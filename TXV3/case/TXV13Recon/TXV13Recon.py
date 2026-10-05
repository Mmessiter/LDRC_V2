# TXV13Recon — Fusion 360 script, by Claude and Malcolm, July 2026
#
# ZERO clicks: walks the ACTIVE design and writes its structure to
#     ~/Documents/GitHub/LDRC_V2_ALL/TXV2/case/txv13_recon.json
# so Claude can "see" the model and generate a fully-automatic cutting
# script. Reads only — changes nothing.

import adsk.core, adsk.fusion, traceback, json, os

OUT = os.path.expanduser('~/Documents/GitHub/LDRC_V2_ALL/TXV2/case/txv13_recon.json')

def p3(p):  # Point3D/Vector3D -> [x,y,z] in mm
    return [round(p.x * 10, 3), round(p.y * 10, 3), round(p.z * 10, 3)]


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active design.')
            return

        out = {
            'document': app.activeDocument.name,
            'units': 'mm',
            'bodies': [],
        }

        def bbox(bb):
            return {'min': p3(bb.minPoint), 'max': p3(bb.maxPoint)}

        def dumpBody(body, path):
            if not body.isVisible:
                return
            b = {
                'name': body.name,
                'component': path,
                'token': body.entityToken,
                'bbox': bbox(body.boundingBox),
                'faces': body.faces.count,
                'planarFaces': [],
                'circularEdges': [],
            }
            for f in body.faces:
                try:
                    pl = adsk.core.Plane.cast(f.geometry)
                    if not pl:
                        continue
                    if f.area < 1.0:          # skip tiny faces (< 100 mm^2)
                        continue
                    b['planarFaces'].append({
                        'token': f.entityToken,
                        'areaMm2': round(f.area * 100, 1),
                        'normal': p3(pl.normal),
                        'point': p3(f.pointOnFace),
                        'bbox': bbox(f.boundingBox),
                    })
                except Exception:
                    pass
            for e in body.edges:
                try:
                    g = e.geometry
                    isCirc = g.objectType == adsk.core.Circle3D.classType()
                    isArc = g.objectType == adsk.core.Arc3D.classType()
                    if not (isCirc or isArc):
                        continue
                    r = g.radius * 10
                    if r < 0.8 or r > 4.0:    # keep screw-hole-ish rims (1.6-8 mm dia)
                        continue
                    b['circularEdges'].append({
                        'token': e.entityToken,
                        'radiusMm': round(r, 3),
                        'center': p3(g.center),
                        'normal': p3(g.normal),
                        'arc': isArc,
                    })
                except Exception:
                    pass
            out['bodies'].append(b)

        root = design.rootComponent
        for body in root.bRepBodies:
            dumpBody(body, root.name)
        for occ in root.allOccurrences:
            if not occ.isVisible:
                continue
            for body in occ.bRepBodies:
                dumpBody(body, occ.fullPathName)

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w') as f:
            json.dump(out, f, indent=1)

        nb = len(out['bodies'])
        ne = sum(len(b['circularEdges']) for b in out['bodies'])
        nf = sum(len(b['planarFaces']) for b in out['bodies'])
        ui.messageBox('Recon complete — nothing was modified.\n\n'
                      '%d visible bodies, %d wall-sized planar faces, %d screw-hole '
                      'edges written to:\n%s\n\nNow tell Claude "recon done".'
                      % (nb, nf, ne, OUT))
    except Exception:
        ui.messageBox('TXV13Recon failed:\n{}'.format(traceback.format_exc()))
