// RC serial input decoder — ported from LDRC2SIM (LDRC2SIM/src/rc_input.*)
// for the SIMULATOR INTERFACE role (0.9.757). Malcolm 2026-09-17: "All we
// need to do is add to the dongle a new option called 'Simulator interface'."
//
// Decodes ONE receiver signal wire into channel microseconds, auto-detecting
// CRSF / SBUS / IBUS / PPM. In this firmware it feeds simTx[] exactly where
// the radio would, so the existing USB joystick (SimUsb.h) needs no change.
//
// Runs ONLY in the simulator-interface role: a radio-less board, no flight
// controller, nothing on the output pin. It is never compiled into the
// flying path and update() is called from loop() only in that role.
//
// Folded into one header (RXV2 is a single translation unit).
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

// RC_SBUS_NI (0.9.766): SBUS framing on a NON-inverted line - some receivers
// offer it, and the LDRC RXV1's port sits that way until its transmitter
// connects (Binding.h StartSBUSandSERVOS), which is what the first bench test
// was listening to.
enum RcProtocol : uint8_t { RC_NONE = 0, RC_CRSF, RC_SBUS, RC_SBUS_NI, RC_IBUS, RC_PPM };

class RcInput {
public:
  static const uint8_t MAX_CH = 16;

  // rxPin: GPIO carrying the receiver signal. uart: HardwareSerial to use for
  // the serial protocols (PPM detaches it and uses a pin interrupt instead).
  void begin(int8_t rxPin, HardwareSerial* uart);
  bool update();                         // call often, non-blocking; true on a new frame

  bool        linkUp() const;            // locked AND a frame seen recently
  RcProtocol  protocol() const { return _proto; }
  const char* protocolName() const;
  uint8_t     channelCount() const { return _chCount; }
  uint16_t    channelUs(uint8_t i) const;  // microseconds; 1500 if absent
  bool        failsafe() const { return _failsafe; }
  uint32_t    bytesSeen() const;         // everything that ever arrived on the wire (bytes, or PPM edges)
  // Diagnostics (0.9.766): what each candidate saw, and the last bytes raw.
  uint8_t     candCount() const;
  const char* candName(uint8_t i) const;
  uint32_t    candBytes(uint8_t i) const  { return _candBytes[i]; }
  uint32_t    candFrames(uint8_t i) const { return _candFrames[i]; }
  void        rawHex(char* out, size_t cap) const;   // last 32 bytes, oldest first, "0F 00 .."

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
  uint32_t _bytes = 0;                    // serial bytes read, whatever they turned out to be
  uint32_t _candBytes[8]  = { 0 };        // per candidate index: bytes read while it was listening
  uint32_t _candFrames[8] = { 0 };        // per candidate index: valid frames it parsed
  uint8_t  _raw[32];                      // ring of the last bytes, whatever the candidate
  uint8_t  _rawIdx = 0;

  // parser scratch
  uint8_t  _buf[64];
  uint8_t  _idx = 0;
  uint8_t  _len = 0;
};

// ===================== implementation (inline) =====================

// ---- tunables ----------------------------------------------------------
inline constexpr uint32_t DETECT_WINDOW_MS = 350;  // listen per candidate
inline constexpr uint8_t  LOCK_HITS        = 3;    // valid frames needed to lock
inline constexpr uint32_t LINK_TIMEOUT_MS  = 500;  // no frame this long -> re-detect

// Detection order. CRSF first (most common today), PPM last (slowest to prove).
inline constexpr RcProtocol CANDIDATES[] = { RC_CRSF, RC_SBUS, RC_SBUS_NI, RC_IBUS, RC_PPM };
inline constexpr uint8_t NUM_CANDIDATES = sizeof(CANDIDATES) / sizeof(CANDIDATES[0]);

// ======================================================================
// PPM capture — file-scope so the pin ISR can reach it
// ======================================================================
static volatile uint16_t s_ppmRaw[RcInput::MAX_CH];
static volatile uint8_t  s_ppmIdx       = 0;
static volatile uint8_t  s_ppmCount     = 0;
static volatile uint32_t s_ppmLastEdge  = 0;
static volatile bool     s_ppmFrameReady = false;
static volatile uint32_t s_ppmEdges     = 0;   // diagnostics: edges seen while trying PPM

// NOT `inline`: an IRAM ISR in a header makes the linker place its literal
// pool after the use ("dangerous relocation"). One translation unit here.
static void IRAM_ATTR ppmIsr() {
  uint32_t now = micros();
  s_ppmEdges++;
  uint32_t d   = now - s_ppmLastEdge;
  s_ppmLastEdge = now;
  if (d > 3000) {                 // sync gap -> frame boundary
    s_ppmCount = s_ppmIdx;
    s_ppmIdx = 0;
    s_ppmFrameReady = true;
  } else if (s_ppmIdx < RcInput::MAX_CH) {
    if (d >= 700 && d <= 2300) {  // plausible channel period
      s_ppmRaw[s_ppmIdx++] = (uint16_t)d;
    } else {
      s_ppmIdx = 0;               // glitch -> resync
    }
  }
}

// Diagnostics for the dongle page (0.9.762). The first bench test (Malcolm,
// an SBUS receiver: "no evidence that it was" detected) had nothing to read
// back. Zero = a wiring or power problem; rising = a protocol one.
inline uint32_t RcInput::bytesSeen() const { return _bytes + s_ppmEdges; }
inline uint8_t  RcInput::candCount() const { return NUM_CANDIDATES; }
inline const char* RcInput::candName(uint8_t i) const {
  if (i >= NUM_CANDIDATES) return "?";
  switch (CANDIDATES[i]) {
    case RC_CRSF:    return "CRSF";
    case RC_SBUS:    return "SBUS";
    case RC_SBUS_NI: return "SBUS-NI";
    case RC_IBUS:    return "IBUS";
    case RC_PPM:     return "PPM";
    default:         return "?";
  }
}
inline void RcInput::rawHex(char* out, size_t cap) const {
  static const char* hx = "0123456789ABCDEF";
  size_t o = 0;
  const uint8_t n = (_bytes < 32) ? (uint8_t)_bytes : 32;
  for (uint8_t k = 0; k < n && o + 4 <= cap; k++) {
    const uint8_t b = _raw[(uint8_t)(_rawIdx - n + k) & 31];
    if (k) out[o++] = ' ';
    out[o++] = hx[b >> 4]; out[o++] = hx[b & 15];
  }
  out[o] = 0;
}

// ======================================================================
// Lifecycle
// ======================================================================
inline void RcInput::begin(int8_t rxPin, HardwareSerial* uart) {
  _rxPin = rxPin;
  _uart  = uart;
  for (uint8_t i = 0; i < MAX_CH; i++) _chUs[i] = 1500;
  _proto = RC_NONE;
  _locked = false;
  _cand = 0;
  useCandidate(_cand);
}

inline const char* RcInput::protocolName() const {
  switch (_proto) {
    case RC_CRSF:    return "CRSF";
    case RC_SBUS:    return "SBUS";
    case RC_SBUS_NI: return "SBUS (non-inverted)";
    case RC_IBUS:    return "IBUS";
    case RC_PPM:     return "PPM";
    default:         return "(searching)";
  }
}

inline bool RcInput::linkUp() const {
  return _locked && (millis() - _lastFrameMs) < LINK_TIMEOUT_MS;
}

inline uint16_t RcInput::channelUs(uint8_t i) const {
  return (i < _chCount) ? _chUs[i] : 1500;
}

// ======================================================================
// Candidate (re)configuration
// ======================================================================
inline void RcInput::useCandidate(uint8_t idx) {
  RcProtocol p = CANDIDATES[idx];
  _idx = 0; _len = 0;
  _candStartMs = millis();
  _candHits = 0;

  if (p == RC_PPM) {
    if (_uart) _uart->end();
    noInterrupts();
    s_ppmIdx = 0; s_ppmCount = 0; s_ppmFrameReady = false; s_ppmLastEdge = micros();
    interrupts();
    pinMode(_rxPin, INPUT);
    attachInterrupt(digitalPinToInterrupt(_rxPin), ppmIsr, RISING);
  } else {
    // UART protocols: rx-only on _rxPin, tx unused (-1).
    const bool sbus = (p == RC_SBUS) || (p == RC_SBUS_NI);
    uint32_t baud   = (p == RC_CRSF) ? 420000 : sbus ? 100000 : 115200;
    uint32_t config = sbus ? SERIAL_8E2 : SERIAL_8N1;
    bool     invert = (p == RC_SBUS);
    _uart->end();                    // clean reconfigure between candidates
    _uart->setRxBufferSize(1024);    // ~24ms headroom at 420 kbaud (call before begin)
    _uart->begin(baud, config, _rxPin, -1, invert);
  }
}

inline void RcInput::leaveCandidate() {
  if (CANDIDATES[_cand] == RC_PPM) {
    detachInterrupt(digitalPinToInterrupt(_rxPin));
  }
}

// ======================================================================
// Main pump
// ======================================================================
inline bool RcInput::update() {
  bool gotFrame = false;
  if (CANDIDATES[_cand] == RC_PPM) gotFrame = pollPpm();
  else                             gotFrame = feedSerial();

  if (gotFrame) {
    _lastFrameMs = millis();
    _candFrames[_cand]++;
    if (!_locked) {
      if (++_candHits >= LOCK_HITS) {
        _locked = true;
        _proto  = CANDIDATES[_cand];
      }
    }
    return true;
  }

  if (_locked) {
    // Lost the link? Drop back to searching from this protocol.
    if (millis() - _lastFrameMs > LINK_TIMEOUT_MS) {
      _locked = false;
      _proto  = RC_NONE;
      _candStartMs = millis();
      _candHits = 0;
    }
    return false;
  }

  // Still searching: rotate to the next candidate after the listen window.
  if (millis() - _candStartMs > DETECT_WINDOW_MS) {
    leaveCandidate();
    _cand = (_cand + 1) % NUM_CANDIDATES;
    useCandidate(_cand);
  }
  return false;
}

// ======================================================================
// Serial pumping
// ======================================================================
inline bool RcInput::feedSerial() {
  bool frame = false;
  if (!_uart) return false;
  // Bound the work per call so loop() stays responsive at high baud.
  for (int n = 0; n < 64 && _uart->available(); n++) {
    uint8_t b = (uint8_t)_uart->read();
    _bytes++;
    _candBytes[_cand]++;
    _raw[_rawIdx++ & 31] = b;
    switch (CANDIDATES[_cand]) {
      case RC_CRSF:    frame |= crsfByte(b); break;
      case RC_SBUS:
      case RC_SBUS_NI: frame |= sbusByte(b); break;
      case RC_IBUS:    frame |= ibusByte(b); break;
      default: break;
    }
  }
  return frame;
}

inline bool RcInput::pollPpm() {
  if (!s_ppmFrameReady) return false;
  noInterrupts();
  s_ppmFrameReady = false;
  uint8_t n = s_ppmCount;
  uint16_t tmp[MAX_CH];
  for (uint8_t i = 0; i < MAX_CH; i++) tmp[i] = s_ppmRaw[i];
  interrupts();

  if (n < 4 || n > MAX_CH) return false;   // implausible -> not PPM (yet)
  _chCount = n;
  for (uint8_t i = 0; i < n; i++) _chUs[i] = tmp[i];   // already microseconds
  _failsafe = false;
  return true;
}

// ======================================================================
// Channel bit unpacking (CRSF and SBUS share the 16x 11-bit layout)
// ======================================================================
inline void RcInput::store11(const uint8_t* p, uint16_t* out16) {
  uint32_t bits = 0; uint8_t avail = 0, bi = 0;
  for (uint8_t ch = 0; ch < 16; ch++) {
    while (avail < 11) { bits |= (uint32_t)p[bi++] << avail; avail += 8; }
    out16[ch] = bits & 0x7FF;
    bits >>= 11; avail -= 11;
  }
}

inline uint16_t RcInput::crsfRawToUs(uint16_t raw) {
  // CRSF/SBUS 11-bit: 172 -> 988us, 992 -> 1500us, 1811 -> 2012us
  int32_t us = ((int32_t)raw - 992) * 5 / 8 + 1500;
  if (us < 880)  us = 880;
  if (us > 2120) us = 2120;
  return (uint16_t)us;
}

// ======================================================================
// CRSF: [addr][len][type][payload...][crc8]   RC channels type 0x16
// ======================================================================
static uint8_t crc8_dvb_s2(const uint8_t* d, uint8_t len) {
  uint8_t crc = 0;
  for (uint8_t i = 0; i < len; i++) {
    crc ^= d[i];
    for (uint8_t b = 0; b < 8; b++)
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
  }
  return crc;
}

inline bool RcInput::crsfByte(uint8_t b) {
  if (_idx == 0) {                       // address byte
    if (b == 0xC8 || b == 0xEE || b == 0xEC) _buf[_idx++] = b;
    return false;
  }
  if (_idx == 1) {                       // length (type+payload+crc)
    if (b < 2 || b > 62) { _idx = 0; return false; }
    _len = b; _buf[_idx++] = b; return false;
  }
  _buf[_idx++] = b;
  if (_idx == (uint8_t)(2 + _len)) {     // full frame
    uint8_t got = _idx; _idx = 0;
    uint8_t crc = crc8_dvb_s2(&_buf[2], (uint8_t)(_len - 1));  // type+payload
    if (crc != _buf[got - 1]) return false;
    if (_buf[2] == 0x16) {               // RC channels packed
      uint16_t raw[16];
      store11(&_buf[3], raw);
      for (uint8_t i = 0; i < 16; i++) _chUs[i] = crsfRawToUs(raw[i]);
      _chCount = 16; _failsafe = false;
      return true;
    }
  }
  return false;
}

// ======================================================================
// SBUS: 25 bytes, 0x0F start; 22B of 16x 11-bit; byte23 flags; byte24 footer
// ======================================================================
inline bool RcInput::sbusByte(uint8_t b) {
  if (_idx == 0) {
    if (b == 0x0F) _buf[_idx++] = b;
    return false;
  }
  _buf[_idx++] = b;
  if (_idx == 25) {
    _idx = 0;
    uint8_t footer = _buf[24];
    // Accept common end bytes; rejects most mis-syncs on data 0x0F.
    if (footer != 0x00 && footer != 0x04 && footer != 0x14 &&
        footer != 0x24 && footer != 0x34 && footer != 0x08) return false;
    uint16_t raw[16];
    store11(&_buf[1], raw);
    for (uint8_t i = 0; i < 16; i++) _chUs[i] = crsfRawToUs(raw[i]);
    _chCount  = 16;
    _failsafe = (_buf[23] & 0x08) != 0;       // bit3 = failsafe
    return true;
  }
  return false;
}

// ======================================================================
// IBUS: 32 bytes, 0x20 0x40 header; 14x 2-byte LE us; 2-byte LE checksum
// ======================================================================
inline bool RcInput::ibusByte(uint8_t b) {
  if (_idx == 0) { if (b == 0x20) _buf[_idx++] = b; return false; }
  if (_idx == 1) { if (b == 0x40) _buf[_idx++] = b; else _idx = 0; return false; }
  _buf[_idx++] = b;
  if (_idx == 32) {
    _idx = 0;
    uint16_t sum = 0;
    for (uint8_t i = 0; i < 30; i++) sum += _buf[i];
    uint16_t chk = (uint16_t)(0xFFFF - sum);
    uint16_t rx  = (uint16_t)(_buf[30] | (_buf[31] << 8));
    if (chk != rx) return false;
    for (uint8_t i = 0; i < 14; i++)
      _chUs[i] = (uint16_t)(_buf[2 + i * 2] | (_buf[3 + i * 2] << 8));
    _chCount = 14; _failsafe = false;
    return true;
  }
  return false;
}

// The one instance, used only in the simulator-interface role.
inline RcInput g_rcIn;
// Wire finder results (0.9.767): level changes seen in 40 ms on D4, D5, D6
// while nothing is recognised - filled in main.cpp, shown on the dongle page.
inline uint32_t simIfEdges[3] = { 0, 0, 0 };
inline bool     simIfFloat[3] = { false, false, false };   // 0.9.772: true = nothing is connected to that pad
