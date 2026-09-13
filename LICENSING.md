# Licensing

LDRC is free for other flyers, and Malcolm Messiter's wish is that every
derivative stays free too. So:

| What | Licence | In plain English |
|---|---|---|
| All code — firmware (RXV2, TXV2, LDRC2SIM), the iOS/Android apps, the web pages | **GPL-3.0-or-later** ([LICENSE](LICENSE)), with an [app-store exception](LICENSE-EXCEPTION.txt) | Use, copy, change and share it freely. If you share a changed version, you must share its source under the same licence. |
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
