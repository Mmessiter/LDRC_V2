// LockDownRadioControl — RXV2  ::  FlightLog.h
//
// Persist completed flights to LittleFS so the Black box graph + link stats
// survive a reboot and can be compared flight-to-flight. The live flight lives
// in the RAM ring (teleRing / linkStats). When a flight ends (transmitter gone
// for a while), we write it to flash as /flt0.bin and rotate the previous two
// down to /flt1.bin, /flt2.bin — keeping the last 3 flights. No real-time clock
// on the receiver, so flights are ordered most-recent-first, labelled by their
// duration, not a wall-clock date.
//
//*********************************************************************

#ifndef _SRC_FLIGHTLOG_H
#define _SRC_FLIGHTLOG_H

#include "1Defs.h"

// FLIGHT_SAVE_AFTER_MS lives in 1Defs.h — Radio.h shares it as its new-flight
// reset threshold, so the save boundary and the reset boundary can never drift.
constexpr uint16_t FLIGHT_MIN_SAMPLES   = 10;     // don't bother saving a trivial run
constexpr uint8_t  FLIGHT_KEEP          = 3;      // /flt0..2.bin

struct __attribute__((packed)) FlightHeader {
    uint32_t magic;        // 'FLT1'
    uint16_t count;        // samples
    uint16_t intervalS;    // seconds per sample
    uint32_t connMs;       // flight duration (ms)
    uint32_t packets;      // RF packets
    uint32_t maxGapUs;     // longest inter-packet gap
    uint32_t avgGapUs;     // average gap
    uint32_t hist[6];      // gap histogram
    // FLT2 additions (Malcolm 2026-07-23): dual/triple-transceiver failover
    // figures for THIS flight — how many swaps, and active ms on each slot.
    uint32_t radioSwaps;
    uint32_t radioMs[3];
    // FLT3 addition (Malcolm 2026-07-23): WHEN the longest gap happened,
    // as ms since the connection was established (0 = unknown).
    uint32_t maxGapAtOffsetMs;
};
constexpr uint32_t FLIGHT_MAGIC      = 0x33544C46;   // "FLT3"
constexpr uint32_t FLIGHT_MAGIC_FLT2 = 0x32544C46;   // previous: no gap-position field

// A static scratch buffer for a flight loaded from flash (avoids a huge stack
// frame; ~8 kB, only used while serving a saved flight).
inline TeleSample flightLoadBuf[TELE_RING];

inline const char* flightPath(uint8_t idx) {
    static const char* names[FLIGHT_KEEP] = { "/flt0.bin", "/flt1.bin", "/flt2.bin" };
    return (idx < FLIGHT_KEEP) ? names[idx] : names[FLIGHT_KEEP - 1];
}

//*********************************************************************
//  Save the current RAM flight to flash
//*********************************************************************
// rotate = true  : a NEW flight — shuffle flt0→flt1→flt2 and write flt0.
// rotate = false : an UPDATE of the current session (e.g. a second take-off
//                  after landing to inspect) — overwrite flt0 in place, so a
//                  single battery with several arm/disarm cycles stays ONE
//                  saved flight instead of cluttering the history with partials.
inline void saveFlightToLittleFS(bool rotate = true) {
    if (!littleFsMounted || teleCount < FLIGHT_MIN_SAMPLES) return;
    // Write the NEW flight to a temp file FIRST — only a successful write may
    // rotate the old ones. (Rotating first meant a failed open/write — e.g.
    // FS full — deleted the oldest saved flight and left no new one.)
    File f = LittleFS.open("/flt.tmp", "w");
    if (!f) return;
    FlightHeader h{};
    h.magic     = FLIGHT_MAGIC;
    h.count     = teleCount;
    h.intervalS = 1;
    h.connMs    = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
    h.packets   = linkStats.packets;
    { uint32_t tMax, tAvg, tHist[6], tAt;             // packed fields can't bind by ref
      gapsForDisplay(tMax, tAvg, tHist, tAt);         // shutdown artifact excluded
      h.maxGapUs = tMax; h.avgGapUs = tAvg;
      h.maxGapAtOffsetMs = (tAt > linkStats.connStartMs) ? (tAt - linkStats.connStartMs) : 0;
      for (uint8_t i = 0; i < 6; ++i) h.hist[i] = tHist[i]; }
    h.radioSwaps = radioSwaps - linkStats.swapsAtStart;
    for (uint8_t i = 0; i < 3; ++i) h.radioMs[i] = linkStats.radioMsAtLive[i] - linkStats.radioMsAtStart[i];
    f.write((const uint8_t*)&h, sizeof(h));
    const uint16_t start = (teleCount < TELE_RING) ? 0 : teleHead;
    size_t wrote = 0;
    for (uint16_t i = 0; i < teleCount; ++i) {
        TeleSample s = teleRing[(start + i) % TELE_RING];
        wrote += f.write((const uint8_t*)&s, sizeof(s));
    }
    f.close();
    if (wrote != (size_t)teleCount * sizeof(TeleSample)) {   // short write (FS full) — keep the old flights
        LittleFS.remove("/flt.tmp");
        events.add("Flight save FAILED (flash full?)");
        return;
    }
    // Success — commit. A new flight shuffles the history down; an update of the
    // current session just replaces flt0 (no rotation), keeping one slot per flight.
    if (rotate) {
        LittleFS.remove(flightPath(FLIGHT_KEEP - 1));
        for (int8_t i = FLIGHT_KEEP - 2; i >= 0; --i) {
            if (LittleFS.exists(flightPath(i))) LittleFS.rename(flightPath(i), flightPath(i + 1));
        }
    } else {
        LittleFS.remove(flightPath(0));   // overwrite the current session's slot only
    }
    LittleFS.rename("/flt.tmp", flightPath(0));
    events.add(rotate ? "Flight saved to flash" : "Flight updated (same session)");
}

//*********************************************************************
//  Flight-end detector — call from loop()
//*********************************************************************
inline void maybeSaveFlight() {
    static uint32_t armedConnStart = 0;   // the connStart of a flight awaiting save
    const uint32_t now = millis();
    const bool connected = (rx.lastMillis != 0) && ((uint32_t)(now - rx.lastMillis) < 3000);
    if (connected) {
        armedConnStart = linkStats.connStartMs;   // a flight is running; arm it
        return;
    }
    if (armedConnStart != 0 && armedConnStart == linkStats.connStartMs &&
        rx.lastMillis != 0 && (uint32_t)(now - rx.lastMillis) > FLIGHT_SAVE_AFTER_MS) {
        saveFlightToLittleFS();
        armedConnStart = 0;                        // saved; re-arms on the next connection
    }
}

//*********************************************************************
//  ARM-BASED SAVE  (Malcolm's idea, 2026-07-03) — call from loop()
//*********************************************************************
// The safest possible trigger: write the flight to flash the moment the model
// is DISARMED after a real flight. Disarming happens after landing while the
// RX is still very much powered on, so the save runs SAFELY ON THE GROUND —
// zero flash writes while airborne (a flash write stalls loop(), which must
// never happen mid-flight). It also solves the RX-off-first problem: you
// disarm, the flight is saved, THEN you switch off.
//
// "Armed" = the user's arming channel (armingChannel, 1..16; set on the View-
// channels page) sitting above mid-stick. A >= 30 s armed spell marks a real
// flight, so a spool-up test / aborted start isn't saved. If armingChannel is
// 0 (unset) we fall back to the old link-loss save so nothing regresses.
constexpr uint32_t FLIGHT_ARMED_MIN_MS = 30000;   // armed at least this long = a real flight

inline void flightSaveTick() {
    if (armingChannel < 1 || armingChannel > 16) {   // feature off → keep the old behaviour
        maybeSaveFlight();
        return;
    }
    static bool     wasArmed        = false;
    static uint32_t armedSince      = 0;
    static bool     sessionWorth    = false;         // has this session had a real (>=30 s) flight?
    static bool     sessionSaved    = false;         // has this session been written to flt0 yet?
    static bool     sessionEverArmed = false;        // any arm edge at all this session?
    static uint32_t sessionConnStart = 0xFFFFFFFF;
    const uint32_t now = millis();

    // A NEW session = a new connection (>= 15 s link gap, i.e. a new battery /
    // power-cycle). One session is ONE saved flight, however many times you
    // arm/disarm within it (e.g. landing to inspect, then flying again).
    if (linkStats.connStartMs != sessionConnStart) {
        sessionConnStart = linkStats.connStartMs;
        sessionWorth = false;
        sessionSaved = false;
        sessionEverArmed = false;
    }

    // Armed only counts while the link is actually live — a lost link freezes
    // channelMicros at its last value, which must not read as "still armed".
    const bool linkLive = (rx.lastMillis != 0) && ((uint32_t)(now - rx.lastMillis) < 2000);
    const bool armed    = linkLive && (channelMicros[armingChannel - 1] > 1500);

    if (armed && !wasArmed) { armedSince = now; sessionEverArmed = true; }      // arm edge
    if (armed && (uint32_t)(now - armedSince) >= FLIGHT_ARMED_MIN_MS) sessionWorth = true;
    if (!armed && wasArmed && sessionWorth) {                                   // DISARM edge in a real flight
        saveFlightToLittleFS(!sessionSaved);   // first disarm of the session rotates a new slot; later disarms overwrite it
        sessionSaved = true;                   // (the RAM ring spans the whole session, so each save holds everything so far)
    }
    wasArmed = armed;

    // A session where the arm switch was NEVER touched (bench run, simulated
    // flight, arming channel misconfigured) would otherwise never save at all
    // — Malcolm lost a simulated flight exactly this way. Fall back to the
    // link-dead save for those. Armed-but-short sessions (aborted spool-ups)
    // stay excluded: they had an arm edge, so the strict rule still applies.
    if (!sessionEverArmed && !sessionSaved) maybeSaveFlight();
}

//*********************************************************************
//  JSON rendering (shared by the current RAM flight and saved flights)
//*********************************************************************
inline void renderFlightJson(String& j, const FlightHeader& h, const TeleSample* s) {
    char b[96];
    // ~28 bytes/sample worst case across the four arrays (esc 4 + head 6 +
    // v 6 + amps 7 + commas). Under-reserving forced several ~30 kB reallocs
    // per render; a failed realloc on a fragmented heap silently truncates
    // the JSON (Arduino String concat has no error path).
    j.reserve((size_t)h.count * 28 + 300);
    snprintf(b, sizeof(b), "{\"count\":%u,\"interval_s\":%u", (unsigned)h.count, (unsigned)h.intervalS); j += b;
    snprintf(b, sizeof(b), ",\"dur_ms\":%u", (unsigned)h.connMs); j += b;
    j += ",\"link\":{";
    snprintf(b, sizeof(b), "\"packets\":%u", (unsigned)h.packets); j += b;
    snprintf(b, sizeof(b), ",\"max_gap_ms\":%.1f", h.maxGapUs / 1000.0f); j += b;
    snprintf(b, sizeof(b), ",\"max_gap_at_ms\":%u", (unsigned)h.maxGapAtOffsetMs); j += b;
    snprintf(b, sizeof(b), ",\"avg_gap_ms\":%.2f", h.avgGapUs / 1000.0f); j += b;
    snprintf(b, sizeof(b), ",\"conn_ms\":%u", (unsigned)h.connMs); j += b;
    snprintf(b, sizeof(b), ",\"hist\":[%u,%u,%u,%u,%u,%u]",
             (unsigned)h.hist[0], (unsigned)h.hist[1], (unsigned)h.hist[2],
             (unsigned)h.hist[3], (unsigned)h.hist[4], (unsigned)h.hist[5]); j += b;
    snprintf(b, sizeof(b), ",\"swaps\":%u,\"radio_ms\":[%u,%u,%u]}",
             (unsigned)h.radioSwaps,
             (unsigned)h.radioMs[0], (unsigned)h.radioMs[1], (unsigned)h.radioMs[2]); j += b;
    j += ",\"esc\":[";  for (uint16_t i = 0; i < h.count; ++i) { if (i) j += ','; j += s[i].escC; }
    j += "],\"head\":["; for (uint16_t i = 0; i < h.count; ++i) { if (i) j += ','; j += s[i].headRpm; }
    j += "],\"v\":[";   for (uint16_t i = 0; i < h.count; ++i) { if (i) j += ','; snprintf(b, sizeof(b), "%.2f", s[i].cV / 100.0f); j += b; }
    j += "],\"amps\":[";for (uint16_t i = 0; i < h.count; ++i) { if (i) j += ','; snprintf(b, sizeof(b), "%.1f", s[i].dA / 10.0f); j += b; }
    j += "]}";
}

// Build the JSON for flight index f: 0 = live RAM flight, 1..FLIGHT_KEEP = saved.
// Returns false if that saved flight doesn't exist.
inline bool buildFlightJson(uint8_t f, String& j) {
    if (f == 0) {
        FlightHeader h{};
        h.magic = FLIGHT_MAGIC; h.count = teleCount; h.intervalS = 1;
        h.connMs   = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
        h.packets  = linkStats.packets;
        { uint32_t tMax, tAvg, tHist[6], tAt;         // packed fields can't bind by ref
          gapsForDisplay(tMax, tAvg, tHist, tAt);     // trimmed once link is dead
          h.maxGapUs = tMax; h.avgGapUs = tAvg;
          h.maxGapAtOffsetMs = (tAt > linkStats.connStartMs) ? (tAt - linkStats.connStartMs) : 0;
          for (uint8_t i = 0; i < 6; ++i) h.hist[i] = tHist[i]; }
        h.radioSwaps = radioSwaps - linkStats.swapsAtStart;
        for (uint8_t i = 0; i < 3; ++i) h.radioMs[i] = linkStats.radioMsAtLive[i] - linkStats.radioMsAtStart[i];
        // copy the ring oldest→newest into the load buffer for uniform rendering
        const uint16_t start = (teleCount < TELE_RING) ? 0 : teleHead;
        for (uint16_t i = 0; i < teleCount; ++i) flightLoadBuf[i] = teleRing[(start + i) % TELE_RING];
        renderFlightJson(j, h, flightLoadBuf);
        return true;
    }
    if (!littleFsMounted || f > FLIGHT_KEEP) return false;
    File file = LittleFS.open(flightPath(f - 1), "r");
    if (!file) return false;
    FlightHeader h{};
    if (file.read((uint8_t*)&h, sizeof(h)) != (int)sizeof(h) ||
        (h.magic != FLIGHT_MAGIC && h.magic != FLIGHT_MAGIC_FLT2)) { file.close(); return false; }
    if (h.magic == FLIGHT_MAGIC_FLT2) {               // older file: header is 4 bytes shorter
        h.maxGapAtOffsetMs = 0;
        file.seek(sizeof(FlightHeader) - sizeof(uint32_t));
    }
    if (h.count > TELE_RING) h.count = TELE_RING;
    for (uint16_t i = 0; i < h.count; ++i) {
        if (file.read((uint8_t*)&flightLoadBuf[i], sizeof(TeleSample)) != (int)sizeof(TeleSample)) { h.count = i; break; }
    }
    file.close();
    renderFlightJson(j, h, flightLoadBuf);
    return true;
}

// Small listing of available flights for the selector: [{i,count,dur_ms},...]
inline void buildFlightsListJson(String& j) {
    char b[64];
    j += "[";
    snprintf(b, sizeof(b), "{\"i\":0,\"count\":%u,\"dur_ms\":%u,\"live\":true}",
             (unsigned)teleCount,
             (unsigned)((rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0));
    j += b;
    if (littleFsMounted) {
        for (uint8_t f = 1; f <= FLIGHT_KEEP; ++f) {
            File file = LittleFS.open(flightPath(f - 1), "r");
            if (!file) continue;
            FlightHeader h{};
            bool ok = (file.read((uint8_t*)&h, sizeof(h)) == (int)sizeof(h)) &&
                      (h.magic == FLIGHT_MAGIC || h.magic == FLIGHT_MAGIC_FLT2);
            file.close();
            if (!ok) continue;
            snprintf(b, sizeof(b), ",{\"i\":%u,\"count\":%u,\"dur_ms\":%u}", f, (unsigned)h.count, (unsigned)h.connMs);
            j += b;
        }
    }
    j += "]";
}

#endif // _SRC_FLIGHTLOG_H
