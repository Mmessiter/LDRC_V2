# TXV16d — construction-plane finisher: last pocket + 4 drills. Silent.
import adsk.core, adsk.fusion, traceback, json, os

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv16_report.json')
PLATE_Z = 1.707
NEW = [(-6.34, -12.55), (1.30, -12.55), (-6.34, -4.06), (1.30, -4.06)]
PIL_TOP = PLATE_Z + 0.60
POCKET_R, POCKET_D = 0.36, 0.40
DRILL_R = 0.24
MISSING_POCKET = (-6.34, -12.55)


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': []}
    F = adsk.fusion

    def smallProfileAt(sk, x, y):
        c = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, PIL_TOP))
        c = adsk.core.Point3D.create(c.x, c.y, 0)
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

    try:
        design = F.Design.cast(app.activeProduct)
        rep['document'] = app.activeDocument.name
        if not app.activeDocument.name.startswith('TXV16'):
            rep['error'] = 'open TXV16 first'
            raise SystemExit
        root = design.rootComponent
        sup = None
        for b in root.bRepBodies:
            if b.name == 'TX_SUPPORT12':
                sup = b
        if not sup:
            for occ in root.allOccurrences:
                for b in occ.bRepBodies:
                    if b.name == 'TX_SUPPORT12':
                        sup = b
        comp = sup.parentComponent
        ext = comp.features.extrudeFeatures

        plate, bestA = None, 0
        for f in sup.faces:
            pl = adsk.core.Plane.cast(f.geometry)
            if pl and abs(abs(pl.normal.z) - 1.0) < 0.05 and abs(f.pointOnFace.z - PLATE_Z) < 0.03:
                if f.area > bestA:
                    plate, bestA = f, f.area

        planes = comp.constructionPlanes
        pi = planes.createInput()
        pi.setByOffset(plate, adsk.core.ValueInput.createByReal(PIL_TOP - PLATE_Z))
        cp = planes.add(pi)
        rep['steps'].append('construction plane at boss-top level')

        def cutFromPlane(x, y, radius, depth, tag):
            sk = comp.sketches.add(cp)
            c = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, PIL_TOP))
            c = adsk.core.Point3D.create(c.x, c.y, 0)
            sk.sketchCurves.sketchCircles.addByCenterRadius(c, radius)
            prof = smallProfileAt(sk, x, y)
            if not prof:
                rep['warnings'].append('%s: profile missing' % tag)
                return False
            for d in (-depth, depth):
                inp = ext.createInput(prof, F.FeatureOperations.CutFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(d))
                inp.participantBodies = [sup]
                try:
                    ext.add(inp)
                    return True
                except Exception:
                    continue
            rep['warnings'].append('%s: both directions failed' % tag)
            return False

        pk = 1 if cutFromPlane(MISSING_POCKET[0], MISSING_POCKET[1], POCKET_R, POCKET_D, 'pocket') else 0
        dr = 0
        for (hx, hy) in NEW:
            if cutFromPlane(hx, hy, DRILL_R, 0.95, 'drill %.1f' % hx):
                dr += 1
        rep['steps'].append('missing pocket: %d/1, drills: %d/4' % (pk, dr))

        saved = app.activeDocument.save('TXV16 support drills complete by Claude')
        rep['steps'].append('saved: %s' % saved)
        rep['ok'] = (pk == 1 and dr == 4)
    except SystemExit:
        pass
    except Exception:
        rep['error'] = traceback.format_exc()
    try:
        with open(REPORT, 'w') as f:
            json.dump(rep, f, indent=1)
    except Exception:
        pass
