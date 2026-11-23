# Threat Model: resume-steps-actor-labels

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (reduced tier; no REQUIREMENTS.md, design step skipped),
the two regulation documents the feature edits
(`em-workflow/references/batch-terminal-line.md`, the stop-report section of
`em-workflow/skills/develop/SKILL.md`) and the pinning test modules the
feature adds or updates. The only task, task0001, declares `api-contract`;
it declares none of `auth`, `input-handling`, `external-io` or
`data-persistence`, so the one boundary below is analysed at standard depth
and no boundary-file consistency gap exists.

The feature changes no code path and no value format (NFR1). Its effect is
on what downstream readers of the stop-recovery guidance — triage, a later
automated run, a human reviewer — are told about who may perform each step.
Because the label is what lets a downstream automated run decide to act on
a step without a human, a wrong or misplaced label can hand that run an
action that needs human authority. That is the boundary recorded below.

Considered and not recorded:
- Information disclosure: the labels and the three reasons are fixed
  vocabulary; they add no content to the value beyond what the existing
  confidentiality rule of `batch-terminal-line.md`'s
  `## Responsibility boundary` already governs.
- A forged label line injected through newlines inside carried text: the
  guidance is composed by the orchestrator, and this feature adds no new
  carriage of external text into the value; no mechanical label check is
  added (SPEC.md assumption a1, NFR1).
- The new test module reads repository files only and crosses no boundary.

## Trust Boundaries

### TB-1: Stop-recovery guidance to downstream executors
Crossing: the recovery steps carried in `resume_conditions` and in the stop
report (batch and interactive) leave em-workflow's turn and are read by a
downstream party — triage, a later automated run, or a human — that uses
each step's actor label to decide whether the step may be performed without
a human. Control over whether a step runs autonomously crosses from
em-workflow's guidance text to that downstream executor.
Boundary files: em-workflow/references/batch-terminal-line.md, em-workflow/skills/develop/SKILL.md
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A step that needs approval of a change that cannot be undone is labelled as AI-doable, so a downstream automated run performs it without the human approval it needs (FR1, FR3) | TM-1 | The `resume_conditions` rule names approval of a change that cannot be undone (「戻せない変更の承認」) as one of exactly three fixed reasons that make a step a human step, and the label and reason vocabulary is pinned by test | task0001 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 item (TS-1) |
| Elevation of privilege | AI work that may only run after a human decision is listed as its own AI-labelled step; because AI steps are acted on first, a downstream automated run performs it before, or without, the decision (FR2) | TM-2 | The rule forbids any AI step after a human step and requires AI work that depends on a human decision to be written inside that human step as 「判断の後、AI が ... を実行する」; the rule and the labelled Result format example are pinned by test | task0001 AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 item (TS-2, TS-4) |
