"""Pictogrammes originaux, PNG transparents autonomes, sans dépendance externe."""
import math
import struct
import zlib

COLOURS={'rando':(46,125,50),'ski':(21,101,192),'raquettes':(123,31,162),'escalade':(230,81,0)}
LABELS={'rando':'Rando','raquettes':'Raq.','ski':'Ski','escalade':'Esc.'}
ORDER=('rando','raquettes','ski','escalade')


def activity_scale(types):
    return .65*max(1,len(set(types)&set(ORDER)))


def key(types):return '-'.join(t for t in ORDER if t in types) or 'bus'


def label(types):
    values=[LABELS[t] for t in ORDER if t in types]
    return '/'.join(values) if len(values)<=2 else 'Multi'


class Canvas:
    def __init__(self):self.n=144;self.raw=bytearray(self.n*self.n*4)
    def disc(self,x,y,r,c):
        x*=3;y*=3;r*=3
        for yy in range(max(0,int(y-r)),min(self.n,int(y+r)+1)):
            for xx in range(max(0,int(x-r)),min(self.n,int(x+r)+1)):
                if (xx+.5-x)**2+(yy+.5-y)**2<=r*r:
                    i=4*(yy*self.n+xx);self.raw[i:i+4]=bytes((*c,255))
    def line(self,a,b,width,c):
        steps=max(1,int(math.dist(a,b)*5))
        for i in range(steps+1):
            f=i/steps;self.disc(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,width/2,c)
    def png(self):
        rows=bytearray()
        for y in range(48):
            rows.append(0)
            for x in range(48):
                pixels=[self.raw[4*((y*3+j)*self.n+x*3+i):4*((y*3+j)*self.n+x*3+i)+4] for j in range(3) for i in range(3)]
                alpha=sum(p[3] for p in pixels)
                rows.extend([round(sum(p[k]*p[3] for p in pixels)/alpha) if alpha else 0 for k in range(3)]+[round(alpha/9)])
        def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
        return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',48,48,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(rows)))+chunk(b'IEND',b'')


def glyph(c,kind,cx,cy,scale=1):
    white=(255,255,255)
    def p(x,y):return (cx+(x-12)*scale,cy+(y-12)*scale)
    def line(a,b,w=2):c.line(p(*a),p(*b),w*scale,white)
    c.disc(*p(12,4),2*scale,white)
    if kind=='ski':
        for a,b in [((10,8),(14,13)),((10,8),(7,13)),((7,13),(14,13)),((14,13),(10,18)),((10,18),(17,20)),((11,10),(18,11)),((18,11),(20,20)),((5,23),(22,20)),((3,20),(19,17))]:line(a,b)
    elif kind=='escalade':
        for a,b in [((12,8),(11,14)),((12,9),(6,8)),((6,8),(6,3)),((12,10),(18,7)),((18,7),(19,2)),((11,14),(7,18)),((7,18),(3,17)),((11,14),(16,18)),((16,18),(19,15))]:line(a,b)
    else:
        for a,b in [((11,8),(11,15)),((10,9),(6,12)),((11,10),(16,11)),((16,11),(19,7)),((11,15),(7,22)),((11,15),(17,21)),((19,7),(19,23))]:line(a,b)
        if kind=='raquettes':
            line((3,23),(10,23),2.5);line((14,22),(21,22),2.5)
        else:line((7,8),(7,13),3)


def bus(c,x,y,scale=1):
    blue=(21,65,98);white=(255,255,255)
    c.disc(x,y,8*scale,white);c.disc(x,y,6.5*scale,blue)
    for a,b in [((-4,-4),(4,-4)),((-4,-4),(-4,3)),((4,-4),(4,3)),((-4,1),(4,1)),((-4,3),(4,3))]:
        c.line((x+a[0]*scale,y+a[1]*scale),(x+b[0]*scale,y+b[1]*scale),1.4*scale,white)
    c.disc(x-2.5*scale,y+4.5*scale,1*scale,white);c.disc(x+2.5*scale,y+4.5*scale,1*scale,white)


def icon(types,stop=False):
    types=[t for t in ORDER if t in types];c=Canvas()
    if not types:
        c.disc(24,24,22,(255,255,255));bus(c,24,24,2.2)
    elif len(types)==1:
        c.disc(24,24,22,(255,255,255));c.disc(24,24,20,COLOURS[types[0]]);glyph(c,types[0],24,24,1.25)
        if stop:bus(c,37,37,.95)
    else:
        c.disc(24,24,23,(255,255,255))
        positions=[(13,24),(35,24)] if len(types)==2 else [(13,13),(35,13),(13,35),(35,35)]
        for kind,(x,y) in zip(types,positions):c.disc(x,y,11,COLOURS[kind]);glyph(c,kind,x,y,.75)
        if stop:bus(c,24,24,.85)
    return c.png()
