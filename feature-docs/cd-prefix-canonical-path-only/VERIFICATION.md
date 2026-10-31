# Verification Document: cd-prefix-canonical-path-only

## Overview
**Feature**: cd-prefix-canonical-path-only / **SPEC.md**: `feature-docs/cd-prefix-canonical-path-only/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/cd-prefix-canonical-path-only/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/cd-prefix-canonical-path-only/THREAT-MODEL.md`

## Build Verification
- Command: not configured (`project.components.main.build_command` is empty)
- Expected: nothing to run

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, every test passes (the full suite, including
  `tests/test_tests_yaml_id_resolution.py`)
- Coverage target: no coverage tool is configured. Coverage is judged by
  the acceptance-criterion-to-test mapping in each task's
  `test-docs/cd-prefix-canonical-path-only/{T}.tests.yaml` record.

### Test Scenarios from SPEC.md
TS1 to TS11 come from SPEC.md. TS12 to TS15 were added during planning for
requirements that SPEC.md's scenarios do not name (FR7 for the implementer
procedures, the within-bound half of NFR4, NFR1 and NFR2).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Through the hook, `cd "<p>" && <approved>` for `<area>/task0001`, `<area>/task0001/sub/deeper`, canonical directories whose names hold a space or `&&`, and a git worktree below the area; the hook's cwd is first the main worktree, then a git worktree | `allow` with the cd prefix reason in every case | Integration |
| TS2 | Through the hook and by a direct `is_below` call: `<in>/`, `<area>//task0001`, `//` followed by the rest of `<in>`, `<in>/.`, `<area>/./task0001`, `<in>/..`, `<in>/sub/../sub` | Silent through the hook; `is_below` is False | Integration + Unit |
| TS3 | Same two ways: a link inside the area to an in-area directory, a link to outside the area, a broken link, a link to a file, the former `FALLBACK_ALLOW_CASES` forms and the relative-link forms | Silent; False | Integration + Unit |
| TS4 | Same two ways: `/`, the area itself, a sibling sharing the area's name prefix, another repository's area, a nonexistent path, a regular file, each /proc and /dev/fd form | Silent; False | Integration + Unit |
| TS5 | `/dev/null` followed by 32000 repetitions of `/x`, and the area followed by 32000 repetitions of `/x`, through the candidate decision and `is_below`, with recording doubles on `worktree_area()` and the file-system entry points | False; the doubles record no call | Unit |
| TS6 | Bound source replaced by a double that raises OSError, returns 0, or returns a negative value; a path whose encoded length equals the bound; a path one byte shorter | False for each failure and for the equal length; the shorter path passes the length check and is decided by the remaining conditions | Unit |
| TS7 | Fixture repositories in which `.claude/worktrees/em-workflow`, and separately `.claude`, is a link to a directory outside the main worktree; and one in which `.claude/worktrees/em-workflow` links to a directory inside the main worktree | Outside: a canonical directory beyond the link is silent. Inside: the resolved canonical path is allowed, and the path through the link is silent | Integration |
| TS8 | A path holding NUL; a path holding a character the file-system encoding cannot encode (an unpaired surrogate escape in the JSON input); an injected resolution error; an error while the bound is obtained; a cd prefix form whose remainder matches a refusal pattern; the existing syntax, operator and safe-side tests | Path check False without raising; the hook exits 0, stderr empty, no allow; the refusal form denies; the existing tests (including `tests/test_bash_guard_cd_prefix_operators.py`) pass | Unit + Integration |
| TS9 | Document tests on the hook module and on the protocol's Verbatim execution rule | `_stage_walk_refuses`, `_under_proc_or_dev_fd`, `FOLLOWED_LINK_LIMIT` and `resolves_to_directory` are absent. The module docstring `path:` item, the `is_below` docstring and the protocol path item state FR1 (a) to (d), the no-normalization rule, the length bound, the area containment rule and the any-depth scope. None holds "logical path", "physical path", "/proc", "/dev/fd" or "stage". Forged-text cases fire. The existing `cd prefix:` paragraph checks and the "realpath" checks pass | Unit (document) |
| TS10 | Document test on Step I.2.a of `em-workflow/references/implement-phase.md` | It states that `$WT_ROOT/{T}` is canonicalized with a strict realpath once the worktree exists (created or reused) and passed as worktree_path, and that tests_yaml_path is derived from that canonical value. The pre-change placeholders and forged text without the statement fail the matcher | Unit (document) |
| TS11 | After the deleted test IDs are removed from past features' `test-docs/**/*.tests.yaml`: `python3 -m unittest discover -s tests` | Full pass, including `tests/test_tests_yaml_id_resolution.py`; no test calls, patches or names a removed symbol | Integration (suite) |
| TS12 | Document test on `em-workflow/agents/implementer.md` (Inputs, Step 3) and `em-workflow/skills/worktree-task-workflow/SKILL.md` (command execution gate) | Each place states that the cd target is the supplied worktree_path used as is and assumed to be a canonical absolute path; forged-text cases fire; the existing implementer cd-chain wording tests pass | Unit (document) |
| TS13 | For existing canonical directory chains below the area at two sizes, the number of file-system calls the path check makes, counted with recording doubles (no wall-clock threshold) | The count grows no faster than linearly with the number of components | Unit |
| TS14 | Standard-library-only checks: the existing `TestAc7StandardLibraryOnly` of `tests/test_bash_guard_cd_prefix.py`, and the self-check of `tests/test_canonical_worktree_path_docs.py` | The hook and both test modules import only standard library modules | Unit |
| TS15 | The path check runs for allowed and refused forms while child-process creation is replaced by a failing double; the existing git-shim check that no git call carries the prefixed path | No child process is started by the path check; no git call's cwd or arguments contain the path | Unit + Integration |

## Code Quality Verification
- Format: not configured (`format_command` is empty)
- Static analysis: not configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Only paths that satisfy all four conditions of FR1 are allowed | TS1, TS2, TS3, TS4 |
| AC2 | Over-bound paths are refused before traversal and before `worktree_area()`; a failed or non-positive bound refuses | TS5, TS6 |
| AC3 | Syntax restriction, exclusion rules, deny-pattern order, decision table and exception handling unchanged | TS8 |
| AC4 | The removed symbols and the logical/physical checks are gone from the code | TS9 |
| AC5 | A resolved area not strictly below the main worktree's realpath allows nothing; stated in the SPEC | TS7; the SPEC's FR5 section |
| AC6 | Canonical existing directories at any depth below the area are allowed; stated in the SPEC | TS1; the SPEC's FR6 section |
| AC7 | Protocol, module docstring, `is_below` docstring and implementer procedures match the new check; no old description remains | TS9, TS12 |
| AC8 | implement-phase.md passes the strict-realpath canonical `$WT_ROOT/{T}` as worktree_path and derives tests_yaml_path from it | TS10 |
| AC9 | Tests refuse trailing `/`, `//`, `.`, `..` and links, and confirm that long paths return immediately | TS2, TS3, TS5 |
| AC10 | `python3 -m unittest discover -s tests` passes in full | TS11 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS4 |
| FR2 | task0001 | TS5, TS6 |
| FR3 | task0001 | TS8 |
| FR4 | task0001 | TS9 |
| FR5 | task0001 | TS7 |
| FR6 | task0001 | TS1 |
| FR7 | task0001, task0002 | TS9, TS12 |
| FR8 | task0002 | TS10 |
| FR9 | task0001 | TS2, TS3, TS5, TS7, TS11 |
| FR10 | task0001 | TS11 |
| NFR1 | task0001, task0002 | TS14 |
| NFR2 | task0001 | TS15 |
| NFR3 | task0001 | TS8 |
| NFR4 | task0001 | TS5, TS13 |
| NFR5 | task0001 | TS6, TS8 |

## Manual Testing (E2E Not Possible)
- [ ] Real-layout check of FR5: from this repository's project root, feed
  the merged hook a PreToolUse payload (stdin) for each of three commands
  and read the decisions.
  - `cd "<canonical path of an existing task worktree of this feature>" && python3 -m unittest discover -s tests`:
    `allow`.
  - The same path with a trailing `/`: no decision.
  - The same path written with `/./` inserted: no decision.

  This confirms that the real `.claude/worktrees/em-workflow` passes the area
  containment rule. The approval store is only read.
- [ ] Read the module docstring's `path:` item and the protocol's path item
  side by side. Both state the same conditions in the same order: the area
  and its containment, (a) to (d), no normalization, the length bound, any
  depth, and errors counting as not below.
- [ ] Read Step I.2.a of implement-phase.md. Confirm that the
  canonicalization covers both a newly created worktree and one reused under
  the Resume guard, and that the payload placeholders and the
  `tests_yaml_path` paragraph use the canonical value.

## Performance / Security Verification
- NFR4: an over-bound path returns without `worktree_area()` or any
  file-system call (TS5); for a within-bound path, the file-system call
  count grows no faster than linearly with the components (TS13). No
  wall-clock threshold is used.
- TM-1: only already-canonical paths strictly below the area are accepted,
  never after normalization. Checked by TS2, TS3 and TS4: every
  non-canonical, link, outside-area, /proc and /dev/fd form is silent
  through the hook from both cwds, and `is_below` is False for each.
- TM-2: the run-time length bound refuses before `worktree_area()` and any
  file-system access, and a failed or non-positive bound refuses. Checked by
  TS5 (recording doubles record nothing), TS6 (bound failures and boundary
  lengths) and TS13 (linear growth).
- TM-3: every OSError and ValueError from the length check or the path check
  makes the path not allowed, with no new deny, exit code 0 and empty stderr.
  Checked by TS8 (NUL, an unencodable character, an injected resolution
  error, a bound error, observed through the hook) and TS6.
- TM-4: the resolved area is used only when it lies strictly below the
  realpath of the main worktree. Checked by TS7 (an area or ancestor linked
  outside refuses; linked inside allows only the resolved canonical path).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1 to TS15) | 15 | 15 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| SPEC success criteria (AC1 to AC10) | 10 | 10 | 0 | 0 |
| Performance / security (NFR4, TM-1 to TM-4) | 5 | 5 | 0 | 0 |
| Manual checks | 3 | 0 | 0 | 3 |
