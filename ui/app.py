import base64
import requests
# ui/app.py
# Simple UI to drive the existing creative pipeline.
# Adds basic guardrails (rate limit, prompt checks) and a download bundle.

import io
import os
import time
import zipfile
import random
from pathlib import Path
from typing import List

import streamlit as st
from PIL import Image  # noqa: F401  # (kept for possible future inline editing)
from dotenv import load_dotenv

# Ensure repo root is on sys.path so `src.*` imports work when running from /ui
import sys
from pathlib import Path as _PathAlias
sys.path.insert(0, str(_PathAlias(__file__).resolve().parents[1]))
from src.services import generator, composer, checks

# ---------------------------
# Config & Safety Guardrails
# ---------------------------
load_dotenv()

ALLOWED_RATIOS = ["1:1", "9:16", "16:9"]
ALLOWED_SIZES = ["1024x1024", "1792x1024", "1024x1792"]
BLOCKED_PROMPT_TERMS: List[str] = [
    # very lightweight content safety list (extendable)
    "graphic violence",
    "gore",
    "explicit adult",
    "porn",
    "hate symbol",
    "illegal",
    "self-harm",
]
MAX_PROMPT_CHARS = 500
MAX_VARIANTS_PER_CLICK = 6          # locales × ratios cap
MIN_SECONDS_BETWEEN_RUNS = 10        # simple rate limit per session

OPENAI_KEY_PRESENT = bool(os.getenv("OPENAI_API_KEY"))

USE_API_GATEWAY = True  # set False to run services in-process
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
API_TOKEN = os.getenv("API_TOKEN", "dev-token")

# init session state for rate-limiting
if "last_run_ts" not in st.session_state:
    st.session_state.last_run_ts = 0.0

st.set_page_config(page_title="Ad Generator", layout="wide")
st.title("Generative Ad Creator (POC)")

# Quick examples to pre-fill the prompt
st.subheader("Examples")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Eco kitchen bottle"):
        st.session_state.prompt = (
            "eco friendly cleaning bottle on wooden kitchen counter with soft daylight"
        )
with col2:
    if st.button("Gym water bottle"):
        st.session_state.prompt = (
            "stainless steel sports bottle on gym floor with dramatic lighting"
        )
with col3:
    if st.button("Desk coffee mug"):
        st.session_state.prompt = (
            "ceramic coffee mug on designer desk near laptop, product shot"
        )

# Random preset button using the full pool of examples
PRESET_POOL = [
    "eco friendly cleaning bottle on wooden kitchen counter with soft daylight",
    "stainless steel sports bottle on gym floor with dramatic lighting",
    "ceramic coffee mug on designer desk near laptop, product shot",
    "sunscreen bottle on sandy beach towel with bright summer light and sea in background",
    "premium shampoo bottle on marble bathroom shelf with soft steam and backlight",
    "healthy snack bar on minimalist work desk beside notebook and coffee cup",
]

st.divider()
if st.button("Random preset"):
    st.session_state.prompt = random.choice(PRESET_POOL)
    st.experimental_rerun()

# Additional product preset examples
col4, col5, col6 = st.columns(3)
with col4:
    if st.button("Sunscreen beach shot"):
        st.session_state.prompt = (
            "sunscreen bottle on sandy beach towel with bright summer light and sea in background"
        )
with col5:
    if st.button("Shampoo bathroom shelf"):
        st.session_state.prompt = (
            "premium shampoo bottle on marble bathroom shelf with soft steam and backlight"
        )
with col6:
    if st.button("Snack bar on desk"):
        st.session_state.prompt = (
            "healthy snack bar on minimalist work desk beside notebook and coffee cup"
        )

st.sidebar.subheader("Safety & Usage Notes")
st.sidebar.markdown(
    "- Prompts are lightly checked for unsafe content.\n"
    "- Runs are rate limited to prevent abuse.\n"
    "- Image generation falls back to a placeholder if the model/API is unavailable.\n"
    "- For production, replace the image backend with Adobe Firefly and add server-side rate limits/auth."
)

with st.form("inputs"):
    prompt = st.text_area(
        "Main Image Prompt",
        value=st.session_state.get("prompt", ""),
        placeholder="Eco-friendly cleaner on a kitchen counter, spring light, minimal style",
        help=f"Up to {MAX_PROMPT_CHARS} characters. Avoid unsafe content.",
        max_chars=MAX_PROMPT_CHARS,
    )
    message = st.text_input("Brand Message", "Make your home greener this spring!")
    locales = st.multiselect("Locales", ["en-GB", "de-DE", "fr-FR"], default=["en-GB"])
    ratios = st.multiselect("Aspect Ratios", ALLOWED_RATIOS, default=ALLOWED_RATIOS)
    brand_colour = st.color_picker("Brand Colour", "#0A84FF")
    logo_file = st.file_uploader("Brand Logo (PNG)", type=["png"])
    size = st.selectbox("Generation Size", ALLOWED_SIZES, index=0)
    submitted = st.form_submit_button("Generate")

# ---------------------------
# Validation helpers
# ---------------------------
def prompt_is_safe(text: str) -> bool:
    t = (text or "").lower()
    return not any(term in t for term in BLOCKED_PROMPT_TERMS)

def check_variant_limits(selected_locales: List[str], selected_ratios: List[str]) -> bool:
    return len(selected_locales) * len(selected_ratios) <= MAX_VARIANTS_PER_CLICK

def rate_limited() -> bool:
    return (time.time() - st.session_state.last_run_ts) < MIN_SECONDS_BETWEEN_RUNS

# ---------------------------
# Main submit handler
# ---------------------------
if submitted:
    # Basic validations
    if not prompt_is_safe(prompt or ""):
        st.error("The prompt appears to contain unsafe content. Please revise and try again.")
        st.stop()

    if not locales:
        st.error("Please select at least one locale.")
        st.stop()

    if not ratios:
        st.error("Please select at least one aspect ratio.")
        st.stop()

    if not set(ratios).issubset(set(ALLOWED_RATIOS)):
        st.error("One or more selected aspect ratios are not allowed.")
        st.stop()

    if not check_variant_limits(locales, ratios):
        st.error(f"Too many variants requested in one go. Please keep to ≤ {MAX_VARIANTS_PER_CLICK} (locales × ratios).")
        st.stop()

    if rate_limited():
        wait = int(MIN_SECONDS_BETWEEN_RUNS - (time.time() - st.session_state.last_run_ts))
        st.warning(f"Please wait {max(wait, 1)} seconds before running again.")
        st.stop()

    # Warn if key missing (we will still attempt placeholder path)
    if not OPENAI_KEY_PRESENT:
        st.info("No OPENAI_API_KEY detected. Will use a local placeholder image instead of a generated one.")

    st.session_state.last_run_ts = time.time()

    if not USE_API_GATEWAY:
        # derive session and output paths
        session_id = f"UI_SESSION_{int(time.time())}"
        outputs_root = Path("outputs") / session_id / "AD"
        outputs = []

        # persist logo if provided
        logo_path = None
        if logo_file:
            logo_path = Path("assets") / "logos"
            logo_path.mkdir(parents=True, exist_ok=True)
            logo_path = logo_path / f"ui_logo_{session_id}.png"
            with open(logo_path, "wb") as f:
                f.write(logo_file.read())

        # Generate a main hero image (prompt-driven if provided)
        hero_path = Path("assets") / "sessions" / session_id / "hero.png"
        hero_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            generator.generate_hero(
                product_name="UI Product",
                audience="UI Audience",
                market="UI Market",
                out_path=hero_path,
                prompt=(prompt or None),
                size=size,
            )
        except Exception as e:
            st.error(f"Image generation failed: {e}")
            st.stop()

        # Compose across locales × ratios
        errors = 0
        for loc in locales:
            for ratio in ratios:
                try:
                    out_path = outputs_root / ratio.replace(":", "x") / f"ad_{loc}_001.jpg"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    composed = composer.compose_variant(
                        hero_path,
                        logo_path if logo_path else Path("assets/brand/logo.png"),
                        message,
                        brand_colour,
                        ratio,
                        out_path,
                    )
                    ok_logo = checks.logo_present(logo_path if logo_path else Path("assets/brand/logo.png"))
                    ok_terms = checks.legal_check(message)
                    outputs.append((loc, ratio, composed, ok_logo, ok_terms))
                except Exception as e:
                    errors += 1
                    st.warning(f"Failed to compose {loc} / {ratio}: {e}")

        st.success(f"Generated {len(outputs)} variants under {outputs_root} (errors: {errors})")
        cols = st.columns(3)
        for idx, (loc, ratio, path, ok_logo, ok_terms) in enumerate(outputs):
            with cols[idx % 3]:
                st.caption(f"{loc} • {ratio} • logo:{'✓' if ok_logo else '×'} legal:{'✓' if ok_terms else '×'}")
                st.image(str(path))

        # Bundle as ZIP for download
        if outputs:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for _, _, p, _, _ in outputs:
                    z.write(p, arcname=str(Path(p).relative_to(outputs_root)))
            st.download_button(
                "Download all as ZIP",
                data=buf.getvalue(),
                file_name=f"{session_id}.zip",
                mime="application/zip",
            )
    else:
        # new: call FastAPI gateway
        # Prepare payload
        logo_b64 = None
        if logo_file:
            logo_b64 = base64.b64encode(logo_file.getvalue()).decode("utf-8")

        payload = {
            "prompt": (prompt or None),
            "message": message,
            "locales": locales,
            "ratios": ratios,
            "brand_colour": brand_colour,
            "size": size,
            "logo_base64": logo_b64,
        }

        try:
            resp = requests.post(
                f"{API_URL}/generate",
                json=payload,
                headers={"X-API-Key": API_TOKEN, "Content-Type": "application/json"},
                timeout=120,
            )
            if resp.status_code != 200:
                st.error(f"API error {resp.status_code}: {resp.text}")
                st.stop()
            data = resp.json()
        except Exception as e:
            st.error(f"Failed to call API: {e}")
            st.stop()

        outputs = []
        for item in data.get("outputs", []):
            outputs.append((item["locale"], item["ratio"], item["path"], item["logo_ok"], item["legal_ok"], item.get("preview_b64")))

        st.success(f'Generated {len(outputs)} variants under {data.get("outputs_root")}')

        cols = st.columns(3)
        for idx, (loc, ratio, path, ok_logo, ok_terms, preview_b64) in enumerate(outputs):
            with cols[idx % 3]:
                st.caption(f"{loc} • {ratio} • logo:{'✓' if ok_logo else '×'} legal:{'✓' if ok_terms else '×'}")
                if preview_b64:
                    st.image(preview_b64)
                else:
                    st.text(path)

        # Download button via API
        try:
            zip_resp = requests.get(
                f'{API_URL}{data.get("download_route")}',
                headers={"X-API-Key": API_TOKEN},
                timeout=120,
            )
            if zip_resp.status_code == 200:
                st.download_button(
                    "Download all as ZIP",
                    data=zip_resp.content,
                    file_name=f'{data.get("session_id")}.zip',
                    mime="application/zip",
                )
            else:
                st.warning("ZIP not available.")
        except Exception as e:
            st.warning(f"Could not fetch ZIP: {e}")