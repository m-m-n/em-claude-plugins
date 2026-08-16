# Implementation Plan: routeback-reset-scope-consistency

## Overview

Make Step I.2.c's route-back derive its admissibility gate, its workflow.yaml
write set and its worktree/branch cleanup from one and the same source — Step
I.2.b step 1's reconciled state — without disturbing any literal or ordering
the existing contract suites assert, back the new wording with a new
document-contract test module, and bump the plugin version in both registries.
Documentation + manifests + tests only; no hook, script, agent or skill
behaviour changes.

## Technology Stack

- **Protocol document**: Markdown (`em-workflow/references/implement-phase.md`)
  — the SSOT the orchestrator executes inline; prose is the deliverable.
- **Registries**: JSON (`em-workflow/.claude-plugin/plugin.json`, root
  `.claude-plugin/marketplace.json`) — plugin version metadata.
- **Tests**: Python `unittest` (standard library only), modules under the
  repository-root `tests/`, discovered with
  `python3 -m unittest discover -s tests` from the project root.
- **New dependencies**: none — no library is added, so no license check
  applies. `project.license` is `none`; there is nothing to record beyond
  this line.

## Layer Structure

Three layers with a one-way dependency direction:

1. **Protocol layer** — `em-workflow/references/implement-phase.md`. States the
   rules the orchestrator follows. Never references the verification layer.
2. **Registry layer** — the two `.claude-plugin` JSON manifests. Carries only
   version metadata; independent of the protocol layer's content.
3. **Verification layer** — modules under `tests/`. READS layers 1 and 2 as raw
   text or parsed JSON and asserts properties of them. Layers 1 and 2 never
   read layer 3.

Consequence for parallel work: a verification-layer module may read a file
owned by another task (reads never conflict); only a WRITE to the same file
conflicts.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `em-workflow/references/implement-phase.md` | The protocol document under change | Written by task0001 ONLY. Postconditions every other task and every existing suite relies on: the heading `### I.2.c: Failed handling` stays byte-identical; the batch-mode paragraph stays the byte-identical TAIL of the I.2.c section; no line of the file, after stripping indentation and markdown backticks, begins with `git ` and also contains `commit` or `add -A` | task0001 (writes), task0002 (reads: none — see D6) |
| Anchor set (NFR1–NFR6) | The raw literals, orderings and containment properties existing suites depend on | Precondition on every write to the protocol document: every item under D3 survives unchanged. Postcondition: `python3 -m unittest discover -s tests` is green with `tests/test_implement_routeback_gate.py` and `tests/test_recycled_task_id_consistency.py` unmodified | task0001 |
| Reconciled state (Step I.2.b step 1) | The single task-state derivation source this feature restores | Defined and owned by I.2.b step 1 (journal last-event-per-task replay + I.2.a's recycled-task-id carve-out + `git merge-base --is-ancestor` verification of any `merged` claim). Every new sentence CITES it as owner and never restates its rule | task0001 |
| `tests/` module namespace | Where this feature's new assertions live | Exactly one new module per task, at the fixed path in the ownership map below, so parallel tasks never write the same file. No task modifies, imports from, or deletes any pre-existing module | task0001, task0002 |
| Plugin version value `0.1.39` | The version both registries must carry after this change | Written by task0002 ONLY, replacing `0.1.38` in `em-workflow/.claude-plugin/plugin.json` (`version`) and in the `em-workflow` entry of the root `.claude-plugin/marketplace.json` (`version`). Postcondition: both files parse as JSON and report the same string | task0002 |

## Conventions

### File ownership map (one writer per file)

Tasks run fully in parallel in separate worktrees and merge back
independently, so every file has exactly one owning task. No task writes a
file owned by another; reading another task's file is allowed.

| File | Owner |
|------|-------|
| `em-workflow/references/implement-phase.md` | task0001, then task0003 (D9) |
| `tests/test_routeback_reset_scope_consistency.py` | task0001, then task0003 (D9) |
| `em-workflow/.claude-plugin/plugin.json` | task0002 |
| `.claude-plugin/marketplace.json` | task0002 |
| `tests/test_routeback_reset_scope_version_bump.py` | task0002 |

Files no task may touch: `tests/test_implement_routeback_gate.py`,
`tests/test_recycled_task_id_consistency.py` and every other pre-existing
module under `tests/`; anything under `em-workflow/hooks/`,
`em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/`; any file
under `em-workflow/references/` other than `implement-phase.md`; anything
under another feature's `feature-docs/` directory.

Each task additionally writes its own TDD record at
`test-docs/routeback-reset-scope-consistency/{task_id}.tests.yaml` inside its
own worktree (one file per task, so the records can never conflict).

### Prose conventions (protocol document)

- English, matching the surrounding paragraphs; bullet and paragraph structure
  unchanged.
- Identifiers, file names and status values in backticks (`` `pending` ``,
  `` `tasks.{T}.status` ``, `` `merged` ``).
- Minimal, locally consistent edits — no copy-editing of prose the
  requirements do not touch.
- New sentences wrap consistently with the paragraph they join and never
  reflow a protected raw literal (D3).

### Test conventions (both new modules)

Both modules follow the pattern of the two protected modules:

- A module docstring naming the task, the acceptance criteria it covers, and
  the matcher → negative-proof inventory (including recorded exemptions).
- Module-level path constants derived from the module file's own location
  (repository root → target file); never a hard-coded absolute path, never the
  current working directory.
- Section slicing by heading literal (heading → next heading) before asserting
  on a section's content.
- A whitespace-normalizing helper collapsing every whitespace run to a single
  space, used for ALL prose assertions. Byte-identity and line-wrap assertions
  use the RAW text instead — mixing the two is the known source of both false
  passes and false failures in this suite.
- JSON files are parsed, never pattern-matched.
- Negative proofs per D8.

## Cross-task Design Decisions

### D1: Two tasks, split by file ownership rather than by requirement

Every prose requirement (FR1–FR6) edits one file — and FR1–FR4 edit one
section of it — so splitting them across tasks would guarantee a merge
conflict on every parallel run, and would split wording from the assertions
that pin that exact wording. The decomposition therefore follows file
ownership: task0001 takes the protocol document plus the module asserting its
content; task0002 takes the two registry manifests plus the module asserting
their version. The two file sets are disjoint. Affected tasks: both.

### D2: One derivation source, one vocabulary

All three route-back surfaces name the same source. The vocabulary below is
used identically by the document and by both test modules, so a later reader
(and every matcher) can tell that the three surfaces state one rule:

| Term | Meaning as used in the document |
|------|--------------------------------|
| journal last event | The last event the journal replay yields for a task id (`launched` / `merged` / `failed`, or none) |
| terminal (last event) | `merged` or `failed` |
| reconciled state | The per-task classification Step I.2.b step 1 produces: journal last-event-per-task replay, I.2.a's recycled-task-id carve-out, and `git merge-base --is-ancestor` verification of any `merged` claim |
| union (of two sources) | workflow.yaml's `tasks.{T}.status` OR the reconciled state — EITHER blocks; never a replacement of one by the other |

Contracts that follow, not prose preferences:

- The gate's `merged` conjunct is a union of the two sources, exactly parallel
  to the `in_progress` conjunct's existing union (FR1); the union is added
  AROUND the retained literal "no task has status `merged`", never substituted
  for it.
- The write set's reset target set is "every task whose Step I.2.b step 1
  reconciled state is `failed`" (FR2), replacing the workflow.yaml-status
  basis.
- The cleanup target set is exactly the set the write set just reset, and the
  document says in so many words that those are tasks confirmed NOT merged
  (FR3).

Affected tasks: task0001 (author), task0002 (its assertions must not
contradict the vocabulary).

### D3: Anchor-preservation contract (NFR1–NFR6)

Two existing test modules, neither of which may be modified, assert literals
and orderings inside `implement-phase.md`. This is the single most likely way
this change breaks, so it is a precondition on every write to the document.

**Raw, line-wrap-sensitive literals** (matched against un-normalized text — a
reflow breaks them even when the prose is unchanged):

- Step I.0: `require at least one task in `` `tasks` `` whose` at the end of a
  line, followed by a three-space-indented line beginning
  `` `status == pending` ``.
- Step I.2.a: `` `tasks.*.status`. Select `` at the end of a line, immediately
  followed by a line beginning `unlaunched tasks (no journal event yet and
  `` `status != merged` ``, ascending`.
- Step I.2.b step 3: the commit literal that breaks after `implement wake` and
  continues on a three-space-indented line beginning `phase reconcile"`, with
  `"$RECONCILE_TIP"` on that same continuation line.

**Byte-identical literals**: the heading `### I.2.c: Failed handling`, and the
batch-mode paragraph that closes the I.2.c section — including its position as
the byte-identical TAIL of that section.

**Ordering / proximity constraints inside I.2.c** (evaluated on the
whitespace-normalized section):

1. The FIRST occurrence of `tasks.{T}.status` has `pending` within the
   following 60 normalized characters.
2. `` `create-plan` to `needs_update` ``, `` `implement` step back to
   `pending` ``, `` `tasks.{T}.status` back to `pending` `` and
   `` `tasks.{T}.notes` `` all precede `git worktree remove --force`.
3. `commit-docs.sh` precedes `git worktree remove --force`, which precedes
   `End the phase with a`.
4. The literal "terminal journal last event (`merged` or `failed`)" survives
   and still precedes "`create-plan` to `needs_update`".
5. The literals "no task has status `merged`" and "no task has status
   `in_progress`" survive, in that order, joined inside ONE sentence — the
   normalized text between them contains no sentence break (no ". ").
6. "re-read from workflow.yaml task statuses", "not inferred from the drain
   above" and "a union of two independent sources" survive.
7. The normalized text after "When the gate does not hold" contains none of
   "make one ordered workflow.yaml write set", "git worktree remove --force",
   "ROUTEBACK_TIP"; and neither "rework" nor "append" occurs anywhere in the
   I.2.c section.

**Whole-file invariant**: no line, after stripping indentation and backticks,
begins with `git ` and contains `commit` or `add -A` — every commit
instruction goes through `commit-docs.sh`.

Affected tasks: task0001 (must not break any of them while editing; owns the
regression assertions for all of them).

### D4: All new prose is inserted BEFORE the section's protected tail

Every sentence FR1–FR4 adds lands strictly before the batch-mode paragraph
that closes I.2.c, so that paragraph stays the byte-identical tail (NFR1). The
same rule applies inside I.2.a: FR6's sentence is added after the existing
unreachability sentence's terminal "can never arise.", which is AFTER the
protected Step I.2.a wrap literal, so that literal is never re-wrapped.
Affected tasks: task0001.

### D5: SSOT non-duplication

Added text cites, never restates: Step I.2.b step 1 for the reconciled state
and its `git merge-base --is-ancestor` verification, `references/workflow-patch.md`
for the `replace_planning` / `replace_all` permission conditions, and
`skills/develop/SKILL.md` Step B's stop-condition-3 precedence clause for the
develop-side precedence. A restatement is a defect even when it is currently
accurate — the same drift this feature exists to remove. Affected tasks:
task0001.

### D6: Version-bump safety against existing monotonic assertions

`tests/test_recycled_task_id_version_bump.py` asserts the plugin version is on
the `0.1.x` line, strictly greater than a fixed pre-feature baseline (37), and
identical in both registries. `0.1.39` satisfies all of it, so no existing
module needs to change. The new module for this feature raises its own
baseline to 38, so it goes red on an un-bumped tree and stays durable across
later unrelated bumps. task0002 makes no assertion about
`implement-phase.md` — the whole-file bare-git-line invariant is task0001's
(NFR6/TS-7) and is already covered by two existing modules — so the two new
modules never assert the same property against a file the other owns.
Affected tasks: task0002.

### D7: One verification command for both tasks

`python3 -m unittest discover -s tests` from the repository root is the only
project command (no build, no format, no E2E). Each task runs the FULL suite
in its own worktree before merging; every assertion a task's own module makes
concerns only files that task owns, so each task's suite is green in its own
worktree independently of the other's merge state. Affected tasks: both.

### D8: One matcher literal, shared by the assertion and its negative proof

Carried forward from the preceding feature's verify finding: a negative proof
written with its own copy of a matcher's literal proves nothing about the
matcher that actually runs — the two copies drift, and the assertion can then
pass against wording that never changed. Both new modules follow:

1. Each matcher asserting NEW post-change wording keeps its literal in ONE
   module-level constant; the positive assertion and its negative proof both
   read that constant. The literal is never spelled twice.
2. Each negative proof runs against a captured pre-change sample — a verbatim
   excerpt of the file under test at this feature's implement base commit
   (`c8843c9c086323c5378c6b3abe89dc63e5c02a40`), not paraphrased, not
   reconstructed — normalized with the module's own helper first, so the proof
   exercises the same comparison the positive assertion does.
3. Each sample carries a RETAINED anchor (a phrase present in both the sample
   and the post-change file) asserted positively in a guard test, so a sample
   that was emptied or truncated cannot make an absence assertion pass
   vacuously.
4. Matchers asserting RETAINED pre-change wording, and pure regression guards,
   need no negative proof; each such exemption is recorded per matcher in the
   module docstring inventory rather than left implicit.

Affected tasks: both.

### D9: Rework round 1 (verify-sourced) — amended shared contracts

task0003 is a verify-sourced rework task (failed items MANUAL-1 / MANUAL-2 /
MANUAL-3). It edits two files task0001 already owns, so the contracts below are
amended rather than added alongside the originals. Everything not listed here —
D2's vocabulary table, D3's anchor set, D4, D5, D7, D8 — applies to task0003
unchanged.

1. **File ownership passes to task0003** for
   `em-workflow/references/implement-phase.md` and
   `tests/test_routeback_reset_scope_consistency.py`. task0001 and task0002 are
   both `merged`, so no writer runs concurrently with task0003 and the
   one-writer-per-file rule is preserved by the transfer rather than broken by
   it. The "files no task may touch" list is unchanged, and now also covers
   `tests/test_routeback_reset_scope_version_bump.py` (task0002's module) for
   task0003.
2. **D2's write-set contract is amended.** The reset target set is no longer
   "every task whose Step I.2.b step 1 reconciled state is `failed`" alone; it
   is the union of that set with "every task workflow.yaml reports
   `status: failed`" — the same union shape D2 already defines for the gate's
   two halves, for the same reason: the postcondition the write set claims, and
   `references/workflow-patch.md`'s `replace_all` permission conditions, are
   evaluated over workflow.yaml's own `tasks.{T}.status` values, while Step
   I.2.b step 3 can write `failed` for a task whose reconciled state is not
   `failed` (a `failed`/malformed report with no journal event). Naming only
   the reconciled state left the postcondition resting on an unstated
   inclusion that does not hold. The reconciled-state member stays the leading,
   verbatim member of the phrase so task0001's TS-2 matcher keeps matching.
3. **D2's cleanup contract is amended**: "the document says in so many words
   that those are tasks confirmed NOT merged" becomes "the document says that
   those are tasks not merged UNDER THE TWO SOURCES this path reads
   (workflow.yaml `status` and Step I.2.b step 1's reconciled state), and
   records the residual it cannot see". Reviewer option (a) for MANUAL-2 — a
   per-candidate `git merge-base --is-ancestor` check before cleanup — is NOT
   adopted: it would add a verification step to the protocol that SPEC.md never
   requires, and either narrow the cleanup target set below the set the write
   set just reset (breaking the postcondition for a task that is merged yet
   recorded `failed`) or force the gate's `merged` union to a third source,
   contradicting FR1's two-source shape and the literals task0001's module
   pins. The honest documentation of the residual is option (b), and it keeps
   the change documentation-only (NFR8).
4. **No further version bump.** `0.1.39` (task0002) has not shipped; it covers
   this feature's whole change set, including task0003's edits. The existing
   monotonic assertions (patch > 38, both registries equal) stay satisfied, so
   the two `.claude-plugin` manifests remain out of task0003's file set and
   keep task0002 as their owner.

Affected tasks: task0003 (author of all four); task0001 / task0002 are merged
and unaffected in place.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New gate wording introduces an earlier `tasks.{T}.status` mention and breaks the 60-character proximity assertion | High | High | D3 constraint 1; task0001 states the safe phrasing shape and re-runs the full suite after every document edit |
| A union sentence inserted between the two retained gate literals breaks the one-sentence join | Medium | High | D3 constraint 5; the `merged` union sentence is placed after the joined sentence, never between the two literals |
| Added prose reflows a protected raw literal in I.0 / I.2.a / I.2.b | Medium | High | D3's raw-literal list plus D4's insert-after-the-literal placement rule; task0001 owns raw-text regression assertions with failure messages naming the wrap |
| New prose displaces the batch-mode paragraph from the section tail | Low | High | D4; byte-identity assertion re-run on the post-change file |
| FR4's added blocker leaks a route-back instruction into the rejected branch | Medium | High | D3 constraint 7; asserted as containment over the normalized text after "When the gate does not hold" |
| A new sentence restates I.2.b's rule instead of citing it, re-creating the drift being removed | Medium | Medium | D5; asserted as the presence of the citation, and reviewed against the vocabulary in D2 |
| Both tasks write `tests/` and collide | Low | Medium | Fixed module paths in the ownership map; one module per task |

## Open Questions

- [ ] None blocking. Two items are recorded as deliberate non-goals rather
      than gaps: I.2.b step 3's own precedence ambiguity between its "verified
      merged" clause and its "report is `failed`/malformed" clause (SPEC.md
      A-2), and any change to hook behaviour (NFR8). Both stay out of scope
      for this feature.
