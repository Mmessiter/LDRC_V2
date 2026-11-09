// *************************************** Model_IDs.h *****************************************

// This is the code for handling model IDs

#include <Arduino.h>
#include "1Definitions.h"

#ifndef MODEL_IDS_H
#define MODEL_IDS_H

FLASHMEM void CheckAllModelIds()
{ // B204 (Malcolm, 8 Nov 2026: "the presentation looks poor"): a report, not a wheel - one row per model in use, in a fixed-width
  // font so the columns line up (slot, name, ID, and "same as N" where two models share an ID; "no ID stored" where none is), the
  // empty slots left out, and a plain summary below instead of a count box. Screen 1.11.193 draws a list marked "report" from the
  // top, left-aligned, without the wheel's band or wrap.
    char MMemsp[] = "MMems.path=\"";
    char GoIDview[] = "page IDsView";
    char buf[MAXBUFFERSIZE];
    char row[72];
    uint64_t ModelIDs[92];
    uint8_t DuplicatesCount = 0, InUse = 0, Stored = 0;
    uint32_t SavedModelNumber = ModelNumber;

    SendCommand(GoIDview);
    CurrentView = IDCHECKVIEW;
    for (ModelNumber = 1; ModelNumber < MAXMODELNUMBER - 1; ++ModelNumber)
    {
        ReadOneModel(ModelNumber);
        ModelIDs[ModelNumber] = ModelsMacUnionSaved.Val64 & 0x0000FFFFFFFFFFFF;
    }
    buf[0] = 0;
    for (ModelNumber = 1; ModelNumber < MAXMODELNUMBER - 1; ++ModelNumber)
    {
        ReadOneModel(ModelNumber);
        if (strcmp(ModelName, "Not in use") == 0 || strcmp(ModelName, "File error?") == 0)
            continue;
        ++InUse;
        const uint64_t mac = ModelIDs[ModelNumber];
        int same = 0;
        if (mac)
        {
            ++Stored;
            for (unsigned int i = 1; i < MAXMODELNUMBER - 1; ++i)
                if (ModelIDs[i] == mac && i != ModelNumber && !same)
                    same = i;
            if (same)
                ++DuplicatesCount;
        }
        if (!mac)
            snprintf(row, sizeof(row), "%2u  %-16.16s  no ID stored\r\n", (unsigned)ModelNumber, ModelName);
        else if (same)
            snprintf(row, sizeof(row), "%2u  %-16.16s  %012llX  same as %d\r\n", (unsigned)ModelNumber, ModelName, (unsigned long long)mac, same);
        else
            snprintf(row, sizeof(row), "%2u  %-16.16s  %012llX\r\n", (unsigned)ModelNumber, ModelName, (unsigned long long)mac);
        if (strlen(buf) + strlen(row) + 1 < sizeof(buf))
            strcat(buf, row);
    }
    if (!buf[0])
        strcpy(buf, "No models in use\r\n");
    SendOtherText(MMemsp, buf);
    SendValue((char *)"MMems", 0); // the first row at the top
    char summary[64];
    if (DuplicatesCount)
        snprintf(summary, sizeof(summary), "%u of %u IDs are shared: see 'same as'", (unsigned)DuplicatesCount, (unsigned)Stored);
    else if (Stored >= 2)
        snprintf(summary, sizeof(summary), "All %u stored IDs are different.", (unsigned)Stored);
    else if (Stored == 1)
        snprintf(summary, sizeof(summary), "One stored ID: nothing to compare.");
    else
        snprintf(summary, sizeof(summary), "No model has a stored ID yet.");
    SendText((char *)"t1", summary);
    ModelNumber = SavedModelNumber;
    ReadOneModel(ModelNumber);
}

// *********************************************************************************************************************************/
FLASHMEM void DisplayStoredID()
{
    char buf[20];
    if (ModelsMacUnionSaved.Val64)
    {
        sprintf(buf, "%012llX", ModelsMacUnionSaved.Val64 & 0x0000FFFFFFFFFFFF);
        SendText((char *)"t4", buf);
    }
    else
    {
        SendText((char *)"t4", (char *)"No ID stored");
    }
}

FLASHMEM void DisplayCurrentID()
{
    char buf[20];
    if (ModelsMacUnion.Val64)
    {
        sprintf(buf, "%012llX", ModelsMacUnion.Val64 & 0x0000FFFFFFFFFFFF);
        SendText((char *)"t5", buf);
    }
    else
    {
        SendText((char *)"t5", (char *)"No ID received");
    }
}
/******************************************************************************************************************************/
FLASHMEM void DeleteModelID()
{

    // This deletes current model ID
    char prompt[60];
    char p[] = "Delete ID for ";
    char p1[] = "?";
    char Done[] = "Model ID deleted.";
    char DoneAlready[] = "No model ID found.";
    char NotDone[] = "Model ID retained.";

    strcpy(prompt, p);
    strcat(prompt, ModelName);
    strcat(prompt, p1);

    if (!ModelsMacUnionSaved.Val64)
    {
        MsgBox(pModelsIDView, DoneAlready);
        return;
    }
    if (GetConfirmation(pModelsIDView, prompt))
    {
        ModelsMacUnionSaved.Val64 = 0;
        SaveOneModel(ModelNumber);
        MsgBox(pModelsIDView, Done);
    }
    else
    {
        MsgBox(pModelsIDView, NotDone);
    }
    DisplayStoredID();
    DisplayCurrentID();
}
/*********************************************************************************************************************************/

FLASHMEM void StoreModelID()
{ // This stores current model ID

    char prompt[60];
    char p[] = "Store ID for ";
    char p1[] = "?";
    char Done[] = "Model ID stored.";
    char NotDone[] = "Model ID not stored.";
    char DoneAlready[] = "ID was already stored.";
    char NotConnected[] = "No ID to store.";

    strcpy(prompt, p);
    strcat(prompt, ModelName);
    strcat(prompt, p1);

    if (ModelsMacUnion.Val64 == ModelsMacUnionSaved.Val64)
    {
        MsgBox(pModelsIDView, DoneAlready);
        return;
    }
    if (!ModelsMacUnion.Val64)
    {
        MsgBox(pModelsIDView, NotConnected);
        return;
    }

    if (GetConfirmation(pModelsIDView, prompt))
    {
        // ClearDuplicateModelIDs(ModelsMacUnion.Val64); // ensure no duplicates
        PlaySound(MMSAVED);
        ModelsMacUnionSaved.Val64 = ModelsMacUnion.Val64;
        SaveOneModel(ModelNumber);
        MsgBox(pModelsIDView, Done);
    }
    else
    {
        MsgBox(pModelsIDView, NotDone);
    }
    DisplayStoredID();
    DisplayCurrentID();
}
/// *********************************************************************************************************************************/
// B148: this transmitter's own ID, the five bytes a receiver binds to, written the way the receiver's pages and the
// Air Monitor write them (the bind frame carries MacAddress[1..5]; the receiver stores them reversed) - so that two
// transmitters that look alike can be told apart (Malcolm, 27 Oct 2026: "the receiver knows the ID ... but I don't!").
FLASHMEM void DisplayTransmitterID()
{
    char buf[20];
    sprintf(buf, "%02X %02X %02X %02X %02X", MacAddress[5], MacAddress[4], MacAddress[3], MacAddress[2], MacAddress[1]);
    SendText((char *)"t6", buf);
}
FLASHMEM void StartModelIDView()
{
    SendCommand((char *)"page IDsStartView");
    CurrentView = MODELIDVIEW;
    SendText((char *)"t1", ModelName);
    DisplayStoredID();
    DisplayCurrentID();
    DisplayTransmitterID();
}
// *********************************************************************************************************************************/
FLASHMEM void EndModelIDView()
{
    GotoFrontView();
}

#endif // MODEL_IDS_H