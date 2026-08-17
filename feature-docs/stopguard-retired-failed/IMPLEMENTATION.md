# Implementation Plan: stopguard-retired-failed

## Overview

The implement-phase Stop hook stops reading a retired task id's residual
`failed` journal event as a genuine failure: workflow.yaml's per-task status
becomes the discriminator, mirroring the orchestrator's existing
recycled-task-id carve-out. The plugin's SSOT document and its two version
registries are brought into line in the same change.

## Technology Stack

- **Language**: Python 3 — standard library only. Neither the hook nor the
  tests gain an import outside the stdlib (NFR2).
- **Documents**: Markdown (`em-workflow/references/`) and JSON (the two
  plugin registries).
- **New dependencies**: none. No package manifest is added or edited, so
  `project.license: none` imposes no constraint on this feature and there is
  no new dependency license to record.

## Layer Structure

| Layer | Feature files | Responsibility | Depends on |
|---|---|---|---|
| Runtime net | `em-workflow/hooks/queue_stop_guard.py` | classify the declared tasks of an in-progress feature and decide block / pass | nothing else in the repository |
| Contract tests | `tests/test_queue_stop_guard.py` | drive the hook as a subprocess over throwaway fixture roots; assert exit code and stderr | the hook |
| SSOT documents | `em-workflow/references/implement-phase.md` | state the phase protocol, including the scope of the recycled-task-id rule and the hook roster | nothing (prose only) |
| Plugin registries | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | plugin identity and version | nothing |

Allowed direction: tests read the hook, the documents and the registries.
Nothing in the other three layers depends on the tests, and the hook never
reads a document or a registry at runtime.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Recycled-task-id carve-out (the classification rule) | the single definition of how a `failed` journal last event combines with the per-task workflow status | **Pre**: the task id is a key under workflow.yaml's `tasks:` mapping AND its journal last event is `failed`. **Post**: exactly one classification results — *unlaunched* if and only if that task's workflow status reads exactly `pending`; *failed* (whole-feature suppression, hook exits 0) in every other case, including `failed`, `in_progress`, `merged`, an unrecognized value, an absent status key, and a task block whose status cannot be determined. A `launched` last event is unaffected by this rule and always means in-flight. | task0001 implements it; task0002 documents it |
| Pinned-literal surface of `implement-phase.md` | pre-existing test modules that are OUTSIDE this feature's declared change set assert literal phrases and section headings inside the document task0002 edits | **Pre**: no test module outside the declared change set is edited. **Post**: every phrase those modules pin is still present after the edit, and the full suite is green. The literals in scope are listed in D3. | task0002 (edits the document); task0001 (must not edit those modules either) |
| Declared change set | the boundary of this feature: the five feature-specific paths in SPEC.md plus `feature-docs/{feature}/**` and `test-docs/{feature}/**` | **Pre**: a task's file list is a subset of the declared set. **Post**: the observed change set is contained in the declared set — a needed file outside it is a reportable plan deviation, never a licence to expand. | task0001, task0002 |
| Full-suite green (`python3 -m unittest discover -s tests`) | the shared completion gate for both tasks | **Pre**: the task's own edits are in place. **Post**: the whole suite passes from the repository root, including every module neither task owns. | task0001, task0002 |

## Conventions

- **Parsing**: workflow.yaml is read line by line, never through a YAML
  library. A per-task status read is scoped to the individual `taskNNNN:`
  block (that key's own indented keys), so a workflow-step status line can
  never be taken for a task status, nor the reverse.
- **Fail-open**: every unexpected condition resolves to a silent exit 0 and
  no exception escapes the hook's top-level entry point. Ambiguity resolves
  toward suppression, never toward blocking.
- **Surface stability**: the BLOCK and WARNING stderr strings, the exit-code
  vocabulary (0 / 2), the sidecar's field set and its atomic write technique
  are unchanged. No new file and no new sidecar field is introduced.
- **Test style**: hook behaviour is asserted by invoking the hook as a
  subprocess against a throwaway fixture root, per the existing module's
  style; document and registry content is asserted by reading the file.
- **Version bump**: only the version values change in the two registries;
  every other field, and the key set of each file, stays as it is.
- **Naming**: no new public identifier is introduced beyond the one status
  read described in D2; existing helper names in the hook keep their meaning.

## Cross-task Design Decisions

### D1 — The discriminator is the per-task workflow status, and ambiguity suppresses

The carve-out applies to exactly one pair: journal last event `failed` plus a
per-task workflow status that reads exactly `pending`. Every other status
value, an absent status, and an undeterminable task block classify as failed
and keep suppressing the block. Rationale: the journal is append-only and
carries no retirement marker, so no journal-only discriminator exists; and
the hook is a net, not an authority, so unreadable state must never produce
a block (SPEC A1, A4). Affects task0001 (behaviour) and task0002 (wording).

### D2 — The status read is block-scoped and line-based

The read walks the same single line-based pass family already used for the
step status and the task-id list, associating each status value with the
`taskNNNN:` key whose indented block it sits in. A task block that yields no
determinable status contributes the conservative classification of D1 rather
than an error. No YAML library, no second file open pattern, no extra
subprocess or filesystem scan (FR3, NFR2, NFR4). Affects task0001.

### D3 — The documentation amendment is additive with respect to pinned literals

Pre-existing test modules assert literal phrases inside the section
`implement-phase.md` I.2.a and use its following heading as a section
boundary. Those modules are outside this feature's declared change set and
must not be edited, so the amendment has to leave all of the following in
place while still removing the false claim about the Stop hook:

- all four hook filenames still appear, backtick-quoted, inside I.2.a;
- the phrase *never consult `tasks.{T}.status`* still occurs in I.2.a — now
  predicated of the other three hooks only;
- the phrase *governs only the orchestrator's interpretation of the journal*
  still occurs in I.2.a;
- the sentence stating the carve-out is deliberately scoped to `failed` only,
  and the retained sentence about a `launched` last event always meaning
  in-flight, both survive verbatim;
- the `### Supporting cast` heading text is unchanged (three modules index on
  it as a section boundary);
- the document nowhere claims that a hook never reads workflow.yaml.

Affects task0002. The mechanical check is the full suite (D5).

### D4 — The version bump is verified by an existing durable-invariant module

The suite already contains a module asserting that both registries parse,
that their versions agree, that the version advances past the previous
patch baseline, and that the surrounding key sets and identity fields are
unchanged. Bumping both registries to the target version satisfies it
without a new test module; the literal target value is checked at verify
time by reading the two files. Affects task0002.

### D5 — No new test module; the declared change set is the outer bound

`tests/test_queue_stop_guard.py` is the only test file this feature may
create or modify. Consequence: the positive wording assertion for the
document amendment has no automated home, and is verified as a document
check in the verify phase (VERIFICATION.md, manual section) rather than by a
new test. Affects both tasks; it is the reason FR6 carries only the
regression sweep as its automated test.

### D6 — Task boundaries: disjoint files, one global non-modification constraint

task0001 owns the hook and its test module; task0002 owns the document and
the two registries. No file is claimed by both tasks, so the two branches
merge into the integration branch independently. The constraint that the
other three queue hooks stay unmodified is global: it is stated in both task
plans, and owned as a requirement by task0001, the only task that opens the
hooks directory.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A workflow-step status line is mistaken for a task status (or the reverse), producing a wrong classification | medium | high (a wrongly blocked or wrongly silenced session) | D2's block scoping, plus a test scenario that exercises a fixture containing both kinds of status line |
| The document amendment breaks a pinned literal in a test module this feature may not edit | medium | medium (red suite, no way to fix inside the change set) | D3's explicit retention list; the full suite is part of task0002's acceptance |
| The conservative default is applied too widely and the net stays silent where it should fire | low | medium | the classification contract enumerates the suppressing cases exactly; the retired-id scenario asserts a block, not merely the absence of a crash |
| The version bump edits a field the existing invariant module pins | low | medium | D4 limits the edit to the version values; the module runs as part of the suite |

## Open Questions

- [ ] FR6's positive wording ("the Stop hook is named as the explicit
      exception") has no automated assertion available inside the declared
      change set; it is verified as a document check at verify time (D5).
- [ ] NFR3 (journal read-only) and NFR4 (single line-based pass, no added
      scan or subprocess) have no dedicated automated scenario; both are
      verified by inspection at verify time, as SPEC.md itself states for
      NFR4.
