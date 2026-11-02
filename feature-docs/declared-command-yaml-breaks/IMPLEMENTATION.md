# Implementation Plan: declared-command-yaml-breaks

## Overview

`declared_commands` in `em-workflow/hooks/bash_guard.py` adds a second form of every extracted `*_command` value to the declared set, so a quoted declaration with U+0085, U+2028 or U+2029 at either end is denied as unapproved in its raw, YAML-parsed and end-stripped forms. The countermeasure and the mismatches that stay out of scope are appended to approval-unicode-whitespace's SPEC.md FR8 and THREAT-MODEL.md TM-5.

## Technology Stack

- **Language**: Python 3.14, standard library only (NFR1)
- **Tests**: standard library `unittest`, run as `python3 -m unittest discover -s tests` (NFR4)
- **New dependencies**: none

## Layer Structure

- **Hook decision logic** — `em-workflow/hooks/bash_guard.py`: extracts declared commands from workflow.yaml and decides allow / deny / no verdict for a Bash command.
- **Regression tests** — `tests/`: drive the hook as a subprocess, and load the module without writing bytecode for direct calls.
- **Prior-feature documentation** — `feature-docs/approval-unicode-whitespace/`: SPEC.md FR8 and THREAT-MODEL.md TM-5 receive appended text only.

No dependency direction changes.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Declared-set end-stripped form ("form (b)") | Second declared-set entry per extracted `*_command` value | Pre: the value has been extracted by `strip_yaml_quotes` and is not empty, not `"null"`, not `"~"` (existing exclusion, unchanged). Post: the declared set holds `trim_blanks(value)` when non-empty (form (a), unchanged) and the value with every leading and trailing character from the end-strip set removed, when that result is non-empty (form (b)). The end-strip set is exactly five characters: U+0020, U+0009, U+0085, U+2028, U+2029. No other character is removed by form (b), at either end or inside the value. Form (b) receives no additional `"null"` / `"~"` exclusion. | task0001 (implements), task0002 (documents) |
| Declared-set role boundary | Limits what the declared set can influence | The declared set is consulted only to judge whether a command is workflow-related and to deny it as unapproved. Allow is decided only by an exact match against the approval store and by the cd-prefix form, and neither consults the declared set. No entry added by form (b) can produce an allow. | task0001 (preserves), task0002 (documents) |
| Out-of-scope mismatches | Names what form (b) does not cover | Mismatches produced by YAML escape notation, by block scalars, and by characters inside the value are not handled; such invocations reach the normal permission prompt. | task0001 (does not handle), task0002 (documents) |

## Conventions

- Characters are named by code point (U+0085, U+2028, U+2029, ...) in every plan and document text. No file of this feature carries those three characters raw, except the workflow.yaml fixtures the tests generate at run time. Source-level constraints for `bash_guard.py` and the tests (NFR1 to NFR5) are stated in task0001's plan.
- `feature-docs/approval-unicode-whitespace/reviews/round1.yaml` and `em-workflow/references/command-execution-protocol.md` are changed by no task (FR4).
- The plugin version fields are not touched by any task (NFR6).

## Cross-task Design Decisions

### D1: Form (b) is added to the declared set; allow paths stay untouched

Decision: per SPEC FR1, FR3, A1 and A2, the declared set gains form (b) (Shared Components) while `trim_blanks`, `is_matchable`, `approved_for`, the exact-match and cd-prefix allow in `hook_main`, `read_stdin_commands` and the `--record` / `--remove` / `--list` behavior stay unchanged. A larger declared set only moves the boundary between deny and no verdict.

Affected tasks: task0001 (implements), task0002 (describes the added form).

### D2: The end-strip set is exactly five characters

Decision: form (b) removes only U+0020, U+0009, U+0085, U+2028 and U+2029 from either end. It is not based on the full Unicode whitespace class, so U+00A0, U+000B, U+000C, U+2000 to U+200A, U+3000 and every other whitespace character keep the treatment approval-unicode-whitespace FR8 decided (SPEC FR2). Both the implementation and the appended documentation name the same five characters.

Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The change widens an allow path (THREAT-MODEL.md TM-2) | Low | High | D1; task0001 asserts that no padded or end-stripped form is allowed and that the bare approved command keeps its exact-match allow |
| An existing test pins an outcome that the larger declared set changes (SPEC A6) | Low | Medium | Full suite run in task0001; the existing unicode-whitespace test file is in task0001's file set with change limits stated in its plan |
| The documentation names a strip set different from the implementation | Low | Medium | D2 pins the five characters for both tasks |
| A new constant, comment or docstring line breaks a pinned-text test (status substring, function order, docstring phrases) | Medium | Low | task0001's source constraints; full suite run in task0001 |

## Open Questions

- None.
