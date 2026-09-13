# Verification Document: codex-wrapper-fallback-removal

## Overview

**Feature**: codex-wrapper-fallback-removal
**SPEC.md**: `feature-docs/codex-wrapper-fallback-removal/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/codex-wrapper-fallback-removal/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task is
merged. Task-level acceptance criteria live in the task plans and are
verified inside each task's own worktree.

## Build Verification

Neither declared component has a build command (`project.components.main` and
`project.components.hooks` both declare an empty `build_command`). There is no
compilation step: the change set is a shell script, YAML values, Markdown, JSON
registries and Python test modules.

- Command: none
- Expected: n/a

## Test Verification

- Command (main): `python3 -m unittest discover -s tests`
- Command (hooks): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: both exit 0
- Coverage target: not tracked numerically in this repository. The coverage
  obligation is structural instead: every FR/NFR maps to at least one scenario
  below, and every new matcher carries a negative proof.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Stub emits a usage-limit diagnostic on stderr and exits non-zero | Exactly one recorded launch; the wrapper exits with the stub's exit code; the stub's stderr reaches the caller; no fallback marker line | Integration (subprocess) |
| TS2 | Stub emits a provider-error diagnostic on stderr and exits non-zero | Identical outcome to TS1, single launch | Integration (subprocess) |
| TS3 | Usage-limit diagnostic with the former prerequisites configured (proxy credential set, profile file present under an isolated `HOME`) | Still exactly one launch; the prerequisite gate no longer exists and configuring it changes nothing | Integration (subprocess) |
| TS4 | Switch-shaped text present ONLY on the stub's stdout | No behavioural difference from an unrelated failure; one launch; proves no stdout-driven control flow survives | Integration (subprocess) |
| TS5 | Schema-shaped reply on stdout plus a multi-line banner on stderr | Every byte of stdout content precedes every byte of stderr content in the combined output; no combined-stream redirection in the script | Integration (subprocess) |
| TS6 | Stub outlives the configured timeout (compressed via an isolated copy paired with a reduced configured value) | Exit code 124 and a stderr diagnostic naming the configured timeout in seconds | Integration (subprocess) |
| TS7 | Unrelated non-zero exit | Surfaces with its own exit code and output, no diagnostic added | Integration (subprocess) |
| TS8 | Document sweep across all four documents | Neither removed phrase appears in the wrapper header, `question-resolution.md`, `batch-mode.md` or `phase-state.md`; the chain-walk description, the routing table and the Opus escalation prose are unchanged | Integration (static, post-merge) |
| TS9 | Version consistency for both plugins | Manifest and marketplace entry agree per plugin; each is above its pre-feature baseline | Unit (static) |
| TS10 | Full run of both suites | Both exit 0 | Integration |
| TS11 | Timeout configuration sweep | Both configuration files report 540; all three invocation sites declare 600000 milliseconds; the nesting relation holds; both fenced invocation lines are unchanged | Integration (static) |
| TS12 | No-change sweep | `em-review/scripts/run_codex_exec.sh` and `feature-docs/batch-codex-autonomous-decisions/SPEC.md` are absent from the integrated change set | Integration (static + change-set check) |
| TS13 | Removed-phrase surface sweep, mechanically enumerated | Neither phrase occurs anywhere under `em-workflow/` or `em-review/`; every remaining tracked occurrence in the repository lies under `feature-docs/`, `test-docs/` or `tests/`; a forged occurrence outside those areas is rejected | Integration (static, repository-wide) |
| TS14 | Derived-pin declaration for `em-workflow/agents/codex-reviewer.md` | `tests/test_reviewer_roles_protocol.py` declares the source documents its byte-level pins are derived from, including that agent document, and still declares every test class and at least as many pinned digests as it does today | Integration (static) |

TS1–TS7 are owned by task0001's replacement module; TS11 and the em-review
half of TS12 by task0002's new module; the `batch-mode.md` / `phase-state.md`
half of TS8 and the superseded-SPEC half of TS12 by task0003's new module; TS9
by task0004's new module; TS13 and TS14 by task0005's new module. TS8 and TS12
are ALSO verified here as a union that no single task worktree can observe
(IMPLEMENTATION.md D4, D6).

### Integrated checks that belong only to this phase

1. **Removed-phrase surface sweep**: neither `whether a fallback provider
   answered` nor `The wrapper's reply may come from a fallback provider`
   occurs anywhere under `em-workflow/` or `em-review/` — the plugins' shipped
   surface, which is what the four edited documents belong to and the only
   surface a user's installed plugin ever sees. Every remaining tracked
   occurrence in the repository lies under exactly one of three areas:
   `feature-docs/` and `test-docs/` (per-feature preserved history — the
   feature documents and the TDD red/green records quote the phrases
   deliberately) and `tests/` (a test asserting a string's absence necessarily
   contains that string). An occurrence on any other path fails this check.
   This check is pinned mechanically by TS13 rather than resolved by reading:
   the areas above are the check's stated condition, not an informal
   allowance, so a future occurrence outside them is a failure and not a
   judgement call.
2. **Change-set containment**: the integrated change set, compared against the
   implement phase's base commit, is contained in the declared set — the union
   of EVERY task's `files` entries (task0001 through task0005) plus
   `feature-docs/codex-wrapper-fallback-removal/**` and
   `test-docs/codex-wrapper-fallback-removal/**`. A file that a task's declared
   edit mechanically forces to change — a pin derived from a declared document,
   such as `tests/test_reviewer_roles_protocol.py`'s digest over
   `em-workflow/agents/codex-reviewer.md` — is inside the declared set only
   when some task names it in `files`; being a mechanical consequence of a
   declared edit never makes it implicitly permitted. In particular the change
   set contains none of `em-review/scripts/run_codex_exec.sh`,
   `feature-docs/batch-codex-autonomous-decisions/SPEC.md`,
   `em-workflow/references/review-phase.md` or
   `tests/test_codex_reviewer_temp_file_isolation.py` (AC7, AC10, AC11, AC14).
3. **Marker sweep**: neither fallback marker prefix occurs anywhere in
   `em-workflow/scripts/run_codex_exec.sh`.

## Code Quality Verification

- Format: no formatter is declared for either component (`format_command` is
  empty in both). Match the surrounding style of each edited file.
- Static analysis: none declared. The suite's own structural assertions
  (standard-library-only imports, non-vacuity proofs) serve that role.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Usage-limit stub → exactly one recorded launch, exit with that launch's code | TS1 |
| AC2 | Same for a provider-error diagnostic, and with the former prerequisites configured | TS2, TS3 |
| AC3 | No run emits either fallback marker line; neither string occurs in the wrapper | TS1–TS4 plus the marker sweep above |
| AC4 | Combined output places the whole stdout before any stderr; no combined-stream redirection | TS5 |
| AC5 | Timeout → exit 124 with the diagnostic naming the configured timeout; unrelated failures surface unchanged | TS6, TS7, and TS11 for the production value of 540 |
| AC6 | Both configuration files read 540; all three invocation sites declare 600000 milliseconds | TS11 |
| AC7 | `em-review/scripts/run_codex_exec.sh` unchanged | TS12 plus change-set containment |
| AC8 | The superseded wrapper test module is gone and its replacement covers AC1–AC5 | TS1–TS7; file-absence assertion in task0001's module |
| AC9 | Neither removed phrase appears in the four documents; the four pinning tests pass against the edited text | TS8, TS10, TS13 |
| AC10 | Chain-walk text, routing table and Opus escalation prose unchanged | TS8 plus change-set containment (`review-phase.md` must not appear in the change set at all) |
| AC11 | The superseded feature's SPEC unchanged | TS12 plus change-set containment |
| AC12 | em-workflow 0.1.77 and em-review 0.5.10 in both places each | TS9 |
| AC13 | Both suites exit 0 | TS10 |
| AC14 | The temp-file isolation module passes unmodified, its pinned invocation constant untouched | TS10 plus change-set containment (the module must not appear in the change set) |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS4, TS10 |
| FR2 | task0001 | TS5, TS10 |
| FR3 | task0001 | TS6, TS7, TS10 |
| FR4 | task0002 | TS10, TS11 |
| FR5 | task0002 | TS11, TS12 |
| FR6 | task0001 | TS1, TS2, TS3, TS5, TS6, TS7 |
| FR7 | task0001, task0002, task0003, task0005 | TS8, TS10, TS13 |
| FR8 | task0003 | TS12 |
| FR9 | task0004 | TS9, TS10 |
| NFR1 | task0001, task0002 | TS6, TS11 |
| NFR2 | task0001 | TS1, TS2 |
| NFR3 | task0001 | TS4 |
| NFR4 | task0002, task0003, task0005 | TS8, TS13 |
| NFR5 | task0001, task0002, task0003, task0004, task0005 | TS10 |
| NFR6 | task0002, task0005 | TS11, TS14 |

## E2E Testing

No E2E framework is configured for this repository (`e2e_test_command` is
empty for both components), and the wrapper's real counterpart is an external
CLI backed by a paid account. The scenarios below are therefore covered by the
subprocess-level tests above rather than by an E2E runner.

## Manual Testing (E2E Not Possible)

- [ ] Against a real account that has reached its usage limit, invoke the
      wrapper once and confirm it returns within the configured timeout
      carrying the provider's own diagnostic, rather than after a multiple of
      it carrying only a timeout line. This is the defect this feature exists
      to fix and no hermetic test can observe it.
- [ ] Run one review perspective end to end and confirm the reviewer
      classifies a usage-limit failure as rate-limited, using the diagnostic
      the wrapper now passes through (NFR2).
- [ ] Confirm the Bash-tool timeout declared in each invocation site is
      actually honoured by the caller — that the tool parameter reaches the
      call, not merely the prose.
- [ ] After merging, restart Claude Code and confirm the cached plugin
      directories resolve to the new versions; the bump has no effect on an
      already-cached install until the restart.

No mockup comparison applies: the design step is `skipped` and this feature
has no user-visible surface.

## Performance / Security Verification

- NFR1: a single wrapper run does not exceed the configured 540 seconds, and
  therefore fits inside the caller's 600-second ceiling. Verified structurally
  by TS11's nesting relation plus TS1–TS7's single-launch evidence — the
  worst case is one timeout, not a multiple of one.
- NFR3: no control-flow decision reads the model-generated stdout stream.
  Verified by TS4 (a switch-shaped stdout changes nothing) and by the absence
  of any response-shape recognizer in the script.
- NFR4: no provider or model identifier and no usage-limit detection
  description exists anywhere under `em-workflow/references/`. Verified by TS8
  for the owned documents and by TS13 for the removed phrases across the whole
  shipped plugin surface.
- NFR5: both suites are hermetic — stubbed command on `PATH`, isolated `HOME`,
  no network, no real provider — and every new or edited module imports only
  the standard library. Verified by TS10 plus each module's own import check.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1–TS14) | 14 | 14 | 0 | 0 |
| Integrated phase checks | 3 | 3 | 0 | 0 |
| Success criteria (AC1–AC14) | 14 | 14 | 0 | 0 |
| Manual confirmations | 4 | 0 | 0 | 4 |
