// LockDownRadioControl — RXV2App (Android)  ::  SessionCache.kt
//
// The armchair review (Malcolm's lodge idea, 2026-08-04): while connected,
// every successful read the receiver answers is teed in here; afterwards
// "Review last session" serves the recording to the same bundled pages with
// the receiver switched off. Mirrors the iOS SessionCache.

package com.messiter.rxv2

import android.content.Context
import android.util.Base64
import org.json.JSONObject
import java.io.File

object SessionCache {
    private val entries = HashMap<String, Pair<String, ByteArray>>() // pathAndQuery -> (type, body)
    var modelName: String = ""; private set
    var savedAtMs: Long = 0; private set
    private var file: File? = null
    private var dirty = false

    fun init(ctx: Context) {
        file = File(ctx.filesDir, "lastSession.json")
        load()
    }

    val available: Boolean get() = entries.isNotEmpty()

    val label: String
        get() {
            val name = if (modelName.isEmpty()) "last receiver" else modelName
            if (savedAtMs == 0L) return name
            val t = android.text.format.DateFormat.format("HH:mm", savedAtMs)
            return "$name — $t"
        }

    /** Reads only; never MSP writes (data= payload) and never firmware/check. */
    fun cacheable(path: String, query: String?): Boolean {
        if (!path.startsWith("/api/")) return false
        if (path == "/api/msp" && (query ?: "").contains("data=")) return false
        if (path == "/api/firmware/check") return false
        return true
    }

    @Synchronized
    fun record(pathAndQuery: String, path: String, type: String, body: ByteArray) {
        entries[pathAndQuery] = Pair(type, body)
        if (path == "/api/state.json") {
            runCatching {
                val name = JSONObject(String(body)).getJSONObject("info").getString("name")
                if (name.isNotEmpty()) {
                    if (modelName.isNotEmpty() && name != modelName) {
                        // Different receiver — never blend two models' recordings.
                        val keep = entries[pathAndQuery]!!
                        entries.clear()
                        entries[pathAndQuery] = keep
                    }
                    modelName = name
                }
            }
        }
        savedAtMs = System.currentTimeMillis()
        dirty = true
    }

    @Synchronized
    fun lookup(pathAndQuery: String): Pair<String, ByteArray>? = entries[pathAndQuery]

    /** Called opportunistically (on disconnect / app background). */
    @Synchronized
    fun saveIfDirty() {
        val f = file ?: return
        if (!dirty) return
        dirty = false
        runCatching {
            val root = JSONObject()
            root.put("model", modelName)
            root.put("savedAtMs", savedAtMs)
            val es = JSONObject()
            for ((k, v) in entries) {
                val e = JSONObject()
                e.put("type", v.first)
                e.put("b64", Base64.encodeToString(v.second, Base64.NO_WRAP))
                es.put(k, e)
            }
            root.put("entries", es)
            f.writeText(root.toString())
        }
    }

    private fun load() {
        val f = file ?: return
        if (!f.exists()) return
        runCatching {
            val root = JSONObject(f.readText())
            modelName = root.optString("model", "")
            savedAtMs = root.optLong("savedAtMs", 0)
            val es = root.getJSONObject("entries")
            es.keys().forEach { k ->
                val e = es.getJSONObject(k)
                entries[k] = Pair(e.getString("type"),
                                  Base64.decode(e.getString("b64"), Base64.NO_WRAP))
            }
        }
    }
}
