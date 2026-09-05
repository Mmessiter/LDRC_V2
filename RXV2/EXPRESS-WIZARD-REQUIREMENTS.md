# Express wizard — requirements sketch (2026-09-05)

Goal: a new helicopter flying in about ten minutes on the phone, as quick and
easy as a Mikado VBar NEO — after ONE computer session the FC will always need.
Every step is either something only the user can do (physical), one question
that sets many things, or a silent default. Every physical step is verified
live by the receiver (the phone shows what the FC actually sees), and the user
types numbers only twice: gear teeth and motor poles.

## Three buckets

- **MUST-DO (user, physical)** — cannot be defaulted: wiring, bind, orientation,
  servo directions/centres, collective range, tail direction, channel learning,
  gear teeth + poles, blades-off spool check.
- **ONE QUESTION → many settings** — size class, swash type, ESC brand,
  "copy from a previous model?".
- **SILENT DEFAULTS** — everything else; the full wizard / À la carte remains
  for anyone who wants control.

## The flow (order matters — each step verifies the one before)

0. **Prepare the FC (computer, once):** Rotorflight firmware, receiver port =
   CRSF with telemetry ON. Skipped automatically when the receiver already
   sees a Rotorflight FC on CRSF.
1. **Name + size + copy?** — name; size class (280 · 380 · 450 · 500 · 550 ·
   600 · 700 · 800 by blade length); optional "copy from <previous model>"
   (portable backup + declared items). Size sets: PIDs (3 banks: stable /
   sport / 3D), rates, filters, governor gains, head speeds, rescue, cyclic
   ring, I-term relax, cross-coupling. ONE QUESTION.
2. **Bind the transmitter** — MUST-DO (skipped if already bound).
3. **Which way is the board mounted?** — pick the arrow; then tilt the heli and
   watch the live attitude agree. MUST-DO, verified live.
4. **Motor & ESC** — ESC brand (Scorpion · Hobbywing · YGE · Castle · other) sets
   telemetry protocol + half-duplex + governor mode (electric, external);
   main gear / pinion teeth + motor poles typed; the receiver reads RPM back
   and shows head speed. ONE QUESTION + the only typing.
5. **Swash & servos** — swash type (CCPM 120 · 140 · mechanical); plug servos
   in the wizard's order; the wizard moves each servo, user taps "right way /
   reversed"; centres by eye with the links level; collective range with the
   pitch gauge at max and min (the wizard writes the limits); cyclic ring
   default 10°. MUST-DO, verified live (Travel extents machinery).
6. **Tail** — direction check (nose left → tail servo response shown), servo
   end-points against the mechanical stops. MUST-DO.
7. **Transmitter channels — learned by movement** — "move the throttle",
   "move roll" … the receiver watches which channel moves (order learned, no
   dropdowns); then flip the arm switch, the bank switch, the rates switch,
   the rescue switch (or skip). Positions counted automatically. MUST-DO but
   nearly effortless — this is where we beat NEO.
8. **Head speeds** — from the size table per bank, editable; reminder that the
   throttle must be 100 % in every bank (Rotorflight's governor needs it).
   ONE QUESTION (accept or edit).
9. **Safety & proof** — arming-disabled reasons read from the FC and explained;
   blades-off spool check with the RPM live; volts + RPM visible on the
   transmitter; failsafe posture verified. Automated where possible.
10. **Backup + first-flight card** — automatic phone backup, then the
    first-flight checklist (bank 1, hover, trims).

## Silent defaults (never asked)

Features ticks; telemetry sensor list + fast link speed; arm/rescue thresholds
(1500); blackbox setup; filters by head speed; PID banks by size; rates by
size; governor gains; rescue settings; battery cells (FC detects); voltage
divider; beeper/LED off; default mixer rules; servo rates/frequencies by servo
class (asked only if not standard).

## Success measures

- ≤ 10 min after the computer session, ≤ 12 screens.
- No numeric typing except gear teeth and motor poles.
- Every physical step confirmed by the FC's own reading, not by trust.
- A wrong answer is recoverable: each step can be redone alone.

## Open questions for Malcolm

- Size classes: by blade length (as above) or by "class" names?
- Servo classes: ask (standard / high-speed / narrow-pulse) or default to
  standard and warn?
- Does Express live beside the full wizard (recommended) or replace it?
- Which ESC brands first? Scorpion is proven; Hobbywing next?

## Depends on

- The size-based PID/rates/head-speed table (desk draft, then field
  confirmation: Goblin 770, RAW 420, Goblin Havok).
- Channel learning by movement (new receiver feature).
- Live attitude readout on the phone (MSP 108 already read for the sim).
