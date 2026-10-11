# Threat Model: cross-repo-write-guard

## Verdict
threats-identified

## Rationale

Inspected: SPEC.md and REQUIREMENTS.md (FR1–FR16, NFR1–NFR4) at the `full`
tier; no DESIGN.md (design step skipped). The feature adds a PreToolUse hook
that reads tool-call payloads (model-authored file paths and shell command
text, plus the session cwd), consults git and the filesystem, and returns a
permission decision to Claude Code. Three trust boundaries were found. Depth
is deep for all three: TB-1 through `input-handling`, TB-2 through
`external-io`, TB-3 through `auth` (the hook's output is a permission
decision). task0001 declares `auth`, `input-handling` and `external-io`; its
hook script and `hooks.json` appear in the Boundary files lines below.
task0002 declares none of the four depth domains.

Accepted by design, with no mitigation recorded: the hook is a confirmation
aid for a cooperating agent, not a sandbox. Destinations that cannot be
resolved statically (FR9), commands outside the FR7 list, strings run by
`bash -c` and `$( )` bodies (FR8), relative destinations after a
working-directory change (FR10), and compound commands other than subshells
and brace groups pass without output, following the fail-open objective
BO-3. Precedence between hooks (FR16) — another hook's `allow` not
overriding this hook's `ask` / `deny` — is a Claude Code property this
feature relies on and does not implement.

## Trust Boundaries

### TB-1: Tool-call payload → hook
Crossing: the PreToolUse payload Claude Code passes on stdin — `tool_name`, the model-authored `tool_input.file_path` / `tool_input.command` (text that untrusted content read by the model can shape), and the session `cwd` — enters the hook's parser.
Boundary files: em-workflow/hooks/cross-repo-write-guard.py, em-workflow/hooks/hooks.json
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A statically resolvable write outside the toplevel escapes judgment because the analysis misreads shell syntax (a redirection form, a `tee` / `sed -i` / `cp` / `mv` destination, or a write nested in a subshell, brace group, wrapper or after leading assignments), or because one tool path is not hooked, so the write runs without the confirmation FR6 requires (FR1, FR7, FR8) | TM-1 | The analysis follows shell quoting and grouping and recognizes every FR7 form within every FR8 scope; the same script is registered on both the `Bash` and `Write\|Edit\|MultiEdit` matchers | task0001 AC-1, AC-5, AC-6 | VERIFICATION.md Performance / Security Verification TM-1 (TS-6, TS-7, TS-11) |
| Denial of service | Text that is not a write — heredoc bodies, quoted strings, comments, `bash -c` strings, `$( )` bodies, descriptor duplication, `/dev/null`-style sinks, unresolvable or post-`cd` relative destinations, a command that cannot be parsed — is judged as an outside write; the false `ask` becomes `deny` in unattended runs and stops them (FR5, FR8, FR9, FR10) | TM-2 | Non-command text is never read as a command; descriptor duplication and the listed `/dev` paths are not destinations; unresolvable and post-`cd` relative destinations are dropped one by one; a command that cannot be parsed as a whole yields no output | task0001 AC-5, AC-6, AC-7 | VERIFICATION.md Performance / Security Verification TM-2 (no-output rows of TS-5 to TS-9) |

### TB-2: Hook → git process and filesystem
Crossing: the payload `cwd` becomes the working directory of a git process, and the judgment depends on filesystem state (symbolic links, worktree layout, sibling directories) that repository content controls.
Boundary files: em-workflow/hooks/cross-repo-write-guard.py
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A destination that is outside in reality appears inside: a symbolic link under the toplevel pointing outside (also for a not-yet-existing file), a sibling directory sharing the toplevel's string prefix, or a write from a linked worktree into the main working tree compared against a broader root (FR3, FR4) | TM-3 | Compare only against the cwd's own `--show-toplevel`; resolve destination, toplevel and exclusion roots with real-path semantics along the longest existing prefix; compare at path-component boundaries | task0001 AC-4 | VERIFICATION.md Performance / Security Verification TM-3 (TS-3, TS-4) |
| Elevation of privilege | Payload-controlled text (the `cwd`, a directory name containing shell metacharacters) reaches a shell when git is started and runs as a command (NFR2) | TM-4 | git is started as an argument vector with no shell; payload values never become command-line text; the `cwd` is passed only as the process working directory | task0001 AC-9 | VERIFICATION.md Performance / Security Verification TM-4 |
| Denial of service | A git process that does not answer (slow filesystem, lock) holds every tool call until the hook's 15-second timeout (NFR3) | TM-5 | git runs under a time limit shorter than 15 seconds; on expiry the process is terminated and the hook outputs nothing | task0001 AC-9 | VERIFICATION.md Performance / Security Verification TM-5 (TS-14) |

### TB-3: Hook decision → Claude Code permission system
Crossing: the hook's stdout becomes a permission decision that controls whether a tool call runs.
Boundary files: em-workflow/hooks/cross-repo-write-guard.py
Depth: deep (auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | An `allow` decision would skip the user's own permission rules and other hooks' prompts for the tool call (FR6) | TM-6 | The hook outputs only `ask`, `deny` or nothing, on every path | task0001 AC-8 | VERIFICATION.md Performance / Security Verification TM-6 (TS-10) |
| Denial of service | In an unattended run nobody can answer an `ask`, so the run stalls (FR6) | TM-7 | When `CLAUDE_BATCH` is active the decision is `deny` with a reason stating the downgrade, so the agent receives a tool result and can continue | task0001 AC-8 | VERIFICATION.md Performance / Security Verification TM-7 (TS-10) |
