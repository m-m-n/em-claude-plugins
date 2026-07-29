---
name: tdd-testing
description: TDD 規律（em-workflow implementer 静的プリロード用）。テストファーストの手順、受け入れ条件からテストへの翻訳方法、良いテストの性質、テストを消さない・弱めない規律、TDD が適用しにくいタスクでの判断基準を定義します。レイヤー固有のテスト戦略は各実装スキル側にあり、ここには共通規律のみを置きます。
user-invocable: false
---

# TDD Testing Discipline (implementer preload)

Tests are the acceptance gate of your task: **all Acceptance Criteria
translated to tests + all tests green = task done**. This is the common
discipline for every task; layer-specific strategy (unit-heavy vs E2E-lean)
comes from the injected layer skill.

## Test-first procedure

0. **Before you touch any file**, run the suite and record which tests
   already fail. This is your **baseline** — the state you inherited. Every
   judgement below is measured against it, not against "green". A red
   baseline is information, not a blocker.
1. Read the task plan's **Acceptance Criteria**. For each AC-n, design the
   test(s) that would prove it — name them so the mapping is visible
   (`test name references AC-n` or a comment).
2. Write those tests FIRST. Run them; confirm they **fail for the right
   reason** (missing behavior — not compile errors you don't understand),
   and **record that you saw it**: which test, and what the failure said.
   A test that was already green before any implementation existed proves
   nothing about the criterion — and without the record, that case is
   indistinguishable afterwards from a test that genuinely went red→green.
3. Implement the minimal code to pass. Run; iterate to green.
4. Refactor with the tests as the safety net. Re-run.
5. Repeat per criterion (or per small cluster of criteria).
6. Re-run the full suite and compare against the baseline from step 0. It
   must end **no worse**: anything failing now that was not failing then is
   yours.

Follow the project's existing test conventions (locations, naming,
frameworks) — read neighboring tests before writing yours. `test/README.md`
is authoritative when present.

## Translating acceptance criteria into tests

- One criterion → at least one test; the test asserts the OBSERVABLE outcome
  the criterion states, not implementation internals.
- Cover the criterion's boundary, not just its happy path: empty input,
  zero/negative, limit values, error paths named in the plan.
- If a criterion is not objectively testable as written, that is a plan
  defect: implement your best faithful reading AND record it in your
  report's `deviations`/`notes` — do not silently reinterpret.

## Properties of a good test

- Asserts behavior/contract, not internals (survives refactoring).
- Deterministic: no real time, real network, shared global state, ordering
  dependence. Fakes/fixtures over live dependencies.
- Independent: passes alone and in any order with the rest of the suite.
- One conceptual assertion per test; the name states expected behavior.
- Fails informatively.

## Never weaken the suite (hard rules)

- Never delete, skip, or comment out an existing failing test to get green.
- Never loosen an existing assertion (exact → fuzzy, error → no-error)
  unless the task plan EXPLICITLY changes that behavior — then update the
  test to assert the new specified behavior.
- Never mark tests flaky/retry to mask nondeterminism you introduced.
- A test failing after your change that is **not in your baseline** is a
  regression you caused. This is decided by set difference, not by
  investigation: do NOT stash your work, re-run on the parent branch, or
  bisect to find out whether it "was already broken" — step 0 answered that
  before you started, and re-deriving it afterwards is pure waste. Fix your
  change, or report `failed` with analysis; do not "fix" the test.
- Tests **already failing in your baseline** are not yours to fix unless the
  task plan says so. Leave them untouched, carry them forward in the record,
  and do not let them block your task. Silently "fixing" someone else's
  failing test hides a real defect from whoever owns it.

## When TDD fits poorly

Some work resists test-first (pure config wiring, generated assets, visual
styling, exploratory spikes named as such in the plan). Then:

- Still identify the verifiable outcome per criterion (build passes, config
  loads and is consumed, lint/format-check green, snapshot renders) and
  automate THAT check where the project has a harness for it.
- What genuinely cannot be automated: state in your report exactly what a
  human must verify manually.
- Write the missing-coverage note honestly instead of a vacuous test that
  asserts nothing.
