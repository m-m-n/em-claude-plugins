---
name: gpt.security
description: GPT/Codex security review of the current code change. Cross-validates the Claude security reviewer. Falls back to whole-codebase mode in non-git directories. Skips cleanly when codex-cli is unavailable.
disable-model-invocation: true
context: fork
agent: multi-review-gpt-security
---

Get a Codex (GPT) second opinion on security aspects of the current code change.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the GPT-security workflow in the `multi-review-gpt-security` agent definition (codex availability check, schema path resolution, prompt construction, readonly Codex invocation).

$ARGUMENTS
