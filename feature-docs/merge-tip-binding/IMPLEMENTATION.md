# Implementation Plan: merge-tip-binding

## Overview
Bind every decision of the unattended merge skill to a judged integration tip:
`merge-git.py integrate` refuses to integrate a worktree HEAD other than the
expected one (task0001), and the post-lock re-decision of the PR route reads
the current tip after the lock instead of reusing the preflight value
(task0002). Requirements: `feature-docs/merge-tip-binding/SPEC.md`.

## Technology Stack
- **Language**: Python 3 standard library only (script and tests).
- **Skill procedure**: Markdown (`em-workflow/skills/merge/SKILL.md`, Japanese),
  result contract in Markdown (`em-workflow/references/merge-result.md`,
  English).
- **External tool**: git CLI (already used).
- **New dependencies**: none (no license to record).

## Layer Structure
| Layer | Files | Responsibility |
|---|---|---|
| Procedure | `em-workflow/skills/merge/SKILL.md` | What the agent runs, in which order, with which literal values, and how each outcome ends |
| Decision script | `em-workflow/scripts/merge-git.py` | Deterministic git-side decisions; validates every argument before acting |
| Result contract | `em-workflow/references/merge-result.md` | Closed reason-code table (28 codes, unchanged in number) |
| Tests | `tests/test_merge_git.py`, `tests/test_merge_local_route.py`, `tests/test_merge_skill_doc.py` | Script behaviour in temporary git repositories; the procedure read as text |

Direction: the procedure calls the scripts and quotes the contract; scripts
never read the procedure. `merge-pr.py`, `merge-preflight.py` and
`merge-result.py` are not changed by this feature.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| C1: `merge-git.py integrate --expected-head <sha>` | Refuse to integrate a worktree HEAD other than the judged tip | Pre: `--expected-head` is present and is exactly 40 lowercase hexadecimal characters, else exit 2 with empty stdout. Post (mismatch): after the existing worktree-state check and the HEAD-equals-branch-tip check, a HEAD different from the expected value yields outcome `stop`, reason `verification_failed`, detail exactly `integration branch moved after preflight`, `head` and `integrated_base` null, `conflicted_paths` empty; no fetch, no merge, no ref or worktree change. Post (match): every previous outcome unchanged | task0001 (implements the script and the step 8 call); task0002 (the held-values text describes `integration_tip` as step 8's expected head) |
| C2: Expected-head selection in step 8 | Which held value step 8 passes as the expected head | First integration of the run: `integration_tip` (from preflight). Return from the step 12 redo, including after a step 9 resolution: the last verified `head_sha`. Each case is its own literal command form in step 8 (`--expected-head <integration_tip>` and `--expected-head <head_sha>`) | task0001 (step 8 text); task0002 (held-values text) |
| C3: Held value `locked_tip` | The integration tip read after the lock in the step 6.4 PR route | Set only from a `git rev-parse --verify refs/heads/em-workflow/<feature>/integration` output that, trailing newline removed, is exactly 40 lowercase hex; passed only to the step 6.4 `merge-pr.py resolve --integration-tip`. `integration_tip` is never overwritten by it | task0002 (defines and uses it); task0001 (step 8 must not use it) |

## Conventions
- **Fail-closed (NFR1)**: a value that cannot be validated or compared ends the
  run on the non-merge side (`stop`, exit 2, or `internal_error`), never by
  skipping the check.
- **Command forms (NFR2)**: new Bash forms follow SKILL.md's 「呼び出しの規則」
  — literal placeholders only, no expansion, substitution, glob or revision
  suffix; `cd` is its own Bash call; every foreground call has its own
  `Bash 呼び出し（timeout: N）:` line directly before its fence, N ≤ 600000.
- **State (NFR3)**: no new state file; no write to `workflow.yaml`.
- **Redaction (NFR5)**: no absolute home path and no Notion URL in any output,
  detail or document text.
- **Tests (NFR4)**: `unittest` only, temporary git repositories, the git
  logging shim already used by the merge tests; a concurrent writer is
  reproduced by committing inside the integration worktree at a fixed point,
  never by load, sleep loops or parallel processes.
- **Doc tests**: assert stable tokens (placeholders, reason codes, script
  names, exact command forms, short fixed phrases); every absence assertion is
  paired with a forged-text case on which its matcher fires. Existing forged-
  text detections are kept; an existing assertion that no longer fits the new
  shape is rewritten to the new shape, not deleted.

## Cross-task Design Decisions

### D1: Split by defect, keep each procedure change with its counterpart
task0001 owns the integration binding (script option, step 8, step 12,
result-value row, merge-result.md); task0002 owns the post-lock re-decision
(step 6 item 4, held values). The step 8 form that carries `--expected-head`
and the script that defines it live in the same task, so the existing check
that every option used in the skill exists in `merge-git.py`
(`TestScriptContractAgreement`) passes inside each task's worktree.

### D2: Names
Option `--expected-head`; held value `locked_tip`; fixed detail
`integration branch moved after preflight` (the same text on the first
integration and on a redo return). Affected: task0001, task0002.

### D3: The two bindings compose (C2 + C3)
`locked_tip` serves only the re-decision; the integration stays bound to
`integration_tip`. When the branch moved during the lock wait and the PR
re-decision answers `open`, the run reaches step 8, whose check stops with
`verification_failed`. Neither task adds handling for that path beyond C1–C3.
Affected: task0001, task0002.

### D4: Section ownership inside shared files
| File | task0001 owns | task0002 owns |
|---|---|---|
| `em-workflow/skills/merge/SKILL.md` | Step 8, step 12, the `verification_failed` row of 「結果の値」 | Step 6 item 4, 「保持する値」 |
| `tests/test_merge_skill_doc.py` | The existing test `test_ac2_the_verification_failed_row_lists_step_13_and_the_moved_branch_detail`; one new test class placed directly after `TestLocalMergeBoundToHeadSha` | The existing tests `test_ac6_every_resolve_form_in_the_skill_passes_an_integration_tip` and `test_ac4_the_redecision_forms_pass_the_options_of_steps_4_and_5_2`; one new test class placed directly after `TestPostLockMergedRedecision` |

A task edits no region the other owns. New helpers sit next to the owning
task's new class, and each new class carries its own coverage note in its
class docstring; the module docstring is not edited.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Both tasks edit `SKILL.md` and `tests/test_merge_skill_doc.py` and collide | Medium | Low | D4 ownership and placement; remaining conflicts follow the parent-side adoption protocol |
| The new check stops a normal run (false `verification_failed`) | Low | High | No step between preflight and step 8 moves the local integration branch (push does not, step 7 abort restores the tip, worktree add attaches the existing branch); C2 uses `head_sha` after a redo; task0001's positive chain test proves the normal path still merges |
| The held-values text and step 8 disagree on which value is the expected head | Low | Medium | C2 is the single statement both texts follow; TS5 and TS9 in VERIFICATION.md check each side |

## Open Questions
- [ ] (Out of scope, observed) `merge-result.md`'s `verification_failed`
      Condition does not mention the existing step 13 case
      (`integration branch moved after verification`). FR4 adds only the step 8
      case; the step 13 wording is left as is.
