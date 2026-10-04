# Implementation Plan: codex-fallback-review-residuals

## Overview

Closes the three round-2 medium findings that are still open (21fcec3b529ebbd1, ad385249e099e34b, f16ba900e23a5497) through document and test changes: the README batch clause (FR1), a dedicated Opus escalation agent with its own contract, wired into `references/question-resolution.md` (FR2-FR4), and the batch audit `source` mapping for escalation-decided non-packet gates (FR5). Adds the `--litellm MODEL` passthrough regression test (FR7). No script changes.

## Technology Stack

- **Documents**: Markdown under `em-workflow/`. README in Japanese; `references/` and `agents/` bodies in English; agent frontmatter `description` in Japanese, matching the existing files.
- **Tests**: Python 3 standard-library `unittest`, discovered by `python3 -m unittest discover -s tests` (NFR5).
- **Invariant checker**: `em-workflow/scripts/check-plugin-invariants.py`, unchanged; its `agent_dispatch_parity` and `forbidden_task_assignment_heading` checks apply to the new agent (NFR7).
- **New dependencies**: none. `project.license` is `none`, and no license needs recording.

## Layer Structure

| Layer | Members | Responsibility | May cite |
|---|---|---|---|
| User-facing docs | `em-workflow/README.md` | Describes behaviour for users; owns no rule | Protocol SSOT |
| Protocol SSOT | `em-workflow/references/*.md` | Owns each rule exactly once | Other protocol documents (cite, never restate) |
| Agent definitions | `em-workflow/agents/*.md` | Role, model binding in frontmatter, pointer to its contract | Its own contract for every shape |
| Tests | `tests/*.py` | Pin document text and wrapper behaviour | Read documents and scripts; never read by them |

Allowed directions: README to references; an agent definition to its contract; tests to everything, read-only. No reference document cites README or a test.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Opus escalation agent identity | The single name the dedicated escalation agent goes by | Name: `opus-escalation` (matches `[A-Za-z0-9_-]+`). Postcondition: the file stem of `em-workflow/agents/opus-escalation.md`, its frontmatter `name`, the `em-workflow:` suffix of the dispatch literal in `references/question-resolution.md`'s `### Opus escalation` section, and the first cell of the README agent-table row are this same string. | task0001, task0002 |
| Non-packet escalation `source` ownership | Which document states the audit `source` for a non-packet gate the escalation decided | Owner: `em-workflow/references/phase-state.md`'s `## Batch audit record file` section, general mapping. Values: `batch-codex-consultation` under the route-naming reading, `batch-safe-default` when the minimum-side-effect option was taken, both from the existing closed vocabulary (NFR1). Postcondition: `references/question-resolution.md` and the escalation contract cite phase-state.md for this and write no `source` literal for the non-packet case. | task0001, task0003 |
| Non-packet gate identifying names | The `question_id` a gate with no `gate_id` goes by | Existing and unchanged, owned by the same phase-state.md section: `review.diff-size-gate` and `command-execution.per-command-approval-fallback`. Postcondition: the escalation contract's non-packet presentation uses this name as the presented question's `question_id` (citing phase-state.md), and phase-state.md's new worked example uses one of the two. | task0001, task0003 |

## Conventions

- **Cite, never restate (NFR4)**: a document that needs another document's rule names it by path (and section) and does not copy its content. README defers conditions to `references/question-resolution.md`; question-resolution.md defers the escalation's input and return shape to the contract; the agent definition defers every shape to the contract.
- **Pinned-phrase retention (NFR3)**: every existing pin on an edited document is a constraint. Known pin holders: question-resolution.md, `tests/test_question_resolution_doc.py`, `tests/test_consultation_harness_chain.py`, `tests/test_batch_quiet_output_audit_record_contract.py`; phase-state.md, `tests/test_batch_quiet_output_audit_record_contract.py`, `tests/test_batch_quiet_output_audit_persistence.py`, `tests/test_wrapper_fallback_doc_realignment.py`, `tests/test_phase_state_doc.py`; README, `tests/test_llm_led_review_user_docs.py` and other README readers. The only pinned sentence allowed to move is the Opus escalation return-shape sentence (NFR3's exception), and its pin moves with it.
- **Vocabulary guards already enforced**: phase-state.md carries no provider/model token and no usage-limit phrasing (case-insensitive substring guard over the whole file); question-resolution.md carries no rate-limit phrasing and no new `gate_id` literal assignment; no document mints a `source` value.
- **Dispatch-literal discipline**: check-plugin-invariants scans the raw text of every `.md`, `.py`, `.yaml` and `.yml` file under `em-workflow/`, `feature-docs/`, `test-docs/` and `tests/` for the dispatch-reference form. A test fixture, test record or planning document must never contain that form naming an agent that does not exist (a dangling dispatch fails the invariant). The dispatch literal for `opus-escalation` belongs in question-resolution.md's section, and tests that pin it extract it from that section.
- **Test authoring**: standard library only; no import from another test module; constants re-declared locally; every new negative (absence) assertion carries a negative proof over a forged sample plus a non-vacuity guard, following the existing modules; prose matched after whitespace normalisation so Markdown re-wrapping does not break a pin.

## Cross-task Design Decisions

### D1: Agent name `opus-escalation` (SPEC A6, open item 14.3)

The dedicated agent is named `opus-escalation`. It is the section's own term ("Opus escalation"), so the section heading, the file stem, the frontmatter `name` and the dispatch suffix read as one identifier, and it satisfies the capture pattern `agent_dispatch_parity` compares against file stems. Affects task0001 (creates the agent and its dispatch site) and task0002 (README row).

### D2: Agent definition, contract and dispatch site in one task

The agent file, its contract and the `### Opus escalation` section edits form one task. check-plugin-invariants, run by the full suite through `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant`, fails both when an agent exists with no dispatch reference and when a dispatch reference names a missing agent. Split across parallel worktrees, neither half could pass its own suite. The README row lives with the README task because its assertions read README text alone. Affects task0001 and task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A rewrite of a heavily pinned section silently breaks an existing pin | Medium | Medium | Pinned-phrase retention convention; full suite before merge |
| A fixture or test record contains a dangling dispatch reference | Low | High (invariant fails, suite red) | Dispatch-literal discipline convention |
| The README row lands after the paragraph that interrupts the agent table and renders outside it | Medium | Low | task0002 places the row directly after the review-evaluator row; manual rendering check in VERIFICATION.md |
| Moving the return-shape sentence weakens coverage | Low | Medium | The pin is updated in the same task to assert the section-to-contract citation and the contract's content |

## Open Questions

- [ ] The README heading "エージェント 11 枚" already disagrees with its table (12 rows) and reaches 13 with the new row. Not in SPEC scope; left unchanged.
- [ ] README's agent table is interrupted by the `vertex-review:vertex-reviewer` paragraph, so the gitignore-guard and git-setup-guard rows render outside the table. Pre-existing; not in SPEC scope.
- [ ] SPEC FR7 says no test covers `--litellm MODEL` passthrough, but `tests/test_consultation_harness_chain.py::test_model_value_passes_through_verbatim` already checks the `-m` value for a non-default model. FR7's consecutive-element check in `tests/test_codex_wrapper_single_invocation.py` is still added as specified.
