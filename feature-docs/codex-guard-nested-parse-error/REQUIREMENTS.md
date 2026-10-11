---
title: "codex-guard-nested-parse-error"
created_date: 2026-10-11
status: draft
---

# codex-guard-nested-parse-error - 要件定義書

## 1. 概要

### 1.1 背景

review round 1 の deferred 指摘 815e62007171d07b（security / medium）への対応。

- 入れ子の `bash -c` 文字列の parse で例外が出ると、ガード全体が無出力になる。
- リダイレクトの直前に数千桁の数字があると、後続の対話起動を見逃す。

### 1.2 目的

- 入れ子の `bash -c` 文字列の parse で例外が出ても、ガード全体が無出力にならず、後続のコマンドの判定を続けるようにする。
- 数千桁の数字がリダイレクトの直前にあっても、後続の対話起動を見逃さないようにする（0 段目・1 段目・2 段目以降のどれでも）。

### 1.3 スコープ

対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`

対象外:

- 0 段目の `parse(command)` で出た例外の扱い（無出力のまま。手順 9）
- `_judge` の例外処理
- module docstring の手順 6
- push・PR 作成・Codex への相談・Notion への記録（実行の手順として扱う）
- `<plugin>/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version

## 2. ビジネス要件

### 2.1 ビジネス目標

- 入れ子の `bash -c` 文字列の parse で例外が出ても、ガード全体が無出力にならず、後続のコマンドの判定を続ける。
- 数千桁の数字がリダイレクトの直前にあっても、後続の対話起動を見逃さない（0 段目・1 段目・2 段目以降のどれでも）。

### 2.2 対象ユーザー

該当なし。

### 2.3 期待される効果

2.1 と同じ。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | fd を int 変換せずに読む |
| FR2 | 入れ子の文字列の想定外の例外を読み飛ばす |
| FR3 | 依頼された回帰ケース |
| FR4 | 2 つのコピーをバイト単位で同一に保つ |
| FR5 | int の範囲を超える数字列は普通の語として扱う |
| FR6 | docstring 手順 7 に書き足す |
| FR7 | 追加の回帰ケース |

### 4.2 機能詳細

#### FR1: fd を int 変換せずに読む

- `_Parser._redirection` は、リダイレクト演算子の直前にある、クォートのない数字だけの語を int に変換しない。
- 先頭の 0 を除いた桁数と文字列の比較だけで判定する。
- どんな桁数でも例外を出さない。
- 全ゼロの数字列（`0`、`00`、5000 個の `0` など）は fd 0、つまり標準入力の接続とみなす。

#### FR2: 入れ子の文字列の想定外の例外を読み飛ばす

- `_scan` の `parse(inner)` で `_Undecidable` 以外の例外（`Exception`）が出たときも、その文字列を読み飛ばし、それを持つコマンドの次から走査を続ける。
- 拒否の理由にはしない。
- 0 段目の `parse(command)` の扱いは変えない（無出力のまま）。
- 読み直し文字数の累計は、これまでどおり parse の前に加算する。

#### FR3: 依頼された回帰ケース

`tests/test_codex_hook_interactive_guard.py` の `CASES` に deny ケースを 2 つ足す。

- (a) 再現手順の入力: `': ' + '9'*5000 + '>/dev/null'` を `json.dumps` で 2 回 `'bash -c '` に包み、`'; python3 -i'` を続けたもの。
- (b) 0 段目の同じ形: `': ' + '9'*5000 + '>/dev/null; python3 -i'`。

#### FR4: 2 つのコピーをバイト単位で同一に保つ

`em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR5: int の範囲を超える数字列は普通の語として扱う

- FR1 の数字列は、先頭の 0 を除いた値が 2147483647 以下のときだけ fd として読む。
- 除いた後に 11 桁以上のもの、または 10 桁で文字列として `"2147483647"` より大きいものは fd ではない。
- その数字列は普通の語として残り、リダイレクトは演算子の既定の fd（`>` は標準出力、`<` は標準入力）にかかる。
- 2147483647 以下の値の数字列の判定は、修正前と変わらない。

#### FR6: docstring 手順 7 に書き足す

- module docstring の手順 7 で、読めない文字列の例として「読んでいる途中で想定外のエラーが出た文字列」を加える。
- その文を `TestGuardDocumentation.DOCSTRING_MARKERS` に足して固定する。
- 両コピーに同じ変更を入れる。

#### FR7: 追加の回帰ケース

`CASES` に次を足す。

- silent: `'python3 00< f'`（全ゼロの複数桁 fd は標準入力）
- deny: `"bash -c ': " + '9'*5000 + ">/dev/null'; python3 -i"`（1 段目の巨大な数字）
- silent: `'python3 2147483648>/dev/null'`（数字列が python3 のオペランドになる）
- deny: `'python3 2147483647>/dev/null'`（fd として読まれ、オペランドなしの起動になる）

## 5. 非機能要件

| ID | 要件名 | 内容 |
|----|--------|------|
| NFR1 | 標準ライブラリのみ・副作用なし | 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（`TestStaticConstraints`） |
| NFR2 | 再帰を入れない | 入れ子の走査は明示的な作業リストのまま。再帰呼び出しを足さない（`TestNoRecursion`） |
| NFR3 | テストスイートが通る | `python3 -m unittest tests.test_codex_hook_interactive_guard`、`python3 -m unittest discover -s tests`、`python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。`CASES` のコマンドは重複しない |
| NFR4 | version を変えない | `<plugin>/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は変えない |
| NFR5 | 誤拒否より通過を優先する | 想定外のエラーは読み飛ばし（通過）に倒す。拒否には倒さない |

## 6. UI/UX要件

該当なし（UI・画面を持たない）。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR1）。
- 入れ子の走査に再帰呼び出しを足さない（NFR2）。
- 2 つのコピーをバイト単位で同一に保つ（FR4）。

### 9.2 ビジネス上の制約

- version を変えない（NFR4）。

### 9.3 スケジュール制約

なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-nested-parse-error/**`
- `test-docs/codex-guard-nested-parse-error/**`

`feature-docs/codex-guard-nested-parse-error/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-nested-parse-error/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-nested-parse-error/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-nested-parse-error/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-nested-parse-error/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

- FR5 の後は、FR2 の経路（`_scan` の `parse(inner)` で想定外の例外が出る経路）に届く入力が見つかっていない。FR2 は AST の静的検査で確かめる（TS-6）。

### 10.2 ビジネスリスク

なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: 再現手順の入力をガードの `main` に渡すと、標準出力に deny が 1 つ出る（両コピー）（FR1, FR3, FR5）
- [ ] AC2: `': ' + '9'*5000 + '>/dev/null; python3 -i'` と、その 1 段目版が deny になる（FR1, FR3, FR5, FR7）
- [ ] AC3: `'python3 00< f'` と `'python3 2147483648>/dev/null'` は silent、`'python3 2147483647>/dev/null'` は deny（FR1, FR5, FR7）
- [ ] AC4: `_scan` で `parse(inner)` を囲む例外処理が、`_Undecidable` に加えて想定外の例外（`Exception`）も捕まえ、読み飛ばして走査を続ける（FR2）
- [ ] AC5: docstring の手順 7 が、想定外のエラーが出た文字列も読み飛ばすと述べ、そのマーカーがテストで固定されている（FR6）
- [ ] AC6: 既存の `CASES` の判定がすべて変わらない。2 つのコピーがバイト単位で同一。テストスイートと plugin invariants が通る（FR4, NFR1, NFR2, NFR3）
- [ ] AC7: version ファイルに差分がない（NFR4）

### 11.2 KPI

なし。

## 12. テストシナリオ

### 12.1 テスト観点

すべて自動テスト。

| ID | シナリオ | 方法 | 対象 |
|----|----------|------|------|
| TS-1 | 再現手順の deny | `CASES` の deny ケース（FR3 a）を両コピーで実行する | FR1, FR3, FR5, AC1 |
| TS-2 | 0 段目の巨大な数字の deny | `CASES` の deny ケース（FR3 b） | FR1, FR3, FR5, AC2 |
| TS-3 | 1 段目の巨大な数字の deny | `CASES` の deny ケース（FR7 の 1 段目版） | FR7, AC2 |
| TS-4 | 全ゼロの複数桁 fd | `CASES` の silent ケース `'python3 00< f'` | FR1, FR7, AC3 |
| TS-5 | int の範囲の境界 | `CASES` の silent `'python3 2147483648>/dev/null'` と deny `'python3 2147483647>/dev/null'` | FR5, FR7, AC3 |
| TS-6 | 想定外の例外の読み飛ばし | `_scan` の `parse(inner)` を囲む try の例外処理が `Exception` を捕まえ、走査を続けることを AST の静的検査で確かめる | FR2, AC4 |
| TS-7 | docstring 手順 7 | `TestGuardDocumentation.DOCSTRING_MARKERS` に足した文が、両コピーの module docstring に含まれる | FR6, AC5 |
| TS-8 | スイート全体・コピー同一・静的制約 | `python3 -m unittest discover -s tests`（`TestCasesTable` / `TestCopies` / `TestStaticConstraints` / `TestNoRecursion` を含む）と `python3 em-workflow/scripts/check-plugin-invariants.py .` | FR4, NFR1, NFR2, NFR3, NFR5, AC6 |
| TS-9 | version 据え置き | base_commit からの `git diff` で `plugin.json` と `marketplace.json` の version に変更がないことを確かめる | NFR4, AC7 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 0 段目 | ガードに渡されたコマンド文字列そのもの。`parse(command)` で読む |
| 1 段目以降 | 入れ子の文字列。`_scan` の `parse(inner)` で読む |
| deny | ガードが標準出力に拒否の判定を出すこと |
| silent | ガードが何も出力しないこと |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1（create-spec.req.huge-fd-reading）: リダイレクト演算子の直前にある数字だけの語は、値が 2147483647 以下のときだけ fd になり、それより大きい値は普通の語になる（bash の読み方）。
- [x] A2（create-spec.req.extra-tests）: 全ゼロの数字列は桁数を問わず fd 0 とみなす。
- [x] A3: 読み飛ばしの対象は、`_scan` で 1 段目以降の文字列に対して呼ぶ `parse(inner)` だけ。0 段目の `parse(command)` で出た例外は無出力のまま（手順 9）。`_judge` の例外処理は変えない。
- [x] A4（create-spec.req.extra-tests、create-spec.req.huge-fd-reading）: `'python3 2147483647>/dev/null'` は bash では fd エラーで実行されない。それでもガードの規則（fd として読み、オペランドなし、標準入力は未接続）では deny になる。これを期待どおりの判定として固定する。
- [x] A5（create-spec.req.docstring-step7）: docstring の手順 6 には、int の範囲を超える数字列の読み方を書き足さない。
- [x] A6: task_description の「追加指示（起動時）」にある push・PR 作成・Codex への相談・Notion への記録は、実行の手順として扱い、コードの要件には含めない。

### 14.2 未確認・保留事項

なし。
