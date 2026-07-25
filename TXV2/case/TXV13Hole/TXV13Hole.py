# TXV13 SURGEON — Fusion 360 script, by Claude, July 2026. SILENT.
# Cuts the USB-C charging slot in TXV13's bottom wall at coordinates computed
# from the TXV2_MAIN PCB + the recon dump, then SAVES the document.
# Writes a report to txv13_surgeon_report.json — no dialogs.

import adsk.core, adsk.fusion, traceback, json, os

CASE_DIR = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case')
REPORT = os.path.join(CASE_DIR, 'txv13_surgeon_report.json')

# All cm (Fusion API). Derived: PCB pattern on the support's countersunk
# holes; USB J1 kicad(150,189.2) -> case (-36.0, y=wall, z=plate17.07+5-1.6).
CX = -3.60          # slot centre X
CZ = 2.047          # slot centre Z
WALL_Y = -12.950    # inner wall plane
SLOT_W = 1.40
SLOT_H = 0.75
SLOT_R = 0.30


def run(context):
    app = adsk.core.Application.get()
    rep = {'ok': False, 'steps': []}
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        rep['document'] = app.activeDocument.name
        if not app.activeDocument.name.startswith('TXV13'):
            rep['error'] = 'active document is not TXV13 — aborting, nothing done'
            raise SystemExit

        token = open(os.path.join(CASE_DIR, 'wall_token.txt')).read().strip()
        found = design.findEntityByToken(token)
        if not found or len(found) == 0:
            rep['error'] = 'wall face token not found'
            raise SystemExit
        face = adsk.fusion.BRepFace.cast(found[0])
        rep['steps'].append('wall face resolved: point=%s area=%.1fcm2'
                            % (str([round(v, 2) for v in [face.pointOnFace.x, face.pointOnFace.y, face.pointOnFace.z]]),
                               face.area))

        comp = face.body.parentComponent
        sk = comp.sketches.add(face)
        rep['steps'].append('sketch created')

        def mpt(x, z):
            return sk.modelToSketchSpace(adsk.core.Point3D.create(x, WALL_Y, z))

        pA = mpt(CX - SLOT_W / 2, CZ - SLOT_H / 2)
        pB = mpt(CX + SLOT_W / 2, CZ - SLOT_H / 2)
        pC = mpt(CX + SLOT_W / 2, CZ + SLOT_H / 2)
        rect = sk.sketchCurves.sketchLines.addThreePointRectangle(pA, pB, pC)
        rep['steps'].append('rectangle drawn')

        try:
            lines = [rect.item(i) for i in range(4)]
            for i in range(4):
                l1, l2 = lines[i], lines[(i + 1) % 4]
                sk.sketchCurves.sketchArcs.addFillet(
                    l1, l1.endSketchPoint.geometry,
                    l2, l2.startSketchPoint.geometry, SLOT_R)
            rep['steps'].append('corners rounded')
        except Exception as e:
            rep['steps'].append('fillets skipped: %s' % str(e)[:80])

        sCentre = sk.modelToSketchSpace(adsk.core.Point3D.create(CX, WALL_Y, CZ))
        best, bestArea = None, 1e9
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            bb = pr.boundingBox
            if (bb.minPoint.x - 0.01 <= sCentre.x <= bb.maxPoint.x + 0.01 and
                    bb.minPoint.y - 0.01 <= sCentre.y <= bb.maxPoint.y + 0.01):
                a = pr.areaProperties().area
                if a < bestArea:
                    best, bestArea = pr, a
        if not best:
            rep['error'] = 'slot profile not found'
            raise SystemExit
        rep['steps'].append('profile found, area %.3f cm2 (expect ~%.3f)'
                            % (bestArea, SLOT_W * SLOT_H - (4 - 3.14159) * SLOT_R * SLOT_R))

        extrudes = comp.features.extrudeFeatures
        inp = extrudes.createInput(best, adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
        inp.participantBodies = [face.body]
        try:
            feat = extrudes.add(inp)
            rep['steps'].append('cut (negative through-all) ok, health=%d' % feat.healthState)
        except Exception:
            inp2 = extrudes.createInput(best, adsk.fusion.FeatureOperations.CutFeatureOperation)
            inp2.setAllExtent(adsk.fusion.ExtentDirections.PositiveExtentDirection)
            inp2.participantBodies = [face.body]
            feat = extrudes.add(inp2)
            rep['steps'].append('cut (positive through-all) ok, health=%d' % feat.healthState)

        saved = app.activeDocument.save('USB-C charging slot cut by Claude '
                                        '(14x7.5 r3 at X-36.0 Z20.47, from TXV2_MAIN PCB geometry)')
        rep['steps'].append('document saved: %s' % saved)
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
