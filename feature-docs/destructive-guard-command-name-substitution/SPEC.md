# Feature: destructive-guard-command-name-substitution

## Overview

`destructive-guard.py` lets a command whose command word itself is decided by a
command substitution (`$(which rm) -rf <path>`) through as `allow`, because
`head()` skips the `.substitution_only` token at the command-word position and
the statement's command word becomes `-rf`. This feature closes that miss by
reading the command name statically out of the substitution's raw text and
gating the rm / git routes on that evidence. It also replaces the payload
position's partial-match quote test with a whole-word (`.substitution_only`)
precondition, so that a `-c` body mixing quoted substitutions with destructive
commands is rescanned again instead of regressing from `deny` to `allow`.

The requirements source is
`feature-docs/destructive-guard-command-name-substitution/REQUIREMENTS.md`.

## Objectives

- Bring the substitution-headed spellings whose command name reads statically as
  `rm` into scope and close the `$(which rm) -rf <path>` miss, with no escape via
  operand-first flag ordering or via omitting the force flag (OBJ-1).
- At the `-c` / `eval` / `<<<` payload argument position, distinguish quoting only
  when the payload word is a substitution in its entirety, removing the false
  positive produced by promoting a quoted `"$(...)"`; keep rescanning the body
  when it mixes substitutions with real commands (OBJ-2).
- Declare in writing that a form whose substitution *result* becomes the script
  body is not statically decidable, and keep the reason text, the case label and
  the docstring in agreement about that scope (OBJ-3).
- Add no false positives. A substitution-headed spelling is never judged more
  strictly than the plain spelling. `$(true) echo safe` / `env $(true) echo safe` /
  `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` /
  `$(which cp) -rf src dst` / `$(which chmod) -Rf 755 build` /
  `$(which tar) -rf archive.tar file.txt` / `$(which make) clean -fd` /
  `eval "$(ssh-agent -s)"` / `bash -c "$(cat script.sh)"` stay `allow` (OBJ-4).
- Make the substitution-headed spelling's decision tier and reason id identical to
  the plain spelling of the statically read command name. When the command name
  cannot be read, keep today's blanket `allow` and document that limit (OBJ-5).

## User Stories

### US1: Stop a destructive command whose name comes from a substitution

As the destructive-guard decision, I want the rm / git routes to be entered on
statically read command-name evidence, so that `$(which rm) -rf <path>` no longer
passes as `allow`.

**Acceptance Criteria:**

- [ ] AC-1: `$(which rm) -rf /home/sakura/valuable` is `deny` with reason id `rm-recursive`; the backtick spelling behaves the same.
- [ ] AC-2: `$(which git) reset --hard HEAD` is `deny` / `git-reset-hard`, and `$(which git) clean -fd` is `deny` / `git-clean`.
- [ ] AC-13: The operand-first spelling `$(which rm) /home/sakura/valuable -rf` is `deny` / `rm-recursive`; `$(which rm) /home/sakura -rf` is `deny` too.
- [ ] AC-14: Recursive-without-force forms `$(which rm) -r /home/sakura/valuable` / `$(which rm) -R /home/sakura/valuable` / `$(which rm) --recursive /home/sakura/valuable` are all `deny` / `rm-recursive`.

### US2: Do not stop harmless forms

As the destructive-guard decision, I want forms with no rm / git evidence to keep
today's `allow`, so that an unattended run is not halted by a false positive.

**Acceptance Criteria:**

- [ ] AC-3: `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` are `allow`.
- [ ] AC-4: `$(which rm) -rf dist` and `$(which rm) -rf /tmp/scratch/x` are `allow` (the existing safe-route exception is inherited).
- [ ] AC-6: `eval "$(ssh-agent -s)"` / `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` / `bash -c "$(cat script.sh)"` are all `allow`.
- [ ] AC-15: Non-rm/git commands that legitimately take recursive + force flags are `allow`: `$(which cp) -rf src dst` / `$(which cp) -Rf src dst` / `$(which chmod) -Rf 755 build` / `$(which chown) -Rf user:group /srv/app` / `$(which tar) -rf archive.tar file.txt` / `$(which grep) -rf patterns.txt src` / `$(which rsync) -rf src/ dst/` / `$(which scp) -rf host:/a /b`.
- [ ] AC-16: Non-git commands in the substitution-head + git-subcommand shape are `allow`: `$(which make) clean -fd` / `$(hatch env find) reset --hard`.
- [ ] AC-17: `$(which grep) -r pattern src` stays `allow`, and its label states the new rationale: no readable evidence that the command is `rm`.

### US3: Match real shell semantics at the payload position

As the destructive-guard decision, I want quoting to be distinguished at the
`-c` / `eval` / `<<<` payload argument position only when the payload word is a
substitution in its entirety, so that the quoted-substitution false positive
disappears, the unquoted `deny`s are preserved, and mixed bodies are still
rescanned.

**Acceptance Criteria:**

- [ ] AC-5: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` is `allow`, and the case is not deleted from cases.json — it stays with a rewritten label.
- [ ] AC-7: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / the backtick spelling / `sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` stay `deny`.
- [ ] AC-18: All three `-c` bodies that mix a quoted substitution with a destructive command are `deny`: `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` / `sh -c 'echo "$(date)" && rm -rf /home/sakura/valuable'` / `bash -c 'echo "$(pwd)"; git reset --hard HEAD'`.
- [ ] AC-19: The quoted here-string `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` is `allow`, and its inversion from `deny` is recorded both in the acceptance criteria and in the case table.

### US4: State the out-of-scope range in writing

As a reader of this hook, I want the static analysis's out-of-scope range stated
identically in the case label and in the docstring, so that the known limit can be
confirmed from a single description.

**Acceptance Criteria:**

- [ ] AC-8: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` is `allow`, and its label together with `extract_shell_payload()`'s docstring state the same range: a form whose substitution result becomes the script body is out of scope.
- [ ] AC-21: The statically unreadable substitution-headed form (`$(cat cmdfile) -rf /home/sakura/valuable`) stays `allow`, and that limit is written down as part of the same out-of-scope declaration in the case label and the docstring.

### US5: Keep the existing decisions, the tests and the route's shape

As a user of this plugin, I want existing decisions and reason texts unchanged,
the route's entry condition testable in one place, and the version convention
satisfied, so that the change reaches the cache and detection power is
demonstrably intact.

**Acceptance Criteria:**

- [ ] AC-9: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes for every case.
- [ ] AC-10: The set of failing test IDs from `python3 -m unittest discover -s tests` matches the base revision's set exactly, with zero new failures introduced by this change.
- [ ] AC-11: The em-workflow `version` in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` is the same value and at least one patch ahead of the previous value.
- [ ] AC-12: For commands containing no substitution, the changed hook returns the same decision and the same reason text as before.
- [ ] AC-20: The substitution-head routing is extracted from `main()` into one named function, `main()` retains only the call, and `_rm_route_candidate()` is deleted.
- [ ] AC-22: FR11's reading is performed with string processing only — no substitution execution, no subprocess launch, no filesystem access.

## Technical Requirements

### Functional Requirements

- **FR1 - Substitution at the command-word position, rm route (gated on command-name evidence):**
  For a statement where `head()` skipped a `.substitution_only` token at the
  command-word position, and only when the command name read by FR11 is `rm`, pass
  the remaining tokens after the skip position straight to the existing
  `check_rm()`. Both of today's pre-gates are removed: the dash pre-gate requiring
  the next token to start with `-`, and `_rm_route_candidate()`'s "recursive AND
  force AND at least one non-flag operand" floor. The threshold decision is left to
  `check_rm()` itself (recursion presence and `RM_ROOT_SHAPE`). The decision tier
  (`deny` / `ask`) and the reason id are exactly what `check_rm()` returns; no new
  tier and no new reason id is created. As a result the flag-first form, the
  operand-first form and the recursive-without-force form each produce the same
  decision as giving the same arguments to a plain `rm`. Safe-route exceptions are
  inherited just as in the plain spelling.
- **FR2 - Substitution at the command-word position, git route (gated on command-name evidence):**
  For the same statement, and only when the command name read by FR11 is `git`,
  pass the remaining tokens to the existing `check_git()`. Today's behaviour —
  calling `check_git()` unconditionally whenever a substitution was skipped — is
  removed. `$(which git) reset --hard HEAD` / `$(which git) clean -fd` become
  `deny` under the existing `git-reset-hard` / `git-clean`, while
  `$(which make) clean -fd` and `$(hatch env find) reset --hard` never enter the
  route (no git evidence) and stay `allow`. A remainder that `check_git()` matches
  nothing against (`echo safe`, `status`) yields no decision.
- **FR3 - Keeping `allow` for remainders with no evidence:** When FR11's reading is
  neither `rm` nor `git`, and when the reading could not be performed at all,
  neither route is entered and today's blanket `allow` is kept.
  `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` /
  `$(which node) script.js` / `$(which ls) -la` / `$(which cp) -rf src dst` /
  `$(which cp) -Rf src dst` / `$(which chmod) -Rf 755 build` /
  `$(which chown) -Rf user:group /srv/app` / `$(which tar) -rf archive.tar file.txt` /
  `$(which grep) -rf patterns.txt src` / `$(which grep) -r pattern src` /
  `$(which rsync) -rf src/ dst/` / `$(which scp) -rf host:/a /b` are all `allow`.
  The discriminator is command-name evidence, not flag shape, and no path exists on
  which a substitution-headed spelling is judged more strictly than the plain one.
- **FR4 - Quote judgement at the payload argument position (only when the whole word is a substitution):**
  The quote judgement at the `-c` / `eval` / `<<<` payload argument position takes
  as its precondition that the word at that position is a substitution in its
  entirety (`.substitution_only`). Today's partial-match test
  (`QUOTED_MARK in quoted_args[idx + 1]`), which stops the promotion merely because
  a quoted substitution appears somewhere inside the word, is wrong: it disables
  the whole rescan of a `-c` body that mixes quoted substitutions (`"$(pwd)"` /
  `"$(date)"` / `"$(dirname ...)"`) with destructive commands, regressing `deny` to
  `allow`. The `-c` side is made symmetric with the here-string side (the existing
  ordering that tests `.substitution_only` first). Only when the payload word is a
  quoted substitution in its entirety is the promotion to the next word skipped —
  the word does not vanish even on empty expansion — and that position itself is
  treated as the payload boundary (trailing arguments are the real shell's `$0`).
- **FR5 - Preserving the promotion behaviour for unquoted substitutions:** The
  promotion behaviour for unquoted `$(...)` / backticks is kept as is. The `deny`
  expectations of `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'`, the
  backtick spelling, `sh -c $(true) 'git reset --hard HEAD'` and
  `bash <<<$(true) 'rm -rf /home/sakura/valuable'` are unchanged.
- **FR6 - Inverting the expectation and rewriting the label of the quoted `-c` payload case:**
  The case `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` is kept
  rather than deleted, and its expectation changes from `deny` to `allow`. Its
  label is rewritten from "the price of fail-closed: quoting cannot be
  distinguished statically" to the fact that the quote judgement now matches real
  shell semantics (the second argument is `$0`). Against
  `.claude/rules/hook-tests.md`'s "never delete existing deny / ask cases", the
  response is to retain the case itself as an `allow`-side false-positive guard.
- **FR7 - Writing down the out-of-scope declaration:**
  `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` stays `allow`, and
  its label is rewritten into the design decision that a form whose substitution
  result (i.e. the output of the substitution body) becomes the script body is out
  of scope for this hook's static analysis. The same range description is also
  placed in `extract_shell_payload()`'s docstring, so that the reason text, the
  label and the docstring agree. The form FR11 cannot handle — a substitution-headed
  form whose command name cannot be read statically, e.g.
  `$(cat cmdfile) -rf /home/sakura/valuable` — is written down in the same place as
  part of the same out-of-scope declaration.
- **FR8 - Adding cases:** `destructive-guard-cases.json` carries the commands of
  TS-1 through TS-33 in the three-element `[expected decision, label, command]`
  form. The existing entries (those corresponding to TS-1 through TS-12) are kept
  and the new TS-13 through TS-33 are added. Both sides are included: the `deny`
  side (operand-first, recursive-without-force, mixed `-c` bodies) and the `allow`
  side (non-rm/git commands taking recursive + force flags, substitution-head +
  `clean -fd` / `reset --hard` shapes, the quoted here-string, and the unreadable
  form). The labels of the existing TS-6 / TS-7 are rewritten because their
  rationale changes from "does not reach the rm shape floor" to "no readable
  evidence that the command is rm" (the `allow` expectation is unchanged).
- **FR9 - Updating the mirror-divergence note:** The mirror note in the docstrings
  of `head()` / `git_subcommand()` — that `failed-run-cleanup-guard.py` does not
  know `Tok.substitution_only` and that the skip added here is local to this file —
  is extended to state that the branches added by FR1 / FR2 / FR11 / FR13 and the
  new function are likewise local. The code of `failed-run-cleanup-guard.py` and
  `muse_guard.py` is not changed (neither file references a single symbol this
  feature touches).
- **FR10 - Raising the plugin version:** Per
  `.claude/rules/core-plugin-version-bump.md`, raise the `version` in
  `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of
  `.claude-plugin/marketplace.json` to the same next patch value within the same
  change. It is a behaviour fix, so the step is a patch.
- **FR11 - Reading the command name statically out of the command-position substitution:**
  Take the raw substitution text (`$(...)` or backticks) corresponding to the
  `.substitution_only` token that was skipped at the command-word position, out of
  the pre-lexing segment body. Split that body on whitespace, take the last word,
  and take everything after the final `/` (the basename) as the "statically read
  command name": `$(which rm)` → `rm`, `$(command -v rm)` → `rm`,
  `$(which cp)` → `cp`, `$(hatch env find)` → `find`. Any of the following counts as
  "could not read", and the FR1 / FR2 routes are not entered: the substitution body
  is empty; the last word starts with `-`; the raw text cannot be mapped to the
  token position; a nested substitution makes the raw text's extent
  indeterminable. The reading is done with string processing only — no substitution
  execution, no subprocess launch and no filesystem access whatsoever (NFR1). An
  arbitrary word inside the body matching `rm` / `git` is never taken as evidence
  (a form like `$(git config alias.x) -rf <path>` would otherwise produce a false
  `deny`).
- **FR12 - Making the quoted here-string branch's inversion explicit:** The fact
  that a quoted here-string — `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'`,
  where the here-string target is a quoted substitution in its entirety and a
  destructive command follows as a trailing argument — inverts from `deny` to
  `allow` is stated as an acceptance criterion and pinned in
  `destructive-guard-cases.json` as an `allow` case. The label records that the
  inversion aligns with real shell semantics (the here-string body is executed and
  the trailing argument is `$0`). The `deny` for the unquoted here-string
  (`bash <<<$(true) 'rm -rf /home/sakura/valuable'`) is unchanged (FR5).
- **FR13 - Extracting the substitution-head routing into a function:** The
  substitution-head token-structure classification currently inlined in `main()`'s
  loop — judging `_skip_to_command_word()`'s result, reading the command-name
  evidence, and handing off to the rm / git routes — is extracted into a single
  named function (e.g. `_check_substitution_head(words, segment)`) placed next to
  where `_rm_route_candidate()` was. The condition is that the route's entry
  condition ends up in one testable place, with only the call left in `main()`.
  `_rm_route_candidate()`, which loses its purpose, is deleted.

### Non-Functional Requirements

- **NFR1 - Determinism of the decision:** The decision stays deterministic. No
  filesystem access (`realpath` / `stat`), no subprocess launch and no substitution
  execution. The only decision material is the command string. Reading the
  substitution's raw text statically (FR11) is neither expansion nor evaluation and
  therefore sits inside this constraint.
- **NFR2 - Preserving existing expectations:** Existing case expectations are
  unchanged except for the one FR6 inverts and the one FR12 makes explicit. In
  particular the non-substitution commands, the regression-guard (A)/(B) groups, the
  false-positive-guard (A)/(B) groups and the trailing `ask` group keep today's
  decisions and reason ids. Existing `deny` / `ask` cases are not deleted.
- **NFR3 - Cost of a false positive:** The cost of a false positive is the same
  order as the cost of a miss (`.claude/rules/hook-tests.md`). An implementation
  that falls back uniformly to `ask` is not adopted. Because `ask` is demoted to
  `deny` under unattended execution, any change that could halt the happy path is
  landed only after the `allow`-side cases pin it.
- **NFR4 - Invariance of the demotion path:** The `ask` → `deny` unattended demotion
  (`decide()` / `unattended()`) is not changed. The demotion cases at the end of
  run-destructive-guard.py keep passing.
- **NFR5 - Change scope:** The change scope is limited to
  `em-workflow/hooks/destructive-guard.py`,
  `em-workflow/hooks/tests/destructive-guard-cases.json` and FR10's two version
  files. `failed-run-cleanup-guard.py` / `muse_guard.py` are not touched.
- **NFR6 - Test independence:** The tests carry no external dependency. Added cases
  follow the existing three-element JSON form; no new runner and no new dependency
  is introduced.
- **NFR7 - Equivalence with the plain spelling:** The substitution-headed spelling's
  decision tier and reason id match the decision produced by giving the same
  remaining arguments to the plain spelling of the command name FR11 read. What is
  `allow` in the plain spelling is never `deny` / `ask` in the substitution-headed
  spelling (never stricter). When the command name cannot be read, the route is not
  entered, so the decision is identical to the pre-change one.

## Implementation Approach

### Architecture

The decision is a static analysis over a single command string; the change stays
inside the existing stages.

```
Command string
      │
      ▼
  Lexing (Tok / UNRESOLVED_MARK / QUOTED_MARK / SUBSTITUTION_STANDIN)  ← structure unchanged (AS-6)
      │
      ├─ extract_shell_payload()        ← FR4 / FR5 / FR12: whole-word quote judgement at the payload position
      │
      ▼
  head() / git_subcommand()             ← FR9: mirror note extended
      │
      ▼
  _check_substitution_head()            ← FR13: the single extracted entry point
      │     └─ command-name evidence reading (FR11)
      │
      ▼
  check_rm() / check_git()              ← FR1 / FR2: tier and reason id used as returned (AS-1)
      │
      ▼
  decide() / unattended()               ← unchanged (NFR4)
```

**Component Diagram:**

```
destructive-guard.py
  ├─ extract_shell_payload()      : -c / eval / <<< payload extraction (FR4, FR5, FR12, FR7 docstring)
  ├─ _payload_index()             : payload word position (a whole-word quoted substitution is not promoted)
  ├─ head()                       : statement command word (FR9 mirror note)
  ├─ git_subcommand()             : git subcommand extraction (FR2 route, FR9 mirror note)
  ├─ _skip_to_command_word()      : skipping .substitution_only at the command-word position
  ├─ _check_substitution_head()   : NEW — substitution-head routing, one testable entry condition (FR13)
  │     └─ command-name evidence  : last word of the substitution body → basename (FR11)
  ├─ _rm_route_candidate()        : DELETED (FR13)
  ├─ check_rm()                   : rm shape decision (only its caller set grows; threshold unchanged)
  ├─ check_git()                  : git shape decision (only its caller set grows)
  └─ decide() / unattended()      : tier finalization and unattended demotion (unchanged)
```

### Data Flow

```
Bash command string → lexing → payload extraction → command-word resolution
  → command-name evidence (FR11) → rm / git route → decision (allow/ask/deny) + reason id
```

### API Design

Not applicable. The PreToolUse hook's input/output format is unchanged.

### Database Schema

Not applicable. No persistent data is handled.

### Dependencies

**Internal Dependencies:**

- `em-workflow/hooks/destructive-guard.py`: the decision logic itself.
- `em-workflow/hooks/tests/destructive-guard-cases.json`: the
  `[expected decision, label, command]` three-element cases.
- `em-workflow/hooks/tests/run-destructive-guard.py`: the case runner.
- `em-workflow/hooks/failed-run-cleanup-guard.py` / `em-workflow/hooks/muse_guard.py`:
  the mirror targets of `head()` / `git_subcommand()`. Their code is not changed;
  only the mirror note in this file's docstrings is updated (FR9, AS-9).

**External Dependencies:**

None. The tests carry no external dependency (NFR6).

### File Structure

```
em-workflow/
├── hooks/
│   ├── destructive-guard.py                 # FR1-FR5, FR7, FR9, FR11, FR12, FR13
│   └── tests/
│       └── destructive-guard-cases.json     # FR6, FR7, FR8, FR12
├── .claude-plugin/
│   └── plugin.json                          # FR10 (version)
.claude-plugin/
└── marketplace.json                         # FR10 (version)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-command-name-substitution/**`
- `test-docs/destructive-guard-command-name-substitution/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers
`test-docs/destructive-guard-command-name-substitution/{T}.tests.yaml`, the
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

### Unit Tests

- [ ] TS-1 (FR1, FR11): `$(which rm) -rf /home/sakura/valuable` → `deny`. Ticket reproduction; an rm destructive shape whose command name comes from a substitution.
- [ ] TS-2 (FR1, FR11): `` `which rm` -rf /home/sakura/valuable `` → `deny`. Symmetry across both spellings (backtick side).
- [ ] TS-3 (FR2, FR11): `$(which git) reset --hard HEAD` → `deny`. The equivalent form in the git subcommand shape.
- [ ] TS-4 (FR2, FR11): `$(which git) clean -fd` → `deny`. The equivalent form in the git-clean shape.
- [ ] TS-5 (FR3): `$(which node) script.js` → `allow`. False-positive guard; no rm/git evidence.
- [ ] TS-6 (FR3, FR8): `$(which ls) -la` → `allow`. False-positive guard; flag-first but no rm evidence (label rewritten).
- [ ] TS-7 (FR3, FR8): `$(which grep) -r pattern src` → `allow`. False-positive guard; has a recursive flag but grep carries no rm evidence (label rewritten, pinned allow).
- [ ] TS-8 (FR1, NFR7): `$(which rm) -rf dist` → `allow`. Inheriting the safe-route (build artifact) exception.
- [ ] TS-9 (FR1, NFR7): `$(which rm) -rf /tmp/scratch/x` → `allow`. Inheriting the scratch-root exception.
- [ ] TS-10 (FR4, FR6): `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` → `allow`. Expectation inversion of an existing case; the second argument is `$0` in a real shell.
- [ ] TS-11 (FR4): `eval "$(ssh-agent -s)"` → `allow`. Happy path pinned; a quoted substitution payload is not stopped.
- [ ] TS-12 (FR7): `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` → `allow`. Allowed after the out-of-scope range is written down.
- [ ] TS-13 (FR1, NFR7): `$(which rm) /home/sakura/valuable -rf` → `deny`. Operand-first spelling; pins the removal of the dash pre-gate.
- [ ] TS-14 (FR1, NFR7): `$(which rm) /home/sakura -rf` → `deny`. Operand-first spelling against a home-root target.
- [ ] TS-15 (FR1, NFR7): `$(which rm) -r /home/sakura/valuable` → `deny`. Recursive without force; aligned with `check_rm()`'s own threshold.
- [ ] TS-16 (FR1, NFR7): `$(which rm) -R /home/sakura/valuable` → `deny`. Recursive without force (uppercase spelling).
- [ ] TS-17 (FR1, NFR7): `$(which rm) --recursive /home/sakura/valuable` → `deny`. Recursive without force (long spelling).
- [ ] TS-18 (FR3, NFR7): `$(which cp) -rf src dst` → `allow`. False-positive guard; the plain cp form is allow, so this is equivalent.
- [ ] TS-19 (FR3, NFR7): `$(which cp) -Rf src dst` → `allow`. False-positive guard; identical for the uppercase spelling.
- [ ] TS-20 (FR3, NFR7): `$(which chmod) -Rf 755 build` → `allow`. False-positive guard; chmod legitimately takes recursive and force.
- [ ] TS-21 (FR3, NFR7): `$(which chown) -Rf user:group /srv/app` → `allow`. False-positive guard; chown is the same shape.
- [ ] TS-22 (FR3, NFR7): `$(which tar) -rf archive.tar file.txt` → `allow`. False-positive guard; tar's `-r` is append and `-f` names the file.
- [ ] TS-23 (FR3, NFR7): `$(which grep) -rf patterns.txt src` → `allow`. False-positive guard; grep's `-f` is a pattern file.
- [ ] TS-24 (FR3, NFR7): `$(which rsync) -rf src/ dst/` → `allow`. False-positive guard.
- [ ] TS-25 (FR3, NFR7): `$(which scp) -rf host:/a /b` → `allow`. False-positive guard.
- [ ] TS-26 (FR2, NFR7): `$(which make) clean -fd` → `allow`. False-positive guard; pins the removal of the unconditional git-route call.
- [ ] TS-27 (FR2, NFR7): `$(hatch env find) reset --hard` → `allow`. False-positive guard; substitution-head + git subcommand shape but no git evidence.
- [ ] TS-33 (FR7, FR11): `$(cat cmdfile) -rf /home/sakura/valuable` → `allow`. A substitution-headed form whose command name cannot be read statically is out of scope; accompanied by writing the limit down.

### Integration Tests

- [ ] TS-28 (FR4): `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` → `deny`. A `-c` body mixing a quoted substitution with a destructive command.
- [ ] TS-29 (FR4): `sh -c 'echo "$(date)" && rm -rf /home/sakura/valuable'` → `deny`. Same, mixed form (date substitution).
- [ ] TS-30 (FR4): `bash -c 'echo "$(pwd)"; git reset --hard HEAD'` → `deny`. Same, a git destructive command in a mixed body.
- [ ] TS-31 (FR12): `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` → `allow`. Pins the quoted here-string's decision inversion explicitly.
- [ ] TS-32 (FR5): `bash <<<$(true) 'rm -rf /home/sakura/valuable'` → `deny`. The unquoted here-string's promotion `deny` is unchanged (control).
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes for every case (AC-9).
- [ ] `python3 -m unittest discover -s tests` produces a failing-test-ID set identical to the base revision's, with zero new failures (AC-10).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] The unquoted promotion forms (`bash -c $(printf %s) 'rm -rf /home/sakura/valuable'`,
  the backtick spelling, `sh -c $(true) 'git reset --hard HEAD'`,
  `bash <<<$(true) 'rm -rf /home/sakura/valuable'`) stay `deny` (AC-7, FR5).
- [ ] A remainder that `check_git()` matches nothing against (`echo safe`, `status`)
  yields no decision (FR2).
- [ ] FR11 reports "could not read" when the substitution body is empty, when the
  last word starts with `-`, when the raw text cannot be mapped to the token
  position, or when a nested substitution makes the raw text's extent
  indeterminable; such statements stay `allow` (FR3, FR11, AS-7).
- [ ] An arbitrary word inside the substitution body is never evidence: a form like
  `$(git config alias.x) -rf <path>` must not produce a false `deny` (FR11, AS-4).
- [ ] A command containing no substitution returns the same decision and the same
  reason text as before (AC-12).
- [ ] `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` /
  `bash -c "$(cat script.sh)"` are `allow` (AC-6).

### Performance Tests

Not applicable.

## Security Considerations

- **Input Validation:** The only decision material is the command string. No
  filesystem access (`realpath` / `stat`), no subprocess launch, no substitution
  execution (NFR1, AC-22).
- **Detection Scope:** A statement whose command-word position is a substitution
  enters the rm / git route only on statically read command-name evidence
  (FR1, FR2, FR11).
- **Detection Limits (declared out of scope):** A form whose substitution result
  (the output of the substitution body) becomes the script body, and a
  substitution-headed form whose command name cannot be read statically, are both
  out of scope for this hook's static analysis (FR7, AC-21). This is a deliberate
  narrowing of detection range relative to a shape-only implementation (AS-5).
- **No Added Strictness:** A substitution-headed spelling is never judged more
  strictly than the plain spelling of the same command name (NFR7).
- **Unattended Behaviour:** `ask` is demoted to `deny` under unattended execution;
  the demotion path is not changed (NFR3, NFR4).

## Error Handling

### Decision tiers and reason ids

| Reason id | Decision | Condition |
|-----------|----------|-----------|
| `rm-recursive` | deny | The command-word position is a substitution, FR11 reads the name as `rm`, and `check_rm()` decides on the remaining tokens (FR1, AC-1, AC-13, AC-14) |
| `git-reset-hard` | deny | The command-word position is a substitution, FR11 reads the name as `git`, and the remainder is the `reset --hard` shape (FR2, AC-2) |
| `git-clean` | deny | The command-word position is a substitution, FR11 reads the name as `git`, and the remainder is the `clean -fd` shape (FR2, AC-2) |

The decision tier (`deny` / `ask`) and the reason id are exactly what the existing
`check_rm()` / `check_git()` return; no new tier and no new reason id is created
(AS-1). When FR11 cannot read a name, or reads a name other than `rm` / `git`,
neither route is entered and the result is today's blanket `allow` (FR3, AS-5).

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC-1: `$(which rm) -rf /home/sakura/valuable` is `deny` with reason id `rm-recursive`; the backtick spelling behaves the same.
- [ ] AC-2: `$(which git) reset --hard HEAD` is `deny` / `git-reset-hard`, and `$(which git) clean -fd` is `deny` / `git-clean`.
- [ ] AC-3: `$(true) echo safe` / `env $(true) echo safe` / `git $(true) status` / `$(which node) script.js` / `$(which ls) -la` are `allow`.
- [ ] AC-4: `$(which rm) -rf dist` and `$(which rm) -rf /tmp/scratch/x` are `allow` (the existing safe-route exception is inherited).
- [ ] AC-5: `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` is `allow`, and the case is not deleted from cases.json — it stays with a rewritten label.
- [ ] AC-6: `eval "$(ssh-agent -s)"` / `eval "$(direnv export bash)"` / `eval "$(mise activate zsh)"` / `bash -c "$(cat script.sh)"` are all `allow`.
- [ ] AC-7: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'` / the backtick spelling / `sh -c $(true) 'git reset --hard HEAD'` / `bash <<<$(true) 'rm -rf /home/sakura/valuable'` stay `deny`.
- [ ] AC-8: `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` is `allow`, and its label together with `extract_shell_payload()`'s docstring state the same range: a form whose substitution result becomes the script body is out of scope.
- [ ] AC-9: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes for every case.
- [ ] AC-10: The set of failing test IDs from `python3 -m unittest discover -s tests` matches the base revision's set exactly, with zero new failures introduced by this change (the base carries 6 pre-existing failures unrelated to this feature; matching counts is not enough — the comparison is per test ID). The pre-existing failures are filed as a separate task and placed outside this feature's change scope (NFR5).
- [ ] AC-11: The em-workflow `version` in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` is the same value and at least one patch ahead of the previous value.
- [ ] AC-12: For commands containing no substitution, the changed hook returns the same decision and the same reason text as before.
- [ ] AC-13: The operand-first spelling `$(which rm) /home/sakura/valuable -rf` is `deny` / `rm-recursive`; `$(which rm) /home/sakura -rf` is `deny` too.
- [ ] AC-14: Recursive-without-force forms `$(which rm) -r /home/sakura/valuable` / `$(which rm) -R /home/sakura/valuable` / `$(which rm) --recursive /home/sakura/valuable` are all `deny` / `rm-recursive`.
- [ ] AC-15: Non-rm/git commands that legitimately take recursive + force flags are `allow`: `$(which cp) -rf src dst` / `$(which cp) -Rf src dst` / `$(which chmod) -Rf 755 build` / `$(which chown) -Rf user:group /srv/app` / `$(which tar) -rf archive.tar file.txt` / `$(which grep) -rf patterns.txt src` / `$(which rsync) -rf src/ dst/` / `$(which scp) -rf host:/a /b`.
- [ ] AC-16: Non-git commands in the substitution-head + git-subcommand shape are `allow`: `$(which make) clean -fd` / `$(hatch env find) reset --hard`.
- [ ] AC-17: `$(which grep) -r pattern src` stays `allow`, and its label states the new rationale: no readable evidence that the command is `rm`.
- [ ] AC-18: All three `-c` bodies that mix a quoted substitution with a destructive command are `deny`: `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` / `sh -c 'echo "$(date)" && rm -rf /home/sakura/valuable'` / `bash -c 'echo "$(pwd)"; git reset --hard HEAD'`.
- [ ] AC-19: The quoted here-string `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` is `allow`, and its inversion from `deny` is recorded both in the acceptance criteria and in the case table.
- [ ] AC-20: The substitution-head routing is extracted from `main()` into one named function, `main()` retains only the call, and `_rm_route_candidate()` is deleted.
- [ ] AC-21: The statically unreadable substitution-headed form (`$(cat cmdfile) -rf /home/sakura/valuable`) stays `allow`, and that limit is written down as part of the out-of-scope declaration in the case label and the docstring.
- [ ] AC-22: FR11's reading is performed with string processing only — no substitution execution, no subprocess launch, no filesystem access (NFR1).

## Assumptions

- AS-1: Neither `deny` nor `ask` is newly introduced; FR1 / FR2 adopt the tier and
  reason id that the existing `check_rm()` / `check_git()` return for the remaining
  tokens. (reversible)
- AS-2: The route's entry discriminator is "the command name read statically out of
  the command-word-position substitution is `rm` / `git`", not the tokens' flag
  shape. Inference from shape alone (generation 1) was shown by review round 1's
  measurements to produce a false `deny` and a miss at the same time, so it is
  removed. (reversible)
- AS-3: Once the rm route is entered, the threshold is left to `check_rm()` itself
  (recursion presence, `RM_ROOT_SHAPE`, the safe-route exceptions); the route side
  adds no further floor. TS-7 stays `allow` because grep carries no rm evidence, so
  dropping the force-flag requirement does not create a false `deny`. (reversible)
- AS-4: The command name is read as "the basename of the last word of the
  substitution body". A match against an arbitrary word in the body is not adopted
  (it would produce a false `deny` on forms where `rm` / `git` appears as another
  command's argument). (reversible)
- AS-5: A substitution-headed form whose command name cannot be read statically is
  not routed and stays `allow`. Generation 1's shape-only implementation denied
  this form, so this is a deliberate narrowing of the detection range. Falling back
  uniformly to `ask` is not adopted, per NFR3 and generation 1's settled answer
  (`narrow_destructive_shape`). (reversible)
- AS-6: The marker structure (`UNRESOLVED_MARK` / `QUOTED_MARK` /
  `SUBSTITUTION_STANDIN` / `Tok`'s attributes) is not changed. Reading the raw text
  is done as string processing over the segment body; no information is carried on
  the token side. (reversible)
- AS-7: Mapping the substitution's raw text to the token position relies on the
  order of substitution occurrences in the segment body matching the order of
  marker occurrences. For an input where the mapping cannot be established, the
  result is "could not read" and the route is not entered (falling open).
  (reversible)
- AS-8: cases.json's existing `deny` / `ask` cases keep their expectations except
  for the one FR6 inverts and the one FR12 makes explicit. Nothing is deleted.
  (reversible)
- AS-9: `failed-run-cleanup-guard.py` / `muse_guard.py` receive no code change;
  neither file references any of the symbols this feature touches — confirmed.
  (reversible)
- AS-10: AC-10 is read as "the failing-test-ID set matches the base exactly, with
  zero new failures" rather than the literal "everything passes" that the goal
  block's DoD words. The same 6 tests fail on base / main, and resolving the
  pre-existing red is outside the change scope (NFR5). The pre-existing red is
  filed as a separate task. (reversible)

## Constraints

- The only decision material is the command string; no filesystem access, no
  subprocess launch, no substitution execution (NFR1).
- The change scope is 4 files (NFR5 plus FR10).
- The tests carry no external dependency and follow the existing three-element JSON
  form (NFR6).
- The test commands are `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  and `python3 -m unittest discover -s tests`.
- `.claude/rules/hook-tests.md`: existing `deny` / `ask` cases are never deleted.
- `.claude/rules/core-plugin-version-bump.md`: raise the version in two places to
  the same value within the same change.

## Out of Scope

- Analysing a form whose substitution result (the output of the substitution body)
  becomes the script body (FR7).
- Detecting a substitution-headed form whose command name cannot be read statically,
  e.g. `$(cat cmdfile) -rf /home/sakura/valuable` (FR7, AS-5).
- Code changes to `failed-run-cleanup-guard.py` / `muse_guard.py` (FR9, NFR5, AS-9).
- Resolving the 6 pre-existing test failures on the base revision; they are filed as
  a separate task (AS-10).
- The design step (skipped). This feature has no UI and `design_system_candidates`
  is empty with `kind: none`; running design would create tokens.yaml / tokens.html
  in a repository that has no UI. The lexer-layer contract decisions and the
  false-positive tolerance are carried by create-plan's IMPLEMENTATION.md.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. FR1–FR13 and NFR1–NFR7 all have `status: resolved`.

## References

- Requirements document: `feature-docs/destructive-guard-command-name-substitution/REQUIREMENTS.md`
- Hook implementation: `em-workflow/hooks/destructive-guard.py`
- Case definitions: `em-workflow/hooks/tests/destructive-guard-cases.json`
- Case runner: `em-workflow/hooks/tests/run-destructive-guard.py`
- Mirror targets (unchanged): `em-workflow/hooks/failed-run-cleanup-guard.py`, `em-workflow/hooks/muse_guard.py`
- Hook test rules: `.claude/rules/hook-tests.md`
- Version bump rule: `.claude/rules/core-plugin-version-bump.md`
