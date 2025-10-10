from pathlib import Path
from typing import Dict, List

PROHIBITED = {"free","guaranteed","best price"}

def legal_check(message: str) -> str:
    m = message.lower()
    flagged = [w for w in PROHIBITED if w in m]
    return "pass" if not flagged else f"warn:{','.join(flagged)}"

def logo_present(logo_path: Path) -> str:
    return "pass" if logo_path.exists() else "warn:missing_logo"
