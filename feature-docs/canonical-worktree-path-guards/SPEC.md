# Feature: canonical-worktree-path-guards

## Overview

Some layouts have `.claude`, `.claude/worktrees` or `.claude/worktrees/em-workflow` as a link that resolves inside the main worktree. In those layouts, the launch guard (`em-workflow/hooks/queue_launch_guard.py`) and the stale-launched identity binding (`em-workflow/scripts/recover-orphaned-task.py`) accept the canonical (strict-realpath) `worktree_path` that implement-phase.md passes to implementers. This feature also closes the Open Question that feature cd-prefix-canonical-path-only left in its IMPLEMENTATION.md.

Requirements document: `feature-docs/canonical-worktree-path-guards/REQUIREMENTS.md`.

## Objectives

- In the layouts above, the launch guard and the stale-launched identity binding accept the canonical `worktree_path`.
- Close the cd-prefix-canonical-path-only Open Question. The decision: align both consumers.

## Decision

The Open Question left by cd-prefix-canonical-path-only is answered here: both consumers — the launch guard and the stale-launched identity binding — are aligned with the canonical `worktree_path` (FR1). Past features' SPEC/IMPLEMENTATION documents are not edited.

## Acceptance Criteria

- [ ] **AC1** (FR1): SPEC records the decision to align both consumers.
- [ ] **AC2** (FR2, FR6): For each of the three link placements, a launch with cwd at the main worktree is allowed and appends `launched`. A launch with cwd in the integration worktree is denied, its reason names the project root, and the journal is unchanged.
- [ ] **AC3** (FR2, NFR2): When the segment is absent and the git common dir cannot be resolved (for example a `worktree_path` outside any repository or one that does not exist), the launch guard fails open as before. Every existing test in `tests/test_queue_launch_guard.py` passes, including `test_worktree_path_outside_layout_fails_open`.
- [ ] **AC4** (FR3): The hook docstring states the segment derivation, the git-common-dir fallback and fail-open when neither resolves, and no longer says that an outside-layout path always skips the check.
- [ ] **AC5** (FR4, FR7): In a linked layout, the canonical recorded worktree binds to `$WT_ROOT/{T}` and the chain reaches `recovered`. A nonexistent `--task-worktree` still binds. A mismatched, empty, relative or non-string value, or one that raises during resolution, yields `agent-identity-unproven`.
- [ ] **AC6** (FR4): The single-candidate rule, the `agent_ids`-only candidate source and the absence of `session_id` in `resolve_bound_stop_target`'s source still hold. The existing tests in `tests/test_stale_launched_recovery_chain.py` and `tests/test_recover_orphaned_task.py` pass.
- [ ] **AC7** (FR5): implement-phase.md states the link-resolving comparison for `--task-worktree`, and the updated `R4_NEW_STATEMENT` matches it. The pre-change "as a plain string" wording is absent from that sentence, with a negative proof.
- [ ] **AC8** (NFR1, NFR5): `python3 -m unittest discover -s tests` passes in full, including `tests/test_tests_yaml_id_resolution.py`.

## Technical Requirements

### Functional Requirements

- **FR1:** Alignment decision. The launch guard (`em-workflow/hooks/queue_launch_guard.py`) and the stale-launched identity binding (`em-workflow/scripts/recover-orphaned-task.py`) are both aligned with the canonical `worktree_path` in the layout where `.claude`, `.claude/worktrees` or `.claude/worktrees/em-workflow` is a link that resolves inside the main worktree.
- **FR2:** Launch guard: project root fallback. The launch guard keeps deriving the project root from the `/.claude/worktrees/em-workflow/` segment of `worktree_path`, unchanged. When `worktree_path` has no such segment, the project root is the parent directory of the output of `git rev-parse --path-format=absolute --git-common-dir` run with `worktree_path` as its working directory, under the existing git timeout. When that git call fails, times out or prints nothing, the cwd check is skipped (fail-open), as today. The derived root is compared with the cwd's git toplevel by realpath, as today. A launch whose cwd toplevel is a different root is denied before the journal is opened. The deny names the derived project root as the cd target.
- **FR3:** Launch guard: docstring. The hook's module docstring no longer says that a worktree path outside the `.claude/worktrees/em-workflow/` layout always skips the cwd check. It states the segment derivation, the git-common-dir fallback when the segment is absent, and fail-open when neither resolves.
- **FR4:** Stale-launched: link-tolerant worktree binding. In `resolve_bound_stop_target`, the recorded entry `worktree_path` and `--task-worktree` each have to be a non-empty string that is an absolute path. Otherwise the binding fails (`agent-identity-unproven`). The two values are compared after `os.path.realpath` without `strict`, so a worktree that no longer exists still binds when it names the recorded worktree. Any error raised while resolving either side (`OSError`, `ValueError` such as an embedded NUL) is a binding failure (`agent-identity-unproven`), never an exception out of the script. The existing conditions are unchanged: `agent_ids` is the only candidate source, exactly one distinct candidate is required, and `--stop-target` must equal that candidate. The source text of `resolve_bound_stop_target` does not contain the token `session_id`.
- **FR5:** Stale-launched: documents and pinned wording. In implement-phase.md's Same-session extension invocation contract, the `--task-worktree` value stays the task's expected worktree path (`$WT_ROOT/{T}`), supplied whether or not that path exists. The sentence no longer says "compared ... as a plain string". It states that the identity-binding step compares it with the Agent index entry's recorded worktree after resolving links on both sides. The `R4_NEW_STATEMENT` constant in `tests/test_stale_launched_missing_artifacts_doc_contract.py`, the docstring of `resolve_bound_stop_target` and the "plain string" docstring of `TestChainTaskWorktreeExistenceIrrelevant` are updated to that rule.
- **FR6:** Tests: launch guard in linked layouts. Subprocess-driven tests build a temporary git project with a real `git worktree add` integration worktree and task worktree under the feature's worktree root, for each of the three link placements (`.claude`, `.claude/worktrees`, `.claude/worktrees/em-workflow`, each a symlink to a directory inside the project). They pass the strict realpath of the task worktree as `worktree_path`. A launch with cwd at the main worktree is allowed and appends `launched`. A launch with cwd in the integration worktree is denied, the reason names the project root, and the journal is unchanged.
- **FR7:** Tests: stale-launched binding in linked layout. Tests cover `recover-orphaned-task.py` in a linked layout. An entry recording the canonical `worktree_path` binds to `--task-worktree` `$WT_ROOT/{T}` given through the link, and the chain reaches `recovered` through a stub helper. Binding still succeeds when the task worktree does not exist. A different worktree, an empty, relative or non-string value on either side, and a value that raises during resolution all yield `agent-identity-unproven` with the journal unchanged.

### Non-Functional Requirements

- **NFR1 - Standard library only:** The hook, the script and every new or changed test module import only the standard library.
- **NFR2 - Hook output discipline:** The launch guard exits 0 for every input. Undecidable states (malformed input, git unresolvable or timed out, path outside any repository) keep failing open. A denied launch leaves no `launched` event.
- **NFR3 - Fail safe in the evidence chain:** Doubt in the stale-launched binding is a residual, never `recovered`, and a residual leaves the journal byte-identical.
- **NFR4 - Read-only git call:** The fallback git call is `git rev-parse` only, bounded by the existing `GIT_TIMEOUT_SECONDS`, and it runs only when the segment is absent.
- **NFR5 - Deterministic tests:** Linked layouts are built with symlinks in temporary directories. No test relies on load or timing.

## Implementation Approach

### Architecture

Two consumers of `worktree_path` change; no new component is added.

```
implement-phase.md ── canonical worktree_path ──┬──> launch guard (queue_launch_guard.py)
                                                │       project root: segment, else git-common-dir parent, else fail-open
                                                │
Agent index entry (worktree_path) ──────────────┴──> stale-launched binding (recover-orphaned-task.py)
--task-worktree ($WT_ROOT/{T}) ──────────────────────    resolve_bound_stop_target: realpath (non-strict) on both sides
```

### Launch guard: project root derivation (FR2, FR3, NFR2, NFR4)

```
worktree_path
  ├─ contains '/.claude/worktrees/em-workflow/'  -> project root from the segment (unchanged)
  └─ no segment
       └─ git rev-parse --path-format=absolute --git-common-dir   (cwd = worktree_path, GIT_TIMEOUT_SECONDS)
            ├─ success, non-empty output -> project root = parent directory of the output
            └─ failure / timeout / empty -> skip the cwd check (fail-open)

project root vs. cwd's git toplevel (realpath comparison, unchanged)
  ├─ same root      -> continue
  └─ different root -> deny before the journal is opened; the deny names the project root as the cd target
```

The in-flight/merged denials, the deny-before-journal order and the existing fail-open conventions are unchanged.

### Stale-launched binding (FR4, NFR3)

`resolve_bound_stop_target`:

1. Each of the entry `worktree_path` and `--task-worktree` must be a non-empty string that is an absolute path; otherwise `agent-identity-unproven`.
2. Resolve both with `os.path.realpath` (non-strict). Any `OSError` / `ValueError` raised here is `agent-identity-unproven`; no exception leaves the script.
3. Compare the resolved values; a mismatch is `agent-identity-unproven`.
4. Existing conditions unchanged: candidates come only from `agent_ids`, exactly one distinct candidate, and `--stop-target` equals it. The function's source does not contain `session_id`.

A binding failure is a residual and leaves the journal byte-identical.

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- implement-phase.md: supplies the canonical `worktree_path` to implementers and states the `--task-worktree` contract (FR5).
- `tests/test_stale_launched_missing_artifacts_doc_contract.py`: pins the implement-phase.md sentence through `R4_NEW_STATEMENT` (FR5).

**External Dependencies:**
- git: `git rev-parse` only (NFR4).
- Python standard library only (NFR1).

### File Structure

Files named by the requirements:

- `em-workflow/hooks/queue_launch_guard.py` — FR2, FR3
- `em-workflow/scripts/recover-orphaned-task.py` — FR4, FR5 (docstring of `resolve_bound_stop_target`)
- implement-phase.md (Same-session extension invocation contract) — FR5
- `tests/test_stale_launched_missing_artifacts_doc_contract.py` — `R4_NEW_STATEMENT` (FR5)
- `tests/test_queue_launch_guard.py` — existing tests keep passing (AC3)
- `tests/test_stale_launched_recovery_chain.py`, `tests/test_recover_orphaned_task.py` — existing tests keep passing (AC6)

The modules that hold the new FR6/FR7 tests and `TestChainTaskWorktreeExistenceIrrelevant` are fixed at create-plan.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/canonical-worktree-path-guards/**`
- `test-docs/canonical-worktree-path-guards/**`

`feature-docs/canonical-worktree-path-guards/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/canonical-worktree-path-guards/**` covers `test-docs/canonical-worktree-path-guards/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS5** (AC4): Document test: the hook docstring contains the fallback statement and not the old outside-layout skip statement, each assertion paired with a forged-text negative proof.
- [ ] **TS9** (AC6): The existing source-level `session_id` pin and the single-candidate tests pass unchanged.
- [ ] **TS10** (AC7): Document test: implement-phase.md's `--task-worktree` sentence equals the updated `R4_NEW_STATEMENT`, and the old "plain string" wording is absent, with a negative proof against the verbatim pre-change sentence.

### Integration Tests

- [ ] **TS1** (AC2): Launch guard, link at `.claude/worktrees/em-workflow`: allow from the main worktree (`launched` appended), deny from the integration worktree (journal unchanged, reason names the project root).
- [ ] **TS2** (AC2): Same as TS1 with the link at `.claude/worktrees`.
- [ ] **TS3** (AC2): Same as TS1 with the link at `.claude`.
- [ ] **TS4** (AC3): Segment absent and git unresolvable (path in a non-repository temporary directory): exit 0, no output, fail-open. The existing outside-layout test still passes.
- [ ] **TS6** (AC5): `recover-orphaned-task.py` in a linked layout: the entry records the canonical path, `--task-worktree` is the link path, and the result is `recovered` with a stub helper called exactly once.
- [ ] **TS7** (AC5): The same linked fixture with the task worktree removed still binds and reaches `recovered`.
- [ ] **TS8** (AC5): `agent-identity-unproven` for: a different worktree, an empty string, a relative path, a non-string value (entry side and argument side), and a value containing NUL. The journal is byte-identical and the helper is not invoked.
- [ ] **TS11** (AC8): The full suite passes.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] A link target that itself contains a nested `/.claude/worktrees/em-workflow/` segment: `rfind` still derives a wrong root, which can give a false deny. Out of scope; not fixed here.
- [ ] The task worktree is missing in the missing-artifacts case: non-strict realpath still binds.
- [ ] `agents.jsonl` entries recorded before the canonical producer (`$WT_ROOT/{T}` form) still bind, because both sides are resolved.
- [ ] A link resolving outside the main worktree: out of scope (bash_guard FR5 refuses every cd prefix there).
- [ ] A link at or above the project root does not remove the segment (`WT_ROOT` comes from git's toplevel), so behaviour there is unchanged.

### Performance Tests

Not applicable.

## Security Considerations

- **Input Validation:** `worktree_path` and `--task-worktree` must each be a non-empty absolute-path string; resolution errors (including an embedded NUL) are binding failures (FR4).
- Other items: not applicable.

## Error Handling

| Condition | Component | Outcome |
|-----------|-----------|---------|
| cwd toplevel differs from the derived project root | launch guard | deny before the journal is opened; reason names the project root as the cd target |
| Segment absent and git call fails, times out or prints nothing | launch guard | cwd check skipped (fail-open), exit 0 |
| Malformed input, path outside any repository | launch guard | fail-open, exit 0 |
| Empty, relative or non-string worktree value on either side | stale-launched binding | `agent-identity-unproven`, journal byte-identical |
| `OSError` / `ValueError` while resolving either side | stale-launched binding | `agent-identity-unproven`, no exception out of the script |
| Resolved worktrees differ | stale-launched binding | `agent-identity-unproven`, journal byte-identical |

## Performance Optimization

Not applicable.

## Assumptions

- **a1:** Scope is the layout where the link resolves inside the main worktree.
- **a2:** The launch guard's in-flight/merged denials, the deny-before-journal order and the existing fail-open conventions are unchanged.
- **a3:** In the fallback, the derived project root is the parent of the git common dir. That equals the main worktree when the common dir is the main worktree's `.git` directory, which is how em-workflow creates task worktrees (`git worktree add` from the project root).
- **a4:** Past features' SPEC/IMPLEMENTATION documents are not edited. The cd-prefix-canonical-path-only Open Question is answered in this feature's own docs.
- **a5:** The plugin version is not changed.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1–AC8 hold

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements: `feature-docs/canonical-worktree-path-guards/REQUIREMENTS.md`
- Open Question being closed: `feature-docs/cd-prefix-canonical-path-only/IMPLEMENTATION.md`
