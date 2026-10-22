// Host test of src/BankSelector.h (0.9.904): the position count of the flight controller's bank and rates selector
// lines, read off the receiver's copy of its adjustment lines. Run by dev/bank_selector_test.sh.
#include <cstdio>
#include <cstring>
#include <cstdint>
#include "../src/BankSelector.h"

static int checks = 0, failures = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++failures; printf("   FAIL: %s\n", what); } } while (0)

static uint8_t adj[42 * 14];
static int n = 0;
static void clear() { memset(adj, 0, sizeof adj); n = 0; }
// a line as MSP 52 carries it: fn, enable ch, enable lo, hi (steps), adj ch, range 1 lo, hi, range 2 lo, hi, min, max, step
static void line(uint8_t fn, uint8_t ch, uint16_t mn, uint16_t mx, uint8_t stp) {
    uint8_t *l = adj + n++ * 14;
    l[0] = fn; l[1] = ch; l[2] = 0x83; l[3] = 0x7D; l[4] = ch; l[5] = 0x83; l[6] = 0x7D; l[7] = 0; l[8] = 0;
    l[9] = mn & 255; l[10] = mn >> 8; l[11] = mx & 255; l[12] = mx >> 8; l[13] = stp;
}

int main() {
    printf("- Rotorflight's own form: one line, min..max over the travel\n");
    clear(); line(2, 1, 1, 6, 0); CHECK(bankSelectorZones(adj, 42, 2) == 6, "1..6 is six positions");
    clear(); line(2, 1, 1, 4, 0); CHECK(bankSelectorZones(adj, 42, 2) == 4, "1..4 is four positions");
    clear(); line(2, 1, 0, 1, 0); CHECK(bankSelectorZones(adj, 42, 2) == 2, "0..1 is two positions");
    clear(); line(2, 1, 1, 12, 0); CHECK(bankSelectorZones(adj, 42, 2) == 6, "a range beyond six is capped at six");
    clear(); line(2, 1, 5, 2, 0); CHECK(bankSelectorZones(adj, 42, 2) == 0, "max below min is no selector");
    printf("- the old form: one line per position, each a fixed value\n");
    clear(); for (uint16_t p = 1; p <= 4; ++p) line(2, 1, p, p, 0); CHECK(bankSelectorZones(adj, 42, 2) == 4, "four fixed lines are four positions");
    clear(); for (uint16_t p = 1; p <= 6; ++p) line(2, 1, p, p, 0); CHECK(bankSelectorZones(adj, 42, 2) == 6, "six fixed lines");
    clear(); for (uint16_t p = 1; p <= 8; ++p) line(2, 1, p, p, 0); CHECK(bankSelectorZones(adj, 42, 2) == 6, "eight fixed lines are capped at six");
    clear(); line(2, 1, 3, 3, 0); CHECK(bankSelectorZones(adj, 42, 2) == 0, "one fixed value on its own is no selector");
    printf("- what is not a selector\n");
    clear(); CHECK(bankSelectorZones(adj, 42, 2) == 0, "no lines at all");
    clear(); line(2, 1, 1, 6, 1); CHECK(bankSelectorZones(adj, 42, 2) == 0, "a step adjustment on the bank function is a nudge, not a selector");
    clear(); line(14, 1, 10, 60, 0); line(8, 2, 1, 4, 0); CHECK(bankSelectorZones(adj, 42, 2) == 0, "other functions do not count");
    printf("- bank and rates lines side by side, in any order, among other lines\n");
    clear(); line(14, 3, 10, 60, 0); line(1, 2, 1, 3, 0); line(5, 4, 1, 1, 0); line(2, 1, 1, 6, 0);
    CHECK(bankSelectorZones(adj, 42, 2) == 6, "the bank line found after the others");
    CHECK(bankSelectorZones(adj, 42, 1) == 3, "the rates line with three positions");
    printf("- the first selector line of a function decides (a duplicate below it is the pages' to remove)\n");
    clear(); line(2, 1, 1, 4, 0); line(2, 1, 1, 6, 0); CHECK(bankSelectorZones(adj, 42, 2) == 4, "the first bank line");
    printf("- a short set (fewer lines than 42)\n");
    clear(); line(2, 1, 1, 6, 0); CHECK(bankSelectorZones(adj, 1, 2) == 6 && bankSelectorZones(adj, 0, 2) == 0, "only the lines given are read");
    printf("\n%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
