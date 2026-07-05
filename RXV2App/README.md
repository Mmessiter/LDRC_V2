# RXV2App — configure the receiver over Bluetooth from an iPhone

The receiver's own web interface, carried over Bluetooth LE instead of WiFi.
No network switching, no captive-portal fights: power the receiver (TX off),
open the app, tap the receiver's name, and the familiar pages appear.

The WiFi web portal is completely unchanged — this is a second door to the
same configuration engine (firmware 0.9.206+, `src/BleConfig.h`).

## How it works

- All the portal's static pages and assets (`RXV2/data/`) are **bundled in
  the app** (`webroot/`) and load instantly from local storage.
- Only the small dynamic calls — `/api/*.json` polls and the POST actions —
  cross Bluetooth, using an HTTP-over-BLE framing to the firmware's NimBLE
  service. The same C++ handlers serve WiFi and BLE.
- BLE follows the flying rules WiFi already obeys: it never comes up if the
  TX was heard at boot, and **Fly mode switches it off** along with WiFi.

## Building onto your iPhone (free Apple ID — no paid account)

1. `cd RXV2App && xcodegen generate` (only needed after editing project.yml;
   the generated `RXV2App.xcodeproj` is committed).
2. Open `RXV2App.xcodeproj` in Xcode.
3. Target **RXV2App → Signing & Capabilities**: tick *Automatically manage
   signing* and choose your **Personal Team** (your Apple ID).
4. Plug in the iPhone, pick it as the run destination, press **Run**.
5. First time only, on the phone:
   - Settings → Privacy & Security → **Developer Mode** → on (reboots).
   - Settings → General → VPN & Device Management → **trust** your Apple ID.

Free-signing limits: the app expires after **7 days** (press Run again to
refresh it) and at most 3 such apps per Apple ID.

## Updating the bundled web pages

The app carries a copy of `RXV2/data/`. After changing the portal pages:

    rm -rf RXV2App/webroot && cp -R RXV2/data RXV2App/webroot

then rebuild in Xcode. (A stale bundle still works — any page missing from
the bundle is fetched over BLE from the receiver instead.)
