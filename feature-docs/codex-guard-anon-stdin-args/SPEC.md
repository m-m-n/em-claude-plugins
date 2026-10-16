# Feature: codex-guard-anon-stdin-args

## Overview

codex-hook-interactive-guard (both the em-workflow and em-review copies)
must stop denying non-interactive runs of zsh anonymous functions whose
stdin is connected. This removes the false positive (regression)
introduced by feature codex-guard-anon-brace-forms. Requirements document:
`feature-docs/codex-guard-anon-stdin-args/REQUIREMENTS.md`.

## Objectives

- codex-hook-interactive-guard (both the em-workflow and em-review copies)
  no longer denies non-interactive runs of zsh anonymous functions whose
  stdin is connected, resolving the false positive (regression)
  introduced by feature codex-guard-anon-brace-forms.
- The detected range (what is denied) and the undecidable range (silent)
  do not change, except for the forms targeted by this feature.

## User Stories

Not applicable.

## Technical Requirements

### Functional Requirements

- **FR1: Inherit the anonymous function head's stdin redirect into the body.**
  When the body group of an anonymous function is opened, any stdin
  redirect (`<` `<<` `<<<` `<&` `0<`) read in the head simple command
  before the body is inherited by the body group, and the body is treated
  as connected. All three forms are in scope:
  - bare `function { ...; }` — the redirect sits before `function`, or
    between `function` and `{`;
  - `function () { ...; }` — the redirect sits before `function`;
  - `() { ...; }` — the redirect sits before `(`.

  A redirect read in the head reaches the body even when a newline sits
  between `()` and `{`. It also reaches nested groups inside the body,
  following the existing connection-propagation rules.

- **FR2: Scope of the inheritance.**
  The connection inherited under FR1 reaches only that anonymous
  function's body (and the groups inside the body). It does not reach:
  - the `(` group of the head's `()` itself;
  - commands after the separator that ends the arguments (`;` `&&` `||`
    `|` `|&` `&` newline);
  - groups that are not anonymous functions (a plain `{ ...; }` or a
    subshell `( ... )`).

  Redirects other than stdin (`>`, `2>`, etc.) do not connect the body.
  An explicit `-i` inside the body is still denied, as before.

- **FR3: Read `(` inside anonymous-function arguments as part of an argument word.**
  A `(` that appears while reading the arguments after the body's closing
  `}` — whether mid-word (`foo(x)`) or word-initial (`(x)`) — is read,
  up to its matching `)`, as part of a single argument word. The
  after_group pointing at the body is preserved, so a later stdin
  redirect connects the body.
  - Whitespace and `|` inside that range are part of the word
    (`foo(a b|c)` is one argument).
  - When the range from `(` to its matching `)` contains any unquoted
    `;`, `&`, or newline, the pre-change reading (opening a group) is
    kept.
  - An unclosed `(` stays undecidable (silent), as before.
  - A `)` with no matching `(` is not undecidable; it is treated as a
    separator per the current `_close_paren` (closing an enclosing
    subshell if there is one).

- **FR4: Align docstrings with the behavior.**
  Step 4 of the module docstring — and, where needed, the relevant
  `_Group` / `_Parser` docstrings — describe the FR1–FR3 behavior:
  inheritance of the head's stdin redirect, how `(` inside arguments is
  read, and the exception when the range contains `;`, `&`, or newline.
  - The description of where arguments end (`;` `&&` `||` `|` `|&` `&`
    newline) must not contradict the fact that a `|` inside a `(`…`)`
    range does not end the argument.
  - The `(`…`)` search must not be described as a "fully quote-aware
    search" (`_skip_parens` does not treat backquotes and comments
    specially).

- **FR5: Keep both copies identical.**
  `em-workflow/scripts/codex-hook-interactive-guard.py` and
  `em-review/scripts/codex-hook-interactive-guard.py` are fixed in the
  same change and kept byte-for-byte identical.

- **FR6: Add regression tests.**
  Add the three reproduction commands to `CASES` in
  `tests/test_codex_hook_interactive_guard.py` as silent, and add each
  case under Test Scenarios in the form
  `(expected verdict, label, command)`. Cases whose arguments contain
  `foo(x)` or `(x)` are prefixed with `setopt nonomatch nobareglobqual;`.

### Non-Functional Requirements

- **NFR1:** Every existing deny / ask / silent case in `CASES` keeps
  passing with the same verdict. No existing deny case is removed.
- **NFR2:** Parsing stays linear in input length. The range scan for `(`
  inside arguments must not become quadratic even when, after a range
  containing `;` opens a group, it is scanned again by the arguments of a
  nested anonymous function (e.g. repeated `function { :; } x(`). The
  existing `TestMalformedAndDeepInput` passes within its 60-second limit.
- **NFR3:** The existing constraints — standard library only, no
  recursion, no file / network / subprocess access (`TestNoRecursion`,
  `TestStaticConstraints`) — are preserved.
- **NFR4:** The existing docstring wording pinned by
  `TestGuardDocumentation` is kept (e.g. `A stdin redirect among or after
  the arguments connects the body`, `the pipe connection passes to the
  body`, ``the anonymous body takes it as its `pipe` ``, `the pipe
  connection comes from the head`).
- **NFR5:** The plugin version is not changed.

## Implementation Approach

### Architecture

Not applicable (parser fix inside an existing hook script; no new
components).

### Data Flow

Not applicable.

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- Existing `_close_paren` behavior: unchanged (FR3).
- Existing `_skip_parens`: does not treat backquotes and comments
  specially (FR4).
- Existing connection propagation into nested groups (FR1).

**External Dependencies:**
- None (standard library only, NFR3).

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1-FR5
em-review/scripts/codex-hook-interactive-guard.py     # FR1-FR5 (byte-identical copy)
tests/test_codex_hook_interactive_guard.py            # FR6
```

### Out of Scope

The following stay exactly as they are judged today:

- a stdin redirect between `()` and `{` (the `() < f { ...; }` form);
- a redirect before a group that is not an anonymous function
  (`< f { ...; }`, `< f ( ... )`).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-anon-stdin-args/**`
- `test-docs/codex-guard-anon-stdin-args/**`

`feature-docs/codex-guard-anon-stdin-args/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-anon-stdin-args/**` covers
`test-docs/codex-guard-anon-stdin-args/{T}.tests.yaml`, the per-task test
record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-anon-stdin-args/` directory at all; the declared
`test-docs/codex-guard-anon-stdin-args/**` entry is still correct in that
case — a declared path that never materializes is not a violation.

## Test Scenarios

Run command: `python3 -m unittest tests.test_codex_hook_interactive_guard`.

### Unit Tests

TS1–TS19 are added to `CASES` in
`tests/test_codex_hook_interactive_guard.py` as
`(expected verdict, label, command)`. Labels below are English renderings;
the label strings in `CASES` may be written in the file's existing style.

| ID | Refs | Expected | Command | Label |
|----|------|----------|---------|-------|
| TS1 | AC1 | silent | `zsh -c 'function < /dev/null { python3; }'` | An input redirect between `function` and `{` connects the body of a bare anonymous function |
| TS2 | AC2 | silent | `zsh -c '< /dev/null function { python3; }'` | An input redirect before `function` connects the body of a bare anonymous function |
| TS3 | AC3 | silent | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'` | An input redirect after an argument word containing `(` connects the body |
| TS4 | AC4 | silent | `zsh -c '< /dev/null () { python3; }'` | An input redirect before the head of a word-less `()` anonymous function connects the body |
| TS5 | AC4 | silent | `zsh -c '< /dev/null function () { python3; }'` | An input redirect before the head of a `function ()` anonymous function connects the body |
| TS6 | AC4, FR1 | silent | `zsh -c '< /dev/null function { { python3; }; }'` | The head input redirect's connection also reaches nested groups in the anonymous body |
| TS7 | AC5 | deny | `zsh -c '< /dev/null function { python3 -i; }'` | `-i` in the body is denied even with a head input redirect |
| TS8 | AC5 | deny | `zsh -c '< /dev/null function { :; } arg; python3'` | The head input redirect's connection does not reach past the separator after the arguments |
| TS9 | AC5 | deny | `zsh -c '2> /dev/null function { python3; }'` | A non-stdin redirect in the head does not connect the body |
| TS10 | AC6 | silent | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } (x) < /dev/null'` | A word-initial `(` in the arguments is also read as an argument |
| TS11 | AC6 | silent | `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(a b\|c) < /dev/null'` | Whitespace and `\|` inside `(`…`)` in the arguments are part of the word |
| TS12 | AC6 | silent | `zsh -c "setopt nonomatch nobareglobqual; function { python3; } foo(';') < /dev/null"` | A quoted `;` inside `(`…`)` in the arguments does not open a group |
| TS13 | AC6, FR3 | silent | `zsh -c 'setopt nonomatch nobareglobqual; () { python3; } foo(x) < /dev/null'` | For a word-less `()` anonymous function too, an input redirect after `(` in the arguments connects the body |
| TS14 | AC5, FR3 | deny | `zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(x) < /dev/null'` | `-i` in the body is denied even with `(` in the arguments |
| TS15 | AC5, FR3 | deny | `zsh -c 'setopt nonomatch nobareglobqual; function { :; } foo(x); python3'` | A launch past the separator after a word containing `(` is denied |
| TS16 | AC7 | deny | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i)'` | When `(`…`)` in the arguments contains `;`, it is read as a group as before |
| TS17 | AC7 | deny | `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i)'` | When `(`…`)` in the arguments contains `&`, it is read as a group as before |
| TS18 | AC7 | deny | `zsh -c 'setopt nobadpattern; function { :; } foo(a<NEWLINE>python3 -i)'` (`<NEWLINE>` is a literal newline character) | When `(`…`)` in the arguments contains a newline, it is read as a group as before |
| TS19 | AC7 | silent | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` | When `(`…`)` in the arguments contains `;` and the closing paren is inside a comment, it stays undecidable as before (existing miss, unchanged) |

### Integration Tests

- [ ] TS21 (AC8): `TestGuardDocumentation` passes; all existing markers
  remain. This SPEC fixes no additional marker wording.
- [ ] AC9: `TestCopies` passes (both copies byte-for-byte identical).
- [ ] AC10: `python3 -m unittest tests.test_codex_hook_interactive_guard`
  passes in full.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] Unquoted `;` / `&` / newline inside `(`…`)` in the arguments: same
  verdict as before the change (TS16–TS19).
- [ ] Unclosed `(` in the arguments: stays undecidable (silent) (FR3).
- [ ] `)` with no matching `(`: treated as a separator per the current
  `_close_paren` (FR3).

### Performance Tests

- [ ] TS20 (NFR2): input consisting of `function { :; } x(` repeated 6000
  times, followed by `; :` and then 6000 `)` characters. Expected: exit
  code 0, no stderr output, output is empty or a single deny (the
  `TestMalformedAndDeepInput` shape).
- [ ] The existing `TestMalformedAndDeepInput` passes within its 60-second
  limit.

## Security Considerations

- **Input Validation:** The detected (deny) range and the undecidable
  (silent) range do not change outside the forms targeted here; every
  existing `CASES` entry keeps its verdict and no existing deny case is
  removed (NFR1).
- Other items: Not applicable.

## Error Handling

Not applicable.

## Performance Optimization

### Performance Goals
- Parsing remains linear in input length (NFR2).

## Success Criteria

- [ ] AC1 (FR1, FR6): `zsh -c 'function < /dev/null { python3; }'` produces no output (silent).
- [ ] AC2 (FR1, FR6): `zsh -c '< /dev/null function { python3; }'` is silent.
- [ ] AC3 (FR3, FR6): `zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null'` is silent.
- [ ] AC4 (FR1): The `() { ...; }` and `function () { ...; }` forms are also connected by a stdin redirect before the head and are silent.
- [ ] AC5 (FR2): Even with a head stdin redirect, `python3 -i` in the body, `python3` after the separator following the arguments, and `python3` in a body with only non-stdin redirects remain deny.
- [ ] AC6 (FR3): Word-initial `(x)`, `foo(a b|c)` containing whitespace and `|`, and `foo(';')` containing a quoted `;` are each read as one argument, and the following `< /dev/null` connects the body (silent).
- [ ] AC7 (FR3): When `(`…`)` in the arguments contains an unquoted `;`, `&`, or newline, the verdict is the same as before the change (`foo(a; python3 -i)` etc. deny; `foo(a; python3 -i #)` stays silent).
- [ ] AC8 (FR4): The module docstring describes the FR1–FR3 behavior and every existing `TestGuardDocumentation` marker remains.
- [ ] AC9 (FR5): `TestCopies` passes (both copies byte-for-byte identical).
- [ ] AC10 (NFR1, NFR2, NFR3): `python3 -m unittest tests.test_codex_hook_interactive_guard` passes in full.

## Assumptions

- **A1:** Inheritance of the head's stdin redirect covers the
  `() { ...; }` and `function () { ...; }` forms in addition to the bare
  form (Codex confirmed on real zsh 5.9 that stdin reaches the body).
- **A2:** Reading `(` through its matching `)` as one word applies only
  when that range contains no unquoted `;`, `&`, or newline. Otherwise
  the pre-change reading (opening a group) is kept, changing neither the
  detected range nor the undecidable range.
- **A3:** A word-initial `(` (`function { python3; } (x) < /dev/null`) is
  also covered by A2.
- **A4:** Test commands whose arguments contain `foo(x)` or `(x)` are
  prefixed with `setopt nonomatch nobareglobqual;`. Without it, real zsh
  fails with `no matches found` and never reaches the body.
- **A5:** A `)` with no matching `(` is treated as a separator by the
  current `_close_paren`, and an unclosed `(` stays undecidable. This
  distinction is unchanged.
- **A6:** `_skip_parens` does not treat backquotes and comments
  specially, so the spec does not call it a "fully quote-aware search".
- **A7:** A stdin redirect between `()` and `{` (the `() < f { ...; }`
  form) and a redirect before a non-anonymous-function group
  (`< f { ...; }`, `< f ( ... )`) are out of scope; their verdicts stay
  as they are today.
- **A8:** As a bug fix, neither minor nor major is bumped and the version
  is not changed.

## Open Questions

None. No requirement has `status: tbd`.

## References

- Requirements document: `feature-docs/codex-guard-anon-stdin-args/REQUIREMENTS.md`
