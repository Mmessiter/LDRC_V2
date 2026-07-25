# TXV16 MEGA-SURGEON — the case as software. Silent. -> txv16_report.json
# Opens TXV12a, saves as TXV16, then applies EVERY feature parameterized by
# the new PCB offset (pattern centred in the case) + 6 mm standoffs:
#   FRONT: USB slot + chamfer, 3 cooling vents, signature, 2808 pinhole +
#          ring, 2 hook pockets (slanted shoulders)
#   BACK:  2 hook tabs
#   SUPPORT: old nRF pedestal removed (enlarged box), 4 NEW PCB mounting
#          holes (centred pattern), new nRF pedestal with cable-tie tunnel
# All lengths cm. by Claude and Malcolm, July 2026.
import adsk.core, adsk.fusion, traceback, json, os

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv16_report.json')

OFF = 1.91                 # PCB shift right: pattern centre -44.3 -> -25.2 (case centre)
STANDOFF = 0.60            # 6 mm (2808 underside-mount decision)
SOCKET_H = 0.85            # 2x4 socket stack NOMINAL - confirm with callipers!
PLATE_Z = 1.707
BOARD_TOP = PLATE_Z + STANDOFF + 0.16

WALL_IN_Y, WALL_OUT_Y = -12.950, -13.250
SLOT_CX = -3.615 + OFF     # USB J1
SLOT_CZ = PLATE_Z + STANDOFF - 0.16
SLOT_W, SLOT_H_, SLOT_R, CHAMFER = 1.40, 0.75, 0.30, 0.08
VENT_XS = [SLOT_CX - 1.6, SLOT_CX, SLOT_CX + 1.6]
VENT_Z, VENT_W, VENT_H, VENT_R = 3.00, 1.00, 0.30, 0.14
SIG_TEXT = 'TXV16 - Claude + Malcolm - 2026'
SIG_CX, SIG_CZ, SIG_H = 3.0, 3.30, 0.45
PIN_X = -7.415 + OFF       # 2808 at kicad(112,181)
PIN_Z, PIN_R = 2.60, 0.09
RING_R, RING_W, RING_DEPTH = 0.30, 0.06, 0.03
SIDES = [
    {'A': (-6.30, 6.55), 's': (0.9683, 0.2501), 'n': (-0.2501, 0.9683)},
    {'A': ( 1.45, 6.50), 's': (0.9683, -0.2501), 'n': (0.2501, 0.9683)},
]
POCKET_HALF, TAB_HALF = 1.40, 1.15
POCKET_Z0, POCKET_Z1, POCKET_DEPTH = 3.90, 4.055, 0.08
TONGUE_Z, TAB_T, TAB_ROOT, TAB_TIP, RIDGE_OFF = 3.95, 0.085, -0.45, 0.05, -0.10
OLD_PED = (-5.36, -3.50, -3.73, -2.61)     # x0,x1,y0,y1 enlarged removal box
HOLES = [(-8.25 + OFF, -12.55), (-0.61 + OFF, -12.55),
         (-8.25 + OFF, -4.06), (-0.61 + OFF, -4.06)]   # new PCB pattern (old holes stay as spares)
HOLE_R, CBORE_R, CBORE_D = 0.24, 0.36, 0.25
NRF_TIP_X = (-6.455 + OFF) - 3.40          # socket + nominal module extension
PED = {'x0': NRF_TIP_X - 0.55, 'x1': NRF_TIP_X + 0.55,
       'y0': -5.80, 'y1': -4.20,
       'top': PLATE_Z + STANDOFF + 0.16 + SOCKET_H - 0.005,
       'tun_w': 0.50, 'tun_roof_drop': 0.15, 'tun_floor': 2.20}


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': []}
    F = adsk.fusion

    def step(m): rep['steps'].append(m)
    def warn(m): rep['warnings'].append(m)

    def smallProfileAt(sk, pt3):
        c = sk.modelToSketchSpace(adsk.core.Point3D.create(*pt3))
        best, bestA = None, 1e9
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            bb = pr.boundingBox
            if (bb.minPoint.x - 0.01 <= c.x <= bb.maxPoint.x + 0.01 and
                    bb.minPoint.y - 0.01 <= c.y <= bb.maxPoint.y + 0.01):
                a = pr.areaProperties().area
                if a < bestA:
                    best, bestA = pr, a
        return best

    def rect(sk, corners):
        pts = []
        for (x, y, z) in corners:
            p = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, z))
            pts.append(adsk.core.Point3D.create(p.x, p.y, 0))
        return sk.sketchCurves.sketchLines.addThreePointRectangle(pts[0], pts[1], pts[2])

    def filletRect(sk, r, radius):
        try:
            lines = [r.item(i) for i in range(4)]
            for i in range(4):
                l1, l2 = lines[i], lines[(i + 1) % 4]
                sk.sketchCurves.sketchArcs.addFillet(
                    l1, l1.endSketchPoint.geometry, l2, l2.startSketchPoint.geometry, radius)
        except Exception:
            pass

    def cutDist(comp, prof, body, dists):
        ext = comp.features.extrudeFeatures
        for d in dists:
            inp = ext.createInput(prof, F.FeatureOperations.CutFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(d))
            inp.participantBodies = [body]
            try:
                ext.add(inp)
                return d
            except Exception:
                continue
        return None

    try:
        doc = app.activeDocument
        folder = doc.dataFile.parentFolder
        src = None
        for i in range(folder.dataFiles.count):
            df = folder.dataFiles.item(i)
            if df.name == 'TXV12a':
                src = df
        if not src:
            rep['error'] = 'TXV12a not found in folder'
            raise SystemExit
        if not doc.name.startswith('TXV12a'):
            app.documents.open(src, True)
            adsk.doEvents()
            doc = app.activeDocument
        if not doc.saveAs('TXV16', folder, 'TXV16: centred PCB, full regenerated feature set - by Claude', ''):
            rep['error'] = 'saveAs TXV16 failed'
            raise SystemExit
        adsk.doEvents()
        design = F.Design.cast(app.activeProduct)
        step('TXV16 created from TXV12a')

        root = design.rootComponent
        bodies = {}
        for b in root.bRepBodies:
            bodies[b.name] = b
        for occ in root.allOccurrences:
            for b in occ.bRepBodies:
                bodies.setdefault(b.name, b)
        front = bodies.get('TX_FRONT12a'); back = bodies.get('TX_BACK12a'); sup = bodies.get('TX_SUPPORT12')
        if not front or not back or not sup:
            rep['error'] = 'bodies missing: %s' % list(bodies)
            raise SystemExit

        def wallFace(body, yT, nyWant):
            best, bestA = None, 0
            for f in body.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if not pl:
                    continue
                if abs(pl.normal.y - nyWant) > 0.1 or abs(f.pointOnFace.y - yT) > 0.05:
                    continue
                if f.area > bestA:
                    best, bestA = f, f.area
            return best

        comp = front.parentComponent

        # ---- 1) USB slot ----------------------------------------------------
        inner = wallFace(front, WALL_IN_Y, 1.0)
        sk = comp.sketches.add(inner)
        r = rect(sk, [(SLOT_CX - SLOT_W/2, WALL_IN_Y, SLOT_CZ - SLOT_H_/2),
                      (SLOT_CX + SLOT_W/2, WALL_IN_Y, SLOT_CZ - SLOT_H_/2),
                      (SLOT_CX + SLOT_W/2, WALL_IN_Y, SLOT_CZ + SLOT_H_/2)])
        filletRect(sk, r, SLOT_R)
        prof = smallProfileAt(sk, (SLOT_CX, WALL_IN_Y, SLOT_CZ))
        if prof and cutDist(comp, prof, front, (-0.35, 0.35)) is not None:
            step('USB slot cut at X %.2f Z %.2f' % (SLOT_CX*10, SLOT_CZ*10))
        else:
            warn('USB slot failed')

        # chamfer its outer rim
        try:
            outer = wallFace(front, WALL_OUT_Y, -1.0)
            edges = adsk.core.ObjectCollection.create()
            for lp in outer.loops:
                if lp.isOuter:
                    continue
                bb = None
                for e in lp.edges:
                    ebb = e.boundingBox
                    if bb is None:
                        bb = [ebb.minPoint.x, ebb.maxPoint.x, ebb.minPoint.z, ebb.maxPoint.z]
                    else:
                        bb = [min(bb[0], ebb.minPoint.x), max(bb[1], ebb.maxPoint.x),
                              min(bb[2], ebb.minPoint.z), max(bb[3], ebb.maxPoint.z)]
                cx, cz = (bb[0]+bb[1])/2, (bb[2]+bb[3])/2
                if abs(cx - SLOT_CX) < 0.3 and abs(cz - SLOT_CZ) < 0.3:
                    for e in lp.edges:
                        edges.add(e)
            if edges.count >= 4:
                ch = comp.features.chamferFeatures
                ci = ch.createInput2()
                ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    edges, adsk.core.ValueInput.createByReal(CHAMFER), False)
                ch.add(ci)
                step('slot rim chamfered')
            else:
                warn('chamfer loop not found')
        except Exception:
            warn('chamfer failed: ' + traceback.format_exc(limit=1))

        # ---- 2) vents -------------------------------------------------------
        try:
            inner = wallFace(front, WALL_IN_Y, 1.0)
            sk = comp.sketches.add(inner)
            for vx in VENT_XS:
                rr = rect(sk, [(vx - VENT_W/2, WALL_IN_Y, VENT_Z - VENT_H/2),
                               (vx + VENT_W/2, WALL_IN_Y, VENT_Z - VENT_H/2),
                               (vx + VENT_W/2, WALL_IN_Y, VENT_Z + VENT_H/2)])
                filletRect(sk, rr, VENT_R)
            profs = adsk.core.ObjectCollection.create()
            for vx in VENT_XS:
                p = smallProfileAt(sk, (vx, WALL_IN_Y, VENT_Z))
                if p:
                    profs.add(p)
            if profs.count == 3:
                ext = comp.features.extrudeFeatures
                inp = ext.createInput(profs, F.FeatureOperations.CutFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-0.35))
                inp.participantBodies = [front]
                try:
                    ext.add(inp)
                except Exception:
                    inp2 = ext.createInput(profs, F.FeatureOperations.CutFeatureOperation)
                    inp2.setDistanceExtent(False, adsk.core.ValueInput.createByReal(0.35))
                    inp2.participantBodies = [front]
                    ext.add(inp2)
                step('3 vents cut around X %.1f' % (SLOT_CX*10))
            else:
                warn('vent profiles %d/3' % profs.count)
        except Exception:
            warn('vents failed: ' + traceback.format_exc(limit=1))

        # ---- 3) signature ---------------------------------------------------
        try:
            outer = wallFace(front, WALL_OUT_Y, -1.0)
            sk = comp.sketches.add(outer)
            def flat(x, z):
                p = sk.modelToSketchSpace(adsk.core.Point3D.create(x, WALL_OUT_Y, z))
                return adsk.core.Point3D.create(p.x, p.y, 0)
            c1 = flat(SIG_CX - 3.6, SIG_CZ - SIG_H/2 - 0.1)
            c2 = flat(SIG_CX + 3.6, SIG_CZ + SIG_H/2 + 0.1)
            lo = adsk.core.Point3D.create(min(c1.x, c2.x), min(c1.y, c2.y), 0)
            hi = adsk.core.Point3D.create(max(c1.x, c2.x), max(c1.y, c2.y), 0)
            ti = sk.sketchTexts.createInput2(SIG_TEXT, SIG_H * 0.6)
            ti.setAsMultiLine(lo, hi,
                              adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                              adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
            st = sk.sketchTexts.add(ti)
            pc = adsk.core.ObjectCollection.create(); pc.add(st)
            ext = comp.features.extrudeFeatures
            inp = ext.createInput(pc, F.FeatureOperations.CutFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-0.04))
            inp.participantBodies = [front]
            try:
                ext.add(inp)
            except Exception:
                inp2 = ext.createInput(pc, F.FeatureOperations.CutFeatureOperation)
                inp2.setDistanceExtent(False, adsk.core.ValueInput.createByReal(0.04))
                inp2.participantBodies = [front]
                ext.add(inp2)
            step('signature engraved')
        except Exception:
            warn('signature failed: ' + traceback.format_exc(limit=1))

        # ---- 4) 2808 pinhole + ring ----------------------------------------
        try:
            inner = wallFace(front, WALL_IN_Y, 1.0)
            sk = comp.sketches.add(inner)
            c = sk.modelToSketchSpace(adsk.core.Point3D.create(PIN_X, WALL_IN_Y, PIN_Z))
            c = adsk.core.Point3D.create(c.x, c.y, 0)
            sk.sketchCurves.sketchCircles.addByCenterRadius(c, PIN_R)
            prof = smallProfileAt(sk, (PIN_X, WALL_IN_Y, PIN_Z))
            if prof and cutDist(comp, prof, front, (-0.35, 0.35)) is not None:
                step('pinhole at X %.1f' % (PIN_X*10))
            else:
                warn('pinhole failed')
            outer = wallFace(front, WALL_OUT_Y, -1.0)
            sk2 = comp.sketches.add(outer)
            c2 = sk2.modelToSketchSpace(adsk.core.Point3D.create(PIN_X, WALL_OUT_Y, PIN_Z))
            c2 = adsk.core.Point3D.create(c2.x, c2.y, 0)
            sk2.sketchCurves.sketchCircles.addByCenterRadius(c2, RING_R)
            sk2.sketchCurves.sketchCircles.addByCenterRadius(c2, RING_R - RING_W)
            ring, ra = None, 1e9
            for i in range(sk2.profiles.count):
                pr = sk2.profiles.item(i)
                bb = pr.boundingBox
                if abs((bb.maxPoint.x - bb.minPoint.x) - 2*RING_R) < 0.05:
                    a = pr.areaProperties().area
                    if a < ra:
                        ring, ra = pr, a
            if ring and cutDist(comp, ring, front, (-RING_DEPTH, RING_DEPTH)) is not None:
                step('ring marker engraved')
        except Exception:
            warn('pinhole/ring failed: ' + traceback.format_exc(limit=1))

        # ---- 5) hook pockets (front slanted ridges) -------------------------
        try:
            ridges = []
            for f in front.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if (pl and pl.normal.y < -0.9 and abs(pl.normal.z) < 0.1 and
                        10.0 <= f.area * 100 <= 250 and 3.85 <= f.pointOnFace.z <= 4.12):
                    ridges.append(f)
            pockets = 0
            for side in SIDES:
                ax, ay = side['A']; sx, sy = side['s']
                rf = None
                for f in ridges:
                    bb = f.boundingBox
                    if bb.minPoint.x - 0.1 <= ax <= bb.maxPoint.x + 0.1:
                        rf = f
                if not rf:
                    continue
                sk = comp.sketches.add(rf)
                rect(sk, [(ax - sx*POCKET_HALF, ay - sy*POCKET_HALF, POCKET_Z0),
                          (ax + sx*POCKET_HALF, ay + sy*POCKET_HALF, POCKET_Z0),
                          (ax + sx*POCKET_HALF, ay + sy*POCKET_HALF, POCKET_Z1)])
                prof = smallProfileAt(sk, (ax, ay, (POCKET_Z0+POCKET_Z1)/2))
                if prof and cutDist(comp, prof, front, (-POCKET_DEPTH, POCKET_DEPTH)) is not None:
                    pockets += 1
            step('hook pockets: %d' % pockets)
        except Exception:
            warn('pockets failed: ' + traceback.format_exc(limit=1))

        # ---- 6) hook tabs (back tongue) -------------------------------------
        try:
            bcomp = back.parentComponent
            tongues = []
            for f in back.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if (pl and abs(abs(pl.normal.z) - 1.0) < 0.1 and
                        abs(f.pointOnFace.z - TONGUE_Z) < 0.03 and
                        10.0 <= f.area * 100 <= 250 and f.pointOnFace.y > 5.0):
                    tongues.append((f, pl))
            tabs = 0
            for side in SIDES:
                ax, ay = side['A']; sx, sy = side['s']; nx, ny = side['n']
                tf, tpl = None, None
                for f, pl in tongues:
                    bb = f.boundingBox
                    if bb.minPoint.x - 0.1 <= ax <= bb.maxPoint.x + 0.1:
                        tf, tpl = f, pl
                if not tf:
                    continue
                sk = bcomp.sketches.add(tf)
                r0x, r0y = ax + nx*(RIDGE_OFF+TAB_ROOT), ay + ny*(RIDGE_OFF+TAB_ROOT)
                r1x, r1y = ax + nx*TAB_TIP, ay + ny*TAB_TIP
                rect(sk, [(r0x - sx*TAB_HALF, r0y - sy*TAB_HALF, TONGUE_Z),
                          (r0x + sx*TAB_HALF, r0y + sy*TAB_HALF, TONGUE_Z),
                          (r1x + sx*TAB_HALF, r1y + sy*TAB_HALF, TONGUE_Z)])
                prof = smallProfileAt(sk, ((r0x+r1x)/2, (r0y+r1y)/2, TONGUE_Z))
                if not prof:
                    continue
                dist = -TAB_T if tpl.normal.z < 0 else TAB_T
                ext = bcomp.features.extrudeFeatures
                for d in (dist, -dist):
                    inp = ext.createInput(prof, F.FeatureOperations.JoinFeatureOperation)
                    inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(d))
                    inp.participantBodies = [back]
                    try:
                        ext.add(inp)
                        tabs += 1
                        break
                    except Exception:
                        continue
            step('hook tabs: %d' % tabs)
        except Exception:
            warn('tabs failed: ' + traceback.format_exc(limit=1))

        # ---- 7) support: remove old pedestal, new holes, new pedestal ------
        try:
            scomp = sup.parentComponent
            plate, bestA = None, 0
            for f in sup.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if pl and abs(pl.normal.z - 1.0) < 0.05 and abs(f.pointOnFace.z - PLATE_Z) < 0.03:
                    if f.area > bestA:
                        plate, bestA = f, f.area
            sk = scomp.sketches.add(plate)
            x0, x1, y0, y1 = OLD_PED
            rect(sk, [(x0, y0, PLATE_Z), (x1, y0, PLATE_Z), (x1, y1, PLATE_Z)])
            prof = smallProfileAt(sk, ((x0+x1)/2, (y0+y1)/2, PLATE_Z))
            ext = scomp.features.extrudeFeatures
            inp = ext.createInput(prof, F.FeatureOperations.CutFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(1.80))
            inp.participantBodies = [sup]
            ext.add(inp)
            step('old pedestal removed')

            # new mounting holes (through + counterbore from below)
            plate = None; bestA = 0
            for f in sup.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if pl and abs(pl.normal.z - 1.0) < 0.05 and abs(f.pointOnFace.z - PLATE_Z) < 0.03:
                    if f.area > bestA:
                        plate, bestA = f, f.area
            sk = scomp.sketches.add(plate)
            hp = []
            for (hx, hy) in HOLES:
                c = sk.modelToSketchSpace(adsk.core.Point3D.create(hx, hy, PLATE_Z))
                c = adsk.core.Point3D.create(c.x, c.y, 0)
                sk.sketchCurves.sketchCircles.addByCenterRadius(c, HOLE_R)
            profs = adsk.core.ObjectCollection.create()
            for (hx, hy) in HOLES:
                p = smallProfileAt(sk, (hx, hy, PLATE_Z))
                if p:
                    profs.add(p)
            if profs.count == 4:
                inp = ext.createInput(profs, F.FeatureOperations.CutFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-0.30))
                inp.participantBodies = [sup]
                ext.add(inp)
                step('4 new PCB mounting holes (pattern centred)')
            else:
                warn('mount hole profiles %d/4' % profs.count)

            # counterbores from the underside
            under, bestA = None, 0
            for f in sup.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if pl and abs(pl.normal.z + 1.0) < 0.05 and abs(f.pointOnFace.z - (PLATE_Z - 0.25)) < 0.05:
                    if f.area > bestA:
                        under, bestA = f, f.area
            if under:
                sk = scomp.sketches.add(under)
                for (hx, hy) in HOLES:
                    c = sk.modelToSketchSpace(adsk.core.Point3D.create(hx, hy, PLATE_Z - 0.25))
                    c = adsk.core.Point3D.create(c.x, c.y, 0)
                    sk.sketchCurves.sketchCircles.addByCenterRadius(c, CBORE_R)
                cb = adsk.core.ObjectCollection.create()
                for (hx, hy) in HOLES:
                    p = smallProfileAt(sk, (hx, hy, PLATE_Z - 0.25))
                    if p:
                        cb.add(p)
                if cb.count == 4:
                    inp = ext.createInput(cb, F.FeatureOperations.CutFeatureOperation)
                    for d in (-0.20, 0.20):
                        i2 = ext.createInput(cb, F.FeatureOperations.CutFeatureOperation)
                        i2.setDistanceExtent(False, adsk.core.ValueInput.createByReal(d))
                        i2.participantBodies = [sup]
                        try:
                            ext.add(i2)
                            step('counterbores cut (%.2f)' % d)
                            break
                        except Exception:
                            continue
                else:
                    warn('counterbore profiles %d/4' % cb.count)
            else:
                warn('underside face not found - counterbores skipped')

            # new pedestal with cable-tie tunnel (JOIN block, then tunnel cut)
            plate = None; bestA = 0
            for f in sup.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if pl and abs(pl.normal.z - 1.0) < 0.05 and abs(f.pointOnFace.z - PLATE_Z) < 0.03:
                    if f.area > bestA:
                        plate, bestA = f, f.area
            sk = scomp.sketches.add(plate)
            rect(sk, [(PED['x0'], PED['y0'], PLATE_Z), (PED['x1'], PED['y0'], PLATE_Z),
                      (PED['x1'], PED['y1'], PLATE_Z)])
            prof = smallProfileAt(sk, ((PED['x0']+PED['x1'])/2, (PED['y0']+PED['y1'])/2, PLATE_Z))
            h = PED['top'] - PLATE_Z
            inp = ext.createInput(prof, F.FeatureOperations.JoinFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(h))
            inp.participantBodies = [sup]
            ext.add(inp)
            step('new pedestal built (top z %.2f mm - NOMINAL socket %.1f mm, confirm!)'
                 % (PED['top']*10, SOCKET_H*10))

            # tie tunnel through it along Y: cut from the pedestal's y0 face
            pedFace, bestA = None, 0
            for f in sup.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if not pl:
                    continue
                if abs(pl.normal.y + 1.0) < 0.05 and abs(f.pointOnFace.y - PED['y0']) < 0.03 \
                        and f.pointOnFace.z > PLATE_Z + 0.05:
                    if f.area > bestA:
                        pedFace, bestA = f, f.area
            if pedFace:
                sk = scomp.sketches.add(pedFace)
                tx = (PED['x0'] + PED['x1']) / 2
                z0, z1 = PED['tun_floor'], PED['top'] - PED['tun_roof_drop']
                rect(sk, [(tx - PED['tun_w']/2, PED['y0'], z0),
                          (tx + PED['tun_w']/2, PED['y0'], z0),
                          (tx + PED['tun_w']/2, PED['y0'], z1)])
                prof = smallProfileAt(sk, (tx, PED['y0'], (z0+z1)/2))
                if prof and cutDist(scomp, prof, sup, (-1.70, 1.70)) is not None:
                    step('cable-tie tunnel cut')
                else:
                    warn('tunnel profile/cut failed')
            else:
                warn('pedestal face for tunnel not found')
        except Exception:
            warn('support ops failed: ' + traceback.format_exc(limit=1))

        saved = app.activeDocument.save('TXV16 complete regeneration by Claude: centred PCB, '
                                        'slot+chamfer, vents, signature, pinhole, hooks, pedestal')
        step('document saved: %s' % saved)
        rep['ok'] = True
    except SystemExit:
        pass
    except Exception:
        rep['error'] = traceback.format_exc()
    try:
        with open(REPORT, 'w') as f:
            json.dump(rep, f, indent=1)
    except Exception:
        pass
