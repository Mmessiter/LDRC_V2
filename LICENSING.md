# Licensing

LDRC is free for other flyers, and Malcolm Messiter's wish is that every
derivative stays free too. So:

| What | Licence | In plain English |
|---|---|---|
| All code — firmware (RXV2, TXV2, LDRC2SIM), the iOS/Android apps, the web pages | **GPL-3.0-or-later** ([LICENSE](LICENSE)) | Use, copy, change and share it freely. If you share a changed version, you must share its source under the same licence. |
| Circuit boards (KiCad schematics and layouts, when published) | **CERN-OHL-S-2.0** | The hardware equivalent of the GPL: build and sell boards, but published changes must stay open. |
| Manuals, help text, pictures | **CC BY-SA 4.0** | Share and adapt, credit the author, same licence for adaptations. |

Copyright (C) 2026 Malcolm Messiter.

## Credits

Designed and built by **Malcolm Messiter**, with **Claude** (Anthropic's AI)
as pair programmer — the firmware, the apps, the pages and the tests were
written together, 2025–2026. The copyright line names Malcolm alone only
because the law does not let an AI hold copyright; the credit is shared.
Please keep this credit in derivatives.

Notes for anyone publishing a derivative:

- Keep this notice and the copyright line; add your own name for your changes.
- Apple's App Store terms clash with the GPL, so a GPL app can only go on
  the App Store with the copyright holder's permission. Ask, if you want to
  publish an app-store build of the RXV2 app.
- Third-party libraries keep their own licences (all permissive or LGPL,
  compatible with the GPL); see each product's `platformio.ini`,
  `Package.swift`/`project.yml` or `build.gradle.kts`.
