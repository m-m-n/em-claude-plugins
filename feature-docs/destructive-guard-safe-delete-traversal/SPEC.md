# Feature: destructive-guard-safe-delete-traversal

## Overview

`destructive-guard.py`'s `SAFE_DELETE` exception is applied by regex prefix match against the un-normalized target string. Paths that merely carry a safe directory name as a prefix, and paths containing a parent reference `..`, therefore pass as safe and the delete guard returns allow. This feature replaces that check with component-wise containment on the normalized path, and realigns `destructive-guard-cases.json` with the corrected behaviour.

Requirement details, assumptions and confirmed facts: `feature-docs/destructive-guard-safe-delete-traversal/REQUIREMENTS.md`.

## Objectives

- Replace the `SAFE_DELETE` exception's un-normalized prefix match with component-wise containment on the normalized path, closing the hole where a path that merely prefixes a safe directory name, or that contains a parent reference, is allowed.
- Move the case-table entries currently pinned to allow as known holes to the deny side, so the case table stays a description of actual behaviour.
- Do not increase false positives. Existing allow cases (deletions under scratch roots, mentions inside quotes, heredoc bodies) must not regress.

## User Stories

### US1: Traversal targets are not treated as safe
As an em-workflow user, I want a recursive delete whose target escapes the safe roots via `..` to be denied, so that the pre-execution hook remains the layer that stops it.

**Acceptance Criteria:**
- [ ] A recursive delete of `/tmp/../home/sakura/valuable` results in deny or ask (currently allow).
- [ ] A recursive delete of `build/../src` results in deny or ask (currently allow, case table line 139).
- [ ] A recursive delete of `targets` results in deny or ask (currently allow, case table line 138).
- [ ] The control case, a recursive delete of `/home/sakura/valuable`, stays deny.

### US2: The case table describes actual behaviour
As a maintainer of the guard, I want the case table to state the corrected decisions, so that no entry is pinned to a known hole.

**Acceptance Criteria:**
- [ ] The 14 entries whose label contains SAFE_DELETE are flipped to deny expectations and no longer carry the "既知の穴(未修正)" wording.
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes on every case.
- [ ] The versions in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are raised to the same value.

### US3: No new false positives
As an unattended batch run, I want the existing allow decisions preserved, so that the run is not stopped in place by a demoted ask.

**Acceptance Criteria:**
- [ ] Recursive deletes with no trailing slash on `/tmp` / `tmp` / `.cache` / `/var/tmp` stay deny (case table lines 134-137).
- [ ] A recursive delete of `node_modules` with its output discarded stays allow (case table line 8).
- [ ] A recursive delete of `/tmp/x` stays allow both with and without redirection (case table lines 7, 9).
- [ ] A recursive delete of `dist/*` stays allow (case table line 132).
- [ ] The two existing cases whose only targets are command substitutions stay allow (the zero-target early-return path, case table lines 96, 129).

## Technical Requirements

### Functional Requirements

- **FR1 — Normalize the target before the safe exception:** `check_rm()` normalizes the delete target lexically before applying the `SAFE_DELETE` exception. Expansion covers `~` / `$HOME` / `${HOME}`; folding covers `.` / `..` / repeated slashes / a leading `//`. Limited to the same filesystem-free transformation as the existing `normalize_candidate()` (`destructive-guard.py:1093`).
- **FR2 — A surviving parent reference is never safe:** a relative target that still begins with `..` after normalization does not reach the safe exception and falls through to the existing rm-recursive deny.
- **FR3 — Judge containment on component boundaries:** comparison against a safe root moves from regex prefix match to component-wise containment. `targets` must not match `target`, `build-debug` must not match `build`, `node_modules_bak` must not match `node_modules`. A match requires either an exact component match or a following separator.
- **FR4 — Absolute scratch roots are safe only for proper descendants:** `/tmp` and `/var/tmp` are safe only below themselves. The roots themselves stay deny. Because normalization drops the trailing slash, a recursive delete targeting `/tmp/` is the same deny as `/tmp`.
- **FR5 — Keep the two classes of relative safe names:** for relative targets only, judge on the leading component. Build-artifact names (`node_modules` / `dist` / `build` / `target` / `.next` / `coverage`) are safe on exact match and below, preserving the allow for `node_modules` alone. Scratch names (`tmp` / `.cache`) are safe only below themselves; the bare names stay deny. Absolute paths never become safe through this class (`/build` stays deny).
- **FR6 — Unresolved expansions are judged before the safe exception:** a target containing variable expansion or command substitution does not reach the safe exception even when it appears to sit under a safe root, and falls through to the existing ask(rm-unresolvable). Today the `SAFE_DELETE` match takes effect before the DYNAMIC check, so an unresolved expansion under a safe root is allowed.
- **FR7 — Pure globs under a safe root stay allow:** a glob deletion under a safe root, such as `dist/*`, stays allow (case table line 132). Dot-leading glob components that could match `..` (e.g. `/tmp/.*`) do not reach the safe exception.
- **FR8 — Realign the case table with actual behaviour:** in `destructive-guard-cases.json`, flip the expectation of the 14 entries whose label contains SAFE_DELETE (lines 98-109, 138, 139) from allow to deny, drop the "既知の穴(未修正)" wording from their labels and rewrite them with the corrected reason. Add a new deny case for a recursive delete targeting `/tmp/../home/sakura/valuable`. Delete no existing deny or ask case.
- **FR9 — Raise the plugin version:** because files under `em-workflow` change, raise the version in `em-workflow/.claude-plugin/plugin.json` and in the repository-root `.claude-plugin/marketplace.json` from 0.1.72 to the same new value (patch increment).
- **FR10 — The suite passes in full:** `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes on every case.

### Non-Functional Requirements

- **NFR1 — Determinism:** the decision never touches the filesystem. No `os.path.realpath`, `stat` or `subprocess`; the same command always yields the same decision (the determinism stated in `destructive-guard.py`'s module docstring and the constraint in `normalize_candidate()`'s docstring).
- **NFR2 — False-positive cost:** a false positive costs the same order as a miss (`.claude/rules/hook-tests.md`). ask is demoted to deny under claude-batch, so a regression on an allow case stops an unattended run in place.
- **NFR3 — Synchronous execution:** the PreToolUse hook runs synchronously on every Bash execution, so normalization stays confined to string processing.
- **NFR4 — Residual symlink escape:** escape via symlink cannot be excluded by lexical normalization. Case table line 9 pins the allow for a recursive delete of `/tmp/x`, and introducing real-path resolution would break both determinism and that allow, so the residual constraint is stated explicitly in the code.
- **NFR5 — Constant comment:** because the meaning of `SAFE_DELETE` changes, the constant's comment (`destructive-guard.py:151`) is updated to describe the new decision rule.

## Implementation Approach

### Architecture

**Decision order inside `check_rm()`:**

```
recursive delete detected
  → target extraction (zero targets → early return, unchanged)
  → unresolved expansion / command substitution?      [FR6] → ask(rm-unresolvable)
  → lexical normalization of the target               [FR1]
  → leading ".." survives?                            [FR2] → deny(rm-recursive)
  → component-wise containment against safe roots     [FR3]
      ├ absolute scratch roots: proper descendants    [FR4]
      ├ relative build-artifact names: self + below   [FR5]
      ├ relative scratch names: below only            [FR5]
      └ pure glob under a safe root, non dot-leading  [FR7]
  → safe → allow ; otherwise → deny(rm-recursive)
```

**Components:**

- `SAFE_DELETE` (`destructive-guard.py:151-152`) — the constant whose meaning and comment change (NFR5).
- `check_rm()` — applies the new decision order above.
- `normalize_candidate()` (`destructive-guard.py:1093`) — the existing filesystem-free transformation FR1 reuses.

### Data Flow

```
Bash command → PreToolUse hook → check_rm() → allow | ask(rm-unresolvable) | deny(rm-recursive)
```

### Dependencies

**Internal Dependencies:**

- `em-workflow/hooks/destructive-guard.py`: the decision logic being changed.
- `em-workflow/hooks/tests/destructive-guard-cases.json`: the case table realigned by FR8.
- `em-workflow/hooks/tests/run-destructive-guard.py`: the runner that must pass in full (FR10).
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: version bump (FR9).

**External Dependencies:**

- None. The decision uses string processing only (NFR1, NFR3).

### File Structure

```
em-workflow/
├── hooks/
│   ├── destructive-guard.py
│   └── tests/
│       ├── destructive-guard-cases.json
│       └── run-destructive-guard.py
└── .claude-plugin/
    └── plugin.json
.claude-plugin/
└── marketplace.json
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

- [ ] TS1: Path traversal — a recursive delete of `/tmp/../home/sakura/valuable` is deny, with the same rm-recursive reason as the control `/home/sakura/valuable`. (FR1, FR2, FR4, FR8)
- [ ] TS2: Relative path traversal — `build/../src` normalizes to `src` and is deny. (FR1, FR2, FR8)
- [ ] TS3: Component boundary — `targets` / `build-debug` / `dist-ssr` / `target-old` / `coverage.old` / `build-artifacts` / `dist-newstyle` / `coverage-old` / `node_modules_bak` are all deny. (FR3, FR8)
- [ ] TS4: Scratch root itself — `/tmp/` / `tmp/` / `.cache/` / `/var/tmp/` reach the same deny as their trailing-slash-free counterparts (asymmetry removed). (FR1, FR4, FR5, FR8)
- [ ] TS7: Unresolved expansion — a form with a variable placed under a safe root does not reach the safe exception and becomes ask. (FR6)

### Integration Tests

- [ ] TS8: The batch-demotion case (the extra assertion inside `run-destructive-guard.py`) still returns deny. (FR10)

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS5: Regression guard (allow side) — exact `node_modules`, targets under `/tmp/x`, `./build`, and `dist/*` stay allow. (FR1, FR4, FR5, FR7)
- [ ] TS6: Regression guard (deny/ask side) — the existing rm-root / rm-unresolvable / dynamic targets mixed with parent references (lines 110-112) do not change their decisions. (FR2, FR6)

## Security Considerations

- **Input Validation:** delete targets are normalized lexically before the safe exception is applied (FR1); a surviving leading `..` (FR2), an unresolved expansion (FR6) and a dot-leading glob component (FR7) never reach the safe exception.
- **Data Protection:** safe roots match on component boundaries only (FR3), absolute scratch roots only for proper descendants (FR4), and relative safe names only on the leading component in two classes (FR5).
- **Residual risk:** escape via symlink is not excluded; the decision stays lexical and the residual constraint is stated in the code (NFR4).

## Error Handling

| Decision | When | Requirement |
|---|---|---|
| `allow` | Target resolves, after normalization, to a proper descendant of a safe root, or to a safe relative build-artifact name, or to a non dot-leading glob under a safe root | FR4, FR5, FR7 |
| `ask` (rm-unresolvable) | Target contains variable expansion or command substitution | FR6 |
| `deny` (rm-recursive) | Everything else, including a surviving leading `..`, a component-boundary mismatch, and a scratch root itself | FR2, FR3, FR4, FR5 |

## Success Criteria

- [ ] All functional requirements FR1-FR10 are implemented.
- [ ] All test scenarios TS1-TS8 pass.
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes on every case.
- [ ] The 14 SAFE_DELETE-labelled case-table entries carry deny expectations and no "既知の穴(未修正)" wording.
- [ ] No existing deny or ask case has been deleted.
- [ ] `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same raised version.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement is `status: resolved`.

## References

- Requirements document: `feature-docs/destructive-guard-safe-delete-traversal/REQUIREMENTS.md`
- Guard implementation: `em-workflow/hooks/destructive-guard.py` (`SAFE_DELETE` at 151-152, `normalize_candidate()` at 1093)
- Case table: `em-workflow/hooks/tests/destructive-guard-cases.json`
- Test runner: `em-workflow/hooks/tests/run-destructive-guard.py`
- Hook testing rules: `.claude/rules/hook-tests.md`
- Version bump rules: `.claude/rules/core-plugin-version-bump.md`
