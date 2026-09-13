# Feature: destructive-guard-quoted-substitution

## Overview

`destructive-guard.py` denies a recursive delete whose target is a quoted
command substitution, but the reason text used to show a single-space target
and an unusable `gio trash` path. The underlying cause was already fixed by
the sibling ticket, so this feature pins that behaviour down with regression
cases in `em-workflow/hooks/tests/destructive-guard-cases.json` and bumps the
plugin version so the change reaches installed caches. The hook itself is not
modified.

Requirements source: `feature-docs/destructive-guard-quoted-substitution/REQUIREMENTS.md`.

## Objectives

- Pin down, with a permanent regression test, the state in which the reason
  text reads as "the target cannot be statically determined" when
  destructive-guard stops a recursive delete containing a quoted command
  substitution.
- Make a recurrence of the same cause detectable through test cases covering
  both the ticket's exact reproduction form and its alternate spelling.
- Make sure the change reaches the plugin cache in user environments.

## Acceptance Criteria

- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in full
      including the added cases (226 + 2 = 228 cases).
- [ ] The command strings of the two added cases match, character for
      character, the ticket's reproduction command and its backtick-spelled
      variant.
- [ ] Both added cases expect the verdict `ask`.
- [ ] Existing cases are unchanged in count and content, apart from the
      additions.
- [ ] `em-workflow/hooks/destructive-guard.py` has no diff.
- [ ] Running the ticket's reproduction steps yields a reason text whose
      target is not a single space, and which carries
      `[destructive-guard/rm-unresolvable]`.
- [ ] The em-workflow version in `em-workflow/.claude-plugin/plugin.json` and
      in the root `.claude-plugin/marketplace.json` are equal to each other and
      newer than before the change.

## Technical Requirements

### Functional Requirements

- **FR1 — Add the reproduction-form regression case:** Add to
  `em-workflow/hooks/tests/destructive-guard-cases.json` a case whose command
  string matches the ticket's reproduction command character for character,
  in the 3-element `[expected verdict, label, command]` form. The command
  string is:

  ```
  rm -rf "$(printf /home/sakura/valuable)"
  ```

- **FR2 — Add the backtick-spelling regression case:** Add to the same file a
  case for the backtick-spelled variant of the reproduction form, in the same
  3-element form. This pins down that the `$(...)` spelling and the backtick
  spelling take the same path and reach the same verdict. The command string
  is:

  ```
  rm -rf "`printf /home/sakura/valuable`"
  ```

- **FR3 — Preserve existing cases:** Do not delete or alter any existing
  deny / ask / allow case. Additions only. The existing 226 cases stay
  unchanged in both count and content.

- **FR4 — Bump the plugin version:** Because files under `em-workflow/` are
  changed, raise, within the same change, the `version` in
  `em-workflow/.claude-plugin/plugin.json` and the `version` of the
  em-workflow entry in the repository-root `.claude-plugin/marketplace.json`
  to the same value, bumped by one patch unit.

- **FR5 — Leave the hook body untouched:** Make no change at all to
  `em-workflow/hooks/destructive-guard.py`. The ticket's symptom is already
  resolved by the sibling ticket's fix for the same cause, so the work for
  this ticket is limited to adding regression cases and bumping the version.

- **FR6 — Expected verdict of the added cases:** The first element (expected
  verdict) of both cases added by FR1 / FR2 is `ask`, matching the existing
  cases on the same rm-unresolvable path. The `deny` observed when running the
  reproduction steps is a display difference caused by the ask→deny demotion
  under unattended execution (`CLAUDE_BATCH`), not a different verdict.

- **FR7 — Case labels:** The labels of the two added cases are Japanese text
  from which both the rm-unresolvable path and the difference in quoted
  command-substitution spelling (`$()` vs. backtick) can be read.

### Non-Functional Requirements

- **NFR1 — Standard library only:** Test code uses only the Python standard
  library and imports no third-party package (test/README.md).
- **NFR2 — Case format compliance:** Added cases follow the 3-element
  `[expected verdict, label, command]` form (`.claude/rules/hook-tests.md`).
- **NFR3 — No new files:** Add no new file; complete the change by appending
  to the existing `em-workflow/hooks/tests/destructive-guard-cases.json`.
- **NFR4 — Suitability as distributed content:** All files under
  `em-workflow/` are distributed to the plugin cache in user environments, so
  the added test cases must be suitable as distributed content
  (`.claude/rules/core-plugin-structure.md`).
- **NFR5 — No false positives:** The added cases must not drag existing allow
  cases into false positives. A false positive stops unattended execution on
  the spot, so it is weighted as heavily as a miss
  (`.claude/rules/hook-tests.md`).

## Implementation Approach

### Files Touched

| Path | Change |
|---|---|
| `em-workflow/hooks/tests/destructive-guard-cases.json` | Append the two regression cases (FR1, FR2, FR6, FR7); existing entries untouched (FR3) |
| `em-workflow/.claude-plugin/plugin.json` | Bump `version` (FR4) |
| `.claude-plugin/marketplace.json` | Bump the em-workflow entry's `version` to the same value (FR4) |
| `em-workflow/hooks/destructive-guard.py` | No change (FR5) |

### Design Step

Skipped. The change covers only appends to a JSON test-case array and the
plugin version strings; it involves neither UI/visual elements nor new module
design.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/tests/run-destructive-guard.py`: the runner that executes
  the case file.
- `em-workflow/hooks/destructive-guard.py`: the hook under test; unchanged by
  this feature (FR5).

**External Dependencies:**
- None. Python standard library only (NFR1).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from every
task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated entries
in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-quoted-substitution/**`
- `test-docs/destructive-guard-quoted-substitution/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the phase
documents and by `references/phase-state.md`; this section cites them and
restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`; this
section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC author
explicitly removes them; their absence is never assumed by silence — removal is
a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed at
verification time must be CONTAINED IN the declared set, not equal to it.

## Test Scenarios

### TS-1: Reproduction steps do not yield a single-space target
- **Requirements:** FR5
- **Given:** the current integration worktree's
  `em-workflow/hooks/destructive-guard.py`
- **When:** the ticket's reproduction steps are run (the reproduction command
  passed on stdin as `tool_input.command`)
- **Then:** the target in `permissionDecisionReason` is not a single space, and
  the text appears as `[destructive-guard/rm-unresolvable]` stating that the
  target is a variable / command substitution whose blast radius cannot be
  statically determined. No non-existent `gio trash` path is offered.

### TS-2: The reproduction-form case exists with expected verdict `ask`
- **Requirements:** FR1, FR6, NFR2
- **Given:** `em-workflow/hooks/tests/destructive-guard-cases.json`
- **When:** entries whose command string matches the reproduction form
  (`$()` spelling) are searched for
- **Then:** exactly one such entry exists and its first element is `ask`.

### TS-3: The backtick-spelling case exists with expected verdict `ask`
- **Requirements:** FR2, FR6, NFR2
- **Given:** `em-workflow/hooks/tests/destructive-guard-cases.json`
- **When:** entries whose command string matches the backtick-spelled variant
  are searched for
- **Then:** exactly one such entry exists and its first element is `ask`.

### TS-4: The guard suite passes in full
- **Requirements:** FR1, FR2, FR3, NFR5
- **Given:** `destructive-guard-cases.json` including the added cases
- **When:** `python3 em-workflow/hooks/tests/run-destructive-guard.py` is run
- **Then:** 228/228 pass with zero failures. The verdicts of the existing 226
  cases are unchanged.

### TS-5: The version matches in both places and is newer
- **Requirements:** FR4
- **Given:** `em-workflow/.claude-plugin/plugin.json` and the root
  `.claude-plugin/marketplace.json`, before and after the change
- **When:** the em-workflow version string is read from both files and compared
- **Then:** the two values are equal, and the patch has advanced by at least
  one from the pre-change value. Other plugins' versions are unchanged.

### TS-6: No diff in the hook body
- **Requirements:** FR5
- **Given:** the integration branch's diff
- **When:** the diff of `em-workflow/hooks/destructive-guard.py` is inspected
- **Then:** there is no diff.

## Assumptions

- **a1** (impact: medium, reversible): No change to `destructive-guard.py`
  itself is needed for this ticket; the work is limited to adding regression
  cases and the version bump. The sibling ticket's fix for the same cause is
  already merged into main, and the reproduction command is already stopped as
  rm-unresolvable. Confirmed by the answer to `scope.remaining-work`.
- **a2** (impact: medium, reversible): The expected verdict of the added
  regression cases is `ask`; the `deny` observed in the reproduction steps is a
  display difference from the demotion under unattended execution. The two
  existing cases on the same path pass with `ask` as their expected value.
  Confirmed by the answer to `testing.expected-verdict`.
- **a3** (impact: low, reversible): A change confined to
  `em-workflow/hooks/tests/` is still subject to the version bump, because
  `core-plugin-structure.md` distributes every file under the plugin to the
  plugin cache in user environments. Related question: `scope.remaining-work`.
- **a4** (impact: low, reversible): This feature has no UI or visual elements,
  so the design step is unnecessary. The change targets only appends to a JSON
  test-case array and the plugin version strings. Related question:
  `design-step.decision`.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every FR and NFR has `status: resolved`.

## Success Criteria

- [ ] All functional requirements are implemented and tested.
- [ ] All test scenarios pass.
- [ ] Non-functional requirements NFR1–NFR5 are satisfied.
- [ ] Code review is completed.

## References

- Requirements document: `feature-docs/destructive-guard-quoted-substitution/REQUIREMENTS.md`
- Hook test rules: `.claude/rules/hook-tests.md`
- Plugin structure and distribution: `.claude/rules/core-plugin-structure.md`
- Plugin version bump: `.claude/rules/core-plugin-version-bump.md`
- Ticket: [https://www.notion.so/3d63509ec8ee815d8337cc340757a824](https://www.notion.so/3d63509ec8ee815d8337cc340757a824)
