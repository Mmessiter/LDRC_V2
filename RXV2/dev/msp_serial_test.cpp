// Host test for MspSerialCore.h:  clang++ -std=c++17 -I../src dev/msp_serial_test.cpp -o /tmp/mspt && /tmp/mspt
#include <cstdio>
#include <vector>
#include "MspSerialCore.h"
static int fails = 0;
static void check(bool ok, const char* what) { printf("%s %s\n", ok ? "ok  " : "FAIL", what); if (!ok) fails++; }
struct Got { int calls = 0; uint8_t cmd = 0; std::vector<uint8_t> p; bool err = false; };
static void onFrame(void* ctx, uint8_t cmd, const uint8_t* p, uint16_t n, bool e) { Got* g = (Got*)ctx; g->calls++; g->cmd = cmd; g->p.assign(p, p + n); g->err = e; }
// Encode a REPLY the way the FC does (same framing, '>' or '!'), for feeding the parser.
static std::vector<uint8_t> reply(uint8_t cmd, const std::vector<uint8_t>& d, bool err = false) {
    std::vector<uint8_t> f = { '$', 'M', (uint8_t)(err ? '!' : '>') }; uint8_t crc = 0;
    auto put = [&](uint8_t b) { f.push_back(b); crc ^= b; };
    // Rotorflight/Betaflight order (msp_serial.c): jumbo = 255, cmd, u16 length; else size, cmd
    if (d.size() >= 255) { put(255); put(cmd); put((uint8_t)d.size()); put((uint8_t)(d.size() >> 8)); } else { put((uint8_t)d.size()); put(cmd); }
    for (uint8_t b : d) put(b); f.push_back(crc); return f;
}
int main() {
    uint8_t out[700];
    // 1. a bare request (MSP 101) = $M< 00 65 65
    uint16_t n = mspSerialEncode(out, sizeof out, 101, nullptr, 0);
    check(n == 6 && out[0]=='$' && out[1]=='M' && out[2]=='<' && out[3]==0 && out[4]==101 && out[5]==(0^101), "encode MSP 101 no payload");
    // 2. a request with payload: MSP 210 data 01  → size 1, cmd 210, crc = 1 ^ 210 ^ 1
    uint8_t one = 1; n = mspSerialEncode(out, sizeof out, 210, &one, 1);
    check(n == 7 && out[3]==1 && out[4]==210 && out[5]==1 && out[6]==(uint8_t)(1^210^1), "encode MSP 210 [01]");
    // 3. an 84-byte payload (Scorpion ESC write) round-trips through a parser (as if echoed)
    std::vector<uint8_t> big(84); for (int i = 0; i < 84; i++) big[i] = (uint8_t)(i * 7);
    MspSerialParser P; Got g;
    auto f = reply(218, big); for (uint8_t b : f) P.feed(b, onFrame, &g);
    check(g.calls == 1 && g.cmd == 218 && g.p == big && !g.err, "parse 84-byte reply");
    // 4. jumbo reply (588 bytes, MSP 52 style)
    std::vector<uint8_t> jb(588); for (int i = 0; i < 588; i++) jb[i] = (uint8_t)(i * 3 + 1);
    g = Got(); f = reply(52, jb); for (uint8_t b : f) P.feed(b, onFrame, &g);
    check(g.calls == 1 && g.cmd == 52 && g.p == jb, "parse 588-byte jumbo reply");
    // 5. error reply
    g = Got(); f = reply(217, {}, true); for (uint8_t b : f) P.feed(b, onFrame, &g);
    check(g.calls == 1 && g.cmd == 217 && g.err && g.p.empty(), "parse error reply ($M!)");
    // 6. garbage + bad CRC then a good frame: resyncs
    g = Got(); for (uint8_t b : std::vector<uint8_t>{ 0x00, 0xFF, '$', 'M', '>', 1, 101, 9, 0x00 }) P.feed(b, onFrame, &g);
    f = reply(101, { 1, 2, 3 }); for (uint8_t b : f) P.feed(b, onFrame, &g);
    check(g.calls == 1 && g.cmd == 101 && g.p.size() == 3 && P.badCrc == 1, "resync after garbage and a bad crc");
    // 7. two frames back to back, split anywhere
    g = Got(); auto a = reply(1, { 9 }); auto b2 = reply(2, { 8, 7 }); a.insert(a.end(), b2.begin(), b2.end());
    for (uint8_t b : a) P.feed(b, onFrame, &g);
    check(g.calls == 2 && g.cmd == 2 && g.p.size() == 2, "two frames back to back");
    printf(fails ? "FAILURES: %d\n" : "ALL PASS\n", fails); return fails ? 1 : 0;
}
