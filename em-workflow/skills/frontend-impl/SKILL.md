---
name: frontend-impl
description: フロントエンド実装の知識（em-workflow implementer 動的注入用）。状態管理、コンポーネント設計、非同期処理の作法、ユニット＋コンポーネントテスト戦略、品質チェックリストと落とし穴を提供します。タスクの skills に frontend-impl が指定されたときに implementer がロードします。
user-invocable: false
---

# Implementation Skill: Frontend (state / components / async)

Layer-specific knowledge for tasks whose primary output is client-side
behavior. TDD discipline comes from `tdd-testing`; this adds the frontend
strategy.

## State management

- **Single source of truth per piece of state**: derive, don't duplicate. A
  value computable from existing state is a computed value, not a second
  store entry.
- Keep state at the lowest component that needs it; lift only when sharing
  demands it. Global stores are for genuinely global concerns.
- Server data is a cache, not app state: it has staleness, loading, and
  error dimensions — model them explicitly (or with the project's data
  fetching layer) instead of ad-hoc booleans.
- State transitions should be explicit and enumerable; boolean explosions
  (`isLoading && !isError && hasFetched`) are a smell — prefer a status
  union.

## Component design

- Follow the project's component conventions (props shape, file layout,
  naming) — read two or three sibling components before writing one.
- Container/presentation separation to the degree the project practices it:
  logic hooks/services testable without rendering.
- Props are the contract: no reaching into children, no undocumented
  context coupling. Boundary components validate/normalize external data.
- Composition over configuration flags: a component sprouting its fifth
  boolean prop usually wants splitting.

## Async correctness

- Every async operation has THREE user-visible outcomes: success, failure,
  and pending. Handle all three; swallowed rejections are bugs.
- Cancellation/staleness: a response arriving after unmount or after a newer
  request must not write state (abort, ignore-stale-token, or the
  fetch-layer's built-in dedupe).
- Race conditions: rapid re-trigger (typing, double-click, remount) is the
  default usage pattern, not an edge case — debounce/disable/dedupe per the
  plan.
- Optimistic updates need a rollback path.

## Test strategy (unit + component-behavior)

- Logic (reducers, hooks, services, validators): plain unit tests, no DOM.
- Components: behavior-level tests — interact as the user does (click,
  type), assert visible outcomes (text, roles, disabled states), not
  implementation internals or child call counts.
- Async: test all three outcomes + the stale-response case for anything
  cancellable.
- Mock at the network/service boundary, not inside your own module.

## Pitfalls

- Effect/subscription cleanup omitted (listeners, timers, observers leak
  across remounts).
- Deriving state in an effect instead of computing it during render.
- Key-less or index-keyed lists that shuffle state on reorder.
- Untyped/unvalidated API responses trusted at the boundary.
- Hidden temporal coupling: component works only when mounted after some
  sibling initialized a store.
