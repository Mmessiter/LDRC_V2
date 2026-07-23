// LockDownRadioControl — RXV2App (Android)  ::  MainActivity.kt
//
// Scanner list → WebView hosting the receiver's own web UI, every HTTP
// request tunnelled over Bluetooth. Two interception paths, because
// Android's WebView cannot read POST bodies in shouldInterceptRequest:
//   • Static pages/assets (GET) are served from assets/webroot by
//     shouldInterceptRequest — no radio traffic.
//   • All fetch() (the /api polls and every POST) is bridged through a
//     JavaScript shim to a @JavascriptInterface, which crosses BLE and
//     resolves the JS Promise. Redirects (POST→303→GET) are followed
//     here and the final page returned, mirroring the iOS handler.

package com.messiter.rxv2

import android.Manifest
import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.view.View
import android.view.ViewGroup
import android.webkit.*
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.ByteArrayInputStream

class MainActivity : AppCompatActivity() {

    private lateinit var ble: Rxv2Ble
    private lateinit var root: FrameLayout
    private var webView: WebView? = null
    private var demoMode = false
    private var demoBtn: TextView? = null

    // Fake same-origin the WebView believes it is talking to. Every request
    // to this host is intercepted; the network is never actually touched.
    private val ORIGIN = "https://rxv2.local"

    // Where publish_app.sh puts each release (host 301s plain http — keep https).
    private val APP_MANIFEST_URL = "https://www.messiter.com/rxv2app/release/manifest.json"

    // The RECEIVER's public release manifest — fetched by the app on the
    // pages' behalf (/app/manifest): the phone has internet at the field,
    // the Bluetooth-only receiver does not.
    private val RX_MANIFEST_URL = "https://www.messiter.com/rxv2/release/manifest.json"

    private val permReq = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()
    ) { if (it.values.all { g -> g }) ble.startScan() else showMessage("Bluetooth permission is needed.") }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ble = Rxv2Ble(applicationContext)
        root = FrameLayout(this)
        setContentView(root)
        // Android 15+ draws apps edge-to-edge: without this, the update
        // banner (and the top of the scanner) slide UNDER the status bar,
        // where taps never reach them. Pad the root by the system bars.
        root.setOnApplyWindowInsetsListener { v, insets ->
            if (Build.VERSION.SDK_INT >= 30) {
                val b = insets.getInsets(android.view.WindowInsets.Type.systemBars())
                v.setPadding(b.left, b.top, b.right, b.bottom)
            } else {
                @Suppress("DEPRECATION")
                v.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                             insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
            }
            insets
        }

        ble.onState = { st ->
            when (st) {
                is Rxv2Ble.State.Ready -> { demoMode = false; showWeb() }
                is Rxv2Ble.State.Failed -> { showScanner(); showMessage(st.msg) }
                is Rxv2Ble.State.Idle -> showScanner()
                else -> {}
            }
        }
        ble.onFound = { list ->
            scannerAdapter?.submit(list)
            // a real receiver in sight → the demo offer just muddies the water
            demoBtn?.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
        }
        ble.onStreamFrame = { line -> injectStream(line) }

        showScanner()
        requestPerms()
    }

    private fun requestPerms() {
        val needed = if (Build.VERSION.SDK_INT >= 31)
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (needed.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED })
            ble.startScan()
        else permReq.launch(needed)   // callback starts the scan on grant
    }

    override fun onBackPressed() {
        val w = webView
        if (w != null && w.canGoBack()) w.goBack()
        else if (w != null) {
            if (demoMode) { demoMode = false; showScanner() }
            else ble.disconnect()               // Ready → back = disconnect
        }
        else super.onBackPressed()
    }

    // ── Scanner list ────────────────────────────────────────────────
    private var scannerAdapter: ScannerAdapter? = null

    private fun showScanner() {
        webView?.let { it.stopLoading(); it.destroy() }; webView = null
        root.removeAllViews()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        col.addView(TextView(this).apply {
            text = "RXV2 Receivers"; textSize = 22f; setPadding(40, 60, 40, 8)
        })
        col.addView(TextView(this).apply {
            text = "App v" + packageManager.getPackageInfo(packageName, 0).versionName
            setPadding(40, 0, 40, 8); alpha = 0.5f; textSize = 12f
        })
        col.addView(TextView(this).apply {
            text = "Power the receiver with the transmitter OFF so its config radio comes up. The WiFi web interface still works exactly as before."
            setPadding(40, 0, 40, 20); alpha = 0.7f; textSize = 13f
        })
        val list = ListView(this)
        scannerAdapter = ScannerAdapter()
        list.adapter = scannerAdapter
        list.setOnItemClickListener { _, _, pos, _ -> ble.connect(scannerAdapter!!.item(pos)) }
        col.addView(list, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        val hint = TextView(this).apply {
            text = "Searching…  Bring the receiver within a few metres."
            setPadding(40, 16, 40, 40); alpha = 0.6f; textSize = 13f
        }
        col.addView(hint)
        // No receiver? Let anyone play: the same web UI runs against
        // canned data from a real receiver, with animated channels.
        demoBtn = TextView(this).apply {
            text = "🎭  No receiver yet?  Try the demo"
            textSize = 15f; setPadding(40, 28, 40, 28)
            setBackgroundColor(0xFF1E293B.toInt()); setTextColor(0xFF7DD3FC.toInt())
            setOnClickListener { demoMode = true; showWeb() }
        }
        col.addView(demoBtn)
        root.addView(col)
        startScanIfPermitted()
        checkAppUpdate(col)
    }

    // ── App self-update ─────────────────────────────────────────────
    // The same idea as the receiver's own update banner: check messiter.com
    // for a newer build of THIS app and offer it with one tap. The APK is
    // downloaded in-app (progress in the notification shade) and handed
    // straight to Android's installer when it completes — no trip through
    // the browser and its blank tab. First ever time, Android sends the
    // user to Settings to allow this app to install updates; we then carry
    // on automatically. Checked once per launch, on the scanner screen.
    private var lastUpdateCheck = 0L
    private var pendingUpdate: Pair<String, String>? = null   // url to versionName

    private fun checkAppUpdate(col: LinearLayout) {
        // every visit to the scanner re-checks (a backgrounded app can sit in
        // recents for days — a once-per-launch gate never fired again);
        // lightly throttled so back-and-forth doesn't hammer the server
        if (System.currentTimeMillis() - lastUpdateCheck < 60_000) return
        lastUpdateCheck = System.currentTimeMillis()
        Thread {
            runCatching {
                val txt = java.net.URL(APP_MANIFEST_URL).openStream()
                    .use { it.readBytes().toString(Charsets.UTF_8) }
                val j = JSONObject(txt)
                val newest = j.getInt("versionCode")
                val name = j.optString("versionName", "?")
                val url = j.getString("url")
                val installed = packageManager.getPackageInfo(packageName, 0).run {
                    if (Build.VERSION.SDK_INT >= 28) longVersionCode.toInt()
                    else @Suppress("DEPRECATION") versionCode
                }
                if (newest > installed) runOnUiThread {
                    if (col.parent == null) return@runOnUiThread   // scanner gone — connected already
                    col.addView(TextView(this).apply {
                        text = "⬆️  App update available: v$name — tap to install"
                        textSize = 15f; setPadding(40, 28, 40, 28)
                        setBackgroundColor(0xFFFFD278.toInt()); setTextColor(0xFF5C3A00.toInt())
                        setOnClickListener { installUpdate(url, name) }
                    }, 0)
                }
            }
        }.start()
    }

    private fun installUpdate(url: String, name: String) {
        // One-time gate: this app needs the "install unknown apps" permission.
        // Send the user straight to our entry in Settings; onResume retries.
        if (!packageManager.canRequestPackageInstalls()) {
            pendingUpdate = url to name
            showMessage("Please allow RXV2 to install updates, then come back.")
            startActivity(android.content.Intent(
                android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:$packageName")))
            return
        }
        showMessage("Downloading v$name…")
        val dm = getSystemService(DOWNLOAD_SERVICE) as android.app.DownloadManager
        val req = android.app.DownloadManager.Request(Uri.parse(url))
            .setTitle("RXV2 app v$name")
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(
                android.app.DownloadManager.Request.VISIBILITY_VISIBLE)
            .setDestinationInExternalFilesDir(this, null, "RXV2App-$name.apk")
        val id = dm.enqueue(req)
        val rx = object : android.content.BroadcastReceiver() {
            override fun onReceive(c: android.content.Context?, i: android.content.Intent?) {
                if (i?.getLongExtra(android.app.DownloadManager.EXTRA_DOWNLOAD_ID, -1) != id) return
                runCatching { unregisterReceiver(this) }
                val apk = dm.getUriForDownloadedFile(id)
                    ?: run { showMessage("Download failed — please try again."); return }
                startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW)
                    .setDataAndType(apk, "application/vnd.android.package-archive")
                    .addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or
                              android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
            }
        }
        val filter = android.content.IntentFilter(
            android.app.DownloadManager.ACTION_DOWNLOAD_COMPLETE)
        if (Build.VERSION.SDK_INT >= 33)
            registerReceiver(rx, filter, android.content.Context.RECEIVER_EXPORTED)
        else registerReceiver(rx, filter)
    }

    override fun onResume() {
        super.onResume()
        // Back from the Settings permission screen — resume the update.
        pendingUpdate?.let { (url, name) ->
            if (packageManager.canRequestPackageInstalls()) {
                pendingUpdate = null
                installUpdate(url, name)
            }
        }
    }

    // Scan only once the runtime BLE permission is granted — calling the
    // scanner without it throws a SecurityException (crash on launch).
    private fun startScanIfPermitted() {
        val perms = if (Build.VERSION.SDK_INT >= 31)
            arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (perms.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED })
            ble.startScan()
    }

    inner class ScannerAdapter : BaseAdapter() {
        private var items: List<Rxv2Ble.Discovered> = emptyList()
        fun submit(l: List<Rxv2Ble.Discovered>) { items = l; notifyDataSetChanged() }
        fun item(i: Int) = items[i]
        override fun getCount() = items.size
        override fun getItem(i: Int) = items[i]
        override fun getItemId(i: Int) = i.toLong()
        override fun getView(i: Int, convert: View?, parent: ViewGroup?): View {
            val v = convert as? LinearLayout ?: LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL; setPadding(40, 28, 40, 28)
            }
            v.removeAllViews()
            val d = items[i]
            v.addView(TextView(this@MainActivity).apply { text = d.name; textSize = 17f })
            v.addView(TextView(this@MainActivity).apply {
                text = "Signal ${d.rssi} dBm"; alpha = 0.6f; textSize = 12f
            })
            return v
        }
    }

    // ── WebView over BLE ────────────────────────────────────────────
    @SuppressLint("SetJavaScriptEnabled")
    // ── BLE OTA push: phone downloads (WiFi or 5G), streams over Bluetooth ──
    @Volatile private var otaPhase = "idle"     // idle|download|fw|fs|finish|rebooting|error|done
    @Volatile private var otaMsg = ""
    @Volatile private var otaSent = 0L
    @Volatile private var otaTotal = 0L

    private fun bleReqSync(method: String, path: String, body: ByteArray? = null): Rxv2Ble.Response {
        val latch = java.util.concurrent.CountDownLatch(1)
        var result: kotlin.Result<Rxv2Ble.Response>? = null
        ble.request(method, path, emptyMap(), body) { r -> result = r; latch.countDown() }
        if (!latch.await(30, java.util.concurrent.TimeUnit.SECONDS))
            throw Exception("BLE request timed out: $path")
        return result!!.getOrThrow()
    }

    private fun otaSendSync(chunks: List<ByteArray>) {
        val latch = java.util.concurrent.CountDownLatch(1)
        var err: Throwable? = null
        ble.otaSend(chunks) { r -> err = r.exceptionOrNull(); latch.countDown() }
        if (!latch.await(60, java.util.concurrent.TimeUnit.SECONDS)) throw Exception("chunk batch stalled")
        err?.let { throw it }
    }

    private fun httpDownload(url: String): ByteArray {
        val conn = java.net.URL(url).openConnection() as java.net.HttpURLConnection
        conn.connectTimeout = 15000; conn.readTimeout = 30000
        conn.instanceFollowRedirects = true
        try {
            if (conn.responseCode != 200) throw Exception("HTTP ${conn.responseCode} for $url")
            return conn.inputStream.readBytes()
        } finally { conn.disconnect() }
    }

    private fun otaStatus(): org.json.JSONObject =
        org.json.JSONObject(String(bleReqSync("GET", "/api/bleota/status").body))

    private fun streamImage(type: String, bytes: ByteArray, base: Long) {
        val begin = bleReqSync("POST", "/api/bleota/begin?type=$type&size=${bytes.size}")
        if (begin.code == 404)
            throw Exception("this receiver's firmware is too old for Bluetooth updates — do this one update over WiFi, then Bluetooth works from now on")
        if (begin.code != 200) throw Exception("begin($type): ${String(begin.body)}")
        val chunkData = ble.otaChunkSize()
        var off = 0
        // A BLE hiccup mid-stream is NOT fatal: the receiver keeps the
        // transfer open (it only ever accepts the next in-sequence chunk),
        // so on any error we re-ask where it got to and carry on from there.
        // Only give up after several consecutive failures with no progress.
        var fails = 0
        while (off < bytes.size) {
            try {
                val batch = ArrayList<ByteArray>(128)
                var o = off
                while (o < bytes.size && batch.size < 128) {
                    val n = minOf(chunkData, bytes.size - o)
                    val frame = ByteArray(5 + n)
                    frame[0] = 0xA5.toByte()
                    frame[1] = (o and 0xFF).toByte(); frame[2] = ((o shr 8) and 0xFF).toByte()
                    frame[3] = ((o shr 16) and 0xFF).toByte(); frame[4] = ((o shr 24) and 0xFF).toByte()
                    System.arraycopy(bytes, o, frame, 5, n)
                    batch.add(frame); o += n
                }
                otaSendSync(batch)
                // resync: the receiver only accepts in-sequence chunks
                val st = otaStatus()
                val err = st.optString("error", "")
                if (err.isNotEmpty()) throw Exception("receiver: $err")
                if (!st.optBoolean("active", true))
                    throw Exception("receiver abandoned the transfer")
                val got = st.optLong("got", o.toLong()).toInt()
                fails = if (got > off) 0 else fails + 1
                if (fails >= 5) throw Exception("no progress after 5 attempts at ${off / 1024} KB")
                off = got
                otaSent = base + off
            } catch (e: Exception) {
                val m = e.message ?: ""
                if (m.startsWith("receiver") || m.startsWith("no progress") || m.contains("too old")) throw e
                if (++fails >= 5) throw e
                Thread.sleep(1500)   // transient (timeout / stalled batch) — resync and retry
                runCatching { off = otaStatus().optLong("got", off.toLong()).toInt() }
            }
        }
        val end = bleReqSync("POST", "/api/bleota/end")
        if (end.code != 200) throw Exception("end($type): ${String(end.body)}")
    }

    private fun runBleOta(fwUrl: String, fsUrl: String?) {
        try {
            otaPhase = "download"; otaMsg = "Downloading with the phone's internet…"; otaSent = 0; otaTotal = 0
            val fw = httpDownload(fwUrl)
            var fs = fsUrl?.takeIf { it.isNotBlank() }?.let { runCatching { httpDownload(it) }.getOrNull() }
            // Older on-receiver pages omit &fs= — derive the pages image from
            // the release-directory convention so web pages always ship too.
            if (fs == null && fwUrl.endsWith("firmware.bin"))
                fs = runCatching { httpDownload(fwUrl.removeSuffix("firmware.bin") + "littlefs.bin") }.getOrNull()
            otaTotal = fw.size.toLong() + (fs?.size ?: 0).toLong()
            // one clean restart per image: /begin resets the receiver side,
            // so a transfer that died mid-way gets a second, fresh attempt
            val sendImage = { type: String, bytes: ByteArray, base: Long, label: String ->
                try { streamImage(type, bytes, base) } catch (e: Exception) {
                    if ((e.message ?: "").contains("too old")) throw e
                    otaMsg = "Bluetooth hiccup — starting the $label again…"
                    Thread.sleep(2000)
                    streamImage(type, bytes, base)
                }
            }
            otaPhase = "fw"; otaMsg = "Sending firmware over Bluetooth…"
            sendImage("fw", fw, 0L, "firmware")
            if (fs != null) {
                otaPhase = "fs"; otaMsg = "Sending web pages over Bluetooth…"
                sendImage("fs", fs, fw.size.toLong(), "web pages")
            }
            otaPhase = "rebooting"; otaMsg = "Waiting for the receiver to come back…"
            runCatching { bleReqSync("POST", "/api/bleota/reboot") }   // reply may die with the radio
            // The receiver reboots straight back into BLE mode (config-reboot
            // flag) and Rxv2Ble auto-reconnects for 90 s — poll until it
            // answers, then report the version it now runs.
            Thread.sleep(4000)
            var newVer = ""
            val deadline = System.currentTimeMillis() + 120_000
            while (System.currentTimeMillis() < deadline) {
                try {
                    val st = bleReqSync("GET", "/api/state.json")
                    if (st.code == 200) {
                        val v = org.json.JSONObject(String(st.body))
                            .optJSONObject("info")?.optString("fw_version", "") ?: ""
                        if (v.isNotEmpty()) { newVer = v; break }
                    }
                } catch (_: Exception) {}
                Thread.sleep(3000)
            }
            otaPhase = "done"
            otaMsg = if (newVer.isEmpty())
                "installed; the receiver didn't reappear on Bluetooth to confirm — reopen the app to check it"
            else "now running $newVer"
        } catch (e: Exception) {
            otaPhase = "error"; otaMsg = e.message ?: "failed"
            runCatching { bleReqSync("POST", "/api/bleota/status") }
        }
    }

    private fun showWeb() {
        if (webView != null) return
        root.removeAllViews()
        val w = WebView(this)
        webView = w
        w.settings.javaScriptEnabled = true
        w.settings.domStorageEnabled = true
        w.settings.cacheMode = WebSettings.LOAD_NO_CACHE
        w.settings.mediaPlaybackRequiresUserGesture = false
        w.setBackgroundColor(0xFF0B1220.toInt())
        w.addJavascriptInterface(Bridge(), "AndroidBle")
        w.webViewClient = object : WebViewClient() {
            // A crashed WebView renderer otherwise leaves a dead BLACK screen
            // until the app is force-quit (seen on the Fold saving settings,
            // 2026-07-23). Recreate the WebView and reload the front page.
            override fun onRenderProcessGone(view: WebView, detail: android.webkit.RenderProcessGoneDetail): Boolean {
                runOnUiThread {
                    runCatching { view.destroy() }
                    webView = null
                    showWeb()
                }
                return true
            }
            override fun shouldInterceptRequest(view: WebView, req: WebResourceRequest): WebResourceResponse? {
                // Only GET page/asset loads reach here (fetch is bridged in JS).
                if (req.url.host != Uri.parse(ORIGIN).host) return null
                if (req.method.uppercase() != "GET") return null
                val path = req.url.path ?: "/"
                if (path == "/app/bleota/start") {
                    val fw = req.url.getQueryParameter("fw") ?: return jsonResp("{\"ok\":false}")
                    val fs = req.url.getQueryParameter("fs")
                    if (otaPhase != "fw" && otaPhase != "fs" && otaPhase != "download")
                        Thread { runBleOta(fw, fs) }.start()
                    return jsonResp("{\"ok\":true}")
                }
                if (path == "/app/bleota/progress") {
                    val j = org.json.JSONObject()
                    j.put("phase", otaPhase); j.put("msg", otaMsg)
                    j.put("sent", otaSent); j.put("total", otaTotal)
                    return jsonResp(j.toString())
                }
                if (path == "/app/manifest") {
                    // runs on a WebView worker thread — blocking download is fine
                    val json = if (demoMode) "{}"
                               else runCatching { String(httpDownload(RX_MANIFEST_URL)) }.getOrElse { "{}" }
                    return jsonResp(json)
                }
                val asset = bundled(path)
                if (asset != null) {
                    val (bytes, type) = asset
                    val out = when {
                        type == "text/html" -> withShim(bytes)
                        // The web UI decides Bluetooth-vs-WiFi from
                        // location.protocol === 'ble:'. Android loads over
                        // https (custom schemes break WebView storage/fetch),
                        // so patch that one check to true → it shows the
                        // Bluetooth badge and Bluetooth wording, as on iOS.
                        path.endsWith("/app.js") -> String(bytes)
                            .replace("location.protocol === 'ble:'", "true")
                            .toByteArray()
                        else -> bytes
                    }
                    return WebResourceResponse(type, null, 200, "OK",
                        mapOf("Cache-Control" to "no-store"),
                        ByteArrayInputStream(out))
                }
                // Not a static file: a GET page that lives in firmware. Fetch
                // it over BLE synchronously (this runs off the UI thread).
                if (demoMode) return WebResourceResponse("text/plain", null, 404, "Not Found",
                    emptyMap(), ByteArrayInputStream(ByteArray(0)))
                return bleSync(req.method, req.url)
            }
        }
        root.addView(w)
        w.loadUrl("$ORIGIN/")
    }

    // Prepend the bridge shim so it runs before any of the page's scripts.
    // In demo mode the DEMO shim is injected instead: it intercepts fetch()
    // with canned receiver data, so nothing ever touches Bluetooth.
    private fun withShim(html: ByteArray): ByteArray {
        val tag = if (demoMode)
            "<script src=\"/demo-shim.js\"></script>".toByteArray(Charsets.UTF_8)
        else "<script>$JS_SHIM</script>".toByteArray(Charsets.UTF_8)
        return tag + html
    }

    // Blocking BLE fetch for GET navigations that aren't static assets.
    private fun bleSync(method: String, url: Uri): WebResourceResponse {
        val latch = java.util.concurrent.CountDownLatch(1)
        var out: WebResourceResponse? = null
        var pathAndQuery = url.encodedPath ?: "/"
        if (!url.encodedQuery.isNullOrEmpty()) pathAndQuery += "?" + url.encodedQuery
        followFetch(method, pathAndQuery, emptyMap(), null, 0) { res ->
            out = res.fold(
                onSuccess = { r ->
                    val type = r.contentType.ifEmpty { "text/html" }
                    val bytes = if (type.startsWith("text/html")) withShim(r.body) else r.body
                    WebResourceResponse(type, null,
                        if (r.code == 0) 200 else r.code, "OK",
                        mapOf("Cache-Control" to "no-store"), ByteArrayInputStream(bytes))
                },
                onFailure = { e ->
                    val html = "<html><body style='font-family:sans-serif;padding:2em;text-align:center'>" +
                            "<h2>Receiver not reachable</h2><p>${e.message}</p></body></html>"
                    WebResourceResponse("text/html", "utf-8", 502, "Error", null,
                        ByteArrayInputStream(html.toByteArray()))
                })
            latch.countDown()
        }
        runCatching { latch.await(8, java.util.concurrent.TimeUnit.SECONDS) }
        return out ?: WebResourceResponse("text/plain", "utf-8", 504, "Timeout", null,
            ByteArrayInputStream(ByteArray(0)))
    }

    // BLE fetch that follows up to 3 redirects; a redirect target that is a
    // bundled page is served from assets (mirrors the iOS handler).
    private fun followFetch(method: String, pathAndQuery: String, headers: Map<String, String>,
                            body: ByteArray?, hops: Int,
                            cb: (kotlin.Result<Rxv2Ble.Response>) -> Unit) {
        // Static files the pages fetch() (i18n dictionaries etc.) are in the
        // app bundle — serve them locally instead of paying ~half a second
        // of radio time on every page change. /api/* always crosses BLE.
        if (hops == 0 && method == "GET") {
            val bare = pathAndQuery.substringBefore("?")
            if (!bare.startsWith("/api/")) {
                bundled(bare)?.let {
                    cb(kotlin.Result.success(Rxv2Ble.Response(200, it.second, "", it.first)))
                    return
                }
            }
        }
        ble.request(method, pathAndQuery, headers, body) { result ->
            val resp = result.getOrNull()
            if (resp != null && resp.code in 300..399 && resp.location.isNotEmpty() && hops < 3) {
                val loc = if (resp.location.startsWith("/")) resp.location else "/" + resp.location
                val bare = loc.substringBefore("?")
                val asset = bundled(bare)
                if (asset != null) {
                    cb(kotlin.Result.success(Rxv2Ble.Response(200, asset.second, "", asset.first)))
                } else {
                    followFetch("GET", loc, emptyMap(), null, hops + 1, cb)
                }
                return@request
            }
            cb(result)
        }
    }

    // ── JS ↔ Kotlin bridge for fetch() (POST bodies + async) ────────
    inner class Bridge {
        @JavascriptInterface
        fun request(id: Int, method: String, url: String, headersJson: String, body: String) {
            val uri = Uri.parse(if (url.startsWith("http")) url else "$ORIGIN$url")
            var pathAndQuery = uri.encodedPath ?: "/"
            if (!uri.encodedQuery.isNullOrEmpty()) pathAndQuery += "?" + uri.encodedQuery
            // BLE OTA push is handled by the APP, not the receiver — and the
            // page's fetch() arrives HERE (the JS bridge), not in
            // shouldInterceptRequest, so it must be answered here too.
            val p = uri.path ?: "/"
            // Public release manifest, fetched with the PHONE's internet on the
            // pages' behalf (the Bluetooth-only receiver has none at the field).
            if (p == "/app/manifest") {
                Thread {
                    val json = if (demoMode) "{}"
                               else runCatching { String(httpDownload(RX_MANIFEST_URL)) }.getOrElse { "{}" }
                    runOnUiThread {
                        val w = webView ?: return@runOnUiThread
                        val b64 = Base64.encodeToString(json.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
                        w.evaluateJavascript(
                            "window.__bleResolve($id,200,${JSONObject.quote("application/json")},${JSONObject.quote(b64)})", null)
                    }
                }.start()
                return
            }
            if (p == "/app/bleota/start" || p == "/app/bleota/progress") {
                val json = if (p == "/app/bleota/start") {
                    val fw = uri.getQueryParameter("fw")
                    if (fw != null && !demoMode) {
                        if (otaPhase != "download" && otaPhase != "fw" &&
                            otaPhase != "fs" && otaPhase != "rebooting") {
                            val fs = uri.getQueryParameter("fs")
                            otaPhase = "download"; otaMsg = "Starting…"; otaSent = 0; otaTotal = 0
                            Thread { runBleOta(fw, fs) }.start()
                        }
                        "{\"ok\":true}"
                    } else "{\"ok\":false}"
                } else {
                    val j = JSONObject()
                    j.put("phase", otaPhase); j.put("msg", otaMsg)
                    j.put("sent", otaSent); j.put("total", otaTotal)
                    j.toString()
                }
                runOnUiThread {
                    val w = webView ?: return@runOnUiThread
                    val b64 = Base64.encodeToString(json.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
                    w.evaluateJavascript(
                        "window.__bleResolve($id,200,${JSONObject.quote("application/json")},${JSONObject.quote(b64)})", null)
                }
                return
            }
            val headers = HashMap<String, String>()
            runCatching {
                val o = JSONObject(headersJson)
                o.keys().forEach { k -> headers[k] = o.getString(k) }
            }
            val bodyData = if (body.isNotEmpty()) body.toByteArray(Charsets.UTF_8) else null
            followFetch(method.uppercase(), pathAndQuery, headers, bodyData, 0) { result ->
                runOnUiThread {
                    val w = webView ?: return@runOnUiThread
                    result.fold(
                        onSuccess = { r ->
                            val b64 = Base64.encodeToString(r.body, Base64.NO_WRAP)
                            w.evaluateJavascript(
                                "window.__bleResolve($id,${if (r.code == 0) 200 else r.code}," +
                                "${JSONObject.quote(r.contentType)},${JSONObject.quote(b64)})", null)
                        },
                        onFailure = { e ->
                            w.evaluateJavascript(
                                "window.__bleReject($id,${JSONObject.quote(e.message ?: "error")})", null)
                        })
                }
            }
        }

        @JavascriptInterface
        fun disconnect() { runOnUiThread { ble.disconnect() } }
    }

    // Runs on the main thread already (Rxv2Ble posts onStreamFrame there).
    private fun injectStream(line: String) {
        val clean = line.trim()
        if (!clean.startsWith("S|")) return
        if (!clean.drop(2).all { it.isDigit() || it == ',' || it == '|' || it == '-' }) return
        webView?.evaluateJavascript("window.__rxStream && window.__rxStream('$clean')", null)
    }

    // ── Static assets from assets/webroot (mirrors iOS bundled()) ───
    private val mime = mapOf(
        "html" to "text/html", "css" to "text/css", "js" to "application/javascript",
        "svg" to "image/svg+xml", "jpg" to "image/jpeg", "jpeg" to "image/jpeg",
        "png" to "image/png", "json" to "application/json", "ico" to "image/x-icon")

    private fun bundled(path: String): Pair<ByteArray, String>? {
        var name = if (path == "/") "index.html" else path.trimStart('/')
        if (!name.contains(".")) name += ".html"
        if (name.contains("..")) return null
        // The demo shim lives outside webroot so data syncs can't delete it.
        val dir = if (name.startsWith("demo-")) "demo" else "webroot"
        return runCatching {
            assets.open("$dir/$name").use { it.readBytes() } to
                (mime[name.substringAfterLast('.').lowercase()] ?: "application/octet-stream")
        }.getOrNull()
    }

    private fun jsonResp(j: String) = WebResourceResponse("application/json", null, 200, "OK",
        mapOf("Cache-Control" to "no-store"), java.io.ByteArrayInputStream(j.toByteArray()))

    private fun showMessage(m: String) =
        Toast.makeText(this, m, Toast.LENGTH_LONG).show()

    companion object {
        // Injected into every page: bridge fetch()/forms through AndroidBle,
        // and expose the disconnect hook the page's Bluetooth badge posts to.
        private const val JS_SHIM = """
        (function(){
          if (window.__bleShim) return; window.__bleShim = true;
          window.__blePending = {}; window.__bleSeq = 0;
          window.__bleResolve = function(id, code, type, b64){
            var p = window.__blePending[id]; if(!p) return; delete window.__blePending[id];
            var bytes; try { bytes = Uint8Array.from(atob(b64||''), function(c){return c.charCodeAt(0);}); }
            catch(e){ bytes = new Uint8Array(); }
            var resp = new Response(bytes, {status: code||200, headers: {'Content-Type': type||'text/plain'}});
            p.resolve(resp);
          };
          window.__bleReject = function(id, msg){
            var p = window.__blePending[id]; if(!p) return; delete window.__blePending[id];
            p.reject(new Error(msg||'BLE error'));
          };
          var nf = window.fetch;
          window.fetch = function(input, init){
            init = init || {};
            var url = (typeof input === 'string') ? input : (input && input.url) || '';
            var method = (init.method || 'GET').toUpperCase();
            var headers = {};
            try { new Headers(init.headers||{}).forEach(function(v,k){ headers[k]=v; }); } catch(e){}
            var body = '';
            if (init.body != null) body = (typeof init.body === 'string') ? init.body : String(init.body);
            var id = ++window.__bleSeq;
            return new Promise(function(resolve, reject){
              window.__blePending[id] = {resolve:resolve, reject:reject};
              try { AndroidBle.request(id, method, url, JSON.stringify(headers), body); }
              catch(e){ reject(e); }
            });
          };
          // Classic <form> submit → fetch (WebView drops POST bodies otherwise).
          // Bubble phase + defaultPrevented check: a page that handles its own
          // submit calls preventDefault and the shim steps aside — otherwise it
          // document.writes a raw JSON reply over the page (the black screen).
          document.addEventListener('submit', function(ev){
            var f = ev.target; if(!(f instanceof HTMLFormElement)) return;
            if (ev.defaultPrevented) return;
            ev.preventDefault();
            var method=(f.method||'GET').toUpperCase();
            var action=f.getAttribute('action')||location.pathname;
            var data=new URLSearchParams(new FormData(f)).toString();
            if(method==='GET'){ location.href=action+(data?('?'+data):''); return; }
            fetch(action,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:data})
              .then(function(r){return r.text().then(function(t){document.open();document.write(t);document.close();});})
              .catch(function(e){alert('Send failed: '+e);});
          }, false);
          // Disconnect hook. The web UI posts to iOS via
          // window.webkit.messageHandlers.rxv2.postMessage('disconnect');
          // shim that same object on Android so the page code is unchanged.
          window.rxv2 = window.rxv2 || {};
          window.rxv2.disconnect = function(){ try{ AndroidBle.disconnect(); }catch(e){} };
          if (!window.webkit) window.webkit = {};
          if (!window.webkit.messageHandlers) window.webkit.messageHandlers = {};
          window.webkit.messageHandlers.rxv2 = {
            postMessage: function(m){ if(String(m)==='disconnect') window.rxv2.disconnect(); }
          };
        })();
        """
    }
}
