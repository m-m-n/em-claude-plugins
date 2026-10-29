# Threat Model: cd-prefix-process-dependent-paths

## Verdict
threats-identified

## Rationale
Inspected: the cd prefix allow of `em-workflow/hooks/bash_guard.py` as changed by this feature (SPEC.md FR1-FR4, NFR3-NFR5), the two prose places it touches (FR5) and the regression tests (FR6). Tier: full. The path-check task declares `auth`, `input-handling` and `external-io`, so both boundaries below are analysed at deep depth. The hook grants `allow` to a command written by an agent, and the `<path>` in that command is resolved against the live file system in the hook's own process while Bash acts on it in another process; both crossings carry realistic Elevation of privilege and Denial of service threats, so the verdict holds.

Not recorded as threats, because SPEC.md places them out of scope: a procfs mounted elsewhere than /proc and other per-process file systems (SPEC A4), and a link changed between the hook's decision and Bash's cd (SPEC A5). Spoofing of the input `cwd` field, from which the area is derived, is not changed by this feature and has no row.

Domain consistency: task0001 declares `auth`, `input-handling` and `external-io`, and its implementation file appears in both `Boundary files` lines; its test file is not a boundary. task0002 declares none of the four depth domains; it edits only prose and a wording test, so it adds no boundary.

## Trust Boundaries

### TB-1: Hook process to Bash process
Crossing: the `allow` decision is computed from the hook process's own per-process view of the file system (its working directory, root, open file descriptors, process and thread identity) and is then acted on by Bash in a different process whose view can differ.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A cd prefix path written under /proc or /dev/fd (the attack form of the goal, `/proc/thread-self`, `/proc/self/fd`, `/dev/fd`, `/proc/<pid>`, `/proc/self/root` including the `/proc/self/root/..` prefix, and lexical variants such as `//proc`, `/./proc`, `/<dir>/../proc`) resolves below the area in the hook process while Bash lands outside it, so an approved command is auto-allowed outside `.claude/worktrees/em-workflow/` (FR1, FR2, FR3) | TM-1 | `is_below` is False when the written path, or any stage of the stage-by-stage logical or physical resolution, is under /proc or /dev/fd; no exception for the `/proc/self/root/..` prefix; the refused form is judged as if it had no cd prefix | task0001 AC-1, AC-2, AC-5 | VERIFICATION.md Performance / Security Verification TM-1 |
| Elevation of privilege | A link placed inside the area (agents can write there) whose target, or a stage reached while resolving through it, is under /proc or /dev/fd makes the path look like an ordinary in-area directory, so a check on the written path or on the final realpath alone misses it (FR1 (b), (c)) | TM-2 | Both stage-by-stage resolutions check the target text of every followed link and every stage reached after it, not only the final realpath | task0001 AC-3 | VERIFICATION.md Performance / Security Verification TM-2 |

### TB-2: Agent-written cd prefix path to the hook's path check
Crossing: the `<path>` text of a Bash command written by an agent (prompt-influenceable model output), together with links the agent can create inside the worktree area, enters the hook's authorization decision and drives file-system queries in the hook process.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A link loop or a very long link chain makes the new stage-by-stage resolution loop without end or run unboundedly, hanging the hook and with it an unattended run (NFR5) | TM-3 | The resolution counts followed links against a fixed bound equal to the kernel's own limit; a loop or exceeding the bound makes `is_below` False | task0001 AC-6 | VERIFICATION.md Performance / Security Verification TM-3 |
| Elevation of privilege | An error raised while a stage is probed or a link is read inside the new checks is treated as "nothing under /proc seen", so the decision falls through to the existing rule, which can allow (fail-open) (NFR4) | TM-4 | Only an absent component, or a non-directory with components remaining, ends a walk without refusal; every other OSError or ValueError makes `is_below` False, and the hook exits 0 with nothing on stderr | task0001 AC-6 | VERIFICATION.md Performance / Security Verification TM-4 |
