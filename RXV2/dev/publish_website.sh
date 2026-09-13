#!/usr/bin/env bash
# Publish the staged RXV2 OTA area to messiter.com (Krystal hosting).
#
# Mirrors ONLY  NewWebSite/public_html/rxv2/  ->  <site>/public_html/rxv2/
# i.e. https://messiter.com/rxv2/release/...  — same mechanism as LDRC2SIM / ReedsV2.
# No --delete, so old release versions are preserved for rollback.
#
# Run dev/stage_website.py first. Credentials: $LFTP_PASSWORD, or the gitignored
# dev/ftp_credentials.sh (sourced if present). Shared messiter.com FTP login.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
LOCAL_DIR="$ROOT/NewWebSite/public_html"
PRODUCT="rxv2"
HOST="${LDRC_FTP_HOST:?set LDRC_FTP_HOST (see dev/ftp_credentials.sh)}"
USER_NAME="${LDRC_FTP_USER:?set LDRC_FTP_USER (see dev/ftp_credentials.sh)}"

if [[ -z "${LFTP_PASSWORD:-}" && -f "$HERE/ftp_credentials.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HERE/ftp_credentials.sh"
fi
if [[ -z "${LFTP_PASSWORD:-}" ]]; then
  echo "LFTP_PASSWORD not set and dev/ftp_credentials.sh missing." >&2
  exit 1
fi
command -v lftp >/dev/null 2>&1 || { echo "lftp not found (brew install lftp)." >&2; exit 1; }
[[ -d "$LOCAL_DIR/$PRODUCT" ]] || { echo "Staging tree missing — run dev/stage_website.py first." >&2; exit 1; }

echo "Mirroring $LOCAL_DIR/$PRODUCT  ->  $HOST:public_html/$PRODUCT"
cd "$LOCAL_DIR"
lftp --env-password -u "$USER_NAME" "$HOST" <<EOF
set ftp:ssl-allow yes
set ssl:verify-certificate no
set net:max-retries 3
cd public_html
mirror -R --verbose --parallel=2 $PRODUCT $PRODUCT
quit
EOF
echo
echo "Done. Live manifest: https://messiter.com/$PRODUCT/release/manifest.json"
