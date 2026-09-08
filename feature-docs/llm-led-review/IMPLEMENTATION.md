# Implementation Plan: llm-led-review

## Overview

Re-shape the em-workflow review phase so each selected perspective is reviewed
by ONE non-Claude reviewer (codex / litellm harness), and a single Opus
evaluator subagent judges the whole round's reviewer output afterwards; the
orchestrator keeps every write, gate and next-action decision. All work is
document / agent-prompt / registry editing inside `em-workflow/` plus one new
unittest module per task under `tests/`.

## Technology Stack

- **Language**: Markdown / YAML / JSON (plugin source), Python 3 standard
  library `unittest` for the structural-assertion tests.
- **New dependencies**: none. `project.license` is `none`, so no license
  constraint applies to this feature — there is no new dependency and no
  license to record.
- **Existing external harnesses** (unchanged, both optional): codex CLI via the
  bundled wrapper script; the separately-installed `vertex-review` plugin for
  the litellm harness.

## Layer Structure

| Layer | Owner file(s) | Responsibility | May depend on |
|---|---|---|---|
| Orchestration | `references/review-phase.md` | perspective selection, dispatch, chain walk, mechanical gates, records, commits, gates, next action | registries, contracts |
| Registries | `references/reviewers.yaml`, `references/review-rules.yaml` | which perspective gets which primary-reviewer chain; the mechanical floor | — |
| Reviewer I/O SSOT | `references/review-protocol.md`, `references/review-output-schema.json` | reviewer input names, skip vocabulary, output schema (also read by the external `vertex-review` plugin) | — |
| Evaluation I/O SSOT | `references/review-evaluation-contract.md` (new) | the evaluator's input block and output object | reviewer I/O SSOT (cites, never restates) |
| Agents | `agents/review-evaluator.md` (new), `agents/reviewer.md`, `agents/codex-reviewer.md` | thin prompts that resolve and follow the SSOT documents | the two SSOT layers above |
| Entry points / docs | `skills/review/SKILL.md`, `README.md`, the two plugin manifests | the user-facing description of the above | all |
| Tests | `tests/` | structural assertions, one module per task over that task's own files | all |

Dependency direction is one-way downward: an agent prompt may cite an SSOT
document, an SSOT document never cites an agent prompt's internals, and no
registry cites the phase protocol.

## Shared Components

Every literal in this table is a CROSS-TASK CONTRACT. Tasks run fully in
parallel in separate worktrees, so a task that writes one of these literals and
a task whose own document merely cites it must both use it byte-for-byte; a
paraphrase is an integration break that only surfaces at review. Each task's
test module asserts these literals **as text inside the files that task owns** —
never by checking that a sibling task's file exists on disk.

| Component | Responsibility | Contract | Used by tasks |
|---|---|---|---|
| Evaluator agent definition | Opus subagent that evaluates one round of reviewer output | File `em-workflow/agents/review-evaluator.md`; frontmatter `name: review-evaluator`, `model: opus`, `effort: xhigh`, `tools: Read, Glob, Grep, Bash` (no Write/Edit) | 0002, 0005 |
| Evaluator dispatch | The only dispatch site of the evaluator | `Task(subagent_type="em-workflow:review-evaluator")`, written in `references/review-phase.md` Phase R3a | 0002 |
| Fallback reviewer dispatch | Keeps `agents/reviewer.md` reachable for the invariants check | `Task(subagent_type="em-workflow:reviewer")` stays present in `references/review-phase.md` Phase R2, on the no-available-entry branch only | 0002, 0004 |
| Evaluation contract document | SSOT of the evaluator's input block and output object | Path `em-workflow/references/review-evaluation-contract.md`; the orchestrator passes its path as the input field `evaluation_contract_path`; the evaluator resolves it fail-closed exactly as reviewers resolve `protocol_path` | 0001, 0002 |
| Evaluator input block | What the orchestrator hands the evaluator | Field names: `evaluation_contract_path`, `project_root`, `review_mode`, `changed_files`, `round`, `cross_validation`, `perspectives_dispatched`, `reviewer_outputs`, `round_context`, `spec_path` (only when the spec perspective ran), `lessons` (optional). `perspectives_dispatched` entries carry `run_id`, `perspective`, `role`, `status`, `skip_reason`, and `model` for litellm runs; `reviewer_outputs` entries carry `run_id` plus that run's verbatim reviewer output | 0001, 0002 |
| Evaluator output object | One machine-checkable object | Root fields: `findings`, `round_summary`, `recommended_action`, `action_rationale`. Finding fields: `stable_id`, `severity`, `category`, `file`, `line`, `title`, `description`, `suggestion`, `source_run_ids`, `confidence` | 0001, 0002 |
| `recommended_action` vocabulary | Round-level advice, never a decision | Closed set `auto_fix` / `another_round` / `rework` / `complete`; a value outside it is treated as absent | 0001, 0002 |
| Source identity vocabulary | Orchestrator-owned provenance | `codex:<perspective>`, `litellm:<model>:<perspective>`, `claude:<perspective>` (fallback run), `claude:evaluator` (a finding left with no valid `source_run_ids`) | 0001, 0002 |
| Registry chain key | Per-perspective primary-reviewer chain | In `references/reviewers.yaml` the per-perspective key is `primary_chain` (ordered list of `{harness, model?}`, replacing today's `cross_validation` key); `claude_skill` and `requires_spec` keep their names and meanings | 0002, 0003, 0005 |
| Primary chains | The registry's per-perspective values, quoted identically wherever they are documented | security: codex → litellm `muse-spark`. performance and spec: litellm `vertex-deepseek-v3.2` → litellm `muse-spark` → codex. architecture: litellm `vertex-glm-5` → litellm `muse-spark` → codex. comprehensive (new): codex → litellm `vertex-glm-5` → litellm `muse-spark`. license (new): codex → litellm `vertex-deepseek-v3.2` → litellm `muse-spark` | 0003, 0005 |
| `perspective_runs` role vocabulary | Round-record extension | `primary` / `fallback` / `evaluator` under a new `role` key; the evaluator entry carries no `perspective` | 0002 |
| Confidence corrections | The only orchestrator-side confidence arithmetic | `+15` (cap 100) when ≥ 2 perspectives flag the same site; hard cap `50` for a finding outside `changed_files`; `60` as the default assigned to un-evaluated findings on the evaluator-failure path | 0002 |
| Retryable skip vocabulary | Chain-walk trigger, unchanged | `rate_limited`, `budget_exhausted`, `harness_unavailable` — same three strings, same per-harness / per-model advance semantics | 0002, 0004 |
| Perspective → category vocabulary | Must accept every perspective that now has a primary chain | `references/review-output-schema.json`'s `category` enum contains all six registry perspectives, `license` included | 0003, 0004 |
| Phase headings | Stable anchors for tests and cross-document citations | `## Phase R3a: Evaluation (single Opus evaluator)` and `## Phase R3b: Mechanical gates on the evaluation` replace today's `## Phase R3: Aggregate, sanitize, score`; the R0 / R1 / R2 / R2b / R4 / R5 / R6 headings are unchanged | 0002 |
| Plugin version | One value in two registries | `0.1.59` in `em-workflow/.claude-plugin/plugin.json` and in the `em-workflow` entry of `.claude-plugin/marketplace.json` (patch bump from 0.1.58, matching this repository's practice of patch-stepping behaviour changes) | 0005 |
| Evaluator accountability field (rework round 1) | The reviewer sites an evaluation must account for | Output-object root field `dismissed_sites`; each entry carries `file`, `line`, `run_id` and `reason`. A reviewer-reported critical/high site matched by `same_site` against neither `findings` nor `dismissed_sites` is lifted into `findings` individually, carrying that run's own text, the run's orchestrator-assigned source identity, the dispatching perspective as `category`, and confidence `60` | 0006 |
| Evaluator finding source field (rework round 1) | FR7-conformant field name | The evaluator's finding field is `sources`; the name `source_run_ids` is retired. Its values are run ids and are ALWAYS overwritten by the orchestrator with its own run identities; a finding left with no valid run is attributed to `claude:evaluator` | 0006 |
| Evaluator run degradation marker (rework round 1) | How a successful-but-incomplete evaluation is recorded | The evaluator's `perspective_runs` entry is `status: completed` with `degraded: true` whenever its Task succeeded; `status: failed` is used only when the Task itself failed or a required root field was missing | 0006, 0007 |
| `unreviewed_perspectives` (rework round 1) | Perspectives that produced no completed reviewer run | A list of perspective names. It is BOTH a round-record root field (Phase R5) and a Phase R3a evaluator input field; present and empty when there are none. A perspective enters it only after its Claude fallback has been dispatched and produced no completed run. Producing the value is task0007's; stating what the evaluator does with it is task0006's | 0006, 0007 |

## Conventions

- **Naming**: the new agent is `review-evaluator` (file name, frontmatter
  `name`, and dispatch string all agree); the new reference document is
  `review-evaluation-contract.md`. No other new plugin file is introduced.
- **Language**: plugin documents keep their current language mix (English
  protocol prose, Japanese where the existing file already uses it); agent
  `description` frontmatter stays Japanese, matching its siblings.
- **SSOT discipline**: each fact has exactly one owning document; other
  documents cite it by path/section instead of restating it. The evaluation
  contract cites the reviewer protocol for everything reviewer-side and never
  restates the reviewer output schema.
- **Test ownership**: every task adds its own module under `tests/` covering
  only the files that task owns, using the Python standard library only (this
  repository's test code has no external dependency — YAML is read as text, not
  through PyYAML). No task asserts the existence or content of a sibling task's
  file; cross-file parity is verified at integration time by
  `em-workflow/scripts/check-plugin-invariants.py` and the verify phase.
- **Error-handling policy**: every failure in this phase degrades, never
  aborts — a harness-less perspective falls back to the Claude reviewer, a
  non-retryable skip is kept, and an unusable evaluation falls back to the
  reviewers' own findings. Aborts stay reserved for the pre-existing
  SSOT-resolution failures in Phase R0.
- **No new AskUserQuestion gate anywhere in the new path** (NFR3), therefore no
  new `gate_id` and no `references/batch-policies.yaml` entry.
- **Read-only reviews** (NFR5): neither the primary reviewers nor the evaluator
  may write, commit, switch branches, or run formatters.

## Cross-task Design Decisions

### D1 — One primary reviewer per perspective, Claude only as fallback

For each selected perspective the orchestrator takes the first entry of that
perspective's `primary_chain` whose harness is available and dispatches exactly
one reviewer for it. When no entry is available it dispatches
`em-workflow:reviewer` instead, with `role: fallback`. The two are mutually
exclusive: the Claude reviewer is never launched alongside a harness reviewer.
All of a round's primary/fallback Task calls are still issued in ONE message.
Affects tasks 0002 (protocol), 0003 (chains exist for all six perspectives),
0004 (agent role framing), 0005 (user-facing description).

### D2 — The `cross_validation` axis keeps its computation and loses its dispatch effect

`review-rules.yaml`'s `cross_validation` rule block, its Layer-1 evaluation and
its post-Layer-2 re-evaluation stay exactly as they are, and the resulting
boolean is still recorded in `workflow.yaml` `review.plan.cross_validation` and
in the round record — so `references/workflow-schema.md` and
`skills/plan-writing/SKILL.md` need no edit and stay outside this feature's
change set. What changes is its consequence: because every selected perspective
already runs a non-Claude primary reviewer, the flag no longer adds a second
dispatch. It is passed to the evaluator as the `cross_validation` input field,
marking the round as high-intensity. Only the prose describing the old
"claude + one cross-model run" double dispatch is rewritten. Affects tasks
0002, 0003.

### D3 — The orchestrator recomputes identity, never trusts the evaluation's

`stable_id`, `sources` and `category` are orchestrator-owned. The gates run in
this order:

1. `file` lexical check (reject absolute paths, `..`, NUL), then existence
   under `project_root`.
2. `severity` must be one of critical / high / medium, else drop.
3. `category` must be one of THIS round's dispatched perspectives, else drop
   unconditionally — never relabel (relabelling launders injection). The
   pre-existing forced relabel of out-of-`changed_files` findings to
   `comprehensive` is REMOVED for the same reason; such findings keep their
   category and take only the confidence cap.
4. `title` / `description` / `suggestion` truncated at 4096 bytes each.
5. `stable_id` recomputed from the unchanged normalization formula (the
   `title_normalized`, `line_bucket`, `stable_id`, `coupling_id` and
   `same_site` definitions stay verbatim); any evaluator-supplied value is
   discarded.
6. `sources` built by mapping `source_run_ids` onto the run identities the
   orchestrator itself assigned; unknown ids are dropped, and a finding left
   with none is attributed to `claude:evaluator`.
7. Confidence = the evaluator's value, then the two mechanical corrections of
   the Shared Components table, in that order.

The orchestrator also keeps its mechanical dedupe (same category + `same_site`:
richest description, union of sources, max severity, max confidence) and the
round-context suppression of `declined` findings, so `round_context` semantics
survive unchanged. Affects tasks 0001 (the contract states which fields are
orchestrator-owned), 0002 (performs them).

### D4 — Evaluation failure degrades to the reviewers' own findings

If the evaluator's Task fails or returns an object missing required root
fields, the orchestrator neither aborts nor skips the round: it takes each
primary/fallback reviewer's own findings through the same gates as D3 (with
`category` fixed to the dispatching perspective, `sources` set to that run's
identity, and confidence `60`), records the evaluator run with `status: failed`
in `perspective_runs`, and proceeds to Phase R4 with its own decision
procedure. Affects tasks 0001 (the contract states the failure is the
orchestrator's to absorb), 0002 (defines the procedure).

### D5 — The evaluation is advice; the orchestrator decides

`recommended_action` never overrides the completion gate
(`residual_critical_high == 0`), the `--report-only` flag, the auto-fix loop
cap, the batch rework cap, or the fixed rework ordering of
`references/rework-task-synthesis.md` Section 10. Writes, commits and
AskUserQuestion stay orchestrator-exclusive. Affects tasks 0001, 0002.

### D6 — Backward compatibility of the round record

`reviews/roundN.yaml` keeps its path, file name and every field downstream
reads: `stable_id` / `file` / `line` / `resolution` (Phase R0 `round_context`)
and `severity` / `category` / `resolution_reason` / the review plan's Layer-2
reasons (`skills/develop/SKILL.md` retrospect signals). The only change is
additive: `perspective_runs` entries gain `role`, and one entry records the
evaluator run. A record written before this change stays readable with no
translation, which is why `skills/develop/SKILL.md` needs no edit. Affects
task 0002.

### D7 — Existing tests are part of the contract

These literals must survive unchanged because existing test modules assert
them:

- `references/review-phase.md`: the fix-commit block's shared
  `em-workflow-merge.lock`, `flock 9`, the stage-before-commit ordering and the
  commit message prefix `fix({feature}): review round `
  (`tests/test_review_implement_develop_lock_contracts.py`); the Phase R5 / R6
  batch statements about the withheld report body and the unchanged
  round-record writes (`tests/test_batch_quiet_output_phase_wiring.py`); the
  Phase R5 rework ordering and its citations
  (`tests/test_rework_synthesis_contract.py`).
- `references/review-rules.yaml`: the `domains vocabulary` header comment block
  must stay intact and in parity with `skills/plan-writing/SKILL.md`
  (`check_domains_vocabulary_parity`).
- `agents/codex-reviewer.md`: the scratchpad temp-file discipline section
  (`tests/test_codex_reviewer_temp_file_isolation.py`).
- The two plugin manifests: the em-workflow version must stay numerically
  greater than the past baseline in both registries, looked up by `name`
  (`tests/test_plugin_version_parity.py`).

Affects tasks 0002, 0003, 0004, 0005.

### D8 — Evaluator accountability is a per-site floor declared by the evaluation contract (rework round 1)

Amends D3 and D4; the rest of both decisions stands. An evaluation object is
never discarded on coverage grounds: coverage is not a degradation trigger,
and D4's degradation keeps exactly its two structural triggers (evaluator
Task failure, missing required root field). In its place, every critical/high
site a reviewer run reported must appear in the evaluation's `findings` or in
its `dismissed_sites`; a site in neither is lifted individually with the
values pinned in Shared Components. Because `dismissed_sites` is part of the
evaluator's own contract, the floor checks a declared completeness property
of the output rather than re-judging the evaluation's content. `same_site` is
the only site predicate anywhere in R3b — the `(file, line_bucket)` reduction
is not a site predicate. D3's step 3 tightens from set membership to equality
with the dispatched perspective of the finding's source run (SPEC FR6), and
D3's step 6 reads the field as `sources`. The evaluator additionally inspects
the round's `changed_files` per dispatched perspective, so a schema-valid
empty reviewer result is corroborated rather than accepted in silence — no
second reviewer is dispatched, so SPEC FR3 is untouched. Affects task0006.

### D9 — The Claude fallback is reachable at chain exhaustion (rework round 1)

Amends D1's timing, not its exclusivity. "No available chain entry" is
evaluated whenever the orchestrator must decide who reviews a perspective:
at Phase R2 from the availability probes, and again at Phase R2b when the
walk ends with every eligible entry having proven unavailable (retryable
skip, or unavailable harness) or with a malformed result and no further
entry. In that state the perspective receives exactly ONE Claude fallback
dispatch, after the walk — never concurrently with a harness reviewer and
never as a second opinion alongside a completed one, so D1's mutual
exclusivity and SPEC FR3's no-parallel clause both hold unchanged. That
dispatch does not consume the 2-hop harness budget, and all perspectives
reaching the state in one round go in ONE message (FR9). A perspective whose
fallback also produces no completed run stays in `unreviewed_perspectives`,
which remains record-keeping and never becomes a completion blocker — a
blocker would need a new user gate, which NFR3 forbids. Affects task0007.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Two tasks spell a shared literal differently (chain key, chain contents, field names, dispatch string) | High | High | Every shared literal is pinned in Shared Components and quoted verbatim, never paraphrased |
| Editing `review-phase.md` breaks an existing test's asserted literal | Medium | High | D7 lists the protected literals; each task re-runs the full suite before finishing |
| The `review-protocol.md` change alters the external `vertex-review` reviewer's behaviour (NFR4) | Medium | High | task0004 is restricted to role framing; input names, `skip_reason` strings and the output schema's existing members are additive-only |
| The evaluator becomes a single point of failure for the round | Medium | High | D4's degradation path |
| Evaluator-assigned confidence is less predictable than mechanical counting (SPEC A-6) | High | Medium | Corrections limited to the two pinned ones; the value is recorded per finding so retrospect can audit it |
| comprehensive / license have no track record on a non-Claude primary reviewer (SPEC A-3) | Medium | Medium | Both chains lead with codex and the Claude fallback stays reachable; revisit from round records |

## Open Questions

- [ ] D2: retaining `cross_validation` as a recorded intensity signal with no
      dispatch effect is a planner decision, not a SPEC requirement — confirm
      at review that its one live consumer (the evaluator input field)
      justifies keeping the flag.
- [ ] D4: the evaluator-failure degradation path (and its default confidence of
      60) is not required by any FR; confirm it is wanted rather than an abort.
- [ ] FR7 asks for the round-record finding shape; the evaluator emits
      `source_run_ids` where the round record has `sources`, because FR6 makes
      `sources` orchestrator-owned. Confirm this field-name split is
      acceptable.
- [ ] SPEC A-3 (comprehensive / license on a non-Claude primary reviewer)
      remains an unvalidated assumption after this feature ships.
