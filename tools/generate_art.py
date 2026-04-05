#!/usr/bin/env python3
"""
Generate Garfield portrait art for the Don't Starve mod.

Produces PNG files in the correct sizes for each image slot.
These PNGs then need to be converted to .tex/.xml pairs with ktools:
    ktech <file>.png <file>.tex

Outputs (relative to repo root):
    images/bigportraits/garfield.png          170 x 220
    images/saveslot_portraits/garfield.png     62 x  62
    images/selectscreen_portraits/garfield.png 260 x 226
    modicon.png                                 64 x  64
"""

import os
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Colour palette — classic Garfield
# ---------------------------------------------------------------------------
ORANGE       = (239, 131,  34)   # main body fur
DARK_ORANGE  = (200,  90,  10)   # stripes / shading
LIGHT_ORANGE = (252, 183, 100)   # highlight / belly edge
CREAM        = (255, 235, 195)   # muzzle, belly, inner ear
DARK_CREAM   = (230, 200, 155)   # cream shadow
EYE_GREEN    = ( 90, 170,  60)   # iris
EYE_DARK     = ( 30, 100,  20)   # pupil / iris ring
EYE_WHITE    = (240, 245, 230)   # sclera
NOSE         = (230,  90,  90)   # pinkish nose
MOUTH_LINE   = ( 80,  40,  20)   # outlines around mouth
OUTLINE      = ( 40,  20,   5)   # main black outline
WHITE        = (255, 255, 255)
TRANSPARENT  = (0, 0, 0, 0)

def outline_color(alpha=255):
    r, g, b = OUTLINE
    return (r, g, b, alpha)

# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------
def ellipse(draw, cx, cy, rx, ry, fill, outline=None, width=1):
    draw.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        fill=fill, outline=outline, width=width
    )

def filled_ellipse(img_arr, cx, cy, rx, ry, color):
    """Draw a filled ellipse directly onto a PIL Image (RGBA)."""
    draw = ImageDraw.Draw(img_arr)
    ellipse(draw, cx, cy, rx, ry, fill=color)

# ---------------------------------------------------------------------------
# Core Garfield face/body drawing functions
# ---------------------------------------------------------------------------

def draw_garfield_face(draw, cx, cy, scale=1.0, show_body=False):
    """
    Draw Garfield centred at (cx, cy) at the given scale.
    scale=1.0 produces a face roughly 120 px wide.
    """
    s = scale

    # ---- Body (if requested) ----
    if show_body:
        # Fat belly
        body_w, body_h = int(90*s), int(70*s)
        draw.ellipse([cx - body_w, cy + int(60*s),
                      cx + body_w, cy + int(60*s) + body_h*2],
                     fill=ORANGE, outline=OUTLINE, width=max(1, int(2*s)))
        # Cream belly patch
        draw.ellipse([cx - int(55*s), cy + int(65*s),
                      cx + int(55*s), cy + int(60*s) + int(body_h*1.7)],
                     fill=CREAM)
        # Stripes on body
        for i, sx in enumerate([-int(35*s), 0, int(35*s)]):
            draw.line([cx + sx, cy + int(62*s), cx + sx, cy + int(100*s)],
                      fill=DARK_ORANGE, width=max(1, int(4*s)))

    # ---- Head ----
    head_rx, head_ry = int(62*s), int(55*s)
    # Head shadow
    ellipse(draw, cx + int(3*s), cy + int(3*s), head_rx, head_ry,
            fill=(180, 80, 10, 120) if hasattr(draw, '_image') else DARK_ORANGE)
    # Main head
    ellipse(draw, cx, cy, head_rx, head_ry, fill=ORANGE, outline=OUTLINE, width=max(1, int(2*s)))

    # ---- Ears ----
    ear_pts_l = [
        (cx - int(45*s), cy - int(35*s)),
        (cx - int(62*s), cy - int(65*s)),
        (cx - int(22*s), cy - int(50*s)),
    ]
    ear_pts_r = [
        (cx + int(45*s), cy - int(35*s)),
        (cx + int(62*s), cy - int(65*s)),
        (cx + int(22*s), cy - int(50*s)),
    ]
    draw.polygon(ear_pts_l, fill=ORANGE, outline=OUTLINE)
    draw.polygon(ear_pts_r, fill=ORANGE, outline=OUTLINE)
    # Inner ear
    inner_l = [
        (cx - int(45*s), cy - int(37*s)),
        (cx - int(57*s), cy - int(58*s)),
        (cx - int(28*s), cy - int(48*s)),
    ]
    inner_r = [
        (cx + int(45*s), cy - int(37*s)),
        (cx + int(57*s), cy - int(58*s)),
        (cx + int(28*s), cy - int(48*s)),
    ]
    draw.polygon(inner_l, fill=CREAM)
    draw.polygon(inner_r, fill=CREAM)

    # ---- Stripes on head ----
    for dx in [-int(28*s), 0, int(28*s)]:
        draw.line([cx + dx, cy - int(55*s), cx + dx + int(5*s), cy - int(28*s)],
                  fill=DARK_ORANGE, width=max(1, int(4*s)))

    # ---- Muzzle ----
    muzzle_rx, muzzle_ry = int(32*s), int(24*s)
    ellipse(draw, cx, cy + int(18*s), muzzle_rx, muzzle_ry, fill=CREAM)

    # ---- Eyes — Garfield's signature half-lidded bored look ----
    for sign, ex in [(-1, cx - int(24*s)), (1, cx + int(24*s))]:
        ey = cy - int(10*s)
        eye_rx, eye_ry = int(15*s), int(12*s)
        # Sclera
        ellipse(draw, ex, ey, eye_rx, eye_ry, fill=EYE_WHITE, outline=OUTLINE, width=max(1,int(1*s)))
        # Iris
        ellipse(draw, ex, ey + int(2*s), int(9*s), int(8*s), fill=EYE_GREEN)
        # Pupil (slightly elliptical, cat-like)
        ellipse(draw, ex, ey + int(2*s), int(4*s), int(7*s), fill=EYE_DARK)
        # Half-lid — this is Garfield's most iconic feature
        lid_top = ey - eye_ry
        lid_bottom = ey - int(2*s)   # covers top half of eye
        draw.rectangle([ex - eye_rx, lid_top, ex + eye_rx, lid_bottom],
                       fill=ORANGE)
        # Lid outline / lash line
        draw.line([ex - eye_rx, lid_bottom, ex + eye_rx, lid_bottom],
                  fill=OUTLINE, width=max(1, int(2*s)))
        draw.arc([ex - eye_rx, lid_top, ex + eye_rx, lid_bottom + int(4*s)],
                 start=200, end=340, fill=OUTLINE, width=max(1, int(2*s)))

    # ---- Nose ----
    nose_pts = [
        (cx,              cy + int(8*s)),
        (cx - int(7*s),   cy + int(14*s)),
        (cx + int(7*s),   cy + int(14*s)),
    ]
    draw.polygon(nose_pts, fill=NOSE, outline=OUTLINE)

    # ---- Mouth — smug Garfield smirk ----
    # Philtrum
    draw.line([cx, cy + int(14*s), cx, cy + int(20*s)], fill=MOUTH_LINE, width=max(1, int(2*s)))
    # Left side of mouth goes slightly down
    draw.arc([cx - int(24*s), cy + int(14*s), cx, cy + int(32*s)],
             start=0, end=90, fill=MOUTH_LINE, width=max(1, int(2*s)))
    # Right side curls up into a smirk
    draw.arc([cx, cy + int(10*s), cx + int(24*s), cy + int(28*s)],
             start=90, end=180, fill=MOUTH_LINE, width=max(1, int(2*s)))

    # ---- Whiskers ----
    whisker_y = cy + int(22*s)
    for i, (x1, x2) in enumerate([
        (cx - int(65*s), cx - int(30*s)),
        (cx + int(30*s), cx + int(65*s)),
    ]):
        dy_offsets = [-int(8*s), 0, int(8*s)]
        for dy in dy_offsets:
            draw.line([x1, whisker_y + dy, x2, whisker_y + dy],
                      fill=OUTLINE, width=max(1, int(1*s)))


# ---------------------------------------------------------------------------
# Generate: Big Portrait  170 x 220
# ---------------------------------------------------------------------------
def gen_bigportrait(path):
    W, H = 170, 220
    img = Image.new("RGBA", (W, H), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # Dark background gradient suggestion — DS portraits have a dark BG
    for y in range(H):
        t = y / H
        r = int(18 + 12 * t)
        g = int(12 + 8  * t)
        b = int(8  + 5  * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # Body stub at bottom
    cx, cy = W // 2, 128
    scale = 0.88

    # Body
    bw, bh = int(75*scale), int(55*scale)
    draw.ellipse([cx - bw, cy + int(55*scale),
                  cx + bw, cy + int(55*scale) + bh*2],
                 fill=ORANGE, outline=OUTLINE, width=2)
    draw.ellipse([cx - int(48*scale), cy + int(60*scale),
                  cx + int(48*scale), cy + int(55*scale) + int(bh*1.65)],
                 fill=CREAM)
    for sx in [-int(28*scale), 0, int(28*scale)]:
        draw.line([cx + sx, cy + int(57*scale), cx + sx, cy + int(88*scale)],
                  fill=DARK_ORANGE, width=3)

    draw_garfield_face(draw, cx, cy, scale=scale)

    # Vignette border
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for i in range(20):
        alpha = int(180 * (i / 20) ** 2)
        vdraw.rectangle([i, i, W-i, H-i], outline=(0, 0, 0, alpha), width=1)
    img = Image.alpha_composite(img, vignette)

    img.save(path)
    print(f"  Saved {path}  ({W}x{H})")


# ---------------------------------------------------------------------------
# Generate: Save Slot Portrait  62 x 62
# ---------------------------------------------------------------------------
def gen_saveslot(path):
    W, H = 62, 62
    img = Image.new("RGBA", (W, H), (20, 14, 10, 255))
    draw = ImageDraw.Draw(img)

    cx, cy = W // 2, H // 2 + 4
    scale = 0.32

    draw_garfield_face(draw, cx, cy, scale=scale)

    img.save(path)
    print(f"  Saved {path}  ({W}x{H})")


# ---------------------------------------------------------------------------
# Generate: Select Screen Portrait  260 x 226
# ---------------------------------------------------------------------------
def gen_selectscreen(path):
    W, H = 260, 226
    img = Image.new("RGBA", (W, H), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # Slightly lighter background for the select screen
    for y in range(H):
        t = y / H
        r = int(28 + 10 * t)
        g = int(18 + 8  * t)
        b = int(10 + 5  * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    cx, cy = W // 2, H // 2 + 10
    scale = 1.3

    # Full body
    bw, bh = int(90*scale), int(70*scale)
    draw.ellipse([cx - bw, cy + int(58*scale),
                  cx + bw, cy + int(58*scale) + bh*2],
                 fill=ORANGE, outline=OUTLINE, width=2)
    draw.ellipse([cx - int(58*scale), cy + int(63*scale),
                  cx + int(58*scale), cy + int(58*scale) + int(bh*1.7)],
                 fill=CREAM)
    for sx in [-int(35*scale), 0, int(35*scale)]:
        draw.line([cx + sx, cy + int(60*scale), cx + sx, cy + int(100*scale)],
                  fill=DARK_ORANGE, width=max(1, int(4*scale)))

    # Arms
    for sign in [-1, 1]:
        arm_cx = cx + sign * int(80*scale)
        arm_cy = cy + int(75*scale)
        draw.ellipse([arm_cx - int(18*scale), arm_cy - int(30*scale),
                      arm_cx + int(18*scale), arm_cy + int(30*scale)],
                     fill=ORANGE, outline=OUTLINE, width=2)
        # Paw
        draw.ellipse([arm_cx - int(14*scale), arm_cy + int(20*scale),
                      arm_cx + int(14*scale), arm_cy + int(40*scale)],
                     fill=CREAM, outline=OUTLINE, width=1)

    # Legs / feet
    for sign in [-1, 1]:
        leg_cx = cx + sign * int(45*scale)
        leg_cy = cy + int(58*scale) + bh*2 - int(10*scale)
        draw.ellipse([leg_cx - int(20*scale), leg_cy,
                      leg_cx + int(28*scale), leg_cy + int(30*scale)],
                     fill=ORANGE, outline=OUTLINE, width=2)
        draw.ellipse([leg_cx - int(16*scale), leg_cy + int(20*scale),
                      leg_cx + int(24*scale), leg_cy + int(36*scale)],
                     fill=CREAM, outline=OUTLINE, width=1)

    # Tail
    draw.arc([cx + int(70*scale), cy + int(90*scale),
              cx + int(130*scale), cy + int(160*scale)],
             start=200, end=360, fill=ORANGE, width=max(1, int(8*scale)))
    draw.arc([cx + int(74*scale), cy + int(94*scale),
              cx + int(126*scale), cy + int(156*scale)],
             start=200, end=360, fill=DARK_ORANGE, width=max(1, int(3*scale)))

    draw_garfield_face(draw, cx, cy, scale=scale)

    img.save(path)
    print(f"  Saved {path}  ({W}x{H})")


# ---------------------------------------------------------------------------
# Generate: Mod Icon  64 x 64
# ---------------------------------------------------------------------------
def gen_modicon(path):
    W, H = 64, 64
    img = Image.new("RGBA", (W, H), (22, 14, 8, 255))
    draw = ImageDraw.Draw(img)

    cx, cy = W // 2, H // 2 + 4
    scale = 0.34

    draw_garfield_face(draw, cx, cy, scale=scale)

    # Rounded corner border
    for i in range(3):
        draw.rounded_rectangle([i, i, W-i-1, H-i-1],
                                radius=8, outline=(80, 40, 10, 200 - i*60), width=1)

    img.save(path)
    print(f"  Saved {path}  ({W}x{H})")


# ---------------------------------------------------------------------------
# Generate: Name plate  ~180 x 30
# (White text "Garfield" on transparent; DS composites this over the UI)
# ---------------------------------------------------------------------------
def gen_nameplate(path):
    W, H = 180, 30
    img = Image.new("RGBA", (W, H), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # Simple bold text approximation via thick stroked letters is tricky
    # without a bundled font. We draw block letters manually for "GARFIELD".
    # DS actually renders the character name from the STRINGS table for most
    # purposes; this atlas is the stylised select-screen nameplate.

    # Orange banner
    draw.rounded_rectangle([0, 4, W-1, H-4], radius=6, fill=(180, 70, 5, 230))
    draw.rounded_rectangle([2, 6, W-3, H-6], radius=4, outline=(255, 200, 80, 200), width=1)

    # Text — use default font at size 14 (may vary by system)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except Exception:
        font = None

    text = "GARFIELD"
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    else:
        tw, th = len(text) * 8, 11

    tx = (W - tw) // 2
    ty = (H - th) // 2

    # Shadow
    draw.text((tx+1, ty+1), text, fill=(80, 30, 5, 200), font=font)
    # Main text
    draw.text((tx, ty), text, fill=(255, 235, 160, 255), font=font)

    img.save(path)
    print(f"  Saved {path}  ({W}x{H})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
ROOT = os.path.join(os.path.dirname(__file__), "..")

def out(subpath):
    p = os.path.join(ROOT, subpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p

if __name__ == "__main__":
    print("Generating Garfield portrait art …")
    gen_bigportrait(   out("images/bigportraits/garfield.png"))
    gen_saveslot(      out("images/saveslot_portraits/garfield.png"))
    gen_selectscreen(  out("images/selectscreen_portraits/garfield.png"))
    gen_modicon(       out("modicon.png"))
    gen_nameplate(     out("images/names_garfield.png"))
    print("Done.")
    print()
    print("Next step — convert PNGs to .tex/.xml with ktools:")
    print("  for f in images/**/*.png modicon.png; do ktech $f ${f%.png}.tex; done")
