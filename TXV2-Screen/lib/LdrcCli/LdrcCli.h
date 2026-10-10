// LdrcCli - Rotorflight's command line on the transmitter's screen (screen 1.11.41, 10 Oct 2026; Malcolm: "Are we able
// to add CLI?" ... "Yes - let's add save diff to card! And let's do it!").
//
// The flight controller's command line is a text mode of its USB port. The receiver reaches it over the USB cable
// (RXV2 UsbHostMsp, /api/cli: one command per request, the printed reply back; /api/cli/leave: save or exit, either
// of which restarts the flight controller), and the screen reaches the receiver over its Bluetooth pipe. The page is
// the screen's own: a console of what the flight controller printed, a line to type a command on (the keys as the
// WiFi page has them), the usual commands as buttons, "Diff to card" (diff all, kept on the screen's card as a text
// file the configurator can replay), and the two ways out. Opened from the Rotorflight menu ("Command line ...") for
// the console; from the Backup page for a job on its own: "Diff to card", or "Execute diff" (1.11.42, Malcolm, 10 Oct:
// the newest diff file of the model, every command of it sent to the command line, then saved - a restore from text).
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
    virtual std::string newestDiff(const std::string &model) = 0;   // the newest /rfdiff file of the model ("" = none): the stamped ones by their stamp, the numbered by their number
    virtual bool load(const std::string &path, std::string &text) = 0;
};
enum CliJob { CLI_CONSOLE = 0, CLI_TO_CARD = 1, CLI_EXECUTE = 2 };

enum { CLI_ID_CONSOLE = 60, CLI_ID_FIELD = 61, CLI_ID_TITLE = 62, CLI_ID_HINT = 63, CLI_ID_NOTE1 = 64, CLI_ID_NOTE2 = 65, CLI_ID_NOTE3 = 66, CLI_ID_NOTE4 = 67 };

class CliPage {
public:
    explicit CliPage(CliHost &host);
    void open(int job);                       // CliJob: the console, Diff to card on its own, or Execute diff
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
    int sent() const { return sent_; }        // Execute diff: commands sent so far, and how many of them the flight controller refused
    int refused() const { return refused_; }
    std::string wantsToLeaveWith() const;     // for the record: "save" / "exit" / ""

private:
    enum Page { PG_NONE, PG_CONSOLE, PG_KEYS, PG_NOTE };
    enum Step { ST_IDLE, ST_OPENING, ST_COMMAND, ST_DIFF, ST_EXEC, ST_LEAVING };
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
    void note(const std::string &l1, const std::string &l2, const std::string &l3, const std::string &b1, const std::string &b2, bool bad, const std::string &l4 = "");
    void refusal(const std::string &why);     // the receiver's reason, wrapped over three lines under "The command line could not be opened:"
    void finish(bool ok, const std::string &body, const std::string &err);
    std::string fileName();
    void execNext();                          // Execute diff: the next command of the file, or the save

    CliHost &host_; Page page_; Step step_; WifiScene scene_; std::vector<WifiItem> next_;
    std::vector<std::string> lines_; int top_; bool follow_;
    std::string typed_; int layer_;
    int job_; bool cliOpen_, leaveSave_, closeAfter_;
    std::vector<std::string> exec_; size_t execAt_; int sent_, refused_; std::string execFile_;
    std::string pending_, diffText_, savedAs_;
    std::string noteL1_, noteL2_, noteL3_, noteL4_, noteB1_, noteB2_; bool noteBad_; int noteFrom_;
    bool down_; int pressed_; int lastX_, lastY_, downY_, dragTop_; bool dragged_; uint32_t seenDown_, repeatAt_; bool repeated_;
    uint32_t serial_, askedAt_;
};

// The reply to one command as the flight controller printed it, made into lines: carriage returns dropped, the prompt
// ("# " alone, or at the end of the last line) and empty lines at the end dropped. Shared with the file written by Diff to card.
void cliLines(const std::string &reply, std::vector<std::string> &out);
std::string cliFileName(const std::string &model, const std::string &stamp, int n);   // "/rfdiff/<Model>_<stamp>.txt", or "..._<n>.txt" with no stamp
std::string cliModelPrefix(const std::string &model);                                 // "<Model>_" as the file names begin
bool cliNewer(const std::string &a, const std::string &b, const std::string &prefix);  // of two of a model's files (prefix = "/rfdiff/" + cliModelPrefix), is a the newer? (stamped beat numbered; numbered compare as numbers)
// The commands of a diff file: every line that is not empty and not a comment; save / exit / reboot left out (the save is the job's own)
void cliCommands(const std::string &text, std::vector<std::string> &out);
// Words wrapped at spaces into lines of at most `width` characters (a word longer than that is cut), at most `most` lines; the rest ends in " ..."
void cliWrap(const std::string &text, size_t width, size_t most, std::vector<std::string> &out);

}  // namespace ldrc
#endif
