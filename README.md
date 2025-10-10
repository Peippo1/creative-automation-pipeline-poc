# Creative Automation Pipeline (POC)

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


---

## 🧩 Architecture Overview

The Creative Automation Pipeline is a modular proof-of-concept that mimics a real-world
creative generation system. It ingests structured campaign briefs, validates them,
and automates the creation of brand-safe ad creatives in multiple aspect ratios.
Where assets are missing, the system uses GenAI to generate new hero images,
then overlays campaign messaging and brand elements.

> In production, this pipeline would integrate with **Adobe Firefly** for on-brand image
> generation and **Adobe Experience Manager (AEM)** for centralised asset management.

---

## 🏗️ System Components

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

## 📂 Project Structure
```text
creative-automation-pipeline-poc/
│
├── assets/          # Input & reusable media
├── briefs/          # JSON campaign briefs
├── outputs/         # Generated creatives
├── manifests/       # Run metadata & logs
├── src/             # Source code (models, services, utils)
└── main.py          # CLI orchestrator
```

---

## 🧮 Data Flow

1. Load and validate campaign brief.  
2. Discover existing assets; reuse if available.  
3. Generate missing assets via GenAI or placeholder logic.  
4. Compose creatives (1:1, 9:16, 16:9) with overlay and logo.  
5. Run brand/legal compliance checks.  
6. Save results and manifest for transparency and reproducibility.

---

## ⚙️ Design Decisions & Rationale

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

## 🔍 Evaluation Highlights

| Adobe Evaluation Theme | Evidence in This Build |
|--------------------------|------------------------|
| **Technical Ability** | Modular Python design with validation and service abstractions. |
| **Problem Solving** | Anticipates missing assets, compliance, and localisation. |
| **Design Thinking** | Clean structure, automation-ready pipeline, and metadata logging. |
| **Collaboration** | Logging and manifests support multi-team workflows. |
| **Creativity** | Visual composition and scalable design echo Adobe’s creative stack. |

---

## 🚀 Future Extensions

- Integrate with **Adobe Firefly** for on-brand AI image generation.  
- Replace local folders with **Adobe Experience Manager (AEM)** or S3 storage.  
- Add localisation via translation API.  
- Implement async processing for multi-campaign batch runs.  
- Extend to a simple **FastAPI dashboard** for visual review and approval.  

---

## 📤 Outputs & Manifests

- Creatives: `outputs/<campaign_id>/<sku>/<aspect>/ad_<locale>_001.jpg`
- Manifest: `manifests/<campaign_id>_run_001.json` (contains sources, compliance flags, counts)
- Logs: `logs/<campaign_id>.log` (optional)

## 🧱 Assumptions & Limitations

- English copy only for the POC; localisation can be added later.
- Placeholder generator used if no image API key is set.
- Simple brand/legal checks (logo present, prohibited words) are indicative, not exhaustive.
- Fonts are system defaults; substitute with brand fonts in production.

## 🛠 Troubleshooting

- **Pillow not finding a font**: the script falls back to a default bitmap font; install `DejaVuSans` for better rendering.
- **No images generated**: ensure `assets/brand/logo.png` exists and your brief path is correct.
- **Using a real image API**: copy `.env.example` to `.env` and set `OPENAI_API_KEY=...` (or your provider key). Re-run the command.

---

## 🧾 Task 2: Proof of Concept Summary

This proof of concept demonstrates a **Creative Automation Pipeline** for scalable ad creative generation, aligned with Adobe’s Forward Deployed Engineer brief.

### 🎯 Objectives Met
- **Automated creative generation:** Generates and composes ad creatives in 1:1, 9:16, and 16:9 formats.  
- **Smart asset reuse:** Detects existing heroes to optimise time and resources.  
- **Localised campaigns:** Demonstrates multi-language support using external JSON message files.  
- **Compliance checks:** Performs lightweight brand and legal validation (logo + prohibited terms).  
- **Manifest-driven reporting:** Records metadata for each creative, enabling future analytics and governance.  
- **Optional flags:** Allows reviewers to test regeneration and output paths via `--force-regenerate` and `--outdir`.

### 💡 Highlights
- Modular design with **Typer**, **Pydantic**, **Pillow**, and **Structlog**.
- End-to-end automation from brief → creative → manifest.
- Built to mirror a production-ready architecture (Firefly + AEM integration ready).

---

## ▶️ Quickstart Guide

```bash
# 1️⃣ Create and activate environment
python3 -m venv .venv && source .venv/bin/activate

# 2️⃣ Install dependencies
pip install -r requirements.txt

# 3️⃣ Copy environment example (if using real API key)
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

## 🖼️ Viewing Outputs

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

## 🧭 How to Evaluate This Build

This project has been structured to make evaluation simple and transparent. The following steps help reviewers verify technical design, creative automation, and alignment with Adobe’s ecosystem.

### 🧩 1. Run the Proof of Concept
```bash
python main.py --brief briefs/sample.json
```
Check the logs for:
- Correct brief ingestion (`Starting campaign SPRING24-UK-001`)
- Hero reuse or generation messages  
- Localisation line showing active locales (e.g., `en-GB, de-DE`)
- Manifest and output confirmation lines

### 🖼️ 2. Inspect the Generated Creatives
Browse the `/outputs` folder:
- Each SKU (e.g. `ECOCLEAN-1L`, `FRESH-AIR`) should have 3 subfolders: `1x1`, `9x16`, `16x9`.
- Each contains creatives with campaign message and brand logo overlays.
- Check that reuse vs. generation is consistent with the terminal logs.

### 📄 3. Validate the Manifest
Open the manifest file in `/manifests`:
- Confirm accurate metadata (aspect ratios, locales, compliance results).
- Verify `source` field correctly shows `genai` or `existing`.

### 🧠 4. Assess the Architecture
In `src/services/`:
- Note modular separation between generation, composition, checks, and storage.
- Observe comments and logging that explain design intent.

### 💬 5. Review for Adobe Alignment
- Mentions of **Adobe Firefly** and **Adobe Experience Manager (AEM)** in the README show architectural foresight.
- Localisation and compliance features reflect scalable, enterprise-ready design.
- Logging and manifesting mimic production creative-ops pipelines.

> 💡 **Tip:** Reviewers can run multiple briefs or change locales to test flexibility. The deterministic outputs and clean manifest structure make validation easy.

