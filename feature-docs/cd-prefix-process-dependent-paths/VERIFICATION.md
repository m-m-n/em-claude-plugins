# Verification Document: cd-prefix-process-dependent-paths

## Overview
**Feature**: cd-prefix-process-dependent-paths / **SPEC.md**: `feature-docs/cd-prefix-process-dependent-paths/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/cd-prefix-process-dependent-paths/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/cd-prefix-process-dependent-paths/THREAT-MODEL.md`

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty; the hook is a Python script run directly).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0; every test passes or is skipped only by the /proc platform guard.
- Coverage target: no coverage tool is configured for this component; coverage is judged by the scenario table below, in which every scenario has an automated test.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `/proc/self/cwd/<name>`, `/proc/self/cwd/../<name>`, `/proc/thread-self/cwd/<name>`, `/proc/self/fd/<N>` and `/dev/fd/<N>` (descriptor opened on an area directory), `/proc/<own pid>/cwd/<name>`, `/proc/self/root<inside>`, `/proc/self/root/..<inside>` | `is_below` is False, including forms whose final resolution is strictly below the area | Unit |
| TS-2 | Lexical variants `//proc/self/cwd/<name>`, `/./proc/self/cwd/<name>`, `/<existing directory>/../proc/self/cwd/<name>`, trailing slash | `is_below` is False | Unit |
| TS-3 | Links inside the area: target `/proc/self/cwd`; target `/dev/fd/<N>`; target `/proc/self` followed by `/cwd/<name>` | `is_below` is False | Unit |
| TS-4 | `<area>/.../proc`, `<area>/.../procfoo`, `<area>/.../dev/fd`, the existing in-area form and the `@HOP@/../sub` form | `is_below` is True | Unit |
| TS-5 | Existing NUL, resolution-error and lenient-realpath cases | Still pass unchanged | Unit |
| TS-6 | Hook subprocess whose own working directory differs from the input cwd; `/proc/self/cwd` forms in front of an approved string; input cwd is the main tree and a git worktree | No output in both cases | Integration |
| TS-7 | `/proc/self/root/..` prefix in front of a worktree path (the changed existing test) | No output from the main tree and from a git worktree | Integration |
| TS-8 | Existing hook-level PATH_CASES, operator and safe-side test groups | Unchanged results | Integration |
| TS-9 | `TestPathConditionWording`, `TestAc6DocstringStatesTheConditions`, `tests/test_cd_prefix_exception_docs.py` | Pass with the extended wording | Unit |
| TS-10 | Link loop inside the area, and a link chain longer than the followed-link bound, through `is_below` and through the hook | `is_below` is False; the hook exits 0, writes nothing to stderr, does not allow | Unit / Integration |
| TS-11 | OSError or ValueError injected while a stage is probed or a link target is read | `is_below` is False | Unit |
| TS-12 | Imports of `bash_guard.py` | Standard-library modules only | Unit |
| TS-13 | Executable text of `bash_guard.py` | No `status` substring | Unit |
| TS-14 | Child-process guard over the added /proc, /dev/fd and link forms | The path check starts no child process | Unit |
| TS-15 | Imports and data sources of the new tests | Standard library only; no real `~/.claude` state or real `workflow.yaml` read | Unit / Review |
| TS-16 | Signature of `is_below` and its call in `is_cd_prefixed_approved` | Parameters stay `(path, area)`; the caller is unchanged | Unit / Review |
| TS-17 | Module docstring path item and Verbatim execution rule path item | Both state the FR1 rule (/proc, /dev/fd, the written path, the stages of both resolutions, link targets); the matcher fires on forged text | Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- Diff check: `feature-docs/is-below-physical-fallback/` has no change in the integrated diff (SPEC A2).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | With the hook's process cwd placed so the path resolves below the area and the input cwd in the main tree or a git worktree, both `/proc/self/cwd` forms produce no output | TS-6 |
| AC-2 | Every FR6 (2) form makes `is_below` False, including forms whose final resolution is strictly below the area | TS-1, TS-2, TS-3 |
| AC-3 | `proc`, `procfoo` and `dev/fd` directories inside the area keep `is_below` True | TS-4 |
| AC-4 | The `/proc/self/root/..` prefix form produces no output from both trees, and `is_below` is False for it | TS-1, TS-7 |
| AC-5 | The approved string alone is still allowed; a refused form with a declared but unapproved remainder is judged as without cd (no new deny) | TS-6, TS-8 |
| AC-6 | Both prose places state the FR1 rule; the existing wording matchers pass | TS-9, TS-17 |
| AC-7 | The full suite passes; only the two FR6 expectations change; lines 870-915 of the test file are kept | Test Verification command, TS-5, TS-8 |
| SC-1 | All functional requirements implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | Test Verification command |
| SC-3 | Non-functional requirements met | TS-5, TS-10 to TS-16 |
| SC-4 | Prose updated (FR5) | TS-9, TS-17 |
| SC-5 | Code review completed | Review phase result |
| SC-6 | `python3 -m unittest discover -s tests` passes | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-6 |
| FR2 | task0001 | TS-1, TS-7 |
| FR3 | task0001 | TS-6, TS-7 |
| FR4 | task0001 | TS-4, TS-5, TS-8 |
| FR5 | task0002 | TS-9, TS-17 |
| FR6 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-6, TS-7 |
| NFR1 | task0001 | TS-12 |
| NFR2 | task0001 | TS-13 |
| NFR3 | task0001 | TS-14 |
| NFR4 | task0001 | TS-5, TS-11 |
| NFR5 | task0001 | TS-10 |
| NFR6 | task0001, task0002 | TS-15 |
| NFR7 | task0001 | TS-16 |

## Manual Testing (E2E Not Possible)
- [ ] Read the updated path item in the module docstring and in the Verbatim execution rule side by side and confirm they state the same rule, and that neither describes the `/proc/self/root/..` prefix form as allowed.

## Performance / Security Verification (if applicable)
- NFR5: the followed-link bound equals the kernel's own limit for one resolution; a loop or a longer chain makes the check False (TS-10).
- TM-1: the written path and every stage of both resolutions are checked against /proc and /dev/fd, with no `/proc/self/root/..` exception, and the refused form is judged as without cd — checked by TS-1, TS-2, TS-6 and TS-7 (False from `is_below`, no output through the hook with a differing process cwd).
- TM-2: every followed link target and every stage after it is checked — checked by TS-3 (links inside the area pointing at `/proc/self/cwd`, `/dev/fd/<N>`, `/proc/self`).
- TM-3: the followed-link bound and loop detection — checked by TS-10 (False, and the hook exits 0 without allowing).
- TM-4: no fail-open on errors inside the new checks — checked by TS-11 (injected OSError and ValueError make the check False) and TS-5 (existing error cases unchanged).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 17 | 17 | 0 | 0 |
| Code quality (diff check) | 1 | 1 | 0 | 0 |
| Success criteria | 13 | 12 | 0 | 1 |
| Manual | 1 | 0 | 0 | 1 |
| Performance / Security (NFR5, TM-1 to TM-4) | 5 | 5 | 0 | 0 |
