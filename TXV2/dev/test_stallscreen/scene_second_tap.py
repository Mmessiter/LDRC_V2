#!/usr/bin/env python3
"""A SECOND TAP ON OK, AND A SCREEN WHOSE LOOP STANDS STILL FOR LONGER THAN THE MARKER'S WAIT (the ninth review, reviewer A).
Model options: values typed, OK. The transmitter reads the boxes, saves, and sends "page FrontView". At that moment the screen's
loop stands still (its WiFi, its card), the page command unread, Model options still showing. The pilot taps OK again - on the
real screen: his finger was down on it and lifts during the silence - and the screen, when it wakes, prints that tap BEFORE it
reads the page command. The marker's wait had been given up after a second and a half: the tap was obeyed, the boxes answered
by the front page, and ZEROS WERE SAVED (motor switch 0, stop flying 0.00 V, trim step 0, six banks 0, timer 0).
Now a marker that is late is OWED: the wait goes on - for 1.2, 1.7, 2.5, 6, 12 and 40 seconds here - and the tap is not obeyed."""
import sys
import lib
SCENES = r'''
    for (int form : { 197, 198 })
        for (uint32_t stallMs : { 1200u, 1700u, 2500u, 6000u, 12000u, 40000u })
        {
            more(); screen.realUart = true; screen.shoutForm = form; screen.latencyUs = 40000; screen.tapInLoadFallsThrough = true; tapAt(5, "setup"); loopFor(900);
            { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["n4"].val = 8; }   // typed: trim step 9, stop flying 3.70 V, 8 minutes
            static bool planted; static uint32_t ms; planted = false; ms = stallMs;
            flyHook = []() { if (planted) return; for (auto &c : screen.cmds) if (c.second == "page FrontView") { planted = true; screen.stall(nowUs, ms, true, 300); screen.taps.insert({ nowUs + 10000, "OK" }); return; } };
            tapAt(5, "OK"); loopFor(stallMs + 9000); flyHook = nullptr;
            say("a screen of 1.11.%d stands still for %u ms as \"page FrontView\" arrives, a second tap on OK 10 ms later: OK obeyed %d times (on the wrong page %d), saves %d, presses not obeyed %d, 'the marker never came' %d, told of lost boxes %d\n",
                form, stallMs, count(obeyed, 39), wrongPage, (int) saves.size(), stale, noMarks, boxesLostTold);
            for (auto &s : saves) say("   saved: motor switch %d, stop flying %.2f V, trim step %u, six banks %d, timer %u s\n", s.kill, s.volts, s.step, s.six, s.timer);
            bool allTyped = !saves.empty(); for (auto &s : saves) if (!(s.step == 9 && s.volts > 3.69f && s.volts < 3.71f && s.timer == 480 && s.kill && s.six && s.amps == 120)) allTyped = false;
            CHECK(planted && wrongPage == 0 && allTyped && TrimMultiplier == 9 && StopFlyingVoltsPerCell > 3.69f && TimerStartTime == 480 && UseMotorKill && SixBanks);
            CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && stale == 1 && noMarks == 0 && !ScreenAnswerOwed && !ScreenMarkAwaited && boxesLostTold == 0 && screen.page == "FrontView");
            if (stallMs > 1600) CHECK(owedCaughtUp >= 1);                          // (the marker was owed, and the screen caught up - after forty seconds too: the wait is not given up)
        }
    // THE MARKER LOST ON THE WIRE (the screen itself well): it is owed - and the number told behind it comes back without it: the page is up, its
    // number is asked for again, and the page's buttons work. (The buttons were deaf for a second and a half, then the wait was given up.)
    more(); tapAt(5, "setup"); loopFor(900); CHECK(ScreenSaysMarks && ScreenPageId == 9);
    { static bool cut; cut = false; flyHook = []() { if (cut) return; for (auto &c : screen.cmds) if (c.second == "page FrontView") { cut = true; screen.knowsSysGet = false; return; } };   // (from here it says no number: both markers "lost")
      tapAt(5, "OK"); for (int i = 0; i < 4000 && !cut; ++i) loopFor(1);
      CHECK(cut); loopFor(100); flyHook = nullptr; screen.knowsSysGet = true;       // (the page command has gone, and its two markers were never said; from here the screen says numbers again)
      CHECK(ScreenMarkAwaited && !ScreenAnswerOwed && noMarks == 0 && screen.page == "FrontView");
      tapAt(5, "setup"); loopFor(100); CHECK(count(obeyed, 1077) == 1 && stale == 1 && ScreenMarkAwaited);   // (a tap meanwhile is not obeyed: the page is not known to be up)
      loopFor(2000); CHECK(!ScreenAnswerOwed && !ScreenMarkAwaited && noMarks == 1 && owedCaughtUp == 1 && ScreenPageId == 13);   // (a second and a half: owed; the number came back without the marker - the page is up, its number learned afresh)
      tapAt(5, "setup"); loopFor(900); CHECK(count(obeyed, 1077) == 2 && screen.page == "RXOptionsView"); }
    // THE NUMBER SAID BACK PROVES ONLY WHAT WAS ASKED BEFORE IT. An answer is owed and the number is on its way; THEN a page command goes out. The
    // number comes back first - the page's markers behind it: the page is NOT up yet, and a tap that falls through as it comes up is let go
    more(); screen.tapInLoadFallsThrough = true; screen.roundUs = 20000; tapAt(5, "setup"); loopFor(900);
    screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed);
    screen.latencyUs = 40000; loopFor(2); CHECK(ScreenEchoToldMs != 0 && ScreenAnswerOwed);
    SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; tapAt(60, "setup"); loopFor(600);
    CHECK(!ScreenAnswerOwed && !ScreenMarkAwaited && noMarks == 0 && LoadPrintsLetGo == 1 && count(obeyed, 1077) == 1 && owedCaughtUp == 1 && ScreenPageId == 13);
    // AN EARLIER NUMBER DOES NOT PAY THE DEBT: only the one last told (the "say this back", and the session's number after a restart)
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; ScreenSaidSession = false; ScreenSessionTries = SCREEN_SESSION_TRIES; ScreenSessionNextMs = millis() + 600000;
    ScreenAnswerOwed = true; ScreenOwedSinceMs = millis(); ScreenEchoToldMs = 0; ScreenSaidEcho = false; loopFor(5); CHECK(ScreenEcho != 0 && ScreenAnswerOwed);
    { const uint32_t e = ScreenEcho - 1; screen.emit(nowUs + 1000, { 'q', (uint8_t) e, (uint8_t) (e >> 8), (uint8_t) (e >> 16), (uint8_t) (e >> 24), 0xFF, 0xFF, 0xFF }); loopFor(20); CHECK(ScreenAnswerOwed && !ScreenSaidEcho); }
    { const uint32_t e = ScreenEcho; screen.emit(nowUs + 1000, { 'q', (uint8_t) e, (uint8_t) (e >> 8), (uint8_t) (e >> 16), (uint8_t) (e >> 24), 0xFF, 0xFF, 0xFF }); loopFor(20); CHECK(!ScreenAnswerOwed && owedCaughtUp == 1); }
    more(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; NoteScreenRestart(5); loopFor(5); CHECK(ScreenRestartSeen && ScreenSession != 0 && !ScreenSaidSession);
    { const uint32_t s = ScreenSession - 1; screen.emit(nowUs + 1000, { 'q', (uint8_t) s, (uint8_t) (s >> 8), (uint8_t) (s >> 16), (uint8_t) (s >> 24), 0xFF, 0xFF, 0xFF }); loopFor(20); CHECK(ScreenRestartSeen && !ScreenSaidSession && restartsHandled == 0); }
    { const uint32_t s = ScreenSession; screen.deaf = false; screen.emit(nowUs + 1000, { 'q', (uint8_t) s, (uint8_t) (s >> 8), (uint8_t) (s >> 16), (uint8_t) (s >> 24), 0xFF, 0xFF, 0xFF }); loopFor(300); CHECK(!ScreenRestartSeen && restartsHandled == 1); }
    // A QUESTION WHOSE OWN PAGE COMES UP LATE (the screen stands still for two seconds as the box's page command arrives): its marker is owed, and
    // the question's own wait catches up with it - "Yes", and the boxes of the work that follows are answered (left owed, each had no answer)
    more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900); screen.latencyUs = 40000;
    { static bool planted; planted = false; flyHook = []() { if (planted) return; for (auto &c : screen.cmds) if (c.second == "page PopupView") { planted = true; screen.stall(nowUs, 2000, true, 300); return; } };
      tapAt(2600, "yes");
      const bool yes = GetConfirmation((char *) "page RXOptionsView", (char *) "Save these?"); flyHook = nullptr;
      CHECK(planted && yes && !QuestionClosedItself && !ScreenAnswerOwed && owedCaughtUp == 0 && GetValue((char *) "n3") == 5 && boxesLostTold == 0); }
    // A SCREEN THAT HAS NEVER SAID A MARKER (one older than them): the wait ends after a second and a half, as it always did - three such, and
    // presses are only purged
    more(); screen.knowsSysGet = false; tapAt(5, "setup"); loopFor(3000); CHECK(!ScreenSaysMarks && noMarks == 1 && !ScreenMarkAwaited && !ScreenAnswerOwed && ScreenMarkMisses == 1 && ScreenMarkGivenUp);
    // ... a give-up is the LAST page command's own: the next page command's markers, come in their time, void nothing (a box read right
    // behind that page command is answered)
    more(); screen.knowsSysGet = false; tapAt(5, "setup"); loopFor(3000); LeaveQuick(); loopFor(3000); CHECK(ScreenMarkGivenUp && noMarks == 2 && ScreenMarkMisses == 2);
    screen.knowsSysGet = true; tapAt(5, "read"); loopFor(1500); CHECK(count(obeyed, 1079) == 1 && readNumber == 6 && !ScreenMarkGivenUp && ScreenSaysMarks && ScreenMarkMisses == 0);
    // ... AND ONE THAT SAYS IT AFTER ALL (it was slow to start: what was said to it is kept, and handled when its loop begins): the marker comes
    // after its wait was given up. A press obeyed since then may have been the old page's - the boxes of the work in hand have no answer
    more(); tapAt(5, "setup"); loopFor(900); ScreenSaysMarks = false;               // (as if this were the first page command of all)
    { Page &p = screen.pages["RXOptionsView"]; p.boxes["n3"].val = 9; p.boxes["t10"].txt = "3.70"; p.boxes["n4"].val = 8; }
    screen.latencyUs = 40000; screen.tapInLoadFallsThrough = true;
    { static bool planted; planted = false; flyHook = []() { if (planted) return; for (auto &c : screen.cmds) if (c.second == "page FrontView") { planted = true; screen.stall(nowUs, 2500, false, 300); screen.taps.insert({ nowUs + 10000, "OK" }); return; } };
      tapAt(5, "OK"); loopFor(12000); flyHook = nullptr;
      bool allTyped = !saves.empty(); for (auto &s : saves) if (!(s.step == 9 && s.volts > 3.69f && s.timer == 480 && s.kill && s.six)) allTyped = false;
      CHECK(planted && noMarks == 1 && count(obeyed, 39) == 2 && saves.size() == 2 && allTyped && TrimMultiplier == 9 && boxesLostTold == 1 && ScreenSaysMarks && !ScreenMarkAwaited && !ScreenMarkGivenUp); }
'''
if __name__ == '__main__':
    rc = lib.build_run('second_tap', SCENES)
    sys.exit(rc)
