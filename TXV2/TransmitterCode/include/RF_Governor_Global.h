// ********************************************************************************************************
// RF_Governor_Global.h
// Handles global/config parameters for the Rotorflight Governor on the Nextion display.
// Config parameters — MSP cmd 142, payload bytes [18]-[41]
// B195 (Malcolm, 6 Nov 2026, the Rotorflight gap list): on a 16 MB screen (ScreenIsBig) Start-up [20-21] joins the General
// column (n16) and the five filters [34-38] are the page's Filters tab (n23 RPM, n24 power, n25 D x0.1 Hz, n26 FF, n27 TTA;
// the tabs are the page's own script). On a 4 MB screen the page hides them itself (ldrcmb < 16) and they are kept as read.
// Profile-specific parameters are handled in RF_Governor_Profile.h
// B165 (1 Nov 2026): A SAVE IS READ BACK, as on every other Rotorflight page (RF_Verify.h, VK_GOV_CFG). The three write
// packets go as before; the page's own read is queued first (the stack sends it last) with an 8 s window - the receiver
// writes, checks the flight controller's answer, saves and RESTARTS it, and answers from its verified copy meanwhile -
// and the 24 bytes that come back are compared with GovWritePayload[18..41]: the same = "Saved, and confirmed by reading
// it back." on t4, the done sound, OK's "Save now?" closes the page; different or nothing = a message box, the values
// sent back on the page with the boxes that differ in red, Save shown again. The edited flag stays up until the
// read-back says saved, so OK's "Save now?" waits for the verdict. The kept copy sent from the card is read back too.
// ********************************************************************************************************

#ifndef GOVERNOR_GLOBAL_H
#define GOVERNOR_GLOBAL_H
#define GOVERNOR_GLOBAL_LABELS_COUNT 17

#include <Arduino.h>
#include "1Definitions.h"

uint8_t Global_Params_Received_Flags[24] = {0}; // tracks which config bytes [18]-[41] have been received from FC

char GOV_Global_Labels[GOVERNOR_GLOBAL_LABELS_COUNT][4] = {
    "n14", "n15", "n16", "n17", "n18", "n19", "n20",
    "n21", "n22", "n23", "n24", "n25", "n26", "n27",
    "n28", "n29", "n30"};

char Gov_Mode_types[5][20] = {"0 - OFF", "1 - LIMIT", "2 - DIRECT", "3 - ELECTRIC", "4 - NITRO"};   // (15 Oct: the phone app's words)
char Throttle_types[3][20] = {"0 - NORMAL", "1 - SWITCH", "2 - FUNCTION"};   // (Rotorflight's names, in the modes' style)

// ====================================================
FLASHMEM void ForegroundColourGOVConfigLabels(uint16_t Colour)
{
    for (int i = 0; i < GOVERNOR_GLOBAL_LABELS_COUNT; ++i)
        SendForegroundColour(GOV_Global_Labels[i], Colour);
}

// ====================================================
FLASHMEM void ShowGOVConfigMsg(const char *msg, uint16_t Colour)
{
    if (CurrentView == RFGOVERNORVIEW_GLOBAL)
    {
        ForegroundColourGOVConfigLabels(Colour);
        SendText((char *)"t4", (char *)msg);
        SendCommand((char *)"vis t4,1");
        SendCommand((char *)"vis b1,0");
        BlockBankChanges = true;
    }
}
// ====================================================
FLASHMEM void AddWords() // Add in the text words to describe the meaning of numeric config values, so user doesn't have to keep the manual open
{
    uint8_t temp = GetValue((char *)"n14"); // Current governor mode
    static uint8_t last_temp = -1;
    static uint8_t last_temp1 = -1;

    if (temp != last_temp)
    {
        if (temp < 5)
            SendText((char *)"GovMode", Gov_Mode_types[temp]);
        else
            SendText((char *)"GovMode", (char *)"0 - 4 only!");
        last_temp = temp;
    }

    uint8_t temp1 = GetValue((char *)"n28"); // Current throttle type
    if (temp1 != last_temp1)
    {
        if (temp1 < 3)
            SendText((char *)"ThrMode", Throttle_types[temp1]);
        else
            SendText((char *)"ThrMode", (char *)"0 - 2 only!");
        last_temp1 = temp1;
    }
}
// ====================================================
// B103 (15 Oct: the Havoc's diff said "gov_throttle_type = 3"). Rotorflight keeps any number it is sent, even one
// outside its own list, and then calls its settings corrupted (the Configurator will not load such a diff).
// So a governor mode or throttle type outside the list is never sent, nor kept: say which, and stay on the page.
FLASHMEM bool GovChoiceBad(const uint8_t *p, const char *what)
{
    char m[120];
    if (p[18] > 4)
        snprintf(m, sizeof(m), "%s: Governor mode is %u.\r\nIt must be 0 - 4.", what, p[18]);
    else if (p[39] > 2)
        snprintf(m, sizeof(m), "%s: Throttle type is %u.\r\nIt must be 0 - 2. Usually 0 - NORMAL.", what, p[39]);
    else
        return false;
    PlaySound(WHAHWHAHMSG);
    MsgBox((char *)"page RFGovViewGlbl", m);
    return true;
}

// ====================================================
FLASHMEM void HideGOVConfigMsg()
{
    BlockBankChanges = false; // ALWAYS clear — a view change before this call
                              // must never leave the bank switch dead (ClaudeFix 25-8-2026)
    if (CurrentView == RFGOVERNORVIEW_GLOBAL)
    {
        SendCommand((char *)"vis t4,0");
        SendCommand((char *)"vis b1,1");
        ForegroundColourGOVConfigLabels(Black);
        if (RfLive() && !AllGlobalConfigBytesReceived())
        {
            MsgBox((char *)"page RFGovViewGlbl", (char *)"Failed to read global \r\n(config) bytes. Try again.");
            Start_RF_Governor();
        }
        AddWords();
    }
}
// B165: the plain hide, for the read-back's verdict (RF_Verify.h): the message line goes, OK and the labels come back,
// and nothing is asked again - the verdict says what came back, or that nothing did.
FLASHMEM void HideGOVConfigMsgQuiet()
{
    BlockBankChanges = false;
    if (CurrentView != RFGOVERNORVIEW_GLOBAL)
        return;
    SendCommand((char *)"vis t4,0");
    SendCommand((char *)"vis b1,1");
    ForegroundColourGOVConfigLabels(Black);
    AddWords();
}
// B165: the page's own read, as RF_Verify.h asks for it after a save: the flags and the boxes are left as they are (the
// set was whole before the write, and the numbers on the page are the ones just sent)
FLASHMEM void GovCfgAskValues()
{
    if (CurrentView != RFGOVERNORVIEW_GLOBAL) { BlockBankChanges = false; return; }
    GOV_Config_Send_Duration = GOV_GLOBAL_WAIT_TIME;
    Reading_GOV_Config_Now = true;
    AddParameterstoQueue(SEND_GOV_CONFIG_VALUES);
    GOV_Global_Start_Time = millis();
}

// ====================================================
FLASHMEM void GOVS_G_Were_Edited()
{
    SendCommand((char *)"vis b3,1");
    GOVS_GLOBAL_Were_Edited = true;
    AddWords();
}

// ====================================================
// LoadGovConfigWritePayload()
// Reads visible config fields from Nextion into GovWritePayload[18..41]
// Off-screen fields preserved directly from GovAckPayload[]
// U16 fields split into lo/hi byte pairs
// ====================================================
FLASHMEM void LoadGovConfigWritePayload()
{
    // Gov mode and Handover thr — visible, editable
    GovWritePayload[18] = (uint8_t)GetValue((char *)"n14"); // Gov mode
    GovWritePayload[19] = (uint8_t)GetValue((char *)"n15"); // Handover thr %

    const bool big = ScreenIsBig(); // B195: start-up and the filters are on the page only on a 16 MB screen
    uint16_t v;
    if (big)
    {
        v = (uint16_t)GetValue((char *)"n16"); // Start-up (whole seconds: the receiver turns them into tenths)
        GovWritePayload[20] = (uint8_t)(v & 0xFF);
        GovWritePayload[21] = (uint8_t)(v >> 8);
    }
    else
    { // Startup — not on the page: preserve from last FC read
        GovWritePayload[20] = GovAckPayload[20];
        GovWritePayload[21] = GovAckPayload[21];
    }

    // U16 fields — visible, editable
    v = (uint16_t)GetValue((char *)"n17"); // Spoolup ×.1%/s
    GovWritePayload[22] = (uint8_t)(v & 0xFF);
    GovWritePayload[23] = (uint8_t)(v >> 8);

    v = (uint16_t)GetValue((char *)"n18"); // Spooldown ×.1%/s
    GovWritePayload[24] = (uint8_t)(v & 0xFF);
    GovWritePayload[25] = (uint8_t)(v >> 8);

    v = (uint16_t)GetValue((char *)"n19"); // Tracking ×.1%/s
    GovWritePayload[26] = (uint8_t)(v & 0xFF);
    GovWritePayload[27] = (uint8_t)(v >> 8);

    v = (uint16_t)GetValue((char *)"n20"); // Recovery ×.1%/s
    GovWritePayload[28] = (uint8_t)(v & 0xFF);
    GovWritePayload[29] = (uint8_t)(v >> 8);

    v = (uint16_t)GetValue((char *)"n21"); // Hold timeout ×.1s
    GovWritePayload[30] = (uint8_t)(v & 0xFF);
    GovWritePayload[31] = (uint8_t)(v >> 8);

    v = (uint16_t)GetValue((char *)"n22"); // Autorot timeout s
    GovWritePayload[32] = (uint8_t)(v & 0xFF);
    GovWritePayload[33] = (uint8_t)(v >> 8);

    if (big)
    { // B195: the Filters tab
        GovWritePayload[34] = (uint8_t)GetValue((char *)"n23"); // RPM filter Hz
        GovWritePayload[35] = (uint8_t)GetValue((char *)"n24"); // Power filter Hz
        GovWritePayload[36] = (uint8_t)GetValue((char *)"n25"); // D filter ×.1Hz
        GovWritePayload[37] = (uint8_t)GetValue((char *)"n26"); // FF filter Hz
        GovWritePayload[38] = (uint8_t)GetValue((char *)"n27"); // TTA filter Hz
    }
    else
    { // Filter bytes — not on the page: preserve from last FC read
        GovWritePayload[34] = GovAckPayload[34]; // RPM filter Hz
        GovWritePayload[35] = GovAckPayload[35]; // Power filter Hz
        GovWritePayload[36] = GovAckPayload[36]; // D filter ×.1Hz
        GovWritePayload[37] = GovAckPayload[37]; // FF filter Hz
        GovWritePayload[38] = GovAckPayload[38]; // TTA filter Hz
    }

    // Throttle section — visible, editable
    GovWritePayload[39] = (uint8_t)GetValue((char *)"n28"); // Throttle type
    GovWritePayload[40] = (uint8_t)GetValue((char *)"n29"); // Idle thr ×.1%
    GovWritePayload[41] = (uint8_t)GetValue((char *)"n30"); // Auto thr ×.1%
}

// ====================================================
FLASHMEM bool AllGlobalConfigBytesReceived()
{
    for (int i = 0; i < 24; ++i)
    {
        if (Global_Params_Received_Flags[i] == 0)
            return false;
    }
    return true;
}

// ====================================================
// DisplayGovConfigValues()
// Called with byte range [n, m) from GovAckPayload[]
// Receives only two values at a time — mirrors DisplayGovValues()
// Off-screen fields: stored in GovAckPayload[] but not sent to Nextion
// All U16 pairs: skip lo byte, display on hi byte once both are in buffer
// ====================================================
FLASHMEM void DisplayGovConfigValues(uint8_t n, uint8_t m)
{
    if (CurrentView != RFGOVERNORVIEW_GLOBAL)
        return;

    for (uint8_t i = n; i < m; ++i)
    {
        if (i >= GOV_ACK_PAYLOAD_SIZE)
            break;

        if (i >= 18 && (uint8_t)(i - 18) < sizeof(Global_Params_Received_Flags))
            Global_Params_Received_Flags[i - 18] = 1; // mark this config byte as received

        if (AllGlobalConfigBytesReceived() && !RfVerifyPending())
        {
            GOV_Global_Start_Time = 0; // instant timeout — all bytes in (B165: not during a read-back - a set that differs waits for the window's end, another may follow)
        }

        switch (i)
        {
        case 18:
            SendValue((char *)"n14", GovAckPayload[i]);
            break; // Gov mode
        case 19:
            SendValue((char *)"n15", GovAckPayload[i]);
            break; // Handover thr %

        // Startup — off-screen, silent
        case 20:
            break; // lo byte of Startup
        case 21:
            SendValue((char *)"n16", (uint16_t)GovAckPayload[20] | ((uint16_t)GovAckPayload[21] << 8));
            break; // Startup (s) — B195: shown (hidden by the page itself on a 4 MB screen)

        case 22:
            break; // lo byte of Spoolup
        case 23:
            SendValue((char *)"n17", (uint16_t)GovAckPayload[22] | ((uint16_t)GovAckPayload[23] << 8));
            break; // Spoolup ×.1%/s

        case 24:
            break; // lo byte of Spooldown
        case 25:
            SendValue((char *)"n18", (uint16_t)GovAckPayload[24] | ((uint16_t)GovAckPayload[25] << 8));
            break; // Spooldown ×.1%/s

        case 26:
            break; // lo byte of Tracking
        case 27:
            SendValue((char *)"n19", (uint16_t)GovAckPayload[26] | ((uint16_t)GovAckPayload[27] << 8));
            break; // Tracking ×.1%/s

        case 28:
            break; // lo byte of Recovery
        case 29:
            SendValue((char *)"n20", (uint16_t)GovAckPayload[28] | ((uint16_t)GovAckPayload[29] << 8));
            break; // Recovery ×.1%/s

        case 30:
            break; // lo byte of Hold timeout
        case 31:
            SendValue((char *)"n21", (uint16_t)GovAckPayload[30] | ((uint16_t)GovAckPayload[31] << 8));
            break; // Hold timeout ×.1s

        case 32:
            break; // lo byte of Autorot timeout
        case 33:
            SendValue((char *)"n22", (uint16_t)GovAckPayload[32] | ((uint16_t)GovAckPayload[33] << 8));
            break; // Autorot timeout s

        // Filter bytes — B195: the Filters tab (hidden by the page itself on a 4 MB screen)
        case 34:
            SendValue((char *)"n23", GovAckPayload[i]);
            break; // RPM filter Hz
        case 35:
            SendValue((char *)"n24", GovAckPayload[i]);
            break; // Power filter Hz
        case 36:
            SendValue((char *)"n25", GovAckPayload[i]);
            break; // D filter ×.1Hz
        case 37:
            SendValue((char *)"n26", GovAckPayload[i]);
            break; // FF filter Hz
        case 38:
            SendValue((char *)"n27", GovAckPayload[i]);
            break; // TTA filter Hz

        case 39:
            SendValue((char *)"n28", GovAckPayload[i]);
            break; // Throttle type
        case 40:
            SendValue((char *)"n29", GovAckPayload[i]);
            break; // Idle thr ×.1%
        case 41:
            SendValue((char *)"n30", GovAckPayload[i]);
            break; // Auto thr ×.1%

        default:
            break;
        }
    }
}

// ====================================================
// ShowLocalGovConfigBank()
// Shows saved config values from SD card when not connected
// Off-screen fields not sent to Nextion
// ====================================================
FLASHMEM void ShowLocalGovConfigBank()
{
    const bool kept = KeptCopy(KEPT_GOV_GLOBAL, 0); // B180: a copy never kept is not shown as values (Black Thunder 1's "mode 100")
    const uint8_t *c = Saved_GOV_Config_Values;
    uint8_t zero[GOV_CONFIG_PAYLOAD_SIZE] = {0};
    if (!kept)
        c = zero;
    SendValue((char *)"n14", c[18]); // Gov mode
    SendValue((char *)"n15", c[19]); // Handover thr %

    SendValue((char *)"n16", (uint16_t)c[20] | ((uint16_t)c[21] << 8)); // Startup (B195)

    SendValue((char *)"n17", (uint16_t)c[22] | ((uint16_t)c[23] << 8)); // Spoolup
    SendValue((char *)"n18", (uint16_t)c[24] | ((uint16_t)c[25] << 8)); // Spooldown
    SendValue((char *)"n19", (uint16_t)c[26] | ((uint16_t)c[27] << 8)); // Tracking
    SendValue((char *)"n20", (uint16_t)c[28] | ((uint16_t)c[29] << 8)); // Recovery
    SendValue((char *)"n21", (uint16_t)c[30] | ((uint16_t)c[31] << 8)); // Hold timeout
    SendValue((char *)"n22", (uint16_t)c[32] | ((uint16_t)c[33] << 8)); // Autorot timeout

    SendValue((char *)"n23", c[34]); // RPM filter (B195)
    SendValue((char *)"n24", c[35]); // Power filter
    SendValue((char *)"n25", c[36]); // D filter ×.1Hz
    SendValue((char *)"n26", c[37]); // FF filter
    SendValue((char *)"n27", c[38]); // TTA filter

    SendValue((char *)"n28", c[39]); // Throttle type
    SendValue((char *)"n29", c[40]); // Idle thr ×.1%
    SendValue((char *)"n30", c[41]); // Auto thr ×.1%

    if (kept)
        HideGOVConfigMsg();
    else
        ShowGOVConfigMsg(KeptNoneText(0), Gray);
    BlockBankChanges = false;
}

// ====================================================
// SaveToLocalGovConfigBank()
// ====================================================
FLASHMEM void SaveToLocalGovGLOBAL() // "Save FC to SD" button
{ // This function only works when connected. The values are already on screen so it's easy enough.
    
    if (!GetConfirmation((char *)"page RFGovViewGlbl", (char *)"Keep a copy of these governor\r\nsettings on the card?"))
        return;
    
    const bool edited = GOVS_GLOBAL_Were_Edited; // B47: a copy on the card is not a save to the model
    RfGatherStart();   // B187 (was NextionTextMissed = false: now the screen is let finish its queue first)
    LoadGovConfigWritePayload();
    if (RfFieldsMissed("page RFGovViewGlbl")) return;   // B156: a box unanswered (GetValue 65535): nothing kept
    if (GovChoiceBad(GovWritePayload, "Not kept")) // B103
        return;
    ShowGOVConfigMsg((char *)"Keeping a copy on the card ...", Gray);

    for (int i = 18; i < GOV_CONFIG_PAYLOAD_SIZE; ++i)
        Saved_GOV_Config_Values[i] = GovWritePayload[i];
    MarkKept(KEPT_GOV_GLOBAL, 0); // B180

    SaveOneModel(ModelNumber);
    HideGOVConfigMsg();
    if (edited && RfLive())
    { // B47: the typed changes have not reached the model yet: Save stays, and OK still asks
        SendCommand((char *)"vis b3,1");
        GOVS_GLOBAL_Were_Edited = true;
    }
    else
    {
        SendCommand((char *)"vis b3,0");
        GOVS_GLOBAL_Were_Edited = false;
    }
    PlaySound(BEEPCOMPLETE);
}

// ====================================================
// RestoreFromSDGlobalGOV()
// Reads saved config values from SD card, displays them on screen,
// and sends them to the FC via MSP. Only works when connected.
// ====================================================
FLASHMEM void RestoreFromSDGlobalGOV()
{
    if (!LedWasGreen)
    {
        MsgBox((char *)"page RFGovViewGlbl", (char *)"Not connected!\r\nCannot restore to FC.");
        return;
    }

    char why[80];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) // B45: says what it saw; B47/B48: or the pipe is not ready (joining, or none)
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFGovViewGlbl", why);
        return;
    }

    { // B42: only a copy that was kept: never 24 zeros (the governor off) from a model that never kept one. B180: the mark says
        if (!KeptCopy(KEPT_GOV_GLOBAL, 0))
        {
            MsgBox((char *)"page RFGovViewGlbl", (char *)"No copy of the governor settings has\r\nbeen kept on the card for this model.\r\nUse 'Keep a copy' first.");
            return;
        }
    }
    if (GovChoiceBad(Saved_GOV_Config_Values, "Kept copy not sent")) // B103
        return;
    if (!GetConfirmation((char *)"page RFGovViewGlbl", (char *)"Send the kept copy of the governor\r\nsettings to the flight controller?"))
        return;

    ShowGOVConfigMsg((char *)"Sending the kept copy ...", Gray);

    // Copy SD values into GovWritePayload[18..41]
    for (int i = 18; i < GOV_CONFIG_PAYLOAD_SIZE; ++i)
        GovWritePayload[i] = Saved_GOV_Config_Values[i];

    // Show restored values on screen
    ShowLocalGovConfigBank();

    const bool readBack = RfVerifyArm(VK_GOV_CFG, GovCfgAskValues);   // B165: read back after the write and compared with what was sent (the read queued first: the stack sends it last)
    // Send to FC — queue in reverse order (LIFO)
    AddParameterstoQueue(SEND_GOV_WRITE_CONFIG3); // executes 3rd
    AddParameterstoQueue(SEND_GOV_WRITE_CONFIG2); // executes 2nd
    AddParameterstoQueue(SEND_GOV_WRITE_CONFIG1); // executes 1st

    GOVS_GLOBAL_Were_Edited = false;
    SendCommand((char *)"vis b3,0");
    if (readBack) return;                         // "reading back ..." stays up: the verdict does the rest (RF_Verify.h)
    HideGOVConfigMsg();
    PlaySound(BEEPCOMPLETE);
}

// ====================================================
// SendEditedGovConfigValues()
// Writes config values to FC via MSP, then reboots FC
// ====================================================
// B196: the words of a save, once Undo's read of the block (RF_Undo.h UndoPreSave) is in - at once on a 4 MB screen
FLASHMEM static void GovCfgQueueWrite()
{
    const bool readBack = RfVerifyArm(VK_GOV_CFG, GovCfgAskValues);   // B165: read back after the write and compared with what was sent (the read queued first: the stack sends it last)
    // Queue in reverse order — LIFO executes CONFIG1 first, CONFIG2 second, CONFIG3 third
    AddParameterstoQueue(SEND_GOV_WRITE_CONFIG3); // executes 3rd
    AddParameterstoQueue(SEND_GOV_WRITE_CONFIG2); // executes 2nd
    AddParameterstoQueue(SEND_GOV_WRITE_CONFIG1); // executes 1st

    if (CurrentView == RFGOVERNORVIEW_GLOBAL) SendCommand((char *)"vis b3,0");   // (B196: up to 3 s after the press now - only on its own page: the menu has a b3 too)
    if (readBack) return;        // "reading back ..." stays up; the edited flag stays up too, so OK's "Save now?" waits for the verdict (RF_Verify.h clears it when the read-back matches)
    GOVS_GLOBAL_Were_Edited = false;
    PlaySound(BEEPCOMPLETE);

    // Reboot FC is done at receiver.
}
FLASHMEM void SendEditedGovConfigValues()
{
    if (UndoPreBusy()) return;   // B196: this save's read for Undo is out: its words follow (a second press is not a second save)
    if (!RfLive())
    {
        SaveToLocalGovGLOBAL();
        return;
    }

    char why[80];
    if (ModelSeemsArmed(why, sizeof(why)) || RfPipeBlocked(why, sizeof(why))) // B45: says what it saw; B47/B48: or the pipe is not ready (joining, or none)
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFGovViewGlbl", why);
        return;
    }

    if (!AllGlobalConfigBytesReceived())   // B156: the boxes were zeroed for the read: a Save before it is whole would send mode OFF and spool-up 0
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFGovViewGlbl", (char *)"Not saved: the governor settings have\r\nnot all arrived yet. Wait, then Save.");
        return;
    }
    if (RfVerifyPending())   // B165: the last save is still being read back (OK's "Save now?" can ask while it is): one at a time
    {
        PlaySound(WHAHWHAHMSG);
        MsgBox((char *)"page RFGovViewGlbl", (char *)"Not saved yet: the last save is still\r\nbeing read back. Wait for its answer.");
        return;
    }
    RfGatherStart();   // B187 (was NextionTextMissed = false: now the screen is let finish its queue first)
    LoadGovConfigWritePayload();
    if (RfFieldsMissed("page RFGovViewGlbl")) return;   // B156: a box unanswered (GetValue 65535): nothing sent
    if (GovChoiceBad(GovWritePayload, "Not saved")) // B103
        return;
    PlaySound(BEEPMIDDLE);
    DelayWithDog(100);
    UndoPreSave(142, -1, GovCfgQueueWrite, "page RFGovViewGlbl");   // B196: Undo's read of the block first (16 MB screens; at once on a 4 MB one), then the words
}
// ====================================================
FLASHMEM void ShowGOV_Global_Bank()
{
    if (CurrentView == RFGOVERNORVIEW_GLOBAL)
    {
        for (int i = 0; i < GOVERNOR_GLOBAL_LABELS_COUNT; ++i)
            SendValue(GOV_Global_Labels[i], 0);

        // Reset received flags for fresh read
        memset(Global_Params_Received_Flags, 0, sizeof(Global_Params_Received_Flags));

        if (!RfLive())
        {
            ShowGOVConfigMsg((char *)"Loading config values ...", Gray);
            GOVS_GLOBAL_Were_Edited = false;
            ShowLocalGovConfigBank();
            return;
        }

        BlockBankChanges = true;
        ShowGOVConfigMsg((char *)"Loading config values ...", Gray);
        GOV_Config_Send_Duration = GOV_GLOBAL_WAIT_TIME; // heer
        Reading_GOV_Config_Now = true;
        AddParameterstoQueue(SEND_GOV_CONFIG_VALUES);
        GOVS_GLOBAL_Were_Edited = false;
        SendCommand((char *)"vis b3,0");
        GOV_Global_Start_Time = millis();
    }
}

// ====================================================
FLASHMEM void Start_Gov_Global()
{
    if (GOVS_PROFILE_Were_Edited && CurrentView == RFGOVERNORVIEW_PROFILE)
    { // B46: the bank page's edits would go with the page: ask, as OK does
        if (!GetConfirmation((char *)"page RFGovView", (char *)"Discard edited governor values?"))
            return;
        GOVS_PROFILE_Were_Edited = false;
    }
    {
        char why[120];
        if (RfPipeBlocked(why, sizeof(why))) // B48: the pipe first
        {
            PlaySound(WHAHWHAHMSG);
            MsgBox((char *)"page RFGovView", why);
            return;
        }
    }
    AddParameterstoQueue(MSP_INHIBIT_TELEMETRY);
    SendCommand((char *)"page RFGovViewGlbl");
    CurrentView = RFGOVERNORVIEW_GLOBAL;
    SendText((char *)"t27", ModelName);
    ShowGOV_Global_Bank();
    SendText((char *)"b3", (char *)"Save");
}

// ====================================================
FLASHMEM void Save_Gov_Global();
FLASHMEM void End_Gov_Global()
{
    if (UndoPreBusy()) return;   // B196: a save's read for Undo is out (up to 3 s): its words follow on this page, then OK
    if (GOVS_GLOBAL_Were_Edited)
    {
        if (!RfSaveFirst("page RFGovViewGlbl", "The edited governor settings are", Save_Gov_Global, End_Gov_Global, &GOVS_GLOBAL_Were_Edited)) return;   // B102: "Save now?"
        GOVS_GLOBAL_Were_Edited = false;   // (Discard)
        AddParameterstoQueue(MSP_ENABLE_TELEMETRY);
        RotorFlightStart();
    }
    else
    {
        AddParameterstoQueue(MSP_ENABLE_TELEMETRY);
        RotorFlightStart();
    }
}

// ====================================================
FLASHMEM void Restore_FROM_SD_Global_GOV()
{
    // Implementation for restoring from SD card
}
// ====================================================
FLASHMEM void Gov_Global_Were_Edited()
{
    SendCommand((char *)"vis b3,1");
    GOVS_GLOBAL_Were_Edited = true;
}
// B183 (Malcolm, 5 Nov 2026: "a button that offers Defaults"): Rotorflight 2.3's own values (src/main/pg/governor.c) into
// every box on the page - a starting point for a new model, not a tune. Nothing reaches the flight controller until Save,
// which reads the boxes as it reads typed values. On a 4 MB screen the bytes it does not show (startup time, the filters) stay as read.
FLASHMEM void GovGlobalDefaults()
{
    if (CurrentView != RFGOVERNORVIEW_GLOBAL)
        return;
    if (!GetConfirmation((char *)"page RFGovViewGlbl", (char *)"Put Rotorflight's defaults in every box?\r\nNothing goes to the flight controller\r\nuntil you press Save."))
        return;
    SendValue((char *)"n14", 0);  // Governor mode: OFF
    SendValue((char *)"n15", 25); // Handover %
    SendValue((char *)"n22", 15); // Autorotation timeout (s)
    SendValue((char *)"n17", 10); // Spool-up (s)
    SendValue((char *)"n18", 3);  // Spool-down (s)
    SendValue((char *)"n19", 5);  // Speed change / tracking (s)
    SendValue((char *)"n20", 3);  // Quick restart / recovery (s)
    SendValue((char *)"n21", 5);  // Throttle-hold timeout (s)
    SendValue((char *)"n28", 0);  // Throttle type: NORMAL
    SendValue((char *)"n29", 0);  // Idle throttle (tenths of %)
    SendValue((char *)"n30", 0);  // Auto throttle (tenths of %)
    if (ScreenIsBig())
    { // B195: Rotorflight 4.6's own (src/main/pg/governor.c) for the boxes a 16 MB screen shows
        SendValue((char *)"n16", 20); // Start-up 200 tenths = 20 s
        SendValue((char *)"n23", 10); // RPM filter Hz
        SendValue((char *)"n24", 5);  // Power filter Hz
        SendValue((char *)"n25", 50); // D filter 5.0 Hz
        SendValue((char *)"n26", 5);  // FF filter Hz
        SendValue((char *)"n27", 0);  // TTA filter (0 = off)
    }
    Gov_Global_Were_Edited();
}

// ====================================================
FLASHMEM void Save_Gov_Global()
{
    SendEditedGovConfigValues();
    AddWords();
}

#endif // RF_GOVERNOR_GLOBAL_H