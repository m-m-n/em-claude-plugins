# Verification Document: destructive-guard-heredoc-bypass-fixes

## Overview
**Feature**: destructive-guard-heredoc-bypass-fixes / **SPEC.md**: `feature-docs/destructive-guard-heredoc-bypass-fixes/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-heredoc-bypass-fixes/IMPLEMENTATION.md`

Notation: `{BS-NL}` is a backslash immediately followed by a newline; `{NL}`
is a newline. "Base" means `workflow.implement.base_commit`.

## Build Verification
- Command: none (`build_command` is empty; the hook is an interpreted script).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  (registered as `e2e_test_command`)
- Expected: both exit 0 with no failing case or test.
- Coverage target: not measured; completeness is judged by the case table and
  the scenarios below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | (FR1, AC1) Case-table entry `x{BS-NL}=( <<EOF{NL}git reset --hard HEAD{NL}EOF` | deny | Unit (case table) |
| TS2 | (FR1, AC2) Case-table entry `decl{BS-NL}are x=( <<EOF{NL}git reset --hard HEAD{NL}EOF` | deny | Unit (case table) |
| TS3 | (FR2, AC3) Case-table entries: a here-document operator first, `NAME[` in the arguments of declare / typeset / local / export / readonly on the same line, and on a following line a destructive line that bash 5.3.9 executes | deny | Unit (case table) |
| TS4 | (FR3, AC4) Case-table entries: the TS3 shape with the command name eval / let / alias, limited to the forms measured on bash 5.3.9 to execute the destructive line | deny | Unit (case table) |
| TS5 | (FR4, AC5) Case-table entry: an outer and an inner eval both carrying the prefix `x=(@`, extglob switched between them (f34ee27bc8c323b1) | ask | Unit (case table) |
| TS6 | (FR2, FR3, NFR1, AC6) Existing entries T2 E-1 and T2 E-9 | deny | Unit (case table) |
| TS7 | (FR4, NFR1, AC8) Existing entry T2 AC-4.7 (`x=( @(foo\|bar) ); cat <<"EOF"{NL}hello{NL}EOF`) | allow | Unit (case table) |
| TS8 | (FR3, NFR2, NFR3, AC7, AC10) Both test commands above, including the unchanged `SUBSCRIPT_ARRAY_FORMS` test, `TestStageAgreement`, `TestStageAgreementUnderExtglobOn`, the existing linearity tests and the unattended downgrade cases at the end of `run-destructive-guard.py` | pass | Integration |
| TS9 | (FR5, NFR1, AC9) Compare the case table at Base and at the integrated tip: the change is additions only (no entry removed, reordered or altered); the reproduction inputs of b0734a006de6f4d7 and a7c0d90ac3e44e5b (eval / let / alias forms included) are present as deny and that of f34ee27bc8c323b1 as ask; the deny count and the ask count are each at least their Base value | pass | Integration (scripted comparison) |
| TS10 | (NFR4) Every import in `em-workflow/hooks/destructive-guard.py`, and in any test file the feature changed, is a Python standard-library module | pass | Static |
| TS11 | (NFR5) The diff from Base to the integrated tip contains no change to `em-workflow/.claude-plugin/plugin.json` and no change to the em-workflow entry of `.claude-plugin/marketplace.json` | pass | Static |
| TS12 | (FR1, FR2, FR3) On the integrated tip, run the hook on (a) one TS3 declaration-group input and (b) one TS4 re-parsing-group input (T2 E-1 when TS4 has no entry), each with its command name split by one `{BS-NL}` | deny for both, the same verdict as the unsplit inputs | Integration |
| TS13 | (NFR1; rework round 1, task0004) Case-table entries: a here-document operator whose delimiter word is `$(x)`, a backquoted span, `$[1]`, `${x}`, `$'x'`, `'a'$'b'`, an unclosed quote, or a word containing `{BS-NL}`, followed by body lines holding a `<<WORD` or an unclosed quote that would hide a destructive line bash 5.3.9 executes; and `cat <<$(x)` followed only by harmless lines and the line `$(x)` | ask or deny for every hiding form (never allow); ask, with the unreadable-delimiter rule, for the harmless form | Unit (case table) |
| TS14 | (NFR1; rework round 1, task0004) Case-table entries: the reproduction input of every finding recorded as fixed in `reviews/round1.yaml` whose input contains a here-document operator (`<<` not part of `<<<`) | each entry's expected verdict; no entry whose destructive line bash 5.3.9 executes expects allow | Unit (case table) |
| TS15 | (FR4; rework round 1, task0005) In one process: the map `lex_shell()` returns for the TS5 input, its differing-prefix variant and T2 AC-4.7, fresh vs cached vs after lexing other texts; a repeat judgment and a judgment after pre-lexing every chunk, over those inputs and every case-table entry containing `@(` `!(` `+(` `*(` or `?(`; and the whole case table judged with the lexer cache disabled | identical extended-glob line starts and met fact on every map; identical verdict, met determination and unit count to a first judgment with an empty cache; every entry's expected verdict with the cache disabled | Unit (`tests/test_destructive_guard_extglob_units.py`) |

### Edge Cases (SPEC.md)
- [ ] Consecutive `{BS-NL}` inside a word before `=(` — case-table entry, same verdict as without them.
- [ ] `{BS-NL}` in the middle of `NAME[` or `+=` (`x{BS-NL}[0]=(`, `x+{BS-NL}=(`) — case-table entries, same verdict as without them.
- [ ] `{BS-NL}` in the middle of the command name of eval / let / alias and of the other declaration builtins — case-table entries, same verdict as the unsplit names; split-name variants of T2 E-1 and T2 E-9 deny.
- [ ] eval / let / alias with quoted arguments do not open an array — T2 E-15 stays allow.
- [ ] declare prefixed by builtin / command stays allow — T2 E-16 / E-17.
- [ ] Every new entry passes `TestStageAgreement`, and every new entry containing an extended-pattern parenthesis also passes `TestStageAgreementUnderExtglobOn` (TS8).

## Code Quality Verification
- Format: not configured (`format_command` is empty).
- Static analysis: not configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | TS1 input is denied | TS1 |
| AC2 | TS2 input is denied | TS2 |
| AC3 | Declaration-builtin `NAME[` reproduction input is denied | TS3 |
| AC4 | Measured eval / let / alias reproduction inputs are denied | TS4 |
| AC5 | Outer / inner eval sharing `x=(@` with an extglob switch yields ask | TS5 |
| AC6 | T2 E-1 and T2 E-9 stay deny | TS6 |
| AC7 | `SUBSCRIPT_ARRAY_FORMS` test passes unchanged | TS8 (and `tests/test_destructive_guard_lexer_agreement.py` unchanged from Base) |
| AC8 | T2 AC-4.7 stays allow | TS7 |
| AC9 | Every reproduction input added; deny and ask counts not lower | TS9 |
| AC10 | Both test commands pass | TS8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS12 |
| FR2 | task0002 | TS3, TS6, TS12 |
| FR3 | task0002 | TS4, TS6, TS8, TS12 |
| FR4 | task0003, task0005 | TS5, TS7, TS15 |
| FR5 | task0001, task0002, task0003 | TS9 |
| NFR1 | task0001, task0002, task0003, task0004, task0005 | TS6, TS7, TS9, TS13, TS14 |
| NFR2 | task0001, task0003, task0004, task0005 | TS8 |
| NFR3 | task0001, task0002, task0003, task0004, task0005 | TS8 |
| NFR4 | task0001, task0002, task0003, task0004, task0005 | TS10 |
| NFR5 | task0001, task0002, task0003, task0004, task0005 | TS11 |

## E2E Testing
No E2E framework beyond the case-table runner, which workflow.yaml registers
as `e2e_test_command` and which TS8 already runs. No separate E2E scenario.

## Manual Testing (E2E Not Possible)
- [ ] For each new deny entry whose expectation rests on bash executing the
  destructive line (TS1, TS2, TS3, TS4, TS13, TS14 forms), confirm on bash 5.3.9 in a
  scratch directory, with the destructive line replaced by a harmless marker
  command, that the marker runs. Never run the destructive line itself. When
  the available bash is not 5.3.9, record the version used.

## Performance / Security Verification (if applicable)
- NFR2: the existing linearity tests pass unchanged (TS8).
- TM-1: logical-word judgment of assignment words and builtin names — TS1 and
  TS2 deny, the line-continuation edge-case entries pass, and TS12 holds on
  the integrated tip.
- TM-2: declaration-builtin `NAME[` does not defer a pending here-document
  body — TS3 entries deny and T2 E-9 stays deny (TS6).
- TM-3: eval / let / alias handled as a separate group — TS4 entries deny,
  T2 E-1 stays deny (TS6), and the `SUBSCRIPT_ARRAY_FORMS` test passes
  unchanged (TS8).
- TM-4: extglob parse units identified by origin and position — TS5 yields
  ask, the differing-prefix variant entry yields the same verdict, T2 AC-4.7
  stays allow (TS7), and the unattended downgrade cases pass (TS8).
- TM-5: lexer work stays within `LEX_WORK_FACTOR` — the existing linearity
  tests pass unchanged (TS8).
- TM-6: a here-document operator whose delimiter word cannot be read fails
  closed — TS13 hiding forms are ask or deny, the harmless form is ask, and
  the round 1 here-document fixes hold (TS14).
- TM-7: the extglob parse-unit count and the verdict do not depend on the
  lexer cache or on which stage lexed a chunk first — TS15.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1–TS15) | 15 | 15 | 0 | 0 |
| Edge cases | 6 | 6 | 0 | 0 |
| Success criteria (AC1–AC10) | 10 | 10 | 0 | 0 |
| Performance (NFR2) | 1 | 1 | 0 | 0 |
| Security (TM-1–TM-7) | 7 | 7 | 0 | 0 |
| Manual (bash 5.3.9 execution confirmation) | 1 | 0 | 0 | 1 |
