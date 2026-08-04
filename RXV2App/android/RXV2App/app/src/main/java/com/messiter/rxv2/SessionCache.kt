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
        if (file != null) return
        file = File(ctx.filesDir, "lastSession.json")
        pendingFile = File(ctx.filesDir, "pendingEdits.json")
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

    // ── Offline Rotorflight edits (refinement 2) ────────────────────
    val writeToRead = mapOf(204 to 111, 202 to 112, 95 to 94, 143 to 142, 149 to 148)
    private val writeLabels = mapOf(204 to "rates", 202 to "PIDs", 95 to "advanced PIDs",
                                    143 to "governor (global)", 149 to "governor profile")
    private var pendingFile: File? = null

    data class PendingEdit(val fn: Int, val hex: String, val label: String)

    fun loadPending(): Pair<String, List<PendingEdit>> {
        val f = pendingFile ?: return Pair("", emptyList())
        if (!f.exists()) return Pair("", emptyList())
        return runCatching {
            val root = JSONObject(f.readText())
            val model = root.optString("model", "")
            val arr = root.getJSONArray("edits")
            val out = ArrayList<PendingEdit>()
            for (i in 0 until arr.length()) {
                val e = arr.getJSONObject(i)
                out.add(PendingEdit(e.getInt("fn"), e.getString("hex"), e.getString("label")))
            }
            Pair(model, out as List<PendingEdit>)
        }.getOrDefault(Pair("", emptyList()))
    }

    fun savePending(model: String, edits: List<PendingEdit>) {
        val f = pendingFile ?: return
        if (edits.isEmpty()) { f.delete(); return }
        runCatching {
            val root = JSONObject()
            root.put("model", model)
            val arr = org.json.JSONArray()
            for (e in edits) {
                val o = JSONObject()
                o.put("fn", e.fn); o.put("hex", e.hex); o.put("label", e.label)
                arr.put(o)
            }
            root.put("edits", arr)
            f.writeText(root.toString())
        }
    }

    /** Capture an offline MSP write; update the cached read so the page's
     *  own read-back verification passes. True when supported. */
    @Synchronized
    fun captureOfflineWrite(fn: Int, dataHex: String): Boolean {
        val readFn = writeToRead[fn] ?: return false
        var (model, edits) = loadPending()
        val list = ArrayList(if (model == modelName) edits else emptyList())
        list.removeAll { it.fn == fn }
        list.add(PendingEdit(fn, dataHex, writeLabels[fn] ?: "settings"))
        savePending(modelName, list)
        record("/api/msp?fn=$readFn", "/api/msp", "text/plain",
               dataHex.uppercase().toByteArray())
        saveIfDirty()
        return true
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
