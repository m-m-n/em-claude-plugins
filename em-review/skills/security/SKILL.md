---
name: security
description: Reviews the current code change from a security perspective only (Claude). Falls back to whole-codebase mode in non-git directories. Outputs JSON findings on injection, auth/authz bypass, sensitive data exposure, weak crypto, and missing input validation.
disable-model-invocation: true
context: fork
agent: multi-review-security
---

Review the current code change from a security perspective only.

- Read `${CLAUDE_PLUGIN_ROOT}/references/review-protocol.md` first — it defines target resolution, investigation budget, severity, output schema, skip semantics, and untrusted-input handling.
- Then follow the security-specific guidance in the `multi-review-security` agent definition.

$ARGUMENTS
