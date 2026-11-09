# Implementation Plan: destructive-guard-false-deny

## Overview
Phenomenon 2: destructive-guard must stop denying git command text that
sits in a single-quoted data argument the shell never executes. Phenomenon
1: cases pin that the protocol's non-forced task-branch deletion passes and
that forced deletion stays denied. One task (task0001) carries the whole
change, because the cases must land before the hook change (FR6).

## Technology Stack
- **Language**: Python 3, standard library only (the hook and its runner).
- **Tests**: the case suite `em-workflow/hooks/tests/destructive-guard-cases.json`, run by `em-workflow/hooks/tests/run-destructive-guard.py`. Repository unit tests under `tests/` run through unittest discovery.
- **New dependencies**: none.

## Layer Structure
The hook reads one PreToolUse payload and emits one decision. Inside it:

1. **Lexing and structural scan** (the lexer, `scan_structure()`): finds
   where quotes, substitutions and heredocs are.
2. **Chunk loop** (`statements()`): takes chunks off a pending stack. The
   command itself comes first, then the chunks derived from it: substitution
   bodies, unclosed command forms, heredoc bodies, and -c / eval /
   here-string payloads. For each chunk the loop marks substitutions, walks
   and yields the statements, and queues further derived chunks.
3. **Per-statement checks and decision** (`check_git()`, `check_rm()`, ...,
   `decide()`).

This feature changes only which derived chunks layer 2 queues. Layers 1
and 3 stay unchanged. Dependencies point one way: layer 2 reads layer 1,
and layer 3 reads what layer 2 yields.

## Shared Components
None. The feature has a single task, so no component is built by one task
and used by another.

## Conventions
- Case format and placement follow `.claude/rules/hook-tests.md`. A case this feature adds carries its SPEC scenario ID (TS-n) in its label.
- Pre-existing cases are never removed or changed (hook-tests rule, NFR1).
- Plugin versions: the repository's Actions workflow bumps them. Plans and tasks of this feature make no version edit (NFR3).
- Fail-closed: when a judgement this feature adds cannot be decided, the hook falls back to the pre-feature behaviour (re-scan), never to skipping.

## Cross-task Design Decisions

### D1: Phenomenon 1 is resolved on the protocol side
The git-branch-force-delete judgement of `check_git()` stays as it is. The
task-branch cleanup in `em-workflow/references/implement-phase.md` Step
I.2.b step 4 already uses the non-forced deletion from the integration
worktree, with no forced fallback, so its text also stays as it is. The
feature only pins both facts with cases: TS-1 (allow) and TS-2 (deny).
Basis: SPEC A1. Affected: task0001, and any later rework task. No task may
relax the forced-deletion judgement.

### D2: The narrowing is a queueing decision on the top-level chunk
Phenomenon 2 is fixed in one place. The body of a single-quote candidate is
not queued for re-scanning when the candidate sits in the top-level chunk
and that chunk meets FR2 (a)-(d). Marking (FR3) and every other derived
chunk stay untouched. task0001's plan defines the terms and invariants.
Affected: task0001, and any later rework task that touches `statements()`.

### D3: Cases precede the hook change
The case additions are committed and run against the unmodified hook before
the hook changes (FR6, hook-tests rule). The task's test record holds the
pre-fix result. Affected: task0001, and any rework task that changes the
hook's judgement.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A program outside the execution-word vocabulary runs single-quoted text that the hook no longer re-scans, for example one that runs its argument as a command | Low | High: a destructive command runs without deny | The vocabulary covers at least FR2 (c). The command word is read after the wrapper skip and compared by its last path segment. SPEC allows extending the vocabulary. The guard never caught the plain single-quoted form of the same command, so the loss is confined to the substitution form (THREAT-MODEL.md TM-1) |
| A change in the order of queued derived chunks shifts run-global state (the override flag, the deferred data-heredoc bodies, marker positions) and changes unrelated verdicts | Medium | Medium | task0001 invariant Q1 keeps the queue identical except for the omitted bodies. The full case suite runs |
| Marking changes by accident (FR3), which weakens the rm checks | Low | High | THREAT-MODEL.md TM-2. The FR3 example cases stay in the suite |
| Pre-fix behaviour differs from SPEC's code reading (SPEC A7), for example TS-1 or TS-5 not allow, or a deny-side case not deny | Low | Medium | Checked before the hook change (FR6). A mismatch is reported as a plan deviation, and `check_git()` is not loosened |
| A comment or docstring rewrite (FR7) breaks a repository test that reads the hook's text | Low | Low | NFR4 comparison of unittest discovery before and after |

## Open Questions
- [ ] SPEC A2: it is unconfirmed whether em-review or plugin-dev carries a copy of destructive-guard. This plan changes em-workflow only.
