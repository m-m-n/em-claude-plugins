# Threat Model: build-format-both-excluded-tests

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR3, NFR1-NFR5), the two procedure documents the
feature edits (implementer.md Step 3 and the worktree-task-workflow skill's
Command execution gate section), and the existing document test for the
build / format statements. Tier: reduced. task0001 declares `api-contract`
and `config-infra`; none of the four depth-adjusting domains applies, so the
single boundary is analysed at standard depth. The feature adds one sentence
to each document and a new document test; it introduces no new execution
path, no parsing of external input and no dependency. The new test reads only
repository files inside the project, which is no trust boundary. The one
boundary that matters is the existing one where approved `project_commands`
strings reach the implementer and the implementer's `tests` value reaches
the orchestrator: the feature changes the documented rule for that value, and
a realistic integrity threat exists there (TB-1).

## Trust Boundaries

### TB-1: Approved project_commands strings to the implementer report
Crossing: repository-controlled `project_commands` strings from workflow.yaml
(user-approved, treated as untrusted data) enter the implementer's command
handling; the implementer's report, including its `tests` value, goes back to
the orchestrator, which relies on it.
Boundary files: em-workflow/agents/implementer.md, em-workflow/skills/worktree-task-workflow/SKILL.md
Depth: standard

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | When the build string and the format string both fall outside the cd prefix form and the test command passes, the current statements leave no single value for `tests`; an implementer resolving the conflict toward the format statement reports `tests: "pass"` although the build never ran, so the report the orchestrator relies on misstates verification (FR1, FR2). | TM-1 | Both documents state, in one sentence separate from the existing format sentence, that not running the format command does not override a `tests: "fail"` that another rule decides, citing the case where the build command also falls outside the cd prefix form; a document test pins exactly one such sentence per section. | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification: TM-1 |
