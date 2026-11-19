"""The scenes of dev/test_wholepage are built on dev/test_noanswer (which is built on dev/test_stalepress): the REAL routines lifted
out of the headers, test_noanswer's pretend screen and its extra buttons, and each scene file's own stubs and main."""
import importlib.util, os, subprocess, sys, tempfile
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('noanswer_for_wholepage', os.path.join(os.path.dirname(HERE), 'test_noanswer', 'test_noanswer.py'))
n = importlib.util.module_from_spec(spec); spec.loader.exec_module(n)
m = n.m

# (the fifteenth review) "the read failed - the page is left": the REAL RfLeaveNotRead (RF_SaveNow.h) and a stand-in for the menu it opens. A scene whose
# page can fail a read puts LEAVE in front of the page's own code, and gives its pretend screen a page "RFView".
LEAVE = ('#ifndef ROTORFLIGHTVIEW\n#define ROTORFLIGHTVIEW %s\n#endif\n' % m.define('ROTORFLIGHTVIEW')) + r"""
static int menuOpened = 0; static bool menuShut = false;   // RF_RotorFlight.h RotorFlightStart: the menu - or, the motor switch on (menuShut), nothing at all
void RotorFlightStart() { if (menuShut) return; SendCommand((char *) "page RFView"); CurrentView = ROTORFLIGHTVIEW; ++menuOpened; }
// (the sixteenth review) no box that waits while the model may fly: PipeHttp.h RfMayFly / RfSayQuietly / RfBoxOrQuiet stood in for; the guide's "not read"
static bool RfHomeNotRead = false, rfMayFlyNow = false; static int quietSaid = 0;
static bool RfMayFly() { return rfMayFlyNow; } static void RfSayQuietly(const char *) { ++quietSaid; }
static void RfBoxOrQuiet(const char *page, const char *msg) { if (RfMayFly()) { RfLeaveAfterSave = false; RfSayQuietly(msg); return; } MsgBox((char *) page, (char *) msg); }
""" + __import__('re').search(r'^#define RF_NOT_READ_LINE[^\n]*', m.release(m.src('include/RF_SaveNow.h')), __import__('re').M).group(0) + '\n' \
    + __import__('re').search(r'^#define RF_NOT_SAVED_LINE[^\n]*', m.release(m.src('include/RF_SaveNow.h')), __import__('re').M).group(0) + '\n' \
    + m.lift(m.release(m.src('include/RF_SaveNow.h')), 'inline void RfMenuFromPage(bool have)') \
    + m.lift(m.release(m.src('include/RF_SaveNow.h')), 'bool RfLeaveNotRead(char *msg)')

def build_run(name, scenes, extra='', more_lifts=(), more_defines=(), args=None, sanitize=True, timeout=1200, label='test_wholepage'):
    text = m.program()
    head = text[:text.index('int main(int argc, char **argv)')]
    defs = ''.join('#define %s %s\n' % (d, m.define(d)) for d in tuple(n.DEFINES) + tuple(more_defines))
    lifts = ''.join(src if nm is None else m.lift(src, nm) for src, nm in list(n.LIFTS) + list(more_lifts))   # (nm None: a piece of the source as it stands)
    prog = head + defs + n.EXTRA.replace('@LIFTS@', lifts) + extra + n.MAIN_HEAD + scenes + n.MAIN_TAIL.replace('test_noanswer:', label + ' (' + name + '):')
    d = tempfile.mkdtemp()
    cpp = os.path.join(d, name + '.cpp'); open(cpp, 'w').write(prog)
    exe = os.path.join(d, name)
    cmd = ['clang++', '-std=c++14', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-format', '-Wno-unused-but-set-variable', '-funsigned-char']
    cmd += ['-fsanitize=address,undefined'] if sanitize else ['-O1']
    r = subprocess.run(cmd + ['-o', exe, cpp], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-8000:]); raise SystemExit('compile failed: ' + name)
    if args is None: args = [a for a in sys.argv[1:] if a == '--show']
    p = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=timeout)
    print(p.stdout[-20000:], end='')
    if p.stderr: print(p.stderr[-6000:], end='')
    return p.returncode
