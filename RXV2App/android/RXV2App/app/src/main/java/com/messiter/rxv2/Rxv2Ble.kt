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
        const val WEAK_RSSI = -85      // at or below this, too weak to connect reliably
        fun signalWord(rssi: Int) = when {
            rssi >= -70 -> "Strong"
            rssi >= -84 -> "Good"
            rssi >= -92 -> "Weak"
            else        -> "Too far"
        }
        fun tooWeak(rssi: Int) = rssi != 0 && rssi <= WEAK_RSSI
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
        data class Reconnecting(val name: String) : State()
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
    private class Pending(val payload: ByteArray, val cb: (kotlin.Result<Response>) -> Unit,
                          val rawChunks: List<ByteArray>? = null,
                          val firstByteMs: Long = 12000)
    private val queue = ArrayDeque<Pending>()
    private var inFlight: Pending? = null
    private var rxHeader = ByteArrayOut()
    private var rxBody = ByteArrayOut()
    private var rxExpected = -1
    private var rxCode = 0; private var rxType = ""; private var rxLocation = ""
    private var rxDiscarded = 0
    private var timeout: Runnable? = null
    private val txChunks = ArrayDeque<ByteArray>()   // outgoing request chunks, fed by onCharacteristicWrite

    private fun writeNextChunk(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
        val chunk = txChunks.removeFirstOrNull()
        if (chunk == null) {
            // a raw OTA batch has no reply to wait for — done when drained
            if (inFlight?.rawChunks != null)
                finish(kotlin.Result.success(Response(200, "", "", ByteArray(0))))
            return
        }
        // Write-without-response when the characteristic allows it: the BLE
        // link layer still guarantees delivery AND order, but there is no
        // ATT round trip per chunk — several chunks ride one connection
        // event instead of one each. onCharacteristicWrite still fires when
        // the stack is ready for the next chunk, so sequencing is kept.
        val wnr = (c.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0
        writeChar(g, c, chunk, noResp = wnr)
    }

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
                // Ease downwards only: one advertisement can read several dB
                // low, and a dip should not condemn a receiver that is in range.
                val prev = found[r.device.address]?.rssi
                val shown = if (prev == null) r.rssi else maxOf(r.rssi, prev - 3)
                found[r.device.address] = Discovered(r.device, name, shown)
            }
            val list = synchronized(found) { found.values.sortedByDescending { it.rssi } }
            ui.post { onFound?.invoke(list) }
        }
    }

    // ── Connect / disconnect ────────────────────────────────────────
    private var connName = "RXV2"   // scan-time name; g.device.name is a stale cache
    private var lastDevice: BluetoothDevice? = null
    private var userDisconnect = false

    // A disconnect is only worth riding through when the receiver is known
    // to be rebooting deliberately (install / config save / fly). Plain
    // browsing never arms this — a disconnect then = model switched off →
    // straight back to the scanner (Malcolm 2026-08-07).
    @Volatile var rebootishUntil = 0L
    fun noteRebootish(ms: Long) {
        val until = System.currentTimeMillis() + ms
        if (until > rebootishUntil) rebootishUntil = until
    }
    private var reconnectUntil = 0L

    // connectGatt can sit for half a minute before Android gives up, and out
    // of range it may never report at all - the app just looks stuck (Malcolm
    // 2026-09-12: "it fails slowly and I have to quit the app"). Give it a
    // deadline, and when the signal was weak to begin with, say so plainly.
    private var connectWatchdog: Runnable? = null
    private var connectingRssi = 0

    private fun armConnectWatchdog(name: String, rssi: Int, ms: Long = 12_000) {
        cancelConnectWatchdog()
        connectingRssi = rssi
        val r = Runnable {
            if (state !is State.Connecting) return@Runnable
            runCatching { gatt?.disconnect(); gatt?.close() }
            gatt = null
            state = State.Failed(
                if (rssi != 0 && rssi <= WEAK_RSSI)
                    "Too far away. The signal from $name was weak ($rssi dBm) - get closer and tap it again."
                else
                    "$name did not answer. Get closer, check it is switched on, and tap it again.")
        }
        connectWatchdog = r
        ui.postDelayed(r, ms)
    }
    private fun cancelConnectWatchdog() { connectWatchdog?.let { ui.removeCallbacks(it) }; connectWatchdog = null }

    fun connect(d: Discovered) {
        stopScan()
        connName = d.name
        lastDevice = d.device
        userDisconnect = false
        state = State.Connecting(d.name)
        armConnectWatchdog(d.name, d.rssi)
        // Remember the MAC so the NEXT launch can connect directly
        // (fastConnect) without waiting for a scan to hear an advert.
        context.getSharedPreferences("scanner", android.content.Context.MODE_PRIVATE)
            .edit().putString("lastAddr", d.device.address).putInt("lastRssi", d.rssi).apply()
        gatt = d.device.connectGatt(context, false, gattCb, BluetoothDevice.TRANSPORT_LE)
    }

    // Instant auto-connect (Malcolm 2026-08-17): connect straight to the
    // stored MAC, skipping the advertisement wait. Returns false when
    // nothing is stored or Bluetooth is unavailable — caller falls back to
    // the scan (which keeps running anyway so the list still populates).
    fun fastConnect(name: String, addr: String): Boolean {
        val a = adapter ?: return false
        if (!a.isEnabled) return false
        // No RSSI here - this connects by stored MAC without scanning. Use the
        // strength recorded at the END of the last session: if the model was far
        // away then, scan and let the pilot choose rather than connecting blind.
        val lastRssi = context.getSharedPreferences("scanner", android.content.Context.MODE_PRIVATE)
            .getInt("lastRssi", 0)
        if (tooWeak(lastRssi)) return false
        val dev = runCatching { a.getRemoteDevice(addr) }.getOrNull() ?: return false
        connName = name
        lastDevice = dev
        userDisconnect = false
        state = State.Connecting(name)
        gatt = dev.connectGatt(context, false, gattCb, BluetoothDevice.TRANSPORT_LE)
        return true
    }

    fun disconnect() {
        cancelConnectWatchdog()
        userDisconnect = true
        // No GATT (the link had already dropped, or we are between reconnect
        // attempts): nothing will call back, so go Idle here — otherwise the
        // app stays on a dead page ("Load another model" did nothing).
        val g = gatt
        if (g == null) state = State.Idle else g.disconnect()
    }

    // Quietly re-establish the link after an unexpected drop — above all a
    // firmware install, where the receiver reboots mid-session and comes
    // back ~20 s later. The web page keeps polling the whole time; as soon
    // as the link is back its requests start answering again, so the
    // update flow completes instead of dying at the reboot.
    private fun tryReconnect() {
        if (userDisconnect) { state = State.Idle; return }   // the pilot chose to leave meanwhile
        val d = lastDevice ?: run { state = State.Idle; return }
        if (System.currentTimeMillis() > reconnectUntil) { state = State.Idle; return }
        gatt = d.connectGatt(context, false, gattCb, BluetoothDevice.TRANSPORT_LE)
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
            if (state !is State.Ready) {
                // Fail fast (notably while quietly reconnecting after a
                // firmware-install reboot) so page polls keep their cadence.
                cb(kotlin.Result.failure(Exception("Not connected")))
                return@post
            }
            // A flight-controller read through /api/msp can hold the receiver
            // longer than a page: Rotorflight meters big replies out at
            // ~0.5-0.8 s per 58-byte chunk (588-byte adjustment table ~6 s)
            // and the receiver waits up to 12 s for them (fw 0.9.560).
            val window = if (path.startsWith("/api/msp")) 14000L else 12000L
            queue.addLast(Pending(payload, cb, firstByteMs = window))
            pump()
        }
    }

    /** Max payload bytes per OTA chunk ([0xA5] + 4-byte offset overhead). */
    fun otaChunkSize(): Int = ((mtu - 3).coerceAtMost(240) - 5).coerceAtLeast(64)

    /** Stream pre-framed raw OTA chunks ([0xA5][offset LE][data]) through the
     *  ordered write pipeline; completes when the last write is accepted.
     *  Flow control is the ATT layer itself + periodic /api/bleota/status. */
    fun otaSend(chunks: List<ByteArray>, cb: (kotlin.Result<Unit>) -> Unit) {
        bg.post {
            if (state !is State.Ready) { cb(kotlin.Result.failure(Exception("Not connected"))); return@post }
            queue.addLast(Pending(ByteArray(0), { r -> cb(r.map { }) }, rawChunks = chunks))
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
        txChunks.clear()

        next.rawChunks?.let { raw ->
            txChunks.addAll(raw)
            writeNextChunk(g, req)
            armTimeout(20000)
            return
        }

        val prefix = "Q${next.payload.size}|".toByteArray(Charsets.UTF_8)
        // Cap request chunks at 240 bytes. Two reasons: Android hard-rejects
        // GATT writes over 512 bytes (with MTU 517, mtu-3 = 514 -> instant
        // IllegalArgumentException that KILLS the BLE thread — found when the
        // editor synced a 3 KB template on navigation), and 240 is the size
        // every phone in this house has proven to carry reliably.
        val attMax = (mtu - 3).coerceAtLeast(20).coerceAtMost(240)
        // Small requests (the polls) go write-without-response so the reply
        // rides the next radio event — halves per-poll latency. Larger ones
        // use acknowledged, chunked writes for ordering.
        if (prefix.size + next.payload.size <= attMax &&
            (req.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0) {
            writeChar(g, req, prefix + next.payload, noResp = true)
        } else {
            // Multi-chunk request. Android accepts ONE GATT write at a time:
            // issuing the next chunk before onCharacteristicWrite fires makes
            // it silently rejected — every chunk after the first was lost and
            // a 3 KB upload turned into a 12 s timeout. Queue the chunks and
            // let the completion callback feed them out one by one.
            txChunks.clear()
            var off = 0
            val take = (attMax - prefix.size).coerceAtMost(next.payload.size)
            txChunks.addLast(prefix + next.payload.copyOfRange(0, take))
            off = take
            while (off < next.payload.size) {
                val n = (attMax - 1).coerceAtMost(next.payload.size - off)
                val cont = ByteArray(1 + n); cont[0] = '+'.code.toByte()
                System.arraycopy(next.payload, off, cont, 1, n)
                txChunks.addLast(cont)
                off += n
            }
            writeNextChunk(g, req)
        }
        // Generous first-byte window: /api/firmware/check blocks the receiver
        // for up to ~8 s of dead air while it fetches manifests over HTTPS.
        armTimeout(next.firstByteMs)
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
                    if (!userDisconnect && state is State.Ready &&
                        System.currentTimeMillis() < rebootishUntil) {
                        reconnectUntil = System.currentTimeMillis() + 90_000
                        state = State.Reconnecting(connName)
                        bg.postDelayed({ tryReconnect() }, 2000)
                    } else if (!userDisconnect && state is State.Reconnecting) {
                        bg.postDelayed({ tryReconnect() }, 2000)
                    } else {
                        state = State.Idle
                    }
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
        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic,
                                           status: Int) {
            if (c.uuid == REQ) bg.post { writeNextChunk(g, c) }
        }
        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            bg.post {
                cancelConnectWatchdog()
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
