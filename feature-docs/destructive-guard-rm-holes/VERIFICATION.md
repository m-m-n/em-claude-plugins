# Verification Document: destructive-guard-rm-holes

## Overview
**Feature**: destructive-guard-rm-holes / **SPEC.md**: `feature-docs/destructive-guard-rm-holes/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, single task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/destructive-guard-rm-holes/THREAT-MODEL.md`

Scenario IDs TS-1 to TS-11 correspond one-to-one to SPEC.md TS1 to TS11.

## Build Verification
- Command: none. Every component (hooks, repo-tests, plugin-invariants) has an empty build_command; the Python sources run as-is.
- Expected: not applicable

## Test Verification
- Command (hooks): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: each command exits 0 with no failing case, test or check
- Coverage target: no coverage tool is configured for these components; coverage is judged by scenario coverage — every TS-n below is executed and every Acceptance Criterion of task0001 maps to at least one test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Case suite: the hole-1 forms (a plain word sharing a scratch-root prefix, a relative parent traversal out of a scratch path, an absolute traversal from /tmp into a home directory) and the bare and trailing-slash forms of tmp, .cache and /var/tmp | All deny; the suite passes in full; no case is labelled as a known unfixed hole; no pre-existing deny / ask case changed or removed | Integration (hooks case suite) |
| TS-2 | Case suite plus unittest: an rm target made only of command substitution, in the dollar-paren and the backtick form | ask without CLAUDE_BATCH; deny with CLAUDE_BATCH, carrying the unchanged downgrade wording | Integration (hooks case suite) / Unit |
| TS-3 | A literal target outside the scratch area whose name carries planted instruction text | deny; the reason does not contain the planted text | Unit |
| TS-4 | Planted text inside a variable-bearing target, a glob-bearing target, a glob mixed with a parent reference, and a partially substituted target | Verdict and rule id equal the same shape without planted text; the reason does not contain the planted text | Unit |
| TS-5 | Several planted targets at the same verdict strength: several targets in one rm, and several rm joined with a semicolon | The joined reason contains none of the planted strings; each target is designated by a distinct position | Unit |
| TS-6 | A target containing a newline and a forged destructive-guard-style bracketed prefix | The reason contains neither the newline nor the forged prefix; stdout contains no control character | Unit |
| TS-7 | TS-3 to TS-6 rerun with CLAUDE_BATCH set | ask forms become deny; the reason contains none of the planted strings | Unit |
| TS-8 | HOME fixed by the test: a target under HOME with gio on PATH, the same target with gio removed from PATH, and a target outside HOME | gio trash template, mv template, mv template respectively; each carries a placeholder, never the target string; the reason names the target's position | Unit |
| TS-9 | The rm-recursive deny form with gio on PATH and with gio removed from PATH | The reason contains no mkdir and no command that creates or modifies .local/share/Trash | Unit |
| TS-10 | Existing reason tests in the command-substitution test module, rewritten to the position notation | Pass; the substitution stand-in stays identical, the direct and payload-carried forms render the same notation, the notation is never whitespace-only; the stdlib-only / no-new-call check passes; two runs of the same command give byte-identical stdout | Unit |
| TS-11 | Repository unittest discovery and the plugin-invariants check after the version bump | Both exit 0; em-workflow's version is raised at the patch position and equal in plugin.json and marketplace.json; em-review's version is unchanged | Integration |

## Code Quality Verification
- Format: none configured (format_command is empty for every component)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The case suite passes in full and has no known-unfixed-hole label | TS-1, TS-2 via the hooks test command |
| AC2 | The three hole-1 forms are deny | TS-1 |
| AC3 | Substitution-only targets (both forms) are ask, and deny under CLAUDE_BATCH | TS-2 |
| AC4 | Bare and trailing-slash tmp, .cache, /var/tmp are deny; no pre-existing deny / ask case became allow | TS-1 |
| AC5 | Planted text never appears in the reason on the rm-unresolvable, rm-recursive and joined paths, with and without CLAUDE_BATCH; verdict and rule id unchanged | TS-3, TS-4, TS-5, TS-6, TS-7 |
| AC6 | The rm-recursive reason carries the target position and a templated gio trash or mv alternative | TS-8 |
| AC7 | No reason contains mkdir or a trash-directory creation command, with or without gio | TS-9 |
| AC8 | Repository unittest discovery passes | TS-10 via the repo-tests command |
| AC9 | em-workflow version raised at the patch position and equal in both manifests; the invariants check exits 0 | TS-11 via the plugin-invariants command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-9 |
| FR4 | task0001 | TS-3, TS-4, TS-5, TS-6, TS-7, TS-8 |
| FR5 | task0001 | TS-1 |
| FR6 | task0001 | TS-3, TS-4, TS-5, TS-6, TS-7, TS-9, TS-10 |
| FR7 | task0001 | TS-10 |
| FR8 | task0001 | TS-11 |
| NFR1 | task0001 | TS-10 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-6, TS-10 |
| NFR4 | task0001 | TS-2, TS-7 |
| NFR5 | task0001 | TS-8, TS-9 |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction from the goal, re-expressed for the current tree (SPEC.md a6): run the hooks test command and confirm that no case in the case table is labelled as a known unfixed hole.

## Performance / Security Verification (if applicable)
- TM-1: SAFE_DELETE matched per path component on the normalized target, without re-opening bare scratch roots — checked by TS-1 (hole-1 forms and bare / trailing-slash tmp, .cache, /var/tmp all deny; no pre-existing deny / ask case changed).
- TM-2: substitution-only rm target yields ask, deny under CLAUDE_BATCH with the unchanged downgrade wording — checked by TS-2.
- TM-3: rm reasons designate targets only by unique position and templated alternatives; no planted target text reaches the reason — checked by TS-3, TS-4, TS-5, TS-7 and TS-8.
- TM-4: no newline, forged prefix or other control character from target text reaches the reason or stdout — checked by TS-6 (and TS-7 for the CLAUDE_BATCH variant).
- TM-5: no rm reason presents a command that creates or modifies the trash directory, with or without gio on PATH — checked by TS-9.
- NFR1: the hook adds no filesystem or subprocess call and stays standard-library only — checked by the existing check inside TS-10.
- NFR2: the same command yields the same verdict and byte-identical stdout — checked by TS-10.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 11 | 11 | 0 | 0 |
| Success criteria | 9 | 9 | 0 | 0 |
| Security (TM-1 to TM-5) | 5 | 5 | 0 | 0 |
| Other non-functional (NFR1, NFR2) | 2 | 2 | 0 | 0 |
| Manual | 1 | 0 | 0 | 1 |
