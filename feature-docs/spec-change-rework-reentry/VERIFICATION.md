# Verification Document: spec-change-rework-reentry

## Overview
**Feature**: spec-change-rework-reentry / **SPEC.md**: `feature-docs/spec-change-rework-reentry/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/spec-change-rework-reentry/IMPLEMENTATION.md`

## Build Verification
- Command: `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0, no errors

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured; the changed artifacts are Markdown protocol
  documents, and coverage is judged by the scenario table below (every
  scenario automated where marked Unit / Integration)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Extract step 2 of the SPEC-change transition from `rework-task-synthesis.md` Section 10, `contracts/rework-planner-contract.md` and `agents/rework-planner.md` | Each names `verify` among the steps set to `pending` (whitespace-normalised); each keeps five numbered steps; the pre-change three-step wording fails the matcher | Unit |
| TS-2 | Extract `implement-phase.md` Step I.0 | It names the SPEC-change re-entry route, states that a zero-`pending`, zero-`failed` entry on it does not ABORT, and that it proceeds through Step I.1 to Step I.3 without Step I.2; the pre-change three-route wording fails the matcher | Unit |
| TS-3 | Step I.0's ABORT for states other than the SPEC-change re-entry | The immediate ABORT for a non-fresh entry with no `pending` and no `failed` task remains, ahead of the Step A.6 restoration paragraph; a synthetic Step I.0 without it fails the matcher | Unit |
| TS-4 | Section 11 of `rework-task-synthesis.md` | Exactly 11 invariants; Invariant 1 names the SPEC-change transition as out of its scope and cites Step I.0; the pre-change Invariant 1 fails the matcher | Unit |
| TS-5 | 「verify フェーズ」 item 6 of `skills/develop/SKILL.md` | It cites `references/rework-task-synthesis.md` Section 10 for `verify` returning to `pending` under the SPEC-change transition; the stop-condition list is unchanged; the pre-change item 6 fails the matcher | Unit |
| TS-6 | Full suite and plugin invariants after the existing pins are updated | `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` both exit 0 | Integration |
| TS-7 | Citation without restatement across the owner and citing documents | Invariant 1 cites Step I.0 and holds none of `recorded_at_commit` / `replan_authorized` / `consumed` / `completed_at_commit`; Step I.0 cites Section 10 and `references/phase-state.md`; the SKILL.md addition cites Section 10 and lists no transition step | Unit |
| TS-8 | Other entry routes of Step I.0 | The fresh-first-pass sentence, the rework re-entry paragraph (byte for byte), the batch infra auto-resume paragraph with its citation and the Step A.6 restoration paragraph are unchanged | Unit |
| TS-9 | Redaction of the changed documents | None of the five changed documents contains a Notion URL (`notion.so`, `notion.site`, `notion.com`) or an absolute path under `/home/` | Unit |
| TS-10 | Security statements of the SPEC-change re-entry identification in Step I.0 | Commit values are checked against the full hexadecimal commit object-id shape before any git command (TM-1); all five committed-fact conditions are required and a failing entry falls to the ABORT (TM-2); session memory and worker natural-language output are not used (TM-3) | Unit |
| TS-11 | Plugin version files | The integrated diff (implement `base_commit` to the integration tip) does not touch `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | Manual |
| TS-12 | Reproduction desk-check from the feature goal | Tracing the reproduction steps through the updated documents: verify-sourced SPEC-change transition sets `verify` to `pending`; a re-plan with zero new tasks enters implement through the SPEC-change re-entry, runs Step I.1 then Step I.3; review, verify and retrospect follow with no `failed` step left for stop condition 3 | Manual |

## Code Quality Verification
- Format: no format command is configured (`project.components.main.format_command` is empty)
- Static analysis: covered by `python3 em-workflow/scripts/check-plugin-invariants.py .`

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | In all three documents, step 2 of the SPEC-change transition includes `verify` and the five-step numbering is kept | TS-1 |
| AC2 | Step I.0 lists the SPEC-change re-entry and does not ABORT on it with zero `pending` and zero `failed` tasks | TS-2 |
| AC3 | Step I.0 launches no implementer for a zero-task SPEC-change re-entry and completes the phase at Step I.3 | TS-2 |
| AC4 | The immediate ABORT still holds for other non-fresh entries; the identification is stated in committed facts only | TS-3, TS-10 |
| AC5 | Invariant 1 lists the SPEC-change transition as out of scope and cites Step I.0; still 11 invariants | TS-4, TS-7 |
| AC6 | SKILL.md 「verify フェーズ」 item 6 cites that the SPEC-change transition returns `verify` to `pending` | TS-5 |
| AC7 | Run against the pre-change wording, the new tests fail for each of FR7 (a)–(d) | TS-1, TS-2, TS-3, TS-4 (verbatim pre-change negative samples), plus the red-phase run recorded in each task's test record |
| AC8 | The unittest suite and `check-plugin-invariants.py` both pass | TS-6 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-12 |
| FR2 | task0003 | TS-2, TS-12 |
| FR3 | task0003 | TS-2, TS-12 |
| FR4 | task0003 | TS-3, TS-10 |
| FR5 | task0002 | TS-4 |
| FR6 | task0001 | TS-5 |
| FR7 | task0001, task0002, task0003 | TS-1, TS-2, TS-3, TS-4 |
| FR8 | task0001, task0002, task0003 | TS-6 |
| NFR1 | task0001, task0002, task0003 | TS-7 |
| NFR2 | task0001, task0002, task0003 | TS-11 |
| NFR3 | task0001, task0002, task0003 | TS-6 |
| NFR4 | task0001, task0002, task0003 | TS-9; language checked manually below |
| NFR5 | task0003 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] TS-11: inspect the integrated diff for the two version files; neither changes.
- [ ] TS-12: desk-check the reproduction steps of the feature goal against the merged documents, as described in the scenario table.
- [ ] Language (NFR4): the added text in `implement-phase.md`, `rework-task-synthesis.md`, `contracts/rework-planner-contract.md` and `agents/rework-planner.md` is English; the added sentence in `skills/develop/SKILL.md` is Japanese.

## Performance / Security Verification (if applicable)
- TM-1: commit values read for the SPEC-change re-entry identification are checked against the full hexadecimal commit object-id shape before any git command, and a non-matching value means the route is not identified — checked by TS-10 (matcher on Step I.0 plus a negative sample naming the ancestry check without a shape check).
- TM-2: the identification requires all five committed-fact conditions and an entry failing any of them falls to the immediate ABORT — checked by TS-3 and TS-10.
- TM-3: the identification uses neither session memory nor worker natural-language output — checked by TS-10.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 1 | 1 | 0 | 0 |
| Test scenarios | 12 | 10 | 0 | 2 |
| Success criteria | 8 | 8 | 0 | 0 |
| Security (TM-n) | 3 | 3 | 0 | 0 |
| Language check | 1 | 0 | 0 | 1 |
