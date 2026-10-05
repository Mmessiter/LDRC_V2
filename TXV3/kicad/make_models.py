import os
OUT=os.path.expanduser("~/Documents/KiCad/TXV2_MAIN/models"); os.makedirs(OUT,exist_ok=True)
S=2.54  # KiCad VRML: 1 unit = 0.1 inch
def wrl(name, parts):
    shapes=[]
    for dx,dy,dz,cx,cy,cz,col in parts:
        hx,hy=dx/2/S,dy/2/S; z0,z1=cz/S,(cz+dz)/S; x0,y0=cx/S,cy/S
        v=[(x0-hx,y0-hy,z0),(x0+hx,y0-hy,z0),(x0+hx,y0+hy,z0),(x0-hx,y0+hy,z0),
           (x0-hx,y0-hy,z1),(x0+hx,y0-hy,z1),(x0+hx,y0+hy,z1),(x0-hx,y0+hy,z1)]
        pts=",\n            ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x,y,z in v)
        # outward winding, CCW viewed from outside
        idx="1,2,3,0,-1, 4,5,6,7,-1, 0,4,7,3,-1, 1,5,4,0,-1, 2,6,5,1,-1, 3,7,6,2,-1"
        shapes.append(f'''    Shape {{
      appearance Appearance {{
        material Material {{
          diffuseColor {col}
          emissiveColor 0 0 0
          specularColor 0.1 0.1 0.1
          ambientIntensity 0.2
          transparency 0
          shininess 0.1
        }}
      }}
      geometry IndexedFaceSet {{
        ccw TRUE
        solid FALSE
        coord Coordinate {{
          point [
            {pts}
          ]
        }}
        coordIndex [ {idx} ]
      }}
    }}''')
    body="#VRML V2.0 utf8\nTransform {\n  children [\n"+",\n".join(shapes)+"\n  ]\n}\n"
    open(f"{OUT}/{name}.wrl","w").write(body)
    print("wrote",name)

wrl("teensy41",[
    (17.8,61,1.6, 7.62,29.21,8.5, "0.05 0.35 0.15"),
    (8,6,3, 7.62,1.5,10.1, "0.75 0.75 0.78"),
    (12,11,2, 7.62,55,6.6, "0.55 0.55 0.58"),
    (12,12,1, 7.62,30,10.1, "0.15 0.15 0.15"),
])
wrl("devkitc",[
    (25.4,56,1.6, 11.43,26.5,8.5, "0.05 0.35 0.15"),
    (18,25.5,3.1, 11.43,13,10.1, "0.75 0.75 0.78"),
    (9,7,3.2, 3,1,10.1, "0.55 0.55 0.58"),
    (9,7,3.2, 19.9,1,10.1, "0.55 0.55 0.58"),
])
wrl("nrf24e01",[
    (39,17,1.6, 14.5,3.8,8.5, "0.05 0.4 0.15"),
    (17,15,2.5, 16.5,3.8,10.1, "0.75 0.75 0.78"),
    (10,6.3,6.3, 36.5,3.8,7.0, "0.85 0.7 0.2"),
])
wrl("pololu2808",[
    (15,17.8,1.6, 6.15,7.62,8.5, "0.15 0.25 0.6"),
    (6,6,1.5, 6.15,7.62,10.1, "0.2 0.2 0.2"),
])
wrl("buck3pin",[
    (12,4,1.6, 2.54,-0.8,8.5, "0.05 0.35 0.15"),
    (6,3,2, 2.54,-0.8,10.1, "0.2 0.2 0.2"),
])
