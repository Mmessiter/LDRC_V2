# LDRC2SIM

> **RETIRED 2026-09-18.** This firmware's job is now a role in the RXV2
> firmware — *Mode → Simulator interface* on the dongle page (RXV2 0.9.757).
> One board, one firmware, three roles. See [RETIRED.md](RETIRED.md). The
> published OTA area stays up for anyone already running LDRC2SIM.

Firmware for a **Seeed XIAO ESP32-S3** that turns a model RC receiver into a USB
flight-sim controller. It **auto-detects and decodes a CRSF / SBUS / IBUS / PPM**
receiver on one signal wire and presents the channels as an **8-axis USB HID
joystick** that **neXt (CGM)** on macOS reads as 8 proportional channels. With no
receiver connected (or on link loss) it holds the last known channel positions (failsafe).

Grew out of the Phase 1 HID spike (which proved the S3 can present independent HID
axes — verified at the macOS IOKit layer). Why 8 axes and not 16: **neXt caps
proportional input at 8 channels** (so does the whole RC-sim USB ecosystem — RX2SIM,
FrSky XSR-SIM, rcstick-f). Extra channels would have to be buttons/switches.

Still intentionally minimal: no WiFi, web UI, BLE, or Windows personality yet.

---

## What it does

- **Auto-detecting RC decoder** on one input pin: CRSF (ELRS/Crossfire), SBUS
  (FrSky/Futaba, inverted), IBUS (FlySky), PPM (CPPM). Cycles protocols until valid
  frames arrive, then locks on; re-detects if the link drops.
- Maps the first 8 RC channels → 8 HID axes. Channels normalised to microseconds
  (~988–2012, centre 1500) internally, then to signed-16 axis range.
- **Failsafe hold** — on RC link loss the axes hold their last known positions
  (centred on a fresh boot). Heartbeat shows `src=hold`.
- Custom HID **report descriptor**: Generic Desktop → **Joystick (0x04)**, one
  Application collection, **Report ID 1**, 8 axes × **Report Size 16**, logical range
  **−32768..32767** (clean signed-16 encoding).
- HID reports paced with `micros()` at **333 Hz** (in the 250–500 Hz target band).
- **USB CDC** second interface prints a 1 Hz heartbeat (protocol + sample channel
  µs). Device is a **CDC + HID composite**.
- **WiFi config portal + OTA** (see below): a `LDRC2SIM` access point for setup,
  joins your home WiFi in the background, and a web UI at `http://LDRC2SIM.local`
  for status, WiFi config, help, and over-the-air firmware updates. Runs alongside
  the USB joystick without disturbing it.

### Axis layout (`NUM_AXES = 8`)

| Axis | Usage         | ← RC channel |
|------|---------------|--------------|
| 0    | X (0x30)      | ch1          |
| 1    | Y (0x31)      | ch2          |
| 2    | Z (0x32)      | ch3          |
| 3    | Rx (0x33)     | ch4          |
| 4    | Ry (0x34)     | ch5          |
| 5    | Rz (0x35)     | ch6          |
| 6    | Slider (0x36) | ch7          |
| 7    | Dial (0x37)   | ch8          |

These are exactly the 8 distinct usages neXt reads. (Phase 1 proved 16 axes
enumerate fine at the OS level, but neXt binds only the first 8 — see the
de-risking note below. `NUM_AXES` still drives the descriptor if you want to
experiment.)

### VID / PID / strings

| Field        | Value                                    |
|--------------|------------------------------------------|
| VID          | **0x1209** ([pid.codes](https://pid.codes), the open-source/hobby vendor ID) |
| PID          | **0x525C**                               |
| Manufacturer | `LDRC`                                   |
| Product      | `LDRC2SIM`                               |
| Serial       | `LDRC-P1-0005`                           |

0x1209 is the community test/hobby VID — it won't collide with a real vendor and
won't be on a sim's keyboard/mouse HID blocklist. Exact axis range is irrelevant
(the sim calibrates); independently-reporting axes is what matters.

> The PID was bumped several times during bring-up because **neXt caches its
> controller calibration by VID/PID** — changing the descriptor needs a new PID to
> force a fresh parse. 0x525C is the settled value; changing it again will make
> neXt see a new controller (re-calibrate).

### Channel mapping (matches RX2SIM)

`AXIS_SOURCE` / `AXIS_REVERSE` in `src/main.cpp` map the raw RC stream to the 8 HID
axes so neXt shows the **RX2SIM order**: aileron=0, elevator=1, **rudder=2**,
**throttle=3** (RX2SIM swaps throttle/rudder vs a raw Futaba AETR stream), ch5–8 =
4–7. Rudder is reversed. Two non-obvious things are folded into the map:

- **neXt enumerates this descriptor's axes rotated by +2** (our report X,Y show up as
  neXt axes 6,7). Stable and deterministic, so it's cancelled in `AXIS_SOURCE`.
- The map is **SBUS-specific** for this radio (CRSF/PPM pack channels in a different
  order — they'd need their own map; the auto-detect still works, but only SBUS is
  channel-order-tuned right now).

Two HID-descriptor details were essential to get neXt to read all 8 axes (it read
the RX2SIM fine but not an earlier version of ours):
- Axes **must** sit inside a `Collection(Physical)` (without it neXt grouped only ~2).
- Keep a **Report ID** — this arduino-esp32 core's no-Report-ID path is buggy.

---

## RC receiver wiring

One signal wire carries the receiver data; the firmware figures out the protocol.

| XIAO pin        | Connect to                                  |
|-----------------|---------------------------------------------|
| **D7 (GPIO44)** | Receiver signal out (see per-protocol below)|
| **GND**         | Receiver GND  ← **required common ground**  |
| **5V**          | Receiver V+ (or use **3V3** if your RX needs it) |

Which receiver pad goes to **D7**:

| Protocol | Receiver pad                          | Notes                              |
|----------|---------------------------------------|------------------------------------|
| CRSF     | the RX's **TX** pad (UART out)        | ELRS / TBS, 420 kbaud              |
| SBUS     | the **SBUS** pad                      | inverted — handled in firmware     |
| IBUS     | the **IBUS / Servo** signal pad       | FlySky                             |
| PPM      | the **PPM / CPPM** pad                | rising-edge timing                 |

**⚠️ 3.3 V signals only.** The ESP32-S3 GPIO is **not 5 V-tolerant**. Almost all RC
receiver signal pads are 3.3 V logic even when the RX is powered from 5 V (SBUS,
CRSF, IBUS all are). If your receiver's signal line actually swings to 5 V, add a
level shifter or a simple resistor divider on the D7 line.

**How auto-detect behaves:** on power-up it listens ~0.35 s each for CRSF → SBUS →
IBUS → PPM, repeating until it sees ≥3 valid frames, then locks. If the link is lost
for ~0.5 s it re-detects. The 1 Hz CDC heartbeat shows the locked protocol and the
first four channel values in microseconds:

```
LDRC2SIM src=CRSF  n=16  ch1-8us=1500 1500 1000 2000 1500 1500 1500 1500
LDRC2SIM src=hold  n= 8  ch1-8us=1500 1500 1500 1500 1500 1500 1500 1500   <- no RX
```

To change protocol order, the input pin, or timeouts, see the constants at the top
of `src/rc_input.cpp` and `RC_PIN` in `src/main.cpp`.

---

## Wi-Fi, web portal & OTA

The device runs `WIFI_AP_STA`: an open access point named **`LDRC2SIM`** is always
available for setup, and it also joins your home WiFi in the background once you've
entered credentials. A small web UI is served on port 80, reachable at
**`http://LDRC2SIM.local`** (mDNS) or **`http://192.168.4.1`** on the AP.

**First-time setup:**
1. On a phone/laptop, join the **`LDRC2SIM`** WiFi network (open, no password). A
   captive-portal page should pop up; if not, browse to `http://192.168.4.1` or
   `http://LDRC2SIM.local`.
2. Open **Wi-Fi**, pick/enter your home network + password, **Save & connect**.
   The device reboots and joins your home WiFi.
3. From then on, reach it at `http://LDRC2SIM.local` on your home network.

**Pages:** **Home** (transmitter connected? + nav) · **Channels** (live Rotorflight-
style bars) · **Wi-Fi** (config, band-aware scan, show-password, *Forget*) ·
**Protocols** (what's supported + wiring) · **Firmware** (version picker / OTA).

**OTA firmware update (version picker):** the **Firmware** page lists builds from a
firmware server and offers **Install** (newer) / **Roll back** (older) / **Reinstall**
(current) — no filenames. The device pulls the chosen `.bin` over HTTP, flashes the
spare slot, reboots, and the page returns to Home. Sources:
- **Local** — `dev/firmware_server.py` on your Mac (port 8001). Run
  `python3 dev/firmware_server.py` and drop `LDRC2SIM-x.y.z.bin` builds in `dev/`.
  Default URL `http://m4macmini.local:8001/manifest.json`.
- **Public** — `https://messiter.com/ldrc2sim/release/manifest.json` (**live**), mirrored
  like the RXV2 / ReedsV2 OTA areas. Publish a new release with
  `python3 dev/stage_website.py` (builds `NewWebSite/public_html/ldrc2sim/release/` +
  manifest from the `dev/*.bin` files) then `dev/publish_website.sh` (FTP-mirrors it to
  messiter.com). The section hides itself if the host is unreachable.

A plain upload endpoint also remains for dev use:
`curl -F update=@.pio/build/seeed_xiao_esp32s3/firmware.bin http://LDRC2SIM.local/update`.

**Notes / assumptions to confirm:**
- The AP is currently **open** (no password) for easy first setup — add one later if
  you want (`WiFi.softAP(AP_SSID, "password")` in `src/web_portal.cpp`).
- OTA needs the dual-slot partition table (`default_8MB.csv`, set in
  `platformio.ini`). Because that changes the flash layout, the **first** WiFi-
  enabled build must be flashed over **USB**; subsequent updates can be OTA.
- WiFi coexists with the USB joystick; web/OTA traffic may cause brief HID timing
  jitter (harmless — the sim calibrates, and during OTA the device reboots anyway).

---

## Build / flash

Toolchain confirmed on this machine: **PlatformIO 6.1.19**, platform
**espressif32 @ 6.6.0**, which ships **arduino-esp32 core 2.0.14**.

```bash
# Build
pio run

# Flash — see gotcha #3. Two ways to get into download mode:
#
# Easy (no button): run upload once; it "fails" with 'Device not configured'
# but that reset bounces the board INTO download mode on a new port. Then:
ls /dev/cu.usbmodem*                                    # note the new port
pio run -t upload --upload-port /dev/cu.usbmodemXXXX    # this one succeeds
#
# Reliable fallback: hold BOOT, replug USB (or tap RESET), release BOOT, then
# upload to the resulting download port.
#
# Either way, after "Hard resetting via RTS pin" the board sits in download
# until a plain unplug/replug (no button) boots the new firmware.

# Serial heartbeat
pio device monitor          # 115200 baud, prints "LDRC2SIM src=SBUS n=16  ch1-8us=..."
```

### Required build flags (in `platformio.ini`) — and *why* they differ from defaults

```ini
build_unflags = -DARDUINO_USB_MODE=1          # board default — overridden
build_flags   = -DARDUINO_USB_MODE=0          # USB-OTG / TinyUSB
                -DARDUINO_USB_CDC_ON_BOOT=0    # we own USB init order in setup()
```

These two flags are the whole game, and **both differ from the `seeed_xiao_esp32s3`
board defaults**:

1. **`ARDUINO_USB_MODE=0`** (board default is `1`). Mode `1` is Hardware
   Serial/JTAG, which *compiles TinyUSB out* — custom HID is impossible. Mode `0`
   is USB-OTG/TinyUSB.

2. **`ARDUINO_USB_CDC_ON_BOOT=0`**. The core derives
   `ARDUINO_USB_ON_BOOT = CDC_ON_BOOT | MSC_ON_BOOT | DFU_ON_BOOT` and, when set,
   calls `USB.begin()` in `app_main()` **before `setup()`** — enumerating with the
   board's *default* VID/PID and **without** our HID interface, after which every
   override in `setup()` no-ops behind the `_started` guard. With `CDC_ON_BOOT=0`
   we control the order in `setup()`:
   `USB.VID/PID/strings → simrx.begin() → USBSerial.begin() → USB.begin()`.

> Note on the 16-bit descriptor: a *signed* 16-bit range (`0x16 0x00 0x80` /
> `0x26 0xFF 0x7F`) is used deliberately. An *unsigned* 0..65535 range would need a
> 32-bit Logical Maximum item (`0x27 0xFF 0xFF 0x00 0x00`); encoding 65535 in a
> 16-bit item silently truncates to −1. Signed avoids the trap with full 16-bit
> resolution.

---

## ⚠️ ESP32-S3 native-USB gotchas (read before flashing)

3. **Reflashing needs BOOT + a power-cycle to boot.** Flashing over native USB goes
   through the S3's USB-Serial-JTAG, and on this setup (macOS + this firmware)
   esptool's auto-reset does **not** reliably drop the running app into download
   mode, nor reliably boot the app afterward. The dependable workflow:
   - **Enter download:** hold **BOOT**, replug USB (or tap RESET), release BOOT.
   - **Flash** to the resulting download port.
   - **Boot the app:** a plain unplug/replug (no button). After flashing, the board
     often sits as *"USB JTAG/serial debug unit"* / `boot:0x0 (DOWNLOAD)` until this
     clean power-on.
   Host-side reset tricks (1200-baud touch, DTR/RTS handshakes) were unreliable
   through the macOS CDC driver, so don't count on `pio run -t upload` alone.

4. **Un-flashable / bricked descriptor recovery.** If a bad descriptor ever makes
   the board refuse to enumerate for flashing: **hold BOOT, tap RESET, release
   BOOT** to force ROM download mode, then `pio run -t upload`. (Recovery for a
   wedged board — distinct from gotcha #3.)

---

## Verification

### ✅ Verified at the macOS HID layer

Phase 1 (16-axis build) was confirmed via IOKit on the Mac Mini, proving the USB/HID
path end to end: `ioreg` showed **`LDRC2SIM`, VID 0x1209 / PID 0x5258**, serial
`LDRC-P1-0001`, **`PrimaryUsage = 4` (Joystick)**, and the parsed element tree held
the expected independent axis elements (distinct ElementCookies, `ReportSize=16`,
`Min=−32768`/`Max=32767`), with macOS even building a `GameController` view.

The current **8-axis** build will show `MaxInputReportSize = 17` (8×2 + report-ID)
and 8 axis elements. Quick re-check commands:

```bash
ioreg -p IOUSB  -l -w0 | grep -iE "LDRC|idVendor|idProduct"      # device identity
ioreg -r -c IOHIDDevice -l -w0 | grep -iA1 "LDRC2SIM"          # HID + report size
ls /dev/cu.usbmodem*                                             # CDC port
```

### 1. Alive check (no receiver needed)

1. Plug in the XIAO with **nothing on D7**.
2. CDC heartbeat (`pio device monitor`) should print `src=hold n= 0` and the 8 axes
   should read centred in a gamepad tester (<https://hardwaretester.com/gamepad>) / neXt.

### 2. Real RC decode

1. Wire the receiver per **RC receiver wiring** above; bind it to your transmitter.
2. Watch the heartbeat: it should switch from `src=hold` to `src=CRSF` /
   `SBUS` / `IBUS` / `PPM`, and `ch1-8us` should track your sticks (≈1000–2000,
   centre ≈1500).
3. In neXt: **settings → input device → start calibration**, move all sticks/knobs
   through full range, finish. The 8 channels should now follow your transmitter.

---

## File layout

```
platformio.ini     board + the critical USB build flags, documented
src/main.cpp        USB HID (descriptor + report), RC→axis mapping, failsafe hold
src/rc_input.{h,cpp}  CRSF/SBUS/IBUS/PPM decoders + auto-detect on one pin
src/web_portal.{h,cpp} WiFi AP/STA, web UI (status/config/help), mDNS, web OTA
README.md           this file
```

---

## Assumptions / things to confirm

- **Your protocol** — auto-detect covers CRSF / SBUS / IBUS / PPM. If your link is
  something else (DSMX satellite, SUMD, SRXL2…), tell me and I'll add it.
- **Signal voltage** — assumed 3.3 V (see the ⚠️ in wiring). Confirm your RX's signal
  pad isn't 5 V before connecting.
- **Failsafe behaviour** — on link loss the axes **hold their last known positions**
  (centred on a fresh boot). Adjust in `fillAxes()` if you ever want centre-on-loss.
- **Channel→axis order** — first 8 RC channels map straight to axes 0–7. If your
  model uses a different channel order (e.g. AETR vs TAER) or you want to pick which
  8 of 16, that's a small tweak.
- **8-channel cap is neXt's**, not the device's — see the de-risking note above. The
  decoder already reads all 16 channels internally; exposing >8 needs buttons or a
  different sim.
- **CDC interface** — included for the heartbeat and easier re-flashing. Remove the
  `USBCDC USBSerial` lines for a pure-HID device.
