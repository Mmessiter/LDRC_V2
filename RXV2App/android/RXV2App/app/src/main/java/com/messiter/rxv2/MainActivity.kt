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
    private var debugView: TextView? = null

    // Fake same-origin the WebView believes it is talking to. Every request
    // to this host is intercepted; the network is never actually touched.
    private val ORIGIN = "https://rxv2.local"

    private val permReq = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()
    ) { if (it.values.all { g -> g }) ble.startScan() else showMessage("Bluetooth permission is needed.") }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ble = Rxv2Ble(applicationContext)
        root = FrameLayout(this)
        setContentView(root)

        ble.onState = { st ->
            when (st) {
                is Rxv2Ble.State.Ready -> showWeb()
                is Rxv2Ble.State.Failed -> { showScanner(); showMessage(st.msg) }
                is Rxv2Ble.State.Idle -> showScanner()
                else -> {}
            }
        }
        ble.onFound = { list -> scannerAdapter?.submit(list) }
        ble.onStreamFrame = { line -> injectStream(line) }
        ble.onDebug = { s -> debugView?.text = "BLE: $s" }

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
        else if (w != null) ble.disconnect()   // Ready → back = disconnect
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
        root.addView(col)
        startScanIfPermitted()
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
        WebView.setWebContentsDebuggingEnabled(true)
        w.addJavascriptInterface(Bridge(), "AndroidBle")
        w.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, req: WebResourceRequest): WebResourceResponse? {
                android.util.Log.d("RXV2perf", "intercept ${req.method} ${req.url}")
                // Only GET page/asset loads reach here (fetch is bridged in JS).
                if (req.url.host != Uri.parse(ORIGIN).host) return null
                if (req.method.uppercase() != "GET") return null
                val path = req.url.path ?: "/"
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
                return bleSync(req.method, req.url)
            }
        }
        w.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(m: ConsoleMessage): Boolean {
                android.util.Log.d("RXV2web", "${m.messageLevel()} ${m.message()} @${m.lineNumber()}")
                return true
            }
        }
        root.addView(w)
        // On-screen BLE diagnostic strip (bottom) — lets us debug without USB.
        val dbg = TextView(this).apply {
            text = "BLE: —"; textSize = 11f
            setBackgroundColor(0xCC000000.toInt()); setTextColor(0xFF4ADE80.toInt())
            setPadding(16, 6, 16, 6)
        }
        debugView = dbg
        root.addView(dbg, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { gravity = android.view.Gravity.BOTTOM })
        w.loadUrl("$ORIGIN/")
    }

    // Prepend the bridge shim so it runs before any of the page's scripts.
    private fun withShim(html: ByteArray): ByteArray {
        val tag = "<script>$JS_SHIM</script>".toByteArray(Charsets.UTF_8)
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
            android.util.Log.d("RXV2perf", "JS fetch → $method $url")
            val uri = Uri.parse(if (url.startsWith("http")) url else "$ORIGIN$url")
            var pathAndQuery = uri.encodedPath ?: "/"
            if (!uri.encodedQuery.isNullOrEmpty()) pathAndQuery += "?" + uri.encodedQuery
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
        return runCatching {
            assets.open("webroot/$name").use { it.readBytes() } to
                (mime[name.substringAfterLast('.').lowercase()] ?: "application/octet-stream")
        }.getOrNull()
    }

    private fun showMessage(m: String) =
        Toast.makeText(this, m, Toast.LENGTH_LONG).show()

    companion object {
        // Injected into every page: bridge fetch()/forms through AndroidBle,
        // and expose the disconnect hook the page's Bluetooth badge posts to.
        private const val JS_SHIM = """
        (function(){
          if (window.__bleShim) return; window.__bleShim = true;
          console.log('[shim] installing, AndroidBle=' + (typeof AndroidBle));
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
          document.addEventListener('submit', function(ev){
            var f = ev.target; if(!(f instanceof HTMLFormElement)) return;
            ev.preventDefault();
            var method=(f.method||'GET').toUpperCase();
            var action=f.getAttribute('action')||location.pathname;
            var data=new URLSearchParams(new FormData(f)).toString();
            if(method==='GET'){ location.href=action+(data?('?'+data):''); return; }
            fetch(action,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:data})
              .then(function(r){return r.text().then(function(t){document.open();document.write(t);document.close();});})
              .catch(function(e){alert('Send failed: '+e);});
          }, true);
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
