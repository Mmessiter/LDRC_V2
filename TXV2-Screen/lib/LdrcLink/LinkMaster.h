// LinkMaster — the screen's end of LdrcLink: a queue of jobs (send a file, fetch a file, install
// firmware and see it through its trial) run one request at a time, with time-outs, repeats and a
// plain-words record of what happened. Portable: the wire and the screen's card are reached through
// MasterPort and MasterFiles, so the host tests run this very code against the Teensy's LinkServer.
#ifndef LDRC_LINK_MASTER_H
#define LDRC_LINK_MASTER_H

#include "LdrcLink.h"
#include <string>
#include <vector>

namespace ldrc {

class MasterPort {                                // the wire (outwards) and the clock
public:
    virtual ~MasterPort() {}
    virtual void write(const uint8_t *b, size_t n) = 0;
    virtual uint32_t ms() = 0;
    virtual void knock() = 0;                     // send LDRC_LINK_KNOCK as a touch-event text
};

class MasterFiles {                               // the screen's own card
public:
    virtual ~MasterFiles() {}
    virtual int  open(const char *path, bool forWriting) = 0;
    virtual int  read(int handle, uint8_t *buf, size_t n) = 0;
    virtual int  write(int handle, const uint8_t *buf, size_t n) = 0;
    virtual bool seek(int handle, uint32_t pos) = 0;
    virtual uint32_t size(int handle) = 0;
    virtual void close(int handle) = 0;
    virtual bool remove(const char *path) = 0;
    virtual bool rename(const char *from, const char *to) = 0;      // `to` is not there (it has been moved aside first)
};

const uint32_t TRIAL_WAIT_MS = 38000;             // the Teensy accepts its new firmware after 30 s of running: look again after this

class LinkMaster {
public:
    LinkMaster(MasterPort &port, MasterFiles &files);

    // ---- build a job list, then start()
    void clear();
    void put(const std::string &local, const std::string &remote, uint8_t flags = 0, bool onlyIfDifferent = true);
    void get(const std::string &remote, const std::string &local, bool optional = false);   // optional: a file that is not there is not a failure
    void del(const std::string &remote, uint8_t flags = 0);
    // A whole folder of the Teensy's card kept on ours: it is listed, and every file in it whose name ends as
    // asked ("" = every file) is fetched to the same name below localDir. The pilot's model files, before
    // new firmware goes in. A folder that is not there, or is empty, is nothing to keep and no failure.
    // Files bigger than maxBytes are left where they are, and said so (a card may hold anything).
    // onlyNew: a file of which we hold the very same copy (size and checksum) is left alone (logs: a hundred files
    // that never change, and one that grows). A copy is replaced ONLY by a file that begins with all of it (the log
    // has grown). If the file is anything else - smaller, or begun again under the same name - the copy stays, as
    // <name>.older, <name>.older2 ... : a copy once taken is never removed.
    // And a copy counts as kept only when it has been read back from OUR card and agrees with the Teensy's checksum.
    void keepFolder(const std::string &remoteDir, const std::string &localDir, const std::string &ending = "", uint32_t maxBytes = 4u * 1024u * 1024u, bool onlyNew = false);
    // A file that MUST be among the copies before the job goes on: the Teensy is asked whether it has `remote` (and
    // for its size and checksum); if it has, our copy at `local` must be that very file, read back from our card.
    // If it has none, there is nothing to hold and the job goes on. (models.dat: the models and the transmitter's
    // settings. A card that could not list its own folder said "empty", and new firmware went in without a copy.)
    void mustHold(const std::string &remote, const std::string &local);
    size_t kept() const { return kept_; }         // files fetched for keepFolder() in this run
    size_t held() const { return held_; }         // files we held already, unchanged
    // Every file that keepFolder() was to copy has arrived and been read back from our card - whatever became of
    // the rest of the job. (A copy that is whole is a copy worth keeping, even if the install behind it failed.)
    bool copiesDone() const;
    // What was NOT copied, and why, in plain words (a file too big, a name we cannot use): never trimmed, never silent.
    const std::vector<std::string> &warnings() const { return warnings_; }
    void list(const std::string &remoteDir);      // just look: what is in that folder
    struct Entry { std::string name; uint32_t size; bool dir; };
    const std::vector<Entry> &entries() const { return entries_; }
    void hello();                                 // just ask who is there (answered even when the link is refused)
    // Install, wait for the restart, check the version, let it run through its trial AS A TRANSMITTER, check again.
    void install(const std::string &remotePackage, const std::string &expectVersion);
    void rollback();
    void confirm();                               // accept the firmware on trial now
    // A job is built and started by ONE caller. While a job runs, nothing can be added to it: put(), get(),
    // install() ... do nothing then, and start() answers false. (Steps used to join the running job: the update's
    // install went in behind a copy asked for from the Mac, a minute after the panel had said "failed".)
    bool start();                                 // false if already running or nothing to do

    // ---- run it. The caller reads the wire and sorts it (ldrc::Router): frames come here, display commands
    //      go to the display as ever, and each one is reported with sawDisplayTraffic().
    void poll();                                  // time-outs and the next step: call often
    void frameArrived(const Frame &f);
    void sawDisplayTraffic();
    bool running() const { return state_ != S_IDLE && state_ != S_DONE && state_ != S_FAILED; }
    bool linkOpen() const { return linkOpen_; }   // the Teensy is a file server just now: send it no touches
    bool listening() const { return listening_; } // the Teensy is a transmitter just now and we are waiting
    void cancel(const char *why);

    // ---- what happened
    bool finished() const { return state_ == S_DONE; }
    bool failed() const { return state_ == S_FAILED; }
    const std::string &stage() const { return stage_; }              // what it is doing, in plain words
    const std::string &result() const { return result_; }            // the last line: how it ended
    const std::vector<std::string> &log() const { return log_; }            // the first 40 lines and the last 360
    uint32_t noted() const { return noted_; }                                // how many lines were written in all
    const std::string &peer() const { return peer_; }                // the Teensy's last hello text
    std::string peerValue(const char *key) const;                    // e.g. peerValue("fw")
    uint8_t refusal() const { return refusal_; }                     // LE_OK, or why it answered the knock and kept the link shut
    int peerStatus() const;                                          // the Teensy's "st" (FlightGuard.h: 1 motor, 2 armed, 4 model connected, 8 safety on, 16 model a moment ago), -1 if it did not say
    // Did the firmware just installed read the model's settings as the one before it? "" until an install has been
    // checked, then "same", "different" (it was not kept), or "unknown: <why it could not be compared>".
    const std::string &settingsRead() const { return settingsRead_; }
    bool changedTeensy() const { return changed_; }                  // this job wrote, removed or installed something on the Teensy (a look, a copy, a hello did not)
    // How far the job has got. The files of a folder that is kept are not steps of their own (a pilot with 700 logs
    // would cost the screen 130 kB of memory for them): they are counted here all the same.
    size_t stepIndex() const { return step_ + childrenDone_; }
    size_t stepCount() const { return steps_.size() + childrenTotal_; }
    uint32_t fileDone() const { return fileDone_; }
    uint32_t fileSize() const { return fileSize_; }
    uint32_t resends() const { return resends_; }

private:
    enum State { S_IDLE, S_KNOCK, S_STEP, S_AWAIT, S_WAIT_RESTART, S_SETTLE, S_BYE, S_VERIFY, S_DONE, S_FAILED };
    enum Kind { K_PUT, K_GET, K_DEL, K_HELLO, K_INSTALL, K_ROLLBACK, K_AWAIT_RESTART, K_CHECK, K_SETTLE, K_CONFIRM, K_LIST, K_STOP, K_HOLD };
    struct Step {
        Kind kind; std::string local, remote, expect; uint8_t flags; bool option; uint32_t ms;
        bool keep;                                // a copy for keepFolder(): it arrives as <name>.part and takes its place when it is whole
        bool onlyNew;                             // (K_LIST) what we hold already is not fetched again
        bool check;                               // (K_GET) we hold a copy under this name: look at it first
        bool back;                                // (K_CHECK) this is the firmware we went BACK to: nothing to compare, nothing to undo
        Step() : kind(K_HELLO), flags(0), option(false), ms(0), keep(false), onlyNew(false), check(false), back(false) {}
    };

    bool add(Kind kind, const std::string &local = "", const std::string &remote = "", const std::string &expect = "", uint8_t flags = 0, bool option = false, uint32_t ms = 0);
    void warn(const std::string &line);
    bool holds(const std::string &path);
    bool putInPlace(const std::string &from, const std::string &to);
    Step &cur() { return inChild_ ? child_ : steps_[step_]; }     // the step in hand: one of the list, or a file of a folder that is kept
    void beginGet();
    void nextChild();
    void getDone();
    void askToRead();
    void beginVerify(const std::string &path, int what);
    void verifySome();
    void verified(bool readable, uint32_t size, uint32_t crc);
    void copyArrived();
    void compareSettings();
    void note(const std::string &line);
    void fail(const std::string &why);
    void finish();
    void request(uint32_t timeoutMs, int tries);
    void knockNow(int limit);
    void beginStep();
    void nextStep();
    void onReply(const Frame &f);
    void sendNextBlock();
    void askNextBlock();
    void closeLocal();
    void beginSettle();

    MasterPort &port_; MasterFiles &files_;
    Frame req_;
    State state_;
    std::vector<Step> steps_; size_t step_;
    int phase_;                                   // within a step
    uint8_t seq_;
    bool awaiting_; uint32_t sentAt_, timeout_; int triesLeft_; uint32_t resends_;
    uint32_t startedAt_, knockAt_; int knocks_, knockLimit_;
    bool listening_, trafficSeen_; uint32_t trafficAt_, waitFrom_, settleMs_;
    bool linkOpen_;                               // the Teensy has opened the link and not been told goodbye
    uint8_t refusal_;                             // why it would not (LE_BUSY, LE_NOT_NOW), when it answered the knock but kept the link shut
    bool peerLeft_;                               // display commands from a Teensy that should be serving files: it has restarted
    int resyncs_;
    int local_; uint32_t fileSize_, fileCrc_, fileDone_, runCrc_;
    uint32_t listIndex_; std::vector<std::string> listed_; std::vector<bool> listedHeld_; size_t kept_, held_;
    Step child_; bool inChild_; size_t childAt_, childrenDone_, childrenTotal_; std::string childDir_, childTo_;
    std::string writing_;                         // the file being written on our card (a copy goes to <name>.part first)
    // reading a file of OUR card back, a piece at a time (the screen has other things to do): the copy we hold,
    // before the Teensy is asked for its file; and the copy that has just arrived, before it counts as kept
    int verify_, verifyWhat_; uint32_t verifySize_, verifyCrc_; std::string verifyPath_;
    bool heldKnown_; uint32_t heldSize_, heldCrc_, prefixCrc_;
    std::string fwBefore_, settingsBefore_, settingsRead_;       // what the Teensy ran, and how it read the settings, when an install began
    bool undoing_;                                // the firmware just installed read the settings differently: the previous one is being put back
    bool changed_;
    std::vector<Entry> entries_;
    std::string stage_, result_, peer_;
    std::vector<std::string> log_, warnings_; uint32_t noted_;
};

}  // namespace ldrc
#endif
