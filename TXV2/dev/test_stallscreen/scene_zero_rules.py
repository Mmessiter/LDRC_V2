#!/usr/bin/env python3
"""THE READERS' SMALL RULES, EACH HELD BY ITSELF (the eleventh review, reviewer A's break-it round: eight of them could be taken out of Nextion.h
with every test still passing - and "the 0 must stand right in front" held in one reader of three). The bytes are said by hand to a screen that
is deaf, and the REAL readers read them: StashPendingEventBytes (what a wait finds on the wire), GetTextIn (the main loop's read), CollectReply
(a get's wait), TakeScreenMark, StashFrame, StashFramed, TrailingReplies.
 "IT HAS STARTED AGAIN" is said by the screen: 0 for its session's number, RIGHT IN FRONT of the number it says back (ScreenEchoBehindZero).
  Z0  a whole value reply of 0, then the number said back: the 0 stood right in front (the rule itself)
  Z9  a value reply of 0 that was CUT (no end): it is no whole reply - not in front
  Za  a FRAMED burst between the 0 and the number (a page's own print, a press) - read by a wait, and read by the main loop: not in front
  Zb  another frame between them (a button's code): not in front
  Z2  a bare word between them, read by the main loop: not in front
  Z1  ONE bare read that holds a word, the 0 and the number: the 0 stood right in front - and with another number there, or none, not
  Z3  a 0 read before a get's wait began; the number comes during the wait: not in front
 THE PAGE'S NUMBER behind a word of the screen's own is taken only when one is DUE (P4): a stray "which page?" answer of the page before is not
 the new page's number.  THE NUMBER SAID BACK does not say "the session's number was said" (S4).
 A PAGE COMMAND FROM INSIDE A GET'S RADIO TURN (O8): what stood open in this get's wait is let go - the page command's own reading wrote over it.
  (This scene runs the moment - four bytes standing open, the box's "Yes" written over them, their end coming in - on a screen that frames and on
  one that never did: no answer for the get, nothing kept, nothing obeyed twice. It does NOT tell the rule from its absence: without "let go" the
  frame that closes is a press read between a page command and its marker, which Nextion.h lets go anyway, and the get has no answer because its
  page went. The rule is a second fence behind those two; the break-it list names it as such.)
 THE LIBRARY'S OWN WORDS (N; reviewer A's finding 2 and his experiment 8): a field screen's Bluetooth library says lines of its own straight to the
 wire with the ROM's printf (dev/test_stalepress LIB_WORDS pins them). Said bare, each is let go as "an unframed word" and the answer it makes this
 board owe is caught up; a text box asked right behind it is answered when the half second is over; glued in front of a box's answer it costs that
 answer - "no answer", never another text; and nothing is taken for the screen's restart. (A screen from 1.11.198 on keeps them to itself.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
EXTRA = r'''
static std::vector<uint8_t> q9(uint32_t v) { return { 'q', (uint8_t) v, (uint8_t) (v >> 8), (uint8_t) (v >> 16), (uint8_t) (v >> 24), 0xFF, 0xFF, 0xFF }; }
static std::vector<uint8_t> framed9(const char *w) { std::vector<uint8_t> v = { 0x7E, 0x7E, (uint8_t) strlen(w), 0 }; v.insert(v.end(), w, w + strlen(w)); return v; }
static void wire9(const std::vector<uint8_t> &b) { screen.emit(nowUs + 100, b); delayMicroseconds(1500 + 100 * (int) b.size()); }   // the bytes are on the wire, all of them
static void quiet9()   // Model options up; from here the screen says only what the scene says by hand; this board's own catching-up is held
{
    more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900); screen.deaf = true; holdCatchUp = true;
    ScreenEcho = SCREEN_ECHO_BASE | 0x2345; ScreenSaidEcho = false; ScreenEchoBehindZero = false; ScreenZeroJustSaid = false;
}
static bool echo9(void (*reader)())   // the number said back, read by `reader`: did a 0 stand right in front of it?
{
    ScreenSaidEcho = false; ScreenEchoBehindZero = false;
    wire9(q9(ScreenEcho)); reader();
    return ScreenSaidEcho && ScreenEchoBehindZero;
}
static void byWait() { StashPendingEventBytes(); }
static void byLoop() { GetTextIn(); }
static int o8Step = 0, o8Calls = 0, o8OnWire = -1;
static void o8Hook()   // from inside a get's radio turn: a box is put up (a page command) - and its own look for a press reads the wire THROUGH TextIn
{
    ++o8Calls;
    if (o8Step == 1 && o8Calls == 2)
    {   // the radio's FIRST turn inside the get's wait (the call before it was the send's own wait): four bytes of something are on their way -
        // they come in just before the NEXT turn, 20 ms on, and stand open in the wait when it begins
        for (int i = 0; i < 4; ++i) screen.emit(nowUs + 18400 + (uint64_t) i * 400, { (uint8_t) (i ? 0x00 : 0xC1) });
        o8Step = 2;
        return;
    }
    if (o8Step != 2) return;
    o8Step = 3; o8OnWire = (int) NEXTION.available();
    SendCommand((char *) "page FrontView");
    TextIn[0] = (char) 0x81; TextIn[1] = TextIn[2] = TextIn[3] = 0;   // (what that look left in TextIn: the box's own "Yes", which it has obeyed)
    screen.emit(nowUs + 100, END9);                                    // ... and the end of what stood open comes in during this turn
}
'''
SCENES = r'''
    // Z0. the rule itself, in each of the two readers
    quiet9(); wire9(q9(0)); byWait(); CHECK(ScreenZeroJustSaid); CHECK(echo9(byWait));
    quiet9(); wire9(q9(0)); byWait(); CHECK(echo9(byLoop) || true);                    // (the main loop reads a value reply frame by frame, as a wait does: either way)
    quiet9(); wire9(q9(5)); byWait(); CHECK(!ScreenZeroJustSaid && !echo9(byWait));    // (a value that is not 0 is no 0)
    quiet9(); CHECK(!echo9(byWait));                                                   // (the number alone)
    // Z9. a value reply of 0 CUT before its end ("q" and four zeros, and nothing more): no whole reply
    quiet9(); wire9({ 'q', 0, 0, 0, 0 }); delayMicroseconds(6000); byWait();
    say("Z9. 'q 0 0 0 0' with no end, read by a wait: 'a whole 0 was just said' %d\n", (int) ScreenZeroJustSaid);
    CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    // Za. a FRAMED burst between the 0 and the number said back - read by a wait (StashFramed) ...
    quiet9(); wire9(q9(0)); byWait(); CHECK(ScreenZeroJustSaid);
    wire9(framed9("ldrcadj")); byWait();
    say("Za. a 0, then a framed burst read by a wait: 'a whole 0 was just said' %d\n", (int) ScreenZeroJustSaid);
    CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    //     ... and by the main loop (GetTextIn's framed branch)
    quiet9(); wire9(q9(0)); byWait(); CHECK(ScreenZeroJustSaid);
    wire9(framed9("ldrcadj")); byLoop();
    say("Za. a 0, then a framed burst read by the main loop: 'a whole 0 was just said' %d (the burst read: framed %d, '%s')\n", (int) ScreenZeroJustSaid, (int) TextInFramed, TextIn);
    CHECK(TextInFramed && !strcmp(TextIn, "ldrcadj"));                                 // (the scene is the one meant: the burst went through that branch)
    CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    // Zc (the twelfth review, reviewer A's B32 and his finding 8). A PAGE'S MARKER between the 0 and the number said back: the 0 does not stand right in
    //     front - read frame by frame (StashFrame: it never passed over one, and no test held that) ...
    quiet9(); wire9(q9(0)); byWait(); CHECK(ScreenZeroJustSaid);
    wire9(q9(SCREEN_MARK_BASE | 0x0777)); byWait();
    say("Zc. a 0, then a page's marker read by a wait: 'a whole 0 was just said' %d\n", (int) ScreenZeroJustSaid);
    CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    //     ... and in ONE bare read behind a word (TrailingReplies: it took the marker out, and the number then stood behind the 0)
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false;
    wire9(cat9({ by9("UKRULES"), q9(0), q9(SCREEN_MARK_BASE | 0x0777), q9(ScreenEcho) })); byLoop();
    say("Zc. one bare read 'UKRULES' + 0 + a page's marker + the number said back: said %d, a 0 right in front %d\n", (int) ScreenSaidEcho, (int) ScreenEchoBehindZero);
    CHECK(ScreenSaidEcho && !ScreenEchoBehindZero);
    //     ... the same with the page's number behind the marker (thirteen bytes taken out)
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false;
    wire9(cat9({ by9("UKRULES"), q9(0), q9(SCREEN_MARK_BASE | 0x0777), PAGE9, q9(ScreenEcho) })); byLoop();
    CHECK(ScreenSaidEcho && !ScreenEchoBehindZero);
    //     ... and two numbers said back one behind the other, the 0 in front of the first: the first stands behind it, the second does not
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false;
    wire9(cat9({ by9("UKRULES"), q9(0), q9(ScreenEcho) })); byLoop(); CHECK(ScreenSaidEcho && ScreenEchoBehindZero);
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false;
    wire9(cat9({ by9("UKRULES"), q9(0), q9(SCREEN_ECHO_BASE | 0x1111), q9(ScreenEcho) })); byLoop(); CHECK(ScreenSaidEcho && !ScreenEchoBehindZero);
    // Zb. a button's code between them
    quiet9(); wire9(q9(0)); byWait(); wire9({ 0x81, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF }); byWait(); CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    // Z2. a bare word between them, read by the main loop (TrailingReplies' last line)
    quiet9(); wire9(q9(0)); byWait(); CHECK(ScreenZeroJustSaid);
    wire9(by9("UKRULES")); delayMicroseconds(6000); byLoop();
    say("Z2. a 0, then a bare word read by the main loop ('%s'): 'a whole 0 was just said' %d\n", TextIn, (int) ScreenZeroJustSaid);
    CHECK(!strncmp(TextIn, "UKRULES", 7));                                             // (the word went through the main loop's bare read)
    CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    // Z1. ONE bare read: a word, the 0, the number said back - the 0 inside it counts ...
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false;
    wire9(cat9({ by9("UKRULES"), q9(0), q9(ScreenEcho) })); byLoop();
    say("Z1. one bare read 'UKRULES' + 0 + the number said back: said %d, a 0 right in front %d\n", (int) ScreenSaidEcho, (int) ScreenEchoBehindZero);
    CHECK(ScreenSaidEcho && ScreenEchoBehindZero);
    //     ... a 5 there does not, nor does no number at all
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false; wire9(cat9({ by9("UKRULES"), q9(5), q9(ScreenEcho) })); byLoop(); CHECK(ScreenSaidEcho && !ScreenEchoBehindZero);
    quiet9(); ScreenSaidEcho = false; ScreenEchoBehindZero = false; wire9(cat9({ by9("UKRULES"), q9(ScreenEcho) })); byLoop(); CHECK(ScreenSaidEcho && !ScreenEchoBehindZero);
    //     ... and what follows such a read does not stand behind ITS 0 either (the flag is put back at the read's end)
    quiet9(); wire9(cat9({ by9("UKRULES"), q9(0), q9(SCREEN_MARK_BASE | 0x0777) })); byLoop(); CHECK(!ScreenZeroJustSaid); CHECK(!echo9(byWait));
    // Z3. a 0 read BEFORE a get's wait began; the number said back comes during that wait: the 0 did not stand right in front of it
    quiet9(); wire9(q9(0)); byWait(); CHECK(ScreenZeroJustSaid);
    { ScreenSaidEcho = false; ScreenEchoBehindZero = false; screen.emit(nowUs + 3000, q9(ScreenEcho));
      uint16_t k = 0; NextionReplyWaitMs = 30; (void) CollectReply('q', k); NextionReplyWaitMs = 100;
      say("Z3. a 0, then a get's wait in which the number said back comes: said %d, a 0 right in front %d\n", (int) ScreenSaidEcho, (int) ScreenEchoBehindZero);
      CHECK(ScreenSaidEcho && !ScreenEchoBehindZero); }
    // P4. THE PAGE'S NUMBER BEHIND A WORD IS TAKEN ONLY WHEN ONE IS DUE. A page command has gone out (this board does not know the new page's number
    //     yet, and none is due before the second marker): a stray "which page?" answer - the page BEFORE's, 9 - glued behind a word of the screen's own
    quiet9(); ScreenPageId = 0xFF; ScreenPageIdDue = false;
    wire9(cat9({ by9("UKRULES"), { 0x66, 9, 0xFF, 0xFF, 0xFF } })); byWait();
    say("P4. 'UKRULES' with a page's number (9) glued behind it, none due: the page's number is now %u\n", (unsigned) ScreenPageId);
    CHECK(ScreenPageId == 0xFF);
    quiet9(); ScreenPageId = 0xFF; ScreenPageIdDue = true;                             // ... and when one is due, it is taken
    wire9(cat9({ by9("UKRULES"), { 0x66, 9, 0xFF, 0xFF, 0xFF } })); byWait(); CHECK(ScreenPageId == 9);
    //     ... and a word of the screen's own that merely ENDS like a page's number - 66 is the letter f: "... all off!" - is handed on WHOLE when
    //     none is due (the seventh review: a line ending "...off" and one more byte lost its last two bytes when this rule was not held to "one is due")
    quiet9(); ScreenPageId = 0xFF; ScreenPageIdDue = false; screenLogLines.clear();
    wire9(cat9({ by9("LDRCLOG all off!"), END9 })); byWait(); CHECK(PendingCount == 1);
    for (int i = 0; i < 40; ++i) { LoopPass(); nowUs += 500; }
    say("P4. the screen's line 'LDRCLOG all off!' with its end, no page's number due: handed on as '%s'\n", screenLogLines.empty() ? "(nothing)" : screenLogLines.back().c_str());
    CHECK(screenLogLines.size() == 1 && screenLogLines.back() == "LDRCLOG all off!");
    // S4. THE NUMBER SAID BACK is not the session's number: "its session's number has been said" is set by that number alone
    quiet9(); ScreenSaidSession = false; ScreenSession = SCREEN_MARK_BASE; ScreenSession = (SCREEN_ECHO_BASE & 0xFFFF0000UL) - 0x00010000UL + 0x0456;   // (4C46....: the restart's number kind)
    { ScreenSaidEcho = false; wire9(q9(ScreenEcho)); byWait();
      say("S4. the number said back read: 'said back' %d, 'the session's number said' %d\n", (int) ScreenSaidEcho, (int) ScreenSaidSession);
      CHECK(ScreenSaidEcho && !ScreenSaidSession);
      wire9(q9(ScreenSession)); byWait(); CHECK(ScreenSaidSession); }
    // O8. A PAGE COMMAND FROM INSIDE A GET'S RADIO TURN. A box's answer is awaited (2 s); four bytes of something come in and STAND OPEN in this
    //     get's wait (no end yet); the radio's turn puts a box up (a page command) whose own look for a press reads the wire through TextIn and
    //     leaves the box's "Yes" there - which that look has obeyed; the end of what stood open comes in during that turn. What stood open is LET
    //     GO: counted on, the four bytes now in TextIn - the "Yes" - and that end made a press of their own: kept, to be obeyed a second time
    for (int framing = 1; framing >= 0; --framing)
    {
      more(); screen.realUart = true; tapAt(5, "setup"); loopFor(900); screen.deaf = true; holdCatchUp = true; obeyed.clear(); ghosts.clear();
      if (!framing) ScreenFramesBursts = false;                                          // (... and from a screen that has never framed, which may say a bare code)
      const int pend0 = PendingCount;
      o8Step = 1; o8Calls = 0; o8OnWire = -1; flyHook = o8Hook;
      const uint32_t v = GetValue((char *) "n3"); flyHook = nullptr;
      const int kept = PendingCount - pend0;
      int yes = 0; for (int i = 0; i < 400; ++i) { LoopPass(); nowUs += 500; } for (int c : obeyed) yes += c == 1;
      say("O8 (%s). a page command and a box's own read from inside a get's radio turn, four bytes standing open: the get gave %lu; frames kept from that wait %d; the box's 'Yes' obeyed again %d time(s); step %d\n",
          framing ? "a screen that frames" : "one that never framed", (unsigned long) v, kept, yes, o8Step);
      CHECK(o8Step == 3 && o8OnWire == 0);                                               // (the scene is the one meant: the four bytes had been read, and stood open, when the page command went out)
      CHECK(v == 65535);                                                                 // the get has no answer (its page went)
      CHECK(kept == 0);                                                                  // nothing of what stood open is kept as a press
      CHECK(yes == 0);
      ScreenFramesBursts = true;
    }
    // N. the Bluetooth library's own lines, as they stand in its source (with what it puts in for %s and %d)
    { static const char *said[6] = { "Host not enabled. Dropping the packet!", "Received HCI data length at host (300) exceeds maximum configured HCI event buffer size (255).",
                                     "Failed to allocate buffer, retrying\n", "ble_hci_trans_hs_cmd_tx failed to os_mbuf_append; rc = 6\n", "assertion:rc == 0\n", "line:231,function:host_rcv_pkt\n" };
      int wrong = 0, restarts = 0, answered = 0, refused = 0, glued = 0;
      for (int form : { 197, 198 })
        for (const char *w : said)
        {
            more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(900); ghosts.clear();
            screen.emit(nowUs + 1000, by9(w)); loopFor(60);
            { char tx[20] = "x"; const uint32_t lost0 = BoxesLost; (void) GetText((char *) "t10", tx, sizeof tx);
              if (BoxesLost != lost0) ++refused; else if (!strcmp(tx, "3.50")) ++answered; else ++wrong; }
            loopFor(2500); restarts += restartsFoundByAsking + restartsHandled; CHECK(!ScreenAnswerOwed && screen.page == "RXOptionsView");
            // ... and glued in front of a text box's answer (the pipe taken down in the moment a box is read)
            more(); screen.realUart = true; screen.shoutForm = form; tapAt(5, "setup"); loopFor(900);
            screen.mute.insert("t10"); screen.emit(nowUs + 60000, cat9({ by9(w), by9("p3.50"), END9, PAGE9 }));
            { char t2[20] = "x"; const uint32_t lost1 = BoxesLost; (void) GetText((char *) "t10", t2, sizeof t2); screen.mute.clear();
              if (BoxesLost != lost1) ++glued; else if (strcmp(t2, "3.50")) ++wrong; }
            loopFor(3000); restarts += restartsFoundByAsking + restartsHandled;
        }
      say("N. the Bluetooth library's six lines, bare, on both kinds of screen: a text box asked 60 ms behind one answered %d, refused %d; glued in front of an answer: no answer %d; WRONG TEXTS %d; restarts 'found' %d\n", answered, refused, glued, wrong, restarts);
      CHECK(wrong == 0 && restarts == 0 && answered + refused == 12 && answered >= 8); }
'''
sys.exit(lib.build_run('zero_rules', SCENES, EXTRA, sanitize=False))
