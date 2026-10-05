// Pong's court, drawn by the screen (screen 1.9.3). The game is the main board's (ZPong.h: the sticks, the physics,
// the scores, the sounds); it sends "pong=x,y,ly,ry" once a frame and this draws it, in the court's own colours as the
// main board had them: black, white lines, a yellow ball. Drawn with whatever gfx points at (our own layer on the
// transmitter, the picture on the Mac). The geometry is the main board's (1Definitions.h): keep the two the same.
#pragma once

static const int PONG_X1 = 20, PONG_X2 = 790, PONG_Y1 = 60, PONG_Y2 = 410;   // the court (the main board's PONGX1..PONGY2)
static const int PONG_GOAL = 180, PONG_BALL = 7, PONG_PADDLE_H = 60, PONG_PADDLE_GAP = 40, PONG_PADDLE_W = 6;
static const int PONG_GOAL_TOP = PONG_Y1 + (PONG_Y2 - PONG_Y1) / 2 - PONG_GOAL / 2, PONG_GOAL_BOT = PONG_Y1 + (PONG_Y2 - PONG_Y1) / 2 + PONG_GOAL / 2;
static const int PONG_LEFT_X = PONG_X1 + PONG_PADDLE_GAP, PONG_RIGHT_X = PONG_X2 - PONG_PADDLE_GAP;
static const uint16_t PONG_BLACK = 0x0000, PONG_WHITE = 0xFFFF, PONG_BALL_COL = 0xFFE0, PONG_LINE = 0x4208, PONG_BALL_RIM = 0x8400;
// The layer: the court and a little round it. Not the score boxes above (they end at 55: the layer begins at 56), nor the
// OK button below. A paddle can reach 38 px beyond the court's lines (the main board's EXTRAPONG): the part outside the
// court is not drawn - it slides behind the frame - so nothing of ours covers the scores or the buttons.
static const int PONG_LAYER_X = PONG_X1 - 16, PONG_LAYER_Y = PONG_Y1 - 4, PONG_LAYER_W = PONG_X2 - PONG_X1 + 33, PONG_LAYER_H = PONG_Y2 - PONG_Y1 + 17;
static const int PONG_PADDLE_TOP = PONG_Y1 + 2, PONG_PADDLE_BOT = PONG_Y2 - 1;   // where a paddle may be drawn (the court's inside)

struct PongRect { int x, y, w, h; };
static bool pongOverlaps(const PongRect &a, const PongRect &b) { return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h; }
static PongRect pongBallRect(int x, int y) { return { x - PONG_BALL - 2, y - PONG_BALL - 2, 2 * PONG_BALL + 5, 2 * PONG_BALL + 5 }; }
static PongRect pongPaddleRect(int px, int y) {          // the paddle's place, clipped to the court's inside (an empty rect when it is wholly outside)
    int top = y - PONG_PADDLE_H / 2 - 1, bot = y + PONG_PADDLE_H / 2 + 1;
    if (top < PONG_PADDLE_TOP) top = PONG_PADDLE_TOP; if (bot > PONG_PADDLE_BOT) bot = PONG_PADDLE_BOT;
    return { px - PONG_PADDLE_W / 2 - 1, top, PONG_PADDLE_W + 2, bot > top ? bot - top : 0 };
}

// The still parts of the court that lie in a rectangle (drawn whole: they are cheap, and the rectangle is what is shown)
static void pongDrawCourtIn(const PongRect &r) {
    const PongRect top = { PONG_X1, PONG_Y1, PONG_X2 - PONG_X1 + 1, 2 }, bot = { PONG_X1, PONG_Y2 - 1, PONG_X2 - PONG_X1 + 1, 2 };
    const PongRect left = { PONG_X1, PONG_Y1, 2, PONG_Y2 - PONG_Y1 + 1 }, right = { PONG_X2 - 1, PONG_Y1, 2, PONG_Y2 - PONG_Y1 + 1 };
    const int mid = PONG_X1 + (PONG_X2 - PONG_X1) / 2; const PongRect centre = { mid - 1, PONG_Y1, 2, PONG_Y2 - PONG_Y1 + 1 };
    if (pongOverlaps(r, top)) gfx->fillRect(top.x, top.y, top.w, top.h, PONG_WHITE);
    if (pongOverlaps(r, bot)) gfx->fillRect(bot.x, bot.y, bot.w, bot.h, PONG_WHITE);
    if (pongOverlaps(r, left)) { gfx->fillRect(left.x, left.y, left.w, PONG_GOAL_TOP - PONG_Y1, PONG_WHITE); gfx->fillRect(left.x, PONG_GOAL_BOT, left.w, PONG_Y2 - PONG_GOAL_BOT + 1, PONG_WHITE); }   // (the goals: gaps in the sides)
    if (pongOverlaps(r, right)) { gfx->fillRect(right.x, right.y, right.w, PONG_GOAL_TOP - PONG_Y1, PONG_WHITE); gfx->fillRect(right.x, PONG_GOAL_BOT, right.w, PONG_Y2 - PONG_GOAL_BOT + 1, PONG_WHITE); }
    if (pongOverlaps(r, centre)) for (int y = PONG_Y1 + 6; y < PONG_Y2 - 6; y += 16) gfx->fillRect(centre.x, y, 2, 8, PONG_LINE);   // (a dashed line down the middle)
}
static void pongDrawBall(int x, int y) {
    gfx->fillCircle(x, y, PONG_BALL + 1, PONG_BALL_RIM);        // (a darker rim: the edge looks rounder on the glass)
    gfx->fillCircle(x, y, PONG_BALL, PONG_BALL_COL);
}
static void pongDrawPaddle(int px, int y) {              // (the part inside the court; the ends stay rounded while they show)
    const int top = y - PONG_PADDLE_H / 2, bot = y + PONG_PADDLE_H / 2;
    const int t = top < PONG_PADDLE_TOP ? PONG_PADDLE_TOP : top, b = bot > PONG_PADDLE_BOT ? PONG_PADDLE_BOT : bot;
    if (b <= t) return;
    if (t == top && b == bot) { gfx->fillRoundRect(px - PONG_PADDLE_W / 2, top, PONG_PADDLE_W, PONG_PADDLE_H, 3, PONG_WHITE); return; }
    gfx->fillRect(px - PONG_PADDLE_W / 2, t, PONG_PADDLE_W, b - t, PONG_WHITE);
}
static void pongErase(const PongRect &r) { gfx->fillRect(r.x, r.y, r.w, r.h, PONG_BLACK); pongDrawCourtIn(r); }
// The whole court afresh: when the layer comes
static void pongDrawAll(int x, int y, int ly, int ry, bool things) {   // (things: the paddles and the ball too; not before the first frame)
    gfx->fillRect(PONG_LAYER_X, PONG_LAYER_Y, PONG_LAYER_W, PONG_LAYER_H, PONG_BLACK);
    pongDrawCourtIn({ PONG_LAYER_X, PONG_LAYER_Y, PONG_LAYER_W, PONG_LAYER_H });
    if (!things) return;
    pongDrawPaddle(PONG_LEFT_X, ly); pongDrawPaddle(PONG_RIGHT_X, ry);
    pongDrawBall(x, y);
}
