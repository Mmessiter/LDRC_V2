// LockDownRadioControl — RXV2  ::  MspSerialCore.h
//
// Plain MSP v1 over a UART, for DONGLE MODE (Malcolm 2026-09-08): a bare
// XIAO ESP32-S3 on a spare Rotorflight UART set to MSP, so the phone app
// works with ANY receiver flying the model. No Arduino here on purpose —
// this file is compiled on the Mac by dev/msp_serial_test.cpp as well.
//
// Frame (Rotorflight msp_serial.c): '$' 'M' dir size cmd payload crc.
//   dir  '<' request, '>' reply, '!' error reply
//   size u8; 255 = JUMBO: a u16 little-endian size follows, then cmd
//   crc  XOR of every byte after "$M<" up to and including the payload
#ifndef _SRC_MSPSERIALCORE_H
#define _SRC_MSPSERIALCORE_H
#include <stdint.h>
#include <string.h>

constexpr uint16_t MSP_SERIAL_MAX_PAYLOAD = 640;    // the FC's biggest reply we accept (jumbo)

// Build a request frame into `out`; returns the frame length, 0 if it does not fit.
inline uint16_t mspSerialEncode(uint8_t* out, uint16_t outMax, uint8_t fn, const uint8_t* payload, uint16_t len) {
    const bool jumbo = len >= 255;
    const uint16_t need = 3 + 1 + (jumbo ? 2 : 0) + 1 + len + 1;
    if (need > outMax) return 0;
    uint16_t n = 0;
    out[n++] = '$'; out[n++] = 'M'; out[n++] = '<';
    uint8_t crc = 0;
    auto put = [&](uint8_t b) { out[n++] = b; crc ^= b; };
    if (jumbo) { put(255); put(fn); put((uint8_t)len); put((uint8_t)(len >> 8)); }   // RF/BF order: 255, cmd, u16 length
    else       { put((uint8_t)len); put(fn); }
    for (uint16_t i = 0; i < len; i++) put(payload[i]);
    out[n++] = crc;
    return n;
}

// Byte-at-a-time decoder for what the FC sends back.
struct MspSerialParser {
    enum State : uint8_t { S_IDLE, S_M, S_DIR, S_SIZE, S_JCMD, S_JLO, S_JHI, S_CMD, S_DATA, S_CRC };
    State    state = S_IDLE;
    bool     error = false;
    uint16_t size  = 0, got = 0;
    uint8_t  cmd   = 0, crc = 0;
    uint8_t  buf[MSP_SERIAL_MAX_PAYLOAD];
    uint32_t frames = 0, badCrc = 0, dropped = 0;

    typedef void (*Handler)(void* ctx, uint8_t cmd, const uint8_t* payload, uint16_t len, bool isError);

    void reset() { state = S_IDLE; size = got = 0; crc = 0; }

    void feed(uint8_t b, Handler onFrame, void* ctx) {
        switch (state) {
            case S_IDLE: if (b == '$') state = S_M; break;
            case S_M:    state = (b == 'M') ? S_DIR : S_IDLE; break;
            case S_DIR:
                if (b == '>' || b == '!') { error = (b == '!'); crc = 0; state = S_SIZE; }
                else state = S_IDLE;                       // '<' is a request echo we never expect
                break;
            case S_SIZE:
                crc ^= b;
                if (b == 255) { state = S_JCMD; }                    // jumbo: cmd next, then the u16 length
                else { size = b; state = S_CMD; }
                break;
            case S_JCMD: crc ^= b; cmd = b; state = S_JLO; break;
            case S_JLO:  crc ^= b; size = b; state = S_JHI; break;
            case S_JHI:  crc ^= b; size |= (uint16_t)b << 8; got = 0;
                if (size > MSP_SERIAL_MAX_PAYLOAD) { dropped++; reset(); }
                else state = size ? S_DATA : S_CRC;
                break;
            case S_CMD:  crc ^= b; cmd = b; got = 0; state = size ? S_DATA : S_CRC; break;
            case S_DATA:
                crc ^= b;
                if (got < MSP_SERIAL_MAX_PAYLOAD) buf[got] = b;
                got++;
                if (got >= size) state = S_CRC;
                break;
            case S_CRC:
                if (b == crc) { frames++; if (onFrame) onFrame(ctx, cmd, buf, size, error); }
                else badCrc++;
                reset();
                break;
        }
    }
};
#endif // _SRC_MSPSERIALCORE_H
