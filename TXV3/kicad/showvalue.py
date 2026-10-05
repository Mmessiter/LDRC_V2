import re
s = open('TXV2_MAIN.kicad_pcb').read()
def blocks(src):
    return [(m.start(),) for m in re.finditer(r'\(footprint "', src)]
def prop_span(fp, name):
    m = re.search(r'\(property "%s"' % re.escape(name), fp)
    if not m: return None
    i=m.start(); d=0
    for j in range(i,len(fp)):
        if fp[j]=='(':d+=1
        elif fp[j]==')':
            d-=1
            if d==0:return (i,j+1)
def fp_span(src, i):
    d=0
    for j in range(i,len(src)):
        if src[j]=='(':d+=1
        elif src[j]==')':
            d-=1
            if d==0:return j+1
starts=[m.start() for m in re.finditer(r'\(footprint "', s)]
for i in reversed(starts):
    j=fp_span(s,i); fp=s[i:j]
    if '"MountingHole' in fp[:120]:  # hide value too
        vs=prop_span(fp,"Value")
        if vs and '(hide yes)' not in fp[vs[0]:vs[1]]:
            fp=fp[:vs[0]]+fp[vs[0]:vs[1]].replace('(at ','(hide yes)\n\t\t(at ',1)+fp[vs[1]:]
        s=s[:i]+fp+s[j:]; continue
    back='(layer "B.Cu")' in fp[:200]
    silk="B.SilkS" if back else "F.SilkS"
    rs=prop_span(fp,"Reference")
    if rs and '(hide yes)' not in fp[rs[0]:rs[1]]:
        fp=fp[:rs[0]]+fp[rs[0]:rs[1]].replace('(at ','(hide yes)\n\t\t(at ',1)+fp[rs[1]:]
    vs=prop_span(fp,"Value")
    if vs:
        vb=fp[vs[0]:vs[1]]
        vb=vb.replace('(hide yes)\n\t\t\t','').replace('(hide yes)\n\t\t','').replace(' (hide yes)','')
        vb=re.sub(r'\(layer "[^"]*"\)', f'(layer "{silk}")', vb, count=1)
        vb=re.sub(r'\(size [\d.]+ [\d.]+\)', '(size 0.9 0.9)', vb, count=1)
        fp=fp[:vs[0]]+vb+fp[vs[1]:]
    s=s[:i]+fp+s[j:]
open('TXV2_MAIN.kicad_pcb','w').write(s)
print("values on silk")
