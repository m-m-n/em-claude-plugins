# Implementation Plan: destructive-guard-command-name-substitution

## Overview

Enter the destructive rm / git routes for a statement whose command word is
produced by a command substitution **only on statically read command-name
evidence**, and make the payload argument position of the shell-command-string
option, the evaluation builtin and the here-string operator distinguish quoting
**only when the payload word is a substitution in its entirety**. This is the
second planning generation for this feature: the first generation's gate
inferred "this is rm / git" from the remaining tokens' flag shape alone, which
review round 1 measured as producing a false `deny` and a miss at the same time,
and its payload quote test matched a quoted substitution anywhere inside the
word, which silently disabled the rescan of mixed `-c` bodies.

## Starting state (read this before the task plan)

This plan is written against an integration branch that **already contains the
first generation's merged work** (task0001). The delta task does not start from
the pre-feature revision:

| Already present on the branch | Status in this generation |
|---|---|
| Skipping a substitution-only token at the command-word position | Kept |
| A dash pre-gate plus a recursion-AND-force-AND-operand pre-screen before the rm route | **Removed** — replaced by command-name evidence |
| An unconditional call into the git route whenever a substitution was skipped | **Removed** — replaced by command-name evidence |
| The routing block written inline in the main dispatch loop | **Extracted** into one named function; the pre-screen helper is deleted |
| A quote test at the payload position that matches a quoted substitution anywhere inside the word | **Replaced** by a whole-word precondition |
| Case entries for the first generation's scenarios | Kept; two labels rewritten, no entry deleted |
| A published version value one patch above the pre-feature value | Advanced again (see D6) |

Whoever implements the delta therefore edits existing branches of behaviour
rather than adding new ones to a pristine file, and must read the current state
of the two changed source files before deciding what to remove.

## Technology Stack

- **Language**: Python 3 — the hook module and its case runner are plain
  standard-library Python; no framework is involved.
- **Key libraries**: none. No dependency is added and no package manifest exists
  in this repository to add one to.
- **New dependency licenses**: none introduced by this feature. `project.license`
  is `none`, so there is no project license for a dependency to conflict with,
  and nothing to record beyond this line.
- **Test runners**: the two commands already declared in workflow.yaml
  `project.components` (the case-suite runner and the repository unit-test
  discovery). No new runner, harness or test dependency is introduced (NFR6).

## Layer Structure

The hook is a single-file static analyzer over one command string. Its stages run
strictly in order; each stage consumes the previous stage's output and never
re-enters an earlier one.

| # | Stage | Responsibility | Status in this generation |
|---|-------|----------------|---------------------------|
| 1 | Pre-lexical marking | Replaces substitution occurrences in the raw command text with markers before lexing | **Frozen** — marker structure and the token attribute set are unchanged (AS-6) |
| 2 | Lexing | Produces the token sequence carrying the existing attributes | **Frozen** |
| 3 | Payload extraction | For the shell-command-string option, the evaluation builtin and the here-string operator, decides which token is the script body | **Changed** — the quote distinction gains a whole-word precondition (FR4, FR5, FR12) |
| 4 | Command-word resolution and route entry | Decides a statement's command name; for a substitution at that position, reads the command name statically and hands the remainder to a route | **Rebuilt** — evidence reading (FR11), evidence-gated routes (FR1, FR2, FR3), single extracted entry point (FR13) |
| 5 | Shape matching | Matches remaining tokens against the existing rm / git destructive shapes | **Callers only** — its thresholds, tiers and reason ids are unchanged |
| 6 | Decision and unattended demotion | Fixes the final tier and applies the unattended demotion | **Frozen** (NFR4) |

### Direction rules

- **R1 — raw-text access.** Stage 3 (payload boundary) and stage 4's evidence
  reading are the only readers of the raw pre-lexical segment body. Both read it
  as text: splitting, slicing and basename extraction only — never expansion,
  evaluation, subprocess launch or filesystem access (NFR1). This supersedes the
  first generation's rule that confined raw-text access to stage 3; that
  confinement is precisely what forced stage 4 to guess from flag shape (D5).
- **R2 — evidence, not shape.** A route is entered only when the command name
  read at stage 4 is the route's own command. The remaining tokens' flag shape
  is never an entry condition.
- **R3 — no route-side threshold.** Once a route is entered, the remainder is
  handed to the shape matcher unchanged and the matcher's own threshold decides.
  The route adds no floor of its own (AS-3).
- **R4 — unreadable falls open.** When the command name cannot be read, no route
  is entered and the statement keeps today's blanket `allow`. Falling back to
  `ask` is forbidden: `ask` demotes to `deny` unattended, so a fallback `ask`
  would halt normal operation (NFR3).
- **R5 — no new vocabulary.** No new decision tier and no new reason id is
  created anywhere. A newly reachable path reuses whatever the existing matcher
  returns (AS-1).
- **R6 — never stricter than the plain spelling.** For every input, the
  substitution-headed spelling's tier and reason id equal what the plain spelling
  of the read command name produces for the same remaining arguments. No path
  exists on which the substitution-headed spelling is judged more strictly
  (NFR7). This is the invariant review round 1 found violated and is the single
  most important property of this generation.
- **R7 — frozen stages.** Stages 1, 2 and 6 receive no change; the quote
  knowledge of stage 3 and the evidence of stage 4 are consumed where they are
  produced and are never carried on the token side.

## Shared Components

Contracts that outlive the task that implements them. Each is stated so that a
later rework task can be checked against it without re-deriving the reasoning.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Guard decision logic (`em-workflow/hooks/destructive-guard.py`) | Produces a tier (`allow` / `ask` / `deny`) and a reason id for one command string | **Pre**: the command string is the only input; no filesystem access, no subprocess, no substitution evaluation. **Post**: for any command containing no substitution, the tier and the reason text are identical to the pre-change behaviour; the set of reason ids is unchanged | task0002 |
| Command-name evidence reader | Given the command-word-position substitution token, yields either one command name or "unreadable" | **Pre**: reads the pre-lexical segment body as text and the token's position; mapping from token position to raw text relies on occurrence order (AS-7). **Post**: the name is the basename of the last whitespace-separated word of the substitution body; a name is never derived from any earlier word of the body; "unreadable" is returned when the body is empty, when the last word begins with a dash, when the position cannot be mapped, or when nesting makes the raw extent indeterminable | task0002 |
| Substitution-head route entry point | The single place that classifies a substitution-headed statement and hands its remainder to a route | **Pre**: called once per statement whose command-word position held a substitution token; receives the statement's words and its segment. **Post**: returns the shape matcher's own tier and reason id, or no decision at all; the complete entry condition lives inside it, with only the call left at the dispatch site; the superseded pre-screen helper no longer exists | task0002 |
| Payload boundary rule | Decides, at the payload argument position, whether the payload word is the body or whether the next word is promoted to it | **Pre**: the quote distinction is evaluated only when the word at that position is a substitution in its entirety. **Post**: a whole-word quoted substitution is the boundary (no promotion; trailing arguments are the real shell's zeroth argument); every other word — including one that merely contains a quoted substitution — keeps today's behaviour, so a mixed body is still pushed back for rescanning | task0002 |
| Case table (`em-workflow/hooks/tests/destructive-guard-cases.json`) | The behavioural contract of the guard, as expected-verdict / label / command triples | **Pre**: every pre-existing entry is retained — no entry is deleted, including `deny` and `ask` entries. **Post**: every pre-existing expected verdict is unchanged except the two this generation inverts (the quoted payload entry and the quoted here-string entry), each of which keeps its entry with a rewritten label; new entries follow the same three-element form; scenario numbering and label wording come from one owner in one pass | task0002 |
| Published plugin version value | One version string that must read identically from the plugin manifest and from the marketplace entry | **Pre**: both files hold the same value V, which already publishes the first generation's content. **Post**: both hold the same value V′, equal to V with the patch component advanced by at least one, major and minor unchanged. **Ownership**: whichever task changes plugin content owns the bump and performs it in the same change; a later task reads the current value from the files (never from a document) and bumps only when its own content change is not yet published by that value | task0002 |
| Out-of-scope declaration | One statement of what this hook's static analysis deliberately does not decide | **Post**: it covers both forms — a form whose substitution *result* becomes the script body, and a substitution-headed form whose command name cannot be read — and the same statement appears in the corresponding case labels and in the payload-extraction docstring, with the same scope; a divergence in scope is a defect | task0002 |
| Mirror divergence note | The note saying the mirrored guard scripts do not carry this file's substitution handling | **Post**: the note also covers the branches and the function added by this generation as local to this file; the two mirror scripts receive no code change | task0002 |

## Conventions

- **Change scope is exactly four files** (NFR5): the hook module, the case table
  and the two version manifests. A need for a fifth file is a reportable plan
  deviation, not a licence to expand.
- **Commits are split by concern inside the task**: case-table changes, analyzer
  changes, version bump. A reviewer can then read the behaviour change without
  the mechanical bump in the way, and a revert of one does not drag the others.
- **Allow-side cases land before the widening.** A change that could halt normal
  operation is written only after the allow-side cases that pin normal operation
  exist in the table (NFR3). Concretely: the false-positive guards for non-rm /
  non-git commands taking recursion and force flags are written first.
- **Existing deny / ask cases are never deleted** (`.claude/rules/hook-tests.md`).
  When a decision must invert, the entry stays and its expected verdict and label
  change — it becomes a false-positive guard on the allow side.
- **Determinism.** The judgement reads the command string only: no path
  resolution, no stat, no subprocess, no evaluation of any substitution (NFR1).
- **Documentation wording is part of the deliverable.** Where a scope statement
  appears in more than one place (case label, docstring, mirror note), the
  statements must agree; a divergence is a defect, not a cosmetic difference.
- **No new verdict vocabulary** (R5).

## Cross-task Design Decisions

### D1: One task for the whole delta (re-affirmed)

The delta is delivered by a single task. The first generation reached the same
conclusion and nothing in review round 1 challenged it — the findings were about
what the gate decided, not about how the work was divided.

Two properties make a split actively harmful here:

1. **The acceptance criteria are stated over the whole case table.** "Every
   pre-existing verdict is preserved" and "the full suite passes" can only be
   satisfied by whoever holds the complete file. Two partial owners would each
   pass their own worktree's suite and integrate into a red one, and because
   tasks run fully in parallel with no ordering, both would be editing the same
   JSON file for the same merge.
2. **The two code paths interact.** A payload substitution followed by a
   destructive-looking argument passes through the payload stage and the
   command-word stage in sequence; the criteria that pin those forms describe the
   combined behaviour. Neither implementer of a split pair could verify the
   criterion they were given.

The task's acceptance criteria run slightly past the usual size guidance. That is
accepted deliberately: the alternative is two owners of one behavioural contract
and one test file, which review round 1's findings show is exactly the kind of
seam where this feature goes wrong.

### D2: Evidence, not shape (supersedes generation 1)

The route's entry discriminator is the command name read statically out of the
command-word-position substitution, never the remaining tokens' flag shape.
Generation 1 used shape, and review round 1 measured that shape produces both
failure directions at once: benign commands that legitimately take recursion and
force flags flipped from `allow` to `deny`, while the operand-first and
force-flag-free rm spellings stayed `allow`. Flag shape is not evidence of
identity — it is a property that many unrelated commands share (AS-2).

Affected: FR1, FR2, FR3, FR11; the whole of stage 4.

### D3: The threshold belongs to the shape matcher

Both of generation 1's pre-gates are removed: the one requiring the token after
the skip to begin with a dash, and the recursion-AND-force-AND-operand
pre-screen. Once evidence says the command is rm, the remainder goes to the
matcher unchanged and the matcher decides, exactly as it does for the plain
spelling. This is what makes R6 hold by construction rather than by inspection:
any route-side floor is a place where the two spellings can diverge.

The generation-1 objection — that dropping the force-flag requirement would
falsely deny a recursion-flagged grep — does not apply once D2 is in place: that
command never enters the route, because its evidence does not read as rm (AS-3).

Affected: FR1, FR2.

### D4: Unreadable evidence falls open, and the limit is declared

A substitution-headed form whose command name cannot be read is not routed and
keeps its `allow`. This is a deliberate narrowing of detection range relative to
generation 1's shape-only implementation, and it is written down rather than left
to be inferred: the out-of-scope declaration names both undecidable forms in one
wording, placed in the case labels and in the payload-extraction docstring. A
reviewer meeting that `allow` should find the declaration, not infer an oversight
(AS-5).

Affected: FR3, FR7, FR11.

### D5: Raw-text access widens to the evidence reader

Generation 1's direction rule allowed only the payload stage to consult the raw
pre-lexical text. That rule is revised (R1): the evidence reader consults it too.
The rule existed to protect determinism, and reading raw text does not threaten
determinism — it is string processing over an input the process already holds,
with no expansion, no subprocess and no filesystem access. Keeping the old rule
would have left stage 4 with nothing but flag shape to reason from, which is the
defect D2 removes.

The narrower property that does survive is R7: raw-text knowledge is consumed in
the stage that reads it and is never stored on the token side, so the marker
structure and token attributes stay frozen (AS-6).

Affected: FR4, FR11; the Layer Structure direction rules.

### D6: This generation bumps the published version again

The value currently in the two manifests publishes the first generation's
content. The delta changes plugin content again, so under the repository's
version-bump rule that change carries its own bump, and the manifests advance by
one more patch. The first generation's own risk register anticipated exactly this
case and fixed the test: a later task reads the current value from the files and
bumps only when its own content change is not yet published by that value. It is
not, so it bumps.

The value is deliberately never named in any planning document, so that a value
advanced by unrelated work between planning and implementation is still handled
correctly.

Affected: FR10, NFR5.

### D7: Two decision inversions are pinned, not deleted

This generation carries two inversions from `deny` to `allow`: the quoted payload
entry (already inverted by generation 1) and the quoted here-string entry (a side
effect of generation 1 that was never declared). Both are correct against real
shell semantics — the body is what executes and the trailing argument is the
shell's zeroth argument — and both stay in the case table as allow-side
false-positive guards with rewritten labels. The repository rule against deleting
existing `deny` / `ask` cases is satisfied by retention, not by exemption.

The second inversion reaching review undeclared is itself the lesson: a branch
that changes any decision must have a case exercising it in the same change.

Affected: FR6, FR12, NFR2.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The evidence reader mis-maps a token position to raw text and reads the wrong command name | Medium | High — a wrong name either denies a benign command or misses a destructive one | Mapping relies on occurrence order and returns "unreadable" whenever it cannot be established (R4, AS-7); the unreadable form is pinned as an allow case |
| Evidence is taken from an arbitrary word of the substitution body | Low | High — a form where rm or git appears as another command's argument would be falsely denied | The contract fixes the evidence as the basename of the *last* word only (Shared Components); the mixed-body form is called out in the task plan's edge cases |
| Removing both pre-gates widens the rm route onto benign commands | Low | High — a false positive halts unattended runs, since `ask` demotes to `deny` | The widening is gated on evidence (D2, D3); eight non-rm commands taking recursion and force flags are pinned as allow cases before the gate change is accepted |
| The whole-word payload precondition is written as a containment test again | Medium | High — this is the exact critical regression of round 1; the guard silently stops rescanning ordinary `-c` bodies | Three mixed-body forms are pinned as `deny` cases; the payload side is made symmetric with the here-string side, which already tests the whole-word property first |
| The function extraction changes behaviour while moving code | Medium | Medium | The extraction and the gate change are one task but separate commits; the full case suite is the invariant across both |
| A branch that changes a decision reaches review with no case exercising it | Medium | High — this is how the here-string inversion escaped round 1 | Every inverted decision is an entry in the case table in the same change (D7); the case-table completeness scenario is an explicit verification item |
| The version is bumped twice or not at all across the two generations | Low | Medium | D6 fixes the test as "is this content change published by the current value?", answered by reading the files rather than any document |
| The mirror scripts drift further without anyone noticing | Medium | Medium | The divergence note is extended to the new branches and the new function; the mirrors' code stays untouched so the divergence stays a documented one |

## Open Questions

- [ ] None blocking. All FR / NFR entries are `status: ok` in workflow.yaml and
      the design step is `skipped`, so no visual decisions reach the implementer.
- [ ] Traceability note for the orchestrator (not a planning decision): the
      generation-1 requirements-to-tests mapping in workflow.yaml references
      scenario ids that the revised SPEC renumbered. The planner's patch can only
      append ids, so the superseded ids stay until something with removal rights
      cleans them up. VERIFICATION.md's coverage table is the accurate mapping
      for this generation.
