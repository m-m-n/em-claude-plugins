# Verification Document: resume-conditions-newline-rejection

## Overview

**Feature**: resume-conditions-newline-rejection /
**SPEC.md**: `feature-docs/resume-conditions-newline-rejection/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/resume-conditions-newline-rejection/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature. Per-task
acceptance criteria live in
`feature-docs/resume-conditions-newline-rejection/tasks/task0001.md` and
`tasks/task0002.md`.

## Build Verification

- Command: none. `workflow.yaml` `project.components.main.build_command` is
  empty — this repository distributes documents, skills and scripts, and has
  no build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root, i.e. the integration worktree root)
- Expected: exit code 0, and no failure that is not already present on the
  base revision. The comparison against the base revision is what decides
  pass/fail — a pre-existing failure recorded before any edit is not a new
  failure.
- Coverage target: no coverage threshold is configured for this repository
  and none is introduced here. The suite is a document/registry conformance
  suite; coverage is expressed as requirement traceability below, not as a
  line-coverage percentage.

### Test Scenarios (TS1-TS8 from SPEC.md; TS9-TS10 added at create-plan)

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The OWN-rules text of `## Consumer constraints` states the CR/LF/TAB exemption for `resume_conditions` (new matcher, asserted against the real document) | Passes: the field name, the three exempted code points with their code-point literals, the "other than" restriction, and the explicit not-a-violation statement are all present | Unit |
| TS2 | Negative proof for TS1 — the pre-change shared bullet, used verbatim as a forged sample preceded by the OWN-rules label | Rejected by TS1's matcher, and rejected for the contradictory wording rather than for a missing anchor | Unit |
| TS3 | Non-vacuity for TS1 — the carried-over numbered constraints alone, with no OWN-rules label | Does not satisfy TS1's matcher; the matcher stays anchored on the OWN-rules label | Unit |
| TS4 | Regression — the existing own-hardening matcher against the updated document | Passes, and still requires all three shape defenses (eight keys in order, duplicate-key / eight-physical-lines, closed documented domain for `state`/`step`/`reason`) and the "carried-over consumer behaviour" labelling | Unit |
| TS5 | Regression — the updated forged partial own-rules sample | Still otherwise well-formed, and still rejected for the missing shape defenses rather than for the changed control-code-point wording | Unit |
| TS6 | Regression — `## Result format` and `## Escaping` byte-identity, the five-numbered-constraint count, and the `## Field values` `resume_conditions` pins (normalization-not-applied, presence rule, carried-in-full) | All hold unchanged; the byte-identity test passes unmodified | Unit |
| TS7 | Regression — the em-workflow version in `em-workflow/.claude-plugin/plugin.json` equals the version in the `.claude-plugin/marketplace.json` em-workflow entry and compares strictly greater than the base revision's `0.1.84` | Both assertions pass; comparison is per-component numeric | Unit |
| TS8 | Regression — the whole suite runs with `python3 -m unittest discover -s tests` using only the standard library | Exit code 0, no new failures versus the base revision, no third-party import in test code | Integration |
| TS9 | The OWN-rules introductory sentence is framed as em-workflow's own hardening rules, carries the "carried-over consumer behaviour" labelling, and holds neither a blanket "cannot fire" claim nor a count word for the number of rules | Passes against the real document | Unit |
| TS10 | Negative proof and non-vacuity for TS9 — the pre-change introductory sentence used verbatim as a forged sample carrying the OWN-rules label | Rejected by TS9's matcher; the guard shows the forged sample is otherwise well-formed | Unit |

TS9 and TS10 extend the SPEC's TS1-TS8 list: FR4 is a SPEC requirement with
no test scenario assigned in SPEC.md, and every requirement must map to at
least one verifying test. They add no scope beyond FR4.

## Code Quality Verification

- Format: none. `workflow.yaml` `project.components.main.format_command` is
  empty; no formatter is configured for this repository.
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py`
  run against the repository root — expected exit code 0. This is the
  repository's plugin-structure invariant checker and covers the manifest
  pair touched by task0002.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-A | All functional requirements FR1-FR10 are implemented and tested | The Functional Requirements Coverage table below: every FR has at least one task and at least one test |
| SC-B | All test scenarios TS1-TS10 pass | Run the test command; every scenario above is green |
| AC5 | `python3 -m unittest discover -s tests` passes with no new failures relative to the base revision | Run the suite; compare the failure set against the pre-change baseline recorded before any edit |
| AC6 | The existing own-hardening matcher and the forged partial own-rules sample reflect the new wording, and the own-hardening negative-proof class's three tests all still pass | TS4, TS5 |
| AC7 | A new positive test fails against the pre-change document text and passes against the post-change text | TS1 green against the post-change document, TS2 proving rejection of the pre-change text |
| AC8 | The byte-identity tests for `## Result format` / `## Escaping` and the five-carried-over-constraints count test pass unmodified | TS6, with the diff confirming neither test was edited |
| AC9 | `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same bumped em-workflow version | TS7 |
| SC-C | Performance goals | Not applicable — no runtime path is introduced or changed |
| SC-D | Security requirements are satisfied | See Security Verification below |
| SC-E | Documentation is complete | The SSOT is internally consistent after the change (TS6 plus the manual read-through below) |
| SC-F | Code review is completed | The review phase's disposition for this feature |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS4 |
| FR2 | task0001 | TS1 |
| FR3 | task0001 | TS4 |
| FR4 | task0001 | TS9, TS10 |
| FR5 | task0001 | TS6 |
| FR6 | task0001 | TS6 |
| FR7 | task0001 | TS4 |
| FR8 | task0001 | TS5 |
| FR9 | task0001 | TS1, TS2, TS3 |
| FR10 | task0002 | TS7 |
| NFR1 | task0001, task0002 | TS8 |
| NFR2 | task0001 | TS1, TS8 |
| NFR3 | task0001, task0002 | TS2, TS3, TS10 |
| NFR4 | task0001, task0002 | TS8 |
| NFR5 | task0001 | TS6 |

## E2E Testing

Not applicable. `workflow.yaml` `project.components.main.e2e_test_command`
is empty and the repository has no E2E infrastructure.

## Manual Testing (E2E Not Possible)

- [ ] Walk the original reproduction steps against the post-change document
      and confirm the contradiction is gone: read the `## Field values`
      `resume_conditions` bullet, then read the first OWN-rules bullet under
      `## Consumer constraints`, and confirm the two regulations are now
      compatible for the same value. This is the bug report's own
      reproduction procedure and requires human judgement about whether two
      prose statements agree.
- [ ] Confirm the normal form of a stop result has a legal representation:
      read the post-change rules and confirm that a `state: stopped` result
      whose `resume_conditions` carries a multi-line recovery procedure
      violates nothing the document states.
- [ ] Confirm no statement in `## Field values`, `## Escaping`,
      `## Result format` or `## Consumer constraints` contradicts another
      for any of the eight values (NFR5) — a whole-document read-through
      that no substring matcher can replace.
- [ ] Confirm the new OWN-rules prose reads as English consistent with the
      surrounding sections (NFR4).
- [ ] When reporting the change, state that a Claude Code restart is needed
      for the bumped plugin version to take effect
      (`.claude/rules/core-plugin-version-bump.md`).

No mockup comparison applies: the design step is `skipped` and this feature
has no DESIGN.md and no visual surface.

## Performance / Security Verification (if applicable)

- Performance: not applicable. No runtime path is introduced or changed.
- Security (input validation): the feature restates, per field, which
  decoded code points a structured-result value rejects. Verify that the
  relaxation is bounded to exactly CR (U+000D), LF (U+000A) and TAB
  (U+0009) for `resume_conditions`, and that every other terminal-control
  code point — including U+2028, U+2029 and the C0/C1 ranges — remains
  rejected (TS1, plus the manual read-through). Verify that `detail`'s
  rejection is unchanged in substance (TS4). Verify that the carried-over
  constraints for `branch` and `pr_url` are untouched (TS6).
- Security (no new attack surface): confirm no runtime script, hook or skill
  file appears in the change set — the rules stay documentation-level
  defense in depth, not executable validation.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 10 | 10 | 0 | 0 |
| Success criteria | 10 | 7 | 0 | 3 |
| Static analysis | 1 | 1 | 0 | 0 |
| Manual checks | 5 | 0 | 0 | 5 |
| Total | 26 | 18 | 0 | 8 |
