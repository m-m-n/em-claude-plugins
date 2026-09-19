# Verification Document: batch-structured-result-output

## Overview

**Feature**: batch-structured-result-output /
**SPEC.md**: `feature-docs/batch-structured-result-output/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/batch-structured-result-output/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature.
Per-task acceptance criteria live in `tasks/taskNNNN.md` and are not repeated
here.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. This
  change is Markdown, Python test modules and two JSON manifests; there is no
  build step.
- Expected: not applicable. The JSON manifests' parseability is covered by
  TS10 instead.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no new failures and no new errors relative to the
  base revision. Baseline: six failures are already present at the implement
  base commit `95c23ed` and are not produced by this feature; "no new
  failures" is measured against that set.
- Coverage target: not measured — this repository tracks no coverage
  percentage. The traceability target is the Functional Requirements Coverage
  table below: every FR/NFR maps to at least one test scenario.
- **Skip policy**: the conformance module of TS2 must run with ZERO skipped
  tests. A skipped conformance run is a FAILED verification item, not a pass
  (IMPLEMENTATION.md D6). Before running the suite, confirm the YAML parser
  the conformance module requires is importable; if it is not, install it into
  the verification environment and re-run.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | A representative structured result for each `state` value is parsed under a strict YAML load | Exactly one mapping; the eight keys of SC1 in SC1's order, each once; every value a string; exactly eight physical lines | Unit |
| TS2 | Each of the 14 adversarial source values is escaped per the canonical rule and parsed by the real parser | Each round-trips to a value equal to the source, character for character, in every one of the eight key positions | Unit |
| TS3 | A `detail` source with CR/LF/TAB and space runs; a `resume_conditions` source with newlines, indentation and trailing spaces | Normalization then escaping on `detail` (no newline escape in the result); escaping only on `resume_conditions` (newline escapes present, indentation and trailing spaces preserved) | Unit |
| TS4 | The ten derivation sites of IMPLEMENTATION.md's Canonical derivation outcomes table, table-driven | `feature`, `branch`, `pr_url` and `resume_conditions` take exactly the documented value at each site; nothing is guessed from a task description or an existing branch | Unit |
| TS5 | The rejected combinations, the `branch` / `pr_url` character constraints applied after parsing, and the 64 KiB boundary | Each constraint has an accepting case and a rejecting case; the size bound is evaluated on encoded UTF-8 bytes | Unit |
| TS6 | A recursive sweep of every file below `em-workflow/` for the removed prefix literal, with no hand-maintained allowlist | The literal occurs in no file under `em-workflow/`; the non-vacuity guard proves the sweep read a non-trivial number of files | Integration |
| TS7 | Structural extraction of the SSOT's `reason` domain and its stop-point coverage table | Twelve documented values; eleven coverage rows binding eleven codes; `context_budget_reached` absent from the coverage table, present in the domain marked never-emitted; the named-exception sentence present. A forged domain adding the twelfth code as a coverage row is rejected | Integration |
| TS8 | Retargeted absence guards over `batch-mode.md`, `skills/develop/SKILL.md` and `implement-phase.md`, plus a positive matcher over the rewritten disjointness paragraph | No member of IMPLEMENTATION.md SC5 occurs in any of the three files; the rewritten paragraph names `EM_WORKFLOW_PROGRESS:`, establishes non-confusability without naming a terminal prefix, and preserves the absence signal; the new matcher carries its own negative proof and non-vacuity guard | Integration |
| TS9 | Every "## Reporting" audit item is asserted present in full within its assigned value; forged pointer-only and count-only samples | Full-content sample accepted; count-substituted, pointer-only and misplaced-stop-recovery samples each rejected; no aggregated report path appears in the feature's declared change set | Integration |
| TS10 | Both version manifests are read and compared | The two em-workflow versions are equal and strictly greater than `0.1.82` under dot-separated numeric comparison; the `em-review` entry is unchanged | Unit |
| TS11 | Whole-suite regression run plus the hook test runner | `python3 -m unittest discover -s tests` exits 0 with no new failures; `python3 em-workflow/hooks/tests/run-destructive-guard.py` exits 0 (unaffected, run as a no-regression check per `.claude/rules/hook-tests.md`) | Integration |
| TS12 | A real `--batch` run and a `--batch --once` run, stdout captured, offered to the consumer's parser | The consumer accepts the result; the run does not end in a schema-rejection exit 1 | Manual |
| TS13 | `skills/develop/SKILL.md`'s statement of the terminal-turn message boundary (IMPLEMENTATION.md SC10), and the two modules that pinned the pre-rework wording | The rule is stated over EVERY turn on which the run reaches a terminal state — the last assistant message is the structured result and nothing else, every prose report precedes it — not for the cap-reached run alone; the stop report's cause / affected paths / recovery guidance are also required in full inside the result's own values; a forged section stating the rule for the cap-reached run alone is rejected while being otherwise well formed; `tests/test_batch_quiet_output_discipline.py` is green against the current `batch-mode.md` and no longer names the removed wording | Integration |
| TS14 | Structural extraction of the SSOT's hardened value rules (IMPLEMENTATION.md SC11) | `## Responsibility boundary` says "beyond paths"; `## Field values` states the in-full loading rule with its single secret-portion placeholder exception, the `detail` item-delimiter and non-verbatim disclosure, the slug pattern literal or its named owner, and non-whitespace `resume_conditions` presence; `## Consumer constraints` defines exactly one outcome for the 64 KiB / in-full collision and states the control-code-point, key-sequence, duplicate-key and closed-domain checks under a label separating them from FR14's five carried-over constraints; `## Escaping` and `## Result format` are byte-identical to their pre-rework text; TS7's twelve-value / eleven-row extraction still passes; each new matcher rejects a forged section that is otherwise well formed | Integration |
| TS15 | The conformance guards' own integrity (IMPLEMENTATION.md SC12) | Every executable copy of the escaping rule is asserted equal to the SSOT's `## Escaping` table and residual ranges, rejecting a forged copy with a dropped row and one with a dropped residual range; no sample or baseline value lies outside the SSOT's closed domains; the `completed` baseline carries `step: retrospect` (FR13); the literal `awaiting_user_input` is absent; each rejection case still yields exactly one rejection reason; both modules run with zero skipped tests | Unit |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty.
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py`
  against the repository root, exit code 0. This is the repository's existing
  plugin-structure check and must stay green after the version bump.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-A | All functional requirements FR1-FR22 are implemented | The Functional Requirements Coverage table below, every row non-empty on both sides |
| SC-B | All acceptance criteria AC-1 through AC-13 hold | AC-1..AC-5 via TS1-TS5; AC-6 via TS5 and TS12; AC-7 via TS6; AC-8 via TS7; AC-9 and AC-11 via TS8; AC-10 via TS9; AC-12 via TS10; AC-13 via TS11 |
| SC-C | All test scenarios TS1-TS12 pass, TS12 performed manually | The suite run plus the manual checklist below. TS13-TS15 were added by review round 1's rework and are verified by the same suite run |
| SC-D | `python3 -m unittest discover -s tests` passes with no new failures | Compare the failure set against the base revision's run |
| SC-E | The two manifests carry the same bumped em-workflow version, `em-review` untouched | TS10 |
| SC-F | The literal `EM_WORKFLOW_TERMINAL:` occurs nowhere under `em-workflow/` | TS6 |
| SC-G | No runtime dependency or generated artifact is added under `em-workflow/` | Inspect the merged diff: every added file is under `tests/`; the only changes under `em-workflow/` are to the three documents and `plugin.json` |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0008 | TS7, TS6, TS14 |
| FR2 | task0001, task0004, task0007 | TS1, TS12, TS13 |
| FR3 | task0001, task0004 | TS1, TS12 |
| FR4 | task0001, task0004 | TS1 |
| FR5 | task0001, task0004, task0009 | TS2, TS15 |
| FR6 | task0001, task0004 | TS1 |
| FR7 | task0001, task0004 | TS3 |
| FR8 | task0001, task0004 | TS3 |
| FR9 | task0001, task0005, task0008 | TS4, TS14 |
| FR10 | task0001, task0005 | TS4 |
| FR11 | task0001, task0005 | TS4 |
| FR12 | task0001, task0005, task0008 | TS4, TS14 |
| FR13 | task0001, task0009 | TS7, TS15 |
| FR14 | task0001, task0004, task0008 | TS5, TS12, TS14 |
| FR15 | task0001, task0009 | TS7, TS15 |
| FR16 | task0001 | TS6 |
| FR17 | task0002, task0003, task0005, task0007, task0008 | TS9, TS13, TS14 |
| FR18 | task0002 | TS8 |
| FR19 | task0002 | TS8 |
| FR20 | task0002, task0003, task0007 | TS8, TS13 |
| FR21 | task0006 | TS10 |
| FR22 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS11, TS13, TS14, TS15 |
| NFR1 | task0001, task0002, task0003, task0007, task0008 | TS8, TS13, TS14 |
| NFR2 | task0001 | TS2 |
| NFR3 | task0004, task0009 | TS2, TS15 |
| NFR4 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS11, TS13, TS14, TS15 |
| NFR5 | task0001, task0008 | TS7, TS14 |
| NFR6 | task0001, task0002, task0007 | TS8, TS13 |
| NFR7 | task0001, task0002, task0003, task0006 | TS9, TS11 |

## E2E Testing

No E2E framework exists in this project
(`project.components.main.e2e_test_command` is empty; SPEC A7). The
end-to-end behaviour — a real batch run's stdout accepted by the external
consumer — is covered by the manual section below instead.

## Manual Testing (E2E Not Possible)

- [ ] M1 (TS12, AC-1): Launch a real `--batch` run of any feature, capture the
      run's stdout, and confirm the final assistant message parses as exactly
      one eight-key mapping under a strict YAML load, with nothing before or
      after it.
- [ ] M2 (TS12, AC-6): Launch a real `--batch --once` run, capture stdout, and
      confirm the consumer's parser accepts the result — specifically that the
      run does not end with a schema rejection naming a missing key, which is
      the defect this feature fixes.
- [ ] M3 (AC-10): For a stopped run, read the emitted `detail` and
      `resume_conditions` and confirm every "## Reporting" audit item appears
      in full, with no item reduced to a count or a bare pointer.
- [ ] M4 (D6): Before recording the suite run as passed, confirm the
      conformance module reported zero skipped tests. A skip means the YAML
      parser was missing; this item is FAILED until the parser is installed
      and the suite re-run.
- [ ] M5 (SC-G): Read the merged diff and confirm no file was added under
      `em-workflow/` and no runtime dependency was introduced there.

## Performance / Security Verification

- FR14 size bound: the whole result document is at most 64 KiB encoded UTF-8 —
  covered by TS5's boundary cases. No other performance requirement applies.
- NFR5 confidentiality: the result carries no confidential information beyond
  paths across all four of `detail`, `resume_conditions`, `branch` and
  `pr_url`. Verified by reading the SSOT's `## Responsibility boundary`
  section (TS7) and, in M1/M3, by inspecting a real run's emitted values.
- FR14 input validation: `branch` and `pr_url` carry no line terminator and no
  terminal-control code point, rejected AFTER parsing — covered by TS5.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 15 | 14 (TS1-TS11, TS13-TS15) | 0 | 1 (TS12) |
| Success criteria | 7 | 6 (SC-A..SC-F) | 0 | 1 (SC-G) |
| Manual checklist | 5 | 0 | 0 | 5 (M1-M5) |
| Static analysis | 1 | 1 | 0 | 0 |
