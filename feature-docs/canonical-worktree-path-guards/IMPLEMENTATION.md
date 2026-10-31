# Implementation Plan: canonical-worktree-path-guards

## Overview
In layouts where `.claude`, `.claude/worktrees` or `.claude/worktrees/em-workflow`
is a link resolving inside the main worktree, the launch guard and the
stale-launched identity binding accept the canonical (strict-realpath)
`worktree_path`. Three tasks run in parallel: the launch guard (task0001),
the identity binding (task0002) and the invocation-contract wording with its
pinned test constant (task0003).

## Technology Stack
- **Language**: Python 3, standard library only (NFR1).
- **External tool**: git CLI — `git rev-parse` only inside the hook (NFR4);
  test fixtures additionally use `git init`, a commit and `git worktree add`
  inside temporary directories.
- **Test runner**: unittest, `python3 -m unittest discover -s tests`.
- **New dependencies**: none. No license entry is needed (`project.license: none`).

## Layer Structure
| Layer | Files | Role in this feature |
|-------|-------|----------------------|
| Orchestrator instructions | `em-workflow/references/implement-phase.md` | Producer of the canonical `worktree_path` (task-assignment payload, unchanged) and owner of the `--task-worktree` invocation contract (wording changes) |
| Hook | `em-workflow/hooks/queue_launch_guard.py` | Consumes the prompt-carried `worktree_path` to derive the project root |
| Script | `em-workflow/scripts/recover-orphaned-task.py` | Consumes the Agent index entry's recorded `worktree_path` and `--task-worktree` |
| Tests | `tests/` | Drive the hook and the script through their entry points and function-level calls; doc-contract tests pin implement-phase.md wording |

Allowed dependencies: tests depend on the hook, the script and the
documents. The hook and the script do not import each other, and no new
cross-module import is introduced.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| SC-1: Canonical `worktree_path` (existing, unchanged) | The value implement-phase.md writes on the task-assignment block's `worktree_path:` line, and the value the Agent index entry records for the launch | Pre: `$WT_ROOT/{T}` exists at launch. Post: the value is the strict realpath of `$WT_ROOT/{T}`. In a linked layout it lacks the `/.claude/worktrees/em-workflow/` segment. Its parent directory is the feature worktree root reached without links, so `journal.jsonl` and `agents.jsonl` derived from it are the same files as those reached through the link | task0001 (fixtures pass it as `worktree_path`), task0002 (fixtures record it in the Agent index entry) |
| SC-2: Worktree binding comparison rule | Decides whether the Agent index entry's recorded worktree names the same worktree as `--task-worktree` | Inputs: the entry's recorded `worktree_path` and the `--task-worktree` value. Bound only when all hold: (1) each is a non-empty string that is an absolute path; (2) each resolves through non-strict link resolution (every existing link is resolved, the path need not exist) without raising; (3) the two resolved values are equal. Every other case, including any OS-level or invalid-value error (embedded NUL) during resolution, is a binding failure reported as `agent-identity-unproven`; no exception leaves the script and the journal stays byte-identical. Unchanged around it: `agent_ids` is the only candidate source, exactly one distinct candidate is required, `--stop-target` must equal it | task0002 (implements it and states it in docstrings), task0003 (states it in implement-phase.md as a comparison after resolving links on both sides) |

## Conventions
- **Standard library only** for the hook, the script and every new or
  changed test module (NFR1).
- **Failure policy per component**: the hook exits 0 for every input; an
  undecidable state produces no output (fail-open), and a deny happens only
  on a positively observed mismatch and always before the journal is opened
  (NFR2). The script turns every doubt in the binding into a residual,
  never `recovered`, and a residual leaves the journal byte-identical (NFR3).
- **Deterministic tests**: linked layouts are built from symlinks inside
  temporary directories. Link targets are directories inside the temporary
  project whose names do not recreate the `/.claude/worktrees/em-workflow/`
  segment. No test sleeps, applies load or depends on timing (NFR5).
- **Stable test identifiers**: no existing test class or test method is
  renamed or removed. Past features' test records under `test-docs/` name
  them, and `tests/test_tests_yaml_id_resolution.py` resolves every recorded
  ID (SPEC AC8).
- **Document tests**: text is compared after whitespace normalization, and
  every presence or absence assertion is paired with a negative proof — a
  forged text or a verbatim pre-change excerpt on which the opposite outcome
  is shown — following the existing doc-contract tests.
- **Documents**: no home-directory absolute paths and no external URLs in
  committed documents; paths are project-relative.

## Cross-task Design Decisions

### D1: Align both consumers with the canonical worktree_path
Decision: both consumers accept the canonical value. The launch guard keeps
deriving the project root from the segment and, only when the segment is
absent, takes the parent of the git common dir resolved from
`worktree_path`; when neither resolves it fails open as before. The binding
compares the two worktree values under SC-2.
Rationale: the producer (SC-1) stays canonical, and in the linked layouts
both consumers currently fail closed. This answers the Open Question left in
`feature-docs/cd-prefix-canonical-path-only/IMPLEMENTATION.md`; that
feature's documents are not edited (SPEC.md Decision, assumption a4).
Affected tasks: task0001, task0002, task0003.

### D2: Placement of the new tests (deferred by SPEC.md to create-plan)
- FR6 tests, the segment-absent fail-open tests, the fallback call-shape
  tests and the hook docstring test go in a new, self-contained module
  `tests/test_queue_launch_guard_linked_layout.py` that imports no other
  test module. `tests/test_queue_launch_guard.py` is not modified.
- FR7 tests go in new test classes in `tests/test_stale_launched_recovery_chain.py`,
  reusing that module's proving fixture and stub journal helper.
- `TestChainTaskWorktreeExistenceIrrelevant` stays in
  `tests/test_stale_launched_recovery_chain.py`; only its docstring changes.

Affected tasks: task0001, task0002.

### D3: Wording ownership
The exact new `--task-worktree` clause in implement-phase.md and the
`R4_NEW_STATEMENT` constant that pins it are owned together by task0003.
task0002's docstrings state SC-2 in their own words. No test in one task
pins text that another task writes.
Affected tasks: task0002, task0003.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The git common dir is not the main worktree's `.git` (a separate git dir or a bare repository), so the fallback derives a wrong root and denies a valid launch | Low | Medium | Out of scope (SPEC.md assumption a3): em-workflow creates task worktrees with `git worktree add` from the project root |
| A link target recreates the segment, so the segment derivation yields a wrong root | Low | Medium | Out of scope (SPEC.md Edge Cases); test link targets never recreate the segment |
| The docstrings (task0002) and the implement-phase.md clause (task0003) drift apart in meaning | Medium | Low | Both state SC-2; VERIFICATION.md carries a manual wording-consistency check |
| An existing test is renamed and a past test record stops resolving | Low | Medium | Stable test identifiers convention; the full suite includes `tests/test_tests_yaml_id_resolution.py` |

## Open Questions
- None. The Open Question of cd-prefix-canonical-path-only is answered by D1.
