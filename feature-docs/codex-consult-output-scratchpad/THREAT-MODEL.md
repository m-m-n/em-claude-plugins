# Threat Model: codex-consult-output-scratchpad

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR6, NFR1-NFR6) at the reduced tier (no
REQUIREMENTS.md, no DESIGN.md); step 2 ("Wrapper invocation") of the Codex
consultation procedure in `em-workflow/references/question-resolution.md`;
step 3 ("Codex 事前調査") of the develop skill's tier section in
`em-workflow/skills/develop/SKILL.md`. The change edits only documents and
structural tests, but those documents are the procedure the orchestrator
executes, and they govern where it writes the output of an external process
(the `run_codex_exec.sh` wrapper around the Codex CLI). That write is one
trust boundary (TB-1). task0001 declares `external-io`, which sets the
boundary's depth to deep.

The content of Codex's reply is already handled as untrusted data by the
consultation procedure's existing untrusted-output rule. This feature leaves
that rule unchanged, so this document does not analyse it again. The two
test modules task0001 touches (`tests/test_question_resolution_doc.py`,
`tests/test_develop_tier_staged_procedure.py`) only read repository
documents and cross no boundary, so they are not boundary files.

## Trust Boundaries

### TB-1: Codex wrapper output to an orchestrator-saved file
Crossing: stdout and stderr of a `run_codex_exec.sh` call made by another
process (the Codex CLI, on the `codex` or the `litellm` entry). This covers
the reply text plus the CLI's own diagnostics, such as session details and
local absolute paths. The crossing happens when the orchestrator saves that
output to a file on the local file system, a location that can be inside the
target project's git working tree.
Boundary files: em-workflow/references/question-resolution.md, em-workflow/skills/develop/SKILL.md
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Information disclosure | A saved output file redirected to a path relative to the current directory lands under the project root as an untracked file. A later commit or push then carries the consultation content and the CLI diagnostics (including local absolute paths) into the repository history (relates to FR1, FR2). | TM-1 | When saved, wrapper output (stdout and stderr) goes only into the session scratchpad directory, never under `{project_root}`, and never through a redirect target relative to the current directory. The rule is defined once, in step 2 of the Codex consultation procedure. The develop tier pre-survey cites it without restating it. Region-scoped doc tests with negative twins pin both documents. | task0001 AC-1, AC-2, AC-4 | VERIFICATION.md, Performance / Security Verification, item TM-1 |
