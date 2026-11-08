# Authorized source ingestion via Hermes — 08/11/2026

Owner reports missing source registry and scoped URL ingestion plus live-profile missing environment. Implement directly with tests, preserving prior reviews/jobs/secrets. Do not enable channel based on an invented authorization or copy an ID from a description without metadata verification. Supplied27-character channel ID is not canonical UC+22; verify metadata of g8Q1UxPJulc before registration. Owner authorization reference/permission pending asynchronous question.

- [x] Diagnose actual gateway environment and fix profile-scoped client credential loading without global credential bleed. Test real agent read-only.
- [x] Source registry backend: permanent canonical channel identity, name, active/pending authorization, owner reference, allowed languages/video kinds/local or external models; authenticated admin mutation and Hermes scoped read. Default deny/pending. No new public exposure.
- [x] Scoped authorized YouTube ingestion: metadata channel proof before media, canonical video ID dedup/reservation under lock with recovery of queue failures, policy checks before enqueue, persist source/video/channel/settings provenance, existing worker download path. Never auto-publish. No real ingestion until authorization supplied.
- [x] Expose sources/import/status in Hermes API and client/skill, make groups distinct from channel sources; regression tests, full suite, independent review, isolated browser flow, safe deploy. Periodic monitoring is next phase; do not silently enable recurring jobs.

Evidence: exactgatewayprocessenvclient19groups andrealHermesbareterminalexit0. SourcebackendRED→GREEN37focused, wiringRED→GREEN31focused, independentbackend13/wiring23pass; broadfinalreviewnoImportantopen. Fullsuite456passed134.73s. MetadatareadonlyverifiedcorrectchannelUCJAbkIY17zAmCTNQHH0bQoQ; authorizationreferencepending, no realjob/media permitted. Monitoringnotenabled; externalplanURLautomationunsupportedexplicit.

Deployed1f91f8d sourcecode, APIrecreated/workerrestartidle0/0, UInotrestarted. PendingGameplayrjregisteredcorrectIDrev1 (noauthorizationinvented). Remoteclient+actualHermesagent sources readexit0; productionbrowserpass. Preservation39byteidenticaljobs12v2events. Ownerauthorizationreference/scope stillrequired forlivevideo acceptance. No monitoredingest/publication activated.
- [ ] After owner supplies authorization, activate source and run real g8Q1UxPJulc job through NEEDS_REVIEW; verify source/video/candidates binding and no duplicate job.
