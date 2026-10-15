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
static void SendValue(char *n, int v) { values[n] = v; }
static void SendCommand(char *c) { cmds.push_back(c); }
static void PlaySound(int s) { sounds.push_back(s); }
static void MsgBox(char *, char *m) { ++boxes; lastBox = m; }
static bool GetConfirmation(char *, char *p) { ++questions; lastBox = p; return true; }
static void SaveOneModel(uint32_t) { ++saves; }
static void DelayWithDog(int) {}
static bool RfLive() { return live; }
static bool ModelSeemsArmed(char *why, size_t n) { if (armed) snprintf(why, n, "armed"); return armed; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static void AddParameterstoQueue(int q) { queued.push_back(q); }
static void ShowGOVConfigMsg(const char *, uint16_t) {}
static void HideGOVConfigMsg() {}
static void ShowLocalGovConfigBank() {}
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

    // Armed: the old refusal still comes first
    armed = true; page(3, 3); SendEditedGovConfigValues(); CHECK(queued.empty()); CHECK(said("armed")); armed = false;

    printf("test_govchoice: %d checks, %d failed\n", checks, fails);
    if (fails == 0) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

def main():
    body = PRE
    body += lift('FLASHMEM bool GovChoiceBad(')
    body += lift('FLASHMEM void LoadGovConfigWritePayload()')
    body += lift('FLASHMEM void SaveToLocalGovGLOBAL()')
    body += lift('FLASHMEM void RestoreFromSDGlobalGOV()')
    body += lift('FLASHMEM void SendEditedGovConfigValues()')
    body += MAIN
    d = tempfile.mkdtemp(prefix='test_govchoice_')
    cpp = os.path.join(d, 'test_govchoice.cpp'); open(cpp, 'w').write(body)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format',
                        '-o', os.path.join(d, 'test_govchoice'), cpp], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout + r.stderr); print('test_govchoice: DID NOT COMPILE'); return 1
    return subprocess.run([os.path.join(d, 'test_govchoice')]).returncode

if __name__ == '__main__':
    sys.exit(main())
