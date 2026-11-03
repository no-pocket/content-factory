# Content Factory v4 — technical design

## Components

```text
Streamlit :8501  ->  Redis job queue  ->  one worker
                                          |
                                          +-> (optional yt-dlp, opt-in licensed URL)
                                          +-> faster-whisper (VAD + timestamps per word)
                                          +-> ranker: heuristic or Ollama Qwen2.5
                                          +-> AI Editing Director: Ollama Qwen2.5
                                          +-> validated timeline JSON, licensed B-roll catalog
                                          +-> FFmpeg media staging
                                          +-> Remotion composition -> MP4
                                          +-> FFmpeg subtitles fallback on render failure
                                          +-> status NEEDS_REVIEW -> UI approve/reject
```

**No extra microservices**: one worker, one Redis, one Streamlit, one optional Ollama. Job state + transcripts + media are persisted in `data/`. The timeline (a versioned edit decision list) is saved next to each output; it never contains arbitrary shell code, filesystem paths provided by LLMs or network URLs.

## Trust boundaries

* Source URL is restricted to canonical individual YouTube URLs; rights attestations are recorded. Download disabled by default.
* Local uploaded assets require a creator description + permission reference and receive a generated ID. Catalog path checks reject traversals and unknown IDs.
* Model output (`hook`, punch zoom, B-roll requests) is **advice only**. The timeline builder enforces clip bounds, maximum effects, asset whitelist and subtitle timings.
* Renderer uses pre-staged `base.mp4` / `broll_N.mp4` under a generated static directory. Audio from B-roll is muted.
* The UI/queue are **not** public-facing services; no publishing authorization is present.

## Timeline 2.0

The schema's relevant fields are `schema_version`, fixed `width`/`height`/`fps`, `duration`, `source_range`, and `layers.video`, `layers.audio`, `layers.captions` (word events), `layers.text` (pop banner), `layers.effects` (punch zoom) and `layers.broll` (licensed local media). `caption_style` selects `bold_karaoke_v1`. All times are seconds **relative to the cropped clip**, except `source_range`.

`app/timeline.py` is the canonical validator/builder. The JSON contract under `contracts/` helps external editing agents, but it is not a substitute for the runtime validator.

## Failure and recovery

* Ranker timeout, invalid JSON or unreachable Ollama -> heuristic shortlist.
* Director timeout, invalid structure -> safe default timeline with captions + spoken-words title.
* Bad B-roll transcode -> skip that insert and continue to render.
* Remotion failure -> optional FFmpeg subtitled render; the UI identifies fallback. Set `RENDER_FALLBACK_FFMPEG=false` for strict validation.
* Worker crash while executing a job may leave the job in an in-progress state; the current MVP does not implement automatic redelivery/recovery. Before 24/7 production, add durable leases and idempotency.

## Non-goals / known gaps

* No account-based access control, no HTTPS edge exposure, no multi-node orchestration, no social uploads, no automatic copyright verification.
* No speaker/face tracking, scene intelligence or WhisperX forced alignment. B-roll suggestions use written descriptions and ASR only.
* Default render is 720x1280 to keep CPU cost manageable. You can scale to 1080x1920 after benchmarks and matching validator/Remotion settings.
