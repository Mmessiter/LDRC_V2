# TXV13Hole — Fusion 360 script, by Claude and Malcolm, July 2026
#
# 1. Saves the ACTIVE design (open TXV12a first!) as a new document "TXV13"
#    in the same cloud folder — the original is never touched.
# 2. Asks you to click:
#       a) the INNER face of the case wall the USB-C plug must pass through
#          (the wall at the charging edge of the PCB),
#       b) the edge of the TX_Support mounting hole FARTHER from the XT30
#          battery corner (the 46.35 mm side),
#       c) the edge of the mounting hole NEARER the battery corner.
# 3. Cuts a rounded slot for the USB-C plug, positioned from those two holes
#    using the real TXV2_MAIN PCB geometry:
#       46.35 mm along the hole line from hole (b),
#       plug centreline (standoff − 1.6) mm above the support face,
#       slot 14 × 7.5 mm, 3 mm corner radius.
#
# If anything looks wrong afterwards, just delete the last two timeline
# features (sketch + cut) and run again — or close TXV13 without saving.

import adsk.core, adsk.fusion, traceback

# ---- PCB-derived constants (mm) — from TXV2_MAIN.kicad_pcb -----------------
HOLE_SPAN_MM   = 76.00   # distance between the two support holes on the USB edge
ALONG_MM       = 46.35   # hole (b)  -> plug centre, along the hole line
STANDOFF_MM    = 5.0     # M3 standoff height (board sits this far above support)
PLUG_DROP_MM   = 1.6     # plug centreline sits this far BELOW the board underside
SLOT_W_MM      = 14.0
SLOT_H_MM      = 7.5
SLOT_R_MM      = 3.0

MM = 0.1  # Fusion API works in cm


def vec(a, b):
    v = a.vectorTo(b)
    return v


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        doc = app.activeDocument
        if not doc or not doc.dataFile:
            ui.messageBox('Open TXV12a (saved, cloud) first, then run this script.')
            return

        # ---- 1) Save a copy as TXV13 — original untouched -------------------
        # (If TXV13 is already the active document — e.g. a previous run made
        # it before failing — just carry on inside it.)
        if doc.name.startswith('TXV13'):
            ok = True
        else:
            ok = doc.saveAs('TXV13', doc.dataFile.parentFolder,
                            'USB-C charging slot, located from the TXV2_MAIN PCB (by Claude and Malcolm)', '')
        if not ok:
            if ui.messageBox('Could not Save-As "TXV13" (name may already exist).\n'
                             'Continue and modify the ACTIVE document instead?',
                             'TXV13', adsk.core.MessageBoxButtonTypes.YesNoButtonType) \
                    != adsk.core.DialogResults.DialogYes:
                return
        adsk.doEvents()

        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion design.')
            return

        # ---- 2) Selections ---------------------------------------------------
        ui.activeSelections.clear()   # selectEntity errors if anything is pre-selected
        selFace = ui.selectEntity(
            'Click the INNER face of the wall the USB-C plug passes through '
            '(the case wall at the charging edge of the PCB)', 'PlanarFaces')
        face = adsk.fusion.BRepFace.cast(selFace.entity)

        def pickHole(prompt):
            ui.activeSelections.clear()
            sel = ui.selectEntity(prompt, 'Edges')
            edge = adsk.fusion.BRepEdge.cast(sel.entity)
            g = edge.geometry
            if g.objectType == adsk.core.Circle3D.classType():
                return g.center, g.normal
            if g.objectType == adsk.core.Arc3D.classType():
                return g.center, g.normal
            raise Exception('That edge is not circular — click the round rim of the mounting hole.')

        hFar, nrmA = pickHole(
            'Click the edge of the TX_Support mounting hole FARTHER from the '
            'battery (XT30) corner — the 46.35 mm side')
        hNear, nrmB = pickHole(
            'Click the edge of the mounting hole NEARER the battery corner')

        # ---- 3) Optional overrides ------------------------------------------
        defaults = '%.2f, %.1f, %.1f, %.1f, %.1f' % (
            ALONG_MM, STANDOFF_MM, SLOT_W_MM, SLOT_H_MM, SLOT_R_MM)
        txt, cancelled = ui.inputBox(
            'along-mm (from first hole), standoff-mm, slot-width, slot-height, corner-radius\n'
            'Just press OK unless something changed.', 'USB slot numbers', defaults)
        if cancelled:
            return
        try:
            along, standoff, slotW, slotH, slotR = [float(x) for x in txt.split(',')]
        except Exception:
            ui.messageBox('Could not read the numbers — using the defaults.')
            along, standoff, slotW, slotH, slotR = \
                ALONG_MM, STANDOFF_MM, SLOT_W_MM, SLOT_H_MM, SLOT_R_MM

        # ---- 4) Geometry (all cm) -------------------------------------------
        span = hFar.distanceTo(hNear) / MM
        if abs(span - HOLE_SPAN_MM) > 1.0:
            if ui.messageBox(
                    'The two holes you clicked are %.2f mm apart — the PCB says %.2f mm.\n'
                    'Are these really the two support holes on the charging edge?\n'
                    'Continue anyway?' % (span, HOLE_SPAN_MM),
                    'Hole check', adsk.core.MessageBoxButtonTypes.YesNoButtonType) \
                    != adsk.core.DialogResults.DialogYes:
                return

        u = hFar.vectorTo(hNear)          # along the hole line, toward battery corner
        u.normalize()

        w = nrmA.copy()                   # support-plate normal (sign fixed below)
        w.normalize()
        facePt = face.pointOnFace
        mid = adsk.core.Point3D.create((hFar.x + hNear.x) / 2,
                                       (hFar.y + hNear.y) / 2,
                                       (hFar.z + hNear.z) / 2)
        toWall = mid.vectorTo(facePt)
        if w.dotProduct(toWall) < 0:      # point "up": from the plate toward the wall's middle
            w.scaleBy(-1.0)

        height = (standoff - PLUG_DROP_MM) * MM
        base = hFar.copy()
        du = u.copy(); du.scaleBy(along * MM);  base.translateBy(du)
        dw = w.copy(); dw.scaleBy(height);      base.translateBy(dw)

        # project the centre onto the wall face plane
        plane = adsk.core.Plane.cast(face.geometry)
        n = plane.normal.copy(); n.normalize()
        po = plane.origin
        d = base.vectorTo(po).dotProduct(n)     # signed distance base->plane along n
        dn = n.copy(); dn.scaleBy(d)
        centre = base.copy(); centre.translateBy(dn)

        # in-plane axes for the slot
        def inPlane(v):
            r = v.copy()
            k = n.copy(); k.scaleBy(r.dotProduct(n))
            r.subtract(k); r.normalize()
            return r
        uf = inPlane(u)
        vf = inPlane(w)

        def corner(su, sv):
            p = centre.copy()
            a = uf.copy(); a.scaleBy(su * slotW / 2 * MM); p.translateBy(a)
            b = vf.copy(); b.scaleBy(sv * slotH / 2 * MM); p.translateBy(b)
            return p

        cA = corner(-1, -1)   # three-point rectangle: two adjacent corners + far side
        cB = corner(+1, -1)
        cC = corner(+1, +1)

        # ---- 5) Sketch + cut -------------------------------------------------
        comp = face.body.parentComponent
        sk = comp.sketches.add(face)
        sA = sk.modelToSketchSpace(cA)
        sB = sk.modelToSketchSpace(cB)
        sC = sk.modelToSketchSpace(cC)
        rectLines = sk.sketchCurves.sketchLines.addThreePointRectangle(sA, sB, sC)

        # round the corners (cosmetic — carries on square if the API objects)
        try:
            lines = [rectLines.item(i) for i in range(4)]
            for i in range(4):
                l1 = lines[i]
                l2 = lines[(i + 1) % 4]
                sk.sketchCurves.sketchArcs.addFillet(
                    l1, l1.endSketchPoint.geometry,
                    l2, l2.startSketchPoint.geometry, slotR * MM)
        except Exception:
            pass

        # smallest profile whose bounding box holds the slot centre = our slot
        sCentre = sk.modelToSketchSpace(centre)
        best, bestArea = None, 1e9
        for i in range(sk.profiles.count):
            pr = sk.profiles.item(i)
            bb = pr.boundingBox
            if (bb.minPoint.x - 0.01 <= sCentre.x <= bb.maxPoint.x + 0.01 and
                    bb.minPoint.y - 0.01 <= sCentre.y <= bb.maxPoint.y + 0.01):
                area = pr.areaProperties().area
                if area < bestArea:
                    best, bestArea = pr, area
        if not best:
            ui.messageBox('Could not find the slot profile — the sketch is in the '
                          'timeline; cut it by hand (Extrude → Cut → Through All).')
            return

        extrudes = comp.features.extrudeFeatures
        inp = extrudes.createInput(best, adsk.fusion.FeatureOperations.CutFeatureOperation)
        inp.setAllExtent(adsk.fusion.ExtentDirections.NegativeExtentDirection)
        inp.participantBodies = [face.body]
        try:
            extrudes.add(inp)
        except Exception:
            inp2 = extrudes.createInput(best, adsk.fusion.FeatureOperations.CutFeatureOperation)
            inp2.setAllExtent(adsk.fusion.ExtentDirections.PositiveExtentDirection)
            inp2.participantBodies = [face.body]
            extrudes.add(inp2)

        ui.messageBox('Done!\n\nTXV13 now has a %.1f x %.1f mm USB-C slot, centred '
                      '%.2f mm from the first hole you clicked and %.1f mm above the '
                      'support face.\n\nCheck it looks right; if not, delete the last '
                      'sketch + cut in the timeline and run again.'
                      % (slotW, slotH, along, standoff - PLUG_DROP_MM))

    except Exception:
        if ui:
            ui.messageBox('TXV13Hole failed:\n{}'.format(traceback.format_exc()))
