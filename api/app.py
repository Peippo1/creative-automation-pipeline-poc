from __future__ import annotations

import os
import io
import re
import uuid
import base64
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from zipfile import ZipFile, ZIP_DEFLATED

from dotenv import load_dotenv

# Local services
from src.services import generator, composer, checks

# ------------------------------------------------------------
# Env & logging
# ------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("api")

ENV = os.getenv("ENV", "dev")
API_TOKEN = os.getenv("API_TOKEN", "dev-token")

if ENV != "dev" and API_TOKEN == "dev-token":
    raise RuntimeError(
        "Unsafe API token configuration: API_TOKEN is 'dev-token' but ENV is not 'dev'. "
        "Set a strong API_TOKEN for non-local usage."
    )

SESSIONS_DIR = Path("assets/sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# Models
# ------------------------------------------------------------
class GenerateRequest(BaseModel):
    prompt: Optional[str] = None
    message: str
    locales: List[str]
    ratios: List[str]
    brand_colour: str = "#0A84FF"
    size: str = "1024x1024"
    logo_b64: Optional[str] = None  # optional inline logo

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message must not be empty")
        return v

class OutputItem(BaseModel):
    locale: str
    ratio: str
    path: str
    preview_b64: Optional[str]
    logo_ok: bool
    legal_ok: bool

class GenerateResponse(BaseModel):
    session_id: str
    outputs_root: str
    outputs: List[OutputItem]

# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(title="Creative Automation API", version="0.2.0")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")  # en-GB, de-DE
SESSION_ID_RE = re.compile(r"^API_SESSION_([0-9a-f]{10})$")
ALLOWED_RATIOS = {"1:1", "9:16", "16:9"}
RATIO_TO_FOLDER = {"1:1": "1x1", "9:16": "9x16", "16:9": "16x9"}
MAX_LOCALES = 5
MAX_RATIOS = 3
MAX_PROMPT_CHARS = 512
MAX_COMBINATIONS = 12  # locales × ratios

def safe_name(s: str, max_len: int = 64) -> str:
    token = re.sub(r"[^A-Za-z0-9\-_]", "_", s)
    return token[:max_len]

# ------------------------------------------------------------
# Routes
# ------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/generate", response_model=GenerateResponse)
def generate_endpoint(payload: GenerateRequest, x_api_key: str = Header(default="")):
    # Auth
    if not API_TOKEN or x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Validate inputs (defence-in-depth)
    if len(payload.locales) == 0 or len(payload.ratios) == 0:
        raise HTTPException(status_code=400, detail="locales and ratios are required")
    if len(payload.locales) > MAX_LOCALES:
        raise HTTPException(status_code=400, detail=f"Too many locales (max {MAX_LOCALES})")
    if len(payload.ratios) > MAX_RATIOS:
        raise HTTPException(status_code=400, detail=f"Too many ratios (max {MAX_RATIOS})")
    for loc in payload.locales:
        if not LOCALE_RE.match(loc):
            raise HTTPException(status_code=400, detail=f"Invalid locale format: {loc}")
    for r in payload.ratios:
        if r not in ALLOWED_RATIOS:
            raise HTTPException(status_code=400, detail=f"Unsupported ratio: {r}")

    # Prompt and combinations limits
    if payload.prompt and len(payload.prompt) > MAX_PROMPT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt too long (max {MAX_PROMPT_CHARS} characters).",
        )

    combos = len(payload.locales) * len(payload.ratios)
    if combos > MAX_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many variants requested ({combos}); max is {MAX_COMBINATIONS}.",
        )

    # Prepare session folder
    session_id = f"API_SESSION_{uuid.uuid4().hex[:10]}"
    outputs_root = SESSIONS_DIR / session_id / "AD"
    outputs_root.mkdir(parents=True, exist_ok=True)

    # Optional: decode logo
    logo_path: Optional[Path] = None
    if payload.logo_b64:
        try:
            raw = base64.b64decode(payload.logo_b64.split(",")[-1])
            logo_path = outputs_root / "uploaded_logo.png"
            with open(logo_path, "wb") as f:
                f.write(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid logo_b64")

    # Generate or reuse hero
    hero_path = outputs_root / "hero.png"
    try:
        generator.generate_hero(
            product_name="API Product",
            audience="API Audience",
            market="API Market",
            out_path=hero_path,
            prompt=(payload.prompt or None),
            size=payload.size,
        )
    except Exception:
        logger.exception("generate_hero failed")
        raise HTTPException(
            status_code=500,
            detail="Image generation failed.",
        )

    # Compose variants (Hardened against path-injection)
    items: List[OutputItem] = []
    resolved_root = outputs_root.resolve()

    for loc in payload.locales:
        for ratio in payload.ratios:
            # Map whitelisted ratios to fixed folder names
            ratio_folder = RATIO_TO_FOLDER[ratio]
            filename = f"ad_{uuid.uuid4().hex[:8]}.jpg"
            out_path = outputs_root / ratio_folder / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Ensure target path is within outputs_root (path semantics)
            try:
                resolved_target = out_path.resolve()
                # Raises ValueError if resolved_target is not under resolved_root
                resolved_target.relative_to(resolved_root)
            except ValueError:
                logger.warning("Rejected path outside outputs_root: %s", resolved_target)
                raise HTTPException(status_code=400, detail="Invalid output path requested")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid output path")

            # Compose and checks
            try:
                composer.compose_variant(
                    hero_path,
                    out_path,
                    payload.message,
                    payload.brand_colour,
                    loc,
                    ratio,
                )
                logo_ok = checks.logo_present(logo_path if logo_path else Path("assets/brand/logo.png"))
                legal_ok = checks.legal_check(payload.message)

                # Normalize compliance results to booleans (helpers may return "pass"/"fail")
                logo_ok_bool = (logo_ok is True) or (str(logo_ok).strip().lower() == "pass")
                legal_ok_bool = (legal_ok is True) or (str(legal_ok).strip().lower() == "pass")

            except Exception:
                logger.exception("compose_variant failed")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to compose the ad image.",
                )

            # Preview (best-effort): use the known-safe out_path
            try:
                comp_path = out_path
                with open(comp_path, "rb") as f:
                    b = f.read()
                ext = comp_path.suffix.lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                preview_b64 = f"data:{mime};base64," + base64.b64encode(b).decode("utf-8")
            except Exception:
                preview_b64 = None

            items.append(
                OutputItem(
                    locale=loc,
                    ratio=ratio,
                    path=str(out_path),
                    preview_b64=preview_b64,
                    logo_ok=logo_ok_bool,
                    legal_ok=legal_ok_bool,
                )
            )

    return GenerateResponse(
        session_id=session_id,
        outputs_root=str(outputs_root),
        outputs=items,
    )


@app.get("/download/{session_id}")
async def download(session_id: str, x_api_key: str = Header(default="")):
    if not API_TOKEN or x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Strictly validate session id format and prevent path traversal
    match = SESSION_ID_RE.fullmatch(session_id)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid session id")

    # Rebuild a canonical, safe session id from the captured hex only
    hex_part = match.group(1)
    safe_session_id = f"API_SESSION_{hex_part}"

    sessions_root = SESSIONS_DIR.resolve()
    # codeql[py/path-injection]: session_id is strictly validated by SESSION_ID_RE and constrained under SESSIONS_DIR
    root = (SESSIONS_DIR / safe_session_id).resolve()

    # Ensure root is inside sessions_root using path semantics
    try:
        root.relative_to(sessions_root)
    except ValueError:
        logger.warning("Rejected download path outside sessions root: %s", root)
        raise HTTPException(status_code=400, detail="Invalid session id")

    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="Session not found")

    # stream a ZIP
    mem = io.BytesIO()
    with ZipFile(mem, mode="w", compression=ZIP_DEFLATED) as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(root))
    mem.seek(0)
    return StreamingResponse(mem, media_type="application/zip", headers={
        "Content-Disposition": f"attachment; filename={session_id}.zip"
    })