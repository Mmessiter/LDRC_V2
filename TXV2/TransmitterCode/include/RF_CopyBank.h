// B78: COPY A BANK on the transmitter, over the Bluetooth pipe: the flight tuning (PIDs, PID+, rescue), the rates and the
// governor gains of one bank into another, as the receiver's own page does it (RXV2 data/rotorflight-copybank.html),
// step for step: Rotorflight's own copy (MSP 183: type 0 the PID profile, 1 the rate profile; destination, source), the
// governor profile put right afterwards (the copy brings the source's governor along: the target keeps its own HEAD
// SPEED unless asked, and its whole governor if the gains are not wanted), the store (250), and the target read back and
// compared byte for byte. Malcolm's head-speed adjustment (5 Sep 2026: "tune bank 2 first, copy it to 1 and 3, and let
// the firmware make intelligent reductions / increases for the head speed"): control power grows with head speed
// squared, so the copied P, I, D, F and B gains are scaled by (source rpm / target rpm)^1.5 going faster, by the plain
// ratio capped at +25 % going slower - the receiver page's rule, byte for byte. The transmitter's bank switch is held
// (BlockBankChanges) while the flight controller's banks are walked, and the transmitter's own banks are put back at the end.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_COPYBANK_H
#define RF_COPYBANK_H

static int CbFrom = 0, CbTo = 1;                       // banks, 0-based
static int CbPidBanks = 6, CbRateBanks = 6;
static bool CbFlight = true, CbRates = true, CbGov = true, CbHs = false, CbAdj = false;
enum { CB_IDLE = 0, CB_STATUS, CB_SEL_SRC, CB_SRC_PID, CB_SRC_ADV, CB_SRC_RESC, CB_SRC_GOV, CB_SEL_SRC_R, CB_SRC_RATES, CB_SEL_DST, CB_DST_GOV,
       CB_COPY_PID, CB_SEL_DST2, CB_PUT_GOV, CB_COPY_RATES, CB_SEL_DST3, CB_ADJ_READ, CB_ADJ_WRITE, CB_STORE,
       CB_V_SEL, CB_V_PID, CB_V_ADV, CB_V_RESC, CB_V_GOV, CB_V_SEL_R, CB_V_RATES, CB_BACK_P, CB_BACK_R, CB_DONE };
static int CbStep = CB_IDLE, CbReq = 0, CbTries = 0;
DMAMEM static uint8_t CbSrcPid[40], CbSrcAdv[64], CbSrcResc[40], CbSrcGov[32], CbSrcRates[48], CbDstGov[32], CbExpGov[32], CbExpPid[40];
static int CbSrcPidN = 0, CbSrcAdvN = 0, CbSrcRescN = 0, CbSrcGovN = 0, CbSrcRatesN = 0, CbDstGovN = 0, CbExpGovN = 0, CbExpPidN = 0;
static char CbBad[80], CbAdjText[110];
static int CbHsSrc = 0, CbHsDst = 0;
static bool CbTouchGov() { return CbFlight || CbGov; }

FLASHMEM static void CbBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg) SendText((char *)"busy", (char *)msg);
}
FLASHMEM static void CbShow()
{
    char b[24];
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"Bluetooth");
    snprintf(b, sizeof(b), "Bank %d", CbFrom + 1); SendText((char *)"tn0", b);
    snprintf(b, sizeof(b), "Bank %d", CbTo + 1); SendText((char *)"tn1", b);
    SendValue((char *)"tn2", CbFlight ? 1 : 0); SendValue((char *)"tn3", CbRates ? 1 : 0); SendValue((char *)"tn4", CbGov ? 1 : 0);
    SendValue((char *)"tn5", CbHs ? 1 : 0); SendValue((char *)"tn6", CbAdj ? 1 : 0);
    char w[90];
    snprintf(w, sizeof(w), "Copy bank %d to bank %d", CbFrom + 1, CbTo + 1);
    SendText((char *)"b3", w);
}
FLASHMEM static void CbEnd(bool ok)
{
    CbStep = CB_IDLE;
    BlockBankChanges = false;
    CbBusy("");
    (void)ok;
}
FLASHMEM static void CbFail(const char *what)
{
    char msg[200];
    snprintf(msg, sizeof(msg), "%s:\r\n%.100s\r\nThe flight controller was left as it was,\r\nor part copied: check bank %d.", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)", CbTo + 1);
    CbEnd(false);
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)"page CopyBankView", msg);
    CbShow();
}
FLASHMEM static int CbBytes(uint8_t *out, int max) { return PipeReplyBytes(out, max); }
FLASHMEM static bool CbSameBytes(const uint8_t *a, int na, const uint8_t *b, int nb) { return na == nb && memcmp(a, b, (size_t)na) == 0; }
static uint8_t CbLastFn = 0, CbLastData[64]; static int CbLastLen = 0;   // the request in flight, for one more go when the receiver was busy
FLASHMEM static void CbAsk(uint8_t fn, const uint8_t *data, int len, int next)
{
    CbLastFn = fn; CbLastLen = len > (int)sizeof(CbLastData) ? (int)sizeof(CbLastData) : len;
    if (data && CbLastLen > 0) memcpy(CbLastData, data, (size_t)CbLastLen);
    CbReq = MspAsk(fn, data, len); CbStep = next; CbTries = 0;
}
FLASHMEM static void CbSelect(int bank, bool rates, int next)
{
    uint8_t d = (uint8_t)((rates ? 0x80 : 0) | (bank & 0x7F));
    CbAsk(210, &d, 1, next);
}
// Malcolm's rule for the copied gains against the two head speeds (the receiver page's hsScale / hsScaleWords)
FLASHMEM static float CbHsFactor(int hsS, int hsD, int &pct)
{
    pct = 0;
    if (hsS <= 0 || hsD <= 0) return 1.0f;
    const float r = (float)hsS / (float)hsD;
    float f = r < 1.0f ? powf(r, 1.5f) : (r < 1.25f ? r : 1.25f);
    pct = (int)floorf((f - 1.0f) * 100.0f + 0.5f);
    return f;
}
FLASHMEM static void CbScalePids(uint8_t *img, int n, float f)
{
    for (int i = 0; i < 15 && (i + 1) * 2 <= n; ++i)
    { // 0..11 P, I, D, F x 3 axes, 12..14 B; 15, 16 (O) untouched
        long v = (long)(img[i * 2] | (img[i * 2 + 1] << 8));
        v = (long)floorf((float)v * f + 0.5f);
        if (v < 0) v = 0;
        if (v > 1000) v = 1000;
        img[i * 2] = (uint8_t)v; img[i * 2 + 1] = (uint8_t)(v >> 8);
    }
}
FLASHMEM static void CbAfterSource() // the source read: on to the target's governor, or the copy
{
    if (CbTouchGov()) { CbSelect(CbTo, false, CB_SEL_DST); return; }
    CbStep = CB_SEL_DST2; // (no governor to put right: straight to the copy)
    uint8_t d[3] = {0, (uint8_t)CbTo, (uint8_t)CbFrom};
    CbBusy("Copying ...");
    if (CbFlight) { CbAsk(183, d, 3, CB_COPY_PID); return; }
    if (CbRates) { uint8_t r[3] = {1, (uint8_t)CbTo, (uint8_t)CbFrom}; CbAsk(183, r, 3, CB_COPY_RATES); return; }
    CbAsk(250, nullptr, 0, CB_STORE);
}
FLASHMEM void CopyBankPoll()
{
    if (CurrentView != COPYBANKVIEW) { if (CbStep != CB_IDLE) CbEnd(false); return; }
    if (CbStep == CB_IDLE) return;
    if (!PipeReplyReady(CbReq))
    {
        if (!PipeReplyLate()) return;
        CbFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    if ((PipeRepCode == 503 || PipeRepCode == 504) && CbTries < 5)
    { // the receiver was busy with the transmitter's own traffic: the same request once more
        ++CbTries;
        CbReq = MspAsk(CbLastFn, CbLastLen ? CbLastData : nullptr, CbLastLen);
        return;
    }
    switch (CbStep)
    {
    case CB_STATUS:
    {
        uint8_t b[40];
        const int n = ok ? CbBytes(b, sizeof(b)) : 0;
        if (n < 26) { CbFail("Could not read where the flight controller is"); return; }
        if (n > 26) { CbPidBanks = b[24] >= 1 && b[24] <= 6 ? b[24] : 6; CbRateBanks = b[26] >= 1 && b[26] <= 6 ? b[26] : 6; }
        char m[48]; snprintf(m, sizeof(m), "Reading bank %d ...", CbFrom + 1); CbBusy(m);
        CbSelect(CbFrom, false, CB_SEL_SRC);
        return;
    }
    case CB_SEL_SRC:
        if (!ok) { CbFail("Could not select the source bank"); return; }
        if (CbFlight) { CbAsk(112, nullptr, 0, CB_SRC_PID); return; }
        if (CbTouchGov()) { CbAsk(148, nullptr, 0, CB_SRC_GOV); return; }
        if (CbRates) { CbSelect(CbFrom, true, CB_SEL_SRC_R); return; }
        CbAfterSource();
        return;
    case CB_SRC_PID:
        if (!ok || (CbSrcPidN = CbBytes(CbSrcPid, sizeof(CbSrcPid))) < 34) { CbFail("Could not read the source PIDs"); return; }
        CbAsk(94, nullptr, 0, CB_SRC_ADV);
        return;
    case CB_SRC_ADV:
        if (!ok || (CbSrcAdvN = CbBytes(CbSrcAdv, sizeof(CbSrcAdv))) < 10) { CbFail("Could not read the source PID+"); return; }
        CbAsk(146, nullptr, 0, CB_SRC_RESC);
        return;
    case CB_SRC_RESC:
        if (!ok || (CbSrcRescN = CbBytes(CbSrcResc, sizeof(CbSrcResc))) < 10) { CbFail("Could not read the source rescue"); return; }
        if (CbTouchGov()) { CbAsk(148, nullptr, 0, CB_SRC_GOV); return; }
        if (CbRates) { CbSelect(CbFrom, true, CB_SEL_SRC_R); return; }
        CbAfterSource();
        return;
    case CB_SRC_GOV:
        if (!ok || (CbSrcGovN = CbBytes(CbSrcGov, sizeof(CbSrcGov))) < 17) { CbFail("Could not read the source governor"); return; }
        CbHsSrc = CbSrcGov[0] | (CbSrcGov[1] << 8);
        if (CbRates) { CbSelect(CbFrom, true, CB_SEL_SRC_R); return; }
        CbAfterSource();
        return;
    case CB_SEL_SRC_R:
        if (!ok) { CbFail("Could not select the source rates bank"); return; }
        CbAsk(111, nullptr, 0, CB_SRC_RATES);
        return;
    case CB_SRC_RATES:
        if (!ok || (CbSrcRatesN = CbBytes(CbSrcRates, sizeof(CbSrcRates))) < 25) { CbFail("Could not read the source rates"); return; }
        CbAfterSource();
        return;
    case CB_SEL_DST:
        if (!ok) { CbFail("Could not select the target bank"); return; }
        CbAsk(148, nullptr, 0, CB_DST_GOV);
        return;
    case CB_DST_GOV:
    {
        if (!ok || (CbDstGovN = CbBytes(CbDstGov, sizeof(CbDstGov))) < 17) { CbFail("Could not read the target governor"); return; }
        // what the target's governor is to be: the source's (its own head speed kept unless asked), or its own
        if (CbGov) { memcpy(CbExpGov, CbSrcGov, (size_t)CbSrcGovN); CbExpGovN = CbSrcGovN; if (!CbHs) { CbExpGov[0] = CbDstGov[0]; CbExpGov[1] = CbDstGov[1]; } }
        else { memcpy(CbExpGov, CbDstGov, (size_t)CbDstGovN); CbExpGovN = CbDstGovN; }
        CbHsDst = CbExpGov[0] | (CbExpGov[1] << 8);
        char m[48]; snprintf(m, sizeof(m), "Copying to bank %d ...", CbTo + 1); CbBusy(m);
        if (CbFlight) { uint8_t d[3] = {0, (uint8_t)CbTo, (uint8_t)CbFrom}; CbAsk(183, d, 3, CB_COPY_PID); return; }
        CbSelect(CbTo, false, CB_SEL_DST2);
        return;
    }
    case CB_COPY_PID:
        if (!ok) { CbFail("The flight tuning was not copied"); return; }
        if (CbTouchGov()) { CbSelect(CbTo, false, CB_SEL_DST2); return; }
        if (CbRates) { uint8_t r[3] = {1, (uint8_t)CbTo, (uint8_t)CbFrom}; CbAsk(183, r, 3, CB_COPY_RATES); return; }
        CbAsk(250, nullptr, 0, CB_STORE);
        return;
    case CB_SEL_DST2:
        if (!ok) { CbFail("Could not select the target bank"); return; }
        CbAsk(149, CbExpGov, CbExpGovN, CB_PUT_GOV);
        return;
    case CB_PUT_GOV:
        if (!ok) { CbFail("The target's governor was not written"); return; }
        if (CbRates) { uint8_t r[3] = {1, (uint8_t)CbTo, (uint8_t)CbFrom}; CbAsk(183, r, 3, CB_COPY_RATES); return; }
        if (CbAdj && CbFlight) { CbSelect(CbTo, false, CB_SEL_DST3); return; }
        CbAsk(250, nullptr, 0, CB_STORE);
        return;
    case CB_COPY_RATES:
        if (!ok) { CbFail("The rates were not copied"); return; }
        if (CbAdj && CbFlight) { CbSelect(CbTo, false, CB_SEL_DST3); return; }
        CbAsk(250, nullptr, 0, CB_STORE);
        return;
    case CB_SEL_DST3:
        if (!ok) { CbFail("Could not select the target bank"); return; }
        CbAsk(112, nullptr, 0, CB_ADJ_READ);
        return;
    case CB_ADJ_READ:
    {
        if (!ok || (CbExpPidN = CbBytes(CbExpPid, sizeof(CbExpPid))) < 34) { CbFail("Could not read the copied PIDs"); return; }
        int pct = 0;
        const float f = CbHsFactor(CbHsSrc, CbHsDst, pct);
        if (CbHsSrc <= 0 || CbHsDst <= 0) { snprintf(CbAdjText, sizeof(CbAdjText), "A bank has no head speed set: gains copied as they were."); CbAsk(250, nullptr, 0, CB_STORE); return; }
        if (pct == 0) { snprintf(CbAdjText, sizeof(CbAdjText), "Both banks run %d rpm: gains unchanged.", CbHsSrc); CbAsk(250, nullptr, 0, CB_STORE); return; }
        CbScalePids(CbExpPid, CbExpPidN, f);
        snprintf(CbAdjText, sizeof(CbAdjText), "Gains %s %d %% for bank %d's %s head speed (%d to %d rpm).", pct >= 0 ? "up" : "down", pct < 0 ? -pct : pct, CbTo + 1, CbHsDst > CbHsSrc ? "faster" : "slower", CbHsSrc, CbHsDst);
        CbBusy("Adjusting the gains for the head speed ...");
        CbAsk(202, CbExpPid, CbExpPidN, CB_ADJ_WRITE);
        return;
    }
    case CB_ADJ_WRITE:
        if (!ok) { CbFail("The adjusted PIDs were not written"); return; }
        CbAsk(250, nullptr, 0, CB_STORE);
        return;
    case CB_STORE:
        if (!ok) { CbFail("Not stored"); return; }
        CbBusy("Reading the target back ...");
        CbBad[0] = 0;
        CbSelect(CbTo, false, CB_V_SEL);
        return;
    case CB_V_SEL:
        if (!ok) { CbFail("Could not read back"); return; }
        if (CbFlight) { CbAsk(112, nullptr, 0, CB_V_PID); return; }
        if (CbTouchGov()) { CbAsk(148, nullptr, 0, CB_V_GOV); return; }
        if (CbRates) { CbSelect(CbTo, true, CB_V_SEL_R); return; }
        CbSelect(Bank > 0 ? Bank - 1 : 0, false, CB_BACK_P);
        return;
    case CB_V_PID:
    {
        uint8_t b[40]; const int n = ok ? CbBytes(b, sizeof(b)) : 0;
        const uint8_t *exp = (CbAdj && CbExpPidN) ? CbExpPid : CbSrcPid; const int expN = (CbAdj && CbExpPidN) ? CbExpPidN : CbSrcPidN;
        if (!CbSameBytes(b, n, exp, expN)) strncat(CbBad, "PIDs ", sizeof(CbBad) - strlen(CbBad) - 1);
        CbAsk(94, nullptr, 0, CB_V_ADV);
        return;
    }
    case CB_V_ADV:
    {
        uint8_t b[64]; const int n = ok ? CbBytes(b, sizeof(b)) : 0;
        if (!CbSameBytes(b, n, CbSrcAdv, CbSrcAdvN)) strncat(CbBad, "PID+ ", sizeof(CbBad) - strlen(CbBad) - 1);
        CbAsk(146, nullptr, 0, CB_V_RESC);
        return;
    }
    case CB_V_RESC:
    {
        uint8_t b[40]; const int n = ok ? CbBytes(b, sizeof(b)) : 0;
        if (!CbSameBytes(b, n, CbSrcResc, CbSrcRescN)) strncat(CbBad, "rescue ", sizeof(CbBad) - strlen(CbBad) - 1);
        if (CbTouchGov()) { CbAsk(148, nullptr, 0, CB_V_GOV); return; }
        if (CbRates) { CbSelect(CbTo, true, CB_V_SEL_R); return; }
        CbSelect(Bank > 0 ? Bank - 1 : 0, false, CB_BACK_P);
        return;
    }
    case CB_V_GOV:
    {
        uint8_t b[32]; const int n = ok ? CbBytes(b, sizeof(b)) : 0;
        if (n < 17 || memcmp(b, CbExpGov, 17) != 0) strncat(CbBad, "governor ", sizeof(CbBad) - strlen(CbBad) - 1);
        if (CbRates) { CbSelect(CbTo, true, CB_V_SEL_R); return; }
        CbSelect(Bank > 0 ? Bank - 1 : 0, false, CB_BACK_P);
        return;
    }
    case CB_V_SEL_R:
        if (!ok) { CbFail("Could not read the rates back"); return; }
        CbAsk(111, nullptr, 0, CB_V_RATES);
        return;
    case CB_V_RATES:
    {
        uint8_t b[48]; const int n = ok ? CbBytes(b, sizeof(b)) : 0;
        if (!CbSameBytes(b, n, CbSrcRates, CbSrcRatesN)) strncat(CbBad, "rates ", sizeof(CbBad) - strlen(CbBad) - 1);
        CbSelect(Bank > 0 ? Bank - 1 : 0, false, CB_BACK_P);
        return;
    }
    case CB_BACK_P:
        CbSelect(DualRateInUse > 0 ? DualRateInUse - 1 : 0, true, CB_BACK_R);   // (the transmitter's own banks back, whatever the answer)
        return;
    case CB_BACK_R:
    {
        char msg[300], what[120] = "";
        if (CbFlight) strncat(what, "flight tuning", sizeof(what) - strlen(what) - 1);
        if (CbRates) { if (what[0]) strncat(what, ", ", sizeof(what) - strlen(what) - 1); strncat(what, "rates", sizeof(what) - strlen(what) - 1); }
        if (CbGov) { if (what[0]) strncat(what, ", ", sizeof(what) - strlen(what) - 1); strncat(what, CbHs ? "governor incl. head speed" : "governor gains (head speed kept)", sizeof(what) - strlen(what) - 1); }
        if (CbBad[0]) snprintf(msg, sizeof(msg), "Copied bank %d to bank %d (%s),\r\nbut read back DIFFERENT: %s\r\nCheck bank %d.", CbFrom + 1, CbTo + 1, what, CbBad, CbTo + 1);
        else snprintf(msg, sizeof(msg), "Copied bank %d to bank %d: %s.\r\nRead back the same.%s%s", CbFrom + 1, CbTo + 1, what, CbAdjText[0] ? "\r\n" : "", CbAdjText);
        CbEnd(!CbBad[0]);
        PlaySound(CbBad[0] ? WHAHWHAHMSG : BEEPCOMPLETE);
        MsgBox((char *)"page CopyBankView", msg);
        CbShow();
        return;
    }
    default:
        CbEnd(false);
        return;
    }
}
FLASHMEM void StartCopyBankView() // the menu's Copy a bank ...
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    { // (B78: with no model but the backup on the card, the copy is made within the backup, and written to the model as edits)
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page CopyBankView");
    CurrentView = COPYBANKVIEW;
    CbStep = CB_IDLE;
    CbFrom = Bank > 0 && Bank <= 6 ? Bank - 1 : 0;
    CbTo = CbFrom == 0 ? 1 : 0;
    CbShow();
}
FLASHMEM void EndCopyBankView() { if (CbStep != CB_IDLE) return; RotorFlightStart(); }
FLASHMEM void CopyBankFromTapped() { if (CbStep != CB_IDLE) return; CbFrom = (CbFrom + 1) % CbPidBanks; if (CbTo == CbFrom) CbTo = (CbTo + 1) % CbPidBanks; CbShow(); }
FLASHMEM void CopyBankToTapped() { if (CbStep != CB_IDLE) return; CbTo = (CbTo + 1) % CbPidBanks; if (CbTo == CbFrom) CbTo = (CbTo + 1) % CbPidBanks; CbShow(); }
FLASHMEM void CopyBankFlightTapped() { if (CbStep != CB_IDLE) return; CbFlight = !CbFlight; CbShow(); }
FLASHMEM void CopyBankRatesTapped() { if (CbStep != CB_IDLE) return; CbRates = !CbRates; CbShow(); }
FLASHMEM void CopyBankGovTapped() { if (CbStep != CB_IDLE) return; CbGov = !CbGov; if (!CbGov) CbHs = false; CbShow(); }
FLASHMEM void CopyBankHsTapped() { if (CbStep != CB_IDLE) return; CbHs = !CbHs; if (CbHs) CbGov = true; CbShow(); }
FLASHMEM void CopyBankAdjTapped() { if (CbStep != CB_IDLE) return; CbAdj = !CbAdj; CbShow(); }
FLASHMEM void CopyBankNow()
{
    if (CbStep != CB_IDLE) return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page CopyBankView", why); CbShow(); return; }
    if (!CbFlight && !CbRates && !CbGov) { MsgBox((char *)"page CopyBankView", (char *)"Switch on at least one thing to copy."); CbShow(); return; }
    if (CbTo == CbFrom) { MsgBox((char *)"page CopyBankView", (char *)"The two banks are the same."); CbShow(); return; }
    char q[200];
    snprintf(q, sizeof(q), "Copy bank %d to bank %d?\r\nBank %d's own values for what is\r\nswitched on are overwritten.", CbFrom + 1, CbTo + 1, CbTo + 1);
    if (!GetConfirmation((char *)"page CopyBankView", q)) { CbShow(); return; }
    CbShow();
    CbBad[0] = 0; CbAdjText[0] = 0; CbExpPidN = 0; CbExpGovN = 0; CbHsSrc = CbHsDst = 0;
    BlockBankChanges = true;
    CbBusy("Reading where the flight controller is ...");
    CbAsk(101, nullptr, 0, CB_STATUS);
}
#endif
