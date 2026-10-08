// *************************************** ModelExchange.h  *****************************************
#include <Arduino.h>
#include <RF24.h>
#include "1Definitions.h"

#ifndef MODELEXCHANGE_H
#define MODELEXCHANGE_H

/*********************************************************************************************************************************/
// SEND AND RECEIVE A MODEL FILE
/*********************************************************************************************************************************/

// ON THE AIR (the same since Version 1, and a Version 1 transmitter at either end must still work - B27, 5-10-2026):
//   a fixed pipe, FILECHANNEL, the usual data rate, 32-byte packets with the radio's own auto-ack and CRC-16.
//   Packet 1:  bytes 0-15 the file name, 16-20 the sender's ID, 28-31 the file size.
//   Then 28 bytes of the file in each packet (the last one padded).
// WHAT B27 ADDS, in the bytes a Version 1 transmitter never reads (it zeroes them, or stores only the 28):
//   Packet 1:  byte 21 the protocol (0 = Version 1, 1 = this), bytes 22-23 a CRC-16 of the whole file.
//   Data:      bytes 28-29 the packet's number (1, 2, 3...), 30-31 its complement.
//   The ack:   Version 1 answers each packet with one byte (1) and reads one byte. A B27 receiver answers a B27 sender
//              with four: 1, 'B', and the count of packets stored so far - and a Version 1 sender with the one byte,
//              as ever. (B31: a Version 1 sender given four bytes read one and left the rest in its radio's FIFO, which
//              holds three acks: the fourth could not land, and the transfer died after four packets - Malcolm, 5-10-2026.)
// So a B27 receiver checks the order and the whole file when the sender is B27, and takes a Version 1 sender's file
// as before; a B27 sender sends to either. At the receiving end the file is now written to a scratch name, checked,
// and only then put over the old one; and no end of the transfer can wait for ever.
#define FILEPIPEADDRESS 0xFEFEFEFEFELL // Unique pipe address for FILE EXCHANGE
#define BUFFERSIZE 28                  // + 4 = 32
#define FILEPALEVEL RF24_PA_MAX
#define FILECHANNEL QUIETCHANNEL
#define FILETIMEOUT 30                 // seconds a receiver waits for a sender to begin
#define FILESENDWAIT 15                // B64: seconds a sender keeps offering its first packet, for a receiver that is not listening yet
#define FILEDATATIMEOUT 3000           // ms a receiver waits for the next packet once the transfer has begun
#define FILEPROTOCOL 1                 // packet 1, byte 21: what this firmware sends (Version 1 sends 0)
#define FILESCRATCH "~RECV.MOD"        // the received file, until it has been checked
#define FILEACKLEN 4                   // the ack this firmware answers with (Version 1: 1 byte)

// CRC-16 (CCITT, 0x1021, from 0xFFFF) of a whole file: packet 1 carries it, the receiver checks it before anything is written
static uint16_t FileCrc16(const char *data, uint32_t len)
{
    uint16_t crc = 0xFFFF;
    for (uint32_t i = 0; i < len; ++i)
    {
        crc ^= (uint16_t)((uint8_t)data[i]) << 8;
        for (int b = 0; b < 8; ++b)
            crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

// B68 (Malcolm, 8 Oct, the second transmitter: "I had to press Receive more than once", and the screen's record of what it
// sent: Receive, Yes, and the main board straight back to the Models page). The exchange gave up its wait on ANY bytes from the
// screen ("the user can abandon by hitting a button"), and the Yes button of the "Overwrite?" box prints its word on the
// press AND on the lift: a finger that lifted a little late put the second word into the wait, and the wait ended at once.
// Now only the exchange page's own button (code 128+61, the one button FileExchView has) abandons; everything else the
// screen may say meanwhile - a lift, the page's "UKRULES", a late reply, the time from the internet - is read and let go.
static bool ExchangeAbandoned()
{
    if (!GetButtonPress())
        return false;
    return (uint8_t)TextIn[0] == 128 + 61;
}
/*********************************************************************************************************************************/
void ShowFileProgress(char *Msg)
{
    char t1[] = "t1";
    SendText(t1, Msg); //
}
/*********************************************************************************************************************************/
void ShowFileTransferWindow()
{
    char gofw[] = "page FileExchView";
    SendCommand(gofw);
    CurrentView = FILEEXCHANGEVIEW;
}
/*********************************************************************************************************************************/
void StoreBuffer(char *Buf, uint32_t len)
{
    for (uint16_t i = 0; i < len; ++i)
    {
        if ((NewFileBufferPointer + i) >= MAXFILELEN)
            break;
        NewFileBuffer[NewFileBufferPointer + i] = Buf[i];
    }
    NewFileBufferPointer += len;
}


/*********************************************************************************************************************************/

void ShowRemoteID()
{ // Show remote ID
    char nb2[5];
    char msg[50];
    char GoModelsView[] = "page ModelsView";
    strcpy(msg, "Remote ID = ");
    for (int i = 0; i < 5; ++i)
    {
        snprintf(nb2, 4, "%X", BuddyMacAddress[i]);
        strcat(msg, nb2);
        strcat(msg, " ");
    }
    MsgBox(GoModelsView, msg);
}

/*********************************************************************************************************************************/

/** @brief SEND A MODEL FILE */
void SendModelFile()
{
    uint64_t TXPipe;
    uint8_t Fack[32];
    unsigned long Fsize = 0;
    unsigned long Fposition = 0;
    char Fbuffer[BUFFERSIZE + 8]; // spare space
    uint16_t PacketNumber = 0;    // 1 = the name packet; then the data packets 1, 2, 3... are PacketNumber - 1
    int p = 5;
    char nb1[20];
    char Sent[] = "Sent ";
    char of[] = " of ";
    char msg[150];
    char bytes[] = " bytes.";
    char ModelsView_filename[] = "filename";
    char t0[] = "t0";
    char Fsend[] = "Sending file";
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char GoModelsView[] = "page ModelsView";
    char Progress[] = "Progress";
    bool ReceiverConnected = false;
    bool ReceiverIsB27 = false;      // it answers with the longer ack
    uint16_t ReceiverStored = 0;     // what its last ack said

    if (strlen(SingleModelFile) > 15)
    { // packet 1 has 16 bytes for the name (the sender's ID follows at byte 16): a longer name would be cut, or read wrong
        strcpy(msg, "                Cannot send!\r\n\r\nThe file name is too long\r\n(15 characters at most).");
        MsgBox(GoModelsView, msg);
        SendCommand(GoModelsView);
        CurrentView = MODELSVIEW;
        return;
    }
    BlueLedOn();
    CloseModelsFile();
    ShowFileTransferWindow();
    SendText(ModelsView_filename, SingleModelFile);
    SendText(t0, Fsend);
    SendCommand(ProgressStart);
    SendValue(Progress, p);
    DelayWithDog(10);
#ifdef DB_MODEL_EXCHANGE
    Serial.print("Sending model: ");
    Serial.println(SingleModelFile);
#endif
    TXPipe = FILEPIPEADDRESS;
    AddPath(SingleModelFile);
    ModelsFileNumber = SD.open(SearchFile, O_READ); // Open file for reading
    Fsize = ModelsFileNumber.size();                     // Get file size
    if (Fsize == 0 || Fsize > MAXFILELEN)
    {
        ModelsFileNumber.close();
        strcpy(msg, "                Cannot send!\r\n\r\nThe file could not be read.");
        SendCommand(ProgressEnd);
        RedLedOn();
        MsgBox(GoModelsView, msg);
        SendCommand(GoModelsView);
        CurrentView = MODELSVIEW;
        return;
    }
    // The whole file into RAM first: its CRC goes in packet 1, and the packets then come from RAM, not the card
    ModelsFileNumber.seek(0);
    const uint32_t got = ModelsFileNumber.read(NewFileBuffer, Fsize);
    ModelsFileNumber.close();
    if (got != Fsize)
    {
        strcpy(msg, "                Cannot send!\r\n\r\nThe file could not be read.");
        SendCommand(ProgressEnd);
        RedLedOn();
        MsgBox(GoModelsView, msg);
        SendCommand(GoModelsView);
        CurrentView = MODELSVIEW;
        return;
    }
    const uint16_t crc = FileCrc16(NewFileBuffer, Fsize);
#ifdef DB_MODEL_EXCHANGE
    Serial.print("File Size: ");
    Serial.print(Fsize);
    Serial.println(" bytes.");
#endif
    ConfigureRadio(); //  Start from known state
    Radio1.setChannel(FILECHANNEL);
    Radio1.setPALevel(FILEPALEVEL, true);
    Radio1.setRetries(2, 15);
    Radio1.openWritingPipe(TXPipe);
    Radio1.stopListening();
    DelayWithDog(4);

    while ((Fposition < Fsize))
    {
        KickTheDog(); // Watchdog
        p = ((float)Fposition / (float)Fsize) * 100;
        strcpy(msg, Sent);
        strcat(msg, Str(nb1, Fposition, 0));
        strcat(msg, of);
        strcat(msg, Str(nb1, Fsize, 0));
        ShowFileProgress(msg);
        SendValue(Progress, p);
        ++PacketNumber;
        for (int q = 0; q < 36; ++q)
        { // clear buffer
            Fbuffer[q] = 0;
        }
        if (PacketNumber == 1)
        {
            strcpy(Fbuffer, SingleModelFile); // Filename in first packet (add in the mac address  as there is space!)
            Fbuffer[BUFFERSIZE] = Fsize;
            Fbuffer[BUFFERSIZE + 1] = Fsize >> 8;
            Fbuffer[BUFFERSIZE + 2] = Fsize >> 16;
            Fbuffer[BUFFERSIZE + 3] = Fsize >> 24; // SEND FILE SIZE (four bytes)
            for (int q = 0; q < 5; ++q)
            {
                Fbuffer[q + 16] = MacAddress[q + 1]; // Add only 5 bytes of the macaddress to buffer at offset 16 and sent it too! 
            }
            Fbuffer[21] = FILEPROTOCOL;  // (bytes 21-27: Version 1 sends zeros here and never reads them)
            Fbuffer[22] = crc;
            Fbuffer[23] = crc >> 8;
        }
        else
        {
            const uint32_t n = (Fsize - Fposition) < BUFFERSIZE ? (Fsize - Fposition) : BUFFERSIZE;
            memcpy(Fbuffer, NewFileBuffer + Fposition, n); // the next part of the file (the last one padded with zeros)
            Fposition += n;
            const uint16_t seq = PacketNumber - 1;         // (bytes 28-31: Version 1 sends zeros, stores only the 28)
            Fbuffer[BUFFERSIZE] = seq;
            Fbuffer[BUFFERSIZE + 1] = seq >> 8;
            Fbuffer[BUFFERSIZE + 2] = (uint8_t)~seq;
            Fbuffer[BUFFERSIZE + 3] = (uint8_t)(~seq >> 8);
        }
        ReceiverConnected = (Radio1.write(&Fbuffer, BUFFERSIZE + 4)); //  we added error checking for RX not ready. Now we maybe need a real checksum
        if (!ReceiverConnected && PacketNumber == 1)
        { // B64 (Malcolm, 7 Oct, the first exchange between two V2s: "I had to press Receive several times"): the radio gives
          // up on an unanswered packet in ten milliseconds, so Send pressed before Receive failed at once. Now the first
          // packet is offered again every tenth of a second for FILESENDWAIT seconds; the other end may press Receive meanwhile.
            for (int q = 0; q < 10; ++q)
            { // (as the receiver does before its wait: a press still pending from the Send button must not end this one)
                delay(5);
                KickTheDog();
                GetButtonPress();
                ClearText();
            }
            const uint32_t t0 = millis();
            int lastShown = -1;
            bool abandoned = false;
            while (!ReceiverConnected)
            {
                KickTheDog();
                if (ExchangeAbandoned())
                {
                    abandoned = true;
                    break;
                }
                const int elapsed = (millis() - t0) / 1000;
                if (elapsed >= FILESENDWAIT)
                    break;
                if (elapsed != lastShown)
                {
                    lastShown = elapsed;
                    strcpy(msg, "Waiting for the receiver ");
                    strcat(msg, Str(nb1, FILESENDWAIT - elapsed, 0));
                    strcat(msg, "...");
                    ShowFileProgress(msg);
                }
                DelayWithDog(100);
                ReceiverConnected = (Radio1.write(&Fbuffer, BUFFERSIZE + 4));
            }
            if (abandoned)
            {
                ButtonWasPressed();
                NormaliseTheRadio();
                SendCommand(ProgressEnd);
                RedLedOn();
                SendCommand(GoModelsView);
                CurrentView = MODELSVIEW;
                CloseModelsFile();
                ConfigureRadio();
                return;
            }
        }
        if (!ReceiverConnected)
            break;
        if (Radio1.available())
        { // the ack's payload: Version 1 says one byte; B27 says four (1, 'B', the count stored so far)
            uint8_t n = Radio1.getDynamicPayloadSize();
            if (n > sizeof(Fack))
                n = sizeof(Fack);
            if (n)
                Radio1.read(Fack, n);
            if (n >= FILEACKLEN && Fack[1] == 'B')
            {
                ReceiverIsB27 = true;
                ReceiverStored = Fack[2] | (uint16_t)Fack[3] << 8;
            }
        }
#ifdef DB_MODEL_EXCHANGE
        Serial.print(PacketNumber);
        if (ReceiverIsB27)
        {
            Serial.print(" rx stored ");
            Serial.print(ReceiverStored);
        }
        Serial.println();
#endif
    }
#ifdef DB_MODEL_EXCHANGE
    Serial.println("ALL SENT.");
#endif
    SendValue(Progress, 100);
    (void)ReceiverIsB27; (void)ReceiverStored; // (seen in the debug print; the hardware's acks already guarantee delivery)
    if (ReceiverConnected)
        DelayWithDog(750);
    NormaliseTheRadio();
    SendCommand(ProgressEnd);
    RedLedOn();
    if (ReceiverConnected)
    {
        strcpy(msg, Sent);
        strcat(msg, Str(nb1, Fsize, 0));
        strcat(msg, bytes);
        PlaySound(BEEPCOMPLETE);
        ShowFileProgress(msg);
        DelayWithDog(2000);
    }
    else
    {
        if (PacketNumber <= 1)
            strcpy(msg, "                Cannot send!\r\n\r\nReceiving transmitter not ready. \r\n\r\n                File not sent.");
        else
            strcpy(msg, "                Cannot send!\r\n\r\nThe receiving transmitter stopped\r\nanswering. \r\n\r\n                File not sent.");
        for (int i = 0; i < 3; ++i)
        {
            PlaySound(BEEPMIDDLE);
            DelayWithDog(130);
        }
        MsgBox(GoModelsView, msg);
    }
    SendCommand(GoModelsView);
    CurrentView = MODELSVIEW;
    CloseModelsFile();
    ConfigureRadio();
}

/***************************************************************************************************************************************************/
/**************************************************** RECEIVE A MODEL FILE *************************************************************************/
/***************************************************************************************************************************************************/

// The transfer is over, for better or worse: the radio as it was, the LED, a word on the screen, back to the models page
static void ReceiveAbandoned(const char *why, bool sadSound)
{
    char ModelsView_filename[] = "filename";
    char ProgressEnd[] = "vis Progress,0";
    SendText(ModelsView_filename, (char *)why);
    NormaliseTheRadio();
    SendCommand(ProgressEnd);
    RedLedOn();
    if (sadSound)
        PlaySound(WHAHWHAHMSG);
    DelayWithDog(2000);
    GotoModelsView();
    ClearText();
}

/** @brief RECEIVE A MODEL FILE */
void ReceiveModelFile()
{
    uint64_t RXPipe;
    uint32_t RXTimer = 0;
    char ModelsView_filename[] = "filename";
    char Fbuffer[BUFFERSIZE + 8]; // spare space
    uint8_t Fack[FILEACKLEN] = {1, 'B', 0, 0}; // Version 1 sends the 1 alone; the rest is for a B27 sender
    char Waiting[] = "Waiting ";
    char WaitTime[6];
    char WaitMsg[17];
    char ThreeDots[] = "...";
    char Receiving[] = "Receiving: ";
    char fnamebuf[30];
    char TimeoutMsg[] = "TIMEOUT";
    char Success[] = "* Success! *";
    unsigned long Fsize = 0;
    unsigned long Fposition = 0;
    uint8_t p = 5;
    char nb1[40];
    int LastSecondShown = -1;

    char Received[] = "Received ";
    char of[] = " of ";
    char msg[50];
    char bytes[] = " bytes.";
    char t0[] = "t0";
    char RXheader[] = "File receive";
    char ovwr[] = "Overwrite ";
    char ques[] = "?";
    char ProgressStart[] = "vis Progress,1";
    char ProgressEnd[] = "vis Progress,0";
    char GoModelsView[] = "page ModelsView";
    char Progress[] = "Progress";
    uint8_t Protocol = 0;          // packet 1, byte 21: 0 = a Version 1 sender (no packet numbers, no CRC), 1 = B27
    uint16_t FileCrc = 0;          // packet 1, bytes 22-23 (B27)
    uint16_t Expected = 1;         // the data packet that should come next (B27)
    uint16_t Stored = 0;           // data packets stored so far (told to a B27 sender in the ack)
    char FinalName[40];            // the name the file will have once it has been checked

    if (strcmp(ModelName, "Not in use"))
    {                      // If not in use, we can overwrite it without asking
        strcpy(msg, ovwr); // Ask user if they want to overwrite current model
        strcat(msg, ModelName);
        strcat(msg, ques);
        if (!GetConfirmation(GoModelsView, msg))
            return; // Get confirmation or quit
    }

    BlueLedOn();
    ShowFileTransferWindow();
    SendText(ModelsView_filename, Waiting);
    SendText(t0, RXheader);

    ConfigureRadio(); //  Start from known state

    RXPipe = FILEPIPEADDRESS;
    Radio1.setRetries(2, 15);
    Radio1.setChannel(FILECHANNEL);
    Radio1.flush_tx();
    Radio1.flush_rx();
    Radio1.openReadingPipe(1, RXPipe);
    Radio1.startListening();
    NewFileBufferPointer = 0;

    CloseModelsFile();

    for (int q = 0; q < 36; ++q)
    {
        Fbuffer[q] = 0;   // clear buffer for the sender's macaddress
        delay(5);         // give the radio a chance to clear the buffer
        KickTheDog();     // Keep Watchdog happy
        GetButtonPress(); // Clear any pending button presses so they won't stop next bit ...
        ClearText();      // Clear any pending text
    }
    RXTimer = millis(); // Start timer
    while (!Radio1.available())
    { // Await the sender....
        delay(1);
        if (ExchangeAbandoned())
        { // user can abandon the transfer wait by hitting the page's button now (B68: and nothing else ends it)
            GotoModelsView();
            ClearText();
            NormaliseTheRadio();
            ButtonWasPressed();
            return;
        }
        KickTheDog(); // Watchdog
        const int SecondsElapsed = (millis() - RXTimer) / 1000;
        if (SecondsElapsed >= FILETIMEOUT)
        { // 30 seconds have elapsed and no file was received
            SendText(ModelsView_filename, TimeoutMsg);
            NormaliseTheRadio();
            RedLedOn();
            PlaySound(WHAHWHAHMSG);
            DelayWithDog(2000);
            GotoModelsView();
            return; // Give up waiting
        }
        if (SecondsElapsed != LastSecondShown)
        { // once a second (it was once a pass: a thousand times a second)
            LastSecondShown = SecondsElapsed;
            strcpy(WaitMsg, Waiting);
            strcat(WaitMsg, Str(WaitTime, (FILETIMEOUT - SecondsElapsed), 0));
            strcat(WaitMsg, ThreeDots);
            SendText(ModelsView_filename, WaitMsg); // Show user how long remains to wait
        }
    } // *First* packet must have arrived!

    DelayWithDog(5);
    Radio1.read(&Fbuffer, BUFFERSIZE + 4); //  Read first packet (the ack it needs goes out by itself; the ack PAYLOADS begin once the sender's kind is known, below)
    char FirstPacket[BUFFERSIZE + 4];
    memcpy(FirstPacket, Fbuffer, BUFFERSIZE + 4); // (B64: to know it again if the sender offers it twice)
    SendCommand(ProgressStart);
    SendValue(Progress, p);
    SendText(ModelsView_filename, Receiving);
    strncpy(SingleModelFile, Fbuffer, 16); //  Get filename (16 bytes at most: the sender's ID follows)
    SingleModelFile[16] = 0;
    Fsize = (uint8_t)Fbuffer[BUFFERSIZE];
    Fsize += (uint32_t)(uint8_t)Fbuffer[BUFFERSIZE + 1] << 8;
    Fsize += (uint32_t)(uint8_t)Fbuffer[BUFFERSIZE + 2] << 16;
    Fsize += (uint32_t)(uint8_t)Fbuffer[BUFFERSIZE + 3] << 24; //  Get file size
    Protocol = (uint8_t)Fbuffer[21];
    FileCrc = (uint8_t)Fbuffer[22] | (uint16_t)(uint8_t)Fbuffer[23] << 8;
    if (Protocol > FILEPROTOCOL)
        Protocol = 0; // (a sender newer than this firmware: read as Version 1, which every sender still is underneath)
    const uint8_t AckLen = Protocol >= 1 ? FILEACKLEN : 1; // a Version 1 sender gets the one byte it reads; a B27 sender the four
    Radio1.writeAckPayload(1, Fack, AckLen);               // the first ack payload, for the first data packet

    if (Fsize == 0 || Fsize > MAXFILELEN || SingleModelFile[0] == 0 || !InStrng((char *)".MOD", SingleModelFile))
    {   // ClaudeFix-2-7-2026 a bogus size off the air used to trap the receive loop forever and
        // over-read the RAM buffer -- reject it cleanly (B27: a name that is not a model file's, too)
        ReceiveAbandoned("Transfer error", true);
        return;
    }

    for (int q = 0; q < 5; ++q)
    {
        BuddyMacAddress[q] = Fbuffer[q + 16]; // sender's macaddress is in buffer at offset 16 - get it 
                                              //  if (q == 0) ++BuddyMacAddress[q];     // add one to lowest byte to make it unique 
    }

#ifdef DB_MODEL_EXCHANGE
    Serial.println("CONNECTED!");
    Serial.print("FileName=");
    Serial.println(SingleModelFile);
    Serial.print("File size = ");
    Serial.println(Fsize);
    Serial.print("Protocol = ");
    Serial.println(Protocol);
#endif

    Fposition = 0;
    strcpy(fnamebuf, Receiving);
    strcat(fnamebuf, SingleModelFile);
    SendText(ModelsView_filename, fnamebuf);
    RXTimer = millis(); //  zero timeout
    while (Fposition < Fsize)
    {    
        KickTheDog(); //  Watchdog
        if (ExchangeAbandoned())
        { // user can abandon the transfer by hitting the page's button
            ButtonWasPressed();
            NormaliseTheRadio();
            SendCommand(ProgressEnd);
            RedLedOn();
            GotoModelsView();
            return;
        }
        if (Radio1.available())
        {
            Fack[2] = Stored;
            Fack[3] = Stored >> 8;
            Radio1.writeAckPayload(1, Fack, AckLen);
            DelayWithDog(5);
            Radio1.read(&Fbuffer, BUFFERSIZE + 4);
            RXTimer = millis();
            if (Protocol >= 1 && Expected == 1 && memcmp(Fbuffer, FirstPacket, BUFFERSIZE + 4) == 0)
                continue; // B64: the first packet again (its ack went astray and the sender offered it once more): already read
            if (Protocol >= 1)
            { // B27 sender: every data packet carries its number. The same again is dropped, anything else is a lost packet.
                const uint16_t seq = (uint8_t)Fbuffer[BUFFERSIZE] | (uint16_t)(uint8_t)Fbuffer[BUFFERSIZE + 1] << 8;
                const uint16_t inv = (uint8_t)Fbuffer[BUFFERSIZE + 2] | (uint16_t)(uint8_t)Fbuffer[BUFFERSIZE + 3] << 8;
                if ((uint16_t)~seq != inv)
                {
                    ReceiveAbandoned("Transfer error", true);
                    return;
                }
                if (seq == Expected - 1)
                    continue; // (sent again after its ack went astray: already stored)
                if (seq != Expected)
                {
                    ReceiveAbandoned("Transfer error: lost sync", true);
                    return;
                }
                ++Expected;
            }
            const uint32_t n = (Fsize - Fposition) < BUFFERSIZE ? (Fsize - Fposition) : BUFFERSIZE;
            StoreBuffer(Fbuffer, n); // Store it in ram for now rather than disk it (only what is the file's: no padding)
            Fposition += n;
            ++Stored;
            p = ((float)Fposition / (float)Fsize) * 100;
            SendValue(Progress, p);
            strcpy(msg, Received);
            strcat(msg, Str(nb1, Fposition, 0));
            strcat(msg, of);
            strcat(msg, Str(nb1, Fsize, 0));
            ShowFileProgress(msg);
        }
        else if (millis() - RXTimer > FILEDATATIMEOUT)
        { // the sender has gone quiet (it gave up, or went out of range): say so, rather than wait for ever
            ReceiveAbandoned("Transfer failed", true);
            return;
        }
    }
    if (Protocol >= 1 && FileCrc16(NewFileBuffer, Fsize) != FileCrc)
    { // B27 sender: the whole file, checked before anything is written
        ReceiveAbandoned("Transfer error: bad file", true);
        return;
    }
    SendValue(Progress, 100);

    // To the card under a scratch name first; the old file of this name stays until the new one has read back as a model
    strcpy(FinalName, SingleModelFile);
    strcpy(SingleModelFile, FILESCRATCH);
    AddPath(SingleModelFile);
    if (SD.exists(SearchFile))
        SD.remove(SearchFile);
    WriteEntireBuffer();
    SingleModelFlag = true;
    const bool good = ReadOneModel(1);
    SingleModelFlag = false;
    CloseModelsFile();
    if (!good)
    {   // ClaudeFix-2-7-2026 the imported file failed its checksum -- do NOT persist it over the
        // current model (the old code ignored this and SaveAllParameters'd it). B27: the old file is untouched.
        AddPath(SingleModelFile);
        SD.remove(SearchFile);
        strcpy(SingleModelFile, FinalName);
        ReadOneModel(ModelNumber); // (the model that was in memory, back from the card: the bad file's reading left its mark)
        CloseModelsFile();
        ReceiveAbandoned("Bad model - not saved", true);
        return;
    }
    {
        char scratch[60];
        AddPath(SingleModelFile); // (still the scratch name)
        strcpy(scratch, SearchFile);
        strcpy(SingleModelFile, FinalName);
        AddPath(SingleModelFile);
        if (SD.exists(SearchFile))
            SD.remove(SearchFile);
        if (!SD.rename(scratch, SearchFile))
        {
            ReadOneModel(ModelNumber); // (the model that was in memory, back from the card)
            CloseModelsFile();
            ReceiveAbandoned("Card error - not saved", true);
            return;
        }
    }
    BuildDirectory();
    SendText(ModelsView_filename, Success);
    DelayWithDog(500);
    SendText(ModelsView_filename, SingleModelFile);

    // Below Here the new model is imported for immediate use (ReadOneModel above has it in memory)

    if (SavedSticksMode != SticksMode)
    { // swap over trims (elevator -  Throttle)
        for (int ba = 1; ba < 5; ++ba)
        {
            uint8_t temp = Trims[ba][1];
            Trims[ba][1] = Trims[ba][2];
            Trims[ba][2] = temp;
        }
    }
    CloseModelsFile();
    SaveAllParameters();
    CloseModelsFile();
    NormaliseTheRadio();
    SendCommand(ProgressEnd);
    strcpy(msg, Received);
    strcat(msg, Str(nb1, Fsize, 0));
    strcat(msg, bytes);
    ShowFileProgress(msg);
    ClearText();
    PlaySound(BEEPCOMPLETE);
    CloseModelsFile();
    DelayWithDog(2000);
    SaveTransmitterParameters();
    GotoModelsView();
    ClearText();
    RedLedOn();
    BoundFlag = true; // This just prevents jump to front screen (Cleared on leaving models area)
    ConfigureRadio();
    if (BuddyPupilOnWireless)
    {
        StartBuddyListen();
        BoundFlag = false;
    }
}
// ***********************************************************************************************************

#endif