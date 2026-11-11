// The receiver's hold and the ages of silence counted from it (0.9.922) - run by dev/link_hold_test.sh against the
// REAL block of src/1Defs.h (LINK-AGES-BEGIN .. END).
// Malcolm, 11 Nov 2026: "let's put both timeouts to 3 seconds. A gap of over 3 seconds is very unlikely and remains a
// problem. Under three seconds and recovery is immediate."
#include <cstdio>
#include <cstdint>
#include LINK_BLOCK
static int fails = 0;
static void expect(const char* what, bool ok) {
    if (!ok) fails++;
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
}
// The output stage's own rule (src/Output.h sbusTick: `failsafe = age > OUTPUT_FAILSAFE_MS`), and the two later ages
// as the sources use them (`< LINK_QUIET_MS` = the channels' arming word still counts; `> LINK_DEAD_MS` = may write flash).
static bool held(uint32_t age)      { return !(age > OUTPUT_FAILSAFE_MS); }
static bool armWord(uint32_t age)   { return age < LINK_QUIET_MS; }
static bool mayWrite(uint32_t age)  { return age > LINK_DEAD_MS; }
int main() {
    expect("the hold is the 3000 ms Malcolm asked for", OUTPUT_FAILSAFE_MS == 3000);
    expect("a gap of 1.6 s (failsafe, at the old 1.5 s): the last positions still go to the flight controller", held(1600));
    expect("a gap of 2.5 s: still held", held(2500));
    expect("a gap of 3000 ms exactly: still held", held(3000));
    expect("3001 ms: the output goes to failsafe", !held(3001));
    // Nothing that stalls the loop may begin while the model flies on its held sticks.
    bool quietInside = false, deadInside = false;
    for (uint32_t age = 0; age <= OUTPUT_FAILSAFE_MS; ++age) {
        if (!armWord(age)) quietInside = true;      // a "disarm edge" here would start the flight's save (sticks still for 2 s: always, in a gap)
        if (mayWrite(age)) deadInside = true;
    }
    expect("through the whole hold the channels' arming word still counts (no save's disarm edge)", !quietInside);
    expect("through the whole hold nothing may write flash", !deadInside);
    expect("the arming word lapses half a second after the hold (as it did: 2000 beside 1500)", LINK_QUIET_MS == OUTPUT_FAILSAFE_MS + 500);
    expect("the link is taken to be dead a second and a half after the hold (as it was: 3000 beside 1500)", LINK_DEAD_MS == OUTPUT_FAILSAFE_MS + 1500);
    expect("the radios come back (WIFI_REENABLE_AFTER_LOST_MS) well after the link is dead", (uint32_t)WIFI_REENABLE >= LINK_DEAD_MS + 3000);
    expect("and before the fallback save of the flight (FLIGHT_SAVE_AFTER_MS), as before", (uint32_t)FLIGHT_SAVE_AFTER > LINK_DEAD_MS);
#ifdef TX_RED_LED_ON_TIME
    expect("the transmitter calls the model lost (RED_LED_ON_TIME) at the same moment the hold ends", (uint32_t)TX_RED_LED_ON_TIME == OUTPUT_FAILSAFE_MS);
#else
    printf("     (the transmitter's source is not on this computer: its timeout was not compared)\n");
#endif
    if (fails) printf("\n%d FAILED\n", fails); else printf("\nALL PASS\n");
    return fails ? 1 : 0;
}
