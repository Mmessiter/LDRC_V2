# Rotorflight ESC Forward Programming over MSP — Scorpion Tribunus + Hobbywing Platinum V5

Byte-exact spec for reading/writing ESC parameters THROUGH the flight controller,
for the phone app's MSP tunnel (MSP-over-CRSF, which RXV2 already speaks).

Sources (all fetched 2026-09-01, branch `master` unless noted):

- `rotorflight/rotorflight-firmware` — `src/main/msp/msp.c`, `src/main/msp/msp_protocol.h`,
  `src/main/sensors/esc_sensor.c`, `src/main/sensors/esc_sensor.h`, `src/main/pg/esc_sensor.h`,
  `src/main/common/streambuf.c`
- `rotorflight/rotorflight-lua-scripts` (EdgeTX — the byte-exact reference client) —
  `src/SCRIPTS/RF2/MSP/mspEscScorp.lua`, `PAGES/esc_scorp.lua`, `MSP/mspEscHwPl5.lua`,
  `PAGES/esc_hwpl5.lua`, `MSP/mspQueue.lua`
- `rotorflight/rotorflight-lua-ethos-suite` — `src/rfsuite/lib/msp_esc_parameters_scorpion.lua`,
  `lib/msp_esc_parameters_hw5.lua`, `app/pages/esc_forward_vendor.lua`

The Rotorflight **Configurator has no ESC tab** — `MSPHelper.js` never references command 217.
The transmitter Lua scripts are the only shipping clients; the EdgeTX scripts are byte-exact
against firmware and are the layout authority used below. The parameter tables are identical in
firmware branches `RF-4.4.x`, `RF-4.5.x`, and master (`tribParamAddrLen` verified same in all three).

---

## 1. MSP commands — all MSP **v1**. No MSP v2 needed.

From `msp_protocol.h`:

| Command | ID (dec / hex) | Direction | Ref |
|---|---|---|---|
| `MSP_ESC_PARAMETERS` | **217** / 0xD9 | FC → app: full param blob | line 260 |
| `MSP_SET_ESC_PARAMETERS` | **218** / 0xDA | app → FC: full param blob back | line 261 |
| `MSP_ESC_SENSOR_CONFIG` | 123 / 0x7B | read esc-sensor config (protocol, halfduplex…) | line 173 |
| `MSP_SET_ESC_SENSOR_CONFIG` | 216 / 0xD8 | write esc-sensor config | line 258 |
| `MSP_SET_4WIF_ESC_FWD_PROG` | 244 / 0xF4 | **BLHeli-S/AM32 only** — NOT used for Scorpion/HW5 | line 278 |

Framing: standard MSP v1 (`$M<` / `$M>`, u8 size, u8 cmd, payload, XOR checksum).
Max blob here is 84 bytes (Scorpion), far below the 255-byte v1 size field —
**no jumbo frames, no MSP v2 required**. Our existing v1 tunnel is sufficient.

### 1.1 Handler semantics (`msp.c`)

Read (`case MSP_ESC_PARAMETERS`, msp.c ≈ line 819):

```c
const uint8_t len = escGetParamBufferLength();
if (len == 0) return false;                    // -> MSP ERROR reply
sbufWriteData(dst, escGetParamBuffer(), len);
```

- 217 request has **no payload**.
- Returns an **MSP error frame** until the FC has a complete cached parameter set from the
  ESC. The client must poll until it succeeds (EdgeTX polls every ~0.8 s indefinitely,
  `ignoreErrors = true`; see `mspQueue.lua` lines 12–13, 68).
- Calling 217 has a side effect: `escGetParamFullBufferLength()` (esc_sensor.c line 4540)
  sets `paramMspActive = true` — this is what switches the FC's ESC driver into
  parameter/programming mode (see §3.2 / §4.2).

Write (`case MSP_SET_ESC_PARAMETERS`, msp.c ≈ line 3153):

```c
const uint8_t len = escGetParamBufferLength();
if (len == 0) return MSP_RESULT_ERROR;
sbufReadData(src, escGetParamUpdBuffer(), len);   // memcpy of EXACTLY len bytes
if (!escCommitParameters()) return MSP_RESULT_ERROR;
```

- Payload must be **byte-for-byte the same length and layout** as the 217 response.
- `sbufReadData` is a raw `memcpy` with **no bounds check** (streambuf.c line 214–217):
  a short payload silently copies garbage into the tail of the update buffer,
  and that garbage can be **written to the ESC**. Always send the full length.
- An ACK to 218 means "**scheduled**", not "written". Commit callbacks
  (`tribParamCommit`, `pl5ParamCommit`) only mark ranges dirty; the actual half-duplex
  writes happen asynchronously in the ESC-sensor task. Confirmation = poll 217 again
  until it succeeds and compare the readback.
- Commit validation (`escCommitParameters`, esc_sensor.c line 4724): signature byte must
  equal the one last read, version bits (`ver & 0x3F`) must match, and the driver must be
  writable (`paramCommit != NULL`, i.e. half-duplex enabled). Otherwise MSP error.

### 1.2 Common 2-byte header (both brands)

Defined in esc_sensor.c lines 107–113:

| Offset | Name | Meaning |
|---|---|---|
| 0 | `PARAM_HEADER_SIG` | ESC brand signature. Scorpion = `0x53` (83, `ESC_SIG_TRIB`, line 124). Hobbywing V5 = `0xFD` (253, `ESC_SIG_PL5`, line 123). Dispatch your decoder on this byte. |
| 1 | `PARAM_HEADER_VER` | bits 0–5 (`0x3F`): protocol version (0 for both brands). bit 6 (`0x40` `PARAM_HEADER_RDONLY`): set on read when params are not writable (half-duplex off) — treat page as read-only. bit 7 (`0x80` `PARAM_HEADER_USER`): **on read** = "this ESC can be reset via MSP" capability flag (Scorpion sets it, line 3192). **On write**, bits 7:6 are the command (`PARAM_HEADER_CMD_MASK 0xC0`): `0x00` = save, `0x80` = user command (Scorpion: reset ESC). |

So on write: byte 1 = `0x00` to save, `0x80` to reboot the ESC (Scorpion only).
Any other cmd value → `tribParamCommit`/`pl5ParamCommit` returns false → MSP error.

---

## 2. Preconditions

- **FC config** (check/fix via MSP 123 / 216, or CLI):
  - `esc_sensor_protocol` = `ESC_SENSOR_PROTO_SCORPION` (**4**) or `ESC_SENSOR_PROTO_HW5` (**3**)
    (enum in `pg/esc_sensor.h`: NONE=0, BLHELI32=1, HW4=2, HW5=3, SCORPION=4, KONTRONIK=5, …).
  - A serial port with `FUNCTION_ESC_SENSOR` assigned (else `escSensorInit()` fails, line 4453).
  - `esc_sensor_halfduplex = ON`. Without it the port opens RX-only (line 4532) and:
    Scorpion never populates the param buffer at all (217 errors forever — `escSig`/`paramCommit`
    are only set in the bidirectional branch, lines 3185–3197); HW5 answers reads but with the
    RDONLY bit set and never actually fetches params either (requests are only sent when
    `paramCommit != NULL`, line 2508). **Half-duplex is mandatory.**
  - Baud is fixed by the driver: Scorpion 38400 8N1, HW5 115200 8N1 (lines 4489, 4507).
- **MSP 123 layout** (msp.c ≈ line 806): u8 protocol, u8 halfDuplex, u16 update_hz,
  u16 current_offset, u32 zero (legacy), u8 pinSwap, s8 voltage_corr, s8 current_corr,
  s8 consumption_corr. Same order for 216 (trailing fields optional). Changing protocol/halfduplex
  needs `MSP_EEPROM_WRITE` + FC reboot to take effect (serial port re-init).
- **Arming**: the FC does **NOT** gate 217/218 on disarm for serial ESCs (only the
  4-way-interface path checks `ARMING_FLAG(ARMED)`). The app MUST refuse to enter
  ESC programming unless disarmed and the motor is stopped — an HW5 save
  **automatically reboots the ESC** (§4.3), and Scorpion programming freezes telemetry.
- **No FC EEPROM write, no FC reboot** is needed for the parameters themselves — they
  live in the ESC. (EdgeTX pages save with `eepromWrite=false, rebootAfterSave=false`.)
- ESC must be powered and its telemetry link alive. FC-side boot delays before any ESC
  comms: Scorpion 4 s (`TRIB_REQ_BOOT_DELAY 4000`, line 2757), HW5 5 s
  (`PL5_BOOT_DELAY 5000`, line 2313).
- **Nexus X wiring (verified on the Goblin 770, 2026-09-02)**: the ESC telemetry pad is
  **UART2 RX** (A03); UART2 TX (A02) is the RPM/FREQ input with no TX resource, so the
  half-duplex single wire MUST use `esc_sensor_pinswap = ON` (MSP 123 byte 10, after the legacy u32) or the FC
  talks into the RPM pin and the ESC never hears it (that was yesterday's silent failure).
  Rotorflight's own Nexus Scorpion preset is exactly protocol 4 + halfduplex 1 + pinswap 1.
  MSP 123 on the Goblin now reads `0401C80000000000000001000000`.
- **ESC listen window**: once the ESC is streaming UNC telemetry the FC's pending settings
  read is only re-sent after >1200 ms of silence (UNC frames arrive ~1 Hz), so the FC
  effectively never gets into the Scorpion's power-up listen window unless the ESC is
  power-cycled while the FC is already asking. The ritual: FC on USB (or just the
  flight battery), unplug the battery, wait 5 s, plug it back in — the page keeps
  polling 217 for 2 minutes and shows these steps after ~5 s of no answer.
- **ESC liveness probe**: MSP 139 (MOTOR_TELEMETRY) → u8 count, per motor u32 rpm,
  u16 errRatio, u16 escVoltage mV, u16 escCurrent, u16 mAh, u16 temp ×0.1 °C, u16 temp2.
  Voltage 0 = ESC data stale (telemetry frozen / wrong pin); ~49.6 V + rising temp = alive.
- **One programming session per FC boot**: the reset command (218, 0x80) clears
  `paramMspActive`, `tribInvalidParams`, `tribDirtyParams` and puts the UNC state machine
  back to INACTIVE but leaves `paramPayloadLength` set — 217 keeps answering the stale
  cache and a later 218 save never executes (no ranges are ever re-read). The page's
  Release therefore sends 218/0x80, waits 1.5 s, then MSP 68 (FC reboot).
- **RXV2 transport**: an MSP request body longer than one CRSF frame (57 bytes) must be
  chunked exactly as `handleMspFrame` expects — first frame status `0x30` (v1 + start,
  seq 0) with size+cmd+data, later frames status `0x20|seq` with data only. RXV2 <0.9.533
  silently dropped any payload over 62 bytes, so the 84-byte 218 never left the receiver.
  The FC's CRSF MSP inbox is 128 bytes (2 chunks of the 84-byte blob fit, 90 bytes).
- **FC "MSP error" replies** come back as `[status|0x80][1][cmd][2]`; RXV2 ≥0.9.533
  returns 502 "rejected fn N" in ~100 ms instead of a 1200 ms 504 timeout — a 1 Hz
  erroring 217 poll used to starve the channel stream (swash twitch, 0.9.532 fix).

---

## 3. Scorpion Tribunus (`ESC_SIG_TRIB = 0x53`)

Firmware section: esc_sensor.c lines ≈ 2699–3210. ESC wire protocol 38400 8N1,
little-endian, request/response with 6-byte header (req, addr24, len, crc), regions:
0 system (RO), 1 status (RO), 3 settings (RW). The FC mirrors 8 address ranges
(`tribParamAddrLen`, line 2788):

```c
{ 0x0020, 0x1008, 0x230E, 0x8204, 0x8502, 0x1406, 0x1808, 0x3408 }
//  hibyte = region addr (0x80 flag = system region, read-only), lobyte = length
```

Total payload 32+8+14+4+2+6+8+8 = **82 bytes**, MSP blob = 2 header + 82 = **84 bytes**.

### 3.1 Full parameter table (MSP blob offsets; all multi-byte fields little-endian)

Layout authority: `mspEscScorp.lua` (reads/writes in exactly this order) — verified to sum
to the firmware's 82-byte payload including the trailing `0x3408` range.

| Offset | Size/type | Field | Unit / scale (wire → display) | Range (wire) | Writable | Notes |
|---|---|---|---|---|---|---|
| 0 | u8 | signature | — | must be 0x53 (83) | echo | |
| 1 | u8 | ver/cmd | see §1.2 | read: 0x80 typical (reset-capable) | cmd | write 0x00=save, 0x80=reset ESC |
| 2–33 | 32 B | esc_type_name | ASCII, NUL-padded, e.g. `"Tribunus ESC-6S-80A"` | — | **yes (echo unchanged!)** | Settings region addr 0x00 — it IS diffed and written if you change it. Trailing bytes after the NUL carry non-zero data (sim: `…,0,4,0`) — echo byte-exact. |
| 34–35 | u16 | esc_mode (flight mode) | enum | 0–6 | yes | 0 Heli Governor, 1 Heli Governor (stored), 2 VBar Governor, 3 External Governor, 4 Airplane, 5 Boat, 6 Quad |
| 36–37 | u16 | bec_voltage | enum | 0–4 | yes | 0=5.1 V, 1=6.1 V, 2=7.3 V, 3=8.3 V, 4=Disabled |
| 38–39 | u16 | rotation | enum | 0–1 | yes | 0 = CCW, 1 = CW |
| 40–41 | u16 | telemetry_protocol | enum | 0–4 | yes | 0 Standard, 1 VBar, 2 Jeti Exbus, 3 Unsolicited, 4 Futaba SBUS. **Careful — see risk notes.** |
| 42–43 | u16 | protection_delay | ms (÷1000 → s) | 0–5000 | yes | display step 100 ms (EdgeTX `mult=100`) |
| 44–45 | u16 | min_voltage | 0.01 V | 0–7000 | yes | e.g. 790 = 7.90 V; step 0.10 V |
| 46–47 | u16 | max_temperature | 0.01 °C | 0–40000 | yes | e.g. 10000 = 100 °C; step 1 °C |
| 48–49 | u16 | max_current | 0.01 A | 0–30000 | yes | e.g. 8000 = 80 A; step 1 A |
| 50–51 | u16 | cutoff_handling | 0.01 % | 0–10000 | yes | step 1 % |
| 52–53 | u16 | max_used | 0.01 Ah | 0–6000 | yes | step 0.10 Ah |
| 54–55 | u16 | motor_startup_sound | enum | 0–1 | yes | **0 = On, 1 = Off** (inverted!) |
| 56–59 | u32 | serial_number | raw (display `%08X`) | — | RO (system 0x02) | never written by FC (system ranges skipped in `tribParamCommit`) |
| 60–61 | u16 | firmware_version | raw (display "v63") | — | RO (system 0x05) | |
| 62–63 | u16 | soft_start_time | ms (÷1000 → s) | 0–60000 | yes | step 100 ms |
| 64–65 | u16 | runup_time | ms (÷1000 → s) | 0–60000 | yes | step 100 ms |
| 66–67 | u16 | bailout | ms (÷1000 → s) | 0–65535 | yes | Lua claims max 100000 but the wire field is u16 — effective max 65535 ms |
| 68–71 | u32 | gov_proportional | wire = gain × 100 | 30–180 (0.30–1.80) | yes | ESC-internal IQ22; FC converts: read `iq22/2^22*100`, write `wire/100*2^22` (lines 2900–2907, 2953–2960) |
| 72–75 | u32 | gov_integral | wire = display × 100; ESC-internal = wire / 100000 | 150–250 (1.50–2.50) | yes | FC converts read `iq22/2^22*100000`, write `wire/100000*2^22`. Display divide by 100 like P. |
| 76–79 | u32 | stick_max | µs (?) | — | echo unchanged | range 0x3408; "don't appear to be populated" per EdgeTX comment — **echo byte-exact** (it is a writable settings range!) |
| 80–83 | u32 | stick_zero | µs (?) | — | echo unchanged | ditto |

Reference simulator blob (a real Tribunus ESC-6S-80A capture, from `mspEscScorp.lua`):

```
83,128, 84,114,105,98,117,110,117,115,32,69,83,67,45,54,83,45,56,48,65,0,0,0,0,0,0,0,0,0,0,0,4,0,
3,0, 3,0, 1,0, 3,0, 136,19, 22,3, 16,39, 64,31, 136,19, 0,0, 1,0,
7,2,0,6, 63,0, 160,15, 64,31, 208,7, 100,0,0,0, 200,0,0,0, 1,0,0,0, 200,250,0,0
```

(84 bytes: mode=ExtGov, BEC=8.3V, CW, telem=Unsolicited, delay 5.0 s, minV 7.90,
maxT 100 °C, maxI 80 A, cutoff 50 %, sound Off, S/N 0x06000207, FW v63,
soft-start 4.0 s, runup 8.0 s, bailout 2.0 s, P 1.00, I 2.00.)

### 3.2 Read → edit → write → commit flow, timings

FC-internal constants (lines 2749–2765): `TRIB_PARAM_FRAME_PERIOD 2` ms between param
requests, `TRIB_PARAM_READ_TIMEOUT 200` ms, `TRIB_PARAM_WRITE_TIMEOUT 1200` ms,
telemetry poll `TRIB_FRAME_PERIOD 100` ms.

1. **FC boot**: 4 s quiet, then the FC reads all 8 ranges into cache
   (`tribInvalidateParams()` at init, `tribStart` → `tribBuildNextParamReq`).
   When all 8 are cached → state `TRIB_UNCSETUP_PARAMSREADY` (line 2952).
2. **App polls MSP 217** every 500–1000 ms until success (expect errors first).
   The first poll sets `paramMspActive`. In `tribCrankUncSetup` (line 3103): if a
   frame from the ESC was seen within the last **4000 ms**, the FC sends a
   status-region read to **abort the ESC's unsolicited (UNC) telemetry mode**;
   on the ack it enters `TRIB_UNCSETUP_ACTIVE` and only then sets
   `paramPayloadLength = tribCalcParamBufferLength()` → 217 starts answering.
   If the ESC is dead/quiet > 4 s, 217 keeps erroring — that's the EdgeTX
   "ESC not ready, waiting... Please power cycle your ESC now" screen.
3. **Validate**: byte 0 == 0x53, byte1 & 0x40 == 0 (writable). Byte1 & 0x80 set →
   show a "Reboot ESC" action.
4. **Edit** only the fields marked writable above; keep everything else byte-identical.
5. **Write MSP 218**: full 84 bytes, byte 1 = 0x00. FC diffs each *writable* (non-system)
   range against cache (`tribParamCommit`, line 2807); dirty ranges are queued, the
   MSP param buffer is invalidated (217 errors again during the write-back).
   Each dirty range is written with packet `0xD3` (write settings) and then re-read to
   refresh cache (`tribDecodeWriteParamResp` sets the invalid bit, line 3021).
   Budget ~50–200 ms per dirty range typical, up to 1.2 s timeout each.
6. **Confirm**: poll 217 until success again, compare readback to intent.
   EdgeTX write uses `retryDelay = 2, postSendDelay = 2` seconds around the 218.
7. **Apply / exit programming**: Scorpion settings need an ESC reboot to take effect —
   Ethos shows *"Please reboot the ESC to apply the changes"* after save. Either:
   - write 218 with byte 1 = `0x80` → FC sends reset (`0xD0`, addr 0, u16 0 — line 2884)
     and clears `paramMspActive`; the ESC reboots (~power-on again, 4 s quiet), or
   - tell the user to power-cycle.
   Note: while in programming mode the Trib telemetry stream is stopped; the FC marks
   telemetry `id = ESC_SIG_RESTART (0xFF)` via `paramEscNeedRestart()` (lines 185–189,
   3121) — expect frozen RPM/voltage until the ESC is rebooted.

### 3.3 Scorpion gotchas

- CRC on the ESC wire is handled by the FC; the MSP blob has **no checksum** of its own
  beyond the MSP frame XOR.
- The 32-byte name block and stick_max/stick_zero are **writable ESC settings** —
  corrupt echoes get written to the ESC. Round-trip them untouched.
- Serial number / FW version (offsets 56–61) are system-region: safe, never written.
- `paramMspActive` never times out (only the reset command clears it). Once the app has
  touched 217, Scorpion telemetry stays frozen until ESC reset/power-cycle — always
  finish a programming session with the reset command or tell the user to power-cycle.
- On a save (218 cmd 0) with any dirty range the FC sets `paramPayloadLength = 0` until
  every range has been written and re-read — 217 errors during the write, then answers
  again with the ESC's real values. The page polls 217 for up to 25 s and flags any field
  the ESC quietly kept (out-of-range clamps happen inside the ESC).
- Editor UI ranges (page `rotorflight-escprog.html`): delay 0–5 s, min V 0–70, max T
  0–400 °C, max A 0–300, cut-off 0–100 %, max Ah 0–60, soft/run-up 0–60 s, bail-out
  0–65.5 s, gov P 0.30–1.80, gov I 1.50–2.50. Telemetry protocol is display-only.

---

## 4. Hobbywing Platinum V5 (`ESC_SIG_PL5 = 0xFD`)

Firmware section: esc_sensor.c lines ≈ 2260–2698. ESC wire 115200 8N1, CRC16-MODBUS,
frame type/lengths at lines 2320–2338. MSP payload =
`PL5_RESP_DEVINFO_PAYLOAD_LENGTH (48)` + `PL5_RESP_GETPARAMS_PAYLOAD_LENGTH (31)` = 79,
blob = 2 + 79 = **81 bytes**.

### 4.1 Parameter table (MSP blob offsets)

Layout authority: `mspEscHwPl5.lua`. Bytes 2–49 are the device-info block; the FC
**rejects any write in which these 48 bytes differ from what it read** (`pl5ParamCommit`
line 2385: "info should never change"). Bytes 50–80 are the writable register block.

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | u8 | signature | must be 0xFD (253) |
| 1 | u8 | ver/cmd | read: 0x00 (0x40 if read-only). write: must be 0x00 — HW5 supports **only** cmd 0 (save); any other cmd → MSP error |
| 2–17 | 16 B | firmware_version | ASCII space/NUL-padded, e.g. `"   PL-04.1.02  "` — **RO, echo exact** |
| 18–33 | 16 B | hardware_version | e.g. `"HW1106_V100456NB"` — **RO, echo exact**. Selects the field-layout profile (§4.4) |
| 34–49 | 16 B | esc_type | e.g. `"Platinum_V5     "` — **RO, echo exact** |
| 50–64 | 15 B | mode/name string | e.g. `"Platinum V5    "` — first 15 bytes of the writable register block; echo unchanged |
| 65–80 | 16 × u8 | item bytes 1–16 | meaning depends on layout profile, default below |

Default layout (`DEFAULT_LAYOUT`, item N at blob offset 64+N):

| Item / offset | Field | Values |
|---|---|---|
| 1 / 65 | flight_mode | 0 Fixed Wing, 1 Ext Gov, 2 Governor, 3 Gov Store |
| 2 / 66 | lipo_cell_count | 0 Auto, 1=3S … 12=14S (profile-dependent tables, §4.4) |
| 3 / 67 | cutoff_type | 0 Soft, 1 Hard |
| 4 / 68 | cutoff_voltage | 0 Disabled, 1=2.8 V … 11=3.8 V (per cell; HW1128 profile: 0 Disabled, 1=2.5 … 14=3.8) |
| 5 / 69 | bec_voltage | numeric: volts = (raw + profile.min)/10; default profile min=50 → raw 0 = 5.0 V, step 0.1 V, max 8.4 V (other profiles to 12.0 V; HW1132: enum 0=6.0, 1=7.4, 2=8.4) |
| 6 / 70 | startup_time | seconds = raw + 4; range 4–25 s (default 11) |
| 7 / 71 | gov_p_gain | 0–9 (default 6) |
| 8 / 72 | gov_i_gain | 0–9 (default 5) |
| 9 / 73 | auto_restart | 0–90 s (default 25) |
| 10 / 74 | restart_time | 0=1 s, 1=1.5 s, 2=2 s, 3=2.5 s, 4=3 s |
| 11 / 75 | brake_type | 0 Disabled, 1 Normal, 2 Proportional, 3 Reverse (many profiles drop Proportional) |
| 12 / 76 | brake_force | 0–100 % |
| 13 / 77 | timing | 0–30 ° (default 24) |
| 14 / 78 | rotation | **0 = CW, 1 = CCW** (opposite of Scorpion!) |
| 15 / 79 | active_freewheel | 0 Enabled, 1 Disabled |
| 16 / 80 | startup_power | 0–6 = Level 1–7 |

Alternative layouts (item index → field), chosen from `hardware_version` / "OPTO" in
esc_type or firmware_version:

- **OPTO** (`…PL_OPTO`): no bec_voltage; items = flight_mode 1, lipo 2, cutoff_type 3,
  cutoff_voltage 4, startup_time 5, gov_p 6, gov_i 7, auto_restart 8, restart_time 9,
  brake_type 10, brake_force 11, timing 12, rotation 13, active_freewheel 14, startup_power 15.
- **HW1132**: lipo 1 (Auto/2S/3S/4S), cutoff_type 2, cutoff_voltage 3, bec 4 (enum 6.0/7.4/8.4),
  response_time 5 (0–9 = "1"–"10"), timing 6, rotation 7, active_freewheel 8, startup_power 9.
- **HW1128**: lipo 1 (Auto/2S/3S/4S), cutoff_type 2, cutoff_voltage 3 (2.5–3.8 table),
  brake_type 5, brake_force 6, timing 7, rotation 8 (0 Forward, 1 Reverse, 2 4D, 3 4D-Reverse
  per Ethos), active_freewheel 9, startup_power 10. (Item 4 unused — leave as read.)
- Known profile keys: `HW1104_V100456NB`, `HW1106_V100456NB/V200456NB/V300456NB`,
  `HW1121_V100456NB`, `HW1121_V00456NB`, `HW1132_V100456NB`, `HW1128_V100456NB`,
  `HW198_V1.00456NB`; prefix-match on `HW1132_`, `HW1128_`, `HW1121_`; else default.

Reference simulator blob (81 bytes, from `mspEscHwPl5.lua`):

```
253,0, "   PL-04.1.02   "(16), "HW1106_V100456NB"(16), "Platinum_V5     "(16),
"Platinum V5    "(15), 0,0,0,3,0,11,6,5,25,1,0,0,24,0,0,2
```

### 4.2 Flow and timings

Constants (lines 2313–2318): `PL5_PARAM_FRAME_PERIOD 4` ms, read timeout 100 ms, write
timeout 200 ms, keep-alive ping every 480 ms (timeout 1600 ms).

1. FC boot: 5 s quiet, then passive telemetry decode (32-byte frames, type 0x5C30).
2. App polls 217 → sets `paramMspActive`. Requests are interleaved after each telemetry
   frame (`pl5DecodeTeleFrame`, line 2508): device-info read (`0x2C25`, 0x20 regs, 73-byte
   resp), then params read (`0x3835`, 0x30 regs, 105-byte resp). Once both cached,
   `paramPayloadLength = 79` and 217 answers — typically well under a second after the
   first successful poll. When idle the FC pings (`0x2C24`) every 480 ms to hold the link.
3. Edit item bytes; **echo devinfo (2–49) and the mode string (50–64) exactly**.
4. Write 218 (81 bytes, byte 1 = 0). `pl5ParamCommit` (line 2383) rejects if devinfo
   changed; otherwise marks dirty and invalidates the MSP buffer.
5. FC write-back (`pl5BuildNextReq`, line 2439): builds a 63-byte write frame
   (13-byte header `pl5WriteParamsReq` + the 48-byte register block, CRC16-MODBUS).
   Note the register block byte 0 is preserved from the last read; your 31 payload bytes
   land at block bytes 1–31 (line 2447–2449).
6. On write ack (`0x3835` resp, `buffer[3] & 0x80` = error flag, line 2565): success →
   **verification read** and byte-exact compare against what was sent
   (`pl5DecodeGetParamsResp`, line 2537). Mismatch → 217 stays in error and the FC
   re-reads (app should treat repeated 217 failure after a write as "write failed").
7. On verified match the FC **automatically sends the ESC reset command**
   (`pl5ResetReq`, opcode 0x2B02/0x55, line 2554 `pl5ResetPending = true`) —
   **the ESC reboots itself to apply settings**. Devinfo + params are then re-read.
8. App: poll 217 until success again, compare, done. No explicit reset/cmd byte needed
   (and none is accepted — cmd must be 0).

---

## 5. Risk notes — what can hurt, and what the stock clients do about it

1. **Short 218 payload = garbage written to the ESC.** `sbufReadData` is an unchecked
   memcpy of `escGetParamBufferLength()` bytes. Always send exactly 84 (Scorpion) /
   81 (HW5) bytes. Beware: the current *Ethos* compact lib
   (`msp_esc_parameters_scorpion.lua`) encodes only 76 of 84 bytes (it models the last
   trib range `0x3408` — stick_max/stick_zero — as absent). **Do not copy the Ethos
   encoder; the EdgeTX `mspEscScorp.lua` layout above is the byte-exact one.**
2. **Read-modify-write only.** Never synthesize a blob. Read 217, mutate the documented
   fields, echo everything else (Scorpion name block, HW5 devinfo + mode string, unknown
   item bytes in reduced HW5 layouts) bit-for-bit. HW5 firmware enforces this for devinfo
   (write rejected if changed); Scorpion does NOT protect its name block — a corrupted
   echo is silently written to the ESC's settings region.
3. **No range validation in the FC.** Values pass straight to the ESC hardware.
   Clamp to the tables above; for HW5 use the per-hardware profile tables (a value legal
   on one HW revision is out of range on another).
4. **HW5 save auto-reboots the ESC.** Motor must be stopped and the model disarmed —
   the FC itself never checks ARMED on 217/218 for serial ESCs; that gate is on us.
5. **Scorpion programming freezes telemetry** (UNC mode aborted; telemetry id flagged
   `ESC_SIG_RESTART`). Finish every session with the reset command (218, byte1=0x80,
   only if the read's byte1 bit7 was set) or a user power-cycle, or the pilot flies
   with dead ESC telemetry.
6. **Changing Scorpion `telemetry_protocol`** away from a Rotorflight-compatible mode
   can sever the telemetry/programming link entirely (recoverable only with Scorpion's
   own USB tools). Warn or hide the field.
7. **218 ACK ≠ committed.** Writes are asynchronous; verify by polling 217 and comparing.
   During write-back 217 deliberately errors (`paramPayloadLength = 0`) — that's normal,
   keep polling (Scorpion: allow ~1.2 s per dirty range; HW5: write + verify + reset +
   re-read ≈ a few seconds).
8. **Concurrent MSP clients** (LUA script on the TX + phone app): both share one FC-side
   param buffer; interleaved read/write sessions can commit stale data. Make the session
   exclusive in the app UX.
9. **Signature check first.** If byte 0 ≠ expected signature, show "wrong/incompatible
   ESC" and refuse edits (both stock clients do). If byte 1 has bit 6 set, the page is
   read-only (half-duplex off) — offer to fix `esc_sensor_halfduplex` via MSP 216 +
   EEPROM write + FC reboot instead.
10. **Scorpion gov_integral scale trap**: wire u32 is display×100 but ESC-internal is
    wire/100000 (asymmetric with gov_proportional's /100). Use the table's conversions
    verbatim; don't "simplify".

---

## 6. Quick implementation checklist for the RXV2/app tunnel

- MSP v1 only; commands 217 (read, no payload) and 218 (write, 84/81-byte payload).
- Poll 217 at ~2 Hz with error tolerance until first success; brand-dispatch on byte 0.
- Keep the raw blob; edit in place; write back whole; byte1=0 to save.
- Re-poll 217 until success; diff to confirm; surface per-field mismatches.
- Scorpion: offer "Reboot ESC" (byte1=0x80) when read byte1 bit7 set; require it (or a
  power-cycle) on session exit. HW5: reboot is automatic after save.
- Gate the whole feature on: disarmed, RX link idle-safe, esc_sensor_protocol ∈ {3, 4},
  halfduplex on.
