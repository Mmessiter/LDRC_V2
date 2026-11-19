#!/usr/bin/env python3
"""RULES THAT NO TEST HELD (the tenth review, reviewer A: each of these could be taken out of Nextion.h and the four tests still passed).
  K. THE BOX'S PAGE, "another page - whatever it is": the screen shows a page that is no keyboard and is not the one this board put up; a
     box asked there has no answer. (The reviewer's change that went unnoticed: NoteScreenPage learning the page's number from EVERY
     "which page?" answer - the box then came back as 0, unflagged. His experiment K1.)
  M. THE HALF MINUTE OF AN ANSWER OWED: a screen that says no number back any more is not waited for for ever - after half a minute it is
     asked again; and not before.
  S. "IT HAS STARTED AGAIN" IS SAID BY THE SCREEN, NOT CONCLUDED FROM SILENCE (the reviewer's finding 6): asked for its session's number
     in front of the number it is to say back, a screen that has started again says 0 for it - twice running, and its front page is drawn
     afresh. The session's answer NOT READ AT ALL (lost, hidden behind a word's tail) says nothing: asked again a fifth of a second on,
     no restart - until the half minute, when a screen that has still not said it is taken to have started again."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static long keepSession = 0;
'''
SCENES = r'''
    // C. THE COUNTS BEGIN WHERE THE CLOCK STANDS (the reviewer's finding 7: they began at 1 with every start of this board - a screen that still owed an
    //    answer to this board's last life could say the very number the new life's first page command waits for). The first count of all is made of
    //    the clock; from there each is the one before plus one, never 0; and a page's first marker, the session's number and the number said back
    //    all begin so. (This stands first: nothing has asked for a count yet.)
    { const uint32_t us0 = micros(); const uint16_t first = ScreenCountAfter(0); const uint32_t us1 = micros();
      bool ofTheClock = false;                                                                                 // (the clock moves on with every look at it: the count is made of a moment between the two looks here)
      for (uint32_t us = us0; us <= us1; ++us) { const uint16_t w = (uint16_t) (us ^ (us >> 16)); ofTheClock |= first == (w ? w : 1); }
      say("C. the clock stands at %lu us: the first count is %u\n", (unsigned long) us0, (unsigned) first);
      CHECK(ofTheClock && first > 1 && us1 - us0 < 100);
      CHECK(ScreenCountAfter(0) == first && ScreenCountAfter(first) == (uint16_t) (first + 1 ? first + 1 : 1) && ScreenCountAfter(65535) == 1 && ScreenCountAfter(7) == 8);
      more(); tapAt(5, "setup"); loopFor(900);
      CHECK(ScreenMarkCount == (uint16_t) (first + 1 ? first + 1 : 1) || ScreenMarkCount == first);          // (the front page at the start, or Model options: the first or the second page command of this life)
      CHECK((uint16_t) ScreenSession == first && ScreenSaidSession);                                           // the session's number: its first
      screen.mute.insert("n3"); (void) GetValue((char *) "n3"); screen.mute.clear(); loopFor(600);
      CHECK((uint16_t) ScreenEcho == first && !ScreenAnswerOwed); }                                            // ... and the number said back: its first
    // K. the box's page
    more(); tapAt(5, "setup"); loopFor(900); CHECK(ScreenPageId == 9 && screen.page == "RXOptionsView");
    screen.page = "FrontView";                                                 // (the screen is on another page - no keyboard - and this board does not know)
    { const uint32_t lost0 = BoxesLost; const uint32_t v = GetValue((char *) "n3");
      say("K. the board put up page 9, the screen shows page 13; box n3 (5 on page 9) asked: GetValue gave %lu, counted as lost %d, 'the screen showed another page' %d\n", (unsigned long) v, (int) (BoxesLost != lost0), offPage);
      CHECK(v == 65535 && BoxesLost != lost0 && offPage == 1);
      CHECK(ScreenPageId == 9); }                                              // (... and that answer did not teach this board "page 13")
    // Q. NO PAGE BOX HAS AN ANSWER INSIDE A QUESTION (reviewer B's finding 2: a page's routine served in a question's wait read its boxes from the
    //    question's page - which says the very page number the last page command asked for). Each of the three ways of asking, from inside one:
    //    nothing is sent to the screen, the box counts as unanswered; and outside the question it is answered again
    more(); tapAt(5, "setup"); loopFor(900);
    { const int g0 = screen.gets; const uint32_t lost0 = BoxesLost; char tx[16] = "x";
      ++ModalWaits;
      const uint32_t v = GetValue((char *) "n3"); const uint16_t k = GetText((char *) "t10", tx, sizeof tx); const int o = GetOtherValue((char *) "n3.val");
      --ModalWaits;
      say("Q. inside a question: a number box gave %lu, a text box %u chars, an attribute %d; asked of the screen %d; counted unanswered %u\n", (unsigned long) v, (unsigned) k, o, screen.gets - g0, (unsigned) (BoxesLost - lost0));
      CHECK(v == 65535 && k == 0 && !tx[0] && o == 0 && screen.gets == g0 && BoxesLost == lost0 + 3);
      CHECK(GetValue((char *) "n3") == 5 && GetText((char *) "t10", tx, sizeof tx) == 4 && !strcmp(tx, "3.50") && BoxesLost == lost0 + 3); }
    // M. the half minute. Model options is up; one box gets no answer (owed); from then on the screen says no number back at all (but answers boxes)
    more(); tapAt(5, "setup"); loopFor(900);
    screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear(); screen.knowsSysGet = false;
    { const uint64_t t0 = nowUs; loopFor(27000);
      const int g0 = screen.gets; const uint32_t early = GetValue((char *) "n3");
      CHECK(ScreenAnswerOwed && early == 65535 && screen.gets == g0);          // 29 s on: still owed - nothing is asked, no box has an answer
      loopFor(4000);
      say("M. an answer owed and a screen that says no number back: still owed after 29 s; %.0f s on: owed %d, a restart noted %d, a box asked then: %lu (5 on the page)\n", (nowUs - t0) / 1e6, (int) ScreenAnswerOwed, (int) ScreenRestartSeen, (unsigned long) GetValue((char *) "n3"));
      CHECK(!ScreenAnswerOwed && !ScreenRestartSeen && restartsHandled == 0 && GetValue((char *) "n3") == 5 && screen.page == "RXOptionsView"); }
    // S1. the session's answer is not read (lost each time), the number said back is: no restart - asked again, a fifth of a second apart; the answer back: over
    more(); tapAt(5, "setup"); loopFor(900); CHECK(ScreenSaidSession);
    screen.sysMute.insert("ldrcup"); screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    { loopFor(50); const uint16_t e0 = (uint16_t) ScreenEcho; loopFor(5000); const int rounds = (uint16_t) ((uint16_t) ScreenEcho - e0);
      say("S1. the session's number asked for and its answer lost each time, the number behind it said back: 5 s on - owed %d, restart noted %d, found by asking %d, rounds asked %d\n", (int) ScreenAnswerOwed, (int) ScreenRestartSeen, restartsFoundByAsking, rounds);
      CHECK(ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && restartsHandled == 0 && screen.page == "RXOptionsView");
      CHECK(rounds >= 15 && rounds <= 30);                                     // (a fifth of a second apart - not pass after pass)
      screen.sysMute.clear(); loopFor(600);
      CHECK(!ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && owedCaughtUp == 1 && GetValue((char *) "n3") == 5); }
    // S2. ... never read in half a minute: a screen that says a number back and not its session's is taken to have started again
    more(); tapAt(5, "setup"); loopFor(900);
    screen.sysMute.insert("ldrcup"); screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    loopFor(28000); CHECK(ScreenAnswerOwed && !ScreenRestartSeen && restartsHandled == 0);
    loopFor(3000); CHECK(restartsFoundByAsking == 1);                          // (the half minute is over: taken to have started again)
    screen.sysMute.clear(); loopFor(9000);                                     // (it says its new number, and its front page is drawn afresh)
    say("S2. ... for half a minute: found by asking %d, the front page afresh %d (reason %d), page %s\n", restartsFoundByAsking, restartsHandled, lastRestartReason, screen.page.c_str());
    CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -4 && screen.page == "FrontView" && CurrentView == FRONTVIEW && !ScreenAnswerOwed && !ScreenRestartSeen);
                                                                               // (reason -4, the eleventh review: "it never said its session's number" - not -3, "it said 0 for it")
    // S3. a screen that HAS started again with every sign lost says 0 for its session's number: twice, and it is found (in well under a second)
    more(); screen.restartPowerOnBytes = false; screen.restartSaysWord = false; screen.restartReason = 5; screen.bootRecord = ""; screen.powerOnUs = 1200000;
    tapAt(5, "setup"); loopFor(900); tapAt(5, "#restart"); loopFor(3000);
    screen.mute.insert("n3"); { const uint64_t t0 = nowUs; (void) GetValue((char *) "n3"); screen.mute.clear(); const uint64_t asked = nowUs; loopFor(900);
      say("S3. a restart with every sign lost, then a box with no answer: found by asking %d, the front page afresh %d (reason %d) within %.2f s of the answer being owed\n", restartsFoundByAsking, restartsHandled, lastRestartReason, (nowUs - asked) / 1e6);
      CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && screen.page == "FrontView" && CurrentView == FRONTVIEW && !ScreenAnswerOwed); (void) t0; }
    // S4. a healthy screen whose session's answer is hidden ONCE behind 0-looking bytes of another reply is not "started again": one round with a 0 is not two
    more(); tapAt(5, "setup"); loopFor(900);
    screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    { keepSession = screen.sys["ldrcup"]; screen.sys["ldrcup"] = 0;                              // (for one round the screen says 0 for it - as if; then its number again)
      for (int i = 0; i < 4000; ++i) { LoopPass(); if (ScreenSessionUnsaid >= 1) screen.sys["ldrcup"] = keepSession; nowUs += 500; }
      CHECK(screen.sys["ldrcup"] == keepSession);                              // (the scene is the one meant: a round with a 0 was counted)
      say("S4. 0 said for the session's number in one round only: owed %d, restart noted %d, found by asking %d, caught up %d\n", (int) ScreenAnswerOwed, (int) ScreenRestartSeen, restartsFoundByAsking, owedCaughtUp);
      CHECK(!ScreenRestartSeen && restartsFoundByAsking == 0 && restartsHandled == 0 && !ScreenAnswerOwed && screen.page == "RXOptionsView" && ScreenSessionUnsaid == 0); }
    // S5. THE 0 MUST STAND RIGHT IN FRONT of the number said back. A healthy screen whose session's answer is lost each time; and again and again a
    //     value reply of 0 comes (some box's own late answer) with a word of the screen's behind it - then, later, the number said back. That 0 is
    //     not "0 for the session's number": no restart, however often
    more(); tapAt(5, "setup"); loopFor(900);
    screen.sysMute.insert("ldrcup"); screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    for (int i = 0; i < 60; ++i) screen.emit(nowUs + 20000 + (uint64_t) i * 50000, cat9({ { 'q', 0, 0, 0, 0 }, END9, by9("UKRULES") }));
    loopFor(3500);
    say("S5. a value reply of 0 and a word, sixty times, among rounds whose session's answer is lost: owed %d, restart noted %d, found by asking %d\n", (int) ScreenAnswerOwed, (int) ScreenRestartSeen, restartsFoundByAsking);
    CHECK(ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && restartsHandled == 0 && screen.page == "RXOptionsView");
    screen.sysMute.clear(); loopFor(1200);
    CHECK(!ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && owedCaughtUp == 1);
    // S5r. the same ON THE REAL PORT (the eleventh review, reviewer A: without it what a scene says by hand for later is read in the order of saying,
    //      not of its time - the sixty zeros came before any number said back): the bytes in the order of their time, a 0 and a word every 5 ms
    more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900);
    screen.sysMute.insert("ldrcup"); screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    for (int i = 0; i < 600; ++i) screen.emit(nowUs + 20000 + (uint64_t) i * 5000, cat9({ { 'q', 0, 0, 0, 0 }, END9, by9("UKRULES") }));
    loopFor(3500);
    say("S5r. on the real port, a 0 with a word behind it every 5 ms for 3 s, the session's answer lost: owed %d, restart noted %d, found by asking %d\n", (int) ScreenAnswerOwed, (int) ScreenRestartSeen, restartsFoundByAsking);
    CHECK(ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && restartsHandled == 0 && screen.page == "RXOptionsView");
    // S5f. ... and with a FRAMED burst behind each 0 (a page's own print, a press) instead of the bare word: it stands between the 0 and the number
    //      said back just the same (a healthy screen was "found restarted": StashFramed and the main loop's framed read did not say so)
    more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900);
    screen.sysMute.insert("ldrcup"); screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    for (int i = 0; i < 600; ++i) screen.emit(nowUs + 20000 + (uint64_t) i * 5000, cat9({ { 'q', 0, 0, 0, 0 }, END9, { 0x7E, 0x7E, 7, 0 }, by9("UKRULES") }));
    loopFor(3500);
    say("S5f. ... a 0 with a FRAMED word behind it: owed %d, restart noted %d, found by asking %d\n", (int) ScreenAnswerOwed, (int) ScreenRestartSeen, restartsFoundByAsking);
    CHECK(ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && restartsHandled == 0 && screen.page == "RXOptionsView");
    screen.sysMute.clear(); loopFor(1500);
    CHECK(!ScreenAnswerOwed && !ScreenRestartSeen && restartsFoundByAsking == 0 && owedCaughtUp == 1);
    // S6. THE SESSION'S NUMBER SAID CLEARS THE DOUBT - also when the half minute is over. Rounds whose session's answer is not read (the doubt stands);
    //     then, the half minute gone, a round in which the screen DOES say its session's number: it is the same screen - no restart
    more(); tapAt(5, "setup"); loopFor(900);
    screen.sysMute.insert("ldrcup"); screen.mute.insert("n3"); CHECK(GetValue((char *) "n3") == 65535 && ScreenAnswerOwed); screen.mute.clear();
    { bool armed = false, moved = false; int restarts = 0, caught = 0;
      holdCatchUp = true;                                                      // (this scene takes the main loop's look at the screen's state in two steps: the read, then the step)
      for (int i = 0; i < 12000 && !moved; ++i)
      {
          LoopPass(); nowUs += 500;                                            // the look for a press: what the screen said is read
          if (!armed && ScreenSessionDoubted && !ScreenSaidEcho) { armed = true; screen.sysMute.clear(); }   // a round read with the session's answer missing: the doubt stands. From now the screen says it
          if (armed && ScreenSaidEcho && ScreenSessionSaidN != ScreenEchoSessionN)
          { // ... this round's answers have been read - the session's number among them - and the step has not looked yet: the half minute is over now
              ScreenOwedSinceMs -= SCREEN_TELL_LONGEST_MS + 1000; moved = true;
          }
          const bool restart = ScreenRestartSeen, owed = ScreenAnswerOwed;
          ScreenKeepUp();                                                      // the step (main.cpp)
          if (!restart && ScreenRestartSeen) ++restarts; else if (owed && !ScreenAnswerOwed) ++caught;
      }
      holdCatchUp = false;
      CHECK(moved);
      say("S6. the doubt standing, then - the half minute just over - a round in which the session's number is said: owed %d, restart noted %d (found by asking %d), caught up %d\n", (int) ScreenAnswerOwed, (int) ScreenRestartSeen, restarts, caught);
      CHECK(!ScreenAnswerOwed && !ScreenRestartSeen && restarts == 0 && caught == 1 && screen.page == "RXOptionsView"); }
    // S7. A SCREEN THAT HAS STARTED AGAIN, every sign lost, whose answers come GLUED BEHIND A WORD of its own in one read (the 0 for its session's
    //     number is then found INSIDE a bare read): found all the same, in well under a second - not at the half minute
    more(); screen.realUart = true; screen.restartPowerOnBytes = false; screen.restartSaysWord = false; screen.restartReason = 5; screen.bootRecord = ""; screen.powerOnUs = 1200000;
    tapAt(5, "setup"); loopFor(900); tapAt(5, "#restart"); loopFor(3000);
    screen.mute.insert("n3"); (void) GetValue((char *) "n3"); screen.mute.clear();
    screen.sysMute.insert("ldrcup"); screen.sysMute.insert("ldrcech");             // (from here its answers are said by hand, behind a word)
    { uint32_t told = 0; int rounds = 0; const uint64_t t0 = nowUs;
      for (int i = 0; i < 6000 && !ScreenRestartSeen && restartsFoundByAsking == 0; ++i)
      {
          LoopPass(); nowUs += 500;
          if (ScreenAnswerOwed && ScreenEcho != told && screen.sys.count("ldrcech") && (uint32_t) screen.sys["ldrcech"] == ScreenEcho)
          { // a round has been told: the screen "answers" - a word of its own, 0 for its session's number, the number said back - in one piece
              told = ScreenEcho; ++rounds;
              screen.emit(nowUs + 3000, cat9({ by9("UKRULES"), { 'q', 0, 0, 0, 0 }, END9, { 'q', (uint8_t) told, (uint8_t) (told >> 8), (uint8_t) (told >> 16), (uint8_t) (told >> 24) }, END9 }));
          }
      }
      say("S7. a restarted screen whose two answers come glued behind a word: rounds answered %d, found by asking %d after %.2f s\n", rounds, restartsFoundByAsking, (nowUs - t0) / 1e6);
      CHECK(rounds >= 2 && restartsFoundByAsking == 1 && nowUs - t0 < 2500000); }
'''
sys.exit(lib.build_run('rules', SCENES, EXTRA, sanitize=False))
