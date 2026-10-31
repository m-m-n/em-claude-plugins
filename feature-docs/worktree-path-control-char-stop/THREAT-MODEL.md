# Threat Model: worktree-path-control-char-stop

## Verdict
threats-identified

## Rationale
Inspected SPEC.md (tier reduced: no REQUIREMENTS.md, design step skipped) and
Step I.2.a of `em-workflow/references/implement-phase.md`, the procedure the
feature changes. Step I.2.a resolves `$WT_ROOT/{T}` with a strict realpath and
puts the result on the `worktree_path:` line of the implementer launch
prompt. The names of the directories and link targets along that path
therefore reach the trusted part of an LLM prompt, and a cloned repository can
influence those names by placing links at or below
`.claude/worktrees/em-workflow`. That is one trust boundary (TB-1). task0001
declares `input-handling`, which sets TB-1's depth to deep. One Elevation of
privilege threat applies there.

The feature's other file, `tests/test_canonical_worktree_path_docs.py`, reads
only the repository's own document and crosses no boundary. No Denial of
service row is recorded: a repository that plants such a name makes the phase
stop, which is the fail-closed outcome FR3 asks for. Residual: the check is a
procedure the orchestrator follows; no hook enforces it, since
`queue_launch_guard.py` and `bash_guard.py` stay unchanged in this feature
(SPEC A4).

## Trust Boundaries

### TB-1: Worktree directory names into the implementer launch prompt
Crossing: the names of the directories and link targets that the strict
realpath of `$WT_ROOT/{T}` passes through (influenceable by a cloned
repository through links at or below `.claude/worktrees/em-workflow`) become
the task's canonical `worktree_path`, which the orchestrator interpolates into
the trusted part of the implementer launch prompt, ahead of the untrusted-data
label line (untrusted text interpolated into an LLM prompt).
Boundary files: em-workflow/references/implement-phase.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A name carrying a line break, or another control or line-separator character, splits the `worktree_path:` line, so attacker text lands as separate lines in the trusted part of the prompt, where the implementer reads it as an orchestrator instruction or as a trusted payload field; the cd-prefix syntax check and the launch hook's first-line extraction do not catch it (FR1, FR2, FR3). | TM-1 | Before the launch loop, Step I.2.a checks the canonical `worktree_path` of every selected task for Unicode Cc characters, U+2028 and U+2029; any hit aborts the implement phase, reports the offending task IDs and builds no launch prompt for any selected task, with no stripping, escaping, replacement or fallback to the unresolved path. | task0001 AC-1, AC-2 (procedure and placement); task0001 AC-4 (forged copies fail) | VERIFICATION.md Performance / Security Verification, TM-1 (TS-1, TS-2, TS-3) |
