# Getting LDRC RX V2 onto the App Store

Checked on the machine 2026-09-20, against build 5.148 (441).

## Ready — verified, not assumed

| | |
|---|---|
| Distribution certificate | **Apple Distribution: Malcolm Messiter (ANLD6T79T5)**, cloud-managed, expires 10 Jul 2027 |
| Archive + export | `RXV2App.ipa` built and signed for `app-store-connect`, `get-task-allow=false`, `beta-reports-active=true` |
| Encryption declaration | `ITSAppUsesNonExemptEncryption: false` — no "export compliance" question at upload |
| Privacy manifest | `PrivacyInfo.xcprivacy` in the bundle |
| App icon | 1024 in the asset catalog, compiled into `Assets.car` |
| Bluetooth strings | `NSBluetoothAlwaysUsageDescription` present |
| Support / privacy / marketing URLs | all three live on messiter.com (200) |
| GPL vs the App Store | handled — `LICENSE-EXCEPTION.txt` + `LICENSING.md`, explained on `messiter.com/rxv2/source.html` |
| Screenshots | re-shot 2026-09-20 for the four-door front door, iPhone 6.9" and iPad 13" |
| Review notes | rewritten for the four-door front door — the old ones sent the reviewer to buttons that no longer exist |

RF24 is GPL-2.0-only and must eventually be replaced — but it is **firmware only**.
It is not in the iOS app and does not block this submission.

## Three things only you can do

1. **App Store Connect API key** — App Store Connect → Users and Access →
   Integrations → App Store Connect API → **+**, role **App Manager**.
   Download the `.p8` ONCE (Apple never shows it again) and put it at
   `~/.appstoreconnect/private_keys/AuthKey_<KEYID>.p8`.
   Tell me the Key ID and Issuer ID and every upload after that is one command.

2. **Create the app record** — App Store Connect → Apps → **+** → New App.
   Platform iOS · Name `LDRC RX V2` · Primary language English (UK) ·
   Bundle ID `com.messiter.rxv2app` · SKU `ldrc-rxv2` · Full access.
   (With the API key I can do this instead.)

3. **Agreements** — Business → the free-apps agreement must show **Active**,
   or the app cannot be sold, even for nothing.

## The answers to the forms

**Privacy (App Privacy → "Data Collection")** — answer **No, we do not collect
data from this app**. True: no accounts, no analytics, no SDKs, no network
calls except firmware downloads from messiter.com. "Send debug data to Malcolm"
hands a file to the system share sheet; the user chooses where it goes and the
app transmits nothing by itself.

**Age rating** — everything **None**. Rates 4+.

**Category** — Utilities. No secondary.

**Price** — Free, all territories.

**Content rights** — you own or are licensed for all of it.

**EU Digital Services Act trader status** — **not a trader**. The hardware is
not for sale and the app is free, so there is no commercial activity to declare.
Without an answer here the app cannot be distributed in the EU at all.

**Sign-in** — no, the app does not require sign-in. Demo mode is how a reviewer
sees the whole app with no hardware, and the review notes say so in the first
six lines.

## Then, one command

    xcrun altool --upload-app -f "/Volumes/2TB SSD/claude-build/export/RXV2App.ipa" \
      -t ios --apiKey <KEYID> --apiIssuer <ISSUERID>

Build first, always, so the archive matches the released app:

    cd RXV2App && xcodegen generate
    xcodebuild -project RXV2App.xcodeproj -scheme RXV2App -configuration Release \
      -destination 'generic/platform=iOS' \
      -derivedDataPath "/Volumes/2TB SSD/claude-build/dd_ios" \
      -archivePath "/Volumes/2TB SSD/claude-build/RXV2App.xcarchive" \
      -allowProvisioningUpdates archive
    xcodebuild -exportArchive -archivePath "/Volumes/2TB SSD/claude-build/RXV2App.xcarchive" \
      -exportOptionsPlist appstore/ExportOptions.plist \
      -exportPath "/Volumes/2TB SSD/claude-build/export" -allowProvisioningUpdates

## Go to TestFlight first

The testers who asked for a receiver are the reason for all this. TestFlight
needs no App Review for internal testers, so they can be flying the app the day
the build uploads — while the store listing is still being reviewed.
