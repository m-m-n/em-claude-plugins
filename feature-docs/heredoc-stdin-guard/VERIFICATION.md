# Verification Document: heredoc-stdin-guard

## Overview

**Feature**: heredoc-stdin-guard
**SPEC.md**: `feature-docs/heredoc-stdin-guard/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/heredoc-stdin-guard/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature. Per-task
acceptance criteria live in `feature-docs/heredoc-stdin-guard/tasks/`. The
feature has exactly one task, task0001 (IMPLEMENTATION.md D2).

Scenario identifiers here are written `TS-n` and correspond one-to-one with
SPEC.md's `TSn` for n = 1..9 (SPEC TS1 is TS-1 here, and so on). TS-10 through
TS-14 are added by this document to give every non-functional requirement and the
version bump a verifiable item; they introduce no new implementation scope beyond
the file set declared for task0001.

## Build Verification

- Command: none. `project.components.main.build_command` is empty in
  workflow.yaml — this feature adds interpreted scripts and JSON manifests, so
  there is no build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Supplementary command: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: exit code 0 from both; both new test modules (the guard contract tests
  and the version-bump module) are discovered and their cases run.
- Coverage target: no numeric target is set for this repository. The coverage
  obligation is behavioural instead: every branch of the guard's decision flow
  (rewrite, each non-target reason, each fail-open reason) is exercised by at
  least one case below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | A Bash event whose command writes a file through a quoted heredoc | One object on standard output whose updated-input command begins with the cut-off token followed by the original command text; every other tool-input field reproduced unchanged; exit 0 | Unit |
| TS-2 | A Bash event where a heredoc and a following stdin-reading command coexist in one call (the stdin reader stood in for by a harmless placeholder) | Rewritten identically to TS-1 | Unit |
| TS-3 | A Bash command with no heredoc at all | Empty standard output, exit 0 | Unit |
| TS-4 | A Bash command whose only candidate operator is a here-string | Empty standard output, exit 0 — a here-string is never mistaken for a heredoc | Unit |
| TS-5 | A command already beginning with the cut-off token, and a command whose first statement already redirects its standard input | Empty standard output in both cases; re-feeding the guard its own output never yields a doubled token | Unit |
| TS-6 | Input that is not well-formed, an event with no command, an empty command, a non-text command, and a non-Bash tool name | Empty standard output and exit 0 in every case | Unit |
| TS-7 | The rewritten command from TS-1 executed in a real shell against a temporary directory | The file written by the heredoc matches the original body byte-for-byte (content, interior newlines, terminator); nothing outside the temporary directory is touched | Integration |
| TS-8 | With the plugin installed at the bumped version and the guard registered, run the SPEC's reproduction procedure once: one Bash call containing a heredoc followed by a stdin-reading CLI | The CLI completes instead of waiting on standard input; its CPU time advances past zero | Manual |
| TS-9 | The full test suite and the destructive-guard case harness after the registration and manifest changes | Both pass; the suite includes the new guard test module, the new version-bump module, and the pre-existing plugin version parity check | Regression |
| TS-10 | Static reading of the guard's own source | Every imported module resolves to the Python standard library; no other process is started, no network connection is opened, no file is written, nothing is written to standard error | Static |
| TS-11 | Decision latency of the guard over the TS-1..TS-6 payloads, and the timeout registered for its entry | Each decision completes far inside the registered 10-second timeout; the registered timeout is 10 seconds | Unit + Static |
| TS-12 | The PreToolUse Bash matcher array and the feature's change set | Exactly seven entries; the seventh is the new guard; the first six are unchanged in order, command, timeout and status message; no file outside the em-workflow plugin, the repository-root marketplace manifest and the repository-root test directory is modified; no reference to the undocumented feature flag is introduced | Unit + Manual |
| TS-13 | Every guard invocation across the whole test corpus | Standard output never carries a permission-decision member; the exit status is 0 every time | Unit |
| TS-14 | The new version-bump module run against the merged tree | Both manifests parse as JSON; each reports an em-workflow version of the form `0.1.<patch>` with patch strictly greater than 72; the two version strings are identical; each of the module's two matchers rejects its forged counter-sample, and each forged sample is itself well-formed | Unit |

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty in
  workflow.yaml; formatting is verified by review rather than by a command.
- Static analysis: none configured. TS-10's source reading and the security
  review perspective stand in for it.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1–FR9 implemented and tested | The requirements coverage table below; every row has at least one task and one scenario |
| SC-2 | TS-1 through TS-9 pass | Run the test command and the destructive-guard harness; perform TS-8 manually |
| SC-3 | AC1 / AC2: the updated input is applied in the real environment and the stdin-reading CLI completes | TS-8 |
| SC-4 | AC9: the PreToolUse Bash array has seven entries, the seventh is the new guard, the first six match their pre-change content | TS-12 |
| SC-5 | AC10: both manifests carry the same bumped em-workflow version | TS-14, plus the pre-existing parity check inside TS-9 |
| SC-6 | AC8: the full suite passes and includes the new guard test file | TS-9 |
| SC-7 | NFR1–NFR6 satisfied | TS-10, TS-11, TS-12, TS-13 |
| SC-8 | Code review completed | The review phase's own result |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6, TS-8 |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| FR3 | task0001 | TS-1, TS-2, TS-7, TS-8 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-1 |
| FR6 | task0001 | TS-6 |
| FR7 | task0001 | TS-8, TS-9, TS-12 |
| FR8 | task0001 | TS-9 |
| FR9 | task0001 | TS-14, TS-9 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-11 |
| NFR4 | task0001 | TS-12 |
| NFR5 | task0001 | TS-13 |
| NFR6 | task0001 | TS-12 |

## E2E Testing

No E2E framework exists in this project and none is introduced
(`project.components.main.e2e_test_command` is empty). SPEC.md's TS8 is an
end-to-end confirmation that can only be performed by hand against a running
Claude Code; it is carried in the manual section below rather than here.

## Manual Testing (E2E Not Possible)

- [ ] TS-8: the real-environment confirmation. Preconditions: the merged feature
      is installed, the plugin cache has been refreshed to the bumped version
      (which requires a Claude Code restart), and the stdin-reading CLI named in
      SPEC.md is available on the machine. Run the SPEC's reproduction procedure
      once and observe that the CLI completes and its CPU time advances. If it
      does not, SPEC A4 pre-authorises adjusting the hook's output shape or its
      position in the matcher array; route that through rework rather than
      accepting a failed item.
- [ ] TS-12 (change-set half): read the merged diff and confirm nothing outside
      the em-workflow plugin, the repository-root marketplace manifest and the
      repository-root test directory changed, and that the user's global hooks
      directory was not touched.

AC10 (both manifests carrying the same bumped version) is no longer a manual
read: TS-14's module asserts it automatically.

No mockup comparison item applies: the design step is `skipped` for this feature
and there is no DESIGN.md.

## Performance / Security Verification

- NFR3 (performance): each decision completes far inside the 10-second timeout
  registered for the hook entry. Verified by TS-11; no benchmark harness is
  added.
- NFR2 (security): the decision is static reading only — no other process is
  started, no network connection is opened, no file is written. Verified by
  TS-10 and by the security review perspective.
- NFR5 (availability): a misdetection can never stop a tool call, because a
  permission decision is never emitted. Verified by TS-13.
- Input validation: every malformed or unexpected payload ends with no output
  and exit 0. Verified by TS-6.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Functional (FR1–FR9) | 9 | 8 | 0 | 1 (FR7's real-environment half) |
| Non-functional (NFR1–NFR6) | 6 | 4 | 0 | 2 (NFR4/NFR6 change-set half) |
| Test scenarios (TS-1..TS-14) | 14 | 12 | 0 | 2 (TS-8, TS-12 change-set half) |
| Success criteria (SC-1..SC-8) | 8 | 6 | 0 | 2 (SC-3, SC-4) |
