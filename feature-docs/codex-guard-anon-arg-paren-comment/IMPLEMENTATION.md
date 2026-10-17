# Implementation Plan: codex-guard-anon-arg-paren-comment

## Overview
In codex-hook-interactive-guard, an anonymous-function argument `(` that
never closes is rescued when the first separator read directly inside it is
`;` or a lone `&`, so an interactive launch after that separator is judged.
Newline-first provisional groups and genuinely unclosed groups stay
undecidable. One task covers both guard copies and the shared test module.

## Technology Stack
- **Language**: Python 3, standard library only (NFR2)
- **Test framework**: unittest (`tests/test_codex_hook_interactive_guard.py`)
- **New dependencies**: none (`project.license: none`; no license to record)

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Guard | `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py` | Read the command string from the hook payload and decide deny or no output. Two copies, byte-identical. |
| Tests | `tests/test_codex_hook_interactive_guard.py` | Run the `CASES` table, documentation markers, byte identity, performance, recursion and constraint checks against both copies. |

Dependency direction: tests load each guard copy; the guard depends on
nothing else in the repository.

## Shared Components
None. The feature is a single task; no component built by one task is
consumed by another.

## Conventions
- Both guard copies change in the same commit and stay byte-identical (FR8).
- Undecidable input produces no output; this policy does not change (SPEC
  Error Handling).
- `CASES` entries keep the existing three-element form (expected verdict
  `deny` or `silent`, label, command) and the existing label style; the table
  runs against both copies.
- Scenario IDs use the VERIFICATION.md form: TS-1 to TS-17 correspond to
  SPEC.md TS1 to TS17 of the same number.
- The change set is the three files above plus workflow-generated documents
  under `feature-docs/` and `test-docs/`. Plugin manifests and the
  marketplace file are not part of it (NFR3).

## Cross-task Design Decisions

### D1: Single task
- **Decision**: task0001 owns both guard copies and the test module.
- **Rationale**: the copies must be byte-identical, the same `CASES` table
  runs against both, and the documentation markers in the test module track
  the docstrings in the guard. Any split puts parallel tasks on the same three
  files with no contract that separates them.
- **Affected tasks**: task0001

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rescued commands keep the anonymous-function head's connection and hide a program-less launch (TS-13) | Medium | High (missed interactive launch) | task0001 design moves rescued commands out of the provisional frame; task0001 AC-3 |
| Cascading rescue over nested provisional groups becomes quadratic | Medium | Medium (time budget exceeded, no verdict) | Linear-time contract and a wide-tail performance form; task0001 AC-7 |
| The rescue trigger is read from the lookahead scan instead of the main reader, so quoted or escaped `;` / `&`, or `&>` / `>&`, act as triggers | Medium | Medium (spurious deny) | task0001 design takes the trigger from main-reader tokens; task0001 AC-2 |
| A docstring wording change breaks existing documentation markers | Low | Low | task0001 AC-5 |
| The two copies diverge | Low | Medium | Byte-identity test; task0001 AC-6 |

## Open Questions
- [ ] The word-initial `(` form (TS-5) and the inner-to-outer cascade over
      nested provisional groups follow SPEC assumptions; neither was measured
      on zsh 5.9.
