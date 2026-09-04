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
    // Delete a saved model's recording + restore point (Malcolm 2026-08-22:
    // long-press a review row to remove it, so they don't pile up).
    fun deleteSession(model: String) {
        fileFor(model)?.delete()
        restoreFileFor(model)?.delete()
    }

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

    private val pidBankFns = setOf("112", "94", "148", "146")

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
        if (path == "/api/msp" && (query ?: "").contains("data=")) {
            // fn=174 (GET_MIXER_INPUT) is the one READ whose parameter — the
            // input index — rides in data=; without this exception the
            // Travel-extents reads were never recorded and backup/restore
            // silently forgot the mixer (Malcolm 2026-08-15).
            if (!(query ?: "").contains("fn=174")) return false
        }
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

    // ── Restore-from-recording (Malcolm 2026-08-06) ─────────────────
    // The confused pilot's parachute: every recorded bank's tuning read is
    // byte-symmetric with its SET command — write the whole lot back.
    // readData/verifyHex: mixer inputs (171/174) read with their index in
    // data= and verify against the payload minus its leading index byte.
    data class RestoreItem(val selectByte: Int?, val writeFn: Int, val readFn: Int, val hex: String, val label: String,
                           val readData: String? = null, val verifyHex: String? = null)

    // The rolling recording tees EVERY read — including read-backs of the
    // very edits a confused pilot wants to undo (Malcolm's closed-loop test
    // caught the restore re-writing the random edits). The parachute uses a
    // FROZEN restore point: written only when a full TX-off sweep completes.
    private fun restoreFileFor(model: String): File? {
        val d = dir ?: return null
        val safe = if (model.isEmpty()) "last"
                   else model.map { if (it.isLetterOrDigit()) it else '_' }.joinToString("")
        return File(d, "restore-$safe.json")
    }
    private val restoreKeyPrefixes = listOf(
        "/api/msp?fn=112&bank=", "/api/msp?fn=94&bank=",
        "/api/msp?fn=148&bank=", "/api/msp?fn=146&bank=", "/api/msp?fn=111&bank=",
        "/api/msp?fn=174&data=")   // mixer inputs (Travel extents)

    /** The mechanical items — servo centres/travel (fn 120) and the mixer's
     *  limits, trims and input travel (42, 174). A backup from ANOTHER model
     *  leaves these out on import: they belong to that airframe's linkage. */
    val mechanicsKeyPrefixes = listOf("/api/msp?fn=120", "/api/msp?fn=42", "/api/msp?fn=174&data=")

    /** The FC's current banks from MSP_STATUS (fn=101): byte 23 = PID
     *  profile, byte 25 = rate profile; bytes 24/26 are the profile COUNTS
     *  (Rotorflight 4.6 — checked against the Goblin's reply, byte 24 = 06).
     *  The earlier code read 24/26, so every "put the FC back" selected
     *  bank 6 → RF clamps that to bank 1. null when the reply makes no sense. */
    fun fcBanks(statusHex: String): Pair<Int, Int>? {
        val h = statusHex.uppercase()
        if (h.length < 54) return null
        fun byte(i: Int) = h.substring(2 * i, 2 * i + 2).toIntOrNull(16)
        val p = byte(23) ?: return null; val pc = byte(24) ?: return null
        val r = byte(25) ?: return null; val rc = byte(26) ?: return null
        if (pc !in 1..8 || rc !in 1..8 || p >= pc || r >= rc) return null
        return Pair(p, r)
    }

    /** Freeze the tuning reads currently in the rolling cache. explicit = the
     *  pilot's own "Back up" (or an import): STICKY — the automatic freeze at
     *  connection never replaces it (review 2026-09-04: it did, so a deliberate
     *  backup lived only until the next battery). Returns false when nothing
     *  was written. */
    @Synchronized
    fun snapshotRestorePoint(explicit: Boolean = false): Boolean {
        val f = restoreFileFor(modelName) ?: return false
        if (!explicit && restorePointIsExplicit()) return false
        val keep = entries.filterKeys { k ->
            restoreKeyPrefixes.any { k.startsWith(it) } || k == "/api/msp?fn=142" || k == "/api/msp?fn=42" || k == "/api/msp?fn=120" || k.startsWith("/app/declared/")
        }
        if (keep.isEmpty()) return false
        return runCatching {
            val root = JSONObject()
            root.put("model", modelName)
            root.put("savedAtMs", System.currentTimeMillis())
            root.put("explicit", explicit)
            val es = JSONObject()
            for ((k, v) in keep) {
                val e = JSONObject()
                e.put("type", v.first)
                e.put("b64", Base64.encodeToString(v.second, Base64.NO_WRAP))
                es.put(k, e)
            }
            root.put("entries", es)
            f.writeText(root.toString())
            true
        }.getOrDefault(false)
    }

    fun restorePointAtMs(): Long {
        val f = restoreFileFor(modelName) ?: return 0
        if (!f.exists()) return 0
        return runCatching { JSONObject(f.readText()).optLong("savedAtMs", 0) }.getOrDefault(0)
    }

    /** Was the current restore point a deliberate backup (or an import)? */
    fun restorePointIsExplicit(): Boolean {
        val f = restoreFileFor(modelName) ?: return false
        if (!f.exists()) return false
        return runCatching { JSONObject(f.readText()).optBoolean("explicit", false) }.getOrDefault(false)
    }

    @Synchronized
    fun restoreItems(): List<RestoreItem> {
        val out = ArrayList<RestoreItem>()
        val f = restoreFileFor(modelName) ?: return out
        if (!f.exists()) return out
        val frozen = HashMap<String, String>()
        runCatching {
            val es = JSONObject(f.readText()).getJSONObject("entries")
            es.keys().forEach { k ->
                frozen[k] = String(Base64.decode(es.getJSONObject(k).getString("b64"), Base64.NO_WRAP))
            }
        }
        fun hexAt(key: String): String? {
            val s = frozen[key] ?: return null
            if (s.length < 2 || !s.all { it.isDigit() || it in 'a'..'f' || it in 'A'..'F' }) return null
            return s.uppercase()
        }
        for (b in 0..3) {
            hexAt("/api/msp?fn=112&bank=$b")?.let { out.add(RestoreItem(b, 202, 112, it, "PIDs bank ${b + 1}")) }
            hexAt("/api/msp?fn=94&bank=$b")?.let  { out.add(RestoreItem(b, 95,  94,  it, "advanced PIDs bank ${b + 1}")) }
            hexAt("/api/msp?fn=148&bank=$b")?.let { out.add(RestoreItem(b, 149, 148, it, "governor profile bank ${b + 1}")) }
            hexAt("/api/msp?fn=146&bank=$b")?.let { out.add(RestoreItem(b, 147, 146, it, "rescue bank ${b + 1}")) }
        }
        for (r in 0..3) {
            hexAt("/api/msp?fn=111&bank=$r")?.let { out.add(RestoreItem(0x80 or r, 204, 111, it, "rates bank ${r + 1}")) }
        }
        hexAt("/api/msp?fn=142")?.let { out.add(RestoreItem(null, 143, 142, it, "governor global")) }
        // Mixer (Travel extents, bankless): config block, then each input —
        // 171 takes ONE input per frame (index byte + rate/min/max).
        hexAt("/api/msp?fn=42")?.let { out.add(RestoreItem(null, 43, 42, it, "mixer limits & trims")) }
        val axisNames = mapOf(1 to "roll", 2 to "pitch", 3 to "yaw", 4 to "collective")
        for (i in 1..4) {
            val key = "%02X".format(i)
            hexAt("/api/msp?fn=174&data=$key")?.let {
                out.add(RestoreItem(null, 171, 174, key + it, "mixer input — ${axisNames[i]}",
                                    readData = key, verifyHex = it))
            }
        }
        // Servos (bankless): stored fn-120 image = count(1B) + 16 B/servo;
        // fn 212 writes one servo (index + 16 B). Structural verify for all
        // but the LAST servo (mid-restore the fn-120 read-back mixes old and
        // new), then the last item compares the whole image byte-for-byte.
        hexAt("/api/msp?fn=120")?.let { full ->
            val count = full.take(2).toIntOrNull(16) ?: 0
            if (count > 0 && full.length >= 2 + count * 32) {
                val roles = listOf("swash 1", "swash 2", "swash 3", "TAIL", "5", "6", "7", "8")
                for (i in 0 until count) {
                    val slice = full.substring(2 + i * 32, 2 + i * 32 + 32)
                    val idx = "%02X".format(i)
                    val last = i == count - 1
                    out.add(RestoreItem(null, 212, 120, idx + slice,
                                        "servo ${i + 1} (${roles[minOf(i, 7)]})",
                                        readData = null,
                                        verifyHex = if (last) full else full.take(2)))
                }
            }
        }
        // Declared items (Malcolm 2026-08-30): write-only settings the FC can't
        // read back — the bank/rates selector adjustment ranges (MSP 53).
        // readFn 0 = no read-back possible.
        for ((k, v) in frozen) {
            if (!k.startsWith("/app/declared/adj")) continue
            if (v.length < 4 || !v.all { it.isDigit() || it in 'a'..'f' || it in 'A'..'F' }) continue
            val label = when { k.endsWith("adj40") -> "bank selector switch"
                               k.endsWith("adj41") -> "rates selector switch"
                               else -> "declared $k" }
            out.add(RestoreItem(null, 53, 0, v.uppercase(), label))
        }
        return out
    }

    // ── Declared items, export & import (Malcolm 2026-08-30) ──
    @Synchronized
    fun declare(key: String, hex: String) {
        val k = "/app/declared/$key"
        entries[k] = Pair("text/plain", hex.toByteArray(Charsets.UTF_8))
        savedAtMs = System.currentTimeMillis(); dirty = true; saveIfDirty()
        val f = restoreFileFor(modelName) ?: return
        runCatching {
            val root = if (f.exists()) JSONObject(f.readText()) else JSONObject().put("model", modelName).put("entries", JSONObject())
            val es = root.optJSONObject("entries") ?: JSONObject().also { root.put("entries", it) }
            es.put(k, JSONObject().put("type", "text/plain").put("b64", Base64.encodeToString(hex.toByteArray(), Base64.NO_WRAP)))
            root.put("savedAtMs", System.currentTimeMillis())
            f.writeText(root.toString())
        }
    }

    @Synchronized
    fun declared(): Map<String, String> {
        val out = HashMap<String, String>()
        restoreFileFor(modelName)?.takeIf { it.exists() }?.let { f ->
            runCatching {
                val es = JSONObject(f.readText()).getJSONObject("entries")
                es.keys().forEach { k -> if (k.startsWith("/app/declared/"))
                    out[k.removePrefix("/app/declared/")] = String(Base64.decode(es.getJSONObject(k).getString("b64"), Base64.NO_WRAP)) }
            }
        }
        for ((k, v) in entries) if (k.startsWith("/app/declared/")) out[k.removePrefix("/app/declared/")] = String(v.second)
        return out
    }

    /** Portable backup file (same shape as iOS): the frozen restore point. */
    fun exportRestoreJson(): String? {
        val f = restoreFileFor(modelName)?.takeIf { it.exists() } ?: return null
        return runCatching {
            val root = JSONObject(f.readText())
            if (root.getJSONObject("entries").length() == 0) return null
            root.put("format", "rxv2-backup-1")
            root.toString(2)
        }.getOrNull()
    }

    /** Result of importRestore: mechanics = servo/mixer items were kept (same-named model). */
    data class ImportResult(val ok: Boolean, val fileModel: String, val count: Int, val mechanics: Boolean)

    /** Adopt a backup file as the restore point for the CONNECTED model. A file
     *  from ANOTHER model (different name) comes without its mechanics — servo
     *  centres/travel and mixer limits stay this airframe's own, as the Import
     *  dialog promises. The result is sticky (explicit), so a reconnection's
     *  automatic freeze cannot replace it before the pilot restores. */
    fun importRestore(json: String, forModel: String): ImportResult {
        return runCatching {
            val root = JSONObject(json)
            if (root.optString("format") != "rxv2-backup-1") return ImportResult(false, "", 0, false)
            val es = root.getJSONObject("entries")
            val fileModel = root.optString("model", "")
            val sameModel = fileModel.trim().lowercase() == forModel.trim().lowercase()
            val keep = JSONObject()
            es.keys().forEach { k ->
                if (!sameModel && mechanicsKeyPrefixes.any { k.startsWith(it) }) return@forEach
                val v = es.optJSONObject(k) ?: return@forEach
                if (!v.has("b64")) return@forEach
                keep.put(k, v)
            }
            if (keep.length() == 0) return ImportResult(false, fileModel, 0, false)
            val f = restoreFileFor(forModel) ?: return ImportResult(false, fileModel, 0, false)
            val out = JSONObject().put("model", forModel).put("savedAtMs", System.currentTimeMillis())
                .put("explicit", true).put("entries", keep)
            f.writeText(out.toString())
            ImportResult(true, fileModel, keep.length(), sameModel)
        }.getOrDefault(ImportResult(false, "", 0, false))
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
