---
name: backend-impl
description: バックエンド実装の知識（em-workflow implementer 動的注入用）。API 設計、エラーハンドリング、トランザクション境界、ユニット寄りのテスト戦略、品質チェックリストと落とし穴を提供します。タスクの skills に backend-impl が指定されたときに implementer がロードします。
user-invocable: false
---

# Implementation Skill: Backend (API / domain logic / data access)

Layer-specific knowledge for tasks whose primary output is server-side or
core-domain logic. TDD discipline comes from `tdd-testing`; this adds the
backend strategy.

## API design

- The task plan / IMPLEMENTATION.md contract is authoritative: request/
  response shapes, status codes, and error semantics are spec, not
  preference. Divergence discovered mid-task is a reportable deviation.
- Validate at the boundary: every external input validated/normalized before
  it reaches domain logic; validation failures produce the contract's error
  shape, never a stack trace.
- Idempotency: retried requests are normal traffic. Mutating endpoints
  need a defined double-submit story (idempotency keys, upsert semantics, or
  documented at-most-once).
- Never leak internals: DB errors, file paths, and dependency exceptions are
  logged, not returned.

## Error handling

- Errors are part of the contract: distinguish caller errors (4xx-shaped)
  from system errors (5xx-shaped) at the type/return level, not by string
  matching.
- No swallowed errors: every error path either handles meaningfully or
  propagates with context (wrap, don't rethrow bare).
- Partial failure discipline: a multi-step operation that fails midway
  leaves a DEFINED state — rolled back, compensated, or explicitly
  documented as partially-applied and queryable.
- Log at the boundary once, with correlation context; avoid double-logging
  every layer.

## Transaction boundaries

- One business operation = one transaction boundary, placed at the use-case/
  service layer — not inside repositories (too narrow) nor around whole
  request handlers (too wide).
- Nothing non-transactional inside a transaction: no network calls, no
  long computation while holding the transaction/locks.
- Read-modify-write under concurrency needs an explicit strategy (unique
  constraints, optimistic version columns, SELECT ... FOR UPDATE — per
  project convention).
- Side effects that escape the transaction (emails, events, external calls)
  happen after commit, or via an outbox pattern when the project has one.

## Test strategy (unit-leaning)

- Domain logic: pure unit tests, exhaustive on branches and boundaries —
  this is where the bulk of the suite lives.
- Data access: integration tests against the project's test DB harness
  (real constraint/transaction semantics); don't unit-mock SQL and call it
  tested.
- API surface: contract-level tests per endpoint — happy path + each defined
  error shape + validation failure.
- Concurrency-sensitive paths: at minimum a test provoking the conflict case
  (duplicate submit, version clash).

## Pitfalls

- N+1 queries introduced by convenient lazy iteration (the performance
  reviewer will find them; don't ship them).
- Time handling: naive local times, `now()` scattered instead of injected —
  system timezone / clock discipline per project convention.
- Nullable creep in schemas to dodge migrations the plan actually requires.
- Hidden global state (package-level singletons) that breaks test isolation.
- Catch-all exception handlers that turn programming errors into silent 200s.
