#!/usr/bin/env python3
"""Host test of B211 (14 Nov 2026): A PRESS BELONGS TO THE PAGE IT WAS MADE ON.

The fault (found by reading, while the ELRS page was reviewed; proven here): a button's code that reaches the main board while
it is busy with the screen - reading a page's boxes takes a second - is KEPT (Nextion.h PendingPush) and served by the loop
afterwards. By then the page may have changed, and the code's function runs on a page that is not its own. The screen answers
0 (or "") for a box the showing page has not got, so a second tap on Model options' OK - one tap too many, a quarter of a
second after the first - ran RXOptionsViewEnd again on the front page: motor switch off, 'stop flying' volts 0, trim step 0,
six banks off, the timer 0 ... saved in the model's memory. Every page's OK or Save had the same weakness (139 of the 318
button functions reach a box read).

Here the REAL code is compiled on the Mac - Nextion.h's reading and sending (PendingPush ... GetButtonPress, SendCommand,
GetValue, GetText) and MenuOptions.h's ReadRXOptionsView and RXOptionsViewEnd - over a pretend screen that keeps the rules of
the real one (src/main.cpp of the screen: commands in order, a page loaded when its command is read, 0 for a box it has not
got, every burst framed), with a clock, and taps at chosen moments.
   python3 dev/test_stalepress/test_stalepress.py            (--show: the scenes' own account)"""
import glob, json, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TC = os.path.join(ROOT, 'TransmitterCode')
def src(rel): return open(os.path.join(TC, rel), encoding='utf-8', errors='replace').read()
def release(t):
    """The text as a RELEASE compiles it: the ELRS test builds' lines (#ifdef ELRS_TEST ... [#else ...] #endif) taken out."""
    out, state = [], []
    for l in t.split('\n'):
        s = l.strip()
        if s.startswith('#ifdef ELRS_TEST'): state.append('test'); continue
        if s.startswith('#else') and state: state[-1] = 'rel'; continue
        if s.startswith('#endif') and state: state.pop(); continue
        if not (state and state[-1] == 'test'): out.append(l)
    return '\n'.join(out)
NEXTION, MENU, MAIN_CPP, UTIL, DEFS = (release(src(p)) for p in ('include/Nextion.h', 'include/MenuOptions.h', 'src/main.cpp', 'include/Utilities.h', 'include/1Definitions.h'))

def lift(text, head):
    """The function whose first line starts with `head` (column 0, Allman style): from there to the next line that is just '}'."""
    lines = text.split('\n')
    if head.endswith('\n{'): head = head[:-2]
    for i, l in enumerate(lines):
        if (l.startswith(head) or l.startswith('FLASHMEM ' + head)) and not l.split('//')[0].rstrip().endswith(';'):
            for j in range(i + 1, len(lines)):
                if lines[j] == '}':
                    return '\n'.join(lines[i:j + 1]) + '\n'
            break
    raise SystemExit('cannot lift ' + head)
def define(name):
    m = re.search(r'#define\s+' + name + r'\s+(\d+)', DEFS)
    if not m: raise SystemExit('no #define ' + name + ' in 1Definitions.h')
    return m.group(1)

# ---- the two pages, as the card has them (when the screen's project is beside this one: the names and the OK's code are checked)
OPTION_BOXES = [('c1', 'n', 1), ('n3', 'n', 5), ('t10', 't', '3.50'), ('t12', 't', '120'), ('n0', 'n', 1000), ('n2', 'n', 3), ('c0', 'n', 1),
                ('n1', 'n', 5), ('c2', 'n', 1), ('c3', 'n', 1), ('n4', 'n', 6), ('Progress', 'n', 0), ('change', 't', 'XX:'), ('va0', 'n', 0)]
PAGES_DIR = os.path.join(os.path.dirname(ROOT), 'ESP32-board2', 'board4', 'nextion-emulator', 'sd', 'hmi', 'pages')
def page_checks():
    if not os.path.isdir(PAGES_DIR): return ['(the screen project is not beside this one: the page files were not looked at)']
    p9, p13 = (json.load(open(os.path.join(PAGES_DIR, '%d.json' % i))) for i in (9, 13))
    n9, n13 = {c['n']: c for c in p9['comps']}, {c['n'] for c in p13['comps']}
    bad = []
    for name, kind, _ in OPTION_BOXES:
        if name not in n9: bad.append('page 9 has no box ' + name)
        if name in n13 and name != 'va0': bad.append('the front page has a box ' + name + ' too')
    ok = [c for c in p9['comps'] if c.get('txt') == 'OK']
    if len(ok) != 1 or (ok[0].get('ev') or {}).get('r') != 'va0.val=128+39\nprint va0.val': bad.append("page 9's OK does not print 128+39")
    if p9['name'] != 'RXOptionsView' or p13['name'] != 'FrontView': bad.append('pages 9 and 13 are not RXOptionsView and FrontView')
    # WHAT A PAGE SENDS BY ITSELF AS IT COMES UP comes between the two markers: a word passes only if it is one of the page's
    # own (IsPageOwnWord) or the one load print (IsLoadPrint: the Sub-trim page's "StCH"), and a CODE is let go. So every page
    # of the card is read here: the codes printed as a page comes up (its preinitialize / postinitialize, also through a
    # "click" of a part whose own script prints; a timer that is on) must be exactly the three known - MixesView's click of
    # b22 (128+76: let go, nothing is missed), the Governor page's timer (58<<8: the next tick is obeyed), ModelsView's old
    # line (needs send.val == 1, which nothing sets) - and the words exactly those two kinds. A new page that prints something
    # as it comes up fails here, and must be thought about.
    own_codes, own_words, sets_send = page_prints({int(os.path.basename(f)[:-5]): json.load(open(f)) for f in sorted(glob.glob(os.path.join(PAGES_DIR, '*.json')))})
    if own_codes != PAGE_CODES_KNOWN: bad.append('the codes a page prints as it comes up are not the three known: ' + repr(own_codes))
    if sets_send: bad.append('something sets ModelsView\'s send.val (its page would print a code as it comes up): ' + repr(sets_send))
    p5, p15, p29 = (json.load(open(os.path.join(PAGES_DIR, '%d.json' % i))) for i in (5, 15, 29))
    if 'va0.val=58<<8' not in json.dumps([c.get('ev') for c in p5['comps'] if c['n'] == 'tm0']): bad.append("page 5's timer does not print 58<<8")
    if 'va0.val=128+76' not in json.dumps([c.get('ev') for c in p29['comps'] if c['n'] == 'b22']): bad.append("page 29's b22 does not print 128+76")
    if (p15.get('ev') or {}).get('postinitialize') != 'if(send.val==1)\n{\n  va0.val=128+3\n  print va0.val\n}': bad.append("page 15's postinitialize is not the old line that needs send.val == 1")
    notown = sorted(set((pid, w) for pid, w in own_words if not (w in ('ldrcadj', 'ldrcrcv') or re.fullmatch(r'CH\d{1,2}NAME=', w))))
    if notown != [(32, 'StCH')]: bad.append('the words a page prints as it comes up must be the page\'s own (IsPageOwnWord) or the one load print (IsLoadPrint: the Sub-trim page\'s StCH): ' + repr(notown))
    p32 = json.load(open(os.path.join(PAGES_DIR, '32.json')))
    if 'click n00,0' not in (p32.get('ev') or {}).get('preinitialize', '') or not any('print "StCH"' in (c.get('ev') or {}).get('r', '') for c in p32['comps'] if c['n'] == 'n00'):
        bad.append("page 32 (SubTrimView) does not click its first channel as it comes up, or that channel does not print StCH")
    for rel in ('include', 'src'):
        for f in glob.glob(os.path.join(TC, rel, '*')):
            if not os.path.isfile(f): continue
            t = open(f, encoding='utf-8', errors='replace').read()
            if re.search(r'"send(\.val)?"|send\.val=', t): bad.append(os.path.basename(f) + ' names ModelsView\'s send: does it set it?')
    return bad
def page_prints(pages):
    """WHAT EVERY PAGE OF THE CARD PRINTS BY ITSELF AS IT COMES UP - pages: {its number: the page file's content}. The codes (who prints a
    number), the words, and whoever sets ModelsView's send.val.
    (The eighth review: the script's "prints" and "printh" print too. The ninth: a timer that is OFF in the page file can be switched on by
    the page's own script - every timer that prints counts, on or off; a part clicked as the page comes up can click another - followed all
    the way; and a print can stand behind its "if" on the same line - looked for anywhere in a line. PAGE_SELFTEST below keeps this scan honest.)"""
    def live(script): return '\n'.join(l for l in script.split('\n') if not l.strip().startswith('//'))
    def prints_number(script): return any(not re.fullmatch(r'\w+\.txt(?:,\d+)?', a) for a in re.findall(r'(?<![\w."])prints?\s+(?!")([^\s;}]+)', live(script))) \
        or re.search(r'(?<![\w."])printh\b', live(script)) is not None   # (print x.txt is a text: a word's tail)
    def words_of(script): return re.findall(r'(?<![\w."])prints?\s+"([^"]*)"', live(script))
    own_codes, own_words, sets_send = [], [], []
    for pid in sorted(pages):
        pg = pages[pid]; comps = {c['n']: c for c in pg['comps']}
        for c in pg['comps']:
            for k, v in (c.get('ev') or {}).items():
                if re.search(r'\bsend\.val\s*=(?!=)', live(v)): sets_send.append('%d %s' % (pid, c['n']))
            if c.get('t') == 'timer' and prints_number((c.get('ev') or {}).get('t', '')): own_codes.append((pid, c['n']))
            if c.get('t') == 'timer': own_words += [(pid, w) for w in words_of((c.get('ev') or {}).get('t', ''))]
        for k in ('preinitialize', 'postinitialize'):
            v = (pg.get('ev') or {}).get(k, '')
            if re.search(r'\bsend\.val\s*=(?!=)', live(v)): sets_send.append('%d page' % pid)
            if prints_number(v): own_codes.append((pid, k))
            own_words += [(pid, w) for w in words_of(v)]
            todo = [(name, d) for name, d in re.findall(r'(?<![\w."])click\s+(\w+)\s*,\s*([01])', live(v))]; done = set()
            while todo:                                                        # (a part clicked as the page comes up - and whatever ITS script clicks, all the way)
                name, d = todo.pop()
                if (name, d) in done: continue
                done.add((name, d))
                ev = (comps.get(name, {}).get('ev') or {}).get('p' if d == '1' else 'r', '')
                if prints_number(ev): own_codes.append((pid, name))
                own_words += [(pid, w) for w in words_of(ev)]
                todo += re.findall(r'(?<![\w."])click\s+(\w+)\s*,\s*([01])', live(ev))
    return sorted(set(own_codes)), own_words, sets_send
ROM_TEXT = ("ESP-ROM:esp32s3-20210327\r\nBuild:Mar 27 2021\r\nrst:0xc (RTC_SW_CPU_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)\r\nSaved PC:0x420b7a66\r\n"
            "SPIWP:0xee\r\nmode:DIO, clock div:1\r\nload:0x3fce3808,len:0x44c\r\nload:0x403c9700,len:0xbe4\r\nload:0x403cc700,len:0x2a38\r\nentry 0x403c98d4\r\n")
def rom_as_read(text):
    """What a 921600-baud receiver makes of `text` sent at 115200 baud, 8N1, back to back (the seventh review's model: a start bit is taken
    at a falling edge, eight bits sampled at their middles): [(microseconds from the first bit, the byte)]. An ESP32-S3's ROM says its
    piece at 115200 at every reset; the screen's program then talks at 921600."""
    runs = []
    def add(level, n):
        if runs and runs[-1][0] == level: runs[-1] = (level, runs[-1][1] + n)
        else: runs.append((level, n))
    for ch in text.encode('latin-1'):
        add(0, 8)
        for i in range(8): add((ch >> i) & 1, 8)
        add(1, 8)
    add(1, 400)
    starts, p = [], 0
    for lv, n in runs: starts.append((p, lv, n)); p += n
    def level(x):
        for s, lv, n in starts:
            if s <= x < s + n: return lv
        return 1
    out, search, bit = [], 0.0, 1e6 / 921600.0
    while True:
        edge = None
        for i, (s, lv, n) in enumerate(starts):
            if lv == 0 and s >= search and (i == 0 or starts[i - 1][1] == 1): edge = s; break
        if edge is None: break
        b = 0
        for i in range(8):
            if level(edge + 1.5 + i): b |= 1 << i
        out.append((int(round((edge + 10) * bit)), b))
        search = edge + 9.5
    return out
WIRE_SITES = [   # every line of the screen's firmware (1.11.197) that can put a byte on the wire - see wire_sites() below
    'ble_device.h: static void bleMailPost(const std::string &s) { if (!bleMutex) bleMutex = xSemaphoreCreateMutex(); i #a943b0b27d',
    'ble_device.h: bleTelLast = tel; bleTelAt = millis(); bleMailPost(tel + "\\n"); #1b46f85a2d',
    'ble_device.h: } else { bleWhy = "the receiver refused a parameter (" + err + ")"; bleMailPost("ldrcpipe=3"); blePo #b560644ca3',
    'ble_device.h: bleMailPost(rep); #a9ad4f9da3',
    'ble_device.h: if (st != blePipeTold && !teensyLink.running()) { blePipeTold = st; flushOut(); const std::string t  #08c8a9ca85',
    'ble_device.h: if (!bleMail.empty() && bleMutex && xSemaphoreTake(bleMutex, pdMS_TO_TICKS(5)) == pdTRUE) { #4c83ae64fb',
    'ble_device.h: std::string m = bleMail.front(); bleMail.erase(bleMail.begin()); xSemaphoreGive(bleMutex); #466ce52e2a',
    'ble_device.h: if (!teensyLink.running()) { flushOut(); Serial.write((const uint8_t *) m.data(), m.size()); blog("b #0369c85d4c',
    'ble_device.h: if (updWifi) { bleNote("the update has the radio: not now"); bleMailPost("ldrcpipe=3"); return; } #d5684f8900',
    'ble_device.h: if (bleState != BLE_READY) { bleMailPost("ldrcrep " + std::to_string(q.id) + " 0 not joined\\n"); ret #8f9546205c',
    'ble_device.h: if (cliPageUp) { bleMailPost("ldrcrep " + std::to_string(q.id) + " 409 the command line page is open #95bcefaf9a',
    'cli_device.h: if (now - cliTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running() && page.name != " #c2e3ff9907',
    'film_device.h: filmAwakeAt = now ? now : 1; flushOut(); Serial.write((const uint8_t *) "LDRCAWAKE", 9); #47a9187630',
    'flight_device.h: if (poke && now - lastPoke > 20000 && !teensyLink.running()) { lastPoke = now; flushOut(); Serial.wr #08df9b0483',
    'last_moments.h: static void lmShout(const char *s) { #be75b94a76',
    'last_moments.h: uart_tx_chars(UART_NUM_0, line, n); #e2d860c94b',
    'last_moments.h: lmShout(wire); #6aa8582d0c',
    'last_moments.h: ets_install_putc1(lmHeapPutc); #b58fc78498',
    'last_moments.h: esp_rom_install_channel_putc(1, lmRomPutc); #8c9de1d288',
    'main.cpp: T *allocate(size_t n) { void *p = heap_caps_malloc(n * sizeof(T), MALLOC_CAP_SPIRAM); if (!p) p = ma #73a5ffd016',
    'main.cpp: outBuf.append((const char *) b, n); #b738dcade0',
    'main.cpp: outBuf.insert(0, h, 4); #fa82dc92ce',
    'main.cpp: Serial.write((const uint8_t *) outBuf.data(), outBuf.size()); outBuf.clear(); #d6daf5f269',
    'main.cpp: static void lmTell(const std::string &line) { flushOut(); Serial.print((line + "\\n").c_str()); Seria #1e50f103ae',
    'main.cpp: if (lmHeapOn && !lmHeapCheck((page.name + ">" + name).c_str())) { blog("heap", lmHeapLast.substr(0,  #2393671328',
    'main.cpp: static void reply(uint8_t code) { const uint8_t f[4] = { code, 0xFF, 0xFF, 0xFF }; Serial.write(f, 4 #29b1b765a3',
    'main.cpp: Serial.printf("[%lu:%s]\\n", (unsigned long) cmdCount, cmd.c_str()); #fdfaad351f',
    'main.cpp: outBuf.append("\\0\\0\\0\\0", 4); flushOut(); #7602f3c78a',
    "main.cpp: const int32_t v = host.getSys(ref); const uint8_t f[8] = { 'q', (uint8_t) v, (uint8_t) (v >> 8), (ui #8cce2ad27d",
    'main.cpp: if (attr == "txt") { std::string s = host.getTxt(pg, nm); std::string f = "p" + s; f += "\\xFF\\xFF\\xF #0d3d8557e5',
    "main.cpp: else { int32_t v = host.getInt(pg, nm, attr); const uint8_t f[8] = { 'q', (uint8_t) v, (uint8_t) (v  #5ee2ec96b1",
    'main.cpp: if (cmd == "sendme") { const uint8_t f[5] = { 0x66, (uint8_t) (getPage >= 0 ? getPage : page.id), 0x #d3ddb1a88b',
    'main.cpp: void write(const uint8_t *b, size_t n) override { Serial.write(b, n); } #0beccdd770',
    'main.cpp: void knock() override { Serial.write((const uint8_t *) LDRC_LINK_KNOCK, strlen(LDRC_LINK_KNOCK)); } #2f1ca2e5af',
    'main.cpp: doorOn("/poweroff", HTTP_POST, []() { if (teensyLink.running()) { web.send(409, "text/plain", "a job #23a12130af',
    'main.cpp: doorOn("/awake", HTTP_POST, []() { if (teensyLink.running()) { web.send(409, "text/plain", "a job is #f77164bf3a',
    'main.cpp: flushOut(); Serial.write((const uint8_t *) b, strlen(b)); #c02606638f',
    'main.cpp: Serial.setRxBufferSize(32768); #bb32419e60',
    'main.cpp: Serial.begin(NEXTION_BAUD); #a6c7b7a89c',
    'main.cpp: esp_log_set_vprintf(sysLogHook); #59ee97a0f7',
    'main.cpp: esp_rom_install_channel_putc(1, romPutc); #1f9b179595',
    'main.cpp: esp_rom_install_channel_putc(2, NULL); #ee257336b7',
    'main.cpp: Serial.setRxFIFOFull(24); #58d15a0d91',
    'main.cpp: Serial.print("EMU READY\\n"); #7e9d7f9427',
    'main.cpp: Serial.write(powerOn, sizeof(powerOn)); #192b8c403b',
    'main.cpp: if (why != ESP_RST_POWERON && !pageNames.empty()) { delay(300); Serial.printf("FrontView rst=%d", (i #19da127d8e',
    'main.cpp: if (!bootBefore.empty()) { Serial.flush(); for (size_t i = 0; i < bootBefore.size(); i += 280) { del #8bb5024e17',
    'main.cpp: if (lmHeapOn && !lmHeapCheck((page.name + " +400ms").c_str())) { blog("heap", lmHeapLast.substr(0, 6 #7200d50678',
    'main.cpp: lmTell(std::string("LDRCLOG ") + lmStuck); #d39c5bfda2',
    'pics_device.h: flushOut(); Serial.write((const uint8_t *) b.data(), b.size()); #df4a374125',
    'pics_device.h: void keepAwake() override { if (teensyLink.running()) return; flushOut(); Serial.write((const uint8_ #4b04636125',
    'theme_device.h: if (now - coloursTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running()) { lastPoke = #0eaa7fc248',
    'theme_device.h: if (now - appearanceTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running()) { lastPok #fdc7bebe0e',
    'update_device.h: void askTeensyWho() override { if (teensyLink.running()) return; flushOut(); Serial.write((const uin #c3626a4ab4',
    'update_device.h: void keepAwake() override { flushOut(); Serial.write((const uint8_t *) "UKRULES", 7); } #f0718e33e0',
    'update_device.h: flushOut(); Serial.write((const uint8_t *) b, strlen(b)); #2478cdcc7a',
    'update_device.h: if (millis() > 6000) abort(); #1328cecd4b',
    'wifi_device.h: if (now - wifiTouchedAt < 180000 && now - lastPoke > 20000 && !teensyLink.running() && page.name !=  #07c6425a18',
]
WIRE_WORDS = [   # ... and every piece of text in its source that begins as one of its own words does
    'FrontView',
    'FrontView rst=%d',
    'FrontView.',
    'FrontView.bt0',
    'FrontView.exp0',
    'FrontView\\',
    'LDRC',
    'LDRC V2 screen sd=%d pages=%d touch=%d',
    'LDRC-V1B-screen/',
    'LDRCAWAKE',
    'LDRCBUILD=full;',
    'LDRCBUILD=standard;',
    'LDRCFILM',
    'LDRCFW01',
    'LDRCIMG',
    'LDRCLINK',
    'LDRCLOG ',
    'LDRCLOG %s',
    'LDRCLOG %s%.280s\\n',
    'LDRCLOG heap check failed ',
    'LDRCOFF',
    'LDRCPK01',
    'LDRCRXUP',
    'LDRCSCREEN=',
    'LDRCWHO',
    'LDRC_FLASH_MB',
    'TIME=%ld',
    'UKRULES',
    'ldrc ',
    'ldrc appearance',
    'ldrc cli',
    'ldrc colours',
    'ldrc defined',
    'ldrc diff',
    'ldrc door',
    'ldrc exec',
    'ldrc flight',
    'ldrc rxupdate',
    'ldrc update',
    'ldrc wifi',
    'ldrc-recent',
    'ldrc-release',
    'ldrc-screen',
    'ldrcDiff',
    'ldrcExec',
    'ldrcble',
    'ldrcech=',
    'ldrcframe=1',
    'ldrcmb',
    'ldrcpipe ',
    'ldrcpipe=',
    'ldrcpipe=3',
    'ldrcrep ',
    'ldrcreq ',
    'ldrcrx=',
    'ldrcst=',
    'ldrcsync=',
    'ldrctel ',
    'ldrctx ',
    'ldrcup=',
    'ldrcwho=',
]
# EVERY LINE OF THE SCREEN'S FIRMWARE THAT CAN PUT A BYTE ON THE WIRE (the eighth and ninth reviews, 15 Nov 2026). The screen's console
# IS the wire to this board: a write to its port, a printf, a puts, a line of its core's log, a word put into the Bluetooth mail or into
# the burst that is being put together - each is something this board will read. The first form of this pin read the words out of
# string literals at the write itself; the second pinned the places, from the call on, with the text put together in the six lines above
# - and passed a word pushed straight into the Bluetooth mail, puts(), esp_rom_printf(), a Print& alias of the port, and a changed byte
# in front of a write (the page number's 66, a value reply's q, a text reply's end, the power-on bytes, a burst's frame mark, the restart
# word's condition): the ninth review's own list, kept below as WIRE_SELFTEST - each of those changes, made to a copy of the screen's
# source in memory, must be SEEN.
# So: every line that names the port (Serial.anything but its reads), any console print (printf, puts, putchar, esp_rom_printf, a log
# macro ...), the helpers (lmTell, lmShout, bleMailPost), the Bluetooth mail and the burst's buffer themselves, and any Print/Stream alias,
# is pinned AS A WHOLE LINE TOGETHER WITH THE SIX LINES ABOVE IT (their text, by a hash; its first hundred characters are shown). One
# that is added, taken away or changed - or whose six lines above changed - fails this test until someone has looked at WHAT IT SAYS:
# a new bare word must go into IsScreensOwnWord (Nextion.h), or it is not obeyed; no bare word may begin with p, q or f (a reply's first
# byte); a new reply or burst must be one the readers know - and has brought WIRE_SITES / WIRE_WORDS up to date. The screen's
# platformio.ini is looked at too: its core's own log stays off, its port stays the UART.
# (What this cannot see: bytes put together further away than six lines and handed to a line already known - by a variable.)
# (The tenth review, 15 Nov 2026 - reviewer A changed a copy of the screen so that new bytes went out, and 21 changes were NOT seen: the port
# under another name (a file-scope "auto &wire = Serial", "#define WIRE Serial", Serial0, a template handed Serial), the console by other
# doors (dprintf, fwrite to stdout, std::cout, write(1, ..), fputc, perror), the chip's own (esp_rom_uart_tx_one_char, uart_ll_write_txfifo,
# esp_log_write), files the scan never read (the project's include folder, a library's deeper folders, .hpp, .inc), and platformio.ini beyond
# one line of one environment. So now: EVERY FILE under src, lib and include is read, whatever its depth (a file of a kind not known is itself
# a failure; secrets.h is never opened); EVERY MENTION OF THE PORT is a site - the bare name Serial or Serial<n>, however it is used, but for
# its three reads - and so are stdout, stderr, cout and the UART by its number; the list of calls is longer; and platformio.ini is read whole.)
# (The twelfth review - reviewer A tried again: 13 new writers of 14 were not seen. The Arduino core's own C calls for a UART (uartBegin, uartWriteBuf,
# uartSetDebug); a second HardwareSerial on UART 0 made with braces, or its number written 0x0; write() to a descriptor held in a variable;
# "/dev/uart/0" opened; the FIFO's register written directly, by its name or its address; wprintf; the heap tracer's dump; abort() - which says where
# it was called, and a backtrace; the TX pin (43) driven by hand; and the ROM's printf put back on the UART by its other name. All sites now.)
import hashlib
WIRE_CALL = re.compile(r'\bSerial\d*\b(?!\s*\.\s*(?:available|read|peek)\b)'
                       r'|(?<![\w.])(?:printf|puts|putchar|putc|fputs|fputc|fprintf|fwrite|vprintf|vfprintf|dprintf|vdprintf|perror|putchar_unlocked|putc_unlocked|esp_rom_printf|ets_printf|uart_tx_chars|uart_write_bytes'
                       r'|uart_write_bytes_with_break|esp_rom_uart_tx_one_char|esp_rom_uart_putc|uart_tx_one_char|ets_write_char_uart|uart_ll_write_txfifo|uart_hal_write_txfifo|esp_log_write|esp_log_writev'
                       r'|esp_log_set_vprintf|ets_install_putc1|esp_rom_install_channel_putc|esp_rom_install_uart_printf|bleMailPost|lmTell|lmShout'
                       r'|log_printf|iprintf|fiprintf|viprintf|esp_backtrace_print|esp_backtrace_print_from_frame|heap_caps_print_heap_info|heap_caps_dump|heap_caps_dump_all'
                       r'|uart_set_baudrate|uart_param_config|uart_driver_install|uart_driver_delete|uart_set_pin|esp_vfs_dev_uart_use_driver|esp_vfs_dev_uart_use_nonblocking'
                       r'|uartBegin|uartEnd|uartWrite|uartWriteBuf|uartSetDebug|ets_install_uart_printf|wprintf|vwprintf|fwprintf|vfwprintf|putwchar|putwc|fputwc|fputws'
                       r'|heap_trace_dump|heap_trace_dump_caps|abort|esp_system_abort|panic_abort)\s*\('
                       r'|(?<![\w.>])write\s*\(\s*(?:\(\s*int\s*\)\s*)?\w+\s*,'
                       r'|"/dev/uart[^"]*"|\b(?:WRITE_PERI_REG|REG_WRITE|SET_PERI_REG_MASK|REG_SET_BIT)\s*\(|\bUART_FIFO(?:_AHB)?_REG\b|\bDR_REG_UART_BASE\b|\b0[xX]6000_?0000\b'
                       r'|\b(?:pinMode|digitalWrite|gpio_set_level|gpio_set_direction|gpio_reset_pin|gpio_matrix_out|esp_rom_gpio_connect_out_signal|pinMatrixOutAttach|gpio_pad_select_gpio)\s*\(\s*(?:GPIO_NUM_)?43\b|\bU0TXD\w*'
                       r'|\bESP_DRAM_LOG[EWIDV]\s*\(|\bESP_ERROR_CHECK(?:_WITHOUT_ABORT)?\s*\(|\bHardwareSerial\s+\w+\s*[({]\s*(?:0[xX]0*|0)\s*[)}]|\bHardwareSerial\s*[({]\s*(?:0[xX]0*|0)\s*[)}]'
                       r'|\b(?:stdout|stderr|cout|cerr|clog|UART0|UART_NUM_0)\b'
                       r'|\blog_[evdiwn]\s*\(|\bESP_(?:EARLY_)?LOG[EWIDV]\s*\(|\bbleMail\s*\.|\boutBuf\s*(?:\+=|\.\s*(?:append|push_back|insert|assign)\b|=(?!=))|\b(?:Print|Stream|HardwareSerial)\s*[&*]'
                       # (the thirteenth review, reviewer A's finding 6) WHATEVER GIVES THE ROM'S PRINTF, OR THE PORT'S DEBUG OUTPUT, A WAY TO THE UART - BY ITS BARE NAME: no
                       # bracket wanted behind it, a dot allowed in front (a #define for it, a pointer to it, the name in brackets, a comment or a line's end
                       # behind it, "Serial.setDebugOutput" through any object: eight ways went unseen)
                       r'|\b(?:esp_rom_install_channel_putc|ets_install_putc[12]?|esp_rom_install_uart_printf|ets_install_uart_printf|uartSetDebug|setDebugOutput|esp_rom_uart_putc|ets_write_char_uart'
                       r'|esp_rom_uart_tx_one_char|uart_tx_one_char|esp_rom_printf|ets_printf)\b')
PASTED = re.compile(r'##')   # ... and tokens pasted together by the preprocessor (a name made of two halves is seen by no pattern): outside a text between quotes
def is_wire_site(c): return bool(WIRE_CALL.search(c)) or bool(PASTED.search(re.sub(r'"(?:[^"\\]|\\.)*"', '""', c)))
OWN_LITERAL = re.compile(r'"((?:LDRC|ldrc|UKRULES|TIME=|FrontView)[^"]*)"')
SOURCE_KINDS = ('.h', '.hpp', '.hh', '.hxx', '.c', '.cc', '.cpp', '.cxx', '.ino', '.inc', '.ipp', '.tpp', '.s', '.S')
def screen_texts(root):
    """The screen's own source: ({file name: text}, [files of a kind not known]) - EVERY file under its src, lib and include folders, at any
    depth. Not opened: secrets.h (it holds passwords; it is not part of a published build's source) and the fonts' tables."""
    out, odd, seen = {}, [], {}
    for top in ('src', 'lib', 'include'):
        for d, _, files in sorted(os.walk(os.path.join(root, top))):
            for f in sorted(files):
                p = os.path.join(d, f); rel = os.path.relpath(p, root)
                if f == 'secrets.h' or 'nextion_fonts' in f or f == '.DS_Store': continue
                if not f.endswith(SOURCE_KINDS): odd.append(rel); continue
                seen.setdefault(f, []).append((rel, p))
    for f, places in seen.items():
        for rel, p in places:
            out[f if len(places) == 1 else rel] = open(p, encoding='utf-8', errors='replace').read()   # (by its bare name, as WIRE_SITES has it - by its path when two files share one)
    return out, sorted(odd)
def ini_problems(ini):
    """The screen's platformio.ini, WHOLE: what would turn its console - the wire - into something else in ANY of its builds."""
    bad = []; live = '\n'.join(l.split(';')[0] for l in ini.split('\n'))
    flags = re.search(r'\[env:crowpanel50\].*?\nbuild_flags\s*=\s*([^\n]*)', live, re.S)
    if not flags or '-DCORE_DEBUG_LEVEL=0' not in flags.group(1) or '-DARDUINO_USB_CDC_ON_BOOT=0' not in flags.group(1): bad.append('the first environment\'s flags do not say CORE_DEBUG_LEVEL=0 and ARDUINO_USB_CDC_ON_BOOT=0')
    if len(re.findall(r'CORE_DEBUG_LEVEL', live)) != 1 or len(re.findall(r'ARDUINO_USB_CDC_ON_BOOT', live)) != 1: bad.append('CORE_DEBUG_LEVEL or ARDUINO_USB_CDC_ON_BOOT is named more than once (another build changes it)')
    if re.search(r'EMU_ECHO|ARDUHAL_LOG_LEVEL|LOG_LOCAL_LEVEL|CONFIG_LOG_DEFAULT_LEVEL', live): bad.append('a build echoes its commands or turns a log on (EMU_ECHO, ARDUHAL_LOG_LEVEL, LOG_LOCAL_LEVEL)')
    if re.search(r'(?:^|\s)-U\s*\w|\bbuild_unflags\b|\bbuild_src_flags\b|\bextra_scripts\b|(?:^|\s)-D\s+\w|(?:^|\s)-include\b', live): bad.append('flags are taken away, added by another door, or written apart (-U, build_unflags, build_src_flags, extra_scripts, "-D NAME")')
    for mo in re.finditer(r'^build_flags\s*=\s*([^\n]*)', live, re.M):
        if '${env:' not in mo.group(1) and '-DCORE_DEBUG_LEVEL=0' not in mo.group(1): bad.append('an environment sets its flags afresh, without the first one\'s: ' + mo.group(1)[:60])
    return bad
INI_SELFTEST = [   # (reviewer A's) changes to a copy of the screen's platformio.ini that must be seen
    ('another environment undefines the log level and turns the core\'s log on by another name', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL -UCORE_DEBUG_LEVEL -DARDUHAL_LOG_LEVEL=5'),
    ('the FULL build makes Serial the USB port', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL -UARDUINO_USB_CDC_ON_BOOT -DARDUINO_USB_CDC_ON_BOOT=1'),
    ('EMU_ECHO by a build_src_flags line', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL\nbuild_src_flags = -DEMU_ECHO'),
    ('"-D CORE_DEBUG_LEVEL=5" written apart, in another environment', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL -D CORE_DEBUG_LEVEL=5'),
    ('an environment that sets its flags afresh', 'build_flags = ${env:crowpanel50.build_flags} -DLDRC_FULL', 'build_flags = -DBOARD_HAS_PSRAM -DLDRC_FULL'),
    ('the log level raised where it stands', '-DCORE_DEBUG_LEVEL=0', '-DCORE_DEBUG_LEVEL=3'),
    ('a script run at build time', '[env:ota]\nextends = env:crowpanel50', '[env:ota]\nextends = env:crowpanel50\nextra_scripts = pre:dev/flags.py'),
]
# THE LIBRARIES THE SCREEN IS BUILT WITH CAN WRITE TO THE WIRE BY THEMSELVES (the eleventh review, reviewer A's finding 2) - and they stand outside the
# screen's own source: the pin above did not see them. One does, today: the Bluetooth library (NimBLE-Arduino, esp_nimble_hci.c) says "Host not
# enabled. Dropping the packet!" and three more with the ROM's printf, straight to UART0, past the screen's hook for the system's log. And the
# build asked for its libraries by a RANGE ("^2.2.3"): the next build takes whatever is newest, unseen. So:
#  - every library in the two released builds' folders (.pio/libdeps/ota and ota_full) is PINNED here by its version and by what its files hold;
#  - the screen's platformio.ini is pinned WHOLE (a library added, another board, platform_packages, a moved source folder: all of it);
#  - what the libraries say with the ROM's printf today is LIB_WORDS: dev/test_stallscreen says them to the main board (scene_zero_rules).
# A pin that speaks: LOOK at what changed (can it put a byte on the wire?), then `python3 <scratch>/edits/regen_wire_sites.py <tree> --write`.
# (Screen 1.11.198 keeps the ROM's printf to itself - src/main.cpp romPutc - and names exact versions.)
# (The twelfth review, reviewer A's finding 3 - THE PIN LOOKED AT THE WRONG FOLDER. It hashed the screen project's own .pio: the BENCH builds. The firmware that
#  is PUBLISHED is built in a copy of the project that holds no secrets.h - dev/out/screen_build (release_v1b.py clean_copy) - with a .pio and libraries
#  of its own; asked for by a range, that copy had taken NimBLE-Arduino 2.5.2 and JPEGDEC 1.8.5 on 11 Nov 2026 while the bench folder still held 2.5.1
#  and 1.8.4, and THOSE were pinned here as "what the field runs". They were not: the staged images of screen 1.11.197 are the release folder's, byte
#  for byte. So now:
#   - the pins are the PUBLISHED build's: the libraries in dev/out/screen_build;
#   - dev/release_v1b.py hashes that folder after its own build and REFUSES a difference - and a folder it cannot look at (here, with no such folder
#     beside the tree, the pin can only say that it was not looked at);
#   - the bench folder is looked at too: built with other libraries than the published firmware, it says so (a bench build goes to his own screens
#     through the workshop door).)
LIB_ENVS = ('ota', 'ota_full')
RELEASE_SCREEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'screen_build')   # dev/out/screen_build
LIB_PINS = [   # (library, version, its files) - the PUBLISHED screens in the field (1.11.197, releases B206 to B210) are built with these
    ('ArduinoJson', '7.4.3', 'cc9bc1de6a51d23c'),
    ('GFX Library for Arduino', '1.3.8', '57cf9833fa9db26f'),
    ('JPEGDEC', '1.8.5', '56040dadfd8b17a5'),
    ('NimBLE-Arduino', '2.5.2', '86601ed5a7f960ba'),
    ('SensorLib', '0.2.6', '2793c360c4a679f5'),
    ('bb_spi_lcd', '2.9.10', '02297028896b508d'),
]
INI_PIN = 'faf2ea8354e08551'   # the screen's platformio.ini, its comments left out
# (The twelfth review, reviewer A's finding 7: the platform is named by its version - but IT asks for the Arduino framework by a range, "~3.20017.0": the
#  framework - the core's own code, its UART driver, its logging - could move on unseen. The framework this machine builds the screen with is pinned by
#  its version, which carries its commit. Screen 1.11.198's platformio.ini names it exactly as well - platform_packages.)
FRAMEWORK_PIN = '3.20017.241212+sha.dcc1105b'   # framework-arduinoespressif32, as platform espressif32 7.0.1 takes it on the machine the releases are built on
FRAMEWORK_DIR = os.path.expanduser('~/.platformio/packages/framework-arduinoespressif32')
def framework_now():
    """the Arduino framework package the screen is built with on this machine: its version - None when it is not installed here"""
    try: return json.load(open(os.path.join(FRAMEWORK_DIR, 'package.json'), encoding='utf-8'))['version']
    except (OSError, ValueError, KeyError): return None
# (The thirteenth review, reviewer A's finding 7: the framework was pinned by its version TEXT - a file of it changed by hand, for a look at something, and left so,
#  went unseen. Pinned by what its files hold now: the core's own source, its libraries, the boards' variants, the build's scripts, the partition tables
#  and the precompiled SDK of the screen's chip - its UART driver and its logging are in there. Half a second.)
FRAMEWORK_PARTS = ('package.json', 'cores', 'libraries', 'variants', 'tools/platformio-build.py', 'tools/platformio-build-esp32s3.py', 'tools/partitions', 'tools/sdk/esp32s3')
FRAMEWORK_FILES_PIN = '5d6b6afdb9200d65'
def framework_files_now(top=None):
    """what the files of the Arduino framework on this machine hold (sha) - None when it is not installed here"""
    top = FRAMEWORK_DIR if top is None else top
    if not os.path.isdir(os.path.join(top, 'cores')): return None
    h = hashlib.sha1()
    for part in FRAMEWORK_PARTS:
        p = os.path.join(top, part)
        files = [p] if os.path.isfile(p) else [os.path.join(d, f) for d, dirs, fs in os.walk(p) for f in fs if f not in ('.DS_Store', '.piopm')]
        for fp in sorted(files):
            h.update(os.path.relpath(fp, top).encode('utf-8', 'replace')); h.update(b'\0'); h.update(open(fp, 'rb').read()); h.update(b'\0')
    return h.hexdigest()[:16]
def images_older_than_libs(clean):
    """(the thirteenth review) AN IMAGE IS NOT OLDER THAN THE LIBRARIES BESIDE IT. The pin hashes the build's library folder - not what the image was made of: an
    image kept from an earlier build (--no-build), its libraries installed anew since, passed. [] when every image there is newer than every file of
    its build's libraries."""
    bad = []
    for env in LIB_ENVS:
        img = os.path.join(clean, '.pio', 'build', env, 'firmware.bin'); top = os.path.join(clean, '.pio', 'libdeps', env)
        if not os.path.isfile(img) or not os.path.isdir(top): continue
        newest = max((os.path.getmtime(os.path.join(d, f)) for d, _, fs in os.walk(top) for f in fs if f != '.DS_Store'), default=0)
        if newest > os.path.getmtime(img): bad.append('the %s image is OLDER than the libraries beside it (by %d s): it was built before they changed - build it again (leave out --no-build)' % (env, newest - os.path.getmtime(img)))
    return bad
LIB_WORDS = ['%s failed to os_mbuf_append; rc = %d\\n', 'Failed to allocate buffer, retrying\\n', 'Host not enabled. Dropping the packet!', 'Received HCI data length at host (%d) exceeds maximum configured HCI event buffer size (%d).', 'assertion:%s\\n', 'line:%d,function:%s\\n']   # what the libraries say with the ROM's printf, as their source has it (NimBLE-Arduino 2.5.1: esp_nimble_hci.c, nimble_npl_os.h)
def ini_live(ini): return '\n'.join(l.split(';')[0].rstrip() for l in ini.split('\n') if l.split(';')[0].strip())
def ini_pin(ini): return hashlib.sha1(ini_live(ini).encode('utf-8', 'replace')).hexdigest()[:16]
def lib_version(d):
    for f in ('library.json', 'library.properties'):
        q = os.path.join(d, f)
        if not os.path.exists(q): continue
        s = open(q, encoding='utf-8', errors='replace').read()
        mo = re.search(r'"version"\s*:\s*"([^"]+)"', s) if f.endswith('json') else re.search(r'^version=(.*)$', s, re.M)
        if mo: return mo.group(1).strip()
    return '?'
def lib_named(ini):
    """the libraries the screen's platformio.ini asks for (lib_deps): their names"""
    mo = re.search(r'^lib_deps\s*=\s*\n((?:[ \t]+\S[^\n]*\n?)+)', ini_live(ini) + '\n', re.M)
    return sorted(l.split('@')[0].strip().split('/')[-1].strip() for l in mo.group(1).split('\n') if l.strip()) if mo else []
def lib_pins(root, ini):
    """[(library, version, sha of its files)] of the released builds' folders: EVERY library that lies there - None when the screen has not been
    built here; a string when the builds differ, or when a library the ini does not name is BUILT INTO the firmware.
    (The thirteenth review: a library the ini does not name - one that an installed library asks for - was pinned only by "has it a built folder of
    its own?": a header-only library has none (ArduinoJson has none), and would have come into the build unseen. Every folder is pinned now.)"""
    per = []; named = lib_named(ini)
    for env in LIB_ENVS:
        top = os.path.join(root, '.pio', 'libdeps', env)
        if not os.path.isdir(top): return None
        rows = []
        for name in sorted(os.listdir(top)):
            d = os.path.join(top, name)
            if not os.path.isdir(d): continue
            if name not in named:
                if glob.glob(os.path.join(root, '.pio', 'build', env, 'lib*', name)): return 'a library that platformio.ini does not name is built into the screen (%s, %s)' % (name, env)
            h = hashlib.sha1()
            for dd, dirs, files in os.walk(d):
                dirs.sort()
                for f in sorted(files):
                    if f in ('.DS_Store', '.piopm'): continue
                    fp = os.path.join(dd, f); h.update(os.path.relpath(fp, d).encode('utf-8', 'replace')); h.update(b'\0'); h.update(open(fp, 'rb').read()); h.update(b'\0')
            rows.append((name, lib_version(d), h.hexdigest()[:16]))
        per.append(rows)
    if any(r != per[0] for r in per[1:]): return 'the released builds (%s) are not built with the same libraries' % ', '.join(LIB_ENVS)
    return per[0]
def lib_rom_words(root):
    """what the libraries' sources say with the ROM's printf (their string's first 24 letters), found afresh"""
    out = set()
    top = os.path.join(root, '.pio', 'libdeps', LIB_ENVS[0])
    for dd, _, files in os.walk(top):
        for f in files:
            if not f.endswith(SOURCE_KINDS): continue
            s = open(os.path.join(dd, f), encoding='utf-8', errors='replace').read()
            for mo in re.finditer(r'\b(?:esp_rom_printf|ets_printf)\s*\(\s*"((?:[^"\\]|\\.)*)"', s): out.add(mo.group(1))
    return sorted(out)
def pins_differ(now, pins):
    """what differs between the libraries found in a build's folder and the pins: [] when they are the same"""
    bad = []; was = {a: (b, c) for a, b, c in pins}
    for a, b, c in now:
        if a not in was: bad.append('a library the screen is built with is NEW: %s %s - can it put a byte on the wire? LOOK, then regenerate' % (a, b))
        elif was[a] != (b, c): bad.append('a library the screen is built with has CHANGED: %s %s -> %s (its files: %s -> %s) - LOOK at what it writes to the console, then regenerate' % (a, was[a][0], b, was[a][1], c))
    for a in was:
        if a not in [x[0] for x in now]: bad.append('a library pinned here is no longer in the screen\'s build: ' + a)
    return bad
def lib_problems(root, ini, release=None):
    """root: the screen's project beside this tree (its platformio.ini; its bench builds). release: the folder the PUBLISHED firmware is built in
    (dev/out/screen_build). -> (what is wrong, a note or None). The note: the published build's libraries could not be looked at here."""
    bad = []; notes = []
    if ini_pin(ini) != INI_PIN: bad.append('the screen\'s platformio.ini is not the one pinned here (%s, pinned %s): a library added or asked for anew, another board, platform_packages, a moved folder ... LOOK, then regenerate' % (ini_pin(ini), INI_PIN))
    release = RELEASE_SCREEN if release is None else release
    rini = os.path.join(release, 'platformio.ini')
    pub = lib_pins(release, open(rini, encoding='utf-8', errors='replace').read()) if os.path.exists(rini) else None
    bench = lib_pins(root, ini)
    if isinstance(pub, str): bad.append('the published build (dev/out/screen_build): ' + pub)
    elif pub is not None: bad += ['the PUBLISHED screen build (dev/out/screen_build): ' + b for b in pins_differ(pub, [tuple(x) for x in LIB_PINS])]
    if isinstance(bench, str): bad.append('the bench build beside this tree: ' + bench)
    elif bench is not None and bench != [tuple(x) for x in LIB_PINS]:
        notes.append('(NOTE: the BENCH build of the screen beside this tree is built with other libraries than the published firmware - a bench build installed through the workshop door is not what "Check for update" gives: '
                     + '; '.join('%s %s (published %s)' % (a, b, dict((x[0], x[1]) for x in LIB_PINS).get(a, 'none')) for a, b, c in bench if (a, b, c) not in [tuple(x) for x in LIB_PINS]) + ')')
    looked = release if isinstance(pub, list) else root if isinstance(bench, list) else None
    if looked:
        words = lib_rom_words(looked)
        for w in words:
            if w not in LIB_WORDS: bad.append('a library says something with the ROM\'s printf that is not among LIB_WORDS (dev/test_stallscreen says those to the main board): ' + repr(w[:70]))
        for w in LIB_WORDS:
            if w not in words: bad.append('LIB_WORDS names something no library says with the ROM\'s printf any more: ' + repr(w[:70]))
    if pub is None: notes.append('(the PUBLISHED screen firmware has not been built beside this tree - dev/out/screen_build: the libraries it is built with were not looked at here. dev/release_v1b.py looks at them after its own build, and refuses a difference)')
    fw = framework_now()
    if fw is None: notes.append('(the Arduino framework the screen is built with is not installed on this machine: not looked at)')
    elif fw != FRAMEWORK_PIN: bad.append('the Arduino framework the screen is built with on this machine has CHANGED: %s, pinned %s - its UART driver and its logging are in it: LOOK, then bring FRAMEWORK_PIN up to date' % (fw, FRAMEWORK_PIN))
    elif framework_files_now() != FRAMEWORK_FILES_PIN: bad.append('the FILES of the Arduino framework on this machine are not the pinned ones (%s, pinned %s) though its version is: a file of it was changed - LOOK (its UART driver and its logging are in it), then put it right or bring FRAMEWORK_FILES_PIN up to date' % (framework_files_now(), FRAMEWORK_FILES_PIN))
    if isinstance(pub, list): bad += ['the PUBLISHED screen build (dev/out/screen_build): ' + b for b in images_older_than_libs(release)]
    return bad, ('\n'.join(notes) if notes else None), isinstance(pub, list)
def release_lib_problems(clean):
    """FOR dev/release_v1b.py, after its own build: the libraries the firmware about to be published IS built with, against the pins. [] when they are
    the same; a folder that cannot be looked at is itself a problem (the twelfth review: "not looked at" passed, and the gate read exit codes only)."""
    rini = os.path.join(clean, 'platformio.ini')
    if not os.path.exists(rini): return ['the folder the published screen firmware is built in has no platformio.ini: ' + clean]
    now = lib_pins(clean, open(rini, encoding='utf-8', errors='replace').read())
    if now is None: return ['the libraries of the published screen build could not be looked at (no .pio/libdeps/%s in %s)' % (' or '.join(LIB_ENVS), clean)]
    if isinstance(now, str): return [now]
    bad = pins_differ(now, [tuple(x) for x in LIB_PINS])
    fw = framework_now()
    if fw != FRAMEWORK_PIN: bad.append('the Arduino framework this machine built the screen with is %s, pinned %s' % (fw or 'not to be found', FRAMEWORK_PIN))
    elif framework_files_now() != FRAMEWORK_FILES_PIN: bad.append('the files of the Arduino framework this machine built the screen with are not the pinned ones (%s, pinned %s): a file of it was changed' % (framework_files_now(), FRAMEWORK_FILES_PIN))
    return bad + images_older_than_libs(clean)
LIB_SELFTEST = [   # (what, the pins as they would be found, the ini's change): each must be SEEN
    ('a library moved on to another version', lambda pins: [(a, b + '.1' if a == 'NimBLE-Arduino' else b, c) for a, b, c in pins], None),
    ('a library\'s files changed under the same version', lambda pins: [(a, b, '0' * 16 if a == 'ArduinoJson' else c) for a, b, c in pins], None),
    ('a library more', lambda pins: pins + [('Zzz', '1.0.0', '1' * 16)], None),
    ('a library added to lib_deps', None, ('    bitbank2/JPEGDEC', '    someone/Chatty @ ^1.0.0\n    bitbank2/JPEGDEC')),
    ('another board', None, ('board = esp32-s3-devkitc-1', 'board = esp32-s3-devkitm-1')),
    ('the source folder moved', None, ('framework = arduino', 'framework = arduino\nsrc_dir = other')),
    ('platform_packages', None, ('framework = arduino', 'framework = arduino\nplatform_packages = framework-arduinoespressif32 @ 3.0.0')),
]
def wire_sites(texts):
    found, words = [], set()
    for name in sorted(texts):
        lines = texts[name].split('\n')
        code = [re.sub(r'\s+', ' ', re.sub(r'\s//.*$', '', l).strip()) if not l.strip().startswith('//') else '' for l in lines]
        for i, c in enumerate(code):
            words.update(OWN_LITERAL.findall(c))
            if not is_wire_site(c): continue
            h = hashlib.sha1('\n'.join(code[max(0, i - 6):i + 1]).encode('utf-8', 'replace')).hexdigest()[:10]
            found.append('%s: %s #%s' % (name, c[:100], h))
    return found, sorted(words)
WIRE_SELFTEST = [   # (the ninth review's list) changes to the screen's source that the pin must see
    # (the twelfth review, reviewer A's thirteen - each a new writer put in front of timePoll)
    ('the Arduino core\'s own C calls for UART 0', 'main.cpp', 'static void timePoll() {\n', 'static void sayHal() { uart_t *u = uartBegin(0, 921600, SERIAL_8N1, -1, -1, 256, 0, false, 112); uartWriteBuf(u, (const uint8_t *) "page 9", 6); }\nstatic void timePoll() {\n'),
    ('a second HardwareSerial on UART 0, made with braces', 'main.cpp', 'static void timePoll() {\n', 'static HardwareSerial wire2{0};\nstatic void timePoll() {\n'),
    ('a second HardwareSerial on UART 0, its number written 0x0', 'main.cpp', 'static void timePoll() {\n', 'static HardwareSerial wire3(0x0);\nstatic void timePoll() {\n'),
    ('write() to a descriptor held in a variable', 'main.cpp', 'static void timePoll() {\n', 'static void sayFd() { const int out = 1; write(out, "page", 4); }\nstatic void timePoll() {\n'),
    ('"/dev/uart/0" opened', 'main.cpp', 'static void timePoll() {\n', 'static int sayDev() { return open("/dev/uart/0", O_WRONLY); }\nstatic void timePoll() {\n'),
    ('the FIFO\'s register written directly', 'main.cpp', 'static void timePoll() {\n', "static void sayReg() { WRITE_PERI_REG(UART_FIFO_AHB_REG(0), 'p'); }\nstatic void timePoll() {\n"),
    ('the FIFO\'s register by its address', 'main.cpp', 'static void timePoll() {\n', "static void sayAddr() { *(volatile uint32_t *) 0x60000000 = 'q'; }\nstatic void timePoll() {\n"),
    ('a wide-character print', 'main.cpp', 'static void timePoll() {\n', 'static void sayWide() { wprintf(L"page"); }\nstatic void timePoll() {\n'),
    ('the heap tracer\'s dump', 'main.cpp', 'static void timePoll() {\n', 'static void sayTrace() { heap_trace_dump(); }\nstatic void timePoll() {\n'),
    ('abort()', 'main.cpp', 'static void timePoll() {\n', 'static void sayAbort() { if (millis() > 4000000000u) abort(); }\nstatic void timePoll() {\n'),
    ('the TX pin driven by hand', 'main.cpp', 'static void timePoll() {\n', 'static void sayPin() { pinMode(43, OUTPUT); digitalWrite(43, LOW); }\nstatic void timePoll() {\n'),
    ('the ROM\'s printf put back on the UART by its other name', 'main.cpp', 'static void timePoll() {\n', 'static void sayBack() { ets_install_uart_printf(); }\nstatic void timePoll() {\n'),
    ('the port\'s debug output turned on by the core\'s own call', 'main.cpp', 'static void timePoll() {\n', 'static void sayDbg() { uartSetDebug(nullptr); }\nstatic void timePoll() {\n'),
    ('a new write to the port', 'main.cpp', '    if (cmd == "sendme") {', '    if (cmd == "hello") { Serial.write((const uint8_t *) "pong", 4); return; }\n    if (cmd == "sendme") {'),
    ('a printf in the page loader (stdout is the wire)', 'main.cpp', 'static bool loadPage(const std::string &name) {\n', 'static bool loadPage(const std::string &name) {\n    printf("page %s up\\n", name.c_str());\n'),
    ('a word pushed straight into the Bluetooth mail', 'ble_device.h', 'static void blePoll() {\n', 'static void bleSayIdle() { bleMail.push_back("pipe idle"); }\nstatic void blePoll() {\n'),
    ('the page number\'s first byte, 66 -> 67', 'main.cpp', 'const uint8_t f[5] = { 0x66, (uint8_t) (getPage >= 0 ? getPage : page.id),', 'const uint8_t f[5] = { 0x67, (uint8_t) (getPage >= 0 ? getPage : page.id),'),   # (screen 1.11.198's line)
    ('the power-on bytes, 88 -> 89', 'main.cpp', 'static const uint8_t powerOn[] = { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF };', 'static const uint8_t powerOn[] = { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x89, 0xFF, 0xFF, 0xFF };'),
    ('a burst\'s frame mark, 7E 7E -> 7D 7E', 'main.cpp', 'const char h[4] = { 0x7E, 0x7E,', 'const char h[4] = { 0x7D, 0x7E,'),
    ('esp_rom_printf from the other core\'s watch', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    if (gone > 150) esp_rom_printf("quiet %lu\\n", (unsigned long) gone);\n'),
    ('a Print& alias of the port', 'main.cpp', 'static void timePoll() {\n', 'static void sayQnh() { Print &w = Serial; w.print("qnh?"); }\nstatic void timePoll() {\n'),
    ('a page\'s word put into a burst by the firmware itself', 'main.cpp', '    if (cmd == "sendme") {', '    if (cmd == "ldrcfs") { outBuf += "FailSAVE"; flushOut(); return; }\n    if (cmd == "sendme") {'),
    ('a value reply\'s first byte, q -> r', 'main.cpp', "const int32_t v = host.getSys(ref); const uint8_t f[8] = { 'q',", "const int32_t v = host.getSys(ref); const uint8_t f[8] = { 'r',"),
    ('the restart word no longer said after a watchdog (its condition)', 'main.cpp', 'if (why != ESP_RST_POWERON && !pageNames.empty()) { delay(300); Serial.printf("FrontView rst=%d", (int) why); }', 'if (why == ESP_RST_SW && !pageNames.empty()) { delay(300); Serial.printf("FrontView rst=%d", (int) why); }'),
    ('the time word begins with p', 'main.cpp', 'snprintf(b, sizeof(b), "TIME=%ld", local);', 'snprintf(b, sizeof(b), "pTIME=%ld", local);'),
    ('puts() of a word', 'main.cpp', 'static void timePoll() {\n', 'static void sayHello() { puts("qed"); }\nstatic void timePoll() {\n'),
    ('the text reply no longer ends FF FF FF', 'main.cpp', 'std::string f = "p" + s; f += "\\xFF\\xFF\\xFF";', 'std::string f = "p" + s; f += "\\xFF\\xFF";'),
    ('a log line of the core\'s own', 'main.cpp', 'static void timePoll() {\n', 'static void timePoll() {\n    log_e("time");\n'),
    ('the line "the loop is silent" given a second end', 'last_moments.h', 'char line[128]; int n = snprintf(line, sizeof line - 1, "LDRCLOG %s", s);', 'char line[128]; int n = snprintf(line, sizeof line - 1, "LDRCLOG %s\\n", s);'),   # (screen 1.11.198's line: it ends its line itself, behind this)
    ('the word a touch of the screen\'s own page says', 'cli_device.h', 'Serial.write((const uint8_t *) "UKRULES", 7); }', 'Serial.write((const uint8_t *) "UKRULE!", 7); }'),
    # (the tenth review, reviewer A: none of these was seen)
    ('the port under another name, made far above its use', 'main.cpp', 'static uint32_t cmdCount = 0, badCount = 0;', 'static uint32_t cmdCount = 0, badCount = 0;\nstatic auto &wire = Serial;'),
    ('a macro for the port', 'main.cpp', 'static uint32_t cmdCount = 0, badCount = 0;', 'static uint32_t cmdCount = 0, badCount = 0;\n#define WIRE Serial'),
    ('the UART by its other name, Serial0', 'main.cpp', 'static void timePoll() {\n', 'static void sayFresh() { Serial0.print("fresh"); }\nstatic void timePoll() {\n'),
    ('a template handed the port, two lines apart', 'main.cpp', 'static void timePoll() {\n', 'template <typename T> static void sayTo(T &port) { port.print("quiet"); }\nstatic void sayQuiet() { sayTo(\n    Serial\n); }\nstatic void timePoll() {\n'),
    ('dprintf(1, ..)', 'main.cpp', 'static void timePoll() {\n', 'static void sayD() { dprintf(1, "pwned\\n"); }\nstatic void timePoll() {\n'),
    ('fwrite(.., stdout)', 'main.cpp', 'static void timePoll() {\n', 'static void sayF() { fwrite("page", 1, 4, stdout); }\nstatic void timePoll() {\n'),
    ('std::cout', 'main.cpp', 'static void timePoll() {\n', 'static void sayC() { std::cout << "fresh"; }\nstatic void timePoll() {\n'),
    ('write(1, ..): a page number by hand', 'main.cpp', 'static void timePoll() {\n', 'static void sayW() { write(1, "f\\x09\\xFF\\xFF\\xFF", 5); }\nstatic void timePoll() {\n'),
    ('fputc', 'main.cpp', 'static void timePoll() {\n', "static void sayP() { fputc('p', stdout); }\nstatic void timePoll() {\n"),
    ('perror', 'main.cpp', 'static void timePoll() {\n', 'static void sayE() { perror("quiet"); }\nstatic void timePoll() {\n'),
    ('esp_rom_uart_tx_one_char from the other core\'s watch', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', "    if (gone < 200) { saidFor = 0; return; }\n    if (gone > 150) esp_rom_uart_tx_one_char('p');\n"),
    ('uart_ll_write_txfifo straight into the FIFO', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    if (gone > 150) uart_ll_write_txfifo(&UART0, (const uint8_t *) "q", 1);\n'),
    ('esp_log_write', 'main.cpp', 'static void timePoll() {\n', 'static void sayL() { esp_log_write(ESP_LOG_ERROR, "t", "page fault\\n"); }\nstatic void timePoll() {\n'),
    ('the system\'s log hook handed to vprintf', 'main.cpp', 'esp_log_set_vprintf(sysLogHook);', 'esp_log_set_vprintf(vprintf);'),
    # (the thirteenth review, reviewer A's experiment 5: none of these was seen - the pin wanted the name with its bracket behind it, and no dot in front)
    ('the ROM\'s printing given to the UART under another name (a #define)', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n#define LM_GIVE_BACK esp_rom_install_uart_printf\n    LM_GIVE_BACK();\n'),
    ('... through a function pointer', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    { void (*back)(void) = esp_rom_install_uart_printf; back(); }\n'),
    ('... with a block comment between the name and its bracket', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    esp_rom_install_uart_printf /* as the system had it */ ();\n'),
    ('... the name in brackets', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    (esp_rom_install_uart_printf)();\n'),
    ('... a line broken behind the name', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    esp_rom_install_uart_printf\\\n    ();\n'),
    ('... the name pasted together by the preprocessor', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n#define LM_CAT(a, b) a##b\n    LM_CAT(esp_rom_install_uart_, printf)();\n'),
    ('the UART\'s own write installed, both names in brackets', 'last_moments.h', '    if (gone < 200) { saidFor = 0; return; }\n', '    if (gone < 200) { saidFor = 0; return; }\n    (esp_rom_install_channel_putc)(1, (esp_rom_uart_putc));\n'),
    ('the port\'s debug output through a pointer to a port of another name', 'main.cpp', 'static void timePoll() {\n', 'static void sayDbg(HardwareSerial *q) { q->setDebugOutput(true); }\nstatic void timePoll() {\n'),
]
PAGE_CODES_KNOWN = [(5, 'tm0'), (15, 'postinitialize'), (29, 'b22')]
PAGE_EVENTS_KNOWN = ('preinitialize', 'postinitialize', 'touch_press', 'touch_release'); PART_EVENTS_KNOWN = ('p', 'r', 'm', 't')
def page_scan(pages):
    """What the scripts of the card's pages do that the main board is never told of - pages: {number: the page file's content}:
    (the pages that go to another page BY THEMSELVES, the words printed that begin as a reply does or look like the screen's own, the events
    of a kind this scan does not know). The tenth review: a page command was looked for at the BEGINNING of a line only - "if(c0.val==1){page
    FrontView}" passed; and a page's page_exit script (what it prints falls between the NEXT page command's two markers) was not looked at at
    all: any event that is not one of the kinds known fails here, and must be thought about."""
    def live(script): return '\n'.join(re.sub(r'//.*$', '', l) for l in script.split('\n'))
    movers, first, odd = [], set(), []
    for pid in sorted(pages):
        pg = pages[pid]; scripts = []
        for k, v in (pg.get('ev') or {}).items():
            if k not in PAGE_EVENTS_KNOWN: odd.append('%s: the page\'s %s' % (pg['name'], k))
            if v: scripts.append(v)
        for c in pg['comps']:
            for k, v in (c.get('ev') or {}).items():
                if k not in PART_EVENTS_KNOWN: odd.append('%s: %s\'s %s' % (pg['name'], c['n'], k))
                if v: scripts.append(v)
        for s in scripts:
            if re.search(r'(?<![\w."])page\s+\w', live(s)): movers.append(pg['name'])
            for w in re.findall(r'prints?\s+"([^"]*)"', live(s)):
                if w[:1] in ('p', 'q') or 'FrontView' in w or any(w.startswith(o) for o in ('LDRC', 'UKRULES!', 'TIME=', 'ldrcpipe=', 'ldrctel ', 'ldrcrep ')): first.add(w)
    return sorted(set(movers)), sorted(first), odd
def _p_exit_print(pg): pg.setdefault('ev', {})['page_exit'] = 'va0.val=128+39\nprint va0.val'
def _p_exit_word(pg): pg.setdefault('ev', {})['page_exit'] = 'print "SwitchesView1"'
def _p_if_page(pg): [c for c in pg['comps'] if c.get('txt') == 'OK'][0]['ev']['r'] = 'va0.val=128+39\nprint va0.val\nif(c0.val==1){page FrontView}'
def _p_timer_page(pg): pg['comps'].append({'n': 'tmz', 'i': 94, 't': 'timer', 'g': 'l', 'a': {'tim': 400, 'en': 1}, 'ev': {'t': 'if(c0.val==1){page FrontView}'}})
def _p_page_by_number(pg): [c for c in pg['comps'] if c.get('txt') == 'OK'][0]['ev']['r'] = 'va0.val=128+39\nprint va0.val\n  if(c0.val==1)\n  {\n    page 13\n  }'
def _p_word_q(pg): pg['comps'].append({'n': 'bq', 'i': 93, 't': 'button', 'g': 'l', 'x': 0, 'y': 0, 'w': 1, 'h': 1, 'ev': {'r': 'if(c0.val==1){prints "qnh",0}'}})
PAGE_SCAN_SELFTEST = [   # (reviewer A's) changes to a copy of page 9 that page_scan must see
    ('a page_exit script that prints OK\'s code', _p_exit_print), ('a page_exit script that prints a page\'s word', _p_exit_word),
    ('OK says "page FrontView" behind an if on the same line', _p_if_page), ('a timer says "page FrontView" behind an if on the same line', _p_timer_page),
    ('OK says "page 13" on a line of its own, indented', _p_page_by_number), ('a word that begins with q, behind an if on the same line', _p_word_q),
]
def _p_timer_on(pg): pg['comps'].append({'n': 'tmy', 'i': 96, 't': 'timer', 'g': 'l', 'a': {'tim': 400, 'en': 1}, 'ev': {'t': 'va0.val=128+39\nprint va0.val'}})
def _p_timer_by_script(pg): pg['comps'].append({'n': 'tmx', 'i': 99, 't': 'timer', 'g': 'l', 'a': {'tim': 400, 'en': 0}, 'ev': {'t': 'va0.val=128+39\nprint va0.val'}}); pg['ev']['postinitialize'] = pg['ev'].get('postinitialize', '') + '\ntmx.en=1'
def _p_click_two(pg):
    pg['comps'].append({'n': 'bx1', 'i': 97, 't': 'button', 'g': 'l', 'x': 0, 'y': 0, 'w': 1, 'h': 1, 'ev': {'r': 'click bx2,0'}})
    pg['comps'].append({'n': 'bx2', 'i': 98, 't': 'button', 'g': 'l', 'x': 0, 'y': 0, 'w': 1, 'h': 1, 'ev': {'r': 'va0.val=128+39\nprint va0.val'}})
    pg['ev']['postinitialize'] = pg['ev'].get('postinitialize', '') + '\nclick bx1,0'
def _p_click_one(pg): pg['comps'].append({'n': 'bx2', 'i': 98, 't': 'button', 'g': 'l', 'x': 0, 'y': 0, 'w': 1, 'h': 1, 'ev': {'r': 'va0.val=128+39\nprint va0.val'}}); pg['ev']['postinitialize'] = pg['ev'].get('postinitialize', '') + '\nclick bx2,0'
def _p_print_behind_if(pg): pg['ev']['postinitialize'] = pg['ev'].get('postinitialize', '') + '\nif(c0.val<5){print va0.val}'
def _p_word_f(pg): pg['ev']['postinitialize'] = pg['ev'].get('postinitialize', '') + '\nprint "fresh"'
def _p_timer_word(pg): pg['comps'].append({'n': 'tmw', 'i': 95, 't': 'timer', 'g': 'l', 'a': {'tim': 400, 'en': 1}, 'ev': {'t': 'print "SwitchesView1"'}})
def _p_printh(pg): pg['ev']['preinitialize'] = pg['ev'].get('preinitialize', '') + '\nprinth a7 00 00 00'
PAGE_SELFTEST = [   # (the ninth review's list) changes to a copy of page 9 that the scan must see
    ('a timer that is on prints OK\'s code', _p_timer_on), ('a timer that is OFF in the file, switched on by the page\'s script', _p_timer_by_script),
    ('a part clicked as the page comes up clicks another, which prints', _p_click_two), ('a part clicked as the page comes up prints', _p_click_one),
    ('a print on the same line as its if', _p_print_behind_if), ('a word printed as the page comes up that begins with f', _p_word_f),
    ('a timer prints a page\'s word', _p_timer_word), ('printh as the page comes up', _p_printh),
]
def table_entry(name, n):
    t = MAIN_CPP[MAIN_CPP.index('void (*%s[' % name):]; t = t[t.index('{') + 1:t.index('};')]
    t = re.sub(r'/\*.*?\*/', '', re.sub(r'//[^\n]*', '', t), flags=re.S)
    return [x.strip() for x in t.split(',') if x.strip()][n]

PRE = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <cstdarg>
#include <string>
#include <map>
#include <set>
#include <deque>
#include <vector>
#include <algorithm>
#include <sys/types.h>
#define FLASHMEM
#define FASTRUN
#define DMAMEM
#define CRUMB(x)
#define MAXTEXTIN 1024 * 4
#define MAXBUFFERSIZE 1024 * 6
#define SCREENCHANGEWAIT %(SCREENCHANGEWAIT)s
#define FRONTVIEW %(FRONTVIEW)s
#define RXSETUPVIEW1 %(RXSETUPVIEW1)s
#define RXSETUPVIEW %(RXSETUPVIEW)s
#define ONE_SWITCH_VIEW %(ONE_SWITCH_VIEW)s
#define MODELSVIEW %(MODELSVIEW)s
#define HELP_VIEW %(HELP_VIEW)s
#define LOGVIEW %(LOGVIEW)s
#define MAXMODELNUMBER %(MAXMODELNUMBER)s
#define CALIBRATEVIEW %(CALIBRATEVIEW)s
#define NORMAL %(NORMAL)s
#define CALIBRATELIMITS %(CALIBRATELIMITS)s
#define CENTRESTICKS %(CENTRESTICKS)s
#define WHAHWHAHMSG %(WHAHWHAHMSG)s
#define MINMICROS %(MINMICROS)s
#define MAXMICROS %(MAXMICROS)s
static int checks = 0, fails = 0;
static bool show = false;
#define CHECK(c) do { ++checks; if (!(c)) { ++fails; fprintf(stderr, "FAIL line %%d: %%s\n", __LINE__, #c); } } while (0)
static void say(const char *f, ...) { if (!show) return; va_list a; va_start(a, f); vprintf(f, a); va_end(a); }

// ---- the clock: every look at it takes a little time, a wait takes what it says
static uint64_t nowUs = 5000000;
static uint64_t nowUs_peek() { return nowUs; }
static uint32_t micros() { nowUs += 4; return (uint32_t) nowUs; }
static uint32_t millis() { nowUs += 4; return (uint32_t) (nowUs / 1000); }
static void delayMicroseconds(int n) { nowUs += n; }
// THE WATCHDOG, as the Teensy has it (Utilities.h KickTheDog: fed when the last feed is a second old; unfed for 2.5 s, the Teensy restarts). The
// longest time it went unfed while watched is kept (the eighth review: a loop that fed it nowhere).
static uint64_t lastFeedUs = 0, maxUnfedUs = 0; static long dogKicks = 0; static bool dogWatch = false;
static uint64_t nowUs_peek();
static void dogLook() { const uint64_t n = nowUs_peek(); if (dogWatch && lastFeedUs && n - lastFeedUs > maxUnfedUs) maxUnfedUs = n - lastFeedUs; }
static void KickTheDog() { ++dogKicks; const uint64_t n = nowUs_peek(); if (!lastFeedUs) { lastFeedUs = n; return; } if (n - lastFeedUs >= 1000000ull) { dogLook(); lastFeedUs = n; } }
static void LinkStrayFrame() {}
uint8_t ModalWaits = 0; bool InsideDelayWithDog = false;                      // (Utilities.h: a question waits; DelayWithDog is flying the model)
static int soundsPlayed = 0; static void PlaySound(uint16_t) { ++soundsPlayed; }
uint32_t BoxesLost = 0, BoxesLostAtWork = 0; char BoxLostName[24] = { 0 }; bool BoxLostNoNumber = false;   // (1Definitions.h: NO ANSWER IS NOT A NUMBER)
bool QuestionClosedItself = false, QuestionOvertaken = false;                 // (Utilities.h: the last question was closed by this board; ... by another page over it)
static long constrain(long v, long lo, long hi) { return v < lo ? lo : v > hi ? hi : v; }
static long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }
static int radioPasses = 0;
static void (*waitHook)() = nullptr;                                          // what a wait does besides waiting, once (the real one flies the model, and looks at the power button)
// THE MODEL IS FLOWN from every pass of the main loop and from every DelayWithDog (the sticks read, a packet sent). The longest time
// WITHOUT that, while it is watched, is kept - the seventh review found two seconds of it in a wait for the screen - and so is the
// longest single pass of the loop: the switches are read once a pass.
static uint64_t lastRadioUs = 0, maxRadioGapUs = 0, maxPassUs = 0; static bool gapWatch = false;
static void radioService() { if (gapWatch && lastRadioUs && nowUs - lastRadioUs > maxRadioGapUs) maxRadioGapUs = nowUs - lastRadioUs; lastRadioUs = nowUs; }
// (The thirteenth review, reviewer A's finding 2: THE LONGEST SILENCE WAS BROUGHT UP TO DATE ONLY WHEN THE RADIO WAS NEXT SERVED - a routine that stopped
//  flying the model and never served it again before it returned read "0.1 ms" with 545 ms standing open: a wait made a plain delay passed every test.
//  What stands open counts, as the dog's watch has it (dogLook): the checks read the silence through radioGapUs() - never the variable itself; this
//  file's main() looks through every scene for a read of it.)
static void radioLook() { if (gapWatch && lastRadioUs && nowUs - lastRadioUs > maxRadioGapUs) maxRadioGapUs = nowUs - lastRadioUs; }
static uint64_t radioGapUs() { radioLook(); return maxRadioGapUs; }
static void (*flyHook)() = nullptr;                                           // what flying the model writes to the screen from inside a wait (its telemetry, to the page showing)
static long nestedWaits = 0;
static void DelayWithDog(uint32_t ms)
{
    if (InsideDelayWithDog) { ++nestedWaits; return; }                         // (the real one's guard: a wait inside a wait goes straight back - and waits for nothing)
    InsideDelayWithDog = true; KickTheDog(); radioService(); if (flyHook) flyHook();
    { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs + 1000 <= until) { nowUs += 1000; KickTheDog(); } nowUs = until; }   // (the real one feeds the dog all through its wait)
    radioPasses += ms; lastRadioUs = nowUs; KickTheDog();
    if (waitHook) { void (*h)() = waitHook; waitHook = nullptr; h(); }
    InsideDelayWithDog = false;
}

// ---- THE PRETEND SCREEN, by the real one's rules (the screen's src/main.cpp): commands are handled in the order they came,
// a page is loaded when its command is handled (nothing else happens meanwhile), "get" answers at once - a box the showing
// page has not got: what was last written to that name on this page, else 0 or "" -, a name=number is a system variable,
// and what a page's event prints goes out as one framed burst (7E 7E, the length, the bytes).
struct Box { bool text; long val; std::string txt; };
struct Page { std::map<std::string, Box> boxes; std::map<std::string, std::vector<uint8_t>> buttons; std::set<std::string> raw, numberBoxes; std::vector<uint8_t> loadPrint, timerPrint; uint32_t timerUs = 0; int id = 0; };
static void (*tapScript)(const char *button) = nullptr;   // (the twelfth review) A PAGE'S OWN SCRIPT, run at the moment of the touch IN THE SCREEN'S OWN TIME - before its word goes out,
static void (*loadScript)(const char *page) = nullptr;    //  in its place among the main board's commands (a scene sets it: the Sub-trim page's "+", "-", Zero, its channel taps); and as a page comes up
static bool (*cmdScript)(const char *cmd) = nullptr;      //  ... and every command of the main board's as the screen handles it (true: it never landed - a write lost on the way)
static double g_gapProb = 0.0;   // (the tenth review, reviewer A's: A PAUSE INSIDE ONE WRITE of the screen's, at this rate - set by a scene before its fresh screen; 0: none)
static uint32_t g_screens = 0;   // (with pauses on: every fresh screen has dice of its own)
struct Screen
{
    std::map<std::string, Page> pages; std::string page = "FrontView";
    std::map<std::string, long> sys, keptInt; std::map<std::string, std::string> keptTxt;
    std::string in; std::deque<std::pair<uint64_t, std::string>> cmds;        // main board -> screen: (when it can be handled, the command)
    std::deque<std::pair<uint64_t, uint8_t>> out;                              // screen -> main board: (when it is on the wire, the byte)
    std::multimap<uint64_t, std::string> taps;                                 // (when, the button's name): a tap finds the button on the page then showing
    uint64_t busyUntil = 0, at = 0, cmdHoldUntil = 0, nextTickAt = UINT64_MAX;
    uint32_t roundUs = 0;                                                      // after a page is up, a round of the screen's loop (touch, timers) before its next command is read
    std::set<std::string> files, mute;                                         // the pictures on its card; boxes it gives no answer for (a reply lost)
    std::vector<std::string> visSaid;                                          // every "vis" it was told, with the page that was up
    std::set<std::string> sysMute;                                             // ... and system variables it gives no answer for (the session's number, say: its answer lost each time)
    int ticks = 0;
    long tapAfterPageUs = -1; std::string tapAfterPageButton;                  // one tap, so long after the next page command leaves the main board
    long tap2AfterPageUs = -1; std::string tap2AfterPageButton;
    uint32_t latencyUs = 1500, loadUs = 90000;                                 // a loop pass before a command is read; a page's load
    bool frames = true, canFrame = true, knowsSysGet = true, knowsSendme = true, tapInLoadFallsThrough = false;
    int muteSendme = 0;                                                        // so many "sendme" go unanswered (an answer lost)
    bool deaf = false;                                                         // it takes nothing in (a scene then says by hand what "it" says)
    // ITS OWN RESTART, as the real screen makes it (its src/main.cpp setup()): the port open early, with a big buffer - what is
    // said to it from then on is KEPT and handled when its loop begins; its power-on bytes; the page it was on put back from
    // the card (what that page prints as it comes up goes out UNFRAMED: nothing has told this start to frame); 300 ms; the bare
    // word "FrontView rst=N" (not after a power-on); after a watchdog or a panic its record, "LDRCLOG ...", in parts of 280
    // characters, the first 30 ms after the word and the rest 300 ms apart; and only then does it answer anything.
    int restartReason = 5;                                                     // (1: the power itself came on - no page put back, no word)
    bool restartPowerOnBytes = true, restartSaysWord = true, restartKeeps = true; std::string bootRecord;
    uint32_t aliveLateUs = 0;                                                  // its loop begins so much later than a moment after its last word
    // (the seventh review) WHAT THE CHIP SAYS BEFORE ITS PROGRAM DOES - its panic handler's lines and "Rebooting..." at the wire's own
    // speed, then its ROM's text at 115200 baud, which this wire reads as 80 80 00 80 ... - (when after the restart, the byte); and
    // how long its start takes: 1.2 s on the bench, 18 s after an update that copies its files
    std::vector<std::pair<uint64_t, uint8_t>> prelude; uint64_t powerOnUs = 1800000, wordAfterUs = 700000;
    std::string keyboardOver;                                                  // its keyboard page is up, over this page (opened by a touch on a number box - by the screen itself)
    std::map<std::string, Page> pages0;                                        // the pages as the card has them (a restart puts them back)
    uint64_t deadUntil = 0; int restarts = 0, keyboards = 0, offPageAnswers = 0;
    int loads = 0, tapsOnNothing = 0, gets = 0, oddCommands = 0; std::vector<std::string> log, events;
    std::string lastGetPage;                       // (the page the last command, a box's get, was answered on: a screen from 1.11.198 on says THAT for a "which page?" right behind it)
    bool lastGetUnderKb = false; int known7 = 0;   // (the tenth review, reviewer A's: a box asked for while the screen's keyboard was up, and its "which page?" answered when the
                                                   //  keyboard had gone - the 0 said under the keyboard is then taken. Known, and the screen's to cure (1.11.198): counted here)
    long gapsMade = 0;
    // THE REAL SCREEN'S PORT (the ninth review, 15 Nov 2026 - reviewer A's model, from the screen's src/main.cpp and last_moments.h and the
    // UART driver it is built with; off unless realUart):
    //  - one FIFO of 128 bytes, a byte leaves every 10.85 us;
    //  - the loop's core writes every reply, burst and word with ONE write, under the port's lock until every byte is in the FIFO: never
    //    cut by the other core - and each command takes that core a little time (a text or a value drawn: more);
    //  - the OTHER core's line when the loop has stood still (lmShout), as screens up to 1.11.197 say it: "what is left" pushed again and
    //    again - what fits goes in (the lock held for that piece only); nothing fitted: 300 us, and again. So 128 bytes at once, then some
    //    27 every 300 us - and BETWEEN two pieces the loop's core can write (its bytes then stand INSIDE the line), or the shouting core
    //    can be held (a pause inside it). The line has no end, and its last words are the last command handled.
    //    From 1.11.198 (shoutForm 198): ONE push of 127 bytes at most, the last a newline; what does not fit is not said.
    bool realUart = false; int shoutForm = 197; uint64_t wireFreeAt = 0; uint32_t upMs = 81234;
    std::multimap<uint64_t, std::vector<uint8_t>> later;                       // what the loop's core will write, and when (a page's own print at its load's end; a scene's own bytes)
    std::string shoutLeft, lastShout, lastCmd; uint64_t shoutNextAt = 0, shoutHoldUs = 0, lastCmdAt = 0; bool shoutFirstDone = false;
    int shoutPieces = 0, shoutCuts = 0, realShouts = 0, shoutsCutShort = 0;
    uint32_t costSeed = g_gapProb > 0 ? 7 + (++g_screens) * 2654435761u : 7; uint32_t costRnd(uint32_t n) { costSeed = costSeed * 1664525u + 1013904223u; return n ? (costSeed >> 8) %% n : 0; }
    uint64_t costOf(const std::string &c) { if (c.rfind("get ", 0) == 0 || c == "sendme") return 40 + costRnd(80); if (c.find(".txt=") != std::string::npos || c.find(".val=") != std::string::npos) return 150 + costRnd(700); return 20 + costRnd(40); }
    size_t fifoLevel(uint64_t t) const { return wireFreeAt > t ? (size_t) ((wireFreeAt - t + 10) / 11) : 0; }
    void fifoPush(uint64_t t, const uint8_t *p, size_t n) { for (size_t i = 0; i < n; ++i) { const uint64_t s = std::max(t, wireFreeAt); wireFreeAt = s + 11; out.push_back({ wireFreeAt, p[i] }); } }
    void shoutPiece()   // the other core, at shoutNextAt
    {
        const uint64_t t = shoutNextAt;
        const size_t level = fifoLevel(t), room = level >= 128 ? 0 : 128 - level, n = std::min(room, shoutLeft.size());
        if (shoutForm >= 198)
        {   // one push: what does not fit is not said
            if (n < shoutLeft.size()) ++shoutsCutShort;
            if (n) { fifoPush(t, (const uint8_t *) shoutLeft.data(), n); ++shoutPieces; }
            shoutLeft.clear(); return;
        }
        if (n)
        {
            fifoPush(t, (const uint8_t *) shoutLeft.data(), n); shoutLeft.erase(0, n); ++shoutPieces; shoutNextAt = t + 4;
            if (!shoutFirstDone) { shoutFirstDone = true; shoutNextAt += shoutHoldUs; }   // (that core held after its first piece: another task of its own, the loop's flash write)
        }
        else shoutNextAt = t + 300;
    }
    void loopWrite(uint64_t t, const std::vector<uint8_t> &b)   // the loop's core: one write, under the lock until all of it is in the FIFO
    {
        const bool inside = !shoutLeft.empty() && shoutFirstDone;
        size_t done = 0; uint64_t now = t;
        // (the tenth review, reviewer A's: A PAUSE INSIDE ONE WRITE - the port's refill held back by a busy moment - at a chosen rate: the bytes behind it, and all that follows, come later)
        size_t gapAt = 0; uint64_t gapUs = 0;
        if (g_gapProb > 0 && b.size() >= 2 && (double) costRnd(1000000) / 1e6 < g_gapProb) { gapAt = 1 + costRnd((uint32_t) b.size() - 1); const uint32_t k = costRnd(4); gapUs = k == 0 ? 150 + costRnd(300) : k == 1 ? 500 + costRnd(2500) : k == 2 ? 3000 + costRnd(27000) : 250 + costRnd(1000); ++gapsMade; }
        while (done < b.size())
        {
            const size_t level = fifoLevel(now), room = level >= 128 ? 0 : 128 - level; size_t n = std::min(room, b.size() - done);
            if (gapAt && done < gapAt && done + n > gapAt) n = gapAt - done;
            if (n) { fifoPush(now, b.data() + done, n); done += n; }
            if (gapAt && done == gapAt) { gapAt = 0; wireFreeAt = std::max(wireFreeAt, now) + gapUs; now = wireFreeAt; continue; }
            if (done < b.size()) now = wireFreeAt > 9 * 11 ? std::max(now + 1, wireFreeAt - 9 * 11) : now + 1;   // (the FIFO under ten bytes: its interrupt wakes the writer)
        }
        if (inside) ++shoutCuts;
        if (!shoutLeft.empty() && shoutNextAt < now) shoutNextAt = now;        // (the other core waited for the lock meanwhile)
    }
    void pumpWire(uint64_t upTo)   // what is due on the port by then, in the order of its time
    {
        while (true)
        {
            const uint64_t tl = later.empty() ? UINT64_MAX : later.begin()->first, ts = shoutLeft.empty() ? UINT64_MAX : shoutNextAt;
            if (std::min(tl, ts) == UINT64_MAX || std::min(tl, ts) > upTo) return;
            if (ts <= tl) shoutPiece();
            else { const std::vector<uint8_t> b = later.begin()->second; later.erase(later.begin()); loopWrite(tl, b); }
        }
    }
    void shoutBegin(uint64_t when, const std::string &text, uint64_t holdUs) { shoutLeft = text; shoutNextAt = when; shoutHoldUs = holdUs; shoutFirstDone = false; ++realShouts; }
    std::string shoutText(uint32_t goneMs, uint64_t whenUs, const char *task = nullptr, const char *part = nullptr, const char *busy = nullptr)   // the line, as the screen's lmWatch puts it together
    {
        static const char *const tasks[] = { "loopTask", "loopTask", "loopTask", "loopTask", "loopTask", "loopTask", "IDLE1", "IDLE1" };
        static const char *const parts[] = { "-", "-", "-", "-", "web", "quiet", "tick", "dot", "wauto", "joined", "weak", "time" };
        static const char *const busys[] = { "serial", "handle", "handle", "wifi", "wifi", "touch", "prefs", "sd", "sd", "present", "draw", "pics", "flight", "timers", "audio", "link", "bg" };
        char cmd[32]; size_t k = 0; for (; k < 31 && k < lastCmd.size(); ++k) { const char ch = lastCmd[k]; cmd[k] = (ch >= 32 && ch < 127) ? ch : '.'; } cmd[k] = 0;
        if (!task) task = tasks[costRnd(8)]; if (!part) part = parts[costRnd(12)]; if (!busy) busy = busys[costRnd(17)];
        const unsigned long ago = (unsigned long) ((whenUs > lastCmdAt ? whenUs - lastCmdAt : 0) / 1000);
        char line[260];
        if (shoutForm >= 198)
        {
            int n = snprintf(line, 127, "LDRCLOG core 1 (the loop's) silent for %%lu ms: task %%.15s, part %%.15s, at %%s, cmd %%lu ms ago: %%.31s", (unsigned long) goneMs, task, part, busy, ago, cmd);
            if (n > 126) n = 126;
            line[n] = '\n'; line[n + 1] = 0;
        }
        else snprintf(line, 240, "LDRCLOG core 1 (the loop's) silent for %%lu ms at %%lu ms: task '%%.15s' on it, part '%%.15s', loop at '%%s', last command %%lu ms ago: %%s", (unsigned long) goneMs, (unsigned long) upMs, task, part, busy, ago, cmd);
        return line;
    }
    void emit(uint64_t t, const std::vector<uint8_t> &b)
    {
        if (!realUart) { for (size_t i = 0; i < b.size(); ++i) out.push_back({ t + 11 * (i + 1), b[i] }); return; }
        if (t > at) { later.insert({ t, b }); return; }                        // (said later: it goes into the FIFO when its time has come)
        pumpWire(t); loopWrite(t, b);
    }
    // ITS LOOP STANDS STILL for a while (its WiFi, its card: 606 ms was measured, and a card that does not answer takes seconds): nothing is
    // read, nothing answered - every command waits its turn and is answered, in order, when the loop comes round again. And a 16 MB
    // screen's OTHER core says so, bare and with no end, a fifth of a second into the silence (its last_moments.h lmShout). (The
    // eighth review: the pretend screen did neither - an answer later than its wait, and a word in front of it, were never met.)
    // (the ninth review: with the real port - realUart - the line is the real one too: 200 to 250 ms into the silence, should the loop still be
    //  silent then; its words those of the last command handled; in pieces, or - shoutForm 198 - in one. wakeRound: the rest of the loop's pass
    //  before its serial job, when the silence was in another job - what a finger did meanwhile is printed BEFORE the commands are read. holdUs:
    //  the shouting core held after its first piece. core0Line: both cores stood still (a flash operation) - the loop says so itself, and that
    //  line stands directly in front of its answers.)
    int shouts = 0; uint64_t loadShoutHoldUs = 0; bool autoLoadShout = true;
    void stall(uint64_t when, uint32_t ms, bool shout, uint32_t wakeRound = 0, uint64_t holdUs = 0, bool core0Line = false)
    {
        busyUntil = std::max(busyUntil, when + (uint64_t) ms * 1000); cmdHoldUntil = std::max(cmdHoldUntil, busyUntil + wakeRound);
        if (!realUart)
        {
            if (shout && ms >= 200)
            {
                static const char *const S = "LDRCLOG core 1 (the loop's) silent for 213 ms at 81234 ms: task 'loopTask' on it, part 'web', loop at 'wifi', last command 310 ms ago: Progress.val=5";
                emit(when + 215000, std::vector<uint8_t>(S, S + strlen(S))); ++shouts;
            }
            return;
        }
        if (shout)
        {
            const uint32_t after = 200000 + costRnd(50000);
            if (after < (uint64_t) ms * 1000 + wakeRound) { lastShout = shoutText(after / 1000, when + after); shoutBegin(when + after, lastShout, holdUs); ++shouts; }
        }
        if (core0Line)
        {
            char b[160]; snprintf(b, sizeof b, "LDRCLOG core 0 silent for %%u ms at %%lu ms: task 'wifi' on it (the loop goes on)%%s", (unsigned) ms, (unsigned long) upMs + ms, shoutForm >= 198 ? "\n" : "");
            later.insert({ cmdHoldUntil, std::vector<uint8_t>(b, b + strlen(b)) });
        }
    }
    void burst(uint64_t t, const std::vector<uint8_t> &payload)
    {
        std::vector<uint8_t> b;
        if (frames) { b = { 0x7E, 0x7E, (uint8_t) (payload.size() & 0xFF), (uint8_t) (payload.size() >> 8) }; }
        b.insert(b.end(), payload.begin(), payload.end()); emit(t, b);
    }
    void handle(uint64_t t, const std::string &c)
    {
        if (deaf) return;
        if (cmdScript && cmdScript(c.c_str())) return;
        lastCmd = c; lastCmdAt = t;
        const std::string getPg = lastGetPage; lastGetPage.clear();              // (a screen from 1.11.198 on: the page the box just asked for was answered on - for the very next command only)
        if (c.rfind("page ", 0) == 0)
        {
            const std::string p = c.substr(5);
            if (!pages.count(p)) { ++oddCommands; return; }
            keyboardOver.clear();                                              // (a page command of the main board's takes the keyboard away with the page it was over)
            page = p; ++loads; busyUntil = t + loadUs; cmdHoldUntil = busyUntil + roundUs; log.push_back("page " + p);
            if (loadScript) loadScript(p.c_str());
            if (realUart && autoLoadShout && loadUs >= 200000)
            {   // (a page that is a fifth of a second and more in coming up: the other core says the loop is silent - "... last command 2xx ms ago: page <name>")
                const uint32_t after = 200000 + costRnd(50000);
                if (after < loadUs) { lastShout = shoutText(after / 1000, t + after, costRnd(5) ? "loopTask" : "IDLE1", "-", "handle"); shoutBegin(t + after, lastShout, loadShoutHoldUs); ++shouts; }
            }
            nextTickAt = pages[p].timerUs ? busyUntil : UINT64_MAX;            // (a page's timer ticks at once when the page is up, then at its pace: the screen's lastTick is 0 at a load)
            { char b[120]; snprintf(b, sizeof b, "%%8.1f ms  (screen) page %%s, loaded at %%.1f", (double) (t %% 100000000ull) / 1000.0, p.c_str(), (double) (busyUntil %% 100000000ull) / 1000.0); events.push_back(b); }
            if (!pages[p].loadPrint.empty()) burst(busyUntil, pages[p].loadPrint);   // (a page's own print as it comes up: ModelsView's, GovView's timer)
            return;
        }
        if (c == "sendme")
        {   // the number of the page it is showing - a screen from 1.11.198 on: right behind a box's get, the page THAT was answered on (its keyboard, though it has closed since)
            const std::string says = (shoutForm >= 198 && !getPg.empty()) ? getPg : page;
            if (lastGetUnderKb && keyboardOver.empty() && says == page) ++known7;
            lastGetUnderKb = false; if (muteSendme > 0) { --muteSendme; return; } if (knowsSendme) emit(t, { 0x66, (uint8_t) pages[says].id, 0xFF, 0xFF, 0xFF }); return;
        }
        if (c.rfind("get ", 0) == 0)
        {
            ++gets;
            const std::string ref = c.substr(4); const size_t dot = ref.rfind('.');
            if (dot == std::string::npos)
            {   // a system variable
                if (!knowsSysGet) { ++oddCommands; return; }
                if (sysMute.count(ref)) return;
                const long v = sys.count(ref) ? sys[ref] : 0;
                { char b[120]; snprintf(b, sizeof b, "%%8.1f ms  (screen) marker %%ld said", (double) (t %% 100000000ull) / 1000.0, v & 0xFFFF); events.push_back(b); }
                emit(t, { 'q', (uint8_t) v, (uint8_t) (v >> 8), (uint8_t) (v >> 16), (uint8_t) (v >> 24), 0xFF, 0xFF, 0xFF }); return;
            }
            const std::string name = ref.substr(0, dot), attr = ref.substr(dot + 1); Page &pg = pages[page];
            lastGetUnderKb = !keyboardOver.empty(); lastGetPage = page;
            if (mute.count(name)) return;
            const bool has = pg.boxes.count(name) != 0;
            if (!has) ++offPageAnswers;                                        // (0 or "" for a box the showing page has not got: what the main board must never take for the box's value)
            if (attr == "txt")
            {
                std::string s = has ? pg.boxes[name].txt : keptTxt.count(page + "." + name) ? keptTxt[page + "." + name] : "";
                std::vector<uint8_t> f; f.push_back('p'); f.insert(f.end(), s.begin(), s.end()); f.insert(f.end(), 3, 0xFF); emit(t, f); return;
            }
            const long v = has ? pg.boxes[name].val : keptInt.count(page + "." + name) ? keptInt[page + "." + name] : 0;
            emit(t, { 'q', (uint8_t) v, (uint8_t) (v >> 8), (uint8_t) (v >> 16), (uint8_t) (v >> 24), 0xFF, 0xFF, 0xFF }); return;
        }
        if (c.rfind("vis ", 0) == 0) { visSaid.push_back(page + ": " + c); return; }   // (kept: which page was up when a part was hidden or shown)
        if (c.rfind("click ", 0) == 0 || c.rfind("play ", 0) == 0) return;
        if (c.rfind("findfile \"", 0) == 0)
        {   // findfile "sd0/images/Name.jpg",sys0
            const size_t q2 = c.find('"', 10), comma = c.find(',', q2);
            if (q2 == std::string::npos || comma == std::string::npos) { ++oddCommands; return; }
            sys[c.substr(comma + 1)] = files.count(c.substr(10, q2 - 10)) ? 1 : 0; return;
        }
        if (c == "ldrcframe=1") { if (!canFrame) return; frames = true; burst(t, { 0, 0, 0, 0 }); return; }   // (an older screen takes it for a variable and frames nothing)
        const size_t eq = c.find('='), dot = c.rfind('.', eq);
        if (eq == std::string::npos) { ++oddCommands; return; }
        if (dot == std::string::npos) { sys[c.substr(0, eq)] = atol(c.c_str() + eq + 1); return; }
        const std::string name = c.substr(0, dot), attr = c.substr(dot + 1, eq - dot - 1); std::string v = c.substr(eq + 1);
        Page &pg = pages[page];
        if (attr == "txt")
        {
            if (v.size() >= 2 && v.front() == '"' && v.back() == '"') v = v.substr(1, v.size() - 2);
            keptTxt[page + "." + name] = v; if (pg.boxes.count(name)) pg.boxes[name].txt = v;
        }
        else { keptInt[page + "." + name] = atol(v.c_str()); if (pg.boxes.count(name) && attr == "val") pg.boxes[name].val = atol(v.c_str()); }
    }
    void restart(uint64_t t)   // its own restart: the pages as the card has them, nothing remembered (see above)
    {
        ++restarts; const std::string was = keyboardOver.empty() ? page : keyboardOver; const bool warm = restartReason != 1;
        later.clear(); shoutLeft.clear(); wireFreeAt = t;                      // (nothing more of what it was about to say; the port fresh)
        for (auto &kv : pages0) { const auto b = pages[kv.first].buttons; pages[kv.first] = kv.second; pages[kv.first].buttons = b; }
        sys.clear(); keptInt.clear(); keptTxt.clear(); cmds.clear(); in.clear(); keyboardOver.clear(); frames = false; page = warm ? was : "NoPage";
        while (!out.empty() && out.back().first > t) out.pop_back();          // (what it was about to say is never said)
        uint64_t at = t + powerOnUs;
        for (auto &g : prelude) if (g.first < powerOnUs) out.push_back({ t + g.first, g.second });
        if (restartPowerOnBytes) emit(at, { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF });
        if (warm && !pages[page].loadPrint.empty()) emit(at + 400000, pages[page].loadPrint);   // (the page put back, as it comes up)
        at += wordAfterUs;
        if (warm && restartSaysWord)
        {
            char w[24]; if (restartReason < 0) snprintf(w, sizeof w, "FrontView"); else snprintf(w, sizeof w, "FrontView rst=%%d", restartReason);   // (an older screen gives no reason)
            emit(at, std::vector<uint8_t>(w, w + strlen(w)));
        }
        for (size_t i = 0; warm && restartSaysWord && i < bootRecord.size(); i += 280)
        {
            at += i ? 300000 : 30000;
            const std::string part = std::string("LDRCLOG ") + (i ? "(cont) " : "") + bootRecord.substr(i, 280);
            emit(at, std::vector<uint8_t>(part.begin(), part.end()));
        }
        const uint64_t alive = at + 80000 + aliveLateUs;
        deadUntil = restartKeeps ? t + 600000 : alive; busyUntil = alive; cmdHoldUntil = alive; nextTickAt = (warm && pages[page].timerUs) ? alive : UINT64_MAX;
        log.push_back("RESTART");
        { char b[160]; snprintf(b, sizeof b, "%%8.1f ms  (screen) RESTARTS on %%s (reason %%d): its power-on bytes at %%.1f, answers from %%.1f", (double) (t %% 100000000ull) / 1000.0, was.c_str(), restartReason, (double) ((t + powerOnUs) %% 100000000ull) / 1000.0, (double) (alive %% 100000000ull) / 1000.0); events.push_back(b); }
    }
    void tap(uint64_t t, const std::string &button)
    {
        if (button == "#restart") { restart(t); return; }
        if (!keyboardOver.empty())
        {   // the keyboard is up: only its own keys are there
            if (button != "kbOK") { ++tapsOnNothing; return; }
            page = keyboardOver; keyboardOver.clear(); busyUntil = t + loadUs; cmdHoldUntil = busyUntil + roundUs;   // back to the page it was over, loaded afresh (its boxes as they were)
            if (loadScript) loadScript(page.c_str());
            nextTickAt = pages[page].timerUs ? busyUntil : UINT64_MAX;
            if (!pages[page].loadPrint.empty()) burst(busyUntil, pages[page].loadPrint);
            log.push_back("keyboard closed");
            { char b[120]; snprintf(b, sizeof b, "%%8.1f ms  (screen) keyboard closed: back on %%s", (double) (t %% 100000000ull) / 1000.0, page.c_str()); events.push_back(b); }
            return;
        }
        if (pages[page].numberBoxes.count(button))
        {   // a number box touched: the screen opens its keyboard page BY ITSELF - no page command of the main board's
            keyboardOver = page; page = "keybdB"; ++keyboards; busyUntil = t + 30000; cmdHoldUntil = busyUntil; nextTickAt = UINT64_MAX;
            log.push_back("keyboard over " + keyboardOver);
            { char b[120]; snprintf(b, sizeof b, "%%8.1f ms  (screen) KEYBOARD up over %%s", (double) (t %% 100000000ull) / 1000.0, keyboardOver.c_str()); events.push_back(b); }
            return;
        }
        Page &pg = pages[page];
        if (!pg.buttons.count(button)) { ++tapsOnNothing; return; }
        log.push_back("tap " + button + " on " + page);
        { char b[120]; snprintf(b, sizeof b, "%%8.1f ms  (screen) tap %%s on %%s", (double) (t %% 100000000ull) / 1000.0, button.c_str(), page.c_str()); events.push_back(b); }
        if (tapScript) tapScript(button.c_str());
        if (pg.raw.count(button)) emit(t, pg.buttons[button]); else burst(t, pg.buttons[button]);   // (raw: the screen's own words and the pipe's lines go out unframed)
    }
    void run(uint64_t now)   // everything due by now, in the order of its time (a load holds the rest back; after it, a round before the next command)
    {
        while (true)
        {
            const uint64_t tc0 = cmds.empty() ? UINT64_MAX : cmds.front().first, tt0 = taps.empty() ? UINT64_MAX : taps.begin()->first;
            const uint64_t tc = tc0 == UINT64_MAX ? UINT64_MAX : std::max(tc0, std::max(busyUntil, cmdHoldUntil));
            const uint64_t tt = tt0 == UINT64_MAX ? UINT64_MAX : std::max(tt0, busyUntil);
            const uint64_t tk = nextTickAt == UINT64_MAX ? UINT64_MAX : std::max(nextTickAt, busyUntil);
            const uint64_t t = std::min(tc, std::min(tt, tk));
            if (t == UINT64_MAX || t > now) { if (realUart) pumpWire(now); return; }
            at = t; if (realUart) pumpWire(t);
            if (tc == t && tc0 <= tt0)                     // (a tap at the very moment of a command: the command first - the serial job, then the touch; but a
            {                                              //  tap that has waited out a load comes before a command the round holds back)
                const std::string c = cmds.front().second; cmds.pop_front(); handle(t, c); if (realUart) cmdHoldUntil = std::max(cmdHoldUntil, t + costOf(c));
            }
            else if (tc == t && tt != t && tk != t) { const std::string c = cmds.front().second; cmds.pop_front(); handle(t, c); if (realUart) cmdHoldUntil = std::max(cmdHoldUntil, t + costOf(c)); }
            else if (tk == t && tt != t) { ++ticks; burst(t, pages[page].timerPrint); nextTickAt = t + pages[page].timerUs; }
            else
            {
                const bool inLoad = tt0 < busyUntil; const std::string b = taps.begin()->second; taps.erase(taps.begin());
                if (!inLoad || tapInLoadFallsThrough) tap(t, b); else ++tapsOnNothing;
            }
        }
    }
} screen;
struct FakeLink
{
    void write(uint8_t b)
    {
        screen.run(nowUs);
        screen.in.push_back((char) b);
        const size_t n = screen.in.size();
        if (nowUs < screen.deadUntil) { screen.in.clear(); nowUs += 11; return; }   // (it is starting again: what is said to it now is lost)
        if (n >= 3 && (uint8_t) screen.in[n - 1] == 0xFF && (uint8_t) screen.in[n - 2] == 0xFF && (uint8_t) screen.in[n - 3] == 0xFF)
        {
            const std::string c = screen.in.substr(0, n - 3);
            screen.cmds.push_back({ nowUs + screen.latencyUs, c }); screen.in.clear();
            if (c.rfind("page ", 0) == 0 && screen.tapAfterPageUs >= 0)
            {
                screen.taps.insert({ nowUs + screen.tapAfterPageUs, screen.tapAfterPageButton }); screen.tapAfterPageUs = -1;
                if (screen.tap2AfterPageUs >= 0) { screen.taps.insert({ nowUs + screen.tap2AfterPageUs, screen.tap2AfterPageButton }); screen.tap2AfterPageUs = -1; }
            }
        }
        nowUs += 11;
    }
    void write(const uint8_t *p, size_t n) { for (size_t i = 0; i < n; ++i) write(p[i]); }
    void print(const char *s) { for (; *s; ++s) write((uint8_t) *s); }
    void flush() {}
    int available() { screen.run(nowUs); int n = 0; for (auto &e : screen.out) { if (e.first > nowUs) break; ++n; } return n; }
    int read() { if (!available()) return -1; const uint8_t b = screen.out.front().second; screen.out.pop_front(); return b; }
    int peek() { if (!available()) return -1; return screen.out.front().second; }
} NEXTION;

// ---- the main board's own things the lifted code uses
char TextIn[MAXTEXTIN + 2];
uint32_t NextionReplyWaitMs = 100;
#define NEXTION_GET_WAIT_MS 2000
bool NextionGetPending = false;
bool NextionTextMissed = false; char NextionMissedBox[24] = ""; bool NextionSettledOk = false, NextionMissedNoNumber = false;
bool ValueSent = false;
uint8_t CurrentView = FRONTVIEW;
static std::vector<std::string> ghosts, lateReplies, logLines;
static void LogGhostFrame(const char *why, const uint8_t *f, uint16_t n) { char b[200]; int p = snprintf(b, sizeof b, "%%s:", why); for (uint16_t i = 0; i < n && i < 8; ++i) p += snprintf(b + p, sizeof b - p, " %%02X", f[i]); ghosts.push_back(b); }
static void NoteLateReply(const char *cmd, uint32_t ms, bool got) { if (got && ms <= 400) return; char b[120]; snprintf(b, sizeof b, "%%s %%s after %%u ms", got ? "late" : "MISSING", cmd, (unsigned) ms); lateReplies.push_back(b); }
static void LogText(char *t, uint16_t, bool) { logLines.push_back(t); }
static void DeferLogText(const char *t, bool) { logLines.push_back(std::string("(kept for later) ") + t); }
static void KeepScreenNote(const char *t, bool) { DeferLogText(t, true); }      // (LogFiles.h: within a budget - the real one runs in the namespace "kept", below)
static void KeepScreenReason(const char *t, const char *more) { KeepScreenNote(t, true); if (more) KeepScreenNote(more, true); }   // (... its pair rule too)
static bool mayFly = false;
static bool RadiosMustBeOff() { return mayFly; }
#define RF_NO_ANSWER_SAVING "No answer - PART MAY BE WRITTEN, NOT STORED: try again, or switch the model off and on"   // (RF_SaveNow.h, the seventeenth review: its own words are held by dev/test_wholepage/scene_read_fails)
static inline const char *RfNoAnswerWords(bool savingStep) { return savingStep ? RF_NO_ANSWER_SAVING : "No answer"; }
static bool rfJobRuns = false; bool RfPageJobRuns() { return rfJobRuns; } bool RfPageWatchRuns() { return false; }   // (main.cpp, B211: the Rotorflight page showing reads or saves - Help and the screen saver wait; dev/test_pagejob runs the real one)
static bool LogMustWait() { return mayFly; }   // (FlightGuard.h: ... or, with no safety switch, a model connected at all - dev/test_wholepage/scene_read_fails runs the real one)
static int stale = 0, noMarks = 0; static std::vector<std::string> staleCodes;
static void tell(const char *f, ...);
static int wordsLetGo = 0; static void (*subTrimLetGo)(const uint8_t *, uint16_t, bool) = nullptr;   // (Trims.h's own routine, in the scenes that have the Sub-trim page)
static void SubTrimWordLetGo(const uint8_t *f, uint16_t n, bool framed) { ++wordsLetGo; if (subTrimLetGo) subTrimLetGo(f, n, framed); }   // (the fifteenth review: Nextion.h tells Trims.h of every frame it lets go unserved)
static void NoteStalePress(const uint8_t *f, uint16_t n)
{
    char b[24];
    if (n && f[0] >= 0x20 && f[0] < 0x7F) { uint16_t i = 0; for (; i < n && i < 20 && f[i] >= 0x20 && f[i] < 0x7F; ++i) b[i] = (char) f[i]; b[i] = 0; }   // a word a page's button printed
    else { if (n < 4 || !(f[0] >= 0x80 || f[1] || f[2])) return; snprintf(b, sizeof b, "%%02X%%02X%%02X%%02X", f[0], f[1], f[2], f[3]); }
    ++stale; staleCodes.push_back(b); tell("NOT obeyed %%s", b);
}
static void NoteNoScreenMark() { ++noMarks; tell("the marker never came"); }
static int textDoubted = 0; static void NoteTextDoubted(const char *cmd) { ++textDoubted; tell("a text answer behind a word with no end was not believed: '%%s'", cmd); }
static int underGet = 0, offPage = 0, pageUnsaid = 0;
static void NotePageChangedUnderGet(const char *cmd) { ++underGet; tell("the page was changed under '%%s'", cmd); }
static void NoteBoxOffPage(const char *cmd, bool unsaid) { if (unsaid) { ++pageUnsaid; tell("the screen did not say its page at '%%s'", cmd); } else { ++offPage; tell("the screen showed another page at '%%s'", cmd); } }
uint32_t GetSysValue(const char *name);
void SendCommand(char *tbox);
void StashPendingEventBytes();
void AskPageMarker(bool pageUp);
void StashFrame(const uint8_t *f, uint16_t n, bool withEnd = false);
'''

MODEL = r'''
// ---- the model's memory, as MenuOptions.h's two functions use it
bool CopyTrimsToAll = true, UseMotorKill = true, TimerDownwards = true, SixBanks = true;
uint8_t TrimMultiplier = 5, MotorChannelZero = 45, MotorChannel = 4, PreviousBank = 0, ModelNumber = 3;
float StopFlyingVoltsPerCell = 3.5f; int Max_Safe_Amps = 120; uint16_t SFV = 350, TimerStartTime = 360; short int RxVoltageCorrection = 3;
static void SixBanksSet(bool on) { SixBanks = on; }
static void GetBank() {}
struct Saved { bool kill, trims, down, six; uint8_t step, motorZero, motorCh; float volts; int amps; uint16_t timer; short corr; uint8_t view; };
static std::vector<Saved> saves;
static void SaveOneModel(uint8_t) { saves.push_back({ UseMotorKill, CopyTrimsToAll, TimerDownwards, SixBanks, TrimMultiplier, MotorChannelZero, MotorChannel, StopFlyingVoltsPerCell, Max_Safe_Amps, TimerStartTime, RxVoltageCorrection, CurrentView }); }
static void UpdateModelsNameEveryWhere() {}
static void SendInitialSetupParams() {}
void SendText(char *tbox, char *NewWord);
static int picMissing = 9, picThere = 9; static bool frontAsksPicture = false;
static void GotoFrontView()   // (the real one draws much more: what matters here is the page command, and a few of its writes)
{
    SendCommand((char *) "page FrontView");
    CurrentView = FRONTVIEW;
    if (frontAsksPicture) { picMissing = NextionFileExistsOnSD3("Missing.jpg"); picThere = NextionFileExistsOnSD3("Yak.jpg"); }   // (the real one asks whether the model's picture is on the card: ShowModelImage)
    SendText((char *) "t0", (char *) "Model"); SendText((char *) "Owner", (char *) "Pilot"); SendText((char *) "StillConnected", (char *) "Not connected");
}
// ---- Help (the REAL HelpWordCame of main.cpp and SendHelp of Help.h are lifted behind these)
char TextFileName[40] = ""; uint8_t SavedCurrentView = 0;
static bool RfSaveHoldsBank() { return false; }   // (B211, e101b: main.cpp's Help tap asks it - RF_Verify.h; dev/test_verify runs the real one)
bool HelpTookRead = false, Reading_PIDS_Now = false, Reading_RATES_Now = false, Reading_RATES_Advanced_Now = false, Reading_PIDS_Advanced_Now = false, Reading_GOV_Now = false, Reading_GOV_Config_Now = false;
static std::vector<std::string> helpOpened; static void LogVIEWNew() { helpOpened.push_back(TextFileName); SendCommand((char *) "page LogView"); CurrentView = LOGVIEW; }   // (the fifteenth review: as LogFilesDisplay.h - LOGVIEW at once; while a help text shows this board believes LOGVIEW, never HELP_VIEW)
// ---- a question box (the REAL GetYesOrNo of Utilities.h is lifted behind these)
char Confirmed[2] = "?"; bool BoundFlag = false, ModelMatched = false;
void GetYesOrNo(uint16_t asked = 0);                                          // (1Definitions.h: asked - the count of the page command that put the question up; 0: the last one sent)
static int questionsClosed = 0, questionsOvertaken = 0, questionsSilent = 0, boxSpins = 0; static void NoteQuestionClosed(uint8_t why) { ++questionsClosed; if (why == 0) ++questionsOvertaken; if (why == 2) ++questionsSilent; }
static int boxesLostTold = 0; static void NoteBoxesLost() { ++boxesLostTold; }   // (LogFiles.h: the pilot is told - a sound, a line)
static void Dispatch();
static void ButtonWasPressed() { Dispatch(); }
void CheckForNextionButtonPress();                                            // (the REAL one, of Utilities.h, is lifted behind the loop's Dispatch)
static void (*powerButtonHook)() = nullptr;                                   // (what the power button does when it is looked at: the front page, while connected)
static void CheckPowerOffButton() { nowUs += 500; if (++boxSpins > 400000) Confirmed[0] = 'T'; if (powerButtonHook) powerButtonHook(); }   // (the clock moves on; a box nobody answers is given up by the test, as 'T')
static void (*sendDataHook)() = nullptr;                                      // (what sending a packet can do from inside a wait: the link found lost)
static void GetNewChannelValues() {} static void FixMotorChannel() {} static void SendData() { radioService(); if (sendDataHook) sendDataHook(); }
// ---- the Models page (the REAL CheckModelName of main.cpp is lifted behind these)
uint16_t FileNumberInView = 0, LastModelLoaded = 0, LastFileInView = 0; char ModelName[30] = "Goblin";
static std::vector<int> modelsRead;
static void ShowFileNumber() {} static void ReadOneModel(uint32_t n) { modelsRead.push_back((int) n); } static void DisplayModelImage() {}
// ---- what a watchdog's record of the screen looks like: up to twelve hundred characters (its last_moments.h, and its setup()'s own head)
static std::string watchdogRecord()
{
    std::string r = "before the restart (rst 5): the loop was at serial, page RXOptionsView; the loop's last pass 81234 ms after start (40211 passes); 12 flash operations, the last ended at 80111 ms (410 us, task 'loopTask'); the longest 2210 us by 'loopTask' during 'prefs'; part '-'; interrupts off for up to 3 ms on core 1 at 80002 ms (part '-', loop at 'serial') and 1 ms on core 0 at 79000 ms; the last commands (ms before the loop's last pass): [990] page FrontView";
    for (int i = 0; i < 36; ++i) { char b[60]; snprintf(b, sizeof b, " [%d] Progress.val=%d", 950 - i * 25, i * 5); r += b; }
    return r.substr(0, 1200);                                                  // (the screen keeps twelve hundred characters of it: five parts)
}
static const std::string rec = watchdogRecord();
// ---- WHAT THE SCREEN'S CHIP SAYS AS IT STARTS AGAIN, before its program says a word (the seventh review): after a watchdog or a panic its
// handler's lines, then "Rebooting..." - bare text at the wire's own speed - and 50 ms on its ROM's text at 115200 baud, which this wire
// (921600) reads as 80 80 00 80 ... (romBytes: made by the Python part, bit by bit)
static std::vector<std::pair<uint64_t, uint8_t>> chipStart(int reason)
{
    std::vector<std::pair<uint64_t, uint8_t>> v; uint64_t at = 300;
    auto text = [&](const char *s) { for (; *s; ++s) { at += 11; v.push_back({ at, (uint8_t) *s }); } };
    if (reason == 4 || reason == 5 || reason == 6)
    {
        text("Guru Meditation Error: Core  1 panic'ed (Interrupt wdt timeout on CPU1). \r\n\r\nCore  1 register dump:\r\nPC      : 0x4200d3a2  PS      : 0x00060035  A0      : 0x82003a20\r\n\r\nBacktrace: 0x4200d39f:0x3fcebf70 0x42003a1d:0x3fcebf90\r\n\r\n\r\n");
        at += 5000;
    }
    if (reason != 1) text("Rebooting...\r\n");
    for (auto &b : romBytes) v.push_back({ 50000 + b.first, b.second });
    return v;
}
// ---- the screen's own restart, as main.cpp answers it (the REAL ScreenHasRestarted is lifted behind these)
bool BankSoundHeld = false; static int warmups = 0; static void ScreenWarmup() { ++warmups; }
uint8_t CurrentMode = NORMAL; static int paramsLoaded = 0, redLeds = 0; static void LoadAllParameters() { ++paramsLoaded; } static void RedLedOn() { ++redLeds; }
static std::vector<std::string> frontReasons, frontBriefs, frontMore;
static void LogFrontPageReason(const char *why, const char *brief, const char *more = nullptr) { frontReasons.push_back(why); frontBriefs.push_back(brief); frontMore.push_back(more ? more : ""); }
// ---- the One switch page's own routine (main.cpp), with what it writes to
#define SWITCH_INPUTS 12
#define SWITCHES_VIEW 53
uint8_t BankSwitch = 1, Autoswitch = 2, SafetySwitch = 3, BuddySwitch = 0, DualRatesSwitch = 4, FrontSwitchUnused = 0, SwitchEditNumber = 3;
uint8_t TopChannelSwitch[SWITCH_INPUTS] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }; bool SwitchReversed[8] = { false, false, true, false, false, false, false, false };
static int txSaves = 0, switchPagesDrawn = 0;
static void SaveTransmitterParameters() { ++txSaves; }
static void UpdateSwitchesView() { ++switchPagesDrawn; }
static void ClearText() { memset(TextIn, 0, 16); }
static bool switchesAsAtFirst() { return BankSwitch == 1 && Autoswitch == 2 && SafetySwitch == 3 && BuddySwitch == 0 && DualRatesSwitch == 4 && SwitchReversed[2] && !SwitchReversed[0] && TopChannelSwitch[0] == 0; }
static bool sameAsAtFirst()
{
    return UseMotorKill && CopyTrimsToAll && TimerDownwards && SixBanks && TrimMultiplier == 5 && MotorChannel == 4 && MotorChannelZero == 45
        && StopFlyingVoltsPerCell > 3.49f && StopFlyingVoltsPerCell < 3.51f && Max_Safe_Amps == 120 && TimerStartTime == 360 && RxVoltageCorrection == 3;
}
'''

MAIN = r'''
// ---- the loop: a press is taken and obeyed as ButtonWasPressed does (genuine? a 24-bit code, a 7-bit code, a word)
static std::vector<int> obeyed; static std::vector<std::string> words;
static void OptionsBoxes();
static void OpenOptions()   // RXOptionsViewStart's part that matters: the page, and the model's values into its boxes
{
    SendCommand((char *) "page RXOptionsView");
    CurrentView = RXSETUPVIEW1;
    OptionsBoxes();
}
static uint32_t readNumber = 0; static char readText[40] = "";
static void LeaveQuick() { SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; }                                    // a page command, and back to the loop
static void OptionsBoxes()   // the model's values into the page's boxes (RXOptionsViewStart's own writes)
{
    SendValue((char *) "c1", CopyTrimsToAll); SendValue((char *) "n3", TrimMultiplier); SendText((char *) "t10", (char *) "3.50");
    SendValue((char *) "n0", 1000); SendValue((char *) "n1", MotorChannel + 1); SendValue((char *) "c0", UseMotorKill); SendValue((char *) "n2", RxVoltageCorrection);
    SendValue((char *) "c2", TimerDownwards); SendValue((char *) "c3", SixBanks ? 1 : 0); SendValue((char *) "n4", TimerStartTime / 60); SendText((char *) "t12", (char *) "120");
}
static void OpenAndRead() { SendCommand((char *) "page RXOptionsView"); CurrentView = RXSETUPVIEW1; readNumber = GetValue((char *) "n4"); OptionsBoxes(); }      // a get straight after the page command (the page file's own value, or the last one written there)
static void OpenAndReadText() { SendCommand((char *) "page RXOptionsView"); CurrentView = RXSETUPVIEW1; GetText((char *) "t10", readText, sizeof(readText)); OptionsBoxes(); }
static void otherWork(uint32_t us) { const bool w = gapWatch; gapWatch = false; nowUs += us; lastRadioUs = nowUs; gapWatch = w; }   // (the test's own invention, not the screen code's doing: not on the radio's meter)
static void BusyAfterPage() { SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; otherWork(3000000); }             // ... and three seconds of other work, the wire unread
static void BusyThenWrite() { SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; otherWork(3000000); SendText((char *) "t0", (char *) "Model"); }   // ... and then a write, which reads the wire in
static void ReadBig() { readNumber = GetValue((char *) "big"); }
static void TwoPages() { SendCommand((char *) "page RXOptionsView"); SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; }   // a page that is left at once (a question's box and back)
static void TextWithPageInIt() { SendText((char *) "t0", (char *) "Go to page 2 of the notes"); }
static void OpenAndAskPicture()   // straight after a page command, the question "is the model's picture on the card?" (Model options after Help; Models after its box)
{
    SendCommand((char *) "page RXOptionsView"); CurrentView = RXSETUPVIEW1;
    picMissing = NextionFileExistsOnSD3("Missing.jpg"); picThere = NextionFileExistsOnSD3("Yak.jpg");
    OptionsBoxes();
}
static void FrontPageUnderIt() { SendCommand((char *) "page FrontView"); CurrentView = FRONTVIEW; }   // (what the power button did from inside a get's wait)
static uint64_t boxUpAtUs = 0, boxAnsweredAtUs = 0; static int boxLooks = 0;
static void BoxInWait()   // a question box put up from inside a wait (the link lost with the motor switch on; the build's age): MsgBox, as Utilities.h has it
{
    SendCommand((char *) "page PopupView"); SendText((char *) "Dialog", (char *) "Lost contact"); boxUpAtUs = nowUs;
    for (boxLooks = 0; boxLooks < 20000; ++boxLooks)
    {   // GetYesOrNo: the loop looks for a press, and obeys it (here: the box's OK, code 1)
        if (GetButtonPress() && TextInIsGenuine() && (uint8_t) TextIn[0] == 0x81) { boxAnsweredAtUs = nowUs; break; }
        nowUs += 500;
    }
    SendCommand((char *) "page RXOptionsView");   // (goback)
}
static int wrongPage = 0;   // codes obeyed while the page this board believes is showing was not their own
static std::vector<std::string> story;   // what was obeyed, when, on which page (and what the screen did): told when a storm's trial goes wrong
static void tell(const char *f, ...) { char b[200]; int p = snprintf(b, sizeof b, "%%8.1f ms  ", (double) (nowUs %% 100000000ull) / 1000.0); va_list a; va_start(a, f); vsnprintf(b + p, sizeof b - p, f, a); va_end(a); story.push_back(b); }
static void home(int code)
{
    tell("obeyed %%d on view %%u%%s", code, (unsigned) CurrentView, TextInWasStashed ? " (kept)" : " (read)");
    const bool front = code == 1077 || code == 1079 || code == 1080 || code == 1081 || code == 1084, options = code == 39 || code == 1010 || code == 1078 || code == 1082 || code == 1083 || code == 1085;
    if ((front && CurrentView != FRONTVIEW) || (options && CurrentView != RXSETUPVIEW1)) ++wrongPage;
}
static void OpenOneSwitch()   // the Switches page's row for switch 3: the One switch page, its choices as the transmitter has them
{
    SendCommand((char *) "page OneSwitchView"); CurrentView = ONE_SWITCH_VIEW; SwitchEditNumber = 3;
    static const char *const radios[] = { "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "r16", "r17" };
    for (const char *r : radios) SendValue((char *) r, 0);                    // (UpdateOneSwitchView: every choice as the transmitter has it - switch 3 is the safety switch, reversed)
    SendValue((char *) "r7", 1); SendValue((char *) "c_revd", 1);
}
static std::vector<std::string> screenLogLines; static int restartsHandled = 0, lastRestartReason = 99, owedCaughtUp = 0; static bool helpLive = false;
static void OpenModels();
static void storm_telemetry() { if (CurrentView == FRONTVIEW) SendText((char *) "StillConnected", (char *) "Amps 12.3"); }   // (what flying the model writes to the front page)
static void (*extra24)(int) = nullptr, (*extra7)(int) = nullptr;               // (more buttons, for the tests built on this one: dev/test_noanswer)
static bool (*wordHook)(const char *) = nullptr;                               // (... and more WORDS: a page's own "I am back" - main.cpp's "ldrcadj", say)
// (the ninth review) THE STORM'S SECOND PASS: the screen's loop stands still now and then, for a fifth of a second to several seconds, begun at any
// moment - from inside a wait of this board's, or between two passes of its loop
static uint64_t stormNextStall = UINT64_MAX; static uint32_t stormSeed = 1, stormLongest = 4000; static bool stormTele = false; static long stormStalls = 0, stormLongStalls = 0;
static uint32_t stormRnd(uint32_t n) { stormSeed = stormSeed * 1664525u + 1013904223u; return n ? (stormSeed >> 8) %% n : 0; }
static void stormStallDue()
{
    if (nowUs < stormNextStall || nowUs < screen.deadUntil || nowUs < screen.busyUntil) return;
    const uint32_t ms = 200 + stormRnd(stormLongest - 200);
    stormNextStall = nowUs + (uint64_t) ms * 1000 + 300000 + stormRnd(2500000);
    screen.stall(nowUs, ms, true, stormRnd(3) ? stormRnd(2500) : 0, stormRnd(100) < 15 ? 1500 + stormRnd(4500) : 0, stormRnd(8) == 0);
    ++stormStalls; if (ms > 1500) ++stormLongStalls;
}
static void stormHook() { if (stormTele) storm_telemetry(); stormStallDue(); }
static void Dispatch()
{
    if (!TextInIsGenuine()) { memset(TextIn, 0, 8); return; }
    const uint8_t first = (uint8_t) TextIn[0];
    if (first == 0)
    {
        const int n = (uint8_t) TextIn[1] | ((uint8_t) TextIn[2] << 8);
        if (n)
        {
            home(1000 + n);
            obeyed.push_back(1000 + n);
            if (n == 77) OpenOptions(); else if (n == 86) OpenOneSwitch(); else if (n == 78) LeaveQuick(); else if (n == 79) OpenAndRead(); else if (n == 80) OpenAndReadText();
            else if (n == 81) TwoPages(); else if (n == 82) BusyAfterPage(); else if (n == 83) ReadBig(); else if (n == 84) TextWithPageInIt(); else if (n == 85) BusyThenWrite(); else if (n == 87) OpenAndAskPicture();
            else if (n == 88) OpenModels();
            else if (extra24) extra24(n);
        }
    }
    else if (first >= 128) { const int n = first & 0x7F; home(n); obeyed.push_back(n); if (n == 39) RXOptionsViewEnd(); else if (n == 1) Confirmed[0] = 'Y'; else if (extra7) extra7(n); }
    else
    {   // a word, in main.cpp's own order: a line for the log first; the screen's restart word (which no longer comes this far)
        const std::string w = TextIn;
        if (InStrng((char *) "LDRCLOG ", TextIn) > 0) { screenLogLines.push_back(w); tell("a line for the log: %%.30s...", TextIn); memset(TextIn, 0, 8); return; }
        if (ScreenDyingWords(TextIn)) { memset(TextIn, 0, 8); return; }           // (the REAL one, of LogFiles.h: the screen's panic handler's lines, kept in the log)
        words.push_back(w);
        if (helpLive && InStrng((char *) "HelpView", TextIn) > 0) { HelpWordCame(); memset(TextIn, 0, 8); return; }
        if (InStrng((char *) "FrontView", TextIn)) { const char *r = strstr(TextIn, "rst="); NoteScreenRestart(r ? (int8_t) atoi(r + 4) : -1); memset(TextIn, 0, 8); return; }
        if (wordHook && wordHook(w.c_str())) { memset(TextIn, 0, 8); return; }
        if (w == "SwitchesView1") { if (CurrentView != ONE_SWITCH_VIEW) ++wrongPage; tell("obeyed the word %%s on view %%u", w.c_str(), (unsigned) CurrentView); ReadNewSwitchFunction(); }   // (main.cpp: the One switch page's OK)
    }
    memset(TextIn, 0, 8);
}
static bool holdCatchUp = false;   // (a scene that only looks at what was NOTED keeps the loop from answering it)
static int restartsFoundByAsking = 0;
static int frontBeliefs = 0;   // (how often the main loop found the screen on the front page with this board believing another page)
static void LoopPass()   // ManageTransmitter's first lines: the look for a press; and the REAL look at the screen's state (main.cpp ScreenKeepUp: nothing in it waits)
{
    radioService();                                                             // (every pass of the loop flies the model)
    CheckForNextionButtonPress();
    if (!holdCatchUp && (ScreenRestartSeen || ScreenAnswerOwed || (CurrentView != FRONTVIEW && ScreenPageId == SCREEN_FRONT_PAGE) || (!ScreenSaidSession && (int32_t) (millis() - ScreenSessionNextMs) >= 0)))
    {
        const bool restart = ScreenRestartSeen, owed = ScreenAnswerOwed; const int reason = ScreenRestartReason;
        if (!restart && !owed && CurrentView != FRONTVIEW && ScreenPageId == SCREEN_FRONT_PAGE) { ++frontBeliefs; tell("the screen shows the front page and this board believed view %%u: the front page, afresh", (unsigned) CurrentView); }
        ScreenKeepUp();
        if (restart && !ScreenRestartSeen) { lastRestartReason = reason; ++restartsHandled; tell("THE SCREEN HAS RESTARTED (reason %%d): the front page, afresh", reason); }
        else if (!restart && ScreenRestartSeen) { ++restartsFoundByAsking; tell("the screen no longer knew its session's number: IT HAS STARTED AGAIN (found by asking)"); }
        else if (owed && !ScreenAnswerOwed) { ++owedCaughtUp; tell("the screen has caught up: what it owed has come and gone"); }
    }
    KickTheDog();                                                               // (ManageTransmitter: "Watchdog ... ALWAYS!")
}
static void loopFor(uint32_t ms) { const uint64_t until = nowUs + (uint64_t) ms * 1000; while (nowUs < until) { const uint64_t t0 = nowUs; LoopPass(); if (gapWatch && nowUs - t0 > maxPassUs) maxPassUs = nowUs - t0; nowUs += 500; } }
// ---- the Models page's own look at its lists, twice a second (the REAL CheckModelName is lifted in front of this), in ManageTransmitter's
//      order: the look for a press; once a second the housekeeping - a few writes, each of which reads the wire in - AND BACK; else the poll
static void OpenModels()   // the Models page: its list on the model in use (number 4: row 3), the files' list on row 2
{
    SendCommand((char *) "page ModelsView"); CurrentView = MODELSVIEW;
    SendValue((char *) "MMems", 3); SendValue((char *) "Mfiles", 2); ModelNumber = 4; LastModelLoaded = 4; LastFileInView = 2; FileNumberInView = 2;
}
static void loopForModels(uint32_t ms, bool housekeeping = true)
{
    const uint64_t until = nowUs + (uint64_t) ms * 1000; static uint64_t lastPoll = 0, lastHouse = 0;
    while (nowUs < until)
    {
        const uint64_t rightNow = nowUs;
        LoopPass();
        if (housekeeping && rightNow - lastHouse >= 1000000)
        {
            if (CurrentView != 0) { SendText((char *) "DateTime", (char *) "14-11-26 20:00"); SendText((char *) "Comms", (char *) "-"); }
            lastHouse = nowUs; nowUs += 500; continue;
        }
        if (CurrentView == MODELSVIEW && rightNow - lastPoll >= 500000) { lastPoll = rightNow; CheckModelName(); }
        if (gapWatch && nowUs - rightNow > maxPassUs) maxPassUs = nowUs - rightNow;
        nowUs += 500;
    }
}
static int count(const std::vector<int> &v, int x) { int n = 0; for (int e : v) n += e == x; return n; }
static void fresh()
{
    screen = Screen(); nowUs += 10000000;
    Page front, opt;
    front.boxes["t0"] = { true, 0, "" }; front.boxes["Owner"] = { true, 0, "" }; front.boxes["StillConnected"] = { true, 0, "" }; front.boxes["va0"] = { false, 0, "" };
    front.buttons["setup"] = { 0x00, 77, 0x00, 0x00 };                       // (a button of the front page: here, straight to Model options)
    front.buttons["read"] = { 0x00, 79, 0x00, 0x00 }; front.buttons["readtext"] = { 0x00, 80, 0x00, 0x00 }; front.buttons["text"] = { 0x00, 84, 0x00, 0x00 };
    front.buttons["bg"] = { 'U', 'K', 'R', 'U', 'L', 'E', 'S' };              // (the page's own touch: a word, framed as every burst)
    front.buttons["two"] = { 0x00, 81, 0x00, 0x00 }; front.buttons["switch3"] = { 0x00, 86, 0x00, 0x00 }; front.buttons["picture"] = { 0x00, 87, 0x00, 0x00 };
    front.buttons["models"] = { 0x00, 88, 0x00, 0x00 };
    { Page mv; mv.id = 15; mv.boxes["MMems"] = { false, 0, "" }; mv.boxes["Mfiles"] = { false, 0, "" }; mv.boxes["modelname"] = { true, 0, "" }; screen.pages["ModelsView"] = mv; }   // (the card's page 15: its lists on row 0)
    { Page kb; kb.id = 56; screen.pages["keybdA"] = kb; Page none; none.id = 0; screen.pages["NoPage"] = none; Page lg; lg.id = 20; lg.boxes["t0"] = { true, 0, "" }; screen.pages["LogView"] = lg; }
    screen.files.insert("sd0/images/Yak.jpg");
    { Page one, sws;                                                          // the One switch page (its choices, "Reversed", its OK - which prints a WORD) and the Switches page
      for (const char *r : { "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "r16", "r17", "c_revd", "Progress" }) one.boxes[r] = { false, 0, "" };
      { const char *w = "SwitchesView1"; one.buttons["OK"] = std::vector<uint8_t>(w, w + strlen(w)); }
      { const char *w = "HelpView:ONESWICH.TXT"; one.buttons["Help"] = std::vector<uint8_t>(w, w + strlen(w)); }
      sws.boxes["t1"] = { true, 0, "" }; sws.buttons["row3"] = { 0x00, 86, 0x00, 0x00 };
      screen.pages["OneSwitchView"] = one; screen.pages["SwitchesView"] = sws; }
    %(OPTION_BOXES)s
    opt.buttons["OK"] = { 128 + 39, 0x00, 0x00, 0x00 };
    opt.buttons["Servo types"] = { 0x00, 10, 0x00, 0x00 };
    opt.buttons["leave"] = { 0x00, 78, 0x00, 0x00 }; opt.buttons["busy"] = { 0x00, 82, 0x00, 0x00 }; opt.buttons["big"] = { 0x00, 83, 0x00, 0x00 }; opt.buttons["busywrite"] = { 0x00, 85, 0x00, 0x00 };
    opt.buttons["bg"] = { 'U', 'K', 'R', 'U', 'L', 'E', 'S' };
    { const char *w = "CH3NAME=Gear"; opt.buttons["name"] = std::vector<uint8_t>(w, w + strlen(w)); }           // (a typed channel name, as InputsView prints it)
    opt.buttons["a5"] = { 0xA5, 0x00, 0x00, 0x00 };                             // (the 7-bit code 37: its first byte is the file link's too - a path of its own in GetButtonPress)
    { const char *l = "ldrctel 25:AABBCCDD 26:EEFF0011\n"; opt.buttons["pipe"] = std::vector<uint8_t>(l, l + strlen(l)); opt.raw.insert("pipe"); }   // (the Bluetooth pipe's line: the screen's own, unframed)
    opt.boxes["big"] = { false, 0x4C430001L, "" };                            // (a number next to the markers' own: a box's value all the same)
    front.id = 13; opt.id = 9; opt.numberBoxes = { "n3box", "n4box" };                                  // (touching one opens the screen's keyboard)
    screen.pages["FrontView"] = front; screen.pages["RXOptionsView"] = opt; screen.page = "FrontView";
    screen.pages["OneSwitchView"].id = 54; screen.pages["SwitchesView"].id = 53;
    { Page kb; kb.id = 57; kb.boxes["show"] = { true, 0, "" }; screen.pages["keybdB"] = kb; }
    { Page pop; pop.id = 41; pop.boxes["Dialog"] = { true, 0, "" }; pop.buttons["yes"] = { 0x81, 0x00, 0x00, 0x00 }; screen.pages["PopupView"] = pop; }
    screen.pages0 = screen.pages;
    PendingEventLen = 0; PendingCount = 0; TextInFramed = false; ScreenFramesBursts = true; FrameEnableSentMs = 0; memset(TextIn, 0, 64);
    NextionGetPending = false; NextionTextMissed = false; NextionReplyWaitMs = 100; CurrentView = FRONTVIEW; mayFly = false;
    BankSwitch = 1; Autoswitch = 2; SafetySwitch = 3; BuddySwitch = 0; DualRatesSwitch = 4; FrontSwitchUnused = 0; SwitchEditNumber = 3; memset(TopChannelSwitch, 0, sizeof TopChannelSwitch);
    memset(SwitchReversed, 0, sizeof SwitchReversed); SwitchReversed[2] = true; txSaves = 0; switchPagesDrawn = 0; waitHook = nullptr;
    CopyTrimsToAll = UseMotorKill = TimerDownwards = SixBanks = true; TrimMultiplier = 5; MotorChannelZero = 45; MotorChannel = 4;
    StopFlyingVoltsPerCell = 3.5f; Max_Safe_Amps = 120; SFV = 350; TimerStartTime = 360; RxVoltageCorrection = 3;
    saves.clear(); obeyed.clear(); words.clear(); ghosts.clear(); lateReplies.clear(); logLines.clear(); radioPasses = 0; picMissing = picThere = 9; boxUpAtUs = boxAnsweredAtUs = 0;
    ScreenMarkAwaited = 0; ScreenMarkOldPage = false; ScreenMarkMisses = 0; LoadPrintsLetGo = 0; ScreenPageId = 0xFF; ScreenPageIdDue = false; ScreenPageUnsaid = 0; offPage = 0; stale = 0; noMarks = 0; staleCodes.clear(); readNumber = 0; readText[0] = 0; wrongPage = 0; story.clear(); underGet = 0; PageChangedUnderGet = false;
    ScreenRestartSeen = false; ScreenRestartReason = -1; ScreenRestartSeenMs = 0; ScreenStartupOver = true; ScreenSession = 0; ScreenToldMs = 0; ScreenSaidSession = false; ScreenSaysPage = false; pageUnsaid = 0;
    gapWatch = false; maxRadioGapUs = 0; maxPassUs = 0; lastRadioUs = 0; flyHook = nullptr; holdCatchUp = false;
    restartsHandled = 0; lastRestartReason = 99; screenLogLines.clear(); frontReasons.clear(); frontBriefs.clear(); frontMore.clear(); warmups = 0; helpLive = false; helpOpened.clear(); questionsClosed = 0; boxSpins = 0; modelsRead.clear();
    frontAsksPicture = false; Confirmed[0] = '?'; ModalWaits = 0; ModelNumber = 3; LastModelLoaded = 0; FileNumberInView = 0; LastFileInView = 0; SavedCurrentView = 0;
    extra24 = nullptr; extra7 = nullptr; QuestionClosedItself = QuestionOvertaken = false; BoxesLostAtWork = BoxesLost; InsideDelayWithDog = false; nestedWaits = 0; dogWatch = false; maxUnfedUs = 0; lastFeedUs = 0; dogKicks = 0; powerButtonHook = nullptr; sendDataHook = nullptr; BoundFlag = ModelMatched = false;
    questionsOvertaken = 0; questionsSilent = 0; ScreenPageSaidCount = 0; boxesLostTold = 0; soundsPlayed = 0; CurrentMode = NORMAL; paramsLoaded = 0; redLeds = 0; ScreenAnswerOwed = false; ScreenOwedSinceMs = 0; owedCaughtUp = 0;
    PageLeftUnderWork = false; RfKeepTyped = false; RfSettleAsked = false; wordHook = nullptr;
    ScreenSaysMarks = false; ScreenMarkGivenUp = false; ScreenSessionSaidN = 0; ScreenSessionTries = 0; ScreenSessionNextMs = millis() /* (the sixteenth review: "now", as at a real power-on - it was 0, and a storm past 2^31 ms of this clock never told the session's number: the board's signed comparison never came true) */; ScreenSessionUnsaid = 0; ScreenEcho = 0; ScreenEchoToldMs = 0; ScreenSaidEcho = false;
    ScreenEchoAskedSession = false; ScreenEchoSessionN = 0; ScreenEchoMarkCount = 0; WordOpenMs = 0; TextReplyDoubted = false; textDoubted = 0; restartsFoundByAsking = 0; frontBeliefs = 0;
    %(FRESH_MORE)s
}
static void tapAt(uint32_t msFromNow, const char *button) { screen.taps.insert({ nowUs + (uint64_t) msFromNow * 1000, button }); }
static void report(const char *what)
{
    say("%%s\n   obeyed:", what); for (int c : obeyed) say(" %%d", c); say("   saves: %%d", (int) saves.size());
    for (auto &s : saves) say("  [on page %%u: motor switch %%d, stop flying %%.2f V, trim step %%u, six banks %%d, timer %%u s, most amps %%d]", s.view, s.kill, s.volts, s.step, s.six, s.timer, s.amps);
    say("\n   the model now: motor switch %%d, stop flying %%.2f V, trim step %%u, six banks %%d, timer %%u s\n", UseMotorKill, StopFlyingVoltsPerCell, TrimMultiplier, SixBanks, TimerStartTime);
    for (auto &l : logLines) say("   log: %%s\n", l.c_str());
    say("   the screen:"); for (auto &l : screen.log) say(" [%%s]", l.c_str()); say(" taps on nothing: %%d, odd commands: %%d\n", screen.tapsOnNothing, screen.oddCommands);
    say("   let go between the two markers: %%u;", (unsigned) LoadPrintsLetGo);
    say("   presses not obeyed (their page had gone): %%d;", stale); for (auto &c : staleCodes) say(" %%s", c.c_str()); say("   markers awaited: %%s, never came: %%d\n", ScreenMarkAwaited ? "one" : "none", noMarks);
}
int main(int argc, char **argv)
{
    show = argc > 1 && !strcmp(argv[1], "--show");
    // 1. one tap on OK: the page is read, the model saved once, as it was; the front page comes
    fresh(); tapAt(5, "setup"); loopFor(600); CHECK(screen.page == "RXOptionsView" && CurrentView == RXSETUPVIEW1 && count(obeyed, 1077) == 1);
    tapAt(5, "OK"); loopFor(3000);
    report("1. one tap on OK");
    CHECK(count(obeyed, 39) == 1 && saves.size() == 1); CHECK(sameAsAtFirst()); CHECK(screen.page == "FrontView"); CHECK(CurrentView == FRONTVIEW);
    // 2. THE FAULT: two taps on OK, a quarter of a second apart - the second while the first one's boxes are being read
    fresh(); tapAt(5, "setup"); loopFor(600); tapAt(5, "OK"); tapAt(255, "OK"); loopFor(4000);
    report("2. two taps on OK, 250 ms apart");
    CHECK(screen.tapsOnNothing == 0);                        // (the second tap did land on OK: the page was still there)
    CHECK(count(obeyed, 39) == 1);                           // obeyed once
    CHECK(saves.size() == 1 && sameAsAtFirst());             // saved once, and the model is as it was
%(SCENES)s
    // 19. a screen that does not frame (an older one): a press glued in front of the marker (B162's way) is the old page's, the
    //     marker is no answer, and the get's own answer behind them is the answer
    {
        fresh(); ScreenFramesBursts = false; ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
        screen.emit(nowUs, { 0xA7, 0x00, 0x00, 0x00, 'q', 9, 0, 0x45, 0x4C, 0xFF, 0xFF, 0xFF, 'q', 5, 0, 0, 0, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
        uint16_t k = 0; CHECK(CollectReply('q', k) && k == 8 && TextIn[0] == 'q' && TextIn[1] == 5 && !ScreenMarkAwaited && stale == 1 && PendingCount == 0);
        // ... and with no marker awaited, B162's own case is as it was: the press kept, the answer the answer
        fresh(); ScreenFramesBursts = false;
        screen.emit(nowUs, { 0xA7, 0x00, 0x00, 0x00, 'q', 5, 0, 0, 0, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
        k = 0; CHECK(CollectReply('q', k) && k == 8 && TextIn[1] == 5 && PendingCount == 1 && stale == 0);
        PendingCount = 0; PendingEventLen = 0;
    }
    // 20. 'Motor off' is a number someone could have typed, or it is not taken: four digits are held to 500..2500 as ever (B129:
    //     the old units typed by habit land on the low end), but a missed answer and a number in the millions (the marker's own
    //     kind) leave it alone - the last would have made 'motor off' full throttle
    {
        const long typed[] = { 1000, 400, 2600, 0, -67, 9999, 10000, -10000, 65535, 0x4C440007L, 0x4C450007L, 1500 };
        const int  wants[] = {   45,   0,  180, 0,   0,  180,    -1,     -1,    -1,          -1,          -1,   90 };
        for (size_t i = 0; i < sizeof(typed) / sizeof(typed[0]); ++i)
        {
            fresh(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n0"].val = typed[i]; MotorChannelZero = 77;
            tapAt(5, "OK"); loopFor(3500);
            CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && MotorChannelZero == (wants[i] < 0 ? 77 : wants[i]) && UseMotorKill && TrimMultiplier == 5 && TimerStartTime == 360);
        }
        // ... and the marker's kind of number is no box's answer at all (GetNumberReply): the box is "not answered", not a value
        fresh(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["big"].val = 0x4C440007L; NextionTextMissed = false; readNumber = 0;
        tapAt(5, "big"); loopFor(3500); CHECK(count(obeyed, 1083) == 1 && readNumber == 65535 && NextionTextMissed);
    }
    // 17. two page commands one after the other (a page left at once): the first one's marker does not end the wait for the
    //     second's - a code of the page between them (here a tap that fell through onto it) comes between the two markers
    fresh(); screen.latencyUs = 40000; screen.tapInLoadFallsThrough = true; screen.tapAfterPageUs = 50000; screen.tapAfterPageButton = "OK"; tapAt(5, "two"); loopFor(3000);   // (50 ms after the first page command left: the screen is loading that page)
    report("17. two page commands, a tap on the page between them");
    CHECK(screen.tapsOnNothing == 0 && screen.loads == 2 && count(obeyed, 1081) == 1 && count(obeyed, 39) == 0 && saves.empty() && stale == 1 && !ScreenMarkAwaited && noMarks == 0);
    // 18. the lines in the log (the real NoteStalePress and NoteNoScreenMark of LogFiles.h): on the ground the whole story, one in
    //     two seconds; while the model may fly a short line kept for later (36 places); the empty burst is no press
    {
        fresh(); CurrentView = RXSETUPVIEW1; nowUs += 5000000;
        const uint8_t ok[4] = { 0xA7, 0, 0, 0 }, servo[4] = { 0, 10, 0, 0 }, empty[4] = { 0, 0, 0, 0 };
        real::StalePressCount = 0; real::NoteStalePress(ok, 4);
        CHECK(real::StalePressCount == 1 && logLines.size() == 1 && logLines[0] == "Screen press not obeyed (its page had gone): A7 00 00 00 (page 28) B211");
        real::NoteStalePress(servo, 4); CHECK(real::StalePressCount == 2 && logLines.size() == 1);     // (counted; the log has had its line for now)
        real::NoteStalePress(empty, 4); real::NoteStalePress(ok, 3); CHECK(real::StalePressCount == 2);   // (nothing was pressed)
        nowUs += 2100000; mayFly = true; real::NoteStalePress(servo, 4);
        CHECK(real::StalePressCount == 3 && logLines.size() == 2 && logLines[1] == "(kept for later) Old press dropped: 00 0A 00 00" && logLines[1].size() - 17 <= 36);
        // a word a page's button printed: said by its name
        nowUs += 2100000; mayFly = false; real::NoteStalePress((const uint8_t *) "SwitchesView1", 13);
        CHECK(real::StalePressCount == 4 && logLines.size() == 3 && logLines[2] == "Screen press not obeyed (its page had gone): SwitchesView1 (page 28) B211");
        nowUs += 2100000; mayFly = true; real::NoteStalePress((const uint8_t *) "HelpView:RXSETUP1.TXT", 21);
        CHECK(real::StalePressCount == 5 && logLines.size() == 4 && logLines[3] == "(kept for later) Old press dropped: HelpView:RXSETUP1" && logLines[3].size() - 17 <= 36);
        logLines.erase(logLines.begin() + 2, logLines.end()); mayFly = true;
        nowUs += 2100000; mayFly = false; real::NoteNoScreenMark(); CHECK(logLines.size() == 3 && logLines[2].find("did not confirm a page change") != std::string::npos);
        real::NoteNoScreenMark(); CHECK(logLines.size() == 3);                                           // (once in a minute)
        nowUs += 61000000; mayFly = true; real::NoteNoScreenMark(); CHECK(logLines.size() == 4 && logLines[3] == "(kept for later) No page marker from the screen" && logLines[3].size() - 17 <= 36);
        // ... and a page changed under a get: said, with the box asked for; once in ten seconds
        mayFly = false; real::NotePageChangedUnderGet("get n3.val"); real::NotePageChangedUnderGet("get n4.val");
        CHECK(logLines.size() == 5 && logLines[4] == "The page was changed while the screen was asked 'get n3.val': its answer was not used B211");
        nowUs += 11000000; mayFly = true; real::NotePageChangedUnderGet("get n4.val"); CHECK(logLines.size() == 6 && logLines[5] == "(kept for later) Page changed under get n4.val" && logLines[5].size() - 17 <= 36);
        // ... the keyboard's and the restart's notes (the seventh review: nothing looked at them): on the ground the whole story, while the
        //     model may fly a short line kept for later - never a write to the card in the air
        nowUs += 61000000; mayFly = false; logLines.clear(); real::NoteBoxOffPage("get n3.val", false); real::NoteBoxOffPage("get n4.val", false);
        CHECK(logLines.size() == 1 && logLines[0] == "The screen was showing another page (its keyboard?) when asked 'get n3.val': not used B211");
        nowUs += 61000000; real::NoteBoxOffPage("get n3.val", true); CHECK(logLines.size() == 2 && logLines[1] == "The screen did not say which page it showed when asked 'get n3.val': not used B211");
        nowUs += 61000000; mayFly = true; real::NoteBoxOffPage("get n3.val", false); CHECK(logLines.size() == 3 && logLines[2] == "(kept for later) Other page shown at get n3.val" && logLines[2].size() - 17 <= 36);
        nowUs += 61000000; real::NoteBoxOffPage("get t10.txt_and_a_long_name", true); CHECK(logLines.size() == 4 && logLines[3] == "(kept for later) Page not said at get t10.txt_and_a_l" && logLines[3].size() - 17 <= 36);
        mayFly = false; real::NoteQuestionClosed(1); CHECK(logLines.size() == 5 && logLines[4].find("closed as 'No'") != std::string::npos && logLines[4].find("restarted") != std::string::npos && logLines[4].rfind("(kept", 0) != 0);
        mayFly = true; real::NoteQuestionClosed(1); CHECK(logLines.size() == 6 && logLines[5] == "(kept for later) Question closed: screen restart" && logLines[5].size() - 17 <= 36);
        // (The twelfth review; the released code had it: the three OLDER notes wrote the card AT ONCE whatever flew - a late answer, a frame not obeyed (a
        //  cut line's tail on a field screen is one, read by the main loop), the front page by itself. Kept for a quiet moment now, and short, as these.)
        const auto npos = std::string::npos;
        logLines.clear(); mayFly = false; real::NoteLateReply("get tn12.txt", 700, true); real::NoteLateReply("get tn12.txt", 2000, false); real::NoteLateReply("get n3.val", 300, true);
        CHECK(logLines.size() == 2 && logLines[0].find("late") != npos && logLines[0].find("700 ms") != npos && logLines[0].rfind("(kept", 0) != 0 && logLines[1].find("MISSING") != npos && logLines[1].rfind("(kept", 0) != 0);
        mayFly = true; real::NoteLateReply("get tn12.txt", 700, true); real::NoteLateReply("get a_box_with_a_long_name.txt", 2000, false); real::NoteLateReply("get n3.val", 300, true);
        CHECK(logLines.size() == 4 && logLines[2] == "(kept for later) Late 700 ms: get tn12.txt" && logLines[3] == "(kept for later) No answer: get a_box_with_a_long_na" && logLines[2].size() - 17 <= 36 && logLines[3].size() - 17 <= 36);
        { const uint8_t tail[] = { 'p', 'l', 'a', 'y', ' ', '0', ',', '7', ',', '0' };
          logLines.clear(); nowUs += 2100000; mayFly = false; real::LogGhostFrame("an unframed word", tail, sizeof tail);
          CHECK(logLines.size() == 1 && logLines[0].find("Screen frame dropped (an unframed word): 70 6C 61 79 20 30 2C 37") != npos && logLines[0].rfind("(kept", 0) != 0);
          nowUs += 2100000; mayFly = true; real::LogGhostFrame("an unframed word", tail, sizeof tail);
          CHECK(logLines.size() == 2 && logLines[1] == "(kept for later) Dropped (unframed word) 70 6C 61 79" && logLines[1].size() - 17 <= 36);
          real::LogGhostFrame("an unframed word", tail, sizeof tail); CHECK(logLines.size() == 2);     // (once in two seconds, as ever)
          // (the thirteenth review: nine letters of the reason made a word and a code one and the same - "an unfram")
          nowUs += 2100000; real::LogGhostFrame("an unframed code", tail, sizeof tail); nowUs += 2100000; real::LogGhostFrame("an incomplete framed burst", tail, sizeof tail);
          CHECK(logLines.size() == 4 && logLines[2] == "(kept for later) Dropped (unframed code) 70 6C 61 79" && logLines[3] == "(kept for later) Dropped (incomplete fra) 70 6C 61 79" && logLines[3].size() - 17 <= 36); }
        logLines.clear(); mayFly = false; real::FrontReasonLogged = false; CurrentView = 9; real::LogFrontPageReason("the motor switch went on", "motor switch on", nullptr);
        CHECK(logLines.size() == 1 && logLines[0] == "Front page by itself: the motor switch went on (it was on page 9) B172" && real::FrontReasonLogged);
        mayFly = true; real::FrontReasonLogged = false; real::LogFrontPageReason("the power button was pressed while connected", "power button", nullptr);
        CHECK(logLines.size() == 2 && logLines[1] == "(kept for later) Page 9 -> front: power button" && logLines[1].size() - 17 <= 36 && real::FrontReasonLogged);
        CurrentView = 255; real::LogFrontPageReason("the box 'The motor switch is ON' is over", "motor box is over", "a second line of thirty-six places !!");
        CHECK(logLines.size() == 4 && logLines[2] == "(kept for later) Page 255 -> front: motor box is over" && logLines[2].size() - 17 == 36 && logLines[3] == "(kept for later) a second line of thirty-six places !!");
        mayFly = false; CurrentView = FRONTVIEW;
    }

    // 22. A BUTTON THAT PRINTS A WORD (half the older pages' do): the One switch page's OK prints "SwitchesView1" and its
    //     routine reads nineteen boxes. A second tap, obeyed on the Switches page where every box answers 0, took the safety
    //     switch's job away, cleared "reversed" and saved (the fourth review). The word is a press as a code is: not obeyed
    fresh(); tapAt(5, "switch3"); loopFor(600); CHECK(screen.page == "OneSwitchView" && CurrentView == ONE_SWITCH_VIEW && count(obeyed, 1086) == 1);
    tapAt(5, "OK"); tapAt(255, "OK"); loopFor(5000);
    report("22. two taps on the One switch page's OK (a word), 250 ms apart");
    CHECK(screen.tapsOnNothing == 0 && words.size() == 1 && words[0] == "SwitchesView1" && wrongPage == 0 && stale == 1 && staleCodes[0] == "SwitchesView1");
    CHECK(switchesAsAtFirst() && saves.size() == 1 && txSaves == 1 && switchPagesDrawn == 1 && screen.page == "SwitchesView" && CurrentView == SWITCHES_VIEW);
    //     ... and in the gap, after the page command has left
    fresh(); screen.latencyUs = 40000; tapAt(5, "switch3"); loopFor(800);
    screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "OK"; tapAt(5, "OK"); loopFor(5000);
    CHECK(screen.tapsOnNothing == 0 && words.size() == 1 && wrongPage == 0 && stale == 1 && switchesAsAtFirst() && saves.size() == 1 && noMarks == 0);
    // 23. ... and that routine with an answer that NEVER COMES (the screen busy for two seconds): the job stays as it was. It was
    //     taken for "chosen": the switch being edited became the bank switch and the dual-rates switch (and, for that box, the
    //     safety switch)
    fresh(); tapAt(5, "switch3"); loopFor(600); screen.mute.insert("r1"); screen.mute.insert("r8");
    tapAt(5, "OK"); loopFor(9000);
    CHECK(words.size() == 1 && BankSwitch == 1 && DualRatesSwitch == 4 && SafetySwitch == 3 && Autoswitch == 2 && SwitchReversed[2] && lateReplies.size() == 1 && saves.size() == 1);   // (ONE wait of two seconds: after an answer that never came no box of this press is asked - the seventh review)
    // 24. a page's own words are no press: a typed channel name printed by the page being left, in the gap, passes
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "name"; tapAt(5, "leave"); loopFor(3000);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1078) == 1 && words.size() == 1 && words[0] == "CH3NAME=Gear" && stale == 0);
    { const uint8_t a[] = "ldrcadj", b[] = "ldrcrcv", c[] = "CH16NAME=x", d[] = "CH1NAME=", e[] = "UKRULES", f[] = "CHANNEL=", g[] = "SwitchesView1", h[] = "CH17", i[] = "CH0NAME=";
      CHECK(IsPageOwnWord(a, 7) && IsPageOwnWord(b, 7) && IsPageOwnWord(c, 10) && IsPageOwnWord(d, 8) && IsPageOwnWord(e, 7) && !IsPageOwnWord(f, 8) && !IsPageOwnWord(g, 13) && !IsPageOwnWord(h, 4) && !IsPageOwnWord(i, 8));
      CHECK(IsPress(g, 13, true) && !IsPress(g, 13, false) && !IsPress(a, 7, true) && !IsPress(e, 7, true) && !IsPress(c, 10, true) && !IsPress(g, 0, true));   // (a bare word is the screen's own: never a press)
      const uint8_t code[4] = { 0xA7, 0, 0, 0 }; CHECK(IsPress(code, 4, true) && IsPress(code, 4, false)); }
    // 25. A MARKER GLUED BEHIND A BARE WORD of the screen's own (UKRULES, TIME= have no end of their own): the marker is noted
    //     and the word is the word - read by the loop, and read in by a write. A word that merely ends like one is left whole
    for (int way = 0; way < 2; ++way)
    {
        fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
        screen.emit(nowUs, { 'U', 'K', 'R', 'U', 'L', 'E', 'S', 'q', 9, 0, 0x45, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
        if (way) { StashPendingEventBytes(); CHECK(PendingCount == 1 && PendingLens[0] == 7 && !ScreenMarkAwaited); }
        CHECK(GetButtonPress() && !strcmp(TextIn, "UKRULES") && !TextInFramed && !ScreenMarkAwaited && TextInIsGenuine());
        CHECK(!GetButtonPress() && noMarks == 0 && ghosts.empty());
        fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
        screen.emit(nowUs, { 'T', 'I', 'M', 'E', '=', 'q', 9, 0, 0x48, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 1000;      // (0x4C48....: no marker)
        if (way) StashPendingEventBytes();
        CHECK(GetButtonPress() && !memcmp(TextIn, "TIME=q\x09", 7) && ScreenMarkAwaited != 0);
    }
    // 26. THE PICTURE QUESTION straight after a page command (Model options after Help; Models after its question box): it took
    //     the page's marker for its answer - "the picture is there" for one that is not - and the marker was lost with it (the
    //     page's buttons dead until it was given up). Now: the right answer to both, the marker noted, the page's buttons at once
    fresh(); screen.latencyUs = 40000; tapAt(5, "picture"); loopFor(1500);
    CHECK(count(obeyed, 1087) == 1 && picMissing == 0 && picThere == 1 && !ScreenMarkAwaited && noMarks == 0 && lateReplies.empty());
    tapAt(5, "OK"); loopFor(3000); CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && stale == 0);
    fresh(); screen.knowsSysGet = false; tapAt(5, "picture"); loopFor(6000); CHECK(picMissing == -1 && picThere == -1);   // (a screen that says nothing: "no answer", which is not "no")
    // 27. THE PAGE CHANGED UNDER A GET (from inside the wait that flies the model: the power button's way to the front page did
    //     it, until now): the box being asked has no answer - and nor has any box after it, for as long as this press's work
    //     lasts: they are not asked. Model options' OK then keeps what it has for them; nothing is read from the front page
    fresh(); tapAt(5, "setup"); loopFor(800); waitHook = FrontPageUnderIt; NextionTextMissed = false;
    { const uint32_t v = GetValue((char *) "n3"); nowUs += 30000; screen.run(nowUs); const int gets0 = screen.gets;
      CHECK(v == 65535 && NextionTextMissed && underGet == 1 && PageChangedUnderGet && screen.page == "FrontView");
      NextionTextMissed = false; CHECK(GetValue((char *) "n4") == 65535 && NextionTextMissed);
      char t[20] = "x"; NextionTextMissed = false; CHECK(GetText((char *) "t10", t, sizeof t) == 0 && t[0] == 0 && NextionTextMissed && !strcmp(NextionMissedBox, "t10"));
      nowUs += 5000; screen.run(nowUs); CHECK(screen.gets == gets0);                         // (not asked at all)
      loopFor(50); CHECK(!PageChangedUnderGet); }                                             // the next look for a press: over
    fresh(); tapAt(5, "setup"); loopFor(800);
    screen.pages["RXOptionsView"].boxes["n3"].val = 9; screen.pages["RXOptionsView"].boxes["n4"].val = 2;   // (typed: trim step 9, two minutes)
    tapAt(5, "OK"); loopFor(3); waitHook = FrontPageUnderIt; loopFor(4000);                 // the front page comes up under the first box's get
    report("27. the front page came up under Model options' OK");
    CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && underGet == 1 && sameAsAtFirst());   // nothing taken from the front page: all as it was
    // 28. A SCREEN THAT TAKES A ROUND OF ITS LOOP between putting the page up and answering the marker (the twin's flip): a tap
    //     on the NEW page within that round comes before the marker and is not obeyed - one tap lost, to the right side - and
    //     the next is
    fresh(); screen.roundUs = 60000; screen.tapAfterPageUs = 1500 + 90000 + 20000; screen.tapAfterPageButton = "OK"; tapAt(5, "setup"); loopFor(1500);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1077) == 1 && count(obeyed, 39) == 0 && stale == 0 && LoadPrintsLetGo == 1 && !ScreenMarkAwaited && noMarks == 0);
    tapAt(5, "OK"); loopFor(3000); CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst());
    // 29. A PAGE'S TIMER that ticks the moment the page is up and then at its pace (the Governor page's, code 58): the first
    //     tick comes before the marker and is let go, the next ones are obeyed - and one still on its way when the page is
    //     left is not obeyed on the next page
    fresh(); screen.roundUs = 30000; screen.pages["RXOptionsView"].timerUs = 500000; screen.pages["RXOptionsView"].timerPrint = { 0x00, 58, 0x00, 0x00 };
    tapAt(5, "setup"); loopFor(1400);
    CHECK(screen.ticks == 3 && count(obeyed, 1058) == 2 && stale == 0 && LoadPrintsLetGo == 1 && wrongPage == 0);
    screen.latencyUs = 40000; tapAt(170, "leave"); loopFor(1500);                            // (left some 25 ms before a tick, on a screen 40 ms behind: the tick is the old page's)
    CHECK(count(obeyed, 1078) == 1 && screen.ticks == 4 && count(obeyed, 1058) == 2 && stale == 1 && LoadPrintsLetGo == 1 && wrongPage == 0);
    // 30. AN OLDER SCREEN, which frames nothing: its codes are under the same rule (its words cannot be: nothing tells a page's
    //     word from the screen's own) - also the code whose first byte is the file link's, which has a path of its own
    fresh(); screen.frames = false; screen.canFrame = false; ScreenFramesBursts = false; screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 30000; screen.tapAfterPageButton = "a5"; tapAt(5, "leave"); loopFor(3000);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1078) == 1 && count(obeyed, 37) == 0 && stale == 1 && staleCodes[0] == "A5000000" && !ScreenMarkAwaited);
    fresh(); screen.frames = false; screen.canFrame = false; ScreenFramesBursts = false; tapAt(5, "setup"); loopFor(800); tapAt(5, "a5"); loopFor(300);
    CHECK(count(obeyed, 37) == 1 && stale == 0);                                             // (on its own page it is obeyed)
    // 31. THE MARKER IN TWO PIECES (the screen's port held for a moment in the middle of it): the loop waits for the rest, two
    //     milliseconds at most, and reads it whole - not its first bytes as a word
    fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
    screen.emit(nowUs, { 'q', 9, 0 }); screen.emit(nowUs + 300, { 0x45, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 60;
    CHECK(NEXTION.available() == 3); CHECK(!GetButtonPress() && !ScreenMarkAwaited && PendingCount == 0 && NEXTION.available() == 0 && ghosts.empty());

    // 32. THE SCREEN'S OWN KEYBOARD (the fifth review): OK, and a quarter of a second later a touch on a number box - the screen
    //     puts its keyboard page up BY ITSELF, with no page command of this board's, and the rest of the boxes answered 0: motor
    //     switch off saved (on the PID page: zeros sent). Now every box is asked with "which page are you showing?", and the
    //     boxes read under the keyboard have no answer: the model keeps what it had
    fresh(); tapAt(5, "setup"); loopFor(800); CHECK(ScreenPageId == 9 && !ScreenPageIdDue);       // (the page's number, said behind its second marker)
    tapAt(5, "OK"); tapAt(255, "n3box"); loopFor(4000);
    report("32. OK, then a number box touched while the boxes are read");
    CHECK(screen.keyboards == 1 && screen.offPageAnswers >= 1 && count(obeyed, 39) == 1 && saves.size() == 1 && offPage == 1 && sameAsAtFirst() && screen.page == "FrontView");
    //     ... a box asked while the keyboard is up: no answer; the keyboard closed (the page comes back by itself, no marker
    //     awaited: its own print as it comes up is obeyed), the next press's boxes are answered again
    fresh(); screen.pages["RXOptionsView"].loadPrint = { 0xCC, 0x00, 0x00, 0x00 }; tapAt(5, "setup"); loopFor(800); obeyed.clear(); LoadPrintsLetGo = 0;
    tapAt(5, "n4box"); loopFor(200); CHECK(screen.page == "keybdB" && screen.keyboardOver == "RXOptionsView");
    NextionTextMissed = false; CHECK(GetValue((char *) "n4") == 65535 && NextionTextMissed && PageChangedUnderGet && offPage == 1);
    { char t[20] = "x"; CHECK(GetText((char *) "t10", t, sizeof t) == 0 && t[0] == 0); }
    tapAt(5, "kbOK"); loopFor(600); CHECK(screen.page == "RXOptionsView" && count(obeyed, 76) == 1 && LoadPrintsLetGo == 0);
    NextionTextMissed = false; CHECK(GetValue((char *) "n4") == 6 && !NextionTextMissed && !PageChangedUnderGet);
    //     ... and the Rotorflight pages' look at the screen before they read their boxes (RfGatherStart) finds the keyboard too
    fresh(); tapAt(5, "setup"); loopFor(800); RfGatherStart(); CHECK(NextionSettledOk && !PageChangedUnderGet && ScreenPageId == 9);
    tapAt(5, "n3box"); loopFor(200); RfGatherStart(); CHECK(NextionSettledOk && PageChangedUnderGet && offPage == 1);
    NextionTextMissed = false; CHECK(GetValue((char *) "n3") == 65535 && NextionTextMissed); loopFor(20);
    //     ... a screen that does not say which page it shows (an older one): the boxes' answers are used, as they always were
    fresh(); screen.knowsSendme = false; tapAt(5, "setup"); loopFor(800); CHECK(ScreenPageId == 0xFF && !ScreenSaysPage);
    { const uint64_t t0 = nowUs; CHECK(GetValue((char *) "n3") == 5); CHECK(nowUs - t0 < 200000); }     // (... and is waited for 60 ms at a box, not the 600 of one that does say)
    tapAt(5, "OK"); loopFor(4000); CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && ScreenPageUnsaid >= 10 && offPage == 0);
    // 33. THE SCREEN RESTARTS UNDER AN OK (its watchdog): it comes back on the same page with the page file's values, and says
    //     "FrontView rst=N" before it answers anything. The boxes after that word have no answer: the page file's values are
    //     not saved as the model's (throttle on channel 16 among them)
    fresh(); tapAt(5, "setup"); loopFor(800);
    screen.pages0["RXOptionsView"].boxes["n1"].val = 16; screen.pages0["RXOptionsView"].boxes["c0"].val = 0; screen.pages0["RXOptionsView"].boxes["t10"].txt = "3.80";
    tapAt(5, "OK"); tapAt(260, "#restart"); loopFor(16000);
    report("33. the screen restarted under Model options' OK");
    if (show) { std::vector<std::string> all = story; all.insert(all.end(), screen.events.begin(), screen.events.end()); std::sort(all.begin(), all.end(), [](const std::string &a, const std::string &b) { return atof(a.c_str()) < atof(b.c_str()); }); for (auto &l : all) printf("      %%s\n", l.c_str());
      printf("      motor channel %%u, kill %%d, zero %%u, corr %%d, late replies:", MotorChannel, UseMotorKill, MotorChannelZero, RxVoltageCorrection); for (auto &l : lateReplies) printf(" [%%s]", l.c_str()); printf(" words:"); for (auto &w : words) printf(" [%%s]", w.c_str()); printf(" page %%s\n", screen.page.c_str()); }
    CHECK(screen.restarts == 1 && count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && MotorChannel == 4 && UseMotorKill);
    CHECK(words.empty() && restartsHandled == 1 && lastRestartReason == 5 && !ScreenRestartSeen && screen.page == "FrontView");
    // 34. A QUESTION BOX PUT UP FROM INSIDE A GET'S WAIT (the link lost with the motor switch on): the page of the boxes being
    //     read has gone - they have no answer; and the box's own OK is obeyed at the first tap (its markers were left unread
    //     while the get "waited", and the box was deaf for a second and a half: the fifth review)
    fresh(); tapAt(5, "setup"); loopFor(800); waitHook = BoxInWait; NextionTextMissed = false; tapAt(400, "yes");
    { const uint32_t v = GetValue((char *) "n3");
      CHECK(v == 65535 && NextionTextMissed && underGet == 1 && boxAnsweredAtUs != 0 && boxAnsweredAtUs - boxUpAtUs < 450000 && screen.tapsOnNothing == 0);
      NextionTextMissed = false; CHECK(GetValue((char *) "n4") == 65535 && NextionTextMissed);   // (the goback's page command went under the same get: the rest have no answer either)
      loopFor(400); CHECK(!PageChangedUnderGet && !ScreenMarkAwaited && noMarks == 0); }
    //     ... the box's OK on the wire right behind the box's own marker (a tap that fell through as the box came up): the loop
    //     reads marker, number and press frame by frame - read in one lump, the press was lost and the box waited for another
    fresh(); screen.tapInLoadFallsThrough = true; tapAt(5, "setup"); loopFor(800); waitHook = BoxInWait;
    screen.tapAfterPageUs = 30000; screen.tapAfterPageButton = "yes";                        // (30 ms after the box's page command: the screen is loading it)
    { const uint32_t v = GetValue((char *) "n3"); CHECK(v == 65535 && boxAnsweredAtUs != 0 && boxAnsweredAtUs - boxUpAtUs < 200000 && screen.tapsOnNothing == 0); loopFor(400); }
    //     ... and A PAGE'S BOXES ARE STILL TAKEN (nothing above may make a Save deaf): after Model options, the One switch page -
    //     another page, another number - with a choice changed on it: its OK takes the change
    fresh(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n3"].val = 9; tapAt(5, "OK"); loopFor(3000);
    CHECK(count(obeyed, 39) == 1 && TrimMultiplier == 9 && ScreenPageId == 13);
    tapAt(5, "switch3"); loopFor(800); CHECK(ScreenPageId == 54); screen.pages["OneSwitchView"].boxes["r1"].val = 1; screen.pages["OneSwitchView"].boxes["r7"].val = 0;
    tapAt(5, "OK"); loopFor(5000);
    CHECK(words.size() == 1 && BankSwitch == 3 && SafetySwitch == 0 && offPage == 0 && underGet == 0 && ScreenPageId == 53);
    // 35. the other two readers of a box: a TEXT box under which the page is changed has no answer; GetOtherValue (a part's
    //     other attribute) the same - and for it a marker is no value, and the keyboard's page is "no answer" (0 there)
    fresh(); tapAt(5, "setup"); loopFor(800); waitHook = FrontPageUnderIt; NextionTextMissed = false;
    { char t[20] = "x"; CHECK(GetText((char *) "t10", t, sizeof t) == 0 && t[0] == 0 && NextionTextMissed && underGet == 1 && !strcmp(NextionMissedBox, "t10")); loopFor(50); }
    fresh(); tapAt(5, "setup"); loopFor(800); CHECK(GetOtherValue((char *) "n4.val") == 6 && offPage == 0);
    waitHook = FrontPageUnderIt; CHECK(GetOtherValue((char *) "n4.val") == 0 && underGet == 1 && PageChangedUnderGet); CHECK(GetOtherValue((char *) "n3.val") == 0); loopFor(50);
    fresh(); tapAt(5, "setup"); loopFor(800); tapAt(5, "n3box"); loopFor(200); CHECK(GetOtherValue((char *) "n4.val") == 0 && offPage == 1); loopFor(50);
    fresh(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["big"].val = 0x4C450007L; CHECK(GetOtherValue((char *) "big.val") == 0);
    // 36. A MARKER IN TWO PIECES while a write reads the wire in (most markers are read there): whole, not two junk words
    fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
    screen.emit(nowUs, { 'q', 9, 0 }); screen.emit(nowUs + 300, { 0x45, 0x4C, 0xFF, 0xFF, 0xFF, 0x66 }); screen.emit(nowUs + 900, { 9, 0xFF, 0xFF, 0xFF }); nowUs += 60;
    StashPendingEventBytes(); CHECK(!ScreenMarkAwaited && ScreenPageId == 9 && PendingCount == 0 && NEXTION.available() == 0 && ghosts.empty());
    // 37. A PIPE LINE with a page's markers and its number right behind it, read by the loop: the line is the line, and the
    //     three frames behind it are noted in their order (found by the storm: they were read on as the line's tail, and lost)
    fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
    { const char *l = "ldrctel 25:AABBCCDD\n"; std::vector<uint8_t> b(l, l + strlen(l));
      for (uint8_t x : { (uint8_t) 'q', (uint8_t) 9, (uint8_t) 0, (uint8_t) 0x44, (uint8_t) 0x4C, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 'q', (uint8_t) 9, (uint8_t) 0, (uint8_t) 0x45, (uint8_t) 0x4C, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0x66, (uint8_t) 9, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x);
      screen.emit(nowUs, b); nowUs += 1000; }
    CHECK(GetButtonPress() && !strcmp(TextIn, "ldrctel 25:AABBCCDD\n") && ScreenMarkAwaited != 0);
    CHECK(!GetButtonPress() && !ScreenMarkAwaited && !ScreenMarkOldPage && ScreenPageId == 9 && noMarks == 0);
    //     ... and behind a bare word that has no end of its own (the screen's keep-awake): all three noted, the word the word
    fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
    screen.emit(nowUs, { 'L', 'D', 'R', 'C', 'A', 'W', 'A', 'K', 'E', 'q', 9, 0, 0x44, 0x4C, 0xFF, 0xFF, 0xFF, 'q', 9, 0, 0x45, 0x4C, 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
    CHECK(GetButtonPress() && !strcmp(TextIn, "LDRCAWAKE") && !ScreenMarkAwaited && !ScreenMarkOldPage && ScreenPageId == 9);
    // 38. between the two markers ONLY "StCH" is let through - not the Sub-trim page's other word (its handler stores a box)
    { fresh(); ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = false;
      CHECK(DropUnconfirmedPress((const uint8_t *) "StEDIT", 6, true) && DropUnconfirmedPress((const uint8_t *) "St", 2, true) && DropUnconfirmedPress((const uint8_t *) "StC", 3, true) && !DropUnconfirmedPress((const uint8_t *) "StCH", 4, true)); }
    // 39. the One switch page's other two boxes with no answer: "Not used" (a front switch's) and "Reversed" stay as they were
    fresh(); tapAt(5, "switch3"); loopFor(600); SwitchEditNumber = 5; FrontSwitchUnused = 0; SwitchReversed[4] = false; screen.mute.insert("r0"); screen.mute.insert("c_revd");
    tapAt(5, "OK"); loopFor(9000); CHECK(words.size() == 1 && FrontSwitchUnused == 0 && !SwitchReversed[4] && lateReplies.size() == 1);   // (no answer is not "Not used", nor "Reversed")
    //     ... "Reversed" alone unanswered (the last box asked): as it was - AND SO IS ALL THE REST OF THE PAGE (the ninth review: the switch's
    //     jobs and its direction are taken together, or not at all - "Not used" answered, and was taken, with the direction left behind)
    fresh(); tapAt(5, "switch3"); loopFor(600); SwitchEditNumber = 5; FrontSwitchUnused = 1; SwitchReversed[4] = false; screen.mute.insert("c_revd");
    tapAt(5, "OK"); loopFor(9000); CHECK(words.size() == 1 && FrontSwitchUnused == 1 && !SwitchReversed[4] && lateReplies.size() == 1 && switchesAsAtFirst());
    //     ... every box answering, all of it is taken (the page's own choices: switch 5 is a front switch, used, now reversed)
    fresh(); tapAt(5, "switch3"); loopFor(600); SwitchEditNumber = 5; FrontSwitchUnused = 1; SwitchReversed[4] = false; screen.pages["OneSwitchView"].boxes["c_revd"].val = 1;
    tapAt(5, "OK"); loopFor(9000); CHECK(words.size() == 1 && FrontSwitchUnused == 0 && SwitchReversed[4] && lateReplies.empty());
    //     ... and AFTER AN ANSWER THAT NEVER CAME the boxes that follow are not asked at all (each was waited for two seconds: a page of
    //     nineteen boxes held the main loop for most of a minute on a screen that had stopped answering): Model options' OK, its first
    //     box unanswered - one wait, the model as it was, and the next press's boxes are asked again
    fresh(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("c1"); screen.pages["RXOptionsView"].boxes["n3"].val = 9;
    { const int gets0 = screen.gets; const uint64_t t0 = nowUs; tapAt(5, "OK"); while (saves.empty() && nowUs - t0 < 60000000ull) { LoopPass(); nowUs += 500; }
      CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && lateReplies.size() == 1 && nowUs - t0 < 3000000 && screen.gets - gets0 <= 3); }
    screen.mute.clear(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n3"].val = 9; tapAt(5, "OK"); loopFor(3000); CHECK(count(obeyed, 39) == 2 && TrimMultiplier == 9);
    fresh(); tapAt(5, "switch3"); loopFor(600); SwitchEditNumber = 5; FrontSwitchUnused = 1; SwitchReversed[4] = false;
    tapAt(5, "OK"); loopFor(5000); CHECK(words.size() == 1 && FrontSwitchUnused == 0 && SwitchReversed[4]);   // (answered - "Not used" no, "Reversed" yes: taken)
%(SCENES2)s
    // 21. A STORM OF TAPS: buttons of both pages tapped at random moments (a few ms to most of a second apart) on screens of
    //     every temper - quick or slow to read its commands, quick or slow to load a page, a tap during a load lost or falling
    //     through. Whatever the order: no code is ever obeyed on a page that is not its own, the model is never changed (every
    //     OK that is obeyed reads its own page), and the buttons are not dead.
    //     (the ninth review) ... AND ONCE MORE WITH THE SCREEN'S LOOP STANDING STILL NOW AND THEN - a fifth of a second to four seconds, one
    //     trial in four up to nine - on the real screen's port (its line "the loop is silent" in pieces with no end, or - every other trial,
    //     a screen from 1.11.198 on - in one piece with a newline). The marker's wait was given up after a second and a half: a tap made on
    //     the page a stalled screen still showed was then obeyed on the next (11 wrong pages and a model changed in 400 such trials).
    for (int pass = 0; pass < 2; ++pass)
    {
        uint32_t seed = pass ? 20261115u : 20261114u; auto rnd = [&](uint32_t n) { seed = seed * 1664525u + 1013904223u; return (seed >> 8) %% n; };
        stormSeed = 77 + pass; stormStalls = stormLongStalls = 0; long doubtedAll = 0, askedAll = 0;
        static const char *const names[] = { "setup", "OK", "leave", "read", "readtext", "busywrite", "two", "bg", "pipe", "OK", "setup", "leave", "switch3", "row3", "OK", "Help", "name", "picture",
                                             "n3box", "n4box", "kbOK", "kbOK", "n3box", "OK", "#restart" };
        long taps = 0, obeyedAll = 0, staleAll = 0, oks = 0, savesAll = 0, wrongAll = 0, changed = 0, missesAll = 0, keyboardsAll = 0, restartsAll = 0, offPageAll = 0, offPageAnswersAll = 0;
        long restartsHandledAll = 0, restartsLeft = 0, restartsMissed = 0; bool bothLost = false; uint64_t stormGapUs = 0;
        for (int trial = 0; trial < 400; ++trial)
        {
            fresh();
            if (pass) { screen.realUart = true; screen.shoutForm = (trial & 1) ? 198 : 197; screen.upMs = 4000 + rnd(15000000); stormLongest = (trial %% 4 == 3) ? 9000 : 4000; }
            screen.latencyUs = 200 + rnd(3) * rnd(30000); screen.loadUs = rnd(4) ? rnd(pass ? 320000 : 200000) : 0; screen.tapInLoadFallsThrough = rnd(2) != 0; screen.roundUs = rnd(3) ? 0 : rnd(80000);
            {   // (what the card's page files hold - a restarted screen shows these - is nothing like the model: were one of them taken, it would show)
                Page &d = screen.pages0["RXOptionsView"]; d.boxes["c1"].val = 0; d.boxes["n3"].val = 0; d.boxes["t10"].txt = "3.80"; d.boxes["t12"].txt = "0"; d.boxes["n0"].val = 0; d.boxes["n2"].val = 0;
                d.boxes["c0"].val = 0; d.boxes["n1"].val = 16; d.boxes["c2"].val = 0; d.boxes["c3"].val = 0; d.boxes["n4"].val = 5;
                Page &o = screen.pages0["OneSwitchView"]; for (auto &b : o.boxes) b.second.val = b.first == "r1" ? 1 : 0;
            }
            {   // (this trial's restarts: with a watchdog's record or without; and now and then the power itself (no word, no page put back), an older
                //  screen's bare word, one of the two signs lost, or both - then only an unframed press tells this board)
                const uint32_t kind = rnd(20); screen.bootRecord = rnd(2) ? rec : ""; screen.restartReason = screen.bootRecord.empty() ? 3 : 5;
                if (kind == 0) screen.restartReason = 1; else if (kind == 1) screen.restartPowerOnBytes = false; else if (kind == 2) screen.restartSaysWord = false;
                else if (kind == 3) { screen.restartPowerOnBytes = false; screen.restartSaysWord = false; } else if (kind == 4) { screen.restartReason = -1; screen.bootRecord.clear(); }
                bothLost = kind == 3;
                screen.prelude = chipStart(screen.restartReason);                  // (what the chip itself says first, at every restart)
                screen.powerOnUs = rnd(8) ? 1200000 + rnd(1800000) : 3000000 + rnd(15000000);   // (a start of 1.2 to 3 s; one in eight, up to 18 s)
                stormTele = rnd(2) != 0;
                if (pass) flyHook = stormHook; else if (stormTele) flyHook = storm_telemetry;   // (flying the model writes to the page from inside the waits)
                gapWatch = true; lastRadioUs = nowUs;
            }
            uint32_t at = 5;
            for (int k = 0; k < 30; ++k) { at += rnd(4) ? 3 + rnd(700) : 3 + rnd(40); const uint32_t pick = rnd(100); tapAt(at, pick == 0 ? names[24] : names[rnd(24)]); ++taps; }   // (a restart of the screen: one tap in a hundred)
            if (!pass) loopFor(at + 14000 + (uint32_t) (screen.powerOnUs / 1000));
            else
            {   // (stalls while the taps last and three seconds beyond; then the time for whatever is still to be answered - a stall of nine seconds, a start of eighteen)
                const uint64_t stallsEnd = nowUs + (uint64_t) (at + 3000) * 1000, until = stallsEnd + 26000000ull + screen.powerOnUs;
                stormNextStall = nowUs + 200000 + stormRnd(1500000);
                while (nowUs < until) { if (nowUs < stallsEnd) stormStallDue(); else stormNextStall = UINT64_MAX; loopFor(3); }
                stormNextStall = UINT64_MAX; flyHook = nullptr; doubtedAll += textDoubted; askedAll += screen.gets;
            }
            restartsHandledAll += restartsHandled; if (ScreenRestartSeen) ++restartsLeft;
            if (radioGapUs() > stormGapUs) stormGapUs = radioGapUs();
            if (show && radioGapUs() > 60000) fprintf(stderr, "   storm trial %%d: the radio silent for %%.1f ms\n", trial, radioGapUs() / 1000.0);
            if (screen.restarts && !restartsHandled && !bothLost) ++restartsMissed;
            int switchOks = 0; for (auto &w : words) switchOks += w == "SwitchesView1";
            obeyedAll += (long) obeyed.size() + switchOks; staleAll += stale; wrongAll += wrongPage; savesAll += (long) saves.size(); oks += count(obeyed, 39) + switchOks; missesAll += noMarks;
            if (!sameAsAtFirst() || !switchesAsAtFirst()) ++changed;
            keyboardsAll += screen.keyboards; restartsAll += screen.restarts; offPageAll += offPage; offPageAnswersAll += screen.offPageAnswers;
            if (wrongPage || !sameAsAtFirst() || !switchesAsAtFirst() || (int) saves.size() != count(obeyed, 39) + switchOks)
            {
                fprintf(stderr, "   storm trial %%d: wrong page %%d, model the same %%d, switches the same %%d, saves %%d, OKs obeyed %%d + %%d (latency %%u us, load %%u us, round %%u us, falls through %%d)\n", trial, wrongPage, (int) sameAsAtFirst(), (int) switchesAsAtFirst(), (int) saves.size(), count(obeyed, 39), switchOks, screen.latencyUs, screen.loadUs, screen.roundUs, (int) screen.tapInLoadFallsThrough);
                if (show) { std::vector<std::string> all = story; all.insert(all.end(), screen.events.begin(), screen.events.end()); std::sort(all.begin(), all.end(), [](const std::string &a, const std::string &b) { return atof(a.c_str()) < atof(b.c_str()); }); for (auto &l : all) fprintf(stderr, "      %%s\n", l.c_str()); }
            }
        }
        say("21. a storm%%s: %%ld taps, %%ld obeyed, %%ld not obeyed (their page had gone), %%ld OKs each saving once (%%ld saves), on the wrong page %%ld, models changed %%ld, markers never come %%ld; the screen's keyboard up %%ld times, restarted %%ld times, answered for a box it was not showing %%ld times (refused here %%ld times)\n", pass ? ", the screen's loop standing still now and then" : "", taps, obeyedAll, staleAll, oks, savesAll, wrongAll, changed, missesAll, keyboardsAll, restartsAll, offPageAnswersAll, offPageAll);
        if (pass) { say("    its loop stood still %%ld times (%%ld of them for longer than the marker's second and a half); text answers not believed %%ld\n", stormStalls, stormLongStalls, doubtedAll); CHECK(stormStalls > 500 && stormLongStalls > 200); }
        CHECK(wrongAll == 0 && changed == 0 && savesAll == oks);
        CHECK(keyboardsAll > (pass ? 100 : 200) && restartsAll > 20 && offPageAnswersAll > (pass ? 20 : 50));     // (the keyboard and the restarts were really among it)
        say("    the screen's restarts answered with the front page afresh: %%ld; left unanswered at a trial's end: %%ld; missed though the screen said so: %%ld\n", restartsHandledAll, restartsLeft, restartsMissed);
        CHECK(restartsHandledAll > 20 && restartsLeft == 0 && restartsMissed == 0);   // every restart the screen spoke of was answered
        say("    the radio's longest silence in the whole storm: %%.1f ms\n", stormGapUs / 1000.0);
        CHECK(stormGapUs <= 60000);                                               // ... and through it all the model was flown: never more than 60 ms without a packet (measured: under 30)
        CHECK(obeyedAll > taps / (pass ? 14 : 10) && staleAll > 50 && oks > 100);             // (the buttons work, the rule had work to do, and OK was obeyed often)
    }
    printf("test_stalepress: %%d checks, %%d failures\n", checks, fails);
    if (fails == 0) printf("ALL GOOD\n");
    return fails ? 1 : 0;
}
'''

SCENES = r"""
    // 3. THE GAP: the second tap lands after the page command has left this board and before the screen has read it (a screen
    //    busy for 40 ms) - too late to be purged, and still the old page's: it comes before the marker
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800); CHECK(screen.page == "RXOptionsView");
    screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "OK"; tapAt(5, "OK"); loopFor(4000);   // (the second: 10 ms after the first one's page command has left)
    report("3. the second tap in the gap, kept while the front page was being written");
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && stale == 1 && noMarks == 0 && !ScreenMarkAwaited);
    //    ... and at the last moment of the old page - the screen has had the page command's first bytes for a while, and reads
    //    it a tenth of a millisecond later (were the marker asked BEFORE the page command, the screen would have answered it by
    //    now, and this tap - the old page's - would come after it: found by the storm below)
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 40000 - 90; screen.tapAfterPageButton = "OK"; tapAt(5, "OK"); loopFor(4000);
    report("3b. the second tap at the old page's last moment");
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && stale == 0 && LoadPrintsLetGo == 1 && noMarks == 0 && !ScreenMarkAwaited);   // (after the first marker: let go without a word)
    // 4. ... the same gap, the code read by the loop itself (the function that sent the page command had gone back at once)
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 30000; screen.tapAfterPageButton = "OK"; tapAt(5, "leave"); loopFor(3000);
    report("4. the second tap in the gap, read by the loop");
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1078) == 1 && count(obeyed, 39) == 0 && saves.empty() && sameAsAtFirst() && stale == 1 && noMarks == 0 && !ScreenMarkAwaited);
    //    ... and a 24-bit code as well as a 7-bit one (the same button again, in the gap)
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 30000; screen.tapAfterPageButton = "leave"; tapAt(5, "leave"); loopFor(3000);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1078) == 1 && stale == 1 && staleCodes[0] == "004E0000" && !ScreenMarkAwaited);
    // 5. the new page's own taps are obeyed - 150 ms after its page command (it has been up for 60 ms), and later
    fresh(); tapAt(5, "setup"); loopFor(800); screen.tapAfterPageUs = 150000; screen.tapAfterPageButton = "setup"; tapAt(5, "OK"); loopFor(3000);
    CHECK(count(obeyed, 39) == 1 && count(obeyed, 1077) == 2 && screen.page == "RXOptionsView" && stale == 0);
    tapAt(700, "OK"); loopFor(4000); CHECK(count(obeyed, 39) == 2 && saves.size() == 2 && sameAsAtFirst() && screen.page == "FrontView" && stale == 0 && noMarks == 0);
    // 6. a page's own print as it comes up: a WORD passes (AdjustView's "ldrcadj", the typed name of InputsView), a CODE would
    //    not - it comes before the marker, as the old page's last codes do. No page of the card prints a code as it comes up
    //    (checked below, where the screen's project is beside this one) - also for a page that loads in no time
    for (int quick = 0; quick < 2; ++quick)
    {
        fresh(); screen.pages["FrontView"].loadPrint = { 'l', 'd', 'r', 'c', 'a', 'd', 'j' }; if (quick) screen.loadUs = 0;
        tapAt(5, "setup"); loopFor(800); tapAt(5, "OK"); loopFor(3000);
        CHECK(count(obeyed, 39) == 1 && words.size() == 1 && words[0] == "ldrcadj" && stale == 0 && !ScreenMarkAwaited);
        fresh(); screen.pages["FrontView"].loadPrint = { 0x00, 58, 0x00, 0x00 }; if (quick) screen.loadUs = 0;
        tapAt(5, "setup"); loopFor(800); tapAt(5, "OK"); loopFor(3000);
        CHECK(count(obeyed, 39) == 1 && count(obeyed, 1058) == 0 && stale == 0 && LoadPrintsLetGo == 1 && !ScreenMarkAwaited);
        // ... but the Sub-trim page's "StCH" (it clicks its first channel as it comes up; this board's "channel being edited" is put
        // back in step by it after the screen saver or Help) is obeyed there
        fresh(); { const char *w = "StCH"; screen.pages["FrontView"].loadPrint = std::vector<uint8_t>(w, w + 4); } if (quick) screen.loadUs = 0;
        tapAt(5, "setup"); loopFor(800); tapAt(5, "OK"); loopFor(3000);
        CHECK(count(obeyed, 39) == 1 && words.size() == 1 && words[0] == "StCH" && stale == 0 && LoadPrintsLetGo == 0 && !ScreenMarkAwaited);
    }
    //    ... and "StCH" as a PRESS (a channel's number tapped on the Sub-trim page): kept while the page's OK reads its boxes,
    //    or tapped before the screen has read the page command - the old page's, not obeyed (it writes two boxes of its page)
    fresh(); { const char *w = "StCH"; screen.pages["RXOptionsView"].buttons["channel"] = std::vector<uint8_t>(w, w + 4); }
    tapAt(5, "setup"); loopFor(800); tapAt(5, "OK"); tapAt(255, "channel"); loopFor(4000);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 39) == 1 && words.empty() && stale == 1 && staleCodes[0] == "StCH");
    fresh(); { const char *w = "StCH"; screen.pages["RXOptionsView"].buttons["channel"] = std::vector<uint8_t>(w, w + 4); } screen.latencyUs = 40000;
    tapAt(5, "setup"); loopFor(800); screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "channel"; tapAt(5, "leave"); loopFor(3000);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1078) == 1 && words.empty() && stale == 1 && LoadPrintsLetGo == 0);
    // 7. A SCREEN THAT DOES NOT SAY THE MARKER: for a second and a half after a page command its buttons are not obeyed (the
    //    price of the doubt), then they are; after three such, codes are only purged - which still cures the double tap - until
    //    a marker comes
    fresh(); screen.knowsSysGet = false;
    tapAt(5, "setup"); loopFor(100); CHECK(screen.page == "RXOptionsView" && ScreenMarkAwaited != 0);
    tapAt(300, "OK"); loopFor(700); CHECK(count(obeyed, 39) == 0 && stale == 1);            // within that time: not obeyed
    loopFor(500); CHECK(ScreenMarkAwaited != 0 && noMarks == 0);                            // (1.3 s: still awaited)
    loopFor(600); CHECK(!ScreenMarkAwaited && noMarks == 1 && ScreenMarkMisses == 1);       // the time is over, the wire empty: given up
    tapAt(5, "OK"); loopFor(1500); CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst());   // now it is
    loopFor(1800); CHECK(noMarks == 2 && ScreenMarkMisses == 2);
    tapAt(5, "setup"); loopFor(2200); CHECK(noMarks == 3 && ScreenMarkMisses == 3 && screen.page == "RXOptionsView");
    stale = 0; tapAt(5, "OK"); tapAt(255, "OK"); loopFor(3000);                              // the double tap, on a screen without markers
    report("7. two taps on OK, a screen that does not say the marker");
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 39) == 2 && saves.size() == 2 && sameAsAtFirst() && stale == 1);
    tapAt(100, "setup"); loopFor(600); CHECK(count(obeyed, 1077) == 3);                      // (no second's doubt any more: obeyed at once)
    stale = 0; tapAt(5, "leave"); tapAt(6, "OK"); nowUs += 10000; loopFor(1500);             // two buttons a thousandth apart, both on the wire before the loop comes round: the second is there, unread, when the first one's page command goes
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1078) == 1 && count(obeyed, 39) == 2 && saves.size() == 2 && sameAsAtFirst() && stale == 1 && screen.page == "FrontView");
    tapAt(5, "setup"); loopFor(600); CHECK(count(obeyed, 1077) == 4 && screen.page == "RXOptionsView");
    screen.knowsSysGet = true; tapAt(5, "OK"); loopFor(3000); CHECK(count(obeyed, 39) == 3 && ScreenMarkMisses == 0 && !ScreenMarkAwaited);   // a marker came: the rule is whole again
    // 8. the marker is noted wherever it is read, and never taken for a box's answer: by a get that follows the page command at
    //    once (a number, a text), by the loop
    fresh(); screen.latencyUs = 40000; tapAt(5, "read"); loopFor(1500);
    CHECK(count(obeyed, 1079) == 1 && readNumber == 6 && !ScreenMarkAwaited && !NextionTextMissed && lateReplies.empty());
    fresh(); screen.latencyUs = 40000; tapAt(5, "readtext"); loopFor(1500);
    CHECK(count(obeyed, 1080) == 1 && !strcmp(readText, "3.50") && !ScreenMarkAwaited && !NextionTextMissed && lateReplies.empty());
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800); tapAt(5, "leave"); loopFor(30); CHECK(ScreenMarkAwaited != 0);   // (back in the loop, the marker not yet come)
    loopFor(300); CHECK(!ScreenMarkAwaited && noMarks == 0 && words.empty() && ghosts.empty());
    tapAt(5, "setup"); loopFor(800); CHECK(count(obeyed, 1077) == 2);
    // 9. words always pass: the page's own touch word in the gap, and the pipe's line kept while the boxes were read
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "bg"; tapAt(5, "OK"); tapAt(255, "pipe"); loopFor(4000);
    CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && words.size() == 2 && words[0] == "ldrctel 25:AABBCCDD 26:EEFF0011\n" && words[1] == "UKRULES" && stale == 0);
    // 10. a box's number next to the markers' own is the box's number
    fresh(); tapAt(5, "setup"); loopFor(800); tapAt(5, "big"); loopFor(800); CHECK(count(obeyed, 1083) == 1 && readNumber == 0x4C430001UL && !NextionTextMissed);
    // 11. TakeScreenMark by itself: the first marker says "what comes now is no longer the old page's", the second ends the wait
    //     (and, should the first have been lost, does both); an earlier page command's markers are let go and end nothing; a
    //     number that is no marker is no marker; and one that comes after its wait was given up says the screen can
    {
        fresh(); ScreenMarkCount = 7; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 7; ScreenMarkOldPage = true; ScreenMarkMisses = 0;
        const uint8_t olderA[5] = { 'q', 6, 0, 0x44, 0x4C }, olderB[5] = { 'q', 6, 0, 0x45, 0x4C }, first[5] = { 'q', 7, 0, 0x44, 0x4C }, second[5] = { 'q', 7, 0, 0x45, 0x4C },
                      box[5] = { 'q', 7, 0, 0, 0 }, above[5] = { 'q', 7, 0, 0x48, 0x4C }, below[5] = { 'q', 7, 0, 0x43, 0x4C };
        CHECK(TakeScreenMark(olderA) && TakeScreenMark(olderB) && ScreenMarkOldPage && ScreenMarkAwaited == (SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 7));
        CHECK(!TakeScreenMark(box) && !TakeScreenMark(above) && !TakeScreenMark(below) && ScreenMarkOldPage && ScreenMarkAwaited != 0);
        CHECK(ScreenPageUnconfirmed());
        CHECK(TakeScreenMark(first) && !ScreenMarkOldPage && ScreenMarkAwaited != 0 && ScreenPageUnconfirmed());
        CHECK(TakeScreenMark(second) && ScreenMarkAwaited == 0 && !ScreenPageUnconfirmed());
        ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 7; ScreenMarkOldPage = true; CHECK(TakeScreenMark(second) && !ScreenMarkOldPage && ScreenMarkAwaited == 0);   // (the first lost)
        ScreenMarkMisses = 3; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 7; CHECK(!ScreenPageUnconfirmed());
        ScreenMarkAwaited = 0; CHECK(TakeScreenMark(second) && ScreenMarkMisses == 0);
        ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 7; CHECK(ScreenPageUnconfirmed());
        const uint8_t press[4] = { 0xA7, 0, 0, 0 }, press24[4] = { 0, 10, 0, 0 }, word[4] = { 'Y', 'e', 's', 0 };
        CHECK(IsButtonCode(press, 4) && IsButtonCode(press24, 4) && !IsButtonCode(word, 3) && !IsButtonCode(press, 0));
        // what is dropped when: until the first marker every press, and it is said; between the two, every press but "StCH", unsaid
        ScreenMarkOldPage = true; stale = 0; LoadPrintsLetGo = 0;
        CHECK(DropUnconfirmedPress(press, 4, true) && DropUnconfirmedPress((const uint8_t *) "StCH", 4, true) && DropUnconfirmedPress((const uint8_t *) "SwitchesView1", 13, true) && stale == 3 && LoadPrintsLetGo == 0);
        CHECK(!DropUnconfirmedPress((const uint8_t *) "UKRULES", 7, true) && !DropUnconfirmedPress((const uint8_t *) "SwitchesView1", 13, false) && !DropUnconfirmedPress((const uint8_t *) "ldrcadj", 7, true));
        ScreenMarkOldPage = false;
        CHECK(DropUnconfirmedPress(press, 4, true) && DropUnconfirmedPress((const uint8_t *) "SwitchesView1", 13, true) && !DropUnconfirmedPress((const uint8_t *) "StCH", 4, true) && !DropUnconfirmedPress((const uint8_t *) "StCH", 4, false) && stale == 3 && LoadPrintsLetGo == 2);
        ScreenMarkAwaited = 0; CHECK(!DropUnconfirmedPress(press, 4, true) && !DropUnconfirmedPress((const uint8_t *) "SwitchesView1", 13, true));
    }
    // 12. what is a page command: "page X" alone or among commands sent together - not a text with the word in it
    CHECK(IsPageCommand("page FrontView") && IsPageCommand("vis b1,0\xFF\xFF\xFFpage PopupView") && !IsPageCommand("t0.txt=\"Next page here\"") && !IsPageCommand("pageX") && !IsPageCommand("vis page ,1"));
    fresh(); tapAt(5, "setup"); loopFor(800);
    { const int marks = ScreenMarkCount; const uint8_t press[4] = { 0x00, 10, 0x00, 0x00 }; PendingPush(press, 4, true);
      TextWithPageInIt(); CHECK(PendingCount == 1 && ScreenMarkCount == marks && !ScreenMarkAwaited); PendingCount = 0; PendingEventLen = 0; }   // (a text with "page " in it purges nothing and asks no marker)
    // 13. a page command sent while a get waits for its answer (from the wait that flies the model): nothing is drained then,
    //     and the old page's code still on the wire is not obeyed when it is read
    fresh(); tapAt(5, "setup"); loopFor(800); tapAt(1, "OK"); nowUs += 5000;
    NextionGetPending = true; LeaveQuick(); NextionGetPending = false;
    CHECK(PendingCount == 0 && NEXTION.available() > 0);                    // (still on the wire)
    loopFor(1500); CHECK(count(obeyed, 39) == 0 && saves.empty() && stale == 1 && !ScreenMarkAwaited && noMarks == 0);
    // 14. the wait is given up only with the wire EMPTY: three seconds of other work after the page command, the wire unread -
    //     the old page's code, the marker and the new page's tap are all there, and are told apart by their order
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "OK"; screen.tap2AfterPageUs = 2000000; screen.tap2AfterPageButton = "setup"; tapAt(5, "busy"); loopFor(5000);
    report("14. three seconds unread after the page command");
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1082) == 1 && count(obeyed, 39) == 0 && count(obeyed, 1077) == 2 && stale == 1 && noMarks == 0 && saves.empty() && sameAsAtFirst());
    //     ... the same, the wire first read in by a write (the kept frames' way) after the three seconds
    fresh(); screen.latencyUs = 40000; tapAt(5, "setup"); loopFor(800);
    screen.tapAfterPageUs = 10000; screen.tapAfterPageButton = "OK"; screen.tap2AfterPageUs = 2000000; screen.tap2AfterPageButton = "setup"; tapAt(5, "busywrite"); loopFor(5000);
    CHECK(screen.tapsOnNothing == 0 && count(obeyed, 1085) == 1 && count(obeyed, 39) == 0 && count(obeyed, 1077) == 2 && stale == 1 && noMarks == 0 && saves.empty() && sameAsAtFirst());
    // 15. what this does NOT do (the screen's matter): a tap made while the new page loads falls through onto the new page's own
    //     button. It is that page's press - obeyed, on its own page, which is read as it stands: here the model's own values
    fresh(); screen.tapInLoadFallsThrough = true; screen.tapAfterPageUs = 30000; screen.tapAfterPageButton = "OK"; tapAt(5, "setup"); loopFor(4000);
    report("15. a tap that falls through onto the new page's OK");
    CHECK(count(obeyed, 1077) == 1 && count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && stale == 0);
    // 16. the kept frames at a page command: codes go, words stay in their order (PurgeKeptPresses by itself)
    {
        fresh(); const uint8_t c1[4] = { 0xA7, 0, 0, 0 }, c2[12] = { 0, 14, 0, 0, 0x90, 1, 0, 0, 0, 3, 0, 0 };
        PendingPush(c1, 4, true); PendingPush((const uint8_t *) "UKRULES", 7, true); PendingPush(c2, 12, true); PendingPush((const uint8_t *) "ldrcrep 12 200 01\n", 18, false); PendingPush(c1, 4, false);
        CHECK(PendingCount == 5 && PendingEventLen == 45);
        PurgeKeptPresses();
        CHECK(PendingCount == 2 && PendingEventLen == 25 && PendingLens[0] == 7 && PendingFramedFlags[0] && PendingLens[1] == 18 && !PendingFramedFlags[1] && !memcmp(PendingEvent, "UKRULESldrcrep 12 200 01\n", 25) && PendingEvent[25] == 0 && stale == 3);
        CHECK(GetButtonPress() && !strcmp(TextIn, "UKRULES") && TextInFramed); CHECK(GetButtonPress() && !strcmp(TextIn, "ldrcrep 12 200 01\n") && !TextInFramed && PendingCount == 0);
        PurgeKeptPresses(); CHECK(PendingCount == 0 && PendingEventLen == 0);       // (nothing kept: nothing to do)
    }
"""
FRESH_MORE = ''
SCENES2 = r'''
    // ================= AFTER THE SIXTH REVIEW (14 Nov 2026) =================
    {
        const int parts = (int) ((rec.size() + 279) / 280);
        const std::vector<uint8_t> powerOn = { 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x88, 0xFF, 0xFF, 0xFF };
        auto bytes = [](const char *w) { return std::vector<uint8_t>(w, w + strlen(w)); };
        auto tellAll = []() { std::vector<std::string> all = story; all.insert(all.end(), screen.events.begin(), screen.events.end()); std::sort(all.begin(), all.end(), [](const std::string &a, const std::string &b) { return atof(a.c_str()) < atof(b.c_str()); }); for (auto &l : all) printf("      %s\n", l.c_str()); };
        // 40. THE SCREEN RESTARTS UNDER AN OK, AS THE REAL SCREEN DOES IT - after its watchdog with the record of what it was doing
        //     (a thousand characters, in parts), and by itself without one. The word "FrontView" was glued to the record and never
        //     obeyed; then every code button was dead until the power went off. Now: nothing of the page file is saved, the front
        //     page is drawn afresh ONCE, when the screen has finished speaking - every part of its record in the log - the screen
        //     frames again, and its buttons work
        for (int withRecord = 1; withRecord >= 0; --withRecord)
        {
            fresh(); screen.bootRecord = withRecord ? rec : ""; screen.restartReason = withRecord ? 5 : 3;
            tapAt(5, "setup"); loopFor(800);
            screen.pages0["RXOptionsView"].boxes["n1"].val = 16; screen.pages0["RXOptionsView"].boxes["c0"].val = 0; screen.pages0["RXOptionsView"].boxes["t10"].txt = "3.80";
            tapAt(5, "OK"); tapAt(260, "#restart"); loopFor(20000);
            report(withRecord ? "40. the screen's watchdog restarted it under Model options' OK (with its record)" : "40. the screen restarted by itself under Model options' OK");
            if (show) tellAll();
            CHECK(screen.restarts == 1 && count(obeyed, 39) == 1 && saves.size() == 1 && sameAsAtFirst() && MotorChannel == 4 && UseMotorKill);
            CHECK(restartsHandled == 1 && lastRestartReason == (withRecord ? 5 : 3) && !ScreenRestartSeen && screen.page == "FrontView" && CurrentView == FRONTVIEW && warmups == 1 && frontReasons.size() == 1);
            CHECK(screen.frames && ScreenFramesBursts && words.empty() && (int) screenLogLines.size() == (withRecord ? parts : 0));
            CHECK(ScreenSession != 0 && screen.sys["ldrcup"] == (long) ScreenSession);   // (the screen has been told this session's number again)
            if (withRecord) CHECK(frontReasons[0].find("rst=5") != std::string::npos && screenLogLines[0].rfind("LDRCLOG before the restart", 0) == 0 && screenLogLines[parts - 1].rfind("LDRCLOG (cont) ", 0) == 0);
            const int before = count(obeyed, 1077); ghosts.clear(); tapAt(5, "setup"); loopFor(1500);
            CHECK(count(obeyed, 1077) == before + 1 && screen.page == "RXOptionsView" && ghosts.empty());
            tapAt(5, "OK"); loopFor(3000); CHECK(count(obeyed, 39) == 2 && saves.size() == 2 && sameAsAtFirst());
        }
        // 41. THE MODELS PAGE asks for its two lists twice a second (the REAL CheckModelName): a screen that restarts there comes
        //     back with its list on row 0, and MODEL 1 WAS LOADED BY ITSELF. At fifty moments of the poll's half second, with the
        //     record and without: the model in use stays the model in use, no model is read from the card, the front page comes
        for (int withRecord = 1; withRecord >= 0; --withRecord)
        {
            int loadedByItself = 0, answered = 0, moments = 0;
            for (int offset = 0; offset < 500; offset += 10)
            {
                fresh(); screen.bootRecord = withRecord ? rec : ""; screen.restartReason = withRecord ? 5 : 3;
                tapAt(5, "models"); loopForModels(2000);
                CHECK(ModelNumber == 4 && modelsRead.empty() && ScreenPageId == 15 && CurrentView == MODELSVIEW);
                tapAt(100 + offset, "#restart"); loopForModels(30000);
                ++moments; loadedByItself += (ModelNumber != 4 || !modelsRead.empty()); answered += restartsHandled == 1 && CurrentView == FRONTVIEW && screen.page == "FrontView" && screen.frames;
                if (show && (ModelNumber != 4 || !modelsRead.empty() || restartsHandled != 1)) { printf("   41, %d ms: model %u, read %u, restarts answered %d\n", offset, (unsigned) ModelNumber, (unsigned) modelsRead.size(), restartsHandled); tellAll(); }
            }
            say("41. the screen restarted on the Models page (%s), %d moments: a model loaded by itself %d times; the front page afresh %d times\n", withRecord ? "its watchdog, with the record" : "by itself", moments, loadedByItself, answered);
            CHECK(loadedByItself == 0 && answered == moments);
        }
        //     ... and on a screen that keeps nothing of what is said to it while it starts
        fresh(); screen.restartKeeps = false; screen.bootRecord = rec; tapAt(5, "models"); loopForModels(2000); tapAt(130, "#restart"); loopForModels(30000);
        CHECK(ModelNumber == 4 && modelsRead.empty() && restartsHandled == 1 && CurrentView == FRONTVIEW && screen.page == "FrontView");
        //     ... A BOX ASKED WHILE THE SCREEN STARTS is kept by it and answered when its loop begins - here a second and a half after
        //     its word, when the front page is already being drawn afresh: this board waits until the screen says the session's new
        //     number back, so that late answer (the page file's value) is let go, and is not taken for the answer to the next
        //     question - "is the model's picture on the card?"
        fresh(); frontAsksPicture = true; screen.aliveLateUs = 1500000; tapAt(5, "setup"); loopFor(800); screen.pages0["RXOptionsView"].boxes["n3"].val = 0;
        tapAt(5, "#restart"); loopFor(700); NextionTextMissed = false; CHECK(GetValue((char *) "n3") == 65535 && NextionTextMissed);
        loopFor(20000);
        CHECK(restartsHandled == 1 && picMissing == 0 && picThere == 1 && screen.page == "FrontView" && CurrentView == FRONTVIEW && !ScreenRestartSeen && screen.sys["ldrcup"] == (long) ScreenSession);
        //     ... and the same when MORE was asked while the screen started, a page command among it: a box, then the front page with
        //     its two picture questions - all kept by the screen, and answered one after the other when its loop begins at last (six
        //     and a half seconds late), the page's load between them. Every one of those late answers is let go before the front page
        //     is drawn afresh: its own picture questions get their own answers
        fresh(); frontAsksPicture = true; screen.aliveLateUs = 6500000; screen.restartReason = 3;
        tapAt(5, "setup"); loopFor(800); screen.pages0["RXOptionsView"].boxes["n3"].val = 7;
        tapAt(5, "#restart"); loopFor(700); CHECK(GetValue((char *) "n3") == 65535); GotoFrontView(); CHECK(picMissing == -1 && picThere == -1);   // (a box, then the front page with its two questions: no answer to any - the screen is starting)
        loopFor(25000);
        if (show) { printf("   41d: pictures %d %d, restarts answered %d, page %s\n", picMissing, picThere, restartsHandled, screen.page.c_str()); tellAll(); }
        CHECK(restartsHandled == 1 && picMissing == 0 && picThere == 1 && screen.page == "FrontView" && CurrentView == FRONTVIEW && sameAsAtFirst() && !ScreenRestartSeen);
        // 42. THE SCREEN'S POWER WENT AND CAME BACK (its supply dipped while this board ran on; or it was the slower of the two to start):
        //     it says its power-on bytes and no word, and puts no page back. From those bytes NOTHING IS ASKED of it - no box has an
        //     answer, a system variable neither, a Rotorflight page's look before its boxes does not wait - and as soon as it has said
        //     the number back the front page is drawn afresh (it stayed dark until the power was switched off and on)
        fresh(); screen.restartReason = 1; tapAt(5, "setup"); loopFor(800); tapAt(5, "#restart"); loopFor(2200);
        CHECK(ScreenRestartSeen && restartsHandled == 0 && screen.page == "NoPage");
        { const int gets0 = screen.gets; NextionTextMissed = false; CHECK(GetValue((char *) "n3") == 65535 && NextionTextMissed); char tx[20] = "x"; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && GetOtherValue((char *) "n4.val") == 0);
          CHECK(GetSysValue("ldrcmb") == 65535);
          { const uint64_t t0 = nowUs; RfGatherStart(); CHECK(nowUs - t0 < 2000 && !NextionSettledOk); }
          nowUs += 5000; screen.run(nowUs); CHECK(screen.gets == gets0); }
        loopFor(1500);
        CHECK(restartsHandled == 1 && lastRestartReason == -2 && !ScreenRestartSeen && screen.page == "FrontView" && CurrentView == FRONTVIEW && screen.frames && frontReasons.size() == 1 && frontReasons[0].find("with no word") != std::string::npos);
        // 43. AT THIS BOARD'S OWN START the screen's power-on bytes are the common power-on's: nothing to answer. Afterwards they mean the
        //     screen has started again - read in by a write, read by the loop, and behind rubbish. They are never a press; what stands
        //     behind them in the same read is neither lost nor left with their length; and a button's code 8 from an older screen
        //     (88 00 00 00: no end of its own, here glued to a page's marker) is a button's code, not those bytes
        fresh(); ScreenStartupOver = false; screen.emit(nowUs, powerOn); nowUs += 1000; StashPendingEventBytes(); CHECK(!ScreenRestartSeen && PendingCount == 0);
        fresh(); ScreenStartupOver = false; screen.emit(nowUs, powerOn); nowUs += 1000; loopFor(30); CHECK(!ScreenRestartSeen && restartsHandled == 0 && obeyed.empty() && ghosts.empty());
        fresh(); screen.emit(nowUs, powerOn); nowUs += 1000; StashPendingEventBytes(); CHECK(ScreenRestartSeen && ScreenRestartReason == -2 && PendingCount == 0);
        fresh(); holdCatchUp = true; screen.emit(nowUs, powerOn); nowUs += 1000; loopFor(30); CHECK(ScreenRestartSeen && ScreenRestartReason == -2 && obeyed.empty() && ghosts.empty());
        for (int way = 0; way < 2; ++way)
        {
            fresh(); holdCatchUp = true; { std::vector<uint8_t> b = { 0x8F, 0x33, 0xF8, 0x00, 0x1C }; b.insert(b.end(), powerOn.begin(), powerOn.end()); screen.emit(nowUs, b); } nowUs += 1000;
            if (way) StashPendingEventBytes(); else loopFor(30);
            CHECK(ScreenRestartSeen && obeyed.empty());
        }
        fresh(); holdCatchUp = true; { std::vector<uint8_t> b = powerOn; const auto w = bytes("UKRULES"); b.insert(b.end(), w.begin(), w.end()); screen.emit(nowUs, b); } nowUs += 1000;
        CHECK(GetButtonPress() && !strcmp(TextIn, "UKRULES") && ScreenRestartSeen && !TextInIsGenuine() && ghosts.empty());   // (the power-on bytes are taken out, the word is the word - and while the restart
                                                                                                                                  //  is noted it is let go, without a line: the eighth review)
        //     ... of the screen's own words only those pass, those seconds, that main.cpp answers before it looks for any page's word
        for (const char *w : { "LDRCLOG core 1 (the loop's) silent for 213 ms", "LDRCWHO", "LDRCAWAKE", "Guru Meditation Error: Core 1 panic'ed" })
        { fresh(); holdCatchUp = true; ScreenRestartSeen = true; screen.emit(nowUs, bytes(w)); nowUs += 1000; CHECK(GetButtonPress() && TextInIsGenuine()); }
        for (const char *w : { "UKRULESSwitchesView1", "TIME=1763200000SwitchesView1", "ldrcpipe=2SwitchesView1", "ldrctel 25:AABBCCDD\n", "ldrcrep 12 200 0102\n" })
        { fresh(); holdCatchUp = true; ScreenRestartSeen = true; screen.emit(nowUs, bytes(w)); nowUs += 1000; CHECK(GetButtonPress() && !TextInIsGenuine() && ghosts.empty()); }
        //     ... and from a screen that frames, the blank code with a fourth byte (the chip's own text; the head of its power-on bytes)
        //     is nothing - it counted as a touch, and kept the screen saver away. With no fourth byte it is "nothing to obey", as ever
        fresh(); screen.emit(nowUs, { 0x00, 0x00, 0x00, 0x80 }); nowUs += 1000; CHECK(GetButtonPress() && !TextInIsGenuine() && ghosts.empty());
        fresh(); memset(TextIn, 0, 8); TextInFramed = false; CHECK(TextInIsGenuine());
        fresh(); ScreenFramesBursts = false; screen.emit(nowUs, { 0x00, 0x00, 0x00, 0x80 }); nowUs += 1000; CHECK(GetButtonPress() && TextInIsGenuine());   // (an older screen, which frames nothing: as it always was)
        fresh(); screen.frames = false; screen.canFrame = false; ScreenFramesBursts = false; ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = false; ScreenMarkAskedMs = millis();
        screen.emit(nowUs, { 0x88, 0x00, 0x00, 0x00, 'q', 9, 0, 0x45, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 1000; StashPendingEventBytes();
        CHECK(!ScreenRestartSeen && !ScreenMarkAwaited);
        // 44. THE WORD, in every way it comes: alone, from an older screen that gives no reason; in a get's wait, glued to twelve
        //     hundred characters of record and to the answer behind them (that lump was too long to keep, and all of it went); behind
        //     a code that the page put back printed as it came up; at the end of a wait that got no answer; with a page's marker
        //     glued behind it (both are noted). It is noted each time, and never kept as a word. And the record's own text may NAME
        //     the front page (among "the last commands"): no restart
        fresh(); holdCatchUp = true; screen.emit(nowUs, bytes("FrontView")); nowUs += 1000; loopFor(5); CHECK(ScreenRestartSeen && ScreenRestartReason == -1 && words.empty() && PendingCount == 0);
        fresh(); { std::string lump = "FrontView rst=5LDRCLOG " + rec; std::vector<uint8_t> b(lump.begin(), lump.end()); for (uint8_t x : { (uint8_t) 'q', (uint8_t) 5, (uint8_t) 0, (uint8_t) 0, (uint8_t) 0, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x);
          screen.emit(nowUs, b); nowUs += 20000; uint16_t k = 0; NextionReplyWaitMs = 100;
          CHECK(CollectReply('q', k) && k == 8 && ScreenRestartSeen && ScreenRestartReason == 5 && PendingCount == 1 && PendingLens[0] == 400 && !memcmp(PendingEvent, "LDRCLOG before", 14)); }
        fresh(); holdCatchUp = true; { std::vector<uint8_t> b = { 0xC1, 0x00, 0x00, 0x00 }; const auto w = bytes("FrontView rst=6"); b.insert(b.end(), w.begin(), w.end()); screen.emit(nowUs, b); } nowUs += 1000; loopFor(5);
        CHECK(ScreenRestartSeen && ScreenRestartReason == 6 && obeyed.empty() && ghosts.empty());
        fresh(); { std::vector<uint8_t> b = { 0xC1, 0x00, 0x00, 0x00 }; const auto w = bytes("FrontView rst=6"); b.insert(b.end(), w.begin(), w.end()); screen.emit(nowUs + 50000, b); uint16_t k = 0; NextionReplyWaitMs = 100;
          CHECK(!CollectReply('q', k) && ScreenRestartSeen && ScreenRestartReason == 6 && PendingCount == 0); }
        fresh(); holdCatchUp = true; ScreenMarkCount = 9; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | 9; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis();
        { auto b = bytes("FrontView rst=5"); for (uint8_t x : { (uint8_t) 'q', (uint8_t) 9, (uint8_t) 0, (uint8_t) 0x45, (uint8_t) 0x4C, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x); screen.emit(nowUs, b); } nowUs += 1000; loopFor(5);
        CHECK(ScreenRestartSeen && ScreenRestartReason == 5 && !ScreenMarkAwaited);
        fresh(); screen.emit(nowUs, bytes("LDRCLOG the last commands: [900] page FrontView [800] t0.txt=x")); nowUs += 1000; loopFor(5); CHECK(!ScreenRestartSeen && restartsHandled == 0 && screenLogLines.size() == 1 && words.empty());
        //     ... and a TEXT BOX may hold those very words (the log viewer's): its answer, come late and read by the loop or read in by a
        //     write, is no restart - but the word behind such an answer is one
        for (int way = 0; way < 2; ++way)
        {
            fresh(); { std::vector<uint8_t> b = bytes("pthe screen said FrontView rst=5 at noon"); b.insert(b.end(), 3, 0xFF); screen.emit(nowUs, b); } nowUs += 1000;
            if (way) StashPendingEventBytes(); else loopFor(5);
            CHECK(!ScreenRestartSeen && restartsHandled == 0 && PendingCount == 0);
            fresh(); holdCatchUp = true; { std::vector<uint8_t> b = bytes("pFrontView"); b.insert(b.end(), 3, 0xFF); const auto w = bytes("FrontView rst=4"); b.insert(b.end(), w.begin(), w.end()); screen.emit(nowUs, b); } nowUs += 1000;
            if (way) StashPendingEventBytes(); else loopFor(5);
            CHECK(ScreenRestartSeen && ScreenRestartReason == 4);
        }
        //     ... the signs of ONE restart in any order: the reason the word gave is not replaced by "its power-on bytes" (a second
        //     start's) nor by a word without one - but by a later word's reason it is; and each sign has the screen told, and asked, afresh
        fresh(); NoteScreenRestart(-2); CHECK(ScreenRestartSeen && ScreenRestartReason == -2); NoteScreenRestart(5); CHECK(ScreenRestartSeen && ScreenRestartReason == 5);
        NoteScreenRestart(-2); CHECK(ScreenRestartReason == 5); NoteScreenRestart(-1); CHECK(ScreenRestartReason == 5); NoteScreenRestart(6); CHECK(ScreenRestartSeen && ScreenRestartReason == 6);
        ScreenRestartSeen = false; NoteScreenRestart(-1); NoteScreenRestart(-2); CHECK(ScreenRestartReason == -1); ScreenRestartSeen = false; NoteScreenRestart(-2); NoteScreenRestart(-1); CHECK(ScreenRestartReason == -1);
        ScreenSaidSession = true; ScreenToldMs = 5; NoteScreenRestart(5); CHECK(!ScreenSaidSession && ScreenToldMs == 0); ScreenRestartSeen = false;
        { const uint8_t a[] = "FrontView rst=12 and more", b[] = "FrontView rst=", c[] = "FrontViewX", d[] = "xFrontView", e[] = "xxFrontView rst=7";
          CHECK(RestartWordAt(a, 25) == 0 && RestartReasonAt(a, 25) == 12 && RestartWordAt(b, 14) == 0 && RestartReasonAt(b, 14) == -1 && RestartWordAt(c, 10) == 0 && RestartReasonAt(c, 10) == -1 && RestartWordAt(d, 10) == -1 && RestartWordAt(e, 17) == 2 && RestartReasonAt(e + 2, 15) == 7 && RestartWordAt(a, 8) == -1); }
        // 45. A QUESTION BOX THAT WAITS when the screen restarts (the REAL GetYesOrNo): the screen no longer shows the question - the
        //     box is closed as "No", and the front page comes. (It waited on, obeying whatever was tapped; and the answer to a LATER
        //     question was taken for this one's.) A box on a screen that does not restart is answered as ever
        fresh(); tapAt(5, "setup"); loopFor(800); SendCommand((char *) "page PopupView"); SendText((char *) "Dialog", (char *) "Delete this model?");
        tapAt(300, "#restart"); GetYesOrNo(); CHECK(screen.restarts == 1 && Confirmed[0] == 'N' && questionsClosed == 1 && ModalWaits == 0);
        loopFor(8000); CHECK(restartsHandled == 1 && screen.page == "FrontView" && CurrentView == FRONTVIEW && obeyed.size() == 1);
        fresh(); tapAt(5, "setup"); loopFor(800); SendCommand((char *) "page PopupView"); SendText((char *) "Dialog", (char *) "Delete this model?");
        tapAt(300, "yes"); GetYesOrNo(); CHECK(Confirmed[0] == 'Y' && questionsClosed == 0 && ModalWaits == 0);
        // 46. ALL ITS SIGNS LOST (nothing told this board that the screen restarted): the screen shows the page as its card has it, and
        //     frames nothing. Its buttons are NOT OBEYED - a code is not, and nor is a WORD that comes bare (the One switch page's OK: its
        //     routine would have read the card's choices). Nothing is read from such a page, nothing saved; and NOTHING WAITS (the
        //     seventh review: an asking stood here, two seconds in the main loop).
        //     (The ninth review: its buttons then stayed unanswered until this board was switched off and on. Now the first of them makes
        //     this board ask the screen for its session's number - "say this back", for which nothing waits: it has forgotten it, and the
        //     front page is drawn afresh.)
        fresh(); screen.restartPowerOnBytes = false; screen.restartSaysWord = false; tapAt(5, "setup"); loopFor(800);
        screen.pages0["RXOptionsView"].boxes["n1"].val = 16; screen.pages0["RXOptionsView"].boxes["c0"].val = 0; screen.pages0["RXOptionsView"].boxes["n3"].val = 0;
        tapAt(5, "#restart"); loopFor(4000); CHECK(!ScreenRestartSeen && restartsHandled == 0 && !screen.frames && screen.page == "RXOptionsView");
        { const int gets0 = screen.gets; gapWatch = true; lastRadioUs = nowUs; tapAt(5, "OK"); loopFor(3000);
          say("46. every sign lost, the card's OK tapped: obeyed %d, saves %d, ghosts %d, the longest pass %.1f ms, the radio's longest silence %.1f ms, answered off the page %d, asked %d\n", count(obeyed, 39), (int) saves.size(), (int) ghosts.size(), maxPassUs / 1000.0, radioGapUs() / 1000.0, screen.offPageAnswers, screen.gets - gets0);
          CHECK(count(obeyed, 39) == 0 && saves.empty() && sameAsAtFirst() && ghosts.size() == 1 && maxPassUs < 60000 && radioGapUs() < 5000 && screen.offPageAnswers == 0 && screen.gets > gets0);   // (the longest pass is the one that draws the front page afresh: 23 ms - the asking itself waits for nothing)
          CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && !ScreenRestartSeen && !ScreenAnswerOwed && screen.page == "FrontView" && CurrentView == FRONTVIEW); }
        fresh(); screen.restartPowerOnBytes = false; screen.restartSaysWord = false; tapAt(5, "switch3"); loopFor(800);
        { Page &o = screen.pages0["OneSwitchView"]; for (auto &b : o.boxes) b.second.val = b.first == "r1" ? 1 : 0; }
        tapAt(5, "#restart"); loopFor(4000);
        { const int gets0 = screen.gets; tapAt(5, "OK"); loopFor(6000);
          CHECK(words.empty() && switchesAsAtFirst() && saves.empty() && txSaves == 0 && ghosts.size() == 1 && ghosts[0].rfind("an unframed word", 0) == 0 && screen.gets > gets0);
          CHECK(restartsFoundByAsking == 1 && restartsHandled == 1 && lastRestartReason == -3 && screen.page == "FrontView"); }
        //     ... and A PAGE'S WORD PRINTED BETWEEN THE RESTART'S ANSWER AND THE SCREEN'S FRAMING AGAIN (the screen is 40 ms behind; the
        //     One switch page's OK is tapped a thousandth of a second after the front page's command has left this board): bare, on a
        //     page of the card - not obeyed. (This board used to forget at the restart that the screen frames: such a word was obeyed,
        //     and its routine read the front page.)
        fresh(); screen.latencyUs = 40000; tapAt(5, "switch3"); loopFor(900);
        { Page &o = screen.pages0["OneSwitchView"]; for (auto &b : o.boxes) b.second.val = b.first == "r1" ? 1 : 0; }
        tapAt(5, "#restart"); loopFor(2000); screen.tapAfterPageUs = 1000; screen.tapAfterPageButton = "OK"; ghosts.clear(); loopFor(9000);
        CHECK(screen.tapsOnNothing == 0 && restartsHandled == 1 && words.empty() && wrongPage == 0 && switchesAsAtFirst() && saves.empty() && txSaves == 0 && ghosts.size() == 1 && ghosts[0].rfind("an unframed word", 0) == 0 && screen.page == "FrontView");
        //     ... an unframed code from a screen that frames and has NOT restarted (a split tail): dropped, said - the screen asked once
        //     for its session's number (and the number behind it): the same screen, and that is all
        fresh(); tapAt(5, "setup"); loopFor(800);
        { const int gets0 = screen.gets; screen.emit(nowUs, { 0xA7, 0x00, 0x00, 0x00 }); nowUs += 1000; loopFor(1500);
          CHECK(count(obeyed, 39) == 0 && ghosts.size() == 1 && !ScreenRestartSeen && restartsHandled == 0 && restartsFoundByAsking == 0 && owedCaughtUp == 1 && screen.page == "RXOptionsView" && screen.gets == gets0 + 2); }
        //     ... the screen's own words always pass, bare as they come; a page's word bare from a screen that frames does not
        { fresh(); const char *const own[] = { "LDRCAWAKE", "LDRCLOG x", "LDRCWHO", "LDRCOFF", "LDRCLINK", "LDRCRXUP 0 9 926", "LDRCIMG Yak", "UKRULES", "TIME=1763150000", "ldrcpipe=2", "ldrctel 25:AABBCCDD\n", "ldrcrep 12 200 01\n", "FrontView rst=5",
                                               "\r\nGuru Meditation Error: Core  1 panic'ed", "Backtrace: 0x4200 0x4201", "CORRUPT HEAP: Bad head at 0x3fca1234", "Core  1 register dump:", "Core dump started", "ELF file SHA256: 1a2b (the core dump)" };
          for (const char *w : own) { strcpy(TextIn, w); TextInFramed = false; CHECK(TextInIsGenuine()); }
          const char *const pages[] = { "SwitchesView1", "StEDIT", "FailSAVE", "HelpView:MODELS.TXT", "ldrcadj", "ldrcrcv", "CH3NAME=Gear", "Yes", "MixesView", "Rebooting...\r\n" };
          for (const char *w : pages) { ghosts.clear(); strcpy(TextIn, w); TextInFramed = false; CHECK(!TextInIsGenuine() && ghosts.size() == 1); strcpy(TextIn, w); TextInFramed = true; CHECK(TextInIsGenuine()); }
          ScreenFramesBursts = false; for (const char *w : pages) { strcpy(TextIn, w); TextInFramed = false; CHECK(TextInIsGenuine()); }   // (an older screen, which has never framed: every word, as ever)
          memset(TextIn, 0, 64); }
        // 47. WHILE A RESTART IS NOTED and the page not yet drawn afresh, no press is obeyed - not one kept from a moment before
        //     either (its page has gone) - but the screen's own words are
        fresh(); holdCatchUp = true; tapAt(5, "setup"); loopFor(800);
        { const uint8_t ok[4] = { 0xA7, 0, 0, 0 }; PendingPush(ok, 4, true); PendingPush((const uint8_t *) "SwitchesView1", 13, true); PendingPush((const uint8_t *) "LDRCLOG a line", 14, false); }
        ScreenRestartSeen = true; ScreenRestartSeenMs = millis(); loopFor(100);
        CHECK(count(obeyed, 39) == 0 && saves.empty() && words.empty() && screenLogLines.size() == 1 && restartsHandled == 0);
        // 48. THE KEYBOARD'S NUMBER IS NEVER LEARNED AS A PAGE'S: a number box touched in the round of the screen's loop between the
        //     page coming up and its "sendme". The keyboard's number was learned as the page's, and once the keyboard had closed every
        //     box of the page was refused - what was typed went unsaved, silently. Now: the box read under the keyboard has no answer,
        //     the page's own number is learned from the next answer, and what is typed is saved
        fresh(); screen.roundUs = 60000; screen.tapAfterPageUs = 1500 + 90000 + 5000; screen.tapAfterPageButton = "n4box"; tapAt(5, "read"); loopFor(1500);
        CHECK(screen.page == "keybdB" && ScreenPageId == 0xFF && ScreenPageIdDue && readNumber == 65535 && screen.offPageAnswers == 1 && offPage == 1);
        tapAt(5, "kbOK"); loopFor(600); screen.pages["RXOptionsView"].boxes["n3"].val = 9; const int off0 = offPage;
        tapAt(5, "OK"); loopFor(4000);
        CHECK(count(obeyed, 39) == 1 && saves.size() == 1 && TrimMultiplier == 9 && offPage == off0 && pageUnsaid == 0);
        CHECK(IsKeyboardPage(56) && IsKeyboardPage(57) && !IsKeyboardPage(9) && !IsKeyboardPage(0) && !IsKeyboardPage(55) && !IsKeyboardPage(58));
        // 49. A BOX THAT HOLDS -1 (a sub trim one step below its centre, a mix's offset, the volts correction): its answer is q and four
        //     FFs and the end's three. The frame "ended" after q, the value was put together from three FFs and a byte of an earlier
        //     read, and an FF was left over that swallowed the page's number behind it. Every value is read as it is, nothing is left
        for (long val : { -1L, -2L, -256L, -65536L, 16777215L, 255L, 5L })
        {
            fresh(); tapAt(5, "setup"); loopFor(800);
            screen.pages["RXOptionsView"].boxes["n2"].val = val; ghosts.clear(); ScreenPageUnsaid = 0; NextionTextMissed = false; memset(TextIn, 0x55, 16);
            const uint32_t v = GetValue((char *) "n2");
            CHECK((int32_t) v == (int32_t) val && !NextionTextMissed && ScreenPageUnsaid == 0 && PendingCount == 0 && offPage == 0 && pageUnsaid == 0 && NEXTION.available() == 0);
            loopFor(300); CHECK(ghosts.empty() && obeyed.size() == 1);
        }
        //     ... one that nobody waits for, read in by a write: one frame, let go - and the page's number behind it noted
        fresh(); ScreenPageId = 0xFF; ScreenPageIdDue = true; screen.emit(nowUs, { 'q', 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x66, 9, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
        StashPendingEventBytes(); CHECK(PendingCount == 0 && NEXTION.available() == 0 && ScreenPageId == 9);
        //     ... and a damaged answer (a byte lost on the wire) is no answer - never a number put together from what is there
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; screen.emit(nowUs + 20000, { 'q', 5, 0, 0xFF, 0xFF, 0xFF }); { uint16_t k = 0; NextionReplyWaitMs = 100; CHECK(!CollectReply('q', k) && PendingCount == 0); }
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; screen.emit(nowUs + 20000, { 'q', 5, 0, 0, 0, 0, 0xFF, 0xFF, 0xFF, 'q', 7, 0, 0, 0, 0xFF, 0xFF, 0xFF }); { uint16_t k = 0; NextionReplyWaitMs = 100; CHECK(CollectReply('q', k) && k == 8 && TextIn[1] == 7); }
        // 50. THE SCREEN DOES NOT SAY WHICH PAGE IT SHOWS (the "sendme" asked with a box goes unanswered) though it has said so
        //     before: the box has no answer - it was used unchecked - and the wait for it keeps the radio's packets going
        fresh(); tapAt(5, "setup"); loopFor(800); CHECK(ScreenSaysPage && ScreenPageId == 9);
        screen.muteSendme = 1; NextionTextMissed = false; radioPasses = 0;
        { const uint64_t t0 = nowUs; const uint32_t v = GetValue((char *) "n3"); const uint64_t took = nowUs - t0;
          CHECK(v == 65535 && NextionTextMissed && pageUnsaid == 1 && offPage == 0 && PageChangedUnderGet && radioPasses >= 55 + 20 && took > 600000 && took < 900000); }
        loopFor(50); NextionTextMissed = false; CHECK(GetValue((char *) "n3") == 5 && !NextionTextMissed && pageUnsaid == 1);
        //     ... its answer a little late (a round of the screen's loop between the box's answer and the page's number) is waited for
        fresh(); tapAt(5, "setup"); loopFor(800); NextionTextMissed = false;
        { NextionGetPending = true; NEXTION.print("get n3.val"); EndSend(); uint16_t k = 0; NextionReplyWaitMs = 100; CHECK(CollectReply('q', k) && TextIn[1] == 5);
          screen.emit(nowUs + 250000, { 0x66, 9, 0xFF, 0xFF, 0xFF }); CHECK(BoxPageWrong() == 0); screen.emit(nowUs + 250000, { 0x66, 57, 0xFF, 0xFF, 0xFF }); CHECK(BoxPageWrong() == 1); CHECK(BoxPageWrong() == 2); NextionGetPending = false; }
        // 51. THE END OF A WAIT: an answer that comes in two pieces across it is the answer (it was "missing", and its tail was left on
        //     the wire); a pipe line still coming in is kept WHOLE (its head alone was handed on as a line, the last item cut); half
        //     an answer with nothing behind it is not kept as a word; a button's code left open (an older screen's: no end) is kept
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; { uint16_t k = 0; NextionReplyWaitMs = 100; const uint64_t t0 = nowUs;
          screen.emit(t0 + 99700, { 'q', 7, 0 }); screen.emit(t0 + 100600, { 0, 0, 0xFF, 0xFF, 0xFF });
          CHECK(CollectReply('q', k) && k == 8 && TextIn[1] == 7 && NEXTION.available() == 0); }
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; { uint16_t k = 0; NextionReplyWaitMs = 100; const uint64_t t0 = nowUs; const char *l = "ldrctel 25:AABBCCDD 26:EEFF0011\n";
          screen.emit(t0 + 99800, std::vector<uint8_t>(l, l + 12)); screen.emit(t0 + 103000, std::vector<uint8_t>(l + 12, l + strlen(l)));
          CHECK(!CollectReply('q', k) && PendingCount == 1 && PendingLens[0] == strlen(l) && !memcmp(PendingEvent, l, strlen(l)) && NEXTION.available() == 0); }
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 50000, { 'q', 5, 0 }); CHECK(!CollectReply('p', k) && PendingCount == 0); }
        fresh(); screen.frames = false; screen.canFrame = false; ScreenFramesBursts = false; nowUs = (nowUs / 1000 + 1) * 1000;
        { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 50000, { 0xA7, 0x00, 0x00, 0x00 }); CHECK(!CollectReply('q', k) && PendingCount == 1 && PendingLens[0] == 4); }
        // 52. THE PAGE'S NUMBER glued behind a bare word (no end of its own), read in by a write when it is what comes next: noted,
        //     and the word is the word
        fresh(); ScreenPageId = 0xFF; ScreenPageIdDue = true; screen.emit(nowUs, { 'U', 'K', 'R', 'U', 'L', 'E', 'S', 0x66, 9, 0xFF, 0xFF, 0xFF }); nowUs += 1000;
        StashPendingEventBytes(); CHECK(PendingCount == 1 && PendingLens[0] == 7 && ScreenPageId == 9 && !ScreenPageIdDue);
        // 53. a SYSTEM variable is no page's: it is answered while the keyboard is up, too
        fresh(); tapAt(5, "setup"); loopFor(800); tapAt(5, "n3box"); loopFor(200); CHECK(screen.page == "keybdB");
        screen.sys["ldrcmb"] = 16; CHECK(GetSysValue("ldrcmb") == 16 && !PageChangedUnderGet && offPage == 0);
        // 54. HELP ON MODEL OPTIONS (the REAL HelpWordCame): the page's boxes are read first - what was typed is kept - and their
        //     answers took the help's name out of TextIn: nothing opened (since B160). The name is taken first, and the help opens
        fresh(); helpLive = true; screen.pages["RXOptionsView"].buttons["Help"] = bytes("HelpView:RXSETUP1.TXT");
        tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n3"].val = 9;
        tapAt(5, "Help"); loopFor(3000);
        CHECK(helpOpened.size() == 1 && helpOpened[0] == "RXSETUP1.TXT" && TrimMultiplier == 9 && CurrentView == LOGVIEW && SavedCurrentView == RXSETUPVIEW1 && screen.page == "LogView");
        //     ... from another page (nothing to read first) as ever; and a name that is not whole opens nothing, and reads nothing
        fresh(); helpLive = true; tapAt(5, "switch3"); loopFor(800); tapAt(5, "Help"); loopFor(1500); CHECK(helpOpened.size() == 1 && helpOpened[0] == "ONESWICH.TXT" && SavedCurrentView == ONE_SWITCH_VIEW);
        fresh(); helpLive = true; screen.pages["RXOptionsView"].buttons["Help"] = bytes("HelpView:RXSETUP1");
        tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["n3"].val = 9; { const int gets0 = screen.gets; tapAt(5, "Help"); loopFor(1500); CHECK(helpOpened.empty() && TrimMultiplier == 5 && CurrentView == RXSETUPVIEW1 && screen.gets == gets0); }

        // ================= AFTER THE SEVENTH REVIEW (14 Nov 2026) =================
        // 55. WHAT A REAL SCREEN'S CHIP SAYS AS IT STARTS AGAIN, and how long its start takes. Its panic handler's lines, "Rebooting...",
        //     and its ROM's text at another speed (read here as the code 80 80 00 80: an unframed code from a screen that frames) all
        //     come before its program's first word - and this board, which asked the screen at such a code, waited two seconds in its
        //     main loop at EVERY restart: the switches unread, in the air. Now the radio's longest silence and the loop's longest
        //     pass are measured: (a) with nothing in hand, on the front page - nothing is asked, nothing waits, the model is flown
        //     without a gap, and the front page (with its two picture questions) comes afresh once
        for (int reason : { 5, 3, 1 })
        {
            fresh(); frontAsksPicture = true; screen.restartReason = reason; screen.bootRecord = reason == 5 ? rec : ""; screen.prelude = chipStart(reason);
            loopFor(300); gapWatch = true; lastRadioUs = nowUs; const int gets0 = screen.gets;
            tapAt(5, "#restart"); loopFor(1500);                                      // its chip has said its piece; its program nothing yet
            CHECK(!ScreenRestartSeen && screen.gets == gets0 && maxPassUs < 40000 && radioGapUs() < 40000);   // (the ROM's text is one read of some 25 ms: nothing is asked, nothing waits)
            loopFor(8000);
            if (show) printf("55a (reason %d): the radio's longest silence %.1f ms, the loop's longest pass %.1f ms\n", reason, radioGapUs() / 1000.0, maxPassUs / 1000.0);
            CHECK(restartsHandled == 1 && lastRestartReason == (reason == 1 ? -2 : reason) && screen.page == "FrontView" && screen.frames && picMissing == 0 && picThere == 1);
            CHECK(radioGapUs() < 60000 && maxPassUs < 300000);
            CHECK(std::find(ghosts.begin(), ghosts.end(), "an unframed code: 80 80 00 80") != ghosts.end());   // (the chip's ROM text, as the transmitters' logs have it)
            if (reason == 5) { int said = 0; for (auto &l : logLines) said += l.rfind("Screen said: ", 0) == 0; CHECK(said >= 2 && (int) screenLogLines.size() == parts); }   // its panic's lines and its record are in the log
        }
        //     (b) a box asked a thousandth of a second before the screen dies: the wait for its answer is two seconds, and what the
        //     chip says meanwhile has no end - the radio's packets go on all the same (they stopped until the wait was over)
        fresh(); screen.restartReason = 5; screen.bootRecord = rec; screen.prelude = chipStart(5); tapAt(5, "setup"); loopFor(800);
        gapWatch = true; lastRadioUs = nowUs; tapAt(3, "#restart"); nowUs += 2000; NextionTextMissed = false;
        { const uint32_t v = GetValue((char *) "n3"); CHECK(v == 65535 && NextionTextMissed && screen.restarts == 1); }
        if (show) printf("55b: the radio's longest silence under the box's wait %.1f ms\n", radioGapUs() / 1000.0);
        CHECK(radioGapUs() <= 45000);                                            // (from the wait's START every 20 ms: the ROM's one line of 25 ms is the longest)
        loopFor(9000); CHECK(restartsHandled == 1 && radioGapUs() <= 60000 && sameAsAtFirst() && saves.empty());
        //     (c) the Models page (its lists asked for twice a second) through starts of 1.2, 6 and 18 seconds: no model loaded by
        //     itself, the front page once, and never more than 60 ms without a packet
        for (uint64_t boot : { 1200000ull, 6000000ull, 18000000ull })
            for (int offset = 0; offset < 500; offset += 125)
            {
                fresh(); frontAsksPicture = true; screen.restartReason = 5; screen.bootRecord = rec; screen.prelude = chipStart(5); screen.powerOnUs = boot;
                tapAt(5, "models"); loopForModels(2000); gapWatch = true; lastRadioUs = nowUs; tapAt(100 + offset, "#restart"); loopForModels(30000);
                if (show && (ModelNumber != 4 || restartsHandled != 1 || radioGapUs() > 60000)) { printf("   55c, start of %.1f s, %d ms: model %u, restarts answered %d, silence %.1f ms\n", boot / 1e6, offset, (unsigned) ModelNumber, restartsHandled, radioGapUs() / 1000.0); tellAll(); }
                CHECK(ModelNumber == 4 && modelsRead.empty() && restartsHandled == 1 && CurrentView == FRONTVIEW && screen.page == "FrontView" && picThere == 1 && radioGapUs() <= 60000);
            }
        // 56. THE CATCH-UP never waits, and is not fooled. (a) A screen that hears nothing until its loop begins: told at its power-on
        //     bytes and at its word - both lost - and told again three seconds on: then it answers. (b) A screen that cannot say a
        //     number back: the front page all the same, half a minute on - not before, and not never. (c) The number of an EARLIER
        //     telling does not count; and a number of that kind is never a box's value
        fresh(); screen.restartKeeps = false; tapAt(5, "#restart"); loopFor(2700); CHECK(ScreenRestartSeen && restartsHandled == 0);
        { const uint32_t told = ScreenSession; loopFor(2000); CHECK(restartsHandled == 0 && ScreenRestartSeen && ScreenSession == told && told != 0);
          loopFor(1500); CHECK(restartsHandled == 1 && ScreenSession != told && screen.sys["ldrcup"] == (long) ScreenSession && screen.page == "FrontView" && screen.frames); }
        fresh(); screen.knowsSysGet = false; tapAt(5, "#restart"); loopFor(28000); CHECK(ScreenRestartSeen && restartsHandled == 0);
        loopFor(6000); CHECK(restartsHandled == 1 && !ScreenRestartSeen && screen.page == "FrontView");
        fresh(); ScreenSessionTell();
        { const uint32_t a = ScreenSession; ScreenSessionTell(); const uint32_t b = ScreenSession; CHECK(a != b && IsMarkKind(a) && IsMarkKind(b) && !IsMarkKind(0x4C480001UL) && !IsMarkKind(0x4C430001UL) && ScreenToldMs != 0);
          const uint8_t qa[5] = { 'q', (uint8_t) a, (uint8_t) (a >> 8), (uint8_t) (a >> 16), (uint8_t) (a >> 24) }, qb[5] = { 'q', (uint8_t) b, (uint8_t) (b >> 8), (uint8_t) (b >> 16), (uint8_t) (b >> 24) };
          CHECK(TakeScreenMark(qa) && !ScreenSaidSession); CHECK(TakeScreenMark(qb) && ScreenSaidSession);
          ScreenSessionTell(); CHECK(!ScreenSaidSession && ScreenSession != b); }   // (told afresh: the answer to the telling before is no answer to this one)
        fresh(); tapAt(5, "setup"); loopFor(800); screen.pages["RXOptionsView"].boxes["big"].val = 0x4C460005L; NextionTextMissed = false; CHECK(GetValue((char *) "big") == 65535 && NextionTextMissed);
        // 57. THE LETTER f IS NOT A PAGE'S NUMBER (66 is both). While a page's number was awaited, a pipe line ending "...off" and its
        //     newline, read in by a write, lost its last two bytes and gave "page 10"; a late text answer "pOff" gave "page 102" - and
        //     every box of the page was then refused. A page's number is taken only from a frame that had its end, never out of a
        //     text reply, and - behind a bare word - only right behind its marker
        fresh(); ScreenPageId = 0xFF; ScreenPageIdDue = true; screen.emit(nowUs, bytes("ldrcrep 12 200 off\n")); nowUs += 1000; StashPendingEventBytes();
        CHECK(PendingCount == 1 && PendingLens[0] == 19 && ScreenPageId == 0xFF && ScreenPageIdDue);
        for (int way = 0; way < 2; ++way)
        {
            fresh(); ScreenPageId = 0xFF; ScreenPageIdDue = true; { auto b = bytes("pOff"); b.insert(b.end(), 3, 0xFF); screen.emit(nowUs, b); } nowUs += 1000;
            if (way) StashPendingEventBytes(); else loopFor(5);
            CHECK(ScreenPageId == 0xFF && ScreenPageIdDue);
            fresh(); ScreenPageId = 0xFF; ScreenPageIdDue = true; { auto b = bytes("LDRCAWAKE"); for (uint8_t x : { (uint8_t) 0x66, (uint8_t) 9, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x); screen.emit(nowUs, b); } nowUs += 1000;
            if (way) { StashPendingEventBytes(); CHECK(PendingCount == 1 && PendingLens[0] == 9 && ScreenPageId == 9); }   // (read in by a write: a frame with its end - the page's number behind the word)
            else { CHECK(GetButtonPress() && !strncmp(TextIn, "LDRCAWAKE", 9) && TextInIsGenuine() && ScreenPageId == 0xFF); }   // (read by the loop in one go: not behind a marker - left, and learned from the next box)
        }
        //     ... a page's number at the head of the wire is read as what it is, not as a word; half of one at a wait's end is not
        //     kept as a word; a damaged one (a byte lost, a byte too many) is no number
        fresh(); ScreenPageId = 0xFF; ScreenPageIdDue = true; screen.emit(nowUs, { 0x66, 9, 0xFF, 0xFF, 0xFF }); nowUs += 1000; CHECK(!GetButtonPress() && ScreenPageId == 9 && ghosts.empty() && PendingCount == 0);
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 50000, { 0x66, 9 }); CHECK(!CollectReply('q', k) && PendingCount == 0); }
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 20000, { 0x66, 0xFF, 0xFF, 0xFF }); CHECK(!CollectReply(0x66, k)); }
        fresh(); nowUs = (nowUs / 1000 + 1) * 1000; { uint16_t k = 0; NextionReplyWaitMs = 100; screen.emit(nowUs + 20000, { 0x66, 9, 5, 0xFF, 0xFF, 0xFF }); CHECK(!CollectReply(0x66, k)); }
        //     ... a Rotorflight page's look before its boxes learns the page's number when it is what comes next
        fresh(); tapAt(5, "setup"); loopFor(800); ScreenPageId = 0xFF; ScreenPageIdDue = true; RfGatherStart(); CHECK(NextionSettledOk && ScreenPageId == 9 && !ScreenPageIdDue && !PageChangedUnderGet);
        // 58. A BOX ANSWERED, AND THEN THE SCREEN'S POWER-ON BYTES BEFORE ITS PAGE'S NUMBER: no answer - for a number, a text, a
        //     part's other attribute (the screen deaf here, what "it" says said by hand)
        fresh(); tapAt(5, "setup"); loopFor(800); holdCatchUp = true; screen.deaf = true;
        { std::vector<uint8_t> b = { 'q', 5, 0, 0, 0, 0xFF, 0xFF, 0xFF }; b.insert(b.end(), powerOn.begin(), powerOn.end()); for (uint8_t x : { (uint8_t) 0x66, (uint8_t) 9, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x);
          screen.emit(nowUs + 10000, b); NextionTextMissed = false; CHECK(GetValue((char *) "n3") == 65535 && NextionTextMissed && ScreenRestartSeen); }
        fresh(); tapAt(5, "setup"); loopFor(800); holdCatchUp = true; screen.deaf = true;
        { std::vector<uint8_t> b = { 'p', '3', '.', '5', '0', 0xFF, 0xFF, 0xFF }; b.insert(b.end(), powerOn.begin(), powerOn.end()); for (uint8_t x : { (uint8_t) 0x66, (uint8_t) 9, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x);
          screen.emit(nowUs + 10000, b); NextionTextMissed = false; char tx[20] = "x"; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && tx[0] == 0 && NextionTextMissed && ScreenRestartSeen); }
        fresh(); tapAt(5, "setup"); loopFor(800); holdCatchUp = true; screen.deaf = true;
        { std::vector<uint8_t> b = { 'q', 6, 0, 0, 0, 0xFF, 0xFF, 0xFF }; b.insert(b.end(), powerOn.begin(), powerOn.end()); for (uint8_t x : { (uint8_t) 0x66, (uint8_t) 9, (uint8_t) 0xFF, (uint8_t) 0xFF, (uint8_t) 0xFF }) b.push_back(x);
          screen.emit(nowUs + 10000, b); CHECK(GetOtherValue((char *) "n4.val") == 0 && ScreenRestartSeen); }
        // 59. WHAT THE BREAK-IT ROUND OF THE NIGHT OF 14 NOV 2026 LEFT STANDING. (a) A late text answer whose text ENDS as the
        //     awaited marker does ("...q12EL": q, the count, 45 4C), read by the loop: a text box may hold any letters - it is no
        //     marker, and the page is not "up" for it. (b) The one byte 88 with nothing behind it, at the end of what a write read
        //     in, is not the screen's power-on byte (that one comes with its end). (c) A Rotorflight page's look before its boxes,
        //     the screen silent: two and a half seconds of waiting, in windows of 20 ms - the radio's packets never 45 ms apart
        fresh(); ScreenMarkCount = 0x3231; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis(); ScreenMarkMisses = 0;
        holdCatchUp = true;                                                         // (what was READ is looked at - not what the asking that follows makes of a marker that will never come)
        screen.emit(nowUs, { 'p', 'a', 'b', 'q', 0x31, 0x32, 0x45, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 1000; loopFor(5);
        CHECK(ScreenMarkAwaited != 0 && ScreenMarkOldPage);
        fresh(); ScreenMarkCount = 0x3231; ScreenMarkAwaited = SCREEN_MARK_BASE | SCREEN_MARK_PAGE | ScreenMarkCount; ScreenMarkOldPage = true; ScreenMarkAskedMs = millis(); ScreenMarkMisses = 0;
        screen.emit(nowUs, { 'L', 'D', 'R', 'C', 'A', 'W', 'A', 'K', 'E', 'q', 0x31, 0x32, 0x45, 0x4C, 0xFF, 0xFF, 0xFF }); nowUs += 1000; loopFor(5);
        CHECK(ScreenMarkAwaited == 0 && !ScreenMarkOldPage);                           // (... while behind a bare word of the screen's own it IS the marker, as ever)
        fresh(); screen.emit(nowUs, { 0x88 }); nowUs += 1000; StashPendingEventBytes(); CHECK(!ScreenRestartSeen);
        fresh(); screen.emit(nowUs, { 0x88, 0xFF, 0xFF, 0xFF }); nowUs += 1000; holdCatchUp = true; StashPendingEventBytes(); CHECK(ScreenRestartSeen && ScreenRestartReason == -2);
        // (the thirteenth review: no scene held it) ... and two bytes that begin with the letter f and have NO END - a cut line's tail, a line's last two letters -
        // are not "the page the screen shows" (66 and a number, WITH its end, is the screen's answer to "sendme": the page it shows, and counted)
        fresh(); { const uint16_t said = ScreenPageSaidCount; screen.emit(nowUs, { 0x66, 9 }); nowUs += 1000; StashPendingEventBytes(); nowUs += 3000; StashPendingEventBytes(); CHECK(ScreenPageSaidCount == said); }
        fresh(); { const uint16_t said = ScreenPageSaidCount; screen.emit(nowUs, { 0x66, 9, 0xFF, 0xFF, 0xFF }); nowUs += 1000; StashPendingEventBytes(); CHECK(ScreenPageSaidCount == (uint16_t) (said + 1)); }
        fresh(); tapAt(5, "setup"); loopFor(800); screen.deaf = true; gapWatch = true; lastRadioUs = nowUs;
        { const uint64_t t0 = nowUs; RfGatherStart(); CHECK(!NextionSettledOk && nowUs - t0 >= 2400000 && nowUs - t0 < 2700000 && radioGapUs() <= 45000); }
        //     (d) After a TEXT box's answer that never came, or another attribute's, no box of that press is asked (as after a
        //     number box's): not asked, not waited for - and no answer
        fresh(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("t10"); screen.pages["RXOptionsView"].boxes["n3"].val = 9;
        { char tx[20] = "x"; NextionTextMissed = false; CHECK(GetText((char *) "t10", tx, sizeof tx) == 0 && tx[0] == 0 && NextionTextMissed && PageChangedUnderGet);
          const int g1 = screen.gets; const uint64_t t1 = nowUs; CHECK(GetValue((char *) "n3") == 65535 && screen.gets == g1 && nowUs - t1 < 100000); }
        fresh(); tapAt(5, "setup"); loopFor(800); screen.mute.insert("n4"); screen.pages["RXOptionsView"].boxes["n3"].val = 9;
        { CHECK(GetOtherValue((char *) "n4.val") == 0 && PageChangedUnderGet);
          const int g1 = screen.gets; const uint64_t t1 = nowUs; CHECK(GetValue((char *) "n3") == 65535 && screen.gets == g1 && nowUs - t1 < 100000); }
    }
    // 58. (the thirteenth review, reviewer A's finding 1) THE LINES KEPT WHILE THE MODEL MAY FLY, AS THEY REACH THE CARD. The twelfth review's cure kept the
    //     front page's reason short: "Front page: " and its first 24 letters - and the screen's restart read "the screen restarted (rs" for every cause;
    //     the second restart of a flight, the same text, was not kept at all. main.cpp's own ScreenHasRestarted for every cause, and LogFiles.h's own
    //     chain (KeepScreenNote, LogFrontPageReason, DeferLogText, FlushDeferredLog) to a card that is a text.
    {
        const int causes[] = { 3, 4, 5, 6, 7, 9, -1, -2, -3, -4, 42 };
        const char *words[] = { "its own", "PANIC", "int wdog", "task wdog", "wdog", "BROWN-OUT", "no reason", "power on", "by asking", "silent", "?" };
        fresh(); mayFly = true;
        int n = 0, lastCount = -1; size_t longest = 0;
        for (int rst : causes)
        {
            CurrentView = RXSETUPVIEW1; ScreenRestartSeen = true; ScreenRestartReason = rst; frontReasons.clear(); frontBriefs.clear(); frontMore.clear();
            ScreenHasRestarted();
            CHECK(frontReasons.size() == 1 && frontBriefs[0] == "screen restart" && frontMore[0].size() <= 36 && frontMore[0].rfind("Screen restart ", 0) == 0);
            char want[60]; snprintf(want, sizeof want, ": rst=%d %s", rst, words[n]);
            const int count = atoi(frontMore[0].c_str() + 15);
            CHECK(frontMore[0].size() > strlen(want) && frontMore[0].compare(frontMore[0].size() - strlen(want), strlen(want), want) == 0);   // its code and its word, at the line's end: whole
            CHECK(count >= 1 && (lastCount < 0 || count == lastCount + 1));                                   // which restart of this run: each has its own number
            lastCount = count; if (frontMore[0].size() > longest) longest = frontMore[0].size();
            // ... and through the real chain: nothing written while it may fly; at the quiet moment two lines, the page left in the first, the cause whole in the second
            kept::reset(); CurrentView = RXSETUPVIEW1;
            kept::LogFrontPageReason(frontReasons[0].c_str(), frontBriefs[0].c_str(), frontMore[0].c_str());
            CHECK(kept::cardOpens == 0 && kept::cardText.empty() && kept::FrontReasonLogged);
            kept::FlushDeferredLog();
            { const std::vector<std::string> l = kept::lines(); char first[60]; snprintf(first, sizeof first, "12.34.56 - Page %u -> front: screen restart", (unsigned) RXSETUPVIEW1);
              if (show && n == 5) printf("58. a brown-out in flight, as the log has it: [%s] [%s]\n", l.size() > 0 ? l[0].c_str() : "?", l.size() > 1 ? l[1].c_str() : "?");
              CHECK(l.size() == 2 && l[0] == first && l[1] == "12.34.56 - " + frontMore[0] && kept::cardOpens == 1); }
            ++n;
        }
        CHECK(longest >= 28);                                                                                  // (the longest today: "Screen restart N: rst=-3 by asking")
        // two restarts of the same cause from the same page: four lines (the second was dropped as "the same thing twice")
        kept::reset(); CurrentView = 9;
        kept::LogFrontPageReason("the screen restarted (rst=9: a BROWN-OUT (its supply dipped))", "screen restart", "Screen restart 1: rst=9 BROWN-OUT");
        kept::LogFrontPageReason("the screen restarted (rst=9: a BROWN-OUT (its supply dipped))", "screen restart", "Screen restart 2: rst=9 BROWN-OUT");
        kept::FlushDeferredLog();
        { const std::vector<std::string> l = kept::lines();
          CHECK(l.size() == 4 && l[0] == "12.34.56 - Page 9 -> front: screen restart" && l[1] == "12.34.56 - Screen restart 1: rst=9 BROWN-OUT" && l[2] == l[0] && l[3] == "12.34.56 - Screen restart 2: rst=9 BROWN-OUT"); }
        // the longest a kept line may be - a page of three digits, a reason of 17 letters, a second line of 36 - reaches the card whole
        kept::reset(); CurrentView = 255; kept::LogFrontPageReason("x", "motor box is over", "Screen restart 999: rst=-3 by asking"); kept::FlushDeferredLog();
        { const std::vector<std::string> l = kept::lines(); CHECK(l.size() == 2 && l[0] == "12.34.56 - Page 255 -> front: motor box is over" && l[1] == "12.34.56 - Screen restart 999: rst=-3 by asking"); }
        // THE BUDGET: a screen that starts again and again, a wire gone bad - forty notes and forty reasons in one flight. Eight and six are kept, NOTHING IS
        // WRITTEN (the store has 24 places, and when they are full it writes them all at once, in the air); the rest are counted, and said at the quiet moment
        kept::reset();
        for (int i = 0; i < 40; ++i) { char b[40]; snprintf(b, sizeof b, "Late %d ms: get t%d.txt", 500 + i, i); kept::KeepScreenNote(b, false); snprintf(b, sizeof b, "Screen restart %d: rst=9 BROWN-OUT", i + 1); kept::KeepScreenNote(b, true); }
        CHECK(kept::cardOpens == 0 && kept::cardText.empty() && kept::DeferredLogN == 14);
        kept::FlushDeferredLog();
        { const std::vector<std::string> l = kept::lines();
          if (show) printf("58. forty notes and forty reasons in one flight: %d lines on the card, the last [%s], the card opened %d time(s)\n", (int) l.size(), l.empty() ? "?" : l.back().c_str(), kept::cardOpens);
          CHECK(l.size() == 15 && l[14] == "               - 66 more notes about the screen were not kept B211" && kept::cardOpens == 1); }
        kept::KeepScreenNote("Late 1 ms: get x.txt", false); kept::KeepScreenNote("Screen restart 41: rst=9 BROWN-OUT", true); CHECK(kept::DeferredLogN == 2);   // ... and the budget begins again
        kept::FlushDeferredLog(); CHECK(kept::lines().size() == 17);                                           // (nothing more is said of what was not kept: it has been said)
        // ... THE SAME NOTE AGAIN AND AGAIN TAKES ONE PLACE (it is kept once): the note that matters behind it still finds room (thirty times "No page
        // marker ..." used the budget up - the late answer behind them was "one more note not kept")
        kept::reset(); for (int i = 0; i < 30; ++i) kept::KeepScreenNote("No page marker from the screen", false);
        kept::KeepScreenNote("Late 512 ms: get n3.val", false); kept::FlushDeferredLog();
        { const std::vector<std::string> l = kept::lines(); CHECK(l.size() == 2 && l[0] == "12.34.56 - No page marker from the screen" && l[1] == "12.34.56 - Late 512 ms: get n3.val"); }
        // (the thirteenth review, reviewer B's A6) A KEPT LINE NEVER REACHED THE CARD when the transmitter was switched off with no model connected:
        // they were written when the safety changed, when the model went, when the store was full - and at power-off only inside "a model is still
        // connected". main.cpp's own lines of the once-a-second chores: written while NO MODEL IS CONNECTED and nothing may fly ...
        kept::reset(); kept::KeepScreenNote("Box n4: text is no number", false);
        kept::BoundFlag = kept::ModelMatched = true; kept::flies = false; kept::onceASecond(); CHECK(kept::cardOpens == 0 && kept::DeferredLogN == 1);    // a model connected: they wait (a card write is a gap in the link)
        kept::flies = true; kept::onceASecond(); CHECK(kept::cardOpens == 0 && kept::DeferredLogN == 1);
        kept::ModelMatched = false; kept::onceASecond(); CHECK(kept::cardOpens == 0 && kept::DeferredLogN == 1);                                           // no model, but it may fly (the safety off): they wait
        kept::BoundFlag = false; kept::ModelMatched = true; kept::onceASecond(); CHECK(kept::cardOpens == 0);
        kept::BoundFlag = true; kept::ModelMatched = false; kept::flies = false; kept::onceASecond();                                                      // bound, but not this model's receiver: no model is connected
        { const std::vector<std::string> l = kept::lines(); if (show) printf("58b. a note kept with no model connected: on the card within the second: %d line(s) [%s]\n", (int) l.size(), l.empty() ? "?" : l[0].c_str());
          CHECK(kept::cardOpens == 1 && l.size() == 1 && l[0] == "12.34.56 - Box n4: text is no number" && kept::DeferredLogN == 0); }                      // no model, nothing may fly: written
        kept::onceASecond(); kept::onceASecond(); CHECK(kept::cardOpens == 1);                                                                                 // nothing kept: the card is not touched
        kept::BoundFlag = kept::ModelMatched = false; kept::KeepScreenNote("Late 600 ms: get n3.val", false); kept::onceASecond(); CHECK(kept::cardOpens == 2 && kept::lines().size() == 2);
        kept::reset(); mayFly = false; CurrentView = FRONTVIEW;
    }
'''

_once_at = MAIN_CPP.index('\n', MAIN_CPP.index('        FlightStampTick(); // (11 Nov 2026)')) + 1
ONCE_A_SECOND = MAIN_CPP[_once_at:MAIN_CPP.index('        if (VersionMismatch)', _once_at)]
if ONCE_A_SECOND.count('FlushDeferredLog();') != 1 or 'BoundFlag' not in ONCE_A_SECOND or len(ONCE_A_SECOND) > 900:
    raise SystemExit('main.cpp: the once-a-second chores no longer write the kept lines between FlightStampTick and the version check (dev/test_stalepress lifts those lines)')
def program():
    decl_start = NEXTION.index('#define MAXPENDINGFRAME'); decl_end = NEXTION.index('void PendingPush(')
    decls = '\n'.join(l for l in NEXTION[decl_start:decl_end].split('\n') if not l.startswith('//'))
    nx = ''.join('#define %s %s\n' % (d, define(d)) for d in ('SUBTRIM_WORD_BYTES', 'SUBTRIM_DONE_BYTES')) + decls   # (1Definitions.h: the Sub-trim page's two bursts - IsPageOwnWord knows the "done" by its length)
    keep_at = NEXTION.index('static bool WorkLostABox()'); keep_end = NEXTION.index('\n', NEXTION.index('#define KEEP_WHOLE(id, thing)')) + 1
    KEEPTEXT = NEXTION[keep_at:keep_end]
    word_at = NEXTION.index('#define WORD_OPEN_MS'); word_end = NEXTION.index('// B186 (Malcolm, 5 Nov 2026, PID plus:', word_at)
    WORDTEXT = '\n'.join(l for l in NEXTION[word_at:word_end].split('\n') if not l.startswith('//')) + '\n'
    for head in ('void PendingPush(', 'int ReadFramedRest(', 'void StashFramed(', 'void PendingShrinkFirst()', 'FLASHMEM void PurgeKeptPresses()', '@WORD@', 'static bool PipeLineHead(', 'static bool PipeLineDone(', 'static bool PipeLineOpen(', 'static bool BareLineDone(', 'B211_RARE static void NoteBareRead(',
                 'void StashFrame(const uint8_t *f, uint16_t n, bool withEnd)', 'B211_RARE static void NotePipeLineTooLong()', 'void StashPendingEventBytes()', 'static bool GluedNumberOk(', 'bool CollectReply(uint8_t expected, uint16_t &k)',
                 'void GetTextIn()', 'bool GetButtonPress()', 'B211_RARE static bool IsScreensOwnWord(', 'bool TextInIsGenuine()', 'bool HelpNameWhole(', 'bool HelpNameFrom(',
                 'void GetReturnCode(char *tbox)', 'void CopyTextForNextion(',
                 'void SendText1(', 'void SendText(char *tbox', 'static bool IsPageCommand(', 'FLASHMEM void BeforePageCommand()', 'FLASHMEM void AskPageMarker(bool pageUp)\n{', 'void SendCommand(char *tbox)', 'void EndSend()', 'void SendValue(', 'FLASHMEM static uint8_t BoxPageWrong()', 'static uint32_t GetNumberReply(',
                 'static void BoxWasLost(', 'FLASHMEM bool TextMustBeNumber(', '@KEEP@', 'uint32_t getvalue(', 'uint32_t GetSysValue(', 'uint32_t GetValue(', 'FLASHMEM static bool ScreenSettles(uint32_t mostMs)', 'uint16_t GetText(', 'FLASHMEM uint8_t ScreenSessionCheck()', 'FLASHMEM void RfGatherStart()', 'int GetOtherValue(', 'static inline void NextionTerminator()', 'int NextionFileExistsOnSD3('):
        nx += KEEPTEXT if head == '@KEEP@' else WORDTEXT if head == '@WORD@' else lift(NEXTION, head)
    helpers = lift(MAIN_CPP, 'int InStrng(') + lift(MAIN_CPP, 'int CheckRange(') + lift(UTIL, 'FASTRUN char *Str(') \
        + [l for l in UTIL.split('\n') if l.startswith('uint8_t MotorOffFromMicros(')][0] + '\n' \
        + lift(UTIL, 'static uint16_t ScreenCountSeed()') + lift(UTIL, 'static uint16_t ScreenCountAfter(uint16_t c)')   # (the counts of a page's markers and the numbers said back: Utilities.h)
    boxes = ' '.join('opt.boxes["%s"] = { %s, %s, "%s" };' % (n, 'true' if k == 't' else 'false', v if k == 'n' else 0, v if k == 't' else '') for n, k, v in OPTION_BOXES)
    pre = PRE % {k: define(k) for k in ('SCREENCHANGEWAIT', 'FRONTVIEW', 'RXSETUPVIEW1', 'RXSETUPVIEW', 'ONE_SWITCH_VIEW', 'MINMICROS', 'MAXMICROS', 'MODELSVIEW', 'HELP_VIEW', 'LOGVIEW', 'MAXMODELNUMBER', 'CALIBRATEVIEW', 'NORMAL', 'CALIBRATELIMITS', 'CENTRESTICKS', 'WHAHWHAHMSG')}
    LOGF = release(src('include/LogFiles.h'))
    # (the thirteenth review) THE KEPT LINES' WHOLE CHAIN, AS IT STANDS: the budget, the reason's line, the store and its writing - LogFiles.h's own, with a card that is a text
    keptlog = ('namespace kept {\nstatic bool FrontReasonLogged = false; static std::string cardText; static int cardOpens = 0;\n'
               'static void CheckLogFileIsOpen() { ++cardOpens; } static void CloseLogWriteFile() {} static void WriteToLogFile(char *t, size_t n) { cardText.append(t, n); }\n'
               'static void CreateTimeStamp(char *s) { strcpy(s, "12.34.56"); }\nvoid DeferLogText(const char *text, bool stamp);\n'
               + LOGF[LOGF.index('#define SCREEN_NOTES_MOST'):LOGF.index('// B172 (Malcolm, 2 Nov 2026: "several times')]
               + lift(LOGF, 'FLASHMEM void LogFrontPageReason(const char *why, const char *brief, const char *more)')
               + LOGF[LOGF.index('static char DeferredLog[24][48];'):LOGF.index('FASTRUN void LogMotor(bool On)')]
               + 'static std::vector<std::string> lines() { std::vector<std::string> l; size_t at = 0; while (at < cardText.size()) { const size_t e = cardText.find("|\\r\\n", at); if (e == std::string::npos) break; l.push_back(cardText.substr(at, e - at)); at = e + 3; } return l; }\n'
               'static void reset() { cardText.clear(); cardOpens = 0; DeferredLogN = 0; DeferredLast[0] = 0; ScreenNotesKept = ScreenReasonsKept = 0; ScreenNotesNotKept = 0; ScreenLinesHeldN = 0; ScreenLinesNotHeld = 0; }\n'
               'static bool BoundFlag = false, ModelMatched = false, flies = false; static bool RadiosMustBeOff() { return flies; } static bool LogMustWait() { return flies; }\n'
               'static void onceASecond()   // main.cpp, the once-a-second chores: its own lines between FlightStampTick and the version check\n{\n' + ONCE_A_SECOND + '}\n}\n')
    reallog = ('namespace real {\nstatic bool FrontReasonLogged = false;\n' + lift(LOGF, 'FLASHMEM void LogFrontPageReason(const char *why, const char *brief, const char *more)') + lift(LOGF, 'FLASHMEM void LogGhostFrame(const char *why, const uint8_t *f, uint16_t n)')
               + lift(NEXTION, 'static void NoteLateReply(const char *cmd, uint32_t ms, bool got)')   # (the twelfth review: the three older notes, as they are)
               + LOGF[LOGF.index('uint16_t StalePressCount = 0;'):LOGF.index('// B198 (Malcolm, 8 Nov 2026, the screen\'s interrupt watchdog twice')] + '}\n'
               + 'static void ScreenLineOut(char *t, int n) { LogText(t, (uint16_t) n, true); }   // (LogFiles.h: at once on the ground - the real one, which holds the lines while the model may fly, runs in the namespace "kept": scene_kept_lines)\n'
               + lift(LOGF, 'FLASHMEM bool ScreenDyingWords(const char *t)'))
    rom = rom_as_read(ROM_TEXT)
    if [b for _, b in rom[:4]] != [0x80, 0x80, 0x00, 0x80]: raise SystemExit('the ROM text\'s first bytes are not 80 80 00 80 as the transmitters\' logs have them: ' + repr(rom[:6]))
    romtable = 'static const std::vector<std::pair<uint64_t, uint8_t>> romBytes = { ' + ', '.join('{ %dull, 0x%02X }' % p for p in rom) + ' };\n'
    return (pre + 'int InStrng(char *text1, char *text2);\nFASTRUN char *Str(char *s, int n, int comma);\n' + helpers + nx + reallog + keptlog + romtable + MODEL
            + lift(MENU, 'FLASHMEM void ReadRXOptionsView()') + lift(MENU, 'void RXOptionsViewEnd()')
            + lift(MAIN_CPP, 'FLASHMEM static void SwitchJobFromPage(') + lift(MAIN_CPP, 'FLASHMEM void ReadNewSwitchFunction()')
            + lift(MAIN_CPP, 'FLASHMEM void ScreenHasRestarted()') + lift(MAIN_CPP, 'FLASHMEM void ScreenKeepUp()') + lift(release(src('include/Help.h')), 'FLASHMEM void SendHelp()') + lift(MAIN_CPP, 'FLASHMEM void HelpWordCame()')
            + '\n'.join(l for l in UTIL.split('\n') if l.startswith('#define QUESTION_')) + '\n'
            + lift(UTIL, 'void GetYesOrNo(uint16_t asked)') + lift(MAIN_CPP, 'bool CheckModelName()') + lift(UTIL, 'void CheckForNextionButtonPress()')
            + MAIN % {'OPTION_BOXES': boxes, 'SCENES': SCENES, 'SCENES2': SCENES2, 'FRESH_MORE': FRESH_MORE})

def main():
    bad = page_checks()
    if table_entry('NumberedFunctions', 39) != 'RXOptionsViewEnd': bad.append('code 39 is not RXOptionsViewEnd')
    for fn, miss in (('static uint32_t GetNumberReply(', 'ValueIn = 65535;'), ('int GetOtherValue(', 'ValueIn = 0;')):
        if not re.search(r'if \(IsMarkKind\((?:\(uint32_t\))?ValueIn\)\)\s*\{?\s*' + re.escape(miss), re.sub(r'//[^\n]*', '', lift(NEXTION, fn))):
            bad.append(fn + ' ...): a number of the markers\' kind must be "no answer" there too (no run reaches the line: CollectReply lets no marker through)')
    SC = re.sub(r'//[^\n]*', '', lift(NEXTION, 'void SendCommand(char *tbox)'))
    if NEXTION.count('BeforePageCommand();') != 1 or not re.search(
            r'const bool pageCommand = IsPageCommand\(tbox\);\s*if \(pageCommand\)\s*BeforePageCommand\(\);\s*NEXTION\.print\(tbox\);\s*for \(int i = 0; i < 3; \+\+i\)\s*NEXTION\.write\(0xff\);\s*if \(pageCommand\)\s*AskPageMarker\(true\);', SC) \
            or NEXTION.count('AskPageMarker(true);') != 1 or NEXTION.count('AskPageMarker(false);') != 1 or not re.search(r'PurgeKeptPresses\(\);\s*AskPageMarker\(false\);', re.sub(r'//[^\n]*', '', lift(NEXTION, 'FLASHMEM void BeforePageCommand()'))):
        bad.append('SendCommand: for a page command BeforePageCommand (which ends by asking the first marker), the command itself, and the second marker asked right behind it - and nowhere else')
    mc = re.sub(r'//[^\n]*', '', MAIN_CPP)
    ctd = re.sub(r'//[^\n]*', '', lift(MAIN_CPP, 'void Close_TX_Down()'))
    if not re.search(r'FlushDeferredLog\(\);\s*if \(UseLog && LedWasGreen\)', ctd) or ctd.index('FlushDeferredLog();') > ctd.index('LogDisConnection'):
        bad.append('main.cpp Close_TX_Down: the lines kept for a quiet moment are written at EVERY power-off - in front of "a model is still connected" (they were written only inside it: switched off with no model connected, a kept line never reached the card)')
    if not re.search(r'if \(InStrng\(StCH, TextIn\)\)\s*\{\s*ClearText\(\);\s*return;\s*\}', mc) \
            or not re.search(r'if \(InStrng\(StEDIT, TextIn\)\)\s*\{\s*if \(CurrentView == SUBTRIMVIEW\)\s*SubTrimWord\(\(const uint8_t \*\)TextIn, TextInLen, TextInFramed\);\s*ClearText\(\);\s*return;\s*\}', mc):
        bad.append('main.cpp: the Sub-trim page\'s "StCH" tells this board nothing (nothing asked, nothing written); its "StEDIT" is handed to Trims.h SubTrimWord with its burst and its length, on that page only (dev/test_wholepage/scene_subtrim runs it)')
    if not re.search(r'if \(BoundFlag && ModelMatched && CurrentView != FRONTVIEW && !NextionGetPending && !ModalWaits\)', mc):
        bad.append('main.cpp: the power button must not bring the front page up while a get waits for its answer, nor over a question that waits')
    for gone in ('FlushNextionInput(', 'ReadNextionNumber('):
        if gone in re.sub(r'//[^\n]*', '', NEXTION): bad.append('Nextion.h: ' + gone + '...) read the wire blindly and is to stay gone')
    if len(re.findall(r'\bScreenMarkAwaited = ', re.sub(r'//[^\n]*', '', NEXTION))) != 6:
        bad.append('ScreenMarkAwaited is set in six places only: its declaration, BeforePageCommand, TakeScreenMark (the wait over; on again when a marker comes after it was given up), ScreenMarkGiveUp and ScreenOwedOver (the marker lost on the wire)')
    # THE SIXTH AND SEVENTH REVIEWS' checks (the parts of main.cpp that cannot be run on the Mac are looked at as text)
    nxc = re.sub(r'//[^\n]*', '', NEXTION)
    if not re.search(r'CheckForNextionButtonPress\(\);\s*if \(ScreenRestartSeen \|\| ScreenAnswerOwed \|\| \(CurrentView != FRONTVIEW && ScreenPageId == SCREEN_FRONT_PAGE\) \|\| \(!ScreenSaidSession && \(int32_t\)\(RightNow - ScreenSessionNextMs\) >= 0\)\)\s*ScreenKeepUp\(\);\s*KickTheDog\(\);', re.sub(r'//[^\n]*', '', MAIN_CPP)):
        bad.append('main.cpp ManageTransmitter: its look for a press; then, while the screen has restarted, owes an answer or has not yet said its session\'s number, ScreenKeepUp (which never waits); then the dog - and on with the pass (nothing returns, nothing waits)')
    ku = re.sub(r'//[^\n]*', '', lift(MAIN_CPP, 'FLASHMEM void ScreenKeepUp()'))
    if not re.search(r'\{\s*if \(ScreenRestartSeen\)\s*\{\s*if \(ScreenCaughtUp\(\)\)\s*ScreenHasRestarted\(\);\s*return;\s*\}\s*if \(ScreenAnswerOwed\)\s*\{\s*ScreenOwedStep\(\);\s*return;\s*\}\s*if \(CurrentView != FRONTVIEW && ScreenPageId == SCREEN_FRONT_PAGE\)\s*\{\s*LogFrontPageReason\("[^"]*", "[^"]*"\);\s*GotoFrontView\(\);\s*return;\s*\}\s*ScreenSessionAtStart\(\);\s*\}', ku):
        bad.append('main.cpp ScreenKeepUp: a restart noted - caught up? then the front page afresh; an answer owed - ScreenOwedStep; else the session\'s number at this board\'s start')
    if not re.search(r'StashPendingEventBytes\(\);\s*ScreenStartupOver = true;', mc) or mc.count('ScreenStartupOver = true;') != 1 or len(re.findall(r'\bScreenStartupOver = ', nxc)) != 1:
        bad.append('main.cpp setup(): its last lines read the wire in and say "ScreenStartupOver = true" - there and nowhere else')
    fv = mc[mc.index('if (InStrng(Front_View, TextIn))'):]; fv = fv[:fv.index('if (InStrng(Sticks_View, TextIn))')]
    if 'NoteScreenRestart(' not in fv or 'GotoFrontView' in fv or 'ScreenFramesBursts' in fv:
        bad.append('main.cpp: the word FrontView is noted (NoteScreenRestart) - the main loop draws the page afresh, not the word\'s branch')
    if 'ScreenFramesBursts = false' in mc:
        bad.append('main.cpp: nothing may forget that the screen frames (its unframed presses after a restart are not to be obeyed)')
    if not re.search(r'if \(InStrng\(HelpView, TextIn\) > 0\)\s*\{\s*HelpWordCame\(\);', mc):
        bad.append('main.cpp: the Help word is answered by HelpWordCame (which takes the name before it reads the page)')
    sh = re.sub(r'//[^\n]*', '', lift(MAIN_CPP, 'FLASHMEM void ScreenHasRestarted()'))
    if not re.search(r'ScreenRestartSeen = false;.*SendCommand\(\(char \*\)"ldrcframe=1"\);.*ScreenWarmup\(\);.*GotoFrontView\(\);', sh, re.S):
        bad.append('main.cpp ScreenHasRestarted: the restart is done with, the screen told to frame, warmed up, the front page')
    # NOTHING OF THE RESTART'S ANSWER WAITS (the seventh review): no asking with a wait in the loop's part, nor where a press is judged
    for fn in ('B211_RARE static bool ScreenCaughtUp()', 'FLASHMEM void ScreenSessionTell()', 'B211_RARE static void NoteScreenRestart(', 'bool TextInIsGenuine()', 'B211_RARE static void ScreenEchoTell()',
               'B211_RARE static void ScreenOwedOver()', 'FLASHMEM void ScreenOwedStep()', 'B211_RARE static void ScreenSessionAtStart()', 'FLASHMEM static void ScreenMarkLate()', 'B211_RARE static void NoteAnswerOwed()', '@ScreenKeepUp'):
        body = re.sub(r'//[^\n]*', '', lift(MAIN_CPP, 'FLASHMEM void ScreenKeepUp()') if fn.startswith('@') else lift(NEXTION, fn))
        for w in ('CollectReply', 'GetSysValue', 'GetNumberReply', 'GetValue', 'DelayWithDog', 'EndSend', 'delay(', 'while ('):
            if w in body: bad.append('Nextion.h %s ...: it must not wait (%s)' % (fn, w))
    for w in ('GetSysValue', 'CollectReply', 'ScreenCaughtUp', 'while ('):
        if w in sh: bad.append('main.cpp ScreenHasRestarted must not ask or wait itself (%s): ScreenCaughtUp has said that the screen is ready' % w)
    # THE SESSION'S NUMBER IS TOLD IN ONE PLACE (the ninth review): ScreenSessionTell - called after a noted restart (ScreenCaughtUp) and at this board's start
    # (ScreenSessionAtStart), and by nothing else. Whatever else told the screen "ldrcup=" would make a screen that has started again unnoticed "the same" again.
    allc = nxc + re.sub(r'//[^\n]*', '', MAIN_CPP + UTIL + MENU)
    if 'ldrcup=%lu' not in lift(NEXTION, 'FLASHMEM void ScreenSessionTell()') or allc.count('ldrcup=') != 1 or len(re.findall(r'\bScreenSessionTell\(\)', allc)) != 3 \
            or 'ScreenSessionTell();' not in lift(NEXTION, 'B211_RARE static bool ScreenCaughtUp()') or 'ScreenSessionTell();' not in lift(NEXTION, 'B211_RARE static void ScreenSessionAtStart()'):
        bad.append('Nextion.h: the screen is told its session\'s number ("ldrcup=") in ScreenSessionTell and nowhere else - after its restart was noted (ScreenCaughtUp) and at this board\'s start (ScreenSessionAtStart)')
    if allc.count('get ldrcup') != 3 or 'get ldrcup' not in lift(NEXTION, 'B211_RARE static void ScreenEchoTell()') or 'NEXTION.print("get ldrcup");' not in lift(NEXTION, 'FLASHMEM uint8_t ScreenSessionCheck()'):
        bad.append('Nextion.h: the session\'s number is asked for where it is told, in front of every "say this back" (ScreenEchoTell) and by ScreenSessionCheck')
    if len(re.findall(r'NoteScreenRestart\(\s*(?:-3|-4|saidZeroTwice)', allc)) != 1 or 'NoteScreenRestart(saidZeroTwice ? -3 : -4);' not in lift(NEXTION, 'B211_RARE static void ScreenOwedOver()'):
        bad.append('Nextion.h: "it has started again, found by asking" is said in ONE place - ScreenOwedOver: -3 when the screen has twice said 0 for its session\'s number, -4 when it never said that number in the half minute')
    gy = re.sub(r'//[^\n]*', '', lift(UTIL, 'void GetYesOrNo(uint16_t asked)'))
    if not re.search(r"while \(Confirmed\[0\] == '\?'\)\s*\{\s*KickTheDog\(\);\s*CheckForNextionButtonPress\(\);\s*if \(ScreenAnswerOwed\)\s*ScreenOwedStep\(\);", gy) \
            or not re.search(r"const bool silent = ScreenSaysPage && unanswered && \(millis\(\) - unanswered\) > QUESTION_SILENT_MS;\s*if \(ScreenRestartSeen \|\| ScreenMarkCount != asked \|\| silent\)\s*\{\s*Confirmed\[0\] = 'N';\s*closed = true;\s*overtaken = ScreenMarkCount != asked;\s*NoteQuestionClosed\(ScreenRestartSeen \? 1 : silent \? 2 : 0\);\s*if \(silent && !ScreenRestartSeen\)\s*ScreenOwesAnswer\(\);\s*break;", gy) \
            or not re.search(r"--ModalWaits;\s*if \(ScreenMarkCount != asked\)\s*\{\s*if \(!closed\)\s*NoteQuestionClosed\(0\);\s*Confirmed\[0\] = 'N';\s*closed = true;\s*overtaken = true;\s*\}\s*QuestionClosedItself = closed;\s*QuestionOvertaken = overtaken;", gy) or not re.search(r"\{\s*if \(!asked\)\s*asked = ScreenMarkCount;", gy) or not re.search(r"Confirmed\[0\] = '\?';\s*if \(ScreenMarkCount != asked\)\s*Confirmed\[0\] = 'N';\s*\+\+ModalWaits;", gy):
        bad.append('Utilities.h GetYesOrNo: the dog is fed first in every round; a question that waits when the screen restarts, when another page is put up over it, or when the screen has stopped answering, is closed as No - an answer given meanwhile is not its own - and it says how it ended')
    # (the thirteenth review, reviewer A's finding 1) EVERY WAY THE FRONT PAGE COMES UP BY ITSELF BRINGS ITS REASON IN 17 LETTERS, for the line that is kept
    # while the model may fly ("Page 255 -> front: " and 17 letters are the 36 places a kept line has); the restart's second line is 36 at its longest
    callc = re.sub(r'//[^\n]*', '', MAIN_CPP + src('include/Motor_sign.h'))
    calls = re.findall(r'\bLogFrontPageReason\(\s*(?:"(?:[^"\\]|\\.)*"|line)\s*,\s*"((?:[^"\\]|\\.)*)"\s*(?:,\s*kept\s*)?\)\s*;', callc)
    if len(calls) != len(re.findall(r'\bLogFrontPageReason\(', callc)) or len(calls) != 6 or any(not 0 < len(c) <= 17 for c in calls) or len(set(calls)) != 6:
        bad.append('every LogFrontPageReason(...) brings a short reason of its own, 17 letters at most, as its second argument (found: %r of %d calls)' % (calls, len(re.findall(r'\bLogFrontPageReason\(', callc))))
    shw = re.search(r'const char \*word = ([^;]*);', sh); shwords = re.findall(r'"([^"]*)"', shw.group(1)) if shw else []
    if len(shwords) != 11 or any(len(w) > 9 for w in shwords) or not re.search(r'if \(restarts < 999\)\s*\+\+restarts;', sh) or 'snprintf(kept, sizeof(kept), "Screen restart %u: rst=%d %s", (unsigned)restarts, rst, word);' not in sh \
            or not re.search(r'LogFrontPageReason\(line, "screen restart", kept\);', sh):
        bad.append('main.cpp ScreenHasRestarted: its kept line is "Screen restart N: rst=R word" - N to 999, a word of nine letters at most for each cause (36 places in all)')
    lfc = re.sub(r'//[^\n]*', '', src('include/LogFiles.h'))
    if not re.search(r'snprintf\(line, sizeof\(line\), "Page %u -> front: %\.17s", \(unsigned\)CurrentView, brief\);\s*KeepScreenReason\(line, more\);\s*return;', lfc) \
            or not re.search(r'void KeepScreenReason\(const char \*line, const char \*more\)\s*\{\s*if \(more && ScreenReasonsKept \+ 2 > SCREEN_REASONS_MOST\)\s*\{\s*ScreenNotesNotKept = [^;]+;\s*return;\s*\}\s*KeepScreenNote\(line, true\);\s*if \(more\)\s*KeepScreenNote\(more, true\);\s*\}', lfc):
        bad.append('LogFiles.h LogFrontPageReason: while the model may fly - the page left and the short reason, kept; then the second line, if there is one - THE TWO TOGETHER OR NEITHER (KeepScreenReason: the fourteenth review)')
    notes = lfc[lfc.index('FLASHMEM void KeepScreenNote('):lfc.index('FLASHMEM void LogScreenLine(')] + re.sub(r'//[^\n]*', '', NEXTION)
    if 'DeferLogText(' in notes.replace('        DeferLogText(line, true);\n    }\n    else if (ScreenNotesNotKept < 65535)', ''):
        bad.append('LogFiles.h / Nextion.h: what this work says of the screen while the model may fly is kept through KeepScreenNote (its budget) - DeferLogText is called by KeepScreenNote alone there')
    if not re.search(r'if \(!DeferredLogN && !ScreenLinesHeldN && !ScreenLinesNotHeld\)\s*return;', lfc) or not re.search(r'DeferredLogN = 0;\s*DeferredLast\[0\] = 0;\s*if \(!DeferredFullOnly\)\s*ScreenLinesFlushed\(\);\s*ScreenNotesFlushed\(\);\s*CloseLogWriteFile\(\);', lfc) \
            or not re.search(r'if \(DeferredLogN >= 24\)\s*\{\s*DeferredFullOnly = true;\s*FlushDeferredLog\(\);\s*DeferredFullOnly = false;\s*\}', lfc) or len(re.findall(r'DeferredFullOnly = true;', lfc)) != 1:
        bad.append('LogFiles.h FlushDeferredLog: the line kept last is forgotten (the same note behind a writing is a new event), the screen\'s own held lines are written (ScreenLinesFlushed) - but NOT by the writing that a full store forces, in the air (DeferredFullOnly; the sixteenth review: that one is the 24 short lines only) - the notes that found no place are said and their budget begins again (ScreenNotesFlushed)')
    _scr = lift(lfc, 'FLASHMEM void LogScreenLine(const char *t)') + lift(lfc, 'FLASHMEM bool ScreenDyingWords(const char *t)')
    if 'LogText(' in _scr or _scr.count('ScreenLineOut(line, n);') != 2 or not re.search(r'static void ScreenLineOut\(char \*line, int n\)\s*\{\s*if \(!LogMustWait\(\)\)\s*\{\s*LogText\(line, \(uint16_t\)n, true\);\s*return;\s*\}', lfc):
        bad.append('LogFiles.h LogScreenLine / ScreenDyingWords: the screen\'s own lines go through ScreenLineOut - to the card at once only while nothing may fly (the fourteenth review: they were written part by part in flight)')
    # (the thirteenth review, reviewer A's finding 2) THE RADIO'S LONGEST SILENCE IS READ THROUGH radioGapUs() - never the variable itself (what stands open would not count)
    devdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for f in sorted(__import__('glob').glob(os.path.join(devdir, 'test_*', '*.py'))):
        for no, l in enumerate(open(f, encoding='utf-8', errors='replace').read().split('\n'), 1):
            if l.startswith(('static uint64_t lastRadioUs', 'static void radioService()', 'static void radioLook()', 'static uint64_t radioGapUs()', '//', '#')) or 'bad.append(' in l or 're.search(' in l or 're.sub(' in l: continue   # (not this check's own lines)
            if re.search(r'maxRadioGapUs(?!\s*=[^=])', l): bad.append('%s line %d reads maxRadioGapUs itself: read the silence through radioGapUs() (what stands open counts)' % (os.path.relpath(f, devdir), no))
    for name in ('NoteScreenRestart', 'ScreenCaughtUp', 'ScreenSessionTell', 'BoxesHaveNoPage', 'IsKeyboardPage', 'TakeScreenStart', 'RestartWordAt', 'IsMarkKind', 'AfterTextReplies', 'ScreenMarkLate', 'ScreenOwedOver', 'NoteBareRead', 'GluedNumberOk'):
        if name + '(' not in nxc: bad.append('Nextion.h has no ' + name)
    for gone in ('AskScreenSession', 'ScreenSessionCaughtUp', 'ScreenRestartStillTalking', 'ScreenRestartDue', 'ScreenSessionBegin'):
        if gone in nxc or gone in mc: bad.append(gone + ' asked or waited in the main loop (the seventh review): it is to stay gone')
    IDX = os.path.join(os.path.dirname(PAGES_DIR), 'index.json')
    if os.path.isfile(IDX):
        import glob
        pages = {p['id']: p['name'] for p in json.load(open(IDX))['pages']}
        kb = sorted((i, n) for i, n in pages.items() if n.startswith('keybd'))
        ids = [int(x) for x in re.findall(r'#define SCREEN_KEYBOARD_PAGE_[AB] (\d+)', NEXTION)]
        if kb != [(56, 'keybdA'), (57, 'keybdB')] or sorted(ids) != [56, 57]:
            bad.append('the card\'s keyboard pages are not keybdA 56 and keybdB 57, or Nextion.h does not say so: ' + repr(kb) + ' ' + repr(ids))
        # (the ninth review) ... and the two pages that look at their own boxes with no press: each only while the screen's page is its own
        own = {q['name']: q['id'] for q in json.load(open(IDX))['pages'] if q['name'] in ('ModelsView', 'DualRatesView', 'FrontView')}
        said = {n: int(re.search(r'#define ' + d + r' (\d+)', NEXTION).group(1)) for n, d in (('ModelsView', 'SCREEN_MODELS_PAGE'), ('DualRatesView', 'SCREEN_DUALRATES_PAGE'), ('FrontView', 'SCREEN_FRONT_PAGE'))}
        if own != said: bad.append('the card\'s Models, Dual-rates and front pages are not the numbers Nextion.h says (SCREEN_MODELS_PAGE, SCREEN_DUALRATES_PAGE, SCREEN_FRONT_PAGE): ' + repr(own) + ' ' + repr(said))
        allPages = {int(os.path.basename(f)[:-5]): json.load(open(f)) for f in sorted(glob.glob(os.path.join(PAGES_DIR, '*.json')))}
        movers, first, oddEvents = page_scan(allPages)
        if movers != ['keybdA', 'keybdB']:
            bad.append('pages that go to another page BY THEMSELVES must be the two keyboards only: ' + repr(movers))
        if first:
            bad.append('a page prints a word that begins as a reply does (p, q), names FrontView, or looks like one of the screen\'s own: ' + repr(first))
        if oddEvents:
            bad.append('a page of the card has an event of a kind this test does not know (a page_exit script prints between the NEXT page command\'s two markers): ' + repr(oddEvents))
        for what, change in PAGE_SCAN_SELFTEST:                               # (the scan's own test: each of these changes to a copy of page 9 must be SEEN)
            pg = {int(k): v for k, v in json.loads(json.dumps(allPages)).items()}; change(pg[9])
            if page_scan(pg) == (movers, first, oddEvents): bad.append('the scan of the card\'s pages does NOT SEE this any more: ' + what)
        # every word the SCREEN'S OWN firmware sends bare must be one that TextInIsGenuine lets pass (IsScreensOwnWord)
        SCR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(PAGES_DIR))), 'src'); LIB = os.path.join(os.path.dirname(SCR), 'lib')
        own = ('LDRC', 'UKRULES', 'TIME=', 'ldrcpipe=', 'ldrctel ', 'ldrcrep ', 'FrontView')
        sent = set()
        for f in glob.glob(os.path.join(SCR, '*')):
            if not os.path.isfile(f): continue
            for l in open(f, encoding='utf-8', errors='replace').read().split('\n'):
                if 'EMU READY' in l or '[%lu:%s]' in l: continue          # (a bench build's echo, never in a released screen)
                code = l.split('//')[0] if l.strip().startswith('//') else l
                for w in re.findall(r'Serial\.(?:write|print|printf)\(\s*(?:\(const uint8_t \*\)\s*)?"([^"]+)"', code): sent.add(w)
                for w in re.findall(r'bleMailPost\(\s*"([^"]+)"', code): sent.add(w)
                for w in re.findall(r'snprintf\(b, sizeof\(?b\)?, "((?:TIME|%s)[^"]*)"', code):
                    if w.startswith('TIME'): sent.add(w)
                for w in re.findall(r'std::string t = "([^"]+)"', code): sent.add(w)
        for name in ('LDRC_LINK_KNOCK', 'LDRC_RX_UPDATE_WORD', 'LDRC_IMAGE_WORD'):
            for f in glob.glob(os.path.join(LIB, '*', '*.h')):
                m = re.search(r'#define ' + name + r' "([^"]+)"', open(f, encoding='utf-8', errors='replace').read())
                if m: sent.add(m.group(1))
        notown = sorted(w for w in sent if not w.startswith(own))
        if len(sent) < 8 or notown:
            bad.append('the screen\'s firmware sends a bare word that IsScreensOwnWord does not know (it would not be obeyed), or its words were not found: ' + repr(notown) + ' of ' + repr(sorted(sent)))
        texts, oddFiles = screen_texts(os.path.dirname(SCR))
        if oddFiles: bad.append('the screen\'s source folders hold files of a kind the wire pin does not read (look at each: can it put a byte on the wire?): ' + repr(oddFiles))
        now, nowWords = wire_sites(texts)
        ini = open(os.path.join(os.path.dirname(SCR), 'platformio.ini'), encoding='utf-8', errors='replace').read()
        for why in ini_problems(ini):
            bad.append('the screen\'s platformio.ini: the console IS the wire to this board - its core\'s own log lines must stay off (CORE_DEBUG_LEVEL=0, once), the port must be the UART (ARDUINO_USB_CDC_ON_BOOT=0), and no build may echo its commands (EMU_ECHO): ' + why)
        for what, old, new in INI_SELFTEST:                                   # (the look at platformio.ini has its own test too)
            if ini.count(old) < 1: bad.append('the test of the look at platformio.ini: the line to change is not there any more (%s)' % what)
            elif ini_problems(ini.replace(old, new, 1)) == ini_problems(ini): bad.append('the look at the screen\'s platformio.ini does NOT SEE this any more: ' + what)
        libBad, libNote, libLooked = lib_problems(os.path.dirname(SCR), ini)  # (the eleventh review: the libraries the screen is built with, and its platformio.ini whole)
        bad += libBad
        if libNote: print(libNote)
        if True:   # (the pin's own test runs whether or not a build stands beside the tree: the comparison is the same one)
            pinned = [tuple(x) for x in LIB_PINS]
            for what, change, inichange in LIB_SELFTEST:
                if change:
                    if not pins_differ(change(list(pinned)), pinned): bad.append('the pin of the screen\'s libraries does NOT SEE this any more: ' + what)
                else:
                    if ini.count(inichange[0]) < 1: bad.append('the test of the pin of platformio.ini: the line to change is not there any more (%s)' % what)
                    elif lib_problems(os.path.dirname(SCR), ini.replace(inichange[0], inichange[1], 1))[0] == libBad: bad.append('the pin of the screen\'s platformio.ini does NOT SEE this any more: ' + what)
        if True:   # ... and the walk through the screen's folders: a made-up project, with a writer in every kind of place reviewer A put one
            import shutil
            fake = tempfile.mkdtemp()
            for rel, text in (('src/a.h', 'x'), ('include/hello_device.h', 'static void helloPoll() { Serial.write((const uint8_t *) "pong", 4); }'), ('lib/LdrcCli/src/extra.cpp', 'void cliExtra() { Serial.print("page 9"); }'),
                              ('lib/Hello/Hello.hpp', 'static inline void helloSay() { Serial.print("quiet"); }'), ('lib/LdrcCli/extra.inc', 'static void cliInc() { Serial.print("fresh"); }'),
                              ('include/secrets.h', 'never opened'), ('lib/Hello/table.bin', 'what is this?'), ('lib/A/same.h', 'one'), ('lib/B/same.h', 'two')):
                os.makedirs(os.path.dirname(os.path.join(fake, rel)), exist_ok=True); open(os.path.join(fake, rel), 'w').write(text)
            ft, fodd = screen_texts(fake); fsites = wire_sites(ft)[0]; shutil.rmtree(fake)
            if sorted(ft) != ['Hello.hpp', 'a.h', 'extra.cpp', 'extra.inc', 'hello_device.h', os.path.join('lib', 'A', 'same.h'), os.path.join('lib', 'B', 'same.h')] or fodd != [os.path.join('lib', 'Hello', 'table.bin')] or len(fsites) != 4:
                bad.append('the wire pin does not read every file of the screen\'s source any more (its src, lib and include, at any depth; not secrets.h): ' + repr(sorted(ft)) + ' ' + repr(fodd) + ' ' + repr(fsites))
        for what, f, old, new in WIRE_SELFTEST:                               # THE PIN'S OWN TEST: each of these changes to a copy of the screen's source must be SEEN
            if f not in texts or texts[f].count(old) < 1: bad.append('the wire pin\'s own test: the text to change is not in the screen\'s %s any more (%s)' % (f, what)); continue
            t2 = dict(texts); t2[f] = texts[f].replace(old, new, 1)
            if wire_sites(t2) == (now, nowWords): bad.append('the wire pin does NOT SEE this change to the screen any more: ' + what)
        pages0 = {int(os.path.basename(f)[:-5]): json.load(open(f)) for f in sorted(glob.glob(os.path.join(PAGES_DIR, '*.json')))}
        for what, change in PAGE_SELFTEST:                                    # ... and the page scan's: each of these changes to a copy of page 9 must be SEEN
            pg = json.loads(json.dumps(pages0)); pg = {int(k): v for k, v in pg.items()}; change(pg[9])
            codes, wordsNow, _ = page_prints(pg)
            if codes == PAGE_CODES_KNOWN and sorted(set(wordsNow)) == sorted(set(page_prints(pages0)[1])): bad.append('the scan of what a page prints as it comes up does NOT SEE this any more: ' + what)
        if sorted(now) != sorted(WIRE_SITES):
            gone = [s for s in WIRE_SITES if s not in now]; new = [s for s in now if s not in WIRE_SITES]
            bad.append('the screen\'s firmware writes to the wire in a place this test does not know, or no longer as it did (look at what each says, then bring WIRE_SITES up to date): NEW ' + repr(new) + ' GONE ' + repr(gone))
        if nowWords != sorted(WIRE_WORDS):
            bad.append('the text in the screen\'s source that begins as one of its own words does has changed (look, then bring WIRE_WORDS up to date): NEW ' + repr([w for w in nowWords if w not in WIRE_WORDS]) + ' GONE ' + repr([w for w in WIRE_WORDS if w not in nowWords]))
        iw = lift(NEXTION, 'B211_RARE static bool IsScreensOwnWord(')
        for o in own:
            if '"%s"' % o not in iw: bad.append('IsScreensOwnWord does not name ' + o)
    notes = [b for b in bad if b.startswith('(')]; bad = [b for b in bad if not b.startswith('(')]
    for n in notes: print(n)
    for b in bad: print('FAIL: ' + b)
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, 't.cpp'); open(cpp, 'w').write(program())
    r = subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-Wno-unused-but-set-variable',
                        '-funsigned-char',   # (as the Teensy: a plain char is unsigned there, and a reply's bytes are summed as chars)
                        '-fsanitize=address,undefined', '-o', os.path.join(d, 'test_stalepress'), cpp], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-6000:] + '\ncompile failed')
    rc = subprocess.run([os.path.join(d, 'test_stalepress')] + [a for a in sys.argv[1:] if a == '--show']).returncode
    return 1 if (rc or bad) else 0

if __name__ == '__main__': sys.exit(main())
