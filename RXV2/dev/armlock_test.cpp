// The lock on an armed model (0.9.923) - run by dev/armlock_test.sh against the REAL blocks of src/1Defs.h
// (ARMLOCK-BEGIN .. END, and LINK-AGES for the time after which a quiet transmitter is taken to be off): the rule,
// what the app is shown, the arm switch followed, the question and its bounds, and whole mornings played through
// millisecond by millisecond.
// Malcolm, 11 Nov 2026, Test1: "frequently the iOS app has warned me that arming is on when it was not" - the
// transmitter model arms on channel 16, that board's Rotorflight on channel 6, where the model keeps a switch high.
// The three cases of the independent review of the same morning are here too: the switch flicked off and on while a
// question was out, how long loop() may be held at a real arming, and a confirmed arming through a gap in the link.
#include <cstdio>
#include <cstdint>
#include <functional>
#include LINK_BLOCK
#include ARMLOCK_BLOCK
static int fails = 0;
static const char* vname(ArmVerdict v) { return v == ARM_NOT ? "not armed" : v == ARM_FC_SAYS ? "FC says armed" : v == ARM_SWITCH_SAYS ? "switch says armed" : "ask the FC"; }
static const char* lname(ArmLock l) {
    return l == ARMLOCK_OPEN ? "open" : l == ARMLOCK_FC ? "locked (FC)" : l == ARMLOCK_SWITCH ? "locked (switch)" : l == ARMLOCK_SETTLING ? "locked (settling)" : "locked (asking)";
}
static void expectV(const char* what, ArmVerdict got, ArmVerdict want) {
    if (got != want) fails++;
    printf("%s %-96s %s\n", got == want ? "PASS" : "FAIL", what, vname(got));
}
static void expectB(const char* what, bool got, bool want) {
    if (got != want) fails++;
    printf("%s %-96s %s\n", got == want ? "PASS" : "FAIL", what, got ? "yes" : "no");
}
static void expectL(const char* what, ArmLock got, ArmLock want) {
    if (got != want) fails++;
    printf("%s %-96s %s\n", got == want ? "PASS" : "FAIL", what, lname(got));
}
static void expectI(const char* what, int got, int want) {
    if (got != want) fails++;
    printf("%s %-96s %d\n", got == want ? "PASS" : "FAIL", what, got);
}
// fcAnswers, fcWordKnown, fcArmed, fcWordAgeMs, switchOn, switchOnForMs, fcArmedSinceSwitchOn
static ArmFacts F(bool ans, bool known, bool armed, uint32_t age, bool sw, uint32_t swFor, bool conf = false) {
    ArmFacts f; f.fcAnswers = ans; f.fcWordKnown = known; f.fcArmed = armed; f.fcWordAgeMs = age; f.switchOn = sw; f.switchOnForMs = swFor; f.fcArmedSinceSwitchOn = conf;
    return f;
}

// ---------------------------------------------------------------- a transmitter, a receiver, a flight controller and a phone, in time
struct Sim {
    uint32_t now = 100000;
    ArmSwitchTrack tr = { 0, false };
    ArmAsk   ask = { 0, 0 };
    bool     fcAnswers = true;                          // a flight controller is known here (fcInfo.detected)
    bool     fcDeaf = false;                            // ... but does not answer
    bool     word = false; uint32_t wordMs = 0;         // fcInfo.armed, fcInfo.armedMs
    std::function<bool(uint32_t)>     txOn      = [](uint32_t) { return true; };     // packets arrive
    std::function<bool(uint32_t)>     switchHigh = [](uint32_t) { return false; };   // what they say of the arming channel
    std::function<bool(uint32_t)>     fcIsArmed = [](uint32_t) { return false; };
    std::function<uint32_t(uint32_t)> replyMs   = [](uint32_t) { return 40u; };      // a question sent at t is answered this much later
    uint32_t lastPacketMs = 0; bool lastWordOn = false;  // rx.lastMillis, lastRxArmUs > 1500
    bool     qOut = false; uint32_t qSentMs = 0, qAnswerAt = 0;   // the one question the flight controller holds
    uint32_t asks = 0, asksWhileArmed = 0;
    bool     phone = false; uint32_t followLastMs = 0, movedAt = 0; bool lastSw = false;
    uint32_t held = 0, maxHeld = 0;                     // how long the last request held loop(), and the longest

    bool live() const { return lastPacketMs && now - lastPacketMs < 1000; }
    bool readsOn() const { return live() && lastWordOn; }                                    // armSwitchReadsOn()
    bool quietButLastOn() const {                                                            // armSwitchQuietButLastOn()
        if (!lastPacketMs || !lastWordOn) return false;
        const uint32_t q = now - lastPacketMs;
        return q >= 1000 && q < LINK_DEAD_MS;
    }
    void step() {                                       // one millisecond of the link and the output running: loop(), or a wait (keepLinkTick)
        if (txOn(now)) { lastPacketMs = now; lastWordOn = switchHigh(now); }
        if (qAnswerAt && now >= qAnswerAt) { qAnswerAt = 0; qOut = false; word = fcIsArmed(now); wordMs = now; }   // the digest
        if (qOut && now - qSentMs >= 500) qOut = false;                                      // MSP_PROBE_REPLY_WAIT_MS
        armSwitchStep(tr, readsOn(), quietButLastOn(), word, wordMs, now);
    }
    bool sendQuestion() {
        asks++; if (fcIsArmed(now)) asksWhileArmed++;
        qOut = true; qSentMs = now;
        if (!fcDeaf && !qAnswerAt) qAnswerAt = now + replyMs(now);                           // (a second one behind an unanswered one is thrown away)
        return true;
    }
    void follow() {                                     // the phone's follow, bankFollowTick: only in loop(), only watched, stops once the FC says armed
        if (!phone || !fcAnswers || word || !live()) return;
        const bool sw = lastWordOn;
        if (sw != lastSw) { lastSw = sw; if (!movedAt) movedAt = now; }                      // a switch channel moved: asked 120 ms later
        const uint32_t gap = movedAt ? 120 : tr.onSinceMs ? 1000 : 2000;
        if (now - (movedAt ? movedAt : followLastMs) < gap || now - followLastMs < 250) return;
        if (qOut) return;
        followLastMs = now; movedAt = 0;
        sendQuestion();
    }
    void advance(uint32_t ms) { for (uint32_t i = 0; i < ms; ++i) { now++; step(); follow(); } }
    ArmFacts facts() { armSwitchStep(tr, readsOn(), quietButLastOn(), word, wordMs, now); return armFactsFrom(tr, fcAnswers, word, wordMs, now); }
    struct IO {
        Sim* s;
        uint32_t nowMs() { return s->now; }
        uint32_t wordMs() { return s->wordMs; }
        bool outstanding() { return s->qOut; }
        bool send() { return s->sendQuestion(); }
        void pump() { s->now++; s->step(); }
    };
    ArmLock gate() {                                    // a page's request: WebPages.h armLockNow()
        const uint32_t t0 = now;
        IO io{ this };
        const ArmLock l = armLockWaiting(
            [this]() { return facts(); },
            [this, &io](bool renewing) -> int { return armAsk(ask, io, renewing); },
            [this](uint32_t ms) { for (uint32_t i = 0; i < ms; ++i) { now++; step(); } });
        held = now - t0; if (held > maxHeld) maxHeld = held;
        return l;
    }
    ArmLock ruleNow() {                                 // the rule at this very millisecond, nobody waiting and nobody asked
        return armLockFrom([this]() { return facts(); }, [](bool) -> int { return -1; });
    }
    bool shown() { return armShown(facts()); }
};

int main() {
    // ------------------------------------------------------------------ the numbers
    expectB("the flight controller's 'armed' counts 5 s, as every gate has had it", FC_ARMED_HOLD_MS == 5000, true);
    expectB("'fresh' for what the app is shown is the radios' 2.5 s (fcArmedWordFresh, 0.9.917)", FC_WORD_FRESH_MS == 2500, true);
#ifdef RADIOS_FRESH_MS
    expectB("... and fcArmedWordFresh() in 1Defs.h still says that number", RADIOS_FRESH_MS == FC_WORD_FRESH_MS, true);
#endif
    expectB("its 'not armed' lifts the lock for less long than the radios call it fresh", FC_NOT_ARMED_MS < FC_WORD_FRESH_MS, true);
    expectB("the settle time is 0.3 s: the first answer to a switch going on (120 ms + the reply) never counts", ARM_SWITCH_SETTLE_MS == 300, true);
    expectB("at an arming loop() is held 0.7 s at the very most (0.3 s + the first question's 0.4 s)", ARM_SWITCH_SETTLE_MS + FC_ASK_FIRST_MS <= 700, true);
    expectB("a question is never given up as deaf before its answer could come (1.5 s)", FC_ASK_ANSWER_MS >= FC_ASK_RENEW_MS && FC_ASK_ANSWER_MS >= 1500, true);
    expectB("a confirmed arming is kept through a radio gap past the 3 s the held channels go out, to 'transmitter off' and no longer",
            LINK_DEAD_MS > OUTPUT_FAILSAFE_MS && LINK_DEAD_MS <= OUTPUT_FAILSAFE_MS + 1500, true);

    // ------------------------------------------------------------------ the rule
    expectV("nothing known, switch off", armVerdict(F(false, false, false, 0xFFFFFFFFu, false, 0)), ARM_NOT);
    expectV("the FC said armed 1 s ago, switch off: locked", armVerdict(F(true, true, true, 1000, false, 0)), ARM_FC_SAYS);
    expectV("... 4.999 s ago", armVerdict(F(true, true, true, 4999, false, 0)), ARM_FC_SAYS);
    expectV("... 5 s ago and the switch off: not armed", armVerdict(F(true, true, true, 5000, false, 0)), ARM_NOT);
    expectV("no flight controller, switch on 10 ms: the switch says armed (as before 0.9.923)", armVerdict(F(false, false, false, 0xFFFFFFFFu, true, 10)), ARM_SWITCH_SAYS);
    expectV("no flight controller, switch on an hour: the switch says armed", armVerdict(F(false, false, false, 0xFFFFFFFFu, true, 3600000)), ARM_SWITCH_SAYS);
    expectV("a flight controller lost (not answering), its old 'not armed' 1 s old: the switch says armed", armVerdict(F(false, true, false, 1000, true, 60000)), ARM_SWITCH_SAYS);
    expectV("11 Nov, Test1: switch on a minute, the FC said 'not armed' 0.8 s ago: NOT armed", armVerdict(F(true, true, false, 800, true, 60000)), ARM_NOT);
    expectV("... 1.499 s ago: still not armed", armVerdict(F(true, true, false, 1499, true, 60000)), ARM_NOT);
    expectV("... 1.5 s ago: ask it again", armVerdict(F(true, true, false, 1500, true, 60000)), ARM_ASK_FC);
    expectV("switch on 100 ms, 'not armed' said 50 ms ago: locked, nobody asked (a model being armed)", armVerdict(F(true, true, false, 50, true, 100)), ARM_SWITCH_SAYS);
    expectV("switch on 299 ms: still locked without asking", armVerdict(F(true, true, false, 100, true, 299)), ARM_SWITCH_SAYS);
    expectV("switch on 700 ms, 'not armed' said 170 ms after it went on (the follow's first answer): it does not count - ask", armVerdict(F(true, true, false, 530, true, 700)), ARM_ASK_FC);
    expectV("switch on 700 ms, 'not armed' said 299 ms after it went on: ask", armVerdict(F(true, true, false, 401, true, 700)), ARM_ASK_FC);
    expectV("switch on 700 ms, 'not armed' said 300 ms after it went on: not armed", armVerdict(F(true, true, false, 400, true, 700)), ARM_NOT);
    expectV("'not armed' said BEFORE the switch went on (1 s old, switch on 600 ms): ask", armVerdict(F(true, true, false, 1000, true, 600)), ARM_ASK_FC);
    expectV("... (1.4 s old, switch on 501 ms): ask", armVerdict(F(true, true, false, 1400, true, 501)), ARM_ASK_FC);
    expectV("the FC has never said anything, switch on 2 s: ask", armVerdict(F(true, false, false, 0xFFFFFFFFu, true, 2000)), ARM_ASK_FC);
    expectV("a word of unknown age (wrapped clock), switch on 2 s: ask, never 'not armed'", armVerdict(F(true, true, false, 0xFFFFFFFFu, true, 2000)), ARM_ASK_FC);
    expectV("the FC said armed 6 s ago, before this switch-on: ask", armVerdict(F(true, true, true, 6000, true, 3000)), ARM_ASK_FC);
    expectV("in flight: it said armed after the switch went on, 20 minutes ago: locked, NOT asked again", armVerdict(F(true, true, true, 1200000, true, 1200100, true)), ARM_FC_SAYS);
    expectV("it disarmed itself in the air (fresh 'not armed') with the switch still on: stays locked", armVerdict(F(true, true, false, 300, true, 1200100, true)), ARM_FC_SAYS);
    expectV("no live link, the transmitter's last word ARMED, the FC said 'not armed' 0.1 s ago: not armed", armVerdict(F(true, true, false, 100, true, 0x7FFFFFFFu)), ARM_NOT);
    expectV("... and nothing fresh from the FC: ask", armVerdict(F(true, true, false, 9000, true, 0x7FFFFFFFu)), ARM_ASK_FC);

    // ------------------------------------------------------------------ what the app is shown
    expectB("shown: Test1 - switch on a minute, 'not armed' 0.8 s ago: no red banner", armShown(F(true, true, false, 800, true, 60000)), false);
    expectB("shown: ... 2.499 s ago: none", armShown(F(true, true, false, 2499, true, 60000)), false);
    expectB("shown: ... 2.5 s ago: ARMED, as the radios then take it (they go by the switch)", armShown(F(true, true, false, 2500, true, 60000)), true);
    expectB("shown: the FC says armed: ARMED", armShown(F(true, true, true, 100, true, 700, true)), true);
    expectB("shown: the FC said armed 4 s ago, switch off again: ARMED", armShown(F(true, true, true, 4000, false, 0)), true);
    expectB("shown: ... 5 s ago: not", armShown(F(true, true, true, 5000, false, 0)), false);
    expectB("shown: no flight controller, switch on 100 ms: not yet", armShown(F(false, false, false, 0xFFFFFFFFu, true, 100)), false);
    expectB("shown: no flight controller, switch on 299 ms: not yet", armShown(F(false, false, false, 0xFFFFFFFFu, true, 299)), false);
    expectB("shown: no flight controller, switch on 300 ms: ARMED", armShown(F(false, false, false, 0xFFFFFFFFu, true, 300)), true);
    expectB("shown: transmitter switched on beside the app, old word, switch on 50 ms: no flash", armShown(F(true, true, false, 10000, true, 50)), false);
    expectB("shown: confirmed in this arming, then a fresh 'not armed': still ARMED", armShown(F(true, true, false, 300, true, 60000, true)), true);
    expectB("shown: switch off, nothing fresh: not", armShown(F(true, true, false, 9000, false, 0)), false);

    // ------------------------------------------------------------------ the arm switch followed
    {
        ArmSwitchTrack t = { 0, false };
        armSwitchStep(t, false, false, false, 0, 5000);
        expectB("track: off = no moment", t.onSinceMs == 0 && !t.fcConfirmed, true);
        armSwitchStep(t, true, false, false, 4000, 6000);
        expectB("track: on at 6000", t.onSinceMs == 6000 && !t.fcConfirmed, true);
        armSwitchStep(t, true, false, false, 4000, 6500);
        expectB("track: still 6000 half a second later", t.onSinceMs == 6000, true);
        armSwitchStep(t, true, false, true, 5999, 6600);
        expectB("track: an 'armed' said just BEFORE it went on does not confirm this arming", t.fcConfirmed, false);
        armSwitchStep(t, false, true, true, 5999, 6650);
        expectB("track: the link quiet, NOT confirmed: no switch, as before (a transmitter switched off is not an arming)", t.onSinceMs == 0, true);
        armSwitchStep(t, true, false, true, 5999, 6660);
        armSwitchStep(t, true, false, true, 6700, 6700);
        expectB("track: on again at 6660, and an 'armed' said after that confirms it", t.onSinceMs == 6660 && t.fcConfirmed, true);
        armSwitchStep(t, false, true, true, 6700, 8000);
        expectB("track: the link quiet, CONFIRMED: kept - the model is flying on its held channels", t.onSinceMs == 6660 && t.fcConfirmed, true);
        armSwitchStep(t, true, false, true, 6700, 9500);
        expectB("track: the packets back, switch still on: the SAME arming, still confirmed", t.onSinceMs == 6660 && t.fcConfirmed, true);
        armSwitchStep(t, false, false, true, 6700, 20000);
        expectB("track: quiet for longer than 'transmitter off', or seen off on a live link: forgotten", t.onSinceMs == 0 && !t.fcConfirmed, true);
        armSwitchStep(t, true, false, true, 6700, 20300);
        expectB("track: on again = a new arming, the old 'armed' does not confirm it", t.onSinceMs == 20300 && !t.fcConfirmed, true);
        ArmSwitchTrack z = { 0, false };
        armSwitchStep(z, true, false, false, 0, 0);
        expectB("track: on at the very first millisecond is still 'on'", z.onSinceMs != 0, true);
        ArmSwitchTrack w = { 0, false };
        armSwitchStep(w, true, false, false, 0, 0xFFFFFF00u);
        armSwitchStep(w, true, false, true, 0x00000010u, 0x00000020u);      // the clock wrapped between the switch and the word
        expectB("track: across the 49-day clock wrap a later 'armed' still confirms", w.fcConfirmed, true);
    }

    // ------------------------------------------------------------------ the question, bounded
    {
        struct FakeIO {
            uint32_t now = 50000, word = 0, answerAt = 0, sends = 0, pumps = 0; bool out = false, lineFree = true;
            uint32_t nowMs() { return now; }
            uint32_t wordMs() { return word; }
            bool outstanding() { return out; }
            bool send() { if (!lineFree) return false; sends++; out = true; return true; }
            void pump() { now++; pumps++; if (answerAt && now >= answerAt) { word = now; answerAt = 0; out = false; } }
        };
        { FakeIO io; ArmAsk a = { 0, 0 }; io.answerAt = io.now + 40;
          expectI("ask: answered in 40 ms: a word came in", armAsk(a, io, false), 1);
          expectB("ask: ... after 40 ms of waiting, one question, nothing left out", io.pumps == 40 && io.sends == 1 && a.sentMs == 0, true); }
        { FakeIO io; ArmAsk a = { 0, 0 }; io.answerAt = io.now + 900;
          expectI("ask: the FIRST question of an arming, answer 0.9 s away: 'out, not answered yet'", armAsk(a, io, false), 0);
          expectB("ask: ... loop() was held 0.4 s and no longer", io.pumps == FC_ASK_FIRST_MS, true);
          const uint32_t p0 = io.pumps;
          io.now += 200;
          expectI("ask: asked again 0.2 s later: still out - nothing is sent behind it", armAsk(a, io, false), 0);
          expectB("ask: ... and nobody waited this time", io.pumps == p0 && io.sends == 1, true);
          io.now += 320; io.word = io.now; io.out = false;             // loop() collected the answer
          const uint32_t s0 = io.sends; io.answerAt = io.now + 30;
          expectI("ask: once loop() has collected the answer, a new question may go out", armAsk(a, io, false), 1);
          expectB("ask: ... one more question", io.sends == s0 + 1, true); }
        { FakeIO io; ArmAsk a = { 0, 0 }; io.answerAt = io.now + 900;
          expectI("ask: a RENEWING question, answer 0.9 s away: waited for, a word came in", armAsk(a, io, true), 1);
          expectB("ask: ... 0.9 s", io.pumps == 900, true); }
        { FakeIO io; ArmAsk a = { 0, 0 };                              // a flight controller that never answers
          expectI("ask: deaf: the first question is out, not answered", armAsk(a, io, false), 0);
          io.now += 600; io.out = false;
          expectI("ask: deaf: 1 s on, still 'out' - it is given 1.5 s", armAsk(a, io, false), 0);
          io.now += 600;
          const uint32_t p0 = io.pumps, s0 = io.sends;
          expectI("ask: deaf: after 1.5 s without an answer: it does not answer (-1)", armAsk(a, io, false), -1);
          io.now += 4000;
          expectI("ask: deaf: left alone for 5 s - not asked, nobody waits", armAsk(a, io, false), -1);
          expectB("ask: ... no question and no waiting in those 5 s", io.pumps == p0 && io.sends == s0, true);
          io.now += 1100;
          expectI("ask: deaf: after the 5 s it is asked once more", armAsk(a, io, false), 0);
          expectB("ask: ... one question", io.sends == s0 + 1, true); }
        { FakeIO io; ArmAsk a = { 0, 0 }; io.out = true; io.answerAt = io.now + 60;       // the follow's question is already out
          expectI("ask: somebody else's question is out and answered in 60 ms: its answer will do", armAsk(a, io, false), 1);
          expectB("ask: ... ours was never sent", io.sends == 0, true); }
        { FakeIO io; ArmAsk a = { 0, 0 }; io.out = true;                                  // somebody else's, never answered
          expectI("ask: somebody else's question out and unanswered when our time is up: nothing is sent behind it", armAsk(a, io, false), 0);
          expectB("ask: ... ours was not sent, and loop() was held 0.4 s at most", io.sends == 0 && io.pumps <= FC_ASK_FIRST_MS, true); }
        { FakeIO io; ArmAsk a = { 0, 0 }; io.lineFree = false;
          expectI("ask: the line is not free (the transmitter's own edit): it cannot be put (-1)", armAsk(a, io, false), -1); }
    }

    // ------------------------------------------------------------------ 11 Nov 2026, Test1, played through
    {
        Sim s; s.phone = true;
        s.switchHigh = [](uint32_t) { return true; };                 // channel 6 is high whenever the transmitter is on
        s.txOn = [](uint32_t t) { return t >= 169000; };              // ... and it comes on at 169 s
        s.fcIsArmed = [](uint32_t) { return false; };                 // Rotorflight never arms (its throttle channel is high)
        s.advance(68990);                                             // the phone alone, to just before
        expectL("Test1: before the transmitter is on", s.gate(), ARMLOCK_OPEN);
        s.advance(10 + 50);                                           // 50 ms after channel 6 went high
        expectL("Test1: 50 ms after the transmitter came on, the rule alone: locked, nobody asked (settling)", s.ruleNow(), ARMLOCK_SETTLING);
        expectB("Test1: ... and no red banner in that moment", s.shown(), false);
        {
            Sim q = s;                                                // a page's request at that very moment
            const uint32_t a0 = q.asks;
            expectL("Test1: a request 50 ms after: it waits out the 0.3 s, the FC is asked, says not armed - OPEN", q.gate(), ARMLOCK_OPEN);
            expectB("Test1: ... kept waiting no longer than 0.3 s and the answer", q.held <= ARM_SWITCH_SETTLE_MS + 40, true);
            expectB("Test1: ... with exactly one question, answered after the 0.3 s", q.asks == a0 + 1 && q.wordMs >= 169000 + ARM_SWITCH_SETTLE_MS, true);
        }
        s.advance(200);                                               // 250 ms: the follow's first answer (120 ms + 40) is in, but too early to count
        expectL("Test1: 250 ms after, the rule alone: still locked (settling) - the follow's first answer does not count", s.ruleNow(), ARMLOCK_SETTLING);
        s.advance(350);                                               // 600 ms
        const uint32_t asksBefore = s.asks;
        expectL("Test1: 600 ms after: the flight controller is asked, says not armed - OPEN", s.gate(), ARMLOCK_OPEN);
        expectB("Test1: ... that took exactly one question, and no waiting but for the answer", s.asks == asksBefore + 1 && s.held == 40, true);
        int locked = 0, banners = 0, n = 0; uint32_t gateAsks = 0;
        for (int i = 0; i < 600; ++i) {                               // five minutes of a page reading twice a second
            s.advance(500);
            const uint32_t a0 = s.asks;
            if (s.gate() != ARMLOCK_OPEN) locked++;
            gateAsks += s.asks - a0;
            if (s.shown()) banners++;
            n++;
        }
        expectB("Test1: five minutes on, a page reading twice a second: never locked (it was 'ARMED' every time)", locked == 0, true);
        expectB("Test1: ... and the red banner never shown", banners == 0, true);
        expectB("Test1: ... the phone's follow keeps the word fresh: the page itself asks hardly ever", gateAsks <= 5, true);
        printf("     (%d requests, %u questions by the page, %u in all)\n", n, (unsigned)gateAsks, (unsigned)s.asks);
        // and the transmitter switched off again, the page still reading
        const uint32_t offAt = s.now;
        s.txOn = [offAt](uint32_t t) { return t < offAt; };
        int lockedAfterOff = 0; const uint32_t a1 = s.asks;
        for (int i = 0; i < 40; ++i) { s.advance(250); if (s.now - offAt >= 1000 && s.gate() != ARMLOCK_OPEN) lockedAfterOff++; }
        expectB("Test1: the transmitter switched off: a second later no switch, no lock, and no question (as before)", lockedAfterOff == 0 && s.asks - a1 <= 1, true);
    }
    {   // the same model with nothing following for the phone (a page over WiFi that speaks MSP all the time holds the follow off)
        Sim s; s.phone = false;
        s.switchHigh = [](uint32_t t) { return t >= 101000; };
        s.advance(2000);
        int locked = 0; const uint32_t a0 = s.asks;
        for (int i = 0; i < 120; ++i) { s.advance(250); if (s.gate() != ARMLOCK_OPEN) locked++; }     // 30 s, four requests a second
        expectB("no follow at all, a page reading 4 times a second for 30 s: never locked", locked == 0, true);
        expectB("... and it asks the flight controller about every 1.5 s, not at every request", s.asks - a0 >= 15 && s.asks - a0 <= 22, true);
        printf("     (%u questions in 30 s)\n", (unsigned)(s.asks - a0));
    }
    {   // the same model, the flight controller busy with the page's reads: its answers take 0.9 s
        Sim s; s.phone = false;
        s.replyMs = [](uint32_t) { return 900u; };
        s.switchHigh = [](uint32_t t) { return t >= 101000; };
        s.advance(1000 + 50);                                         // a request 50 ms after the switch
        int armedSaid = 0, busy = 0, open = 0;
        for (int i = 0; i < 12; ++i) {                                // the page's tries, 200 ms apart
            const ArmLock l = s.gate();
            if (l == ARMLOCK_OPEN) open++; else if (l == ARMLOCK_ASKING) busy++; else armedSaid++;
            if (l == ARMLOCK_OPEN) break;
            s.advance(200);
        }
        expectB("slow answers (0.9 s) at switch-on: the page is told 'busy' and then let in - never 'ARMED'", armedSaid == 0 && open == 1, true);
        expectB("... and loop() was never held longer than 0.7 s for it", s.maxHeld <= ARM_SWITCH_SETTLE_MS + FC_ASK_FIRST_MS, true);
        printf("     (%d times busy, longest hold %u ms)\n", busy, (unsigned)s.maxHeld);
        int locked = 0;
        for (int i = 0; i < 60; ++i) { s.advance(500); if (s.gate() != ARMLOCK_OPEN) locked++; }
        expectB("... and for the next half minute, answers still 0.9 s: never locked (the renewing question waits for its answer)", locked == 0, true);
        expectB("... a renewing question holds loop() no longer than its 1.5 s", s.maxHeld <= FC_ASK_RENEW_MS, true);
    }

    // ------------------------------------------------------------------ a real arming, with the app open
    for (int slow = 0; slow < 2; ++slow) {
        Sim s; s.phone = true;
        if (slow) s.replyMs = [](uint32_t) { return 900u; };
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 110010; };        // Rotorflight arms 10 ms after the switch
        s.advance(9990);
        expectL(slow ? "arming, slow answers: just before" : "arming: just before", s.gate(), ARMLOCK_OPEN);
        int open = 0; bool sawFc = false; uint32_t fcAt = 0, worstHold = 0;
        for (int i = 0; i < 3000; ++i) {                              // every millisecond for 3 s: a request at any moment
            s.advance(1);
            Sim probe = s;                                            // (a copy: looking must not change what happens)
            const ArmLock l = probe.gate();
            if (s.now >= 110000 && l == ARMLOCK_OPEN) open++;
            if (s.now >= 110000 && probe.held > worstHold) worstHold = probe.held;
            if (l == ARMLOCK_FC && !sawFc) { sawFc = true; fcAt = s.now; }
        }
        expectB(slow ? "arming, slow answers: from the moment the switch goes on, never open again - at any millisecond"
                     : "arming: from the moment the switch goes on, never open again - at any millisecond", open == 0, true);
        expectB(slow ? "arming, slow answers: a request at any millisecond holds loop() 0.7 s at the most"
                     : "arming: a request at any millisecond holds loop() 0.7 s at the most", worstHold <= ARM_SWITCH_SETTLE_MS + FC_ASK_FIRST_MS, true);
        printf("     (longest hold %u ms)\n", (unsigned)worstHold);
        if (!slow) expectB("arming: the flight controller's own 'armed' has it within 0.2 s (the follow's question)", sawFc && fcAt <= 110200, true);
        expectB(slow ? "arming, slow answers: the red banner is up" : "arming: the red banner is up", s.shown(), true);
        const uint32_t a0 = s.asks;
        int open2 = 0; s.maxHeld = 0;
        for (int i = 0; i < 1200; ++i) { s.advance(500); if (s.gate() == ARMLOCK_OPEN) open2++; }   // ten minutes of flight, a page still asking
        expectB("flight: ten minutes, a page asking twice a second: locked throughout", open2 == 0, true);
        expectB("flight: ... the flight controller was not asked once in the air, and loop() never held", s.asks == a0 && s.maxHeld == 0, true);
    }
    {   // no phone following, and no answer before the first request: the page's own question finds it armed
        Sim s; s.phone = false;
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 110010; };
        s.advance(10000 + 100);
        expectL("arming, nobody following: 100 ms after the switch, the rule alone: locked (settling), not asked", s.ruleNow(), ARMLOCK_SETTLING);
        expectB("... no question was put", s.asks == 0, true);
        expectL("... a request at that moment: it waits, the FC is asked once, says armed: locked", s.gate(), ARMLOCK_FC);
        expectB("... the question was put no sooner than 0.3 s after the switch", s.asks == 1 && s.wordMs >= 110000 + ARM_SWITCH_SETTLE_MS, true);
        const uint32_t a0 = s.asks;
        int open = 0;
        for (int i = 0; i < 240; ++i) { s.advance(500); if (s.gate() == ARMLOCK_OPEN) open++; }
        expectB("... and for the next two minutes: locked, and never asked again", open == 0 && s.asks == a0, true);
    }
    {   // the same with slow answers (0.9 s): the page is told busy, then ARMED - and loop() is held 0.6 s once, then not at all
        Sim s; s.phone = false;
        s.replyMs = [](uint32_t) { return 900u; };
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 110010; };
        s.advance(10000 + 100);
        expectL("arming, nobody following, slow answers: the first request: 'busy' (asking)", s.gate(), ARMLOCK_ASKING);
        expectB("... held 0.2 s of settling and the question's 0.4 s", s.held == 200 + FC_ASK_FIRST_MS, true);
        s.advance(200);
        expectL("... the page's second try: still asking", s.gate(), ARMLOCK_ASKING);
        expectB("... without holding loop() at all, and without a second question", s.held == 0 && s.asks == 1, true);
        s.advance(600);
        expectL("... once the answer is in: locked (FC)", s.gate(), ARMLOCK_FC);
    }
    {   // a deaf flight controller (known here, not answering): the switch stands, as before, and loop() is not worn out
        Sim s; s.phone = false; s.fcDeaf = true;
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.advance(10000 + 700);
        int open = 0; uint32_t heldSum = 0;
        for (int i = 0; i < 120; ++i) { if (s.gate() == ARMLOCK_OPEN) open++; heldSum += s.held; s.advance(250); }   // 30 s, four requests a second
        expectB("a flight controller that does not answer: never open - the arm switch stands", open == 0, true);
        expectB("... and a page asking 4 times a second holds loop() for under a tenth of the time", heldSum <= 3000, true);
        printf("     (loop() held %u ms in 30 s, %u questions)\n", (unsigned)heldSum, (unsigned)s.asks);
    }
    {   // an arming Rotorflight only DELAYS (a DShot beacon, the gyro calibration): seen at the next question
        Sim s; s.phone = true;
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 111300; };         // armed 1.3 s after the switch
        s.advance(10000);
        uint32_t lastOpenAfterArmed = 0;
        for (int i = 0; i < 6000; ++i) {
            s.advance(1);
            Sim probe = s;
            if (probe.gate() == ARMLOCK_OPEN && s.now >= 111300) lastOpenAfterArmed = s.now;
        }
        expectB("a delayed arming: open for no longer than 1.5 s after the flight controller really armed", lastOpenAfterArmed <= 111300 + FC_NOT_ARMED_MS, true);
        expectL("... and locked from then on", s.gate(), ARMLOCK_FC);
        printf("     (a request could still pass until %u ms after it armed)\n", lastOpenAfterArmed ? (unsigned)(lastOpenAfterArmed - 111300) : 0u);
    }
    {   // refused arming, then the switch off and on again - the flight controller's word from before must not open the door
        Sim s; s.phone = false;
        s.switchHigh = [](uint32_t t) { return (t >= 110000 && t < 120000) || t >= 120300; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 120310; };         // refused the first time, arms the second
        s.advance(10000 + 5000);
        expectL("refused arming (the switch on 5 s, the FC says no): open", s.gate(), ARMLOCK_OPEN);
        s.advance(4990);                                               // 119990: asked a moment ago, 'not armed'
        expectL("... still open just before the switch goes off", s.gate(), ARMLOCK_OPEN);
        s.advance(10 + 300 + 100);                                     // off at 120000, on again at 120300, now 120400
        expectL("switch off and on again: 100 ms into the new arming - locked, the old 'not armed' does not count", s.ruleNow(), ARMLOCK_SETTLING);
        expectL("... a request then: it waits, asks, armed - locked", s.gate(), ARMLOCK_FC);
    }
    {   // THE REVIEW, 1: the switch flicked off and on while the question is out; the answer ("not armed") lands 12 ms into
        // the new arming, and the flight controller arms 3 ms after that. The answer must not open the door.
        Sim s; s.phone = false;
        const uint32_t T = 120000;
        s.switchHigh = [](uint32_t t) { return (t >= 110000 && t < T + 100) || t >= T + 290; };
        s.fcIsArmed  = [](uint32_t t) { return t >= T + 305; };
        s.advance(10000 + 8000);                                       // the switch on 8 s, the flight controller refusing
        expectL("flick: the switch on 8 s, refused: open", s.gate(), ARMLOCK_OPEN);
        s.advance(T - s.now);                                          // T: the last 'not armed' is 2 s old - the next request renews it
        s.replyMs = [](uint32_t) { return 302u; };                     // this answer takes 302 ms
        const ArmLock l = s.gate();
        expectL("flick: off and on again while the question was out, 'not armed' heard 12 ms into the new arming: LOCKED", l, ARMLOCK_SWITCH);
        expectB("flick: ... (the answer did come in, 302 ms later)", s.held == 302 && s.wordMs == T + 302 && !s.word, true);
        s.replyMs = [](uint32_t) { return 40u; };
        s.advance(400);
        expectL("flick: ... and the next request finds it armed", s.gate(), ARMLOCK_FC);
    }
    {   // THE REVIEW, 3: a confirmed arming and a gap in the radio link - the model flies on its held channels
        Sim s; s.phone = false;
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 110010; };
        s.advance(10000 + 600);
        expectL("gap: armed and confirmed", s.gate(), ARMLOCK_FC);
        s.advance(60000);                                              // a minute into the flight: the FC's 'armed' is a minute old
        const uint32_t gapAt = s.now;
        s.txOn = [gapAt](uint32_t t) { return t < gapAt || t >= gapAt + 2500; };     // 2.5 s of radio silence
        int open = 0; const uint32_t a0 = s.asks; uint32_t worst = 0;
        for (int i = 0; i < 6000; ++i) { s.advance(1); Sim probe = s; if (probe.gate() == ARMLOCK_OPEN) open++; if (probe.held > worst) worst = probe.held; }
        expectB("gap: 2.5 s of radio silence in flight and the 3.5 s after it: locked at every millisecond", open == 0, true);
        expectB("gap: ... the flying flight controller was not asked, and loop() never held", s.asks == a0 && worst == 0, true);
        expectL("gap: ... and it is the flight controller's own lock still", s.gate(), ARMLOCK_FC);
    }
    {   // ... and a transmitter switched off after the flight with the arm switch still on: not locked for ever
        Sim s; s.phone = false;
        s.switchHigh = [](uint32_t t) { return t >= 110000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 110010 && t < 200000 + 4500; };   // Rotorflight disarms 4.5 s after the last packet
        s.advance(10000 + 600);
        expectL("transmitter off: armed and confirmed", s.gate(), ARMLOCK_FC);
        s.advance(200000 - s.now);
        s.txOn = [](uint32_t t) { return t < 200000; };
        s.advance(4000);
        expectL("transmitter off 4 s, arm switch never switched off: still locked (the model may be coming down)", s.gate(), ARMLOCK_FC);
        s.advance(600);
        expectL("transmitter off 4.6 s: taken to be off - no switch, no lock (as before 0.9.923)", s.gate(), ARMLOCK_OPEN);
    }
    {   // disarming: the lock goes when the switch goes off and the flight controller's 'armed' is 5 s old
        Sim s; s.phone = false;
        s.switchHigh = [](uint32_t t) { return t >= 110000 && t < 200000; };
        s.fcIsArmed  = [](uint32_t t) { return t >= 110010 && t < 200010; };
        s.advance(10000 + 600);
        expectL("a flight: locked", s.gate(), ARMLOCK_FC);
        s.advance(89400 + 100);                                        // 200100: the switch has been off 100 ms
        expectL("after landing, switch off 100 ms: open (the FC's last 'armed' is a minute and a half old)", s.gate(), ARMLOCK_OPEN);
    }

    printf("\n%s\n", fails ? "FAILED" : "ALL PASS");
    return fails ? 1 : 0;
}
