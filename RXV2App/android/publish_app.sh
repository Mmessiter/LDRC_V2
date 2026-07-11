#!/usr/bin/env bash
# Publish the Android RXV2App to messiter.com so installed copies can
# self-update (the app checks rxv2app/release/manifest.json on launch and
# offers any newer versionCode with one tap).
#
#   ./publish_app.sh "release notes"
#
# Builds app-debug.apk (all phones so far run debug-signed installs — Android
# only updates over a matching signature, so we keep publishing debug), stages
#     site/rxv2app/release/RXV2App.apk        (stable URL — banner always points here)
#     site/rxv2app/release/RXV2App-<ver>.apk  (archive copy for rollback)
#     site/rxv2app/release/manifest.json
# and mirrors site/rxv2app -> public_html/rxv2app (no --delete; old APKs kept).
#
# Remember to bump versionCode + versionName in app/build.gradle.kts first.
# Credentials: $LFTP_PASSWORD, or ~/.config/messiter_ftp.sh, or the RXV2 repo's
# gitignored dev/ftp_credentials.sh. Same Krystal login as the other products.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HERE/RXV2App"
NOTES="${1:-}"
HOST="s96.lon.krystal.io"
USER_NAME="messiter"

VCODE=$(sed -n 's/^[[:space:]]*versionCode = \([0-9][0-9]*\).*/\1/p' "$APP/app/build.gradle.kts")
VNAME=$(sed -n 's/^[[:space:]]*versionName = "\([^"]*\)".*/\1/p' "$APP/app/build.gradle.kts")
[[ -n "$VCODE" && -n "$VNAME" ]] || { echo "Could not read versionCode/versionName from build.gradle.kts" >&2; exit 1; }

# Keep every copy of the shared assets in lockstep BEFORE building:
# the web pages (master: RXV2/data) and the demo shim (master:
# RXV2App/demo) are bundled into BOTH apps — a fix must never ship in
# one and get left behind in another.
ROOT="$(dirname "$(dirname "$HERE")")"
rm -rf "$APP/app/src/main/assets/webroot" "$(dirname "$HERE")/webroot"
cp -R "$ROOT/RXV2/data" "$APP/app/src/main/assets/webroot"
cp -R "$ROOT/RXV2/data" "$(dirname "$HERE")/webroot"
mkdir -p "$APP/app/src/main/assets/demo" "$(dirname "$HERE")/demo"
cp "$(dirname "$HERE")/demo/"* "$APP/app/src/main/assets/demo/"
echo "── Synced webroot + demo from masters (android + ios)"

JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}" \
    "$APP/gradlew" -p "$APP" assembleDebug -q
APK="$APP/app/build/outputs/apk/debug/app-debug.apk"
[[ -f "$APK" ]] || { echo "APK not found: $APK" >&2; exit 1; }

REL="$HERE/site/rxv2app/release"
mkdir -p "$REL"
cp "$APK" "$REL/RXV2App.apk"
cp "$APK" "$REL/RXV2App-$VNAME.apk"
python3 - "$REL/manifest.json" "$VCODE" "$VNAME" "$NOTES" <<'EOF'
import json, sys
path, vcode, vname, notes = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
json.dump({
    "versionCode": vcode,
    "versionName": vname,
    "url": "https://www.messiter.com/rxv2app/release/RXV2App.apk",
    "notes": notes,
}, open(path, "w"), indent=1)
EOF

if [[ -z "${LFTP_PASSWORD:-}" ]]; then
  for f in "$HOME/.config/messiter_ftp.sh" "$HERE/../../RXV2/dev/ftp_credentials.sh"; do
    # shellcheck disable=SC1090
    if [[ -f "$f" ]]; then source "$f"; fi
    # ~/.config/messiter_ftp.sh exports MESSITER_FTP_*; the repo file exports LFTP_PASSWORD
    LFTP_PASSWORD="${LFTP_PASSWORD:-${MESSITER_FTP_PASSWORD:-}}"
    [[ -n "${LFTP_PASSWORD:-}" ]] && break
  done
  export LFTP_PASSWORD
fi
[[ -n "${LFTP_PASSWORD:-}" ]] || { echo "LFTP_PASSWORD not set and no credentials file found." >&2; exit 1; }
command -v lftp >/dev/null 2>&1 || { echo "lftp not found (brew install lftp)." >&2; exit 1; }

echo "Publishing RXV2App v$VNAME (versionCode $VCODE) -> $HOST:public_html/rxv2app"
cd "$HERE/site"
lftp --env-password -u "$USER_NAME" "$HOST" <<EOF
set ftp:ssl-allow yes
set ssl:verify-certificate no
set net:max-retries 3
cd public_html
mirror -R --verbose --parallel=2 rxv2app rxv2app
quit
EOF
echo
echo "Done. Live manifest: https://www.messiter.com/rxv2app/release/manifest.json"
