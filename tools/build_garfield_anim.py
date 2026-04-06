#!/usr/bin/env python3
"""
Build garfield.zip and ghost_garfield_build.zip from Wilson's game assets.

Pipeline:
  1. Extract and decode Wilson's atlas (DXT5 → RGBA PNG)
  2. Find the 8 large dark "hair" sprites via blob detection
  3. Replace each hair sprite with cat ear art (transparent background,
     two pointed ears at the top; one ear for side-view frames)
  4. Re-encode atlas as KTEX DXT5 (via ImageMagick) or RGBA8 fallback
  5. Patch build.bin: replace the build name "wilson" → "garfield"
  6. Pack into garfield.zip

Run from repo root:
  python3 tools/build_garfield_anim.py
"""

import io, struct, subprocess, tempfile, zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import texture2ddecoder
from scipy import ndimage

DS_DATA = Path("/home/eric/snap/steam/common/.local/share/Steam/steamapps/common/dont_starve/data")
REPO = Path(__file__).parent.parent
OUT_ANIM = REPO / "anim"
OUT_ANIM.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# KTEX decode
# ---------------------------------------------------------------------------
def decode_ktex(data: bytes) -> tuple[Image.Image, int, int]:
    """Return (Image RGBA top-down, atlas_w, atlas_h)."""
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
    return img.transpose(Image.FLIP_TOP_BOTTOM), w, h  # convert to top-down

# ---------------------------------------------------------------------------
# KTEX encode  (DXT5 via ImageMagick, RGBA8 fallback)
# ---------------------------------------------------------------------------
def encode_ktex(img: Image.Image) -> bytes:
    """Encode a top-down PIL RGBA image as KTEX."""
    img = img.convert('RGBA')
    w, h = img.size

    # Flip back to bottom-up (OpenGL convention) before encoding
    img_bu = img.transpose(Image.FLIP_TOP_BOTTOM)

    mips = _try_dxt5(img_bu)
    if mips:
        pixfmt = 2
        print(f"    DXT5 {w}×{h}  {len(mips)} mips")
    else:
        # RGBA8 single-mip fallback
        print(f"    RGBA8 {w}×{h} 1 mip")
        pixfmt = 4
        raw = img_bu.tobytes()
        mips = [(w, h, w * 4, raw)]

    hdr = (pixfmt << 4) | (1 << 9) | (len(mips) << 13) | (3 << 18) | (0xFFF << 20)
    out = b'KTEX' + struct.pack('<I', hdr)
    for mw, mh, pitch, data in mips:
        out += struct.pack('<HHHi', mw, mh, pitch, len(data))
    for _, _, _, data in mips:
        out += data
    return out


def _try_dxt5(img_bu: Image.Image):
    """Try ImageMagick DXT5 encode. Returns mip list or None."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as src:
        img_bu.save(src.name)
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix='.dds', delete=False) as dst:
        dst_path = dst.name
    try:
        r = subprocess.run(
            ['convert', src_path,
             '-define', 'dds:compression=dxt5',
             '-define', 'dds:mipmaps=1000',
             dst_path],
            capture_output=True, timeout=30)
        if r.returncode != 0:
            return None
        dds = Path(dst_path).read_bytes()
        if dds[:4] != b'DDS ':
            return None
        num_mips = max(struct.unpack('<I', dds[28:32])[0], 1)
        offset = 128
        mips = []
        mw, mh = img_bu.size
        for _ in range(num_mips):
            if mw < 1 or mh < 1:
                break
            bw, bh = max(1, mw // 4), max(1, mh // 4)
            size = bw * bh * 16
            data = dds[offset:offset + size]
            if len(data) < size:
                break
            mips.append((mw, mh, bw * 16, data))
            offset += size
            mw, mh = max(1, mw // 2), max(1, mh // 2)
        return mips or None
    except Exception:
        return None
    finally:
        Path(src_path).unlink(missing_ok=True)
        Path(dst_path).unlink(missing_ok=True)

# ---------------------------------------------------------------------------
# Build name patcher
# ---------------------------------------------------------------------------
def patch_build_name(build_bin: bytes, old_name: str, new_name: str) -> bytes:
    new_enc = new_name.encode()
    name_len = struct.unpack('<I', build_bin[16:20])[0]
    stored = build_bin[20:20+name_len].rstrip(b'\x00').decode()
    assert stored == old_name, f"Expected build name '{old_name}', got '{stored}'"
    return (build_bin[:16]
            + struct.pack('<I', len(new_enc))
            + new_enc
            + build_bin[20 + name_len:])

# ---------------------------------------------------------------------------
# Cat ear drawing
# ---------------------------------------------------------------------------
def draw_cat_ears(width: int, height: int, aspect: float) -> Image.Image:
    """
    Return an RGBA image (width×height) with cat ears at the top.

    The entire image is transparent except for the ear shapes. This is
    composited into the atlas ON TOP of the existing pixels so that the
    skull/face layers underneath still show through.

    aspect: sprite width / sprite height
      < 0.9 → tall/narrow → treat as front-facing but compressed
      0.9-1.3 → roughly square → front-facing (two ears)
      > 1.3 → wide → side view (one ear)

    Pixels are white so that AnimState:SetMultColour makes them orange.
    """
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Ear proportions (relative to sprite size)
    ear_h = int(height * 0.42)          # ear height (tip to base)
    ear_h = max(ear_h, 40)

    is_side = aspect > 1.25

    if is_side:
        # One ear, placed toward the near side (left third of sprite)
        ear_w = int(width * 0.22)
        ear_w = max(ear_w, 30)
        cx = int(width * 0.28)

        _draw_ear(draw, cx, 0, ear_w, ear_h)
    else:
        # Two symmetric ears
        ear_w = int(width * 0.21)
        ear_w = max(ear_w, 30)
        cx1 = int(width * 0.24)
        cx2 = int(width * 0.76)

        _draw_ear(draw, cx1, 0, ear_w, ear_h)
        _draw_ear(draw, cx2, 0, ear_w, ear_h)

    # Slight blur to soften aliased polygon edges
    img = img.filter(ImageFilter.GaussianBlur(radius=1.0))
    return img


def _draw_ear(draw, cx: int, top: int, ear_w: int, ear_h: int):
    """Draw one pointed ear centered at cx, tip at top, base at top+ear_h."""
    half = ear_w // 2

    # Outer ear (main body) — white, will be orange with tint
    outer = [
        (cx,          top),                     # tip
        (cx - half,   top + ear_h),             # base left
        (cx + half,   top + ear_h),             # base right
    ]
    draw.polygon(outer, fill=(245, 245, 245, 255))

    # Dark outline strokes around the ear
    draw.line([(cx, top), (cx - half, top + ear_h)], fill=(30, 20, 8, 255), width=2)
    draw.line([(cx, top), (cx + half, top + ear_h)], fill=(30, 20, 8, 255), width=2)
    draw.line([(cx - half, top + ear_h), (cx + half, top + ear_h)],
              fill=(30, 20, 8, 255), width=2)

    # Inner ear detail — slightly darker/cooler so it stands out after orange tint
    margin_x = max(ear_w // 6, 3)
    margin_y = max(ear_h // 7, 4)
    inner_h  = int(ear_h * 0.62)
    inner = [
        (cx,                  top + margin_y),
        (cx - half + margin_x, top + inner_h),
        (cx + half - margin_x, top + inner_h),
    ]
    draw.polygon(inner, fill=(200, 180, 180, 230))

# ---------------------------------------------------------------------------
# Garfield face drawing — AI-generated source image
# ---------------------------------------------------------------------------

# Path to the AI-generated expression overlay (eyes + mouth, white background)
_FACE_SRC_FRONT = Path("/tmp/garfield_expression_ai.png")
_FACE_SRC_SIDE  = Path("/tmp/garfield_face_side_ai.png")

def _load_face_source(path: Path) -> Image.Image:
    """Load an AI-generated face image and remove the white background."""
    img = Image.open(path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    # White-background removal: pixels with R,G,B all > 230 become transparent
    r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
    white_mask = (r > 230) & (g > 230) & (b > 230)
    arr[white_mask, 3] = 0
    # Soften the edges around the cutout
    result = Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA')
    return result


def draw_garfield_face(width: int, height: int, is_side: bool = False) -> Image.Image:
    """
    Return an RGBA (width×height) Garfield face scaled to fit the sprite slot.
    Uses the AI-generated expression overlay; falls back to a simple PIL drawing
    if the source file is missing.
    """
    src_path = _FACE_SRC_SIDE if is_side else _FACE_SRC_FRONT
    if not src_path.exists():
        src_path = _FACE_SRC_FRONT if is_side else _FACE_SRC_SIDE
    if not src_path.exists():
        # Minimal fallback: two dark dots for eyes
        img  = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = max(width // 8, 3)
        draw.ellipse([width//3-r, height//3-r, width//3+r, height//3+r],
                     fill=(20,15,8,255))
        draw.ellipse([2*width//3-r, height//3-r, 2*width//3+r, height//3+r],
                     fill=(20,15,8,255))
        return img

    src = _load_face_source(src_path)

    # Scale to fill the sprite slot, keeping the face centred
    # Use only the central 80% of the source (the actual face, not white margin)
    sw, sh = src.size
    cx_s, cy_s = sw // 2, sh // 2
    margin = int(min(sw, sh) * 0.1)
    src_cropped = src.crop((margin, margin, sw - margin, sh - margin))

    # Fit into target with a bit of padding
    pad_x = max(int(width  * 0.05), 2)
    pad_y = max(int(height * 0.05), 2)
    tw = width  - 2 * pad_x
    th = height - 2 * pad_y
    sc = min(tw / src_cropped.width, th / src_cropped.height)
    nw = max(1, int(src_cropped.width  * sc))
    nh = max(1, int(src_cropped.height * sc))
    resized = src_cropped.resize((nw, nh), Image.LANCZOS)

    out = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    ox = (width  - nw) // 2
    oy = (height - nh) // 2
    out.paste(resized, (ox, oy), resized)
    return out


# ---------------------------------------------------------------------------
# Find hair sprite bounding boxes (large, dark sprites)
# ---------------------------------------------------------------------------
def find_hair_regions(arr: np.ndarray):
    """
    Return list of (row, col, w, h) for hair sprite bounding boxes.

    Wilson's hair sprites are the 8 largest mostly-opaque, mostly-dark
    blobs in the atlas.  We detect them by:
      1. Finding connected opaque regions
      2. Keeping only those with area > 10,000 px and avg brightness < 80
    """
    alpha = arr[:,:,3]
    mask = alpha > 20
    labeled, ns = ndimage.label(mask)
    slices = ndimage.find_objects(labeled)

    candidates = []
    for i, sl in enumerate(slices):
        if sl is None:
            continue
        rsl, csl = sl
        sprite_h = rsl.stop - rsl.start
        sprite_w = csl.stop - csl.start
        if sprite_h < 80 or sprite_w < 80:
            continue
        sprite_mask = labeled[rsl, csl] == (i + 1)
        sprite_px   = arr[rsl, csl]
        opaque      = sprite_mask & (sprite_px[:,:,3] > 50)
        if opaque.sum() < 5000:
            continue
        avg_brightness = sprite_px[:,:,:3][opaque].mean()
        if avg_brightness < 80:
            candidates.append((rsl.start, csl.start, sprite_w, sprite_h, avg_brightness))

    # Return the 8 darkest-largest blobs (hair + hair_hat)
    candidates.sort(key=lambda x: x[4])   # sort by brightness ascending
    return [(r, c, w, h) for r, c, w, h, _ in candidates[:8]]


def find_face_regions(arr: np.ndarray):
    """
    Return list of (row, col, w, h) for Wilson's face-expression sprite bounding boxes.

    The face expression sprites live in the TOP-RIGHT section of the atlas
    (rows 6–220, cols > 900).  They are medium-to-large sprites showing
    Wilson's head/face overlays (60–200 px wide, 60–200 px tall).

    Excluded:
      - The dark hair sprites in the top-left (cols < 900 or avg brightness < 30)
      - Ghost/very-bright sprites (brightness > 215) — those are ghost hair
    """
    alpha = arr[:,:,3]
    mask  = alpha > 20
    labeled, ns = ndimage.label(mask)
    slices = ndimage.find_objects(labeled)

    candidates = []
    for i, sl in enumerate(slices):
        if sl is None:
            continue
        rsl, csl = sl
        r0, r1 = rsl.start, rsl.stop
        c0, c1 = csl.start, csl.stop
        h = r1 - r0
        w = c1 - c0

        # Face sprites are in the top-right area of the atlas
        if r0 < 5 or r0 > 220:
            continue
        if c0 < 900:           # left side is hair sprites
            continue

        # Size: large-ish, roughly square-ish (face-shaped)
        if w < 60 or w > 220 or h < 60 or h > 220:
            continue
        aspect = w / h
        if aspect > 2.0 or aspect < 0.5:
            continue

        sprite_mask = labeled[rsl, csl] == (i + 1)
        sprite_px   = arr[rsl, csl]
        opaque      = sprite_mask & (sprite_px[:,:,3] > 50)
        if opaque.sum() < 1000:
            continue

        avg_brightness = float(sprite_px[:,:,:3][opaque].mean())
        # Exclude pure-ghost sprites (near-white)
        if avg_brightness > 215 or avg_brightness < 25:
            continue

        candidates.append((r0, c0, w, h))

    return candidates

# ---------------------------------------------------------------------------
# Expression mark erasure — used for skull sprites that have Wilson's marks baked in
# ---------------------------------------------------------------------------
def _erase_expression_marks(sprite_arr: np.ndarray) -> np.ndarray:
    """
    Remove Wilson's dark expression marks (eyes, brows, stubble) from a skull sprite,
    replacing them with the sprite's own skin/background color.

    Strategy: inside the central face area (avoiding the head outline edges),
    any opaque pixel darker than 140 avg brightness is considered an expression mark
    and is repainted with the mean color of the surrounding bright opaque pixels.
    """
    h, w = sprite_arr.shape[:2]
    result = sprite_arr.copy().astype(np.float32)

    # Inner face area — skip ~20% margins to avoid the head outline
    mx = int(w * 0.20)
    my = int(h * 0.18)
    face = result[my:h - my, mx:w - mx]

    opaque    = face[:, :, 3] > 50
    brightness = face[:, :, :3].mean(axis=2)

    # Skin color = average of bright opaque pixels in the face area
    bright_mask = opaque & (brightness > 150)
    if bright_mask.any():
        skin = face[:, :, :3][bright_mask].mean(axis=0)
    else:
        skin = np.array([220.0, 220.0, 220.0])

    # Paint over dark marks with skin color
    dark_mask = opaque & (brightness < 140)
    face[dark_mask, :3] = skin
    face[dark_mask, 3]   = 255.0

    result[my:h - my, mx:w - mx] = face
    return result.clip(0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Build garfield.zip
# ---------------------------------------------------------------------------
def make_garfield_build():
    wilson_zip = DS_DATA / "anim" / "wilson.zip"
    out_zip    = OUT_ANIM / "garfield.zip"

    print(f"\nBuilding {out_zip.name} from {wilson_zip.name}…")
    with zipfile.ZipFile(wilson_zip) as z:
        tex_data   = z.read('atlas-0.tex')
        build_data = z.read('build.bin')

    # 1. Decode atlas (top-down)
    atlas, AW, AH = decode_ktex(tex_data)
    arr = np.array(atlas)
    print(f"  Atlas: {AW}×{AH}")

    # 2. Find hair sprite regions
    hair_regions = find_hair_regions(arr)
    print(f"  Hair regions found: {len(hair_regions)}")
    for r, c, w, h in hair_regions:
        print(f"    ({r},{c}) {w}×{h}")

    # 3. For each hair region, composite cat ears
    for r, c, w, h in hair_regions:
        aspect = w / h
        ears = draw_cat_ears(w, h, aspect)

        region = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        region.paste(ears, (0, 0), ears)
        arr[r:r+h, c:c+w] = np.array(region)

    # 3b. Replace Wilson's face expression sprites with Garfield's.
    # Wilson's atlas has two kinds of face sprites:
    #   - Head outline (rows ~6-7):  just the outer head shape/silhouette — DON'T TOUCH
    #   - Expression overlays (rows 170+): skull+expression baked in — REPLACE ENTIRELY
    # Replacing the expression sprites with Garfield's expression (transparent bg +
    # heavy-lidded eyes/mouth) lets the head outline layer show through underneath.
    face_regions = find_face_regions(arr)
    print(f"  Face regions found: {len(face_regions)}")
    replaced = 0
    for r, c, w, h in face_regions:
        if r <= 100:
            # Head outline sprite — leave it untouched
            continue
        is_side = (w / h) > 1.2
        face = draw_garfield_face(w, h, is_side=is_side)
        arr[r:r+h, c:c+w] = np.array(face)
        replaced += 1
    print(f"  Expression sprites replaced: {replaced}")

    # 4. Re-encode atlas
    print("  Encoding atlas…")
    new_atlas = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    new_tex   = encode_ktex(new_atlas)

    # 5. Patch build name
    new_build = patch_build_name(build_data, 'wilson', 'garfield')

    # 6. Write zip
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('atlas-0.tex', new_tex)
        z.writestr('build.bin',   new_build)

    print(f"  Written: {out_zip}  ({out_zip.stat().st_size:,} bytes)")

# ---------------------------------------------------------------------------
# Ghost build
# ---------------------------------------------------------------------------
def find_ghost_build():
    for p in [
        DS_DATA / "anim" / "ghost_build.zip",
        DS_DATA / "anim" / "ghost_wendy_build.zip",
    ]:
        if p.exists():
            return p
    return None


def make_ghost_build():
    ghost_zip = find_ghost_build()
    if not ghost_zip:
        print("\nWARN: ghost build not found — skipping")
        return

    out_zip = OUT_ANIM / "ghost_garfield_build.zip"
    print(f"\nBuilding {out_zip.name} from {ghost_zip.name}…")

    with zipfile.ZipFile(ghost_zip) as z:
        tex_data   = z.read('atlas-0.tex')
        build_data = z.read('build.bin')
        anim_data  = z.read('anim.bin') if 'anim.bin' in z.namelist() else None

    name_len    = struct.unpack('<I', build_data[16:20])[0]
    old_name    = build_data[20:20+name_len].rstrip(b'\x00').decode()
    new_build   = patch_build_name(build_data, old_name, 'ghost_garfield_build')

    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('atlas-0.tex', tex_data)
        z.writestr('build.bin',   new_build)
        if anim_data:
            z.writestr('anim.bin', anim_data)

    print(f"  Written: {out_zip}  ({out_zip.stat().st_size:,} bytes)")

# ---------------------------------------------------------------------------
# Lasagna build (patch carrot.zip)
# ---------------------------------------------------------------------------
def make_lasagna_build():
    """Build lasagna.zip by patching carrot.zip — only the build name changes."""
    out_path   = OUT_ANIM / "lasagna.zip"
    carrot_zip = DS_DATA / "anim" / "carrot.zip"
    print(f"\nBuilding {out_path.name} from carrot.zip…")

    with zipfile.ZipFile(carrot_zip) as z:
        tex_data   = z.read('atlas-0.tex')
        build_data = z.read('build.bin')
        anim_data  = z.read('anim.bin')

    new_build = patch_build_name(build_data, 'carrot', 'lasagna')

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('anim.bin',    anim_data)
        z.writestr('atlas-0.tex', tex_data)
        z.writestr('build.bin',   new_build)

    print(f"  Written: {out_path}  ({out_path.stat().st_size:,} bytes)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    make_garfield_build()
    make_ghost_build()
    make_lasagna_build()
    print("\nDone. Animation bundles written to anim/")
