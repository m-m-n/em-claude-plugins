---
name: review-spec
description: 仕様準拠観点のレビュー知識（em-workflow 動的注入用）。SPEC.md との矛盾・必須動作の欠落・クリティカルロジックの誤実装・データ整合性違反を検出する基準を汎用レビュアーに与えます。SPEC.md 不在時はレビュアーがクリーンにスキップします。オーケストレーター指示以外で自発的にロードするものではありません。
user-invocable: false
---

# Review Perspective: Spec Compliance

This skill defines WHAT the spec perspective flags. Discipline comes from the
reviewer agent + review-protocol.md. The reviewer Reads `spec_path` (passed
by the orchestrator); with no resolvable SPEC.md it skips cleanly per the
protocol's Skip Semantics.

## What to flag (spec compliance only)

- **Direct contradictions**: code does X, spec mandates not-X.
- **Misimplemented critical logic**: required algorithm / formula / rule
  implemented incorrectly.
- **Missing required functionality**: a spec requirement not implemented at
  all in code that purports to implement it.
- **Data integrity violations**: invariants stated in the spec broken
  (uniqueness, ordering, monotonicity, ...).
- **Boundary mismatch**: API signatures / status codes / error semantics
  differ from spec.

For each finding, **quote or reference the spec passage** in the
`description` (e.g., "SPEC §3.2: ..."). Cannot point to a specific passage?
Do NOT raise it here — that is correctness/architecture territory.

## What NOT to flag

- Implementation choices the spec does not constrain.
- Code-quality concerns (other perspectives own those).

## category

Every finding MUST have `"category": "spec"`.
