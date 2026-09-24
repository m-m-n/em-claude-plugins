# Implementation Plan: stop-reason-coverage

## Overview

`em-workflow/references/batch-terminal-line.md` binds every batch-terminating
stop to exactly one reason code by construction: a catch-all code
`unmapped_stop` with a lowest-precedence fallback rule, plus a named row that
maps the refusal-pattern hard fail to `gate_fail_closed`. The `no-step` rule
becomes condition-based and the precedence rule is corrected. Contract test
pins follow, and the plugin version is bumped.

## Technology Stack

- **Contract document**: Markdown. `em-workflow/references/batch-terminal-line.md`
  is the SSOT of the batch structured result.
- **Tests**: Python 3 `unittest`, standard library only, discovered by
  `python3 -m unittest discover -s tests` from the repository root.
- **Invariant check**: `em-workflow/scripts/check-plugin-invariants.py`
  (existing, not edited), run as `python3 em-workflow/scripts/check-plugin-invariants.py .`.
- **New dependencies**: none. `project.license` is `none`; there is no
  dependency license to record.

## Layer Structure

| Layer | Members | Rule |
|---|---|---|
| SSOT | `em-workflow/references/batch-terminal-line.md` | Sole owner of reason-code literals, stop-point keys, field names and the value domains |
| Stop sources | `skills/develop/SKILL.md`, `references/implement-phase.md`, `references/phase-state.md`, `references/question-resolution.md`, `references/batch-policies.yaml`, `references/contracts/designer-contract.md` | Define where a stop happens. Cited by path from the coverage table's Source column. Not edited |
| Pointer documents | `skills/develop/SKILL.md`, `references/batch-mode.md`, `references/implement-phase.md` | Name the SSOT document only and never restate its literals. Not edited by any task (FR11) |
| Contract tests | `tests/test_*.py` | Pin the SSOT and pointer documents through raw-text extraction. Each module is self-contained |
| Registries | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Only the em-workflow `version` fields change |

Dependency direction: tests read the SSOT and the pointer documents; the SSOT
cites stop sources by path; nothing points back into the tests.

## Shared Components

### SC1: New identifiers

| Identifier | Kind | Binding | Source cell | Defined by | Also used by |
|---|---|---|---|---|---|
| `unmapped_stop` | Stop reason code; Applies to `state` `stopped` | Catch-all code | — | task0001 | task0003 (absence-guard literal) |
| `unmapped-terminating-stop` | Coverage key | → `unmapped_stop` | `references/batch-terminal-line.md` | task0001 | — |
| `command-refusal` | Coverage key | → `gate_fail_closed` (existing code) | `references/batch-policies.yaml` | task0001 | — |

Contract:

- Each identifier is spelled exactly as above, and none contains a dot (NFR2).
- `unmapped_stop` never appears in `skills/develop/SKILL.md`,
  `references/batch-mode.md` or `references/implement-phase.md`.
- task0002 names none of the three as a backticked token. They do not exist in
  its worktree, and the `no-step` bullet may name only coverage keys that exist.

### SC2: Edit regions of `batch-terminal-line.md`

| Region | Owner |
|---|---|
| `## Field values`: the `reason` bullet | task0001 |
| `## Field values`: the `step` bullet, from the sentence carrying "`no-step` applies whenever" up to, but excluding, the sentence that starts "When `state` is `completed`" | task0002 |
| `## Stop reason codes` (whole section) | task0001 |
| `## Stop point coverage`: the opening sentences before the table, the table rows, and new paragraphs appended after the `context_budget_reached` paragraph | task0001 |
| `## Stop point coverage`: the "Precedence rule:" paragraph | task0002 |
| Everything else stays byte-identical: `## Purpose`, `## Result format`, `## Escaping`, the rest of `## Field values`, the `context_budget_reached` paragraph, `## Consumer constraints`, `## No result on a wait turn`, `## Responsibility boundary`, and all nine level-2 headings | nobody |

Postcondition: the two tasks' hunks never touch the same lines or adjacent
lines. At least one unchanged line separates any task0001 hunk from any
task0002 hunk.

### SC3: Test pin ownership

| Module | task0001 | task0002 | task0003 | task0004 |
|---|---|---|---|---|
| `tests/test_batch_stop_contract.py` | `REASON_CODES`, `STOP_POINT_KEYS`, `_KEY_CODE_PAIRS_IN_ORDER`, the count tests of `TestStopReasonCodes`, count wording in coverage-test docstrings. Change notes are comments next to these | `NO_STEP_STOP_POINTS`, `_assert_precedence_rule_stated`, the sentinel-condition assertion, the no-step and precedence test classes with their negative proofs, and the module docstring | — | — |
| `tests/test_failed_kind_batch_docs.py` | `EXPECTED_REASON_CODE_STATE_PAIRS` | Pins on the state-based precedence phrase | — | — |
| `tests/test_no_work_required_stop.py` | `EXPECTED_REASON_CODE_STATE_PAIRS`, the exact coverage-row list, the set-size prose pins | Only pins bound to the Precedence rule paragraph's wording, and only if they break | — | — |
| `tests/test_stop_reason_catch_all.py` (new) | All | — | — | — |
| `tests/test_batch_stop_contract_skill_wiring.py` | — | — | `REASON_CODES` tuple (absence-only) and its member-count test | — |
| `tests/test_develop_once_option.py` | — | — | `SC5_REASON_CODES` (absence list) | — |
| `tests/test_stop_reason_coverage_version_bump.py` (new) | — | — | — | All |

### SC4: Cross-region wording contract (`## Stop point coverage`)

- The "Precedence rule:" label stays; task0002 keeps it. task0001 may refer to
  that paragraph by its label.
- task0001 introduces the label "Fallback rule:" at the start of its first
  appended paragraph. task0002 does not reference or edit it.
- After both tasks merge, the section contains none of these phrases:
  - "no phase-specific row covers" and "all three leave". task0002 removes
    them, and task0001 must not introduce them.
  - "Every terminating stop point is bound to exactly one reason code above".
    task0001 removes it, and task0002 must not reintroduce it.
- Matcher scoping:
  - task0001's new matchers read from the "Fallback rule:" label to the end of
    the section, plus the two tables and the reason-code section.
  - task0002's matchers read only the Precedence rule paragraph, from its
    label to the next blank line, plus the coverage table's key set.
  - Neither side depends on the other's region or on the coverage table's row
    count.
- A check that a key is or is not named runs on the relevant paragraph only.
  The table names every key.

### SC5: Resulting cardinalities

| Quantity | Before | After | Changed by |
|---|---|---|---|
| Rows in the stop reason-code table | 12 | 13 | task0001 |
| Documented `reason` values (codes plus `context_budget_reached`) | 13 | 14 | task0001 |
| Coverage rows | 12 | 14 | task0001 |
| Documented codes with no coverage row | 1 (`context_budget_reached`) | 1 (unchanged) | — |
| Backticked keys in the `no-step` bullet (`NO_STEP_STOP_POINTS`) | 3 | 4: `stop-condition-6`, `step-a-abort`, `step-c-abort`, `stop-condition-4` | task0002 |
| `test_batch_stop_contract_skill_wiring.py` absence tuple | 13 | 14 | task0003 |

Count words: the `## Stop reason codes` intro says "thirteen". The
`context_budget_reached` paragraph says "fourteenth". The `reason` bullet says
"fourteen" documented values and "thirteen" stop reason codes.

## Conventions

- **Test authoring (NFR4)**:
  - Every new matcher carries a negative proof, a forged sample the matcher
    rejects, and a non-vacuity guard showing that sample is otherwise well
    formed.
  - Forged samples reproduce the real pre-change wording wherever that wording
    exists.
  - Widening an existing matcher's domain needs no second negative proof.
  - Pure regression guards over retained wording are exempt.
- **Test mechanics**:
  - Tests read raw file text and split sections at level-2 headings.
  - Prose phrases are matched after whitespace normalization. Table and bullet
    extraction stays structural.
  - No test module imports another test module. Only the standard library is
    imported.
- **Anchor phrases**: an anchor phrase that a test matches without
  normalization stays on one physical line.
- **Contract text rules**:
  - Table cells in the contract contain no `|`.
  - The contract stays free of the phrases its existing guard forbids:
    "terminal line", "four-field", "four fields", "key=value", "dual emission",
    "compatibility period", and the removed prefix literal.
- **Identifiers**: new identifiers contain no dot. Backticked dotted spans in
  the contract, such as file names or a gate id, are allowed.
- **Pointer documents**: `skills/develop/SKILL.md`, `references/batch-mode.md`
  and `references/implement-phase.md` are not edited. The sentence
  implement-phase.md pins ("since `references/batch-terminal-line.md` already
  gives `implement-second-failure` precedence over `stop-condition-3`")
  stays true.
- **Version fields**: only task0004 edits them.
- **Contract prose**: English. It states the rules, not their history.

## Cross-task Design Decisions

### D1: A catch-all code instead of one row per untabled stop

- **Decision**: One code (`unmapped_stop`) and one row
  (`unmapped-terminating-stop`) cover every batch-terminating stop no other row
  names. The fallback has the lowest precedence. Untabled stops get no rows of
  their own.
- **Rationale**: Hand-maintained rows did not converge; each review round found
  more stops.
- **Affected**: task0001 defines the code and row. task0003 guards the literal's
  absence from the pointer documents.

### D2: The refusal-pattern hard fail reuses `gate_fail_closed`

- **Decision**: A named row, `command-refusal`, binds the hard fail to the
  existing `gate_fail_closed` code (FR5). No new code is minted.
- **Affected**: task0001 adds the row and the Meaning extension. task0002 names
  this stop only in prose.

### D3: Two contract tasks with disjoint regions

- **Decision**: The contract change is split along SC2:
  - task0001 covers the tables, count words, fallback, scope and catch-all
    `detail` rule.
  - task0002 covers the `step` bullet and the Precedence rule paragraph.
- **Rationale**: Each task's own pins (SC3) stay green in its own worktree,
  and the two diffs do not overlap.
- **Affected**: task0001, task0002.

### D4: The `no-step` bullet names only pre-existing coverage keys

- **Decision**: The rewritten bullet names these backticked keys:
  - `stop-condition-6`, `step-a-abort` and `step-c-abort` as examples;
  - `stop-condition-4` for its explicit case.

  The Step A.5 case, including the refusal-pattern hard fail, is stated in
  prose.
- **Rationale**: Every backticked hyphenated key the bullet names must be a
  coverage key in task0002's own worktree (FR6).
- **Affected**: task0002.

### D5: New catch-all matchers live in a new test module

- **Decision**: `tests/test_stop_reason_catch_all.py` holds TS-1, TS-3–TS-6
  and TS-12. In `tests/test_batch_stop_contract.py`, task0001 only syncs the
  constants and count tests.
- **Rationale**: Keeps task0001's test diff away from the classes task0002
  rewrites in the same module.
- **Affected**: task0001.

### D6: The catch-all `detail` rule lives in `## Stop point coverage`

- **Decision**: FR4's statement is a paragraph appended to the coverage
  section. The `## Field values` `detail` bullet is not edited.
- **Rationale**: Keeps task0001's `## Field values` edit to the `reason`
  bullet (SC2).
- **Affected**: task0001.

### D7: The version bump is isolated, with its own test module

- **Decision**: task0004 bumps em-workflow from 0.2.0 to 0.2.1 in both
  registries. `tests/test_stop_reason_coverage_version_bump.py` asserts a
  version strictly greater than 0.2.0 and equality between the registries.
  It never pins the literal. `tests/test_batch_stop_contract_version_bump.py`
  is not edited.
- **Affected**: task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Merge conflict between task0001 and task0002 in `batch-terminal-line.md`, `test_batch_stop_contract.py` or `test_failed_kind_batch_docs.py` | Medium | Low | SC2 and SC3 disjoint regions; the implementer's parent-side adoption protocol |
| The pin shapes of `test_failed_kind_batch_docs.py`, `test_no_work_required_stop.py` and `test_develop_once_option.py` differ from SPEC's description. These modules were not read at planning | Medium | Medium | Each owning task reads the module before editing. A pin that breaks because of the task's own region is synced in that task. A pin outside the region is reported as a plan deviation |
| A module SPEC does not list also pins the reason-code set or the coverage rows | Low | Medium | Full-suite run in every task. The minimal sync is recorded as a plan deviation |
| The plugin version guard rejects a task commit that changes `em-workflow/` without a version change | Low | Medium | Earlier features used the same single version-bump task. If it happens, the implementer applies the identical 0.2.1 value in both registries (identical edits merge cleanly) and records a deviation |
| The external consumer rejects `unmapped_stop` as out of domain | Medium | Medium | Out of scope (SPEC A8); a follow-up on the consumer side |

## Open Questions

- [ ] None blocking. Consumer-side acceptance of `unmapped_stop` is out of
  scope (SPEC A8).
