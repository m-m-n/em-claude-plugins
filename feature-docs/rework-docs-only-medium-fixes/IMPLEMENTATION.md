# Implementation Plan: rework-docs-only-medium-fixes

## Overview
This plan tightens three checks of `em-workflow/scripts/validate-worker-output.py` to SPEC.md FR1–FR4: rename-aware coverage, the docs-only round's step_patches, and tests_replace. The SSOT documents get the same rules (FR5). Every new rejection is backed by an invalid- fixture and a test (FR6), and every existing valid- fixture stays accepted (FR7).

## Technology Stack
- **Language**: Python 3 (the existing validator script and test suite)
- **Test framework**: standard-library unittest only (NFR2). The suite runs as `python3 -m unittest discover -s tests` from the repository root (NFR3).
- **New dependencies**: none. No license to record.

## Layer Structure
| Layer | Location | Responsibility |
|---|---|---|
| Validator | `em-workflow/scripts/validate-worker-output.py` | Runs structural and cross-artifact checks on worker results and workflow patches. Exit 0 means accepted; exit 1 means rejected, with JSON error details. |
| Fixtures | `em-workflow/references/fixtures/` | Accept and reject examples (`valid-*` / `invalid-*`) that the validator runs against |
| Tests | `tests/test_rework_docs_only_validator_rules.py` | Run the validator on fixtures and on inputs the tests build, then assert the exit code and the reported codes |
| SSOT documents | `em-workflow/references/rework-task-synthesis.md` (Section 12), `em-workflow/references/contracts/rework-planner-contract.md` (check 2), `em-workflow/references/workflow-patch.md` (Tests replacement) | State the rules the validator enforces |

Allowed dependencies: tests use the validator as a CLI, and the validator reads fixtures as data. The validator never reads the SSOT documents. The validator code and the SSOT text both come from SPEC.md FR1–FR4 plus decisions D1–D4 below. Neither waits on the other.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Validator error-code vocabulary | Names each rejection this feature adds | `rework-index`: FR1/FR2 rejections. `requirements_patch`: FR4 overlap. `docs-only-implement-reset` (existing code): any docs-only-round step patch that targets implement. `docs-only-step-patches` (new code): a docs-only-round step_patches count, origin or status violation. Postcondition of every rejection: the validator's existing error report gains an entry with the code and a message, and the process exits 1 with JSON error details. | task0001, task0002, task0003, task0004 |
| Validator CLI surface | The invocation that tests and the orchestrator use | No option and no envelope field is added. Existing options: `--kind worker-result` / `--kind workflow-patch`, `--dry-run-apply`, `--feature-dir`, `--baseline-dir`, plus the existing way the input envelope is supplied. Postcondition: exit 0 means accepted, exit 1 means rejected. Malformed input content never produces exit 2. | task0001, task0002, task0003 |
| Fixture layout | One directory per fixture | Each fixture is a directory under `em-workflow/references/fixtures/` whose name starts with `valid-` or `invalid-`. A new fixture goes next to the existing fixture it is derived from and copies that fixture's internal layout. Optional subdirectories `feature-dir/` and `baseline-dir/` hold the post-change and the baseline VERIFICATION.md. Postcondition (built by task0001): the fixture test runner passes each subdirectory that exists as `--feature-dir` / `--baseline-dir`, independently. A fixture with neither subdirectory runs exactly as before. | task0001 (builds the runner support), task0002, task0003 (create fixtures without these subdirectories) |
| Test module `tests/test_rework_docs_only_validator_rules.py` | Holds all tests of this feature | Each task adds its tests in its own new test class: task0001 `TestRenameCoverageDiff`, task0002 `TestDocsOnlyStepPatches`, task0003 `TestTestsReplaceOverlap`. Expectations for new fixtures go wherever the existing fixture tests keep theirs. Only task0001 changes `TestFixtures._run`. | task0001, task0002, task0003 |

## Conventions
- **Fail-closed**: if information that an acceptance depends on is missing or malformed, the check rejects.
- **Robustness (NFR1)**: no new check raises on malformed shapes. Such shapes include a non-mapping where a mapping is expected, a non-string where a string is expected, a list element of the wrong shape, and a file that cannot be read as text. Each is reported as an error. Non-string values never take part in set or membership computations; they are excluded and reported.
- **Structural layer**: the FR3 and FR4 checks run whether or not `--dry-run-apply` is given. They run on every route that validates the patch: the result's workflow_patch under `--kind worker-result`, and the patch under `--kind workflow-patch`.
- **Scenario IDs**: the only scenario-ID forms are TS-n and TSn. IDs are compared as literal strings, so `TS13` and `TS-13` are different IDs.
- **Single-defect fixtures**: each new invalid- fixture is derived from a valid- fixture by the smallest change that introduces its one targeted defect. It satisfies every rule of FR1–FR4 except the targeted one, as SPEC.md states those rules (not as the current code enforces them). This way another task's new check does not add codes to it after merge.
- **tests_replace in fixtures**: no new fixture that contains tests_replace joins the rework-planner fixture set that `test_ac6_no_fixture_uses_tests_replace` targets. Each task checks how that test selects its fixtures and names and places new fixtures outside that set.
- **Existing fixtures**: an existing invalid- fixture may gain additional reported codes. Its expected codes are then updated on the tests side. Existing valid- fixtures stay unchanged, with one exception: `valid-mixed-round-renamed-scenario-declared` gains `feature-dir/` and `baseline-dir/` (task0001).
- **Scope guards**: no task edits `feature-docs/rework-docs-only-task-routing/`. No task edits `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.

## Cross-task Design Decisions

### D1: Rule source
The validator tasks implement SPEC.md FR1–FR4 together with D2–D4. The SSOT task writes the same rules. Messages are task0001's wording; the SSOT documents do not quote them.
Affected: task0001, task0002, task0003, task0004.

### D2: Rename-aware coverage decision (FR1, FR2)
Definitions:
- **Declared pair**: a mapping under payload.doc_corrections[].scenario_renames whose `from` and `to` are both non-empty strings.
- **Diff available**: `--feature-dir` and `--baseline-dir` are both given, and feature-dir contains VERIFICATION.md.
- **Post set**: the scenario IDs defined by `{feature-dir}/VERIFICATION.md`.
- **Baseline set**: the scenario IDs defined by `{baseline-dir}/VERIFICATION.md`. The set is empty when that file is absent.

Each ID in rework_index.covered_by_existing is judged by the first matching row:

| # | The ID is | Diff available | Diff not available |
|---|---|---|---|
| 1 | the `from` of any declared pair | rejected | rejected |
| 2 | a verification_index key | accepted only if it is in the post set | accepted (unchanged behavior) |
| 3 | the `to` of one or more declared pairs | accepted only if **every** declared pair with this `to` meets all four conditions: `from` is a verification_index key, `to` is in the post set, `from` is in the baseline set, `from` is not in the post set | rejected with the diff-unavailable message |
| 4 | none of the above | rejected (existing no-declaration message) | rejected (existing no-declaration message) |

Every rejection uses code `rework-index`. If a set is needed and its VERIFICATION.md exists but cannot be read as text, the check reports one `rework-index` error that names the file, and no ID is accepted on the strength of that set. The diff-unavailable message names what is missing (`--feature-dir`, `--baseline-dir`, or feature-dir's VERIFICATION.md). Its text differs from the no-declaration message.
Affected: task0001 (implements), task0004 (documents).

### D3: Docs-only round step_patches (FR3)
A docs-only round is an `append_rework` patch whose tasks_patch.entries is absent or empty. Origin step resolution:

| Envelope state | Origin step |
|---|---|
| The validator holds the run's input envelope; rework_source is a mapping with `type` exactly `review` or `verify` | that value |
| No envelope (for example `--kind workflow-patch` alone), rework_source absent, or rework_source a mapping without a `type` key | either `verify` or `review` |
| rework_source present but not a mapping, or a `type` key present whose value is not exactly the string `review` or `verify` (null, a non-string, or any other string) | none: the origin match cannot be satisfied (fail-closed) |

Two independent checks, both structural:
- Every step_patches entry whose step_id is `implement` yields `docs-only-implement-reset`, whatever its set.status is.
- `docs-only-step-patches` is reported once per patch unless step_patches is a list of exactly one mapping whose step_id is the origin step (or `verify` / `review` when the origin is unresolved) and whose set.status is the string `pending`. The message names the violated condition.

An implement entry can therefore yield both codes.
Affected: task0002 (implements), task0004 (documents).

### D4: tests_replace overlap (FR4)
For each requirements_patch entry whose set.tests_replace is a list:
- The from set is the string `from` values of its mapping pairs, and the to set is the string `to` values.
- A non-empty intersection is rejected as `requirements_patch`. The error names the requirement ID and the overlapping IDs.
- This covers chains (TS-1→TS-2, TS-2→TS-3) and swaps (TS-1→TS-2, TS-2→TS-1).
- Pairs that share a `to` (TS1→X, TS2→X) do not overlap and keep the existing application rule.
- Malformed pairs stay with the existing shape checks.

Affected: task0003 (implements), task0004 (documents).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Merge conflicts in the validator and the test module across task0001–task0003 | High | Low | Each task changes only its own check and adds its own test class (Shared Components). Conflicts are resolved by the parent-side adoption protocol. |
| After merge, one task's new check adds a code to another task's fixture | Medium | Medium | Single-defect fixture convention. The full suite runs in the verify phase (TS-24). |
| An existing valid- fixture depends on a behavior that this feature tightens | Low | Medium | Each code task's acceptance criteria require every valid- fixture to pass (TS-20). |
| SSOT wording and validator behavior diverge | Medium | Medium | Both follow SPEC.md plus D2–D4. Manual inspection covers this (TS-22). |

## Open Questions
- None.
