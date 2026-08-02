# TXV2 Revision A — Firmware Plan
*by Claude and Malcolm — July 2026 · boards arrive ~29 July*

## The head start (why this goes fast)
- **V1 TransmitterCode** — the whole radio brain already works: nRF24 protocol, Nextion UI host, model memories, bind flow, telemetry screens, reconnection histogram. Port, don't rewrite.
- **RXV2 firmware** — proven ESP32 WiFi web config, BLE GATT bridge (the 240-byte chunk lesson learned!), OTA-over-BLE+5G, messiter.com update channel.
- **RXV2App iOS/Android** — the phone apps already speak our BLE protocol; the TX becomes one more device type.

## Phase 0 — board #1 bring-up (day 1, no firmware needed)
1. Visual + meter checks BEFORE any modules: 3V3 at gimbal "+" pins, rail shorts, USB-C orientation
2. Battery on → 2808 latch test with the button (press = on) — no MCUs fitted
3. Buck outputs: 5V and 5V-NEXT
4. Fit Teensy alone → USB blink sketch → soft-power test (pin 4 sense, pin 5 latch-off)
5. Charger: USB-C in → CHG LED, I2C scan finds BQ25887 at 0x6A

## Phase 1 — Teensy core (week 1)
- Port V1 `main.cpp` wholesale; remap pins (SENSE 33→4, new: WS2812 on 2, SIG on 3, VBAT divider on A10/24)
- nRF24 loop unchanged (CE 9 / CSN 10 / SPI 11-13) — V1-compatible pipe = TX ID
- Nextion on Serial1 (pins 0/1) — V1 host code near-verbatim
- New drivers: BQ25887 (charge state, per-cell volts → telemetry screen), WS2812 status LED (green/red/blue, V1 scheme), VBAT divider calibration (ratio 62/15)
- Trims as channel-function buttons (1L/1R/2U/2D/3U/3D/4R/4L mapping)

## Phase 2 — ESP32 sidecar (week 2)
- Link UART to Teensy: 1 Mbaud, length-prefix + CRC framing, HANDSHAKE_A/B flow control
- BLE GATT bridge (lift from RXV2) → phone app config: model names, settings, telemetry mirror
- WiFi web UI (lift from RXV2 pages pattern)

## Phase 3 — the OTA trinity (week 3)
1. **ESP32 self-OTA** — stock ArduinoOTA / BLE fwup (RXV2 pattern, exists)
2. **Teensy OTA** — FlasherX: ESP streams hex over the link UART, Teensy self-flashes
3. **Nextion OTA** — ESP → Teensy → Serial1 passthrough of the .tft (upload protocol, baud escalation)
- All three fetch from messiter.com `/txv2/release/` (stage_website.py + publish_website.sh convention)

## Phase 4 — polish
- TX MODULE output on SIG: CRSF (ELRS) first, PPM fallback
- Reconnection histogram screen (port from V1 — it earned its keep)
- Bind-on-long-press with audible Nextion prompt (V1 timing: 2–5 s window)
- Charging screen: pack + per-cell volts from BQ25887 while plugged in

## Standing rules
- Board #1 is the guinea pig; nothing ships to boards 2–100 until OTA works end-to-end
- Every release published to messiter.com; apps + firmware ship together (one-pass rule)

## Lessons from the 2026-07-23 RXV2 gap hunt (V1 shortcomings to fix in TXV2)

Found while chasing a mystery 1-second link gap that turned out to be the
V1 transmitter itself:

1. **The connect ritual stalls the RF loop ~1 s** (bind confirm / model-ID
   before the green light). TXV2: the handshake must not pause the packet
   stream — stream safe frames throughout, or interleave.
2. **Blocking Nextion writes create real air gaps** — the telemetry screen's
   redraws measurably silenced the RF (95 ms + several 32-64 ms gaps at the
   receiver while the TX's own display showed a perfect zero). TXV2: display
   I/O must never block the RF path (own task/core, queued writes).
3. **V1's link stats can't see the TX's own stalls** — gap bookkeeping runs
   in the same loop that stalls, MinimumGap=50 ms hides everything smaller,
   and stats are wiped 4-6 s after the green light. TXV2: measure honestly
   (the RXV2 blackbox is the reference: microsecond gaps, histogram,
   position-of-longest, handshake grace instead of a stats wipe) — and
   prefer the RECEIVER's numbers via telemetry, since only the receiving
   end sees the truth.

## Full UI mirror on the phone (Malcolm, 2026-07-23 evening)

The Nextion is hard to read in sunshine; a modern phone is not. TXV2 should
offer the ENTIRE transmitter UI on the phone, so nobody has to struggle
with the screen at the field.

Architecture (proven end-to-end by RXV2 + RXV2App in July 2026):
- The transmitter's state lives in ONE place (the main MCU). The Nextion
  and the phone are two VIEWS of that state — no duplicated logic.
- The ESP32 sidecar serves the web UI over BLE (HTTP-over-BLE framing,
  same as RXV2) and WiFi at home; pages bundled in the phone apps load
  instantly, only small /api calls cross the link.
- Two-way live sync: a change made on either screen appears on the other.
- Reuse wholesale from RXV2: BleConfig framing, app shells (iOS + Android),
  publish/OTA pipeline, update announcements via /app/manifest.
- Safety rule: configuration writes locked out while a model is armed /
  link live, same spirit as the RX's fly-mode rules.
- Bonus once it exists: the phone UI works even with the TX's screen
  dark/broken, and a future budget TX variant could omit the screen.

## Flight archive on the TX (Malcolm, 2026-07-31)
After landing, the RX streams the just-saved flight record (~7 kB, FLT4)
to the TX over the ack-payload side channel (the TxParams lane) — a
couple of seconds at ~500 pkt/s. The Teensy 4.1 stores it on the 32 GB
microSD as /flights/<model>/<date>_<time>.flt (timestamp already in the
header via the phone clock sync). RX 20-slot diary = field cache; TX SD
= permanent library (7 kB × 10 flights/day × 50 years ≈ 1% of the card).
Later: browse years of flights from the TX screen or the phone.

## TX clock → RX (parameter ID 34, shipped in V1 2026-08-02)

The transmitter's battery-backed RTC dates the receiver's flight logs:
parameter ID 34 = [Gyear(2-digit), Gmonth, Gday, Ghour, Gmin, Gsec, 321
magic], queued in SendInitialSetupParams just after connect. RX (0.9.297+)
converts the TX's LOCAL wall time to UTC epoch using a phone-taught
timezone offset (NVS "tzmin", refreshed on every phone connect so DST
self-heals; phone sync outranks TX for the boot). V1 receivers ignore the
ID. TXV2 must keep this: same ID, same layout — its RTC (or GPS) is the
primary field timekeeper, phones optional.

### TXV2 timekeeping hierarchy (Malcolm, 2026-08-02 siesta musing)
1. Teensy 4.1 built-in RTC (32 kHz crystal, coin cell on VBAT) — ±20-30 ppm,
   better than V1's DS1307 but still ~a minute/month.
2. NTP via the on-board ESP32 whenever home WiFi is in range — the primary
   corrector; silent, exact, no user action. Do this.
3. GPS from any model that carries one, over the link (V1 scheme kept).
   Model mounting: sky view, away from ESC/motor/BEC wiring and the tail
   dipole V — tailboom top forward of the fin, or non-carbon canopy top.
4. RX-side learned-offset calibration (0.9.300) stays as the safety net.

Note (2026-08-02): V1's "Delta GMT" display-offset setting is retired — with
phone-corrected local time in the RTC it must stay 0 (Malcolm set it so).
TXV2 has NO manual timezone/DST setting: the clock holds local time, taught
by phone (tz included) / NTP / GPS, and DST changes heal themselves.
