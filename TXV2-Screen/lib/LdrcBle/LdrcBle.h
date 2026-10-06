// The receiver's Bluetooth bridge, as the screen speaks it (screen 1.11.0, 2026-10-06; Malcolm: the Rotorflight
// editing "should go via Bluetooth rather than the current method which can be removed"). The receiver (RXV2
// src/BleConfig.h) serves its web handlers over one GATT service: the client writes a framed request to REQ and the
// reply comes back on RESP as notifications. This file is the framing only, portable and tested on the Mac
// (hmi/test_ble); the radio itself is src/ble_device.h.
//
//   request:   'Q' <total length, decimal> '|' <payload ...>   then   '+' <more payload>   until the length is reached
//   payload:   METHOD SP path '\n' { header ':' value '\n' } '\n' body
//   reply:     'R' code '|' type '|' body length '|' location '\n'   then the body, in notifications of up to the MTU
//
// Every request carries "X-Req: n"; a reply that is not a redirect carries "#n" in its location slot (receiver 0.9.746):
// a late reply to an earlier request is told from the one being waited for.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace ldrc {

static const char *BLE_SVC_UUID = "8e400001-f315-4f60-9fb8-838830daea50";
static const char *BLE_REQ_UUID = "8e400002-f315-4f60-9fb8-838830daea50";
static const char *BLE_RESP_UUID = "8e400003-f315-4f60-9fb8-838830daea50";
static const int BLE_WRITE_CHUNK = 240;            // bytes per write (the apps' lesson: 240 is what every stack carries)

struct BleReply { int code = 0; std::string type, body, location; };

class BleBridge {
public:
    // The writes for one request, each at most `chunk` bytes. The id goes in as "X-Req".
    static std::vector<std::string> frames(const std::string &method, const std::string &path, const std::string &body, uint32_t id, int chunk = BLE_WRITE_CHUNK, const std::string &contentType = "");
    // Feed every notification in. True once a whole reply is in (reply()); a reply for another id is dropped and false stays.
    bool feed(const uint8_t *data, size_t len, uint32_t wantId);
    void reset();                                  // forget a half reply (a new request is going out)
    const BleReply &reply() const { return reply_; }
    bool waiting() const { return !header_ || !head_.empty(); }   // a reply is partly in
private:
    bool header_ = true; std::string head_; size_t bodyLen_ = 0; std::string body_; BleReply reply_; bool mine_ = false;
};

// The receiver's /api/txparams reply, '{"block":"rates","open":true,"items":{"25":"AABBCCDD","26":"EEFF0011"}}', as
// the word for the main board: "ldrctel 25:AABBCCDD 26:EEFF0011" ("" when the block has no items yet).
std::string bleItemsWord(const std::string &json);

}  // namespace ldrc
