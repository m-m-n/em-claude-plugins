# Feature: codex-guard-extglob-funcname

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）は、extglob の演算子 `?()` `*()` `+()` `@()` `!()` を含む語を関数名と読み、その後ろの実行グループを判定から外している。この検出漏れをなくす。

## Objectives

- codex-hook-interactive-guard.py（em-workflow / em-review の両コピー）が、extglob の演算子 `?()` `*()` `+()` `@()` `!()` を含む語を関数名と読んで後ろの実行グループを判定から外す検出漏れをなくす

## Technical Requirements

### Functional Requirements

- **FR1: extglob の演算子文字で終わる語は関数名とみなさない**
  `_Parser._names_function` は、予約語の除去と `function` の除去のあとに残った 1 語のテキストの末尾が `?` `*` `+` `@` `!` のいずれかであるとき、関数名とみなさない（False を返す）。その語の後ろの `()` は関数定義を始めず、続くグループ（`( ... )` / `{ ...; }`、改行を挟む場合を含む）は判定の対象になる。
- **FR2: 予約語の有無によらず同じ扱い**
  FR1 は、予約語の無い形（`f?()`）、予約語の連なりの直後の形（`then f?()`、`time /bin/true?()`、`time -p f?()` など）、`function` 付きの形（`function f?()`）のすべてに適用する。
- **FR3: bash -c の文字列の中でも同じ判定**
  `bash -O extglob -c '<文字列>'` の文字列の中に FR1 の形と、その後ろに改行を挟んだ対話起動のグループ（例: `(python3 -i)`）があるとき、ガードは deny を返す。
- **FR4: 既存の関数定義の判定は変えない**
  末尾が FR1 の文字でない関数名（`f()`、`my-func()`、`function f()`、予約語の直後の `f()`、予約語だけの 1 語 `then()` など）の判定は変えない。既存の CASES の期待する判定はすべてそのまま通る。
- **FR5: 説明文の更新**
  モジュールの docstring の手順 4、`_Group` の `head` の説明、`_names_function` の docstring に FR1 の規則を書き足す。`tests/test_codex_hook_interactive_guard.py` の `TestGuardDocumentation` に、その文を確かめる目印を足す。
- **FR6: テストケースの追加**
  `tests/test_codex_hook_interactive_guard.py` の `CASES` に `(期待する判定, ラベル, コマンド)` の形で deny ケースを足す。予約語の有り（例: `bash -O extglob -c 'time /bin/true?()` + 改行 + `(python3 -i)'`）と無し（例: `bash -O extglob -c 'f?()` + 改行 + `(python3 -i)'`）の両方を `bash -O extglob -c` の形で含める。

### Non-Functional Requirements

- **NFR1:** `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **NFR2:** ガードは標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない既存の制約（TestStaticConstraints）を保つ。判定はコマンド文字列だけで決まり、作業ディレクトリや環境変数に依存しない。
- **NFR3:** プラグインの version は変えない。

## Acceptance Criteria

- [ ] AC1（FR1, FR2, FR3）: `bash -O extglob -c 'time /bin/true?()` + 改行 + `(python3 -i)'` を両コピーに渡すと deny が返る。
- [ ] AC2（FR1, FR2, FR3）: `bash -O extglob -c 'f?()` + 改行 + `(python3 -i)'`（予約語の無い形）を両コピーに渡すと deny が返る。
- [ ] AC3（FR1）: `?` `*` `+` `@` `!` の各文字について、末尾がその文字の語の `()` の後ろに改行と `(python3 -i)` が続くコマンドは deny になる。
- [ ] AC4（FR4, NFR2）: 既存の CASES のすべてが両コピーで期待どおりの判定になる（`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る）。
- [ ] AC5（FR5）: docstring の手順 4、`_Group` の `head` の説明、`_names_function` の docstring に FR1 の規則があり、TestGuardDocumentation がそれを確かめる。
- [ ] AC6（NFR1）: 2 つのコピーがバイト単位で同一である（TestCopies が通る）。
- [ ] AC7（FR4, NFR1, NFR2）: `python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### 対象ファイル

- `em-workflow/scripts/codex-hook-interactive-guard.py`
    - `_Parser._names_function`（FR1, FR2, FR4）
    - モジュールの docstring の手順 4、`_Group` の `head` の説明、`_names_function` の docstring（FR5）
- `em-review/scripts/codex-hook-interactive-guard.py`
    - 上と同じ内容。バイト単位で同一（NFR1）
- `tests/test_codex_hook_interactive_guard.py`
    - `CASES` への deny ケースの追加（FR6）
    - `TestGuardDocumentation` への目印の追加（FR5）

### 前提

- A1: 判定は語のテキストの末尾の文字だけで行う。末尾の文字が引用符やバックスラッシュで囲まれていても（`'f?'()`、`f\?()`）、`(` との間に空白があっても（`f? ()`）、関数名とみなさない。
- A2: extglob が無効の Bash で `f?() { ...; }` が関数定義として読まれる場合も、ガードはその本体を判定の対象にする。本体に対話起動があれば deny になる。
- A3: 予約語だけの 1 語が FR1 の文字で終わる場合（`!()`）も FR1 を適用し、関数名とみなさない。
- A4: 既存の CASES の deny / silent ケースは消さない。既存の CASES に `?()` `*()` `+()` `@()` `!()` を含むコマンドは無く、FR1 で期待する判定が変わる既存ケースは無い。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-extglob-funcname/**`
- `test-docs/codex-guard-extglob-funcname/**`

`feature-docs/codex-guard-extglob-funcname/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-extglob-funcname/**` covers `test-docs/codex-guard-extglob-funcname/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-extglob-funcname/` directory at all; the declared
`test-docs/codex-guard-extglob-funcname/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

コマンド中の `\n` は改行を表す。

### Unit Tests（`tests/test_codex_hook_interactive_guard.py` の `CASES`、両コピーに流す）

- [ ] TS1（FR1, FR2, FR3, FR6）: `bash -O extglob -c 'time /bin/true?()\n(python3 -i)'` - deny（予約語の有り、bash -c の中）
- [ ] TS2（FR1, FR2, FR3, FR6）: `bash -O extglob -c 'f?()\n(python3 -i)'` - deny（予約語の無し、bash -c の中）
- [ ] TS3（FR1, FR2）: `if true; then f?()\n(python3 -i)\nfi` - deny（then の直後、最上位）
- [ ] TS4（FR1）: `f*()\n(python3 -i)` / `f+()\n(python3 -i)` / `f@()\n(python3 -i)` / `f!()\n(python3 -i)` - それぞれ deny（残りの演算子文字それぞれ 1 ケース）
- [ ] TS5（FR1, FR2）: `function f?()\n{ python3 -i; }` - deny（function 付きの形、波括弧のグループ）
- [ ] TS6（FR4）: 既存の `foo()\n(python3 -i)` / `then()\n(python3 -i)` / `time f() { python3 -i; }` など - silent（既存の関数定義の判定が変わらないこと）

### Documentation / Copy Tests

- [ ] `TestGuardDocumentation` が FR1 の規則の記述を確かめる（FR5）
- [ ] `TestCopies` が 2 つのコピーのバイト単位の同一性を確かめる（NFR1）
- [ ] `TestStaticConstraints` が通る（NFR2）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### 実行コマンド

```
python3 -m unittest tests.test_codex_hook_interactive_guard
python3 -m unittest discover -s tests
```

## Success Criteria

- [ ] AC1〜AC7 をすべて満たす
- [ ] 上の 2 つの実行コマンドが通る

## Open Questions

なし（`status: tbd` の要件は無い）。
