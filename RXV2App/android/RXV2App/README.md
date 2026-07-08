# RXV2App — Android (Bluetooth)

The Android twin of the iOS RXV2App. Same idea: the app hosts the
receiver's **own web UI** in a WebView and tunnels every HTTP request
over Bluetooth (firmware framing in `RXV2/src/BleConfig.h`). The WiFi
web portal is untouched — this is just a second, fuss-free door.

## How it maps to the iOS app

| iOS | Android |
|---|---|
| `BleLink` (CoreBluetooth) | `Rxv2Ble.kt` (android.bluetooth) — same `Q…|`/`R…|` framing, `S|` live stream |
| `BleSchemeHandler` (`ble://`) | `shouldInterceptRequest` serves `assets/webroot`; `fetch()` bridged via JS |
| `WebScreen` form-shim | same shim + a `fetch()` override (Android can't read POST bodies in the interceptor) |
| bundle `webroot/` | `app/src/main/assets/webroot/` (same 28 files) |

The `webkit.messageHandlers.rxv2` disconnect hook the web UI posts to is
shimmed on Android, so the web pages run unchanged.

## Build & install (command line)

    cd android/RXV2App
    JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home" ./gradlew assembleDebug
    adb install -r app/build/outputs/apk/debug/app-debug.apk

Or open `android/RXV2App` in Android Studio and press Run.

## Using it

Power the receiver with the **transmitter OFF** so its config radio
advertises (same rule as the WiFi portal). The app lists nearby
receivers by signal; tap one to open its web UI over Bluetooth.

## Keeping webroot in sync

`assets/webroot/` is a copy of the iOS app's `webroot/` (which mirrors
`RXV2/data`). If the web UI changes, re-copy it:

    cp -R ../../webroot/* app/src/main/assets/webroot/
