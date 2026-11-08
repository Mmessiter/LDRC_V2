// B196 (Malcolm, 8 Nov 2026: "Please do all five"): THE DIRECTION CHECK, page 87 (RFDirView, from Guide & checks and the
// guide's first step: 16 MB screens). Is the flight controller the right way round? The pilot moves the model three ways -
// nose down, right side down, nose turned right - and the page watches what the flight controller sees (MSP 108, four
// times a second): roll and pitch in tenths of a degree, the heading in degrees. Rotorflight 4.6's own signs (release/4.6.0):
// pitch is POSITIVE NOSE DOWN (osd_elements.c: "if (attitude.values.pitch > 0) //nose down"), roll positive right side down
// (leveling.c: the error is the stick's angle less the attitude - right stick, right roll), and the heading rises as the
// nose turns right (a compass). Each move is judged once it passes 20 degrees (30 for the turn): the right way, the wrong
// way, or about another axis.
// A board turned round (pitch and roll both backwards, the turn right) is the one fault fixed here: the phone app's two
// mountings (rotorflight-firsttime.html, Malcolm 24 Aug 2026 - connections to the front, yaw 0; to the back, yaw 180),
// offered only when the flight controller has one of them now. Written with 39 (roll 0, pitch 0, yaw), stored, read back,
// and the flight controller restarted (the rotation is built at its start); then the check is run again. Anything else is
// a custom mounting: the configurator's. The board alignment is in the backup, restore and offline editing already (38/39).
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_DIRECTION_H
#define RF_DIRECTION_H

enum { DR_IDLE = 0, DR_STEP, DR_BACK, DR_DONE, DR_FIX_READ, DR_FIX_WRITE, DR_FIX_STORE, DR_FIX_VERIFY, DR_FIX_RESTART, DR_FIX_WAIT };
static int DrState = DR_IDLE, DrStep = 0, DrReq = 0, DrFixReq = 0;   // DrStep: 1 nose down, 2 right side down, 3 turn right
static int DrRoll = 0, DrPitch = 0, DrHead = 0;                       // the last seen (tenths, tenths, degrees)
static int DrRoll0 = 0, DrPitch0 = 0, DrHead0 = 0;                    // at Start (level)
static int8_t DrResult[4] = {0, 0, 0, 0};                             // per move: 0 not yet, 1 right, -1 backwards, -2 another axis
static bool DrSeen = false, DrPending = false;
static uint32_t DrNextAt = 0, DrAskedAt = 0, DrWaitUntil = 0;
static int16_t DrMount[3] = {0, 0, 0};                                // the board alignment as it is (roll, pitch, yaw degrees)
static int DrMountYaw = 0;                                            // the yaw the fix writes
static bool DrMountKnown = false, DrMountOk = false, DrMountPending = false;   // (review, 8 Nov: read as the page opens - the fix's words
static int DrMountReq = 0;                                                     //  and its offer depend on it: at yaw 180 the question said BACK)

FLASHMEM static int DrWrap180(int d) { while (d > 180) d -= 360; while (d < -180) d += 360; return d; }
FLASHMEM static const char *DrMoveWords(int k)
{
    return k == 1 ? "Tilt the nose DOWN" : k == 2 ? "Tilt the RIGHT side down" : "Turn the nose to the RIGHT";
}
FLASHMEM static const char *DrResultWords(int k)
{
    const int r = DrResult[k];
    if (r == 1) return "agrees";
    if (r == 0) return "";
    if (k == 1) return r == -1 ? "it saw the nose go UP" : "it saw a side go down";
    if (k == 2) return r == -1 ? "it saw the LEFT side go down" : "it saw the nose move";
    return "it saw the nose turn LEFT";
}
FLASHMEM static bool DrTurnedRound() { return DrResult[1] == -1 && DrResult[2] == -1 && DrResult[3] == 1; }
FLASHMEM static bool DrAllRight() { return DrResult[1] == 1 && DrResult[2] == 1 && DrResult[3] == 1; }
FLASHMEM static bool DrFixable() // turned round, and the mounting now one of the phone's two (read as the page opened)
{
    return DrState == DR_DONE && DrTurnedRound() && DrMountOk && DrMount[0] == 0 && DrMount[1] == 0 && (DrMount[2] == 0 || DrMount[2] == 180 || DrMount[2] == -180);
}
FLASHMEM static void DrShowLive()
{
    if (CurrentView != DIRVIEW) return;
    char b[90];
    if (!DrSeen) snprintf(b, sizeof(b), "Waiting for the flight controller ...");
    else
    {
        const int p = DrPitch / 10, r = DrRoll / 10;
        snprintf(b, sizeof(b), "Nose %d\xB0 %s   Right side %d\xB0 %s   Heading %d\xB0", abs(p), p >= 0 ? "down" : "up", abs(r), r >= 0 ? "down" : "up", DrHead);
    }
    SendText((char *)"lv", b);
}
FLASHMEM static void DrShow()
{
    if (CurrentView != DIRVIEW) return;
    char b[160];
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)((BoundFlag && ModelMatched) ? "Connected" : "No model"));
    switch (DrState)
    {
    case DR_IDLE: snprintf(b, sizeof(b), "Stand the model level, then press Start."); break;
    case DR_STEP: snprintf(b, sizeof(b), "%d of 3: %s about 30\xB0", DrStep, DrMoveWords(DrStep)); break;
    case DR_BACK: snprintf(b, sizeof(b), "Now stand it level again."); break;
    case DR_DONE: snprintf(b, sizeof(b), DrAllRight() ? "Done: every move seen the right way." : "Done: see below."); break;
    default: snprintf(b, sizeof(b), "Changing the mounting ..."); break;
    }
    SendText((char *)"do", b);
    for (int k = 1; k <= 3; ++k)
    {
        char n[8], c[40], t[80];
        snprintf(t, sizeof(t), "%d. %s%s%s", k, DrMoveWords(k), DrResult[k] ? ": " : "", DrResultWords(k));
        snprintf(n, sizeof(n), "s%d", k); SendText(n, t);
        const uint16_t col = DrResult[k] == 1 ? 2016u : DrResult[k] < 0 ? 63488u : (DrState == DR_STEP && DrStep == k) ? 64512u : 33808u;
        snprintf(c, sizeof(c), "m%d.bco=%u", k, (unsigned)col); SendCommand(c);
    }
    const bool fixable = DrFixable();
    if (DrState != DR_DONE) b[0] = 0;
    else if (DrAllRight()) snprintf(b, sizeof(b), "The flight controller knows which way round it is.");
    else if (fixable) snprintf(b, sizeof(b), "It sees the model turned round: its connections face the %s. Turn it round below (it restarts).", DrMount[2] == 0 ? "back" : "front");
    else if (DrTurnedRound() && !DrMountOk) snprintf(b, sizeof(b), "It sees the model turned round, but its mounting could not be read: press Again to read it once more.");   // (review: not "custom" when it was not read)
    else if (DrTurnedRound()) snprintf(b, sizeof(b), "It sees the model turned round, with a custom mounting set. Set the mounting with the configurator.");
    else snprintf(b, sizeof(b), "It sees some moves wrongly: its mounting is not one of the two here. Set it with the configurator.");
    SendText((char *)"rs", b);
    SendCommand((char *)(fixable ? "vis bT,1" : "vis bT,0"));
    SendText((char *)"bS", (char *)(DrState == DR_IDLE ? "Start" : "Again"));
    DrShowLive();
}
FLASHMEM static void DrJudge() // a new sample, in a move: judged once it is far enough
{
    const int dp = (DrPitch - DrPitch0) / 10, dr = (DrRoll - DrRoll0) / 10, dh = DrWrap180(DrHead - DrHead0);
    if (DrState == DR_BACK)
    {
        if (abs(dp) < 8 && abs(dr) < 8) { ++DrStep; DrState = DR_STEP; DrHead0 = DrHead; DrShow(); }
        return;
    }
    if (DrState != DR_STEP) return;
    int8_t r = 0;
    if (DrStep == 1 && (abs(dp) >= 20 || abs(dr) >= 20)) r = abs(dp) >= abs(dr) ? (dp > 0 ? 1 : -1) : -2;
    if (DrStep == 2 && (abs(dp) >= 20 || abs(dr) >= 20)) r = abs(dr) >= abs(dp) ? (dr > 0 ? 1 : -1) : -2;
    if (DrStep == 3 && abs(dh) >= 30) r = dh > 0 ? 1 : -1;
    if (!r) return;
    DrResult[DrStep] = r;
    PlaySound(r == 1 ? BEEPCOMPLETE : WHAHWHAHMSG);
    if (DrStep < 3) DrState = DR_BACK;
    else DrState = DR_DONE;
    DrShow();
}
FLASHMEM static void DrFixFail(const char *what)
{
    DrState = DR_DONE;
    if (CurrentView != DIRVIEW) { FsBusy(""); return; }   // (left meanwhile: nothing to say it on)
    FsFail("page RFDirView", what);
    DrShow();
}
FLASHMEM static void DirectionPoll()
{
    if (!(BoundFlag && ModelMatched) || PipeState != 2)
    { // the model went: a fix under way stops (what was not stored goes at the flight controller's next start)
        DrPending = false;
        if (DrState >= DR_FIX_READ && DrState <= DR_FIX_RESTART) { DrState = DR_DONE; FsBusy(""); if (CurrentView == DIRVIEW) DrShow(); }
        return;
    }
    // the mounting fix: its own requests, one at a time - carried through to the end whatever the screen shows (dark, a box)
    if (DrState >= DR_FIX_READ && DrState <= DR_FIX_RESTART)
    {
        if (!DrFixReq)
        { // (the fix's first request goes when the pipe is free: the live read in flight is let finish)
            if (!RfPipeFree()) return;
            DrFixReq = MspAsk(38, nullptr, 0);
            return;
        }
        if (!PipeReplyReady(DrFixReq))
        {
            if (PipeReplyLate()) DrFixFail("No answer");
            return;
        }
        const bool ok = PipeRepCode == 200;
        switch (DrState)
        {
        case DR_FIX_READ:
        {
            uint8_t b[8];
            if (!ok || PipeReplyBytes(b, sizeof(b)) < 6) { DrFixFail("The mounting could not be read"); return; }
            const int r = RdS16(b, 0), pt = RdS16(b, 2), y = RdS16(b, 4);
            if (r != DrMount[0] || pt != DrMount[1] || y != DrMount[2]) { DrMountKnown = DrMountOk = false; DrFixFail("The mounting changed meanwhile:\r\ncheck it again"); return; }   // (not what the question said; read afresh before the next try)
            if (r != 0 || pt != 0 || !(y == 0 || y == 180 || y == -180)) { DrFixFail("The mounting is a custom one: set it\r\nwith the configurator"); return; }
            DrMountYaw = y == 0 ? 180 : 0;
            uint8_t w[6] = {0, 0, 0, 0, (uint8_t)(DrMountYaw & 0xFF), (uint8_t)((DrMountYaw >> 8) & 0xFF)};
            DrFixReq = MspAsk(39, w, 6); DrState = DR_FIX_WRITE;
            return;
        }
        case DR_FIX_WRITE:
            if (!ok) { DrFixFail("Not written (the mounting)"); return; }
            DrFixReq = MspAsk(250, nullptr, 0); DrState = DR_FIX_STORE;
            return;
        case DR_FIX_STORE:
            if (!ok) { DrFixFail("Not stored"); return; }
            DrFixReq = MspAsk(38, nullptr, 0); DrState = DR_FIX_VERIFY;
            return;
        case DR_FIX_VERIFY:
        {
            uint8_t b[8];
            if (!ok || PipeReplyBytes(b, sizeof(b)) < 6 || RdS16(b, 0) != 0 || RdS16(b, 2) != 0 || RdS16(b, 4) != DrMountYaw) { DrFixFail("Read back different: not changed"); return; }
            DrMount[2] = (int16_t)DrMountYaw;
            DrFixReq = MspAsk(68, nullptr, 0); DrState = DR_FIX_RESTART;
            FsBusy("Restarting the flight controller ...");
            return;
        }
        case DR_FIX_RESTART:
            DrState = DR_FIX_WAIT; DrWaitUntil = millis() + 5000;
            return;
        default: return;
        }
    }
    if (DrState == DR_FIX_WAIT)
    {
        if ((int32_t)(millis() - DrWaitUntil) < 0) return;
        DrState = DR_IDLE; DrStep = 0; DrSeen = false;
        for (int k = 0; k < 4; ++k) DrResult[k] = 0;
        if (CurrentView != DIRVIEW) return;   // (left meanwhile: done all the same)
        FsBusy("");
        PlaySound(BEEPCOMPLETE);
        RfBoxOrQuiet("page RFDirView", "Turned round, and restarted.\r\nNow check it again: stand it level,\r\nthen Start.");
        DrShow();
        return;
    }
    if (CurrentView != DIRVIEW) { DrPending = false; return; }   // (the live level only while the page shows)
    if (!DrMountKnown)
    { // the mounting as it is, once a visit, before the live level
        if (DrMountPending)
        {
            if (PipeReplyReady(DrMountReq))
            {
                uint8_t b[8];
                DrMountPending = false; DrMountKnown = true;
                DrMountOk = PipeRepCode == 200 && PipeReplyBytes(b, sizeof(b)) >= 6;
                if (DrMountOk) { DrMount[0] = (int16_t)RdS16(b, 0); DrMount[1] = (int16_t)RdS16(b, 2); DrMount[2] = (int16_t)RdS16(b, 4); }
                DrShow();
            }
            else if ((uint32_t)(millis() - DrAskedAt) > 2000) { DrMountPending = false; DrMountKnown = true; DrMountOk = false; }
            return;
        }
        if (!RfPipeFree()) return;
        DrMountReq = MspAsk(38, nullptr, 0); DrAskedAt = millis(); DrMountPending = true;
        return;
    }
    // the live level, four times a second
    if (DrPending)
    {
        if (PipeReplyReady(DrReq))
        {
            DrPending = false; DrNextAt = millis() + 250;
            uint8_t b[8];
            if (PipeRepCode == 200 && PipeReplyBytes(b, sizeof(b)) >= 6)
            {
                DrRoll = RdS16(b, 0); DrPitch = RdS16(b, 2); DrHead = RdS16(b, 4);
                DrSeen = true;
                DrJudge();
                DrShowLive();
            }
        }
        else if ((uint32_t)(millis() - DrAskedAt) > 2000) { DrPending = false; DrNextAt = millis() + 250; }
        return;
    }
    if ((int32_t)(millis() - DrNextAt) < 0) return;
    if (!RfPipeFree()) return;   // (another request is out: not one on top of it)
    DrReq = MspAsk(108, nullptr, 0); DrAskedAt = millis(); DrPending = true;
}
// ---- the page
FLASHMEM static void DrReset()
{
    DrState = DR_IDLE; DrStep = 0; DrPending = false; DrSeen = false; DrNextAt = 0;
    for (int k = 0; k < 4; ++k) DrResult[k] = 0;
    DrMount[0] = DrMount[1] = DrMount[2] = 0;
    DrMountKnown = DrMountOk = DrMountPending = false;
}
FLASHMEM void DirStart() // from Guide & checks, the guide's first step, or a check's row
{
    if (BakJob != BAK_JOB_NONE) return;
    if (!CkModelThere(CurrentView == GUIDEVIEW ? "page RFGuideView" : CurrentView == CHECKVIEW ? "page RFCheckView" : "page RFToolsView")) { RfToolsRedraw(); return; }
    UndoNewVisit();
    SendCommand((char *)"page RFDirView");
    CurrentView = DIRVIEW;
    DrReset();
    DrShow();
}
FLASHMEM void DirStartTapped() // 248: Start / Again
{
    if (DrState >= DR_FIX_READ) return;
    if (!DrSeen) { MsgBox((char *)"page RFDirView", (char *)"The flight controller has not said how\r\nit is tilted yet: wait a moment."); DrShow(); return; }
    for (int k = 0; k < 4; ++k) DrResult[k] = 0;
    if (DrMountKnown && !DrMountOk) DrMountKnown = false;   // (review: a mounting that could not be read is read again with each Again)
    DrRoll0 = DrRoll; DrPitch0 = DrPitch; DrHead0 = DrHead;
    if (abs(DrRoll0) > 300 || abs(DrPitch0) > 300)
    { // (30 degrees: it is not standing level - or its mounting is far out; said, and the moves are judged from here all the same)
        MsgBox((char *)"page RFDirView", (char *)"It does not stand level as the flight\r\ncontroller sees it. If it IS level, its\r\nmounting is wrong: go on, the moves say how.");
    }
    DrStep = 1; DrState = DR_STEP;
    DrShow();
}
FLASHMEM void DirTurnTapped() // 249: Turn it round - the other of the two mountings
{
    if (!DrFixable()) return;
    if (FsRefused("page RFDirView", true)) { DrShow(); return; }
    char q[200];
    snprintf(q, sizeof(q), "Set the mounting to connections at the\r\n%s (yaw %d), and restart the flight\r\ncontroller?", DrMount[2] == 0 ? "BACK" : "FRONT", DrMount[2] == 0 ? 180 : 0);
    if (!GetConfirmation((char *)"page RFDirView", q)) { DrShow(); return; }
    DrShow();
    DrPending = false;
    DrFixReq = 0; DrState = DR_FIX_READ;   // (asked from the poll, when the pipe is free)
    FsBusy("Changing the mounting ...");
}
FLASHMEM void EndDirView() // 250: OK
{
    if (DrState >= DR_FIX_READ && DrState != DR_FIX_WAIT) return;   // (the fix is being written: wait for it)
    FsBusy("");
    DrState = DR_IDLE; DrPending = false;
    RfBackHome();
}
#endif // RF_DIRECTION_H
