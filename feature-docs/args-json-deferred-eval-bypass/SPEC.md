# Feature: args-json-deferred-eval-bypass

Requirements document: `feature-docs/args-json-deferred-eval-bypass/REQUIREMENTS.md`

## Overview

The notion-pair exclusion in `em-workflow/hooks/destructive-guard.py` (`_args_json_notion_pair()`) uses `_args_json_nameref_scan()` to judge whether a preceding command can create a nameref. Constructs that re-evaluate a value later in the current shell (arithmetic, `${var@P}`, values obtained by `read`) slip past that judgment and let `--args-json` go uninspected. This feature makes such chunks, and any simple command whose name is not on a command-name allowlist, mark the shell state as uncertain so the exclusion is dropped and `--args-json` is inspected.

Attack shape: with a shell-executing MCP tool registered in mcp-bridge, a nameref `r` is pointed at an array through one of the forms below, then `mcp-bridge run --mcp notion --tool notion-create-comment --format "$r" --args-json '{"command":"<destructive command>"}'` is run. The hook judges the call notion-bound and allows it without inspecting the JSON, while Bash expands `"$r"` to `json --mcp desktop-commander --tool start_process` and sends it to another tool.

- A value hiding the opening sigil with ANSI-C quoting, evaluated by `${p@P}` (`p=$'$\x7b declare -gn r=A[@]; }'`)
- A value split with `$''{`, or an ANSI-C value, evaluated as an array subscript inside the arithmetic command `(( a ))`
- A value obtained by `read` from a heredoc with a quoted delimiter, or from a file, evaluated the same way

## Objectives

- Make the attack that creates a nameref through values evaluated later in the current shell (arithmetic, `${var@P}`, values obtained by `read`) and bypasses the notion-pair exclusion impossible.
- Pin each attack form as a deny case in `destructive-guard-cases.json`.
- Close the gap for string-evaluating builtins (`fc`, `history`, `enable`, `compgen`, `complete`, `bind`) at the same time, through a builtin allowlist.

## User Stories

### US1: Inspect `--args-json` when the shell state is uncertain
As an em-workflow user running Claude Code unattended with destructive-guard enabled, I want a notion call whose chunk (or an outer chunk) contains a deferred-evaluation construct or a command name outside the allowlist to have its `--args-json` inspected, so that a destructive command inside it is denied.

**Acceptance Criteria:**
- [ ] AC1: Each form of the attack scenario passes as deny in `destructive-guard-cases.json`.
- [ ] AC2: For each FR1 construct, a command that places it before the notion call passes as deny.
- [ ] AC3: For each of `fc`, `history`, `enable`, `compgen`, `complete`, `bind`, those forms prefixed with `builtin` / `command`, `printf -v`, `printf` with a format containing `%n`, builtins that take a variable name as an argument (`read`, `getopts`, `wait -p`, `unset`, `test -v`), and names not on the allowlist, a command that places it before the notion call passes as deny.
- [ ] AC6: The added deny cases use only existing reason IDs, and `destructive-guard.py` has no new reason ID.

### US2: Keep the existing exclusion where it holds
As an em-workflow user, I want notion calls that the existing cases keep excluded to stay excluded.

**Acceptance Criteria:**
- [ ] AC4: The existing allow cases listed in FR6, and all existing deny / ask cases, pass with the same decision.
- [ ] AC5: A chunk with no nameref declaration, no FR1 construct, and only allowlisted command names (e.g. `A=(...); echo hello;` and a notion call with `--session "$SID"`) is still KIND_NOTHING.
- [ ] AC7: `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` both succeed.
- [ ] AC8: The Interim Mitigation section of this SPEC states that no upstream fixed version exists and that this feature's fix is the response.

## Technical Requirements

### Functional Requirements

- **FR1:** Chunks containing a deferred-evaluation construct make the shell state uncertain. `_args_json_nameref_scan()` returns True (shell state uncertain) when the chunk contains any one of the constructs below. This applies at every position the lexer reads as syntax, including inside function bodies, groups, conditionals and loops, inside double quotes, in the body of a heredoc with an unquoted delimiter, and in here-strings. Constructs:
    - arithmetic command `((...))` (including `for ((...))`)
    - arithmetic expansion `$((...))`, `$[...]`
    - `let`
    - arithmetic comparisons in `[[ ]]` (`-eq` `-ne` `-lt` `-le` `-gt` `-ge`) and `-v`
    - array subscripts that use a variable (a `$` expansion or a name) as the subscript (in assignment words, in `[..]=` of compound assignments, inside parameter expansions)
    - `declare` / `local` / `typeset` options containing `i`
    - parameter expansions with the `@P` transformation
    - indirect expansion `${!x}`
    - assignment to a predefined variable with the integer attribute (e.g. `OPTIND`)
    - assignment to `PS4`, and enabling xtrace (`set -x` / `set -o xtrace`)
- **FR2:** Stop treating arithmetic commands as "declares nothing". In `_args_json_declaration_word()` and its callers, stop treating the arithmetic-command region as "not a command name and declares nothing". Arithmetic commands are treated as uncertain per FR1.
- **FR3:** Judge command names by an allowlist. Change the command-name judgment in `_args_json_declares_nameref()` from a denylist (`eval`, `source`, `.`, `trap`, `alias`, `mapfile`, `readarray`) to an allowlist.
    - The allowlist holds only builtins, keywords and external commands confirmed not to change shell state, not to evaluate strings, and not to take a variable name as an argument.
    - A simple command whose name is not on the allowlist makes the shell state uncertain. This covers `fc`, `history`, `enable`, `compgen`, `complete`, `bind`; unclassified names; calls to functions defined in the chunk; and builtins that take a variable name as an argument (`read`, `printf -v`, `getopts`, `wait -p`, `unset`, `test -v` / `[ -v`, etc.).
    - When called with `builtin` / `command` in front (and the existing prefixes `exec`, `time`, `!`), the name after skipping the prefix is classified the same way.
    - `printf` is uncertain when it has `-v`, and also when it has a format containing `%n`.
    - `declare` / `local` / `typeset` stay handled individually as today; any option containing `n`, any option containing `i` (FR1), or any word that cannot be restored makes the state uncertain.
- **FR4:** Keep the literal search as a supplement. The round 3 literal `${` / `${|` search across the chunk regardless of quoting, and its line-continuation handling (`_args_json_has_brace_substitution()`), stay in place.
- **FR5:** Pin the attack forms as deny cases. Add to `destructive-guard-cases.json` as deny, with labels starting with `args-json-deferred-eval-bypass`:
    - each attack form in the Overview (`${p@P}` evaluating an ANSI-C value; a `$''{`-split value or an ANSI-C value evaluated as an `(( a ))` array subscript; a value `read` from a quoted-delimiter heredoc or from a file, then evaluated)
    - each FR1 construct
    - each name that FR3 makes uncertain (`fc`, `history`, `enable`, `compgen`, `complete`, `bind`; the `builtin` / `command`-prefixed forms; `printf -v`; a `printf` format containing `%n`; builtins that take a variable name as an argument)
- **FR6:** Keep the forms that retain the existing exclusion. The existing allow cases that keep the notion-pair exclusion (`destructive-guard-cases.json` entries 1161-1163, 1200-1201, 1374, 1421, 1426, 1473, 1474; covering single-quoted bodies, `"$SID"`, and one- and two-level command substitution), and the existing deny / ask cases (including the round 3 denies), all keep the same decision. To that end the allowlist includes the command names that appear in the notion-call chunk and its outer chunks in these cases and in the existing unit tests (`mcp-bridge`, `echo`), and a classification that lets the forms the existing unit tests pin as KIND_NOTHING (`declare -a`, `command -- echo`, comments) pass.
- **FR7:** Revise the unit test that pinned the arithmetic command. In `tests/test_destructive_guard_args_json.py`, remove the subtest `'arithmetic command without blanks'` (the notion call after `((x=1));` expected as KIND_NOTHING) from `TestNamerefDeclarations.test_a_declaration_with_no_nameref_option_does_not_make_the_call_uncertain`, and move it to a form expecting KIND_INSPECTED. Revise the docstring's "an arithmetic command" wording accordingly.
- **FR8:** Add no new rule or reason ID. The uncertain treatment is reflected only in the existing notion-pair exclusion judgment (the result of `_args_json_nameref_declared()`). No new ask / deny rule and no new reason ID are added.

### Non-Functional Requirements

- **NFR1 - Static analysis only:** The judgment uses static analysis only and never executes or evaluates commands. A chunk the lexer cannot read as statements is treated as uncertain, as today.
- **NFR2 - Performance:** The judgment is computed once per chunk and cached (`_nameref_declared_cache`). Walking to outer chunks does not use recursion (the existing `test_the_chain_is_walked_without_recursion` is kept).
- **NFR3 - Test dependencies:** Tests use the standard library only (`test/README.md`).
- **NFR4 - Versioning:** The em-workflow version is not changed (`.claude/rules/core-plugin-version-bump.md`).
- **NFR5 - Hook tests:** `python3 em-workflow/hooks/tests/run-destructive-guard.py` is run in the same change that modifies `destructive-guard.py` (`.claude/rules/hook-tests.md`).

## Implementation Approach

### Architecture

**Component Diagram:**
```
_args_json_notion_pair()
  └─ _args_json_nameref_declared()        # result drives the notion-pair exclusion (FR8)
       └─ _args_json_nameref_scan()       # per chunk, cached in _nameref_declared_cache (NFR2)
            ├─ deferred-evaluation constructs → uncertain (FR1, FR2)
            ├─ _args_json_declares_nameref() → command-name allowlist (FR3)
            │    └─ _args_json_declaration_word()  # arithmetic-command region no longer "declares nothing" (FR2)
            └─ _args_json_has_brace_substitution() # literal ${ / ${| search, kept (FR4)
```

### Data Flow

```
Bash command with a notion call
  → scan the notion-call chunk and its outer chunks (iterative, no recursion)
  → nameref declaration / FR1 construct / non-allowlisted command name found?
       no  → keep the notion-pair exclusion
       yes → shell state uncertain → drop the exclusion → inspect --args-json
                                     → destructive command inside → deny
                                     → none                       → not denied
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: the notion-pair exclusion and the `--args-json` inspection.
- `em-workflow/hooks/tests/run-destructive-guard.py` and `em-workflow/hooks/tests/destructive-guard-cases.json`: the `[decision, label, command]` case table.
- `tests/test_destructive_guard_args_json.py`: unit tests for the `--args-json` stage (drives `statements()` with a Spy and checks the kind).

**External Dependencies:**
- Python 3 standard library only (`test/README.md` assumes Python 3.14).

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # FR1-FR4, FR8
└── tests/
    └── destructive-guard-cases.json     # FR5 deny cases
tests/
└── test_destructive_guard_args_json.py  # FR7
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/args-json-deferred-eval-bypass/**`
- `test-docs/args-json-deferred-eval-bypass/**`

`feature-docs/args-json-deferred-eval-bypass/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/args-json-deferred-eval-bypass/**` covers `test-docs/args-json-deferred-eval-bypass/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/args-json-deferred-eval-bypass/` directory at all; the declared
`test-docs/args-json-deferred-eval-bypass/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Integration Tests (case table, `run-destructive-guard.py`)
- [ ] TS-1: After `p=$'$\x7b declare -gn r=A[@]; }'` and `${p@P}`, a notion call with `--format "$r"` and a destructive command - deny (AC1)
- [ ] TS-2: After evaluating a `$''{`-split value and an ANSI-C value as an `(( a ))` array subscript, the same notion call - deny (AC1)
- [ ] TS-3: After evaluating a value `read` from a quoted-delimiter heredoc, and a value `read` from a file, the same notion call - deny (AC1)
- [ ] TS-4: One case per FR1 construct placed before the notion call, including forms placed inside a function body, group, conditional, loop, double quotes, the body of an unquoted-delimiter heredoc, and a here-string - deny (AC2)
- [ ] TS-5: Each of `fc`, `history`, `enable`, `compgen`, `complete`, `bind`, alone and with a `builtin` / `command` prefix - deny (AC3)
- [ ] TS-6: `printf -v`, `printf` with a format containing `%n`, `read`, `getopts`, `wait -p`, `unset`, `test -v`, a call to a function defined in the chunk, and a name not on the allowlist - deny (AC3)
- [ ] TS-7: All existing allow / deny / ask cases - same decision (AC4)

### Unit Tests
- [ ] TS-8: The notion call with `--session "$SID"` after `A=(...); echo hello;`, `declare -a`, `command -- echo`, and the comment form - KIND_NOTHING in the unit tests; the `((x=1));` form - KIND_INSPECTED (FR7) (AC5)

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-9: A deferred-evaluation construct only inside a command substitution, with the notion call outside it - the exclusion is kept (AC5)

### Reason ID Checks
- [ ] TS-10: The added deny cases carry `rule`, and it matches an existing reason ID (AC6)

### Performance Tests
Not applicable.

### Edge Case Notes

- The value obtained by `read` is not visible statically (including reads from a file). `read` is not on the allowlist, so it is uncertain if it appears in the same chunk or an outer chunk. A construct that evaluates the read value afterwards (FR1) is also uncertain.
- Passing a subscripted name to a builtin that takes a variable name (`read 'x[a]'`, `printf -v 'x[a]'`, `getopts o 'x[a]'`, `wait -p 'x[a]'`, `unset 'x[a]'`, `test -v 'x[a]'`) evaluates the subscript as arithmetic. Under the allowlist these builtins are uncertain regardless of their arguments.
- `test` / `[` is uncertain only when it has `-v`. `[[ ]]` is uncertain when it has an FR1 arithmetic comparison or `-v`.
- Assigning a value to a predefined variable with the integer attribute (such as `OPTIND`) evaluates the value as arithmetic.
- `PS4` is expanded in the current shell on every xtrace line.
- A function defined in the chunk makes its calls uncertain unless it has the same name as an allowlisted name. When a function is defined with an allowlisted name, its body is scanned as part of the same chunk.
- When the evaluating construct is inside a command substitution (a subshell) and the notion call is outside, the caller's state does not change. The current judgment only walks outward, so the exclusion is kept in this case.
- `((` and `@P` inside single quotes or in the body of a quoted-delimiter heredoc are data and are not counted (A3).
- Array subscripts consisting only of digits, and compound assignments without subscripts, keep the exclusion (A4).
- The uncertain treatment drops only the exclusion. If `--args-json` contains no destructive command, it is not denied.

## Security Considerations

- **Severity:** high. In unattended runs, a destructive command can be executed through an MCP-routed shell without passing destructive-guard's deny.
- **Fail-safe:** Forms that cannot be judged and unclassified names are treated as uncertain.
- **Input Validation:** The command string is judged by static analysis only; it is never executed or evaluated (NFR1).
- **Test suite:** Existing deny / ask cases are not removed (`.claude/rules/hook-tests.md`).
- **Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF:** Not applicable.

## Interim Mitigation

No upstream fixed version exists (no CVE / GHSA ID, no affected package). The response is this feature's fix to `em-workflow/hooks/destructive-guard.py`.

## Error Handling

### Error Codes

No new rule and no new reason ID are added (FR8). Denies produced by the inspected `--args-json` use the existing reason IDs.

### Error Flow

```
Shell state uncertain → notion-pair exclusion dropped → --args-json inspected → existing deny rule and reason ID
```

## Performance Optimization

### Performance Goals
- Not specified beyond NFR2.

### Optimization Strategies
- Per-chunk computation once (NFR2).
- Iterative walk to outer chunks, no recursion (NFR2).

### Caching Strategy
- Per-chunk nameref-uncertainty result: `_nameref_declared_cache` (NFR2).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Code review is completed
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` both succeed (AC7)

## Assumptions

- A1: Command names are judged by an allowlist. Only builtins, keywords and external commands confirmed not to change shell state, not to evaluate strings, and not to take a variable name as an argument are known; everything else is uncertain. (Source: answer `requirement.builtin-judgment-approach`)
- A2: Calls prefixed with `builtin` / `command` are also classified. `printf` is uncertain with `-v` and also with a format containing `%n`. (Source: answer `requirement.builtin-judgment-approach`)
- A3: `((` and `@P` inside single quotes or in the body of a quoted-delimiter heredoc are not counted; they are data. (Source: existing allow cases 1161, 1162, 1200, 1201)
- A4: Array subscripts consisting only of digits, and compound assignments without subscripts, keep the exclusion. (Source: existing unit tests and the AC5 example)
- A5: The uncertain treatment is reflected only in the existing notion-pair exclusion judgment; no new ask / deny rule and no reason ID are added. All existing notion allow cases and the round 3 denies are kept. (Source: answer `requirement.builtin-judgment-approach`)
- A6: The design step is skipped. (Source: answer `design.step.recommendation`)

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- None

## References

- Requirements document: `feature-docs/args-json-deferred-eval-bypass/REQUIREMENTS.md`
- `em-workflow/hooks/destructive-guard.py`
- `em-workflow/hooks/tests/destructive-guard-cases.json`
- `em-workflow/hooks/tests/run-destructive-guard.py`
- `tests/test_destructive_guard_args_json.py`
- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
- `test/README.md`
