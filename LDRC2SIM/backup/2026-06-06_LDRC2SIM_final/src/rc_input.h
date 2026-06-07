// LDRC SimRX — RC serial input decoder
// ------------------------------------------------------------------
// Decodes a single receiver signal wire into channel values, auto-detecting
// the protocol. Supports:
//   CRSF  (ELRS / TBS Crossfire)  420000 baud, 8N1, non-inverted, CRC8
//   SBUS  (FrSky / Futaba)        100000 baud, 8E2, INVERTED, 25-byte frame
//   IBUS  (FlySky)                115200 baud, 8N1, 32-byte frame, checksum
//   PPM   (CPPM pulse train)      GPIO edge timing, sync gap > 3 ms
//
// All four share one input pin. update() cycles through the protocols until
// one produces valid frames, then locks on. Channel values are exposed in
// microseconds (~988..2012, centre 1500) regardless of source protocol.

#pragma once
#include <Arduino.h>

enum RcProtocol : uint8_t { RC_NONE = 0, RC_CRSF, RC_SBUS, RC_IBUS, RC_PPM };

class RcInput {
public:
  static const uint8_t MAX_CH = 16;

  // rxPin: GPIO carrying the receiver signal. uart: HardwareSerial to use for
  // the serial protocols (PPM detaches it and uses a pin interrupt instead).
  void begin(int8_t rxPin, HardwareSerial* uart);
  void update();                         // call often, non-blocking

  bool        linkUp() const;            // locked AND a frame seen recently
  RcProtocol  protocol() const { return _proto; }
  const char* protocolName() const;
  uint8_t     channelCount() const { return _chCount; }
  uint16_t    channelUs(uint8_t i) const;  // microseconds; 1500 if absent
  bool        failsafe() const { return _failsafe; }

private:
  // ---- detection / lock ----
  void useCandidate(uint8_t idx);        // configure UART/ISR for candidate
  void leaveCandidate();                 // release UART/ISR
  bool feedSerial();                     // pump bytes into the active parser
  bool pollPpm();                        // check PPM ISR state for a frame

  // ---- parsers (return true on a complete, valid frame) ----
  bool crsfByte(uint8_t b);
  bool sbusByte(uint8_t b);
  bool ibusByte(uint8_t b);

  static void store11(const uint8_t* p, uint16_t* out16);  // 22B -> 16x 11-bit
  static uint16_t crsfRawToUs(uint16_t raw);               // 11-bit -> us

  HardwareSerial* _uart = nullptr;
  int8_t   _rxPin   = -1;
  RcProtocol _proto = RC_NONE;           // locked protocol (RC_NONE = searching)
  uint8_t  _cand    = 0;                  // candidate index while detecting
  bool     _locked  = false;
  uint32_t _candStartMs = 0;
  uint8_t  _candHits = 0;

  uint16_t _chUs[MAX_CH];
  uint8_t  _chCount = 0;
  uint32_t _lastFrameMs = 0;
  bool     _failsafe = false;

  // parser scratch
  uint8_t  _buf[64];
  uint8_t  _idx = 0;
  uint8_t  _len = 0;
};
