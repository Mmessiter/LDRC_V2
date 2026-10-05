// LdrcLink — the framed link between the transmitter's screen (ESP32-S3) and its Teensy 4.1, on the
// same UART that carries the display protocol. Used for files on the Teensy's SD card and for
// replacing the Teensy's firmware. Portable C++11: no Arduino types, so both ends (and the host
// tests) compile the same source. KEEP THE TWO COPIES IDENTICAL (dev/sync_link.sh):
//     TXV1B/TransmitterCode/lib/LdrcLink            (the Teensy)
//     ESP32-board2/board4/nextion-emulator/lib/LdrcLink   (the screen)
//
// A frame, in both directions:
//     A5 5A | type | seq | len lo | len hi | payload[len] | crc32 (LE) over type..payload
// The screen asks, the Teensy answers with type | 0x80 and the same seq; the first payload byte of
// every answer is a status (LE_OK or an error). One request at a time (stop and wait): the Teensy
// stops listening while it writes flash or the card, so nothing is in flight then.
#ifndef LDRC_LINK_H
#define LDRC_LINK_H

#include <stdint.h>
#include <stddef.h>

namespace ldrc {

const uint8_t  LINK_PROTO       = 1;
const uint8_t  LINK_SOF0        = 0xA5, LINK_SOF1 = 0x5A;
const uint16_t LINK_BLOCK       = 1024;      // file bytes per frame
const uint16_t LINK_MAX_PAYLOAD = 1100;      // a block plus its small header
const size_t   LINK_MAX_FRAME   = LINK_MAX_PAYLOAD + 10;
const size_t   LINK_MAX_PATH    = 288;       // a folder and a long file name (FAT: 255). It was 96 until 2.5.6 B7: longer names could be listed and not fetched

// The words that open the link: sent by the screen as an ordinary touch-event text.
#define LDRC_LINK_KNOCK "LDRCLINK"
// The words that order the connected receiver to update itself, followed by " major minor minimus" (B11 / screen
// 1.3.0): sent by the screen as an ordinary touch-event text; the Teensy answers on the wire with "ldrcrx=...".
#define LDRC_RX_UPDATE_WORD "LDRCRXUP"
// The screen's own picture chooser (screen 1.5.0, B21), as the pilot presses OK or Cancel: "LDRCIMG <name>" (the
// picture's name, 1-8 of A-Z a-z 0-9 _ -, or "Noimage") or "LDRCIMG" alone (keep what the model has). An ordinary
// touch-event text, as the knock is. The pictures live on the screen's card only.
#define LDRC_IMAGE_WORD "LDRCIMG"

enum : uint8_t {
    LK_HELLO = 0x01,          // -> text "proto=1;fw=...;target=...;state=...;card=1;free=..."
    LK_STAT = 0x02,           // path -> exists u8, size u32, crc32 u32
    LK_LIST = 0x03,           // start u32, dir -> count u8, more u8, { size u32, isDir u8, name\0 }...
    LK_WRITE_BEGIN = 0x10,    // flags u8, size u32, crc32 u32, path
    LK_WRITE_DATA = 0x11,     // offset u32, bytes            -> next offset u32
    LK_WRITE_END = 0x12,      //                              -> size u32, crc32 u32 (as read back from the card)
    LK_READ_BEGIN = 0x20,     // path                         -> size u32, crc32 u32
    LK_READ_DATA = 0x21,      // offset u32, want u16         -> offset u32, bytes
    LK_DELETE = 0x30,         // flags u8, path
    LK_MKDIR = 0x31,          // path
    LK_FW_INSTALL = 0x40,     // path of a firmware package on the Teensy's card
    LK_FW_CONFIRM = 0x41,     // the firmware on trial is accepted
    LK_FW_ROLLBACK = 0x42,    // put the previous firmware back
    LK_BYE = 0x7F,            // leave the link, carry on as a transmitter
    LK_REPLY = 0x80
};

enum : uint8_t {
    LE_OK = 0, LE_BAD_REQUEST = 1, LE_NO_FILE = 2, LE_IO = 3, LE_SEQUENCE = 4, LE_CRC = 5, LE_SIZE = 6,
    LE_PROTECTED = 7, LE_BUSY = 8, LE_NO_CARD = 9, LE_BAD_IMAGE = 10, LE_BATTERY = 11, LE_UNSUPPORTED = 12,
    LE_NO_PREVIOUS = 13, LE_NOT_NOW = 14,
    LE_MOTOR_ON = 15, LE_SAFETY_OFF = 16, LE_MODEL_JUST_NOW = 17     // (2.5.6 B8) the link stays shut: flying comes first
};
const char *errorText(uint8_t code);

enum : uint8_t { LF_USER_DATA = 0x01 };       // flags: the caller really means to replace/delete the pilot's own data

// zlib's CRC-32. Chain calls by passing the previous result: crc = crc32(a, na); crc = crc32(b, nb, crc);
uint32_t crc32(const uint8_t *data, size_t n, uint32_t crc = 0);

struct Frame {
    uint8_t type, seq;
    uint16_t len;
    uint8_t payload[LINK_MAX_PAYLOAD];
    Frame() : type(0), seq(0), len(0) {}
    // building a payload
    void clear(uint8_t t, uint8_t s) { type = t; seq = s; len = 0; }
    bool put8(uint8_t v)   { if (len + 1u > LINK_MAX_PAYLOAD) return false; payload[len++] = v; return true; }
    bool put16(uint16_t v) { return put8((uint8_t) v) && put8((uint8_t) (v >> 8)); }
    bool put32(uint32_t v) { return put16((uint16_t) v) && put16((uint16_t) (v >> 16)); }
    bool putBytes(const uint8_t *b, size_t n) { if (len + n > LINK_MAX_PAYLOAD) return false; for (size_t i = 0; i < n; ++i) payload[len++] = b[i]; return true; }
    bool putText(const char *s) { while (*s) if (!put8((uint8_t) *s++)) return false; return true; }   // no terminator: text runs to the end of the payload
    // reading one
    uint8_t  get8(size_t at) const  { return at < len ? payload[at] : 0; }
    uint16_t get16(size_t at) const { return (uint16_t) (get8(at) | (get8(at + 1) << 8)); }
    uint32_t get32(size_t at) const { return (uint32_t) get16(at) | ((uint32_t) get16(at + 2) << 16); }
    // the text from `at` to the end of the payload, copied and terminated; false if it does not fit
    bool getText(size_t at, char *out, size_t outSize) const;
};

// Bytes for the wire. `out` must hold LINK_MAX_FRAME bytes. Returns the count.
size_t encode(const Frame &f, uint8_t *out);

// Bytes from the wire. push() returns true when a whole frame with a good CRC has arrived.
// A frame travels as one burst: a gap of more than LINK_GAP_MS inside one means a byte was lost, and the
// half-read frame is dropped - otherwise it would swallow the start of the repeat that follows.
const uint32_t LINK_GAP_MS = 60;
class Parser {
public:
    Parser() : badCrc_(0), gaps_(0) { reset(); }
    void reset() { state_ = 0; got_ = 0; }
    bool push(uint8_t b, Frame &out);
    bool push(uint8_t b, Frame &out, uint32_t nowMs) {
        if (state_ != 0 && nowMs - lastMs_ > LINK_GAP_MS) { reset(); gaps_++; }
        lastMs_ = nowMs;
        return push(b, out);
    }
    bool midFrame() const { return state_ != 0; }
    uint32_t badCrc() const { return badCrc_; }
    uint32_t gaps() const { return gaps_; }
private:
    uint8_t state_; uint16_t got_; uint8_t head_[4]; uint8_t crc_[4]; uint32_t badCrc_, gaps_, lastMs_;
    Frame work_;
};

// Spots the words that open the link in a stream of bytes.
class Knock {
public:
    Knock() : at_(0) {}
    void reset() { at_ = 0; }
    bool push(uint8_t b) {
        static const char words[] = LDRC_LINK_KNOCK;
        if (b == (uint8_t) words[at_]) { if (words[++at_] == 0) { at_ = 0; return true; } }
        else at_ = (b == (uint8_t) words[0]) ? 1 : 0;
        return false;
    }
private:
    uint8_t at_;
};

// Sorts the bytes of a wire that carries display commands (text ended by FF FF FF) and, now and then, a
// frame. A display command never begins with A5, so at the start of a command that byte begins a frame.
// Nothing is lost to either side: the screen can knock, and listen for the answer, while the Teensy goes
// on driving its display.
class Router {
public:
    enum What { TO_DISPLAY = 0, FRAME_PART = 1, WHOLE_FRAME = 2 };   // (Arduino has macros called DISPLAY and the like)
    Router() : atStart_(true), inFrame_(false), ff_(0), last_(0) {}
    What push(uint8_t b, uint32_t nowMs, Frame &out) {
        // After a pause every byte starts afresh: a frame cut short must not eat what follows, and the tail of
        // a damaged frame (read as display bytes) must not hide the start of the next one.
        if (nowMs - last_ > LINK_GAP_MS) { if (inFrame_) parser_.reset(); inFrame_ = false; atStart_ = true; ff_ = 0; }
        last_ = nowMs;
        if (inFrame_) {
            if (parser_.push(b, out)) { inFrame_ = false; atStart_ = true; ff_ = 0; return WHOLE_FRAME; }
            if (!parser_.midFrame()) { inFrame_ = false; atStart_ = true; ff_ = 0; }      // not a frame after all, or damaged
            return FRAME_PART;
        }
        if (atStart_ && b == LINK_SOF0) { inFrame_ = true; parser_.reset(); parser_.push(b, out); return FRAME_PART; }
        if (b == 0xFF) { atStart_ = (++ff_ >= 3); if (atStart_) ff_ = 0; }
        else { ff_ = 0; atStart_ = false; }
        return TO_DISPLAY;
    }
    bool inFrame() const { return inFrame_; }
private:
    Parser parser_; bool atStart_, inFrame_; uint8_t ff_; uint32_t last_;
};

// A firmware package: this header, then the image exactly as it sits in the Teensy's flash from 0x60000000.
const size_t FW_HEADER_SIZE = 64;
#define LDRC_FW_MAGIC "LDRCFW01"
struct FwHeader {
    char magic[8];
    uint32_t size, crc;
    char version[32];
    char target[16];
};
bool fwHeaderParse(const uint8_t *raw, FwHeader &h);        // false unless the magic is right and the strings are terminated
void fwHeaderBuild(const FwHeader &h, uint8_t *raw);

// The pilot's own data on the Teensy's card: never replaced or deleted unless the request says so.
bool isUserData(const char *path);

// A path both ends accept: it begins with '/', has no empty part, no "..", none of \ : * ? " < > | and nothing
// below a space, and NO PART OF IT begins with a space or ends with a space or a dot. FAT drops those silently, so
// "/MODELS.DAT." would open the pilot's models.dat while it does not look like it to isUserData().
bool plainPath(const char *path);

}  // namespace ldrc
#endif
