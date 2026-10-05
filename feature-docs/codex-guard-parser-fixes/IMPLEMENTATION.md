# Implementation Plan: codex-guard-parser-fixes

## Overview
This feature fixes the six medium findings left in the command parser of
`codex-hook-interactive-guard.py`. The fixes go into both copies, which stay
byte-identical, and into the shared regression table. A separate change
corrects the earlier feature's SPEC, which still states information short
options as common to every interpreter.

## Technology Stack
- **Language**: Python 3, standard library only (NFR2)
- **Tests**: unittest. The existing `tests/test_codex_hook_interactive_guard.py` runs its `CASES` table against both copies.
- **New dependencies**: none, so there is no license to record (`project.license: none`)

## Layer Structure
There are no layers. The guard is one self-contained hook script, shipped as
two byte-identical copies (`em-workflow/scripts/` and `em-review/scripts/`).
The test module depends on both copies. The earlier feature's SPEC is
documentation and has no code dependency in either direction.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Information short-option rule (a behavioural contract shared by code and documentation) | Defines which short options make an interpreter launch an information display, which is never denied | Pre: the interpreter is identified by its name. Post: (1) the shell family (bash / sh / zsh / dash / ksh) has no information short options; `-h` and `-V` are ordinary flags there. (2) Each non-shell interpreter has exactly the information short options in effect for it at the base revision, so its verdicts do not change. (3) Long options (`--version`, `--help`, and each interpreter's own long information options) keep their current treatment. | task0001 (implements it in both copies of the guard), task0002 (states it in the earlier feature's SPEC) |

## Conventions
- **Verdict vocabulary**: both task plans say `deny` when the guard prints its deny JSON, and `silent` when it prints nothing and exits 0. "Indeterminate" (判定不能) always means `silent` (NFR1).

## Cross-task Design Decisions

### D1: One task owns the guard copies and the test table
- **Decision**: task0001 is the only task that edits the two guard copies and `tests/test_codex_hook_interactive_guard.py`. task0002 never touches these files.
- **Rationale**: every parser fix (FR1–FR5) lands in the same pair of files. Each fix also extends the same `CASES` table and the same module docstring. FR6 requires both copies to stay byte-identical in the same change. Parallel tasks would edit the same docstring and table regions, and their merges could leave the copies different.
- **Affected tasks**: task0001, task0002

### D2: The documentation fix is decoupled through the shared rule
- **Decision**: task0002 states the "Information short-option rule" above. It does not wait for, read, or depend on task0001's code.
- **Affected tasks**: task0001, task0002

### D3: Plugin version
- **Decision**: this repository bumps plugin versions automatically. No task edits any `plugin.json` or `.claude-plugin/marketplace.json` (NFR3).
- **Affected tasks**: task0001, task0002

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A relaxation (FR3 / FR4 / FR5) reaches beyond its trigger and lets an interactive launch through | Medium | High | Deny-side boundary cases in `CASES` (THREAT-MODEL.md TM-2) |
| The guard can only tell whether a group is connected after reading past the group's close, so judging inner commands too early causes false denials | Medium | Medium | Silent-side group cases, including nested groups and a heredoc after the close |
| Documents outside the SPEC scope (README, references) still describe `-h` / `-V` as common to every interpreter | Low | Low | Out of scope. An implementer who notices one reports it as an observation and does not edit it |
| The two copies diverge | Low | High | The existing byte-equality test |

## Open Questions
- [ ] Do documents other than `feature-docs/codex-interactive-guard-hook/SPEC.md` (for example a plugin README or a reference document) restate the old common `-h` / `-V` rule? SPEC.md limits the change to that SPEC's FR7 and table note.
