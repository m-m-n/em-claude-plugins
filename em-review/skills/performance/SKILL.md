---
name: performance
description: Reviews the current code change from a performance perspective only (Claude). Falls back to whole-codebase mode in non-git directories. Outputs JSON findings on N+1, algorithmic blow-ups, memory inefficiency, blocking I/O, and resource leaks.
disable-model-invocation: true
context: fork
agent: multi-review-performance
---

Review the current code change from a performance perspective only.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the performance-specific guidance in the `multi-review-performance` agent definition.

$ARGUMENTS
