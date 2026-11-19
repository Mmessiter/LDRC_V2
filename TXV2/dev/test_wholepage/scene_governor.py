#!/usr/bin/env python3
"""E9: the governor (bank) page's Save. Its payload builder writes 65535 / 255 straight into GovWritePayload for a box with no
answer ("RfFieldsMissed refuses the send" - the lint's reason for allowing it). But the SEND of an earlier press may still be
pending: the bank check (PipeHttp.h BankCheck) runs from the main loop's 50 ms round and the words are put together from
GovWritePayload WHEN THEY GO (Parameters.h 422-442). A second press on Save re-reads the boxes into the same array before
BankCheck says "the same save"; if one of ITS boxes has no answer the save is "refused" - and the first save then sends 255s.
Real: LoadGovWritePayload, SendEditedGovValues, GovQueueWrite (RF_Governor_Profile.h), BankCheck, BankCheckTick,
BankCheckRefuse (PipeHttp.h), RfFieldsMissed, ScreenIsBig (Nextion.h). Stood in for: the pipe's answer (the flight controller
is on the transmitter's bank), Undo's read (a 4 MB screen: none), the read-back."""
import sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
GOVP, PIPE = (m.release(m.src('include/' + f)) for f in ('RF_Governor_Profile.h', 'PipeHttp.h'))
def line(text, head):
    for l in text.split('\n'):
        if l.startswith(head): return l + '\n'
    raise SystemExit('no line ' + head)
REAL = (m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)') + m.lift(m.NEXTION, 'FLASHMEM bool ScreenIsBig()')
        + m.lift(GOVP, 'FLASHMEM void LoadGovWritePayload()') + m.lift(GOVP, 'FLASHMEM static void GovQueueWrite()')
        + line(PIPE, 'static void (*BcThen)() = nullptr;') + line(PIPE, 'static int BcReq = 0, BcStep = 0, BcWant = 0, BcView = -1;') + line(PIPE, 'static uint32_t BcAt = 0;')
        + line(PIPE, 'static uint8_t BcUndoFn = 0;') + line(PIPE, 'static bool BcRates = false;') + line(PIPE, 'static const char *BcPage = "page RFView";')
        + m.lift(PIPE, 'FLASHMEM static void BankCheckRefuse(') + m.lift(PIPE, 'FLASHMEM void BankCheck(') + m.lift(PIPE, 'FLASHMEM static void BankCheckTick()')
        + m.lift(GOVP, 'FLASHMEM void SendEditedGovValues()'))
EXTRA = r'''
uint8_t GovWritePayload[GOV_ACK_PAYLOAD_SIZE] = { 0 }, GovAckPayload[GOV_ACK_PAYLOAD_SIZE] = { 0 }, Saved_GOV_Profiles_Values[GOV_PROFILE_PAYLOAD_SIZE][BANKS_USED];
bool GOV_Loaded = true, GOVS_PROFILE_Were_Edited = true, BlockBankChanges = false, FcBankPending = false; uint8_t PipeState = 2; int PipeRepCode = 200, FcPidBank = 1, FcRateBank = 1;
enum { VK_NONE = 0, VK_GOV = 5 };
static bool RfLive() { return true; } static bool BakOffline() { return false; } static bool UndoPreBusy() { return false; } static uint8_t UndoFnOfView(int) { return 0; }
static bool RfBlockNotLoaded(bool loaded, const char *, const char *) { return !loaded; }
static void SaveToLocalGovBank() {} static bool ModelSeemsArmed(char *, size_t) { return false; } static bool RfPipeBlocked(char *, size_t) { return false; }
static void ShowGOVMsg(const char *, uint16_t) {} static void HideGOVMsg() {} static void GovAskValues() {} static bool RfVerifyArm(uint8_t, void (*)()) { return false; }
static void RfSavedThenLeave(int) {} static bool RfMayFly() { return false; } static void RfSayQuietly(const char *) {} static void RfWordPageSays(int, const char *) {}
static int mspAsked = 0; int MspAsk(uint8_t, const uint8_t *, int) { return ++mspAsked; }
static bool PipeReplyReady(int) { return true; } static bool PipeReplyLate() { return false; } static void FcBankShow() {}
static int PipeReplyBytes(uint8_t *b, int n) { memset(b, 0, (size_t) n); b[23] = (uint8_t) (Bank - 1); b[25] = (uint8_t) (Bank - 1); return 26; }   // (MSP 101: the flight controller is on the transmitter's bank, not armed)
static void UndoPreGo(uint8_t, int, void (*then)(), const char *, int) { then(); }
#define Gray 33840
''' + REAL + r'''
static void my24(int n) { if (n == 210) SendEditedGovValues(); else more24(n); }
static uint8_t wordsSent[18]; static bool sent = false;
static void sendTheWords()   // Parameters.h 422-442: the two words are put together from GovWritePayload WHEN THEY GO
{
    for (int q : queued) if (q == SEND_GOV_WRITE_PROFILE1 || q == SEND_GOV_WRITE_PROFILE2) { memcpy(wordsSent, GovWritePayload, 18); sent = true; }
    queued.clear();
}
static void addGov()
{
    Page g; g.id = 44; static const int v[14] = { 1800, 40, 40, 50, 0, 10, 0, 20, 100, 10, 10, 10, 10, 50 };
    for (int i = 0; i < 14; ++i) { char n[8]; snprintf(n, sizeof n, "n%d", i); g.boxes[n] = { false, v[i], "" }; }
    g.boxes["sw0"] = { false, 0, "" }; g.boxes["busy"] = { true, 0, "" }; g.buttons["Save"] = { 0x00, 210, 0x00, 0x00 }; g.numberBoxes = { "n9box" };
    screen.pages["RFGovView"] = g; screen.pages0 = screen.pages; screen.sys["ldrcmb"] = 4;
    BcStep = 0; sent = false; mspAsked = 0; GOVS_PROFILE_Were_Edited = true; memset(GovWritePayload, 0, sizeof GovWritePayload);
}
static void sayWords(const uint8_t *b) { say("head speed %u, gain %u, P %u, I %u, D %u, F %u, TTA %u/%u, throttle max %u min %u, fallback %u, weights %u %u %u", (unsigned) (b[1] | (b[2] << 8)), b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]); }
'''
SCENES = r'''
    // one press on Save, nothing in the way: what the page holds is what goes
    more(); addGov(); extra24 = my24; BoundFlag = ModelMatched = true; SendCommand((char *) "page RFGovView"); CurrentView = RFGOVERNORVIEW_PROFILE; loopFor(600);
    screen.pages["RFGovView"].boxes["n0"].val = 1900; tapAt(5, "Save"); loopFor(3000); BankCheckTick(); sendTheWords();
    say("E9. one press on Save: sent %d: ", (int) sent); sayWords(wordsSent); say("\n");
    CHECK(sent && (wordsSent[1] | (wordsSent[2] << 8)) == 1900 && wordsSent[3] == 40 && wordsSent[15] == 50);
    // Save, Save again a quarter of a second later, and a touch on a number box as the second press's boxes are read
    more(); addGov(); extra24 = my24; BoundFlag = ModelMatched = true; SendCommand((char *) "page RFGovView"); CurrentView = RFGOVERNORVIEW_PROFILE; loopFor(600);
    screen.pages["RFGovView"].boxes["n0"].val = 1900; tapAt(5, "Save"); tapAt(255, "Save");
    { const uint64_t t0 = nowUs; while (nowUs - t0 < 9000000ull && count(obeyed, 1210) < 2) loopFor(1);        // (the first press's work, the second press taken up)
      say("E9. Save twice: presses obeyed %d, the bank check out %d;", count(obeyed, 1210), BcStep); }
    CHECK(count(obeyed, 1210) == 2);
    BankCheckTick(); sendTheWords();
    say(" with nothing in the way, sent %d: ", (int) sent); sayWords(wordsSent); say("\n");
    CHECK(sent && (wordsSent[1] | (wordsSent[2] << 8)) == 1900 && wordsSent[3] == 40);
    more(); addGov(); extra24 = my24; BoundFlag = ModelMatched = true; SendCommand((char *) "page RFGovView"); CurrentView = RFGOVERNORVIEW_PROFILE; loopFor(600);
    screen.pages["RFGovView"].boxes["n0"].val = 1900; tapAt(5, "Save"); tapAt(255, "Save"); tapAt(1700, "n9box"); tapAt(5000, "yes");
    { const uint64_t t0 = nowUs; while (nowUs - t0 < 12000000ull && count(obeyed, 1210) < 2) loopFor(1);
      say("E9. Save twice, and a number box touched while the second press's boxes are read: presses obeyed %d, keyboards %d, the pilot told %d, the bank check still out %d (%.1f s old);", count(obeyed, 1210), screen.keyboards, boxesLostTold, BcStep, (millis() - BcAt) / 1e3); }
    loopFor(60); BankCheckTick(); sendTheWords();
    say("\n    then the main loop's round: sent %d: ", (int) sent); if (sent) sayWords(wordsSent); say("\n");
    CHECK(!sent || ((wordsSent[1] | (wordsSent[2] << 8)) == 1900 && wordsSent[10] == 100 && wordsSent[15] == 50));   // (what should hold: nothing goes, or what the page holds)
'''
sys.exit(lib.build_run('governor', SCENES, extra=EXTRA, more_defines=('RFGOVERNORVIEW_PROFILE', 'GOV_ACK_PAYLOAD_SIZE', 'GOV_PROFILE_PAYLOAD_SIZE', 'SEND_GOV_WRITE_PROFILE1', 'SEND_GOV_WRITE_PROFILE2', 'BEEPCOMPLETE', 'BEEPMIDDLE'), sanitize=False))
