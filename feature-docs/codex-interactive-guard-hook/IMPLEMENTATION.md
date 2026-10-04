# Implementation Plan: codex-interactive-guard-hook

## Overview

Both `run_codex_exec.sh` wrappers register a Codex PreToolUse hook, `scripts/codex-hook-interactive-guard.py`, which denies launches of interpreters and shells in interactive mode. The work splits into three parallel tasks: the hook itself (task0001), the wrapper registration (task0002) and the reviewer guidance (task0003).

## Technology Stack

- **Hook**: Python 3, standard library only (NFR1).
- **Wrappers**: the existing shell scripts `em-workflow/scripts/run_codex_exec.sh` and `em-review/scripts/run_codex_exec.sh`.
- **Tests**: the repository's existing `unittest` suite under `tests/`, run with `python3 -m unittest discover -s tests` from the repository root.
- **New dependencies**: none. Nothing is added beyond the Python 3 standard library, so there is no license to record (`project.license: none`).

## Layer Structure

| Layer | Files | Responsibility | May depend on |
|-------|-------|----------------|---------------|
| Launch configuration | both `run_codex_exec.sh` | Starts `codex exec` with the hook registered and the hook-trust bypass flag set | the hook's file path only (never its content) |
| Guard | both `codex-hook-interactive-guard.py` | Classifies one Bash tool-call command string as deny or pass | nothing outside the Python 3 standard library; never imports `em-workflow/hooks/` (A8) |
| Reviewer guidance | both `agents/codex-reviewer.md` | Tells the Codex reviewer to verify with non-interactive forms | nothing |
| Tests | new modules under `tests/` | Pin the behavior above | the files above, a stub `codex`, a temporary HOME |

Each plugin is self-contained. The em-review wrapper references only the em-review copy of the hook, and the em-workflow wrapper references only the em-workflow copy.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Interactive-guard hook: `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` | Decide, for one Codex Bash tool call, whether the command launches an interpreter in interactive mode (FR6–FR9) | **Pre**: Codex starts it as the Python 3 interpreter running the file's absolute path, with no further arguments. The working directory can be anything. Exactly one PreToolUse JSON object arrives on stdin. **Post**: stdout is either empty or exactly one deny object in the FR12 shape. The exit status is 0 in both cases. The hook writes no file, opens no network connection and starts no child process. The decision does not depend on the working directory or on environment variables. **Invariant**: the two files are byte-identical. | task0001 builds both copies. task0002 references each copy by its absolute path. |
| Interactive-mode alternatives wording | Name the same three non-interactive ways to run code, so the hook's deny reason and the reviewer guidance give the same advice | Both texts name the same three alternatives: `python3 -c`, a script file, and `python3 - <<EOF`. The deny reason is in Japanese (FR12). The reviewer guidance follows the language of the text around it in `codex-reviewer.md`. | task0001 (deny reason), task0003 (Step 4 guidance) |

## Conventions

- **Test modules per task**: each task adds its own new test module under `tests/`, and no task edits a test module that another task creates. Existing test modules stay unmodified (NFR3). If a task finds it must change one, it reports a plan deviation.
- **No real Codex in tests**: any test that runs a wrapper puts a stub `codex` first on PATH and points HOME to a temporary directory (NFR4).
- **No bytecode caches inside plugin directories**: tests never import Python files from `em-workflow/` or `em-review/`. Everything under a plugin directory is distributed to users, so a stray cache directory would ship too. The hook is run as a separate process.
- **Failure policy (fail-open end to end)**: the guard never causes a Codex launch or a Bash tool call to fail. The wrapper passes the hook registration without checking that the hook file exists (A5). If the hook cannot reach a decision, it prints nothing and exits 0 (FR11). Codex runs the command if the hook itself fails.
- **Config isolation is preserved**: no task removes or reorders the config-isolation flags a launch carries today: `--ignore-user-config` where it is present, and `--ignore-rules` (NFR5, A3).

## Cross-task Design Decisions

### D1: One hook copy per plugin, located from the wrapper's own position

Each wrapper resolves the hook path as the absolute path of `codex-hook-interactive-guard.py` in the same `scripts/` directory as the wrapper. The path does not depend on the caller's working directory. em-review cannot reach em-workflow's files (A8), so each plugin ships its own byte-identical copy.
Affected: task0001, task0002.

### D2: Wrapper tests pin the path string, and the live wrapper-to-hook check happens at verify

Tasks run in parallel worktrees, so the hook file is missing from task0002's worktree. task0002's tests therefore assert only the path that the `-c` value names; they never assert that the file exists or behaves correctly. After integration, the verify phase runs each wrapper's recorded hook command against the real hook file (VERIFICATION.md TS-12).
Affected: task0001, task0002.

### D3: Separate test modules

The test modules are `tests/test_codex_hook_interactive_guard.py` (task0001), `tests/test_codex_hook_wrapper_args.py` (task0002) and `tests/test_codex_reviewer_interactive_guidance.py` (task0003). Separate files keep parallel tasks from editing the same new file.
Affected: task0001, task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The hook configuration key names, or whether Codex runs the hook command through a shell, differ from the A6 form. The hook would then be silently unregistered or fail open. | Medium | High: the guard does nothing, and no test notices because tests use a stub | task0002 confirms the form on Codex 0.160.0 before fixing the value. VERIFICATION.md has a manual check on real Codex (M-1). |
| Read literally, FR7 denies option-only launches that never open a REPL, such as `node -v`, `perl -v` and `node --test`. These are misfires (NFR2). | Medium | Medium: a reviewer command is denied, and the deny reason shows an alternative | task0001 implements the FR7 pass list as written. The gap is raised as an open question. |
| The hook-trust bypass flag lifts trust for hooks from every configuration layer a launch loads | Low | High | TM-4 (THREAT-MODEL.md): existing isolation flags are kept. The residual risk is an open question. |
| Adding arguments breaks existing tests that pin the wrapper arguments (NFR3) | Medium | Medium | The task0002 acceptance criteria cover each pinned property, and the full suite must pass. |
| The two hook copies drift apart in later edits | Medium | Medium | TS-5 byte-identity test, and the hook-tests.md rule section added by task0001 |

## Open Questions

- [ ] FR7 lets only `--version`, `-V`, `-h` and `--help` through. `-v` (version for node, perl and lua) and non-REPL option modes such as `node --test` are denied under the literal rule. Should the pass list be extended?
- [ ] AC6 lists `ruby -i` as silent, but bare `ruby -i` meets FR7's "options only" condition. This plan reads AC6's entry as the in-place-edit form (a code option and a target), so bare `ruby -i` is denied under FR7.
- [ ] A9 gives no code-passing options for lua, deno, irb or ipython. This plan applies FR7's general set (`-c`, `-m`, `-e`) to them.
- [ ] With `--dangerously-bypass-hook-trust`, would Codex 0.160.0 also run hooks defined in configuration layers the wrapper does not write? Examples: a repository-local Codex configuration, or user configuration on the `--litellm` path, which loads it by design (A3).
