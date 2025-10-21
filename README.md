# Creative Automation Pipeline (POC)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-%F0%9F%9A%80-009688.svg)](https://fastapi.tiangolo.com/) [![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B.svg)](https://streamlit.io/)

A local proof-of-concept that ingests a campaign brief, reuses or generates hero images,
creates 1:1, 9:16 and 16:9 variants with message + logo, and writes a manifest.

## Quickstart
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API key later if using a real image API

# Run the pipeline with the default brief
python main.py --brief briefs/sample.json

# Optional: Specify custom output folder and force regeneration
python main.py --brief briefs/sample.json --outdir demo_outputs --force-regenerate

# Optional: Test localisation (ensure assets/localisation/messages_de-DE.json exists)
python main.py --brief briefs/sample.json
```

```bash
# Optional: Demonstrate asset reuse
cp outputs/SPRING24-UK-001/ECOCLEAN-1L/1x1/ad_en-GB_001.jpg assets/products/ECOCLEAN-1L/hero.png
python main.py --brief briefs/sample.json
```
```bash
# Optional: Use advanced CLI flags
# --outdir lets you choose a custom output folder
# --force-regenerate ignores cached heroes and regenerates all assets
python main.py --brief briefs/sample.json --outdir demo_outputs --force-regenerate
```

## One‑Command Demo Script (optional)

For macOS/Linux reviewers who want a *single command* demo, save this script and run it.

**Create the script:**
```bash
mkdir -p scripts
cat > scripts/demo.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root and enter it
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$repo_root"

echo "[1/5] Creating venv & installing deps..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "[2/5] Preparing environment..."
[ -f .env ] || cp .env.example .env
# Uncomment and add a key for real generations
# echo 'OPENAI_API_KEY=sk-...' >> .env

echo "[3/5] Running pipeline with sample brief..."
python main.py --brief briefs/sample.json

echo "[4/5] Locating a sample output..."
latest_img=$(ls -t outputs/*/*/9x16/ad_en-GB_001.jpg 2>/dev/null | head -n1 || true)

echo "[5/5] Opening the output (if possible)..."
if [[ -n "${latest_img}" ]]; then
  if command -v open >/dev/null 2>&1; then
    open "${latest_img}"          # macOS
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${latest_img}"      # Linux
  else
    echo "Output ready at: ${latest_img}"
  fi
else
  echo "No output found. Check 'outputs/' and logs above."
fi
EOF
chmod +x scripts/demo.sh
```

**Run it:**
```bash
./scripts/demo.sh
```

This script bootstraps a venv, installs dependencies, runs the pipeline on the sample brief, and opens a generated creative (falls back to printing the path if GUI open is unavailable).

## Reviewer Walkthrough (2 minutes)

If you're short on time, follow these steps to verify the build quickly:

1) **Run the CLI once**
   ```bash
   python main.py --brief briefs/sample.json
   ```
   - Watch the logs for: brief loaded, hero reuse/generation, locales, output & manifest paths.

2) **Open the outputs & manifest**
   - Creatives appear under `outputs/<campaign_id>/<sku>/<ratio>/ad_<locale>_001.jpg`.
   - The manifest is written to `manifests/<campaign_id>_run_001.json`.

3) **(Optional) Try the UI**
   - Start API: `uvicorn api.app:app --reload` (with `API_TOKEN` set).
   - Start UI: `streamlit run ui/app.py` (with `API_URL` + `API_TOKEN`).
   - Enter a prompt, pick ratios/locales, upload a logo → generate and download ZIP.

That’s it — you’ve seen the full path from brief → generation → review.

---

## Architecture Overview

The Creative Automation Pipeline is a modular proof-of-concept that mimics a real-world
creative generation system. It ingests structured campaign briefs, validates them,
and automates the creation of brand-safe ad creatives in multiple aspect ratios.
Where assets are missing, the system uses GenAI to generate new hero images,
then overlays campaign messaging and brand elements.

> In production, this pipeline would integrate with **Adobe Firefly** for on-brand image
> generation and **Adobe Experience Manager (AEM)** for centralised asset management.

---

## System Components

| Layer | Purpose | Key Decisions |
|-------|----------|----------------|
| **CLI (`main.py`)** | Provides a simple local entry point. | Built with Typer for readability and quick setup. |
| **Schemas (`src/models/schemas.py`)** | Validates campaign briefs. | Pydantic ensures strict data contracts and early error catching. |
| **Services (`src/services/*`)** | Encapsulates functionality: storage, generation, composition, and checks. | Enforces single-responsibility design and scalability. |
| **Storage Layer** | Handles asset discovery and output structuring. | Easily swapped with AEM/S3/Azure in production. |
| **Image Generator** | Creates placeholders or calls GenAI APIs. | Offline by default; easily configured for OpenAI or Firefly. |
| **Composer** | Produces final creatives (text, logo, colour bar). | Pillow chosen for lightweight, platform-agnostic image operations. |
| **Checks** | Runs brand/legal QA. | Demonstrates awareness of marketing governance workflows. |
| **Logger** | Standardises pipeline logging. | Ensures clear reporting and future integration with monitoring tools. |

---

## Project Structure
```text
creative-automation-pipeline-poc/
│
├── assets/          # Input & reusable media
├── briefs/          # JSON campaign briefs
├── outputs/
│   └── SPRING24-UK-001/  # generated creatives (truncated)
│       └── ...
├── manifests/       # Run metadata & logs
├── src/             # Source code (models, services, utils)
└── main.py          # CLI orchestrator
```

### Folder Legend
- **[api/](api/)** — FastAPI gateway exposing `/generate` and `/download` routes
- **[assets/](assets/)** — reusable brand, localisation, and product heroes
- **[briefs/](briefs/)** — campaign brief JSON inputs
- **[docs/gallery/](docs/gallery/)** — lightweight sample outputs for reviewers
- **[manifests/](manifests/)** — JSON run manifests for traceability
- **[outputs/](outputs/)** — generated creatives (per campaign/SKU/ratio)
- **[src/](src/)** — core pipeline logic (models, services, utils)
- **[ui/](ui/)** — optional Streamlit user interface
- **[main.py](main.py)** — CLI entrypoint for local execution

---

## Data Flow

1. Load and validate campaign brief.  
2. Discover existing assets; reuse if available.  
3. Generate missing assets via GenAI or placeholder logic.  
4. Compose creatives (1:1, 9:16, 16:9) with overlay and logo.  
5. Run brand/legal compliance checks.  
6. Save results and manifest for transparency and reproducibility.

---

## Design Decisions & Rationale

| Decision | Rationale |
|-----------|------------|
| **Python + Typer + Pydantic + Pillow** | Fast, readable, and ideal for a code-review environment. |
| **Local-first design** | Enables reviewers to test without credentials while mirroring real pipelines. |
| **JSON Manifest output** | Provides an auditable record of each run and aligns with data-driven creative ops. |
| **Aspect ratios (1:1, 9:16, 16:9)** | Mirrors standard social ad formats (Meta, TikTok, YouTube). |
| **Compliance checks** | Demonstrates awareness of brand and legal requirements in creative automation. |
| **Deterministic generation** | Ensures reproducibility for QA and creative review cycles. |
| **Single command execution** | Minimises friction for technical reviewers. |

---

## Evaluation Highlights

| Adobe Evaluation Theme | Evidence in This Build |
|--------------------------|------------------------|
| **Technical Ability** | Modular Python design with validation and service abstractions. |
| **Problem Solving** | Anticipates missing assets, compliance, and localisation. |
| **Design Thinking** | Clean structure, automation-ready pipeline, and metadata logging. |
| **Collaboration** | Logging and manifests support multi-team workflows. |
| **Creativity** | Visual composition and scalable design echo Adobe’s creative stack. |

---

## Future Extensions

- Integrate with **Adobe Firefly** for on-brand AI image generation.  
- Replace local folders with **Adobe Experience Manager (AEM)** or S3 storage.  
- Add localisation via translation API.  
- Implement async processing for multi-campaign batch runs.  
- Extend to a simple **FastAPI dashboard** for visual review and approval.  

---

## Outputs & Manifests

- Creatives: `outputs/<campaign_id>/<sku>/<aspect>/ad_<locale>_001.jpg`
- Manifest: `manifests/<campaign_id>_run_001.json` (contains sources, compliance flags, counts)
- Logs: `logs/<campaign_id>.log` (optional)

## Assumptions & Limitations

- English copy only for the POC; localisation can be added later.
- Placeholder generator used if no image API key is set.
- Simple brand/legal checks (logo present, prohibited words) are indicative, not exhaustive.
- Fonts are system defaults; substitute with brand fonts in production.

## 🛠 Troubleshooting

- **Pillow not finding a font**: the script falls back to a default bitmap font; install `DejaVuSans` for better rendering.
- **No images generated**: ensure `assets/brand/logo.png` exists and your brief path is correct.
- **Using a real image API**: copy `.env.example` to `.env` and set `OPENAI_API_KEY=...` (or your provider key). Re-run the command.

---

## Task 2: Proof of Concept Summary

This proof of concept demonstrates a **Creative Automation Pipeline** for scalable ad creative generation, aligned with Adobe’s Forward Deployed Engineer brief.

### Objectives Met
- **Automated creative generation:** Generates and composes ad creatives in 1:1, 9:16, and 16:9 formats.  
- **Smart asset reuse:** Detects existing heroes to optimise time and resources.  
- **Localised campaigns:** Demonstrates multi-language support using external JSON message files.  
- **Compliance checks:** Performs lightweight brand and legal validation (logo + prohibited terms).  
- **Manifest-driven reporting:** Records metadata for each creative, enabling future analytics and governance.  
- **Optional flags:** Allows reviewers to test regeneration and output paths via `--force-regenerate` and `--outdir`.

### Highlights
- Modular design with **Typer**, **Pydantic**, **Pillow**, and **Structlog**.
- End-to-end automation from brief → creative → manifest.
- Built to mirror a production-ready architecture (Firefly + AEM integration ready).

---

## Quickstart Guide

```bash
# Create and activate environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment example (if using real API key)
cp .env.example .env
```

### Run the pipeline
```bash
python main.py --brief briefs/sample.json
```

### Optional Flags
```bash
# Custom output directory and force regenerate all heroes
python main.py --brief briefs/sample.json --outdir demo_outputs --force-regenerate
```

### Demonstrate Asset Reuse
```bash
cp outputs/SPRING24-UK-001/ECOCLEAN-1L/1x1/ad_en-GB_001.jpg assets/products/ECOCLEAN-1L/hero.png
python main.py --brief briefs/sample.json
```

### Test Localisation
```bash
mkdir -p assets/localisation
cat > assets/localisation/messages_de-DE.json << 'EOF'
{ "message": "Machen Sie Ihr Zuhause in diesem Frühling grüner!" }
EOF
```

Then edit your brief to include:
```json
"languages": ["en-GB", "de-DE"]
```
and rerun:
```bash
python main.py --brief briefs/sample.json
```

---

## Viewing Outputs

Once the pipeline completes, your generated assets can be found under:

```
outputs/<campaign_id>/<product_sku>/<aspect_ratio>/ad_<locale>_001.jpg
```

For example:
```
outputs/SPRING24-UK-001/ECOCLEAN-1L/9x16/ad_en-GB_001.jpg
outputs/SPRING24-UK-001/ECOCLEAN-1L/9x16/ad_de-DE_001.jpg
```

The campaign manifest summarising all generated variants lives at:
```
manifests/SPRING24-UK-001_run_001.json
```


You can open it in any text editor or JSON viewer to see:
- Asset sources (existing or generated)  
- Localisation details  
- Compliance check results  
- Total generation metrics  

---

## Architecture Diagram (High-Level)
```
+------------------+
|  Brief (JSON)    |
+--------+---------+
         |
         v
+------------------+
|  CLI / API / UI  |
+--------+---------+
         |
         v
+------------------+
|   Pipeline Core  |
| (services/*)     |
|  ├ generator     |
|  ├ composer      |
|  ├ checks        |
|  └ storage       |
+--------+---------+
         |
         v
+------------------+
|  Outputs & Logs  |
|  creatives/      |
|  manifests/      |
+--------+---------+
         |
         v
+------------------------------+
|   (Future) Firefly + AEM     |
+------------------------------+
```
---

## FastAPI + UI Flow (at a glance)

```text
[ Browser UI (Streamlit) ]
          |
          v
   POST /generate        (X-API-Key, per-IP rate limit)
          |
          v
      FastAPI
          |
          v
   services/generator  ->  hero (AI or placeholder)
          |
          v
   services/composer   ->  overlays (brand bar, message, logo)
          |
          v
   services/checks     ->  logo present? legal terms?
          |
          v
   outputs/ + manifests/ + ZIP download (/download/{session})
```

This complements the high-level architecture and shows the optional API-enabled path for interactive demos.


### OpenAI for POC, Firefly for Production

For the POC
	•	Immediate key access enabled rapid iteration without enterprise provisioning delay
	•	Keeps focus on the architecture, not account provisioning
	•	Placeholder fallback allows the demo to run fully offline

For production
	•	Firefly provides brand-safe presets and style consistency
	•	Integrates with AEM for approvals, versioning and governance
	•	C2PA support and enterprise controls align with real creative ops

Only the generator service would be swapped — the orchestration, composer, checks,
storage and manifest layers remain the same.

---

## 🖥️ Optional UI (Streamlit)

A simple Streamlit app can be launched to provide a minimal UI for uploading briefs,
triggering generation, and previewing outputs.
Enables non-technical stakeholders to generate creatives interactively without using the CLI.

```bash
streamlit run ui/app.py
```

## 🌐 FastAPI Gateway (Optional)

A lightweight API layer exposes the generation pipeline over HTTP for UI or external callers.

### Run the API

```bash
export API_TOKEN=dev-token
uvicorn api.app:app --reload
```

### Example request

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "X-API-Key: dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "minimalist eco cleaner bottle on marble counter, daylight",
    "message": "Make your home greener",
    "locales": ["en-GB"],
    "ratios": ["1:1","9:16"],
    "brand_colour": "#0A84FF"
  }'
```

### Notes
- Basic auth via `X-API-Key`
- Per‑IP rate limiting enabled
- `/download/{session_id}` returns ZIP of all variants
- Designed to be swapped to Adobe Firefly + AEM in production

---

## 📸 Output Gallery

Below are examples of generated creative outputs from the Proof of Concept pipeline.  
To keep the repo light, commit just 1–2 representative JPGs under `docs/gallery/`.

### 1️⃣ Localised Creative Output (German)
*Automated asset generation with multilingual text placement.*

![Localized Creative - German](docs/gallery/creative_de-DE_9x16.jpg)

### 2️⃣ English Campaign Output
*Base campaign asset generated for the English (UK) locale, 9:16 ratio.*

![English Creative - 9x16](docs/gallery/creative_en-GB_9x16.jpg)

## How to Evaluate This Build

This project has been structured to make evaluation simple and transparent. The following steps help reviewers verify technical design, creative automation, and alignment with Adobe’s ecosystem.

### 1. Run the Proof of Concept
```bash
python main.py --brief briefs/sample.json
```
Check the logs for:
- Correct brief ingestion (`Starting campaign SPRING24-UK-001`)
- Hero reuse or generation messages  
- Localisation line showing active locales (e.g., `en-GB, de-DE`)
- Manifest and output confirmation lines

### 2. Inspect the Generated Creatives
Browse the `/outputs` folder:
- Each SKU (e.g. `ECOCLEAN-1L`, `FRESH-AIR`) should have 3 subfolders: `1x1`, `9x16`, `16x9`.
- Each contains creatives with campaign message and brand logo overlays.
- Check that reuse vs. generation is consistent with the terminal logs.

### 3. Validate the Manifest
Open the manifest file in `/manifests`:
- Confirm accurate metadata (aspect ratios, locales, compliance results).
- Verify `source` field correctly shows `genai` or `existing`.

### 4. Assess the Architecture
In `src/services/`:
- Note modular separation between generation, composition, checks, and storage.
- Observe comments and logging that explain design intent.

### 5. Review for Adobe Alignment
- Mentions of **Adobe Firefly** and **Adobe Experience Manager (AEM)** in the README show architectural foresight.
- Localisation and compliance features reflect scalable, enterprise-ready design.
- Logging and manifesting mimic production creative-ops pipelines.

> **Tip:** Reviewers can run multiple briefs or change locales to test flexibility. The deterministic outputs and clean manifest structure make validation easy.

## Branch Management

This project uses a protected `main` branch to ensure stability.

**Rules applied:**
- Pull requests required before merging.
- Linear commit history enforced.
- Force pushes and deletions disabled.
- Optional status checks may be added later.

Developers can freely create feature branches (e.g. `feature/localisation`) and open pull requests for review before merging into `main`.

## Version Control & Branch Workflow

To ensure clean collaboration and maintain high code quality, the project uses a **feature-branch workflow** with protected branches:

- **`main`** – the production-ready branch; direct commits are blocked.  
- **Feature branches** – new functionality and fixes are developed in `feature/<name>` branches.  
- **Pull Requests (PRs)** – all changes are merged into `main` via reviewed PRs.  
- **Branch Protection Rules** – prevent force-pushes and require at least one review before merge, enforcing good DevOps practice even for solo development.

Example flow:
```bash
# Create a new branch
git checkout -b feature/update-readme

# Commit changes
git add .
git commit -m "Docs: Updated README with workflow section"

# Push branch and open PR
git push -u origin feature/update-readme
```


## Security & Abuse Prevention

This POC includes several safeguards to prevent accidental or malicious over‑use:

- **Prompt safety filtering** — basic term‑block list and max prompt length.
- **Variant cap per request** — limits locales×ratios to prevent burst usage.
- **UI rate limit (per session)** — throttles repeated clicks client‑side.
- **API rate limit (per IP)** — window‑based limiter in FastAPI gateway.
- **API key auth (`X‑API‑Key`)** — required for all API calls.
- **Graceful fallbacks** — placeholder generation if external API is missing/unavailable.

In a hardened environment this would be extended with:
- JWT / OAuth2 and per‑user quotas
- Audit logging and cost metering per run
- Server‑side moderation and policy enforcement
- Network‑level throttling and WAF rules

---

## Production Hardening Roadmap

If taken beyond POC, the next steps would include:

1) **Replace placeholder/OpenAI with Adobe Firefly**
   - On‑brand presets, enterprise licensing, C2PA credentials.

2) **Move assets & manifests into AEM / S3**
   - Versioning, approvals, lifecycle, signed URLs.

3) **Make the pipeline asynchronous**
   - Queue workers, retries, and SLA tracking (Celery/Temporal).

4) **Add authentication and RBAC**
   - OAuth2 / enterprise IdP integration with role‑based actions.

5) **Expose review & approval UI**
   - Preview grid, accept/reject, regenerate with comments.

6) **Telemetry & cost visibility**
   - Metrics for throughput, reuse‑rate, variant coverage and spend.

These steps map cleanly onto the current abstractions without redesign.

## License
This project is provided for evaluation and portfolio purposes only.  
No part of this repository may be used or redistributed without explicit permission.
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.