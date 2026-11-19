#!/usr/bin/env python3
"""E8: GetConfirmation reads the answer from the global AFTER it has sent the question's way back (SendCommand(goback), which
waits 20 ms flying the model). A box put up from inside THAT wait - the link found lost with the motor switch on - leaves its
own OK in the same global: the pilot's "No" comes back as Yes. (The eighth review's cure covers a box put up while the
question still waits; this is the 20 ms after it.)"""
import sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static bool armed8 = false, fired8 = false;
static void lostAfterNo() { if (!armed8 || fired8 || ModalWaits || Confirmed[0] != 'N') return; fired8 = true; motorOffAtUs = nowUs + 1500000; tapAt(3000, "yes"); LinkLostNow(); }
static void my7(int n) { if (n == 2) Confirmed[0] = 'N'; else more7(n); }
'''
SCENES = r'''
    more(); extra7 = my7; screen.pages["PopupView"].buttons["no"] = { 0x82, 0x00, 0x00, 0x00 }; tapAt(5, "setup"); loopFor(800); BoundFlag = ModelMatched = true;
    armed8 = true; fired8 = false; flyHook = lostAfterNo; tapAt(1500, "no");
    const bool answer = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?\r\nThis cannot be undone."); flyHook = nullptr; armed8 = false;
    say("E8. the pilot presses NO; the link is found lost (motor switch on) in the 20 ms wait behind the question's way back; he switches off and presses that box's OK:\n    the first question's answer comes back as %s (the box came up: %d; questions closed %d)\n", answer ? "YES" : "No", (int) fired8, questionsClosed);
    CHECK(fired8); CHECK(!answer);
'''
sys.exit(lib.build_run('answer', SCENES, extra=EXTRA, sanitize=False))
