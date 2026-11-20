# Verification Document: args-json-quoting-bypass

## Overview
**Feature**: args-json-quoting-bypass / **SPEC.md**: `feature-docs/args-json-quoting-bypass/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/args-json-quoting-bypass/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/args-json-quoting-bypass/THREAT-MODEL.md`

All commands run from the repository root of the integration worktree.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook is
  a Python script loaded directly by the runner and the unit tests).
- Expected: not applicable.

## Test Verification
- Command (workflow.yaml `test_command`):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Also run (NFR3): `python3 -m unittest tests.test_destructive_guard_args_json`
- Expected: every command exits 0; the runner reports no FAIL line.
- Coverage target: no coverage tool is configured; coverage is the scenario
  table below (every scenario is a runner case or a unit test).

### Test Scenarios from SPEC.md

TS-1 to TS-18 are SPEC.md's scenarios. TS-19 to TS-23 are added here for the
SPEC acceptance criteria and non-functional requirements that SPEC.md gives no
scenario number (AC-6 docstring part, AC-10, AC-11, NFR5, NFR6). TS-24 to
TS-32 are added by the review round 2 rework (task0005) for FR1's
single-word-certain judgment under nameref (`declare -n`) declarations. TS-33
is added by the verify round 1 rework (task0006), which moves the chunk
derivation links out of `statements()`. In TS-24 to TS-31, `A=(…)` abbreviates
`A=(json --mcp desktop-commander --tool start_process)` and `MB` abbreviates
`mcp-bridge run --mcp notion --tool notion-create-comment --format "$r" --args-json '{"command":"git branch -D example"}'`;
the runner cases hold the commands written out in full.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Notion pair whose `--format` value is an unquoted `${REVIEW_UNSET:-json --mcp desktop-commander --tool start_process}`, with a static `--args-json` whose `command` is `git branch -D example` (3f7145c6c8c0b26a) | deny (pre-fix allow) | Integration (runner) |
| TS-2 | Same with the `--session` value `${REVIEW_UNSET:-s --mcp desktop-commander --tool start_process}` (3f7145c6c8c0b26a) | deny (pre-fix allow) | Integration (runner) |
| TS-3 | Notion pair with `--format "${A[@]}"` after an array assignment (3f7145c6c8c0b26a) | deny (pre-fix allow) | Integration (runner) |
| TS-4 | Notion pair with `--format {json,--mcp=desktop-commander}` (3f7145c6c8c0b26a) | deny (pre-fix allow) | Integration (runner) |
| TS-5 | Notion pair with `--session "$SID"` and a single-quoted body holding `$(git branch -D example)` | allow (pre-fix allow) | Integration (runner) |
| TS-6 | `--mcp\="$S" --tool start_process` with a static `--args-json` holding `git branch -D example` (f16e5bb8d5da2621) | deny (pre-fix allow) | Integration (runner) |
| TS-7 | `--session\="$SID"` before a static `--args-json` holding `git branch -D example` (f16e5bb8d5da2621 / 63d94a7bddc5d673) | deny (pre-fix allow) | Integration (runner) |
| TS-8 | Double-quoted `--args-json` whose command is `printf $`, a line continuation, `DEST` (dc2fdf65ce30d198) | ask with rule `args-json-unrestorable` (pre-fix allow) | Integration (runner) |
| TS-9 | Double-quoted `--args-json` whose command is `git branch -D $`, a line continuation, `X` (dc2fdf65ce30d198) | ask with rule `args-json-unrestorable` (pre-fix deny) | Integration (runner) |
| TS-10 | Double-quoted `--args-json` holding `git branch -D example` and a note `5 $€` (f35ed060564bcf20) | deny (pre-fix allow) | Integration (runner) |
| TS-11 | Single-quoted `--args-json` with an unquoted `$€` spliced into a note, `command` `git branch -D example` (f35ed060564bcf20) | deny (pre-fix allow) | Integration (runner) |
| TS-12 | `--mcp desktop-commander --format ${REVIEW_UNSET:-json --tool} start_process --args-json ...` (O2 (8)) | allow (pre-fix allow) | Integration (runner) |
| TS-13 | `_read_static_word()` on the FR3 forms (double-quoted with one or two continuations, with `{`; unquoted with `X` and with a single-quoted part), on a word also holding `$Y`, and on `$`, a continuation, then a space or the closing quote | WORD_UNRESTORABLE for the FR3 forms; WORD_NOT_STATIC with `$Y`; literal `$` with the continuation removed for the last | Unit |
| TS-14 | `_read_word_as_written()` on a double-quoted word holding `$`, a continuation and a name | None (undeterminable); words without the form read as before | Unit |
| TS-15 | Double-quoted `"5 $€"` and the same written with `\$€` | WORD_STATIC, text `5 $€`, both forms | Unit |
| TS-16 | Many `--args-json '{}'` values plus one value with a `command` string | Same anchor as before; the token lookup is not repeated per value (shown by spy or mock, no timing) | Unit |
| TS-17 | `TestFlagReading`: notion pair with non-certain `--format` / `--session` values; non-certain `--args-json` value; `--session "$SID"`, `--args-json "$(cat comment.json)"`, ANSI-C value | KIND_INSPECTED for the format/session forms; notion-pair predicate false for the args-json forms; KIND_NOTHING with no Unrestorable flag for the quoted / ANSI-C forms | Unit |
| TS-18 | `TestFlagReading`: `--mcp\="$S"` and `--session\="$SID"` before a static `--args-json`; `"--mcp\=$S"` | KIND_INSPECTED with the decoded command; KIND_NOTHING for the double-quoted form | Unit |
| TS-19 | Docstrings and comment (SPEC AC-6 docstring part, FR6, FR7, FR10): O2 (8) in the `_mcp_bridge_args_json_chunks()` and `extract_shell_payload_anchored()` docstrings with SPEC's scope; the FR3 form named in the `_read_static_word()` docstring, step 4 and the `ARGS_JSON_UNRESTORABLE_ASK` comment; the FR10 places describe the new behaviour | `TestDocstring` (with the O2 (8) pin) passes; inspection confirms each place | Unit + Manual |
| TS-20 | Subtest 'equals form with a destination' of `test_a_destination_that_is_not_static_is_inspected` (SPEC AC-10, FR11) | Passes (KIND_INSPECTED) | Unit |
| TS-21 | Regression suite (SPEC AC-11, NFR1, NFR2, NFR3): the runner, `tests.test_destructive_guard_args_json` and `unittest discover -s tests` | All pass; every runner case finishes within the runner's `GUARD_TIMEOUT_SECONDS`; the diff of `destructive-guard-cases.json` against `workflow.implement.base_commit` deletes no case and changes no existing case's elements: it adds lines, and the only existing line it changes is the formerly-last case line, which gains a trailing comma and nothing else | Integration |
| TS-22 | Structure (NFR6): `TestStructure` and the single-word-certain helper | `TestStructure` passes with no change to the test; the helper is one function referenced only from `_args_json_notion_pair()`; `statements()` has no diff | Unit + Manual |
| TS-23 | Version (NFR5): the feature diff against `workflow.implement.base_commit` | `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are not in the diff | Manual |
| TS-24 | `A=(…); echo $(declare -n r='A[@]'; echo $(MB))`: the nameref is declared only in the middle shell of two nested command substitutions (1d971862e2458376, a3fdb05c00db3c03, 21b0ef3d5aaa59ae) | deny (pre-fix allow) | Integration (runner) |
| TS-25 | `A=(…); echo $(declare -n r='A[@]'; echo $(echo $(MB)))`: the declaration two levels above the statement's chunk, below the top chunk | deny | Integration (runner) |
| TS-26 | `bash -c` payload that assigns `A`, declares `r` as a nameref to `A[@]` and runs `MB` (with a double-quoted JSON value) in the same payload | deny | Integration (runner) |
| TS-27 | `A=(…); declare</dev/null -n r='A[@]'; MB` and the same with `declare>/dev/null` (6083a3b46956a2f0) | deny, both (pre-fix allow) | Integration (runner) |
| TS-28 | `A=(…); declare </dev/null -n r='A[@]'; MB` and `A=(…); </dev/null declare -n r='A[@]'; MB` | deny, both | Integration (runner) |
| TS-29 | `source&>/dev/null ./env.sh; MB`, `source &>/dev/null ./env.sh; MB` and `.&>/dev/null ./env.sh; MB` (4d1573a9f53b167f) | deny, all three (pre-fix allow for `source&>`) | Integration (runner) |
| TS-30 | `A=(…); command -- declare -n r='A[@]'; MB` and the same with `command -p --` (7bb299da67faace7) | deny, both (pre-fix allow for `command --`) | Integration (runner) |
| TS-31 | Notion call with `--session "$SID"` and a static `--args-json` holding `{"command":"git branch -D example"}`, inside one and inside two nested command substitutions, with no nameref declaration anywhere | allow, both | Integration (runner) |
| TS-32 | `statements()` with the `Spy` on every TS-27 to TS-30 command | KIND_INSPECTED for the `mcp-bridge` statement of each; each glued form gives the same kind as its spaced form | Unit |
| TS-33 | `bash -c` payload that assigns `A` and declares `r` as a nameref to `A[@]`, then runs `MB` (with a double-quoted JSON value) inside a command substitution in the same payload (TS-22, verify round 1) | deny | Integration (runner) |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.
- Docstrings: English; inside the "Out of scope" part of the
  `_mcp_bridge_args_json_chunks()` docstring no phrase forbidden by
  `TestDocstring.test_no_form_that_is_not_out_of_scope_is_listed` appears
  (covered by TS-19).

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | TS-1 to TS-4 deny (pre-fix allow) | Runner; pre-fix verdict in task0001's test record |
| AC-2 | TS-5 allow; the existing notion-pair allow cases (base lines 1161, 1162, 1163, 1200, 1201, 1374, 1405) stay allow | Runner |
| AC-3 | TS-6, TS-7 deny (pre-fix allow) | Runner; pre-fix verdict in task0002's test record |
| AC-4 | TS-8, TS-9 ask with `args-json-unrestorable` (pre-fix allow / deny) | Runner; pre-fix verdicts in task0003's test record |
| AC-5 | TS-10, TS-11 deny (pre-fix allow) | Runner; pre-fix verdict in task0003's test record |
| AC-6 | TS-12 allow; label and the three out-of-scope texts state O2 (8) with the same scope; `TestDocstring` passes | Runner, TS-19 |
| AC-7 | TS-13 to TS-15 pass | Unit tests |
| AC-8 | TS-16 passes; existing anchor tests (base test-file lines 718-735) pass unchanged | Unit tests |
| AC-9 | TS-17 passes | Unit tests |
| AC-10 | Subtest 'equals form with a destination' passes | TS-20 |
| AC-11 | Runner passes with no existing case deleted or changed; `tests.test_destructive_guard_args_json` and `unittest discover -s tests` pass | TS-21 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0005, task0006 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-17, TS-24 to TS-33 |
| FR2 | task0002 | TS-6, TS-7, TS-18 |
| FR3 | task0003 | TS-8, TS-9, TS-13, TS-14 |
| FR4 | task0003 | TS-10, TS-11, TS-15 |
| FR5 | task0004 | TS-16 |
| FR6 | task0001 | TS-12, TS-19 |
| FR7 | task0003 | TS-8, TS-9, TS-19 |
| FR8 | task0001, task0002, task0003, task0005, task0006 | TS-1 to TS-12, TS-24 to TS-31, TS-33 |
| FR9 | task0001, task0002, task0003, task0004, task0005 | TS-13 to TS-18, TS-32 |
| FR10 | task0001, task0002, task0003 | TS-19 |
| FR11 | task0002 | TS-20 |
| NFR1 | task0004 | TS-16, TS-21 |
| NFR2 | task0001, task0002, task0003, task0005, task0006 | TS-8, TS-9, TS-21 |
| NFR3 | task0001, task0002, task0003, task0004, task0005, task0006 | TS-21 |
| NFR4 | task0004 | TS-16 |
| NFR5 | task0001, task0002, task0003, task0004, task0005, task0006 | TS-23 |
| NFR6 | task0001, task0004, task0005, task0006 | TS-22 |

## Manual Testing (E2E Not Possible)
SPEC.md lists no existing E2E tests and no E2E run command, so there is no E2E
section.

- [ ] TS-19 inspection: read the five FR10 places, the FR7 places and both
  O2 lists, and check they say what SPEC.md FR6, FR7 and FR10 require.
- [ ] TS-22 inspection: the single-word-certain judgment is one helper.
- [ ] TS-23: the feature diff leaves both version files untouched.

## Performance / Security Verification
- NFR1: one hook evaluation stays within the destructive-guard timeout of
  `hooks.json` (10 s) and the runner's `GUARD_TIMEOUT_SECONDS` — TS-21; the
  anchor lookup is linear in values plus tokens — TS-16.
- NFR4: TS-16 is structural (spy or mock); no wall-clock measurement and no
  CPU load is used anywhere.
- TM-1: the notion-pair exclusion applies only to single-word-certain value
  words — checked by TS-1, TS-2, TS-3, TS-4 (deny) and TS-17; under nameref
  declarations in enclosing shells, behind redirections and after
  `command --` — checked by TS-24 to TS-30, TS-33 (deny) and TS-32.
- TM-2: legitimate notion calls stay allow — checked by TS-5, TS-17, TS-31 and
  the existing notion-pair allow cases (AC-2).
- TM-3: an unquoted backslash-escaped `=` is the `=` separator — checked by
  TS-6, TS-7 (deny) and TS-18.
- TM-4: the FR3 form is Unrestorable and holds the `args-json-unrestorable`
  ask; the masking-stop reading treats it as undeterminable — checked by
  TS-8, TS-9 (ask), TS-13 and TS-14.
- TM-5: `$` before a non-ASCII character is literal, so the value is
  inspected — checked by TS-10, TS-11 (deny) and TS-15.
- TM-6: the anchor lookup is linear (map built at most once per call, only
  for values that queue something) — checked by TS-16.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Runner scenarios (TS-1 to TS-12, TS-24 to TS-31, TS-33) | 21 | 21 | 0 | 0 |
| Unit scenarios (TS-13 to TS-18, TS-20, TS-32) | 8 | 8 | 0 | 0 |
| Docstrings / structure (TS-19, TS-22) | 2 | 2 | 0 | 2 |
| Regression suite (TS-21) | 1 | 1 | 0 | 0 |
| Version (TS-23) | 1 | 0 | 0 | 1 |
| Security mitigations (TM-1 to TM-6) | 6 | 6 | 0 | 0 |
| Performance (NFR1, NFR4) | 2 | 2 | 0 | 0 |
