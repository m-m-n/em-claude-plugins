# Hook trust findings: codex-repo-hook-trust

Record of whether hook definitions in the working directory's Codex configuration
(repository hooks) execute under each launch route of the em-workflow and em-review
Codex wrappers, measured on Codex 0.160.0. Written by task0001. The tests, the wrapper
comments and TB-3 of `feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md` follow
this record; a later change that contradicts it updates this record first.

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

- Codex as reported by the binary used: `codex-cli 0.160.0` (`codex --version`). The
  real-Codex test (TS2) skips unless the binary reports exactly this.
- Platform: Linux, bash and zsh available; the wrappers ran under bash.
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
- Reads outside the temporary homes. The following were run without a temporary home and
  only read: `codex --version`, `codex --help` and subcommand help text, `codex features
  list`, and `strings` over the codex binary (the output was kept outside the repository).
  No Codex session, no launch and no configuration write was made against the user's real
  Codex home. `codex app-server generate-json-schema` and the `hooks/list` requests ran
  with a temporary home.

## 3. Hook locations and events under test

How the list was established (all on 0.160.0):

1. `codex app-server generate-json-schema` (temporary home). The schema defines:
   - `HookEventName`: `preToolUse`, `permissionRequest`, `postToolUse`, `preCompact`,
     `postCompact`, `sessionStart`, `sessionEnd`, `userPromptSubmit`, `subagentStart`,
     `subagentStop`, `stop`, `interrupt` (12 events);
   - `HookSource`: `system`, `user`, `project`, `mdm`, `sessionFlags`, `plugin`,
     `cloudRequirements`, `cloudManagedConfig`, `legacyManagedConfigFile`,
     `legacyManagedConfigMdm`, `unknown`. Only `project` comes from the repository under
     review; `sessionFlags` is what the wrapper's `-c hooks.PreToolUse=...` produces.
2. `hooks/list` on `codex app-server --stdio` (temporary home), given a temporary
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
   (a pre-change `--litellm`, trusted, readwrite launch: all 24 markers of the two
   existing directories, none from the lower one). Project layers are therefore the
   working directory and its ancestors.

Locations probed (repository-controlled, `source = project`), four per event:

| Location key | File |
|---|---|
| `config_toml` | `<working directory>/.codex/config.toml`, `[[hooks.<Event>]]` tables |
| `hooks_json` | `<working directory>/.codex/hooks.json` |
| `ancestor_config_toml` | `<git root, one level above>/.codex/config.toml` |
| `ancestor_hooks_json` | `<git root, one level above>/.codex/hooks.json` |

Events probed: all 12 above.

`hooks/list` gives the gate itself. With the temporary user config marking the repository
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
as variable names only.

```
HOME=<probe>/home CODEX_HOME=<probe>/home/.codex PATH=<probe>/bin:$PATH   # LITELLM_API_KEY inherited
P1: em-workflow/scripts/run_codex_exec.sh {readonly|readwrite} -C <repo>/sub "<prompt>"
P2: em-workflow/scripts/run_codex_exec.sh {readonly|readwrite} --litellm muse-spark -C <repo>/sub "<prompt>"
    (temporary user config trusts <repo>)
P3: the P2 command with a temporary user config that has no trust entry
P4: em-review/scripts/run_codex_exec.sh {readonly|readwrite} -C <repo>/sub "<prompt>"
```

Argv the wrapper hands to `codex` (path of the working directory and of the plugin shortened):

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
  was written to `config.toml`). Readonly leaves the configuration unchanged (P3 ro does
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
changed route.

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
