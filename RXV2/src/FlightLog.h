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
// 20 slots (3→8→20 on 2026-07-31): ground tests save too since 0.9.265, so
// bench wiggles rotated real flights out of a short history. ~7 kB per
// flight. Space came from shrinking flying-field.jpg (468→177 kB) — the fs
// partition is only 1.5 MB and the pages fill most of it. Across fs-OTAs
// the RAM lifeboat preserves newest-first within a heap budget; but with
// the fs_md5 skip (same release) most updates no longer touch the fs at
// all, so the full 20 normally survive untouched.
constexpr uint8_t  FLIGHT_KEEP          = 20;     // /flt0..19.bin

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
    // FLT4 addition (Malcolm 2026-07-26): wall-clock save time (unix seconds,
    // 0 = unknown). The phone supplies the clock via POST /api/time; flights
    // saved before any phone connected are patched retroactively.
    uint32_t savedEpochS;
};
constexpr uint32_t FLIGHT_MAGIC      = 0x34544C46;   // "FLT4"
constexpr uint32_t FLIGHT_MAGIC_FLT3 = 0x33544C46;   // previous: no save-time field
constexpr uint32_t FLIGHT_MAGIC_FLT2 = 0x32544C46;   // older: no gap-position field either

// Slots saved THIS power-up while the clock was still unknown, recorded as
// millis()-at-save so a later time sync can back-date them (0 = nothing owed).


// Post-mortem event persistence (Malcolm 2026-08-07: Bluetooth dead after
// landing — TWICE — and the reboot destroyed the RAM event log both times).
// The ring is copied to flash at moments that are already stall-pardoned;
// at boot the previous copy becomes /evprev.txt, served in
// /api/events.json as "prev" (and captured by the phone's session save).
//
// 0.9.551 (Goblin "little jump every minute or two at the table"): the old
// version rewrote the WHOLE ring every time — up to ~10 kB, two or three
// flash blocks erased and programmed, plus LittleFS's allocator scan on a
// full filesystem: seconds of frozen loop, no CRSF frames, a swash twitch.
// Now only the lines added since the last persist are APPENDED (usually a
// handful — one block copy), nothing at all is written when there is
// nothing new, and a full rewrite happens only when the file is missing,
// the ring has lapped the file, or the file has grown past its cap.
inline uint32_t eventsPersistedUpTo = 0;   // events.added the /evcur.txt tail reflects (0 = never)
constexpr size_t EVENTS_FILE_CAP = 24 * 1024;   // /api/events-prev.json reads the whole file into RAM

inline void eventsPersist() {
    if (!littleFsMounted) return;
    const uint32_t added = events.added;
    if (added == eventsPersistedUpTo) return;                 // nothing new — not one flash byte
    uint32_t missing = added - eventsPersistedUpTo;
    bool rewrite = eventsPersistedUpTo == 0 || missing >= EventLog::SIZE ||
                   !LittleFS.exists("/evcur.txt");
    File f;
    if (!rewrite) {
        f = LittleFS.open("/evcur.txt", "a");
        if (f && f.size() > EVENTS_FILE_CAP) { f.close(); rewrite = true; }
    }
    if (rewrite) {
        missing = events.count;                               // the whole ring
        f = LittleFS.open("/evcur.txt", "w");
    }
    if (!f) return;
    size_t start = (events.head + EventLog::SIZE - missing) % EventLog::SIZE;
    for (size_t i = 0; i < missing; ++i) {
        size_t idx = (start + i) % EventLog::SIZE;
        f.printf("%lu %s\n", (unsigned long)events.when[idx], events.msgs[idx]);
    }
    f.close();
    eventsPersistedUpTo = added;
}

// Proven-tune counter — called ONLY when a NEW flight slot is written
// (updates of the same session don't recount). Runs inside the flight
// save's already-pardoned flash window, so the NVS writes cost nothing
// extra in the logs.
inline void tuneCountFlight(bool rotated) {
    if (!rotated) return;
    if (tuneEditsPending) {
        tuneEditsPending = false;
        tuneEditGen++;
        tuneFlightsSince = 1;
        prefs.putUShort(NVS_KEY_EDIT_GEN, tuneEditGen);
    } else {
        tuneFlightsSince++;
    }
    prefs.putULong(NVS_KEY_FLT_SINCE_EDIT, tuneFlightsSince);
}

inline uint32_t fltPendingStampMs[FLIGHT_KEEP] = { 0, 0, 0 };

// A static scratch buffer for a flight loaded from flash (avoids a huge stack
// frame; ~8 kB, only used while serving a saved flight).
inline TeleSample flightLoadBuf[TELE_RING];

inline const char* flightPath(uint8_t idx) {
    static char names[FLIGHT_KEEP][12] = {};
    if (!names[0][0])
        for (uint8_t i = 0; i < FLIGHT_KEEP; ++i)
            snprintf(names[i], sizeof(names[i]), "/flt%u.bin", i);
    return names[idx < FLIGHT_KEEP ? idx : FLIGHT_KEEP - 1];
}

// RING head (2026-08-01): the physical slot holding the NEWEST flight.
// The old design renamed up to 20 files at every save — that storm stalled
// loop() long enough for the TX to declare the link lost at Malcolm's
// landing. Now a save writes exactly ONE slot and advances the head.
// Loaded from NVS at boot (legacy rotation layouts are migrated there too).
inline uint8_t fltHead = 0;
// logical index (0 = newest saved flight) -> physical slot number
inline uint8_t fltPhys(uint8_t logical) {
    return (uint8_t)((fltHead + FLIGHT_KEEP - (logical % FLIGHT_KEEP)) % FLIGHT_KEEP);
}

//*********************************************************************
//  Save the current RAM flight to flash
//*********************************************************************
// rotate = true  : a NEW flight — shuffle flt0→flt1→flt2 and write flt0.
// rotate = false : an UPDATE of the current session (e.g. a second take-off
//                  after landing to inspect) — overwrite flt0 in place, so a
//                  single battery with several arm/disarm cycles stays ONE
//                  saved flight instead of cluttering the history with partials.
// Synchronous writer — used ONLY where a stall cannot matter (the battery
// guardian, immediately before deep sleep). Normal saves go through the
// ASYNC writer below (Malcolm's 10 ms doctrine, 2026-08-01: any operation
// longer than ~10 ms must be certain the flight is over — so ordinary saves
// never do anything long at all).
inline void saveFlightToLittleFS(bool rotate = true) {
    if (!littleFsMounted || teleCount < FLIGHT_MIN_SAMPLES) return;
    // Flash writes + up to 20 rotation renames stall the loop (~1 s): tell
    // the link statistics to look away — this is ground housekeeping, not
    // link quality (an 808 ms 'gap' was billed exactly at disarm).
    statsSelfStallUntilMs = millis() + 5000;
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
    h.radioSwaps = linkStats.flightSwaps;
    for (uint8_t i = 0; i < 3; ++i) h.radioMs[i] = linkStats.radioMsAtLive[i] - linkStats.radioMsAtStart[i];
    h.savedEpochS = epochNowS();          // 0 until a phone has told us the time
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
    // Success — commit to ONE ring slot (no rename storm). A new flight
    // advances the head; a same-session update overwrites the head slot.
    const uint8_t target = rotate ? (uint8_t)((fltHead + 1) % FLIGHT_KEEP) : fltHead;
    LittleFS.remove(flightPath(target));
    LittleFS.rename("/flt.tmp", flightPath(target));
    if (rotate) { fltHead = target; prefs.putUChar(NVS_KEY_FLT_HEAD, fltHead); }
    fltPendingStampMs[target] = h.savedEpochS ? 0 : millis();   // slots are stable: no shifting
    tuneCountFlight(rotate);
    eventsPersist();
    events.add(rotate ? "Flight saved to flash" : "Flight updated (same session)");
}

//*********************************************************************
//  ASYNC flight writer — spreads the save across loop() passes
//*********************************************************************
// The one-shot save stalled loop() long enough for the TX to notice (a
// ~250 ms ack gap at the end of Malcolm's third August flight — his TX
// logged it, ours politely didn't). Here the samples are captured into a
// private buffer in microseconds, then written ~64 samples per loop pass:
// no single pass exceeds a flash-block erase (~10-30 ms), invisible to
// both ends of the link.
inline TeleSample   svBuf[TELE_RING];
inline FlightHeader svHdr;
inline File         svFile;
inline uint8_t      svState   = 0;        // 0 idle, 1 writing, 2 commit
inline uint16_t     svWritten = 0;
inline bool         svRotate  = true;
inline bool         svOk      = true;

// Ack item 38: "pardon the next N ms" — sent a couple of dozen times before
// the save's file operations so the TX can exclude the flash-erase stall from
// its gap statistics (Malcolm 2026-08-03: the only >100 ms gap in his log was
// the save, right after motor-off — honest, but it polluted the averages).
inline uint32_t svAnnounceStartMs = 0;

inline void startFlightSaveAsync(bool rotate) {
    if (svState) return;                                 // one save at a time
    if (!littleFsMounted || teleCount < FLIGHT_MIN_SAMPLES) return;
    statsSelfStallUntilMs = millis() + 2000;
    svHdr = FlightHeader{};
    svHdr.magic     = FLIGHT_MAGIC;
    svHdr.count     = teleCount;
    svHdr.intervalS = 1;
    svHdr.connMs    = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
    svHdr.packets   = linkStats.packets;
    { uint32_t tMax, tAvg, tHist[6], tAt;
      gapsForDisplay(tMax, tAvg, tHist, tAt);
      svHdr.maxGapUs = tMax; svHdr.avgGapUs = tAvg;
      svHdr.maxGapAtOffsetMs = (tAt > linkStats.connStartMs) ? (tAt - linkStats.connStartMs) : 0;
      for (uint8_t i = 0; i < 6; ++i) svHdr.hist[i] = tHist[i]; }
    svHdr.radioSwaps = linkStats.flightSwaps;
    for (uint8_t i = 0; i < 3; ++i) svHdr.radioMs[i] = linkStats.radioMsAtLive[i] - linkStats.radioMsAtStart[i];
    svHdr.savedEpochS = epochNowS();
    // Snapshot the ring NOW (a ~7 kB memcpy, microseconds) so sampling can
    // continue while the write trickles out.
    const uint16_t start = (teleCount < TELE_RING) ? 0 : teleHead;
    for (uint16_t i = 0; i < svHdr.count; ++i) svBuf[i] = teleRing[(start + i) % TELE_RING];
    svWritten = 0; svRotate = rotate;
    // ANNOUNCE first (svState 3): the tmp-file open below can trigger a flash
    // erase — the very stall we are pardoning — so the pardon must be on the
    // TX's side of the air before any file work begins.
    fltPardonMsToSend = FLT_PARDON_MS;
    fltPardonAnnounceLeft = 25;                          // ~50 ms of acks at 500 Hz
    svAnnounceStartMs = millis();
    svState = 3;
}

// Announce complete (or timed out — TX off means nobody consumes acks):
// open the file and write the header, then hand over to the chunked writer.
inline void flightSaveAsyncBeginFile() {
    svFile = LittleFS.open("/flt.tmp", "w");
    if (!svFile) { svState = 0; return; }
    svOk = svFile.write((const uint8_t*)&svHdr, sizeof(svHdr)) == sizeof(svHdr);
    svState = 1;
}

inline void flightSaveAsyncTick() {
    if (!svState) return;
    statsSelfStallUntilMs = millis() + 2000;             // stats look away until done
    if (svState == 3) {                                  // pardon-announce phase
        if (fltPardonAnnounceLeft == 0 ||
            (uint32_t)(millis() - svAnnounceStartMs) > 500) {
            fltPardonAnnounceLeft = 0;
            flightSaveAsyncBeginFile();
        }
        return;
    }
    if (svState == 1) {
        uint16_t n = svHdr.count - svWritten; if (n > 64) n = 64;
        if (n && svOk) {
            size_t want = (size_t)n * sizeof(TeleSample);
            if (svFile.write((const uint8_t*)&svBuf[svWritten], want) != want) svOk = false;
            svWritten += n;
        }
        if (!svOk || svWritten >= svHdr.count) { svFile.close(); svState = 2; }
        return;                                          // one chunk per pass
    }
    if (!svOk) {
        LittleFS.remove("/flt.tmp");
        events.add("Flight save FAILED (flash full?)");
        svState = 0;
        // Save finished — send Malcolm's explicit "unignore" (item 38, value
        // 0) so the TX's pardon ends NOW rather than at the 3 s safety ceiling.
        fltPardonMsToSend = 0;
        fltPardonAnnounceLeft = 10;
        return;
    }
    const uint8_t target = svRotate ? (uint8_t)((fltHead + 1) % FLIGHT_KEEP) : fltHead;
    LittleFS.remove(flightPath(target));
    LittleFS.rename("/flt.tmp", flightPath(target));
    if (svRotate) { fltHead = target; prefs.putUChar(NVS_KEY_FLT_HEAD, fltHead); }
    fltPendingStampMs[target] = svHdr.savedEpochS ? 0 : millis();
    tuneCountFlight(svRotate);
    eventsPersist();
    events.add(svRotate ? "Flight saved to flash" : "Flight updated (same session)");
    svState = 0;
}

//*********************************************************************
//  Retro-date flights once the phone tells us the time
//*********************************************************************
// Flights usually save 15 s after the TX goes quiet — BEFORE the pilot opens
// the app. When the first time sync of this power-up arrives, patch the wall
// clock into any file saved earlier in the session.
inline void patchFlightEpochs() {
    if (!epochOffsetMs || !littleFsMounted) return;
    for (uint8_t i = 0; i < FLIGHT_KEEP; ++i) {
        if (!fltPendingStampMs[i]) continue;
        File f = LittleFS.open(flightPath(i), "r+");
        if (f) {
            uint32_t magic = 0;
            f.read((uint8_t*)&magic, sizeof(magic));
            if (magic == FLIGHT_MAGIC) {
                const uint32_t epochS = (uint32_t)((epochOffsetMs + (int64_t)fltPendingStampMs[i]) / 1000);
                f.seek(offsetof(FlightHeader, savedEpochS));
                f.write((const uint8_t*)&epochS, sizeof(epochS));
            }
            f.close();
        }
        fltPendingStampMs[i] = 0;
    }
}

//*********************************************************************
//  Flight-end detector — call from loop()
//*********************************************************************
// Brief ground tests are not flights (Malcolm 2026-07-31): an UNARMED
// session under a minute is a wiggle-check, and saving those rotated real
// flights out of history. The arm-based save keeps its own rule (>=30 s
// ARMED) — a deliberate short armed hop still saves.
constexpr uint32_t FLIGHT_FALLBACK_MIN_MS = 60000;
// Malcolm's idea (2026-08-03): a REQUEST for the flight list is itself proof
// the pilot is on the ground looking at a phone — so it may end the save's
// quiet-moment wait immediately. Set to millis() by the /api/flights.json
// handler; treated as active for 5 s (auto-expires, nothing to clear).
inline uint32_t fltSaveAsapMs = 0;
inline bool fltSaveAsapActive() {
    return fltSaveAsapMs && (uint32_t)(millis() - fltSaveAsapMs) < 5000;
}
// Lifted out of flightSaveTick so the flights-list JSON can say "saving".
inline bool fltSavePending = false;
inline bool fltSessionSaved = false;


inline void maybeSaveFlight() {
    static uint32_t armedConnStart = 0;   // the connStart of a flight awaiting save
    const uint32_t now = millis();
    const bool connected = (rx.lastMillis != 0) && ((uint32_t)(now - rx.lastMillis) < 3000);
    if (connected) {
        armedConnStart = linkStats.connStartMs;   // a flight is running; arm it
        return;
    }
    const uint32_t waitMs = fltSaveAsapActive() ? 3000 : FLIGHT_SAVE_AFTER_MS;
    if (armedConnStart != 0 && armedConnStart == linkStats.connStartMs &&
        rx.lastMillis != 0 && (uint32_t)(now - rx.lastMillis) > waitMs) {
        const uint32_t durMs = (rx.lastMillis > linkStats.connStartMs)
                               ? rx.lastMillis - linkStats.connStartMs : 0;
        if (durMs >= FLIGHT_FALLBACK_MIN_MS) startFlightSaveAsync(true);
        armedConnStart = 0;                        // handled; re-arms on the next connection
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
    static bool     sessionEverArmed = false;        // any arm edge at all this session?
    static uint32_t sessionConnStart = 0xFFFFFFFF;
    const uint32_t now = millis();

    // A NEW session = a new connection (>= 15 s link gap, i.e. a new battery /
    // power-cycle). One session is ONE saved flight, however many times you
    // arm/disarm within it (e.g. landing to inspect, then flying again).
    if (linkStats.connStartMs != sessionConnStart) {
        sessionConnStart = linkStats.connStartMs;
        sessionWorth = false;
        fltSessionSaved = false;
        sessionEverArmed = false;
        fltSavePending = false;
    }

    // Armed only counts while the link is actually live — a lost link freezes
    // channelMicros at its last value, which must not read as "still armed".
    const bool linkLive = (rx.lastMillis != 0) && ((uint32_t)(now - rx.lastMillis) < 2000);
    const bool armed    = linkLive && (channelMicros[armingChannel - 1] > 1500);

    if (armed && !wasArmed) { armedSince = now; sessionEverArmed = true; }      // arm edge
    if (armed && (uint32_t)(now - armedSince) >= FLIGHT_ARMED_MIN_MS) sessionWorth = true;
    if (!armed && wasArmed && sessionWorth) fltSavePending = true;                 // DISARM edge in a real flight
    wasArmed = armed;

    // The WRITE waits for a provably-quiet moment (Malcolm 2026-08-01: the
    // disarm-edge save stalled the loop long enough that his TX announced a
    // reconnect right after landing — and if the arming switch doubles as
    // motor-hold, an AUTOROTATION could have fired that stall MID-AIR).
    // Quiet = disarmed AND sticks still for 2 s (a pilot flying is never
    // hands-still), or the TX is off. First save of the session advances the
    // ring; later saves overwrite the same slot (one flight per battery).
    if (fltSavePending && !armed) {
        const bool sticksStill = lastChMoveMs && (uint32_t)(now - lastChMoveMs) >= 2000;
        const bool linkDead    = rx.lastMillis && (uint32_t)(now - rx.lastMillis) > 3000;
        if (sticksStill || linkDead || fltSaveAsapActive()) {   // a data request ends the wait
            startFlightSaveAsync(!fltSessionSaved);
            fltSessionSaved = true;            // (the RAM ring spans the whole session, so each save holds everything so far)
            fltSavePending  = false;
        }
    }

    // A session where the arm switch was NEVER touched (bench run, simulated
    // flight, arming channel misconfigured) would otherwise never save at all
    // — Malcolm lost a simulated flight exactly this way. Fall back to the
    // link-dead save for those. Armed-but-short sessions (aborted spool-ups)
    // stay excluded: they had an arm edge, so the strict rule still applies.
    if (!sessionEverArmed && !fltSessionSaved) maybeSaveFlight();
}

//*********************************************************************
//  JSON rendering (shared by the current RAM flight and saved flights)
//*********************************************************************
// paramOps: Rotorflight edits via the TX this session (live flight only) —
// the page shows a friendly note so tuning-session gaps don't alarm anyone.
inline void renderFlightJson(String& j, const FlightHeader& h, const TeleSample* s, uint32_t paramOps = 0) {
    char b[96];
    // ~28 bytes/sample worst case across the four arrays (esc 4 + head 6 +
    // v 6 + amps 7 + commas). Under-reserving forced several ~30 kB reallocs
    // per render; a failed realloc on a fragmented heap silently truncates
    // the JSON (Arduino String concat has no error path).
    j.reserve((size_t)h.count * 28 + 300);
    snprintf(b, sizeof(b), "{\"count\":%u,\"interval_s\":%u", (unsigned)h.count, (unsigned)h.intervalS); j += b;
    snprintf(b, sizeof(b), ",\"dur_ms\":%u", (unsigned)h.connMs); j += b;
    snprintf(b, sizeof(b), ",\"saved_at\":%u", (unsigned)h.savedEpochS); j += b;
    j += ",\"link\":{";
    snprintf(b, sizeof(b), "\"packets\":%u", (unsigned)h.packets); j += b;
    snprintf(b, sizeof(b), ",\"max_gap_ms\":%.1f", h.maxGapUs / 1000.0f); j += b;
    snprintf(b, sizeof(b), ",\"max_gap_at_ms\":%u", (unsigned)h.maxGapAtOffsetMs); j += b;
    snprintf(b, sizeof(b), ",\"avg_gap_ms\":%.2f", h.avgGapUs / 1000.0f); j += b;
    snprintf(b, sizeof(b), ",\"conn_ms\":%u", (unsigned)h.connMs); j += b;
    snprintf(b, sizeof(b), ",\"hist\":[%u,%u,%u,%u,%u,%u]",
             (unsigned)h.hist[0], (unsigned)h.hist[1], (unsigned)h.hist[2],
             (unsigned)h.hist[3], (unsigned)h.hist[4], (unsigned)h.hist[5]); j += b;
    snprintf(b, sizeof(b), ",\"swaps\":%u,\"radio_ms\":[%u,%u,%u]",
             (unsigned)h.radioSwaps,
             (unsigned)h.radioMs[0], (unsigned)h.radioMs[1], (unsigned)h.radioMs[2]); j += b;
    snprintf(b, sizeof(b), ",\"param_ops\":%u}", (unsigned)paramOps); j += b;
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
        h.savedEpochS = epochNowS();   // "now" — lets the page show the live flight's start time
        h.connMs   = (rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0;
        h.packets  = linkStats.packets;
        { uint32_t tMax, tAvg, tHist[6], tAt;         // packed fields can't bind by ref
          gapsForDisplay(tMax, tAvg, tHist, tAt);     // trimmed once link is dead
          h.maxGapUs = tMax; h.avgGapUs = tAvg;
          h.maxGapAtOffsetMs = (tAt > linkStats.connStartMs) ? (tAt - linkStats.connStartMs) : 0;
          for (uint8_t i = 0; i < 6; ++i) h.hist[i] = tHist[i]; }
        h.radioSwaps = linkStats.flightSwaps;
        for (uint8_t i = 0; i < 3; ++i) h.radioMs[i] = linkStats.radioMsAtLive[i] - linkStats.radioMsAtStart[i];
        // copy the ring oldest→newest into the load buffer for uniform rendering
        const uint16_t start = (teleCount < TELE_RING) ? 0 : teleHead;
        for (uint16_t i = 0; i < teleCount; ++i) flightLoadBuf[i] = teleRing[(start + i) % TELE_RING];
        renderFlightJson(j, h, flightLoadBuf, linkStats.paramOps);
        return true;
    }
    if (!littleFsMounted || f > FLIGHT_KEEP) return false;
    File file = LittleFS.open(flightPath(fltPhys(f - 1)), "r");
    if (!file) return false;
    FlightHeader h{};
    if (file.read((uint8_t*)&h, sizeof(h)) != (int)sizeof(h) ||
        (h.magic != FLIGHT_MAGIC && h.magic != FLIGHT_MAGIC_FLT3 && h.magic != FLIGHT_MAGIC_FLT2)) { file.close(); return false; }
    if (h.magic == FLIGHT_MAGIC_FLT3) {               // older file: no save-time field
        h.savedEpochS = 0;
        file.seek(sizeof(FlightHeader) - sizeof(uint32_t));
    } else if (h.magic == FLIGHT_MAGIC_FLT2) {        // older still: no gap-position either
        h.savedEpochS = 0;
        h.maxGapAtOffsetMs = 0;
        file.seek(sizeof(FlightHeader) - 2 * sizeof(uint32_t));
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
    // 128, not 64: a dated entry is ~68 chars ({"i","count","dur_ms",
    // 10-digit "saved_at","phys"}) — at 64 the JSON truncated mid-field and
    // the whole list became unparseable (2026-08-04: "all the flights are
    // gone" — they weren't; only this list was broken).
    char b[128];
    j += "[";
    snprintf(b, sizeof(b), "{\"i\":0,\"count\":%u,\"dur_ms\":%u,\"live\":true,\"saving\":%s}",
             (unsigned)teleCount,
             (unsigned)((rx.lastMillis > linkStats.connStartMs) ? (rx.lastMillis - linkStats.connStartMs) : 0),
             (fltSavePending || svState) ? "true" : "false");
    j += b;
    if (littleFsMounted) {
        for (uint8_t f = 1; f <= FLIGHT_KEEP; ++f) {
            File file = LittleFS.open(flightPath(fltPhys(f - 1)), "r");
            if (!file) continue;
            FlightHeader h{};
            bool ok = (file.read((uint8_t*)&h, sizeof(h)) == (int)sizeof(h)) &&
                      (h.magic == FLIGHT_MAGIC || h.magic == FLIGHT_MAGIC_FLT3 || h.magic == FLIGHT_MAGIC_FLT2);
            file.close();
            if (!ok) continue;
            if (h.magic != FLIGHT_MAGIC) h.savedEpochS = 0;   // shorter header: that field read sample bytes
            snprintf(b, sizeof(b), ",{\"i\":%u,\"count\":%u,\"dur_ms\":%u,\"saved_at\":%u,\"phys\":%u}",
                     f, (unsigned)h.count, (unsigned)h.connMs, (unsigned)h.savedEpochS,
                     (unsigned)fltPhys(f - 1));
            j += b;
        }
    }
    j += "]";
}

#endif // _SRC_FLIGHTLOG_H
