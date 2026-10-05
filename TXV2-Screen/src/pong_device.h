// Pong on the transmitter (screen 1.9.3; Malcolm, 5-10-2026: "optimise it better so that the ball appears to move a
// little more smoothly"). The main board plays the game and sends "pong=x,y,ly,ry" once a frame (every 10 ms, 5 px a
// step); it used to draw the court itself with nine commands a frame, which the page could only show in lumps (at most
// 40 a second, and held back while its serial was still arriving). Now the court is a layer of ours over the Pong page:
// drawn in memory and shown at once, and the ball and paddles move BETWEEN the main board's steps - each pass draws
// where they were 15 ms ago, by the two frames either side of that moment - so the eye sees a steady glide. The
// page's scores, OK and Help stay the page's, around the layer (touches there are the page's as ever).
#pragma once
#include "pong_draw.h"

static const int PONG_WHO = 9;
static const uint32_t PONG_LAG_MS = 15, PONG_HOLD_MS = 80;     // drawn this far behind the main board; a frame older than this is held still
struct PongFrame { int x = 0, y = 0, ly = 0, ry = 0; uint32_t at = 0; };
static PongFrame pongPrev, pongLast; static int pongFrames = 0;
static bool pongOpen = false; static uint32_t pongOpenedAt = 0;
static int pongBx = -1, pongBy = -1, pongLy = -1, pongRy = -1;   // as drawn
static bool pongUp() { return topOn && topWho == PONG_WHO; }

// "pong=start" / "pong=x,y,ly,ry", from the main board
static void pongCommand(const std::string &a) {
    if (a == "start") { pongOpen = true; pongOpenedAt = millis(); pongFrames = 0; return; }
    int v[4]; if (sscanf(a.c_str(), "%d,%d,%d,%d", &v[0], &v[1], &v[2], &v[3]) != 4) return;
    PongFrame f; f.x = v[0]; f.y = v[1]; f.ly = v[2]; f.ry = v[3]; f.at = millis();
    if (!pongOpen) { pongOpen = true; pongOpenedAt = f.at; pongFrames = 0; }   // (a frame before "start": the game is on)
    pongPrev = pongFrames ? pongLast : f; pongLast = f; if (pongFrames < 2) ++pongFrames;
}
static int pongLerp(int a, int b, uint32_t num, uint32_t den) { return den ? a + (int) (((long) (b - a) * (long) num) / (long) den) : b; }
static void pongPoll() {
    static bool wasUp = false;
    const uint32_t now = millis();
    // the layer goes with the page: the main board leaves Pong by loading another page
    if (pongOpen && page.name != "PongView" && page.name != "BlankView") pongOpen = false;
    if (pongOpen && now - pongOpenedAt > 2000 && !pongFrames) pongOpen = false;   // (asked for, and nothing came)
    const bool layerFree = !topOn || topWho == PONG_WHO;
    const bool up = pongOpen && page.name == "PongView" && layerFree && topReady();
    if (up) {
        // where things are now: 15 ms behind the latest frame, between the two frames either side of that moment
        int x = pongLast.x, y = pongLast.y, ly = pongLast.ly, ry = pongLast.ry;
        if (pongFrames >= 2 && now - pongLast.at < PONG_HOLD_MS) {
            const uint32_t t = now - PONG_LAG_MS, span = pongLast.at - pongPrev.at;
            if (t <= pongPrev.at) { x = pongPrev.x; y = pongPrev.y; ly = pongPrev.ly; ry = pongPrev.ry; }
            else if (t < pongLast.at && span) {
                const uint32_t k = t - pongPrev.at;
                x = pongLerp(pongPrev.x, pongLast.x, k, span); y = pongLerp(pongPrev.y, pongLast.y, k, span);
                ly = pongLerp(pongPrev.ly, pongLast.ly, k, span); ry = pongLerp(pongPrev.ry, pongLast.ry, k, span);
            }
        }
        if (!wasUp) {
            { TopDraw on; pongDrawAll(x, y, ly, ry, pongFrames > 0); }
            if (pongFrames) { pongBx = x; pongBy = y; pongLy = ly; pongRy = ry; } else pongBx = pongBy = pongLy = pongRy = -1;
            topX = PONG_LAYER_X; topY = PONG_LAYER_Y; topW = PONG_LAYER_W; topH = PONG_LAYER_H; topWho = PONG_WHO; topOn = true;
            dirty(PONG_LAYER_X, PONG_LAYER_Y, PONG_LAYER_W, PONG_LAYER_H); touchPainted = true;
        } else if (pongFrames && (x != pongBx || y != pongBy || ly != pongLy || ry != pongRy)) {
            TopDraw on;
            if (ly != pongLy) { const PongRect o = pongPaddleRect(PONG_LEFT_X, pongLy), n = pongPaddleRect(PONG_LEFT_X, ly); if (o.h) { pongErase(o); dirty(o.x, o.y, o.w, o.h); } pongDrawPaddle(PONG_LEFT_X, ly); if (n.h) dirty(n.x, n.y, n.w, n.h); }
            if (ry != pongRy) { const PongRect o = pongPaddleRect(PONG_RIGHT_X, pongRy), n = pongPaddleRect(PONG_RIGHT_X, ry); if (o.h) { pongErase(o); dirty(o.x, o.y, o.w, o.h); } pongDrawPaddle(PONG_RIGHT_X, ry); if (n.h) dirty(n.x, n.y, n.w, n.h); }
            if (x != pongBx || y != pongBy) {
                const PongRect o = pongBallRect(pongBx, pongBy), n = pongBallRect(x, y);
                pongErase(o);
                if (pongOverlaps(o, pongPaddleRect(PONG_LEFT_X, ly))) pongDrawPaddle(PONG_LEFT_X, ly);   // (a paddle the ball passed over: back on top)
                if (pongOverlaps(o, pongPaddleRect(PONG_RIGHT_X, ry))) pongDrawPaddle(PONG_RIGHT_X, ry);
                pongDrawBall(x, y); dirty(o.x, o.y, o.w, o.h); dirty(n.x, n.y, n.w, n.h);
            }
            pongBx = x; pongBy = y; pongLy = ly; pongRy = ry; touchPainted = true;   // (shown at once, not at the page's pace)
        }
    } else if (wasUp) {
        if (topWho == PONG_WHO) { topOn = false; topWho = 0; }
        dirty(PONG_LAYER_X, PONG_LAYER_Y, PONG_LAYER_W, PONG_LAYER_H); touchPainted = true;
        pongBx = pongBy = pongLy = pongRy = -1;
    }
    wasUp = up;
}
