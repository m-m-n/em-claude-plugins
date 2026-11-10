# Implementation Plan: contributor-consent-command-path

## Overview

Replace the wording-locked command checks in `tests/test_contributor_consent_skill.py`
with structural checks of the two contributor-consent skill copies, and bring the
module's task0009 descriptions in line with the skill-executed design. The skill
copies keep their current design and are expected to stay unchanged. The work is
one task, task0001.

## Technology Stack

- **Language**: Python 3 (the repository test suite)
- **Framework**: unittest from the Python standard library (NFR1)
- **Key libraries**: standard library only
- **New dependencies**: none, so no license entry is recorded (`project.license`: none)

## Layer Structure

| Layer | Responsibility | May depend on |
|-------|----------------|---------------|
| Skill documents (`em-workflow/skills/contributor-consent/SKILL.md`, `em-review/skills/contributor-consent/SKILL.md`) | The subject under test: the six-step consent flow | nothing |
| Test module (`tests/test_contributor_consent_skill.py`) | Reads both copies, splits them into steps, runs the checks, and builds the synthetic inputs of the non-vacuity proofs | the skill documents (read only) |

`tests/test_muse_consent_no_new_questions.py` keeps its exclusion of the two skill
copies and is not changed.

## Shared Components

No component is shared across tasks: the feature has one task (task0001). The
step splitting, element classification and branch binding the checks need are
task-local and are specified in `tasks/task0001.md`.

## Conventions

- Every check runs on both skill copies, one sub-case per plugin, as the existing
  tests of the module do.
- When the two skill copies change, they change together and identically (FR1,
  FR7).
- No document or test written for this feature contains a Notion URL or an
  absolute path under a home directory (NFR5).

## Cross-task Design Decisions

### D1: One task for the whole feature

FR2 to FR6 all land in one test module (SPEC.md, File Structure), and the skill
copies change only when a new check cannot pass against their current text.
Splitting the work would make parallel tasks edit the same module's helpers and
docstring at the same time, or move part of the checks into a second module
against the SPEC's file structure. task0001 therefore carries more acceptance
criteria than the usual task size; they form one coherent set around one module.

Affected tasks: task0001.

### D2: Skill copies are expected unchanged

The skill-executed design of step 5 is the current specification (SPEC.md A3,
A4). The planned classification and binding checks are built to pass against the
current text of both copies. A change to the copies is made only when a check
cannot pass otherwise, and then in both copies identically (FR1, FR7).

Affected tasks: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A structural check passes vacuously because it finds nothing to check | Medium | High: a regression goes undetected | Positive-form assertions (FR3) and a failing synthetic case for every new check (NFR4) |
| A new check is still tied to wording and breaks on a rewrap or a meaning-preserving edit | Medium | Medium | Term matching that ignores whitespace, the rewrap variants of TS-12, and the static check of TS-8 |
| Dropping the exact-count assertions loses detection of a mutating command outside its branch | Medium | High | Classification of every fenced block (FR4) together with the branch binding (FR3); THREAT-MODEL.md TM-1 |

## Open Questions

- None.
