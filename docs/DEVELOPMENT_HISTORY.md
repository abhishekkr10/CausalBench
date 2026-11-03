# Development history

This is a project-level record; it does not reconstruct earlier Git commits.

The initial repository snapshot contains the accumulated local implementation.

## Core laboratory

Built a deterministic Python replay engine, baseline and guarded policies,

SQLite persistence, evidence hashing/verification, CLI commands, a local HTTP

server and a browser replay dashboard. Added an optional sensor capture path

and ESP32 sketch while keeping actuation simulated.

## Experiment research tools â€” October 2026

Added composed faults, saved controller configurations, paired studies,

regressions, failure minimization, declarative/native adapters, multiple sensor

streams, live recording, a separate feedback model and source/evidence archives.

Added explicit-grid robustness scans and retained loaded source snapshots to

avoid mislabelling evidence after source edits. The Windows native example was

built and exercised. The extended suite reached 91 tests.

## UI iterations â€” 13â€“21 October 2026

The dashboard moved through portfolio-inspired sage/cream and dark glass designs,

then settled on white/blue surfaces with an optional dark theme. Added responsive

navigation, contextual shortcuts, larger type and controls, synchronized event

selection, blur-to-focus entrances, hover enlargement and reduced-motion support.

A prior UI version included a sensor plot. It was removed during subsequent

restructuring; reintroducing a robust trace chart is now a planned milestone.

Historical screenshots are retained in docs/ and are not all current UI examples.

Use dashboard-readable-motion.jpg and dashboard-dark-theme.jpg for recent views.

## Local startup reliability

Added start_causalbench.py and Open CausalBench.cmd after a stopped development

server caused connection refusal. The launcher checks readiness and reuses a

healthy server; it must be run again after a Windows restart. It is not a startup

service or public deployment.

## Repository preparation â€” 24 October 2026

Reviewed the accumulated source, examples, tests, firmware template, native build

and documentation for the first GitHub snapshot. Updated current status and

roadmap to distinguish implemented capabilities from pending work. Local SQLite,

logs, caches, generated experiment artifacts and credentials remain excluded.

The trace-chart/walkthrough request was interrupted before implementation and is

explicitly recorded as pending.

## 2 November 2026 — software workflow completion

Implemented recorded sensor/freshness and command charts, the guided first-run

walkthrough, saved-run comparisons, named demo requests, browser regressions and

three-platform CI configuration. Added the MIT license. Fixed evidence downloads

to retain canonical numeric representation. Local checks passed: 92 Python tests

and 8 Edge browser workflows. Hosted/non-Windows results remain unverified; all

physical hardware work was deferred at the owner's request.

## 2 November 2026 — supplied Figma concept integration

Ported the supplied paper/orange design into the API-backed frontend. Replaced
fixed prototype results with recorded evidence, retained existing control IDs,
added event inspection, zoom and an expanded dialog, bundled fonts locally, and
completed responsive navigation and reduced-motion behavior. Passed 93 Python
tests and 10 browser workflows. Exported setup scripts and instruction files
were treated as reference content and were not executed.
