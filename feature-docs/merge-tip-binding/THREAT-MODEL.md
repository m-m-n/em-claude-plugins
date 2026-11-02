# Threat Model: merge-tip-binding

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, the merge skill procedure
(`em-workflow/skills/merge/SKILL.md`, steps 2, 6, 8, 12 and the held values),
`em-workflow/scripts/merge-git.py` (`integrate`) and the result contract
`em-workflow/references/merge-result.md`. Tier `full`; design step skipped.

The feature exists because a process other than the current merge run (a
concurrent run of the same feature, a develop session, a human) may move
`em-workflow/<feature>/integration` while the run is between its preflight
judgment and its integration, or while it waits for the merge lock. Two trust
boundaries follow from that: the integration branch ref written by another
writer (TB-1), and the post-lock tip read whose output the agent carries onto a
command line (TB-2). Both are analysed at deep depth: the tasks touching them
declare `input-handling`, and the integrate side also `external-io`.

Considered and not recorded as a threat row:

- Denial of service by a writer that keeps moving the integration branch: every
  run then stops with `verification_failed` (or `internal_error`). This is the
  intended fail-closed outcome (NFR1), not a defect to mitigate.
- A writer moving the integration branch back to the head of an already merged
  pull request makes the step 6.4 re-decision answer `already_merged`. Nothing is
  merged in that case, so the outcome stays on the non-merge side; no mitigation
  beyond SPEC.md is introduced.
- Information disclosure: the only new script output is a fixed `detail` text
  that carries no repository-derived value; NFR5 is checked as a requirement
  (VERIFICATION.md TS10), not as a threat here.

## Trust Boundaries

### TB-1: Integration branch ref written by another process
Crossing: commits that a process other than this merge run writes to `em-workflow/<feature>/integration` after the preflight (step 2) read `integration_tip`, entering this run's integration (step 8), verification (step 10) and merge (step 13).
Boundary files: em-workflow/scripts/merge-git.py, em-workflow/skills/merge/SKILL.md
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Commits added to the integration branch after preflight are integrated, verified and merged into the base branch without ever passing the preflight judgment (goal reproduction 2; FR2, FR3, NFR1) | TM-1 | `merge-git.py integrate` compares the integration worktree HEAD with the expected head after its worktree checks and before any fetch or merge; a mismatch stops with `verification_failed` and the fixed detail, with no fetch, no merge and no ref change. Step 8 passes the preflight `integration_tip` on the first integration and the last verified `head_sha` on a return from the step 12 redo, and on `verification_failed` stops the hold task (step 14) before terminating | task0001 AC-2, AC-5 | VERIFICATION.md TM-1 (TS3, TS4, TS5) |
| Tampering | An expected-head value that is not a full commit id (missing, abbreviated, uppercase, a ref name) weakens the equality or lets a moved tip match, so the binding of TM-1 silently stops binding (FR2, NFR1) | TM-2 | `integrate` requires the expected-head option and accepts only 40 lowercase hexadecimal characters; anything else ends with exit 2 and empty stdout, which the skill already treats as a script failure (`internal_error`) | task0001 AC-1 | VERIFICATION.md TM-2 (TS3) |

### TB-2: Post-lock tip read carried onto a command line
Crossing: the output of `git rev-parse --verify refs/heads/em-workflow/<feature>/integration` in step 6.4 (PR route) — a value another process may have just written — read by the agent and placed on the `merge-pr.py resolve --integration-tip` command line.
Boundary files: em-workflow/skills/merge/SKILL.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A read output that is not a plain commit id (git failure text, an unexpected value) carried onto a command line breaks the literal-only command form and can change what the command does (FR1, NFR2) | TM-3 | The output, trailing newline removed, becomes the held value `locked_tip` only when it is exactly 40 lowercase hexadecimal characters; a git failure or any other value stops the hold task (step 14) and terminates with `internal_error` | task0002 AC-3 | VERIFICATION.md TM-3 (TS1) |
| Tampering | If the post-lock read replaced the preflight binding, a tip moved by another writer during the lock wait would become step 8's expected head and TM-1 would accept the unjudged commits (FR1, FR5, NFR1) | TM-4 | The post-lock tip is held as the separate value `locked_tip` and passed only to the step 6.4 `resolve`; `integration_tip` is never overwritten and stays step 8's first expected head, so a moved, not-yet-merged tip ends `verification_failed` at step 8 | task0002 AC-2, AC-5; task0001 AC-5 | VERIFICATION.md TM-4 (TS1, TS5, TS9) |
