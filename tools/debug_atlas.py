#!/usr/bin/env python3
"""
Save Wilson's atlas and annotated sprite regions so we can see exactly what
find_hair_regions and find_face_regions are targeting.
"""
import struct, zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import texture2ddecoder
from scipy import ndimage

DS_DATA = Path("/home/eric/snap/steam/common/.local/share/Steam/steamapps/common/dont_starve/data")
OUT = Path("/tmp/atlas_debug")
OUT.mkdir(exist_ok=True)

def decode_ktex(data):
    assert data[:4] == b'KTEX'
    hdr      = struct.unpack('<I', data[4:8])[0]
    pixfmt   = (hdr >> 4) & 0x1F
    num_mips = (hdr >> 13) & 0x1F
    w, h, pitch, size = struct.unpack('<HHHi', data[8:18])
    data_start = 8 + num_mips * 10
    raw = data[data_start:data_start + size]
    if pixfmt == 2:
        rgba = texture2ddecoder.decode_bc3(raw, w, h)
    elif pixfmt == 0:
        rgba = texture2ddecoder.decode_bc1(raw, w, h)
    else:
        rgba = raw
    img = Image.frombytes('RGBA', (w, h), rgba)
    return img.transpose(Image.FLIP_TOP_BOTTOM)

with zipfile.ZipFile(DS_DATA / "anim" / "wilson.zip") as z:
    atlas = decode_ktex(z.read('atlas-0.tex'))

# Save raw atlas
atlas.save(OUT / "wilson_atlas.png")
print(f"Saved atlas {atlas.size}")

arr = np.array(atlas)
alpha = arr[:,:,3]
mask  = alpha > 20
labeled, ns = ndimage.label(mask)
slices = ndimage.find_objects(labeled)

annotated = atlas.copy().convert('RGB')
draw = ImageDraw.Draw(annotated)

hair_regions = []
face_regions = []

for i, sl in enumerate(slices):
    if sl is None: continue
    rsl, csl = sl
    r0, r1 = rsl.start, rsl.stop
    c0, c1 = csl.start, csl.stop
    h = r1 - r0
    w = c1 - c0
    if h < 60 or w < 60: continue

    sprite_mask = labeled[rsl, csl] == (i + 1)
    sprite_px   = arr[rsl, csl]
    opaque      = sprite_mask & (sprite_px[:,:,3] > 50)
    if opaque.sum() < 1000: continue
    avg_brightness = float(sprite_px[:,:,:3][opaque].mean())

    # Hair: dark + large
    if avg_brightness < 80 and opaque.sum() >= 5000:
        hair_regions.append((r0, c0, w, h))
        draw.rectangle([c0, r0, c1, r1], outline=(255, 0, 0), width=2)
        # Save individual sprite
        crop = atlas.crop((c0, r0, c1, r1))
        crop.save(OUT / f"hair_{len(hair_regions):02d}_r{r0}c{c0}_{w}x{h}.png")
        continue

    # Face candidates: top portion of atlas, right side, brightness in range
    if r0 < 5 or r0 > 220: continue
    if c0 < 900: continue
    if w < 60 or w > 220 or h < 60 or h > 220: continue
    aspect = w / h
    if aspect > 2.0 or aspect < 0.5: continue
    if avg_brightness > 215 or avg_brightness < 25: continue

    face_regions.append((r0, c0, w, h))
    draw.rectangle([c0, r0, c1, r1], outline=(0, 128, 255), width=2)
    crop = atlas.crop((c0, r0, c1, r1))
    crop.save(OUT / f"face_{len(face_regions):02d}_r{r0}c{c0}_{w}x{h}_br{avg_brightness:.0f}.png")

annotated.save(OUT / "wilson_annotated.png")
print(f"Hair regions: {len(hair_regions)}")
for r,c,w,h in hair_regions:
    print(f"  ({r},{c}) {w}x{h}")
print(f"Face regions: {len(face_regions)}")
for r,c,w,h in face_regions:
    print(f"  ({r},{c}) {w}x{h}")
print(f"Sprites saved to {OUT}/")
