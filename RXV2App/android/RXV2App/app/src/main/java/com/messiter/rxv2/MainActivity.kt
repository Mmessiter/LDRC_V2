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
    private var demoRole = "receiver"    // which demo: receiver | dongle | simif
    private var reviewMode = false   // armchair review of the recorded last session

    // Fake same-origin the WebView believes it is talking to. Every request
    // to this host is intercepted; the network is never actually touched.
    private val ORIGIN = "https://rxv2.local"

    // Where publish_app.sh puts each release (host 301s plain http — keep https).
    private val APP_MANIFEST_URL = "https://www.messiter.com/rxv2app/release/manifest.json"

    // The RECEIVER's public release manifest — fetched by the app on the
    // pages' behalf (/app/manifest): the phone has internet at the field,
    // the Bluetooth-only receiver does not.
    private val RX_MANIFEST_URL = "https://www.messiter.com/rxv2/release/manifest.json"

    // Backup file import (Malcolm 2026-08-30): pick a .json backup, adopt it
    // as the restore point for the CONNECTED model, narrate via
    // /app/backup/import/status.
    @Volatile private var importPhase = "idle"; @Volatile private var importModel = ""; @Volatile private var importCount = 0
    @Volatile private var importMechanics = true   // false = another model's file: servo/mixer items left out
    private var importFor = ""
    private val importPick = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) { importPhase = "idle"; return@registerForActivityResult }
        Thread {
            val text = runCatching { contentResolver.openInputStream(uri)?.use { String(it.readBytes()) } }.getOrNull()
            if (text == null) { importPhase = "failed"; return@Thread }
            val r = SessionCache.importRestore(text, importFor)
            importModel = r.fileModel; importCount = r.count; importMechanics = r.mechanics
            importPhase = if (r.ok) "done" else "failed"
        }.start()
    }
    // Model photos (Malcolm 2026-09-05): long-press a receiver → choose /
    // remove a photograph, shown beside the name so similar names don't muddle.
    private var photoFor: String? = null
    private val photoPick = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.GetContent()) { uri: Uri? ->
        val name = photoFor ?: return@registerForActivityResult
        if (uri != null) { ModelPhotos.save(this, name, uri); scannerAdapter?.notifyDataSetChanged() }
    }
    private val permReq = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()
    ) { if (it.values.all { g -> g }) ble.startScan() else showMessage("Bluetooth permission is needed.") }

    // A backup file opened or shared from another app (Malcolm 2026-09-10):
    // keep it as the restore point for the model named inside it.
    override fun onNewIntent(intent: android.content.Intent) { super.onNewIntent(intent); setIntent(intent); handleImportIntent(intent) }
    override fun onStart() { super.onStart(); intent?.let { handleImportIntent(it) } }
    private fun handleImportIntent(i: android.content.Intent) {
        if (i.getBooleanExtra("ldrc_handled", false)) return
        val uri: android.net.Uri? = when (i.action) {
            android.content.Intent.ACTION_VIEW -> i.data
            android.content.Intent.ACTION_SEND -> @Suppress("DEPRECATION") (i.getParcelableExtra(android.content.Intent.EXTRA_STREAM) as? android.net.Uri)
            else -> null
        } ?: return
        i.putExtra("ldrc_handled", true)
        Thread {
            val text = runCatching { contentResolver.openInputStream(uri!!)?.use { String(it.readBytes()) } }.getOrNull()
            val root = runCatching { JSONObject(text ?: "") }.getOrNull()
            val model = root?.optString("model", "")?.trim() ?: ""
            val msg = if (root == null || root.optString("format") != "rxv2-backup-1" || model.isEmpty()) "That file is not an LDRC backup."
                      else {
                          val r = SessionCache.importRestore(text!!, model)
                          if (r.ok) "Backup for \"$model\" is now on this phone (${r.count} settings). Connect to $model, open Backup & restore, and tap Restore."
                          else "That backup could not be read."
                      }
            runOnUiThread { android.app.AlertDialog.Builder(this).setTitle("Backup file").setMessage(msg).setPositiveButton("OK", null).show() }
        }.start()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        installCrashReporter()
        showLastCrashIfAny()
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
                is Rxv2Ble.State.Ready -> {
                    demoMode = false; reviewMode = false
                    connectedName = st.name
                    showWeb()
                    onConnectedSession(st.name)
                }
                is Rxv2Ble.State.Failed -> { showScanner(); showMessage(st.msg) }
                is Rxv2Ble.State.Idle -> {
                    // The reconnect window after an UNEXPECTED drop has closed:
                    // land on the scanner with auto-connect ARMED, so the moment
                    // the receiver is seen again it connects by itself (0.9.746).
                    // A chosen parting (back / disconnect) still disarms it.
                    if (ble.lastDropUnexpected) { ble.lastDropUnexpected = false; autoDone = false }
                    showScanner()
                }
                else -> {}
            }
        }
        ble.onFound = { list ->
            latestFound = list
            maybeArmAuto()
            scannerAdapter?.submit(list)
            // The demos used to be hidden whenever a receiver was in sight.
            // They have their own page now (2026-09-19), chosen deliberately —
            // hiding them there would empty the page you just asked for.
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

    override fun onPause() {
        super.onPause()
        ble.appInForeground = false
        SessionCache.saveIfDirty()   // recording survives app switches / kills
        pausedAtMs = System.currentTimeMillis()
    }

    // Fresh start after a real absence (Malcolm 2026-08-06: "on reloading
    // the app… usually I want to connect to a different model"): away for
    // over a minute → drop the old link and land on the model list. A quick
    // app-switch (checking a message) keeps the connection.
    private var pausedAtMs = 0L

    override fun onBackPressed() {
        val w = webView
        if (w != null && w.canGoBack()) w.goBack()
        else if (w != null) {
            if (demoMode) { demoMode = false; showScanner() }
            else if (reviewMode) { reviewMode = false; SessionCache.saveIfDirty(); showScanner() }
            else { autoDone = true; ble.disconnect() }   // Ready → back = disconnect (chosen)
        }
        // A sub-page (Connect, Reviews, Backups, Demos) → back to the four
        // doors, not out of the app (2026-09-19).
        else if (homePage == "help") helpBack()
        else if (homePage != "home") showScanner()
        else super.onBackPressed()
    }

    // ── Scanner list ────────────────────────────────────────────────
    private var scannerAdapter: ScannerAdapter? = null
    // Auto-connect to the receiver used last time (Malcolm 2026-08-16):
    // once per arming, cancellable, never after a deliberate disconnect.
    private var autoDone = false
    private var autoPending: Runnable? = null
    private var autoBanner: TextView? = null
    private var latestFound: List<Rxv2Ble.Discovered> = emptyList()

    private fun cancelAuto() {
        autoPending?.let { root.removeCallbacks(it) }
        autoPending = null
        autoBanner?.visibility = View.GONE
    }

    private fun maybeArmAuto() {
        // Instant (Malcolm 2026-08-17: "straight to the front screen without
        // going round the houses"). Choosing another receiver stays easy:
        // back/disconnect returns to the scanner with auto-connect disarmed.
        if (autoDone) return
        val last = getSharedPreferences("scanner", MODE_PRIVATE).getString("last", "") ?: ""
        if (last.isEmpty()) return
        val d = latestFound.firstOrNull { it.name == last } ?: return
        // Never connect by ourselves to something we can already see is too far:
        // it half-connects and everything after is slow (Malcolm 2026-09-12).
        if (Rxv2Ble.tooWeak(d.rssi)) { cancelAuto(); autoDone = true; return }
        // More than one receiver in range: show the list and let the pilot choose
        // (Malcolm 2026-09-11: the app went to the dongle when he wanted Test1).
        // Alone, connect after a one-second look-around so a second receiver that
        // advertises a beat later still gets its say.
        if (latestFound.size > 1) { cancelAuto(); autoDone = true; return }
        if (autoPending != null) return
        val r = Runnable {
            autoPending = null
            if (autoDone) return@Runnable
            if (latestFound.size > 1) { autoDone = true; return@Runnable }
            val now = latestFound.firstOrNull { it.name == last } ?: return@Runnable
            if (Rxv2Ble.tooWeak(now.rssi)) { cancelAuto(); autoDone = true; return@Runnable }
            autoDone = true
            autoBanner?.visibility = View.GONE
            ble.connect(now)
        }
        autoPending = r
        root.postDelayed(r, 1000)
    }

    // Friendly "when" for saved reviews (Malcolm 2026-08-22): Today/Yesterday
    // keep just the time, older ones gain a short date.
    private fun friendlyWhen(ms: Long): String {
        val time = android.text.format.DateFormat.format("HH:mm", ms).toString()
        val now = java.util.Calendar.getInstance()
        val then = java.util.Calendar.getInstance().apply { timeInMillis = ms }
        fun sameDay(a: java.util.Calendar, b: java.util.Calendar) =
            a.get(java.util.Calendar.YEAR) == b.get(java.util.Calendar.YEAR) &&
            a.get(java.util.Calendar.DAY_OF_YEAR) == b.get(java.util.Calendar.DAY_OF_YEAR)
        if (sameDay(now, then)) return "Today $time"
        now.add(java.util.Calendar.DAY_OF_YEAR, -1)
        if (sameDay(now, then)) return "Yesterday $time"
        return android.text.format.DateFormat.format("d MMM, HH:mm", ms).toString()
    }

    // The web pages' ink colours, used explicitly on the scanner so it reads
    // the same whatever the phone's dark-mode setting (2026-09-19).
    private val INK = 0xFF22384B.toInt()
    private val SUB = 0xFF3A5165.toInt()

    // ── The front door ──────────────────────────────────────────────
    // Four doors instead of one crowded list (Malcolm 2026-09-19): Connect,
    // Reviews, Backups, Demos — each a button in the app's usual style, each
    // its own page. Scanning still runs on the home page, so the model used
    // last still connects by itself without going round the houses.
    private var homePage = "home"

    /** The flying-field backdrop every web page uses, under a wash. */
    private fun backdrop() {
        runCatching {
            val bmp = assets.open("webroot/flying-field.jpg").use { android.graphics.BitmapFactory.decodeStream(it) }
            // FULL COLOUR (Malcolm 2026-09-19) — the text that sits on it has
            // its own solid chip, exactly as the web pages do.
            root.background = android.graphics.drawable.BitmapDrawable(resources, bmp)
                .apply { gravity = android.view.Gravity.FILL }
        }
    }

    /** Title bar: a back chevron on the sub-pages, the title, and the "?". */
    private fun pageHeader(col: LinearLayout, title: String, back: Boolean,
                           withHelp: Boolean = true, onBack: (() -> Unit)? = null) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = android.view.Gravity.CENTER_VERTICAL
            setPadding(40, 60, 40, 8)
        }
        if (back) row.addView(roundButton("\u2039", 38f) { if (onBack != null) onBack() else showScanner() })
        row.addView(TextView(this).apply {
            text = ""; textSize = 22f
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        if (withHelp) row.addView(roundButton("?") { showScannerHelp() })
        col.addView(row)
        if (title.isNotEmpty()) col.addView(TextView(this).apply {
            text = title
            textSize = 25f; setTextColor(INK)
            letterSpacing = 0.08f
            gravity = android.view.Gravity.CENTER
            setPadding(36, 26, 36, 26)
            background = android.graphics.drawable.GradientDrawable().apply {
                cornerRadius = 30f; setColor(0xFFF2F6F8.toInt())
            }
            elevation = 4f
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                     ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 4, 40, 18) })
    }

    /** A round button on a SOLID white disc — never a bare glyph on the
     *  photograph, where it cannot be read. */
    private fun roundButton(glyph: String, size: Float = 22f, go: () -> Unit): TextView = TextView(this).apply {
        text = glyph
        textSize = size; setTextColor(0xFF2F6FB0.toInt())
        setTypeface(typeface, android.graphics.Typeface.BOLD)
        gravity = android.view.Gravity.CENTER
        width = 108; height = 108
        background = android.graphics.drawable.GradientDrawable().apply {
            shape = android.graphics.drawable.GradientDrawable.OVAL
            setColor(0xFFFFFFFF.toInt()); setStroke(2, 0xFFC9D3DC.toInt())
        }
        elevation = 3f
        setOnClickListener { go() }
    }

    /** Standalone words sit on a solid chip, never straight on the photograph. */
    private fun chip(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 13f; setTextColor(SUB); setPadding(34, 22, 34, 22)
        setLineSpacing(5f, 1.0f)
        background = android.graphics.drawable.GradientDrawable().apply {
            cornerRadius = 20f; setColor(0xFFF2F6F8.toInt())
        }
    }

    /** A big coloured button in the app's usual style. */
    private fun homeTile(col: LinearLayout, icon: String, colour: Int,
                         title: String, go: () -> Unit) {
        col.addView(TextView(this).apply {
            text = "$icon   $title"
            textSize = 19f; setTextColor(0xFFFFFFFF.toInt())
            setPadding(48, 42, 48, 42)
            background = android.graphics.drawable.GradientDrawable().apply {
                cornerRadius = 28f; setColor(colour)
            }
            setOnClickListener { go() }
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                     ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            setMargins(40, 10, 40, 10)
        })
    }

    /** HOME — the four doors. Kept as showScanner() so every existing
     *  "back to the list" path still lands here. */
    private fun showScanner() {
        webView?.let { it.stopLoading(); it.destroy() }; webView = null
        homePage = "home"
        root.removeAllViews()
        backdrop()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        pageHeader(col, "", back = false)
        // The masthead: it is the first thing anyone sees, so it carries more
        // weight than a page heading (Malcolm 2026-09-19).
        val masthead = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setPadding(36, 44, 36, 40)
            background = android.graphics.drawable.GradientDrawable().apply {
                cornerRadius = 40f; setColor(0xFFF2F6F8.toInt())
            }
            elevation = 6f
        }
        masthead.addView(TextView(this).apply {
            text = "LockDown Radio Control"
            textSize = 27f; setTextColor(INK)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            gravity = android.view.Gravity.CENTER
        })
        masthead.addView(TextView(this).apply {
            text = "RXV2"
            textSize = 14f; setTextColor(0xFF5FA099.toInt())
            letterSpacing = 0.5f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
            gravity = android.view.Gravity.CENTER
            setPadding(0, 14, 0, 0)
        })
        col.addView(masthead, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                     ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 0, 40, 22) })
        autoBanner = TextView(this).apply {
            visibility = View.GONE
            textSize = 14f; setPadding(40, 24, 40, 24)
            setBackgroundColor(0xFF3B2F14.toInt()); setTextColor(0xFFFFD966.toInt())
        }
        col.addView(autoBanner)

        SessionCache.init(this)
        homeTile(col, "🔌", 0xFF6CAB5E.toInt(), "Connect") { showConnect() }
        homeTile(col, "🕰", 0xFF4A90C9.toInt(), "Reviews") { showReviews() }
        homeTile(col, "💾", 0xFFC98A4A.toInt(), "Backups") { showBackups() }
        homeTile(col, "🎭", 0xFF6C8EB0.toInt(), "Demos")   { showDemos() }

        root.addView(col)
        // No searching here: the hunt — and the leap to the model used last —
        // begins only when Connect is tapped (Malcolm 2026-09-19).
        ble.stopScan()
        checkAppUpdate(col)
    }

    /** CONNECT — the live search that used to be the whole first screen. */
    private fun showConnect() {
        homePage = "connect"
        root.removeAllViews()
        backdrop()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        pageHeader(col, "Connect", back = true)
        val list = ListView(this).apply { divider = null; dividerHeight = 0 }
        scannerAdapter = ScannerAdapter()
        list.adapter = scannerAdapter
        list.setOnItemClickListener { _, _, pos, _ ->
            cancelAuto(); autoDone = true
            val d = scannerAdapter!!.item(pos)
            // Do not start a connection the signal says will fail; RSSI wanders,
            // so ask rather than forbid (Malcolm 2026-09-12).
            if (Rxv2Ble.tooWeak(d.rssi)) {
                android.app.AlertDialog.Builder(this)
                    .setTitle("Too far away")
                    .setMessage("${d.name} is only ${d.rssi} dBm — too weak to connect reliably. Walk closer to the model and it will connect at once.")
                    .setNegativeButton("Cancel", null)
                    .setPositiveButton("Try anyway") { _, _ ->
                        getSharedPreferences("scanner", MODE_PRIVATE).edit().putString("last", d.name).apply()
                        ble.connect(d)
                    }.show()
            } else {
                getSharedPreferences("scanner", MODE_PRIVATE).edit().putString("last", d.name).apply()
                ble.connect(d)
            }
        }
        list.setOnItemLongClickListener { _, _, pos, _ ->
            val d = scannerAdapter!!.item(pos)
            val has = ModelPhotos.file(this, d.name).exists()
            val items = if (has) arrayOf("Choose photo…", "Remove photo") else arrayOf("Choose photo…")
            android.app.AlertDialog.Builder(this)
                .setTitle(d.name)
                .setItems(items) { _, which ->
                    if (which == 0) { photoFor = d.name; photoPick.launch("image/*") }
                    else { ModelPhotos.remove(this, d.name); scannerAdapter?.notifyDataSetChanged() }
                }.show()
            true
        }
        col.addView(list, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        root.addView(col)
        startScanIfPermitted()
        scannerAdapter?.submit(latestFound)   // whatever is already in sight
    }

    /** REVIEWS — one recording per model, made automatically at every connection. */
    private fun showReviews() {
        homePage = "reviews"
        root.removeAllViews()
        backdrop()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        pageHeader(col, "Reviews", back = true)
        SessionCache.init(this)
        val sessions = SessionCache.savedSessions()
        if (sessions.isEmpty()) col.addView(
            chip("Nothing recorded yet. Connect to a model and one is kept for you."),
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                      ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 8, 40, 28) })
        for ((model, atMs) in sessions) {
            val t = if (atMs > 0) "\nLast session · " + friendlyWhen(atMs) else ""
            col.addView(TextView(this).apply {
                text = "🕰  $model$t"
                textSize = 15f; setPadding(40, 28, 40, 28)
                setBackgroundColor(0xFF14532D.toInt()); setTextColor(0xFF86EFAC.toInt())
                ModelPhotos.load(this@MainActivity, model, 96)?.let {
                    setCompoundDrawablesWithIntrinsicBounds(android.graphics.drawable.BitmapDrawable(resources, it), null, null, null)
                    compoundDrawablePadding = 24
                }
                setOnClickListener {
                    SessionCache.activate(model)
                    reviewMode = true; showWeb()
                }
                // Long-press to delete an old review. Confirm first — these
                // hold flight recordings.
                setOnLongClickListener {
                    android.app.AlertDialog.Builder(this@MainActivity)
                        .setTitle("Delete review?")
                        .setMessage("Remove the saved recording for \"$model\"?")
                        .setPositiveButton("Delete") { _, _ ->
                            SessionCache.deleteSession(model); showReviews()
                        }
                        .setNegativeButton("Cancel", null)
                        .show()
                    true
                }
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                         ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 8, 40, 8) })
        }
        root.addView(ScrollView(this).apply { addView(col) })
    }

    /** BACKUPS — what this phone has saved for each model, and when. */
    private fun showBackups() {
        homePage = "backups"
        root.removeAllViews()
        backdrop()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        pageHeader(col, "Backups", back = true)
        SessionCache.init(this)
        val backups = SessionCache.savedBackups()
        if (backups.isEmpty()) col.addView(
            chip("No backups yet. Open a model, go to Rotorflight → Backup & restore, and tap Back up."),
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                      ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 8, 40, 28) })
        for (b in backups) {
            // "Kept automatically" is the ordinary case and needs no label;
            // only a deliberate backup is worth marking. "What's in it" is a
            // pill so it LOOKS like the button it is (Malcolm 2026-09-19).
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(40, 28, 40, 28)
                setBackgroundColor(0xFF3B2F14.toInt())
                setOnClickListener { showBackupContents(b) }
            }
            card.addView(TextView(this).apply {
                text = "💾  ${b.model}"
                textSize = 16f; setTextColor(0xFFFFD966.toInt())
                ModelPhotos.load(this@MainActivity, b.model, 96)?.let {
                    setCompoundDrawablesWithIntrinsicBounds(android.graphics.drawable.BitmapDrawable(resources, it), null, null, null)
                    compoundDrawablePadding = 24
                }
            })
            card.addView(TextView(this).apply {
                text = (if (b.explicit) "Your backup \u00b7 " else "Automatic \u00b7 ") + friendlyWhen(b.atMs)
                textSize = 12f; setTextColor(0xFFC9B27A.toInt())
                setPadding(0, 8, 0, 12)
            })
            card.addView(TextView(this).apply {
                text = "\uD83D\uDCCB  What\u2019s in it \u2014 ${b.items} settings"
                textSize = 14f; setTextColor(0xFF0E2E08.toInt())
                setTypeface(typeface, android.graphics.Typeface.BOLD)
                setPadding(28, 14, 28, 14)
                background = android.graphics.drawable.GradientDrawable().apply {
                    cornerRadius = 40f; setColor(0xFFFFD966.toInt())
                }
                setOnClickListener { showBackupContents(b) }
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                                         ViewGroup.LayoutParams.WRAP_CONTENT))
            col.addView(card, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                         ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 8, 40, 8) })
        }
        root.addView(ScrollView(this).apply { addView(col) })
    }

    /** WHAT'S IN THE BACKUP — the plain lines, for a backup this phone holds. */
    private fun showBackupContents(b: SessionCache.BackupInfo) {
        val lines = SessionCache.backupSummary(b.model, b.explicit)
        val head = b.model + " \u2014 " + (if (b.explicit) "your backup" else "automatic, taken when you connected") +
                   " \u00b7 " + friendlyWhen(b.atMs) + "\n\n"
        val body = if (lines.isEmpty()) "Nothing readable in this backup yet."
                   else lines.joinToString("\n") + "\n\n" +
                        (if (b.explicit) "This one is yours: the app never overwrites it. "
                         else "This copy is refreshed every time you connect. ") +
                        "Rotorflight settings only \u2014 no flight data. Connect to the model and " +
                        "use Backup & restore to put it back."
        android.app.AlertDialog.Builder(this)
            .setTitle("What\u2019s in the backup")
            .setMessage(head + body)
            .setPositiveButton("Done", null)
            .show()
    }

    /** DEMOS — one board, three jobs (Malcolm 2026-09-19). */
    private fun showDemos() {
        homePage = "demos"
        root.removeAllViews()
        backdrop()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        pageHeader(col, "Demos", back = true)
        homeTile(col, "✈️", 0xFF6CAB5E.toInt(), "Receiver") { demoRole = "receiver"; demoMode = true; showWeb() }
        homeTile(col, "🔌", 0xFF5FA099.toInt(), "Rotorflight dongle") { demoRole = "dongle"; demoMode = true; showWeb() }
        homeTile(col, "🎮", 0xFF6C8EB0.toInt(), "Simulator interface") { demoRole = "simif"; demoMode = true; showWeb() }
        root.addView(col)
    }

    private var helpReturn = "home"
    private fun helpBack() {
        when (helpReturn) {
            "connect" -> showConnect()
            "reviews" -> showReviews()
            "backups" -> showBackups()
            "demos"   -> showDemos()
            else      -> showScanner()
        }
    }

    private fun showScannerHelp() {
        val forPage = if (homePage == "help") helpReturn else homePage
        val heading = when (forPage) {
            "connect" -> "About Connect"
            "reviews" -> "About Reviews"
            "backups" -> "About Backups"
            "demos"   -> "About the demos"
            else      -> "About this app"
        }
        val html = when (forPage) {
            "connect" -> """
                <p>Find a LockDown receiver or dongle over Bluetooth and open its pages.</p>
                <p><b>Getting a model to appear</b><br>
                Power the model with the transmitter OFF, so the board&#39;s own config radios come
                up &mdash; the same rule as the WiFi portal. A dongle has no transmitter of its own,
                so just power the model it is plugged into. Bring the phone within a few metres.</p>
                <p><b>Signal strength</b><br>
                Each row says how strong the signal is. Below about &minus;85&nbsp;dBm a connection
                half-forms and everything afterwards is slow, so the app asks before trying.</p>
                <p><b>The model you used last</b><br>
                It connects by itself when it is the only board in range; with more than one in
                range the list waits for you to choose.</p>
                <p><b>Photographs</b><br>
                Press and hold any row to give that board a photograph of its model.</p>
            """
            "reviews" -> """
                <p>A recording of a model&#39;s last connection, kept for you automatically.</p>
                <p><b>What a review holds</b><br>
                The flights and the black box, and every Rotorflight setting as it was at that
                connection &mdash; enough to sit indoors and go through a model with everything
                switched off.</p>
                <p><b>One per model</b><br>
                Connecting a different model never erases another&#39;s. Press and hold to delete one.</p>
                <p><b>The safety net</b><br>
                A review can also put a model&#39;s tuning back &mdash; what saves the day when no
                backup was ever made.</p>
                <p><b>Not a backup</b><br>
                A backup is one you make on purpose, holds the settings only, and is what to take
                before changing anything. A review is a record of what happened.</p>
            """
            "backups" -> """
                <p>The Rotorflight settings this phone has saved for each model.</p>
                <p><b>What a backup is</b><br>
                Every setting the model had when you tapped Back up: PIDs, rates, governor,
                servos, the lot. No flight data.</p>
                <p><b>Where it lives</b><br>
                Here, on the phone &mdash; one per model, so it survives anything that happens to
                the model. You can also send one to yourself as a file and open it again later.</p>
                <p><b>Making one</b><br>
                Connect to the model, open Rotorflight &rarr; Backup &amp; restore, and tap Back up.
                Do it before you change anything.</p>
                <p><b>Putting it back</b><br>
                On the same page, transmitter off and blades off. Each setting is written and read
                back to check it landed.</p>
                <p><b>Two kinds, both kept</b><br>
                &ldquo;Your backup&rdquo; is one you asked for, and nothing ever overwrites it &mdash;
                only another Back up replaces it. &ldquo;Automatic&rdquo; is the copy the app takes by
                itself each time you connect with the transmitter off. Both are kept side by side,
                and Backup &amp; restore offers each by name and date.</p>

                <p><b>What the automatic copy is for</b><br>
                It holds the settings as they were WHEN YOU CONNECTED, before anything you changed
                in this session &mdash; so it undoes an afternoon&rsquo;s experimenting. It is not an
                archive: next time you connect it is taken again, and then it holds your changes
                too. A change that restarts the receiver (protocol, name, WiFi) refreshes it on the
                spot, so that undo is gone. Anything you want to keep beyond today belongs in your
                own backup.</p>

                <p><b>Never while you fly</b><br>
                Arming takes the receiver&rsquo;s Bluetooth down, so nothing can be read in the air at
                all. A backup also refuses to start if the transmitter is on, and stops at once if
                it comes on part way through &mdash; a half-read sweep is never kept.</p>
            """
            "demos" -> """
                <p>The whole app on canned data &mdash; every page, nothing connected.</p>
                <p><b>One board, three jobs</b><br>
                Every demo here is the same little XIAO ESP32-S3 running the same firmware. What it
                does depends only on what is fitted to it and which role you choose in its
                settings &mdash; not on buying a different product.</p>
                <p><b>Receiver</b><br>
                With transceivers fitted it flies the model: it takes your transmitter&#39;s signal
                and drives the flight controller, records the flight, and gives you every
                Rotorflight page from your phone.</p>
                <p><b>Rotorflight dongle</b><br>
                The same board with no transceivers, plugged into a flight controller. Your own
                radio and receiver still fly the model; the dongle just gives the app to any
                Rotorflight helicopter.</p>
                <p><b>Simulator interface</b><br>
                The same bare board again, with a receiver wired to it, turning that receiver into
                a USB joystick for RealFlight or neXt. It works out for itself whether the receiver
                speaks CRSF, SBUS, IBUS or PPM.</p>
                <p><b>And a receiver does all three</b><br>
                A LockDown receiver needs no dongle for the app, and flies a simulator on its own
                over USB. The other two roles are for spare boards, and for people flying someone
                else&#39;s radio.</p>
            """
            else -> """
                <p>Four doors: Connect to a model, browse a Review of an earlier session, see the
                Backups this phone holds, or try a Demo with no hardware at all.</p>
                <p><b>Connect</b><br>
                Searches for receivers and dongles nearby and opens the one you choose. The model
                you used last connects by itself once you are in there, if it is alone in range.</p>
                <p><b>Reviews</b><br>
                One recording per model, made at every connection: the flights and the settings as
                they were, to go through indoors with everything switched off.</p>
                <p><b>Backups</b><br>
                What this phone has saved for each model, and when &mdash; settings you can put
                back if a change goes wrong.</p>
                <p><b>Demos</b><br>
                The same pages driven by canned data: a receiver in a model, a Rotorflight dongle,
                or a simulator interface. Nothing to buy first.</p>
                <p><b>No phone needed at all</b><br>
                Everything here is also in the receiver&#39;s own WiFi pages, in any web browser.
                The app simply carries the same pages over Bluetooth, so there is no network to
                switch at the field.</p>
            """
        }.trimIndent()

        if (homePage != "help") helpReturn = homePage
        homePage = "help"
        root.removeAllViews()
        backdrop()
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        pageHeader(col, heading, back = true, withHelp = false) { helpBack() }
        val body = TextView(this).apply {
            text = android.text.Html.fromHtml(html, android.text.Html.FROM_HTML_MODE_COMPACT)
            textSize = 14f; setPadding(36, 28, 36, 28); setTextColor(INK)
            setLineSpacing(6f, 1.0f)
            background = android.graphics.drawable.GradientDrawable().apply {
                cornerRadius = 24f; setColor(0xFFF2F6F8.toInt())
            }
        }
        col.addView(body, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                                    ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 0, 40, 20) })
        if (forPage == "home") col.addView(chip("App version " +
            packageManager.getPackageInfo(packageName, 0).versionName),
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                                      ViewGroup.LayoutParams.WRAP_CONTENT).apply { setMargins(40, 0, 40, 36) })
        root.addView(ScrollView(this).apply { addView(col) })
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

    @Volatile private var appUpdateDialogUp = false

    private fun checkAppUpdate(col: LinearLayout) {
        // every visit to the scanner re-checks (a backgrounded app can sit in
        // recents for days — a once-per-launch gate never fired again);
        // lightly throttled so back-and-forth doesn't hammer the server
        if (System.currentTimeMillis() - lastUpdateCheck < 60_000) return
        lastUpdateCheck = System.currentTimeMillis()
        // "Pending" from the moment the CHECK starts, not only once the dialog
        // is up: the page's firmware offer asks /app/update-pending within a
        // second of connecting, which is exactly while this fetch is still in
        // flight - it read "nothing pending", showed its offer, and then this
        // dialog landed on top of it. Cleared when the check finds nothing,
        // fails, or the dialog is dismissed.
        appUpdateDialogUp = true
        Thread {
            var stillPending = false
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
                if (newest > installed) { stillPending = true; runOnUiThread {
                    // The banner on the scanner is fine when the scanner is
                    // still there - but instant auto-connect leaves it within
                    // a second, and this reply usually lands AFTER that, when
                    // it used to be thrown away (Malcolm 2026-09-17: "went
                    // straight past the page that offered the update before I
                    // could hit update"). So: banner if the scanner is up,
                    // and ALWAYS a dialog, which outlives the page. "Later" is
                    // remembered per version so it does not nag every minute.
                    if (col.parent != null) col.addView(TextView(this).apply {
                        text = "⬆️  App update available: v$name — tap to install"
                        textSize = 15f; setPadding(40, 28, 40, 28)
                        setBackgroundColor(0xFFFFD278.toInt()); setTextColor(0xFF5C3A00.toInt())
                        setOnClickListener { installUpdate(url, name) }
                    }, 0)
                    val sp = getSharedPreferences("appupdate", MODE_PRIVATE)
                    if (sp.getInt("later", 0) == newest || isFinishing) { appUpdateDialogUp = false; return@runOnUiThread }
                    // While this is up the page holds its own firmware offer
                    // (it asks /app/update-pending) - Malcolm 2026-09-17 got
                    // both on one screen. App first: it restarts the app, and
                    // the firmware offer comes back on reconnect.
                    stillPending = true
                    android.app.AlertDialog.Builder(this)
                        .setTitle("App update available")
                        .setMessage("RXV2 app v$name is out. Install it now?")
                        .setPositiveButton("Update") { _, _ -> installUpdate(url, name) }
                        .setNegativeButton("Later") { _, _ -> sp.edit().putInt("later", newest).apply() }
                        .setOnDismissListener { appUpdateDialogUp = false }
                        .show()
                } }
            }
            if (!stillPending) appUpdateDialogUp = false   // no update, or the check failed
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
        ble.appInForeground = true
        // Away >1 min with a live/reconnecting link → fresh start on the
        // model list (demo and armchair review are deliberate — left alone).
        if (pausedAtMs > 0 && System.currentTimeMillis() - pausedAtMs > 60_000 &&
            webView != null && !demoMode && !reviewMode) {
            autoDone = false   // idle timeout is not a chosen parting — re-arm auto
            ble.disconnect()   // state callback lands us on the scanner
        }
        pausedAtMs = 0
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
        if (perms.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }) {
            ble.startScan()
            // Instant path: go straight for the remembered receiver by MAC.
            // The scan keeps running underneath, so if this device is off the
            // list still fills and a manual choice (or discovery auto-connect
            // for the same name) takes over.
            if (!autoDone) {
                val sp = getSharedPreferences("scanner", MODE_PRIVATE)
                val last = sp.getString("last", "") ?: ""
                val addr = sp.getString("lastAddr", "") ?: ""
                if (last.isNotEmpty() && addr.isNotEmpty() && ble.fastConnect(last, addr)) {
                    autoDone = true
                }
            }
        }
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
                orientation = LinearLayout.HORIZONTAL; setPadding(40, 28, 40, 28)
                gravity = android.view.Gravity.CENTER_VERTICAL
                // A solid card on the backdrop, never translucent (2026-09-19).
                setBackgroundColor(0xFFF2F6F8.toInt())
            }
            v.removeAllViews()
            val d = items[i]
            val photo = ModelPhotos.load(this@MainActivity, d.name, 160)
            v.addView(ImageView(this@MainActivity).apply {
                if (photo != null) { setImageBitmap(photo); scaleType = ImageView.ScaleType.CENTER_CROP }
                else setImageResource(android.R.drawable.stat_sys_data_bluetooth)
            }, LinearLayout.LayoutParams(160, 160).apply { rightMargin = 28 })
            val texts = LinearLayout(this@MainActivity).apply { orientation = LinearLayout.VERTICAL }
            texts.addView(TextView(this@MainActivity).apply { text = d.name; textSize = 17f; setTextColor(INK) })
            texts.addView(TextView(this@MainActivity).apply {
                text = Rxv2Ble.signalWord(d.rssi) + " — ${d.rssi} dBm" +
                       (if (Rxv2Ble.tooWeak(d.rssi)) " — get closer" else "")
                setTextColor(if (Rxv2Ble.tooWeak(d.rssi)) 0xFFC0603C.toInt() else SUB)
                textSize = 12f
            })
            v.addView(texts, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
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
    @Volatile private var otaConfirmed = true   // false with "done" = never reappeared over Bluetooth (firmware.html goes back to the list, 5.93)

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
        if (begin.code != 200) throw Exception("refused: " + String(begin.body))   // the receiver's own sentence; final (no retry)
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
        // Foreground service + screen awake for the whole install (2026-09-18,
        // Malcolm: "screen timeout or checking emails etc during update" must
        // not matter). The service keeps the process alive and the link up
        // while the screen is locked or another app is in front; the flag
        // stops the screen locking in the first place. Both undone in finally.
        runOnUiThread {
            runCatching { OtaService.start(this) }
            window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                runCatching { requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 77) }   // so the "update in progress" notice can show; the service runs either way
        }
        try {
            otaPhase = "download"; otaMsg = "Downloading with the phone's internet…"; otaSent = 0; otaTotal = 0
            val fw = httpDownload(fwUrl)
            var fs = fsUrl?.takeIf { it.isNotBlank() }?.let { runCatching { httpDownload(it) }.getOrNull() }
            // Older on-receiver pages omit &fs= — derive the pages image from
            // the release-directory convention so web pages always ship too.
            if (fs == null && fwUrl.endsWith("firmware.bin"))
                fs = runCatching { httpDownload(fwUrl.removeSuffix("firmware.bin") + "littlefs.bin") }.getOrNull()
            // Fingerprint skip (2026-07-31): identical pages image already on
            // the receiver (info.fs_md5) → don't rewrite the filesystem; the
            // 20 saved flights + Rotorflight backups stay untouched.
            if (fs != null) runCatching {
                val st = org.json.JSONObject(String(bleReqSync("GET", "/api/state.json").body))
                val have = st.optJSONObject("info")?.optString("fs_md5") ?: ""
                if (have.length == 32) {
                    val md = java.security.MessageDigest.getInstance("MD5").digest(fs)
                    val mine = md.joinToString("") { "%02x".format(it) }
                    if (mine == have.lowercase()) {
                        fs = null
                        otaMsg = "Web pages unchanged — keeping flights…"
                    }
                }
            }
            otaTotal = fw.size.toLong() + (fs?.size ?: 0).toLong()
            // one clean restart per image: /begin resets the receiver side,
            // so a transfer that died mid-way gets a second, fresh attempt
            val sendImage = { type: String, bytes: ByteArray, base: Long, label: String ->
                try { streamImage(type, bytes, base) } catch (e: Exception) {
                    val m = e.message ?: ""
                    if (m.contains("too old") || m.startsWith("refused:")) throw e   // a refusal is final: no retry
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
            // flag) and Rxv2Ble auto-reconnects for 240 s (the window stamped
            // at /app/bleota/start) — poll until it answers, then report the
            // version it now runs. Was 120 s against a 90 s window (5.93).
            Thread.sleep(4000)
            var newVer = ""
            val deadline = System.currentTimeMillis() + 240_000
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
            otaConfirmed = newVer.isNotEmpty()
            otaPhase = "done"
            otaMsg = if (newVer.isEmpty())
                "installed; the receiver didn't reappear on Bluetooth to confirm — reopen the app to check it"
            else "now running $newVer"
        } catch (e: Throwable) {
            // Throwable, not Exception (0.9.746): an OutOfMemoryError on this
            // bare thread had no handler at all and killed the app.
            otaPhase = "error"
            otaMsg = if (e is OutOfMemoryError) "the phone ran out of memory - close other apps and try again"
                     else (e.message ?: e.javaClass.simpleName)
            runCatching { bleReqSync("POST", "/api/bleota/status") }
        } finally {
            runOnUiThread {
                runCatching { OtaService.stop(this) }
                window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
        }
    }


    // ---- Crash reporter (0.9.746) ----------------------------------------
    // Malcolm 2026-09-17: "the app crashed" on the update screen, and there
    // was nothing to read afterwards - no logcat without a cable. Every
    // uncaught throw is now written to a file first, and shown on the next
    // launch with a Copy button so the trace can be pasted straight into a
    // message. The default handler still runs, so Android's own behaviour is
    // unchanged.
    private fun crashFile() = java.io.File(filesDir, "last-crash.txt")

    private fun installCrashReporter() {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            runCatching {
                val sw = java.io.StringWriter()
                e.printStackTrace(java.io.PrintWriter(sw))
                val ver = runCatching { packageManager.getPackageInfo(packageName, 0).versionName }.getOrNull() ?: "?"
                crashFile().writeText(
                    "RXV2App $ver on Android ${Build.VERSION.RELEASE} (${Build.MODEL})\n" +
                    "thread ${t.name} at ${java.util.Date()}\n\n" + sw.toString())
            }
            previous?.uncaughtException(t, e)
        }
    }

    private fun showLastCrashIfAny() {
        val f = crashFile()
        if (!f.exists()) return
        val text = runCatching { f.readText() }.getOrNull() ?: return
        f.delete()
        val shown = if (text.length > 2500) text.substring(0, 2500) + "\n..." else text
        android.app.AlertDialog.Builder(this)
            .setTitle("The app crashed last time")
            .setMessage("This is what went wrong. Copy it and send it to Claude.\n\n" + shown)
            .setPositiveButton("Copy") { _, _ ->
                val cm = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
                cm.setPrimaryClip(android.content.ClipData.newPlainText("RXV2 crash", text))
            }
            .setNegativeButton("Dismiss", null)
            .show()
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
        // Pages use a few plain alert()/confirm()/prompt() calls (Setup's
        // rename, refusals). A WebView shows NONE of them without a
        // WebChromeClient: the rename button did nothing and refusals were
        // swallowed silently (2026-09-16 review). iOS implements all three.
        w.webChromeClient = object : android.webkit.WebChromeClient() {
            override fun onJsAlert(v: WebView?, url: String?, msg: String?, r: android.webkit.JsResult?): Boolean {
                android.app.AlertDialog.Builder(this@MainActivity).setMessage(msg ?: "")
                    .setPositiveButton("OK") { _, _ -> r?.confirm() }
                    .setOnCancelListener { r?.cancel() }.show()
                return true
            }
            override fun onJsConfirm(v: WebView?, url: String?, msg: String?, r: android.webkit.JsResult?): Boolean {
                android.app.AlertDialog.Builder(this@MainActivity).setMessage(msg ?: "")
                    .setPositiveButton("OK") { _, _ -> r?.confirm() }
                    .setNegativeButton("Cancel") { _, _ -> r?.cancel() }
                    .setOnCancelListener { r?.cancel() }.show()
                return true
            }
            override fun onJsPrompt(v: WebView?, url: String?, msg: String?, def: String?, r: android.webkit.JsPromptResult?): Boolean {
                val box = android.widget.EditText(this@MainActivity).apply { setText(def ?: ""); setSelectAllOnFocus(true) }
                android.app.AlertDialog.Builder(this@MainActivity).setMessage(msg ?: "").setView(box)
                    .setPositiveButton("OK") { _, _ -> r?.confirm(box.text.toString()) }
                    .setNegativeButton("Cancel") { _, _ -> r?.cancel() }
                    .setOnCancelListener { r?.cancel() }.show()
                return true
            }
        }
        w.webViewClient = object : WebViewClient() {
            // A crashed WebView renderer otherwise leaves a dead BLACK screen
            // until the app is force-quit (seen on the Fold saving settings,
            // 2026-07-23). Recreate the WebView and reload the front page.
            override fun onRenderProcessGone(view: WebView, detail: android.webkit.RenderProcessGoneDetail): Boolean {
                // Never touch the dead WebView from inside its own callback
                // (0.9.746). This ran runOnUiThread { view.destroy() } - but
                // this callback IS on the UI thread, so that ran synchronously,
                // re-entrantly, inside the framework's own call: Android
                // documents that as a crash, and a renderer death (memory
                // pressure, a WebView bug) then took the whole app with it
                // instead of the page quietly reloading. Detach and rebuild on
                // the next main-loop pass.
                webView = null
                root.post {
                    runCatching { (view.parent as? android.view.ViewGroup)?.removeView(view) }
                    runCatching { view.destroy() }
                    runCatching { showWeb() }
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
                if (path == "/app/update-pending")
                    return jsonResp("{\"pending\":$appUpdateDialogUp}")
                if (path == "/app/bleota/progress") {
                    val j = org.json.JSONObject()
                    j.put("phase", otaPhase); j.put("msg", otaMsg)
                    j.put("sent", otaSent); j.put("total", otaTotal); j.put("confirmed", otaConfirmed)
                    return jsonResp(j.toString())
                }
                if (path == "/app/manifest") {
                    // runs on a WebView worker thread — blocking download is fine
                    val json = if (demoMode || reviewMode) "{}"
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

    // ── Armchair-review refinements (Malcolm 2026-08-04) ────────────
    private var sessionStartedFor = ""
    private var txOnNoticeShown = false

    private fun onConnectedSession(name: String) {
        SessionCache.init(this)
        prefetchSession()   // EVERY (re)connection — an OTA reboot can cut the walk short
        if (sessionStartedFor == name) return
        sessionStartedFor = name
        val (model, edits) = SessionCache.loadPending()
        if (edits.isNotEmpty() && model == name) {
            // Malcolm's rule (2026-08-04): send ONLY with the transmitter OFF —
            // then the app controls the bank and edits land in the right place.
            Thread {
                var txLive = false
                bleSyncQuiet("/api/state.json")?.let { body ->
                    runCatching {
                        // last_pkt_ms is an AGE in ms (-1 = no TX heard yet),
                        // not a timestamp (bug found 2026-08-04).
                        val lastPkt = org.json.JSONObject(String(body))
                            .getJSONObject("rf").optLong("last_pkt_ms", -1)
                        txLive = lastPkt in 0..2999
                    }
                }
                val what = edits.joinToString(", ") { it.label }
                // Malcolm 2026-08-04: TX on → never offered; edits DISCARDED
                // with a clear notice (no stale-edit limbo).
                if (txLive) {
                    // Malcolm 2026-08-04: keep the edits — they stay until
                    // overwritten by a newer offline edit (or sent later).
                    // Un-latch so a TX-off reconnect still gets the offer; the
                    // notice shows once per launch (no between-flights nagging).
                    sessionStartedFor = ""
                    if (txOnNoticeShown) return@Thread
                    txOnNoticeShown = true
                    runOnUiThread {
                        android.app.AlertDialog.Builder(this)
                            .setTitle("Offline edits kept")
                            .setMessage("Your offline edits ($what) cannot be sent because " +
                                "the transmitter is on.\n\nThey are kept — connect with " +
                                "the transmitter off to send them.")
                            .setPositiveButton("OK", null)
                            .show()
                    }
                    return@Thread
                }
                runOnUiThread {
                    android.app.AlertDialog.Builder(this)
                        .setTitle("Settings edited offline")
                        .setCancelable(false)
                        .setMessage("While offline you edited: $what.\n\n" +
                            "Send the edits to the model now, or discard them and keep " +
                            "what the model already has?\n\n" +
                            "While sending, keep the transmitter OFF and the model powered.")
                        .setPositiveButton("Send to model") { _, _ -> sendPendingEdits(edits) }
                        .setNegativeButton("Discard offline edits") { _, _ ->
                            SessionCache.savePending("", emptyList()) }
                        .setNeutralButton("Not now", null)
                        .show()
                }
            }.start()
        }
    }

    private fun sendPendingEdits(edits: List<SessionCache.PendingEdit>) {
        // Solid progress dialog (Malcolm 2026-08-04: "I did not know when
        // the upload had finished") — bar per radio step, then a done tick.
        val banked = edits.any { it.bank != null }
        // +2 = the two put-back selects (worst case); the bar just ends early.
        val steps = edits.fold(0) { a, e -> a + if (e.bank != null) 2 else 1 } +
                    (if (banked) 2 else 0) +
                    1 + (if (edits.any { it.fn == 143 }) 1 else 0)
        val lab = android.widget.TextView(this).apply {
            text = "Sending edits… 0 / $steps"
            textSize = 16f
            setPadding(60, 50, 60, 10)
        }
        val bar = android.widget.ProgressBar(this, null,
            android.R.attr.progressBarStyleHorizontal).apply {
            max = steps
            setPadding(50, 0, 50, 30)
        }
        val box = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            addView(lab); addView(bar)
        }
        val dlg = android.app.AlertDialog.Builder(this)
            .setView(box).setCancelable(false).create()
        dlg.show()
        var doneSteps = 0
        var failures = 0
        fun step(ok: Boolean) {
            doneSteps++
            if (!ok) failures++
            runOnUiThread {
                bar.progress = doneSteps
                lab.text = "Sending edits… $doneSteps / $steps\n" +
                           "Keep the transmitter OFF and the model ON."
            }
        }
        fun finish(msg: String, holdMs: Long) {
            runOnUiThread {
                lab.text = msg
                bar.visibility = android.view.View.GONE
            }
            Thread.sleep(holdMs)
            runOnUiThread { dlg.dismiss() }
        }
        Thread {
            // Foolish-user guard: the offer may have sat open a while —
            // re-check the transmitter at PRESS time.
            var txLive = false
            bleSyncQuiet("/api/state.json")?.let { body ->
                runCatching {
                    val lastPkt = org.json.JSONObject(String(body))
                        .getJSONObject("rf").optLong("last_pkt_ms", -1)
                    txLive = lastPkt in 0..2999
                }
            }
            if (txLive) {
                finish("⚠️ The transmitter came on — nothing was sent.\n" +
                       "The edits are kept; try again with the transmitter off.", 6000)
                return@Thread
            }
            // The FC's own banks (MSP_STATUS bytes 23/25) BEFORE any select:
            // the FC goes back on them before the save, because the EEPROM
            // save persists the current bank and Rotorflight re-applies the
            // pilot's switch only when it MOVES (rc_adjustments compares the
            // channel value with its own last-applied value) — a model saved
            // on the last edit's bank would fly on that bank with the switch
            // still saying another. Unreadable → nothing is sent.
            var orig: Pair<Int, Int>? = null
            if (banked) {
                lastPageMspMs = System.currentTimeMillis()
                orig = bleSyncQuiet("/api/msp?fn=101")?.let { SessionCache.fcBanks(String(it)) }
                if (orig == null) {
                    finish("⚠️ Could not read which bank the flight controller is on — " +
                           "nothing was sent.\nThe edits are kept; check the model is " +
                           "powered and try again.", 6000)
                    return@Thread
                }
                Thread.sleep(300)
            }
            var curPid = orig?.first
            var curRate = orig?.second
            fun select(b: Int): Boolean {
                lastPageMspMs = System.currentTimeMillis()
                val ok = bleSyncQuiet("/api/msp?fn=210&data=%02X".format(b)) != null
                Thread.sleep(300)
                return ok
            }
            for (e in edits) {
                // Land each edit in the bank it was made in (fn=210 select
                // first, 0x80|idx = rate bank); gov global goes bankless.
                // Stamp so the background sweep's bank selects yield to ours.
                lastPageMspMs = System.currentTimeMillis()
                e.bank?.let { b ->
                    if ((b and 0x80) != 0) {
                        if (curRate != (b and 0x7F)) { step(select(b)); curRate = b and 0x7F } else step(true)
                    } else {
                        if (curPid != b) { step(select(b)); curPid = b } else step(true)
                    }
                }
                step(bleSyncQuiet("/api/msp?fn=${e.fn}&data=${e.hex}") != null)
                Thread.sleep(400)
            }
            orig?.let { o ->
                if (curPid != o.first) step(select(o.first))
                if (curRate != o.second) step(select(0x80 or o.second))
            }
            step(bleSyncQuiet("/api/msp?fn=250") != null)      // save to EEPROM
            if (edits.any { it.fn == 143 }) {
                Thread.sleep(300)
                step(bleSyncQuiet("/api/msp?fn=68") != null)   // gov config needs an FC reboot
            }
            if (failures == 0) {
                SessionCache.savePending("", emptyList())
                finish("✅ Edits sent to the model!", 3000)
            } else {
                // A step never arrived (model off? radio drop?) — the edits
                // are NOT lost; the offer returns next time.
                finish("⚠️ $failures step(s) didn't arrive — the edits are kept.\n" +
                       "Check the model is powered and try again (transmitter off).", 6000)
            }
        }.start()
    }

    /** Record EVERYTHING, not just what was viewed: walk the flight list and
     *  the tuning reads in the background, gently paced. */
    @Volatile private var connectedName = ""

    // ── Restore-from-recording (Malcolm 2026-08-06): the parachute ──
    @Volatile private var restPhase = "idle"   // idle | running | done
    @Volatile private var restDone = 0
    @Volatile private var restTotal = 0
    @Volatile private var restFailures = 0
    @Volatile private var restFailed = ArrayList<String>()
    @Volatile private var restError = ""       // non-empty = the run stopped early; the page shows it
    // What the run actually did — the page's finishing line is built from
    // these (Malcolm 2026-09-04, back-up-then-restore: "I thought it was
    // going to skip them all" — it did, but the page said "restored").
    @Volatile private var restWritten = 0      // items written AND verified
    @Volatile private var restSame = 0         // items the FC already held (reads only)
    @Volatile private var restBlind = 0        // of restWritten: declared items with no read-back (the switch assignments)
    @Volatile private var restWrittenNames = ArrayList<String>()   // the readable items that were written — the page names them
    @Volatile private var restRunning = false

    /** Which backup the next restore writes back: null = the pilot's own if
     *  he has one (set from /app/restore/start?which=…). */
    @Volatile private var restoreUseMine: Boolean? = null

    private fun runRestore() {
        if (restRunning) return
        restRunning = true
        restPhase = "running"; restDone = 0; restFailures = 0; restFailed = ArrayList(); restError = ""
        restWritten = 0; restSame = 0; restBlind = 0; restWrittenNames = ArrayList()
        val items = SessionCache.restoreItems(mine = restoreUseMine)
        restTotal = items.size + 1
        Thread {
            fun req(p: String): Pair<Boolean, String> {
                lastPageMspMs = System.currentTimeMillis()   // sweep yields to us
                val body = bleSyncQuiet(p)
                Thread.sleep(250)
                return Pair(body != null, body?.let { String(it) } ?: "")
            }
            // The FC's banks right now (null = MSP_STATUS unreadable).
            fun fcBanks(): Pair<Int, Int>? = SessionCache.fcBanks(req("/api/msp?fn=101").second)
            // Is a transmitter talking to the receiver? (last_pkt_ms = AGE, -1 = never)
            fun txLive(): Boolean = runCatching {
                org.json.JSONObject(req("/api/state.json").second).getJSONObject("rf").optLong("last_pkt_ms", -1) in 0..2999
            }.getOrDefault(false)
            // Note the FC's own banks first — the walk ends on bank 3, and
            // the EEPROM save would persist that as the boot profile.
            // Unreadable → nothing is written: without them we could neither
            // put the FC back nor tell which bank a write landed in.
            val orig = fcBanks()
            if (orig == null) {
                restError = "could not read the flight controller's bank (MSP 101) — nothing was written"
                restDone = restTotal; restPhase = "done"; restRunning = false
                return@Thread
            }
            val origPid = orig.first; val origRate = orig.second
            var wroteGov = false; var wroteMotor = false; var wroteAny = false
            var curPid = origPid; var curRate = origRate
            var stopped = false
            // The modes' second image (238), read once and again after any
            // mode write; absent = not read yet.
            val extraImages = HashMap<Int, String>()
            for (it0 in items) {
                var it = it0
                if (stopped) { restFailures++; restFailed.add(it.label); restDone++; continue }
                // TWO attempts — one radio hiccup among ~50 sequential MSP
                // ops must not fail the parachute.
                var itemOk = false; var already = false
                for (attempt in 1..2) {
                    var ok = true
                    already = false
                    // Skip selects that are already true — each one stalls
                    // the FC on a flash write (the swash twitch).
                    it.selectByte?.let { b ->
                        val isRate = (b and 0x80) != 0
                        val target = b and 0x7f
                        if ((if (isRate) curRate else curPid) != target) {
                            ok = req("/api/msp?fn=210&data=%02X".format(b)).first
                            if (ok) { if (isRate) curRate = target else curPid = target }
                        }
                    }
                    // Read first: an item the FC already holds is not written
                    // again (a restore of an unchanged setup is then reads
                    // only — no flash stalls, no needless re-inits). Mixer
                    // inputs and RPM notches read with their index in data=
                    // and compare against verifyHex (the write payload minus
                    // its leading index byte); chunk items compare their
                    // slice of the image.
                    val rq = if (it.readFn != 0) "/api/msp?fn=${it.readFn}" + (it.readData?.let { d -> "&data=$d" } ?: "") else ""
                    if (ok && it.readFn != 0) {
                        val cur = req(rq).second
                        it = it0.withLive(cur)            // live-owned bytes (telemetry speed) come from the FC
                        var extraOk = true
                        it.extraFn?.let { xf ->
                            if (!extraImages.containsKey(xf)) extraImages[xf] = req("/api/msp?fn=$xf").second
                            extraOk = it.extraMatches(extraImages[xf] ?: "")
                        }
                        already = it.matches(cur, strict = true) && extraOk
                    }
                    if (ok && !already) {
                        if (it.writeFn == 0) {
                            ok = false                       // verify-only item that does not match
                        } else {
                            wroteAny = true
                            ok = req("/api/msp?fn=${it.writeFn}&data=${it.hex}").first
                            // Verify: read back, compare (reply may be longer — prefix).
                            if (ok && it.readFn != 0) ok = it.matches(req(rq).second)   // readFn 0 = declared item, no read-back exists
                            // ... and the extra image (mode logic/link bytes) — re-read,
                            // it changed with the write; a slot the FC ignored fails HERE.
                            it.extraFn?.let { xf ->
                                extraImages[xf] = req("/api/msp?fn=$xf").second
                                if (ok) ok = it.extraMatches(extraImages[xf] ?: "")
                            }
                        }
                    }
                    // Banked item: the FC must STILL be on the bank we chose.
                    // A transmitter switched on mid-restore drags the FC onto
                    // its own switch position — the write (and its read-back!)
                    // would then land in that bank and "verify" perfectly.
                    val sel = it.selectByte
                    if (ok && sel != null) {
                        val isRate = (sel and 0x80) != 0
                        val now = fcBanks()
                        if (now == null) ok = false
                        else {
                            curPid = now.first; curRate = now.second
                            if ((if (isRate) now.second else now.first) != (sel and 0x7f)) ok = false
                        }
                        if (!ok && txLive()) {
                            restError = "the transmitter came on — restore stopped (switch it off and run the restore again)"
                            stopped = true
                        }
                    }
                    if (ok) { itemOk = true; break }
                    if (stopped || attempt == 2) break
                    Thread.sleep(600)
                }
                if (!itemOk) { restFailures++; restFailed.add(it.label) }
                if (itemOk && already) restSame++
                if (itemOk && !already) {
                    restWritten++
                    if (it.readFn == 0) restBlind++              // declared item: written unseen
                    else restWrittenNames.add(it.label)
                    if (it.writeFn == 143) wroteGov = true
                    if (it.writeFn == 222) wroteMotor = true   // motor / gear ratio: FC restart needed
                }
                restDone++
            }
            // Put the FC back on its own banks BEFORE the EEPROM save — unless
            // a live transmitter now owns the bank switch.
            if (!stopped) {
                if (curPid != origPid) req("/api/msp?fn=210&data=%02X".format(origPid))
                if (curRate != origRate) req("/api/msp?fn=210&data=%02X".format(0x80 or origRate))
            }
            // Save to EEPROM — verified: an unsaved restore evaporates at the
            // next power-up while the page said "restored". Nothing written
            // (the FC already held it all) → nothing to save, no flash stall.
            var saved = true
            if (wroteAny) {
                saved = req("/api/msp?fn=250").first
                if (!saved) { Thread.sleep(600); saved = req("/api/msp?fn=250").first }
                if (!saved) { restFailures++; restFailed.add("save to flight controller memory (EEPROM) — run the restore again") }
            }
            // Governor config and the motor block only take effect after an
            // FC restart — reboot only after a CONFIRMED save (an unsaved
            // reboot would throw the whole restore away).
            if ((wroteGov || wroteMotor) && saved) req("/api/msp?fn=68")
            restDone++
            restPhase = "done"
            restRunning = false
        }.start()
    }

    // Page MSP traffic stamps this; the sweep's bank switching yields to it
    // (Malcolm 2026-08-06: interleaved selects showed the WRONG bank's values).
    @Volatile private var lastPageMspMs = 0L
    private fun pageMspQuiet() = System.currentTimeMillis() - lastPageMspMs > 10_000

    @Volatile private var prefetchRunning = false
    @Volatile private var snapPhase = "idle"   // idle | running | done
    @Volatile private var snapDone = 0
    @Volatile private var snapTotal = 0
    // ok = this run completed the whole Rotorflight sweep with every read
    // answered, so the frozen restore point is fresh and complete. Anything
    // less says why in snapError (the page shows ⚠️ and keeps the old backup).
    @Volatile private var snapOk = false
    @Volatile private var snapError = ""
    @Volatile private var snapRetries = 0   // reads that needed a second try: a weak link, shown live
    /** explicit = the pilot pressed "Back up": the restore point it freezes is
     *  sticky — later automatic sweeps at connection never overwrite it. */
    // A "Back up" tap landing while a sweep runs used to be DROPPED by the
    // guard below, so the pilot's deliberate backup was written as an
    // automatic one (Malcolm 2026-09-19). The sweep in flight adopts it.
    @Volatile private var pendingExplicit = false

    private fun prefetchSession(fast: Boolean = false, explicit: Boolean = false) {
        if (explicit) pendingExplicit = true
        if (prefetchRunning) return
        prefetchRunning = true
        snapPhase = "running"; snapDone = 0; snapOk = false; snapError = ""; snapRetries = 0
        Thread {
            Thread.sleep(if (fast) 100 else 6000)   // manual = at once; auto = settle first
            val pace = if (fast) 150L else 400L
            var failures = 0      // MSP reads that never answered (after one retry)
            var straightFails = 0 // ...in a row: five means the link is gone, not a hiccup
            var tooFar = false    // (Malcolm 2026-09-10: "it tried and tried" out of range)
            fun reqCoded(p: String): Pair<Int, ByteArray?> {   // followFetch records automatically
                val r = bleSyncCoded(p)
                // Progress counts PLANNED items, not requests: bank checks,
                // selects and retries pushed "done" past "total" (Malcolm
                // 2026-09-07: "97/90 is beyond 100%").
                Thread.sleep(pace)
                return r
            }
            fun req(p: String): ByteArray? = reqCoded(p).second
            // A Rotorflight read the backup depends on: one retry, then it
            // counts as a failure — a missing answer must never let a stale
            // value from an earlier session pass as today's backup. An
            // `optional` read the FC rejects (502 — older Rotorflight) is not
            // a failure: the item is dropped from the recording so the
            // restore point cannot carry a stale copy of it either.
            fun mspRead(p: String, optional: Boolean = false) {
                try {
                    if (tooFar) return                     // the link is gone: skip the rest, finish fast
                    val first = reqCoded(p)
                    if (first.second != null) { straightFails = 0; return }
                    if (optional && first.first == 502) { SessionCache.forget(p); return }
                    Thread.sleep(500)
                    val second = reqCoded(p)
                    if (second.second != null) { straightFails = 0; snapRetries++; return }
                    if (optional && second.first == 502) { SessionCache.forget(p); return }
                    failures++
                    straightFails++
                    if (straightFails >= 5) tooFar = true
                } finally { snapDone++ }                 // one planned item, however many tries
            }
            fun selectBank(byte: Int) {
                val hex = "%02X".format(byte)
                SessionCache.noteBankSelect(hex)
                req("/api/msp?fn=210&data=$hex")
            }
            // The FC's banks now, from MSP_STATUS bytes 23/25 (null = no answer).
            fun fcBanks(): Pair<Int, Int>? = req("/api/msp?fn=101")?.let { SessionCache.fcBanks(String(it)) }
            snapTotal = 4                                // state, flights, events x2
            var txLive = false
            req("/api/state.json")?.let { body ->
                runCatching {
                    // AGE in ms, -1 = never — the bank sweep must NEVER run
                    // when this is small (TX live).
                    val lastPkt = org.json.JSONObject(String(body))
                        .getJSONObject("rf").optLong("last_pkt_ms", -1)
                    txLive = lastPkt in 0..2999
                }
            }
            snapDone++
            val flightPaths = mutableListOf<String>()
            req("/api/flights.json")?.let { body ->
                runCatching {
                    val arr = org.json.JSONArray(String(body))
                    for (k in 0 until arr.length()) {
                        val idx = arr.getJSONObject(k).optInt("i", 0)
                        if (idx > 0) flightPaths.add("/api/flightlog.json?f=$idx")
                    }
                }
            }
            snapDone++
            req("/api/events.json"); snapDone++
            req("/api/events-prev.json"); snapDone++   // previous boot's persisted tail
            // Rotorflight reads — every PID-side bank + every rate bank the
            // flight controller has (MSP 101 bytes 24/26 say how many),
            // ONLY with the transmitter off (never switch a bank under a
            // live TX). Current banks from MSP_STATUS fn=101 bytes 23/25 —
            // bytes 24/26 are the profile COUNTS; the 2026-09-04 review found
            // the old code reading those, so every sweep parked the FC on
            // bank 1 instead of putting it back. Restored exactly afterwards.
            // Foolish-user guard (Malcolm 2026-08-04): if the transmitter
            // comes ON mid-sweep, stop switching banks IMMEDIATELY and put
            // the FC back on its own banks — never fly on a sweep leftover.
            fun txAppeared(): Boolean {
                val body = req("/api/state.json") ?: return false
                return runCatching {
                    val lastPkt = org.json.JSONObject(String(body))
                        .getJSONObject("rf").optLong("last_pkt_ms", -1)
                    lastPkt in 0..2999
                }.getOrDefault(false)
            }
            // After a bank's reads: is the FC STILL on that bank? A TX that
            // came on between the select and the reads drags the FC onto its
            // switch's bank — the reads would then be another bank's values
            // filed under this one. null (no answer) counts as not verified.
            fun stillOn(pid: Int?, rate: Int?): Boolean {
                val now = fcBanks() ?: return false
                if (pid != null && now.first != pid) return false
                if (rate != null && now.second != rate) return false
                return true
            }
            // Yield to the user's tuning pages: wait (≤2 min) for a 10 s gap
            // in page MSP traffic before ANY bank switching; still busy →
            // skip the MSP sweep this run.
            var waited = 0L
            while (!pageMspQuiet() && waited < 120_000) { Thread.sleep(2000); waited += 2000 }
            var sweepOK = false
            if (txLive) {
                snapError = "the transmitter is on — switch it off, then back up"
            } else if (!pageMspQuiet()) {
                snapError = "a Rotorflight page was busy reading — back up again in a moment"
            } else {
                val orig = fcBanks()
                if (orig == null) {
                    snapError = "could not read the flight controller's bank (MSP 101) — is it powered and connected, and are you close enough?"
                } else {
                    val origPid = orig.first; val origRate = orig.second
                    // How many banks this flight controller HAS (0.9.742). It
                    // used to sweep four flat, so on a full-size board banks 5
                    // and 6 were never saved - and the bar still read 100 %.
                    val counts = req("/api/msp?fn=101")?.let { SessionCache.fcBankCounts(String(it)) } ?: Pair(4, 4)
                    val nPid  = minOf(counts.first,  SessionCache.MAX_BANKS)
                    val nRate = minOf(counts.second, SessionCache.MAX_BANKS)
                    // Exactly the planned reads: bankless + 4 mixer inputs + 3 RPM
                    // notch axes + 4 reads per PID bank + 1 per rate bank. Bank
                    // selects, MSP 101 checks and TX checks are not items.
                    snapTotal += SessionCache.banklessReadFns.size + 4 + 3 + 4 * nPid + nRate
                    // Every bankless setup block (Malcolm 2026-09-04: "cover
                    // all items") — governor global, mixer, servos, modes,
                    // channel map, motor & gear, battery & meters, features,
                    // alignment, filters, telemetry, blackbox, name … the
                    // catalogue's order. Reads an older Rotorflight rejects
                    // are optional.
                    for (fn in SessionCache.banklessReadFns)
                        mspRead("/api/msp?fn=$fn", optional = fn in SessionCache.optionalReadFns)
                    // Mixer inputs — Travel extents' blocks (Malcolm
                    // 2026-08-15: the backup must not forget yesterday's
                    // additions), one read per input 1..4.
                    for (i in 1..4) mspRead("/api/msp?fn=174&data=%02X".format(i))
                    // RPM filter notches, one read per axis (roll, pitch, yaw).
                    for (a in 0..2) mspRead("/api/msp?fn=154&data=%02X".format(a), optional = true)
                    // Every bank select makes the FC write flash — a brief
                    // servo stall (the swash twitch). Skip no-op selects.
                    var curPid = origPid; var curRate = origRate
                    var aborted = false
                    for (b in 0 until nPid) {
                        if (tooFar) break
                        if (txAppeared()) { aborted = true; break }
                        if (b != curPid) { selectBank(b); curPid = b }
                        else SessionCache.noteBankSelect("%02X".format(b))
                        mspRead("/api/msp?fn=112"); mspRead("/api/msp?fn=94"); mspRead("/api/msp?fn=148"); mspRead("/api/msp?fn=146")
                        if (!stillOn(b, null)) { aborted = true; break }
                    }
                    if (!aborted) for (r in 0 until nRate) {
                        if (tooFar) break
                        if (txAppeared()) { aborted = true; break }
                        if (r != curRate) { selectBank(0x80 or r); curRate = r }
                        else SessionCache.noteBankSelect("%02X".format(0x80 or r))
                        mspRead("/api/msp?fn=111")
                        if (!stillOn(null, r)) { aborted = true; break }
                    }
                    // Put the FC back exactly — always — unless a live TX now
                    // owns the bank switch (our select would fight it).
                    if (!txAppeared()) {
                        if (curPid != origPid) selectBank(origPid)
                        if (curRate != origRate) selectBank(0x80 or origRate)
                    }
                    if (tooFar) snapError = "too far from the receiver — the link kept dropping. Move within a metre and back up again"
                    else if (aborted) snapError = "the transmitter came on (or the flight controller changed bank) mid-backup — switch it off and back up again"
                    else if (failures > 0) snapError = "$failures read${if (failures == 1) "" else "s"} got no answer — back up again"
                    sweepOK = !aborted && !tooFar && failures == 0
                }
            }
            // Full sweep completed → freeze the restore point (the rolling
            // cache keeps updating; this copy never follows the pilot's later
            // edits). A pilot's own backup (explicit) is sticky: the
            // automatic sweep at connection must never replace it.
            if (sweepOK) {
                val wanted = explicit || pendingExplicit
                val froze = SessionCache.snapshotRestorePoint(wanted)
                if (wanted) pendingExplicit = false
                snapOk = froze || !wanted
                if (!snapOk) snapError = "the backup file could not be written on the phone"
            }
            snapTotal += flightPaths.size
            for (p in flightPaths) { req(p); snapDone++ }
            if (sweepOK && snapDone < snapTotal) snapDone = snapTotal   // every planned item was attempted
            // A "Back up" that landed after the freeze still gets what it
            // asked for, from the reads this sweep just gathered.
            if (pendingExplicit) {
                if (sweepOK) { SessionCache.snapshotRestorePoint(true); snapOk = true }
                pendingExplicit = false
            }
            SessionCache.saveIfDirty()
            snapPhase = "done"
            prefetchRunning = false
        }.start()
    }

    /** Blocking GET through followFetch (which does the recording); null on failure. */
    private fun bleSyncQuiet(pathAndQuery: String): ByteArray? = bleSyncCoded(pathAndQuery).second

    /** As bleSyncQuiet, with the receiver's HTTP code too (0 = no answer at
     *  all, -1 = transport trouble): the receiver says 502 when the FC
     *  REJECTED the request (an MSP this Rotorflight build lacks), 504 when
     *  it never answered. The body is null unless the code was 200. */
    private fun bleSyncCoded(pathAndQuery: String): Pair<Int, ByteArray?> {
        val latch = java.util.concurrent.CountDownLatch(1)
        var out: ByteArray? = null
        var code = 0
        followFetch("GET", pathAndQuery, emptyMap(), null, 0) { res ->
            res.fold(
                onSuccess = { r ->
                    code = if (r.code == 0) 200 else r.code
                    if (code == 200) out = r.body
                },
                onFailure = { code = -1 })
            latch.countDown()
        }
        latch.await(20, java.util.concurrent.TimeUnit.SECONDS)
        return Pair(code, out)
    }

    // Prepend the bridge shim so it runs before any of the page's scripts.
    // In demo mode the DEMO shim is injected instead: it intercepts fetch()
    // with canned receiver data, so nothing ever touches Bluetooth.
    private fun withShim(html: ByteArray): ByteArray {
        // The demos answer every request themselves, but the page's
        // "Load another model" / Bluetooth-badge disconnect still has to reach
        // the app, so the demo gets the disconnect hook too (Malcolm 2026-09-11:
        // "load another model fails on Android" — the hook was only in JS_SHIM).
        val tag = if (demoMode)
            "<script>$JS_DISCONNECT_HOOK</script><script>window.__demoRole=\"$demoRole\";</script><script src=\"/demo-shim.js\"></script>".toByteArray(Charsets.UTF_8)
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
        if (reviewMode) {   // armchair review: recording answers, radio sleeps
            val bare = pathAndQuery.substringBefore("?")
            val q = pathAndQuery.substringAfter("?", "")
            if (bare == "/api/msp") {
                val u = Uri.parse("$ORIGIN$pathAndQuery")
                val fn = u.getQueryParameter("fn")?.toIntOrNull() ?: -1
                val dataHex = u.getQueryParameter("data")
                if (fn == 210) {   // bank select = part of the READ flow:
                    // note it (banked reads key by it), nod politely.
                    if (!dataHex.isNullOrEmpty()) SessionCache.noteBankSelect(dataHex)
                    cb(kotlin.Result.success(Rxv2Ble.Response(200, "text/plain", "", ByteArray(0))))
                    return
                }
                if (!dataHex.isNullOrEmpty()) {   // offline EDIT: capture for the reconnect offer
                    if (SessionCache.captureOfflineWrite(fn, dataHex))
                        cb(kotlin.Result.success(Rxv2Ble.Response(200, "text/plain", "", ByteArray(0))))
                    else
                        cb(kotlin.Result.success(Rxv2Ble.Response(409, "text/plain", "",
                            "receiver offline — this change cannot be made in review".toByteArray())))
                    return
                }
                if (fn == 250 || fn == 68) {   // EEPROM save / reboot: nod politely
                    cb(kotlin.Result.success(Rxv2Ble.Response(200, "text/plain", "", ByteArray(0))))
                    return
                }
            }
            if (method == "GET") {
                val hit = SessionCache.lookup(pathAndQuery)
                if (hit != null) {
                    cb(kotlin.Result.success(Rxv2Ble.Response(200, hit.first, "", hit.second)))
                    return
                }
            }
            if (method == "POST" && bare == "/api/time") {
                cb(kotlin.Result.success(Rxv2Ble.Response(200, "application/json", "",
                    "{\"ok\":true}".toByteArray())))
                return
            }
            val code = if (method == "GET") 404 else 409
            cb(kotlin.Result.success(Rxv2Ble.Response(code, "application/json", "",
                "{\"ok\":false,\"error\":\"receiver offline — reviewing the last session\"}".toByteArray())))
            return
        }
        ble.request(method, pathAndQuery, headers, body) { result ->
            val resp = result.getOrNull()
            // Bank selects steer the recorder's keys for banked MSP reads.
            if (resp != null && (resp.code == 0 || resp.code == 200)
                && pathAndQuery.startsWith("/api/msp") && pathAndQuery.contains("fn=210")) {
                Uri.parse("$ORIGIN$pathAndQuery").getQueryParameter("data")
                    ?.let { SessionCache.noteBankSelect(it) }
            }
            // Armchair-review recorder: tee every successful read.
            if (resp != null && method == "GET" && (resp.code == 0 || resp.code == 200)) {
                val bare = pathAndQuery.substringBefore("?")
                val q = if (pathAndQuery.contains("?")) pathAndQuery.substringAfter("?") else null
                if (SessionCache.cacheable(bare, q))
                    SessionCache.record(pathAndQuery, bare, resp.contentType, resp.body)
            }
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
                    val json = if (demoMode || reviewMode) "{}"
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
            if (p == "/app/declare" || p == "/app/declared" || p == "/app/backup/export" ||
                p == "/app/backup/import" || p == "/app/backup/import/status") {
                fun answer(json: String) = runOnUiThread {
                    val w = webView ?: return@runOnUiThread
                    val b64 = Base64.encodeToString(json.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
                    w.evaluateJavascript(
                        "window.__bleResolve($id,200,${JSONObject.quote("application/json")},${JSONObject.quote(b64)})", null)
                }
                when (p) {
                    "/app/declare" -> {
                        val key = uri.getQueryParameter("key") ?: ""; val hex = uri.getQueryParameter("hex") ?: ""
                        val ok = key.isNotEmpty() && hex.isNotEmpty() && !demoMode && !reviewMode
                        if (ok) SessionCache.declare(key, hex)
                        answer("{\"ok\":$ok}")
                    }
                    "/app/declared" -> answer(JSONObject(SessionCache.declared() as Map<*, *>).toString())
                    "/app/backup/export" -> {
                        val json = SessionCache.exportRestoreJson()
                        if (json == null) answer("{\"ok\":false,\"error\":\"no backup on this phone for this model yet\"}")
                        else {
                            val safe = SessionCache.modelName.map { if (it.isLetterOrDigit()) it else '_' }.joinToString("").ifEmpty { "model" }
                            val dir = java.io.File(cacheDir, "backups").apply { mkdirs() }
                            val day = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US).format(java.util.Date())
                            val f = java.io.File(dir, "$safe-LDRC-backup-$day.json").apply { writeText(json) }
                            val u = androidx.core.content.FileProvider.getUriForFile(this@MainActivity, "$packageName.fileprovider", f)
                            val send = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                                type = "application/json"
                                putExtra(android.content.Intent.EXTRA_STREAM, u)
                                putExtra(android.content.Intent.EXTRA_SUBJECT, "LDRC backup — ${SessionCache.modelName}")
                                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            }
                            runOnUiThread { startActivity(android.content.Intent.createChooser(send, "Share backup")) }
                            answer("{\"ok\":true}")
                        }
                    }
                    "/app/backup/import" -> {
                        if (demoMode || reviewMode || connectedName.isEmpty())
                            answer("{\"ok\":false,\"error\":\"" + (if (demoMode || reviewMode) "this is the demo \u2014 nothing here is really connected" else "connect to the receiver or dongle first") + "\"}")
                        else {
                            importFor = connectedName; importPhase = "picking"; importModel = ""; importCount = 0; importMechanics = true
                            runOnUiThread { importPick.launch(arrayOf("application/json", "text/plain", "application/octet-stream")) }
                            answer("{\"ok\":true}")
                        }
                    }
                    else -> answer("{\"phase\":\"$importPhase\",\"model\":${JSONObject.quote(importModel)},\"count\":$importCount,\"mechanics\":$importMechanics}")
                }
                return
            }
            if (p == "/app/restore/info" || p == "/app/restore/start" || p == "/app/restore/progress") {
                fun answer(json: String) = runOnUiThread {
                    val w = webView ?: return@runOnUiThread
                    val b64 = Base64.encodeToString(json.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
                    w.evaluateJavascript(
                        "window.__bleResolve($id,200,${JSONObject.quote("application/json")},${JSONObject.quote(b64)})", null)
                }
                when (p) {
                    "/app/restore/info" -> {
                        val avail = !demoMode && !reviewMode && SessionCache.restoreItems().isNotEmpty() &&
                                    SessionCache.modelName == connectedName
                        val rpAt = SessionCache.restorePointAtMs()
                        val whenTxt = if (rpAt > 0)
                            android.text.format.DateFormat.format("d MMM HH:mm", rpAt) else ""
                        // explicit = the pilot's own "Back up" / an imported file (sticky);
                        // false = the automatic freeze taken at connection.
                        // items = every setting the restore point holds, by name, so
                        // the page can show a human what is in it (Malcolm 2026-09-17:
                        // the exported JSON "means little to a mere human").
                        val items = org.json.JSONArray().also { a -> SessionCache.restoreItems().forEach { a.put(it.label) } }
                        // Two slots since 0.9.800: name BOTH so the page can offer the choice.
                        val choices = org.json.JSONArray()
                        if (!demoMode && !reviewMode && SessionCache.modelName == connectedName) {
                            for (mine in listOf(true, false)) {
                                val n = SessionCache.restoreItems(mine = mine).size
                                if (n == 0) continue
                                val at = SessionCache.restorePointAtMs(mine)
                                val w = if (at > 0) android.text.format.DateFormat.format("d MMM HH:mm", at).toString() else ""
                                choices.put(JSONObject().put("which", if (mine) "yours" else "auto")
                                                        .put("items", n).put("when", w))
                            }
                        }
                        answer("{\"available\":$avail,\"when\":${JSONObject.quote(whenTxt.toString())},\"explicit\":${SessionCache.restorePointIsExplicit()},\"choices\":$choices,\"items\":$items}")
                    }
                    "/app/restore/start" -> {
                        if (demoMode || reviewMode) {
                            answer("{\"ok\":false,\"error\":\"this is the demo \u2014 nothing here is really connected\"}")
                        } else Thread {
                            // Foolish-user guard: refuse outright with the TX on.
                            var txLive = false
                            bleSyncQuiet("/api/state.json")?.let { body ->
                                runCatching {
                                    val lastPkt = org.json.JSONObject(String(body))
                                        .getJSONObject("rf").optLong("last_pkt_ms", -1)
                                    txLive = lastPkt in 0..2999
                                }
                            }
                            if (txLive) answer("{\"ok\":false,\"error\":\"switch the transmitter OFF first\"}")
                            else {
                                val which = uri.getQueryParameter("which")
                                restoreUseMine = when (which) { "yours" -> true; "auto" -> false; else -> null }
                                runRestore(); answer("{\"ok\":true}")
                            }
                        }.start()
                    }
                    else -> {
                        val names = restFailed.joinToString(",") { JSONObject.quote(it) }
                        val wnames = restWrittenNames.joinToString(",") { JSONObject.quote(it) }
                        answer("{\"phase\":\"$restPhase\",\"done\":$restDone,\"total\":$restTotal,\"failures\":$restFailures,\"failed\":[$names],\"error\":${JSONObject.quote(restError)}," +
                               "\"written\":$restWritten,\"same\":$restSame,\"blind\":$restBlind,\"writtenNames\":[$wnames]}")
                    }
                }
                return
            }
            if (p == "/app/snapshot/start" || p == "/app/snapshot/progress") {
                val json = if (p == "/app/snapshot/start") {
                    if (!demoMode && !reviewMode) { prefetchSession(fast = true, explicit = true); "{\"ok\":true}" }   // the pilot's own backup — sticky
                    else "{\"ok\":false,\"error\":\"this is the demo \u2014 nothing here is really connected\"}"
                } else {
                    // Review: phone IS the store — the page hides its save button.
                    if (reviewMode) "{\"phase\":\"replay\",\"done\":0,\"total\":0}"
                    else "{\"phase\":\"$snapPhase\",\"done\":$snapDone,\"total\":$snapTotal,\"ok\":$snapOk,\"retries\":$snapRetries,\"error\":${JSONObject.quote(snapError)}}"
                }
                runOnUiThread {
                    val w = webView ?: return@runOnUiThread
                    val b64 = Base64.encodeToString(json.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
                    w.evaluateJavascript(
                        "window.__bleResolve($id,200,${JSONObject.quote("application/json")},${JSONObject.quote(b64)})", null)
                }
                return
            }
            if (p == "/app/bleota/start" || p == "/app/bleota/progress") {
                val json = if (p == "/app/bleota/start") {
                    val fw = uri.getQueryParameter("fw")
                    if (fw != null && !demoMode && !reviewMode) {
                        ble.noteRebootish(600_000, 240_000)
                        if (otaPhase != "download" && otaPhase != "fw" &&
                            otaPhase != "fs" && otaPhase != "rebooting") {
                            val fs = uri.getQueryParameter("fs")
                            otaPhase = "download"; otaMsg = "Starting…"; otaSent = 0; otaTotal = 0; otaConfirmed = true
                            Thread { runBleOta(fw, fs) }.start()
                        }
                        "{\"ok\":true}"
                    } else "{\"ok\":false}"
                } else {
                    val j = JSONObject()
                    j.put("phase", otaPhase); j.put("msg", otaMsg)
                    j.put("sent", otaSent); j.put("total", otaTotal); j.put("confirmed", otaConfirmed)
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
            // Page-originated MSP: stamp it so the background sweep yields —
            // interleaved bank selects showed pages the WRONG bank's values.
            if (p == "/api/msp") lastPageMspMs = System.currentTimeMillis()
            // Reboot-ish traffic keeps the ride-through reconnect armed;
            // plain browsing doesn't — a disconnect then = model off.
            if (method.uppercase() == "POST" && p != "/api/time")
                if (p == "/api/firmware/install") {
                    ble.noteRebootish(300_000, 240_000)
                    // The receiver downloads by itself on this lane; the phone only watches. Keep the screen on while it does (page watches ≤ 330 s).
                    runOnUiThread { window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
                    android.os.Handler(mainLooper).postDelayed({ if (otaPhase == "idle" || otaPhase == "done" || otaPhase == "error") window.clearFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }, 420_000)
                } else ble.noteRebootish(15_000)
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
        fun disconnect() { runOnUiThread { if (demoMode || reviewMode) { demoMode = false; reviewMode = false; showScanner() } else { autoDone = true; SessionCache.saveIfDirty(); ble.disconnect() } } }   // Load another model works in the demo too (Malcolm 2026-09-11)
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
        // The page posts 'disconnect' the iOS way
        // (window.webkit.messageHandlers.rxv2.postMessage); shim that object so
        // the page code is unchanged. Injected on its own in the demos, and as
        // part of JS_SHIM on a live link.
        private const val JS_DISCONNECT_HOOK = """
        (function(){
          window.rxv2 = window.rxv2 || {};
          window.rxv2.disconnect = function(){ try{ AndroidBle.disconnect(); }catch(e){} };
          if (!window.webkit) window.webkit = {};
          if (!window.webkit.messageHandlers) window.webkit.messageHandlers = {};
          window.webkit.messageHandlers.rxv2 = {
            postMessage: function(m){ if(String(m)==='disconnect') window.rxv2.disconnect(); }
          };
        })();
        """
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


// A photograph per receiver, on the phone: files/photos/<name>.jpg, ≤900 px.
object ModelPhotos {
    private fun safe(n: String) = n.map { if (it.isLetterOrDigit() || it == '-' || it == '_') it else '_' }.joinToString("")
    fun file(ctx: android.content.Context, name: String): java.io.File {
        val d = java.io.File(ctx.filesDir, "photos"); d.mkdirs()
        return java.io.File(d, safe(name) + ".jpg")
    }
    fun load(ctx: android.content.Context, name: String, side: Int): android.graphics.Bitmap? {
        val f = file(ctx, name); if (!f.exists()) return null
        val b = android.graphics.BitmapFactory.decodeFile(f.path) ?: return null
        val s = side.toFloat() / minOf(b.width, b.height)
        val w = (b.width * s).toInt().coerceAtLeast(1); val h = (b.height * s).toInt().coerceAtLeast(1)
        val scaled = android.graphics.Bitmap.createScaledBitmap(b, w, h, true)
        return android.graphics.Bitmap.createBitmap(scaled, (w - side).coerceAtLeast(0) / 2, (h - side).coerceAtLeast(0) / 2, minOf(side, w), minOf(side, h))
    }
    fun save(ctx: android.content.Context, name: String, uri: Uri) {
        try {
            val opts = android.graphics.BitmapFactory.Options().apply { inJustDecodeBounds = true }
            ctx.contentResolver.openInputStream(uri)?.use { android.graphics.BitmapFactory.decodeStream(it, null, opts) }
            var sample = 1
            while (maxOf(opts.outWidth, opts.outHeight) / sample > 1800) sample *= 2
            val o2 = android.graphics.BitmapFactory.Options().apply { inSampleSize = sample }
            val b = ctx.contentResolver.openInputStream(uri)?.use { android.graphics.BitmapFactory.decodeStream(it, null, o2) } ?: return
            val s = minOf(1f, 900f / maxOf(b.width, b.height))
            val small = if (s < 1f) android.graphics.Bitmap.createScaledBitmap(b, (b.width * s).toInt(), (b.height * s).toInt(), true) else b
            java.io.FileOutputStream(file(ctx, name)).use { small.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, it) }
        } catch (_: Exception) {}
    }
    fun remove(ctx: android.content.Context, name: String) { file(ctx, name).delete() }
}
