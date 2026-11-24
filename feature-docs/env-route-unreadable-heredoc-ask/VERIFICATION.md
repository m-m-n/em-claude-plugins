# Verification Document: env-route-unreadable-heredoc-ask

## Overview
**Feature**: env-route-unreadable-heredoc-ask / **SPEC.md**: `feature-docs/env-route-unreadable-heredoc-ask/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/env-route-unreadable-heredoc-ask/IMPLEMENTATION.md`

## Build Verification
- Command: none. `build_command` of component `main` in workflow.yaml is empty (Python, no build step).
- Expected: nothing to run.

## Test Verification
- Command (from the repository root): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Coverage target: no coverage tool is configured; every scenario below passes.

### Test Scenarios from SPEC.md

TS-1 to TS-8 come from SPEC.md. TS-9 to TS-21 are added by this plan for the
in-process facts no hook verdict shows (FR1 to FR3), for NFR1, NFR2 and NFR4,
for assumption A2, and for the failures of the payload's map and chunk build
(FR1, IMPLEMENTATION.md D5). "TS-1 body" is: a `cat <<${tag}` line, one
harmless line, a `${tag}` line, then a notion-pair
`mcp-bridge run --mcp notion --tool notion-create-comment --args-json` call
whose JSON `command` is `git branch -D example`.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `/usr/bin/env 'BASH_FUNC_mcp-bridge%%=() { :; }' bash -c '<TS-1 body>'`, without batch | ask, rule `args-json-unrestorable` (allow before the change) | Case (runner) |
| TS-2 | The TS-1 command in batch | deny, rule `args-json-unrestorable` | Case (runner) |
| TS-3 | The TS-1 body through `env - 'BASH_FUNC_mcp-bridge%%=() { :; }' bash -c`, in batch | deny, rule `args-json-unrestorable` | Case (runner) |
| TS-4 | After the unreadable `${tag}` here-document, the call's command word written as (a) `"mcp-"bridge`, (b) `mcp-br`, a backslash, a newline and `idge`, (c) `$'\x6dcp-bridge'`, (d) `mcp-$"bridge"`, (e) `mcp-$`, a backslash, a newline and `"bridge"`, (f) `$`, a backslash, a newline and `'\x6dcp-bridge'`; each in batch | each: deny, rule `args-json-unrestorable` ((d), (e) and (f): allow before task0002) | Case (runner) |
| TS-5 | The existing env-route-lex-flag-isolation cases at lines 1678 and 1679 of the case file, not edited | batch allow, as before | Case (runner) |
| TS-6 | Control: body `echo mcp-bridge; cat <<${tag}`, one harmless line, a `${tag}` line, in batch | the verdict recorded before the change (expected allow); never `args-json-unrestorable` | Case (runner) |
| TS-7 | Body `cat <<${tag}`, a `mcp-bridge` line, a `${tag}` line (the word only as here-document body text), in batch | deny, rule `args-json-unrestorable` | Case (runner) |
| TS-8 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` | both pass | Integration |
| TS-9 | The tail rule on hand-written payloads: plain word, quote-split word, continuation-split word, `$'`; and a tail without the word, `${a}cp-bridge`, a name built with `$(printf ...)`, the word only before the tail start, a readable map | true for the first four; false for the last five | Unit |
| TS-10 | The env body reading for the TS-1, TS-4 (a) to (c) and TS-7 bodies, and for a readable payload holding `mcp-bridge` in a statement that is not a lifted notion statement | Unrestorable reported for the unreadable bodies, not for the readable payload; for the unreadable bodies the map has `unreadable` set and a tail start at or before the first unreadable `<<` (A4) | Unit |
| TS-11 | A payload read under both extglob settings whose tail rule answers true under only one setting, either setting being the first | the combined result is unrestorable | Unit |
| TS-12 | A reading in which the tail rule answers true, for all eight combinations of the entry values of `_lex_unreadable_met`, `_lex_extglob_met` and `_lex_extglob` | the three equal their entry values after the reading | Unit |
| TS-13 | The TS-1 command followed by `; git branch -D example` at the top level, without batch | deny, rule `git-branch-force-delete` (the deny outranks the held ask) | Case (runner) |
| TS-14 | `bash -c '<TS-1 body>'` with no env, in batch | the verdict and rule recorded before the change (expected deny, `unreadable-heredoc-delimiter`) | Case (runner) |
| TS-15 | The TS-1 body with `--mcp desktop-commander --tool start_process` in place of the notion pair; the TS-1 body through `/usr/bin/env bash -c` with no `BASH_FUNC_` assignment; each in batch | each: deny, rule `args-json-unrestorable` (A2) | Case (runner) |
| TS-16 | The feature's change set: the integration branch diffed against its base | no change to `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | Integration (diff check) |
| TS-17 | The tail rule's condition (b) on hand-written payloads: the word split by `$"`; `$"` without the word; `$` and `"` around one line continuation; `$` and `'` around one line continuation; `$` and a quote character around two line continuations; and, with no `mcp-bridge` word in the tail: `$"` only before the tail start, `$` and a quote character separated by a blank, by a newline without a backslash, or by a backslash, a double-quoted `"$x"`, and `$"` with a map whose `unreadable` is not set | true for the first five; false for the rest | Unit |
| TS-18 | The env body reading for the TS-4 (d), (e) and (f) bodies | Unrestorable reported for each; the rule changes neither the entries nor Overrun; the map has `unreadable` set and a tail start at or before the first unreadable `<<` (A4) | Unit |
| TS-19 | The payload's map is obtained and a later step of the chunk build fails (LexBudgetExceeded, and LexUnmatchedSubscript): for the TS-1, TS-4 and TS-7 bodies; for an unreadable body whose tail meets neither (a) nor (b) and for a readable body holding `mcp-bridge`; for a payload read under both extglob settings where the step fails under only one of them; and for all eight combinations of the flag entry values | the rule is asked once per reading with the payload and its map; no entries and no Overrun; Unrestorable true for the first group, false for the second; the combined result is unrestorable when the rule answers true in the failing reading; the three flags equal their entry values; no exception leaves the reading | Unit |
| TS-20 | The payload's map cannot be obtained (the lexer raises LexBudgetExceeded, and LexUnmatchedSubscript, for the payload's text), with a payload that would meet (a), for all eight combinations of the flag entry values | the rule is not asked; the reading is empty and the route's result is the nothing result; the three flags equal their entry values; no exception leaves the reading | Unit |
| TS-21 | The TS-1 command whose body has one more last line, opening an array subscript at an assignment position that is never closed, in batch | deny; the verdict and rule on the unmodified hook are recorded first (expected deny, `args-json-unrestorable`); after the change the rule is the recorded one, or `args-json-unrestorable` when the recorded verdict is allow | Case (runner) |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; every listed scenario passes in TS-8 or as TS-16 |
| SC-2 | All test scenarios pass | TS-8 and TS-16 |
| SC-3 | No existing deny / ask case was removed | The diff of `em-workflow/hooks/tests/destructive-guard-cases.json` against the base holds only appended cases; TS-5 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-6, TS-7, TS-9, TS-10, TS-15, TS-17, TS-18, TS-19, TS-20, TS-21 |
| FR2 | task0001, task0002 | TS-11, TS-19 |
| FR3 | task0001, task0002 | TS-5, TS-6, TS-12, TS-17, TS-19, TS-20 |
| FR4 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-6, TS-7, TS-8, TS-13, TS-14, TS-15, TS-21 |
| NFR1 | task0001, task0002 | TS-5, TS-14 |
| NFR2 | task0001 | TS-13 |
| NFR3 | task0001, task0002 | TS-8 |
| NFR4 | task0001, task0002 | TS-16 |

## E2E Testing
None: the project has no E2E framework (SPEC.md, E2E Tests).

## Manual Testing (E2E Not Possible)
None. The design step was skipped, so there is no mockup comparison.

## Performance / Security Verification
- NFR2: a deny outranks the `args-json-unrestorable` ask and the scan-budget ask outranks it — TS-13; the existing precedence cases run in TS-8.
- TM-1: an unreadable payload map whose raw tail holds the `mcp-bridge` word makes the reading unrestorable, giving the `args-json-unrestorable` ask (deny in batch) — TS-1, TS-2, TS-3, TS-7 and TS-15 (cases), TS-10 (unit).
- TM-2: line continuations, then `'`, `"` and `\`, are removed from the tail before the word is matched — TS-4 (a) and (b) (cases), TS-9 (unit).
- TM-3: any `$'` in the tail makes the reading unrestorable — TS-4 (c) (case), TS-9 (unit).
- TM-4: the Unrestorable flags of the two extglob readings are combined with OR — TS-11 and TS-19 (unit).
- TM-5: the new ask needs an unreadable map and condition (a) or (b); the flag save and restore and every path outside the env route are unchanged — TS-5, TS-6 and TS-14 (cases), TS-12, the false answers of TS-17 and TS-19, and TS-20 (unit).
- TM-6: any `$"` in the tail makes the reading unrestorable — TS-4 (d) (case), TS-17 and TS-18 (unit).
- TM-7: `$'` and `$"` are looked for after the line continuations are removed from the tail — TS-4 (e) and (f) (cases), TS-17 and TS-18 (unit).
- TM-8: the tail rule's answer on an obtained map is kept when a later step of the chunk build fails — TS-19 (unit), TS-21 (case).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-21) | 21 | 21 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 3 | 3 | 0 | 0 |
| Requirements coverage | 8 | 8 | 0 | 0 |
| Performance / Security (NFR2, TM-1 to TM-8) | 9 | 9 | 0 | 0 |
