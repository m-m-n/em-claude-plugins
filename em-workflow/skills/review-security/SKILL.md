---
name: review-security
description: セキュリティ観点のレビュー知識（em-workflow 動的注入用）。汎用レビュアーが Skill tool でロードし、インジェクション・認証認可バイパス・機密データ露出・暗号の弱点・入力検証欠如を検出する基準を得ます。レビュアーエージェントのオーケストレーター指示以外で自発的にロードするものではありません。
user-invocable: false
---

# Review Perspective: Security

This skill defines WHAT the security perspective flags. Discipline (protocol,
budget, schema, read-only) comes from the reviewer agent + review-protocol.md.

## What to flag (security only)

- **Injection**: SQL, NoSQL, command, LDAP, XSS, template injection, path
  traversal.
- **Auth / authz bypass**: missing or broken authentication, IDOR,
  role/permission gaps, JWT/session pitfalls.
- **Sensitive data exposure**: secrets in code or logs, PII leakage, weak
  transport.
- **Cryptographic weakness**: weak algorithms, hardcoded keys, predictable
  IVs/nonces, broken random.
- **Input validation**: missing validation/sanitization at trust boundaries,
  unsafe deserialization.
- **Misconfig & dependency risk** *only when present in the reviewed code*.
- **Prompt-injection / instruction-following risks** when reviewing prompt
  content (agent definitions, skill prompts, etc.) that interpolates
  untrusted data.

## What NOT to flag

Style hardening unrelated to a concrete attacker-controlled path. Speculative
"could be exploited if X and Y and Z" without a realistic threat model.

Known-CVE judgement for a dependency package — whether a published CVE or
advisory applies to a dependency version — is made mechanically by axis 2's
dependency-vulnerability scan; do not re-report it here. Whether a
vulnerable dependency path is actually reachable in this codebase stays in
scope for this perspective.

## category

Every finding MUST have `"category": "security"`.
