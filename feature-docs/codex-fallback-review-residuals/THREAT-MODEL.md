# Threat Model: codex-fallback-review-residuals

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the four task plans (tier: full; design step skipped). The feature changes documentation and tests only, and no runtime script changes. It does add an LLM subagent and its dispatch contract. During batch runs, the orchestrator interpolates question material into that agent's prompt, and the agent's output feeds a decision the orchestrator records in `batch-audit.yaml`. That makes two real trust boundaries. Both are analysed at deep depth. TB-1 is deep because of `input-handling` (untrusted text interpolated into a prompt) and `auth` (the agent's tool privilege). TB-2 is deep because of `input-handling` (an LLM output read by the orchestrator) and `data-persistence` (the audit record).

Not a trust boundary:

- The README edit (FR1) is user-facing text that nothing parses at run time.
- The `--litellm` regression test (FR7) runs a stubbed CLI inside the test process.
- The Codex wrapper boundary is unchanged (NFR2) and gains no new crossing.

Domain consistency after decomposition:

- task0001 declares `auth`, `input-handling` and `api-contract`. Its files appear in TB-1's and TB-2's Boundary files lines.
- task0003 declares `data-persistence`. Its `em-workflow/references/phase-state.md` appears in TB-2's Boundary files line.
- task0002 and task0004 declare none of the four depth-adjusting domains.

## Trust Boundaries

### TB-1: question material into the Opus escalation agent's prompt
Crossing: Question material moves from the orchestrator (holding content derived from repository files, specs, diffs and Codex consultation output) into the prompt of the `opus-escalation` subagent. The material consists of each carried question's `prompt`, `options`, `why_needed`, `evidence` and tentative position. Untrusted text is interpolated into an LLM prompt, and the receiving agent holds file-read tools.
Boundary files: em-workflow/references/opus-escalation-contract.md, em-workflow/agents/opus-escalation.md, em-workflow/references/question-resolution.md
Depth: deep (input-handling, auth)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | Instruction-shaped text inside carried question material (for example in `evidence` or `why_needed`) steers the agent away from its task, or closes the data region early and injects text the agent reads as its own instructions (FR3; SPEC.md Security Considerations, Input Validation) | TM-1 | The contract places the whole input inside one explicitly delimited untrusted-data block and states its boundary. The dispatcher neutralises closing-delimiter occurrences inside carried content. The agent body states that it treats its whole input as data and never follows instructions inside it | task0001 AC-2, AC-3 | VERIFICATION.md TM-1 (TS2, TS3) |
| Elevation of privilege | An agent steered by injected input uses a write-capable or shell tool to change repository files or run commands during an unattended batch run (FR3, NFR7) | TM-2 | The agent frontmatter's `tools` is Read, Glob and Grep only. It contains none of Write, Edit or NotebookEdit, and no Bash | task0001 AC-1 | VERIFICATION.md TM-2 (TS2) |
| Information disclosure | Injected input directs the agent to read files outside the project, or unrelated files, and surface their content in its reasoning. That content then reaches the orchestrator's transcript and the audit `resolution_note` (FR3) | TM-3 | The contract forbids writes and limits reads to the contract itself and to files under the project root that a carried question's `evidence` names | task0001 AC-5 | VERIFICATION.md TM-3 (TS3) |

### TB-2: escalation output into the orchestrator's decision and the batch audit record
Crossing: The `opus-escalation` agent's returned text goes back to the orchestrator. The orchestrator maps it onto a gate decision, which may take an irreversible or security-relevant path in batch. It then records that decision in `feature-docs/{feature}/batch-audit.yaml`, which is the only after-the-fact account of an unattended choice.
Boundary files: em-workflow/references/question-resolution.md, em-workflow/references/opus-escalation-contract.md, em-workflow/references/phase-state.md
Depth: deep (input-handling, data-persistence)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A manipulated or malformed escalation return can carry several kinds of bad answer: an option that does not belong to the question, an answer for an unknown question, free text posing as a decision, or a non-packet presentation that omits the safe choice. Any of these drives the orchestrator to a choice no presented option supports (FR2, FR3, FR4) | TM-4 | The contract closes the per-question return set: an `option_id` drawn from that question's own `options[].option_id`, or an explicit no-decision, with reasoning in both cases. An unknown question, a foreign option, a missing entry or an unusable return counts as a no-decision. The non-packet presentation's options always include the gate's minimum-side-effect option. The section keeps its rule that the orchestrator reads the output as untrusted, never executes it, never adopts it verbatim, and keeps the per-question mapping judgement | task0001 AC-4, AC-6, AC-7 | VERIFICATION.md TM-4 (TS3, TS4) |
| Denial of service | A non-packet gate re-enters the escalation repeatedly within one run, so dispatches multiply without bound. The per-command approval fallback is the main case, being hit once per command attempt (FR4) | TM-5 | The section bounds the non-packet scope. Each non-packet gate resolution gets one dispatch. The per-command approval fallback gets at most one dispatch per distinct literal command string within a run. A no-decision falls to the minimum-side-effect option | task0001 AC-7 | VERIFICATION.md TM-5 (TS4) |
| Repudiation | An escalation-decided non-packet gate is recorded with an unclear or unsupported `source`. The resulting audit record misstates whether Codex was consulted, or whether the escalation ran at all, so an unattended decision cannot be traced afterwards (FR5, NFR1) | TM-6 | phase-state.md maps the case to the existing `batch-codex-consultation` value. That value is read as naming the consultation route, never as a claim that Codex was consulted, including when no harness was available. The Non-packet gates writer's `resolution_note` names whether the Opus escalation ran and its reasoning. A worked example shows the no-Codex-turn record | task0003 AC-1, AC-2, AC-3 | VERIFICATION.md TM-6 (TS5) |
