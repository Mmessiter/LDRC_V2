#!/bin/zsh
# Upload one directory of screenshots into an App Store Connect screenshot set.
#   upload_screenshots.sh <set-id> <dir>
# Apple's three-step dance: reserve (POST, returns uploadOperations) → PUT the
# bytes → PATCH uploaded=true with the md5. Done in order so the numbering in
# the listing matches the file names.
set -e
SETID=$1; DIR=$2
HERE=$(cd "$(dirname $0)" && pwd)
ASC="$HERE/../../../../private/tmp"        # unused; asc helper passed via $ASC_SH
for f in $DIR/*.png(n); do
  NAME=$(basename $f); SIZE=$(stat -f%z $f)
  RES=$($ASC_SH POST /v1/appScreenshots /dev/stdin <<JSON
{"data":{"type":"appScreenshots","attributes":{"fileName":"$NAME","fileSize":$SIZE},
"relationships":{"appScreenshotSet":{"data":{"type":"appScreenshotSets","id":"$SETID"}}}}}
JSON
)
  ID=$(print -r -- "$RES" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['id'] if 'data' in d else 'ERR')")
  if [[ "$ID" == "ERR" ]]; then print -r -- "$RES" | head -c 400; echo; exit 1; fi
  # one PUT per upload operation (Apple may chunk large files)
  print -r -- "$RES" | python3 -c "
import json,sys,subprocess
ops=json.load(sys.stdin)['data']['attributes']['uploadOperations']
path='$f'
data=open(path,'rb').read()
for o in ops:
    cmd=['curl','-s','-X',o['method'],o['url']]
    for h in o.get('requestHeaders',[]): cmd += ['-H', h['name']+': '+h['value']]
    chunk=data[o['offset']:o['offset']+o['length']]
    cmd += ['--data-binary','@-']
    subprocess.run(cmd, input=chunk, check=True)
"
  MD5=$(md5 -q $f)
  $ASC_SH PATCH /v1/appScreenshots/$ID /dev/stdin > /dev/null <<JSON
{"data":{"type":"appScreenshots","id":"$ID","attributes":{"uploaded":true,"sourceFileChecksum":"$MD5"}}}
JSON
  echo "  uploaded $NAME"
done
