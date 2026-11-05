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
#define FRAME_MARK 0x7E
#define FRAME_GAP_US 20000           // the longest pause waited out inside a framed burst
bool ScreenFramesBursts = false;     // the screen has framed a burst this session: an unframed binary frame is a ghost
bool TextInFramed = false;           // the frame now in TextIn came framed
uint32_t FrameEnableSentMs = 0;      // when "ldrcframe=1" was last sent

void PendingPush(const uint8_t *f, uint16_t n, bool framed) // a frame kept for GetButtonPress
{
    if (n == 0 || PendingCount >= MAXPENDINGFRAMES || PendingEventLen + n >= sizeof(PendingEvent) - 1)
        return;
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
int ReadFramedRest(uint8_t *dst, uint16_t cap, uint16_t &len)
{
    uint8_t hdr[2];
    uint16_t have = 0, want = 0;
    len = 0;
    while (true)
    {
        const uint32_t quiet = micros();
        while (!NEXTION.available())
        {
            if ((micros() - quiet) >= FRAME_GAP_US)
                return -1;
            delayMicroseconds(10);
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
    }
}
void StashFramed(const uint8_t *p, uint16_t len) // a framed burst, kept whole
{
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

void StashFrame(const uint8_t *f, uint16_t n);
// B186 (Malcolm, 5 Nov 2026, PID plus: "The screen did not answer for one of the boxes, so NOTHING was sent", twice - the screen's
// own log showed all 26 answers sent): a PIPE LINE ("ldrctel ...\n", "ldrcrep ...\n") has no FF FF FF, and since screen 1.11.179
// the block's line is told again every 600 ms while its read window is open (up to 15 s after a page loads). One that came while
// a get waited was glued to the reply in front of it - "ldrctel 25:... p2.5 FF FF FF" - and the whole frame was stashed as a word:
// the reply lost, the save refused. A pipe line now ends at its newline wherever it is met, and is kept for GetButtonPress.
static bool PipeLineDone(const uint8_t *f, uint16_t n)
{
    return n >= 5 && f[n - 1] == '\n' && memcmp(f, "ldrc", 4) == 0;
}
static bool PipeLineOpen(const uint8_t *f, uint16_t n) // a pipe line begun and not yet ended
{
    return n >= 4 && memcmp(f, "ldrc", 4) == 0 && f[n - 1] != '\n';
}
// B189 (Malcolm, 5 Nov 2026 ~18:48, PID plus after B188: "Screen answer MISSING: 'get sw0.val' after 2001 ms" and 't20.txt',
// while the screen's /sent showed both answers SENT): the answer was read and THROWN AWAY by the transmitter itself. After a get,
// EndSend waits 55 ms in DelayWithDog, which flies the model (SendData); the model's telemetry is written to the screen meanwhile
// ("StillConnected.txt=Amps ..."), every SendText ends in GetReturnCode -> here, and here a frame beginning with p or q is "a late
// reply nobody waits for" (StashFrame) - so the answer that arrived in those 55 ms was dropped. Only with a model connected, any
// box at random. While a get waits for its answer (NextionGetPending), nothing else drains the line: the bytes stay for CollectReply.
bool NextionGetPending = false;
void StashPendingEventBytes() // replaces the blind pre-get flush (B69: frame by frame, so a button's code is kept too, not only a word)
{
    if (NextionGetPending)
        return; // B189
    uint8_t f[MAXPENDINGFRAME];   // (B186: was 64 - a pipe line of ten items is ~130 bytes)
    uint16_t n = 0, ffs = 0;
    while (true)
    {
        if (!NEXTION.available())
        { // B186: a pipe line still arriving is waited for (5 ms of quiet, as GetTextIn), not stashed in two halves
            if (!PipeLineOpen(f, n))
                break;
            const uint32_t quiet = micros();
            while (!NEXTION.available() && (micros() - quiet) < 5000)
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
        if (PipeLineDone(f, n))
        { // B186: a pipe line, whole
            StashFrame(f, n);
            n = 0;
            ffs = 0;
            continue;
        }
        if (b == 0xFF)
        {
            if (++ffs >= 3)
            {
                StashFrame(f, n >= 3 ? n - 3 : 0);
                n = 0;
                ffs = 0;
            }
        }
        else
            ffs = 0;
        delayMicroseconds(20); // one byte at 921600 baud takes ~11 us
    }
    if (n)
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
void StashFrame(const uint8_t *f, uint16_t n) // a frame without its FF FF FF
{
    if (n == 0)
        return;
    const uint8_t first = f[0];
    const bool code7 = first >= 0x80;                          // a button's 7-bit code (128 + n), 4 bytes
    const bool code24 = first == 0 && n == 4;                  // va0.val=n<<8: 00 n 00 00
    const bool word = first >= 0x20 && first < 0x7F;           // a word, "SendModel", "Import x.MOD" ...
    const bool reply = first == 'p' || (first == 'q' && n == 5); // B162: a late reply to a get (no button's burst begins with p or q)
    if (reply || !(code7 || code24 || word))
        return;                                                // return-code debris (01, 1A ...), or a reply nobody waits for
    PendingPush(f, n, false);
}
// The reply to a "get": the frame that begins with `expected` ('q' a value, 'p' a text), into TextIn (k = its length,
// terminator included). Other frames meanwhile are stashed. False: no such frame within 100 ms.
bool CollectReply(uint8_t expected, uint16_t &k)
{
    const uint32_t begun = millis();
    uint8_t ffs = 0;
    k = 0;
    uint32_t radioAt = begun;
    while ((millis() - begun) < NextionReplyWaitMs)   // (B152: 100 ms; B188: 2000 round a get - GetText and getvalue set it)
    {
        if (NextionReplyWaitMs > 400 && k == 0 && !NEXTION.available() && (millis() - radioAt) >= 20 && (millis() - begun) >= 100)
        { // B188: a long wait keeps the radio's packets going (between frames only: a reply half in is read on at once)
            radioAt = millis();
            DelayWithDog(1);
        }
        while (NEXTION.available())
        {
            const uint8_t b = NEXTION.read();
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
            if (PipeLineDone((const uint8_t *)TextIn, k))
            { // B186: a pipe line ahead of the reply: kept whole, and the reply still awaited
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
            if (TextIn[0] == expected)                        // the reply: done
                return true;
            // B162 (the yellow transmitter, 31 Oct 2026: the Help button still opened "No log yet today" after B160): the
            // screen's button codes and words carry NO terminator (its print sends the raw bytes), so a press that lands in
            // this window is glued to the reply - "HelpView:MODELS.TXT" q 05 00 00 00 FF FF FF - and the whole frame was
            // stashed as the press: the reply lost (400 ms, then 65535), and the word delivered with the reply's bytes on
            // its tail (B160 then opened nothing; before it, the log). A value reply is always q and 4 bytes: when a frame
            // ends with one, the press is what comes before it, and the reply is the reply.
            if (expected == 'q' && k >= 9 && TextIn[k - 8] == 'q')
            {
                StashFrame((const uint8_t *)TextIn, k - 8);
                memmove(TextIn, TextIn + k - 8, 8);
                k = 8;
                return true;
            }
            StashFrame((const uint8_t *)TextIn, k >= 3 ? k - 3 : 0);   // something else first: kept for GetButtonPress
            k = 0;
            ffs = 0;
        }
        KickTheDog();
    }
    return false;
}

void GetTextIn()
{
    delayMicroseconds(20);
    TextInFramed = false;
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
                ScreenFramesBursts = true;
                return;
            }
        }
        while (true)
        {
            while (NEXTION.available())
            {
                TextIn[j] = NEXTION.read();
                KickTheDog();
                if (j < MAXTEXTIN)
                    ++j;
                delayMicroseconds(20);
            }
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
        TextIn[j] = 0; // (B160: the read ends the text - what an earlier, unanswered read left behind is no part of it)
    }
}

/*********************************************************************************************************************************/
void LinkStrayFrame(); // LinkMode.h
bool GetButtonPress()
{
    if (PendingCount)
    {   // a touch event rescued from a get-reply window -- deliver it now (B177: one frame at a time, as it came)
        const uint16_t n = PendingLens[0];
        memcpy(TextIn, PendingEvent, n);
        TextIn[n] = 0;
        TextIn[n + 1] = 0;
        TextIn[n + 2] = 0;
        TextIn[n + 3] = 0;
        TextInFramed = PendingFramedFlags[0];
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
            return true;
        }
        GetTextIn();
        return true;
    }
    return false;
}

// B177: the frame in TextIn is to be obeyed? A framed one always. An unframed binary one (a 7-bit or 24-bit code) only while
// the screen has never framed (an older screen, or one just restarted) - and then the screen is asked to frame, once in 2 s.
// From a screen that frames, an unframed code is a split tail or a late reply's: logged, and not obeyed. Words always pass.
bool TextInIsGenuine()
{
    if (TextInFramed)
        return true;
    const uint8_t first = (uint8_t)TextIn[0];
    if (first != 0 && first < 0x80)
        return true; // a word: LDRCAWAKE, UKRULES, TIME=, FrontView ...
    if (first == 0 && TextIn[1] == 0 && TextIn[2] == 0)
        return true; // the 24-bit code 0 (Blank): nothing to obey - the screen's power-on bytes, a burst that never completed
    if (ScreenFramesBursts)
    {
        LogGhostFrame("an unframed code", (const uint8_t *)TextIn, 4);
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
void SendCommand(char *tbox)
{
    CRUMB(CRUMB_COMMAND);
    char page[] = "page ";
    char blankview[] = "BlankView";
    NEXTION.print(tbox);
    for (int i = 0; i < 3; ++i)
        NEXTION.write(0xff);
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
static void NoteLateReply(const char *cmd, uint32_t ms, bool got)
{
    if (got && ms <= 400)
        return;
    char m[80];
    snprintf(m, sizeof(m), "Screen answer %s: '%s' after %lu ms B188", got ? "late" : "MISSING", cmd, (unsigned long)ms);
    LogText(m, strlen(m), true);
}
static uint32_t GetNumberReply(const char *CB)
{
    uint32_t ValueIn = 0;
    // ClaudeFix-2-7-2026 Same discipline as the fixed GetText: FLUSH stale bytes first (a
    // leftover reply used to be parsed as THIS one -- the ArmingChannel bug
    // family, which also fed shifted-by-one PIDs/rates to the FC), then WAIT
    // for the framed 'q' reply instead of hoping it already arrived.
    StashPendingEventBytes(); // ClaudeFix-14-7-2026 rescue any waiting button press, don't flush it
    TextIn[0] = 0;
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    EndSend();
    {
        uint16_t k = 0;
        NextionReplyWaitMs = NEXTION_GET_WAIT_MS; // (B152: 400; B188: 2000 - see NoteLateReply)
        const uint32_t asked = millis();
        const bool got = CollectReply('q', k);   // (B69: frame by frame; a touch word ahead of the reply is kept, binary or not)
        NextionReplyWaitMs = 100;
        NextionGetPending = false; // B189
        NoteLateReply(CB, millis() - asked, got);
        if (!got)
            TextIn[0] = 0;
    }
    if (TextIn[0] == 'q')
    {
        ValueIn = TextIn[1]; // Collect and build 32 bit value from 4 bytes
        ValueIn += (TextIn[2] << 8);
        ValueIn += (TextIn[3] << 16);
        ValueIn += (TextIn[4] << 24);
    }
    else
    {
        ValueIn = 65535; // = THERE WAS AN ERROR !
    }
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
    return GetNumberReply(CB);
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
    }   // B156: as GetText - a page gathering its boxes for a save checks RfFieldsMissed and sends NOTHING
                                    // (the PIDs and governor pages took 65535 as the value: 255 in a byte, 65535 in a word)
    return ValueIn;
}

// ***************************************************************************************************************
// This function gets Nextion textbox Text into a char array pointed to by * TheText. There better be room!
// It returns the length of array
uint16_t GetText(char *TextBoxName, char *TheText, uint16_t maxlen)
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

    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    EndSend();

    // WAIT for the actual reply. The old code waited 20 MICROseconds — the
    // Nextion cannot even begin answering that fast, so what got read was
    // whatever the buffer already held (usually the PREVIOUS get's answer).
    // A reply is 'p' + text + FF FF FF: collect until that terminator, with
    // a timeout so a dead display can't hang us (normal replies take ~2 ms).
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
        const bool got = CollectReply('p', k);   // (B69: frame by frame; a touch word ahead of the reply is kept, binary or not)
        NextionReplyWaitMs = 100;
        NextionGetPending = false; // B189
        NoteLateReply(CB, millis() - asked, got);
        if (!got)
        {
            TextIn[0] = 0;
            if (!NextionTextMissed)
                snprintf(NextionMissedBox, sizeof(NextionMissedBox), "%s", TextBoxName);   // B187: the first box missed, for the log
            NextionTextMissed = true;
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
    return strlen(TheText);
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
    NextionSettledOk = false;
    StashPendingEventBytes();
    NextionGetPending = true; // B189
    NEXTION.print("sendme");
    EndSend();
    const uint32_t t0 = millis();
    while ((millis() - t0) < 2500)
    {
        uint16_t k = 0;
        NextionReplyWaitMs = 100;
        const bool got = CollectReply(0x66, k);
        NextionReplyWaitMs = 100;
        if (got)
        {
            NextionSettledOk = true;
            break;
        }
        DelayWithDog(2); // the radio's packets go on between windows
    }
    NextionGetPending = false; // B189
}
/*********************************************************************************************************************************/
FLASHMEM bool RfFieldsMissed(const char *page)
{
    if (!NextionTextMissed)
        return false;
    NextionTextMissed = false;
    {   // B187: the box and the page go in the log - the next "did not answer" names itself
        char m[90];
        snprintf(m, sizeof(m), "Save refused: the screen did not answer for box %s (%s; the screen %s) B188", NextionMissedBox, page,
                 NextionSettledOk ? "had settled" : "never settled");
        LogText(m, strlen(m), true);
    }
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)page, (char *)"The screen did not answer for one of\r\nthe boxes, so NOTHING was sent.\r\nPlease press Save again.");
    return true;
}
/*********************************************************************************************************************************/
int GetOtherValue(char *nbox)
{
    // don't add .val as other thingy is already there ...
    double ValueIn = 0;
    char GET[] = "get ";
    char CB[100];
    strcpy(CB, GET);
    strcat(CB, nbox);
    StashPendingEventBytes(); // ClaudeFix-14-7-2026 rescue any waiting button press, don't flush it
    TextIn[0] = 0;
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    EndSend();
    {
        uint16_t k = 0;
        NextionReplyWaitMs = NEXTION_GET_WAIT_MS; // (B152: 400; B188: 2000 - see NoteLateReply)
        const uint32_t asked = millis();
        const bool got = CollectReply('q', k);   // (B69: frame by frame; a touch word ahead of the reply is kept, binary or not)
        NextionReplyWaitMs = 100;
        NextionGetPending = false; // B189
        NoteLateReply(CB, millis() - asked, got);
        if (!got)
            TextIn[0] = 0;
    }
    if (TextIn[0] == 'q')
    {
        ValueIn = TextIn[1]; // Collect and build 32 bit value from 4 bytes
        ValueIn += (TextIn[2] << 8);
        ValueIn += (TextIn[3] << 16);
        ValueIn += (TextIn[4] << 24);
    }
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
static void FlushNextionInput(uint32_t ms = 30)
{
    uint32_t start = millis();
    while (millis() - start < ms)
    {
        while (NEXTION.available())
            (void)NEXTION.read();
        delay(1);
        KickTheDog();
    }
}

// ******************************************************************************************************************************
static bool ReadNextionNumber(int32_t &out, uint32_t timeout_ms)
{
    uint32_t start = millis();

    // wait for 0x71
    while (millis() - start < timeout_ms)
    {
        if (NEXTION.available())
        {
            if ((uint8_t)NEXTION.read() == 0x71)
                break;
        }
        delay(1);
        KickTheDog();
    }
    if (millis() - start >= timeout_ms)
        return false;

    uint8_t b[4];
    for (int i = 0; i < 4; i++)
    {
        uint32_t t0 = millis();
        while (!NEXTION.available())
        {
            if (millis() - t0 > timeout_ms)
                return false;
            delay(1);
            KickTheDog();
        }
        b[i] = (uint8_t)NEXTION.read();
    }

    out = (int32_t)((uint32_t)b[0] |
                    ((uint32_t)b[1] << 8) |
                    ((uint32_t)b[2] << 16) |
                    ((uint32_t)b[3] << 24));
    return true;
}
// ******************************************************************************************************************************
int GetIntFromTextBox(char *tbox)
{
    char get[] = "get ";
    char _txt[] = ".txt";
    char CB[100];
    uint8_t j = 0;
    char Text[50];
    strcpy(CB, get);
    strcat(CB, tbox);
    strcat(CB, _txt);
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    EndSend();
    GetTextIn();
    NextionGetPending = false; // B189
    if (TextIn[0] == 'p')
    {
        while (TextIn[j + 1] < 0xFF && j < sizeof(Text) - 1) // ClaudeFix-2-7-2026 bounded: a fragment reply used to copy forever (uint8_t j wraps, smashing the stack past Text[50])
        {
            Text[j] = TextIn[j + 1];
            ++j;
            KickTheDog(); // ??
        }
        Text[j] = 0;

        return atoi(Text);
    }
    return 0;
}
// ******************************************************************************************************************************
float GetFloatFromTextBox(char *tbox)
{
    char get[] = "get ";
    char _txt[] = ".txt";
    char CB[100];
    uint8_t j = 0;
    char Text[50];
    strcpy(CB, get);
    strcat(CB, tbox);
    strcat(CB, _txt);
    NextionGetPending = true; // B189: the answer is ours - no nested drain may take it
    NEXTION.print(CB);
    EndSend();
    GetTextIn();
    NextionGetPending = false; // B189
    if (TextIn[0] == 'p')
    {
        while (TextIn[j + 1] < 0xFF && j < sizeof(Text) - 1) // ClaudeFix-2-7-2026 bounded: a fragment reply used to copy forever (uint8_t j wraps, smashing the stack past Text[50])
        {
            Text[j] = TextIn[j + 1];
            ++j;
            KickTheDog(); // ??
        }
        Text[j] = 0;

        return atof(Text);
    }
    return 0;
}

// ******************************************************************************************************************************
// 1 the file is there, 0 it is not, -1 no answer came (the screen was busy: not the same as "no")
int NextionFileExistsOnSD3(const char *filename);
bool NextionFileExistsOnSD(char *filename, bool verbose = false)
{
    if (!verbose)
        return NextionFileExistsOnSD3(filename) != 0; // (V2 B29: silence is not "no")
    // filename like "Adrians.jpg" in /images
    char path[96];
    int n = snprintf(path, sizeof(path), "sd0/images/%s", filename); // <-- changed
    if (n < 0 || n >= (int)sizeof(path))
        return false;

    if (verbose)
    {
        Look1("NextionFileExists: ");
        Look(path);
    }

    FlushNextionInput(50);

    NEXTION.print("findfile \"");
    NEXTION.print(path);
    NEXTION.print("\",sys0");
    NextionTerminator();

    delay(10);

    NEXTION.print("get sys0");
    NextionTerminator();

    int32_t v = 0;
    if (!ReadNextionNumber(v, 500))
    {
        if (verbose)
            Look("  read sys0 FAILED.");
        return false;
    }

    if (verbose)
    {
        Look1("  sys0 = ");
        Look(v);
    }
    return (v != 0);
}
int NextionFileExistsOnSD3(const char *filename)
{
    char path[96];
    const int n = snprintf(path, sizeof(path), "sd0/images/%s", filename);
    if (n < 0 || n >= (int)sizeof(path))
        return 0;
    FlushNextionInput(50);
    NEXTION.print("findfile \"");
    NEXTION.print(path);
    NEXTION.print("\",sys0");
    NextionTerminator();
    delay(10);
    NEXTION.print("get sys0");
    NextionTerminator();
    int32_t v = 0;
    if (!ReadNextionNumber(v, 1000)) // (a page just loaded, with the front screen's boxes to draw, can take the screen a moment)
        return -1;
    return v != 0 ? 1 : 0;
}
/*********************************************************************************************************************************/
//             END OF NEXTION FUNCTIONS
/*********************************************************************************************************************************/
#endif