#!/usr/bin/env python3
"""THE ROTORFLIGHT SETTINGS PAGE TAKES ITS THREE BOXES WHOLE, OR NOT AT ALL (15 Nov 2026; found by the tenth review's check of what
a gather writes). The page holds the gear ratio, THE ARMING CHANNEL and "rates follow the banks". Its gather (RF_RotorFlight.h
RFSettingsGather: the page's OK, and the way on to Model basics and to Calibrate) looked at each box for itself - a ratio above 0,
digits only, 0 or 1 - so "no answer" changed none of them. But the first box could be taken and the next not: the gear ratio new,
the arming channel as it was, the model SAVED so, and the page left with no more than a sound. Now all three are asked before any
is taken; with one unanswered the box "The screen did not answer ..." comes, nothing is taken, nothing saved, and the page stays.
The REAL RFSettingsGather, EndRFSettingsView (RF_RotorFlight.h) and RfFieldsMissed (Nextion.h) over the pretend screen."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
RFS = m.release(m.src('include/RF_RotorFlight.h'))
SDC = m.release(m.src('include/SDcard.h'))
_at = SDC.index('    GearRatio = SDReadFLOAT(SDCardAddress);'); RATIO_LINES = SDC[_at:SDC.index('    ++SDCardAddress;', _at)]   # (the read, and what stands between it and the address moving on)
if 'GearRatio = 10.3f' not in RATIO_LINES: print('FAIL: SDcard.h: the gear ratio read from the card is held to a number in the line behind its read'); sys.exit(1)
EXTRA = r'''
float GearRatio = 10.3f; uint8_t ArmingChannel = 6; bool LinkRatesToBanks = false;
static int rfMenus = 0; static void RotorFlightStart() { ++rfMenus; SendCommand((char *) "page RFView"); CurrentView = 47; }
''' + m.lift(m.NEXTION, 'FLASHMEM bool RfFieldsMissed(const char *page)') + m.lift(RFS, 'FLASHMEM bool RFSettingsGather()') + m.lift(RFS, 'FLASHMEM void EndRFSettingsView()') + r'''
static float cardFloat = 0; static int SDCardAddress = 0; static float SDReadFLOAT(int) { return cardFloat; }
static float ratioFromCard(float onCard) { cardFloat = onCard; GearRatio = -1;
''' + RATIO_LINES + r'''    return GearRatio; }   // include/SDcard.h's own two lines: the model's gear ratio as it comes from the card
static void my24(int n) { if (n == 200) EndRFSettingsView(); else more24(n); }
static void my7(int n) { if (n == 2) Confirmed[0] = 'N'; else more7(n); }   // (the question's No)
static void addSettings()
{
    Page s; s.id = 61;
    for (const char *t : { "Ratio", "Arming", "t5" }) s.boxes[t] = { true, 0, "" };
    s.boxes["sw0"] = { false, 0, "" };
    s.boxes["Ratio"].txt = "10.30"; s.boxes["Arming"].txt = "6"; s.buttons["OK"] = { 0x00, 200, 0x00, 0x00 };
    screen.pages["RFSetupView"] = s; { Page r; r.id = 47; screen.pages["RFView"] = r; }
    screen.pages0 = screen.pages;
    GearRatio = 10.3f; ArmingChannel = 6; LinkRatesToBanks = false; rfMenus = 0; extra24 = my24;
}
static void openSettings()   // the page up, and the screen has said its page once (as on a transmitter in use)
{
    SendCommand((char *) "page RFSetupView"); CurrentView = RFSETUPVIEW; loopFor(600); { char t[8]; GetText((char *) "t5", t, sizeof t); } loopFor(50);
}
static void typeAll() { Page &p = screen.pages["RFSetupView"]; p.boxes["Ratio"].txt = "11.25"; p.boxes["Arming"].txt = "7"; p.boxes["sw0"].val = 1; }
static bool asBefore() { return GearRatio > 10.29f && GearRatio < 10.31f && ArmingChannel == 6 && !LinkRatesToBanks; }
static bool asTyped() { return GearRatio > 11.24f && GearRatio < 11.26f && ArmingChannel == 7 && LinkRatesToBanks; }
'''
SCENES = r'''
    // (1) nothing in the way: the three boxes typed anew, OK - all taken, the model saved once, the menu comes
    more(); addSettings(); openSettings(); typeAll(); { const size_t s0 = saves.size(); tapAt(5, "OK"); loopFor(3000);
      say("F1. the settings page, three boxes typed, OK: gear ratio %.2f, arming channel %u, rates follow banks %d; the model saved %d time(s); the menu came %d; boxes lost %d\n",
          GearRatio, (unsigned) ArmingChannel, (int) LinkRatesToBanks, (int) (saves.size() - s0), rfMenus, boxesLostTold);
      CHECK(asTyped() && saves.size() == s0 + 1 && rfMenus == 1 && boxesLostTold == 0 && screen.page == "RFView"); }
    // (2) ONE BOX HAS NO ANSWER - each of the three in turn, and the "which page?" answer of the first: NOTHING is taken (the gear
    //     ratio went in while the arming channel stayed), nothing saved, the box says so, the page stays with what he typed on it.
    //     He presses OK again: all three are taken.
    for (int which = 0; which < 4; ++which)
    {
        static const char *box[3] = { "Ratio", "Arming", "sw0" };
        more(); addSettings(); openSettings(); typeAll(); const size_t s0 = saves.size();
        if (which < 3) screen.mute.insert(box[which]); else screen.muteSendme = 1;
        tapAt(5, "OK"); tapAt(4500, "yes"); loopFor(8000);
        say("F2 (%s unanswered). OK: gear ratio %.2f, arming channel %u, rates follow banks %d (they were 10.30, 6, 0; typed 11.25, 7, 1); saved %d; the menu came %d; told %d; page %s; the boxes show '%s', '%s', %ld\n",
            which < 3 ? box[which] : "one 'which page?'", GearRatio, (unsigned) ArmingChannel, (int) LinkRatesToBanks, (int) (saves.size() - s0), rfMenus, boxesLostTold, screen.page.c_str(),
            screen.pages["RFSetupView"].boxes["Ratio"].txt.c_str(), screen.pages["RFSetupView"].boxes["Arming"].txt.c_str(), screen.pages["RFSetupView"].boxes["sw0"].val);
        CHECK(asBefore());                                                           // nothing taken
        CHECK(saves.size() == s0 && rfMenus == 0);                                   // nothing saved, the page not left
        CHECK(boxesLostTold == 1 && screen.page == "RFSetupView" && CurrentView == RFSETUPVIEW);
        CHECK(screen.pages["RFSetupView"].boxes["Ratio"].txt == "11.25" && screen.pages["RFSetupView"].boxes["Arming"].txt == "7" && screen.pages["RFSetupView"].boxes["sw0"].val == 1);
        screen.mute.clear(); tapAt(5, "OK"); loopFor(3000);
        say("    ... OK again: gear ratio %.2f, arming channel %u, rates follow banks %d; saved %d; the menu came %d\n", GearRatio, (unsigned) ArmingChannel, (int) LinkRatesToBanks, (int) (saves.size() - s0), rfMenus);
        CHECK(asTyped() && saves.size() == s0 + 1 && rfMenus == 1);
    }
    // (3) an arming channel of 1 to 5 is asked about (B146) - with every box answered: "Yes" takes it, "No" leaves it; the rest is taken either way
    for (int yes = 0; yes < 2; ++yes)
    {
        more(); addSettings(); openSettings(); typeAll(); screen.pages["RFSetupView"].boxes["Arming"].txt = "5"; const size_t s0 = saves.size();
        screen.pages["PopupView"].buttons["no"] = { 0x82, 0x00, 0x00, 0x00 };   // (the eleventh review's follow-up: the question's No is PRESSED - it had been left to close by itself) 
        extra7 = my7;
        tapAt(5, "OK"); tapAt(2500, yes ? "yes" : "no"); loopFor(6000);
        say("F3. arming channel 5 typed, the question answered %s: arming channel %u, gear ratio %.2f; saved %d; the menu came %d\n", yes ? "Yes" : "No", (unsigned) ArmingChannel, GearRatio, (int) (saves.size() - s0), rfMenus);
        CHECK(ArmingChannel == (yes ? 5 : 6) && GearRatio > 11.24f && GearRatio < 11.26f && LinkRatesToBanks && saves.size() == s0 + 1 && rfMenus == 1 && boxesLostTold == 0);
    }
    // (4) what "no answer" could never do, and still cannot: a box that answers with nonsense changes nothing of its own field
    more(); addSettings(); openSettings(); { Page &p = screen.pages["RFSetupView"]; p.boxes["Ratio"].txt = ""; p.boxes["Arming"].txt = "10.30"; p.boxes["sw0"].val = 7; }   // (the ratio's box EMPTY: as it was. A ratio of 0 is refused with a box now - scene 7)
    { const size_t s0 = saves.size(); tapAt(5, "OK"); loopFor(3000);
      say("F4. the ratio's box empty, an arming channel of '10.30', a switch of 7: gear ratio %.2f, arming channel %u, rates follow banks %d; saved %d\n", GearRatio, (unsigned) ArmingChannel, (int) LinkRatesToBanks, (int) (saves.size() - s0));
      CHECK(asBefore() && saves.size() == s0 + 1 && rfMenus == 1); }
'''
SCENES += r'''
    // (5) THE RATIO'S BOX HOLDS NO NUMBER (the thirteenth review, reviewer B's A8: "nan" - what the page showed for a ratio the card held as FF FF FF FF):
    //     NOTHING is taken (the arming channel typed beside it neither), and the box and the log say what it IS - "The screen did not answer ...
    //     Please press Save again" was said, every time. Typed again, OK saves all three.
    more(); addSettings(); openSettings(); typeAll(); screen.pages["RFSetupView"].boxes["Ratio"].txt = "nan";
    { const size_t s0 = saves.size(), l0 = logLines.size(); tapAt(5, "OK"); tapAt(4500, "yes"); loopFor(8000);
      const std::string said = screen.pages["PopupView"].boxes["Dialog"].txt; std::string refused;
      for (size_t i = l0; i < logLines.size(); ++i) if (logLines[i].find("Refused:") != std::string::npos) refused = logLines[i];
      say("F5. the ratio's box holds 'nan': gear ratio %.2f, arming channel %u; saved %d; the box says [%s]; the log [%s]\n", GearRatio, (unsigned) ArmingChannel, (int) (saves.size() - s0), said.substr(0, said.find('\r')).c_str(), refused.c_str());
      CHECK(asBefore() && saves.size() == s0 && rfMenus == 0 && screen.page == "RFSetupView" && CurrentView == RFSETUPVIEW);
      CHECK(said.find("A number box gave no number") == 0 && said.find("NOTHING was sent") != std::string::npos && said.find("Press Save again") != std::string::npos && said.find("empty or not a number") != std::string::npos && said.find("did not answer") == std::string::npos && said.find("Ratio") == std::string::npos);   // (words that fit a box that IS fine, its answer glued behind a line of the screen's - Save again helps there. The fifteenth review: no inner name on the screen - "tn7" says nothing to a pilot; the log's line names it, below)
      { size_t longest = 0, at = 0; while (at <= said.size()) { size_t e = said.find("\r\n", at); if (e == std::string::npos) e = said.size(); if (e - at > longest) longest = e - at; at = e + 2; } CHECK(longest <= 40); }   // (four lines that fit the box)
      CHECK(refused.find("box Ratio holds a text that is no number") != std::string::npos && refused.find("did not answer") == std::string::npos);
      screen.pages["RFSetupView"].boxes["Ratio"].txt = "11.25"; tapAt(5, "OK"); loopFor(3000); CHECK(asTyped() && saves.size() == s0 + 1 && rfMenus == 1); }
    //     ... and a box that gives NO answer is still said as that (the two are told apart at each Save: the mark of the one before does not stand)
    more(); addSettings(); openSettings(); typeAll(); screen.pages["RFSetupView"].boxes["Ratio"].txt = "nan";
    { tapAt(5, "OK"); tapAt(4500, "yes"); loopFor(8000); screen.pages["RFSetupView"].boxes["Ratio"].txt = "11.25"; screen.mute.insert("Arming"); const size_t l0 = logLines.size();
      tapAt(5, "OK"); tapAt(4500, "yes"); loopFor(8000); screen.mute.clear();
      const std::string said = screen.pages["PopupView"].boxes["Dialog"].txt; std::string refused;
      for (size_t i = l0; i < logLines.size(); ++i) if (logLines[i].find("Refused:") != std::string::npos) refused = logLines[i];
      CHECK(asBefore() && said.find("did not answer") != std::string::npos && said.find("gave no number") == std::string::npos && refused.find("did not answer for box Arming") != std::string::npos); }
    //     ... nor does the mark left by ANOTHER page's work (Model options' OK looks at its number boxes the same way, and nothing there clears it)
    more(); addSettings(); openSettings(); typeAll();
    { char tx[8] = "3p"; NextionTextMissed = false; CHECK(!TextMustBeNumber("t10", tx) && NextionMissedNoNumber); BoxesLostAtWork = BoxesLost;
      screen.mute.insert("Arming"); tapAt(5, "OK"); tapAt(4500, "yes"); loopFor(8000); screen.mute.clear();
      const std::string said = screen.pages["PopupView"].boxes["Dialog"].txt;
      CHECK(asBefore() && said.find("did not answer") != std::string::npos && said.find("gave no number") == std::string::npos); }
    // (7) (the fourteenth review) THE PAGE TAKES THE RATIOS THE CARD KEEPS: "1030" typed for 10.30 was taken, used, and was 10.3 at the next switch-on
    // (the fifteenth review: ... AND AS THE PAGE WILL SHOW IT, to two places: "999.999" was taken and shown as "1000.00", "0.004" as "0.00" - and the next OK
    //  on the untouched page was refused for a number he had not typed)
    for (const char *typed : { "1030", "1000", "0", "-3", "0.0", ".", "999.999", "999.996", "0.004", "0.0049" })
    {
        more(); addSettings(); openSettings(); typeAll(); screen.pages["RFSetupView"].boxes["Ratio"].txt = typed;
        const size_t s0 = saves.size(); const int sounds0 = soundsPlayed; tapAt(5, "OK"); tapAt(4500, "yes"); loopFor(8000);
        const std::string said = screen.pages["PopupView"].boxes["Dialog"].txt;
        if (!(asBefore() && saves.size() == s0)) say("F7. the ratio typed '%s': gear ratio %.2f, arming channel %u, saved %d, the menu came %d; the box [%s]\n", typed, GearRatio, (unsigned) ArmingChannel, (int) (saves.size() - s0), rfMenus, said.substr(0, said.find('\r')).c_str());
        CHECK(asBefore() && saves.size() == s0 && rfMenus == 0 && screen.page == "RFSetupView" && CurrentView == RFSETUPVIEW && soundsPlayed == sounds0 + 1);   // NOTHING is taken (the arming channel and the switch typed beside it neither), the page stays
        CHECK(said.find("The gear ratio must be more than 0") == 0 && said.find("less than 1000") != std::string::npos && said.find("NOTHING was changed") != std::string::npos);
        screen.pages["RFSetupView"].boxes["Ratio"].txt = "11.25"; tapAt(5, "OK"); loopFor(3000); CHECK(asTyped() && saves.size() == s0 + 1 && rfMenus == 1);
    }
    for (const char *typed : { "999.99", "0.01", "10.30", "", "999.994", "0.006", "10.333", "0.0051" })      // ... what the card keeps is taken; an empty box leaves the ratio as it was
    {
        more(); addSettings(); openSettings(); typeAll(); screen.pages["RFSetupView"].boxes["Ratio"].txt = typed;
        const size_t s0 = saves.size(); tapAt(5, "OK"); loopFor(3000);
        float want = *typed ? (float) atof(typed) : 10.3f;
        { char as[16]; snprintf(as, sizeof as, "%1.2f", want); want = (float) atof(as); }             // (the sixteenth review) IT IS KEPT AS THE PAGE SHOWS IT - to two places ("10.333" is 10.33)
        CHECK(GearRatio > want - 0.001f && GearRatio < want + 0.001f && ArmingChannel == 7 && LinkRatesToBanks && saves.size() == s0 + 1 && rfMenus == 1);
        const float back = ratioFromCard(GearRatio); CHECK(back > want - 0.001f && back < want + 0.001f);       // ... and the card's reader gives the same ratio back
        { char as[16]; snprintf(as, sizeof as, "%1.2f", GearRatio); const float shown = (float) atof(as); CHECK(shown > 0.0f && shown < 1000.0f); }   // (the fifteenth review) ... and what the page will SHOW of it is a ratio the page takes
        GearRatio = 10.3f;
    }
    // (6) THE RATIO AS IT COMES FROM THE CARD (include/SDcard.h's own lines): FF FF FF FF is no number - the page showed "nan" and its OK refused for ever.
    //     Held to a number at the read: above 0 and below 1000, else the 10.3 of a new model.
    { float nanv; const uint32_t ff = 0xFFFFFFFFu; memcpy(&nanv, &ff, 4); const float inf = 1.0f / 0.0f;
      const float in[] = { nanv, inf, -inf, 0.0f, -3.0f, 1000.0f, 5000.0f, 999.5f, 10.3f, 0.01f, 8.0f };
      const float out[] = { 10.3f, 10.3f, 10.3f, 10.3f, 10.3f, 10.3f, 10.3f, 999.5f, 10.3f, 0.01f, 8.0f };
      bool all = true; for (int i = 0; i < 11; ++i) { const float r = ratioFromCard(in[i]); if (!(r > out[i] - 0.001f && r < out[i] + 0.001f)) { all = false; printf("   the card's ratio %f came out as %f\n", in[i], r); } }
      say("F6. the gear ratio from the card - no number, infinite, 0, negative, 1000 and more: 10.3; a ratio: itself: %d\n", (int) all);
      CHECK(all); }
'''
sys.exit(lib.build_run('rfsettings', SCENES, extra=EXTRA, more_defines=('RFSETUPVIEW', 'CHANNELSUSED')))
