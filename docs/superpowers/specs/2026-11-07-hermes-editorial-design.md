# Hermes editorial workspace design

Owner requested implementation directly after choosing existing Hermes integration and model labels visible from the beginning; proceed without another design approval round.

Goal: Telegram topic/profile nopocket-content uses Hermes natural language with Content Factory as source of truth. Group candidates by confirmed source provenance across jobs/models, preserve all prior feedback, choose zero/one/many artifact-bound finals, and flex duration to story development. Selection does not fabricate an approval or publish.

Approach selected: existing Hermes handles Telegram updates, dedicated editorial profile/personality + skill invokes a private authenticated Content Factory API. Do not create a second update consumer on its bot. Separate bot remains unnecessary alternative. MCP bridge is messaging access, not the persistent runtime integration.

Comparison: models shown from outset, group by exact source fingerprint and confirmed parent provenance (never title similarity); list jobs and render identities, overlap signals and saved feedback. Final-selection revisions persist separately from candidate ratings, require expected group revision and exact candidate artifact identity. Replacement/stale render is not selected as current. Preserve independent useful clips, no forced single winner or duplicate approval.

Hermes tools: list source groups, inspect group/candidate, obtain private application deep link/video attachment, submit explicit owner feedback using existing v2 service, save selected finals. Tool outputs do not expose tokens or raw filesystem paths. Conversation ambiguity prompts clarification, ordinary chat is not automatically a review. Review action records owner identity/channel and exact artifact shown. A profile cannot claim media vision when it only saw transcript.

Duration: new configurable flexible mode within a bounded window; relevance/development/conclusion govern candidate length, target is guidance. Existing job snapshots stay unchanged. Full render+preview+QC use actual source and outro duration; destination preflight remains separate.

Install: inspect actual Hermes version, existing profile/topic conventions and skills before changing remote config. Back up changed remote files; preserve existing bot ownership, tokens, topics, sessions and unrelated config. Only report installed once observed via SSH and topic/agent checks. Current SSH/MCP connectivity is failing; no speculative remote layout changes.

Acceptance: cross-model group includes same-root jobs and prior comments; concurrent/stale final selections rejected; Telegram/API cannot bypass existing review integrity; profile tool can read live group and owner feedback reaches app; no test human reviews on real candidates; duration regressions tested, browser flow through agent-browser, no external social publishing.
