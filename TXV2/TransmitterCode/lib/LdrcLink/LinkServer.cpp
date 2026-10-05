#include "LinkServer.h"
#include <string.h>
#include <stdio.h>

namespace ldrc {

uint8_t checkFirmwarePackage(LinkFs &fs, LinkPlatform &pf, const char *path, const char *target, uint32_t maxSize, FwHeader &header) {
    const int h = fs.open(path, false);
    if (h < 0) return LE_NO_FILE;
    uint8_t raw[FW_HEADER_SIZE];
    if (fs.read(h, raw, FW_HEADER_SIZE) != (int) FW_HEADER_SIZE || !fwHeaderParse(raw, header)) { fs.close(h); return LE_BAD_IMAGE; }
    if (strcmp(header.target, target) != 0) { fs.close(h); return LE_BAD_IMAGE; }
    if (header.size < 32768 || header.size > maxSize || (header.size & 3) != 0 || fs.size(h) != FW_HEADER_SIZE + header.size) { fs.close(h); return LE_SIZE; }
    uint8_t buf[512]; uint32_t crc = 0, left = header.size; int turns = 0; bool named = false;
    const size_t tl = strlen(target); size_t matched = 0;
    while (left) {
        const uint32_t want = left > sizeof buf ? (uint32_t) sizeof buf : left;
        if (fs.read(h, buf, want) != (int) want) { fs.close(h); return LE_IO; }
        crc = crc32(buf, want, crc); left -= want;
        for (uint32_t i = 0; i < want && !named; ++i) {                 // the image itself must carry the target's name
            if (buf[i] == (uint8_t) target[matched]) { if (++matched == tl) named = true; }
            else matched = (buf[i] == (uint8_t) target[0]) ? 1 : 0;
        }
        if ((++turns & 63) == 0) pf.busy();
    }
    fs.close(h);
    if (crc != header.crc) return LE_CRC;
    if (!named) return LE_BAD_IMAGE;
    return LE_OK;
}

LinkServer::LinkServer(LinkFs &fs, LinkPlatform &pf) : fs_(fs), pf_(pf), wr_(-1), rd_(-1), wrSize_(0), wrCrc_(0), wrGot_(0), wrRun_(0), wrLastLen_(0), rdSize_(0), userDataChanged_(false) { wrPath_[0] = 0; }

void LinkServer::abandon() {
    if (wr_ >= 0) { fs_.close(wr_); wr_ = -1; fs_.remove(tempName()); }
    if (rd_ >= 0) { fs_.close(rd_); rd_ = -1; }
}

void LinkServer::makeFolders(const char *path) {
    char part[LINK_MAX_PATH];
    for (size_t i = 1; path[i]; ++i) {
        if (path[i] != '/') continue;
        memcpy(part, path, i); part[i] = 0;
        if (!fs_.exists(part)) fs_.mkdir(part);
    }
}

bool LinkServer::fileCrc(const char *path, uint32_t &size, uint32_t &crc) {
    const int h = fs_.open(path, false);
    if (h < 0) return false;
    uint8_t buf[512]; size = 0; crc = 0; int n, turns = 0;
    while ((n = fs_.read(h, buf, sizeof buf)) > 0) { crc = crc32(buf, (size_t) n, crc); size += (uint32_t) n; if ((++turns & 63) == 0) pf_.busy(); }
    fs_.close(h);
    return n == 0;
}

void LinkServer::hello(Frame &reply, uint8_t seq) {
    reply.clear(LK_REPLY | LK_HELLO, seq);
    reply.put8(LE_OK);
    char text[236];                                                 // (the screen reads it into 240)
    const char *extra = pf_.extra();
    snprintf(text, sizeof text, "proto=%u;fw=%s;target=%s;state=%s;starts=%d;up=%lu;card=%d;block=%u%s%s",
             (unsigned) LINK_PROTO, pf_.firmwareVersion(), pf_.target(), pf_.updateState(), pf_.startsOnTrial(), (unsigned long) pf_.uptimeSeconds(),
             fs_.present() ? 1 : 0, (unsigned) LINK_BLOCK, (extra && extra[0]) ? ";" : "", (extra && extra[0]) ? extra : "");
    reply.putText(text);
}

LinkAction LinkServer::handle(const Frame &req, Frame &reply) {
    reply.clear((uint8_t) (LK_REPLY | req.type), req.seq);
    char path[LINK_MAX_PATH];
    #define FAIL(code) do { reply.len = 0; reply.put8(code); return LA_NONE; } while (0)

    switch (req.type) {
    case LK_HELLO:
        hello(reply, req.seq);
        return LA_NONE;

    case LK_BYE:
        abandon();
        reply.put8(LE_OK);
        return LA_LEAVE;

    case LK_STAT: {
        if (!req.getText(0, path, sizeof path) || !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        uint32_t size = 0, crc = 0;
        const bool there = fs_.exists(path) && fileCrc(path, size, crc);
        reply.put8(LE_OK); reply.put8(there ? 1 : 0); reply.put32(size); reply.put32(crc);
        return LA_NONE;
    }

    case LK_LIST: {
        if (req.len < 4 || !req.getText(4, path, sizeof path)) FAIL(LE_BAD_REQUEST);
        if (!(path[0] == '/' && path[1] == 0) && !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        const bool root = path[0] == '/' && path[1] == 0;
        if (!root && !fs_.exists(path)) FAIL(LE_NO_FILE);           // no such folder (which is not the same as an empty one, nor as one that cannot be read)
        uint32_t index = req.get32(0);
        reply.put8(LE_OK);
        const size_t countAt = reply.len; reply.put8(0); reply.put8(0);
        uint8_t count = 0; bool more = false;
        for (;;) {
            char name[256]; uint32_t size = 0; bool isDir = false;  // (FAT's long names: 255. It was 64, and a longer name was cut: listed, never fetched)
            const int got = fs_.entry(path, index, name, sizeof name, size, isDir);
            if (got < 0) FAIL(LE_IO);
            if (got == 0) break;
            if (reply.len + 5u + strlen(name) + 1u > LINK_MAX_PAYLOAD || count == 255) { more = true; break; }
            reply.put32(size); reply.put8(isDir ? 1 : 0); reply.putText(name); reply.put8(0);
            count++; index++;
        }
        reply.payload[countAt] = count; reply.payload[countAt + 1] = more ? 1 : 0;
        return LA_NONE;
    }

    case LK_MKDIR:
        if (!req.getText(0, path, sizeof path) || !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        makeFolders(path);
        if (!fs_.exists(path) && !fs_.mkdir(path)) FAIL(LE_IO);
        reply.put8(LE_OK);
        return LA_NONE;

    case LK_DELETE:
        if (req.len < 1 || !req.getText(1, path, sizeof path) || !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        if (isUserData(path) && !(req.get8(0) & LF_USER_DATA)) FAIL(LE_PROTECTED);
        if (!fs_.exists(path)) FAIL(LE_NO_FILE);
        if (!fs_.remove(path)) FAIL(LE_IO);
        if (isUserData(path)) userDataChanged_ = true;
        reply.put8(LE_OK);
        return LA_NONE;

    case LK_WRITE_BEGIN:
        if (req.len < 9 || !req.getText(9, path, sizeof path) || !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        if (isUserData(path) && !(req.get8(0) & LF_USER_DATA)) FAIL(LE_PROTECTED);
        if (wr_ >= 0) { fs_.close(wr_); wr_ = -1; }
        fs_.remove(tempName());
        wr_ = fs_.open(tempName(), true);
        if (wr_ < 0) FAIL(LE_IO);
        strcpy(wrPath_, path);
        wrSize_ = req.get32(1); wrCrc_ = req.get32(5); wrGot_ = 0; wrRun_ = 0; wrLastLen_ = 0;
        reply.put8(LE_OK);
        return LA_NONE;

    case LK_WRITE_DATA: {
        if (req.len < 4) FAIL(LE_BAD_REQUEST);
        if (wr_ < 0) FAIL(LE_SEQUENCE);
        const uint32_t offset = req.get32(0), n = (uint32_t) req.len - 4u;
        if (offset == wrGot_) {
            if (wrGot_ + n > wrSize_) FAIL(LE_SIZE);
            if (n && fs_.write(wr_, req.payload + 4, n) != (int) n) { abandon(); FAIL(LE_IO); }
            wrRun_ = crc32(req.payload + 4, n, wrRun_);
            wrGot_ += n; wrLastLen_ = n;
        } else if (!(offset + n == wrGot_ && n == wrLastLen_)) {   // (the block we already have, sent again because our answer was lost, is fine)
            reply.put8(LE_SEQUENCE); reply.put32(wrGot_);           // tell the screen where we are
            return LA_NONE;
        }
        reply.put8(LE_OK); reply.put32(wrGot_);
        return LA_NONE;
    }

    case LK_WRITE_END: {
        if (wr_ < 0) {                                              // our answer to an earlier END may have been lost: is the file there, whole?
            uint32_t size = 0, crc = 0;
            if (wrPath_[0] && fileCrc(wrPath_, size, crc) && size == wrSize_ && crc == wrCrc_) { reply.put8(LE_OK); reply.put32(size); reply.put32(crc); return LA_NONE; }
            FAIL(LE_SEQUENCE);
        }
        fs_.close(wr_); wr_ = -1;
        if (wrGot_ != wrSize_) { fs_.remove(tempName()); FAIL(LE_SIZE); }
        if (wrRun_ != wrCrc_) { fs_.remove(tempName()); FAIL(LE_CRC); }
        uint32_t size = 0, crc = 0;                                 // what the CARD holds, not what we were sent
        if (!fileCrc(tempName(), size, crc)) { fs_.remove(tempName()); FAIL(LE_IO); }
        if (size != wrSize_ || crc != wrCrc_) { fs_.remove(tempName()); FAIL(LE_CRC); }
        makeFolders(wrPath_);
        {   // The file it replaces is moved aside, not removed, until the new one is in its place: if the new one
            // cannot be put there, the old one goes back. (Removed first, a failed rename left NEITHER.)
            const bool was = fs_.exists(wrPath_);
            if (was) {
                if (fs_.exists(asideName())) fs_.remove(asideName());
                if (!fs_.rename(wrPath_, asideName())) { fs_.remove(tempName()); FAIL(LE_IO); }
            }
            if (isUserData(wrPath_)) userDataChanged_ = true;       // from here on the card may differ from what the transmitter holds in memory
            if (!fs_.rename(tempName(), wrPath_)) {
                const bool back = was && fs_.rename(asideName(), wrPath_);
                fs_.remove(tempName());
                if (was && !back) FAIL(LE_IO);                      // (the old file is still on the card, as /LINK.OLD)
                FAIL(LE_IO);
            }
            if (was) fs_.remove(asideName());
        }
        reply.put8(LE_OK); reply.put32(size); reply.put32(crc);
        return LA_NONE;
    }

    case LK_READ_BEGIN: {
        if (!req.getText(0, path, sizeof path) || !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        if (rd_ >= 0) { fs_.close(rd_); rd_ = -1; }
        if (!fs_.exists(path)) FAIL(LE_NO_FILE);
        uint32_t crc = 0;
        if (!fileCrc(path, rdSize_, crc)) FAIL(LE_IO);
        rd_ = fs_.open(path, false);
        if (rd_ < 0) FAIL(LE_IO);
        reply.put8(LE_OK); reply.put32(rdSize_); reply.put32(crc);
        return LA_NONE;
    }

    case LK_READ_DATA: {
        if (req.len < 6) FAIL(LE_BAD_REQUEST);
        if (rd_ < 0) FAIL(LE_SEQUENCE);
        const uint32_t offset = req.get32(0); uint32_t want = req.get16(4);
        if (want > LINK_BLOCK) want = LINK_BLOCK;
        if (offset > rdSize_) FAIL(LE_SIZE);
        if (offset + want > rdSize_) want = rdSize_ - offset;
        reply.put8(LE_OK); reply.put32(offset);
        if (want) {
            if (!fs_.seek(rd_, offset)) FAIL(LE_IO);
            const int n = fs_.read(rd_, reply.payload + reply.len, want);
            if (n != (int) want) FAIL(LE_IO);
            reply.len = (uint16_t) (reply.len + want);
        }
        return LA_NONE;
    }

    case LK_FW_INSTALL: {
        if (!req.getText(0, path, sizeof path) || !goodPath(path)) FAIL(LE_BAD_REQUEST);
        if (!fs_.present()) FAIL(LE_NO_CARD);
        abandon();
        const uint8_t e = pf_.stageFirmware(path);
        reply.put8(e);
        return e == LE_OK ? LA_SWAP_AND_RESTART : LA_NONE;
    }

    case LK_FW_ROLLBACK: {
        if (!fs_.present()) FAIL(LE_NO_CARD);
        abandon();
        const uint8_t e = pf_.stagePrevious();
        reply.put8(e);
        return e == LE_OK ? LA_SWAP_AND_RESTART : LA_NONE;
    }

    case LK_FW_CONFIRM:
        pf_.confirmFirmware();
        reply.put8(LE_OK);
        return LA_NONE;

    default:
        FAIL(LE_UNSUPPORTED);
    }
    #undef FAIL
}

}  // namespace ldrc
