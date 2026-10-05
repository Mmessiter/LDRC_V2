// ********************** ChooseImage.h ***********************************************
// This file contains the functions to Choose the model image
// ******************************************************************************

#include <Arduino.h>
#include "1Definitions.h"
#include <SPI.h>
#include "LdrcLink.h" // LDRC_IMAGE_WORD: the screen's chooser answers (V1B, B21)

#ifndef CHOOSEIMAGE_H
#define CHOOSEIMAGE_H
// *********************************************************************************************************************************/
char *GetModelImageFileName(char *fname)
{
    FileNumberInView = GetValue((char *)"MMems");
    for (int i = 0; i < 12; ++i)
    {
        fname[i] = TheFilesList[FileNumberInView][i];
        if (TheFilesList[FileNumberInView][i + 1] == '.')
        {
            fname[i + 1] = 0;
            break;
        }
    }
    return fname;
}

// *************************************************************************************************************************/

void ImageScrollStop() // finger lifted from the screen, so stop scrolling and show the currently selected image
{
    DisplayModelImage();        // show the currently selected image
    for (int i = 0; i < 5; ++i) // display the image repeatedly for a second as it's often slow to respond.
    {
        DelayWithDog(100);                         // delay for a 0.1 second while kicking the dog and checking for power off button
        GetModelImageFileName(ModelImageFileName); // get the currently selected image file name
        DisplayModelImage();                       // show the currently selected image
    }
}

// *************************************************************************************************************************/
uint16_t GetThisImageNumber()
{
    char temp[30];
    for (int j = 0; j < 89; ++j)
    {
        for (int i = 0; i < 12; ++i)
        {
            temp[i] = TheFilesList[j][i];
            if (TheFilesList[j][i + 1] == '.')
            {
                temp[i + 1] = 0;
                break;
            }
        }
        if (strcmp(temp, ModelImageFileName) == 0)
            return j;
    }
    return 0;
}

// *************************************************************************************************************************/
void StartChooseImage()
{
    // V1B (B22): the screen's own chooser (screen 1.5.0 and later) covers this page from its very first frame and shows
    // the pictures on ITS card, so this transmitter no longer lists /Images on its own card nor scrolls a list. It says
    // FIRST whose picture is being chosen and which picture the model has now, so that first frame is right, and then
    // shows the page. (Malcolm, 10-03: the old page flashed up before the new one: "erased from our memory".)
    CheckModelImageFileName(); // asks the screen whether the picture is there: before the page, not after
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "ImageView.exp0.path=\"sd0/images/%s.jpg\"", ModelImageFileName);
    SendCommand(cmd);
    SendText((char *)"ImageView.t0", ModelName);
    SendCommand((char *)"page ImageView");
    CurrentView = CHOOSEIMAGEVIEW;
}
// *********************************************************************************************************************************/
void EndChooseImage()
{
    SaveOneModel(ModelNumber);
    RXOptionsViewStart();
}
// *********************************************************************************************************************************/
// V1B (screen 1.5.0, B21): the screen covers this page with its own chooser (thumbnails of the pictures on ITS card,
// and photos sent from a phone) and answers as the pilot presses OK or Cancel: "LDRCIMG <name>", or "LDRCIMG" alone
// (keep the picture). The pictures live on the screen's card only: no copy on this card is needed any more. The name
// is kept as before (8 characters, ModelImageFileName), and the model saved as the page's own OK button does.
void ChooseImageFromScreen(const char *text)
{
    const char *p = strstr(text, LDRC_IMAGE_WORD);
    if (!p || CurrentView != CHOOSEIMAGEVIEW) // only as the answer to this page: a late repeat finds another page, and is ignored
        return;
    p += strlen(LDRC_IMAGE_WORD);
    while (*p == ' ')
        ++p;
    char name[sizeof(ModelImageFileName)];
    size_t n = 0;
    while (n < sizeof(name) - 1 && ((*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9') || *p == '_' || *p == '-'))
        name[n++] = *p++;
    name[n] = 0;
    if (n > 0)
        strcpy(ModelImageFileName, name);
    EndChooseImage();
}

#endif
