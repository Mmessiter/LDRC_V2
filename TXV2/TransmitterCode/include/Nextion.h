#include <Arduino.h>
#include "1Definitions.h"
#ifndef NEXTION_H
#define NEXTION_H

/*********************************************************************************************************************************/
//                        NEXTION functions
/*********************************************************************************************************************************/
void StashPendingEventBytes(); // (below)
void GetReturnCode(char *tbox)
{
    CRUMB(CRUMB_RETURNCODE);
    // B162: this screen sends no return codes, so what this drained after every command was a button pressed just then -
    // its code or word read and thrown away, the press dead. Now such a press is kept for GetButtonPress, frame by frame;
    // debris (a return code, a late reply to a get) is still let go (StashFrame).
    StashPendingEventBytes();
}
/*********************************************************************************************************************************/
void ClearNextionCommand()
{
    strcpy(NextionCommand, "");
}
/*********************************************************************************************************************************/
void BuildNextionCommand(char *cmd) // these strings can be <= 255 bytes but here we limit to 127 to avoid delays etc.
{
    if (strlen(NextionCommand) + strlen(cmd) + 3 >= MAXNEXTIONCOMMANDLENGTH) // If too long, send what we have and start building again.
    {
        SendCommand(NextionCommand);
        ClearNextionCommand();
    }
    if (strlen(NextionCommand) > 0)
        strcat(NextionCommand, "\xFF\xFF\xFF"); // add ending beforehand if this is not  first
    strcat(NextionCommand, cmd);
}

/*********************************************************************************************************************************/
void BuildValue(char *nbox, int value)
{ // Same as SendValue only delayed send
    char Val[] = ".val=";
    char CB[100];
    char NB[25];
    strcpy(CB, nbox);
    strcat(CB, Val);
    strcat(CB, Str(NB, value, 0));
    BuildNextionCommand(CB);
}
/*********************************************************************************************************************************/
// ClaudeFix-2-7-2026 Bounded, sanitising copy for anything sent inside a Nextion txt="..."
// assignment. Two characters are LETHAL in there: an embedded double quote
// terminates the string so the display SILENTLY REJECTS the whole command
// (the frozen-help-screen bug), and a 0xFF byte ends the command early,
// letting the remaining bytes execute as a NEW command (injection from
// garbage telemetry). maxroom includes the terminating NUL. CR/LF pass
// through (the log viewer needs them).
void CopyTextForNextion(char *dst, const char *src, uint16_t maxroom)
{
    uint16_t i = 0;
    while (src[i] && (i + 1) < maxroom)
    {
        char c = src[i];
        if (c == '"')
            c = '\'';
        if ((uint8_t)c >= 0xFE)
            c = ' ';
        dst[i] = c;
        ++i;
    }
    dst[i] = 0;
}
/*********************************************************************************************************************************/
void BuildText(char *tbox, char *NewWord) // same as sendtext only delayed send
{
    char CB[120];
    // ClaudeFix-2-7-2026 The old cap forgot the name + ".txt=\"" + quote overhead (and replaced
    // the CALLER's buffer with "Too long!") -- truncate safely instead.
    strcpy(CB, tbox);
    strcat(CB, ".txt=\"");
    uint16_t used = strlen(CB);
    CopyTextForNextion(CB + used, NewWord, (uint16_t)(sizeof(CB) - used - 2));
    strcat(CB, "\"");
    BuildNextionCommand(CB);
}


/*********************************************************************************************************************************/
void SendText1(char *tbox, char *NewWord)
{
    char CB[2048];
    strcpy(CB, tbox);
    strcat(CB, ".txt=\"");
    uint16_t used = strlen(CB);
    CopyTextForNextion(CB + used, NewWord, (uint16_t)(sizeof(CB) - used - 2));
    strcat(CB, "\"");
    SendCommand(CB);
    GetReturnCode(tbox);
}
/*********************************************************************************************************************************/
void SendText(char *tbox, char *NewWord)
{
    SendText1(tbox, NewWord);
}

/*********************************************************************************************************************************/
void SendOtherText(char *tbox, char *NewWord)
{
    char CB[MAXBUFFERSIZE];
    strcpy(CB, tbox); // ClaudeFix-2-7-2026 tbox carries its own prefix incl. the opening quote
    uint16_t used = strlen(CB);
    CopyTextForNextion(CB + used, NewWord, (uint16_t)(sizeof(CB) - used - 2));
    strcat(CB, "\"");
    // ClaudeFix-14-7-2026 Send BIG commands in paced chunks. The models list is ~1.6 KB in
    // ONE command; blasted at 921600 while the display is still redrawing
    // (e.g. rendering the model image) it overruns the display's RX buffer
    // and is silently dropped -- the freshly imported model then never
    // appeared in the list until a second attempt.
    uint16_t len = strlen(CB);
    for (uint16_t i = 0; i < len; i += 64)
    {
        uint16_t n = (uint16_t)(len - i);
        if (n > 64)
            n = 64;
        NEXTION.write((uint8_t *)CB + i, n);
        NEXTION.flush();
        delayMicroseconds(800); // let the display's parser drain the chunk
        KickTheDog();
    }
    EndSend();
    GetReturnCode(tbox);
}

/*********************************************************************************************************************************/
void SendOtherValue(char *nbox, int value)
{
    char Val[] = "=";
    char CB[100];
    char NB[25];
    strcpy(CB, nbox);
    strcat(CB, Val);
    strcat(CB, Str(NB, value, 0));
    SendCommand(CB);
    ValueSent = true;
    GetReturnCode(nbox);
}

/*********************************************************************************************************************************/
// ClaudeFix-14-7-2026 The Nextion sends UNSOLICITED touch-event strings ("Import x.MOD",
// "Yes", ...) into the same serial buffer as get-replies. The 2-7 fix flushed
// that buffer before every get -- which DESTROYED any button press that was
// waiting there (the restore button needed 2-3 presses). Instead of discarding,
// printable bytes are rescued here and served to GetButtonPress afterwards.
// (Return-code debris -- 0x01/0x1A + FF FF FF -- is non-printable and still dropped.)
#define MAXPENDINGFRAME 512
#define MAXPENDINGFRAMES 8
#define SCREEN_READ_MOST 4096     // B211: the most bytes one read of the wire takes in (StashPendingEventBytes): the port's buffer, 44 ms of the screen talking flat out
#define SCREEN_READ_LONGEST_MS 40 // ... and the longest the main loop's read of a word goes on (GetTextIn): the chip's whole panic text is some 25 ms
char PendingEvent[MAXPENDINGFRAME];     // the frames kept for GetButtonPress, one after another (B177: 512 - a framed burst can be long)
uint16_t PendingEventLen = 0;
bool TextInWasStashed = false; // B163: the frame in TextIn came from PendingEvent (set aside by a get window or a send), not a read of the port
uint16_t PendingLens[MAXPENDINGFRAMES]; // B177: each kept frame's length, so that GetButtonPress serves them one at a time ...
bool PendingFramedFlags[MAXPENDINGFRAMES]; // ... and whether it came framed
uint8_t PendingCount = 0;

// B177 (Malcolm, 4 Nov 2026: the Sounds page's switches "spontaneously turned off", the volume with them; the front page came
// up by itself from the log page and others; 31 Oct's volume zero): THE SCREEN'S BURSTS ARE FRAMED. A page's event prints
// its bytes raw - a button's code, or several numbers at once (the log page's lift prints its code, where it is scrolled to
// and how far it can go: twelve bytes). The screen sends an event's output in one write, but its serial port is fed by an
// interrupt that a busy moment holds back, and a pause of more than 200 us inside the burst ended the frame here
// (GetTextIn): the tail came as a frame of its own and was obeyed as a command. A tail beginning 00 03 00 00 (the log text's
// height, 768) is the 24-bit code 3 = the Sounds page's OK, which then read every box from a page that was not showing
// (the screen answers 0 for a box it has not got): volume 0, the six switches off, the variometer's numbers 0 - exactly the
// bytes that changed in models.dat between the copies kept on 3 Nov at 09:02 and 21:22. A tail whose first byte is 128 or
// more is a 7-bit code: B0 (176) is 48 = GotoFrontView, and most pages' End functions go there too.
// Now a screen told "ldrcframe=1" (screen 1.11.173 and later; sent at this board's start, again when the screen says
// FrontView after its own restart, and when it answers a code unframed) wraps every burst: 7E 7E, two bytes of length (low
// first), the bytes. A framed burst is read to its length - a pause inside it is waited out (20 ms), and what follows is the
// next frame, never glued on (B162) - and once one framed burst has come (ScreenFramesBursts) an UNFRAMED binary frame (a
// split tail, a late reply split from its q) is logged and dropped, never obeyed. Words still pass unframed (the screen's
// own LDRCAWAKE, UKRULES, TIME= and the FrontView it says after a restart). An older screen never frames: nothing changes.
// (B211: once a screen has framed, a PAGE's word that comes unframed is not obeyed either, and this board no longer forgets at
// the screen's restart that the screen frames - TextInIsGenuine, and THE SCREEN'S OWN RESTART below.)
#define FRAME_MARK 0x7E
#define FRAME_GAP_US 20000           // the longest pause waited out inside a framed burst
#define FRAME_MOST 4000              // B211: the longest burst the screen frames (its flushOut): a longer one declared is a damaged length
#define FRAME_LONGEST_MS 100         // ... and the longest one burst is read for (4000 bytes flat out are 44 ms)
bool ScreenFramesBursts = false;     // the screen has framed a burst this session: an unframed binary frame is a ghost
bool TextInFramed = false;           // the frame now in TextIn came framed
uint16_t TextInLen = 0;              // ... and how many bytes it has (B211, the thirteenth review: a burst that carries numbers behind its word - the Sub-trim
                                     //  page's - has zeros among them, and a text's end does not tell its length)
uint32_t FrameEnableSentMs = 0;      // when "ldrcframe=1" was last sent


// B211 (14 Nov 2026; found by reading while a new page was reviewed, then proven on the Mac - dev/test_stalepress):
// A PRESS BELONGS TO THE PAGE IT WAS MADE ON. A button's code that came while this board was busy with the screen is kept
// (PendingPush) and served by the loop afterwards - by then the page may have changed, and the code's function ran on a page
// that was not its own. The screen answers 0 (or "") for a box the showing page has not got: a second tap on Model options'
// OK, a quarter of a second after the first (its boxes take a second to read), ran RXOptionsViewEnd again on the front page
// and SAVED motor switch off, 'stop flying' volts 0, trim step 0, six banks off, the timer 0. Every OK and Save had the
// weakness, the Rotorflight pages' too (139 of the 318 button functions reach a box read).
// Now, with every page command (SendCommand): the presses kept so far go (PurgeKeptPresses), and the screen is asked for
// TWO MARKERS, one just before the page command and one right behind it - "ldrcsync=<number>", "get ldrcsync": every
// screen keeps a name=number, and answers a get in the order the commands came. Nothing waits for them: each is noted
// wherever a value reply is read (TakeScreenMark).
//  - Until the FIRST marker comes, what the screen says was said before it read the page command: the OLD PAGE'S. A press
//    among it is not obeyed (PendingPush, GetButtonPress), and is said in the log.
//  - Between the two markers the screen is putting the new page up. What a page prints by itself AS IT COMES UP comes now,
//    and passes if it is one of the page's own (below); anything else is let go without a word - it is a tap made in the
//    one round of the screen's loop between its answer and its reading of the page command (a storm of random taps on the
//    Mac found that round), or a code a page prints as it comes up and nobody needs: MixesView's "click b22,0" (its boxes
//    as the page file has them), the first tick of the Governor page's timer (the next comes half a second later).
//  - After the SECOND marker, the new page's own.
// A MARKER THAT IS LATE IS OWED (the ninth review, 15 Nov 2026). The wait for a marker used to END after a second and a half
// with the wire empty. A screen whose loop stood still for longer than that with the page command unread - its WiFi, its
// card - then printed the tap made meanwhile on the page it still showed, and the tap was obeyed: on the new page. Model
// options' OK saved its zeros - the very fault all this was written against (found by a run: any stall over 1.5 s).
// A screen that HAS SAID A MARKER BEFORE says this one too, when its loop comes round. So the wait goes on - presses are
// dropped - and the screen is asked to say a number back, as for any answer it owes (ScreenAnswerOwed, further down:
// nothing is asked of it meanwhile, nothing waits). When that number comes back and the marker has not, the marker was
// lost on the wire: the page is up (the number was asked for AFTER the page command) and its number is asked for again.
// Only a screen that has NEVER said a marker - one older than them - has the wait ended after a second and a half; three
// such in a row, and presses are only purged until one comes. And should a marker come AFTER its wait was given up (such
// a screen - one slow to start, say, that says them after all), the boxes of the button's work then in hand have no answer:
// the press that began that work may have been the old page's (TakeScreenMark).
// A PRESS IS A CODE, OR A WORD A PAGE'S BUTTON PRINTED (IsPress). Half the older pages' buttons print a word - the One
// switch page's OK prints "SwitchesView1", and a second tap on it ran ReadNewSwitchFunction on the Switches page: the
// safety switch un-assigned, "reversed" cleared, saved (found by the fourth review, 14 Nov 2026). A page's prints come
// FRAMED (B177); the screen's own words come bare and always pass (LDRCAWAKE, TIME=, LDRCLOG, the pipe's lines, FrontView
// after its restart). Of the framed words, five kinds are never a press and pass at any time (IsPageOwnWord): "ldrcadj",
// "ldrcrcv" (a page asks to be drawn), a typed channel name "CHnNAME=...", "UKRULES", the touch on a background, and the
// Sub-trim page's "done".
// THE BOX'S PAGE (the fifth review, 14 Nov 2026: OK or Send, then a touch on a number box while the boxes are read - the
// SCREEN opens its keyboard page by itself, no page command of this board's, and the rest of the boxes answered 0: motor
// switch off saved; on the PID page, zeros sent). With every get of a page's box the screen is also asked "sendme" - the
// number of the page it is showing - and that number must be the one it gave right behind the last page command's
// second marker (ScreenPageId). Another page (its keyboard; whatever it is) = the box has NO ANSWER, and nor has any box
// after it until this press's work is over (PageChangedUnderGet). And when the screen has STARTED AGAIN (its page's boxes
// are the page file's again) no box has an answer until this board has drawn its page afresh: THE SCREEN'S OWN RESTART,
// further down.
// And ONE is a press that a page also prints as it comes up (IsLoadPrint): "StCH". The Sub-trim page clicks its first
// channel as it loads; between the two markers the word passes, before the first it is a press. (It tells this board
// nothing any more: the page's "StEDIT" says its channel itself - Trims.h. And that page's "done", a burst of "StEDIT"
// and a number twice, is the page's own word: IsPageOwnWord.)
#define SCREEN_MARK_BASE 0x4C440000UL // a marker's number: "LD" and a count - no box holds such a number. This is the first of the two ...
#define SCREEN_MARK_PAGE 0x00010000UL // ... and with this bit, the second (0x4C45....): the page is up - the screen is DONE with the page command (the tenth
                                      // review: a page it could not load - one its card has not got - is answered too: it then shows what it showed, and
                                      // the number it says behind the marker is that page's. Known; nothing tells this board the load failed)
#define SCREEN_MARK_WAIT_MS 1500      // the longest a marker is waited for, the wire empty (a page with a picture is some hundreds of ms in coming up)
#define SCREEN_MARK_MISSES 3          // so many never came, one after another: this screen does not say it
uint32_t ScreenMarkAwaited = 0;       // the last page command's SECOND marker, not back yet (0: none awaited)
bool ScreenMarkOldPage = false;       // ... and nor is its first: what the screen says is still the old page's
uint32_t ScreenMarkAskedMs = 0;       // when it was asked for
uint16_t ScreenMarkCount = 0;         // the count in the last marker asked for (never 0 once one was asked)
uint8_t ScreenMarkMisses = 0;         // the markers that never came, one after another
bool ScreenSaysMarks = false;         // this screen has said a page's marker: one that is late from here on is OWED, not "never" (A MARKER THAT IS LATE IS OWED)
bool ScreenMarkGivenUp = false;       // the last page command's marker was given up - and may come yet (TakeScreenMark)
bool RfSettleAsked = false;           // a Rotorflight page's look before its boxes (RfGatherStart) was really asked: its silence is "never settled", not "was not asked"
bool PageLeftUnderWork = false;       // ... and it was THIS BOARD that put another page up under a button's work (BeforePageCommand): a box that work puts up
                                      // afterwards would go "back" to a page this board is no longer on (RfFieldsMissed)
bool PageChangedUnderGet = false;     // a page command went out while a get waited for its answer (BeforePageCommand), or the screen was found showing
                                      // another page than this board's (BoxPageWrong), or a box's answer never came: until this press's work is over -
                                      // the next look for a press, GetButtonPress - no box has an answer (the page they are on has gone, or may have)
uint8_t ScreenPageId = 0xFF;          // the number of the page the screen put up for the last page command ("sendme" says it; 0xFF: not known)
bool ScreenPageIdDue = false;         // the second marker has come: the next "sendme" answer read is the new page's number
uint16_t ScreenPageUnsaid = 0;        // gets whose "sendme" went unanswered (a screen that has never said its page: the box's answer is used, as it always was)
// THE SCREEN'S KEYBOARD PAGES - the only pages the screen puts up by itself (a touch on a number box). Their numbers are the
// card's (keybdA 56, keybdB 57: dev/test_stalepress reads the card, and fails should they move). One of them is never learned
// as "the page this board put up" (the sixth review, 14 Nov 2026: a number box touched in the round of the screen's loop
// between the page coming up and its "sendme" - the keyboard's number was learned, and once the keyboard had closed every box
// of the page was refused), and a box answered while one of them shows has no answer even while the page's own number is
// not yet known.
#define SCREEN_KEYBOARD_PAGE_A 56
#define SCREEN_KEYBOARD_PAGE_B 57
// ... and the two pages that LOOK AT THEIR OWN BOXES with no button pressed (the Models page's lists, the Dual-rates page's
// channels): each looks only while the page the screen last put up for this board is its own (the ninth review: a box had gone
// back to the front page with a bare page command, this board still believed the Models page - and the front page's "0" for the
// list's row loaded model 1). The card's numbers again: dev/test_stalepress reads the card, and fails should they move.
#define SCREEN_MODELS_PAGE 15
#define SCREEN_DUALRATES_PAGE 31
// ... and THE FRONT PAGE's number (the card's, pinned by dev/test_stalepress as the others are). THE SCREEN SHOWS THE FRONT PAGE AND THIS
// BOARD BELIEVES ANOTHER PAGE (15 Nov 2026, the author's, after the tenth review; released code had it): the front page is put up from
// INSIDE a wait that flies the model - the model connects, the power button while connected, the motor box - and that wait may be the one
// behind another page's own page command: the pilot touched "Models" in the moment his model connected. The opening work then went
// on: its values were written onto the front page (which has parts of the same names), and it set the page this board believes to
// its own. The screen showed a front page that was no longer kept up to date - its numbers standing still, in flight too - until a
// button was pressed. The page's number the screen says behind every page command tells it: the main loop (main.cpp ScreenKeepUp)
// draws the front page afresh, leaving the other page as its own way out leaves it. (A page the screen's card has not got, asked
// for from the front page, ends the same way: the screen stays on the front page and says so.)
#define SCREEN_FRONT_PAGE 13
static bool IsKeyboardPage(uint8_t id)
{
    return id == SCREEN_KEYBOARD_PAGE_A || id == SCREEN_KEYBOARD_PAGE_B;
}
bool ScreenSaysPage = false;          // this screen has answered a "sendme" (every V2 screen does): one that goes unanswered now is not "a screen that cannot say"
uint16_t ScreenPageSaidCount = 0;     // the "sendme" answers read so far (a question that waits counts them: Utilities.h GetYesOrNo)
static void NoteScreenPage(uint8_t id) // a "sendme" answer has been read (66 and the showing page's number)
{
    ScreenSaysPage = true;
    ++ScreenPageSaidCount;
    if (!ScreenPageIdDue || IsKeyboardPage(id))
        return; // (the keyboard is up: the page's own number is learned from the next answer that is not a keyboard's)
    ScreenPageId = id; // the first one after the second marker: said after the page was put up
    ScreenPageIdDue = false;
}
// THE SCREEN'S OWN RESTART (the sixth and seventh reviews, 14 Nov 2026; released code had the fault too). A screen that
// restarts (its watchdog, a panic, an update) comes back on the page it was showing, with the PAGE FILE's values in every
// box, and frames nothing until told again. It says so twice: its power-on bytes (00 00 00 FF FF FF 88 FF FF FF - at EVERY
// start, the first thing its own program says, and a frame with an end), then - unless the power itself came on - the bare
// word "FrontView rst=N", and after a watchdog or a panic the record of what it was doing ("LDRCLOG ...", in parts, 300 ms
// apart), all before it answers anything. The word has no end: read inside a get's wait it was glued to the record behind
// it, and the lump was dropped (too long to keep) or taken for a line of the log - "FrontView" was never obeyed. This board
// then went on believing the page it had drawn: on the Models page its twice-a-second look at the list read the page
// file's row 0, and MODEL 1 WAS LOADED BY ITSELF; and every button's code was dropped as "unframed" until the power went off.
// Now a restart is NOTED wherever it is read - the power-on bytes (StashFrame, GetTextIn), the word at the head of a bare
// frame or "FrontView rst=" anywhere in one - and not kept as a word in the queue (which can be full, or too short for it).
// From that moment, until this board has drawn its page afresh:
//  - NOTHING IS ASKED OF THE SCREEN, and no box has an answer (GetNumberReply, GetText, GetOtherValue);
//  - no press is obeyed (TextInIsGenuine), and a question box that waits is closed as "No" (Utilities.h GetYesOrNo: the
//    screen no longer shows the question);
//  - NOTHING WAITS. The main loop, pass after pass (main.cpp ManageTransmitter), tells the screen a number and asks for it
//    back ("ldrcup=N", "get ldrcup" - again every three seconds: it may not be listening yet) and goes on flying the model
//    and reading the switches. The screen answers in the order it was spoken to, and only once its own start is over: when
//    it says THAT number back it has said all it had to say (its record, each part read by itself and logged whole) and has
//    done all that was said to it while it started - whatever it was asked then has been answered, and let go. Then the
//    front page is drawn afresh (main.cpp ScreenHasRestarted: the framing, the colours, the page).
// At this board's own start the screen's power-on bytes are the common power-on's: nothing to do (ScreenStartupOver).
// (The seventh review: the first form of this ASKED the screen and waited two seconds for its answer, in the main loop - at
// every restart, for the chip's own start-up text is read here as an unframed code - and then waited again for it to catch
// up: the switches unread for seconds, in the air. Nothing of it waits now, and that asking is gone.)
// IS IT STILL THE SAME SCREEN? (the ninth review, 15 Nov 2026.) The number the screen is told after its restart is ITS SESSION'S
// NUMBER: told at this board's own start too (main.cpp ScreenKeepUp), under the name "ldrcup" - and by NOTHING ELSE. A screen
// that has started again says 0 for it until this board, having noted the restart, tells it a new one: so a restart whose
// every sign was lost can be found by asking (ScreenSessionCheck, further down; and every "say this back" asks for it first:
// ScreenEchoTell). It was the last PAGE MARKER that was asked for - which any page command of this board's tells the screen
// anew: after an unnoticed restart the screen saver's own page command made the screen "the same", and the Models page, put
// back as the card has it, loaded model 1 by itself (found by a run). And the number that says "I have caught up" when an
// answer is owed has a name of its own on the screen ("ldrcech") - it was the session's, told afresh each time.
#define SCREEN_SESSION_BASE 0x4C460000UL // the session's number ("LF" and a count): no box holds one, and it is no page's marker
#define SCREEN_ECHO_BASE 0x4C470000UL    // the number the screen says back when it owes an answer ("LG" and a count)
#define SCREEN_TELL_AGAIN_MS 3000        // told, and not said back within so long: told again
#define SCREEN_TELL_LONGEST_MS 30000     // ... and so long after the restart was noted the front page is drawn afresh all the same (a screen that cannot say a number back)
#define SCREEN_SESSION_TRIES 10          // told so often at this board's start with no answer: a screen that says no number back (it is told once a minute from then on)
bool ScreenRestartSeen = false;       // the screen has started again and this board has not yet drawn its page afresh
int8_t ScreenRestartReason = -1;      // the word's rst=N (-1: its word gave none, an older screen; -2: its power-on bytes alone; -3: no sign at all - found by asking)
uint32_t ScreenRestartSeenMs = 0;     // when that was first noted
bool ScreenStartupOver = false;       // this board's own setup() is over
uint32_t ScreenSession = 0;           // the session's number the screen was last told
uint32_t ScreenToldMs = 0;            // ... and when (0: not yet, since the last sign of its restart)
bool ScreenSaidSession = false;       // ... and it has said it back
uint16_t ScreenSessionSaidN = 0;      // how often it has said it (it is asked for again by ScreenSessionCheck, and with every "say this back")
uint8_t ScreenSessionTries = 0;       // told at this board's start (or after a restart that brought no number back) and not said: so many times
uint32_t ScreenSessionNextMs = 0;     // ... and when it is told next
uint8_t ScreenSessionUnsaid = 0;      // asked for with a "say this back", and not said though that number was: so many times running (two: it has started again)
// AN ANSWER THAT NEVER CAME MAY COME YET (the eighth review, 15 Nov 2026; released code had the fault too). The screen answers in
// the order it was asked - when its loop comes round. A loop that stood still for longer than a question's two seconds (no
// restart: nothing says so) leaves that question "MISSING" here, and answers it when it wakes: FIRST, in front of the answer to
// whatever was asked next - so the next question took the old one's answer. On the Models page (its two lists asked for twice a
// second) the files' row was taken for the model's row: A MODEL WAS LOADED BY ITSELF (found by a run: 288 times in 3000 stalls).
// So an answer waited for to the end of its time and not come is OWED, and until the screen has caught up - it is told a number
// and asked for it back, exactly as after its restart, and nothing waits (ScreenCaughtUp, from the main loop) - NOTHING IS ASKED
// OF IT: every box has no answer (BoxesHaveNoPage), a system variable too. What it owed has come by then, and was let go.
bool ScreenAnswerOwed = false;        // an answer was waited for to the end and did not come: nothing is asked until the screen has caught up
uint32_t ScreenOwedSinceMs = 0;       // ... since when
uint32_t ScreenEcho = 0;              // the number it was last told to say back ("ldrcech")
uint32_t ScreenEchoToldMs = 0;        // ... and when (0: not yet, since an answer was last found owed)
bool ScreenSaidEcho = false;          // ... and it has said it back
bool ScreenSessionDoubted = false;    // while an answer is owed: the screen has said a number back and NOT its session's, asked for in front of it
bool ScreenZeroJustSaid = false;      // the frame read last was a whole value reply of 0 (StashFrame, TrailingReplies) ...
bool ScreenEchoBehindZero = false;    // ... and that is what stood right in front of the number said back: its session's number asked for, and 0 said
bool ScreenEchoAskedSession = false;  // in front of that number the screen was asked for its session's, which it had said before ...
uint16_t ScreenEchoSessionN = 0;      // ... and this is how often it had said it when it was asked
uint16_t ScreenEchoMarkCount = 0;     // the last page command's count when that number was told (what was asked BEFORE it has been answered when it comes back)
// (These few are kept OUT OF LINE, in flash: written into the readers that call them, they took a kilobyte and a half of the
// fast memory - which has two left before its next 32 kB block.)
#define B211_RARE FLASHMEM __attribute__((noinline))
B211_RARE static void NoteAnswerOwed();
B211_RARE static void NoteScreenRestart(int8_t reason) // reason: the N of the screen's word; -1 its word without one; -2 its power-on bytes; -3 found by asking (ScreenOwedOver)
{
    if (reason == -2 && !ScreenStartupOver)
        return; // the power came on for both boards: this one draws its pages anyway
    if (reason == -1 && !ScreenRestartSeen && ScreenSaidSession && ScreenMarkMisses < SCREEN_MARK_MISSES)
    { // (the ninth review) ITS WORD ALONE, WITH NO NUMBER: an older screen's - or the TAIL of a line of the screen's own that was cut in two
      // ("... last command 213 ms ago: page " | "FrontView": found by a run - the front page was drawn afresh over whatever the pilot was
      // doing). This screen has said its session's number: so it is ASKED, as when it owes an answer (nothing waits) - and only one that no
      // longer knows that number has started again (ScreenOwedOver). Until then nothing is asked of it, as after any answer owed.
      // (Owed already: it is asked AFRESH - a number it said back before this word was read says nothing about what came after.)
        if (ScreenAnswerOwed)
        {
            ScreenEchoToldMs = 0;
            ScreenSaidEcho = false;
        }
        else
            NoteAnswerOwed();
        return;
    }
    if (!ScreenRestartSeen)
    {
        ScreenRestartSeen = true;
        ScreenRestartReason = reason;
    }
    else if (reason >= 0 || ScreenRestartReason == -2)
        ScreenRestartReason = reason; // (the word's reason is not replaced by "its power-on bytes" - a second start's, say)
    ScreenRestartSeenMs = millis(); // (its half minute is counted from the LAST sign: a second start, 29 s after the first, was given one second)
    ScreenToldMs = 0; // whatever it was told before this sign: it is told, and asked, afresh - its answer then comes behind all it has to say
    ScreenSaidSession = false;
    ScreenSessionTries = 0;
    ScreenSessionUnsaid = 0;
}
B211_RARE static void NoteAnswerOwed() // an answer was waited for to the end of its time, and did not come (AN ANSWER THAT NEVER CAME MAY COME YET, above)
{
    if (ScreenAnswerOwed || ScreenMarkMisses >= SCREEN_MARK_MISSES)
        return; // (a screen that says no number back - older than the markers - cannot be waited for: with it, all is as it always was)
    ScreenAnswerOwed = true;
    ScreenOwedSinceMs = millis();
    ScreenEchoToldMs = 0; // told a number, and asked for it, afresh: its answer comes behind all that is owed
    ScreenSaidEcho = false;
    ScreenSessionDoubted = false;
    ScreenSessionUnsaid = 0;
}
FLASHMEM void ScreenOwesAnswer() { NoteAnswerOwed(); } // (for Utilities.h, which comes before this file)
FLASHMEM void ScreenAskPage() { NEXTION.print("sendme\xFF\xFF\xFF"); } // "which page are you showing?" - and nothing waits for the answer (a question that waits asks it once a second)
// The screen is told a number and asked to say it back. NOTHING WAITS for the answer: it is noted wherever a value reply is
// read (TakeScreenMark). Its session's number - after its restart, and at this board's start:
FLASHMEM void ScreenSessionTell()
{
    static uint16_t count = 0;
    count = ScreenCountAfter(count); // (never 0; the first from the clock: Utilities.h)
    ScreenSession = SCREEN_SESSION_BASE | count;
    ScreenSaidSession = false;
    ScreenToldMs = millis();
    if (!ScreenToldMs)
        ScreenToldMs = 1;
    char m[48];
    snprintf(m, sizeof(m), "ldrcup=%lu\xFF\xFF\xFFget ldrcup\xFF\xFF\xFF", (unsigned long)ScreenSession);
    NEXTION.print(m);
}
// ... and when it OWES an answer: "say this back" - and, in front of it, "say your session's number" (when it has said one
// before): that number NOT said, and this one said, is a screen that has started again with every sign of it lost
// (ScreenOwedOver).
B211_RARE static void ScreenEchoTell()
{
    static uint16_t count = 0;
    count = ScreenCountAfter(count); // (never 0; the first from the clock: Utilities.h)
    ScreenEchoAskedSession = ScreenSaidSession; // (it has said its session's number before: it is asked for it in front of this one)
    ScreenEchoSessionN = ScreenSessionSaidN;
    ScreenEcho = SCREEN_ECHO_BASE | count;
    ScreenEchoMarkCount = ScreenMarkCount;
    ScreenSaidEcho = false;
    ScreenEchoBehindZero = false;
    ScreenEchoToldMs = millis();
    if (!ScreenEchoToldMs)
        ScreenEchoToldMs = 1;
    char m[64];
    snprintf(m, sizeof(m), "%sldrcech=%lu\xFF\xFF\xFFget ldrcech\xFF\xFF\xFF", ScreenEchoAskedSession ? "get ldrcup\xFF\xFF\xFF" : "", (unsigned long)ScreenEcho);
    NEXTION.print(m);
}
// The main loop's question, pass after pass, while a restart is noted or an answer is owed: has the screen caught up - has it
// said back the number it was last told? It never waits: not yet told, or told three seconds ago without an answer - told
// (again), and "not yet".
B211_RARE static bool ScreenCaughtUp()
{
    if (ScreenRestartSeen)
    {
        if (ScreenSaidSession)
            return true;
        if ((millis() - ScreenRestartSeenMs) > SCREEN_TELL_LONGEST_MS)
            return true; // (half a minute and no number back: a screen that cannot say one is not waited for for ever)
        if (!ScreenToldMs || (millis() - ScreenToldMs) > SCREEN_TELL_AGAIN_MS)
            ScreenSessionTell();
        return false;
    }
    if (ScreenSaidEcho)
        return true;
    if ((millis() - ScreenOwedSinceMs) > SCREEN_TELL_LONGEST_MS)
        return true;
    if (!ScreenEchoToldMs || (millis() - ScreenEchoToldMs) > SCREEN_TELL_AGAIN_MS)
        ScreenEchoTell();
    return false;
}
// This board has started (or the screen's restart went by with no number said back): the screen is told its session's number
// until it says it - ten times three seconds apart, then once a minute (a screen older than all this never will).
B211_RARE static void ScreenSessionAtStart()
{
    if (ScreenSaidSession || !ScreenStartupOver)
        return;
    ScreenSessionNextMs = millis() + (ScreenSessionTries < SCREEN_SESSION_TRIES ? SCREEN_TELL_AGAIN_MS : 60000UL);
    if (ScreenSessionTries < 255)
        ++ScreenSessionTries;
    ScreenSessionTell();
}
// ... AND WHILE A QUESTION BOX WAITS (the tenth review, 15 Nov 2026; released code had the fault): the screen is showing the box's page -
// PopupView - and that IS the page of this board's last page command, so the box's-page check passes. A page's own word that is no press
// ("ldrcadj": the Switches-and-knobs page says it as it comes up) outlives the page commands and was served inside the question's wait:
// its routine gathered the row's fields from the box's page - "" for each, made 0: a knob 20 to 80 became 0 to 0. Nothing reads a page's
// boxes rightly from inside a question's wait: they have no answer there (and such a word is not obeyed there: main.cpp).
static bool BoxesHaveNoPage() // no box has an answer: the page they are on has gone (PageChangedUnderGet), the screen has started again, it owes an answer, or a question waits
{
    return PageChangedUnderGet || ScreenRestartSeen || ScreenAnswerOwed || ModalWaits != 0;
}
// The screen's word after its restart, in a frame that came BARE (a page's prints come framed): at the frame's head (an older
// screen says "FrontView" alone), or "FrontView rst=" anywhere in it - behind what the page it put back printed as it came up,
// say. Where it begins, or -1. (The record's own text never holds "FrontView rst=": it lists this board's commands.)
B211_RARE static int RestartWordAt(const uint8_t *f, uint16_t n)
{
    if (n >= 9 && !memcmp(f, "FrontView", 9))
        return 0;
    for (uint16_t i = 1; i + 14 <= n; ++i)
        if (f[i] == 'F' && !memcmp(f + i, "FrontView rst=", 14))
            return (int)i;
    return -1;
}
B211_RARE static int8_t RestartReasonAt(const uint8_t *w, uint16_t n) // w: at the word; the N of " rst=N" behind it, or -1
{
    if (n < 15 || memcmp(w + 9, " rst=", 5) != 0)
        return -1;
    int v = 0;
    uint16_t i = 14;
    for (; i < n && i < 17 && w[i] >= '0' && w[i] <= '9'; ++i)
        v = v * 10 + (w[i] - '0');
    return i > 14 ? (int8_t)v : -1;
}
B211_RARE static int RestartRecordAt(const uint8_t *f, uint16_t n) // "LDRCLOG " in a frame, or -1 (the record glued behind the word)
{
    for (uint16_t i = 0; i + 8 <= n; ++i)
        if (f[i] == 'L' && !memcmp(f + i, "LDRCLOG ", 8))
            return (int)i;
    return -1;
}
// What was read from the wire in one go may begin with TEXT replies that came late (nobody waited for them): 'p', the box's
// text, FF FF FF. A text box may hold any words and any letters - nothing in it is the screen's word, a marker or a page's
// number. Where the rest begins (j: all of it is such replies, or the last of them has no end yet).
B211_RARE static int AfterTextReplies(const uint8_t *t, int j)
{
    int from = 0;
    while (from < j && t[from] == 'p')
    {
        int e = from + 1;
        while (e + 2 < j && !(t[e] == 0xFF && t[e + 1] == 0xFF && t[e + 2] == 0xFF))
            ++e;
        if (e + 2 >= j)
            return j;
        from = e + 3;
    }
    return from;
}
// What GetTextIn read from the wire in one go (j bytes, bare): the screen's power-on bytes are taken out of it, and its
// restart word with what stands in front of it; the record behind the word stays, for the log. The length left.
B211_RARE static int TakeScreenStart(uint8_t *t, int j)
{
    static const uint8_t powerOn[10] = {0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF};
    for (int i = 0; i + 10 <= j; ++i)
        if (t[i] == 0 && !memcmp(t + i, powerOn, 10))
        {
            NoteScreenRestart(-2);
            memmove(t + i, t + i + 10, (size_t)(j - i - 10));
            j -= 10;
            break;
        }
    const int from = AfterTextReplies(t, j);
    const int found = from < j ? RestartWordAt(t + from, (uint16_t)(j - from)) : -1;
    if (found < 0)
        return j;
    const int at = from + found;
    NoteScreenRestart(RestartReasonAt(t + at, (uint16_t)(j - at)));
    const int rec = RestartRecordAt(t + at, (uint16_t)(j - at));
    if (rec < 0)
        return 0;
    memmove(t, t + at + rec, (size_t)(j - at - rec));
    return j - at - rec;
}
static bool IsButtonCode(const uint8_t *f, uint16_t n) // a button's code (7-bit: 128 + n; 24-bit: 00 n n 00; a burst of numbers), framed or not - never a word
{
    return n && (f[0] == 0 || f[0] >= 0x80);
}
static bool IsPageOwnWord(const uint8_t *f, uint16_t n) // a framed word that is no press: the page's own as it comes up, or the touch on its background
{
    if (n >= 7 && (!memcmp(f, "ldrcadj", 7) || !memcmp(f, "ldrcrcv", 7) || !memcmp(f, "UKRULES", 7)))
        return true;
    if (n == SUBTRIM_DONE_BYTES && !memcmp(f, "StEDIT", 6))
        return true; // (the fourteenth review) the Sub-trim page's "done": said behind this board's own click of its part "rs" - no finger made it. As a
                     // press it was logged "not obeyed (its page had gone)" whenever the page was left as one arrived
    if (n >= 8 && f[0] == 'C' && f[1] == 'H' && f[2] >= '1' && f[2] <= '9')
    { // CH1NAME= ... CH16NAME=
        const uint16_t at = (uint16_t)((f[3] >= '0' && f[3] <= '9') ? 4 : 3);
        return n >= at + 5 && !memcmp(f + at, "NAME=", 5);
    }
    return false;
}
static bool IsPress(const uint8_t *f, uint16_t n, bool framed) // what the marker's rule is for: a button's code, or a word a page's button printed
{
    if (IsButtonCode(f, n))
        return true;
    return n && framed && !IsPageOwnWord(f, n);
}
static bool IsLoadPrint(const uint8_t *f, uint16_t n, bool framed) // a press that a page also prints by itself as it comes up: obeyed between the two markers
{
    return framed && n >= 4 && !memcmp(f, "StCH", 4);
}
static bool ScreenPageUnconfirmed() // a page command has gone and the screen has not said that the page is up
{
    return ScreenMarkAwaited != 0 && ScreenMarkMisses < SCREEN_MARK_MISSES;
}
static bool IsMarkKind(uint32_t v) // a page's marker (4C44...., 4C45....), the number the screen is told after its restart (4C46....) or the one it says back when it owes an answer (4C47....: SCREEN_ECHO_BASE): never a box's value
{
    return (v & 0xFFFC0000UL) == SCREEN_MARK_BASE;
}
static bool TakeScreenMark(const uint8_t *q) // q: a value reply, 'q' and four bytes. True: a page's marker (or the restart's number), not a box's value
{
    const uint32_t v = (uint32_t)q[1] | ((uint32_t)q[2] << 8) | ((uint32_t)q[3] << 16) | ((uint32_t)q[4] << 24);
    if (!IsMarkKind(v))
        return false;
    ScreenSaysMarks = true; // (the tenth review) A SCREEN THAT SAYS ANY OF THIS BOARD'S NUMBERS BACK SAYS A PAGE'S MARKERS TOO - an earlier page command's,
                            // its session's number, the one that says it has caught up. It was set by the LAST page command's second marker
                            // alone: with that one overtaken by the next page command, or lost, the screen went on as one "that has never said
                            // a marker" - whose late marker is given up after a second and a half, and an old page's tap obeyed on the new one
    if ((v & 0xFFFE0000UL) != SCREEN_MARK_BASE)
    { // B211: a number the screen was told to say back (an earlier one is let go: the last one told is still to come) - its session's, or
      // the one that says it has caught up
        if (v == ScreenSession)
        {
            ScreenSaidSession = true;
            ++ScreenSessionSaidN;
        }
        else if (v == ScreenEcho)
        {
            ScreenSaidEcho = true;
            ScreenEchoBehindZero = ScreenZeroJustSaid; // (what stood right in front of it: a whole value reply of 0 - the session's number of a screen that has started again)
        }
        return true;
    }
    if (ScreenMarkCount && (v & 0xFFFF) == ScreenMarkCount)
    { // the last page command's (an earlier one's is let go: the last one's are still to come)
        ScreenMarkOldPage = false; // either marker: the screen has read as far as the page command
        if (ScreenMarkGivenUp)
        { // A MARKER COME AFTER ITS WAIT WAS GIVEN UP (the ninth review): the screen is only now reading the page command - a press obeyed since
          // the wait ended may have been the OLD page's. The boxes of the work in hand have no answer; and the wait is on again
            ScreenMarkGivenUp = false;
            PageChangedUnderGet = true;
            if (!(v & SCREEN_MARK_PAGE))
            {
                ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount;
                ScreenMarkAskedMs = millis();
            }
        }
        if (v & SCREEN_MARK_PAGE)
        { // the second: the page is up (the screen is done with the page command) - the wait is over
            ScreenMarkAwaited = 0;
            ScreenMarkMisses = 0;
            ScreenSaysMarks = true;
            ScreenPageIdDue = ScreenPageId == 0xFF; // ... and its number comes next (asked right behind this marker)
        }
    }
    return true;
}
// REPLY FRAMES AMONG WHAT WAS READ BARE (GetTextIn reads a word with all that is on the wire behind it: the screen's own
// words have no end). A page's markers, and its number ("sendme") right behind one, are noted IN THE ORDER THEY CAME and
// taken out: what is left is the word. (A storm of taps found them lost behind a pipe line: the new page's buttons were
// dead until the markers were given up.)
// (The tenth review, 15 Nov 2026: they were looked for at the END of what was read only. A screen up to 1.11.197 says the
// line of its other core - "the loop is silent ..." - in two pieces, and the loop's own replies can go out BETWEEN them: a
// page that took a fifth of a second to come up had its second marker and its number there. Read in one go by the main loop
// they stood in the MIDDLE, were taken for part of the line, and the new page's buttons were deaf for a second and a half -
// a tap in that time let go without a word. A marker's frame cannot be mistaken wherever it stands: q, a number of the
// markers' kind, FF FF FF - no word of the screen's, and no line for the log, holds an FF.)
// (The seventh review: a page's number was looked for by its first byte alone, 66 - which is the letter f. A late text answer
// "pOff" read by the loop gave "page 102". Now nothing is looked for inside a text reply at the head of what was read, and a
// page's number counts only RIGHT BEHIND A MARKER - where the one asked with a page command always stands.)
static bool MarkFrameEndsAt(const uint8_t *t, int floor, int cut) // the eight bytes before t[cut] are a marker's frame (not before t[floor])
{
    return cut - 8 >= floor && t[cut - 8] == 'q' && t[cut - 1] == 0xFF && t[cut - 2] == 0xFF && t[cut - 3] == 0xFF &&
           IsMarkKind((uint32_t)t[cut - 7] | ((uint32_t)t[cut - 6] << 8) | ((uint32_t)t[cut - 5] << 16) | ((uint32_t)t[cut - 4] << 24));
}
FLASHMEM static void TrailingReplies(uint8_t *t, int &j)
{
    const int floor = AfterTextReplies(t, j);
    int taken = -1; // where a frame was taken out last: what stands there now stood BEHIND that frame - not right behind what is in front of it
    for (int i = floor; i + 8 <= j;)
    {
        if (!MarkFrameEndsAt(t, i, i + 8))
        {
            ++i;
            continue;
        }
        int n = 8; // a marker (or a number the screen was told to say back) ...
        // (The twelfth review: "the 0 right in front" passed over a marker here - 0, a page's marker, the number said back: the marker taken out, the
        //  number stood behind the 0. The other reader, StashFrame, never passed over one. Right in front is right in front.)
        ScreenZeroJustSaid = i != taken && i - 8 >= floor && t[i - 8] == 'q' && !(t[i - 7] | t[i - 6] | t[i - 5] | t[i - 4]) && t[i - 3] == 0xFF && t[i - 2] == 0xFF && t[i - 1] == 0xFF;
        TakeScreenMark(t + i);
        if (i + 13 <= j && t[i + 8] == 0x66 && t[i + 10] == 0xFF && t[i + 11] == 0xFF && t[i + 12] == 0xFF)
        { // ... and the showing page's number, right behind it
            NoteScreenPage(t[i + 9]);
            n = 13;
        }
        memmove(t + i, t + i + n, (size_t)(j - i - n));
        j -= n;
        taken = i;
    }
    ScreenZeroJustSaid = false; // (a word was read: what comes next does not stand right behind a 0)
}
// A press that has come while the page is not known to be up: is it to be dropped? Until the first marker, yes, and it is
// said (the old page's). Between the two, yes and without a word - but for what a page prints as it comes up (IsLoadPrint).
uint16_t LoadPrintsLetGo = 0; // (what was let go between the two markers: counted, for the tests and a bench look)
FLASHMEM static bool DropUnconfirmedPress(const uint8_t *f, uint16_t n, bool framed)
{
    if (!ScreenPageUnconfirmed() || !IsPress(f, n, framed))
        return false;
    if (ScreenMarkOldPage)
    {
        NoteStalePress(f, n);
        SubTrimWordLetGo(f, n, framed); // (the fifteenth review) a touch of the Sub-trim page's, let go here, owes that page its writing-out: Trims.h
        return true;
    }
    if (IsLoadPrint(f, n, framed))
        return false;
    if (LoadPrintsLetGo < 65535)
        ++LoadPrintsLetGo;
    SubTrimWordLetGo(f, n, framed);
    return true;
}
static bool StalePressInTextIn() // the frame just read from the wire is a press and the page is not known to be up: not obeyed
{
    if (!ScreenPageUnconfirmed())
        return false;
    const bool code = IsButtonCode((const uint8_t *)TextIn, 1);
    const uint16_t n = code ? 4 : (TextInFramed && TextInLen) ? TextInLen : (uint16_t)strnlen(TextIn, 40); // (B211, the fourteenth review: a framed burst by its
                                                                                                          //  FRAME - the Sub-trim page's carry numbers behind their word, and
                                                                                                          //  a number's zero ended the text: its "done" was measured 7, a press)
    if (!DropUnconfirmedPress((const uint8_t *)TextIn, n, TextInFramed))
        return false;
    TextIn[0] = TextIn[1] = TextIn[2] = TextIn[3] = 0;
    return true;
}
FLASHMEM static void ScreenMarkGiveUp() // the marker's wait ENDS without it: only for a screen that has never said one (ScreenMarkLate)
{
    ScreenMarkAwaited = 0;
    ScreenMarkOldPage = false;
    ScreenMarkGivenUp = true; // (should it come yet: TakeScreenMark)
    if (ScreenMarkMisses < 255)
        ++ScreenMarkMisses;
    NoteNoScreenMark();
}
FLASHMEM static void ScreenMarkLate() // the wire is empty and the page's marker a second and a half late (GetButtonPress)
{
    if (!ScreenSaysMarks || ScreenMarkMisses >= SCREEN_MARK_MISSES)
    { // a screen that has never said one: the wait ends, as it always did
        ScreenMarkGiveUp();
        return;
    }
    if (!ScreenRestartSeen)
        NoteAnswerOwed(); // A MARKER THAT IS LATE IS OWED: the wait goes on, and the screen is asked to say a number back (ScreenOwedStep).
                          // (While its restart is noted nothing is done here: that ends with the front page, and a marker of its own.)
}
// THE SCREEN OWED AN ANSWER AND HAS CAUGHT UP - it has said back the number it was told - or half a minute has gone by.
B211_RARE static void ScreenOwedOver()
{
    const bool said = ScreenSaidEcho;
    const bool longEnough = (millis() - ScreenOwedSinceMs) > SCREEN_TELL_LONGEST_MS;
    if (said && ScreenEchoAskedSession && !ScreenRestartSeen)
    {
        if (ScreenSessionSaidN == ScreenEchoSessionN)
        { // Asked for its session's number in front of this one, the screen said this one and NOT that.
          // IT HAS STARTED AGAIN, and every sign of that was lost, when it said 0 for it - twice in this episode, not needing to be one round after the
          // other (noted: the front page is drawn afresh).
          // (The tenth review: that was concluded from the session's number NOT BEING READ, twice. On a screen up to 1.11.197 the tail of a
          //  line of its other core in front of the two answers hides the first of them: twice running, and a healthy screen had "started
          //  again". Now a round counts only when a whole value reply of 0 stood right in front of the number said back. A round in which
          //  the session's number was not read at all says nothing: the screen is asked again, a fifth of a second on - until the half
          //  minute of an answer owed is over; a screen that says numbers back and has still not said its session's by then is taken to
          //  have started again.)
            ScreenSessionDoubted = true;
            if (ScreenEchoBehindZero && ScreenSessionUnsaid < 255)
                ++ScreenSessionUnsaid;
            if (ScreenSessionUnsaid < 2 && !longEnough)
            {
                ScreenEchoToldMs = ScreenEchoBehindZero ? 0 : ((millis() - (SCREEN_TELL_AGAIN_MS - 200)) | 1); // (0 said: asked again at once; nothing read: in 200 ms)
                ScreenSaidEcho = false;
                return; // (still owed)
            }
        }
        else
            ScreenSessionDoubted = false; // (it has said its session's number: the same screen)
    }
    const bool startedAgain = ScreenSessionDoubted && !ScreenRestartSeen && (ScreenSessionUnsaid >= 2 || longEnough);
    const bool saidZeroTwice = ScreenSessionUnsaid >= 2;
    ScreenSessionDoubted = false;
    ScreenSessionUnsaid = 0;  // (whatever was counted in this episode is over with it - it was left standing when the half minute ended one)
    ScreenAnswerOwed = false; // what it owed has come and gone: it is asked again from here
    if (startedAgain)
    {
        NoteScreenRestart(saidZeroTwice ? -3 : -4); // (-3: it said 0 for its session's number, twice. -4, the eleventh review: it never said that number in the
                                                    //  half minute, and no 0 either - taken to have started again all the same, and the log says which)
        return;
    }
    if (!ScreenMarkAwaited)
        return;
    if (said && ScreenEchoMarkCount == ScreenMarkCount)
    { // A page's marker is still awaited - and the screen has said back a number it was told AFTER that page command: the marker was lost on the
      // wire. The page is up; its number is asked for again (the keyboard's is never learned: NoteScreenPage)
        ScreenMarkAwaited = 0;
        ScreenMarkOldPage = false;
        ScreenPageIdDue = ScreenPageId == 0xFF;
        ScreenAskPage();
        NoteNoScreenMark();
    }
    // (Half a minute and no number back, the marker still awaited: THE WAIT GOES ON. A screen that says markers and has said nothing for so long
    //  has not read the page command - whatever it prints when it wakes was pressed on the page it still shows. The next look for a press finds
    //  the marker late again, and the screen is asked afresh: ScreenMarkLate.)
}
FLASHMEM void ScreenOwedStep() // the screen owes an answer: has it caught up? Pass after pass, from the main loop and from a question that waits; it never waits
{
    if (ScreenAnswerOwed && !ScreenRestartSeen && ScreenCaughtUp())
        ScreenOwedOver();
}

uint16_t PendingDropped = 0; // B211: the frames NOT kept for want of room - counted, never cleared. The Sub-trim page, whose words say what each was made
                             // from, finds a gap by itself when another word follows - and by this count when none does (Trims.h SubTrimPoll)
uint16_t PipeLinesTooLong = 0; // B211: lines of the Bluetooth pipe longer than the reader behind a send can keep - dropped whole (StashPendingEventBytes)
void PendingPush(const uint8_t *f, uint16_t n, bool framed) // a frame kept for GetButtonPress
{
    if (n == 0)
        return;
    if (PendingCount >= MAXPENDINGFRAMES || PendingEventLen + n >= sizeof(PendingEvent) - 1)
    {
        ++PendingDropped; // (no room: not kept - and counted)
        SubTrimWordLetGo(f, n, framed); // (the fifteenth review: ... and a touch of the Sub-trim page's says what kind of page it came from: Trims.h)
        return;
    }
    if (DropUnconfirmedPress(f, n, framed))
        return; // B211: pressed on the page being left (or, between the two markers, nothing a page prints as it comes up)
    memcpy(PendingEvent + PendingEventLen, f, n);
    PendingEventLen += n;
    PendingEvent[PendingEventLen] = 0;
    PendingLens[PendingCount] = n;
    PendingFramedFlags[PendingCount] = framed;
    ++PendingCount;
}
// Both marker bytes have been read: the two length bytes, then that many bytes, into dst (cap at most: more are read and
// dropped). A pause of up to FRAME_GAP_US between bytes is waited out. The payload's length; -1 when the burst never
// completed (what came is in dst, len bytes of it) - such a burst is never obeyed.
// (B211, the ninth review: a damaged length - up to 65535 - was followed for as long as bytes kept coming, the model not flown
// meanwhile. The screen frames 4000 bytes at most, which take 44 ms: a longer burst declared, or one still coming after 100 ms,
// never completed. The clock is looked at whenever a byte had to be waited for, and once in 64 bytes.)
int ReadFramedRest(uint8_t *dst, uint16_t cap, uint16_t &len)
{
    uint8_t hdr[2];
    uint16_t have = 0, want = 0;
    const uint32_t begun = millis();
    len = 0;
    while (true)
    {
        const uint32_t quiet = micros();
        bool waited = false;
        while (!NEXTION.available())
        {
            waited = true;
            if ((micros() - quiet) >= FRAME_GAP_US)
            {
                if (len > cap)
                    len = cap;
                return -1;
            }
            delayMicroseconds(10);
        }
        if (waited && (millis() - begun) >= FRAME_LONGEST_MS)
        {
            if (len > cap)
                len = cap;
            return -1;
        }
        const uint8_t b = (uint8_t)NEXTION.read();
        KickTheDog();
        if (have < 2)
        {
            hdr[have++] = b;
            if (have == 2)
            {
                want = (uint16_t)(hdr[0] | (hdr[1] << 8));
                if (want == 0)
                    return 0;
                if (want > FRAME_MOST)
                    return -1;
            }
            continue;
        }
        if (len < cap)
            dst[len] = b;
        ++len;
        if (len >= want)
        {
            if (len > cap)
                len = cap;
            return (int)len;
        }
        if ((len & 63) == 0 && (millis() - begun) >= FRAME_LONGEST_MS)
        {
            if (len > cap)
                len = cap;
            return -1;
        }
    }
}
void StashFramed(const uint8_t *p, uint16_t len) // a framed burst, kept whole
{
    ScreenZeroJustSaid = false; // (the eleventh review: a burst stands between - what comes next does not stand right behind a 0. See ScreenOwedOver)
    ScreenFramesBursts = true;
    PendingPush(p, len, true);
}
void PendingShrinkFirst() // HelpNameFrom took the first kept frame's first byte: the queue follows (a frame used up goes)
{
    if (!PendingCount)
        return;
    if (--PendingLens[0])
        return;
    for (uint8_t i = 1; i < PendingCount; ++i)
    {
        PendingLens[i - 1] = PendingLens[i];
        PendingFramedFlags[i - 1] = PendingFramedFlags[i];
    }
    --PendingCount;
}

// B211: a page command is about to go - no press kept so far outlives its page (the screen's own words stay, in their order)
FLASHMEM void PurgeKeptPresses()
{
    uint16_t from = 0, to = 0;
    uint8_t kept = 0;
    for (uint8_t i = 0; i < PendingCount; ++i)
    {
        const uint16_t n = PendingLens[i];
        if (from + n > PendingEventLen)
            break; // (never: the lengths are the bytes)
        if (IsPress((const uint8_t *)PendingEvent + from, n, PendingFramedFlags[i]))
        {
            NoteStalePress((const uint8_t *)PendingEvent + from, n);
            SubTrimWordLetGo((const uint8_t *)PendingEvent + from, n, PendingFramedFlags[i]); // (the seventeenth review: a touch of the Sub-trim page's that was KEPT and is
                                                                                                 //  purged with its page says what kind of page file said it - Trims.h)
        }
        else
        {
            memmove(PendingEvent + to, PendingEvent + from, n);
            PendingLens[kept] = n;
            PendingFramedFlags[kept] = PendingFramedFlags[i];
            to += n;
            ++kept;
        }
        from += n;
    }
    PendingCount = kept;
    PendingEventLen = to;
    PendingEvent[to] = 0;
}

void StashFrame(const uint8_t *f, uint16_t n, bool withEnd = false);
// A WORD WITH NO END MAY NOT BE OVER (the ninth review, 15 Nov 2026). The screen's own words come bare, with no end - and a long
// one can come IN TWO PARTS: the line its other core says when the loop has stood still ("LDRCLOG core 1 ... last command 213 ms
// ago: page RXOptionsView") goes out in pieces, and a hold of that core between two of them, or a reply of the loop's core
// written between them, leaves the line's TAIL to begin a frame of its own. A tail that begins with p is the head of a TEXT
// reply to whoever reads it: "page RXOptionsView", then the real answer "p3.70" and its end - the box's text was handed back as
// "age RXOptionsViewp3.70", a number made of it: 0 (found by a run; a text box may hold anything, so nothing in the bytes tells
// the two apart). A value reply and a page's number have a shape of their own (eight bytes, five), and a tail in front of one
// nearly always breaks that shape: no answer. (Not always - the tenth review: a tail that is the one letter q, in front of a
// value below zero, makes eight bytes again: -1 was read as -143. A page's box is then refused all the same - the FF left over
// spoils the page's number behind it - and a system variable's value is held to its bounds by whoever asked. Known, and rare
// beyond counting: one byte of a line cut exactly there, by a screen up to 1.11.197.)
// So: whenever a bare word WITHOUT AN END is read from a screen that frames, anywhere, the time is kept - and for half a second
// from then NO TEXT REPLY IS BELIEVED (CollectReply: no answer, at once; the screen then owes one, and nothing is asked until it
// has caught up). A line of the Bluetooth pipe is whole at its newline. (A line for the log that ends with a newline - a screen
// from 1.11.198 on says it so, in one piece that cannot be cut - opened no half second either, until 15 Nov 2026: NoteBareRead,
// below, says why it does now.) (A screen that has never framed - an older one - is read as it always was: its pages' own words
// come bare.)
// (The tenth review. HALF A SECOND IS A TIME, NOT A BOUND: nothing says when the rest of a cut line has come. A word open when a
// get's wait begins, or opened during it, is open for that whole wait (CollectReply). And the screen's other bare words with no
// newline - TIME=, UKRULES, ldrcpipe=N, LDRCAWAKE - open the half second on every screen, 1.11.198 too: they are written in one
// piece by its loop, and nothing follows them.)
// (The twelfth review: a text box asked JUST BEHIND the half second, the line's rest still held, was asked the old way - and was
// handed the rest with its answer glued on, 100 of 100.) THE WORD IS UNSETTLED UNTIL THE SCREEN HAS ANSWERED "sendme" BEHIND ITS
// HALF SECOND: its loop was running then, and what a stall had held back came out in front of THAT answer, where nothing takes
// it for a text. Until then every text box settles first (GetText), and a text reply is not believed (CollectReply).
// (The thirteenth review: "CAME OUT IN FRONT OF THAT ANSWER" IS AN ORDER BETWEEN THE SCREEN'S TWO CORES, and nothing on the wire makes it so. Held
//  together, they are let go together - and the loop may write its answer a millisecond BEFORE the other core writes its line's rest: the look
//  answered clean, the word settled, the rest in front of the box's answer after all (by a run: up to 100 of 100, the loop 0.1 to 2.5 ms ahead).
//  What holds THAT order is a line of the screen's own loop: a field screen (1.11.191 to 1.11.197) whose other core's watch has stood still a
//  quarter second says "LDRCLOG core 0 silent ..." at the top of its next pass - in front of its serial work, so in front of the look's answer:
//  another bare word with no end, the look is not clean, and nothing is settled by it (dev/test_stallscreen scene_core_order has both orders, with
//  that line and without). A hold of both cores SHORTER than that quarter second lets no half second run out; so both orders are covered.)
// AND A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER, whatever the timing (TextMustBeNumber, below).
// What is left: a FREE text box (a name, a file's name) of a screen up to 1.11.197 whose OTHER core alone is held between two pieces of
// its line - its loop running, and answering - for some three quarters of a second and more (a quarter second in, the loop says its
// "core 0 silent" line: another half second from there), and lets go AFTER the look that settles has been answered: the next text box's
// name - that one's, or a later one's of the same work - then begins with the line's rest. (1.11.198 says the line in one piece.)
#define WORD_OPEN_MS 500
#define WORD_WAIT_MOST_MS 2500 // (the eleventh review) the longest a text box waits for such a word to be over and the screen's loop to be running (GetText)
#define WORD_SETTLE_MS 1000    // ... and, within it, for the screen's answer to "sendme"
uint32_t WordOpenMs = 0;       // when a bare word with no end was last read (0: never)
uint32_t WordSettledFor = 0;   // the word - by its time - behind whose half second a "sendme" has been answered (0: none)
bool TextReplyDoubted = false; // the text reply just read was not believed for that reason (GetText says so in the log)
static void NoteWordOpen()
{
    WordOpenMs = millis();
    if (!WordOpenMs)
        WordOpenMs = 1;
    WordSettledFor = 0;
}
static bool WordMayBeOpen()
{
    return WordOpenMs && (millis() - WordOpenMs) < WORD_OPEN_MS;
}
static bool WordUnsettled() // (the twelfth review) such a word was read, and no "sendme" has been answered behind its half second since
{
    return WordOpenMs && WordSettledFor != WordOpenMs;
}
// B186 (Malcolm, 5 Nov 2026, PID plus: "The screen did not answer for one of the boxes, so NOTHING was sent", twice - the screen's
// own log showed all 26 answers sent): a PIPE LINE ("ldrctel ...\n", "ldrcrep ...\n") has no FF FF FF, and since screen 1.11.179
// the block's line is told again every 600 ms while its read window is open (up to 15 s after a page loads). One that came while
// a get waited was glued to the reply in front of it - "ldrctel 25:... p2.5 FF FF FF" - and the whole frame was stashed as a word:
// the reply lost, the save refused. A pipe line now ends at its newline wherever it is met, and is kept for GetButtonPress.
// (B211, the eighth review: a pipe line is "ldrctel " or "ldrcrep " - not everything that begins "ldrc". The pipe's state,
// "ldrcpipe=2", has no newline and was waited for as an open line: what came within 5 ms was glued to it, and a reply behind
// it was cut at a byte 0A.)
static bool PipeLineHead(const uint8_t *f, uint16_t n) // the first n bytes (8 at most looked at) are a pipe line's beginning
{
    const uint16_t m = n < 8 ? n : 8;
    return m >= 4 && (memcmp(f, "ldrctel ", m) == 0 || memcmp(f, "ldrcrep ", m) == 0);
}
static bool PipeLineDone(const uint8_t *f, uint16_t n)
{
    return n >= 9 && f[n - 1] == '\n' && PipeLineHead(f, n);
}
static bool PipeLineOpen(const uint8_t *f, uint16_t n) // a pipe line begun and not yet ended
{
    return PipeLineHead(f, n) && f[n - 1] != '\n';
}
// B211 (the ninth review): ... and A LINE FOR THE LOG THAT ENDS WITH A NEWLINE is over there too ("LDRCLOG ...": a screen from 1.11.198
// on ends each with one, and says the line of its other core in one piece) - what stands behind it, be it the answer awaited with
// no pause at all, is a frame of its own. (An older screen's line has no end: it is over when it has stood quiet, as before.)
static bool BareLineDone(const uint8_t *f, uint16_t n)
{
    return PipeLineDone(f, n) || (n >= 9 && f[n - 1] == '\n' && memcmp(f, "LDRCLOG ", 8) == 0);
}
// WHAT WAS READ BARE (no framed burst): a word of the screen's own that may not be over? Then the half second begins (A WORD WITH NO END MAY NOT BE
// OVER, above).
// (The author's, 15 Nov 2026, by a storm run six times as long as the suite runs it - the released readers and every review's had it: "A LINE THAT
//  ENDS WITH A NEWLINE IS WHOLE" WAS TAKEN FROM THE BYTES, AND THE BYTES CAN LIE. A field screen's line for the log has no end of its own; the reply
//  the loop writes right behind its first piece can hold the byte 0A - a page's marker whose count's low byte is 10, the number of page 10, a box
//  that holds 10. The line was ended there (BareLineDone), taken for whole - no half second - and the reply's remaining bytes read as a frame of
//  their own: with the marker's count at 700A those are "p", "E", "L" and an end - a TEXT REPLY, handed to the box that was being asked: "EL". A
//  line taken for whole also left its REST, still held back, with no guard at all. So: ONLY A LINE OF THE BLUETOOTH PIPE IS WHOLE AT ITS NEWLINE -
//  it always has one of its own, and nothing else begins as it does. Every other bare word opens the half second: a line for the log too, with a
//  newline at its end or without, from a screen of any age. What that costs on a screen from 1.11.198 on, whose lines ARE whole: a text box asked
//  within half a second of such a line waits that out and asks "sendme" first - as on a field screen.)
B211_RARE static void NoteBareRead(const uint8_t *f, uint16_t n, bool withEnd)
{
    if (!n || !ScreenFramesBursts || f[0] < 0x20 || f[0] >= 0x7F || PipeLineDone(f, n))
        return; // (nothing; an older screen; a code; a line of the pipe)
    if (withEnd && (f[0] == 'p' || (f[0] == 'q' && n == 5) || (f[0] == 0x66 && n == 2)))
        return; // (a reply that came late, with its end)
    NoteWordOpen();
}
// B189 (Malcolm, 5 Nov 2026 ~18:48, PID plus after B188: "Screen answer MISSING: 'get sw0.val' after 2001 ms" and 't20.txt',
// while the screen's /sent showed both answers SENT): the answer was read and THROWN AWAY by the transmitter itself. After a get,
// EndSend waits 55 ms in DelayWithDog, which flies the model (SendData); the model's telemetry is written to the screen meanwhile
// ("StillConnected.txt=Amps ..."), every SendText ends in GetReturnCode -> here, and here a frame beginning with p or q is "a late
// reply nobody waits for" (StashFrame) - so the answer that arrived in those 55 ms was dropped. Only with a model connected, any
// box at random. While a get waits for its answer (NextionGetPending), nothing else drains the line: the bytes stay for CollectReply.
bool NextionGetPending = false;
B211_RARE static void NotePipeLineTooLong()
{
    ScreenZeroJustSaid = false; // (the fifteenth review: a line stood between, as StashFrame says of every other frame - what comes next is not "right behind a 0")
    if (PipeLinesTooLong < 65535)
        ++PipeLinesTooLong;
    static uint32_t last = 0;
    if (last && (millis() - last) < 2000)
        return;
    last = millis();
    if (LogMustWait())
    {
        KeepScreenNote("Pipe line over 511 bytes: dropped", false);
        return;
    }
    char m[] = "A line of the Bluetooth pipe was longer than 511 bytes as a command was being sent: dropped whole (whoever asked asks again) B211";
    LogText(m, strlen(m), true);
}
void StashPendingEventBytes() // replaces the blind pre-get flush (B69: frame by frame, so a button's code is kept too, not only a word)
{
    if (NextionGetPending)
        return; // B189
    uint8_t f[MAXPENDINGFRAME];   // (B186: was 64 - a pipe line of ten items is ~130 bytes)
    uint16_t n = 0, ffs = 0;
    uint16_t taken = 0;
    bool pipeTooLong = false; // B211 (the fourteenth review; the released code had it): A LINE OF THE PIPE LONGER THAN f (a reply's body may be 1500 characters).
                              // Its bytes behind the 512th were let go - its NEWLINE with them: the line never ended, and at the next FF FF FF (the end of
                              // whatever stood behind it) its first 509 bytes were handed on as a whole line - a reply's body cut short - and the frame
                              // behind it was swallowed. It is read TO ITS NEWLINE and dropped WHOLE; what stands behind it is a frame of its own.
    while (true)
    {
        if (++taken > SCREEN_READ_MOST)
            break; // B211 (the eighth review): a screen that talks WITHOUT END (none known; a fault in it) held this board here for ever, the dog unfed. What
                   // one read takes in has a limit - the port's whole buffer - and the rest is for the next read
        KickTheDog();
        if (!NEXTION.available())
        { // B186: a pipe line still arriving is waited for (5 ms of quiet, as GetTextIn), not stashed in two halves
          // B211: and so is the rest of a reply's frame - a page's marker ('q' and four bytes) or a "sendme" answer in two pieces
          // (the screen's port held for a moment in the middle of it) was kept as two junk words, and the marker lost (2 ms)
            const bool replyOpen = n >= 1 && ((f[0] == 'q' && n < 8) || (f[0] == 0x66 && n < 5));
            if (!PipeLineOpen(f, n) && !replyOpen)
                break;
            const uint32_t quiet = micros(), longest = replyOpen ? 2000 : 5000;
            while (!NEXTION.available() && (micros() - quiet) < longest)
                delayMicroseconds(20);
            if (!NEXTION.available())
                break;
        }
        const uint8_t b = NEXTION.read();
        if (n == 1 && f[0] == FRAME_MARK && b == FRAME_MARK)
        { // B177: a framed burst: read to its length and kept whole; what follows is the next frame
            uint8_t p[MAXPENDINGFRAME];
            uint16_t len = 0;
            if (ReadFramedRest(p, sizeof(p), len) < 0)
                LogGhostFrame("an incomplete framed burst", p, len);
            else
                StashFramed(p, len);
            n = 0;
            ffs = 0;
            delayMicroseconds(20);
            continue;
        }
        if (n < sizeof(f))
            f[n++] = b;
        else if (PipeLineHead(f, 8))
            pipeTooLong = true;
        if (pipeTooLong)
        { // (nothing of it is kept; its newline ends it)
            if (b == '\n')
            {
                NotePipeLineTooLong();
                pipeTooLong = false;
                n = 0;
                ffs = 0;
            }
            delayMicroseconds(20);
            continue;
        }
        if (f[0] == 'q' && n >= 2 && n <= 5)
        { // B211: a value reply is 'q' and FOUR bytes of value, whatever they are - an FF among them is no part of its end (CollectReply says more)
            ffs = 0;
            delayMicroseconds(20);
            continue;
        }
        if (BareLineDone(f, n))
        { // B186: a pipe line, whole (B211: or a line for the log that ended)
            StashFrame(f, n);
            n = 0;
            ffs = 0;
            continue;
        }
        if (b == 0xFF)
        {
            if (++ffs >= 3)
            {
                StashFrame(f, n >= 3 ? n - 3 : 0, true);
                n = 0;
                ffs = 0;
            }
        }
        else
            ffs = 0;
        delayMicroseconds(20); // one byte at 921600 baud takes ~11 us
    }
    if (pipeTooLong)
        NotePipeLineTooLong(); // (its newline never came, or this read's own limit was reached: not kept either)
    else if (n)
        StashFrame(f, n);   // (an unterminated tail: a word still arriving)
}

// B69 (Malcolm, 8 Oct: "Receive once was not enough ... this bug was definitely here on version one as well"): the
// screen's touch words are frames ending in FF FF FF, and so are the replies to "get". A reply's collector used to stop
// at the FIRST terminator: a touch word that arrived just ahead of the reply ended the collecting, the reply itself was
// then read as debris, and the word was rescued only if PRINTABLE (StashPrintableBytes) - a button code such as the
// Models page's Receive (C1 00 00 00) is not, so it was lost whenever it landed inside one of the page's constant
// "get MMems.val" windows. Now a reply is collected FRAME BY FRAME: a frame that is not the reply is kept whole for
// GetButtonPress (codes, 24-bit codes and words alike; the one-byte return codes are let go), and the collecting goes
// on until the reply, or the timeout.
// withEnd: the frame HAD an FF FF FF, taken off - it is not a pipe line taken at its newline, nor what stood open when a wait
// or a read ended. Only such a frame can end in, or be, a page's number or the screen's power-on byte: those are told by
// one byte (66 is the letter f, too - the seventh review: a pipe line ending "...off" and its newline, read in while a page's
// number was awaited, lost its last two bytes and gave "page 10").
void StashFrame(const uint8_t *f, uint16_t n, bool withEnd) // a frame without its FF FF FF
{
    if (!(n == 5 && f[0] == 'q'))
        ScreenZeroJustSaid = false; // (the tenth review: only a value reply stands "right behind a 0" - see ScreenOwedOver)
    if (f[0] != 'p' && n > 5 && f[n - 5] == 'q' && TakeScreenMark(f + n - 5))
        n -= 5; // B211: a page's marker glued behind a word of the screen's own that has no end (UKRULES, TIME=): the marker is noted, the word is the word
                // (not in a text reply come late: a text box may hold any letters - "...q12EL" is no marker; the eighth review)
    else if (withEnd && ScreenPageIdDue && n > 2 && f[n - 2] == 0x66 && f[0] >= 0x20 && f[0] < 0x7F && f[0] != 'p' && f[0] != 'q')
    { // ... and so is the page's number, when it is what comes next (the second marker has just been read)
        NoteScreenPage(f[n - 1]);
        n -= 2;
    }
    if (n == 0)
        return;
    NoteBareRead(f, n, withEnd); // B211: a word with no end may not be over (above) - noted here, before anything below goes back
    if (withEnd && f[0] == 0x66 && n == 2)
    { // B211: a "sendme" answer nobody waits for here (a page command's own; a get's, come late): the showing page's number
        NoteScreenPage(f[1]);
        return;
    }
    if (withEnd && f[0] == 0x88 && n == 1)
    { // B211: the screen's power-on bytes (their second frame, 88; the first, 00 00 00, is let go below): it has STARTED AGAIN
        NoteScreenRestart(-2);
        return;
    }
    {
        const int at = f[0] == 'p' ? -1 : RestartWordAt(f, n); // (not in a text reply that came late: a text box may hold any words)
        if (at >= 0)
        { // B211: the screen has RESTARTED, and says so (THE SCREEN'S OWN RESTART, above): noted - the word itself is not kept.
          // What is glued behind it, the record of what the screen was doing, is a line for the log and is kept as one
            NoteScreenRestart(RestartReasonAt(f + at, (uint16_t)(n - at)));
            const int rec = RestartRecordAt(f + at, (uint16_t)(n - at));
            if (rec < 0)
                return;
            f += at + rec;
            n = (uint16_t)(n - at - rec);
        }
    }
    if (n > 400 && !memcmp(f, "LDRCLOG ", 8))
        n = 400; // (a line for the log, with the next part glued behind it: its head is kept - whole, it was too long for the queue and all of it went)
    const uint8_t first = f[0];
    const bool code7 = first >= 0x80;                          // a button's 7-bit code (128 + n), 4 bytes
    const bool code24 = first == 0 && n == 4;                  // va0.val=n<<8: 00 n 00 00
    const bool word = first >= 0x20 && first < 0x7F;           // a word, "SendModel", "Import x.MOD" ...
    const bool reply = first == 'p' || (first == 'q' && n == 5); // B162: a late reply to a get (no button's burst begins with p or q)
    if (first == 'q' && n == 5)
    {
        TakeScreenMark(f); // B211: a page's marker (the reply to its "get ldrcsync")
        ScreenZeroJustSaid = withEnd && !(f[1] | f[2] | f[3] | f[4]); // (a whole value reply of 0: what a screen that has started again says for its session's number)
    }
    if (reply || !(code7 || code24 || word))
        return;                                                // return-code debris (01, 1A ...), or a reply nobody waits for
    PendingPush(f, n, false);
}
// 'q' and four bytes that stand at the END of a frame, behind a word (B162): a number a box can hold - under a million - or one
// of this board's own markers. Anything else there is the word's own tail and another frame's bytes: a page's number (66, its
// id) behind "...q 7", a return code behind "...qxyz". (A number below zero never comes this far: glued behind a word, its own
// FF bytes end the frame early - no answer.)
static bool GluedNumberOk(const uint8_t *q)
{
    const uint32_t v = (uint32_t)q[1] | ((uint32_t)q[2] << 8) | ((uint32_t)q[3] << 16) | ((uint32_t)q[4] << 24);
    return IsMarkKind(v) || v < 0x00100000UL;
}
// The reply to a "get": the frame that begins with `expected` ('q' a value, 'p' a text), into TextIn (k = its length,
// terminator included). Other frames meanwhile are stashed. False: no such frame within 100 ms.
bool CollectReply(uint8_t expected, uint16_t &k)
{
    const uint32_t begun = millis();
    const uint32_t openAtEntry = WordOpenMs; // (the tenth review) A WORD THAT WAS OPEN WHEN THIS WAIT BEGAN, OR OPENED DURING IT, IS OPEN FOR ALL OF IT:
    const bool doubtAtEntry = WordMayBeOpen() || WordUnsettled(); // its half second is a time, not a bound - the screen's other core, held for longer than that between a
                                               // line's first piece and the rest, let the rest go out with the answer this wait was for (found by a run)
    uint8_t ffs = 0;
    k = 0;
    ScreenZeroJustSaid = false;
    uint32_t radioAt = begun;
    uint32_t lastByteUs = micros();
    while (true)   // (B152: 100 ms; B188: 2000 round a get - GetText and getvalue set it)
    {
        if ((millis() - begun) >= NextionReplyWaitMs)
        { // B211: the time is over - but A FRAME STILL COMING IN IS READ TO ITS END (its bytes come back to back: 2 ms of quiet ends
          // it; a pipe line, 5 ms or its newline; 50 ms beyond the time at most). Cut off here, an answer that came at the last
          // moment was "missing" with its tail left on the wire as junk, and the head of a pipe line was kept as a whole line -
          // its last item read with zeros for the bytes that had not come (the sixth review, 14 Nov 2026)
            // (the eighth review: ... and what is WAITING on the wire at that moment is read too - the answer may have come during the
            //  radio's last turn; the time was over, nothing was "open", and it was left unread)
            if ((millis() - begun) >= NextionReplyWaitMs + 50 ||
                (!NEXTION.available() && (k == 0 || (micros() - lastByteUs) >= (PipeLineOpen((const uint8_t *)TextIn, k) ? 5000u : 2000u))))
                break;
        }
        if (NextionReplyWaitMs > 400 && (millis() - radioAt) >= 20)
        { // B188: a long wait keeps the radio's packets going (also through what is read beyond its time, above).
          // B211: EVERY 20 ms, FROM THE WAIT'S START, WHATEVER THE WIRE IS DOING. It was "between frames only" (the seventh review:
          // bytes without an end - the screen's chip starting again says a line of them - held the frame open to the wait's end:
          // two seconds with not one packet for a model in the air); then "when nothing has come for 2 ms" (the eighth: bytes that
          // trickle in, one in a millisecond, did the same); and only after the wait's first tenth of a second (a hole of 100 ms
          // at every answer that came late). What comes meanwhile waits in the port's buffer (4 kB: a millisecond is 92 bytes).
            radioAt = millis();
            const uint16_t mark = ScreenMarkCount;
            DelayWithDog(1);
            if (ScreenMarkCount != mark)
            { // (B211: a page command went out from inside that turn - a box put up when the link is lost, say. Its own looks for a
              //  press read the wire through TextIn: what stood open here has been written over, and is let go)
                k = 0;
                ffs = 0;
            }
        }
        if (k && !NEXTION.available() && (micros() - lastByteUs) >= (PipeLineOpen((const uint8_t *)TextIn, k) ? 5000u : 2000u))
        { // B211 (the eighth review): A WORD WITH NO END THAT HAS STOOD QUIET FOR 2 ms IS OVER (a pipe line: 5 ms) - it is handed on, and
          // what comes next is a frame of its own. It was held open until the next FF FF FF, which is the END OF THE ANSWER awaited:
          // the answer was glued to the word's tail and lost with it. A 16 MB screen whose loop has stood still for a fifth of a
          // second SAYS SO, bare ("LDRCLOG core 1 (the loop's) silent for 213 ms ...", from its other core) - so the answer that was
          // late for that very reason came behind that line, and was "MISSING".
          // (the ninth review) ... AND SO IS WHAT ONLY BEGINS AS A REPLY DOES. The screen writes a reply in one piece: a text reply
          // that has stood open and quiet for 2 ms, a value reply longer than its eight bytes, a page's number longer than its five,
          // is the SECOND HALF OF A WORD that was cut (A WORD WITH NO END MAY NOT BE OVER, above). Held open, it took the answer that
          // came behind it - and when it began with p, handed that back as the box's text with the word's tail in front. It is let
          // go, and noted. Half a reply is still waited for: q and fewer than eight bytes, 66 and fewer than five - and, from a
          // screen that has never framed, whatever begins as a reply does (all as it always was).
            const uint8_t first = (uint8_t)TextIn[0];
            const bool replyHead = first == 'p' || first == 'q' || first == 0x66;
            const bool half = (first == 'q' && k < 8) || (first == 0x66 && k < 5) || (k == 1 && first == FRAME_MARK) || (replyHead && !ScreenFramesBursts);
            if (!half)
            {
                if (first == 'p')
                    NoteWordOpen(); // (a text box may hold any words: nothing is looked for in it)
                else
                    StashFrame((const uint8_t *)TextIn, k);
                k = 0;
                ffs = 0;
            }
        }
        while (NEXTION.available())
        {
            const uint8_t b = NEXTION.read();
            lastByteUs = micros();
            if (k == 1 && (uint8_t)TextIn[0] == FRAME_MARK && b == FRAME_MARK)
            { // B177: a framed burst ahead of the reply: kept whole, by its length
                uint8_t p[MAXPENDINGFRAME];
                uint16_t len = 0;
                if (ReadFramedRest(p, sizeof(p), len) < 0)
                    LogGhostFrame("an incomplete framed burst", p, len);
                else
                    StashFramed(p, len);
                k = 0;
                ffs = 0;
                continue;
            }
            if (k < MAXTEXTIN)
                TextIn[k++] = b;
            if (TextIn[0] == 'q' && k >= 2 && k <= 5)
            { // B211: A VALUE REPLY IS 'q' AND FOUR BYTES OF VALUE, whatever they are - an FF among them is no part of its end. A box
              // that holds -1 (a sub trim one step below its centre, an offset, a correction) answers q FF FF FF FF FF FF FF: the
              // frame "ended" after q, the value was put together from three FFs and a byte left over from an earlier read, and
              // the FF that remained was glued to the next frame - the page's number was lost with it (the sixth review)
                ffs = 0;
                continue;
            }
            if (BareLineDone((const uint8_t *)TextIn, k))
            { // B186: a pipe line ahead of the reply: kept whole, and the reply still awaited (B211: or a line for the log that ended)
                StashFrame((const uint8_t *)TextIn, k);
                k = 0;
                ffs = 0;
                continue;
            }
            if (b != 0xFF)
            {
                ffs = 0;
                continue;
            }
            if (++ffs < 3)
                continue;
            if (expected == 'q' && k == 8 && TextIn[0] == 'q' && TakeScreenMark((const uint8_t *)TextIn))
            { // B211: a page's marker, not this get's answer (which comes after it: the screen answers in order)
                k = 0;
                ffs = 0;
                continue;
            }
            if ((TextIn[0] == 'q' && k != 8) || (expected == 0x66 && (uint8_t)TextIn[0] == 0x66 && k != 5))
            { // B211: a value reply is eight bytes, a page's number five: of another length it is a damaged one (bytes lost on the
              // wire) - no answer, never a number put together from what is there
                k = 0;
                ffs = 0;
                continue;
            }
            if (TextIn[0] == expected)                        // the reply: done
            {
                if (expected == 'p' && (WordMayBeOpen() || doubtAtEntry || WordOpenMs != openAtEntry))
                { // B211 (the ninth review): A TEXT REPLY BEHIND A WORD WITH NO END IS NOT BELIEVED - it may be that word's second
                  // half with the answer glued to it. No answer, at once (the screen then owes one: GetText)
                    TextReplyDoubted = true;
                    k = 0;
                    return false;
                }
                return true;
            }
            // B162 (the yellow transmitter, 31 Oct 2026: the Help button still opened "No log yet today" after B160): the
            // screen's button codes and words carry NO terminator (its print sends the raw bytes), so a press that lands in
            // this window is glued to the reply - "HelpView:MODELS.TXT" q 05 00 00 00 FF FF FF - and the whole frame was
            // stashed as the press: the reply lost (400 ms, then 65535), and the word delivered with the reply's bytes on
            // its tail (B160 then opened nothing; before it, the log). A value reply is always q and 4 bytes: when a frame
            // ends with one, the press is what comes before it, and the reply is the reply.
            if (expected == 'q' && TextIn[0] != 'p' && k >= 9 && TextIn[k - 8] == 'q' && GluedNumberOk((const uint8_t *)TextIn + k - 8))
            { // (B211, the eighth review: not when the frame is a TEXT reply come late - "pSeq 100" ends in q and four bytes too, and was
              //  handed back as the number 808464672)
              // (the ninth review: nor when those four bytes are no number a box holds - a word ending "q 7" with a page's number glued
              //  behind it, 66 09, was handed back as 157693728: GluedNumberOk)
                StashFrame((const uint8_t *)TextIn, k - 8);
                if (TakeScreenMark((const uint8_t *)TextIn + k - 8))
                { // B211: the press was glued to a page's marker, not to the answer: the answer is still to come
                    k = 0;
                    ffs = 0;
                    continue;
                }
                memmove(TextIn, TextIn + k - 8, 8);
                k = 8;
                return true;
            }
            StashFrame((const uint8_t *)TextIn, k >= 3 ? k - 3 : 0, true);   // something else first: kept for GetButtonPress
            k = 0;
            ffs = 0;
        }
        KickTheDog();
    }
    {   // B211: no answer came - but a BARE WORD of the screen's own may have (it has no end, so no frame ever closed on it): it
        // is kept for GetButtonPress as every other is, not thrown away with the wait. Above all the screen's "FrontView rst=N":
        // it restarted under this get, and says so before it answers anything - lost here, nothing knew, and the boxes asked for
        // next were answered from the page file (found on the Mac: throttle channel 16 saved as the model's)
        // (the sixth review: and what the page it put back printed as it came up - a code, unframed after a restart - may stand in
        //  front of that word: any frame left open is handed on, StashFrame finds the word in it. Half a reply is not: p, q, 66)
        const uint8_t first = (uint8_t)TextIn[0];
        if (k > 1 && first != 'p' && first != 'q' && first != 0x66 && first != expected)
            StashFrame((const uint8_t *)TextIn, k);
        else if (k && ScreenFramesBursts && !(first == 'q' && k < 8) && !(first == 0x66 && k < 5) && !(k == 1 && first == FRAME_MARK))
            NoteWordOpen(); // (the ninth review: what stands open when the wait ends and is no half reply - a text reply never is: the screen
                            //  writes a reply in one piece - is a word's second half, or a word's first byte)
    }
    return false;
}

void GetTextIn()
{
    delayMicroseconds(20);
    TextInFramed = false;
    TextInLen = 0;
    if (NEXTION.available())
    {
        CRUMB(CRUMB_GETTEXT);
        int j = 0;
        if (NEXTION.peek() == FRAME_MARK)
        { // B177: a framed burst? (its second byte is the marker too; a lone 7E begins a word, read below as ever)
            TextIn[0] = (char)NEXTION.read();
            j = 1;
            const uint32_t quiet = micros();
            while (!NEXTION.available() && (micros() - quiet) < 200)
                delayMicroseconds(20);
            if (NEXTION.available() && NEXTION.peek() == FRAME_MARK)
            {
                NEXTION.read();
                uint16_t len = 0;
                const int got = ReadFramedRest((uint8_t *)TextIn, MAXTEXTIN - 4, len);
                if (got < 0)
                { // never completed: not obeyed
                    LogGhostFrame("an incomplete framed burst", (const uint8_t *)TextIn, len);
                    TextIn[0] = 0;
                    return;
                }
                TextIn[len] = 0;
                TextIn[len + 1] = 0; // (a short payload read as an int sees zeros, not what was there before)
                TextIn[len + 2] = 0;
                TextIn[len + 3] = 0;
                TextInFramed = true;
                TextInLen = len;
                ScreenFramesBursts = true;
                ScreenZeroJustSaid = false; // (the eleventh review: a burst stands between - as StashFramed)
                return;
            }
        }
        const uint32_t readBegun = millis();
        while (true)
        {
            bool lineDone = false;
            while (NEXTION.available())
            {
                TextIn[j] = NEXTION.read();
                KickTheDog();
                if (j < MAXTEXTIN)
                    ++j;
                if (TextIn[j - 1] == '\n' && j >= 9 && BareLineDone((const uint8_t *)TextIn, (uint16_t)j))
                { // B211: a pipe line is over at its newline WHATEVER is on the wire behind it (a page's markers were read on as its tail, and lost) -
                  // and so is a line for the log that ends with one
                    lineDone = true;
                    break;
                }
                if (j >= MAXTEXTIN || ((j & 63) == 0 && (millis() - readBegun) >= SCREEN_READ_LONGEST_MS))
                { // B211 (the eighth review): ONE READ HAS AN END, whatever the screen does. A screen that talked without a pause (none
                  // is known to; a fault in it) held the main loop in here for as long as it talked - not one packet for the model. What
                  // has come is the read; the rest is the next one's (the clock is looked at once in 64 bytes)
                    lineDone = true;
                    break;
                }
                delayMicroseconds(20);
            }
            if (lineDone)
                break;
            // B160: a touch word comes in one burst, but its bytes can reach this board with a short pause among them,
            // and a pause of 20 us used to end the word ("HelpView:" was read without its name). The word is over when
            // nothing more has come for 200 us.
            // B181 (Malcolm, 5 Nov 2026, "PIDs: only PART came back in 2 s (Bluetooth 2)" - often, with the bigger blocks): a
            // PIPE LINE from the screen ("ldrctel 25:... 26:...", the block's items; "ldrcrep ...", a reply) is long, and a
            // pause on the screen's side (an interrupt held while it draws) can fall inside it: ended at the pause, the line's
            // second half had no name and was lost - the items in it never came. A pipe line ends at its newline (screen
            // 1.11.179 ends every pipe line with one), or after 5 ms of quiet (an older screen's items line, or a line cut).
            const bool pipeLine = j >= 8 && (memcmp(TextIn, "ldrctel ", 8) == 0 || memcmp(TextIn, "ldrcrep ", 8) == 0);
            if (pipeLine && TextIn[j - 1] == '\n')
                break;
            const uint32_t quietUs = pipeLine ? 5000 : 200;
            const uint32_t quiet = micros();
            while (!NEXTION.available() && (micros() - quiet) < quietUs)
                delayMicroseconds(20);
            if (!NEXTION.available())
                break;
        }
        TrailingReplies((uint8_t *)TextIn, j); // B211: a page's markers and its number among what was read bare: noted, and no part of the word
        j = TakeScreenStart((uint8_t *)TextIn, j);   // B211: the screen's power-on bytes and its "FrontView rst=N" are noted and taken out (THE SCREEN'S OWN RESTART)
        NoteBareRead((const uint8_t *)TextIn, (uint16_t)j, j >= 3 && (uint8_t)TextIn[j - 1] == 0xFF && (uint8_t)TextIn[j - 2] == 0xFF && (uint8_t)TextIn[j - 3] == 0xFF &&
                                                               AfterTextReplies((const uint8_t *)TextIn, j) >= j); // B211: a word with no end may not be over
        TextIn[j] = 0; // (B160: the read ends the text - what an earlier, unanswered read left behind is no part of it)
        TextInLen = (uint16_t)j;
        if (j < 4)
            TextIn[j + 1] = TextIn[j + 2] = TextIn[j + 3] = 0; // (a read that left nothing, or less than a code's four bytes, shows zeros behind it - not the bytes of the read before)
    }
}

/*********************************************************************************************************************************/
void LinkStrayFrame(); // LinkMode.h
bool GetButtonPress()
{
    if (!ModalWaits && !InsideDelayWithDog)
        PageLeftUnderWork = false;
    if (!ModalWaits && !InsideDelayWithDog)
        PageChangedUnderGet = false; // B211: the press whose boxes lost their page is done with: the next one's are asked for again. (Not by a question's
                                     // own look for its answer, nor from inside a wait: the work they belong to is still going on - the eighth review)
    if (!PendingCount && NEXTION.available() && (NEXTION.peek() == 'q' || NEXTION.peek() == 0x66))
    {   // B211: a value reply or a "sendme" answer at the head of the wire (a page's marker, its number; a late answer) is never a
        // press: it is read in frame by frame - the marker noted, what follows it kept in its order (StashPendingEventBytes waits
        // for a frame that comes in two pieces). Also when this is a question box's loop INSIDE a get's wait (a box put up by the
        // link's loss, say: NextionGetPending): the get it interrupted has no answer by then (PageChangedUnderGet - its own page
        // went), and left unread the markers kept the box deaf for a second and a half.
        const bool pending = NextionGetPending;
        NextionGetPending = false;
        StashPendingEventBytes();
        NextionGetPending = pending;
    }
    if (PendingCount)
    {   // a touch event rescued from a get-reply window -- deliver it now (B177: one frame at a time, as it came)
        const uint16_t n = PendingLens[0];
        memcpy(TextIn, PendingEvent, n);
        TextIn[n] = 0;
        TextIn[n + 1] = 0;
        TextIn[n + 2] = 0;
        TextIn[n + 3] = 0;
        TextInFramed = PendingFramedFlags[0];
        TextInLen = n;
        PendingEventLen -= n;
        memmove(PendingEvent, PendingEvent + n, PendingEventLen);
        PendingEvent[PendingEventLen] = 0;
        for (uint8_t i = 1; i < PendingCount; ++i)
        {
            PendingLens[i - 1] = PendingLens[i];
            PendingFramedFlags[i - 1] = PendingFramedFlags[i];
        }
        --PendingCount;
        TextInWasStashed = true; // (B163)
        return true;
    }
    if (NEXTION.available())
    {
        TextInWasStashed = false;
        TextInFramed = false;
        if (NEXTION.peek() == 0xA5)
        {   // V1B: A5 5A begins a frame of the screen's file link (LinkMode.h), which must never be read as a touch.
            // A5 alone begins the touch code 128+37: that one is put back together and handled as ever.
            uint8_t first = NEXTION.read();
            uint32_t waited = micros();
            while (!NEXTION.available() && (micros() - waited) < 400)
            {
            }
            if (NEXTION.available() && NEXTION.peek() == 0x5A)
            {
                LinkStrayFrame();
                return false;
            }
            TextIn[0] = first;
            int j = 1;
            delayMicroseconds(20);
            while (NEXTION.available())
            {
                TextIn[j] = NEXTION.read();
                KickTheDog();
                if (j < MAXTEXTIN)
                    ++j;
                delayMicroseconds(20);
            }
            TextIn[j] = 0;
            return !StalePressInTextIn(); // B211
        }
        GetTextIn();
        return !StalePressInTextIn(); // B211: a code pressed on the page being left is not obeyed
    }
    if (ScreenMarkAwaited && (millis() - ScreenMarkAskedMs) > SCREEN_MARK_WAIT_MS)
        ScreenMarkLate(); // B211: nothing on the wire, and the page's marker a second and a half late: it is OWED (a screen that has never said one: the wait ends)
    return false;
}

// B177: the frame in TextIn is to be obeyed? A framed one always. An unframed binary one (a 7-bit or 24-bit code) only while
// the screen has never framed (an older screen) - and then the screen is asked to frame, once in 2 s.
// From a screen that frames, an unframed code is a split tail or a late reply's: logged, and not obeyed.
// B211 (THE SCREEN'S OWN RESTART, above): ... or it is a button of a screen that has STARTED AGAIN and frames nothing until
// it is told to - pressed on a page as the card has it, not one this board drew. So:
//  - from a screen that has framed, an unframed WORD is obeyed only if it is one of the screen's own (IsScreensOwnWord: no
//    page's button prints those). A page's word that comes bare - the One switch page's OK, say - is not obeyed, as a code
//    is not;
//  - and while a restart is noted and the page not yet drawn afresh, no press at all is obeyed.
// (This board no longer forgets, at the screen's restart, that the screen frames: its unframed presses were obeyed until it
// had been told again. Should a restart ever go unnoticed - all its signs lost - the screen's buttons are not obeyed: nothing
// is read from, or done on, a page as the card has it. The first of them makes this board ASK the screen for its session's
// number - it has forgotten it - and the front page is drawn afresh: below, and ScreenOwedOver.)
B211_RARE static bool IsScreensOwnWord(const char *t) // a bare word of the screen's own firmware (TextIn, ended by a 0)
{
    if (!strncmp(t, "LDRC", 4) || !strncmp(t, "UKRULES", 7) || !strncmp(t, "TIME=", 5) || !strncmp(t, "ldrcpipe=", 9) || !strncmp(t, "ldrctel ", 8) || !strncmp(t, "ldrcrep ", 8) || !strncmp(t, "FrontView", 9))
        return true; // LDRCLOG, LDRCAWAKE, LDRCWHO, LDRCOFF, LDRCLINK, LDRCRXUP, LDRCIMG; the touch on a page of its own; the time; the Bluetooth pipe's lines
    static const char *const dying[] = {"Guru Meditation", "CORRUPT HEAP", "Backtrace:", "register dump", "Core dump", "core dump"}; // (its panic handler's words: LogFiles.h ScreenDyingWords keeps them)
    for (const char *k : dying)
        if (strstr(t, k))
            return true;
    return false;
}
// B211 (the eleventh review): A BARE WORD OF THE SCREEN'S OWN ENDS WHERE ITS OWN TEXT ENDS. "TIME=" and "ldrcpipe=" are numbers; the Bluetooth pipe's
// two lines end with a newline. Whatever is glued behind in the same read - a text reply that came late: p and a box's text - was left in
// TextIn, and main.cpp looks for the PAGES' words anywhere in it, in front of these: "ldrcpipe=2" with a box's text "Mark 2" behind it would
// have marked the GPS position. The word is ended where it ends (main.cpp ButtonWasPressed, for a word that came bare from a screen that frames).
// (The twelfth review: "UKRULES" - the touch on a background of the screen's own pages, said every 20 s for three minutes after one - was not among
//  them, and it is the one own word that falls through to the pages' words: "UKRULES" with the late answer "pMark 2" behind it marked the GPS
//  position, by a run. Seven letters, and it is over. The "LDRC..." words are answered in front of the pages' words and go back from there; the one
//  of them that carries a name looks for a reply's end behind it itself: ChooseImage.h.)
B211_RARE static void OwnWordCut(char *t)
{
    size_t n;
    if (!strncmp(t, "TIME=", 5))
        n = 5;
    else if (!strncmp(t, "ldrcpipe=", 9))
        n = 9;
    else if (!strncmp(t, "UKRULES", 7))
    {
        if (t[7] && strstr(t + 7, "LDRCLOG "))
            LogScreenLine(t + 7); // (the seventeenth review: below)
        else if (t[7])
            ScreenDyingWords(t + 7); // (the sixteenth review: below)
        t[7] = 0;
        return;
    }
    else
    {
        if (!strncmp(t, "ldrctel ", 8) || !strncmp(t, "ldrcrep ", 8))
        {
            char *e = strchr(t, '\n');
            if (e)
                e[1] = 0;
        }
        return;
    }
    while (t[n] >= '0' && t[n] <= '9')
        ++n;
    if (t[n] && strstr(t + n, "LDRCLOG "))
        LogScreenLine(t + n);    // (the seventeenth review) ... and A LINE FOR THE LOG glued behind is written (kept) before the cut too: it went with it
    else if (t[n])
        ScreenDyingWords(t + n); // (the sixteenth review) WHAT IS CUT AWAY IS LOOKED AT FOR THE SCREEN'S DYING WORDS FIRST (LogFiles.h: kept for the log, never
                                 // obeyed): its panic handler's line glued behind "TIME=", "ldrcpipe=N" or "UKRULES" went with the cut - no line of its death
    t[n] = 0;
}
bool TextInIsGenuine()
{
    const uint8_t first = (uint8_t)TextIn[0];
    const bool word = first != 0 && first < 0x80;
    if (!TextInFramed && word && ScreenRestartSeen && ScreenFramesBursts)
        return IsScreensOwnWord(TextIn) && strncmp(TextIn, "UKRULES", 7) != 0 && strncmp(TextIn, "TIME=", 5) != 0 && strncmp(TextIn, "ldrc", 4) != 0;
        // B211 (the eighth review): WHILE THE SCREEN'S RESTART IS NOTED only those of its own words pass that main.cpp's ButtonWasPressed
        // answers FIRST, and goes back from (its "LDRC..." words, its restart word, its panic handler's lines). The others - the touch
        // on a background, the time, the pipe's state and lines - are looked for BEHIND the pages' words there: a page's button printed
        // bare by the restarted screen, glued behind one of them in one read, was obeyed as that page's word. Those are let go for
        // these few seconds.
    if (!TextInFramed && word && (!ScreenFramesBursts || IsScreensOwnWord(TextIn)))
        return true; // a word of the screen's own: LDRCAWAKE, UKRULES, TIME= ... (from a screen that has never framed, an older one: any word)
    if (!TextInFramed && first == 0 && TextIn[1] == 0 && TextIn[2] == 0)
        return !ScreenFramesBursts || TextIn[3] == 0; // the 24-bit code 0 (Blank): nothing to obey - a burst that never completed, a read that left nothing.
                                                      // (B211, the eighth review: with a fourth byte - 00 00 00 xx, the chip's own text read at this wire's speed,
                                                      //  the head of its power-on bytes - it is not even that from a screen that frames: it counted as a touch,
                                                      //  and kept the screen saver and the power-off time away. Let go without a word.)
    if (ScreenRestartSeen)
        return false; // B211: the screen has started again and its page is not yet drawn afresh: no press is obeyed
    if (TextInFramed)
        return true;
    if (ScreenFramesBursts)
    {
        LogGhostFrame(word ? "an unframed word" : "an unframed code", (const uint8_t *)TextIn, 4);
        NoteAnswerOwed(); // B211 (the ninth review): A PRESS THAT COMES UNFRAMED FROM A SCREEN THAT FRAMES is what a screen says that has STARTED AGAIN
                          // UNNOTICED (every sign of it lost) - its buttons were then dead until this board was switched off and on. So the screen is
                          // asked for its session's number, as when it owes an answer (nothing waits): found to have forgotten it, the front page
                          // is drawn afresh and its buttons work again (ScreenOwedOver). The same screen says the number, and that is all.
        return false;
    }
    if ((millis() - FrameEnableSentMs) > 2000)
    {
        FrameEnableSentMs = millis();
        SendCommand((char *)"ldrcframe=1");
    }
    return true;
}

/*********************************************************************************************************************************/
// B160 (Malcolm, 31 Oct 2026: "The help button on the models page usually brings the help screen, but a couple of times it
// tried to open a log file instead"). A Help button's word is "HelpView:" and the text's name - HelpView:MODELS.TXT - in one
// burst. SendHelp took the name from a FIXED place (the tenth byte on): a word read in two parts, or one with another event
// ahead of it in the same read, gave NO name, and the viewer, given none, opened TODAY'S LOG. Now the name is taken from
// after the word wherever the word sits; a name not all there yet (every help text's is NAME.TXT) is completed from what the
// get-reply collector set aside and from the wire, 30 ms at most; and without a whole name, nothing opens.
bool HelpNameWhole(const char *name)
{
    const size_t n = strlen(name);
    return n > 4 && strcmp(name + n - 4, ".TXT") == 0;
}
bool HelpNameFrom(char *name) // name: room for 16
{
    const char *at = strstr(TextIn, "HelpView");
    uint8_t i = 0;
    name[0] = 0;
    if (!at)
        return false;
    uint16_t k = (uint16_t)(at - TextIn) + 8;
    if (TextIn[k] == ':')
        ++k;
    while (i < 15 && (uint8_t)TextIn[k] > 32 && (uint8_t)TextIn[k] < 127)
    {
        name[i++] = TextIn[k++];
        name[i] = 0;
    }
    {
        char *txt = strstr(name, ".TXT");
        if (txt)
        {   // B162: whatever rode in behind the name (a reply's bytes, when the word was glued to one) is not the name
            txt[4] = 0;
            i = (uint8_t)strlen(name);
        }
    }
    const uint32_t began = millis();
    while (!HelpNameWhole(name) && i < 15 && (millis() - began) < 30)
    {
        int c;
        if (PendingEventLen && !(PendingCount && PendingFramedFlags[0]))
        {   // set aside by a get-reply window: the rest of this word begins printable; a code or another frame is left alone
            // (B177: a FRAMED frame is whole and its own - never the rest of this word)
            c = (uint8_t)PendingEvent[0];
            if (c <= 32 || c >= 127)
                break;
            memmove(PendingEvent, PendingEvent + 1, PendingEventLen - 1);
            PendingEvent[--PendingEventLen] = 0;
            PendingShrinkFirst();
        }
        else if (NEXTION.available())
        {
            c = NEXTION.peek();
            if (c <= 32 || c >= 127)
                break; // not ours: left in the port
            NEXTION.read();
        }
        else
        {
            KickTheDog();
            continue;
        }
        if (c == ':' && i == 0)
            continue; // the colon, when the cut fell right after the word
        name[i++] = (char)c;
        name[i] = 0;
    }
    return HelpNameWhole(name);
}
/*********************************************************************************************************************************/
static bool IsPageCommand(const char *c) // "page <name>": alone, or one of several commands sent together (FF FF FF between them)
{
    return strncmp(c, "page ", 5) == 0 || strstr(c, "\xFF\xFF\xFFpage ") != nullptr;
}
// B211: a page command is about to go. From this moment a press that comes in was made on the page being left: what is on
// the wire already is read in (its presses dropped on the way, the screen's own words kept), the presses kept earlier go,
// and the first marker is asked for.
FLASHMEM void AskPageMarker(bool pageUp);
FLASHMEM void BeforePageCommand()
{
    ScreenMarkCount = ScreenCountAfter(ScreenMarkCount); // (never 0; the first from the clock: Utilities.h)
    ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount;
    ScreenMarkOldPage = true;
    ScreenMarkGivenUp = false;
    ScreenMarkAskedMs = millis();
    ScreenPageId = 0xFF; // (the new page's number: said right behind the second marker)
    ScreenPageIdDue = false;
    if (NextionGetPending || InsideDelayWithDog || ModalWaits)
        PageLeftUnderWork = true;
    if (NextionGetPending || InsideDelayWithDog || ModalWaits)
        PageChangedUnderGet = true; // THE PAGE IS CHANGED UNDER A BUTTON'S WORK, from inside one of its waits: under a get that waits for its answer; from
                                    // inside any wait that flies the model (the eighth review: the power button's way to the front page, the box "The
                                    // motor switch is ON" when the link is lost - a button's work that waits BETWEEN its boxes read the rest of them from
                                    // that other page, and the page's number said the same as this board's last page command); from inside a question's
                                    // wait. No box of that work has an answer from here on (GetNumberReply, GetText, GetOtherValue)
    StashPendingEventBytes();
    PurgeKeptPresses();
    AskPageMarker(false); // the first marker: answered just before the screen reads the page command
}
// The screen is asked for a marker: the first before the page command, the second right behind it (answered once the page is
// up) - and with the second, for the number of the page it then shows ("sendme": THE BOX'S PAGE, above).
FLASHMEM void AskPageMarker(bool pageUp)
{
    char m[32];
    snprintf(m, sizeof(m), "ldrcsync=%lu", (unsigned long)(SCREEN_MARK_BASE | (pageUp ? SCREEN_MARK_PAGE : 0) | ScreenMarkCount));
    NEXTION.print(m);
    NEXTION.print(pageUp ? "\xFF\xFF\xFFget ldrcsync\xFF\xFF\xFFsendme\xFF\xFF\xFF" : "\xFF\xFF\xFFget ldrcsync\xFF\xFF\xFF");
}
void SendCommand(char *tbox)
{
    CRUMB(CRUMB_COMMAND);
    char page[] = "page ";
    char blankview[] = "BlankView";
    const bool pageCommand = IsPageCommand(tbox);
    if (pageCommand)
        BeforePageCommand(); // B211: a press belongs to the page it was made on
    NEXTION.print(tbox);
    for (int i = 0; i < 3; ++i)
        NEXTION.write(0xff);
    if (pageCommand)
        AskPageMarker(true); // B211: the second marker
    delayMicroseconds(70);
    GetReturnCode(tbox);
    if (InStrng(blankview, tbox))
        return; // Don't need to wait for blankview
    if (InStrng(page, tbox))
        DelayWithDog(SCREENCHANGEWAIT); // Allow time for new page to appear
}
/*********************************************************************************************************************************/
void EndSend()
{
    for (u_int8_t pp = 0; pp < 3; ++pp)
    {
        NEXTION.write(0xff); // Send end of Input message //
    }
    DelayWithDog(55); // ** A DELAY ** (>=50 ms) was needed if an answer might come! (!! Shorter with Intelligent dislay)
}
/*********************************************************************************************************************************/
void SendValue(char *nbox, int value)
{
    char Val[] = ".val=";
    char CB[100];
    char NB[25];
    strcpy(CB, nbox);
    strcat(CB, Val);
    strcat(CB, Str(NB, value, 0));
    SendCommand(CB);
    ValueSent = true;
    GetReturnCode(nbox);
}

/*********************************************************************************************************************************/
// The number the screen answers to a "get" command (CB = "get Mfiles.val", "get tch2"): 65535 when no reply came.
// (B171: lifted out of getvalue so that a system variable can be asked for by its bare name, GetSysValue below.)
// B188 (Malcolm, 5 Nov 2026 ~18:38, PID plus after B187: refused again; the B187 log line named box sw0 - the FIRST box - and
// "the screen had settled"; the screen's /sent showed its q1 sent, nothing glued ahead of it): the answer came LATE. The screen
// takes the next serial bytes only between its loop's other jobs (its /perf: touch up to 193 ms, the WiFi up to 325 ms, one
// serial pass 606 ms), so now and then a get waited longer than 400 ms. Each get now waits up to 2 s for its own answer -
// still ONE ask, so a late answer is still this box's - with the radio kept going meanwhile (CollectReply). A slow answer
// (over 400 ms) or none at all is written in the log with its box and time, so the next report says how late they come.
#define NEXTION_GET_WAIT_MS 2000
// NO ANSWER IS NOT A NUMBER (the eighth review, 15 Nov 2026). A box asked for can have NO ANSWER: the reply never came, the
// screen was showing another page (its keyboard), the page was taken away under the button's work, the screen had started
// again. The getters then say 65535 (GetValue), "" (GetText) or 0 (GetOtherValue) - and B211 made "no answer" of what used to
// be another page's number. WHOEVER ASKS MUST NOT TAKE THAT FOR THE BOX'S VALUE: the setting stays as it is
// (`if (gv != 65535) ...`; `if (gv <= 1) ...` for a tick), or nothing of the page is taken. The older pages' OK routines did
// take it: a servo's frequency 65535 saved and sent to the receiver, a tick "on", a stick on another channel. Every box with
// no answer is COUNTED here - a count that only grows, so "did every box I asked for answer?" is `BoxesLost == <the count
// before>` (GetText's "" and GetOtherValue's 0 can be real answers; a count cannot be cleared by somebody else half way) -
// and at the end of a button's work that lost one the pilot is told (Utilities.h CheckForNextionButtonPress, LogFiles.h
// NoteBoxesLost). dev/test_noanswer reads every place a box is asked for, and fails for one that is not known to it.
static void BoxWasLost(const char *box, bool noNumber = false) // noNumber: it answered - with a text that is no number (TextMustBeNumber)
{
    if (BoxesLost == BoxesLostAtWork)
    {
        strlcpy(BoxLostName, box, sizeof(BoxLostName)); // (the FIRST of this button's work: those behind it are not even asked, and count too - the last of
                                                        //  them was what the log named: the tenth review)
        BoxLostNoNumber = noNumber;
    }
    ++BoxesLost;
}
// B211 (the twelfth review; the author's, reading reviewer A's finding 1): A NUMBER FIELD'S TEXT THAT IS NO NUMBER IS NO ANSWER. Every typed number field is
// asked as a text and made a number by atof or strtol - which make 0 of whatever they cannot read. The rest of a line of the screen's glued in front of
// the answer ("lay 0,7,0p3.70": the tenth, the eleventh and the twelfth review each found a timing that lets one through) was read as 0, and 0 was a
// number like any other - written to the flight controller, saved to the card. Whatever the timing: a text that holds anything no number is made of
// is "no answer" - counted, said, nothing taken. A number field is typed on the number keypad (digits, the point, the minus) and written by this
// board as a number: so digits, a sign, a point and blanks are all it can hold, and what is glued to an answer always brings a letter - the p the
// answer itself begins with. An empty field is still an empty field. Every routine that makes a number of a box's text calls this behind its
// GetText (dev/test_noanswer checks that). False: no number - the text is emptied, the box counted as not answered.
FLASHMEM bool TextMustBeNumber(const char *box, char *text)
{
    bool number = true;
    for (const char *p = text; *p && number; ++p)
        number = (*p >= '0' && *p <= '9') || *p == ' ' || *p == '+' || *p == '-' || *p == '.';
    if (number)
        return true;
    {
        char line[60];
        snprintf(line, sizeof(line), "Box %.12s: text is no number", box); // (36 places are kept: it said "... - not taken" behind them, to nobody)
        KeepScreenNote(line, false);
    }
    if (!NextionTextMissed)
    {
        snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", box);
        NextionMissedNoNumber = true; // (the thirteenth review: "the screen did not answer", it said of this box - which did)
    }
    NextionTextMissed = true;
    BoxWasLost(box, true);
    text[0] = 0;
    return false;
}
// A PAGE'S FIELDS ARE TAKEN WHOLE, OR NOT AT ALL (the ninth review, 15 Nov 2026). The Rotorflight pages GATHER their typed
// fields into the bytes they will write to the flight controller: a text asked for, a number made of it, the number held to its
// range - and "no answer" ("") made 0, held to its range: a number like any other. Filters were written with 10 Hz for 250, the
// level trims with 0 for 2.5 degrees, the model's name in the flight controller wiped (found by runs: Save, and a touch on a
// field while its boxes were read; or one "which page?" answer lost - which B211 itself made "no answer" of).
//  - KEEP_WHOLE stands at the head of every routine that gathers, once for each thing it gathers into: it keeps what was there,
//    and PUTS IT BACK when a box asked for meanwhile had no answer. A gather that lost a box has changed nothing.
//  - Whoever called the gather then asks: WorkLostABox() - a box of this button's work had no answer - and goes back at once
//    (the page stays as the pilot sees it, he is told, and presses again); a Save asks RfFieldsMissed, which says so in a box.
// dev/test_noanswer reads the source for both: a gather without its keep, a gather called with neither question behind it.
static bool WorkLostABox() // a box asked for in the button's work now in hand had no answer
{
    return BoxesLost != BoxesLostAtWork;
}
// WHAT THE PILOT TYPED STAYS ON THE PAGE (the tenth review). These pages take a typed field only when they gather - at a Save, at a tap on
// a choice - and after a box ("... NOTHING was sent. Please press Save again.") they draw themselves afresh from what is in hand: the
// numbers he had just typed were written over with the old ones, and "Save again" saved THOSE. While this is set, a page's drawing
// leaves its typed fields as the screen has them (it keeps them through a box): only its words, switches and rows are put right.
bool RfKeepTyped = false;
template <size_t N> struct BoxesWhole
{
    uint8_t *what;
    uint32_t lost;
    uint8_t was[N];
    explicit BoxesWhole(void *p) : what((uint8_t *)p), lost(BoxesLost) { memcpy(was, what, N); }
    ~BoxesWhole()
    {
        if (BoxesLost != lost)
            memcpy(what, was, N);
    }
};
#define KEEP_WHOLE(id, thing) BoxesWhole<sizeof(thing)> keepWhole_##id(&(thing))
static void NoteLateReply(const char *cmd, uint32_t ms, bool got)
{
    if (got && ms <= 400)
        return;
    char m[80];
    if (LogMustWait())
    { // B211 (the twelfth review; the released code had it): this older note wrote the card AT ONCE, the model in the air - an open, a write and a close
      // of the file, tens of milliseconds in which no packet goes out (B47). Kept for a quiet moment, and short, as B211's own notes are.
        if (got)
            snprintf(m, sizeof(m), "Late %lu ms: %.18s", (unsigned long)ms, cmd);
        else
            snprintf(m, sizeof(m), "No answer: %.24s", cmd);
        KeepScreenNote(m, false);
        return;
    }
    snprintf(m, sizeof(m), "Screen answer %s: '%s' after %lu ms B188", got ? "late" : "MISSING", cmd, (unsigned long)ms);
    LogText(m, strlen(m), true);
}
// B211, THE BOX'S PAGE: after a box's own answer, the "sendme" answer that was asked with it is read. 0: the box was read
// from the page this board put up. 1: the screen is showing another page (its keyboard, opened by a touch on a number box;
// whatever it is). 2: it did not say which page. For 1 and 2 the box's answer is no answer.
FLASHMEM static uint8_t BoxPageWrong()
{
    // Asked with the box: its answer is on the wire by now, or a round of the screen's loop away - and a busy screen's round is
    // long, so a screen that says its page is given 600 ms (one that never has, 60). In waits of 20 ms with the radio's packets
    // between them (the sixth review: the one wait of 60 ms flew nothing - CollectReply flies the model only in a long wait).
    const uint32_t longest = ScreenSaysPage ? 600 : 60, begun = millis();
    bool got = false;
    while (true)
    {
        uint16_t k = 0;
        NextionReplyWaitMs = 20;
        got = CollectReply(0x66, k);
        NextionReplyWaitMs = 100;
        if (got || (millis() - begun) >= longest)
            break;
        DelayWithDog(1);
    }
    if (!got)
    {
        if (ScreenPageUnsaid < 65535)
            ++ScreenPageUnsaid;
        if (ScreenSaysPage)
            NoteAnswerOwed(); // (the page's number, come late, would be taken for the NEXT box's: "the page was right" - said of another moment)
        return ScreenSaysPage ? 2 : 0; // a screen that says its page, and for this box did not: which page the box was read from is not
                                       // known - no answer. (A screen that has never said it: the box's answer is used, as it always was.)
    }
    const uint8_t id = (uint8_t)TextIn[1];
    NoteScreenPage(id);
    return (IsKeyboardPage(id) || (ScreenPageId != 0xFF && id != ScreenPageId)) ? 1 : 0;
}
// (B211, the tenth review: this, GetText and GetOtherValue wait 55 ms and more for the screen - they are in flash now, with the questions of
// Utilities.h: the fast memory had 2.2 kB left before its next 32 kB block)
FLASHMEM static uint32_t GetNumberReply(const char *CB, bool ofPage = true) // ofPage: a page's box (false: a system variable, which is no page's)
{
    uint32_t ValueIn = 0;
    // ClaudeFix-2-7-2026 Same discipline as the fixed GetText: FLUSH stale bytes first (a
    // leftover reply used to be parsed as THIS one -- the ArmingChannel bug
    // family, which also fed shifted-by-one PIDs/rates to the FC), then WAIT
    // for the framed 'q' reply instead of hoping it already arrived.
    StashPendingEventBytes(); // ClaudeFix-14-7-2026 rescue any waiting button press, don't flush it
    TextIn[0] = 0;
    if (ScreenRestartSeen || ScreenAnswerOwed || (ofPage && (PageChangedUnderGet || ModalWaits)))
        return 65535; // B211: the page these boxes are on has gone under an earlier get of this press's work (or a question box is up): no answer (not asked). And once the screen
                      // has started again, or owes an answer, NOTHING is asked of it until it has caught up - a system variable neither: an
                      // answer the screen owed from before would be taken for this one
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    const uint16_t mark = ScreenMarkCount; // (... from before the first of this asking's waits)
    NEXTION.print(CB);
    if (ofPage)
        NEXTION.print("\xFF\xFF\xFFsendme"); // B211: ... and, with it, which page the screen is showing (BoxPageWrong)
    EndSend();
    bool got;
    {
        uint16_t k = 0;
        NextionReplyWaitMs = NEXTION_GET_WAIT_MS; // (B152: 400; B188: 2000 - see NoteLateReply)
        const uint32_t asked = millis();
        got = CollectReply('q', k);   // (B69: frame by frame; a touch word ahead of the reply is kept, binary or not)
        NextionReplyWaitMs = 100;
        if (!got && !ScreenRestartSeen)
            NoteAnswerOwed(); // B211: waited for to the end, and not come: it may come yet (AN ANSWER THAT NEVER CAME MAY COME YET)
        const bool under = !ofPage && ScreenMarkCount != mark;
        if (under)
            got = false; // B211: a system variable is no page's - but a page command sent from INSIDE this wait (a box put up by the link's loss) read
                         // the wire for itself: whatever stands here now is not known to be this answer
        if (ScreenRestartSeen || (ofPage && PageChangedUnderGet))
        { // B211: the page was changed while this box's answer was awaited, or the screen started again: whatever came is not this box's - no answer
            got = false;
            if (ofPage && PageChangedUnderGet)
                NotePageChangedUnderGet(CB);
        }
        else
        {
            if (under)
                NotePageChangedUnderGet(CB); // (not "MISSING": it came, and was not used)
            else
                NoteLateReply(CB, millis() - asked, got);
            if (!got && ofPage)
                PageChangedUnderGet = true; // B211: an answer that NEVER CAME, in two seconds: the screen is not answering - it may be starting again, and
                                            // what it then says is another page's. No box after this one has an answer until this press's work is over
                                            // (nor is that work held up two seconds for every box that follows)
        }
        if (!got)
            TextIn[0] = 0;
    }
    if (TextIn[0] == 'q')
    {
        ValueIn = TextIn[1]; // Collect and build 32 bit value from 4 bytes
        ValueIn += (TextIn[2] << 8);
        ValueIn += (TextIn[3] << 16);
        ValueIn += (TextIn[4] << 24);
        if (IsMarkKind(ValueIn))
            ValueIn = 65535; // B211: a page's marker is never a box's value, by whatever way it came here (CollectReply lets none through): no answer
    }
    else
    {
        ValueIn = 65535; // = THERE WAS AN ERROR !
    }
    const uint8_t off = (ofPage && got) ? BoxPageWrong() : 0;
    if (off || (got && ScreenRestartSeen))
    { // B211: the screen was showing another page when it answered (or did not say which; or said meanwhile that it has started
      // again): no answer - for this box and the rest of this press's work
        PageChangedUnderGet = true;
        if (off)
            NoteBoxOffPage(CB, off == 2);
        ValueIn = 65535;
    }
    NextionGetPending = false; // B189
    return ValueIn;
}

uint32_t getvalue(char *nbox) // a component's val: "get <nbox>.val"
{
    char GET[] = "get ";
    char VAL[] = ".val";
    char CB[100];
    strcpy(CB, GET);
    strcat(CB, nbox);
    strcat(CB, VAL);
    return GetNumberReply(CB);
}

// B171 (2 Nov 2026; Malcolm: "I cannot see the date and time of the backup file by double clicking yet"): a SYSTEM variable
// (tch2 = where the finger lifted) is asked for by its bare name, "get tch2". B169 asked GetValue, whose "get tch2.val" named a
// component the screen has not got: the screen answered 0 for it, every tap looked like the left list, and no tap ever counted.
// 65535 when no reply came (as GetValue; nothing else is marked - a missed system variable fails no page's save).
uint32_t GetSysValue(const char *name)
{
    char GET[] = "get ";
    char CB[60];
    strcpy(CB, GET);
    strncat(CB, name, sizeof(CB) - sizeof(GET) - 1);
    return GetNumberReply(CB, false); // (no page's: asked whatever page shows - and whatever happened to a page's boxes before)
}

// B195 (Malcolm, 6 Nov 2026: the new Rotorflight settings are for the 16 MB screens only, "not included in the 4 meg version"):
// the screen says which build it runs (screen 1.11.186: "get ldrcmb" = 16 on FULL, 4 on STANDARD, 0 from an older screen).
// Only a yes is remembered: a screen updated to 1.11.186 while the Teensy runs on is asked again next time (the answer is instant).
FLASHMEM bool ScreenIsBig()
{
    static int8_t known = -1;   // -1 not known yet, 0 a 4 MB screen (it said 1-15), 1 a 16 MB one
    if (known < 0)
    {   // (B196, review: a 4 MB screen's answer is kept too - each save on a word page asks this now, and the screen's answer
        //  waits up to 2 s if it is busy; an older screen (0) or no answer (65535) is asked again: it may be updated meanwhile)
        const uint32_t v = GetSysValue("ldrcmb");
        if (v >= 16 && v < 1000) known = 1;
        else if (v >= 1 && v < 16) known = 0;
    }
    return known == 1;
}

/*********************************************************************************************************************************/

uint32_t GetValue(char *nbox)
{
    CRUMB(CRUMB_GETVALUE); // This function calls the function above until it returns no error

    uint32_t ValueIn = getvalue(nbox);   // B156: ONE ask of 400 ms, as GetText since B152 - a second ask would leave the first's late
                                         // reply to be read as the NEXT box's answer (box N+1 = box N: plausible, and undetectable)
    if (ValueIn == 65535)
    {
        if (!NextionTextMissed)
            snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", nbox);   // B187
        NextionTextMissed = true;
        BoxWasLost(nbox); // B211
    }   // B156: as GetText - a page gathering its boxes for a save checks RfFieldsMissed and sends NOTHING
                                    // (the PIDs and governor pages took 65535 as the value: 255 in a byte, 65535 in a word)
    return ValueIn;
}

/*********************************************************************************************************************************/
// (10 Nov 2026, the code review) The row a file list box on the screen says is chosen, or -1. Three places took GetValue
// straight as the row of TheFilesList (150 rows): a missed reply is 65535 and a list can be shorter than the box believes, so
// they read far past the list (a wild read on the Teensy, a strcpy of whatever lay there into a 30-byte name - and Delete then
// removed the file of THAT name). The lists are BuildDirectory's: ExportedFileCounter rows.
FLASHMEM int ChosenFileRow(const char *box)
{
    const uint32_t row = GetValue((char *)box);
    if (row >= ExportedFileCounter || row >= (uint32_t)(sizeof(TheFilesList) / sizeof(TheFilesList[0])))
        return -1;
    return (int)row;
}

// ***************************************************************************************************************
// This function gets Nextion textbox Text into a char array pointed to by * TheText. There better be room!
// It returns the length of array
// THE SCREEN IS ASKED "sendme" AND ITS ANSWER AWAITED (B187, RfGatherStart's own; a routine of its own since the eleventh review): in waits of 20 ms
// with the radio's packets between them, for so long at most. The screen answers its commands in order: once this has been answered everything
// queued ahead of it is done, and its loop is running. true: answered (the page it shows noted - another page than this board's: no box has an
// answer, PageChangedUnderGet). false: not in that time - a screen that says its page then OWES an answer (nothing more is asked of it).
FLASHMEM static bool ScreenSettles(uint32_t mostMs)
{
    bool settled = false;
    NextionGetPending = true; // B189
    NEXTION.print("sendme");
    EndSend();
    const uint32_t t0 = millis();
    while ((millis() - t0) < mostMs)
    {
        uint16_t k = 0;
        NextionReplyWaitMs = 20; // (B211: waits of 20 ms, the radio's packets between them - they were 100 ms each)
        const bool got = CollectReply(0x66, k);
        NextionReplyWaitMs = 100;
        if (got)
        {
            settled = true;
            NoteScreenPage((uint8_t)TextIn[1]);
            if (IsKeyboardPage((uint8_t)TextIn[1]) || (ScreenPageId != 0xFF && (uint8_t)TextIn[1] != ScreenPageId))
            { // B211: the screen is showing another page (its keyboard) as the boxes are about to be read: none of them has an answer
              // (the thirteenth review: the keyboard's page is that also while the page's own number is not yet known - as BoxPageWrong has it; a
              //  box was then asked of the keyboard's page, to be refused by its own look)
                PageChangedUnderGet = true;
                NoteBoxOffPage("sendme", false);
            }
            break;
        }
        DelayWithDog(2); // the radio's packets go on between windows
    }
    if (!settled && ScreenSaysPage && !ScreenRestartSeen)
        NoteAnswerOwed(); // B211: its "sendme" was not answered in that time: owed (the boxes that follow have no answer)
    NextionGetPending = false; // B189
    if (settled && !WordMayBeOpen())
        WordSettledFor = WordOpenMs; // (the twelfth review) answered behind the word's half second, and nothing more of a line came out with the answer: the word is settled
    return settled;
}
FLASHMEM uint16_t GetText(char *TextBoxName, char *TheText, uint16_t maxlen)
{
    TheText[0] = 0; // guarantee a defined result even if the Nextion doesn't answer with 'p'
    if (maxlen < 2)
        return 0;
    char get[] = "get ";
    char _txt[] = ".txt";
    char CB[100];
    uint16_t j = 0;
    strcpy(CB, get);
    strcat(CB, TextBoxName);
    strcat(CB, _txt);

    // ClaudeFix-2-7-2026 Discard any STALE bytes before asking. Leftovers from earlier traffic
    // (especially after heavy MSP work on the Rotorflight screens) used to be
    // parsed as THIS field's reply — so field N's answer became field N+1's
    // value. That is exactly how ArmingChannel "mysteriously" changed: the
    // Ratio box's "10.30" was read back as Arming and atoi'd to a perfectly
    // plausible channel 10, which then sailed past the range check.
    StashPendingEventBytes(); // ClaudeFix-14-7-2026 rescue any waiting button press, don't flush it
    TextIn[0] = 0; // if no reply arrives, stale TextIn content must not be re-parsed

    if (BoxesHaveNoPage())
    { // B211: the page this box is on was changed under an earlier get of this press's work, or the screen has started again: no answer (not asked)
        if (!NextionTextMissed)
            snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", TextBoxName);
        NextionTextMissed = true;
        BoxWasLost(TextBoxName);
        return 0;
    }
    if (WordMayBeOpen() || WordUnsettled())
    {   // B211 (the eleventh review, 15 Nov 2026): A WORD WITH NO END IS WAITED OUT - NOT PAID FOR WITH THE SAVE. A field screen (to 1.11.197) says a
        // line from its other core whenever its loop has stood still for a fifth of a second - and it stands still for that long behind a save's
        // own queue ("Sending ...", the colours: 325 to 606 ms measured, B187 and B188) and behind the page a question's way back puts up again.
        // That line is a bare word with no end: no text reply is believed for half a second from when it was READ (above) - and the first text box
        // was asked inside that half second whenever the stall had lasted a quarter to two thirds of a second: "Please press Save again", every
        // time (the released code saved: its settling wait threw the line away). Now the box is asked when the half second is over: waited for in
        // steps that fly the model, what the screen says meanwhile read in (another such word: another half second).
        // AND WHEN THE SCREEN'S LOOP IS RUNNING: half a second is a time, not a bound - a stall that is STILL going on holds the line's rest back,
        // and lets it go together with the answer to whatever was asked meanwhile: the rest, which may begin with p, glued in front of the box's
        // text (the reviewer's own word on his cure: that timing "becomes the usual one after a stall"). So once the half second is over the
        // screen is asked "sendme" first (ScreenSettles): its answer has a shape no line's rest can give it, and whatever comes out with it is
        // read in here - another half second, if it was the rest of a line. The box is asked when both hold: no such word for half a second, and
        // an answer since. No new look is begun after two and a half seconds (one begun just inside them is finished: a second more); then the
        // box is asked as before, to be refused as before; a screen that did not answer "sendme" owes an answer, and is asked nothing.
        // (The twelfth review: all this was entered only INSIDE the half second - and a box asked 510 ms behind the word, the rest still held,
        // was asked the old way. Entered now for as long as the word is UNSETTLED: no "sendme" answered behind its half second yet. And the
        // look that settles may find ANOTHER PAGE on the screen - its keyboard: the box is then not asked at all. It was: the way out of this
        // wait went round the look at "has the page gone?".)
        // (The thirteenth review: what stood on the wire behind the settling answer was read in BEHIND this wait - and the box asked all the same,
        //  though that read had just taken in ANOTHER such word: a sure "press Save again" where one more turn takes the box. Each turn ends with
        //  that read now, and the box is asked right behind a read that found no new word.)
        const uint32_t waitBegun = millis();
        bool settledNow = false;
        while (!settledNow && (millis() - waitBegun) < WORD_WAIT_MOST_MS) // (entered only with such a word open or unsettled: see the "if" this stands in)
        {
            if (WordMayBeOpen())
                DelayWithDog(10);
            else
                settledNow = ScreenSettles(WORD_SETTLE_MS); // (its loop is running)
            StashPendingEventBytes();                       // what the screen has said meanwhile - behind that answer too - is read in HERE
            settledNow = settledNow && !WordMayBeOpen();    // ... and nothing more of a line came out with the answer, or behind it
            if (BoxesHaveNoPage())
            { // (the page went, the screen started again or owes an answer, meanwhile - or the settling look found another page: no answer, as above)
                if (!NextionTextMissed)
                    snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", TextBoxName);
                NextionTextMissed = true;
                BoxWasLost(TextBoxName);
                return 0;
            }
        }
        TextIn[0] = 0; // (what was read in meanwhile is kept for the main loop: none of it is this box's answer)
    }
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    NEXTION.print("\xFF\xFF\xFFsendme"); // B211: ... and, with it, which page the screen is showing (BoxPageWrong)
    EndSend();

    // WAIT for the actual reply. The old code waited 20 MICROseconds — the
    // Nextion cannot even begin answering that fast, so what got read was
    // whatever the buffer already held (usually the PREVIOUS get's answer).
    // A reply is 'p' + text + FF FF FF: collect until that terminator, with
    // a timeout so a dead display can't hang us (normal replies take ~2 ms).
    bool got;
    {
        // B152 (Malcolm, 28 Oct 2026, Mehul's RAW 420 took off with no aileron: "when I save the rates in the transmitter
        // code, I get zero on roll when I read it back"): the window was 100 ms, and the first box asked for after a page's
        // "Sending ..." message - its 13 colour changes queued ahead of the ask - was answered later than that, read as "",
        // written as 0. Four hundred ms now. A box the screen still does not answer for sets NextionTextMissed, and a page
        // gathering its boxes for a save stops and says so (RfFieldsMissed) instead of sending zeros. ONE ask only: a
        // second ask would leave the first's late reply to be read as the NEXT box's answer.
        uint16_t k = 0;
        NextionReplyWaitMs = NEXTION_GET_WAIT_MS; // (B188: 2000)
        const uint32_t asked = millis();
        got = CollectReply('p', k);   // (B69: frame by frame; a touch word ahead of the reply is kept, binary or not)
        NextionReplyWaitMs = 100;
        if (!got && !ScreenRestartSeen)
            NoteAnswerOwed(); // B211: (as GetNumberReply) not come in its time: it may come yet
        if (PageChangedUnderGet || ScreenRestartSeen)
        { // B211: the page was changed while this box's answer was awaited, or the screen started again (as GetNumberReply): no answer
            got = false;
            if (PageChangedUnderGet)
                NotePageChangedUnderGet(CB);
        }
        else
        {
            if (TextReplyDoubted)
                NoteTextDoubted(CB); // (not "missing": it came, behind a word with no end, and was not believed)
            else
                NoteLateReply(CB, millis() - asked, got);
            if (!got)
                PageChangedUnderGet = true; // B211: an answer that never came (as GetNumberReply): no box after this one has an answer until this press's work is over
        }
        TextReplyDoubted = false;
        if (!got)
        {
            TextIn[0] = 0;
            if (!NextionTextMissed)
                snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", TextBoxName);   // B187: the first box missed, for the log
            NextionTextMissed = true;
            BoxWasLost(TextBoxName); // B211
        }
    }

    if (TextIn[0] == 'p')
    {
        while (TextIn[j + 1] < 0xFF && j < MAXTEXTIN - 2 && j < maxlen - 1)
        {   // ClaudeFix-2-7-2026 maxlen: the reply lands in CALLER buffers as small as 10 bytes
            // ("There better be room!" -- now there is)
            TheText[j] = TextIn[j + 1];
            ++j;
            KickTheDog(); // ??
        }
        TheText[j] = 0;
    }
    const uint8_t off = got ? BoxPageWrong() : 0;
    if (off || (got && ScreenRestartSeen))
    { // B211: the screen was showing another page when it answered (or did not say which; or has started again): no answer - for
      // this box and the rest of this press's work
        PageChangedUnderGet = true;
        if (off)
            NoteBoxOffPage(CB, off == 2);
        TheText[0] = 0;
        if (!NextionTextMissed)
            snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", TextBoxName);
        NextionTextMissed = true;
        BoxWasLost(TextBoxName);
    }
    NextionGetPending = false; // B189
    return strlen(TheText);
}
/*********************************************************************************************************************************/
// IS THE SCREEN STILL THE ONE THIS BOARD DREW ITS PAGE ON? (the eighth and ninth reviews, 15 Nov 2026.) A screen that has started
// again says so - but should every sign of it be lost, nothing here knows; its buttons are then not obeyed (they come unframed),
// but what a page ASKS BY ITSELF, with no button pressed - the Models page looks at its list twice a second, the Dual-rates page
// at its boxes - is answered by the page as the card has it: row 0, and MODEL 1 WAS LOADED BY ITSELF (found by a run). So
// before such a look ACTS on a box that has changed, the screen is asked for ITS SESSION'S NUMBER ("get ldrcup": IS IT STILL
// THE SAME SCREEN?, above): a screen that has started again has forgotten it.
// 0: the same screen - it said the number. 1: its restart is noted already. 2: nothing is known - it did not say the number
// (the "say this back" that follows then decides whether it has started again: ScreenOwedOver; nothing waits for that), or it
// has never said one yet, or a page's marker is still awaited, or a page command went out from inside this asking - and whoever
// asked does nothing this time.
// (A screen that says no numbers back - older than all this - cannot be asked: 0, and all is as it always was.)
FLASHMEM uint8_t ScreenSessionCheck()
{
    if (ScreenRestartSeen)
        return 1;
    if (ScreenMarkAwaited || ScreenAnswerOwed)
        return 2;
    if (!ScreenMarkCount || ScreenMarkMisses >= SCREEN_MARK_MISSES)
        return 0;
    if (!ScreenSaidSession)
        return ScreenSessionTries >= SCREEN_SESSION_TRIES ? 0 : 2; // (not said yet: it is being told - main.cpp ScreenKeepUp; ten times and no answer: it never will)
    StashPendingEventBytes();
    if (ScreenRestartSeen)
        return 1; // (its sign was on the wire, read in just now)
    const uint16_t heard = ScreenSessionSaidN, mark = ScreenMarkCount;
    const uint32_t begun = millis();
    NextionGetPending = true; // (as a box's get: the answer is ours)
    NEXTION.print("get ldrcup");
    EndSend();
    uint8_t answer = 2;
    while (true)
    {
        uint16_t k = 0;
        NextionReplyWaitMs = 20;
        const bool plain = CollectReply('q', k); // (the session's number is noted and passed over in there - TakeScreenMark; what is handed back is a plain number)
        NextionReplyWaitMs = 100;
        if (ScreenRestartSeen)
        {
            answer = 1;
            break;
        }
        if (ScreenSessionSaidN != heard)
        {
            answer = 0;
            break;
        }
        if (plain || (millis() - begun) >= 600)
            break; // a plain number where its session's number was asked for (0: it has forgotten), or nothing at all
        DelayWithDog(1); // the radio's packets go on between the waits
    }
    NextionGetPending = false;
    if (answer == 2)
        NoteAnswerOwed(); // (not said: the screen is asked again with a "say this back" behind it, and THAT decides - ScreenOwedOver)
    if (answer == 0 && ScreenMarkCount != mark)
        answer = 2; // (a page command went out from inside this asking - a box put up by the link's loss: the screen is the same, the page is not)
    return answer;
}
/*********************************************************************************************************************************/
// B152: after a page has gathered its boxes for a save - true = the screen left one unanswered (GetText, 400 ms); the pilot
// is told and the caller sends NOTHING. A box read as "" went to the flight controller as 0: Mehul's RAW 420 took off with no
// aileron (28 Oct 2026) after the rates were saved from this transmitter, bank by bank.
// B187 (Malcolm, 5 Nov 2026 evening, PID plus after B186: "The screen did not answer for one of the boxes, so NOTHING was sent",
// again): the screen's own /perf showed its loop held for 604 ms in one serial pass (loop_max_ms 604) - a get that waits 400 ms
// behind a page's queued commands (PID plus: 26 colour changes + the "Sending ..." message) is answered too late. Before a save
// gathers its boxes the screen is now asked "sendme" and its answer awaited (up to 2.5 s, in 100 ms windows with the radio kept
// going between them): the screen answers commands in order, so once it has answered, everything queued ahead is done and the
// gets that follow are answered at once. ONE ask per box stays (a second ask could be read as the next box's answer).
FLASHMEM void RfGatherStart()
{
    NextionTextMissed = false;
    NextionMissedBox[0] = 0;
    NextionMissedNoNumber = false;
    NextionSettledOk = false;
    RfSettleAsked = false;
    StashPendingEventBytes();
    if (BoxesHaveNoPage())
        return; // B211: the screen has started again, or the page these boxes are on was taken away under this button's work: nothing is asked,
                // and nothing waits (the boxes that follow have no answer)
    RfSettleAsked = true;
    NextionSettledOk = ScreenSettles(2500); // (the routine in front of GetText: not answered in two and a half seconds - owed, and the boxes that follow have no answer)
}
/*********************************************************************************************************************************/
FLASHMEM bool RfFieldsMissed(const char *page)
{
    if (!NextionTextMissed)
        return false;
    NextionTextMissed = false;
    const bool noNumber = NextionMissedNoNumber; // (the thirteenth review) the first box missed DID answer - with a text that is no number
    NextionMissedNoNumber = false;
    {   // B187: the box and the page go in the log - the next "did not answer" names itself
        char m[190]; // (B211: it was 90, and the line was cut)
        if (noNumber)
            snprintf(m, sizeof(m), "Refused: box %s holds a text that is no number (%s) - nothing was sent B211", NextionMissedBox, page);
        else
            snprintf(m, sizeof(m), "Refused: the screen did not answer for box %s (%s; the screen %s) B188", NextionMissedBox, page,
                     NextionSettledOk ? "had settled" : RfSettleAsked ? "never settled" : "was not asked: it had started again, it owed an answer, a question was up, or the page had gone");
        LogText(m, strlen(m), true);
    }
    PlaySound(WHAHWHAHMSG);
    if (PageLeftUnderWork)
        return true; // B211 (the tenth review): THIS BOARD ITSELF went to another page under this work (the power button's front page, the motor box): no box
                     // - its way back would put the save's page on the screen with this board on the other one. The sound, and the log's line
    if (noNumber)
    { // (the fourteenth review: "does not hold a number ... please type it again" was also said when the box was fine - its answer had come glued
      //  behind the rest of a line of the screen's, and there Save again DOES help: the words fit both. The fifteenth review: the box was named by
      //  its inner name - "tn7" - which says nothing to a pilot. The log's line above keeps that name; the box tells him what to look for.)
        MsgBox((char *)page, (char *)"A number box gave no number,\r\nso NOTHING was sent. Press Save again.\r\nIf this comes again: find the box that\r\nis empty or not a number, and type it.");
    }
    else
        MsgBox((char *)page, (char *)"The screen did not answer for one of\r\nthe boxes, so NOTHING was sent.\r\nPlease press Save again.");
    return true;
}
/*********************************************************************************************************************************/
FLASHMEM int GetOtherValue(char *nbox)
{
    // don't add .val as other thingy is already there ...
    double ValueIn = 0;
    char GET[] = "get ";
    char CB[100];
    strcpy(CB, GET);
    strcat(CB, nbox);
    StashPendingEventBytes(); // ClaudeFix-14-7-2026 rescue any waiting button press, don't flush it
    TextIn[0] = 0;
    if (BoxesHaveNoPage())
    {
        BoxWasLost(nbox);
        return 0; // B211: (as GetNumberReply) no answer, which is 0 here - and counted (NO ANSWER IS NOT A NUMBER)
    }
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    NEXTION.print("\xFF\xFF\xFFsendme"); // B211: ... and which page the screen is showing (BoxPageWrong)
    EndSend();
    bool got;
    {
        uint16_t k = 0;
        NextionReplyWaitMs = NEXTION_GET_WAIT_MS; // (B152: 400; B188: 2000 - see NoteLateReply)
        const uint32_t asked = millis();
        got = CollectReply('q', k);   // (B69: frame by frame; a touch word ahead of the reply is kept, binary or not)
        NextionReplyWaitMs = 100;
        if (!got && !ScreenRestartSeen)
            NoteAnswerOwed(); // B211: (as GetNumberReply) not come in its time: it may come yet
        if (PageChangedUnderGet || ScreenRestartSeen)
        { // B211: the page was changed while this answer was awaited, or the screen started again (as GetNumberReply): no answer
            got = false;
            if (PageChangedUnderGet)
                NotePageChangedUnderGet(CB);
        }
        else
        {
            NoteLateReply(CB, millis() - asked, got);
            if (!got)
                PageChangedUnderGet = true; // B211: an answer that never came (as GetNumberReply): no box after this one has an answer until this press's work is over
        }
        if (!got)
            TextIn[0] = 0;
    }
    bool lost = !got;
    if (TextIn[0] == 'q')
    {
        ValueIn = TextIn[1]; // Collect and build 32 bit value from 4 bytes
        ValueIn += (TextIn[2] << 8);
        ValueIn += (TextIn[3] << 16);
        ValueIn += (TextIn[4] << 24);
        if (IsMarkKind((uint32_t)ValueIn))
        {
            ValueIn = 0; // B211: a page's marker is never a box's value (as above): no answer, which is 0 here
            lost = true;
        }
    }
    const uint8_t off = got ? BoxPageWrong() : 0;
    if (off || (got && ScreenRestartSeen))
    { // B211: the screen was showing another page when it answered (or did not say which; or has started again): no answer (which is
      // 0 here) - for this box and the rest of this press's work
        PageChangedUnderGet = true;
        if (off)
            NoteBoxOffPage(CB, off == 2);
        ValueIn = 0;
        lost = true;
    }
    if (lost)
        BoxWasLost(nbox); // B211: 0 may be a real answer - the count tells (NO ANSWER IS NOT A NUMBER)
    NextionGetPending = false; // B189
    return ValueIn;
}

// ******************************************************************************************************************************
static inline void NextionTerminator()
{
    NEXTION.write(0xFF);
    NEXTION.write(0xFF);
    NEXTION.write(0xFF);
}

// ******************************************************************************************************************************
// (B211: FlushNextionInput - which threw away whatever the screen said for a while, presses and markers with it - and
// ReadNextionNumber - which took the first 0x71 on the wire for its answer - are gone: the picture question that used them
// is asked as every other question is, NextionFileExistsOnSD3 below.)
// ******************************************************************************************************************************
// (B211, the ninth review: GetIntFromTextBox - which asked for a box and read the wire blindly: no page's number, no "owed", 0 for
// no answer - was used by nothing, and is gone.)
// ******************************************************************************************************************************
// (B211, the tenth review: GetFloatFromTextBox - the other getter that read the wire blindly - was used by nothing either, and is gone.)

// ******************************************************************************************************************************
// 1 the file is there, 0 it is not, -1 no answer came (the screen was busy: not the same as "no")
int NextionFileExistsOnSD3(const char *filename);
bool NextionFileExistsOnSD(char *filename, bool verbose = false)
{
    (void)verbose; // (its bench words went with the old way of asking, B211)
    return NextionFileExistsOnSD3(filename) != 0; // (V2 B29: silence is not "no")
}
int NextionFileExistsOnSD3(const char *filename)
{
    char path[96];
    const int n = snprintf(path, sizeof(path), "sd0/images/%s", filename);
    if (n < 0 || n >= (int)sizeof(path))
        return 0;
    // B211: asked as every other question is. This used to throw away whatever the screen said for 50 ms (a press; a page's
    // marker) and then take the first 0x71 on the wire for its answer - so, asked straight after a page command (back from
    // Help to Model options, Models after its question box), it took the page's MARKER for "the picture is there" and left the
    // page's buttons dead until the marker was given up (found by the fourth review, 14 Nov 2026). Now what is on the wire is
    // read in frame by frame (a press kept, a marker noted), and the answer is read as any system variable's (GetSysValue:
    // the model is flown while it waits, a marker in front of the answer is passed over, two seconds at most).
    StashPendingEventBytes();
    NEXTION.print("findfile \"");
    NEXTION.print(path);
    NEXTION.print("\",sys0");
    NextionTerminator();
    const uint32_t v = GetSysValue("sys0");
    if (v == 65535)
        return -1; // (no answer: not the same as "no")
    return v != 0 ? 1 : 0;
}
/*********************************************************************************************************************************/
//             END OF NEXTION FUNCTIONS
/*********************************************************************************************************************************/
#endif