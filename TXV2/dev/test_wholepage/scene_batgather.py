#!/usr/bin/env python3
"""R10-B exp 5: THE BATTERY SENSORS PAGE'S GATHER KEEPS THE WRONG THING. RF_FcSetup.h BatGather has KEEP_WHOLE(want, BatWant) - but on
the sensors page (BATSENSORSVIEW) it writes VmWant and CmWant (the FC pads' voltage scale, current scale and offset), which no keep
holds: "no answer" -> "" -> 0, held to its range, STAYS there. dev/test_noanswer's page_lint ("every routine that gathers has its
keep") passes it: it looks for a KEEP_WHOLE, not for what is kept. Real routines: BatGather, FieldNumber, FieldHundredths, the page's
own block (RF_FcSetup.h, RF_Rescue.h) over the pretend screen."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RES, FCS, SRV = (m.release(m.src('include/' + f)) for f in ('RF_Rescue.h', 'RF_FcSetup.h', 'RF_Servos.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
REAL = (line(RES, 'FLASHMEM static uint16_t RdU16(') + m.lift(RES, 'FLASHMEM static void WrU16(') + line(SRV, 'FLASHMEM static int RdS16(')
        + m.lift(RES, 'FLASHMEM static long FieldNumber(') + m.lift(FCS, 'FLASHMEM static int FieldHundredths(') + m.lift(FCS, 'FLASHMEM static void WrS16(')
        + line(FCS, 'static uint8_t BatRaw[40], BatWant[40];') + line(FCS, 'static uint8_t VmRaw[48], VmWant[48], CmRaw[48], CmWant[48];') + line(FCS, 'static int VmN = 0, CmN = 0;')
        + line(FCS, 'static bool BatHave = false, Bat_Was_Edited = false, BatSame = true;')
        + line(FCS, 'FLASHMEM static bool BatVmThere()') + line(FCS, 'FLASHMEM static bool BatCmThere()') + line(FCS, 'FLASHMEM static bool BatVmShown()') + line(FCS, 'FLASHMEM static bool BatCmShown()')
        + m.lift(FCS, 'FLASHMEM static void BatGather()'))
EXTRA = REAL + r'''
static void addSensors()
{
    Page s; s.id = 75; for (const char *t : { "tn8", "tn9", "tn10", "t11", "t9" }) s.boxes[t] = { true, 0, "" };
    s.boxes["tn8"].txt = "110"; s.boxes["tn9"].txt = "400"; s.boxes["tn10"].txt = "-5"; s.numberBoxes = { "tn10box" };
    screen.pages["BatSensorsView"] = s; screen.pages0 = screen.pages;
    memset(BatWant, 0, sizeof BatWant); memset(VmWant, 0, sizeof VmWant); memset(CmWant, 0, sizeof CmWant);
    BatHave = true; BatWant[3] = 1; BatWant[4] = 1; VmN = 9; CmN = 8;                 // both sources: FC pads
    VmWant[0] = 1; VmWant[1] = 7; WrU16(VmWant, 4, 110);                               // voltage scale 110
    CmWant[0] = 1; CmWant[1] = 6; WrS16(CmWant, 4, 400); WrS16(CmWant, 6, -5);         // current scale 400, offset -5
    memcpy(VmRaw, VmWant, sizeof VmRaw); memcpy(CmRaw, CmWant, sizeof CmRaw); memcpy(BatRaw, BatWant, sizeof BatRaw);
}
'''
SCENES = r'''
    // the sensors page as the flight controller has it: voltage scale 110, current scale 400, offset -5. The pilot types 112 for the voltage
    // scale; the gather (a Save, "< Back", OK: each calls it) - and the current scale's box has no answer (one "which page?" answer lost)
    more(); addSensors(); SendCommand((char *) "page BatSensorsView"); CurrentView = BATSENSORSVIEW; loopFor(600); { char t[8]; GetText((char *) "t9", t, sizeof t); } loopFor(50);
    screen.pages["BatSensorsView"].boxes["tn8"].txt = "112";
    { const uint32_t lost0 = BoxesLost; BoxesLostAtWork = BoxesLost; screen.mute.insert("tn9"); holdCatchUp = true;
      BatGather();
      say("B1. the Battery sensors page's gather, the current scale's box unanswered: boxes lost %u (WorkLostABox %d);\n    in hand now: voltage scale %u (was 110, typed 112), current scale %d (was 400), offset %d (was -5); the same as the flight controller's: voltage %d, current %d\n",
          (unsigned) (BoxesLost - lost0), (int) (BoxesLost != BoxesLostAtWork), (unsigned) RdU16(VmWant, 4), RdS16(CmWant, 4), RdS16(CmWant, 6), (int) !memcmp(VmWant, VmRaw, 9), (int) !memcmp(CmWant, CmRaw, 8));
      CHECK(BoxesLost != lost0);
      CHECK(RdU16(VmWant, 4) == 110 && RdS16(CmWant, 4) == 400 && RdS16(CmWant, 6) == -5); }   // what "A PAGE'S FIELDS ARE TAKEN WHOLE, OR NOT AT ALL" promises: a gather that lost a box has changed nothing
'''
sys.exit(lib.build_run('batgather', SCENES, extra=EXTRA, more_defines=('BATTERYVIEW', 'BATSENSORSVIEW'), sanitize=False))
