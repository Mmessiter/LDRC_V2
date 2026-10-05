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
    if (!LogFileOpen)
    {
        AddPath(TextFileName);
        LogFileNumber = TINYCARD.open(SearchFile, FILE_WRITE);
        LogFileOpen = true;
    }
}
/************************************************************************************************************/
FASTRUN void DeleteLogFile()
{
    AddPath(TextFileName);
    TINYCARD.remove(SearchFile);
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
    char Head[] = "Rename this backup";
    char model[] = "(i.e. just change its filename)";
    char prompt[] = "New filename?";
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
        if (strcmp(Deleteable, SingleModelFile) == 0)
            return;
        Serial.println(SingleModelFile);
        if (CheckFileExists(SingleModelFile))
        {
            strcpy(Prompt, overwr);
            strcat(Prompt, SingleModelFile);
            strcat(Prompt, ques);
            if (GetConfirmation(pModelsView, Prompt))
            {
                WriteBackup();
                AddPath(Deleteable);
                TINYCARD.remove(SearchFile); // ClaudeFix-2-7-2026 backups live in /mod/ -- a bare name removed nothing, leaving both files
            }
        }
        else
        {
            WriteBackup();
            AddPath(Deleteable);
            TINYCARD.remove(SearchFile);
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