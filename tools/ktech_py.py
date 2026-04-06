#!/usr/bin/env python3
"""
Pure-Python ktech replacement.

Converts PNG images → DS .tex + .xml pairs.
- Pads images to power-of-two dimensions (required by DS/OpenGL)
- Encodes textures as DXT5 (BC3) via ImageMagick for GPU efficiency
- Falls back to RGBA8 if ImageMagick DXT5 encoding fails

Usage:
    python3 tools/ktech_py.py <image.png> [<image2.png> ...]

Outputs <stem>.tex and <stem>.xml alongside each input PNG.
"""

import struct, sys, subprocess, tempfile
from pathlib import Path
from PIL import Image


def next_pow2(n):
    p = 1
    while p < n:
        p <<= 1
    return p


def pad_to_pow2(img: Image.Image) -> Image.Image:
    w, h = img.size
    pw, ph = next_pow2(w), next_pow2(h)
    if pw == w and ph == h:
        return img
    padded = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    padded.paste(img.convert('RGBA'), (0, 0))
    return padded


# ---------------------------------------------------------------------------
# DXT5 encode via ImageMagick → parse DDS → extract raw BC3 data
# ---------------------------------------------------------------------------
def encode_dxt5_via_imagemagick(img: Image.Image):
    """
    Use ImageMagick to encode a PIL Image as DXT5 with a full mip chain.
    Returns list of (w, h, pitch, data) tuples, one per mip, or None on failure.
    """
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as src:
        img.save(src.name)
        src_path = src.name
    with tempfile.NamedTemporaryFile(suffix='.dds', delete=False) as dst:
        dst_path = dst.name

    try:
        result = subprocess.run(
            ['convert', src_path,
             '-define', 'dds:compression=dxt5',
             '-define', 'dds:mipmaps=1000',  # full mip chain
             dst_path],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            return None

        dds = Path(dst_path).read_bytes()
        assert dds[:4] == b'DDS ', "Not a DDS file"

        # Parse DDS header
        num_mips = struct.unpack('<I', dds[28:32])[0]
        num_mips = max(num_mips, 1)

        # Raw data starts at byte 128
        offset = 128
        mips = []
        mw, mh = img.size
        for _ in range(num_mips):
            if mw < 1 or mh < 1:
                break
            # DXT5: 16 bytes per 4×4 block; minimum block size 1×1 block
            bw = max(1, mw // 4)
            bh = max(1, mh // 4)
            size = bw * bh * 16
            pitch = bw * 16
            data = dds[offset:offset + size]
            if len(data) < size:
                break
            mips.append((mw, mh, pitch, data))
            offset += size
            mw = max(1, mw // 2)
            mh = max(1, mh // 2)

        return mips if mips else None
    except Exception as e:
        print(f"    ImageMagick error: {e}")
        return None
    finally:
        Path(src_path).unlink(missing_ok=True)
        Path(dst_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# KTEX encode
# ---------------------------------------------------------------------------
def encode_ktex(img: Image.Image) -> bytes:
    """Encode a PIL Image as KTEX with a full DXT5 mip chain."""
    img = pad_to_pow2(img.convert('RGBA'))
    w, h = img.size

    mips = encode_dxt5_via_imagemagick(img)

    if mips:
        pixfmt = 2  # DXT5
        num_mips = len(mips)
        print(f"    DXT5  {w}×{h}  {num_mips} mips")
    else:
        # Fallback: RGBA8, single mip
        print(f"    RGBA8 {w}×{h}  1 mip  [DXT5 unavailable]")
        pixfmt = 4
        num_mips = 1
        flipped = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        raw = flipped.tobytes()
        mips = [(w, h, w * 4, raw)]

    # Top 12 bits (the "fill" field) must be 0xFFF — the DS reader requires it.
    hdr_word = (0) | (pixfmt << 4) | (1 << 9) | (num_mips << 13) | (3 << 18) | (0xFFF << 20)

    out = b'KTEX'
    out += struct.pack('<I', hdr_word)
    for mw, mh, pitch, data in mips:
        out += struct.pack('<HHHi', mw, mh, pitch, len(data))
    for _, _, _, data in mips:
        out += data
    return out


# ---------------------------------------------------------------------------
# XML atlas
# ---------------------------------------------------------------------------
def make_atlas_xml(tex_filename: str, element_name: str) -> str:
    u1 = v1 = 0.001953125
    u2 = v2 = 0.998046875
    return (
        f'<Atlas>'
        f'<Texture filename="{tex_filename}" />'
        f'<Elements>'
        f'<Element name="{element_name}" u1="{u1}" u2="{u2}" v1="{v1}" v2="{v2}" />'
        f'</Elements>'
        f'</Atlas>'
    )


# ---------------------------------------------------------------------------
# Convert one PNG
# ---------------------------------------------------------------------------
def convert(png_path: Path):
    stem = png_path.stem
    out_dir = png_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(png_path)
    orig_size = img.size
    print(f"  {png_path.name}  ({orig_size[0]}×{orig_size[1]})")

    tex_bytes = encode_ktex(img)

    tex_name = stem + '.tex'
    xml_name = stem + '.xml'
    (out_dir / tex_name).write_bytes(tex_bytes)
    (out_dir / xml_name).write_text(make_atlas_xml(tex_name, tex_name))
    print(f"    → {out_dir / tex_name}  ({len(tex_bytes):,} bytes)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    for arg in args:
        convert(Path(arg))
