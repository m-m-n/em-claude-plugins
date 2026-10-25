# Implementation Plan: codex-stop-hook-tty-reaper

## Overview
Both `run_codex_exec.sh` wrappers register a Codex Stop hook on every launch
path. The hook ships as two byte-identical copies. At turn end it stops the
launch's descendants whose standard input is a terminal (`/dev/pts/*`). The
work splits into the hook and its tests (task0001) and the registration in
both wrappers with its tests (task0002).

## Technology Stack
- **Language**: Python 3, standard library only, for the Stop hook and the
  tests. Bash for the wrappers (existing).
- **Test framework**: `unittest` (standard library), under `tests/`.
- **Process information**: `/proc`.
- **New dependencies**: none. There is no license to record
  (`project.license: none`).

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Launch wiring | `em-workflow/scripts/run_codex_exec.sh`, `em-review/scripts/run_codex_exec.sh` | Builds the Codex launch, including both hook registrations, and supplies the anchor |
| Process control | `em-workflow/scripts/codex-hook-tty-reaper.py`, `em-review/scripts/codex-hook-tty-reaper.py` | At Stop, determines the targets and stops them |

Dependency direction: the wrapper depends on the hook only through S1 and S2
below. The hook knows nothing about the wrapper except the anchor argument.
Codex sits between the two and passes the command through unchanged.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| S1: Stop hook command line | How Codex invokes the hook | Shape: `python3`, then the absolute path of the hook in the same plugin's `scripts/` (single-quoted for a POSIX shell), then exactly one argument, the anchor. The anchor is the PID of the `run_codex_exec.sh` main shell process (never a subshell's), written as ASCII decimal digits. Precondition: the anchor process stays alive and remains an ancestor of the hook for the whole launch. Postcondition (hook side): on every path the hook exits with status 0, writes nothing to standard output or standard error, and returns no block / continue decision. An argument list that is not exactly one valid anchor stops nothing | task0001 (consumer), task0002 (producer) |
| S2: Stop hook file | Where the hook lives | File name `codex-hook-tty-reaper.py`, in `em-workflow/scripts/` and `em-review/scripts/`, with the two copies byte-identical. The wrapper derives the path from its own directory (`SCRIPT_DIR`) and does not check that the file exists | task0001 (creates), task0002 (references) |

## Conventions
- Tests are standard-library `unittest` modules under `tests/`, named per
  `test/README.md`. Plugin scripts run as separate processes. A test that
  drives the hook in-process loads it from its path with bytecode writing
  disabled, so no `__pycache__` lands in a distributed plugin directory.
- Signals sent during tests reach only processes the test started. Every
  anchor a test passes to the hook is a process the test started (NFR4).
- The two hook copies change together and stay byte-identical, as with
  `codex-hook-interactive-guard.py`.
- Inside the hook, any doubt (input, anchor, process table) ends in stopping
  nothing. Inside the wrapper, a missing hook file leads to no reaping and
  does not block the launch (D2).

## Cross-task Design Decisions

### D1: The anchor is the wrapper's own process (resolves the SPEC Open Question on FR3)
Decision: the wrapper passes the PID of its own main shell process to the
hook as the hook command's single argument (S1). That process waits on the
launch for its whole duration. The hook uses that process as the anchor. It
acts only when the anchor is a proper ancestor of the hook. The targets are
the anchor's descendants whose standard input is `/dev/pts/*`, minus the hook
and every one of its ancestors.

Rationale: the alternative is to walk the hook's ancestors to a process
recognised as Codex. That relies on process names, which sandboxed commands
control and which differ between a Codex launcher and its native binary. It
can also choose an ancestor that is too high and so reach Codex launches
running in parallel (NFR1). The wrapper is the one process that knows which
launch it started.

Equivalence with FR3: during the launch, the wrapper's only live child is
the `timeout` -> `codex` chain, and that chain lies on the hook's own ancestor
path. So "anchor descendants minus the hook's ancestors" equals "Codex
descendants minus the hook's ancestors". task0002 keeps this true: the wrapper
starts no other process that lives at the same time as the codex launch.

Affected tasks: task0001, task0002.

### D2: Fail-open in the wrapper, fail-closed in the hook
The wrapper never checks the hook file. If the file is missing, there is no
reaping and the launch is otherwise unchanged, the same as the existing
PreToolUse registration. The hook stops nothing whenever its input, its
anchor or the process table cannot be confirmed (FR5, NFR5).

Affected tasks: task0001, task0002.

### D3: Each task tests only its own side of S1
task0002's tests pin S1 as text and as the arguments that a POSIX shell
passes to `python3`. They never execute the hook and never require its file,
which does not exist in task0002's worktree. task0001's tests invoke the hook
directly with an anchor the test started, and never run a wrapper.

Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Codex rejects the Stop registration shape, or writes no JSON object to the Stop hook's standard input, so the hook silently stops nothing | Medium | High | Real-machine items TS-9 to TS-11 (VERIFICATION.md) |
| The launch structure changes so that the anchor is no longer an ancestor of the hook | Low | Medium | The hook stops nothing (D2); TS-9 to TS-11 detect it |
| A process that was intentionally left in the background with a terminal as standard input gets stopped | Medium | Low | Accepted by FR7; the outcome is recorded by TS-12 |
| Real-process tests are timing-sensitive under load | Medium | Low | Ordering and timing are checked in-process with a recording signal sender and a fake clock; real-process tests poll with generous bounds |
| The PreToolUse guard denies interactive launches, which blocks the real-machine reproduction | High | Low | The VERIFICATION.md manual procedure runs a copy of `scripts/` without the guard file |

## Open Questions
- [ ] FR8 (real-machine confirmation and record) has no implement task. The
  verify phase satisfies it through the manual items TS-9 to TS-12.
