// LinkServer — the Teensy's end of LdrcLink: files on its SD card, and its own firmware.
// Portable: the card and the chip are reached through LinkFs and LinkPlatform, so the host tests
// run this very code against a folder on the Mac.
#ifndef LDRC_LINK_SERVER_H
#define LDRC_LINK_SERVER_H

#include "LdrcLink.h"

namespace ldrc {

class LinkFs {                                    // the SD card
public:
    virtual ~LinkFs() {}
    virtual bool present() = 0;
    virtual bool exists(const char *path) = 0;
    virtual bool remove(const char *path) = 0;
    virtual bool rename(const char *from, const char *to) = 0;
    virtual bool mkdir(const char *path) = 0;
    virtual int  open(const char *path, bool forWriting) = 0;      // a handle (>= 0), or -1. Writing starts an empty file.
    virtual int  read(int handle, uint8_t *buf, size_t n) = 0;     // bytes read, 0 at the end, -1 on error
    virtual int  write(int handle, const uint8_t *buf, size_t n) = 0;
    virtual bool seek(int handle, uint32_t pos) = 0;
    virtual uint32_t size(int handle) = 0;
    virtual void close(int handle) = 0;
    // The index-th entry of a folder: 1 = here it is, 0 = there is none (the end of the folder),
    // -1 = the folder cannot be read. (A folder that cannot be read is NOT an empty folder: the pilot's files
    // may be in it, and "nothing to keep" would be a lie.)
    virtual int entry(const char *dir, uint32_t index, char *name, size_t nameSize, uint32_t &size, bool &isDir) = 0;
};

class LinkPlatform {                              // the chip
public:
    virtual ~LinkPlatform() {}
    virtual const char *firmwareVersion() = 0;
    virtual const char *target() = 0;             // "fw_teensy41"
    virtual const char *updateState() = 0;        // "confirmed" | "trial" | "rolledback"
    virtual uint32_t uptimeSeconds() { return 0; }
    virtual int startsOnTrial() { return 0; }     // how many times the firmware on trial has started
    // Check a firmware package on the card, keep a copy of the firmware now running, put the new one
    // in the spare half of the flash and read it back. LE_OK means only the swap remains.
    virtual uint8_t stageFirmware(const char *path) = 0;
    virtual uint8_t stagePrevious() = 0;          // the same, for the firmware kept at the last update
    virtual void confirmFirmware() = 0;
    virtual void busy() = 0;                      // called during long work: the watchdog wants feeding
    // More for the hello, as key=value;key=value (no ';' at either end), or nothing. The Teensy says how it reads
    // the model's settings (mfp=) and what it is doing (st=): see FlightGuard.h.
    virtual const char *extra() { return ""; }
};

enum LinkAction { LA_NONE = 0, LA_SWAP_AND_RESTART = 1, LA_LEAVE = 2 };

// Is the file at `path` a firmware package for `target`, whole and unharmed, and no bigger than maxSize?
// LE_OK and the header, or the reason why not. Reads the whole file once.
uint8_t checkFirmwarePackage(LinkFs &fs, LinkPlatform &pf, const char *path, const char *target, uint32_t maxSize, FwHeader &header);

class LinkServer {
public:
    LinkServer(LinkFs &fs, LinkPlatform &pf);
    void hello(Frame &reply, uint8_t seq);        // what the Teensy says on entering the link, and to LK_HELLO
    // Answer one request. What the caller must do AFTER the answer has gone out is returned.
    LinkAction handle(const Frame &req, Frame &reply);
    void abandon();                               // the link was lost: close what is open, drop the half-written file
    // One of the pilot's own files (models.dat, a model file, a log) has been replaced or removed in this link.
    // What the transmitter holds in memory no longer agrees with its card: it must save nothing, and restart.
    bool userDataChanged() const { return userDataChanged_; }

    static bool goodPath(const char *path) { return plainPath(path); }
    static const char *tempName() { return "/LINK.TMP"; }
    static const char *asideName() { return "/LINK.OLD"; }      // the file being replaced, until its successor is in place

private:
    bool fileCrc(const char *path, uint32_t &size, uint32_t &crc);
    void makeFolders(const char *path);
    LinkFs &fs_; LinkPlatform &pf_;
    int wr_, rd_;                                 // open handles, -1 when none
    char wrPath_[LINK_MAX_PATH];
    uint32_t wrSize_, wrCrc_, wrGot_, wrRun_, wrLastLen_;
    uint32_t rdSize_;
    bool userDataChanged_;
};

// The Teensy in the link, byte by byte: frames in, answers out, the hello said again if the screen
// knocks again (it did not hear the first), and an end to it after LINK_IDLE_MS of silence.
const uint32_t LINK_IDLE_MS = 30000;
class LinkSession {
public:
    explicit LinkSession(LinkServer &server) : server_(server), lastFrame_(0) {}
    void begin(uint32_t nowMs, Frame &helloOut) { parser_.reset(); knock_.reset(); lastFrame_ = nowMs; server_.hello(helloOut, 0); }
    // true: `reply` is to be sent, then `action` carried out
    bool byte(uint8_t b, uint32_t nowMs, Frame &reply, LinkAction &action) {
        action = LA_NONE;
        const bool inFrame = parser_.midFrame();
        if (parser_.push(b, req_, nowMs)) { knock_.reset(); lastFrame_ = nowMs; action = server_.handle(req_, reply); return true; }
        if (!inFrame && !parser_.midFrame() && knock_.push(b)) { lastFrame_ = nowMs; server_.hello(reply, 0); return true; }
        return false;
    }
    bool expired(uint32_t nowMs) const { return nowMs - lastFrame_ > LINK_IDLE_MS; }
    void touch(uint32_t nowMs) { lastFrame_ = nowMs; }
private:
    LinkServer &server_; Parser parser_; Knock knock_; Frame req_; uint32_t lastFrame_;
};

}  // namespace ldrc
#endif
