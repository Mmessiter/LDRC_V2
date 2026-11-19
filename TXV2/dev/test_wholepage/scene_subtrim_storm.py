#!/usr/bin/env python3
"""THE SUB-TRIM PAGE UNDER A STORM (the author's; written again for the thirteenth review's cure, 15 Nov 2026).

scene_subtrim holds the rules one by one; here the page is used at random - and with what the thirteenth review's reviewer B showed the first storm
could not reach: a screen that answers 60 to 400 ms late for a whole trial, touches at a hand's spacing (110 to 400 ms) as well as in bursts, only
two channels in play (the page comes back to a channel again and again), the page put up again by this board under the pilot's fingers (a box and
its way back, Help), a FINGER RESTING ON THE SLIDER (the screen puts the slider back under it 40 ms after any write of it, and says so), the main
loop held elsewhere while the finger drags (words not kept for want of room) - besides touches whose word is never heard, writes of this board's
that never land, the screen's loop standing still, another model read into memory under the open page. Both page files: this release's (its word
says the channel, the number as it stood, the number it made) and the one before (its word alone).

 I0. THE MODEL NEVER HOLDS A NUMBER THE PILOT DID NOT MAKE ON THAT CHANNEL - looked at after every pass of the main loop: whenever a channel's sub
     trim has changed, the book of the pilot's own touches (the pretend page writes it as its scripts run: which channel the page showed, the
     slider's number as it stood, what the touch made of it) must hold exactly that change - on that channel, FROM the number the model had; and
     the new number is one the card keeps. THE BOOK IS STRICT (the fourteenth review, reviewer B's): the touch must have been made ON A PAGE THAT
     HAD THIS MODEL'S NUMBERS - the page had run a click of this board's made at or behind the writing-out of the model now in memory (another
     model read under the open page: a touch on the old model's page is not the new model's to take, though both have the same number there).
 I5. WHAT OK SAVES IS WHAT THE PAGE SHOWED WHEN OK WAS PRESSED - in every trial in which nothing was lost so far: when OK is obeyed (the model saved,
     the page left), every box showed the model's number at the moment of the press; or nothing at all was taken since this model's numbers were
     written out (a page just put up, OK at once). OK pressed while a putting-right is owed, or on its way, stays (Trims.h EndSubTrimView).
 I1. LEFT ALONE, THE PAGE AND THE MODEL AGREE - in every trial in which nothing was lost on the way (no touch unheard, no write lost, the page not
     put up again under his fingers, no line of a FIELD screen's other core on the wire - said in pieces, such a line can swallow the page's burst
     whole: found by this storm, trial 512726): two quiet seconds after the last touch every box shows what the model has, and the slider and its
     number are the shown channel's. Words not kept for want of room are NOT a loss here: this board knows of those, and writes the page out.
 I2. ONE TOUCH PUTS A CHANNEL RIGHT - in every trial, whatever was lost: each channel whose box shows another number than the model's is tapped and
     "+" pressed - that "+" is refused, and the box shows the model's number.
 I3. THE PAGE FILE FROM BEFORE: nothing is ever taken.
 I4. NOTHING WAITS: no pass of the main loop on this page takes as long as one question to the screen would (55 ms and more) - the longest are the
     passes that write the page out, seventeen commands, some milliseconds (the storm's own waits apart).

The REAL Trims.h and main.cpp's own lines for the page's two words over the pretend screen, the page's scripts as scene_subtrim has them from the
two page files.
   python3 scene_subtrim_storm.py [--n trials] [--seed first]        (--seed N --n 1 runs one trial again, and tells it)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
import scene_subtrim as base
EXTRA = base.EXTRA + r'''
static uint32_t xs = 1; static uint32_t xr(uint32_t k) { xs = xs * 1664525u + 1013904223u; return k ? (xs >> 8) % k : 0; }
static std::deque<std::string> trail;         // the last things that happened
static void note(const char *f, ...) { char b[200]; va_list a; va_start(a, f); vsnprintf(b, sizeof b, f, a); va_end(a); char t[240]; snprintf(t, sizeof t, "%9.3f s  %s", nowUs / 1e6, b); trail.push_back(t); if (trail.size() > 70) trail.pop_front(); }
static int pLose = 0;                         // of 1000 writes, how many never land
static int pDoneLost = 0; static long donesLost9 = 0;   // of 1000 of the page's "done", how many are never heard (reviewer B's mix of the fourteenth review: 15 %)
static uint32_t xr(uint32_t k);
static bool stormDoneLost() { if (pDoneLost && xr(1000) < (uint32_t) pDoneLost) { ++donesLost9; return true; } return false; }
static bool lossy = false;                    // something was lost on the way in this trial (a touch unheard, a write, the page put up again under the fingers)
static long lostWrites = 0, unheard9 = 0, touches9 = 0, taken9 = 0, reloads9 = 0, modelReads9 = 0, stalls9 = 0, held9 = 0, drops9 = 0, fingers9 = 0;
static long i0Bad = 0, i4Bad = 0; static std::string i0First; static uint8_t prevTrims[16]; static uint64_t worstPassUs = 0, worstPassEver = 0;
static long oks9 = 0, okStayed9 = 0, okSaved9 = 0, okElsewhere9 = 0, i5Bad = 0, i5Looked = 0, i5First9 = 0, firsts9 = 0, firstDoors9 = 0, longStalls9 = 0, wakeRounds9 = 0; static std::string i5First;
struct OkPress { long shown[16]; bool finger[16]; bool lossy; uint16_t drops; };   // what the page showed as an OK was pressed (each press its own: they are served in their order)
static std::deque<OkPress> okPresses; static uint8_t trimsAtFresh[16]; static std::vector<std::string> i5Trail;
static int shown(int ch);
static void stormTap(const char *button)      // the page's own script (scene_subtrim's stTap) - and the trail
{
    if (screen.page != "SubTrimView") { note("a touch on '%s' while the page was away: nothing", button); return; }
    if (!strcmp(button, "ok")) { OkPress p; for (int c = 0; c < 16; ++c) { p.shown[c] = shown(c + 1); p.finger[c] = byFinger[c + 1]; } p.lossy = lossy; p.drops = PendingDropped; okPresses.push_back(p); note("OK is pressed"); return; }   // (what the page shows as OK is pressed)
    const size_t n0 = touches.size(); stTap(button);
    const bool heard = !*button || button[strlen(button) - 1] != '!';
    if (!heard) { lossy = true; ++unheard9; }
    if (touches.size() != n0) note("%s on channel %d: %ld -> %ld%s", button, touches.back().ch, touches.back().stood, touches.back().made, heard ? "" : "  (NEVER HEARD)");
    else note("%s: the page on channel %ld%s", button, B("s0"), heard ? "" : "  (never heard)");
}
static bool stormCmd(const char *c)           // this board's writes as the screen handles them - and those that never land
{
    if (!strstr(c, ".val=") && strcmp(c, "click rs,0")) return false;
    if (pLose && xr(1000) < (uint32_t) pLose) { ++lostWrites; lossy = true; note("LOST write %s", c); return true; }
    return stCmd(c);
}
static void i0Check(const char *where)
{
    for (int c = 0; c < 16; ++c)
    {
        if (SubTrims[c] == prevTrims[c]) continue;
        const long a = (long) prevTrims[c] - 127, b = (long) SubTrims[c] - 127; prevTrims[c] = SubTrims[c]; ++taken9;
        if (pageNew && wasMadeOnModel(c + 1, a, b) && b >= -SUBTRIM_MOST && b <= SUBTRIM_MOST) continue;
        ++i0Bad;
        if (i0First.empty()) { char t[300]; snprintf(t, sizeof t, "%s: channel %d went from %ld to %ld - %s", where, c + 1, a, b, !pageNew ? "and the page file is the one before: nothing is to be taken" : wasMade(c + 1, a, b) ? "a touch made that of it, but NOT on a page that had this model's numbers" : "no touch of the pilot's made that of it on that channel"); i0First = t; }
    }
}
static void stormLoad(const char *page)       // the page comes up on the screen: an OK pressed on its EARLIER showing (the screen behind, this board's page commands not yet there) is thrown
{                                             // away by this board with that page (a press belongs to its page) - its picture of the page goes with it
    stLoad(page); if (!strcmp(page, "SubTrimView")) okPresses.clear();
}
static void stormOk(int n)                    // the page's OK (its code 128+21) has been served: main.cpp's table calls Trims.h EndSubTrimView
{
    if (n != 21) return;
    // WHICH press is this? The board obeys them in their order - but not every one: a press made as the page was still coming up (between its two
    // markers) is let go without a word, one from the page's earlier showing is thrown away with that page. So the save is held against EVERY press
    // still open: what OK saves must be what the page showed at ONE of them. (Each trial that found a press unserved showed the save right, and
    // the book wrong: trials 639, 60826.)
    ++oks9; std::deque<OkPress> open = okPresses; bool snap = !open.empty();
    for (auto &q : open) if (q.drops != PendingDropped || q.lossy) snap = false;              // (words were not kept since, or something was lost: not asked)
    if (CurrentView != SUBTRIMVIEW) { ++okElsewhere9; note("OK served while this board has another page up: nothing"); return; }
    const bool heardThen = SubTrimSaysDone;   // (this board believes the page to be one that says "done": OK waits for it - the save is held against ALL the page showed)
    EndSubTrimView();
    if (CurrentView == SUBTRIMVIEW) { ++okStayed9; note("OK: the page STAYS (a putting-right owed, or on its way)"); return; }
    ++okSaved9; note("OK: the model saved, the page left"); okPresses.clear();                 // (the presses behind this one were made on a page that has gone)
    if (!pageNew || !snap) return;
    ++i5Looked; bool same = false; int first = 0; OkPress p = open.back();
    // (the fifteenth review: the excuse was "a page that has never said done - nothing can have been taken". Something can be SHOWN: a touch not taken
    //  on the first visit since power-on, OK twice, and the model was saved behind it. Before anything has been heard from the page OK is obeyed at
    //  once - with boxes the board's first writing-out has not reached yet, which no finger made; a number A FINGER MADE must be the one saved, always.)
    for (auto &q : open) { bool all = true; for (int c = 0; c < 16; ++c) if (q.shown[c] != (long) SubTrims[c] - 127 && (heardThen || q.finger[c])) { all = false; if (&q == &open.back() && !first) first = c + 1; } if (all) same = true; }
    if (!heardThen) ++i5First9;
    if (same) return;
    ++i5Bad;
    if (i5First.empty()) { char t[260]; snprintf(t, sizeof t, "OK saved the model with %d on channel %d - the page showed %ld there when OK was pressed", (int) SubTrims[first - 1] - 127, first, p.shown[first - 1]); i5First = t; i5Trail.assign(trail.begin(), trail.end()); }
}
static void stormOpen()                       // Trims.h StartSubTrimView's own lines (main.cpp UpdateButtonLabels: SubTrimPageOut, fresh)
{
    SendCommand((char *) "page SubTrimView"); SubTrimToEdit = 0; SubTrimOldPageSaid = false; SubTrimStarts(); CurrentView = SUBTRIMVIEW; freshOut(); memcpy(trimsAtFresh, SubTrims, 16); okPresses.clear();
}
static void stormLoop(uint32_t ms)
{
    const uint64_t until = nowUs + (uint64_t) ms * 1000;
    while (nowUs < until)
    {   // (I4 looks at the passes ON this page: the pass that obeys OK leaves it - a page command and its marker, the storm's own doing)
        const uint64_t t0 = nowUs; const bool on = CurrentView == SUBTRIMVIEW; LoopPass(); SubTrimPoll(); if (on && CurrentView == SUBTRIMVIEW && nowUs - t0 > worstPassUs) worstPassUs = nowUs - t0; i0Check("a pass of the main loop"); nowUs += 300 + xr(900);
    }
}
'''
SCENES = r'''
    const int N = argc > 2 ? atoi(argv[2]) : 300; const uint32_t seed0 = argc > 3 ? (uint32_t) atoi(argv[3]) : 7000;
    long i1Bad = 0, i1Looked = 0, i2Bad = 0, probes = 0, oldTrials = 0, trialsBad = 0; int shownBad = 0;
    for (int trial = 0; trial < N; ++trial)
    {
        const uint32_t sd = seed0 + trial;                                                                               // (everything of a trial follows from its seed)
        more(); addSubTrim(); xs = sd * 2654435761u + 12345u; trail.clear(); i0First.clear(); i5First.clear(); const long i0Before = i0Bad, i5Before = i5Bad; lossy = false; worstPassUs = 0; okPresses.clear(); i5Trail.clear();
        P().buttons["ok"] = { 149, 0, 0, 0 }; screen.pages0 = screen.pages; extra7 = stormOk;                         // the page's OK: print 149 (128+21)
        pageNew = sd % 9 != 8; oldTrials += !pageNew;
        tapScript = stormTap; cmdScript = stormCmd; loadScript = stormLoad; pLose = 0; doneLostNow = stormDoneLost; pDoneLost = 0;
        screen.realUart = true; screen.shoutForm = (sd & 1) ? 198 : 197;
        const bool slow = sd % 4 >= 2;                                                                                   // a screen that answers late, for the whole trial
        screen.latencyUs = slow ? 60000 + xr(340000) : 200 + xr(3) * xr(20000);
        const int nCh = (sd % 5 < 2) ? 2 : (sd % 5 == 2) ? 3 : 16; const int ch0 = 1 + xr(17 - nCh);                    // the channels in play: two, three, or all sixteen
        for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + (xr(3) ? 0 : (int) xr(235) - 117));               // the model: most channels centred, some anywhere the card keeps
        for (int ch = 1; ch <= 16; ++ch) B(boxOf(ch)) = (long) xr(235) - 117;                                           // what the last visit (another model's) left on the page
        B("n0") = (long) xr(255) - 127; B("h0") = xr(255); memset(byFinger, 0, sizeof byFinger);
        if (sd % 6 == 5) { SubTrimSaysDone = false; SubTrimShown = false; SubTrimAsked = SubTrimDone = 0; ++firsts9; }       // THE FIRST VISIT SINCE THIS BOARD STARTED: nothing heard from the page yet, no click made
        stormOpen();
        memcpy(prevTrims, SubTrims, 16);
        if (sd % 6 == 5 && xr(2))
        {   // REVIEWER B'S DOOR (the fifteenth review): the first visit, the page's first "done" lost on the wire - or only late -, a touch, and OK twice
            // close together. (OK left at the second press: "no done was ever heard" - with the page showing the touch, and the model saved without it.)
            pDoneLost = xr(2) ? 1000 : 0; stormLoop(xr(3) ? 50 + xr(800) : xr(40));
            tapCh(1, ch0 + xr(nCh)); tapAt(40 + xr(200), xr(2) ? "plus" : "minus"); stormLoop(50 + xr(250));
            tapAt(1 + xr(60), "ok"); tapAt(100 + xr(250), "ok"); stormLoop(200 + xr(600)); pDoneLost = 0; ++firstDoors9;
            if (CurrentView != SUBTRIMVIEW) { stormOpen(); memcpy(prevTrims, SubTrims, 16); note("the page is put up again (Sub trim pressed)"); }
        }
        stormLoop(xr(4) ? 700 : xr(80));                                                                                 // (now and then the pilot is on the page before its writes have landed)
        pLose = (sd % 7 == 6) ? 25 : (sd % 7 == 5) ? 4 : 0;
        pDoneLost = (sd % 11 == 10) ? 150 : (sd % 11 == 9) ? 20 : 0;                                                     // (the page's "done" lost on the wire: NOT a loss of a touch or of a write - I1 is still asked)
        const bool rough = sd % 3 == 2;                                                                                  // stalls, the page put up again, another model read, the loop held elsewhere
        const bool hand = xr(2) != 0;                                                                                    // touches at a hand's spacing (110 ms and more) - or in bursts
        const int actions = 10 + xr(36);
        for (int a = 0; a < actions; ++a)
        {
            const uint32_t pick = xr(100); const bool heard = xr(25) != 0; ++touches9;
            const uint32_t gap = hand ? 110 + xr(300) : xr(3) ? xr(60) : xr(5) ? 60 + xr(500) : 600 + xr(2500);
            const int ch = ch0 + xr(nCh);
            if (pick < 16) tapCh(1, ch, heard);
            else if (pick < 28)
            {   // a channel tapped and "+" or "-" close behind
                tapCh(1, ch, heard); const int n = 1 + xr(3); for (int s = 0; s < n; ++s) tapAt(2 + (hand ? 110 * (s + 1) + xr(200) : xr(160)), xr(2) ? "plus" : "minus"); touches9 += n;
            }
            else if (pick < 46) slide(1, (int) xr(255) - 127, heard);
            else if (pick < 62) tapAt(1, heard ? "plus" : "plus!");
            else if (pick < 74) tapAt(1, heard ? "minus" : "minus!");
            else if (pick < 78) tapAt(1, heard ? "zero" : "zero!");
            else if (pick < 86)
            {   // A DRAG - and at its end the finger rests on the slider for a while (the screen puts the slider back under it after any write of it)
                const int steps = 3 + xr(14); int v = (int) B("h0"); uint64_t at = nowUs + 1000;
                for (int s = 0; s < steps; ++s) { v += (int) xr(9) - 4; if (v < 0) v = 0; if (v > 254) v = 254; slideTo.push_back(v); screen.taps.insert({ at, "slider" }); at += 40000; }
                stormLoop(1 + steps * 40);
                if (xr(2)) { const long most = pageMost(); int at9 = v < 127 - most ? (int) (127 - most) : v > 127 + most ? (int) (127 + most) : v; fingerAt = at9; fingerDown = true; ++fingers9; note("the finger rests on the slider at %d", at9 - 127); stormLoop(200 + xr(1500)); fingerUp(); note("the finger is lifted"); }
            }
            else if (pick < 89 && rough)
            {   // (the fifteenth review: one stall in twelve is LONGER than OK's two seconds; one in three wakes with the rest of its loop's pass in front of its
                //  serial job - what a finger did meanwhile is printed BEFORE the queued commands are read)
                const bool longOne = xr(12) == 0; const uint32_t ms = longOne ? 2100 + xr(2500) : 100 + xr(4) * xr(900), wake = xr(3) ? 0 : 3000 + xr(40000);
                longStalls9 += longOne; wakeRounds9 += wake != 0;
                screen.stall(nowUs + xr(200000), ms, xr(2) != 0, wake); ++stalls9; if (screen.shoutForm < 198) lossy = true; note("the screen's loop stands still for %u ms%s", (unsigned) ms, wake ? " (and wakes with a touch in front of its commands)" : "");
            }
            else if (pick < 92 && rough)
            {   // THE PAGE IS PUT UP AGAIN BY THIS BOARD under his fingers - Help and its way back (the screen saver and a touch likewise: the two roads there are,
                // main.cpp "GOTO:" and Utilities.h SaveOrRestoreScreen). The words not yet served are thrown away with the page - and the page is written
                // out as the model has it (Trims.h SubTrimPageBack): NOTHING COUNTS AS LOST by it any more
                CurrentView = LOGVIEW; SendCommand((char *) "page LogView"); stormLoop(20 + xr(400)); SendCommand((char *) "page SubTrimView"); CurrentView = SUBTRIMVIEW; pageBack(); okPresses.clear(); ++reloads9; note("Help and its way back: the page put up again, written out");
            }
            else if (pick < 95 && rough)
            {   // another model is read into memory under the open page (main.cpp UpdateButtonLabels: SubTrimPageOut)
                stormLoop(xr(300)); i0Check("before another model was read");
                for (int i = 0; i < 16; ++i) SubTrims[i] = (uint8_t) (127 + (xr(3) ? 0 : (int) xr(235) - 117));
                memcpy(prevTrims, SubTrims, 16); freshOut(); memcpy(trimsAtFresh, SubTrims, 16); ++modelReads9; note("another model read under the page");
            }
            else if (pick < 98 && rough)
            {   // THE MAIN LOOP IS HELD ELSEWHERE for a second or two while the finger drags - and writes to the screen go on meanwhile (each reads what has come: the
                // queue of kept frames fills, and the rest are not kept)
                int v = (int) B("h0"); uint64_t at = nowUs + 1000; const int steps = 20 + xr(30);
                for (int s = 0; s < steps; ++s) { v += (int) xr(5) - 2; if (v < 0) v = 0; if (v > 254) v = 254; slideTo.push_back(v); screen.taps.insert({ at, "slider" }); at += 40000; }
                const uint16_t d0 = PendingDropped;
                for (int k = 0; k < steps / 2 + 2; ++k) { DelayWithDog(80); SendText((char *) "ModelName", (char *) "Storm"); }
                ++held9; drops9 += (uint16_t) (PendingDropped - d0); note("the main loop held elsewhere for %d ms: %u words not kept", (steps / 2 + 2) * 80, (unsigned) (uint16_t) (PendingDropped - d0));
            }
            else tapCh(1, ch, heard);
            if (xr(9) == 0) tapAt(1 + xr(hand ? 700 : 120), "ok");                                                   // OK, at any moment
            stormLoop(gap);
            if (CurrentView != SUBTRIMVIEW) { stormLoop(xr(300)); stormOpen(); memcpy(prevTrims, SubTrims, 16); note("the page is put up again (Sub trim pressed)"); stormLoop(xr(4) ? 400 : xr(60)); }   // OK was obeyed: he comes back to the page
        }
        // the trial's end: the screen running, nothing more lost
        pLose = 0; pDoneLost = 0; fingerUp();
        while (screen.busyUntil > nowUs) stormLoop(100);
        stormLoop(700);
        if (CurrentView != SUBTRIMVIEW) { stormOpen(); memcpy(prevTrims, SubTrims, 16); note("the page is put up again (Sub trim pressed)"); }
        stormLoop(2000);
        if (CurrentView != SUBTRIMVIEW) { stormOpen(); memcpy(prevTrims, SubTrims, 16); stormLoop(2000); }           // (an OK that waited in a stall)
        while (screen.busyUntil > nowUs) stormLoop(100);                                                             // (a long stall still running: the trial's end waits it out)
        if (SubTrimSettleDue || SubTrimDone != SubTrimAsked) stormLoop(2500);
        if (CurrentView != SUBTRIMVIEW) { stormOpen(); memcpy(prevTrims, SubTrims, 16); stormLoop(2000); }
        const bool agree = pageIsModel() && sliderIsShown() && PendingCount == 0;
        bool healed = true;
        if (pageNew)
        {
            if (!lossy) { ++i1Looked; if (!agree) ++i1Bad; }
            // I2: one touch puts a channel right
            for (int ch = 1; ch <= 16; ++ch)
            {
                if (shown(ch) == trim(ch)) continue;
                ++probes; const int had = trim(ch);
                tapCh(1, ch); tapAt(150, "plus"); stormLoop(600);
                if (trim(ch) != had || shown(ch) != had) { healed = false; note("PROBE of channel %d: the model %d (it had %d), the page %d", ch, trim(ch), had, shown(ch)); }
            }
            tapCh(1, B("s0") >= 1 && B("s0") <= 16 ? (int) B("s0") : 1); stormLoop(400);                                 // (a tap on the channel shown: the page's slider is that channel's again)
            if (!(pageIsModel() && sliderIsShown())) healed = false;
            if (!healed) ++i2Bad;
        }
        const bool waited = worstPassUs > 20000; if (worstPassUs > worstPassEver) worstPassEver = worstPassUs;
        const bool bad = i0Bad != i0Before || (pageNew && !lossy && !agree) || !healed || waited || i5Bad != i5Before;
        if (bad && ++trialsBad && ++shownBad <= 3)
        {
            printf("---- trial %d (seed %u, the page file %s, the screen %u ms behind, %d channel(s) in play)%s%s%s%s\n", trial, sd, pageNew ? "this release's" : "the one before", (unsigned) (screen.latencyUs / 1000), nCh,
                   i0Bad != i0Before ? (" | I0: " + i0First).c_str() : i5Bad != i5Before ? (" | I5: " + i5First).c_str() : "", (pageNew && !lossy && !agree) ? " | I1: nothing was lost, and two quiet seconds on the page and the model do not agree" : "", !healed ? " | I2: a tap and a + did not put a channel right" : "", waited ? " | I4: a pass of the main loop waited" : "");
            for (int c = 1; c <= 16; ++c) if (shown(c) != trim(c)) printf("     channel %d: the page shows %d, the model has %d\n", c, shown(c), trim(c));
            printf("     the page on channel %ld, its slider's number %ld, the slider %ld; frames waiting %d; the loop's longest pass %.1f ms\n", B("s0"), B("n0"), B("h0"), (int) PendingCount, worstPassUs / 1e3);
            for (auto &l : trail) printf("       %s\n", l.c_str());
            if (!i5Trail.empty()) { printf("     ... and as OK saved (I5):\n"); for (auto &l : i5Trail) printf("       %s\n", l.c_str()); }
        }
        if (waited) ++i4Bad;
        if (N == 1 && !bad) { for (auto &l : trail) printf("       %s\n", l.c_str()); }
        tapScript = nullptr; cmdScript = nullptr; extra7 = nullptr; doneLostNow = nullptr;
    }
    printf("   the page's \"done\" never heard %ld times\n", donesLost9);
    printf("   OK pressed and served %ld times: obeyed %ld (the model saved, the page left), the page stayed %ld times, served on another page %ld\n   I5 (what OK saves is what the page showed when it was pressed): broken %ld time(s) of %ld looked at (%ld of them before anything had been heard from the page: by the numbers a finger made)\n", oks9, okSaved9, okStayed9, okElsewhere9, i5Bad, i5Looked, i5First9);
    printf("   %ld trials began as the first visit since power-on (%ld of them with a touch and OK twice at once); %ld stalls longer than two seconds, %ld that woke with a touch in front of the commands\n", firsts9, firstDoors9, longStalls9, wakeRounds9);
    printf("the Sub-trim page under a storm: %d trials (%ld with the page file from before), %ld touches (%ld never heard), %ld changes taken; %ld writes that never landed, %ld stalls, the page put up again %ld times,\n"
           "   %ld models read under the page, a finger resting on the slider %ld times, the main loop held elsewhere %ld times (%ld words not kept)\n", N, oldTrials, touches9, unheard9, taken9, lostWrites, stalls9, reloads9, modelReads9, fingers9, held9, drops9);
    printf("   I0 (the model never holds a number the pilot did not make on that channel; from the page file before, nothing): broken %ld time(s)\n"
           "   I1 (nothing lost: the page and the model agree): broken in %ld of %ld trial(s)\n   I2 (one touch puts a channel right): broken in %ld trial(s); %ld channels were probed\n"
           "   I4 (nothing waits): broken in %ld trial(s); the main loop's longest pass %.1f ms\n", i0Bad, i1Bad, i1Looked, i2Bad, probes, i4Bad, worstPassEver / 1e3);
    CHECK(i0Bad == 0);
    CHECK(i4Bad == 0);
    CHECK(i1Bad == 0);
    CHECK(i2Bad == 0);
    CHECK(i5Bad == 0);
    if (N >= 300) CHECK(okSaved9 > N / 4 && okStayed9 > N / 50 && i5Looked > N / 20 && modelReads9 > N / 30);
    if (N >= 3000) CHECK(firsts9 > N / 10 && firstDoors9 > N / 20 && longStalls9 > N / 400 && wakeRounds9 > N / 100);   // (the fifteenth review's cases were met)
    if (N >= 300) CHECK(taken9 > N && unheard9 > N / 4 && probes > N / 100 && i1Looked > N / 10 && oldTrials > N / 20 && drops9 > 0 && fingers9 > N / 10 && reloads9 > N / 20);   // (the storm was the one meant)
    wordHook = nullptr; loadScript = nullptr;
'''
if __name__ == '__main__':
    nn = sys.argv[sys.argv.index('--n') + 1] if '--n' in sys.argv else '3000'
    sd = sys.argv[sys.argv.index('--seed') + 1] if '--seed' in sys.argv else '7000'
    sys.exit(lib.build_run('subtrim_storm', SCENES, extra=EXTRA, more_defines=('SUBTRIMVIEW',), args=['--x', nn, sd], sanitize=False, timeout=3000))
