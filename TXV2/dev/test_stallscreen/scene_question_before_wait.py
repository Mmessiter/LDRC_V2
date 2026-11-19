#!/usr/bin/env python3
"""EXP W1 (review 10, reviewer A): A PAGE COMMAND FROM INSIDE THE WAIT OF A QUESTION'S OWN PAGE COMMAND.
MsgBox / GetConfirmation send "page PopupView" - and SendCommand then waits 20 ms flying the model (DelayWithDog). A page command sent from
inside THAT wait (the power button pressed while connected: the front page; the link lost with the motor switch on: its own box and the front
page) comes over the question BEFORE GetYesOrNo has begun - and GetYesOrNo takes "the last page command" for its own: it waits for an answer to
a question that is not on the screen. (ModalWaits is still 0 in those 20 ms: the power button's own guard does not hold.)

(The tenth review, reviewer A's experiment - the scenes his, what must hold the author's. THE CURE: whoever puts a question up takes the count its
own page command WILL have before sending it (Utilities.h NextPageMark) and hands it to GetYesOrNo: a question whose page command is no
longer the last one when its wait begins is closed at once - "No", overtaken, and no way back sent over the page that came.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static int w1Calls = 0; static long w1SendsInQuestion = 0;
static void w1LinkLostInFirstWait() { if (++w1Calls != 1) return; motorOffAtUs = nowUs + 2500000; LinkLostNow(); }   // RedLedOn's part that matters, from inside the wait behind the question's own page command
static void w1CountSend() { ++w1SendsInQuestion; }
''' + lib.m.lift(lib.m.UTIL, 'bool GetSaveOrDiscard(char *goback, char *Prompt)')

SCENES = r'''
    // (1) the power button, in the 20 ms behind the question's page command
    more(); tapAt(5, "setup"); loopFor(900); CHECK(screen.page == "RXOptionsView" && ScreenSaysMarks);
    BoundFlag = ModelMatched = true; powerAtWait = 1; flyHook = PowerButtonInWait; boxSpins = 0;
    { const uint64_t t0 = nowUs; const int radio0 = radioPasses;
      const bool yes = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?"); flyHook = nullptr;
      printf("W1.1 the power button in the wait behind \"page PopupView\": the question came back %s after %.1f s; the screen shows %s; closed by the board %d (overtaken %d); given up by the TEST ('T': nobody could answer) %d\n",
             yes ? "YES" : "no", (nowUs - t0) / 1e6, screen.page.c_str(), (int) QuestionClosedItself, (int) QuestionOvertaken, (int) (boxSpins > 399999));
      CHECK(!yes); CHECK(boxSpins < 400000);   // (it waited until the test itself gave it up - 200 s; on the transmitter: for ever, the switches unread)
      CHECK(nowUs - t0 < 200000 && QuestionClosedItself && QuestionOvertaken && ModalWaits == 0);
      loopFor(1500); CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW && !ScreenMarkAwaited);   // the front page stands: no way back was sent over it
    }
    // (2) the same, and the pilot touches a button of the front page he sees: it is obeyed from inside the question
    more(); tapAt(5, "setup"); loopFor(900);
    BoundFlag = ModelMatched = true; powerAtWait = 1; flyHook = PowerButtonInWait; boxSpins = 0; tapAt(3000, "setup");
    { const uint64_t t0 = nowUs; const size_t ob0 = obeyed.size();
      const bool yes = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?"); flyHook = nullptr;
      printf("W1.2 ... and a tap on the front page 3 s later: the question came back %s after %.1f s; closed by the board %d (overtaken %d); presses obeyed meanwhile %d; the screen shows %s\n",
             yes ? "YES" : "no", (nowUs - t0) / 1e6, (int) QuestionClosedItself, (int) QuestionOvertaken, (int) (obeyed.size() - ob0), screen.page.c_str());
      CHECK(!yes && nowUs - t0 < 200000 && QuestionClosedItself && QuestionOvertaken && obeyed.size() == ob0);   // nothing obeyed from inside the question: it was over at once
      loopFor(5000);
      CHECK(obeyed.size() == ob0 + 1 && screen.page == "RXOptionsView" && CurrentView == RXSETUPVIEW1);          // ... and his tap on the front page is the main loop's: Model options
    }
    // (3) the link lost with the motor switch ON, in those same 20 ms: the box "The motor switch is ON" comes up at once (from inside the wait), the
    //     pilot switches the motor off and presses its OK, the front page is drawn - and THEN the first question begins to wait, behind the front page
    more(); tapAt(5, "setup"); loopFor(900);
    BoundFlag = ModelMatched = false; w1Calls = 0; flyHook = w1LinkLostInFirstWait; boxSpins = 0; tapAt(3500, "yes"); w1SendsInQuestion = 0; sendDataHook = w1CountSend;   // (the motor switch goes off 2.5 s on; the box's OK a second later)
    { const uint64_t t0 = nowUs;
      const bool yes = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?"); flyHook = nullptr; sendDataHook = nullptr;
      printf("W1.3 the link lost with the motor switch on, in the wait behind \"page PopupView\": the motor box answered, the front page drawn; the first question came back %s after %.1f s; closed by the board %d (overtaken %d); given up by the TEST %d; packets sent while it waited: %ld; the screen shows %s\n",
             yes ? "YES" : "no", (nowUs - t0) / 1e6, (int) QuestionClosedItself, (int) QuestionOvertaken, (int) (boxSpins > 399999), w1SendsInQuestion, screen.page.c_str());
      CHECK(!yes && boxSpins < 400000 && nowUs - t0 < 6000000 && QuestionClosedItself && QuestionOvertaken && !MotorEnabled && ModalWaits == 0);   // the motor box was answered; the first question was over at once behind it
      loopFor(1500); CHECK(screen.page == "FrontView" && CurrentView == FRONTVIEW);
    }
    // (4) A QUESTION'S OWN TEXTS GO ONTO ITS OWN PAGE ONLY (the author's, 15 Nov 2026). The front page that came over the question in that first wait has
    //     parts of the same names as the question's pages (b0, b1, t0, t1, t3): "vis b1,0" hid one of its buttons, "Save" and "Discard" were written onto
    //     two others, the backup's file name into its text boxes. Each of the four askers, overtaken so: nothing of the question reaches the front page
    for (int asker = 0; asker < 4; ++asker)
    {
        more(); tapAt(5, "setup"); loopFor(900); BoundFlag = ModelMatched = true; powerAtWait = 1; flyHook = PowerButtonInWait; boxSpins = 0;
        const size_t vis0 = screen.visSaid.size(); screen.keptTxt.clear(); const uint32_t lost0 = BoxesLost; strcpy(SingleModelFile, "KEEP.MOD"); bool said = false;
        if (asker == 0) MsgBox((char *) "page RXOptionsView", (char *) "Not saved: each cell's voltages must rise.");
        else if (asker == 1) said = GetConfirmation((char *) "page RXOptionsView", (char *) "Delete every model and all settings?");
        else if (asker == 2) said = GetSaveOrDiscard((char *) "page RXOptionsView", (char *) "The edited PIDs are not saved.\r\nSave now?");
        else said = GetBackupFilename((char *) "page RXOptionsView", (char *) "GOBLIN.MOD", (char *) "Goblin", (char *) "Backup", (char *) "File name");
        flyHook = nullptr; loopFor(1500);
        int onFront = 0; for (const char *n : { "b0", "b1", "Dialog", "t1", "t3", "Modelname" }) onFront += (int) screen.keptTxt.count(std::string("FrontView.") + n);
        int visOnFront = 0; for (size_t i = vis0; i < screen.visSaid.size(); ++i) visOnFront += screen.visSaid[i].rfind("FrontView: ", 0) == 0;
        printf("W1.4 asker %d overtaken by the front page in the wait behind its own page command: answered %d; written onto the front page: %d texts of the question's, %d parts hidden or shown; the front page's own t0: '%s'\n",
               asker, (int) said, onFront, visOnFront, screen.keptTxt.count("FrontView.t0") ? screen.keptTxt["FrontView.t0"].c_str() : "(not written)");
        CHECK(!said && QuestionOvertaken && QuestionClosedItself && onFront == 0 && visOnFront == 0 && screen.keptTxt["FrontView.t0"] == "Model" && screen.page == "FrontView" && CurrentView == FRONTVIEW);
        if (asker == 3) CHECK(BoxesLost == lost0 && !strcmp(SingleModelFile, "KEEP.MOD") && boxesLostTold == 0);   // (... and the name is not "read" from the front page's box)
    }
    // ... and with nothing in the way each asker writes its texts as ever (the popup's page, the backup's page)
    more(); tapAt(5, "setup"); loopFor(900); screen.keptTxt.clear(); { const size_t vis0 = screen.visSaid.size(); tapAt(1500, "yes");
      MsgBox((char *) "page RXOptionsView", (char *) "Not saved.");
      CHECK(screen.keptTxt["PopupView.Dialog"] == "Not saved." && screen.visSaid.size() == vis0 + 1 && screen.visSaid.back() == "PopupView: vis b1,0"); }
    more(); tapAt(5, "setup"); loopFor(900); screen.keptTxt.clear(); tapAt(1500, "yes");
    CHECK(GetSaveOrDiscard((char *) "page RXOptionsView", (char *) "Save now?") && screen.keptTxt["PopupView.b0"] == "Save" && screen.keptTxt["PopupView.b1"] == "Discard" && screen.keptTxt["PopupView.Dialog"] == "Save now?");
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('w1', SCENES, EXTRA, args=[], sanitize=False, timeout=600))
