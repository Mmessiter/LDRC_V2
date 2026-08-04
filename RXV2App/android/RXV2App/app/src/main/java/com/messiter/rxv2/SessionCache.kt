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
    private var dir: File? = null
    private var dirty = false

    // Per-model session files (Malcolm 2026-08-04: connecting another model
    // must never erase this one's recording).
    private fun fileFor(model: String): File? {
        val d = dir ?: return null
        val safe = if (model.isEmpty()) "last"
                   else model.map { if (it.isLetterOrDigit()) it else '_' }.joinToString("")
        return File(d, "session-$safe.json")
    }

    fun init(ctx: Context) {
        if (dir != null) return
        dir = ctx.filesDir
        pendingFile = File(ctx.filesDir, "pendingEdits.json")
        // One-time migration: the old single lastSession.json becomes that
        // model's own session file.
        val legacy = File(ctx.filesDir, "lastSession.json")
        if (legacy.exists()) {
            runCatching {
                val model = JSONObject(legacy.readText()).optString("model", "")
                fileFor(model)?.let { legacy.copyTo(it, overwrite = true) }
            }
            legacy.delete()
        }
        load()
    }

    /** All saved sessions, newest first — one per model. */
    fun savedSessions(): List<Pair<String, Long>> {
        val d = dir ?: return emptyList()
        val out = ArrayList<Pair<String, Long>>()
        d.listFiles { f -> f.name.startsWith("session-") }?.forEach { f ->
            runCatching {
                val root = JSONObject(f.readText())
                if (root.getJSONObject("entries").length() > 0)
                    out.add(Pair(root.optString("model", ""), root.optLong("savedAtMs", 0)))
            }
        }
        return out.sortedByDescending { it.second }
    }

    /** Load a saved model's recording as the active one (for review). */
    @Synchronized
    fun activate(model: String) {
        if (model == modelName) return
        saveIfDirty()
        entries.clear()
        modelName = model
        savedAtMs = 0
        loadFile(fileFor(model))
    }

    val available: Boolean get() = entries.isNotEmpty()

    // Bank-aware keys (Malcolm 2026-08-04: "the PID values fail to differ by
    // bank"). Reads 112/94/148 follow the PID-side bank, 111 the rate bank
    // (fn=210 select, 0x80 flag = rates) — key them by the selected bank.
    @Volatile var pidBank = 0; private set
    @Volatile var rateBank = 0; private set

    fun noteBankSelect(dataHex: String) {
        val b = dataHex.take(2).toIntOrNull(16) ?: return
        if (b and 0x80 != 0) rateBank = b and 0x7f else pidBank = b
    }

    private val pidBankFns = setOf("112", "94", "148")

    private fun keyFor(pathAndQuery: String): String {
        if (!pathAndQuery.startsWith("/api/msp?") || pathAndQuery.contains("data=")) return pathAndQuery
        val fn = pathAndQuery.substringAfter("?").split("&")
            .firstOrNull { it.startsWith("fn=") }?.removePrefix("fn=") ?: ""
        if (fn in pidBankFns) return "$pathAndQuery&bank=$pidBank"
        if (fn == "111") return "$pathAndQuery&bank=$rateBank"
        return pathAndQuery
    }

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
        entries[keyFor(pathAndQuery)] = Pair(type, body)
        if (path == "/api/state.json") {
            runCatching {
                val name = JSONObject(String(body)).getJSONObject("info").getString("name")
                if (name.isNotEmpty()) {
                    if (modelName.isNotEmpty() && name != modelName) {
                        // Different receiver: park the old model's recording
                        // in its own file and RESUME the new model's (never a
                        // chimera, never an erasure — Malcolm 2026-08-04).
                        val keep = entries[keyFor(pathAndQuery)]!!
                        dirty = true
                        saveIfDirty()
                        entries.clear()
                        modelName = name
                        loadFile(fileFor(name))
                        entries[keyFor(pathAndQuery)] = keep
                    }
                    modelName = name
                }
            }
        }
        savedAtMs = System.currentTimeMillis()
        dirty = true
    }

    @Synchronized
    fun lookup(pathAndQuery: String): Pair<String, ByteArray>? = entries[keyFor(pathAndQuery)]

    /** Called opportunistically (on disconnect / app background). */
    @Synchronized
    fun saveIfDirty() {
        val f = fileFor(modelName) ?: return
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

    // bank = fn=210 select byte to send BEFORE this write (0x80|idx for
    // rates); null = bankless (governor global).
    data class PendingEdit(val fn: Int, val hex: String, val label: String,
                           val bank: Int? = null)

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
                out.add(PendingEdit(e.getInt("fn"), e.getString("hex"), e.getString("label"),
                    if (e.has("bank")) e.getInt("bank") else null))
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
                e.bank?.let { o.put("bank", it) }
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
        // Rates follow the rate bank, gov global has none, the rest follow
        // the PID-side bank (mirrors the iOS SessionCache).
        val bank: Int? = when (fn) { 143 -> null; 204 -> 0x80 or rateBank; else -> pidBank }
        var label = writeLabels[fn] ?: "settings"
        if (bank != null) label += " (bank ${(bank and 0x7f) + 1})"
        val (model, edits) = loadPending()
        val list = ArrayList(if (model == modelName) edits else emptyList())
        list.removeAll { it.fn == fn && it.bank == bank }
        list.add(PendingEdit(fn, dataHex, label, bank))
        savePending(modelName, list)
        record("/api/msp?fn=$readFn", "/api/msp", "text/plain",
               dataHex.uppercase().toByteArray())
        saveIfDirty()
        return true
    }

    private fun load() {
        // Wake up with the newest model's session active.
        val newest = savedSessions().firstOrNull() ?: return
        modelName = newest.first
        loadFile(fileFor(newest.first))
    }

    private fun loadFile(f: File?) {
        if (f == null || !f.exists()) return
        runCatching {
            val root = JSONObject(f.readText())
            modelName = root.optString("model", modelName)
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
