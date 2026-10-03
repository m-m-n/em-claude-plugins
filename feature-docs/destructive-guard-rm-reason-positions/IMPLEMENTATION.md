# Implementation Plan: destructive-guard-rm-reason-positions

## Overview

This feature changes four things in destructive-guard's rm deny/ask reasons:

- the `N番目のrmのM番目の対象` designations are numbered by position in the original command string;
- each rm is counted once across the hook's two routes;
- operands are counted with the `--` rule;
- the combined rm-recursive reason gets a deletion-alternative template per target.

Verdicts and rule ids do not change. The feature is one task (task0001).

## Technology Stack

- **Language**: Python 3, standard library only (the hook and its tests).
- **Test framework**: unittest from the standard library (NFR3).
- **New dependencies**: none. project.license is `none`, so there is no license constraint to check and nothing to record.

## Layer Structure

The hook is a single script. This feature touches four consecutive stages of its rm pipeline. Each stage reads only what the stage before it produced:

1. **Statement enumeration** splits the command, and every chunk derived from it (substitution bodies, shell payloads, heredoc bodies), into statements. It now also reports each statement's origin position in the original command.
2. **rm judgment** judges the targets of at most one rm invocation per statement and returns position-tagged records. It never emits and never exits.
3. **Numbering and rendering** runs after every statement has been examined. It assigns invocation ordinals, deduplicates records and renders designations and single-target messages.
4. **Selection and emission** picks the strongest decision, builds the single or combined reason, and emits once.

Everything outside the rm pipeline keeps its current behaviour and its current early exits: the git, file-destruction, external, permission and self-modification checks, and the deferral to sibling guards.

## Shared Components

None. The feature has a single task, so no component one task builds is used by another. The rm pipeline's internal contracts are specified in tasks/task0001.md.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | — | — | — |

## Conventions

- **Reason-text hygiene (NFR2; preserves destructive-guard-rm-holes FR4 / NFR3).** A reason is built only from hook-authored text:
  - fixed sentences;
  - position designations;
  - the fixed substitution stand-in;
  - an rm-root target's raw token, which is limited to the fixed root/home shape vocabulary;
  - deletion templates with the fixed placeholder.

  No other character of a target's text reaches a reason, and the hook's stdout carries no raw control character.
- **Wording that does not change (FR5, A4, A5):**
  - the designation format;
  - the single-target reason texts;
  - the rm-root reason;
  - the CLAUDE_BATCH downgrade wording;
  - the substitution stand-in marker.
- **Determinism (NFR1).** Ordinals, entry order and template selection depend only on the command text and the environment the hook already reads (HOME, PATH for gio). Nothing depends on iteration order of an unordered collection.
- **Tests.**
  - The hook runs as a child process with PreToolUse JSON on standard input. No test imports the hook as a module.
  - Each test builds the environment explicitly: HOME and PATH are always set, and CLAUDE_BATCH only when a case needs it. This follows the existing rm-reason test module.
  - The destructive-guard cases file is not extended (A6). Reason-text checks live in the unittest modules.
- **Plugin version.** This feature's change set does not include it (NFR4). The repository's CI handles versioning.

## Cross-task Design Decisions

### D1: One task, not a split by requirement

- **Decision.** FR1–FR7 are implemented in one task.
- **Rationale.** FR1–FR4 all reshape the same rm decision record and the same handful of functions in one file:
  - FR1 moves rendering after a full scan;
  - FR2 merges the two routes;
  - FR3 changes the target number;
  - FR4 needs a per-record template.

  Tasks run fully in parallel. Split tasks would each re-shape that record independently, conflicting in every shared function. The combined reason (FR4) also cannot be tested end to end without the numbering change (FR1–FR3).
- **Affected tasks.** task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Origin positions misorder a derived-chunk form, such as a heredoc body following statements on its operator line, or a payload that contains a substitution | Medium | Low (numbering wrong, verdict intact) | One test per derived-chunk form (task0001 AC-1); the anchor rules in the task plan's Design Part 1 |
| The restructure (route merge, deduplication, deferred rendering) changes a verdict | Low | High (guard bypass or a new false positive) | Verdicts and rule ids pinned from the unmodified hook; full case suite (THREAT-MODEL.md TM-2) |
| The combined reason picks up target-derived text through the new templates | Low | High | Templates only with the fixed placeholder; planted-text tests (THREAT-MODEL.md TM-1) |
| An existing exact-text pin breaks (the single-target wording, or a designation count in the existing rm-reason tests) | Medium | Medium | Single-target text byte-identical; each designation exactly once in a combined reason; the whole unittest suite runs |

## Open Questions

None.
