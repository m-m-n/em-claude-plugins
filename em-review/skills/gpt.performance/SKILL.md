---
name: gpt.performance
description: GPT/Codex performance review of the current code change. Cross-validates the Claude performance reviewer. Falls back to whole-codebase mode in non-git directories. Skips cleanly when codex-cli is unavailable.
disable-model-invocation: true
context: fork
agent: multi-review-gpt-performance
---

Get a Codex (GPT) second opinion on performance aspects of the current code change.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the GPT-performance workflow in the `multi-review-gpt-performance` agent definition.

$ARGUMENTS
