#!/usr/bin/env python3
"""Host test of Guide & checks (B196, 16 MB screens): include/RF_Undo.h, RF_Check.h, RF_Direction.h, RF_Changes.h, RF_Guide.h,
RF_Tools.h - compiled on the Mac with the REAL backup engine (RF_Backup.h), the REAL pipe bookkeeping and bank check of
PipeHttp.h (its MspAsk and PipeReplyFromScreen carry Undo's hooks), and the shared helpers lifted from the pages that own them,
over a fake screen whose pipe answers a pass later (as Bluetooth does), a fake flight controller that keeps Rotorflight 4.6's
settings by the backup's keys, and a fake card holding Malcolm's real backup of Black Thunder 2 (when the SSD is there).
Then the wiring, by text: RotorFlightStart's first look, the function table's numbers, the pages' codes, the help files.
   python3 dev/test_tools/test_tools.py"""
import os, re, subprocess, sys, tempfile, json
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INC = os.path.join(ROOT, 'TransmitterCode', 'include')
SCREEN = os.path.join(os.path.dirname(ROOT), 'ESP32-board2', 'board4', 'nextion-emulator')
def src(name): return open(os.path.join(INC, name), encoding='utf-8', errors='replace').read()
def strip(t): return t.replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '')
RFMAP = (lambda d: d[d.index('// RFMAP-BEGIN'):d.index('// RFMAP-END')])(open(os.path.join(INC, '1Definitions.h'), encoding='utf-8', errors='replace').read())   # (B210: the channel map's block, the real one)
def line(text, start):
    for l in text.split('\n'):
        if l.startswith(start): return l + '\n'
    sys.exit('not found: ' + start)
def func(text, head):
    i = text.index(head); j = text.index('\n}\n', i); return text[i:j + 3]
FC, SW, RES, SRV, PIPE, BAK = src('RF_FcSetup.h'), src('RF_Switches.h'), src('RF_Rescue.h'), src('RF_Servos.h'), src('PipeHttp.h'), src('RF_Backup.h')
lifted = (func(FC, 'FLASHMEM static void FsBusy(') + line(FC, 'FLASHMEM static uint32_t RdU32(') + func(FC, 'FLASHMEM static void FsFail(')
          + func(FC, 'FLASHMEM static bool FsRefused(') + FC[FC.index('static const char *const ArmWhy[27] PROGMEM'):FC.index('};', FC.index('static const char *const ArmWhy[27] PROGMEM')) + 3]
          + line(SW, 'static const int SW_SLOTS') + line(SW, 'struct SwSlot') + line(SW, 'static inline int SwUs(') + line(SW, 'static inline bool SwUsed(')
          + line(SW, 'FLASHMEM static int SwArmChannel(') + line(RES, 'FLASHMEM static uint16_t RdU16(') + line(SRV, 'FLASHMEM static int RdS16('))
m1 = re.search(r'static int PipeReqId = 0;.*?\nint PipeReplyBytes\(uint8_t \*out, int max\)\n\{.*?\n\}\n', PIPE, re.S)
m2 = re.search(r'static void \(\*BcThen\)\(\) = nullptr;.*?\nFLASHMEM static void BankCheckTick\(\)\n\{.*?\n\}\n', PIPE, re.S)
assert m1 and m2, 'PipeHttp.h: the pipe bookkeeping or the bank check not found'
SILENCE = 'static void SilenceTick() { uint32_t now = millis(); ' + line(src('transceiver.h'), '    if (SilenceMsgUntil && ').strip() + ' }\n'   # (Hide_msg_if_needed's first look)
SSD_BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Black_Thunder_2.rfb')   # (Malcolm's real backup of Black Thunder 2, 3 Nov 2026: tuning only - no names of networks, no passwords)
bt2 = open(SSD_BACKUP).read() if os.path.exists(SSD_BACKUP) and not os.environ.get('NO_SSD') else None
if bt2 is None:   # (the SSD not there: a backup made as the real one is, from its first lines)
    bt2 = ('rfb=1\nmodel=Black Thunder 2\ndate=2026-11-03 15:34\nbanks=6/6\nedits=\n'
           + ''.join('112.%d=37005F001900820078006E00410082008200BE001E00080000001900080037003C00\n148.%d=1405282832001E00140A0A32640A0A1000\n146.%d=0001C864030A14058A02C2015E01F401140014000A00F4012C01B80B\n94.%d=031900000000012D2D3C4141C8191923000F0C0F7850050A3C0000000037004B1400001964641919230019\n111.%d=040F28190000000F2814000000191424000000280030000000000F000F005A000F000A3C9600\n' % (b, b, b, b, b) for b in range(6))
           + '142=032C01FA00C8001E00320000000F00000000000A050A000500321E000000000000000000000000000000\n42=000000320002640000D606000000000000007D000A\n'
           + '131=2E04D007E803010A0000FA00010A080808646464640A00670001000200\n10=425448554E44455232\n36=0804007C\n38=000000000000\n240=00000000\n'
           + '32=88130C02024A01A401A4015E016423881300000000000000000000\n34=000000780000888800008888' + '0000888800008888' * 8 + '\n')
bt2_c = bt2.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cctype>
#include <cmath>
#include <string>
#include <map>
#include <vector>
#define FLASHMEM
#define PROGMEM
#define DMAMEM
#define NORMAL 0
#define SAVE_RF_SETTINGS 7
#define RESTORE_RF_SETTINGS 8
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define FILE_READ 0
#define FILE_WRITE 1
#define FRONTVIEW 0
#define RXSETUPVIEW 31
#define BLANKVIEW 39
#define PIDVIEW 45
#define RATESVIEW_RF 46
#define ROTORFLIGHTVIEW 47
#define RATESADVANCEDVIEW 48
#define PIDADVANCEDVIEW 49
#define RFBACKUP_RESTOREVIEW 53
#define RFGOVERNORVIEW_PROFILE 54
#define RFGOVERNORVIEW_GLOBAL 55
#define RESCUEVIEW 58
#define RESCUE2VIEW 59
#define SERVOVIEW 60
#define RFSETUPVIEW 61
#define TRAVELVIEW 62
#define TRAVEL2VIEW 63
#define FILTERVIEW 64
#define FILTER2VIEW 65
#define TRAVEL3VIEW 66
#define ADJUSTVIEW 67
#define ADJPICKVIEW 68
#define COPYBANKVIEW 71
#define BATTERYVIEW 72
#define BLACKBOXVIEW 73
#define LEVELVIEW 74
#define BATSENSORSVIEW 75
#define TRAVEL4VIEW 76
#define BASICSVIEW 77
#define BASICS2VIEW 78
#define PORTSVIEW 79
#define ESCCALVIEW 80
#define EASYVIEW 81
#define RATESTYPEVIEW 82
#define RATESCURVEVIEW 83
#define BEEPERVIEW 84
#define TOOLSVIEW 85
#define CHECKVIEW 86
#define DIRVIEW 87
#define CHANGESVIEW 88
#define GUIDEVIEW 89
#define CHANNELSUSED 16
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
static int CurrentView = 0, CurrentMode = NORMAL, PipeState = 2;
static bool BoundFlag = true, ModelMatched = true, BlockBankChanges = false, bigScreen = true, armedFake = false, refuseOpen = false;
static char ModelName[32] = "Black Thunder 2";
static uint8_t Bank = 1, DualRateInUse = 1, RotorFlight_V = 2, ArmingChannel = 6, ScreenEventArg = 0;
static bool ArmingManaged() { return RotorFlight_V && ArmingChannel >= 1 && ArmingChannel <= 16; }   // (B209: as 1Definitions.h's ARMRULE)
''' + RFMAP + r'''
static uint8_t ModalWaits = 0;
static uint32_t now = 1000;
static uint32_t millis() { return now; }
static bool ScreenIsBig() { return bigScreen; }
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
struct { int Second, Minute, Hour, Wday, Day, Month, Year; } tm;
struct { bool read(decltype(tm) &t) { t.Year = 56; t.Month = 11; t.Day = 8; t.Hour = 14; t.Minute = 2; return true; } } RTC;
static int Gyear = 26, Gmonth = 11, GmonthDay = 8, Ghour = 14, Gminute = 2;
static void ReadTheRTC() {}
// ---- the fake screen (a pipe request answered a pass later, as Bluetooth does)
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0, asked = 0, sounds = 0, rfStarts = 0;
static std::string lastBox, lastBoxPage; static bool confirmAnswer = true;
void PipeReplyFromScreen(const char *text);
static void fakeFc(int id, const char *path);
static void SendCommand(char *c) { cmds.push_back(c); if (strncmp(c, "ldrcreq ", 8) == 0) { const int id = atoi(c + 8); const char *p = strchr(c + 8, ' '); fakeFc(id, p ? p + 1 : ""); } }
static void SendText(char *n, char *t) { fields[n] = t; }
static void SendValue(char *n, int v) { char b[16]; snprintf(b, sizeof b, "%d", v); fields[n] = b; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; lastBoxPage = page; cmds.push_back(page); }
static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; cmds.push_back(page); return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static bool ModelSeemsArmed(char *why, size_t n) { if (armedFake) snprintf(why, n, "armed"); return armedFake; }
static bool safetyOff = false; static bool RadiosMustBeOff() { return safetyOff; }
static std::string lastLog; static int logs = 0; static void LogText(char *t, uint16_t, bool) { lastLog = t; ++logs; }
static bool RfLeaveAfterSave = false; static uint32_t SilenceMsgUntil = 0; static int SilenceMsgView = -1, pageHides = 0;
void HidePIDMsg() { ++pageHides; } void HideRATESMsg() { ++pageHides; } void Hide_Advanced_Rates_Msg() { ++pageHides; } void HidePID_Advanced_Msg() { ++pageHides; } void HideGOVMsg() { ++pageHides; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
// ---- the Version 1 word route (RF_Backup.h's stand-in needs its names; nothing here uses it)
static struct { uint8_t ID; uint16_t word[12]; } Parameters;
static void LoadOneParameter() {}
static void TelemetryFromPipe(const char *) {}
static bool Reading_PIDS_Now = false, Reading_PIDS_Advanced_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static uint16_t PID_Send_Duration = 0, PID_Advanced_Send_Duration = 0, RATES_Send_Duration = 0, Rates_Advanced_Send_Duration = 0;
static uint32_t GOV_Send_Duration = 0, GOV_Config_Send_Duration = 0;
// ---- the pages the tools open (each its view, or a refusal that leaves the view as it was)
static std::string opened;
static void opens(const char *what, int view) { opened = what; if (refuseOpen) { MsgBox((char *)"page RFView", "refused"); return; } CurrentView = view; }
void StartCalibrateView() { opens("calibrate", LEVELVIEW); }  void StartBasicsView() { opens("basics", BASICSVIEW); }
void StartBatteryView() { opens("battery", BATTERYVIEW); }    void StartBlackboxView() { opens("blackbox", BLACKBOXVIEW); }
void StartJobsView() { opens("switches", ADJUSTVIEW); }       void StartFilterView() { opens("filters", FILTERVIEW); }
void StartRFSettingsView() { opens("settings", RFSETUPVIEW); } void StartRescueView() { opens("rescue", RESCUEVIEW); }
void StartServoView() { opens("servos", SERVOVIEW); }         void StartTravelView() { opens("travel", TRAVELVIEW); }
void Start_RF_Governor() { opens("governor", RFGOVERNORVIEW_PROFILE); } void Start_Gov_Global() { opens("govglobal", RFGOVERNORVIEW_GLOBAL); }
void StartRFRatesView() { opens("rates", RATESVIEW_RF); }     void StartBeeperView() { opens("beeper", BEEPERVIEW); }
void RfToolsRedraw(); void RfBackHome(); void RfOpenFrom(uint8_t from, uint8_t id); void CheckShowAgain(bool again); void GuideShowAgain(bool tick); void GuideStart(); void CheckStart(); void DirStart();   // (1Definitions.h)
// RotorFlightStart, as RF_RotorFlight.h has it from its gate on (its first look is checked by text below)
void UndoNewVisit(); bool RfHomeBack();
static void RotorFlightStart() { UndoNewVisit(); if (RfHomeBack()) return; CurrentView = ROTORFLIGHTVIEW; ++rfStarts; }
#define BAK_OTHER_FILE_FAKE
static bool BakOtherFile(int, char *, size_t, char *, size_t) { return false; }
// ---- the bank check's neighbours (PipeHttp.h)
static bool FcBankPending = false; static int FcPidBank = 0, FcRateBank = 0; static void FcBankShow() {}
// ---- PipeHttp.h: the Undo hooks' prototypes, the requests and replies, the bank check (B102, B196)
void UndoSeeAsk(uint8_t fn, const uint8_t *data, int len, int id); void UndoSeeReply(int id, int code, const char *body);
uint8_t UndoFnOfView(int view); void UndoPreGo(uint8_t fn, int bank, void (*then)(), const char *page, int view); bool UndoPreBusy();
''' + m1.group(0) + m2.group(0) + r'''
// ---- the helpers, lifted from the pages that own them
''' + lifted + strip(BAK) + strip(src('RF_Undo.h')) + strip(src('RF_Check.h')) + strip(src('RF_Direction.h')) + strip(src('RF_Changes.h')) + strip(src('RF_Guide.h')) + strip(src('RF_Tools.h')) + SILENCE + r'''
// ---- the fake flight controller: Rotorflight 4.6's settings by the backup's keys
static std::map<std::string, std::string> fc;
static int fcPid = 0, fcRate = 0, fcStores = 0, fcRestarts = 0, fail210 = 0, busyFn = 0, busyLeft = 0; static bool fcArmed = false, holdFc = false, armed409 = false;
static uint32_t fcFlags = 0; static int fcFlagCount = 27, fcRoll = 0, fcPitch = 0, fcHead = 180;
static uint8_t fcMem[13];
struct FcReq { int fn; std::string data; }; static std::vector<FcReq> fcLog;
struct Pend { int id, code; std::string body; }; static std::vector<Pend> pend;
static std::string hexOf(const uint8_t *d, int n) { char b[4]; std::string s; for (int i = 0; i < n; ++i) { snprintf(b, sizeof b, "%02X", d[i]); s += b; } return s; }
static std::string keyOf(int fn, int idx) { char k[16]; if (fn == 112 || fn == 94 || fn == 148 || fn == 146) snprintf(k, sizeof k, "%d.%d", fn, fcPid); else if (fn == 111) snprintf(k, sizeof k, "111.%d", fcRate); else if (idx >= 0) snprintf(k, sizeof k, "%d.%02X", fn, idx); else snprintf(k, sizeof k, "%d", fn); return k; }
static int readOfW(int w) { static const int p[][2] = {{93,92},{37,36},{147,146},{149,148},{202,112},{95,94},{204,111},{143,142},{43,42},{11,10},{39,38},{62,61},{239,240},{97,96},{220,126},{65,64},{45,44},{67,66},{76,75},{51,50},{74,73},{33,32},{216,123},{185,184}}; for (auto &q : p) if (q[0] == w) return q[1]; return 0; }
static void put32(uint8_t *b, int o, uint32_t v) { b[o] = v; b[o + 1] = v >> 8; b[o + 2] = v >> 16; b[o + 3] = v >> 24; }
static void fakeFc(int id, const char *path) {
    int fn = 0; uint8_t d[400]; int len = 0;
    const char *f = strstr(path, "fn="); if (f) fn = atoi(f + 3);
    const char *h = strstr(path, "data="); if (h) { h += 5; while (h[0] && h[1] && len < 400) { char t[3] = {h[0], h[1], 0}; d[len++] = (uint8_t) strtol(t, nullptr, 16); h += 2; } }
    fcLog.push_back({fn, hexOf(d, len)});
    auto reply = [&](int code, const std::string &body) { if (!holdFc) pend.push_back({id, code, body}); };
    if (fn == 101) { uint8_t b[30] = {0}; b[6] = fcArmed ? 1 : 0; b[16] = (uint8_t) fcFlagCount; put32(b, 17, fcFlags); b[23] = fcPid; b[24] = 6; b[25] = fcRate; b[26] = 6; reply(200, hexOf(b, 30)); return; }
    if (busyLeft > 0 && fn == busyFn) { --busyLeft; reply(503, "receiver busy with a transmitter edit - try again"); return; }
    if (armed409 && fn != 101) { reply(409, "ARMED - the flight controller says it is armed. Disarm first."); return; }
    if (fn == 210) { if (fail210 > 0) { --fail210; reply(503, "busy"); return; } if (d[0] & 0x80) fcRate = d[0] & 0x7F; else fcPid = d[0]; reply(200, ""); return; }
    if (fn == 250) { ++fcStores; reply(200, ""); return; }
    if (fn == 68) { ++fcRestarts; reply(200, ""); return; }
    if (fn == 108) { uint8_t b[6]; b[0] = fcRoll & 255; b[1] = (fcRoll >> 8) & 255; b[2] = fcPitch & 255; b[3] = (fcPitch >> 8) & 255; b[4] = fcHead & 255; b[5] = fcHead >> 8; reply(200, hexOf(b, 6)); return; }
    if (fn == 70) { reply(200, hexOf(fcMem, 13)); return; }
    if (len == 0 || ((fn == 174 || fn == 154) && len == 1)) { const std::string k = keyOf(fn, len == 1 ? d[0] : -1); if (fc.count(k)) reply(200, fc[k]); else reply(404, "unknown"); return; }
    if (fn == 11) { std::string n = hexOf(d, len); while (n.size() >= 2 && n.substr(n.size() - 2) == "00") n.resize(n.size() - 2); fc["10"] = n; reply(200, ""); return; }
    if (fn == 171 && len == 7) { fc[keyOf(174, d[0])] = hexOf(d + 1, 6); reply(200, ""); return; }
    if (fn == 212 && len == 17) { std::string &img = fc["120"]; const int i = d[0]; if ((int) img.size() >= 2 + (i + 1) * 32) img.replace(2 + i * 32, 32, hexOf(d + 1, 16)); reply(200, ""); return; }
    if (fn == 35 && len >= 5) { std::string &img = fc["34"]; const int i = d[0]; if ((int) img.size() >= (i + 1) * 8) img.replace(i * 8, 8, hexOf(d + 1, 4)); reply(200, ""); return; }
    if (fn == 222 && len >= 28) { std::string hh = hexOf(d, len); fc["131"] = hh.substr(0, 12) + fc["131"].substr(12, 2) + hh.substr(12); reply(200, ""); return; }
    if (fn == 183 || fn == 205 || fn == 55) { reply(200, ""); return; }
    const int r = readOfW(fn);
    if (r && len > 0) { fc[keyOf(r, -1)] = hexOf(d, len); reply(200, ""); return; }
    reply(404, "unknown");
}
static void deliver() { if (pend.empty()) return; Pend q = pend.front(); pend.erase(pend.begin()); static char l[1800]; snprintf(l, sizeof l, "%d %d %s", q.id, q.code, q.body.c_str()); PipeReplyFromScreen(l); }
static void tick(int n = 1) { for (int i = 0; i < n; ++i) { deliver(); BankCheckTick(); ToolsPoll(); if (BakJob != BAK_JOB_NONE) BackupRun(); now += 50; } }
static int runJob(int limit = 6000) { int n = 0; while ((BakJob != BAK_JOB_NONE || !pend.empty()) && n < limit) { tick(); ++n; } tick(3); return n; }
static int count(int fn) { int k = 0; for (auto &q : fcLog) if (q.fn == fn) ++k; return k; }
static bool sent(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
static std::string lastDataOf(int fn) { for (int i = (int) fcLog.size() - 1; i >= 0; --i) if (fcLog[i].fn == fn) return fcLog[i].data; return "?"; }
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void fcFromBackup() { fc.clear(); const char *p = BT2; std::string s = p; size_t a = 0; while (a < s.size()) { size_t e = s.find('\n', a); if (e == std::string::npos) e = s.size(); std::string l = s.substr(a, e - a); size_t q = l.find('='); if (q != std::string::npos) { std::string k = l.substr(0, q); if (isdigit((unsigned char) k[0])) fc[k] = l.substr(q + 1); } a = e + 1; } fc["184"] = "000000000105000000"; }
static void setByte(const char *key, int off, uint8_t v) { std::string &img = fc[key]; if ((int) img.size() < (off + 1) * 2) img.resize((off + 1) * 2, '0'); char h[3]; snprintf(h, sizeof h, "%02X", v); img[off * 2] = h[0]; img[off * 2 + 1] = h[1]; }
static int byteOf(const std::string &hex, int off) { return (int) strtol(hex.substr(off * 2, 2).c_str(), nullptr, 16); }
static bool rowHas(const char *t) { for (int i = 0; i < CkN; ++i) if (strstr(CkRows[i].text, t)) return true; return false; }
static int rowOf(const char *t) { for (int i = 0; i < CkN; ++i) if (strstr(CkRows[i].text, t)) return i; return -1; }
static int chgRowOf(const char *t) { for (int i = 0; i < ChgN; ++i) if (strstr(ChgRows[i].text, t)) return i; return -1; }
int main() {
    const std::string bakPath = "/rfbak/Black_Thunder_2.rfb";
    card[bakPath] = BT2; dirs["/rfbak"] = true;
    fcFromBackup();
    memset(fcMem, 0, sizeof fcMem); fcMem[0] = 3; put32(fcMem, 5, 16777216); put32(fcMem, 9, 1000000);

    // ==== 1. Guide & checks opens on a 16 MB screen only; Undo says there is nothing yet
    CurrentView = ROTORFLIGHTVIEW; bigScreen = false; StartToolsView();
    CHECK(CurrentView == ROTORFLIGHTVIEW && boxes == 1 && lastBox.find("16 MB") != std::string::npos);
    bigScreen = true; StartToolsView();
    CHECK(CurrentView == TOOLSVIEW && sent("page RFToolsView") && fields["tU"] == "Nothing to undo yet" && fields["t11"] == "Black Thunder 2");
    boxes = 0; ToolsUndo(); CHECK(boxes == 1 && lastBox.find("Nothing to undo yet") != std::string::npos && BakJob == BAK_JOB_NONE);

    // ==== 2. CHECK MY SETUP on Malcolm's Black Thunder 2 as backed up: nothing found (a green row offering the direction check)
    cmds.clear(); fcLog.clear(); ToolsCheck(); CHECK(CurrentView == CHECKVIEW && sent("page RFCheckView") && fields["hd"] == "Reading the flight controller ...");
    tick(80);
    CHECK(CkDone && count(101) == 1 && count(34) == 1 && count(146) == 1 && count(32) == 1 && count(70) == 1 && count(131) == 1 && count(142) == 1 && count(108) == 1);
    CHECK(CkN == 1 && CkRows[0].sev == 2 && rowHas("Nothing found") && CkRows[0].fix == RFO_DIRECTION && fields["hd"] == "All well, as far as this can tell");
    CHECK(fields["r0"] == "Nothing found. A new model: Direction check" && fields["f0"] == "Direction ..." && sent("mk0.bco=2016") && sent("vis f0,1") && sent("vis mk1,0"));
    // the flight controller's own reasons, the switches, the battery, the memory, the gears, rescue, the level
    fcFlags = (1u << 23) | (1u << 21) | (1u << 26); fcFlagCount = 27;
    setByte("34", 1, 1);                       // the arm switch on AUX 2 = channel 7, this model's arming channel 6
    setByte("32", 0, 0); setByte("32", 1, 0);   // no capacity
    put32(fcMem, 9, 14000000);                  // 83 % of the memory used
    setByte("131", 21, 103); setByte("131", 23, 10);   // the main gear backwards (103 : 10), the governor ELECTRIC
    setByte("146.0", 0, 1);                     // rescue on in bank 1, no rescue switch
    fcRoll = 880;                               // 88 degrees
    CheckAgain(); tick(80);
    CHECK(rowHas("Calibrate level first") && CkRows[rowOf("Calibrate level first")].fix == RFO_CALIBRATE && CkRows[rowOf("Calibrate level first")].sev == 0);
    CHECK(rowHas("Restart the flight controller") && CkRows[rowOf("Restart the flight controller")].fix == RFO_RESTART);
    CHECK(rowHas("Arm switch on too soon"));   // (the arm switch flag, always Rotorflight's last)
    CHECK(rowHas("Arm switch on channel 7: the safety drives 6") && CkRows[rowOf("Arm switch on channel 7")].fix == RFO_SWITCHES);
    CHECK(rowHas("Battery capacity not set") && CkRows[rowOf("Battery capacity")].sev == 1);
    CHECK(rowHas("Black box 83% full") && rowHas("Main gear ratio backwards (103 : 10)") && CkRows[rowOf("Main gear")].sev == 0);
    CHECK(rowHas("Rescue is on, but no switch starts it") && rowHas("Tilted 88\xB0: if it stands level, check it"));
    CHECK(CkN == 9 && fields["hd"] == "5 stop it arming, 4 worth a look" && sent("vis bN,1"));
    CheckNext(); CHECK(CkFirst == 6 && sent("vis bP,1")); CheckPrev(); CHECK(CkFirst == 0);
    // a row's button: the page opens; its OK comes back here and the check runs again
    { const int r = rowOf("Calibrate level first"); ScreenEventArg = (uint8_t)(r + 1); CheckFixTapped();
      CHECK(opened == "calibrate" && CurrentView == LEVELVIEW && RfHomeN == 1);
      fcFlags = 0; RotorFlightStart(); CHECK(CurrentView == CHECKVIEW && RfHomeN == 0 && CkStep == CK_STATUS && rfStarts == 0); tick(80); CHECK(!rowHas("Calibrate level first")); }
    // a page that will not open: the check is shown again at once
    refuseOpen = true; ScreenEventArg = (uint8_t)(rowOf("Arm switch on channel 7") + 1); cmds.clear(); CheckFixTapped(); refuseOpen = false;
    CHECK(CurrentView == CHECKVIEW && RfHomeN == 0 && sent("page RFCheckView"));
    // Restart, when the flight controller says one is owed: one question, a 68, a breath, then checked again
    fcFlags = 1u << 21; CheckAgain(); tick(80);
    { const int r = rowOf("Restart the flight controller"); ScreenEventArg = (uint8_t)(r + 1); asked = 0; fcLog.clear(); fcFlags = 0; CheckFixTapped();
      tick(3); CHECK(asked == 1 && count(68) == 1 && CkStep == CK_RESTARTING); tick(150); CHECK(CkDone && !rowHas("Restart the flight controller")); }
    // the receiver busy once ("try again"): asked again a moment later, and the battery still checked
    fcFromBackup(); setByte("32", 0, 0); setByte("32", 1, 0); busyFn = 32; busyLeft = 1; fcLog.clear(); CheckAgain(); tick(90);
    CHECK(CkDone && count(32) == 2 && rowHas("Battery capacity not set")); fcFromBackup();
    // the screen goes dark in the middle of a check: it carries on when the page is back
    CheckAgain(); tick(2); CurrentView = BLANKVIEW; tick(20); CurrentView = CHECKVIEW; tick(80); CHECK(CkDone && CkStep == CK_IDLE);
    EndCheckView(); CHECK(CurrentView == TOOLSVIEW);
    fcFromBackup(); fcRoll = 0;

    // ==== 3. THE DIRECTION CHECK: every move right; then a board turned round, and the fix
    DirStart(); CHECK(CurrentView == DIRVIEW && DrState == DR_IDLE); tick(10);
    CHECK(DrSeen && fields["lv"] == "Nose 0\xB0 down   Right side 0\xB0 down   Heading 180\xB0");
    DirStartTapped(); CHECK(DrState == DR_STEP && DrStep == 1 && fields["do"] == "1 of 3: Tilt the nose DOWN about 30\xB0");
    fcPitch = 250; tick(10); CHECK(DrResult[1] == 1 && DrState == DR_BACK);
    fcPitch = 30; tick(10); CHECK(DrState == DR_STEP && DrStep == 2);
    fcRoll = 260; tick(10); CHECK(DrResult[2] == 1); fcRoll = 0; tick(10); CHECK(DrStep == 3);
    fcHead = 225; tick(10); CHECK(DrResult[3] == 1 && DrState == DR_DONE && fields["rs"] == "The flight controller knows which way round it is." && sent("vis bT,0"));
    // turned round: the nose and the side backwards, the turn right
    fcHead = 180; DirStartTapped(); fcPitch = -250; tick(10); fcPitch = 0; tick(10); fcRoll = -250; tick(10); fcRoll = 0; tick(10); fcHead = 230; tick(10);
    CHECK(DrResult[1] == -1 && DrResult[2] == -1 && DrResult[3] == 1 && DrState == DR_DONE && sent("vis bT,1") && fields["rs"].find("connections face the back") != std::string::npos);
    CHECK(fields["s1"] == "1. Tilt the nose DOWN: it saw the nose go UP" && fields["s2"] == "2. Tilt the RIGHT side down: it saw the LEFT side go down");
    asked = 0; fcLog.clear(); fcStores = fcRestarts = 0; DirTurnTapped(); CHECK(asked == 1 && DrState == DR_FIX_READ);
    tick(20);
    CHECK(count(38) == 2 && count(39) == 1 && fcLog[1].fn == 39 && fcLog[1].data == "00000000B400" && fcStores == 1 && fcRestarts == 1 && fc["38"] == "00000000B400");
    tick(110); CHECK(DrState == DR_IDLE && lastBox.find("Turned round") != std::string::npos);
    CHECK(UndoOffered() && strcmp(UndoWhat, "Mounting direction") == 0 && UndoKeepN == 1 && strcmp(UndoKeep[0].key, "38") == 0);   // (the fix is a save: Undo can put it back)
    // the board at yaw 180 (the phone's "connections to the back"), turned round: the question says FRONT, yaw 0 is written
    EndDirView(); fc["38"] = "00000000B400"; DirStart(); tick(12); CHECK(DrMountKnown && DrMountOk && DrMount[2] == 180);
    DirStartTapped(); fcPitch = -250; tick(10); fcPitch = 0; tick(10); fcRoll = -250; tick(10); fcRoll = 0; tick(10); fcHead = 300; tick(10);
    CHECK(DrState == DR_DONE && sent("vis bT,1") && fields["rs"].find("connections face the front") != std::string::npos);
    asked = 0; fcLog.clear(); DirTurnTapped(); CHECK(asked == 1 && lastBox.find("FRONT (yaw 0)") != std::string::npos); tick(20);
    CHECK(fc["38"] == "000000000000" && count(39) == 1 && fcLog[1].data == "000000000000"); tick(110); fcHead = 180;
    // a custom mounting (roll 90): turned round is said, but nothing is offered to write
    EndDirView(); fc["38"] = "5A0000000000"; DirStart(); tick(12); CHECK(DrMountOk && DrMount[0] == 90);
    DirStartTapped(); fcPitch = -250; tick(10); fcPitch = 0; tick(10); fcRoll = -250; tick(10); fcRoll = 0; tick(10); fcHead = 300; tick(10);
    CHECK(DrState == DR_DONE && sent("vis bT,0") && fields["rs"].find("custom mounting") != std::string::npos);
    asked = 0; fcLog.clear(); DirTurnTapped(); CHECK(asked == 0 && fcLog.empty()); fcHead = 180;
    EndDirView(); fc["38"] = "000000000000"; DirStart(); tick(12);
    // (review 5) the mounting cannot be read as the page opens: "turned round" says so, and Again reads it once more
    EndDirView(); { std::string keep = fc["38"]; fc.erase("38"); DirStart(); tick(12); CHECK(DrMountKnown && !DrMountOk);
      DirStartTapped(); fcPitch = -250; tick(10); fcPitch = 0; tick(10); fcRoll = -250; tick(10); fcRoll = 0; tick(10); fcHead = 300; tick(10);
      CHECK(DrState == DR_DONE && sent("vis bT,0") && fields["rs"].find("could not be read") != std::string::npos);
      fc["38"] = keep; fcHead = 180; DirStartTapped(); tick(12); CHECK(DrMountKnown && DrMountOk); }
    EndDirView(); DirStart(); tick(12);
    // the screen goes dark in the middle of a fix: it is carried through all the same (written, stored, checked, restarted)
    fc["38"] = "000000000000"; DirStartTapped(); fcPitch = -250; tick(10); fcPitch = 0; tick(10); fcRoll = -250; tick(10); fcRoll = 0; tick(10); fcHead = 300; tick(10);
    CHECK(DrState == DR_DONE && DrTurnedRound()); fcLog.clear(); fcStores = fcRestarts = 0; DirTurnTapped(); tick(2); CurrentView = BLANKVIEW; tick(130);
    CHECK(fc["38"] == "00000000B400" && fcStores == 1 && fcRestarts == 1 && DrState == DR_IDLE);
    CurrentView = DIRVIEW; fcHead = 180; tick(10);
    // another axis: a nose-down move seen as a side going down - not fixable here
    DirStartTapped(); fcRoll = 300; tick(10); CHECK(DrResult[1] == -2); fcRoll = 0; tick(10); fcRoll = 270; tick(10); fcRoll = 0; tick(10); fcHead = 300; tick(10);
    CHECK(DrState == DR_DONE && sent("vis bT,0") && fields["rs"].find("configurator") != std::string::npos);
    EndDirView(); CHECK(CurrentView == TOOLSVIEW);
    fcFromBackup(); fcHead = 180;

    // ==== 4. UNDO: an MSP page's save (read, then written, then stored) - and put back
    UndoUsed();
    CurrentView = BEEPERVIEW; UndoNewVisit();
    MspAsk(10, nullptr, 0); MspAsk(184, nullptr, 0); tick(5);
    { uint8_t n[6] = {'H', 'E', 'L', 'L', 'O', 0}; MspAsk(11, n, 6); uint8_t b[9] = {1, 0, 0, 0, 3, 0, 0, 0, 0}; MspAsk(185, b, 9); MspAsk(250, nullptr, 0); tick(5); }
    CHECK(UndoReady && UndoKeepN == 2 && strcmp(UndoWhat, "Beeper & name") == 0 && fc["10"] == "48454C4C4F" && fc["184"] == "010000000300000000");
    CurrentView = ROTORFLIGHTVIEW; UndoNewVisit(); StartToolsView(); CHECK(fields["tU"] == "Last save: Beeper & name, just now");
    now += 3 * 60000; ToolsShow(); CHECK(fields["tU"] == "Last save: Beeper & name, 3 min ago");
    asked = 0; fcLog.clear(); fcStores = 0; confirmAnswer = true; ToolsUndo(); CHECK(asked == 1 && BakJob == BAK_JOB_UNDO); runJob();
    CHECK(fc["10"] == "425448554E44455232" && fc["184"] == "000000000105000000" && fcStores == 1 && count(68) == 0 && lastBox.find("Put back as it was") != std::string::npos && !UndoOffered());
    CHECK(card[bakPath] == BT2);   // (the backup itself never written)
    // a per-bank MSP save (rescue: bank chosen with 210): its bank's key, put back into that bank
    CurrentView = RESCUEVIEW; UndoNewVisit(); { uint8_t s1 = 2; MspAsk(210, &s1, 1); } MspAsk(146, nullptr, 0); tick(5);
    { std::string w = fc["146.2"]; uint8_t b[30]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 2; MspAsk(147, b, n); MspAsk(250, nullptr, 0); tick(5); }
    CHECK(UndoReady && strcmp(UndoKeep[0].key, "146.2") == 0 && strcmp(UndoWhat, "Rescue (bank 3)") == 0 && byteOf(fc["146.2"], 0) == 2);
    fcPid = 0; CurrentView = ROTORFLIGHTVIEW; StartToolsView(); ToolsUndo(); runJob();
    CHECK(byteOf(fc["146.2"], 0) == 0 && byteOf(fc["146.0"], 0) == 0 && fcPid == Bank - 1);   // (bank 3 put back; the transmitter's bank chosen again)
    // a Version 1 word page (PIDs): the bank check reads the transmitter's bank once more, then the words go
    static int thens = 0; struct T { static void then() { ++thens; } };
    CurrentView = PIDVIEW; fcLog.clear(); Bank = 2; fcPid = 1; BankCheck(false, 2, T::then, "page PIDView"); tick(8);
    CHECK(thens == 1 && fcLog.size() == 2 && fcLog[0].fn == 101 && fcLog[1].fn == 112 && UndoReady && strcmp(UndoKeep[0].key, "112.1") == 0 && strcmp(UndoWhat, "PIDs (bank 2)") == 0);
    setByte("112.1", 0, 0x46);   // (the receiver writes the new Roll P)
    CurrentView = ROTORFLIGHTVIEW; StartToolsView(); ToolsUndo(); runJob();
    CHECK(byteOf(fc["112.1"], 0) == 0x37 && count(202) == 1);
    // on a 4 MB screen: no read before the words - the save goes exactly as before
    bigScreen = false; CurrentView = PIDVIEW; fcLog.clear(); thens = 0; BankCheck(false, 2, T::then, "page PIDView"); tick(8);
    CHECK(thens == 1 && fcLog.size() == 1 && fcLog[0].fn == 101);
    thens = 0; fcLog.clear(); UndoPreSave(142, -1, T::then, "page RFGovViewGlbl"); CHECK(thens == 1 && fcLog.empty());
    bigScreen = true;
    // the governor global page (no bank): read first, then the words
    CurrentView = RFGOVERNORVIEW_GLOBAL; thens = 0; fcLog.clear(); UndoPreSave(142, -1, T::then, "page RFGovViewGlbl"); CHECK(thens == 0 && UndoPreBusy()); tick(4);
    CHECK(thens == 1 && fcLog.size() == 1 && fcLog[0].fn == 142 && UndoReady && strcmp(UndoKeep[0].key, "142") == 0 && strcmp(UndoWhat, "Governor (global)") == 0);
    // no answer to that read: the words go all the same (3 s), and nothing is offered
    holdFc = true; thens = 0; UndoPreSave(142, -1, T::then, "page RFGovViewGlbl"); tick(30); CHECK(thens == 0); tick(40); CHECK(thens == 1 && !UndoReady && UndoBad); holdFc = false; pend.clear();
    // (review 1) the bank switch moves after a bank was chosen: what is read and written after is not kept - no wrong bank put back
    CurrentView = EASYVIEW; UndoNewVisit(); Bank = 2; fcPid = 1; { uint8_t b1 = 1; MspAsk(210, &b1, 1); } MspAsk(112, nullptr, 0); tick(4);
    Bank = 3; fcPid = 2;   // (the bank switch: the transmitter on bank 3, and the flight controller follows it - no 210 of ours)
    MspAsk(112, nullptr, 0); tick(3);
    { std::string w = fc["112.2"]; uint8_t b[40]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 0x50; MspAsk(202, b, n); MspAsk(250, nullptr, 0); tick(4); }
    CHECK(!UndoOffered() && UndoBad && strstr(UndoBadWhy, "which bank") && byteOf(fc["112.1"], 0) == 0x37);
    Bank = 2; fcPid = 1; fcFromBackup();
    // (review 2) one save that stores more than once (Easy tuning: the PIDs, then the governor bank by bank) is ONE save, whole
    CurrentView = EASYVIEW; UndoNewVisit(); { uint8_t b1 = 1; MspAsk(210, &b1, 1); } MspAsk(112, nullptr, 0); MspAsk(148, nullptr, 0); tick(5);
    { std::string w = fc["112.1"]; uint8_t b[40]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 0x51; MspAsk(202, b, n); MspAsk(250, nullptr, 0); tick(3); }
    { std::string w = fc["148.1"]; uint8_t b[40]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[1] = 0x09; MspAsk(149, b, n); MspAsk(250, nullptr, 0); tick(3); }   // (head speed 1400 -> 2424: Black Thunder 2's bank 2 has PID spool-up on already)
    CHECK(UndoOffered() && UndoKeepN == 2 && !UndoBad);
    CurrentView = ROTORFLIGHTVIEW; StartToolsView(); fcLog.clear(); ToolsUndo(); runJob();
    CHECK(byteOf(fc["112.1"], 0) == 0x37 && byteOf(fc["148.1"], 1) == 0x05 && lastBox.find("2 written") != std::string::npos);
    fcFromBackup();
    // two saves on one page with a pause between them: two saves - the second's before is its own read-back, not the first's
    CurrentView = BEEPERVIEW; UndoNewVisit(); MspAsk(184, nullptr, 0); tick(3);
    { uint8_t b[9] = {1, 0, 0, 0, 2, 0, 0, 0, 0}; MspAsk(185, b, 9); MspAsk(250, nullptr, 0); MspAsk(184, nullptr, 0); tick(5); }
    now += 10000; { uint8_t b[9] = {3, 0, 0, 0, 4, 0, 0, 0, 0}; MspAsk(185, b, 9); MspAsk(250, nullptr, 0); tick(4); }
    CHECK(UndoOffered() && UndoKeepN == 1 && UndoKeep[0].b[0] == 1 && UndoKeep[0].b[4] == 2);
    // a second save with no read-back between: not undoable (its before is not known) - never the first save's before again
    now += 10000; { uint8_t b[9] = {5, 0, 0, 0, 5, 0, 0, 0, 0}; MspAsk(185, b, 9); MspAsk(250, nullptr, 0); tick(4); }
    CHECK(!UndoOffered() && UndoBad);
    fcFromBackup();
    // (review 3) the model goes while the read before the words is out: refused - nothing into the file, nothing sent
    { static int t3 = 0; struct T3 { static void then() { ++t3; } };
      CurrentView = PIDVIEW; Bank = 2; fcPid = 1; holdFc = false; BankCheck(false, 2, T3::then, "page PIDView"); holdFc = true;   // (the 101 answered, the 112 after it not)
      tick(3); CHECK(UndoPreBusy() && t3 == 0); BoundFlag = false; boxes = 0; tick(4);
      CHECK(t3 == 0 && !UndoPreBusy() && boxes == 1 && lastBox.find("no longer") != std::string::npos && lastBoxPage == "page PIDView" && card[bakPath] == BT2);
      BoundFlag = true; holdFc = false; pend.clear(); }
    // (review 7) the flight controller says ARMED to that read: refused
    { static int t7 = 0; struct T7 { static void then() { ++t7; } };
      now += 10000;   // (the read the last test held back given up: the pipe free)
      CurrentView = RFGOVERNORVIEW_GLOBAL; armed409 = true; boxes = 0; UndoPreSave(142, -1, T7::then, "page RFGovViewGlbl"); tick(4); armed409 = false;
      CHECK(t7 == 0 && boxes == 0 && lastLog.find("ARMED") != std::string::npos); }   // (review 2: no box that waits while it is armed - a sound and the log)
    // (review 2) the safety goes off while the read is out (the radios' rule lets Bluetooth go): refused with no box at all
    { static int t9 = 0; struct T9 { static void then() { ++t9; } };
      now += 10000; CurrentView = RFGOVERNORVIEW_GLOBAL; holdFc = true; boxes = 0; logs = 0; UndoPreSave(142, -1, T9::then, "page RFGovViewGlbl"); tick(2);
      safetyOff = true; PipeState = 0; tick(2); safetyOff = false; PipeState = 2; holdFc = false; pend.clear();
      CHECK(t9 == 0 && boxes == 0 && logs == 1 && lastLog.find("safety") != std::string::npos && !UndoPreBusy()); }
    // (review 4) the page left meanwhile: no box over the page the pilot is on
    { static int t10 = 0; struct T10 { static void then() { ++t10; } };
      now += 10000; CurrentView = PIDVIEW; holdFc = true; boxes = 0; UndoPreSave(112, 1, T10::then, "page PIDView"); tick(2);
      CurrentView = ROTORFLIGHTVIEW; BoundFlag = false; tick(2); BoundFlag = true; holdFc = false; pend.clear();
      CHECK(t10 == 0 && boxes == 0 && lastLog.find("no longer") != std::string::npos); }
    // (review 2) a second Save while the first one's read is out: the same save, not two at once
    { static int t11 = 0; struct T11 { static void then() { ++t11; } };
      now += 10000; CurrentView = PIDVIEW; Bank = 2; fcPid = 1; fcLog.clear(); BankCheck(false, 2, T11::then, "page PIDView"); tick(1);
      BankCheck(false, 2, T11::then, "page PIDView"); tick(8);
      CHECK(t11 == 1 && count(101) == 1 && count(112) == 1); }
    // (review 3) a save on bank 1, the bank switch flipped, a save on bank 2 a moment later: two saves - only the last undone,
    // and it is offered (the last review: a store ends a save, except Easy tuning's - no rule against a flip between two saves)
    CurrentView = RESCUEVIEW; UndoNewVisit(); Bank = 1;
    { uint8_t s0 = 0; MspAsk(210, &s0, 1); } MspAsk(146, nullptr, 0); tick(4);
    { std::string w = fc["146.0"]; uint8_t b[30]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 1; MspAsk(147, b, n); MspAsk(250, nullptr, 0); tick(4); }
    Bank = 2; { uint8_t s1 = 1; MspAsk(210, &s1, 1); } MspAsk(146, nullptr, 0); tick(4);
    { std::string w = fc["146.1"]; uint8_t b[30]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 2; MspAsk(147, b, n); MspAsk(250, nullptr, 0); tick(4); }
    CHECK(UndoOffered() && UndoKeepN == 1 && strcmp(UndoKeep[0].key, "146.1") == 0 && strcmp(UndoWhat, "Rescue (bank 2)") == 0);
    CurrentView = ROTORFLIGHTVIEW; StartToolsView(); ToolsUndo(); runJob();
    CHECK(byteOf(fc["146.1"], 0) == 0 && byteOf(fc["146.0"], 0) == 1);   // (bank 2 put back; bank 1's own save left as made)
    Bank = 2; fcPid = 1; fcFromBackup();
    // (the last review) the same with Easy tuning, whose save goes on after a store: the flip is caught by the bank each read was of
    CurrentView = EASYVIEW; UndoNewVisit(); Bank = 1; fcPid = 0;
    { uint8_t s0 = 0; MspAsk(210, &s0, 1); } MspAsk(112, nullptr, 0); tick(4);
    { std::string w = fc["112.0"]; uint8_t b[40]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 0x52; MspAsk(202, b, n); MspAsk(250, nullptr, 0); tick(3); }
    Bank = 2; fcPid = 1; MspAsk(112, nullptr, 0); tick(3);   // (the switch: no 210 of ours - this read is of a bank not known)
    { std::string w = fc["112.1"]; uint8_t b[40]; int n = 0; for (size_t i = 0; i + 1 < w.size(); i += 2) b[n++] = (uint8_t) strtol(w.substr(i, 2).c_str(), nullptr, 16); b[0] = 0x53; MspAsk(202, b, n); MspAsk(250, nullptr, 0); tick(3); }
    CHECK(!UndoOffered() && UndoBad && strstr(UndoBadWhy, "which bank"));
    Bank = 2; fcPid = 1; fcFromBackup();
    // (the last review) a word page left while its bank check was out: the read before the words is that page's, by name;
    // and a refusal of it then says nothing over the page the pilot went to (a box from the loop would take them back)
    { static int t14 = 0; struct T14 { static void then() { ++t14; } };
      now += 10000; CurrentView = PIDVIEW; Bank = 2; fcPid = 1; BankCheck(false, 2, T14::then, "page PIDView"); CurrentView = ROTORFLIGHTVIEW; tick(8);
      CHECK(t14 == 1 && UndoReady && strcmp(UndoWhat, "PIDs (bank 2)") == 0);
      now += 10000; CurrentView = PIDVIEW; BankCheck(false, 2, T14::then, "page PIDView"); holdFc = true; CurrentView = ROTORFLIGHTVIEW; tick(3);
      CHECK(UndoPreBusy()); BoundFlag = false; boxes = 0; logs = 0; tick(4);
      CHECK(t14 == 1 && boxes == 0 && logs == 1 && lastLog.find("no longer") != std::string::npos && !UndoPreBusy());
      BoundFlag = true; holdFc = false; pend.clear(); }
    // the flight controller's own ARMED (101) at a word page's save, on the bench: no box that waits - the page says it
    { static int t12 = 0; struct T12 { static void then() { ++t12; } };
      now += 10000; CurrentView = PIDVIEW; fcArmed = true; boxes = 0; pageHides = 0; RfLeaveAfterSave = true; cmds.clear(); BankCheck(false, 2, T12::then, "page PIDView"); tick(4); fcArmed = false;
      CHECK(t12 == 0 && boxes == 0 && pageHides == 1 && fields["busy"].find("ARMED") != std::string::npos && sent("vis b3,1") && sent("vis busy,1") && !RfLeaveAfterSave && SilenceMsgUntil > now);
      // (the last review) that line is taken away after six seconds on its own page only - never the next page's "Loading ..."
      cmds.clear(); CurrentView = RATESVIEW_RF; now += 7000; SilenceTick(); CHECK(SilenceMsgUntil == 0 && !sent("vis busy,0"));
      CurrentView = PIDVIEW; RfWordPageSays(PIDVIEW, "x"); cmds.clear(); now += 7000; SilenceTick(); CHECK(SilenceMsgUntil == 0 && sent("vis busy,0")); }
    // a save on another word page while the first one's check is out: not made, and that page says so (never two at once)
    { static int t13 = 0; struct T13 { static void then() { ++t13; } };
      now += 10000; CurrentView = PIDVIEW; holdFc = true; BankCheck(false, 2, T13::then, "page PIDView"); CurrentView = RFGOVERNORVIEW_PROFILE; pageHides = 0; fields["busy"] = "";
      BankCheck(false, 2, T13::then, "page RFGovView"); CHECK(t13 == 0 && pageHides == 1 && fields["busy"].find("still being checked") != std::string::npos);
      // a check left unanswered while the pilot was elsewhere is never resumed: 12 s on, it is let go
      now += 13000; PipeReqSentMs = now; CurrentView = PIDVIEW; boxes = 0; BankCheckTick(); CHECK(t13 == 0 && !BcStep && (boxes == 1 || logs > 0) && lastBox.find("not finish") != std::string::npos);
      holdFc = false; pend.clear(); }
    // (review, low) a busy pipe: no read on top - this save cannot be undone, and no older one is offered as "the last"
    { static int t8 = 0; struct T8 { static void then() { ++t8; } };
      CurrentView = BEEPERVIEW; UndoNewVisit(); MspAsk(184, nullptr, 0); tick(3); { uint8_t b[9] = {1, 0, 0, 0, 2, 0, 0, 0, 0}; MspAsk(185, b, 9); MspAsk(250, nullptr, 0); tick(4); }
      CHECK(UndoOffered());
      CurrentView = RFGOVERNORVIEW_GLOBAL; holdFc = true; MspAsk(101, nullptr, 0); holdFc = false; UndoPreSave(142, -1, T8::then, "page RFGovViewGlbl");
      CHECK(t8 == 1 && !UndoOffered() && UndoBad); now += 10000; tick(2); pend.clear(); }
    // (review, low) a level calibration (205, no data) is a save that cannot be undone
    CurrentView = LEVELVIEW; UndoNewVisit(); MspAsk(205, nullptr, 0); tick(2); CHECK(!UndoOffered() && UndoBad && strstr(UndoBadWhy, "calibrat"));
    fcFromBackup();
    // saves that cannot be undone say why
    CurrentView = ADJUSTVIEW; UndoNewVisit(); MspAsk(34, nullptr, 0); tick(3); { uint8_t s[5] = {0, 0, 0, 0, 120}; MspAsk(35, s, 5); MspAsk(250, nullptr, 0); tick(3); }
    CHECK(!UndoOffered() && UndoBad && strstr(UndoBadWhy, "switches too"));
    CurrentView = COPYBANKVIEW; UndoNewVisit(); { uint8_t c[3] = {0, 1, 0}; MspAsk(183, c, 3); MspAsk(250, nullptr, 0); tick(3); } CHECK(!UndoOffered() && strstr(UndoBadWhy, "copied bank"));
    CurrentView = FILTERVIEW; UndoNewVisit(); { uint8_t f[27] = {0}; MspAsk(93, f, 27); MspAsk(250, nullptr, 0); tick(3); } CHECK(!UndoOffered() && strstr(UndoBadWhy, "had not been read"));
    CurrentView = ROTORFLIGHTVIEW; StartToolsView(); boxes = 0; ToolsUndo(); CHECK(boxes == 1 && lastBox.find("cannot be") != std::string::npos);
    // another model: what was kept is not offered
    CurrentView = BEEPERVIEW; UndoNewVisit(); MspAsk(10, nullptr, 0); tick(3); { uint8_t n[2] = {'X', 0}; MspAsk(11, n, 2); MspAsk(250, nullptr, 0); tick(3); }
    CHECK(UndoOffered()); strcpy(ModelName, "Goblin"); CHECK(!UndoOffered()); strcpy(ModelName, "Black Thunder 2");
    UndoUsed(); fcFromBackup();
    // the backup's own jobs are not saves
    CurrentView = RFBACKUP_RESTOREVIEW; BakForModel(); BakStart(BAK_JOB_RESTORE); runJob(); CHECK(!UndoOffered());

    // ==== 5. WHAT CHANGED? against the real backup: nothing; then three changes named, each put back alone
    CurrentView = ROTORFLIGHTVIEW; StartToolsView(); fcLog.clear(); ToolsChanges(); CHECK(CurrentView == CHANGESVIEW && BakJob == BAK_JOB_COMPARE); runJob();
    CHECK(ChgDone && ChgN == 0 && ChgUnread == 0 && fields["hd"] == "Nothing changed since the backup of 2026-11-03 15:34" && count(250) == 0 && count(210) > 0);
    setByte("112.1", 0, 70); setByte("112.1", 8, 99);                           // bank 2: Roll P 55 -> 70, Pitch P too
    { std::string &f = fc["36"]; f = "0804003C"; }                               // features: the RPM filter (bit 30) off
    fc["10"] = "474F424C494E";                                                     // the name
    setByte("34", 3, 0x64);                                                        // the arm switch's end, 2100 -> 2000 us
    ChangesAgain(); runJob();
    const int rP = chgRowOf("PIDs bank 2: Roll P 55 -> 70"), rF = chgRowOf("Features: RPM filter on -> off"), rN = chgRowOf("Name: BTHUNDER2 -> GOBLIN");
    CHECK(rP >= 0 && chgRowOf("PIDs bank 2: Pitch P") >= 0 && rF >= 0 && rN >= 0 && chgRowOf("Switches: Slot 1 to 2100 us -> 2000 us") >= 0 && ChgN == 5);
    CHECK(fields["hd"] == "5 changes since the backup of 2026-11-03 15:34");
    // Roll P put back: nothing else in its key moves (Pitch P stays 99); no restart for PIDs
    ChgFirst = (rP / 6) * 6; ChgShow(); ScreenEventArg = (uint8_t)(rP - ChgFirst + 1); fcLog.clear(); fcRestarts = 0; asked = 0; ChangesPutBack(); CHECK(asked == 1 && BakJob == BAK_JOB_PUTBACK); runJob();
    CHECK(byteOf(fc["112.1"], 0) == 55 && byteOf(fc["112.1"], 8) == 99 && count(202) == 1 && fcRestarts == 0 && ChgRows[rP].done && lastBox.find("Put back as the backup has it.") == 0);
    // the RPM filter feature: that bit alone, and a restart (Rotorflight reads its features at its start)
    ChgFirst = (rF / 6) * 6; ScreenEventArg = (uint8_t)(rF - ChgFirst + 1); fcLog.clear(); ChangesPutBack(); runJob();
    CHECK(fc["36"] == "0804007C" && count(37) == 1 && fcRestarts == 1);
    // the name: the whole key
    ChgFirst = (rN / 6) * 6; ScreenEventArg = (uint8_t)(rN - ChgFirst + 1); ChangesPutBack(); runJob(); CHECK(fc["10"] == "425448554E44455232");
    CHECK(card[bakPath] == BT2 && !BakDirty);   // (the backup on the card, and in memory, untouched)
    { const int rS = chgRowOf("Switches: Slot 1"); ChgFirst = (rS / 6) * 6; ScreenEventArg = (uint8_t)(rS - ChgFirst + 1); fcLog.clear(); ChangesPutBack(); runJob();
      CHECK(count(35) == 1 && lastDataOf(35).size() == 10 && byteOf(fc["34"], 3) == 0x78); }
    setByte("34", 3, 0x64); ChangesAgain(); runJob();
    // the model goes in the middle of a put back: stopped, nothing more sent, nothing into the file
    { const int rS = chgRowOf("Switches: Slot 1"); ChgFirst = (rS / 6) * 6; ScreenEventArg = (uint8_t)(rS - ChgFirst + 1); ChangesPutBack(); tick(2); BoundFlag = false; const size_t before = fcLog.size(); runJob();
      CHECK(BakJob == BAK_JOB_NONE && fcLog.size() <= before + 1 && lastBox.find("Not put back") == 0 && card[bakPath] == BT2); BoundFlag = true; }
    // the telemetry's link speed (73, bytes 8-11) is the flight controller's own: never shown as a change
    fcFromBackup(); if (fc.count("73") && fc["73"].size() >= 24) { setByte("73", 9, 0x77); setByte("73", 10, 0x12); ChangesAgain(); runJob(); CHECK(ChgDone && !ChgStopped && ChgN == 0); }
    fcFromBackup(); fail210 = 5; boxes = 0; fcLog.clear(); ChangesAgain(); runJob();
    CHECK(ChgDone && ChgStopped && boxes == 1 && lastBox.find("Not everything could be read") == 0 && fields["hd"].find("Not all read") == 0 && fcPid == Bank - 1);
    fail210 = 0; ChangesAgain(); runJob(); CHECK(!ChgStopped && ChgN == 0 && fields["hd"].find("Nothing changed") == 0);
    // B197 (Malcolm, 8 Nov: "I changed the trim from 1 to 0.5 not 10 to 5"): a value in its page's units
    { char o[24]; const uint8_t vp[2] = {0, 0}, mo[2] = {0, 1}; const ChgCtx cv = {42, -1, vp, 2}, cm = {42, -1, mo, 2}, in1 = {174, 1, nullptr, 0}, in3 = {174, 3, nullptr, 0};
      ChgFmt(o, sizeof o, K_S16_T10P, 10, &cv); CHECK(strcmp(o, "1.0 %") == 0); ChgFmt(o, sizeof o, K_S16_T10P, 5, &cv); CHECK(strcmp(o, "0.5 %") == 0);
      ChgFmt(o, sizeof o, K_S16_T10P, -5, &cv); CHECK(strcmp(o, "-0.5 %") == 0); ChgFmt(o, sizeof o, K_S16_T10D, -123, &cv); CHECK(strcmp(o, "-12.3 deg") == 0);
      ChgFmt(o, sizeof o, K_U16_DEG12, 1000, &cv); CHECK(strcmp(o, "12.0 deg") == 0); ChgFmt(o, sizeof o, K_U16_DEG12, 1750, &cv); CHECK(strcmp(o, "21.0 deg") == 0);
      ChgFmt(o, sizeof o, K_S16_TAIL, 50, &cv); CHECK(strcmp(o, "1.2 deg") == 0); ChgFmt(o, sizeof o, K_S16_TAIL, 50, &cm); CHECK(strcmp(o, "5.0 %") == 0);
      ChgFmt(o, sizeof o, K_S16_INDEG, -1000, &in1); CHECK(strcmp(o, "-12.0 deg") == 0); ChgFmt(o, sizeof o, K_S16_INDEG, 1000, &in3); CHECK(strcmp(o, byteOf(fc["42"], 1) ? "100.0 %" : "24.0 deg") == 0);
      ChgFmt(o, sizeof o, K_S8_GEO, 15, &cv); CHECK(strcmp(o, "3.0") == 0); ChgFmt(o, sizeof o, K_S8_GEO, -1, &cv); CHECK(strcmp(o, "-0.2") == 0);
      ChgFmt(o, sizeof o, K_U16_H100V, 330, &cv); CHECK(strcmp(o, "3.30 V") == 0); ChgFmt(o, sizeof o, K_U16_H100M, 50, &cv); CHECK(strcmp(o, "0.50 m") == 0);
      ChgFmt(o, sizeof o, K_U8_T10S, 25, &cv); CHECK(strcmp(o, "2.5 s") == 0); ChgFmt(o, sizeof o, K_U16_T10P, 1000, &cv); CHECK(strcmp(o, "100.0 %") == 0);
      ChgFmt(o, sizeof o, K_S16_DEG, 180, &cv); CHECK(strcmp(o, "180 deg") == 0); ChgFmt(o, sizeof o, K_U16_HZ, 333, &cv); CHECK(strcmp(o, "333 Hz") == 0); ChgFmt(o, sizeof o, K_S16_US, -500, &cv); CHECK(strcmp(o, "-500 us") == 0);
      // the rows, against the real backup: the swash trim pitch set to 0.5 %, a rescue time, a cell voltage, the level trim
      auto s16 = [](const std::string &h, int off) { return (int) (int16_t) (byteOf(h, off) | (byteOf(h, off + 1) << 8)); };
      char was[24], expect[96]; ChgTenths(was, sizeof was, s16(fc["42"], 13), " %"); snprintf(expect, sizeof expect, "Mixer: Swash trim pitch %s -> 0.5 %%", was);
      setByte("42", 13, 5); setByte("42", 14, 0); setByte("146.0", 5, 25); setByte("32", 11, 0x68); setByte("32", 12, 0x01); setByte("240", 0, 0xF6); setByte("240", 1, 0xFF);
      ChangesAgain(); runJob();
      CHECK(ChgN == 4 && chgRowOf(expect) >= 0 && chgRowOf("Rescue bank 1: Climb time ") >= 0 && chgRowOf("-> 2.5 s") >= 0 && chgRowOf("Battery: Cell warning ") >= 0 && chgRowOf("-> 3.60 V") >= 0 && chgRowOf("Level: Pitch trim ") >= 0 && chgRowOf("-> -1.0 deg") >= 0);
      // put back by the row: the bytes, whatever the words
      const int rT = chgRowOf("Swash trim pitch"); ChgFirst = (rT / 6) * 6; ChgShow(); ScreenEventArg = (uint8_t)(rT - ChgFirst + 1); fcLog.clear(); ChangesPutBack(); runJob();
      CHECK(s16(fc["42"], 13) == s16(std::string(BT2).substr(std::string(BT2).find("\n42=") + 4, 42), 13) && count(43) == 1 && ChgRows[rT].done);
      fcFromBackup(); }
    // (review, low) a request already out when the comparison is asked for: its first question waits for it
    now += 10000; holdFc = true; MspAsk(101, nullptr, 0); holdFc = false; fcLog.clear(); ChangesAgain(); tick(3);
    CHECK(BakJob == BAK_JOB_COMPARE && BakStep == 0 && fcLog.empty()); now += 10000; runJob(); CHECK(ChgDone && !ChgStopped && ChgN == 0);
    // the safety goes off in the middle of the comparison (the radios' rule lets Bluetooth go): stopped, and no box that waits
    ChangesAgain(); tick(20); safetyOff = true; PipeState = 0; boxes = 0; logs = 0; runJob(); safetyOff = false; PipeState = 2;
    CHECK(ChgDone && ChgStopped && boxes == 0 && logs >= 1 && lastLog.find("Not everything could be read") != std::string::npos && BakJob == BAK_JOB_NONE);
    ChangesAgain(); runJob(); CHECK(!ChgStopped);
    // Bluetooth goes in the middle of the comparison: stopped at once, said so (not nine seconds a request, item after item)
    ChangesAgain(); tick(20); PipeState = 1; boxes = 0; runJob(); PipeState = 2;
    CHECK(ChgDone && ChgStopped && boxes == 1 && lastBox.find("Bluetooth") != std::string::npos && BakJob == BAK_JOB_NONE);
    ChangesAgain(); runJob(); CHECK(!ChgStopped);
    EndChangesView(); CHECK(CurrentView == TOOLSVIEW);
    fcFromBackup();

    // ==== 6. THE GUIDE: steps ticked as their pages come back; kept on the card; the check inside it comes back to it
    ToolsGuide(); CHECK(CurrentView == GUIDEVIEW && fields["nx"] == "Next: 1. Direction check" && fields["g0"] == "1. Direction check" && fields["t9"] == "0 of 16 done");
    GuideNextTapped(); CHECK(CurrentView == DIRVIEW && RfHomeN == 1);
    EndDirView(); CHECK(CurrentView == GUIDEVIEW && (GdDone & 1) && card["/rfbak/Black_Thunder_2.rfg"] == "done=0001\n" && fields["nx"] == "Next: 2. Calibrate level");
    ScreenEventArg = 4; GuideStepTapped(); CHECK(opened == "battery" && CurrentView == BATTERYVIEW);
    RotorFlightStart(); CHECK(CurrentView == GUIDEVIEW && (GdDone & 8) && rfStarts == 0 && sent("k3.bco=2016"));
    refuseOpen = true; ScreenEventArg = 2; cmds.clear(); GuideStepTapped(); refuseOpen = false;
    CHECK(CurrentView == GUIDEVIEW && !(GdDone & 2) && RfHomeN == 0 && sent("page RFGuideView"));
    GuidePageTapped(); CHECK(fields["g6"] == "15. Check my setup" && fields["bPg"] == "< Steps 1 - 8");
    ScreenEventArg = 7; fcLog.clear(); GuideStepTapped(); CHECK(CurrentView == CHECKVIEW && RfHomeN == 1); tick(80);
    fcFlags = 1u << 23; CheckAgain(); tick(80); { const int r = rowOf("Calibrate level first"); ScreenEventArg = (uint8_t)(r + 1); CheckFixTapped(); }
    CHECK(CurrentView == LEVELVIEW && RfHomeN == 2);
    fcFlags = 0; RotorFlightStart(); CHECK(CurrentView == CHECKVIEW && RfHomeN == 1); tick(80);
    EndCheckView(); CHECK(CurrentView == GUIDEVIEW && (GdDone & (1u << 14)) && RfHomeN == 0);
    // the ticks from the card for another visit; Start again clears them
    strcpy(GdModel, ""); GdDone = 0; GdLoad(); CHECK(GdDone == ((1u << 0) | (1u << 3) | (1u << 14)));
    confirmAnswer = true; GuideRestart(); CHECK(GdDone == 0 && card["/rfbak/Black_Thunder_2.rfg"] == "done=0000\n");
    EndGuideView(); CHECK(CurrentView == TOOLSVIEW);
    // the menu's own way in (Model setup) clears a way back left behind
    RfHomeN = 1; RfHome[0] = GUIDEVIEW; CurrentView = RXSETUPVIEW; RotorFlightStart(); CHECK(CurrentView == ROTORFLIGHTVIEW && RfHomeN == 0);
    EndToolsView();

    // ==== 7. every row's words at their longest, for the screen's own font widths (measured by the Python below)
    { FILE *w = fopen(getenv("WORDS"), "w");
      if (w) {
        char t[200], sec[40], val[24];
        for (int i = 0; i < CHG_TABLES; ++i) {   // What changed?: each named setting, the longest section, the widest values
            const ChgT &T = ChgTables[i]; char key[16];
            if (T.fn == 112 || T.fn == 94 || T.fn == 148 || T.fn == 146 || T.fn == 111) snprintf(key, sizeof key, "%u.5", T.fn); else if (T.fn == 174) snprintf(key, sizeof key, "174.04"); else snprintf(key, sizeof key, "%u", T.fn);
            ChgSection(key, sec, sizeof sec);
            for (int f = 0; f < T.nf; ++f) { const ChgF &F = T.f[f]; if (F.kind == K_SKIP || F.kind == K_BITS || F.kind == K_TEXT) continue;
              for (int tail = 0; tail < 2; ++tail) {   // (a tail of either kind: the mixer's and the inputs' tail values read in % or degrees)
                const uint8_t img[2] = {0, (uint8_t)tail}; const ChgCtx c = {(int)T.fn, T.fn == 174 ? 3 : -1, img, 2};
                const int wd = ChgKindW(F.kind);
                const long big = F.kind == K_STEP ? 2135 : ChgKindSigned(F.kind) ? (wd == 1 ? -128 : -32768) : wd == 1 ? 255 : wd == 2 ? 65535 : 0xFFFFFFFFL;
                ChgFmt(val, sizeof val, F.kind, big, &c);
                if (T.item) { char itn[16]; snprintf(itn, sizeof itn, T.item, 20); snprintf(t, sizeof t, "%s: %s %s %s -> %s", sec, itn, F.name, val, val); } else snprintf(t, sizeof t, "%s: %s %s -> %s", sec, F.name, val, val);
                fprintf(w, "548\t2\t%s\n", t);
                if (F.kind != K_S16_TAIL) break; } } }
        for (int b = 0; b < 32; ++b) if (ChgFeatureNames[b][0]) fprintf(w, "548\t2\tFeatures: %s off -> on\n", ChgFeatureNames[b]);
        fprintf(w, "548\t2\tName: ABCDEFGHIJKLMN -> ABCDEFGHIJKLMN\n");
        fprintf(w, "548\t2\tSensor alignment: changed\n");
        fprintf(w, "548\t2\tVoltage sensors: byte 255 255 -> 255\n");
        for (int i = 0; i < 27; ++i) fprintf(w, "516\t2\t%s\n", ArmWhy[i]);   // Check my setup's rows
        fprintf(w, "516\t2\tArm switch on channel 16: the safety drives 16\n516\t2\tArm zone reaches 988 us: arms, safety ON\n516\t2\tArm zone ends below 2012 us: may not arm\n");
        fprintf(w, "516\t2\tMain gear ratio backwards (65535 : 65535)\n516\t2\tTail gear ratio backwards (65535 : 65535)\n516\t2\tBlack box 100%% full\n");
        fprintf(w, "516\t2\tTilted 180\xB0: if it stands level, check it\n516\t2\tNothing found. A new model: Direction check\n516\t2\tRescue is on, but no switch starts it\n");
        fprintf(w, "702\t2\t9 stop it arming, 9 worth a look\n702\t2\t60 changes since the backup of 2026-11-03 15:34 (the first 60)\n");
        fprintf(w, "702\t2\tComparing with the backup of 2026-11-03 15:34 ...\n702\t2\tNothing changed since the backup of 2026-11-03 15:34\n");
        fprintf(w, "702\t2\tLast save: Mounting direction, 119 min ago\n702\t2\tLast save: Rates dynamics (rates bank 6), 119 min ago\n702\t2\tThe last save (Switches & knobs) cannot be undone\n");
        for (int i = 0; i < GD_STEPS; ++i) { fprintf(w, "339\t6\tNext: %d. %s\n300\t2\t%d. %s\n339\t2\t%s\n", i + 1, GdSteps[i].name, i + 1, GdSteps[i].name, "Go to step 16 ..."); }
        fprintf(w, "200\t2\t16 of 16 done\n");
        fclose(w); } }
    printf("test_tools: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''
prog = prog.replace('static void RotorFlightStart() {', 'static const char *BT2 = "' + bt2_c + '";\nstatic void RotorFlightStart() {', 1)
d = tempfile.mkdtemp(); import atexit, shutil as _sh; atexit.register(_sh.rmtree, d, True)
cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-Wno-format-truncation',
                    '-fsanitize=address,undefined', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit('test_tools: DID NOT COMPILE')
words = os.path.join(d, 'words.txt')
rc = subprocess.run([os.path.join(d, 't')], env=dict(os.environ, WORDS=words)).returncode
sys.path.insert(0, os.path.join(SCREEN, 'hmi'))
try:
    from fontw import width
    over = []
    for l in open(words, encoding='latin-1'):
        box, font, text = l.rstrip('\n').split('\t', 2)
        if width(int(font), text) > int(box) - 4: over.append('%d px > %s: %s' % (width(int(font), text), box, text))
    for o in over: print('TOO WIDE:', o)
    print('test_tools (the words\' widths): %d too wide' % len(over))
    if over: rc = 1
except ImportError:
    print('(the screen project is not beside TXV1B: the widths not measured)')

# ---- the wiring, by text
problems = []
rf = src('RF_RotorFlight.h')
i_gate, i_undo, i_home, i_page = rf.find('if (MotorEnabled ||'), rf.find('UndoNewVisit();'), rf.find('if (RfHomeBack()) return;'), rf.find('SendCommand((char *)"page RFView");')
if not (0 <= i_gate < i_undo < i_home < i_page): problems.append('RotorFlightStart: after its gate, UndoNewVisit then RfHomeBack, before the menu')
main = open(os.path.join(ROOT, 'TransmitterCode', 'src', 'main.cpp')).read()
t0 = main.index('void (*NumberedFunctions1[LASTFUNCTION1])(){'); body = main[t0:main.index('};', t0)]
entries = [l for l in body.split('\n')[1:] if l.strip() and not l.strip().startswith('//')]
table = {}
for k, l in enumerate(entries):
    mnum = re.search(r'//\s*(\d+)', l)
    if not mnum or int(mnum.group(1)) != k: problems.append('function table: entry %d says %r' % (k, l.strip()[:60]))
    table[k] = l.strip().split(',')[0]
if int(re.search(r'#define LASTFUNCTION1 (\d+)', main).group(1)) != len(entries): problems.append('LASTFUNCTION1 is not the table length')
if 'ToolsPoll();' not in main: problems.append('the loop does not call ToolsPoll()')
if 'RfToolsRedraw(); // B196' not in main: problems.append('the way back from Help does not draw the tools\' pages again')
want = {85: {'bGuide': 'ToolsGuide', 'bCheck': 'ToolsCheck', 'bDir': 'ToolsDirection', 'bChg': 'ToolsChanges', 'bUndo': 'ToolsUndo', 'b1': 'EndToolsView'},
        86: dict({'f%d' % k: 'CheckFixTapped' for k in range(6)}, bA='CheckAgain', b1='EndCheckView', bP='CheckPrev', bN='CheckNext'),
        87: {'bS': 'DirStartTapped', 'bT': 'DirTurnTapped', 'b1': 'EndDirView'},
        88: dict({'p%d' % k: 'ChangesPutBack' for k in range(6)}, bA='ChangesAgain', b1='EndChangesView', bP='ChangesPrev', bN='ChangesNext'),
        89: dict({'g%d' % k: 'GuideStepTapped' for k in range(8)}, bG='GuideNextTapped', bPg='GuidePageTapped', bR='GuideRestart', b1='EndGuideView'),
        8: {'Tools': 'StartToolsView'}}
pages_dir = os.path.join(SCREEN, 'sd', 'hmi', 'pages')
if os.path.isdir(pages_dir):
    for pid, comps in want.items():
        pg = json.load(open(os.path.join(pages_dir, '%d.json' % pid)))
        byname = {c['n']: c for c in pg['comps']}
        for n, fn in comps.items():
            scr = byname.get(n, {}).get('ev', {}).get('r', '')
            mc = re.search(r'\((\d+)<<8\)|va0\.val=(\d+)<<8', scr)
            code = int(mc.group(1) or mc.group(2)) if mc else -1
            if table.get(code) != fn: problems.append('page %d %s: code %s is %s, not %s' % (pid, n, code, table.get(code), fn))
        if pid != 8:
            hm = re.search(r'HelpView:([A-Z]+\.TXT)', byname['b0']['ev']['r'])
            if not hm or not os.path.exists(os.path.join(ROOT, 'Help files for SD', hm.group(1))): problems.append('page %d: its help file is missing' % pid)
    pre8 = json.load(open(os.path.join(pages_dir, '8.json')))['ev']['preinitialize']
    if 'vis Tools,0' not in pre8 or 'if(ldrcmb>=16)' not in pre8 or 'vis Cli,0' not in pre8: problems.append('page 8: Tools / Cli not swapped by ldrcmb')
    ix = {p['id']: p['name'] for p in json.load(open(os.path.join(SCREEN, 'sd', 'hmi', 'index.json')))['pages']}
    for pid, name in ((85, 'RFToolsView'), (86, 'RFCheckView'), (87, 'RFDirView'), (88, 'RFChangesView'), (89, 'RFGuideView')):
        if ix.get(pid) != name: problems.append('index.json: page %d is not %s' % (pid, name))
else: print('(the screen project is not beside TXV1B: its pages not checked)')
# What changed?'s names: each table tiles its setting's bytes - none twice, none left out - to the length Rotorflight sends
chg = src('RF_Changes.h'); widths = {'K_SKIP': 1, 'K_U8': 1, 'K_S8': 1, 'K_STEP': 1, 'K_U16': 2, 'K_S16': 2, 'K_T10': 2, 'K_U32': 4, 'K_HEX': 4, 'K_BITS': 4, 'K_TEXT': 0,
                                      'K_U8_T10S': 1, 'K_U8_T10P': 1, 'K_S8_GEO': 1, 'K_U16_T10P': 2, 'K_S16_T10P': 2, 'K_S16_T10D': 2, 'K_S16_DEG': 2, 'K_U16_DEG12': 2,
                                      'K_S16_INDEG': 2, 'K_S16_TAIL': 2, 'K_U16_H100V': 2, 'K_U16_H100M': 2, 'K_U16_US': 2, 'K_S16_US': 2, 'K_U16_HZ': 2, 'K_U16_MS': 2}
for k in sorted(set(re.findall(r'\{\d+, (K_\w+), "', chg))):
    if k not in widths: problems.append('RF_Changes.h: a kind this test does not know the width of: ' + k)
    elif widths[k] != (1 if k in ('K_SKIP', 'K_U8', 'K_S8', 'K_STEP', 'K_U8_T10S', 'K_U8_T10P', 'K_S8_GEO') else 4 if k in ('K_U32', 'K_HEX', 'K_BITS') else 0 if k == 'K_TEXT' else 2): problems.append('width of ' + k)
assert all(('case ' + k + ':') in chg for k in widths if widths[k] == 1 and k != 'K_SKIP' or widths[k] == 4), 'ChgKindW must name every 1- and 4-byte kind'
for k in widths:
    if widths[k] == 1 and k != 'K_SKIP' or widths[k] == 4:
        if ('case ' + k + ':') not in chg[chg.index('ChgKindW'):chg.index('ChgKindSigned')]: problems.append('ChgKindW: ' + k + ' is not a 2-byte kind')
ftabs = {m.group(1): [(int(o), k, n) for o, k, n in re.findall(r'\{(\d+), (K_\w+), "([^"]*)"\}', m.group(2))] for m in re.finditer(r'static const ChgF (CF_\d+)\[\] PROGMEM = \{(.*?)\};', chg, re.S)}
lens = {l.split('=', 1)[0].split('.')[0]: len(l.split('=', 1)[1]) // 2 for l in bt2.split('\n') if '=' in l and l[:1].isdigit()}
for fn, first, stride, item, tab in re.findall(r'CT\((\d+), (\d+), (\d+), ("[^"]*"|nullptr), (CF_\d+)\)', chg):
    if fn in ('10', '36'): continue
    cov = {}; f = ftabs[tab]; skips = {o for o, k, n in f if k == 'K_SKIP'}; end = max(o + widths[k] for o, k, n in f)
    for o, k, n in f:
        for b in range(o, o + widths[k]):
            if b in cov: problems.append('%s: byte %d named twice' % (tab, b))
            cov[b] = n
    gaps = [b for b in range(end) if b not in cov and not any(s0 < b <= s0 + 3 for s0 in skips)]
    if gaps: problems.append('%s: bytes %s not named' % (tab, gaps))
    if int(stride) and end != int(stride): problems.append('%s: fields end at %d, the stride is %s' % (tab, end, stride))
    if not int(stride) and fn in lens and lens[fn] != end and not (lens[fn] > end and any(s0 >= end - 4 for s0 in skips)): problems.append('%s: fields end at %d, Rotorflight sends %d' % (tab, end, lens[fn]))
for p in problems: print('WIRING:', p)
print('test_tools (wiring): %d problems' % len(problems))
sys.exit(1 if (rc or problems) else 0)
