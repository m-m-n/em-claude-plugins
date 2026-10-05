# Threat Model: codex-interactive-guard-hook

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md and REQUIREMENTS.md at tier `full`, plus the task decomposition.
- task0001 (the hook) declares `input-handling` and `api-contract`.
- task0002 (the wrapper registration) declares `config-infra`, `external-io` and `auth`.
- task0003 (the reviewer guidance) declares `config-infra`.

`input-handling` deepens TB-1. `external-io` and `auth` deepen TB-2 and TB-3.

Three boundaries carry realistic threats:
- model-generated command text entering the hook
- a run-time filesystem path being interpolated into Codex configuration and a command line
- the hook-trust gate being lifted on every launch

Accepted residual risks, with no mitigation recorded:
- **Deliberate evasion of the guard**: option-bearing wrappers, shell expansions, `eval`, shell nesting deeper than one `-c` literal, interaction through `write_stdin`, REPLs opened from inside code, and REPLs opened by subcommands. These are passed by design (SPEC A7, FR11, NFR2). The hook guards against accidental launches of a REPL; it is not a sandbox.
- **Configuration layers the wrapper does not author**: the `--litellm` path loads user-level Codex configuration by design (SPEC A3). Whether Codex 0.160.0 also loads repository-local configuration under the bypass flag was confirmed afterwards by the codex-repo-hook-trust feature and is no longer open: see the "Status after codex-repo-hook-trust" paragraph under TB-3 and `feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md`.

Not boundaries:
- the static reviewer guidance text in `codex-reviewer.md`, which is authored in this repository and has nothing interpolated into it
- the hook's deny reason, which is fixed text and discloses nothing
- the test modules

Domain consistency: every task declaring `input-handling`, `external-io` or `auth` (task0001, task0002) has files on a `Boundary files` line below. task0003 declares none of the four deepening domains.

## Trust Boundaries

### TB-1: Codex tool-call command text into the interactive-guard hook
Crossing: command strings composed by the Codex model are attacker-influenceable, because they are shaped by repository content under review and by prompt text. They cross from the Codex agent process into the hook as the PreToolUse JSON on stdin. The hook's verdict decides whether Codex starts the command on a pseudo-terminal on the host.
Boundary files: em-workflow/scripts/codex-hook-interactive-guard.py, em-review/scripts/codex-hook-interactive-guard.py
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | Codex starts an interpreter or shell that waits for interactive input on a pseudo-terminal that is never closed for it (FR6, FR7). This includes versioned names (FR8) and launches inside compound commands or one shell `-c` literal level (FR9). After the session ends, the process stays orphaned and keeps a host CPU core busy. | TM-1 | The hook denies every launch that matches FR6 or FR7 under FR8 name matching after the FR9 parse, and returns the FR12 deny object, so Codex never starts the command | task0001 AC-1, AC-2 | VERIFICATION.md TS-1, TS-9; Performance / Security Verification item TM-1 |
| Denial of service | Unusual or malformed command text is misclassified, or crashes the parse, so legitimate reviewer commands are denied and an unattended review stalls (FR10, FR11, NFR2). Examples: text in quotes, comments or heredoc bodies; in-place-edit `-i` flags; `-i` after an operand; option-bearing wrappers; unbalanced quoting; non-JSON input. | TM-2 | Only launches positively identified under FR6–FR9 are denied. Quoted, commented and heredoc-body text, `-i` after the first operand or a code-option value, names outside the families, input that cannot be parsed, and any unexpected error all produce no output and exit 0. | task0001 AC-3, AC-4 | VERIFICATION.md TS-2, TS-3; Performance / Security Verification item TM-2 |

### TB-2: Run-time hook path into Codex configuration and the hook command line
Crossing: the wrapper resolves its own plugin `scripts/` directory at run time; the installation or checkout chooses that location, not the wrapper. It interpolates the path into a TOML string passed with `-c`. Codex parses that string as configuration and later runs the resulting command line to start the hook.
Boundary files: em-workflow/scripts/run_codex_exec.sh, em-review/scripts/run_codex_exec.sh
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A path containing a space, a quote, a backslash or a shell metacharacter breaks out of the TOML string or out of the command's word boundaries (FR1–FR3, SPEC A6). Codex then fails to load the configuration, or starts a command other than the hook. | TM-3 | The path is escaped for the command-execution layer confirmed on Codex 0.160.0, and the command is then escaped as a TOML string, so the configured command resolves to exactly the hook's absolute path | task0002 AC-4 | VERIFICATION.md TS-10; Performance / Security Verification item TM-3 |

### TB-3: Hook-trust gate lifted on every Codex launch
Crossing: a privilege change. `--dangerously-bypass-hook-trust` lifts Codex's hook-trust gate for the whole launch. Hook commands from every configuration layer Codex loads for that launch then run on the host, outside the Codex sandbox, without a trust decision.
Boundary files: em-workflow/scripts/run_codex_exec.sh, em-review/scripts/run_codex_exec.sh
Depth: deep (auth, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | With the gate lifted, hook definitions from a configuration layer the wrapper does not author, such as user-level Codex configuration, would run unsandboxed and without a trust prompt (FR1–FR4, NFR5) | TM-4 | Every launch keeps the config-isolation flags it carries today: `--ignore-user-config` where present, and `--ignore-rules`. The bypass flag is only ever added alongside them, so lifting the gate does not widen which configuration layers a launch loads. | task0002 AC-5 | VERIFICATION.md TS-6; Performance / Security Verification item TM-4 |

#### Status after codex-repo-hook-trust

The open question of the Rationale (do repository-local Codex hooks run under the bypass flag) was answered on Codex 0.160.0 by the codex-repo-hook-trust feature. The evidence is in `feature-docs/codex-repo-hook-trust/HOOK-TRUST-FINDINGS.md`; this paragraph records the status and does not restate the evidence.

Per-route verdicts, for hook definitions in the working directory's `.codex/config.toml` and `.codex/hooks.json` and in the same files one directory above (the repository root):
- em-workflow default route (`--ignore-user-config`): repository hooks did not run, in readonly and in readwrite.
- em-review default route (`--ignore-user-config`): repository hooks did not run, in readonly and in readwrite.
- em-workflow `--litellm` route: repository hooks ran when the user configuration trusts the project (readonly and readwrite), and in readwrite also when it does not, because Codex marks an unmarked project trusted itself under a writable sandbox. This was the only executing route.

Every "did not run" verdict has a control in which the same definitions ran in the same environment. Three events could not be observed on any route: PermissionRequest (`codex exec` runs with approval policy `never`) and SubagentStart / SubagentStop (Codex rejects the model's `spawn_agent` call). The protective specification below does not depend on them, because it keeps the whole project layer from loading.

Change: the `--litellm` route of `em-workflow/scripts/run_codex_exec.sh` now runs `codex exec` with `CODEX_HOME` set to a launch-dedicated directory, created for the run and removed on exit. It holds a copy of the `litellm` profile and a `config.toml` that marks the working directory and every ancestor `untrusted`. The argv is unchanged; `-p litellm -m MODEL`, `--ignore-rules`, the guard registration and the bypass flag stay. The default routes of both wrappers keep their launch composition. A probe of the changed route, with the project trusted and with it unmarked, in both modes, showed no repository hook running (tests: `tests/test_codex_repo_hook_trust.py`, a stub check and a real-Codex check).

The wrapper's guard still fires on every route, including the changed one, so the A1 exception (a route on which the guard no longer fires) is not triggered. The wrapper's `-c hooks.PreToolUse` merges with a repository PreToolUse definition rather than replacing it, so a repository hook that reaches execution runs alongside the guard and the guard is no defense against it.

Consequences accepted with the change: the `--litellm` route no longer loads the user's base `config.toml` (only the `litellm` profile), so SPEC A3's statement that the path loads user-level configuration no longer holds for the base file; and a writable-sandbox run on a default route still writes a trust entry for the project into `$CODEX_HOME/config.toml` without reading it, which has no effect on those launches. Other Codex versions are outside this record.
