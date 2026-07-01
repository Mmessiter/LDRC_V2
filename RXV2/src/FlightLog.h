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

constexpr uint32_t FLIGHT_SAVE_AFTER_MS = 15000;  // link gone this long → flight over → save
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
};
constexpr uint32_t FLIGHT_MAGIC = 0x31544C46;   // "FLT1"

// A static scratch buffer for a flight loaded from flash (avoids a huge stack
// frame; ~8 kB, only used while serving a saved flight).
inline TeleSample flightLoadBuf[TELE_RING];

inline const char* flightPath(uint8_t idx) {
    static const char* names[FLIGHT_KEEP] = { "/flt0.bin", "/flt1.bin", "/flt2.bin" };
    return (idx < FLIGHT_KEEP) ? names[idx] : names[FLIGHT_KEEP - 1];
}

//*********************************************************************
//  Save the current RAM flight to flash (rotating the older ones down)
//*********************************************************************
inline void saveFlightToLittleFS() {
    if (!littleFsMounted || teleCount < FLIGHT_MIN_SAMPLES) return;
    // Rotate: drop the oldest, shuffle the rest down one slot.
    LittleFS.remove(flightPath(FLIGHT_KEEP - 1));
    for (int8_t i = FLIGHT_KEEP - 2; i >= 0; --i) {
        if (LittleFS.exists(flightPath(i))) LittleFS.rename(flightPath(i), flightPath(i + 1));
    }
    File f = LittleFS.open(flightPath(0), "w");
    if (!f) return;
    FlightHeader h{};
    h.magic     = FLIGHT_MAGIC;
    h.count     = teleCount;
    h.intervalS = 1;
    h.connMs    = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
    h.packets   = linkStats.packets;
    h.maxGapUs  = linkStats.maxGapUs;
    h.avgGapUs  = linkStats.gapCount ? (uint32_t)(linkStats.gapSumUs / linkStats.gapCount) : 0;
    for (uint8_t i = 0; i < 6; ++i) h.hist[i] = linkStats.hist[i];
    f.write((const uint8_t*)&h, sizeof(h));
    const uint16_t start = (teleCount < TELE_RING) ? 0 : teleHead;
    for (uint16_t i = 0; i < teleCount; ++i) {
        TeleSample s = teleRing[(start + i) % TELE_RING];
        f.write((const uint8_t*)&s, sizeof(s));
    }
    f.close();
    events.add("Flight saved to flash");
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
//  JSON rendering (shared by the current RAM flight and saved flights)
//*********************************************************************
inline void renderFlightJson(String& j, const FlightHeader& h, const TeleSample* s) {
    char b[96];
    j.reserve((size_t)h.count * 20 + 256);
    snprintf(b, sizeof(b), "{\"count\":%u,\"interval_s\":%u", (unsigned)h.count, (unsigned)h.intervalS); j += b;
    snprintf(b, sizeof(b), ",\"dur_ms\":%u", (unsigned)h.connMs); j += b;
    j += ",\"link\":{";
    snprintf(b, sizeof(b), "\"packets\":%u", (unsigned)h.packets); j += b;
    snprintf(b, sizeof(b), ",\"max_gap_ms\":%.1f", h.maxGapUs / 1000.0f); j += b;
    snprintf(b, sizeof(b), ",\"avg_gap_ms\":%.2f", h.avgGapUs / 1000.0f); j += b;
    snprintf(b, sizeof(b), ",\"conn_ms\":%u", (unsigned)h.connMs); j += b;
    snprintf(b, sizeof(b), ",\"hist\":[%u,%u,%u,%u,%u,%u]}",
             (unsigned)h.hist[0], (unsigned)h.hist[1], (unsigned)h.hist[2],
             (unsigned)h.hist[3], (unsigned)h.hist[4], (unsigned)h.hist[5]); j += b;
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
        h.maxGapUs = linkStats.maxGapUs;
        h.avgGapUs = linkStats.gapCount ? (uint32_t)(linkStats.gapSumUs / linkStats.gapCount) : 0;
        for (uint8_t i = 0; i < 6; ++i) h.hist[i] = linkStats.hist[i];
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
    if (file.read((uint8_t*)&h, sizeof(h)) != (int)sizeof(h) || h.magic != FLIGHT_MAGIC) { file.close(); return false; }
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
            bool ok = (file.read((uint8_t*)&h, sizeof(h)) == (int)sizeof(h)) && h.magic == FLIGHT_MAGIC;
            file.close();
            if (!ok) continue;
            snprintf(b, sizeof(b), ",{\"i\":%u,\"count\":%u,\"dur_ms\":%u}", f, (unsigned)h.count, (unsigned)h.connMs);
            j += b;
        }
    }
    j += "]";
}

#endif // _SRC_FLIGHTLOG_H
