// B55: Rotorflight's servos, on the transmitter (page ServoView on the screen's card, hmi/servo_pages.py), one servo at
// a time, as the receiver's own servos page reads them (RXV2 data/rotorflight-servos.html): MSP 120 gives a count and
// sixteen bytes a servo - centre, min, max, scale negative, scale positive, rate, speed, flags (bit 0 reverse, bit 1
// geometry correction) - MSP 212 sets one (its index and the sixteen bytes), 250 stores, 120 again checks. The
// transmitter asks through the screen's Bluetooth pipe (PipeHttp.h) and does the thinking here.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_SERVOS_H
#define RF_SERVOS_H

static const int SERVO_BYTES = 16, SERVOS_MAX = 8;
static uint8_t ServoRaw[1 + SERVOS_MAX * SERVO_BYTES];  // as last read: count, then the servos
static int ServoCount = 0, ServoAt = 0;                 // how many, and which one the page shows (0-based)
static bool ServoHave = false, Servo_Was_Edited = false;
static int ServoRev = 0, ServoGeo = 0;                  // the two choices of the servo shown
enum { SRV_IDLE = 0, SRV_READ, SRV_WRITE, SRV_STORE, SRV_VERIFY };
static int ServoStep = SRV_IDLE, ServoReq = 0;
static uint8_t ServoWant[SERVO_BYTES];
static bool ServoReadAgainWanted = false;
static uint32_t ServoMsgUntil = 0;

static uint8_t *ServoBytes(int i) { return ServoRaw + 1 + i * SERVO_BYTES; }
static int RdS16(const uint8_t *b, int o) { const int v = b[o] | (b[o + 1] << 8); return v > 32767 ? v - 65536 : v; }
static void ServoBusy(const char *msg)
{
    SendCommand((char *)(msg && *msg ? "vis busy,1" : "vis busy,0"));
    if (msg && *msg)
        SendText((char *)"busy", (char *)msg);
}
static void ServoTitle()
{
    char b[40];
    snprintf(b, sizeof(b), "Servo %d of %d (Rotorflight)", ServoAt + 1, ServoCount > 0 ? ServoCount : 1);
    SendText((char *)"t0", b);
}
static void ServoNum(const char *name, long v)
{
    char b[16];
    snprintf(b, sizeof(b), "%ld", v);
    SendText((char *)name, b);
}
static void ServoShow()
{
    if (!ServoHave || ServoCount < 1)
        return;
    if (ServoAt >= ServoCount)
        ServoAt = ServoCount - 1;
    const uint8_t *b = ServoBytes(ServoAt);
    ServoTitle();
    ServoNum("tn0", RdU16(b, 0));
    ServoNum("tn1", RdS16(b, 2));
    ServoNum("tn2", RdS16(b, 4));
    ServoNum("tn3", RdU16(b, 6));
    ServoNum("tn4", RdU16(b, 8));
    ServoNum("tn5", RdU16(b, 10));
    ServoNum("tn6", RdU16(b, 12));
    const int flags = RdU16(b, 14);
    ServoRev = (flags & 1) ? 1 : 0;
    ServoGeo = (flags & 2) ? 1 : 0;
    SendValue((char *)"tn7", ServoRev ? 1 : 0);   // (B65: a switch)
    SendValue((char *)"tn8", ServoGeo ? 1 : 0);   // (B65: a switch)
}
static void ServoGather() // the page's fields, clamped as the receiver's page clamps them
{
    const uint8_t *was = ServoBytes(ServoAt);
    memcpy(ServoWant, was, SERVO_BYTES);
    WrU16(ServoWant, 0, FieldNumber("tn0", 750, 2250));
    WrU16(ServoWant, 2, FieldNumber("tn1", -1000, 0) & 0xFFFF);
    WrU16(ServoWant, 4, FieldNumber("tn2", 0, 1000));
    WrU16(ServoWant, 6, FieldNumber("tn3", 50, 1000));
    WrU16(ServoWant, 8, FieldNumber("tn4", 50, 1000));
    WrU16(ServoWant, 10, FieldNumber("tn5", 25, 5000));
    WrU16(ServoWant, 12, FieldNumber("tn6", 0, 60000));
    WrU16(ServoWant, 14, (ServoRev ? 1 : 0) | (ServoGeo ? 2 : 0));
}
static void ServoFail(const char *what)
{
    char msg[180];
    snprintf(msg, sizeof(msg), "%s:\r\n%.140s", what, PipeRepCode ? PipeRepBody : "the screen could not ask (no Bluetooth)");
    ServoStep = SRV_IDLE;
    ServoBusy("");
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)"page ServoView", msg);
    SendText((char *)"t11", ModelName);
    SendCommand((char *)(Servo_Was_Edited ? "vis b3,1" : "vis b3,0"));
    ServoShow();
}
static void ServoRead()
{
    ServoBusy("Reading the servos from the flight controller ...");
    ServoReq = MspAsk(120, nullptr, 0);
    ServoStep = SRV_READ;
}
void ServoPoll() // each time round the loop (ManageTransmitter)
{
    if (CurrentView != SERVOVIEW)
    {
        ServoStep = SRV_IDLE;
        return;
    }
    if (ServoMsgUntil && (int32_t)(millis() - ServoMsgUntil) >= 0)
    {
        ServoMsgUntil = 0;
        ServoBusy("");
        ServoShow();
    }
    if (ServoStep == SRV_IDLE)
    {
        if (ServoReadAgainWanted)
        {
            ServoReadAgainWanted = false;
            ServoRead();
        }
        return;
    }
    if (!PipeReplyReady(ServoReq))
    {
        if (PipeReplyLate())
            ServoFail("No answer");
        return;
    }
    const bool ok = PipeRepCode == 200;
    switch (ServoStep)
    {
    case SRV_READ:
    {
        if (!ok) { ServoFail("Could not read the servos"); return; }
        uint8_t b[1 + SERVOS_MAX * SERVO_BYTES];
        const int n = PipeReplyBytes(b, sizeof(b));
        const int count = n >= 1 ? b[0] : 0;
        if (count < 1 || n < 1 + count * SERVO_BYTES) { snprintf(PipeRepBody, sizeof(PipeRepBody), "%d bytes came for %d servos", n, count); ServoFail("Could not read the servos"); return; }
        memcpy(ServoRaw, b, 1 + count * SERVO_BYTES);
        ServoCount = count > SERVOS_MAX ? SERVOS_MAX : count;
        ServoHave = true;
        ServoStep = SRV_IDLE;
        ServoBusy("");
        Servo_Was_Edited = false;
        SendCommand((char *)"vis b3,0");
        ServoShow();
        return;
    }
    case SRV_WRITE:
        if (!ok) { ServoFail("Not written"); return; }
        ServoReq = MspAsk(250, nullptr, 0);
        ServoStep = SRV_STORE;
        return;
    case SRV_STORE:
        if (!ok) { ServoFail("Not stored"); return; }
        ServoReq = MspAsk(120, nullptr, 0);
        ServoStep = SRV_VERIFY;
        return;
    case SRV_VERIFY:
    {
        if (!ok) { ServoFail("Could not read back"); return; }
        uint8_t b[1 + SERVOS_MAX * SERVO_BYTES];
        const int n = PipeReplyBytes(b, sizeof(b));
        const int count = n >= 1 ? b[0] : 0;
        bool same = false;
        if (count >= 1 && n >= 1 + count * SERVO_BYTES)
        {
            memcpy(ServoRaw, b, 1 + (count > SERVOS_MAX ? SERVOS_MAX : count) * SERVO_BYTES);
            ServoCount = count > SERVOS_MAX ? SERVOS_MAX : count;
            same = ServoAt < ServoCount && memcmp(ServoBytes(ServoAt), ServoWant, SERVO_BYTES) == 0;
        }
        ServoStep = SRV_IDLE;
        Servo_Was_Edited = false;
        SendCommand((char *)"vis b3,0");
        ServoShow();
        ServoBusy(same ? "Saved, and read back the same." : "Saved; the flight controller adjusted some values (shown).");
        ServoMsgUntil = millis() + 4000;
        PlaySound(BEEPCOMPLETE);
        return;
    }
    default:
        ServoStep = SRV_IDLE;
        return;
    }
}
void StartServoView()
{
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFView", why);
        return;
    }
    SendCommand((char *)"page ServoView");
    CurrentView = SERVOVIEW;
    SendText((char *)"t11", ModelName);
    char b[16];
    snprintf(b, sizeof(b), "Bank %d", Bank);
    SendText((char *)"t9", b);
    SendCommand((char *)"vis b3,0");
    Servo_Was_Edited = false;
    ServoAt = 0;
    ServoRead();
}
static void ServoShowEdits() // after a question's page: the typed values again (ServoWant holds them)
{
    SendText((char *)"t11", ModelName);
    SendCommand((char *)"vis b3,1");
    ServoTitle();
    ServoNum("tn0", RdU16(ServoWant, 0)); ServoNum("tn1", RdS16(ServoWant, 2)); ServoNum("tn2", RdS16(ServoWant, 4));
    ServoNum("tn3", RdU16(ServoWant, 6)); ServoNum("tn4", RdU16(ServoWant, 8)); ServoNum("tn5", RdU16(ServoWant, 10)); ServoNum("tn6", RdU16(ServoWant, 12));
    SendValue((char *)"tn7", ServoRev ? 1 : 0);   // (B65: a switch)
    SendValue((char *)"tn8", ServoGeo ? 1 : 0);   // (B65: a switch)
}
void EndServoView() // OK
{
    if (Servo_Was_Edited)
    {
        ServoGather(); // (B59) before the question's page takes the fields away
        if (!GetConfirmation((char *)"page ServoView", (char *)"Discard the edited servo values?")) { ServoShowEdits(); return; }
    }
    ServoStep = SRV_IDLE;
    Servo_Was_Edited = false;
    RotorFlightStart();
}
void ServoWasEdited()
{
    SendCommand((char *)"vis b3,1");
    Servo_Was_Edited = true;
}
void ServoReverseTapped()
{
    ServoRev = !ServoRev;
    SendValue((char *)"tn7", ServoRev ? 1 : 0);   // (B65: a switch)
    ServoWasEdited();
}
void ServoGeometryTapped()
{
    ServoGeo = !ServoGeo;
    SendValue((char *)"tn8", ServoGeo ? 1 : 0);   // (B65: a switch)
    ServoWasEdited();
}
static void ServoStep1(int d) // < Servo / Servo >
{
    if (!ServoHave || ServoCount < 2)
        return;
    if (Servo_Was_Edited)
    {
        ServoGather();
        if (!GetConfirmation((char *)"page ServoView", (char *)"Discard the edited servo values?")) { ServoShowEdits(); return; }
        SendText((char *)"t11", ModelName);
    }
    Servo_Was_Edited = false;
    SendCommand((char *)"vis b3,0");
    ServoAt = (ServoAt + d + ServoCount) % ServoCount;
    ServoShow();
}
void ServoPrevious() { ServoStep1(-1); }
void ServoNext() { ServoStep1(1); }
void SaveServo()
{
    if (!ServoHave)
        return;
    char why[120];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page ServoView", why);
        return;
    }
    ServoGather();
    uint8_t body[1 + SERVO_BYTES];
    body[0] = (uint8_t)ServoAt;
    memcpy(body + 1, ServoWant, SERVO_BYTES);
    ServoBusy("Writing to the flight controller ...");
    ServoReq = MspAsk(212, body, sizeof(body));
    ServoStep = SRV_WRITE;
}
#endif
