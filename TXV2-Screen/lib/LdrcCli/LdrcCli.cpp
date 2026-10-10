// LdrcCli - the command line page's thinking (see LdrcCli.h).
#include "LdrcCli.h"
#include <cstdio>
#include <cstring>

namespace ldrc {

// ------------------------------------------------------------------ the reply as lines, the file's name
void cliLines(const std::string &reply, std::vector<std::string> &out) {
    out.clear();
    std::string cur;
    for (size_t i = 0; i <= reply.size(); ++i) {
        const char c = i < reply.size() ? reply[i] : '\n';
        if (c == '\r') continue;
        if (c == '\n') { out.push_back(cur); cur.clear(); continue; }
        if ((unsigned char) c < 32) continue;
        cur.push_back(c);
    }
    while (!out.empty()) {                                         // the prompt, and nothing after it
        std::string &l = out.back();
        while (!l.empty() && l[l.size() - 1] == ' ') l.erase(l.size() - 1);
        if (l.empty() || l == "#") { out.pop_back(); continue; }
        if (l.size() >= 2 && l.compare(l.size() - 2, 2, " #") == 0) { l.erase(l.size() - 2); continue; }
        break;
    }
}
static std::string cliSafeName(const std::string &model) {
    std::string name;
    for (char c : model) {
        if (name.size() >= 20) break;
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-') name.push_back(c);
        else if (c == ' ' || c == '_') { if (!name.empty() && name[name.size() - 1] != '_') name.push_back('_'); }
    }
    while (!name.empty() && name[name.size() - 1] == '_') name.erase(name.size() - 1);
    if (name.empty()) name = "model";
    return name;
}
std::string cliFileName(const std::string &model, const std::string &stamp, int n) {
    const std::string name = cliSafeName(model);
    char b[64];
    if (!stamp.empty()) snprintf(b, sizeof b, "/rfdiff/%s_%s.txt", name.c_str(), stamp.c_str());
    else snprintf(b, sizeof b, "/rfdiff/%s_%d.txt", name.c_str(), n);
    return b;
}
std::string cliModelPrefix(const std::string &model) { return cliSafeName(model) + "_"; }
static bool cliTail(const std::string &path, const std::string &prefix, std::string &tail, long &num) {   // what follows the model's prefix, without ".txt"; num = it as a number, or -1
    if (path.size() <= prefix.size() || path.compare(0, prefix.size(), prefix) != 0) return false;
    tail = path.substr(prefix.size());
    if (tail.size() > 4 && tail.compare(tail.size() - 4, 4, ".txt") == 0) tail.erase(tail.size() - 4);
    num = -1;
    if (!tail.empty() && tail.find_first_not_of("0123456789") == std::string::npos) num = atol(tail.c_str());
    return true;
}
bool cliNewer(const std::string &a, const std::string &b, const std::string &prefix) {
    std::string ta, tb; long na, nb;
    if (!cliTail(a, prefix, ta, na)) return false;
    if (!cliTail(b, prefix, tb, nb)) return true;
    if (na >= 0 && nb >= 0) return na > nb;
    if (na >= 0) return false;                                      // (a numbered file is older than any stamped one: it was made with no clock)
    if (nb >= 0) return true;
    return ta > tb;                                                 // (stamps, "YYYY-MM-DD_HHMM", sort as time does)
}
std::string cliNewest(const std::string &model, const std::vector<std::string> &files) {
    const std::string pre = "/rfdiff/" + cliModelPrefix(model);
    std::string best;
    for (auto &f0 : files) {
        std::string f = f0;
        if (f.rfind("/rfdiff/", 0) != 0) { const size_t slash = f.find_last_of('/'); f = "/rfdiff/" + (slash == std::string::npos ? f : f.substr(slash + 1)); }
        if (f.size() < pre.size() + 5 || f.compare(0, pre.size(), pre) != 0) continue;
        std::string low = f.substr(f.size() - 4); for (auto &c : low) c = (char) tolower((unsigned char) c);
        if (low != ".txt") continue;
        if (best.empty() || cliNewer(f, best, pre)) best = f;
    }
    return best;
}
void cliCommands(const std::string &text, std::vector<std::string> &out) {
    out.clear();
    std::vector<std::string> ls; cliLines(text, ls);
    for (auto &l : ls) {
        std::string c = l;
        while (!c.empty() && (c[0] == ' ' || c[0] == '\t')) c.erase(0, 1);
        while (!c.empty() && (c[c.size() - 1] == ' ' || c[c.size() - 1] == '\t')) c.erase(c.size() - 1);
        if (c.empty() || c[0] == '#') continue;
        std::string low = c; for (auto &ch : low) ch = (char) tolower((unsigned char) ch);
        if (low == "save" || low == "exit" || low == "reboot" || low == "defaults" || low.rfind("dfu", 0) == 0 || low == "msc") continue;
        if (c.size() > 160) continue;
        out.push_back(c);
    }
}

bool cliReadOnly(const std::string &cmd) {
    static const char *words[] = { "diff", "dump", "get", "status", "version", "help", "tasks", "mcu_id", "bootlog", "sd_info", "flash_info", "gyroregisters",
                                   "dshot_telemetry_info", "rc_smoothing_info", "beacon", "batch", "exit", "save", "reboot", "#", "?" };
    std::string w; for (char c : cmd) { if (c == ' ' || c == '\t') break; w.push_back((char) tolower((unsigned char) c)); }
    for (const char *k : words) if (w == k) return true;
    return false;
}
bool cliDiffWhole(const std::vector<std::string> &lines) {
    bool head = false, start = false, end = false;
    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string &l = lines[i];
        if (i < 5 && l.find("diff") != std::string::npos) head = true;
        if (l.find("###ERROR") != std::string::npos) return false;
        if (l == "batch start") start = true;
        if (l == "batch end") end = true;
    }
    return head && lines.size() >= 3 && (!start || end);
}
void cliWrap(const std::string &text, size_t width, size_t most, std::vector<std::string> &out) {
    out.clear();
    std::string rest = text;
    while (!rest.empty() && out.size() < most) {
        while (!rest.empty() && rest[0] == ' ') rest.erase(0, 1);
        if (rest.size() <= width) { out.push_back(rest); rest.clear(); break; }
        size_t cut = rest.rfind(' ', width);
        if (cut == std::string::npos || cut < width / 2) cut = width;
        out.push_back(rest.substr(0, cut)); rest.erase(0, cut);
    }
    if (!rest.empty() && !out.empty()) {                            // more than fits: the last line ends in dots
        std::string &l = out.back();
        if (l.size() + 4 > width) { const size_t sp = l.rfind(' ', width - 4); l.erase(sp == std::string::npos ? width - 4 : sp); }
        l += " ...";
    }
}

// ------------------------------------------------------------------ the pages: what is where
// The screen is 800 x 480. Ids: 1.. buttons, 60.. the console and its line, 90.. the keys' row, 100.. keys.
enum { ID_CLOSE = 1, ID_CANCEL, ID_SEND, ID_NOTE1, ID_NOTE2,
       ID_LOWER = 90, ID_UPPER, ID_SYMBOLS, ID_SPACE, ID_DELETE, ID_KEY = 100 };
static const char *LAYERS[3][4] = {
    { "1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm._=" },
    { "1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM._=" },
    { "!\"#$%&'()*", "+,-./:;<=>", "?@[\\]^_`{|", "}~        " } };
static const int CON_X = 6, CON_Y = 64, CON_W = 788, CON_H = 312;   // the console (1.11.44: across the page; a finger scrolls it, as the help pages)

CliPage::CliPage(CliHost &host)
    : host_(host), page_(PG_NONE), step_(ST_IDLE), top_(0), follow_(true), layer_(0), job_(0), cliOpen_(false), leaveSave_(false), closeAfter_(false), closing_(false), changed_(false), waitUntil_(0), more_(false), moreAt_(0), moreSince_(0), moreLines_(0),
      execAt_(0), sent_(0), refused_(0), noteBad_(false), noteFrom_(0), down_(false), pressed_(0), lastX_(0), lastY_(0), downY_(0), dragTop_(0), dragged_(false), seenDown_(0), repeatAt_(0), repeated_(false), serial_(1), askedAt_(0) {}

std::string CliPage::pageName() const {
    static const char *names[] = { "", "console", "keys", "note" };
    return names[page_];
}
std::string CliPage::wantsToLeaveWith() const { return step_ == ST_LEAVING ? (leaveSave_ ? "save" : "exit") : ""; }

void CliPage::add(WifiItem::Kind kind, int id, int x, int y, int w, int h, const std::string &text) {
    WifiItem it; it.kind = kind; it.id = id; it.x = x; it.y = y; it.w = w; it.h = h; it.text = text;
    it.pressed = down_ && pressed_ == id;
    next_.push_back(it);
}
void CliPage::go(Page p) { page_ = p; build(); scene_.layout++; }
void CliPage::build() {
    next_.clear();
    const bool busy = step_ != ST_IDLE;
    switch (page_) {
    case PG_NONE: break;
    case PG_CONSOLE: {
        // 1.11.44 (Malcolm, 10 Oct, of the first page: OK at the right "means leave"; the buttons "we can remove for simplicity
        // because the user can type in whatever he wants"; "Open" and "Close" unexplained; Up and Down unneeded, "we can scroll
        // with a finger just as in the help files"): the console, the line to type on, OK. Typed save / exit do what the
        // buttons did; "Working ..." at the right of the strip while the flight controller is being asked.
        add(WifiItem::TITLE, CLI_ID_TITLE, 6, 6, 620, 48, "Command line (Rotorflight)");
        { std::string h = busy ? "Working ..." : "";
          if (step_ == ST_EXEC) { char b[32]; snprintf(b, sizeof b, "%d of %u", sent_, (unsigned) exec_.size()); h = b; }
          else if (more_) { char b[32]; snprintf(b, sizeof b, "%u lines ...", (unsigned) moreLines_); h = b; }
          add(WifiItem::TEXT, CLI_ID_HINT, 630, 6, 164, 48, h); last().strong = true; }
        add(WifiItem::ROW, CLI_ID_CONSOLE, CON_X, CON_Y, CON_W, CON_H, "");   // (drawn by the screen as the console: ROW only so a touch lands on it)
        add(WifiItem::FIELD, CLI_ID_FIELD, 6, 384, 788, 46, typed_); last().hint = "Touch here to type a command"; last().enabled = !busy;
        add(WifiItem::BUTTON, ID_CLOSE, 634, 436, 160, 40, "OK"); last().enabled = !busy;
        break;
    }
    case PG_KEYS: {
        // 1.11.45 (Malcolm, 10 Oct, of the keys: Delete "should be on the right-hand side of the text entry box"; the big key at
        // the bottom right "should be the one for send. And bright yellow is a good colour"): Delete at the box's end, Send the
        // big yellow key at the bottom right. The WiFi page's keys are laid out the same.
        add(WifiItem::BUTTON, ID_CANCEL, 6, 6, 140, 48, "Cancel");
        add(WifiItem::TITLE, CLI_ID_TITLE, 154, 6, 640, 48, "Command");
        add(WifiItem::FIELD, CLI_ID_FIELD, 6, 60, 660, 54, typed_);
        last().hint = "set name = value, get name, diff all, status ...";
        add(WifiItem::KEY, ID_DELETE, 672, 60, 122, 54, "Delete"); last().strong = true; last().enabled = !typed_.empty();
        for (int r = 0; r < 4; ++r)
            for (int c = 0; c < 10; ++c) {
                const char ch = LAYERS[layer_][r][c];
                if (ch == ' ') continue;
                add(WifiItem::KEY, ID_KEY + r * 10 + c, c * 80 + 1, 120 + r * 72, 78, 70, std::string(1, ch));
            }
        add(WifiItem::KEY, ID_LOWER, 1, 408, 108, 70, "abc"); last().strong = true; last().good = layer_ == 0;
        add(WifiItem::KEY, ID_UPPER, 111, 408, 108, 70, "ABC"); last().strong = true; last().good = layer_ == 1;
        add(WifiItem::KEY, ID_SYMBOLS, 221, 408, 108, 70, "#+="); last().strong = true; last().good = layer_ == 2;
        add(WifiItem::KEY, ID_SPACE, 331, 408, 248, 70, "Space"); last().strong = true;
        add(WifiItem::BUTTON, ID_SEND, 581, 408, 218, 70, "Send"); last().strong = true; last().enabled = !typed_.empty();
        break;
    }
    case PG_NOTE: {
        add(WifiItem::TITLE, CLI_ID_TITLE, 16, 6, 768, 50, "Command line"); last().bad = noteBad_;
        add(WifiItem::TEXT, CLI_ID_NOTE1, 20, 150, 760, 40, noteL1_);
        add(WifiItem::TEXT, CLI_ID_NOTE2, 20, 196, 760, 40, noteL2_);
        add(WifiItem::TEXT, CLI_ID_NOTE3, 20, 242, 760, 40, noteL3_);
        add(WifiItem::TEXT, CLI_ID_NOTE4, 20, 288, 760, 40, noteL4_);
        if (!noteB2_.empty()) { add(WifiItem::BUTTON, ID_NOTE2, 200, 412, 250, 56, noteB2_); add(WifiItem::BUTTON, ID_NOTE1, 466, 412, 250, 56, noteB1_); last().strong = true; }
        else { add(WifiItem::BUTTON, ID_NOTE1, 622, 412, 170, 56, noteB1_); last().strong = true; }
        break;
    }
    }
    // what changed is drawn again: an item keeps its serial while nothing about it has
    std::vector<WifiItem> &old = scene_.items;
    for (auto &it : next_) {
        bool same = false;
        for (auto &o : old)
            if (o.id == it.id && o.kind == it.kind && o.x == it.x && o.y == it.y && o.w == it.w && o.h == it.h && o.text == it.text && o.note == it.note && o.hint == it.hint &&
                o.pressed == it.pressed && o.enabled == it.enabled && o.good == it.good && o.strong == it.strong && o.bad == it.bad) { it.serial = o.serial; same = true; break; }
        if (!same) it.serial = serial_++;
    }
    scene_.items = next_;
    if (page_ == PG_CONSOLE) for (auto &it : scene_.items) if (it.id == CLI_ID_CONSOLE) it.serial = serial_++;   // (the console is drawn every time it is built: its lines are not in the item)
}

// ------------------------------------------------------------------ the console
void CliPage::say(const std::string &line) {
    // 1.11.48 (Malcolm, 10 Oct, of a line that ended "(b...": "I'm curious to know what the last word would have been"): a line
    // too long for the console wraps at a space, the rest indented, so nothing is lost. 62 characters of the 24 px font fit
    // the console in ordinary words (the screen still cuts a line of wide letters with dots).
    std::vector<std::string> ls; cliWrap(line, 62, 20, ls);
    for (size_t i = 0; i < ls.size(); ++i) {
        lines_.push_back(i ? "  " + ls[i] : ls[i]);
        while (lines_.size() > CLI_LINES_MAX) lines_.erase(lines_.begin());
    }
    if (follow_) top_ = (int) lines_.size() > CLI_VISIBLE ? (int) lines_.size() - CLI_VISIBLE : 0;
}
void CliPage::print(const std::string &text) {
    std::vector<std::string> ls; cliLines(text, ls);
    for (auto &l : ls) say(l);
}
void CliPage::note(const std::string &l1, const std::string &l2, const std::string &l3, const std::string &b1, const std::string &b2, bool bad, const std::string &l4) {
    noteL1_ = l1; noteL2_ = l2; noteL3_ = l3; noteL4_ = l4; noteB1_ = b1; noteB2_ = b2; noteBad_ = bad; noteFrom_ = page_;
    go(PG_NOTE);
}
void CliPage::refusal(const std::string &why) {                   // (the receiver's reasons are plain words: no USB cable, the transmitter linked with the safety off, armed, the FC silent)
    std::vector<std::string> ls; cliWrap(why, 58, 3, ls);
    while (ls.size() < 3) ls.push_back("");
    note("The command line could not be opened:", ls[0], ls[1], "OK", "", true, ls[2]);
    closeAfter_ = true;
}

// ------------------------------------------------------------------ open, close, the steps
void CliPage::open(int job) {
    job_ = job; cliOpen_ = false; closeAfter_ = false; closing_ = false; changed_ = false; step_ = ST_IDLE; waitPath_.clear(); waitUntil_ = 0; jobFailed_.clear(); more_ = false; lines_.clear(); top_ = 0; follow_ = true; typed_.clear(); layer_ = 0;
    pending_.clear(); diffText_.clear(); savedAs_.clear(); down_ = false; pressed_ = 0; exec_.clear(); execAt_ = 0; sent_ = 0; refused_ = 0; execFile_.clear();
    if (host_.armed()) { page_ = PG_CONSOLE; note("Not while the model could be flying.", "Safety on, motor off.", "", "OK", "", true); closeAfter_ = true; return; }
    if (!host_.pipeReady()) {
        page_ = PG_CONSOLE;
        note("No Bluetooth link to the receiver.", "The command line needs the model on, its USB cable", "in, and the screen's Bluetooth joined (the Rotorflight menu).", "OK", "", true);
        closeAfter_ = true; return;
    }
    go(PG_CONSOLE);
    if (job == CLI_EXECUTE) {
        const std::string model = host_.modelName();
        std::vector<std::string> files; host_.listDiffs(files);
        execFile_ = cliNewest(model, files);
        std::string text;
        if (execFile_.empty()) {                                     // (1.11.50: what it looked for, and what is there - Malcolm, 10 Oct: Execute found no file after a Diff to card)
            std::string there = files.empty() ? "The folder /rfdiff is empty." : "There: " + files[0].substr(files[0].rfind('/') + 1) + (files.size() > 1 ? " and " + std::to_string(files.size() - 1) + " more" : "");
            note("No diff of " + (model.empty() ? std::string("this model") : model) + " on the screen's card.", "Looked for /rfdiff/" + cliModelPrefix(model) + "...txt", there, "OK", "", true, "Diff to card makes one.");
            closeAfter_ = true; return;
        }
        if (!host_.load(execFile_, text)) { note("Could not read", execFile_, "", "OK", "", true); closeAfter_ = true; return; }
        cliCommands(text, exec_);
        if (exec_.empty()) { note("Nothing to execute in", execFile_, "(no commands in it).", "OK", "", true); closeAfter_ = true; return; }
        say("Execute " + execFile_ + ": " + std::to_string(exec_.size()) + " commands");
        char l2[80]; snprintf(l2, sizeof l2, "Its %u commands go to the flight controller's command line,", (unsigned) exec_.size());
        note("Execute " + execFile_.substr(execFile_.rfind('/') + 1) + "?", l2, "then save: it restarts with those settings.", "Execute", "Cancel", false);
        return;
    }
    if (job == CLI_TO_CARD) { say("Diff to card: asking the flight controller for diff all ..."); send("diff all", ST_DIFF); }
    else send("", ST_OPENING);                                        // (nothing said while it opens: "Working ..." stands in the strip)
}
void CliPage::execNext() {
    if (execAt_ >= exec_.size()) {                                   // every command sent: the save, and the flight controller restarts
        say("All sent. Saving ..."); leave(true); return;
    }
    const std::string &c = exec_[execAt_++];
    say("# " + c);
    send(c, ST_EXEC);
}
void CliPage::close() { page_ = PG_NONE; step_ = ST_IDLE; scene_.items.clear(); scene_.layout++; }

static std::string urlEncode(const std::string &s) {
    std::string o;
    for (unsigned char c : s) {
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') o.push_back((char) c);
        else { char b[4]; snprintf(b, sizeof b, "%%%02X", c); o += b; }
    }
    return o;
}
void CliPage::send(const std::string &cmd, Step step) {
    pending_ = cmd; step_ = step; askedAt_ = host_.ms();
    if ((step == ST_COMMAND || step == ST_EXEC) && !cliReadOnly(cmd)) changed_ = true;
    const std::string path = "/api/cli?cmd=" + urlEncode(cmd) + "&wait=5000";   // (1.11.53: the receiver answers within 5 s - with 202 and the start, when the flight controller is still printing)
    if (!host_.ask("GET", path)) { waitMethod_ = "GET"; waitPath_ = path; waitUntil_ = host_.ms() + 5000; }   // (busy: tried again in poll(), 5 s)
    build();
}
void CliPage::leave(bool save) {
    leaveSave_ = save; step_ = ST_LEAVING; askedAt_ = host_.ms();
    const std::string path = std::string("/api/cli/leave?save=") + (save ? "1" : "0");
    if (!host_.ask("POST", path)) { waitMethod_ = "POST"; waitPath_ = path; waitUntil_ = host_.ms() + 5000; }
    build();
}
std::string CliPage::fileName() {
    const std::string stamp = host_.stamp(), model = host_.modelName();
    if (!stamp.empty()) return cliFileName(model, stamp, 0);
    for (int n = 1; n < 1000; ++n) { const std::string f = cliFileName(model, "", n); if (!host_.exists(f)) return f; }
    return cliFileName(model, "", 999);
}
// The answer to the request on its way: what the step does with it
void CliPage::finish(bool ok, const std::string &body, const std::string &err) {
    const Step step = step_; step_ = ST_IDLE;
    if (!ok) {
        // (the receiver's reasons are plain words: no USB cable, armed, the transmitter linked and not safe, the FC silent)
        std::string why = body.empty() ? err : body;
        if (step == ST_OPENING || (job_ == CLI_TO_CARD && step == ST_DIFF) || (job_ == CLI_EXECUTE && step == ST_EXEC && sent_ == 0)) { refusal(why); return; }
        if (step == ST_LEAVING) { say("Not left: " + why); build(); return; }
        if (step == ST_EXEC) { char b[80]; snprintf(b, sizeof b, "Stopped at command %d of %u: ", sent_ + 1, (unsigned) exec_.size()); say(b + why); say("Nothing saved. OK leaves it - or Execute diff again."); exec_.clear(); build(); return; }
        say("No answer: " + why); build(); return;
    }
    if (step == ST_LEAVING) {
        cliOpen_ = false;
        if (job_ == CLI_TO_CARD && !jobFailed_.empty()) {
            std::vector<std::string> w; cliWrap(jobFailed_, 58, 2, w); while (w.size() < 2) w.push_back("");
            note("Diff to card: NOT saved -", w[0], w[1], "OK", "", true); closeAfter_ = true; return;
        }
        if (job_ == CLI_TO_CARD && !savedAs_.empty()) { note("Saved on the screen's card as", savedAs_, "The flight controller is restarting (nothing changed).", "OK", "", false); closeAfter_ = true; return; }
        if (job_ == CLI_EXECUTE && leaveSave_ && !exec_.empty()) {
            char l1[80]; snprintf(l1, sizeof l1, "Executed: %d commands sent, %d refused.", sent_, refused_);
            note(l1, refused_ ? "The refused ones are in the console (###ERROR)." : "Saved. The flight controller is restarting with them.", refused_ ? "Saved all the same; the flight controller is restarting." : "", "OK", "", refused_ > 0);
            closeAfter_ = true; return;
        }
        changed_ = false;
        if (closing_) { closing_ = false; close(); return; }
        say(leaveSave_ ? "Saved. The flight controller is restarting." : "Left without saving. The flight controller is restarting.");
        say("Type a command to open it again (once it is back)."); build(); return;
    }
    cliOpen_ = true;
    if (step == ST_EXEC) {
        sent_++;
        std::vector<std::string> ls; cliLines(body, ls);
        bool bad = false;
        const std::string &was = exec_[execAt_ - 1];
        for (auto &l : ls) { if (l.find("###ERROR") != std::string::npos || l.find("Invalid") != std::string::npos || l.find("UNKNOWN COMMAND") != std::string::npos) bad = true; if (l != was) say(l); }   // (the echo of the command is not repeated)
        if (bad) refused_++;
        execNext(); return;
    }
    if (step == ST_OPENING) { say("Type a command"); build(); return; }   // (1.11.49, Malcolm: "If they've got this far, they will know that already, so let's keep the words a bit shorter")
    if (step == ST_DIFF) {
        std::vector<std::string> ls; cliLines(body, ls);
        std::string text;
        for (auto &l : ls) { text += l; text += '\n'; }
        diffText_ = text;
        if (!cliDiffWhole(ls)) {
            if (job_ == CLI_TO_CARD) { print(body); jobFailed_ = "the flight controller's answer was not a whole diff (" + std::to_string(ls.size()) + " lines)"; leave(false); return; }
            say("That did not look like a diff: not saved."); print(body); build(); return;
        }
        std::string errf; const std::string name = fileName();
        if (!host_.save(name, text, errf)) {
            if (job_ == CLI_TO_CARD) { jobFailed_ = "the card would not keep " + name + ": " + errf; leave(false); return; }
            say("Could not save " + name + ": " + errf); print(body); build(); return;
        }
        savedAs_ = name;
        char b[80]; snprintf(b, sizeof b, "Saved: %s (%u lines)", name.c_str(), (unsigned) ls.size());
        if (job_ != CLI_TO_CARD) { print(body); say(b); build(); return; }
        say(b); leave(false);                                       // the job: and out again (the FC restarts; nothing was changed)
        return;
    }
    print(body);                                                    // a command's reply
    build();
}
void CliPage::poll() {
    if (page_ == PG_NONE) return;
    if (step_ != ST_IDLE && !waitPath_.empty()) {                    // (1.11.51) the pipe was busy: again, until it takes it or 5 s have gone
        if (host_.ask(waitMethod_, waitPath_)) { waitPath_.clear(); askedAt_ = host_.ms(); }
        else if ((int32_t) (host_.ms() - waitUntil_) >= 0) { waitPath_.clear(); finish(false, "", "the Bluetooth pipe stayed busy"); }
        return;
    }
    if (step_ != ST_IDLE && more_ && moreAt_ && (int32_t) (host_.ms() - moreAt_) >= 0) {   // (1.11.53) the rest of a long reply
        if (host_.ask("GET", "/api/cli/out")) moreAt_ = 0; else if (host_.ms() - moreSince_ > 90000) { more_ = false; finish(false, "", "the reply never ended"); }
        return;
    }
    if (step_ != ST_IDLE && !(more_ && moreAt_)) {                   // (a fetch of the rest is scheduled: no request is out, nothing to look for)
        const int st = host_.askState();
        if (st == 1 && host_.askCode() == 202 && (step_ == ST_COMMAND || step_ == ST_DIFF || step_ == ST_EXEC)) {   // the start only: the flight controller still prints
            if (!more_) { more_ = true; moreSince_ = host_.ms(); }
            std::vector<std::string> ls; cliLines(host_.askBody(), ls); moreLines_ = ls.size();
            if (host_.ms() - moreSince_ > 90000) { more_ = false; finish(false, "", "the reply never ended (" + std::to_string(moreLines_) + " lines)"); return; }
            moreAt_ = host_.ms() + 500; askedAt_ = host_.ms(); build(); return;
        }
        if (st == 1) { more_ = false; finish(host_.askCode() == 200, host_.askBody(), ""); }
        else if (st == -1) { more_ = false; finish(false, "", host_.askError()); }
        else if (host_.ms() - askedAt_ > 20000) { more_ = false; finish(false, "", "no answer in 20 s"); }
    }
}

// ------------------------------------------------------------------ touches
int CliPage::hit(int x, int y) const {
    for (size_t i = scene_.items.size(); i > 0; --i) {
        const WifiItem &it = scene_.items[i - 1];
        if (it.kind != WifiItem::BUTTON && it.kind != WifiItem::KEY && it.kind != WifiItem::ROW && it.kind != WifiItem::FIELD) continue;
        if (!it.enabled) continue;
        if (x >= it.x && x < it.x + it.w && y >= it.y && y < it.y + it.h) return it.id;
    }
    return 0;
}
void CliPage::touch(bool down, int x, int y) {
    if (page_ == PG_NONE) return;
    const uint32_t now = host_.ms();
    if (down) {
        seenDown_ = now; lastX_ = x; lastY_ = y;
        if (!down_) {
            down_ = true; repeated_ = false; dragged_ = false; downY_ = y; dragTop_ = top_;
            pressed_ = hit(x, y); repeatAt_ = now + 600;
            if (pressed_ && pressed_ != CLI_ID_CONSOLE) build();
        } else if (pressed_ == CLI_ID_CONSOLE) {                      // a finger moving up or down the console scrolls it
            const int lines = (downY_ - y) / 26;
            int t = dragTop_ + lines;
            const int most = (int) lines_.size() > CLI_VISIBLE ? (int) lines_.size() - CLI_VISIBLE : 0;
            if (t < 0) t = 0; if (t > most) t = most;
            if (t != top_) { top_ = t; follow_ = top_ >= most; dragged_ = true; build(); }
        } else if (pressed_ == ID_DELETE && (int32_t) (now - repeatAt_) >= 0 && hit(x, y) == ID_DELETE) {
            repeated_ = true; repeatAt_ = now + 110; key(ID_DELETE);
        }
        return;
    }
    if (!down_ || now - seenDown_ <= 80) return;
    down_ = false;
    const int id = pressed_; pressed_ = 0;
    if (!id) return;
    if (id == CLI_ID_CONSOLE) { if (!dragged_) build(); return; }
    if (hit(lastX_, lastY_) == id && !repeated_) act(id);
    else build();
}
void CliPage::key(int id) {
    if (id == ID_DELETE) { if (!typed_.empty()) typed_.erase(typed_.size() - 1); }
    else if (id == ID_SPACE) { if (typed_.size() < CLI_CMD_MAX) typed_.push_back(' '); }
    else if (id == ID_LOWER) layer_ = 0; else if (id == ID_UPPER) layer_ = 1; else if (id == ID_SYMBOLS) layer_ = 2;
    else if (id >= ID_KEY && id < ID_KEY + 40) {
        const char ch = LAYERS[layer_][(id - ID_KEY) / 10][(id - ID_KEY) % 10];
        if (ch != ' ' && typed_.size() < CLI_CMD_MAX) typed_.push_back(ch);
    }
    build();
}
void CliPage::act(int id) {
    switch (page_) {
    case PG_CONSOLE: {
        if (step_ != ST_IDLE) { build(); return; }
        if (id == CLI_ID_FIELD) { go(PG_KEYS); return; }
        if (id == ID_CLOSE) {                                           // OK: out. The line still open with nothing changed: left (the flight controller restarts, as it must); something changed: asked
            if (!cliOpen_) { close(); return; }
            if (!changed_) { closing_ = true; leave(false); return; }   // (Malcolm, 10 Oct: "I'm invited to save, even though I have changed nothing")
            note("Leave the command line without saving?", "Type save first to keep what you changed.", "The flight controller restarts either way.", "Leave", "Stay", false);
            return;
        }
        break;
    }
    case PG_KEYS: {
        if (id == ID_CANCEL) { typed_.clear(); go(PG_CONSOLE); return; }
        if (id == ID_SEND) {
            std::string cmd = typed_;
            while (!cmd.empty() && cmd[cmd.size() - 1] == ' ') cmd.erase(cmd.size() - 1);
            while (!cmd.empty() && cmd[0] == ' ') cmd.erase(0, 1);
            typed_.clear(); go(PG_CONSOLE);
            if (cmd.empty()) return;
            const std::string low = [&] { std::string l = cmd; for (auto &c : l) c = (char) tolower((unsigned char) c); return l; }();
            if (low == "save" || low == "exit" || low == "reboot") {      // the receiver takes these on its own line (and the flight controller restarts)
                if (!cliOpen_) { say("# " + cmd); say("The command line is not open: type a command first."); build(); return; }
                say("# " + cmd); closing_ = false; leave(low == "save"); return;
            }
            say("# " + cmd); send(cmd, ST_COMMAND); return;
        }
        key(id); return;
    }
    case PG_NOTE: {
        if (id == ID_NOTE2) { if (noteB1_ == "Execute") { close(); return; } go(PG_CONSOLE); return; }   // "Cancel" / "Stay"
        if (closeAfter_) { close(); return; }
        if (noteB1_ == "Execute") { go(PG_CONSOLE); execNext(); return; }
        if (noteB1_ == "Leave") { go(PG_CONSOLE); closing_ = true; leave(false); return; }
        go(PG_CONSOLE); return;
    }
    case PG_NONE: break;
    }
    build();
}

}  // namespace ldrc
