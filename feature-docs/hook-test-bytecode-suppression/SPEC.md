# Feature: hook-test-bytecode-suppression

## Overview

`tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` が `em-workflow/hooks/destructive-guard.py` を `spec.loader.exec_module()` で読み込むとき、読み込み中だけ `sys.dont_write_bytecode` を `True` にし、`em-workflow/hooks/__pycache__/` にバイトコードが書かれないようにする。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- `tests/test_destructive_guard_extglob_units.py` と `tests/test_destructive_guard_lexer_agreement.py` の実行で `em-workflow/hooks/__pycache__/` にバイトコードが書かれないようにする。

## User Stories

該当なし。

## Technical Requirements

### Functional Requirements
- **FR1:** extglob_units のフック読み込みでバイトコードを書かない。`tests/test_destructive_guard_extglob_units.py` の `load_hook()` は、`em-workflow/hooks/destructive-guard.py` を `spec.loader.exec_module()` で読み込むときに `sys.dont_write_bytecode` を `True` にする。読み込みの後（読み込みが例外を投げた場合も含む）は、読み込み前の値に戻す。
- **FR2:** lexer_agreement のフック読み込みでバイトコードを書かない。`tests/test_destructive_guard_lexer_agreement.py` の `_load_hook()`（モジュール読み込み時に `H = _load_hook()` として呼ばれる）は、`em-workflow/hooks/destructive-guard.py` を `spec.loader.exec_module()` で読み込むときに `sys.dont_write_bytecode` を `True` にする。読み込みの後（読み込みが例外を投げた場合も含む）は、読み込み前の値に戻す。
- **FR3:** 全体実行でも em-workflow/hooks/ 配下に __pycache__ ができない。リポジトリルートで `python3 -m unittest discover -s tests` を実行した後、`em-workflow/hooks/` 配下（`em-workflow/hooks/tests/` を含む）に `__pycache__` ができない。

### Non-Functional Requirements
- **NFR1:** 既存テストはすべて通る（`python3 -m unittest discover -s tests` と `python3 em-workflow/hooks/tests/run-destructive-guard.py`）。
- **NFR2:** テストコードは標準ライブラリだけを使う（test/README.md、および両ファイルの `TestModuleContract` が標準ライブラリだけの import を確かめている）。
- **NFR3:** 読み込み後の `sys.dont_write_bytecode` は読み込み前の値と同じ。同じプロセスで動く他のテストモジュールの挙動を変えない。

## Implementation Approach

### Architecture

変更箇所は次の 2 つの関数だけ。

| ファイル | 関数 | 要件 |
|---|---|---|
| `tests/test_destructive_guard_extglob_units.py` | `load_hook()` | FR1、NFR3 |
| `tests/test_destructive_guard_lexer_agreement.py` | `_load_hook()` | FR2、NFR3 |

どちらも `spec.loader.exec_module()` の呼び出しの間だけ `sys.dont_write_bytecode` を `True` にし、呼び出しの後（例外を投げた場合も含む）に読み込み前の値に戻す。

### Data Flow

```
読み込み前の sys.dont_write_bytecode を保持
  → sys.dont_write_bytecode = True
  → spec.loader.exec_module()（destructive-guard.py）
  → 正常終了・例外のどちらでも、保持した値に戻す
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: 読み込み対象。変更しない。

**External Dependencies:**
- なし（標準ライブラリだけを使う。NFR2）。

### File Structure

```
tests/
├── test_destructive_guard_extglob_units.py   # load_hook() を変更（FR1）
└── test_destructive_guard_lexer_agreement.py # _load_hook() を変更（FR2）
```

変更対象にしない経路:
- サブプロセスでフックを起動する経路（`tests/test_destructive_guard_lexer_agreement.py` の `hook_verdict()`、`em-workflow/hooks/tests/run-destructive-guard.py` の `verdict()`）。
- フック自身の `load_merge_exception()` による `merge_pr_allow.py` の読み込み。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/hook-test-bytecode-suppression/**`
- `test-docs/hook-test-bytecode-suppression/**`

`feature-docs/hook-test-bytecode-suppression/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/hook-test-bytecode-suppression/**` covers `test-docs/hook-test-bytecode-suppression/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/hook-test-bytecode-suppression/` directory at all; the declared
`test-docs/hook-test-bytecode-suppression/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

確認はすべて `em-workflow/hooks/` 配下に `__pycache__` が無い状態から始める（`__pycache__/` は `.gitignore` で無視されているため、以前の実行で残ったものは `git status` に出ない）。

### Unit Tests
- [ ] TS-1（AC-1 / FR1）: `tests.test_destructive_guard_extglob_units` を単体実行する - テストが通り、実行後も `em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] TS-2（AC-2 / FR2）: `tests.test_destructive_guard_lexer_agreement` を単体実行する - テストが通り、実行後も `em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] TS-5（NFR3）: `load_hook()` / `_load_hook()` を呼ぶ前と後の `sys.dont_write_bytecode` を比べる - 値が同じ。

### Integration Tests
- [ ] TS-3（AC-3、AC-4 / FR3、NFR1、NFR2、NFR3）: リポジトリルートから `python3 -m unittest discover -s tests` を実行する - 全テストが通り、実行後も `em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] TS-4（AC-4 / NFR1、NFR2、NFR3）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行する - 全ケース通る。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] `spec.loader.exec_module()` が例外を投げた場合: `sys.dont_write_bytecode` は読み込み前の値に戻る（FR1、FR2）。

### Performance Tests
該当なし。

## Security Considerations

該当なし。

## Error Handling

### Error Codes

該当なし。

### Error Flow

```
spec.loader.exec_module() が例外を投げる → sys.dont_write_bytecode を読み込み前の値に戻す
```

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC-1（FR1）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態から `python3 -m unittest tests.test_destructive_guard_extglob_units` を実行した後、`em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] AC-2（FR2）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態から `python3 -m unittest tests.test_destructive_guard_lexer_agreement` を実行した後、`em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] AC-3（FR3）: `em-workflow/hooks/` 配下に `__pycache__` が無い状態から `python3 -m unittest discover -s tests` を実行した後、`em-workflow/hooks/` 配下に `__pycache__` が無い。
- [ ] AC-4（NFR1、NFR2、NFR3）: 既存テストはすべて通る。

## Assumptions

- A-1: 修正は 2 本のテストファイル（`tests/` 配下）だけで行う。`em-workflow/hooks/destructive-guard.py` は変更しない。
- A-2: サブプロセスでフックを起動する経路（lexer_agreement の `hook_verdict()`、`run-destructive-guard.py` の `verdict()`）は、フックをスクリプトとして実行するのでフック本体のバイトコードを書かない。隣のモジュール `merge_pr_allow.py` はフック自身の `load_merge_exception()` が `sys.dont_write_bytecode` を立てて読み込む。この経路は変更対象にしない。
- A-3: 受け入れ条件の確認は `em-workflow/hooks/` 配下に `__pycache__` が無い状態から始める。`__pycache__/` は `.gitignore` で無視されているため、以前の実行で残ったものは `git status` に出ない。
- A-4: 変更は `tests/` 配下だけで、プラグイン配下のファイルを変更しないため、version の変更は伴わない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## References

- 要件定義書: `feature-docs/hook-test-bytecode-suppression/REQUIREMENTS.md`
