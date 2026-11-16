# Printed parts for an ELRS module

For a transmitter that carries an ExpressLRS (ELRS) module inside its case. These parts are made for Malcolm's module, a **RadioMaster Ranger Nano**. ELRS is being tested now: it is not in the released firmware yet.

First make the small change to the main board: [Optional: ready for an ELRS module](https://messiter.com/ldrc/build.html#tx-elrs).

<img src="elrs-case-parts.png" width="800" alt="The new case back seen from behind in two views, drawn from the design files: the module and charger bay glued into its longer, higher opening; the module in its pocket under two straps, its aerial going up through the taller handle; the charger's USB-C lead plugged in from the right.">

<sub>The new back with the module and charger bay and the taller handle. Drawn from the design files.</sub>

| File | What it is |
|---|---|
| `BACK_ELRS_HIGH.step` / `.stl` | **The case back.** Print it instead of `TXV12a_BACK_V2.step`: only its opening differs, longer and higher. The module's aerial goes up through the handle, and its tip stands above the top of the transmitter. |
| `ELRS_CHARGER_BAY.step` | **The module and charger bay**, for editing. |
| `ELRS_CHARGER_BAY_PRINT.stl` | The same bay lying as it prints: flange down, supports off. A loose prop holds up the charger's two risers while they print: snap it out afterwards. |
| `TX_HANDLE_TALL.step` / `.stl` | **A taller handle:** its legs are 10 mm longer, so your fingers pass above the aerial. It fits the same two pockets in the back. Turn it for printing as you would the standard handle. |
| `PIN_STRIP_JIG.step` | **The jig** that holds the pin strip while its glue sets, for editing. |
| `PIN_STRIP_JIG_PRINT.stl` | The jig lying as it prints: on its side, supports off. About 8 g. |

Print in PETG or PLA, like the rest of the case. Most slicers open STEP files directly.

## The module and charger bay

- It is one part, glued into the back from the inside with five-minute epoxy, like the Version 2 charger bay.
- At the bottom, the USB-C charger board sits on the same two risers as in `CHARGERBAY.stl`. Its lead plugs in from the right (seen from behind), so the transmitter still stands up while it charges. The red charge light goes in the hole in the face.
- Above it is a pocket for the module. The module slides in from the top, under two straps, onto a strip of pins. One tiny self-tapping screw each side (6 mm or longer) stops it sliding out. A strip of felt or foam tape under each strap stops any rattle.
- **The pins:** an 8-way 2.54 mm **turned-pin** strip (round pins, about 0.5 mm: the module's sockets do not take square DuPont pins). It lies in a little comb, its fat brass collars against the comb and its long thin pins pointing up, towards the module. The wires go through the window behind it.
- Only three pins are wired. The module's sockets 1, 2 and 3 are SIGNAL, GROUND and BATTERY: from the left, looking at the module's back with its aerial up. Check yours before you glue. The module's own XT30 power socket then stays empty.
- The module needs a power switch for now: see the build guide's [Power for the module](https://messiter.com/ldrc/build.html#tx-elrs).

## The jig

Holding the pin strip still while its glue sets is very hard by hand. The jig holds it for you. Malcolm's way, from experience:

1. Put the strip in the comb, its fat brass collars against the comb and its long thin pins pointing up. The wires go through the window.
2. Put sticky tape over the window at the back, so that glue cannot run through it.
3. Rub a little candle wax or grease on the jig's nose, so that the glue cannot hold it.
4. Slide the jig in from the top end, like the module, until it stops. The pins lie in its slots and touch nothing.
5. Very carefully, put one drop of thin superglue where the strip meets the comb. It runs: keep it well away from the pins.
6. When the superglue has set, press the tab and slide the jig out.
7. Then reinforce the joint with a generous amount of five-minute epoxy, over the comb and the wires. Be extremely careful not to get any on the pins or their connections.

A spring tab goes under the upper strap. The strap presses on its slope, and that holds the strip down on its pad and back against the comb. Never glue the strip with the module in place: glue must not reach the module.

<img src="elrs-pin-strip-jig.png" width="600" alt="The pin strip jig: a cut through one pin shows the jig holding the strip down and back against the comb, the pins lying in its slots, and its spring tab under the upper strap; below, the jig in place in the bay, and lying on its side as it prints.">

<sub>The jig: how it holds the strip, in place in the bay, and how it prints.</sub>

Check the repository before printing: a newer version may follow.

How to build the whole transmitter: https://messiter.com/ldrc/build.html
