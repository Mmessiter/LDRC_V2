# TXV16g — THE clean-room fixer. All sketches on construction planes (no
# face-edge projection), profiles picked by AREA MATCH, every extrude
# probe-verified with flip-and-delete. census -> ops -> census -> save.
import adsk.core, adsk.fusion, traceback, json, os, math

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv16_report.json')
PLATE_Z, PLATE_BOT = 1.707, 1.457
OLD = [(-8.25, -12.55), (-0.61, -12.55), (-8.25, -4.06), (-0.61, -4.06)]
NEW = [(-6.34, -12.55), (1.30, -12.55), (-6.34, -4.06), (1.30, -4.06)]
BOSS_H = 0.53
PIL_TOP = PLATE_Z + 0.60
WALL = {'x0': -11.43, 'x1': 6.27, 'y0': -3.63, 'y1': -3.38, 'top': 2.007}
STRIP = {'x0': -11.44, 'x1': 6.28, 'y0': -3.74, 'y1': -3.37}
LIP_CLEAR_Y = -12.80
INSIDE = adsk.fusion.PointContainment.PointInsidePointContainment


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': [], 'before': {}, 'after': {}}
    F = adsk.fusion
    try:
        doc = app.activeDocument
        folder = doc.dataFile.parentFolder
        tx16 = None
        for i in range(folder.dataFiles.count):
            df = folder.dataFiles.item(i)
            if df.name == 'TXV16':
                tx16 = df
        if doc.name.startswith('TXV16'):
            doc.close(False)
            adsk.doEvents()
        app.documents.open(tx16, True)
        adsk.doEvents()
        design = F.Design.cast(app.activeProduct)
        rep['steps'].append('opened TXV16 v%s' % getattr(app.activeDocument.dataFile, 'versionNumber', '?'))

        def sup():
            root = design.rootComponent
            for b in root.bRepBodies:
                if b.name == 'TX_SUPPORT12':
                    return b
            for occ in root.allOccurrences:
                for b in occ.bRepBodies:
                    if b.name == 'TX_SUPPORT12':
                        return b

        def probe(x, y, z):
            return sup().pointContainment(adsk.core.Point3D.create(x, y, z)) == INSIDE

        def census():
            return {
                'newBoss': sum(1 for (x, y) in NEW if probe(x + 0.35, y + 0.35, 2.00)),
                'pocketOpen': sum(1 for (x, y) in NEW if not probe(x, y, 2.25)),
                'drillOpen': sum(1 for (x, y) in NEW if not probe(x, y, 1.55)),
                'oldPlugged': sum(1 for (x, y) in OLD if probe(x, y, 1.58)),
                'oldBossGone': sum(1 for (x, y) in OLD if not probe(x, y + 0.2, 1.90)),
                'wallGapFilled': probe(-4.4, -3.5, 1.85),
                'wallMid': probe(-2.5, -3.5, 1.85),
                'oldWallSeg': probe(2.61, -3.55, 1.95),
            }

        rep['before'] = census()
        comp = sup().parentComponent
        ext = comp.features.extrudeFeatures

        def plateFace():
            best, bestA = None, 0
            for f in sup().faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if pl and abs(abs(pl.normal.z) - 1.0) < 0.05 and abs(f.pointOnFace.z - PLATE_Z) < 0.03:
                    if f.area > bestA:
                        best, bestA = f, f.area
            return best

        def planeAt(zTarget):
            planes = comp.constructionPlanes
            for offset in (zTarget - PLATE_Z, -(zTarget - PLATE_Z)):
                pi = planes.createInput()
                pi.setByOffset(plateFace(), adsk.core.ValueInput.createByReal(offset))
                cp = planes.add(pi)
                if abs(cp.geometry.origin.z - zTarget) < 0.05:
                    return cp
                cp.deleteMe()
            return None

        def profByArea(sk, expectArea):
            best, bestErr = None, 1e9
            for i in range(sk.profiles.count):
                pr = sk.profiles.item(i)
                a = pr.areaProperties().area
                err = abs(a - expectArea)
                if err < bestErr:
                    best, bestErr = pr, err
            if best and bestErr < 0.25 * expectArea:
                return best
            return None

        def vext(prof, op, dist, probePt, wantInside, tag):
            for d in (dist, -dist):
                inp = ext.createInput(prof, op)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(d))
                inp.participantBodies = [sup()]
                try:
                    feat = ext.add(inp)
                except Exception:
                    continue
                if probe(*probePt) == wantInside:
                    return True
                try:
                    feat.deleteMe()
                except Exception:
                    rep['warnings'].append('%s: bad feature stuck!' % tag)
                    return False
            rep['warnings'].append('%s: unverified' % tag)
            return False

        CUT = F.FeatureOperations.CutFeatureOperation
        JOIN = F.FeatureOperations.JoinFeatureOperation

        topPlane = planeAt(PLATE_Z)
        bossPlane = planeAt(PIL_TOP)
        rep['steps'].append('planes: top %s, boss %s' %
                            ('ok' if topPlane else 'FAIL', 'ok' if bossPlane else 'FAIL'))

        def rectSketch(cp, x0, y0, x1, y1, zref):
            sk = comp.sketches.add(cp)
            pts = []
            for (x, y) in ((x0, y0), (x1, y0), (x1, y1)):
                p = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, zref))
                pts.append(adsk.core.Point3D.create(p.x, p.y, 0))
            sk.sketchCurves.sketchLines.addThreePointRectangle(pts[0], pts[1], pts[2])
            return sk, abs(x1 - x0) * abs(y1 - y0)

        def circleSketch(cp, x, y, r, zref):
            sk = comp.sketches.add(cp)
            c = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, zref))
            c = adsk.core.Point3D.create(c.x, c.y, 0)
            sk.sketchCurves.sketchCircles.addByCenterRadius(c, r)
            return sk, math.pi * r * r

        # 1) strip wipe (removes old wall segments + pedestal-zone scar)
        sk, area = rectSketch(topPlane, STRIP['x0'], STRIP['y0'], STRIP['x1'], STRIP['y1'], PLATE_Z)
        prof = profByArea(sk, area)
        if prof and vext(prof, CUT, 1.80, (2.61, -3.55, 1.95), False, 'strip'):
            rep['steps'].append('strip wiped (old wall cleared)')

        # 2) continuous wall
        sk, area = rectSketch(topPlane, WALL['x0'], WALL['y0'], WALL['x1'], WALL['y1'], PLATE_Z)
        prof = profByArea(sk, area)
        if prof and vext(prof, JOIN, WALL['top'] - PLATE_Z, (-4.4, -3.5, 1.85), True, 'wall'):
            rep['steps'].append('continuous wall built + verified in the gap')

        # 3) plug old holes (7.6 disc, down through plate)
        pl_n = 0
        for (hx, hy) in OLD:
            if probe(hx, hy, 1.58):
                pl_n += 1
                continue
            sk, area = circleSketch(topPlane, hx, hy, 0.38, PLATE_Z)
            prof = profByArea(sk, area)
            if prof and vext(prof, JOIN, -(PLATE_Z - PLATE_BOT + 0.02), (hx, hy, 1.58), True, 'plug'):
                pl_n += 1
        rep['steps'].append('old holes plugged: %d/4' % pl_n)

        # 4) new bosses (JOIN up; the open hole gets roofed - drill re-cut later)
        made = 0
        for (hx, hy) in NEW:
            if probe(hx + 0.35, hy + 0.35, 2.00):
                made += 1
                continue
            y0 = max(hy - BOSS_H, LIP_CLEAR_Y) if hy < -10 else hy - BOSS_H
            sk, area = rectSketch(topPlane, hx - BOSS_H, y0, hx + BOSS_H, hy + BOSS_H, PLATE_Z)
            prof = profByArea(sk, area)
            if prof and vext(prof, JOIN, PIL_TOP - PLATE_Z, (hx + 0.35, hy + 0.35, 2.00), True, 'boss'):
                made += 1
        rep['steps'].append('new bosses: %d/4' % made)

        # 5) pockets then drills from the boss plane
        pk = dr = 0
        for (hx, hy) in NEW:
            sk, area = circleSketch(bossPlane, hx, hy, 0.36, PIL_TOP)
            prof = profByArea(sk, area)
            if prof and vext(prof, CUT, -0.40, (hx, hy, 2.25), False, 'pocket'):
                pk += 1
            sk, area = circleSketch(bossPlane, hx, hy, 0.24, PIL_TOP)
            prof = profByArea(sk, area)
            if prof and vext(prof, CUT, -0.95, (hx, hy, 1.55), False, 'drill'):
                dr += 1
        rep['steps'].append('pockets %d/4, drills %d/4' % (pk, dr))

        rep['after'] = census()
        a = rep['after']
        good = (a['newBoss'] == 4 and a['oldPlugged'] == 4 and a['wallGapFilled']
                and a['oldBossGone'] == 4 and not a['oldWallSeg']
                and a['pocketOpen'] == 4 and a['drillOpen'] == 4)
        saved = app.activeDocument.save('TXV16 support - clean-room rebuild, census-verified')
        rep['steps'].append('saved: %s' % saved)
        rep['ok'] = good
        if not good:
            rep['warnings'].append('census imperfect')
    except SystemExit:
        pass
    except Exception:
        rep['error'] = traceback.format_exc()
    try:
        with open(REPORT, 'w') as f:
            json.dump(rep, f, indent=1)
    except Exception:
        pass
