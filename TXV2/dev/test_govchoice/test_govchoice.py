#!/usr/bin/env python3
"""Host test of B103 (15 Oct 2026, the Havoc's diff: "###ERROR IN diff: CORRUPTED CONFIG: gov_throttle_type = 3"):
the Governor (global) page never sends, keeps or restores a governor mode outside 0 - 4 or a throttle type outside 0 - 2
(Rotorflight 2.3's lists: OFF LIMIT DIRECT ELECTRIC NITRO; NORMAL SWITCH FUNCTION). The page's own functions, lifted out of
RF_Governor_Global.h by name, compiled on the Mac over fakes of the screen, the queue and the card.
   python3 dev/test_govchoice/test_govchoice.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Governor_Global.h'), encoding='utf-8', errors='replace').read()

def lift(head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = SRC.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
            break
    raise SystemExit('cannot lift ' + head)

PRE = r'''
#define RFGOVERNORVIEW_GLOBAL 60
static int CurrentView = 60;
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <map>
#include <vector>
#define FLASHMEM
#define GOV_CONFIG_PAYLOAD_SIZE 42
#define GOV_ACK_PAYLOAD_SIZE 59
#define SEND_GOV_WRITE_CONFIG1 31
#define SEND_GOV_WRITE_CONFIG2 32
#define SEND_GOV_WRITE_CONFIG3 33
enum { BEEPMIDDLE = 1, BEEPCOMPLETE, WHAHWHAHMSG };
static const uint16_t Gray = 0x8410;
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static std::map<std::string, long> values; static std::vector<std::string> cmds; static std::vector<int> sounds, queued;
static int boxes = 0, questions = 0, saves = 0; static std::string lastBox; static bool live = true, armed = false;
static uint32_t GetValue(char *n) { return values.count(n) ? (uint32_t) values[n] : 0; }
static bool bigScreen = false; static bool ScreenIsBig() { return bigScreen; }   // B195: start-up + the filters on a 16 MB screen only
static bool NextionTextMissed = false;   // (B156: a box the screen never answered - here every box answers; dev/test_missed_reply has the misses)
char NextionMissedBox[12] = {0}; bool NextionSettledOk = false; static void RfGatherStart() { NextionTextMissed = false; }   // (B187)
static bool AllGlobalConfigBytesReceived() { return true; }   // (B156: the whole set is in, here)
static bool RfFieldsMissed(const char *) { const bool m = NextionTextMissed; NextionTextMissed = false; return m; }
static void SendValue(char *n, int v) { values[n] = v; }
static void SendCommand(char *c) { cmds.push_back(c); }
static void PlaySound(int s) { sounds.push_back(s); }
static void MsgBox(char *, char *m) { ++boxes; lastBox = m; }
static bool confirmAnswer = true;
static bool GetConfirmation(char *, char *p) { ++questions; lastBox = p; return confirmAnswer; }
static void SaveOneModel(uint32_t) { ++saves; }
static void DelayWithDog(int) {}
static bool RfLive() { return live; }
static bool ModelSeemsArmed(char *why, size_t n) { if (armed) snprintf(why, n, "armed"); return armed; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static void AddParameterstoQueue(int q) { queued.push_back(q); }
static void ShowGOVConfigMsg(const char *, uint16_t) {}
static void HideGOVConfigMsg() {}
static void ShowLocalGovConfigBank() {}
enum { VK_GOV_CFG = 6 };   // B165: the read-back itself lives in RF_Verify.h (dev/test_verify); here only that the save asks for it
static bool verifyArmed = false, verifyPending = false; static int armedKind = -1;
static bool RfVerifyArm(uint8_t kind, void (*)()) { armedKind = kind; return verifyArmed; }
static bool RfVerifyPending() { return verifyPending; }
static void GovCfgAskValues() {}
static bool LedWasGreen = true, GOVS_GLOBAL_Were_Edited = false;
static uint32_t ModelNumber = 1;
static uint8_t GovAckPayload[GOV_ACK_PAYLOAD_SIZE], GovWritePayload[GOV_ACK_PAYLOAD_SIZE], Saved_GOV_Config_Values[GOV_CONFIG_PAYLOAD_SIZE];
'''

MAIN = r'''
static void page(int mode, int ttype) {   // the page as the flight controller filled it, then edited
    values.clear(); values["n14"] = mode; values["n15"] = 20; values["n17"] = 3; values["n28"] = ttype; values["n29"] = 50; values["n30"] = 60;
    cmds.clear(); sounds.clear(); queued.clear(); boxes = questions = saves = 0; lastBox.clear(); GOVS_GLOBAL_Were_Edited = true;
}
static bool said(const char *w) { return lastBox.find(w) != std::string::npos; }
int main() {
    // GovChoiceBad itself: the edges of both lists
    { uint8_t p[GOV_CONFIG_PAYLOAD_SIZE] = {0};
      for (int m = 0; m <= 4; ++m) for (int t = 0; t <= 2; ++t) { p[18] = m; p[39] = t; boxes = 0; CHECK(!GovChoiceBad(p, "x")); CHECK(boxes == 0); }
      p[18] = 5; p[39] = 0; boxes = 0; CHECK(GovChoiceBad(p, "Not saved")); CHECK(boxes == 1); CHECK(said("Not saved: Governor mode is 5.")); CHECK(said("0 - 4"));
      p[18] = 3; p[39] = 3; boxes = 0; CHECK(GovChoiceBad(p, "Not saved")); CHECK(boxes == 1); CHECK(said("Not saved: Throttle type is 3.")); CHECK(said("0 - 2"));
      p[18] = 255; p[39] = 255; boxes = 0; CHECK(GovChoiceBad(p, "x")); CHECK(said("Governor mode is 255")); }

    // Save, live: a good page goes (three writes), the Havoc's 3 does not - and the page keeps its edit and its Save
    live = true; page(3, 0); SendEditedGovConfigValues();
    CHECK(queued.size() == 3); CHECK(boxes == 0); CHECK(!GOVS_GLOBAL_Were_Edited); CHECK(GovWritePayload[18] == 3); CHECK(GovWritePayload[39] == 0);
    page(3, 3); SendEditedGovConfigValues();
    CHECK(queued.empty()); CHECK(boxes == 1); CHECK(said("Not saved: Throttle type is 3.")); CHECK(GOVS_GLOBAL_Were_Edited);
    CHECK(sounds.size() == 1 && sounds[0] == WHAHWHAHMSG);
    page(5, 0); SendEditedGovConfigValues();
    CHECK(queued.empty()); CHECK(said("Not saved: Governor mode is 5."));
    page(4, 2); SendEditedGovConfigValues(); CHECK(queued.size() == 3); CHECK(boxes == 0);   // (NITRO, FUNCTION: the last of each list)

    // B165: with the pipe the save is read back - the three writes go, the edited flag stays up for the verdict, no done sound yet;
    // a Save while the last one is still being read back is refused, nothing queued
    verifyArmed = true; page(3, 0); SendEditedGovConfigValues();
    CHECK(queued.size() == 3); CHECK(armedKind == VK_GOV_CFG); CHECK(GOVS_GLOBAL_Were_Edited); CHECK(boxes == 0); CHECK(sounds.size() == 1 && sounds[0] == BEEPMIDDLE);
    verifyArmed = false; armedKind = -1;
    verifyPending = true; page(3, 0); SendEditedGovConfigValues();
    CHECK(queued.empty()); CHECK(boxes == 1); CHECK(said("still")); CHECK(GOVS_GLOBAL_Were_Edited); CHECK(armedKind == -1);
    verifyPending = false;

    // Keep a copy: nothing written to the card with a bad choice
    live = true; memset(Saved_GOV_Config_Values, 0, sizeof(Saved_GOV_Config_Values));
    page(3, 3); SaveToLocalGovGLOBAL();
    CHECK(saves == 0); CHECK(boxes == 1); CHECK(said("Not kept: Throttle type is 3.")); CHECK(Saved_GOV_Config_Values[39] == 0); CHECK(Saved_GOV_Config_Values[18] == 0);
    page(3, 1); SaveToLocalGovGLOBAL();
    CHECK(saves == 1); CHECK(Saved_GOV_Config_Values[18] == 3); CHECK(Saved_GOV_Config_Values[39] == 1);

    // Save with no model: it keeps a copy instead - refused the same way
    live = false; page(3, 3); SendEditedGovConfigValues();
    CHECK(saves == 0); CHECK(queued.empty()); CHECK(said("Not kept: Throttle type is 3."));

    // Restore: a kept copy with a bad choice is not sent, and not even offered
    live = true; LedWasGreen = true; page(3, 0);
    Saved_GOV_Config_Values[18] = 3; Saved_GOV_Config_Values[39] = 3;
    RestoreFromSDGlobalGOV();
    CHECK(queued.empty()); CHECK(questions == 0); CHECK(boxes == 1); CHECK(said("Kept copy not sent: Throttle type is 3."));
    Saved_GOV_Config_Values[39] = 0; page(3, 0); RestoreFromSDGlobalGOV();
    CHECK(queued.size() == 3); CHECK(questions == 1); CHECK(GovWritePayload[39] == 0);
    // B165: the kept copy sent to the flight controller is read back too (no done sound until the verdict)
    verifyArmed = true; page(3, 0); RestoreFromSDGlobalGOV();
    CHECK(queued.size() == 3); CHECK(armedKind == VK_GOV_CFG); CHECK(sounds.empty()); CHECK(!GOVS_GLOBAL_Were_Edited);
    verifyArmed = false; armedKind = -1;

    // B180: a copy never kept (no mark, whatever its bytes - Black Thunder 1's "mode 100") is not offered, let alone sent
    page(3, 0); ClearKept(); Saved_GOV_Config_Values[18] = 3; Saved_GOV_Config_Values[39] = 0;
    RestoreFromSDGlobalGOV();
    CHECK(queued.empty()); CHECK(questions == 0); CHECK(boxes == 1); CHECK(said("No copy of the governor settings"));
    page(3, 0); MarkKept(KEPT_GOV_GLOBAL, 0); RestoreFromSDGlobalGOV();
    CHECK(queued.size() == 3); CHECK(questions == 1);

    // B183: Defaults - Rotorflight 2.3's own values into every box, the page marked edited (Save shown); No leaves the boxes alone
    values.clear(); GOVS_GLOBAL_Were_Edited = false; confirmAnswer = false; GovGlobalDefaults();
    CHECK(values.empty() && !GOVS_GLOBAL_Were_Edited);
    confirmAnswer = true; GovGlobalDefaults();
    CHECK(values["n14"] == 0 && values["n15"] == 25 && values["n22"] == 15 && values["n17"] == 10 && values["n18"] == 3 && values["n19"] == 5 && values["n20"] == 3 && values["n21"] == 5 && values["n28"] == 0 && values["n29"] == 0 && values["n30"] == 0);
    CHECK(GOVS_GLOBAL_Were_Edited && values.size() == 11);
    { uint8_t p[GOV_ACK_PAYLOAD_SIZE] = {0}; p[18] = (uint8_t) values["n14"]; p[39] = (uint8_t) values["n28"]; boxes = 0; CHECK(!GovChoiceBad(p, "x") && boxes == 0); }   // (the defaults pass the page's own gate)

    // B195: a 16 MB screen - Defaults fill start-up and the five filters too (Rotorflight 4.6's own), and Save reads them from the
    // page; a 4 MB screen keeps the bytes as read whatever the hidden boxes hold
    values.clear(); bigScreen = true; confirmAnswer = true; GovGlobalDefaults();
    CHECK(values.size() == 17 && values["n16"] == 20 && values["n23"] == 10 && values["n24"] == 5 && values["n25"] == 50 && values["n26"] == 5 && values["n27"] == 0);
    for (int i = 0; i < GOV_ACK_PAYLOAD_SIZE; ++i) GovAckPayload[i] = (uint8_t)(100 + i);
    values["n14"] = 3; values["n28"] = 0; values["n16"] = 300; values["n23"] = 11; values["n24"] = 12; values["n25"] = 13; values["n26"] = 14; values["n27"] = 15;
    LoadGovConfigWritePayload();
    CHECK(GovWritePayload[20] == (300 & 0xFF) && GovWritePayload[21] == (300 >> 8) && GovWritePayload[34] == 11 && GovWritePayload[35] == 12 && GovWritePayload[36] == 13 && GovWritePayload[37] == 14 && GovWritePayload[38] == 15);
    bigScreen = false; LoadGovConfigWritePayload();
    CHECK(GovWritePayload[20] == 120 && GovWritePayload[21] == 121 && GovWritePayload[34] == 134 && GovWritePayload[38] == 138);
    values.clear(); GovGlobalDefaults(); CHECK(values.size() == 11 && !values.count("n16") && !values.count("n23"));

    // Armed: the old refusal still comes first
    armed = true; page(3, 3); SendEditedGovConfigValues(); CHECK(queued.empty()); CHECK(said("armed")); armed = false;

    printf("test_govchoice: %d checks, %d failed\n", checks, fails);
    if (fails == 0) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

KEPT = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Kept.h'), encoding='utf-8', errors='replace').read()
KEPT_BODY = KEPT[KEPT.index('enum : uint8_t { KEPT_PIDS'):KEPT.index('#endif')]   # (B180: the kept-copy mark the page's keep and restore use)

def main():
    body = PRE + KEPT_BODY
    body += lift('FLASHMEM bool GovChoiceBad(')
    body += lift('FLASHMEM void LoadGovConfigWritePayload()')
    body += lift('FLASHMEM void SaveToLocalGovGLOBAL()')
    body += lift('FLASHMEM void RestoreFromSDGlobalGOV()')
    body += lift('FLASHMEM void SendEditedGovConfigValues()')
    body += lift('FLASHMEM void Gov_Global_Were_Edited()') + lift('FLASHMEM void GovGlobalDefaults()')   # (B183)
    body += MAIN
    d = tempfile.mkdtemp(prefix='test_govchoice_')
    import atexit, shutil as _sh; atexit.register(_sh.rmtree, d, True)   # (17 Oct 2026: 1,800 left behind filled the Mac's disk)
    cpp = os.path.join(d, 'test_govchoice.cpp'); open(cpp, 'w').write(body)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format',
                        '-o', os.path.join(d, 'test_govchoice'), cpp], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout + r.stderr); print('test_govchoice: DID NOT COMPILE'); return 1
    rc = subprocess.run([os.path.join(d, 'test_govchoice')]).returncode
    # B183: the profile page's defaults are Rotorflight 2.3's (pg/pid.c resetPidProfile .governor), and both pages carry the button
    import json
    prof = open(os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Governor_Profile.h'), encoding='utf-8', errors='replace').read()
    ok = 'static const uint16_t d[GOVERNOR_LABELS_COUNT] = {1000, 40, 40, 50, 0, 10, 0, 20, 100, 10, 10, 10, 10, 50};' in prof and 'GOVS_P_Were_Edited();' in prof[prof.index('void GovProfileDefaults()'):]
    pages = os.path.expanduser('~/Documents/GitHub/ESP32-board2/board4/nextion-emulator/sd/hmi/pages')
    for pid, code in ((5, 229), (6, 230)):
        f = os.path.join(pages, '%d.json' % pid)
        if os.path.exists(f):
            comps = json.load(open(f))['comps']
            ok = ok and any(c.get('n') == 'defaults' and c.get('txt') == 'Defaults' and ('va0.val=%d<<8' % code) in (c.get('ev') or {}).get('r', '') for c in comps)
    print('test_govchoice (B183 source + pages): %s' % ('ok' if ok else 'FAIL'))
    return rc or (0 if ok else 1)

if __name__ == '__main__':
    sys.exit(main())
