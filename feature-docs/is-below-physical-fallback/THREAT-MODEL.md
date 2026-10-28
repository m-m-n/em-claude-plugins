# Threat Model: is-below-physical-fallback

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR8, NFR1-NFR5, Security Considerations, Assumptions A1-A5) at the reduced tier (no REQUIREMENTS.md, design step skipped). The changed path check decides whether a cd-prefixed Bash command may be auto-allowed by the PreToolUse hook without a permission prompt. The path inside that prefix is agent-generated text that untrusted content can influence, and the filesystem it resolves against (symbolic links inside or outside the worktree area) can be shaped by repository content. That makes the check a privilege boundary. It is analysed at deep depth because task0001 declares the `auth` and `input-handling` domains. The boundary file is the task's only file that implements the decision; the protocol document and the test file do not implement it.

Considered and not recorded as rows:
- Spoofing, Repudiation and Information disclosure do not realistically apply. The hook authenticates no party, this feature changes no audit record, and the hook outputs only a decision.
- A filesystem change between the hook's check and Bash's cd (time of check versus time of use) needs a concurrent actor that can already write the filesystem. That window is inherent to every path-based check. It already existed for the logical-path branch before this feature, and this feature does not address it.
- Per-process paths (for example under the process's own /proc entry for its working directory) resolve in the hook's process, while Bash resolves them in the shell's process. SPEC A3 explicitly leaves them without special handling, so no mitigation is recorded for them. The fallback branch makes forms that collapse such a path lexically into a non-existent logical path judgeable by their physical path. Before this feature those forms were rejected. The outcome depends on the hook and the shell sharing a working directory. This is reported as an open question, not mitigated here.

## Trust Boundaries

### TB-1: cd-prefixed Bash command to the hook's auto-allow decision
Crossing: the Bash tool input (agent-generated command text that untrusted content the agent read can influence) enters the PreToolUse hook. The hook can grant allow and so skip the user's permission prompt, which is a privilege change. The path in the cd prefix is resolved against a filesystem whose symbolic links can come from repository content.
Boundary files: em-workflow/hooks/bash_guard.py
Depth: deep (auth, input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A path whose logical destination is an existing directory outside the area, while its physical destination is inside the area (a symbolic link followed by `..`), is allowed. Bash's logical cd then runs the approved string outside the area (FR2, FR4). | TM-1 | When the logical path is an existing directory, allow only if the logical path and the physical path are both existing directories strictly below the area. The physical-path fallback is entered only when the logical path is not an existing directory. That is the condition under which Bash's logical move fails. | task0001 AC-3 | VERIFICATION.md TM-1 (TS-3) |
| Elevation of privilege | In the fallback branch, a physical destination is allowed that is outside the area, is the area itself, is a sibling sharing only a name prefix, does not exist, or is a file (FR5). | TM-2 | In the fallback branch, allow only a physical path that is an existing directory strictly below the area, compared by path components, never by string prefix. | task0001 AC-4 | VERIFICATION.md TM-2 (TS-4, TS-9) |
| Elevation of privilege | To mimic Bash's cd fallback, the path is handed to a shell or another child process. That executes attacker-shaped path text before any approval (NFR3). | TM-3 | The path is resolved in-process only. It is never given to a child process as a working directory or an argument. | task0001 AC-6 | VERIFICATION.md TM-3 (TS-5) |
| Elevation of privilege | Input that makes the new resolution step raise aborts the hook before the decisions it evaluates after the path check, such as the forbidden-pattern deny and the declared-but-unapproved deny. A command the hook would deny then reaches the normal permission flow instead (NFR4, FR6). | TM-4 | An OSError or ValueError raised during path resolution or comparison makes the path check return False. The command is then treated as having no cd prefix, the remaining decisions still run, and the hook exits 0 with nothing written to stderr. | task0001 AC-5 | VERIFICATION.md TM-4 (TS-7) |
