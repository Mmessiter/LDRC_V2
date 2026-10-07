# Transmitter Version 1B: updates without opening the case

The 5-inch screen has WiFi. Through it the whole transmitter is updated:

- the **screen's firmware** and the **screen's card** (pages, fonts, sounds, model images),
- the **Teensy's firmware**, and
- the **files on the Teensy's SD card** (help texts; backups of the models)

— the last two over the wire that already carries the display protocol.

**Flying comes first.** Nothing is begun, nothing is changed and nothing is restarted while a model is connected,
or while the screen's radios must be off (below). (A minute's wait after the model is switched off was tried on
30 Sep and taken out the same morning: Malcolm found it unnecessary and frustrating.) Nor while a question is on screen, or the
radio is calibrating or scanning.

Two ways in: **the button on the transmitter** (from messiter.com, no computer), and the Mac (for development).

## On the transmitter: Transmitter > Check for update

Nothing is ever offered or done by itself. The pilot presses **Check for update** on the *Transmitter setup* page:

| The panel says | What it means |
|---|---|
| **Up to date** | Both versions are shown. **OK**, or **Earlier versions**. |
| **Update available** | What would change (now / new) and the release's note. **Install now**, **Later**, or **Earlier versions**. |
| **Choose a version** | The latest release and the three before it, the one installed marked. Touch one: what would change is shown, then **Install now** or **Back**. |
| **Fetching the update** | Everything is fetched to the screen's card first, each file checked. **Cancel** is still possible: nothing has been changed. |
| **Updating ... Do not switch off** | The Teensy (about 80 s, with its trial), then the screen's files, then the screen's firmware and a restart. |
| **Update complete** (green) | Both versions. OK. |
| **Update failed** (red) | Where it stopped, why, and what state things are in. |

Rules it keeps:

- **Flying comes first:** refused, with the reason and what to do (*The safety is off: put the safety on, then check again*;
  *A model is connected*). This is looked at before every step that changes
  anything, not only at the start: an update that has fetched everything stops if the pilot arms, and the screen does not
  restart in flight. A panel that waits for OK steps aside when flying begins; a note that says *why* nothing can be done stays
  four seconds first. No keep-awake is sent to a transmitter that flies.
- **New firmware must read the model's settings as the old one did.** When it says who it is, the Teensy gives a fingerprint of
  everything that decides what the sticks and switches do to the servos, as its firmware holds it in memory (`mfp=`,
  `FlightGuard.h`: end points, curves, mixes, trims, sub-trims, reversed channels, which stick and which output is which,
  rates, expo, failsafe, motor and arming channels, servo pulses, stick calibration, switches). What is in memory is saved
  to the card on the way into the link, as at power-off, so the new firmware reads exactly what the old one held. After the
  restart the two fingerprints are compared. **If they differ the new firmware is not kept:** the previous one is put back at
  once, the screen is left alone, and the red panel says why. If it could not be put back (the pilot armed meanwhile), the
  panel says **DO NOT FLY** and stays until OK is pressed. Firmware older than 2.5.6 B8 gives no fingerprint: the green
  panel then says that nothing could be compared.
- **Fetch first, change later.** A failed download changes nothing. What was fetched is kept and not fetched again.
- **The transmitter does not switch itself off in the middle.** The Teensy cannot see touches on the panel, so while work goes
  on the screen tells it every 20 s that someone is here (its screen saver and its inactivity power-off start counting again).
  While the Teensy serves files it never powers off by itself, and it restarts both clocks when the session ends.
  A panel that only waits for OK keeps the transmitter awake for three minutes, no longer: a transmitter left on still goes off.
- **The verdict is never lost.** It stays until OK is pressed; switched off before that, it is shown at the next power-on.
  An update cut short by the power button says so at the next power-on ("Update not finished").
- **Both firmwares have to earn their place.** The Teensy: 30 s of running as a transmitter, else its previous firmware comes back
  by itself (below). The screen: it must talk to the Teensy and join the WiFi again, else the boot loader brings the previous firmware
  back, and that one says what happened.
- The record is on the screen's card: `/update/log.txt` (`curl "http://<screen>/file?path=/update/log.txt"`).

**Going back is as easy as going forward.** An earlier version is installed the way an update is: the pilot's files are
copied first, both firmwares go on trial, the pages and sounds of that release come back with it. Afterwards
"Check for update" offers the latest again. (A release older than 1.2.0 has no "Earlier versions" of its own, and none older
than 1.1.0 is offered: those held the house's WiFi password and were withdrawn.)

A new screen with an empty card fills itself the same way (40 MB, a few minutes): flash its firmware once by USB, press the button.

## The receiver's update: Model setup > Receiver update (B11+, screen 1.4.0, receivers 0.9.864+)

Malcolm, 30 Sep 2026: *"If a receiver is connected when I hit check for update, I think it would be wonderful if we could
check for a receiver update! And we could install it without having to open the app."* And, that afternoon: *"the transmitter
section should only update the transmitter, and the button should be greyed out if there is a receiver connected. Under the
model section add an update-the-receiver button, greyed out if a receiver is not connected."* So (screen 1.4.0): **Check for
update** on *Transmitter setup* does the transmitter and screen, greyed out and deaf while a model is connected; **Receiver
update** on *Model setup* (bottom left) does the connected receiver, greyed out and deaf without one. (A page component with
`"need": "model"` or `"nomodel"` in its JSON is governed by the main board's `ldrcst`; a main board that says nothing leaves
it usable.) The receiver's button:

| The panel says | What happens |
|---|---|
| **Checking the receiver** | The screen joins the WiFi and reads the receivers' release list (`messiter.com/rxv2/release/manifest.json`). The receiver's own release number comes through the Teensy (`ldrcrx=`, from telemetry item 39). |
| **Receiver up to date** / **Receiver update available** | *Receiver 0.9.863 → 0.9.870*, the release note, **Install now** or **Later**. |
| **The receiver did not say its version** | A receiver older than 0.9.864 (or a Teensy older than B11). Update it once with the phone app; from then on the transmitter can. |
| **Receiver update** (working) | *Asking the receiver* → *The receiver is updating itself. Transmitter silent for 1:23 more* → *Waiting for the receiver to come back*. Big and bold: **Keep the model on, safety on**. |
| **Receiver updated** (green) | The receiver is back and says the number wanted. |
| **Receiver not updated** (red) | Why, in the receiver's own words when it has them (*could not join its WiFi network: at the field, give it your phone's hotspot on the app's WiFi page*), and *Nothing was changed*. |

How it goes, and why it is safe (`TransmitterCode/include/RxUpdate.h`, RXV2 `src/TxParams.h` and `rxUpdStep()` in `WebPages.h`):

1. The screen sends `LDRCRXUP 0 9 870` on the wire. The Teensy refuses it outright unless a model is connected, the motor is
   off and the safety is on (the same rule as for everything else, `RadiosMustBeOff()`).
2. The Teensy sends **parameter 35** (321, major, minor, minimus, 321) over the radio. The receiver answers in **telemetry
   item 40**: accepted, refused because the model is armed (its arming channel, or its flight controller's own word), or
   refused because it knows no WiFi network. No answer in 10 s = an older receiver.
3. Accepted: **the Teensy goes silent** for the time the receiver asks (90 s). The receiver never installs anything under a
   live link (the standing rule of its install endpoint); the transmitter's silence is its consent, and if the transmitter
   never goes quiet the order lapses after 60 s. No "Disconnected" voice, no log line: the comings and goings are ours.
4. The receiver switches Bluetooth off, joins **the one WiFi network it already knows** (no password ever travels over the
   air), reads the public release list itself, installs exactly the version ordered with the very code the app uses, and
   restarts. It has 30 s to join; then nothing changes and it says why.
5. The Teensy transmits again and waits up to 4 minutes for the receiver. Its release number is the proof: the one wanted =
   done; the old one, with item 40 idle, = failed, and item 40 carries the receiver's reason (kept in its NVS across the
   restart, so a firmware that did not take says so too). A receiver still busy downloading answers with the radio chip's own
   acks, which can carry a stale item from before the silence: those never say idle, so they are waited out.

Once a second the Teensy tells the screen `ldrcrx=<phase>,<why>,<outcome>,<release hex>,<wanted hex>,<seconds left>`, and
the screen's `/status` shows it under `rx`. The receiver's `state.json` shows `tx_update` (state and last outcome), and its
event log tells the story (*Update to 0.9.870 ordered by the transmitter: accepted, waiting for it to go quiet* ... *Transmitter
quiet: receiver update begins, joining House* ... *Receiver update: installing RXV2-0.9.870-...*).

Not built: a countdown the receiver could shorten (it cannot know how long the download takes), and progress during the
download (the transmitter is silent, on purpose).

**The first bench afternoon (30 Sep 2026), and what it taught.** Every fault below was found on the transmitter within
an hour, and every one was in the new code:

- B11 never sent `ldrcrx=`: it waited for 64 free bytes in the port's 40-byte outgoing buffer. (B12)
- Both readers of the receivers' release list expected `"name":"`; the website writes `"name": "`. (Screen 1.3.1,
  RXV2 0.9.868; the screen's test now reads the live list itself.)
- The order text was thrown away when it landed just after one of the Teensy's own display commands (`GetReturnCode`
  drains the port blind). The screen now repeats it every 0.7 s until the Teensy's line shows it. (Screen 1.3.2)
- **The silence froze the Teensy.** SendData() returned before moving the packet clock; ManageTransmitter() stands aside
  whenever a packet is "due" and a model is matched, and so stood aside for ever: no chores, no switches, no clock,
  *no power button*, and the tick that ends the silence never ran. Malcolm had to bypass the button. (B13: the clock
  moves when silent on purpose, and ManageTransmitter never stands aside for more than 3 s. V1 carried the same
  latent hang through SendNoData.)
- The receiver's telemetry rotation went from item 37 straight back to 0 unless a phone had set its clock, so items
  39 and 40 were never sent. (RXV2 0.9.871)
- A WiFi install begun while the app streamed firmware over Bluetooth cut that transfer short. (RXV2 0.9.870: one
  update at a time, on every path.)
- One transient HTTP 404 from messiter.com for a file uploaded 35 s earlier: reported honestly as "download failed".

**Proven at 14:15, and again at 15:57 from the new button with the bar (0.9.872 → 0.9.873, 1 min 30 with the 90 s
silence; 60 s from 0.9.873 on):** Test1 0.9.871 → 0.9.872 through the transmitter, on B13 with screen 1.3.3. Accepted in under a
second, the transmitter quiet 2 s later, firmware fetched and written in 14 s (the pages identical and skipped), restart;
the transmitter back on air after its 90 s, reconnected, the new number heard, the green panel *Receiver updated*.
Since then: the silence is 60 s (receiver 0.9.873, which also tries a failed download once more after 5 s) and the
screen counts it down as a bar (1.3.4).

The chain had in fact run end to end on the first try (the receiver's previous-boot log: *TX param ID 35 first seen* →
*accepted, waiting for it to go quiet* → *Transmitter quiet: receiver update begins* → *installing RXV2-0.9.870* →
*HTTP 404*); it was the transmitter's freeze that hid it. For the bench, B13's `ldrcrx=` line carries a seventh field of
flags (1 silent for the update, 2 SendNoData, 4 model matched, 8 bound, 16 connected, 32 not in the normal mode, 64 a
question waits), shown by the screen's `/status` under `rx`.

## Where the time goes while flying (B15, 1 Oct 2026)

Malcolm: *"measure and keep track of those delays which might actually affect flying, and move them one at a time,
starting with the most important ones. Those which update the front screen without user intervention strike me as
important because they occur while flying."* The plan this serves: **the Teensy flies, the screen talks to the pilot.**
Every wait the Teensy makes for the screen is a moment when the sticks, the radio or the power button can be ignored.

The Teensy sends a packet every 2 ms. B15 measures, while a model is connected (as in flight):

- **every gap between packets** - a histogram; 4 ms or more is a *late packet* (a whole slot lost), and the last 24
  are kept with the job that took longest by itself in that gap, the job that called it, and the page showing;
- **every job** (`CRUMB(...)` guards, 1Definitions.h): runs, longest run by itself, longest with what it calls, total
  time by itself. Guarded: the channel bars, the front/data page, battery, the page clock, trims, the motor timer,
  switches, the bank, the vario, the mixing, the status lines, sending to the screen, reading it and draining it, plus
  the older guards (questions, delays, log, saves, reconnects, parameters, the clock chip...).

Nothing is written while flying. `/PERF.TXT` is written on the Teensy's card when the file link opens (it never opens with
a model connected) and, from B19, at power-off too - by the button or the inactivity timer - with a dated copy of each
session in `/PERF/` (yymmdd-hhmm.TXT). B15-B18 wrote it only when the link opened, so a transmitter switched off straight
after flying lost the lot (Malcolm's first simulator session, 1 Oct 2026); its headline is in the hello (`late=`, `worst=`, `wc=` the culprit, `wp=` its caller). Read it with
`dev/teensy_ota.py perf` (kept in `TXV1B/dev/perf/`). The guards' own cost is a few cycles; the breadcrumb that the same
guards keep goes to the coin cell at most every 50 ms.

**Motor on = the front page (B16).** Malcolm: *"when motor moves from off to on, the screen should move to the front
screen if it was not there, so that we KNOW we are on front screen when flying."* `MotorEnabledHasChanged()` does it, in
the normal mode only (never mid-calibration, scan, buddy session or Rotorflight save/restore) and with no question
waiting; unconfirmed edits on the page that was showing are left behind, never half-applied; a Rotorflight read stops.
It wakes a blank screen too. The screen saver may blank it again in flight after its timeout (120 s by default): decided
so by Malcolm - *"A touch wakes it if needed. Saves battery."*

**Back to the same page after the screen saver (B17 + screen 1.4.3).** Malcolm: *"if the screen times out and goes
blank, a touch should really return to the screen that was in use at the timeout moment."* Before, 17 pages came back
and every other page went to the front page. Now `SaveOrRestoreScreen()` (Utilities.h) has a table of all 49 pages that
can be shown in the normal mode. The screen remembers the page exactly as it blanked (values, texts, colours,
positions, what was hidden, scroll, timers, unconfirmed touch edits) and puts it back when the very next page is the same
one. Nothing is re-read or re-started: a page's own Start function is NOT called, because some reset things
(StartTrimDefView zeroes the trims; the Rotorflight pages read the flight controller again). Only the curve graph is
redrawn, being drawn with lines; the data, GPS and gaps pages refresh at once. The screen saver no longer blanks in the
middle of a calibration, a scan, trim setting, Pong or a Rotorflight save or restore (CheckScreenTime), which a restore
could not resume.

**How to use it:** model on, safety on, a few minutes on the front page with the sticks moving and the switches (bank,
motor) flipped as in flight; model off; `teensy_ota.py perf`. Then move the worst job to the screen, measure again.

## A banner that looks like one; Next and Previous (V2 B53 + screen 1.11.22, 7 Oct 2026)

Malcolm: "It seems to work very well now, bravo!" Two refinements. The line that says "Writing ..." / "Reading ..." /
"Saved ..." was the colour of the page: it is now a yellow strip with black words. And the two rescue pages are joined
by "Next >" and "< Previous" in the middle of the bottom row (it was "Height hold ...", with only OK on the second
page); OK on either page leaves the rescue pages, asking first if something was edited and not saved.

## Rescue as the configurator shows it (V2 B52 + screen 1.11.21, 7 Oct 2026)

Malcolm, with the latest Rotorflight configurator open: "the configurator offers flip or no flip. Climb goes elsewhere
... I think we should use the same names in the same places." So the first page now has the configurator's Rescue
Settings in its order, names and units: Enable Rescue (Off / On), Flip to upright (Flip / No-Flip), Pull-up Collective
[%], Pull-up Time [s], Climb Collective [%], Climb Time [s], Hover Collective [%], Flip Fail Time [s], Exit Time [s],
Leveling Gain, Flip-to-Upright Gain, Max Levelling Rate, Max Leveling Accel. Collectives are percent (45, or 65.5), as
there, not the flight controller's thousandths. The height-hold page carries the rescue mode (Off / Climb / Hold
height), the hover height, its P, I, D, and Max Collective [%].

## Rescue reads back what it wrote (V2 B51, 7 Oct 2026)

Malcolm: "After writing, it should really read back what has been written to confirm, but it does not. It displays the
values that we had before they were edited." The screen's timeline of the pipe (1.11.20) showed the save: select the
bank, write, store, select the bank ... and no read. B50 took the second bank selection's empty answer for the read-back,
found no bytes in it, and showed the old values with "the flight controller adjusted some values". B51 asks for the
values after the selection, as the first read does, and compares those.

## "Clicking receiver update makes the screen reboot" (screen 1.11.20, 7 Oct 2026)

The crash record (read through /status): task wifi, abort() in the driver's pm_set_sleep_type. The update panel keeps
the WiFi awake for its downloads (power save off), and the one radio cannot be kept awake while Bluetooth is up: the
driver aborts. 1.11.20: an update lets the Bluetooth pipe go first and keeps the WiFi awake only once Bluetooth is down;
a pipe asked for while an update has the radio is refused (the main board tries again in fifteen seconds). Also: each
request the main board sends over the pipe, and its answer, now goes into the screen's Bluetooth timeline, for the
rescue read-back question ("immediately after writing them, the transmitter screen reverts to the default values").

## Rescue on the transmitter, and the line that makes the rest possible (V2 B50 + screen 1.11.19, 7 Oct 2026)

Malcolm: "Assuming we still have sufficient memory, let us add in now the other Rotorflight settings to complete our
set! After that, we better do some rigorous testing." The set agreed: Rescue, Servos, Travel extents, Filters, ESC
setup; switches, ports, wiring, wizards, calibration and the black box stay on the phone. Rescue first.

**The line.** The receiver already answers raw Rotorflight requests on /api/msp?fn=N[&data=HEX], as its own pages do.
Screen 1.11.18 relays the main board's own requests over the pipe ("ldrcreq <id> <path>" on the wire, "ldrcrep <id>
<code> <body>" back, one at a time after the parameter packets); B50's PipeHttp.h asks and never waits (a page's state
machine looks for the reply each time round). No receiver change: every receiver from 0.9.874 serves it.

**Rescue** (RF_Rescue.h; pages RescueView and Rescue2View on the card, made by the screen project's hmi/rescue_pages.py;
help RESCUE.TXT and RESCUE2.TXT): Rotorflight 2.3's 28-byte rescue profile for the bank shown, read with 210 then 146,
saved with 210, 147, 250 and read back to compare. Page 1: the mode (Off / Climb / Hold height, tap to change), roll
upright first (tap), flip and levelling strength, the four times in tenths of a second, the pull-up, climb, hover and
max collectives, max turn rate and acceleration. Page 2 (Height ...): hover height in metres, height hold P, I, D. Save
on either page writes both. The Rotorflight menu gets a fifth button, "Rescue ...", with the model name and the blue
tooth below. Untested on hardware as written: the bench next.

## The blue tooth (screen 1.11.17, 7 Oct 2026)

Malcolm: "I wonder if we might remove By Bluetooth and replace it with the little icon we created a few days ago of a
tooth which happens to be blue!" His own Genmoji molar, the Bluetooth badge of the receiver's pages (RXV2 data/app.js,
15 August), cut from its PNG and scaled to 31 x 40 (src/tooth_icon.h: RGB565 and an alpha, 3.7 kB), is drawn at the
right of the Rotorflight menu's line in place of the words, blended on the panel's colour. The other states keep their
words: "Connecting Bluetooth: wait", "No Bluetooth", "Bluetooth: not joined". (The Mac renderer learnt the door and the
pipe as stubs on the way; it had not built since 1.11.4.)

## The crash, read and fixed (screen 1.11.16, 7 Oct 2026)

Malcolm: "the screen crash happens when going to the model screen and probably while attempting to connect." The core
dump, read through 1.11.15 and decoded against the 1.11.14 firmware: task ldrcble, a load from address 0x28 in
NimBLEClient::setClientCallbacks, called from bleJoin. The screen made a new Bluetooth client for every connection
attempt and "deleted" it after a failed one; but NimBLE only marks a client that is still connecting or parting for
deletion later, and it counts until then: at three, the next createClient() gives nothing, and 1.11.14 used it without
looking. Now one client serves the whole session, looked at before use, and the main task's stack goes from 8 to 16 kB
(it had 2.5 kB to spare at the worst moment seen).

## A goodbye that arrives; the crash kept for reading (screen 1.11.15, 7 Oct 2026)

Malcolm, with B49: "If it tries to join while it's on the Bluetooth screen, it takes a long time. But if I allow it to
join before we get to that screen, it's much quicker." And: "While changing screens, the tx screen went blank for a
moment, and I think it rebooted."

**The slow joins.** The receiver's events showed every parting as a timeout ("disconnected (reason 0x08)"), never a
goodbye, although 1.11.9 meant to say one: the screen waited for its link to stop being "connected", which happens the
moment a goodbye is ASKED for, long before it has gone out on the air, and then took its Bluetooth down. A receiver that
has not yet noticed the old link refuses the new one until its timeout runs out, several seconds; a join begun in that
time hung for fifteen seconds and failed. Now the screen waits for the disconnect event itself (up to 1.5 s) before its
Bluetooth goes down, and the timeline says "goodbye said". Also: a second "on" from the main board while a join is under
way is left alone; a dead connection attempt is given up after about eight seconds, not fifteen, and the scan runs again.

**The reboot.** `/status` said rst 4: a crash, and the chip keeps a core dump of a crash in its flash. `/status` now
carries its summary (the task, the cause, the program counter, the backtrace) under "crash", and `/coredump` (door)
gives the whole dump for espcoredump on the Mac. The release tool keeps each screen firmware's ELF in dev/out/elf for
the reading. The crash itself is not yet found: its dump is in the screen's flash, readable once this is installed.

## The join begins on Model setup, and ends the moment the receiver is heard (V2 B49 + screen 1.11.14, 7 Oct 2026)

Malcolm: "when safety is on, we could quietly try to connect Bluetooth in the background so that the connection banner
and pause are eliminated or at least reduced. Turning safety off should instantly turn Bluetooth and WiFi off." Two
parts, and one limit.

**B49:** the screen is asked to join the model's receiver as soon as the pilot is in Model setup (or any Rotorflight
page), one step before the Rotorflight menu, so the menu usually opens already joined; a failed join is tried again
after fifteen seconds while those pages show. Not sooner than Model setup: the receiver takes one Bluetooth client at
a time, and the phone app must find it free the rest of the time. The pipe is let go on the way back to the front page,
as before, and when the safety goes off the receiver is told at once (not twenty seconds later when the ask lapses); the
screen already drops Bluetooth and WiFi the moment the safety goes off.

**Screen 1.11.14:** the scan stops the moment the model's receiver is heard, rather than at the end of its 2.5 s window.
The receiver's Bluetooth address is its board id or that plus one to three (the ESP32 derives its addresses from one
base), so heard with such an address it is connected to at once and the identity check by its state page is skipped.
Any other receiver waits for the window, as before. A join with the receiver's Bluetooth already up should now take a
second or so.

Still open: "a big drop in frame rate when moving the motor switch with safety off", and at a bank change. The
transmitter's timing report of this morning's session shows no gap in its sending above 55 ms and no gap in the
acknowledgements above 50 ms except at the safety changes (the receiver's flight saves), so the link itself does not
stall there; what the box shows, and for how long, is the next question.

## Rotorflight editing is Bluetooth only; the bank and gap lines wait too; a join's timeline (V2 B48 + screen 1.11.13, 7 Oct 2026)

Malcolm, with 1.11.12: "It works much better now." Then three things.

**"I think we can remove the By radio fallback. Rotorflight editing should be entirely over Bluetooth."** B48: with a
model connected, the PID, rates, governor and advanced pages, and their writes, need the pipe; they refuse with the
reason ("Connecting Bluetooth. Please wait a moment." or "No Bluetooth link to the receiver. Rotorflight needs a Version
2 receiver (0.9.874 or later), in reach."). Without a model they work on the transmitter's own copies as before. A
Rotorflight parameter is never sent by radio any more; the menu says "No Bluetooth" / "Connecting Bluetooth: wait" /
"By Bluetooth" / "Bluetooth: not joined". Version 1 receivers have lost Rotorflight editing from the transmitter, as
decided on 6 October.

**"There is still a drop in frame rate when I move the motor switch, whether safety is on or not."** The motor switch
also moves the bank (to 4 and back: positions 2 and 3), and every bank change wrote a log line to the card. B48 keeps
the bank lines, the radio-swap lines and the gap lines with the motor lines, written at the next safety change, the
disconnection or power-off (24 lines of room). A gap's own log line used to be the next gap.

**"Sometimes connecting to Bluetooth takes a very long time, and sometimes it's quicker."** Screen 1.11.13 keeps the last
24 happenings of the pipe with their time ("scan 1: 3 devices", "connecting to Test1 (-57 dBm)", "ready: Test1, MTU
247", "disconnected (19)" ...) in `/status` under ble.log: the next slow join can be read.

## The pipe's parameters were never accepted: now sent as a form (screen 1.11.12, 7 Oct 2026)

Malcolm, with B47 and 1.11.10: the banner, then "By Bluetooth", "but all the values it reads are zero from PID and
rates". The screen's status had the answer: "the receiver refused a parameter (400): 9,321,1000,0,0,0,0,0,0,0,0,0". The
receiver's Bluetooth bridge hands a POST's body to its handlers only as FORM FIELDS; the raw body ("plain") that the
WiFi server gives never exists over Bluetooth. So every parameter the pipe sent as text/plain was refused. Until 1.11.9
the first refusal quietly put the main board back on the radio link, so the values came, by radio, under a banner that
said Bluetooth; from 1.11.9 the pipe stayed, and the values never came. **1.11.12** sends each parameter as a form,
"w=9,321,...", which the receiver's handler reads when there is no raw body - every receiver from 0.9.874 takes it. The
first real reads over Bluetooth are therefore still to be seen.

## The WiFi joins afresh after a Bluetooth session (screen 1.11.11, 7 Oct 2026)

Malcolm, updating: "I noticed not for the first time that I could not update, or rather could not join the Wi-Fi
usefully until I had switched the transmitter off and switched it on again. This happened yesterday." Both times after a
Rotorflight session over Bluetooth. One radio serves both, and when the Bluetooth stack is taken down the WiFi link can
be left looking joined and carrying nothing - then "Transmitter updates" waits on a WiFi that will never answer. So:
after every Bluetooth session the screen's WiFi disconnects and joins again by itself (a few seconds, on the ground).
Not proven to be the cause: `/status` now also shows `largest` (the largest piece of free memory; a secure connection
wants about 45 kB in one piece) and `rssi`, and a failed connection to messiter.com puts those numbers in its message.
If it happens again: do not switch off, say so, and the numbers will be read.

## "Connecting Bluetooth": wait, said loudly; motor lines logged later (V2 B47 + screen 1.11.10, 7 Oct 2026)

Malcolm: "It's very easy to try to view the PIDs while it says Bluetooth connecting. Probably we should wait for it to
finish connecting before attempting to read them ... a much more obvious banner that says please wait, connecting
Bluetooth!" So: **screen 1.11.10** puts a box over the Rotorflight menu's four buttons while it is joining, in the
biggest letters it has ("Connecting / Bluetooth / please wait a moment"); it goes when the join ends. **B47** refuses
the PID, rates and governor pages while the screen is joining, with the same words, and the menu's own line says
"Connecting Bluetooth: wait". B47 also asks the screen to join only when the connected receiver can carry the pipe
(release 0.9.874 or later, heard in the telemetry): a Version 1 receiver gets "By radio link" at once, no scan.

And: "when I turn the motor on or off, there is a momentary, huge drop in the frame rate ... this should occur when
safety is turned on and off rather than motor". A log line is an open-write-close of the file on the card, tens of
milliseconds in which no packet goes out, and the motor goes on and off with the model in the air. **B47** keeps "Motor
On" / "Motor Off" in memory with their time and writes them when the safety next changes (on the ground), when the
model disconnects, or at power-off.

## Rotorflight over Bluetooth WORKS; three blemishes tidied (screen 1.11.9, 7 Oct 2026)

Malcolm, early, on the footstool with receiver 0.9.876 and B46: "It seems to be working!" The receiver's events agreed:
the transmitter's ask arrived, Bluetooth stayed up ("staying up while disarmed"), the screen joined, and rates, PIDs,
governor profile and governor config were all read over the pipe. The transmitter's menu said Rotorflight 2.3 again.

Tidied in **1.11.9**: a parameter the receiver refuses (one 400 was seen; which one, the status now says) no longer ends
the pipe, only no answer at all does; "ldrcpipe on" while already joined (the menu re-entered from one of its pages)
makes the screen say "ready" again instead of leaving the menu on "Bluetooth: joining"; and leaving the pages now says a
proper goodbye to the receiver (its log had "disconnected (reason 0x08)", a timeout) so it advertises again at once.

## A failed Rotorflight enquiry no longer un-Rotorflights a model (V2 B46, 6 Oct 2026, late)

Malcolm: "the tx enquires about Rotorflight as soon as they connect and if it fails then it assumes no Rotorflight -
wrongly in this case." The receiver's telemetry item 31 carries the flight controller's Rotorflight version (0 none,
1 = 2.2, 2 = 2.3+), and it says 0 while the flight controller has not answered the receiver's own enquiry, not only when
there is no Rotorflight. The transmitter took that 0 as gospel, so Black Thunder 2's arming channel stopped following
the safety switch (FixArmingChannel) and its menu said 0.0. **B46:** a 0 from the receiver does not clear what the model's
file knows; a real answer still rules and is saved with the model as before.

## A refusal explains itself (V2 B45 + screen 1.11.8 + receiver 0.9.876, 6 Oct 2026, late)

Malcolm, in the Rotorflight menu with a Bluetooth link at last: "when I try to read PIDs, it thinks arming is on or
safety is off ... arming is in fact off, safety is on". The test behind "Model is armed and dangerous" was *arming
channel above 1000*, and since B40 a front switch with another job parks its channel at its CENTRE (1500); a model whose
Rotorflight version is not set (Black Thunder 2 shows 0.0) has nothing else driving that channel. **B45:** one helper,
`ModelSeemsArmed`, for the PID, rates and governor pages: when the transmitter drives the arming channel (a Rotorflight
version set, FixArmingChannel) armed means *the safety is off*; otherwise only the channel's upper third (1800 up)
counts. The message names what was seen: "Model may be armed: channel 6 (arming) is at 1500. Move it low first." The
menu's own entry message says which of the two it saw (motor enabled, or safety off).

**Receiver 0.9.876:** when the transmitter's Bluetooth ask cannot be honoured, the events log says why ("not while armed
(channel 6 at 1503)", or a receiver update), and state.json's `ble.tx_ask` shows the ask. **Screen 1.11.7:** `/status`
gains `rst`, why the screen last started (1 power, 3 its own restart, 4 panic, 5-7 watchdogs, 9 brown-out): it restarted
once in the evening's session, cause unknown; the Bluetooth task's stack goes from 8 to 12 kB. **Screen 1.11.8:** `/status` also
shows `stack` (the least each task has ever had spare: `loop`, `ble`).

**Still open (7 Oct morning):** the receiver did not open its Bluetooth when asked, minutes after power-on. Suspect: the
receiver's own arming channel (6) reads the parked centre as "armed" (its rule is above 1500). The bench order that
shows everything: model on FIRST with the transmitter off (it joins the house WiFi, so its events can be read), then the
transmitter on, then the Rotorflight menu; read `/api/events.json` on the receiver and `/status` on the screen.

## The transmitter asks the receiver for Bluetooth (V2 B44 + screen 1.11.6 + receiver 0.9.875, 6 Oct 2026)

Malcolm, with 1.11.5 and the door open: "I'm getting still by Radio Link". The screen's status said why: the scan found
no receiver at all. **The receiver shuts its Bluetooth 30 seconds after it hears the transmitter at its power-on**, and
keeps it shut while a model with no arming channel is connected (its flying rule, from the days when only a phone
would ever join it). The first live session had worked because the menu was opened within those 30 seconds.

So the transmitter now asks. **B44** sends a new parameter over the radio link, 36 "Bluetooth wanted" (321, 1), when the
Rotorflight menu opens and again every five seconds while it stays open and the transmitter is on the ground by its
own rule; (321, 0) on leaving. Version 1 receivers and older Version 2 receivers ignore it. **Receiver 0.9.875** honours
it while not armed by its own knowledge: Bluetooth comes up (with the usual pardon to the transmitter for the keying
stall), the boot window and the no-arming-channel flying rule stand down while the asks keep coming, and the ordinary
rules take it down again once they stop. **Screen 1.11.6** scans for up to fifteen seconds instead of 2.5, since the
receiver needs a second or two to come up, and stops at once if the menu is left.

## The firmware write checks itself and tries again (screen 1.11.5, 6 Oct 2026)

Malcolm's install of 1.11.4 stopped at the last step: "The new firmware was not accepted by the flash (Could Not
Activate The Firmware)." The file had reached the card whole (its CRC checked twice) and every byte given to the flash
had the right CRC: it was the chip's own check of what it had just written (header, segments, SHA-256) that said no,
and the reason it logged went out on UART0, the wire to the main board, where nobody reads it.

Three changes:
- **The written half is read back** and compared with what was written before the chip is asked. A flash that did not
  keep what it was given is named as such ("the flash did not keep what was written").
- **A second attempt by itself**: the whole write again from the file on the card, before anyone is told. The message
  names both reasons if they differ.
- **The system's own lines come to the screen**, not to the main board (esp_log_set_vprintf): the last eight at the end
  of `/recent`, the last one in `/status` as "sys", and those logged while the chip checks a new firmware go into the
  failure message, e.g. "Could Not Activate The Firmware: esp_image: Image hash failed - image is corrupt".

Also: **the corner holds run on through dropped touch samples** (the GT911 drops a sample now and then mid-press, and
each one began the hold again: "I held for three seconds, no banner"). A finger is up only after 120 ms up, as the
flight screen's long press has had since 1.10.3.

## A Workshop door button (screen 1.11.4, 6 Oct 2026)

Malcolm: "you could create an ordinary button that switches it on, which I can find perhaps bottom left on the
transmitter setup screen." Done: "Workshop door" at the bottom left of Transmitter setup opens or shuts it, with the
banner saying which. The corner hold stays.

## The door on every page, and the pipe's state in plain sight (screen 1.11.3, 6 Oct 2026)

Malcolm, trying to open the workshop door on the defined front screen and then on Transmitter setup: "no banner".
The corner holds (the door at the top right, the radios at the top left) were checked only after the screen's own
pages had taken the touch, so they never worked over the defined front screen; now they come first, on every page,
and the page underneath sees no press. The Bluetooth pipe's state (state, why, the receiver wanted and joined, the
receivers seen) is on /status, which answers with the door shut; and a failed join keeps its reason instead of
putting the stack away at once.

## Help comes back to the page it was opened from (V2 B43, 6 Oct 2026)

Malcolm: "on returning from help, it goes all the way back to the front screen, which it should not do." A Version 1
habit: every page without a special case of its own went to the front screen after help ("might fix later"). Now
every page stays where help was opened; the screen gives it back every value it had.

## Which way the values travel (V2 B42, 6 Oct 2026)

Malcolm, on the first live session (a bench Nexus, PIDs read and written): "What I don't know for sure is whether
it's using BLE or the old method." The Rotorflight menu now says, at the right of its message line: "Bluetooth:
joining", then "By Bluetooth", or "By radio link" / "By radio link (no Bluetooth)".

## The Bluetooth pipe, steps 2 and 3 (B41 + screen 1.11.2 + receiver 0.9.874, 6 Oct 2026)

The receiver's identity: no change to its Bluetooth advertisement is needed. The screen tries the receivers in reach,
strongest first, reads each one's board identity from its state page and keeps the one the main board named, which is
what it learned at binding. The receiver gains two endpoints feeding its existing, proven parameter code: the words of a
packet in, the block being read out. The screen relays: "ldrcpipe on <id>" from the main board joins the receiver,
"ldrctx id,w1..w11" packets go across, and while a read is open the block comes back as "ldrctel" items into the same
telemetry parser the radio link's acks use. The main board sends the Rotorflight parameters (IDs 9-21, 27-33) by the
pipe only while the screen says it is ready, and by the radio link as ever otherwise; the pages, values, save and
restore are untouched. Released the same afternoon; the first live session on a bench Nexus read the PIDs and wrote one over
Bluetooth (the write landed in every bank: the bench Nexus had no profile switching set up, as Malcolm found).

## The Bluetooth pipe, step 1 (screen 1.11.0, 6 Oct 2026)

Malcolm: the Rotorflight editing "should go via Bluetooth rather than the current method which can be removed",
with the processing kept on the Teensy, "where I believe we still have plenty of room". Step 1 of four: the screen
can find a Version 2 receiver, join its Bluetooth bridge (the one the phone app uses) and relay a request. The
framing is lib/LdrcBle, tested on the Mac; the radio is src/ble_device.h, NimBLE in a task of its own so the
Nextion wire is never starved; the stack comes up only when asked and goes down after, and never while the model
could be flying. Nothing uses it yet but the bench, through the workshop door (/ble/on, /ble/status, /ble/req,
/ble/reply). Flash: 1.60 MB -> 1.80 MB of the 1.97 MB slot. Next: the receiver's identity in its advertisement,
then the Teensy's pages over this pipe instead of the radio link, then the old path removed.

## Cell voltage big (screen 1.10.9, 6 Oct 2026)

Malcolm: "In those boxes which show voltage please make the PER CELL voltage big, and the total voltage smaller."
Both battery boxes: the cell voltage big, and below it "7.82 V total  78 %". The small line says "total" so that it
cannot be read as the cell, which is what went wrong the last time the cell was big (10-04).

## "6 defined front screens" (screen 1.10.8, 6 Oct 2026)

Malcolm: "Please change defined front screen into '6 defined front screens'." The Appearance page's button says so,
and the help texts that point to it.

## Tabs easier to hit (screen 1.10.7, 6 Oct 2026)

Malcolm: "Because they are so close to the top of the screen they were quite difficult to hit with a finger ... but
they're okay now... Just!" A tab now answers to a touch up to 10 px below its drawn edge and 2 px either side,
without looking any different.

## The same tabs, and "Defined screens" (screen 1.10.6, 6 Oct 2026)

Malcolm: "They are still smaller! Please make them the same size as setup area. Also please change Defined screen to
Defined screens." The flight screen's strip was 44 high, the setup page's 58, so its tabs were clipped to 28; the
strip is 50 now and the tabs 38 by 42 on both pages. The front page's middle button says "Defined screens", there
being six, and the help texts follow.

## Bigger tabs (screen 1.10.5, 6 Oct 2026)

Malcolm: "The six little buttons for selecting which defined screen on the front screen are a bit too small. Please
make them the same size as the ones in the definition area." Done: 38 by 42, four apart, on both pages.

## The lift after the long press (screen 1.10.4, 5 Oct 2026)

Malcolm: "It does now go to the select screen after two seconds, but when I lift my finger it goes instantly back to
the front screen. If I slide my finger elsewhere before lifting it works better!" The finger that opened the chooser
was still down, over whatever button the chooser had put there, and its lift chose that. The chooser now ignores that
finger until it has really lifted; the next touch counts.

## The long press that did nothing (screen 1.10.3, 5 Oct 2026)

Malcolm: "I held my finger still on a box for over three seconds but it did nothing" (1.10.2, screen lit, safety
on). The touch chip drops the odd sample in the middle of a press - the screen has always known, a lift counts only
after 80 ms with no samples - and the long press's clock restarted at every dropped sample, so two seconds never
came. It now runs on through a dropped sample and restarts only at a real lift.

## A long press on a box (screen 1.10.2, 5 Oct 2026)

Malcolm: "While on a defined front screen, a long press on a box allows that box to be redefined. Possible? But not
a short tap. A very long press." Two full seconds on a box, without moving, and that box's chooser opens from the
flight screen itself; the choice made (or OK, or its theme page done), the flight screen is straight back and the
change is kept. A tap or a slide does nothing, as before. Only on the ground: in flight setup pages close by rule, so
a held finger does nothing then. The Appearance page's way in is unchanged.

## The tabs on the screen itself (screen 1.10.1, 5 Oct 2026)

Malcolm: "when a defined front screen is in view, please try to squeeze in those 6 buttons so that a user can
rapidly switch to another defined screen. We might need to omit an element from the top bar." The clock goes from
the top line (it is a box you can add, and the original screen still shows it) and the six tabs take its place,
before Help; the bank sits between the name and the tabs. A warning (BATTERY LOW, NO LINK) shows alone, centred
before the tabs. A tab touched in flight switches at once and the choice is kept.

## The six screens explained (help files, 5 Oct 2026)

Malcolm: "let us explain the functionality of the six definable front screens in the help text." The Appearance help
has a paragraph of its own on the six screens (tabs, the yellow one in use, what each keeps, why: one design for
the simulator, one for a helicopter, one for a glider), and the defined screen's own help points to the tabs.

## Six defined front screens (screen 1.10.0, 5 Oct 2026)

Malcolm: "Currently one defined screen is all we can have. Perhaps we can allow a choice? I suggest perhaps 6 slots
each of which can hold a different screen definition. Then a user can easily switch from one good definition to
another without needing to laboriously redesign it." Six definitions, each with its own boxes, sizes and themes,
chosen by tabs 1 to 6 in the strip of the Defined front screen setup page; the one in use is yellow. Touching a tab
switches at once, and the boxes below show that design. Each is kept in the chip; the one definition of 1.6.0-1.9.15
becomes screen 1, so an update changes nothing. Whether the defined or the original front screen shows (the two
buttons) is the pilot's choice, not a slot's, and goes along when the tab changes.

## "Defined front screen" (screen 1.9.15, 5 Oct 2026)

Malcolm: "Front screen needs to say Defined front screen for greater clarity." The Appearance page's button and the
title of its setup pages say so; the help texts follow.

## Which themes the other boxes wear (screen 1.9.14, 5 Oct 2026)

Malcolm: "when choosing a theme it would be quite nice to know while choosing which themes have already been used."
On a box's theme page, a theme other boxes wear carries their numbers in a small dark pill, top right ("2 5"). The
box's own theme keeps its yellow frame. (A host test had walked a scene's buttons while asking for the scene again,
which rebuilds it; it only showed when the button record grew. The test copies the scene first now.)

## The Motor box in the safety's colours (screen 1.9.13, 5 Oct 2026)

Malcolm: "The Motor option in a screen box does not convey the state of Safety yet as on the original screen. I
suggest the use of green if safety is on, otherwise red, overriding user colour selection there." The original
page's motor button is coloured by the main board as the safety switch moves (Motor_sign.h ShowSafety: red with
white words while the safety is on, green with black words when it is off). The Motor box now takes exactly those
colours, over whatever theme it was given, whenever the main board has written them; with no safety switch, or the
motor kill off, it keeps its theme. The box's theme page still shows the theme being chosen.

## What the other boxes show (screen 1.9.12, 5 Oct 2026)

Malcolm: "When choosing the contents of one of the new screen boxes, it's easy to forget which ones have already
been selected. Perhaps we can put some marker on the buttons to indicate which has been used already." In the
chooser, a thing another box already shows is a shade darker and carries that box's number in a small disc, top
right. The box's own choice stays yellow.

## The picture alone (screen 1.9.11, 5 Oct 2026)

Malcolm: "If I select model image, I get the name as well as the image. But I only want the image, so if we remove
the name, we can have a bigger image!" The Model image box shows the picture alone, as big as the box allows, its
shape kept. The model's name stays in the strip at the top of the screen. A box with no picture to show keeps its
"Model image" label and says which picture is missing.

## A switch does one thing (V2 B40, 5 Oct 2026)

Malcolm set switch 8 to move channel 15: "it did move channel 15, but it also moved channel 8 as well, which I think
it should not have done." B32's rule had a front switch keep feeding its own channel whatever job it had. Now a front
switch given any other job (a special job, or another channel) lets go of its own channel, whose input sits at its
centre, as "Not used" does. The B32 note below about a front switch feeding its channel no longer applies.

## A renamed channel by its name (V2 B39, 5 Oct 2026)

Malcolm: "it is possible that channel 5, 6, 7 or 8 might have been renamed flaps or gear. In which case, let's
display that instead." On the Switches page and the job page a channel shows its name where the pilot has renamed
it, else "Channel N". The names a model starts with ("Ch 5", "AUX1", and the old "Gear" of channel 5) count as not
renamed, so B34's "by number" still holds for them.

## A front switch's marking is its channel (V2 B38, 5 Oct 2026)

Malcolm: "the default markings for channels 5, 6, 7 and 8 is Not Used. This is not strictly true, because by default
they are still controlling channels 5, 6, 7 and 8 ... If anyone actually does select not used (pretty unlikely) then
I guess they should do nothing at all." A front switch with no job now shows "Channel 5" (to 8) on the Switches page,
and that radio is the one selected on its job page. Choosing it is the default (nothing is stored as a job, so a knob
there stays a knob). "Not used", chosen on purpose, is kept (TX_EXT_ADDR + 11, outside the checksum) and parks that
channel's input at its centre. The fingerprint folds the flag in only when it is set.

## Near, mid, away (V2 B37 + screen files, 5 Oct 2026)

Malcolm: "that last swap of directions was a mistake. My mistake. Perhaps up and down is not the ideal way of
describing their positions. Towards the pilot and away from the pilot makes better sense." B36's swap is undone (a
high reading is position 3 again, as B35 had it), and the words beside each switch are now "near" (towards you),
"mid" and "away" for all eight: position 3 is near, 1 is away. The help texts say which position does what in those
words. If a switch reads the other way round, Reversed turns it.

## The front switches the right way up (V2 B36, 5 Oct 2026)

B35 installed and ran ("it looks very good indeed"). Malcolm: the front switches "say they are up when they are down
and down when they are up". Their analogue reading is low with the lever up; B35 had taken a high reading as up. B36
turns the reading's order round for switches 5-8, so up is up; Reversed still turns it round again for odd wiring.

## The refused update, and the fingerprint (V2 B35, 5 Oct 2026)

Malcolm's first install of B34 was refused by the transmitter's own guard: "2.5.6 B34 read this model's settings
differently from 2.5.6 B31 ... It was NOT kept." He suspected the saved parameters' layout ("the replacement
parameters must be precisely the same size"). It was not that: the transmitter block's sequence is untouched and the
new bytes sit at fixed spare addresses outside it. It was the settings FINGERPRINT (FlightGuard.h): B32 had made it
cover eight reversed flags and twelve switch inputs instead of four and four, so B34 gave a different number for
settings that had not changed, and the guard did what it is for. B35 computes version 1's sequence exactly as B31
did, and folds the new settings in only when one of them is in use: a setup an earlier firmware could hold gives the
number it always gave, so the update is compared and kept. The rule in FlightGuard.h now says so: never put a new
setting inside the sequence, never widen a loop in it. The extension also gained a second marker byte and a check
of every value, so a stale byte on an old card cannot pass for ours.

## Channels by number (V2 B34, 5 Oct 2026)

Malcolm: "I note you put Gear instead of Channel 5. Please call it channel 5 as it's only rarely gear." The job page
and the Switches page say "Channel 5" to "Channel 16", never the channel's name.

## A switch as the input of any channel, 5 to 16 (V2 B33 + screen files, 5 Oct 2026)

Malcolm: "you said channels 9-12 are offered. Can we make that 5 to 16, I wonder? That would be complete!" The
"Channel N" job now runs from 5 to 16. A switch given channel 5 to 8 takes the place of the front switch or knob
there (the mixer reads the switch instead of the analogue input); 13 to 16 had no input at all before. The switches
of channels 9-12 keep their four bytes of the transmitter block; the other eight are in the block's extension
(TX_EXT_ADDR + 3 .. + 10, outside the checksum, like the reversed flags). The job page shows the twelve channels in two
columns on the right, the special jobs down the left; the Switches page names the job "<channel name> (Ch N)".
Help texts SWITCHES, ONESWICH and INPUTS say so.

## Any switch, any job (V2 B32 + screen files, 5 Oct 2026)

Malcolm: "It has eight switches. Four of them simply are the sources for channels 5678. The other four on the top of
the transmitter handle special functions like safety, buddy, motor, etc. ... Ideally, it should be possible to
designate any of these eight to any of those functions."

The two groups are different hardware: the top edge's four are digital (two contacts each), the front four are the
analogue inputs of channels 5-8 (so a knob can take a switch's place). Every job (Safety, Buddy, Banks 1 2 3, Bank 4 &
Motor, Rates, Channel 9-12) already went through one routine, GetSwitchPosition(), so:

- **GetSwitchPosition() answers for switches 5-8 too**, from the front inputs' readings and their calibration: thirds
  of the travel, with a dead band of a twelfth either side of each threshold so a reading near one does not flicker.
  The four readings are taken once a frame, and only when a job uses a front switch (or the Switches page shows).
- **The Switches page shows all eight**, the top edge's four as before and the front four below, and beside each
  where it is now: up, mid or down (the main board writes p1..p8 while the page shows). Move a switch to see which
  number it is. Touching a number or its job opens the same job page as before.
- **Reversed** works for all eight. The four new flags live near the end of the transmitter block (TX_EXT_ADDR 500:
  two marker bytes, the flags, then B33's eight switch bytes), read and written outside the checksummed sequence, so
  a models.dat from before B32 loads as it always did, and a build before B32 never looks at them. The sequence of
  the block itself is untouched: nothing moved, nothing changed size.
- The pre-flight motor check (CheckMotorOff) and the Channel 9-12 reader accept switches 5-8.
- A switch edit now saves the transmitter block at once (it used to wait for the next switch-off).
- Help texts SWITCHES, ONESWICH and INPUTS say all this.

**What changes in an existing setup: nothing.** The jobs belong to the transmitter, not to the model, and every job
stays on the switch it had. Only when a job is moved onto a front switch:

- that switch goes on feeding its channel's input (5-8). If the channel is in use, give it another input on the
  Inputs page, or an unused one;
- a Version 1 transmitter, or this one on a build before B32, reads a job on a front switch as a switch that does not
  exist: Safety reads as permanently on, Banks stays on bank 1, and with the Bank & Motor job there the motor stays off. The jobs are
  the transmitter's own and are not in a model file, so a model copied to another transmitter is unaffected.

A top-edge switch driving a channel is unchanged: give it the job "Channel 9" (to "Channel 12"), then on the Inputs
page give the channel that input number.

## The Models page in two colours (screen files, 5 Oct 2026)

Malcolm: "the heading Models should become Models Loaded. And the heading Backups should become Backup Files ... the
left-hand side should adopt a colour for the headings and the buttons and the models, which looks unified. The
right-hand side, which handles the backup files and functions connected with them, should also use a unified colour,
but a different one." Done as hmi/colour_models_page.py: the left side (the models in the transmitter) in blue, the
right (the backup files on the card) in amber: each heading a solid strip in its deep colour, its list bordered in it
on a pale tint, its buttons the pale tint. The middle column, the picture, the name and OK are as they were. Page
file only: no new firmware.

## Lists centred again (screen 1.9.10, 5 Oct 2026)

Malcolm: "The model names and the back-up file names in version one were centred rather than left justified, which
I think I preferred." Every scrolling list (the Models page's two, the log files, the bank names, the rates, the
model IDs) centres its rows again, as the Nextion's wheel did; a name too long for its box still ends in "...".

## The Front screen setup page's row (screen 1.9.9, 5 Oct 2026)

Malcolm: "The three remaining buttons now look as if there's one just missing! I think they should be evenly spaced
and perhaps a little larger." Box sizes, Stays lit and OK are now three equal buttons across the width, as the front
screens' own row is (250 wide, where the old four-slot row had them 180).

## The front screens: the buttons choose, nothing else (screen 1.9.8, 5 Oct 2026)

Malcolm: "The When: Never etc button I think ought to go because we just hit a button to swap." Gone, and with it
the rule behind it: until now a take-off or a landing put the rule back ("When: flying" showed the defined screen in
the air and the original on the ground, whatever had been chosen). Now the front page's "Defined screen" and the
defined screen's "Original screen" are the whole story: the choice stays, through take-offs, landings and switching
off, until the other button is pressed. A transmitter that has never chosen shows the original. The Front screen
setup page's bottom row is Box sizes, Stays lit, OK. The old setting is still written and read, so that older and
newer screens read each other's settings; nothing looks at it. Help texts FLIGHT, APPEAR and FRONT say so.

## The exchange from a Version 1 transmitter (V2 B31, 5 Oct 2026)

Malcolm: "I just tried to send a model memory from a V1 transmitter. Unfortunately, it failed." Four packets came
(112 bytes), then the V1 sender said "not ready". B27's four-byte ack was the cause: a Version 1 sender reads one byte
of each ack, and the nRF24 keeps a partly read ack in its receive FIFO, which holds three; after three acks it was
full, the fourth could not land, and the sender's radio gave up. So "a Version 1 sender reads the first byte as ever"
was wrong on the real chip. A B27+ receiver now answers a Version 1 sender with the one byte, as Version 1 always
did, and a B27+ sender with the four; it knows which from the first packet, so the first ack payload is loaded after
that packet is read. Everything else of B27 stands.

## The scores' blue (screen 1.9.7, 5 Oct 2026)

Malcolm: "the score has a coloured background, which I haven't seen before!" The score boxes take their colours from
the front page's global variables, which the main board writes once at its own power-on (black). An update restarts
only the screen; the write was lost, and since 1.9.4 a never-written global reads as its page file has it: 214, an old
blue from the Nextion days. Two things: the last values written to global variables are now kept in the screen's RTC
memory through its own restarts, as the model's picture name is; and the front page's starting value is black anyway.

## The clock (V2 B30 + screen 1.9.6, 5 Oct 2026)

Malcolm: "the real-time clock ... occasionally simply refuses to give us any time and has to be reset ... when we
boot up we check that we can see the time and if not send the real-time clock a reset ... we could use our access to
the Internet to set the time correctly automatically."

- **At power-on** the clock is asked for the time. If it does not answer, the I2C bus is clocked clear (nine pulses
  with the bus released, then a stop: the standard cure for a chip left half-way through a byte by a brown-out) and
  it is asked again. The front page then says so: "The clock had stopped answering and was started again. The time
  is put right by itself from WiFi, or from a phone." (or "The clock does not answer" if it still will not).
- **From the internet:** whenever the screen is on a network it asks SNTP for the time, in the UK's time zone, summer
  time and all, and gives the main board the word TIME=<local seconds>; the main board sets its clock by it when ten
  seconds or more adrift, exactly as it does with a phone's time through the receiver. Again every hour. A clock that
  does not answer is written all the same: the write is what starts a halted one.

## The model's picture kept; the log folder tidied (V2 B29, 5 Oct 2026)

Malcolm: "occasionally when I returned to the front screen, the image for the model has been forgotten or cannot be
read." The transmitter asks the screen whether the picture is there (findfile, then get sys0) and gives it 500 ms to
answer. It asked right after loading the front page, and a page just loaded, with the front screen's boxes to draw
and a picture to read, sometimes answered later than that; silence was taken for "no", and the name was replaced by
"Noimage" for good. Now only a definite "no" loses the name; silence keeps it. The question is asked where the name
can have changed (a model loaded, a picture chosen), before a page is loaded, with a second to answer; the front page,
and a model regained after a lost link, just show the name they have, with no question and no wait.

Malcolm: "there is a maximum number of log files which I allowed for when setting up the arrays. I made no provision
for what happens when this is exceeded." The list has room for 96 and a day's flying makes one log, so the newest
dropped off the list after a season. At power-on, before the radio starts, the log folder is tidied: more than 90 of
them and the oldest go (by the date in the name; NO_CLOCK.LOG first), down to 80. LOGFILES.TXT says so.

## The phone's hotspot without being asked (screen 1.9.5, 5 Oct 2026)

Malcolm: "in the bedroom, the Wi-Fi is very weak. The last update, it's been ages, trying to connect to house and never
did. Eventually I forced it to join my phone's hotspot ... perhaps it could have tried automatically after a timeout
on its attempt to connect to house?" It tried: after 12 s it looks around and tries the strongest network it knows -
but a quick look shows only what beacons loudly, so it saw the house's network (too weak to join) and nothing else,
and tried the house again, and again. Now a network it knows that the look did not show is tried all the same, by
name, before the failing one is tried again: a phone's hotspot answers a direct call. A radio that says "no such
network" is not waited for; every step of the automatic joining goes in the boot log; and the update's "No WiFi"
note says to open the phone's hotspot page. Simulated in test_device: joined in 17 s where it never was.

## Pong's scores (screen 1.9.4, 5 Oct 2026)

Malcolm: "the score is missing at the top" - then, after a restart, "now the score is visible!! But the digits are
clipped at their bottom." Two things. The score boxes take their colours from FrontView.ForeGround, which the main
board tells the screen once at power-on; when only the screen had restarted, that was unknown and read as 0: black
digits on black. The screen now reads a never-written global as its page file has it, as a Nextion does; every page
that reads another page's variable gains the same. And the court's layer began 12 px above the court, over the bottom
of the score boxes: it begins just under them now, and a paddle pushed beyond the court's lines slides behind the
frame instead of over the scores or the buttons.

## Pong, smoothly (V2 B28 + screen 1.9.3, 5 Oct 2026)

Malcolm: "I provided a little game of pong! It works, but it's not very well optimised, particularly for this new
screen. I wonder if you can optimise it better so that the ball appears to move a little more smoothly?" The game
stays on the main board (the sticks, the physics, the scores, the sounds). It used to draw the court itself: nine
drawing commands a frame, a hundred frames a second, erase then draw. The screen shows a page at most 40 times a
second and holds a burst back until it has all arrived, so the ball moved in lumps and flickered. Now the main board
sends one line a frame, "pong=x,y,ly,ry", and the screen draws the court in a layer of its own: in memory, shown at
once, with the ball and paddles gliding between the main board's 5-pixel steps (each pass draws where they were
15 ms ago, between the two frames either side of that moment). A yellow ball with a rounded edge, 6-pixel paddles, a
dashed centre line. The scores, OK and Help are the page's, as before. The two halves go together: a B28 main board
with an older screen shows an empty court.

(From this release the transmitter is called V2. The folders and the update address stay as they were.)

## Model exchange hardened (B27, 5 Oct 2026)

Malcolm: "One of my favourite features of Ldrc is the copying of model memories to another transmitter without wires
or moving sd cards! But I think my 'protocol' is not really bullet proof - yet ... we MUST remain compatible with
version 1." Everything Version 1 reads on the air is as it was; B27 uses the bytes Version 1 never reads:

- **Packet 1, byte 21:** the protocol (Version 1 sends 0, B27 sends 1); **bytes 22-23:** a CRC-16 of the whole file.
- **Data packets, bytes 28-31:** the packet's number and its complement (Version 1 stores only the 28 bytes of data).
- **The ack:** B27 answers with four bytes (1, 'B', the count stored so far); a Version 1 sender reads the first byte
  as ever. A B27 sender shows the count in its debug print.
- **The receiver**, from a B27 sender, drops a packet sent twice, gives up on one out of order ("lost sync") and checks
  the whole file before writing. From a Version 1 sender it takes the file as before.
- **Local, whoever sends:** the receiver gives up after 3 s without a packet (it used to wait for ever); the file goes
  to the card as ~RECV.MOD, is read back as a model, and only then put over the old one (a bad transfer used to destroy
  the old file first); no padding is written; the name is read with a 15-character limit, and a sender refuses a
  longer name; the "Waiting N..." text is written once a second, not a thousand times.
- Sender messages tell "not ready" from "stopped answering".

Not yet tried between two transmitters: Malcolm has the pair.

## Cancel no longer starts something else (screen 1.9.2, 5 Oct 2026)

Malcolm: "If I press cancel after invoking a function, such as delete a file or send a file, I end up going round
in an endless loop of more and more cancels ... Each press of cancel seems to invoke an unasked for function!" The
popup's OK and Cancel print on press, so the main board loads the Models page while the finger is still down. The
screen kept the pressed component as a place in the page's list, and on the lift ran the release script of whatever
sat at that place in the new page's list: Backup, Delete, Receive, the picture chooser. Each of those asks a question
with a Cancel, and round it went. A page that changes under the finger now drops the press, as a Nextion does.

## Frame rate (B26 + screen 1.9.0, 4 Oct 2026)

Malcolm: "Please add another box option 'Frame rate'." The frame rate (packets a second) was only ever shown on the
Data page. B26 writes it to the front page as "pps" once a second while a model is connected (GetFrameRate); the page
has no such box, but the 5-inch screen keeps every value the main board writes, and the front screen's new "Frame
rate" box reads it. "no model" without a model, "--" until the first second's count.

## A switch the finger flipped comes back with its page (screen 1.8.9, 4 Oct 2026)

Malcolm: "On the Wireless buddy screen, on return from 'select channels to pass to buddy' master gets turned off even
if it was on." The main board goes back to the buddy page without sending the switches (BuddyChViewEnd), relying on
the Nextion's global components to keep their values. The screen keeps values the main board writes, but a switch
flipped by a finger (or a slider moved, or a row picked in a list) was not remembered, so the page came back with the
main board's last write: master off. Now every value the finger changes is remembered like a write.

## A picture asked for again; the battery boxes the right way up (screen 1.8.8, 4 Oct 2026)

Malcolm: "just occasionally, when I select a new model, which has an image, when I return to the front screen, it
says there's no image. I can reselect it and then it's okay again." A box is drawn again only when something in it
changes, so one failed read of the card (SPI, 40 MHz: the odd one fails) left "no picture" standing. The picture is
now asked for again, up to eight times 600 ms apart, and each failure is logged with its reason (the boot log).

And: "the transmitter battery per cell voltage and total voltage seem to be the wrong way around." The cell voltage
was the big number with "per cell  8.18 V" below, which read as if the total were per cell. Now the pack is the big
number and "4.09 V per cell  100 %" sits below, as the front page says it.

## The screen you were using comes back (screen 1.8.7, 4 Oct 2026)

Malcolm: "when I boot up, it always starts with a defined front screen, even if I had been using the default when I
switched off. I think it should boot up with whichever I was using last time." The choice of the moment (Original
screen / Defined screen) is kept with the front screen's settings (a token " m:1" / " m:2"), written when it is made
(when the wire is quiet, never in flight) and cleared, as before, by a take-off or landing. Older screens ignore the
token.

## The front screens' buttons (screen 1.8.6, 4 Oct 2026)

Malcolm: "The front screen buttons at the bottom ought to say Transmitter / Original screen / Model, or Transmitter /
Defined screen / Model." Done, on both: the original front page's row is three equal buttons now (38 to 765), with
"Defined screen" in the middle; the pilot's own front screen has "Original screen" in the middle. Help texts follow.

## Blue LED while updating (B25, 4 Oct 2026)

Malcolm: "the other convention I forgot to mention is the 3-colour LED: RED means trying to connect. GREEN means
connected. BLUE means busy and not even trying to connect. Hence when we are updating the firmware etc. that LED
ought to be blue." While the screen has the link open (the transmitter's update, its help files, the pilot's files
copied or put back) the radio is idle and the LED is now blue (LinkMode.h); the main loop puts red back when the link
closes. The receiver's update goes over the radio with a model connected, so green stays right there.

## OK at the bottom right (screen 1.8.5, 4 Oct 2026)

Malcolm: "For consistency with the rest of the system, let's rename the button OK and put it on the right, which is
where all the other OK buttons are. 'Same as screens' can move over to the left. And if there are other screens where
the accepting and departing from the screen is not an OK bottom right, then I think it should be." Every page of the
screen's own now leaves by OK at the bottom right: a box's theme page (Same as screens on the left), the box chooser
(Theme on the left), the box sizes, Appearance, the WiFi list and a known network's page, a photo from a phone, and
the versions list. Cancel stays where a job is being stopped (joining a network, fetching an update).

## Themes (screen 1.8.4, 4 Oct 2026)

Malcolm: "I don't think we need both panels and text because the text is displayed within the panels. So perhaps the
subheadings are not needed. And I don't think we need 'hints look like this'. We have here 12 themes that can be edited
each with a foreground and background colour. A further six are appearing below, and I don't think these are needed, and
I'm not sure what they do! Perhaps the original 12 that we can edit are sufficient." And: "Perhaps it's good to call
them themes rather than colours, because each has two colours."

- **Themes:** twelve, each a panel colour with its own text colour. The Themes page shows twelve big swatches, each
  number in its theme's text colour on its panel colour; no headings, no hint line. One theme is the screens'.
- **Edit themes:** touch a theme, then 'Panel colour' or 'Text colour' and the bars. The six separate text colours are
  gone: a text colour belongs to its theme.
- **Front screen boxes** take a theme ('Theme' in the box chooser; 'Same as screens'). Settings from before are read:
  a box's panel becomes its theme.
- The screens' setting from before is read too: the panel colours as they were, the screens' text colour kept on the
  screens' theme, the other themes with the text colours they came with.
- Appearance's button is 'Themes'; help (APPEAR.TXT, TXSETUP.TXT, FLIGHT.TXT) says themes; COLOURS.TXT (never shown) removed.

## "Example text" (screen 1.8.3, 4 Oct 2026)

Malcolm: "I think it's working well now, bravo!! I suggest we should change 'Words  a hint' into 'Example text'." Done:
the sample in Edit colours shows Title, Example text and Model name.

## The bars away from the edge (screen 1.8.2, 4 Oct 2026)

Malcolm, on 1.8.1: "the three sliders are very close to the right hand edge of the screen, which makes it difficult to
slide it all the way to the right ... putting their descriptor words on the other side". And: "when I press okay, the
selected text colour sometimes fails to appear as the colour in use on that selected colour number."

- The bars now run from 400 to 682, their names to their right.
- A reading far from the finger's last place is not followed unless the next reading agrees: the touch chip gives the
  odd stray point, worst at the edge of the glass, and the last reading before a lift decided the colour. The likely
  cause of a colour that was not the one dialled; not seen on the Mac, to be confirmed on the transmitter.

## Edit colours keeps still (screen 1.8.1, 4 Oct 2026)

Malcolm, on 1.8.0: "editing the panel colour works very well. But when I edit the text colour, things go very strange:
The background colour all over the screen changes as I edit ... the colour of the text in the example box should change
to match what I have selected, but the background colour should not change at all." Two causes:

- The page repainted itself in a panel just made only at the next touch of a swatch, so a panel edit landed as a
  whole-page colour change when "Text colour" was pressed. Edit colours now keeps the colours it opened with; the work
  shows in the sample and the swatches, and the Colours page takes it at OK.
- The sample's ground (and the edited swatch's) swapped to a grey whenever the colour stopped reading on the panel, so
  it flipped back and forth along the colour bar. The sample now always sits on the screens' panel, reads or not; the
  swatch's grey is chosen when the colour is picked and kept. The numbers on the panel swatches are plain black or
  white while editing, so only the colour being made moves.

## Appearance (screen 1.8.0, 4 Oct 2026)

Malcolm: "Background and colours, and flight screen, are very closely associated, and yet they are separated on the
transmitter set up screen. I think they merit their own subcategory: appearance. Also, I think flight screen should be
renamed front screen." And: "Editing the text colour does not seem possible yet, and I'm not sure what you mean by
quieter words. The model image is still not showing in more than one box."

- **Transmitter setup > Appearance:** one button where Background was, opening a page of three: "Background picture"
  (the main board's own page: its old button is pressed for the pilot, out of sight), "Colours" and "Front screen";
  Back, and Help at the top right (APPEAR.TXT, new). Each comes back to Appearance when it is done. Transmitter updates
  is two wide again, on one line. The Background page loses its Colours button (one row, as before 1.7.0).
- **Front screen:** the flight screen's new name, on its pages and in the help (TXSETUP, FRONT, FLIGHT, COLOURS).
- **Edit colours:** sliding the colour bar did nothing to white (no strength) or black (no light), so text colour 1
  (white) seemed not to edit. The colour bar now gives a colour without strength or light some of each. The bars are
  named on the page: Colour, Strength, Light. The sample's grey words are "hints", not "quieter words".
- **Two picture boxes:** on the Mac the picture shows in every box. The box chooser's "Model" (the model's name, next
  to "Model image") is now "Model name", the likely cause of the second box showing the name, not the picture.
- How the Appearance page goes and comes back (the main board changing page, a blank screen, flying, a page that never
  comes) is in lib/LdrcTheme and tested on the Mac (test_theme: 1108 checks).

## The picture in every box (screen 1.7.9, 4 Oct 2026)

Malcolm: "The image does appear! But I noticed if I put it into two boxes, I only get the image in the first." (So the
1.7.7 fix for the picture box after an update worked.) On the Mac every box showed it; on the transmitter the card was
not read a second time. The picture is now read once into memory and every box that shows it draws from that copy;
it is forgotten when the flight screen goes, so a new photo of the same name is read afresh.

## Colours by number (screen 1.7.8, 4 Oct 2026)

Malcolm: "It might be better to give our colours numbers rather than names. Because if I define green to be blue
instead, the name will look a bit wrong!" The swatches on the Colours page, in Edit colours and on a box's colour page
show numbers: panels 1 to 12, text colours 1 to 6, each in a colour that reads on it.

## Text colour button, and the picture box after an update (screen 1.7.7, 4 Oct 2026)

Malcolm: "Model image does not yet appear in the box. The defined colours area is good, but it lacks a button to define
the text colour."

- **Edit colours:** two buttons above the bars, "Panel colour" and "Text colour", say which is being made and switch
  between them (each goes back to the one last touched); touching a colour still picks it too.
- **The picture box:** the screen forgot the model picture's name at its own restart (after an update) until the main
  board showed its front page again, so the box (and the setup page's) had nothing to show. The name is now kept in RTC
  memory through our own restarts (as the page to come back to is). Not seen failing on the Mac, so not proven on the
  transmitter: a box that cannot find its picture now says which ("Raw420: no picture").

## One set of colours, made on the Colours page; the model's picture in a box (screen 1.7.6, 4 Oct 2026)

Malcolm, with a photo of the Colours page on the transmitter: "It works beautifully! But I had thought the option to
define the colours would occur on this screen so that it can affect all of the backgrounds, and these options would
simply be reused for the individual boxes on the defined front screen." And: "can we add to the available box options
'model image'".

- **The Colours page holds the colours:** twelve panel colours and six text colours, now eight dark panels plus red,
  white, yellow and sky, and white, cream and lemon plus black, burgundy and navy for text. **Edit colours** there
  changes any of the eighteen to any colour (colour, strength, light: three bars that follow the finger; a sample page
  shows it; Cancel, Defaults, OK). One panel and one text colour are the screens'.
- **Light screens work:** on a light panel the model's name takes the text colour (yellow would not read on white),
  the quieter words and the strip are worked out from the colours, and the text colours that suit a light panel are
  shown on a light ground on the page.
- **The flight screen's boxes reuse them:** touch a box, then Colour: the twelve panel colours and six text colours,
  the box as it will look beside them, Same as screens, Done. A box given only a colour takes the screens' text colour
  where it reads, else black or white. The flight screen's own Edit colours page (1.7.5) is gone; its choices are read
  as the same colours where they exist.
- **Model image:** a new thing for a box - the front page's own model picture, as big as the box allows, the model's
  name above it.
- Settings: the screens' colours "t2 P I" (+ the pilot's own colours when changed; 1.7.0's names still read); a box's
  colours "b:F.I,...".
- Navy and white: all 183 page pictures of the scenarios byte-identical to before.

## Colour pairs of your own (screen 1.7.5, 4 Oct 2026)

Malcolm: "We have several 'mild' colour options that are not very dissimilar. I'd like to use some brighter options - eg
red with white text; white with burgundy text... but we mustn't have too many options... Hence can we have an area that
allows our selection of colour options to be itself defined from infinite colour options?"

- A box colour is now a pair: the box and its words. Still twelve to choose from when a box is touched, each shown as
  "Aa" in its own two colours. The defaults: six dark with white words (navy, teal, forest, wine, plum, black) and six
  bright (red with white, white with burgundy, yellow with black, sky with navy, green with black, silver with black) -
  every pair 5:1 or better.
- **Edit colours** (beside Done when a box is touched): the twelve pairs on the left, the chosen one as a box on the
  right, Box / Text for which of its colours to change, and three bars: colour (the rainbow), strength (grey to vivid),
  light (black to bright) - any colour at all. The bars follow the finger. Cancel puts the twelve back, Defaults gives
  the twelve as they came, OK keeps them.
- In a light box, "ON" and "--" take the box's own text colour (green and grey would not read on white or yellow);
  amber and red still take over a box whose value needs a look.
- Settings: "c:" now numbers the pairs (1.7.4's colour names still read, as the pair with that box colour); "p:" holds
  the pilot's own twelve, written only when they differ from the defaults.

## A colour for each box (screen 1.7.4, 4 Oct 2026)

Malcolm: "When clicking a box to define its contents, can we also pick a colour for that box?"

- Touching a box on the setup page now offers its colour too: the twelve panel colours of the Colours page in a row
  under the things it can show. A colour is kept at once and the page stays (then a thing, or Done). The box's own is
  marked. Picking the Colours page's current panel colour makes the box follow the Colours page again.
- Every writing colour reads on every one of them (they are the Colours page's dark panels); amber and red still take
  over a box whose value needs a look.
- Settings: a token of its own at the end ("... c:,teal,,,wine,,,,"), so a screen before 1.7.4 reads the rest as
  before and ignores it.

## Use defined, and Help on the flight screen (screen 1.7.3, 4 Oct 2026)

Malcolm: "On the original screen let's add 'use defined' as a middle button and on the defined let's add help button
top right."

- **Front screen:** "Use defined" in the middle of the bottom row, between Transmitter and Model. The link (the word
  "Connected" or "Sending Parameters ..." and the green quality bar) moved up into the band just above the buttons, side
  by side, the bar out to the Model button's right edge; the buttons came down 4 pixels. Same boxes, same names: the
  main board writes them as before.
- **The choice now lasts:** "Use original" keeps the front screen until its "Use defined" is pressed, or until the next
  take-off or landing (then the When rule again). No more ten-second return. "Use defined" works on the ground too, and
  with When: never.
- **Help** at the top right of the flight screen, as on the front screen: its own help file, FLIGHT.TXT (new).

## Flight screen buttons (screen 1.7.2, 4 Oct 2026)

Malcolm: "When flying with newly defined screen, any press returns to default. Instead, let's include 'use original' as
an option, and on the defined front screen add the 'model setup' and 'transmitter setup' buttons."

- Three buttons along the bottom of the flight screen: Transmitter setup (left, as on the front screen), Use original
  (the front screen for ten seconds, longer while it is being touched), Model setup (right). A touch anywhere else does
  nothing. The two setups press the front screen's own buttons for the pilot (b0 "Transmitter", b1 "Model": the main
  board hears exactly what it always hears); never while the screen's link is busy with the main board.
- The boxes give up 56 pixels at the bottom for the buttons; every layout still fits (host tests).

## Box sizes on the flight screen (screen 1.7.1, 4 Oct 2026)

Malcolm: "It would also be great if a user could define the relative sizes of these boxes as inevitably some will be
more important. Box size should be linked to font size."

- **Box sizes:** the setup page's "Boxes: 6" button became "Box sizes": twelve layouts, each shown as its boxes - one
  box, two, four, six or nine equal ones, one big with two, four or six small, one wide with three or four small, two
  big with three or four small. Box 1 is always the biggest; what each box shows is kept when the layout changes (a box
  beyond the new layout's keeps its choice for a bigger one). Settings "f2 w1 big4 s1 ..."; the old "f1 ... b6 ..." is
  still read.
- **Numbers grow with their box:** each box's number is as big as the box allows, up to three times the 64-pixel font
  (192 pixels), drawn from the font's own smooth letters (scaled, made once for each size and kept). The size comes
  from the widest value the box can expect ("88:88" for the timer, "8888 RPM" for the head speed), so it does not jump
  as the value changes. Boxes of one size show their numbers at one size; words (bank, model) as big as their box allows
  but never bigger than the numbers beside them. A big box's name and small line are bigger too.
- Host tests: every layout inside its area, no overlaps, box 1 the biggest, 92 % of the area used; sizes with
  made-up fonts (1113 checks in all).

## Colours and centre bars (screen 1.7.0, 4 Oct 2026)

Malcolm, in the morning: "Because the dark blue and white are becoming ubiquitous around this firmware, let's make
these colours user-definable somewhere." And: "your style of making the channel bars move out from the centre ... should
be imitated on the default front screen as well as the channels screen."

- **Colours:** Transmitter setup > Background and colours > Colours. Twelve panel colours (Navy, Royal, Slate, Teal,
  Forest, Olive, Brown, Wine, Plum, Grey, Midnight, Black) and six text colours (White, Cream, Lemon, Mint, Sky,
  Silver). The page is drawn in the colours as they are touched; OK keeps them, Cancel leaves things as they were.
  Only dark panels and light text are offered: all 72 pairs read well (contrast 5.8:1 or better) with everything that
  keeps its own colour - the buttons, the white boxes you type into, yellow, red and green words, the pictures.
- **How:** the restyled pages use two navies nothing else uses (panel 0x114A, strip 0x08A6). When a page is loaded,
  a component whose background is one of them follows the chosen panel colour, and its white and light grey words the
  chosen text colour (lib/LdrcTheme). The main board is not involved and nothing new crosses the wire. The flight
  screen and the screen's own pages (WiFi, updates, model pictures, the link panel, messages) take the same colours.
  Navy and white draw every page exactly as before (all 197 test pictures compared).
- **Centre bars:** the channel bars on the front screen and the Channels screen grow from a middle line, as on the
  flight screen. The bar's end is where it always was: only where the colour starts has changed.
- Teensy unchanged (still B24); help texts: TXSETUP, COLOURS (rewritten: the old one described RGB sliders), CHANNELS,
  FRONT.

## The flight screen (screen 1.6.0, 3-4 Oct 2026)

Malcolm: "could you create a user definable alternative front screen? This screen could be put up instead of our
default front screen while flying containing those items of information that the user has selected."

- **What it shows:** 4, 6 or 9 boxes, each the pilot's choice of timer, flight battery, transmitter battery, link,
  head speed, ESC temperature, current, capacity used, bank, rate, motor, clock, model, or the channel bars
  (1-8, or all 16 in two columns: each bar grows from a centre line, normal travel reaching the side; Malcolm,
  10-03: "Please make one of the front screen options 'Channel bars' (first 8 or all 16)"). A strip along the top:
  the model, the bank, the time. Numbers are big (64 pixels); a box turns amber or red when its value needs a look
  (battery 40 % / 20 %, link 75 % / 50 %, ESC 80 / 95 degrees); "--" when there is nothing to show.
- **When:** while flying (the main board's own rule: safety off, or the motor on where no safety switch is defined),
  always in place of the front screen, or never. A touch shows the front screen for ten seconds (longer while it is
  being used). "Stays lit" keeps the screen saver away while it shows.
- **Warnings stay seen:** the front screen's BATTERY LOW and a lost link in flight turn the strip red; the power-off
  countdown (TURN OFF?!) takes the flight screen away so the front screen's countdown shows (until 1.5 s after the
  last second is written: the words stay in the box when the button is let go). Stays lit also for a minute after
  the link goes, and while armed.
- **Setup:** Transmitter setup > Flight screen: the screen as it will look, live. Touch a box to choose what it
  shows; When / Boxes / Stays lit; OK. Kept in the screen's chip, written only when the wire is quiet and never in
  flight.
- **The main board does nothing new.** The flight screen is made of what it already sends to its front page, and
  drawn by the screen on its own layer ("the Teensy flies, the screen talks"). Nothing is sent to the main board but
  the usual "someone is here" word every 20 s.
- Code: lib/LdrcFlight (host-tested, hmi/test_flight), src/flight_draw.h, src/flight_source.h,
  src/flight_device.h; the Mac renderer draws it too (`@flight`, `@flightsetup` in hmi/render_host).
- **Teensy B24 (display only), found on the way:** on a Rotorflight model the front screen's Warning box showed the
  ESC temperature ten times a second, so a low battery only showed whatever words were last in the box, and the
  battery check hid the box once a second (the ESC temperature blinked). Now a low battery puts "Battery LOW" in the
  box and the ESC temperature waits; with the battery fine, the box is hidden only when there is no ESC temperature.
  And the current ("Amps:") no longer overwrites the power-off countdown in the same box while the button is held.
- **Checked before release (a read-only review of the flight screen):** its own layer numbers (it had borrowed the
  picture chooser's, so the setup page's buttons would not have answered); taps settled over 80 ms like every other
  page of ours (one tap could have counted twice); the setup page goes when the main board leaves its page; the
  flight screen is in place before the front page is drawn (no flash on the way back); nothing of ours over a
  blanked screen (the screen saver, "Closing down ..."); a waking touch does nothing more.

## Tidied overnight (B23 + screen 1.5.6, 3 Oct 2026)

Malcolm, at bedtime: "The screens are good!! But some need tidying ... perhaps you might examine each for visual
imperfections." Every restyled page was rendered on the Mac by the screen's own drawing code
(`hmi/render_host` in the screen's project), filled with what the Teensy really sends (`hmi/scenarios`, written
from this code, worst cases included), and checked by eye and by `hmi/lint_pages.py`.

- **Screen firmware 1.5.6.** Sliders, the empty model-picture frame and other see-through parts show the card
  they sit on, not the background picture (red bands behind the sliders). A line too long for its box ends in
  "..." (long model and owner names). Centred words ignore trailing spaces ("Not used" sat 31 px left of centre).
  A box marked "fresh" starts from its page's own words at every visit (Set trim directions came back saying
  "... is defined!").
- **Pages.** Nothing clipped or touching the card's edge any more (Inputs Ch10-16, Telemetry, the bank-copy
  hint, GPS coordinates, the Rates page's channel names, Mixes' bank name, Rename on two lines); lists framed like
  the other white boxes; sliders grey and white like the switches; the yes/no question wraps and keeps a visible
  edge over the Models page; "File error!" can be seen on the Models page.
- **Page script repairs:** Failsafe All/None now save channels 9 and 10 (the script spelled them "sf9sg10");
  editing D gain on Governor (profile) brings up Save; Rates + reports its collective box; the bank-copy Governor
  switch greys its own label; no blank row in the bank-name lists.
- **Teensy B23 (display only):** Trims labels follow their sliders in stick mode 2; the countdown minutes box is
  white when the timer counts down; Max safe ESC current shows 0 rather than nothing; "No model ID found.";
  "Gear down" and "Gear up" the right way round.

Found and NOT changed (for Malcolm to decide): "Stop Bind" stays after a successful bind (main.cpp:300); after
the Switches page's OK, and on Batteries, a screen timeout returns to the wrong page; Help then back goes to the
front page from the channel pages; an empty macro shows "Aileron"; Rotorflight rates may be scaled for the
Rotorflight rates type whatever type is set (Actual); log files sort by day number; files of 1000 KB or more run
into their names in the Files list.

## The new look (screen files, 3 Oct 2026)

Malcolm asked for the three System pages to look better "without altering its functionality" (screen 1.5.4), then for
"the same clean style on the remaining pages". 44 pages now share one style: a navy title strip with Help at its right,
one navy card, and the buttons in four places along the bottom (Back, second, Next, OK). Every scrolling list shows
whole rows with a margin (screen 1.5.5).

**The pages behave exactly as before.** Each is restyled by a script from its original (`hmi/originals/<id>.json` in
the screen's project) and `hmi/pagestyle.py` checks it: every component keeps its name, id, type, events, keyboard,
rules and starting values; only places, sizes, fonts, colours and fixed words change.

- **Kept on purpose:** the Rotorflight colours (Roll, Pitch, Yaw, Collective; the olive headers) and the white value
  boxes, which the Teensy colours while it reads. The two bank-copy dialogs stay light, red for restore and green for
  backup, because their switches colour the labels black or grey.
- **Not restyled:** the front page, keyboards, splash, Pong, graphs, scan, calibration, sticks, gaps, the help viewer,
  the picture page (the chooser covers it) and the Models page (tidied before).
- **Fixed on the way:** Governor (global) showed "x10" labels with a broken sign (the "×" was lost when the HMI was
  turned into pages). They now read "x10", like "Hold timeout x10".
- **The Teensy's messages fit:** each "Reading values ..." box was measured against its longest message in the
  screen's own fonts (`hmi/fontw.py`).

Releases: "2.5.6 B22 (screen 1.5.5) new style 1", "... 2" and "... 3" (files only).

## Dark at power-on (screen 1.5.3, 3 Oct 2026)

Malcolm: "When turning on the transmitter, it flashes brightly before the front screen appears. I wonder if it could
start up with zero brightness and then fade in gently while the opening screen is in view?" The Teensy already does
that fade (setup: `SetBrightness(1)`, `page SplashView`, dim 1 to 99), but the screen lit itself fully at power-on and
showed its own start-up text until the Teensy's first `dim=`. Now the backlight stays off until that first `dim=`;
a restart of the screen alone (an update) fades back to the brightness it had (RTC memory); a screen with no Teensy
lights up by itself after 6 s.

## Model pictures: the screen's own chooser, and photos from a phone (B21 + screen 1.5.0, 3 Oct 2026)

Malcolm: "Can we add a feature that allows a user to add a photograph of a model easily, and adjust it on arrival so
that the dimensions and pixel count are ok?" And: "I put those images onto both discs, because the teensy was not able
to give me the directory from the Nextion and the Nextion could not display quickly from the teensy! ... you might be
able to find an altogether better way of managing the pictures."

- **One copy, on the screen's card.** `/images/<name>.565` (the release's) and `/images/mine/<name>.565` (the pilot's
  own, found first, never touched by an update). 320 x 200, RGB565. The Teensy keeps only each model's picture NAME
  (8 characters, as before); its own `/Images/` folder is no longer needed.
- **The chooser.** When the Teensy shows "Choose image" (ImageView), the screen covers it: thumbnails, 8 to a page with
  arrows, Help (the Teensy's own help, run from its hidden Help button), **Add photo**, **Delete** (the pilot's own
  photos only, and it asks first), **Cancel**, **OK**. OK answers `LDRCIMG <name>`, Cancel `LDRCIMG` alone. The answer
  is said again every 0.7 s until the Teensy leaves its page; it saves the model and goes back, as its OK did. A Teensy
  before B21 never answers: after 4 s the chooser steps aside and its old page is underneath.
- **Add photo.** A QR code for `http://<screen>/photo?k=<key>`. The key is made for each chooser and works only while
  it is open. The phone's page (`hmi/web/photo.html` on the screen's card): choose a photo, drag and pinch it into the
  frame, a name of 8 letters at most, Send. The PHONE makes it exactly 320 x 200 RGB565 (dithered) and sends it to
  `/photo/put`; the screen checks its size and header and keeps it as `/images/mine/<name>.565`. The chooser asks for
  the WiFi while it waits (as the update panel does), never while the radios must be off.
- **Code.** Screen: `lib/LdrcPics` (the thinking, `hmi/test_pics`: 153 checks), `src/pics_device.h` (card, thumbnails,
  drawing, web), `sd/hmi/web/photo.html`. Teensy: `ChooseImage.h` (`ChooseImageFromScreen`), the hook beside the
  receiver-update word in `main.cpp`, `LDRC_IMAGE_WORD` in `LdrcLink.h`. Help: `IMAGE.TXT` rewritten.
- **Proven the same evening** (Malcolm's first photo: the 1960 control-line Viscount). Then: "it briefly displays my
  old screen ... could then be erased from our memory?" **B22 + screen 1.5.1:** the screen opens the chooser inside
  `loadPage()`, before anything of the old page is drawn; the Teensy names the model and its picture BEFORE the page
  (`ImageView.t0.txt=`, `ImageView.exp0.path=`; the screen now keeps a picture named before its page is shown) and no
  longer lists `/Images` on its card. The old page is never seen.
- Then "about 2/3 of a second pause ... perhaps ... a little please wait banner?" **Screen 1.5.2:** the chooser's frame
  ("Opening...") appears the moment the button is released; the card's picture list is read by name only and kept; the
  thumbnails of the page it will open on are made in the background on RXOptionsView and ModelsView.

## Louder sound without distortion (screen 1.4.7, 3 Oct 2026)

Malcolm, on the first transmitter built with the new screen: the speaker distorted as the volume went up, yet the
same speaker on a Nextion had been louder and clean. Two causes:

- **The amplifier has less power.** The CrowPanel's NS4168 runs from 3.3 V (R10 fitted, R45 not). At 5 V its inputs
  would want 3.5 V, more than the ESP32's 3.3 V signals, so the board's own choice is the safe one. Its anti-clipping
  (NCN) turns it down smoothly when it cannot follow.
- **The screen bent the sound.** Screens 1.0 to 1.4.6 multiplied the clips by up to 3 (volume 100) into a limiter that
  squashed every sample that came out too big: 19 % of the sound at volume 20, 45 % at 100. That was the distortion.

Now the screen's gain is at most 1 and no sample is ever bent. The loudness is in the clips themselves, processed once
on the Mac by `hmi/loud_audio.py` (in the screen's project, used by `build_sd.py`): a 250 Hz high-pass (the small
speaker cannot play lower), a phase rotator, a gentle compressor and a look-ahead limiter, then the loudest sample at
-1 dBFS. Speech is 5 dB louder on average; clicks and beeps are left byte for byte. Volume 100 plays as loud as the old
50, clean. The same day Malcolm found it "extremely toppy": evening out the loudness had lifted the quiet consonants,
which are treble (8 kHz +4 dB), and the 250 Hz high-pass had thinned the voice. The release "2.5.6 B20 (screen 1.4.7)
warmer sound" (sound files only) cuts at 100 Hz instead, and after the limiter puts in a -6 dB treble shelf at 4 kHz
and a 9 kHz low-pass: every octave band within about 1 dB of the original clips. Then "less top, less distortion,
more volume": the release "darker sound" cuts treble from 2.5 kHz (8 kHz about 6 dB below the original) at the same
loudness, with gentler gain changes. Steady tones come out of the processing with 0.01 % harmonics, so the distortion
left is the amplifier's. The Nextion's speaker output gives up to 1.5 W from 5 V; this amplifier about 0.5 W from
3.3 V. A 4 Ω speaker of the same size doubles its power, within its rating. Then Malcolm found the edge by ear: "about
33% it's fine - but distorts if I go higher". The clips peak at -1 dBFS, so the amplifier runs out of room at about
half of full scale. Screen 1.4.8 makes volume 100 send what 30 sent before (`AUDIO_MAX_GAIN` 0.55): the whole slider
is clean, and the pilot sets it to 100. More loudness would need more limiting (`DRIVE_DB`: 13 instead of 10 gives 1 dB more, with three times as
much limiting) or more amplifier power.

## The slow update of 2 October, and what it was (B20 + screen 1.4.5)

Malcolm's update to B19 paused so long on "Installing" that he thought it had hung. The screen's record (/update/log.txt)
put the time not in the install but in sending the firmware: 99 s for 348 kB, where every earlier install took 6-10 s.
A speed test from the Mac (`teensy_ota.py put` of the same file) took 128 s with **121 requests repeated**, each after a
1-second timeout. The cause was mine: B15 copied the breadcrumb to the clock's battery-backed registers (SNVS) every
50 ms, and each write holds up the next access to the peripheral bus - long enough for the Teensy's serial port to drop
bytes from the screen. B20 writes the breadcrumb only when one crumb has lasted 2 s (what a hang looks like), once, and
clears it at a clean power-off: the same test then took **6.9 s with 1 repeat**. (B15-B19 also lost bytes from the
screen's touches the same way, and stalled the bus 20 times a second in flight: B20 is an important fix.)

Screen 1.4.5: a step of the transmitter's that lasts more than 3 s shows its seconds ("Waiting for the transmitter to
restart  (8 s)"), so it is never taken for a hang; and **Install again** on the "Up to date" panel puts every part of the
same release in again (Malcolm: "a reinstall option, so that we can install the same update more than once for our
tests") - files still go only where they differ, and firmware proven here needs no trial.

## Firmware that has proved itself here is not tried again (B18 + screen 1.4.4)

Malcolm: *"testing new firmware is good - but only needed for the first installation. After that we can KNOW it's ok
and not test that one again."* The 30-second trial only ever runs straight after an install; it would repeat only when
going back to an earlier version and forward again. Now `/FW/PROVEN.TXT` on the Teensy's card lists every firmware
that has passed its trial on this transmitter, by the CRC-32 of its package (a rebuilt firmware that kept an old name
is a different program and is tried like any other); `/FW/STAGED.TXT` says which package went in, so that the firmware
on trial can add itself when accepted. Installing a package on the list writes "confirmed" at once (whatever the
firmware's age: older firmware reads "confirmed" and starts no trial), and the screen sees it straight after the
restart and skips the wait. The comparison of how the model's settings are read still follows every install.
Only firmware accepted by B18 or later is on the list: older versions are tried once more when installed.

## The pilot's own files: copied first, never written by an update

On the Teensy's card the pilot's own files are `models.dat` (every model, **and the transmitter's own settings**: they are
its first 512 bytes), the model files he has exported, `/mod/*.MOD`, and the logs, `/log/*.LOG`.

- **No update writes or deletes any of them.** The release tool refuses a release that names one, the screen refuses
  such a list, and the Teensy refuses the write.
- **Before new firmware goes into the Teensy, a copy is made on the screen's card:** every file of the card's own folder
  (so `models.dat`, and a settings file too if one is ever added, whatever it is called), every `*.MOD` of `/mod`, and
  every `*.LOG` of `/log`.
  **If the copy cannot be made, no firmware goes in.**
- **A copy counts only when it has been read back from the screen's card** and agrees with the Teensy's checksum (a full card
  does not say so when a file is closed). `models.dat` is made sure of once more: the Teensy is asked for its size and
  checksum, and the copy is read again. A file that is listed and cannot be fetched stops the job. A folder that cannot be
  *read* is an error, not an empty folder. What is not copied (a file over 4 MB, a name the link cannot use) is said by name,
  on the green panel too.
- **Models and settings: a new folder each time**, `/teensy/backup/<number> <the firmware it ran>/`, with `about.txt`
  saying when and why. A copy is never written over an older copy. The newest 12 are kept.
- **Logs: one store that grows**, `/teensy/backup/log/`. They are many (110, 4.5 MB on Malcolm's card) and never change,
  so a log of which a copy of the same size is held is not fetched again: 163 s the first time, 16 s after that.
  A log is compared by size **and checksum**. A copy is replaced only by a file that *begins with all of it* (the log has
  grown). Anything else (smaller, or begun again under the same name) leaves the copy where it is, as `<name>.older`,
  `.older2` ...: a copy once taken is never removed.
- The green panel says so: *Your models, settings and logs were copied first: 145 files.*
- If a future firmware changes the format of the model files, going back to an earlier version will need the copy of
  the models made before that update: `restore`, below.

From the Mac (`ESP32-board2/board4/nextion-emulator`):

```
dev/teensy_ota.py backup            # a copy now: to the screen's card and to ~/Documents/LDRC backups
dev/teensy_ota.py sets              # the copies on the screen's card
dev/teensy_ota.py restore "0002 2.5.6 B6 29-09-26"    # models.dat and the *.MOD files of that copy, back onto the Teensy's card
dev/teensy_ota.py list /mod         # what is in a folder of the Teensy's card
```

`backup` also brings the logs to `~/Documents/LDRC backups/log` (only the new ones). A file on the Mac is never emptied or
written over by one that is not the same file grown: what the Mac held stays, as `<name>.older`.

`restore` sends `models.dat` and the `*.MOD` files of a copy that is whole (it has its `about.txt`), and only what differs.
Never the logs. **The transmitter restarts when the link closes**: what it held in memory is no longer what its card holds.
From the moment one of the pilot's files has been replaced it saves nothing (the power button included), so the settings
of before cannot be written over the ones put back. There is no restore button on the screen yet.

*Why that matters (found by review, 29 Sep 2026, proved on the real SdFat):* until 2.5.6 B7 the Teensy kept `models.dat`
open while the link replaced it. The save at power-off then wrote through the old handle, into clusters that by then
belonged to other files: `models.dat` could not be read to its end and a model file was damaged. `restore` had been run
once on the transmitter, with files that were "already the same", so nothing was written and nothing was harmed.

## WiFi: Transmitter > WiFi

The transmitter knows up to eight networks (the house, the phone, the club) and joins the best one it can hear.
**No network name and no password is in the firmware**: they are typed on the screen, once, and kept in the screen's chip.

| On the page | What it does |
|---|---|
| The list | The networks in range, the strongest first; the ones the transmitter knows come before the strangers. Bars = signal, a padlock = needs a password. Until the radio has looked, a known network says *Checking*; the one joined says *Joined* at once. |
| A touch on a new network | The keyboard: `abc`, `ABC`, `#+=` are three layers of keys, **Delete** goes on deleting while held, **Hide** shows stars instead of the password. **Join** wakes up at eight characters. |
| A touch on a known network | **Join**, **New password** (the router's password has changed), **Forget**. |
| **Look again** | Looks around afresh (a phone's hotspot that has just been switched on). |
| **WiFi off / WiFi on** | The pilot's own switch. (Whatever it says, the radio is off while it must be: below.) |

- A wrong password is said in words, and the transmitter goes back to the network it had.
- **At the field:** the phone's hotspot is a network like any other. Switch it on, **Look again**, touch it, type its
  password, once. From then on the transmitter joins it by itself when the house's WiFi is out of range.
  An iPhone must have *Maximise Compatibility* switched on (Settings, Personal Hotspot): the screen's radio is 2.4 GHz
  only, and the phone shows its hotspot to new devices only while that page of its settings is open.
- The page is the screen's own: it works on a new screen whose card is empty. "Check for update" offers **WiFi setup** when there is no WiFi.
- No picture of the screen can be fetched from the Mac while the keyboard is up; `GET /wifi/status` gives names, never a password.
- The list of networks is written to the chip as **one value**: after a power cut the transmitter knows the old list or the
  new one, never a name with another network's password. A network that refuses the password waits its turn, so the phone
  is joined although the house is stronger. One handshake that times out (a weak signal) is not a wrong password.

## When the screen's radios are off

**The pilot's rule** (Malcolm, 29 Sep 2026): *"Motor ON to kill wifi only if no safety switch was defined. If safety switch is
defined then safety off should kill wifi and ble irrespective of motor status."*

| A safety switch is | WiFi and Bluetooth are off while |
|---|---|
| defined | the safety is **off**, whatever the motor switch says |
| not defined | the motor is **on** |

The rule is decided in ONE place, on the main board (`RadiosMustBeOff()`, `FlightGuard.h`), and sent to the screen once a
second and at once when anything changes: `ldrcst=<bits>`.

| Bit | Means |
|---|---|
| 1 | the motor is enabled |
| 2 | the safety is off |
| 4 | a model is connected |
| 8 | a safety switch is defined |
| 16 | a model was connected less than a minute ago |
| 32 | **the screen's radios must be off** |

The screen obeys bit 32 on every page (until now it read the front page's "Motor is ON" text, so with another page showing
its WiFi stayed on in flight). At start-up its radio waits for the main board's word, or 8 s: a screen that restarts in
flight does not come up with its WiFi on. A main board older than 2.5.6 B8 says no `ldrcst`; the text is used as before.
The same rule shuts the file link on the Teensy's side (`LinkRefusal()`), whatever the screen believes.

## 29 Sep 2026: the passwords that went to the website, and what was done

The first screen firmwares (1.0.0 to 1.0.3) had the house's WiFi password and the phone's hotspot password compiled in
(`include/secrets.h`), and were published on messiter.com for the button "Check for update". They could be downloaded by
anybody from about 19:10 to 20:12 BST. Found the same evening while the WiFi page was being begun, and:

1. the five files were taken off the website (`dev/release_v1b.py purge`), each address proven to answer 404;
2. `release_v1b.py` searches every file for the texts of `secrets.h` at `stage` and at `publish`, and refuses.
   *The review found that this gate read only one form of line* (`#define NAME "value"` with nothing behind it, a name with
   PASS in it, 8 bytes or more). Now every string literal of the file counts, whatever its line looks like
   (`dev/test_release_gate.py`), every file below the staging folder is searched (the upload takes them all), and
   **the screen's firmware is built in a copy of its project that has no `secrets.h` in it** (`dev/out/screen_build`);
3. from 1.1.0 the firmware holds no network at all (the WiFi page, above); 1.2.0 also erases the copy of the last network
   that the radio's driver had kept in the chip since 1.0.x;
4. **owed:** the host's log (archived daily about 13:10 to `~/logs/` on the FTP account) shows who fetched those five files.
   Only the house's own address should be there. **Malcolm has decided (29 Sep, 22:40) not to change the passwords.**

## The workshop door

Everything the Mac can do to the screen (push firmware, put files, press buttons, replace the Teensy's firmware) used to
be open to anybody on the same network. Fine at home; not on a club's network.

- **The firmware that is published has the door shut.** It answers `GET /status` and nothing else, and takes no firmware
  from the Mac.
- **The pilot opens it on the screen:** hold the **top right corner** for three seconds while on the WiFi. A banner says
  *Workshop door OPEN on House*. It is open on that network only, and stays so across power cycles, until the corner is
  held again.
- A request that changes anything must carry the header `X-LDRC: 1` (the tools in `dev/` do).
- Bench builds (`pio run -e ota_dev`) have it open always. They are never published.
- From the Mac, through a door that is open: `curl -X POST -H "X-LDRC: 1" "http://<screen>/door?on=1"` opens it on the
  network the screen is on, and it is remembered. Done on a bench build BEFORE the transmitter updates itself to the
  published firmware, the door is open when that firmware starts. `on=0` shuts it.
- `GET /status` says `"door":true` or `false`.

## A new screen, a new transmitter

1. **The screen, once by USB:** `cd ESP32-board2/board4/nextion-emulator && pio run -e crowpanel50 -t upload`.
2. **A card** in the screen: FAT32, empty. At power-on the screen finds no pages, so there is no button to press:
   it opens the panel by itself. It knows no network yet: **WiFi setup**, choose the network, type its password, **Done**.
   The panel comes back and offers the files. **Install now**: 40 MB, a few minutes, then it restarts with its pages.
   (The one case in which the panel opens unasked.)
3. **The Teensy, once by USB:** `cd TXV1B/TransmitterCode && pio run -t upload` (B4 or later).
4. From then on: **Transmitter > Check for update**.

## Publishing a release (from `TXV1B`)

```
dev/release_v1b.py stage "what is new"   # builds both firmwares, collects every file, stages the release
dev/release_v1b.py publish               # uploads (files first, latest.txt last), reads EVERY file back and compares
dev/release_v1b.py status                # what is live, what is staged
dev/release_v1b.py latest "2.5.6 B3 (screen 1.0.0)"   # an earlier release becomes the latest again; then publish
```

- Bump `TXVERSION_EXTRA` (Teensy, `1Definitions.h`) and/or `SCREEN_VERSION` (screen, `src/main.cpp`): firmware is compared **by version text**.
  Different firmware under the same number is never offered to anybody.
- The files (help texts from `Help files for SD`, the screen's card from the screen project's `sd/`) are compared by content:
  change a file, stage, publish.
- The pilot's models and logs are never in a release: the tool refuses, the screen refuses, the Teensy refuses.
- The screen's own parser reads the staged release before anything is uploaded; what it would refuse is not published.
- On the site: `https://messiter.com/txv1b/release/` — `latest.txt` (what the screen reads), `manifest.json` (for people),
  `v/<release>/`, and `files/<CRC32>-<size>.bin` (every file once, under the name of its content).
- The site's certificate is checked against the roots in the screen's `include/ca_bundle.h` (Let's Encrypt, Sectigo).

## From the Mac, for development (from `ESP32-board2/board4/nextion-emulator`)

```
dev/teensy_ota.py hello          # who is there
dev/teensy_ota.py install        # new Teensy firmware (after: pio run, then TXV1B/dev/make_fw_package.py)
dev/teensy_ota.py help-files     # the help texts in "Help files for SD" to /help on the Teensy's card
dev/teensy_ota.py backup         # MODELS.DAT to ~/Documents/LDRC backups, dated
dev/teensy_ota.py rollback       # the previous firmware back
dev/teensy_ota.py confirm        # accept the firmware that is running (clears "rolledback")
```

`hello` is answered even while a model is connected: the Teensy says who it is and keeps the link shut.

Every job ends with one line: `DONE ...` or `FAILED at <stage>: <why>`.

## How the Teensy's firmware is replaced, and why it is safe to try

1. The new firmware travels as an ordinary **file** to the Teensy's card, in 1 kB blocks each checked by CRC-32,
   and the whole file is read back from the card and checked again.
2. `MODELS.DAT` is copied to the screen's card first. The firmware now running is copied to `/FW/PREVIOUS.BIN`.
3. The new image is written to the **upper half of the flash** and read back. Up to here nothing is lost
   if power fails or anything goes wrong.
4. With every interrupt off, a routine in RAM copies it over the program and restarts. About two seconds:
   **the only moment at which a power cut means "connect USB"**. The screen says *Do not switch off*.
5. The new firmware is **on trial**. Thirty seconds of running *as a transmitter* (its main loop; time
   spent serving files does not count) = accepted, by the Teensy itself. If it restarts three times
   without that (a crash, the watchdog), the start-up code puts `PREVIOUS.BIN` back by itself.
6. The screen does not take the Teensy's word at once: it checks the version after the restart, hands
   the transmitter back for the length of the trial, then asks again. An install therefore takes
   about 70 seconds and ends `DONE: the transmitter runs ...`, or says that the previous firmware
   came back.

What this cannot cure: firmware so broken that it dies before it has found its SD card, or a power cut in
step 4. Then: USB and the Teensy loader (the button on the Teensy), as ever. A Teensy cannot be bricked.

## The first time, and only then: USB

The firmware in the transmitter today knows nothing of all this. Once:

1. USB cable from the Teensy to the Mac.
2. `cd TXV1B/TransmitterCode && pio run -t upload` — PlatformIO with the Teensy loader app, as ever.
   (The command-line loader fails with "error writing to Teensy" while that app is running.)
3. From then on, `dev/teensy_ota.py install`.

## Where things are

| What | Where |
|---|---|
| The protocol (frames, CRC, package header), shared | `TransmitterCode/lib/LdrcLink/LdrcLink.*` — the master copy; `dev/sync_link.sh` in the screen's project copies it |
| The Teensy's file server (portable, tested on the Mac) | `TransmitterCode/lib/LdrcLink/LinkServer.*` |
| The Teensy's card, flash and start-up trial | `TransmitterCode/include/LinkMode.h` |
| Hooks in the old code | `main.cpp` (setup, loop, the knock in `ButtonWasPressed`), `Nextion.h` (`GetButtonPress`), `Utilities.h` (`KickTheDog`, `GetYesOrNo`) — each marked `V1B` |
| The screen's job engine (portable, tested on the Mac) | `ESP32-board2/board4/nextion-emulator/lib/LdrcLink/LinkMaster.*` |
| The tests | `ESP32-board2/board4/nextion-emulator/hmi/test_link/run.sh`, `hmi/test_update/run.sh`; the wire loses and damages bytes |
| Packages | `dev/make_fw_package.py` → `dev/out/TXFW.BIN` |
| "Check for update": the thinking (portable, tested on the Mac) | `ESP32-board2/board4/nextion-emulator/lib/LdrcUpdate/` |
| "Check for update": the panel, the downloads, the screen's own firmware | `ESP32-board2/board4/nextion-emulator/src/update_device.h` |
| The WiFi page: the thinking (portable, tested on the Mac) | `ESP32-board2/board4/nextion-emulator/lib/LdrcWifi/` |
| The WiFi page: the radio, the store in the chip, the drawing | `ESP32-board2/board4/nextion-emulator/src/wifi_device.h` |
| The button itself | `hmi/overrides.json` (`"+"`), event `ldrc update` |
| Releases | `dev/release_v1b.py` → `NewWebSite/public_html/txv1b/release/` (not in git) → messiter.com |

## Two changes to the old code worth knowing

- **`KickTheDog()` runs on the CPU's cycle counter**, not `millis()`. Flash work holds interrupts off for tens
  of milliseconds at a time and `millis()` stands nearly still meanwhile.
- **Serial1 has 4 kB more receive memory** (`addMemoryForRead`), for a whole frame.

## Status

**29 Sep 2026, evening: proven on the transmitter, from the Mac and from the button. It runs Teensy 2.5.6 B7 and a bench build of the screen ("dev"); the last release installed by the button was B7 with screen 1.1.1.**

| Test | Result |
|---|---|
| Knock at the old firmware (2.5.6 P) | no answer, plain message, not one frame sent, display undisturbed |
| First load of 2.5.6 B1 by USB | link open at once |
| Backup of `MODELS.DAT` to the Mac | 272 kB in 8.5 s, checksum agreed |
| 43 help files compared | 2.1 s; the 2 that differed were sent |
| Install B2, then B3 (from the Mac) | 70 s: sent, staged, swapped, restarted, on trial, accepted by itself |
| Install a build that hangs 8 s after start (`-DLDRC_TEST_FALL_OVER`) | three starts, then the Teensy put B3 back by itself; the screen said so |
| **First release published** (B3, screen 1.0.0: 284 files, 42 MB) | every file read back from messiter.com and compared |
| **Check for update**, first time | offered the files; 281 files compared on the card, none needed fetching, help files' mark written: *Update complete* |
| **Check for update** again | *Up to date* in under a second |
| **Second release** (B4, screen 1.0.1: version numbers, and the idle clock) | offered with both versions |
| **Install now** | 103 s from the button to *Update complete*: 2 files fetched (1.6 MB, 12 s), models kept, Teensy installed and through its trial (70 s), screen firmware written (8 s), restart, accepted |
| **By Malcolm's own finger** (screen 1.0.1 to 1.0.2) | 36 s from *Install now* to *Update complete* |
| The keep-awake, with a panel left waiting | the Teensy's screen saver (120 s) held off while the panel was fresh, then came as designed; a touch woke the screen, the panel still there |
| A screen build made to **fail its trial** (`ota_test_fail_trial`) | gave its place back after 75 s; the previous firmware started and said: *could not join the WiFi, the previous screen firmware (1.0.1) is back* |
| A screen build made to **fall over** 6 s after every start (`ota_test_fall_over`) | the boot loader put the previous firmware back at the next start, and that one said: *the new firmware (9.9.9-test) did not start* |
| **The WiFi page** (screen 1.1.0), tried from the Mac with the remote finger | the list in 3 to 7 s, House *Joined* first; a **wrong password** on House: *Not joined, the password was not accepted*, and back on House by itself 2 s later; the **right password** typed on the screen's keyboard, hidden: *Joined* in 3 s; remembered in the chip |
| The network of the firmware before (1.0.2) | taken over at the first start of 1.1.0: the transmitter never left the house's WiFi |
| A picture of the screen asked for while a password could be read in the box | refused (423) |
| **Release B6 + screen 1.1.0** installed by the button | 155 s: Teensy B4 to B6, screen to 1.1.0 (no network in it), the setup page with its WiFi button fetched as a file; *Update complete* |
| The firmware as served by messiter.com, fetched from outside | the checksums of the description; no password in it |
| **The pilot's files copied first** (release B7 + screen 1.1.1, by the button) | 35 files in 20 s before the firmware went in: `models.dat` (272 kB), 32 model files of `/mod`, 2 small files; then B6 to B7 and screen 1.1.1; 124 s in all; the panel said so |
| The same files fetched again AFTER the update and compared on the Mac with the copy made before it | all 35 byte for byte the same |
| **The logs copied too** (bench build) | 110 logs, 4.5 MB: 163 s the first time; 16 s the second time, none fetched again |
| The WiFi list while the radio is still looking (bench build) | *Checking*, and *Joined* for the house at once |
| Transmitter setup laid out afresh (bench build) | one grid, four columns; seen on the screen by Malcolm |
| **Earlier versions** (1.2.0) | NOT YET on the transmitter: tested on the Mac only (157 checks); staged, not published |
| `restore`, tried with a test file added to a copy | the 35 real files "already the same", the test file written to `/mod`; then removed from both cards |
| A screenshot fetched over a slow WiFi in the middle of the Teensy's files (the screen's loop held for 33 s) | the job failed cleanly: *Update failed*, where and why, nothing harmed. Cured: long web jobs now keep the wire read (`breathe()`) |

### 29 Sep 2026, night: three reviews, and what they changed

Three independent reviews of the day's code (`reviews/2026-09-29/`: the link and the copies, the update engine, the WiFi
page) found 45 things. The worst: the restore fault above; a first install that stopped on every new screen (two sounds
with the same content); a motor rule that only worked on the front page; a secrets gate that could be fooled; open doors.
**Every one has a host test that failed before it was put right** (`reviews/2026-09-29/WHAT-WAS-DONE.md`).
None of it has run on the transmitter yet: see the list below.

Host tests, all of them with `hmi/test_all.sh`:

| Suite | Checks | What it runs |
|---|---|---|
| `hmi/test_link` | 207 | the screen's LinkMaster against the Teensy's real LinkServer, over a wire that loses bytes |
| `hmi/test_link/sdfat` | 29 | the restore on the **real SdFat** of Teensyduino, as it was (must show the damage) and as it is |
| `hmi/test_update` | 255 | "Check for update" from the button to the verdict; the radio rule (`TxState.h`) |
| `hmi/test_wifi` | 96 | the WiFi page |
| `hmi/test_device` | 42 | `src/wifi_device.h` as it is, on a make-believe ESP32: power cuts in the store, joining by itself |
| `TXV1B/dev/test_release_gate.py` | 29 | the secrets gate, against a make-believe `secrets.h` |

### 30 Sep 2026, morning: proven on the transmitter

| Test | Result |
|---|---|
| Teensy B8 from the Mac (`teensy_ota.py install`) | 89 s: 145 files copied and read back (models.dat "read back from both cards"), B8 on trial, accepted; "the settings could not be compared: B7 did not say" (as expected) |
| **The same B8 installed again** | "reads the model's settings exactly as 2.5.6 B8 did (1.16890A8B)": the fingerprint does not change by itself |
| **The safety switch, on the Transmitter setup page** | safety off: `tx=42`, "Safety off: WiFi and Bluetooth OFF" within a second; safety on: "WiFi back ON" 7 s later (GET /radiolog) |
| `restore` of a copy that is the same | every file "already the same", nothing written, the transmitter did NOT restart |
| **Release 2.5.6 B8 + screen 1.2.0 published** | 284 files read back from messiter.com; three releases can be gone back to |
| **Install by the button** (screen only: the Teensy had B8) | 77 s from Install now to green; screen 1.2.0, the door still open on House (opened from the Mac beforehand) |
| **Earlier versions** > B7 + 1.1.1 > Install now (driven from the Mac) | 2 min 15 s: 146 files copied first, B7 through its trial, screen 1.1.1; green |
| Forward again from 1.1.1 (the OLD updater) to B8 + 1.2.0 | 2 min: green; the fingerprint the same as before the round trip |

| **The phone's hotspot** (its real name has "Max" at the end; the seeded name had not) | learned on the WiFi page, joined; *Check for update* over the phone: *Up to date*; back on House when the hotspot went |
| A receiver switched on, then *Check for update* | *A model is connected: switch the model off, then check again* |
| **Release 2.5.6 B10 + screen 1.2.1 published**, installed by the button | 2 min 11 s; the green panel photographed for 50 s: nothing drew over it; "reads your model's settings exactly as the old one did" |

**Open: the transmitter switched itself off twice while idle** (between 07:35 and 07:50, and between 08:05 and 08:40),
long before its 60-minute inactivity time; 25 minutes idle measured afterwards without a switch-off. Since B9 every way
out writes why to the EEPROM, and the hello says it (`off=`, `rst=`): the next time, `dev/teensy_ota.py hello` first.

Still to be tried: a real `restore` (the transmitter restarts by itself); the door shut on another network.

Not yet done: a restore button on the screen.
