#!/usr/bin/env python3
"""Host test of the log and help viewer (Malcolm, 19 Oct 2026, from the field: "when I scrolled to the end by hitting the
end button, I could not scroll up with my finger any more. It was stuck"). include/LogFilesDisplay.h is compiled on the
Mac AS IT IS, over a fake card and a fake screen: the LogText slide text of page 44 (348 px tall, a 6 px border, font 2 =
24 px: 14 lines show), scrolled by a finger as the screen does it (hmi/pages/44.json: the release prints val_y and
maxval_y to the main board's function 14). Files of every length, lines short and long, a log shaped like a real day's,
and the real logs when the SSD is here. For each: Bottom, then a finger up to the top; Top, a finger down to the end and up
again; Bottom again. Every step must move, every line shown must be the file's line, and no scroll position sent may lie
past the text (the screen would show a blank box).
   python3 dev/test_logview/test_logview.py"""
import os, random, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDR = os.path.join(ROOT, 'TransmitterCode', 'include', 'LogFilesDisplay.h')
LIVE = '/Volumes/2TB SSD/ClaudeScratch/calib/live'

FAKE_DEFS = r'''
// The test's stand-in for 1Definitions.h: what LogFilesDisplay.h uses, nothing more.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <map>
#include <vector>
#include <algorithm>
#define FLASHMEM
#define DMAMEM                                         // B149: the seek table lives in RAM2 on the Teensy
#define FASTRUN
#define MAXFILELEN (1024 * 3)
#define LOGVIEW 23
#define FILE_READ 0
#define FILE_WRITE 1
struct FakeFs { std::map<std::string, std::string> files; };
extern FakeFs fs;
struct File {                                            // SdFat's File, as far as the viewer uses it
    std::string name; size_t pos = 0; bool ok = false;
    std::string &d() { return fs.files[name]; }
    operator bool() const { return ok; }
    bool seek(uint32_t p) { if (!ok || p > d().size()) return false; pos = p; return true; }
    int read(void *buf, size_t n) { if (!ok) return -1; const size_t k = std::min(n, d().size() - pos); memcpy(buf, d().data() + pos, k); pos += k; return (int) k; }
    size_t write(const void *buf, size_t n) { if (!ok) return 0; d().append((const char *) buf, n); pos = d().size(); return n; }
    void close() { ok = false; pos = 0; }
    size_t size() { return ok ? d().size() : 0; }
};
struct FakeSd {
    bool remove(const char *name) { return fs.files.erase(name) > 0; }
    File open(const char *name, int mode) {
        File f; auto it = fs.files.find(name);
        if (it == fs.files.end()) { if (mode != FILE_WRITE) return f; it = fs.files.emplace(name, std::string()).first; }
        f.name = name; f.ok = true; f.pos = mode == FILE_WRITE ? it->second.size() : 0; return f;
    }
};
extern FakeSd SD;
extern int Previous_Current_Y, Max_Y, CurrentView; extern bool LogFileOpen, ReadingaFile; extern File LogFileNumber;
extern char TextFileName[40]; extern char pLogView[];
void ShowLogFileNew(uint16_t LinesCounter); uint16_t ReadAFewLines(); void LogVIEWNew();
void SendOtherValue(char *nbox, int value); int GetIntFromTextIn(uint8_t offset); void SendText(char *tbox, char *NewWord);
void SendText1(char *tbox, char *NewWord); void SendCommand(char *tbox); int InStrng(char *text1, char *text2);
void DelayWithDog(uint32_t HowLong); File OpenTextFileForReading(); void KickTheDog(); void CloseLogFile(); void ClearFilesList(); void MakeTextFileName();
'''

PROG = r'''
#include "1Definitions.h"
#include "LogFilesDisplay.h"                            // the real one, copied beside this file
FakeFs fs; FakeSd SD; int Previous_Current_Y = 0, Max_Y = 666, CurrentView = 0; bool LogFileOpen = false, ReadingaFile = false;
File LogFileNumber; char TextFileName[40] = ""; char pLogView[] = "page LogView";
static int checks = 0, fails = 0;
#define CHECK(c, what) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %d: %s [%s]\n", __LINE__, #c, what); } } while (0)

// ---- the screen: page 44's LogText, as the emulator draws and drags it (h 348, border 6, font 2 = 24 px)
static const int BOX = 348 - 2 * 6, FH = 24;
static bool clampY = true;                               // the screen of 1.11.96 keeps val_y within the text; the one before did not
static std::string boxTxt; static int boxY = 0, overMax = 0;
static std::vector<std::string> boxLines() {              // textLines(): split at \r\n or \n; a final newline adds no line
    std::vector<std::string> out; size_t i = 0;
    while (i < boxTxt.size()) {
        size_t e = boxTxt.find_first_of("\r\n", i);
        out.push_back(boxTxt.substr(i, e == std::string::npos ? std::string::npos : e - i));
        if (e == std::string::npos) i = boxTxt.size(); else i = (boxTxt[e] == '\r' && e + 1 < boxTxt.size() && boxTxt[e + 1] == '\n') ? e + 2 : e + 1;
    }
    return out;
}
static int boxMax() { return std::max(0, (int) boxLines().size() * FH - BOX); }
void SendText1(char *tbox, char *NewWord) { if (!strcmp(tbox, "LogText")) { boxTxt = NewWord; boxY = 0; } }   // (a new text starts at the top)
void SendText(char *, char *) {}
void SendCommand(char *) {}
void SendOtherValue(char *nbox, int value) {
    if (strcmp(nbox, "LogText.val_y")) return;
    if (value > boxMax()) ++overMax;                     // past the text: the old screen showed blank below the last line
    boxY = clampY ? std::max(0, std::min(value, boxMax())) : std::max(0, value);
}
int GetIntFromTextIn(uint8_t offset) { return offset == 4 ? boxY : offset == 8 ? boxMax() : 0; }   // the release: val_y then maxval_y
int InStrng(char *text1, char *text2) { return strstr(text2, text1) != nullptr; }
void DelayWithDog(uint32_t) {} void KickTheDog() {} void ClearFilesList() {} void MakeTextFileName() {}
File OpenTextFileForReading() { File f = SD.open("/log/SOURCE", FILE_READ); if (f) LogFileOpen = true; return f; }
void CloseLogFile() { if (LogFileOpen) LogFileNumber.close(); LogFileOpen = false; }

// ---- the finger: the screen moves the text as it drags, then the release reaches the main board
static void finger(int dy) {                             // dy > 0: the finger goes down the glass, earlier lines come into view
    boxY = std::max(0, std::min(boxY - dy, boxMax()));
    LogReleasedNEW();
}

// ---- what the box shows, against the file
static std::vector<std::string> expected;                 // the viewer's own wrapped copy, line by line
static void open(const std::string &content, const char *name) {
    fs.files.clear(); fs.files["/log/SOURCE"] = content; strcpy(TextFileName, name);
    boxTxt.clear(); boxY = 0; overMax = 0;
    LogVIEWNew();
    expected.clear(); const std::string &w = fs.files["/WRAP.TMP"]; size_t i = 0;
    while (i < w.size()) { size_t e = w.find('|', i); if (e == std::string::npos) { expected.push_back(w.substr(i)); break; } expected.push_back(w.substr(i, e - i)); i = e + 1; }
}
struct View { int first = -1, last = -1, n = 0; bool ok = true; };
static View view(const char *what) {                     // the file lines in the box now, checked against the file
    View v; const std::vector<std::string> lines = boxLines();
    const bool finalWindow = FinalReadStartLine == StartReadLine;
    for (int k = 0; k < (int) lines.size(); ++k) {
        const int top = k * FH; if (top + FH <= boxY || top >= boxY + BOX) continue;
        const int idx = StartReadLine + k; ++v.n; if (v.first < 0) v.first = idx; v.last = idx;
        bool same = idx < (int) expected.size() && expected[idx] == lines[k];
        if (!same && !finalWindow && k == (int) lines.size() - 1 && idx < (int) expected.size() && expected[idx].compare(0, lines[k].size(), lines[k]) == 0) same = true;   // the window's last line, cut by the read buffer
        if (!same) { v.ok = false; fprintf(stderr, "  %s: line %d shows '%s', the file has '%s'\n", what, idx, lines[k].c_str(), idx < (int) expected.size() ? expected[idx].c_str() : "(nothing)"); }
    }
    return v;
}
static void exercise(const std::string &content, const char *name, bool clamp) {
    clampY = clamp; char what[200];
    open(content, name);
    const int total = (int) expected.size(), fullBox = std::min(total, BOX / FH);
    const bool wholeFile = total <= MAXSEEKPOSITIONS - 1;  // (B57: a log of more than 5000 lines stops at the table's end)
    snprintf(what, sizeof(what), "%s, %d lines, screen %s", name, total, clamp ? "clamps" : "does not clamp");
    // Bottom, then the finger up to the top
    BottomOfLogFileNEW();
    View v = view(what); CHECK(v.ok, what);
    if (wholeFile) { CHECK(v.last == total - 1, what); CHECK(v.n == fullBox, what); }
    int steps = 0;
    while (true) {
        const int before = v.first;
        finger(+300); v = view(what); CHECK(v.ok, what);
        if (v.first == 0 && boxY == 0) break;
        if (!(v.first < before)) { ++fails; ++checks; fprintf(stderr, "FAIL: %s: STUCK after Bottom at line %d (box %d..%d, val_y %d of %d)\n", what, v.first, v.first, v.last, boxY, boxMax()); break; }
        if (++steps > total + 50) { ++fails; ++checks; fprintf(stderr, "FAIL: %s: the top never came\n", what); break; }
    }
    // Top, the finger down to the end, and up again
    TopOfLogFileNEW(); v = view(what); CHECK(v.ok && v.first == 0, what);
    steps = 0;
    while (wholeFile) {
        const int before = v.last;
        finger(-300); v = view(what); CHECK(v.ok, what);
        if (v.last == total - 1) break;
        if (!(v.last > before)) { ++fails; ++checks; fprintf(stderr, "FAIL: %s: STUCK going down at line %d (val_y %d of %d)\n", what, v.last, boxY, boxMax()); break; }
        if (++steps > total + 50) { ++fails; ++checks; fprintf(stderr, "FAIL: %s: the end never came\n", what); break; }
    }
    steps = 0;
    while (true) {
        const int before = v.first;
        finger(+300); v = view(what); CHECK(v.ok, what);
        if (v.first == 0 && boxY == 0) break;
        if (!(v.first < before)) { ++fails; ++checks; fprintf(stderr, "FAIL: %s: STUCK going up again at line %d (val_y %d of %d)\n", what, v.first, boxY, boxMax()); break; }
        if (++steps > total + 50) { ++fails; ++checks; fprintf(stderr, "FAIL: %s: the top never came again\n", what); break; }
    }
    // Bottom once more, with the end already known
    BottomOfLogFileNEW(); v = view(what); CHECK(v.ok, what);
    if (wholeFile) { CHECK(v.last == total - 1, what); CHECK(v.n == fullBox, what); }
    CHECK(overMax == 0, what);                           // never a scroll position past the text
}
static std::string readFile(const char *path) { FILE *f = fopen(path, "rb"); if (!f) return ""; std::string s; char b[4096]; size_t n; while ((n = fread(b, 1, sizeof(b), f)) > 0) s.append(b, n); fclose(f); return s; }
int main(int argc, char **argv) {
    for (int i = 1; i + 1 < argc; i += 2) {              // name, path pairs: the files the Python side made
        const std::string content = readFile(argv[i + 1]);
        if (content.empty()) { fprintf(stderr, "cannot read %s\n", argv[i + 1]); return 2; }
        exercise(content, argv[i], true); exercise(content, argv[i], false);
    }
    printf("test_logview: %d checks, %d failures\n", checks, fails);
    return fails ? 1 : 0;
}
'''

def log_line(t, i, rnd):
    """A line as the logger writes them: a time, a dash, some words, '|' and CR LF; now and then an indented continuation."""
    texts = ['Connected to Havok', 'RX: 1', 'RX: 2', 'Safety Off', 'Safety On', 'Motor On', 'Motor Off', 'Bank 1', 'Bank 4', 'Rate: 1',
             '(307 ms gap excluded - RX saving flight data)', 'Transmitter powered off while still connected', 'Max ESC Temp: 41.00 C.',
             'Time connected: 0 minutes and 42 seconds', 'Receiver type: TRX:2 V2', 'Minimum logged gap: 50 ms', 'TX Volts per cell: 8.21']
    if rnd.random() < 0.3:
        return '               - %s|\r\n' % rnd.choice(texts)
    return '%02d.%02d.%02d - %s|\r\n' % (t // 3600 % 24, t // 60 % 60, t % 60, rnd.choice(texts))

def make_files(d):
    rnd = random.Random(1910)
    files = []
    for n in [1, 5, 13, 14, 15, 20, 37, 38, 39, 40, 41, 60, 77, 100, 150, 200, 333, 500, 997, 1234, 2000]:
        t = 17 * 3600 + 24 * 60 + 58; s = ''
        for i in range(n):
            t += rnd.randint(0, 40); s += log_line(t, i, rnd)
        p = os.path.join(d, 'log%d.LOG' % n); open(p, 'w').write(s); files += ['%d-10-26.LOG' % (n % 28 + 1), p]
    for n in [3, 30, 120]:                                # help-like: paragraphs the viewer wraps itself
        words = 'the transmitter keeps every model on its card and shows the one in use at the top of the front screen'.split()
        s = ''
        for i in range(n):
            s += ' '.join(rnd.choice(words) for _ in range(rnd.randint(3, 60))) + '.|\r\n'
        p = os.path.join(d, 'help%d.TXT' % n); open(p, 'w').write(s); files += ['HELP%d.TXT' % n, p]
    s = ''.join('%04d|\r\n' % i for i in range(300))     # very short lines: more than a window holds in one read buffer
    p = os.path.join(d, 'short.LOG'); open(p, 'w').write(s); files += ['SHORT.LOG', p]
    s = ''.join(('x' * rnd.randint(100, 400)) + '|\r\n' for i in range(50))   # lines with nothing to wrap at: cut at the row's end
    p = os.path.join(d, 'long.TXT'); open(p, 'w').write(s); files += ['LONG.TXT', p]
    s = ''.join(log_line(60000 + i * 7, i, rnd) for i in range(5200))   # past the seek table (B57)
    p = os.path.join(d, 'huge.LOG'); open(p, 'w').write(s); files += ['HUGE.LOG', p]
    for real in ['18-10-26.LOG', '19-10-26.LOG']:        # the real logs of the day it bit, when the SSD is here
        rp = os.path.join(LIVE, real)
        if os.path.exists(rp): files += [real, rp]
        else: print('(%s is not here: the real log not tried)' % real)
    return files

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'Arduino.h'), 'w').write('#pragma once\n#include <cstdint>\n#include <cstring>\n')
    open(os.path.join(d, '1Definitions.h'), 'w').write(FAKE_DEFS)
    open(os.path.join(d, 'LogFilesDisplay.h'), 'w').write(open(HDR, encoding='utf-8', errors='replace').read())
    open(os.path.join(d, 't.cpp'), 'w').write(PROG)
    r = subprocess.run(['clang++', '-std=c++17', '-O1', '-Wall', '-Wno-unused-function', '-Wno-format-truncation', '-I', d, '-o', os.path.join(d, 't'), os.path.join(d, 't.cpp')], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    files = make_files(d)
    r = subprocess.run([os.path.join(d, 't')] + files, capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
    sys.exit(r.returncode)
