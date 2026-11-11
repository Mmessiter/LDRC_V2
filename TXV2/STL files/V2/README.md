# The Version 2 transmitter case

The case as refined by 24 October 2026. Print it in PETG or PLA. Check the repository before printing: a newer version may follow.

There are two fronts, because the two screens the firmware supports differ slightly in size. Print the one for your screen.

| File | What it is |
|---|---|
| `TXV12_FRONT_16m_V2.step` | The front for the **16 MB screen** (Elecrow's 5-inch IPS panel, SKU DLE06050B): the one to use for a new transmitter. |
| `TXV12a_Front_4meg_V2.step` | The front for the **4 MB screen** (the CrowPanel 5.0, SKU DIS07050H): for the transmitters that already have one (the 4 MB screen gets fixes only, no new features). |
| `TXV12a_BACK_V2.step` | The back. The bay where Version 1's JR module went now takes the charger. |
| `CHARGERBAY.stl` | The charger bay: holds the small USB-C 2S charger module (IP2326) on the back, with a window for its charge light. Tighten the board's two screws with a USB-C plug in its socket; fit the light after the bay is in the back; then fix the bay with five-minute epoxy from the inside. |

Both fronts hold the screen, the gimbals, the switches and the trims; the screen has no mounting holes, the front holds it.

Most slicers (PrusaSlicer, Bambu Studio, OrcaSlicer, Cura with its STEP plugin) open STEP files directly.
The other parts (handle, supports, gimbal protector, antenna parts) are the Version 1 parts in the folders above.

How to build the whole transmitter: https://messiter.com/ldrc/build.html
