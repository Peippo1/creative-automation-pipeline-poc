# api/app.py
# FastAPI gateway for the creative pipeline with basic API key auth and per-IP rate limiting.

import base64
import io
import os
import time
import logging
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Dict

# Load env (e.g., OPENAI_API_KEY, API_TOKEN) and set up logging
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("api")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

# Local services
from src.services import generator, composer, checks

# -----------------------------
# Config
# -----------------------------
API_TOKEN = os.getenv("API_TOKEN", "dev-token")
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))

# simple in-memory IP -> timestamps window
_rate_window: Dict[str, List[float]] = {}

# -----------------------------
# App
# -----------------------------
app = FastAPI(title="Creative Pipeline API", version="1.0.0")

# CORS for local UI/dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Models
# -----------------------------
class GenerateRequest(BaseModel):
    prompt: Optional[str] = Field(None, description="Image generation prompt")
    message: str = Field(..., description="Brand message to render")
    locales: List[str] = Field(..., description="Locales to render, e.g. ['en-GB']")
    ratios: List[str] = Field(..., description="Aspect ratios, e.g. ['1:1','9:16','16:9']")
    brand_colour: str = Field("#0A84FF", description="Hex colour for brand bar")
    size: str = Field("1024x1024", description="Image generation size")
    logo_base64: Optional[str] = Field(None, description="PNG logo as base64 (optional)")


class OutputItem(BaseModel):
    locale: str
    ratio: str
    path: str
    preview_b64: Optional[str] = None
    logo_ok: bool
    legal_ok: bool


class GenerateResponse(BaseModel):
    session_id: str
    outputs_root: str
    outputs: List[OutputItem]
    download_route: str


# -----------------------------
# Helpers
# -----------------------------
def _auth(request: Request):
    token = request.headers.get("X-API-Key")
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _rate_window.get(ip, [])
    # prune old timestamps
    window = [t for t in window if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(window) >= RATE_LIMIT_MAX_REQUESTS:
        seconds = int(RATE_LIMIT_WINDOW_SECONDS - (now - window[0]))
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Try again in ~{max(seconds,1)}s.")
    window.append(now)
    _rate_window[ip] = window


# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(payload: GenerateRequest, request: Request):
    _auth(request)
    _rate_limit(request)

    allowed_ratios = {"1:1", "9:16", "16:9"}
    if not set(payload.ratios).issubset(allowed_ratios):
        raise HTTPException(status_code=400, detail="Unsupported ratios requested.")

    session_id = f"API_SESSION_{int(time.time())}"
    outputs_root = Path("outputs") / session_id / "AD"
    outputs_root.mkdir(parents=True, exist_ok=True)

    # Optional logo
    logo_path: Optional[Path] = None
    if payload.logo_base64:
        try:
            raw = base64.b64decode(payload.logo_base64)
            logo_path = Path("assets") / "logos" / f"api_logo_{session_id}.png"
            logo_path.parent.mkdir(parents=True, exist_ok=True)
            with open(logo_path, "wb") as f:
                f.write(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 logo data.")

    # Generate hero
    hero_path = Path("assets") / "sessions" / session_id / "hero.png"
    hero_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        generator.generate_hero(
            product_name="API Product",
            audience="API Audience",
            market="API Market",
            out_path=hero_path,
            prompt=(payload.prompt or None),
            size=payload.size,
        )
    except Exception as e:
        logger.exception("generate_hero failed")
        raise HTTPException(status_code=500, detail=f"generate_hero failed: {e}")

    # Compose & build previews
    items: List[OutputItem] = []
    for loc in payload.locales:
        for ratio in payload.ratios:
            out_path = outputs_root / ratio.replace(":", "x") / f"ad_{loc}_001.jpg"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                composed = composer.compose_variant(
                    hero_path,
                    logo_path if logo_path else Path("assets/brand/logo.png"),
                    payload.message,
                    payload.brand_colour,
                    ratio,
                    out_path,
                )
                logo_ok = checks.logo_present(logo_path if logo_path else Path("assets/brand/logo.png"))
                legal_ok = checks.legal_check(payload.message)
            except Exception as e:
                logger.exception("compose_variant failed")
                raise HTTPException(status_code=500, detail=f"compose_variant failed: {e}")

            try:
                with open(composed, "rb") as f:
                    b = f.read()
                preview_b64 = "data:image/jpeg;base64," + base64.b64encode(b).decode("utf-8")
            except Exception:
                preview_b64 = None

            items.append(
                OutputItem(
                    locale=loc,
                    ratio=ratio,
                    path=str(composed),
                    preview_b64=preview_b64,
                    logo_ok=logo_ok,
                    legal_ok=legal_ok,
                )
            )

    return GenerateResponse(
        session_id=session_id,
        outputs_root=str(outputs_root),
        outputs=items,
        download_route=f"/download/{session_id}",
    )


@app.get("/download/{session_id}")
def download_zip(session_id: str, request: Request):
    _auth(request)
    _rate_limit(request)

    root = Path("outputs") / session_id / "AD"
    if not root.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    import zipfile
    import tempfile

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file():
                z.write(p, arcname=str(p.relative_to(root)))

    def iterfile():
        with open(tmp.name, "rb") as f:
            yield from f
        os.remove(tmp.name)

    return StreamingResponse(iterfile(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{session_id}.zip"'
    })