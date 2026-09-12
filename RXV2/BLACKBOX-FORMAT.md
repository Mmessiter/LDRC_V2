# Rotorflight 4.6 black box: the log format, as read by the receiver

Source of truth: `rotorflight-firmware` branch RF-4.6.x, `src/main/blackbox/blackbox.c`,
`blackbox_encoding.c`, `blackbox_fielddefs.h`, `src/main/msp/msp.c` (read 2026-09-12).
The receiver decodes this on the fly (`src/BlackboxDecode.h`) while pulling the flash
over USB (`src/BlackboxCheck.h`); the page `rotorflight-filtercheck.html` turns the
spectra into filter advice. Host test: `dev/bbcheck_test.sh` (synthetic log from
`dev/bb_synth.py`, which mirrors the encoders byte for byte).

## Getting the bytes (MSP, over USB only)

* **70 DATAFLASH_SUMMARY** reply 13 B: u8 flags (1 supported, 2 ready), u32 sectors,
  u32 total bytes, u32 used bytes (`flashfsGetOffset`, the write head).
* **71 DATAFLASH_READ** request 7 B: u32 address, u16 size, u8 allowCompression (0).
  Reply: u32 address, u16 bytes actually read, u8 compression (0), data. Size is clipped
  to the FC's reply buffer minus 16 (4096 over USB, ~300 over CRSF) and to the end of
  the volume. A 6-byte request would get the legacy 128-byte format; we never send that.
* **72** erase (async, poll 70 until ready + used 0). **80/81** recorder config
  (u8 supported, u8 device, u8 mode, u16 denom, u32 fields, u16 initialEraseKiB,
  u8 rollingErase, u8 gracePeriod).
* Consecutive logs sit back to back; `flashfsClose` pads to a page boundary with 0xFF.
  Erased flash is 0xFF. With rolling erase ON the volume can wrap, so the first bytes
  may be the tail of an older log; the decoder simply waits for the next header.

## One log

```
H Product:Blackbox flight data recorder by Nicholas Sherlock
H Data version:2
H I interval:<n>            I frame every n iterations (<= 64 P frames, <= 32 ms)
H P interval:<denom>        P frame every denom PID iterations (blackbox_denom)
H Field I name:loopIteration,time,gyroRAW[0],...   (only the ENABLED fields appear)
H Field I signed:0,0,1,...
H Field I predictor:0,0,0,...
H Field I encoding:1,1,0,...
H Field P predictor:6,2,3,...
H Field P encoding:9,0,0,...
H Field S name:flightModeFlags,stateFlags,failsafePhase,rxSignalReceived,rxFlightChannelsValid
H Field S signed / predictor / encoding
H Field G name / H Field H name ...   only with GPS
H Firmware type:Rotorflight     H Firmware revision:...   H Craft name:...   H Log start datetime:...
H looptime:<us>  (gyro.sampleLooptime - NOT the log rate; measure the rate from `time`)
H gyro_scale:0x3f800000 (1.0: gyroRAW/gyroADC are lrintf(deg/s))   H vbatref:<n>   H minthrottle:<n>
H fields_mask:<n>  H gyro_rpm_notch_preset:<n>  H gyro_notch_hz:<a>,<b>  ... (many more)
```
Then frames until `E 255 "End of log\0"`, or an abrupt stop (power cut).

### Frame types
* `I` intra: every field per its I predictor/encoding; history[1]=history[2]=this.
* `P` inter: every field per its P predictor/encoding, from history[1] (previous) and
  history[2] (the one before). `loopIteration` is NULL-encoded (predictor INC:
  previous + P interval). `time` is LINEAR (2*prev1 - prev2 + delta).
* `S` slow: flightModeFlags UVB, stateFlags UVB, then failsafePhase/rxSignalReceived/
  rxFlightChannelsValid as one TAG2_3S32 group.
* `E` event: u8 id then per id: 0 SYNC_BEEP UVB; 13 INFLIGHT_ADJUSTMENT u8 fn (+float32
  if fn&128 else SVB); 14 LOGGING_RESUME UVB,UVB; 15 DISARM UVB; 30 FLIGHTMODE UVB,UVB;
  50 GOVSTATE UVB; 51 RESCUE UVB; 52 AIRBORNE UVB; 100 CUSTOM_DATA u8 len + bytes;
  101 CUSTOM_STRING u8 len + chars; 255 LOG_END "End of log" + 0x00.
* `G` / `H` GPS frames only when the G/H headers exist.

### Field order (RF 4.6 `blackboxMainFields`, each present only if its condition holds)
loopIteration, time, rcCommand[0..3] (P: TAG8_4S16 group), rcCommand[4] throttle (P: SVB),
setpoint[0..3] (TAG8_4S16), mixer[0..3] (TAG8_4S16), axisP/I/D/F[0..2] (TAG2_3S32 groups),
axisB[0..2], axisO[0..2] (TAG2_3S32), attitude[0..2] (TAG2_3S32),
gyroRAW[0..2], gyroADC[0..2], accADC[0..2] (P: AVERAGE_2 + SVB),
magADC[0..2], altitude, vario, rssi (P: one TAG8_8SVB group of the consecutive ones),
Vbat (I: NEG_14BIT + VBATREF), Ibat, Vbec, Vbus, EscV/I/Cap/RPM/Thr/Pwm, BecV/I,
Esc2V/I/Cap/RPM (P: PREVIOUS + SVB), Tmcu, Tesc, Tbec, Tesc2 (P: TAG8_8SVB group),
govP/I/D/F (TAG8_4S16), govSum, govTarget, govRequest (SVB),
headspeed, tailspeed (P: AVERAGE_2 + SVB), motor[0..3] (AVERAGE_2), servo[0..7]
(I: predictor 1500; P: AVERAGE_2), debug[0..7] (PREVIOUS + SVB).

### Predictors (decoder side)
0 none | 1 PREVIOUS +prev1 | 2 LINEAR +2*prev1-prev2 | 3 AVERAGE_2 +trunc((prev1+prev2)/2)
| 4 MINTHROTTLE | 5 MOTOR_0 +motor[0] | 6 INC prev1 + P interval | 7 HOME_COORD | 8 +1500
| 9 +vbatref | 10 +last main frame time | 11 MINMOTOR (0).

### Encodings (decoder side)
0 SIGNED_VB zigzag(UVB) | 1 UNSIGNED_VB (7 bits per byte, low first, 0x80 = more)
| 3 NEG_14BIT -signExtend14(UVB) | 6 TAG8_8SVB: consecutive fields with this encoding
form one group (<= 8); a group of ONE is a bare SVB; otherwise a header byte (bit i =
field i non-zero) then an SVB per set bit | 7 TAG2_3S32: group of 3; selector = byte>>6:
0 = three 2-bit values in the same byte (bits 5-4, 3-2, 1-0), 1 = 4-bit: v0 = byte&15,
next byte hi nibble v1, lo nibble v2, 2 = v0 = byte&63 (6-bit), v1, v2 one int8 each,
3 = byte&63 is a per-field byte-count selector (2 bits each, 1..4 bytes little-endian,
sign-extended) | 8 TAG8_4S16: group of 4, selector byte (2 bits per field: 0 zero, 1
nibble, 2 byte, 3 two bytes high first) then a nibble stream exactly as
`blackboxWriteTag8_4S16` writes it | 9 NULL nothing | 10 TAG2_3SVARIABLE (unused by 4.6).
All small fields are two's-complement sign-extended.

### Rates
Iterations run at the PID rate (gyro.targetRateHz, 4 kHz on a Nexus-X); a P frame every
`denom` iterations, so "1 in 2" = 2000 samples/s. The decoder measures the rate from the
`time` field (median delta) and ignores `looptime`.
