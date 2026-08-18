# Implementation Plan: exit4-tip-argument

## Overview

Two independently-implementable tasks: task0001 rewrites the implement-phase
protocol prose so every `commit-docs.sh` call site the exit-4 recovery bullet
enumerates passes a captured `expected_base_tip`; task0002 bumps the plugin
version in the two registries. Each task ships the contract-test module that
asserts its own change.

## Technology Stack

- **Language**: Markdown (protocol prose), JSON (plugin registries),
  Python 3 standard library (`unittest`) for contract tests.
- **Key libraries**: none. This feature introduces NO new dependency, so no
  license compatibility question arises. `project.license` is `none` and is
  not changed by this feature.

## Layer Structure

Not a code architecture. The artifacts form three layers with a one-way
dependency direction:

1. **Protocol prose** — `em-workflow/references/implement-phase.md`. The
   normative source for implement-phase orchestration. Single file.
2. **Registry** — `em-workflow/.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json`. Plugin identity/version only.
3. **Contract tests** — modules under `tests/`. Layer 3 READS layers 1 and 2
   and asserts their content; layers 1 and 2 never reference layer 3.

`em-workflow/scripts/commit-docs.sh` sits outside all three: it is the
authority this feature's prose cites, and it is READ-ONLY for every task.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `em-workflow/references/implement-phase.md` | The protocol prose under change | Pre: exists, current suite green. Post: edited by EXACTLY ONE task (task0001); every other task treats it read-only and asserts nothing about it | task0001 (writer) |
| `em-workflow/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` | Plugin version registries | Pre: both report `0.1.44`. Post: both report the IDENTICAL new version string, written by EXACTLY ONE task (task0002) | task0002 (writer) |
| New version string | The single value both registries carry | `0.1.45` — same major/minor line, patch strictly greater than 44, `X.Y.Z` form | task0002 |
| `tests/test_exit4_tip_argument_consistency.py` | Asserts the post-change wording of the protocol prose | Reads ONLY `em-workflow/references/implement-phase.md`; imports no other test module; asserts nothing about plugin version | task0001 (owner) |
| `tests/test_exit4_tip_argument_version_bump.py` | Asserts both registries carry the same bumped version | Reads ONLY the two JSON registries, parsed as JSON; imports no other test module; asserts nothing about protocol prose | task0002 (owner) |
| Pre-existing modules under `tests/` | Retention guards written by earlier features | Read-only for EVERY task — no task may edit an existing test module (FR4, NFR3), and no task may make its own change pass by weakening one | task0001, task0002 |
| `em-workflow/scripts/commit-docs.sh` | Supplies `expected_base_tip`, the exit codes and the RECOVERY CONTRACT the new prose cites | Read-only for EVERY task; must be absent from the feature diff (NFR2, AC8) | task0001, task0002 |

## Conventions

- **Test module naming**: `tests/test_exit4_tip_argument_<scope>.py`,
  discovered automatically by `python3 -m unittest discover -s tests`
  (`test/README.md`); classes `Test<Behavior>`, methods
  `test_<condition>_<expected_result>`; standard library only, no
  third-party import.
- **Assertion style over prose** (the convention already established by the
  modules in `tests/`): content assertions compare against a
  whitespace-normalized copy of the relevant section, so a line-wrap choice
  never makes a prose assertion brittle; byte-identity and
  line-wrap-survival assertions compare the RAW, un-normalized text. The two
  are never mixed in one assertion — mixing them is the known source of both
  false passes and false failures in this suite.
- **Negative proof per matcher**: every matcher asserting NEW wording
  carries (a) a negative proof that it fails against a verbatim pre-change
  sample of the same passage, and (b) a non-vacuity guard asserting that the
  sample itself still contains a retained anchor, so the proof cannot decay
  into a tautology. Matchers that only guard RETAINED wording, ordering, or
  a pre-existing invariant need no negative proof.
- **Registry assertions parse JSON**, never pattern-match raw JSON text; the
  version assertion is expressed as a durable baseline (patch strictly
  greater than the pre-change patch) rather than a fixed literal, so it does
  not go stale on the next unrelated bump.
- **Commit-message convention inside the protocol prose**:
  `docs({feature}): {summary}` — the existing convention the document
  already uses at its other call sites; the two new invocations follow it.
- **Error-handling policy for the prose being written**: exactly one
  documented failure route, `commit-docs.sh` exit 4, and it is always
  handled by cross-referencing the Branch & Worktree Model's exit-4
  recovery — never by restating that recovery locally.

## Cross-task Design Decisions

### D1 — One writer per file

`em-workflow/references/implement-phase.md` is written by task0001 only; the
two version registries are written by task0002 only. Tasks run fully in
parallel in separate worktrees, and the protocol document is a single file:
a second writer would guarantee a merge conflict on a document whose exact
byte layout is pinned by several existing tests. Every task's `files` list is
disjoint from every other task's.

Affected tasks: task0001, task0002.

### D2 — Each new test module ships in the same task as the change it asserts

task0001's module asserts prose task0001 writes; task0002's module asserts a
version task0002 writes. Neither module is added ahead of its subject.
Rationale: tasks merge into the integration branch in an unpredictable
order, and a test module that lands before its subject makes the integration
branch red between merges. With this rule the suite is green at every merge
point, in either order.

Affected tasks: task0001, task0002.

### D3 — Version bump target

Current version in both registries: `0.1.44`. This is a documentation /
protocol correction, so the bump is patch level: both registries move to
`0.1.45`, as the identical string. task0002's durable baseline is therefore
"patch strictly greater than 44", which is red on the un-bumped tree.

Affected tasks: task0002.

### D4 — Existing test modules are frozen

No task edits any pre-existing file under `tests/` (FR4 names
`tests/test_rework_synthesis_contract.py` explicitly; NFR3 extends the rule
to the whole suite). When a task's change would make an existing assertion
fail, the change is wrong — the assertion is not. The full inventory of
pinned literals and orderings that constrain the protocol edit lives in
task0001's plan, because task0001 is the only task that can disturb them.

Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The prose insertion reflows or otherwise disturbs a pinned literal in `implement-phase.md`, turning an existing module red | High | High | task0001's plan carries the explicit retention inventory (which literals, which orderings, which whole-file invariant); the full suite is run before the merge; insertions are placed strictly outside pinned spans |
| The Step I.3 insertion lands inside the byte-pinned completion sentence | Medium | High | The sentence is quoted verbatim in task0001's plan with its internal line break marked; all new material goes strictly before or strictly after it |
| A new line that begins with `git` and also contains the word `commit` trips the whole-file bare-git-line invariant | Medium | Medium | Called out explicitly in task0001's retention inventory as a line-wrapping constraint |
| Version bumped in one registry only, or to differing strings | Low | Medium | D3 pins one value; task0002's equality matcher compares the two registries directly |
| Integration branch red between the two merges | Low | Medium | D2 — every new module ships with its own subject |

## Open Questions

- [ ] None blocking. Every requirement (FR1-FR6, NFR1-NFR4) is `ok` in
      workflow.yaml; there is no `tbd` requirement, no new dependency and
      therefore no license question.
- [ ] NFR1 (wording parity across the six call sites) has no mechanical
      verifier: it is judged by a human reading pass in the verify phase
      (VERIFICATION.md TS9). Recorded here so the absence of an automated
      check is a decision rather than an oversight.
