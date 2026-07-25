# TXV13Hole — Fusion 360 script, by Claude and Malcolm, July 2026 (v3)
#
# Cuts the USB-C charging slot in the TXV13 case, located from the two
# TX_Support mounting holes on the charging edge using the real TXV2_MAIN
# PCB geometry.
#
# v3: proper command dialog with selection inputs — Fusion's selectEntity()
# API proved unreliable after a document Save-As (InternalValidationError),
# so all picking now happens inside one dialog panel:
#     1. Wall face   — the INNER face the USB-C plug passes through
#     2. Hole A      — support mounting hole FARTHER from the battery corner
#     3. Hole B      — support mounting hole NEARER the battery corner
#     + the numbers (defaults from the PCB; normally just press OK)
#
# Run with TXV13 open (it exists — yesterday's run created it). If you run
# it with TXV12a open instead, it saves a copy as TXV13 first and works there.
# Wrong result? Delete the last sketch + cut in the timeline and run again.

import adsk.core, adsk.fusion, traceback

# ---- PCB-derived constants — from TXV2_MAIN.kicad_pcb (cm: Fusion API unit)
HOLE_SPAN_CM = 7.600    # the two support holes on the USB edge are 76.00 mm apart
ALONG_CM     = 4.635    # hole A -> plug centre along the hole line (46.35 mm)
STANDOFF_CM  = 0.50     # M3 standoff height (5 mm)
PLUG_DROP_CM = 0.16     # plug centreline below the board underside (1.6 mm)
SLOT_W_CM    = 1.40
SLOT_H_CM    = 0.75
SLOT_R_CM    = 0.30

CMD_ID = 'TXV13HoleCmd'
_app = None
_ui = None
_handlers = []          # keep handlers alive for the command's lifetime


def cutSlot(face, hFar, plateNormal, hNear, along, standoff, slotW, slotH, slotR):
    """All lengths in cm. Returns a human summary string."""
    u = hFar.vectorTo(hNear)
    u.normalize()

    w = plateNormal.copy()
    w.normalize()
    facePt = face.pointOnFace
    mid = adsk.core.Point3D.create((hFar.x + hNear.x) / 2,
                                   (hFar.y + hNear.y) / 2,
                                   (hFar.z + hNear.z) / 2)
    if w.dotProduct(mid.vectorTo(facePt)) < 0:   # "up" = from plate toward wall middle
        w.scaleBy(-1.0)

    base = hFar.copy()
    du = u.copy(); du.scaleBy(along);                    base.translateBy(du)
    dw = w.copy(); dw.scaleBy(standoff - PLUG_DROP_CM);  base.translateBy(dw)

    plane = adsk.core.Plane.cast(face.geometry)
    n = plane.normal.copy(); n.normalize()
    d = base.vectorTo(plane.origin).dotProduct(n)
    dn = n.copy(); dn.scaleBy(d)
    centre = base.copy(); centre.translateBy(dn)         # projected onto the wall

    def inPlane(v):
        r = v.copy()
        k = n.copy(); k.scaleBy(r.dotProduct(n))
        r.subtract(k); r.normalize()
        return r
    uf = inPlane(u)
    vf = inPlane(w)

    def corner(su, sv):
        p = centre.copy()
        a = uf.copy(); a.scaleBy(su * slotW / 2); p.translateBy(a)
        b = vf.copy(); b.scaleBy(sv * slotH / 2); p.translateBy(b)
        return p

    comp = face.body.parentComponent
    sk = comp.sketches.add(face)
    sA = sk.modelToSketchSpace(corner(-1, -1))
    sB = sk.modelToSketchSpace(corner(+1, -1))
    sC = sk.modelToSketchSpace(corner(+1, +1))
    rect = sk.sketchCurves.sketchLines.addThreePointRectangle(sA, sB, sC)

    try:                                                  # cosmetic corner rounds
        lines = [rect.item(i) for i in range(4)]
        for i in range(4):
            l1, l2 = lines[i], lines[(i + 1) % 4]
            sk.sketchCurves.sketchArcs.addFillet(
                l1, l1.endSketchPoint.geometry,
                l2, l2.startSketchPoint.geometry, slotR)
    except Exception:
        pass

    sCentre = sk.modelToSketchSpace(centre)               # smallest profile at centre
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
        raise Exception('Could not isolate the slot profile — the sketch is in the '
                        'timeline; finish with Extrude → Cut → Through All by hand.')

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

    return ('Cut a %.1f x %.1f mm slot, %.2f mm from hole A along the hole line, '
            'plug centreline %.1f mm above the support face.'
            % (slotW * 10, slotH * 10, along * 10, (standoff - PLUG_DROP_CM) * 10))


class TXV13Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            ins = cmd.commandInputs

            s1 = ins.addSelectionInput('wall', 'Wall face',
                                       'The INNER face of the wall the USB-C plug passes through')
            s1.addSelectionFilter('PlanarFaces')
            s1.setSelectionLimits(1, 1)

            s2 = ins.addSelectionInput('holeA', 'Hole A (far from battery)',
                                       'Support mounting hole FARTHER from the XT30 battery corner')
            s2.addSelectionFilter('CircularEdges')
            s2.setSelectionLimits(1, 1)

            s3 = ins.addSelectionInput('holeB', 'Hole B (near battery)',
                                       'Support mounting hole NEARER the battery corner')
            s3.addSelectionFilter('CircularEdges')
            s3.setSelectionLimits(1, 1)

            vi = adsk.core.ValueInput.createByReal
            ins.addValueInput('along',    'Hole A → plug centre', 'mm', vi(ALONG_CM))
            ins.addValueInput('standoff', 'Standoff height',      'mm', vi(STANDOFF_CM))
            ins.addValueInput('slotW',    'Slot width',           'mm', vi(SLOT_W_CM))
            ins.addValueInput('slotH',    'Slot height',          'mm', vi(SLOT_H_CM))
            ins.addValueInput('slotR',    'Corner radius',        'mm', vi(SLOT_R_CM))

            onExec = TXV13Execute()
            cmd.execute.add(onExec)
            _handlers.append(onExec)
            onDestroy = TXV13Destroy()
            cmd.destroy.add(onDestroy)
            _handlers.append(onDestroy)
        except Exception:
            _ui.messageBox('TXV13Hole dialog failed:\n{}'.format(traceback.format_exc()))


class TXV13Execute(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            ins = args.command.commandInputs
            face = adsk.fusion.BRepFace.cast(ins.itemById('wall').selection(0).entity)

            def holeOf(inputId):
                e = adsk.fusion.BRepEdge.cast(ins.itemById(inputId).selection(0).entity)
                g = e.geometry
                return g.center, g.normal

            hFar, plateNormal = holeOf('holeA')
            hNear, _ = holeOf('holeB')

            span = hFar.distanceTo(hNear)
            if abs(span - HOLE_SPAN_CM) > 0.10:
                if _ui.messageBox(
                        'Holes A and B are %.2f mm apart — the PCB says %.2f mm.\n'
                        'Continue anyway?' % (span * 10, HOLE_SPAN_CM * 10),
                        'Hole check', adsk.core.MessageBoxButtonTypes.YesNoButtonType) \
                        != adsk.core.DialogResults.DialogYes:
                    return

            summary = cutSlot(face, hFar, plateNormal, hNear,
                              ins.itemById('along').value,
                              ins.itemById('standoff').value,
                              ins.itemById('slotW').value,
                              ins.itemById('slotH').value,
                              ins.itemById('slotR').value)
            _ui.messageBox('Done!\n\n' + summary +
                           '\n\nIf it looks wrong, delete the last sketch + cut '
                           'in the timeline and run again.')
        except Exception:
            _ui.messageBox('TXV13Hole failed:\n{}'.format(traceback.format_exc()))


class TXV13Destroy(adsk.core.CommandEventHandler):
    def notify(self, args):
        adsk.terminate()


def run(context):
    global _app, _ui
    _app = adsk.core.Application.get()
    _ui = _app.userInterface
    try:
        doc = _app.activeDocument
        if not doc or not doc.dataFile:
            _ui.messageBox('Open TXV13 (or TXV12a) first — a saved cloud document.')
            return

        # Work in TXV13; make it from the active doc if needed (original untouched).
        if not doc.name.startswith('TXV13'):
            if not doc.saveAs('TXV13', doc.dataFile.parentFolder,
                              'USB-C charging slot, located from the TXV2_MAIN PCB '
                              '(by Claude and Malcolm)', ''):
                _ui.messageBox('Save-As "TXV13" failed — open TXV13 from the data '
                               'panel (it exists from the earlier run) and run again.')
                return
            adsk.doEvents()

        cmdDef = _ui.commandDefinitions.itemById(CMD_ID)
        if cmdDef:
            cmdDef.deleteMe()
        cmdDef = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, 'TXV13 USB-C slot',
            'Cut the USB-C charging slot located from the TX_Support holes')
        onCreated = TXV13Created()
        cmdDef.commandCreated.add(onCreated)
        _handlers.append(onCreated)
        cmdDef.execute()
        adsk.autoTerminate(False)   # stay alive while the dialog is open
    except Exception:
        _ui.messageBox('TXV13Hole failed to start:\n{}'.format(traceback.format_exc()))
