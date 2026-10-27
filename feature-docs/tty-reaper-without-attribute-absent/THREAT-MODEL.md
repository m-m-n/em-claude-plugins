# Threat Model: tty-reaper-without-attribute-absent

## Verdict
no-trust-boundary

## Rationale
Inspected SPEC.md (FR1-FR5, NFR1-NFR3) at the reduced tier (no
REQUIREMENTS.md, design skipped). The only changed file is the test module
tests/test_codex_hook_tty_reaper.py (NFR2): a test helper that temporarily
removes and restores an attribute of a module object within the same test
process, plus unit tests for it. Its inputs are module objects and attribute
names written literally in the test code; no user input, external service,
file from outside the project, other process, LLM prompt text or privilege
change is involved. The hook scripts, which do interact with other processes,
are unchanged (NFR2). task0001 declares none of the domains auth,
input-handling, external-io or data-persistence, so no depth adjustment or
boundary reconciliation applies.
