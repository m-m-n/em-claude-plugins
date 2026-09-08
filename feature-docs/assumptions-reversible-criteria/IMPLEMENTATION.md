# Implementation Plan: assumptions-reversible-criteria

## Overview

The judgement criterion for `assumptions[].reversible` is written once, in the
SSOT that owns the field, and is bound into the six worker-facing documents of
the three packet-capable workers by a condensed citation. A recurrence-detecting
test module, a `reversible: true` counter-example fixture and a two-registry
version bump complete the change; the fail-closed classification itself is left
untouched.

## Technology Stack

- **Markdown**: the SSOT schema document, three agent prompts, three worker
  contracts — the whole definition and binding surface.
- **JSON**: one new question-packet fixture, two plugin manifests.
- **Python 3 standard library (`unittest`)**: the recurrence-detecting tests.
- **New dependencies**: none. `project.license` is `none`, so no license
  constraint applies to this feature and no new dependency license needs
  recording.

## Layer Structure

| Layer | Member documents | Responsibility |
|---|---|---|
| Definition | `em-workflow/references/question-packet-schema.md` | Sole owner of the criterion's normative wording |
| Binding | 3 agent prompts + 3 worker contracts | Carry a condensed, binding form plus a pointer to the definition layer |
| Consumption | `em-workflow/references/question-resolution.md` | Reads the field in the fail-closed irreversibility arm; unchanged by this feature |
| Evidence | `tests/`, `em-workflow/references/fixtures/question-packet/` | Pin the definition and binding layers mechanically; demonstrate the criterion applied |

Allowed dependency direction: binding → definition, evidence → definition and
binding. Nothing in the definition layer points at a binding or evidence site,
and the consumption layer gains no new inbound edge.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| C1 criterion token set | The single machine-checkable definition of "this document carries the criterion" | Pre: the text of one document. Post: the document carries the criterion iff it contains the field token `assumptions[].reversible`, the irreversible-half phrase `cannot be undone once applied`, and all three preserved-half phrases `preserved constraint`, `invariant`, `pinned by an existing test`; a *citing* site additionally contains the pointer token `references/question-packet-schema.md` | task0001, task0002 |
| C2 site role split | Distinguishes the one definition site from the six citing sites | Pre: a site is either the definition site or a citing site, never both. Post: the definition site carries the field's type statement plus the full normative criterion sentence; a citing site carries exactly one binding sentence (both halves in condensed form) plus the pointer, and restates none of the schema row's surrounding text | task0001 |
| C3 test-module name allocation | Keeps the three tasks' new test modules distinct and discoverable | Pre: each task creates exactly the module allocated to it. Post: `tests/test_assumptions_reversible_criterion.py` belongs to task0001, `tests/test_question_packet_reversible_fixture.py` to task0002, `tests/test_assumptions_reversible_criteria_version_bump.py` to task0003; no task creates or edits another task's module | task0001, task0002, task0003 |
| C4 worktree-isolated greenness | Makes every task's test suite pass in a worktree holding only that task's own changes | Pre: the task's worktree contains only its own edits. Post: `python3 -m unittest discover -s tests` passes there; no new assertion depends on a file another task creates or edits, and any assertion that ranges over sibling-owned surfaces is an *absence* assertion that also holds on the unedited file | task0001, task0002, task0003 |
| C5 version-bump ownership | Exactly one owner for the two-registry bump | Pre: only task0003 edits the two manifests. Post: both manifests read the same version, `0.1.65`; no other task touches either file | task0001, task0002, task0003 |
| C6 do-not-touch set | Names the files this feature must leave byte-for-byte unchanged | Pre: none. Post: `em-workflow/references/question-resolution.md`, `em-workflow/references/batch-policies.yaml`, `em-workflow/scripts/validate-worker-output.py`, the existing `valid-irreversible-assumption-blocking` fixture and every pre-existing test module are unmodified after the feature's tasks are merged | task0001, task0002, task0003 |

## Conventions

- **Attribution**: no `task00NN` identifier and no `feature-docs/` path appears
  inside any file under `em-workflow/`, in prose, comment or fixture data
  (NFR3).
- **Added prose states the criterion and nothing else**: no justification
  narrative, no reference to the originating incident, no restatement of the
  resolution procedure that the consumption layer owns (NFR6).
- **New tests**: repository-root `tests/`, named `test_*.py`, standard-library
  imports only, no pre-existing test removed or weakened (NFR4).
- **Negative proof style**: every text matcher a task introduces is proved
  non-vacuous by a pair — it rejects forged text with the criterion removed and
  accepts forged text containing it — following the style of the repository's
  existing version-bump test module.
- **Error handling**: no new error path, error code or validation rule is
  introduced anywhere; the validator keeps only its existing boolean type check
  on the field.

## Cross-task Design Decisions

### D1 — The consumption layer is not edited

`em-workflow/references/question-resolution.md` receives no edit at all. FR4 is
a preservation requirement ("any edit here is a citation, never a change of what
aborts"), so the strictly minimal way to satisfy it — and the only way that
carries zero risk to the byte-for-byte arm pins — is to leave the file alone and
pin its current wording with a test. Affected tasks: task0001 (owns the pin),
all tasks (must not edit it).

### D2 — Condensed citation, drift prevented mechanically

NFR1 forbids a restatement "in a way that can drift", while TS-2 / TS-3 require
each citing site to *carry* the criterion, which a bare pointer cannot satisfy.
The resolution: a citing site carries the criterion in condensed form plus the
pointer (C2), and C1's token set is asserted per file by one test module, so any
divergence between the seven sites fails a test rather than surviving as drift.
The condensed form is therefore not free-form prose — it is bounded by C1.
Affected tasks: task0001, task0002.

### D3 — Each task owns the tests that pin its own change

Tasks are implemented fully in parallel in isolated worktrees, so a test
asserting on a sibling task's artifact cannot pass at the time its own task is
finished. Every task therefore ships the tests for its own surface (C3, C4).
FR5's "a new module" is task0001's criterion module; the fixture and version
modules pin FR6 and FR7, which FR5 does not cover. Affected tasks: all.

### D4 — This planning document is not a plugin document

C1 quotes the criterion's invariant phrases so that parallel tasks converge on
the same wording. NFR1's define-once rule governs the shipped document set under
`em-workflow/`; feature-docs planning artifacts are outside it. No task copies
C1's text into a plugin document as a second definition. Affected tasks: all.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The seven sites drift apart in wording, so the criterion means something slightly different per site | medium | high | C1's token set is pinned per file by one test module (D2) |
| An edit near the fail-closed arms silently weakens an abort condition | low | high | D1 forbids editing the consumption layer; TS-4 pins the arms, and the existing arm tests must pass unmodified |
| The new fixture's member-file layout diverges from what the fixture sweep expects | medium | medium | task0002 mirrors the existing sibling fixture's layout and name pattern, and validates directly and under the sweep before declaring done |
| A new test asserts on a sibling task's artifact and cannot pass in its own worktree | medium | high | C4 makes worktree-isolated greenness a contract; sibling-ranging assertions must be absence assertions |
| Two tasks both bump the plugin version, producing a manifest conflict | low | low | C5 gives the bump exactly one owner |

## Open Questions

- [ ] NFR6 (documentation minimality) has no mechanical check; it is verified by
      human reading only and is listed as a manual-verification item.
- [ ] Whether the consumption layer should nonetheless gain a one-line citation
      of the criterion. D1 deliberately says no; a reviewer who disagrees should
      raise it as a review finding rather than an implementer-side expansion.
