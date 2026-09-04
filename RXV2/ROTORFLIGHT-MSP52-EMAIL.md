Subject: Rotorflight 4.6 — MSP_ADJUSTMENT_RANGES over CRSF overflows the telemetry reply buffer and wipes the telemetry setup

Hi [name],

I hope you're well. I've found what looks like a genuine bug in Rotorflight 4.6 while developing my own receiver (LDRC RXV2 — an ESP32-S3 talking CRSF to a Nexus X, with MSP over CRSF for a phone configurator). Would you mind passing this on to the Rotorflight team? I'm happy to file it on GitHub instead if they'd prefer — just say.

SUMMARY

Requesting MSP_ADJUSTMENT_RANGES (52) over the CRSF/telemetry MSP path makes the FC write a 588-byte reply into a 320-byte buffer. The overflow lands on telemetryConfig, which ends up all zero — sensors, rate, ratio, half-duplex, everything. Nothing is visible until the next EEPROM save; after that the FC boots with telemetry mute (no volts, no RPM at the transmitter). Over USB it is fine, because the serial MSP path has a 4112-byte buffer.

WHAT I SAW

Goblin 770, Nexus X, Rotorflight 2.3 / firmware 4.6.0 (API 12.9), CRSF at 420 kbaud, receiver as handset (origin 0xEA). After a phone session the transmitter showed no volts and no RPM. MSP_TELEMETRY_CONFIG (73) read back all zero: inverted 0, halfDuplex 0, pinSwap 0, mode 0, rate 0, ratio 0, all 40 sensor slots 0. The defaults (halfDuplex 1, rate 250, ratio 8) can never produce that image, so it was not a reset — the struct had been overwritten.

WHERE (tag release/4.6.0)

- src/main/telemetry/msp_shared.c:125 — uint8_t responseBuffer[MSP_TLM_OUTBUF_SIZE];
- src/main/telemetry/msp_shared.h:26 — #define MSP_TLM_OUTBUF_SIZE MSP_PORT_OUTBUF_SIZE_MIN
- src/main/msp/msp_serial.h:71 — #define MSP_PORT_OUTBUF_SIZE_MIN 320
- src/main/msp/msp.c:1492-1508 — case MSP_ADJUSTMENT_RANGES: writes 14 bytes per entry (9 × U8 + 2 × U16 + U8)
- src/main/pg/adjustments.h:41 — #define MAX_ADJUSTMENT_RANGE_COUNT 42 → 588 bytes
- src/main/common/streambuf.c:34-46 — SBUFPUSH / sbufWriteU8 / sbufWriteU16 push without looking at dst->end

processMspPacket (msp_shared.c:150-153) sets responsePacket.buf.end = ARRAYEND(responseBuffer) and calls mspFcProcessCommand, but the reply builders never consult end, so the 268 bytes past responseBuffer land on whatever the linker placed after it — on this build evidently telemetryConfig. The tail of the adjustment table is unused slots (zeros), which is why the telemetry setup becomes all zero rather than garbage. Any other reply over 320 bytes would do the same; every other function my receiver uses answers in 258 bytes or less. The path is the generic telemetry MSP path, shared by every CRSF/ELRS handset script that talks MSP over the link, so a Lua script asking for 52 should see the same — not verified, my receiver was the requester here.

REPRODUCTION (bench, blades off)

1. Reboot the FC (MSP_REBOOT, 68). Read 73 → good (e.g. 00 01 00 00 00 00 00 00 E8 03 01 00 59 02 6C 6D 40 3A 48 …).
2. Read 120 (65 B), 34 (80 B), 172 (224 B) → 73 still good.
3. Read 52 (588 B) → 73 is all zero. Every time.

The reply to 52 takes about 300 ms at link rate 1000/1 (11 CRSF chunks).

POSSIBLE FIX

Any one of: a bounds check before building the reply for the telemetry descriptor (return MSP_RESULT_ERROR when sbufBytesRemaining(dst) is too small); make sbufWriteU8/U16/U32 stop at end; or raise MSP_TLM_OUTBUF_SIZE to cover the largest reply. The cheapest: if (sbufBytesRemaining(dst) < MAX_ADJUSTMENT_RANGE_COUNT * 14) return MSP_RESULT_ERROR; at the top of case MSP_ADJUSTMENT_RANGES.

On my side the receiver now refuses to send 52 over the link and watches for oversize replies, so I'm not blocked — but it cost me a couple of days of "where has my telemetry gone", and I doubt I'm the only one it could bite.

Thanks very much — and do let me know if the team would like a GitHub issue, more logs, or anything else.

Best wishes,
Malcolm
