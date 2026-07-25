# TXV14 signature-only pass — silent. Report -> txv14_report.json
import adsk.core, adsk.fusion, traceback, json, os

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv14_report.json')
WALL_OUT_Y = -13.250
SIG_TEXT = 'TXV14 - Claude + Malcolm - 2026'
SIG_H = 0.45
SIG_DEPTH = 0.04
SIG_CX, SIG_CZ = 2.2, 3.30

def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': []}
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        rep['document'] = app.activeDocument.name
        if not app.activeDocument.name.startswith('TXV14'):
            rep['error'] = 'not in TXV14 - aborting'
            raise SystemExit
        root = design.rootComponent
        front = None
        for b in root.bRepBodies:
            if b.name == 'TX_FRONT12a':
                front = b
        if not front:
            for occ in root.allOccurrences:
                for b in occ.bRepBodies:
                    if b.name == 'TX_FRONT12a':
                        front = b
        outer, bestA = None, 0
        for f in front.faces:
            pl = adsk.core.Plane.cast(f.geometry)
            if not pl:
                continue
            if abs(pl.normal.y + 1.0) > 0.1 or abs(f.pointOnFace.y - WALL_OUT_Y) > 0.05:
                continue
            if f.area > bestA:
                outer, bestA = f, f.area
        if not outer:
            rep['error'] = 'outer wall not found'
            raise SystemExit
        rep['steps'].append('outer wall found (%.1f cm2)' % outer.area)

        comp = front.parentComponent
        sk = comp.sketches.add(outer)
        def flat(x, z):
            p = sk.modelToSketchSpace(adsk.core.Point3D.create(x, WALL_OUT_Y, z))
            return adsk.core.Point3D.create(p.x, p.y, 0)   # clamp to sketch plane
        c1 = flat(SIG_CX - 3.6, SIG_CZ - SIG_H / 2 - 0.1)
        c2 = flat(SIG_CX + 3.6, SIG_CZ + SIG_H / 2 + 0.1)
        lo = adsk.core.Point3D.create(min(c1.x, c2.x), min(c1.y, c2.y), 0)
        hi = adsk.core.Point3D.create(max(c1.x, c2.x), max(c1.y, c2.y), 0)
        texts = sk.sketchTexts
        tIn = texts.createInput2(SIG_TEXT, SIG_H * 0.6)
        tIn.setAsMultiLine(lo, hi,
                           adsk.core.HorizontalAlignments.CenterHorizontalAlignment,
                           adsk.core.VerticalAlignments.MiddleVerticalAlignment, 0)
        st = texts.add(tIn)
        rep['steps'].append('text placed')
        profs = adsk.core.ObjectCollection.create()
        profs.add(st)
        ext = comp.features.extrudeFeatures
        inp = ext.createInput(profs, adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-SIG_DEPTH))
        inp.participantBodies = [front]
        try:
            ext.add(inp)
            rep['steps'].append('engraved (negative %.1f mm)' % (SIG_DEPTH * 10))
        except Exception:
            inp2 = ext.createInput(profs, adsk.fusion.FeatureOperations.CutFeatureOperation)
            inp2.setDistanceExtent(False, adsk.core.ValueInput.createByReal(SIG_DEPTH))
            inp2.participantBodies = [front]
            ext.add(inp2)
            rep['steps'].append('engraved (positive %.1f mm)' % (SIG_DEPTH * 10))
        saved = app.activeDocument.save('TXV14 signature engraved by Claude')
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
