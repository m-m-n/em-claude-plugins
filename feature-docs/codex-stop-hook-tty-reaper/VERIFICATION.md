# Verification Document: codex-stop-hook-tty-reaper

## Overview
**Feature**: codex-stop-hook-tty-reaper / **SPEC.md**: `feature-docs/codex-stop-hook-tty-reaper/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-stop-hook-tty-reaper/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/codex-stop-hook-tty-reaper/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty, and the
  Python and Bash scripts have no build step.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Focused run: `python3 -m unittest tests.test_codex_hook_tty_reaper tests.test_codex_hook_wrapper_args tests.test_codex_litellm_launch_home_location`
- Expected: exit code 0. On the Linux verification host, no test in these
  three modules is skipped.
- Coverage target: not measured, because the standard-library-only test
  setup has no coverage tool. Completeness is tracked through the mapping
  from Acceptance Criteria to tests.

### Test Scenarios from SPEC.md

SPEC.md's MV-1 to MV-4 appear below as TS-9 to TS-12. TS-13 to TS-17 are
added for FR7, NFR4 / NFR5, NFR6 and the THREAT-MODEL.md mitigations. TS-18
is added by the verify rework of TS-11 (task0003).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (AC-1, FR1, FR2, FR6, NFR3) Stub codex. Each path: em-workflow readonly / readwrite / `--litellm` (both modes), em-review readonly / readwrite | Exactly one `-c hooks.Stop=...`. Its command runs `python3` on the absolute path of that plugin's `scripts/codex-hook-tty-reaper.py`, followed by the wrapper's PID. The PreToolUse registration and the wrapper's existing contract are unchanged | Unit (subprocess) |
| TS-2 | (FR2) Compare the two Stop hook copies | Byte-identical | Unit |
| TS-3 | (AC-2, FR3) Pseudo-Codex tree with one pty-stdin descendant and one pipe-stdin descendant. The hook runs as a descendant with the pseudo-Codex as its anchor | Only the pty descendant is stopped; the pipe descendant remains | Unit (real processes) |
| TS-4 | (FR3, FR4) A pty parent and its pty child | Both are stopped. In the recorded signal sequence, every target is signalled after its target descendants, in both phases | Unit (real processes + in-process) |
| TS-5 | (FR4, NFR2) A target that ignores SIGTERM | It receives SIGKILL no earlier than 0.5 s after the last SIGTERM (fake clock) and is gone when the hook exits. The hook's wall-clock time is under 3 s | Unit (real processes + in-process) |
| TS-6 | (NFR1) pty-stdin processes outside the pseudo-Codex, including the descendants of a parallel pseudo-Codex, and pty-stdin ancestors of the hook, including the anchor | None of them is signalled | Unit (real processes) |
| TS-7 | (FR4, FR5) A target that ends after enumeration. Invalid standard input (empty, malformed, a JSON array, not UTF-8). Standard input left open. A garbled entry on the hook's ancestor chain. A signal error other than no-such-process | No error. Every path writes nothing to stdout or stderr and exits 0. Invalid or open stdin stops nothing. After a failure, no further signal is sent | Unit (real processes + in-process) |
| TS-8 | (NFR5) Process table unavailable (a nonexistent process-table location, in-process) | Nothing is signalled; exit 0 with no output | Unit (in-process) |
| TS-9 | (SPEC MV-1, AC-3, FR8) Real Codex: `python3 -i` and `bash -i` left running with tty:true | After exit, neither process remains. Result recorded | Manual |
| TS-10 | (SPEC MV-2, AC-4, FR8) Real Codex: read-only commands only | The hook stops nothing. Result recorded | Manual |
| TS-11 | (SPEC MV-3, AC-5, FR8) Real Codex: TS-9 repeated through readwrite and through `--litellm` | Targets are found and stopped with the same determination. Result recorded | Manual |
| TS-12 | (SPEC MV-4, AC-6, FR7, FR8) Real Codex, readonly and readwrite: processes intentionally left in the background | Whether each one is caught is recorded, for both modes | Manual |
| TS-13 | (FR7) A pty-stdin descendant running in its own session and process group (like a detached background process), next to a pipe-stdin background descendant | The pty one is stopped like any other target; the pipe one remains | Unit (real processes) |
| TS-14 | (NFR4, NFR5) Import check of the hook and both test modules. Harness shape of both modules | Standard-library imports only. The wrapper tests always run the stub codex with an isolated HOME. Every anchor in the hook tests is a process the test started | Unit |
| TS-15 | (NFR6, TM-1, TM-2, TM-4) (a) A stdin JSON object whose fields name other PIDs or paths. (b) Anchor argument missing, more than one, not ASCII digits only, equal to 1, or not a proper ancestor of the hook. (c) A process-name field with spaces and parentheses that imitate the following fields | (a) The targets are the same as with `{}`. (b) Nothing is signalled. (c) Parent and start time are read correctly: an outsider with a forged name is not targeted, and a descendant with a forged name is | Unit (real processes + in-process) |
| TS-16 | (FR4, NFR1, TM-3) The start time of a target changes between enumeration and SIGTERM, and also between SIGTERM and SIGKILL (in-process) | That target receives no further signal | Unit (in-process) |
| TS-17 | (FR2, TM-6) Copies of each plugin's `scripts/` under a path with a space and a single quote, plus the existing hostile directory names for the em-workflow default path and em-review | The `hooks.Stop=` value parses as TOML, and the command passes exactly the copied hook path and the wrapper's PID to `python3` | Unit (subprocess) |
| TS-18 | (FR8, NFR3) Stub codex. em-workflow `--litellm`, readonly and readwrite, with `XDG_CACHE_HOME` absolute, unset or relative, and `TMPDIR` set to a separate directory. Also: `HOME` empty with no `XDG_CACHE_HOME`, and the default route | On `--litellm`, the launch home the stub sees is directly under the cache base's `em-workflow` directory, not under `TMPDIR` and not under the user's Codex home, owner-only, with the same files as before; it is gone after exit, also when codex exits non-zero. With no cache base, one diagnostic and a non-zero exit without launching codex. The default route sets no `CODEX_HOME` and creates nothing under the cache base | Unit (subprocess) |

## Code Quality Verification
- Format: not configured (`format_command` is empty).
- Static analysis: not configured.
- The byte identity of the two hook copies is checked by TS-2.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; the full test run passes |
| SC-2 | All test scenarios pass | TS-1 to TS-8 and TS-13 to TS-18 pass in the test run; TS-9 to TS-12 are performed |
| SC-3 | AC-1 to AC-6 are satisfied | AC-1: TS-1. AC-2: TS-3, TS-4. AC-3: TS-9. AC-4: TS-10. AC-5: TS-11. AC-6: TS-12 |
| SC-4 | MV-1 to MV-4 are performed and recorded | The results of TS-9 to TS-12 are recorded |
| SC-5 | Code review is completed | Review phase result |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1 |
| FR2 | task0001, task0002 | TS-1, TS-2, TS-17 |
| FR3 | task0001 | TS-3, TS-4, TS-6 |
| FR4 | task0001 | TS-4, TS-5, TS-7, TS-16 |
| FR5 | task0001 | TS-7 |
| FR6 | task0002 | TS-1 |
| FR7 | task0001 | TS-12, TS-13 |
| FR8 | task0003 (the `--litellm` launch home that TS-11 needs); otherwise the verify phase | TS-9, TS-10, TS-11, TS-12, TS-18 |
| NFR1 | task0001 | TS-6, TS-15, TS-16 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0002, task0003 | TS-1, TS-18 |
| NFR4 | task0001, task0002 | TS-14 |
| NFR5 | task0001 | TS-8, TS-14 |
| NFR6 | task0001, task0002 | TS-15 |

## Manual Testing (E2E Not Possible)

Common procedure for TS-9 to TS-12:
- Use a real Codex and record the Codex version in each result.
- The PreToolUse guard denies interactive launches. Runs that must leave
  `python3 -i` or `bash -i` running therefore use a temporary copy of the
  plugin's `scripts/` directory, with `references/codex-cli.yaml` beside it,
  that leaves out `codex-hook-interactive-guard.py`. The wrapper registers the
  guard path without checking it, so only the guard is missing in that copy.
  The wrapper and the Stop hook are the ones under test. Confirm in the run's
  output that the launch was not denied.
- Before and after each run, take a read-only process listing (PID, parent,
  state, terminal, command line) and record the matching lines.
- The verifier sends no signal. If a process remains, record its PID and
  command line as failure evidence and leave the cleanup to the user.
- Every process the verifier itself starts for a check has a lifetime that
  ends on its own.

Items:
- [ ] TS-9 (SPEC MV-1): readonly launch of the copied em-workflow wrapper. The
  prompt asks Codex to start `python3 -i` and `bash -i` through its exec tool
  with tty:true, leave them running, and finish. Expected: after the wrapper
  exits, neither process exists. Record the before / after listing.
- [ ] TS-10 (SPEC MV-2): readonly launch of the installed wrapper (guard
  present). The prompt runs read-only commands only (list files, read a file,
  show git status). Before the run, start a sentinel outside the launch whose
  standard input is a pseudo-terminal and that ends on its own. Expected: the
  run finishes with its normal exit status and output, nothing belonging to
  the run is stopped, and the sentinel is still alive after the run. Record.
- [ ] TS-11 (SPEC MV-3): repeat TS-9 with readwrite, and with
  `--litellm MODEL`, on the copied em-workflow wrapper. Also repeat it with
  readwrite on a copied em-review wrapper. Expected: both processes are gone
  after exit on every route. If the LiteLLM proxy is unavailable, record the
  `--litellm` part as not performed and give the reason.
- [ ] TS-12 (SPEC MV-4): on readonly and on readwrite, the prompt asks Codex
  to leave two intentionally backgrounded processes that end on their own
  within a few minutes: one started with tty:true and one started without a
  terminal. Record, for each mode and each process, whether the hook stopped
  it. The determination is unchanged (FR7): only the result is recorded.

## Performance / Security Verification (if applicable)
- NFR2: the hook's wall-clock time is under 3 s with a SIGTERM-ignoring target (TS-5).
- TM-1: the target determination takes nothing from standard input — checked by TS-15 (a): a stdin object naming other PIDs or paths gives the same targets as `{}`.
- TM-2: the wrapper's own PID is the anchor, and the hook acts only for a valid anchor that is a proper ancestor — checked by TS-1 (the anchor equals the wrapper's PID), TS-6 (outsiders, the parallel tree and the hook's ancestors receive no signal) and TS-15 (b) (an invalid or non-ancestor anchor signals nothing).
- TM-3: start-time identity check before each SIGTERM and SIGKILL — checked by TS-16.
- TM-4: parent and start time are read after the last closing parenthesis of the name field — checked by TS-15 (c).
- TM-5: bounded stdin read, a single 0.5 s wait, and exit 0 with no output on every path — checked by TS-7 (open stdin, garbled ancestor entry, signal error) and TS-5 (time bound).
- TM-6: two-layer shell / TOML encoding of the Stop hook command — checked by TS-17.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 18 | 14 (TS-1 to TS-8, TS-13 to TS-18) | 0 | 4 (TS-9 to TS-12) |
| Success criteria | 5 | 2 (SC-1, SC-2) | 0 | 3 (SC-3, SC-4, SC-5) |
| Requirements coverage | 14 | 13 | 0 | 1 (FR8) |
| Performance / security items | 7 | 7 (NFR2, TM-1 to TM-6) | 0 | 0 |
