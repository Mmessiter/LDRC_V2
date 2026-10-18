// Films for the renderer (screen 1.11.89): src/film_device.h itself - the films menu, and a film paused at a moment with
// its bar and slider - drawn by the screen's own code and fonts over the film's own picture, decoded by JPEGDEC as on the
// screen. Included by own.h.
//   @film menu                    the films menu
//   @film problems                the problems list (1.11.94: "Fix problems")
//   @film button TOPIC            a help page's own "Animation" button (Help tapped for TOPIC.TXT), over the page shown;
//                                 and (1.11.94) "Fix problems" top right, while problems.txt lists animations on the card
//   @film NAME SECONDS            film NAME (sd/hmi/films/NAME.ldf) played to SECONDS, then a tap: paused - the bar, the slider
//   @film NAME SECONDS drag TO    ... and a finger on the slider at TO seconds: the picture there
#pragma once
static const int FILM_AUDIO_ID = -2; static int audioId = -1;
static void audioStartFile(const char *, uint32_t = 0) { audioId = FILM_AUDIO_ID; }
static void audioStop() { audioId = -1; }
static int flyingNow() { return 0; }                               // (the motor safe: films allowed)
static uint32_t filmDecodeUs = 0, filmDecodeMax = 0, filmPictures = 0, filmSkipped = 0, filmFadeSteps = 0, filmFadeMax = 0;
static uint16_t *topFb = nullptr;                                  // (the layer: here the one frame, as the glass shows it)
#include "film_device.h"
static void filmShot(const std::string &args) {
    topFb = fbNow; page.name = "LogView";                          // (a film plays over a help page)
    if (args == "menu") { filmReadList(); filmMenuOpen(); return; }
    if (args == "problems") { filmReadList(); filmMenuOpen(1); return; }
    if (args.rfind("button ", 0) == 0) {                            // (1.11.91) a help page's own "Animation" button: Help tapped for TOPIC
        filmNoteHelp("print \"HelpView:" + args.substr(7) + ".TXT\""); filmPoll();
        if (!filmButtonUp()) fprintf(stderr, "render: @film %s: that help page has no animation of its own\n", args.c_str());
        return;
    }
    char name[24] = {0}, word[8] = {0}; double secs = 0, to = -1;
    const int n = sscanf(args.c_str(), "%23s %lf %7s %lf", name, &secs, word, &to);
    if (n < 2) { fprintf(stderr, "render: @film %s: NAME SECONDS [drag TO]\n", args.c_str()); return; }
    if (!filmStartName(name)) { fprintf(stderr, "render: @film %s: the film would not start\n", name); return; }
    while (hostClockMs - filmStartMs < (uint32_t) (secs * 1000)) { hostClockMs += 10; filmPoll(); }
    for (int i = 0; i < 400; ++i) filmPoll();                       // (every picture due, decoded)
    filmTouch(true, 400, 200, hostClockMs); hostClockMs += 200; filmTouch(false, 0, 0, hostClockMs);   // a tap on the picture: paused
    if (n == 4 && !strcmp(word, "drag") && to >= 0) {
        const int x = ldrcfilm::seekX((int32_t) (to * filmHead.fps), FILM_SEEK_X0, FILM_SEEK_W, filmHead.frames);
        filmTouch(true, x, FILM_SEEK_MID, hostClockMs);
        for (int i = 0; i < 4000 && filmLast != filmSeekWant; ++i) filmPoll();
    }
}
