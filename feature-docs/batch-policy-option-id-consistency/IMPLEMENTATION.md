# Implementation Plan: batch-policy-option-id-consistency

## Overview

Every `action: select` entry in `em-workflow/references/batch-policies.yaml`
gains an issuing site that declares and offers the option_id the policy names,
expressed in one canonical, machine-readable declaration block, and the
correspondence is pinned by the repository-root unittest suite.

## Technology Stack

- **Language**: Python 3 (standard library only) — the repository's existing
  `tests/` suite, run by `python3 -m unittest discover -s tests`.
- **Documents**: Markdown reference / contract / phase-protocol documents and
  agent prompts under `em-workflow/`, plus two JSON plugin manifests.
- **New dependencies**: none. No package is added, so no license check applies
  (`project.license: none`; nothing in this change introduces an SPDX
  obligation). Test code imports no third-party package (NFR2): the
  restricted-subset YAML parsing of `batch-policies.yaml` is reused or
  reimplemented from `tests/test_batch_policies.py`.

## Layer Structure

Three layers, with a one-way dependency direction (NFR5 — the arrow never
reverses):

1. **Policy layer** — `em-workflow/references/batch-policies.yaml`. The
   authoritative side. Its `gate_policies` entries, including every
   `option_id`, are read-only for this feature; no entry is renamed, added or
   removed. It remains the single policy table (NFR4).
2. **Issuing-site layer** — the worker contracts, agent prompts and phase
   protocol documents that define what option vocabulary each gate offers.
   This layer is what moves: each site declares the option_id its gate's
   policy names.
3. **Verification layer** — `tests/`. Reads layers 1 and 2 and fails when the
   correspondence between them breaks. It never writes to either.

A separate **documentation layer** (`em-workflow/references/`) records the
correspondence rule itself, the canonical declaration format, and the
exemption registry for any gate that cannot be checked mechanically. It holds
no policy decisions and no gate's option vocabulary of its own.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Gate option vocabulary block | The canonical, machine-readable way an issuing document declares which option_ids a gate offers | Precondition: the document is one of the issuing sites. Postcondition: the block is a level-2 section headed exactly `## Gate option vocabulary`, containing one Markdown table whose header row names, in order, a gate-id column, an option-id column and a meaning column; each data row carries exactly one backtick-quoted gate_id in the first cell, exactly one backtick-quoted option_id in the second, and a non-empty prose meaning in the third; one row per offered option. The set of option_ids a document offers for a gate is exactly the second-cell values of the rows whose first cell names that gate — nothing outside the block counts (D1, D3) | task0001 (writes and parses), task0002 (documents the format) |
| Issuing-site map | The pinned association gate_id → the document paths that must declare that gate's vocabulary | Precondition: none. Postcondition: the map lives in exactly one place — the new correspondence-check module under `tests/` — keyed by gate_id, valued by one or more repository-relative document paths; its key set equals the set of `action: select` + `option_id` gate_ids in `batch-policies.yaml`. No other document restates the map (D2) | task0001 (owns it), task0002 (must cite it, never restate it) |
| Exemption registry | The documented list of select gates whose correspondence cannot be checked mechanically, with the reason and the compensating guarantee for each | Precondition: none. Postcondition: it is a single Markdown table in `em-workflow/references/gate-option-vocabulary.md` with a gate-id column, a reason column and a compensating-guarantee column, one row per exempted gate; it is the ONLY source of exemptions (the checker holds no hardcoded exemption list); a missing or unreadable registry file is treated as zero exemptions, never as a check-skipping condition; at the end of this feature the registry holds zero rows (D3) | task0002 (writes it), task0001 (consumes it) |
| Frozen machine-read surface | The two frozen files, and the contract-document heading the frozen validator parses | Precondition: a task edits a document under `em-workflow/references/contracts/`. Postcondition: `em-workflow/references/workflow-patch.md` and `em-workflow/scripts/validate-worker-output.py` are byte-unchanged (NFR1); no contract document that lacks a `## Gate identifiers` section gains one; the existing `## Gate identifiers` section in the analyst contract keeps exactly its current two gate-id tokens and gains no further backtick-quoted token of the `name.suffix` shape; `tests/test_validate_worker_output.py` and the `valid-design-step-correct-binding` fixture are byte-unchanged (D4) | all tasks |
| Plugin version bump | The single owner of the two version fields | Precondition: none. Postcondition: `em-workflow/.claude-plugin/plugin.json`'s `version` is greater than 0.1.41 and the em-workflow entry in `.claude-plugin/marketplace.json` carries the identical string; no other task edits either file (D6) | task0003 only |

## Conventions

- **Naming**: an option_id is lower snake_case and never contains a dot; a
  gate_id keeps its existing `namespace.name` form. Both are always written
  backtick-quoted in the declaration blocks.
- **Section placement**: a new `## Gate option vocabulary` section is appended
  at the end of its document, or immediately before the document's final
  section — never inserted between an existing heading and a heading that an
  existing test uses as a section end marker. When an existing test's section
  extraction breaks, the fix is to move the new section, not to edit that
  test's expectations.
- **Wording**: no document touched by this change may contain the phrase
  "decision table" or "決定表" (an existing suite check forbids it in the
  policy file, `batch-mode.md`, `question-resolution.md` and the develop
  skill; this change applies the same discipline to every document it
  touches).
- **Gate-id mentions**: only gate_ids that already exist in
  `batch-policies.yaml` may appear backtick-quoted in a plugin document. No
  invented example gate id (an unknown gate id backtick-quoted near the words
  "gate id" is reported as a dangling reference by the plugin invariant
  checker, which the suite runs against the real repository).
- **Error-handling policy for the verification layer**: a malformed
  declaration block fails loudly with the offending document path and row,
  never silently yields an empty option set — an empty set would make a
  missing declaration look like a passing check. The one deliberate
  degrade-to-empty case is the absent exemption registry (see Shared
  Components).
- **Direction**: every reconciliation moves the issuing site toward the policy
  file. No task edits an `option_id` value in `batch-policies.yaml` (NFR5).

## Cross-task Design Decisions

### D1: A dedicated `## Gate option vocabulary` section, not `## Gate identifiers`

The frozen validator derives a gate registry by scanning, in each worker
contract, the section headed `## Gate identifiers` for backtick-quoted tokens
of the `namespace.name` shape, attributing each found gate to that contract's
worker and then enforcing the policy's `option_id` for it. Only the analyst
contract has such a section today, which is exactly why the wider fixture
corpus may reuse other gate_ids with unrelated option vocabularies.

Consequence: declaring vocabularies inside a `## Gate identifiers` section, or
adding that heading to a contract that lacks it, would silently start
enforcing policy option_ids against dozens of existing fixtures and would
contradict an existing test that pins one gate as worker-unattributed.
Therefore the declaration block uses its own distinct level-2 heading, and the
"Frozen machine-read surface" contract above forbids introducing the other
heading anywhere new. Affected tasks: task0001 (all seven documents),
task0002 (must document this constraint as the reason the format is what it
is).

### D2: The issuing-site map is owned by the check module alone

FR2 requires an identified issuing site per gate. Recording that map in both a
document and the checker would create two sources that can drift, which is the
class of defect this feature exists to remove. The map therefore lives only in
the correspondence-check module, where it is executable; the documentation
cites the module as the place the map is pinned and does not restate its rows.
Affected tasks: task0001 (owns), task0002 (cites).

### D3: Exemption registry is documentation-owned and consumed by the checker

FR6 requires a documented reason and compensating guarantee for any gate that
cannot be checked mechanically. Making the documentation the only source of
exemptions removes the possibility of an undocumented exemption existing in
code: the checker has no exemption list of its own, so a gate can only be
skipped by appearing in the documented registry. Because the registry document
and the checker are produced by different tasks working in parallel, the
checker treats an absent registry as zero exemptions; this is a documented
degrade, and after both tasks merge the registry exists with zero rows.
Affected tasks: task0002 (writes), task0001 (consumes).

### D4: Vocabulary declarations and the mechanical check are one task

The check that FR5 requires asserts against documents the declarations create.
Splitting the two across parallel tasks would leave the check task red in its
own worktree until a sibling merged, which contradicts the
"tests passing = task complete" contract implementers work to. The two are
therefore one task (task0001). To keep that task tractable, its hermetic tests
run against synthetic document trees, and only the repository-level assertions
read the real `em-workflow/` tree. Affected tasks: task0001.

### D5: Test placement split

Policy-structure facts (every select entry carries an option_id; the select
gate-id set equals an explicitly pinned set; the intentionally unlisted gate
stays absent; non-select gates carry no option_id) are additions to the module
that already pins the policy file's structure. Correspondence facts (per-gate
option membership, the two regression pins, the on_unanswered disambiguation,
frozen-file byte identity, parser robustness) live in the new module. This
keeps each module's subject single and satisfies FR7 with a real, non-vacuous
update rather than a cosmetic one. Affected tasks: task0001.

### D6: Version bump ownership

Two parallel tasks editing the same two JSON manifests would conflict on every
merge, so exactly one task owns both version fields and no other task lists
them. Affected tasks: task0003 (owns), all others (must not touch).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A vocabulary declaration placed inside a contract's `## Gate identifiers` section (or that heading added to a contract lacking it) silently enforces policy option_ids against the existing fixture corpus | Medium | High — dozens of fixture cases and one derivation test fail, and the frozen validator cannot be edited to compensate | D1's dedicated heading; the "Frozen machine-read surface" contract; the full suite is run before a task is considered done |
| A new section inserted mid-document breaks an existing section-scoped assertion in another test module | Medium | Medium — unrelated test failures attributed to the wrong cause | Append-at-end convention; the full suite (not only the changed module) must be green |
| A backtick-quoted token of `name.suffix` shape added near the words "gate id" is read as a dangling gate reference by the plugin invariant checker the suite runs against the real repository | Low | Medium — repository-level invariant test fails | Gate-id mention convention; only existing gate_ids appear backtick-quoted |
| The checker accepts an option_id found somewhere other than the gate's own vocabulary block (for example an `on_unanswered` value elsewhere in the same document) | Medium | High — the check passes while the batch abort remains reachable | The block-scoped membership contract in Shared Components, pinned by a dedicated negative test (TS5) |
| A frozen file is modified incidentally while editing neighbouring documentation | Low | High — NFR1 violated, and the feature's own premise (no validator change) is lost | No task lists a frozen file in its scope; a digest pin test fails if any of them changes |
| The pinned select-gate count drifts because `batch-policies.yaml` changes before implementation | Low | Low | The pinned set is derived from the file at implementation time and the coverage assertion fails loudly, forcing deliberate re-registration |

## Open Questions

- [ ] None blocking. NFR4 and NFR5 are verified by the pinned policy-file
      assertions and by review reading rather than by a dedicated scenario of
      their own; if the review phase wants a stronger machine guarantee for
      "no second policy table", that is a follow-up, not a gap in this plan.
