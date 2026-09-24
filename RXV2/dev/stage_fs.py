"""
PlatformIO PRE script (0.9.844): build the LittleFS image from a STAGED copy of
data/ in which every text asset over 2 kB (html, js, css, svg, json, txt) is
gzipped. The receiver serves a ".gz" twin transparently (serveLittleFsFile,
Content-Encoding: gzip), so nothing else changes - but the image shrinks ~4x
and the "filesystem full" stops at every new page ends (three times on
2026-09-24 alone). data/ itself stays plain: the apps bundle it as-is and every
dev test reads it. Wired into platformio.ini via:
    extra_scripts =
        pre:dev/stage_fs.py
        post:dev/archive_firmware.py
dev/check_fs_image.py compares the image with .pio/fsdata (this staging).
"""
import gzip, shutil
from pathlib import Path
Import("env")  # type: ignore  # injected by PlatformIO

PROJECT_DIR = Path(env.subst("$PROJECT_DIR"))  # type: ignore
DATA  = PROJECT_DIR / "data"
STAGE = PROJECT_DIR / ".pio" / "fsdata"
GZ_TYPES = {".html", ".js", ".css", ".svg", ".json", ".txt"}
MIN_GZ_BYTES = 2048

def stage():
    STAGE.mkdir(parents=True, exist_ok=True)
    for old in STAGE.iterdir():
        if old.is_file(): old.unlink()
    for f in sorted(DATA.iterdir()):
        if not f.is_file() or f.name.startswith("."): continue
        already_gz = f.suffix == ".gz" or (DATA / (f.name + ".gz")).exists()
        if f.suffix in GZ_TYPES and f.stat().st_size >= MIN_GZ_BYTES and not already_gz:
            with open(f, "rb") as i, gzip.GzipFile(STAGE / (f.name + ".gz"), "wb", compresslevel=9, mtime=0) as o:
                shutil.copyfileobj(i, o)
        else:
            shutil.copy2(f, STAGE / f.name)

stage()
env.Replace(PROJECT_DATA_DIR=str(STAGE))  # type: ignore
print("stage_fs: LittleFS image built from %s (text assets gzipped)" % STAGE)
