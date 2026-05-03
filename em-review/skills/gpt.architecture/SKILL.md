---
name: gpt.architecture
description: GPT/Codex architecture review of the current code change. Cross-validates the Claude architecture reviewer. Falls back to whole-codebase mode in non-git directories. Skips cleanly when codex-cli is unavailable.
disable-model-invocation: true
context: fork
agent: multi-review-gpt-architecture
---

Get a Codex (GPT) second opinion on architecture / design aspects of the current code change.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the GPT-architecture workflow in the `multi-review-gpt-architecture` agent definition.

$ARGUMENTS
