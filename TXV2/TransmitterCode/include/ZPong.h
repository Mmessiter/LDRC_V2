
#include <Arduino.h>
#include "1Definitions.h"
#ifndef ZPONG_H
    #define ZPONG_H
   
    
/*******************************************************************************************************************************/
//                                                  ZPONG.h
/*******************************************************************************************************************************/

bool GameEnd(){
        PlaySound(THEFANFARE);
        DelayWithDog(6000); 
        return true; // = play again ...//
}
/*******************************************************************************************************************************/

// V2 B28 (Malcolm, 5-10-2026: "optimise it better so that the ball appears to move a little more smoothly"): the game
// stays here (the sticks, the physics, the scores, the sounds), but the drawing is the 5-inch screen's. Each frame goes
// to it as ONE line, "pong=x,y,ly,ry", and the screen draws the court, the paddles and the ball in a layer of its own,
// smoothly, between our steps. The court used to be drawn from here with nine commands a frame, which the screen could
// only show in lumps. (A screen older than 1.9.3 knows no "pong=": the court stays empty - update both together.)
void StartPong()
{
    if (LedWasGreen) { // if connected to model, don't start pong
        char no[] = "Please disconnect first!";
        MsgBox(pFrontView,no);
        GotoFrontView();
        return;
    }
    SendCommand(pPongView);
    SetDefaultValues();
    CurrentView = PONGVIEW;
    CurrentMode = PONGMODE;
    BlueLedOn();
    char start[] = "pong=start";
    SendCommand(start); // the screen draws the court
}
/*********************************************************************************************************************************/
void SendPong(int x, int y, int ly, int ry)
{ // one line a frame: the ball, the two paddles
    char cb[48];
    snprintf(cb, sizeof(cb), "pong=%d,%d,%d,%d", x, y, ly, ry);
    SendCommand(cb);
}
/*********************************************************************************************************************************/

void PlayPong()
{ // called 100 times per second
    static uint32_t  Ponged          = 0;
    static short int x               = STARTX;
    static short int y               = STARTY;
    static short int LeftPaddlY      = STARTY;
    static short int RightPaddlY     = STARTY;
    static short int PrevLeftPaddlY  = STARTY;
    static short int PrevRightPaddlY = STARTY;

    static short int incy       = PONGBALLSPEED;
    static short int incx       = PONGBALLSPEED;
    static short int LeftScore  = 0;
    static short int RightScore = 0;
    char             n0[]       = "n0"; // score labels
    char             n1[]       = "n1"; // score labels
    uint8_t          lstk       = 1;    // left stick input
    uint8_t          rstk       = 2;    // right stick input

    if (CurrentView == HELP_VIEW || CurrentView == LOGVIEW) return;
    if ((millis() - Ponged) < PONGSPEED) return;
    Ponged = millis();
    y += incy;
    x += incx;
    if (SticksMode == 2) swap(&lstk, &rstk);
    LeftPaddlY  = map(PreMixBuffer[lstk], MINMICROS, MAXMICROS, PONGY2 + EXTRAPONG, PONGY1 - EXTRAPONG);
    RightPaddlY = map(PreMixBuffer[rstk], MINMICROS, MAXMICROS, PONGY2 + EXTRAPONG, PONGY1 - EXTRAPONG);
    if ((x <= LEFTPADDLEX + PONGCLEAR) && (x >= LEFTPADDLEX - PONGCLEAR)) { // hit left paddle?
        if ((y >= (LeftPaddlY - (PADDLEHEIGHT / 2))) && (y <= (LeftPaddlY + (PADDLEHEIGHT / 2)))) {
            incx = -incx;
            x    = LEFTPADDLEX + PONGCLEAR + 10;
            randomSeed(micros());
            if (PrevLeftPaddlY > LeftPaddlY) incy = -random(PONGBALLSPEED);
            if (PrevLeftPaddlY < LeftPaddlY) incy = random(PONGBALLSPEED);
            PlaySound(BEEPMIDDLE);
        }
    }
    PrevLeftPaddlY = LeftPaddlY;
    if ((x <= (RIGHTPADDLEX + PONGCLEAR)) && (x >= (RIGHTPADDLEX - PONGCLEAR))) { // hit right paddle?
        if ((y >= (RightPaddlY - (PADDLEHEIGHT / 2))) && (y <= (RightPaddlY + (PADDLEHEIGHT / 2)))) {
            incx = -incx;
            x    = (RIGHTPADDLEX - PONGCLEAR) - 10;
            randomSeed(micros());
            if (PrevRightPaddlY > RightPaddlY) incy = -random(PONGBALLSPEED);
            if (PrevRightPaddlY < RightPaddlY) incy = random(PONGBALLSPEED);
            PlaySound(BEEPMIDDLE);
        }
    }
    PrevRightPaddlY = RightPaddlY;
    if ((y + PONGCLEAR) >= PONGY2) { // bounce off bottom
        incy = -incy;
        y    = (PONGY2 - PONGCLEAR) - 10;
        PlaySound(CLICKZERO);
    }
    if (y <= (PONGY1 + PONGCLEAR)) { // bounce off top
        incy = -incy;
        y    = PONGY1 + PONGCLEAR + 10;
        PlaySound(CLICKZERO);
    }
    if (((x + PONGCLEAR) >= PONGX2) && (x)) {
        if ((y < GOALBOT - 2) && (y > GOALTOP + 2)) { // scored on the right?
            ++RightScore;
            SendValue(n0, RightScore);
            if (RightScore >= 10) {
               if (GameEnd()) {
                    RightScore = 0;
                    LeftScore  = 0;
                    SendValue(n0, RightScore);
                    SendValue(n1, LeftScore);
                } else {
                    GotoFrontView();
                }
                
            }
            x = PONGX2 + 5;
            SendPong(x, y, LeftPaddlY, RightPaddlY);
            PlaySound(BEEPCOMPLETE);
            DelayWithDog(500);
            x = -STARTX;
            y = -STARTY;
            randomSeed(micros());
            incx = -PONGBALLSPEED + random(PONGBALLSPEED * 2);
            while (abs(incx) < 3) incx = -PONGBALLSPEED + random(PONGBALLSPEED * 2);
            incy = PONGBALLSPEED - random(PONGBALLSPEED * 2);
        }
        else {
            incx = -incx;
            PlaySound(CLICKZERO);
        }
    }
    if ((x <= (PONGX1 + PONGCLEAR)) && (x)) { // scored on the left?
        if ((y < GOALBOT - 2) && (y > GOALTOP + 2)) {
            ++LeftScore;
            x = PONGX1 - 5;
            SendPong(x, y, LeftPaddlY, RightPaddlY);
            PlaySound(BEEPCOMPLETE);
            SendValue(n1, LeftScore);
            if (LeftScore >= 10) {
                if (GameEnd()) {
                    RightScore = 0;
                    LeftScore  = 0;
                    SendValue(n0, RightScore);
                    SendValue(n1, LeftScore);
                } else {
                     GotoFrontView();
                }
                   

            }
            DelayWithDog(500);
            x = -STARTX;
            y = -STARTY;
            randomSeed(micros());
            incx = PONGBALLSPEED - random(PONGBALLSPEED * 2);
            while (abs(incx) < 3) incx = PONGBALLSPEED - random(PONGBALLSPEED * 2);
            incy = PONGBALLSPEED - random(PONGBALLSPEED * 2);
        }
        else {
            incx = -incx;
            PlaySound(CLICKZERO);
        }
    }
    SendPong(x, y, LeftPaddlY, RightPaddlY);
    NewCompressNeeded = false;
    static short int ShownLeft = -1, ShownRight = -1; // the scores: written when they change, not every frame
    if (RightScore != ShownRight) { SendValue(n0, RightScore); ShownRight = RightScore; }
    if (LeftScore != ShownLeft) { SendValue(n1, LeftScore); ShownLeft = LeftScore; }
}

/****************************************************************************************************************/
#endif