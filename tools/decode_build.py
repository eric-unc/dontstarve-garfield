#!/usr/bin/env python3
"""
Decode a DS character build zip into:
  - atlas.png  (the decoded sprite sheet)
  - build.json (human-readable symbol/frame layout)

Usage: python3 decode_build.py <path/to/build.zip> <out_dir>
"""
import json, struct, sys, zipfile
from PIL import Image
import texture2ddecoder

def decode_ktex(data):
    assert data[:4] == b'KTEX'
    hdr = struct.unpack('<I', data[4:8])[0]
    pixfmt   = (hdr >> 4) & 0x1F
    num_mips = (hdr >> 13) & 0x1F
    desc_offset = 8
    w, h, pitch, size = struct.unpack('<HHHi', data[desc_offset:desc_offset+10])
    data_start = desc_offset + num_mips * 10
    raw = data[data_start:data_start+size]
    if pixfmt == 2:   # DXT5 / BC3
        rgba = texture2ddecoder.decode_bc3(raw, w, h)
    elif pixfmt == 0: # DXT1 / BC1
        rgba = texture2ddecoder.decode_bc1(raw, w, h)
    elif pixfmt == 4: # RGBA8
        rgba = raw
    else:
        raise ValueError(f"Unsupported pixel format {pixfmt}")
    img = Image.frombytes('RGBA', (w, h), rgba)
    # DS atlases are stored bottom-up (OpenGL convention)
    return img.transpose(Image.FLIP_TOP_BOTTOM), w, h

def parse_buildbин(data):
    assert data[:4] == b'BILD'
    version     = struct.unpack('<I', data[4:8])[0]
    num_symbols = struct.unpack('<I', data[8:12])[0]
    num_frames  = struct.unpack('<I', data[12:16])[0]
    name_len    = struct.unpack('<I', data[16:20])[0]
    name        = data[20:20+name_len].rstrip(b'\x00').decode()
    offset = 20 + name_len

    # Atlas name table (sits between build name and symbol table)
    num_atlases = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
    for _ in range(num_atlases):
        alen = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
        offset += alen  # skip atlas name string

    symbols = []
    for _ in range(num_symbols):
        sym_hash   = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
        num_frames_in_sym = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
        frames = []
        for _ in range(num_frames_in_sym):
            frame_num = struct.unpack('<I',   data[offset:offset+4])[0]; offset += 4
            duration  = struct.unpack('<I',   data[offset:offset+4])[0]; offset += 4
            x         = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            y         = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            w         = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            h         = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            # UV coords into atlas (normalised 0..1)
            u1        = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            v1        = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            u2        = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            v2        = struct.unpack('<f',   data[offset:offset+4])[0]; offset += 4
            atlas_idx = struct.unpack('<I',   data[offset:offset+4])[0]; offset += 4
            frames.append(dict(frame_num=frame_num, duration=duration,
                               x=x, y=y, w=w, h=h,
                               u1=u1, v1=v1, u2=u2, v2=v2,
                               atlas_idx=atlas_idx))
        symbols.append(dict(hash=sym_hash, frames=frames))

    # Symbol name hash table follows
    num_hashes = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
    hash_to_name = {}
    for _ in range(num_hashes):
        h = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
        slen = struct.unpack('<I', data[offset:offset+4])[0]; offset += 4
        s = data[offset:offset+slen].rstrip(b'\x00').decode(); offset += slen
        hash_to_name[h] = s

    for sym in symbols:
        sym['name'] = hash_to_name.get(sym['hash'], f"hash_{sym['hash']:08x}")

    return dict(version=version, name=name, num_symbols=num_symbols,
                num_frames=num_frames, symbols=symbols)

if __name__ == '__main__':
    import os
    zip_path = sys.argv[1]
    out_dir  = sys.argv[2] if len(sys.argv) > 2 else '.'
    os.makedirs(out_dir, exist_ok=True)

    z = zipfile.ZipFile(zip_path)
    img, aw, ah = decode_ktex(z.read('atlas-0.tex'))
    img.save(os.path.join(out_dir, 'atlas.png'))
    print(f"Atlas: {aw}x{ah} → {out_dir}/atlas.png")

    build = parse_buildbин(z.read('build.bin'))
    with open(os.path.join(out_dir, 'build.json'), 'w') as f:
        json.dump(build, f, indent=2)
    print(f"Build: {build['name']}  symbols={build['num_symbols']}  frames={build['num_frames']}")
    print("Symbols:", [s['name'] for s in build['symbols']])
