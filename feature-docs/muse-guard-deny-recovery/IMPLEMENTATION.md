# Implementation Plan: muse-guard-deny-recovery

## Overview

Define one recovery route for a muse_guard deny of the contributor tier: a new
retryable `skip_reason`, `contributor_consent_missing`, added to the Skip
Semantics and the Phase R2b routing table of both plugins, and the two
`muse_guard.py` copies' DENY_CONTEXT rewritten to point at that route.

## Technology Stack

- **Language**: Python 3 (standard library only) for the hook copies and the
  `unittest` suite under `tests/`.
- **Documents**: Markdown protocol and phase references of em-workflow and
  em-review, and the em-workflow README.
- **New dependencies**: none.

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Hook (agent-facing) | the two `hooks/muse_guard.py` copies | On a deny, tell the denied agent what to do next (DENY_CONTEXT). Decision behavior is untouched. |
| Reviewer protocol | the two `references/review-protocol.md` | Skip Semantics: the reviewer returns the skip object and ends. |
| Orchestrator phase | the two `references/review-phase.md` | Phase R2b: the orchestrator routes the skip object to the next chain entry. |
| User docs | `em-workflow/README.md` | Summarizes the R2b hop rule. |
| Pins | `tests/` | Pin each document's text and the hook's output. |

Dependency direction: the hook text and the R2b table both refer to the
`skip_reason` value the reviewer protocol defines; the protocol refers to no
hook text. The README summarizes Phase R2b and is not read by any agent.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `skip_reason` value | Names the contributor-tier deny in every document and in DENY_CONTEXT | The literal string is exactly `contributor_consent_missing` (snake_case, no variant spelling) in every file that names it | task0001, task0002, task0003, task0004 |
| Skip object | The reviewer's whole result after the deny | Exactly the one-line JSON object of SPEC.md FR1: `findings` empty, `summary` is `skipped: contributor consent missing`, `skipped` true, `skip_reason` is the value above, `source` is `<source>` (the reviewer's own harness). Identical in both review-protocol.md files. | task0002 (defines); task0001, task0003, task0004 (refer to it by its `skip_reason`) |
| Role split after the deny | Who chooses what happens next | The reviewer returns the skip object and ends. It does not retry the same entry as plain `muse-spark`, does not record or re-judge consent, and does not pick another model or chain entry. Only the orchestrator selects the next entry, through Phase R2b. | task0001, task0002, task0003, task0004 |
| R2b routing row | The table row both review-phase.md files add | The row text is exactly: pipe, the value in backticks, pipe, `muse_guard denied the contributor tier because the repository has no recorded consent`, pipe, `the next entry in the chain`, pipe; cells separated by single spaces exactly like the existing `rate_limited` row. It is the last row of the table. Existing rows stay byte-identical. | task0003, task0004 |
| R2b note on the new row | The prose both review-phase.md files add in Phase R2b | States, in the R2b section: (1) consent is a property of the contributor tier, not of the harness, so the walk may advance within the same harness; (2) the walk resumes from the entry after the recorded chain index and never re-dispatches the same entry as plain `muse-spark`; (3) Phase R0's `contributor_consented` is not re-judged and the chain is not edited. The hop counts against the existing "At most 2 fallback dispatches per perspective" budget. | task0003, task0004 |
| Retryable count words | The retryable-set statements of the two protocols | em-workflow: `five`; em-review: `four`. The exact statement sentences are SPEC.md FR1 / FR2. | task0002 |

## Conventions

- **Copies stay twins**: the two `muse_guard.py` files differ in exactly one
  line, `PLUGIN_SLUG`. Every edit is applied identically to both.
- **No version change**: no task edits a `plugin.json` or
  `.claude-plugin/marketplace.json`.
- **Forbidden words**: no file under `em-review/` contains `shard` or
  `dispatch cap` (any case, hyphen or space); `em-workflow/references/review-protocol.md`
  contains none of the framing phrases listed in
  `tests/test_reviewer_roles_protocol.py` (`FORBIDDEN_FRAMING_PHRASES`).
- **Contributor-tier wording**: the review-phase.md edits add none of the
  phrases listed in `tests/test_contributor_tier_criteria.py`
  (`REMOVED_CONDITION_PHRASES`, `FORBIDDEN_RECORDED_VALUE_COMPARISONS`).
- **Question budget**: no document under either plugin's `references/` or
  `skills/` gains an occurrence of the interactive-question tool name
  (`tests/test_muse_consent_no_new_questions.py`); no gate identifier is
  added.
- **Pinned phrases stay verbatim**: every phrase an existing test pins in a
  touched section is left byte-identical (SPEC.md NFR4 lists the R2b ones).
- **Test ownership**: a task updates only the test modules listed in its own
  plan. Where a module already pairs a matcher with forged-text rejection,
  every new pin gets a forged text that the matcher rejects.
- **Language**: the reference documents stay English; DENY_CONTEXT stays
  Japanese, one line, a module-level constant.

## Cross-task Design Decisions

### D1: The recovery route is a retryable `skip_reason`

The deny maps to `contributor_consent_missing`, retryable, advancing to the
next entry in the chain (SPEC.md A-1). Affected: all tasks.

### D2: DENY_CONTEXT branches on the agent's role

Reviewer: return the skip object and end. Any other agent: continue without
the contributor tier and without looking for a workaround (SPEC.md A-3).
Affected: task0001 (the text) and task0002 (the reviewer branch points at the
skip object the protocol defines).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A test module outside the plan pins a count or table that changes | Low | Suite red at verify | Each task runs the full suite before merging; the known pins are listed in the task plans |
| The two hook copies drift by more than the slug line | Medium | `TestBothCopiesShape` fails | One task owns both copies and applies one edit to both |
| New prose in em-review introduces a forbidden word | Low | Suite red | Conventions above; existing scan test |
| The R2b row texts of the two plugins diverge | Low | Inconsistent routing description | Row text pinned in Shared Components |

## Open Questions

- [ ] em-review's README hop paragraph also enumerates retryable values; SPEC.md
  scopes the README change to em-workflow only, so it is not changed here.
- [ ] Reviewer agent definitions (em-workflow's codex reviewer and the
  separately installed vertex reviewer) do not list the new value; reviewers
  learn it from review-protocol.md and DENY_CONTEXT. SPEC.md scope does not
  include them.
