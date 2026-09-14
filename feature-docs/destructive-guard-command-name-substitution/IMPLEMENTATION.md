# Implementation Plan: destructive-guard-command-name-substitution

## Overview

Close the miss where a statement whose command word is produced by a command
substitution (`$(which rm) -rf <path>`) is judged `allow`, by matching the
remaining tokens against the already-existing destructive shapes, and make the
payload argument position of `-c` / `eval` / `<<<` quote-aware so the quoted
`"$(...)"` promotion stops producing a false positive. The feature is decomposed
into a single implement task covering all four changed files.

## Scope of this document

The feature has one task, so this document carries no task-to-task coordination.
What it does carry — and what the task plan deliberately does not restate — is
the stage structure the change must respect, the contracts that outlive the
task (the guard's behavioural postcondition, the case table's retention rule,
the published version value), the decomposition rationale, and the risk
register. The review and verify phases read this document as the statement of
what the change was allowed to do.

## Technology Stack

- **Language**: Python 3 — the hook module and its case runner are plain
  standard-library Python; no framework is involved.
- **Key libraries**: none. No dependency is added, and no package manifest
  exists in this repository to add one to.
- **New dependency licenses**: none introduced by this feature. `project.license`
  is `none`, so there is no project license for a dependency to conflict with
  and nothing to record beyond this line.
- **Test runners**: the two commands already declared in workflow.yaml
  `project.components` (case-suite runner and the repository unit-test
  discovery). No new runner, harness, or test dependency is introduced (NFR6).

## Layer Structure

The hook is a single-file static analyzer over one command string. Its stages
run strictly in order; each stage consumes the previous stage's output and never
re-enters an earlier one.

| # | Stage | Responsibility | Status in this feature |
|---|-------|----------------|------------------------|
| 1 | Pre-lexical marking | Replaces substitution occurrences in the raw command text with markers before lexing | **Frozen** — marker structure and the token attribute trio are unchanged (AS-5) |
| 2 | Lexing | Produces the token sequence carrying the existing attributes | **Frozen** |
| 3 | Payload extraction | For `-c` / `eval` / `<<<`, decides which token is the script body | **Changed** — quote awareness at the payload argument position (FR4, FR5, FR7) |
| 4 | Command-word determination | Decides a statement's command name, or classifies it as statically unknown | **Changed** — new "statically unknown" classification and its two routes (FR1, FR2, FR3, FR9) |
| 5 | Shape matching | Matches remaining tokens against the existing rm / git destructive shapes | **Callers only** — gains callers; its outcomes, thresholds and reason ids are unchanged |
| 6 | Decision and unattended demotion | Fixes the final stage and applies the unattended demotion | **Frozen** (NFR4) |

Direction rules that hold across the whole feature:

- Only stage 3 may consult the raw pre-lexical text, and only for the payload
  argument position. No other stage gains access to it — in particular, the
  command-word determination of stage 4 keeps working from tokens alone (FR4).
- Stage 5 is reached only through an existing destructive-shape match. A stage-4
  "statically unknown" classification never produces a verdict by itself.
- No new decision stage and no new reason id are created anywhere (AS-1).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Guard decision logic (`em-workflow/hooks/destructive-guard.py`) | Produces a stage (`allow` / `ask` / `deny`) and a reason id for one command string | **Pre**: input is the command string alone; no filesystem, subprocess, or substitution evaluation is permitted. **Post**: for any command containing no substitution, the stage and the reason text are identical to the pre-change behaviour; the set of reason ids is unchanged | task0001 |
| Case table (`em-workflow/hooks/tests/destructive-guard-cases.json`) | The behavioural contract of the guard, as `[expected verdict, label, command]` triples | **Pre**: every pre-existing entry is retained — no entry is deleted. **Post**: every pre-existing expected verdict is unchanged except the single FR6 entry, whose verdict flips to `allow` and whose label is rewritten; new entries follow the same three-element form, and their scenario numbering and label wording come from one owner in one pass so they stay mutually consistent | task0001 |
| Published plugin version value | One version string that must read identically from the plugin manifest and from the marketplace entry | **Pre**: both files hold the same value V. **Post**: both hold the same value V′, equal to V with the patch component advanced by at least one, major and minor unchanged. **Ownership**: whichever task changes plugin content owns the bump and performs it in the same change — today that is task0001; a later rework task must check the current value before bumping again rather than assuming a bump is still owed | task0001 |
| Out-of-scope scope sentence | One sentence stating that a form whose substitution output becomes the script body is outside this hook's static analysis | **Post**: the same statement appears in the case label of the corresponding entry and in the payload-extraction docstring, with the same scope — one wording, two locations (FR7, AC-8) | task0001 |
| Mirror divergence note | The note in the mirrored command-word / git-subcommand descriptions saying the mirrors do not carry this file's substitution handling | **Post**: the note also covers the branches added by FR1 / FR2 as local to this file; the two mirror scripts themselves receive no code change (FR9, AS-6) | task0001 |

## Conventions

- **Change scope is exactly four files** (NFR5): the hook module, the case
  table, and the two version manifests. A need for a fifth file is a reportable
  plan deviation, not a licence to expand.
- **Commits are split by concern inside the single task.** The analyzer change,
  the case-table change, and the version bump are separate commits on the task
  branch, so a reviewer can read the behaviour change without the mechanical
  bump in the way, and so a revert of one does not drag the others.
- **No new verdict vocabulary.** A newly reachable path reuses the stage and the
  reason id the existing shape matcher already returns. Introducing a new reason
  id, a new stage, or a blanket `ask` is out of bounds (AS-1, NFR3).
- **Determinism.** The judgement reads the command string only: no path
  resolution, no stat, no subprocess, no evaluation of any substitution (NFR1).
- **False-positive cost equals false-negative cost.** Every widening of the deny
  surface is gated on an existing destructive shape, and the allow-side cases
  that pin normal operation are added to the case table before the widening is
  considered done (NFR3).
- **Documentation wording is part of the deliverable.** Where a scope statement
  appears in more than one place (case label, docstring, mirror note), the
  statements must agree; a divergence is a defect, not a cosmetic difference.

## Decomposition Decisions

### D1: One task for the whole feature

All ten functional requirements are delivered by a single task. The feature
touches four files: the hook module and the case table (FR1-FR9) and the two
version manifests (FR10). An earlier draft of this plan split the manifests into
a second task on file-ownership grounds — the two file sets genuinely do not
overlap, so neither split nor merge risks a conflict — and that split was
rejected on proportion grounds after an independent second opinion. D4 records
why. With one task, "cross-task coordination" does not arise; what remains in
this document is the stage structure, the contracts, and the rationale.

### D2: FR1-FR9 stay together

Splitting the hook work (for example, command-word handling in one task and
payload quoting in another) was considered and rejected. Two reasons:

1. **The acceptance criteria are stated over the whole case table.** The
   requirement that every pre-existing verdict is preserved, and that the full
   suite passes, can only be satisfied by whoever holds the complete file; two
   partial owners would each pass their own worktree's suite and still integrate
   into a red one.
2. **The two code paths interact.** Forms such as an unquoted payload
   substitution followed by a destructive-looking quoted argument pass through
   both the payload-extraction stage and the command-word stage. The criteria
   that pin those forms describe the combined behaviour, so no single
   implementer of a split pair could verify the criterion they are given.

### D3: The out-of-scope range is a design decision, not a deferred defect

The form whose substitution output becomes the script body cannot be resolved
statically without evaluating the substitution, which NFR1 forbids. This feature
therefore declares that form outside the analyzer's scope and makes the
declaration verifiable by requiring the same wording in the case label and the
docstring. A reviewer encountering that `allow` should find the declaration, not
infer an oversight.

### D4: FR10 is folded into the same task, not split out

The version bump is a two-value edit. Giving it its own task was rejected for
three reasons, each of which outweighs the file-ownership tidiness a split would
have bought:

1. **Proportion.** A separate worktree, branch, dispatch and merge for a
   two-value edit costs more process than the work contains.
2. **The repository rule is about the change, not the integration branch.** The
   version-bump rule requires the bump to be in the same change as the
   plugin-file edit. Split out, the task branch that edits the hook carries no
   bump — a literal violation at the task-commit level, even though the
   integration branch would end up correct.
3. **Double-bump hazard.** A standalone bump task, with no tie to the behaviour
   change it publishes, invites a second bump if a later rework round appends
   another task that also edits plugin content. Tying the bump to the task that
   changes the content makes the question "has this change been published yet?"
   answerable from the change itself. The Shared Components contract states the
   corollary for any later rework task: read the current value first, and bump
   only if this round's content change is not yet published.

A standalone bump task also has no acceptance criterion that verifies anything
about the behaviour it publishes, which is a further sign it is not a unit of
work in its own right.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The "statically unknown command word" classification is drawn too wide and starts denying normal commands | Medium | High — a false positive halts unattended runs, since `ask` demotes to `deny` there | Restrict the classification to the two routes fixed by the requirements, and pin eight allow-side commands as cases before the widening is accepted (task0001 AC-3) |
| The rm shape threshold catches recursive-flag-only commands | Medium | High | Require recursion flag AND force flag AND at least one non-flag operand; pin the recursive-flag-only command as an allow case |
| Quote awareness at the payload position leaks into other stages and changes unrelated verdicts | Low | High | Confine raw-text access to the payload argument position (Layer Structure direction rules); require every pre-existing verdict except the single flip to be unchanged |
| The two mirror scripts drift further without anyone noticing | Medium | Medium | Extend the divergence note to cover the new branches; leave the mirrors' code untouched so the divergence stays a documented one |
| The version is bumped twice — once here, once by a later rework task | Low | Medium | The bump belongs to the task that changes plugin content and is committed separately inside it; a later rework task reads the current value first and bumps only if its own content change is unpublished (Shared Components) |
| The bump is forgotten because it rides along with a large behaviour change | Low | Medium | It is a separate commit inside the task and a separate acceptance criterion (task0001 AC-8), not a step buried in the implementation narrative |
| A reviewer reads the deliberate `allow` of the out-of-scope form as a residual vulnerability | Medium | Low | The scope sentence is required in two places and is itself an acceptance criterion |

## Open Questions

- [ ] None. All FR/NFR entries are `resolved` / `status: ok` in workflow.yaml,
      and no design-step artifacts exist for this feature (the step is
      `skipped`, so no visual decisions reach the implementers).
