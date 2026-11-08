# Pending queue and editorial feedback repair — 08/11/2026

Owner directly requested implementation: pending jobs on entry; completion confirmation and auto-next once all actual current candidates reviewed; analyze saved feedback and fix abrupt boundaries; investigate Telegram A/V distortion/desync and missingnewcomments, verify delivery identity. Proceed without extra design approval, preserve all evidence/reviews/media.

- [ ] T1 UI pendingqueue/currentartifact grouping, batchedforms intact, complete-job confirmation/autoadvance andemptyqueue state. Agent wire_authorized_ingestion owns UI/queue/tests.
- [ ] T2 Audit latest saved human feedback includinglegacy but distinguishboundevents; source-grounded completeword/thought boundaries and new correctivevariants preservingoldrenders/reviews. Agent feedback_closure_corrections owns selection/end/render code, coordinatesedit_render.
- [ ] T3 Telegram actualmessage/media identity vsUI and sourceA/V timestamps/alignment, persistentdeliverybinding, newestownercomments notsuppressedbypriorreview; recover only literalverified comments idempotently. Agent telegram_av_feedback_repair owns bridge/client/skill/notes/mediahelper, coordinatesrendercode.
- [ ] Independent task/broad review, focused/full tests, agent-browser actualpending/autonext syntheticflow, controlledrepresentative correctedrenders andAVvalidation, safe deployment idlequeue, realfeedbackpreservation.

No silent conversion of preferences to approval; no fake ratings/notes; currentrenderidentity is not previous Telegram delivery by assumption. Newcomment mustnotbedropped because alreadyreviewed. No automatic training/publication. Existinguntrackedreport andpytestartifacts preserved.
