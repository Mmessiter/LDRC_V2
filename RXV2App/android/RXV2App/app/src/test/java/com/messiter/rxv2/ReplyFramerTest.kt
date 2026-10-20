// LockDownRadioControl — RXV2App (Android)  ::  ReplyFramerTest.kt
//
// The Bluetooth reply framing, packet by packet, including the shapes a
// real link produced (apps 5.204, 20 Oct 2026). Run with
//   JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew testDebugUnitTest
package com.messiter.rxv2

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReplyFramerTest {
    private fun b(s: String) = s.toByteArray(Charsets.UTF_8)
    private fun hdr(id: Int, len: Int, code: Int = 200, type: String = "application/json") = "R$code|$type|$len|#$id\n"
    private fun feed(f: ReplyFramer, waiting: Int, vararg packets: ByteArray): List<ReplyFramer.Event> {
        val ev = ArrayList<ReplyFramer.Event>()
        for (p in packets) f.feed(p, waiting, ev)
        return ev
    }
    private fun done(ev: List<ReplyFramer.Event>): ReplyFramer.Reply {
        val d = ev.filterIsInstance<ReplyFramer.Event.Done>()
        assertEquals("exactly one Done in $ev", 1, d.size)
        return d[0].reply
    }
    private fun kinds(ev: List<ReplyFramer.Event>) = ev.joinToString(",") { it.javaClass.simpleName }

    @Test fun onePacketReply() {
        val ev = feed(ReplyFramer(), 7, b(hdr(7, 11) + "{\"ok\":true}"))
        assertEquals("Done", kinds(ev))
        val r = done(ev)
        assertEquals(200, r.code); assertEquals("application/json", r.contentType)
        assertEquals("", r.location); assertEquals("{\"ok\":true}", String(r.body))
    }

    @Test fun headerThenBodyPackets() {
        val body = "{\"active\":true,\"got\":123456,\"size\":1593456,\"error\":\"\"}"
        val ev = feed(ReplyFramer(), 7, b(hdr(7, body.length)), b(body.substring(0, 20)), b(body.substring(20)))
        assertEquals("Done", kinds(ev))
        assertEquals(body, String(done(ev).body))
    }

    @Test fun streamFramesBeforeTheHeader() {
        val ev = feed(ReplyFramer(), 7, b("S|1500,1500,1000|3\n"), b("S|1501,1500,1000|4\n" + hdr(7, 2)), b("{}"))
        assertEquals("Stream,Stream,Done", kinds(ev))
        assertEquals("S|1500,1500,1000|3", (ev[0] as ReplyFramer.Event.Stream).line)
        assertEquals("{}", String(done(ev).body))
    }

    @Test fun staleReplySwallowedThenOurs() {
        val ev = feed(ReplyFramer(), 7, b(hdr(6, 11) + "{\"ok\":true}"), b(hdr(7, 2) + "{}"))
        assertEquals("StaleDropped,Done", kinds(ev))
        assertEquals(6, (ev[0] as ReplyFramer.Event.StaleDropped).id)
        assertEquals("{}", String(done(ev).body))
    }

    @Test fun staleReplyAndOursInOnePacket() {
        val ev = feed(ReplyFramer(), 7, b(hdr(6, 2) + "{}" + hdr(7, 3) + "{a}"))
        assertEquals("StaleDropped,Done", kinds(ev))
        assertEquals("{a}", String(done(ev).body))
    }

    @Test fun staleHeaderCutShortByOurHeader() {
        // The receiver dropped the stale body when our request reached it (0.9.746 shape).
        val ev = feed(ReplyFramer(), 7, b(hdr(6, 55)), b(hdr(7, 2)), b("{}"))
        assertEquals("Resynced,Done", kinds(ev))
        assertEquals("{}", String(done(ev).body))
    }

    @Test fun duplicateHeaderIsNotABody() {
        // 20 Oct 2026: the page got "R200|application/json|55|#7\n{..." as the body of /api/bleota/status.
        val body = "{\"active\":true,\"got\":123456,\"size\":1593456,\"error\":\"\"}"
        val ev = feed(ReplyFramer(), 7, b(hdr(7, body.length)), b(hdr(7, body.length)), b(body))
        assertEquals("Resynced,Done", kinds(ev))
        assertEquals(body, String(done(ev).body))
    }

    @Test fun droppedBodyThenAFreshReply() {
        val ev = feed(ReplyFramer(), 7, b(hdr(7, 55)), b(hdr(7, 2)), b("{}"))
        assertEquals("Resynced,Done", kinds(ev))
        assertEquals("{}", String(done(ev).body))
    }

    @Test fun junkWithoutNewlineBeforeAHeaderPacket() {
        // Leftover chunks of an abandoned reply (compact JSON has no newline) then our header:
        // before, the junk and the header shared one line and the header was lost with it.
        val ev = feed(ReplyFramer(), 7, b("\"size\":1593456,\"error\":\"\"}"), b("more junk"), b(hdr(7, 2)), b("{}"))
        assertEquals("Resynced,Done", kinds(ev))
        assertEquals("{}", String(done(ev).body))
    }

    @Test fun junkLinesBeforeAHeaderInTheSamePacket() {
        val ev = feed(ReplyFramer(), 7, b("xyz\nabc\n" + hdr(7, 2) + "{}"))
        assertEquals("Done", kinds(ev))
        assertEquals("{}", String(done(ev).body))
    }

    @Test fun bodyStartingWithRIsStillABody() {
        val body = "Rotorflight 4.4.0 diff all\nR123|not|a|header"
        val ev = feed(ReplyFramer(), 7, b(hdr(7, body.length, type = "text/plain")), b(body.substring(0, 10)), b(body.substring(10)))
        assertEquals("Done", kinds(ev))
        assertEquals(body, String(done(ev).body))
    }

    @Test fun bodyPacketThatOnlyLooksHeaderish() {
        // "R123|not|a|header" has no newline, "R12|x|y\n" has a bad length: neither is a header.
        val ev = feed(ReplyFramer(), 7, b(hdr(7, 25)), b("R123|not|a|header"), b("R12|x|y\n"))
        assertEquals("Done", kinds(ev))
        assertEquals("R123|not|a|headerR12|x|y\n", String(done(ev).body))
    }

    @Test fun replyWithNoIdIsOurs() {
        val ev = feed(ReplyFramer(), 7, b("R200|text/plain|2|\nok"))
        assertEquals("Done", kinds(ev))
        assertEquals("ok", String(done(ev).body))
    }

    @Test fun redirectKeepsItsLocation() {
        val ev = feed(ReplyFramer(), 7, b("R303|text/plain|0|/index.html\n"))
        assertEquals("Done", kinds(ev))
        val r = done(ev)
        assertEquals(303, r.code); assertEquals("/index.html", r.location); assertEquals(0, r.body.size)
    }

    @Test fun rawBatchTreatsAnyIdAsStale() {
        val ev = feed(ReplyFramer(), 0, b(hdr(7, 2) + "{}"))
        assertEquals("StaleDropped", kinds(ev))
    }

    @Test fun extraBytesAfterTheBodyAreDropped() {
        val f = ReplyFramer()
        val ev = feed(f, 7, b(hdr(7, 2) + "{}junk"))
        assertEquals("Done", kinds(ev))
        assertEquals("{}", String(done(ev).body))
        assertEquals(-1, f.expected)
        // the next request starts clean
        val ev2 = feed(f, 8, b(hdr(8, 2) + "[]"))
        assertEquals("Done", kinds(ev2)); assertEquals("[]", String(done(ev2).body))
    }

    @Test fun endlessJunkIsBad() {
        val f = ReplyFramer()
        val ev = ArrayList<ReplyFramer.Event>()
        val junk = ByteArray(1000) { 'x'.code.toByte() }
        for (i in 0 until 40) f.feed(junk, 7, ev)
        assertTrue("Bad expected in $ev", ev.any { it is ReplyFramer.Event.Bad })
        assertEquals(-1, f.expected)
    }

    @Test fun resetForgetsEverything() {
        val f = ReplyFramer()
        feed(f, 7, b(hdr(7, 55)), b("half a body"))
        assertEquals(55, f.expected)
        f.reset()
        assertEquals(-1, f.expected)
        val ev = feed(f, 8, b(hdr(8, 2) + "{}"))
        assertEquals("Done", kinds(ev))
    }
}
