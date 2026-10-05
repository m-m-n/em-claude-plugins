# Verification Document: destructive-guard-unified-lexer

## Overview

**Feature**: destructive-guard-unified-lexer / **SPEC.md**: `feature-docs/destructive-guard-unified-lexer/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-unified-lexer/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/destructive-guard-unified-lexer/THREAT-MODEL.md`

## Build Verification

- Command: none (workflow.yaml project.components.main.build_command is empty; Python, no build step)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests` (workflow.yaml test_command)
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py` (workflow.yaml e2e_test_command; the hook case suite)
- Coverage target: not measured (no coverage tooling; NFR2 keeps tests on the standard library)

### Test Scenarios from SPEC.md

TS-1 to TS-8 come from SPEC.md. TS-9 to TS-20 are added by the planner: TS-9 to TS-12 so that NFR1, NFR2, NFR4 and the unclosed-opener side of NFR3 each have a verifying test, and TS-13 to TS-20 for the create-plan plan review answers (PA1, PA4, Q3-procsub, Q3-single-quote-candidates, Q3-position-map, Q3-agreement-risk). Case numbers below refer to task0001's "Cases to append" list.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | SPEC AC-1 forms 1-11 are in destructive-guard-cases.json as deny cases (FR1, FR2, FR3, FR11) | The case runner reports deny for each | Unit (case suite) |
| TS-2 | SPEC AC-2 form `echo $((1<<2)); cat <<'EOF'\nrm -rf /tmp/zz\nEOF` is an allow case (FR3, FR11) | allow | Unit (case suite) |
| TS-3 | SPEC AC-7 forms 1-5 are deny cases (FR1, FR3, FR4, FR5, FR11) | deny for each | Unit (case suite) |
| TS-4 | The round-2 guard cases (cases.json 592-596: `$$'`, `${x:-a #}`, `$${`, `rm -rf /tmp/safe$'\t'`, `"${x:-a(b}"`) keep their expected verdicts (FR7, FR12) | pass | Unit (case suite) |
| TS-5 | The agreement test over every cases.json command, the AC-1 / AC-7 attack forms, the benign controls and the fixed-expectation forms (FR6, FR7, FR8, FR9, FR10) | Stage agreement properties (a)-(f) of task0001 hold: quote ranges, substitution spans, statement boundaries, heredoc operator positions, Tok provenance and inspection values agree; no inspection value contains the mask character | Unit |
| TS-6 | Run `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` (FR12) | Both pass in full | Integration |
| TS-7 | The existing ~60KB performance case (`echo ' + $(` x30000 ` + ' ; rm -rf <target>`) (NFR3) | deny within the 10-second limit | Performance |
| TS-8 | The SPEC edge forms (double-quoted `$'`, `$"..."`, `$$'...'` / `$?'...'`, `\\` and `\'` in `$'...'`, `${#x}` / `${x#pat}` / `$#`, `${x:-"}"}`, `${x:-${y}}`, `$((...))` vs `$( (...) )`, `( (cmd) )`, `a[1] <<EOF` outside arithmetic, `<<<`, a real heredoc inside a substitution, several contexts on one line and contexts spanning lines) are read as bash reads them (FR1, FR2, FR3, FR5, FR8) | Each form's hand-written expected regions and expected verdict (allow) hold | Unit |
| TS-9 | (planner-added, NFR1) Every agreement-test command is lexed and judged twice | Identical lexer map and identical decision both times | Unit |
| TS-10 | (planner-added, NFR2) The imports of destructive-guard.py and of the new test file | Only Python standard library modules | Unit (import check in the agreement test) |
| TS-11 | (planner-added, NFR4) Changed paths between workflow.yaml implement.base_commit and the integration HEAD | Only `em-workflow/hooks/destructive-guard.py`, `em-workflow/hooks/tests/destructive-guard-cases.json`, `tests/test_destructive_guard_lexer_agreement.py` and feature-docs / test-docs of this feature; hooks.json, plugin.json and marketplace.json unchanged | Integration (scripted diff) |
| TS-12 | (planner-added, NFR3) A roughly 60KB input of repeated unclosed openers (`${`, `$((`, `$[`, `((`, `$'`) followed by a destructive statement, run through the hook | A non-allow decision within 10 seconds | Performance |
| TS-13 | (planner-added, Q3-procsub) Process-substitution cases 18-21 (`cat <((rm -rf /home/sakura/valuable))`, `cat <(rm -rf /home/sakura/valuable)`, `cat <(((1<<2)))`, `cat <(((1<<2)))` followed by a destructive line) and the existing `tee >(bash) <<'EOF'` case (FR3, FR4, FR11) | deny, deny, allow, deny; the existing case keeps deny | Unit (case suite) |
| TS-14 | (planner-added, PA4) Grammar-state cases 22-28: bare `((` after `!`, `time -p`, a case-pattern `)`, a function-definition head and `coproc`, and `$((` inside double quotes and as a redirection target, each followed by a destructive line (FR3, FR11) | deny for each | Unit (case suite) |
| TS-15 | (planner-added, Q3-agreement-risk) Re-read-tail cases 29-30: a `#` and a `<<` after an unclosed `${` (FR5, FR11, SPEC A3) | deny for each | Unit (case suite) |
| TS-16 | (planner-added, PA4, Q3-agreement-risk) The agreement test's added fixed-expectation forms: every command-position kind, the non-arithmetic `((` forms, the process-substitution forms, the expansion-position forms and every unclosed-opener kind, as listed in task0001 Test Notes (FR1, FR2, FR3, FR5, FR10) | Each form's hand-written expected regions and expected verdict hold, so a misread shared by every layer still fails | Unit |
| TS-17 | (planner-added, Q3-position-map) Position-map checks over every agreement-test command, including a chunk whose marker is longer than its substitution and a chunk with a removed heredoc body (FR8) | Order kept; exact position and character round trips within unchanged segments; each removed body and marked substitution maps whole range to whole counterpart | Unit |
| TS-18 | (planner-added, Q3-single-quote-candidates) Broad substitution search from lexer output: for every agreement-test command, honor_single_quotes=False spans equal the default spans plus the lexer's single-quote candidates; the candidate fixtures (balancing close, first-close rule, no close, backtick, unclosed backtick, inside an ANSI-C quote) hold (FR9) | Equal span sets; fixture ranges and recorded verdicts hold; the ~60KB case still denies within 10 seconds | Unit |
| TS-19 | (planner-added, PA1) Commit order between workflow.yaml implement.base_commit and the integration HEAD (FR11) | The earliest commit that changes the cases file changes neither destructive-guard.py nor the agreement test, and its message lists the failing new cases; the commit that first adds the agreement test descends from it and does not change destructive-guard.py; every commit that changes destructive-guard.py descends from both | Integration (scripted git history check) |
| TS-20 | (planner-added, PA1) Failure confirmation: copy destructive-guard.py as of implement.base_commit to a temporary path and run the case runner on that copy with the final cases file (the alternate-copy invocation in .claude/rules/hook-tests.md) (FR11) | FAIL for SPEC AC-1 forms 1-11 and for case 18; every case present at implement.base_commit passes | Integration |

## Code Quality Verification

- Format: not configured (workflow.yaml format_command is empty)
- Static analysis: not configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | SPEC AC-1 forms 1-11 deny and are deny cases in cases.json | TS-1 |
| AC-2 | SPEC AC-2 form allows and is an allow case | TS-2 |
| AC-3 | cases.json 592-596 keep their expected verdicts | TS-4 |
| AC-4 | The existing 574 cases and the unattended-demotion case keep their verdicts; no deny / ask case removed | TS-6, plus a diff of cases.json against implement.base_commit showing only appended entries |
| AC-5 | Both suites pass, each case within 10 seconds | TS-6, TS-7 |
| AC-6 | The FR10 agreement test passes | TS-5 |
| AC-7 | SPEC AC-7 forms 1-5 deny and are deny cases | TS-3 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3, TS-8, TS-16 |
| FR2 | task0001 | TS-1, TS-8, TS-16 |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-8, TS-13, TS-14, TS-16 |
| FR4 | task0001 | TS-3, TS-13 |
| FR5 | task0001 | TS-3, TS-8, TS-15, TS-16 |
| FR6 | task0001 | TS-5; manual review below |
| FR7 | task0001 | TS-4, TS-5 |
| FR8 | task0001 | TS-5, TS-8, TS-17 |
| FR9 | task0001 | TS-5, TS-18 |
| FR10 | task0001 | TS-5, TS-16 |
| FR11 | task0001 | TS-1, TS-2, TS-3, TS-13, TS-14, TS-15, TS-19, TS-20 |
| FR12 | task0001 | TS-4, TS-6 |
| NFR1 | task0001 | TS-9; manual review below |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-7, TS-12 |
| NFR4 | task0001 | TS-11 |

## E2E Testing

The hook case suite (workflow.yaml e2e_test_command) drives the hook through its stdin JSON / stdout contract.

- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case, each within 10 seconds (TS-1, TS-2, TS-3, TS-4, TS-6, TS-7, TS-13, TS-14, TS-15)

## Manual Testing (E2E Not Possible)

- [ ] Code review of destructive-guard.py (FR6, NFR1; the resolution condition of 7e700e9f9906edc7). _OperatorContext and _blank_comments() are gone. No function other than the unified lexer classifies characters as quote, comment, expansion, arithmetic, substitution (process substitution included) or heredoc operator, or decides command position or single-quote substitution candidates; scan_structure(), _lex_layout() and tokens() take those judgments from it. tokens() never passes raw text to a comment-stripping tokenizer. The lexer reads no file and evaluates nothing.

## Performance / Security Verification

- NFR3: the ~60KB performance case returns deny within 10 seconds (TS-7). The unclosed-opener input returns a non-allow decision within 10 seconds (TS-12).
- TM-1: The unified lexer reads ANSI-C, parameter-expansion and arithmetic contexts as bash does, recognizes a bare `((` only at real command positions, and never lets the re-read tail after an unclosed opener drop text as a comment or heredoc body. Checked by TS-1, TS-3, TS-14 and TS-15 (attack forms deny) and TS-8 and TS-16 (hand-written regions and verdicts, so a misread every layer shares still fails).
- TM-2: `$(...)` and backticks inside `${...}` and arithmetic are still extracted and scanned, and the broad search keeps its single-quote reach through the lexer's candidates. Checked by TS-3 (SPEC AC-7 forms 2 and 3 deny), TS-5 (spans agree with the lexer's substitution regions) and TS-18 (broad spans equal default spans plus candidates).
- TM-3: Heredoc body lines change no lexer state, each body belongs to the statement holding its operator, and positions map between the three coordinates without assuming character-exact correspondence across markers. Checked by TS-1 (SPEC AC-1 form 1 deny), TS-2 (real heredoc after arithmetic stays allow), TS-5 (heredoc operator positions agree) and TS-17 (position-map contract).
- TM-4: Inspection values are restored from the original text, so the mask character never reaches a value, and Tok provenance follows the original input. Checked by TS-5 (no mask character; values equal the shlex reading where nothing is masked) and TS-4 (`rm -rf /tmp/safe$'\t'` keeps its verdict).
- TM-5: Every existing expectation, allow cases included, holds after the lexer change. Checked by TS-6 (full suite), TS-4 and TS-20 (every pre-existing case still passes on the base hook, so the cases file was only appended).
- TM-6: Lexing stays linear, including settling unclosed openers and computing single-quote candidates, and an over-budget input falls back to the existing ask decision. Checked by TS-7, TS-12 and TS-18 (decisions within 10 seconds, never allow).
- TM-7: A process-substitution opener is consumed once, its body starts a new command position, and its body is extracted and scanned while the host statement keeps its process-substitution evidence. Checked by TS-13 (`cat <((rm -rf /home/sakura/valuable))` deny, `cat <(((1<<2)))` allow, `tee >(bash) <<'EOF'` still deny) and TS-16 (hand-written process-substitution regions).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-20) | 20 | 20 | 0 | 0 |
| Success criteria (AC-1 to AC-7) | 7 | 7 | 0 | 0 |
| Functional / non-functional requirements (FR1-FR12, NFR1-NFR4) | 16 | 16 | 0 | 2 (FR6, NFR1 review) |
| E2E (hook case suite) | 1 | 0 | 1 | 0 |
| Manual review | 1 | 0 | 0 | 1 |
| Performance (NFR3) | 2 | 2 | 0 | 0 |
| Security (TM-1 to TM-7) | 7 | 7 | 0 | 0 |
