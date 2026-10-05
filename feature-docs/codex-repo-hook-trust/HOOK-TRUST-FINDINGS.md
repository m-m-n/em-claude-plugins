# Hook trust findings: codex-repo-hook-trust

Record of whether hook definitions in the working directory's Codex configuration
(repository hooks) execute under each launch route of the em-workflow and em-review
Codex wrappers, measured on Codex 0.160.0. Written by task0001; the auxiliary Codex
invocations of section 2 were re-run under temporary Codex homes by task0002 (sections 2.1
and 2.2). The tests, the wrapper comments and TB-3 of
`feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md` follow this record; a later
change that contradicts it updates this record first.

## 1. Result in brief

| Route | Executes repository hooks (before the change) | Launch after the change |
|---|---|---|
| em-workflow default (`--ignore-user-config`), P1 | no, readonly and readwrite | unchanged |
| em-workflow `--litellm MODEL`, user config trusts the project, P2 | yes, readonly and readwrite | launch-dedicated Codex home (section 8) |
| em-workflow `--litellm MODEL`, user config does not trust the project, P3 | readonly: no. readwrite: yes | launch-dedicated Codex home (section 8) |
| em-review default (`--ignore-user-config`), P4 | no, readonly and readwrite | unchanged |

Branch taken: **Branch E**. The only executing route is the `--litellm` route of the
em-workflow wrapper, which em-review does not have. That route was changed; the other
routes keep their launch composition. After the change no repository hook ran on the
changed route in either mode (section 9), and the wrapper's own interactive-guard
registration still fired there.

Three events could not be observed on any route (PermissionRequest, SubagentStart,
SubagentStop); the reasons are in section 6.3.

## 2. Environment

- Codex as reported by the binary used: `codex-cli 0.160.0` (`codex --version`, run under
  temporary homes: section 2.1, row 1). The real-Codex test (TS2) skips unless the binary
  reports exactly this.
- Platform: Linux, bash and zsh available; the wrappers ran under bash.
- Codex home isolation. Every Codex command line this record cites as evidence (the
  auxiliary invocations of section 2.1, the probes, the positive controls, the post-change
  probes) ran with `HOME` and `CODEX_HOME` set, on the same command line, to temporary
  directories created for that one invocation, with `CODEX_HOME` = `<HOME>/.codex` (the
  one exception in form is section 9, where the changed wrapper points `CODEX_HOME` at its
  own temporary launch home). Section 2.2 states the two values for every group of command
  lines. The user's real HOME and real Codex home are neither read, listed nor written for
  any fact in this record (no configuration, session or credential file of them is touched).
  The `codex` executable is the installed one found on `PATH`; it is only executed.
- Every probe launch ran with `HOME` and `CODEX_HOME` set to directories created for that
  one probe, with `CODEX_HOME` = `<HOME>/.codex`. The temporary home alone held:
  - `config.toml`: empty, or one `[projects."<path>"]` table with `trust_level`, depending
    on the condition (sections 5 and 6.4);
  - `litellm.config.toml` (P2, P3 only): the profile `-p litellm` reads, with a
    `[model_providers.litellm]` table (`env_key = "LITELLM_API_KEY"`, `wire_api =
    "responses"`, `base_url` of the local LiteLLM proxy).
- Credentials: the only credential is the variable `LITELLM_API_KEY`. It reached Codex
  through the environment inherited by the probe processes; its name is the only thing
  this record knows about it. Nothing was copied from the user's real Codex home, no login
  step was run, and no credential value appears in this record, in the tests or in their
  output.
- Model: `muse-spark` through the local LiteLLM proxy (the Standard tier, not the
  contributor tier).
- Temporary repository per probe: `git init`, `<repo>/sub` is the working directory
  passed with `-C`, `<repo>` is the git root (one directory above the working directory).

### 2.1 Auxiliary Codex invocations: isolated re-runs

The auxiliary invocations that earlier versions of this section cited (`codex --version`,
`codex --help` and subcommand help, `codex features list`) were run without temporary
homes. On 0.160.0 `codex features list` reads `$CODEX_HOME/config.toml`, so those runs read
the user's real Codex home. They are **superseded**: none of their output is cited
anywhere in this record, and every fact those runs gave is re-derived below from the runs
listed here. The same holds for a `codex --version` run made while this re-run was being
prepared, before its temporary homes were in place. (A `strings` scan of the codex binary
file made earlier is not a Codex invocation; nothing from it is cited either.)

Every row below was run, after the earlier runs, with the same setup:

- `<aux>` is a directory created fresh for that one invocation (`mktemp -d`).
  `HOME=<aux>/home` and `CODEX_HOME=<aux>/home/.codex` are set on the same command line as
  `codex`. The environment is cleared (`env -i`) except `PATH`, `HOME`, `CODEX_HOME` and
  `LANG`. No credential variable is set: these commands need none, and the variable the
  probes inherited (`LITELLM_API_KEY`) is not present.
- Working directory `<aux>/repo/sub` (`git init` in `<aux>/repo`), the layout the probes used.
- The temporary `CODEX_HOME` is **rebuilt from this record's own description** of the
  probes' configuration (the `config.toml` and `litellm.config.toml` bullets above), file
  by file: `config.toml` holds one `[projects."<aux>/repo"]` table with `trust_level =
  "trusted"`; `litellm.config.toml` holds `[model_providers.litellm]` with `name =
  "LiteLLM proxy"`, `env_key = "LITELLM_API_KEY"`, `wire_api = "responses"` and, as the
  `base_url` of the local LiteLLM proxy, the loopback address `http://127.0.0.1:4000/v1`
  (no row makes a request to it). The probes' configuration, as this record describes it,
  sets no feature, so none is set. **Nothing was copied from the user's real HOME or Codex
  home, and no configuration, session or credential file there was read, listed or
  written.** (The installed `codex` executable, found on `PATH`, is only executed.) The
  same configuration is rebuilt for every row, so `codex features list` (row 5) reads the
  probes' configuration as this record describes it.
- Bound: each invocation ran under a wall-clock bound of at most 120 seconds (the per-command
  timeout of the run harness) and exited by itself (`rc` 0) before it. In rows 9a to 9c the
  client additionally bounds the exchange to 60 seconds, closes the app-server's stdin after
  the answer and waits for it to exit. No process of these runs was left behind (checked
  after the runs).
- Every run prints one `WARNING: proceeding, even though we could not create PATH aliases:
  Refusing to create helper binaries under temporary dir "/tmp" ...` line from the
  temporary Codex home (section 8.3). It is not part of the output cited below.

Command lines (`HOME` and `CODEX_HOME` as above, `codex` first-on-`PATH`, no credential
variable):

| Row | Command line | Output the record relies on |
|---|---|---|
| 1 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex --version` | `codex-cli 0.160.0` |
| 2 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex --help` | Subcommands include `exec`, `features`, `app-server`. `-p, --profile`: "Layer $CODEX_HOME/<name>.config.toml on top of the base user config". `--dangerously-bypass-hook-trust`: "Run enabled hooks without requiring persisted hook trust for this invocation." |
| 3 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex exec --help` | The flags the wrappers pass exist: `-c/--config`, `-m/--model`, `-p/--profile`, `-s/--sandbox` (`read-only`, `workspace-write`, `danger-full-access`), `-C/--cd`, `--skip-git-repo-check`, `--ignore-rules`, `--output-schema`, `--color`, `--dangerously-bypass-hook-trust`, and `--ignore-user-config`: "Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`". |
| 4 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex features --help` | Subcommands `list`, `enable`, `disable`. |
| 5 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex features list` | 154 features, each with stage and effective state. The hook-related ones: `hooks` stable true; `plugin_hooks` removed false. |
| 6 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex app-server --help` | Subcommands `daemon`, `proxy`, `generate-ts`, `generate-json-schema`; `--stdio` selects the stdio transport. |
| 7 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex app-server generate-json-schema --help` | `-o, --out <DIR>` is required. |
| 8 | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex app-server generate-json-schema --out <aux>/schema` | `HookEventName` and `HookSource` as listed in section 3 step 1: 12 events and 11 sources, in that order. |
| 9a | `HOME=<aux>/home CODEX_HOME=<aux>/home/.codex codex app-server --stdio`, then `initialize`, `initialized`, `hooks/list` with `cwds: ["<aux>/repo/sub"]`; `<aux>/repo/sub` holds a one-event (`SessionStart`) hook in each of the 13 candidate files of section 3 step 2; temporary user config trusts `<aux>/repo` | 1 hook listed: `source` `project`, `trustStatus` `untrusted`, file `<aux>/repo/sub/.codex/hooks.json`. |
| 9b | as 9a; `<aux>/repo/sub/.codex/` holds `config.toml` and `hooks.json`, each with one hook for every one of the 12 events; temporary user config trusts `<aux>/repo` | 24 hooks listed (12 from `hooks.json`, 12 from `config.toml`), all `source` `project`, `trustStatus` `untrusted`; warning: `loading hooks from both <aux>/repo/sub/.codex/hooks.json and <aux>/repo/sub/.codex/config.toml; prefer a single representation for this layer`. |
| 9c | as 9b, with a temporary user config that has no trust entry (empty `config.toml`) | 0 hooks listed. |

Facts re-derived from these runs, and whether each is unchanged from what this section
derived before the re-run:

| Fact | Derived before | Re-derived (row) | Unchanged |
|---|---|---|---|
| Reported version | `codex-cli 0.160.0` | `codex-cli 0.160.0` (1) | Yes |
| Hook event list | 12 events: `preToolUse`, `permissionRequest`, `postToolUse`, `preCompact`, `postCompact`, `sessionStart`, `sessionEnd`, `userPromptSubmit`, `subagentStart`, `subagentStop`, `stop`, `interrupt` | the same 12, same order (8) | Yes |
| Hook source values | 11 values; only `project` comes from the repository under review; `sessionFlags` is what the wrapper's `-c hooks.PreToolUse=...` produces | the same 11 values (8) | Yes |
| Hook locations | Of the 13 candidate files only `.codex/hooks.json` was listed, with source `project`; `.codex/config.toml` and `.codex/hooks.json` together listed both, with the single-representation warning; 24 hooks against 0 for the same two-file repository, trusted and not trusted | the same (9a, 9b, 9c) | Yes |
| Feature state | The record named `codex features list` and cited no value from it | `hooks` stable true (enabled); `plugin_hooks` removed false (5) | No earlier cited value to differ from. The state is the one the probe results presuppose (repository hooks ran on the executing routes, so the `hooks` feature was on); no probe result, per-route verdict or the branch changes |

The result matrix (section 6.1), the per-route verdicts (section 7) and the branch (section
1) are unchanged by these re-runs.

### 2.2 `HOME` and `CODEX_HOME` of every Codex command line in this record

| Command lines | Where | `HOME` | `CODEX_HOME` |
|---|---|---|---|
| Auxiliary invocations, rows 1 to 9c | 2.1; the re-derived content of section 3 steps 1 and 2 and of its final paragraph | `<aux>/home` | `<aux>/home/.codex` |
| Probes P1 to P4, readonly and readwrite, every kind, and the `codex` shim that forwards to the real binary | section 5 | `<probe>/home` | `<probe>/home/.codex` |
| Section 3 step 3, the directory-scope observation | one pre-change probe launch (P2 readwrite with the extra `<repo>/sub/deeper/.codex/`, section 10 `deeperdir`) | `<probe>/home` | `<probe>/home/.codex` |
| Positive controls (`stripiuc`, P2 ro for P3 ro) | 6.2 | `<probe>/home` | `<probe>/home/.codex` |
| Attempts at the unobservable events | 6.3 (P2 launches) | `<probe>/home` | `<probe>/home/.codex` |
| Trust-gate observations (`addiuc`, `mixedroot*`, `ro444`, `sandboxc`, `slash*`, `symlinkC`, `untrust*`, `sandbox`) and the same-key override runs | 6.4, 6.5 | `<probe>/home` | `<probe>/home/.codex` |
| Pre-change rows of the run log | 10 | `<probe>/home` | `<probe>/home/.codex` |
| Post-change probes and post-change rows of the run log (P2, P3, changed wrapper) | 9, 10 | `<probe>/home` | the wrapper's launch-dedicated home `${TMPDIR:-/tmp}/codex-launch-home.XXXXXX` (a fresh temporary directory per launch, section 8.1); `<probe>/home/.codex` is only what the wrapper copies the probe's `litellm.config.toml` from |
| Real-Codex test TS2, its control launch and its wrapper launch | 11 | `<work>/home` | `<work>/codex-home` (`<work>` a temporary directory the test creates) |
| TS2's version check (`codex --version`) | 11 | one scratch temporary directory | the same scratch temporary directory |
| Stub-codex test TS1 | 11 | `<work>/home` | `<work>/user-codex-home`; on the changed route, the launch-dedicated home |

No command line of this record names the user's real HOME or Codex home as a place read or
written for evidence.

## 3. Hook locations and events under test

How the list was established (all on 0.160.0; steps 1 and 2 are the isolated re-runs of
section 2.1, rows 8 and 9a to 9c, under temporary `HOME` and `CODEX_HOME`):

1. `codex app-server generate-json-schema` (section 2.1, row 8). The schema defines:
   - `HookEventName`: `preToolUse`, `permissionRequest`, `postToolUse`, `preCompact`,
     `postCompact`, `sessionStart`, `sessionEnd`, `userPromptSubmit`, `subagentStart`,
     `subagentStop`, `stop`, `interrupt` (12 events);
   - `HookSource`: `system`, `user`, `project`, `mdm`, `sessionFlags`, `plugin`,
     `cloudRequirements`, `cloudManagedConfig`, `legacyManagedConfigFile`,
     `legacyManagedConfigMdm`, `unknown`. Only `project` comes from the repository under
     review; `sessionFlags` is what the wrapper's `-c hooks.PreToolUse=...` produces.
2. `hooks/list` on `codex app-server --stdio` (section 2.1, rows 9a to 9c), given a temporary
   repository holding a one-event hook in every candidate file below. Only
   `.codex/hooks.json` was listed, with source `project`:
   `.codex.toml`, `codex.toml`, `hooks.json`, `hooks/hooks.json`,
   `.codex-plugin/hooks.json`, `.agents/hooks.json`, `.claude/settings.json`,
   `.claude/settings.local.json`, `.codex/hooks.toml`, `.codex/requirements.toml`,
   `.codex/settings.json`, `.codex/hook.json`, `.codex/hooks.json`.
   A second listing with `.codex/config.toml` and `.codex/hooks.json` both present listed
   both, and Codex warned `loading hooks from both ... hooks.json and ... config.toml;
   prefer a single representation for this layer`.
3. Directory scope, by observation: a hook in `<repo>/.codex/` (the directory above the
   working directory) and one in `<repo>/sub/.codex/` (the working directory) both ran;
   a hook in `<repo>/sub/deeper/.codex/` (below the working directory) never ran
   (a pre-change `--litellm`, trusted, readwrite probe launch, run with `HOME=<probe>/home`
   and `CODEX_HOME=<probe>/home/.codex`: all 24 markers of the two existing directories,
   none from the lower one). Project layers are therefore the working directory and its
   ancestors.

Locations probed (repository-controlled, `source = project`), four per event:

| Location key | File |
|---|---|
| `config_toml` | `<working directory>/.codex/config.toml`, `[[hooks.<Event>]]` tables |
| `hooks_json` | `<working directory>/.codex/hooks.json` |
| `ancestor_config_toml` | `<git root, one level above>/.codex/config.toml` |
| `ancestor_hooks_json` | `<git root, one level above>/.codex/hooks.json` |

Events probed: all 12 above.

`hooks/list` gives the gate itself (section 2.1, rows 9b and 9c, run with `HOME=<aux>/home`
and `CODEX_HOME=<aux>/home/.codex`). With the temporary user config marking the repository
trusted it listed the project hooks (source `project`, `trustStatus` `untrusted`, which is
the hook-level trust that `--dangerously-bypass-hook-trust` lifts); with no trust entry it
listed none (24 hooks and 0 hooks for the same two-file repository).

## 4. Hook definitions

Each location x event has its own hook. The command is a marker writer:

```sh
#!/bin/sh
cat > "<probe markers dir>/$1.$2"      # $1 = location key, $2 = event name
exit 0
```

so a hook that ran leaves `<location>.<Event>` in the markers directory, holding the hook
input JSON. The markers directory is outside the repository. Hooks run on the host,
outside the Codex sandbox, so a marker is written in readonly mode too (P2 readonly
produced markers). The observation does not depend on the sandbox permitting the hook's
own effect, and the readwrite result did not have to decide anything. The same hook set is written as `[[hooks.<Event>]]` tables in `config.toml` and
as a `{"hooks": {...}}` object in `hooks.json`, for both directories. Hook timeouts are 20
seconds in the definitions; Codex clamps `SessionEnd` and `Interrupt` to 3 seconds.

## 5. Probe commands

Every probe starts the wrapper itself, so the argv is the wrapper's own. Credentials appear
as variable names only. Each command line below carries `HOME=<probe>/home` and
`CODEX_HOME=<probe>/home/.codex`, both temporary directories created for that one probe.
The `codex` shim and the real `codex` it forwards to run with the environment of the
wrapper that starts them; only the changed `--litellm` route alters it (see below).

```
P1: HOME=<probe>/home CODEX_HOME=<probe>/home/.codex PATH=<probe>/bin:$PATH \
    em-workflow/scripts/run_codex_exec.sh {readonly|readwrite} -C <repo>/sub "<prompt>"
P2: HOME=<probe>/home CODEX_HOME=<probe>/home/.codex PATH=<probe>/bin:$PATH \
    em-workflow/scripts/run_codex_exec.sh {readonly|readwrite} --litellm muse-spark -C <repo>/sub "<prompt>"
    (temporary user config trusts <repo>)
P3: the P2 command line, HOME and CODEX_HOME included, with a temporary user config that
    has no trust entry
P4: HOME=<probe>/home CODEX_HOME=<probe>/home/.codex PATH=<probe>/bin:$PATH \
    em-review/scripts/run_codex_exec.sh {readonly|readwrite} -C <repo>/sub "<prompt>"
# LITELLM_API_KEY inherited by every line (name only)
```

Argv the wrapper hands to `codex` (path of the working directory and of the plugin shortened).
Before the change every one of these `codex` processes ran with `HOME=<probe>/home` and
`CODEX_HOME=<probe>/home/.codex`. After the change, on the `--litellm` route (P2, P3) the
wrapper sets `CODEX_HOME` to its launch-dedicated temporary home (section 8.1) and `HOME`
stays `<probe>/home`; on P1 and P4 both stay as before.

```
P1 readwrite: exec --color never --skip-git-repo-check --ignore-rules -s workspace-write -C <repo>/sub
              --ignore-user-config -c hooks.PreToolUse=[{matcher="Bash", hooks=[{type="command",
              command="python3 '<plugin>/scripts/codex-hook-interactive-guard.py'"}]}]
              --dangerously-bypass-hook-trust "<prompt>"
P2/P3 readwrite: the same without --ignore-user-config, with -p litellm -m muse-spark before the -c
P4 readonly:  exec ... --ignore-rules --ignore-user-config -s read-only -c model_reasoning_effort="xhigh"
              -C <repo>/sub -c hooks.PreToolUse=[...] --dangerously-bypass-hook-trust "<prompt>"
```

Differences from the wrapper's argv that a probe needed (probe-only, from a `codex` shim
placed first on PATH that forwards to the real binary under `timeout`):

- P1 and P4: the wrapper passes no model or provider on the default route, and the
  default provider needs a login that this investigation may not copy in. The shim adds
  `-m muse-spark -c model_provider="litellm" -c model_providers.litellm={name="LiteLLM
  proxy", base_url=<local proxy>, env_key="LITELLM_API_KEY", wire_api="responses"}` so the
  turn reaches the same model. `--ignore-user-config` is untouched.
- Every kind: the shim wraps the real codex in `timeout 150` (the outer harness bound is
  the shim bound plus 90 seconds); the `interrupt` kind uses `timeout -s INT 20`.
- `compact` kind: the shim adds `-c model_auto_compact_token_limit=1500`.
- Control runs (section 6.2) additionally change the shim as named there.

Prompts (kind) that make the events fire:

| Kind | Prompt | Fires |
|---|---|---|
| `main` | run `echo probe-ok`, then reply DONE | SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop, SessionEnd |
| `compact` | four `echo` commands one per tool call, auto-compact limit 1500 tokens | adds PreCompact, PostCompact |
| `interrupt` | run `sleep 60`; SIGINT after 20 seconds | adds Interrupt |
| `guard` | run `python3 -i` and say whether it was blocked | the wrapper's own guard |
| `sandbox` | attempt a write outside the workspace | sandbox check (section 8.3) |

Each (condition, mode, kind) was run once. The model is not deterministic, so a single run
can decline to call the tool (marked in the run log by `PreToolUse hook lines` 0); the
verdicts below are aggregated over the kinds and rest on the positive controls rather than
on any one run.

## 6. Results before the change

Every launch behind this section (the probes, the positive controls of 6.2, the attempts
of 6.3 and the observations of 6.4 and 6.5) is a probe command line of section 5 and ran
with `HOME=<probe>/home` and `CODEX_HOME=<probe>/home/.codex`, temporary directories
created for that one probe (section 2.2). A trust entry or a configuration write named in
this section refers to that temporary `config.toml`.

### 6.1 Matrix

Cell = executed (E), not executed (N) or unobservable (U), aggregated over the four kinds
for each condition and mode. Each cell stands for all four locations: in every cell the
four locations agreed (no cell is partial).

| Event | P1 ro | P1 rw | P2 ro | P2 rw | P3 ro | P3 rw | P4 ro | P4 rw |
|---|---|---|---|---|---|---|---|---|
| SessionStart | N | N | E | E | N | E | N | N |
| UserPromptSubmit | N | N | E | E | N | E | N | N |
| PreToolUse | N | N | E | E | N | E | N | N |
| PermissionRequest | U | U | U | U | U | U | U | U |
| PostToolUse | N | N | E | E | N | E | N | N |
| PreCompact | N | N | E | E | N | E | N | N |
| PostCompact | N | N | E | E | N | E | N | N |
| SubagentStart | U | U | U | U | U | U | U | U |
| SubagentStop | U | U | U | U | U | U | U | U |
| Stop | N | N | E | E | N | E | N | N |
| Interrupt | N | N | E | E | N | E | N | N |
| SessionEnd | N | N | E | E | N | E | N | N |

The full list of runs is the run log in section 10.

### 6.2 Positive controls behind each "not executed"

A "not executed" verdict stands only because the same hook definitions demonstrably ran in
a control launch in the same kind of environment.

| Verdict | Control | Control result |
|---|---|---|
| P1 and P4, ro and rw: N | The same wrapper and prompt kinds (`main`, `compact`, `interrupt`), with the shim removing `--ignore-user-config` and the temporary user config trusting `<repo>` (`stripiuc`) | All 9 observable events ran in all four locations, in both modes, on both wrappers (24 markers for `main`, 32 for `compact`, 16 to 20 for `interrupt`). The repository hooks do load where Codex reads the trust entry. |
| P3 ro: N | P2 ro, same mode and kinds; the only difference is the trust entry in the temporary user config | All 9 observable events ran in all four locations. |

### 6.3 Unobservable events

| Event | Reason it could not be observed | What was tried |
|---|---|---|
| PermissionRequest | `codex exec` runs with approval policy `never` (the launch banner prints `approval: never`); no run produced an approval request | readwrite P2 with a prompt asking to run `touch` on a path outside the workspace and, if blocked, to retry with `sandbox_permissions=require_escalated`: PreToolUse and PostToolUse fired, PermissionRequest did not. In readonly the model declined to try. |
| SubagentStart, SubagentStop | The model cannot spawn a sub-agent in this launch: Codex answers the `spawn_agent` call with `unsupported call` (tool names `multi_agent_v1.spawn_agent`, `collaboration.spawn_agent`) | Two prompts asking for one sub-agent on P2 readwrite: SessionStart, UserPromptSubmit, Stop and SessionEnd fired; no sub-agent event |

These events are unobservable on every route, including the controls (a control that
never fires cannot support "not executed"). The protective specification below does not
depend on observing them: it keeps the project layer from loading, and the `hooks/list`
check in section 3 shows that an unmarked project contributes none of the 12 events'
hooks (0 listed, against 24 for the trusted project), whatever the event.

### 6.4 How a repository hook reaches execution

Observed on 0.160.0 and used to choose the means in section 8.

- The project layer (`<dir>/.codex/config.toml` hook tables and `<dir>/.codex/hooks.json`)
  of a directory loads only when the user-level configuration (`$CODEX_HOME/config.toml`,
  `[projects."<path>"] trust_level`) marks that directory, or the repository it belongs
  to, trusted. With `--ignore-user-config` the trust entries are never read, which is why
  P1 and P4 do not execute. `--dangerously-bypass-hook-trust` lifts the hook-level trust
  (`trustStatus untrusted`) but not this layer-level one.
- Writable sandbox: on a launch that reads the user configuration and runs
  `workspace-write`, Codex marks an unmarked project `trusted` in the user configuration
  and loads its project layer in the same run (P3 rw executes; the entry for the git root
  was written to the probe's temporary `config.toml`). Readonly leaves the configuration unchanged (P3 ro does
  not execute). `-c sandbox_mode="workspace-write"` in place of `-s workspace-write`
  behaves the same (`sandboxc`), and making the configuration file read-only (`ro444`)
  did not prevent it.
- An explicit `untrusted` entry is respected: P3 rw with `<repo>` marked `untrusted` in
  the user configuration produced no marker (`untrustroot`), and the sandbox of that run
  was still enforced (`sandbox`: a write to `/var/tmp` failed with a read-only file
  system error).
- Gating is per directory: with `<repo>` trusted and `<repo>/sub` untrusted only the
  hooks of `<repo>/.codex/` ran (`mixedrootT_subU`, 12 markers, all `ancestor_`); with the
  reverse only those of `<repo>/sub/.codex/` ran (`mixedrootU_subT`).
- Paths: a working directory passed as a symlink that lies outside the repository and
  points into it was not treated as trusted by a trust entry for the physical repository
  (`symlinkC` on P2 ro: no marker), while the writable-sandbox self-trust still applied
  to it (`slashsymlinkC`: the hooks of the working directory ran, those of the ancestor
  did not). A `[projects."/"]` entry of `untrusted` did not stop the writable-sandbox
  trust (`slash`).
- `-c` cannot replace the user configuration's entries: `-c
  'projects."<repo>".trust_level="untrusted"'` on a launch whose user configuration
  trusts `<repo>` still executed the hooks, and `-c projects...="trusted"` on a
  `--ignore-user-config` launch did not trust the project.
- `--ignore-user-config` on the `--litellm` route does not work: the `-p litellm` profile
  is a file of the user configuration directory and is dropped with it, so the launch
  goes to the default provider and fails with a 401 (`addiuc`, rc 1).
- Side effect on default routes: with `--ignore-user-config` the trust entries are not
  read, but a readwrite run still writes a `trust_level = "trusted"` entry for the project
  into `$CODEX_HOME/config.toml` (observed on P1 rw and P4 rw). It has no effect on those
  launches and is not caused by this change.

### 6.5 Same-key override

The wrapper's `-c hooks.PreToolUse=[...]` **merges** with repository PreToolUse
definitions; it neither replaces them nor is replaced. On a route that executed
repository hooks, one tool call ran five PreToolUse hooks: the four repository ones and
the wrapper's guard (`PreToolUse hook lines` 5 on `main`, 20 on the four-command
`compact`), and the wrapper's guard still denied `python3 -i` (P2 rw `guard`: guard
denied, 20 markers). Merging does not make the guard a defense against repository hooks.

## 7. Per-route verdict and branch

- em-workflow default route: not executing (positively controlled, 6.2). Unchanged.
- em-review default route: not executing (positively controlled, 6.2). Unchanged.
- em-workflow `--litellm` route: executing. Trusted project: readonly and readwrite.
  Untrusted project: readwrite, through the writable-sandbox trust of 6.4.
- Branch E applies (IMPLEMENTATION.md D2): a route is executing when any of its
  conditions executed. FR3 applies to that route only. em-review has no `--litellm`
  route and its only route is non-executing, so its launch composition is unchanged and
  it receives the FR6 comment update only.

The plan's deviation conditions did not occur: codex reports 0.160.0, and every route has
observable location x event pairs.

## 8. The protective specification

### 8.1 Means

On the `--litellm` route only, the em-workflow wrapper runs `codex exec` with
`CODEX_HOME` pointed at a **launch-dedicated Codex home** created per run
(`mktemp -d "${TMPDIR:-/tmp}/codex-launch-home.XXXXXX"`) and removed on `EXIT`. It
contains:

- `litellm.config.toml`: a copy of the user's profile file (when it exists), so
  `-p litellm -m MODEL` resolves as before;
- `config.toml`: one `[projects."<dir>"] trust_level = "untrusted"` table for the working
  directory and for every ancestor of it up to `/`, each under three spellings (the path
  as given made absolute, `pwd`, `pwd -P`), de-duplicated. A directory with a
  TOML-hostile name is written as a TOML basic string.

The specification is visible to a stub as the `CODEX_HOME` value and the files in it. The
argv is unchanged: still `-p litellm -m MODEL`, `--ignore-rules`, the wrapper's
`-c hooks.PreToolUse` and `--dangerously-bypass-hook-trust`. No `--ignore-user-config`.

### 8.2 Rationale

- The launch reads only this home, so no project directory is trusted by the user's
  configuration (the trusted case, P2) and the writable-sandbox self-trust finds an
  explicit `untrusted` entry (the unmarked case, P3 rw), which 6.4 shows is respected.
- Per-directory gating means one entry for the working directory is not enough; the
  project root and any parent with a `.codex/` must be covered, hence the chain up to `/`
  and the symlink-aware spellings.
- The self-trust write now lands in the throwaway home, so these launches no longer write
  a trust entry into the user's real `config.toml`.

Alternatives checked and rejected:

| Alternative | Result |
|---|---|
| `--ignore-user-config` on the `--litellm` route | Drops the `-p litellm` profile; the launch fails (6.4, `addiuc`) |
| `-c projects."<dir>".trust_level="untrusted"` | Does not override the user configuration (6.4) |
| Read-only user `config.toml` | Does not stop the self-trust (`ro444`) |
| Single `"/"` entry | Does not stop the self-trust (`slash`) |
| Avoid the self-trust by not using a writable sandbox | Not available: readwrite mode needs `workspace-write` (and `-c sandbox_mode` self-trusts the same way, `sandboxc`), and the trusted case (P2) executes in readonly too |

### 8.3 Costs, stated

- The `--litellm` route no longer loads the user's base `config.toml` (model defaults,
  `[otel]`, MCP servers, features), user hooks, user skills or user `AGENTS.md`; only the
  `litellm` profile is carried over. SPEC A3's premise that this path loads user-level
  configuration no longer holds for the base file.
- Sessions of these launches live in the throwaway home and disappear with it.
- Codex prints one warning for a Codex home under a temporary directory (`WARNING:
  proceeding, even though we could not create PATH aliases: Refusing to create helper
  binaries under temporary dir ...`). On the `--litellm` route it now appears in the
  wrapper's output, among the Codex stderr text the wrapper appends after the final
  message, as other Codex warnings do. The launch proceeds, the sandbox is enforced
  (`sandbox` runs above) and tool calls ran normally. Every probe, before and after the
  change, ran with a Codex home under `/tmp`, so the pre/post comparison carries the same
  warning.
- Credentials still come from `LITELLM_API_KEY` in the environment (`env_key`); no
  `auth.json` is needed or carried.
- The home is removed by an `EXIT` trap, together with the existing temp files.

## 9. Post-change probe

The changed wrapper was launched with the same hook definitions and the same kinds on the
changed route. Each launch is a P2 or P3 command line of section 5 with `HOME=<probe>/home`
and `CODEX_HOME=<probe>/home/.codex`; the wrapper then ran `codex` with `HOME=<probe>/home`
and `CODEX_HOME` set to its launch-dedicated temporary home (section 8.1), so both values
the launched `codex` saw were temporary directories. The user's real HOME and Codex home
were not involved (section 2.2).

| Event | P2 ro | P2 rw | P3 ro | P3 rw |
|---|---|---|---|---|
| SessionStart | N | N | N | N |
| UserPromptSubmit | N | N | N | N |
| PreToolUse | N | N | N | N |
| PermissionRequest | U | U | U | U |
| PostToolUse | N | N | N | N |
| PreCompact | N | N | N | N |
| PostCompact | N | N | N | N |
| SubagentStart | U | U | U | U |
| SubagentStop | U | U | U | U |
| Stop | N | N | N | N |
| Interrupt | N | N | N | N |
| SessionEnd | N | N | N | N |

Positive control for each "N" here: the pre-change launches of the same route and mode
with the same hook definitions (P2 ro, P2 rw, P3 rw, all E in 6.1; P3 ro by the P2 ro
control), and the `hooks/list` check in section 3. Further post-change runs: `mixedrootT_subU`
(user config trusts `<repo>`, marks `<repo>/sub` untrusted; the pre-change run executed
the `<repo>/.codex/` hooks) on P2 ro and P3 rw, and `symlinkC` (working directory passed
through a symlink) on P2 rw and P3 rw: no marker in any of them.

The wrapper's own guard still fires on the changed route: in every `main` run the one
PreToolUse hook line is the wrapper's guard registration, and the guard denied `python3
-i` on P2 ro, P2 rw and P3 rw. The first P3 ro `guard` run was one where the model declined
to call the tool (no hook line); two repeats denied. The A1 exception (the guard no longer
fires on a route) does not apply to any route.

## 10. Run log

`rc` 124 is the bound firing in the `interrupt` kind, as designed. `rc` 1 are launch
failures (`addiuc`: the dropped profile, section 6.4; `untrustsub`: the backend closed the
stream before any turn, inconclusive and not relied on). Control names are defined in
sections 5 and 6.4; `Wrapper guard denied` is only meaningful in `guard` runs.

Labels: `pre` = before the change, `post` = after.

Every row is a launch under temporary directories (section 2.2): `HOME=<probe>/home` and
`CODEX_HOME=<probe>/home/.codex` on every `pre` row; `HOME=<probe>/home` and the
wrapper's launch-dedicated temporary `CODEX_HOME` on every `post` row.

| Label | Condition | Mode | Kind | Control | rc | Markers | PreToolUse hook lines | Wrapper guard denied |
|---|---|---|---|---|---|---|---|---|
| pre | P1 | readonly | main | none | 0 | 0 | 1 | no |
| pre | P1 | readonly | compact | none | 0 | 0 | 4 | no |
| pre | P1 | readonly | interrupt | none | 124 | 0 | 0 | no |
| pre | P1 | readonly | guard | none | 0 | 0 | 0 | no |
| pre | P1 | readwrite | main | none | 0 | 0 | 1 | no |
| pre | P1 | readwrite | compact | none | 0 | 0 | 4 | no |
| pre | P1 | readwrite | interrupt | none | 124 | 0 | 1 | no |
| pre | P1 | readwrite | guard | none | 0 | 0 | 1 | yes |
| pre | P2 | readonly | main | none | 0 | 24 | 5 | no |
| pre | P2 | readonly | compact | none | 0 | 32 | 20 | no |
| pre | P2 | readonly | interrupt | none | 124 | 16 | 0 | no |
| pre | P2 | readonly | guard | none | 0 | 16 | 0 | no |
| pre | P2 | readwrite | main | none | 0 | 24 | 5 | no |
| pre | P2 | readwrite | compact | none | 0 | 32 | 20 | no |
| pre | P2 | readwrite | interrupt | none | 124 | 20 | 5 | no |
| pre | P2 | readwrite | guard | none | 0 | 20 | 5 | yes |
| pre | P3 | readonly | main | none | 0 | 0 | 1 | no |
| pre | P3 | readonly | compact | none | 0 | 0 | 4 | no |
| pre | P3 | readonly | interrupt | none | 124 | 0 | 0 | no |
| pre | P3 | readonly | guard | none | 0 | 0 | 1 | yes |
| pre | P3 | readwrite | main | none | 0 | 24 | 5 | no |
| pre | P3 | readwrite | compact | none | 0 | 32 | 20 | no |
| pre | P3 | readwrite | interrupt | none | 124 | 20 | 5 | no |
| pre | P3 | readwrite | guard | none | 0 | 20 | 5 | yes |
| pre | P4 | readonly | main | none | 0 | 0 | 1 | no |
| pre | P4 | readonly | compact | none | 0 | 0 | 4 | no |
| pre | P4 | readonly | interrupt | none | 124 | 0 | 1 | no |
| pre | P4 | readonly | guard | none | 0 | 0 | 1 | yes |
| pre | P4 | readwrite | main | none | 0 | 0 | 1 | no |
| pre | P4 | readwrite | compact | none | 0 | 0 | 4 | no |
| pre | P4 | readwrite | interrupt | none | 124 | 0 | 1 | no |
| pre | P4 | readwrite | guard | none | 0 | 0 | 1 | yes |
| pre | P1 | readonly | main | stripiuc | 0 | 24 | 5 | no |
| pre | P1 | readonly | compact | stripiuc | 0 | 32 | 40 | no |
| pre | P1 | readonly | interrupt | stripiuc | 124 | 16 | 0 | no |
| pre | P1 | readwrite | main | stripiuc | 0 | 24 | 5 | no |
| pre | P1 | readwrite | compact | stripiuc | 0 | 32 | 20 | no |
| pre | P1 | readwrite | interrupt | stripiuc | 124 | 20 | 5 | no |
| pre | P4 | readonly | main | stripiuc | 0 | 24 | 5 | no |
| pre | P4 | readonly | compact | stripiuc | 0 | 32 | 20 | no |
| pre | P4 | readonly | interrupt | stripiuc | 124 | 20 | 5 | no |
| pre | P4 | readwrite | main | stripiuc | 0 | 24 | 5 | no |
| pre | P4 | readwrite | compact | stripiuc | 0 | 32 | 20 | no |
| pre | P4 | readwrite | interrupt | stripiuc | 124 | 20 | 5 | no |
| pre | P3 | readonly | main | addiuc | 1 | 0 | 0 | no |
| pre | P3 | readonly | main | mixedrootT_subU | 0 | 12 | 3 | no |
| pre | P3 | readwrite | main | mixedrootT_subU | 0 | 12 | 3 | no |
| pre | P3 | readonly | main | mixedrootU_subT | 0 | 12 | 3 | no |
| pre | P3 | readwrite | main | ro444 | 0 | 24 | 5 | no |
| pre | P3 | readwrite | main | sandboxc | 0 | 24 | 5 | no |
| pre | P3 | readonly | main | slash | 0 | 0 | 1 | no |
| pre | P3 | readwrite | main | slash | 0 | 24 | 5 | no |
| pre | P3 | readwrite | main | slashsymlinkC | 0 | 12 | 3 | no |
| pre | P2 | readonly | main | symlinkC | 0 | 0 | 1 | no |
| pre | P3 | readonly | sandbox | untrustroot | 0 | 0 | 0 | no |
| pre | P3 | readwrite | main | untrustroot | 0 | 0 | 1 | no |
| pre | P3 | readwrite | sandbox | untrustroot | 0 | 0 | 1 | no |
| pre | P3 | readwrite | main | untrustsub | 1 | 0 | 0 | no |
| pre | P2 | readwrite | main | deeperdir | 0 | 24 | 5 | no |
| post | P2 | readonly | main | none | 0 | 0 | 1 | no |
| post | P2 | readonly | compact | none | 0 | 0 | 4 | no |
| post | P2 | readonly | interrupt | none | 124 | 0 | 0 | no |
| post | P2 | readonly | guard | none | 0 | 0 | 1 | yes |
| post | P2 | readwrite | main | none | 0 | 0 | 1 | no |
| post | P2 | readwrite | compact | none | 0 | 0 | 4 | no |
| post | P2 | readwrite | interrupt | none | 124 | 0 | 0 | no |
| post | P2 | readwrite | guard | none | 0 | 0 | 1 | yes |
| post | P3 | readonly | main | none | 0 | 0 | 1 | no |
| post | P3 | readonly | compact | none | 0 | 0 | 4 | no |
| post | P3 | readonly | interrupt | none | 124 | 0 | 0 | no |
| post | P3 | readonly | guard | none | 0 | 0 | 0 | no |
| post | P3 | readwrite | main | none | 0 | 0 | 1 | no |
| post | P3 | readwrite | compact | none | 0 | 0 | 4 | no |
| post | P3 | readwrite | interrupt | none | 124 | 0 | 0 | no |
| post | P3 | readwrite | guard | none | 0 | 0 | 1 | yes |
| post | P2 | readonly | main | mixedrootT_subU | 0 | 0 | 1 | no |
| post | P3 | readwrite | main | mixedrootT_subU | 0 | 0 | 1 | no |
| post | P2 | readwrite | main | stripiuc (no flag to strip on this route) | 0 | 0 | 1 | no |
| post | P2 | readwrite | main | symlinkC | 0 | 0 | 1 | no |
| post | P3 | readwrite | main | symlinkC | 0 | 0 | 1 | no |
| post | P3 | readonly | guard | none (repeated twice) | 0 | 0 | 1 | yes |

Control names: `stripiuc` the shim removes `--ignore-user-config` and the user config
trusts `<repo>`; `addiuc` the shim adds `--ignore-user-config` to the `--litellm` route;
`mixedrootT_subU` / `mixedrootU_subT` the user config marks `<repo>` trusted and
`<repo>/sub` untrusted, or the reverse; `ro444` the user config file is mode 0444;
`sandboxc` `-c sandbox_mode="workspace-write"` replaces `-s workspace-write`; `slash`
the user config holds only `[projects."/"]` `untrusted`; `symlinkC` the `-C` argument is a
symlink to `<repo>/sub`, `slashsymlinkC` both; `untrustroot` / `untrustsub` the user
config marks `<repo>` or `<repo>/sub` explicitly `untrusted`; `sandbox` kind: the model is
asked to write outside the workspace; `deeperdir` an additional hook directory
`<repo>/sub/deeper/.codex/` below the working directory (no marker from it; 24 markers
are the two existing directories).

## 11. Tests that pin the result

`tests/test_codex_repo_hook_trust.py` (Python standard library only):

- TS1 (always runs, stub codex): on the changed route in both modes, the launch-dedicated
  home (explicit `untrusted` entries for the working directory and its ancestors in three
  spellings, profile copied) is what `CODEX_HOME` points at, the guard registration and
  the unchanged flags are present, the user's temporary home is untouched and the launch
  home is removed, the specification check rejects forged records that lack it
  (non-vacuity), the other routes keep `CODEX_HOME` and `--ignore-user-config`, and a
  sentinel credential never reaches the captured output.
- TS2 (real Codex 0.160.0, skips otherwise): a control launch with the pre-change
  composition must create the SessionStart and UserPromptSubmit markers or the case
  skips; the launch through the wrapper must then leave none. Cases: readonly with the
  repository trusted, readwrite with the repository trusted, readwrite with no trust
  entry. A local stub HTTP backend plays the model endpoint, so the case needs no
  credential and no network.

## 12. Limits of this record

- Single run per cell; the model does not always call the tool, so a cell rests on the
  aggregate of kinds and the controls, not on one run.
- The result is for Codex 0.160.0; a later Codex that changes which configuration layers
  it reads is outside this record. TS2 skips on other versions and TS1 still pins the
  specification.
- PermissionRequest, SubagentStart and SubagentStop are unobservable (6.3).
- User-level and managed hook sources (`user`, `plugin`, `mdm`, `system`, cloud) are not
  repository-controlled and were not probed; the `--litellm` route no longer reads the
  user-level layer at all, and the default routes keep `--ignore-user-config`.
