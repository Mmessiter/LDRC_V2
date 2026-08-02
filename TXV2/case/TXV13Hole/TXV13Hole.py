# TXV16i — ghost-ring fills at old hole sites + corrected strict census.
import adsk.core, adsk.fusion, traceback, json, os, math

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv16_report.json')
PLATE_Z, PLATE_BOT = 1.707, 1.457
OLD = [(-8.25, -12.55), (-0.61, -12.55), (-8.25, -4.06), (-0.61, -4.06)]
NEW = [(-6.34, -12.55), (1.30, -12.55), (-6.34, -4.06), (1.30, -4.06)]
PED = {'x0': -8.5, 'x1': -7.4, 'y0': -5.8, 'y1': -4.2, 'top': 3.312}
INSIDE = adsk.fusion.PointContainment.PointInsidePointContainment


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': [], 'after': {}}
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

        def planeAt(zT):
            planes = comp.constructionPlanes
            for off in (zT - PLATE_Z, -(zT - PLATE_Z)):
                pi = planes.createInput()
                pi.setByOffset(plateFace(), adsk.core.ValueInput.createByReal(off))
                cp = planes.add(pi)
                if abs(cp.geometry.origin.z - zT) < 0.05:
                    return cp
                cp.deleteMe()

        def profByArea(sk, expect):
            best, err = None, 1e9
            for i in range(sk.profiles.count):
                pr = sk.profiles.item(i)
                e = abs(pr.areaProperties().area - expect)
                if e < err:
                    best, err = pr, e
            return best if best and err < 0.25 * expect else None

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
                    rep['warnings'].append('%s stuck' % tag)
                    return False
            rep['warnings'].append('%s unverified' % tag)
            return False

        JOIN = F.FeatureOperations.JoinFeatureOperation
        topPlane = planeAt(PLATE_Z)

        # ghost-ring fills: flush discs, downward only (cannot protrude)
        gf = 0
        for (ox, oy) in OLD:
            already = probe(ox + 0.42, oy, 1.65)
            if already:
                gf += 1
                continue
            sk = comp.sketches.add(topPlane)
            c = sk.modelToSketchSpace(adsk.core.Point3D.create(ox, oy, PLATE_Z))
            c = adsk.core.Point3D.create(c.x, c.y, 0)
            sk.sketchCurves.sketchCircles.addByCenterRadius(c, 0.55)
            prof = profByArea(sk, math.pi * 0.55 * 0.55)
            if prof and vext(prof, JOIN, -0.30, (ox + 0.42, oy, 1.65), True, 'ghost fill'):
                gf += 1
        rep['steps'].append('ghost-ring fills solid: %d/4' % gf)

        # corrected census
        rep['after'] = {
            'bossFillRing': sum(1 for (x, y) in NEW if probe(x + 0.30, y, 2.25)),
            'drillOpenTop': sum(1 for (x, y) in NEW if not probe(x, y, 2.10)),
            'drillOpenMid': sum(1 for (x, y) in NEW if not probe(x, y, 1.60)),
            'nutPocketOpen': sum(1 for (x, y) in NEW if not probe(x + 0.30, y, 1.55)),
            'nutPocketRoof': sum(1 for (x, y) in NEW if probe(x + 0.30, y, 1.85)),
            'plugsIntact': sum(1 for (x, y) in OLD if probe(x, y, 1.58)),
            'ghostFilled': sum(1 for (x, y) in OLD if probe(x + 0.42, y, 1.65)),
            'ghostNoBump': sum(1 for (x, y) in OLD if not probe(x + 0.42, y, 1.90)),
            'pedTopCorners': sum(1 for (x, y) in
                                 ((-8.4, -4.3), (-7.5, -4.3), (-8.4, -5.7), (-7.5, -5.7))
                                 if probe(x, y, 3.24)),
            'pedBaseSolid': probe(-7.5, -4.4, 2.0),
            'tunnelOpen': not probe(-7.95, -5.0, 2.60),
            'wallSolid3': sum(1 for x in (-10.0, -4.4, 5.5) if probe(x, -3.5, 1.85)),
        }
        a = rep['after']
        good = (a['bossFillRing'] == 4 and a['drillOpenTop'] == 4 and a['drillOpenMid'] == 4
                and a['nutPocketOpen'] == 4 and a['nutPocketRoof'] == 4
                and a['plugsIntact'] == 4 and a['ghostFilled'] == 4 and a['ghostNoBump'] == 4
                and a['pedTopCorners'] == 4 and a['pedBaseSolid'] and a['tunnelOpen']
                and a['wallSolid3'] == 3)
        if gf > 0 or good:
            saved = app.activeDocument.save('TXV16 finisher: ghost-ring fills at old hole sites')
            rep['steps'].append('saved: %s' % saved)
        rep['ok'] = good
    except SystemExit:
        pass
    except Exception:
        rep['error'] = traceback.format_exc()
    try:
        with open(REPORT, 'w') as f:
            json.dump(rep, f, indent=1)
    except Exception:
        pass
