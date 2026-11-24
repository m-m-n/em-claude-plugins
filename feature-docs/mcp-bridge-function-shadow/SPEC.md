# Feature: mcp-bridge-function-shadow

## Overview

`destructive-guard` excludes the notion pair (`--mcp notion` / `--tool notion-create-comment`) of `mcp-bridge run` from `--args-json` decoding. This feature stops that exclusion from applying when the same command string contains a construct that overrides the command name or makes the shell state unknown, so the decoded `--args-json` value of such a notion-pair statement is inspected like every other pair.

## Objectives

- Prevent the attack scenario in which a destructive command that should be denied passes through `destructive-guard` via the `--args-json` exclusion of the notion pair (`--mcp notion` / `--tool notion-create-comment`).
- No fixed version exists; this fix is an interim mitigation.

## Acceptance Criteria

- [ ] AC1 (FR1, FR4, FR5): A command that defines a function named `mcp-bridge` and then calls the notion pair with `git branch -D` in the `command` of `--args-json` is denied.
- [ ] AC2 (FR1): The same notion call is denied with any of: the `function NAME` form, a function definition with a name other than `mcp-bridge`, `alias` / `hash` / `enable`, an assignment to `PATH`, a word containing `BASH_CMDS`.
- [ ] AC3 (FR2): The same notion call is denied when an `eval` / `source` / `.` statement, a `${ cmd; }` substitution, or a statement whose command name cannot be read statically is present.
- [ ] AC4 (FR3): The same notion call is denied when a word containing `BASH_FUNC_` or `BASH_ALIASES` is present.
- [ ] AC5 (FR4): The call is also denied when the construct comes after the call, and when the construct is in an enclosing chunk while the notion call is inside a command substitution or a `bash -c` payload.
- [ ] AC6 (FR5): A notion call whose exclusion has been lifted stays allowed when its decoded value is harmless.
- [ ] AC7 (FR6): A function-definition string inside quotes, a comment, or a data heredoc body does not lift the exclusion, and the call stays allowed.
- [ ] AC8 (FR3, FR7): A word containing `BASH_FUNC_` does not change the data-heredoc decision.
- [ ] AC9 (NFR1): The destructive-guard runner passes all cases, and no test of `python3 -m unittest discover -s tests` that passes on base_branch at the integration base fails or errors on the integration branch. Failures that reproduce identically on base_branch at the integration base, in test files this feature's diff does not touch, are not counted.

## Technical Requirements

### Functional Requirements

- **FR1: Lift the notion-pair exclusion when an override construct is present.** Even when a `mcp-bridge run` statement matches the notion pair's canonical form (`_args_json_notion_pair()`), it is not excluded from `--args-json` decoding if any of the following override constructs appears within the FR4 scope:
  - a shell function definition of any name, in any of the forms `NAME()`, `NAME ()`, `function NAME`;
  - `alias` / `hash` / `enable` as the command word (including via `builtin`);
  - an assignment to `PATH` (as a command prefix, as a standalone statement, or as an argument of `export`);
  - a word containing `BASH_CMDS` (substring match).

  Detection reads the command the same way as `_overrides_command_name()` / `_overrides_command_name_unlexed()`.
- **FR2: Lift the notion-pair exclusion when a statement makes the shell state unknown.** If a statement that makes the shell state unknown appears within the FR4 scope, the notion-pair statement is not excluded from `--args-json` decoding. Such statements are:
  - a statement whose command word is `eval` / `source` / `.`;
  - a substitution executed in the current shell (`${ cmd; }` / `${| cmd; }`);
  - a command name that cannot be read statically as a single word.
- **FR3: Function / alias import via environment variables.** If any word within the FR4 scope contains `BASH_FUNC_` or `BASH_ALIASES` (substring match, the same as `BASH_CMDS`), the notion-pair exclusion is lifted. These two words are used only for the notion-pair exclusion decision. They are not added to the existing shared override vocabulary (`OVERRIDE_BUILTINS` / `OVERRIDE_VARIABLE_NAME`, `override_seen`, the heredoc data decision, the masking-stop decision).
- **FR4: Search scope for the constructs.** The constructs of FR1 to FR3 are searched for in the chunk containing the notion-pair statement and in every chunk of the chain of enclosing chunks from that chunk up to the top-level chunk. Whether the construct comes before or after the call within a chunk does not matter.
- **FR5: Decision for a statement whose exclusion is lifted.** A notion-pair statement whose exclusion is lifted is handled like a `mcp-bridge run` statement of any other pair: its flags are read, the static `--args-json` value is decoded, and both the substitution candidates of the decoded string and the top-level `command` string are inspected. The forms that become `ask` for the other pairs (a word whose quoting cannot be statically undone, the scan-volume limit) are handled the same way.
- **FR6: Writings that do not match the constructs.** Function definitions, `alias`, `eval`, and similar strings written inside quotes, in comments, or in a heredoc body judged to be data do not match the constructs of FR1 and FR2. FR3 and `BASH_CMDS` are substring matches, so they match even in a word inside quotes.
- **FR7: Decisions that do not change.** The following are unchanged:
  - skipping the re-scan of raw substitution candidates when the top-level chunk is only a single static notion-pair command (`_single_quote_skip_spans()`);
  - the existing `override_seen` and the heredoc data decision;
  - the masking-stop decision;
  - the `--args-json` decision for pairs other than the notion pair.
- **FR8: Test cases and descriptive text.** Add cases to `em-workflow/hooks/tests/destructive-guard-cases.json` that pin the decisions of FR1 to FR6. Update the descriptive text in `destructive-guard.py` that states the notion pair is "the only pair whose decoded value is not inspected" so that it matches the exclusion being lifted under the conditions of FR1 to FR4.

### Non-Functional Requirements

- **NFR1 - Preservation of existing cases:** The feature introduces no new test failure. `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes. Every test of `python3 -m unittest discover -s tests` that passes on base_branch at the integration base also passes on the integration branch. A test that fails or errors identically on base_branch at the integration base, and whose test file is not touched by this feature's diff, does not count against NFR1. Existing deny / ask cases are not removed, and the decisions of existing allow cases do not change, including the existing notion-pair allow cases in `destructive-guard-cases.json` (case labels `TS-3`, `TS-4`, `TS-5`, `TS-22`; `mcp-bridge-exec-tool-rescan` `TS-2`; `mcp-bridge-args-json-exec-guard` `TS-9`; `args-json-quoting-bypass` `TS-5` / `TS-31`).
- **NFR2 - Scan cost:** The FR4 chain decision is computed once per chunk and kept, and the chain is walked without recursion. Deep nesting does not hit the recursion limit.

## Assumptions

- Skipping the re-scan of raw substitution candidates for the top-level chunk (`_single_quote_skip_spans()`) only applies when the chunk is a single simple command (W2). If a statement such as a function definition is in the same chunk, it is already re-scanned, so the target of this fix is only the exclusion of the decoded value (the notion-pair decision in `_mcp_bridge_args_json_chunks()`).
- Shell state outside a single command string, such as functions or aliases defined by an earlier Bash tool call, is out of scope (the hook statically reads only a single command string).
- The existing notion-pair allow cases contain none of the constructs of FR1 to FR3, and their decisions do not change. In the existing case `TS-22` (`destructive-guard-cases.json` lines 1200 / 1201), `function f()` is inside quotes and a comment and does not count as a function definition.
- False positives where the exclusion is lifted by a function definition of any name or by a `BASH_FUNC_` / `BASH_ALIASES` substring match are accepted, because the call stays allowed when the decoded value is harmless.
- Constructs in sibling chunks that are not on the enclosing-chunk chain (such as the body of a different command substitution) are not included in the FR4 scope.
- Additional instructions in the task description (pushing the integration branch and creating a PR, consulting Codex on unclear points) are treated as process instructions and are not included in the functional requirements.
- Baseline for NFR1 / AC9 / TS-16: base_branch at the integration base is the reference. A unittest failure or error counts against NFR1 only when the same test passes on that baseline, or when its test file is touched by this feature's diff. This feature changes no test or version outside its own scope to make a test that already fails on the baseline pass.

## Implementation Approach

### Architecture

The change is confined to the static analysis of `em-workflow/hooks/destructive-guard.py`. No UI is involved; the design step is skipped.

**Components involved:**
```
_mcp_bridge_args_json_chunks()      notion-pair exclusion decision (target of this fix)
_args_json_notion_pair()            canonical form of the notion pair
_overrides_command_name()           override-construct reading reused by FR1
_overrides_command_name_unlexed()   override-construct reading reused by FR1
_single_quote_skip_spans()          unchanged (FR7)
```

### Decision Flow

```
mcp-bridge run statement
  → matches notion pair (_args_json_notion_pair())?
      no  → existing --args-json decision for other pairs (unchanged, FR7)
      yes → any FR1 / FR2 / FR3 construct in the statement's chunk
            or its enclosing-chunk chain up to the top level (FR4)?
              no  → excluded from --args-json decoding (unchanged)
              yes → exclusion lifted; decoded and inspected like other pairs (FR5)
```

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: the hook whose notion-pair exclusion decision and descriptive text change.
- `em-workflow/hooks/tests/destructive-guard-cases.json`: the case table that pins the new decisions.

**External Dependencies:**
- None.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

`<notion call>` stands for:

```
mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"command":"git branch -D example"}'
```

When written into `destructive-guard-cases.json`, each form listed under a scenario is one case.

### Unit Tests (destructive-guard-cases.json)

- [ ] TS-1 (FR1, FR5): Define a function with the same name as `mcp-bridge` and call the notion pair - expected `deny`.
  - `mcp-bridge() { :; }; mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"command":"git branch -D example"}'`
- [ ] TS-2 (FR1): `function`-form definition - expected `deny`.
  - `function mcp-bridge { :; }; mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"command":"git branch -D example"}'`
- [ ] TS-3 (FR1): Function definition with a name other than `mcp-bridge` - expected `deny`.
  - `f() { :; }; mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"command":"git branch -D example"}'`
- [ ] TS-4 (FR1): Each of the `alias` / `hash` / `enable` / `PATH` assignment / `export PATH` / `BASH_CMDS` forms (one case per form) - expected `deny`.
  - `alias mcp-bridge=:; <notion call>`
  - `hash -p /bin/true mcp-bridge; <notion call>`
  - `enable -n echo; <notion call>`
  - `PATH=/tmp/x:$PATH; <notion call>`
  - `export PATH=/tmp/x; <notion call>`
  - `BASH_CMDS[mcp-bridge]=/bin/true; <notion call>`
- [ ] TS-5 (FR2): Each form of a statement that makes the shell state unknown (one case per form) - expected `deny`.
  - `eval :; <notion call>`
  - `source ./env.sh; <notion call>`
  - `. ./env.sh; <notion call>`
  - `${ :; }; <notion call>`
  - `"$cmd"; <notion call>`
- [ ] TS-6 (FR3): Function / alias via environment variables - expected `deny`.
  - `env 'BASH_FUNC_mcp-bridge%%=() { :; }' bash -c "mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{\"command\":\"git branch -D example\"}'"`
  - `BASH_ALIASES[mcp-bridge]=:; <notion call>`
- [ ] TS-7 (FR3, FR6): `BASH_FUNC_` is a substring match, so it matches even in an unquoted argument word - expected `deny`.
  - `echo BASH_FUNC_x; <notion call>`
- [ ] TS-8 (FR4): The construct comes after the call - expected `deny`.
  - `<notion call>; mcp-bridge() { :; }`
- [ ] TS-9 (FR4): The construct is in an enclosing chunk, and the call is inside a one-level / two-level command substitution - expected `deny`.
  - `mcp-bridge() { :; }; echo $(<notion call>)`
  - `mcp-bridge() { :; }; echo $(echo $(<notion call>))`
- [ ] TS-10 (FR5): Substitution candidates in the decoded body are also inspected - expected `deny`.
  - `f() { :; }; mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"$(git branch -D example) と記載する"}'`
- [ ] TS-11 (FR5): With the exclusion lifted, a harmless decoded value stays allowed - expected `allow`.
  - `f() { :; }; mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"コメント"}'`
- [ ] TS-12 (FR6): A function-definition string inside quotes or a comment does not lift the exclusion - expected `allow`.
  - `echo 'mcp-bridge() { :; }'; <notion call>`
  - `<notion call> # mcp-bridge() { :; }`
- [ ] TS-13 (FR6): A function definition in a data heredoc body does not lift the exclusion - expected `allow`.
  ```
  cat <<'EOF'
  mcp-bridge() { :; }
  EOF
  <notion call>
  ```
- [ ] TS-14 (FR3, FR7): `BASH_FUNC_` does not affect the heredoc data decision - expected `allow`.
  ```
  echo BASH_FUNC_x; cat <<'EOF'
  git branch -D example
  EOF
  ```

### Regression Tests

- [ ] TS-15 (NFR1, FR7): The existing notion-pair allow cases (case labels `TS-3`, `TS-4`, `TS-5`, `TS-22` in `destructive-guard-cases.json`; `mcp-bridge-exec-tool-rescan` `TS-2`; `mcp-bridge-args-json-exec-guard` `TS-9`; `args-json-quoting-bypass` `TS-5` / `TS-31`) stay `allow`.
  - `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- [ ] TS-16 (NFR1): The destructive-guard runner on the integration branch, and `python3 -m unittest discover -s tests` on both the integration branch and base_branch at the integration base. Compare the failing / erroring unittest test ids of the two runs. Expected: the runner passes all cases. Every unittest test id that fails or errors on the integration branch also fails or errors identically on base_branch at the integration base, and its test file is not in this feature's diff.
  - `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  - `python3 -m unittest discover -s tests`

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC1 to AC9 are satisfied

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None.

## References

- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`
