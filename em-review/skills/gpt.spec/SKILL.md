---
name: gpt.spec
description: GPT/Codex spec compliance review of the current code change against SPEC.md. Cross-validates the Claude spec reviewer. Skips cleanly when codex-cli is unavailable OR when no SPEC.md is provided.
disable-model-invocation: true
context: fork
agent: multi-review-gpt-spec
---

Get a Codex (GPT) second opinion on spec compliance of the current code change.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the GPT-spec workflow in the `multi-review-gpt-spec` agent definition (codex availability, SPEC.md presence, schema path resolution, prompt construction with both spec_contents and review target).

$ARGUMENTS
