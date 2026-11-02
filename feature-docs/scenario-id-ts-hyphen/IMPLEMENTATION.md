# Implementation Plan: scenario-id-ts-hyphen

## Overview

Make the TS-n form the only scenario ID form em-workflow writes into a new
SPEC.md, VERIFICATION.md or task plan, enforce it on implementation-planner
results with one new validator check, and keep every read-side path accepting
both the TS-n and the TSn forms.

## Technology Stack

- **Language**: Python 3 — `em-workflow/scripts/validate-worker-output.py` and
  the `tests/` suite (standard library `unittest`).
- **Documents**: Markdown — agent prompts, templates, contracts, the
  plan-writing skill and the create-plan phase document.
- **New dependencies**: none. `project.license` is `none`; there is no license
  to record.

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Authoring rules | `em-workflow/agents/spec-writer.md`, `em-workflow/references/templates/spec-document.md`, `em-workflow/references/contracts/spec-writer-contract.md`, `em-workflow/skills/plan-writing/SKILL.md`, `em-workflow/agents/implementation-planner.md`, `em-workflow/references/contracts/planner-contract.md` | Tell the LLM workers which scenario ID form to write |
| Phase protocol | `em-workflow/references/phases/create-plan-phase.md` | States which planning invariants the validator checks mechanically |
| Validator | `em-workflow/scripts/validate-worker-output.py` | Enforces the TS-n form on implementation-planner results |
| Tests | `tests/` | Pin the validator behavior and the document wording |

Dependency direction: the documents describe the validator check exactly as
pinned in Shared Components below; the validator never reads those documents.
Tests read the files they verify; no test module imports another test module.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Scenario ID forms | The two scenario ID spellings and how they compare | TS-n form: `TS`, one hyphen, one or more digits. TSn form (hyphen-less): `TS` immediately followed by one or more digits. These are the only two forms. IDs are compared as literal strings; neither form is normalized into the other. New documents use the TS-n form only; reading an existing document accepts both. | task0001, task0002, task0003, task0004 |
| Hyphen-less ID detection rule | Decides what the new check counts as a TSn ID (SPEC A1, A2) | Input: the text of one document. The text first passes through the validator's existing noise-stripping step, which removes fenced code blocks and HTML comments; inline code spans are NOT removed. Output: the set of matches of the existing read grammar (`TS-?\d+`) that contain no hyphen and whose immediately preceding character is not an ASCII letter (A-Z, a-z) or ASCII digit (0-9). A match at the very start of the text has no preceding character and counts. A non-ASCII preceding character (for example Japanese text) does not stop a match from counting. | task0001 (implements), task0003 and task0004 (describe) |
| Scenario-ID form check | Rejects hyphen-less IDs in the documents an implementation-planner result newly writes (FR3) | See "Scenario-ID form check contract" below. | task0001 (implements), task0004 (documents) |

### Scenario-ID form check contract

- **When it runs**: only when all four hold — `--kind worker-result`,
  `--worker implementation-planner`, the result's `status` is `completed`,
  and `--feature-dir` is supplied. It never runs for any other worker
  (`rework-planner` included), for any other status, or without
  `--feature-dir`.
- **Targets**:
  - (a) `VERIFICATION.md` directly under the feature directory.
  - (b) every file named by `workflow_patch.tasks_patch.entries[].plan`
    whose final path segment is not `TASK.md`. Ids listed in
    `tasks_patch.carried_task_ids` have no entry, so their plans are not
    targets.
- **Absent VERIFICATION.md**: target (a) is skipped with no error (the
  minimal tier writes no VERIFICATION.md).
- **Read safety (THREAT-MODEL.md TM-1, TM-2)**:
  - A task plan is read only after it has passed the checks the existing
    task-plan validation already applies to the same `plan` value (safe
    relative path, no symlink at any segment, containment in the feature
    directory, existing regular file, size within the existing plan-read byte
    limit). A plan that fails them is left to the existing errors and is
    neither read nor reported again by this check.
  - `VERIFICATION.md` is read only when it is a regular file, not a symlink,
    within the same byte limit, and decodes as UTF-8. Otherwise the check
    reports one error for it, naming the file and the reason, and does not
    scan its content.
  - The check never raises an exception for any file content or file state.
- **Postcondition**: each target that contains at least one hyphen-less ID
  yields exactly one validation error with code `scenario-id-form`. Its
  message names the file (`VERIFICATION.md`, or the task id together with its
  `plan` value) and lists the hyphen-less IDs found, de-duplicated and sorted.
  A target whose IDs are all in the TS-n form yields no error.
- **Read side unchanged (FR4)**: the read grammar, the Test Scenarios ID
  extraction, the noise-stripping step, the rework_index novelty and
  rename-aware coverage checks, `tests_replace`, and verification_index
  reading keep their current behavior.

## Conventions

- **Language of edited documents**: each document keeps its existing
  language.
- **sha256 pin ownership**: only task0001 edits
  `em-workflow/scripts/validate-worker-output.py`,
  `tests/test_validate_worker_output.py` and
  `tests/test_gate_option_vocabulary.py`. No other task touches these three
  files, because the last one pins the digests of the first two.
- **Byte-pinned surfaces stay untouched**: `em-workflow/references/workflow-patch.md`,
  `PINNED_VALIDATOR_TEST_LINE`, and the `## Gate option vocabulary` section of
  `em-workflow/agents/implementation-planner.md` (heading through end of
  file). New text in a document goes before that document's
  `## Gate option vocabulary` heading.
- **Headings stay stable**: existing tests anchor on literal headings. No
  task renames, renumbers or removes an existing heading in a document it
  edits.
- **Document-content tests**: each documentation task adds its own new test
  module under `tests/`. The module locates files relative to its own path,
  anchors on literal headings, compares whitespace-normalized text so a line
  wrap does not break an assertion, and carries at least one negative proof
  per matcher (the matcher shown failing on a pre-change excerpt).
- **Hyphen-less examples**: the documents and tests this feature edits may
  show the hyphen-less form where they explain it (rule text, test data).
  Tests that need hyphen-less IDs build them as test data inside the test
  module.
- **Error-handling policy (validator)**: the content and state of
  worker-written files are reported as validation errors (code + message),
  never as an exception.

## Cross-task Design Decisions

### D1: The check runs on `completed` results only

A `needs_user_input`, `blocked` or `failed` planner result writes no
artifact. On a re-plan of a feature created before this change, the feature
directory still holds the earlier VERIFICATION.md with hyphen-less IDs while
the planner asks its existing-files question; checking that file would reject
a result that wrote nothing and stall the question loop, which FR4 forbids.
Affected: task0001 (implements), task0004 (documents the scope).

### D2: Detection reuses the read grammar plus a left boundary

The new check does not change the read grammar or the extraction function.
It filters the read grammar's matches by the Hyphen-less ID detection rule
above (SPEC A1, A2). Inline code spans are scanned so that wrapping an ID in
backticks does not hide it. Affected: task0001 (implements), task0003 and
task0004 (describe).

### D3: A feature whose SPEC.md uses the hyphen-less form

The planner writes VERIFICATION.md with the same numbers in the TS-n form
(hyphen-less 3 becomes `TS-3`) and does not rewrite SPEC.md (SPEC A6). The
rule text is owned by the plan-writing skill's scenario ID rule (task0003);
the planner documents cite it instead of restating it (task0004).

### D4: Single owner per statement

- Scenario ID authoring rule for VERIFICATION.md and task plans:
  `em-workflow/skills/plan-writing/SKILL.md` (task0003).
- Scenario ID numbering for SPEC.md: `em-workflow/agents/spec-writer.md`
  (task0002), mirrored by the template and the spec-writer contract.
- List of validator-implemented planning invariants:
  `em-workflow/references/phases/create-plan-phase.md` section 9 (task0004).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A document edit breaks an existing document-content test that anchors on wording or headings | Medium | Medium | Insert text without renaming headings; each task runs the full suite (NFR3) |
| A task other than task0001 edits a sha256-pinned file, so the pins fail after merge | Low | High | Pin ownership convention above |
| A completed planner result that does not rewrite VERIFICATION.md (for example a minimal-tier plan in a feature that still holds an older full-tier VERIFICATION.md with hyphen-less IDs) is rejected | Low | Low | The error names the file; listed under Open Questions |
| A planner writes a hyphen-less ID in prose (for example when noting the legacy mapping) and its result is rejected | Medium | Low | The plan-writing rule tells the planner to write no hyphen-less ID outside fenced code blocks and HTML comments (task0003) |

## Open Questions

- [ ] D1 (check only `completed` results) is an interpretation; SPEC FR3 does
  not name a status.
- [ ] A completed planner result in a feature directory that still holds an
  older hyphen-less VERIFICATION.md it did not rewrite is rejected. No current
  route produces this; it is not handled specially.
