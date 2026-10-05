#include "LinkMaster.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace ldrc {

static std::string kb(uint32_t n) { char b[24]; if (n < 10240) snprintf(b, sizeof b, "%lu bytes", (unsigned long) n); else snprintf(b, sizeof b, "%lu kB", (unsigned long) ((n + 512) / 1024)); return b; }
static std::string num(uint32_t n) { char b[16]; snprintf(b, sizeof b, "%lu", (unsigned long) n); return b; }

LinkMaster::LinkMaster(MasterPort &port, MasterFiles &files)
    : port_(port), files_(files), state_(S_IDLE), step_(0), phase_(0), seq_(0), awaiting_(false), sentAt_(0), timeout_(0), triesLeft_(0), resends_(0),
      startedAt_(0), knockAt_(0), knocks_(0), knockLimit_(6), listening_(false), trafficSeen_(false), trafficAt_(0), waitFrom_(0), settleMs_(0),
      linkOpen_(false), refusal_(LE_OK), peerLeft_(false), resyncs_(0),
      local_(-1), fileSize_(0), fileCrc_(0), fileDone_(0), runCrc_(0), listIndex_(0), kept_(0), held_(0),
      verify_(-1), verifyWhat_(0), verifySize_(0), verifyCrc_(0), heldKnown_(false), heldSize_(0), heldCrc_(0), prefixCrc_(0), undoing_(false), changed_(false), noted_(0) { inChild_ = false; childAt_ = childrenDone_ = childrenTotal_ = 0; }

static bool endsAs(const std::string &name, const std::string &ending) {        // whatever the case of the letters
    if (ending.size() > name.size()) return false;
    for (size_t i = 0; i < ending.size(); ++i) {
        char a = name[name.size() - ending.size() + i], b = ending[i];
        if (a >= 'a' && a <= 'z') a = (char) (a - 32);
        if (b >= 'a' && b <= 'z') b = (char) (b - 32);
        if (a != b) return false;
    }
    return true;
}

bool LinkMaster::add(Kind kind, const std::string &local, const std::string &remote, const std::string &expect, uint8_t flags, bool option, uint32_t ms) {
    if (running()) return false;                  // a job is its caller's alone: nothing joins it
    Step s; s.kind = kind; s.local = local; s.remote = remote; s.expect = expect; s.flags = flags; s.option = option; s.ms = ms;
    steps_.push_back(s);
    return true;
}
void LinkMaster::clear() { if (!running()) { steps_.clear(); step_ = 0; } }
void LinkMaster::put(const std::string &local, const std::string &remote, uint8_t flags, bool onlyIfDifferent) { add(K_PUT, local, remote, "", flags, onlyIfDifferent); }
void LinkMaster::get(const std::string &remote, const std::string &local, bool optional) { add(K_GET, local, remote, "", 0, optional); }
void LinkMaster::del(const std::string &remote, uint8_t flags) { add(K_DEL, "", remote, "", flags); }
void LinkMaster::keepFolder(const std::string &remoteDir, const std::string &localDir, const std::string &ending, uint32_t maxBytes, bool onlyNew) { if (add(K_LIST, localDir, remoteDir, ending, 0, false, maxBytes)) steps_.back().onlyNew = onlyNew; }
void LinkMaster::mustHold(const std::string &remote, const std::string &local) { add(K_HOLD, local, remote); }
void LinkMaster::list(const std::string &remoteDir) { add(K_LIST, "", remoteDir, "", 0, true); }
void LinkMaster::hello() { add(K_HELLO); }
void LinkMaster::confirm() { add(K_CONFIRM); }
void LinkMaster::rollback() {
    add(K_ROLLBACK);
    add(K_AWAIT_RESTART);
    if (add(K_CHECK)) steps_.back().back = true;                      // (asked for: how it reads the settings is compared and said, nothing is undone)
}
void LinkMaster::install(const std::string &remotePackage, const std::string &expectVersion) {
    add(K_INSTALL, "", remotePackage, expectVersion);
    add(K_AWAIT_RESTART);
    add(K_CHECK, "", "", expectVersion);                              // it is the new version ...
    add(K_SETTLE, "", "", "", 0, false, TRIAL_WAIT_MS);               // ... let it be a transmitter for its trial ...
    add(K_CHECK, "", "", expectVersion, 0, true);                     // ... and it must have accepted itself (option = must be confirmed)
}

void LinkMaster::note(const std::string &line) {
    char t[16]; snprintf(t, sizeof t, "%6.1f s  ", (port_.ms() - startedAt_) / 1000.0);
    log_.push_back(std::string(t) + line); noted_++;
    // A long job (700 logs) must not push out how it BEGAN: the first 40 lines stay, the middle goes.
    if (log_.size() > 240) { log_.erase(log_.begin() + 41); log_[40] = "          ... (lines left out here: the record keeps its first 40 and its last 200) ..."; }
}
void LinkMaster::warn(const std::string &line) {
    note(line);
    if (warnings_.size() < 40) warnings_.push_back(line);
    else if (warnings_.size() == 40) warnings_.push_back("... and more: see the record");
}
void LinkMaster::closeLocal() { if (local_ >= 0) { files_.close(local_); local_ = -1; } }
bool LinkMaster::holds(const std::string &path) { const int h = files_.open(path.c_str(), false); if (h < 0) return false; files_.close(h); return true; }

// `from` takes the place of `to`. What was at `to` is moved aside first and removed last: if `from` cannot be put
// there, it goes back. (Removed first, a rename that failed left neither.)
bool LinkMaster::putInPlace(const std::string &from, const std::string &to) {
    const std::string aside = to + ".old";
    const bool was = holds(to);
    if (was) { files_.remove(aside.c_str()); if (!files_.rename(to.c_str(), aside.c_str())) return false; }
    if (!files_.rename(from.c_str(), to.c_str())) { if (was) files_.rename(aside.c_str(), to.c_str()); return false; }
    if (was) files_.remove(aside.c_str());
    return true;
}

void LinkMaster::fail(const std::string &why) {
    closeLocal();
    if (verify_ >= 0) { files_.close(verify_); verify_ = -1; }
    if ((inChild_ || (step_ < steps_.size() && steps_[step_].kind == K_GET)) && !writing_.empty()) files_.remove(writing_.c_str());   // no half files (and the copy we held, if any, stays)
    writing_.clear();
    result_ = "FAILED at " + stage_ + ": " + why;
    note(result_);
    awaiting_ = false; listening_ = false;
    // Frames go ONLY into an open link: to a Teensy running as a transmitter they would look like touches.
    if (linkOpen_ && !peerLeft_) { static Frame bye; bye.clear(LK_BYE, (uint8_t) (seq_ + 1)); static uint8_t raw[LINK_MAX_FRAME]; port_.write(raw, encode(bye, raw)); }
    linkOpen_ = false;
    state_ = S_FAILED;
}
void LinkMaster::cancel(const char *why) { if (running()) fail(why); }

void LinkMaster::finish() {
    state_ = S_DONE; linkOpen_ = false; awaiting_ = false; listening_ = false;
    result_ = "DONE";
    for (size_t i = 0; i < steps_.size(); ++i) if (steps_[i].kind == K_CHECK) result_ = "DONE: the transmitter runs " + peerValue("fw");
    note(result_);
}

bool LinkMaster::copiesDone() const {
    if (state_ == S_DONE) return true;
    if (running() && step_ == 0) return false;
    for (size_t i = step_; i < steps_.size(); ++i) if (steps_[i].kind == K_LIST || steps_[i].kind == K_HOLD || (steps_[i].kind == K_GET && steps_[i].keep)) return false;
    return step_ > 0;
}
int LinkMaster::peerStatus() const { const std::string v = peerValue("st"); return v.empty() ? -1 : atoi(v.c_str()); }

std::string LinkMaster::peerValue(const char *key) const {
    const std::string k = std::string(key) + "=";
    size_t at = 0;
    while (at < peer_.size()) {
        size_t end = peer_.find(';', at); if (end == std::string::npos) end = peer_.size();
        if (peer_.compare(at, k.size(), k) == 0) return peer_.substr(at + k.size(), end - at - k.size());
        at = end + 1;
    }
    return "";
}

void LinkMaster::knockNow(int limit) {
    state_ = S_KNOCK; knocks_ = 1; knockLimit_ = limit; knockAt_ = port_.ms();
    port_.knock();
}

bool LinkMaster::start() {
    if (running() || steps_.empty()) return false;
    log_.clear(); noted_ = 0; result_.clear(); peer_.clear();
    step_ = 0; phase_ = 0; resends_ = 0; awaiting_ = false; listening_ = false; local_ = -1; kept_ = 0; held_ = 0; entries_.clear(); writing_.clear();
    inChild_ = false; childAt_ = childrenDone_ = childrenTotal_ = 0; listed_.clear(); listedHeld_.clear(); changed_ = false;
    warnings_.clear(); verify_ = -1; heldKnown_ = false; fwBefore_.clear(); settingsBefore_.clear(); settingsRead_.clear(); undoing_ = false;
    linkOpen_ = false; peerLeft_ = false; refusal_ = LE_OK;
    startedAt_ = port_.ms();
    stage_ = "opening the link";
    knockNow(6);
    return true;
}

void LinkMaster::request(uint32_t timeoutMs, int tries) {
    req_.seq = ++seq_;
    static uint8_t raw[LINK_MAX_FRAME];           // (not on the stack: the screen's loop has 8 kB of it, and these calls nest)
    port_.write(raw, encode(req_, raw));
    awaiting_ = true; sentAt_ = port_.ms(); timeout_ = timeoutMs; triesLeft_ = tries - 1;
    state_ = S_AWAIT;
}

void LinkMaster::nextStep() {
    closeLocal();
    step_++; phase_ = 0;
    if (step_ >= steps_.size()) {
        if (!linkOpen_) { finish(); return; }
        stage_ = "closing the link";
        req_.clear(LK_BYE, 0); request(1000, 4); state_ = S_BYE;
        return;
    }
    beginStep();
}

void LinkMaster::beginSettle() {                  // the Teensy is a transmitter again: wait, then knock
    Step &s = steps_[step_];
    linkOpen_ = false; peerLeft_ = false;
    listening_ = true; waitFrom_ = port_.ms(); settleMs_ = s.ms;
    stage_ = "letting the new firmware run";
    state_ = S_SETTLE;
}

void LinkMaster::beginStep() {
    if (step_ >= steps_.size()) { step_ = steps_.size() ? steps_.size() - 1 : 0; nextStep(); return; }
    Step &s = steps_[step_];
    phase_ = 0; fileDone_ = 0; fileSize_ = 0; resyncs_ = 0;
    const bool needsLink = !(s.kind == K_HELLO || s.kind == K_CHECK || s.kind == K_SETTLE || s.kind == K_AWAIT_RESTART);
    if (needsLink && !linkOpen_) {
        if (undoing_) {                           // the firmware that reads the settings differently could not be undone: nothing is more important to say
            stage_ = "putting the previous firmware back";
            fail(std::string(errorText(refusal_ ? refusal_ : (uint8_t) LE_NOT_NOW)) + ", so the previous firmware could NOT be put back. " + peerValue("fw") + " is running, and it reads this model's settings DIFFERENTLY from " + fwBefore_ +
                 ". DO NOT FLY. Go back to the version before (Check for update, then Earlier versions), or CHECK EVERY CONTROL OF THE MODEL: directions, end points, mixes, switches");
            return;
        }
        fail(errorText(refusal_ ? refusal_ : (uint8_t) LE_NOT_NOW)); return;
    }
    switch (s.kind) {
    case K_PUT: {
        stage_ = "sending " + s.remote;
        local_ = files_.open(s.local.c_str(), false);
        if (local_ < 0) { fail("cannot open " + s.local + " on the screen's card"); return; }
        fileSize_ = files_.size(local_); fileCrc_ = 0;
        static uint8_t buf[1024]; int n;
        while ((n = files_.read(local_, buf, sizeof buf)) > 0) fileCrc_ = crc32(buf, (size_t) n, fileCrc_);
        if (n < 0) { fail("cannot read " + s.local); return; }
        if (s.option) { req_.clear(LK_STAT, 0); req_.putText(s.remote.c_str()); phase_ = 0; request(8000, 5); }
        else { req_.clear(LK_WRITE_BEGIN, 0); req_.put8(s.flags); req_.put32(fileSize_); req_.put32(fileCrc_); req_.putText(s.remote.c_str()); phase_ = 1; request(2000, 8); }
        return;
    }
    case K_GET:
        beginGet();
        return;
    case K_STOP:
        stage_ = s.remote;
        fail(s.expect);
        return;
    case K_HOLD:
        stage_ = "making sure of the copy of " + s.remote;
        req_.clear(LK_STAT, 0); req_.putText(s.remote.c_str()); request(8000, 5);
        return;
    case K_LIST:
        stage_ = "looking into " + s.remote;
        listIndex_ = 0; listed_.clear(); listedHeld_.clear();
        req_.clear(LK_LIST, 0); req_.put32(0); req_.putText(s.remote.c_str()); request(8000, 5);
        return;
    case K_DEL:
        stage_ = "removing " + s.remote;
        req_.clear(LK_DELETE, 0); req_.put8(s.flags); req_.putText(s.remote.c_str()); request(2000, 8);
        return;
    case K_HELLO:
        if (linkOpen_ && step_ > 0) { stage_ = "asking the transmitter"; req_.clear(LK_HELLO, 0); request(1500, 8); return; }   // things have been done since the knock: ask afresh
        note("transmitter: " + peer_ + (linkOpen_ ? "" : std::string(" (it keeps the link shut: ") + errorText(refusal_) + ")"));   // the knock has just been answered: that IS the answer
        nextStep();
        return;
    case K_CHECK: {
        stage_ = s.option ? "checking that the new firmware has stayed up" : "checking the new firmware";
        const std::string fw = peerValue("fw"), st = peerValue("state"); const int starts = atoi(peerValue("starts").c_str());
        std::string said = "the transmitter runs " + fw + " (" + st;
        if (starts > 1) { char b[40]; snprintf(b, sizeof b, ", started %d times", starts); said += b; }
        note(said + ")");
        if (!s.expect.empty() && fw != s.expect) {
            fail("it is running " + fw + ", not " + s.expect + (st == "rolledback" ? ": the new firmware did not stay up, and the transmitter put the previous firmware back by itself" : ""));
            return;
        }
        if (s.option && st != "confirmed") { fail("the new firmware is still on trial: it has not yet run for 30 seconds without restarting"); return; }
        if (!s.option) { compareSettings(); return; }             // fresh from its restart: does it read the model's settings as the firmware before it did?
        nextStep();
        return;
    }
    case K_INSTALL:
        stage_ = "installing " + s.remote;
        fwBefore_ = peerValue("fw"); settingsBefore_ = peerValue("mfp"); settingsRead_.clear();
        note("asking the transmitter to install " + s.remote + (s.expect.empty() ? "" : " (" + s.expect + ")"));
        req_.clear(LK_FW_INSTALL, 0); req_.putText(s.remote.c_str()); request(120000, 1);      // keeping the old firmware, staging and reading back the new one take a while; never asked twice
        return;
    case K_ROLLBACK:
        stage_ = "putting the previous firmware back";
        if (fwBefore_.empty()) { fwBefore_ = peerValue("fw"); settingsBefore_ = peerValue("mfp"); settingsRead_.clear(); }   // (asked for by itself, not as the undoing of an install)
        req_.clear(LK_FW_ROLLBACK, 0); request(120000, 1);
        return;
    case K_CONFIRM:
        stage_ = "accepting the firmware on trial";
        req_.clear(LK_FW_CONFIRM, 0); request(2000, 8);
        return;
    case K_AWAIT_RESTART:
        stage_ = "waiting for the transmitter to restart";
        linkOpen_ = false;                        // it is restarting: it will come back as a transmitter
        listening_ = true; trafficSeen_ = peerLeft_; trafficAt_ = port_.ms(); waitFrom_ = port_.ms();
        peerLeft_ = false;
        state_ = S_WAIT_RESTART;
        return;
    case K_SETTLE:
        // B18: firmware that has passed its trial on this transmitter before comes back "confirmed" at once: there is no
        // trial to wait for, and nothing to check after it (Malcolm, 1-10-2026: "only needed for the first installation").
        if (peerValue("state") == "confirmed") {
            note("this firmware has passed its trial on this transmitter before: no trial needed");
            if (step_ + 1 < steps_.size() && steps_[step_ + 1].kind == K_CHECK && steps_[step_ + 1].option) step_++;
            nextStep();
            return;
        }
        if (linkOpen_) { stage_ = "handing the transmitter back"; req_.clear(LK_BYE, 0); request(1000, 4); return; }
        beginSettle();
        return;
    }
}

void LinkMaster::sendNextBlock() {
    Step &s = steps_[step_];
    if (fileDone_ >= fileSize_) { req_.clear(LK_WRITE_END, 0); phase_ = 3; request(15000, 5); return; }
    static uint8_t buf[LINK_BLOCK];
    uint32_t want = fileSize_ - fileDone_; if (want > LINK_BLOCK) want = LINK_BLOCK;
    if (!files_.seek(local_, fileDone_) || files_.read(local_, buf, want) != (int) want) { fail("cannot read " + s.local); return; }
    req_.clear(LK_WRITE_DATA, 0); req_.put32(fileDone_); req_.putBytes(buf, want);
    phase_ = 2; request(1000, 10);
}
void LinkMaster::beginGet() {
    const Step &s = cur();
    stage_ = "fetching " + s.remote;
    phase_ = 0; fileDone_ = 0; fileSize_ = 0; resyncs_ = 0;
    heldKnown_ = false; heldSize_ = 0; heldCrc_ = 0; prefixCrc_ = 0; writing_.clear();
    if (s.check) { beginVerify(s.local, 0); return; }            // we hold a copy under that name: what is in it? THEN the Teensy is asked
    askToRead();
}
// The files of a folder that is kept are fetched one after the other, each in its turn the step in hand.
void LinkMaster::nextChild() {
    closeLocal();
    if (childAt_ >= listed_.size()) {                             // the folder is done
        inChild_ = false; listed_.clear(); listedHeld_.clear(); std::vector<std::string>().swap(listed_);
        nextStep();
        return;
    }
    child_ = Step(); child_.kind = K_GET; child_.keep = true;
    child_.local = childTo_ + "/" + listed_[childAt_]; child_.remote = childDir_ + "/" + listed_[childAt_]; child_.check = listedHeld_[childAt_];
    childAt_++; inChild_ = true;
    beginGet();
}
void LinkMaster::getDone() {                                      // a file has been dealt with
    if (inChild_) { childrenDone_++; nextChild(); }
    else nextStep();
}
void LinkMaster::askToRead() {
    const Step &s = cur();
    req_.clear(LK_READ_BEGIN, 0); req_.putText(s.remote.c_str()); phase_ = 0; request(8000, 5);
}

// A file of OUR card is read back, a piece at a time. what 0: the copy we hold, before the Teensy is asked for
// its file. what 1: the file that has just arrived, before it counts.
void LinkMaster::beginVerify(const std::string &path, int what) {
    verifyPath_ = path; verifyWhat_ = what; verifySize_ = 0; verifyCrc_ = 0;
    verify_ = files_.open(path.c_str(), false);
    if (verify_ < 0) { verified(false, 0, 0); return; }
    state_ = S_VERIFY;
}
void LinkMaster::verifySome() {
    static uint8_t buf[1024];
    for (int turn = 0; turn < 48; ++turn) {       // 48 kB at a time: some tens of milliseconds of the screen's card
        const int n = files_.read(verify_, buf, sizeof buf);
        if (n > 0) { verifyCrc_ = crc32(buf, (size_t) n, verifyCrc_); verifySize_ += (uint32_t) n; continue; }
        files_.close(verify_); verify_ = -1;
        verified(n == 0, verifySize_, verifyCrc_);
        return;
    }
}
void LinkMaster::verified(bool readable, uint32_t size, uint32_t crc) {
    state_ = S_STEP;
    if (verifyWhat_ == 0) {                       // the copy we hold
        heldKnown_ = readable; heldSize_ = size; heldCrc_ = crc;
        askToRead();
        return;
    }
    if (verifyWhat_ == 2) {                       // (K_HOLD) the copy that must be there
        const std::string remote = steps_[step_].remote;
        if (!readable) { fail(remote + " is on the transmitter's card, and there is no copy of it on the screen's. Nothing is changed"); return; }
        if (size != fileSize_ || crc != fileCrc_) { fail("the copy of " + remote + " on the screen's card is not the file on the transmitter's card. Nothing is changed"); return; }
        note("the copy of " + remote + " is the file on the transmitter's card (" + kb(size) + ", read back from both cards)");
        nextStep();
        return;
    }
    if (!readable || size != fileSize_ || crc != fileCrc_) {      // what the CARD holds, not what we were sent
        fail("the copy on the screen's card is not what the transmitter sent (" + (readable ? kb(size) + " of " + kb(fileSize_) : std::string("it cannot be read back")) + "). Is the screen's card full?");
        return;
    }
    copyArrived();
}

// The file is whole on our card, as <name>.part, read back and in agreement with the Teensy's checksum.
void LinkMaster::copyArrived() {
    const Step s = cur();                         // (a copy)
    std::string said = "fetched " + s.remote + " (" + kb(fileSize_) + ")";
    // It may take the place of the copy we hold ONLY if it begins with all of that copy (a log that has grown).
    const bool grown = s.check && heldKnown_ && fileSize_ >= heldSize_ && prefixCrc_ == heldCrc_;
    if (s.check && !grown && holds(s.local)) {
        std::string older;
        for (int n = 1; n < 10000; ++n) { older = s.local + ".older" + (n > 1 ? num((uint32_t) n) : std::string()); if (!holds(older)) break; }
        if (!files_.rename(s.local.c_str(), older.c_str())) { fail("cannot keep the copy held of " + s.local); return; }
        if (!files_.rename(writing_.c_str(), s.local.c_str())) { files_.rename(older.c_str(), s.local.c_str()); fail("cannot write " + s.local + " on the screen's card"); return; }
        said += ": it is not the file we held a copy of (it is smaller, or was begun again). That copy stays, as " + older;
    } else if (!putInPlace(writing_, s.local)) { fail("cannot write " + s.local + " on the screen's card"); return; }
    writing_.clear();
    note(said);
    if (s.keep) kept_++;
    getDone();
}

void LinkMaster::askNextBlock() {
    if (fileDone_ >= fileSize_) {
        closeLocal();
        if (runCrc_ != fileCrc_) { fail("what arrived does not match the transmitter's checksum"); return; }
        beginVerify(writing_, 1);
        return;
    }
    uint32_t want = fileSize_ - fileDone_; if (want > LINK_BLOCK) want = LINK_BLOCK;
    req_.clear(LK_READ_DATA, 0); req_.put32(fileDone_); req_.put16((uint16_t) want);
    phase_ = 2; request(1000, 10);
}

void LinkMaster::onReply(const Frame &f) {
    Step &s = cur();
    const uint8_t status = f.len ? f.payload[0] : LE_BAD_REQUEST;
    state_ = S_STEP;
    // "Out of sequence" anywhere but in the middle of a file is the answer of a Teensy that is a transmitter
    // again: it heard nothing for half a minute and left the link. It is not sent a goodbye: it is not there.
    if (status == LE_SEQUENCE && !(s.kind == K_PUT && phase_ == 2)) { linkOpen_ = false; fail("the transmitter had left the link (it heard nothing from the screen for too long)"); return; }

    // An answer shorter than the protocol says is not read as zeros (an "ok" of one byte to READ_BEGIN was a file of
    // no bytes, and the copy we held was replaced by it).
    #define SHORT(n) if (status == LE_OK && f.len < (n)) { fail("the transmitter's answer cannot be read (it is too short)"); return; }

    switch (s.kind) {
    case K_PUT:
        if (phase_ == 0) {                        // answer to STAT
            if (status != LE_OK) { fail(errorText(status)); return; }
            SHORT(10)
            if (f.get8(1) && f.get32(2) == fileSize_ && f.get32(6) == fileCrc_) { note(s.remote + " is already the same"); fileDone_ = fileSize_; nextStep(); return; }
            req_.clear(LK_WRITE_BEGIN, 0); req_.put8(s.flags); req_.put32(fileSize_); req_.put32(fileCrc_); req_.putText(s.remote.c_str());
            phase_ = 1; request(2000, 8); return;
        }
        if (phase_ == 1) { if (status != LE_OK) { fail(errorText(status)); return; } fileDone_ = 0; sendNextBlock(); return; }
        if (phase_ == 2) {
            if (status == LE_SEQUENCE && (f.len < 5 || ++resyncs_ > 8)) { fail("the transmitter lost its place in the file"); return; }
            SHORT(5)
            if (status == LE_OK || status == LE_SEQUENCE) { fileDone_ = f.get32(1); if (fileDone_ > fileSize_) { fail("the transmitter lost its place in the file"); return; } sendNextBlock(); return; }
            fail(errorText(status)); return;
        }
        if (status != LE_OK) { fail(errorText(status)); return; }
        SHORT(9)
        if (f.get32(1) != fileSize_ || f.get32(5) != fileCrc_) { fail("the transmitter's card does not hold what was sent"); return; }
        note("sent " + s.remote + " (" + kb(fileSize_) + ")"); changed_ = true;
        nextStep(); return;

    case K_GET:
        if (phase_ == 0) {
            if (status == LE_NO_FILE && s.option) { note(s.remote + " is not on the transmitter's card"); getDone(); return; }
            if (status == LE_NO_FILE && s.keep) { fail("the transmitter lists " + s.remote + " and cannot find it"); return; }
            if (status != LE_OK) { fail(errorText(status)); return; }
            SHORT(9)
            fileSize_ = f.get32(1); fileCrc_ = f.get32(5); fileDone_ = 0; runCrc_ = 0; prefixCrc_ = 0;
            if (s.check && heldKnown_ && heldSize_ == fileSize_ && heldCrc_ == fileCrc_) { held_++; getDone(); return; }   // the very file we hold
            writing_ = s.local + ".part";                        // nothing takes the place of what we hold before it has arrived whole
            local_ = files_.open(writing_.c_str(), true);
            if (local_ < 0) { writing_.clear(); fail("cannot write " + s.local + " on the screen's card"); return; }
            phase_ = 1; askNextBlock(); return;
        }
        if (status != LE_OK) { fail(errorText(status)); return; }
        SHORT(6)
        if (f.get32(1) != fileDone_) { askNextBlock(); return; }          // not the block we asked for: ask again
        {
            const uint32_t n = (uint32_t) f.len - 5u;
            if (n > fileSize_ - fileDone_) { fail("the transmitter sent more than the file holds"); return; }
            if (files_.write(local_, f.payload + 5, n) != (int) n) { fail("cannot write " + s.local + " on the screen's card. Is it full?"); return; }
            runCrc_ = crc32(f.payload + 5, n, runCrc_);
            if (s.check && heldKnown_ && fileDone_ < heldSize_) { const uint32_t part = (heldSize_ - fileDone_ < n) ? heldSize_ - fileDone_ : n; prefixCrc_ = crc32(f.payload + 5, part, prefixCrc_); }
            fileDone_ += n;
        }
        askNextBlock(); return;

    case K_LIST: {
        if (status == LE_NO_FILE) {               // there is no such folder (a card that has never held a log, say)
            note("there is no folder " + s.remote + " on the transmitter's card" + (s.option ? "" : ": nothing to keep"));
            nextStep(); return;
        }
        if (status != LE_OK) { fail(std::string(errorText(status)) + " (the folder " + s.remote + " cannot be read)"); return; }
        SHORT(3)
        const int count = f.get8(1); const bool more = f.get8(2) != 0; size_t at = 3;
        const std::string dir = s.remote == "/" ? std::string() : s.remote, to = s.local;       // (copies: `s` is a place in steps_, which is about to grow)
        for (int i = 0; i < count; ++i) {
            if (at + 5 > f.len) { fail("the list of its files cannot be read"); return; }
            const uint32_t size = f.get32(at); const bool isDir = f.payload[at + 4] != 0; at += 5;
            std::string name; while (at < f.len && f.payload[at]) name.push_back((char) f.payload[at++]);
            if (at >= f.len) { fail("the list of its files cannot be read"); return; }     // (every name ends with a zero)
            at++;
            if (s.option) { Entry e; e.name = name; e.size = size; e.dir = isDir; if (entries_.size() < 1000) entries_.push_back(e); else if (entries_.size() == 1000) { entries_.push_back(e); warn("more than 1000 entries in " + s.remote + ": the rest is not shown"); } continue; }     // just looking
            if (isDir || name.empty() || name[0] == '.') continue;                        // folders; what a Mac leaves behind (._NAME, .DS_Store)
            if (dir.empty() && (name == "LINK.TMP" || name == "LINK.OLD")) continue;          // the link's own
            if (!endsAs(name, s.expect)) continue;
            // From here on it is one of the pilot's files, and it is either copied or SAID not to have been.
            if (name.find('/') != std::string::npos || !plainPath((dir + "/" + name).c_str())) { warn(name + " is NOT copied: the link cannot use its name. It stays on the transmitter's card"); continue; }
            if (s.ms && size > s.ms) { warn(name + " is NOT copied: it is too big (" + kb(size) + "). It stays on the transmitter's card"); continue; }
            listed_.push_back(name); listedHeld_.push_back(s.onlyNew && holds(to + "/" + name));
        }
        listIndex_ += (uint32_t) count;
        if (more && count > 0) { req_.clear(LK_LIST, 0); req_.put32(listIndex_); req_.putText(s.remote.c_str()); request(8000, 5); return; }
        if (s.option) { char b[48]; snprintf(b, sizeof b, "%u entries in ", (unsigned) entries_.size()); note(std::string(b) + s.remote); nextStep(); return; }
        // Each file found is fetched next, in this very job, one after the other (nextChild). One that we hold
        // already is looked at first (its size AND its checksum): the very same file is not fetched again.
        // (Not optional: a file that is listed and cannot be fetched is a failure, not "nothing to keep".)
        { char b[80]; snprintf(b, sizeof b, "%u files to keep from ", (unsigned) listed_.size()); note(std::string(b) + (dir.empty() ? "/" : dir)); }
        childDir_ = dir; childTo_ = to; childAt_ = 0; childrenTotal_ += listed_.size();
        nextChild(); return;
    }

    case K_HOLD:
        if (status != LE_OK) { fail(errorText(status)); return; }
        SHORT(10)
        if (!f.get8(1)) { note("there is no " + s.remote + " on the transmitter's card: nothing to hold a copy of"); nextStep(); return; }
        fileSize_ = f.get32(2); fileCrc_ = f.get32(6);
        beginVerify(s.local, 2);
        return;

    case K_DEL:
        if (status != LE_OK && status != LE_NO_FILE) { fail(errorText(status)); return; }
        note(status == LE_OK ? "removed " + s.remote : s.remote + " was not there"); if (status == LE_OK) changed_ = true;
        nextStep(); return;

    case K_INSTALL: case K_ROLLBACK:
        if (status != LE_OK) { fail(errorText(status)); return; }
        note("staged and verified; the transmitter is swapping firmware and restarting"); changed_ = true;
        nextStep(); return;

    case K_CONFIRM:
        if (status != LE_OK) { fail(errorText(status)); return; }
        note("accepted"); changed_ = true;
        nextStep(); return;

    case K_HELLO: {
        if (status != LE_OK) { fail(errorText(status)); return; }
        char text[240]; if (!f.getText(1, text, sizeof text)) text[0] = 0;
        peer_ = text;
        note("transmitter: " + peer_);
        nextStep(); return;
    }

    case K_SETTLE:                                // our goodbye was heard
        beginSettle(); return;

    default:
        nextStep(); return;
    }
    #undef SHORT
}

// The firmware that has just started says how it reads the model's settings (FlightGuard.h on the Teensy: one
// number made of every end point, mix, trim, reversed channel, switch ...). The firmware that ran before said the
// same of itself when the install began. If the numbers differ, the new firmware is NOT KEPT: a servo would turn
// the other way, a mix or a switch would be another. The previous firmware is put back, and the job says why.
void LinkMaster::compareSettings() {
    const Step s = steps_[step_];
    const std::string now = peerValue("mfp"), fw = peerValue("fw");
    const std::string way1 = settingsBefore_.substr(0, settingsBefore_.find('.')), way2 = now.substr(0, now.find('.'));
    if (settingsBefore_.empty()) settingsRead_ = "unknown: " + (fwBefore_.empty() ? std::string("the firmware that ran before") : fwBefore_) + " did not say how it reads the model's settings (firmware before 2.5.6 B8 does not)";
    else if (now.empty()) settingsRead_ = "unknown: " + fw + " does not say how it reads the model's settings (firmware before 2.5.6 B8 does not)";
    else if (way1 != way2) settingsRead_ = "unknown: " + fw + " describes the settings in another way than " + fwBefore_ + " (way " + way2 + " against way " + way1 + ")";
    else settingsRead_ = (now == settingsBefore_) ? "same" : "different";

    if (undoing_) {                               // the install has been undone: is everything as it was?
        if (settingsRead_ == "same") note(fw + " is back, and reads the model's settings as it did before (" + now + ")");
        else {
            warn(fw + " is back, but how it reads the model's settings could not be confirmed (" + (settingsRead_ == "different" ? settingsBefore_ + " before, " + now + " now" : settingsRead_.substr(9)) + ")");
            if (step_ + 1 < steps_.size() && steps_.back().kind == K_STOP) steps_.back().expect += ". CHECK EVERY CONTROL OF THE MODEL BEFORE FLYING: directions, end points, mixes, switches";
        }
        settingsRead_ = "different";              // (what the job was stopped for)
        nextStep(); return;
    }
    if (settingsRead_ == "same") { note(fw + " reads the model's settings exactly as " + fwBefore_ + " did (" + now + ")"); nextStep(); return; }
    if (settingsRead_ != "different") { warn("how the settings are read could not be compared: " + settingsRead_.substr(9)); nextStep(); return; }

    if (s.back) {                                 // we went back on purpose (or have just undone an install): nothing more to undo
        warn(fw + " reads the model's settings DIFFERENTLY from " + fwBefore_ + " (" + settingsBefore_ + " then, " + now + " now)");
        stage_ = "checking how the firmware reads the settings";
        fail(fw + " is running, and it reads the model's settings differently from " + fwBefore_ + ". CHECK EVERY CONTROL OF THE MODEL BEFORE FLYING: directions, end points, mixes, switches");
        return;
    }
    warn(fw + " reads the model's settings DIFFERENTLY from " + fwBefore_ + " (" + settingsBefore_ + " then, " + now + " now): it is not kept");
    const std::string was = fwBefore_, tried = fw;
    steps_.erase(steps_.begin() + (long) step_ + 1, steps_.end());   // whatever was to follow is not done
    Step r; r.kind = K_ROLLBACK; steps_.push_back(r);
    Step a; a.kind = K_AWAIT_RESTART; steps_.push_back(a);
    Step c; c.kind = K_CHECK; c.expect = was; c.back = true; steps_.push_back(c);
    Step e; e.kind = K_STOP; e.remote = "checking how the new firmware reads the settings";
    e.expect = tried + " read this model's settings differently from " + was + ": a servo could have turned the other way, a mix or a switch could have changed. It was NOT kept. The transmitter runs " + was + " again, and nothing of yours was changed";
    steps_.push_back(e);
    undoing_ = true;
    nextStep();
}

void LinkMaster::sawDisplayTraffic() {
    if (listening_) { if (!trafficSeen_) { trafficSeen_ = true; trafficAt_ = port_.ms(); } return; }
    if (linkOpen_ && running()) peerLeft_ = true;
}

void LinkMaster::frameArrived(const Frame &f) {
    if (!running()) return;
    if (state_ == S_KNOCK) {
        if (f.type != (LK_REPLY | LK_HELLO)) return;
        char text[240]; if (!f.getText(1, text, sizeof text)) text[0] = 0;
        peer_ = text; peerLeft_ = false;
        refusal_ = f.get8(0); linkOpen_ = (refusal_ == LE_OK);        // it may say who it is and still keep the link shut (a model is connected)
        if (step_ == 0) note(linkOpen_ ? "link open: " + peer_ : std::string("the transmitter keeps the link shut: ") + errorText(refusal_));
        state_ = S_STEP; beginStep();
        return;
    }
    if (!awaiting_ || f.seq != req_.seq || f.type != (uint8_t) (LK_REPLY | req_.type)) return;      // an old answer
    awaiting_ = false;
    if (state_ == S_BYE) { finish(); return; }
    onReply(f);
}

void LinkMaster::poll() {
    if (!running()) return;
    const uint32_t now = port_.ms();

    if (state_ == S_WAIT_RESTART) {               // the caller tells us when the Teensy talks to its display again
        if (trafficSeen_ && now - trafficAt_ > 7000) {       // it started 7 s ago: its start-up (splash, fade-in) is over and it reads touches
            listening_ = false;
            note("the transmitter is talking again");
            stage_ = "asking the transmitter who it is";
            step_++; phase_ = 0;                  // the waiting step is done
            knockNow(60);                         // patiently: firmware that falls over needs half a minute to be replaced by the previous one
        } else if (now - waitFrom_ > 60000) {
            listening_ = false; stage_ = "restart";
            fail("the transmitter did not come back within a minute. If it stays dark, connect USB and load firmware with the Teensy loader");
        }
        return;
    }
    if (state_ == S_VERIFY) { verifySome(); return; }
    if (state_ == S_SETTLE) {
        if (now - waitFrom_ >= settleMs_) {
            listening_ = false;
            stage_ = "asking the transmitter who it is";
            step_++; phase_ = 0;
            knockNow(60);
        }
        return;
    }

    if (state_ == S_KNOCK && now - knockAt_ > 1500) {
        if (knocks_ >= knockLimit_) {
            fail(knockLimit_ > 6 ? "the transmitter does not answer. If it stays dark, connect USB and load firmware with the Teensy loader"
                                 : "the transmitter does not answer the link. Its firmware may be older than this feature (it needs one update by USB first)");
            return;
        }
        knocks_++; knockAt_ = now; port_.knock();
        return;
    }
    const bool installing = step_ < steps_.size() && (steps_[step_].kind == K_INSTALL || steps_[step_].kind == K_ROLLBACK);
    const bool parting = state_ == S_BYE || (step_ < steps_.size() && steps_[step_].kind == K_SETTLE);
    if (state_ == S_AWAIT && awaiting_ && installing && peerLeft_) {        // it restarted before we heard its answer
        awaiting_ = false; note("the transmitter restarted (its answer to the install request was not heard)"); state_ = S_STEP; nextStep(); return;
    }
    if ((state_ == S_AWAIT || state_ == S_BYE) && awaiting_ && (now - sentAt_ > timeout_ || (peerLeft_ && now - sentAt_ > 300))) {
        if (parting && (peerLeft_ || triesLeft_ <= 0)) {                    // a goodbye that was not acknowledged is a goodbye all the same
            awaiting_ = false;
            if (state_ == S_BYE) finish(); else beginSettle();
            return;
        }
        if (installing) { awaiting_ = false; note("no answer to the install request; watching for a restart anyway"); state_ = S_STEP; nextStep(); return; }
        if (peerLeft_) { fail("the transmitter left the link (did it restart?)"); return; }
        if (triesLeft_ <= 0) { fail("no answer from the transmitter"); return; }
        triesLeft_--; resends_++;
        static uint8_t raw[LINK_MAX_FRAME];
        port_.write(raw, encode(req_, raw));      // the same request, the same number
        sentAt_ = now;
    }
}

}  // namespace ldrc
