# Verification Document: artifact-digest-intermediate-symlink

## Overview
**Feature**: artifact-digest-intermediate-symlink / **SPEC.md**: `feature-docs/artifact-digest-intermediate-symlink/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/artifact-digest-intermediate-symlink/IMPLEMENTATION.md`

Scenario IDs use the TS-n form. TS-1 to TS-7 follow SPEC.md's own test
scenarios in order, with the same numbers. TS-8 to TS-11 are added by this
plan to cover FR3/FR5 blocking, NFR2, NFR1/NFR3 and NFR4.

## Build Verification
- Command: none. `project.components.main.build_command` is empty: this is
  Python / Markdown with no build step.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (`project.components.main.test_command`),
  run from the integration worktree root.
- Expected: exit code 0 with no failures or errors. The only skips allowed are
  the environment-gated cases named below (TS-3, the permission case of TS-4,
  and the FIFO cases of TS-8 where FIFOs cannot be created).
- Coverage target: not measured, because no coverage tool is configured.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC AC1) `tmp/outside/a.md` exists and `tmp/work/link` points to `../outside`. Run from `tmp/work` with `link/a.md`. | One entry: `path` `link/a.md`, `sha256` null, `error` `not_a_regular_file`. Exit code 1. The digest of `outside/a.md` does not appear on stdout. | Integration (script run) |
| TS-2 | (SPEC AC2) One subTest per case: an absolute path through the link (built from the resolved temp root), `sub/link/x/a.md`, `dangling/a.md`, `file-link/x` where `file-link` points to a regular file, and `loop-a/x` in a link loop. Each case is run alongside a regular file. | Every case gives `not_a_regular_file`, `sha256` null and exit code 1. The regular file in the same invocation is still hashed. | Integration (script run) |
| TS-3 | (SPEC AC3) Run `/proc/self/root/etc/hosts` and `/etc/hosts` in one invocation. Skipped unless `/proc/self` is a symlink and `/etc/hosts` exists. | Entry 0 is `not_a_regular_file`, entry 1 carries a sha256, exit code 1. | Integration (script run) |
| TS-4 | (SPEC AC4) Path spellings, trailing slashes and permissions: `plain.md/child.md`, `no-such-dir/a.md`, the empty argument, `a.md/`, `a.md/.`; `dir/`, `link-to-dir/`; `sub/../sub/a.md`, `sub//a.md`, `./sub/a.md` and the resolved absolute path of `sub/a.md`; an intermediate directory with mode 0o000. | `missing` for the first five. `not_a_regular_file` for the next two. The same digest as `sub/a.md` for the four spellings. `unreadable` for the 0o000 directory (skipped when running as root, or when access succeeds anyway). The existing error-token tests pass without modification. | Integration (script run) |
| TS-5 | (SPEC AC5) A swap driver steps in on each directory-only open made relative to a directory descriptor. It replaces the named directory with a symlink to an outside directory, then performs the real open. | `not_a_regular_file`. The outside file's digest does not appear on stdout. The existing final-element swap test passes without modification. | Integration (in-process) |
| TS-6 | (SPEC AC6) Three subTests run the script in-process: one after removing the no-follow open flag, one after removing the directory-only open flag, and one after withdrawing descriptor-relative open support. | Each gives exit code 2, empty stdout, and a stderr message that names the missing capability and contains no traceback. | Integration (in-process) |
| TS-7 | (SPEC AC7) Document assertions on text sliced by heading or line: the "Calculation" section of `em-workflow/references/artifact-digest.md`, and the script's docstring and `OPEN_FLAGS` comment. | The `not_a_regular_file` item contains "or a path any of whose components is a symlink", and the exit code `2` item includes the platform-capability case. The phrase appears only inside "Calculation". The docstring's `not_a_regular_file` line and "Entry kinds" paragraph do not limit the no-follow rule to the final component. The docstring's exit code 2 line includes the capability case. The `OPEN_FLAGS` comment says that no component is followed. Existing tests in `tests/test_artifact_digest_docs.py` and `tests/test_digest_contract_alignment.py` pass without modification, and `check-plugin-invariants.py` exits 0. | Unit (document) |
| TS-8 | (FR3, FR5) An intermediate FIFO component `fifo/x`, and a FIFO as the final element, each run under a bounded timeout. | `missing` for the intermediate FIFO and `not_a_regular_file` for the final one. Both return promptly with no hang. | Integration (script run) |
| TS-9 | (NFR2) One in-process run whose arguments produce a digest, `missing`, `unreadable`, `not_a_regular_file` through an intermediate symlink, and a directory-required failure. | After the run, no descriptor opened during it is still open. | Integration (in-process) |
| TS-10 | (SPEC AC8; NFR1, NFR3) Run the full suite and diff the existing tests against `workflow.implement.base_commit`. | `python3 -m unittest discover -s tests` exits 0, including the existing standard-library-only / no-child-process test. No existing test method is changed in `tests/test_artifact_digest_script.py` or `tests/test_artifact_digest_docs.py`, and `tests/test_digest_contract_alignment.py` has no diff. | Integration (suite + diff) |
| TS-11 | (NFR4) Compare plugin versions with `workflow.implement.base_commit`. | The `version` in every `.claude-plugin/plugin.json`, and the `version` of every entry in `.claude-plugin/marketplace.json`, equals its value at `workflow.implement.base_commit`. | Static (diff) |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- Plugin invariants: `check-plugin-invariants.py`, which SPEC.md AC7 names
  without a path. Find it in the repository and run it with `python3` from the
  worktree root. Expected: exit code 0. This check is counted in TS-7.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC AC1 to AC8 are all met | TS-1 to TS-7, TS-10 |
| SC-2 | The FR7 documentation update is done | TS-7 |
| SC-3 | The existing tests listed in NFR3 pass without modification | TS-7, TS-10 |
| SC-4 | The reproduction no longer returns two equal digests: `python3 -B em-workflow/scripts/artifact-digest.py /proc/self/root/etc/hosts /etc/hosts` gives entry 0 `not_a_regular_file` and exit code 1 | TS-3, plus the manual run below |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-4 |
| FR2 | task0001 | TS-1, TS-2, TS-3 |
| FR3 | task0001 | TS-4, TS-8 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-5, TS-8 |
| FR6 | task0001 | TS-6 |
| FR7 | task0002 | TS-7 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-9 |
| NFR3 | task0001, task0002 | TS-7, TS-10 |
| NFR4 | task0001, task0002 | TS-11 |

## Manual Testing (E2E Not Possible)
- [ ] On Linux, from the integration worktree root, run the SC-4 reproduction
  command. Confirm that entry 0 is `not_a_regular_file` with `sha256` null,
  entry 1 carries a sha256, and the exit code is 1.

## Performance / Security Verification (if applicable)
- NFR1: memory stays bounded through chunked reading, with the standard
  library only and no child process. Checked by the existing
  standard-library-only / no-child-process test inside TS-10.
- TM-1: the walk opens one component at a time without following a symlink,
  and a symlink at any component yields `not_a_regular_file` with no digest.
  Checked by TS-1, TS-2, TS-3 and the manual reproduction run.
- TM-2: there is no gap between a check and the open. A swap at an
  intermediate or final component yields only an error token. Checked by TS-5.
- TM-3: when an FR6 capability is missing, the script fails closed with exit
  code 2 and empty stdout, and never falls back to resolving the whole path.
  Checked by TS-6.
- TM-4: opens are non-blocking and intermediate opens accept directories only,
  so a FIFO at an intermediate or final component returns promptly. Checked by
  TS-8.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-11) | 11 | 11 | 0 | 0 |
| Code quality (plugin invariants) | 1 | 1 | 0 | 0 |
| Success criteria (SC-1 to SC-4, through the scenarios above) | 4 | 4 | 0 | 0 |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Manual reproduction run | 1 | 0 | 0 | 1 |
