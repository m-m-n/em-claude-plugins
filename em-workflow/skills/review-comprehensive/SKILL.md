---
name: review-comprehensive
description: 包括観点のレビュー知識（em-workflow 動的注入用・常時実行 baseline）。単一観点レビュアーが見逃す横断バグ・正確性/ロジックバグ・統合と契約のドリフト・境界値・テスト齟齬を検出する基準を汎用レビュアーに与えます。オーケストレーター指示以外で自発的にロードするものではありません。
user-invocable: false
---

# Review Perspective: Comprehensive (baseline, Claude-only)

This skill defines WHAT the comprehensive perspective flags. Discipline comes
from the reviewer agent + review-protocol.md. This perspective is the
"catch what the others miss" lens and ALSO owns correctness/logic-bug
detection.

## What to flag

- **Cross-domain bugs**: fine in isolation, breaks an interaction (a
  security fix introducing a race; an optimization breaking an invariant).
- **Correctness / logic bugs**: off-by-one, wrong conditions, nil/undefined
  dereference, inverted booleans, swallowed errors, partial-failure state
  inconsistency, race conditions, TOCTOU.
- **Integration & contract drift**: caller / callee assumptions silently
  violated, mismatched return shapes, missing error propagation across
  boundaries.
- **Edge cases & boundary values**: empty collections, zero/negative inputs,
  Unicode, very large inputs, expired sessions, retried requests, partial
  reads.
- **Test/code mismatch**: tests asserting outdated behavior; new code paths
  with no coverage at all.
- **Migration / rollout safety**: backwards-incompatible change without a
  guard, feature flag, or migration step.
- **Code health hot-spots in the reviewed code**: dead code, logic
  duplicated into two places by the change, TODOs hiding a known bug.
- **SSOT drift across protocol/manifest/code** when reviewing prompt-driven
  plugins.

If a finding fits cleanly into security / performance / architecture / spec,
prefer to leave it to that perspective when it is selected this round; the
orchestrator deduplicates. When those perspectives are NOT selected this
round, report it here (you are the floor).

## What NOT to flag

Single-perspective issues another SELECTED reviewer will clearly catch.

## category

Every finding MUST have `"category": "comprehensive"`.
