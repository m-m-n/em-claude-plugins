# Threat Model: codex-stop-hook-tty-reaper

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md (FR1-FR8, NFR1-NFR6), and the two
`run_codex_exec.sh` wrappers with their existing PreToolUse registration.
Tier: full. The Stop hook runs outside the Codex sandbox, with hook trust
bypassed, and sends SIGTERM / SIGKILL. Its inputs are its standard input
(written by Codex), its command-line argument and the process table. Commands
that Codex runs for the reviewed repository and the model create part of that
process table. The command line is built by the wrapper from the plugin's
install path and is run by Codex through a POSIX shell. task0001 declares
`input-handling` and `external-io`, which set TB-1 to deep. TB-2 (task0002,
`config-infra` / `api-contract`) is standard. The test modules
(`tests/test_codex_hook_tty_reaper.py`, `tests/test_codex_hook_wrapper_args.py`)
are not boundary files: they only start and signal processes of their own
(NFR4), and they never reach a real Codex.

## Trust Boundaries

### TB-1: Codex process tree and hook standard input -> Stop hook
Crossing: data from the Codex launch reaches the Stop hook, an unsandboxed
process that sends SIGTERM / SIGKILL. The data is the JSON that Codex writes
to the hook's standard input, plus the process-table entries (parent link,
start time, process-name field, standard-input link) of processes created by
commands Codex runs for the reviewed repository and the model.
Boundary files: em-workflow/scripts/codex-hook-tty-reaper.py, em-review/scripts/codex-hook-tty-reaper.py
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Fields in the hook's standard input name process IDs, paths or a working directory, and so steer which processes get signalled. The stopped set then grows past the Codex descendants (NFR6, NFR1) | TM-1 | The hook only checks that standard input is one JSON object. The target determination uses none of its fields: it reads only the anchor argument and the process table | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-1 (TS-15) |
| Spoofing | The hook identifies the wrong process as the Codex that launched it, either by a process name that a sandboxed command can imitate or by walking up to an ancestor that is too high (the calling Claude Code session or above). Another Codex launched in parallel, and its descendants, then get signalled (FR3, NFR1) | TM-2 | The anchor is the PID of the wrapper's own process, which the wrapper itself puts on the hook command line. The hook acts only when the argument list is exactly one ASCII-decimal value greater than 1 that names a proper ancestor of the hook. The hook and every one of its ancestors are excluded. Any other argument list stops nothing | task0001 AC-5, task0002 AC-1 | VERIFICATION.md Performance / Security Verification, TM-2 (TS-1, TS-6, TS-15) |
| Spoofing | A target ends after enumeration, and an unrelated process reuses its PID before the SIGTERM or the SIGKILL. The signal then lands on a process that is not a Codex descendant (FR4, NFR1) | TM-3 | Right before each SIGTERM and each SIGKILL, the hook re-reads the target's start time and compares it with the value recorded at enumeration. If it differs, that target gets no further signal | task0001 AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 (TS-16) |
| Tampering | A process created by a Codex-run command uses a process name with spaces and parentheses that imitate the fields after it. A naive reader of the process status record then takes a forged parent or start time, and a process that has left the tree is counted among the descendants (NFR6, NFR1) | TM-4 | Parent, state and start time are read from after the last closing parenthesis of the process-name field. A record that cannot be read that way contributes no target | task0001 AC-2 | VERIFICATION.md Performance / Security Verification, TM-4 (TS-15) |
| Denial of service | The hook delays or changes the end of the Codex turn. Causes: standard input left open, an unbounded wait, an exception raised by a malformed process entry, or output that Codex reads as a block / continue decision (FR5, NFR2) | TM-5 | Standard input is read for a fixed time at most, and there is a single wait phase of 0.5 seconds. Every path, failures included, ends with exit status 0 and writes nothing to standard output or standard error. After a failure, no further signal is sent | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-5 (TS-7) |

### TB-2: run_codex_exec.sh -> Codex launch configuration -> POSIX shell
Crossing: the wrapper puts its own location and its PID into a hook command.
The location is the plugin's install path, which may contain any character.
Codex parses the command as TOML and runs it through a POSIX shell, outside
the sandbox and with hook trust bypassed.
Boundary files: em-workflow/scripts/run_codex_exec.sh, em-review/scripts/run_codex_exec.sh
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A plugin path that holds quotes, spaces or shell / TOML metacharacters breaks out of the Stop hook command, so Codex runs something other than the hook, outside the sandbox (FR1, FR2) | TM-6 | The hook path is single-quoted for the shell, and the whole command is then written as a TOML basic string. This is the same two-layer encoding the PreToolUse registration uses. The anchor is a decimal number that the wrapper produces itself | task0002 AC-3 | VERIFICATION.md Performance / Security Verification, TM-6 (TS-17) |
