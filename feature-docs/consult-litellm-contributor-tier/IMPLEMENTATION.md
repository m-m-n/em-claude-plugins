# Implementation Plan: consult-litellm-contributor-tier

## Overview
The batch Codex consultation's litellm entry now picks its model from a
contributor-consent check that runs once per consultation, the same check
review-phase.md Phase R0 performs. Unit tests pin this behavior. The plan
has one task (task0001).

## Technology Stack
- **Language / Framework**: a Markdown procedure document read by the
  orchestrator; Python 3 standard-library unittest for the tests.
- **Key libraries**: none. The plan adds no new dependency (project.license
  is `none`, so there is no license to record).

## Layer Structure
Not applicable. A single task changes one procedure document and one test
file, and the plan adds no layer.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| None | - | - | - |

No component is shared between tasks, because the plan has a single task.

## Conventions
No cross-task convention beyond the repository's existing rules.

## Cross-task Design Decisions

### Decision 1: one task, not a document task plus a test task
- **Decision**: The procedure change (FR1-FR4) and the recurrence test (FR5)
  are one task.
- **Rationale**: Tasks run fully in parallel, each in its own worktree. FR5's
  test must fail against the pre-fix document and pass against the revised
  one (SPEC.md AC-5). A test task in its own worktree without the document
  change could never finish green, and a document task without the test
  would have no TDD contract.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing assertion forbids the contributor model name inside the consultation procedure, which conflicts with FR2 | Low | High | task0001 reports a plan deviation and does not edit the existing assertion (task0001 Test Notes) |
| The standard flag value is a prefix of the contributor flag value, so a plain presence check for the standard form passes even when only the contributor form exists | High if not handled | Medium | task0001 AC-2 requires the standard-form check to fail when only the contributor form is present |
| A one-line error from a failed consent check is counted as consent | Medium | High | THREAT-MODEL.md TM-1, task0001 AC-6 |
| Line wrapping in the Markdown breaks literal matching | Medium | Low | Whitespace normalization before matching (task0001 Design) |

## Open Questions
- None.
