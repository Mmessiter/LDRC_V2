# Rotorflight 4.6: MSP_ADJUSTMENT_RANGES over CRSF overflows the reply buffer and wipes the telemetry setup

Found on the Goblin 770 (Nexus X, Rotorflight 2.3 / firmware 4.6.0, API 12.9), 2026-09-04.
Receiver: LDRC RXV2 (ESP32-S3) speaking CRSF at 420 kbaud, MSP over CRSF (frame types 0x7A/0x7B)
as a handset (origin 0xEA).

## Symptom

After a session on the phone the transmitter showed **no volts and no RPM** at the next power-up.
`MSP_TELEMETRY_CONFIG` (73) read back **all zero**: inverted 0, halfDuplex 0, pinSwap 0, mode 0,
link rate 0, ratio 0, all 40 sensor slots 0. The defaults (`PG_RESET_TEMPLATE`: halfDuplex 1,
rate 250, ratio 8) can never produce that image, so it was not a reset — the struct was overwritten.

While it is only in RAM nothing changes (crsf.c builds the native schedule and the rate limiter in
`initCrsfTelemetry`, called once from `telemetryInit` at boot); the next `MSP_EEPROM_WRITE` carries
it into flash and the FC boots mute.

## Cause

All references are to tag `release/4.6.0` (checked 2026-09-04):

- `src/main/telemetry/msp_shared.c:125` — `STATIC_UNIT_TESTED uint8_t responseBuffer[MSP_TLM_OUTBUF_SIZE];`
- `src/main/telemetry/msp_shared.h:26` — `#define MSP_TLM_OUTBUF_SIZE MSP_PORT_OUTBUF_SIZE_MIN`
- `src/main/msp/msp_serial.h:71` — `#define MSP_PORT_OUTBUF_SIZE_MIN 320`
- `src/main/msp/msp.c:1492-1508` — `case MSP_ADJUSTMENT_RANGES:` loops `MAX_ADJUSTMENT_RANGE_COUNT` times
  writing 9 × U8 + 2 × U16 + U8 = 14 bytes per entry
- `src/main/pg/adjustments.h:41` — `#define MAX_ADJUSTMENT_RANGE_COUNT 42` → 588 bytes
- `src/main/common/streambuf.c:34-46` — `#define SBUFPUSH(dst, val) ((*(dst)->ptr++ = (val)))`;
  `sbufWriteU8/U16` push without looking at `dst->end`

`processMspPacket` (`msp_shared.c:149-153`) sets `responsePacket.buf.end = ARRAYEND(responseBuffer)`
and calls `mspFcProcessCommand`; the reply builder never consults `end`, so the 268 bytes past
`responseBuffer` land on whatever the linker placed after it — `telemetryConfig` is in that range,
and the tail of the adjustment table is zeros (unused slots), so the telemetry setup becomes all zero.

The same reply goes out fine over USB (`MSP_PORT_OUTBUF_SIZE` = dataflash buffer + info, 4112
bytes, `msp_serial.h:76`); only the telemetry/CRSF path has the 320-byte buffer, which was sized
for MSP_BOXNAMES (`msp_serial.h:78` comment). `serializeDataflashReadReply` respects the buffer
end; the other reply builders do not. Any other reply over 320 bytes would do the same — on this
model every other function the receiver or its apps use answers in ≤ 258 bytes.

The path is the generic telemetry MSP path (`msp_shared.c`), shared by every CRSF/ELRS handset
script that talks MSP over the link — any such script requesting `MSP_ADJUSTMENT_RANGES` should
see the same overwrite (not verified here; this receiver was the requester).

## Reproduction (bench, blades off)

1. Reboot the FC (`MSP_REBOOT`, 68). Read 73 → good (e.g. `00 01 00 00 00 00 00 00 E8 03 01 00 59 02 6C 6D 40 3A 48 …`).
2. Read 120 (65 B), 34 (80 B), 172 (224 B) → 73 still good.
3. Read 52 (588 B) → 73 is **all zero**. Every time.

Timing on this heli: reply to 52 takes ~300 ms at link rate 1000/1 (11 CRSF chunks).

## Suggested fix (firmware)

Either bounds-check in `mspFcProcessOutCommand` for the telemetry descriptor (return
`MSP_RESULT_ERROR` when `sbufBytesRemaining(dst)` is too small before building a reply), or make
`sbufWriteU8/U16/U32` stop at `end`, or raise `MSP_TLM_OUTBUF_SIZE` to cover the largest reply.
A cheap check: `if (sbufBytesRemaining(dst) < MAX_ADJUSTMENT_RANGE_COUNT * 14) return MSP_RESULT_ERROR;`
in `case MSP_ADJUSTMENT_RANGES`.

## Receiver-side workaround (RXV2 0.9.564)

- MSP 52 is never sent to the FC; the receiver's API refuses it with the reason.
- Any reply larger than 320 bytes is logged as "FC memory overwritten", the telemetry setup is
  re-read at once and the cached good image put back in RAM before any save.
- The receiver keeps a copy of the last good telemetry setup (NVS) and restores it on request.
