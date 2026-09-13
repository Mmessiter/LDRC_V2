#!/usr/bin/env bash
# Publish the staged LDRC2SIM OTA area to messiter.com (Krystal hosting).
#
# Mirrors ONLY  NewWebSite/public_html/ldrc2sim/  ->  <site>/public_html/ldrc2sim/
# i.e. https://messiter.com/ldrc2sim/release/...  — the same FTP mechanism the
# RXV2 and ReedsV2 projects use for their OTA areas. Nothing outside ldrc2sim/
# is touched (no --delete, so old release versions are preserved for rollback).
#
# Run dev/stage_website.py first to (re)build the staging tree + manifest.
#
# Credentials: the shared messiter.com FTP login. The password is NOT stored in
# this tracked script — it is read from $LFTP_PASSWORD, or from a gitignored
# dev/ftp_credentials.sh (which this script sources if present).
#
# Usage:
#   dev/publish_website.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
LOCAL_DIR="$ROOT/NewWebSite/public_html"
PRODUCT="ldrc2sim"

HOST="${LDRC_FTP_HOST:?set LDRC_FTP_HOST (see dev/ftp_credentials.sh)}"
USER_NAME="${LDRC_FTP_USER:?set LDRC_FTP_USER (see dev/ftp_credentials.sh)}"

# Load creds from the gitignored file if the env var isn't already set.
if [[ -z "${LFTP_PASSWORD:-}" && -f "$HERE/ftp_credentials.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HERE/ftp_credentials.sh"
fi
if [[ -z "${LFTP_PASSWORD:-}" ]]; then
  echo "LFTP_PASSWORD is not set and dev/ftp_credentials.sh is missing." >&2
  echo "Export LFTP_PASSWORD, or create dev/ftp_credentials.sh (gitignored)." >&2
  exit 1
fi
if ! command -v lftp >/dev/null 2>&1; then
  echo "lftp not found. Install it (brew install lftp)." >&2
  exit 1
fi
if [[ ! -d "$LOCAL_DIR/$PRODUCT" ]]; then
  echo "Staging tree '$LOCAL_DIR/$PRODUCT' not found." >&2
  echo "Run dev/stage_website.py first." >&2
  exit 1
fi

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
