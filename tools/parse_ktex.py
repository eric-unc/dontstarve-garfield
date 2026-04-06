#!/usr/bin/env python3
"""Parse a KTEX texture file and report its structure."""
import struct, sys, zipfile

def parse_ktex(data):
    assert data[:4] == b'KTEX', "Not a KTEX file"
    hdr = struct.unpack('<I', data[4:8])[0]
    platform = hdr & 0xF
    pixfmt   = (hdr >> 4) & 0x1F
    textype  = (hdr >> 9) & 0xF
    num_mips = (hdr >> 13) & 0x1F
    flags    = (hdr >> 18) & 0x3
    print(f"Platform:    {platform}")
    print(f"PixelFormat: {pixfmt}  (0=DXT1 1=DXT3 2=DXT5 4=RGBA8 5=RGB8)")
    print(f"TexType:     {textype}")
    print(f"NumMips:     {num_mips}")
    print(f"Flags:       {flags}")
    offset = 8
    mips = []
    for i in range(num_mips):
        w, h, pitch, size = struct.unpack('<HHIi', data[offset:offset+12])
        print(f"  Mip {i}: {w}x{h}  pitch={pitch}  datasize={size}")
        mips.append((w, h, pitch, size))
        offset += 12
    return mips, offset

path = sys.argv[1]
if path.endswith('.zip'):
    z = zipfile.ZipFile(path)
    data = z.read('atlas-0.tex')
else:
    data = open(path, 'rb').read()

parse_ktex(data)
