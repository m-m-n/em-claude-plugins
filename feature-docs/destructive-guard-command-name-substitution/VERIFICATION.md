# Verification Document: destructive-guard-command-name-substitution

## Overview

**Feature**: destructive-guard-command-name-substitution
**SPEC.md**: `feature-docs/destructive-guard-command-name-substitution/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-command-name-substitution/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature, run after the
delta task has merged. Per-task acceptance criteria live in
`feature-docs/destructive-guard-command-name-substitution/tasks/task0002.md`.
It supersedes the first generation's verification plan: the scenario numbering
below follows the revised SPEC.md (TS-1 through TS-33), and the inspection and
integration scenarios are numbered TS-34 onward so that no id carries two
meanings.

## Build Verification

- Command (component `main`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Component `hooks` declares no build command; nothing is compiled for it.
- Expected: exit code 0, no errors reported.

## Test Verification

- Command (component `hooks`): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (component `main`): `python3 -m unittest discover -s tests`
- Expected: the case runner exits 0 with every case passing. The unit-test
  discovery is compared against the base revision rather than required to be
  green: its failing-test-ID set must match the base revision's set exactly, with
  zero new failures (AC-10, TS-41). The base carries pre-existing failures that
  are outside this feature's change scope (NFR5, AS-10).
- Coverage target: no coverage tooling exists in this repository and none is
  introduced (NFR6). Completeness is measured instead by case-table coverage:
  every Unit scenario below must exist as an entry in
  `em-workflow/hooks/tests/destructive-guard-cases.json`; the scenarios marked
  Inspection are checked by reading the changed files.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `$(which rm) -rf /home/sakura/valuable` | `deny`, reason id `rm-recursive` | Unit |
| TS-2 | Backtick spelling of TS-1 | `deny`, reason id `rm-recursive` | Unit |
| TS-3 | `$(which git) reset --hard HEAD` | `deny`, reason id `git-reset-hard` | Unit |
| TS-4 | `$(which git) clean -fd` | `deny`, reason id `git-clean` | Unit |
| TS-5 | `$(which node) script.js` | `allow` — no rm / git evidence | Unit |
| TS-6 | `$(which ls) -la` | `allow` — flag-leading remainder, no rm evidence (label rewritten) | Unit |
| TS-7 | `$(which grep) -r pattern src` | `allow` — recursion flag present but no rm evidence (label rewritten) | Unit |
| TS-8 | `$(which rm) -rf dist` | `allow` — build-artifact safe-route exception inherited | Unit |
| TS-9 | `$(which rm) -rf /tmp/scratch/x` | `allow` — scratch-root exception inherited | Unit |
| TS-10 | `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` | `allow`; the pre-existing entry is retained with a rewritten label | Unit |
| TS-11 | `eval "$(ssh-agent -s)"`, and the same shape for `eval "$(direnv export bash)"`, `eval "$(mise activate zsh)"`, `bash -c "$(cat script.sh)"` | `allow` for all four | Unit |
| TS-12 | `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` | `allow`, with the out-of-scope declaration present in the label | Unit |
| TS-13 | `$(which rm) /home/sakura/valuable -rf` | `deny`, reason id `rm-recursive` — operand-first spelling | Unit |
| TS-14 | `$(which rm) /home/sakura -rf` | `deny` — operand-first spelling against a home-root target | Unit |
| TS-15 | `$(which rm) -r /home/sakura/valuable` | `deny`, reason id `rm-recursive` — recursion without force | Unit |
| TS-16 | `$(which rm) -R /home/sakura/valuable` | `deny`, reason id `rm-recursive` — uppercase spelling | Unit |
| TS-17 | `$(which rm) --recursive /home/sakura/valuable` | `deny`, reason id `rm-recursive` — long spelling | Unit |
| TS-18 | `$(which cp) -rf src dst` | `allow` — the plain spelling is `allow`, so this is equivalent | Unit |
| TS-19 | `$(which cp) -Rf src dst` | `allow` | Unit |
| TS-20 | `$(which chmod) -Rf 755 build` | `allow` | Unit |
| TS-21 | `$(which chown) -Rf user:group /srv/app` | `allow` | Unit |
| TS-22 | `$(which tar) -rf archive.tar file.txt` | `allow` | Unit |
| TS-23 | `$(which grep) -rf patterns.txt src` | `allow` | Unit |
| TS-24 | `$(which rsync) -rf src/ dst/` | `allow` | Unit |
| TS-25 | `$(which scp) -rf host:/a /b` | `allow` | Unit |
| TS-26 | `$(which make) clean -fd` | `allow` — pins the removal of the unconditional git-route call | Unit |
| TS-27 | `$(hatch env find) reset --hard` | `allow` — substitution head plus git subcommand shape, but no git evidence | Unit |
| TS-28 | `bash -c 'cd "$(dirname /a/b)" && rm -rf /home/sakura/valuable'` | `deny` — mixed `-c` body is still rescanned | Integration |
| TS-29 | `sh -c 'echo "$(date)" && rm -rf /home/sakura/valuable'` | `deny` — mixed body, date substitution | Integration |
| TS-30 | `bash -c 'echo "$(pwd)"; git reset --hard HEAD'` | `deny` — mixed body, git destructive command | Integration |
| TS-31 | `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` | `allow` — the quoted here-string inversion, pinned explicitly | Integration |
| TS-32 | `bash <<<$(true) 'rm -rf /home/sakura/valuable'` | `deny` — the unquoted here-string promotion is unchanged (control) | Integration |
| TS-33 | `$(cat cmdfile) -rf /home/sakura/valuable` | `allow` — the command name cannot be read statically; declared out of scope | Unit |
| TS-34 | The case table carries every command of TS-1 through TS-33 in the three-element form, and the suite runs with no new runner and no added dependency | Table parses; runner unchanged; every command present | Inspection |
| TS-35 | The mirror divergence note covers the branches and the function added by this generation, and the two mirror scripts have no code change | Note extended; mirror scripts byte-identical to their pre-change content | Inspection |
| TS-36 | The two version manifests hold the same value with the patch component advanced by at least one over the value the branch already carried, and the feature's changed-file set is contained in the four declared files | Values equal and advanced; no fifth source file changed | Inspection |
| TS-37 | The judgement path — including the command-name evidence reading — introduces no filesystem access, no subprocess launch and no evaluation of a substitution | None present in the changed code | Inspection |
| TS-38 | Every pre-existing case keeps its expected verdict except the quoted payload entry and the quoted here-string entry, including the unquoted promotion group and the unattended-demotion cases at the end of the runner; no entry is deleted | Full case suite passes; exactly two expectations differ from the pre-change table | Integration |
| TS-39 | The substitution-head routing lives in one named function, the dispatch site retains only the call, and the superseded rm pre-screen helper no longer exists in the file | One entry point; helper absent | Inspection |
| TS-40 | For every substitution-headed command in the case table, the plain spelling of the read command name with the same remaining arguments yields the same tier and reason id, and no substitution-headed spelling is stricter than its plain spelling | Tier and reason id equal for each pair; no allow-to-deny direction | Integration |
| TS-41 | The failing-test-ID set of the repository unit-test discovery matches the base revision's set exactly | Same test IDs fail before and after; zero new failures | Integration |

## Code Quality Verification

- Format: no format command is declared for either component; nothing to run.
- Static analysis: none declared. The plugin invariants check
  (`python3 em-workflow/scripts/check-plugin-invariants.py .`) serves as the
  structural check for the manifests.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The substitution-headed rm spelling is `deny` with reason id `rm-recursive`, in both substitution spellings | TS-1, TS-2 |
| AC-2 | The substitution-headed git spellings are `deny` with the existing git reason ids | TS-3, TS-4 |
| AC-3 | The five no-evidence forms are `allow` | TS-5, TS-6 plus the pre-existing entries for the first three commands (TS-38 proves those are unchanged) |
| AC-4 | The two safe-route rm forms are `allow` | TS-8, TS-9 |
| AC-5 | The quoted payload command is `allow` and its case is retained with a rewritten label | TS-10, TS-34 |
| AC-6 | The four quoted-payload normal-operation commands are `allow` | TS-11 |
| AC-7 | The four unquoted-promotion forms stay `deny` | TS-32, TS-38 |
| AC-8 | The out-of-scope form is `allow`, and its label and the payload-extraction docstring state the same scope | TS-12 plus manual item M-1 |
| AC-9 | The case-suite runner passes for every case | TS-38 and Test Verification |
| AC-10 | The unit-test discovery's failing-ID set matches the base revision's exactly, with zero new failures | TS-41 |
| AC-11 | Both version manifests carry the same value, advanced by at least one patch | TS-36 and Build Verification |
| AC-12 | Commands containing no substitution return the same tier and the same reason text as before | TS-38 plus manual item M-2 |
| AC-13 | The operand-first spellings are `deny` with reason id `rm-recursive` | TS-13, TS-14 |
| AC-14 | The three recursion-without-force spellings are `deny` with reason id `rm-recursive` | TS-15, TS-16, TS-17 |
| AC-15 | The eight non-rm / non-git commands taking recursion and force flags are `allow` | TS-18 through TS-25 |
| AC-16 | The two non-git commands in the substitution-head plus git-subcommand shape are `allow` | TS-26, TS-27 |
| AC-17 | The recursion-flagged grep form stays `allow` and its label states the new rationale | TS-7 plus manual item M-4 |
| AC-18 | All three mixed `-c` bodies are `deny` | TS-28, TS-29, TS-30 |
| AC-19 | The quoted here-string is `allow` and its inversion is recorded in the acceptance criteria and in the case table | TS-31, TS-34 |
| AC-20 | The routing is extracted into one named function, the dispatch site retains only the call, and the superseded helper is deleted | TS-39 |
| AC-21 | The statically unreadable substitution-headed form stays `allow` and the limit is written down in the label and the docstring | TS-33 plus manual item M-1 |
| AC-22 | The evidence reading is string processing only | TS-37 plus manual item M-2 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1, TS-2, TS-8, TS-9, TS-13, TS-14, TS-15, TS-16, TS-17 |
| FR2 | task0002 | TS-3, TS-4, TS-26, TS-27 |
| FR3 | task0002 | TS-5, TS-6, TS-7, TS-18, TS-19, TS-20, TS-21, TS-22, TS-23, TS-24, TS-25, TS-33 |
| FR4 | task0002 | TS-10, TS-11, TS-28, TS-29, TS-30, TS-31 |
| FR5 | task0002 | TS-32, TS-38 |
| FR6 | task0002 | TS-10 |
| FR7 | task0002 | TS-12, TS-33 |
| FR8 | task0002 | TS-34 |
| FR9 | task0002 | TS-35 |
| FR10 | task0002 | TS-36 |
| FR11 | task0002 | TS-1, TS-3, TS-33, TS-37 |
| FR12 | task0002 | TS-31 |
| FR13 | task0002 | TS-39 |
| NFR1 | task0002 | TS-37 |
| NFR2 | task0002 | TS-38, TS-41 |
| NFR3 | task0002 | TS-38 (the allow-side entries TS-18 through TS-27 in particular) |
| NFR4 | task0002 | TS-38 |
| NFR5 | task0002 | TS-36 |
| NFR6 | task0002 | TS-34 |
| NFR7 | task0002 | TS-40 |

Task0001 (merged, first generation) implemented FR1 through FR10 and NFR1
through NFR6 as those requirements read before the SPEC change; the revised text
of every one of them is delivered by task0002, which is why the table above names
a single task per requirement.

## E2E Testing

No E2E framework exists in this repository and `e2e_test_command` is empty for
both components. No E2E scenario is defined for this feature.

## Manual Testing (E2E Not Possible)

- [ ] M-1 (AC-8, AC-21, FR7): Read the out-of-scope case labels and the
      payload-extraction docstring side by side and confirm they state the same
      scope, covering both undecidable forms — a form whose substitution result
      becomes the script body, and a substitution-headed form whose command name
      cannot be read. A difference in scope (not merely in phrasing) is a failure.
- [ ] M-2 (AC-12, AC-22, NFR1): Read the changed judgement path, including the
      evidence reading, and confirm it consults the command string only — no path
      resolution, no stat, no subprocess, no evaluation of a substitution — and
      that no reason text was reworded for a substitution-free command.
- [ ] M-3 (FR9, AS-9): Confirm the mirror divergence note now covers the added
      branches and the new function, and that neither mirror script received a
      code change.
- [ ] M-4 (AC-17, FR8): Confirm the rewritten labels of the two pre-existing
      allow cases state the new rationale — no readable evidence that the command
      is rm — rather than the superseded one about not reaching a shape floor.
- [ ] M-5 (NFR5, FR10): Confirm the feature's integrated change set is contained
      in the four declared source files plus the workflow-generated
      `feature-docs/` and `test-docs/` entries, and that the version bump appears
      as its own commit rather than being mixed into the behaviour change.

## Performance / Security Verification

- Security (detection scope): a statement whose command-word position is a
  substitution reaches a `deny` / `ask` tier only through statically read
  command-name evidence followed by an existing shape match — verified by TS-1
  through TS-4 and TS-13 through TS-17 (positives) together with TS-5 through
  TS-9, TS-18 through TS-27 and TS-33 (negatives).
- Security (declared limits): the two undecidable forms stay `allow` by design —
  verified by TS-12, TS-33 and manual item M-1.
- Security (no added strictness): the substitution-headed spelling is never
  stricter than the plain spelling — verified by TS-40.
- Security (unattended behaviour): the demotion path from `ask` to `deny` is
  unchanged — verified by TS-38's demotion cases.
- Performance: the analysis remains a single pass over one command string; the
  evidence reading adds a bounded scan of the segment body. No performance
  requirement is stated and no threshold is set.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 41 | 34 (TS-1 through TS-33, TS-38) | 0 | 7 (TS-34 through TS-37, TS-39 through TS-41, as inspections and comparisons) |
| Success criteria | 22 | 18 | 0 | 4 (AC-8, AC-17, AC-21, AC-22 partially) |
| Build / quality | 1 | 1 | 0 | 0 |
| Manual items | 5 | 0 | 0 | 5 |
