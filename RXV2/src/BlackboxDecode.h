// BlackboxDecode.h — Rotorflight 4.6 black-box log decoder + vibration analyser.
//
// Pure C++17: no Arduino, no heap of its own, so dev/bbcheck_test.sh can build
// it on the Mac and feed it synthetic logs. The receiver (BlackboxCheck.h)
// streams the flight controller's flash through it over USB, one MSP 71
// chunk at a time, and the analyser accumulates Welch spectra as it goes —
// nothing is stored, so a 10 MB flight costs no RAM beyond the two objects.
//
// Format: RXV2/BLACKBOX-FORMAT.md (from rotorflight-firmware RF-4.6.x).
#ifndef _SRC_BLACKBOXDECODE_H
#define _SRC_BLACKBOXDECODE_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include <stdio.h>

namespace BbDec {

constexpr int MAX_FIELDS = 128;
constexpr int NAME_LEN   = 20;
constexpr int MAX_SLOW   = 16;
constexpr int MAX_GPS    = 16;
constexpr int BUF_SIZE   = 4096;     // must hold the longest header line (~1.3 kB with every field on) and any frame

enum Pred : uint8_t { P_ZERO = 0, P_PREV = 1, P_LINEAR = 2, P_AVG2 = 3, P_MINTHR = 4, P_MOTOR0 = 5, P_INC = 6, P_HOME = 7, P_1500 = 8, P_VBATREF = 9, P_LASTTIME = 10, P_MINMOTOR = 11 };
enum Enc  : uint8_t { E_SVB = 0, E_UVB = 1, E_NEG14 = 3, E_TAG8_8SVB = 6, E_TAG2_3S32 = 7, E_TAG8_4S16 = 8, E_NULL = 9, E_TAG2_3SVAR = 10 };

struct Field { char name[NAME_LEN]; int8_t idx; uint8_t sgn, ipred, ienc, ppred, penc; };

struct Header {
    Field I[MAX_FIELDS]; int nI = 0;
    Field S[MAX_SLOW];   int nS = 0;    // pred/enc in ipred/ienc
    Field G[MAX_GPS];    int nG = 0;
    Field H[MAX_GPS];    int nH = 0;
    int  iInterval = 32, pInterval = 1, dataVersion = 2;
    int  looptime = 0, vbatref = 0, minthrottle = 0, minmotor = 0;
    uint32_t fieldsMask = 0;
    int  rpmPreset = -1, notchHz[2] = {0, 0};
    char firmware[40] = {0}, craft[24] = {0}, date[24] = {0};
    // indices of the fields the analyser wants (-1 = absent)
    int fTime = -1, fIter = -1, fHs = -1, fTail = -1, fMotor0 = -1;
    int fRaw[3] = {-1, -1, -1}, fGyro[3] = {-1, -1, -1};
    bool haveI = false, haveS = false;
    // In place, no temporary: `*this = Header()` put a 4.8 kB Header on the 8 kB loop-task stack.
    void clear() {
        memset(this, 0, sizeof *this);
        iInterval = 32; pInterval = 1; dataVersion = 2; rpmPreset = -1;
        fTime = fIter = fHs = fTail = fMotor0 = -1;
        for (int a = 0; a < 3; a++) { fRaw[a] = -1; fGyro[a] = -1; }
    }
};

struct Frame {
    uint32_t time = 0;               // µs
    int32_t  raw[3] = {0, 0, 0};     // gyroRAW  (deg/s)
    int32_t  gyro[3] = {0, 0, 0};    // gyroADC  (deg/s, filtered)
    int32_t  hs = 0, tail = 0, motor0 = 0;
    bool hasRaw = false, hasGyro = false, hasHs = false, hasMotor = false;
};

struct Sink {
    virtual ~Sink() {}
    virtual void onLogStart(const Header&, uint32_t offset) {}
    virtual void onFrame(const Frame&) {}
    virtual void onLogEnd(uint32_t offset, bool clean) {}
    virtual void onEvent(uint8_t id, uint32_t a, uint32_t b) {}
};

struct Stats {
    uint32_t iFrames = 0, pFrames = 0, sFrames = 0, eFrames = 0, gFrames = 0, hFrames = 0;
    uint32_t resyncs = 0, badFrames = 0, logs = 0, bytes = 0, skipped = 0, truncatedLogs = 0;
};

// ------------------------------------------------------------------ helpers
static inline int32_t signExt(uint32_t v, int bits) { const uint32_t m = 1u << (bits - 1); return (int32_t)((v ^ m) - m); }
static inline int32_t zigzag(uint32_t v) { return (int32_t)((v >> 1) ^ -(int32_t)(v & 1)); }

class Decoder {
public:
    Stats stats;
    Header hdr;

    void reset() {
        stats = Stats(); hdr.clear();
        len = 0; state = ST_SCAN; streamPos = 0; inLog = false; lastMainTime = 0;
        memset(cur, 0, sizeof cur); memset(prev1, 0, sizeof prev1); memset(prev2, 0, sizeof prev2);
        homeLat = homeLon = 0;
    }
    Decoder() { reset(); }

    // Feed n bytes from the stream (any chunking). Frames straddling a call
    // boundary are kept and finished next time.
    void feed(const uint8_t* p, size_t n, Sink& sink) {
        while (n) {
            size_t take = n; if (take > (size_t)(BUF_SIZE - len)) take = BUF_SIZE - len;
            if (take == 0) {            // buffer full and nothing parses: the stream is junk here — drop a byte and move on
                dropFront(1, sink); stats.skipped++; continue;
            }
            memcpy(buf + len, p, take); len += take; p += take; n -= take; stats.bytes += (uint32_t)take;
            parseAll(sink);
        }
    }
    // The stream is over (end of the used flash). Close an open log.
    void finish(Sink& sink) {
        // whatever is left could not be parsed; try once more allowing partial junk
        parseAll(sink);
        if (inLog) { stats.truncatedLogs++; inLog = false; sink.onLogEnd(streamPos + len, false); }
        len = 0;
    }
    uint32_t position() const { return streamPos; }   // stream offset of buf[0]

private:
    enum State : uint8_t { ST_SCAN, ST_HEADER, ST_FRAMES, ST_RESYNC };
    uint8_t  buf[BUF_SIZE]; size_t len = 0;
    State    state = ST_SCAN;
    uint32_t streamPos = 0;
    bool     inLog = false;
    int32_t  cur[MAX_FIELDS], prev1[MAX_FIELDS], prev2[MAX_FIELDS];
    uint32_t lastMainTime = 0;
    int32_t  homeLat = 0, homeLon = 0;

    struct Rd {                     // bounded reader; `short_` set when the buffer ran out
        const uint8_t* p; size_t n, i; bool short_;
        Rd(const uint8_t* p_, size_t n_) : p(p_), n(n_), i(0), short_(false) {}
        bool have(size_t k) const { return i + k <= n; }
        uint8_t u8() { if (i >= n) { short_ = true; return 0; } return p[i++]; }
        uint32_t uvb() { uint32_t v = 0; int sh = 0; for (int k = 0; k < 5; k++) { uint8_t b = u8(); if (short_) return 0; v |= (uint32_t)(b & 0x7F) << sh; if (!(b & 0x80)) break; sh += 7; } return v; }
        int32_t svb() { return zigzag(uvb()); }
        float f32() { uint32_t v = (uint32_t)u8() | ((uint32_t)u8() << 8) | ((uint32_t)u8() << 16) | ((uint32_t)u8() << 24); float f; memcpy(&f, &v, 4); return f; }
    };

    void dropFront(size_t k, Sink& sink) {
        if (k > len) k = len;
        memmove(buf, buf + k, len - k); len -= k; streamPos += (uint32_t)k;
    }

    static const char* HDR_MAGIC() { return "H Product:Blackbox"; }

    void parseAll(Sink& sink) {
        for (;;) {
            if (len == 0) return;
            int consumed = 0;
            switch (state) {
                case ST_SCAN:   consumed = scanForHeader(sink); break;
                case ST_HEADER: consumed = parseHeaderLine(sink); break;
                case ST_FRAMES: consumed = parseFrame(sink, false); break;
                case ST_RESYNC: consumed = resync(sink); break;
            }
            if (consumed == 0) return;              // need more bytes
            if (consumed < 0) {                      // bad: drop one byte, resync
                stats.badFrames++;
                if (state == ST_FRAMES) { state = ST_RESYNC; stats.resyncs++; }
                dropFront(1, sink);
                continue;
            }
            dropFront((size_t)consumed, sink);
        }
    }

    // Looking for the next log: skip anything until "H Product:Blackbox".
    int scanForHeader(Sink& sink) {
        const size_t M = strlen(HDR_MAGIC());
        if (len < M) {
            // keep a possible partial magic at the end, drop everything before it
            for (size_t i = 0; i < len; i++) if (buf[i] == 'H') { if (i) { stats.skipped += (uint32_t)i; return (int)i; } return 0; }
            stats.skipped += (uint32_t)len; return (int)len;
        }
        for (size_t i = 0; i + M <= len; i++) {
            if (buf[i] == 'H' && memcmp(buf + i, HDR_MAGIC(), M) == 0) {
                if (i) { stats.skipped += (uint32_t)i; return (int)i; }
                // magic at the front: start a log
                hdr.clear(); state = ST_HEADER; inLog = true; stats.logs++;
                memset(prev1, 0, sizeof prev1); memset(prev2, 0, sizeof prev2); lastMainTime = 0;
                sink.onLogStart(hdr, streamPos);       // "a log begins here" (haveI false); the full header follows from finishHeader (haveI true)
                return parseHeaderLine(sink);          // consume the magic line now, not at the next feed
            }
        }
        // no magic: drop all but the last M-1 bytes
        size_t keep = M - 1; size_t drop = len - keep; stats.skipped += (uint32_t)drop; return (int)drop;
    }

    // One "H name:value\n" line, or the end of the header.
    int parseHeaderLine(Sink& sink) {
        if (len < 2) return 0;
        if (!(buf[0] == 'H' && buf[1] == ' ')) {
            // header over: frames begin
            finishHeader(sink);
            state = ST_FRAMES;
            return parseFrame(sink, false);
        }
        size_t nl = 0; bool found = false;
        for (size_t i = 2; i < len; i++) if (buf[i] == '\n') { nl = i; found = true; break; }
        if (!found) { if (len >= BUF_SIZE - 1) return -1; return 0; }
        // parse in place: NUL-terminate the line, restore afterwards (no 2 kB stack copy)
        buf[nl] = 0;
        char* line = (char*)buf + 2;
        char* colon = strchr(line, ':');
        if (colon) { *colon = 0; headerLine(line, colon + 1); *colon = ':'; }
        buf[nl] = '\n';
        return (int)(nl + 1);
    }

    static void copyStr(char* dst, size_t cap, const char* src) { size_t n = strlen(src); if (n >= cap) n = cap - 1; memcpy(dst, src, n); dst[n] = 0; }

    // "Field I name" → fill fields; the value is a comma list
    static int fillList(const char* v, Field* f, int maxN, int what) {   // what: 0 name 1 signed 2 ipred 3 ienc 4 ppred 5 penc
        int n = 0; const char* s = v;
        while (*s && n < maxN) {
            const char* e = strchr(s, ','); size_t L = e ? (size_t)(e - s) : strlen(s);
            if (what == 0) {
                char nm[64]; size_t k = L < 63 ? L : 63; memcpy(nm, s, k); nm[k] = 0;
                f[n].idx = -1;
                char* br = strchr(nm, '[');
                if (br) { f[n].idx = (int8_t)atoi(br + 1); *br = 0; }
                copyStr(f[n].name, NAME_LEN, nm);
            } else {
                int val = atoi(s);
                switch (what) { case 1: f[n].sgn = (uint8_t)val; break; case 2: f[n].ipred = (uint8_t)val; break; case 3: f[n].ienc = (uint8_t)val; break; case 4: f[n].ppred = (uint8_t)val; break; case 5: f[n].penc = (uint8_t)val; break; }
            }
            n++;
            if (!e) break; s = e + 1;
        }
        return n;
    }

    void headerLine(const char* name, const char* value) {
        if (strncmp(name, "Field ", 6) == 0) {
            char fr = name[6]; const char* what = name + 8;      // "Field I name"
            Field* arr = nullptr; int maxN = 0; int* cnt = nullptr;
            if (fr == 'I') { arr = hdr.I; maxN = MAX_FIELDS; cnt = &hdr.nI; }
            else if (fr == 'P') { arr = hdr.I; maxN = MAX_FIELDS; cnt = nullptr; }
            else if (fr == 'S') { arr = hdr.S; maxN = MAX_SLOW; cnt = &hdr.nS; }
            else if (fr == 'G') { arr = hdr.G; maxN = MAX_GPS; cnt = &hdr.nG; }
            else if (fr == 'H') { arr = hdr.H; maxN = MAX_GPS; cnt = &hdr.nH; }
            if (!arr) return;
            int w = -1;
            if (strcmp(what, "name") == 0) w = 0; else if (strcmp(what, "signed") == 0) w = 1;
            else if (strcmp(what, "predictor") == 0) w = (fr == 'P') ? 4 : 2;
            else if (strcmp(what, "encoding") == 0) w = (fr == 'P') ? 5 : 3;
            if (w < 0) return;
            int n = fillList(value, arr, maxN, w);
            if (cnt && w == 0) *cnt = n;
            if (fr == 'I' && w == 0) hdr.haveI = true;
            if (fr == 'S' && w == 0) hdr.haveS = true;
            return;
        }
        if (strcmp(name, "I interval") == 0) hdr.iInterval = atoi(value);
        else if (strcmp(name, "P interval") == 0) hdr.pInterval = atoi(value);
        else if (strcmp(name, "Data version") == 0) hdr.dataVersion = atoi(value);
        else if (strcmp(name, "looptime") == 0) hdr.looptime = atoi(value);
        else if (strcmp(name, "vbatref") == 0) hdr.vbatref = atoi(value);
        else if (strcmp(name, "minthrottle") == 0) hdr.minthrottle = atoi(value);
        else if (strcmp(name, "fields_mask") == 0) hdr.fieldsMask = (uint32_t)strtoul(value, nullptr, 10);
        else if (strcmp(name, "gyro_rpm_notch_preset") == 0) hdr.rpmPreset = atoi(value);
        else if (strcmp(name, "gyro_notch_hz") == 0) { hdr.notchHz[0] = atoi(value); const char* c = strchr(value, ','); hdr.notchHz[1] = c ? atoi(c + 1) : 0; }
        else if (strcmp(name, "Firmware revision") == 0) copyStr(hdr.firmware, sizeof hdr.firmware, value);
        else if (strcmp(name, "Craft name") == 0) copyStr(hdr.craft, sizeof hdr.craft, value);
        else if (strcmp(name, "Log start datetime") == 0) copyStr(hdr.date, sizeof hdr.date, value);
    }

    void finishHeader(Sink& sink) {
        // the fields we care about
        for (int i = 0; i < hdr.nI; i++) {
            const Field& f = hdr.I[i];
            if (strcmp(f.name, "time") == 0) hdr.fTime = i;
            else if (strcmp(f.name, "loopIteration") == 0) hdr.fIter = i;
            else if (strcmp(f.name, "headspeed") == 0) hdr.fHs = i;
            else if (strcmp(f.name, "tailspeed") == 0) hdr.fTail = i;
            else if (strcmp(f.name, "motor") == 0 && f.idx == 0) hdr.fMotor0 = i;
            else if (strcmp(f.name, "gyroRAW") == 0 && f.idx >= 0 && f.idx < 3) hdr.fRaw[f.idx] = i;
            else if (strcmp(f.name, "gyroADC") == 0 && f.idx >= 0 && f.idx < 3) hdr.fGyro[f.idx] = i;
        }
        sink.onLogStart(hdr, streamPos);
    }

    // ---- frame decoding ------------------------------------------------
    // Returns bytes consumed (>0), 0 = need more, -1 = bad.
    int parseFrame(Sink& sink, bool probing) {
        if (len < 1) return 0;
        const uint8_t t = buf[0];
        if (t == 'H') {                     // "H " = the next log's header (a log cut short by a power cut has no End-of-log and no padding)
            if (len < 2) return 0;
            if (buf[1] == ' ') {
                if (inLog) { inLog = false; stats.truncatedLogs++; sink.onLogEnd(streamPos, false); }
                state = ST_SCAN; return scanForHeader(sink);
            }
        }
        Rd r(buf + 1, len - 1);
        int ok = 0;
        int32_t mainOut[MAX_FIELDS]; bool isMain = false, intra = false;
        switch (t) {
            case 'I': isMain = true; intra = true;  ok = decodeMainInto(r, true, mainOut); break;
            case 'P': isMain = true; intra = false; ok = decodeMainInto(r, false, mainOut); break;
            case 'S': ok = decodeSlow(r); if (ok > 0 && !probing) stats.sFrames++; break;
            case 'E': ok = decodeEvent(r, sink, probing); break;
            case 'G': ok = decodeGps(r, false); if (ok > 0 && !probing) stats.gFrames++; break;
            case 'H': ok = decodeGps(r, true);  if (ok > 0 && !probing) stats.hFrames++; break;
            case 0xFF: {                        // erased flash / padding after a log
                size_t k = 0; while (k < len && buf[k] == 0xFF) k++;
                if (k == len && !inLog) return (int)k;   // plain padding between logs
                if (inLog) { inLog = false; sink.onLogEnd(streamPos, false); stats.truncatedLogs++; }
                state = ST_SCAN; stats.skipped += (uint32_t)k; return (int)k;
            }
            default: return -1;
        }
        if (ok < 0) return -1;
        if (ok == 0) return 0;
        if (r.short_) return 0;
        // the byte after a frame must be a frame type (or the end of what we have)
        const size_t used = 1 + r.i;
        if (used < len) {
            const uint8_t nx = buf[used];
            if (!(nx == 'I' || nx == 'P' || nx == 'S' || nx == 'E' || nx == 'G' || nx == 'H' || nx == 0xFF)) return -1;
        }
        if (isMain && !probing) commitMain(intra, mainOut, sink);
        return (int)used;
    }

    // Try to find the next I frame (or a header) after corruption.
    int resync(Sink& sink) {
        for (size_t i = 0; i < len; i++) {
            if (buf[i] == 'H' && i + 1 >= len) return i ? (int)i : 0;   // an 'H' at the very end: wait for the next byte
            if (buf[i] == 'H' && buf[i + 1] == ' ') {
                // could be a new log header
                if (i) return (int)i;
                if (inLog) { inLog = false; sink.onLogEnd(streamPos, false); stats.truncatedLogs++; }
                state = ST_SCAN; return 0 + scanForHeader(sink);
            }
            if (buf[i] == 'I') {
                if (i) { stats.skipped += (uint32_t)i; return (int)i; }
                // probe-decode from here without touching history
                int32_t c[MAX_FIELDS]; memcpy(c, cur, sizeof c);
                Rd r(buf + 1, len - 1);
                int ok = decodeMainInto(r, true, c);
                if (r.short_) return 0;
                if (ok > 0) {
                    const size_t used = 1 + r.i;
                    if (used < len) {
                        const uint8_t nx = buf[used];
                        if (nx == 'I' || nx == 'P' || nx == 'S' || nx == 'E' || nx == 'G' || nx == 'H') { state = ST_FRAMES; return parseFrame(sink, false); }
                    } else return 0;
                }
                stats.skipped++; return 1;
            }
        }
        stats.skipped += (uint32_t)len; return (int)len;
    }

    static bool isTempField(const char* n) { return n[0] == 'T' && (!strcmp(n, "Tmcu") || !strcmp(n, "Tesc") || !strcmp(n, "Tbec") || !strcmp(n, "Tesc2")); }
    // decode an I or P frame into `out`; returns 1 ok, -1 bad, 0 short (r.short_)
    int decodeMainInto(Rd& r, bool intra, int32_t* out) {
        const int n = hdr.nI;
        if (n <= 0) return -1;
        for (int i = 0; i < n; ) {
            const Field& f = hdr.I[i];
            const uint8_t enc = intra ? f.ienc : f.penc;
            int32_t v[8]; int g = 1;
            switch (enc) {
                case E_SVB:   v[0] = r.svb(); break;
                case E_UVB:   v[0] = (int32_t)r.uvb(); break;
                case E_NEG14: v[0] = -signExt(r.uvb() & 0x3FFF, 14); break;
                case E_NULL:  v[0] = 0; break;
                case E_TAG8_8SVB: {
                    // writeInterframe packs magADC/altitude/vario/rssi as one group and Tmcu/Tesc/Tbec/Tesc2 as
                    // another; with nothing logged between them they are adjacent in the header, so stop at the family change.
                    const bool tempFam = isTempField(f.name);
                    g = 0; while (i + g < n && g < 8 && (intra ? hdr.I[i + g].ienc : hdr.I[i + g].penc) == E_TAG8_8SVB && isTempField(hdr.I[i + g].name) == tempFam) g++;
                    if (g == 1) v[0] = r.svb();
                    else { uint8_t h = r.u8(); for (int k = 0; k < g; k++) v[k] = (h & (1 << k)) ? r.svb() : 0; }
                    break;
                }
                case E_TAG2_3S32: g = 3; if (!readTag2_3S32(r, v)) return -1; break;
                case E_TAG2_3SVAR: g = 3; if (!readTag2_3SVar(r, v)) return -1; break;
                case E_TAG8_4S16: g = 4; if (!readTag8_4S16(r, v)) return -1; break;
                default: return -1;
            }
            if (r.short_) return 0;
            if (i + g > n) return -1;
            for (int k = 0; k < g; k++) {
                const Field& fk = hdr.I[i + k];
                int32_t val = v[k];
                const uint8_t pred = intra ? fk.ipred : fk.ppred;
                switch (pred) {
                    case P_ZERO: break;
                    case P_PREV:   val = (int32_t)((uint32_t)val + (uint32_t)prev1[i + k]); break;
                    case P_LINEAR: val = (int32_t)((uint32_t)val + 2u * (uint32_t)prev1[i + k] - (uint32_t)prev2[i + k]); break;
                    case P_AVG2:   val = (int32_t)((uint32_t)val + (uint32_t)(int32_t)(((int64_t)prev1[i + k] + prev2[i + k]) / 2)); break;
                    case P_MINTHR: val += hdr.minthrottle; break;
                    case P_MOTOR0: val += (hdr.fMotor0 >= 0) ? out[hdr.fMotor0] : 0; break;
                    case P_INC: val = (int32_t)((uint32_t)val + (uint32_t)prev1[i + k] + (uint32_t)hdr.pInterval); break;
                    case P_HOME: val += (fk.idx == 0) ? homeLat : homeLon; break;
                    case P_1500: val += 1500; break;
                    case P_VBATREF: val += hdr.vbatref; break;
                    case P_LASTTIME: val = (int32_t)((uint32_t)val + lastMainTime); break;
                    case P_MINMOTOR: val += hdr.minmotor; break;
                    default: return -1;
                }
                out[i + k] = val;
            }
            i += g;
        }
        return 1;
    }

    void commitMain(bool intra, const int32_t* out, Sink& sink) {
        memcpy(cur, out, sizeof(int32_t) * (size_t)hdr.nI);
        if (intra) { memcpy(prev1, cur, sizeof(int32_t) * (size_t)hdr.nI); memcpy(prev2, cur, sizeof(int32_t) * (size_t)hdr.nI); stats.iFrames++; }
        else       { memcpy(prev2, prev1, sizeof(int32_t) * (size_t)hdr.nI); memcpy(prev1, cur, sizeof(int32_t) * (size_t)hdr.nI); stats.pFrames++; }
        Frame fr;
        if (hdr.fTime >= 0) { fr.time = (uint32_t)cur[hdr.fTime]; lastMainTime = fr.time; }
        if (hdr.fRaw[0] >= 0) { fr.hasRaw = true; for (int a = 0; a < 3; a++) fr.raw[a] = hdr.fRaw[a] >= 0 ? cur[hdr.fRaw[a]] : 0; }
        if (hdr.fGyro[0] >= 0) { fr.hasGyro = true; for (int a = 0; a < 3; a++) fr.gyro[a] = hdr.fGyro[a] >= 0 ? cur[hdr.fGyro[a]] : 0; }
        if (hdr.fHs >= 0) { fr.hasHs = true; fr.hs = cur[hdr.fHs]; }
        if (hdr.fTail >= 0) fr.tail = cur[hdr.fTail];
        if (hdr.fMotor0 >= 0) { fr.hasMotor = true; fr.motor0 = cur[hdr.fMotor0]; }
        sink.onFrame(fr);
    }

    int decodeSlow(Rd& r) {
        if (!hdr.haveS) return -1;
        for (int i = 0; i < hdr.nS; ) {
            const uint8_t enc = hdr.S[i].ienc; int g = 1; int32_t v[8];
            switch (enc) {
                case E_SVB: v[0] = r.svb(); break;
                case E_UVB: v[0] = (int32_t)r.uvb(); break;
                case E_TAG2_3S32: g = 3; if (!readTag2_3S32(r, v)) return -1; break;
                case E_TAG8_8SVB: { g = 0; while (i + g < hdr.nS && g < 8 && hdr.S[i + g].ienc == E_TAG8_8SVB) g++; if (g == 1) v[0] = r.svb(); else { uint8_t h = r.u8(); for (int k = 0; k < g; k++) v[k] = (h & (1 << k)) ? r.svb() : 0; } break; }
                case E_NULL: v[0] = 0; break;
                default: return -1;
            }
            if (r.short_) return 0;
            i += g;
        }
        return 1;
    }

    int decodeGps(Rd& r, bool home) {
        const Field* F = home ? hdr.H : hdr.G; const int n = home ? hdr.nH : hdr.nG;
        if (n <= 0) return -1;
        int32_t vals[MAX_GPS];
        for (int i = 0; i < n; i++) {
            int32_t v;
            switch (F[i].ienc) {
                case E_SVB: v = r.svb(); break;
                case E_UVB: v = (int32_t)r.uvb(); break;
                case E_NEG14: v = -signExt(r.uvb() & 0x3FFF, 14); break;
                case E_NULL: v = 0; break;
                default: return -1;
            }
            if (r.short_) return 0;
            switch (F[i].ipred) {
                case P_HOME: v += (F[i].idx == 0) ? homeLat : homeLon; break;
                case P_LASTTIME: v += (int32_t)lastMainTime; break;
                default: break;
            }
            vals[i] = v;
        }
        if (home && n >= 2) { homeLat = vals[0]; homeLon = vals[1]; }
        return 1;
    }

    int decodeEvent(Rd& r, Sink& sink, bool probing) {
        const uint8_t id = r.u8(); if (r.short_) return 0;
        uint32_t a = 0, b = 0;
        switch (id) {
            case 0: a = r.uvb(); break;                                   // sync beep
            case 13: { uint8_t fn = r.u8(); if (fn & 128) (void)r.f32(); else (void)r.svb(); a = fn; break; }
            case 14: a = r.uvb(); b = r.uvb(); break;                     // logging resume
            case 15: a = r.uvb(); break;                                  // disarm
            case 30: a = r.uvb(); b = r.uvb(); break;                     // flight mode
            case 50: case 51: case 52: a = r.uvb(); break;                // gov / rescue / airborne state
            case 100: { uint8_t L = r.u8(); for (int k = 0; k < L; k++) r.u8(); a = L; break; }
            case 101: { uint8_t L = r.u8(); for (int k = 0; k < L; k++) r.u8(); a = L; break; }
            case 255: {                                                   // "End of log" + 0
                static const char END[] = "End of log";
                for (size_t k = 0; k < sizeof(END) - 1; k++) { if (r.u8() != (uint8_t)END[k] && !r.short_) return -1; }
                (void)r.u8();
                if (r.short_) return 0;
                if (!probing) { stats.eFrames++; sink.onEvent(id, 0, 0); if (inLog) { inLog = false; sink.onLogEnd(streamPos + 1 + r.i, true); } state = ST_SCAN; }
                return 1;
            }
            default: return -1;
        }
        if (r.short_) return 0;
        if (!probing) { stats.eFrames++; sink.onEvent(id, a, b); }
        return 1;
    }

    // ---- group encodings (mirrors of blackbox_encoding.c) ----
    static bool readTag2_3S32(Rd& r, int32_t* v) {
        const uint8_t b = r.u8(); if (r.short_) return true;
        switch (b >> 6) {
            case 0: v[0] = signExt((b >> 4) & 3, 2); v[1] = signExt((b >> 2) & 3, 2); v[2] = signExt(b & 3, 2); break;
            case 1: { v[0] = signExt(b & 0x0F, 4); const uint8_t c = r.u8(); v[1] = signExt(c >> 4, 4); v[2] = signExt(c & 0x0F, 4); break; }
            case 2: { v[0] = signExt(b & 0x3F, 6); v[1] = (int8_t)r.u8(); v[2] = (int8_t)r.u8(); break; }
            default: {
                uint8_t sel = b & 0x3F;
                for (int x = 0; x < 3; x++, sel >>= 2) {
                    const int nb = (sel & 3) + 1; uint32_t u = 0;
                    for (int k = 0; k < nb; k++) u |= (uint32_t)r.u8() << (8 * k);
                    v[x] = nb == 4 ? (int32_t)u : signExt(u, 8 * nb);
                }
            }
        }
        return true;
    }
    static bool readTag2_3SVar(Rd& r, int32_t* v) {
        const uint8_t b = r.u8(); if (r.short_) return true;
        switch (b >> 6) {
            case 0: v[0] = signExt((b >> 4) & 3, 2); v[1] = signExt((b >> 2) & 3, 2); v[2] = signExt(b & 3, 2); break;
            case 1: { const uint8_t c = r.u8(); v[0] = signExt((b >> 1) & 0x1F, 5); v[1] = signExt(((b & 1) << 4) | (c >> 4), 5); v[2] = signExt(c & 0x0F, 4); break; }
            case 2: { const uint8_t c = r.u8(), d = r.u8(); v[0] = signExt(((b & 0x3F) << 2) | (c >> 6), 8); v[1] = signExt(((c & 0x3F) << 1) | (d >> 7), 7); v[2] = signExt(d & 0x7F, 7); break; }
            default: {
                uint8_t sel = b & 0x3F;
                for (int x = 0; x < 3; x++, sel >>= 2) {
                    const int nb = (sel & 3) + 1; uint32_t u = 0;
                    for (int k = 0; k < nb; k++) u |= (uint32_t)r.u8() << (8 * k);
                    v[x] = nb == 4 ? (int32_t)u : signExt(u, 8 * nb);
                }
            }
        }
        return true;
    }
    static bool readTag8_4S16(Rd& r, int32_t* v) {
        uint8_t sel = r.u8(); if (r.short_) return true;
        int nib = 0; uint8_t bufb = 0;
        for (int x = 0; x < 4; x++, sel >>= 2) {
            switch (sel & 3) {
                case 0: v[x] = 0; break;
                case 1:
                    if (nib == 0) { bufb = r.u8(); v[x] = signExt(bufb >> 4, 4); nib = 1; }
                    else { v[x] = signExt(bufb & 0x0F, 4); nib = 0; }
                    break;
                case 2:
                    if (nib == 0) v[x] = (int8_t)r.u8();
                    else { const uint8_t c = r.u8(); v[x] = signExt(((bufb & 0x0F) << 4) | (c >> 4), 8); bufb = c; }
                    break;
                default:
                    if (nib == 0) { const uint8_t c1 = r.u8(), c2 = r.u8(); v[x] = signExt(((uint32_t)c1 << 8) | c2, 16); }
                    else { const uint8_t c1 = r.u8(), c2 = r.u8(); v[x] = signExt((((uint32_t)bufb & 0x0F) << 12) | ((uint32_t)c1 << 4) | (c2 >> 4), 16); bufb = c2; }
                    break;
            }
        }
        return true;
    }
};

} // namespace BbDec

// ======================================================================
//  Analyser: Welch spectra of the gyro (raw and filtered), an order-domain
//  spectrum locked to the head speed, and a per-window timeline.
// ======================================================================
namespace BbAn {

constexpr int N    = 512;            // FFT size
constexpr int HOP  = 256;            // window step (50 % overlap)
constexpr int BINS = N / 2 + 1;      // 257
constexpr int ORD  = 400;            // order bins, 0.1 order each: 0 .. 40 per rev
constexpr int TL   = 160;            // timeline entries kept
constexpr int HSH  = 80;             // head-speed histogram, 50 rpm bins
constexpr int MAX_LOGS = 64;
constexpr float FLY_RPM = 300.0f;    // a window counts as "flying" above this head speed

struct LogInfo { uint32_t addr = 0, end = 0, frames = 0; float seconds = 0, hsMedian = 0; bool clean = false; };

// Everything the page gets for ONE log. Kept as a block so the newest FLYING
// log survives a bench arm after landing (which would otherwise be "the last log").
struct Res {
    float fRaw[3][BINS], fFilt[3][BINS]; uint32_t flyWin;
    float gRaw[3][BINS];                 uint32_t gndWin;
    float oRaw[3][ORD], oFilt[3][ORD], oCnt[ORD];
    struct TLE { float t, hs, rr[3], fr[3]; } tl[TL]; int tlN, tlStride, tlSkip;
    uint32_t hsHist[HSH];
    float hsMaxAll;                      // over every window, flying or not (the "never rose above" message)
    float rate;                          // samples per second (measured)
    uint32_t frames; float seconds; uint32_t firstTime, lastTime; bool haveFirst;
    bool hasRaw, hasGyro, hasHs, hasMotor;
    uint32_t events[8];                  // counts by class: 0 disarm,1 gov,2 rescue,3 airborne,4 adjust,5 resume,6 other
    int logIdx;                          // 0-based index of the log these came from
    BbDec::Header hdr;
    void clear() { memset(this, 0, sizeof *this); tlStride = 1; logIdx = -1; hdr.clear(); }
};

struct Analyser : BbDec::Sink {
    Res r;                               // the log being read
    Res keep; bool haveKeep = false;     // the newest log that FLEW (wantLog == 0 only)
    LogInfo logs[MAX_LOGS]; int nLogs = 0, logsTotal = 0; int curLog = -1;
    int wantLog = 0;                     // 0 = the newest flying log (else the newest), else 1-based
    bool selectedDone = false;           // wantLog reached and finished

    // ---- working state ----
    int16_t ringR[3][N], ringF[3][N]; int ringPos = 0; uint32_t ringCount = 0; int sinceHop = 0;
    float hsAcc = 0; uint32_t hsN = 0;   // head speed over the current hop
    uint32_t dtSamples[64]; int dtN = 0; uint32_t prevTime = 0;
    float fftRe[N], fftIm[N], win[N], twr[N / 2], twi[N / 2];
    bool accumulating = false;           // true while inside a log we may report

    Analyser() { init(); }
    void init() {
        for (int i = 0; i < N; i++) win[i] = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * (float)i / (float)N);
        for (int i = 0; i < N / 2; i++) { twr[i] = cosf(-2.0f * (float)M_PI * (float)i / (float)N); twi[i] = sinf(-2.0f * (float)M_PI * (float)i / (float)N); }
        r.clear(); keep.clear(); haveKeep = false; nLogs = 0; logsTotal = 0; curLog = -1; selectedDone = false; resetWork();
    }
    void resetWork() {
        ringPos = 0; ringCount = 0; sinceHop = 0; hsAcc = 0; hsN = 0; dtN = 0; prevTime = 0;
        memset(ringR, 0, sizeof ringR); memset(ringF, 0, sizeof ringF);
    }
    // the block the page should see
    const Res& result() const { return (wantLog == 0 && haveKeep && r.flyWin == 0) ? keep : r; }

    void onLogStart(const BbDec::Header& h, uint32_t offset) override {
        if (!h.haveI) {                       // the magic was found; the header follows — a new log begins
            logsTotal++;
            if (nLogs < MAX_LOGS) { curLog = nLogs++; }
            else { memmove(&logs[0], &logs[1], sizeof(LogInfo) * (MAX_LOGS - 1)); curLog = MAX_LOGS - 1; }   // keep the newest 64
            logs[curLog] = LogInfo(); logs[curLog].addr = offset;
            accumulating = (wantLog == 0) || (wantLog == logsTotal);
            if (accumulating) { r.clear(); r.logIdx = logsTotal - 1; resetWork(); }
            return;
        }
        if (accumulating) r.hdr = h;         // fields known now
    }
    void onFrame(const BbDec::Frame& f) override {
        if (curLog >= 0) logs[curLog].frames++;
        if (!accumulating) return;
        r.frames++;
        if (!r.haveFirst) { r.haveFirst = true; r.firstTime = f.time; prevTime = f.time; }
        else {
            uint32_t dt = f.time - prevTime; prevTime = f.time;
            if (dtN < 64 && dt > 0 && dt < 100000) dtSamples[dtN++] = dt;
            if (dtN == 64 && r.rate == 0) rateFromDt();
        }
        r.lastTime = f.time;
        r.hasRaw |= f.hasRaw; r.hasGyro |= f.hasGyro; r.hasHs |= f.hasHs; r.hasMotor |= f.hasMotor;
        // samples: raw missing → use the filtered one for both (marked in the summary)
        for (int a = 0; a < 3; a++) {
            const int32_t rv = f.hasRaw ? f.raw[a] : f.gyro[a];
            const int32_t fv = f.hasGyro ? f.gyro[a] : f.raw[a];
            ringR[a][ringPos] = (int16_t)(rv > 32767 ? 32767 : rv < -32768 ? -32768 : rv);
            ringF[a][ringPos] = (int16_t)(fv > 32767 ? 32767 : fv < -32768 ? -32768 : fv);
        }
        if (f.hasHs) { hsAcc += (float)f.hs; hsN++; }
        ringPos = (ringPos + 1) % N; ringCount++; sinceHop++;
        if (ringCount >= (uint32_t)N && sinceHop >= HOP) { sinceHop = 0; window(); }
    }
    void onLogEnd(uint32_t offset, bool clean) override {
        if (curLog >= 0) {
            logs[curLog].end = offset; logs[curLog].clean = clean;
            if (accumulating) { finalizeRate(); logs[curLog].seconds = r.seconds; logs[curLog].hsMedian = hsMedian(r); }
        }
        if (accumulating) {
            if (wantLog == 0 && r.flyWin > 0) { keep = r; haveKeep = true; }   // the newest log that flew
            if (wantLog != 0) selectedDone = true;
        }
        accumulating = false;
    }
    void onEvent(uint8_t id, uint32_t a, uint32_t b) override {
        (void)a; (void)b;
        if (!accumulating) return;
        int k;
        switch (id) { case 15: k = 0; break; case 50: k = 1; break; case 51: k = 2; break; case 52: k = 3; break; case 13: k = 4; break; case 14: k = 5; break; default: k = 6; }
        r.events[k]++;
    }
    void finalizeRate() {
        if (r.rate == 0 && dtN > 0) rateFromDt();
        if (r.rate == 0 && r.hdr.looptime > 0) r.rate = 1e6f / ((float)r.hdr.looptime * (float)(r.hdr.pInterval > 0 ? r.hdr.pInterval : 1));
        r.seconds = (r.haveFirst && r.rate > 0) ? (float)r.frames / r.rate : 0;
    }
    void rateFromDt() {
        uint32_t s[64]; memcpy(s, dtSamples, sizeof(uint32_t) * (size_t)dtN);
        for (int i = 1; i < dtN; i++) { uint32_t v = s[i]; int j = i - 1; while (j >= 0 && s[j] > v) { s[j + 1] = s[j]; j--; } s[j + 1] = v; }
        const uint32_t med = s[dtN / 2];
        if (med > 0) r.rate = 1e6f / (float)med;
    }
    static float hsMedian(const Res& R) {
        uint32_t tot = 0; for (int i = 0; i < HSH; i++) tot += R.hsHist[i];
        if (!tot) return 0;
        uint32_t acc = 0; for (int i = 0; i < HSH; i++) { acc += R.hsHist[i]; if (acc * 2 >= tot) return (float)i * 50.0f + 25.0f; }
        return 0;
    }
    static float hsMax(const Res& R) { for (int i = HSH - 1; i >= 0; i--) if (R.hsHist[i]) return (float)i * 50.0f + 50.0f; return 0; }
    float hsMedian() const { return hsMedian(result()); }
    uint32_t flyWinNow() const { return result().flyWin; }
    float rateNow() const { return result().rate; }

    // one Welch window over the last N samples
    void window() {
        if (r.rate == 0 && dtN > 0) rateFromDt();
        const float hs = hsN ? hsAcc / (float)hsN : 0; hsAcc = 0; hsN = 0;
        const bool flying = r.hasHs ? (hs >= FLY_RPM) : true;
        if (hs > r.hsMaxAll) r.hsMaxAll = hs;
        if (r.hasHs && flying) { int b = (int)(hs / 50.0f); if (b >= HSH) b = HSH - 1; if (b >= 0) r.hsHist[b]++; }
        float rmsR[3], rmsF[3];
        float pw[BINS];
        const float fRot = hs / 60.0f;
        for (int a = 0; a < 3; a++) {
            spectrum(ringR[a], pw, rmsR[a]);
            if (flying) { for (int k = 0; k < BINS; k++) r.fRaw[a][k] += pw[k]; if (r.hasHs && fRot > 1.0f) order(pw, fRot, r.oRaw[a], a == 0); }
            else        { for (int k = 0; k < BINS; k++) r.gRaw[a][k] += pw[k]; }
            spectrum(ringF[a], pw, rmsF[a]);
            if (flying) { for (int k = 0; k < BINS; k++) r.fFilt[a][k] += pw[k]; if (r.hasHs && fRot > 1.0f) order(pw, fRot, r.oFilt[a], false); }
        }
        if (flying) r.flyWin++; else r.gndWin++;
        // timeline (decimated when full)
        const float t = (r.rate > 0) ? (float)(ringCount) / r.rate : 0;
        if (r.tlSkip > 0) { r.tlSkip--; }
        else {
            if (r.tlN >= TL) { for (int i = 0; i < TL / 2; i++) r.tl[i] = r.tl[2 * i]; r.tlN = TL / 2; r.tlStride *= 2; }
            Res::TLE& e = r.tl[r.tlN++]; e.t = t; e.hs = hs; for (int a = 0; a < 3; a++) { e.rr[a] = rmsR[a]; e.fr[a] = rmsF[a]; }
            r.tlSkip = r.tlStride - 1;
        }
    }
    void spectrum(const int16_t* ring, float* pw, float& rms) {
        // float throughout: the S3 has no double FPU (int16 sums fit a float exactly up to 2^24)
        int32_t sum = 0; for (int i = 0; i < N; i++) sum += ring[(ringPos + i) % N];
        const float mean = (float)sum / (float)N;
        float sq = 0;
        for (int i = 0; i < N; i++) { const float v = (float)ring[(ringPos + i) % N] - mean; sq += v * v; fftRe[i] = v * win[i]; fftIm[i] = 0; }
        rms = sqrtf(sq / (float)N);
        fft();
        const float scale = 1.0f / ((float)N * 0.375f);     // Hann window power compensation
        for (int k = 0; k < BINS; k++) pw[k] = (fftRe[k] * fftRe[k] + fftIm[k] * fftIm[k]) * scale;
    }
    void order(const float* pw, float fRot, float* acc, bool count) {
        const float df = r.rate / (float)N;
        for (int k = 1; k < BINS; k++) {
            const float o = (float)k * df / fRot;
            const int ob = (int)(o * 10.0f + 0.5f);
            if (ob >= ORD) break;
            acc[ob] += pw[k];
            if (count) r.oCnt[ob] += 1.0f;
        }
    }
    void fft() {
        for (int i = 1, j = 0; i < N; i++) {
            int bit = N >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit;
            if (i < j) { float t = fftRe[i]; fftRe[i] = fftRe[j]; fftRe[j] = t; t = fftIm[i]; fftIm[i] = fftIm[j]; fftIm[j] = t; }
        }
        for (int len = 2; len <= N; len <<= 1) {
            const int step = N / len;
            for (int i = 0; i < N; i += len) {
                for (int j = 0; j < len / 2; j++) {
                    const float wr = twr[j * step], wi = twi[j * step];
                    const int u = i + j, v = i + j + len / 2;
                    const float tr = fftRe[v] * wr - fftIm[v] * wi, ti = fftRe[v] * wi + fftIm[v] * wr;
                    fftRe[v] = fftRe[u] - tr; fftIm[v] = fftIm[u] - ti;
                    fftRe[u] += tr; fftIm[u] += ti;
                }
            }
        }
    }

    // ---- JSON ----------------------------------------------------------
    // part: 0 summary, 1 fly, 2 gnd, 3 order raw+count, 4 timeline, 5 order filtered. Returns bytes written (0 if cap too small).
    struct W { char* o; size_t cap, n; bool ovf;
        void put(const char* s) { size_t L = strlen(s); if (n + L >= cap) { ovf = true; return; } memcpy(o + n, s, L); n += L; }
        void num(long v) { char b[24]; snprintf(b, sizeof b, "%ld", v); put(b); }
        void fnum(float v, int d) { char b[32]; snprintf(b, sizeof b, "%.*f", d, (double)v); put(b); }
    };
    static int dB10(float p, float div) { if (div <= 0) div = 1; float v = p / div; if (v < 1e-6f) v = 1e-6f; return (int)lrintf(100.0f * log10f(v)); }   // dB × 10
    static void jstr(W& w, const char* s) {          // JSON string body: escape quotes, backslashes and control bytes
        for (const unsigned char* p = (const unsigned char*)s; *p; p++) {
            char b[8];
            if (*p == '"' || *p == '\\') { b[0] = '\\'; b[1] = (char)*p; b[2] = 0; }
            else if (*p < 0x20) { snprintf(b, sizeof b, "\\u%04x", *p); }
            else { b[0] = (char)*p; b[1] = 0; }
            w.put(b);
        }
    }
    static void arrDb(W& w, const float* a, int n, float div) { w.put("["); for (int k = 0; k < n; k++) { if (k) w.put(","); w.num(dB10(a[k], div)); } w.put("]"); }
    static void arrDb3(W& w, const float (*a)[BINS], float div) { w.put("["); for (int x = 0; x < 3; x++) { if (x) w.put(","); arrDb(w, a[x], BINS, div); } w.put("]"); }
    static void arrOrd(W& w, const Res& R, const float (*a)[ORD]) { w.put("["); for (int x = 0; x < 3; x++) { if (x) w.put(","); w.put("["); for (int k = 0; k < ORD; k++) { if (k) w.put(","); w.num(R.oCnt[k] > 0 ? dB10(a[x][k], R.oCnt[k]) : -600); } w.put("]"); } w.put("]"); }

    size_t toJson(int part, char* out, size_t cap) {
        W w{out, cap, 0, false};
        const Res& R = result();
        switch (part) {
            case 0: {
                w.put("{\"rate\":"); w.fnum(R.rate, 1);
                w.put(",\"frames\":"); w.num(R.frames);
                w.put(",\"seconds\":"); w.fnum(R.seconds, 1);
                w.put(",\"flyWin\":"); w.num(R.flyWin); w.put(",\"gndWin\":"); w.num(R.gndWin);
                w.put(",\"bins\":"); w.num(BINS); w.put(",\"n\":"); w.num(N); w.put(",\"ordStep\":0.1,\"ord\":"); w.num(ORD);
                w.put(",\"fields\":{\"raw\":"); w.put(R.hasRaw ? "true" : "false"); w.put(",\"gyro\":"); w.put(R.hasGyro ? "true" : "false");
                w.put(",\"hs\":"); w.put(R.hasHs ? "true" : "false"); w.put(",\"motor\":"); w.put(R.hasMotor ? "true" : "false"); w.put("}");
                w.put(",\"hs\":{\"median\":"); w.fnum(hsMedian(R), 0); w.put(",\"max\":"); w.fnum(hsMax(R), 0); w.put(",\"maxAll\":"); w.fnum(R.hsMaxAll, 0); w.put(",\"hist\":[");
                for (int i = 0; i < HSH; i++) { if (i) w.put(","); w.num(R.hsHist[i]); } w.put("]}");
                w.put(",\"header\":{\"firmware\":\""); jstr(w, R.hdr.firmware); w.put("\",\"craft\":\""); jstr(w, R.hdr.craft); w.put("\",\"date\":\""); jstr(w, R.hdr.date);
                w.put("\",\"looptime\":"); w.num(R.hdr.looptime); w.put(",\"pInterval\":"); w.num(R.hdr.pInterval); w.put(",\"iInterval\":"); w.num(R.hdr.iInterval);
                w.put(",\"fieldsMask\":"); w.num((long)R.hdr.fieldsMask); w.put(",\"rpmPreset\":"); w.num(R.hdr.rpmPreset); w.put(",\"nFields\":"); w.num(R.hdr.nI); w.put("}");
                w.put(",\"events\":{\"disarm\":"); w.num(R.events[0]); w.put(",\"gov\":"); w.num(R.events[1]); w.put(",\"rescue\":"); w.num(R.events[2]); w.put(",\"airborne\":"); w.num(R.events[3]); w.put(",\"adjust\":"); w.num(R.events[4]); w.put(",\"resume\":"); w.num(R.events[5]); w.put(",\"other\":"); w.num(R.events[6]); w.put("}");
                w.put(",\"logs\":[");
                for (int i = 0; i < nLogs; i++) { if (i) w.put(","); w.put("{\"addr\":"); w.num((long)logs[i].addr); w.put(",\"end\":"); w.num((long)logs[i].end); w.put(",\"frames\":"); w.num((long)logs[i].frames); w.put(",\"seconds\":"); w.fnum(logs[i].seconds, 1); w.put(",\"hsMedian\":"); w.fnum(logs[i].hsMedian, 0); w.put(",\"clean\":"); w.put(logs[i].clean ? "true" : "false"); w.put("}"); }
                w.put("],\"logsTotal\":"); w.num(logsTotal); w.put(",\"logsFirst\":"); w.num(logsTotal - nLogs + 1);   // logs[0] is this 1-based log number
                w.put(",\"wantLog\":"); w.num(wantLog); w.put(",\"log\":"); w.num(R.logIdx + 1); w.put(",\"keptFlying\":"); w.put((wantLog == 0 && haveKeep && r.flyWin == 0) ? "true" : "false"); w.put("}");
                break;
            }
            case 1: { const float d = R.flyWin ? (float)R.flyWin : 1; w.put("{\"raw\":"); arrDb3(w, R.fRaw, d); w.put(",\"filt\":"); arrDb3(w, R.fFilt, d); w.put("}"); break; }
            case 2: { const float d = R.gndWin ? (float)R.gndWin : 1; w.put("{\"raw\":"); arrDb3(w, R.gRaw, d); w.put("}"); break; }
            case 3: { w.put("{\"raw\":"); arrOrd(w, R, R.oRaw); w.put(",\"cnt\":["); for (int k = 0; k < ORD; k++) { if (k) w.put(","); w.num((long)R.oCnt[k]); } w.put("]}"); break; }
            case 4: {
                w.put("{\"stride\":"); w.num(R.tlStride); w.put(",\"rows\":[");
                for (int i = 0; i < R.tlN; i++) { if (i) w.put(","); w.put("["); w.fnum(R.tl[i].t, 1); w.put(","); w.fnum(R.tl[i].hs, 0);
                    for (int a = 0; a < 3; a++) { w.put(","); w.fnum(R.tl[i].rr[a], 1); } for (int a = 0; a < 3; a++) { w.put(","); w.fnum(R.tl[i].fr[a], 1); } w.put("]"); }
                w.put("]}"); break;
            }
            case 5: { w.put("{\"filt\":"); arrOrd(w, R, R.oFilt); w.put("}"); break; }
            default: w.put("{}");
        }
        if (w.ovf) return 0;
        out[w.n] = 0; return w.n;
    }
};

} // namespace BbAn
#endif // _SRC_BLACKBOXDECODE_H
