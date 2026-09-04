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

`telemetry/msp_shared.c`:

```c
STATIC_UNIT_TESTED uint8_t responseBuffer[MSP_TLM_OUTBUF_SIZE];   // = MSP_PORT_OUTBUF_SIZE_MIN = 320
```

`MSP_ADJUSTMENT_RANGES` (52) writes `MAX_ADJUSTMENT_RANGE_COUNT (42) x 14 = 588 bytes` with
`sbufWriteU8/U16`, which never check `dst->end`. The 268 bytes past `responseBuffer` land on
whatever the linker placed after it — `telemetryConfig` is in that range, and the tail of the
adjustment table is zeros (unused slots), so the telemetry setup becomes all zero.

The same reply goes out fine over USB (`MSP_PORT_OUTBUF_SIZE` = 4112 there); only the
telemetry/CRSF path has the small buffer. `serializeDataflashReadReply` respects the buffer end;
the other reply builders do not.

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
