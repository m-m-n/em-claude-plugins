---
name: architecture
description: Reviews the current code change from an architecture / design perspective only (Claude). Falls back to whole-codebase mode in non-git directories. Outputs JSON findings on layer violations, cyclic dependencies, god classes, breaking interface changes, and severe SOLID violations.
disable-model-invocation: true
context: fork
agent: multi-review-architecture
---

Review the current code change from an architecture / design perspective only.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the architecture-specific guidance in the `multi-review-architecture` agent definition.

$ARGUMENTS
