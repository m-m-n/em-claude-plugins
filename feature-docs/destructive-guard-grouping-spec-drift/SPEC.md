# Feature: destructive-guard-grouping-spec-drift

## Overview

Wrapping a command in a grouping or compound construct (`( )`, `{ }`, if/elif/else, for/select, while/until, `!`, case, function definitions) currently makes `em-workflow/hooks/destructive-guard.py` skip every check on that command. Under `ALLOW_NON_DESTRUCTIVE=True` those commands end in an unconditional allow. This feature makes the command inside such constructs receive the same verdict as when written alone, settles the three SPEC-versus-implementation drifts deferred from feature `destructive-guard-write-target-scoping` (review round2 high findings `bb74a3458679e1b4`, `bafd6e8260de4337`, `7f7144aea35f534f`), and pins every detection-strength change with cases in the case table.

Requirement source: `feature-docs/destructive-guard-grouping-spec-drift/REQUIREMENTS.md`.

## Objectives

- Close the bypass where wrapping a command in a grouping or compound construct makes `em-workflow/hooks/destructive-guard.py` skip every check: `( )`, `{ }`, if/elif/else, for/select, while/until, `!`, case, and function definitions. Under `ALLOW_NON_DESTRUCTIVE=True` those commands currently end in an unconditional allow.
- Settle the three SPEC-versus-implementation drifts left deferred from feature `destructive-guard-write-target-scoping` (review round2 high findings `bb74a3458679e1b4`, `bafd6e8260de4337` and `7f7144aea35f534f`) so that the prior feature's SPEC.md and REQUIREMENTS.md describe what the merged implementation actually does.
- Every change to detection strength comes with ask/allow cases in `em-workflow/hooks/tests/destructive-guard-cases.json`, as `.claude/rules/hook-tests.md` requires, so a later regression is caught by the suite.

## User Stories

### US1: Grouping does not bypass the guard
As an unattended (`claude-batch`) run operator, I want a command inside a grouping or compound construct to get the same verdict as the same command written alone, so that wrapping a command in brackets or reserved words does not disable the safety net.

**Acceptance Criteria:**
- [ ] AC-4: The five ticket reproduction commands are ask in the runner (deny with `CLAUDE_BATCH=1`), matching bare `rm -rf $HOME/x`.
- [ ] AC-5: Through `( )`, `{ }`, if/elif/else, for, while/until, `!`, case and function definitions, the rm recursive-delete, git, self-modification and transcript-write verdicts match the same command written alone (FR1 cases).
- [ ] AC-6: The fused-closer forms `(cp /tmp/x ~/.claude/settings.json)` and `(cp /tmp/x ~/.claude/settings.json)>/dev/null` are ask, and `(rm -rf /tmp/x)>/dev/null` is allow.

### US2: No new false positives
As an unattended run operator, I want reserved words and grouping characters used as data to stay allow, so that closing the bypass does not stop a run on a false positive.

**Acceptance Criteria:**
- [ ] AC-7: Every existing case keeps its command and expected verdict. Only the mv label from FR9 changes.
- [ ] AC-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case, including the trailing unattended-demotion case, and exits 0.

### US3: The prior feature's documents match its implementation
As a maintainer of `destructive-guard.py`, I want the prior feature's SPEC.md and REQUIREMENTS.md to describe the merged implementation, and every detection-strength change to be pinned by cases, so that the same drift findings do not recur and regressions are caught.

**Acceptance Criteria:**
- [ ] AC-8: tar `-C` is a write target only in extract mode (`tar -cf /tmp/backup.tar -C ~/.claude/skills .` is allow, `tar -xzf /tmp/a.tgz -C ~/.claude/skills` is ask), and each of the six families has at least one ask case and one allow case.
- [ ] AC-9: Cases for `sudo -u` / `bash -c` / `eval`-routed rm exist and pass.
- [ ] AC-10: In `feature-docs/destructive-guard-write-target-scoping/SPEC.md` and REQUIREMENTS.md, FR2(c)/(d), the Edge Cases mv line and FR6 match the implementation's behaviour for mv, the six destination families and `head()`/`statements()`.

## Technical Requirements

### Functional Requirements

- **FR1 - Add grouping/compound-construct cases before the fix:** Before any change to `destructive-guard.py`, add cases to `em-workflow/hooks/tests/destructive-guard-cases.json` in `[expected, label, command]` form, then run the suite and confirm it is red. Expected verdicts are the ones the runner produces (`CLAUDE_BATCH` cleared).
  - (1) The five ticket reproductions, each expected `ask` to match bare `rm -rf $HOME/x`: `( rm -rf $HOME/important )`, `{ rm -rf $HOME/important; }`, `if true; then rm -rf $HOME/x; fi`, `for f in a; do rm -rf $HOME/x; done`, `! rm -rf $HOME/x`.
  - (2) Literal-target parity, each expected `deny` to match bare `rm -rf /home/sakura/x`: `( rm -rf /home/sakura/x )`, `(rm -rf /home/sakura/x)`, `{ rm -rf /home/sakura/x; }`, `if true; then rm -rf /home/sakura/x; fi`, `if false; then :; elif true; then :; else rm -rf /home/sakura/x; fi`, `if rm -rf /home/sakura/x; then :; fi`, `while true; do rm -rf /home/sakura/x; done`, `until rm -rf /home/sakura/x; do :; done`, `for f in a; do rm -rf /home/sakura/x; done`, `! rm -rf /home/sakura/x`, `case x in a) rm -rf /home/sakura/x;; esac`, `case x in (a) rm -rf /home/sakura/x;; esac`, `case x in a|b) rm -rf /home/sakura/x;; esac`, the multi-line form below, `f() { rm -rf /home/sakura/x; }; f`, `function f { rm -rf /home/sakura/x; }; f`, `( { rm -rf /home/sakura/x; } )`, `if true; then ( sudo rm -rf /home/sakura/x ); fi`, `bash -c '( rm -rf /home/sakura/x )'`, `echo $(if true; then rm -rf /home/sakura/x; fi)`.

    ```
    case $x in
      a) rm -rf /home/sakura/x ;;
    esac
    ```

  - (3) git parity (deny): `( git reset --hard HEAD~1 )`, `{ git push --force origin main; }`, `if true; then git clean -fdx; fi`.
  - (4) self-modification parity (ask): `(cp /tmp/x ~/.claude/settings.json)`, `(cp /tmp/x ~/.claude/settings.json)>/dev/null`, `{ tee ~/.claude/settings.json < /tmp/x; }`, `for f in a; do mv /tmp/x ~/.claude/hooks/x.py; done`, `for f in a; do echo $f; done > ~/.claude/settings.json`.
  - (5) transcript-write parity (deny): `(mv ~/.claude/projects/x/y.jsonl /tmp/y.jsonl)`, `if true; then cp /tmp/x ~/.claude/projects/a/b.jsonl; fi`.
  - (6) Other per-statement checks: `( find /home/sakura -name '*.log' -delete )` (deny), `{ chmod -R 777 /home/sakura/x; }` (ask).
  - (7) False-positive guards (allow): `( rm -rf /tmp/x )`, `(rm -rf node_modules)`, `(rm -rf /tmp/x)>/dev/null`, `if [ -d /tmp/x ]; then rm -rf /tmp/x; fi`, `( cd /tmp && ls )`, `{ echo hi; } 2>/dev/null`, `f() { echo hi; }; f`, `echo if then fi do done`, `echo "( rm -rf /home/sakura/x )"`, `echo '{ rm -rf /home/sakura/x; }'`, `for f in rm -rf /home/sakura/x; do echo $f; done`, `case x in rm) echo hi;; esac`, the here-doc data form below, `git commit -m 'fix: ( rm -rf ) in docs'`.

    ```
    cat <<'EOF'
    if true; then rm -rf /home/sakura/x; fi
    EOF
    ```

  The red confirmation applies to the cases whose verdict changes with the fix. Cases that already pass, such as the pinned allow forms, stay in as regression guards.
- **FR2 - Judge the command inside grouping and compound constructs:** The command that grouping or compound syntax puts at command position gets the same verdict as the same command written alone. This covers the subshell opener `(` (only an unquoted operator token), the brace-group opener `{`, the reserved words `if`, `then`, `elif`, `else`, `while`, `until`, `do`, and `!`, case patterns (`case WORD in`, then an optional `(`, the pattern alternatives and `)`, including patterns split across statements by `|` or newlines), and function definitions (`NAME() {`, `function NAME {`, `function NAME() {`). A function body is judged as if it runs. The `for`/`select` header (`for NAME in WORDS`) is not a command, and the words after `in` are never judged as a command. Closers and terminators (`)`, `}`, `fi`, `done`, `esac`, `;;`) carry no command of their own. A redirect attached to one is still judged as a write target (`... done > ~/.claude/settings.json` stays ask). Nested and combined forms unwrap fully, including grouping combined with the existing VAR=value, `WRAPPERS` and substitution-headed skips. The setting is answer grouping-scope = all_including_case.
- **FR3 - A fused closing token never becomes an argument or target:** A bare `)` operator token that closes a subshell or case pattern is never counted among a command's arguments by any check: rm targets, write targets (cp/ln/rsync positional-last, mv/rm/chmod/chown non-flag arguments, `INPLACE_WRITERS`), git, file-destruction, external or permission checks. This includes a closer fused to its argument list (`(rm -rf /tmp/x)`, `(cp /tmp/x ~/.claude/settings.json)`, where `)` directly follows the last argument). A closer fused with a following redirect operator (`)>`, `)>>`, `)2>` and similar, for example `(cp /tmp/x ~/.claude/settings.json)>/dev/null`) splits into the closer and a real redirect. The redirect target is then judged only as a redirect target, never as the command's destination or an rm target. So `(rm -rf /tmp/x)>/dev/null` is allow, matching `rm -rf /tmp/x > /dev/null`, and `(cp /tmp/x ~/.claude/settings.json)>/dev/null` is ask. A quoted `")"` or `"("` is an ordinary word, so the pinned `git push "(" --force origin main` stays deny.
- **FR4 - No new false positives from reserved words or grouping characters as data:** Reserved words and grouping characters count as grouping syntax only at command position, and `(` only as an unquoted operator token. Every one of these stays allow: a reserved word in argument position (`echo if then fi do done`), grouping text inside quotes, here-doc bodies not aimed at a shell sink, commit messages, the words of a for/select header, and a case pattern whose text happens to be a command name. All existing cases keep their current verdicts. That includes the pinned `(cd /home/sakura && rm -rf ./x)` deny, `(true; X=/tmp/safe; false)>/dev/null; rm -rf $X` / `(X=/tmp/safe; true); rm -rf $X` / the newline subshell form (ask), the if/then HOME forms (deny), the for/while-read forms (ask) and `find /home/sakura \( -name '*.log' \) -delete` (deny). A subshell's trailing `)` is never mistaken for a case-pattern terminator.
- **FR5 - Scope boundary of the grouping fix:** The fix covers every per-statement check in `destructive-guard.py` `main()`: `check_rm` (rm-root / rm-recursive / rm-unresolvable), `check_git`, `check_file_destruction`, `check_external`, `check_permissions`, `check_self_modification` (self-modification and transcript-write), and the substitution-headed route. It applies equally to statements reached through `statements()`'s substitution-body, shell-sink here-doc and `-c` / eval / here-string payload re-scan. Unchanged: the deferral to `failed-run-cleanup-guard.py` (`matches_target_shape()` over `strip_grouping_prefix()`/`_deferral_head()`), so the existing `(silent)` and deferral-related allow cases keep their verdicts. `em-workflow/hooks/failed-run-cleanup-guard.py` is not modified. `head()` keeps its 2-tuple return shape. Any grouping-aware skip is documented in `destructive-guard.py` as local to this file, following the precedent of the `substitution_only` skip, and the mirror note in `head()`'s docstring says so. The `strip_grouping_prefix()` docstring sentence that says subshell- or brace-wrapped destructive commands stay unexamined by the other checks, and the matching `main()` comment, are rewritten to match the new behaviour.
- **FR6 - Keep the six destination families; count tar -C only in extract mode:** Keep destination detection for rsync (last positional after value-flag stripping), git clone (last positional when there are at least two positionals), unzip `-d`, curl `-o`/`--output` and wget `-O`/`--output-document`. Change tar so that the value of `-C` / `--directory` (separate, attached, `=` and cluster-tail spellings) is a write target only in extract mode. Extract mode means `-x`, `--extract`, `--get`, a short-option cluster containing `x` (`-xzf`), or the traditional dashless first argument containing `x` (`tar xzf a.tgz -C DIR`). In create (`-c`/`--create`), list (`-t`/`--list`) and every other mode, `-C` names a directory that is read and is not a write target. The setting is answer dest-families-scope = keep_fix_tar_mode.
- **FR7 - Cases for the six destination families, tar mode included:** Add to `destructive-guard-cases.json`, before the tar change, with the tar create/list allow cases confirmed red first:
  - rsync: `rsync -a /tmp/x/ ~/.claude/skills/` (ask), `rsync -a ~/.claude/skills/ /tmp/backup/` (allow).
  - git clone: `git clone https://x.example/r.git ~/.claude/skills/r` (ask), `git clone https://x.example/r.git /tmp/r` (allow), `git clone https://x.example/r.git` (allow).
  - tar extract: `tar -xzf /tmp/a.tgz -C ~/.claude/skills` (ask), `tar -xf /tmp/a.tar --directory=~/.claude/hooks` (ask), `tar xzf /tmp/a.tgz -C ~/.claude/hooks` (ask), `tar -xf /tmp/a.tar -C /tmp/out` (allow).
  - tar create/list: `tar -cf /tmp/backup.tar -C ~/.claude/skills .` (allow), `tar -tzf /tmp/a.tgz -C ~/.claude/skills` (allow), `tar --directory=~/.claude/hooks -cf /tmp/b.tar .` (allow), `tar --create -f /tmp/b.tar -C ~/.claude/skills .` (allow), `tar -cf - -C ~/.claude/skills . | tar -xf - -C /tmp/copy` (allow).
  - unzip: `unzip /tmp/a.zip -d ~/.claude/skills/` (ask), `unzip /tmp/a.zip -d /tmp/out` (allow).
  - curl: `curl -o ~/.claude/settings.json https://x.example/s.json` (ask), `curl -o ~/.claude/projects/a/b.jsonl https://x.example/l` (deny, transcript-write), `curl -o /tmp/s.json https://x.example/s.json` (allow).
  - wget: `wget -O ~/.claude/hooks/x.py https://x.example/x.py` (ask), `wget -O /tmp/x.py https://x.example/x.py` (allow), `wget -qO- https://x.example/a.txt` (allow).
- **FR8 - Pin the rm verdict changes that came from head()/statements() input shaping:** Add cases for the rm verdicts that the merged wrapper value-flag consumption (`WRAPPER_VALUE_FLAGS`) and the `-c` / eval / here-string payload re-scan introduced. Runner verdicts: `sudo -u root rm -rf $HOME/x` (ask), `bash -c 'rm -rf $HOME/x'` (ask), `eval 'rm -rf $HOME/x'` (ask), `sudo -u root rm -rf /home/sakura/x` (deny), `eval 'rm -rf /home/sakura/x'` (deny), `env -u NAME rm -rf /home/sakura/x` (deny), and the non-destructive control `sudo -u root ls /root` (allow). These already hold on the baseline, so they are pinning cases and are not expected to go red first. The implementation of this behaviour is not changed.
- **FR9 - Correct the misleading mv case label:** In `destructive-guard-cases.json`, rename the label of the existing case `mv ~/.claude/hooks/x.py extra.txt /tmp/y` from `mv 複数ソース + 宛先のみ判定` to a label saying that every non-flag argument of mv (sources included) is a write target, which is why a protected source gives ask. Its command and its expected verdict (ask) stay unchanged.
- **FR10 - Revise the prior feature's SPEC.md to match the implementation:** Edit `feature-docs/destructive-guard-write-target-scoping/SPEC.md` directly. The setting is answer spec-revision-location = edit_prior_spec_and_req.
  - (a) FR2: replace the closed three-source list with the sources the implementation uses. Those are (a) output redirects; (b) `INPLACE_WRITERS` and `sed -i`; (c) rm / chmod / chown non-flag arguments; mv: every non-flag argument, because mv unlinks each source, plus the `-t` / `--target-directory` value; cp / ln: the last positional argument after value-flag stripping, or only the `-t` / `--target-directory` value when that flag is given; (d) command-specific destinations: rsync last positional, git clone last positional, tar `-C` / `--directory` in extract mode only, unzip `-d`, curl `-o` / `--output`, wget `-O` / `--output-document`.
  - (b) Edge Cases: replace the `mv a b c dir/` line with the rule that a, b, c and dir/ are all write targets.
  - (c) FR6: say that the bodies of `check_rm` and `SAFE_DELETE` are unchanged, but `head()`'s wrapper value-flag consumption and `statements()`'s `-c` / eval / here-string payload re-scan changed the input `check_rm` receives. As a result `sudo -u root rm -rf $HOME/x`, `bash -c 'rm -rf $HOME/x'` and `eval 'rm -rf $HOME/x'` went from allow to ask (demoted to deny under `CLAUDE_BATCH`).
  - (d) Revise any other sentence in that SPEC that now contradicts the revised FR2/FR6: the architecture diagram's `(c) rm / mv / cp / ln / chmod / chown args` label, the component-diagram and Dependencies statements that `check_self_modification` is the only function changed, and the Data Flow description.
- **FR11 - Revise the prior feature's REQUIREMENTS.md with the same content:** Edit `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md` so it agrees with the revised SPEC.md. Places to change: 1.3 scope (the 対象外 line for `check_rm` / `SAFE_DELETE`), the 4.1 table rows FR2 and FR6, the FR2 description and its business rule (cp / mv / ln positional-last), the FR6 description, the 10.1 risk row that fixes the sources at three, the 12.1 boundary item `mv a b c dir/ の宛先は最後の 1 つ`, the section 13 glossary entry 書き込み先パス集合, and the 14.1 confirmed item on 対象引数. Wording follows the prior document's existing Japanese style.
- **FR12 - Bump the em-workflow version in two places (patch):** Following `.claude/rules/core-plugin-version-bump.md`, in the same change raise `version` in `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry's `version` in `.claude-plugin/marketplace.json` from 0.2.12 to 0.2.13. em-review's version does not change.

### Non-Functional Requirements

- **NFR1 - Static analysis only, deterministic:** Verdicts come from static analysis of the command string alone. No command runs, no substitution is evaluated, and no filesystem call or subprocess is added (`tests/test_destructive_guard_command_substitution.py` enforces the forbidden-call list). The same command always gets the same verdict.
- **NFR2 - Standard library only:** `destructive-guard.py` and its tests import only the Python standard library (`test/README.md`; enforced by `test_module_uses_only_standard_library`).
- **NFR3 - Test first, keep existing cases:** Per `.claude/rules/hook-tests.md`, cases for a miss or a false positive are added before the fix. No existing case is deleted, and no existing case's command or expected verdict changes. The only change to an existing row is the FR9 label.
- **NFR4 - No duplicate command strings in the case table:** Each added command string must differ from every existing one. `test_every_pre_task_command_preserved_with_only_named_changes` fails on duplicates, and every command in `ORIGINAL_VERDICT_BY_COMMAND` must keep its pinned verdict.
- **NFR5 - False positives cost as much as misses:** Under claude-batch, ask is demoted to deny, so one false positive stops an unattended run. Closing the bypass must not turn any currently-allowed data-form command into ask or deny, and the FR4 and FR7 allow cases guard this.
- **NFR6 - Expected verdicts are runner-environment verdicts:** Case expectations are the verdicts `run-destructive-guard.py` observes with `CLAUDE_BATCH` cleared. A `$HOME/...` rm target is ask there, even though the review record measured deny under batch.

## Implementation Approach

### Architecture

**System Architecture:**

Not applicable as a layered system diagram. The code change is contained in a single PreToolUse(Bash) hook script and its case table:

```
PreToolUse(Bash) → destructive-guard.py main()
                     ├── deferral to failed-run-cleanup-guard   # unchanged (FR5)
                     │     matches_target_shape() over strip_grouping_prefix() / _deferral_head()
                     ├── statements()                           # segments, incl. substitution bodies,
                     │                                          # shell-sink here-docs, -c / eval / here-string payloads
                     ├── head()                                 # command word; grouping-aware skip local
                     │                                          # to this file, 2-tuple return kept (FR2, FR5)
                     ├── closer / fused-closer handling         # `)` never an argument; `)>` splits (FR3)
                     └── per-statement checks (FR5)
                           ├── check_rm
                           ├── check_git
                           ├── check_file_destruction
                           ├── check_external
                           ├── check_permissions
                           ├── check_self_modification        # tar -C: extract mode only (FR6)
                           └── substitution-headed route
```

**Component Diagram:**

```
destructive-guard.py                 — hook body; grouping/compound unwrap (FR2-FR5), tar extract-mode -C (FR6)
destructive-guard-cases.json         — [expected, label, command] case table; FR1 / FR7 / FR8 cases, FR9 label
run-destructive-guard.py             — runner (CLAUDE_BATCH cleared); trailing unattended-demotion case
failed-run-cleanup-guard.py          — deferral target; not modified (FR5)
prior feature SPEC.md / REQUIREMENTS.md — revised to match the implementation (FR10 / FR11)
plugin.json / marketplace.json       — em-workflow version fields (FR12)
```

### Data Flow

```
command string → deferral check (unchanged)
              → statements() → per statement:
                   unwrap grouping / compound syntax at command position (FR2)
                   drop bare `)` closers from arguments; split `)>` into closer + redirect (FR3)
                   reserved words / grouping chars outside command position stay data (FR4)
              → per-statement checks, same as the command written alone (FR5)
                   rm-recursive / git / file-destruction / permissions ⇒ deny or ask
                   write-target set ∩ SELF_CONFIG ⇒ ask (demoted to deny under CLAUDE_BATCH)
                   write-target set ∩ TRANSCRIPT  ⇒ deny
              → no match ⇒ allow (ALLOW_NON_DESTRUCTIVE)
```

### API Design

Not applicable. This feature exposes no API.

### Database Schema

Not applicable. This feature has no persistent data store.

#### Entity Relationship Diagram

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: the hook whose statement handling and per-statement checks change (FR2-FR6).
- `em-workflow/hooks/tests/destructive-guard-cases.json`: the case table FR1, FR7 and FR8 extend and FR9 relabels.
- `em-workflow/hooks/tests/run-destructive-guard.py`: the runner that executes the case table and the trailing unattended-demotion case.
- `em-workflow/hooks/failed-run-cleanup-guard.py`: the deferral target; not modified (FR5).
- `tests/test_destructive_guard_command_substitution.py`: enforces the forbidden-call list (NFR1).
- `feature-docs/destructive-guard-write-target-scoping/SPEC.md` and `REQUIREMENTS.md`: the prior feature's documents FR10 and FR11 revise.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: the two version fields FR12 raises.

**External Dependencies:**
- None. Standard library only (NFR2).

### File Structure

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json                       # version 0.2.12 → 0.2.13 (FR12)
└── hooks/
    ├── destructive-guard.py              # grouping/compound unwrap, closer handling, tar extract-mode -C (FR2-FR6)
    ├── failed-run-cleanup-guard.py       # unchanged (FR5)
    └── tests/
        ├── destructive-guard-cases.json  # FR1 / FR7 / FR8 cases added, FR9 label changed
        └── run-destructive-guard.py      # unchanged; runner + demotion case
.claude-plugin/
└── marketplace.json                      # em-workflow version 0.2.12 → 0.2.13 (FR12)
feature-docs/
└── destructive-guard-write-target-scoping/
    ├── SPEC.md                           # revised (FR10)
    └── REQUIREMENTS.md                   # revised (FR11)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-grouping-spec-drift/**`
- `test-docs/destructive-guard-grouping-spec-drift/**`

`feature-docs/destructive-guard-grouping-spec-drift/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/destructive-guard-grouping-spec-drift/**` covers `test-docs/destructive-guard-grouping-spec-drift/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/destructive-guard-grouping-spec-drift/` directory at all; the declared
`test-docs/destructive-guard-grouping-spec-drift/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` - Case-table run: red after the FR1/FR7 cases are added, green after the fix. Covers FR1, FR2, FR3, FR4, FR6, FR7, FR8, FR9.
- [ ] TS-3: `python3 em-workflow/hooks/tests/run-destructive-guard.py ~/.claude/plugins/cache/em-claude-plugins/em-workflow/0.2.13/hooks/destructive-guard.py` - Optional: after the version bump, confirm the installed cache copy carries the fix. Covers FR12.

### Integration Tests
- [ ] TS-2: `python3 -m unittest discover -s tests` - Repository-wide unit tests, including the case-table invariants (no duplicates, pinned `ORIGINAL_VERDICT_BY_COMMAND`, stdlib-only, no filesystem calls) and failed-run-cleanup-guard tests. Covers FR5, NFR1, NFR2, NFR3, NFR4.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] TS-E2E: Not applicable: no E2E infrastructure exists.

### Edge Cases
- [ ] Case patterns split across statements by `|` (`a|b)`) or by newlines (multi-line case body) need context across statements. A subshell's trailing `)` must not be read as a case-pattern terminator.
- [ ] The optional leading `(` of a case pattern (`(a) cmd`).
- [ ] Fused closer and redirect tokens (`)>`, `)>>`, `)2>`) produced by shlex punctuation fusing.
- [ ] Grouping combined with VAR=value, `WRAPPERS`, mise/asdf exec and substitution-headed command words.
- [ ] Nested constructs (`( { ...; } )`, a subshell inside if/then).
- [ ] Grouping inside `-c` / eval / here-string payloads and inside substitution bodies (`echo $(if true; then rm ...; fi)`).
- [ ] Redirects attached to closing keywords (`done > file`, `} 2>/dev/null`).
- [ ] Reserved words and grouping characters as data: argument position, quotes, here-doc bodies, for/select header words, case-pattern text.
- [ ] A quoted `"{"` at command position cannot be told apart from a bare `{`, because words carry no quote provenance. Treating it as grouping is the stricter direction.
- [ ] Traditional dashless tar mode argument (`tar xzf ...`) and mode given only via a long option (`--create`, `--extract`, `--get`).

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** Verdicts come from static analysis of the command string alone; no command runs, no substitution is evaluated, and no filesystem call or subprocess is added (NFR1). Reserved words and grouping characters count as syntax only at command position, and `(` only as an unquoted operator token (FR4).
- **Data Protection:** This hook is a safety net. Under `ALLOW_NON_DESTRUCTIVE=True` a command that reaches no check ends in allow, so the grouping bypass disables every check on the wrapped command (rm recursive delete, git, self-modification, transcript-write). FR2-FR5 close it for every per-statement check.
- **False-positive cost:** Under claude-batch, ask is demoted to deny, so one false positive stops an unattended run (NFR5). The FR1 (7), FR4 and FR7 allow cases guard against new false positives.
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

Not applicable. This hook emits a verdict (`allow` / `ask` / `deny`), not error codes.

### Error Flow

```
Bare `)` closer → never an argument or target of any check (FR3)
`)>` / `)>>` / `)2>` → split into closer + real redirect; target judged as a redirect target only (FR3)
Quoted `"("` / `")"` → ordinary word (FR3)
Quoted `"{"` at command position → treated as grouping (stricter direction)
```

## Performance Optimization

Not applicable. No performance goals, optimization strategies, or caching are part of this feature.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case, including the trailing unattended-demotion case, and exits 0.
- [ ] AC-2: `python3 -m unittest discover -s tests` passes.
- [ ] AC-3: With only the FR1 cases and the FR7 tar create/list allow cases added (no change to `destructive-guard.py`), the runner is red.
- [ ] AC-4: The five ticket reproduction commands are ask in the runner (deny with `CLAUDE_BATCH=1`), matching bare `rm -rf $HOME/x`.
- [ ] AC-5: Through `( )`, `{ }`, if/elif/else, for, while/until, `!`, case and function definitions, the rm recursive-delete, git, self-modification and transcript-write verdicts match the same command written alone (FR1 cases).
- [ ] AC-6: The fused-closer forms `(cp /tmp/x ~/.claude/settings.json)` and `(cp /tmp/x ~/.claude/settings.json)>/dev/null` are ask, and `(rm -rf /tmp/x)>/dev/null` is allow.
- [ ] AC-7: Every existing case keeps its command and expected verdict. Only the mv label from FR9 changes.
- [ ] AC-8: tar `-C` is a write target only in extract mode (`tar -cf /tmp/backup.tar -C ~/.claude/skills .` is allow, `tar -xzf /tmp/a.tgz -C ~/.claude/skills` is ask), and each of the six families has at least one ask case and one allow case.
- [ ] AC-9: Cases for `sudo -u` / `bash -c` / `eval`-routed rm exist and pass.
- [ ] AC-10: In `feature-docs/destructive-guard-write-target-scoping/SPEC.md` and REQUIREMENTS.md, FR2(c)/(d), the Edge Cases mv line and FR6 match the implementation's behaviour for mv, the six destination families and `head()`/`statements()`.
- [ ] AC-11: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both carry em-workflow version 0.2.13.

## Out of Scope

- Changes to `em-workflow/hooks/failed-run-cleanup-guard.py` and to the deferral judgement (`matches_target_shape` / `strip_grouping_prefix` / `_deferral_head` verdicts).
- The medium findings deferred in review round2 of `destructive-guard-write-target-scoping`, other than the tar `-C` false positive (`ed5c0ae5ec37e137`) that FR6 settles: the `<>` SPEC drift (`a9ef8f56bd1a375a`), deletion_alternative quoting (`02d9c33015f12347`), the trailing-slash protected-dir deny-to-ask regression, `~/.claude/plugins/` missing from `SELF_CONFIG`, `bash -lc` / `bash -cx` bypass, `wget -P` / `curl --output-dir`, `SELF_CONFIG` evaluated before `TRANSCRIPT`, `MAX_SHELL_PAYLOAD_EXPANSIONS` as a total cap, unused `TARGET_DIR_FLAGS`, `_TrackingLexer`'s reliance on shlex internals.
- `coproc`, arithmetic `(( ))` / `[[ ]]` as commands, and substitution bodies containing nested parentheses (`$( ( ... ) )`), which the `SUBSTITUTION` regex does not match.

## Assumptions

- **A-1** (impact: medium, reversible): The deferral to failed-run-cleanup-guard and `failed-run-cleanup-guard.py` itself stay unchanged. `head()`'s mirrored 2-tuple contract is kept, and the grouping skip is documented as local to `destructive-guard.py`. Reason: the answers settle the scope of this hook only. `head()`'s docstring already allows local skips that do not change the return shape (the `substitution_only` precedent). Widening the deferral to if/then/do forms that failed-run-cleanup-guard's own `head()` cannot judge would move those commands from allow to silent, which leaves them to the classifier (NFR5).
- **A-2** (impact: low, reversible): A function body is judged as if it runs, whether or not the command also calls the function. Reason: `strip_grouping_prefix()` already treats a defined function's body as invoked, and judging the body is the stricter direction for a safety net.
- **A-3** (impact: low, reversible): The traditional dashless tar form (`tar xzf ...`) counts as extract mode. Reason: the current implementation treats `-C` as a destination in every mode, so dropping the dashless extract form would lower detection. The answer asks to limit `-C` to extraction, not to drop detected extraction.
- **A-4** (impact: low, reversible): Parity is checked on the verdict tier, which is what the case runner compares. The rule id is not asserted separately. Reason: the ticket's completion definition asks for the verdict to match the bare form, and the runner checks the tier.
- **A-5** (impact: low, reversible): The prior feature branch has been merged into main, and main is the baseline. Its behaviour for mv, the six families and `head()`/`statements()` is the implementation the revised SPEC describes. Reason: orchestrator-supplied fact. The integration worktree's `destructive-guard.py` contains `FLAG_DEST_FLAGS`, `WRAPPER_VALUE_FLAGS` and the payload re-scan.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement is confirmed.

## Implementation Phases (if applicable)

### Phase 1: Failing cases first
**Goals:** FR1, FR7, FR8 — add the grouping/compound cases, the six-family cases and the rm pinning cases; confirm the runner is red on the cases whose verdict changes with the fix (AC-3).
**Deliverables:**
- The added cases in `em-workflow/hooks/tests/destructive-guard-cases.json`
- A red run of TS-1

### Phase 2: Grouping fix and tar extract mode
**Goals:** FR2, FR3, FR4, FR5, FR6 — judge the command inside grouping and compound constructs, handle closers, limit tar `-C` to extract mode, and turn the suite green.
**Deliverables:**
- The changed `em-workflow/hooks/destructive-guard.py`
- A green run of TS-1 and TS-2 (AC-1, AC-2, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9)

### Phase 3: Label and document revisions
**Goals:** FR9, FR10, FR11 — relabel the mv case and revise the prior feature's SPEC.md and REQUIREMENTS.md.
**Deliverables:**
- The relabelled mv case
- The revised `feature-docs/destructive-guard-write-target-scoping/SPEC.md` and `REQUIREMENTS.md` (AC-10)

### Phase 4: Version bump
**Goals:** FR12 — raise both em-workflow version fields to 0.2.13.
**Deliverables:**
- `em-workflow/.claude-plugin/plugin.json` at 0.2.13
- `.claude-plugin/marketplace.json` em-workflow entry at 0.2.13 (AC-11)

## References

- Requirements document: `feature-docs/destructive-guard-grouping-spec-drift/REQUIREMENTS.md`
- Hook under change: `em-workflow/hooks/destructive-guard.py`
- Case table: `em-workflow/hooks/tests/destructive-guard-cases.json`
- Test runner: `em-workflow/hooks/tests/run-destructive-guard.py`
- Deferral target: `em-workflow/hooks/failed-run-cleanup-guard.py`
- Prior feature SPEC: `feature-docs/destructive-guard-write-target-scoping/SPEC.md`
- Prior feature requirements: `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md`
- Prior feature review record: `feature-docs/destructive-guard-write-target-scoping/reviews/round2.yaml`
- Hook test rules: `.claude/rules/hook-tests.md`
- Plugin version bump rules: `.claude/rules/core-plugin-version-bump.md`
- Test dependency policy: `test/README.md`
