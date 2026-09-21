#!/bin/zsh
# Copy the review watchers to /Users/Shared, where a LaunchAgent can actually
# read them. ~/Documents is TCC-protected; launchd gets "can't open input file".
set -e
D=/Users/Shared/ldrc-watch
R=$(cd "$(dirname $0)/../.." && pwd)
mkdir -p $D
cp $R/RXV2App/appstore/{asc_token.py,watch_review.sh,remind_xcode_licence.sh} $D/
cp $R/RXV2/dev/notify.sh $D/notify.sh
sed -i '' "s|APP=$R/RXV2App|APP=$D|" $D/watch_review.sh
sed -i '' 's|"$APP/appstore/asc_token.py"|"$APP/asc_token.py"|' $D/watch_review.sh
sed -i '' "s|^NOTIFY=.*|NOTIFY=$D/notify.sh|" $D/watch_review.sh $D/remind_xcode_licence.sh
chmod +x $D/*.sh
echo "synced to $D"
