# LDRC2SIM is retired (2026-09-18)

Its whole job now lives in the RXV2 firmware as a dongle role.

Malcolm, 2026-09-18: *"Some time ago, we created a simulator only dongle. I
think this project can be abandoned now in favour of the rotorflight dongle
that doubles as a simulator dongle."*

**What replaced it.** RXV2 0.9.757 adds **Mode → Simulator interface** on the
dongle page. A board with no radio, with a receiver wired to it, decodes
CRSF / SBUS / IBUS / PPM and presents the same USB HID joystick. The decoder
here (`src/rc_input.*`) was ported verbatim to `RXV2/src/RcInput.h`; the
joystick was already in `RXV2/src/SimUsb.h`. One board, one firmware, three
roles: receiver, Rotorflight dongle, simulator interface — plus the axis map,
reversing, spool-up realism and camera keys the RXV2 pages already had, which
this firmware never offered.

**Wiring changed by one pin:** LDRC2SIM listened on **D7**; the RXV2 role
listens on **D5**, so the dongle's existing four-wire lead is reused with its
flight-controller end moved to the receiver (signal → D5, 5 V → the board's
5V pin, ground → ground).

**Nothing is being taken away.** The published OTA area stays up for anyone
running it: <https://messiter.com/ldrc2sim/release/manifest.json>, releases to
1.0.12 in `dev/`. The source stays here for reference. There will be no new
LDRC2SIM releases; flash such a board with RXV2 and choose the role instead.
