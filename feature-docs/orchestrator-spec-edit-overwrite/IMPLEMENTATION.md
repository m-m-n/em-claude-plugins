# Implementation Plan: orchestrator-spec-edit-overwrite

## Overview

The orchestrator records each change it makes and commits to the feature's own
SPEC.md / REQUIREMENTS.md during create-plan in a new append-only record of
`phase-state/create-plan.yaml`. The create-spec action decision counts the last
record entry for a path as a second match for `replace_own`. Every change is to
Markdown protocol documents of the em-workflow plugin plus new document tests.
No script changes.

## Technology Stack

- **Documents**: Markdown protocol documents under `em-workflow/references/`
  (English) and `em-workflow/skills/develop/SKILL.md` (Japanese). Each edit
  keeps the language of the document it edits.
- **Tests**: Python 3 `unittest`, standard library only, run by
  `python3 -m unittest discover -s tests`.
- **New dependencies**: none (`project.license` is `none`; no license to record).

## Layer Structure

| Layer | Documents | Role |
|---|---|---|
| Owner sections (each rule stated once) | `em-workflow/references/contracts/spec-writer-contract.md` section "How the orchestrator chooses each target's action before dispatch" (the action decision); `em-workflow/references/phase-state.md` section `## Schema` (the record's shape); `em-workflow/references/artifact-digest.md` (digest definition, calculation, legacy records, pre-dispatch verification; unchanged) | State the rule |
| Procedure and citing places | `em-workflow/skills/develop/SKILL.md` `## Step B: 自走ループ` (the writer procedure); `em-workflow/references/phases/create-spec-phase.md` `## 9. Spec writer dispatch` and the `replace_own` row of spec-writer-contract.md's action table (apply the decision by citation) | Cite by path and section name, never restate |
| Tests | `tests/` | Read the documents; never write them |

Dependency direction: a citing place points to an owner section, never the other
way. Owner sections refer to one another by path and section name only.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| The `orchestrator_doc_edits` record of `phase-state/create-plan.yaml` | Persisted evidence that the orchestrator itself changed and committed the feature's own SPEC.md or REQUIREMENTS.md during create-plan | The field name is exactly `orchestrator_doc_edits`. It is a top-level key of a phase-state mapping, held only when `phase: create-plan`. The value is a list and is append-only: never rewritten or cleared, a phase restart (`generation` increases) included. Each entry has exactly the keys `path`, `sha256` and `reason`. `path` uses the same project-relative form as `artifacts[].path` and `write_policy.targets[].path` (for example `feature-docs/{feature}/SPEC.md`). `sha256` is the value that `references/artifact-digest.md` "Digest definition" defines, calculated by its "Calculation". `reason` is non-empty text. The last entry for a path is the entry for that path that comes last in the list. A `phase-state/create-plan.yaml` without the field stays valid. The shape is owned by `references/phase-state.md` `## Schema`; no other document restates it. | task0001 (reader rule), task0002 (schema and writer) |
| The action-decision owner section | Single statement of which recorded entries give a create-spec target `replace_own` | The heading text "How the orchestrator chooses each target's action before dispatch" in `references/contracts/spec-writer-contract.md` is unchanged and stays a level-2 heading with no subsection. Only this section states the match rule, the read conditions of `phase-state/create-plan.yaml` and the no-record cases. Other documents cite it by the path `references/contracts/spec-writer-contract.md` and the exact heading text. | task0001 (writes it), task0002 (cites it from phase-state.md) |
| The writer procedure | Single statement of when and how the orchestrator appends an `orchestrator_doc_edits` entry | Lives in `skills/develop/SKILL.md` `## Step B: 自走ループ`. Cited from elsewhere as `skills/develop/SKILL.md`, Step B. | task0002 (writes it and cites it from phase-state.md) |

## Conventions

- **Cite, never restate (NFR4)**: a citing place names the owner path and the
  section name. No new or changed text names `git hash-object`, and none
  restates the digest format or the calculation means (raw bytes, hexadecimal
  digits, the script name, its error tokens, the quoting rule).
- **Worker digest stance**: every sentence of a contract document that speaks of
  computing or comparing a digest names the orchestrator as its subject. No
  sentence tells the worker, or any named worker, to compute or compare a digest
  (checked by `scripts/check-plugin-invariants.py` `worker_digest_stance` and by
  `tests/test_digest_contract_alignment.py`).
- **No new vocabulary**: no new `write_policy` action, no new gate id, no new
  phase-state file, and no new heading in any edited document.
- **Existing tests stay as they are (NFR3)**: no existing test method is
  removed, renamed or weakened. Each task adds its own new test file.
- **Test method**: follow `tests/test_artifact_digest_docs.py`. Cut a place out
  by its heading, paragraph or bullet, normalize whitespace, then assert that
  key tokens are present or absent. Never compare a whole document and never pin
  a line-break position. Every presence check has a forged copy without its token
  on which it fails. Every absence check has a forged copy carrying its token on
  which it fires. Each test file is self-contained (its own helpers, no import
  from another test module).
- **Redaction**: no home-directory absolute path and no Notion URL in any
  written file.

## Cross-task Design Decisions

### D1: Record name and place

The record is the `orchestrator_doc_edits` list in `phase-state/create-plan.yaml`
(SPEC A-3), beside the existing append-only `other_feature_doc_fixes` list. It
covers the feature's own SPEC.md and REQUIREMENTS.md only (A-4). Affected:
task0001, task0002.

### D2: Last entry per path, compared by exact path

Only the last entry for a path counts (SPEC TS-4). The entry's `path` is compared
as a string with the target's path, so the writer records the same
project-relative form the targets use. Affected: task0001 (rule), task0002
(writer and schema).

### D3: Read conditions live only in the owner section

The phase / feature condition and the five no-record cases (FR4) are stated only
in the action-decision owner section. The phase-state.md row and the SKILL.md
procedure do not restate them, nor the last-entry rule. Affected: task0001,
task0002.

### D4: The record counts only in the create-spec decision

The create-plan planning-lineage rule and the design step's decision are not
changed (FR5). The record holds only SPEC.md and REQUIREMENTS.md paths, which are
never create-plan or design targets. Affected: task0001, task0002.

### D5: One new test file per task

task0001 adds `tests/test_orchestrator_doc_edits_action_docs.py`; task0002 adds
`tests/test_orchestrator_doc_edits_record_docs.py`. No shared test helper module,
so the two tasks share no file. Affected: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An edit of the owner section breaks a statement that `tests/test_artifact_digest_docs.py` pins (its planning-lineage statements and its `replace_own` row statements) | Medium | High | The create-spec rule is a separate block placed after the create-plan rule's last bullet; existing sentences stay verbatim except the one sentence task0001 names; the full suite is run |
| The `replace_own` row gains a pipe character or a forbidden token | Low | Medium | task0001 AC-5; the existing three-cell and seven-row checks |
| The new SKILL.md paragraph changes a slice that other tests pin | Medium | Medium | task0002 places it after the `**exit-4 リカバリ**` paragraph and writes no git command in it |
| The match is worded more broadly than FR3 | Low | High | THREAT-MODEL.md TM-3; task0001 AC-1, AC-2, AC-4, AC-6 |

## Open Questions

- [ ] `scripts/validate-worker-output.py --kind phase-state` checks the shape of
  `other_feature_doc_fixes` but will not check `orchestrator_doc_edits`. SPEC.md
  asks for no script change, so this plan adds no shape check.
