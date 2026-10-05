# Verification Document: codex-guard-parser-fixes

## Overview
- **Feature**: codex-guard-parser-fixes
- **SPEC.md**: `feature-docs/codex-guard-parser-fixes/SPEC.md`
- **IMPLEMENTATION.md**: `feature-docs/codex-guard-parser-fixes/IMPLEMENTATION.md`
- **THREAT-MODEL.md**: `feature-docs/codex-guard-parser-fixes/THREAT-MODEL.md`

Verdict vocabulary: `deny` means the guard prints its deny JSON. `silent`
means it prints nothing and exits 0. "Both copies" means
`em-workflow/scripts/codex-hook-interactive-guard.py` and
`em-review/scripts/codex-hook-interactive-guard.py`. In command lists, `\n`
outside single quotes is a newline character. Inside the single-quoted
`printf` argument it is the two literal characters backslash and `n`.

## Build Verification
- Command: none. `build_command` is empty for both components (`repo-tests`, `plugin-invariants`).
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: every command exits 0 with no test failures or errors
- Coverage target: not measured (no coverage tooling is configured). Scenario coverage is tracked by the TS IDs below. Each TS-1 to TS-10 command is a `CASES` row run against both copies.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Shell `-c` deny forms (SPEC TS1): `bash -cx 'python3 -i'`, `bash -ce 'python3 -i'`, `bash -c -- 'python3 -i'`, `bash -c - 'python3 -i'`, `bash -ci 'python3'`, `bash -c -i 'python3'`, `bash -co pipefail 'python3 -i'`, `bash -c -o pipefail 'python3 -i'`, `sh -cx 'python3'` | `deny` from both copies | Unit |
| TS-2 | Shell `-c` silent forms (SPEC TS2): `bash -c 'echo hi' -i`, `bash -cx 'echo hi'`, `bash -c -- 'echo hi'`, `bash -cx`, `echo \| bash -cx python3`, `bash -cx 'python3' < f`; existing `python3 -ci` row | `silent` from both copies | Unit |
| TS-3 | Shell information options denied (SPEC TS3): `bash -h`, `sh -h`, `zsh -h`, `zsh -V`, `dash -V`, `bash -V` | `deny` from both copies | Unit |
| TS-4 | Non-shell information options kept (SPEC TS4): existing `python3 -h`, `python3 -V`, `python3 -VV`, `node -v`, `perl -v`, `bash --version` | `silent` from both copies | Unit |
| TS-5 | Substitution inside double quotes (SPEC TS5): `echo "$(echo "; python3 -i")"`, `` echo "`echo x`; python3 -i" ``, `echo "$((1+2)); python3 -i"`, `echo "$(python3 -i)"`, unclosed `echo "$(echo "` | `silent` from both copies | Unit |
| TS-6 | Launch outside the quotes (SPEC TS6): `echo "$(echo x)"; python3 -i` | `deny` from both copies | Unit |
| TS-7 | Connected groups (SPEC TS7): `(python3) < /dev/null`, `printf 'print(1)\n' \| (echo ignored; python3)`, `(python3) 0< f`, `(python3) <<EOF\nprint(1)\nEOF`, `( (python3) ) < f`, `{ python3; } < /dev/null`, `printf 'print(1)\n' \| { echo ignored; python3; }` | `silent` from both copies | Unit |
| TS-8 | Unconnected or `-i` groups (SPEC TS8): `(python3) 2>/dev/null`, `(python3) > out`, `(python3) \| cat`, `(python3 -i) < /dev/null`, `echo x \| (python3 -i)`, `{ python3; } 2>/dev/null`, `{ python3; }` | `deny` from both copies | Unit |
| TS-9 | Multi-line pipe (SPEC TS9): `echo x \|\npython3`, `echo x \|\n\npython3`, `echo x \| # c\npython3`, `cat <<EOF \|\nbody\nEOF\npython3` | `silent` from both copies | Unit |
| TS-10 | Newline after `&&` / `\|\|` (SPEC TS10): `echo x &&\npython3`, `echo x \|\|\npython3` | `deny` from both copies | Unit |
| TS-11 | Regression (SPEC TS11): every `CASES` row that existed at the base revision has the same expected verdict, except `bash -cx 'python3 -i'`, which is now `deny`. No command string appears twice in `CASES`. The byte-equality, static-constraint and rules-document tests pass | All pass under the repo-tests command | Integration |
| TS-12 | Edge cases and malformed input (SPEC Edge Cases, TM-3). Inputs: unclosed groups such as `(python3` and `{ python3;`; a double-quoted substitution nested at least 5000 levels deep; a group nested at least 5000 levels deep; a pipe followed by at least 5000 blank lines; a brace inside a larger word, such as `{a,b}; python3`; and a shell `-c` without a command string (`bash -cx`) | Every input exits 0, prints nothing or exactly one deny JSON object, and writes no traceback to stderr. The brace-in-word row has the base-revision verdict. `bash -cx` is `silent` | Unit |
| TS-13 | Earlier SPEC corrected (FR8, SPEC AC8): in `feature-docs/codex-interactive-guard-hook/SPEC.md`, FR7 and the interpreter-table note define information short options per interpreter and give the shell family none | Neither place lists shell `-h` / `-V` as not denied. The diff against the implement base commit changes only those two places in that file. That feature's `REQUIREMENTS.md` and `reviews/round1.yaml` are unchanged | Manual |
| TS-14 | Plugin version untouched (NFR3): name-only diff of the integration branch against the implement base commit | The diff lists none of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured. NFR2 (standard library only; no file, network or child-process access) is enforced by the existing static-constraint tests inside TS-11.
- Byte identity (FR6): checked by the existing byte-equality test (TS-11). The verify phase may also compare the two files byte for byte directly.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Shell `-c` bundle, `--` and `-` forms, and `bash -ci`, are denied by both copies | TS-1 |
| AC2 | Shell `-h` / `-V` are denied, and the non-shell information options stay silent | TS-3, TS-4 |
| AC3 | `echo "$(echo "; python3 -i")"` is silent | TS-5 |
| AC4 | Commands in connected `( )` / `{ }` groups are silent | TS-7 |
| AC5 | A multi-line pipe's right-hand `python3` is silent | TS-9 |
| AC6 | `CASES` holds the AC1–AC5 commands, the old `bash -cx 'python3 -i'` row expects `deny`, and the focused suite passes | TS-11 plus the focused command |
| AC7 | The two copies are byte-identical | TS-11 (byte-equality test) |
| AC8 | The earlier SPEC's FR7 and table note define information short options per interpreter. REQUIREMENTS.md is unchanged | TS-13 |
| AC9 | `python3 -m unittest discover -s tests` passes | repo-tests command |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-3, TS-4 |
| FR3 | task0001 | TS-5, TS-6, TS-12 |
| FR4 | task0001 | TS-7, TS-8, TS-12 |
| FR5 | task0001 | TS-9, TS-10 |
| FR6 | task0001 | TS-11 |
| FR7 | task0001 | TS-11 |
| FR8 | task0002 | TS-13 |
| NFR1 | task0001 | TS-11, TS-12 |
| NFR2 | task0001 | TS-11 |
| NFR3 | task0001 | TS-14 |

## Manual Testing (E2E Not Possible)
- [ ] TS-13: read the FR7 item and the interpreter-table note of `feature-docs/codex-interactive-guard-hook/SPEC.md`. Confirm that both define information short options per interpreter, give the shell family none, and still state `--version` / `--help` as not denied.

## Performance / Security Verification (if applicable)
- TM-1: shells read `-c` as a flag that takes no value, and have no information short options — checked by TS-1 and TS-3 (every listed form is `deny` from both copies).
- TM-2: each relaxation stays within its trigger — checked by the deny-side boundary cases TS-6, TS-8 and TS-10 (every listed form is `deny` from both copies).
- TM-3: the new reading paths always terminate, and input they cannot follow is indeterminate — checked by TS-12 (exit 0, empty stdout or one deny JSON, no traceback, finishes within the normal test run).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 14 (TS-1 to TS-14) | 13 | 0 | 1 (TS-13) |
| Success criteria | 9 (AC1 to AC9) | 8 | 0 | 1 (AC8) |
| Security (TM-n) | 3 (TM-1 to TM-3) | 3 | 0 | 0 |
| Code quality | 1 (byte identity) | 1 | 0 | 0 |
