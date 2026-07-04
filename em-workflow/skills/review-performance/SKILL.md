---
name: review-performance
description: パフォーマンス観点のレビュー知識（em-workflow 動的注入用）。N+1 クエリ・計算量爆発・メモリ非効率・ブロッキング I/O・リソースリークを検出する基準を汎用レビュアーに与えます。オーケストレーター指示以外で自発的にロードするものではありません。
user-invocable: false
---

# Review Perspective: Performance

This skill defines WHAT the performance perspective flags. Discipline comes
from the reviewer agent + review-protocol.md.

## What to flag (performance only)

- **N+1 queries**: per-item DB / network calls inside loops; missing
  eager-loading or batching.
- **Algorithmic blow-ups**: O(n²) where O(n) is trivial; repeated scans of
  the same collection.
- **Memory inefficiency**: loading whole datasets into memory, large
  allocations in hot paths, lifetime leaks.
- **Blocking I/O**: synchronous I/O in async contexts, unawaited promises,
  blocking calls on the request path.
- **Resource leaks**: unreleased file handles, sockets, DB connections,
  missing `defer`/`with`/`using`.
- **Cache misses**: removing or bypassing caches; expensive recomputation.
- **Serialization hotspots**: redundant JSON parse/stringify, heavy
  reflection per request.
- **Multiplicative LLM / external-call cost** when reviewing
  orchestrator-style prompt code (e.g. fan-out × loop iterations).

## What NOT to flag

Micro-optimizations without measurable impact. "Could be faster" without a
realistic input scale.

## category

Every finding MUST have `"category": "performance"`.
