#!/usr/bin/env python3
"""A SAVE UNDER ITS OWN STALL (the eleventh review, reviewer A's experiments 5 and 7; 15 Nov 2026) - a regression B211 had against the
released code: on a field screen (to 1.11.197) a save was REFUSED whenever the screen's loop had stood still for a quarter to two thirds
of a second just before its first text box was asked for - and it stands still for that long
  (S1) behind the save's own queue ("Sending ...", the colour changes: 325 to 606 ms measured on a real screen, B187 and B188), and
  (S2) behind the page that a question's way back puts up again ("OK with unsaved edits -> Save them now? -> Yes": a page with a picture is
       some hundreds of ms in coming up).
The screen's other core says its line a fifth of a second into the silence - a bare word with no end - and no text reply is believed for
half a second from when that line was READ. The first text box was asked inside that half second: "Please press Save again", on the first,
the second and the third press alike. THE CURE (Nextion.h GetText): the half second is waited out before the box is asked.
What must hold, for every length of the silence, on a screen up to 1.11.197 and on one from 1.11.198: the save's gather is TAKEN - every box,
its own text - on each of three tries; and never a wrong text."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
struct Box5 { const char *name; const char *text; };
static const Box5 rate5[] = { { "t10", "3.70" }, { "t12", "95" }, { "tr1", "1.80" }, { "tr2", "0.65" }, { "tr3", "240" }, { "tr4", "12.5" }, { "tr5", "-3.5" }, { "tr6", "100" }, { "tr7", "0" }, { "tr8", "45" }, { "tr9", "7" }, { "tr10", "360" } };
static void page5() { for (auto *pp : { &screen.pages, &screen.pages0 }) { Page &p = (*pp)["RXOptionsView"]; for (auto &b : rate5) p.boxes[b.name] = { true, 0, b.text }; } }
'''
SCENES = r'''
    int refused = 0, tries = 0, longestMs = 0;
    for (int form : { 197, 198 })
    {
        // (S1) the save's own queue holds the screen's loop for N ms; the save pressed three times running, a second apart
        std::string row[3];
        for (int ms = 100; ms <= 1300; ms += 50)
        {
            more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(800); page5();
            for (int press = 0; press < 3; ++press)
            {
                loopFor(1000);
                const uint32_t lost0 = BoxesLost; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false;
                DelayWithDog(100); SendText((char *) "change", (char *) "Sending edited rates ...");
                screen.stall(nowUs + 200, (uint32_t) ms, true);                       // the screen's loop busy with what the save queued: from now, so long
                const uint64_t t0 = nowUs;
                RfGatherStart();
                int ok = 0; bool wrong = false;
                for (auto &b : rate5) { char t[24] = "x"; GetText((char *) b.name, t, sizeof(t) - 1); if (!strcmp(t, b.text)) ++ok; else if (t[0] && BoxesLost == lost0) wrong = true; }
                const bool taken = BoxesLost == lost0 && !NextionTextMissed && ok == 12;
                ++tries; if (!taken) ++refused; if ((int) ((nowUs - t0) / 1000) > longestMs) longestMs = (int) ((nowUs - t0) / 1000);
                row[press] += taken ? " Y" : " -";
                CHECK(!wrong);                                                        // never a wrong text
                CHECK(taken);                                                         // ... and the save is taken
            }
        }
        say("S1 (1.11.%d). the save's own queue holds the screen's loop for 100 to 1300 ms (in fifties); the save pressed three times:\n   1st:%s\n   2nd:%s\n   3rd:%s   (Y: all twelve boxes taken; -: 'press Save again')\n",
            form, row[0].c_str(), row[1].c_str(), row[2].c_str());
        // (S2) "Save them now?" answered Yes: the way back puts the page up again, N ms in coming up - then the save's gather. Three tries of the whole thing
        std::string rows[3];
        for (int ms = 50; ms <= 900; ms += 50)
        {
            for (int tryNo = 0; tryNo < 3; ++tryNo)
            {
                more(); screen.realUart = true; screen.shoutForm = form; screen.loadUs = (uint32_t) ms * 1000; tapAt(5, "setup"); loopFor(1500); page5(); loopFor(800 + tryNo * 137);
                const uint32_t lost0 = BoxesLost; NextionTextMissed = false; BoxesLostAtWork = BoxesLost; PageChangedUnderGet = false;
                tapAt(1200, "yes");
                const bool yes = GetConfirmation((char *) "page RXOptionsView", (char *) "The edited rates are not saved. Save them now?");
                int ok = 0; bool wrong = false;
                if (yes)
                {
                    DelayWithDog(100); SendText((char *) "change", (char *) "Sending edited rates ...");
                    RfGatherStart();
                    for (int k = 0; k < 6; ++k) { const Box5 &b = rate5[k]; char t[24] = "x"; GetText((char *) b.name, t, sizeof(t) - 1); if (!strcmp(t, b.text)) ++ok; else if (t[0] && BoxesLost == lost0) wrong = true; }
                }
                const bool taken = yes && BoxesLost == lost0 && !NextionTextMissed && ok == 6;
                ++tries; if (!taken) ++refused;
                rows[tryNo] += !yes ? " ?" : taken ? " Y" : " -";
                CHECK(yes); CHECK(!wrong); CHECK(taken);
            }
        }
        say("S2 (1.11.%d). the page 50 to 900 ms in coming up; 'Save them now?' -> Yes -> the way back -> the gather:\n   1st:%s\n   2nd:%s\n   3rd:%s   (?: the question itself not answered)\n",
            form, rows[0].c_str(), rows[1].c_str(), rows[2].c_str());
    }
    say("in all: %d saves, %d refused; the longest a gather took: %d ms\n", tries, refused, longestMs);
    CHECK(refused == 0);
    CHECK(longestMs < 4000);                                                          // (the wait is bounded: a second and a tenth for a box, and the screen's own stall)
'''
sys.exit(lib.build_run('save_stall', SCENES, EXTRA, sanitize=False))
