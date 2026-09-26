# Implementation Plan: batch-once-refire-dedup

## Overview

State the `--batch --once` re-launch contract (continue a run that ended at a
`--once` phase boundary by passing the structured result's `feature` value as
the path argument, without passing the task description again) in
em-workflow's batch reference documents, pin that wording and the existing
Step A rules with regression tests, and bump the em-workflow plugin version.
develop's feature resolution rules and behavior are not changed.

## Technology Stack

- **Documents**: Markdown reference documents under `em-workflow/references/`
  (the plugin's behavior specification).
- **Tests**: Python 3 standard library `unittest` only, discovered by
  `python3 -m unittest discover -s tests`.
- **Manifests**: JSON plugin / marketplace manifests (version fields only).
- **New dependencies**: none (no license to record; `project.license` is
  `none`).

## Layer Structure

Document ownership for this feature (dependency direction is "cites", never
"restates"):

| Layer | Owner of | Rule for this feature |
|-------|----------|-----------------------|
| `em-workflow/references/batch-terminal-line.md` | The structured result format (key set, order, escaping, value domains, including `state` and `feature`) | Sole format owner. Its `state` bullet gains the re-launch wording; no format element changes |
| `em-workflow/references/batch-mode.md` | Batch gate behavior (Non-packet gates table) | States only HOW the `feature` value is used on re-launch, citing `batch-terminal-line.md` as the value's owner; never redefines the format |
| `em-workflow/skills/develop/SKILL.md` | Step A feature resolution rules | Unchanged (read-only for this feature) |
| `tests/` | Regression pins | Pins the new wording and the existing Step A rules; existing test modules are not modified |

## Shared Components

This feature is a single task; no component crosses a task boundary. The
wording contract below is still recorded here because it binds both edited
documents and the tests, and any later rework task touching these files must
keep it.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Re-launch contract wording anchors | The minimal phrases that carry the re-launch contract and that tests match on | Post: after whitespace normalization (every whitespace run collapsed to one space), each scoped passage (the batch-mode.md Step A feature resolution row; the batch-terminal-line.md `state` bullet) contains anchor **A1** = the phrase "`feature` value as the path argument" and anchor **A2** = the phrase "does not pass the task description again". Surrounding sentence wording is free as long as both anchors appear inside the scoped passage | task0001 |
| Existing Step A rule phrases (batch-mode.md row) | Phrases that must survive the edit verbatim | Post: the Step A feature resolution row still contains "Explicit feature-name/path argument wins", "No path argument → always a new feature", "Existing branches are never enumerated, and a feature is never guessed from them" and "resuming requires the explicit feature name" | task0001 |

## Conventions

- **Pointer-document literal constraint (batch-mode.md)**: the existing guard
  `TestBatchModePointerSc5Compliance` in `tests/test_batch_stop_contract.py`
  scans the whole of `batch-mode.md`. Any text added there must not contain:
  the bare phase-boundary `state` value literal (the word that
  `batch-terminal-line.md` defines for a `--once` boundary), any of the eight
  result keys written as a backticked key immediately followed by a colon or
  as `key=`, any stop reason code, the `no-step` sentinel, or `state:` /
  `step:` / `reason:` value shapes. Refer to the boundary in words ("a
  `--once` phase boundary") and to the value as "the structured result's
  `feature` value".
- **Table-cell constraint (batch-mode.md)**: the Step A row stays one physical
  line with its two cells; added text contains no `|` character.
- **Bullet-shape constraint (batch-terminal-line.md)**: `## Field values`
  keeps its eight top-level bullets in the same order (existing tests extract
  them by lines that open with a dash followed by a backticked key);
  continuation lines stay indented, and no added line opens a new top-level
  bullet. The existing substrings "`state` as `phase_done`" and "re-launches
  the same feature" in the `state` bullet stay intact (pinned by
  `tests/test_batch_stop_contract.py`).
- **Matcher conventions for new tests**: every check extracts its scope
  structurally first (level-2 section, then table row by first-cell prefix, or
  top-level bullet by leading backticked key), then does whitespace-normalized
  substring matching inside that scope only. A failed extraction is a test
  failure, never a silent pass. Every matcher is a pure function over text so
  it can be fed forged text, and each has a negative proof.
- **Standard library only**: new test modules import only standard library
  modules and carry a self-check of that fact (same shape as the existing
  self-check in `tests/test_develop_once_option.py`).
- **Existing tests are not modified**: they are the regression guard for the
  unchanged rules.
- **Version bump**: any change under `em-workflow/` raises
  `em-workflow/.claude-plugin/plugin.json` `version` and the em-workflow entry
  of `.claude-plugin/marketplace.json` to the same value by one patch step,
  in the same commit as the `em-workflow/` change (a global commit hook
  rejects plugin changes without the bump). Other plugins' versions are not
  touched.

## Cross-task Design Decisions

### D1: Documentation-only countermeasure (approach (a))

- **Decision**: the duplicate-feature countermeasure is the external
  dispatcher carrying the feature name; em-workflow only states the re-launch
  contract and pins it with tests. develop's feature resolution (no path
  argument means a new feature; no enumeration or guessing of existing
  branches) is not changed.
- **Rationale**: SPEC A1 / FR2.
- **Affected tasks**: task0001.

### D2: Format ownership stays with batch-terminal-line.md

- **Decision**: batch-terminal-line.md's `state` bullet states the consumer
  side of the contract; batch-mode.md's Step A row states the develop-side
  usage and cites `references/batch-terminal-line.md` for the value. Neither
  document changes the result's key set, order, escaping or value domains.
- **Rationale**: SPEC NFR4.
- **Affected tasks**: task0001.

### D3: Single task

- **Decision**: document edits, their regression tests and the version bump
  are one task.
- **Rationale**: the new tests only pass once the wording exists (splitting
  would leave a test-only task that cannot go green in its own worktree), and
  the version bump must share a commit with the `em-workflow/` edits.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Added batch-mode.md text trips the whole-file pointer-literal guard (e.g. writing the boundary `state` value or a backticked key followed by a colon) | Medium | Suite fails | Pointer-document literal constraint above; run the full suite before completion |
| Another existing test (outside the modules read at planning time) pins the exact batch-mode.md Step A row or the `state` bullet text | Low | Suite fails | Keep every existing phrase verbatim and only append; run the full suite |
| Re-wrapping the `state` bullet splits a pinned phrase across a line break | Low | Existing test fails if it does not normalize | Existing pins match after whitespace normalization; still avoid rewording existing sentences |
| New matchers pass vacuously (scope extraction returns nothing) | Medium | Regression goes undetected | Extraction failure is a failure; negative proofs per matcher and per scope |

## Open Questions

- None.
