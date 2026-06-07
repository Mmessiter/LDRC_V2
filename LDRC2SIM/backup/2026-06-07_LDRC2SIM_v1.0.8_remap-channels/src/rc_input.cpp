#include "rc_input.h"

// ---- tunables ----------------------------------------------------------
static const uint32_t DETECT_WINDOW_MS = 350;  // listen per candidate
static const uint8_t  LOCK_HITS        = 3;    // valid frames needed to lock
static const uint32_t LINK_TIMEOUT_MS  = 500;  // no frame this long -> re-detect

// Detection order. CRSF first (most common today), PPM last (slowest to prove).
static const RcProtocol CANDIDATES[] = { RC_CRSF, RC_SBUS, RC_IBUS, RC_PPM };
static const uint8_t NUM_CANDIDATES = sizeof(CANDIDATES) / sizeof(CANDIDATES[0]);

// ======================================================================
// PPM capture — file-scope so the pin ISR can reach it
// ======================================================================
static volatile uint16_t s_ppmRaw[RcInput::MAX_CH];
static volatile uint8_t  s_ppmIdx       = 0;
static volatile uint8_t  s_ppmCount     = 0;
static volatile uint32_t s_ppmLastEdge  = 0;
static volatile bool     s_ppmFrameReady = false;

static void IRAM_ATTR ppmIsr() {
  uint32_t now = micros();
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

// ======================================================================
// Lifecycle
// ======================================================================
void RcInput::begin(int8_t rxPin, HardwareSerial* uart) {
  _rxPin = rxPin;
  _uart  = uart;
  for (uint8_t i = 0; i < MAX_CH; i++) _chUs[i] = 1500;
  _proto = RC_NONE;
  _locked = false;
  _cand = 0;
  useCandidate(_cand);
}

const char* RcInput::protocolName() const {
  switch (_proto) {
    case RC_CRSF: return "CRSF";
    case RC_SBUS: return "SBUS";
    case RC_IBUS: return "IBUS";
    case RC_PPM:  return "PPM";
    default:      return "(searching)";
  }
}

bool RcInput::linkUp() const {
  return _locked && (millis() - _lastFrameMs) < LINK_TIMEOUT_MS;
}

uint16_t RcInput::channelUs(uint8_t i) const {
  return (i < _chCount) ? _chUs[i] : 1500;
}

// ======================================================================
// Candidate (re)configuration
// ======================================================================
void RcInput::useCandidate(uint8_t idx) {
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
    uint32_t baud   = (p == RC_CRSF) ? 420000 : (p == RC_SBUS) ? 100000 : 115200;
    uint32_t config = (p == RC_SBUS) ? SERIAL_8E2 : SERIAL_8N1;
    bool     invert = (p == RC_SBUS);
    _uart->end();                    // clean reconfigure between candidates
    _uart->setRxBufferSize(512);     // headroom at 420 kbaud (call before begin)
    _uart->begin(baud, config, _rxPin, -1, invert);
  }
}

void RcInput::leaveCandidate() {
  if (CANDIDATES[_cand] == RC_PPM) {
    detachInterrupt(digitalPinToInterrupt(_rxPin));
  }
}

// ======================================================================
// Main pump
// ======================================================================
void RcInput::update() {
  bool gotFrame = false;
  if (CANDIDATES[_cand] == RC_PPM) gotFrame = pollPpm();
  else                             gotFrame = feedSerial();

  if (gotFrame) {
    _lastFrameMs = millis();
    if (!_locked) {
      if (++_candHits >= LOCK_HITS) {
        _locked = true;
        _proto  = CANDIDATES[_cand];
      }
    }
    return;
  }

  if (_locked) {
    // Lost the link? Drop back to searching from this protocol.
    if (millis() - _lastFrameMs > LINK_TIMEOUT_MS) {
      _locked = false;
      _proto  = RC_NONE;
      _candStartMs = millis();
      _candHits = 0;
    }
    return;
  }

  // Still searching: rotate to the next candidate after the listen window.
  if (millis() - _candStartMs > DETECT_WINDOW_MS) {
    leaveCandidate();
    _cand = (_cand + 1) % NUM_CANDIDATES;
    useCandidate(_cand);
  }
}

// ======================================================================
// Serial pumping
// ======================================================================
bool RcInput::feedSerial() {
  bool frame = false;
  if (!_uart) return false;
  // Bound the work per call so loop() stays responsive at high baud.
  for (int n = 0; n < 64 && _uart->available(); n++) {
    uint8_t b = (uint8_t)_uart->read();
    switch (CANDIDATES[_cand]) {
      case RC_CRSF: frame |= crsfByte(b); break;
      case RC_SBUS: frame |= sbusByte(b); break;
      case RC_IBUS: frame |= ibusByte(b); break;
      default: break;
    }
  }
  return frame;
}

bool RcInput::pollPpm() {
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
void RcInput::store11(const uint8_t* p, uint16_t* out16) {
  uint32_t bits = 0; uint8_t avail = 0, bi = 0;
  for (uint8_t ch = 0; ch < 16; ch++) {
    while (avail < 11) { bits |= (uint32_t)p[bi++] << avail; avail += 8; }
    out16[ch] = bits & 0x7FF;
    bits >>= 11; avail -= 11;
  }
}

uint16_t RcInput::crsfRawToUs(uint16_t raw) {
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

bool RcInput::crsfByte(uint8_t b) {
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
bool RcInput::sbusByte(uint8_t b) {
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
bool RcInput::ibusByte(uint8_t b) {
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
