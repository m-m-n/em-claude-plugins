# Threat Model: scripts-test-bytecode-suppression

## Verdict
no-trust-boundary

## Rationale
Inspected: REQUIREMENTS.md and SPEC.md (FR1–FR3, NFR1–NFR4), tier `full`,
and the four tasks (task0001–task0004), each declaring the domains
`config-infra` and `external-io`. The change is test code under `tests/`
only. What it handles: repository-owned scripts and repository-owned test
modules loaded by file path into the same test process, probe files the
tests themselves write into their own temporary directories, and one child
process (`report-name-entry.py`, a repository-owned script) launched by the
test as the same user with arguments the test builds. No user or external
input, no network, no file from outside the project, no text interpolated
into an LLM prompt and no privilege change is involved, so nothing crosses
between parties of different trust. The `external-io` domain on all four
tasks refers to the file-system side effect being suppressed (bytecode
cache writes beside the scripts), which stays inside that single trust
domain; this is why no task's files appear in a `Boundary files` line.
SPEC.md's Security Considerations likewise state "Not applicable".
