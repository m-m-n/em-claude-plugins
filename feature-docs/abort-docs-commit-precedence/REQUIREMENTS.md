---
title: "abort-docs-commit-precedence"
created_date: 2026-09-24
status: draft
---

# abort-docs-commit-precedence - Requirements

## 1. Overview

### 1.1 Background

The batch second-failure abort's terminal status commit
(`em-workflow/references/implement-phase.md` Step I.2.c abort-phase terminal
status commit) can exhaust `commit-docs.sh` exit-4 recovery. That stop matches
two phase-specific stop points, `implement-second-failure` and
`docs-commit-conflict`. The state it leaves in the integration worktree, and how
the next run handles that state, are not yet defined.

### 1.2 Purpose

Achieve the business objectives in 2.1.

### 1.3 Scope

In scope:

- The 'Precedence rule:' paragraph of `em-workflow/references/batch-terminal-line.md` (FR1-FR3)
- The Branch & Worktree Model exit-4 bullet of `em-workflow/references/implement-phase.md` (FR4)
- `em-workflow/skills/develop/SKILL.md` Step A resume path (FR5)
- Re-derivation of the abort on resume, and the `detail` / `resume_conditions` content for this stop (FR6, FR7)
- The RECOVERY CONTRACT comment in `em-workflow/scripts/commit-docs.sh` (FR9)
- The em-workflow version in both manifests (FR10)
- Tests for the above (12)

Out of scope:

- Stops at the other implement exit-4 call sites (FR8)
- Any change to the reason code set or the Stop point coverage rows (NFR1)
- Any executable line of any script (NFR4)

## 2. Business Requirements

### 2.1 Business Objectives

- Every batch-terminating stop binds to exactly one reason code, including the
  stop where the batch second-failure abort's terminal status commit exhausts
  `commit-docs.sh` exit-4 recovery.
- The state that stop leaves in the integration worktree, and how the next run
  handles it, is defined.

## 3. Use Cases

### 3.1 Use Case List

| ID | Use case | Actor |
|----|----------|-------|
| UC01 | Batch stop at the abort's terminal status commit | em-workflow orchestrator (batch mode) |
| UC02 | Resume after that stop | em-workflow develop skill (batch or interactive) |

### 3.2 Use Case Details

#### UC01: Batch stop at the abort's terminal status commit

**Actor**: em-workflow orchestrator (batch mode)

**Preconditions**:
- The batch second-failure abort runs for a task.
- The batch retry-consumed marker in `tasks.{T}.notes` is already committed on the branch (a5).

**Basic flow**:
1. The abort path refreshes the integration worktree and writes the terminal status (`implement: failed` / `failed_kind: decision`) (a4).
2. The terminal status commit (Step I.2.c abort-phase terminal status commit) returns exit 4.
3. Exit-4 recovery refreshes, re-applies the write and retries once (a4).
4. The retry returns exit 4 again.
5. The stop binds to `docs-commit-conflict` → `docs_commit_conflict_aborted` (FR1). The run ends (FR2).
6. `detail` names the call site, the failing task(s) and that the terminal status write is uncommitted. `resume_conditions` states that the next run discards the leftover write at develop's resume entry and re-derives the abort from committed facts (FR7).

**Alternative flow**:
- The first attempt returns exit 4 and the retry succeeds: the stop keeps today's binding, `implement-second-failure` → `implement_task_failed` (FR2).

**Postconditions**:
- The terminal status write exists in the integration worktree, uncommitted, and is not on the branch (FR3, FR4).
- The run does not reach a Step B evaluation that reads the uncommitted `implement: failed` (FR2).

#### UC02: Resume after that stop

**Actor**: em-workflow develop skill (batch or interactive)

**Preconditions**:
- The feature exists, its integration worktree exists and holds a workflow.yaml.

**Basic flow**:
1. Step A's bootstrap check takes the 'workflow.yaml 存在する（通常の再開）' branch.
2. The integration worktree is refreshed with `git -C {integration worktree} reset --hard em-workflow/{feature}/integration`, discarding any leftover terminal status write (FR5).
3. Step A.5 runs, then Step B reads workflow.yaml.
4. The implement phase re-derives the abort only from committed facts: task status, the retry-consumed marker in `tasks.{T}.notes`, and the journal. No additional automatic retry is granted (FR6).
5. The re-derived abort re-applies and commits the terminal status write.
6. When that commit succeeds, the stop binds to `implement-second-failure` → `implement_task_failed` (FR6).

**Postconditions**:
- No uncommitted terminal status write from the previous run remains in tracked files.

## 4. Functional Requirements

### 4.1 Function List

| ID | Name | Target |
|----|------|--------|
| FR1 | Phase-specific vs phase-specific precedence | `em-workflow/references/batch-terminal-line.md` |
| FR2 | Same run never reaches Step B | `em-workflow/references/batch-terminal-line.md` |
| FR3 | Written-but-uncommitted vs no status write | `em-workflow/references/batch-terminal-line.md` |
| FR4 | Uncommitted terminal write and the NFR2 exception | `em-workflow/references/implement-phase.md` |
| FR5 | Discard at develop's resume entry | `em-workflow/skills/develop/SKILL.md` |
| FR6 | Re-derivation from committed facts | Not specified |
| FR7 | detail / resume_conditions content | Not specified |
| FR8 | Scope limited to the batch abort | - |
| FR9 | commit-docs.sh NFR2 restatement consistent | `em-workflow/scripts/commit-docs.sh` |
| FR10 | Lockstep version bump | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |

### 4.2 Function Details

#### FR1: Phase-specific vs phase-specific precedence

The 'Precedence rule:' paragraph of `em-workflow/references/batch-terminal-line.md`
states, inside that paragraph with no blank line inserted, what happens when a
stop matches two phase-specific rows. The row whose commit failure directly
caused the stop wins. Concretely: when the batch second-failure abort's
terminal status commit (implement-phase.md Step I.2.c abort-phase terminal
status commit) returns exit 4 on its first attempt and again on its single
retry, the stop binds to `docs-commit-conflict` → `docs_commit_conflict_aborted`,
not `implement-second-failure` → `implement_task_failed`.

#### FR2: Same run never reaches Step B

The same paragraph states that this stop ends the run. The run does not reach a
Step B evaluation that reads the uncommitted `implement: failed`, so neither
`implement-second-failure` (realized through Step B) nor `stop-condition-3`
applies to that run. A first exit 4 followed by a successful retry keeps
today's binding, `implement-second-failure` → `implement_task_failed`.

#### FR3: Written-but-uncommitted vs no status write

The Precedence paragraph keeps the existing sentence that `docs-commit-conflict`
'aborts without writing any status, because the failed status write is itself
its stop cause'. It adds that in the FR1 case, the terminal status write
(`implement: failed` / `failed_kind: decision`) exists in the integration
worktree but stays uncommitted and never reaches the branch.

#### FR4: Uncommitted terminal write and the NFR2 exception

`em-workflow/references/implement-phase.md`, at the Branch & Worktree Model
exit-4 bullet and outside the I.2.c batch-mode paragraph, defines the
following. When the batch second-failure abort's terminal status commit hits a
second exit 4, the re-applied `implement: failed` / `failed_kind: decision`
write stays uncommitted in the integration worktree and is not on the branch.
The NFR2 claim 'the integration worktree never carries uncommitted state across
turns' gets a named exception for exactly this stop, and that exception refers
to FR5 for how the leftover is discarded.

#### FR5: Discard at develop's resume entry

`em-workflow/skills/develop/SKILL.md` Step A: on an existing feature whose
integration worktree exists, the bootstrap check's 'workflow.yaml
存在する（通常の再開）' branch refreshes the integration worktree before Step
A.5, using `git -C {integration worktree} reset --hard em-workflow/{feature}/integration`.
This discards any leftover terminal status write before Step A.5 reads or
commits anything and before Step B reads workflow.yaml. The refresh runs
whether the resuming run is batch or interactive.

#### FR6: Re-derivation from committed facts

After the FR5 discard, the resumed implement phase re-derives the abort only
from committed facts: task status, the retry-consumed marker in
`tasks.{T}.notes`, and the journal. It grants no additional automatic retry.
The re-derived abort re-applies and commits the terminal status write. When
that commit succeeds, the stop follows the existing binding
(`implement-second-failure` → `implement_task_failed`).

#### FR7: detail / resume_conditions content

For the FR1 stop, the text requires `detail` to name the call site (Step I.2.c
abort-phase terminal status commit), the failing task(s), and that the
terminal status write is uncommitted. It also requires `resume_conditions` to
state that the next run discards the leftover write at develop's resume entry
and re-derives the abort from committed facts.

#### FR8: Scope limited to the batch abort

The new precedence and the uncommitted-write definition cover only the
collision between the batch second-failure abort's terminal commit and
`docs-commit-conflict`. Stops at the other implement exit-4 call sites (Step
I.1 baseline, Step I.2.a launch, Step I.2.b wake, Step I.3 completion) keep
their binding to `docs_commit_conflict_aborted` alone. No reason code and no
Stop point coverage row is added or changed.

#### FR9: commit-docs.sh NFR2 restatement consistent

The RECOVERY CONTRACT comment in `em-workflow/scripts/commit-docs.sh` ('safe
per NFR2, this worktree never carries uncommitted state across turns') is
changed, as a comment-only edit, so it no longer contradicts the FR4
exception. It either names the exception or defers to implement-phase.md. The
pinned phrases 'EXCEPT a call site whose', 'a proof of unreachability', 'a
defined terminal for an unexpected non-zero exit',
'em-workflow/references/implement-phase.md' and "I.2.c's route-back commit"
all stay.

#### FR10: Lockstep version bump

The em-workflow version goes from 0.2.1 to 0.2.2 in
`em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of
`.claude-plugin/marketplace.json`, in the same change.

## 5. Non-Functional Requirements

| ID | Name |
|----|------|
| NFR1 | Code and row set unchanged |
| NFR2 | Pinned text preserved |
| NFR3 | No new test failures |
| NFR4 | Documentation-only |

#### NFR1: Code and row set unchanged

The 13-code reason set and the 14-row Stop point coverage table stay unchanged,
including key/code pairs and order.

#### NFR2: Pinned text preserved

The following pinned text stays as it is.

- In the Precedence paragraph: 'phase-specific stop point takes precedence over
  the generic', 'through that phase's own abort route', 'no route of the
  current run produced', 'write a step's status', 'aborts without writing any
  status', 'the failed status write is itself its stop cause', the three
  stop-point keys, and the stop-condition-3 → `failed_kind` restriction order.
  The paragraph never names `no-work-required`.
- The implement-phase.md I.2.c batch-mode paragraph and everything after it up
  to the end of I.2.c stay byte-identical.
- The SKILL.md exit-4 リカバリ pins stay.
- The Branch & Worktree Model exit-4 bullet phrases ('A second exit 4 stops the
  phase', "Step I.2.c's abort-phase terminal status commit", the carve-out
  sentence) stay.

#### NFR3: No new test failures

`python3 -m unittest discover -s tests` shows no failures beyond the 9
pre-existing baseline failures on main.

#### NFR4: Documentation-only

No executable line of `em-workflow/scripts/commit-docs.sh` or of any other
script changes. Changes are limited to reference and SKILL prose, the
commit-docs.sh comment, tests and version manifests.

## 6. UI/UX Requirements

Not applicable. The design step is skipped (documentation-only).

## 7. Data Requirements

Not applicable (NFR4).

## 8. External Integrations

None.

## 9. Constraints

### 9.1 Technical Constraints

- NFR1, NFR2 and NFR4 apply to every change in this feature.

### 9.4 Declared Change Set

Feature-specific paths are not enumerated by hand here. They are derived at
create-plan from every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

**Default members** (always part of the declaration unless the SPEC author explicitly removes them):
- `feature-docs/abort-docs-commit-precedence/**`
- `test-docs/abort-docs-commit-precedence/**`

`feature-docs/abort-docs-commit-precedence/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. Their generators are the phase documents
and `references/phase-state.md` (cited only; their rules are not restated).

`test-docs/abort-docs-commit-precedence/**` covers `{T}.tests.yaml` (path form:
`test-docs/abort-docs-commit-precedence/{T}.tests.yaml`). Its generator is
`implement-phase.md` (cited only; its rules are not restated).

**Semantics**:
- Default members are part of the declaration unless the SPEC author explicitly
  removes them. Removal is a deliberate narrowing, not an omission by silence.
- The declaration is a superset assertion: the actual change set must be
  CONTAINED IN the declaration. A declared path that is never generated is not a
  violation. A feature that generates no implement tasks generates no
  `test-docs/abort-docs-commit-precedence/` directory, and the declared
  `test-docs/abort-docs-commit-precedence/**` is still correct.

## 10. Assumptions

| ID | Assumption | Reason | Impact | Reversible |
|----|------------|--------|--------|------------|
| a1 | No new stop reason code and no new Stop point coverage row are added. | Pinned by test_batch_stop_contract.py and test_failed_kind_batch_docs.py. The answer to requirement.precedence-winner states that 13 codes and 14 rows stay unchanged. | medium | yes |
| a2 | The existing Precedence rule anchors listed in NFR2 stay in the 'Precedence rule:' paragraph. | Asserted by `_assert_precedence_rule_stated`, `_assert_docs_commit_conflict_no_status_stated` and `TestPrecedenceParagraphStatesBothRestrictions`. | medium | yes |
| a3 | The FR5 discard is the same refresh already used elsewhere (`reset --hard em-workflow/{feature}/integration`). It runs every time develop resumes an existing feature whose worktree holds a workflow.yaml, before Step A.5, whether the resuming run is batch or interactive. It is not gated on detecting this particular stop. | The committed state cannot show that the previous run ended at this stop. After a concurrent update-ref, the worktree reads as dirty anyway. NFR2 already declares that no legitimate uncommitted state exists across turns, and a batch stop can be resumed interactively. reset --hard leaves untracked files alone. | medium | no |
| a4 | The abort path's own refresh comes before its single write, and the exit-4 recovery refreshes again before re-applying. So at this stop, the only uncommitted content in tracked files is the terminal status write. | implement-phase.md L963-979 / L993-1004 (tip → refresh → write → commit; the terminal status write is the ONLY side effect) and L52-59 (recovery refreshes before re-applying). | low | yes |
| a5 | The batch retry-consumed marker in `tasks.{T}.notes` is already committed on the branch when the second-failure abort runs, so re-derivation after the FR5 discard sees the retry as consumed. | Every workflow.yaml write is followed by a commit-docs.sh commit in the same step (SKILL.md L469-474, implement-phase.md L40-42). The exact commit point of the marker is not stated in the scanned files. | medium | yes |
| a6 | The version bump is a patch bump from 0.2.1 to 0.2.2, done in lockstep. | `.claude/rules/core-plugin-version-bump.md`: behavior fixes are patch bumps. | low | yes |

In a3, a4, FR4 and FR9, "NFR2" refers to the existing claim 'the integration
worktree never carries uncommitted state across turns', not to NFR2 of this
document.

## 11. Success Criteria

### 11.1 Acceptance Criteria

- [ ] AC1 (FR1): batch-terminal-line.md's 'Precedence rule:' paragraph, sliced from its label to the next blank line, names both `implement-second-failure` and `docs-commit-conflict` as matching the abort-terminal-commit stop and states that `docs-commit-conflict` / `docs_commit_conflict_aborted` wins.
- [ ] AC2 (FR2): The same paragraph states that the stop ends the run and that no Step B evaluation of the uncommitted `implement: failed` happens in that run. It also states that a first exit 4 followed by a successful retry keeps `implement_task_failed`.
- [ ] AC3 (FR3): The paragraph distinguishes the 'written but uncommitted' terminal status write from 'aborts without writing any status' while keeping the existing sentence.
- [ ] AC4 (FR4): implement-phase.md's Branch & Worktree Model defines the uncommitted terminal status write at this stop and gives NFR2's 'never carries uncommitted state across turns' a named exception for it.
- [ ] AC5 (FR5): develop/SKILL.md Step A's resume path for an existing workflow.yaml refreshes the integration worktree with `reset --hard em-workflow/{feature}/integration` before Step A.5.
- [ ] AC6 (FR6, FR7): The text states re-derivation from committed facts with no extra automatic retry, and says what `detail` and `resume_conditions` must contain for this stop.
- [ ] AC7 (FR8, NFR1): The 13 codes and 14 rows are unchanged, and the other implement exit-4 call sites still bind only to `docs_commit_conflict_aborted`.
- [ ] AC8 (NFR2, NFR3): `python3 -m unittest discover -s tests` shows no new failures versus the 9-failure baseline, and the I.2.c batch-mode paragraph byte pins still pass.
- [ ] AC9 (FR10): plugin.json and marketplace.json both read 0.2.2 for em-workflow in the same change.

## 12. Test Scenarios

### 12.1 Test Scenarios

- [ ] TS1 (AC1-AC3): A new doc-contract test slices the Precedence paragraph with the existing `_extract_precedence_rule_paragraph` approach. It asserts the phase-specific-vs-phase-specific statement, `docs_commit_conflict_aborted` as the winner, the terminal-stop / no-Step-B statement, the retry-success carve-out and the written-but-uncommitted distinction, and that `no-work-required` does not appear.
- [ ] TS2 (AC1 negative proof): The new matchers reject the current pre-change paragraph text, pinned as a verbatim sample.
- [ ] TS3 (AC4): A test asserts that the Branch & Worktree Model region of implement-phase.md names the NFR2 exception for the abort-phase terminal status commit's second exit 4, and that the I.2.c batch-mode paragraph is still byte-identical (existing pins).
- [ ] TS4 (AC5): A test asserts that develop/SKILL.md Step A's 'existing workflow.yaml' resume branch contains the `reset --hard em-workflow/{feature}/integration` refresh and that it comes before the 'Step A.5' hand-off in text order.
- [ ] TS5 (AC6): A test asserts that the re-derivation sentence names committed task status, the retry-consumed marker and the journal, states that no additional automatic retry is granted, and names the `detail` / `resume_conditions` content.
- [ ] TS6 (AC7): Existing test_batch_stop_contract.py / test_failed_kind_batch_docs.py code-set and row-set pins pass unchanged.
- [ ] TS7 (AC9): The existing version-lockstep test in test_implement_routeback_gate.py passes with 0.2.2 in both manifests.
- [ ] TS8 (AC8): The full `python3 -m unittest discover -s tests` run shows exactly the 9 baseline failures.

## 13. Glossary

| Term | Definition |
|------|------------|
| Precedence paragraph | The 'Precedence rule:' paragraph of `em-workflow/references/batch-terminal-line.md`, sliced from its label to the next blank line |
| Abort terminal status commit | implement-phase.md Step I.2.c abort-phase terminal status commit of the batch second-failure abort |
| Terminal status write | The `implement: failed` / `failed_kind: decision` write made by the batch second-failure abort |

## 14. Confirmed Items

### 14.1 Confirmed

- [x] requirement.precedence-winner: the 13 codes and 14 rows stay unchanged.

### 14.2 Unconfirmed / Pending

- [ ] The exact commit point of the batch retry-consumed marker in `tasks.{T}.notes` is not stated in the scanned files (a5).

## 15. References

- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/references/implement-phase.md`
- `em-workflow/skills/develop/SKILL.md`
- `em-workflow/scripts/commit-docs.sh`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.claude/rules/core-plugin-version-bump.md`
