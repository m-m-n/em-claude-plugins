# Verification Document: destructive-guard-var-resolution

## Overview

**Feature**: destructive-guard-var-resolution /
**SPEC.md**: `feature-docs/destructive-guard-var-resolution/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-var-resolution/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task is
merged — the two first-pass tasks and the rework tasks added after review
rounds 1, 2, 3 and 4. Per-task acceptance criteria live in the task plans.

### What this feature now delivers, and what it no longer does

After review round 3, the variable-resolution layer is withdrawn. FR1-FR7 and
NFR1/NFR2/NFR3/NFR4/NFR6 carry `status: excluded` in `workflow.yaml` with the
reason recorded there; the requirements that remain in force are **FR8** (the
expectation entries, per `.claude/rules/hook-tests.md`), **FR9** (the
0.1.56 → 0.1.57 version bump, merged by task0002) and **NFR5** (single-file,
standard-library-only hook). task0005 restores the hook to the behaviour of
`1fdb27fe51de6d20e9812027d3aee603cb584173` and keeps every expectation entry
this feature added whose recorded expectation matches what that hook actually
produces. task0006 then makes those retained entries describe themselves
correctly — labels naming the judgment path that really produces each verdict
instead of the withdrawn layer, an explicit marker on every verdict that
records a known guard gap, and the base revision's file layout so the diff
reads as an append. It changes no verdict and does not touch the hook.

Twenty-six scenarios below therefore verify behaviour that no longer exists.
They are **retired in place, not deleted**: each keeps its ID and its original
subject, and states which excluded requirement it belonged to, so the mapping
from a retired scenario to a withdrawn requirement stays readable. A retired
scenario is not run and is not a gap — its requirement is excluded, not unmet.

## Build Verification

- Command: none. Both components in workflow.yaml declare an empty
  `build_command` — the hook is an interpreted script and the manifests are
  data files.
- Expected: not applicable; the suites below execute the hook directly.

## Test Verification

- Command (hooks component):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (main component): `python3 -m unittest discover -s tests`
- Expected: both exit 0, with no failing case reported by either.
- Coverage target: none configured for this repository. Coverage is expressed
  as scenario coverage of the table below, as retention of every pre-existing
  expectation entry (58 at the base revision), and as the differential ledger
  of TS-29.

### Test Scenarios from SPEC.md

Each active scenario's verdict is checked by an expectation entry in
`em-workflow/hooks/tests/destructive-guard-cases.json`, executed by the hooks
component command, or by the differential run TS-29 defines. Where a scenario
also asserts a rule identifier, the runner cannot see it (its entries carry the
expected verdict only), so that half is a manual check — see IMPLEMENTATION.md
D3 and the manual section below.

TS-1 through TS-11 come from SPEC.md's own scenario list. TS-13 through TS-21
were added by the rework round that followed review round 1 and TS-22 through
TS-28 by the round that followed review round 2; both sets state properties of
the resolution layer. TS-29 is added by the rework round that followed review
round 3 and states the property that replaces them: the hook answers as the
pre-feature hook answers. TS-30 and TS-31 are added by the rework round that
followed review round 4 and state properties of the expectation list as a
document rather than of the hook: the shape of its diff against the base
revision, and whether each entry's label is true of the verdict beside it.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | RETIRED (FR1, FR2, FR3 excluded) — standalone literal assignment of a scratch-area path, then a recursive delete through that variable at the same nesting level | Not run. The resolution layer this asserted is withdrawn; the command returns to the pre-feature `rm-unresolvable` ask, which is TS-29's business, not this row's | — |
| TS-2 | RETIRED (FR2, FR3, FR4 excluded) — same shape aimed at a path outside the scratch area | Not run. Asserted a deny reached through a resolved value | — |
| TS-3 | RETIRED (FR6, NFR2 excluded) — the same name assigned twice, then a recursive delete through it, with the split-the-variables reason hint | Not run. The hint is a resolution-layer reason and no longer exists | — |
| TS-4 | RETIRED (FR7, NFR2 excluded) — assignment separated from its use by a shell `-c` payload, and separately by a subshell | Not run. Asserted a scope rule of the resolution layer | — |
| TS-5 | RETIRED (FR5, NFR2 excluded) — command-prefix assignment on the delete command itself | Not run. Asserted an exclusion rule of the resolution layer | — |
| TS-6 | RETIRED (FR2, NFR2 excluded) — resolved value still containing a glob metacharacter | Not run. Asserted a post-substitution outcome | — |
| TS-7 | RETIRED (FR2, NFR2 excluded) — resolved value still containing a command substitution | Not run. Asserted a post-substitution outcome | — |
| TS-8 | RETIRED (FR2, FR3 excluded) — resolved value that is the bare home shorthand, and one that is the filesystem root | Not run. Asserted a deny reached through a resolved value | — |
| TS-9 | RETIRED (FR3 excluded) — resolved value reaching a write target under Claude Code's own configuration | Not run. Asserted the write-target check consuming resolved text | — |
| TS-10 | RETIRED (FR3 excluded) — resolved value reaching a session transcript write target | Not run. Asserted the write-target check consuming resolved text | — |
| TS-11 | The retained expectation set — every pre-existing entry (58 at the base revision), plus every entry added by task0001, task0003 or task0004 that task0005 retains — plus the trailing unattended-demotion check the runner performs after the table | every recorded verdict is produced; runner exits 0; the run is identical when repeated; the hook is one script whose imports are all standard library | Integration |
| TS-13 | RETIRED (FR1, FR7, NFR2 excluded) — an assignment the shell does not execute before the use site | Not run. Asserted which assignments the resolution layer may read | — |
| TS-14 | RETIRED (FR1, FR5, FR6, NFR2 excluded) — a name bound a second time through a form other than a bare assignment statement | Not run. Asserted the layer's invalidation rules | — |
| TS-15 | RETIRED (FR1, FR2, NFR2 excluded) — an assignment whose right-hand side contains a command substitution | Not run. Asserted what the layer may collect as a literal | — |
| TS-16 | RETIRED (FR7, NFR2 excluded) — an assignment inside one pipeline element used from outside it, and one in a background job | Not run. Asserted the layer's scope boundaries | — |
| TS-17 | RETIRED (FR7, NFR2 excluded) — subshell group boundaries under two spellings | Not run. Asserted the layer's scope boundaries | — |
| TS-18 | RETIRED (FR2, FR3, NFR2 excluded) — a resolved value containing whitespace, so the real command names more than one target | Not run. Asserted a post-substitution outcome | — |
| TS-19 | RETIRED (FR3, FR4, NFR2 excluded) — a resolved target that climbs out of a scratch root, and a leading component that merely prefixes a scratch name | Not run as a resolved-side scenario. Its literal-side half — a directory name that merely begins with a scratch-area name — survives as a retained expectation entry under TS-11 and is measured against the base hook by TS-29 | — |
| TS-20 | RETIRED (FR2, FR4, NFR2 excluded) — a reference that substitutes to an empty or whitespace-only value | Not run. Asserted a post-substitution outcome | — |
| TS-21 | RETIRED (FR2, FR3, NFR2 excluded) — a recursive-delete flag supplied through a variable | Not run. Asserted flag recognition through the resolution layer | — |
| TS-22 | RETIRED (FR2, NFR2, NFR6 excluded) — commands carrying no recorded assignment, in the shapes the layer's lexing touched | Not run as a layer-lexing scenario. Its five command strings survive as retained expectation entries under TS-11, and each is measured against the base hook by TS-29 — that is where the escaped-parenthesis `find … -delete` and the quoted-parenthesis force push are now held | — |
| TS-23 | RETIRED (FR2, FR3, NFR6 excluded) — scratch-area containment for a target nothing was substituted into, plus the resolved-side directory form | Not run as written. Its literal-side command strings survive as retained expectation entries under TS-11 and are measured by TS-29 | — |
| TS-24 | RETIRED (FR2, NFR2 excluded) — a dynamic target followed by enough parent references to climb out of the named tree | Not run. Asserted the ordering of the layer's unresolvable gate against containment | — |
| TS-25 | RETIRED (FR1, FR5, FR6, NFR2, NFR3 excluded) — a name bound a second time in shapes other than a bare assignment statement | Not run. Asserted the layer's invalidation rules | — |
| TS-26 | RETIRED (FR2, FR4 excluded) — the reason string emitted for a delete whose target is a command substitution | Not run. The internal placeholder it guarded against belonged to the layer; the base hook emits no such text and TS-29 compares rule identifiers on the same command | — |
| TS-27 | RETIRED (NFR2, NFR4 excluded) — cost of resolution at 44KB and 88KB, and an over-ceiling token | Not run as a resolution-cost scenario. The two measured shapes are carried forward by TS-29, whose comparison is against the base hook rather than against a ceiling the layer defined | — |
| TS-28 | RETIRED (FR3, FR7, NFR2 excluded) — an argument supplied through a variable to a check outside the declared resolved-text set, and a later assignment | Not run. Asserted where the layer was wired | — |
| TS-29 | Behavioural equivalence with the pre-feature hook: every command string in the retained expectation list, every command string quoted in a finding or spot-check table of review rounds 1, 2 and 3 (including round 3's eleven verified inputs), and the 44KB and 88KB shapes round 3 timed, each run through `em-workflow/hooks/destructive-guard.py` and through the hook at `1fdb27fe51de6d20e9812027d3aee603cb584173` on the same machine in the same session | every input yields the same verdict and the same bracketed rule identifier on both sides — zero differing pairs, recorded pairwise; every input yields a verdict at all, none reaching the hook's 10-second timeout; the two timed shapes are judged within twice the base time and under one second | Integration (differential) + Manual (ledger, rule identifiers, timings) |
| TS-30 | Diff shape of the expectation list: `em-workflow/hooks/tests/destructive-guard-cases.json` compared against `1fdb27fe51de6d20e9812027d3aee603cb584173`, after task0006 restores the base revision's one-entry-per-line layout | the file holds one entry per line; every one of the 58 base-revision entry lines is present, in order, byte-identical; the diff consists of added lines only, with at most one non-added line — the base file's final entry line re-emitted with a trailing comma appended, differing from its base form by that comma alone; `em-workflow/hooks/destructive-guard.py` shows no diff against the same revision | Integration (diff) + Manual (one read of the diff) |
| TS-31 | Label truthfulness of the retained expectation entries: each entry this feature added, read against the verdict and the bracketed rule identifier the merged hook actually produces for its command string | no label in the file contains the string `変数解決`, and no label names a resolution stage, assignment map, scope rule, value-length ceiling or reason sentinel; each label names the judgment path that produces its entry's verdict; every entry whose verdict records a known guard gap — the bare command substitution as sole delete target, the trailing-slash scratch-root spelling, the unanchored scratch-name prefix, and the paired counter-cases added beside them — carries the literal marker `既知の穴(未修正)`, and no other entry does; every verdict and every command string is unchanged from before task0006; both suites stay green | Integration (suite, string search) + Manual (label/verdict pairing table) |

### Additional verification scenarios (verification-plan additions)

Not present in SPEC.md's scenario list. Added here so the requirements they
cover have a named, automated check rather than an empty mapping.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-12 | The repository suite's plugin version-parity module reads both registries | the two version values agree and compare past the module's recorded baseline; the suite exits 0 | Integration |

## Code Quality Verification

- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured. One property is instead checked by reading
  the diff, in the manual section below: the hook's import list stays within the
  standard library and the hook remains a single script (NFR5).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | RETIRED with FR1-FR3 — the reported false positive is allowed | Not verified. The false positive is not fixed: with the resolution layer withdrawn, the reported command returns to its `rm-unresolvable` ask. This is the accepted outcome of the withdrawal, recorded here rather than dropped |
| AC-2 | RETIRED with FR2-FR4 — the same shape outside the scratch area is denied with the resolved-path suggestion | Not verified; asserted resolution behaviour |
| AC-3 | RETIRED with FR2, FR3 — a resolved value reaching root or home is denied | Not verified; asserted resolution behaviour |
| AC-4 | RETIRED with FR3 — a resolved write target asks or denies per its pattern | Not verified; asserted resolution behaviour |
| AC-5 | RETIRED with FR5-FR7, NFR2 — every unresolvable form keeps its pre-change verdict and the reassignment reason carries the split hint | Not verified as written. Its stronger successor is TS-29: EVERY form, resolvable or not, keeps the pre-feature verdict |
| AC-6 | The hook expectation suite passes with every pre-existing entry still present | TS-11 plus TS-29's per-entry verdict pairs, plus TS-30's diff-shape check (which is where the pre-existing entries' byte identity is now established: line for line against the base revision, inside a diff that is additions only) |
| AC-7 | Both manifests read 0.1.57 | TS-12 plus the manual manifest read |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003, task0004 | EXCLUDED (see `workflow.yaml` `excluded_reason`). Retired scenarios: TS-1, TS-13, TS-14, TS-15, TS-25 |
| FR2 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-1, TS-2, TS-6, TS-7, TS-8, TS-15, TS-18, TS-20, TS-21, TS-22, TS-23, TS-24, TS-26 |
| FR3 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-1, TS-2, TS-8, TS-9, TS-10, TS-18, TS-19, TS-21, TS-23, TS-28 |
| FR4 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-2, TS-19, TS-20, TS-26 |
| FR5 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-5, TS-14, TS-25 |
| FR6 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-3, TS-14, TS-25 |
| FR7 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-4, TS-13, TS-16, TS-17, TS-28 |
| FR8 | task0001, task0003, task0004, task0005, task0006 | TS-11 (the retained expectation set runs green, twice), TS-29 (each retained added entry's expectation equals the base hook's verdict for its command, and each removed entry's did not), TS-30 (the pre-existing entries are byte-identical line for line and the diff against the base revision is additions only) and TS-31 (every entry's label is true of the verdict beside it, and every verdict that records a known guard gap says so) |
| FR9 | task0002 | TS-12, plus the manual manifest read |
| NFR1 | task0001, task0003, task0004 | EXCLUDED. Retired coverage: TS-11's static-only half |
| NFR2 | task0001, task0003, task0004 | EXCLUDED. Retired scenarios: TS-3 through TS-7, TS-13 through TS-22, TS-24, TS-25, TS-27, TS-28 |
| NFR3 | task0001, task0003, task0004 | EXCLUDED. Retired coverage: TS-25's separator pairs. TS-11's doubled run is retained as an FR8 check |
| NFR4 | task0001, task0003, task0004 | EXCLUDED. Retired scenario: TS-27. TS-29 measures the same two shapes against the base hook instead |
| NFR5 | task0001, task0003, task0004, task0005 | TS-11 (both suites run under a plain interpreter with no package installation, so a non-standard-library import would fail the run), plus the import-list inspection |
| NFR6 | task0001, task0003, task0004 | EXCLUDED. Its subject — existing behaviour untouched — is now the whole feature's outcome and is measured by TS-29 rather than by a requirement of its own |

## E2E Testing

No E2E framework exists in this repository and none is introduced by this
feature (`e2e_test_command` is empty for both components). No E2E scenario
applies.

## Manual Testing (E2E Not Possible)

- [ ] Differential ledger (TS-29): for every corpus input, record side by side
      the verdict and bracketed rule identifier from the hook at
      `1fdb27fe51de6d20e9812027d3aee603cb584173` and from the merged hook, both
      run on the same machine in one session. Confirm zero differing pairs and
      that every input produced a verdict. (FR8, TS-29)
- [ ] Cost measurement (TS-29): run the 44KB repeated-binding-word shape and the
      88KB shape through both hook revisions in the same session and record all
      four times; confirm each current-side time is at most twice its base
      counterpart and under one second, with nothing near the 10-second hook
      timeout. (FR8, TS-29)
- [ ] Pre-existing entries intact (TS-30): every entry present at the base
      revision (58) is present, in order, and byte-identical **line for line**
      in the base revision's one-entry-per-line layout, with no deletion, edit
      or expectation change. Check this on the diff against
      `1fdb27fe51de6d20e9812027d3aee603cb584173`, not by reading the file: the
      diff must contain added lines only, with at most one non-added line — the
      base file's final entry line re-emitted with a trailing comma appended.
      (Round 4 found the earlier wording of this check unverifiable: the file
      had been reformatted to one element per line, so "byte-identical" was
      false of every line while remaining true of every parsed entry. task0006
      restores the layout, which is what makes this check answerable again.)
      (AC-6, FR8, TS-30)
- [ ] Label / verdict pairing (TS-31): for every entry this feature added, the
      test record shows the entry's label beside the verdict and bracketed rule
      identifier the merged hook produces for its command string. Confirm no
      label names the withdrawn resolution layer, that each label names the
      judgment path that actually produced the verdict, and that every entry
      recording a known guard gap — bare command substitution as sole delete
      target, trailing-slash scratch root, unanchored scratch-name prefix —
      carries the `既知の穴(未修正)` marker. (FR8, TS-31)
- [ ] Retention decision per added entry: for every entry added by task0001,
      task0003 or task0004, the test record shows the base hook's verdict for
      its command string beside the entry's recorded expectation, and the entry
      is present exactly when the two agree. Confirm the entries for
      `rm -rf /tmp/`, `rm -rf build-debug`, `rm -rf dist/*`, the
      escaped-parenthesis `find … -delete` and the `git push "(" --force …`
      form are among those present. (FR8, TS-29)
- [ ] Single-file, stdlib-only inspection: the hook is one executable script and
      every import is a standard library module; no dependency is introduced.
      (NFR5, TS-11)
- [ ] Determinism of the suite: run the hook expectation suite twice and confirm
      identical output. (FR8, TS-11)
- [ ] Manifest read: parse both registries, confirm the two version values are
      identical and read 0.1.57, and confirm no other plugin's version key was
      added or changed, and that task0005 modified neither file. (AC-7, FR9)
- [ ] Optional, environment-dependent: after the installed plugin cache has
      picked up the new version, run the hook expectation suite against the
      installed copy by passing its path to the runner. Requires a Claude Code
      restart first.

Retired manual checks (their requirements are excluded; listed so the drop is
visible rather than silent): the resolution-layer rule/reason checks for TS-2,
TS-3, TS-8, TS-9, TS-10; the round-1 rule/reason checks for TS-13 through
TS-20; the round-2 rule/reason checks for TS-22, TS-24, TS-25, TS-26; the
red-run evidence check for the resolution stage; the static-only inspection of
the resolution path; the cost-shape inspection of the resolution pass; the
untouched-pattern inspection; and both pre-resolution parity ledgers, which
TS-29's single ledger supersedes at a wider scope.

## Performance / Security Verification

- Cost: the hook's cost on every measured shape is the base hook's cost
  (TS-29). The superlinear paths the third round measured — 9.85s at 44KB
  against a 10-second timeout — are removed with the layer, so the failure mode
  of emitting no verdict at all is gone.
- Detection preservation: the asymmetric-cost property of this hook means a new
  false positive ends an unattended run on the spot, and a missed real target is
  unrecoverable. Both directions are held by TS-11's retained expectation set —
  the allow entries guard the false-positive cost, the deny/ask entries guard
  detection — and by TS-29, which is what proves neither direction moved
  relative to the pre-feature hook.
- Known gaps recorded rather than endorsed: several retained allow entries hold
  a verdict that follows from a pre-existing weakness of the guard (a delete
  whose only target is an unquoted command substitution reaches the check with
  no targets; the scratch-area allowance matches a name prefix without a path
  separator; a scratch root with a trailing slash is allowed where the same root
  without one is denied). Those weaknesses are base behaviour, unchanged by this
  feature and out of its scope. TS-31 is what keeps them legible: the entry
  stays as a false-positive guard, and its label says the verdict records an
  unfixed gap, so a later change that closes the gap reads as intended rather
  than as a regression.
- Withdrawn-requirement note: the fail-closed property (NFR2) is excluded not
  because it stopped mattering but because the layer it constrained no longer
  exists. The equivalence in TS-29 is a strictly stronger statement over the
  same inputs: not "no weaker than base", but "identical to base".

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 31 (5 active: TS-11, TS-12, TS-29, TS-30, TS-31; 26 retired with their excluded requirements) | 5 | 0 | TS-29, TS-30 and TS-31 each carry a manual half (ledger/rule/timing, diff read, label pairing) |
| Success criteria | 7 (2 active: AC-6, AC-7; 5 retired) | 2 | 0 | AC-7 also carries a manual manifest read |
| Requirements | 15 (3 in force: FR8, FR9, NFR5; 12 excluded) | 3 | 0 | FR8 and NFR5 also carry manual checks |
| Manual checks | 9 (1 optional, environment-dependent) | — | — | 9 |
