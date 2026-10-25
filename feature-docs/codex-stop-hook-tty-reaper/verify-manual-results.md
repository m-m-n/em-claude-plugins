# Manual Verification Results: codex-stop-hook-tty-reaper

Verify round 1. Codex version: codex-cli 0.164.0. Process listings were taken
with `ps -eo pid,ppid,stat,tty,args` before and after each run, filtered to
the processes under test. The verifier sent no signal in any run.

## Procedure deviation

VERIFICATION.md says to use a copy of `scripts/` that leaves out
`codex-hook-interactive-guard.py`. With Codex 0.164.0, a missing PreToolUse
hook script blocks every command (`Command blocked by PreToolUse hook:
python3: can't open file ...codex-hook-interactive-guard.py`), so no process
can be started. The copies used for TS-9, TS-11 and TS-12 instead hold a stub
`codex-hook-interactive-guard.py` that reads standard input and exits 0. The
wrapper and `codex-hook-tty-reaper.py` in the copies are byte-identical to the
integration branch. The copies were placed under a temporary directory, and
each run used a temporary working directory.

## TS-9 (SPEC MV-1): readonly, em-workflow copy

- Prompt: start `python3 -i` and `bash -i` through exec_command with tty
  true, leave them running, reply DONE.
- Run output: both commands started (the Python `>>>` prompt and the bash
  prompt appeared in the session output). `hook: Stop` ran, after which
  both sessions reported `exited 1`. Wrapper exit status 0.
- Before: no matching process. After: no matching process.
- Result: pass.

## TS-10 (SPEC MV-2): readonly, integration-branch wrapper (guard present)

- Sentinel started outside the launch: `script -qc 'sleep 247' /dev/null`,
  whose `sleep 247` had a pseudo-terminal as standard input (`pts/21`).
- Prompt: list files, read the first 5 lines of README.md, show git status,
  summarize.
- Run output: three commands succeeded, normal final answer, `hook: Stop`
  completed. Wrapper exit status 0.
- Before: sentinel `sleep 247` on `pts/21`. After: the same PID still alive.
- Result: pass.

## TS-11 (SPEC MV-3): readwrite and `--litellm`

| Route | Outcome |
|---|---|
| readwrite, em-workflow copy | Both processes started with tty; `hook: Stop` ran; both sessions `exited 1`; none left after exit. Pass |
| readwrite, em-review copy | Same as above. Pass |
| `--litellm muse-spark`, readonly (2 attempts) | The model refused to start the interactive processes both times. `hook: Stop` ran with nothing to stop. Not performed |
| `--litellm vertex-glm-5.2`, readonly | The proxy returned `403 Forbidden` from Vertex AI; the run ended with exit status 1 before any command. Not performed |
| `--litellm muse-spark`, readwrite | Every exec_command failed: `Unable to spawn codex-linux-sandbox because: No viable candidates found in PATH`. Codex also warned that it refused to create helper binaries under the launch-dedicated Codex home in `/tmp`. No process could be started. Not performed |

- Result: fail. The `--litellm` part of AC-5 could not be confirmed. The
  LiteLLM proxy was reachable, so the "proxy unavailable" clause does not
  apply.

## TS-12 (SPEC MV-4): intentionally backgrounded processes

Prompt per mode: one exec_command with tty true running `sleep N & echo
started-a`, one with tty false running `sleep M > /dev/null 2>&1 & echo
started-b`.

| Mode | tty:true background | no-terminal background |
|---|---|---|
| readonly | Not present after the run | Not present after the run |
| readwrite | Not present after the run | Not present after the run |

A repeated readwrite run sampled the process table every 0.5 s for the
whole run. Neither `sleep` process appeared in any sample: both ended when
their exec_command returned, before the Stop hook ran. The hook therefore
caught neither of them; Codex itself ended them.

- Result: recorded (FR7 records the outcome only).
