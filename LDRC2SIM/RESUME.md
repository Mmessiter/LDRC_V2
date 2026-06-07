# LDRC2SIM — session resume note (updated 2026-06-07)

Read this first when resuming. The messiter.com OTA task is **DONE**; only the
device flash (rollout step) remains.

## DONE — firmware now updates from messiter.com
LDRC2SIM publishes OTA updates to **messiter.com** the same way **RXV2** and
**ReedMachine** do. What was wired up:

- **Live:** `https://messiter.com/ldrc2sim/release/manifest.json` (12 versions,
  newest first) + `release/vX.Y.Z/firmware.bin`. Verified 200 + Content-Length,
  no redirect — so both the device "check" and "install" paths work.
- **Firmware** (`src/web_portal.cpp`): `FW_PUBLIC_MANIFEST` now points at that
  URL (was `""`); `FW_VERSION` bumped to **LDRC2SIM-1.0.11**, built.
- **Publish tooling** (in `dev/`): `stage_website.py` builds
  `NewWebSite/public_html/ldrc2sim/release/` + `manifest.json` from `dev/*.bin`;
  `publish_website.sh` FTP-mirrors it to messiter.com (creds in the gitignored
  `dev/ftp_credentials.sh`); `release_notes.json` holds the short per-version notes.

### Rollout — done
The dongle now runs **v1.0.12** (messiter.com OTA + the animated install progress
bar), flashed OTA and verified reading messiter.com (13 versions live). Standing
preference going forward: always flash the newest build OTA once it's ready.
Nothing committed yet — commit when ready (`dev/ftp_credentials.sh` stays
gitignored).

### Animated install progress bar (v1.0.12)
Client-side only — the OTA flash path is untouched. On the Firmware page, tapping
Install/Reinstall/Roll back shows a green striped bar that trickles toward ~95%
(with a live %) for motion, then snaps to 100% when the device replies and reboots.
The install is one blocking call on the device, so true byte-progress isn't
available; the trickle + animated stripe give the motion. All in `inst()` /
`.pbar`/`.pfill` CSS in `src/web_portal.cpp`.

### To publish a future release
Bump `FW_VERSION`, `pio run -e seeed_xiao_esp32s3`, copy the bin to
`dev/LDRC2SIM-x.y.z.bin`, then `python3 dev/stage_website.py && dev/publish_website.sh`.

### Manifest format the device expects
`/api/firmware/check` merges a local + a public manifest. Each must be:
```json
{ "versions": [ { "name": "LDRC2SIM-1.0.10", "url": "/path/LDRC2SIM-1.0.10.bin",
                  "size": 1008016, "mtime": 1733570000 }, ... ] }
```
- `name` must parse as `LDRC2SIM-x.y.z` (drives newer/older/current tagging).
- `url` may be relative; the page resolves it against the manifest URL.
- See `dev/firmware_server.py` (the working local example, port 8001).

### Gotchas
- `FW_PUBLIC_MANIFEST` was disabled because a **blocking HTTPS fetch that 404'd
  hung the single-threaded web server** (felt like a crash when leaving the
  Firmware page). The fetch now has an 8 s timeout and only runs on the Firmware
  "check" action (not during flight), but make sure the URL returns **200** and
  is reachable. HTTPS uses `WiFiClientSecure.setInsecure()` (no cert check).
- Keep the local server source working too; both cards can show at once.

## Where we are (state at end of this session)
- **Path**: `/Users/malcolmmessiter/Documents/GitHub/LDRC2SIM`
- **Firmware**: **v1.0.12** built, flashed OTA, and live on the dongle (messiter.com
  OTA + animated install progress bar). Git branch **`wifi-portal`**; the
  messiter.com + progress-bar work is uncommitted in the working tree.
- **Device**: on home Wi-Fi at **`http://LDRC2SIM.local`** (DHCP, was
  `192.168.1.174`; `.local` is the stable handle). USB CDC serial port
  `/dev/cu.usbmodemLDRC_P1_0005…` for the debug heartbeat (115200).
- **OTA push** (works): `curl -F update=@dev/LDRC2SIM-1.0.10.bin http://LDRC2SIM.local/update`
- **Local firmware server**: `python3 dev/firmware_server.py` (port 8001);
  manifest `http://m4macmini.local:8001/manifest.json`. Release bins
  `dev/LDRC2SIM-1.0.0 … 1.0.10.bin`.

### Features complete & confirmed flying
- USB HID 8-axis joystick in **RX2SIM channel order** (hidden baseline:
  throttle/rudder swap + rudder reverse + neXt +2 axis rotation).
- Auto-detect **CRSF / SBUS / IBUS / PPM** on pin **D7 (GPIO44)**; failsafe-holds
  last positions on link loss.
- **Wi-Fi AP/STA portal** (AP "LDRC2SIM"), house-style web UI, **web OTA**.
- **Remap channels** page (v1.0.8): feed any of 8 USB outputs from any of 16 RX
  inputs + per-output reverse; default reads as tidy 1:1 ("unmapped") but flies
  like RX2SIM; saved to NVS. Inputs shown as colour bars.
- **Low latency** (v1.0.10): event-driven HID reports (sent the instant a CRSF
  frame decodes, sub-ms; 1 kHz cap). User confirms motor on/off is immediate.
- **Wi-Fi reconnect watchdog** (v1.0.10): 10 s retry of `WiFi.begin()` while STA
  is down + mDNS restart on GOT_IP. Fixed the recurring "stuck in AP-only".

### Build flags that MUST stay (platformio.ini)
- `ARDUINO_USB_MODE=0` (TinyUSB; board default 1 disables it),
  `ARDUINO_USB_CDC_ON_BOOT=0`, `board_build.partitions = default_8MB.csv`.
- USB identity: VID `0x1209` / PID `0x525C` / serial `LDRC-P1-0005`.

### Reference material on disk (gitignored)
- `RXV2 copy/` and `ReedMachine copy/` — sibling projects whose **website
  auto-update** and house-style web UI we mirror. RXV2 has `data/style.css`,
  `app.js`, `src/WebPages.h` (firmware check/install), `dev/firmware_server.py`.

### Parked (other than the website task)
- Merge `wifi-portal` → `main`.
- First-motor-on lag: believed to be the sim's spool-up model, not firmware.
