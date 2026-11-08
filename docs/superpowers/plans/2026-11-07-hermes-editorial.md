# Hermes Editorial Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install nopocket-content in existing Hermes and make cross-job editorial review and final selection usable from Telegram and the application.
**Architecture:** Existing Hermes owns Telegram; scoped editorial skill calls private Content Factory API. Source comparison and immutable selection events live in application, no publication transport.
**Tech Stack:** Python, Streamlit, existing JSON persistence/locks/API, installed Hermes profile/skills.
**Spec:** docs/superpowers/specs/2026-11-07-hermes-editorial-design.md

## Global constraints
Preserve all data/settings/reviews and unrelated profiles. Models visible. No second Telegram update consumer. No social publishing. No speculative successful installation. New duration settings only affect new jobs.

## Review focus
Stale artifact/revision, same source across parallel model jobs, root identity changing when jobs added, feedback attribution, private media links, duration snapshot compatibility, remote configuration preservation.

- [x] T1 Source comparison + persistent artifact-bound zero/one/multiple final selection service and Streamlit panel; tests RED/GREEN. Own app/source_review.py, app/source_review_ui.py, app/ui.py, tests/test_source_review*.py. Expose list_groups(), get_group(group_id), select_finals(group_id, request).
- [x] T2 Flexible bounded story-duration controls through settings/proposals/timeline/render contracts; focused tests RED/GREEN and compatible old jobs. Own app/job_settings.py, app/ui_settings.py, app/ranker.py, app/core.py and relevant duration validators/contracts/tests. Do not edit API or app/ui.py.
- [ ] T3 Private Hermes API/client, personality and skill; runtime discovery, backup and install profile/topic nopocket-content using actual supported conventions. Controller owns app/api.py, integrations/hermes, tests/test_hermes_api.py, docs. SSH/MCP recovery while independent tasks proceed.
- [ ] Task reviews, broad final review, full suite, agent-browser isolated flow, production data preservation and safe deployment. Verify real Hermes topic+tools if host reachable; otherwise clearly retain installation as incomplete.

Ruling: user's direct implementation instruction supersedes further brainstorming gates. Reuse current isolated worktree; preserve preexisting untracked report and pytest artifacts. SSH refused and MCP Transport closed at start, local work proceeds while user checks host.

Taskreviews: source modelvisibility/merge reconciliation resolved (RED2→GREEN42); actualfallbackprovenance added. Duration windowcoverage/form-reactivity resolved (RED→GREEN48). Hermes sharedtoken andnoteintent resolved (RED2→GREEN17). Broadreview foundnoadditionalImportant. Fullsuite426passed120.35s; isolatedagent-browserpassed2/1/0selections andflexible120input. SkillquickvalidatorpassedUTF8. T3remoteinstallstillblockedSSH/MCP; bridge disabled pendingverifiedruntime.

Final migration safeguard: RED→GREEN8 UItests, existingselected_job retainsindividualworkspace/commentdraft; new sessionsdefaultcomparison. Finalfreshsuite427passed126.23s. Runtime SSH triedhostname, currentLANIPv4, knowntrustedhistoricalIPv4/TailscaleIP andIPv6: refused/timedout; MCPTransportclosed. No remoteconfigmodified; installremainsopen.
