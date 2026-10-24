# Feature: self-write-digest-path-normalization

## Overview

`self-write-digest.py` decides whether a path falls under one of
`allowed_write_roots` with a normalization that differs from the scope
validation in `validate-worker-output.py` (`path_is_contained_in_root`).
This feature makes the two containment checks agree, so that a worker's own
write that scope validation admits is not judged stale. Tests are added that
detect a recurrence of the same divergence.

## Objectives

- Make `self-write-digest.py`'s `allowed_write_roots` containment check agree
  with `validate-worker-output.py`'s scope validation
  (`path_is_contained_in_root`), so that a worker's own write admitted by
  scope validation is not judged stale.
- Add tests that detect a recurrence of the same divergence.

## Acceptance Criteria

- [ ] **AC-1** (covers FR2, FR1): With `allowed_write_roots` containing
  `./feature-docs/example/tasks/` and `feature-docs/example/tasks/task0004.md`
  observed as `created`, `self-write-digest.py`'s `identify_and_substitute`
  returns a `self_write_set` that contains that path, and the digest after
  substitution equals the dispatch-time digest.
- [ ] **AC-2** (covers FR1, FR4): For every row of a (path, root) table that
  includes `.` segments, empty segments, `\` separators, a `.`-only root, a
  `./`-only root, NUL, `..`, absolute paths and an empty-string root,
  `self-write-digest.py`'s containment check returns the same result as
  `validate-worker-output.py`'s `path_is_contained_in_root`.
- [ ] **AC-3** (covers FR3): The containment bullet of Rule R1 in
  `worker-envelope.md` and the docstrings of `self-write-digest.py` state the
  FR1 normalization.
- [ ] **AC-4** (covers NFR1, NFR2): `python3 -m unittest discover -s tests`
  passes. The existing `CONTAINMENT_CASES` rows and `TestIsolation` pass
  unchanged.

## Technical Requirements

### Functional Requirements

- **FR1: Align the `allowed_write_roots` containment normalization with scope validation.**
  The check that decides whether a path absent from `write_policy.targets`
  falls under one of `allowed_write_roots` (`self-write-digest.py`'s
  `_segments` / `_check_allowed_roots` / `_inside_a_root`) returns, for every
  (path, root) pair, the same truth value as `validate-worker-output.py`'s
  `path_is_contained_in_root(path, root)`. Specifically:
  - For both root and path, `\` is treated as a separator equivalent to `/`;
    empty segments and `.` segments are dropped; comparison is then done
    segment by segment.
  - A path is contained only when the normalized root's segments are a strict
    prefix of the path's segments.
  - If either root or path is the empty string, starts with `/`, contains
    NUL, or has a `..` segment (with `\` treated as a separator), the path is
    not contained.
  - A safe root that has no segments left after normalization (`.`, `./`,
    `\`, etc.) contains every safe relative path.
- **FR2: The reproduction case's write enters `self_write_set`.**
  When `allowed_write_roots` is `./feature-docs/example/tasks/` and
  `observed_changes` contains `feature-docs/example/tasks/task0004.md` as
  `created`, `identify_and_substitute`'s `self_write_set` contains that path,
  and the normalized digest of the substituted `digest_source` equals the
  dispatch-time `input_digest`.
- **FR3: Align the documented containment rule with the implementation.**
  Add the FR1 normalization (ignore `.` and empty segments, treat `\` as a
  separator, a root with no segments left contains every relative path) to
  the allowed-write-root containment bullet of Rule R1 in
  `em-workflow/references/contracts/worker-envelope.md` (currently: compare by
  segment; presence or absence of a trailing slash denotes the same
  directory; the root itself is not contained). Bring the `allowed_write_roots`
  description in `self-write-digest.py`'s module docstring ("Roots and paths
  are compared lexically, segment by segment.") and the docstrings of
  `_check_allowed_roots` / `_segments` in line with the same content.
- **FR4: Tests that detect a recurrence.**
  In `tests/test_self_write_digest.py`, add:
  - (a) the FR2 reproduction case;
  - (b) `CONTAINMENT_CASES` rows for a `./`-prefixed root, a path containing
    `.`, a root and a path using `\` separators, a `.`-only root, and a
    `./`-only root;
  - (c) a cross-check test that, over a shared (path, root) table, confirms
    `self-write-digest.py`'s containment check and `validate-worker-output.py`'s
    `path_is_contained_in_root` return the same result.

### Non-Functional Requirements

- **NFR1 - Script isolation:** `self-write-digest.py` uses only the standard
  library and opens no file other than its input document. It does not load
  `validate-worker-output.py` at runtime. (The existing `TestIsolation`
  confirms that `open` is only called with mode `rb` and that no non-standard
  module is imported.)
- **NFR2 - Preserve existing behavior and tests:** `validate-worker-output.py`
  is not changed. The existing cases in `tests/test_self_write_digest.py` and
  `tests/test_validate_worker_output.py` pass as-is (the `CONTAINMENT_CASES`
  rows "an empty root admits nothing", "a slash-only root admits nothing",
  "a root containing a dot-dot segment", etc. yield the same results under
  FR1).
- **NFR3 - Version:** The em-workflow version is not changed
  (`.claude/rules/core-plugin-version-bump.md`).

## Implementation Approach

### Architecture

`self-write-digest.py`'s containment check (`_segments` /
`_check_allowed_roots` / `_inside_a_root`) is brought to the same result as
`validate-worker-output.py`'s `path_is_contained_in_root` /
`path_segments` / `is_safe_relative_path`, which serve as the reference and
are not changed.

Unchanged behavior:

- Matching against `write_policy.targets` paths remains exact string
  equality. `validate-worker-output.py`'s scope validation also matches by
  exact equality (around line 2012).
- The pre-check on `observed_changes` paths (`_is_relative_and_clean`:
  excludes paths starting with `/` and `..` segments split on `/`) is kept.

### Data Flow

```
observed_changes (path, kind)
  → not in write_policy.targets (exact match)
  → contained in an allowed_write_roots entry (FR1 normalization)
  → self_write_set
  → substituted digest_source → R1 normalized digest == dispatch-time input_digest
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/validate-worker-output.py`: `path_is_contained_in_root`
  / `path_segments` / `is_safe_relative_path` are the reference behavior. The
  FR4 (c) cross-check test calls `path_is_contained_in_root`;
  `self-write-digest.py` does not load it at runtime (NFR1).

**External Dependencies:**
- Python standard library only (NFR1).

### File Structure

```
self-write-digest.py                              # FR1, FR3 (docstrings)
em-workflow/references/contracts/worker-envelope.md   # FR3 (Rule R1 containment bullet)
tests/
└── test_self_write_digest.py                     # FR4
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-2** (FR1, FR4): A root containing `.` keeps its boundary.
  Given root `./docs/x`, supply `docs/x/a.md`, `docs/x2/a.md`, `docs/x` and
  `docs/x/../y/a.md` as `created` - only `docs/x/a.md` is contained.
- [ ] **TS-3** (FR1, FR4): `\` separators. Given root `docs\x`, supply
  `docs/x/a.md`; given root `docs/x`, supply `docs\x\a.md` and
  `docs\x\..\y.md`, all as `created` - matching `path_is_contained_in_root`,
  the first two are contained and the one with `..` is not.
- [ ] **TS-4** (FR1, FR4, NFR2): Roots with no segments left. Given roots `.`
  and `./`, supply `a.md` and `docs/x/a.md` as `created` and as `modified`;
  given roots `""` and `/`, supply `a.md` as `created` - for `.` and `./` the
  two `created` paths are contained and the `modified` ones are not; for `""`
  and `/` nothing is contained.
- [ ] **TS-5** (FR1, FR4): Cross-check of the two implementations. For each
  row of the shared (path, root) table, call `self-write-digest.py`'s
  containment check and `validate-worker-output.py`'s
  `path_is_contained_in_root` - the results agree on every row.

### Integration Tests

- [ ] **TS-1** (FR2, FR1, FR4): Reproduction (CLI). Run
  `identify_and_substitute` in a child process with
  `allowed_write_roots=["./feature-docs/example/tasks/"]` and
  `observed_changes=[{path: feature-docs/example/tasks/task0004.md, kind: created}]` -
  `self_write_set` contains `task0004.md`, and the R1 digest of the
  substituted `digest_source` equals the dispatch-time digest.
- [ ] `python3 -m unittest discover -s tests` passes, with the existing
  `CONTAINMENT_CASES` rows and `TestIsolation` unchanged (AC-4).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] The empty-string root contains nothing, as today.
  `is_safe_relative_path("")` is False in `validate-worker-output.py` as well,
  so there is no divergence here; the existing "an empty root admits nothing"
  row fixes this. The empty-root divergence applies to roots with no segments
  left after normalization (`.`, `./`, `\`).
- [ ] A `.`-only root puts every `created` path into `self_write_set`.
- [ ] Paths in `observed_changes` covered by a root yield results consistent
  with FR1 under the retained `_is_relative_and_clean` pre-check, since
  `validate-worker-output.py`'s check is the same or stricter.

### Performance Tests

Not applicable.

## Security Considerations

- **Input Validation:** A root or path that is the empty string, starts with
  `/`, contains NUL, or has a `..` segment (with `\` treated as a separator)
  is never contained (FR1).

## Error Handling

Not applicable.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` passes
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## Assumptions

- `validate-worker-output.py`'s `path_is_contained_in_root` /
  `path_segments` / `is_safe_relative_path` are the reference and are not
  changed.
- The empty-string root contains nothing, as today. `is_safe_relative_path("")`
  is False in `validate-worker-output.py`, so there is no divergence here. The
  task description's "empty root" divergence applies to roots with no
  segments left after normalization (`.`, `./`, `\`). The existing "an empty
  root admits nothing" test row fixes this.
- Matching against `write_policy.targets` paths remains exact string
  equality. `validate-worker-output.py`'s scope validation also matches by
  exact equality (around line 2012).
- The pre-check on `observed_changes` paths (`_is_relative_and_clean`:
  excludes paths starting with `/` and `..` segments split on `/`) is kept.
  `validate-worker-output.py`'s check is the same or stricter, so the result
  for paths covered by a root does not diverge from FR1.
- A `.`-only root now puts every `created` path into `self_write_set`. This is
  accepted as the result of matching scope validation, which admits those
  writes.
- The fix PR targets `em-workflow/worker-self-write-digest/integration`
  (PR #228).

## References

- Worker envelope contract: `em-workflow/references/contracts/worker-envelope.md`
- Scope validation: `em-workflow/scripts/validate-worker-output.py`
- Version rule: `.claude/rules/core-plugin-version-bump.md`
