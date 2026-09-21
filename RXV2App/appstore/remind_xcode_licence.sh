#!/bin/zsh
# Morning reminder: the Xcode licence still needs accepting (it needs sudo, so
# only Malcolm can do it). Pings once, then gets out of the way for good once
# the licence is accepted - so it never nags about something already done.
NOTIFY=/Users/malcolmmessiter/Documents/GitHub/LDRC_V2_ALL/RXV2/dev/notify.sh
PLIST=$HOME/Library/LaunchAgents/com.messiter.xcodelicence.plist

# /usr/bin/git is one of the shims the licence gates, so it is the test.
if /usr/bin/git --version >/dev/null 2>&1; then
    [[ -f $PLIST ]] && launchctl unload $PLIST 2>/dev/null && rm -f $PLIST
    exit 0
fi

[[ -f $NOTIFY ]] && bash $NOTIFY "Morning! One thing needs your password: type  ! sudo xcodebuild -license accept  in Claude Code. Xcode updated overnight and blocks building until you do. Nothing else is waiting on it."
exit 0
