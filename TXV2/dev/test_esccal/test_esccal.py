#!/usr/bin/env python3
"""Host test of the ESC throttle calibration page (B100): include/RF_EscCal.h on the Mac over a fake screen and a fake
flight controller on the fake pipe. The hold (MSP 195, motor 0 at 1000) renewed about every 350 ms as the replies come,
Minimum (0) then Calibrated after 3 s, a hold that lapses when a renewal gets no answer in 1.2 s, the hold let go by OK
(EscCalStop) and by < Previous, leaving the page, the refusals (armed, offline, the question answered no).
   python3 dev/test_esccal/test_esccal.py"""
import os, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'RF_EscCal.h')
prog = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <map>
#include <vector>
#define FLASHMEM
#define WHAHWHAHMSG 1
#define BEEPCOMPLETE 2
#define ROTORFLIGHTVIEW 47
#define PORTSVIEW 79
#define ESCCALVIEW 80
static int CurrentView = 0;
static bool offline = false, armed = false;
static char ModelName[20] = "Havoc";
static uint32_t now = 1000;
static uint32_t millis() { return now; }
static std::map<std::string, std::string> fields; static std::vector<std::string> cmds; static int boxes = 0; static std::string lastBox; static bool confirmAnswer = true; static int sounds = 0, asked = 0, backs = 0;
static void SendCommand(char *c) { cmds.push_back(c); }
static void SendText(char *n, char *t) { fields[n] = t; }
static void MsgBox(char *page, const char *msg) { ++boxes; lastBox = msg; }
static bool GetConfirmation(char *page, char *prompt) { ++asked; lastBox = prompt; return confirmAnswer; }
static void PlaySound(int) { ++sounds; }
static bool ModelSeemsArmed(char *why, size_t n) { if (!armed) return false; snprintf(why, n, "Model is armed"); return true; }
static bool RfPipeBlocked(char *, size_t) { return false; }
static bool RfNeedsModel(char *, size_t) { return false; }
static bool BakOffline() { return offline; }
void StartBasics3View() { ++backs; CurrentView = PORTSVIEW; }
// ---- the pipe and a fake flight controller: every 195 answered at once (or not at all while holdReplies)
static int PipeReqId = 0, PipeRepId = -1, PipeRepCode = 0; static char PipeRepBody[1600] = "";
static bool holdReplies = false;
bool PipeReplyReady(int id) { return PipeRepId == id; }
struct Sent { uint32_t at; int value; };
static std::vector<Sent> sent;
int MspAsk(uint8_t fn, const uint8_t *data, int len) {
    ++PipeReqId;
    if (fn == 195 && len == 3) sent.push_back({now, data[1] | (data[2] << 8)});
    if (holdReplies) return PipeReqId;
    PipeRepCode = 200; PipeRepBody[0] = 0; PipeRepId = PipeReqId;
    return PipeReqId;
}
''' + open(HDR).read().replace('#include <Arduino.h>', '').replace('#include "1Definitions.h"', '') + r'''
static int checks = 0, fails = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); } } while (0)
static void run(int ms) { for (int t = 0; t < ms; t += 50) { EscCalPoll(); now += 50; } }
static int sends(int value) { int k = 0; for (auto &s : sent) if (s.value == value) ++k; return k; }
static bool cmd(const char *c) { for (auto &x : cmds) if (x == c) return true; return false; }
int main() {
    // ---- 1. the page
    cmds.clear(); StartEscCalView();
    CHECK(CurrentView == ESCCALVIEW && cmd("page EscCalView") && fields["t9"] == "All banks" && fields["tn3"] == "Ready: tap Full throttle to begin" && fields["b2"] == "Full throttle");
    // ---- 2. the hold: asked, then 195 at 1000 renewed about every 350 ms
    asked = 0; EscCalTapped();
    CHECK(asked == 1 && lastBox.find("Blades off") != std::string::npos && EcalState == ECAL_FULL && sends(1000) == 1 && fields["tn3"] == "FULL THROTTLE held: plug the battery in" && fields["b2"] == "Minimum");
    run(2000);
    { const int n = sends(1000); CHECK(n >= 5 && n <= 8); bool spaced = true; for (size_t i = 1; i < sent.size(); ++i) if (sent[i].at - sent[i - 1].at < 300) spaced = false; CHECK(spaced); }
    // ---- 3. Minimum: the override off (0), the beeps awaited, Calibrated after 3 s
    sounds = 0; EscCalTapped();
    CHECK(EcalState == ECAL_MIN && sends(0) == 1 && fields["tn3"] == "MINIMUM: wait for the beeps" && fields["b2"] == "Full throttle");
    run(2000); CHECK(EcalState == ECAL_MIN); run(1200);
    CHECK(EcalState == ECAL_DONE && fields["tn3"] == "Calibrated: unplug the battery" && sounds == 1);
    { const int before = sends(1000); run(1000); CHECK(sends(1000) == before); }   // (nothing renewed once done)
    // ---- 4. a renewal without an answer: the hold has lapsed in the flight controller - said, and stopped
    sent.clear(); EscCalTapped(); CHECK(EcalState == ECAL_FULL); run(1000); holdReplies = true; run(400); const int n1 = sends(1000); run(1300); holdReplies = false;
    CHECK(EcalState == ECAL_IDLE && fields["tn3"] == "The hold lapsed (slow link): start again" && fields["b2"] == "Full throttle" && sends(1000) == n1);
    // ---- 5. OK while holding (EscCalStop, called by RF_Basics.h EndBasicsView): one 0 sent, the hold over
    sent.clear(); EscCalTapped(); run(700); CHECK(EcalState == ECAL_FULL && sends(1000) >= 2);
    EscCalStop(); CHECK(EcalState == ECAL_IDLE && sends(0) == 1); run(1000); CHECK(sends(1000) == 3 || sends(1000) == 2);
    // ---- 6. < Previous while holding: let go, then the ports page
    StartEscCalView(); sent.clear(); EscCalTapped(); run(500); backs = 0; EndEscCalView(); CHECK(sends(0) == 1 && EcalState == ECAL_IDLE && backs == 1 && CurrentView == PORTSVIEW);
    // ---- 7. the page left some other way while holding: no more renewals (the flight controller lets go by itself)
    StartEscCalView(); sent.clear(); EscCalTapped(); run(500); CurrentView = ROTORFLIGHTVIEW; const int n2 = sends(1000); run(2000); CHECK(sends(1000) == n2 && EcalState == ECAL_IDLE);
    // ---- 8. refusals: armed, offline, the question answered no - nothing sent
    StartEscCalView(); sent.clear();
    armed = true; boxes = 0; EscCalTapped(); CHECK(boxes == 1 && lastBox == "Model is armed" && sent.empty() && EcalState == ECAL_IDLE); armed = false;
    offline = true; boxes = 0; EscCalTapped(); CHECK(boxes == 1 && lastBox.find("needs the model") != std::string::npos && sent.empty()); offline = false;
    confirmAnswer = false; EscCalTapped(); CHECK(sent.empty() && EcalState == ECAL_IDLE && fields["b2"] == "Full throttle"); confirmAnswer = true;
    // ---- 9. a refused renewal (the receiver says no): said, and stopped
    EscCalTapped(); CHECK(EcalState == ECAL_FULL); PipeRepCode = 409; run(100); CHECK(EcalState == ECAL_IDLE && fields["tn3"] == "The hold was refused: start again");
    printf("test_esccal: %d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
'''
d = tempfile.mkdtemp(); cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(prog)
r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-const-variable', '-o', os.path.join(d, 't'), cpp], capture_output=True, text=True)
if r.returncode: print(r.stderr[:6000]); sys.exit(1)
if r.stderr.strip(): print(r.stderr[:3000])
sys.exit(subprocess.run([os.path.join(d, 't')]).returncode)
