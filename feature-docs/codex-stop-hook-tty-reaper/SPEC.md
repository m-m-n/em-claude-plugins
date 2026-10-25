# Feature: codex-stop-hook-tty-reaper

## Overview

run_codex_exec.sh in em-workflow and em-review registers a Codex Stop hook on
every launch path. At the end of a Codex turn the hook stops the processes that
are descendants of that Codex and whose standard input is a terminal
(/dev/pts/*), such as python3 -i or bash -i left waiting for input. Requirements
document: `feature-docs/codex-stop-hook-tty-reaper/REQUIREMENTS.md`.

## Objectives

- Interactive processes (python3 -i, bash -i, etc.) left waiting on terminal input after a Codex launched by run_codex_exec.sh exits do not become orphans that keep consuming CPU.
- Stop them by inspecting the processes actually remaining at turn end, without relying on static analysis of command strings.

## User Stories

### US1: Terminal-bound processes do not outlive the Codex turn
As a user of em-workflow / em-review who launches Codex through run_codex_exec.sh, I want processes left waiting on terminal input to be stopped when the Codex turn ends, so that they do not remain as orphans consuming CPU.

**Acceptance Criteria:**
- [ ] AC-1: run_codex_exec.sh (em-workflow / em-review) registers the Stop hook on every launch path
- [ ] AC-2: The Stop hook stops Codex descendants whose standard input is still a terminal, including those that have children
- [ ] AC-3: In a Codex run that leaves python3 -i and bash -i with tty:true, those processes do not remain after exit
- [ ] AC-4: In a Codex run that executes only read-only commands, the hook stops nothing
- [ ] AC-5: Confirm that launches via readwrite and --litellm find targets with the same determination
- [ ] AC-6: Confirm, on both the readonly and readwrite paths, whether intentionally left background processes are caught, and record the result

## Technical Requirements

### Functional Requirements
- **FR1:** Stop hook registration — run_codex_exec.sh in em-workflow and em-review registers the Stop hook through the launch argument `-c hooks.Stop=...` on every launch path (readonly / readwrite; em-workflow's default path and its --litellm path).
- **FR2:** Hook script placement — The Stop hook script is placed in each plugin's scripts/ and registered by an absolute path derived from the wrapper's own location (SCRIPT_DIR). The two copies are kept byte-identical. (Assumed: A2)
- **FR3:** Target determination — Every descendant of the Codex that launched the hook whose standard input is /dev/pts/* is a target. Processes that have children are included; targets are not narrowed to leaves. The hook itself and its ancestors are never targets. The method of identifying the Codex that launched the hook (walk the hook's ancestors, or have the wrapper pass its PID) is to be decided in SPEC.
- **FR4:** Stop procedure — Targets are stopped children first (deepest first). Each target receives SIGTERM; if it is still alive 0.5 seconds later it receives SIGKILL. Before SIGKILL, the hook confirms it is the same process (not a reused PID). A process that ended in the meantime (ESRCH) is not an error. (Assumed: A4)
- **FR5:** Do not interfere with Codex stopping — The hook returns no block / continue decision and changes neither the Codex stop nor the Codex exit code. If anything fails inside the hook, it exits without stopping anything. (Assumed: A6)
- **FR6:** Keep the existing PreToolUse hook — The PreToolUse registration of codex-hook-interactive-guard.py stays as is. (Assumed: A1)
- **FR7:** Background processes — No processing is added to exclude intentionally left background processes from the determination. The FR3 determination (descendant relation and standard input) is unchanged; whether such processes are caught is only confirmed and recorded, on both the readonly and readwrite paths.
- **FR8:** Real-machine confirmation and record — With a real Codex, confirm and record: python3 -i and bash -i left with tty:true do not remain after exit; a run of only read-only commands has the hook stop nothing; launches via readwrite and --litellm find targets with the same determination; whether intentionally left background processes are caught (both readonly and readwrite). (Assumed: A5)

### Non-Functional Requirements
- **NFR1 - Signal reach:** The hook sends no signal to any process that is not a descendant of the Codex that launched it. Another Codex running in parallel, its descendants, the calling Claude Code and any further ancestors are out of scope.
- **NFR2 - Duration bound:** One hook execution finishes within a short fixed time, including the 0.5-second wait after SIGTERM.
- **NFR3 - Wrapper contract preserved:** The usage text, accepted flags, launching codex exec exactly once, --dangerously-bypass-hook-trust appearing exactly once, the 2>&1 handling, and the prompt being the last argument are unchanged (A3).
- **NFR4 - Test dependencies and isolation:** Tests are standard-library-only unittest under tests/, never reach a real Codex, and send no signal to any process the test did not start itself.
- **NFR5 - Runtime environment:** The hook runs with only the python3 standard library. Where /proc is unavailable it does nothing (A7).
- **NFR6 - Resistance to untrusted input:** The hook runs outside the Codex sandbox under --dangerously-bypass-hook-trust. Neither the content of the repository under review nor the content of the hook's standard input can widen the set of stopped processes beyond the Codex descendants.

## Implementation Approach

### Architecture

**Component Diagram:**
```
run_codex_exec.sh (em-workflow / em-review)
  └─ codex exec  -c hooks.PreToolUse=<codex-hook-interactive-guard.py>   (unchanged, FR6)
                 -c hooks.Stop=<absolute path derived from SCRIPT_DIR>   (FR1, FR2)
       └─ Stop hook (python3, standard library only)
            1. identify the Codex that launched the hook (FR3; method open, see Open Questions)
            2. enumerate that Codex's descendants via /proc
            3. keep those whose stdin is /dev/pts/*, excluding the hook and its ancestors
            4. stop deepest first: SIGTERM -> wait 0.5 s -> same-process check -> SIGKILL
            5. exit 0 with no decision output
```

### Data Flow

```
Codex turn ends → Stop hook starts → /proc scan of Codex descendants
  → filter: stdin is /dev/pts/* (not the hook, not its ancestors)
  → order deepest first → SIGTERM → 0.5 s → alive and same process? → SIGKILL
  → exit 0 (no block / continue decision)
```

Failure anywhere inside the hook: exit without stopping anything (FR5).
/proc unavailable: do nothing (NFR5).

### API Design

Not applicable. The hook's interface to Codex is the `-c hooks.Stop=...` launch argument (FR1) and the hook's standard input; the hook emits no decision JSON (FR5).

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- run_codex_exec.sh (em-workflow / em-review): registers the Stop hook (FR1) and keeps its existing contract (NFR3).
- codex-hook-interactive-guard.py: its PreToolUse registration is kept unchanged (FR6).
- tests/test_codex_hook_wrapper_args.py: extended to cover the Stop hook registration (TS-1).

**External Dependencies:**
- python3 standard library only (NFR5).
- /proc for descendant and standard-input determination (A7).

### File Structure

```
em-workflow/
└── scripts/
    └── <Stop hook script>           # byte-identical to the em-review copy (FR2)
em-review/
└── scripts/
    └── <Stop hook script>           # byte-identical to the em-workflow copy (FR2)
tests/
├── test_codex_hook_wrapper_args.py  # extended (TS-1)
└── <unittest module(s) for the Stop hook>  (TS-2 .. TS-8)
```

Each plugin's run_codex_exec.sh is also changed (FR1). The Stop hook script's
file name is not fixed by the requirements.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-stop-hook-tty-reaper/**`
- `test-docs/codex-stop-hook-tty-reaper/**`

`feature-docs/codex-stop-hook-tty-reaper/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-stop-hook-tty-reaper/**` covers
`test-docs/codex-stop-hook-tty-reaper/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-stop-hook-tty-reaper/` directory at all; the declared
`test-docs/codex-stop-hook-tty-reaper/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (AC-1, FR1, FR2, FR6, NFR3): Extend tests/test_codex_hook_wrapper_args.py. With a stub codex, launch each path of em-workflow (readonly / readwrite / --litellm) and em-review (readonly / readwrite) - exactly one `-c hooks.Stop=...` is present and points to the absolute path of the Stop hook in that plugin's scripts/; the PreToolUse registration and the wrapper's existing contract are unchanged.
- [ ] TS-2 (FR2): Compare the em-workflow and em-review Stop hook scripts - they are byte-identical.
- [ ] TS-3 (AC-2, FR3): The test itself starts a pseudo-Codex process tree with one descendant whose stdin is a pty and one whose stdin is a pipe, and runs the hook as a descendant of the pseudo-Codex - only the pty descendant is stopped; the pipe descendant remains.
- [ ] TS-4 (FR3, FR4): A terminal process that has a child (pty parent and its child) - both are stopped, child first.
- [ ] TS-5 (FR4, NFR2): A process that ignores SIGTERM - it is stopped by SIGKILL after 0.5 seconds, and the hook finishes within the time bound.
- [ ] TS-6 (NFR1): Processes outside the pseudo-Codex whose stdin is a pty (including descendants of a parallel, separate pseudo-Codex), and hook ancestors whose stdin is a pty - none are stopped.
- [ ] TS-7 (FR4, FR5): A process that ends after enumeration (ESRCH) causes no error; the hook emits no decision JSON and exits 0; with invalid standard input the hook stops nothing and exits.
- [ ] TS-8 (NFR5): Simulate /proc being unavailable - the hook does nothing and exits.

### Integration Tests
- None beyond the unit tests above.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

Real-Codex confirmation is not part of the test suite; it is recorded as manual real-machine verification (A5):

- [ ] MV-1 (AC-3, FR8): With a real Codex, leave python3 -i and bash -i with tty:true - those processes do not remain after exit; record the result.
- [ ] MV-2 (AC-4, FR8): Run only read-only commands - the hook stops nothing; record the result.
- [ ] MV-3 (AC-5, FR8): Launch via readwrite and via --litellm - targets are found with the same determination; record the result.
- [ ] MV-4 (AC-6, FR7, FR8): On both readonly and readwrite, check whether intentionally left background processes are caught; record the result.

### Edge Cases
- [ ] Target ends between enumeration and signalling (ESRCH): not an error (FR4, TS-7).
- [ ] PID reused before SIGKILL: SIGKILL is sent only after confirming it is the same process (FR4).
- [ ] Target ignores SIGTERM: SIGKILL after 0.5 seconds (FR4, TS-5).
- [ ] Invalid hook standard input: the hook stops nothing and exits (FR5, TS-7).
- [ ] /proc unavailable: the hook does nothing (NFR5, TS-8).
- [ ] Hook ancestors with a pty stdin, and parallel Codex descendants: never signalled (NFR1, TS-6).

### Performance Tests
- [ ] TS-5 covers the duration bound of NFR2.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** The hook runs outside the Codex sandbox under --dangerously-bypass-hook-trust. Neither the repository under review nor the hook's standard input can widen the stopped set beyond the descendants of the Codex that launched the hook (NFR6). Invalid standard input results in stopping nothing (FR5).
- **Data Protection:** Not applicable.
- **Signal reach:** No signal is sent to any process that is not a descendant of the Codex that launched the hook (NFR1).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

| Condition | Handling |
|-----------|----------|
| ESRCH while signalling a target | Not an error; continue (FR4) |
| Target is not the same process before SIGKILL | SIGKILL is not sent (FR4) |
| Any failure inside the hook | Exit without stopping anything (FR5) |
| /proc unavailable | Do nothing (NFR5) |

In every case the hook returns no block / continue decision and does not change the Codex stop or exit code (FR5).

### Error Flow

```
Error inside hook → stop nothing → exit (no decision output)
```

## Performance Optimization

### Performance Goals
- One hook execution finishes within a short fixed time, including the 0.5-second wait after SIGTERM (NFR2).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 through AC-6 are satisfied
- [ ] MV-1 through MV-4 are performed and recorded
- [ ] Code review is completed

## Assumptions

- A1: The PreToolUse registration of codex-hook-interactive-guard.py is kept unchanged.
- A2: The Stop hook script is placed in each plugin's scripts/ and registered by an absolute path derived from the wrapper's location. The two copies are kept byte-identical.
- A3: The wrapper's existing contract (usage, flags, launching codex exec once, --dangerously-bypass-hook-trust once, 2>&1, prompt as the last argument) is unchanged.
- A4: Stopping sends SIGTERM, waits 0.5 seconds, and sends SIGKILL if the process is still alive.
- A5: Confirmation with a real Codex is not part of the test suite; it is recorded as manual real-machine verification.
- A6: The hook returns no block / continue decision and, on failure, exits without stopping anything.
- A7: Where /proc is unavailable the hook does nothing.
- A8: The em-workflow and em-review versions are not changed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

No requirement has `status: tbd`.

- [ ] FR3: The method of identifying the Codex that launched the hook — walk the hook's ancestors, or have the wrapper pass its PID — is not selected in the resolved requirements.

## References

- Requirements: `feature-docs/codex-stop-hook-tty-reaper/REQUIREMENTS.md`
- Wrapper contract test: `tests/test_codex_hook_wrapper_args.py`
