# TXV15: remove the old V1 nRF pedestal from TX_SUPPORT12. Silent.
# Box-cut X[-53.4,-35.2] Y[-37.15,-26.2] upward from the plate top only.
import adsk.core, adsk.fusion, traceback, json, os

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv15_report.json')
X0, X1 = -5.34, -3.52
Y0, Y1 = -3.715, -2.62
PLATE_Z = 1.707
CUT_UP = 1.80


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': []}
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        rep['document'] = app.activeDocument.name
        if not app.activeDocument.name.startswith('TXV15'):
            rep['error'] = 'not in TXV15'
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
        if not sup:
            rep['error'] = 'TX_SUPPORT12 not found'
            raise SystemExit

        plate, bestA = None, 0
        for f in sup.faces:
            pl = adsk.core.Plane.cast(f.geometry)
            if not pl:
                continue
            if abs(pl.normal.z - 1.0) > 0.05 or abs(f.pointOnFace.z - PLATE_Z) > 0.03:
                continue
            if f.area > bestA:
                plate, bestA = f, f.area
        if not plate:
            rep['error'] = 'plate top face not found'
            raise SystemExit
        rep['steps'].append('plate top found (%.1f cm2)' % plate.area)

        comp = sup.parentComponent
        sk = comp.sketches.add(plate)
        def sp(x, y):
            p = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, PLATE_Z))
            return adsk.core.Point3D.create(p.x, p.y, 0)
        sk.sketchCurves.sketchLines.addThreePointRectangle(sp(X0, Y0), sp(X1, Y0), sp(X1, Y1))
        cx, cyy = (X0 + X1) / 2, (Y0 + Y1) / 2
        c = sp(cx, cyy)
        prof, pa = None, 1e9
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            bb = pr.boundingBox
            if (bb.minPoint.x - 0.01 <= c.x <= bb.maxPoint.x + 0.01 and
                    bb.minPoint.y - 0.01 <= c.y <= bb.maxPoint.y + 0.01):
                a = pr.areaProperties().area
                if a < pa:
                    prof, pa = pr, a
        if not prof:
            rep['error'] = 'cut profile not found'
            raise SystemExit
        rep['steps'].append('profile area %.2f cm2' % pa)

        # sketch normal = plate face normal = +Z; POSITIVE distance only (upward).
        ext = comp.features.extrudeFeatures
        inp = ext.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(CUT_UP))
        inp.participantBodies = [sup]
        ext.add(inp)
        rep['steps'].append('old pedestal removed (upward box-cut 18 mm)')

        saved = app.activeDocument.save('TXV15: old V1 nRF pedestal removed (module moved left) - by Claude')
        rep['steps'].append('saved: %s' % saved)
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
