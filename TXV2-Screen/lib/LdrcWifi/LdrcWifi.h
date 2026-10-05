// LdrcWifi — the WiFi page of Transmitter Version 1B.
//
// The pilot chooses a network from the ones in range and types its password on the screen; the transmitter
// remembers up to eight networks (house, phone, club) and joins the best one it can hear. No network name
// and no password is compiled into the firmware: what is published holds nothing private.
//
// The page is the screen's own (not one of the Teensy's pages): it works on a new screen whose card is
// empty, which is when it is needed first. This file is the thinking: which page shows, what is on it and
// where, what a touch does. It is portable, so the host tests (hmi/test_wifi) run it against make-believe
// networks; the radio, the store and the drawing are reached through WifiHost and the scene.
#ifndef LDRC_WIFI_H
#define LDRC_WIFI_H

#include <stdint.h>
#include <stddef.h>
#include <string>
#include <vector>

namespace ldrc {

struct WifiNet { std::string ssid; int rssi; bool locked; };          // a network in range (the strongest of its name)
struct WifiKnown { std::string ssid, pass; };                         // a network this transmitter may join

const size_t WIFI_KNOWN_MAX = 8;
const size_t WIFI_PASS_MAX = 63, WIFI_PASS_MIN = 8;                   // WPA's own limits

std::string wifiShown(const std::string &ssid);                       // the name as the screen's Latin-1 fonts can show it
bool wifiSameName(const std::string &a, const std::string &b);        // the same name, whichever apostrophe it is written with
int wifiBars(int rssi);                                               // 1 (weak) .. 4 (strong)
// The network to join now: the strongest in range of those we know (the newest of them if two are as strong).
// Returns its place in `known` and its name AS BROADCAST, or -1 if none of them is in range.
int wifiBest(const std::vector<WifiKnown> &known, const std::vector<WifiNet> &seen, std::string &ssid);
// A network joined, or its password changed: it goes to the front; the oldest drops off the end of a full list.
void wifiRemember(std::vector<WifiKnown> &known, const std::string &ssid, const std::string &pass);
bool wifiForget(std::vector<WifiKnown> &known, const std::string &ssid);

class WifiHost {                                  // the radio, the store and the clock
public:
    virtual ~WifiHost() {}
    virtual uint32_t ms() = 0;
    virtual bool armed() = 0;
    virtual bool armedBySafety() { return false; }     // ... because the safety is off (a safety switch is defined), not because the motor is on                     // the motor is on: no WiFi, by rule
    virtual bool radioOn() = 0;                   // the pilot's own switch
    virtual void radioSwitch(bool on) = 0;
    virtual void scanStart() = 0;
    virtual int scanState() = 0;                  // 0 looking, 1 done, -1 could not look
    virtual void scanResults(std::vector<WifiNet> &out) = 0;
    virtual void join(const std::string &ssid, const std::string &pass) = 0;
    virtual int joinState() = 0;                  // 0 trying, 1 joined, -1 the password was refused, -2 not found, -3 no answer
    virtual std::string joinedTo() = 0;           // "" = not joined
    virtual int signal() = 0;                     // of the network joined, dBm
    virtual void leave() = 0;
    virtual void load(std::vector<WifiKnown> &out) = 0;
    virtual void save(const std::vector<WifiKnown> &all) = 0;
};

// What is on the screen: a list of things to draw, each with its place. The screen draws them and hands
// every touch back; it knows nothing of what they mean.
struct WifiItem {
    enum Kind { TITLE, TEXT, ROW, BUTTON, KEY, FIELD };
    Kind kind; int id; int x, y, w, h;
    std::string text, note;                       // ROW: the name and "Joined" / "Saved" / "Not in range"
    std::string hint;                             // FIELD: what to type, shown while the box is empty
    int bars;                                     // ROW: 1..4, 0 = none to show
    bool locked, strong, pressed, enabled, good, bad;
    uint32_t serial;                              // changes when this one must be drawn again
    WifiItem() : kind(TEXT), id(0), x(0), y(0), w(0), h(0), bars(0), locked(false), strong(false), pressed(false), enabled(true), good(false), bad(false), serial(0) {}
};
struct WifiScene {
    std::vector<WifiItem> items;
    uint32_t layout;                              // changes when everything must be drawn again
    WifiScene() : layout(0) {}
};

class WifiSetup {
public:
    explicit WifiSetup(WifiHost &host);

    void open();                                  // the pilot asked for the WiFi page
    void close();
    bool showing() const { return page_ != PG_NONE; }
    bool typing() const { return page_ == PG_KEYS; }     // a password is on the screen: no pictures of it
    void poll();
    void touch(bool down, int x, int y);          // the finger, every pass while the page shows
    const WifiScene &scene() const { return scene_; }
    std::string pageName() const;                 // "list", "keys", ... for the record

private:
    enum Page { PG_NONE, PG_LIST, PG_KNOWN, PG_KEYS, PG_JOINING, PG_NOTE };
    struct Row { std::string ssid; int rssi; bool locked, known, inRange, joined, checking; };

    void go(Page p);
    void build();
    void add(WifiItem::Kind kind, int id, int x, int y, int w, int h, const std::string &text);
    WifiItem &last() { return next_.back(); }
    int hit(int x, int y) const;
    void act(int id);
    void key(int id);
    void look();
    void list();
    void choose(const Row &r);
    void tryJoin(const std::string &ssid, const std::string &pass);
    void motorNote();
    void note(const std::string &title, const std::string &l1, const std::string &l2, const std::string &b1, const std::string &b2, bool good, bool bad);
    std::string statusText(bool &good) const;

    WifiHost &host_; Page page_; WifiScene scene_; std::vector<WifiItem> next_;
    std::vector<WifiKnown> known_; std::vector<WifiNet> seen_; std::vector<Row> rows_;
    size_t first_;
    bool looking_, looked_; uint32_t lookSince_; int lookTries_;
    Row target_; std::string typed_; int layer_; bool hidden_, changing_;
    std::string before_, beforePass_, joinPass_; bool goingBack_;
    uint32_t joinSince_, noteSince_; bool noteGood_;
    std::string noteTitle_, noteL1_, noteL2_, noteB1_, noteB2_; bool noteBad_;
    bool down_; int pressed_; int lastX_, lastY_; uint32_t seenDown_, repeatAt_; bool repeated_;
    uint32_t serial_; bool redo_;
    bool fresh_, noteMotor_;                      // the radio has new findings, not yet in the list; the note on the glass is the motor's
};

}  // namespace ldrc
#endif
