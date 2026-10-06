#include "LdrcBle.h"
#include <cstdio>
#include <cstdlib>

namespace ldrc {

std::vector<std::string> BleBridge::frames(const std::string &method, const std::string &path, const std::string &body, uint32_t id, int chunk, const std::string &contentType) {
    std::string payload = method + " " + path + "\nX-Req: " + std::to_string(id) + "\n";
    if (!contentType.empty()) payload += "Content-Type: " + contentType + "\n";
    payload += "\n" + body;
    std::vector<std::string> out;
    const std::string first = "Q" + std::to_string(payload.size()) + "|";
    size_t at = 0, room = chunk > (int) first.size() + 1 ? chunk - first.size() : 1;
    out.push_back(first + payload.substr(0, room)); at = std::min(payload.size(), room);
    while (at < payload.size()) { const size_t n = std::min(payload.size() - at, (size_t) (chunk > 1 ? chunk - 1 : 1)); out.push_back("+" + payload.substr(at, n)); at += n; }
    return out;
}

void BleBridge::reset() { header_ = true; head_.clear(); bodyLen_ = 0; body_.clear(); reply_ = BleReply(); mine_ = false; }

bool BleBridge::feed(const uint8_t *data, size_t len, uint32_t wantId) {
    if (header_) {
        head_.append((const char *) data, len);
        const size_t r = head_.find('R');             // (bytes before a header: the tail of a reply given up on; dropped)
        if (r == std::string::npos) { head_.clear(); return false; }
        if (r > 0) head_.erase(0, r);
        const size_t nl = head_.find('\n');
        if (nl == std::string::npos) return false;
        // "R200|application/json|1234|#17"
        const std::string h = head_.substr(0, nl); const std::string rest = head_.substr(nl + 1);
        if (h.empty() || h[0] != 'R') { head_.clear(); return false; }   // (not a reply header: a stray chunk of an earlier body)
        size_t p1 = h.find('|'), p2 = p1 == std::string::npos ? p1 : h.find('|', p1 + 1), p3 = p2 == std::string::npos ? p2 : h.find('|', p2 + 1);
        if (p3 == std::string::npos) { head_.clear(); return false; }
        reply_ = BleReply();
        reply_.code = atoi(h.substr(1, p1 - 1).c_str()); reply_.type = h.substr(p1 + 1, p2 - p1 - 1);
        bodyLen_ = (size_t) strtoul(h.substr(p2 + 1, p3 - p2 - 1).c_str(), nullptr, 10); reply_.location = h.substr(p3 + 1);
        mine_ = reply_.location == "#" + std::to_string(wantId) || reply_.location.empty() || reply_.location[0] != '#';   // (a redirect names a page, not an id: it is ours)
        header_ = false; head_.clear(); body_.clear(); body_.reserve(bodyLen_);
        if (!rest.empty()) body_.append(rest.substr(0, bodyLen_));
    } else {
        const size_t n = std::min(len, bodyLen_ - body_.size());
        body_.append((const char *) data, n);
    }
    if (body_.size() < bodyLen_) return false;
    header_ = true;                                // the next notification starts a new reply
    if (!mine_) { body_.clear(); bodyLen_ = 0; return false; }
    reply_.body = body_; body_.clear(); bodyLen_ = 0;
    return true;
}

}  // namespace ldrc
