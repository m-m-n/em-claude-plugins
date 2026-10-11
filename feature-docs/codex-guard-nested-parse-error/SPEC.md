# Feature: codex-guard-nested-parse-error

## Overview

`codex-hook-interactive-guard.py`（em-workflow / em-review の 2 コピー）を直す。リダイレクト演算子の直前にある数字だけの語を int に変換せずに読み、int の範囲を超える数字列は普通の語として扱う。入れ子の文字列の parse で想定外の例外が出たときは、その文字列を読み飛ばして走査を続ける。要件は `REQUIREMENTS.md` を参照する。

## Objectives

- 入れ子の `bash -c` 文字列の parse で例外が出ても、ガード全体が無出力にならず、後続のコマンドの判定を続ける。
- 数千桁の数字がリダイレクトの直前にあっても、後続の対話起動を見逃さない（0 段目・1 段目・2 段目以降のどれでも）。

## Acceptance Criteria

- [ ] AC1: 再現手順の入力をガードの `main` に渡すと、標準出力に deny が 1 つ出る（両コピー）（FR1, FR3, FR5）
- [ ] AC2: `': ' + '9'*5000 + '>/dev/null; python3 -i'` と、その 1 段目版が deny になる（FR1, FR3, FR5, FR7）
- [ ] AC3: `'python3 00< f'` と `'python3 2147483648>/dev/null'` は silent、`'python3 2147483647>/dev/null'` は deny（FR1, FR5, FR7）
- [ ] AC4: `_scan` で `parse(inner)` を囲む例外処理が、`_Undecidable` に加えて想定外の例外（`Exception`）も捕まえ、読み飛ばして走査を続ける（FR2）
- [ ] AC5: docstring の手順 7 が、想定外のエラーが出た文字列も読み飛ばすと述べ、そのマーカーがテストで固定されている（FR6）
- [ ] AC6: 既存の `CASES` の判定がすべて変わらない。2 つのコピーがバイト単位で同一。テストスイートと plugin invariants が通る（FR4, NFR1, NFR2, NFR3）
- [ ] AC7: version ファイルに差分がない（NFR4）

## Technical Requirements

### Functional Requirements

- **FR1:** fd を int 変換せずに読む。`_Parser._redirection` は、リダイレクト演算子の直前にある、クォートのない数字だけの語を int に変換しない。先頭の 0 を除いた桁数と文字列の比較だけで判定する。どんな桁数でも例外を出さない。全ゼロの数字列（`0`、`00`、5000 個の `0` など）は fd 0、つまり標準入力の接続とみなす。
- **FR2:** 入れ子の文字列の想定外の例外を読み飛ばす。`_scan` の `parse(inner)` で `_Undecidable` 以外の例外（`Exception`）が出たときも、その文字列を読み飛ばし、それを持つコマンドの次から走査を続ける。拒否の理由にはしない。0 段目の `parse(command)` の扱いは変えない（無出力のまま）。読み直し文字数の累計は、これまでどおり parse の前に加算する。
- **FR3:** 依頼された回帰ケース。`tests/test_codex_hook_interactive_guard.py` の `CASES` に deny ケースを 2 つ足す。(a) 再現手順の入力: `': ' + '9'*5000 + '>/dev/null'` を `json.dumps` で 2 回 `'bash -c '` に包み、`'; python3 -i'` を続けたもの。(b) 0 段目の同じ形: `': ' + '9'*5000 + '>/dev/null; python3 -i'`。
- **FR4:** 2 つのコピーをバイト単位で同一に保つ。`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- **FR5:** int の範囲を超える数字列は普通の語として扱う。FR1 の数字列は、先頭の 0 を除いた値が 2147483647 以下のときだけ fd として読む。除いた後に 11 桁以上のもの、または 10 桁で文字列として `"2147483647"` より大きいものは fd ではない。その数字列は普通の語として残り、リダイレクトは演算子の既定の fd（`>` は標準出力、`<` は標準入力）にかかる。2147483647 以下の値の数字列の判定は、修正前と変わらない。
- **FR6:** docstring 手順 7 に書き足す。module docstring の手順 7 で、読めない文字列の例として「読んでいる途中で想定外のエラーが出た文字列」を加える。その文を `TestGuardDocumentation.DOCSTRING_MARKERS` に足して固定する。両コピーに同じ変更を入れる。
- **FR7:** 追加の回帰ケース。`CASES` に次を足す。
    - silent: `'python3 00< f'`（全ゼロの複数桁 fd は標準入力）
    - deny: `"bash -c ': " + '9'*5000 + ">/dev/null'; python3 -i"`（1 段目の巨大な数字）
    - silent: `'python3 2147483648>/dev/null'`（数字列が python3 のオペランドになる）
    - deny: `'python3 2147483647>/dev/null'`（fd として読まれ、オペランドなしの起動になる）

### Non-Functional Requirements

- **NFR1 - 標準ライブラリのみ・副作用なし:** 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（`TestStaticConstraints`）。
- **NFR2 - 再帰を入れない:** 入れ子の走査は明示的な作業リストのまま。再帰呼び出しを足さない（`TestNoRecursion`）。
- **NFR3 - テストスイートが通る:** `python3 -m unittest tests.test_codex_hook_interactive_guard`、`python3 -m unittest discover -s tests`、`python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。`CASES` のコマンドは重複しない。
- **NFR4 - version を変えない:** `<plugin>/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は変えない。
- **NFR5 - 誤拒否より通過を優先する:** 想定外のエラーは読み飛ばし（通過）に倒す。拒否には倒さない。

## Implementation Approach

### Architecture

変更する箇所:

| 箇所 | 変更 | 要件 |
|------|------|------|
| `_Parser._redirection` | 演算子の直前の数字だけの語を int に変換せず、桁数と文字列の比較で fd を判定する | FR1, FR5 |
| `_scan` の `parse(inner)` を囲む例外処理 | `_Undecidable` に加えて `Exception` を捕まえ、読み飛ばして走査を続ける | FR2, NFR5 |
| module docstring の手順 7 | 「読んでいる途中で想定外のエラーが出た文字列」を読めない文字列の例に加える | FR6 |
| `tests/test_codex_hook_interactive_guard.py` の `CASES` | 回帰ケースを足す | FR3, FR7 |
| `TestGuardDocumentation.DOCSTRING_MARKERS` | 手順 7 に足した文を加える | FR6 |

変えない箇所:

- 0 段目の `parse(command)` で出た例外の扱い（無出力のまま。手順 9）
- `_judge` の例外処理
- module docstring の手順 6

### fd の判定規則

対象は、リダイレクト演算子の直前にある、クォートのない数字だけの語（FR1, FR5）。

| 数字列（先頭の 0 を除いた後） | 扱い |
|-------------------------------|------|
| 空（全ゼロ。`0`、`00`、5000 個の `0` など） | fd 0（標準入力の接続） |
| 1〜9 桁 | その値の fd |
| 10 桁で、文字列として `"2147483647"` 以下 | その値の fd |
| 10 桁で、文字列として `"2147483647"` より大きい | fd ではない。普通の語として残り、リダイレクトは演算子の既定の fd にかかる |
| 11 桁以上 | 同上 |

- 演算子の既定の fd は、`>` が標準出力、`<` が標準入力。
- 2147483647 以下の値の数字列の判定は、修正前と変わらない。
- どんな桁数でも例外を出さない。

### Data Flow

```
command（0 段目）
  → parse(command)              例外: 無出力のまま（変更なし）
  → _scan（明示的な作業リスト）
      → 入れ子の文字列ごとに、読み直し文字数の累計を加算
      → parse(inner)
          _Undecidable: 読み飛ばし、次のコマンドから走査を続ける（変更なし）
          Exception:    読み飛ばし、次のコマンドから走査を続ける（FR2）
  → 判定（deny / silent）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- なし

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）

### File Structure

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1, FR2, FR5, FR6
em-review/scripts/codex-hook-interactive-guard.py     # 上とバイト単位で同一（FR4）
tests/test_codex_hook_interactive_guard.py            # FR3, FR6, FR7
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-nested-parse-error/**`
- `test-docs/codex-guard-nested-parse-error/**`

`feature-docs/codex-guard-nested-parse-error/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-nested-parse-error/**` covers `test-docs/codex-guard-nested-parse-error/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-nested-parse-error/` directory at all; the declared
`test-docs/codex-guard-nested-parse-error/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS-1: 再現手順の deny - `CASES` の deny ケース（FR3 a）を両コピーで実行する（FR1, FR3, FR5, AC1）
- [ ] TS-2: 0 段目の巨大な数字の deny - `CASES` の deny ケース（FR3 b）（FR1, FR3, FR5, AC2）
- [ ] TS-3: 1 段目の巨大な数字の deny - `CASES` の deny ケース（FR7 の 1 段目版）（FR7, AC2）
- [ ] TS-4: 全ゼロの複数桁 fd - `CASES` の silent ケース `'python3 00< f'`（FR1, FR7, AC3）
- [ ] TS-5: int の範囲の境界 - `CASES` の silent `'python3 2147483648>/dev/null'` と deny `'python3 2147483647>/dev/null'`（FR5, FR7, AC3）
- [ ] TS-6: 想定外の例外の読み飛ばし - `_scan` の `parse(inner)` を囲む try の例外処理が `Exception` を捕まえ、走査を続けることを AST の静的検査で確かめる。FR5 の後は、この経路に届く入力が見つかっていないため（FR2, AC4）
- [ ] TS-7: docstring 手順 7 - `TestGuardDocumentation.DOCSTRING_MARKERS` に足した文が、両コピーの module docstring に含まれる（FR6, AC5）
- [ ] TS-8: スイート全体・コピー同一・静的制約 - `python3 -m unittest discover -s tests`（`TestCasesTable` / `TestCopies` / `TestStaticConstraints` / `TestNoRecursion` を含む）と `python3 em-workflow/scripts/check-plugin-invariants.py .`（FR4, NFR1, NFR2, NFR3, NFR5, AC6）
- [ ] TS-9: version 据え置き - base_commit からの `git diff` で `plugin.json` と `marketplace.json` の version に変更がないことを確かめる（NFR4, AC7）

### Integration Tests

該当なし。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 全ゼロの複数桁 fd（`'python3 00< f'`）: 標準入力の接続とみなし、silent（TS-4）
- [ ] int の範囲の境界（`2147483647` / `2147483648`）: 前者は fd として読み deny、後者は普通の語として読み silent（TS-5）
- [ ] 数千桁の数字（0 段目・1 段目・2 段目）: 例外を出さず、後続の `python3 -i` を deny（TS-1, TS-2, TS-3）

### Performance Tests

該当なし。

## Security Considerations

- **Input Validation:** 入れ子の文字列の parse で想定外の例外が出ても、ガード全体を無出力にせず、その文字列を読み飛ばして後続のコマンドの判定を続ける（FR2）。リダイレクト直前の数字列はどんな桁数でも例外を出さない（FR1）。
- **誤拒否と通過:** 想定外のエラーは読み飛ばし（通過）に倒す。拒否には倒さない（NFR5）。
- **副作用:** ファイル・ネットワーク・子プロセスに触れない（NFR1）。

## Error Handling

| 発生箇所 | 例外 | 扱い |
|----------|------|------|
| 0 段目の `parse(command)` | すべて | 無出力のまま（手順 9。変更なし） |
| `_scan` の `parse(inner)` | `_Undecidable` | その文字列を読み飛ばし、それを持つコマンドの次から走査を続ける（変更なし） |
| `_scan` の `parse(inner)` | `_Undecidable` 以外の `Exception` | その文字列を読み飛ばし、それを持つコマンドの次から走査を続ける。拒否の理由にはしない（FR2） |
| `_judge` | — | 変更なし |

## Performance Optimization

該当なし。

## Success Criteria

- [ ] AC1〜AC7 を満たす
- [ ] TS-1〜TS-9 が通る

## Open Questions

なし。

## Assumptions

- A1: リダイレクト演算子の直前にある数字だけの語は、値が 2147483647 以下のときだけ fd になり、それより大きい値は普通の語になる（bash の読み方）。
- A2: 全ゼロの数字列は桁数を問わず fd 0 とみなす。
- A3: 読み飛ばしの対象は、`_scan` で 1 段目以降の文字列に対して呼ぶ `parse(inner)` だけ。0 段目の `parse(command)` で出た例外は無出力のまま（手順 9）。`_judge` の例外処理は変えない。
- A4: `'python3 2147483647>/dev/null'` は bash では fd エラーで実行されない。それでもガードの規則（fd として読み、オペランドなし、標準入力は未接続）では deny になる。これを期待どおりの判定として固定する。
- A5: docstring の手順 6 には、int の範囲を超える数字列の読み方を書き足さない。
- A6: task_description の「追加指示（起動時）」にある push・PR 作成・Codex への相談・Notion への記録は、実行の手順として扱い、コードの要件には含めない。

## References

- 要件定義書: `feature-docs/codex-guard-nested-parse-error/REQUIREMENTS.md`
