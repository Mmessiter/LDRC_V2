#!/usr/bin/env python3
"""WHAT WAS TYPED - AT THE END OF THE JOB THE BOX STARTED (the twelfth review, reviewer B's experiment 2, kept as he wrote it; 15 Nov 2026).
The eleventh review's cure kept what was typed THROUGH the box in front of Calibrate ("Is the model level ...?") and of the black box's Erase
("Erase every flight log ...?"). But nothing was gathered there, the job then ran in the page's own state machine, and at ITS end the page was
drawn from what is IN HAND (RF_FcSetup.h CalibratePoll CAL_CAL_ATT; BlackboxPoll -> BbDone) - over what was typed. The page stayed "edited"; Save
then wrote the OLD values. scene_typed_stays.py never got there: it put the state machine back to idle by hand.
THE CURE: both take the page FIRST, as every Save does - what is in hand at the job's end is what was typed (dev/test_noanswer job_lint holds that
every job of such a page begins with its gather).
The REAL CalibratePoll and BlackboxPoll (and BbDone, CalFail, BbFail) over a pretend pipe that answers each MSP question a little later."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, FCS, SRV = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_FcSetup.h', 'RF_Servos.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
def block(text, a, b): return text[text.index(a):text.index(b)]
REAL = (line(RES, 'FLASHMEM static uint16_t RdU16(') + m.lift(RES, 'FLASHMEM static void WrU16(') + line(SRV, 'FLASHMEM static int RdS16(')
        + m.lift(RES, 'FLASHMEM static long FieldNumber(') + m.lift(RES, 'FLASHMEM static int FieldTenths(')
        + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)')
        + block(FCS, 'FLASHMEM static void FsBusy(', 'FLASHMEM static void FsFail(')
        + m.lift(FCS, 'FLASHMEM static bool FsRefused(')
        + block(FCS, 'static uint8_t BbRaw[16], BbWant[16];', 'FLASHMEM void StartBlackboxView()')      # ... BbShow, BbGather, BbFail, BbDone and the REAL BlackboxPoll
        + line(FCS, 'FLASHMEM void BlackboxWasEdited()')
        + m.lift(FCS, 'FLASHMEM void SaveBlackbox()') + m.lift(FCS, 'FLASHMEM void BlackboxErase()')
        + block(FCS, 'static uint8_t CalRaw[8], CalWant[8];', 'FLASHMEM void StartCalibrateView()')     # ... CalShow, CalGather, CalFail and the REAL CalibratePoll
        + m.lift(FCS, 'FLASHMEM void CalibrateNow()') + m.lift(FCS, 'FLASHMEM void SaveLevelTrims()'))
EXTRA = r'''
// ---- a pretend pipe: each MSP question is answered 150 ms later (200, and the bytes that function gives)
static int mspFn[64], mspN = 0; static uint8_t mspData[64][40]; static uint64_t mspAt[64];
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 64) { mspFn[mspN] = fn; memset(mspData[mspN], 0, 40); if (data && len > 0) memcpy(mspData[mspN], data, (size_t) len); mspAt[mspN] = nowUs; ++mspN; } return mspN; }
char PipeRepBody[64] = ""; int PipeRepCode = 200;
static bool PipeReplyReady(int req) { return req >= 1 && req <= mspN && nowUs - mspAt[req - 1] >= 150000; }
static bool PipeReplyLate() { return false; }
static bool memErased = false;
static int PipeReplyBytes(uint8_t *b, int n)
{
    const int fn = mspN ? mspFn[mspN - 1] : 0;
    memset(b, 0, (size_t) n);
    if (fn == 108) { b[0] = 3; b[2] = 0xFE; b[3] = 0xFF; return 4; }                 // the level now: roll 0.3, pitch -0.2
    if (fn == 70) { b[0] = 3; b[5] = 0; b[6] = 0; b[7] = 0x80; b[8] = 0x07; return 13; }   // the memory: ready, there, 125 MB, nothing used (erased)
    if (fn == 240) { memcpy(b, mspData[0], 4); return 4; }
    return 0;
}
static bool BakOffline() { return false; }
static void RfSavedThenLeave(int) {}
static bool safetyOff = false;
static bool ModelSeemsArmed(char *why, size_t n) { if (!safetyOff) return false; snprintf(why, n, "Model is armed: the safety is off.\r\nSafety on first."); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static void FsFail(const char *, const char *) {}
''' + REAL + r'''
static void my7(int n) { if (n == 2) Confirmed[0] = 'N'; else more7(n); }
static void my24(int n) { if (n == 160) CalibrateNow(); else if (n == 161) SaveLevelTrims(); else if (n == 162) BlackboxErase(); else if (n == 163) SaveBlackbox(); else more24(n); }
static void addPages3()
{
    Page l; l.id = 74;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "busy", "t11", "t9" }) l.boxes[t] = { true, 0, "" };
    l.buttons["Calibrate"] = { 0x00, 160, 0x00, 0x00 }; l.buttons["Save"] = { 0x00, 161, 0x00, 0x00 };
    screen.pages["LevelView"] = l;
    Page x; x.id = 73;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "tn5", "tn6", "busy", "t11", "t9" }) x.boxes[t] = { true, 0, "" };
    x.boxes["tn4"] = { false, 0, "" };
    x.buttons["Erase"] = { 0x00, 162, 0x00, 0x00 }; x.buttons["Save"] = { 0x00, 163, 0x00, 0x00 };
    screen.pages["BlackboxView"] = x; screen.pages0 = screen.pages;
    CalHave = true; Cal_Was_Edited = false; WrS16(CalWant, 0, 15); WrS16(CalWant, 2, -20); memcpy(CalRaw, CalWant, sizeof CalRaw); CalStep = CAL_IDLE; CalNextAtt = millis() + 600000; CalMsgUntil = 0;
    memset(BbWant, 0, sizeof BbWant); BbWant[0] = 1; BbWant[1] = 1; BbWant[2] = 2; BbWant[3] = 8; BbWant[11] = 0; BbWant[12] = 10; memcpy(BbRaw, BbWant, sizeof BbRaw); BbHave = true; Bb_Was_Edited = false; BbStep = BB_IDLE; BbMsgUntil = 0;
    BbMemN = 13; BbMem[0] = 3;
    screen.pages["PopupView"].buttons["no"] = { 0x82, 0x00, 0x00, 0x00 };
    mspN = 0; safetyOff = false; BoundFlag = ModelMatched = true; extra24 = my24; extra7 = my7;
}
// the main loop with the two pages' own polls in it (main.cpp ManageTransmitter: BlackboxPoll, CalibratePoll)
static void loopPolls(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { LoopPass(); BlackboxPoll(); CalibratePoll(); nowUs += 500; } }
'''
SCENES = r'''
    // C. THE LEVEL PAGE: the trims 2.5 and -1.0 typed (the page is "edited": Save is offered). Calibrate - asked, answered Yes - and the calibration RUNS
    //    TO ITS END (205, 2.5 s, 250, 108: about three seconds). Then Save.
    {
        more(); addPages3(); SendCommand((char *) "page LevelView"); CurrentView = LEVELVIEW; CalHead(); CalShow(); loopPolls(600);
        Page &pg = screen.pages["LevelView"];
        CHECK(pg.boxes["tn2"].txt == "1.5" && pg.boxes["tn3"].txt == "-2.0");
        pg.boxes["tn2"].txt = "2.5"; pg.boxes["tn3"].txt = "-1.0"; Cal_Was_Edited = true;
        tapAt(5, "Calibrate"); tapAt(2500, "yes"); loopPolls(3000);
        say("C. trims 2.5 and -1.0 typed; Calibrate - Yes. Right behind the question the page shows '%s' and '%s' (kept)\n", pg.boxes["tn2"].txt.c_str(), pg.boxes["tn3"].txt.c_str());
        CHECK(pg.boxes["tn2"].txt == "2.5" && pg.boxes["tn3"].txt == "-1.0");
        loopPolls(6000);                                                                     // ... the calibration to its end
        say("   the calibration over (MSP asked: %d; the step is %s; the message: '%s'): THE PAGE NOW SHOWS '%s' and '%s'; still edited: %d\n", mspN, CalStep == CAL_IDLE ? "idle" : CalStep == CAL_ATT ? "the level's own look" : "busy",
            pg.boxes["busy"].txt.c_str(), pg.boxes["tn2"].txt.c_str(), pg.boxes["tn3"].txt.c_str(), (int) Cal_Was_Edited);
        CHECK((CalStep == CAL_IDLE || CalStep == CAL_ATT) && mspN >= 3);                     // (the calibration is over: idle, or the page's own look at the level, every 700 ms)
        CHECK(pg.boxes["tn2"].txt == "2.5" && pg.boxes["tn3"].txt == "-1.0");               // WHAT HE TYPED IS STILL ON THE PAGE
        const int at = mspN; tapAt(5, "Save"); loopPolls(1500);
        say("   Save: MSP function %d writes pitch %d, roll %d tenths of a degree (he typed 25 and -10; the flight controller had 15 and -20)\n", mspN > at ? mspFn[at] : -1, mspN > at ? (int) (int16_t) (mspData[at][0] | (mspData[at][1] << 8)) : 0, mspN > at ? (int) (int16_t) (mspData[at][2] | (mspData[at][3] << 8)) : 0);
        CHECK(mspN > at && mspFn[at] == 239 && (int16_t) (mspData[at][0] | (mspData[at][1] << 8)) == 25 && (int16_t) (mspData[at][2] | (mspData[at][3] << 8)) == -10);
    }
    // C2 (the thirteenth review, reviewer B's x6). ... the trims typed WHILE IT CALIBRATES ("keep it still": three seconds): 2.5 and -1.0 before, then 3.5 and 0.5
    //    half a second into the job. At "Calibrated: ..." the page showed 2.5 and -1.0 again - what was in hand - still edited, and Save wrote those
    {
        more(); addPages3(); SendCommand((char *) "page LevelView"); CurrentView = LEVELVIEW; CalHead(); CalShow(); loopPolls(600);
        Page &pg = screen.pages["LevelView"];
        pg.boxes["tn2"].txt = "2.5"; pg.boxes["tn3"].txt = "-1.0"; Cal_Was_Edited = true;
        tapAt(5, "Calibrate"); tapAt(2500, "yes"); loopPolls(3200);
        CHECK(CalStep != CAL_IDLE && CalStep != CAL_ATT);                                    // (the calibration is running)
        pg.boxes["tn2"].txt = "3.5"; pg.boxes["tn3"].txt = "0.5";                            // ... and he types
        loopPolls(6000);
        say("C2. trims typed WHILE it calibrated (3.5 and 0.5): the calibration over, the page shows '%s' and '%s'\n", pg.boxes["tn2"].txt.c_str(), pg.boxes["tn3"].txt.c_str());
        CHECK((CalStep == CAL_IDLE || CalStep == CAL_ATT) && pg.boxes["tn2"].txt == "3.5" && pg.boxes["tn3"].txt == "0.5");
        const int at = mspN; tapAt(5, "Save"); loopPolls(1500);
        CHECK(mspN > at && mspFn[at] == 239 && (int16_t) (mspData[at][0] | (mspData[at][1] << 8)) == 35 && (int16_t) (mspData[at][2] | (mspData[at][3] << 8)) == 5);
    }
    // X. THE BLACK BOX PAGE: 45 s typed for "keep recording after disarm" (edited: Save is offered). Erase - asked, answered Yes - and the erase runs to its end.
    {
        more(); addPages3(); SendCommand((char *) "page BlackboxView"); CurrentView = BLACKBOXVIEW; BbHead(); BbShow(); loopPolls(600);
        Page &pg = screen.pages["BlackboxView"];
        CHECK(pg.boxes["tn3"].txt == "10");
        pg.boxes["tn3"].txt = "45"; Bb_Was_Edited = true;
        tapAt(5, "Erase"); tapAt(2500, "yes"); loopPolls(3000);
        say("X. 45 s typed; Erase - Yes. Right behind the question the page shows '%s' (kept)\n", pg.boxes["tn3"].txt.c_str());
        CHECK(pg.boxes["tn3"].txt == "45");
        loopPolls(6000);
        say("   the erase over (the step is %s; the message: '%s'): THE PAGE NOW SHOWS '%s'; still edited: %d\n", BbStep == BB_IDLE ? "idle" : "busy", pg.boxes["busy"].txt.c_str(), pg.boxes["tn3"].txt.c_str(), (int) Bb_Was_Edited);
        CHECK(BbStep == BB_IDLE);
        CHECK(pg.boxes["tn3"].txt == "45");                                                  // WHAT HE TYPED IS STILL ON THE PAGE
        const int at = mspN; tapAt(5, "Save"); loopPolls(1500);
        say("   Save: MSP function %d writes %u s (he typed 45; the flight controller had 10)\n", mspN > at ? mspFn[at] : -1, mspN > at ? (unsigned) mspData[at][11] : 0u);
        CHECK(mspN > at && mspFn[at] == 81 && mspData[at][11] == 45);
    }
    // X2 (the thirteenth review, reviewer B's x6). ... 45 s typed, Erase - Yes; WHILE IT ERASES he types 30. At "Erased in 1 s" the page showed 45 again, and
    //    Save wrote 45
    {
        more(); addPages3(); SendCommand((char *) "page BlackboxView"); CurrentView = BLACKBOXVIEW; BbHead(); BbShow(); loopPolls(600);
        Page &pg = screen.pages["BlackboxView"];
        pg.boxes["tn3"].txt = "45"; Bb_Was_Edited = true;
        tapAt(5, "Erase"); tapAt(2500, "yes"); loopPolls(3200);
        CHECK(BbStep != BB_IDLE);                                                            // (the erase is running)
        pg.boxes["tn3"].txt = "30";
        loopPolls(6000);
        say("X2. 30 typed WHILE it erased: the erase over (the message: '%s'), the page shows '%s'\n", pg.boxes["busy"].txt.c_str(), pg.boxes["tn3"].txt.c_str());
        CHECK(BbStep == BB_IDLE && pg.boxes["tn3"].txt == "30");
        const int at = mspN; tapAt(5, "Save"); loopPolls(1500);
        CHECK(mspN > at && mspFn[at] == 81 && mspData[at][11] == 30);
    }
    BoundFlag = ModelMatched = false;
'''
sys.exit(lib.build_run('jobs_end', SCENES, extra=EXTRA, more_defines=('BATTERYVIEW', 'BATSENSORSVIEW', 'LEVELVIEW', 'BLACKBOXVIEW', 'BEEPCOMPLETE')))
