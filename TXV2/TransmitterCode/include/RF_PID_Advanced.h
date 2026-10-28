// ******************************************** Rotorflight PID Advanced ******************************************************
// This module handles the Rotorflight PID Advanced screen on the Nextion display

// **********************************************************************************************************
#ifndef PIDADVANCED_H
#define PIDADVANCED_H
#include <Arduino.h>
#include "1Definitions.h"

char PID_Advanced_Labels[26][4] = {"sw0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11", "t12",
                                   "t13", "t14", "t15", "t16", "t17", "t18", "t19", "t20", "t21", "t22", "t23", "t24", "t25"}; // Text boxes for PID Advanced view

// ************************************************************************************************************/
FLASHMEM void Display_PID_Advanced_Values(uint8_t n, uint8_t m) // display PID Advanced values n to m on screen as they are read from RX
{
  char TextFloat[10];
    for (uint8_t i = n; i < m; ++i)
    {
        if (i < MAX_PIDS_ADVANCED_BYTES)
        {
            if (i == 0) // piro compensation is boolean swich
            {
                SendValue(PID_Advanced_Labels[i], (bool)PID_Advanced_Values[i]);
                continue;
            }
            if ((i == 1) || (i == 25)) // these two are floats divided by 10
                snprintf(TextFloat, sizeof(TextFloat), "%.1f", (float)PID_Advanced_Values[i] / 10.0f);
            else
                snprintf(TextFloat, sizeof(TextFloat), "%u", (unsigned)PID_Advanced_Values[i]);

            SendText(PID_Advanced_Labels[i], TextFloat); // Send to screen
        }
    }
}
// ************************************************************************************************************/
FLASHMEM void ReadEditedPIDAdvancedValues()
{
    for (uint8_t i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i)
    {
        if (i == 0) // Piro compensation is boolean switch
        {
            PID_Advanced_Values[i] = (uint8_t)(GetValue(PID_Advanced_Labels[i]) != 0);
            continue;
        }
        char temp[10];
        if (GetText(PID_Advanced_Labels[i], temp, sizeof(temp)) == 0) continue;   // B152: unanswered: the value in hand stays (NextionTextMissed: a save stops)
        if ((i == 1) || (i == 25)) // these two are floats multiplied by 10
            PID_Advanced_Values[i] = RfByteOf((float)atof(temp) * 10.0f); // B07: cut, never wrapped
        else
            PID_Advanced_Values[i] = RfByteOf((float)atoi(temp)); // B07
    }
}
// ************************************************************************************************************/
FLASHMEM void ForegroundColourPIDAdvancedLabels(uint16_t Colour)
{
    for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i)
        SendForegroundColour(PID_Advanced_Labels[i], Colour);
}
// ************************************************************************************************************/
FLASHMEM void HidePID_Advanced_Msg()
{
    if (CurrentView == PIDADVANCEDVIEW) // Must be in PIDAdvanced view
    {
        SendCommand((char *)"vis busy,0");        // Hide PID message
        ForegroundColourPIDAdvancedLabels(Black); // make text black so it is visible again
        BlockBankChanges = false;
    }
}
// **********************************************************************************************************/
FLASHMEM void PIDAdvancedMsg(const char *msg, uint16_t Colour)
{
    if (CurrentView == PIDADVANCEDVIEW) // Must be in PIDAdvanced view
    {
        ForegroundColourPIDAdvancedLabels(Colour); // make text white so it isnt visible
        SendText((char *)"busy", (char *)msg);     // Show PID message
        SendCommand((char *)"vis busy,1");         // Make it visible
        SendCommand((char *)"vis b3,0");           // hide "Send" button
    }
}
// ************************************************************************************************************/
FLASHMEM void PIDsAdvancedWereEdited()
{
    SendCommand((char *)"vis b3,1"); // show "Send" button
    PIDS_Advanced_Were_Edited = true;
}
// ************************************************************************************************************/
FLASHMEM void ShowLocalPIDsAdvancedBank()
{
    char TextFloat[10];
    for (uint8_t i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i)
    {
        if (i < MAX_PIDS_ADVANCED_BYTES)
        {
            if (i == 0) // piro compensation is boolean switch
            {
                SendValue(PID_Advanced_Labels[i], (bool)Saved_PID_Advanced_Values[i][Bank - 1]);
                continue;
            }
            if ((i == 1) || (i == 25)) // these two are floats divided by 10
                snprintf(TextFloat, sizeof(TextFloat), "%.1f", (float)Saved_PID_Advanced_Values[i][Bank - 1] / 10.0f);
            else
                snprintf(TextFloat, sizeof(TextFloat), "%u", (unsigned)Saved_PID_Advanced_Values[i][Bank - 1]);

            SendText(PID_Advanced_Labels[i], TextFloat); // Send to screen
        }
    }
    HidePID_Advanced_Msg();
}
//************************************************************************************************************/
// B102: the read, and the write once the flight controller is known to be on this bank (PipeHttp.h BankCheck)
FLASHMEM static void PidAdvAskValues()
{
    if (CurrentView != PIDADVANCEDVIEW) { BlockBankChanges = false; return; }
    PID_Advanced_Send_Duration = MSP_WAIT_TIME;     // how many milliseconds to await PID values
    Reading_PIDS_Advanced_Now = true;               // This tells the Ack payload parser to get PID values
    AddParameterstoQueue(SEND_PID_ADVANCED_VALUES); // Request PID values from RX
    PID_Advanced_Start_Time = millis();             // record start time as it's not long
}
FLASHMEM static void PidAdvQueueWrite()
{
    const bool readBack = RfVerifyArm(VK_PID_ADV, PidAdvAskValues);        // B153: the block is read back after the write and compared with what was sent (the read queued first: the stack sends it last)
    AddParameterstoQueue(GET_THIRD_8_ADVANCED_PID_VALUES);                  // LAST MUST BE QUEUED FIRST!!!
    AddParameterstoQueue(GET_SECOND_9_ADVANCED_PID_VALUES);                 // the order of the other two doesn't matter ...
    AddParameterstoQueue(GET_FIRST_9_ADVANCED_PID_VALUES);                  // its a LIFO stack with 26 parametres to send
    PIDS_Advanced_Were_Edited = false;                                      // reset edited flag
    if (readBack) return;                                                   // "reading back ..." stays up: the verdict does the rest (RF_Verify.h)
    BlockBankChanges = false;
    if (CurrentView == PIDADVANCEDVIEW)
    {
        HidePID_Advanced_Msg();                                             // ...because this queue is a LIFO stack
        SendCommand((char *)"vis b3,0");                                    // hide "Send" button
    }
    PlaySound(BEEPCOMPLETE);                                                // let user know we're done
    if (RfValueWasCut && CurrentView == PIDADVANCEDVIEW)
    { // B07
        Display_PID_Advanced_Values(0, MAX_PIDS_ADVANCED_BYTES);
        RfCutNote("page PID_A_View");
    }
    RfSavedThenLeave(PIDADVANCEDVIEW);                                      // B102: OK's "Save now?" closes the page once saved
}
FLASHMEM void ShowPIDAdvancedBank() // this is called when bank is changed so new bank's PID Advanced values are requested from Nexus and shown
{
    char buf[40];
    strcpy(buf, "Loading values for ");
    strcat(buf, BankNames[BanksInUse[Bank - 1]]);
    strcat(buf, " ...");
    if (CurrentView == PIDADVANCEDVIEW) // Must be in PIDAdvanced view
    {
        SendText((char *)"t26", BankNames[BanksInUse[Bank - 1]]); // Show bank number etc
        if (!RfLive())
        {
            PIDAdvancedMsg(buf, Gray); // Show loading message and hides old PIDs
            ShowLocalPIDsAdvancedBank();
            return;
        }

        if (PIDS_Advanced_Were_Edited)
        {
            char NB[10];
            char Wmsg[120];
            char w1[] = "Values for Bank ";
            char w2[] = " were edited \r\nbut not saved. (Too late now!)\r\nSo you may want to check them.";
            strcpy(Wmsg, w1);
            strcat(Wmsg, Str(NB, PreviousBank, 0));
            strcat(Wmsg, w2);
            MsgBox((char *)"page PID_A_View", Wmsg); // Warn about unsaved edits
        }
        BlockBankChanges = true;                  // block bank changes while we do this
        PIDAdvancedMsg(buf, Gray);                      // Show loading message and hides old PIDs
        PIDS_Advanced_Were_Edited = false;              // reset edited flag
        PidAdvAskValues();
    }
}
// ************************************************************************************************************/
FLASHMEM void SaveToLocalABank()
{
    PIDAdvancedMsg((char *)"Saving edited advanced PIDs ...", Gray); // Show sending message
    NextionTextMissed = false;
    ReadEditedPIDAdvancedValues();   // read the edited PID Advanced values from the screen
    if (RfFieldsMissed("page PID_A_View")) { HidePID_Advanced_Msg(); return; }   // B152: a box unanswered: nothing saved
    for (int i = 0; i < MAX_PIDS_ADVANCED_BYTES; ++i)
    {
        Saved_PID_Advanced_Values[i][Bank - 1] = PID_Advanced_Values[i];
    }
    SendCommand((char *)"vis b3,0"); // hide "Send" button
    SaveOneModel(ModelNumber);       // save all to SD card
    HidePID_Advanced_Msg();
    PIDS_Advanced_Were_Edited = false; // reset edited flag
    PlaySound(BEEPCOMPLETE);           // let user know we're done
    if (RfValueWasCut)
    { // B07
        Display_PID_Advanced_Values(0, MAX_PIDS_ADVANCED_BYTES);
        RfCutNote("page PID_A_View");
    }
}
// ************************************************************************************************************/
FLASHMEM void SendEditedPID_Advanced()
{
    if (!RfLive())
    { // Model not connected so save to local PIDs
        SaveToLocalABank();
        return;
    }
    {
        char why[120];
        if (RfPipeBlocked(why, sizeof(why))) // B48: the pipe went while the page was open
        {
            MsgBox((char *)"page PID_A_View", why);
            return;
        }
    }
    PlaySound(BEEPMIDDLE);
    DelayWithDog(100);                                                      // allow LOTS of time for screen to update BEFORE sending another Nextion command
    PIDAdvancedMsg((char *)"Sending edited advanced PIDs ...", Gray); // Show sending message
    NextionTextMissed = false;
    ReadEditedPIDAdvancedValues();   // read the edited PID Advanced values from the screen
    if (RfFieldsMissed("page PID_A_View")) { HidePID_Advanced_Msg(); return; }   // B152: a box unanswered: nothing sent
    BlockBankChanges = true;
    BankCheck(false, Bank, PidAdvQueueWrite, "page PID_A_View");     // B102: into this bank, or not at all (the edited flag stays until then)
}
// ********************************************************************************************************
FLASHMEM void StartPIDAdvancedView()
{
    if (PIDS_Were_Edited)
    {
        if (GetConfirmation((char *)"page PIDView", (char *)"Discard edited PIDs?"))
        {
            PIDS_Were_Edited = false;
        }
        else
        {
            return;
        }
    }
    SendCommand((char *)"page PID_A_View"); // Make Advanced visible
    CurrentView = PIDADVANCEDVIEW;
    ShowPIDAdvancedBank();              // Show the current bank's PID Advanced values
    SendText((char *)"t27", ModelName); // Show model name
}
// **********************************************************************************************************/
FLASHMEM void EndPIDsAdvancedView()
{
    if (PIDS_Advanced_Were_Edited)
    {
        if (!RfSaveFirst("page PID_A_View", "The edited values are", SendEditedPID_Advanced, EndPIDsAdvancedView, &PIDS_Advanced_Were_Edited)) return;   // B102: "Save now?"
        PIDS_Advanced_Were_Edited = false;   // (Discard: back to the Rotorflight page, as without edits - it went to the front page)
        RotorFlightStart();
    }
    else
    {
        PIDS_Advanced_Were_Edited = false;
        RotorFlightStart();
    }
}
#endif // PIDADVANCED_H
       // *********************************************************************************************************************************/