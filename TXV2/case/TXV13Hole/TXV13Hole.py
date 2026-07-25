# TXV15 SURGEON v2 — slope-aware tool-free top edge. Silent.
# Discards any dirty TXV15 session, reopens it clean, then cuts 2 pockets in
# the slanted top ridges + grows 2 matching hook tabs on the back tongue,
# built along the actual shoulder slope lines. Report -> txv15_report.json
import adsk.core, adsk.fusion, traceback, json, os, math

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv15_report.json')

# cm. Slope edges (from recon): LEFT ridge (-9.5,5.72)->(-3.5,7.27),
# RIGHT ridge (-1.5,7.27)->(4.4,5.72). Tongue edges parallel, 1.0 mm inboard.
SIDES = [
    {'name': 'left',  'A': (-6.30, 6.55), 's': (0.9683, 0.2501), 'n': (-0.2501, 0.9683)},
    {'name': 'right', 'A': ( 1.45, 6.50), 's': (0.9683, -0.2501), 'n': (0.2501, 0.9683)},
]
POCKET_HALF = 1.40      # pocket half-length along slope (28 mm)
TAB_HALF = 1.15         # tab half-length (23 mm)
POCKET_Z0, POCKET_Z1 = 3.90, 4.055
POCKET_DEPTH = 0.08
TONGUE_Z = 3.95
TAB_T = 0.085
TAB_ROOT = -0.45        # along n from ridge line (inboard, on tongue material)
TAB_TIP = 0.05          # past the ridge face into the pocket
RIDGE_OFF = -0.10       # tongue edge sits 1.0 mm inboard of ridge face


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': [], 'warnings': []}
    try:
        doc = app.activeDocument
        rep['startDocument'] = doc.name

        # ---- clean-slate: operate on a FRESH TXV15 --------------------------
        folder = doc.dataFile.parentFolder
        tx15 = None
        for i in range(folder.dataFiles.count):
            df = folder.dataFiles.item(i)
            if df.name == 'TXV15':
                tx15 = df
        if not tx15:
            rep['error'] = 'TXV15 dataFile not found in folder'
            raise SystemExit
        if doc.name.startswith('TXV15'):
            doc.close(False)                      # discard the dirty session
            adsk.doEvents()
        app.documents.open(tx15, True)
        adsk.doEvents()
        design = adsk.fusion.Design.cast(app.activeProduct)
        rep['steps'].append('opened fresh TXV15 (dirty session discarded)')

        root = design.rootComponent
        bodies = {}
        for b in root.bRepBodies:
            bodies[b.name] = b
        for occ in root.allOccurrences:
            for b in occ.bRepBodies:
                bodies.setdefault(b.name, b)
        front = bodies.get('TX_FRONT12a')
        back = bodies.get('TX_BACK12a')
        if not front or not back:
            rep['error'] = 'bodies not found: %s' % list(bodies)
            raise SystemExit

        def facesOf(body, match):
            out = []
            for f in body.faces:
                pl = adsk.core.Plane.cast(f.geometry)
                if pl and match(f, pl):
                    out.append((f, pl))
            return out

        # slanted ridge inner faces: normal ~(-+0.25,-0.97,0), z-band 38.9..41
        ridges = facesOf(front, lambda f, pl:
                         pl.normal.y < -0.9 and abs(pl.normal.z) < 0.1 and
                         10.0 <= f.area * 100 <= 250 and
                         3.85 <= f.pointOnFace.z <= 4.12)
        # tongue underside faces on the back: |nz|~1 at z=39.5, top region
        tongues = facesOf(back, lambda f, pl:
                          abs(abs(pl.normal.z) - 1.0) < 0.1 and
                          abs(f.pointOnFace.z - TONGUE_Z) < 0.03 and
                          10.0 <= f.area * 100 <= 250 and
                          f.pointOnFace.y > 5.0)
        rep['steps'].append('ridge faces: %d, tongue faces: %d' % (len(ridges), len(tongues)))

        def rectOnSketch(sk, corners3d):
            pts = []
            for (x, y, z) in corners3d:
                p = sk.modelToSketchSpace(adsk.core.Point3D.create(x, y, z))
                pts.append(adsk.core.Point3D.create(p.x, p.y, 0))
            return sk.sketchCurves.sketchLines.addThreePointRectangle(pts[0], pts[1], pts[2]), pts

        def smallProfileAt(sk, centre3d):
            c = sk.modelToSketchSpace(adsk.core.Point3D.create(*centre3d))
            best, bestA = None, 1e9
            for i in range(sk.profiles.count):
                pr = sk.profiles.item(i)
                bb = pr.boundingBox
                if (bb.minPoint.x - 0.01 <= c.x <= bb.maxPoint.x + 0.01 and
                        bb.minPoint.y - 0.01 <= c.y <= bb.maxPoint.y + 0.01):
                    a = pr.areaProperties().area
                    if a < bestA:
                        best, bestA = pr, a
            return best, bestA

        pockets = 0
        for side in SIDES:
            ax, ay = side['A']; sx, sy = side['s']
            rf = None
            for f, pl in ridges:
                bb = f.boundingBox
                if bb.minPoint.x - 0.1 <= ax <= bb.maxPoint.x + 0.1:
                    rf = f
            if not rf:
                rep['warnings'].append('no ridge face for %s' % side['name'])
                continue
            sk = front.parentComponent.sketches.add(rf)
            corners = [
                (ax - sx * POCKET_HALF, ay - sy * POCKET_HALF, POCKET_Z0),
                (ax + sx * POCKET_HALF, ay + sy * POCKET_HALF, POCKET_Z0),
                (ax + sx * POCKET_HALF, ay + sy * POCKET_HALF, POCKET_Z1),
            ]
            rectOnSketch(sk, corners)
            prof, pa = smallProfileAt(sk, (ax, ay, (POCKET_Z0 + POCKET_Z1) / 2))
            if not prof:
                rep['warnings'].append('pocket profile missing (%s)' % side['name'])
                continue
            ext = front.parentComponent.features.extrudeFeatures
            for dist in (-POCKET_DEPTH, POCKET_DEPTH):
                inp = ext.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)
                inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(dist))
                inp.participantBodies = [front]
                try:
                    ext.add(inp)
                    pockets += 1
                    break
                except Exception:
                    continue
        rep['steps'].append('pockets cut: %d' % pockets)

        tabs = 0
        for side in SIDES:
            ax, ay = side['A']; sx, sy = side['s']; nx, ny = side['n']
            tf, tpl = None, None
            for f, pl in tongues:
                bb = f.boundingBox
                if bb.minPoint.x - 0.1 <= ax <= bb.maxPoint.x + 0.1:
                    tf, tpl = f, pl
            if not tf:
                rep['warnings'].append('no tongue face for %s' % side['name'])
                continue
            sk = back.parentComponent.sketches.add(tf)
            r0x, r0y = ax + nx * (RIDGE_OFF + TAB_ROOT), ay + ny * (RIDGE_OFF + TAB_ROOT)
            r1x, r1y = ax + nx * TAB_TIP, ay + ny * TAB_TIP
            corners = [
                (r0x - sx * TAB_HALF, r0y - sy * TAB_HALF, TONGUE_Z),
                (r0x + sx * TAB_HALF, r0y + sy * TAB_HALF, TONGUE_Z),
                (r1x + sx * TAB_HALF, r1y + sy * TAB_HALF, TONGUE_Z),
            ]
            rectOnSketch(sk, corners)
            cx, cy = (r0x + r1x) / 2, (r0y + r1y) / 2
            prof, pa = smallProfileAt(sk, (cx, cy, TONGUE_Z))
            if not prof:
                rep['warnings'].append('tab profile missing (%s)' % side['name'])
                continue
            ext = back.parentComponent.features.extrudeFeatures
            dist = -TAB_T if tpl.normal.z < 0 else TAB_T
            inp = ext.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
            inp.setDistanceExtent(False, adsk.core.ValueInput.createByReal(dist))
            inp.participantBodies = [back]
            try:
                ext.add(inp)
                tabs += 1
            except Exception:
                inp2 = ext.createInput(prof, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                inp2.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-dist))
                inp2.participantBodies = [back]
                try:
                    ext.add(inp2)
                    tabs += 1
                except Exception:
                    rep['warnings'].append('tab join failed (%s)' % side['name'])
        rep['steps'].append('tabs grown: %d' % tabs)

        if pockets >= 2 and tabs >= 2:
            saved = app.activeDocument.save('TXV15 tool-free top edge by Claude: '
                                            'slope-aware hooks (2 tabs + 2 pockets); all screw bosses kept')
            rep['steps'].append('document saved: %s' % saved)
            rep['ok'] = True
        else:
            rep['warnings'].append('incomplete (%d pockets, %d tabs) - NOT saved' % (pockets, tabs))
    except SystemExit:
        pass
    except Exception:
        rep['error'] = traceback.format_exc()
    try:
        with open(REPORT, 'w') as f:
            json.dump(rep, f, indent=1)
    except Exception:
        pass
