#!/bin/zsh
# How many people have the apps? Counts from the web host's own access logs
# (which it keeps anyway) plus TestFlight - NOTHING is added to the app, which
# promises no analytics. Excludes this house, the fleet watcher's fetches and
# known crawlers. Run: dev/downloads.sh [Mon-YYYY]   (default: this month)
set -e
MON=${1:-$(date +%b-%Y)}
M=$HOME/.claude/projects/-Users-malcolmmessiter-Documents-GitHub/memory/messiter-com-ftp-credentials.md
FTPHOST=$(grep -iE "^- \*\*(host|server)" $M | sed -E 's/.*`([^`]+)`.*/\1/')
FTPUSER=$(grep -iE "^- \*\*(user|login)" $M | sed -E 's/.*`([^`]+)`.*/\1/')
export LFTP_PASSWORD=$(grep -iE "^- \*\*pass" $M | sed -E 's/.*`([^`]+)`.*/\1/')
D=$(mktemp -d)
lftp --env-password -u "$FTPUSER" "$FTPHOST" >/dev/null 2>&1 <<EOF
set ssl:verify-certificate no
lcd $D
cd /logs
get messiter.com-ssl_log-$MON.gz
bye
EOF
[[ -s $D/messiter.com-ssl_log-$MON.gz ]] || { echo "no log for $MON on the host"; exit 1; }
ME=$(curl -s -m 5 https://api.ipify.org || echo none)
python3 - "$D/messiter.com-ssl_log-$MON.gz" "$ME" "$MON" <<'PY'
import gzip, re, sys, collections
f, me, mon = sys.argv[1:4]
pat = re.compile(r'^(\S+) \S+ \S+ \[(\d+)/\w+/\d+:[^\]]+\] "(\w+) (\S+)[^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
bots = re.compile(r'bot|crawl|spider|slurp|facebookexternalhit|preview|curl|python|wget|Go-http|HeadlessChrome|iPhone OS 13_2_3', re.I)
apk = collections.defaultdict(set); appchk = collections.defaultdict(set); rxchk = collections.defaultdict(set); flash = collections.defaultdict(set); fwdl = 0
with gzip.open(f, 'rt', errors='replace') as fh:
    for line in fh:
        m = pat.match(line)
        if not m: continue
        ip, day, meth, path, status, ua = m.groups()
        if status not in ('200', '206') or ip == me or bots.search(ua): continue
        p = path.split('?')[0]
        if p.endswith('/rxv2app/release/RXV2App.apk'):
            (apk[ip]).add(day)
        elif p == '/rxv2app/release/manifest.json': appchk[ip].add(day)
        elif p == '/rxv2/release/manifest.json':    rxchk[ip].add(day)
        elif p == '/rotorflight/flash.html':         flash[ip].add(day)
        elif p.endswith('/release/latest/firmware.bin'): fwdl += 1
print(f"{mon} - people other than this house (crawlers removed)")
print(f"  Android app downloaded ........ {len(apk):3d} addresses")
print(f"  Android app in use (checks in)  {len(appchk):3d} addresses")
print(f"  receivers/dongles checking in . {len(rxchk):3d} addresses")
print(f"  browser flasher page opened ... {len(flash):3d} addresses, {fwdl} firmware downloads")
print("  (an address = one home or one phone's network; the same person may appear twice)")
PY
rm -rf $D
SC=/private/tmp/claude-501/-Users-malcolmmessiter-Documents-GitHub/af1a6665-682d-4617-8932-51125e50dc5a/scratchpad
echo "TestFlight"
python3 "$HOME/Documents/GitHub/LDRC_V2_ALL/RXV2App/appstore/asc_token.py" KLS4GZ93JB 69a6de80-5be5-47e3-e053-5b8c7c11a4d1 > $D.tok 2>/dev/null || true
T=$(cat $D.tok 2>/dev/null); rm -f $D.tok
[[ -n "$T" ]] && curl -s -H "Authorization: Bearer $T" "https://api.appstoreconnect.apple.com/v1/betaGroups/1ae46cad-5df4-4227-a333-a49087a1e4f1/betaTesters?limit=200" | python3 -c "
import json,sys
t=json.load(sys.stdin).get('data',[])
inst=sum(1 for x in t if x['attributes'].get('state')=='INSTALLED')
print(f'  testers on the link ........... {len(t):3d}   installed: {inst}')"
