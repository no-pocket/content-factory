# Review experience and publishing foundations

Approved design: docs/planning/2026-11-07-review-experience-design.md.
Owner additionally confirmed Instagram/Facebook, YouTube and TikTok connector foundations.

Execution: use superpowers:subagent-driven-development for independent tasks;
the coordinator owns review concurrency/performance and integration.

- [x] Reproduce multi-candidate stale revisions; fix without weakening same-candidate concurrency. Cache presentation hashes only; final save always checks real bytes. Test focused regressions and two-client behavior.
- [x] Replace numeric ratings with optional stars and explicit zero content grade; add explanatory tooltips, without inventing weights or changing old feedback.
- [x] Improve generated titles without regenerating existing candidates. Implement default-off per-job licensed outro selection and full-duration QC, preserving masters/previews. Synthetic tests; actual user asset still required.
- [x] Implement provider-specific publishing foundations for Meta Instagram/Facebook, YouTube and TikTok using current official docs. Connection/configuration status and validated publication drafts, dry-run initially; no external publishing or account connection without explicit action. Never put secrets in job records or Git.
- [x] Surface truthful ML eligibility status using saved human reviews; no automatic training/promotion.
- [x] Run full tests, browser review flow in isolated fixtures, verify original jobs/feedback remain intact, fresh review and deploy relevant fixes to main application with idle queue.

Review focus: stale forms after another candidate review; true concurrent same-render changes;
same-size media mutation invalidates final approval; optional unset vs zero ratings;
publication cannot bypass current artifact approval; outro audio/timestamps/full QC;
existing processing snapshots remain unchanged.

Task review: review UX/stars and publishing passed. Publishing minor widget limits fixed per provider. Outro identity fix round1 addressed; title grounding round2 in progress after relationship-swap reproduction. Whole-branch reviewer found no additional important regression. Full suite at round1:379 passed in77.42s; final rerun required after round2.
Ruling: preserve existing candidates/titles and feedback; apply new title/outro rules only to newly generated renders, as approved. Publishing is a local foundation with no live transport.

Round2 implemented: original mixed-claim/entity-swap repros fail closed. 34 focused tests passed. Full final suite:385 passed72.67s. BrowserQA passed isolated fullapp sequential approval/rejection, comment preservation, relevance5/content0, Instagramlocaldryrun and MP4/WebMplayback. Scoped finaloutro/title verdict pending before deployment.

Final scoped review: both Important findings ADDRESSED, no new Important breakage. Independent hostfocused22passed/2skipped(noFFmpeg); controllerDockerfull385passed72.67s. Main fast-forwarded to4272005 and pushed; idlequeue0/0 before restart worker/api/ui; Streamlit healthok, workerwaiting recovered0. Preservation check:39/39jobJSONs byte-identical,104candidateIDs/settings/priorreviews preserved,2v2events. No real editorial events or externalpublishing generated. Owneroutro and providerOAuth/transports remain explicit nextsteps.
