# Content Factory — Creator Clips v4.1.0

**Documentação:** [índice de operação, processo, arquitetura, GPU e testes](docs/README.md).

Local-first, **human-reviewed** short-video creator for authorized source media. Input an uploaded video or an explicitly authorized YouTube URL; transcribe with **faster-whisper**, shortlist highlights using a heuristic or local **Qwen2.5 via Ollama**, create an editable **timeline JSON** with a constrained **AI Editing Director**, then render 9:16 cuts using **FFmpeg + Remotion**. Preview and approve in Streamlit. No paid AI API, Hermes account, or autoposting required.


## Start the workstation (Linux / Docker Desktop with WSL2)

```bash
cp .env.example .env
docker compose up --build -d
# Browse http://localhost:8501
docker compose logs -f worker
```

By default, the Python worker transcribes locally (`WHISPER_MODEL=base`, CPU/int8) and creates up to three clips. The **Ajustes de processamento** panel saves model, beam size, highlight count/duration, Qwen analysis limits and engine choices with each job; `app.submit` accepts the same `settings` object. The render step uses the FFmpeg fallback if Remotion fails; **the fallback does not have animated typography or B-roll**. Inspect each candidate's `director_used`, `renderer_used`, `word_count`, and downloadable `.timeline.json` in the UI.

Each finished candidate keeps its 720×1280 MP4 for download and gets a smaller VP8/Opus WebM preview for browser playback. The preview is decoded completely before it appears in the UI. Existing MP4s are used as a fallback when a preview has not been generated yet.

### Enable local Qwen with Ollama

```bash
docker compose --profile local-ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
# Then set CLIP_RANKER=ollama and EDIT_DIRECTOR=ollama in .env
docker compose up -d --force-recreate worker
```

For compatible NVIDIA CUDA setup, add `-f compose.ollama-gpu.yaml` for Ollama, and/or `-f compose.gpu.yaml` for the worker. The default image uses CPU and is slower; the NVIDIA path requires Docker NVIDIA runtime and a matching driver.

### Experimental Quadro K4200 path

The K4200 can run Qwen 2.5 through a CUDA 10.2 build of `llama.cpp` even though current Ollama does not use this card. On this workstation, after starting the base services and pulling `qwen2.5:3b`, run:

```powershell
./research/build-kepler.ps1
docker compose -f compose.yaml -f compose.kepler.yaml up -d worker ui kepler-engine kepler-bridge
Invoke-RestMethod http://127.0.0.1:11436/health
```

Choose **GPU K4200 (experimental)** under **Processamento do Qwen** for each job. `KEPLER_CTX_SIZE`, `KEPLER_BATCH_SIZE`, `KEPLER_UBATCH_SIZE`, `KEPLER_GPU_LAYERS`, `KEPLER_THREADS`, and `KEPLER_REQUEST_TIMEOUT` are adjustable in `.env`. Whisper remains on CPU; the GPU option applies to the Qwen classifier and editing director. See [the measurements and limitations](research/GPU_K4200_EVALUATION_2026-11-04.md).

The GPU bridge checks its live context window before inference and reports when a response reaches its token limit. Those decisions fall back to the deterministic heuristic. The UI shows the release version and GPU health in Doctor. The K4200 path remains optional because the CUDA 10.2/WSL combination is outside NVIDIA's supported WSL GPU range.

## Editing flow

```
Source (uploaded video or permitted YouTube URL)
  -> faster-whisper with word timestamps
  -> heuristic shortlist plus Qwen proposals anchored to transcript segments, then rerank
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

Use os comandos e critérios em [Testes e validação](docs/TESTES.md). Nesta workstation a suíte roda na imagem existente do worker, com o código montado, sem reconstruir a imagem.

The tests cover timeline bounds and media safety, per-job settings, ranker fallback, queue restart recovery, the Doctor, YouTube URL parsing and synthetic FFmpeg output. End-to-end Remotion/Chromium and actual Ollama inference must also be tested on the workstation. This project does not currently include automated social posting, word-level forced alignment after text correction, face tracking, or multi-worker leases.

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
