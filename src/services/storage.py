from pathlib import Path
from typing import Optional

ASSETS_DIR = Path("assets")
PRODUCTS_DIR = ASSETS_DIR / "products"
GENERATED_DIR = Path("generated")
OUTPUTS_DIR = Path("outputs")
MANIFESTS_DIR = Path("manifests")

def product_hero_path(sku: str) -> Path:
    return PRODUCTS_DIR / sku / "hero.png"

def ensure_dirs():
    for p in [ASSETS_DIR, PRODUCTS_DIR, GENERATED_DIR, OUTPUTS_DIR, MANIFESTS_DIR]:
        p.mkdir(parents=True, exist_ok=True)

def find_or_none(p: Path) -> Optional[Path]:
    return p if p.exists() else None
