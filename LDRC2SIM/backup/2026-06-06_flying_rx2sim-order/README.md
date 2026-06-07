# LDRC SimRX

Firmware for a **Seeed XIAO ESP32-S3** that turns a model RC receiver into a USB
flight-sim controller. It **auto-detects and decodes a CRSF / SBUS / IBUS / PPM**
receiver on one signal wire and presents the channels as an **8-axis USB HID
joystick** that **neXt (CGM)** on macOS reads as 8 proportional channels. With no
receiver connected it drives the axes with a sine self-test so the device is always
visibly alive.

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
- **Sine self-test fallback** when no RC link (axes 0–7 sweep at stepped rates).
- Custom HID **report descriptor**: Generic Desktop → **Joystick (0x04)**, one
  Application collection, **Report ID 1**, 8 axes × **Report Size 16**, logical range
  **−32768..32767** (clean signed-16 encoding).
- HID reports paced with `micros()` at **333 Hz** (in the 250–500 Hz target band).
- **USB CDC** second interface prints a 1 Hz heartbeat (protocol + sample channel
  µs). Device is a **CDC + HID composite**.

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
| PID          | **0x5258** (ASCII `"RX"`)                |
| Manufacturer | `LDRC`                                   |
| Product      | `LDRC SimRX`                             |
| Serial       | `LDRC-P1-0001`                           |

0x1209 is the community test/hobby VID — it won't collide with a real vendor and
won't be on a sim's keyboard/mouse HID blocklist. Exact axis range is irrelevant
(the sim calibrates); independently-reporting axes is what matters.

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
LDRC SimRX  src=CRSF       ch1-4us=1500 1500 1000 2000  ax0=0
LDRC SimRX  src=sine-test  ch1-4us=1500 1500 1500 1500  ax0=21456   <- no RX connected
```

To change protocol order, the input pin, or timeouts, see the constants at the top
of `src/rc_input.cpp` and `RC_PIN` in `src/main.cpp`.

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
pio device monitor          # 115200 baud, prints "LDRC SimRX: 16 axes @ 333 Hz ..."
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
path end to end: `ioreg` showed **`LDRC SimRX`, VID 0x1209 / PID 0x5258**, serial
`LDRC-P1-0001`, **`PrimaryUsage = 4` (Joystick)**, and the parsed element tree held
the expected independent axis elements (distinct ElementCookies, `ReportSize=16`,
`Min=−32768`/`Max=32767`), with macOS even building a `GameController` view.

The current **8-axis** build will show `MaxInputReportSize = 17` (8×2 + report-ID)
and 8 axis elements. Quick re-check commands:

```bash
ioreg -p IOUSB  -l -w0 | grep -iE "LDRC|idVendor|idProduct"      # device identity
ioreg -r -c IOHIDDevice -l -w0 | grep -iA1 "LDRC SimRX"          # HID + report size
ls /dev/cu.usbmodem*                                             # CDC port
```

### 1. Sine self-test (no receiver needed)

1. Plug in the XIAO with **nothing on D7**.
2. CDC heartbeat (`pio device monitor`) should print `src=sine-test` and the 8 axes
   should sweep in a gamepad tester (<https://hardwaretester.com/gamepad>) / neXt.

### 2. Real RC decode

1. Wire the receiver per **RC receiver wiring** above; bind it to your transmitter.
2. Watch the heartbeat: it should switch from `src=sine-test` to `src=CRSF` /
   `SBUS` / `IBUS` / `PPM`, and `ch1-4us` should track your sticks (≈1000–2000,
   centre ≈1500).
3. In neXt: **settings → input device → start calibration**, move all sticks/knobs
   through full range, finish. The 8 channels should now follow your transmitter.

---

## File layout

```
platformio.ini     board + the critical USB build flags, documented
src/main.cpp        USB HID (descriptor + report), RC→axis mapping, sine fallback
src/rc_input.{h,cpp}  CRSF/SBUS/IBUS/PPM decoders + auto-detect on one pin
README.md           this file
```

---

## Assumptions / things to confirm

- **Your protocol** — auto-detect covers CRSF / SBUS / IBUS / PPM. If your link is
  something else (DSMX satellite, SUMD, SRXL2…), tell me and I'll add it.
- **Signal voltage** — assumed 3.3 V (see the ⚠️ in wiring). Confirm your RX's signal
  pad isn't 5 V before connecting.
- **Failsafe behaviour** — on link loss the axes currently fall back to the **sine
  self-test** (handy to see "no link", but it *moves the sticks*). For real flying
  you'll likely want **hold-last** or **centre** instead — easy change in
  `fillAxes()`; say which you prefer.
- **Channel→axis order** — first 8 RC channels map straight to axes 0–7. If your
  model uses a different channel order (e.g. AETR vs TAER) or you want to pick which
  8 of 16, that's a small tweak.
- **8-channel cap is neXt's**, not the device's — see the de-risking note above. The
  decoder already reads all 16 channels internally; exposing >8 needs buttons or a
  different sim.
- **CDC interface** — included for the heartbeat and easier re-flashing. Remove the
  `USBCDC USBSerial` lines for a pure-HID device.
