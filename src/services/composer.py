from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import logging

log = logging.getLogger("composer")


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a sane font with fallback to default if TTF not available."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _parse_hex_colour(hex_str: str, default=(10, 132, 255)) -> tuple[int, int, int]:
    try:
        s = hex_str.strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) == 3:  # '#0AF' style
            s = "".join(c * 2 for c in s)
        if len(s) != 6:
            return default
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (r, g, b)
    except Exception:
        return default


def compose_variant(
    hero_path: Path,
    out_path: Path,
    message: str,
    brand_colour: str,
    locale: str,
    ratio: str = "1:1",
):
    """
    Compose a social ad variant:
      - background panel + divider
      - hero image (scaled to fit)
      - message text (bottom left)
      - logo (bottom right)
    Saves as JPEG (RGB).
    """
    ratio_map = {
        "1:1":  (1080, 1080),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
    }
    W, H = ratio_map.get(ratio, (1080, 1080))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Canvas is RGB to be safe for JPEG
    # W, H = 1080, 1080  # overridden upstream per ratio; safe square default
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Read hero (convert to RGB so we never carry alpha into JPEG writes)
    try:
        hero = Image.open(hero_path).convert("RGB")
    except Exception as e:
        log.warning("Failed to open hero %s: %s. Using solid fill.", hero_path, e)
        hero = Image.new("RGB", (W, int(H * 0.6)), (230, 230, 230))

    # Fit hero into upper area with margins
    margin = 48
    hero_box = (margin, margin, W - margin, int(H * 0.62))
    box_w = hero_box[2] - hero_box[0]
    box_h = hero_box[3] - hero_box[1]
    hero.thumbnail((box_w, box_h))
    hx = hero_box[0] + (box_w - hero.width) // 2
    hy = hero_box[1] + (box_h - hero.height) // 2
    canvas.paste(hero, (hx, hy))

    # Accent panel
    accent = _parse_hex_colour(brand_colour)
    panel_h = 180
    panel_y = H - panel_h
    draw.rectangle([0, panel_y, W, H], fill=accent)

    # Divider
    draw.line([(0, panel_y), (W, panel_y)], fill=(0, 0, 0), width=4)

    # Text
    font = _load_font(36)
    msg = message or ""
    # Simple left padding, baseline near panel top + a bit
    tx, ty = 28, panel_y + 24
    # Outline for contrast on bright colours
    def draw_text_with_outline(x, y, txt, fill=(255, 255, 255)):
        for ox, oy in ((-1,0),(1,0),(0,-1),(0,1)):
            draw.text((x+ox, y+oy), txt, font=font, fill=(0,0,0))
        draw.text((x, y), txt, font=font, fill=fill)

    draw_text_with_outline(tx, ty, msg)

    # Logo (bottom-right). Use default if not provided upstream.
    logo_path = Path("assets/brand/logo.png")
    try:
        if logo_path.exists():
            logo = Image.open(logo_path).convert("RGBA")
            # Size relative to panel height
            target = int(panel_h * 0.6)
            logo.thumbnail((target, target))
            lx = W - logo.width - 28
            ly = panel_y + (panel_h - logo.height) // 2
            # Use alpha channel as mask
            canvas.paste(logo, (lx, ly), mask=logo.split()[-1])
        else:
            log.info("No logo at %s. Skipping logo paste.", logo_path)
    except Exception as e:
        log.warning("Logo paste failed: %s", e)

    # Ensure RGB and save as JPEG
    canvas = canvas.convert("RGB")
    try:
        canvas.save(out_path, "JPEG", quality=92, optimize=True, progressive=True)
    except Exception as e:
        log.warning("JPEG save failed for %s: %s. Trying PNG then.", out_path, e)
        # Worst case, write PNG with .jpg extension (not ideal, but no 500)
        canvas.save(out_path.with_suffix(".png"), "PNG")

    return out_path