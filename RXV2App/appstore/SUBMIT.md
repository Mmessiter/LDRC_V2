# Getting LDRC RX V2 onto the App Store

Checked on the machine 2026-09-20, against build 5.148 (441).

## DO THIS — there is only one job, and it takes about five minutes

Everything else I can do for you once you have done this one thing.

### The key

1. Go to **appstoreconnect.apple.com** and sign in.
2. Click **Users and Access** along the top.
3. Click the **Integrations** tab.
4. You are now on **App Store Connect API**, on **Team Keys**.
5. Click the blue **+**.
6. Name it anything — *Claude upload* will do.
7. Access: choose **App Manager** from the dropdown.
8. Click **Generate**.
9. A row appears. Click **Download API Key**.
   **Apple lets you download it once, ever.** If you miss it, delete the key
   and make another — no harm done.
10. On that same page, above the table, is **Issuer ID** — a long line of
    letters, numbers and dashes. Click the copy button beside it.

Then tell me: paste the Issuer ID, and say the key file has downloaded.
I do not need the Key ID — it is in the file's own name.
Leave the file in Downloads. I will put it where it belongs.

### The one thing to check while you are there

Click **Business** in the top bar. The **Free Apps** agreement should say
**Active**. If it does not, click it and accept it — without that, Apple
cannot distribute the app even for nothing.

### That is all

With the key I can create the app record, upload the build, fill in the
listing and put it into TestFlight, without you clicking anything else.
I will read the forms back to you before anything is submitted.

If any screen does not look like the above, just tell me what you see.
Apple moves these pages about, and I would rather you asked than guessed.

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

## Why only one job, and not three

Creating the app record and uploading both go through the same API key, so
once it exists I can do them. That leaves Malcolm with the key itself, which
needs a signed-in human, and the agreement, which needs a person to accept it.

The app record, for the avoidance of doubt, is: Platform **iOS**, Name
**LockDownRadioControl RXV2**, Primary language **English (UK)**, Bundle ID
**com.messiter.rxv2app**, SKU **ldrc-rxv2**, User access **Full Access**.

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
