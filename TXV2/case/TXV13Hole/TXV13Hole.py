# TXV15 pinhole service-button pass — silent. Report -> txv15_report.json
# Drill a 1.8 mm pinhole through the bottom wall by the 2808 module +
# engrave a 0.3 mm ring + 'R' marker on the outer face so it can be found.
import adsk.core, adsk.fusion, traceback, json, os

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv15_report.json')
WALL_IN_Y, WALL_OUT_Y = -12.950, -13.250
HOLE_X, HOLE_Z, HOLE_R = -7.40, 2.60, 0.09
RING_R, RING_W, RING_DEPTH = 0.30, 0.06, 0.03


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': []}
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        rep['document'] = app.activeDocument.name
        if not app.activeDocument.name.startswith('TXV15'):
            rep['error'] = 'not in TXV15 - open TXV15 first'
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
        if not front:
            rep['error'] = 'front body not found'
            raise SystemExit

        def findWall(yT, nyWant):
            best, bestA = None, 0
            for f in front.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if not pl:
                    continue
                if abs(pl.normal.y - nyWant) > 0.1:
                    continue
                if abs(f.pointOnFace.y - yT) > 0.05:
                    continue
                if f.area > bestA:
                    best, bestA = f, f.area
            return best

        # 1) the pinhole (cut from the inner face, through-all outward)
        inner = findWall(WALL_IN_Y, 1.0)
        if not inner:
            rep['error'] = 'inner wall not found'
            raise SystemExit
        comp = front.parentComponent
        sk = comp.sketches.add(inner)
        c = sk.modelToSketchSpace(adsk.core.Point3D.create(HOLE_X, WALL_IN_Y, HOLE_Z))
        c = adsk.core.Point3D.create(c.x, c.y, 0)
        sk.sketchCurves.sketchCircles.addByCenterRadius(c, HOLE_R)
        prof, pa = None, 1e9
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            bb = pr.boundingBox
            if (bb.minPoint.x - 0.01 <= c.x <= bb.maxPoint.x + 0.01 and
                    bb.minPoint.y - 0.01 <= c.y <= bb.maxPoint.y + 0.01):
                a = pr.areaProperties().area
                if a < pa:
                    prof, pa = pr, a
        bb = prof.boundingBox
        rep['steps'].append('hole profile bbox (%.2f,%.2f)-(%.2f,%.2f) area %.4f'
                            % (bb.minPoint.x, bb.minPoint.y, bb.maxPoint.x, bb.maxPoint.y, pa))
        ext = comp.features.extrudeFeatures
        done = False
        for dist in (-0.35, 0.35):
            inp = ext.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(dist))
            inp.participantBodies = [front]
            try:
                ext.add(inp)
                done = True
                rep['steps'].append('pinhole cut (d1.8mm, dist %.2f)' % dist)
                break
            except Exception as e:
                rep['warnings'].append('dist %.2f: %s' % (dist, str(e)[:60]))
        if not done:
            rep['error'] = 'pinhole cut failed both directions'
            raise SystemExit

        # 2) engraved ring marker on the outer face
        outer = findWall(WALL_OUT_Y, -1.0)
        if outer:
            sk2 = comp.sketches.add(outer)
            c2 = sk2.modelToSketchSpace(adsk.core.Point3D.create(HOLE_X, WALL_OUT_Y, HOLE_Z))
            c2 = adsk.core.Point3D.create(c2.x, c2.y, 0)
            sk2.sketchCurves.sketchCircles.addByCenterRadius(c2, RING_R)
            sk2.sketchCurves.sketchCircles.addByCenterRadius(c2, RING_R - RING_W)
            ring, ra = None, 1e9
            for i in range(sk2.profiles.count):
                pr = sk2.profiles.item(i)
                bb = pr.boundingBox
                w = bb.maxPoint.x - bb.minPoint.x
                if abs(w - 2 * RING_R) < 0.05:
                    a = pr.areaProperties().area
                    if a < ra:
                        ring, ra = pr, a
            if ring:
                inp3 = ext.createInput(ring, adsk.fusion.FeatureOperations.CutFeatureOperation)
                inp3.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-RING_DEPTH))
                inp3.participantBodies = [front]
                try:
                    ext.add(inp3)
                except Exception:
                    inp4 = ext.createInput(ring, adsk.fusion.FeatureOperations.CutFeatureOperation)
                    inp4.setDistanceExtent(False, adsk.core.ValueInput.createByReal(RING_DEPTH))
                    inp4.participantBodies = [front]
                    ext.add(inp4)
                rep['steps'].append('ring marker engraved')
            else:
                rep['warnings'].append('ring profile not isolated - marker skipped')
        saved = app.activeDocument.save('TXV15: pinhole service button (A-B) by Claude')
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
