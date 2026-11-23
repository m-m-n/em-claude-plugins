# Verification Document: version-bump-missing-base

## Overview
**Feature**: version-bump-missing-base / **SPEC.md**: `feature-docs/version-bump-missing-base/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/version-bump-missing-base/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (no coverage tool is configured); every automated scenario below maps to at least one test

### Test Scenarios from SPEC.md
TS-1 to TS-14 come from SPEC.md. TS-15 to TS-23 are added by this plan to cover requirements and acceptance criteria that have no SPEC.md scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Extract the heredoc from the workflow YAML | Exactly one heredoc is found and extracted | Unit |
| TS-2 | Compare the workflow with the plugin-dev template | Byte-identical | Unit |
| TS-3 | Read the ruleset definition file | Only the non_fast_forward rule, empty bypass_actors, enforcement active, target main | Unit |
| TS-4 | Push with BEFORE present in the clone and a change under a plugin | The plugin's patch is raised by 1 | Integration |
| TS-5 | BEFORE unreachable in the bare repository (removed from every ref), uploadpack.allowAnySHA1InWant enabled on the bare side | BEFORE is fetched once and used as the base; the version is raised; exit 0 | Integration |
| TS-6 | BEFORE absent from the bare repository too | AFTER's first parent is the base; stdout carries a `::warning::` line | Integration |
| TS-7 | BEFORE is all zeros | AFTER's first parent is the base; a `::warning::` line is printed | Integration |
| TS-8 | BEFORE unavailable and AFTER is a root commit | Non-zero exit; both JSON files unchanged | Integration |
| TS-9 | Reproduction: an update commit is added, main is replaced by a merge commit that does not contain it, and the next push runs | AFTER's version is greater than the base's version; plugin.json and marketplace.json hold the same value | Integration |
| TS-10 | AFTER's version lower than / equal to / higher than the base's | Lower and equal: the greater version with patch + 1 in both JSON files. Higher: unchanged, bumped empty | Integration |
| TS-11 | New plugin; version not in MAJOR.MINOR.PATCH form | Not bumped | Integration |
| TS-12 | marketplace.json entry without a version | Not rewritten | Integration |
| TS-13 | workflow_dispatch: current <= min_version with equal major and minor; current > min_version; unregistered plugin; malformed min_version; current <= min_version with different major or minor | In order: min_version patch + 1 in both JSON files / no file change, exit 0, bumped empty / no file change, non-zero / no file change, non-zero / no file change, non-zero | Integration |
| TS-14 | bumped value in GITHUB_OUTPUT, including the empty case | name@version of each bumped plugin, comma-separated; empty when nothing is bumped | Integration |
| TS-15 | workflow_dispatch declaration and ref guard in the workflow YAML | Required inputs plugin and min_version; the version-update step runs under workflow_dispatch only when the ref is refs/heads/main | Unit |
| TS-16 | Conditions of the pull request create/merge steps | They run whenever bumped is non-empty, for both push and workflow_dispatch | Unit |
| TS-17 | Route of event values and dispatch inputs into the heredoc | The step's env defines every variable the heredoc reads; the heredoc body contains no Actions expression | Unit |
| TS-18 | Dependencies of the heredoc | Only standard-library modules are imported (automated); no external command other than git is run (review) | Unit + review |
| TS-19 | Isolation of the new test modules | No network, nothing under `~/.claude` read, git operated only inside temporary directories (C4) | Review |
| TS-20 | Post-merge procedure documents | `.github/rulesets/README.md` holds (a) ruleset creation and confirmation; README.md's maintenance section points to (a) and holds (b) the workflow_dispatch run and its confirmation and (c) the cache confirmation | Manual |
| TS-21 | create.md 「動き」 | States the FR1-FR5 behavior per IMPLEMENTATION.md C1; no skip-with-success statement remains | Manual |
| TS-22 | Version fields across the feature's changes | The diff between `workflow.implement.base_commit` and the integration tip changes no version field in any plugin.json or in `.claude-plugin/marketplace.json` | Automated (git diff) |
| TS-23 | Concrete version values in SPEC.md, the plans and acceptance criteria | None present | Manual |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | Test command exit 0; manual items TS-19 to TS-21 and TS-23 checked |
| SC-3 | Security requirements are satisfied | Performance / Security Verification below (TM-1 to TM-5) |
| SC-4 | Documentation is complete | TS-20, TS-21 |
| SC-5 | Code review is completed | Review phase result |
| SC-6 | `python3 -m unittest discover -s tests` exits 0 (SPEC AC-16) | Test command |
| SC-7 | The feature's changes leave every plugin.json and marketplace.json version unchanged (NFR4) | TS-22 |

### SPEC Acceptance Criteria
| SPEC AC | Verified by |
|---------|-------------|
| AC-1 | TS-5 |
| AC-2 | TS-6, TS-7 |
| AC-3 | TS-8 |
| AC-4 | TS-9 |
| AC-5 | TS-10 |
| AC-6 | TS-10, TS-14 |
| AC-7 | TS-11 |
| AC-8 | TS-13 |
| AC-9 | TS-13, TS-14 |
| AC-10 | TS-13 |
| AC-11 | TS-15 |
| AC-12 | TS-2, TS-6, TS-8 (absence of the skip branch is asserted with TS-8) |
| AC-13 | TS-3 |
| AC-14 | TS-20 |
| AC-15 | TS-21 |
| AC-16 | Test command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-4, TS-5, TS-6, TS-7, TS-8, TS-9 |
| FR2 | task0001 | TS-4, TS-9, TS-14 |
| FR3 | task0001 | TS-10, TS-11, TS-12 |
| FR4 | task0001 | TS-13, TS-15 |
| FR5 | task0001 | TS-14, TS-16 |
| FR6 | task0001 | TS-2 |
| FR7 | task0002 | TS-3 |
| FR8 | task0002, task0003 | TS-20 |
| FR9 | task0003 | TS-21 |
| FR10 | task0001, task0002 | TS-1, TS-2, TS-3, TS-9 |
| NFR1 | task0001 | TS-18 |
| NFR2 | task0001 | TS-1 |
| NFR3 | task0001, task0002 | TS-19 |
| NFR4 | task0001, task0002, task0003 | TS-22 |
| NFR5 | task0001, task0002, task0003 | TS-23 |

## Manual Testing (E2E Not Possible)
No E2E framework is configured. The following are checked by reading the files:
- [ ] TS-18 (review half): the heredoc runs no external command other than git.
- [ ] TS-19: the new test modules build their subprocess environment explicitly, point HOME and git's global configuration into the temporary directory, use only local bare repositories as remotes, and read nothing under `~/.claude`.
- [ ] TS-20: `.github/rulesets/README.md` and README.md's maintenance section hold procedures (a), (b) and (c) as stated in the scenario table; the concrete min_version value appears only in procedure (b).
- [ ] TS-21: create.md's 「動き」 matches IMPLEMENTATION.md C1 item by item.
- [ ] TS-23: SPEC.md, IMPLEMENTATION.md, VERIFICATION.md and every task plan contain no concrete version value.

Not performed in this run (A7): creating the ruleset on GitHub, running workflow_dispatch, updating the marketplace and restarting Claude Code. These are the human steps documented by TS-20.

## Performance / Security Verification (if applicable)
- Performance: not applicable.
- TM-1: dispatch inputs and event values reach the heredoc only through the step's environment variables, and the heredoc body contains no Actions expression — checked by TS-17 (unit test on the YAML text) and review of the step's env block.
- TM-2: an unregistered plugin, including a value shaped like a relative path, exits non-zero with no file changed — checked by TS-13.
- TM-3: a malformed min_version, including one with trailing text and one containing a line break, exits non-zero with no file changed and no bumped value written — checked by TS-13.
- TM-4: under workflow_dispatch the version-update step runs only when the ref is refs/heads/main — checked by TS-15.
- TM-5: the ruleset definition holds only the non_fast_forward rule on main with enforcement active and an empty bypass list — checked by TS-3; its effect on GitHub starts only after procedure (a) is run (A7).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (file text) | TS-1, TS-2, TS-3, TS-15, TS-16, TS-17, TS-18 | 7 | 0 | 1 (TS-18 review half) |
| Integration (temporary repositories) | TS-4 to TS-14 | 11 | 0 | 0 |
| Repository check | TS-22 | 1 | 0 | 0 |
| Review / documents | TS-19, TS-20, TS-21, TS-23 | 0 | 0 | 4 |
| Security (TM-1 to TM-5) | 5 | 5 (through TS-3, TS-13, TS-15, TS-17) | 0 | 0 |
| Total scenarios | 23 | 19 | 0 | 4 (+1 review half) |
