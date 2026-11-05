import sys
b=open(sys.argv[1],'rb').read()
o=2+16*10+2
mn=b[o]; o+=1; st=b[o]|b[o+1]<<8; o+=2; ina=b[o]; o+=1; name=b[o:o+30].split(b'\0')[0].decode('latin1'); o+=30; o+=2; o+=2
bg=b[o]; o+=2; o+=6
f=['SticksMode','Volume','Brightness','Fanfare','TrimClicks','Vario','Clock','AnnBanks']
v=dict(zip(f,b[o:o+8])); o+=8; sw=list(b[o:o+8]); o+=8
v.update(dict(zip(['ScanSens','MinGap','LogSwaps','UseLog','AnnConnected'],b[o:o+5]))); o+=5
print(sys.argv[1].split('/')[-1], 'model',mn,'name',repr(name),'screenTO',st,'inact',ina,'bg',bg, v, 'switches',sw)
