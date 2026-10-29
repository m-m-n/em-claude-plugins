# Threat Model: cd-prefix-excluded-build-format-tests

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR5, NFR1-NFR5; its Security Considerations names
nothing to protect), at the reduced tier (no REQUIREMENTS.md; the design step
was skipped). The change adds sentences to two implementer instruction
sections and adds one document-test module. It changes no hook, no approval
rule and no script. Task decomposition produced one task, task0001, which
declares `api-contract` and `input-handling`. `input-handling` sets TB-1 to
deep depth: the edited sections tell the implementer what to do with an
approved command string that the hook's exclusion conditions reject. The hook
makes the exclusion decision and is not changed here. No task declares
`auth`, `external-io` or `data-persistence`.

One trust boundary is touched. The two edited sections set the implementer's
policy for command strings that come from the repository. Tampering applies
at this boundary, because the new build rule (FR1, `tests: "fail"`) gives the
implementer a reason to want a build result.

Crossings considered with no applicable threat:
- The implementer's report `notes` reaches the orchestrator. FR3 asks `notes`
  to name the kind of command (build or format) and the reason it was not
  run. It does not ask `notes` to carry the command string, so this feature
  adds no new untrusted text to that crossing.
- The new document-test module reads two repository documents and runs
  nothing.

## Trust Boundaries

### TB-1: approved project command strings to implementer command execution
Crossing: build and format command strings start in workflow.yaml, which is
repository-controlled data. They reach the implementer in the `Untrusted data`
section of its launch prompt. The implementer's instruction sections decide
whether and how the implementer runs them in its Bash calls.
Boundary files: em-workflow/agents/implementer.md, em-workflow/skills/worktree-task-workflow/SKILL.md
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | An approved build or format string that the cd prefix form does not cover gets run in another form: without the prefix from the session's default working directory, or rewritten, or split. The new report rule (FR1: `tests: "fail"` for the build case) gives the implementer a reason to try for a result. The hook still allows the exact approved string with no prefix, so a build or format run outside the worktree changes files in the main working tree (FR1, FR2, FR4) | TM-1 | Each new build or format sentence states that the command is not run. The existing handling sentence (not run with the cd prefix, not run without it, not rewritten or split) stays unchanged, exactly once in each of the two sections | task0001 AC-1, AC-2, AC-3 | VERIFICATION.md, Performance / Security Verification, TM-1 |
