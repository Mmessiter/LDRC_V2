# LockDownRadioControl, Version 2

![The Version 2 transmitter](TXV2/Images/V2_transmitter.jpg)

**LDRC** is a free, open-source radio control system for model aircraft: a 16-channel
transmitter, receivers, and a phone app, all built from parts anyone can buy. Malcolm
Messiter has been developing it since the lockdown of May 2020, and he and his friends
have flown with it ever since. Version 1 lives in the
[LockDownRadioControl](https://github.com/Mmessiter/LockDownRadioControl) repository.
**This repository is Version 2**: the same radio link and the same model memories,
with a new transmitter screen and a new receiver.

If you would like to build one, Malcolm will be happy to help:
[mmessiter@gmail.com](mailto:mmessiter@gmail.com). The project's web pages are at
[messiter.com/LDRC.html](https://messiter.com/LDRC.html).

## What Version 2 is

**The transmitter** is the Version 1 transmitter with its Nextion display replaced by a
5-inch ESP32-S3 touchscreen (an Elecrow CrowPanel 5.0) that has WiFi. The Teensy 4.1
motherboard, the radio module, the gimbals and the case are unchanged, and so is
everything a Version 1 pilot knows. The screen adds:

- **Updates from the internet.** One button, *Transmitter updates*, brings the screen's
  firmware, the screen's card, the Teensy's firmware and the help texts up to date.
  A Version 2 receiver can be updated through the transmitter too.
- **A flight screen of your own.** Nine boxes, each showing what you choose: head
  speed, ESC temperature, flight battery, link quality, transmitter battery, frame
  rate, timer, channel bars, the model's picture.
- **Twelve themes**, each a panel colour with its own text colour, every one editable.
- **Model pictures from your phone**, sent to the transmitter by scanning a QR code.
- **The time from the internet**, so the log files are dated even when the clock
  module has lost its mind.
- **Pong**, for rainy days.

Model memories can still be copied, over the air, between Version 1 and Version 2
transmitters. See [TXV2/README.md](TXV2/README.md) and
[TXV2-Screen/README.md](TXV2-Screen/README.md).

**The receiver** is a Seeed XIAO ESP32-S3 with up to three nRF24L01+ radio modules
for diversity. It drives a flight controller over CRSF, SBUS, IBUS or PPM, carries
Rotorflight telemetry back to the transmitter, updates itself over the air, and has a
WiFi portal and a phone app (Bluetooth) that set up **Rotorflight** in plain English:
rates, PIDs, governor, mixer, backups, and more. The same board also works as a
**dongle** (Rotorflight from your phone with any radio) and as a **simulator
interface** (almost any receiver becomes a USB joystick for RealFlight or neXt).
It binds to Version 1 and Version 2 transmitters alike. See
[RXV2/README.md](RXV2/README.md) and [messiter.com/rotorflight](https://messiter.com/rotorflight/).

**The phone app** (iPhone, iPad, Android) talks to the receiver over Bluetooth. It is
on the [App Store](https://apps.apple.com/app/id6789857533), on
[TestFlight](https://testflight.apple.com/join/6yzhGxae) for testers, and for Android at
[messiter.com/apps](https://messiter.com/apps/). Source in [RXV2App](RXV2App).

## What is in this repository

| Folder | What it is |
|---|---|
| [TXV2](TXV2) | The transmitter: Teensy 4.1 firmware, help texts, sounds, the case (STL and STEP), the circuit board (Gerbers), the change log |
| [TXV2-Screen](TXV2-Screen) | The transmitter's screen: ESP32-S3 firmware, the card's contents (pages, fonts, pictures, sounds), the tools and tests |
| [RXV2](RXV2) | The receiver (and dongle, and simulator interface): firmware, web pages, KiCad boards |
| [RXV2App](RXV2App) | The iOS and Android app |
| [TXV3](TXV3) | Notes and KiCad files for a future transmitter with its own boards. Parked: Version 2 turned out so well that it may wait a long time |

TXV2 and TXV2-Screen are published as snapshots of Malcolm's working repositories, refreshed with every release. The working trees hold nothing more than what is here except WiFi passwords, which are kept out of everything that is published.

## Getting started

Each part has its own README with the parts, the wiring, how to build and flash, and how it updates itself afterwards:

1. **Transmitter**: [TXV2/README.md](TXV2/README.md). Build the Teensy firmware with PlatformIO and flash it over USB, once; make its card; fit the screen.
2. **Screen**: [TXV2-Screen/README.md](TXV2-Screen/README.md). Flash the screen over USB, once, with an empty card in it; give it your WiFi; it fills its card and updates itself from the internet.
3. **Receiver**: [RXV2/README.md](RXV2/README.md). Flash a XIAO ESP32-S3 over USB, once; wire the radio modules and the flight controller; everything after that is over the air.

Released firmware, for the transmitter's own *Transmitter updates* button and the receiver's, is served from messiter.com: [txv1b/release](https://messiter.com/txv1b/release/) and [rxv2/release](https://messiter.com/rxv2/release/).

## Licence and credits

Free for other flyers, and derivatives must stay free: code is **GPL-3.0-or-later**
(see [LICENSE](LICENSE)), except the transmitter's Teensy firmware, which stays
**GPL-2.0-or-later** like Version 1; boards CERN-OHL-S-2.0; manuals and help texts
CC BY-SA 4.0.
Built by Malcolm Messiter with Claude (Anthropic's AI) as pair programmer. Details,
including the app-store permission, in [LICENSING.md](LICENSING.md).
