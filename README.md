# Content Factory — Creator Clips MVP v4.0

Local-first, **human-reviewed** short-video creator for authorized source media. Input an uploaded video or an explicitly authorized YouTube URL; transcribe with **faster-whisper**, shortlist highlights using a heuristic or local **Qwen2.5 via Ollama**, create an editable **timeline JSON** with a constrained **AI Editing Director**, then render 9:16 cuts using **FFmpeg + Remotion**. Preview and approve in Streamlit. No paid AI API, Hermes account, or autoposting required.

> **Copyright / platform access:** Only use media with documented permission to make derivative clips and intended distribution/monetization rights. The optional YouTube downloader additionally requires applicable platform authorization. No cookies, paywall access, private-video access or bypasses are provided.

## Start the workstation (Linux / Docker Desktop with WSL2)

```bash
cp .env.example .env
docker compose up --build -d
# Browse http://localhost:8501
docker compose logs -f worker
```

By default, the Python worker transcribes locally (`WHISPER_MODEL=base`, CPU/int8) and creates up to three clips. The `EDIT_DIRECTOR=ollama` and `CLIP_RANKER=ollama` settings fall back when Ollama is unavailable. The render step uses the FFmpeg fallback if Remotion fails; **the fallback does not have animated typography or B-roll**. Inspect each candidate's `director_used`, `renderer_used`, `word_count`, and downloadable `.timeline.json` in the UI.

### Enable local Qwen with Ollama

```bash
docker compose --profile local-ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
# Then set CLIP_RANKER=ollama and EDIT_DIRECTOR=ollama in .env
docker compose up -d --force-recreate worker
```

For compatible NVIDIA CUDA setup, add `-f compose.ollama-gpu.yaml` for Ollama, and/or `-f compose.gpu.yaml` for the worker. The default image uses CPU and is slower; the NVIDIA path requires Docker NVIDIA runtime and a matching driver.

## Editing flow

```
Source (uploaded video or permitted YouTube URL)
  -> faster-whisper with word timestamps
  -> heuristic shortlist, optional Qwen rerank
  -> Qwen Editing Director suggests hook, punch zooms and B-roll placements
  -> timeline.py validates bounds, IDs and source-anchored text
  -> FFmpeg stages center-cropped video and rights-registered B-roll
  -> Remotion composes overlays, active-word subtitles and final MP4
  -> manual approval in Streamlit
```

The director is not permitted to provide shell commands or arbitrary file paths; it only proposes restricted editing hints. Register B-roll under the **Biblioteca de gameplay** expander, including documented permission, so it becomes selectable. `data/` contains media, job records and sidecar timelines; preserve it across updates.

## Environment options

| Key | Default | Meaning |
| --- | --- | --- |
| `CLIP_RANKER` | `ollama` in .env.example | Local semantic reranking or `heuristic` |
| `EDIT_DIRECTOR` | `ollama` | Local editing proposals or `heuristic` |
| `RENDER_ENGINE` | `remotion` | Animated pipeline or `ffmpeg` |
| `RENDER_FALLBACK_FFMPEG` | `true` | Subtitle-only output if Remotion fails |
| `WHISPER_MODEL` | `base` | `small` improves many transcripts at greater compute cost |
| `WHISPER_DEVICE` | `cpu` | Switch to `cuda` only with compatible worker image |
| `ENABLE_YOUTUBE_DOWNLOAD` | `false` | Opt-in, rights- and platform-permission-gated URL ingestion |

## Test the code

```bash
python -m pytest -q
# Docker tests (source tests are not copied into runtime image):
docker compose run --rm --no-deps -v "$PWD/tests:/app/tests:ro" ui pytest -q tests
```

The tests cover timeline bounds and media safety, ranker fallback, the Doctor, YouTube URL parsing and synthetic FFmpeg output. End-to-end Remotion/Chromium and actual Ollama inference must also be tested on the workstation. This project does not currently include automated social posting, word-level forced alignment after text correction, face tracking, or production fault-tolerant job recovery.

## Troubleshooting — Hugging Face certificate verification

If a job fails during `TRANSCRIBING` with `CERTIFICATE_VERIFY_FAILED`, read [`docs/tls-certificates.md`](docs/tls-certificates.md). The worker supports a mounted `certs/*.crt` root-CA bundle for legitimate TLS inspection; it keeps HTTPS verification enabled.

## Operation & safety

- UI is bound to localhost. Use SSH tunnel or a trusted VPN rather than making it publicly accessible.
- Every source and B-roll asset must be authorized. A text attestation is recorded, but permission is not independently verified.
- Preserve `.env`, `data/`, and Docker volumes when updating. Allow active jobs to finish before restarting the worker.
- Worker heartbeats and Ollama inference/fallback are shown in the **Doctor** dashboard.
- For future Hermes integration, start with the `contracts/youtube_ingest.schema.json` contract and an authenticated submission API instead of exposing Redis.

## License notes

The repository code is a reference implementation. Third-party model, media, and rendering dependencies retain their respective terms. Review Remotion licensing before commercial operation.
