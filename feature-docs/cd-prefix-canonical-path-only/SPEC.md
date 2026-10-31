# Feature: cd-prefix-canonical-path-only

## Overview

The cd-prefix path check in bash_guard.py is replaced with a simple check
that allows only canonical absolute paths, and stops reproducing Bash's path
resolution. The stage walk, the fallback to the physical path, and the
special handling of `/proc` and `/dev/fd` are removed; a length bound and the
simple check absorb the quadratic slowdown of the stage walk.

Requirements document: `feature-docs/cd-prefix-canonical-path-only/REQUIREMENTS.md`.

## Objectives

- Replace the cd-prefix path check in bash_guard.py with a simple check that
  allows only canonical absolute paths, and stop reproducing Bash's path
  resolution.
- Remove the stage walk (`_stage_walk_refuses`), the fallback to the physical
  path, and the special handling of `/proc` and `/dev/fd`.
- Absorb the slowdown of the stage walk, which grows with the square of the
  number of path components, with a length bound and the simple check.

## User Stories

None.

## Technical Requirements

### Functional Requirements

- **FR1: Allow only canonical absolute paths.** A cd-prefix path satisfies the
  path condition only when all of the following hold:
  - (a) It is absolute and contains no empty component, `.` or `..` other
    than the root. The path is never normalized and then accepted.
  - (b) It lexically satisfies `strictly_below(path, area)`.
  - (c) `os.path.realpath(path, strict=True) == path`.
  - (d) `os.path.isdir(path)`.
- **FR2: Length bound.** The bound is obtained at run time with
  `os.pathconf('/', 'PC_PATH_MAX')`. When `len(os.fsencode(path))` is greater
  than or equal to the bound, the path is not allowed. This check runs before
  any filesystem traversal and before `worktree_area()` is called. When the
  bound cannot be obtained, or its value is not positive, the path is not
  allowed. `PC_PATH_MAX` is a limit on paths relative to a directory; here it
  is used as a conservative acceptance bound on the whole absolute path.
- **FR3: Syntax, exclusion rules, decision table and exception handling are
  unchanged.** The syntax restriction by `CD_PREFIX_RE`, the exclusion rules of
  `cd_remainder_excluded` (E1 to E10), the order in which deny patterns are
  applied to the whole command first, the hook's decision table, and the
  behavior of treating exceptions (`OSError`, `ValueError`) as not allowed do
  not change. A cd-prefix form whose path does not satisfy the path condition
  is judged as if it had no cd prefix; no new deny is produced.
- **FR4: Remove the old checks.** Remove `_stage_walk_refuses`,
  `_under_proc_or_dev_fd`, `FOLLOWED_LINK_LIMIT`, `resolves_to_directory`, and
  the dual logical/physical check (the comparison after normpath and the
  realpath of the path as written).
- **FR5: Allowed area containing links.** The allowed area resolved by
  `worktree_area()` is used only when it lies strictly below the realpath of
  the main worktree (the parent of the git common dir). Otherwise the
  cd-prefix form is not allowed.
- **FR6: Allowed scope.** The allowed scope is every existing directory
  strictly below the allowed area, at any depth (same as before).
- **FR7: Align documents with the new check.** Rewrite the path item of the
  Verbatim execution rule in command-execution-protocol.md, the path item of
  bash_guard.py's module docstring, and the docstring of `is_below` to the
  conditions of FR1, FR2, FR5 and FR6. Remove the descriptions of logical
  path, physical path, `/proc`, `/dev/fd` and the stage walk. In the
  implementer's procedures (agents/implementer.md,
  skills/worktree-task-workflow/SKILL.md), state that the cd target is the
  supplied worktree_path used as is, and that it is assumed to be a canonical
  absolute path.
- **FR8: Canonicalize worktree_path at the producer.** WT_ROOT is built only by
  string concatenation, so its form is not guaranteed to be canonical. In
  implement-phase.md, the producer canonicalizes `$WT_ROOT/{T}` created by
  `git worktree add` with realpath (strict) and passes that value as
  worktree_path. tests_yaml_path is derived from the canonicalized
  worktree_path, so that it stays below worktree_path.
- **FR9: Tests.** Add tests that reject paths with a trailing `/`, a duplicated
  `/`, `.`, `..`, or a link. Add tests that confirm the check returns
  immediately for long paths (for example `'/dev/null' + '/x' * 32000`, and a
  long path below the allowed area). Add a test that rejects the case where
  the allowed area resolves outside the main worktree. Clean up the tests of
  the removed checks so that all remaining tests pass.
- **FR10: Test records of past features.** Remove the deleted test IDs from
  past features' `test-docs/**/*.tests.yaml`. Reassign them to remaining tests
  where possible. `tests/test_tests_yaml_id_resolution.py` passes.

### Non-Functional Requirements

- **NFR1 - Standard library only:** The hook and its tests import only the
  standard library (the existing `TestAc7StandardLibraryOnly` is kept).
- **NFR2 - No child processes:** The path check starts no child process. The
  path is never used as a child process's working directory or argument.
- **NFR3 - Hook output discipline:** For every input the hook exits with code 0
  and writes nothing to stderr.
- **NFR4 - Decision time:** A path over the bound returns without traversal.
  For a path within the bound, the decision time does not grow with the
  square of the number of path components.
- **NFR5 - Fail closed:** When the check cannot decide, the path is not
  allowed. Not allowed is not a new deny; the command falls through to the
  other rows of the decision table.

## Implementation Approach

### Architecture

The change is confined to the cd-prefix path check of bash_guard.py, its
documentation, the worktree_path producer in implement-phase.md, and tests.

- `is_below(path, area)` keeps its name and arguments, and the decision table
  of its callers `is_cd_prefixed_approved` / `cd_prefix_allowed` /
  `hook_main` does not change. For FR2, the length check is placed before the
  call to `worktree_area()`.
- The set of exceptions treated as not allowed stays `OSError` and
  `ValueError`, as today.
- No run-time check of worktree_path is added to the implementer; the
  canonical form is guaranteed at the producer (FR8).

### Path condition

A cd-prefix path satisfies the path condition only when every check below
holds. The length check (FR2) runs first, before any filesystem traversal
and before `worktree_area()`; the order of the remaining checks is not fixed
by this SPEC.

```
length check (FR2)                                         ── first
resolved area strictly below realpath(main worktree) (FR5)
(a) absolute, no empty / . / .. components (FR1)
(b) strictly_below(path, area) (FR1)
(c) realpath(path, strict=True) == path (FR1)
(d) isdir(path) (FR1)

any check fails            → not allowed
OSError / ValueError       → not allowed
not allowed                → judged as if there were no cd prefix (FR3, NFR5)
```

### Allowed area containing links (FR5)

The allowed area resolved by `worktree_area()` is used only when it lies
strictly below the realpath of the main worktree (the parent of the git
common dir). Otherwise the cd-prefix form is not allowed.

### Allowed scope (FR6)

The allowed scope is every existing directory strictly below the allowed
area. Depth is not restricted.

### Dependencies

**Internal Dependencies:**
- bash_guard.py: the cd-prefix path check (FR1 to FR6).
- command-execution-protocol.md: Verbatim execution rule, path item (FR7).
- agents/implementer.md, skills/worktree-task-workflow/SKILL.md: implementer
  procedures (FR7).
- implement-phase.md: worktree_path and tests_yaml_path production (FR8).
- `test-docs/**/*.tests.yaml` of past features and
  `tests/test_tests_yaml_id_resolution.py` (FR10).

**External Dependencies:**
- Python standard library only (NFR1).

### Out of scope

- The SPEC.md files of the five past features under feature-docs/ are
  historical documents and are not changed.
- The design step is skipped.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/cd-prefix-canonical-path-only/**`
- `test-docs/cd-prefix-canonical-path-only/**`

`feature-docs/cd-prefix-canonical-path-only/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/cd-prefix-canonical-path-only/**` covers
`test-docs/cd-prefix-canonical-path-only/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Acceptance Criteria

- [ ] **AC1** (FR1): Only paths that satisfy all four conditions of FR1 are
  allowed.
- [ ] **AC2** (FR2): A path whose `os.fsencode` byte length is greater than or
  equal to `os.pathconf('/', 'PC_PATH_MAX')` is not allowed, before traversal
  and before `worktree_area()`. It is also not allowed when obtaining the
  bound fails or the value is not positive.
- [ ] **AC3** (FR3): The syntax restriction, the exclusion rules, the order of
  applying deny patterns, the decision table, and the behavior of treating
  exceptions as not allowed are unchanged (the existing operators tests,
  syntax tests, and SILENT path cases pass).
- [ ] **AC4** (FR4): `_stage_walk_refuses`, `_under_proc_or_dev_fd`,
  `FOLLOWED_LINK_LIMIT`, `resolves_to_directory`, and the logical/physical path
  checks are gone from the code.
- [ ] **AC5** (FR5): When the resolved allowed area is not strictly below the
  realpath of the main worktree, nothing is allowed. This handling is written
  in the SPEC.
- [ ] **AC6** (FR6): Canonical existing directories at any depth below the
  allowed area are allowed. This scope is written in the SPEC.
- [ ] **AC7** (FR7): The protocol, the hook's module docstring, the `is_below`
  docstring, and the implementer's procedures match the new check, and no
  description of the old check remains.
- [ ] **AC8** (FR8): implement-phase.md passes `$WT_ROOT/{T}` canonicalized with
  realpath (strict) as worktree_path, and derives tests_yaml_path from it.
- [ ] **AC9** (FR9): There are tests that reject paths with a trailing `/`,
  `//`, `.`, `..`, or a link, and tests that confirm the check returns
  immediately for long paths.
- [ ] **AC10** (FR9, FR10): `python3 -m unittest discover -s tests` passes in
  full (including `tests/test_tests_yaml_id_resolution.py`).

## Test Scenarios

### Path check tests
- [ ] **TS1** (AC1, AC6; FR1, FR6): `<area>/task0001`,
  `<area>/task0001/sub/deeper`, canonical directories whose names contain
  spaces or `&&`, and a git worktree below the allowed area are allowed (both
  when run from the main worktree and from a git worktree).
- [ ] **TS2** (AC1, AC9; FR1, FR9): `<in>/`, `<area>//task0001`,
  `//<rest of in>`, `<in>/.`, `<area>/./task0001`, `<in>/..`, and
  `<in>/sub/../sub` are silent.
- [ ] **TS3** (AC1, AC9; FR1, FR9): A link inside the allowed area pointing to
  a directory inside the allowed area, a link pointing outside the allowed
  area, a broken link, a link to a file, and the former
  `FALLBACK_ALLOW_CASES` and relative-link cases are silent.
- [ ] **TS4** (AC1; FR1): `/`, the allowed area itself, a sibling directory
  sharing a name prefix, another repository's allowed area, a nonexistent
  path, a regular file, and each `/proc` and `/dev/fd` form stay silent.
- [ ] **TS5** (AC2, AC9; FR2, FR9): For `'/dev/null' + '/x' * 32000` and
  `'<area>' + '/x' * 32000`, the path check returns False immediately. At or
  above the bound, neither `worktree_area()` nor any filesystem check is
  called (confirmed with mocks).
- [ ] **TS6** (AC2; FR2): The result is False when `os.pathconf` raises
  `OSError` or returns 0 or less. A length exactly equal to the bound is not
  allowed; a length one byte shorter than the bound passes the length check.
- [ ] **TS7** (AC5; FR5): When `.claude/worktrees/em-workflow` of the main
  worktree (or one of its ancestors) is a link pointing outside the main
  worktree, canonical directories beyond it are silent. When it is a link
  pointing inside the main worktree, the resolved canonical path is allowed.
- [ ] **TS8** (AC3; FR3): A path containing NUL and a resolution error yield
  False; the hook exits with code 0 and stderr is empty. A cd-prefix form
  containing a deny pattern stays deny. The existing tests of the exclusion
  rules (operators and safe-side syntax) pass.

### Document and record tests
- [ ] **TS9** (AC4, AC7; FR4, FR7): Document tests confirm that the removed
  symbols do not exist in the module, and that the path items of the
  docstring and the protocol contain the new conditions and none of the old
  ones (logical / physical / /proc / /dev/fd / stage). The existing wording
  checks of the `cd prefix:` paragraph and the check that it contains
  `realpath` pass.
- [ ] **TS10** (AC8; FR8): A document test confirms that the launch procedure
  of implement-phase.md states that `$WT_ROOT/{T}` is canonicalized with
  realpath (strict) into worktree_path, and that tests_yaml_path is derived
  from it.
- [ ] **TS11** (AC10; FR9, FR10): After the deleted IDs are removed from past
  features' `*.tests.yaml`, `python3 -m unittest discover -s tests` passes in
  full.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] Trailing `/`, duplicated `/`, `.`, `..`, and links are not allowed (TS2,
  TS3).
- [ ] A path length exactly equal to the bound is not allowed; one byte
  shorter passes the length check (TS6).
- [ ] An allowed area resolving outside the main worktree allows nothing
  (TS7).

### Performance Tests
- [ ] Long paths return immediately without traversal (TS5, NFR4).

## Security Considerations

- **Input Validation:** Only canonical absolute paths satisfying FR1, within
  the length bound of FR2, below an allowed area satisfying FR5, are allowed.
- **Fail closed:** When the check cannot decide, the path is not allowed
  (NFR5).
- **No child processes:** The path check starts no child process and never
  uses the path as a child process's working directory or argument (NFR2).

## Error Handling

- `OSError` and `ValueError` raised during the path check make the path not
  allowed (FR3).
- Not allowed is not a new deny; the command is judged as if it had no cd
  prefix and falls through to the other rows of the decision table (FR3,
  NFR5).
- For every input the hook exits with code 0 and writes nothing to stderr
  (NFR3).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

None.

## References

- Requirements document: `feature-docs/cd-prefix-canonical-path-only/REQUIREMENTS.md`
