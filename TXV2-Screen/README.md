# The Version 2 transmitter's screen

<img src="../docs/images/tx-defined-screen-9-boxes.png" width="600" alt="A front screen with nine boxes: timer 4:07, both batteries at 3.91 and 4.05 volts a cell, head speed and ESC temperature as round dials, link 97 per cent, capacity used 345 mAh, current 12.4 A, the clock and the bank">

<sub>A front screen of your own: up to nine boxes. Six come ready-made. Drawn by this firmware's own code. Sample values.</sub>

**The screen is Elecrow's 5-inch IPS panel** (or the older CrowPanel 5.0) with this firmware on it. **Nothing to compile:** [flash it from your web browser](https://messiter.com/ldrc/flash-screen.html).

- **What the panel is:** an ESP32-S3 (N16R8: 16 MB flash, 8 MB PSRAM; the older board N4R8, 4 MB flash), a 5-inch 800 × 480 display, GT911 touch, WiFi, Bluetooth, an NS4168 speaker amplifier, a microSD slot and a serial port on the back.
- **Buy the 16 MB screen:** Elecrow's **5-inch IPS panel, SKU DLE06050B** (16 MB flash): the firmware's FULL build, with room to spare. New features need it. The older **CrowPanel 5.0, SKU DIS07050H, N4R8** (4 MB flash) is full: since November 2026 it gets fixes only, no new features. Do not buy it for a new transmitter. The firmware tells them apart at start-up. Not Elecrow's "Advance" series: its card slot and speaker are on other pins.
- **What the firmware does:** it pretends to be the Nextion display that Version 1 used. The Teensy 4.1 sends the same display commands it always has (921,600 baud). The screen draws the transmitter's 90 pages from their definitions on its card, and answers with exactly the bytes a Nextion would.
- **On top of that it has pages of its own:** updates from the internet, WiFi, themes, six ready-made front screens with round dials (each yours to change), the picture chooser, Rotorflight's command line, the help animations, and Pong.
- **It is also the Bluetooth link to the receiver.** All Rotorflight editing on the transmitter goes over it, not over the flying link.
- **Building a transmitter?** Start with [../TXV2/README.md](../TXV2/README.md) and [Build one](https://messiter.com/ldrc/build.html).

---

## Flash it once, then it updates itself

1. **Put a blank microSD card**, formatted **FAT32**, in the panel's slot **before** you power it. The card is read at power-up only.
   - Use a card of **32 GB or less**. Larger cards come as exFAT, which the screen cannot read; reformat them FAT32 if you must use one.
2. **Flash it from your web browser**, before the screen is wired to the Teensy. There is nothing to install or compile.
   - Plug the panel's USB-C socket into a computer with a **data** cable.
   - Open [messiter.com/ldrc/flash-screen.html](https://messiter.com/ldrc/flash-screen.html) in Chrome, Edge or Opera, and press **Flash this screen**.
   - The page finds out which screen it is, 16 MB or 4 MB, and writes the right firmware. It takes about a minute.
   - The panel's USB-C port is a CH340 serial chip. A Mac or a Windows PC may need its driver.
3. **First start.** The first line on the glass reads `LDRC V2 screen sd=1 pages=0 touch=1`: a healthy fresh screen with a blank card (no pages yet: the first fetch brings them). The update panel opens by itself and says *No WiFi yet*.
   - Tap **WiFi setup**. Pick your network and type its password on the screen. The password is kept in the chip, never on the card.
   - Once it has WiFi, the screen fetches the latest release by itself: about 430 files, about 230 MB, most of them the help animations. If it asks first, press **Install now**.
   - That takes about 15 minutes on the 16 MB screen, and about half an hour on the older 4 MB one. It then restarts as a complete screen, and the first line counts its pages (`pages=90` or so).
   - With `sd=0`, the line under it (*Card: ...*) says what the screen found on the card and what to do. `touch=0` means the touch chip did not answer.
   - (Or copy what is inside `sd/`, the folders `hmi` and `images`, to the top of the card first. The screen then shows `pages=90` and waits for the Teensy (step 4); later, *Transmitter setup → Transmitter updates* fetches only what differs. The animations themselves, `sd/hmi/films/*.ldf` and
     their sound, `*.ima` (or `*.wav`), are not kept in this repository: they are large and remade from scripts, and the
     release on messiter.com carries them.)

   **Prefer to build it from source?** Install [PlatformIO](https://platformio.org/), then, in place of step 2:

   ```
   cd TXV2-Screen
   pio run -e ips16 -t upload --upload-port /dev/cu.usbserial-XXXX         # the 16 MB screen
   pio run -e crowpanel50 -t upload --upload-port /dev/cu.usbserial-XXXX   # the older 4 MB screen
   ```

   `pio device list` names the port. The panel resets itself, so no button-pressing is needed. `platformio.ini` pins the ESP32 platform to **espressif32 7.0.1** (Arduino core 2.0.17): a newer platform brings the core 3 and the display library does not compile with it (errors inside `GFX Library for Arduino`, such as `'esp_lcd_rgb_panel_frame_trans_done_cb_t' does not name a type`). If you built before 2 Nov 2026 and see those, pull, delete the project's `.pio` folder and build again.
4. **Connect it to the Teensy**, on the Version 1 board's Nextion header:

   | Screen port J10 (HY2.0, 4-pin) | Goes to |
   |---|---|
   | Pin 1: IO44, the screen's RX | Teensy pin 1 (TX1) |
   | Pin 2: IO43, the screen's TX | Teensy pin 0 (RX1) |
   | Pin 3: 3.3 V **output** | Nothing. Leave it unconnected |
   | Pin 4: GND | Ground |

   - Both sides are 3.3 V logic.
   - **Power the panel with 5 V through its USB-C socket** (a cut USB-C lead from the board's screen rail). The pins of its ports are outputs, not power inputs.
   - Find the cut lead's + and − with a meter: colours vary.
   - **Never two power supplies:** do not plug a computer into the USB-C socket while the screen is wired to the board.
   - The **speaker** goes on the SPK socket.
   - Why flash first: the serial port on J10 is shared with the USB chip. A USB cable would fight the Teensy.

From then on the transmitter updates itself: *Transmitter setup → Transmitter updates.*

<img src="../docs/images/tx-update-fetching.png" width="500" alt="The Fetching the update panel: Fetching 13 of 21, About 3 minutes left, a green progress bar and a Cancel button">

<sub>One press. A newer release is fetched and installed straight away; an earlier version asks first. An illustration: the numbers are examples.</sub>

At power-up, on a WiFi it knows and with no model connected, the screen looks for a newer release and tells you: *Update ready*. Nothing is installed until you press **Transmitter updates**.

---

## What is in this folder

| | |
|---|---|
| `src/main.cpp` | The emulator: the serial protocol, the pages and their parts, the script interpreter's host, drawing, touch, WiFi, the web tools, the workshop door |
| `src/*_device.h`, `src/*_draw.h` | The screen's own pages (update, wifi, pics, flight, theme, cli, pong) and the Bluetooth link (`ble_device.h`): the part that touches the hardware, and the drawing |
| `lib/Ldrc*` | The same pages' thinking, in portable C++ with no Arduino in it, tested on a Mac: `LdrcUpdate`, `LdrcWifi`, `LdrcPics`, `LdrcFlight`, `LdrcTheme`, `LdrcCli` (Rotorflight's command line through the receiver's USB cable), `LdrcBle` (the receiver's Bluetooth bridge, as the screen speaks it), `LdrcLink` (the framed file link to the Teensy, identical to the Teensy's copy) |
| `lib/NextionScript`, `lib/NextionFonts` | The interpreter for the pages' own event code, and the Nextion font format |
| `sd/` | **Everything on the screen's card:** `hmi/pages/*.json` (the pages), `hmi/pic/` (their pictures), `hmi/font*_aa.bin` (the fonts), `hmi/audio/` (the sounds), `hmi/web/` (the pages a phone sees), `images/` (model pictures) |
| `hmi/` | How `sd/` is made: `extract_hmi.py` decodes the Version 1 Nextion project, `build_sd.py` writes the card, `pagestyle.py` and `overrides.json` restyle the pages, `render_host/` draws any page on a Mac, `test_*/` are the host tests, `README.md` documents the Nextion file format |
| `dev/` | Tools used from a computer with the workshop door open: `teensy_ota.py` (the Teensy through the screen: hello, install, backup, restore, roll back), `screen.py`, `nextion_send.py`, `preview_page.py` |
| `platformio.ini` | The builds |

---

## Safety

- **The screen's radios are off whenever the model could be flying.** The Teensy says so on the wire (`ldrcst=`), and the screen obeys. That covers WiFi and Bluetooth.
- **No update, file transfer or firmware** is accepted while a model is connected.
- **The Teensy's new firmware installs on trial.** If it does not stay up, the old one comes back by itself.
- **The screen's own new firmware** must talk to the Teensy and rejoin WiFi, or it rolls back.
- **No passwords are published.** WiFi passwords are typed on the screen and kept in the chip.

## The workshop door

A published screen answers nothing on the network except `GET /status`, and accepts no firmware from a computer, until you open its **door**.

- **Open it:** press *Workshop door* in *Transmitter setup*, or hold the top-right corner of the screen for three seconds. Do the same again to shut it.
- It stays open on that one network only, and is shut on every other network. That keeps it safe on a club WiFi.
- With the door open, from the same WiFi:

```
pio run -e ota_full -t upload --upload-port <the screen's IP>   # firmware over the air (`ota` for the 4 MB screen)
python3 dev/teensy_ota.py hello                              # the Teensy, through the screen
python3 dev/screen.py --help                                 # screenshots, pages, the log
```

- Every POST to the screen needs the header `X-LDRC: 1`.
- `/status` gives the screen's version, WiFi and card. `/bootlog` and `/recent` are its logs.

---

## The wire

Besides the Nextion protocol, a few words pass between the boards on the same serial line.

| Direction | Words | Meaning |
|---|---|---|
| Teensy → screen | `ldrcst=<bits>` | The transmitter's state: model connected, motor armed, safety, and so on |
| Teensy → screen | `ldrcrx=...` | The connected receiver's version and update progress, once a second |
| Teensy → screen | `pong=x,y,ly,ry`, `pong=start` | Pong's ball and paddles, once a frame. The screen draws it smoothly |
| Teensy → screen | `ldrcpipe on <id>`, `ldrcpipe off` | Open or close the Bluetooth link to the receiver with that ID |
| Teensy → screen | `ldrctx <words>` | A Rotorflight parameter packet, to send over the Bluetooth link |
| Teensy → screen | `ldrcreq <id> <path>` | A question for the receiver over the Bluetooth link (its raw Rotorflight line, above all) |
| Screen → Teensy | `ldrcpipe=<state>` | How the Bluetooth link is doing |
| Screen → Teensy | `ldrctel <item>:<hex> ...` | The receiver's answer, as telemetry items |
| Screen → Teensy | `ldrcrep <id> <code> <body>` | The receiver's answer to `ldrcreq` |
| Screen → Teensy | `ldrc update`, `ldrc rxupdate`, `ldrc wifi`, `ldrc appearance`, `ldrc colours`, `ldrc flight`, `ldrc defined`, `ldrc cli`, `ldrc diff`, `ldrc exec`, `ldrc door` | The screen's own buttons, placed on the Teensy's pages by `hmi/overrides.json` or its page generators. The screen acts on them itself |
| Screen → Teensy | `TIME=<epoch>` | The local time, from the internet. The Teensy sets its clock module from it |
| Screen → Teensy | `LDRCLINK` | Opens the framed file link (`lib/LdrcLink`): files on the Teensy's card, and firmware |
| Screen → Teensy | `LDRCRXUP major minor patch` | Orders the connected receiver to update itself |
| Screen → Teensy | `LDRCIMG <name>` | The picture chosen for the model |

## Tests and the renderer

- `hmi/test_all.sh` runs every host test and the release tool's gate. They need a C++ compiler, nothing else.
- `hmi/render_pages.py` draws every page with the screen's own drawing code on a Mac, so a change is seen before it goes near a transmitter.
- `hmi/lint_pages.py` looks for overlaps and clipped text.

## Builds in platformio.ini

| Build | What for |
|---|---|
| `ips16` | **The 16 MB screen:** the FULL build, flashed over USB |
| `ota_full` | The same, pushed over WiFi (door open). This is the published firmware for the 16 MB screen |
| `crowpanel50` | **The older 4 MB screen:** the STANDARD build, flashed over USB |
| `ota` | The same, pushed over WiFi (door open). This is the published firmware for the 4 MB screen |
| `ota_dev`, `ota_full_dev` | Bench builds that call themselves `dev`, so the transmitter always offers the published one over them |
| `ota_test_fail_trial`, `ota_test_fall_over` | Builds meant to fail, to prove the roll-back |
| `ota_seed`, `usb_seed`, `usb_seed_full` | Malcolm's bench builds. They need an `include/secrets.h` with his networks, which is never published. **Use `ips16` or `crowpanel50`** |

The firmware tells the two screens apart at start-up. A screen on the 16 MB layout takes only the builds made for 16 MB.

## Licence

- Code: GPL-3.0-or-later. The screen's pages, pictures and sounds: CC BY-SA 4.0. See [../LICENSING.md](../LICENSING.md).
- Third-party libraries (Arduino GFX, SensorLib, ArduinoJson, NimBLE-Arduino) keep their own licences.

Copyright (C) 2026 Malcolm Messiter. Made with Claude (Anthropic's AI) as pair programmer.
