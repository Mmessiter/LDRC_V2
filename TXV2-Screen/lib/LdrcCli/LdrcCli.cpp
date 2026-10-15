// LdrcCli - the command line page's thinking (see LdrcCli.h).
#include "LdrcCli.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <utility>

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
std::string cliFileName(const std::string &model, const std::string &stamp, long long n) {
    const std::string name = cliSafeName(model);
    char b[64];
    if (!stamp.empty()) snprintf(b, sizeof b, "/rfdiff/%s_%s.txt", name.c_str(), stamp.c_str());
    else snprintf(b, sizeof b, "/rfdiff/%s_%lld.txt", name.c_str(), n);
    return b;
}
std::string cliModelPrefix(const std::string &model) { return cliSafeName(model) + "_"; }
static std::string cliInFolder(const std::string &f0) {           // a name as a card may list it (bare, or with the folder) as "/rfdiff/<name>"
    if (f0.rfind("/rfdiff/", 0) == 0) return f0;
    const size_t slash = f0.find_last_of('/');
    return "/rfdiff/" + (slash == std::string::npos ? f0 : f0.substr(slash + 1));
}
long long cliFileKey(const std::string &path, const std::string &prefix) {
    // B22 (10 Oct 2026): "Goblin_700_2026-10-10_0915.txt" began with "Goblin_" and so passed as a diff of "Goblin"; now what
    // follows the model's name must be a stamp or a number and nothing else. B54: a stamp "YYYY-MM-DD_HHMM" is the number
    // YYYYMMDDHHMM, so stamped and numbered files sit on one line of time (see cliTopKey).
    if (path.size() <= prefix.size() + 4 || path.compare(0, prefix.size(), prefix) != 0) return -1;
    std::string tail = path.substr(prefix.size());
    std::string ext = tail.substr(tail.size() - 4); for (auto &c : ext) c = (char) tolower((unsigned char) c);
    if (ext != ".txt") return -1;
    tail.erase(tail.size() - 4);
    if (tail.empty() || tail.size() > 15) return -1;
    std::string digits;
    if (tail.size() == 15 && tail[4] == '-' && tail[7] == '-' && tail[10] == '_') {   // a stamp
        for (size_t i = 0; i < tail.size(); ++i) { if (i == 4 || i == 7 || i == 10) continue; digits.push_back(tail[i]); }
    } else digits = tail;
    if (digits.find_first_not_of("0123456789") != std::string::npos) return -1;
    return strtoll(digits.c_str(), 0, 10);
}
long long cliTopKey(const std::string &model, const std::vector<std::string> &files) {
    const std::string pre = "/rfdiff/" + cliModelPrefix(model);
    long long top = 0;
    for (auto &f0 : files) { const long long k = cliFileKey(cliInFolder(f0), pre); if (k > top) top = k; }
    return top;
}
bool cliNewer(const std::string &a, const std::string &b, const std::string &prefix) {
    const long long ka = cliFileKey(a, prefix), kb = cliFileKey(b, prefix);
    if (ka < 0) return false;
    if (kb < 0) return true;
    return ka > kb;
}
std::string cliNewest(const std::string &model, const std::vector<std::string> &files) {
    const std::string pre = "/rfdiff/" + cliModelPrefix(model);
    std::string best; long long bestKey = -1;
    for (auto &f0 : files) {
        const std::string f = cliInFolder(f0);
        const long long k = cliFileKey(f, pre);
        if (k < 0) continue;                                        // (another model's, or not a diff file)
        if (k > bestKey) { bestKey = k; best = f; }
    }
    return best;
}
void cliModelDiffs(const std::string &model, const std::vector<std::string> &files, std::vector<std::string> &out) {
    const std::string pre = "/rfdiff/" + cliModelPrefix(model);
    std::vector<std::pair<long long, std::string> > found;
    for (auto &f0 : files) {
        const std::string f = cliInFolder(f0);
        const long long k = cliFileKey(f, pre);
        if (k >= 0) found.push_back(std::make_pair(k, f));
    }
    std::sort(found.begin(), found.end(), [](const std::pair<long long, std::string> &a, const std::pair<long long, std::string> &b) { return a.first > b.first; });
    out.clear();
    for (auto &kv : found) out.push_back(kv.second);
}
std::string cliDiffWhen(const std::string &path) {
    // the stamp is the name's last 15 characters before the dot: "2026-10-15_1548"
    const size_t dot = path.rfind('.');
    if (dot == std::string::npos || dot < 15) return "";
    const std::string t = path.substr(dot - 15, 15);
    for (size_t i = 0; i < t.size(); ++i) {
        const bool sep = i == 4 || i == 7 || i == 10;
        if (sep ? t[i] != (i == 10 ? '_' : '-') : (t[i] < '0' || t[i] > '9')) return "";
    }
    static const char *MONTHS[12] = { "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };
    const int month = atoi(t.substr(5, 2).c_str()), day = atoi(t.substr(8, 2).c_str());
    if (month < 1 || month > 12 || day < 1 || day > 31) return "";
    char b[40]; snprintf(b, sizeof b, "%d %s %s  %s:%s", day, MONTHS[month - 1], t.substr(0, 4).c_str(), t.substr(11, 2).c_str(), t.substr(13, 2).c_str());
    return b;
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
    // 1.11.55 (Malcolm's photo, 10 Oct: 347 lines, first "# version", last "save", "batch end NO"): a Rotorflight 4.6 diff all
    // begins "# version" (the receiver drops the echoed command) and ENDS WITH "save", not "batch end" - so the end is not
    // asked for. The receiver (0.9.883) sends 200 only once the flight controller's prompt is back: that is what says the
    // reply is whole. Here: a diff's head, and settings in it. (1.11.70: an ###ERROR line in it no longer refuses it - see
    // LdrcCli.h; a reply that is only the command and an error has no settings, and is still no diff.)
    bool head = false, settings = false;
    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string &l = lines[i];
        if (i < 5 && (l.find("diff") != std::string::npos || l.find("# version") != std::string::npos)) head = true;
        if (l == "batch start" || l == "save" || l.rfind("set ", 0) == 0 || l.rfind("feature ", 0) == 0 || l.rfind("board_name", 0) == 0) settings = true;
    }
    return head && settings && lines.size() >= 3;
}
void cliDiffErrors(const std::vector<std::string> &lines, std::vector<std::string> &out) {
    out.clear();
    for (auto &l : lines) if (l.find("###ERROR") != std::string::npos) out.push_back(l);
}
std::string cliErrorWords(const std::string &line) {
    std::string t = line;
    while (!t.empty() && (t[0] == '#' || t[0] == ' ')) t.erase(0, 1);
    while (!t.empty() && (t.back() == '#' || t.back() == ' ' || t.back() == '\r')) t.pop_back();
    const size_t c = t.find("CORRUPTED CONFIG: ");                     // (Rotorflight's cli.c: a value its table has no word for)
    if (c != std::string::npos) return "a setting out of range: " + t.substr(c + 18);
    return t;
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
enum { ID_CLOSE = 1, ID_CANCEL, ID_SEND, ID_NOTE1, ID_NOTE2, ID_PREV, ID_NEXT,
       ID_LOWER = 90, ID_UPPER, ID_SYMBOLS, ID_SPACE, ID_DELETE, ID_KEY = 100, ID_PICK = 300 };
static const size_t PICK_ROWS = 6;                                   // (the WiFi page's list: six rows of 58 from y 64, above the buttons' row)
static const char *LAYERS[3][4] = {
    { "1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm._=" },
    { "1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM._=" },
    { "!\"#$%&'()*", "+,-./:;<=>", "?@[\\]^_`{|", "}~        " } };
static const int CON_X = 14, CON_Y = 64, CON_W = 772, CON_H = 338;   // the console (1.11.44: across the page; a finger scrolls it, as the help pages; on the pages' 14 px margins, down to the buttons' row)

CliPage::CliPage(CliHost &host)
    : host_(host), page_(PG_NONE), step_(ST_IDLE), top_(0), follow_(true), layer_(0), job_(0), cliOpen_(false), leaveSave_(false), closeAfter_(false), closing_(false), changed_(false), waitUntil_(0), waitMs_(0), wasReady_(false), more_(false), moreAt_(0), moreSince_(0), moreLines_(0),
      requested_(false), batchOpen_(false), execAt_(0), sent_(0), refused_(0), pickFirst_(0), noteBad_(false), noteFrom_(0), down_(false), pressed_(0), lastX_(0), lastY_(0), downY_(0), dragTop_(0), dragged_(false), seenDown_(0), repeatAt_(0), repeated_(false), serial_(1), askedAt_(0) {}

std::string CliPage::pageName() const {
    static const char *names[] = { "", "console", "keys", "note", "pick" };
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
        add(WifiItem::TITLE, CLI_ID_TITLE, 16, 6, 610, 48, "Command line (Rotorflight)");
        { std::string h = busy ? "Working ..." : "";
          if (step_ == ST_EXEC) { char b[32]; snprintf(b, sizeof b, "%d of %u", sent_, (unsigned) exec_.size()); h = b; }
          else if (more_) { char b[32]; snprintf(b, sizeof b, "%u lines ...", (unsigned) moreLines_); h = b; }
          add(WifiItem::TEXT, CLI_ID_HINT, 630, 6, 164, 48, h); last().strong = true; }
        add(WifiItem::ROW, CLI_ID_CONSOLE, CON_X, CON_Y, CON_W, CON_H, "");   // (drawn by the screen as the console: ROW only so a touch lands on it)
        // (the line to type on and OK share the buttons' row, y 414: OK where it is on every page)
        add(WifiItem::FIELD, CLI_ID_FIELD, 14, 414, 577, 56, typed_); last().hint = "Touch here to type a command"; last().enabled = !busy;
        add(WifiItem::BUTTON, ID_CLOSE, 605, 414, 180, 56, "OK"); last().enabled = !busy;
        break;
    }
    case PG_KEYS: {
        // 1.11.45 (Malcolm, 10 Oct, of the keys: Delete "should be on the right-hand side of the text entry box"; the big key at
        // the bottom right "should be the one for send. And bright yellow is a good colour"): Delete at the box's end, Send the
        // big yellow key at the bottom right. The WiFi page's keys are laid out the same.
        // (the top two rows on the keys' columns, as the WiFi page's keys: Cancel over the first two, Delete over the last two)
        add(WifiItem::BUTTON, ID_CANCEL, 1, 6, 158, 48, "Cancel");
        add(WifiItem::TITLE, CLI_ID_TITLE, 167, 6, 627, 48, "Command");
        add(WifiItem::FIELD, CLI_ID_FIELD, 1, 60, 638, 54, typed_);
        last().hint = "set name = value, get name, diff all, status ...";
        add(WifiItem::KEY, ID_DELETE, 641, 60, 158, 54, "Delete"); last().strong = true; last().enabled = !typed_.empty();
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
    case PG_PICK: {
        // 1.11.74 (Malcolm, 15 Oct: "If it collects many diff files, can I select which to execute?"): the model's diffs,
        // newest first, six at a time, as the WiFi page lists networks; a touch on one asks "Execute ...?" (Cancel there comes
        // back here); OK leaves with nothing done.
        add(WifiItem::TITLE, CLI_ID_TITLE, 16, 6, 768, 50, "Execute which diff?");
        for (size_t i = 0; i < PICK_ROWS && pickFirst_ + i < picks_.size(); ++i) {
            const std::string &f = picks_[pickFirst_ + i];
            std::string when = cliDiffWhen(f);
            if (when.empty()) when = f.substr(f.rfind('/') + 1);    // (made with no clock: its name)
            add(WifiItem::ROW, ID_PICK + (int) (pickFirst_ + i), 14, 64 + (int) i * 58, 772, 54, when);
            last().strong = true; if (pickFirst_ + i == 0) last().note = "newest";
        }
        if (picks_.size() > PICK_ROWS) {
            add(WifiItem::BUTTON, ID_PREV, 408, 414, 86, 56, "<"); last().enabled = pickFirst_ > 0;
            add(WifiItem::BUTTON, ID_NEXT, 502, 414, 86, 56, ">"); last().enabled = pickFirst_ + PICK_ROWS < picks_.size();
        }
        add(WifiItem::BUTTON, ID_CLOSE, 605, 414, 180, 56, "OK"); last().strong = true;
        break;
    }
    case PG_NOTE: {
        add(WifiItem::TITLE, CLI_ID_TITLE, 16, 6, 768, 50, "Command line"); last().bad = noteBad_;
        add(WifiItem::TEXT, CLI_ID_NOTE1, 20, 150, 760, 40, noteL1_);
        add(WifiItem::TEXT, CLI_ID_NOTE2, 20, 196, 760, 40, noteL2_);
        add(WifiItem::TEXT, CLI_ID_NOTE3, 20, 242, 760, 40, noteL3_);
        add(WifiItem::TEXT, CLI_ID_NOTE4, 20, 288, 760, 40, noteL4_);
        // (two buttons: centred as a pair, the go-ahead on the right; one: OK where every page has it)
        if (!noteB2_.empty()) { add(WifiItem::BUTTON, ID_NOTE2, 110, 414, 280, 56, noteB2_); add(WifiItem::BUTTON, ID_NOTE1, 410, 414, 280, 56, noteB1_); last().strong = true; }   // (the update panel's and the WiFi page's pair)
        else { add(WifiItem::BUTTON, ID_NOTE1, 605, 414, 180, 56, noteB1_); last().strong = true; }
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
void CliPage::sent(const std::string &cmd) {
    // 1.11.56 (Malcolm, 10 Oct: "after executing a command, the screen should scroll automatically down to see what just
    // happened"): a command sent is a request to see its reply, so the console follows again, however far up it was dragged.
    follow_ = true;
    say("# " + cmd);
}
void CliPage::print(const std::string &text) {
    std::vector<std::string> ls; cliLines(text, ls);
    for (auto &l : ls) say(l);
}
void CliPage::note(const std::string &l1, const std::string &l2, const std::string &l3, const std::string &b1, const std::string &b2, bool bad, const std::string &l4) {
    noteL1_ = l1; noteL2_ = l2; noteL3_ = l3; noteL4_ = l4; noteB1_ = b1; noteB2_ = b2; noteBad_ = bad; noteFrom_ = page_;
    go(PG_NOTE);
}
static std::string cliSentence(std::string s) {                   // words shown as a sentence: a capital first, a full stop last (the words themselves as they came)
    if (!s.empty() && s[0] >= 'a' && s[0] <= 'z') s[0] = (char) (s[0] - 32);
    if (!s.empty() && s.back() != '.' && s.back() != '?' && s.back() != '!') s += ".";
    return s;
}
void CliPage::refusal(const std::string &why) {                   // (the receiver's reasons are plain words: no USB cable, the transmitter linked with the safety off, armed, the FC silent)
    std::vector<std::string> ls; cliWrap(cliSentence(why), 58, 3, ls);
    while (ls.size() < 3) ls.push_back("");
    note("The command line did not open.", ls[0], ls[1], "OK", "", true, ls[2]);
    closeAfter_ = true;
}

void CliPage::execAsk(const std::string &file) {
    execFile_ = file; exec_.clear();
    std::string text;
    if (!host_.load(execFile_, text)) { note("Could not read", execFile_, "", "OK", "", true); closeAfter_ = true; return; }
    cliCommands(text, exec_);
    if (exec_.empty()) { note("Nothing to execute in", execFile_, "(no commands in it).", "OK", "", true); closeAfter_ = true; return; }
    say("Execute " + execFile_ + ": " + std::to_string(exec_.size()) + " commands");
    char l2[80]; snprintf(l2, sizeof l2, "Its %u commands go to the flight controller's command line,", (unsigned) exec_.size());
    note("Execute " + execFile_.substr(execFile_.rfind('/') + 1) + "?", l2, "then save: it restarts with those settings.", "Execute", "Cancel", false);
}

// ------------------------------------------------------------------ open, close, the steps
void CliPage::open(int job) {
    job_ = job; cliOpen_ = false; closeAfter_ = false; closing_ = false; changed_ = false; step_ = ST_IDLE; waitPath_.clear(); waitUntil_ = 0; jobFailed_.clear(); more_ = false; lines_.clear(); top_ = 0; follow_ = true; typed_.clear(); layer_ = 0;
    pending_.clear(); diffText_.clear(); savedAs_.clear(); diffError_.clear(); down_ = false; pressed_ = 0; exec_.clear(); execAt_ = 0; sent_ = 0; refused_ = 0; execFile_.clear(); requested_ = false; batchOpen_ = false;
    picks_.clear(); pickFirst_ = 0;
    if (host_.armed()) { page_ = PG_CONSOLE; note("Not while the model could be flying.", "Put the safety on and the motor off first.", "", "OK", "", true); closeAfter_ = true; return; }
    if (host_.mainBoardBusy()) {                                     // (B52) the main board's backup, restore or write has the pipe; a save or exit would restart the flight controller under it
        page_ = PG_CONSOLE;
        note("The transmitter is busy: a backup, restore or write is running.", "Wait until it has finished, then try again.", "", "OK", "", true);
        closeAfter_ = true; return;
    }
    if (!host_.pipeReady()) {
        page_ = PG_CONSOLE;
        note("No Bluetooth link to the receiver.", "Switch the model on and plug in its USB cable,", "then open the Rotorflight menu (it joins Bluetooth).", "OK", "", true);
        closeAfter_ = true; return;
    }
    wasReady_ = true;
    go(PG_CONSOLE);
    if (job == CLI_EXECUTE) {
        const std::string model = host_.modelName();
        std::vector<std::string> files; host_.listDiffs(files);
        cliModelDiffs(model, files, picks_);
        if (picks_.empty()) {                                        // (1.11.50: what it looked for, and what is there - Malcolm, 10 Oct: Execute found no file after a Diff to card)
            std::string there = files.empty() ? "The folder /rfdiff is empty." : "There: " + files[0].substr(files[0].rfind('/') + 1) + (files.size() > 1 ? " and " + std::to_string(files.size() - 1) + " more" : "");
            note("No diff of " + (model.empty() ? std::string("this model") : model) + " on the screen's card.", "Press Diff to card to make one.", "Looked for /rfdiff/" + cliModelPrefix(model) + "...txt", "OK", "", true, there);   // (what to do first, what was looked for after)
            closeAfter_ = true; return;
        }
        if (picks_.size() > 1) { go(PG_PICK); return; }              // (1.11.74) more than one: the pilot chooses
        execAsk(picks_[0]);
        return;
    }
    if (job == CLI_TO_CARD) { say("Diff to card: asking the flight controller for diff all ..."); send("diff all", ST_DIFF); }
    else send("", ST_OPENING);                                        // (nothing said while it opens: "Working ..." stands in the strip)
}
void CliPage::execNext() {
    if (execAt_ >= exec_.size()) {                                   // every command sent: the save, and the flight controller restarts
        if (refused_ > 0 && batchOpen_) {
            // B53 (10 Oct 2026): Rotorflight refuses "save" while a command batch with errors in it is still open ("PLEASE FIX
            // ERRORS THEN 'SAVE'"), and the receiver's leave does not read the answer - so the page said "Saved all the same" of
            // settings that never were. A Rotorflight 4.6 diff opens its batch and never closes it (it ends with "save"): the
            // batch is closed here first, so the save that follows is done, without the refused lines.
            batchOpen_ = false; exec_.push_back("batch end"); ownCmd_ = true;
            say("Closing the batch first: Rotorflight will not save one with errors still open.");
        } else { say("All sent. Saving ..."); leave(true); return; }
    }
    const std::string &c = exec_[execAt_++];
    sent(c);
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
    if (step == ST_EXEC) {                                             // (B53) is a command batch open on the flight controller?
        std::string low; for (char ch : cmd) { if (ch == ' ' || ch == '\t') { if (!low.empty() && low.back() != ' ') low.push_back(' '); } else low.push_back((char) tolower((unsigned char) ch)); }
        if (low == "batch start") batchOpen_ = true; else if (low == "batch end") batchOpen_ = false;
    }
    const std::string path = "/api/cli?cmd=" + urlEncode(cmd) + "&wait=5000";   // (1.11.53: the receiver answers within 5 s - with 202 and the start, when the flight controller is still printing)
    waitMs_ = 18000;                                                   // (a diff all, every bank, is 20 kB and more: the flight controller's seconds and the Bluetooth's)
    if (host_.ask("GET", path, waitMs_)) requested_ = true;            // (B55: from here on the receiver may have the flight controller's command line open)
    else { waitMethod_ = "GET"; waitPath_ = path; waitUntil_ = host_.ms() + 5000; }   // (busy: tried again in poll(), 5 s)
    build();
}
void CliPage::leave(bool save) {
    leaveSave_ = save; step_ = ST_LEAVING; askedAt_ = host_.ms();
    const std::string path = std::string("/api/cli/leave?save=") + (save ? "1" : "0");
    waitMs_ = 6000;                                                    // (the receiver answers a leave at once; 1.11.56: a receiver that is off is not waited 18 s for)
    if (!host_.ask("POST", path, waitMs_)) { waitMethod_ = "POST"; waitPath_ = path; waitUntil_ = host_.ms() + 5000; }
    build();
}
void CliPage::left(const std::string &how) {
    // how = "": the receiver closed the command line (the flight controller restarts); otherwise why it was given up on -
    // nothing is known to be saved, and the notes say so instead of "restarting"
    const bool sure = how.empty();
    cliOpen_ = false;
    if (!jobFailed_.empty()) {
        // a job that broke down (B55: after the receiver may have opened the line, which has just been left): what happened, in a note
        std::vector<std::string> w; cliWrap(cliSentence(jobFailed_) + (sure ? " The command line was left: nothing changed." : ""), 58, 3, w); while (w.size() < 3) w.push_back("");
        note(job_ == CLI_TO_CARD ? "Diff to card: NOT saved." : job_ == CLI_EXECUTE ? "Execute diff: NOT done, nothing saved." : "The command line did not answer.", w[0], w[1], "OK", "", true, w[2]);
        closeAfter_ = true; return;
    }
    if (job_ == CLI_TO_CARD && !savedAs_.empty() && !diffError_.empty()) {   // (1.11.70) saved, with what the flight controller reported in it
        note("Saved on the screen's card as", savedAs_, "The flight controller reported", "OK", "", true, diffError_); closeAfter_ = true; return;
    }
    if (job_ == CLI_TO_CARD && !savedAs_.empty()) { note("Saved on the screen's card as", savedAs_, sure ? "The flight controller is restarting (nothing changed)." : "(" + how + ": nothing changed on the model)", "OK", "", false); closeAfter_ = true; return; }
    if (job_ == CLI_EXECUTE && leaveSave_ && !exec_.empty()) {
        char l1[80]; snprintf(l1, sizeof l1, "Executed: %d commands sent, %d refused.", sent_, refused_);
        if (!sure) { note(l1, "NOT saved: " + how + ".", "Execute diff again when the model is back.", "OK", "", true); closeAfter_ = true; return; }
        note(l1, refused_ ? "The refused ones are in the console (###ERROR)." : "Saved. The flight controller is restarting with them.", refused_ ? "Saved without them; the flight controller is restarting." : "", "OK", "", refused_ > 0);
        closeAfter_ = true; return;
    }
    changed_ = false;
    if (closing_) { closing_ = false; close(); return; }
    if (!sure) { say("Not left (" + how + "): nothing saved. OK leaves."); build(); return; }
    say(leaveSave_ ? "Saved. The flight controller is restarting." : "Left without saving. The flight controller is restarting.");
    say("Type a command to open it again (once it is back)."); build();
}
std::string CliPage::fileName() {
    const std::string stamp = host_.stamp(), model = host_.modelName();
    if (!stamp.empty()) return cliFileName(model, stamp, 0);
    // no clock (B54): the number after the newest file there is - a stamp counts as its own number - so the file ranks newest, as it is
    std::vector<std::string> files; host_.listDiffs(files);
    const long long top = cliTopKey(model, files);
    for (long long n = top + 1; n < top + 1000; ++n) { const std::string f = cliFileName(model, "", n); if (!host_.exists(f)) return f; }
    return cliFileName(model, "", top + 999);
}
// The answer to the request on its way: what the step does with it
void CliPage::finish(bool ok, const std::string &body, const std::string &err) {
    const Step step = step_; step_ = ST_IDLE;
    if (!ok) {
        // (the receiver's reasons are plain words: no USB cable, armed, the transmitter linked and not safe, the FC silent)
        std::string why = body.empty() ? err : body;
        if (step == ST_OPENING || (job_ == CLI_TO_CARD && step == ST_DIFF) || (job_ == CLI_EXECUTE && step == ST_EXEC && sent_ == 0)) {
            // the receiver's own no (its reason in the body): it opened nothing. No answer at all (B55): the request went, so the
            // receiver may have opened the flight controller's command line - it is left before the page goes (a leave of a line
            // that is not open is answered all the same), else the flight controller cannot arm until the model is power-cycled.
            if (!body.empty() || !requested_ || !host_.pipeReady()) { refusal(why); return; }
            jobFailed_ = why; exec_.clear(); leave(false); return;
        }
        if (step == ST_LEAVING) {
            // 1.11.56 (Malcolm, 10 Oct: "switching off the receiver leaves the transmitter unable to depart from the page. I had
            // to switch off"): a receiver that has gone is not asked again - the page does what it would have (the receiver
            // leaves an idle command line by itself); one that is there but does not answer is left on the pilot's word.
            if (!host_.pipeReady()) { left("the receiver has gone"); return; }
            std::vector<std::string> w; cliWrap("Not left: " + why, 56, 2, w); while (w.size() < 2) w.push_back("");
            note(w[0], w[1], "Leave anyway? The receiver keeps its command line open", "Leave anyway", "Stay", true, "until it is left again, or the model is switched off.");
            return;
        }
        if (step == ST_EXEC) { char b[80]; snprintf(b, sizeof b, "Stopped at command %d of %u: ", sent_ + 1, (unsigned) exec_.size()); say(b + why); say("Nothing saved. OK leaves it - or Execute diff again."); exec_.clear(); build(); return; }
        if (!host_.pipeReady()) { say("The receiver has gone. OK leaves."); build(); return; }
        say("No answer: " + why); build(); return;
    }
    if (step == ST_LEAVING) { left(""); return; }
    cliOpen_ = true;
    if (step == ST_EXEC) {
        if (ownCmd_) ownCmd_ = false; else sent_++;                  // (the page's own "batch end" is not one of the file's commands)
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
            if (job_ == CLI_TO_CARD) {
                print(body);
                // 1.11.54: what came, in the note - the first and last lines, and the batch marks - so the cut can be seen (10 Oct: 347 lines four times)
                bool bs = false, be = false, err = false; for (auto &l : ls) { if (l == "batch start") bs = true; if (l == "batch end") be = true; if (l.find("###ERROR") != std::string::npos) err = true; }
                std::string first = ls.empty() ? "" : ls.front().substr(0, 24), last = ls.empty() ? "" : ls.back().substr(0, 24);
                jobFailed_ = "not a whole diff: " + std::to_string(ls.size()) + " lines, first \"" + first + "\", last \"" + last + "\"; batch start " + (bs ? "yes" : "NO") + ", batch end " + (be ? "yes" : "NO") + (err ? ", an ###ERROR in it" : "");
                leave(false); return;
            }
            say("That did not look like a diff: not saved."); print(body); build(); return;
        }
        std::string errf; const std::string name = fileName();
        if (!host_.save(name, text, errf)) {
            if (job_ == CLI_TO_CARD) { jobFailed_ = "the card would not keep " + name + ": " + errf; leave(false); return; }
            say("Could not save " + name + ": " + errf); print(body); build(); return;
        }
        savedAs_ = name;
        { std::vector<std::string> errs; cliDiffErrors(ls, errs);      // (1.11.70) kept in the file (comments to Execute diff); said
          if (!errs.empty()) diffError_ = cliErrorWords(errs[0]) + (errs.size() > 1 ? " (and " + std::to_string(errs.size() - 1) + " more in the file)" : ""); }
        char b[80]; snprintf(b, sizeof b, "Saved: %s (%u lines)", name.c_str(), (unsigned) ls.size());
        if (job_ != CLI_TO_CARD) { print(body); say(b); if (!diffError_.empty()) say("The flight controller reported " + diffError_); build(); return; }
        say(b); if (!diffError_.empty()) say("The flight controller reported " + diffError_);
        leave(false);                                               // the job: and out again (the FC restarts; nothing was changed)
        return;
    }
    print(body);                                                    // a command's reply
    build();
}
void CliPage::poll() {
    if (page_ == PG_NONE) return;
    const bool ready = host_.pipeReady();                             // (1.11.56, Malcolm: "switching off the receiver leaves the transmitter unable to depart from the page")
    if (wasReady_ && !ready && step_ == ST_IDLE) { say("The receiver has gone. OK leaves."); build(); }   // (on the keys or a note: in the console on return)
    wasReady_ = ready;
    if (step_ != ST_IDLE && !waitPath_.empty()) {                    // (1.11.51) the pipe was busy: again, until it takes it or 5 s have gone
        if (!host_.pipeReady()) { waitPath_.clear(); finish(false, "", "the receiver is not joined"); return; }   // (1.11.56: no 5 s for a receiver that has gone)
        if (host_.ask(waitMethod_, waitPath_, waitMs_)) { waitPath_.clear(); askedAt_ = host_.ms(); requested_ = true; }
        else if ((int32_t) (host_.ms() - waitUntil_) >= 0) { waitPath_.clear(); finish(false, "", "the Bluetooth pipe stayed busy"); }
        return;
    }
    if (step_ != ST_IDLE && more_ && moreAt_ && (int32_t) (host_.ms() - moreAt_) >= 0) {   // (1.11.53) the rest of a long reply
        if (host_.ask("GET", "/api/cli/out", 6000)) moreAt_ = 0; else if (host_.ms() - moreSince_ > 90000) { more_ = false; finish(false, "", "the reply never ended"); }
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
void CliPage::cancelTouch() {
    // B59 (10 Oct 2026): a corner held for the radios or the workshop door is a corner, not a press: the finger on the page is
    // forgotten here, so its lift presses nothing and the next tap is a fresh one (before, the press stayed and swallowed it).
    if (!down_) return;
    down_ = false; pressed_ = 0; dragged_ = false; repeated_ = false;
    build();
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
            if (!host_.pipeReady()) { closing_ = true; left("the receiver has gone"); return; }   // (1.11.56: nothing to tell it, nothing can be saved)
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
                if (!cliOpen_) { sent(cmd); say("The command line is not open: type a command first."); build(); return; }
                sent(cmd); closing_ = false; leave(low == "save"); return;
            }
            sent(cmd); send(cmd, ST_COMMAND); return;
        }
        key(id); return;
    }
    case PG_NOTE: {
        if (id == ID_NOTE2) {                                          // "Cancel" / "Stay"
            if (noteB1_ == "Execute") { if (picks_.size() > 1) { exec_.clear(); execFile_.clear(); go(PG_PICK); return; } close(); return; }   // (1.11.74: back to the list to choose again)
            go(PG_CONSOLE); return;
        }
        if (closeAfter_) { close(); return; }
        if (noteB1_ == "Execute") { go(PG_CONSOLE); execNext(); return; }
        if (noteB1_ == "Leave") { go(PG_CONSOLE); closing_ = true; leave(false); return; }
        if (noteB1_ == "Leave anyway") { go(PG_CONSOLE); closing_ = true; left("the receiver did not answer"); return; }   // (1.11.56)
        go(PG_CONSOLE); return;
    }
    case PG_PICK: {
        if (id == ID_CLOSE) { close(); return; }
        if (id == ID_PREV) { pickFirst_ = pickFirst_ >= PICK_ROWS ? pickFirst_ - PICK_ROWS : 0; go(PG_PICK); return; }
        if (id == ID_NEXT) { if (pickFirst_ + PICK_ROWS < picks_.size()) pickFirst_ += PICK_ROWS; go(PG_PICK); return; }
        if (id >= ID_PICK && (size_t) (id - ID_PICK) < picks_.size()) { execAsk(picks_[(size_t) (id - ID_PICK)]); return; }
        break;
    }
    case PG_NONE: break;
    }
    build();
}

}  // namespace ldrc
