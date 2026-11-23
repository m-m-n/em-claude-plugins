# Verification Document: mcp-bridge-function-shadow

## Overview
**Feature**: mcp-bridge-function-shadow / **SPEC.md**: `feature-docs/mcp-bridge-function-shadow/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/mcp-bridge-function-shadow/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/mcp-bridge-function-shadow/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Baseline: base_branch at the integration base, the commit recorded as the `base_commit` of the `implement` step in `workflow.yaml`. `python3 -m unittest discover -s tests` is also run on a checkout of that commit (TS-16).
- Expected (NFR1, AC9): the destructive-guard runner passes every case. Every unittest test that passes on the baseline also passes on the integration branch. A test that fails or errors identically on the baseline, and whose test file is not in this feature's diff, is not counted. The exit code of the combined command alone does not decide the result; the failing / erroring test ids of the two unittest runs are compared as TS-16 states.
- Coverage target: not set (the project has no coverage tooling)

### Test Scenarios from SPEC.md
`<notion call>` stands for
`mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"command":"git branch -D example"}'`.
Each form listed under a scenario in SPEC.md is one case of
`em-workflow/hooks/tests/destructive-guard-cases.json`. TS-17 to TS-20 are
added by the plan (TS-17 pins TM-2 of THREAT-MODEL.md; TS-18 to TS-20 pin
NFR2, FR7 and FR8 at the unit level), and the second TS-10 form (the `$` of
the body written as the JSON escape `$`) is added because the first form
already gives deny through the raw-candidate re-scan. TS-21 and TS-23 to
TS-27 are added by the review round 1 rework (task0002): `<dc call>` stands for
`mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}'`,
and `<inner notion>` for the notion call inside a double-quoted `bash -c`
argument, as in TS-6.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | A function named `mcp-bridge` is defined, then the notion call | deny | Unit (runner case) |
| TS-2 | `function`-form definition of `mcp-bridge`, then the notion call | deny | Unit (runner case) |
| TS-3 | A function with another name (`f`), then the notion call | deny | Unit (runner case) |
| TS-4 | `alias`, `hash`, `enable`, a PATH assignment, `export PATH`, a `BASH_CMDS` word, then the notion call (one case per form) | deny | Unit (runner case) |
| TS-5 | `eval`, `source`, `.`, a `${ :; }` substitution, a `"$cmd"` command name, then the notion call (one case per form) | deny | Unit (runner case) |
| TS-6 | A `BASH_FUNC_` environment word before `bash -c` running the notion call; a `BASH_ALIASES` assignment before the notion call | deny | Unit (runner case) |
| TS-7 | `echo BASH_FUNC_x` (substring in an argument word), then the notion call | deny | Unit (runner case) |
| TS-8 | The notion call, then a definition of `mcp-bridge` | deny | Unit (runner case) |
| TS-9 | A definition of `mcp-bridge` in the command's own chunk, the notion call one and two command substitutions down | deny | Unit (runner case) |
| TS-10 | `f() { :; }`, then a notion call whose decoded body holds a substitution (raw form and JSON-escaped form) | deny | Unit (runner case) |
| TS-11 | `f() { :; }`, then a notion call with a harmless body | allow | Unit (runner case) |
| TS-12 | A function-definition string inside single quotes, or in a trailing comment, beside the notion call | allow | Unit (runner case) |
| TS-13 | A function definition in a data heredoc body, then the notion call | allow | Unit (runner case) |
| TS-14 | `echo BASH_FUNC_x` beside a data heredoc whose body is `git branch -D example` | allow | Unit (runner case) |
| TS-15 | The existing notion-pair allow cases (destructive-guard-false-deny `TS-3`, `TS-4`, `TS-5`, `TS-22`; mcp-bridge-exec-tool-rescan `TS-2`; mcp-bridge-args-json-exec-guard `TS-9`; args-json-quoting-bypass `TS-5` / `TS-31`) | allow, lines unchanged | Regression (runner) |
| TS-16 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` on the integration branch; `python3 -m unittest discover -s tests` on the integration branch and on base_branch at the integration base (the `implement` step's `base_commit`); the failing / erroring unittest test ids of the two runs are compared | The runner passes every case. Every unittest test id that fails or errors on the integration branch also fails or errors identically on the baseline, and its test file is not in this feature's diff (the diff from the integration base to the integration branch) | Regression |
| TS-17 | `trap`, `mapfile -C` and `readarray -C` running a definition of `mcp-bridge`, then the notion call (one case per form) | deny | Unit (runner case) |
| TS-18 | The chain decision: a chain three times the recursion limit deep is walked without a recursion error; a derived chunk with no link reads as lifted; the per-chunk scan runs at most once per chunk in a run; a definition in a sibling command substitution does not lift | as stated | Unit (`tests/test_destructive_guard_args_json.py`) |
| TS-19 | `OVERRIDE_BUILTINS`, `OVERRIDE_VARIABLE_NAME`, `STOP_COMMAND_WORDS` and `STOP_VARIABLE_NAMES` keep their base values; the notion-pair predicate is still asked first | as stated | Unit (`tests/test_destructive_guard_args_json.py`) |
| TS-20 | The descriptive text of `statements()`, `_single_quote_skip_spans()` and step 2 of `_mcp_bridge_args_json_chunks()` names the lift | as stated | Unit (`tests/test_destructive_guard_args_json.py`) |
| TS-21 | The notion call with the command word written `$'mcp-bridge'` after `f() { :; }`, `$'\x6dcp-bridge'` after `mcp-bridge() { :; }`, and `$'/usr/local/bin/mcp-bridge'` after `f() { :; }` (one case per form); pin: the notion call with the command word `$'mcp-bridge'` and no construct | deny; the pin allow | Unit (runner case) |
| TS-23 | `echo $'BASH\x5fFUNC_x'"$USER"`, `echo $'BASH\x5fALIASES'"$USER"`, `echo $'BASH\x5fCMDS'"$USER"`, then the notion call (one case per form) | deny | Unit (runner case) |
| TS-24 | A `BASH_FUNC_mcp-bridge%%` function import before `bash -c "<inner notion>"` through `/usr/bin/env`, through `env -`, and through `env` with the `=` written `\x3d` in ANSI-C quoting (one case per form) | deny | Unit (runner case) |
| TS-25 | Non-notion forms of the env reading: `/usr/bin/env bash -c`, `env - bash -c` and `env $'A\x3d1' bash -c` running `git branch -D example`; `env - git branch -D example`; `/usr/bin/env` with the `BASH_FUNC_mcp-bridge%%` import before `bash -c` running `<dc call>`; `/usr/bin/env ls`, `env - ls`, `env $'A\x3d1' ls` (one case per form) | the verdict of the hook before task0002 | Unit (runner case) |
| TS-26 | The descriptive text: step 1 of `_mcp_bridge_args_json_chunks()` names the statically restored command word and limits it to a lifted notion pair; the new env reader says it serves only the notion-pair `--args-json` decision and that `head()` does not use it; `_args_json_shadow_scan()` names the static-run match; `head()` still says it is mirrored in failed-run-cleanup-guard.py | as stated | Unit (`tests/test_destructive_guard_args_json.py`) |
| TS-27 | Non-notion command words: `<dc call>` with the command word written `$'mcp-bridge'` (alone and after `f() { :; }`) or `$'\x6dcp-bridge'`; `$"x" args`; `$"x" run`, `$'echo' run` and `"$cmd" run` with an `--args-json` whose `command` is `git branch -D example` (one case per form); at unit level `$'mcp-bridge' run --mcp desktop-commander` and `$"x" run` give KIND_NOTHING and `f() { :; }; $'mcp-bridge' run --mcp notion` with a harmless body gives KIND_INSPECTED | the verdict of the hook before task0002, never reason `args-json-unrestorable`; the kinds as stated | Unit (runner case, `tests/test_destructive_guard_args_json.py`) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | A definition of `mcp-bridge` before the notion call with `git branch -D` in `command` is denied | TS-1 |
| AC2 | The `function NAME` form, another function name, `alias` / `hash` / `enable`, a PATH assignment, a `BASH_CMDS` word are denied | TS-2, TS-3, TS-4, TS-21, TS-23 |
| AC3 | `eval` / `source` / `.`, a `${ cmd; }` substitution, an unreadable command name are denied | TS-5 |
| AC4 | A `BASH_FUNC_` or `BASH_ALIASES` word is denied | TS-6, TS-7, TS-23, TS-24 |
| AC5 | A construct after the call, and a construct in an enclosing chunk with the call in a command substitution or a `bash -c` payload, are denied | TS-8, TS-9, TS-6, TS-24 |
| AC6 | A lifted notion call with a harmless decoded value stays allowed | TS-11 |
| AC7 | A definition string in quotes, a comment or a data heredoc body does not lift the exclusion | TS-12, TS-13 |
| AC8 | A `BASH_FUNC_` word does not change the data-heredoc decision | TS-14, TS-19 |
| AC9 | The destructive-guard runner passes every case, and no unittest test that passes on base_branch at the integration base fails or errors on the integration branch; a failure that reproduces identically on the baseline, in a test file this feature's diff does not touch, is not counted | TS-15, TS-16, TS-25, TS-27 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-21, TS-23 |
| FR2 | task0001 | TS-5, TS-17 |
| FR3 | task0001, task0002 | TS-6, TS-7, TS-14, TS-19, TS-23, TS-24 |
| FR4 | task0001, task0002 | TS-1, TS-8, TS-9, TS-18, TS-24 |
| FR5 | task0001, task0002 | TS-1, TS-10, TS-11, TS-21 |
| FR6 | task0001 | TS-7, TS-12, TS-13 |
| FR7 | task0001, task0002 | TS-14, TS-15, TS-19, TS-25, TS-27 |
| FR8 | task0001, task0002 | TS-1 to TS-14, TS-17, TS-20, TS-21, TS-23, TS-24, TS-26 |
| NFR1 | task0001, task0002 | TS-15, TS-16 (baseline comparison against base_branch at the integration base), TS-25, TS-27 |
| NFR2 | task0001 | TS-18 |

## Manual Testing (E2E Not Possible)
- None. The hook is judged by the runner cases and the unit tests alone.

## Performance / Security Verification (if applicable)
- NFR2: the chain decision is computed once per chunk and kept, and walked without recursion — TS-18.
- TM-1: the notion-pair exclusion is lifted by an FR1 construct in the statement's chunk or its enclosing chain, before or after the call — TS-1 to TS-4, TS-8, TS-9 give deny; on the notion-pair path, a command name `mcp-bridge` in ANSI-C quoting is still recognised, and `BASH_CMDS` in the static part of a word is still matched — TS-21 and TS-23 give deny.
- TM-2: the exclusion is lifted by `eval` / `source` / `.`, `trap`, a `mapfile` / `readarray` callback, a current-shell substitution or an unreadable command name — TS-5 and TS-17 give deny.
- TM-3: the exclusion is lifted by a `BASH_FUNC_` or `BASH_ALIASES` word, and the two words stay out of the shared vocabularies — TS-6 and TS-7 give deny; TS-19 holds. The two words in the static part of a word that also holds an expansion, still lift the exclusion, and a notion call in a `bash -c` payload reached through `/usr/bin/env`, `env -` or an ANSI-C `=` with an import is still found and lifted — TS-23 and TS-24 give deny.
- TM-4: legitimate notion calls stay allowed — TS-11 to TS-15 give allow; TS-19 holds. The readings task0002 adds apply only on the notion-pair path: non-notion pairs and `head()`'s other checks keep the verdict of the hook before task0002, and no command gets a new `args-json-unrestorable` ask — TS-25 and TS-27 keep their verdicts.
- TM-5: a deep chain is walked without a recursion error and each chunk is scanned at most once per run — TS-18.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Runner case scenarios (TS-1 to TS-14, TS-17, TS-21, TS-23 to TS-25, TS-27) | 20 | 20 | 0 | 0 |
| Regression (TS-15, TS-16 with the baseline comparison) | 2 | 2 | 0 | 0 |
| Unit tests (TS-18 to TS-20, TS-26) | 4 | 4 | 0 | 0 |
| SPEC.md success criteria (AC1 to AC9) | 9 | 9 | 0 | 0 |
| Requirements coverage (FR1 to FR8, NFR1, NFR2) | 10 | 10 | 0 | 0 |
| Security / performance (NFR2, TM-1 to TM-5) | 6 | 6 | 0 | 0 |
