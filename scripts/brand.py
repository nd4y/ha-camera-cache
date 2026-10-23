"""Export a small original code-drawn brand icon; no external artwork."""
from pathlib import Path
import struct
import zlib

SIZE=256


def color(x,y):
    camera=(36<=x<220 and 66<=y<194) or (72<=x<126 and 49<=y<70)
    lens=(x-123)**2+(y-129)**2<38**2
    ring=30**2<(x-186)**2+(y-186)**2<48**2
    clock=(abs(x-186)<5 and 157<y<188) or (abs(y-x)<6 and 185<x<208 and 185<y<208)
    if ring or clock:return (155,205,255,255)
    if lens:return (18,30,47,255)
    if camera:return (155,205,255,255)
    return (0,0,0,0)


def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)


raw=b''.join(b'\0'+bytes(channel for x in range(SIZE) for channel in color(x,y)) for y in range(SIZE))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',SIZE,SIZE,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
target=Path(__file__).resolve().parents[1]/'custom_components/camera_cache/brand/icon.png'
target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(png)
