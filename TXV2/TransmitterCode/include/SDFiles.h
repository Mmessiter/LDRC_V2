// ********************** SDFiles.h ***********************************************
// This file contains  the functions for opening files to the SD card

#include <Arduino.h>
#include "1Definitions.h"
#include <SD.h>
#include <SPI.h>

#ifndef SD_FILES_H
#define SD_FILES_H

#define TINYCARD SD





// **********************************************************************************************************************************/
// This function adds the needed path and creates 'SearchFile' but doesn't alter the filename.
// It looks at the filename extension to determine which directory to look in.  
// This is because we have different directories for help files, log files, image files and model files.

void AddPath(char *filename)
{
    strcpy(SearchFile, "/");
    if (InStrng((char *)".TXT", filename))
        strcat(SearchFile, "help/");
    if (InStrng((char *)".LOG", filename))
        strcat(SearchFile, "log/");
    if (InStrng((char *)".MOD", filename))
        strcat(SearchFile, "mod/");
    if (InStrng((char *)".jpg", filename))
        strcat(SearchFile, "images/");
    strcat(SearchFile, filename);
}
/****************************************************************************************************************************/
File OpenTextFileForReading()
{
    AddPath(TextFileName);
    File fnumber = TINYCARD.open(SearchFile, FILE_READ);
    if (fnumber)
        LogFileOpen = true;
    return fnumber;
}
/************************************************************************************************************/
FASTRUN void OpenLogFileW()
{
    if (!LogWriteOpen)
    { // B56: the logger's own name and handle
        AddPath(LogWriteName);
        LogWriteFile = TINYCARD.open(SearchFile, FILE_WRITE);
        LogWriteOpen = (bool)LogWriteFile;
    }
}
/************************************************************************************************************/
FASTRUN void DeleteLogFile()
{
    AddPath(TextFileName);
    TINYCARD.remove(SearchFile);
}
/************************************************************************************************************/
// B130: the banks file - banks 5 and 6 of a model in models.dat (SDcard.h BanksBlockBuild / BanksBlockTake: the record has
// no room for them). /banks56/<slot>.b56, the whole block; read only whole. Written only when it would differ from the last
// block written (a trim moved in bank 1 saves the model but leaves this file alone).
#define BANKS_DIR "/banks56"
static void BanksFileName(uint8_t slot, char *p, size_t n) { snprintf(p, n, BANKS_DIR "/%u.b56", (unsigned)slot); }
FLASHMEM bool BanksFileRead(uint8_t slot, uint8_t *blk, int n)
{
    char p[24];
    BanksFileName(slot, p, sizeof(p));
    File f = TINYCARD.open(p, FILE_READ);
    if (!f)
        return false;
    const bool ok = (int)f.size() == n && f.read(blk, n) == n;
    f.close();
    return ok;
}
DMAMEM static uint8_t BanksLast[BANKS_BLOCK_LEN]; // (the last block written, RAM2)
FLASHMEM bool BanksFileWrite(uint8_t slot, const uint8_t *blk, int n)
{
    static uint8_t lastSlot = 0;
    uint8_t *last = BanksLast;
    if (n == BANKS_BLOCK_LEN && slot == lastSlot && memcmp(last, blk, n) == 0)
        return true;
    char p[24];
    BanksFileName(slot, p, sizeof(p));
    if (!TINYCARD.exists(BANKS_DIR))
        TINYCARD.mkdir(BANKS_DIR);
    TINYCARD.remove(p);
    File f = TINYCARD.open(p, FILE_WRITE);
    if (!f)
        return false;
    const bool ok = (int)f.write(blk, n) == n;
    f.close();
    if (ok && n == BANKS_BLOCK_LEN)
    {
        lastSlot = slot;
        memcpy(last, blk, n);
    }
    return ok;
}
/******************************************************************************************************************************/

void DeleteThisLogFile()
{
    char FileBox[] = "FilesBox";
    char prompt[] = "Delete ";
    char pLogFiles[] = "page LogFiles";
    char Query[] = "?";
    char pprompt[80];
    strcpy(TextFileName, TheFilesList[GetValue(FileBox)]);
    strcpy(pprompt, prompt);
    strcat(pprompt, TextFileName);
    strcat(pprompt, Query);
    if (GetConfirmation(pLogFiles, pprompt))
    {
        AddPath(TextFileName);
        TINYCARD.remove(SearchFile);
        strcpy(TextFileName, ""); // B56: a deleted file is not the one OK opens next
        strcpy(MOD, ".LOG");
        BuildDirectory();
        strcpy(Mfiles, "FilesBox");
        LoadFileSelector();
    }
}
// ******************************************************************************************************************************/
/******************************************************************************************************************************/

uint32_t GetFileSize(char *filename)
{

    AddPath(filename);
    File file = TINYCARD.open(SearchFile, FILE_READ);
    if (!file)
        return 0;
    uint32_t size = file.size();
    file.close();
    return size;
}

/*********************************************************************************************************************************/

void WriteEntireBuffer()
{
    ModelsFileNumber.close();
    CloseModelsFile();
    for (int i = 0; i < 3; ++i)
    {
        AddPath(SingleModelFile);
        ModelsFileNumber = TINYCARD.open(SearchFile, FILE_WRITE);
        ModelsFileNumber.seek(0);
        ShortishDelay();
        ModelsFileNumber.write(NewFileBuffer, NewFileBufferPointer);
        ShortishDelay();
        ModelsFileNumber.close();
        ShortishDelay();
    }
}

/******************************************************************************************************************************/

void ShowFreeSpaceEtc()
{

    float FreeSpaceOnSD = ((float)TINYCARD.totalSize() - (float)TINYCARD.usedSize()) / ((float)(1024 * 1024 * 1024));
    float UsedSpaceOnSD = (float)TINYCARD.usedSize() / ((float)(1024 * 1024));

    char t4[] = "t4";
    char t5[] = "t5";
    char t6[] = "t6";
    char NB[20];
    char Gbytes[] = " GB";
    char Mbytes[] = " MB";
    char *Bbytes = Gbytes;

    dtostrf((float)TINYCARD.totalSize() / (float)(1024 * 1024 * 1024), 2, 2, NB);
    AddSpacesBefore(NB, 5);
    strcat(NB, Gbytes);
    SendText(t4, NB);
    dtostrf(FreeSpaceOnSD, 2, 2, NB);
    AddSpacesBefore(NB, 5);
    strcat(NB, Gbytes);
    SendText(t6, NB);

    if (UsedSpaceOnSD >= 100) // less than 100 MB?
    {
        UsedSpaceOnSD /= (float)1024.00;
    }
    else
    {
        Bbytes = Mbytes; // use MB not GB
    }
    dtostrf(UsedSpaceOnSD, 2, 2, NB);
    AddSpacesBefore(NB, 5);
    strcat(NB, Bbytes);
    SendText(t5, NB);
}

/******************************************************************************************************************************/

// This implements the impossible "TINYCARD card rename file" ... by reading, re-saveing under new name, then deleting old file.

void RenameFile()
{
    char ModelsView_filename[] = "filename";
    char Head[] = "Rename backup file";
    char model[] = "Only the file name changes";
    char prompt[] = "New file name";
    char Prompt[50];
    char overwr[] = "Overwrite ";
    char ques[] = "?";
    char Deleteable[42];

    SaveCurrentModel();
    GetText(ModelsView_filename, SingleModelFile, 40);  // ClaudeFix-2-7-2026
    strcpy(Deleteable, SingleModelFile);
    LoadModelForRenaming();
    if (GetBackupFilename(pModelsView, SingleModelFile, model, Head, prompt))
    {
        FixFileName();
        if (strcmp(Deleteable, SingleModelFile) != 0) // B21: the same name = nothing to do, but the live model still comes back (below)
        {
            bool go = true;
            if (CheckFileExists(SingleModelFile))
            {
                strcpy(Prompt, overwr);
                strcat(Prompt, SingleModelFile);
                strcat(Prompt, ques);
                go = GetConfirmation(pModelsView, Prompt);
            }
            if (go && WriteBackup()) // B21: the old file goes only once the new one has been written (a refused name used to delete it all the same)
            {
                AddPath(Deleteable);
                TINYCARD.remove(SearchFile); // ClaudeFix-2-7-2026 backups live in /mod/ -- a bare name removed nothing, leaving both files
            }
        }
    }
    strcpy(MOD, ".MOD");
    BuildDirectory();
    strcpy(Mfiles, "Mfiles");
    LoadFileSelector();
    RestoreCurrentModel();
}

/*********************************************************************************************************************************/

bool CheckFileExists(char *fl)
{
    CloseModelsFile();
    bool exists = false;
    File t;
    AddPath(fl);
    t = TINYCARD.open(SearchFile, FILE_READ);
    if (t)
        exists = true;
    t.close();
    return exists;
}
/*********************************************************************************************************************************/

// B116 (17 Oct 2026). The card library refuses a seek beyond a file's end (SdFat FatFile::seekSet: the position does not
// move), and the bytes are then written where the position was - the end of the file. So a model saved into a slot beyond
// the end of models.dat was written at the end, one record after another, never in its slot, and read back as empty:
// the example card's models.dat is 186,407 bytes (room for 60 models), and Reset transmitter on a card with none filled
// its last few slots that way. So models.dat is filled with zeros to the end of its last slot, once, when it is opened
// short. A zero slot is an empty model (ModelDefined 0, as a slot never written). Not a .MOD file, nor after the link
// changed the pilot's files (LinkChangedUserData: nothing of theirs is written then).
#define MODELS_FILE_SIZE ((uint32_t)TXSIZE + (uint32_t)MAXMODELNUMBER * (uint32_t)MODELSIZE)
extern bool LinkChangedUserData; // (LinkMode.h, included later)
FLASHMEM bool FillModelsFile()
{
    uint32_t Size = (uint32_t)ModelsFileNumber.size();
    if (Size >= MODELS_FILE_SIZE)
        return true;
    if (LinkChangedUserData || !ModelsFileNumber.seek(Size))
        return false;
    uint8_t Zeros[512] = {0};
    while (Size < MODELS_FILE_SIZE)
    {
        const uint32_t n = (MODELS_FILE_SIZE - Size) < sizeof(Zeros) ? (MODELS_FILE_SIZE - Size) : (uint32_t)sizeof(Zeros);
        if (ModelsFileNumber.write(Zeros, n) != n)
            break;
        Size += n;
        KickTheDog();
    }
    ModelsFileNumber.flush();
    return Size >= MODELS_FILE_SIZE;
}

void OpenModelsFile()
{

    char ModelsFile[] = "models.dat";

    if (!ModelsFileOpen)
    {
        if (SingleModelFlag)
        {
            AddPath(SingleModelFile);
            ModelsFileNumber = TINYCARD.open(SearchFile, FILE_WRITE);
            DelayWithDog(100);
        }
        else
        {
            ModelsFileNumber = TINYCARD.open(ModelsFile, FILE_WRITE);
            DelayWithDog(100);
        }
        if (ModelsFileNumber == 0)
        {
            FileError = true;
        }
        else
        {
            ModelsFileOpen = true;
            if (!SingleModelFlag)
                FillModelsFile(); // B116: every slot reachable
        }
    }
}
// *********************************************************************************************************************************/
// V2 B29 (Malcolm, 5-10-2026: "there is a maximum number of log files which I allowed for when setting up the arrays. I
// made no provision for what happens when this is exceeded"): the list of files has room for 96, and a day's flying
// makes one log, so after three months of flying days the newest logs fell off the list. At power-on, with no model
// connected, the log folder is tidied: more than LOGFILES_TOOMANY of them and the oldest go, down to LOGFILES_KEEP.
// The oldest is found from the name (DD-MM-YY.LOG); NO_CLOCK.LOG, no date, counts as the oldest of all.
#define LOGFILES_KEEP 80
#define LOGFILES_TOOMANY 90
static uint32_t LogDateKey(const char *name)
{
    int d = 0, m = 0, y = 0;
    if (sscanf(name, "%d-%d-%d", &d, &m, &y) != 3)
        return 0;
    if (y < 100)
        y += 2000;
    return (uint32_t)y * 10000u + (uint32_t)m * 100u + (uint32_t)d;
}
void TidyLogFolder()
{
    for (int round = 0; round < 60; ++round) // (never for ever: each round removes one file)
    {
        File dir = TINYCARD.open("/log/");
        if (!dir)
            return;
        int count = 0;
        bool any = false;
        uint32_t oldestKey = 0;
        char oldest[32] = "";
        while (true)
        {
            File e = dir.openNextFile();
            if (!e)
                break;
            char nm[32];
            strncpy(nm, e.name(), sizeof(nm) - 1);
            nm[sizeof(nm) - 1] = 0;
            e.close();
            if (!InStrng((char *)".LOG", nm) || InStrng((char *)"._", nm))
                continue;
            ++count;
            const uint32_t k = LogDateKey(nm);
            if (!any || k < oldestKey)
            {
                any = true;
                oldestKey = k;
                strcpy(oldest, nm);
            }
        }
        dir.close();
        if ((round == 0 && count <= LOGFILES_TOOMANY) || count <= LOGFILES_KEEP || !any)
            return;
        char path[48];
        snprintf(path, sizeof(path), "/log/%s", oldest);
        TINYCARD.remove(path);
        KickTheDog();
    }
}
// *********************************************************************************************************************************/
void CheckSDCard()
{
    CRUMB(CRUMB_SDCARD);
    bool SDCARDOK = TINYCARD.begin(BUILTIN_SDCARD); // MUST return true or SD card is not working
    if (!SDCARDOK)
    {
        delay(50); // allow screen to warm up
        SetBrightness(100);
        delay(20);
        MsgBox(pFrontView,(char *)"SD card missing!");
    } else{
        SD_Card_Exists = true;
    }
}
// *********************************************************************************************************************************/
void DeleteMODfile(int p)
{
    int j = 0;
    char prompt[60];
    int i = p + 6;
    char ques[] = "?";
    char del[] = "Delete ";
    while (uint8_t(TextIn[i]) > 0)
    {
        SingleModelFile[j] = TextIn[i];
        ++j;
        ++i;
        SingleModelFile[j] = 0;
    }
    strcpy(prompt, del);
    strcat(prompt, SingleModelFile);
    strcat(prompt, ques);
    if (GetConfirmation(pModelsView, prompt))
    {
        AddPath(SingleModelFile);
        TINYCARD.remove(SearchFile);
        strcpy(MOD, ".MOD");
        BuildDirectory();
        strcpy(Mfiles, "Mfiles");
        LoadFileSelector();
        --FileNumberInView;
        ShowFileNumber();
    }
    CloseModelsFile();
    ClearText();
}
/*********************************************************************************************************************************/
void BuildDirectory() 
{
    char Entry1[30];
    char fn[20];
    int i = 0;
    File dir; // note: ClaudeFix-2-7-2026 left default if MOD matches nothing -- the openNextFile loop below just yields nothing then

    if ((strcmp(MOD, ".LOG") == 0))
        dir = TINYCARD.open("/log/");
    if ((strcmp(MOD, ".TXT") == 0))
        dir = TINYCARD.open("/help/");
    if ((strcmp(MOD, ".MOD") == 0))
        dir = TINYCARD.open("/mod/");
    if ((strcmp(MOD, ".jpg") == 0)){
        dir = TINYCARD.open("/Images/");
    }

    ExportedFileCounter = 0;
    while (true)
    {
        File entry = dir.openNextFile();
        if (!entry || ExportedFileCounter > MAXBACKUPFILES)
            break;
        strncpy(Entry1, entry.name(), sizeof(Entry1) - 1); // ClaudeFix-2-7-2026 SD long filenames can be 255 chars -- strcpy smashed the 30-byte stack buffer
        Entry1[sizeof(Entry1) - 1] = 0;
        if ((InStrng(MOD, Entry1) > 0) && (!InStrng((char *)"._", Entry1)))
        {
            strncpy(fn, entry.name(), sizeof(fn) - 1);
            fn[sizeof(fn) - 1] = 0;
            for (i = 0; i < 12; ++i)
            {
                TheFilesList[ExportedFileCounter][i] = fn[i];   
            }
            ExportedFileCounter++;
        }
        entry.close();
    }
    SortDirectory();
}
#endif // SD_FILES_H