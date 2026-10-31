// ********************************************** Help.h ************************************************************
// This file displays the help screens ... it now uses the log screen
#ifndef HELP_H
#define HELP_H
#include <Arduino.h>
#include "1Definitions.h"
// ******************************************************************************************************************************/
FLASHMEM void SendHelp()
{ // load new help file
    char name[16];
    if (!HelpNameFrom(name)) // B160: the name after "HelpView:", wherever the word sits, completed if it was cut (Nextion.h)
    {   // no whole name came: nothing opens (least of all today's log) and the page goes on as it was
        CurrentView = SavedCurrentView;
        HelpTookRead = false;
        return;
    }
    strcpy(TextFileName, name);
    LogVIEWNew(); // use the same function as for the log files
}
#endif
