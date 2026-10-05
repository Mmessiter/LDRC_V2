# TX_NEXTION.HMI — file format as reverse-engineered (2026-09-28)

Source: `LockDownRadioControl/Nextion files/TX_NEXTION.HMI` (58 813 519 bytes, Nextion Editor,
Intelligent series). Re-run the extractor with

    python3 extract_hmi.py "<path to TX_NEXTION.HMI>" [output dir]

It writes `pages.json`, `fonts.json`, `resources.json`, `pictures/<id>.png`, `audio/<id>.wav`.
Nothing is compressed or encrypted; every number is little-endian.

**Display is 800 × 480** (page `w`/`h`, all background PNGs are 800×480) — not 480×320.
Components with negative `y` or `x`/`y` beyond 800/480 are deliberately parked off-screen
(FrontView `fm1..fm4`, RFGovViewGlbl `t51…n27`, GraphView `b0`, DataView `b2`).

## 1. Container (offset 0)

| offset | size | meaning |
|---|---|---|
| 0 | u32 | number of directory entries (445 here) |
| 4 | 28 × N | directory entries |
| 0x700000 | … | member data (all members live at `offset`, first one at 0x700000) |

Directory entry (28 bytes): `char name[16]` (NUL padded) · `u32 offset` · `u32 size` ·
`u8 deleted_flag` (1 = deleted; the name's first byte is also zeroed) · 3 bytes (timestamp-ish, ignored).
186 of the 445 entries are deleted leftovers; 259 are live. Member kinds:

| member | what |
|---|---|
| `main.HMI` | resource-id tables (see §2) |
| `Program.s` | the editor's Program.s text (global `int` declarations + `page 0`) |
| `NN.pa` | one page each (58) |
| `NN.zi` | Nextion font (7) |
| `NN.is` | picture *source*: 27-byte header + the original PNG (this is what `pictures/` holds) |
| `NN.i` | the same picture converted to Nextion's internal format (24-byte header, undocumented RLE; not decoded — not needed because every `.i` has its `.is`) |
| `NN.wav` | audio (RIFF WAV, 104 live) |

The numbers in member names are *internal* — they are **not** the picture/font/page ids.

## 2. `main.HMI` — id tables

Header 0x60 bytes: `u32 @0x18` = table offset (0x60), `u32 @0x1c` = entry count (213).
Then 16-byte entries: `char ext[8]` (`"i"`, `"zi"`, `"wav"`, `"pa"`; byte 7 is a flag) + `char member[8]`.
Entries of one kind are listed in id order, so **picture id N = Nth `i` entry**, **font id N = Nth `zi`
entry**, **audio id N = Nth `wav` entry**, **page id N = Nth `pa` entry** (0 = BlankView …
57 = keybdB, matching the order in the task brief).

## 3. `NN.pa` — page file

| offset | size | meaning |
|---|---|---|
| 0 | u32 | checksum (not verified) |
| 4 | u32 | file size |
| 8 | u32 | 0x38, fixed header size |
| 0x0c | u32 | object count (page object + components) |
| 0x10 | u32 | 0 |
| 0x14 | u32 | 0x00214f00 in every page (editor/device version word) |
| 0x18 | char[16] | page name |
| 0x28 | u32 | 0x00010144 in every page (editor build?) |
| 0x2c | 12 bytes | zero |
| 0x38 | 12 × count | object table: `u32 offset_from_0x38`, `u32 size`, `u32 0` |
| 0x38 + 12×count | … | objects, in id order; object 0 is the page itself |

Object:

    u32 len, "att-N"                         N = number of attribute records
    N × { u32 len, char name[16], value[len-16] }
    0..k × { u32 len, "codes<event>-<L>", L × { u32 len, char text[len] } }   one record per code line
    u32 0                                    end of object

Value width tells the type: 1 byte (u8: type, id, vscope, sta, style, font, xcen, ycen, borderw,
key, pw, isbr, spax, spay, dez, dis, mode, wid, hig, ch, dir, en …), 2 bytes (u16: w, h, colours,
pic ids (0xffff = none), txt_maxl, maxval, minval, time; **int16 for x, y, movex, movey, endx, endy**),
4 bytes (int32: val of number/variable/textselect, groupid0/1, tim, qty, stim, molloc),
variable (string: objname, txt, path). Colours are RGB565.

`type` byte → component kind (Intelligent series):
121 page · 116 text · 54 number · 98 button · 53 dual-state button · 112 picture · 106 progress bar ·
1 slider · 109 hotspot · 51 timer · 52 variable · 56 checkbox · 57 radio · 4 audio · 60 external
picture (`exp0`, `path` = SD file) · 61 combobox (`path` = options, `txt` = prompt) · 62 scrollable
text box (`LogText`: `val_y`/`maxval_y`) · 67 switch (`txt` = "off/on" labels) · 68 textselect list
box (`path` = "\r\n"-separated rows, `hig` = row height, `val` = selected row).
The first five and 106/1/109/51/52/56/57 match the Nextion documentation; 4/60/61/62/67/68/112 are
inferred from the attribute sets and the firmware's use of them (`LogText.val_y`, `FilesBox`, …).

Event keys: `load` = Preinitialize, `loadend` = Postinitialize, `down` = Touch Press,
`up` = Touch Release, `unload` = page exit, `slide` = slider move, `timer`, `playend` (audio).

`sta` on the page object: 0 = no background (overlay: PopupView, keybdB, PickBankView1/2,
FileExchView, BackupView keep the previous page underneath), 1 = solid `bco`, 2 = picture `pic`.
On components: 0 crop image (`picc`), 1 solid `bco`, 2 image `pic`, 3 none/transparent.
There is **no visibility attribute** in the file; `vis` is a runtime command (FrontView's
Preinitialize hides Warning/wb/rpm/… itself), so every component is emitted `visible: true`.
Attributes `drag sendkey aph movex movey endx endy effect first time lockobj groupid0 groupid1`
are editor/animation settings and are dropped from `pages.json`.

## 4. `NN.zi` — font

`u8 @7` = pixel height · `u8 @0x0a/@0x0b` = first/last char code · `u32 @0x0c` = glyph count ·
`u8 @0x11` = name length · `u32 @0x14` = glyph-data size · `u32 @0x18` = name offset (0x2c) ·
name e.g. `Arial32Biso-8859-1` (= Arial, 32 px, **B**old, ISO-8859-1) or `24asciiascii`
(built-in bitmap font). Glyph bitmaps follow the name (format not decoded).

## 5. `NN.is` — picture source

`u32 @8` = header length (27) · `u16 @12` width · `u16 @14` height · `u32 @16` payload size ·
`char[3] @24` format tag (`png` for all 44 here) · original file from offset 27.
`pictures/<id>.png` is that payload; `resources.json` maps id → member, size, format.
Picture 3 is the default FrontView background (`FrontView.pic=Screen_Background`, `int Screen_Background=1`
in Program.s selects picture 1 at run time; BackGroundView lets the user pick another).

## 6. Outputs

- `pages.json`: `{display, program_s, pages:[{name,id,member,w,h,background,events,page_attrs,components:[…]}]}`.
  Component: `name id type type_code scope x y w h colours{bco,pco,bco2,pco2,…:{rgb565,hex}} font txt val
  pictures{pic,picc,pic2,…} sta sta_name attrs{…} options[] visible events{touch_press,touch_release,…}`.
- `fonts.json`: font id → name, height, char range, glyph count.
- `resources.json`: raw directory, id tables, picture and audio maps.

Totals: 58 pages, 1663 components (758 text, 329 button, 245 number, 104 variable, 67 progress bar,
52 switch, 32 checkbox, 18 radio, 16 audio, 12 slider, 10 textselect, 6 timer, 4 external picture,
4 dual-state button, 3 combobox, 1 picture, 1 sltext, 1 hotspot), 7 fonts, 44 pictures, 104 wavs.
