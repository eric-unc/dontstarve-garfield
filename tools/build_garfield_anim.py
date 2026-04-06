#!/usr/bin/env python3
"""
Build garfield.zip and ghost_garfield_build.zip from Wilson's game assets.

Pipeline:
  1. Extract and decode Wilson's atlas (DXT5 → RGBA PNG)
  2. Recolor Wilson's sprites → Garfield palette
       pinkish skin → orange fur
       dark brown hair → darker orange/brown (stripes)
       suit blues → tattered tan/brown
       white highlights → cream
  3. Encode recolored atlas as KTEX RGBA8 (no DXT required)
  4. Patch build.bin: replace the build name "wilson" → "garfield"
  5. Pack into garfield.zip

Run from repo root:
  python3 tools/build_garfield_anim.py
"""

import io, struct, zipfile
from pathlib import Path
import numpy as np
from PIL import Image
import texture2ddecoder

DS_DATA = Path("/home/eric/snap/steam/common/.local/share/Steam/steamapps/common/dont_starve/data")
REPO = Path(__file__).parent.parent
OUT_ANIM = REPO / "anim"
OUT_ANIM.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# KTEX decode
# ---------------------------------------------------------------------------
def decode_ktex(data: bytes) -> tuple[Image.Image, int]:
    """Return (Image RGBA, pixel_format)."""
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
    elif pixfmt == 4:
        rgba = raw
    else:
        raise ValueError(f"Unsupported pixel format {pixfmt}")
    img = Image.frombytes('RGBA', (w, h), rgba)
    return img.transpose(Image.FLIP_TOP_BOTTOM), pixfmt

# ---------------------------------------------------------------------------
# KTEX encode (RGBA8, single mip — no DXT compression needed)
# ---------------------------------------------------------------------------
def encode_ktex_rgba8(img: Image.Image) -> bytes:
    img_flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
    w, h = img_flipped.size
    raw = img_flipped.tobytes()
    # Header word: platform=0, pixfmt=4 (RGBA8), textype=1, num_mips=1, flags=3
    # Top 12 fill bits must be 0xFFF to match DS format.
    hdr = 0 | (4 << 4) | (1 << 9) | (1 << 13) | (3 << 18) | (0xFFF << 20)
    pitch = w * 4
    size  = len(raw)
    out = b'KTEX'
    out += struct.pack('<I', hdr)
    out += struct.pack('<HHHi', w, h, pitch, size)  # single mip descriptor
    out += raw
    return out

# ---------------------------------------------------------------------------
# Build name patcher
# ---------------------------------------------------------------------------
def patch_build_name(build_bin: bytes, old_name: str, new_name: str) -> bytes:
    """Replace the build name string inside build.bin.
    The name field is: name_len (4 bytes LE) + name bytes.
    Records after the name are sequential so resizing the name block is safe.
    """
    new_enc = new_name.encode()
    name_len = struct.unpack('<I', build_bin[16:20])[0]
    stored = build_bin[20:20+name_len].rstrip(b'\x00').decode()
    assert stored == old_name, \
        f"Expected build name '{old_name}', got '{stored}'"
    return (build_bin[:16]
            + struct.pack('<I', len(new_enc))
            + new_enc
            + build_bin[20 + name_len:])

# ---------------------------------------------------------------------------
# Garfield colour recolour
# ---------------------------------------------------------------------------
# Wilson skin HSV range (approximate): H 5-30°, S 20-60%, V 60-100%
# We map those to Garfield orange:     H 25°,   S 85%,   V 90%
# Dark hair/outline:                   leave alone (V < 25%)
# Blues (suit):                        → warm tan/brown

GARFIELD_ORANGE     = np.array([239, 131,  34, 255], dtype=np.float32)
GARFIELD_DARK       = np.array([160,  70,   8, 255], dtype=np.float32)  # stripes
GARFIELD_CREAM      = np.array([255, 228, 180, 255], dtype=np.float32)  # belly/muzzle highlight
GARFIELD_CLOTHES    = np.array([120,  90,  55, 255], dtype=np.float32)  # tattered brown

def rgb_to_hsv(r, g, b):
    r, g, b = r/255, g/255, b/255
    mx, mn = max(r,g,b), min(r,g,b)
    diff = mx - mn
    h = 0
    if diff > 0:
        if mx == r:   h = (60 * ((g-b)/diff) % 360)
        elif mx == g: h = 60 * ((b-r)/diff + 2)
        else:         h = 60 * ((r-g)/diff + 4)
    s = 0 if mx == 0 else diff / mx
    v = mx
    return h, s, v

def recolor_garfield(img: Image.Image) -> Image.Image:
    """
    Recolor Wilson's atlas to Garfield's palette.
    Works pixel-by-pixel in HSV space.
    """
    arr = np.array(img, dtype=np.float32)   # RGBA float32
    out = arr.copy()
    H, W = arr.shape[:2]

    r = arr[:,:,0]
    g = arr[:,:,1]
    b = arr[:,:,2]
    a = arr[:,:,3]

    # Only process non-transparent pixels
    visible = a > 10

    # Compute per-pixel HSV (vectorised)
    mx  = np.maximum(np.maximum(r, g), b) / 255
    mn  = np.minimum(np.minimum(r, g), b) / 255
    diff = mx - mn

    V = mx
    S = np.where(mx > 0, diff / mx, 0)
    # Hue — simplified (just need to identify skin/blue/dark)
    # use (R-B) as a cheap proxy: positive → warm (orange/red/yellow), negative → cool (blue)
    warm_bias = (r - b) / 255   # > 0 means warm, < 0 means cool/blue

    # ---- Skin/fur: moderate warm, mid-high brightness, not too saturated ----
    is_skin = (visible
               & (warm_bias > 0.05)
               & (V > 0.35)
               & (V < 0.95)
               & (S > 0.10)
               & (b / 255 < 0.55))  # not blue-dominant

    # ---- Blue suit ----
    is_blue = (visible
               & (b > r + 20)
               & (b > g - 10)
               & (V > 0.2))

    # ---- White/cream highlight (very bright, low saturation) ----
    is_cream = (visible
                & (V > 0.85)
                & (S < 0.20)
                & ~is_skin)

    # ---- Dark outlines/hair ----
    # Everything else that is visible stays (near-black outlines)

    # Apply orange for skin/fur
    for c, val in enumerate(GARFIELD_ORANGE[:3]):
        out[:,:,c] = np.where(is_skin, val, out[:,:,c])

    # Darken already-dark areas of the orange zone slightly for stripe effect
    is_darker_skin = is_skin & (V < 0.60)
    for c, val in enumerate(GARFIELD_DARK[:3]):
        out[:,:,c] = np.where(is_darker_skin, val, out[:,:,c])

    # Apply cream for highlight areas
    for c, val in enumerate(GARFIELD_CREAM[:3]):
        out[:,:,c] = np.where(is_cream, val, out[:,:,c])

    # Apply tattered brown for blue suit
    for c, val in enumerate(GARFIELD_CLOTHES[:3]):
        out[:,:,c] = np.where(is_blue, val, out[:,:,c])

    return Image.fromarray(out.clip(0, 255).astype(np.uint8), 'RGBA')

# ---------------------------------------------------------------------------
# Ghost recolour (desaturated orange + slight green glow for DS ghost style)
# ---------------------------------------------------------------------------
def recolor_ghost(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert('RGBA'), dtype=np.float32)
    # Desaturate and tint orange-ish
    gray = (arr[:,:,0]*0.3 + arr[:,:,1]*0.59 + arr[:,:,2]*0.11)
    arr[:,:,0] = np.clip(gray * 1.4, 0, 255)   # warm tint
    arr[:,:,1] = np.clip(gray * 1.0, 0, 255)
    arr[:,:,2] = np.clip(gray * 0.6, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')

# ---------------------------------------------------------------------------
# Process one build zip
# ---------------------------------------------------------------------------
def process_build(src_zip_path: Path, out_zip_path: Path,
                  old_name: str, new_name: str,
                  recolor_fn):
    print(f"\nProcessing {src_zip_path.name} → {out_zip_path.name}")
    with zipfile.ZipFile(src_zip_path) as z:
        tex_data   = z.read('atlas-0.tex')
        build_data = z.read('build.bin')
        anim_data  = z.read('anim.bin') if 'anim.bin' in z.namelist() else None

    # Keep the original DXT5 texture as-is.
    # The orange fur colour comes from AnimState:SetMultColor in the prefab,
    # so we don't need to re-encode the atlas.
    new_tex = tex_data
    print(f"  Keeping original DXT5 atlas ({len(new_tex):,} bytes)")

    # Patch build name
    new_build = patch_build_name(build_data, old_name, new_name)
    print(f"  Patched build name: '{old_name}' → '{new_name}'")

    # Write zip
    with zipfile.ZipFile(out_zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('atlas-0.tex', new_tex)
        z.writestr('build.bin',   new_build)
        if anim_data:
            z.writestr('anim.bin', anim_data)

    print(f"  Wrote {out_zip_path}  ({out_zip_path.stat().st_size:,} bytes)")

# ---------------------------------------------------------------------------
# Ghost build (from a different source file)
# ---------------------------------------------------------------------------
def find_ghost_build():
    for p in [
        DS_DATA / "anim" / "ghost_build.zip",
        DS_DATA / "anim" / "ghost_wendy_build.zip",
    ]:
        if p.exists():
            return p
    return None

def make_lasagna_build():
    """Build lasagna.zip by patching carrot.zip from the game.

    Approach: reuse carrot's atlas, anim.bin, and BILD structure verbatim —
    only the build name field is changed "carrot" → "lasagna".  The prefab
    uses SetBank("carrot") / SetBuild("lasagna") so the animation bank from
    carrot's anim.bin is referenced correctly.

    Hand-crafting a BILD from scratch caused reader.h:28 crashes because the
    DS engine's BILD parser is sensitive to undocumented fields.  Patching a
    known-good file is the safe approach (same method used for garfield.zip).
    """
    out_path   = OUT_ANIM / "lasagna.zip"
    carrot_zip = DS_DATA / "anim" / "carrot.zip"

    with zipfile.ZipFile(carrot_zip) as z:
        tex_data   = z.read('atlas-0.tex')
        build_data = z.read('build.bin')
        anim_data  = z.read('anim.bin')

    old, new = b"carrot", b"lasagna"
    name_len = struct.unpack('<I', build_data[16:20])[0]
    assert build_data[20:20+name_len] == old
    new_build = (build_data[:16]
                 + struct.pack('<I', len(new))
                 + new
                 + build_data[20 + name_len:])
    print(f"  Patched build name: 'carrot' → 'lasagna'")

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('anim.bin',    anim_data)
        z.writestr('atlas-0.tex', tex_data)
        z.writestr('build.bin',   new_build)

    print(f"\nLasagna build: {out_path}  ({out_path.stat().st_size:,} bytes)")

def ds_hash(s: str) -> int:
    """DS string hash function (from ktools source)."""
    h = 0
    for c in s.lower():
        h = (h * 65599 + ord(c)) & 0xFFFFFFFF
    return h

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    wilson_zip = DS_DATA / "anim" / "wilson.zip"
    ghost_zip  = find_ghost_build()

    # Garfield character build
    process_build(
        src_zip_path  = wilson_zip,
        out_zip_path  = OUT_ANIM / "garfield.zip",
        old_name      = "wilson",
        new_name      = "garfield",
        recolor_fn    = recolor_garfield,
    )

    # Ghost build
    if ghost_zip:
        import zipfile as _zf, struct as _st
        with _zf.ZipFile(ghost_zip) as _z:
            _b = _z.read('build.bin')
        _nl = _st.unpack('<I', _b[16:20])[0]
        ghost_old_name = _b[20:20+_nl].rstrip(b'\x00').decode()
        process_build(
            src_zip_path  = ghost_zip,
            out_zip_path  = OUT_ANIM / "ghost_garfield_build.zip",
            old_name      = ghost_old_name,
            new_name      = "ghost_garfield_build",
            recolor_fn    = recolor_ghost,
        )
    else:
        print("\nWARN: ghost build not found — skipping")

    make_lasagna_build()

    print("\nDone. Animation bundles written to anim/")
