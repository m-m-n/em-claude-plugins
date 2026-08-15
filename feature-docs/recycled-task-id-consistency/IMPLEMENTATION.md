# Implementation Plan: recycled-task-id-consistency

## Overview

Harmonize the recycled-task-id rule across its four sites in the implement-phase
protocol document, give the I.2.c route-back an explicit terminal-journal-event
precondition with a defined failure outcome, bump the plugin version in both
registries, and back all of it with Python `unittest` document-contract tests.
The change is documentation + manifests + tests only — no hook, script, agent or
skill behaviour changes.

## Technology Stack

- **Protocol documents**: Markdown (`em-workflow/references/*.md`) — the SSOT the
  orchestrator executes inline; prose is the deliverable.
- **Registries**: JSON (`em-workflow/.claude-plugin/plugin.json`, root
  `.claude-plugin/marketplace.json`) — plugin version metadata.
- **Tests**: Python `unittest` (standard library) — document-contract assertions,
  discovered from the repository root as `python3 -m unittest discover -s tests`.
- **New dependencies**: none. Only the Python standard library is used, which the
  existing suite already depends on. `project.license` is `none`, so no license
  constraint applies to this feature; nothing new to record.

## Layer Structure

Three layers, with a one-way dependency direction:

1. **Protocol layer** — `em-workflow/references/implement-phase.md`. States the
   rules the orchestrator follows. Never references the test layer.
2. **Registry layer** — the two `.claude-plugin` JSON manifests. Independent of
   the protocol layer's content; carries only the version metadata.
3. **Verification layer** — modules under `tests/`. READS layers 1 and 2 as text
   or parsed JSON and asserts properties of them. Layers 1 and 2 never read
   layer 3.

Consequence for parallel work: a verification-layer module may read a file owned
by another task (reads never conflict); only a WRITE to the same file conflicts.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `em-workflow/references/implement-phase.md` | The protocol document under change | Written by task0001 ONLY. Postcondition after task0001's edit, relied on by task0002's assertions: no line of the file, after stripping indentation and markdown backticks, begins with `git ` and also contains `commit` or `add -A`; the heading `### I.2.c: Failed handling` and the batch-mode paragraph that closes the I.2.c section stay byte-identical, with that paragraph still the last text of the section | task0001 (writes), task0002 (reads) |
| NFR1 anchor set | The literals and orderings existing suites depend on | Precondition on every edit: the raw, un-normalized literals and the intra-section orderings listed under "Anchor-preservation contract" below survive unchanged. Postcondition: `python3 -m unittest discover -s tests` is green with the six protected modules unmodified | task0001, task0002 |
| `tests/` module namespace | Where new document-contract assertions live | Exactly one new module per task; the two module paths are fixed in the ownership map below so parallel tasks never write the same file. Neither task modifies any pre-existing module | task0001, task0002 |
| Plugin version value `0.1.37` | The version both registries must carry | Written by task0002 ONLY, into both `em-workflow/.claude-plugin/plugin.json` (`version`, replacing `0.1.36`) and the `em-workflow` entry of the root `.claude-plugin/marketplace.json` (`version`, a NEW key). Postcondition: both parse as JSON and report `0.1.37` for `em-workflow` | task0002 |

## Conventions

### File ownership map (one writer per file)

Tasks run fully in parallel in separate worktrees and merge back independently,
so every file has exactly one owning task. No task writes a file owned by
another; reading another task's file is allowed.

| File | Owner |
|------|-------|
| `em-workflow/references/implement-phase.md` | task0001 |
| `tests/test_recycled_task_id_consistency.py` | task0001, then task0003 (D8) |
| `em-workflow/.claude-plugin/plugin.json` | task0002 |
| `.claude-plugin/marketplace.json` | task0002 |
| `tests/test_recycled_task_id_version_bump.py` | task0002 |
| `test-docs/recycled-task-id-consistency/task0003.tests.yaml` | task0003 |

The one-writer rule constrains tasks that run in PARALLEL. task0003 belongs to a
later rework round, so it is the only task in flight when it writes; it inherits
sole write ownership of `tests/test_recycled_task_id_consistency.py` from the
merged task0001 rather than sharing it (D8).

Files no task may touch: anything under `em-workflow/hooks/`,
`em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/`,
`em-workflow/references/` other than `implement-phase.md`, anything under
`feature-docs/implement-routeback-gate/`, and every pre-existing module under
`tests/`.

### Prose conventions (protocol document)

- English, matching the surrounding paragraphs; bullet structure unchanged.
- Identifiers, file names and status values in backticks (`` `pending` ``,
  `` `tasks.{T}.status` ``, `` `queue_launch_guard.py` ``).
- No rationale beyond what the requirements state.
- New sentences are wrapped consistently with the paragraph they join, and never
  reflow a protected literal (see the anchor-preservation contract).

### Test conventions (both new modules)

Both modules follow the pattern of `tests/test_implement_routeback_gate.py`:

- A module docstring naming the task and the acceptance criteria it covers.
- Module-level path constants derived from the module file's own location
  (repository root → `em-workflow` → the file under test); never a hard-coded
  absolute path and never the current working directory.
- Section slicing by heading (from a heading literal to the next heading
  literal) before asserting on a section's content.
- A whitespace-normalizing helper that collapses every whitespace run to a
  single space, used for ALL prose assertions, so a line-wrap choice never makes
  an assertion brittle. Byte-identity assertions use the raw text instead.
- At least one negative-proof test class per module: each new matcher is shown
  to flag the corresponding pre-change wording (a test that can never fail is
  not a test). The shape that proof must take — shared constant, captured
  sample, normalization, non-vacuity guard, recorded exemptions — is D8.

### Error-handling convention

Neither task introduces runtime error handling. The one error path this feature
defines is a protocol outcome (route-back inapplicable), expressed as prose in
the protocol document.

## Cross-task Design Decisions

### D1: Two tasks, split by file ownership rather than by requirement

`implement-phase.md` is a single file and every prose requirement (FR1–FR6) edits
it, so those requirements cannot be split across tasks without guaranteeing a
merge conflict on every parallel run. The decomposition therefore follows file
ownership: task0001 takes the whole protocol document plus the tests that assert
its content; task0002 takes the two registry manifests plus the test that asserts
their version and the document's bare-git-line invariant. Affected tasks: both.

### D2: Shared vocabulary for the rule's four sites

All four sites and both test modules use one vocabulary, so a later reader (and
every matcher) can tell that the sites state one rule:

| Term | Meaning as used in the document |
|------|--------------------------------|
| journal last event | The last event the journal replay yields for a task id (`launched` / `merged` / `failed`, or none) |
| terminal (last event) | `merged` or `failed` |
| non-terminal (last event) | `launched`, or no event at all |
| reconciled state | The per-task classification I.2.b step 1 produces by replaying the journal AND applying I.2.a's recycled-task-id rule |
| the recycled-task-id rule | The single normative statement in I.2.a; every other site cites it rather than restating a condition |

Consequences that are contracts, not prose preferences: I.2.b step 3 keys its
`failed` write-back off the RECONCILED STATE (never off the journal last event
directly), and I.2.c's route-back precondition is stated with "terminal journal
last event", the same vocabulary as I.2.a. Affected tasks: task0001 (author),
task0002 (its assertions must not contradict the vocabulary).

### D3: Anchor-preservation contract (NFR1)

Six existing test modules assert literals and orderings inside
`implement-phase.md`. They are not modified by this feature, so every edit must
leave the following intact. This is the single most likely way the change
breaks, so both tasks treat it as a precondition on any write.

**Raw, line-wrap-sensitive literals** (matched against un-normalized text — a
reflow breaks them even when the prose is unchanged):

- In Step I.2.a: `Select` at the end of one line, immediately followed by a line
  beginning `unlaunched tasks (no journal event yet and `` `status != merged` ``,
  ascending`.
- In Step I.0: `require at least one task in `` `tasks` `` whose` at the end of a
  line, followed by a three-space-indented line beginning
  `` `status == pending` ``. This literal must still occur EARLIER in the file
  than the Step I.2.a literal above.
- In Step I.2.b step 3: the commit literal that breaks after `implement wake`
  and continues on a three-space-indented line beginning `phase reconcile"`,
  with `"$RECONCILE_TIP"` on that same continuation line.

**Byte-identical literals**: the heading `### I.2.c: Failed handling`, and the
batch-mode paragraph that closes the I.2.c section — including its position as
the last text of that section.

**Ordering / proximity constraints inside I.2.c** (evaluated on the
whitespace-normalized section):

1. The FIRST occurrence of `tasks.{T}.status` has `pending` within the following
   60 normalized characters.
2. `create-plan` → `needs_update`, `implement` step back to `pending`,
   `tasks.{T}.status` back to `pending`, and `tasks.{T}.notes` all precede
   `git worktree remove --force`.
3. `git worktree remove --force` precedes the first `commit-docs.sh`, which
   precedes `End the phase with a`.
4. The phrase "no task has status `merged`" is still present.
5. The slice from `If any task has already merged` to `- **abort phase**`
   contains neither `rework` nor `append`; and no occurrence of `rework` or
   `append` is introduced anywhere in the I.2.c section.
6. The old phrasings "every existing task is still `pending`" and "create-plan
   exemption owns that precedence" stay absent.

**Whole-file invariant**: no line, after stripping indentation and backticks,
begins with `git ` and contains `commit` or `add -A` — every commit instruction
goes through `commit-docs.sh`.

Affected tasks: task0001 (must not break any of them while editing), task0002
(asserts the whole-file invariant).

### D4: Ordering constraint 5 governs the whole I.2.c section

The new FR4 text lands inside I.2.c and must describe a terminal outcome without
using the words `rework` or `append`, which the existing suite forbids in the
merged-task branch and which this feature's own scenario forbids for the whole
section. The route-back-inapplicable outcome is therefore described as reaching
the same terminal as the existing "abort phase" option, via develop's stop
condition 3. Affected tasks: task0001.

### D5: SSOT non-duplication (NFR2)

The added text cites, never restates: `references/workflow-patch.md` for the
`replace_all` / `replace_planning` permission conditions,
`skills/develop/SKILL.md` Step B's stop-condition-3 precedence clause for the
develop-side precedence, and the document's own "Supporting cast: journal, hooks,
resume" inventory for hook behaviour. The FR6 scope sentence names the four
hooks and the claim "never consults `tasks.{T}.status`" — never the stronger and
false "never reads workflow.yaml" — and points at the inventory instead of
restating hook internals. Affected tasks: task0001.

### D6: Version-bump safety against existing monotonic assertions

Three existing modules assert the em-workflow plugin version is on the `0.1.x`
line and strictly greater than a fixed pre-feature baseline. `0.1.37` satisfies
all of them, so no existing module needs to change. The root marketplace entry
currently has no `version` key and no existing test reads that file, so ADDING
the key is safe. Affected tasks: task0002.

### D7: Both tasks run the same single verification command

`python3 -m unittest discover -s tests` from the repository root is the only
project command (no build, no format, no E2E). Each task runs the FULL suite in
its own worktree before merging; a task's own new module must be green there,
which is possible because each task's assertions only concern files that task
owns — with the single documented exception of task0002's bare-git-line
assertion, which holds both before and after task0001's edit. Affected tasks:
both.

### D8: One matcher literal, shared by the assertion and its negative proof

Verify found (TS-14 / SC-6) that a negative proof written with its own copy of a
matcher's literal proves nothing about the matcher that actually runs: the two
copies drift, and the assertion can then pass against wording that never
changed. The contract every negative proof in this feature's test modules
follows is therefore:

1. Each matcher that asserts NEW post-change wording keeps its literal in ONE
   module-level constant. The positive assertion and its negative proof both
   read that constant; the literal is never spelled twice.
2. Each negative proof runs against a captured pre-change sample — a verbatim
   excerpt of the file under test at the implement phase's base commit — and
   applies the module's own whitespace-normalizing helper to it first, so the
   proof exercises the same comparison the positive assertion does.
3. Each sample carries a RETAINED anchor asserted positively in a guard test, so
   a sample that was emptied or truncated past the relevant sentence fails
   loudly instead of making every absence assertion pass vacuously.
4. Matchers that assert RETAINED pre-change wording, and pure regression guards,
   need no negative proof; the module records that exemption per matcher in its
   docstring inventory rather than leaving it implicit.

This is a cross-task contract because it governs both new modules'
`TestValidationDetectsRegressions` classes and the NFR5 clause both tasks
inherit. `tests/test_recycled_task_id_version_bump.py` already satisfies it for
both of its matchers and is not modified. Affected tasks: task0001 (author of
the module task0003 extends), task0002 (already conformant), task0003
(brings the eight remaining matchers into conformance).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An edit reflows a raw literal an existing suite depends on, breaking a module this feature must not modify | High | High | D3 lists every protected literal; task0001 adds its own regression tests (TS-7, TS-8) that fail with a message naming the wrap, and runs the full suite before merging |
| The FR4 text introduces the word `rework` or `append` into I.2.c | Medium | High | D4; asserted as an absence over the whole I.2.c section |
| Added sentences in I.2.a push the batch-mode paragraph or the I.2.c heading out of byte-identity | Low | High | Byte-identity assertions re-run on the post-change file; the edits stay inside their own paragraphs |
| The FR6 sentence overstates the hooks' behaviour ("never reads workflow.yaml") | Medium | Medium | D5 fixes the exact claim; asserted both positively and as an absence |
| A second normative restatement of the rule leaks into I.2.b or I.2.c, re-creating the drift this feature removes | Medium | High | D2's vocabulary plus the FR2 assertion that the other sites cite rather than restate |
| Both tasks write `tests/` and collide | Low | Medium | Fixed module paths in the ownership map; one module per task |

## Open Questions

- [ ] None blocking. SPEC.md records one deliberate NON-GOAL for follow-up
      outside this feature: `queue_stop_guard.py` goes silent for the remainder
      of a feature once any task carries a permanent `failed` journal event. No
      requirement here addresses it and no hook file is modified.
