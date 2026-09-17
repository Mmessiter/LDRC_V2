# Travel Extents — Rotorflight 2.3 MSP spec (mixer / servos / acc-trim)

Groundwork for the **Travel extents** screen (phone app + V1 TX), requested by
Malcolm after Black Thunder II's first flight (2026-08-14): "abundantly clear I
have nowhere near enough collective pitch" — collective/cyclic/swash limits are
not yet editable over the link. This doc is the byte-exact wire spec, extracted
and verified from the Rotorflight sources.

**Source of truth:** `rotorflight-firmware` tag `release/4.6.0` (= RF 2.3, MSP
API **12.9**) — `src/main/msp/msp_protocol.h`, `msp.c`, `pg/mixer.h`,
`pg/servos.h`; configurator tag `release/2.3.0` — `src/js/tabs/mixer.js`,
`src/js/msp/MSPHelper.js`. There is no "RELEASE_2.3" firmware branch — RF 2.3
is internally fw 4.6.0 (branch `RF-4.6.x`). All multi-byte fields
little-endian, MSPv1 IDs.

## Screen contents (agreed 2026-08-14)

- Collective pitch range  (mixer input 4, symmetric min/max)
- Cyclic pitch limit      (mixer inputs 1+2, symmetric min/max)
- Total swash pitch limit (mixer config swash_pitch_limit)
- Swash trims roll/pitch/collective (mixer config swash_trim[0..2])
- Tail limits/centre      (mixer input 3 min/max, tail_center_trim)
- Governor headspeed      (already editable — existing gov block)

## Command ID table

| Name | ID | Dir |
|---|---|---|
| MSP_MIXER_CONFIG | 42 | read |
| MSP_SET_MIXER_CONFIG | 43 | write |
| MSP_SERVO_CONFIGURATIONS | 120 | read (all servos) |
| MSP_SET_SERVO_CONFIG | 124 | write (one servo, new in 4.6.0) |
| MSP_GET_SERVO_CONFIG | 125 | read (one servo, new in 4.6.0) |
| MSP_MIXER_INPUTS | 170 | read (all inputs) |
| MSP_SET_MIXER_INPUT | 171 | write (**one input per frame**) |
| MSP_MIXER_RULES | 172 | read |
| MSP_SET_MIXER_RULE | 173 | write (one rule) |
| MSP_GET_MIXER_INPUT | 174 | read (one input, payload = index U8) |
| MSP_MIXER_OVERRIDE | 190 | read (all) |
| MSP_SET_MIXER_OVERRIDE | 191 | write (index U8 + value U16) |
| MSP_SET_SERVO_CONFIGURATION | 212 | write (one servo — what configurator 2.3 uses) |
| MSP_SET_ACC_TRIM | 239 | write |
| MSP_ACC_TRIM | 240 | read |
| MSP_EEPROM_WRITE | 250 | save |
| MSP_SET_REBOOT | 68 | reboot |

## MSP_MIXER_CONFIG (42) response / MSP_SET_MIXER_CONFIG (43) request — same order

Response is 21 bytes. SET accepts 19 bytes (pre-12.8 clients) or 21; the last
2 are read only `if (sbufBytesRemaining(src) >= 2)`.

| Off | W | Field (`mixerConfig_t`) | Type | Range | Units / scale |
|---|---|---|---|---|---|
| 0 | 1 | main_rotor_dir | U8 | 0=CW, 1=CCW | enum |
| 1 | 1 | tail_rotor_mode | U8 | 0=VARIABLE, 1=MOTORIZED, 2=BIDIRECTIONAL | enum |
| 2 | 1 | tail_motor_idle | U8 | 0..250 | 0.1 % (÷1000 internally) |
| 3 | 2 | tail_center_trim | S16 | −1000..1000 | var-pitch tail: deg = raw×24/1000; motorized: 0.1 % |
| 5 | 1 | swash_type | U8 | 0=NONE,1=THRU,2=120,3=135,4=140,5=90L,6=90V | enum |
| 6 | 1 | swash_ring | U8 | 0..100 | % |
| 7 | 2 | swash_phase | S16 | −1800..1800 | 0.1 deg |
| 9 | 2 | swash_pitch_limit | U16 | 0..3000 | **deg = raw×12/1000** (0 = off); "Total pitch limit" |
| 11 | 2 | swash_trim[0] (roll) | S16 | −1000..1000 | percent of servo throw (NOT 0.1 deg — source-verified) |
| 13 | 2 | swash_trim[1] (pitch) | S16 | −1000..1000 | 0.1 deg |
| 15 | 2 | swash_trim[2] (collective) | S16 | −1000..1000 | 0.1 deg |
| 17 | 1 | swash_tta_precomp | U8 | 0..250 | gain = raw/100 |
| 18 | 1 | swash_geo_correction | S8 | −125..125 | UI value = raw/5 (raw = ui×5) |
| 19 | 1 | collective_tilt_correction_pos | S8 | −100..100 | % as-is (**API ≥ 12.8**, RF 2.2+) |
| 20 | 1 | collective_tilt_correction_neg | S8 | −100..100 | % as-is (**API ≥ 12.8**) |

Firmware calls `mixerInitConfig()` immediately on SET — everything except
`swash_type` / `tail_rotor_mode` takes effect live. Firmware clamps on save:
if `swash_pitch_limit > 0` it is raised to at least
`|collective input min/max| + 500` (500 raw = 6 deg cyclic reserve).

Exact write sequence (msp.c 3436-3455):
`ReadU8 ×3, ReadU16, ReadU8 ×2, ReadU16 ×5, ReadU8 ×2, [ReadS8 ×2]`.

## MSP_MIXER_INPUTS (170) / MSP_SET_MIXER_INPUT (171)

- Read: for i = 0..28 (`MIXER_INPUT_COUNT` = 29): `rate S16, min S16, max S16`
  → 174 bytes, no count prefix.
- Write: **one input per frame** — `index U8, rate S16, min S16, max S16`
  (7 bytes). Index ≥ 29 → MSP error. Configurator loops one frame per index.
  Values consumed live (`/1000.0f` at use), no init call needed.
- `MSP_GET_MIXER_INPUT` (174): send index U8, get the 3 S16s back.
- Ranges: rate −10000..10000; min/max −2500..2500.

### MIXER_IN_* index enum (pg/mixer.h)

```
0  NONE                     10 RC_COMMAND_THROTTLE      20 RC_CHANNEL_11
1  STABILIZED_ROLL          11 RC_CHANNEL_ROLL          21 RC_CHANNEL_12
2  STABILIZED_PITCH         12 RC_CHANNEL_PITCH         22 RC_CHANNEL_13
3  STABILIZED_YAW           13 RC_CHANNEL_YAW           23 RC_CHANNEL_14
4  STABILIZED_COLLECTIVE    14 RC_CHANNEL_COLLECTIVE    24 RC_CHANNEL_15
5  STABILIZED_THROTTLE      15 RC_CHANNEL_THROTTLE      25 RC_CHANNEL_16
6  RC_COMMAND_ROLL          16 RC_CHANNEL_AUX1          26 RC_CHANNEL_17
7  RC_COMMAND_PITCH         17 RC_CHANNEL_AUX2          27 RC_CHANNEL_18
8  RC_COMMAND_YAW           18 RC_CHANNEL_AUX3          28 (COUNT = 29)
9  RC_COMMAND_COLLECTIVE    19 RC_CHANNEL_10
```

The Mixer tab touches only indices 1 (roll), 2 (pitch), 3 (yaw), 4 (collective).

## Configurator Mixer-tab conversions (mixer.js, release/2.3.0 — exact)

Angle scale: **1 raw = 0.012 deg** on cyclic/collective (1000 = 12 deg),
**0.024 deg** on yaw (1000 = 24 deg), **0.1 %** on tail motor.

| UI field | Wire field | deg→raw | raw→deg |
|---|---|---|---|
| Total pitch limit | MIXER_CONFIG.swash_pitch_limit | `raw = round(deg*1000/12)` | `deg = raw*12/1000` |
| Cyclic pitch limit | INPUTS[1] and [2]: `min=-raw, max=+raw` | `raw = round(deg*1000/12)` | `deg = INPUTS[2].max*12/1000` |
| Collective pitch limit | INPUTS[4]: `min=-raw, max=+raw` | `raw = round(deg*1000/12)` | `deg = INPUTS[4].max*12/1000` |
| Cyclic gain % | INPUTS[1].rate = INPUTS[2].rate = `%×10 × dir(±1)` | | `% = |rate|*0.1`, dir = sign |
| Collective gain % | INPUTS[4].rate = `%×10 × dir` | | |
| Yaw gain % | INPUTS[3].rate = `%×10 × dir` | | |
| Tail yaw min/max (deg) | INPUTS[3].min = `−deg*1000/24`, .max = `deg*1000/24` | | |
| Swash trims r/p/c (deg) | swash_trim[0..2] = `deg×10` | | `deg = raw*0.1` |
| Phase angle (deg) | swash_phase = `deg×10` | | |
| Tail center trim | var-pitch: `deg*1000/24`; motorized: `%×10` | | |
| Geo correction | swash_geo_correction = `ui×5` | | `ui = raw/5` |
| Tilt corr. pos/neg (%) | collective_tilt_correction_pos/neg = ui | | |
| Tail motor idle % | tail_motor_idle = `%×10` | | |

Cyclic limit lives in the **inputs** (1+2, symmetric min/max), collective in
input 4, total limit in MIXER_CONFIG. Same 12/1000 scale for both.

## MSP_SERVO_CONFIGURATIONS (120) response

`U8 count`, then per servo **16 bytes**:

| Off | W | Field | Type | Notes |
|---|---|---|---|---|
| 0 | 2 | mid | U16 | center µs (default 1500) |
| 2 | 2 | min | S16 | lower travel, µs **relative to mid** (−1000..1000, default −700) |
| 4 | 2 | max | S16 | upper travel, µs relative to mid (default +700) |
| 6 | 2 | rneg | U16 | negative scale, µs per full deflection (50..1000, default 500) |
| 8 | 2 | rpos | U16 | positive scale, µs (50..1000) |
| 10 | 2 | rate | U16 | update rate Hz (25..5000, default 333) |
| 12 | 2 | speed | U16 | speed limit, ms per full travel (0..60000, 0 = off) |
| 14 | 2 | flags | U16 | bit0 = REVERSED, bit1 = GEO_CORR |

**4.6.0 quirk:** with SBUS/FBUS *bus servos* configured, count =
`getServoCount() + 18` — PWM servos then 18 bus servos (internal indices
8..25), same record. Normal case (no bus servos): just `getServoCount()`.

### Servo writes
- **MSP_SET_SERVO_CONFIGURATION (212)** — configurator 2.3's choice:
  `index U8` + the 8 U16 fields in order. Payload must be **exactly 17 bytes**
  (`dataSize != 1+16` → error). Index in list space (bus-remapped if bus
  servos). Calls `validateAndFixServoConfig()`; effect immediate.
- **MSP_SET_SERVO_CONFIG (124) / MSP_GET_SERVO_CONFIG (125)** — new 4.6.0
  per-servo pair, raw index, same layout, no bus remap.

MAX_SUPPORTED_SERVOS = 8 PWM (+18 bus channels on SBUS-out/FBUS targets only).

## MSP_ACC_TRIM (240) / MSP_SET_ACC_TRIM (239)

4 bytes, **pitch first**: `pitch S16, roll S16`, units 0.1 deg
(range −300..300 = ±30 deg). Attitude offset for leveling/rescue. Effect
immediate, no reboot.

## MSP_MIXER_OVERRIDE (190/191) — bench testing only

Read: 29 × S16 (input indexing). Write: `index U8, value S16`. Range
−2500..2500; **2501 = OFF**, 2502 = passthrough. Never leave enabled for flight.

## Write / save / reboot semantics

1. SET commands are accepted **even while armed** (no arming gate on
   mixer/servo/acc-trim) and take effect immediately in RAM — but do config
   writes disarmed for safety. (Our existing TxParams safety gates apply.)
2. **Persist with MSP_EEPROM_WRITE (250)**, no payload. Refused while armed
   (MSP error, config dirty). Without it everything reverts on power cycle.
3. **Reboot needed only for `swash_type` / `tail_rotor_mode`** (the only two
   `mixerReboot` controls; they rebuild the mixer rule table). Configurator
   sends MSP_SET_REBOOT (68) after EEPROM write in that case. All limits,
   trims, rates, tilt/geo corrections apply live.
4. Configurator save order: SET_MIXER_CONFIG → SET_MIXER_INPUT 1,2,3,4 (one
   frame each) → rules if dirty → EEPROM_WRITE → (reboot if flagged).

## Version gates

- `collective_tilt_correction_pos/neg` (last 2 bytes of 42/43): API ≥ 12.8
  (RF 2.2 / fw 4.5.0). RF 2.3 = API 12.9. Gate with MSP_API_VERSION if older
  FCs matter; otherwise always send 21 bytes.
- Bus-servo variable-length 120 + commands 124/125: new in fw 4.6.0.
- Everything else identical between 4.5.1 and 4.6.0.
