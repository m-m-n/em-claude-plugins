# Verification Document: destructive-guard-heredoc-syntax-error

## Overview
**Feature**: destructive-guard-heredoc-syntax-error / **SPEC.md**: `feature-docs/destructive-guard-heredoc-syntax-error/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-heredoc-syntax-error/IMPLEMENTATION.md`

In the command examples of this document, `\n` stands for a newline. All
commands run from the repository root of the integration worktree.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook
  is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command (unittest suite): `python3 -m unittest discover -s tests`
- Command (case table): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  (`project.components.main.e2e_test_command`)
- Expected: both exit 0 with every test and every case passing
- Coverage target: no coverage measurement is configured; coverage is the
  scenario table below plus the requirements coverage table

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | SPEC TS1: `x=( <<EOF\ngit reset --hard HEAD\nEOF` and `x=( <<EOF\nrm -rf /home/sakura/valuable\nEOF` | deny for both | Case table |
| TS-2 | SPEC TS2: `x+=( <<EOF`, `x=(a b <<EOF`, `declare -a x=( <<EOF` and `x=(\na <<EOF`, each followed by a `git reset --hard HEAD` line and an `EOF` line; plus the other declaration builtins (`typeset -a`, `export`, `readonly`, `local` inside a function) and the line-end forms where a `"`, `$(`, `# "` or trailing `\` follows the operator on the discarded line (task0001 AC-2 / AC-2b) | deny for every form | Case table |
| TS-3 | SPEC TS3: `cat <<'A'; x=( <<B\ngit reset --hard HEAD\nA\nB` | deny | Case table |
| TS-4 | SPEC TS4: `x=( <<A\ncat <<'EOF'\ngit reset --hard HEAD\nEOF` | allow | Case table |
| TS-5 | SPEC TS5: `x=( $(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n) )`, the double-quoted form `x=( "$(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n)" )`, and `x=( <(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n) )` | allow for all three | Case table |
| TS-6 | SPEC TS6: `x=(a b); cat <<'EOF'\ngit reset --hard HEAD\nEOF` | allow | Case table |
| TS-7 | SPEC TS7: `x=( '<<EOF' )\nrm -rf /home/sakura/valuable\nEOF` | deny | Case table |
| TS-8 | SPEC TS8: the whole case table (pre-existing and new entries) and the unittest suite, including its lexer consistency check | every case and test passes; no pre-existing entry removed or rewritten; deny plus ask count not decreased | Regression |
| TS-9 | Review round 1 rework (task0002 AC-1, AC-2): `eval x=( <<EOF`, `let x=( <<EOF`, `alias x=( <<EOF`, `x["0"]=( <<EOF`, `x[$i]=( <<EOF`, `x['k']=( <<EOF`, `x[a b]=( <<EOF` and `x[0]+=( <<EOF`, each followed by a `git reset --hard HEAD` line and an `EOF` line; `x[0=( <<EOF\necho hi\nEOF`; and `let x=1`, `alias ll='ls -l'`, `x["k"]=v`, `x[$i]=v`, each followed by `; cat <<'EOF'\ngit reset --hard HEAD\nEOF` | deny for the eight array forms; ask for the unmatched subscript; allow for the four non-array forms | Case table |
| TS-10 | Review round 1 rework (task0002 AC-3): `x=([1<<2]=foo); cat <<'A'\ncat <<'true'\nA\ngit reset --hard HEAD\ntrue`, `x=([1<<2]=foo); cat <<'EOF'\ngit reset --hard HEAD\nEOF`, and `x=([1<<2]=foo <<EOF\ngit reset --hard HEAD\nEOF` | deny, allow, deny | Case table |
| TS-11 | Review round 1 rework (task0002 AC-4): `shopt -s extglob\nx=(P(foo)); cat <<'A'\ncat <<'true'\nA\ngit reset --hard HEAD\ntrue` for P in `@ ? * + !`; `x=(@(foo)); cat <<'A'\ngit reset --hard HEAD\nA`; and `x=( @(foo|bar) ); cat <<"EOF"\nhello\nEOF` | deny for the five prefix forms and the extglob-off form; allow for the benign form | Case table |
| TS-12 | Review round 1 rework (task0002 AC-5): `</dev/null x=( <<EOF`, `2>/dev/null x=( <<EOF`, `{fd}>/dev/null x=( <<EOF` and `x=( ( <<EOF`, each followed by a `git reset --hard HEAD` line and an `EOF` line; `x=( <<A ${\nx=( <<B\ngit reset --hard HEAD\nB`; and the labelled case pinning the redirect flag reset on a `(` / `((` push | deny for the five listed forms; the labelled case's stated verdict | Case table |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | `x=( <<EOF\ngit reset --hard HEAD\nEOF` is deny | TS-1 |
| AC2 | `x=( <<EOF\nrm -rf /home/sakura/valuable\nEOF` is deny | TS-1 |
| AC3 | the `x+=(`, element, `declare -a` and multi-line array forms are deny | TS-2 |
| AC4 | the same-line earlier operator form is deny | TS-3 |
| AC5 | a real heredoc after the array-error line stays allow | TS-4 |
| AC6 | heredocs in a command substitution inside an array, bare and double-quoted, stay allow | TS-5 |
| AC7 | a heredoc in a process substitution inside an array stays allow | TS-5 |
| AC8 | a heredoc after a closed array stays allow | TS-6 |
| AC9 | a quoted `<<EOF` inside an array is not an operator, so the following line is deny | TS-7 |
| AC10 | the AC1 to AC9 forms are in the case table | inspect the case table for the TS-1 to TS-7 entries; the case-table run passes them |
| AC11 | the deny plus ask count does not decrease; both test commands pass | TS-8 and the count check under Manual Testing |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-9, TS-10, TS-11, TS-12 (case table) |
| FR2 | task0001 | TS-3 (case table) |
| FR3 | task0001, task0002 | TS-4, TS-12 (case table) |
| FR4 | task0001 | TS-5, TS-6, TS-7 (case table) |
| FR5 | task0001, task0002 | TS-1 to TS-7 and TS-9 to TS-12 entries present in the case table |
| FR6 | task0001, task0002 | TS-8 and the count check under Manual Testing |
| NFR1 | task0001, task0002 | TS-8 (unittest lexer consistency check) and diff inspection: only lex_shell() / _lex_pass() change heredoc decisions |
| NFR2 | task0001, task0002 | TS-8 (runner's 10-second per-case limit across the whole table) |
| NFR3 | task0001, task0002 | TS-8 (no pre-existing case changes verdict), TS-10 and TS-11 (forms the round-1 auto-fix loop moved from deny to allow are deny again) |
| NFR4 | task0001, task0002 | TS-8 (both commands run in the same change) |

## E2E Testing
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case, including the TS-1 to TS-7 and TS-9 to TS-12 entries

## Manual Testing (E2E Not Possible)
- [ ] Compare `em-workflow/hooks/tests/destructive-guard-cases.json` against the integration base: the diff only appends entries, and the number of deny plus ask entries does not decrease (AC11, FR6)

## Performance / Security Verification (if applicable)
- NFR2: every case finishes within the runner's 10-second per-case limit; an input exceeding the lexer work bound still returns the scan-budget ask
- TM-1: lex_shell() / _lex_pass() do not register `<<` / `<<-` at direct position inside an array compound assignment, including arrays after `eval` / `let` / `alias` and arrays whose name carries a subscript — checked by TS-1, TS-2, TS-9 and TS-12 returning deny
- TM-2: no heredoc operator registered on the discarded line takes a body — checked by TS-3 returning deny
- TM-3: the case table only gains entries and every pre-existing case keeps its verdict — checked by TS-8 and the count check under Manual Testing
- TM-4: suppression only at direct position, with all lexical context cleared at the end of the discarded line — checked by TS-4, TS-5 and TS-6 returning allow
- TM-5: tracking and cancellation stay within the single pass and the work bound — checked by the per-case time limit over the whole table (TS-8) and the scan-budget ask on an over-bound input

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 12 | 0 | 0 |
| Success criteria (AC1 to AC11) | 11 | 10 | 0 | 1 |
| Requirements coverage (FR1 to FR6, NFR1 to NFR4) | 10 | 10 | 0 | 0 |
| E2E | 1 | 0 | 1 | 0 |
| Manual | 1 | 0 | 0 | 1 |
| Performance / Security (NFR2, TM-1 to TM-5) | 6 | 6 | 0 | 0 |
