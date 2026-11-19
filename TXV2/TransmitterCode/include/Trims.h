// *********************************************** Trims.h *******************************************

#include <Arduino.h>
#include "1Definitions.h"
#ifndef TRIMS_H
#define TRIMS_H

// **********************************************************************************************************************************
void StartTrimView()
{
    char n0[] = "n0";
    char c0[] = "c0";
    SendCommand(pTrimView);
    CurrentView = TRIM_VIEW;
    SendValue(n0, TrimMultiplier);
    SendValue(c0, CopyTrimsToAll);
    ForceDataRedisplay();
    UpdateModelsNameEveryWhere(); // also updates trimview (If CurrentView == TRIM_VIEW!! :-)
    ClearText();                  //
}

/******************************************************************************************************************************/
void StartTrimDefView()
{

    CurrentView = TRIMDEFVIEW;
    SendCommand(pTrimDefView);
    ResetAllTrims();
    BlueLedOn();
    CurrentMode = SENDNOTHING;
    for (int i = 0; i < 4; ++i)
        TrimDefined[i] = false;
    DefiningTrims = true;
}
/******************************************************************************************************************************/
void DefineTrimsEnd()
{ // exit from trim defining screen
    char pCalibrateView[] = "page CalibrateView";
    CurrentView = TXSETUPVIEW;
    SendCommand(pCalibrateView);
    Force_ReDisplay();
    CurrentView = CALIBRATEVIEW;
    DefiningTrims = false;
    CurrentMode = NORMAL;
    SaveTransmitterParameters();
    UpdateModelsNameEveryWhere();
}
/******************************************************************************************************************************/
void ResetAllTrims()
{

    if (SticksMode == 1)
    {
        TrimNumber[0] = TRIM1A; // these will change when redefined
        TrimNumber[1] = TRIM1B;
        TrimNumber[2] = TRIM2A;
        TrimNumber[3] = TRIM2B;
        TrimNumber[4] = TRIM3A;
        TrimNumber[5] = TRIM3B;
        TrimNumber[6] = TRIM4A;
        TrimNumber[7] = TRIM4B;
    }

    if (SticksMode == 2)
    {
        TrimNumber[0] = TRIM1A;
        TrimNumber[1] = TRIM1B;
        TrimNumber[4] = TRIM2A;
        TrimNumber[5] = TRIM2B;
        TrimNumber[2] = TRIM3A;
        TrimNumber[3] = TRIM3B;
        TrimNumber[6] = TRIM4A;
        TrimNumber[7] = TRIM4B;
    }
}

/************************************************************************************************************/

void SetATrimDefinition(int i)
{
    char AilDone[] = "Aileron trim: done";
    char EleDone[] = "Elevator trim: done";
    char ThrDone[] = "Throttle trim: done";
    char RudDone[] = "Rudder trim: done";

    char ail[] = "ail";
    char ele[] = "ele";
    char thr[] = "thr";
    char rud[] = "rud";

    // Aileron
    if (!TrimDefined[0])
    {
        if ((i == 0) || (i == 1))
        {
            PlaySound(BEEPCOMPLETE);
            SendText(ail, AilDone);
            TrimDefined[0] = true;
        }
        if (i == 0)
        {
            TrimNumber[0] = TRIM1A;
            TrimNumber[1] = TRIM1B;
        }
        if (i == 1)
        {
            TrimNumber[1] = TRIM1A;
            TrimNumber[0] = TRIM1B;
        }
    }

    if (SticksMode == 1)
    {
        // Elevator
        if (!TrimDefined[1])
        {
            if ((i == 2) || (i == 3))
            {
                PlaySound(BEEPCOMPLETE);
                SendText(ele, EleDone);
                TrimDefined[1] = true;
            }
            if (i == 3)
            {
                TrimNumber[2] = TRIM2A;
                TrimNumber[3] = TRIM2B;
            }
            if (i == 2)
            {
                TrimNumber[3] = TRIM2A;
                TrimNumber[2] = TRIM2B;
            }
        }

        // Throttle
        if (!TrimDefined[2])
        {
            if ((i == 4) || (i == 5))
            {
                PlaySound(BEEPCOMPLETE);
                SendText(thr, ThrDone);
                TrimDefined[2] = true;
            }
            if (i == 4)
            {
                TrimNumber[4] = TRIM3A; 
                TrimNumber[5] = TRIM3B;
            }
            if (i == 5)
            {
                TrimNumber[5] = TRIM3A;
                TrimNumber[4] = TRIM3B;
            }
        }
    }

    if (SticksMode == 2)
    {
        // Throttle
        if (!TrimDefined[1])
        {
            if ((i == 4) || (i == 5))
            {
                PlaySound(BEEPCOMPLETE);
                SendText(thr, ThrDone);
                TrimDefined[1] = true;
            }
            if (i == 5)
            {
                TrimNumber[5] = TRIM2A;
                TrimNumber[4] = TRIM2B;
            }
            if (i == 4)
            {
                TrimNumber[4] = TRIM2A;
                TrimNumber[5] = TRIM2B;
            }
        }

        // Elevator
        if (!TrimDefined[2])
        {
            if ((i == 2) || (i == 3))
            {
                PlaySound(BEEPCOMPLETE);
                SendText(ele, EleDone);
                TrimDefined[2] = true;
            }
            if (i == 3)
            {
                TrimNumber[2] = TRIM3A;
                TrimNumber[3] = TRIM3B;
            }
            if (i == 2)
            {
                TrimNumber[3] = TRIM3A;
                TrimNumber[2] = TRIM3B;
            }
        }
    }

    // Rudder
    if (!TrimDefined[3])
    {
        if ((i == 6) || (i == 7))
        {
            PlaySound(BEEPCOMPLETE);
            SendText(rud, RudDone);
            TrimDefined[3] = true;
        }
        if (i == 6)
        {
            TrimNumber[6] = TRIM4A;
            TrimNumber[7] = TRIM4B;
        }
        if (i == 7)
        {
            TrimNumber[7] = TRIM4A;
            TrimNumber[6] = TRIM4B;
        }
    }
}

/************************************************************************************************************/

void CheckHardwareTrims()
{
    CRUMB(CRUMB_HWTRIMS);
    if ((millis() - TrimTimer) < TrimRepeatSpeed)
        return; // check occasionally for trim press
    TrimTimer = millis();
    for (int i = 0; i < 8; ++i)
    {
        if (TrimSwitch[i])
        {
            if (DefiningTrims)
            {
                SetATrimDefinition(i);
                return;
            }
            MoveaTrim(i);
            // TransmitterLastManaged = 0;                     //  to speed up repeat
            TrimRepeatSpeed -= (TrimRepeatSpeed / 4); //  accelerate repeat...
            if (TrimRepeatSpeed < 10)
                TrimRepeatSpeed = 30; //  ... up to a point...
        }
    }
}

/*********************************************************************************************************************************/

/**
 * Retrieves the trim amount for the specified input channel.
 *
 * @param InputChannel The input channel for which to retrieve the trim amount.
 * @return The trim amount for the specified input channel.
 */
int GetTrimAmount(uint8_t InputChannel)
{
    int tt = InputChannel;
    if (SticksMode == 2)
    {
        if (InputChannel == 1)
            tt = 2;
        if (InputChannel == 2)
            tt = 1;
    }
    return (Trims[Bank][tt] - 80) * TrimMultiplier;
}

/*********************************************************************************************************************************/
/**
 * Updates the trim view based on the current trim values.
 */
void UpdateTrimView()
{
    CRUMB(CRUMB_TRIMVIEW);
    uint8_t p;
    char TrimViewChannels[4][4] = {"ch1", "ch4", "ch2", "ch3"};
    char TrimViewNumbers[4][3] = {"n1", "n4", "n2", "n3"};
    char TrimChannelNames[4][3] = {"c1", "c2", "c3", "c4"};

    if (CurrentView == FRONTVIEW || (CurrentView == TRIM_VIEW))
    {
        for (int i = 0; i < 4; ++i)
        {
            p = i;
            if (SticksMode == 2)
            {
                if (i == 1)
                    p = 2;
                if (i == 2)
                    p = 1;
            }
            uint8_t pp = InputTrim[p];
            if (LastTrim[Bank][pp] != Trims[Bank][pp])
            {
                LastTrim[Bank][pp] = Trims[Bank][pp];
                SendValue(TrimViewChannels[p], (Trims[Bank][pp]));
                SendValue(TrimViewNumbers[p], (Trims[Bank][pp] - 80));
                if (CurrentView == TRIM_VIEW)
                    SendText(TrimChannelNames[p], ChannelNames[pp]); // V1B B23: by p, as the slider and number are (by i, mode 2 put "Throttle" over the elevator trim)
            }
        }
    }
}

/*********************************************************************************************************************************/

FLASHMEM void CentreTrims()
{
    for (int j = 0; j <= BANKS_USED; ++j)
    {
        for (int i = 0; i < CHANNELSUSED; ++i)
        {
            Trims[j][i] = 80;
        }
    }
}
/*********************************************************************************************************************************/
void CheckSavedTrimValues()
{
    bool OK = true;
    for (int i = 0; i < 4; ++i)
    {
        if ((InputTrim[i] > 15) || (InputTrim[i] < 0))
            OK = false;
    }
    if (!OK)
    {
        for (int i = 0; i < 4; ++i)
        {
            InputTrim[i] = i;
        }
    }
}
/*********************************************************************************************************************************/
void CheckTrimValues()
{
    bool KO = false;
    for (int j = 0; j < 8; ++j)
    {
        if ((TrimNumber[j] > TRIM4B) || (TrimNumber[j] < TRIM1A))
            KO = true;
    }
    if (KO)
        ResetAllTrims();
}

/******************************************************************************************************************************/

static bool SubTrimOldPageSaid = false; // B211: the page's title has said, since the page was put up, that its file is an older one (SubTrimOldPage, below)
static void SubTrimStarts();            // (below)
/// @brief
void StartSubTrimView()
{ // Subtrim view start

    SendCommand(pSubTrimView);
    SubTrimToEdit = 0;
    SubTrimOldPageSaid = false;
    SubTrimStarts(); // (nothing of the last visit to the page is owed to this one)
    CurrentView = SUBTRIMVIEW;
    UpdateButtonLabels(); // (B211: the sixteen boxes as the model has them, and the page told to set its slider by its own channel's box: SubTrimPageOut, below)
    UpdateModelsNameEveryWhere();
}

/******************************************************************************************************************************/
// B211 (the eleventh, twelfth and thirteenth reviews, 15 Nov 2026): THE SUB-TRIM PAGE - A CHANGE IS TAKEN ONLY WHEN IT STARTS FROM WHAT THE MODEL HAS.
// The page (32.json) works by itself. A channel's number tapped sets s0, says "StCH" and puts the slider on that channel's number; the slider,
// Zero, "+" and "-" set the slider's number n0, copy it into the chosen channel's own box (n00, n1 .. n15) and say "StEDIT". As released, the page
// did not say WHICH channel a "StEDIT" was made on, nor WHAT it made, and a tapped channel did not put ITS number into n0 (only this board's answer
// to "StCH" did): this board stored n0 in "the channel being edited" - its own idea of the channel - and the page itself wrote "the channel
// before's value + 1" into a channel just tapped. Three cures in three reviews ASKED THE PAGE AFTERWARDS what the word had meant (the page's
// channel and that channel's box; this board "arriving" on a channel, its own writes read back; "the channel just left gives its box once") - and
// each time a reviewer found a road by which the answer was no longer true when it came: the page tapped on meanwhile on a screen a quarter
// second behind, the page come back from Help, the channel left asked last, a finger resting on the slider while this board wrote the slider
// back under it.
// SO THE PAGE SAYS WHAT IT DID (the screen's files that ship with this release - its hmi/subtrim_words.py):
//  - "StEDIT" comes with its numbers in the same burst (22 bytes: the word, then four bytes each, low byte first): the channel (1 to 16), the
//    slider's number AS IT STOOD, what the touch made of it - and that last number once more (the fourteenth review: a character of the screen's
//    own that falls into a burst moves the bytes behind it; a burst whose two last numbers differ is not taken);
//  - the slider says so when the finger LANDS on it, at each of its moves, and once more behind its release;
//  - a tapped channel puts its own box into the slider's number; "+", "-" and the slider stop at 117 either way (what the card keeps).
// AND THE RULE HERE IS ONE LINE: THE CHANGE IS TAKEN WHEN "AS IT STOOD" IS EXACTLY WHAT THE MODEL HAS FOR THAT CHANNEL. What is stored is then one
// touch away from the model's own number, on the channel the page showed as it was touched - whatever else went on: a tap never heard, a word
// lost or not kept for want of room, the page come back from Help or the screen saver, another model read under it, this board's own writes
// still on their way, a screen a second behind. Nothing is asked of the page, nothing waits, nothing is concluded.
// A change that does not start from the model's number is NOT TAKEN, and that channel is put right on the page (its box written, and the page told
// to set its slider by its own box): the pilot sees his touch undone, and his next one counts from the right number. (A finger still resting on the
// slider: the screen puts the slider back under the finger and says so - from the right number now: taken.)
// THE FOURTEENTH REVIEW'S FOUR RULES (16 Nov 2026), each in its place below: NOTHING IS TAKEN UNTIL THE PAGE HAS SAID THIS MODEL'S NUMBERS DONE
// (SubTrimShown: another model read under the open page); THE PAGE PUT UP AGAIN WITHOUT ITS START IS WRITTEN OUT (SubTrimPageBack: Help's way back,
// the screen saver's); OK STAYS WHILE A PUTTING-RIGHT IS OWED, OR ON ITS WAY (EndSubTrimView: what OK saves is what the page showed); a change not
// taken leaves a line in the log.
// A page file from before this release says its word alone (6 bytes): NOTHING is taken, the page's title says that the screen's files want
// updating ("Check for update" brings them with this firmware), and the channels' boxes are written out as the model has them when he has paused. An older firmware finds "StEDIT" at the head of the new burst and works as it did.
// What can still be lost is a touch whose WORD never reaches this board: the page then shows a number the model has not got, until the next
// touch on that channel is refused and the channel put right. A sub trim is never a number the pilot did not make on that channel
// (dev/test_wholepage/scene_subtrim_storm holds that at every pass).
// THE MODEL TAKES WHAT THE CARD KEEPS (the twelfth review; the released code had it): the card's reader (SDcard.h ReadOneModel) centres a sub trim
// it finds below 10 or above 244 - one beyond 117 either way was flown today and was 0 at the next switch-on, without a word. The page stops there
// now; a number beyond it (an older page file's) is not taken.
#define SUBTRIM_MOST 117
#define SUBTRIM_REST_MS 600        // the pilot has paused: no word of the page's for so long
#define SUBTRIM_DONE_WAIT_MS 2000  // OK waits for the page's "done" of this board's last click no longer than this (a "done" lost on the wire) ...
#define SUBTRIM_ASK_AGAIN_MOST 2   // ... then clicks once more, and waits again - so often at most (EndSubTrimView)
// (SUBTRIM_WORD_BYTES, SUBTRIM_DONE_BYTES: 1Definitions.h - 22 and 14. THE LAST NUMBER OF EITHER BURST IS SAID TWICE, and nothing is taken or believed
//  when the two do not agree. The fourteenth review, by reading: on a field screen a character of its Bluetooth library's own lines can fall INSIDE a
//  burst and move the bytes behind it - in front of the last number of a burst that made 0 it read as that character's code, 32 to 116: within 117,
//  taken. One byte more anywhere in a burst and its two last numbers differ.)
// THIS BOARD WRITES THE CHANNELS' BOXES - AND THE PAGE SETS ITS OWN SLIDER. A channel's box, written as the model has it, is right for that channel
// wherever the page stands. The slider and the slider's number belong to the channel the page SHOWS, which this board does not know for sure (a tap
// tells it nothing): the page's part "rs", clicked, puts both on the shown channel's box. (This board wrote them itself "for the channel the page was
// last heard on": the author's storm - a screen 133 ms behind - left the slider on another channel's number.)
// AND WHAT THIS BOARD WRITES CAN LAND ON TOP OF WHAT THE PILOT DID NEXT (a screen that answers late: the putting-right of one touch landing behind the
// next, which was taken). So THE PAGE SAYS WHEN IT HAS DONE WHAT THIS BOARD ASKED: every batch of this board's writes ends with its click of "rs",
// and in front of the click it gives the page the click's number (the page's variable "rsn"); the part "rs" says "StEDIT" and that number back when
// it has run (fourteen bytes: the number twice) - the writes in front of it have landed by then, in their order. After a change that was not taken - and after one TAKEN
// WHILE THE LAST CLICK HAS NOT BEEN SAID DONE - the page is written out ONCE MORE when he has paused (SubTrimPoll, from the main loop: no question, no
// wait): whatever landed on top of whatever, the page then shows what the model has. (The rule was "taken within a second of this board's last
// write": the author's storm, run with other seeds, met a screen whose loop stood still for two seconds with a writing-out waiting in it - a touch
// as it woke was taken, the old writing-out landed on top, and nothing was owed.)
extern uint16_t PendingDropped; // (Nextion.h: the frames not kept for want of room)
extern uint8_t PendingCount;
static uint16_t SubTrimAsked = 0;      // the number of this board's last click of "rs" (one more with every click; never 0 once it has clicked)
static uint16_t SubTrimDone = 0;       // ... and the last one the page has said done
static uint32_t SubTrimAskedMs = 0;    // ... and when that last click went
static bool SubTrimShown = false;      // the page has said done a click made since THIS MODEL'S numbers were written out to it: what it shows is this model's
static bool SubTrimSaysDone = false;   // the page is one that SAYS "done": since this board started a "done" has been heard, or a touch's burst in this release's
                                       // form has come from it (the page file from before does neither: its word comes alone)
static uint8_t SubTrimAskedAgain = 0;  // how often OK has clicked "rs" once more, the page not having said the last click done for two seconds (EndSubTrimView)
static bool SubTrimNoteSaid = false;   // (once a visit) the log has its line of a change not taken, or of words not kept
static uint32_t SubTrimWordMs = 0;     // when a word of the page's was last served
static bool SubTrimSettleDue = false;  // the page is to be written out once more when the pilot has paused
static uint16_t SubTrimDropsSeen = 0;  // PendingDropped as last looked at
FLASHMEM static void SubTrimBoxName(uint8_t ch, char *box) // channel 0 to 15: n00, n1 .. n15 (the page's "n0" is the slider's number)
{
    if (ch)
        snprintf(box, 8, "n%u", (unsigned)ch);
    else
        strcpy(box, "n00");
}
FLASHMEM static void SubTrimBoxOut(uint8_t ch) // a channel's own box, as the model has it
{
    char box[8];
    SubTrimBoxName(ch, box);
    SendValue(box, (int)SubTrims[ch] - 127);
}
FLASHMEM static void SubTrimResync() // the page puts its slider, and the slider's number, on the box of the channel it shows - and says this click's number back when
{                                    // it has (a page file from before has neither part: nothing happens, nothing is said)
    if (++SubTrimAsked == 0)
        SubTrimAsked = 1;
    SubTrimAskedAgain = 0; // (the seventeenth review) A NEW CLICK - a writing-out, a putting-right - HAS ITS OWN TWO CHANCES: behind a spent count the putting-right of
                           // a change not taken was left on the clock by one stall. (EndSubTrimView counts its own click behind this.)
    SubTrimAskedMs = millis();
    SendValue((char *)"rsn", SubTrimAsked);
    SendCommand((char *)"click rs,0");
}
FLASHMEM void SubTrimPageOut(bool fresh) // main.cpp UpdateButtonLabels (fresh): the page as the model has it - the page is put up, or ANOTHER MODEL was read into
{                                        // memory under it. (The twelfth review, released code: only the sixteen boxes went out - the slider's number stayed the
                                         //  old model's, and "+" made "the old model's value + 1" of the new model's channel.)
    if (fresh)
        SubTrimAskedAgain = 0; // (the sixteenth review: A FRESH WRITING-OUT BEGINS OK'S COUNT OF "CLICKS ONCE MORE" AFRESH. It was begun afresh by a "done" and
                               //  by the page put up only: two "done"s lost left it spent - and another model read under a screen that stood still was
                               //  then left by the first OK past the two seconds, the page showing the model before)
    if (fresh)
        SubTrimShown = false; // B211 (the fourteenth review): NOTHING IS TAKEN UNTIL THE PAGE HAS SAID THIS WRITING-OUT (or a later one) DONE. Another model
                              // read under the open page (a pupil's transmitter): a touch made on the OLD model's page, its word served behind the read,
                              // was taken into the NEW model whenever both had the same number on that channel - 7 % of the changes behind a model's
                              // read in the reviewer's storm. (Should the "done" be lost: his first touch is not taken, its putting-right is said done.)
    for (uint8_t ch = 0; ch < 16; ++ch)
        SubTrimBoxOut(ch);
    SubTrimResync();
}
FLASHMEM static void SubTrimNote(const char *kept, const char *whole) // once a visit: a line for the log (kept for a quiet moment while the model may fly)
{
    if (SubTrimNoteSaid)
        return;
    SubTrimNoteSaid = true;
    if (LogMustWait())
    {
        KeepScreenNote(kept, false);
        return;
    }
    char line[190];
    strlcpy(line, whole, sizeof(line));
    LogText(line, strlen(line), true);
}
FLASHMEM static void SubTrimOldPage() // the page's word came alone: its file is from before this release. Said once in the page's title, and in the log
{
    if (SubTrimOldPageSaid)
        return;
    SubTrimOldPageSaid = true;
    char t0[] = "t0";
    SendCommand((char *)"vis ModelName,0"); // (the model's name stands OVER the left third of the title's bar: out of the way, so that all of this is read)
    SendText(t0, (char *)"Subtrim: run Check for update first");
    PlaySound(WHAHWHAHMSG);
    if (LogMustWait())
    {
        KeepScreenNote("Sub-trim page file old: not taken", false);
        return;
    }
    char line[] = "Sub-trim page: the screen's page file is older than this firmware - nothing is taken from it (run Check for update) B211";
    LogText(line, strlen(line), true);
}
static int32_t SubTrimNumberAt(const uint8_t *p) // four bytes, the low one first (the screen's print of a number)
{
    return (int32_t)((uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24));
}
// "StEDIT" has been served (main.cpp ButtonWasPressed, on this page only): w its burst, n its bytes, framed: how it came.
FLASHMEM void SubTrimWord(const uint8_t *w, uint16_t n, bool framed)
{
    if (n < 6 || memcmp(w, "StEDIT", 6))
        return; // (the word is not what the burst begins with: nothing)
    if (n == SUBTRIM_DONE_BYTES)
    { // THE PAGE SAYS "DONE": its part "rs" has run - what this board wrote in front of that click has landed. Only the number of this board's LAST
      // click counts (an older one says nothing of the writes behind it), only in a burst that came framed, and only when its two numbers agree
        const int32_t done = SubTrimNumberAt(w + 6);
        if (framed && done == SubTrimNumberAt(w + 10) && done == (int32_t)SubTrimAsked)
        {
            SubTrimDone = SubTrimAsked;
            SubTrimShown = true; // (every write since the page was put up, or another model read, has landed: what it shows is this model's)
            SubTrimSaysDone = true;
            SubTrimAskedAgain = 0;
        }
        return;
    }
    if (!framed || n != SUBTRIM_WORD_BYTES)
    { // the word alone, or not as this release's page says it: an older page file (or a screen that frames nothing - older than all of this)
        SubTrimOldPage();
        SubTrimWordMs = millis() | 1;
        SubTrimSettleDue = true; // (the page has made a number of it that the model has NOT got: the sixteen boxes as the model has them, when he has paused)
        return;
    }
    SubTrimSaysDone = true; // (the fifteenth review) A BURST IN THIS RELEASE'S FORM: the page file is this release's - it says "done" behind every click.
                            // OK's wait (EndSubTrimView) asked whether a "done" had ever been HEARD: on the first visit since power-on, the first one still
                            // on its way, a touch that was not taken and OK pressed twice saved the model behind it - the page showing the touch.
    const int32_t ch = SubTrimNumberAt(w + 6), stood = SubTrimNumberAt(w + 10), made = SubTrimNumberAt(w + 14), again = SubTrimNumberAt(w + 18);
    SubTrimWordMs = millis() | 1;
    if (ch < 1 || ch > 16)
    { // no channel of the page's (a character that fell into the burst's channel): nothing can be put right by its name - the whole page, when he has paused
        SubTrimSettleDue = true;
        return;
    }
    const uint8_t c = (uint8_t)(ch - 1);
    if (made == again && SubTrimShown && stood == (int32_t)SubTrims[c] - 127 && made >= -SUBTRIM_MOST && made <= SUBTRIM_MOST)
    {
        SubTrims[c] = (uint8_t)(made + 127); // TAKEN: one touch from the model's own number, on that channel (127 is the mid point of 0 - 254)
        if (SubTrimDone != SubTrimAsked)
            SubTrimSettleDue = true; // (the page has not said this board's last click done: a write of this board's may yet land on top of this - the page
                                     //  once more, when he has paused)
        return;
    }
    { // NOT TAKEN: its two last numbers do not agree, or the page has not yet said this model's numbers done, or it did not start from what the model
      // has, or went beyond what the card keeps. A line for the log (the first of a visit) - WITH THE RULE THAT REFUSED IT (the fifteenth review: for
      // the first two the line read like a change that should have been taken, and the second of the two last numbers was not in it) ...
        char kept[40], whole[190], why[60];
        const long s = stood < -9999 ? -9999 : stood > 9999 ? 9999 : stood, m = made < -9999 ? -9999 : made > 9999 ? 9999 : made;
        const long a = again < -9999 ? -9999 : again > 9999 ? 9999 : again;
        if (made != again)
            snprintf(why, sizeof(why), "its two last numbers differ, %ld and %ld", m, a);
        else if (!SubTrimShown)
            snprintf(why, sizeof(why), "the page had not yet said this model's numbers done");
        else if (stood != (int32_t)SubTrims[c] - 127)
            snprintf(why, sizeof(why), "it did not start from the model's number");
        else
            snprintf(why, sizeof(why), "it went beyond what the card keeps");
        snprintf(kept, sizeof(kept), "Sub-trim ch %d: a change not taken", (int)ch);
        snprintf(whole, sizeof(whole), "Sub-trim page: channel %d not taken - %s (the page made %ld of %ld; the model has %d); put right on the page B211",
                 (int)ch, why, m, s, (int)SubTrims[c] - 127);
        SubTrimNote(kept, whole);
    }
    SubTrimBoxOut(c); // ... the channel is put right on the page ...
    SubTrimResync();  // ... and the page's slider with it
    SubTrimSettleDue = true;
}
// A FRAME THAT THIS BOARD ITSELF LET GO UNSERVED (Nextion.h: DropUnconfirmedPress - a press not obeyed under the marker's rule, the page not known to
// be up; PendingPush - not kept for want of room). The fifteenth review: when it is a touch's burst of THIS page's, the page shows a change that the
// model has not got - and nothing was owed for it (a page whose markers were lost on the wire while its "done" came through: "+" showed 1, OK saved 0).
// The page is written out when he has paused, and OK stays until then - as behind words not kept. (Its form says what kind of page file said it.)
FLASHMEM void SubTrimWordLetGo(const uint8_t *f, uint16_t n, bool framed)
{
    if (n < 6 || n == SUBTRIM_DONE_BYTES || memcmp(f, "StEDIT", 6))
        return; // (not a touch of this page's - its "done" is no touch)
    if (framed && n == SUBTRIM_WORD_BYTES)
        SubTrimSaysDone = true; // (the sixteenth review: ON WHATEVER PAGE THIS BOARD IS - the burst says what kind of page file said it. On a first visit, the
                                //  first "done" lost: OK was obeyed, a "-" landed on the page as it went, its burst came on the next page and taught
                                //  nothing - and at the next showing an OK in front of the sixteen writes saved the model one click off what the page showed)
    if (CurrentView != SUBTRIMVIEW)
        return; // (another page: nothing is owed - the page is written out whole when it is next put up)
    SubTrimWordMs = millis() | 1;
    SubTrimSettleDue = true;
}
FLASHMEM void SubTrimPageBack() // THIS BOARD HAS PUT THE PAGE UP AGAIN WITHOUT ITS START (main.cpp: Help's way back; Utilities.h: the screen saver's). B211 (the
{                               // fourteenth review, both reviewers): the page came back by its page command alone, and a writing-out that was owed when it
                                // was left - SubTrimPoll lets go of it on another page - was forgotten: the page showed a number the model had not got
                                // until that channel was next touched. The page as the model has it, as when it is first put up.
    SubTrimStarts();
    UpdateButtonLabels(); // (SubTrimPageOut, fresh; and the sixteen names)
    if (SubTrimOldPageSaid)
        SendCommand((char *)"vis ModelName,0"); // (a page file from before, and its title has said so: the screen keeps that text - and shows the model's
                                                //  name over the left of it again. Out of the way, as when it was said: no second sound, no second line)
}
// FROM THE MAIN LOOP: THE PAGE WRITTEN OUT ONCE MORE, WHEN THE PILOT HAS PAUSED - after a change that was not taken, or one taken close behind a write of
// this board's (above); and when WORDS WERE NOT KEPT FOR WANT OF ROOM (Nextion.h PendingPush - the main loop held elsewhere while a finger dragged: the
// words behind such a gap are refused by themselves, but when the gap is the drag's END no word follows, and the page would stand ahead of the model
// in silence). No question, no wait. (A finger still resting on the slider: the screen puts the slider back under it and says so - from the model's
// number now: taken.)
FLASHMEM void SubTrimPoll()
{
    if (CurrentView != SUBTRIMVIEW)
    {
        SubTrimDropsSeen = PendingDropped; // (what was not kept on another page was none of this page's)
        SubTrimSettleDue = false;
        return;
    }
    if (PendingDropped != SubTrimDropsSeen)
    {
        SubTrimDropsSeen = PendingDropped;
        SubTrimSettleDue = true;
        SubTrimNote("Sub-trim: frames not kept, page out", "Sub-trim page: frames from the screen were not kept for want of room with the page up - the page is written out as the model has it B211");
    }
    if (!SubTrimSettleDue || PendingCount || NEXTION.available() || (SubTrimWordMs && (int32_t)(millis() - SubTrimWordMs) < SUBTRIM_REST_MS))
        return; // (nothing to put right; or words still wait - they are served first; or he has not paused yet)
    SubTrimSettleDue = false;
    SubTrimPageOut(false);
}
static void SubTrimStarts() // the page is put up (StartSubTrimView), or put up again (SubTrimPageBack)
{
    SubTrimWordMs = 0;
    SubTrimSettleDue = false;
    SubTrimNoteSaid = false;
    SubTrimAskedAgain = 0;
    SubTrimDropsSeen = PendingDropped;
}

/******************************************************************************************************************************/
void EndSubTrimView()
{ // Subtrim view exit
    if (PendingDropped != SubTrimDropsSeen)
    { // (words of the page's were not kept for want of room, and the main loop's look - SubTrimPoll - has not run since: the page is owed its writing-out)
        SubTrimDropsSeen = PendingDropped;
        SubTrimSettleDue = true;
    }
    if (SubTrimSettleDue)
    { // B211 (the fourteenth review): OK WHILE A WRITING-OUT IS OWED (inside the pause behind a change that was not taken, or behind words not kept): the
      // page may show a number the model has NOT got - and the model was saved, and the page left, with it never seen. The page is written out as the
      // model has it, and STAYS: he sees what will be saved, and presses OK again.
        SubTrimSettleDue = false;
        SubTrimPageOut(false);
        PlaySound(WHAHWHAHMSG);
        return;
    }
    if (SubTrimSaysDone && SubTrimDone != SubTrimAsked)
    { // ... AND WHILE A PUTTING-RIGHT IS STILL ON ITS WAY: the page says "done" behind every click of this board's, and its OK's code comes down the same
      // wire - so this OK was pressed BEFORE the page had been put right (a screen that is behind). It stays; nothing more is written (the writes
      // are on their way).
      // (The author's storm, 200000 trials a seed: this looked at "the page has said THIS showing's numbers done" - and a page put up AGAIN, by Help's
      //  way back, with a change taken a moment before and a stale writing-out landed on top of it, was left by an OK pressed in the milliseconds
      //  in which it was being written out: the old number on the page, the new one saved. It is asked of every page that SAYS "done" at all: a
      //  page file from before never does - and nothing can be taken from one.)
        if ((uint32_t)(millis() - SubTrimAskedMs) < SUBTRIM_DONE_WAIT_MS)
        {
            PlaySound(WHAHWHAHMSG);
            return;
        }
        // TWO SECONDS, AND NO "DONE". It was lost on the wire - or THE SCREEN STOOD STILL, and the putting-right still waits unread in its queue (the
        // fifteenth review; and the author's storm with the real page file, seed 3141592: another model read under the page, the screen still for
        // three seconds, a finger on OK as it woke - the page left on the clock, showing the model before). The clock alone cannot tell the two
        // apart: "rs" IS CLICKED ONCE MORE and OK stays - a screen that is awake says that click done at once, behind whatever waited in front of
        // it. Twice at most: a page that says "done" no longer (its file changed under this board) is then let go - OK IS NEVER REFUSED FOR GOOD.
        if (SubTrimAskedAgain < SUBTRIM_ASK_AGAIN_MOST)
        {
            const uint8_t again = SubTrimAskedAgain;
            SubTrimResync();
            SubTrimAskedAgain = (uint8_t)(again + 1); // (the click just made begins the count afresh - SubTrimResync: this one is OK's own, counted)
            PlaySound(WHAHWHAHMSG);
            return;
        }
    }
    char page_RXSetupView[] = "page RXSetupView";
    SaveOneModel(ModelNumber);
    CurrentView = RXSETUPVIEW;
    SendCommand(page_RXSetupView);
    LastTimeRead = 0;
    UpdateModelsNameEveryWhere();
}

// *************************************************************************************************************

void IncTrim(uint8_t t)
{
    bool Sounded = false;
    Trims[Bank][t] += 1;
    if (Trims[Bank][t] >= 120)
    {
        Trims[Bank][t] = 120;
        if (TrimClicks)
        {

            PlaySound(BEEPCOMPLETE);
            Sounded = true;
            TrimRepeatSpeed = DEFAULTTRIMREPEATSPEED;
        }
    }
    if (Trims[Bank][t] == 80)
    {
        TrimRepeatSpeed = DEFAULTTRIMREPEATSPEED; // Restore default trim repeat speed at centre
        if (TrimClicks)
        {
            PlaySound(BEEPMIDDLE);
            Sounded = true;
        }
    }
    if ((CurrentView == TRIM_VIEW) || (CurrentView == FRONTVIEW))
        UpdateTrimView();
    if ((TrimClicks) && (!Sounded))
        PlaySound(CLICKZERO);
}
// *************************************************************************************************************

void DecTrim(uint8_t t)
{

    bool Sounded = false;
    Trims[Bank][t] -= 1;
    if (Trims[Bank][t] <= 40)
    {
        Trims[Bank][t] = 40;
        if (TrimClicks)
        {
            PlaySound(BEEPCOMPLETE);
            Sounded = true;
            TrimRepeatSpeed = DEFAULTTRIMREPEATSPEED;
        }
    }
    if (Trims[Bank][t] == 80)
    {
        TrimRepeatSpeed = DEFAULTTRIMREPEATSPEED; // Restore default trim repeat speed at centre
        if (TrimClicks)
        {
            PlaySound(BEEPMIDDLE);
            Sounded = true;
        }
    }
    if ((CurrentView == TRIM_VIEW) || (CurrentView == FRONTVIEW))
        UpdateTrimView();
    if ((TrimClicks) && (!Sounded))
        PlaySound(CLICKZERO);
}

// *************************************************************************************************************

void MoveaTrim(uint8_t i)
{
    uint8_t Elevator = 1;
    uint8_t Throttle = 2;

    if (SticksMode == 2)
    {
        Elevator = 2;
        Throttle = 1;
    }

    switch (i)
    {
    case 0:
        IncTrim(InputTrim[0]); // Aileron
        break;
    case 1:
        DecTrim(InputTrim[0]); // Aileron
        break;
    case 2:
        IncTrim(InputTrim[Elevator]);
        break;
    case 3:
        DecTrim(InputTrim[Elevator]);
        break;
    case 4:
        DecTrim(InputTrim[Throttle]);
        break;
    case 5:
        IncTrim(InputTrim[Throttle]);
        break;
    case 6:
        IncTrim(InputTrim[3]); // Rudder
        break;
    case 7:
        DecTrim(InputTrim[3]); // Rudder
        break;
    default:
        break;
    }
    if (CopyTrimsToAll)
    {
        for (i = 0; i < 4; ++i)
        {
            const uint8_t tc = InputTrim[i] < CHANNELSUSED ? InputTrim[i] : i;  // B211: the channel this trim MOVES (Trim setup may have given it any of the sixteen: it copied
                                                                                //  channels 1 to 4 whatever the four trims moved - the other banks then flew without the trim)
            for (int fm = 1; fm <= BanksCount(); ++fm) // (B130: six banks when the model uses them)
            {
                Trims[fm][tc] = Trims[Bank][tc];
                Trims[fm][i] = Trims[Bank][i]; // (channels 1 to 4 as ever)
            }
        }
    }
}

/******************************************************************************************************************************/
// B211 (the thirteenth and fourteenth reviews; the released code had all three): what "Move these trims into subtrim" did.
//  - THE WRONG CHANNEL: a trim moves every channel whose INPUT is its slot (main.cpp DoTrimsAndSubtrims: GetTrimAmount(InPutStick[channel]); in stick
//    mode 2 the slots of inputs 2 and 3 change places), and a lever writes the slot its "Trim out" names (MoveaTrim, below: InputTrim[k]). The move
//    took "Trim out" for a CHANNEL's number. With the sticks' channels on the inputs of their own number that is the same thing. With channel 1 the
//    throttle stick and channel 2 the aileron stick, the aileron trim went into the THROTTLE channel's sub trim and the aileron channel lost its
//    trim; in mode 2 with one vertical lever's Trim out changed, the other vertical lever's trim was neither moved nor centred. "Done", it said.
//  - SIX BANKS: it centred the trims of banks 1 to 4 ("j < 5"). On a model with six, banks 5 and 6 kept the trim AND got the sub trim.
//  - MORE THAN THE CARD KEEPS: the sum was held to 0..255, and the card's reader centres a sub trim outside 10..244 (SDcard.h; the Sub-trim page's own
//    117 either way). A sum beyond was flown until the next switch-on - then centred, with the trims already at centre: out of trim by all of it.
// NOW: for EVERY CHANNEL the trim that acts on it - when a lever writes that trim's slot - goes into that channel's sub trim (two servos on one stick:
// both), so every servo stays where it is. WHOLE, OR NOT AT ALL: the sums are made first; a channel whose sum would pass 117 either way is named and
// NOTHING is changed. Then the slots the levers write are centred in every bank. (A trim at centre moves nothing: that channel's sub trim is left
// exactly as it is.)
FLASHMEM static uint8_t TrimSlotOfChannel(uint8_t c) // the trim slot that acts on channel c (0 to 15) - as GetTrimAmount(InPutStick[c]) takes it
{
    uint8_t slot = InPutStick[c];
    if (SticksMode == 2)
    {
        if (slot == 1)
            slot = 2;
        else if (slot == 2)
            slot = 1;
    }
    return slot;
}
FLASHMEM static bool TrimsIntoSubtrims(int *over) // false: nothing was changed - *over is the channel (1 to 16) that cannot take it
{
    int sum[CHANNELSUSED];
    *over = 0;
    for (int c = 0; c < CHANNELSUSED; ++c)
    {
        sum[c] = SubTrims[c];
        const uint8_t slot = TrimSlotOfChannel((uint8_t)c);
        bool aLevers = false; // a lever writes this slot: it is one of "these trims" (a slot no lever writes is no trim of the page's: left alone)
        for (int k = 0; k < 4; ++k)
            aLevers |= InputTrim[k] == slot;
        if (!aLevers || slot > CHANNELSUSED)
            continue;
        int temp = (int)(Trims[Bank][slot] - 80) * (int)TrimMultiplier; // 'int temp' is needed to avoid overflow. (Trims range from 40 to 120. 80 is centre.)
        temp /= 5;                                                      // Subtrims' multiplier is 5 always
        sum[c] += temp;                                                 // ClaudeFix-2-7-2026 signed: a low trim + low subtrim used to wrap the uint8_t to ~230 (a JUMP to near max)
        if (temp && !*over && (sum[c] < 127 - SUBTRIM_MOST || sum[c] > 127 + SUBTRIM_MOST))
            *over = c + 1;
    }
    if (*over)
        return false;
    for (int c = 0; c < CHANNELSUSED; ++c)
        SubTrims[c] = (uint8_t)sum[c]; // (within 10..244 wherever a trim moved it; else as it was)
    for (int k = 0; k < 4; ++k)
        if (InputTrim[k] <= CHANNELSUSED)
            for (int j = 1; j <= BANKS_USED; ++j)
                Trims[j][InputTrim[k]] = 80; // every bank's trim to centre - banks 5 and 6 too; the slot the LEVER writes (it was the mode-2 swap of it)
    return true;
}
void TrimsToSubtrim()
{ //   Store trims to subtrims and reset trims to centre
    char Prompt[] = "Move these trims into subtrim?\r\n\r\nThe trims of every bank\r\ngo back to centre.";
    char ItsCancelled[] = "Cancelled.\r\nSubtrim not changed.";
    char ItsAllDone[] = "Done.\r\nThe trims are now in subtrim,\r\nand back at centre.";

    if (GetConfirmation(pTrimView, Prompt))
    {
        int over = 0;
        if (TrimsIntoSubtrims(&over))
        {
            SaveOneModel(ModelNumber);     // Save model memory - BEFORE the box (B211, the fourteenth review: the change waited in memory while the box did, and
                                           // another model's receiver switched on under it - its model read by itself - took it away without a word)
            PlaySound(BEEPCOMPLETE);
            MsgBox(pTrimView, ItsAllDone); // Done!
            ForceDataRedisplay();          // force Update trim view
            UpdateTrimView();              // Update trim view
        }
        else
        {
            char TooMuch[130];
            snprintf(TooMuch, sizeof(TooMuch), "Channel %d cannot take that much\r\nsub trim (%d is the most).\r\nNOTHING was changed.\r\nAdjust its linkage instead.", over, SUBTRIM_MOST);
            PlaySound(WHAHWHAHMSG);
            MsgBox(pTrimView, TooMuch);
            ForceDataRedisplay(); // force Update trim view
            UpdateTrimView();     // Update trim view
        }
    }
    else
    {
        if (QuestionOvertaken)
            return; // B211 (the fifteenth review): THE QUESTION WAS CLOSED BY ANOTHER PAGE PUT UP OVER IT (the motor switched on while it waited brings the front page up - Motor_sign.h) - NO BOX
        // BEHIND IT. The box went up over that page, and its way back put the screen on this routine's page while this board believed in the other.
        MsgBox(pTrimView, ItsCancelled); // Cancelled
        ForceDataRedisplay();            // force Update trim view
        UpdateTrimView();                // Update trim view
    }
}

/******************************************************************************************************************************/
void RudderLeftTrim() { MoveaTrim(7); }
/******************************************************************************************************************************/
void RudderRightTrim() { MoveaTrim(6); }
/******************************************************************************************************************************/
void AileronRightTrim() { MoveaTrim(0); }
/******************************************************************************************************************************/
void AileronLeftTrim() { MoveaTrim(1); }
/******************************************************************************************************************************/
void ElevatorUpTrim()
{
    uint8_t tt = 2;
    if (SticksMode == 2)
        tt = 5;
    MoveaTrim(tt);
}
/******************************************************************************************************************************/
void ElevatorDownTrim()
{
    uint8_t tt = 3;
    if (SticksMode == 2)
        tt = 4;
    MoveaTrim(tt);
}
/******************************************************************************************************************************/
void ThrottleUpTrim()
{
    uint8_t tt = 4;
    if (SticksMode == 2)
        tt = 3;
    MoveaTrim(tt);
}
/******************************************************************************************************************************/
void ThrottleDownTrim()
{
    uint8_t tt = 5;
    if (SticksMode == 2)
        tt = 2;
    MoveaTrim(tt);
}

#endif