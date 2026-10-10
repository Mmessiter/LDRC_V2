// LdrcCli - Rotorflight's command line on the transmitter's screen (screen 1.11.41, 10 Oct 2026; Malcolm: "Are we able
// to add CLI?" ... "Yes - let's add save diff to card! And let's do it!").
//
// The flight controller's command line is a text mode of its USB port. The receiver reaches it over the USB cable
// (RXV2 UsbHostMsp, /api/cli: one command per request, the printed reply back; /api/cli/leave: save or exit, either
// of which restarts the flight controller), and the screen reaches the receiver over its Bluetooth pipe. The page is
// the screen's own: a console of what the flight controller printed, a line to type a command on (the keys as the
// WiFi page has them), the usual commands as buttons, "Diff to card" (diff all, kept on the screen's card as a text
// file the configurator can replay), and the two ways out. Opened from the Backup page: "Command line ..." for the
// console, "Diff to card" for the one job on its own.
//
// This file is the thinking: which page shows, what is on it, what a touch does, the job's steps. It is portable and
// tested on the Mac (hmi/test_cli) against a make-believe receiver; the pipe, the card, the clock and the drawing are
// reached through CliHost and the scene. The items are the WiFi page's kind, so the screen draws them with the same
// code (src/wifi_device.h wifiDrawItem); the console (ID_CONSOLE) is the one item of its own.
#ifndef LDRC_CLI_H
#define LDRC_CLI_H

#include <stdint.h>
#include <string>
#include <vector>
#include "LdrcWifi.h"

namespace ldrc {

const size_t CLI_CMD_MAX = 120;               // a command (the receiver takes 160)
const size_t CLI_LINES_MAX = 600;             // the console keeps this many lines
const int CLI_VISIBLE = 12;                   // lines on the glass

class CliHost {                               // the pipe, the card and the clock
public:
    virtual ~CliHost() {}
    virtual uint32_t ms() = 0;
    virtual bool pipeReady() = 0;             // the Bluetooth pipe to the receiver is joined
    virtual bool armed() = 0;                 // the model could be flying: nothing goes
    virtual bool ask(const std::string &method, const std::string &path) = 0;   // one request at a time (false: busy, not joined)
    virtual int askState() = 0;               // 0 waiting, 1 answered, -1 no answer
    virtual int askCode() = 0;                // the answer's HTTP code
    virtual std::string askBody() = 0;
    virtual std::string askError() = 0;       // why there was no answer
    virtual std::string modelName() = 0;      // the model in use, for the file's name ("" = not known)
    virtual std::string stamp() = 0;          // "2026-10-10_0915", or "" when the clock is not set
    virtual bool exists(const std::string &path) = 0;
    virtual bool save(const std::string &path, const std::string &text, std::string &err) = 0;
};

enum { CLI_ID_CONSOLE = 60, CLI_ID_FIELD = 61, CLI_ID_TITLE = 62, CLI_ID_HINT = 63, CLI_ID_NOTE1 = 64, CLI_ID_NOTE2 = 65, CLI_ID_NOTE3 = 66 };

class CliPage {
public:
    explicit CliPage(CliHost &host);
    void open(bool job);                      // job: Diff to card and nothing else
    void close();
    bool showing() const { return page_ != PG_NONE; }
    bool typing() const { return page_ == PG_KEYS; }
    void poll();
    void touch(bool down, int x, int y);
    const WifiScene &scene() const { return scene_; }
    std::string pageName() const;             // "console", "keys", "note", "" for the record
    bool cliOpen() const { return cliOpen_; }
    // the console's lines as the glass shows them: from `top` (the first line shown), CLI_VISIBLE of them
    const std::vector<std::string> &lines() const { return lines_; }
    int top() const { return top_; }
    bool busy() const { return step_ != ST_IDLE; }
    std::string savedAs() const { return savedAs_; }     // the last file written by Diff to card
    std::string wantsToLeaveWith() const;     // for the record: "save" / "exit" / ""

private:
    enum Page { PG_NONE, PG_CONSOLE, PG_KEYS, PG_NOTE };
    enum Step { ST_IDLE, ST_OPENING, ST_COMMAND, ST_DIFF, ST_LEAVING };
    void go(Page p);
    void build();
    void add(WifiItem::Kind kind, int id, int x, int y, int w, int h, const std::string &text);
    WifiItem &last() { return next_.back(); }
    int hit(int x, int y) const;
    void act(int id);
    void key(int id);
    void send(const std::string &cmd, Step step);
    void leave(bool save);
    void print(const std::string &text);      // the flight controller's reply, line by line, into the console
    void say(const std::string &line);        // a line of our own
    void note(const std::string &l1, const std::string &l2, const std::string &l3, const std::string &b1, const std::string &b2, bool bad);
    void finish(bool ok, const std::string &body, const std::string &err);
    std::string fileName();

    CliHost &host_; Page page_; Step step_; WifiScene scene_; std::vector<WifiItem> next_;
    std::vector<std::string> lines_; int top_; bool follow_;
    std::string typed_; int layer_;
    bool job_, cliOpen_, leaveSave_, closeAfter_;
    std::string pending_, diffText_, savedAs_;
    std::string noteL1_, noteL2_, noteL3_, noteB1_, noteB2_; bool noteBad_; int noteFrom_;
    bool down_; int pressed_; int lastX_, lastY_, downY_, dragTop_; bool dragged_; uint32_t seenDown_, repeatAt_; bool repeated_;
    uint32_t serial_, askedAt_;
};

// The reply to one command as the flight controller printed it, made into lines: carriage returns dropped, the prompt
// ("# " alone, or at the end of the last line) and empty lines at the end dropped. Shared with the file written by Diff to card.
void cliLines(const std::string &reply, std::vector<std::string> &out);
std::string cliFileName(const std::string &model, const std::string &stamp, int n);   // "/rfdiff/<Model>_<stamp>.txt", or "..._<n>.txt" with no stamp

}  // namespace ldrc
#endif
