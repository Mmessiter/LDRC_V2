#!/usr/bin/env python3
"""WHAT IS TYPED WHILE A SAVE RUNS IS NOT WIPED WHEN THE SAVE FAILS (the fourteenth review, reviewer B's A2 - this is his own scene, with its checks
made checks; 16 Nov 2026).
The thirteenth review's cure kept what was typed while Erase or Calibrate runs (BbFail, CalFail). Seven other failure routines still drew the page
from what the save had GATHERED as it began: a save over the pipe takes a second or more a step, a step with no answer several; the busy message
covers the middle of the page only; he corrects a number meanwhile - and the failure's box came, his correction was gone, the page still "edited",
and Save again wrote the earlier numbers. No word.
 S1 the Battery page (the REAL SaveBattery, BatteryPoll, BatFail, BatGather, BatShow over a pretend pipe): a step of the save is refused - the store
    behind the write, or the write itself with no answer for three seconds - while he types two fields on: they stand as he typed them, and Save
    again writes THEM.
 S2 the draws of the other pages, each under "keep what was typed" (RfKeepTyped), by their own lines: Basics' numbers (BasNum), the Rescue pages'
    whole draw (its numbers, and the switches as their taps left them - the draw put RescueMode and RescueFlip back to what the save had gathered),
    the Filters' numbers (FltNum), Easy tuning's sliders and switch (EzShowSliders). (That each failure routine DRAWS under it is held from the
    source: dev/test_noanswer's typed check, which no longer excuses any of the seven.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, FCS, SRV, BAS, FLT, EZ = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_FcSetup.h', 'RF_Servos.h', 'RF_Basics.h', 'RF_Filters.h', 'RF_Easy.h'))
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
        + block(FCS, 'static const int BAT_BYTES = 15;', 'FLASHMEM void StartBatteryView()')      # ... BatShow, BatGather, BatFail and the REAL BatteryPoll
        + line(FCS, 'FLASHMEM void BatteryWasEdited()')
        + m.lift(FCS, 'FLASHMEM void SaveBattery()'))
# ---- S2: the other pages' draws, as they stand
RESCUE = ('static int RescueMode = 0, RescueFlip = 0; static uint8_t RescueWant[40];\n' + line(RES, 'static const char *RescueModeWords[3]')
          + line(RES, 'FLASHMEM static void RescueField(') + m.lift(RES, 'FLASHMEM static void RescueNumber(') + m.lift(RES, 'FLASHMEM static void RescueTenths(')
          + m.lift(RES, 'FLASHMEM static void RescuePercent(') + m.lift(RES, 'FLASHMEM static void RescueShowPage1()') + m.lift(RES, 'FLASHMEM static void RescueShowPage2()')
          + m.lift(RES, 'FLASHMEM static void RescueShow()'))
OTHERS = (m.lift(BAS, 'FLASHMEM static void BasNum(') + m.lift(FLT, 'FLASHMEM static void FltNum(')
          + 'static int EzPos[5] = { 50, 50, 50, 0, 0 }; static bool EzSpool = true, EzRatesFeel = true;\n' + m.lift(EZ, 'FLASHMEM static void EzShowSliders()'))
EXTRA = r'''
static int mspFn[64], mspN = 0; static uint8_t mspData[64][40]; static uint64_t mspAt[64]; static int failFn = -1, failAfterMs = 150;
int MspAsk(uint8_t fn, const uint8_t *data, int len) { if (mspN < 64) { mspFn[mspN] = fn; memset(mspData[mspN], 0, 40); if (data && len > 0) memcpy(mspData[mspN], data, (size_t) len); mspAt[mspN] = nowUs; ++mspN; } return mspN; }
char PipeRepBody[64] = ""; int PipeRepCode = 200;
static bool PipeReplyReady(int req)
{
    if (!(req >= 1 && req <= mspN)) return false;
    const bool fails = mspFn[req - 1] == failFn;
    if (nowUs - mspAt[req - 1] < (uint64_t) (fails ? failAfterMs : 150) * 1000) return false;
    PipeRepCode = fails ? 503 : 200; if (fails) snprintf(PipeRepBody, sizeof PipeRepBody, "the receiver did not answer");
    return true;
}
static bool PipeReplyLate() { return false; }
static int PipeReplyBytes(uint8_t *b, int n) { memset(b, 0, (size_t) n); return 0; }
static bool BakOffline() { return false; }
static void RfSavedThenLeave(int) {}
static bool ModelSeemsArmed(char *, size_t) { return false; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static int failBoxes = 0; static void FsFail(const char *, const char *) { ++failBoxes; }   // (the failure's box - said, and answered: scene_jobs_end has it so)
''' + REAL + RESCUE + OTHERS + r'''
static void my24(int n) { if (n == 170) SaveBattery(); else more24(n); }
static void addBattery()
{
    Page b; b.id = 72;
    for (const char *t : { "tn0", "tn1", "tn2", "tn3", "tn4", "tn5", "tn6", "tn7", "busy", "t11", "t9" }) b.boxes[t] = { true, 0, "" };
    b.buttons["Save"] = { 0x00, 170, 0x00, 0x00 };
    screen.pages["BatteryView"] = b; screen.pages0 = screen.pages;
    memset(BatWant, 0, sizeof BatWant); BatWant[2] = 6; WrU16(BatWant, 0, 5000); WrU16(BatWant, 9, 420); WrU16(BatWant, 11, 350); WrU16(BatWant, 5, 330); WrU16(BatWant, 7, 430);
    memcpy(BatRaw, BatWant, sizeof BatRaw); BatN = 27; VmN = CmN = 0; BatHave = true; Bat_Was_Edited = false; BatStep = BAT_IDLE; BatMsgUntil = 0;
    mspN = 0; failBoxes = 0; BoundFlag = ModelMatched = true; extra24 = my24;
}
static void loopPolls(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { LoopPass(); BatteryPoll(); nowUs += 500; } }
// (S2) every command this board says, as the screen reads it
static std::vector<std::string> said;
static bool noteCmd(const char *c) { said.push_back(c); return false; }
static int saidLike(const char *part) { int n = 0; for (auto &s : said) n += s.find(part) != std::string::npos; return n; }
'''
SCENES = r'''
    // S1. the Battery page: the step that fails is the store behind the write (250), or the write itself with no answer for three seconds (33)
    for (int fn : { 250, 33 })
    {
        more(); addBattery(); failFn = fn; failAfterMs = fn == 33 ? 3000 : 400;
        SendCommand((char *) "page BatteryView"); CurrentView = BATTERYVIEW; BatHead(); BatShow(); loopPolls(600);
        Page &pg = screen.pages["BatteryView"];
        CHECK(pg.boxes["tn1"].txt == "5000" && pg.boxes["tn5"].txt == "3.50");
        pg.boxes["tn1"].txt = "4500"; Bat_Was_Edited = true;                                 // he types the capacity: 4500 mAh
        tapAt(5, "Save"); loopPolls(300);
        CHECK(BatStep != BAT_IDLE && mspN >= 1 && mspFn[0] == 33 && (mspData[0][0] | (mspData[0][1] << 8)) == 4500);   // (the save runs: it took 4500)
        pg.boxes["tn0"].txt = "5"; pg.boxes["tn5"].txt = "3.60";                              // WHILE IT RUNS he types on, in two fields the busy message leaves open: 5 cells, the warning at 3.60 V
        loopPolls(5000);
        say("S1. the Battery page, step %d of the Save refused %d ms on: typed while it ran 5 cells and 3.60 V - after the failure's box the page shows '%s' cells and '%s' V (failure boxes %d, still edited %d)\n",
            fn, failAfterMs, pg.boxes["tn0"].txt.c_str(), pg.boxes["tn5"].txt.c_str(), failBoxes, (int) Bat_Was_Edited);
        CHECK(BatStep == BAT_IDLE && failBoxes == 1 && Bat_Was_Edited);
        CHECK(pg.boxes["tn0"].txt == "5" && pg.boxes["tn5"].txt == "3.60" && pg.boxes["tn1"].txt == "4500");   // what he typed stands (it showed 6 and 3.50 again)
        failFn = -1; const int at = mspN; tapAt(5, "Save"); loopPolls(800);
        const int cells = mspN > at ? (int) mspData[at][2] : -1, warn = mspN > at ? (mspData[at][11] | (mspData[at][12] << 8)) : -1, cap = mspN > at ? (mspData[at][0] | (mspData[at][1] << 8)) : -1;
        say("    Save again writes %d cells, warning %d, capacity %d (he typed 5, 3.60 and 4500)\n", cells, warn, cap);
        CHECK(cells == 5 && warn == 360 && cap == 4500);                                    // ... and Save again writes THEM (it wrote 6 and 350)
    }
    BoundFlag = ModelMatched = false;
    // S2. the other pages' draws under "keep what was typed", by their own lines
    more(); cmdScript = noteCmd;
    //  - Basics: a typed number is not written; without the keep it is
    said.clear(); RfKeepTyped = true; BasNum("tn5", 14); RfKeepTyped = false; CHECK(said.empty());
    BasNum("tn5", 14); loopFor(50); CHECK(saidLike("tn5.txt=\"14\"") == 1);
    //  - the Filters: the same
    said.clear(); RfKeepTyped = true; FltNum("tn2", 120); RfKeepTyped = false; CHECK(said.empty());
    FltNum("tn2", 120); loopFor(50); CHECK(saidLike("tn2.txt=\"120\"") == 1);
    //  - the Rescue pages: no NUMBER is drawn, and what is in hand stays as the taps left it (the draw put both back to what the save had gathered) - and
    //    (the fifteenth review) THE PARTS THAT TURN BY THEMSELVES ARE WRITTEN AS THEY ARE IN HAND: the two switches, page 2's word
    for (uint8_t view : { (uint8_t) RESCUEVIEW, (uint8_t) RESCUE2VIEW })
    {
        CurrentView = view; memset(RescueWant, 0, sizeof RescueWant); RescueWant[0] = 0; RescueWant[1] = 0;   // (the save gathered: rescue off, no flip)
        RescueMode = 2; RescueFlip = 1;                                                      // (tapped while it ran: on, flip)
        said.clear(); RfKeepTyped = true; RescueShow(); RfKeepTyped = false; loopFor(50);
        if (view == RESCUEVIEW) CHECK(said.size() == 2 && saidLike("tn0.val=1") == 1 && saidLike("tn1.val=1") == 1 && RescueMode == 2 && RescueFlip == 1);
        else CHECK(said.size() == 1 && saidLike("tn0.txt=\"Level & hold height\"") == 1 && RescueMode == 2 && RescueFlip == 1);
        RescueShow(); loopFor(50); CHECK(!said.empty() && RescueMode == 0);                   // (without the keep: the page as gathered - the Save's own end, the read)
    }
    //  - Easy tuning: the sliders and the switch are left; the rows the rates type does not cover are still shown or hidden
    CurrentView = EASYVIEW; said.clear(); RfKeepTyped = true; EzShowSliders(); RfKeepTyped = false; loopFor(50);
    say("S2. Easy tuning's draw under the keep: %d commands, of them %d of a slider or the switch\n", (int) said.size(), saidLike(".val="));
    CHECK(saidLike(".val=") == 0 && saidLike("vis ") == 8);
    said.clear(); EzShowSliders(); loopFor(50); CHECK(saidLike(".val=") == 6 && saidLike("vis ") == 8);
    cmdScript = nullptr;
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('save_fails', SCENES, extra=EXTRA, more_defines=('BATTERYVIEW', 'BATSENSORSVIEW', 'LEVELVIEW', 'BLACKBOXVIEW', 'BEEPCOMPLETE', 'RESCUEVIEW', 'RESCUE2VIEW', 'EASYVIEW')))
