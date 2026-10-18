#!/usr/bin/env python3
"""The films' helicopter pictures (18 Oct 2026), rendered from the receiver's own 3D model (RXV2 data/diagnostics.html,
buildHeli3D: the SAB Goblin painted as the factory photograph) by headless Chrome, so the films show the same helicopter
as the receiver's View channels page instead of a flat drawing. Malcolm: "Take your time with this job because it needs
to be imaginative, well executed, informative and entertaining!"

   python3 make_sprites.py [RXV2_DIR] [WORK_DIR]
writes heli3d/<view>.png (transparent, cropped) + heli3d/sprites.json (where the main shaft is in each picture, and its
pixels per model unit). Views: top (nose up, no main rotor), top_disc (the spinning main rotor alone, from above), side
(nose right, slightly from above), front (nose towards you), card (three-quarter, for the title cards). illus.py turns
and places them. The model's code is copied out of diagnostics.html each run, so the films follow any change to it."""
import gzip, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
RX = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/RXV2')
WORK = sys.argv[2] if len(sys.argv) > 2 else '/Volumes/2TB SSD/ClaudeScratch/films/heli3d'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
os.makedirs(WORK, exist_ok=True)

src = open(os.path.join(RX, 'data', 'diagnostics.html')).read()
a = src.index('    const scene = new THREE.Scene();', src.index('function buildHeli3D()'))
b = src.index('    heliQuat = new THREE.Quaternion();', a)
model = src[a:b]
# (its own camera and renderer lines are replaced below: ours is orthographic, at a fixed size, kept for the screenshot)
model = model.replace('const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });',
                      'const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });')
model = model.replace('renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));', 'renderer.setPixelRatio(1);')
model = model.replace('sun.shadow.mapSize.set(1024, 1024);', 'sun.shadow.mapSize.set(4096, 4096);')
three = gzip.open(os.path.join(RX, 'data', 'three.min.js.gz')).read().decode()

W, H = 3200, 2000
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:transparent;overflow:hidden}
canvas{display:block}</style><script>%s</script></head><body><canvas id="c" width="%d" height="%d"></canvas><script>
const P = new URLSearchParams(location.search), view = P.get('view');
const canvas = document.getElementById('c'), wrap = {clientWidth: %d, clientHeight: %d};
%s
// ---- ours: the pose, the rotor, the camera
const S = 2.0;                                              // (half the picture's height, in model units)
const cam = view === 'card' ? new THREE.PerspectiveCamera(24, %d / %d, 0.1, 50)
                            : new THREE.OrthographicCamera(-S * %d / %d, S * %d / %d, S, -S, 0.1, 50);
const T = new THREE.Vector3(0, 0.1, 0);                      // (the main shaft's foot: heli.position)
const E = THREE.MathUtils.degToRad(+(P.get('elev') || 0));
if (view === 'top' || view === 'top_disc') { cam.position.set(0, 12, 0); cam.up.set(1, 0, 0); }
else if (view === 'side') { cam.position.set(0, 12 * Math.sin(E), 12 * Math.cos(E)); }
else if (view === 'front') { cam.position.set(12 * Math.cos(E), 12 * Math.sin(E), 0); }
else { cam.position.set(3.1, 1.7, 3.7); }
cam.position.add(T); cam.lookAt(T); cam.updateProjectionMatrix();
ground.visible = false;
const LONG = 1.42 / 1.2 / 0.88;                             // (blades lengthened: the tail rotor just beyond their tips, as on the real thing)
rotorGrp.scale.x = LONG; mainDisc.scale.set(LONG, LONG, 1); mainRim.scale.set(LONG, LONG, 1);
const discOn = view === 'top_disc' || view === 'top' ? false : true;
mainBlades.forEach(o => o.visible = view === 'side' || view === 'front' || view === 'card');
mainDisc.visible = mainRim.visible = view === 'top_disc';                 // (illus.py draws the spinning discs itself, pale for the films' dark pages)
tailBlades.forEach(o => o.visible = view !== 'top_disc' && view !== 'side');
tailDisc.visible = tailRim.visible = false;
if (view === 'side') rotorGrp.rotation.y = 0;                // (the blade across the picture)
if (view === 'front') rotorGrp.rotation.y = Math.PI / 2;
if (view === 'card') rotorGrp.rotation.y = 0.5;
if (view === 'top_disc') heli.traverse(o => { if (o.isMesh && o !== mainDisc && o !== mainRim) o.visible = false; });
renderer.render(scene, cam);
</script></body></html>"""
page = PAGE % (three, W, H, W, H, model, W, H, W, H, W, H)
html = os.path.join(WORK, 'render.html'); open(html, 'w').write(page)

VIEWS = {'top': '', 'top_disc': '', 'side': '&elev=7', 'front': '&elev=7', 'card': ''}
from PIL import Image
meta = {}
for v, extra in VIEWS.items():
    png = os.path.join(WORK, v + '_full.png')
    if os.path.exists(png): os.remove(png)
    pr = subprocess.Popen([CHROME, '--headless=new', '--user-data-dir=' + os.path.join(WORK, 'chrome-profile'), '--no-first-run',
                           '--hide-scrollbars', '--default-background-color=00000000', '--window-size=%d,%d' % (W, H),
                           '--screenshot=' + png, '--virtual-time-budget=4000', 'file://' + html + '?view=' + v + extra],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time(); last = -1                                # (headless Chrome writes the picture, then does not always exit: wait for
    while time.time() - t0 < 90:                              #  the file to stop growing, then end it)
        time.sleep(0.5)
        n = os.path.getsize(png) if os.path.exists(png) else -1
        if n > 0 and n == last: break
        last = n
    pr.kill(); pr.wait()
    im = Image.open(png).convert('RGBA'); box = im.getbbox()
    print(v, im.size, box)
    meta[v] = {'shaft': [W / 2 - box[0], H / 2 - box[1]], 'ppu': H / 4.0, 'size': [box[2] - box[0], box[3] - box[1]]}   # (orthographic, S = 2: the shaft's foot at the picture's centre)
    im.crop(box).save(os.path.join(HERE, v + '.png'))
json.dump(meta, open(os.path.join(HERE, 'sprites.json'), 'w'), indent=1)
