// LdrcUpdate — "Check for update" for Transmitter Version 1B.
//
// The pilot presses a button; nothing is ever offered or done by itself. The screen asks messiter.com what
// the latest release is, asks the Teensy what it runs, and says "Up to date" or offers "Install now".
// An install fetches everything it needs to the screen's card FIRST (each file checked by size and CRC-32),
// and only then changes anything, in this order: the Teensy's files and firmware (LdrcLink, with the
// Teensy's own trial and fall-back), the screen's files, the screen's firmware (with a trial and fall-back
// of its own after the restart). It ends with one panel, good or bad, that stays until OK is pressed and
// comes back at the next power-on if it was never seen.
//
// Portable: the WiFi, the card, the flash and the clock are reached through UpdateHost, so the host tests
// (hmi/test_update) run this very code against a make-believe website, card and Teensy.
#ifndef LDRC_UPDATE_H
#define LDRC_UPDATE_H

#include "LinkMaster.h"
#include "TxState.h"
#include <string>
#include <vector>

namespace ldrc {

struct Work {                                     // how a slow job ended
    bool ok; std::string error; uint32_t size, crc; std::string text;
    Work() : ok(false), size(0), crc(0) {}
};

class UpdateHost {                                // the machine the updater runs on
public:
    virtual ~UpdateHost() {}
    virtual uint32_t ms() = 0;
    virtual std::string screenVersion() = 0;
    virtual std::string stamp() = 0;              // the date and time, if known (the Teensy has the clock), for the record
    virtual bool armed() = 0;                     // the motor is on or the safety is off: the radio is off, and nothing may be done
    // Why nothing may be begun or changed just now, or FLY_NO. Flying comes first: a model that is connected, or
    // was a moment ago, may be in the air.
    enum { FLY_NO = 0, FLY_MOTOR = 1, FLY_SAFETY = 2, FLY_MODEL = 3, FLY_MODEL_JUST_NOW = 4 };
    virtual int flying() { return armed() ? FLY_MOTOR : FLY_NO; }
    virtual bool teensySeen() = 0;                // the main board has sent display commands since power-on
    virtual void wifiWanted(bool on) = 0;
    virtual bool wifiUp() = 0;
    virtual bool wifiAny() = 0;                   // the transmitter knows at least one network
    virtual void wifiSetup() = 0;                 // open the WiFi page (the pilot asked, from our panel)
    virtual void keepAwake() = 0;                 // tell the main board someone is here: its screen saver and its power-off timer start again
    // The receiver, through the main board (firmware B11 and later): what it last said of the receiver (false: never a
    // word), and the order "update yourself to major.minor.minimus" (LDRC_RX_UPDATE_WORD on the wire).
    virtual bool rxNews(RxNews &out) { (void) out; return false; }
    virtual void rxOrder(int major, int minor, int minimus) { (void) major; (void) minor; (void) minimus; }

    // Slow jobs: one at a time, done in the background. done() may be read once busy() is false.
    virtual void fetchText(const std::string &url, size_t maxBytes) = 0;
    virtual void fetchFile(const std::string &url, const std::string &local, uint32_t size, uint32_t crc) = 0;   // never leaves a wrong or half file at `local`
    virtual void checkFile(const std::string &local) = 0;                      // size and CRC-32; ok = false: no such file
    virtual void flashScreen(const std::string &local, uint32_t size, uint32_t crc) = 0;
    virtual bool busy() = 0;
    virtual uint32_t progress() = 0;              // bytes of the running job so far
    virtual const Work &done() = 0;
    virtual void stopWork() = 0;                  // give the running job up

    // The screen's card.
    virtual bool exists(const std::string &path) = 0;
    virtual int32_t sizeOf(const std::string &path) = 0;                       // -1: no such file
    virtual bool remove(const std::string &path) = 0;
    virtual bool rename(const std::string &from, const std::string &to) = 0;   // folders on the way are made; a file already at `to` is replaced
    virtual bool readText(const std::string &path, std::string &out, size_t maxBytes) = 0;
    virtual bool writeText(const std::string &path, const std::string &text) = 0;
    virtual bool appendText(const std::string &path, const std::string &text) = 0;
    virtual uint32_t freeKb() = 0;
    // The pilot's own files (models.dat: the models and the transmitter's settings; every *.MOD) are copied to the screen's
    // card before new firmware goes into the Teensy: a new folder for each time, the oldest let go when there are many.
    virtual std::string backupFolder(const std::string &firmwareNow) = 0;
    virtual void backupDone(const std::string &folder, const std::string &about) = 0;
    virtual void tidy(const std::string &folder) = 0;                          // remove the files in it (what earlier attempts fetched and never used)

    // The screen's own firmware.
    virtual bool onTrial() = 0;                   // it has started for the first time and is not yet accepted
    virtual void accept() = 0;
    virtual bool reject() = 0;                    // the previous firmware comes back (a restart); false: there is none to go back to
    virtual void restart() = 0;
    // The largest piece of memory a new secure connection could get (bytes). After a Bluetooth session the memory is
    // in pieces, and a connection to messiter.com wants some 45 kB in one; the update then restarts the screen first
    // and goes on by itself (1.11.31). The default says "plenty".
    virtual uint32_t roomForTls() { return 0xFFFFFFFFu; }
};

struct UpdRow { std::string what, now, next; };
struct UpdChoice { std::string name, note; bool current; };     // a version to choose: its name, its date, and whether it is the one installed
struct UpdView {                                  // what the panel shows
    enum Kind { NONE, BUSY, NOTE, OFFER, WORKING, GOOD, BAD, CHOOSE };
    std::vector<UpdChoice> choices;               // CHOOSE: touched, a choice is press(10 + its place)
    std::string button3;                          // a third, smaller button ("Earlier versions")
    Kind kind;
    std::string title;
    std::vector<UpdRow> rows;                     // a small table: what / now / new
    std::vector<std::string> lines;               // plain lines under it (the panel wraps them)
    std::string warning;                          // "Do not switch off" (large and bold)
    std::string hint;                             // under it, small: "The screen may flicker while this runs"
    std::string button1, button2;                 // "" = no such button
    bool bar; uint32_t barDone, barTotal;
    uint32_t serial;                              // changes whenever anything but the bar changes
    UpdView() : kind(NONE), bar(false), barDone(0), barTotal(0), serial(0) {}
};

struct UpdPart {
    bool present; std::string version, file; uint32_t size, crc, count, bytes;
    UpdPart() : present(false), size(0), crc(0), count(0), bytes(0) {}
};
struct UpdRelease {
    std::string name, date, notes, base;
    UpdPart teensy, teensyFiles, screen, screenFiles;
};
struct UpdEntry { std::string path; uint32_t size, crc; };
struct UpdRecent { std::string name, date, teensy, screen, path, notes; };      // one of the releases that can be gone back to

// The release description ("latest.txt": key=value lines, ending end=1) and the file lists ("CRC SIZE /path").
bool parseRelease(const std::string &text, UpdRelease &r, std::string &why);
bool parseList(const std::string &text, bool forTeensy, std::vector<UpdEntry> &out, std::string &why);
// The releases on offer ("recent.txt": the latest first, then the few before it), for going back to one of them.
bool parseRecent(const std::string &text, std::vector<UpdRecent> &out, std::string &why);
std::string hex8(uint32_t v);

class Updater {
public:
    Updater(UpdateHost &host, LinkMaster &link, const std::string &latestUrl);

    void begin();                                 // the pilot pressed "Check for update" (Transmitter setup): the transmitter and the screen
    void beginReceiver();                         // the pilot pressed "Receiver update" (Model setup): the connected receiver, through the main board
    void setReceiverManifest(const std::string &url) { rxManifestUrl_ = url; }   // the receivers' release list (messiter.com/rxv2/release/manifest.json)
    void resume();                                // once, at start-up: unfinished business, or firmware on trial
    void poll();                                  // call often
    void press(int button);                       // 1 or 2

    bool showing() const { return view_.kind != UpdView::NONE; }
    bool idle() const { return phase_ == P_IDLE; }
    bool ownsLink() const { return linkOurs_; }   // the link job running is ours: the panel is ours too
    bool working() const { return changing_; }    // something is being changed: do not switch off
    const UpdView &view() const { return view_; }
    const std::vector<std::string> &log() const { return log_; }

private:
    enum Phase { P_IDLE, P_WIFI, P_LATEST, P_ASK, P_NOTE, P_OFFER, P_RECENT, P_PICK, P_DESCR,
                 P_LISTS, P_COMPARE, P_FETCH, P_TEENSY, P_PLACE, P_FLASH, P_RESTART,
                 P_TRIAL, P_RESULT, P_FRESH,
                 P_RX_WIFI, P_RX_LATEST, P_RX_OFFER, P_RX_RUN };     // the receiver's update, through the main board
    struct Item {
        uint8_t kind;                             // 0 Teensy firmware, 1 a Teensy file, 2 the screen's firmware, 3 a screen file
        std::string path, remote, staged, url; uint32_t size, crc; bool have, fetched, known;
    };

    void note(const std::string &line);
    void bar(uint32_t done, uint32_t total);
    void cancel();
    bool linkBusy() const;
    void afterFetch();
    void teensyShow();
    void startPlace();
    void placeSome();
    void afterAll();
    void rejectWith(const std::string &why);
    void versionRows();
    void show(UpdView::Kind kind, const std::string &title);
    void line(const std::string &text);
    void row(const std::string &what, const std::string &now, const std::string &next);
    void buttons(const std::string &b1, const std::string &b2);
    void changed() { view_.serial++; }
    void setLine(size_t index, const std::string &text);
    void message(const std::string &title, const std::string &l1, const std::string &l2 = "");
    bool notNow();                                // true: flying comes first, and the panel says so
    int flyingNow() const;                        // host_.flying(), except that a connected model is no bar to the receiver's own update
    void fetchAsked(const std::string &url, size_t maxBytes = 8192);      // a small text from messiter.com, tried three times
    void freshStart(const std::string &kind);     // the memory is in pieces: the screen restarts, and `kind` ("check" or "install") goes on by itself
    bool freshNeeded() const { return !freshDone_ && host_.roomForTls() < TLS_ROOM; }
    static const uint32_t TLS_ROOM = 48u * 1024u;
    // the receiver's update
    void rxGotLatest();
    void rxInstall();
    void rxPoll();
    void rxVerdict(const RxNews &n);
    void rxResult(bool good, const std::string &title, const std::vector<std::string> &lines);
    bool textArrived();                           // false: not yet, or it is being asked for again, or it failed (and the panel says so)
    void noWifi(const std::string &title, const std::string &l1, const std::string &l2);
    void versions();
    void gotRecent();
    void pick(size_t i);
    void gotDescription();
    void close();
    void fail(const std::string &stage, const std::string &why);
    void finishGood();
    void result(bool good, const std::string &title, const std::vector<std::string> &lines);
    void saveState(const std::string &stage);
    std::string stateText(const std::string &stage) const;
    void linkGo();
    void askTeensy();
    void asked();
    void decide();
    void install();
    void nextList();
    void gotList();
    void buildItems();
    void compareNext();
    void compared();
    void startFetch();
    void fetchNext();
    void fetched();
    void startTeensy();
    void teensyDone();
    void startFlash();
    void trialPoll();
    std::string url(const std::string &file) const;

    UpdateHost &host_; LinkMaster &link_; std::string latestUrl_;
    Phase phase_; UpdView view_;
    std::vector<std::string> log_;
    uint32_t since_, lastPoke_, shownAt_, linkAfter_, restartAt_, stageSince_;
    bool linkOurs_, linkWanted_, linkStarted_, changing_, silent_, waiting_, noteWifi_;
    bool shownFlying_;                            // the panel came up WHILE the motor was on (it says so): it must stay long enough to be read
    bool mustSee_;                                // a verdict that says DO NOT FLY: it steps aside for nothing, until OK is pressed
    std::string textUrl_; int textTries_; size_t textMax_;
    std::string stage_;
    UpdRelease rel_;
    bool teensyThere_, teensyFellBack_; std::string teensyFw_, teensyMarker_;
    std::string recentUrl_; std::vector<UpdRecent> recent_; bool choosing_, noteVersions_;
    std::string descrUrl_;                        // where rel_ came from (latest.txt, or a chosen version's description): a fresh start fetches it again
    std::string freshKind_, freshUrl_; bool freshDone_, freshChoosing_;   // this run began from a fresh start (so it never asks for another)
    bool needTeensyFw_, needTeensyFiles_, needScreenFw_, needScreenFiles_;
    std::vector<UpdEntry> teensyList_, screenList_, known_;
    std::string screenListText_;
    int listStep_;
    std::vector<Item> items_; size_t at_; int sub_, tries_;
    uint32_t fetchTotal_, fetchDone_; size_t fetchCount_, fetchIndex_;
    size_t placed_; uint32_t trialSeen_;
    std::string keepDir_; size_t keptFiles_;
    // after a restart
    std::string stRelease_, stTeensy_, stFrom_, stTo_; bool stTeensyThere_, stTeensyChanged_, stScreenFw_; int stFiles_, stKept_;
    std::string stSettings_;                      // how the new firmware reads the model's settings: "same", "unknown", or "" (no new firmware)
    std::vector<std::string> stWarn_;             // what was NOT copied of the pilot's files, for the last panel
    int trialStep_;
    bool resultGood_;
    // the receiver's update
    std::string rxManifestUrl_;
    bool rxFlow_;                                 // the receiver's flow is running: a connected model is expected, not a bar
    uint32_t rxHave_, rxLatest_;                  // release numbers: the receiver's, and messiter.com's latest
    std::string rxLatestName_, rxNotes_;
    int rxPhaseSeen_; uint32_t rxNewsAt_;
    uint32_t rxQuietTotal_;                       // the whole silence, in seconds: the bar counts it down
    bool again_;                                  // "Install again": every part of the release goes in, even the same
};
std::string rxVersionText(uint32_t code);         // 0x0009035F -> "0.9.863"
bool parseReceiverManifest(const std::string &json, uint32_t &code, std::string &name, std::string &notes);   // the first (latest) entry

}  // namespace ldrc
#endif
