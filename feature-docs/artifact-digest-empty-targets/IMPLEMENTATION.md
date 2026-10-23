# Implementation Plan: artifact-digest-empty-targets

## Overview
Adds a zero-count rule to each of the two digest checks owned by `em-workflow/references/artifact-digest.md` (Pre-dispatch verification and Layer 5 recording), and pins both rules with documentation tests. A single task (task0001) carries the whole change.

## Technology Stack
- **Markdown**: the owning procedure document (`em-workflow/references/artifact-digest.md`, written in English)
- **Python 3 standard library unittest**: the documentation tests (NFR3)
- **New dependencies**: none. `project.license` is `none`, and there is no license to record.

## Layer Structure
| Layer | Members | Responsibility | Change in this feature |
|---|---|---|---|
| Owner | `em-workflow/references/artifact-digest.md` | The only document that states the digest procedure, now including both zero-count rules | Modified |
| Citing sites | create-spec, design, create-plan and rework dispatch sections, and the develop skill's design-step branch | Cite the owner by section name; never restate its procedure | Unchanged (NFR2) |
| Mechanism | `em-workflow/scripts/artifact-digest.py` | The Calculation command that the owner's procedure runs | Unchanged (FR3) |
| Verification | `tests/test_artifact_digest_docs.py`, the dispatch_digest_wiring check of `em-workflow/scripts/check-plugin-invariants.py` | Pin the owner's text and the wiring between the citing sites and the owner | Test file extended; invariant script unchanged |

Allowed dependency direction: citing sites -> owner -> mechanism. Verification reads the owner and the citing sites only.

## Shared Components
No component is built by one task and consumed by another, because this is a single-task feature. The table records the contracts that the owner keeps toward the unchanged citing sites and the unchanged mechanism. Any later rework task must keep the same contracts.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Owner, Pre-dispatch verification section | The orchestrator's `expect_digest` check before a dispatch | Pre: the dispatch's `write_policy.targets` are decided. Post: when zero targets require an `expect_digest`, Calculation is not run and the verification succeeds. An empty targets list and a list whose targets are all `create` both count as zero. When one or more targets require one, the existing procedure and every existing mismatch condition apply unchanged. | task0001 (sole editor); every dispatch site cites it unchanged |
| Owner, Layer 5 recording section | The orchestrator's digest recording for a `completed` result | Pre: the result has passed layer 4. Post: when `written_artifacts` has zero entries, Calculation is not run and nothing is recorded. Whether an empty `completed` result is acceptable is left to the rules of the layer that handles that result. When there are one or more entries, there is one Calculation call over every path, and the existing artifact-validation failure conditions apply unchanged. | task0001 (sole editor); every dispatch site cites it unchanged |
| Mechanism, Calculation command | Computes sha256 digests of the paths it is given | A call with no argument exits with code 2 and prints no array on standard output, unchanged. The owner's procedure never reaches a no-argument call. | task0001 (referenced, not modified) |

## Conventions
- **Ownership**: zero-count handling is written only in the owner. No citing site gains a restatement, a paraphrase or a summary of it (NFR2).
- **Requirement terminology**: "targets that require an `expect_digest`" refers to the requirement owned by the write-policy model (`em-workflow/references/contracts/spec-writer-contract.md`). The owner cites that requirement and does not redefine which actions carry it.
- **Documentation test style** (NFR3): cut a section out by its heading, normalize whitespace, and assert that tokens or phrases are present. Do not rely on whole-document equality or line positions. Pair every assertion of absence with a case showing that the matcher fires on crafted text that contains the phrase.

## Cross-task Design Decisions

### D1: One task for the document change and its tests
The new tests fail until the owner's text exists, and tasks run fully in parallel. A separate test-only task would stay red in its own worktree. The document edit and its tests therefore form one TDD unit. Affected: task0001.

### D2: The procedure avoids the no-argument call; the script keeps exit code 2
The fix lives in the owner's procedure: each zero-count rule is decided before the procedure reaches its Calculation step. The script is not changed to accept a no-argument call. A no-argument call keeps its existing meaning (exit code 2, which the procedure treats as a mismatch or failure) for any caller that still reaches it (FR3). Affected: task0001 and any later rework task touching the owner.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The zero-target rule is keyed on non-null `expect_digest` values instead of on the requirement, so a target that requires an `expect_digest` is dispatched unverified (THREAT-MODEL.md TM-1) | Low | High | Shared Components contract above; task0001 AC-1; VERIFICATION.md TM-1 |
| The Layer 5 zero-artifact rule is read as accepting an empty `completed` result (THREAT-MODEL.md TM-2) | Low | Medium | The delegation statement is required by task0001 AC-2; VERIFICATION.md TM-2 |
| Added text rewords a phrase that existing tests pin, or changes the heading set (NFR1) | Medium | Medium | Add text only; add no heading; existing test methods stay unchanged and must pass |
| The new documentation tests are brittle against wording or line wrapping | Medium | Low | Heading slicing, whitespace normalization and token presence (Conventions) |
| A restatement leaks into a citing site (NFR2) | Low | Medium | Citing sites are outside every task's files; TestEverySiteCitesTheOwner and dispatch_digest_wiring must pass |

## Open Questions
None.
