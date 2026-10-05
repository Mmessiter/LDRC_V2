# Licensing

LDRC is free for other flyers, and Malcolm Messiter's wish is that every
derivative stays free too. So:

| What | Licence | In plain English |
|---|---|---|
| All code — firmware (TXV2-Screen, RXV2, LDRC2SIM), the iOS/Android apps, the web pages, the tools and tests | **GPL-3.0-or-later** ([LICENSE](LICENSE)), with an [app-store exception](LICENSE-EXCEPTION.txt) | Use, copy, change and share it freely. If you share a changed version, you must share its source under the same licence. |
| The transmitter's Teensy firmware (TXV2/TransmitterCode) | **GPL-2.0-or-later** ([TXV2/LICENSE](TXV2/LICENSE)) | The same freedoms. It is Version 1's firmware grown up, and like Version 1 it links the RF24 radio driver, which is GPL-2.0 only; so it stays at version 2 "or later" until RF24 is replaced. |
| Circuit boards (the transmitter's Proteus project and Gerbers, the KiCad files of RXV2 and TXV3) | **CERN-OHL-S-2.0** | The hardware equivalent of the GPL: build and sell boards, but published changes must stay open. |
| Manuals, help texts, the screen's pages and sounds, pictures, the case files | **CC BY-SA 4.0** | Share and adapt, credit the author, same licence for adaptations. |

Copyright (C) 2020-2026 Malcolm Messiter.

## Credits

Designed and built by **Malcolm Messiter**, with **Claude** (Anthropic's AI)
as pair programmer — the firmware, the apps, the pages and the tests were
written together, 2025–2026. The copyright line names Malcolm alone only
because the law does not let an AI hold copyright; the credit is shared.
Please keep this credit in derivatives.

Notes for anyone publishing a derivative:

- Keep this notice and the copyright line; add your own name for your changes.
- App stores are **already permitted** — you need not ask. Apple's and
  Google's terms clash with the plain GPL (that is why VLC was pulled from
  the App Store in 2011), so this project grants an additional permission
  under section 7 of the GPL: see
  [LICENSE-EXCEPTION.txt](LICENSE-EXCEPTION.txt). It is granted to
  **everybody**, not just to Malcolm, so your fork may go on an app store
  too. Its one condition is the point of the whole project: publish the
  source for whatever version you ship, free, where anyone can reach it
  without an app-store account.
- Third-party libraries keep their own licences (all permissive or LGPL,
  compatible with the GPL); see each product's `platformio.ini`,
  `Package.swift`/`project.yml` or `build.gradle.kts`.
