// LockDownRadioControl — RXV2App (Android)  ::  ReplyFramer.kt
//
// Reassembles the receiver's replies from Bluetooth notification packets.
// Pure Kotlin (no Android types) so it runs under a plain JUnit test —
// see app/src/test/.../ReplyFramerTest.kt.
//
// The firmware's framing (RXV2/src/BleConfig.h): a reply is one notify
// carrying the header line "R<code>|<type>|<len>|<loc>\n", then raw body
// bytes in notifies of up to 240 bytes until <len> have arrived. Between
// replies the receiver may push "S|us0,..,us15|age\n" channel frames. The
// location slot carries "#<id>" — the request's X-Req number — on a reply
// that is not a redirect (0.9.746).
//
// Two rules make this robust to whatever the link does (apps 5.204, 20 Oct
// 2026 — Malcolm's Android Bluetooth install failed with "Value
// R200|application ... cannot be converted to JSONObject": a reply HEADER
// had been handed to the page as a BODY):
//
//  1. A header is always its own packet, and a body packet never starts
//     with "R<code>|<type>|<len>|...\n". So a packet that parses as a header
//     IS a header — whatever state we were in. Arriving while a body was
//     still due, it means the receiver abandoned that reply (its body was
//     dropped when a new request reached it mid-pump) or sent the header
//     twice: the half reply is dropped and this header starts afresh.
//     Arriving while junk was piling up in the header hunt (leftovers of a
//     reply we gave up on), the junk is dropped and the header read whole;
//     before this the junk and the header shared one line and the header
//     was lost with it, so the request timed out.
//  2. A header whose id is not the one we are waiting for belongs to a
//     request we gave up on: its body is swallowed and dropped, never
//     handed to the request now waiting (0.9.746, unchanged).

package com.messiter.rxv2

class ReplyFramer {

    class Reply(val code: Int, val contentType: String, val location: String, val body: ByteArray)

    sealed class Event {
        /** A pushed channel frame ("S|...") — out of band, hand it to the page. */
        class Stream(val line: String) : Event()
        /** The reply for the request we are waiting for. */
        class Done(val reply: Reply) : Event()
        /** A reply for a request we gave up on was swallowed whole (id in the header, or null). */
        class StaleDropped(val id: Int?) : Event()
        /** The framer threw away bytes to start again on a header; the request is still waiting. */
        class Resynced(val why: String) : Event()
        /** Framing has gone wrong beyond repair for this request: the caller fails it. */
        class Bad(val why: String) : Event()
    }

    private var header = ByteArrayOut()
    private var body = ByteArrayOut()
    private var discarded = 0
    /** ≥ 0 while body bytes are being collected (the declared length). */
    var expected = -1
        private set
    /** True while swallowing a reply for a request we gave up on. */
    var stale = false
        private set
    private var code = 0
    private var type = ""
    private var location = ""
    private var staleId: Int? = null

    companion object {
        const val LIMIT = 32768

        /** Parsed first line of a packet when it is a reply header. */
        class Header(val code: Int, val type: String, val len: Int, val loc: String, val lineEnd: Int)

        fun parseHeaderLine(line: String): Header? {
            if (!line.startsWith("R")) return null
            val parts = line.substring(1).split("|", limit = 4)
            val code = parts.getOrNull(0)?.toIntOrNull() ?: return null
            val len = parts.getOrNull(2)?.toIntOrNull() ?: return null
            if (parts.size < 3 || code !in 100..599 || len < 0) return null
            return Header(code, parts[1], len, if (parts.size > 3) parts[3] else "", -1)
        }

        /** "R<code>|<type>|<len>|<loc>\n" at the start of a packet? */
        fun headerAtStart(d: ByteArray, len: Int = d.size): Header? {
            var nl = -1
            for (i in 0 until len) if (d[i] == '\n'.code.toByte()) { nl = i; break }
            if (nl < 0) return null
            val h = parseHeaderLine(String(d, 0, nl, Charsets.UTF_8)) ?: return null
            return Header(h.code, h.type, h.len, h.loc, nl)
        }

        fun requestId(loc: String): Int? =
            if (loc.startsWith("#")) loc.substring(1).toIntOrNull() else null
    }

    /** Forget everything: a new request is about to be sent. */
    fun reset() {
        header = ByteArrayOut(); body = ByteArrayOut()
        expected = -1; discarded = 0; stale = false; staleId = null
    }

    /**
     * Feed one notification packet. `waitingFor` is the id of the request in
     * flight (0 for one that carries none, e.g. a raw OTA batch). Events are
     * appended in order; after a Bad or a Done the framer is reset.
     */
    fun feed(data: ByteArray, waitingFor: Int, events: MutableList<Event>) {
        if (expected < 0) {
            // Hunting for the header line.
            if (header.size() > 0) {
                val h = headerAtStart(data)
                if (h != null) {
                    // Rule 1: a packet that is a header IS a header. Whatever
                    // was piling up before it (leftovers of an abandoned reply)
                    // would have swallowed its line — drop the junk instead.
                    discarded += header.size()
                    header = ByteArrayOut()
                    events.add(Event.Resynced("${discarded} stale bytes before a header"))
                }
            }
            header.append(data)
            while (true) {
                val nl = header.indexOf('\n'.code.toByte())
                if (nl < 0) {
                    if (header.size() + discarded > LIMIT) {
                        events.add(Event.Bad("no reply header in $LIMIT bytes")); reset()
                    }
                    return
                }
                val line = String(header.bytes(), 0, nl, Charsets.UTF_8)
                if (line.startsWith("S|")) {
                    events.add(Event.Stream(line))
                    header = header.drop(nl + 1); continue
                }
                val h = parseHeaderLine(line)
                if (h != null) {
                    // Rule 2: echoed request id. A reply for a request we gave
                    // up on is consumed and dropped, never handed to the one
                    // now waiting (0.9.746).
                    val rid = requestId(h.loc)
                    stale = rid != null && rid != waitingFor
                    staleId = rid
                    code = h.code; type = h.type; expected = h.len
                    location = if (h.loc.startsWith("#")) "" else h.loc
                    body = ByteArrayOut(); body.append(header.bytes(), nl + 1, header.size() - (nl + 1))
                    header = ByteArrayOut()
                    break
                }
                discarded += nl + 1
                header = header.drop(nl + 1)
                if (discarded > LIMIT) {
                    events.add(Event.Bad("no reply header in $LIMIT bytes")); reset(); return
                }
            }
        } else if (headerAtStart(data) != null) {
            // Rule 1, mid-body: the receiver started another reply before this
            // one's body was complete. Ours or stale, the half reply is useless;
            // the packet in hand is a header and is read as one.
            val why = if (stale) "stale reply cut short by a header"
                      else "a header arrived where ${expected - body.size()} body bytes were due"
            val keepDiscarded = discarded
            reset(); discarded = keepDiscarded
            events.add(Event.Resynced(why))
            feed(data, waitingFor, events)
            return
        } else {
            body.append(data)
        }
        if (expected in 0..body.size()) {
            if (stale) {
                // Swallowed the whole stale reply — back to hunting for ours.
                val all = body.bytes()
                val rest = all.copyOfRange(expected, body.size())
                val id = staleId
                val keepDiscarded = discarded
                reset(); discarded = keepDiscarded
                events.add(Event.StaleDropped(id))
                if (rest.isNotEmpty()) feed(rest, waitingFor, events)
                return
            }
            val reply = Reply(code, type, location, body.bytes().copyOfRange(0, expected))
            reset()
            events.add(Event.Done(reply))
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
