# Content Factory — Creator Clips MVP v4.0

Local-first, **human-reviewed** short-video creator for authorized source media. Input an uploaded video or an explicitly authorized YouTube URL; transcribe with **faster-whisper**, shortlist highlights using a heuristic or local **Qwen2.5 via Ollama**, create an editable **timeline JSON** with a constrained **AI Editing Director**, then render 9:16 cuts using **FFmpeg + Remotion**. Preview and approve in Streamlit. No paid AI API, Hermes account, or autoposting required.

> **Copyright / platform access:** Only use media with documented permission to make derivative clips and the intended distribution/monetization rights. The optional YouTube downloader additionally requires applicable platform authorization. Declaring permission in the UI records an attestation; the app does not verify license authenticity. No cookies, paywall access, private-video access, or access bypasses are provided.

## Run on a workstation (CPU, Docker Desktop/WSL2, or Linux)

```bash
cp .env.example .env
docker compose up --build -d
# Open http://localhost:8501
docker compose logs -f worker
```

By default, the Python worker transcribes locally (`WHISPER_MODEL=base`, CPU/int8) and creates multiple candidates (up to 3). `EDIT_DIRECTOR=ollama` and `CLIP_RANKER=ollama` will **fall back** when Ollama is unavailable; the render step falls back to an FFmpeg subtitled cut if Remotion fails. Check the per-clip `director_used`, `renderer_used`, `word_count` and downloadable `.timeline.json` in the UI. **Fallback does not include animated typography / B-roll.**

### Enable Qwen, at zero API cost

```bash
docker compose --profile local-ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
# In .env: CLIP_RANKER=ollama; EDIT_DIRECTOR=ollama
docker compose up -d --build ui worker
```

The first model download needs internet. Docker volumes preserve Ollama models and Whisper cache. Doctor verifies worker heartbeat and Ollama availability; it reports actual inference/fallback status per job, not fictitious progress percentages. Qwen uses **transcript text only** (no vision/audio understanding).

For an NVIDIA GPU with a correctly configured Docker GPU runtime:

```bash
# GPU acceleration for faster-whisper (worker):
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
# Separately, optional Ollama GPU acceleration:
docker compose -f compose.yaml -f compose.ollama-gpu.yaml --profile local-ai up -d ollama
```

The Ollama and Whisper workloads may compete for limited VRAM. Test each mode independently before enabling both; CPU is the safe initial baseline. Non-NVIDIA hardware requires another backend.

## What is actually automated?

1. **Acquire:** local MP4/MOV/MKV upload; YouTube individual URL ingestion is opt-in (`ENABLE_YOUTUBE_DOWNLOAD=false` unless authorized by both platform and rights holder).
2. **Transcribe:** `faster-whisper` with voice activity detection, configurable vocabulary hint, and **word-level timestamps**. Original speech remains audible. Word timing quality depends on the model and source audio; this is not WhisperX forced alignment or automatic semantic proofreading.
3. **Select:** heuristic finds candidate speech windows; optionally, Qwen sorts 12 candidates semantically, with fallback. It does not search the entire media visually.
4. **Direct:** Qwen suggests a spoken-word-based title, up to 3 zooms, and up to 2 B-roll inserts **only from registered authorized local assets**. It cannot run arbitrary code or request local file paths. Timeline builder validates bounds and source IDs.
5. **Stage & render:** FFmpeg crops/normalizes base audio/video and trims muted B-roll; Remotion composes animated 3-word captions with the current spoken word highlighted, pop-in title, zooms and B-roll. Defaults: 720×1280 @ 30 fps, duration <= 60 sec.
6. **Review:** Streamlit displays each preview, offers the reproducible timeline JSON, and persists approval/rejection. **No publication to YouTube, Instagram, Facebook or TikTok is implemented.**

### Licensed gameplay library

Open **Biblioteca de gameplay / B-roll autorizado** in Streamlit. Upload your own authorized gameplay, add a descriptive label (e.g., `Vice City driving, daytime`), and retain a reference to permission. This stores assets under `data/assets/` and a catalog there; Qwen only receives asset IDs/descriptions, never filesystem paths. Bad/inaccessible B-roll is skipped rather than failing the full video.

### Directory layout

```text
app/                 Streamlit, queue worker, Whisper, Qwen ranker/director, timeline, render orchestration
renderer/src/        Remotion React timeline renderer (animated captions, title, punch zoom, licensed B-roll)
contracts/           Incoming agent proposal and timeline example schemas
scripts/             Smoke test launcher
tests/               Unit + synthetic FFmpeg regression tests
compose*.yaml        CPU stack, optional NVIDIA whisper and Ollama GPU overrides
data/                 Persistent local files / private content (gitignored)
```

The UI is **localhost-only**, **not authenticated**; use a VPN or SSH tunnel if accessing remotely, **never** expose port 8501 or Redis on the public internet. Keep credentials in `.env` (gitignored).

## Upgrade from v3.2 / backup

Stop accepting new jobs; **allow any active job to finish before restarting**. Back up `.env`, `data/` and Docker named volumes (especially Ollama). Replace the source files with v4 and preserve your data. Add new variables from `.env.example` to `.env`; recreate `ui` and `worker`:

```bash
docker compose up -d --build ui worker
```

Existing job records remain readable; they will not be retranscribed or re-rendered automatically. New clips get a timeline, word timing and render metadata. If `RENDER_ENGINE=ffmpeg` or Remotion fails, the fallback produces the legacy subtitled output and marks it accordingly.

## Tests

```bash
# Local Python environment with FFmpeg installed:
python -m pip install -r requirements.txt
python -m pytest -q
# Or via Docker (mount tests into the container):
docker compose run --rm --no-deps -v "$PWD/tests:/app/tests:ro" ui pytest -q tests
```

Tests use synthetic media; they **do not** download copyrighted YouTube videos or paid models. The Remotion render and GPU/Ollama integration need to be tested in your environment because they require Chromium, Docker and model downloads. See [architecture](docs/ARCHITECTURE.md) and [test plan](docs/TEST_PLAN.md).
