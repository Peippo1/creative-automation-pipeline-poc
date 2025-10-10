

from __future__ import annotations
from pathlib import Path
import json

"""
Lightweight localisation helper for the POC.

Behaviour:
- Attempts to load a per-locale message from `assets/localisation/messages_<locale>.json`.
- If no file or key is found, returns the original English message.
- This keeps the POC offline and deterministic while demonstrating the localisation step.
"""

LOCALISATION_DIR = Path("assets") / "localisation"

def get_localised_message(base_message: str, target_locale: str, source_locale: str = "en-GB") -> str:
    """
    Return a message for the given target locale.

    Looks for a JSON file named `messages_<target_locale>.json` in assets/localisation/
    with a key "message". Example file content:
    {
      "message": "Machen Sie Ihr Zuhause in diesem Frühling grüner!"
    }

    If not present, fall back to the base English message.
    """
    # Already in the source locale? Use the base message.
    if target_locale == source_locale:
        return base_message

    file = LOCALISATION_DIR / f"messages_{target_locale}.json"
    if not file.exists():
        return base_message

    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        override = data.get("message")
        return override if override else base_message
    except Exception:
        # On any parsing/read error, fail safe and return the base message.
        return base_message