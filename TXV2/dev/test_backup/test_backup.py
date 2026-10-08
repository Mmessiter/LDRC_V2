#!/usr/bin/env python3
"""Host test of the Rotorflight backup (B70): include/RF_Backup.h compiled on the Mac over a fake card, a fake screen and a
fake flight controller on a fake pipe. The file store and its edit marks; the stand-in that answers the pages' reads and
writes from the file when no model is connected (the keys per bank, the servo patch, the indexed inputs); the sweep that
backs everything up; the restore that writes only what differs, one servo or rule at a time, reads it back, stores, and
restarts the FC only when the governor global or the motor block changed; Write edits for the marked keys only.
   python3 dev/test_backup/test_backup.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_Backup.h')
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cctype>
#include <string>
#include <map>
#include <vector>
#define DMAMEM
#define NORMAL 0
#define SAVE_RF_SETTINGS 7
#define RESTORE_RF_SETTINGS 8
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define FILE_READ 0
#define FILE_WRITE 1
#define RFBACKUP_RESTOREVIEW 53
static int CurrentView = 0;
static bool BoundFlag = true, ModelMatched = true, BlockBankChanges = false;
static char ModelName[20] = "Goblin";
static uint8_t Bank = 2, DualRateInUse = 1;
static int CurrentMode = NORMAL;
static uint32_t now = 1000;
static uint32_t millis() { return now; }
// ---- the fake card
static std::map<std::string, std::string> card; static std::map<std::string, bool> dirs;
struct File {
    std::string path; bool w = false, ok = false; size_t pos = 0;
    operator bool() const { return ok; }
    size_t read(char *out, size_t n) { const std::string &s = card[path]; size_t k = 0; while (pos < s.size() && k < n) out[k++] = s[pos++]; return k; }
    size_t write(const char *b, size_t n) { card[path].append(b, n); return n; }
    void close() {}
};
struct FakeSD {
    bool exists(const char *p) { return card.count(p) || dirs.count(p); }
    bool mkdir(const char *p) { dirs[p] = true; return true; }
    bool remove(const char *p) { return card.erase(p) > 0; }
    File open(const char *p, int mode) { File f; f.path = p; f.w = mode == FILE_WRITE; f.ok = mode == FILE_WRITE || card.count(p) > 0; if (f.w && !card.count(p)) card[p] = ""; return f; }
} SD;
// ---- the clock
struct { int Second, Minute, Hour, Wday, Day, Month, Year; } tm;
struct { bool read(decltype(tm) &t) { t.Year = 56; t.Month = 10; t.Day = 8; t.Hour = 12; t.Minute = 30; return true; } } RTC;
static int Gyear = 26, Gmonth = 10, GmonthDay = 8, Ghour = 12, Gminute = 30;
static void ReadTheRTC() {}
// ---- the fake screen
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, rfStarts = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static void RotorFlightStart() { ++rfStarts; }
static bool ModelSeemsArmed(char *, int) { return false; }
// ---- the Version 1 word route (B71): the pages' parameter words, and the telemetry items the file answers with
#define PIDVIEW 45
#define RATESVIEW_RF 46
#define RATESADVANCEDVIEW 48
#define PIDADVANCEDVIEW 49
#define RFGOVERNORVIEW_PROFILE 54
#define RFGOVERNORVIEW_GLOBAL 55
#define SEND_PID_VALUES 9
#define GET_FIRST_6_PID_VALUES 10
#define GET_SECOND_11_PID_VALUES 11
#define SEND_RATES_VALUES 12
#define GET_FIRST_7_RATES_VALUES 13
#define GET_SECOND_6_RATES_VALUES 14
#define SEND_RATES_ADVANCED_VALUES 15
#define GET_RATES_ADVANCED_VALUES_SECOND_8 16
#define GET_RATES_ADVANCED_VALUES_FIRST_7 17
#define SEND_PID_ADVANCED_VALUES 18
#define GET_FIRST_9_ADVANCED_PID_VALUES 19
#define GET_SECOND_9_ADVANCED_PID_VALUES 20
#define GET_THIRD_8_ADVANCED_PID_VALUES 21
#define SEND_GOV_VALUES 27
#define SEND_GOV_CONFIG_VALUES 28
#define SEND_GOV_WRITE_PROFILE1 29
#define SEND_GOV_WRITE_PROFILE2 30
#define SEND_GOV_WRITE_CONFIG1 31
#define SEND_GOV_WRITE_CONFIG2 32
#define SEND_GOV_WRITE_CONFIG3 33
static struct { uint8_t ID; uint16_t word[12]; } Parameters;
static std::map<int, std::vector<uint16_t>> words;   // id -> w1..w11, as the page would load them
static void LoadOneParameter() { auto &v = words[Parameters.ID]; for (int i = 1; i < 12; ++i) Parameters.word[i] = (i - 1 < (int) v.size()) ? v[i - 1] : 0; }
static std::string told; static void TelemetryFromPipe(const char *l) { told = l; }
static bool Reading_PIDS_Now = false, Reading_PIDS_Advanced_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static uint16_t PID_Send_Duration = 1000, PID_Advanced_Send_Duration = 1000, RATES_Send_Duration = 1000, Rates_Advanced_Send_Duration = 1000;
static uint32_t GOV_Send_Duration = 1000, GOV_Config_Send_Duration = 1000;
static uint8_t RotorFlight_V = 2;
#define ROTORFLIGHTVIEW 47
static int PipeState = 2; static bool ModalWaits = false;
static bool RfPipeBlocked(char *, int) { return false; }
static bool RfNeedsModel(char *, int) { return false; }
// ---- the pipe: PipeHttp.h's names, a fake flight controller behind it
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = ""; static uint32_t PipeReqSentMs = 0;
bool PipeReplyReady(int id) { return PipeRepId == id; }
bool PipeReplyLate() { return false; }
int PipeReplyBytes(uint8_t *out, int max) { int n = 0; const char *p = PipeRepBody; while (p[0] && p[1] && n < max) { char h[3] = {p[0], p[1], 0}; out[n++] = (uint8_t) strtol(h, nullptr, 16); p += 2; } return n; }
struct FcReq { int fn; std::string data; };
static std::vector<FcReq> fcLog;
static std::map<std::string, std::string> fc;   // the FC's images by the file's keys
static int fcPid = 1, fcRate = 0, fcPidBanks = 3, fcRateBanks = 3;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static std::string fcKey(int fn, const uint8_t *d, int n) {
    char k[16];
    if (fn == 112 || fn == 94 || fn == 148 || fn == 146) snprintf(k, sizeof k, "%d.%d", fn, fcPid);
    else if (fn == 111) snprintf(k, sizeof k, "%d.%d", fn, fcRate);
    else if ((fn == 174 || fn == 154) && n >= 1) snprintf(k, sizeof k, "%d.%02X", fn, d[0]);
    else snprintf(k, sizeof k, "%d", fn);
    return k;
}
static int readOf(int w) {   // the plain pairs the restore writes
    static const int pairs[][2] = {{93,92},{37,36},{147,146},{149,148},{202,112},{95,94},{204,111},{143,142},{43,42},{11,10},{39,38},{62,61},{239,240},{97,96},{220,126},{65,64},{45,44},{67,66},{76,75},{51,50},{74,73},{33,32},{216,123}};
    for (auto &p : pairs) if (p[0] == w) return p[1]; return 0;
}
static void fcReply(int code, const std::string &body) { PipeRepCode = code; strncpy(PipeRepBody, body.c_str(), sizeof(PipeRepBody) - 1); PipeRepBody[sizeof(PipeRepBody) - 1] = 0; PipeRepId = PipeReqId; }
bool BakOffline(); bool BakOfflineAnswer(uint8_t, const uint8_t *, int);
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId; PipeReqSentMs = now;
    if (BakOffline() && BakOfflineAnswer(fn, data, len)) { PipeRepId = PipeReqId; return PipeReqId; }
    fcLog.push_back({fn, hexOf(data, len)});
    if (fn == 101) { uint8_t b[32] = {0}; b[23] = fcPid; b[25] = fcRate; b[24] = fcPidBanks; b[26] = fcRateBanks; fcReply(200, hexOf(b, 32)); return PipeReqId; }
    if (fn == 210) { if (data[0] & 0x80) fcRate = data[0] & 0x7F; else fcPid = data[0]; fcReply(200, ""); return PipeReqId; }
    if (fn == 250 || fn == 68) { fcReply(200, ""); return PipeReqId; }
    const int r = readOf(fn);
    if (r && len > 0) { fc[fcKey(r, nullptr, 0)] = hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 171 && len == 7) { fc[fcKey(174, data, 1)] = hexOf(data + 1, 6); fcReply(200, ""); return PipeReqId; }
    if (fn == 155 && len >= 2) { fc[fcKey(154, data, 1)] = hexOf(data + 1, len - 1); fcReply(200, ""); return PipeReqId; }
    if (fn == 212 && len == 17) { std::string &img = fc["120"]; const int i = data[0]; if ((int) img.size() >= 2 + (i + 1) * 32) img.replace(2 + i * 32, 32, hexOf(data + 1, 16)); fcReply(200, ""); return PipeReqId; }
    if (fn == 173 && len == 8) { std::string &img = fc["172"]; const int i = data[0]; if ((int) img.size() >= (i + 1) * 14) img.replace(i * 14, 14, hexOf(data + 1, 7)); fcReply(200, ""); return PipeReqId; }
    if (fn == 222 && len >= 28) { std::string h = hexOf(data, len); fc["131"] = h.substr(0, 12) + fc["131"].substr(12, 2) + h.substr(12); fcReply(200, ""); return PipeReqId; }
    if (fn == 81 && len >= 12) { fc["80"] = fc["80"].substr(0, 2) + hexOf(data, len); fcReply(200, ""); return PipeReqId; }
    if (fn == 78 && len == 4) { std::string &img = fc["77"]; const int i = data[0]; if ((int) img.size() >= (i + 1) * 6) img.replace(i * 6, 6, hexOf(data + 1, 3)); fcReply(200, ""); return PipeReqId; }
    if (fn == 57 || fn == 41) { const int frame = fn == 57 ? 8 : 7; std::string &img = fc[fn == 57 ? "56" : "40"]; const int n = strtol(img.substr(0, 2).c_str(), nullptr, 16); for (int i = 0; i < n; ++i) { const int f = 2 + i * frame * 2; if (img.substr(f + 2, 2) == hexOf(data, 1)) img.replace(f + 6, (frame - 3) * 2, hexOf(data + 1, len - 1)); } fcReply(200, ""); return PipeReqId; }
    if (fn == 35 && len == 7) { const int i = data[0]; std::string &rg = fc["34"], &ex = fc["238"]; if ((int) rg.size() >= (i + 1) * 8) rg.replace(i * 8, 8, hexOf(data + 1, 4)); if ((int) ex.size() >= 2 + (i + 1) * 6) ex.replace(2 + i * 6 + 2, 4, hexOf(data + 5, 2)); fcReply(200, ""); return PipeReqId; }
    const std::string k = fcKey(fn, data, len);
    if (fc.count(k)) fcReply(200, fc[k]); else fcReply(404, "unknown");
    return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static std::string rep(const char *s, int n) { std::string o; for (int i = 0; i < n; ++i) o += s; return o; }
static void fillFc() {   // a believable flight controller: 3 banks, 4 servos, 2 rules, 2 meters, 2 modes, 4 failsafe channels
    fc.clear();
    for (int b = 0; b < 3; ++b) { char k[16];
        snprintf(k, sizeof k, "112.%d", b); fc[k] = rep("1A", 50); snprintf(k, sizeof k, "94.%d", b); fc[k] = rep("2B", 20);
        snprintf(k, sizeof k, "148.%d", b); fc[k] = rep("3C", 14); snprintf(k, sizeof k, "146.%d", b); fc[k] = "0101" + rep("05", 26);
        snprintf(k, sizeof k, "111.%d", b); fc[k] = rep("4D", 25); }
    fc["142"] = rep("5E", 30); fc["42"] = rep("06", 21);
    for (int i = 1; i <= 4; ++i) { char k[16]; snprintf(k, sizeof k, "174.%02X", i); fc[k] = "E803" "18FC" "E803"; }
    fc["120"] = "04" + rep("1122334455667788990A0B0C0D0E0F10", 4);
    fc["172"] = rep("01020304050607", 2);
    fc["131"] = rep("07", 6) + "02" + rep("08", 22);
    fc["80"] = "01" + rep("09", 12);
    fc["10"] = "476F626C696E"; fc["36"] = "08000060"; fc["38"] = rep("00", 6); fc["61"] = "05"; fc["240"] = rep("00", 4); fc["96"] = rep("01", 5);
    fc["126"] = rep("00", 4); fc["64"] = "0001020304050607"; fc["44"] = rep("00", 20); fc["66"] = rep("00", 10); fc["75"] = rep("00", 12); fc["50"] = "0000";
    fc["73"] = rep("01", 8) + rep("AA", 4) + rep("00", 40); fc["92"] = "0001640000320000000000000000000000000006190014F0000214"; fc["32"] = rep("00", 10); fc["123"] = rep("00", 6);
    fc["154.00"] = fc["154.01"] = fc["154.02"] = rep("00", 12);
    fc["56"] = "02" "08" "0A" "01" "6E" "05" "0A" "00" "00" "08" "0B" "01" "6E" "05" "0A" "00" "00"; fc["40"] = "02" "07" "0A" "01" "90" "01" "00" "00" "07" "0B" "01" "90" "01" "00" "00";
    fc["34"] = "0000" "0607" "0100" "0809"; fc["238"] = "02" "00" "0000" "00" "0101" "0000" ;
    fc["77"] = "00E803" "00E803" "00E803" "01DC05";
}
static int runUntilDone(int limit = 4000) { int n = 0; while (BakJob != BAK_JOB_NONE && n < limit) { BackupRun(); now += 50; ++n; } return n; }
int main() {
    // 1. the store: set, get, edits
    strcpy(Bak, "rfb=1\nmodel=Goblin\nedits=\n"); BakLoaded = true; strcpy(BakModel, "Goblin");
    char v[64];
    CHECK(BakSet("92", "AABB")); CHECK(BakGet("92", v, sizeof v) == 4 && strcmp(v, "AABB") == 0);
    CHECK(BakSet("92", "CC")); CHECK(BakGet("92", v, sizeof v) == 2 && strcmp(v, "CC") == 0); CHECK(BakGet("edits", v, sizeof v) == 0);
    BakMarkEdit("92"); BakMarkEdit("146.2"); BakMarkEdit("92"); CHECK(BakGet("edits", v, sizeof v) > 0 && strcmp(v, "92,146.2") == 0); CHECK(BakEdited("146.2") && !BakEdited("146.1"));
    CHECK(BakSave()); CHECK(card.count("/rfbak/Goblin.rfb") == 1); CHECK(BakLoad("Goblin") && BakEdited("92"));
    // 2. offline: the pages read and write the file
    BoundFlag = false; fillFc(); strcpy(Bak, "rfb=1\nmodel=Goblin\nedits=\n"); for (auto &kv : fc) BakSet(kv.first.c_str(), kv.second.c_str()); BakSet("edits", ""); BakSave();
    CHECK(BakOffline());
    int id = MspAsk(92, nullptr, 0); CHECK(PipeReplyReady(id) && PipeRepCode == 200 && strcmp(PipeRepBody, fc["92"].c_str()) == 0);
    { uint8_t b[27] = {0}; b[2] = 90; id = MspAsk(93, b, 27); CHECK(PipeReplyReady(id) && PipeRepCode == 200); CHECK(BakGet("92", v, sizeof v) == 54 && strncmp(v, "00005A", 6) == 0); CHECK(BakEdited("92")); }
    { uint8_t d = 2; MspAsk(210, &d, 1); id = MspAsk(146, nullptr, 0); CHECK(PipeRepCode == 200 && strcmp(PipeRepBody, fc["146.2"].c_str()) == 0);
      uint8_t r[28] = {1, 0}; MspAsk(147, r, 28); CHECK(BakEdited("146.2") && !BakEdited("146.1")); }
    { uint8_t d = 1; MspAsk(174, &d, 1); CHECK(PipeRepCode == 200 && strcmp(PipeRepBody, "E80318FCE803") == 0);
      uint8_t w[7] = {1, 0x10, 0x27, 0, 0, 0, 0}; MspAsk(171, w, 7); CHECK(BakGet("174.01", v, sizeof v) == 12 && strcmp(v, "102700000000") == 0 && BakEdited("174.01")); }
    { uint8_t s[17] = {2}; for (int i = 1; i < 17; ++i) s[i] = 0xEE; MspAsk(212, s, 17); char img[400]; BakGet("120", img, sizeof img); CHECK(strncmp(img + 2 + 64, "EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE", 32) == 0 && strncmp(img + 2, "1122", 4) == 0 && BakEdited("120")); }
    MspAsk(250, nullptr, 0); CHECK(PipeRepCode == 200 && !BakDirty && card["/rfbak/Goblin.rfb"].find("edits=92,146.2,174.01,120") != std::string::npos);
    id = MspAsk(999 & 0xFF, nullptr, 0); CHECK(PipeRepCode == 404);
    { uint8_t x[2] = {1, 2}; MspAsk(57, x, 2); CHECK(PipeRepCode == 405); }
    BakForModel(); CHECK(BakEditsWaiting());
    // 3. online: the sweep
    BoundFlag = true; ModelMatched = true; fillFc(); fcPid = 1; fcRate = 0; card.clear(); strcpy(BakModel, ""); BakLoaded = false; Bak[0] = 0;
    CHECK(!BakOffline() && !BakHaveFile());
    fcLog.clear(); BackupNow(); CHECK(CurrentMode == SAVE_RF_SETTINGS && BlockBankChanges);
    runUntilDone();
    CHECK(BakJob == BAK_JOB_NONE && CurrentMode == NORMAL && !BlockBankChanges);
    CHECK(BakFails == 0 && lastBox.find("Backed up: ") == 0);
    CHECK(BakHaveFile() && BakGet("banks", v, sizeof v) == 3 && strcmp(v, "3/3") == 0);
    { char a[200]; int n1 = BakGet("112.2", a, sizeof a), n2 = BakGet("111.1", a, sizeof a), n3 = BakGet("174.03", a, sizeof a), n4 = BakGet("154.01", a, sizeof a), n5 = BakGet("77", a, sizeof a);
      CHECK(n1 == 100 && n2 == 50 && n3 == 12 && n4 == 24 && n5 == 24); }
    { int selects = 0, lastSel = -1; for (auto &r : fcLog) if (r.fn == 210) { ++selects; lastSel = strtol(r.data.c_str(), nullptr, 16); } CHECK(selects == 3 * 4 + 3 + 2); CHECK(lastSel == 0x80 || lastSel == (Bank - 1)); }
    CHECK(fcPid == Bank - 1 && fcRate == DualRateInUse - 1);
    // 4. restore all: the FC has changed; only what differs is written, one servo at a time; the store; no restart
    const std::string saved = card["/rfbak/Goblin.rfb"];
    fc["146.1"][0] = '0'; fc["146.1"][1] = '0';                       // rescue bank 2 off on the FC
    fc["120"].replace(2 + 32, 32, rep("77", 16));                       // servo 2 changed
    fc["172"].replace(14, 14, rep("66", 7));                            // rule 2 changed
    fc["77"].replace(18, 6, "00E803");                                   // failsafe ch4 changed
    fcLog.clear(); RestoreAll(); runUntilDone();
    CHECK(BakJob == BAK_JOB_NONE && BakFails == 0);
    { int w147 = 0, w212 = 0, w173 = 0, w78 = 0, w250 = 0, w68 = 0, w202 = 0; std::string s212;
      for (auto &r : fcLog) { if (r.fn == 147) ++w147; if (r.fn == 212) { ++w212; s212 = r.data; } if (r.fn == 173) ++w173; if (r.fn == 78) ++w78; if (r.fn == 250) ++w250; if (r.fn == 68) ++w68; if (r.fn == 202) ++w202; }
      CHECK(w147 == 1 && w212 == 1 && w173 == 1 && w78 == 1 && w202 == 0); CHECK(s212.substr(0, 2) == "01"); CHECK(w250 == 1 && w68 == 0); }
    CHECK(fc["146.1"] == std::string("0101") + rep("05", 26) && fc["120"].substr(2 + 32, 32) == "1122334455667788990A0B0C0D0E0F10" && fc["77"].substr(18, 6) == "01DC05");
    CHECK(BakWritten == 4 && BakUnchanged > 40 && lastBox.find("4 written") == 0);
    // 5. a changed governor global restarts the FC after the store; motor block likewise
    fc["142"] = rep("5F", 30); fcLog.clear(); RestoreAll(); runUntilDone();
    { int w143 = 0, w250 = 0, w68 = 0; for (auto &r : fcLog) { if (r.fn == 143) ++w143; if (r.fn == 250) ++w250; if (r.fn == 68) ++w68; } CHECK(w143 == 1 && w250 == 1 && w68 == 1); }
    // 6. write edits: offline edits, then connected: only the marked keys, then the marks go
    BoundFlag = false; { uint8_t b[27] = {0}; b[2] = 90; MspAsk(93, b, 27); uint8_t d = 0; MspAsk(210, &d, 1); uint8_t r[28] = {0}; MspAsk(147, r, 28); MspAsk(250, nullptr, 0); }
    CHECK(BakEditsWaiting() && BakEdited("92") && BakEdited("146.0"));
    BoundFlag = true; BakOffered = false; confirmAnswer = false; BakOfferEdits(); CHECK(lastBox.find("The backup holds edits") == 0 && BakJob == BAK_JOB_NONE);
    BakOfferEdits(); CHECK(lastBox.find("The backup holds edits") == 0);   // (asked once per connection: the same box text means no second question ... )
    fcLog.clear(); confirmAnswer = true; BakOffered = false; BakOfferEdits(); CHECK(BakJob == BAK_JOB_EDITS);
    runUntilDone();
    { int w93 = 0, w147 = 0, w202 = 0, w212 = 0; for (auto &r : fcLog) { if (r.fn == 93) ++w93; if (r.fn == 147) ++w147; if (r.fn == 202) ++w202; if (r.fn == 212) ++w212; } CHECK(w93 == 1 && w147 == 1 && w202 == 0 && w212 == 0); }
    CHECK(!BakEditsWaiting() && fc["92"].substr(4, 2) == "5A" && fc["146.0"].substr(0, 2) == "00");
    CHECK(card["/rfbak/Goblin.rfb"].find("edits=\n") != std::string::npos);
    // 7. forget edits
    BoundFlag = false; { uint8_t b[27] = {0}; MspAsk(93, b, 27); MspAsk(250, nullptr, 0); } CHECK(BakEditsWaiting()); confirmAnswer = true; DiscardEdits(); CHECK(!BakEditsWaiting());
    // 8. a FC that refuses an optional read: not a failure; one that fails a required read: counted and named
    BoundFlag = true; fillFc(); fc.erase("123"); fc.erase("154.00"); fc.erase("154.01"); fc.erase("154.02"); fc.erase("77");
    BackupNow(); runUntilDone(); CHECK(BakFails == 1 && lastBox.find("Backed up, but 1 could not be read") == 0 && strstr(BakFailed, "77"));
    // 9. the Version 1 word route offline (B71): the six pages read the file's images as the receiver's items ...
    BoundFlag = false; fillFc(); strcpy(Bak, "rfb=1\nmodel=Goblin\nedits=\n"); for (auto &kv : fc) BakSet(kv.first.c_str(), kv.second.c_str()); BakSet("edits", ""); BakSave();
    { std::string h; for (int i = 0; i < 50; ++i) { char b[4]; snprintf(b, sizeof b, "%02X", i); h += b; } BakSet("112.1", h.c_str()); BakSet("94.1", h.c_str()); BakSet("111.0", h.c_str()); BakSet("148.1", h.substr(0, 34).c_str()); BakSet("142", h.c_str()); }
    Bank = 2; DualRateInUse = 1; CurrentView = PIDVIEW; boxes = 0; rfStarts = 0;
    told = ""; Reading_PIDS_Now = true; CHECK(BakOfflineWords(SEND_PID_VALUES)); CHECK(told == "25:00010203 26:04050607 27:08090A0B 28:0C0D0E0F 29:10111213 30:14151617 32:18191A1B 33:1C1D0000 34:1E1F2021 " && PID_Send_Duration == 0);
    told = ""; CHECK(BakOfflineWords(SEND_RATES_VALUES)); CHECK(told == "25:00010302 26:07090800 27:0D0F0E13 28:15140000 " && RATES_Send_Duration == 0);
    told = ""; CHECK(BakOfflineWords(SEND_RATES_ADVANCED_VALUES)); CHECK(told == "25:040A1016 26:191B1D1F 27:1A1C1E20 28:21222300 " && Rates_Advanced_Send_Duration == 0);
    told = ""; CHECK(BakOfflineWords(SEND_PID_ADVANCED_VALUES)); CHECK(told == "25:06011112 26:13070809 27:24250A0B 28:0C0D0E0F 29:26272814 30:15161718 32:292A0000 " && PID_Advanced_Send_Duration == 0);
    told = ""; CHECK(BakOfflineWords(SEND_GOV_VALUES)); CHECK(told == "25:01000102 26:03040506 27:07080C0D 28:0E090A0B 29:0F100000 " && GOV_Send_Duration == 0);
    // governor global: times in tenths on the FC come as whole seconds (0x0201 = 513 tenths -> 51 s = 0x33; 0x0403 = 1027 -> 103 = 0x67; 0x1B1A = 6938 -> 694 = 0x2B6; 0x0605 = 1541 -> 154 = 0x9A; 0x0807 = 2055 -> 206 = 0xCE; 0x0A09 = 2569 -> 257 = 0x101)
    told = ""; CHECK(BakOfflineWords(SEND_GOV_CONFIG_VALUES)); CHECK(told == "25:00133300 26:6700B602 27:9A00CE00 28:01010D0E 29:15141917 30:161C1F20 " && GOV_Config_Send_Duration == 0);
    CHECK(boxes == 0 && rfStarts == 0);
    // ... a bank the file has not: told, and back to the menu
    Bank = 6; told = ""; Reading_PIDS_Now = true; BlockBankChanges = true; CHECK(BakOfflineWords(SEND_PID_VALUES)); CHECK(told == "" && boxes == 1 && rfStarts == 1 && lastBox.find("The PIDs for bank 6 are not in") == 0 && !Reading_PIDS_Now && !BlockBankChanges);
    Bank = 2;
    // ... and their saves patch the images as the receiver patches the flight controller's, mark the key, write the file
    words[GET_FIRST_6_PID_VALUES] = {100, 101, 102, 103, 104, 105}; words[GET_SECOND_11_PID_VALUES] = {106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116};
    CHECK(BakOfflineWords(GET_FIRST_6_PID_VALUES) && BakOfflineWords(GET_SECOND_11_PID_VALUES));
    { char a[200]; CHECK(BakGet("112.1", a, sizeof a) == 100 && strncmp(a, "6400650066006700680069006A006B006C006D006E006F0070007100720073007400", 68) == 0 && strncmp(a + 68, "22232425", 8) == 0); }
    CHECK(BakEdited("112.1") && !BakEdited("112.0") && !BakDirty && card["/rfbak/Goblin.rfb"].find("edits=112.1") != std::string::npos);
    words[GET_FIRST_7_RATES_VALUES] = {4, 10, 11, 12, 20, 21, 22}; words[GET_SECOND_6_RATES_VALUES] = {30, 31, 32, 40, 41, 42, 0};
    CHECK(BakOfflineWords(GET_FIRST_7_RATES_VALUES) && BakOfflineWords(GET_SECOND_6_RATES_VALUES));
    { char a[200]; BakGet("111.0", a, sizeof a); CHECK(strncmp(a, "040A0C0B" "040506" "141615" "0A0B0C" "1E201F" "101112" "282A29", 44) == 0 && strncmp(a + 44, "16", 2) == 0); CHECK(BakEdited("111.0")); }
    words[GET_RATES_ADVANCED_VALUES_FIRST_7] = {50, 51, 52, 53, 60, 61, 62}; words[GET_RATES_ADVANCED_VALUES_SECOND_8] = {63, 70, 71, 72, 73, 80, 81, 82};
    CHECK(BakOfflineWords(GET_RATES_ADVANCED_VALUES_FIRST_7) && BakOfflineWords(GET_RATES_ADVANCED_VALUES_SECOND_8));
    { char a[200]; BakGet("111.0", a, sizeof a); CHECK(strncmp(a + 8, "32", 2) == 0 && strncmp(a + 20, "33", 2) == 0 && strncmp(a + 32, "34", 2) == 0 && strncmp(a + 44, "35", 2) == 0 && strncmp(a + 50, "3C463D473E483F49505152", 22) == 0 && strncmp(a, "040A0C0B", 8) == 0); }
    words[GET_FIRST_9_ADVANCED_PID_VALUES] = {200, 201, 202, 203, 204, 205, 206, 207, 208}; words[GET_SECOND_9_ADVANCED_PID_VALUES] = {209, 210, 211, 212, 213, 214, 215, 216, 217}; words[GET_THIRD_8_ADVANCED_PID_VALUES] = {218, 219, 220, 221, 222, 223, 224, 225};
    CHECK(BakOfflineWords(GET_FIRST_9_ADVANCED_PID_VALUES) && BakOfflineWords(GET_SECOND_9_ADVANCED_PID_VALUES) && BakOfflineWords(GET_THIRD_8_ADVANCED_PID_VALUES));
    { uint8_t p[64]; int n; CHECK(BakBlock(94, 1, p, sizeof p, n) && n == 50 && p[6] == 200 && p[1] == 201 && p[17] == 202 && p[19] == 204 && p[7] == 205 && p[36] == 208 && p[37] == 209 && p[10] == 210 && p[15] == 215 && p[38] == 216 && p[40] == 218 && p[20] == 219 && p[22] == 221 && p[24] == 223 && p[41] == 224 && p[42] == 225 && p[0] == 0 && p[2] == 2 && p[16] == 16); CHECK(BakEdited("94.1")); }
    words[SEND_GOV_WRITE_PROFILE1] = {0x34, 0x12, 3, 4, 5, 6, 7, 8, 9, 10, 11}; words[SEND_GOV_WRITE_PROFILE2] = {12, 13, 14, 15, 16, 17};
    CHECK(BakOfflineWords(SEND_GOV_WRITE_PROFILE1) && BakOfflineWords(SEND_GOV_WRITE_PROFILE2));
    { char a[200]; BakGet("148.1", a, sizeof a); CHECK(strcmp(a, "3412" "0304050607" "0809" "0D0E0F" "0A0B" "0C" "1011") == 0 && BakEdited("148.1")); }
    words[SEND_GOV_WRITE_CONFIG1] = {1, 2, 3, 0, 4, 0, 5, 0, 6, 0, 7}; words[SEND_GOV_WRITE_CONFIG2] = {0, 8, 0, 9, 0, 10, 11, 12, 13, 14, 15}; words[SEND_GOV_WRITE_CONFIG3] = {16, 17, 0, 0, 0, 0};
    CHECK(BakOfflineWords(SEND_GOV_WRITE_CONFIG1) && BakOfflineWords(SEND_GOV_WRITE_CONFIG2) && BakOfflineWords(SEND_GOV_WRITE_CONFIG3));
    { uint8_t p[64]; int n; CHECK(BakBlock(142, -1, p, sizeof p, n) && n == 50);
      CHECK(p[0] == 1 && p[1] == 30 && p[2] == 0 && p[3] == 40 && p[5] == 60 && p[7] == 70 && p[9] == 80 && p[13] == 9 && p[14] == 0 && p[19] == 2 && p[20] == 11 && p[21] == 10 && p[22] == 14 && p[23] == 13 && p[25] == 12 && p[26] == 50 && p[28] == 15 && p[31] == 16 && p[32] == 17);
      CHECK(p[11] == 11 && p[12] == 12 && p[15] == 15 && p[24] == 24 && p[29] == 29 && p[33] == 33);   // the bytes no page edits keep the file's
      CHECK(BakEdited("142")); }
    { char e[200]; BakEditsText(e, sizeof e); CHECK(strcmp(e, "PIDs bank 2, rates bank 1, adv. PIDs bank 2, governor bank 2, governor global") == 0); }
    CHECK(!BakOfflineWords(1) && !BakOfflineWords(36));
    // 10. the offer comes from the tick once the pipe is ready, and is forgotten when the model goes
    BoundFlag = true; CurrentView = ROTORFLIGHTVIEW; BakOffered = false; confirmAnswer = false; lastBox = ""; PipeState = 1; BakOfferTick(); CHECK(lastBox == "" && !BakOffered);
    PipeState = 2; BakOfferTick(); CHECK(lastBox.find("The backup holds edits") == 0 && BakOffered);
    lastBox = ""; BakOfferTick(); CHECK(lastBox == "");                                   // (once per connection)
    BoundFlag = false; BakOfferTick(); CHECK(!BakOffered); BoundFlag = true; CurrentView = PIDVIEW; BakOfferTick(); CHECK(lastBox == "" && !BakOffered);   // (not from another page)
    printf("test_backup: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:4000]); sys.exit(1)
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
