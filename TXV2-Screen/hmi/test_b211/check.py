#!/usr/bin/env python3
"""Source checks of WHAT THE SCREEN DOES FOR THE MAIN BOARD'S B211 ("a press belongs to its page", screen 1.11.198). The main board's
own tests (TXV1B dev/test_stalepress and the three built on it) run its real routines over a pretend screen that behaves as this
source says; these checks keep the source saying it.
  1. The line the other core says when the loop stands still goes out in ONE push of at most 127 bytes that ends with a newline
     (it was written in pieces: the loop's own replies went out between them, and a piece's tail was read as a reply).
  2. Every "LDRCLOG ..." line for the main board's log ends with a newline.
  3. What the main board writes without naming a page while a keyboard of ours is up goes to the page beneath.
  4. A finger that lands within a quarter of a second of a page being UP - the END of its load - is not taken.
  5. A "sendme" right behind a box's get says the page that get was ANSWERED ON (a keyboard that closed between the two commands
     left a 0 answered under it taken for the page's box).
  6. (the main board's eleventh review) THE ROM'S OWN PRINTF never reaches the wire: its characters are kept in the ring of the system's lines
     (romPutc, installed right behind the system log's hook; the second channel is cut too). The Bluetooth library says lines of its own that way
     ("Host not enabled. Dropping the packet!"), a character at a time, from another task - between the bytes of whatever the loop is answering.
  7. ... and platformio.ini names an EXACT version of every library (a range took whatever was newest at the next build, unseen).
   python3 hmi/test_b211/check.py"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(ROOT, 'src', 'main.cpp'), encoding='utf-8', errors='replace').read()
lm = open(os.path.join(ROOT, 'src', 'last_moments.h'), encoding='utf-8', errors='replace').read()
checks = fails = 0
def check(cond, what):
    global checks, fails
    checks += 1
    if not cond:
        fails += 1
        print('   FAIL:', what)
def code(t): return re.sub(r'//[^\n]*', '', t)

# 1. lmShout: one push, at most 127 bytes, a newline at its end
m = re.search(r'static void lmShout\(const char \*s\) \{(.*?)\n\}\n', lm, re.S)
check(m is not None, 'lmShout found')
b = code(m.group(1)) if m else ''
check(re.search(r'char line\[128\];', b) is not None, 'lmShout puts its line together in 128 bytes')
check(re.search(r"line\[n\+\+\] = '\\n';", b) is not None, "lmShout ends its line with a newline")
check(b.count('uart_tx_chars(') == 1 and 'for (' not in b and 'while (' not in b, 'lmShout hands its line over in ONE push (no loop: what does not fit is not said)')
check(re.search(r'if \(n > \(int\) sizeof line - 2\) n = \(int\) sizeof line - 2;', b) is not None, 'lmShout cuts a longer line to 126 bytes and the newline')
# 2. every line for the log ends with a newline
m = re.search(r'static void lmTell\(const std::string &line\) \{([^\n]*)\}', src)
check(m is not None and 'Serial.print((line + "\\n").c_str())' in m.group(1), 'lmTell ends its line with a newline')
said = re.findall(r'Serial\.print[fln]*\(\s*"(LDRCLOG[^"]*)"', src)
check(len(said) == 1 and all(s.endswith('\\n') for s in said), 'the one "LDRCLOG ..." line printed past lmTell (the record of a restart, in parts) ends each part with a newline: ' + repr(said))
# 3. writes under the keyboard
check('static std::string pageUnderKeyboard() {' in src, 'pageUnderKeyboard found')
check(src.count('pg = pageUnderKeyboard();') >= 3, 'vis, click and a box\'s attribute written with no page named go to the page under the keyboard')
# 4. the quarter second, from when the page is UP
m = re.search(r'static bool loadPage\(const std::string &name\) \{(.*?)\n\}\n', src, re.S)
check(m is not None, 'loadPage found')
b = code(m.group(1)) if m else ''
check(re.search(r'runScript\(page\.evPost, ""\);\s*pageUpMs = millis\(\) \| 1;\s*return true;\s*$', b) is not None, 'loadPage notes the moment the page is UP as its last act')
check(b.count('pageUpMs') == 1, 'pageUpMs is set in one place in loadPage: its end')
check('static const uint32_t TOUCH_AFTER_PAGE_MS = 250;' in src, 'the quarter second')
check(re.search(r'if \(pageUpMs && \(int32_t\) \(now - pageUpMs\) < \(int32_t\) TOUCH_AFTER_PAGE_MS\) \{ touchLockout = true; lastSeen = now; return; \}', src) is not None, 'a press that begins within it is not taken, nor anything until that finger has lifted - counted with a sign (the moment kept is a millisecond ahead in an even one)')
check('now - pageLoadedMs < TOUCH_AFTER_PAGE_MS' not in src, 'the quarter second is not counted from the START of the load')
# 5. "sendme" right behind a box's get
m = re.search(r'static void handle\(const std::string &cmd\) \{(.*?)\n\}\n', src, re.S)
check(m is not None, 'handle found')
b = code(m.group(1)) if m else ''
check(re.match(r'\s*const int getPage = getAnsweredOnPage; getAnsweredOnPage = -1;', b) is not None, 'handle() takes "the page the last get was answered on" for THIS command only, first thing')
g = b.find('if (cmd.rfind("get ", 0) == 0) {'); gb = b[g:b.find('\n    }\n', g)] if g >= 0 else ''
check(gb.count('getAnsweredOnPage = page.id;') == 1, 'a box\'s get keeps the page it is answered on')
sysget = gb[:gb.find('std::string attr')] if 'std::string attr' in gb else gb
check('getAnsweredOnPage' not in sysget, 'a system variable\'s get keeps no page (a page command\'s own "sendme" says the page showing)')
check(gb.find('getAnsweredOnPage = page.id;') < gb.find('host.getTxt(') and gb.find('getAnsweredOnPage = page.id;') < gb.find('host.getInt('), '... before the box is read')
check(re.search(r'if \(cmd == "sendme"\) \{ const uint8_t f\[5\] = \{ 0x66, \(uint8_t\) \(getPage >= 0 \? getPage : page\.id\), 0xFF, 0xFF, 0xFF \}; Serial\.write\(f, 5\); return; \}', b) is not None, '"sendme" says that page when it comes right behind a box\'s get, the page showing otherwise - 66, the number, FF FF FF, in one write')
check(src.count('getAnsweredOnPage') == 4, 'getAnsweredOnPage is touched in four places only: its line, handle()\'s first, the get, and nowhere else')
# 6. the ROM's printf
m = re.search(r'static void IRAM_ATTR romPutc\(char c\) \{(.*?)\n\}\n', src, re.S)
check(m is not None, 'romPutc found, and it is kept in RAM (IRAM_ATTR: it may be called with the flash cache off)')
b = code(m.group(1)) if m else ''
check('Serial' not in b and 'uart' not in b.lower() and 'printf' not in b, 'romPutc writes nothing to any port')
check(re.search(r'portENTER_CRITICAL_SAFE\(&sysMux\);.*portEXIT_CRITICAL_SAFE\(&sysMux\);', b, re.S) is not None, 'the line goes into the system lines\' ring under that ring\'s own lock, from a task or an interrupt')
check(re.search(r'static char romLine\[(\d+)\];', src) is not None and int(re.search(r'static char romLine\[(\d+)\];', src).group(1)) + 5 <= int(re.search(r'static char sysLines\[SYS_LINES\]\[(\d+)\];', src).group(1)), 'a ROM line with "rom: " in front fits a line of the ring')
s = code(src[src.index('void setup() {'):])
check(re.search(r'esp_log_set_vprintf\(sysLogHook\);\s*lmRomPutc = romPutc;\s*esp_rom_install_channel_putc\(1, romPutc\);\s*esp_rom_install_channel_putc\(2, NULL\);', s) is not None, 'setup installs it right behind the system log\'s hook, and cuts the second channel')
check(re.search(r'lmRomPutc = romPutc;\s*esp_rom_install_channel_putc\(1, romPutc\);', s) is not None, 'setup names romPutc as the place the heap check gives the ROM\'s printing back to')
# (the main board's twelfth review: this looked at main.cpp alone - and the heap check's task, in last_moments.h, gave the ROM's printing BACK TO THE UART
#  after every check: on a 16 MB board the hook lived for ten lines of setup(). EVERY source file is read now - not secrets.h - for every name that
#  installs a ROM printf channel or turns the port's debug output on.)
# (the main board's thirteenth review, reviewer A's experiment 5: this wanted each name with its bracket behind it and no dot in front, in files of ten kinds -
#  "Serial.setDebugOutput(true);", the usual way, was NOT SEEN; nor a #define for a name, a pointer to it, brackets round it, a comment or a line's end
#  between the name and its bracket, a call with a comma behind it, a file ".hh". Now: the BARE names, wherever they stand, in EVERY file of the
#  source whatever its kind - each name's every mention must be one of the four calls known here; tokens pasted together (##) are refused, for a
#  name made of two halves is seen by no pattern; and the routines the ROM's characters are handed to call nothing but what they call today.)
INSTALLS = r'esp_rom_install_channel_putc|ets_install_putc[12]?|esp_rom_install_uart_printf|ets_install_uart_printf|uartSetDebug|setDebugOutput|esp_rom_uart_putc|ets_write_char_uart|esp_rom_uart_tx_one_char|uart_tx_one_char'
found, bare, pasted, unread = [], [], [], []
def nocomment(t): return re.sub(r'/\*.*?\*/', ' ', code(t), flags=re.S)
for top in ('src', 'lib', 'include'):
    for d, _, files in sorted(os.walk(os.path.join(ROOT, top))):
        for f in sorted(files):
            if f == 'secrets.h' or f == '.DS_Store': continue
            raw = open(os.path.join(d, f), 'rb').read()
            if b'\0' in raw[:4096]: unread.append(f); continue                 # (not a text: nothing the compiler reads)
            text = code(raw.decode('utf-8', 'replace'))
            for mo in re.finditer(r'(?<![\w.])(' + INSTALLS + r')\s*\(([^;]*?)\)\s*;', text): found.append((f, mo.group(1), re.sub(r'\s+', ' ', mo.group(2)).strip()))
            for mo in re.finditer(r'\b(' + INSTALLS + r')\b', text): bare.append((f, mo.group(1)))
            for no, line in enumerate(nocomment(raw.decode('utf-8', 'replace')).split('\n'), 1):
                if '##' in re.sub(r'"(?:[^"\\]|\\.)*"', '""', line): pasted.append('%s:%d' % (f, no))
KNOWN = [('main.cpp', 'esp_rom_install_channel_putc', '1, romPutc'), ('main.cpp', 'esp_rom_install_channel_putc', '2, NULL'),
         ('last_moments.h', 'ets_install_putc1', 'lmHeapPutc'), ('last_moments.h', 'esp_rom_install_channel_putc', '1, lmRomPutc')]
check(sorted(found) == sorted(KNOWN),
      'the ROM\'s printf is installed in four places of the whole source, and never on the UART: setup\'s two, the heap check\'s own catch, and its giving back to lmRomPutc - found: ' + repr(sorted(found)))
check(sorted(bare) == sorted((f, n) for f, n, _ in KNOWN),
      'every mention of a name that installs the ROM\'s printf or turns the port\'s debug output on, in every file of the source, is one of those four calls - found: ' + repr(sorted(bare)))
check(pasted == [], 'no tokens are pasted together (##) anywhere in the source - a name made of two halves would be seen by no check: ' + repr(pasted[:5]))
check(unread == [], 'every file of the source is a text that was read: ' + repr(unread[:5]))
def calls_of(body): return sorted(set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', nocomment(body))) - {'if', 'for', 'while', 'switch', 'sizeof', 'return'})
m_rom = re.search(r'static void IRAM_ATTR romPutc\(char c\) \{(.*?)\n\}\n', src, re.S)
m_heap = re.search(r'static void lmHeapPutc\(char c\) \{(.*?)\n\}\n', open(os.path.join(ROOT, 'src', 'last_moments.h'), encoding='utf-8', errors='replace').read(), re.S)
check(m_rom is not None and calls_of(m_rom.group(1)) == ['portENTER_CRITICAL_SAFE', 'portEXIT_CRITICAL_SAFE'], 'romPutc calls nothing but its ring\'s lock: ' + repr(calls_of(m_rom.group(1)) if m_rom else None))
check(m_heap is not None and calls_of(m_heap.group(1)) == [], 'lmHeapPutc - the heap check\'s own catch - calls nothing: ' + repr(calls_of(m_heap.group(1)) if m_heap else None))
for body, name in ((m_rom.group(1) if m_rom else '', 'romPutc'), (m_heap.group(1) if m_heap else '', 'lmHeapPutc')):
    check(not re.search(r'\b(?:WRITE_PERI_REG|REG_WRITE|SET_PERI_REG_MASK|REG_SET_BIT|UART_FIFO\w*|DR_REG_UART\w*|UART0|Serial\d*)\b|0[xX]6000_?0000', nocomment(body)), name + ' writes to no register and no port')
lm = open(os.path.join(ROOT, 'src', 'last_moments.h'), encoding='utf-8', errors='replace').read()
check(re.search(r'static void IRAM_ATTR lmRomDrop\(char\) \{\}\s*static void \(\*lmRomPutc\)\(char\) = lmRomDrop;', lm) is not None, 'until setup() has named it, the ROM\'s printing is given back to nobody')
task = lm[lm.index('static void lmHeapTaskFn(void *) {'):lm.index('// True = the heap is sound')]
check(re.search(r'ets_install_putc1\(lmHeapPutc\);.*heap_caps_check_integrity_all\(true\);.*esp_rom_install_channel_putc\(1, lmRomPutc\);', code(task), re.S) is not None and 'uart' not in code(task).lower().replace('lmheapputc', ''),
      'the heap check catches the ROM\'s printing for its own findings and gives it back to lmRomPutc - never to the UART')
# 6b. a dying line is kept for the next start
check(re.search(r'RTC_NOINIT_ATTR static char lmRomSaid\[(\d+)\];', lm) is not None and int(re.search(r'RTC_NOINIT_ATTR static char lmRomSaid\[(\d+)\];', lm).group(1)) >= int(re.search(r'static char romLine\[(\d+)\];', src).group(1)),
      'a dying line has a place in RTC memory that holds a whole ROM line')
check('lmRomSaid[0] = 0;' in lm[lm.index('static void lmBegin()'):] if 'static void lmBegin()' in lm else False, 'a new run begins with no dying line')
check(re.search(r'if \(lmRomSaid\[0\]\) \{ snprintf\(t, sizeof t, "; AS IT DIED THE SYSTEM SAID: %s", lmRomSaid\); b \+= t; \}', lm) is not None, 'the next start says it in the record of the run that ended')
check(re.search(r'if \(heap \|\| \(dump && !lmRomSaid\[0\]\)\)', b) is not None and 'strstr' not in b and 'strn' not in b and 'memcmp' not in b, 'romPutc keeps a heap\'s line always and a core dump\'s only when none is kept - with no library call (the flash cache may be off)')
# 7. exact versions
ini = open(os.path.join(ROOT, 'platformio.ini'), encoding='utf-8', errors='replace').read()
live = '\n'.join(l.split(';')[0].rstrip() for l in ini.split('\n'))
m = re.search(r'^lib_deps\s*=\s*\n((?:[ \t]+\S[^\n]*\n)+)', live + '\n', re.M)
libs = [l.strip() for l in m.group(1).split('\n') if l.strip()] if m else []
check(len(libs) == 5 and all(re.search(r'@\s*\d+\.\d+\.\d+$', l) for l in libs), 'every library in lib_deps is named with an exact version: ' + repr(libs))
check(re.search(r'^platform\s*=\s*espressif32\s*@\s*\d+\.\d+\.\d+\s*$', live, re.M) is not None and re.search(r'^platform_packages\s*=\s*platformio/framework-arduinoespressif32\s*@\s*\d+\.\d+\.\d+\+sha\.[0-9a-f]+\s*$', live, re.M) is not None,
      'the platform is named with an exact version, and the Arduino framework with its exact build (platform_packages)')
check('h2zero/NimBLE-Arduino @ 2.5.2' in libs and 'bitbank2/JPEGDEC @ 1.8.5' in libs, 'the Bluetooth library and the JPEG decoder are the PUBLISHED 1.11.197\'s (2.5.2, 1.8.5): 1.11.198 takes nothing back a version')
check(len(re.findall(r'^lib_deps\b', live, re.M)) == 1 and re.search(r'^lib_ignore\s*=\s*bb_spi_lcd\s*$', live, re.M) is not None, 'one lib_deps for every build; the library JPEGDEC merely asks for is not built')
print('test_b211 (screen): %d checks, %d failures' % (checks, fails))
sys.exit(1 if fails else 0)
