# Implementation Plan: resume-steps-actor-labels

## Overview
Add an actor-label rule (AI-doable vs. needs a human decision, AI first, a
reason for each human step) to the `resume_conditions` bullet of the
structured-result contract, make the develop skill's stop report cite it,
and pin both with a new unittest module. The feature is one task
(task0001); per-task detail lives in `tasks/task0001.md`.

## Technology Stack
- **Language / Framework**: Markdown (regulation documents), Python 3
  standard library `unittest` (pinning tests).
- **New dependencies**: none. `project.license` is `none`; no license to
  record.

## Layer Structure
- **Owner document**: `em-workflow/references/batch-terminal-line.md` owns
  the label rule, inside the existing `resume_conditions` bullet of
  `## Field values` (FR4).
- **Citing document**: `em-workflow/skills/develop/SKILL.md`'s stop-report
  section cites the owner document and does not restate the rule.
- **Pinning tests**: `tests/` modules read both documents as raw text.
  Dependency direction: tests depend on the documents; the citing document
  depends on the owner document; the owner document depends on neither.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Actor-label vocabulary | The fixed strings a recovery step starts with | Post: exactly two labels exist, 「AI がやれる」 and 「人の判断が要る（理由: X）」, X being exactly one of 「物理的に人しかできない」, 「戻せない変更の承認」, 「価値判断」. The strings are Japanese whatever the language of the step text (SPEC.md a6). Owned by `batch-terminal-line.md` only | task0001 (and any later rework task) |

## Conventions
- **Single owner**: the label rule text lives only in
  `batch-terminal-line.md`. Other documents cite it by path and restate
  neither the label strings nor the reason words.
- **Test authoring**: follow the repository's documentation-contract test
  form — standard library only, raw file text, constants re-declared
  locally (no import from another test module), and for every new matcher
  a negative proof built from the real pre-change wording plus a
  non-vacuity guard. A pure regression guard over retained wording is
  exempt from a negative proof.
- **Existing pins**: no existing test module changes except the
  `RESULT_FORMAT_TEXT` constant of `tests/test_batch_stop_contract.py`
  (NFR2).
- **Version**: this repository bumps plugin versions through its own
  automation; no task changes a version field (NFR4).

## Cross-task Design Decisions

### D1: No mechanical label validation
The rule is a content rule only. No emitter-side or consumer-side
rejection rule for labels is added, and the value-format rules
(presence, no normalization, `## Escaping`, CR/LF/TAB handling, consumer
constraints) stay as they are (NFR1, SPEC.md a1). A later task that wants
label validation needs a SPEC change first.

### D2: Scene-specific resume paragraphs keep their wording
The per-scene resume-condition paragraphs elsewhere (write rejection in
`batch-terminal-line.md`, the abort paragraphs in `implement-phase.md` and
`review-phase.md`) are not edited; labelling at output time follows the
general rule (SPEC.md a4).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New text breaks an existing pin on either document (bullet regex, forbidden literals, section slices, byte-identical sections) | Medium | Medium | task0001's plan lists the pins the new text must respect; the full suite runs as TS-5 |
| A label literal is hard-wrapped inside a Japanese run, so a whitespace-normalizing matcher no longer finds it | Medium | Low | Keep each fixed string on one physical line (task0001 Design) |
| A step that needs human authority is labelled AI-doable (THREAT-MODEL.md TM-1, TM-2) | Low | High | The three reasons and the ordering / fold-in rule are stated in the owner document and pinned by test |

## Open Questions
- [ ] None
