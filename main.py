"""
Creative Automation Pipeline (POC)
----------------------------------
Single-command CLI:
  python main.py --brief briefs/sample.json

Flow:
  1) Load brief (JSON) and validate (Pydantic),
  2) Reuse existing hero or generate new (OpenAI -> placeholder),
  3) Compose 1:1, 9:16, 16:9 with message + logo,
  4) Run simple brand/legal checks,
  5) Write manifest and log paths.

Note: Using Typer's single-command mode (typer.run) to avoid subcommand parsing quirks.
"""

import json
from pathlib import Path
from typing import Dict
import typer
from dotenv import load_dotenv

from src.models.schemas import CampaignBrief
from src.services import storage, generator, composer, checks, localise
from src.utils.logging import get_logger

log = get_logger()

def main(
    brief: Path = typer.Option(..., "--brief", "-b", help="Path to the campaign brief JSON"),
    outdir: Path = typer.Option(Path("outputs"), "--outdir", help="Root folder for generated outputs"),
    force_regenerate: bool = typer.Option(False, "--force-regenerate", "-f", help="Ignore existing heroes and generate new ones"),
):
    """
    Execute a single pipeline run given a path to a campaign brief JSON.
    """
    # Load environment variables (e.g. OPENAI_API_KEY) from .env if present.
    load_dotenv()

    # Ensure deterministic local folder structure exists.
    storage.ensure_dirs()

    # Validate the brief early to fail fast if it is malformed.
    if not brief.exists():
        log.error(f"Brief not found: {brief}")
        raise typer.Exit(code=2)
    data = json.loads(brief.read_text())
    brief_obj = CampaignBrief(**data)
    log.info(f"Starting campaign {brief_obj.campaign_id}")
    languages = brief_obj.languages or ["en-GB"]
    log.info(f"Locales: {', '.join(languages)} | Outdir: {outdir} | Force regenerate: {force_regenerate}")

    # Manifest collects provenance and outputs for the whole run.
    manifest: Dict = {
        "campaign_id": brief_obj.campaign_id,
        "products": [],
        "metrics": {"generated": 0, "reused": 0, "errors": 0},
    }

    # Iterate all products declared in the brief.
    for p in brief_obj.products:
        # 1) Discover an existing hero (prefer reuse for brand consistency and cost).
        hero_path = storage.product_hero_path(p.sku)
        hero = storage.find_or_none(hero_path)
        if force_regenerate or hero is None:
            action = "regenerating" if force_regenerate and hero is not None else "generating"
            log.info(f"[{p.sku}] {('Existing hero found — ' + action) if force_regenerate and hero else 'No existing hero found — generating'}")
            generator.generate_hero(
                product_name=p.name,
                audience=brief_obj.audience,
                market=brief_obj.target_market,
                out_path=hero_path,
            )
            hero = hero_path
            hero_source = "genai"
            manifest["metrics"]["generated"] += 1
        else:
            log.info(f"[{p.sku}] Reusing existing hero at {hero}")
            hero_source = "existing"
            manifest["metrics"]["reused"] += 1

        # Each product contributes multiple aspect-ratio variants.
        prod_entry: Dict = {"sku": p.sku, "variants": []}

        # 3) Compose required aspect ratios for each requested locale.
        for locale in languages:
            # Localise the message if a file override exists; fall back to English.
            msg = localise.get_localised_message(
                base_message=brief_obj.message,
                target_locale=locale,
                source_locale="en-GB"
            )

            for ratio in brief_obj.requirements.aspect_ratios:
                # Output path: <outdir>/<campaign>/<sku>/<ratio>/ad_<locale>_001.jpg
                out_dir = outdir / brief_obj.campaign_id / p.sku
                out_path = out_dir / ratio.replace(":", "x") / f"ad_{locale}_001.jpg"

                composed = composer.compose_variant(
                    hero,
                    out_path,
                    msg,
                    brief_obj.brand.primary_colour,
                    locale,
                    ratio,
                )

                comp: Dict = {
                    "aspect_ratio": ratio,
                    "locale": locale,
                    "source": hero_source,
                    "output_path": str(composed),
                    "compliance": {
                        "logo": checks.logo_present(Path(brief_obj.brand.logo_path)),
                        "prohibited_terms": checks.legal_check(msg),
                    },
                }
                prod_entry["variants"].append(comp)

        manifest["products"].append(prod_entry)

    # 5) Persist manifest for auditability (downstream analytics / approvals can read this).
    man_path = Path("manifests") / f"{brief_obj.campaign_id}_run_001.json"
    man_path.write_text(json.dumps(manifest, indent=2))

    log.info(f"Completed campaign {brief_obj.campaign_id}")
    log.info(f"Manifest written to: {man_path}")
    log.info(f"Outputs available under: {outdir}/{brief_obj.campaign_id}/")

if __name__ == "__main__":
    typer.run(main)
