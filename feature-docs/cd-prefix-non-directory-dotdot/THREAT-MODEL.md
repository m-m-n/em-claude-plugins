# Threat Model: cd-prefix-non-directory-dotdot

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1–FR6, NFR1–NFR4, assumptions A1–A7), the
current `is_below()` / `is_cd_prefixed_approved()` in
`em-workflow/hooks/bash_guard.py`, and the cd-prefix test module. The tier
is `reduced`: there is no REQUIREMENTS.md and the design step was skipped.
The single task declares `auth` and `input-handling`, so the one boundary is
analysed at deep depth.

The feature narrows an existing allowance and adds no new input. It still
edits the code that turns agent-written command text into a PreToolUse
`allow`. A regression there grants permission. That makes the boundary
below real. Three STRIDE categories realistically apply to the change.
Spoofing, Repudiation and Information disclosure do not: the hook
authenticates no party, keeps no audit trail that this change alters, and
reveals nothing an agent cannot already learn by inspecting the filesystem
itself.

## Trust Boundaries

### TB-1: agent-written cd prefix → Bash guard permission decision
Crossing: the Bash command text written by an agent, which may be
prompt-injected, together with filesystem layout the agent can shape under
and around the worktree area (regular files, links, missing names). Both
reach the hook process, which may return `allow` for a cd-prefixed approved
command.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | The new physical-side condition, or an edit made with it, widens the allowance. A cd-prefixed approved command could then be allowed for a path where Bash lands outside the area, or whose logical destination exists outside the area (FR1–FR4, SPEC A2). | TM-1 | The change only adds a condition on the physical side: the as-written resolution must end at a directory. The logical-side computation, the both-below requirement when the logical path exists, and the per-component strictly-below comparison are unchanged. Every existing allow and silent case keeps its decision without modification. | task0001 AC-5 (with AC-1) | VERIFICATION.md, Performance / Security Verification, TM-1 |
| Elevation of privilege | To mirror Bash's cd more exactly, the as-written path is handed to a child process, as its working directory or as an argument to a shell or git. A directory the agent controls can then supply configuration or code that the child runs before any approval (NFR4). | TM-2 | The path is resolved only inside the hook process by the operating system's own path resolution. No child process ever receives it, and the hook's own working directory is never changed to it. | task0001 AC-6 | VERIFICATION.md, Performance / Security Verification, TM-2 |
| Denial of service | A crafted path the operating system cannot resolve (embedded NUL, a link loop, an over-long name, an unreadable component) makes the new as-written resolution raise out of `is_below()`. The hook then exits non-zero or writes to standard error instead of returning its decision (NFR3). | TM-3 | Every OSError or ValueError raised by the new resolution, as by the existing ones, is caught inside `is_below()` and yields False. The command is then judged as if it had no cd prefix. | task0001 AC-7 | VERIFICATION.md, Performance / Security Verification, TM-3 |
