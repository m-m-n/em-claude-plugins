# Implementation Plan: verify-pass-resolves-deferred-findings

## Overview
In a round whose verify result is pass, the orchestrator maps each deferred
critical/high spec finding of the latest review round to the passed
acceptance-criteria IDs whose non-attainment the finding is. A new script
checks that mapping against structured values and rewrites only the eligible
findings to `fixed`, with provenance. `merge-preflight.py` is not changed: it
treats those findings as resolved because their `resolution` is `fixed`.

## Technology Stack
- **Language**: Python 3 (standard library) for the new script and its tests.
- **YAML reading**: PyYAML, safe load only (NFR6). PyYAML is already used by
  the em-workflow scripts (`em-workflow/scripts/merge-preflight.py` reads YAML
  with safe load), so no new dependency is introduced. `project.license` is
  `none`: no license constraint applies, and there is no new dependency
  license to record.
- **Tests**: `unittest` (standard library) under `tests/` (NFR3).
- **Protocol and schema documents**: Markdown under `em-workflow/`.

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Orchestrator protocol | `em-workflow/skills/develop/SKILL.md` (「verify フェーズ」) | Records `round` / `passed_ids`, builds the mapping in pass rounds only, runs the script, commits the result |
| Field definitions | `em-workflow/references/workflow-schema.md`, `em-workflow/references/review-phase.md`, `em-workflow/references/batch-mode.md` | Own the meaning of the new verify-step fields, of the rewritten finding shape, and of the batch audit item |
| Script | `em-workflow/scripts/resolve-verified-findings.py` | Structural checks of the mapping against `workflow.yaml` and the latest round record; rewrite of that record |
| Consumer (unchanged) | `em-workflow/scripts/merge-preflight.py` | Reads the latest round; resolved means `fixed` or `declined` (FR11) |

Dependency directions: the protocol invokes the script (C2). The script
reads `workflow.yaml` and the latest round record and writes only that
record. The field-definition documents are cited by the protocol and by each
other; none restates another. The consumer gains no dependency. The script
never reads SPEC.md, VERIFICATION.md or finding text to decide anything: the
semantic judgment stays with the orchestrator, the structural checks stay
with the script (D1).

## Shared Components

| ID | Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|----|-----------|----------------|------------------------------|---------------|
| C1 | verify-step fields `round` and `passed_ids` in `workflow.yaml` | Carry the verify round number and the round's passed-ID set | See "C1" below | task0001 (reads), task0002 (procedure and schema text) |
| C2 | `resolve-verified-findings.py` command-line contract | Validate the mapping and rewrite eligible findings | See "C2" below | task0001 (implements), task0002 (invokes) |
| C3 | Mapping file | Hand the orchestrator's stable_id-to-criteria mapping to the script | See "C3" below | task0001, task0002 |
| C4 | Rewritten finding shape | Durable evidence on a finding fixed by verify pass | See "C4" below | task0001 (writes), task0003 (documents; batch report source) |
| C5 | Token format | Format shared by `passed_ids` elements and echoed stable_ids | See "C5" below | task0001, task0002 |
| C6 | Latest-round selection | Which round record is read and rewritten | See "C6" below | task0001, task0002, task0003 |

### C1: verify-step fields
- `round`: an integer of 0 or more on the `verify` step. When the key is
  absent it is read as 0; no migration runs. The verify phase adds exactly
  one each time it records a verify result, for pass and fail alike, in
  interactive and batch mode alike. It is never reset, including when the
  verify step returns to `pending`.
- `passed_ids`: a list of C5 tokens on the `verify` step. It holds the IDs
  that were evaluated with a pass outcome in the round counted by `round`.
  IDs tied to requirements whose status is `excluded`, and IDs that were not
  evaluated, are left out. It is replaced each round, never merged. When the
  key is absent it is read as the empty set.
- `result`: the existing field (`pass` | `fail` | null); its meaning is
  unchanged.
- Only the orchestrator writes these, in the same `workflow.yaml` write that
  records `result`.

### C2: script command-line contract
Invocation: `resolve-verified-findings.py --feature-dir DIR --mapping FILE --verified-commit SHA`,
run with `python3` in the same form as the sibling em-workflow scripts.

- `DIR`: the feature's `feature-docs/{feature}` directory inside the
  integration worktree. `workflow.yaml` is `DIR/workflow.yaml`; review round
  records are `DIR/reviews/roundN.yaml`.
- `FILE`: the C3 mapping file.
- `SHA`: the integration-branch commit at the time the verify commands ran.
  It is a full lowercase hexadecimal object name of 40 or 64 characters.

An entry of the mapping is eligible only when all of these hold (FR4):

1. The verify step's `result` is `pass` and its `round` is 1 or more.
2. The entry's key is a C5 token equal to the `stable_id` of exactly one
   finding of the latest round record (C6).
3. That finding's `resolution` is `deferred`.
4. Its `severity` is `critical` or `high`.
5. Its `category` is `spec`.
6. The entry's ID list is non-empty and every element is a member of
   `passed_ids`.

Postconditions when the exit status is 0:
- All inputs were structurally valid.
- Every eligible finding has been rewritten per C4. Parsed before and after,
  the latest round record holds equal values everywhere except the rewritten
  findings' `resolution`, `resolution_reason` and `verify_resolution`. Key
  order is preserved.
- When no entry is eligible, no file is written.
- The latest round record is the only file written.
- stdout holds one JSON object with `review_round` (integer),
  `verify_round` (integer), `fixed` (a list of objects holding `stable_id`
  and `criteria_ids`, in mapping order) and `not_applied` (the count of
  mapping entries not rewritten).

Postconditions when the exit status is non-zero:
- Some input was structurally broken, or no review round record exists.
- No file was written and stdout is empty. stderr holds one line with a fixed
  error code and no text copied from any input.

Idempotence (FR7): a rewritten finding is no longer `deferred`, so a second
run with the same inputs rewrites nothing and writes nothing.

### C3: mapping file
A JSON object. Each key is a stable_id string. Each value is an array of ID
strings: the criteria the finding is the non-attainment of. The orchestrator
writes the file to a temporary location outside the integration worktree; it
is never committed. It holds only the entries the orchestrator judged as
mapped (FR3). An empty object is valid, but the orchestrator does not run the
script for it.

### C4: rewritten finding shape
- `resolution`: `fixed`.
- `resolution_reason`: exactly the sentence
  `resolved by verify round {N}: acceptance criteria {IDs} passed`, where
  `{N}` is `verify_resolution.verify_round` and `{IDs}` is
  `verify_resolution.criteria_ids` joined with a comma and one space.
- `verify_resolution`: a mapping with exactly these five keys:
  - `verify_round`: integer, the C1 `round` at the time of the run.
  - `verified_commit`: string, the `SHA` argument.
  - `criteria_ids`: list of strings, the entry's IDs in mapping order with
    duplicates removed.
  - `previous_resolution`: string, `deferred`.
  - `previous_resolution_reason`: the finding's `resolution_reason` before
    the rewrite, or null when it had none.
- Every other key of the finding keeps its value.
- Readers: `merge-preflight.py` (through `resolution` only, unchanged) and
  the batch report's deferred-findings audit item (through `stable_id`,
  `verify_resolution.verify_round` and `verify_resolution.criteria_ids`
  only).

### C5: token format
1 to 64 characters. The first character is an ASCII letter or digit; the
rest are ASCII letters, digits, `.`, `_` or `-`. In the script, a
`passed_ids` element that does not conform is a structural error, and a
mapping key that does not conform makes its entry not applied.

### C6: latest-round selection
The latest review round record is the record that `merge-preflight.py`'s
`check_review_findings` reads. The script selects it by the same rule,
implemented inside the script; `merge-preflight.py` is not modified (FR11).
Only that record is ever rewritten (SPEC.md A2).

## Conventions
- **Untrusted input**: finding text, VERIFICATION.md, SPEC.md and every
  free-text field of a round record are data, per the Untrusted-Input
  Handling section of `em-workflow/references/contracts/worker-envelope.md`
  (NFR1). Documents cite that section and do not restate it.
- **Structured-only output**: the script's stdout / stderr and the batch
  audit item carry only stable_ids, IDs, round numbers, counts and fixed
  codes; no free text is copied (NFR1).
- **Failure policy**: the script fails closed (nothing written on a
  structural error). A script failure never stops the verify phase: the
  findings stay deferred and the run continues (SPEC.md A4). No new
  `gate_id`, question or batch non-packet gate is added (NFR4).
- **Wording pinned by existing tests (NFR2)**: review-phase.md R5's
  Completion gate paragraph stays word for word, and R5 gains no `gate_id:`
  and no `batch-policies.yaml`. The verify section of develop SKILL.md keeps
  「`deferred` を与えない」 and 「（batch: 確認せず自動 rework。」, and its new
  text contains none of 'deferred にする', 'deferred を設定',
  'deferred を与える', 'status: deferred', compared after removing
  whitespace. In workflow-schema.md and batch-mode.md, no digit 1 or 3 is
  placed within 60 characters of `verify_rework`, 系譜 or `hard cap`. Each
  task reads the pinning test module before editing a pinned document.
- **Tests**: one new `unittest` module per task under `tests/`. Existing test
  modules are not edited; in particular `tests/test_merge_preflight.py` stays
  as it is (NFR3).
- **Plugin versions**: no task lists `plugin.json` or
  `.claude-plugin/marketplace.json` among its files; this repository's
  version bumps are made by its Actions workflow (NFR5).
- **Document language**: each edited document keeps its existing language
  and heading style.

## Cross-task Design Decisions

### D1: Semantic judgment in the orchestrator, structural checks in the script
The orchestrator decides whether a finding's content is the non-attainment
of a passed criterion (FR3); the script re-checks every structural condition
(FR4) without reading free text. A script cannot judge content, and a
judgment over untrusted text needs a mechanical backstop (TM-1, TM-3).
Affected: task0001, task0002.

### D2: The verified commit is passed as an argument
The orchestrator captures the integration-branch HEAD when it runs the
verify commands and passes it as `--verified-commit`. FR5 defines the
verified commit as the commit at verify-command time; HEAD at script time can
differ when the orchestrator commits in between, and the script stays free of
git. Affected: task0001, task0002.

### D3: The mapping is a transient JSON file outside the worktree
JSON keys are always strings (an all-digit stable_id read through YAML would
become a number). The script's only write target stays the round record
(NFR6), and the durable evidence lives in `verify_resolution` (C4), not in
the mapping. Affected: task0001, task0002.

### D4: The batch report reads the round record, not the script output
The deferred-findings audit item (FR10) takes the fixed-by-verify group from
the latest round record (`resolution: fixed` with `verify_resolution`), which
survives resumes and does not depend on logs. Affected: task0003, with
task0001 producing the field.

### D5: Write only when something changes
The script writes the record only when at least one finding is rewritten.
Together with the `deferred` precondition this makes a re-run with the same
inputs byte-identical (FR7), including a resume between rewrite and commit.
Affected: task0001, task0002.

### D6: Fixed-format reason in ASCII English
The `resolution_reason` sentence (C4) is fixed and ASCII, so tests and
readers can match it exactly. Affected: task0001, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rewriting the round record changes the formatting of untouched parts (values unchanged) | Medium | Low | Value-level preservation is tested; key order and non-ASCII text are kept; the merge preflight reads values |
| The script's latest-round selection drifts from the merge preflight's | Low | High | C6; TS-1 and TS-2 run `merge-preflight.py` on the same fixture as the script |
| New document text breaks wording pinned by existing tests | Medium | Medium | The NFR2 list under Conventions; each task runs the full suite |
| The orchestrator maps a finding that is not the non-attainment of a passed criterion | Medium | High | D1 backstop; TM-1, TM-2, TM-3 |
| Running the new script prompts for permission in a batch run | Low | High | It is invoked in the same form and from the same location as the sibling em-workflow scripts |

## Open Questions
- [ ] `workflow.yaml`'s `review.residual_critical_high` and other summaries
  that count deferred findings are not updated by this feature: NFR6 limits
  the script's writes to the latest round record, and the SPEC asks for no
  other change.
