# Implementation Plan: tip-capture-idiom-unification

## Overview

Unify the seven tip-carrying `commit-docs.sh` call sites in
`em-workflow/references/implement-phase.md` on the single safe tip-capture idiom
already used at Step I.2.a and Step I.3, align `commit-docs.sh`'s two prose blocks
with it, and lock the uniformity with one new test module — a documentation,
shell-comment, test and version-manifest change with no executable behaviour change.

## Technology Stack

- **Artifacts changed**: Markdown protocol document, Bash script comments, Python
  unittest modules, JSON version manifests.
- **Test runner**: Python 3 `unittest` (standard library), discovered with
  `python3 -m unittest discover -s tests` from the integration worktree root.
- **New dependencies**: none. No library is added, so no license check applies
  (`project.license` is `none`; nothing to record beyond "no new dependency").

## Layer Structure

Four artifact layers, with a strict one-way dependency direction:

1. **Protocol SSOT** — `em-workflow/references/implement-phase.md`. Owns the
   canonical idiom and the exit-4 recovery bullet that is its normative reference.
2. **Script contract prose** — `em-workflow/scripts/commit-docs.sh` header comments.
   Describes the same contract from the callee's side; must not contradict layer 1.
3. **Test layer** — `tests/`. Observes layers 1 and 2. Tests never dictate prose:
   where a pin contradicts the canonical idiom the pin is amended (only where FR7
   names it); where it does not, the prose is placed so the pin survives (NFR3, FR6).
4. **Distribution manifests** — `em-workflow/.claude-plugin/plugin.json` and the root
   `.claude-plugin/marketplace.json`. Independent of layers 1-3; carry one shared
   version value.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Canonical tip-capture idiom (SPEC FR1) | The one documented procedure at every tip-carrying call site | Pre: the site passes a captured tip as the commit call's third argument. Post: the tip is resolved from the integration BRANCH REF (never from the worktree HEAD); the refresh targets the BRANCH NAME (never a captured SHA); the capture strictly precedes the refresh; the site keeps its own variable name, commit-message literal and exit-4 cross-reference | task0001 |
| Reference form | Step I.2.a and Step I.3 already carry the canonical idiom | Pre/Post: their content is not changed by this feature; the five converted sites are brought to their form | task0001 |
| Shared plugin version value | One new version string, higher than 0.1.45 by one patch step (`0.1.46`, per SPEC assumption a6) | Post: `em-workflow/.claude-plugin/plugin.json` and the root `.claude-plugin/marketplace.json`'s `em-workflow` entry carry the byte-identical string; no other field of either file changes | task0002 |
| File-ownership boundary | Each declared file has exactly one owning task | Post: task0001 owns `implement-phase.md`, `commit-docs.sh` and everything under `tests/`; task0002 owns the two version manifests. Neither task writes the other's files | task0001, task0002 |
| Green-suite invariant | Each task leaves the discovered suite green in its OWN worktree, without depending on the other task | Pre: the task captures the baseline suite result before its first edit. Post: `python3 -m unittest discover -s tests` passes in that worktree | task0001, task0002 |

## Conventions

- **Assertion style** (existing repository convention, visible in every sibling
  module): whitespace-normalized comparisons and byte-identity comparisons are never
  mixed inside one assertion. Prose-content assertions run against a
  whitespace-normalized copy; line-wrap/byte-stability assertions run against the raw
  text.
- **New test modules**: Python `unittest`, standard library only, no import from any
  other test module, file name `test_*.py` under `tests/` so plain discovery finds it.
- **Negative proof discipline** (existing convention): every matcher asserting NEW
  post-change wording is paired with a proof that it fails against a verbatim
  pre-change sample, and every such sample carries a non-vacuity guard.
- **Frozen-pin discipline** (NFR3): protocol prose is never shaped to satisfy an
  existing test. Where a frozen pin contradicts the canonical idiom, the pin is
  amended — but only where FR7 names it. Where the pin does not contradict the idiom,
  the prose is placed so the pin keeps passing untouched.
- **Editing discipline**: edits stay local. Lines that do not change are never
  reflowed — several modules pin raw line-wrap literals, including the Step I.2.b
  wake-phase commit literal with its internal newline and three-space continuation
  indent.
- **Language**: the protocol document and script comments stay in English, matching
  their surrounding text.

## Cross-task Design Decisions

### D1: `implement-phase.md` is edited by exactly one task

All five site conversions are spread across one file. Tasks run in fully parallel
worktrees with no ordering mechanism, so a second task editing the same document
would guarantee a merge conflict on every hunk. The whole document change is
therefore one task's responsibility (task0001).

### D2: the tests that assert the post-change document live in the same task as the document edits

Both the new uniformity module and FR7's three assertion amendments describe the
POST-change wording. In any other task's worktree the document still carries the old
idiom, so those assertions would be red and that task could never reach a green
suite. Since there is no ordering between tasks, they must be co-located with the
edits they observe (task0001).

### D3: exactly ONE new test module, hence `commit-docs.sh` shares task0001

NFR6 fixes the change set at one new test module. TS-3 and TS-4 (the `commit-docs.sh`
prose and comment-only checks) therefore live in that same new module, and by D2 the
`commit-docs.sh` prose edit must be in the same task as the module that asserts it.
`tests/test_commit_docs.py` is a pre-existing module and is frozen by NFR2, so the
checks cannot be added there.

### D4: the version bump is its own task

The two manifests are independent of the prose change: no test asserts a relationship
between them and the document, and every existing version-bump module compares
against a baseline patch (38 / 41 / 42 / 44) rather than pinning a literal, so a bump
to 0.1.46 keeps them green on its own. Both manifests stay in ONE task so the two
values cannot diverge (task0002).

### D5: the Step I.2.c batch-mode abort restatement is OUT of scope

The batch-mode paragraph closing Step I.2.c restates the abort path as
"refresh the integration worktree, capture the tip, …" — the pre-change order. It is
byte-pinned twice against the live document:

- `tests/test_implement_routeback_gate.py:989-993`
  (`test_batch_mode_paragraph_is_byte_identical`)
- `tests/test_routeback_reset_scope_consistency.py:594-626`
  (`test_batch_mode_paragraph_is_byte_identical_tail`)

Editing that paragraph would require amending a fourth assertion in the first module —
outside FR7's three named amendments — and modifying the second module, which NFR2
freezes by name. FR2's site list does not include this restatement, and FR4 defines
the in-scope set as the seven call sites. The paragraph is therefore left
byte-identical, and the residual wording gap is recorded as an open question below
rather than resolved by widening scope.

### D6: decision rule for a frozen pin not enumerated by FR7

If the suite reveals a pin that contradicts the canonical idiom and is NOT one of
FR7's three: first try a placement that keeps the pin passing (the FR6 pattern —
insert the capture before the pinned sentence rather than rewriting it). Only if no
such placement exists, stop and report a plan deviation with the module, line range
and the contradiction. Never amend a pin outside FR7's three, and never reshape the
prose merely to satisfy one.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A frozen pin outside FR7's three breaks on the conversion | Medium | High — blocks a green suite | Run the full suite and record the baseline BEFORE the first edit; convert one site at a time and re-run; apply D6's placement-first rule; the known pin inventory is enumerated in task0001's Design |
| The route-back order pin's anchor phrase disappears when that site's prose is reordered | High | Medium | The amendment re-anchors that single test method on a phrase that exists in the post-change prose; the change stays inside the one method FR7 names |
| A line-wrap reflow silently breaks a raw literal pin (wake-phase commit literal, Step I.0 / Step I.2.a literals) | Medium | High | Never reflow untouched lines; keep each edit local to its own site; the suite detects it immediately |
| The new module passes vacuously (matches nothing meaningful) | Medium | Medium | Every new matcher carries a negative proof against a captured pre-change sample plus a non-vacuity guard, per the repository convention |
| The two version manifests diverge | Low | Medium | Both files are owned by one task, and an existing module already asserts their equality |
| TS-4's "executable body unchanged" check is captured after the edit and proves nothing | Medium | Medium | Capture the comment-stripped body from the PRE-change file (available in the worktree before the edit) and pin that; the check then guards this change and future drift alike |

## Open Questions

- [ ] The Step I.2.c batch-mode abort restatement still states refresh-then-capture
      (D5). Aligning it needs two byte-pins amended across two modules, which
      FR7 / NFR2 / NFR6 forbid here. Should a follow-up feature align the restatement
      together with both pins?
- [ ] TS-8 (version-manifest agreement above 0.1.45) has no automated module: the
      repository precedent is a per-feature `test_*_version_bump.py`, but NFR6 caps the
      change set at one new test module (FR9's). Confirm at verify time that the
      manual-diff check is the accepted form. The equality of the two manifests is
      already machine-checked by an existing module; only the "> 0.1.45" half is manual.
- [ ] FR9's uniformity check is scoped to the seven call sites, so NFR1's
      "no old idiom anywhere in the document" is machine-checked only over those sites.
      The batch-mode restatement (D5) is deliberately outside that scope.
