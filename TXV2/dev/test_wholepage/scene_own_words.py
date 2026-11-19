#!/usr/bin/env python3
"""THE SCREEN'S OWN WORDS, AS main.cpp ANSWERS THEM IN FRONT OF THE PAGES' WORDS (the thirteenth review, reviewer A's findings 5 and 10; 15 Nov 2026).
main.cpp ButtonWasPressed answers the screen's "LDRC..." words first and goes back; whatever is not one of them goes on to the pages' words, which are
looked for ANYWHERE in the text ("Mark", "Clear", "DelFile", "GOTO:" ...).
 X1 A TEXT THAT BEGINS "LDRC" AND IS NONE OF THE WHOLE WORDS GOES NO FURTHER. Its first four letters make it "the screen's own" (Nextion.h
    IsScreensOwnWord) - and a line cut after four to seven of them ("LDRC" ... "LDRCLOG", no blank yet) with a late text answer glued behind fell
    through: "LDRCLOGpMark 2" marked the GPS position (the reviewer's run).
 X2 every whole word is still answered by its own lines.
 X3 A LINE OF THE BLUETOOTH PIPE IS ANSWERED IN FRONT OF THE PAGES' WORDS (released code had it): its body was searched for every page's word before
    the pipe's own answer was reached - "ldrcrep 200 Mark ..." would have marked the position.
 X4 what is not the screen's own goes on, untouched, and nothing here answers it.
 X5 (the fourteenth review, reviewer A's 6) THE SCREEN'S OWN WORDS ARE LOOKED FOR IN WHAT THE SCREEN ITSELF SAID: never in a page's FRAMED word
    ("DelFile LDRCOFF.MOD" switched the transmitter off), never in a pipe line's body (the line is answered first), and the words that ACT - power
    off, the file link, a receiver's update, a picture chosen - only at the HEAD of the text ("LDRCIMG LDRCOFF", a picture of that name).
The REAL lines of main.cpp (from "OwnWordCut(TextIn)" to the old code's first line) and the REAL OwnWordCut and ScreenDyingWords run here."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
m = lib.m
MAINC = m.MAIN_CPP
a = MAINC.index('        if (!TextInFramed && ScreenFramesBursts)\n            OwnWordCut(TextIn);'); b = MAINC.index('        // The very old code below here', a)
OWN = MAINC[a:b]
if OWN.count('return;') < 9 or 'InStrng(Mark' in OWN or OWN.index('"ldrctel "') > OWN.index('LDRCLOG') or OWN.index('"ldrcrep "') > OWN.index('LDRCLOG') or not re.search(r'if \(!TextInFramed\)\s*\{\s*if \(InStrng\(\(char \*\)"LDRCLOG ", TextIn\) > 0\)', re.sub(r'//[^\n]*', '', OWN)) or 'InStrng((char *)"LDRCOFF"' in OWN or 'InStrng((char *)LDRC_' in OWN: print('FAIL: main.cpp ButtonWasPressed: the screen\'s own words are not where this scene takes them from'); sys.exit(1)
EXTRA = r'''
#ifndef LDRC_LINK_KNOCK
#define LDRC_LINK_KNOCK "LDRCLINK"
#endif
#ifndef LDRC_RX_UPDATE_WORD
#define LDRC_RX_UPDATE_WORD "LDRCRXUP"
#endif
#ifndef LDRC_IMAGE_WORD
#define LDRC_IMAGE_WORD "LDRCIMG"
#endif
static std::vector<std::string> xSaid; static uint32_t ScreenTimeTimer = 0;
static void LogScreenLine(const char *t) { xSaid.push_back(std::string("log:") + t); }
static void Close_TX_Down() { xSaid.push_back("off"); } static void SendWhoWord() { xSaid.push_back("who"); } static void LinkMode() { xSaid.push_back("link"); }
static void OrderReceiverUpdateFromText(const char *t) { xSaid.push_back(std::string("rxup:") + t); } static void ChooseImageFromScreen(const char *t) { xSaid.push_back(std::string("img:") + t); }
static void TelemetryFromPipe(char *t) { xSaid.push_back(std::string("tel:") + t); } static void PipeReplyFromScreen(char *t) { xSaid.push_back(std::string("rep:") + t); }
''' + m.lift(m.NEXTION, 'B211_RARE static void OwnWordCut(char *t)') + r'''
static bool xOwnWords()   // src/main.cpp ButtonWasPressed's own lines, from "a bare word of the screen's own ends where its own text ends" to the old code. true: answered, and gone back
{
''' + OWN.replace('return;', 'return true;') + r'''
        return false;   // (it goes on to the pages' words)
}
static bool xText(const char *t, bool framed = false) { memset(TextIn, 0, 400); memcpy(TextIn, t, strlen(t)); TextInFramed = framed; xSaid.clear(); return xOwnWords(); }
static bool xOnly(const char *what) { return xSaid.size() == 1 && xSaid[0] == what; }
'''
SCENES = r'''
    more(); ScreenFramesBursts = true; BoundFlag = ModelMatched = false;
    // X1. a text that begins "LDRC" and is none of the whole words: it goes no further - whatever is glued behind it
    for (const char *t : { "LDRC", "LDRCL", "LDRCLO", "LDRCLOG", "LDRCLOGpMark 2", "LDRCpStCH", "LDRCLpDelFile A.MOD", "LDRCLOpGOTO:RXSetupView", "LDRCLOGpClear", "LDRCAWAKpMainSetup", "LDRCXYZ" })
    {
        const bool answered = xText(t);
        if (!answered || !xSaid.empty()) say("X1. '%s': answered here %d, did %d thing(s)\n", t, (int) answered, (int) xSaid.size());
        CHECK(answered && xSaid.empty() && TextIn[0] == 0);                                  // (it was: on to the pages' words - "Mark" in it marked the GPS position)
    }
    CHECK(xText("LDRCLOGpMark 2", true) && xSaid.empty());                                   // (framed or not: no page's button prints a word that begins so)
    // X2. every whole word, by its own lines
    CHECK(xText("LDRCLOG core 1 (the loop's) silent for 213 ms: play 0,7,0") && xOnly("log:LDRCLOG core 1 (the loop's) silent for 213 ms: play 0,7,0"));
    CHECK(xText("LDRCWHO") && xOnly("who")); CHECK(xText("LDRCLINK") && xOnly("link")); CHECK(xText("LDRCRXUP 0 9 870") && xOnly("rxup:LDRCRXUP 0 9 870")); CHECK(xText("LDRCIMG Yak") && xOnly("img:LDRCIMG Yak"));
    { ScreenTimeTimer = 0; nowUs += 5000; CHECK(xText("LDRCAWAKE") && xSaid.empty() && ScreenTimeTimer != 0); }
    CHECK(xText("LDRCOFF") && xOnly("off")); BoundFlag = ModelMatched = true; CHECK(xText("LDRCOFF") && xSaid.empty()); BoundFlag = ModelMatched = false;   // (never while a model is connected)
    CHECK(xText("Guru Meditation Error: Core 1 panic'ed") && xSaid.empty());                // (the screen's dying words: kept, not obeyed)
    // (the fifteenth review, reviewer A's X19 and X20: nothing held either) "THE SCREEN IS AWAKE" IS TAKEN ANYWHERE in what the screen itself said - a late
    // reply's byte in front of it; and THE SCREEN'S DYING WORDS ARE LOOKED FOR IN FRONT OF THE ACTING WORDS: a text that begins with "switch off" and
    // holds the panic handler's words leaves them in the log - and switches nothing off (a screen that is falling over says its acting words again
    // when it is back)
    { ScreenTimeTimer = 0; nowUs += 5000; CHECK(xText("pLDRCAWAKE") && xSaid.empty() && ScreenTimeTimer != 0); }
    { const size_t l0 = logLines.size(); nowUs += 3000000; const bool a1 = xText("Guru Meditation Error: Core 1 panic'ed (LoadProhibited)"); const size_t l1 = logLines.size(); nowUs += 3000000;
      const bool a2 = xText("LDRCOFF Guru Meditation Error: Core 1 panic'ed (LoadProhibited)"); const size_t did = xSaid.size(), l2 = logLines.size();
      say("X2. the dying words alone: answered %d, lines in the log %d; behind 'switch off': answered %d, did %d thing(s), lines in the log %d\n", (int) a1, (int) (l1 - l0), (int) a2, (int) did, (int) (l2 - l1));
      CHECK(a1 && l1 == l0 + 1); CHECK(a2 && did == 0 && l2 == l1 + 1 && logLines.back().find("Guru Meditation") != std::string::npos); }
    // X3. a pipe line is answered HERE, in front of the pages' words - whatever its body holds
    CHECK(xText("ldrctel 1,2,3\n") && xOnly("tel:1,2,3\n"));
    CHECK(xText("ldrcrep 12 200 Mark Clear DelFile GOTO:RXSetupView MainSetup\n") && xOnly("rep:12 200 Mark Clear DelFile GOTO:RXSetupView MainSetup\n"));
    CHECK(xText("ldrctel Mark,StCH,StEDIT\n") && xOnly("tel:Mark,StCH,StEDIT\n"));
    CHECK(xText("ldrctel 1,2,3\npMark 2") && xOnly("tel:1,2,3\n"));                           // (a late answer glued behind: the line is ended at its newline first - OwnWordCut)
    // X4. what is not the screen's own goes on to the pages' words, untouched; a pipe line that does not BEGIN the text is answered where it always was
    for (const char *t : { "Mark 2", "MainSetup", "StCH", "TIME=1731672000", "ldrcpipe=2", "UKRULES", "xLDRCLOG", "ldrcadj", "ldrcrcv", " ldrcrep 12 200 01\n", "Aldrctel 1\n", "ldrc", "DelFile LDRC.MOD" })
    {
        const bool answered = xText(t);
        if (answered || !xSaid.empty()) say("X4. '%s': answered here %d, did %d thing(s)\n", t, (int) answered, (int) xSaid.size());
        CHECK(!answered && xSaid.empty() && !strncmp(TextIn, t, strlen(t)));
    }
    // X5. the screen's own words are looked for in what the screen itself said
    {
        struct { const char *t; bool framed; bool answered; const char *did; } tries[] = {
            { "DelFile LDRCOFF.MOD", true, false, "" }, { "Import LDRCLINK.MOD", true, false, "" }, { "SendModelLDRCWHO.MOD", true, false, "" }, { "CH3NAME=LDRCOFF", true, false, "" },   // a page's framed word: on to the pages' words, untouched
            { "Mark LDRCAWAKE", true, false, "" }, { "GOTO:LDRCRXUP 0 9 870", true, false, "" }, { "HelpView:LDRCIMG.TXT", true, false, "" }, { "x LDRCLOG y", true, false, "" },
            { "ldrcrep 12 200 {\"name\":\"LDRCOFF\"}\n", false, true, "rep:12 200 {\"name\":\"LDRCOFF\"}\n" }, { "ldrctel 25:LDRCLINK\n", false, true, "tel:25:LDRCLINK\n" },                 // a pipe line: answered first, its body not looked at
            { "ldrcrep 3 200 LDRCLOG LDRCWHO LDRCAWAKE LDRCRXUP LDRCIMG\n", false, true, "rep:3 200 LDRCLOG LDRCWHO LDRCAWAKE LDRCRXUP LDRCIMG\n" },
            { "LDRCIMG LDRCOFF", false, true, "img:LDRCIMG LDRCOFF" }, { "LDRCIMG LDRCLINK", false, true, "img:LDRCIMG LDRCLINK" }, { "LDRCRXUP 0 9 870 LDRCOFF", false, true, "rxup:LDRCRXUP 0 9 870 LDRCOFF" },   // the words that act: at the head only
            { "DelFile LDRCOFF.MOD", false, false, "" }, { "xLDRCOFF", false, false, "" }, { "Import LDRCLINK.MOD", false, false, "" }, { "pLDRCRXUP 0 9 870", false, false, "" }, { "Yak LDRCIMG", false, false, "" },   // (a screen that frames nothing)
            { "LDRCOFF", true, true, "" }, { "LDRCLINK", true, true, "" }, { "LDRCWHO", true, true, "" }, { "LDRCAWAKE", true, true, "" },      // framed, at the head: no page prints such a word - it goes no further, and nothing is done
            { "LDRCAWAKELDRCWHO", false, true, "who" }, { "pLDRCWHO", false, true, "who" } };                                                // (two words read as one, a late reply in front: "who are you" is still answered)
        int wrong = 0;
        for (auto &q : tries)
        {
            ScreenTimeTimer = 0; nowUs += 5000;
            const bool answered = xText(q.t, q.framed);
            const bool ok = answered == q.answered && (*q.did ? xOnly(q.did) : xSaid.empty()) && (answered || !strncmp(TextIn, q.t, strlen(q.t))) && (q.framed ? ScreenTimeTimer == 0 : true);
            if (!ok) { ++wrong; say("X5. '%s' (%s): answered here %d, did %d thing(s)%s%s\n", q.t, q.framed ? "a page's framed word" : "bare", (int) answered, (int) xSaid.size(), xSaid.empty() ? "" : ": ", xSaid.empty() ? "" : xSaid[0].c_str()); }
            CHECK(ok);
        }
        say("X5. %d texts with one of the screen's own words inside: wrongly answered %d\n", (int) (sizeof tries / sizeof tries[0]), wrong);
    }
    say("X. the screen's own words: a text that begins LDRC and is no whole word goes no further; a pipe line is answered in front of the pages' words\n");
'''
if __name__ == '__main__':
    sys.exit(lib.build_run('own_words', SCENES, extra=EXTRA))
