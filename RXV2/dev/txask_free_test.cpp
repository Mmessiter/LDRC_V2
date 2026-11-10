// The rule that lets a silent phone app go when a transmitter's screen asks for Bluetooth (0.9.921) - run by
// dev/txask_free_test.sh against the REAL block of src/BleConfig.h (TXASK-FREE-BEGIN .. END).
// Malcolm, 10 Nov 2026: the transmitter "is now very reluctant to connect by Bluetooth ... Even with the app closed".
#include <cstdio>
#include <cstdint>
#include TXASK_BLOCK
static int fails = 0;
static void expect(const char* what, bool got, bool want) {
    if (got != want) fails++;
    printf("%s %-78s %s\n", got == want ? "PASS" : "FAIL", what, got ? "let go" : "kept");
}
int main() {
    const uint32_t ask = 600000;                           // the transmitter's ask began 10 minutes after boot
    // The case of 10 Nov: the app was used, then left with Home - connected 5 min before the ask, silent for 2 min.
    expect("app in the background (connected 5 min, silent 2 min): let go at once",
           txAskFreesSilentApp(true, true, false, ask, ask - 300000, ask - 120000, ask + 20), true);
    expect("... not while the transmitter is not asking",
           txAskFreesSilentApp(false, true, false, ask, ask - 300000, ask - 120000, ask + 20), false);
    expect("... nor with no client",
           txAskFreesSilentApp(true, false, false, ask, ask - 300000, ask - 120000, ask + 20), false);
    expect("... nor with no ask start noted",
           txAskFreesSilentApp(true, true, false, 0, ask - 300000, ask - 120000, ask + 20), false);
    // An app in use: its pages ask every second or two.
    expect("app in use (spoke 1 s after the ask began): kept",
           txAskFreesSilentApp(true, true, false, ask, ask - 300000, ask + 1000, ask + 9000), false);
    expect("app in use (spoke at the very moment the ask began): kept",
           txAskFreesSilentApp(true, true, false, ask, ask - 300000, ask, ask + 9000), false);
    // Just backgrounded as the pilot picked up the transmitter: 5 s of silence first.
    expect("app silent 2 s before the ask, now 1 s after (3 s silent): kept for now",
           txAskFreesSilentApp(true, true, false, ask, ask - 300000, ask - 2000, ask + 1000), false);
    expect("... 3 s after the ask (5 s silent): let go",
           txAskFreesSilentApp(true, true, false, ask, ask - 300000, ask - 2000, ask + 3000), true);
    // The transmitter's own screen: it joins after the ask (or, its ask lost, a moment before the renewal).
    expect("the screen, joined while the transmitter asked (silent 30 s on the menu): kept",
           txAskFreesSilentApp(true, true, true, ask, ask + 3000, ask + 3000, ask + 33000), false);
    expect("a client that came after the ask began, flag not set: kept",
           txAskFreesSilentApp(true, true, false, ask, ask + 3000, ask + 3000, ask + 33000), false);
    expect("a client that came 5 s before the ask (its ask lost, the renewal 5 s on): kept",
           txAskFreesSilentApp(true, true, false, ask, ask - 5000, ask - 5000, ask + 30000), false);
    expect("a client that came 10 s before the ask and has been silent since: let go",
           txAskFreesSilentApp(true, true, false, ask, ask - 10000, ask - 10000, ask + 1), true);
    // A screen that joined during an ask, then a lapse of the ask (a radio-link outage of 20 s) and a new ask:
    // the flag set at its connection keeps it.
    expect("the screen across a lapse and a new ask (flag set at its connection): kept",
           txAskFreesSilentApp(true, true, true, ask + 60000, ask + 3000, ask + 3000, ask + 90000), false);
    // millis() wraps after 49.7 days: the same answers across the wrap.
    const uint32_t w = 0xFFFFF000u;                         // 4 s before the wrap
    expect("across the millis() wrap: a background app let go",
           txAskFreesSilentApp(true, true, false, w + 8000, w - 300000, w - 120000, w + 8020), true);
    expect("across the millis() wrap: an app in use kept",
           txAskFreesSilentApp(true, true, false, w + 8000, w - 300000, w + 9000, w + 15000), false);
    expect("across the millis() wrap: a client 5 s before the ask kept",
           txAskFreesSilentApp(true, true, false, w + 8000, w + 3000, w + 3000, w + 40000), false);
    if (fails) printf("\n%d FAILED\n", fails); else printf("\nALL PASS\n");
    return fails ? 1 : 0;
}
