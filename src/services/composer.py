from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple


ASPECT_SIZES = {
    "1:1": (1080,1080),
    "9:16": (1080,1920),
    "16:9": (1920,1080)
}

def _center_fit(im: Image.Image, size: Tuple[int,int]) -> Image.Image:
    # cover-fit crop, then resize
    src_w, src_h = im.size
    dst_w, dst_h = size
    src_ar = src_w/src_h; dst_ar = dst_w/dst_h
    if src_ar > dst_ar:  # too wide -> crop sides
        new_w = int(src_h*dst_ar); x0 = (src_w - new_w)//2
        im = im.crop((x0,0,x0+new_w,src_h))
    else:                # too tall -> crop top/bottom
        new_h = int(src_w/dst_ar); y0 = (src_h - new_h)//2
        im = im.crop((0,y0,src_w,y0+new_h))
    return im.resize(size, Image.LANCZOS)

def _measure_total_h(lines: list[str], draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, line_gap: int) -> int:
    """
    Measure total text block height for wrapped lines using current font and line gap.
    """
    if not lines:
        return 0
    heights = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=0)
        heights.append(bbox[3] - bbox[1])
    return sum(heights) + (len(lines) - 1) * line_gap

def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_px: int) -> list[str]:
    """
    Naive word-wrapping to ensure each line fits within max_px.
    Uses draw.textbbox to measure text width with the given font.
    """
    words = text.split()
    if not words:
        return [""]
    lines = []
    line = words[0]
    for w in words[1:]:
        trial = f"{line} {w}"
        bbox = draw.textbbox((0, 0), trial, font=font, stroke_width=2)
        if (bbox[2] - bbox[0]) <= max_px:
            line = trial
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines

def compose_variant(hero: Path, logo: Path, message: str, colour_hex: str, ratio: str, out_path: Path):
    base = Image.open(hero).convert("RGBA")
    size = ASPECT_SIZES[ratio]
    canvas = _center_fit(base, size).convert("RGBA")

    W, H = size

    # ---- Overlay setup
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ---- Brand bar (bottom)
    # Parse hex colour and compute dimensions
    c = tuple(int(colour_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    bar_h = int(H * 0.18)  # slightly taller for better readability
    bar_y0 = H - bar_h
    draw.rectangle((0, bar_y0, W, H), fill=(*c, 230))

    # subtle top separator line to define the bar edge
    draw.line((0, bar_y0, W, bar_y0), fill=(0, 0, 0, 160), width=3)

    # ---- Prepare logo (reserve space on the right so text can be centered cleanly)
    reserved_right = 0
    lg_img = None
    if Path(logo).exists():
        lg_img = Image.open(logo).convert("RGBA")
        target_w = int(min(size) * 0.18)
        scale = target_w / lg_img.size[0]
        lg_img = lg_img.resize((target_w, int(lg_img.size[1] * scale)), Image.LANCZOS)
        margin = int(min(size) * 0.03)
        reserved_right = lg_img.size[0] + margin * 2
        # Add left/right text padding on top of reserved logo space
        pad_x = int(W * 0.05)
        if reserved_right:
            reserved_right += pad_x
        # Paste logo later after text so we can center text within the remaining area

    # ---- Message text
    # Font sizing based on bar height (ensures visibility across ratios)
    font_size = max(32, int(bar_h * 0.38))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Stroke width scales with font size for consistent contrast
    stroke = max(2, int(font_size * 0.06))
    line_gap = int(font_size * 0.25)

    # Compute available width for text (accounting for padding and reserved logo area)
    available_w = max(10, W - pad_x - reserved_right - pad_x)

    # Wrap message to fit within available width
    lines = _wrap_to_width(draw, message, font, available_w)

    # If the wrapped block is too tall for the bar, iteratively shrink the font to fit
    total_text_h = _measure_total_h(lines, draw, font, line_gap)
    while total_text_h > int(bar_h * 0.9) and font_size > 24:
        font_size = int(font_size * 0.92)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        stroke = max(2, int(font_size * 0.06))
        line_gap = int(font_size * 0.25)
        lines = _wrap_to_width(draw, message, font, available_w)
        total_text_h = _measure_total_h(lines, draw, font, line_gap)

    # Dynamic text/stroke colours for contrast against the bar colour
    r, g, b = c
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    text_fill = (0, 0, 0, 255) if luminance > 160 else (255, 255, 255, 255)
    stroke_fill = (0, 0, 0, 170) if text_fill == (255, 255, 255, 255) else (255, 255, 255, 170)

    # Recompute line heights and total text height using possibly updated font and line_gap
    line_heights = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font, stroke_width=0)
        line_heights.append(bbox[3] - bbox[1])
    total_text_h = sum(line_heights) + (len(lines) - 1) * line_gap

    # Start positions – center vertically; horizontally center within the bar area (excluding reserved logo region)
    text_x0 = pad_x
    text_y0 = bar_y0 + (bar_h - total_text_h) // 2

    # To center horizontally within available_w, we compute each line width and offset
    current_y = text_y0
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=0)
        line_w = bbox[2] - bbox[0]
        # center each line within available_w
        x = text_x0 + max(0, (available_w - line_w) // 2)
        # Draw with stroke for contrast
        draw.text(
            (x, current_y),
            line,
            font=font,
            fill=text_fill,
            stroke_width=stroke,
            stroke_fill=stroke_fill,
        )
        current_y += line_heights[idx] + line_gap

    # ---- Paste logo in the reserved area (bottom-right)
    if lg_img is not None:
        margin = int(min(size) * 0.03)
        pos = (W - lg_img.size[0] - margin, H - lg_img.size[1] - margin)
        overlay.alpha_composite(lg_img, dest=pos)

    # ---- Composite & save
    canvas.alpha_composite(overlay)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, quality=92)
    return out_path
