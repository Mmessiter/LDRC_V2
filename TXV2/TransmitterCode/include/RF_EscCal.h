// B100 (Malcolm, 15 Oct: "Can we also add ports and esc calibration?"): the ESC's THROTTLE CALIBRATION from the
// transmitter, the fourth Model basics page (EscCalView, the screen's page 80), as the receiver's ESC setup page does it
// from the phone (data/rotorflight-esc.html): Rotorflight's motor override (MSP 195: motor index, a signed word 0..1000
// = 0..100 %; 0 = off) holds the motor channel at FULL throttle; the pilot plugs the battery in; the ESC learns the top;
// then the override is let go (0) and the ESC learns the bottom. The flight controller obeys an override only while
// DISARMED, and it LAPSES BY ITSELF one second after the last one (flight/motors.h MOTOR_OVERRIDE_TIMEOUT), so this
// page renews it as each reply comes (about every 350 ms over the pipe) and nothing can stay stuck at full throttle:
// leave the page, lose the link, flick the safety - the hold is gone a second later. A renewal that gets no reply
// within 1.2 s means the hold has lapsed already: the page says so and stops. Blades off, flight pack unplugged, the
// flight controller on USB power - as the configurator's Motors tab procedure, without the computer.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_ESCCAL_H
#define RF_ESCCAL_H

enum { ECAL_IDLE = 0, ECAL_FULL, ECAL_MIN, ECAL_DONE };
static int EcalState = ECAL_IDLE, EcalReq = 0;
static uint32_t EcalSentMs = 0, EcalNextMs = 0, EcalUntil = 0;
static bool EcalWaiting = false;   // a 195 is out, its reply not yet in
static const uint32_t ECAL_RENEW_MS = 350, ECAL_LAPSE_MS = 1200, ECAL_MIN_MS = 3000;

FLASHMEM static void EcalStatus(const char *s) { SendText((char *)"tn3", (char *)s); }
FLASHMEM static void EcalButton() { SendText((char *)"b2", (char *)(EcalState == ECAL_FULL ? "Minimum" : "Full throttle")); }
FLASHMEM static void EcalSend(int value) // MSP 195: motor 0 at value (1000 = full, 0 = the override off)
{
    uint8_t f[3];
    f[0] = 0;
    f[1] = (uint8_t)(value & 0xFF);
    f[2] = (uint8_t)((value >> 8) & 0xFF);
    EcalReq = MspAsk(195, f, 3);
    EcalSentMs = millis();
    EcalWaiting = true;
}
FLASHMEM static void EcalShow()
{
    EcalButton();
    if (EcalState == ECAL_FULL) EcalStatus("FULL THROTTLE held: plug the flight battery in");
    else if (EcalState == ECAL_MIN) EcalStatus("MINIMUM: wait for the confirmation beeps");
    else if (EcalState == ECAL_DONE) EcalStatus("Calibrated: unplug the battery");
    else EcalStatus("Ready: tap Full throttle to begin");
}
FLASHMEM void EscCalStop() // the hold let go, wherever this is called from (OK, < Previous, a refusal); the FC lets go by itself a second later anyway
{
    if (EcalState == ECAL_FULL && CurrentView == ESCCALVIEW) EcalSend(0);
    EcalState = ECAL_IDLE;
    EcalWaiting = false;
}
FLASHMEM static void EcalLapsed(const char *why)
{
    EcalState = ECAL_IDLE;
    EcalWaiting = false;
    PlaySound(WHAHWHAHMSG);
    EcalButton();
    EcalStatus(why);
}
FLASHMEM void EscCalPoll()
{
    if (CurrentView != ESCCALVIEW) { if (EcalState == ECAL_FULL) EcalState = ECAL_IDLE; EcalWaiting = false; return; }   // (left while holding: the hold lapses in the FC within a second)
    if (EcalState == ECAL_MIN)
    {
        if (EcalWaiting && PipeReplyReady(EcalReq)) EcalWaiting = false;
        if ((int32_t)(millis() - EcalUntil) >= 0) { EcalState = ECAL_DONE; EcalWaiting = false; EcalShow(); PlaySound(BEEPCOMPLETE); }
        return;
    }
    if (EcalState != ECAL_FULL) return;
    if (EcalWaiting)
    {
        if (!PipeReplyReady(EcalReq))
        {
            if (millis() - EcalSentMs > ECAL_LAPSE_MS) EcalLapsed("The hold lapsed (slow link): start again");
            return;
        }
        EcalWaiting = false;
        if (PipeRepCode != 200) { EcalLapsed("The hold was refused: start again"); return; }
        EcalNextMs = EcalSentMs + ECAL_RENEW_MS;
    }
    if ((int32_t)(millis() - EcalNextMs) >= 0) EcalSend(1000);
}
FLASHMEM void StartEscCalView() // Next > on the ports page
{
    SendCommand((char *)"page EscCalView");
    CurrentView = ESCCALVIEW;
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)"All banks");
    EcalState = EcalState == ECAL_DONE ? ECAL_DONE : ECAL_IDLE;
    EcalWaiting = false;
    EcalShow();
}
FLASHMEM void EndEscCalView() // < Previous: back to the ports
{
    EscCalStop();
    StartBasics3View();
}
FLASHMEM void EscCalTapped() // the one button: Full throttle, or Minimum while held
{
    if (EcalState == ECAL_FULL) { EcalSend(0); EcalState = ECAL_MIN; EcalUntil = millis() + ECAL_MIN_MS; EcalShow(); return; }
    if (EcalState == ECAL_MIN) return;
    char why[120];
    if (RfNeedsModel(why, sizeof(why)) || ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why)))
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page EscCalView", why);
        return;
    }
    if (BakOffline())
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page EscCalView", (char *)"The calibration needs the model itself,\r\nswitched on and joined by Bluetooth.");
        return;
    }
    if (!GetConfirmation((char *)"page EscCalView", (char *)"Blades OFF or pinion out? Flight pack\r\nUNPLUGGED? Flight controller on USB power?\r\nIt holds FULL throttle until you tap\r\n'Minimum'. Plug the flight battery in\r\nonce it is held."))
    {
        EcalShow();
        return;
    }
    EcalShow();
    EcalState = ECAL_FULL;
    EcalSend(1000);
    EcalShow();
}
#endif
