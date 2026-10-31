# Verification Document: canonical-worktree-path-guards

## Overview
**Feature**: canonical-worktree-path-guards / **SPEC.md**: `feature-docs/canonical-worktree-path-guards/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/canonical-worktree-path-guards/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/canonical-worktree-path-guards/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty; the Python sources have no build step.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run at the repository root)
- Focused run: `python3 -m unittest tests.test_queue_launch_guard tests.test_queue_launch_guard_linked_layout tests.test_stale_launched_recovery_chain tests.test_recover_orphaned_task tests.test_stale_launched_missing_artifacts_doc_contract tests.test_tests_yaml_id_resolution`
- Coverage target: no coverage tool is configured. Every scenario below maps to at least one test, and every task Acceptance Criterion maps to at least one scenario.

### Test Scenarios from SPEC.md
TS1–TS11 are SPEC.md's own scenario IDs, kept as written there. TS12–TS14 were added at create-plan for requirements that SPEC.md's scenarios do not test directly.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Launch guard, link at `.claude/worktrees/em-workflow`; real `git worktree add` integration and task worktrees; `worktree_path` is the task worktree's strict realpath (no segment) | cwd at the main worktree: exit 0, no output, `launched` appended. cwd in the integration worktree: exit 0, deny whose reason and cd instruction name the project root, no `launched` event for the task in the journal | Integration |
| TS2 | Same as TS1 with the link at `.claude/worktrees` | Same as TS1 | Integration |
| TS3 | Same as TS1 with the link at `.claude` | Same as TS1 | Integration |
| TS4 | Segment absent and git unresolvable: an existing directory inside a non-repository temporary directory, and a nonexistent absolute path | Exit 0, no deny output (fail-open). Existing `tests/test_queue_launch_guard.py` passes unmodified, including `test_worktree_path_outside_layout_fails_open` | Integration |
| TS5 | Document test on the hook's module docstring | States segment derivation, git-common-dir fallback and fail-open when neither resolves; the pre-change outside-layout skip statement is absent; each assertion paired with a forged-text negative proof | Unit |
| TS6 | `recover-orphaned-task.py` in a linked layout: entry records the canonical path, `--task-worktree` is `$WT_ROOT/{T}` through the link | `recovered` through `decide()` and once through the command-line entry point; stub helper invoked exactly once with reason `stale-launched` | Integration |
| TS7 | Same linked fixture with the task worktree removed | Still binds; `recovered` | Integration |
| TS8 | Binding failures: a different worktree; empty string and relative path on each side; non-string on each side; NUL-containing value on each side; a resolution forced to raise | `agent-identity-unproven`, no exception out of `decide()`, journal byte-identical, helper not invoked | Integration |
| TS9 | Existing source-level `session_id` pin, single-candidate tests and the rest of `tests/test_stale_launched_recovery_chain.py` / `tests/test_recover_orphaned_task.py` | All pass with no test renamed, removed or changed in body; the function's source (docstring included) has no `session_id` | Unit |
| TS10 | Document test on implement-phase.md's `--task-worktree` clause | The clause equals the updated `R4_NEW_STATEMENT`; "as a plain string" is absent from the I.2.b section, with a negative proof against the verbatim pre-change clause | Unit |
| TS11 | Full suite | `python3 -m unittest discover -s tests` passes, including `tests/test_tests_yaml_id_resolution.py` | Integration |
| TS12 | Launch guard fallback call shape and failure handling, function level, with a recording stand-in process runner (added at create-plan) | Segment present: no git-common-dir call. Segment absent: exactly one `git rev-parse --path-format=absolute --git-common-dir` with `worktree_path` as working directory and `GIT_TIMEOUT_SECONDS`. Start failure, timeout, non-zero exit or empty output: root undetermined, no denial; no real timeout waited for | Unit |
| TS13 | Document test on the docstrings of `resolve_bound_stop_target` and `TestChainTaskWorktreeExistenceIrrelevant` (added at create-plan) | Both state the link-resolving comparison; the class docstring contains no "plain string"; each assertion paired with a negative proof | Unit |
| TS14 | Standard-library-only import check (added at create-plan) on `em-workflow/hooks/queue_launch_guard.py`, `em-workflow/scripts/recover-orphaned-task.py`, `tests/test_queue_launch_guard_linked_layout.py`, `tests/test_stale_launched_recovery_chain.py` and `tests/test_stale_launched_missing_artifacts_doc_contract.py` | Every imported top-level module is a standard-library module | Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | SPEC records the decision to align both consumers | Manual: SPEC.md `## Decision` and IMPLEMENTATION.md D1 |
| AC2 | Each of the three link placements: allow from the main worktree with `launched` appended; deny from the integration worktree naming the project root, journal unchanged | TS1, TS2, TS3 |
| AC3 | Segment absent and git common dir unresolvable: fail-open; every existing launch guard test passes | TS4, TS12, TS11 |
| AC4 | Hook docstring states the new derivation and drops the outside-layout skip statement | TS5 |
| AC5 | Linked layout binds and reaches `recovered`; nonexistent `--task-worktree` still binds; mismatched, empty, relative, non-string or raising values yield `agent-identity-unproven` | TS6, TS7, TS8 |
| AC6 | Single-candidate rule, `agent_ids`-only source and no `session_id` in the function source still hold; existing tests pass | TS9 |
| AC7 | implement-phase.md states the link-resolving comparison, matched by `R4_NEW_STATEMENT`; old "as a plain string" wording absent with a negative proof | TS10 |
| AC8 | Full suite passes, including `tests/test_tests_yaml_id_resolution.py` | TS11, TS14 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS1, TS2, TS3, TS6; manual AC1 check |
| FR2 | task0001 | TS1, TS2, TS3, TS4, TS12 |
| FR3 | task0001 | TS5 |
| FR4 | task0002 | TS6, TS7, TS8, TS9 |
| FR5 | task0002, task0003 | TS10, TS13 |
| FR6 | task0001 | TS1, TS2, TS3 |
| FR7 | task0002 | TS6, TS7, TS8 |
| NFR1 | task0001, task0002, task0003 | TS11, TS14 |
| NFR2 | task0001 | TS1, TS2, TS3, TS4, TS12 |
| NFR3 | task0002 | TS8 |
| NFR4 | task0001 | TS12 |
| NFR5 | task0001, task0002 | TS1, TS2, TS3, TS6, TS7, TS11 |

## Manual Testing (E2E Not Possible)
No E2E framework is configured (`e2e_test_command` is empty).
- [ ] AC1: SPEC.md `## Decision` records aligning both consumers, and IMPLEMENTATION.md D1 records the cd-prefix-canonical-path-only Open Question as answered without editing that feature's documents.
- [ ] Wording consistency: the implement-phase.md `--task-worktree` clause and the docstring of `resolve_bound_stop_target` describe the same comparison rule (IMPLEMENTATION.md SC-2).

## Performance / Security Verification (if applicable)
- NFR4: the fallback git call is `git rev-parse` only, bounded by `GIT_TIMEOUT_SECONDS`, made only when the segment is absent — TS12.
- TM-1: fallback limited to segment-absent paths, `git rev-parse` only, bounded by `GIT_TIMEOUT_SECONDS`; start failure, timeout, non-zero exit or empty output skips the cwd check and the hook exits 0 — checked by TS12 (function-level failure states) and TS4 (hook entry point, git unresolvable).
- TM-2: both worktree values must be non-empty absolute-path strings before resolution — checked by TS8's empty-string and relative-path cases on each side (`agent-identity-unproven`, journal byte-identical, helper not invoked).
- TM-3: type check before resolution; any error raised while resolving is a binding failure and never escapes — checked by TS8's non-string, NUL and forced-raise cases (no exception out of `decide()`, journal byte-identical).
- TM-4: candidates only from `agent_ids`, exactly one distinct, `--stop-target` equal to it, no `session_id` token in the function source — checked by TS9 (source pin and single-candidate tests) together with TS13 (the rewritten docstring).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1–TS14) | 14 | 14 | 0 | 0 |
| Success criteria (AC1–AC8) | 8 | 7 | 0 | 1 |
| Threat mitigations (TM-1–TM-4) | 4 | 4 | 0 | 0 |
| Manual-only checks (wording consistency) | 1 | 0 | 0 | 1 |
