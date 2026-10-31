# Threat Model: cd-prefix-canonical-path-only

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md, the cd prefix path check in
`em-workflow/hooks/bash_guard.py` (`is_cd_prefixed_approved`,
`worktree_area`, `strictly_below`, `is_below` and the stage walk it calls),
the Verbatim execution rule of
`em-workflow/references/command-execution-protocol.md`, and the
worktree_path production in `em-workflow/references/implement-phase.md`.
Tier: full. task0001 declares `auth`, `input-handling` and `external-io`,
which set both boundaries below to deep depth. task0002 declares
`api-contract`, which does not deepen the analysis.

The feature replaces the check that decides whether an agent-written
`cd "<path>" && <approved command>` runs without a permission prompt.
Agent-written command text, and the directory layout of the main worktree
(which a cloned repository can supply), both reach that allow decision, so
trust boundaries exist. Elevation of privilege, Tampering and Denial of
service realistically apply to them.

Considered and not recorded as threats:

- The race between the check and the execution, in which a checked
  directory or one of its ancestors is replaced by a link, is out of scope
  (the out-of-scope item of the feature goal in workflow.yaml): a
  PreToolUse hook alone cannot close it.
- The worktree_path that implement-phase.md produces (FR8) is computed by
  the orchestrator from git's own output and handed to its own implementer
  subagent. No party of different trust takes part, so it is not a trust
  boundary. A non-canonical value only makes the hook refuse the cd prefix
  form, which is the fail-closed side.
- Condition (c) of FR1 resolves every link a path names. A long chain of
  links that an agent plants inside its own task worktree costs time in
  proportion to the chain, delays only that agent's own Bash call and gains
  no privilege.
- Probes of locations under /proc or /dev/fd are no longer prevented (FR4).
  A path written below the area reaches such a location only through a link
  component, and condition (c) of FR1 then refuses it, so the decision never
  rests on how the hook process, rather than the Bash process, resolves the
  path. This is part of TM-1.

Domain consistency: the `auth`, `input-handling` and `external-io` domains
of task0001 all apply to `em-workflow/hooks/bash_guard.py`, the Boundary
file of TB-1 and TB-2. task0001's other files (the protocol document, the
test module and past features' test records) implement no boundary.
task0002 declares none of the four depth-setting domains.

## Trust Boundaries

### TB-1: Agent-written cd prefix command into the hook's allow decision
Crossing: the command text of a Bash call written by an LLM agent (an
implementer subagent that repository content may prompt-inject) crosses
into the deterministic bash_guard.py PreToolUse hook. An allow from the hook
skips the user's permission prompt and runs an approved command in the
directory the agent named.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A cd prefix path in a non-canonical form (a trailing or duplicated `/`, a `.` or `..` component, a link component, or a process-dependent location such as one under /proc) is judged to lie below the allowed area while the Bash process lands somewhere else, so an approved command runs without a prompt outside the task worktrees (FR1, FR6; SPEC Security Considerations, Input Validation) | TM-1 | Accept only a path that is already canonical: absolute with no empty, `.` or `..` component other than the root, lexically strictly below the area, equal to its own strict realpath, and an existing directory. The path is never normalized and then accepted | task0001 AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 (TS2, TS3, TS4) |
| Denial of service | A very long path written in the command makes the path check slow (the removed stage walk grew with the square of the number of components), which stalls the Bash call and an unattended run (FR2, NFR4) | TM-2 | Refuse a path whose encoded byte length reaches the run-time path-length bound before `worktree_area()` is called and before any file-system access, and refuse when the bound cannot be obtained or is not positive. The remaining checks grow linearly with the path | task0001 AC-3 | VERIFICATION.md Performance / Security Verification: TM-2 (TS5, TS6, TS13) |
| Elevation of privilege | Input on which a check cannot decide (an embedded NUL, a character the file-system encoding cannot encode, a resolution error, an unobtainable bound) is treated as allowed, or escapes as an exception that crashes the hook (FR3, NFR3, NFR5; SPEC Security Considerations, Fail closed) | TM-3 | Every OSError and ValueError raised by the length check or the path check makes the path not allowed. Not allowed is judged as if there were no cd prefix, with no new deny, and the hook exits 0 with nothing on stderr | task0001 AC-5 | VERIFICATION.md Performance / Security Verification: TM-3 (TS6, TS8) |

### TB-2: Main worktree layout into the hook's allowed area
Crossing: the directories and symbolic links at
`.claude/worktrees/em-workflow` and its ancestors inside the main worktree
cross into the hook's derivation of the allowed area. A cloned repository
can supply them as tracked symbolic links.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A symbolic link at `.claude/worktrees/em-workflow` or at one of its ancestors points outside the main worktree, so the resolved area, and every directory TM-1 accepts below it, moves to an arbitrary location (FR5) | TM-4 | Use the resolved area only when it lies strictly below the realpath of the main worktree (the parent of the git common dir). Otherwise allow no cd prefix form | task0001 AC-4 | VERIFICATION.md Performance / Security Verification: TM-4 (TS7) |
