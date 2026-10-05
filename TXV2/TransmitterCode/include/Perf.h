// *************************************** Perf.h *****************************************
// V1B B15: WHERE THE TIME GOES WHILE FLYING (Malcolm, 1-10-2026: "measure and keep track of those delays which might
// actually affect flying, and move them one at a time, starting with the most important ones. Those which update the
// front screen without user intervention strike me as important because they occur while flying.")
//
// The transmitter sends a packet every 2 ms (PACEMAKER). Whatever holds the loop for longer delays a packet. So:
//   - every gap between two packets sent while a model is connected is measured, and sorted into a histogram;
//   - a gap of 4 ms or more (a whole packet slot lost) is a LATE PACKET: it is kept (the last 24) with the job that
//     took longest by itself in that gap, and the job that called it (CrumbGuard, 1Definitions.h, times them all);
//   - every guarded job is timed: how often it ran, its longest run by itself and with the jobs inside it, and its
//     total time, all only while a model is connected.
// Nothing is written while flying. The report goes to /PERF.TXT on the card when the screen's file link opens (the
// link never opens with a model connected), and its headline is in the hello (late=, worst=, wc=, wp=).
#ifndef PERF_H
#define PERF_H

#include <Arduino.h>
#include "1Definitions.h"

static const uint32_t PerfBucketMs[] = {3, 4, 6, 10, 20, 50, 100};   // upper edges; the last bucket is 100 ms and more
#define PERF_BUCKETS 8
#define PERF_LATE_US 4000
#define PERF_KEEP 24

static uint32_t PerfGaps[PERF_BUCKETS];
static uint32_t PerfSends = 0, PerfLate = 0, PerfWorstGapUs = 0, PerfWorstAtS = 0;
static uint8_t PerfWorstGapCrumb = 0, PerfWorstGapParent = 0;
static uint32_t PerfLastSendUs = 0;
struct PerfLateOne
{
    uint32_t atS, gapUs, ownUs;
    uint8_t crumb, parent, view;
};
static PerfLateOne PerfKept[PERF_KEEP];
static uint8_t PerfKeptNext = 0, PerfKeptCount = 0;

static inline uint32_t PerfUs(uint32_t cycles) { return cycles / (F_CPU_ACTUAL / 1000000u); }

// Silent on purpose (the motor-switch rule, a receiver update): the gap that ends it is not a late packet.
void PerfSilent()
{
    PerfLastSendUs = 0;
    PerfConnected = false;
}

// Called by SendData() each time a packet is about to go (after the pace and the silences).
void PerfNoteSend()
{
    const uint32_t now = micros();
    const bool connected = BoundFlag && ModelMatched;
    if (connected && PerfConnected && PerfLastSendUs)
    {
        const uint32_t gap = now - PerfLastSendUs;
        uint8_t b = 0;
        while (b < PERF_BUCKETS - 1 && gap >= PerfBucketMs[b] * 1000u)
            ++b;
        ++PerfGaps[b];
        ++PerfSends;
        if (gap >= PERF_LATE_US)
        {
            ++PerfLate;
            PerfLateOne &k = PerfKept[PerfKeptNext];
            k.atS = millis() / 1000;
            k.gapUs = gap;
            k.ownUs = PerfUs(PerfWorstOwn);
            k.crumb = PerfWorstCrumb;
            k.parent = PerfWorstParent;
            k.view = (uint8_t)CurrentView;
            PerfKeptNext = (PerfKeptNext + 1) % PERF_KEEP;
            if (PerfKeptCount < PERF_KEEP)
                ++PerfKeptCount;
            if (gap > PerfWorstGapUs)
            {
                PerfWorstGapUs = gap;
                PerfWorstAtS = k.atS;
                PerfWorstGapCrumb = PerfWorstCrumb;
                PerfWorstGapParent = PerfWorstParent;
            }
        }
    }
    PerfConnected = connected;
    PerfLastSendUs = now;
    PerfWorstOwn = 0;
    PerfWorstCrumb = 0;
    PerfWorstParent = 0;
}

static const char *PerfCrumbName(uint8_t c)
{
    static const char *const names[CRUMB_LAST + 1] = {
        "(no job)", "loop", "file link", "question on screen", "DelayWithDog", "writing the log", "saving models",
        "TryToConnect", "TryToReconnect", "model exchange", "firmware swap", "loading models", "PlaySound",
        "GetValue (waits for the screen)", "motor-switch wait", "sending parameters", "reading the clock (I2C)",
        "CheckSDCard", "ProcessRecentCommsGap", "SendCommand (to the screen)", "ButtonWasPressed",
        "once-a-second chores", "SendData (the radio)", "receiver update", "ShowServoPos (channel bars)",
        "ShowComms (front/data page)", "CheckBatteryStates", "ReadTime (page clock)", "UpdateTrimView",
        "ShowMotorTimer", "GetFrameRate", "CheckScreenTime", "TellScreen", "ReadTheSwitchesAndTrims",
        "CheckHardwareTrims", "GetBank", "DoTheVariometer", "GetNewChannelValues (mixing)", "CheckPowerOffButton",
        "CheckMaxCurrent", "GetTextIn (reading the screen)", "GetReturnCode (draining the screen)"};
    return c <= CRUMB_LAST ? names[c] : "?";
}

// The headline, for the hello.
const char *PerfHelloText()
{
    static char t[64];
    snprintf(t, sizeof(t), "late=%lu;worst=%lu;wc=%u;wp=%u", (unsigned long)PerfLate, (unsigned long)PerfWorstGapUs,
             (unsigned)PerfWorstGapCrumb, (unsigned)PerfWorstGapParent);
    return t;
}

// The whole report into one file.
static void PerfReportTo(File &f)
{
    char line[160];
    snprintf(line, sizeof line, "LDRC transmitter timing - firmware 2.5.6 %s - up %lu s\n", TXVERSION_EXTRA, (unsigned long)(millis() / 1000));
    f.print(line);
    snprintf(line, sizeof line, "While a model was connected: %lu packets. On time = a gap under 3 ms (one every 2 ms).\n\n", (unsigned long)PerfSends);
    f.print(line);
    f.print("GAPS BETWEEN PACKETS\n");
    for (uint8_t b = 0; b < PERF_BUCKETS; ++b)
    {
        if (b == 0)
            snprintf(line, sizeof line, "  under %2lu ms     %8lu\n", (unsigned long)PerfBucketMs[0], (unsigned long)PerfGaps[0]);
        else if (b < PERF_BUCKETS - 1)
            snprintf(line, sizeof line, "  %3lu to %3lu ms   %8lu\n", (unsigned long)PerfBucketMs[b - 1], (unsigned long)PerfBucketMs[b], (unsigned long)PerfGaps[b]);
        else
            snprintf(line, sizeof line, "  %3lu ms or more  %8lu\n", (unsigned long)PerfBucketMs[b - 1], (unsigned long)PerfGaps[b]);
        f.print(line);
    }
    snprintf(line, sizeof line, "Late packets (4 ms or more): %lu. Worst: %lu.%01lu ms at %lu s, in %s, called by %s.\n\n", (unsigned long)PerfLate,
             (unsigned long)(PerfWorstGapUs / 1000), (unsigned long)((PerfWorstGapUs % 1000) / 100), (unsigned long)PerfWorstAtS,
             PerfCrumbName(PerfWorstGapCrumb), PerfCrumbName(PerfWorstGapParent));
    f.print(line);
    f.print("THE LAST LATE PACKETS (oldest first): when, the gap, the job that took longest by itself, its time, who called it, the page\n");
    for (uint8_t i = 0; i < PerfKeptCount; ++i)
    {
        const PerfLateOne &k = PerfKept[(PerfKeptNext + PERF_KEEP - PerfKeptCount + i) % PERF_KEEP];
        snprintf(line, sizeof line, "  %6lu s  %6lu us  %-34s %6lu us  < %-30s page %u\n", (unsigned long)k.atS, (unsigned long)k.gapUs,
                 PerfCrumbName(k.crumb), (unsigned long)k.ownUs, PerfCrumbName(k.parent), (unsigned)k.view);
        f.print(line);
    }
    f.print("\nTHE JOBS, longest single run first: runs, longest by itself, longest with what it calls, total by itself\n");
    uint8_t order[CRUMB_LAST + 1];
    for (uint8_t i = 0; i <= CRUMB_LAST; ++i)
        order[i] = i;
    for (uint8_t i = 0; i <= CRUMB_LAST; ++i) // (a short list: a plain sort will do)
        for (uint8_t j = i + 1; j <= CRUMB_LAST; ++j)
            if (PerfStats[order[j]].maxAll > PerfStats[order[i]].maxAll)
            {
                const uint8_t t = order[i];
                order[i] = order[j];
                order[j] = t;
            }
    for (uint8_t i = 0; i <= CRUMB_LAST; ++i)
    {
        const PerfStat &st = PerfStats[order[i]];
        if (!st.count)
            continue;
        snprintf(line, sizeof line, "  %-38s %9lu  %7lu us  %7lu us  %8lu ms\n", PerfCrumbName(order[i]), (unsigned long)st.count,
                 (unsigned long)PerfUs(st.maxOwn), (unsigned long)PerfUs(st.maxAll), (unsigned long)(st.totalOwn / (F_CPU_ACTUAL / 1000u)));
        f.print(line);
    }
    f.print("\nPages: 0 front, 1 sticks, 7 transmitter setup, 9 data, 30 GPS, 31 model setup, 39 blank (screen off), 43 gaps.\n");
}

// /PERF.TXT: when the file link opens (never with a model connected), and at power-off. (B19: at power-off too, and a
// copy kept in /PERF/ named by the date and time - B15 wrote it only when the link opened, so a transmitter switched off
// straight after flying lost the lot: Malcolm's first simulator session, 1-10-2026.) Nothing is written with no model
// connected since power-on, so the last session's report stays on the card until the next one has something to say.
void PerfWriteReport(bool keepCopy)
{
    if (!PerfSends)
        return; // no model has been connected since power-on: nothing to say
    SD.remove("/PERF.TXT");
    File f = SD.open("/PERF.TXT", FILE_WRITE);
    if (f)
    {
        PerfReportTo(f);
        f.close();
    }
    if (!keepCopy)
        return;
    if (RTC.read(tm))
        ReadTheRTC();
    if (!SD.exists("/PERF"))
        SD.mkdir("/PERF");
    char path[40];
    snprintf(path, sizeof path, "/PERF/%02u%02u%02u-%02u%02u.TXT", (unsigned)Gyear, (unsigned)Gmonth, (unsigned)GmonthDay, (unsigned)Ghour, (unsigned)Gminute);
    SD.remove(path);
    File k = SD.open(path, FILE_WRITE);
    if (k)
    {
        PerfReportTo(k);
        k.close();
    }
}

#endif
