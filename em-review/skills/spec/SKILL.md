---
name: spec
description: Verifies the current code change against SPEC.md from a spec compliance perspective only (Claude). Skips cleanly when no SPEC.md exists. Outputs JSON findings on direct contradictions, mis-implemented logic, missing required functionality, and data integrity violations.
disable-model-invocation: true
context: fork
agent: multi-review-spec
---

Verify the current code change against SPEC.md.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the spec-compliance-specific guidance in the `multi-review-spec` agent definition (including SPEC.md discovery and clean skip behavior).

$ARGUMENTS
