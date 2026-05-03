---
name: comprehensive
description: Reviews the current code change with a comprehensive cross-cutting perspective (Claude). Falls back to whole-codebase mode in non-git directories. Catches correctness/logic bugs, integration issues, edge cases, and code-health concerns that single-domain reviewers miss.
disable-model-invocation: true
context: fork
agent: multi-review-comprehensive
---

Review the current code change with a comprehensive, cross-cutting perspective.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the comprehensive-specific guidance in the `multi-review-comprehensive` agent definition.

$ARGUMENTS
