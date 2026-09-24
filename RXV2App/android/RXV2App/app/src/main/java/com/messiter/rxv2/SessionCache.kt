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

    /** "What's in the backup" in plain lines: "PIDs — banks 1–6", "Servos — 8".
     *  Mirrors showContents() in rotorflight-backup.html and the iOS twin. */
    fun backupSummary(model: String, mine: Boolean? = null): List<String> {
        val items = restoreItems(model, mine).map { it.label }
        val banked = LinkedHashMap<String, MutableSet<Int>>()
        val numbered = LinkedHashMap<String, Int>()
        val plain = ArrayList<String>()
        val bankRe = Regex(" bank (\\d+)$")
        val parenRe = Regex(" \\(.*\\)$")
        val numRe = Regex(" (?:ch)?(\\d+)$")
        for (raw in items) {
            val bm = bankRe.find(raw)
            if (bm != null) {
                val name = raw.substring(0, bm.range.first)
                banked.getOrPut(name) { linkedSetOf() }.add(bm.groupValues[1].toInt())
                continue
            }
            val t = parenRe.replace(raw, "")
            val nm = numRe.find(t)
            if (nm != null) {
                val name = t.substring(0, nm.range.first)
                numbered[name] = (numbered[name] ?: 0) + 1
                continue
            }
            plain.add(raw)
        }
        fun cap(t: String) = if (t.isEmpty()) t else t[0].uppercase() + t.substring(1)
        fun spread(set: Set<Int>): String {
            val a = set.sorted()
            if (a.size == 1) return "bank ${a[0]}"
            val run = a.withIndex().all { (i, v) -> i == 0 || v == a[i - 1] + 1 }
            return if (run) "banks ${a[0]}\u2013${a[a.size - 1]}" else "banks " + a.joinToString(", ")
        }
        val lines = ArrayList<String>()
        for ((k, v) in banked) lines.add(cap(k) + " \u2014 " + spread(v))
        for ((k, v) in numbered) lines.add(cap(k) + "s \u2014 " + v)
        for (k in plain) lines.add(cap(k))
        return lines
    }

    /** One model's backup as held on this phone. */
    data class BackupInfo(val model: String, val atMs: Long, val explicit: Boolean, val items: Int)

    /** Every model this phone holds a backup (restore point) for, newest
     *  first — what the Backups page lists with nothing connected
     *  (Malcolm 2026-09-19: "Backups shows what backups we made and when"). */
    fun savedBackups(): List<BackupInfo> {
        val d = dir ?: return emptyList()
        val out = ArrayList<BackupInfo>()
        d.listFiles { f -> f.name.startsWith("restore-") || f.name.startsWith("backup-") }?.forEach { f ->
            runCatching {
                val root = JSONObject(f.readText())
                val n = root.optJSONObject("entries")?.length() ?: 0
                // The slot the file sits in is the truth.
                if (n > 0) out.add(BackupInfo(root.optString("model", ""),
                                              root.optLong("savedAtMs", 0),
                                              f.name.startsWith("backup-"), n))
            }
        }
        return out.sortedByDescending { it.atMs }
    }

    // Delete a saved model's recording + restore point (Malcolm 2026-08-22:
    // long-press a review row to remove it, so they don't pile up).
    fun deleteSession(model: String) {
        fileFor(model)?.delete()
        restoreFileFor(model)?.delete()
        restoreFileFor(model, true)?.delete()
    }

    /** Load a saved model's recording as the active one (for review).
     *  @Synchronized belongs HERE: a comment block once slipped between the
     *  annotation and this function, so it landed on deleteSession() and
     *  entries.clear() + loadFile() raced the BLE thread's record() (0.9.746). */
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
            // fn=174 (GET_MIXER_INPUT) and fn=154 (RPM filter notches, per
            // axis) are the READS whose parameter — the index — rides in
            // data=; without this exception the Travel-extents reads were
            // never recorded and backup/restore silently forgot the mixer
            // (Malcolm 2026-08-15).
            val q = query ?: ""
            if (!q.contains("fn=174") && !q.contains("fn=154")) return false
        }
        if (path == "/api/firmware/check") return false
        return true
    }

    /** Drop a recorded read — the FC said it does not support a read this
     *  firmware sends, so a value recorded from an earlier session (another
     *  FC version) can never be frozen as today's backup. */
    @Synchronized
    fun forget(pathAndQuery: String) {
        if (entries.remove(keyFor(pathAndQuery)) != null) { savedAtMs = System.currentTimeMillis(); dirty = true }
    }

    // FLIGHTS BY IDENTITY (0.9.833, Malcolm 2026-09-24: "Viewing a review
    // often loads the wrong file"). The receiver numbers saved flights by AGE
    // (f=1 = newest), so a new flight shifts every number and the old by-number
    // key served an older flight. Saved flights are stored under their own
    // identity (saved_at, count, dur_ms) and found through the recorded list.
    // Mirrors the iOS SessionCache.
    private fun flightNumber(pathAndQuery: String): Int? {
        if (!pathAndQuery.startsWith("/api/flightlog.json?")) return null
        val n = pathAndQuery.substringAfter("?").split("&")
            .firstOrNull { it.startsWith("f=") }?.removePrefix("f=")?.toIntOrNull() ?: return null
        return if (n > 0) n else null
    }
    private fun flightId(o: JSONObject): String? {
        if (!o.has("count") || !o.has("dur_ms")) return null
        return "flight#${o.optLong("saved_at", 0)}-${o.optLong("count")}-${o.optLong("dur_ms")}"
    }
    private fun flightId(body: ByteArray): String? = runCatching { flightId(JSONObject(String(body))) }.getOrNull()
    private fun listedFlightId(n: Int): String? = runCatching {
        val arr = org.json.JSONArray(String(entries["/api/flights.json"]!!.second))
        (0 until arr.length()).map { arr.getJSONObject(it) }.firstOrNull { it.optInt("i", -1) == n }?.let { flightId(it) }
    }.getOrNull()

    // A NEW CONNECTION (0.9.837): until its first state.json names the model,
    // replies are held back rather than filed under whichever model was
    // active. Malcolm 2026-09-24: "opening a review file opens the wrong
    // file" - every review on the phone carried ANOTHER model's state.json.
    // A switch filed the new model's first reply under the old model and then
    // saved the old model's file with it inside. Mirrors the iOS SessionCache.
    @Volatile private var awaitingIdentity = false
    private val held = ArrayList<Array<Any>>()
    @Synchronized fun connectionStarted() { awaitingIdentity = true; held.clear() }

    fun stateName(body: ByteArray): String? =
        runCatching { JSONObject(String(body)).getJSONObject("info").getString("name") }.getOrNull()?.takeIf { it.isNotEmpty() }

    @Synchronized
    fun record(pathAndQuery: String, path: String, type: String, body: ByteArray) {
        val name = if (path == "/api/state.json") stateName(body) else null
        if (name != null) {
            if (name != modelName) {
                // Different receiver: park the old model's recording in its
                // own file FIRST, then resume the new model's (never a
                // chimera, never an erasure — Malcolm 2026-08-04).
                if (modelName.isNotEmpty()) { dirty = true; saveIfDirty() }
                entries.clear()
                modelName = name
                savedAtMs = 0
                loadFile(fileFor(name))
                modelName = name
            }
            awaitingIdentity = false
            val flush = ArrayList(held); held.clear()
            for (h in flush) store(h[0] as String, h[1] as String, h[2] as ByteArray)
        } else if (awaitingIdentity) {
            if (held.size < 64) held.add(arrayOf(pathAndQuery, type, body))
            return
        }
        store(pathAndQuery, type, body)
    }

    private fun store(pathAndQuery: String, type: String, body: ByteArray) {
        val id = if (flightNumber(pathAndQuery) != null) flightId(body) else null
        if (id != null) {
            entries[id] = Pair(type, body)
            entries.remove(keyFor(pathAndQuery))   // never a by-number copy to go stale
        } else {
            entries[keyFor(pathAndQuery)] = Pair(type, body)
        }
        savedAtMs = System.currentTimeMillis()
        dirty = true
    }

    @Synchronized
    fun lookup(pathAndQuery: String): Pair<String, ByteArray>? {
        val n = flightNumber(pathAndQuery) ?: return entries[keyFor(pathAndQuery)]
        val id = listedFlightId(n) ?: return null          // only the flight the list names
        entries[id]?.let { return it }
        val old = entries[keyFor(pathAndQuery)] ?: return null   // pre-0.9.833 recording
        return if (flightId(old.second) == id) old else null
    }

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
    // writeFn 0 = verify-only (nothing to write, the read must match);
    // readFn 0 = no read-back exists (declared items).
    // Chunked images (servos 212, modes 35, rxfail 78, mixer rules 173,
    // meters 57/41): one FC read holds every chunk, each write sets one —
    // the chunk's bytes must appear at chunkOffset (hex chars) of the
    // readFn image: that is both the "already identical, skip" test and
    // the verify. Modes carry a second image (238: logic + link per slot)
    // the 35 write also sets; a slot is skipped only when BOTH match.
    data class RestoreItem(val selectByte: Int?, val writeFn: Int, val readFn: Int, val hex: String, val label: String,
                           val readData: String? = null, val verifyHex: String? = null,
                           val chunkOffset: Int? = null, val chunkHex: String? = null,
                           val extraFn: Int? = null, val extraOffset: Int? = null, val extraHex: String? = null,
                           // Hex chars of the write payload that belong to the FC as it is NOW, not to the
                           // backup: replaced by the FC's current bytes before the compare and the write.
                           // Telemetry (73/74): the link rate/ratio (bytes 8-11) is the receiver's Telemetry
                           // speed setting — a restore of a backup taken at the old speed must not drag it back.
                           val liveHexRange: IntRange? = null) {
        /** The item with its live-owned bytes taken from the FC's current image. */
        fun withLive(image: String): RestoreItem {
            val r = liveHexRange ?: return this
            val end = r.last + 1
            if (image.length < end || hex.length < end) return this
            val img = image.uppercase()
            return copy(hex = hex.substring(0, r.first) + img.substring(r.first, end) + hex.substring(end))
        }
        /** Does this FC image already carry the item? Prefix semantics for
         *  whole-image items (a reply may be longer than the write layout);
         *  strict = the image must hold EVERY wanted byte — the "skip the
         *  write" decision must never rest on a short reply. */
        fun matches(image: String, strict: Boolean = false): Boolean {
            val img = image.uppercase()
            if (chunkOffset != null && chunkHex != null) {
                if (img.length < chunkOffset + chunkHex.length) return false
                return img.substring(chunkOffset, chunkOffset + chunkHex.length) == chunkHex
            }
            val want = (verifyHex ?: hex).uppercase()
            if (strict) return img.startsWith(want)
            return img.isNotEmpty() && (img.startsWith(want) || want.startsWith(img))
        }
        fun extraMatches(image: String): Boolean {
            val off = extraOffset ?: return true
            val want = extraHex ?: return true
            val img = image.uppercase()
            if (img.length < off + want.length) return false
            return img.substring(off, off + want.length) == want
        }
    }

    // ── The catalogue (Malcolm 2026-09-04: "let's cover all items") ──
    // Every bankless Rotorflight read the backup freezes. Layouts checked
    // line by line against Rotorflight 4.6's msp.c: the SET payload is the
    // GET reply verbatim except motor config (222 = 131 without byte 6, the
    // motor count) and blackbox (81 = 80 without byte 0, the 'supported'
    // flag). NOT here, deliberately: ESC parameters (217/218 — Scorpion
    // programming freezes its telemetry), serial ports (54/55 — the
    // receiver's own link), LED/OSD/GPS/VTX, and the receiver's NVS.
    val banklessReadFns = listOf(
        142, 42, 120,                                   // governor global, mixer, servos
        10, 36, 38, 61, 240, 96, 126,                   // name, features, board, arming, trims, sensors, alignment
        64, 44, 66, 75, 77, 50, 73,                     // channel map, receiver, sticks, failsafe, rxfail, RSSI, telemetry
        80, 92, 32, 123, 131,                           // blackbox, filters, battery, ESC telemetry, motor
        34, 238, 172, 56, 40)                           // modes (+extras), mixer rules, meters
    /** Verbatim read → write items, in restore order: (read fn, write fn, label). */
    private val simpleItems = listOf(
        Triple(10, 11, "flight controller name"),
        Triple(36, 37, "features"),
        Triple(38, 39, "board alignment"),
        Triple(61, 62, "arming (auto-disarm delay)"),
        Triple(240, 239, "level trims"),
        Triple(96, 97, "sensor selection"),
        Triple(126, 220, "gyro alignment"),
        Triple(64, 65, "channel map"),
        Triple(44, 45, "receiver setup"),
        Triple(66, 67, "stick centre & travel"),
        Triple(75, 76, "failsafe"),
        Triple(50, 51, "RSSI"),
        Triple(73, 74, "telemetry sensors"),
        Triple(92, 93, "gyro filters"),
        Triple(32, 33, "battery"),
        Triple(123, 216, "ESC telemetry setup"))
    /** Reads the FC may legitimately reject (older Rotorflight builds lack
     *  them): a 'rejected' answer is not a backup failure, the item is simply
     *  not in the backup. No answer at all still is. */
    val optionalReadFns = setOf(123, 154)
    /** A telemetry image (MSP 73, 52 bytes) worth restoring: link rate and ratio non-zero
     *  and at least one sensor in the 40 slots. */
    fun telemImageGood(hex: String): Boolean {
        val h = hex.uppercase()
        if (h.length < 104) return false
        return h.substring(16, 20) != "0000" && h.substring(20, 24) != "0000" && h.substring(24, 104).any { it != '0' }
    }

    // The rolling recording tees EVERY read — including read-backs of the
    // very edits a confused pilot wants to undo (Malcolm's closed-loop test
    // caught the restore re-writing the random edits). The parachute uses a
    // FROZEN restore point: written only when a full TX-off sweep completes.
    /** TWO backups per model (Malcolm 2026-09-19): "backup-" is the pilot's
     *  own, written only when he asks; "restore-" is the automatic copy,
     *  refreshed by every clean sweep. Either can be restored. */
    private fun restoreFileFor(model: String, mine: Boolean = false): File? {
        val d = dir ?: return null
        val safe = if (model.isEmpty()) "last"
                   else model.map { if (it.isLetterOrDigit()) it else '_' }.joinToString("")
        return File(d, (if (mine) "backup-" else "restore-") + safe + ".json")
    }

    /** A deliberate backup made before two slots existed lived in "restore-"
     *  with explicit:true — move it to its own slot so it is not lost. */
    private fun migrateRestorePoint(model: String) {
        val mine = restoreFileFor(model, true) ?: return
        if (mine.exists()) return
        val old = restoreFileFor(model) ?: return
        if (!old.exists()) return
        runCatching {
            if (JSONObject(old.readText()).optBoolean("explicit", false)) {
                old.copyTo(mine, overwrite = true); old.delete()
            }
        }
    }

    /** The backup a restore should use: the pilot's own when he has one. */
    fun chosenIsMine(model: String): Boolean {
        migrateRestorePoint(model)
        return restoreFileFor(model, true)?.exists() == true
    }

    /** Compare page (0.9.833): saved models, one row each, READ-ONLY. */
    fun compareModels(): org.json.JSONArray {
        val arr = org.json.JSONArray(); val seen = HashSet<String>()
        for (b in savedBackups()) {
            if (b.model.isEmpty() || !seen.add(b.model)) continue
            val mine = chosenIsMine(b.model)
            val at = savedBackups().firstOrNull { it.model == b.model && it.explicit == mine }?.atMs ?: b.atMs
            arr.put(JSONObject().put("model", b.model).put("savedAtMs", at).put("explicit", mine))
        }
        return arr
    }
    /** A saved model's MSP replies, key -> hex. */
    fun compareEntries(model: String): JSONObject {
        val out = JSONObject()
        val f = restoreFileFor(model, chosenIsMine(model)) ?: return out
        if (!f.exists()) return out
        runCatching {
            val es = JSONObject(f.readText()).getJSONObject("entries")
            for (k in es.keys()) {
                if (!k.startsWith("/api/msp?fn=")) continue
                val h = String(Base64.decode(es.getJSONObject(k).getString("b64"), Base64.NO_WRAP))
                if (h.length >= 2 && h.all { it.isLetterOrDigit() }) out.put(k, h.uppercase())
            }
        }
        return out
    }

    /** Does this model have BOTH kinds? */
    fun hasBothBackups(): Boolean {
        migrateRestorePoint(modelName)
        return restoreFileFor(modelName, true)?.exists() == true &&
               restoreFileFor(modelName)?.exists() == true
    }
    private val restoreKeyPrefixes = listOf(
        "/api/msp?fn=112&bank=", "/api/msp?fn=94&bank=",
        "/api/msp?fn=148&bank=", "/api/msp?fn=146&bank=", "/api/msp?fn=111&bank=",
        "/api/msp?fn=174&data=",   // mixer inputs (Travel extents)
        "/api/msp?fn=154&data=")   // RPM filter notches, per axis
    private fun isRestoreKey(k: String): Boolean {
        if (restoreKeyPrefixes.any { k.startsWith(it) }) return true
        if (k.startsWith("/app/declared/")) return true
        return banklessReadFns.any { k == "/api/msp?fn=$it" }
    }

    /** This airframe's OWN items — servos, mixer, motor & gear, board and
     *  sensor alignment, level trims, features, battery & meters, receiver
     *  wiring, ESC telemetry, telemetry sensors, blackbox, name, modes,
     *  per-channel failsafe values, RPM notches. A backup from ANOTHER model
     *  leaves these out on import: they belong to that helicopter's hardware.
     *  What transfers is the TUNE ONLY: PIDs, advanced PIDs, rates, governor
     *  (and its global settings), rescue, filters, auto-disarm delay, RSSI.
     *  The channel map, stick centre & travel, failsafe and the bank/rates
     *  selector slots were added to this list on 2026-09-17 - they are the
     *  other pilot's RADIO, not his tune. */
    val mechanicsKeyPrefixes = listOf(
        "/api/msp?fn=120", "/api/msp?fn=42", "/api/msp?fn=174&data=", "/api/msp?fn=172",
        "/api/msp?fn=131", "/api/msp?fn=38", "/api/msp?fn=126", "/api/msp?fn=96", "/api/msp?fn=240",
        "/api/msp?fn=36", "/api/msp?fn=32", "/api/msp?fn=56", "/api/msp?fn=40",
        "/api/msp?fn=44", "/api/msp?fn=123", "/api/msp?fn=73", "/api/msp?fn=80", "/api/msp?fn=10",
        "/api/msp?fn=34", "/api/msp?fn=238", "/api/msp?fn=77", "/api/msp?fn=154&data=",
        // The pilot's radio, not the tune (2026-09-16 review): channel map,
        // RSSI channel, RX config, and the bank/rates selector slots.
        "/api/msp?fn=64", "/api/msp?fn=66", "/api/msp?fn=75",
        "/app/declared/adj30", "/app/declared/adj31", "/app/declared/adj32", "/app/declared/adj33", "/app/declared/adj34", "/app/declared/adj35",
        "/app/declared/adj36", "/app/declared/adj37", "/app/declared/adj38", "/app/declared/adj39", "/app/declared/adj40", "/app/declared/adj41")
    fun isMechanicsKey(k: String): Boolean = mechanicsKeyPrefixes.any { p ->
        if (p.endsWith("=")) k.startsWith(p) else (k == p || k.startsWith("$p&"))
    }

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

    /** Rotorflight's own ceiling (upstream common_pre.h). Nothing walks past it. */
    const val MAX_BANKS = 6

    /** How many banks this flight controller HAS - bytes 24 and 26 of the
     *  same reply (0.9.742). Rotorflight builds the counts from flash size,
     *  so they can differ: >256 kB gives 6 PID and 6 rate banks, >128 kB
     *  gives 3 PID but still 6 rate. The sweep used to walk 0..3 flat, so a
     *  full-size board's banks 5 and 6 were never backed up and never
     *  restored - silently, with the progress bar reading 100 %. Falls back
     *  to 4 (what the sweep always did) when the reply is junk. */
    fun fcBankCounts(statusHex: String): Pair<Int, Int> {
        val h = statusHex.uppercase()
        if (h.length < 54) return Pair(4, 4)
        fun byte(i: Int) = h.substring(2 * i, 2 * i + 2).toIntOrNull(16)
        val pc = byte(24) ?: return Pair(4, 4)
        val rc = byte(26) ?: return Pair(4, 4)
        if (pc !in 1..8 || rc !in 1..8) return Pair(4, 4)
        return Pair(pc, rc)
    }

    /** Freeze the tuning reads currently in the rolling cache. explicit = the
     *  pilot's own "Back up" (or an import): STICKY — the automatic freeze at
     *  connection never replaces it (review 2026-09-04: it did, so a deliberate
     *  backup lived only until the next battery). Returns false when nothing
     *  was written. */
    @Synchronized
    fun snapshotRestorePoint(explicit: Boolean = false): Boolean {
        migrateRestorePoint(modelName)
        // Each kind has its own slot, so the automatic copy stays fresh
        // without ever threatening the one the pilot made.
        val f = restoreFileFor(modelName, explicit) ?: return false
        val keep = entries.filterKeys { isRestoreKey(it) }
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

    fun restorePointAtMs(mine: Boolean? = null): Long {
        val f = restoreFileFor(modelName, mine ?: chosenIsMine(modelName)) ?: return 0
        if (!f.exists()) return 0
        return runCatching { JSONObject(f.readText()).optLong("savedAtMs", 0) }.getOrDefault(0)
    }

    /** Was the current restore point a deliberate backup (or an import)? */
    fun restorePointIsExplicit(): Boolean = chosenIsMine(modelName)

    @Synchronized
    fun restoreItems(model: String? = null, mine: Boolean? = null): List<RestoreItem> {
        val out = ArrayList<RestoreItem>()
        val name = model ?: modelName
        val f = restoreFileFor(name, mine ?: chosenIsMine(name)) ?: return out
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
        // Walk every bank Rotorflight can have (0.9.742). hexAt() returns
        // null for a bank the file does not hold, so a 4-bank backup taken
        // before today restores exactly as it always did, and a 6-bank one
        // restores all six. Never ask the FC here - the file decides.
        for (b in 0 until MAX_BANKS) {
            hexAt("/api/msp?fn=112&bank=$b")?.let { out.add(RestoreItem(b, 202, 112, it, "PIDs bank ${b + 1}")) }
            hexAt("/api/msp?fn=94&bank=$b")?.let  { out.add(RestoreItem(b, 95,  94,  it, "advanced PIDs bank ${b + 1}")) }
            hexAt("/api/msp?fn=148&bank=$b")?.let { out.add(RestoreItem(b, 149, 148, it, "governor profile bank ${b + 1}")) }
            hexAt("/api/msp?fn=146&bank=$b")?.let { out.add(RestoreItem(b, 147, 146, it, "rescue bank ${b + 1}")) }
        }
        for (r in 0 until MAX_BANKS) {
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
        fun slice(s: String, off: Int, len: Int): String? =
            if (off < 0 || len <= 0 || s.length < off + len) null else s.substring(off, off + len)
        // Servos (bankless): stored fn-120 image = count(1B) + 16 B/servo;
        // fn 212 writes ONE servo (index + 16 B), verified as that servo's
        // 16 B in the fn-120 read-back.
        hexAt("/api/msp?fn=120")?.let { full ->
            val count = full.take(2).toIntOrNull(16) ?: 0
            if (count in 1..8) {
                val roles = listOf("swash 1", "swash 2", "swash 3", "TAIL", "5", "6", "7", "8")
                for (i in 0 until count) {
                    val s = slice(full, 2 + i * 32, 32) ?: break
                    out.add(RestoreItem(null, 212, 120, "%02X".format(i) + s,
                                        "servo ${i + 1} (${roles[i]})",
                                        chunkOffset = 2 + i * 32, chunkHex = s))
                }
            }
        }
        // Mixer rules (172 → 173, one rule per write: index + 7 B).
        hexAt("/api/msp?fn=172")?.let { full ->
            for (i in 0 until full.length / 14) {
                val s = slice(full, i * 14, 14) ?: break
                out.add(RestoreItem(null, 173, 172, "%02X".format(i) + s, "mixer rule ${i + 1}",
                                    chunkOffset = i * 14, chunkHex = s))
            }
        }
        // Motor & gear ratio: 222 takes the 131 reply WITHOUT byte 6 (motor
        // count) — exactly what the Gear ratio page writes; needs an FC
        // restart afterwards (the runner reboots after the EEPROM save).
        hexAt("/api/msp?fn=131")?.let { full ->
            if (full.length >= 58) {
                val w = full.take(12) + full.drop(14).take(44)
                out.add(RestoreItem(null, 222, 131, w, "motor & gear ratio", verifyHex = full))
            }
        }
        // Blackbox: 81 takes the 80 reply WITHOUT byte 0 (the 'supported' flag).
        hexAt("/api/msp?fn=80")?.let { full ->
            if (full.length >= 26) out.add(RestoreItem(null, 81, 80, full.drop(2), "blackbox setup", verifyHex = full))
        }
        // The verbatim items.
        for ((readFn, writeFn, label) in simpleItems) {
            hexAt("/api/msp?fn=$readFn")?.let {
                if (readFn == 73) {
                    // Telemetry: a backup holding an EMPTY sensor list (the 2026-09-03 fault, caught in a
                    // backup) must not be put back — the FC's own list stays; the receiver refuses such a
                    // write anyway. The link speed is live (liveHexRange).
                    if (telemImageGood(it)) out.add(RestoreItem(null, writeFn, readFn, it, label, liveHexRange = 16 until 24))
                } else out.add(RestoreItem(null, writeFn, readFn, it, label))
            }
        }
        // RPM filter notches (154 per axis → 155): axis byte + the axis image.
        for ((a, name) in listOf(0 to "roll", 1 to "pitch", 2 to "yaw")) {
            val key = "%02X".format(a)
            hexAt("/api/msp?fn=154&data=$key")?.let {
                out.add(RestoreItem(null, 155, 154, key + it, "RPM notches — $name", readData = key, verifyHex = it))
            }
        }
        // Voltage (56 → 57) and current (40 → 41) meters: the reply is a
        // count then frames [len, id, type, values…] — 8 bytes on the wire
        // for a voltage meter (scale, divider, divmul), 7 for a current
        // meter (scale, offset); each write is id + values, verified as the
        // values in the frame.
        for ((fns, frameLen, name) in listOf(Triple(56 to 57, 8, "voltage meter"), Triple(40 to 41, 7, "current meter"))) {
            val full = hexAt("/api/msp?fn=${fns.first}") ?: continue
            val n = full.take(2).toIntOrNull(16) ?: continue
            if (n !in 1..4) continue
            for (i in 0 until n) {
                val f = 2 + i * frameLen * 2
                val id = slice(full, f + 2, 2) ?: break
                val vals = slice(full, f + 6, (frameLen - 3) * 2) ?: break
                out.add(RestoreItem(null, fns.second, fns.first, id + vals, "$name ${i + 1}",
                                    chunkOffset = f + 6, chunkHex = vals))
            }
        }
        // Modes / arming switch (34 + 238 → 35, one slot per write: index,
        // box, channel, start, end, logic, link). A slot is skipped only when
        // both images already match; the 238 image is verified whole at the
        // end (the 34 read-back verifies each slot's range).
        val ranges = hexAt("/api/msp?fn=34")
        val extra = hexAt("/api/msp?fn=238")
        val nModes = extra?.take(2)?.toIntOrNull(16) ?: 0
        if (ranges != null && extra != null && nModes in 1..32 && ranges.length >= nModes * 8 && extra.length >= 2 + nModes * 6) {
            for (i in 0 until nModes) {
                val r = slice(ranges, i * 8, 8) ?: break
                val x = slice(extra, 2 + i * 6 + 2, 4) ?: break
                out.add(RestoreItem(null, 35, 34, "%02X".format(i) + r + x, "mode slot ${i + 1}",
                                    chunkOffset = i * 8, chunkHex = r,
                                    extraFn = 238, extraOffset = 2 + i * 6 + 2, extraHex = x))
            }
            out.add(RestoreItem(null, 0, 238, extra, "mode logic & links"))
        }
        // Per-channel failsafe values (77 → 78: index + mode + value).
        hexAt("/api/msp?fn=77")?.let { full ->
            for (i in 0 until minOf(full.length / 6, 18)) {
                val s = slice(full, i * 6, 6) ?: break
                out.add(RestoreItem(null, 78, 77, "%02X".format(i) + s, "failsafe value ch${i + 1}",
                                    chunkOffset = i * 6, chunkHex = s))
            }
        }
        // Declared items (Malcolm 2026-08-30): write-only settings the FC can't
        // read back — the bank/rates selector adjustment ranges (MSP 53).
        // readFn 0 = no read-back possible.
        for ((k, v) in frozen) {
            if (!k.startsWith("/app/declared/adj")) continue
            if (v.length < 4 || !v.all { it.isDigit() || it in 'a'..'f' || it in 'A'..'F' }) continue
            // The live selector slots are adj30 (bank) and adj36 (rates);
            // 40/41 are legacy and cleared (rotorflight-txchannels.html).
            val label = when { k.endsWith("adj30") -> "bank selector switch"
                               k.endsWith("adj36") -> "rates selector switch"
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
        // A declared item belongs in the backup that will actually be restored.
        val f = restoreFileFor(modelName, chosenIsMine(modelName)) ?: return
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
        restoreFileFor(modelName, chosenIsMine(modelName))?.takeIf { it.exists() }?.let { f ->
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
        // Sending yourself a backup means the one you made, when you have one.
        val f = restoreFileFor(modelName, chosenIsMine(modelName))?.takeIf { it.exists() } ?: return null
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
                if (!sameModel && isMechanicsKey(k)) return@forEach
                val v = es.optJSONObject(k) ?: return@forEach
                if (!v.has("b64")) return@forEach
                keep.put(k, v)
            }
            if (keep.length() == 0) return ImportResult(false, fileModel, 0, false)
            // An imported file is the pilot's own backup.
            val f = restoreFileFor(forModel, true) ?: return ImportResult(false, fileModel, 0, false)
            val out = JSONObject().put("model", forModel).put("savedAtMs", System.currentTimeMillis())
                .put("explicit", true).put("entries", keep)
            f.writeText(out.toString())
            ImportResult(true, fileModel, keep.length(), sameModel)
        }.getOrDefault(ImportResult(false, "", 0, false))
    }

    private fun load() {
        // REPAIR (0.9.837): a review saved with another model's state.json
        // inside (see record) gets its own name back, so it opens as itself.
        // The next connection to that model refreshes the rest.
        dir?.listFiles { f -> f.name.startsWith("session-") }?.forEach { f ->
            runCatching {
                val root = JSONObject(f.readText())
                val model = root.optString("model", "")
                val es = root.getJSONObject("entries")
                val st = es.optJSONObject("/api/state.json") ?: return@runCatching
                val body = Base64.decode(st.getString("b64"), Base64.NO_WRAP)
                val name = stateName(body) ?: return@runCatching
                if (model.isEmpty() || name == model) return@runCatching
                val obj = JSONObject(String(body))
                obj.getJSONObject("info").put("name", model)
                st.put("b64", Base64.encodeToString(obj.toString().toByteArray(), Base64.NO_WRAP))
                f.writeText(root.toString())
            }
        }
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
