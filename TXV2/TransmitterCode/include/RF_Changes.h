// B196 (Malcolm, 8 Nov 2026: "Please do all five"): WHAT CHANGED?, page 88 (RFChangesView, from Guide & checks: 16 MB
// screens). "It flew fine last week - what did I change?" The flight controller is read as a backup reads it (RF_Backup.h
// BAK_JOB_COMPARE: the same sweep, nothing saved) and each key is compared with this model's backup on the card, setting by
// setting, named in the words of the pages that set them (byte for byte release/4.6.0 src/main/msp/msp.c). A row says the
// backup's value, then the flight controller's: "PIDs bank 2: Roll P 50 -> 65".
// PUT BACK writes one setting as the backup has it (BAK_JOB_PUTBACK): at the read before the write, the flight controller's
// image as it is NOW, with only that setting's bytes - or bit, for a feature - taken from the backup; written, read back,
// stored, and the flight controller restarted when it is one it reads only at its start. Nothing else in that key moves,
// and the backup itself is never written.
#include <Arduino.h>
#include "1Definitions.h"
#ifndef RF_CHANGES_H
#define RF_CHANGES_H

enum { K_SKIP = 0, K_U8, K_S8, K_U16, K_S16, K_U32, K_T10, K_BITS, K_TEXT, K_HEX, K_STEP,   // (K_STEP: a switch end, 5 us steps about 1500; K_T10: tenths of a second)
       // B197 (Malcolm, 8 Nov 2026, of a swash trim: "I changed the trim from 1 to 0.5 not 10 to 5"): a value in the phone's units,
       // as its page shows it - tenths of a per cent or a degree, hundredths of a volt or a metre, a mixer limit in degrees
       K_U8_T10S, K_U8_T10P, K_U16_T10P, K_S16_T10P, K_S16_T10D, K_S16_DEG, K_U16_DEG12, K_S16_INDEG, K_S16_TAIL, K_S8_GEO,
       K_U16_H100V, K_U16_H100M, K_U16_US, K_S16_US, K_U16_HZ, K_U16_MS };
struct ChgF { uint8_t off, kind; char name[26]; };   // (the names IN the table, in flash: a pointer would leave each name in RAM1)
struct ChgT { uint8_t fn, first, stride; const char *item; const ChgF *f; uint8_t nf; };

static const ChgF CF_112[] PROGMEM = {{0, K_U16, "Roll P"}, {2, K_U16, "Roll I"}, {4, K_U16, "Roll D"}, {6, K_U16, "Roll F"}, {8, K_U16, "Pitch P"}, {10, K_U16, "Pitch I"},
    {12, K_U16, "Pitch D"}, {14, K_U16, "Pitch F"}, {16, K_U16, "Yaw P"}, {18, K_U16, "Yaw I"}, {20, K_U16, "Yaw D"}, {22, K_U16, "Yaw F"}, {24, K_U16, "Roll boost"},
    {26, K_U16, "Pitch boost"}, {28, K_U16, "Yaw boost"}, {30, K_U16, "Roll offset"}, {32, K_U16, "Pitch offset"}};
static const ChgF CF_94[] PROGMEM = {{0, K_U8, "PID mode"}, {1, K_U8, "I decay ground"}, {2, K_U8, "I decay cyclic"}, {3, K_U8, "I decay yaw"}, {4, K_U8, "I decay limit cyclic"},
    {5, K_U8, "I decay limit yaw"}, {6, K_SKIP, ""}, {7, K_U8, "I limit roll"}, {8, K_U8, "I limit pitch"}, {9, K_U8, "I limit yaw"}, {10, K_U8, "Gyro cutoff roll"},
    {11, K_U8, "Gyro cutoff pitch"}, {12, K_U8, "Gyro cutoff yaw"}, {13, K_U8, "D cutoff roll"}, {14, K_U8, "D cutoff pitch"}, {15, K_U8, "D cutoff yaw"},
    {16, K_U8, "I relax type"}, {17, K_U8, "I relax roll"}, {18, K_U8, "I relax pitch"}, {19, K_U8, "I relax yaw"}, {20, K_U8, "Yaw stop gain CW"},
    {21, K_U8, "Yaw stop gain CCW"}, {22, K_U8, "Yaw precomp cutoff"}, {23, K_U8, "Yaw cyclic feed-fwd"}, {24, K_U8, "Yaw collective feed-fwd"}, {25, K_SKIP, ""},
    {26, K_SKIP, ""}, {27, K_U8, "Pitch collective feed-fwd"}, {28, K_U8, "Angle level strength"}, {29, K_U8, "Angle level limit"}, {30, K_U8, "Horizon strength"},
    {31, K_U8, "Trainer gain"}, {32, K_U8, "Trainer angle limit"}, {33, K_U8, "Cross-coupling gain"}, {34, K_U8, "Cross-coupling ratio"},
    {35, K_U8, "Cross-coupling cutoff"}, {36, K_U8, "Offset limit roll"}, {37, K_U8, "Offset limit pitch"}, {38, K_U8, "Boost cutoff roll"},
    {39, K_U8, "Boost cutoff pitch"}, {40, K_U8, "Boost cutoff yaw"}, {41, K_U8, "Yaw inertia gain"}, {42, K_U8, "Yaw inertia cutoff"}};
static const ChgF CF_111[] PROGMEM = {{0, K_U8, "Rates type"},
    {1, K_U8, "Roll centre"}, {2, K_U8, "Roll expo"}, {3, K_U8, "Roll max"}, {4, K_U8, "Roll response"}, {5, K_U16, "Roll accel limit"},
    {7, K_U8, "Pitch centre"}, {8, K_U8, "Pitch expo"}, {9, K_U8, "Pitch max"}, {10, K_U8, "Pitch response"}, {11, K_U16, "Pitch accel limit"},
    {13, K_U8, "Yaw centre"}, {14, K_U8, "Yaw expo"}, {15, K_U8, "Yaw max"}, {16, K_U8, "Yaw response"}, {17, K_U16, "Yaw accel limit"},
    {19, K_U8, "Collective centre"}, {20, K_U8, "Collective expo"}, {21, K_U8, "Collective max"}, {22, K_U8, "Collective response"}, {23, K_U16, "Collective accel"},
    {25, K_U8, "Roll boost gain"}, {26, K_U8, "Roll boost cutoff"}, {27, K_U8, "Pitch boost gain"}, {28, K_U8, "Pitch boost cutoff"},
    {29, K_U8, "Yaw boost gain"}, {30, K_U8, "Yaw boost cutoff"}, {31, K_U8, "Coll boost gain"}, {32, K_U8, "Coll boost cutoff"},
    {33, K_U8, "Yaw dynamic ceiling"}, {34, K_U8, "Yaw dynamic deadband"}, {35, K_U8, "Yaw deadband filter"}, {36, K_U8, "Cyclic ring"}, {37, K_U8, "Cyclic polar"}};
static const ChgF CF_148[] PROGMEM = {{0, K_U16, "Head speed"}, {2, K_U8, "Gain"}, {3, K_U8, "P gain"}, {4, K_U8, "I gain"}, {5, K_U8, "D gain"}, {6, K_U8, "F gain"},
    {7, K_U8, "TTA gain"}, {8, K_U8, "TTA limit"}, {9, K_U8, "Yaw weight"}, {10, K_U8, "Cyclic weight"}, {11, K_U8, "Collective weight"}, {12, K_U8, "Max throttle"},
    {13, K_U8, "Min throttle"}, {14, K_U8, "Fallback drop"}, {15, K_U16, "Flags (PID spool-up)"}};
static const ChgF CF_142[] PROGMEM = {{0, K_U8, "Mode"}, {1, K_T10, "Start-up time"}, {3, K_T10, "Spool-up time"}, {5, K_T10, "Tracking time"}, {7, K_T10, "Recovery time"},
    {9, K_T10, "Hold timeout"}, {11, K_SKIP, ""}, {13, K_T10, "Autorotation timeout"}, {15, K_SKIP, ""}, {17, K_SKIP, ""}, {19, K_U8, "Handover throttle"},
    {20, K_U8, "Power filter"}, {21, K_U8, "RPM filter"}, {22, K_U8, "TTA filter"}, {23, K_U8, "Feed-fwd filter"}, {24, K_SKIP, ""}, {25, K_U8, "D filter (x0.1 Hz)"},
    {26, K_T10, "Spool-down time"}, {28, K_U8, "Throttle type"}, {29, K_SKIP, ""}, {30, K_SKIP, ""}, {31, K_U8, "Idle throttle"}, {32, K_U8, "Auto throttle"},
    {33, K_U8, "Bypass curve 1"}, {34, K_U8, "Bypass curve 2"}, {35, K_U8, "Bypass curve 3"}, {36, K_U8, "Bypass curve 4"}, {37, K_U8, "Bypass curve 5"},
    {38, K_U8, "Bypass curve 6"}, {39, K_U8, "Bypass curve 7"}, {40, K_U8, "Bypass curve 8"}, {41, K_U8, "Bypass curve 9"}};
static const ChgF CF_146[] PROGMEM = {{0, K_U8, "Mode"}, {1, K_U8, "Roll upright first"}, {2, K_U8, "Flip gain"}, {3, K_U8, "Level gain"}, {4, K_U8_T10S, "Pull-up time"},
    {5, K_U8_T10S, "Climb time"}, {6, K_U8_T10S, "Flip time"}, {7, K_U8_T10S, "Exit time"}, {8, K_U16_T10P, "Pull-up collective"}, {10, K_U16_T10P, "Climb collective"},
    {12, K_U16_T10P, "Hover collective"}, {14, K_U16_H100M, "Hover height"}, {16, K_U16, "Height P"}, {18, K_U16, "Height I"}, {20, K_U16, "Height D"},
    {22, K_U16_T10P, "Max collective"}, {24, K_U16, "Max rate"}, {26, K_U16, "Max acceleration"}};
static const ChgF CF_92[] PROGMEM = {{0, K_U8, "Gyro hardware lowpass"}, {1, K_U8, "Lowpass 1 type"}, {2, K_U16, "Lowpass 1 Hz"}, {4, K_U8, "Lowpass 2 type"},
    {5, K_U16, "Lowpass 2 Hz"}, {7, K_U16, "Notch 1 Hz"}, {9, K_U16, "Notch 1 cutoff"}, {11, K_U16, "Notch 2 Hz"}, {13, K_U16, "Notch 2 cutoff"},
    {15, K_U16, "Dynamic lowpass min"}, {17, K_U16, "Dynamic lowpass max"}, {19, K_U8, "Dynamic notches"}, {20, K_U8, "Dynamic notch Q"},
    {21, K_U16, "Dynamic notch min Hz"}, {23, K_U16, "Dynamic notch max Hz"}, {25, K_U8, "RPM filter strength"}, {26, K_U8, "RPM filter min Hz"}};
static const ChgF CF_42[] PROGMEM = {{0, K_U8, "Rotor direction"}, {1, K_U8, "Tail type"}, {2, K_U8_T10P, "Tail motor idle"}, {3, K_S16_TAIL, "Tail centre trim"}, {5, K_U8, "Swash type"},
    {6, K_U8, "Swash ring"}, {7, K_S16_T10D, "Swash phase"}, {9, K_U16_DEG12, "Total pitch limit"}, {11, K_S16_T10P, "Swash trim roll"}, {13, K_S16_T10P, "Swash trim pitch"},
    {15, K_S16_T10P, "Swash trim collective"}, {17, K_U8, "TTA precomp"}, {18, K_S8_GEO, "Geometry correction"}, {19, K_S8, "Collective tilt +"}, {20, K_S8, "Collective tilt -"}};
static const ChgF CF_174[] PROGMEM = {{0, K_S16_T10P, "rate"}, {2, K_S16_INDEG, "min"}, {4, K_S16_INDEG, "max"}};   // (as the Travel extents pages: the rate in %, the ends in degrees)
static const ChgF CF_120[] PROGMEM = {{0, K_U16_US, "centre"}, {2, K_S16_US, "min"}, {4, K_S16_US, "max"}, {6, K_U16_US, "scale -"}, {8, K_U16_US, "scale +"}, {10, K_U16_HZ, "rate"},
    {12, K_U16_MS, "speed"}, {14, K_U16, "flags"}};
static const ChgF CF_172[] PROGMEM = {{0, K_U8, "operation"}, {1, K_U8, "input"}, {2, K_U8, "output"}, {3, K_S16, "offset"}, {5, K_S16, "weight"}};
static const ChgF CF_131[] PROGMEM = {{0, K_U16, "Min throttle"}, {2, K_U16, "Max throttle"}, {4, K_U16, "Min command"}, {6, K_SKIP, ""}, {7, K_SKIP, ""},
    {8, K_U8, "DShot telemetry"}, {9, K_U8, "ESC signal"}, {10, K_U16, "PWM rate"}, {12, K_U8, "Unsynced PWM"}, {13, K_U8, "Motor poles"}, {14, K_U8, "Motor 2 poles"},
    {15, K_U8, "Motor 3 poles"}, {16, K_U8, "Motor 4 poles"}, {17, K_U8, "RPM filter"}, {18, K_U8, "RPM filter 2"}, {19, K_U8, "RPM filter 3"}, {20, K_U8, "RPM filter 4"},
    {21, K_U16, "Main gear (rotor)"}, {23, K_U16, "Main gear (motor)"}, {25, K_U16, "Tail gear (rotor)"}, {27, K_U16, "Tail gear (tail)"}};
static const ChgF CF_80[] PROGMEM = {{0, K_SKIP, ""}, {1, K_U8, "Where"}, {2, K_U8, "When"}, {3, K_U16, "How often"}, {5, K_HEX, "Fields"}, {9, K_U16, "Erase free KiB"},
    {11, K_U8, "Overwrite the oldest"}, {12, K_U8, "After disarm"}};
static const ChgF CF_38[] PROGMEM = {{0, K_S16_DEG, "Roll"}, {2, K_S16_DEG, "Pitch"}, {4, K_S16_DEG, "Yaw"}};
static const ChgF CF_61[] PROGMEM = {{0, K_U8, "Auto-disarm delay"}};
static const ChgF CF_240[] PROGMEM = {{0, K_S16_T10D, "Pitch trim"}, {2, K_S16_T10D, "Roll trim"}};
static const ChgF CF_96[] PROGMEM = {{0, K_U8, "Accelerometer"}, {1, K_U8, "Barometer"}, {2, K_U8, "Compass"}, {3, K_U8, "Gyro used"}, {4, K_U8, "Gyro high range"},
    {5, K_U8, "Gyro still threshold"}, {6, K_U16, "Gyro calibration time"}, {8, K_SKIP, ""}, {10, K_U8, "Check overflow"}};
static const ChgF CF_126[] PROGMEM = {{0, K_U8, "Gyro 1 alignment"}, {1, K_U8, "Gyro 2 alignment"}, {2, K_U8, "Compass alignment"}};
static const ChgF CF_64[] PROGMEM = {{0, K_U8, "Roll"}, {1, K_U8, "Pitch"}, {2, K_U8, "Yaw"}, {3, K_U8, "Collective"}, {4, K_U8, "Throttle"}, {5, K_U8, "Aux 1"},
    {6, K_U8, "Aux 2"}, {7, K_U8, "Aux 3"}};
static const ChgF CF_66[] PROGMEM = {{0, K_U16, "Stick centre"}, {2, K_U16, "Stick travel"}, {4, K_SKIP, ""}, {6, K_U16, "Min throttle"}, {8, K_U16, "Max throttle"},
    {10, K_U8, "Deadband"}, {11, K_U8, "Yaw deadband"}};
static const ChgF CF_75[] PROGMEM = {{0, K_U8_T10S, "Delay"}, {1, K_U8_T10S, "Off delay"}, {2, K_U16, "Throttle"}, {4, K_U8, "Switch mode"}, {5, K_T10, "Throttle low delay"},
    {7, K_U8, "Procedure"}};
static const ChgF CF_50[] PROGMEM = {{0, K_U8, "RSSI channel"}, {1, K_U8, "RSSI scale"}, {2, K_U8, "RSSI invert"}, {3, K_U8, "RSSI offset"}};
static const ChgF CF_32[] PROGMEM = {{0, K_U16, "Capacity"}, {2, K_U8, "Cells"}, {3, K_U8, "Voltage from"}, {4, K_U8, "Current from"}, {5, K_U16_H100V, "Cell minimum"},
    {7, K_U16_H100V, "Cell maximum"}, {9, K_U16_H100V, "Cell full"}, {11, K_U16_H100V, "Cell warning"}, {13, K_U8, "Low voltage %"}, {14, K_U8, "Used warning %"},
    {15, K_U16, "Capacity 1"}, {17, K_U16, "Capacity 2"}, {19, K_U16, "Capacity 3"}, {21, K_U16, "Capacity 4"}, {23, K_U16, "Capacity 5"}, {25, K_U16, "Capacity 6"}};
static const ChgF CF_123[] PROGMEM = {{0, K_U8, "ESC brand"}, {1, K_U8, "Half duplex"}, {2, K_U16, "Update rate"}, {4, K_U16, "Current offset"}, {6, K_SKIP, ""},
    {10, K_U8, "Pin swap"}, {11, K_S8, "Voltage correction"}, {12, K_S8, "Current correction"}, {13, K_S8, "Used correction"}};
static const ChgF CF_34[] PROGMEM = {{0, K_U8, "action"}, {1, K_U8, "AUX"}, {2, K_STEP, "from"}, {3, K_STEP, "to"}};
static const ChgF CF_77[] PROGMEM = {{0, K_U8, "mode"}, {1, K_U16, "value"}};
static const ChgF CF_52[] PROGMEM = {{0, K_U8, "function"}, {1, K_U8, "on AUX"}, {2, K_STEP, "on from"}, {3, K_STEP, "on to"}, {4, K_U8, "AUX"}, {5, K_STEP, "from"},
    {6, K_STEP, "to"}, {7, K_STEP, "from 2"}, {8, K_STEP, "to 2"}, {9, K_S16, "min"}, {11, K_S16, "max"}, {13, K_U8, "step"}};
static const ChgF CF_184[] PROGMEM = {{0, K_HEX, "Buzzer events"}, {4, K_U8, "Motor beep tone"}, {5, K_HEX, "Motor beep events"}};
static const ChgF CF_36[] PROGMEM = {{0, K_BITS, ""}};
static const ChgF CF_10[] PROGMEM = {{0, K_TEXT, "Rotorflight name"}};
#define CT(fn, first, stride, item, tab) {fn, first, stride, item, tab, (uint8_t)(sizeof(tab) / sizeof(tab[0]))}
static const ChgT ChgTables[] PROGMEM = {
    CT(112, 0, 0, nullptr, CF_112), CT(94, 0, 0, nullptr, CF_94), CT(111, 0, 0, nullptr, CF_111), CT(148, 0, 0, nullptr, CF_148), CT(142, 0, 0, nullptr, CF_142),
    CT(146, 0, 0, nullptr, CF_146), CT(92, 0, 0, nullptr, CF_92), CT(42, 0, 0, nullptr, CF_42), CT(174, 0, 0, nullptr, CF_174), CT(120, 1, 16, "Servo %d", CF_120),
    CT(172, 0, 7, "Rule %d", CF_172), CT(131, 0, 0, nullptr, CF_131), CT(80, 0, 0, nullptr, CF_80), CT(38, 0, 0, nullptr, CF_38), CT(61, 0, 0, nullptr, CF_61),
    CT(240, 0, 0, nullptr, CF_240), CT(96, 0, 0, nullptr, CF_96), CT(126, 0, 0, nullptr, CF_126), CT(64, 0, 0, nullptr, CF_64), CT(66, 0, 0, nullptr, CF_66),
    CT(75, 0, 0, nullptr, CF_75), CT(50, 0, 0, nullptr, CF_50), CT(32, 0, 0, nullptr, CF_32), CT(123, 0, 0, nullptr, CF_123), CT(34, 0, 4, "Slot %d", CF_34),
    CT(77, 0, 3, "Channel %d", CF_77), CT(52, 0, 14, "Knob %d", CF_52), CT(184, 0, 0, nullptr, CF_184), CT(36, 0, 0, nullptr, CF_36), CT(10, 0, 0, nullptr, CF_10)};
static const int CHG_TABLES = sizeof(ChgTables) / sizeof(ChgTables[0]);
static const char ChgFeatureNames[32][16] PROGMEM = {"PPM receiver", "", "", "Serial receiver", "", "", "Soft serial", "GPS", "", "Rangefinder", "Telemetry", "", "",
    "PWM receiver", "MSP receiver", "RSSI from a pin", "LED strip", "Dashboard", "OSD", "OSD menu", "", "", "", "", "", "SPI receiver", "Governor", "ESC telemetry",
    "RPM sensor", "Dynamic notch", "RPM filter", ""};

struct ChgRow { char key[12]; uint16_t off; uint8_t len; uint8_t mask; uint8_t done; char text[64]; };   // mask: a feature's bit in byte off; len 0: the whole key
static const int CHG_MAX = 60, CHG_ROWS = 6;
DMAMEM static ChgRow ChgRows[CHG_MAX];
static int ChgN = 0, ChgMore = 0, ChgFirst = 0, ChgNotInFile = 0, ChgUnread = 0, ChgRow_ = -1;
static bool ChgDone = false, ChgStopped = false;   // (ChgStopped: the comparison ended short - not every key read)
DMAMEM static char ChgImg[1250];   // the put back's image, made at the read before the write
DMAMEM static char ChgFileHex[1250];                 // (scratch: the backup's image of the key in hand - RAM2, not RAM1)
DMAMEM static uint8_t ChgA[600], ChgB[600];          // (the backup's bytes, the flight controller's)
DMAMEM static bool ChgCovered[600];

FLASHMEM static int ChgKindW(uint8_t kind) // a field's bytes
{
    switch (kind)
    {
    case K_SKIP: case K_U8: case K_S8: case K_STEP: case K_U8_T10S: case K_U8_T10P: case K_S8_GEO: return 1;
    case K_U32: case K_HEX: case K_BITS: return 4;
    default: return 2;
    }
}
FLASHMEM static bool ChgKindSigned(uint8_t kind)
{
    return kind == K_S8 || kind == K_S8_GEO || kind == K_S16 || kind == K_S16_T10P || kind == K_S16_T10D || kind == K_S16_DEG || kind == K_S16_INDEG || kind == K_S16_TAIL || kind == K_S16_US;
}
FLASHMEM static int ChgVal(const uint8_t *b, int n, int off, uint8_t kind, long &v) // a field's value; false (0): not all there
{
    const int w = ChgKindW(kind);
    if (off + w > n) return 0;
    switch (kind)
    {
    case K_STEP: v = 1500 + 5 * (int8_t)b[off]; break;
    case K_U32: case K_HEX: case K_BITS: v = (long)RdU32(b, off); break;
    default:
        if (w == 1) v = ChgKindSigned(kind) ? (long)(int8_t)b[off] : (long)b[off];
        else v = ChgKindSigned(kind) ? (long)(int16_t)(b[off] | (b[off + 1] << 8)) : (long)(uint16_t)(b[off] | (b[off + 1] << 8));
        break;
    }
    return w;
}
struct ChgCtx { int fn, bank; const uint8_t *b; int nb; };   // the key a value is of, and the flight controller's bytes of it (a value whose unit depends on another)
FLASHMEM static void ChgTenths(char *out, size_t n, long tenths, const char *unit) // -12.5
{
    const long a = tenths < 0 ? -tenths : tenths;
    snprintf(out, n, "%s%ld.%ld%s", tenths < 0 ? "-" : "", a / 10, a % 10, unit);
}
FLASHMEM static long ChgRawDeg(long raw, int perThousand) { return (raw * perThousand * 10 + (raw < 0 ? -500 : 500)) / 1000; }   // 1000 raw = 12 (or 24) deg -> tenths (the Travel page's RawToDegTenths)
FLASHMEM static bool ChgTailMotorised(const ChgCtx *c) // the tail's kind (the mixer's byte 1): the key in hand when it is the mixer, else the backup's
{
    if (c->fn == 42) return c->nb > 1 && c->b[1] != 0;
    char h[64];
    return BakGet("42", h, sizeof(h)) >= 4 && !(h[2] == '0' && h[3] == '0');
}
FLASHMEM static void ChgFmt(char *out, size_t n, uint8_t kind, long v, const ChgCtx *c) // a value in the words of the page that shows it
{
    switch (kind)
    {
    case K_T10: case K_U8_T10S: ChgTenths(out, n, v, " s"); return;
    case K_U8_T10P: case K_U16_T10P: case K_S16_T10P: ChgTenths(out, n, v, " %"); return;
    case K_S16_T10D: ChgTenths(out, n, v, " deg"); return;
    case K_S16_DEG: snprintf(out, n, "%ld deg", v); return;
    case K_U16_DEG12: ChgTenths(out, n, ChgRawDeg(v, 12), " deg"); return;
    case K_S16_INDEG:   // a mixer input's end: cyclic and collective 1000 = 12 deg; the tail's 1000 = 24 deg, or 0.1 % when it is a motor (the Travel pages)
        if (c->bank != 3) ChgTenths(out, n, ChgRawDeg(v, 12), " deg");
        else if (ChgTailMotorised(c)) ChgTenths(out, n, v, " %");
        else ChgTenths(out, n, ChgRawDeg(v, 24), " deg");
        return;
    case K_S16_TAIL: if (ChgTailMotorised(c)) ChgTenths(out, n, v, " %"); else ChgTenths(out, n, ChgRawDeg(v, 24), " deg"); return;
    case K_S8_GEO: ChgTenths(out, n, v * 2, ""); return;   // (raw / 5, to one decimal: raw 15 = 3.0)
    case K_U16_H100V: snprintf(out, n, "%ld.%02ld V", v / 100, v % 100); return;
    case K_U16_H100M: snprintf(out, n, "%ld.%02ld m", v / 100, v % 100); return;
    case K_U16_US: case K_S16_US: case K_STEP: snprintf(out, n, "%ld us", v); return;
    case K_U16_HZ: snprintf(out, n, "%ld Hz", v); return;
    case K_U16_MS: snprintf(out, n, "%ld ms", v); return;
    case K_HEX: snprintf(out, n, "%08lX", (unsigned long)v); return;
    default: snprintf(out, n, "%ld", v); return;
    }
}
FLASHMEM static void ChgSection(const char *key, char *out, size_t n)
{
    const int fn = atoi(key);
    const char *dot = strchr(key, '.');
    const int b = dot ? (int)strtol(dot + 1, nullptr, (fn == 174 || fn == 154) ? 16 : 10) : -1;
    static const char *const axes[5] = {"", "roll", "pitch", "yaw", "collective"};
    switch (fn)
    {
    case 112: snprintf(out, n, "PIDs bank %d", b + 1); return;
    case 94: snprintf(out, n, "PIDs + bank %d", b + 1); return;
    case 148: snprintf(out, n, "Governor bank %d", b + 1); return;
    case 146: snprintf(out, n, "Rescue bank %d", b + 1); return;
    case 111: snprintf(out, n, "Rates bank %d", b + 1); return;
    case 174: snprintf(out, n, "Travel %s", b >= 1 && b <= 4 ? axes[b] : "?"); return;
    case 154: snprintf(out, n, "RPM notches %s", b >= 0 && b <= 2 ? axes[b + 1] : "?"); return;
    case 142: snprintf(out, n, "Governor"); return;
    case 42: snprintf(out, n, "Mixer"); return;
    case 120: snprintf(out, n, "Servos"); return;
    case 172: snprintf(out, n, "Mixer rules"); return;
    case 131: snprintf(out, n, "Motor"); return;
    case 80: snprintf(out, n, "Black box"); return;
    case 10: snprintf(out, n, "Name"); return;
    case 36: snprintf(out, n, "Features"); return;
    case 38: snprintf(out, n, "Mounting"); return;
    case 61: snprintf(out, n, "Arming"); return;
    case 240: snprintf(out, n, "Level"); return;
    case 96: snprintf(out, n, "Sensors"); return;
    case 126: snprintf(out, n, "Sensor alignment"); return;
    case 64: snprintf(out, n, "Channel order"); return;
    case 44: snprintf(out, n, "Receiver"); return;
    case 66: snprintf(out, n, "Sticks"); return;
    case 75: snprintf(out, n, "Failsafe"); return;
    case 50: snprintf(out, n, "RSSI"); return;
    case 73: snprintf(out, n, "Telemetry"); return;
    case 92: snprintf(out, n, "Filters"); return;
    case 32: snprintf(out, n, "Battery"); return;
    case 123: snprintf(out, n, "ESC telemetry"); return;
    case 56: snprintf(out, n, "Voltage sensors"); return;
    case 40: snprintf(out, n, "Current sensors"); return;
    case 34: snprintf(out, n, "Switches"); return;
    case 238: snprintf(out, n, "Switch logic"); return;
    case 77: snprintf(out, n, "Failsafe values"); return;
    case 52: snprintf(out, n, "Knobs"); return;
    case 184: snprintf(out, n, "Beeper"); return;
    default: snprintf(out, n, "Setting %d", fn); return;
    }
}
FLASHMEM static void ChgAdd(const char *key, int off, int len, uint8_t mask, const char *text)
{
    if (ChgN >= CHG_MAX) { ++ChgMore; return; }
    ChgRow &r = ChgRows[ChgN++];
    snprintf(r.key, sizeof(r.key), "%s", key);
    r.off = (uint16_t)off; r.len = (uint8_t)len; r.mask = mask; r.done = 0;
    snprintf(r.text, sizeof(r.text), "%s", text);
}
FLASHMEM static bool ChgPutable(const char *key) { BakTodo t; return BakTodoOf(key, t); }
FLASHMEM bool ChgTake(const char *key, const char *fcHex, bool optional) // BakToolTake: a key of the sweep, compared with the backup
{
    char *fileHex = ChgFileHex;
    uint8_t *a = ChgA, *b = ChgB;
    if (BakGet(key, fileHex, sizeof(ChgFileHex)) < 0) { ++ChgNotInFile; return true; }   // (an older backup, or more banks now)
    if (!fcHex) { if (!optional) ++ChgUnread; return true; }   // (an optional one - the knobs with no USB cable, an older firmware's - is let go, as the backup lets it go)
    if (strcmp(fcHex, fileHex) == 0) return true;
    const int na = HexToBytes(fileHex, a, 600), nb = HexToBytes(fcHex, b, 600);
    if (atoi(key) == 73) for (int i = 8; i < 12 && i < na && i < nb; ++i) b[i] = a[i];   // (the telemetry's link speed, bytes 8-11, is the flight controller's own: never a change - as the restore's BakSame)
    if (na == nb && memcmp(a, b, (size_t)na) == 0) return true;   // (the same bytes, the hex in another case)
    char sec[32], t[96], w[24], v[24];
    ChgSection(key, sec, sizeof(sec));
    const int fn = atoi(key);
    const ChgT *tab = nullptr;
    for (int i = 0; i < CHG_TABLES; ++i) if (ChgTables[i].fn == fn) { tab = &ChgTables[i]; break; }
    if (!tab || fn == 10 || na != nb)
    { // a key with no table, a name, or one whose length changed (servos, sensors added or gone): the whole key
        if (fn == 10) { char x[20], y[20]; int i = 0; for (; i < na && i < 14 && a[i] >= 32 && a[i] < 127; ++i) x[i] = (char)a[i]; x[i] = 0; for (i = 0; i < nb && i < 14 && b[i] >= 32 && b[i] < 127; ++i) y[i] = (char)b[i]; y[i] = 0; snprintf(t, sizeof(t), "Name: %s -> %s", x[0] ? x : "(none)", y[0] ? y : "(none)"); }   // (14 of the 16 each: two of the widest fit the row)
        else snprintf(t, sizeof(t), "%s: changed", sec);
        ChgAdd(key, 0, 0, 0, t);
        return true;
    }
    bool *covered = ChgCovered;
    memset(covered, 0, 600);
    const char *dot = strchr(key, '.');
    const ChgCtx ctx = {fn, dot ? (int)strtol(dot + 1, nullptr, (fn == 174 || fn == 154) ? 16 : 10) : -1, b, nb};
    const int items = tab->stride ? (na - tab->first) / tab->stride : 1;
    for (int it = 0; it < items; ++it)
    {
        const int base = tab->stride ? tab->first + it * tab->stride : 0;
        for (int f = 0; f < tab->nf; ++f)
        {
            const ChgF &F = tab->f[f];
            long va = 0, vb = 0;
            const int wa = ChgVal(a, na, base + F.off, F.kind, va), wb = ChgVal(b, nb, base + F.off, F.kind, vb);
            if (!wa || !wb) continue;
            for (int k = 0; k < wa; ++k) if (base + F.off + k < 600) covered[base + F.off + k] = true;
            if (va == vb || F.kind == K_SKIP) continue;
            if (F.kind == K_BITS)
            { // a row for each feature turned on or off - each put back alone
                for (int bit = 0; bit < 32; ++bit)
                {
                    const bool oa = (va >> bit) & 1, ob = (vb >> bit) & 1;
                    if (oa == ob) continue;
                    const char *nm = ChgFeatureNames[bit];
                    if (nm[0]) snprintf(t, sizeof(t), "Features: %s %s -> %s", nm, oa ? "on" : "off", ob ? "on" : "off");
                    else snprintf(t, sizeof(t), "Features: bit %d %s -> %s", bit, oa ? "on" : "off", ob ? "on" : "off");
                    ChgAdd(key, base + F.off + bit / 8, 1, (uint8_t)(1u << (bit % 8)), t);
                }
                continue;
            }
            ChgFmt(w, sizeof(w), F.kind, va, &ctx); ChgFmt(v, sizeof(v), F.kind, vb, &ctx);
            if (tab->item) { char itn[16]; snprintf(itn, sizeof(itn), tab->item, it + 1); snprintf(t, sizeof(t), "%s: %s %s %s -> %s", sec, itn, F.name, w, v); }
            else snprintf(t, sizeof(t), "%s: %s %s -> %s", sec, F.name, w, v);
            ChgAdd(key, base + F.off, wa, 0, t);
        }
    }
    for (int i = 0; i < na && i < 600; ++i)
        if (!covered[i] && a[i] != b[i]) { snprintf(t, sizeof(t), "%s: byte %d %u -> %u", sec, i, a[i], b[i]); ChgAdd(key, i, 1, 0, t); }
    return true;
}
// ---- put back
FLASHMEM static void ChgPatch(const char *key, const char *fcHex) // BakToolPatch: the image to write, from the fresh read
{
    snprintf(ChgImg, sizeof(ChgImg), "%s", fcHex);
    if (ChgRow_ < 0 || ChgRow_ >= ChgN || strcmp(ChgRows[ChgRow_].key, key) != 0) return;
    const ChgRow &r = ChgRows[ChgRow_];
    char *fileHex = ChgFileHex;
    if (BakGet(key, fileHex, sizeof(ChgFileHex)) < 2) return;
    if (r.len == 0) { snprintf(ChgImg, sizeof(ChgImg), "%s", fileHex); return; }   // the whole key, as the backup has it
    const size_t at = (size_t)r.off * 2, hl = (size_t)r.len * 2;
    if (strlen(ChgImg) < at + hl || strlen(fileHex) < at + hl) return;
    if (r.mask)
    { // one feature bit: the flight controller's byte, with that bit as the backup has it
        const int fc = Hex2(ChgImg + at), fb = Hex2(fileHex + at);
        const int nv = (fc & ~r.mask) | (fb & r.mask);
        char h[3]; snprintf(h, sizeof(h), "%02X", nv & 0xFF);
        ChgImg[at] = h[0]; ChgImg[at + 1] = h[1];
        return;
    }
    memcpy(ChgImg + at, fileHex + at, hl);
}
FLASHMEM static int ChgImage(const char *key, char *out, size_t n) { (void)key; snprintf(out, n, "%s", ChgImg); return (int)strlen(out); }
// ---- the page
FLASHMEM static void ChgShow()
{
    if (CurrentView != CHANGESVIEW) return;
    char b[96], d[24] = "";
    SendText((char *)"t11", ModelName);
    SendText((char *)"t9", (char *)((BoundFlag && ModelMatched) ? "Connected" : "No model"));
    BakGet("date", d, sizeof(d));
    if (!ChgDone) snprintf(b, sizeof(b), "Comparing with the backup of %s ...", d);
    else if (ChgStopped) snprintf(b, sizeof(b), "Not all read: %d change%s found so far", ChgN + ChgMore, ChgN + ChgMore == 1 ? "" : "s");
    else if (!ChgN) snprintf(b, sizeof(b), "Nothing changed since the backup of %s", d);
    else snprintf(b, sizeof(b), "%d change%s since the backup of %s%s", ChgN + ChgMore, ChgN + ChgMore == 1 ? "" : "s", d, ChgMore ? " (the first 60)" : "");
    SendText((char *)"hd", b);
    for (int r = 0; r < CHG_ROWS; ++r)
    {
        const int i = ChgFirst + r;
        char n[8], c[40];
        const bool on = ChgDone && i < ChgN;
        snprintf(n, sizeof(n), "c%d", r);
        if (on && ChgRows[i].done) { snprintf(b, sizeof(b), "%.52s (put back)", ChgRows[i].text); SendText(n, b); }
        else SendText(n, (char *)(on ? ChgRows[i].text : ""));
        snprintf(c, sizeof(c), "c%d.pco=%u", r, on && ChgRows[i].done ? 33808u : 0u); SendCommand(c);
        const bool put = on && !ChgRows[i].done && ChgPutable(ChgRows[i].key);
        snprintf(c, sizeof(c), "vis p%d,%d", r, put ? 1 : 0); SendCommand(c);
    }
    snprintf(b, sizeof(b), "vis bP,%d", ChgDone && ChgFirst > 0 ? 1 : 0); SendCommand(b);
    snprintf(b, sizeof(b), "vis bN,%d", ChgDone && ChgFirst + CHG_ROWS < ChgN ? 1 : 0); SendCommand(b);
}
FLASHMEM static void ChgCompareDone(int job, const char *verdict)
{
    (void)job;
    ChgDone = true;
    ChgStopped = BakFails > 0;   // (the engine counts what could not be read, the optional ones not)
    if (ChgStopped)
    {
        char m[200];
        snprintf(m, sizeof(m), "Not everything could be read: the list\r\nmay be short.\r\n%.110s", BakFailed[0] ? BakFailed : verdict);
        RfBoxOrQuiet("page RFChangesView", m);
    }
    ChgShow();
}
FLASHMEM static void ChgBegin()
{
    ChgN = 0; ChgMore = 0; ChgFirst = 0; ChgNotInFile = 0; ChgUnread = 0; ChgDone = false; ChgStopped = false; ChgRow_ = -1;
    BakToolTake = ChgTake; BakToolDone = ChgCompareDone; BakToolPage = "page RFChangesView";
    ChgShow();
    BakStart(BAK_JOB_COMPARE);
    if (BakJob != BAK_JOB_COMPARE) { ChgDone = true; ChgShow(); }   // (refused: it said why)
}
FLASHMEM void ToolsChanges() // 241: Guide & checks' "What changed? ..."
{
    if (BakJob != BAK_JOB_NONE) return;
    if (!BakHaveFile()) { PlaySound(WHAHWHAHMSG); MsgBox((char *)"page RFToolsView", (char *)"No backup of this model on the card:\r\nback it up once (Backup & restore),\r\nthen this compares with it."); RfToolsRedraw(); return; }
    if (!CkModelThere("page RFToolsView")) { RfToolsRedraw(); return; }
    UndoNewVisit();
    SendCommand((char *)"page RFChangesView");
    CurrentView = CHANGESVIEW;
    ChgBegin();
}
FLASHMEM void ChangesAgain() { if (BakJob == BAK_JOB_NONE && CurrentView == CHANGESVIEW) { if (CkModelThere("page RFChangesView")) ChgBegin(); else ChgShow(); } }   // 252
FLASHMEM void ChangesPrev() { if (ChgFirst >= CHG_ROWS) ChgFirst -= CHG_ROWS; else ChgFirst = 0; ChgShow(); }                                                     // 254
FLASHMEM void ChangesNext() { if (ChgFirst + CHG_ROWS < ChgN) ChgFirst += CHG_ROWS; ChgShow(); }                                                                 // 255
FLASHMEM void EndChangesView() { if (BakJob != BAK_JOB_NONE) return; RfBackHome(); }                                                                             // 253
FLASHMEM static void ChgPutDone(int job, const char *verdict)
{
    (void)job;
    char m[200];
    if (!BakFails && ChgRow_ >= 0 && ChgRow_ < ChgN)
    {
        ChgRows[ChgRow_].done = 1;
        snprintf(m, sizeof(m), "Put back as the backup has it%s", BakWritten ? "." : ":\r\nit was so already.");
    }
    else snprintf(m, sizeof(m), "Not put back:\r\n%.150s", verdict);
    RfBoxOrQuiet("page RFChangesView", m);
    ChgShow();
}
FLASHMEM void ChangesPutBack() // 251: a row's Put back (the row in the event's top byte, 1-6)
{
    const int r = (int)ScreenEventArg - 1;
    if (BakJob != BAK_JOB_NONE || !ChgDone || r < 0 || r >= CHG_ROWS) return;
    const int i = ChgFirst + r;
    if (i >= ChgN || ChgRows[i].done || !ChgPutable(ChgRows[i].key)) return;
    if (FsRefused("page RFChangesView", true)) { ChgShow(); return; }
    char q[200];
    snprintf(q, sizeof(q), "Put back as the backup has it?\r\n%.60s", ChgRows[i].text);
    if (!GetConfirmation((char *)"page RFChangesView", q)) { ChgShow(); return; }
    ChgRow_ = i;
    BakToolKeysN = 1; snprintf(BakToolKeys[0], sizeof(BakToolKeys[0]), "%s", ChgRows[i].key);
    BakToolImage = ChgImage; BakToolPatch = ChgPatch; BakToolDone = ChgPutDone; BakToolPage = "page RFChangesView";
    ChgImg[0] = 0;
    ChgShow();
    BakStart(BAK_JOB_PUTBACK);
    if (BakJob != BAK_JOB_PUTBACK) ChgShow();   // (refused: it said why)
}
#endif // RF_CHANGES_H
