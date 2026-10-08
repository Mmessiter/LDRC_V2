// What the drawing code needs from the parts of main.cpp that render.cpp leaves out (the transmitter's state, the
// backlight, audio, the radios): a main board that has never said what it is doing, so every button with a rule is usable.
static int txStatus = -1; static const int TX_MODEL = 4, TX_RADIOS_OFF = 32;   // (lib/LdrcUpdate/TxState.h)
struct TxStub { bool armed = false; const char *motorText(bool) { return nullptr; } } tx;
static int sysDim = 100; static int rtcDim = 0; static uint32_t rtcDimMagic = 0; static const uint32_t RTC_DIM_MAGIC = 0x4C44494D;
static bool blDark = false, quietActive = false;
static void backlight(int) {} static bool updHoldsLight() { return false; } static void applyRadios(const char *) {}
static void picPageLoaded() {} static void flightPageLoaded() {} static uint32_t flightCountdownAt = 0; static void coloursPageLoaded() {} static bool coloursRequested = false; static bool flightDefinedRequested = false; static bool appearanceRequested = false; static void appearancePageLoaded() {} static void pongCommand(const std::string &) {} static void audioStart(int, bool) {} static int audioVolume = 50; static void audioSetVolume(int v) { audioVolume = v; }
static int pendingVol = 0, pendingBg = 0; static bool updRequested = false, rxUpdRequested = false, wifiRequested = false, flightRequested = false;
static std::string lastDateTime, sentTrace, outBuf, oddTrace; static int scriptDepth = 0;
static std::string recent[64]; static int recentN = 0;
static void blog(const char *, const std::string &) {}
static void rtcGlobalNote(const std::string &, int32_t) {}            // (1.9.7: the last values of global variables, kept through the chip's own restarts)
static char rtcPage[24]; static uint32_t rtcMagic = 0; static char rtcPicture[40]; static uint32_t rtcPictureMagic = 0;
static void delay(uint32_t) {}
static void flushOut();
// (1.11.17) the workshop door and the Bluetooth pipe: the renderer draws, it does not talk
static void doorToggle() {}
static void blePipeCommand(const std::string &) {}
static void bleTxCommand(const std::string &) {}
static void bleHttpCommand(const std::string &) {}
static void openKeyboard(int, int) {}                                 // (1.11.36: a click from the main board opens a keyboard on the screen; not on the Mac)
