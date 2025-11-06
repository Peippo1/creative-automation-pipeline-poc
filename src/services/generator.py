from pathlib import Path
from os import getenv
from base64 import b64decode
from PIL import Image, ImageDraw, ImageFont
from typing import Optional

import logging

logger = logging.getLogger("generator")
MAX_PROMPT = 500  # defensive cap for prompts echoed to model/placeholder

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Simple word-wrap: returns a list of lines that fit within max_width for the given font.
    """
    words = text.split()
    if not words:
        return []
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        wpx = draw.textbbox((0, 0), test, font=font)[2]
        if wpx <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines

def _placeholder(hero_text: str, out_path: Path, bg=(235, 240, 255), fg=(20, 40, 80)):
    """
    Generates a simple placeholder image with text, with basic word-wrapping.
    """
    # Ensure the output directory exists to avoid file write errors
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a blank RGB image
    width, height = 1600, 1200
    im = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(im)

    try:
        font_title = ImageFont.truetype("DejaVuSans.ttf", 48)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 30)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Title
    title = "Placeholder Hero"
    t_w, t_h = d.textbbox((0, 0), title, font=font_title)[2:]
    d.text(((width - t_w) // 2, height // 3 - t_h), title, fill=fg, font=font_title)

    # Body (wrapped)
    max_text_width = width - 280  # side margins
    for i, line in enumerate(_wrap_text(d, hero_text, font_body, max_text_width)[:4]):
        w, h = d.textbbox((0, 0), line, font=font_body)[2:]
        y = height // 3 + 20 + i * (h + 8)
        d.text(((width - w) // 2, y), line, fill=fg, font=font_body)

    # Save explicitly as PNG
    im.save(out_path, "PNG")
    logger.info("Wrote placeholder hero to %s", out_path)
    return out_path

def generate_hero(
    product_name: str,
    audience: str,
    market: str,
    out_path: Path,
    prompt: Optional[str] = None,
    size: str = "1024x1024",
) -> Path:
    """
    Attempts to generate a hero image using OpenAI Images (gpt-image-1) model.

    Behaviour:
    - If OPENAI_API_KEY is not present, fall back to a local placeholder.
    - If `prompt` is provided, it will be used verbatim for image generation.
    - If `prompt` is not provided, a brand-safe template prompt is constructed from
      `product_name`, `audience`, and `market`.
    - The `size` parameter (default "1024x1024") is forwarded to the image API.

    Args:
        product_name (str): Name of the product to feature in the hero image.
        audience (str): Target audience descriptor.
        market (str): Market context for the image.
        out_path (Path): Filesystem path where the generated image should be saved.
        prompt (Optional[str]): Optional explicit prompt supplied by a UI or caller.
        size (str): Target size for generation (e.g., "1024x1024", "1792x1024").

    Returns:
        Path: The path to the generated (or placeholder) image.
    """
    # Cap any incoming prompt we might echo to model/placeholder
    if prompt:
      prompt = prompt[:MAX_PROMPT]

    # Retrieve the OpenAI API key from environment variables to determine if online generation is possible
    api_key = getenv("OPENAI_API_KEY")

    if not api_key:
        logger.info("OPENAI_API_KEY not set; using placeholder.")
        safe_text = (prompt or product_name or "Product")
        return _placeholder(safe_text, out_path)

    final_prompt = (
        prompt.strip() if prompt else
        f"Studio-quality product hero image of '{product_name}' targeted to {audience} "
        f"in market {market}. Natural lighting, clean background, subtle lifestyle context. "
        "Brand-safe, family-friendly, high contrast focal point, minimal clutter. "
        "No text, no watermarks, no logos."
    )[:MAX_PROMPT]

    try:
        # Import the OpenAI client library here to avoid requiring it unless actually used
        from openai import OpenAI

        # Initialise the OpenAI client with the provided API key
        client = OpenAI(api_key=api_key)

        # Send a request to generate an image with the specified model, prompt, and size
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=final_prompt,
            size=size
        )

        # Extract the base64-encoded image data from the response
        b64 = resp.data[0].b64_json

        # Decode the base64 string into binary image bytes
        img_bytes = b64decode(b64)

        # Ensure the output directory exists before writing the image file
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the image bytes to the specified output file path
        with open(out_path, "wb") as f:
            f.write(img_bytes)

        # Return the path to the successfully generated image
        return out_path

    except Exception as e:
        # Fall back gracefully and log why
        logger.warning("Model generation failed; using placeholder. Error: %s", e)
        placeholder_text = (prompt or product_name or "Product")
        return _placeholder(placeholder_text[:MAX_PROMPT], out_path)
