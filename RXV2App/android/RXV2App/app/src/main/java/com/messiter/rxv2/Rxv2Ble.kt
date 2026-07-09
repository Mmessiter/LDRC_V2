// LockDownRadioControl — RXV2App (Android)  ::  Rxv2Ble.kt
//
// The Kotlin twin of the iOS BleLink. Speaks the firmware's HTTP-over-BLE
// framing (RXV2/src/BleConfig.h):
//   request  (app → rx):  first write  'Q'<totalLen>'|'<payload>,
//                         continuations '+'<payload>
//   payload:              "METHOD path[?query]\n{Header: v\n}\n\nbody"
//   response (rx → app):  first notify  'R'<code>'|'<type>'|'<len>'|'<loc>'\n'
//                         then raw body bytes until <len> received.
//   stream (rx → app):    'S|us0,..,us15|age\n' pushed between responses.
//
// One request in flight at a time; requests queue and run in order. All
// pipeline state is touched only on the main Looper (like the iOS main
// queue), so GATT callbacks post here.

package com.messiter.rxv2

import android.annotation.SuppressLint
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.ParcelUuid
import java.util.UUID

@SuppressLint("MissingPermission")
class Rxv2Ble(private val context: Context) {

    companion object {
        val SERVICE: UUID  = UUID.fromString("8e400001-f315-4f60-9fb8-838830daea50")
        val REQ: UUID      = UUID.fromString("8e400002-f315-4f60-9fb8-838830daea50")
        val RESP: UUID     = UUID.fromString("8e400003-f315-4f60-9fb8-838830daea50")
        val CCCD: UUID     = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
    }

    data class Discovered(val device: BluetoothDevice, val name: String, val rssi: Int)
    class Response(val code: Int, val contentType: String, val location: String, val body: ByteArray)

    sealed class State {
        object Idle : State()
        object Scanning : State()
        data class Connecting(val name: String) : State()
        data class Ready(val name: String) : State()
        data class Failed(val msg: String) : State()
    }

    // ── Observable state (simple listener callbacks; UI is a plain Activity) ─
    var onState: ((State) -> Unit)? = null
    var onFound: ((List<Discovered>) -> Unit)? = null
    var onStreamFrame: ((String) -> Unit)? = null

    var state: State = State.Idle
        private set(v) { field = v; ui.post { onState?.invoke(v) } }
    private val found = LinkedHashMap<String, Discovered>()

    // The whole BLE pipeline runs on its OWN thread, NOT the main/UI thread.
    // On Android the WebView renders in-process; if radio parsing shared the
    // UI thread, page rendering and Bluetooth would block each other and
    // everything would crawl (unlike iOS, where WebKit is out-of-process).
    // Only the public callbacks are marshalled to the UI thread.
    private val bgThread = HandlerThread("rxv2-ble").apply { start() }
    private val bg = Handler(bgThread.looper)
    private val ui = Handler(Looper.getMainLooper())
    private val adapter: BluetoothAdapter? =
        (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private var scanner: BluetoothLeScanner? = null
    private var gatt: BluetoothGatt? = null
    private var reqChr: BluetoothGattCharacteristic? = null
    private var respChr: BluetoothGattCharacteristic? = null
    private var mtu = 23

    // ── Single-request pipeline ────────────────────────────────────
    private class Pending(val payload: ByteArray, val cb: (kotlin.Result<Response>) -> Unit)
    private val queue = ArrayDeque<Pending>()
    private var inFlight: Pending? = null
    private var rxHeader = ByteArrayOut()
    private var rxBody = ByteArrayOut()
    private var rxExpected = -1
    private var rxCode = 0; private var rxType = ""; private var rxLocation = ""
    private var rxDiscarded = 0
    private var timeout: Runnable? = null

    // ── Scanning ────────────────────────────────────────────────────
    fun startScan() {
        val a = adapter ?: run { state = State.Failed("Bluetooth unavailable"); return }
        if (!a.isEnabled) { state = State.Failed("Bluetooth is switched off"); return }
        found.clear(); onFound?.invoke(emptyList())
        state = State.Scanning
        scanner = a.bluetoothLeScanner
        // No hardware filter — Samsung/Qualcomm offloaded scanners miss
        // 128-bit UUIDs; match the service UUID in software (onScanResult).
        val settings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        runCatching { scanner?.startScan(null, settings, scanCb) }
            .onFailure { state = State.Failed("Bluetooth permission needed") }
    }

    fun stopScan() { runCatching { scanner?.stopScan(scanCb) } }

    private val scanCb = object : ScanCallback() {
        override fun onScanResult(type: Int, r: ScanResult) {
            val uuids = r.scanRecord?.serviceUuids
            if (uuids == null || uuids.none { it.uuid == SERVICE }) return
            // The real name rides the scan RESPONSE; adv-only results have a
            // null deviceName. Never let those downgrade a name we already
            // captured (device.name is Android's stale cache, "RXV2" is our
            // placeholder of last resort).
            synchronized(found) {
                val name = r.scanRecord?.deviceName
                    ?: found[r.device.address]?.name
                    ?: r.device.name ?: "RXV2"
                found[r.device.address] = Discovered(r.device, name, r.rssi)
            }
            val list = synchronized(found) { found.values.sortedByDescending { it.rssi } }
            ui.post { onFound?.invoke(list) }
        }
    }

    // ── Connect / disconnect ────────────────────────────────────────
    private var connName = "RXV2"   // scan-time name; g.device.name is a stale cache

    fun connect(d: Discovered) {
        stopScan()
        connName = d.name
        state = State.Connecting(d.name)
        gatt = d.device.connectGatt(context, false, gattCb, BluetoothDevice.TRANSPORT_LE)
    }

    fun disconnect() {
        gatt?.disconnect()
    }

    // ── Public request API ──────────────────────────────────────────
    fun request(method: String, path: String, headers: Map<String, String>,
                body: ByteArray?, cb: (kotlin.Result<Response>) -> Unit) {
        val sb = StringBuilder("$method $path\n")
        for ((k, v) in headers) sb.append("$k: $v\n")
        sb.append("\n")
        val head = sb.toString().toByteArray(Charsets.UTF_8)
        val payload = if (body != null) head + body else head
        bg.post {
            queue.addLast(Pending(payload, cb))
            pump()
        }
    }

    // ── Pipeline internals (main thread only) ───────────────────────
    private fun pump() {
        if (inFlight != null) return
        val g = gatt ?: return
        val req = reqChr ?: return
        if (state !is State.Ready) return
        val next = queue.removeFirstOrNull() ?: return
        inFlight = next
        rxHeader = ByteArrayOut(); rxBody = ByteArrayOut(); rxExpected = -1; rxDiscarded = 0

        val prefix = "Q${next.payload.size}|".toByteArray(Charsets.UTF_8)
        val attMax = (mtu - 3).coerceAtLeast(20)
        // Small requests (the polls) go write-without-response so the reply
        // rides the next radio event — halves per-poll latency. Larger ones
        // use acknowledged, chunked writes for ordering.
        if (prefix.size + next.payload.size <= attMax &&
            (req.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0) {
            writeChar(g, req, prefix + next.payload, noResp = true)
        } else {
            var off = 0
            val take = (attMax - prefix.size).coerceAtMost(next.payload.size)
            writeChar(g, req, prefix + next.payload.copyOfRange(0, take), noResp = false)
            off = take
            while (off < next.payload.size) {
                val n = (attMax - 1).coerceAtMost(next.payload.size - off)
                val cont = ByteArray(1 + n); cont[0] = '+'.code.toByte()
                System.arraycopy(next.payload, off, cont, 1, n)
                writeChar(g, req, cont, noResp = false)
                off += n
            }
        }
        // Generous first-byte window: /api/firmware/check blocks the receiver
        // for up to ~8 s of dead air while it fetches manifests over HTTPS.
        armTimeout(12000)
    }

    private fun writeChar(g: BluetoothGatt, c: BluetoothGattCharacteristic,
                          data: ByteArray, noResp: Boolean) {
        val type = if (noResp) BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                   else BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        if (Build.VERSION.SDK_INT >= 33) {
            g.writeCharacteristic(c, data, type)
        } else {
            @Suppress("DEPRECATION")
            run { c.writeType = type; c.value = data; g.writeCharacteristic(c) }
        }
    }

    private fun armTimeout(ms: Long) {
        timeout?.let { bg.removeCallbacks(it) }
        timeout = Runnable {
            finish(kotlin.Result.failure(Exception("Receiver did not answer (timeout)")))
        }.also { bg.postDelayed(it, ms) }
    }

    private fun finish(result: kotlin.Result<Response>) {
        timeout?.let { bg.removeCallbacks(it) }; timeout = null
        val done = inFlight; inFlight = null
        done?.cb?.invoke(result)
        pump()
    }

    private fun handleNotify(data: ByteArray) {
        if (inFlight == null) {
            // Between requests: only pushed channel frames appear.
            if (data.isNotEmpty() && data[0] == 'S'.code.toByte()) {
                val s = String(data, Charsets.UTF_8)
                if (s.startsWith("S|")) ui.post { onStreamFrame?.invoke(s) }
            }
            return
        }
        armTimeout(5000)
        if (rxExpected < 0) {
            rxHeader.append(data)
            while (true) {
                val nl = rxHeader.indexOf('\n'.code.toByte())
                if (nl < 0) {
                    if (rxHeader.size() + rxDiscarded > 32768)
                        finish(kotlin.Result.failure(Exception("Bad response framing")))
                    return
                }
                val line = String(rxHeader.bytes(), 0, nl, Charsets.UTF_8)
                if (line.startsWith("S|")) {
                    ui.post { onStreamFrame?.invoke(line) }
                    rxHeader = rxHeader.drop(nl + 1); continue
                }
                if (line.startsWith("R")) {
                    val parts = line.substring(1).split("|", limit = 4)
                    val code = parts.getOrNull(0)?.toIntOrNull()
                    val len = parts.getOrNull(2)?.toIntOrNull()
                    if (parts.size >= 3 && code != null && len != null &&
                        code in 100..599 && len >= 0) {
                        rxCode = code; rxType = parts[1]; rxExpected = len
                        rxLocation = if (parts.size > 3) parts[3] else ""
                        rxBody = ByteArrayOut(); rxBody.append(rxHeader.bytes(), nl + 1, rxHeader.size() - (nl + 1))
                        rxHeader = ByteArrayOut()
                        break
                    }
                }
                rxDiscarded += nl + 1
                rxHeader = rxHeader.drop(nl + 1)
                if (rxDiscarded > 32768) {
                    finish(kotlin.Result.failure(Exception("Bad response framing"))); return
                }
            }
        } else {
            rxBody.append(data)
        }
        if (rxExpected in 0..rxBody.size()) {
            val body = rxBody.bytes().copyOfRange(0, rxExpected)
            finish(kotlin.Result.success(Response(rxCode, rxType, rxLocation, body)))
        }
    }

    private fun cleanup(msg: String) {
        timeout?.let { bg.removeCallbacks(it) }; timeout = null
        inFlight?.cb?.invoke(kotlin.Result.failure(Exception(msg))); inFlight = null
        while (queue.isNotEmpty()) queue.removeFirst().cb.invoke(kotlin.Result.failure(Exception(msg)))
        reqChr = null; respChr = null
    }

    // ── GATT callbacks (binder thread → post to main) ──────────────
    private val gattCb = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                // ONE GATT op at a time on Android. Request MTU first; the
                // fast-connection request is issued from onMtuChanged (once
                // the MTU exchange has completed) so it isn't silently
                // dropped. Without the fast interval the receiver's TX
                // buffer can't drain and large replies stall part-way.
                g.requestMtu(517)
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                bg.post {
                    cleanup("Receiver disconnected")
                    g.close(); gatt = null
                    state = State.Idle
                }
            }
        }
        override fun onMtuChanged(g: BluetoothGatt, m: Int, status: Int) {
            mtu = if (status == BluetoothGatt.GATT_SUCCESS) m else 23
            // Now that the MTU exchange is done, ask for the fast interval
            // (sequenced, so it isn't dropped). Then discover services.
            g.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH)
            g.discoverServices()
        }
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            val svc = g.getService(SERVICE) ?: run {
                run { state = State.Failed("RXV2 service not found") }; return
            }
            reqChr = svc.getCharacteristic(REQ)
            respChr = svc.getCharacteristic(RESP)
            val rc = respChr
            if (reqChr == null || rc == null) {
                run { state = State.Failed("Characteristics missing") }; return
            }
            g.setCharacteristicNotification(rc, true)
            val d = rc.getDescriptor(CCCD)
            if (Build.VERSION.SDK_INT >= 33) {
                g.writeDescriptor(d, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            } else {
                @Suppress("DEPRECATION")
                run { d.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE; g.writeDescriptor(d) }
            }
        }
        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            bg.post {
                state = State.Ready(connName)
                pump()
            }
        }
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic,
                                             value: ByteArray) {
            if (c.uuid == RESP) bg.post { handleNotify(value) }
        }
        @Deprecated("pre-33")
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
            @Suppress("DEPRECATION")
            val v = c.value ?: return
            if (c.uuid == RESP) bg.post { handleNotify(v) }
        }
    }
}

// Small growable byte buffer (avoids pulling in extra deps).
class ByteArrayOut {
    private var buf = ByteArray(256)
    private var len = 0
    fun append(d: ByteArray) = append(d, 0, d.size)
    fun append(d: ByteArray, off: Int, n: Int) {
        ensure(len + n); System.arraycopy(d, off, buf, len, n); len += n
    }
    fun size() = len
    fun bytes() = buf
    fun indexOf(b: Byte): Int { for (i in 0 until len) if (buf[i] == b) return i; return -1 }
    fun drop(from: Int): ByteArrayOut {
        val out = ByteArrayOut(); if (from < len) out.append(buf, from, len - from); return out
    }
    private fun ensure(cap: Int) {
        if (cap <= buf.size) return
        var n = buf.size; while (n < cap) n *= 2
        buf = buf.copyOf(n)
    }
}
