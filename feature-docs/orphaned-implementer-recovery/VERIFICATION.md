# Verification Document: orphaned-implementer-recovery

## Overview

**Feature**: orphaned-implementer-recovery
**SPEC.md**: `feature-docs/orphaned-implementer-recovery/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task has
merged. Per-task acceptance criteria live in the task plans and are not
repeated here.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. The
  changed artifacts are Python scripts, a Python hook, Markdown documents
  and two JSON manifests; there is no build step.
- Expected: the two JSON manifests parse (covered by TS-11).

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no errors, no skipped scenario from the table below.
- Coverage target: no coverage threshold is defined for this repository.
  Scenario coverage in the table below is the acceptance measure.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Proven orphan, end to end with both real helpers: journal final event `launched`, task worktree and branch present, agent index session identity differs from the current session, that session's transcript carries no activity at or after the current session's start | Exactly one `failed` line carrying reason `orphaned` is appended for the task; no other line changes | Integration |
| TS-2 | Idempotency: the journal helper is invoked twice in the same state | The second invocation appends nothing and reports the terminal no-op; a single `failed` line remains | Unit |
| TS-3 | Residual degradation, three cases: (a) the agent index entry carries no session identity, (b) the recorded identity equals the current session, (c) the transcript is unreadable or carries activity at or after the current session's start | The journal is byte-identical in all three cases; each reports its own residual reason code | Unit |
| TS-4 | Downstream convergence: a launch of the same task after `failed` (reason `orphaned`) was recorded | The launch guard permits it and `launched` is appended; it is not denied | Integration |
| TS-5 | Path containment: an agent index entry carrying a malformed session identity (path separator, dot segment, empty, over-length) | Nothing outside the resolved transcripts directory is opened, the journal is not written, and the outcome is residual | Unit |
| TS-6 | Backward compatibility: an existing agent index entry with no session identity | Stop-side resolution behaviour — match, ambiguity refusal, staleness, containment — is unchanged | Unit |
| TS-7 | Journal append discipline (NFR2): symbolic-link journal path, absent journal file, absent parent directory, and two contending invocations | The link is refused; neither file nor directory is created; at most one `failed` line is appended and never a partial line | Unit |
| TS-8 | Hook fail-open (NFR3): hook input with the session identity absent, of the wrong type, or failing validation | The agent index entry is still appended, without the field, and the hook exits 0 | Unit |
| TS-9 | Session identity validation (FR6): a UUID-like identity versus identities carrying separators, dot segments, empty values and over-length values | The valid one is accepted; every invalid one is rejected before any path is assembled | Unit |
| TS-10 | Documentation constants (FR7, FR8, NFR7): the rewritten I.2.b Recovery / Residual block, the Supporting-cast journal-write rule, the Stale-`launched` caveat and the Agent index writer bullet | The suite's verbatim constants match the new text, and the rule appears in exactly one owning section with citations elsewhere | Unit |
| TS-11 | Version consistency (NFR6): `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` | Both parse, declare the same version, and that version is higher than at the feature's base commit | Manual |
| TS-12 | Dependency and isolation constraints (NFR4, NFR5): the whole suite under the project test command | It passes with only the standard library available, all new tests live in repository-root `tests/` as `test_*.py`, and no test reads or writes real `~/.claude` state | Integration |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty.
- Static analysis: none declared for this repository.
- Regression command (a hook file changed):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` — expected exit
  code 0, no new ask/deny classifications.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-A | FR1–FR9 are implemented and tested | The requirements coverage table below; every row names at least one task and one scenario |
| SC-B | NFR1–NFR7 are satisfied | TS-3, TS-5 (NFR1), TS-7 (NFR2), TS-8 (NFR3), TS-12 (NFR4, NFR5), TS-11 (NFR6), TS-10 (NFR7) |
| SC-C | TS-1 – TS-6 pass under `python3 -m unittest discover -s tests` | Run the test command; TS-1 and TS-4 exercise the real helper pairing after both scripts have merged |
| SC-D | AC-1 – AC-6 of REQUIREMENTS.md are met | AC-1 → TS-8 and the entry-shape assertions of TS-1; AC-2 → TS-1; AC-3 → TS-4 plus the I.2.c text checked by TS-10; AC-4 → TS-3 and TS-5; AC-5 → TS-10; AC-6 → TS-1, TS-2, TS-3, TS-4 |
| SC-E | The SSOT documents are updated under the cite-not-restate discipline | TS-10, plus the manual read-through below |
| SC-F | The plugin version is bumped in both locations | TS-11 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6 |
| FR2 | task0003 | TS-1, TS-3 |
| FR3 | task0002 | TS-1, TS-2, TS-7 |
| FR4 | task0002, task0004 | TS-4 |
| FR5 | task0003 | TS-3, TS-5 |
| FR6 | task0003 | TS-5, TS-9 |
| FR7 | task0004 | TS-10 |
| FR8 | task0004 | TS-10 |
| FR9 | task0001 | TS-6 |
| NFR1 | task0002, task0003 | TS-3, TS-5 |
| NFR2 | task0002 | TS-7 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001, task0002, task0003, task0004 | TS-12 |
| NFR5 | task0001, task0002, task0003, task0004 | TS-12 |
| NFR6 | task0004 | TS-11 |
| NFR7 | task0004 | TS-10 |

## Manual Testing (E2E Not Possible)

No E2E framework is configured for this repository
(`e2e_test_command` is empty), and a real develop run is explicitly not
required as a verification method (NFR4). The following need human
judgement:

- [ ] The transcripts directory derivation (IMPLEMENTATION.md D1) produces
      the directory name that actually exists under `~/.claude/projects/`
      for this repository's absolute path — read-only inspection, no state
      touched.
- [ ] The marker-based current-session resolution (D2) finds the current
      session's transcript when tried once from a real session — read-only.
- [ ] The rewritten SSOT text reads as one owning section with citations
      elsewhere, with no rule duplicated (NFR7) — a reviewer read-through of
      `implement-phase.md`, `workflow-schema.md` and `em-workflow/README.md`.
- [ ] TS-11: both manifests declare the same version and it is higher than
      at the feature's base commit; note in the report that the change takes
      effect only after a Claude Code restart.

## Security Verification

- Session identity validation (FR6): TS-9 — the value is validated before it
  is used as a path element.
- Path containment (FR6): TS-5 — the assembled transcript path is confirmed
  to stay inside the resolved transcripts directory, and under
  `~/.claude/projects/` when the default derivation is used.
- Symlink refusal and no directory creation (NFR2): TS-7.
- Fail-safe default (NFR1): TS-3 and TS-5 — every unproven condition leaves
  the journal untouched; there is no path on which doubt produces a write.
- Narrow write authority (NFR1): the journal helper rejects any reason
  outside the closed set (task0002 AC-3).
- Test isolation (NFR5): TS-12 — no test reads or writes real `~/.claude`
  state.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 12 | 11 | 0 | 1 |
| Success criteria | 6 | 5 | 0 | 1 |
| Requirements | 16 | 16 | 0 | 0 |
| Manual checks | 4 | 0 | 0 | 4 |
