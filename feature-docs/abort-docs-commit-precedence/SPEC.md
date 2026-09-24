# Feature: abort-docs-commit-precedence

## Overview

When the batch second-failure abort's terminal status commit (implement-phase.md
Step I.2.c abort-phase terminal status commit) returns exit 4 on its first
attempt and again on its single retry, the stop binds to `docs-commit-conflict`
→ `docs_commit_conflict_aborted` and ends the run, leaving the terminal status
write uncommitted in the integration worktree. The next run of develop discards
that leftover at its resume entry and re-derives the abort from committed facts.
This is a documentation-only change; see `REQUIREMENTS.md` in this directory.

## Objectives

- Every batch-terminating stop binds to exactly one reason code, including the stop where the batch second-failure abort's terminal status commit exhausts `commit-docs.sh` exit-4 recovery.
- The state that stop leaves in the integration worktree, and how the next run handles it, is defined.

## User Stories

### US1: One reason code for the abort terminal-commit stop
As a user of an em-workflow batch run, I want the stop where the batch
second-failure abort's terminal status commit exhausts exit-4 recovery to bind
to exactly one reason code, so that every batch-terminating stop binds to
exactly one reason code.

**Acceptance Criteria:**
- [ ] AC1 (FR1): batch-terminal-line.md's 'Precedence rule:' paragraph, sliced from its label to the next blank line, names both `implement-second-failure` and `docs-commit-conflict` as matching the abort-terminal-commit stop and states that `docs-commit-conflict` / `docs_commit_conflict_aborted` wins.
- [ ] AC2 (FR2): The same paragraph states that the stop ends the run and that no Step B evaluation of the uncommitted `implement: failed` happens in that run. It also states that a first exit 4 followed by a successful retry keeps `implement_task_failed`.
- [ ] AC3 (FR3): The paragraph distinguishes the 'written but uncommitted' terminal status write from 'aborts without writing any status' while keeping the existing sentence.
- [ ] AC7 (FR8, NFR1): The 13 codes and 14 rows are unchanged, and the other implement exit-4 call sites still bind only to `docs_commit_conflict_aborted`.

### US2: Defined leftover state and resume handling
As a user resuming an em-workflow feature after that stop, in batch or
interactive mode, I want the leftover terminal status write to be defined and
discarded at develop's resume entry, and the abort re-derived from committed
facts, so that the state that stop leaves and how the next run handles it are
defined.

**Acceptance Criteria:**
- [ ] AC4 (FR4): implement-phase.md's Branch & Worktree Model defines the uncommitted terminal status write at this stop and gives NFR2's 'never carries uncommitted state across turns' a named exception for it.
- [ ] AC5 (FR5): develop/SKILL.md Step A's resume path for an existing workflow.yaml refreshes the integration worktree with `reset --hard em-workflow/{feature}/integration` before Step A.5.
- [ ] AC6 (FR6, FR7): The text states re-derivation from committed facts with no extra automatic retry, and says what `detail` and `resume_conditions` must contain for this stop.

## Technical Requirements

In FR4, FR9 and assumptions a3/a4, "NFR2" refers to the existing claim 'the
integration worktree never carries uncommitted state across turns', not to
NFR2 of this document.

### Functional Requirements
- **FR1:** Phase-specific vs phase-specific precedence. The 'Precedence rule:' paragraph of `em-workflow/references/batch-terminal-line.md` states, inside that paragraph with no blank line inserted, what happens when a stop matches two phase-specific rows. The row whose commit failure directly caused the stop wins. Concretely: when the batch second-failure abort's terminal status commit (implement-phase.md Step I.2.c abort-phase terminal status commit) returns exit 4 on its first attempt and again on its single retry, the stop binds to `docs-commit-conflict` → `docs_commit_conflict_aborted`, not `implement-second-failure` → `implement_task_failed`.
- **FR2:** Same run never reaches Step B. The same paragraph states that this stop ends the run. The run does not reach a Step B evaluation that reads the uncommitted `implement: failed`, so neither `implement-second-failure` (realized through Step B) nor `stop-condition-3` applies to that run. A first exit 4 followed by a successful retry keeps today's binding, `implement-second-failure` → `implement_task_failed`.
- **FR3:** Written-but-uncommitted vs no status write. The Precedence paragraph keeps the existing sentence that `docs-commit-conflict` 'aborts without writing any status, because the failed status write is itself its stop cause'. It adds that in the FR1 case, the terminal status write (`implement: failed` / `failed_kind: decision`) exists in the integration worktree but stays uncommitted and never reaches the branch.
- **FR4:** Uncommitted terminal write and the NFR2 exception. `em-workflow/references/implement-phase.md`, at the Branch & Worktree Model exit-4 bullet and outside the I.2.c batch-mode paragraph, defines the following. When the batch second-failure abort's terminal status commit hits a second exit 4, the re-applied `implement: failed` / `failed_kind: decision` write stays uncommitted in the integration worktree and is not on the branch. The NFR2 claim 'the integration worktree never carries uncommitted state across turns' gets a named exception for exactly this stop, and that exception refers to FR5 for how the leftover is discarded.
- **FR5:** Discard at develop's resume entry. `em-workflow/skills/develop/SKILL.md` Step A: on an existing feature whose integration worktree exists, the bootstrap check's 'workflow.yaml 存在する（通常の再開）' branch refreshes the integration worktree before Step A.5, using `git -C {integration worktree} reset --hard em-workflow/{feature}/integration`. This discards any leftover terminal status write before Step A.5 reads or commits anything and before Step B reads workflow.yaml. The refresh runs whether the resuming run is batch or interactive.
- **FR6:** Re-derivation from committed facts. After the FR5 discard, the resumed implement phase re-derives the abort only from committed facts: task status, the retry-consumed marker in `tasks.{T}.notes`, and the journal. It grants no additional automatic retry. The re-derived abort re-applies and commits the terminal status write. When that commit succeeds, the stop follows the existing binding (`implement-second-failure` → `implement_task_failed`).
- **FR7:** detail / resume_conditions content. For the FR1 stop, the text requires `detail` to name the call site (Step I.2.c abort-phase terminal status commit), the failing task(s), and that the terminal status write is uncommitted. It also requires `resume_conditions` to state that the next run discards the leftover write at develop's resume entry and re-derives the abort from committed facts.
- **FR8:** Scope limited to the batch abort. The new precedence and the uncommitted-write definition cover only the collision between the batch second-failure abort's terminal commit and `docs-commit-conflict`. Stops at the other implement exit-4 call sites (Step I.1 baseline, Step I.2.a launch, Step I.2.b wake, Step I.3 completion) keep their binding to `docs_commit_conflict_aborted` alone. No reason code and no Stop point coverage row is added or changed.
- **FR9:** commit-docs.sh NFR2 restatement consistent. The RECOVERY CONTRACT comment in `em-workflow/scripts/commit-docs.sh` ('safe per NFR2, this worktree never carries uncommitted state across turns') is changed, as a comment-only edit, so it no longer contradicts the FR4 exception. It either names the exception or defers to implement-phase.md. The pinned phrases 'EXCEPT a call site whose', 'a proof of unreachability', 'a defined terminal for an unexpected non-zero exit', 'em-workflow/references/implement-phase.md' and "I.2.c's route-back commit" all stay.
- **FR10:** Lockstep version bump. The em-workflow version goes from 0.2.1 to 0.2.2 in `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of `.claude-plugin/marketplace.json`, in the same change.

### Non-Functional Requirements
- **NFR1 - Code and row set unchanged:** The 13-code reason set and the 14-row Stop point coverage table stay unchanged, including key/code pairs and order.
- **NFR2 - Pinned text preserved:** The following pinned text stays as it is. In the Precedence paragraph: 'phase-specific stop point takes precedence over the generic', 'through that phase's own abort route', 'no route of the current run produced', 'write a step's status', 'aborts without writing any status', 'the failed status write is itself its stop cause', the three stop-point keys, and the stop-condition-3 → `failed_kind` restriction order; the paragraph never names `no-work-required`. The implement-phase.md I.2.c batch-mode paragraph and everything after it up to the end of I.2.c stay byte-identical. The SKILL.md exit-4 リカバリ pins stay. The Branch & Worktree Model exit-4 bullet phrases ('A second exit 4 stops the phase', "Step I.2.c's abort-phase terminal status commit", the carve-out sentence) stay.
- **NFR3 - No new test failures:** `python3 -m unittest discover -s tests` shows no failures beyond the 9 pre-existing baseline failures on main.
- **NFR4 - Documentation-only:** No executable line of `em-workflow/scripts/commit-docs.sh` or of any other script changes. Changes are limited to reference and SKILL prose, the commit-docs.sh comment, tests and version manifests.

## Implementation Approach

### Architecture

Not applicable (NFR4). The change sites are:

| File | Location | Requirements |
|------|----------|--------------|
| `em-workflow/references/batch-terminal-line.md` | 'Precedence rule:' paragraph (no blank line inserted) | FR1, FR2, FR3, NFR2 |
| `em-workflow/references/implement-phase.md` | Branch & Worktree Model exit-4 bullet, outside the I.2.c batch-mode paragraph | FR4, NFR2 |
| `em-workflow/skills/develop/SKILL.md` | Step A bootstrap check, 'workflow.yaml 存在する（通常の再開）' branch, before Step A.5 | FR5, NFR2 |
| `em-workflow/scripts/commit-docs.sh` | RECOVERY CONTRACT comment (comment-only) | FR9, NFR4 |
| `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | em-workflow `version` | FR10 |
| `tests/` | New doc-contract tests | TS1-TS5 |

The location of the FR6 and FR7 text is not fixed by the requirements.

### Data Flow

Stop (batch run):

```
Step I.2.c batch second-failure abort
  → refresh → write `implement: failed` / `failed_kind: decision` → commit-docs.sh: exit 4
  → exit-4 recovery: refresh → re-apply write → retry: exit 4
  → stop: docs-commit-conflict → docs_commit_conflict_aborted; run ends
     (terminal status write left uncommitted in the integration worktree; no Step B)
```

Resume (next run, batch or interactive):

```
develop Step A, 'workflow.yaml 存在する（通常の再開）' branch
  → git -C {integration worktree} reset --hard em-workflow/{feature}/integration
  → Step A.5 → Step B reads workflow.yaml
  → implement re-derives the abort from committed task status, the retry-consumed
    marker in tasks.{T}.notes, and the journal (no additional automatic retry)
  → re-apply and commit the terminal status write
  → on success: implement-second-failure → implement_task_failed
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `_extract_precedence_rule_paragraph`: existing approach used by TS1 to slice the Precedence paragraph.
- `test_batch_stop_contract.py`, `test_failed_kind_batch_docs.py`: existing code-set and row-set pins (TS6).
- `test_implement_routeback_gate.py`: existing version-lockstep test (TS7).
- `_assert_precedence_rule_stated`, `_assert_docs_commit_conflict_no_status_stated`, `TestPrecedenceParagraphStatesBothRestrictions`: existing assertions on the Precedence rule anchors (a2).

**External Dependencies:**
- None.

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json           # FR10
├── references/
│   ├── batch-terminal-line.md           # FR1-FR3
│   └── implement-phase.md               # FR4
├── skills/develop/SKILL.md              # FR5
└── scripts/commit-docs.sh               # FR9 (comment only)
.claude-plugin/marketplace.json          # FR10
tests/                                   # TS1-TS5 (new doc-contract tests)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/abort-docs-commit-precedence/**`
- `test-docs/abort-docs-commit-precedence/**`

`feature-docs/abort-docs-commit-precedence/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/abort-docs-commit-precedence/**` covers
`test-docs/abort-docs-commit-precedence/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section cites
it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/abort-docs-commit-precedence/` directory at all; the declared
`test-docs/abort-docs-commit-precedence/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1-AC3; FR1, FR2, FR3, NFR2): A new doc-contract test slices the Precedence paragraph with the existing `_extract_precedence_rule_paragraph` approach. It asserts the phase-specific-vs-phase-specific statement, `docs_commit_conflict_aborted` as the winner, the terminal-stop / no-Step-B statement, the retry-success carve-out and the written-but-uncommitted distinction, and that `no-work-required` does not appear.
- [ ] TS2 (AC1 negative proof; FR1): The new matchers reject the current pre-change paragraph text, pinned as a verbatim sample.
- [ ] TS3 (AC4; FR4, NFR2): A test asserts that the Branch & Worktree Model region of implement-phase.md names the NFR2 exception for the abort-phase terminal status commit's second exit 4, and that the I.2.c batch-mode paragraph is still byte-identical (existing pins).
- [ ] TS4 (AC5; FR5): A test asserts that develop/SKILL.md Step A's 'existing workflow.yaml' resume branch contains the `reset --hard em-workflow/{feature}/integration` refresh and that it comes before the 'Step A.5' hand-off in text order.
- [ ] TS5 (AC6; FR6, FR7): A test asserts that the re-derivation sentence names committed task status, the retry-consumed marker and the journal, states that no additional automatic retry is granted, and names the `detail` / `resume_conditions` content.
- [ ] TS6 (AC7; FR8, NFR1): Existing test_batch_stop_contract.py / test_failed_kind_batch_docs.py code-set and row-set pins pass unchanged.
- [ ] TS7 (AC9; FR10): The existing version-lockstep test in test_implement_routeback_gate.py passes with 0.2.2 in both manifests.

### Integration Tests
- [ ] TS8 (AC8; NFR2, NFR3): The full `python3 -m unittest discover -s tests` run shows exactly the 9 baseline failures.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] First exit 4 followed by a successful retry: binding stays `implement-second-failure` → `implement_task_failed` (FR2).
- [ ] Exit 4 at Step I.1 baseline, Step I.2.a launch, Step I.2.b wake or Step I.3 completion: binding stays `docs_commit_conflict_aborted` alone (FR8).
- [ ] A batch stop resumed interactively: the FR5 refresh still runs (FR5, a3).

### Performance Tests
Not applicable.

## Security Considerations

Not applicable (NFR4).

## Error Handling

### Stop Binding

| Situation | Stop point key | Reason code | Requirement |
|-----------|----------------|-------------|-------------|
| Abort terminal status commit: exit 4, retry exit 4 | `docs-commit-conflict` | `docs_commit_conflict_aborted` | FR1 |
| Abort terminal status commit: exit 4, retry succeeds | `implement-second-failure` | `implement_task_failed` | FR2 |
| Resumed run: re-derived abort's terminal status commit succeeds | `implement-second-failure` | `implement_task_failed` | FR6 |
| Stop at another implement exit-4 call site (I.1, I.2.a, I.2.b, I.3) | `docs-commit-conflict` | `docs_commit_conflict_aborted` | FR8 |

For the first row, `detail` names the call site (Step I.2.c abort-phase
terminal status commit), the failing task(s), and that the terminal status
write is uncommitted; `resume_conditions` states that the next run discards the
leftover write at develop's resume entry and re-derives the abort from
committed facts (FR7).

## Assumptions

| ID | Assumption | Impact | Reversible |
|----|------------|--------|------------|
| a1 | No new stop reason code and no new Stop point coverage row are added. | medium | yes |
| a2 | The existing Precedence rule anchors listed in NFR2 stay in the 'Precedence rule:' paragraph. | medium | yes |
| a3 | The FR5 discard is the same refresh already used elsewhere (`reset --hard em-workflow/{feature}/integration`). It runs every time develop resumes an existing feature whose worktree holds a workflow.yaml, before Step A.5, whether the resuming run is batch or interactive. It is not gated on detecting this particular stop. | medium | no |
| a4 | The abort path's own refresh comes before its single write, and the exit-4 recovery refreshes again before re-applying. So at this stop, the only uncommitted content in tracked files is the terminal status write. | low | yes |
| a5 | The batch retry-consumed marker in `tasks.{T}.notes` is already committed on the branch when the second-failure abort runs, so re-derivation after the FR5 discard sees the retry as consumed. | medium | yes |
| a6 | The version bump is a patch bump from 0.2.1 to 0.2.2, done in lockstep. | low | yes |

Reasons for each assumption are recorded in `REQUIREMENTS.md` section 10.

## Success Criteria

- [ ] AC1-AC9 are met.
- [ ] TS1-TS8 pass.

## Open Questions

None. Every FR/NFR is `resolved`.

## References

- `feature-docs/abort-docs-commit-precedence/REQUIREMENTS.md`
- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/references/implement-phase.md`
- `em-workflow/skills/develop/SKILL.md`
- `em-workflow/scripts/commit-docs.sh`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
