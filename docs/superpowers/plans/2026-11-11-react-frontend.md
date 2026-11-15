# React frontend Implementation Plan

> Execute inline with superpowers:executing-plans. User approved the design and requested minimal tokens, no extra approval loops or redundant refactors.

**Goal:** Replace the default Streamlit UI with integrated React and FastAPI.
**Architecture:** nginx serves Vite and proxies to internal web-api; Python domain services and optional integration API stay authoritative.
**Tech Stack:** React/TypeScript/Vite, FastAPI/Starlette, nginx, existing Redis/worker.
**Spec:** ../specs/2026-11-11-react-frontend-design.md

## Global Constraints

- Preserve data, environment files, volumes, job snapshots, media and integrations.
- YouTube enabled by default, explicit false honored, rights/platform gates required.
- No remote publication during tests; actual flow uses agent-browser CLI.
- Five viewports: 1440, 1024, 820, 430, 375 px. Legacy Streamlit archived.
- Work inline on codex/react-frontend; no automatic commit/push/merge.

## Review Focus

- Stale/mutated media and candidate history must reject review atomically.
- Polling and route changes must preserve unsaved feedback tied to its render.
- Proxy must not expose secrets, internal paths or cross-origin mutation access.
- An active publisher must never consume test schedules.
- Explicit installation overrides and old settings must retain their behavior.

### Task 1: API and service contracts

Files: app/web_api.py, app/web_views.py, app/service.py, app/job_settings.py,
app/edit_render.py, app/worker.py, app/youtube.py, tests/test_web_api.py.
Interfaces: /api/bootstrap, jobs, review, media, groups, sources, assets, publications,
metrics, settings and Doctor; review(jid,cid,seen,p) maps to shared locked service.
- [x] Add failing HTTP tests: auth/origin, snapshot/rights, stale history/artifact,
  rejection of failed candidates, source conflict, metrics, schedule limits and media Range.
- [x] Run focused tests; implement adapter and small shared-service additions; rerun.

### Task 2: Integrated frontend

Files: frontend/src/{App,store,types,ui,Review,Publish,Library,Other,Settings}.tsx/ts,
styles.css, package/lock, vite config and frontend tests.
Interfaces: named store functions remain, return Promises and accept optional complete inputs.
- [x] Add failing store/form contract tests (fetch/409/incomplete input/demo isolation).
- [x] Import proposal assets; integrate real endpoints, missing settings/Doctor/comparison,
  preserve drafts across polling/routes; implement explicit isolated DEMO.
- [x] Run frontend tests, typecheck and Vite build.

### Task 3: Deployment and legacy

Files: Dockerfile.web-api, requirements.web.lock, frontend/Dockerfile, nginx config,
compose.yaml, compose overrides, app/_legacy_streamlit, .gitignore.
Interfaces: localhost:8501 frontend; internal web-api; existing optional API unchanged.
- [x] Verify no active processing/publication and available disk before build/cutover.
- [x] Build only thin web image/frontend, preserve worker; archive presentation-only code.
- [x] Validate Compose combinations and start web services without interrupting worker.

### Task 4: Acceptance and documentation

Files: README.md, docs/{README,ARCHITECTURE,PROCESSO,CONFIGURACAO,OPERACAO,TESTES,API_WEB}.md,
research/react_frontend_acceptance.md and focused regression tests as needed.
- [x] Run focused then complete relevant suites; fix observed regressions with tests.
- [x] agent-browser: real authorized job to review, approve/reject, 409/drafts, five
  viewports, WebM/MP4 playback; isolated schedule/rejection/replanning and DEMO simulation.
- [x] Document observed results, blocked checks and operational settings without secrets.
- [x] One final review, proportional fixes, git diff --check; no unobserved success claims.

## Execution ledger

- Initial status: only approved design doc untracked; branch created codex/react-frontend.
- Queue/processing observed 0/0; publisher is active. 21 GB free on C:, 1.78 TB on E:.
- Ruling: work in the provided checkout on a dedicated branch, preserving running
  services and paths; avoid an extra worktree/context to honor token/operation economy.
- Ruling: execute the approved design directly; this plan records steps without another
  approval prompt, as explicitly requested by the user.
- Pre-flight: Task 1 DTOs and async mutations consumed by Task 2; nginx in Task 3 forwards
  /api unchanged with a server-only token; Task 4 tests this same contract.

- Tasks 1–3 implemented: thin API/contracts, integrated frontend, nginx cutover; optional integration API and publisher preserved. Worker restarted only after queue/processing 0/0 to load additive settings support.
- Ruling: cache browser DTOs by job JSON and file stat fingerprint after observing repeated full-media reads on polling. Reviews retain fresh byte hashing under lock.
- Review: one independent static review; fixed artifact-bound publication consent, atomic expected identity for scheduling/drafts and form retention across modules. Runtime/browser and isolated publisher acceptance remain executor checks.
- Validation observed: focused API/publication 35 passed; archived UI/settings/queue/flexible 33 passed; frontend 8 passed/build; full suite rerun in progress.
- Browser real job 0b7bf3b8-f83f-4de2-ba30-4ef57fe3b240: NEEDS_REVIEW, two Remotion high candidates VALID; both WebM and both MP4 reached ended without media error, all four decoded fully with FFmpeg.

- Task 4 complete: definitive Python suite 623 passed; frontend 8 passed/build; renderer typecheck passed; Compose variants and diff check passed. Five viewports, real job/media/reviews, form retention, isolated agenda/library and DEMO verified with agent-browser CLI.
- User authorized one real Portuguese subtitled approved candidate; Instagram @nextgen.zip confirmed PUBLISHED at https://www.instagram.com/reel/Dfmv8_CCY4c/. Owner subsequently edited the caption and confirmed doing so; no corrective overwrite performed.
- Ruling: reuse configured publisher via non-secret readiness declaration in auto mode, rather than leaving an existing Instagram integration disabled. Explicit false and per-send human consent remain required controls. User explicitly requested Instagram functioning.
- Final evidence and limitations: research/react_frontend_acceptance.md. Keep changes on codex/react-frontend without commit/push/merge, matching the approved plan.
