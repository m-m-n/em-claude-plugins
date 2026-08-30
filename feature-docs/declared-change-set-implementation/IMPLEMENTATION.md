# Implementation Plan: declared-change-set-implementation

## Overview

Add the missing `IMPLEMENTATION.md` member to the enumerated membership of
`feature-docs/{feature}/**` in both document templates and in the matching
literal sets of their two test modules, and bump the plugin version in the two
manifests that declare it. No runtime code is involved.

## Technology Stack

- **Markdown** — the two document templates under
  `em-workflow/references/templates/`; the artifact whose content changes.
- **Python 3 standard library `unittest`** — the entire test suite. No
  third-party package may be imported by test code (NFR2, `test/README.md`).
- **JSON** — the two plugin manifests carrying the version declaration.

**New dependencies introduced by this feature: none.** `project.license` is
`none`, so no license compatibility constraint applies and there is no new
dependency license to record.

## Layer Structure

Four artifact layers with a single permitted dependency direction:

1. **Naming SSOT layer** — `em-workflow/references/phases/create-plan-phase.md`
   and `em-workflow/references/phase-state.md`. Read-only in this feature.
   Supplies the authoritative spelling of the member being added (NFR1).
2. **Template layer** — `spec-document.md` (English) and
   `requirements-document.md` (Japanese). Enumerates the members; derives every
   member name from layer 1.
3. **Test layer** — the two test modules under `tests/`. Reads the template
   layer's files at run time and asserts that every name in its own literal set
   appears in the sliced section. Layer 2 never reads layer 3.
4. **Release-metadata layer** — `em-workflow/.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json`. Depends on nothing above, but must move
   whenever layer 2 changes, because layer 2 lives inside the plugin.

Permitted direction: 1 → 2 → 3. No layer reads downward; layer 1 is never
edited by this feature.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Feature-docs member literal | The single spelling of the member being added to every enumeration | Precondition: the spelling is taken verbatim from the naming SSOT layer and is exactly `IMPLEMENTATION.md` — no variant, no path prefix, no suffix. Postcondition: the identical spelling appears in all four destinations (two template sections, two test literal sets), positioned immediately after the existing `SPEC.md` entry in each, and appears exactly once per destination. | task0001 |
| Plugin version value | The single version string both manifests declare | Precondition: both manifests currently declare the same value. Postcondition: both declare one identical new value, one patch increment above the current one; no other field of either manifest changes. | task0002 |
| Declared change-set partition | The disjoint file ownership that lets the two tasks run fully in parallel | Precondition: the feature's declared change set is the six files named in SPEC.md. Postcondition: task0001 modifies only the two templates and the two test modules; task0002 modifies only the two manifests; no file is written by both tasks, so the two worktrees never conflict on merge. | task0001, task0002 |

## Conventions

- **Naming**: the added member's name is SSOT-derived (layer 1). A variant
  spelling is a defect even if the tests would pass with it.
- **Notation follows the destination, not a new house style**: each of the four
  destinations already has an established notation for its existing members
  (English inline-code list separated by commas; Japanese inline-code list
  separated by the ideographic comma; a module-level literal set of plain
  strings). The added entry adopts the notation already used by its neighbours
  in that same destination. No destination gains a new notation.
- **Additive only**: no existing member is renamed, reordered, or removed in any
  of the four destinations. The relative order of all pre-existing members is
  preserved.
- **No new files**: this feature creates no new test module, no new template, and
  no new fixture. Every change is an edit to one of the six declared files
  (NFR4).
- **Frozen negative-proof samples**: the captured pre-change samples inside the
  test modules are read-only for this feature. They must remain byte-identical,
  so the negative proof (the matcher reports absence against pre-change text)
  keeps its meaning (NFR3).
- **Test dependencies**: standard library only (NFR2).
- **Manifest edits**: only the version value changes. Indentation, key order,
  and every other field are preserved byte-for-byte.
- **Truthful comments**: a comment or docstring that states a member *count*
  becomes wrong when a member is added; such statements are updated in the same
  edit. Comments that do not state a count are left alone.
- **Error handling / logging policy**: not applicable — no runtime code.

## Cross-task Design Decisions

### D1: File-ownership partition (content edits vs release metadata)

The feature is split along the only seam where the two halves share no file and
no literal: the content edit (templates + tests) and the release metadata
(the two manifests).

All four content destinations stay inside a single task. They share one literal
whose whole point is to be identical everywhere; splitting them across parallel
worktrees would let two implementers independently choose a spelling or a
position, and the tests would not catch a divergence in *position* at all.
Keeping them together makes the shared contract hold by construction rather
than by agreement.

The two manifests stay inside a single task because they must declare the same
value within the same change (FR4); two parallel tasks editing them separately
could pick different values and would conflict on merge.

Affected tasks: task0001, task0002.

### D2: Insertion position immediately after the `SPEC.md` entry

In every destination the added member is placed directly after the existing
`SPEC.md` entry, ahead of `workflow.yaml`. This matches the order in which the
phases produce the artifacts (create-spec before create-plan) and matches how
this feature's own REQUIREMENTS.md and SPEC.md already enumerate the set.
Placement is not asserted by any existing test, so it is an acceptance criterion
verified by inspection rather than by the suite.

Affected tasks: task0001.

### D3: Test-first direction when the test artifacts are themselves in scope

The tests being modified are the same tests that verify the templates. The
test-first cycle is therefore: add the member to both test literal sets first
and observe the suite turn red (the templates do not yet name the member), then
add the member to both templates and observe it turn green. Writing the template
edit first would make the change unfalsifiable — the suite would be green before
and after, proving nothing.

Affected tasks: task0001.

### D4: Version increment is a patch step

The change is a behavioural fix to plugin-owned content, so the increment is the
patch component only (FR4 / AS-4). The concrete current value is read from the
manifests at implementation time rather than restated here, so this document
cannot go stale against them.

Affected tasks: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The four destinations end up with different spellings or positions | Low | Medium | D1 keeps all four in one task; the Shared Components contract pins spelling and position |
| Re-wrapping the English paragraph to fit the added member breaks a content assertion | Medium | Low | The content assertions read a whitespace-normalized copy of the sliced section, so line-wrap choices are immaterial; the section's heading anchors must stay intact and unique |
| A negative-proof sample is edited while adding the member, silently voiding the negative proof | Low | High | Explicit acceptance criterion (task0001) that both pre-change samples are unchanged; the pre-change text contains no occurrence of the added member, so no edit is needed for the suite to pass |
| The version bump is forgotten because the content change looks self-contained | Medium | Medium | The bump is its own task with its own acceptance criteria (task0002) |
| A comment stating the member count is left saying the old count | Medium | Low | Conventions require count-stating comments to be updated in the same edit |

## Open Questions

- [ ] FR4 (version bump) has no automated verification: adding a test for it
      would require a new test module, which NFR4 places outside the change
      scope. It is verified by inspection in VERIFICATION.md instead.
- [ ] NFR4 (bounded change scope) is verified by the verify phase's declared
      change-set containment check, not by the test suite.
- [ ] The *placement* half of NFR1 (position relative to neighbouring members)
      is not asserted by any test; only the presence and spelling of the member
      are. Placement is an inspection item.
