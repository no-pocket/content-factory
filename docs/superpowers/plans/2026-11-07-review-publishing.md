# Review experience and publishing foundations

Approved design: docs/planning/2026-11-07-review-experience-design.md.
Owner additionally confirmed Instagram/Facebook, YouTube and TikTok connector foundations.

Execution: use superpowers:subagent-driven-development for independent tasks;
the coordinator owns review concurrency/performance and integration.

- [ ] Reproduce multi-candidate stale revisions; fix without weakening same-candidate concurrency. Cache presentation hashes only; final save always checks real bytes. Test focused regressions and two-client behavior.
- [ ] Replace numeric ratings with optional stars and explicit zero content grade; add explanatory tooltips, without inventing weights or changing old feedback.
- [ ] Improve generated titles without regenerating existing candidates. Implement default-off per-job licensed outro selection and full-duration QC, preserving masters/previews. Synthetic tests; actual user asset still required.
- [ ] Implement provider-specific publishing foundations for Meta Instagram/Facebook, YouTube and TikTok using current official docs. Connection/configuration status and validated publication drafts, dry-run initially; no external publishing or account connection without explicit action. Never put secrets in job records or Git.
- [ ] Surface truthful ML eligibility status using saved human reviews; no automatic training/promotion.
- [ ] Run full tests, browser review flow in isolated fixtures, verify original jobs/feedback remain intact, fresh review and deploy relevant fixes to main application with idle queue.

Review focus: stale forms after another candidate review; true concurrent same-render changes;
same-size media mutation invalidates final approval; optional unset vs zero ratings;
publication cannot bypass current artifact approval; outro audio/timestamps/full QC;
existing processing snapshots remain unchanged.
