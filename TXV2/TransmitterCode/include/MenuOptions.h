// *************************************** MenuOptions.h  *****************************************
#include <Arduino.h>
#include "1Definitions.h"

#ifndef MENUOPTIONS_H
#define MENUOPTIONS_H

/*********************************************************************************************************************************/

void SystemPage1Start()
{
    char lpm[] = "c0"; // Auto model selection
    char Bwn[] = "Bwn";
    char n0[] = "n0";
    char ScreenViewTimeout[] = "Sto"; // needed for display info
    char Pto[] = "Pto";
    char dGMT[] = "dGMT";
    char Tx_Name[] = "TxName";

    FixDeltaGMTSign();
    if (CurrentView == OPTIONVIEW2)
        DeltaGMT = GetValue(dGMT);
    SendCommand(pOptionsViewS); // TX options view
    SendValue(n0, SticksMode);
    SendValue(ScreenViewTimeout, ScreenTimeout);
    SendValue(Pto, (Inactivity_Timeout / TICKSPERMINUTE));
    SendText(Tx_Name, TxName);
    SendValue(lpm, AutoModelSelect);
    SendValue(Bwn, LowBattery);
    CurrentView = OPTIONS_VIEW;
    ClearText();
}

/*********************************************************************************************************************************/

void SystemPage1End()
{
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char Progress[] = "Progress";
    char TxNme[] = "TxName";
    char lpm[] = "c0";
    char Bwn[] = "Bwn";
    char n0[] = "n0";
    char ScreenViewTimeout[] = "Sto"; // needed for display info
    char Pto[] = "Pto";
    char change[] = "change";
    char cleared[] = "XX:";

    SendCommand(ProgressStart);
    // ClaudeFix-16-7-2026 same guard as EndAudioVisualView: a comms error (65535)
    // must keep the previous setting, not become one (the low-battery
    // threshold could silently revert, among others).
    uint32_t gv;
    const uint8_t OldSticksMode = SticksMode;
    gv = GetValue(n0);  if (gv != 65535) SticksMode = CheckRange(gv, 1, 2);
    if (SticksMode != OldSticksMode)
        ResetAllTrims(); // B38: the trim levers follow the sticks (their map is built per stick mode)
    SendValue(Progress, 20);
    GetText(TxNme, TxName, sizeof(TxName));  // ClaudeFix-2-7-2026
    SendValue(Progress, 40);
    gv = GetValue(lpm); if (gv != 65535) AutoModelSelect = gv;
    SendValue(Progress, 50);
    gv = GetValue(Bwn); if (gv != 65535) LowBattery = CheckRange(gv, 10, 100);
    SendValue(Progress, 60);
    gv = GetValue(ScreenViewTimeout); if (gv != 65535) ScreenTimeout = gv;
    SendValue(Progress, 80);
    Inactivity_Timeout = GetValue(Pto) * TICKSPERMINUTE;
    if (Inactivity_Timeout < INACTIVITYMINIMUM)
        Inactivity_Timeout = INACTIVITYMINIMUM;
    if (Inactivity_Timeout > INACTIVITYMAXIMUM)
        Inactivity_Timeout = INACTIVITYMAXIMUM;
    SendValue(Progress, 90);
    FixDeltaGMTSign();
    SaveTransmitterParameters();
    SaveOneModel(ModelNumber); // ClaudeFix-16-7-2026 LowBattery is stored per-model — persist the new threshold NOW, not just at power-off
    SendText(change, cleared);
    SendValue(Progress, 100);
    CurrentView = TXSETUPVIEW;
    SendCommand(pTXSetupView);
    LastTimeRead = 0;
    SendCommand(ProgressEnd);
    UpdateModelsNameEveryWhere();
    ClearText();
    ConfigureStickMode();
}

/*****************************************************************************************************/
void Blank()
{
    return;
}

/*********************************************************************************************************************************/

void EndReverseView()
{ // channel reverse flags are 16 individual BITs in var 'ReversedChannelBITS'
    char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
    uint8_t i;
    char ProgressStart[] = "vis Progress,1";
    char Progress[] = "Progress";
    bool Altered = false;
    char chgs[512];
    char change[] = "change";
    char cleared[] = "XX:";
    for (uint16_t i = 0; i < 500; ++i)
    { // get copy of any changes
        chgs[i] = TextIn[i + 4];
        chgs[i + 1] = 0;
    }
    SendCommand(ProgressStart);
    for (i = 0; i < 16; ++i)
    {
        SendValue(Progress, (i * (100 / 16)));
        if (InStrng(fs[i], chgs))
        {
            Altered = true;
            uint32_t RevVal = GetValue(fs[i]);
            if (RevVal == 65535)
                continue; // comms error -- ClaudeFix-2-7-2026 do NOT flip a channel's direction on garbage
            if (RevVal)
                ReversedChannelBITS |= 1 << i; // set a BIT
            else
                ReversedChannelBITS &= ~(1 << i); // clear a BIT
        }
    }
    SendText(change, cleared);
    if (Altered)
    {
        SaveOneModel(ModelNumber);
    }
    SendCommand(pRXSetupView);
    CurrentView = RXSETUPVIEW;
    UpdateModelsNameEveryWhere();
}

/*********************************************************************************************************************************/

void StartReverseView()
{ // channel reverse flags are 16 individual BITs in ReversedChannelBITS
    char pReverseView[] = "page ReverseView";
    char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
    uint8_t i;
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char Progress[] = "Progress";

    CurrentView = REVERSEVIEW;
    SendCommand(pReverseView);
    UpdateButtonLabels();
    SendCommand(ProgressStart);
    for (i = 0; i < 16; ++i)
    {
        SendValue(Progress, (i * (100 / 16)));
        if (ReversedChannelBITS & 1 << i)
        { // is BIT set??
            SendValue(fs[i], 1);
        }
        else
        {
            SendValue(fs[i], 0);
        }
    }
    SendCommand(ProgressEnd);
    UpdateModelsNameEveryWhere();
}

/*********************************************************************************************************************************/

void FixCHNames() // channel names on Mix screen now with Bank name and enabled status too.
{
    char MixesView_chM[] = "chM";
    char MixesView_chS[] = "chS";
    char BankNameLable[] = "t10";
    char All[] = "All banks";
    SendText(MixesView_chM, ChannelNames[ScreenData[MASTERCHANNEL] - 1]); // show master channel
    SendText(MixesView_chS, ChannelNames[ScreenData[SLAVECHANNEL] - 1]);  // show slave channel
    if (ScreenData[BANK] > 0)
    {
        SendText(BankNameLable, BankNames[BanksInUse[ScreenData[BANK] - 1]]); // Show bank name
    }
    else
    {
        SendText(BankNameLable, All);
    }
}

/*********************************************************************************************************************************/

void ReadMixValues() // just reads from the screen and saves to Mixes array

{
    Mixes[MixNumber][M_MIX_INPUTS] = ScreenData[0];
    Mixes[MixNumber][M_MIX_OUTPUTS] = ScreenData[1];
    Mixes[MixNumber][M_Bank] = ScreenData[2];
    Mixes[MixNumber][M_MasterChannel] = CheckRange(ScreenData[3], 1, 16); // B11: 17-32 wrote past the channel memory every loop
    Mixes[MixNumber][M_SlaveChannel] = CheckRange(ScreenData[4], 1, 16);
    Mixes[MixNumber][M_ONEDIRECTION] = ScreenData[5];
    Mixes[MixNumber][M_Reversed] = ScreenData[6];
    Mixes[MixNumber][M_OFFSET] = constrain((int)(int16_t)ScreenData[7], -100, 100) + 127; // because it's unsigned (B32: signed now, and within -100..100)
    Mixes[MixNumber][M_Percent] = ScreenData[8];
    FixCHNames();
}

/*********************************************************************************************************************************/

void ShowMixValues() // sends mix values to Nextion screen
{
    char MixesView_MixOutput[] = "Enabled";
    char MixesView_MixInput[] = "c0";
    char MixesView_Bank[] = "FlightMode";
    char MixesView_MasterChannel[] = "MasterChannel";
    char MixesView_SlaveChannel[] = "SlaveChannel";
    char MixesView_Reversed[] = "Reversed";
    char MixesView_Percent[] = "Percent";
    char MixesView_chM[] = "chM";
    char MixesView_chS[] = "chS";
    char MixesView_od[] = "od";
    char MixesView_offset[] = "Offset";

    SendValue(MixesView_MixOutput, Mixes[MixNumber][M_MIX_OUTPUTS]); //  load the ScreenData array with the mix values tomorrow
    ScreenData[MIXINPUT] = Mixes[MixNumber][M_MIX_INPUTS];
    SendValue(MixesView_MixInput, Mixes[MixNumber][M_MIX_INPUTS]);
    ScreenData[MIXOUTPUT] = Mixes[MixNumber][M_MIX_OUTPUTS]; // B05: was M_MIX_INPUTS - a typo that switched the mix's output on or off
    SendValue(MixesView_Bank, Mixes[MixNumber][M_Bank]);
    ScreenData[BANK] = Mixes[MixNumber][M_Bank];
    if (Mixes[MixNumber][M_MasterChannel] == 0)
        Mixes[MixNumber][M_MasterChannel] = 1;
    SendValue(MixesView_MasterChannel, Mixes[MixNumber][M_MasterChannel]);
    ScreenData[MASTERCHANNEL] = Mixes[MixNumber][M_MasterChannel];
    if (Mixes[MixNumber][M_SlaveChannel] == 0)
        Mixes[MixNumber][M_SlaveChannel] = 1;
    SendValue(MixesView_SlaveChannel, Mixes[MixNumber][M_SlaveChannel]);
    ScreenData[SLAVECHANNEL] = Mixes[MixNumber][M_SlaveChannel];
    SendValue(MixesView_Reversed, Mixes[MixNumber][M_Reversed]);
    ScreenData[REVERSED] = Mixes[MixNumber][M_Reversed];
    if (Mixes[MixNumber][M_Percent] == 0)
        Mixes[MixNumber][M_Percent] = 100;
    if (Mixes[MixNumber][M_SlaveChannel] == Mixes[MixNumber][M_MasterChannel])
    {
        Mixes[MixNumber][M_SlaveChannel]++;
        SendValue(MixesView_SlaveChannel, Mixes[MixNumber][M_SlaveChannel]);
        ScreenData[SLAVECHANNEL] = Mixes[MixNumber][M_SlaveChannel];
    }
    SendValue(MixesView_Percent, Mixes[MixNumber][M_Percent]);
    ScreenData[PERCENT] = Mixes[MixNumber][M_Percent];
    SendValue(MixesView_od, Mixes[MixNumber][M_ONEDIRECTION]);
    ScreenData[ONEDIRECTION] = Mixes[MixNumber][M_ONEDIRECTION];
    if (((Mixes[MixNumber][M_OFFSET]) > 227) || ((Mixes[MixNumber][M_OFFSET]) < 27))
        Mixes[MixNumber][M_OFFSET] = 127;                          // zeroed if out of range
    SendValue(MixesView_offset, Mixes[MixNumber][M_OFFSET] - 127); // because it's 'unsigned'
    ScreenData[OFFSET] = Mixes[MixNumber][M_OFFSET] - 127;
    SendText(MixesView_chM, ChannelNames[Mixes[MixNumber][M_MasterChannel] - 1]);
    SendText(MixesView_chS, ChannelNames[Mixes[MixNumber][M_SlaveChannel] - 1]);
}

/***************************************************** ShowChannelName ****************************************************************************/

void ShowChannelName()
{
    char MoveToChannel[] = "Mch";
    char MacrosView_chM[] = "chM";
    uint8_t ch = GetValue(MoveToChannel);
    if (ch > 0)
        --ch; // no zero
    if (ch > 15)
        ch = 0; // ClaudeFix-2-7-2026 ChannelNames is [16][11]; a comms error gave 254
    SendText(MacrosView_chM, ChannelNames[ch]);
}
/*********************************************************************************************************************************/

static uint8_t MacroValue(char *box, uint8_t old, int lo, int hi)
{ // B33: a typed value beyond its range is cut to the range (a position over 180 drove the servo past its end and then wiped every macro); a comms error keeps the old value
    const uint32_t v = GetValue(box);
    if (v == 65535)
        return old;
    return (uint8_t)constrain((int)v, lo, hi);
}

void ExitMacrosView()
{
    char MacroNumber[] = "Mno";
    char TriggerChannel[] = "Tch";
    char MoveToChannel[] = "Mch";
    char MoveToPosition[] = "Pos";
    char Delay[] = "Del";
    char Duration[] = "Dur";
    uint8_t n = GetValue(MacroNumber) - 1;
    if (n >= MAXMACROS)
        return; // 0 or a comms-error 65535 ClaudeFix-2-7-2026 would write ~1.5 KB past MacrosBuffer[8][6]
    MacrosBuffer[n][MACROTRIGGERCHANNEL] = MacroValue(TriggerChannel, MacrosBuffer[n][MACROTRIGGERCHANNEL], 0, 16);
    MacrosBuffer[n][MACROMOVECHANNEL] = MacroValue(MoveToChannel, MacrosBuffer[n][MACROMOVECHANNEL], 0, 16);
    MacrosBuffer[n][MACROMOVETOPOSITION] = MacroValue(MoveToPosition, MacrosBuffer[n][MACROMOVETOPOSITION], 0, 180);
    MacrosBuffer[n][MACROSTARTTIME] = MacroValue(Delay, MacrosBuffer[n][MACROSTARTTIME], 0, 255);
    MacrosBuffer[n][MACRODURATION] = MacroValue(Duration, MacrosBuffer[n][MACRODURATION], 0, 255);
    UseMacros = true;
    SaveOneModel(ModelNumber);
    SendCommand(pRXSetupView);
    CurrentView = RXSETUPVIEW;
    UpdateModelsNameEveryWhere();
}

/*********************************************************************************************************************************/
void EndWifiScan()
{
    CurrentView = TXSETUPVIEW;
    SendCommand(pTXSetupView);
    LastTimeRead = 0;
    DoScanEnd();
    UpdateModelsNameEveryWhere();
    ClearText();
}
/*********************************************************************************************************************************/

void StartWifiScan()
{
    if (ModelMatched && BoundFlag)
    { // B24: refused while a model is connected (a scan stops the link and the model goes to failsafe), as Calibrate and Pong refuse
        MsgBox(pTXSetupView, (char *)"The model is connected.\r\nA scan stops its radio link.\r\nSwitch the model off first.");
        return;
    }

    SendCommand(pFhssView);
    DrawFhssBox();
    DoScanInit();
    CurrentMode = SCANWAVEBAND;
    CurrentView = SCANVIEW;
    BlueLedOn();
    ClearText();
}

/***************************************************** Populate Macros View ****************************************************************************/

void PopulateMacrosView()
{
    char MacroNumber[] = "Mno";
    char TriggerChannel[] = "Tch";
    char MoveToChannel[] = "Mch";
    char MoveToPosition[] = "Pos";
    char Delay[] = "Del";
    char Duration[] = "Dur";
    uint8_t n = PreviousMacroNumber;

    if (n < 8)
    { // Read previous values before moveing to next
        MacrosBuffer[n][MACROTRIGGERCHANNEL] = MacroValue(TriggerChannel, MacrosBuffer[n][MACROTRIGGERCHANNEL], 0, 16);
        MacrosBuffer[n][MACROMOVECHANNEL] = MacroValue(MoveToChannel, MacrosBuffer[n][MACROMOVECHANNEL], 0, 16);
        MacrosBuffer[n][MACROMOVETOPOSITION] = MacroValue(MoveToPosition, MacrosBuffer[n][MACROMOVETOPOSITION], 0, 180);
        MacrosBuffer[n][MACROSTARTTIME] = MacroValue(Delay, MacrosBuffer[n][MACROSTARTTIME], 0, 255);
        MacrosBuffer[n][MACRODURATION] = MacroValue(Duration, MacrosBuffer[n][MACRODURATION], 0, 255);
    }
    n = GetValue(MacroNumber) - 1;
    if (n >= MAXMACROS)
        return; // ClaudeFix-2-7-2026 same clamp as ExitMacrosView -- comms error must not index OOB
    SendValue(TriggerChannel, MacrosBuffer[n][MACROTRIGGERCHANNEL]);
    SendValue(MoveToChannel, MacrosBuffer[n][MACROMOVECHANNEL]);
    SendValue(MoveToPosition, MacrosBuffer[n][MACROMOVETOPOSITION]);
    SendValue(Delay, MacrosBuffer[n][MACROSTARTTIME]);
    SendValue(Duration, MacrosBuffer[n][MACRODURATION]);
    ShowChannelName();
    PreviousMacroNumber = n;
}

/******************************************************************************************************************************/
void GotoMacrosView()
{
    char pMacrosView[] = "page MacrosView";
    PreviousMacroNumber = 200; // i.e. no usable number
    SendCommand(pMacrosView);  // Display MacroView
    CurrentView = MACROS_VIEW;
    DelayWithDog(200); // allow enough time for screen to display
    UpdateModelsNameEveryWhere();
    PopulateMacrosView();
}

// ******************************************************************************************************************************
void ShowModelImage() // the picture the model has, named to the page showing: no question asked (V2 B29)
{
    char temp[60];
    strcpy(temp, "exp0.path=\"sd0/images/");
    strcat(temp, ModelImageFileName);
    strcat(temp, ".jpg\"");
    SendCommand(temp);
}
void DisplayModelImage() // asked for and shown: where the name can have changed (a model loaded, a picture chosen)
{
    CheckModelImageFileName();
    ShowModelImage();
}

/******************************************************************************************************************************/
void GotoModelsView()
{
    char prompt[] = "The model is connected.\r\n\r\nOpen Models anyway?";
    if (ModelMatched && BoundFlag)
    {
        if (!GetConfirmation(pRXSetupView, prompt))
            return;
    }

    SaveCurrentModel();
    CheckModelImageFileName(); // (before the page, not after: a page just loaded answers late)
    SendCommand(pModelsView);
    CurrentView = MODELSVIEW;
    ShowModelImage();
    UpdateModelsNameEveryWhere();
    strcpy(MOD, ".MOD");
    BuildDirectory();
    strcpy(Mfiles, "Mfiles");
    LoadFileSelector();
    ShowFileNumber();
    PreviousModelNumber = ModelNumber; // save number
    LoadModelSelector();
}

/******************************************************************************************************************************/
void DoLastTimeRead()
{
    LastTimeRead = 0;
}
/******************************************************************************************************************************/

void ModelViewEnd()
{
    char pr[] = "Select ";
    char buf[60];
    char q[] = "?";
    if (PreviousModelNumber != ModelNumber)
    {
        strcpy(buf, pr);
        strcat(buf, ModelName);
        strcat(buf, q);
        GetConfirmation(pModelsView, buf);
        if (Confirmed[0] != 'Y')
        {
            ModelNumber = PreviousModelNumber;
            ReadOneModel(ModelNumber);
        }
        else
            CentreNotePending = true; // B126: the model chosen is looked at on the front page (CentreNoteTick)
    }
    SaveAllParameters();
    GotoFrontView();
    ModelMatchFailed = false; // allows us to match with selected model.
}

/******************************************************************************************************************************/

// B169 (Malcolm, 2 Nov 2026: "if the user double taps on the name of a backup file on the right-hand side of this screen, I would
// like it to put up a little box which shows the date and time that that file was written"). Both lists of the Models page send
// the same code (1); where the finger lifted (the screen's tch2, its x) says which list it was: the backup list is x 498-788.
// Two taps on the same backup file within a second open the box. The list is a wheel: the first tap turns it so that the file
// tapped sits in the highlighted band, so the second tap is on that band (the help says so). The date is the card's own (the
// file's modify time), right from B169 on: ReadTheRTC now sets the Teensy's clock from the clock chip, and the card's library
// dates every file it writes from that clock (it started at 1 Jan 2019 at every power-up before, so a file written before B169
// carries no real date). B171: tch2 is asked for by its bare name (GetSysValue) - as "tch2.val" the screen answered 0 and no tap
// counted - and a tap's time is when its code arrived, before the 100 ms wait and the reads: the gap between two taps is the
// pilot's, not ours.
static void ShowBackupFileDate(uint32_t row)
{
    if (row >= 150 || TheFilesList[row][0] <= ' ')
        return;
    char name[14];
    int n = 0;
    while (n < 12 && TheFilesList[row][n] > ' ' && TheFilesList[row][n] < 127)
    { // (as ShowFileNumber reads the list: up to 12 characters, to the first blank)
        name[n] = TheFilesList[row][n];
        ++n;
    }
    name[n] = 0;
    AddPath(name); // /mod/NAME.MOD into SearchFile
    char msg[160];
    File f = SD.open(SearchFile, FILE_READ);
    if (!f)
        snprintf(msg, sizeof(msg), "%s\r\nThe file could not be opened.", name);
    else
    {
        static const char Months[12][4] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
        DateTimeFields dt;
        const uint32_t size = f.size();
        const bool dated = f.getModifyTime(dt) && dt.year >= 124; // 2024 or later: a date from a clock that was set
        f.close();
        if (dated)
            snprintf(msg, sizeof(msg), "%s\r\nWritten on %u %s %u at %02u:%02u\r\n(%lu bytes)", name, (unsigned)dt.mday, Months[dt.mon % 12], (unsigned)dt.year + 1900, (unsigned)dt.hour, (unsigned)dt.min, (unsigned long)size);
        else
            snprintf(msg, sizeof(msg), "%s\r\nNo date recorded: it was written before\r\nthe clock reached the card.\r\n(%lu bytes)", name, (unsigned long)size);
    }
    MsgBox(pModelsView, msg);
}
static void BackupFileTapped(uint32_t at) // at = millis() when the tap's code arrived
{
    static uint32_t lastTapMs = 0;
    static uint32_t lastRow = 0xFFFFFFFF;
    const uint32_t x = GetSysValue(SCREEN_X); // where the finger lifted (B171: by its bare name)
    if (x == 65535 || x < 490)
    { // a reply that never came, or the left list
        lastTapMs = 0;
        return;
    }
    const uint32_t row = GetValue((char *)"Mfiles");
    if (row == 65535)
        return;
    const bool twice = row == lastRow && lastTapMs != 0 && (at - lastTapMs) < 1000;
    lastRow = row;
    lastTapMs = at;
    if (!twice)
        return;
    lastTapMs = 0;
    ShowBackupFileDate(row);
}
void DoMFName()
{
    const uint32_t at = millis(); // B171: the tap's time is now, not after the wait and the reads below
    DelayWithDog(100);
    CheckModelName();
    if (CurrentView == MODELSVIEW)
        BackupFileTapped(at); // B169: two quick taps on a backup file say when it was written
}

/******************************************************************************************************************************/
// This function receives upto 50 data elements from the Nextion display and loads it into ScreenData array of uint16_t

void ReceiveLotsofData()
{
    int i = 0;
    union
    {
        uint8_t First4Bytes[4];
        uint32_t FirstDWord;
    } NextionData;

    for (int field = 1; field < 49; ++field)
    {
        int offset = field * 4;
        for (int p = 0; p < 4; ++p)
            NextionData.First4Bytes[p] = TextIn[offset + p];
        const int32_t sv = (int32_t)NextionData.FirstDWord;
        if (NextionData.FirstDWord < 0xFFFF || (CurrentView == MIXESVIEW && i == 7 && sv < 0 && sv >= -200))
        { // B32: a negative Offset arrived as a huge unsigned number and ended the read here, so neither it nor the Percent after it was stored
            ScreenData[i] = (uint16_t)(int16_t)sv;
            ++i;
        }
        else
        {
            break;
        }
    }
    switch (CurrentView)
    {
    case MIXESVIEW:
        ReadMixValues();
        break;
    case DUALRATESVIEW:
        DualRatesRefresh();
        break;
    default:
        break;
    }
}

/******************************************************************************************************************************/

void SaveSwitches()
{
    SaveTransmitterParameters();
    DelayWithDog(100);
    char pTXSetupView[] = "page TXSetupView";
    SendCommand(pTXSetupView);
}

/******************************************************************************************************************************/

void StartTXSetupView()
{
    CurrentView = TXSETUPVIEW;
    SendCommand(pTXSetupView);
    UpdateModelsNameEveryWhere();
    ClearText();
}

/******************************************************************************************************************************/

void StartAudioVisualView()
{

    char n0[] = "n0";
    char n2[] = "n2";
    char n3[] = "n3";
    char h0[] = "h0";
    char Ex1[] = "Ex1"; // slider
    char c0[] = "c0";
    char c1[] = "c1";
    char c2[] = "c2"; // now its variometer
    char c3[] = "c3";
    char c4[] = "c4";
    char c5[] = "c5";
    CurrentView = AUDIOVIEW;
    SendCommand(pAudioView);
    SendValue(Ex1, AudioVolume);
    VariometerBank = CheckRange(VariometerBank, 0, 3);
    SendValue(n2, VariometerBank);
    VariometerThreshold = CheckRange(VariometerThreshold, 0, 1000);
    SendValue(n0, VariometerThreshold);
    VariometerSpacing = CheckRange(VariometerSpacing, 50, 1000);
    SendValue(n3, VariometerSpacing);
    SendValue(h0, Brightness);
    SendValue(c0, PlayFanfare);
    SendValue(c1, TrimClicks);
    SendValue(c2, UseVariometer);
    SendValue(c3, SpeakingClock);
    SendValue(c4, AnnounceBanks);
    SendValue(c5, AnnounceConnected);
    SetAudioVolume(AudioVolume);
    ClearText();
}

/******************************************************************************************************************************/

void EndAudioVisualView()
{
    char n0[] = "n0";
    char n2[] = "n2";
    char n3[] = "n3";
    char c0[] = "c0";
    char c1[] = "c1";
    char c2[] = "c2";
    char c3[] = "c3";
    char c4[] = "c4";
    char c5[] = "c5";
    char Ex1[] = "Ex1"; // slider
    char h0[] = "h0";
    // ClaudeFix-16-7-2026 A comms error (65535) was being STORED: checkboxes flipped
    // themselves on and sliders jumped ("settings spontaneously change").
    // Before the 2-July read-back fix a bad read returned a stale-but-sane
    // value, which hid this; now an error keeps the previous setting.
    // B177 (Malcolm, 4 Nov 2026: "all sound switches had been spontaneously turned off. I had not moved them"): this ran
    // on a 24-bit code 3 that was no press - the tail of a split burst from the log page (Nextion.h) - with another page
    // showing, and the screen answers 0 for every box it has not got: volume 0, the six switches off, the variometer's
    // numbers 0 (the bytes that changed in models.dat on 3 Nov). Split bursts are gone; and this now reads nothing unless
    // this board is on the Sounds page AND the screen shows it: the brightness box is never 0 there (10 at least).
    if (CurrentView != AUDIOVIEW)
    {
        LogSoundsLine("Sounds page OK refused: not on the Sounds page");
        ClearText();
        return;
    }
    uint32_t gv;
    gv = GetValue(h0);
    if (gv == 0)
    {
        LogSoundsLine("Sounds page OK refused: the screen answered 0 for the brightness - it is not showing the page");
        ClearText();
        return;
    }
    if (gv != 65535) Brightness = gv;
    const uint8_t wasVolume = AudioVolume;
    const bool was[6] = {PlayFanfare, TrimClicks, UseVariometer, SpeakingClock, AnnounceBanks, AnnounceConnected};
    gv = GetValue(Ex1); if (gv != 65535) AudioVolume = gv;
    gv = GetValue(n2);  if (gv != 65535) VariometerBank = CheckRange(gv, 0, 3);
    gv = GetValue(n0);  if (gv != 65535) VariometerThreshold = CheckRange(gv, 0, 1000);
    gv = GetValue(n3);  if (gv != 65535) VariometerSpacing = CheckRange(gv, 50, 1000);
    gv = GetValue(c0);  if (gv != 65535) PlayFanfare = gv;
    gv = GetValue(c1);  if (gv != 65535) TrimClicks = gv;
    gv = GetValue(c2);  if (gv != 65535) UseVariometer = gv;
    gv = GetValue(c3);  if (gv != 65535) SpeakingClock = gv;
    gv = GetValue(c4);  if (gv != 65535) AnnounceBanks = gv;
    gv = GetValue(c5);  if (gv != 65535) AnnounceConnected = gv;
    if (wasVolume != AudioVolume || was[0] != PlayFanfare || was[1] != TrimClicks || was[2] != UseVariometer || was[3] != SpeakingClock || was[4] != AnnounceBanks || was[5] != AnnounceConnected)
    { // B177: a change of the sounds is written down, old > new
        char line[140];
        snprintf(line, sizeof(line), "Sounds saved: volume %u>%u fanfare %u>%u clicks %u>%u vario %u>%u clock %u>%u banks %u>%u connected %u>%u",
                 (unsigned)wasVolume, (unsigned)AudioVolume, (unsigned)was[0], (unsigned)PlayFanfare, (unsigned)was[1], (unsigned)TrimClicks, (unsigned)was[2], (unsigned)UseVariometer,
                 (unsigned)was[3], (unsigned)SpeakingClock, (unsigned)was[4], (unsigned)AnnounceBanks, (unsigned)was[5], (unsigned)AnnounceConnected);
        LogSoundsLine(line);
    }
    SetAudioVolume(AudioVolume);
    CurrentView = TXSETUPVIEW;
    SendCommand(pTXSetupView);
    LastTimeRead = 0;
    SaveTransmitterParameters();
    UpdateModelsNameEveryWhere();
    Variometer_InitDone = false; // re-initialise variometer in case settings were changed
    ClearText();
}

// ********************************************************************************************************************************************

void DeleteModel()
{

    char Prompt[60];
    char del[] = "Delete ";
    char ques[] = "?";
    char MMems[] = "MMems";
    char msg[] = "Model deleted!";
    strcpy(Prompt, del);
    strcat(Prompt, ModelName);
    strcat(Prompt, ques);
    const uint32_t Named = ModelNumber; // (10 Nov 2026) the model the question names: ModelName is the one loaded, ModelNumber's
    (void)MMems;
    if (GetConfirmation(pModelsView, Prompt))
    {
        // (10 Nov 2026, the code review) THAT model, not the screen asked again: a missed reply (65535) became model 1 - the
        // wrong model erased -, and a wheel turned meanwhile chose a model the question never named
        if (Named < 1 || Named >= MAXMODELNUMBER)
        {
            ClearText();
            return;
        }
        ModelNumber = Named;
        SetDefaultValues();
        SaveOneModel(ModelNumber);
        LoadModelSelector();
        MsgBox(pModelsView, msg);
    }
    ClearText();
}

// ********************************************************************************************************************************************

void InputsViewEnd()
{
    char ProgressStart[] = "vis Progress,1";
    char Progress[] = "Progress";
    char InputStick_Labels[16][4] = {"c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10", "c11", "c12", "c13", "c14", "c15", "c16"};
    char OutputStick_Labels[16][4] = {"n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12", "n13", "n14", "n15", "n16", "n17", "n18", "n19"};
    char InputTrim_labels[4][4] = {"n0", "n1", "n2", "n3"};
    char changes[260];
    char changes_label[] = "change";
    char ChangesCleared[] = "XX:"; // clear the changes label The two Xs are just so that I can see it even when blank
    bool Altered = false;

    for (uint16_t i = 0; i < 250; ++i) // get the changes from the Nextion TextIn
    {
        changes[i] = TextIn[i + 4];
        changes[i + 1] = 0;
    }

    SendCommand(ProgressStart);
    for (uint8_t i = 0; i < 16; ++i)
    {
        if (InStrng(InputStick_Labels[i], changes)) // if this input stick has changed
        {
            InPutStick[i] = CheckRange((GetValue(InputStick_Labels[i]) - 1), 0, 15); // get the value and check it
            Altered = true;                                                          // set the flag
        }
        if (InStrng(OutputStick_Labels[i], changes)) // if this output channel has changed
        {
            ChannelOutPut[i] = CheckRange((GetValue(OutputStick_Labels[i]) - 1), 0, 15); // get the value and check it
            Altered = true;                                                              // set the flag
        }
        if (i < 4)
        {
            if (InStrng(InputTrim_labels[i], changes)) // if this  trim output has changed
            {
                InputTrim[i] = CheckRange((GetValue(InputTrim_labels[i]) - 1), 0, 15); // get the value and check it
                Altered = true;                                                        // set the flag
            }
        }
        if (Altered)
            SendValue(Progress, (((i + 1) * 100) / 16) - 1);
    }

    if (Altered)
    {
        SendValue(Progress, 95);
        SendText(changes_label, ChangesCleared);
        CheckOutPutChannels();
        SaveOneModel(ModelNumber);
    }
    SendValue(Progress, 100);
    UpdateButtonLabels();
    CurrentView = RXSETUPVIEW;
    SendCommand(pRXSetupView);
    LastTimeRead = 0;
    ClearText();
}
/*********************************************************************************************************************************/
void StartBuddyView()
{
    char BuddyM[] = "BuddyM";
    char BuddyP[] = "BuddyP";
    char pBuddyView[] = "page BuddyView";
    char cb0[] = "cb0";
    char cb1[] = "cb1";
    char cb2[] = "cb2";

    char VisCommand[512];   // Large enough to hold the full command string
    char InVisCommand[512]; // Large enough to hold the full command string

    const char *visCommands[] = {
        "vis t1,1",
        "vis t2,1",
        "vis t3,1",
        "vis t6,1",
        "vis t7,1",
        "vis b0,1",
        "vis cb0,1",
        "vis cb1,1",
        "vis cb2,1"};

    const char *invisCommands[] = {
        "vis t1,0",
        "vis t2,0",
        "vis t3,0",
        "vis t6,0",
        "vis t7,0",
        "vis b0,0",
        "vis cb0,0",
        "vis cb1,0",
        "vis cb2,0"};

    VisCommand[0] = '\0';   // Start with an empty string
    InVisCommand[0] = '\0'; // Start with an empty string

    for (uint8_t i = 0; i < 9; ++i)
    {
        strcat(VisCommand, visCommands[i]);
        strcat(VisCommand, "\xFF\xFF\xFF");
        strcat(InVisCommand, invisCommands[i]);
        strcat(InVisCommand, "\xFF\xFF\xFF");
    }

    SendCommand(pBuddyView); // load the Buddy screen.
    CurrentView = BUDDYVIEW;

    SendValue(BuddyM, BuddyMasterOnWireless);
    SendValue(BuddyP, BuddyPupilOnWireless);
    SendValue(cb0, Buddy_Low_Position);
    SendValue(cb1, Buddy_Mid_Position);
    SendValue(cb2, Buddy_Hi_Position);

    if (BuddyMasterOnWireless)
        SendCommand(VisCommand); // Master options become visible if Master is ON.
    else
        SendCommand(InVisCommand); // master options are invisible if Master is NOT ON.
}

/******************************************************************************************************************************/

void EndBuddyView()
{
    char BuddyM[] = "BuddyM";
    char BuddyP[] = "BuddyP";
    char cb0[] = "cb0";
    char cb1[] = "cb1";
    char cb2[] = "cb2";
    char Prompt[] = "Middle and Up both give control\r\nto the instructor (Master).\r\nKeep these switch positions?";

    {
        const uint32_t p = GetValue(BuddyP), m = GetValue(BuddyM);   // B156: a reply that never came (65535) changes nothing
        if (p != 65535)
            BuddyPupilOnWireless = p;
        if (m != 65535)
            BuddyMasterOnWireless = m;
    }
    WirelessBuddy = BuddyPupilOnWireless || BuddyMasterOnWireless;
    if (WirelessBuddy)
        FHSS_data::PaceMaker = 5; // only 200 HZ for Buddy
    else
        FHSS_data::PaceMaker = PACEMAKER; // flat out speed without buddy

    { // B18: a list closed without a choice says 255 (and a comms error 65535): the old value stays
        uint32_t v;
        v = GetValue(cb0); if (v <= 3) Buddy_Low_Position = v; // here we read what to do at each switch position
        v = GetValue(cb1); if (v <= 3) Buddy_Mid_Position = v;
        v = GetValue(cb2); if (v <= 3) Buddy_Hi_Position = v;
    }

    if (BuddyMasterOnWireless && (!Buddy_Mid_Position && !Buddy_Hi_Position))
    { // Bottom can be master but -- maybe not both top two.
        if (!GetConfirmation(pBuddyView, Prompt))
            return;
    }
    SaveAllParameters();
    UpdateModelsNameEveryWhere();
    RationaliseBuddy();
    GotoFrontView();
}

/******************************************************************************************************************************/
void LoadModelSelector()
{
    char MMemsp[] = "MMems.path=\"";
    char MMems[] = "MMems";
    char crlf[] = {13, 10, 0};
    char lb[] = " (";
    char rb[] = ")";
    char nb[4];
    char buf[MAXBUFFERSIZE];
    char mn[] = "modelname";

    int32_t SavedModelNumber = ModelNumber;
    char mark[] = {(char)0x7F, 0}; // B170: a name begun with DEL is drawn in orange by the screen (1.11.157)
    buf[0] = 0;
    for (ModelNumber = 1; ModelNumber < MAXMODELNUMBER; ++ModelNumber)
    {
        ReadOneModel(ModelNumber);
        if (!ModelsMacUnionSaved.Val64)
        {
            strcpy(lb, " [");
            strcpy(rb, "]");
        }
        else
        {
            strcpy(lb, " (");
            strcpy(rb, ")");
        }
        // B170 (Malcolm, 2 Nov 2026): a model changed since it was last backed up or restored - its record's content CRC is
        // not the one its mark remembers - is shown in orange: the backup is behind. Never backed up: plain.
        if (ModelBackupCrc != 0 && ModelBackupCrc != ModelContentCrc)
            strcat(buf, mark);
        strcat(buf, ModelName);
        strcat(buf, lb);
        Str(nb, ModelNumber, 0);
        strcat(buf, nb);
        strcat(buf, rb);
        strcat(buf, crlf);
    }
    SendOtherText(MMemsp, buf);
    ModelNumber = SavedModelNumber;
    ReadOneModel(ModelNumber);
    SendValue(MMems, ModelNumber - 1);
    SendText(mn, ModelName);
}

/******************************************************************************************************************************/
void SetupViewFM()
{
    SaveAllParameters();
    CurrentView = RXSETUPVIEW;
    SendCommand(pRXSetupView);
    UpdateModelsNameEveryWhere();
}

/******************************************************************************************************************************/
void Options2End()
{ // back to setup?
    char dGMT[] = "dGMT";
    char pTXSetupView[] = "page TXSetupView";
    DeltaGMT = GetValue(dGMT);
    SaveTransmitterParameters();
    CurrentView = TXSETUPVIEW;
    SendCommand(pTXSetupView);
    UpdateModelsNameEveryWhere();
}
/******************************************************************************************************************************/

void OptionView3End() //
{
    char TxVCorrextion[] = "t2";
    char n1[] = "n1";
    char n2[] = "n2";
    char n3[] = "n3";
    char n4[] = "n4";
    char pTXSetupView[] = "page TXSetupView";
    char QNH[] = "Qnh";

    char sw0[] = "sw0";
    char sw1[] = "sw1";
    char n0[] = "n0";

    TxVoltageCorrection = GetValue(TxVCorrextion);
    PowerOffWarningSeconds = GetValue(n2);
    PowerOffWarningSeconds = CheckRange(PowerOffWarningSeconds, 1, 10);
    Qnh = (uint16_t)GetValue(QNH);
    if (LEDBrightness != GetValue(n1))
        UpdateLED();
    ConnectionAssessSeconds = GetValue(n3);
    ConnectionAssessSeconds = CheckRange(ConnectionAssessSeconds, 1, 6);
    ScanSensitivity = GetValue(n4);
    ScanSensitivity = CheckRange(ScanSensitivity, 1, 255);
    MinimumGap = GetValue(n0);
    if (MinimumGap < 10)
        MinimumGap = 10;
    UseLog = GetValue(sw0);
    LogRXSwaps = GetValue(sw1);
    SaveTransmitterParameters();
    CloseModelsFile();
    AddParameterstoQueue(QNH_SETTING); // 2
    AddParameterstoQueue(QNH_SETTING); // repeat it to ensure that it really is sent
    SendCommand(pTXSetupView);
    CurrentView = TXSETUPVIEW;
    UpdateModelsNameEveryWhere();
}

/******************************************************************************************************************************/

void OptionView3Start()
{
    char TxVCorrextion[] = "t2";
    char n1[] = "n1";
    char n2[] = "n2";
    char n3[] = "n3";
    char n4[] = "n4";
    char lpm[] = "c0"; // Low power mode
    char OptionV3Start[] = "page OptionView3";
    char QNH[] = "Qnh";
    char sw0[] = "sw0";
    char sw1[] = "sw1";
    char n0[] = "n0";

    CurrentView = OPTIONVIEW3;
    SendCommand(OptionV3Start);
    DelayWithDog(250);
    SendValue(TxVCorrextion, TxVoltageCorrection);
    SendValue(n2, PowerOffWarningSeconds);
    SendValue(n3, ConnectionAssessSeconds);
    SendValue(n4, ScanSensitivity);
    SendValue(lpm, AutoModelSelect);
    if (LEDBrightness < 15)
        LEDBrightness = DEFAULTLEDBRIGHTNESS;
    SendValue(n1, LEDBrightness);
    SendValue(QNH, Qnh);
    SendValue(sw0, UseLog);
    SendValue(sw1, LogRXSwaps);
    SendValue(n0, MinimumGap);
}

/******************************************************************************************************************************/

void OptionView2Start()
{
    char dGMT[] = "dGMT"; // Time zone
    char n1[] = "n1";
    char n2[] = "n2";
    char n3[] = "n3";

    char OptionV2Start[] = "page OptionView2";
    char TxVCorrextion[] = "t2";

    if (CurrentView == OPTIONVIEW3)
    { //  TODO: And what if was Options 1??

        TxVoltageCorrection = GetValue(TxVCorrextion);
        PowerOffWarningSeconds = GetValue(n2);
        PowerOffWarningSeconds = CheckRange(PowerOffWarningSeconds, 1, 10);
        if (LEDBrightness != GetValue(n1))
            UpdateLED();
        ConnectionAssessSeconds = GetValue(n3);
        ConnectionAssessSeconds = CheckRange(ConnectionAssessSeconds, 1, 6);
        SaveAllParameters();
    }

    CurrentView = OPTIONVIEW2;
    LastTimeRead = 0;
    SendCommand(OptionV2Start);
    DelayWithDog(100);
    SendValue(dGMT, DeltaGMT);
}

/******************************************************************************************************************************/
void ResetClock()
{

    char Prompt[] = "Set clock to firmware build time?";
    char Done[] = "Clock set to firmware build time.";

    if (GetConfirmation(pOptionView2, Prompt))
    {
        SetDS1307ToCompilerTime();
        MsgBox(pOptionView2, Done);
    }
}

/******************************************************************************************************************************/

void BuddyChViewStart()
{
    char pBuddyChView[] = "page BuddyChView";
    char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
    char mSwitch[] = "mSwitch";
    SendCommand(pBuddyChView);
    CurrentView = BUDDYCHVIEW;
    UpdateButtonLabels();
    SendValue(mSwitch, BuddyHasAllSwitches);

    for (int i = 0; i < 16; ++i)
    {
        if (BuddyControlled & 1 << i)
        {
            SendValue(fs[i], 1);
        }
        else
        {
            SendValue(fs[i], 0);
        }
    }
}

/******************************************************************************************************************************/

void BuddyChViewEnd()
{
    char Progress[] = "Progress";
    char ProgressStart[] = "vis Progress,1";
    char fs[16][5] = {"fs1", "fs2", "fs3", "fs4", "fs5", "fs6", "fs7", "fs8", "fs9", "fs10", "fs11", "fs12", "fs13", "fs14", "fs15", "fs16"};
    char mSwitch[] = "mSwitch";
    char mSwi[] = "mSwi"; // not sure why we need this but the full length string is not always found
    bool Altered = false;
    char chgs[512];
    char change[] = "change";
    char cleared[] = "XX:";
    for (uint16_t i = 0; i < 500; ++i)
    { // get copy of any changes
        chgs[i] = TextIn[i + 4];
        chgs[i + 1] = 0;
    }
    SendCommand(ProgressStart);
    if (InStrng(mSwi, chgs))
    {
        if (GetValue(mSwitch))
            BuddyHasAllSwitches = true;
        else
            BuddyHasAllSwitches = false;
        Altered = true;
    }
    for (int i = 0; i < 16; ++i)
    {
        if (InStrng(fs[i], chgs))
        {
            if (GetValue(fs[i]))
            {
                BuddyControlled |= 1 << i;
            }
            else
            {
                BuddyControlled &= ~(1 << i);
            }
            Altered = true;
        }
        SendValue(Progress, i * (100 / 16));
    }
    if (Altered)
    {
        SendText(change, cleared);
        SaveOneModel(ModelNumber);
        CloseModelsFile();
    }
    SendCommand(pBuddyView);
    CurrentView = BUDDYVIEW;
}

// *******************************************************************************************************************************/
void CheckModelImageFileName() // If the file doesn't exist then set to Noimage .
                               // This also covers zero length name and non ascii characters in the name which also are not found.
{ // V2 B29 (Malcolm, 5-10-2026: "occasionally when I returned to the front screen, the image for the model has been
  // forgotten"): the screen is asked whether the picture is there and given 500 ms to answer; busy with a page just
  // loaded, it sometimes answered later, and silence was taken for "no" - the picture's name was thrown away. Now a
  // picture that is NOT there is the only thing that loses the name; silence keeps it (the screen shows its own
  // "no picture" for a name it cannot find). And the asking is done where the name can have changed - a model loaded,
  // a picture chosen - before a page is loaded, not after; the front page shows the name it has (ShowModelImage).
    char temp[30];
    strncpy(temp, ModelImageFileName, sizeof(temp) - 1);
    temp[sizeof(temp) - 1] = '\0';
    if (strlen(temp) <= 8)
        strcat(temp, ".jpg");
    const int answer = NextionFileExistsOnSD3(temp);
    if (answer == 0)
        strcpy(ModelImageFileName, "Noimage");
}
/******************************************************************************************************************************/

void RXOptionsViewStart() // model Options screen
{
    CheckModelImageFileName(); // (before the page, not after: a page just loaded answers late)
    char UseKill[] = "c0";
    char Mchannel[] = "n1";
    char Mvalue[] = "n0";
    char t10[] = "t10";
    char Vbuf[15];
    char RxVCorrextion[] = "n2";
    char c1[] = "c1";
    char n3[] = "n3";
    char Max_Amps[] = "t12";
    char n4[] = "n4"; // TimerDownwards timer minutes
    char c2[] = "c2"; // TimerDownwards timer on off

    SendCommand(pRXSetup1);
    CurrentView = RXSETUPVIEW1;
    SendValue(c1, CopyTrimsToAll);
    SendValue(n3, TrimMultiplier);
    snprintf(Vbuf, 5, "%1.2f", StopFlyingVoltsPerCell);
    SendText(t10, Vbuf);
    
    SendValue(Mvalue, MotorOffMicros()); // B129: in microseconds (it was -100..100: -67 = 833)
    SendValue(Mchannel, MotorChannel + 1);
    SendValue(UseKill, UseMotorKill);
    SendValue(RxVCorrextion, RxVoltageCorrection);
    SendValue(c2, TimerDownwards);
    SendValue((char *)"c3", SixBanks ? 1 : 0); // B130: six banks
    SendCommand((char *)"click c2,0"); // V1B B23: its script shades the minutes box by c2 (the page's start-up ran before c2 came: on, it stayed grey)
    SendValue(n4, TimerStartTime / 60);
    SendValue((char *)"sw0", 1); // redundant
    snprintf(Vbuf, 15, "%d", Max_Safe_Amps); // V1B B23: was "%3.0d", which prints nothing for 0 (the box was blank)
    SendText(Max_Amps, Vbuf);
    ShowModelImage();
    UpdateModelsNameEveryWhere();
}

/******************************************************************************************************************************/

void ReadRXOptionsView() // B23: the page's values into memory (RXOptionsViewEnd reads them and leaves; Help, Model picture and Servos read them and stay)
{
    char UseKill[] = "c0";
    char Mchannel[] = "n1";
    char Mvalue[] = "n0";
    char t10[] = "t10";
    char fbuf[16];
    char RxVCorrextion[] = "n2";
    char c1[] = "c1";
    char n3[] = "n3";
    char n4[] = "n4"; // TimerDownwards timer minutes
    char c2[] = "c2"; // TimerDownwards timer on off

    char ProgressStart[] = "vis Progress,1";
    char Progress[] = "Progress";

    // (10 Nov 2026, the code review) EVERY box here keeps the value it had when the screen's reply is missed (GetValue gives
    // 65535, GetText ""), as the motor-off value and Six banks already did. Before: a missed trim step became 65535 - any trim
    // off centre then drove its channel to the end of its travel until the model was next loaded -, a missed motor channel
    // became channel 3 (the motor's real channel then followed its stick), and a missed 'Stop flying volts' became 0 (no
    // low-battery warning).
    SendCommand(ProgressStart);
    {
        const uint32_t v = GetValue(c1);
        if (v <= 1)
            CopyTrimsToAll = (v == 1);
    }
    SendValue(Progress, 5);
    {
        const uint32_t v = GetValue(n3);
        if (v != 65535)
            TrimMultiplier = CheckRange((int)v, 0, 25); // (as a model's load holds it, SDcard.h)
    }
    NextionTextMissed = false;
    GetText(t10, fbuf, sizeof(fbuf));  // ClaudeFix-2-7-2026
    if (!NextionTextMissed)
        StopFlyingVoltsPerCell = atof(fbuf);

    NextionTextMissed = false;
    GetText((char *)"t12", fbuf, sizeof(fbuf)); // MCMFix-2-7-2026
    if (!NextionTextMissed)
        Max_Safe_Amps = atoi(fbuf);
    NextionTextMissed = false;

    SFV = StopFlyingVoltsPerCell * 100; // this makes it a 16 bit value I can save easily
    SendValue(Progress, 15);
    {
        int32_t mv = (int32_t)GetValue(Mvalue); // B04: below -100 the byte wrapped round to full throttle
        if (mv != 65535)                        // (a comms error keeps the old value)
            MotorChannelZero = MotorOffFromMicros(mv); // B129: microseconds, 500 to 2500, to the byte's 0 to 180
    }
    SendValue(Progress, 30);
    {
        const uint32_t v = GetValue(RxVCorrextion);
        if (v != 65535)
            RxVoltageCorrection = (short int)v;
    }
    SendValue(Progress, 40);
    {
        const uint32_t v = GetValue(UseKill);
        if (v <= 1)
            UseMotorKill = (v == 1);
    }
    SendValue(Progress, 50);
    {
        const uint32_t v = GetValue(Mchannel); // ClaudeFix-2-7-2026 a comms error returned 65535 -> 254 -> OOB writes every loop pass
        if (v >= 1 && v <= 16)
            MotorChannel = (uint8_t)(v - 1);
    }
    SendValue(Progress, 60);
    {
        const uint32_t v = GetValue(c2);
        if (v <= 1)
            TimerDownwards = (v == 1);
    }
    {
        const int six = GetValue((char *)"c3"); // B130: six banks (a comms error, 65535, keeps it as it was)
        if (six == 0 || six == 1)
            SixBanksSet(six == 1);
    }
    SendValue(Progress, 70);
    {
        const uint32_t v = GetValue(n4);
        if (v != 65535)
            TimerStartTime = (uint16_t)(v * 60);
    }

}

/******************************************************************************************************************************/
void RXOptionsViewEnd()
{
    char Progress[] = "Progress";
    char change[] = "change";
    char cleared[] = "XX:";
    ReadRXOptionsView();
    SendValue(Progress, 100);
    CurrentView = RXSETUPVIEW;
    PreviousBank = 42;
    GetBank();
    SaveOneModel(ModelNumber);
    SendText(change, cleared);
    UpdateModelsNameEveryWhere();
    GotoFrontView();
    DelayWithDog(200);
    SendInitialSetupParams();
}

/******************************************************************************************************************************/

void StartServosTypeView() // Frequency and centre pulse width
{
    if (CurrentView == RXSETUPVIEW1)
    { // B23: what was typed on Model options goes with us (the page is drawn afresh afterwards)
        ReadRXOptionsView();
        SaveOneModel(ModelNumber);
    }
    char n_labels[22][5] = {{"n0"}, {"n1"}, {"n2"}, {"n3"}, {"n4"}, {"n5"}, {"n6"}, {"n7"}, {"n16"}, {"n18"}, {"n20"}, {"n8"}, {"n9"}, {"n10"}, {"n11"}, {"n12"}, {"n13"}, {"n14"}, {"n15"}, {"n17"}, {"n19"}, {"n21"}};
    char ch_labels[11][5] = {{"ch1"}, {"ch2"}, {"ch3"}, {"ch4"}, {"ch5"}, {"ch6"}, {"ch7"}, {"ch8"}, {"t13"}, {"t14"}, {"t16"}}; // 11
    char GoServoTypesView[] = "page ServosTypeView";

    SendCommand(GoServoTypesView);

    for (int i = 0; i < 11; ++i)
    {
        SendValue(n_labels[i], ServoFrequency[i]);
        SendValue(n_labels[i + 11], ServoCentrePulse[i]);
        SendText(ch_labels[i], ChannelNames[i]);
    }
    CurrentView = SERVOTYPESVIEW;
    UpdateModelsNameEveryWhere();
}

/******************************************************************************************************************************/

void EndServoTypeView()
{ // Frequency and centre pulse width

    char n_labels[22][5] = {{"n0"}, {"n1"}, {"n2"}, {"n3"}, {"n4"}, {"n5"}, {"n6"}, {"n7"}, {"n16"}, {"n18"}, {"n20"}, {"n8"}, {"n9"}, {"n10"}, {"n11"}, {"n12"}, {"n13"}, {"n14"}, {"n15"}, {"n17"}, {"n19"}, {"n21"}};
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char Progress[] = "Progress";
    bool Altered = false;
    char chgs[512];
    char change[] = "change";
    char cleared[] = "XX:";
    for (uint16_t i = 0; i < 500; ++i)
    { // get copy of any changes
        chgs[i] = TextIn[i + 4];
        chgs[i + 1] = 0;
    }
    SendCommand(ProgressStart);
    for (int i = 0; i < 11; ++i)
    {
        if (InStrng(n_labels[i], chgs))
        {
            ServoFrequency[i] = GetValue(n_labels[i]);
            Altered = true;
        }
        if (InStrng(n_labels[i + 11], chgs))
        {
            ServoCentrePulse[i] = GetValue(n_labels[i + 11]);
            Altered = true;
        }
        SendValue(Progress, (i + 1) * (100 / 11));
    }
    if (ServoFrequency[3] != ServoFrequency[2] || ServoFrequency[9] != ServoFrequency[6])
    { // B51: channel 4 shares channel 3's timer and channel 10 channel 7's (the page shows them in grey; they never came through the change list)
        ServoFrequency[3] = ServoFrequency[2];
        ServoFrequency[9] = ServoFrequency[6];
        Altered = true;
    }
    SendValue(Progress, 100);
    SendCommand(ProgressEnd);
    if (Altered)
    {
        SaveOneModel(ModelNumber);
        SendText(change, cleared);
        AddParameterstoQueue(SERVO_FREQUENCIES);  // SERVO_FREQUENCIES
        AddParameterstoQueue(SERVO_PULSE_WIDTHS); // SERVO_PULSE_WIDTHS
        SendText(change, cleared);
    }
    GotoFrontView();
}
//******************************************************************************************************************************/
void ReturnToModelSetupView()
{
    RXOptionsViewStart();
}

#endif
