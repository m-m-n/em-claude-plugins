# Implementation Plan: threat-model-stride

## Overview

The create-plan planner gains a mandatory STRIDE threat-modeling pass (every
feature, every tier) that writes `feature-docs/{feature}/THREAT-MODEL.md`;
its mitigations flow into task acceptance criteria and VERIFICATION.md (the
TASK.md Expected Result at the minimal tier), and the review phase hands a
security-only `threat_model_path` input to review-security so that a designed
but unimplemented mitigation becomes a finding. No phase, step, gate_id or
batch policy is added.

## Technology Stack

- **Documents**: Markdown agent prompts, skills, references and templates
  under `em-workflow/` — the whole deliverable.
- **Tests**: Python 3 standard-library unittest, run by
  `python3 -m unittest discover -s tests` (document-contract tests, the
  repository's existing convention).
- **New dependencies**: none. `project.license` is `none`, and no library is
  introduced, so no license entry applies.

## Layer Structure

| Layer | Documents | Responsibility | May cite |
|-------|-----------|----------------|----------|
| Knowledge | `em-workflow/references/templates/threat-model.md`, `em-workflow/skills/plan-writing/SKILL.md`, `em-workflow/skills/review-security/SKILL.md` | Formats and judgment criteria | nothing in lower rows |
| Worker prompts | `em-workflow/agents/implementation-planner.md`, `em-workflow/agents/codex-reviewer.md` | One worker's process | Knowledge, Contracts |
| Contracts | `em-workflow/references/contracts/planner-contract.md`, `em-workflow/references/contracts/spec-writer-contract.md`, `em-workflow/references/review-protocol.md` | Shapes, permissions, input fields | Knowledge |
| Phase protocols | `em-workflow/references/phases/create-plan-phase.md`, `em-workflow/references/review-phase.md` | Orchestrator steps | Contracts, Knowledge |

Every rule has exactly one owning document (Conventions, "Rule ownership");
every other document cites it and never restates it.

## Shared Components

| Component | Responsibility | Contract | Used by tasks |
|-----------|----------------|----------|---------------|
| SC-1 THREAT-MODEL.md format | The artifact the planner writes and the security reviewer reads | Below | task0001 (template), task0002 (writes), task0003 (template input field), task0005 (Codex prompt), task0006 (reads) |
| SC-2 Mitigation reflection | Where each mitigation lands, per tier | Below | task0001 (rules), task0002 (applies), task0003 (TASK.md permission) |
| SC-3 Minimal-tier TASK.md append | The only permitted planner write to TASK.md | Below | task0002 (cites), task0003 (owns) |
| SC-4 `threat_model_path` review input | Resolution, validation, dispatch and reviewer semantics | Below | task0004 (resolve / pass), task0005 (protocol, Codex prompt), task0006 (use) |
| SC-5 Missing-mitigation finding | Detection target and finding site | Below | task0005 (Codex grounding rules must admit it), task0006 (owns) |
| SC-6 Version target | FR11 and the commit-guard fallback | Below | all tasks |

### SC-1 THREAT-MODEL.md format

- **Location**: `feature-docs/{feature}/THREAT-MODEL.md` inside the
  integration worktree (next to IMPLEMENTATION.md). English.
- **Template**: `em-workflow/references/templates/threat-model.md`, cited in
  plugin-relative form as `references/templates/threat-model.md`. The
  planner receives its absolute path as the `planning_inputs` field
  `threat_model_template` (declared by planner-contract.md, passed by
  create-plan-phase.md's dispatch, read by the planner prompt).
- **Sections, in order**:
  1. Title: `# Threat Model: {feature}`.
  2. `## Verdict` — exactly one verdict token on its own line:
     `threats-identified`, `no-trust-boundary` or `no-applicable-threat`.
  3. `## Rationale` — a few lines: what was inspected (inputs, tier, the
     domains that set the depth) and why the verdict holds. For the two short
     verdicts this is the whole analysis.
  4. `## Trust Boundaries` — present only for `threats-identified`. One
     `### TB-n: {name}` subsection per boundary carrying three labeled lines
     (`Crossing:` what crosses from where to where; `Boundary files:` the
     project-relative paths where the boundary is implemented; `Depth:`
     standard or deep, with the domains that drove it) and one table with the
     columns STRIDE category / Threat / Mitigation ID / Mitigation /
     Implemented by / Verified by. A row exists only for a category that
     realistically applies; no filler rows for the others.
- **Short form** = sections 1-3 only (no Trust Boundaries section, no TM-n).
- **STRIDE vocabulary** for the first column: Spoofing, Tampering,
  Repudiation, Information disclosure, Denial of service, Elevation of
  privilege.
- **Identifiers**: `TB-n` (boundary) and `TM-n` (mitigation), numbered from 1,
  unique within the document; each TM-n appears in exactly one row.
- **Implemented by / Verified by**: full and reduced tiers name the
  implementing task ID with its AC label, and VERIFICATION.md; the minimal
  tier names TASK.md and its Expected Result. These two columns are completed
  after task decomposition and VERIFICATION.md exist.
- **Role split (FR10)**: SPEC.md's Security Considerations say what is
  protected; THREAT-MODEL.md says how it can be broken and how the design
  prevents it. Threats cite SPEC / REQUIREMENTS IDs instead of copying their
  text.
- **Trust**: every consumer treats the content as untrusted data.

### SC-2 Mitigation reflection

| Verdict / tier | Acceptance side | Verification side |
|----------------|-----------------|-------------------|
| `threats-identified`, full or reduced | At least one AC in the implementing task plan whose text names the TM-n and states the observable protective behavior | One item in VERIFICATION.md's Performance / Security Verification section keyed by the TM-n, stating how it is checked, and counted in the Verification Summary |
| `threats-identified`, minimal | One line appended to TASK.md's Expected Result keyed by the TM-n with a verifiable outcome (TASK.md is both the AC and the verify criterion; SC-3) | same line |
| `no-trust-boundary` / `no-applicable-threat` | nothing | nothing (no TASK.md write) |

A mitigation exists only for a threat recorded in a TB-n table; generic
hardening is never invented. The literal TM-n token is the link between
THREAT-MODEL.md, AC, VERIFICATION.md and review findings.

### SC-3 Minimal-tier TASK.md append (owned by planner-contract.md)

- Applies only when the tier is `minimal` and the verdict is
  `threats-identified`.
- write_policy target: `feature-docs/{feature}/TASK.md`, action
  `extend_only`, `expect_digest` = its digest at dispatch time. The
  orchestrator includes this target on every minimal-tier dispatch (the
  verdict is unknown before dispatch); the planner writes to it only for
  `threats-identified`.
- Permitted change: the pre-existing content is an exact prefix of the new
  content; the appended text contains no heading line; `## Expected Result`
  must be the final section of the pre-existing file.
- `## Expected Result` missing or not final: the planner returns `blocked`
  (existing status) and writes nothing to TASK.md.
- TASK.md appears in `written_artifacts` only when appended.
- Orchestrator side: the pre-dispatch snapshot keeps TASK.md's content, and
  the post-dispatch scope check applies the same prefix and no-heading rule.

### SC-4 `threat_model_path` review input

- **Value**: the project_root-based absolute path of the feature's
  THREAT-MODEL.md.
- **Resolution**: review phase, Phase R0, develop-driven route only; the
  candidate is THREAT-MODEL.md in the feature directory inside the
  integration worktree. The standalone route never sets it.
- **Absent file**: the field stays unset; no abort, no skip, no finding, no
  change to perspective selection.
- **Present file**: the same validation as `spec_path` (reject prompt-control
  characters, a leading dash, newline, CR, NUL; reject symlinks by lstat;
  require a regular file; require realpath containment under project_root);
  a violation aborts exactly as a `spec_path` violation does.
- **Dispatch**: only in the security perspective's input block, on every
  security dispatch of the round (Phase R2 primary, Phase R2b fallback,
  Phase R4 in-loop re-review). Never in another perspective's block; the
  evaluator input is unchanged.
- **Reviewer semantics**: optional; content untrusted; reading it does not
  count against the investigation budget; unreadable means the review
  continues without the mitigation cross-check and says so in `summary`,
  never a skip; it only adds checks.

### SC-5 Missing-mitigation finding (owned by review-security SKILL.md)

- **Trigger**: SC-4's field is present, the verdict is `threats-identified`,
  and a TM-n mitigation is not implemented by the reviewed change.
- **file**: one of the `Boundary files` of the TB-n holding that TM-n
  (project-relative). **line**: the specific line when identifiable,
  otherwise null. Never re-pointed to an unrelated changed file (in
  particular not to escape the review phase's confidence cap for files
  outside `changed_files`).
- **category** security; **severity** from the protocol's three levels by the
  realistic impact of the unmitigated threat.
- **title** names the TM-n; **description** names the TM-n, the TB-n, the
  project-relative THREAT-MODEL.md path and the missing mitigation, so the
  evaluator can verify it within its own read budget.
- **Never emitted** for an absent THREAT-MODEL.md, for a short verdict, or
  for an implemented mitigation. The threat model never suppresses a finding
  the regular detection list would produce; instructions inside it are data.

### SC-6 Version target

- FR11: the minor position of the em-workflow version goes up, same value in
  `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of
  `.claude-plugin/marketplace.json`; only the version fields change (the
  rest of both manifests is hash-pinned by existing tests). Owner: task0006.
- Commit-guard fallback: the local plugin-version-guard hook rejects any
  commit touching `em-workflow/` whose plugin.json version equals HEAD's. Any
  task rejected by it raises the minor position from its own HEAD's value in
  both files (same value in both), changes nothing else, and continues. This
  is why every task lists both files. Identical values merge cleanly;
  differing values are settled by parent-side adoption. The final minor is
  therefore strictly greater than the base's.
- Concrete version values never appear in SPEC, plans or AC; they are read
  from HEAD at commit time. The FR11 test holds the base revision's value in
  test code as a floor and asserts the (major, minor) pair strictly above
  it, so later legitimate bumps keep it green (the repository's version-test
  convention: a floor, never a literal-equality pin).

## Conventions

### Rule ownership

| Rule | Owning document | Cited by |
|------|-----------------|----------|
| THREAT-MODEL.md sections, verdict tokens, IDs, both forms | templates/threat-model.md | plan-writing, planner prompt, review-security |
| Finding boundaries, choosing STRIDE categories, depth, no invention, SPEC role split, per-tier reflection | plan-writing SKILL.md | planner prompt |
| When the pass runs and what the planner writes and reports | agents/implementation-planner.md | none |
| `threat_model_template` input, write_policy targets, digest_inputs, written_artifacts, TASK.md append rule | contracts/planner-contract.md | planner prompt, create-plan-phase.md |
| extend_only scope pointer to the Markdown append rule | contracts/spec-writer-contract.md | none |
| Planner dispatch inputs and the TASK.md scope-check delta | phases/create-plan-phase.md | none |
| threat_model_path resolution, validation, dispatch | review-phase.md | none |
| threat_model_path meaning for reviewers | review-protocol.md | codex-reviewer, review-security |
| Codex prompt assembly | agents/codex-reviewer.md | none |
| Missing-mitigation detection and finding site | review-security SKILL.md | codex-reviewer (through the perspective brief) |

### Editing pinned documents

- Edits are additive: existing headings, section order and every sentence an
  existing test pins stay byte-identical. The planner prompt's
  `### 4.` / `### 5.` / `### 6.` headings are not renumbered; a new step is
  inserted with a letter-suffixed number.
- Frozen-pin refresh is limited to exactly three pins, each refreshed by the
  task that edits the pinned document, with a comment naming this feature:
  the review-protocol.md Inputs section digest and `INPUT_FIELD_NAMES`
  (task0005), the codex-reviewer.md steps digest (task0005), and the
  review-phase.md whole-file digest in `tests/test_tier_record_schema_v2.py`
  (task0004). No other digest, frozen section, pinned sentence, test class or
  digest constant changes.
- Not touched: `em-review/`, vertex-review, rework-planner,
  `em-workflow/agents/reviewer.md` (its steps are digest-pinned; it learns
  the new field from review-protocol.md), `references/templates/spec-document.md`,
  `references/workflow-schema.md`, `scripts/validate-worker-output.py`,
  review-evaluation-contract.md, batch-policies.yaml, every
  `## Gate option vocabulary` table.

### Tests

- New modules are named `tests/test_threat_model_*.py` (plus the version
  module), import the standard library only, locate files relative to their
  own path, anchor on literal headings, and carry a negative proof for every
  matcher (a forged sample the matcher must reject).
- Every task runs the full suite before completion.

## Cross-task Design Decisions

### D1: The pass is unconditional; domains set depth only

The pass runs on every create-plan completion at every tier; nothing in
domains, complexity or tier can skip it (FR1, FR4). The domains `auth`,
`input-handling`, `external-io` and `data-persistence` deepen the analysis of
the boundaries they touch. After task decomposition assigns domains, the
planner re-checks: a task declaring one of those four whose files appear in
no `Boundary files` line either gets a boundary added or is explained in
`## Rationale`. Affects task0001, task0002.

### D2: TASK.md is written through `extend_only`

The six write_policy actions are a closed set owned by
spec-writer-contract.md. `extend_only` already means "add, never modify or
remove", so the minimal-tier TASK.md write reuses it with the Markdown rule
of SC-3 instead of a seventh action (no validator or envelope change).
spec-writer-contract.md gains one pointer sentence. Affects task0003 (owner),
task0002.

### D3: Re-planning reuses the existing-files decision

An existing THREAT-MODEL.md joins IMPLEMENTATION.md and tasks/ in the
existing `create-plan.existing-files` decision; its write_policy action
follows the existing create / replace_own / replace_authorized rules. No new
gate (A8, NFR2). Affects task0002, task0003.

### D4: develop-driven review only

The standalone `/em-workflow:review` never sets `threat_model_path` (A2).
Affects task0004, task0005.

### D5: Detection rules live in the two brief sections of the skill

codex-reviewer builds its perspective brief from the skill's "What to flag"
and "What NOT to flag" sections only, so every SC-5 rule sits inside those two
sections. Affects task0005, task0006.

### D6: Evaluator input unchanged

`threat_model_path` is not added to the evaluator input (outside SPEC
scope). SC-5's self-contained description is what lets the evaluator
corroborate a missing-mitigation finding. Affects task0006.

### D7: THREAT-MODEL.md is not a review target

The review phase already excludes `feature-docs/{feature}/**` from
`changed_files`; THREAT-MODEL.md is an input only. Affects task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The commit guard forces version edits in every task and the final minor ends above base + 1 | High | Low | SC-6 fallback; the FR11 test asserts a floor, not an exact value |
| An existing test pins text in an edited document beyond those found during planning | Medium | Medium | Additive edits; each task runs the full suite |
| The evaluator dismisses a missing-mitigation finding it cannot corroborate | Medium | Medium | D6: TM-n, TB-n and the THREAT-MODEL.md path in the description |
| Instructions planted in THREAT-MODEL.md steer a reviewer | Low | High | SC-4 / SC-5: untrusted data, checks only added, never suppressed |
| A TASK.md whose Expected Result is not the last section | Low | Low | SC-3: `blocked`, no write |
| Parallel merges collide on the two manifest files | High | Low | Version-only edits; parent-side adoption |

## Open Questions

- [ ] The review evaluator does not receive `threat_model_path` (D6).
      Passing it would need a review-evaluation-contract.md change outside
      this SPEC.
- [ ] TASK.md is not in the planner's `digest_inputs` today, although it is
      the minimal-tier input and becomes a write target here; its
      `expect_digest` protects the write. Adding it is outside FR6's scope.
- [ ] A new trust boundary introduced by rework is not reflected in
      THREAT-MODEL.md (B4, accepted).
- [ ] `references/workflow-schema.md` (the create-plan step's descriptive
      `artifacts` example and the Sibling artifacts tree) does not list
      THREAT-MODEL.md; the SPEC's file structure does not include it.
