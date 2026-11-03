# Acceptance test plan — v4

## Automated

* `python -m pytest -q`: validate timed captions, timeline bounds, unauthorized assets, Qwen director fallback, download URL validation, status persistence, audio/video synthetic FFmpeg output.
* `docker compose config`: check Compose interpolation for local target system.
* `docker compose build ui worker`: confirm Chromium + Node/Remotion setup in images.

## Manual integrated smoke test (workstation)

1. Preserve and back up your existing `.env`, `data/` and model volumes; update services without deleting volumes.
2. Start Ollama using the Compose profile and confirm `ollama list` contains `qwen2.5:3b`.
3. Open the local Streamlit UI; check Doctor reports Worker online and model available.
4. Submit a **locally stored authorized** 5–15 minute video with clear PT-BR speech; record authorization evidence.
5. Verify job transitions: `QUEUED -> TRANSCRIBING -> (DIRECTING -> RENDERING) -> NEEDS_REVIEW`.
6. Confirm three separate candidates when source speech permits; open `candidate_N.timeline.json` and compare word times with audio.
7. Upload a **licensed** B-roll clip and create a new job; confirm Director never chooses an unregistered ID and any inserted footage is muted.
8. Inspect an animated subtitle and title, audio continuity, readability within social safe areas, and visual crop. Check `renderer_used` is `remotion` rather than fallback.
9. Temporarily disable Ollama: new jobs should continue via semantic/director fallback, not crash, with reasons recorded.
10. Set `RENDER_ENGINE=ffmpeg`; verify output is playable and metadata says `ffmpeg_subtitled`.
11. Approve one candidate, reject another, refresh the dashboard; confirm persisted decision and **no social posting**.

### Known environment constraints

Automated tests do not guarantee Docker/Chromium/Remotion execution. Run the full integration smoke test on the actual workstation with its GPU/driver combination before unattended use. Measure VRAM, transcription speed, rendering latency and subtitle accuracy with real material.
