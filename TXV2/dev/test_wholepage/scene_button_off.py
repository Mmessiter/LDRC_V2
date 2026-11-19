#!/usr/bin/env python3
"""THE KEPT LINES AT THE POWER BUTTON'S POWER-OFF, BY A RUN (main.cpp Close_TX_Down; the thirteenth review's cure). The suite held this road by a text
check alone (dev/test_poweroff_lines), and the eighteenth and the nineteenth reviews (reviewer A) each showed a wrong condition in front of the writing
- "if (UseLog && LedWasGreen) FlushDeferredLog();", the thirteenth review's own fault - passing every test. The idle power-off has its run in
scene_idle_off; this is the button's. The REAL Close_TX_Down, lifted, in the harness's namespace "kept" beside the REAL LogFiles.h chain
(KeepScreenNote, DeferLogText, FlushDeferredLog; a card that is a text); stand-ins for what else it calls, which write down THE ORDER.
 P1. NO MODEL CONNECTED, the log switched off in the options, lines kept: they are on the card AT THE MOMENT THE POWER IS CUT, in one opening.
 P2. a model still connected, the log on: the kept lines first, then the session's own last lines, then the cut.
 P3. nothing kept, no model: the card is not opened; the power is cut."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'dev', 'test_wholepage'))
import lib
m = lib.m
MAINC = m.release(m.src('src/main.cpp'))
EXTRA = 'namespace kept {\n' + r'''
static std::vector<std::string> order; static std::string cardAtCut; static int cuts = 0, opensAtCut = 0;
enum { OFF_BUTTON_ = 1, OFF_BUTTON_CONNECTED_ = 2 };
#define OFF_BUTTON kept::OFF_BUTTON_
#define OFF_BUTTON_CONNECTED kept::OFF_BUTTON_CONNECTED_
#define POWER_OFF_PIN 5
#ifndef HIGH
#define HIGH 1
#endif
#define GREENLED 1
#define BLUELED 2
#define REDLED 3
#define WINDOWS2 9
#define POWERONOFFDELAY 2000
static bool PlayFanfare = false, UseLog = false, LedWasGreen = false; static char ModelName[30] = "Not in use", LogWriteName[20] = "LOG.TXT"; static char pBlankView[] = "page BlankView";
static void NoteWhyOff(uint8_t why) { order.push_back(why == OFF_BUTTON_CONNECTED_ ? "why off: the button, a model connected" : "why off: the button"); }
static void PerfWriteReport(bool) { order.push_back("the timing report"); }
static void CrumbClear() { order.push_back("the crumb cleared"); }
static void analogWrite(int, int) {} static void RestoreBrightness() {} static void SendCommand(char *) {} static void PlaySound(int) {} static void SendText(char *, char *) {} static void SetBrightness(int) {}
static void SaveAllParameters() { order.push_back("the model saved"); } static void DelayWithDog(uint32_t ms) { nowUs += (uint64_t) ms * 1000ull; } static void delay(uint32_t) {}
static void LogText(char *t, uint16_t, bool) { order.push_back(std::string("the log: ") + t); } static void LogDisConnection() { order.push_back("the session's summary"); }   // (CloseLogWriteFile is the harness's own)
static void digitalWrite(int pin, int v) { if (pin == POWER_OFF_PIN && v == HIGH) { ++cuts; if (cuts == 1) { cardAtCut = cardText; opensAtCut = cardOpens; } order.push_back("THE POWER IS CUT"); } }
''' + m.lift(MAINC, 'void Close_TX_Down()').replace('FlushDeferredLog();', '{ const int o0 = cardOpens; const size_t b0 = cardText.size(); FlushDeferredLog(); char b[80]; snprintf(b, sizeof b, "the kept lines (%d opening(s) of the card, %u bytes)", cardOpens - o0, (unsigned) (cardText.size() - b0)); order.push_back(b); }', 1) + '}\n'
SCENES = r"""
    {
        auto at = [&](const char *what) { for (size_t i = 0; i < kept::order.size(); ++i) if (kept::order[i].find(what) == 0) return (int) i; return -1; };
        // P1. no model connected, the log off in the options, lines kept (a note of this release about the screen, with the safety off on the bench; two of the link's)
        kept::reset(); kept::order.clear(); kept::cuts = 0; kept::flies = true; mayFly = true; kept::BoundFlag = kept::ModelMatched = false; kept::LedWasGreen = false; kept::UseLog = false;
        kept::KeepScreenNote("Box unanswered: tn3 of the page as it was", false); kept::DeferLogText((char *) "Gap: 41", true); kept::DeferLogText((char *) "Gap: 57", true);
        const int kept0 = kept::DeferredLogN, opens0 = kept::cardOpens; const size_t bytes0 = kept::cardText.size();
        kept::Close_TX_Down();
        printf("P1. the button, NO MODEL CONNECTED, the log off, %d lines kept. The calls, in their order:", kept0); for (auto &o : kept::order) printf(" [%s]", o.c_str()); printf("\n");
        printf("    on the card as the power was cut: %u bytes more, in %d opening(s); left in memory: %d\n", (unsigned) (kept::cardAtCut.size() - bytes0), kept::opensAtCut - opens0, kept::DeferredLogN);
        CHECK(kept0 >= 3 && kept::cuts == 1 && kept::opensAtCut - opens0 == 1 && kept::cardAtCut.size() > bytes0 && kept::cardAtCut == kept::cardText && kept::DeferredLogN == 0);
        CHECK(kept::cardAtCut.find("Box unanswered: tn3") != std::string::npos && kept::cardAtCut.find("Gap: 41") != std::string::npos && kept::cardAtCut.find("Gap: 57") != std::string::npos);
        CHECK(at("why off: the button") == 0 && at("the kept lines (1 opening") > 0 && at("the kept lines") < at("THE POWER IS CUT") && at("the log: ") < 0 && at("the session's summary") < 0);
        // P2. a model still connected, the log on: the kept lines, then the session's last lines, then the cut
        kept::reset(); kept::order.clear(); kept::cuts = 0; kept::BoundFlag = kept::ModelMatched = true; kept::LedWasGreen = true; kept::UseLog = true; strcpy(kept::ModelName, "Havoc");
        kept::DeferLogText((char *) "Gap: 63", true);
        const int opens2 = kept::cardOpens;
        kept::Close_TX_Down();
        printf("P2. the button, a model CONNECTED, the log on. The calls:"); for (auto &o : kept::order) printf(" [%s]", o.c_str()); printf("\n");
        CHECK(kept::cuts == 1 && kept::opensAtCut - opens2 == 1 && kept::cardAtCut.find("Gap: 63") != std::string::npos && kept::DeferredLogN == 0);
        CHECK(at("why off: the button, a model connected") == 0 && at("the model saved") > 0 && at("the kept lines") > at("the model saved") && at("the log: Transmitter powered off while still connected") > at("the kept lines")
              && at("the session's summary") > at("the log: ") && at("THE POWER IS CUT") == (int) kept::order.size() - 1);
        // P3. nothing kept, no model
        kept::reset(); kept::order.clear(); kept::cuts = 0; kept::BoundFlag = kept::ModelMatched = false; kept::LedWasGreen = false; kept::UseLog = true; strcpy(kept::ModelName, "Not in use");
        const int opens3 = kept::cardOpens;
        kept::Close_TX_Down();
        printf("P3. the button, nothing kept, no model: the card opened %d time(s); the power cut %d\n", kept::cardOpens - opens3, kept::cuts);
        CHECK(kept::cardOpens == opens3 && kept::cuts == 1 && at("the model saved") < 0);
    }
    mayFly = false; kept::flies = false;
"""
if __name__ == '__main__':
    sys.exit(lib.build_run('button_off', SCENES, extra=EXTRA, args=['--show']))
