# Threat Model: cleanup-guard-cap-sync-test

## Verdict
no-trust-boundary

## Rationale
Inspected: SPEC.md (reduced tier; REQUIREMENTS.md and DESIGN.md are not
produced) and the single task task0001 (domains: input-handling, standard
depth). The feature adds unit-test code to
`tests/test_failed_run_cleanup_guard.py` that reads
`em-workflow/skills/develop/SKILL.md` as text, loads
`em-workflow/hooks/failed-run-cleanup-guard.py` through the module's existing
loader, and compares four numbers with two constants (FR1-FR5). Both sources
are project-tracked files at the same trust level as the test code itself:
nothing arrives from a user, an external service, another process, a file
from outside the project or an LLM prompt, and no privilege changes. The
values read are only compared with integers and echoed in assertion
messages; they are never executed, used as a path or passed to a command,
and the tests write no file (NFR2).

task0001 declares `input-handling` for the parsing robustness FR4 requires
(exactly-once matching, line-break normalization). The parsed text is
project-authored content, not input from another party, so it forms no
trust boundary and no `Boundary files` line exists for that task.
