# Verification Document: destructive-guard-lexer-round2-deferred

## Overview
**Feature**: destructive-guard-lexer-round2-deferred / **SPEC.md**: `feature-docs/destructive-guard-lexer-round2-deferred/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-lexer-round2-deferred/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/destructive-guard-lexer-round2-deferred/THREAT-MODEL.md`

This document covers the integrated verification after all nine tasks are
merged (task0006 to task0008 come from review round 1, task0009 from verify
round 1). Task-level acceptance criteria live in `tasks/task0001.md` to
`tasks/task0009.md`.

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty; the hook is a Python script with no build step).
- Expected: not applicable.

## Test Verification
- Command (project test suite): `python3 -m unittest discover -s tests`
- Command (lexer agreement suite): `python3 -m unittest tests.test_destructive_guard_lexer_agreement`
- Command (case table runner): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: every command exits 0 with no failure or error.
- Coverage target: not measured (no coverage tooling is configured for this project); completeness is judged by the scenarios below.

### Test Scenarios from SPEC.md
Inputs use the case table's JSON string notation (`\n` newline, `\r`
carriage return, `\u000b` vertical tab, ` ` line separator, `\\`
backslash, `\t` tab). RM is `rm -rf /home/sakura/valuable`. "Both modes"
means without `CLAUDE_BATCH` and with `CLAUDE_BATCH=1`.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The six FR1 forms: `a[1\n]=x\ncat <<E\n'\nE\nRM\n'`, its `\"` and `${` (closed by `}`) versions, the `a[1\n]=x; cat <<E` version, `a[$(echo 1\n)]=x\ncat <<E\n'\nE\nRM\n'` and `a[b[1\n]]=x\ncat <<E\n'\nE\nRM\n'` (SPEC TS1, F1) | deny in both modes; one here-document operator, delimiter `E`, unquoted, body = the line after the operator's line, close line `E`; the array-subscript region spans the newline; no region covers the RM line; no tail start | Unit + case runner |
| TS-2 | `cat <<E${x}\n${\nE${x}\nRM\n}` and its `$((` / `$[` / `((` / `case x in` versions (closed by `))` / `]` / `))` / `esac`) (SPEC TS2) | deny in both modes; no here-document operator; tail start at the `<<`; no parameter-expansion, arithmetic-expansion, bracket-arithmetic, arithmetic-command, quote or comment region starts at or after it; the refused openers are in UNOPENED; in the `case` form the RM statement's shaped words begin with `rm` | Unit + case runner |
| TS-3 | `cat <<EOF\r; RM\nEOF` and its `\u000b` / ` ` versions, `cat <<END \r; RM\nEND`, `cat <<END\nx\rEND\n# $(RM)\nEND`, `cat <<E\rX\nE\n# $(RM)\nE\rX`, `cat <<EOF\r\nx\r\nEOF\r\nRM\nEOF` (SPEC TS3) | deny in both modes; each delimiter value keeps its `\r` / `\u000b` / ` `; line starts only at offset 0 and after each `\n`; the RM text or the `# $(RM)` line falls where bash puts it (outside every body, or inside a body whose substitution is reported) | Unit + case runner |
| TS-4 | `a\\\n[1<<2]=x\nRM\n2]=x`, `ab\\\nc[1<<2]=x\nRM\n2]=x`, and the forms with the continuation inside the subscript, before `]` and before `=` (SPEC TS4, F4) | deny in both modes; no here-document operator; for the first two an array-subscript region opens at the `[`; `a\\\n[1<<2\nRM` is ask without `CLAUDE_BATCH` and deny with it; `declare a\\\n[1<<2]=x\nbody\n2]=x` reads like `declare a[1<<2]=x\nbody\n2]=x` | Unit + case runner |
| TS-5 | `cat <<END\nfoo\\\nEND\n# $(RM)\nEND` and `cat <<-END\nfoo\\\n\tEND\n# $(RM)\nEND` (SPEC TS5) | deny in both modes; the body runs to the last line and holds the `# $(RM)` line; the here-document body extraction reports that command substitution | Unit + case runner |
| TS-6 | `echo x\r# ; RM` (SPEC TS6) | deny in both modes; no comment region; the RM statement's shaped words begin with `rm`; the masked-view tokenizer splits `a\rb c` into `a\rb` and `c` in its layout and plain-word modes | Unit + case runner |
| TS-7 | `echo ${ RM; }`, `echo ${\|RM; }`, `echo ${\nRM\n}`, `cat <<E\n${ RM; }\nE` (SPEC TS7) | deny in both modes; one closed `brace-command-substitution` region per form (a reported body substitution for the here-document form), inner text = the characters between the opener and the closing `}`; no parameter-expansion region, no UNOPENED offset, no tail start | Unit + case runner |
| TS-8 | Fixed lexical expectations for every FR1 to FR7 form (SPEC TS8, FR11) | the agreement suite pins heredocs, the regions each task owns and the tail start per form, and the decision in both modes; every map is identical after a lexer cache clear (NFR4) | Unit |
| TS-9 | k = 200 and k = 400 repetitions of every FR1 to FR7 form, plus a name with 200 / 400 continuation pairs, a body of 200 / 400 continued lines, `cat` with 200 / 400 copies of ` <<'\\' <<B` followed by as many backslash-only lines, and `${ ` repeated 20000 times (SPEC TS9) | 400 work ≤ 2.5 × 200 work + 100 and ≤ `LEX_WORK_FACTOR` × length + 1024 | Unit (linearity) |
| TS-10 | Whole existing suites (base: 769 case-table entries) plus everything added (SPEC TS10) | all pass; positional pins (`ROUND2_BASE_CASE_COUNT`, `SUBSCRIPT_CASE_FLOOR`, the cases[574:604] and cases[604:627] slices) unchanged; existing allow cases stay allow; existing linearity, budget, determinism and module-contract tests pass (the rewrites named in task0001 and task0005 keep their purpose) | Regression |
| TS-11 | One tail gate (SPEC AC4, FR8) | a source-inspection test finds every tail-start / tail-source comparison made for an opener decision inside the gate function only, and every site SPEC FR8 lists calls it; every pre-existing tail decision is unchanged, including the whole-text-restart map equivalence of the non-adjacent-close re-reading | Unit |
| TS-12 | Case placement and order (SPEC AC2, AC3, FR9, FR10, FR11) | no label at index < 769 carries 5753be9288beab27, 52bfa0f59d1ea852, e959ba60bde865a4, e25427e2a8b1dddf, 2b52be5874de85f4, aa735aa95be36542 or 1fcae1f76f2a20f0; every new case sits at index ≥ 769 and its label begins with its stable_id and `round2-deferred`; the first 769 entries are unchanged; in each task's history the case-adding commit precedes its hook-changing commits | Unit + history check |
| TS-13 | ~60 KB inputs: the unclosed-opener bulk forms (`${ ` nested command forms, `${x`, `$((`, `$[`, `((`, `$'`, the mixed unit) followed by RM (SPEC NFR2, F7) | a decision other than allow, within the 10-second hook bound | Integration (timed hook run) |
| TS-14 | Work bound exceeded: `${ ` repeated 20000 times followed by `\nRM\n`, and the existing `(( ;` budget input (SPEC NFR3) | ask or deny without `CLAUDE_BATCH`, deny with it; never allow | Unit (in-process hook run) |
| TS-15 | `\r` and other separators as word characters (SPEC F3/F6, F3): `cat <<EOF\r\nhi\r\nEOF\r\n`, `echo hi\r\necho done\r\n`, `echo hi\r`, `RM\r`, `git reset --hard\r`; delimiter words holding `\x0c`, `\x1c`, `\x1d`, `\x1e`, `\x85`, U+2029; `echo a\r#b` vs `echo a\r #b` | the first three allow in both modes; `RM\r` and `git reset --hard\r` deny in both modes; each delimiter value keeps its character; `echo a\r#b` has no comment region, `echo a\r #b` has one | Unit + case runner |
| TS-16 | Continuation joining edges (SPEC F5 and planner-found forms): `cat <<END\nfoo\\\\\nEND\nRM\nEND`, `cat <<'END'\nfoo\\\nEND\nRM\nEND`, `cat <<END\nfoo\\\nbar\nEND\necho done`, `cat <<END\nfoo\nEN\\\nD\nRM\nEND`, `cat <<-END\nfoo\n\tEN\\\nD\nRM\nEND`, `cat <<'A\\' <<B\nA\\\nB\nRM\nB` | the first two close at the third line and deny; the third is allow; the joined close lines `EN\\\nD` close the body at the `D` line and the RM line is outside every body (deny); in the last form the second body's first line `B` closes it (deny); all in both modes | Unit (+ case runner for the forms in the case table) |
| TS-17 | Command-form edges (SPEC F7): `echo ${ RM` (unclosed), `echo ${ echo }`, `echo ${x} ${x:-y} ${#x}`, `cat <<'E'\n${ RM; }\nE`, `echo "${ RM; }"`, `echo ${x:-${ RM; }}`, `echo ${ { RM; }; }`, and the existing entries labelled `heredoc-syntax-error E-12`, `T2 AC-5.5`, `T2 AC-5.7` | the unclosed form runs to the end, is inspected and denies; `}` as an argument closes nothing; parameter forms stay parameter-expansion regions and allow; the quoted body stays literal and allows; the double-quoted, nested and inner-brace-group forms deny; the three existing discarded-line entries stay deny, the command form closing at the discarded line's newline | Unit + case runner |
| TS-18 | Tail edges (SPEC F2, D4): `cat <<E${x}\necho $(RM)`, ``cat <<E${x}\necho `RM` ``, `cat <<E${x}\necho ${ RM; }`, `case x in x) cat <<E${x};; esac\nRM`, `cat <<E${x}\n"a\n$'b\n$"c\nRM\n"` | `$(`, backticks and the command form open after the tail source and deny; the case construct opened before the tail keeps its shaping and the RM statement's shaped words begin with `rm` (deny); the quote-character form has no region and its `${` is in UNOPENED (deny); all in both modes | Unit |
| TS-19 | Backtick extent (review round 1 rework, task0006): the ten `R1.BT` cases (``echo `rm -rf src #` ``, ``echo `true #`; git reset --hard``, ``echo `echo \"`; echo `rm -rf src` ``, the `${x` / `$((x` / `$[x` / `a[x` forms inside `${ ` inside a backtick, ``` `${ echo '\\` ignored'; }`git reset --hard ```, ``` `\"${ echo # `git reset --hard ```, ``echo `date # note`; echo done``); ``echo `O x`; RM`` for O in `#`, `'`, `"`, `$'`, `${`, `${ `, `$((`, `$[`, `$(`, `a[`, `@(`, bare, in double quotes and in `$(`; escaped and even-backslash backticks; the entry labelled `heredoc-syntax-error E-7` | the nine reproductions and every `O` form deny, ``echo `date # note`; echo done`` and E-7 allow, in both modes; each backtick region is closed right after the next unescaped backtick and every region inside it ends at or before it; work linear (400 ≤ 2.5 × 200 + 100) | Unit + case runner |
| TS-20 | Line continuations (review round 1 rework, task0007): the nine `R1.LC` cases (`echo $\\\n{ git reset --hard; }` bare, in double quotes and in an unquoted body; `echo ${\|\\\nRM; }`, `echo ${ \\\nRM; }`, `\\\nRM`, `r\\\nm -rf /home/sakura/valuable`, `echo $(\\\nRM)`, `echo a\\\nb 'c\\\nd'`); `$\\\n(`, `$(\\\n(`, `$\\\n[`, `$\\\n{x}`; the tokenizer over `r\\\nm -rf x` and `a 'b\\\nc'` | the eight reproductions deny and the last allow, in both modes; each `$\\\n` opener reports its region kind starting at the `$` (the tail gate unchanged); the tokenizer yields `rm` spanning offsets 0 to 4 and keeps the single-quoted pair; work linear | Unit + case runner |
| TS-21 | Trailing `\r` on delete targets (review round 1 rework, task0008): the five `R1.CR` cases (`rm -rf build\\\r`, `rm -rf build\r`, `rm -rf \"build\r\"\n'`, `rm -rf ./node_modules\r\n`, `rm -rf /tmp/x\r`); every build-artifact name with an unquoted, escaped and quoted trailing `\r`; the agreement-test matching form `rm -rf ./build\r` | the first four deny and `rm -rf /tmp/x\r` allow, in both modes; each build-artifact form has the verdict of the same command with `\r` replaced by `x`; `rm -rf ./build\r` is deny in both modes; `RM\r`, `git reset --hard\r` stay deny and `echo hi\r` stays allow | Unit + case runner |
| TS-22 | Doubled-length nested unclosed forms (verify round 1 rework, task0009): `${ ` repeated 40000 times followed by `\nRM\n` (~120 KB), and the mixed unit `${ $(( $[ (( $' ` repeated to ~120 KB followed by `\nRM\n`; `echo ${ RM`, `echo ${ echo x ${ RM`, `${ ${ ${ RM` | one hook evaluation of each ~120 KB input finishes within 20 seconds, the first with ask or deny without `CLAUDE_BATCH` and deny with it, the second with a decision other than allow in both modes; the three short forms deny in both modes (every nested unclosed form's content is still inspected); the TS-13 and TS-14 tests pass with their 10-second bound unchanged in two consecutive suite runs | Integration (timed hook run) |

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty).
- Static analysis: none configured. `TestModuleContract` checks that the hook and the agreement test import only the standard library and that the lexer reads no file and evaluates nothing (NFR5).

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Every FR1 to FR7 reproduction denies in normal runs and with `CLAUDE_BATCH=1` | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7 |
| AC2 | Each reproduction is a deny case at the end of the case table, added in a commit before the fix, its label beginning with its stable_id | TS-12 (history: `git log` of the integration branch shows, per task, the case-table commit before the hook commits) |
| AC3 | No existing deny / ask case removed, order unchanged | TS-10, TS-12; `git diff` of the case table against the feature base shows additions only after the 769th entry |
| AC4 | The tail decision is one function and every opener site uses it | TS-11 |
| AC5 | Both suites pass | TS-10 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1, TS-8 |
| FR2 | task0001 | TS-2, TS-8, TS-18 |
| FR3 | task0003 | TS-3, TS-8, TS-15 |
| FR4 | task0002 | TS-4, TS-8 |
| FR5 | task0003 | TS-5, TS-8, TS-16 |
| FR6 | task0004, task0008 | TS-6, TS-8, TS-15, TS-21 |
| FR7 | task0005, task0006, task0007, task0009 | TS-7, TS-8, TS-17, TS-19, TS-20, TS-22 |
| FR8 | task0001 | TS-11, TS-18 |
| FR9 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-12, TS-19, TS-20, TS-21 |
| FR10 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS-10, TS-12 |
| FR11 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008 | TS-8, TS-12 |
| NFR1 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0009 | TS-9, TS-19, TS-20, TS-22 |
| NFR2 | task0005, task0009 | TS-13, TS-22 |
| NFR3 | task0005, task0009 | TS-14, TS-22 |
| NFR4 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS-8 |
| NFR5 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS-10 |
| NFR6 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS-15, TS-16, TS-17, TS-18, TS-19, TS-20, TS-21, TS-22 |
| NFR7 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008, task0009 | TS-10, TS-15, TS-17 |

## E2E Testing
The project's E2E command (workflow.yaml `e2e_test_command`) runs every
case-table entry through the hook's stdin / stdout contract.
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case, including the blocks the five tasks appended.

## Manual Testing (E2E Not Possible)
- [ ] bash 5.3 spot check: for each SPEC FR1 to FR7 deny form with `rm` replaced by `echo`, bash 5.3 executes the replaced line (or, for the unclosed `${ ` form, reports a syntax error and runs nothing), so each deny case matches bash; the planner-found forms of task0003 and the extra command-form contexts of task0005 are listed in the task reports with their bash 5.3 outcome, and any not confirmed is pinned in the agreement suite only.

## Performance / Security Verification (if applicable)
- NFR1: `lex_shell()` work ≤ `LEX_WORK_FACTOR` × input length + 1024 for every FR1 to FR7 form and the adversarial inputs; doubling the input keeps work ≤ 2.5 × + 100 (TS-9).
- NFR2: one hook evaluation of ~60 KB, including nested `${ `, finishes within 10 seconds with a decision other than allow (TS-13); the doubled ~120 KB nested forms finish within 20 seconds, so the cost grows in proportion to the length (TS-22).
- NFR3: exceeding the work or scan bound gives ask (deny in batch), never allow (TS-14).
- TM-1: after a `<<` whose delimiter word cannot be read, no parameter-form `${`, `$((`, `$[`, `((` or case construct opens, and every tail decision comes from one gate — checked by TS-2 (lexical expectation plus deny in both modes), TS-11 (single gate, unchanged existing decisions) and TS-18 (`$(`, backticks and the command form still open; the pre-tail case construct keeps its shaping).
- TM-2: a `<<` after a subscript closed on a later line is a real operator whose body quotes and `${` stay inside the body — checked by TS-1.
- TM-3: a `NAME[` whose name holds line continuations opens a subscript, so its `<<` is no operator and no whole-word delimiter swallows the following lines — checked by TS-4.
- TM-4: delimiter words end only at metacharacters and lines only at `\n`, so bodies cover exactly the lines bash reads — checked by TS-3 and TS-15.
- TM-5: unquoted close lines are matched on continuation-joined lines, with the first-line rule, so a body neither closes early nor late — checked by TS-5 and TS-16.
- TM-6: `\r` is a word character in the lexer and the tokenizer, so `#` after it opens no comment, and a trailing `\r` keeps existing deny verdicts and never makes a delete target safe — checked by TS-6, TS-15 and TS-21.
- TM-7: the content of `${ cmd; }` / `${| cmd; }`, closed or not, is inspected as commands at every level, a backtick substitution ends at the next unescaped backtick, and line continuations neither hide an opener nor split a command word — checked by TS-7, TS-17, TS-19 and TS-20.
- TM-8: the new readings keep the lexer linear and every bound overflow is ask (deny in batch), never allow or a timeout — checked by TS-9, TS-13, TS-14 and TS-22.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-22) | 22 | 22 | 0 | 0 |
| SPEC success criteria (AC1 to AC5) | 5 | 5 | 0 | 0 |
| E2E (case table runner) | 1 | 0 | 1 | 0 |
| Manual (bash 5.3 spot check) | 1 | 0 | 0 | 1 |
| Performance (NFR1 to NFR3) | 3 | 3 | 0 | 0 |
| Security (TM-1 to TM-8) | 8 | 8 | 0 | 0 |
