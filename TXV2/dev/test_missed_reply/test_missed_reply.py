#!/usr/bin/env python3
"""Host test of B156 (29 Oct 2026, the day after Mehul's RAW 420 took off with no aileron): a NUMBER box the screen does not
answer for never reaches the flight controller or the card. GetValue (Nextion.h) returns 65535 when the screen never answers
('q' within 400 ms, ONE ask: a second ask would take the first's late reply as the next box's answer); the PIDs page and both governor pages took that as the value - a PID word of 65535, a head
speed of 65535, every byte field 255 - and B152's guard covered only the TEXT boxes (GetText). Now GetValue sets
NextionTextMissed as GetText does, and the three pages clear it, gather, then ask RfFieldsMissed before anything is queued
for the model or kept in the model's bank on the card.

The real GetValue and RfFieldsMissed (lifted from Nextion.h) over a fake screen; the pages' own gather-and-save functions
(lifted from RF_PIDs.h, RF_Governor_Profile.h, RF_Governor_Global.h) over fakes of the queue, the pipe and the card.
   python3 dev/test_missed_reply/test_missed_reply.py"""
import os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
def src(name): return open(os.path.join(INC, name), encoding='utf-8', errors='replace').read()
NEXTION, PIDS, GOVP, GOVG, DEFS = src('Nextion.h'), src('RF_PIDs.h'), src('RF_Governor_Profile.h'), src('RF_Governor_Global.h'), src('1Definitions.h')

def lift(text, head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = text.split('\n')
    for i, l in enumerate(lines):
        if l.startswith(head):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
            break
    raise SystemExit('cannot lift ' + head)

def define(name):
    m = re.search(r'#define\s+' + name + r'\s+(\d+)', DEFS)
    if not m: raise SystemExit('no #define ' + name + ' in 1Definitions.h')
    return m.group(1)

PRE = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <string>
#include <map>
#include <set>
#include <vector>
#define FLASHMEM
#define CRUMB(x)
#define MAX_PID_WORDS %(MAX_PID_WORDS)s
#define GOV_PROFILE_PAYLOAD_SIZE %(GOV_PROFILE_PAYLOAD_SIZE)s
#define GOV_CONFIG_PAYLOAD_SIZE %(GOV_CONFIG_PAYLOAD_SIZE)s
#define GOV_ACK_PAYLOAD_SIZE %(GOV_ACK_PAYLOAD_SIZE)s
#define BANKS_USED 6
#define SEND_GOV_WRITE_CONFIG1 31
#define SEND_GOV_WRITE_CONFIG2 32
#define SEND_GOV_WRITE_CONFIG3 33
enum { BEEPMIDDLE = 1, BEEPCOMPLETE, WHAHWHAHMSG };
static const uint16_t Gray = 0x8410;
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %%d: %%s\n", __LINE__, #c); } } while (0)

// ---- the screen: a value per box; a box in `silent` never answers; a box in `lateBy` answers on its n-th ask
static std::map<std::string, long> values; static std::set<std::string> silent; static std::map<std::string, int> lateBy, asks;
static int delays = 0;
static void DelayWithDog(int) { ++delays; }
static uint32_t getvalue(char *nbox)   // (Nextion.h's own: 'q' + four bytes, or 65535 = THERE WAS AN ERROR)
{
    const std::string n = nbox; ++asks[n];
    if (silent.count(n)) return 65535;
    if (lateBy.count(n) && asks[n] < lateBy[n]) return 65535;
    return values.count(n) ? (uint32_t) values[n] : 0;
}
static bool NextionTextMissed = false;
static std::vector<int> sounds; static int boxes = 0; static std::string lastBox;
static void PlaySound(int s) { sounds.push_back(s); }
static void MsgBox(char *, char *m) { ++boxes; lastBox = m; }
%(GETVALUE)s
%(FIELDSMISSED)s

// ---- the pages' surroundings: the queue, the pipe, the card
static std::vector<std::string> cmds; static std::vector<int> queued; static int saves = 0, pidWrites = 0, govWrites = 0, bankChecks = 0;
static bool live = true, armed = false, pipeBlocked = false;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendValue(char *n, int v) { values[n] = v; }
static void SaveOneModel(uint32_t) { ++saves; }
static bool RfLive() { return live; }
static bool ModelSeemsArmed(char *why, size_t n) { if (armed) snprintf(why, n, "armed"); return armed; }
static bool RfPipeBlocked(char *why, size_t n) { if (pipeBlocked) snprintf(why, n, "no pipe"); return pipeBlocked; }
static bool RfBlockNotLoaded(bool loaded, const char *, const char *) { return !loaded; }
static void BankCheck(bool, int, void (*fn)(), const char *) { ++bankChecks; fn(); }
static void AddParameterstoQueue(int q) { queued.push_back(q); }
static bool GetConfirmation(char *, char *) { return true; }
static uint32_t ModelNumber = 1; static int Bank = 2; static bool BlockBankChanges = false;
// PIDs
char PID_Labels[17][4] = {"n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15", "n16"};
uint16_t PID_Values[MAX_PID_WORDS], PID_Boost_Values[3], PID_HSI_Offset_Values[2];
uint16_t Saved_PID_Values[MAX_PID_WORDS + 5][BANKS_USED];
static bool PIDS_Loaded = true, PIDS_Were_Edited = true;
static void PIDMsg(const char *, uint16_t) {}
static void HidePIDMsg() {}
static void PidQueueWrite() { ++pidWrites; }
// governor (profile and global share the payload buffers, as on the Teensy)
static uint8_t GovAckPayload[GOV_ACK_PAYLOAD_SIZE], GovWritePayload[GOV_ACK_PAYLOAD_SIZE];
static uint8_t Saved_GOV_Profiles_Values[GOV_PROFILE_PAYLOAD_SIZE][BANKS_USED], Saved_GOV_Config_Values[GOV_CONFIG_PAYLOAD_SIZE];
static bool GOV_Loaded = true, GOVS_PROFILE_Were_Edited = true, GOVS_GLOBAL_Were_Edited = true, LedWasGreen = true;
static void ShowGOVMsg(const char *, uint16_t) {}
static void HideGOVMsg() {}
static void GovQueueWrite() { ++govWrites; }
static void ShowGOVConfigMsg(const char *, uint16_t) {}
static void HideGOVConfigMsg() {}
static void ShowLocalGovConfigBank() {}
static bool allGlobalIn = true; static bool AllGlobalConfigBytesReceived() { return allGlobalIn; }
'''

MAIN = r'''
static void screen() {   // every box answers: PIDs n0..n16 = 10..26, governor profile n0 = 2100 and n1..n13 = 1..13, global as the Havoc
    values.clear(); silent.clear(); lateBy.clear(); asks.clear();
    for (int i = 0; i < 17; ++i) values[PID_Labels[i]] = 10 + i;
    sounds.clear(); cmds.clear(); queued.clear(); boxes = saves = pidWrites = govWrites = bankChecks = delays = 0; lastBox.clear();
    NextionTextMissed = false; PIDS_Were_Edited = GOVS_PROFILE_Were_Edited = GOVS_GLOBAL_Were_Edited = true; BlockBankChanges = false;
    memset(Saved_PID_Values, 0, sizeof(Saved_PID_Values)); memset(Saved_GOV_Profiles_Values, 0, sizeof(Saved_GOV_Profiles_Values));
    memset(Saved_GOV_Config_Values, 0, sizeof(Saved_GOV_Config_Values)); memset(GovWritePayload, 0, sizeof(GovWritePayload));
    for (int i = 0; i < GOV_ACK_PAYLOAD_SIZE; ++i) GovAckPayload[i] = (uint8_t) (100 + i);
}
static void govScreen() {   // the governor pages' boxes (the same names as the PIDs page's: n0 .. n30, a page at a time)
    values["n0"] = 2100; for (int i = 1; i <= 13; ++i) { char n[8]; snprintf(n, sizeof n, "n%d", i); values[n] = i; }
    values["n14"] = 3; values["n15"] = 20; values["n17"] = 30; values["n18"] = 40; values["n19"] = 50; values["n20"] = 60; values["n21"] = 70;
    values["n22"] = 80; values["n28"] = 0; values["n29"] = 50; values["n30"] = 60;
}
static bool said(const char *w) { return lastBox.find(w) != std::string::npos; }
static bool noMissFlag() { return !NextionTextMissed; }
static bool storedNo65535() { for (int i = 0; i < MAX_PID_WORDS + 5; ++i) for (int b = 0; b < BANKS_USED; ++b) if (Saved_PID_Values[i][b] == 65535) return false; return true; }
static bool govNo255() { for (int i = 1; i < 16; ++i) if (GovWritePayload[i] == 255) return false; return true; }

int main() {
    // ---- GetValue itself: a box that answers is read; one that answers on its third ask is read, no flag; one that never answers = 65535 + the flag
    screen(); values["n3"] = 77;
    CHECK(GetValue((char *) "n3") == 77); CHECK(asks["n3"] == 1); CHECK(noMissFlag());
    lateBy["n4"] = 3; CHECK(GetValue((char *) "n4") == 65535); CHECK(asks["n4"] == 1); CHECK(NextionTextMissed); NextionTextMissed = false;   // ONE ask (B156): a late reply is a miss, never the next box's answer
    silent.insert("n5"); CHECK(GetValue((char *) "n5") == 65535); CHECK(asks["n5"] == 1); CHECK(NextionTextMissed);
    CHECK(RfFieldsMissed("page X")); CHECK(boxes == 1); CHECK(said("NOTHING was sent")); CHECK(noMissFlag());   // said once, then clear
    CHECK(!RfFieldsMissed("page X")); CHECK(boxes == 1);
    CHECK(sounds.size() == 1 && sounds[0] == WHAHWHAHMSG);

    // ---- PIDs, model connected: every box answers -> the write is queued into this bank, the words as the boxes
    live = true; screen(); SendEditedPIDs();
    CHECK(pidWrites == 1); CHECK(bankChecks == 1); CHECK(boxes == 0); CHECK(PID_Values[0] == 10 && PID_Values[11] == 21);
    CHECK(PID_Boost_Values[0] == 22 && PID_HSI_Offset_Values[1] == 26); CHECK(BlockBankChanges);
    // one box never answers -> NOTHING queued, the pilot told, the edit kept for "Save again", the flag clear again
    screen(); silent.insert("n7"); SendEditedPIDs();
    CHECK(pidWrites == 0); CHECK(bankChecks == 0); CHECK(boxes == 1); CHECK(said("did not answer")); CHECK(said("NOTHING was sent"));
    CHECK(PIDS_Were_Edited); CHECK(!BlockBankChanges); CHECK(noMissFlag());
    CHECK(std::find(sounds.begin(), sounds.end(), WHAHWHAHMSG) != sounds.end());
    // the next Save, every box answering, goes
    silent.clear(); SendEditedPIDs(); CHECK(pidWrites == 1); CHECK(boxes == 1);
    // ---- PIDs, no model: the bank on the card is NOT written with a 65535
    live = false; screen(); silent.insert("n0"); SendEditedPIDs();
    CHECK(saves == 0); CHECK(pidWrites == 0); CHECK(boxes == 1); CHECK(storedNo65535()); CHECK(PIDS_Were_Edited);
    screen(); SendEditedPIDs(); CHECK(saves == 1); CHECK(Saved_PID_Values[0][Bank - 1] == 10); CHECK(Saved_PID_Values[16][Bank - 1] == 26); CHECK(!PIDS_Were_Edited);

    // ---- Governor profile, connected: every box answers -> queued, head speed 2100 in bytes 1-2, the bytes as the boxes
    live = true; screen(); govScreen(); SendEditedGovValues();
    CHECK(govWrites == 1); CHECK(boxes == 0); CHECK(GovWritePayload[1] == (2100 & 0xFF) && GovWritePayload[2] == (2100 >> 8));
    CHECK(GovWritePayload[3] == 1 && GovWritePayload[15] == 13); CHECK(GovWritePayload[16] == GovAckPayload[16]);
    // the head speed box never answers -> nothing queued (65535 would have been the head speed); a byte box -> the same (255 would have been it)
    screen(); govScreen(); silent.insert("n0"); SendEditedGovValues();
    CHECK(govWrites == 0); CHECK(boxes == 1); CHECK(said("NOTHING was sent")); CHECK(GOVS_PROFILE_Were_Edited); CHECK(noMissFlag());
    screen(); govScreen(); silent.insert("n8"); SendEditedGovValues();   // Max throttle
    CHECK(govWrites == 0); CHECK(boxes == 1); CHECK(govNo255() || GovWritePayload[10] == 255);   // (the payload may hold it: it is never queued)
    // not connected: the card's bank is not written either
    live = false; screen(); govScreen(); silent.insert("n9"); SendEditedGovValues();
    CHECK(saves == 0); CHECK(boxes == 1); CHECK(Saved_GOV_Profiles_Values[11][Bank - 1] == 0); CHECK(GOVS_PROFILE_Were_Edited);
    screen(); govScreen(); SendEditedGovValues(); CHECK(saves == 1); CHECK(Saved_GOV_Profiles_Values[11][Bank - 1] == 9); CHECK(!GOVS_PROFILE_Were_Edited);

    // ---- Governor global, connected: every box answers -> the three writes queued; a silent box -> none, and B103's choice check still runs after
    live = true; screen(); govScreen(); SendEditedGovConfigValues();
    CHECK(queued.size() == 3); CHECK(boxes == 0); CHECK(GovWritePayload[18] == 3); CHECK(GovWritePayload[22] == 30 && GovWritePayload[23] == 0);
    CHECK(!GOVS_GLOBAL_Were_Edited);
    screen(); govScreen(); silent.insert("n17"); SendEditedGovConfigValues();   // Spoolup: 65535 would have gone as FF FF
    CHECK(queued.empty()); CHECK(boxes == 1); CHECK(said("NOTHING was sent")); CHECK(GOVS_GLOBAL_Were_Edited); CHECK(noMissFlag());
    screen(); govScreen(); silent.insert("n14"); SendEditedGovConfigValues();   // Gov mode: 255 would have been refused by B103 anyway - now it is the miss that is said
    CHECK(queued.empty()); CHECK(boxes == 1); CHECK(said("did not answer"));
    screen(); govScreen(); values["n28"] = 3; SendEditedGovConfigValues();      // B103 still: a throttle type of 3 is refused
    CHECK(queued.empty()); CHECK(said("Not saved: Throttle type is 3."));
    screen(); govScreen(); allGlobalIn = false; SendEditedGovConfigValues();   // B156: a Save before the whole set is in (the boxes were zeroed for the read)
    CHECK(queued.empty()); CHECK(boxes == 1); CHECK(said("not all arrived")); CHECK(asks.empty()); CHECK(GOVS_GLOBAL_Were_Edited); allGlobalIn = true;
    // the kept copy ("Save FC to SD" / not connected): nothing kept with a silent box
    live = false; screen(); govScreen(); silent.insert("n29"); SendEditedGovConfigValues();
    CHECK(saves == 0); CHECK(boxes == 1); CHECK(said("NOTHING was sent")); CHECK(Saved_GOV_Config_Values[40] == 0);
    screen(); govScreen(); SendEditedGovConfigValues(); CHECK(saves == 1); CHECK(Saved_GOV_Config_Values[40] == 50);

    // ---- armed, or no pipe: refused before any box is asked (nothing changes there)
    live = true; armed = true; screen(); govScreen(); SendEditedGovValues(); CHECK(govWrites == 0); CHECK(said("armed")); CHECK(asks.empty()); armed = false;
    pipeBlocked = true; screen(); SendEditedPIDs(); CHECK(pidWrites == 0); CHECK(said("no pipe")); CHECK(asks.empty()); pipeBlocked = false;

    printf("test_missed_reply: %d checks, %d failed\n", checks, fails);
    if (fails == 0) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

def main():
    pre = PRE % {'MAX_PID_WORDS': define('MAX_PID_WORDS'), 'GOV_PROFILE_PAYLOAD_SIZE': define('GOV_PROFILE_PAYLOAD_SIZE'),
                 'GOV_CONFIG_PAYLOAD_SIZE': define('GOV_CONFIG_PAYLOAD_SIZE'), 'GOV_ACK_PAYLOAD_SIZE': define('GOV_ACK_PAYLOAD_SIZE'),
                 'GETVALUE': lift(NEXTION, 'uint32_t GetValue(char *nbox)'), 'FIELDSMISSED': lift(NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)')}
    body = (lift(PIDS, 'FLASHMEM void ReadEditedPIDs()') + lift(PIDS, 'FLASHMEM void SaveToLocalBank()') + lift(PIDS, 'FLASHMEM void SendEditedPIDs()')
            + lift(GOVP, 'FLASHMEM void LoadGovWritePayload()') + lift(GOVP, 'FLASHMEM void SaveToLocalGovBank()') + lift(GOVP, 'FLASHMEM void SendEditedGovValues()')
            + lift(GOVG, 'FLASHMEM bool GovChoiceBad(const uint8_t *p, const char *what)') + lift(GOVG, 'FLASHMEM void LoadGovConfigWritePayload()')
            + lift(GOVG, 'FLASHMEM void SaveToLocalGovGLOBAL()') + lift(GOVG, 'FLASHMEM void SendEditedGovConfigValues()'))
    # the guards must be in the gather-and-save functions themselves, not only in this test's expectations
    for fn, text in (('SaveToLocalBank', PIDS), ('SendEditedPIDs', PIDS), ('SaveToLocalGovBank', GOVP), ('SendEditedGovValues', GOVP),
                     ('SaveToLocalGovGLOBAL', GOVG), ('SendEditedGovConfigValues', GOVG)):
        f = lift(text, 'FLASHMEM void ' + fn + '()')
        if 'NextionTextMissed = false' not in f or 'RfFieldsMissed(' not in f: sys.exit(fn + ' does not clear NextionTextMissed and ask RfFieldsMissed (B156)')
    if 'NextionTextMissed = true' not in lift(NEXTION, 'uint32_t GetValue(char *nbox)'): sys.exit('GetValue does not set NextionTextMissed on a miss (B156)')
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(pre + '#include <algorithm>\n' + body + MAIN)
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-Wno-unused-but-set-variable',
                        '-fsanitize=address,undefined', '-o', os.path.join(d, 'test_missed_reply'), cpp], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-4000:] + '\ncompile failed')
    return subprocess.run([os.path.join(d, 'test_missed_reply')]).returncode

if __name__ == '__main__': sys.exit(main())
