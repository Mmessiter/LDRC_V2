# LDRC2SIM public release mirror (messiter.com)

This directory is the FTP-upload staging area for the public LDRC2SIM firmware
mirror at `https://messiter.com/ldrc2sim/release/`. The device's
`/api/firmware/check` endpoint fetches `manifest.json` here in addition to the
local dev server (`dev/firmware_server.py`), so any dongle with internet access
can install official releases without the dev Mac being on the LAN. Same
mechanism the sibling **RXV2** and **ReedsV2** projects use.

## Layout

```
public_html/
└── ldrc2sim/
    └── release/
        ├── manifest.json          # version list — newest entries first
        └── v1.0.11/
            └── firmware.bin       # the .bin matching the entry's `name`
```

Each version entry in `manifest.json` is:
```json
{
  "name":  "LDRC2SIM-1.0.11",                                   // matches FW_VERSION
  "url":   "https://messiter.com/ldrc2sim/release/v1.0.11/firmware.bin",
  "size":  1008080,                                             // informational
  "mtime": 1780831838,                                          // informational
  "notes": "Optional short change summary."
}
```

The device reads only `name` (parsed as `LDRC2SIM-(\d+)\.(\d+)\.(\d+)` to tag each
entry newer / current / older than what's running) and `url` (used as-is when
absolute, else resolved against the manifest's location). `size` / `mtime` /
`notes` are for humans and the website. Keep the manifest small — the device
loads the whole thing into RAM on each check.

## Release workflow

Both steps are scripted (run from the project root, one dir up from here):

1. Build the firmware (bump `FW_VERSION` in `src/web_portal.cpp` first):
   `pio run -e seeed_xiao_esp32s3`, then copy the new
   `.pio/build/seeed_xiao_esp32s3/firmware.bin` to `dev/LDRC2SIM-x.y.z.bin`.
2. `python3 dev/stage_website.py` — copies every `dev/LDRC2SIM-*.bin` into
   `public_html/ldrc2sim/release/vX.Y.Z/firmware.bin` and regenerates
   `manifest.json` (newest first; notes from `dev/release_notes.json`).
3. `dev/publish_website.sh` — FTP-mirrors `public_html/ldrc2sim/` to messiter.com.
   Credentials come from `dev/ftp_credentials.sh` (gitignored) or `$LFTP_PASSWORD`.

The dongle picks the new release up on the next visit to its **Firmware** page —
no separate "publish" step on the device.
