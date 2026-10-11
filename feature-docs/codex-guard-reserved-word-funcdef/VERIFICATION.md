# Verification Document: codex-guard-reserved-word-funcdef

## Overview
**Feature**: codex-guard-reserved-word-funcdef / **SPEC.md**: `feature-docs/codex-guard-reserved-word-funcdef/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-reserved-word-funcdef/IMPLEMENTATION.md`

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) have an empty build command; the hook is a Python script with no build step.
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (hook-specific, same suite subset): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for each command, no failures or errors
- Coverage target: not measured (no coverage tool is configured). Every scenario below maps to an automated check.

### Test Scenarios from SPEC.md
Commands use the `CASES` table's Python string literal notation; `\n` is a newline. Every case-table scenario runs against both hook copies. TS-32 to TS-36 are additions in this document for the non-functional requirements and threat mitigations.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `if true; then f() { python3 -i; }; fi` (regression reproduction) | silent: empty stdout, empty stderr, exit 0 | Unit (CASES) |
| TS-2 | `for x in 1; do f() { python3 -i; }; done` | silent | Unit (CASES) |
| TS-3 | `! f() { python3 -i; }` | silent | Unit (CASES) |
| TS-4 | `time f() { python3 -i; }` | silent | Unit (CASES) |
| TS-5 | `if false; then :; else f() { python3 -i; }; fi` | silent | Unit (CASES) |
| TS-6 | `if false; then :; elif f() { python3 -i; }; then :; fi` | silent | Unit (CASES) |
| TS-7 | `if f() { python3 -i; }; then :; fi` | silent | Unit (CASES) |
| TS-8 | `while f() { python3 -i; }; do :; done` | silent | Unit (CASES) |
| TS-9 | `until f() { python3 -i; }; do :; done` | silent | Unit (CASES) |
| TS-10 | `time -p f() { python3 -i; }` | silent | Unit (CASES) |
| TS-11 | `! time f() { python3 -i; }` | silent | Unit (CASES) |
| TS-12 | `if true; then function f() { python3 -i; }; fi` | silent | Unit (CASES) |
| TS-13 | `if true; then f()\n{ python3 -i; }\nfi` | silent | Unit (CASES) |
| TS-14 | `if true; then f() (python3 -i); fi` | silent | Unit (CASES) |
| TS-15 | `then()\n(python3 -i)` | silent | Unit (CASES) |
| TS-16 | `if true; then a=()\n(python3 -i)\nfi` | deny | Unit (CASES) |
| TS-17 | `if true; then export a=()\n(python3 -i)\nfi` | deny | Unit (CASES) |
| TS-18 | `for x in 1; do a=()\n(python3 -i)\ndone` | deny | Unit (CASES) |
| TS-19 | `if false; then :; else a=()\n{ python3 -i; }\nfi` | deny | Unit (CASES) |
| TS-20 | `echo then f()\n(python3 -i)` | deny | Unit (CASES) |
| TS-21 | `if true; then a b()\n(python3 -i)\nfi` | deny | Unit (CASES) |
| TS-22 | `if true; then $f()\n(python3 -i)\nfi` | deny | Unit (CASES) |
| TS-23 | `time -p()\n(python3 -i)` | deny | Unit (CASES) |
| TS-24 | `time -p python3 -i` (existing case) | silent, unchanged | Unit (CASES) |
| TS-25 | `time python3 -i` (existing case) | deny, unchanged | Unit (CASES) |
| TS-26 | `f() { python3; }` (existing case) | silent, unchanged | Unit (CASES) |
| TS-27 | `a=()\n(python3 -i)` (existing case) | deny, unchanged | Unit (CASES) |
| TS-28 | `a b c()\n(python3 -i)` (existing case) | deny, unchanged | Unit (CASES) |
| TS-29 | `TestGuardDocumentation.DOCSTRING_MARKERS` holds at least one new marker for the reserved-word removal sentence; the new and existing markers are all found in both copies' docstrings | documentation test passes | Unit |
| TS-30 | The two hook copies are byte-identical | `TestCopies` passes | Integration |
| TS-31 | `python3 -m unittest tests.test_codex_hook_interactive_guard` and `python3 -m unittest discover -s tests` | both exit 0 | Integration |
| TS-32 | Deep-input test: commands with at least 50,000 leading reserved words before `()`. One is followed by a name and a body holding an interactive launch; the other is only reserved words | each copy answers within the deep-input class's time limit: exit 0, empty stderr, stdout empty or exactly one deny object | Integration (performance) |
| TS-33 | Static constraints of each copy | `TestStaticConstraints` passes (standard library only; no file write, network or process access) | Unit |
| TS-34 | Fail-open behaviour | `TestFailOpen` passes, and every case-table run exits 0 with empty stderr | Unit |
| TS-35 | Plugin version files untouched | the feature diff against the base branch modifies none of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Automated check (git diff) |
| TS-36 | Existing case-table entries preserved | the diff of `tests/test_codex_hook_interactive_guard.py` against the base branch removes or alters no existing `CASES` entry; it only adds entries | Automated check (git diff) |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components)
- Static analysis: none configured. The static-constraints test (TS-33) covers the hook's import and side-effect constraints

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The regression reproduction is silent with exit 0 on both copies | TS-1 |
| AC-2 | Definitions right after `do` / `!` / `time` / `else` / `elif` / `if` / `while` / `until` / `then function` / `time -p` / `! time` are silent on both copies | TS-2 to TS-12 |
| AC-3 | Definitions with a newline before the body, or a subshell body, are silent | TS-13, TS-14 |
| AC-4 | Array assignment (`a=()` / `export a=()`) after a reserved word followed by a subshell or brace group is deny | TS-16 to TS-19 |
| AC-5 | A mid-sequence reserved word is not removed; multi-word and dynamic heads after removal are deny | TS-20, TS-21, TS-22 |
| AC-6 | Reserved-word-only heads: `then()` silent, `time -p()` deny | TS-15, TS-23 |
| AC-7 | Existing cases keep their expected verdicts | TS-24 to TS-28, TS-36 |
| AC-8 | Docstrings describe the removal; documentation markers pass | TS-29 |
| AC-9 | Both copies byte-identical | TS-30 |
| AC-10 | Hook test module and full suite pass | TS-31 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 to TS-14 |
| FR2 | task0001 | TS-10 |
| FR3 | task0001 | TS-15, TS-23 |
| FR4 | task0001 | TS-24, TS-25 |
| FR5 | task0001 | TS-12, TS-16 to TS-22, TS-27, TS-28 |
| FR6 | task0001 | TS-29 |
| FR7 | task0001 | TS-29 |
| FR8 | task0001 | TS-1 to TS-23, TS-31 |
| FR9 | task0001 | TS-1, TS-30 |
| NFR1 | task0001 | TS-30 |
| NFR2 | task0001 | TS-33 |
| NFR3 | task0001 | TS-32, TS-34 |
| NFR4 | task0001 | TS-31, TS-32 |
| NFR5 | task0001 | TS-24 to TS-28, TS-36 |
| NFR6 | task0001 | TS-35 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is automated.

## Performance / Security Verification (if applicable)
- NFR4: deeply nested and very long input is answered within `TestMalformedAndDeepInput`'s time limit (TS-31, TS-32)
- TM-1: only the leading run of reserved words is removed, inside function-name recognition, with the unstripped fallback and unchanged name conditions. Checked by the deny cases TS-16 to TS-23, TS-27 and TS-28, all deny on both copies
- TM-2: the removal step is a single linear pass. Checked by TS-32: a run of at least 50,000 leading reserved words is answered within the time limit by both copies

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-36) | 36 | 36 | 0 | 0 |
| Performance (NFR4) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Total | 39 | 39 | 0 | 0 |
