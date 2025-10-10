from pathlib import Path
from os import getenv
from base64 import b64decode
from PIL import Image, ImageDraw, ImageFont

"""
Image generation service.

This module implements a dual-mode generator: it attempts to create images via OpenAI's API,
but gracefully falls back to a local placeholder image if the API key is missing or any error occurs.

Behaviour:
- If OPENAI_API_KEY is set, attempt to generate a hero image via OpenAI Images (gpt-image-1).
- On any failure (no key/network/API error), fall back to a local placeholder hero.
- Output path is always written so downstream composer can proceed deterministically.
"""

def _placeholder(hero_text: str, out_path: Path):
    """
    Generates a simple placeholder image with the given hero text.

    This function is used as a fallback when the OpenAI image generation is not available.
    It creates a basic image with a frame and text to ensure the pipeline can continue without interruption.
    """
    # Ensure the output directory exists to avoid file write errors
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a blank RGB image with a light grey background as a neutral placeholder
    im = Image.new("RGB", (1600, 1200), (245, 245, 245))
    d = ImageDraw.Draw(im)

    # Draw a simple rectangular frame near the bottom of the image to visually separate the text area
    d.rectangle((100, 900, 1500, 1100), outline=(0, 0, 0), width=6)

    try:
        # Attempt to load a common TrueType font for better text rendering quality
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except Exception:
        # If the TrueType font is unavailable (e.g., environment lacks font files),
        # fall back to the default PIL bitmap font to ensure text is still rendered
        font = ImageFont.load_default()

    # Draw the hero text inside the frame with a dark grey colour for readability
    d.text((140, 930), hero_text, fill=(20, 20, 20), font=font)

    # Save the generated placeholder image to the specified output path
    im.save(out_path)

    # Return the output path for downstream usage
    return out_path

def generate_hero(product_name: str, audience: str, market: str, out_path: Path):
    """
    Attempts to generate a hero image using OpenAI Images (gpt-image-1) model.

    The function first checks for the presence of the OPENAI_API_KEY environment variable.
    If the key is not configured, it immediately falls back to generating a local placeholder image.

    When the key is present, it constructs a detailed prompt designed to instruct the model to produce
    a studio-quality product hero image tailored for the specified audience and market. The prompt emphasises
    natural lighting, a clean background, and brand-safe content without text or logos to ensure suitability.

    The OpenAI client is lazily imported to avoid hard dependencies when the API is not used.

    In case of any exceptions during the API call or image processing (e.g., network issues, API errors),
    the function falls back to the local placeholder to maintain pipeline robustness.

    Args:
        product_name (str): Name of the product to feature in the hero image.
        audience (str): Target audience descriptor.
        market (str): Market context for the image.
        out_path (Path): Filesystem path where the generated image should be saved.

    Returns:
        Path: The path to the generated (or placeholder) image.
    """
    # Retrieve the OpenAI API key from environment variables to determine if online generation is possible
    api_key = getenv("OPENAI_API_KEY")

    if not api_key:
        # API key is not configured; use the offline placeholder image to ensure deterministic output
        return _placeholder(product_name, out_path)

    # Construct a prompt that guides the AI to generate a high-quality, brand-safe hero image
    prompt = (
        f"Studio-quality product hero image of '{product_name}' targeted to {audience} "
        f"in market {market}. Natural lighting, clean background, subtle lifestyle context. "
        "Brand-safe, family-friendly, high contrast focal point, minimal clutter. "
        "No text, no watermarks, no logos."
    )

    try:
        # Import the OpenAI client library here to avoid requiring it unless actually used
        from openai import OpenAI

        # Initialise the OpenAI client with the provided API key
        client = OpenAI(api_key=api_key)

        # Send a request to generate an image with the specified model, prompt, and size
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
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

    except Exception:
        # Catch all exceptions (network errors, API failures, decoding issues) and fall back gracefully
        # This ensures the pipeline remains robust and deterministic by providing a placeholder image
        return _placeholder(product_name, out_path)
