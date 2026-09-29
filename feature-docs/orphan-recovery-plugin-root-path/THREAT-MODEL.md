# Threat Model: orphan-recovery-plugin-root-path

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md (FR1-FR7, NFR1-NFR4, A1-A5), the workflow goal, and the
text this feature rewrites — the three places in
`em-workflow/references/implement-phase.md` I.2.b step 1 where the
orchestrator itself launches a plugin-bundled helper, plus the Step I.0
step 4 resolution rule those places are to cite. Tier: reduced. The single
task (task0001) declares `config-infra` and `external-io`; `external-io`
sets TB-1's depth to deep.

The feature changes which file the orchestrator executes: a path relative
to the working directory (the user's project, whose content is
repository-controlled) is replaced by a path under the installed plugin
root. That is a trust boundary between repository content and the
installed plugin, and two STRIDE categories realistically apply to it
(TB-1).

Considered and not recorded as a boundary: the working-directory fix for
`recover-orphaned-task.py` (FR5, A1) only selects which directory under the
user's own home the script reads session transcripts from. That directory
is not repository-controlled, and a mismatch ends the script in a residual
outcome without touching the journal. The trust assumptions of Step I.0
step 4's own fallback search are pre-existing; this feature cites that
rule and does not change it.

## Trust Boundaries

### TB-1: Helper script selection by the orchestrator
Crossing: the orchestrator selects an executable file by path and runs it
with its own authority, including the authority to append to
`journal.jsonl`. The candidate locations differ in trust: the project
working directory holds repository-controlled content; the plugin install
root (`${CLAUDE_PLUGIN_ROOT}`, or Step I.0 step 4's trusted fallback roots)
holds the installed plugin.
Boundary files: `em-workflow/references/implement-phase.md`
Depth: deep (external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A file planted at the cwd-relative helper path inside a repository is executed by the orchestrator at the three I.2.b invocation sites (FR1, FR2, FR3), so repository-controlled content runs as code with orchestrator authority | TM-1 | All three sites resolve the helper under `${CLAUDE_PLUGIN_ROOT}` by citing Step I.0 step 4 (trusted roots only, never the working directory), and no cwd-relative invocation form remains in the document; an absence test enforces this (FR6, NFR1) | task0001 AC-1, AC-2, AC-3, AC-5 | VERIFICATION.md Performance / Security Verification item TM-1 (TS-1, TS-2) |
| Tampering | When the helper cannot be resolved, the orchestrator improvises a substitute location (for example the old cwd-relative path) and that substitute appends to `journal.jsonl`, altering the task-state record (FR4) | TM-2 | A resolution failure invokes nothing: both recovery invocations leave the candidate in the Residual outcome, and the merge-unverified invocation leaves the task under the Helper-failure residue; the journal is unchanged in both cases (FR4) | task0001 AC-4 | VERIFICATION.md Performance / Security Verification item TM-2 (TS-4) |
