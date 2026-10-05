#include "LdrcLink.h"
#include <string.h>

namespace ldrc {

const char *errorText(uint8_t code) {
    switch (code) {
        case LE_OK: return "ok";
        case LE_BAD_REQUEST: return "bad request";
        case LE_NO_FILE: return "no such file";
        case LE_IO: return "card read/write failed";
        case LE_SEQUENCE: return "out of sequence";
        case LE_CRC: return "checksum wrong";
        case LE_SIZE: return "wrong size";
        case LE_PROTECTED: return "pilot's data, not touched";
        case LE_BUSY: return "a model is connected";
        case LE_NO_CARD: return "no SD card";
        case LE_BAD_IMAGE: return "not firmware for this transmitter";
        case LE_BATTERY: return "battery too low";
        case LE_UNSUPPORTED: return "not supported";
        case LE_NO_PREVIOUS: return "no previous firmware kept";
        case LE_NOT_NOW: return "the transmitter is in the middle of something (a question on screen, calibration, a scan). Go to its front page and try again";
        case LE_MOTOR_ON: return "the motor is on";
        case LE_SAFETY_OFF: return "the safety is off";
        case LE_MODEL_JUST_NOW: return "a model was connected less than a minute ago";
        default: return "error";
    }
}

uint32_t crc32(const uint8_t *data, size_t n, uint32_t crc) {
    static uint32_t table[256]; static bool made = false;
    if (!made) {
        for (uint32_t i = 0; i < 256; ++i) { uint32_t c = i; for (int k = 0; k < 8; ++k) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1; table[i] = c; }
        made = true;
    }
    crc = ~crc;
    for (size_t i = 0; i < n; ++i) crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

bool Frame::getText(size_t at, char *out, size_t outSize) const {
    if (at > len || outSize == 0) return false;
    const size_t n = len - at;
    if (n + 1 > outSize) return false;
    memcpy(out, payload + at, n); out[n] = 0;
    return true;
}

size_t encode(const Frame &f, uint8_t *out) {
    const uint16_t len = f.len > LINK_MAX_PAYLOAD ? LINK_MAX_PAYLOAD : f.len;
    out[0] = LINK_SOF0; out[1] = LINK_SOF1; out[2] = f.type; out[3] = f.seq; out[4] = (uint8_t) len; out[5] = (uint8_t) (len >> 8);
    memcpy(out + 6, f.payload, len);
    const uint32_t c = crc32(out + 2, 4u + len);
    out[6 + len] = (uint8_t) c; out[7 + len] = (uint8_t) (c >> 8); out[8 + len] = (uint8_t) (c >> 16); out[9 + len] = (uint8_t) (c >> 24);
    return 10u + len;
}

bool Parser::push(uint8_t b, Frame &out) {
    switch (state_) {
        case 0: if (b == LINK_SOF0) state_ = 1; return false;
        case 1: if (b == LINK_SOF1) { state_ = 2; got_ = 0; } else state_ = (b == LINK_SOF0) ? 1 : 0; return false;
        case 2:
            head_[got_++] = b;
            if (got_ == 4) {
                work_.type = head_[0]; work_.seq = head_[1]; work_.len = (uint16_t) (head_[2] | (head_[3] << 8));
                if (work_.len > LINK_MAX_PAYLOAD) { state_ = 0; return false; }      // not a frame: hunt again
                got_ = 0; state_ = work_.len ? 3 : 4;
            }
            return false;
        case 3:
            work_.payload[got_++] = b;
            if (got_ == work_.len) { got_ = 0; state_ = 4; }
            return false;
        default:
            crc_[got_++] = b;
            if (got_ < 4) return false;
            state_ = 0;
            {
                uint32_t c = crc32(head_, 4);
                c = crc32(work_.payload, work_.len, c);
                const uint32_t sent = (uint32_t) crc_[0] | ((uint32_t) crc_[1] << 8) | ((uint32_t) crc_[2] << 16) | ((uint32_t) crc_[3] << 24);
                if (c != sent) { badCrc_++; return false; }
            }
            out.type = work_.type; out.seq = work_.seq; out.len = work_.len;
            memcpy(out.payload, work_.payload, work_.len);
            return true;
    }
}

bool fwHeaderParse(const uint8_t *raw, FwHeader &h) {
    if (memcmp(raw, LDRC_FW_MAGIC, 8) != 0) return false;
    memcpy(h.magic, raw, 8);
    h.size = (uint32_t) raw[8] | ((uint32_t) raw[9] << 8) | ((uint32_t) raw[10] << 16) | ((uint32_t) raw[11] << 24);
    h.crc  = (uint32_t) raw[12] | ((uint32_t) raw[13] << 8) | ((uint32_t) raw[14] << 16) | ((uint32_t) raw[15] << 24);
    memcpy(h.version, raw + 16, 32); memcpy(h.target, raw + 48, 16);
    if (h.version[31] != 0 || h.target[15] != 0) return false;
    return true;
}
void fwHeaderBuild(const FwHeader &h, uint8_t *raw) {
    memset(raw, 0, FW_HEADER_SIZE);
    memcpy(raw, LDRC_FW_MAGIC, 8);
    raw[8] = (uint8_t) h.size; raw[9] = (uint8_t) (h.size >> 8); raw[10] = (uint8_t) (h.size >> 16); raw[11] = (uint8_t) (h.size >> 24);
    raw[12] = (uint8_t) h.crc; raw[13] = (uint8_t) (h.crc >> 8); raw[14] = (uint8_t) (h.crc >> 16); raw[15] = (uint8_t) (h.crc >> 24);
    strncpy((char *) raw + 16, h.version, 31); strncpy((char *) raw + 48, h.target, 15);
}

static char lower(char c) { return (c >= 'A' && c <= 'Z') ? (char) (c + 32) : c; }
static bool startsWithNoCase(const char *s, const char *prefix) { while (*prefix) { if (lower(*s++) != lower(*prefix++)) return false; } return true; }
static bool equalsNoCase(const char *a, const char *b) { while (*a && *b) { if (lower(*a++) != lower(*b++)) return false; } return *a == 0 && *b == 0; }
static bool endsWithNoCase(const char *s, const char *suffix) { const size_t n = strlen(s), m = strlen(suffix); return n >= m && equalsNoCase(s + n - m, suffix); }

bool isUserData(const char *path) {
    while (*path == '/') path++;
    // models and their backups, logs: the pilot's. Help texts and firmware packages are ours.
    return equalsNoCase(path, "models.dat") || startsWithNoCase(path, "mod/") || startsWithNoCase(path, "log/") ||
           endsWithNoCase(path, ".mod") || endsWithNoCase(path, ".log") || endsWithNoCase(path, ".dat");
}

bool plainPath(const char *p) {
    if (!p || p[0] != '/' || p[1] == 0) return false;
    const size_t n = strlen(p);
    if (n >= LINK_MAX_PATH || p[n - 1] == '/') return false;
    for (size_t i = 0; i < n; ++i) {
        const unsigned char c = (unsigned char) p[i];
        if (c < 32 || c == 127 || c == '\\' || c == ':' || c == '*' || c == '?' || c == '"' || c == '<' || c == '>' || c == '|') return false;
        if (c == '.' && p[i + 1] == '.') return false;                      // no climbing out
        if (c == '/') {
            if (p[i + 1] == '/' || p[i + 1] == ' ') return false;           // an empty part; a part that begins with a space
            if (i > 0 && (p[i - 1] == ' ' || p[i - 1] == '.')) return false; // a part that ends with a space or a dot
        }
    }
    return p[n - 1] != ' ' && p[n - 1] != '.';
}

}  // namespace ldrc
