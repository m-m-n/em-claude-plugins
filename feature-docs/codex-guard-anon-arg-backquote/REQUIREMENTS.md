---
title: "codex-guard-anon-arg-backquote"
created_date: 2026-10-17
status: draft
---

# codex-guard-anon-arg-backquote - 要件定義書

## 1. 概要

### 1.1 背景

`codex-hook-interactive-guard.py`（em-workflow / em-review の両コピー）は、zsh 匿名関数の引数中の `(`〜`)` 範囲にバッククォートがあると、範囲の終端をバッククォート内の `)` と誤認する。残ったバッククォートが未閉鎖と判定され、`-c` 文字列全体が判定不能（出力なし）になり、匿名関数本体の明示的な `python3 -i` の deny が外れる。

feature `codex-guard-anon-stdin-args`（引数中の `(`〜`)` を 1 語として読む変更）で入った後退で、変更前は deny だった。review round 1 の指摘（stable_id `1241d15972c80d75`、severity medium、category security）。見逃し側（fail-open）で、THREAT-MODEL の TB-1/TM-2（明示的な `-i` は拒否する）を満たさない。

再現するコマンド:

```
zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'
```

### 1.2 目的

- 匿名関数の引数中の `(`〜`)` 範囲にバッククォートがあっても、本体の明示的な `python3 -i` を deny する（TB-1/TM-2 の回帰を直す）
- 再発を `CASES` で検出できるようにする

### 1.3 スコープ

- 対象: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` の `_scan_parens` / `_read_argument_parens` まわりの判定と docstring、`tests/test_codex_hook_interactive_guard.py`
- 対象外: `_skip_parens`（`$(` とプロセス置換）の戻り値と挙動、`_scan_parens` の `)` の終端判定、`paren_budget` への課金、plugin.json / marketplace.json の version

## 2. ビジネス要件

### 2.1 ビジネス目標

- 匿名関数の引数中の `(`〜`)` 範囲にバッククォートがあっても、本体の明示的な `python3 -i` を deny する（TB-1/TM-2 の回帰を直す）
- 再発を `CASES` で検出できるようにする

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow / em-review の利用者 | Codex のフック経由で `codex-hook-interactive-guard.py` の判定を受ける |

### 2.3 期待される効果

- 引数中の `(`〜`)` 範囲にバッククォートを含む形でも、本体の明示的な `python3 -i` が deny される
- 同じ後退が `CASES` で検出される

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 引数にバッククォートを含む匿名関数のコマンドを判定する | フック（標準入力で `tool_input.command` を受け取る） | 高 |

### 3.2 ユースケース詳細

#### UC01: 引数にバッククォートを含む匿名関数のコマンドを判定する

**アクター**: フック

**事前条件**:
- `tool_input.command` に zsh 匿名関数を含む `-c` 文字列を設定した JSON が標準入力に渡される

**基本フロー**:
1. `_read_argument_parens` が匿名関数の引数中の `(`（語中 `foo(` と語頭 `(`）を読む
2. `_scan_parens` が `(` から終端の `)` までを走査する
3. 範囲内に契機となるバッククォートがあれば、範囲を語として読まず `(` で群を開く（仮に開いた群）
4. 既存の仮の群・救済・接続の規則で判定し、本体の `python3 -i` を deny する

**代替フロー**:
- 契機となるバッククォートが無い範囲は従来どおり 1 語として読む
- 群の読みに戻った後にバッククォートが閉じない形は判定不能（出力なし）

**事後条件**:
- 本体に明示的な `python3 -i` がある形は deny を出力する

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 引用されていないバッククォートで群の読みに戻す | 範囲内の引用されていないバッククォートで `(` を群として開く | 高 |
| FR2 | 二重引用符内のバッククォートも契機にする | 二重引用符内（バックスラッシュの後でない）のバッククォートも FR1 と同じ契機にする | 高 |
| FR3 | 単一引用符内とバックスラッシュの後のバッククォートは契機にしない | 該当する範囲は従来どおり 1 語として読む | 高 |
| FR4 | 平衡したバッククォートも契機にする（既知の誤拒否） | 平衡の有無を問わず契機にする | 高 |
| FR5 | 終端判定・作業上限・既存の契機と救済を変えない | 既存の挙動を保つ | 高 |
| FR6 | 閉じないバッククォートは判定不能 | 既存の引用符の不平衡の規則どおり出力なし | 高 |
| FR7 | docstring の更新 | 両コピーの docstring にバッククォートの規則を書く | 中 |
| FR8 | 2 つのコピーを同時に直す | バイト単位で同一に保つ | 高 |
| FR9 | 再発を検出するテスト | `CASES` に再現手順と FR2〜FR6 のケースを足す | 高 |

### 4.2 機能詳細

#### FR1: 引用されていないバッククォートで群の読みに戻す

**説明**: `_read_argument_parens` が読む匿名関数の引数中の `(`（語中 `foo(` と語頭 `(` の両方）について、`_scan_parens` が `(` から終端の `)` までの間で引用されていないバッククォートを読んだときは、`;` `&` 改行を含む場合と同じく範囲を語として読まず、`(` で群を開く（仮に開いた群）。

**入力**:
- `tool_input.command`: 文字列 - 判定対象のコマンド

**出力**:
- `permissionDecision: deny`、または出力なし

**ビジネスルール**:
- 次のコマンドは deny になる。

```
zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'
```

#### FR2: 二重引用符内のバッククォートも契機にする

**説明**: 範囲の走査が二重引用符の中で（バックスラッシュの後でない）バッククォートを読んだときも FR1 と同じく群の読みに戻す。

**ビジネスルール**:
- 次のコマンドは deny になる。

```
zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo "x)"`")'
```

#### FR3: 単一引用符内とバックスラッシュの後のバッククォートは契機にしない

**説明**: 単一引用符内のバッククォート、引用符の外のバックスラッシュの後のバッククォート、二重引用符内のバックスラッシュの後のバッククォートは契機にせず、範囲は従来どおり 1 語として読む。

**ビジネスルール**:
- 次の形は silent のまま。
    - ``function { python3; } foo("\`x\`") < /dev/null``
    - ``function { python3; } foo(\`x\`) < /dev/null``
    - ``function { python3; } foo('`x`') < /dev/null``

#### FR4: 平衡したバッククォートも契機にする（既知の誤拒否）

**説明**: 範囲内のバッククォートが平衡しているか（`` foo(`echo x`) ``）を問わず、FR1・FR2 の契機があれば群の読みに戻す。

**ビジネスルール**:
- 次のコマンドは deny になる。zsh ではこの形の本体の標準入力は /dev/null になるため、これは既知の誤拒否（fail-closed 側）とする。

```
zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x`) < /dev/null'
```

- ``function { python3; } foo("`echo x`") < /dev/null`` も同じく deny になる。

#### FR5: 終端判定・作業上限・既存の契機と救済を変えない

**説明**: `_scan_parens` の `)` の終端判定（バックスラッシュの組・単一引用符・二重引用符だけを読み飛ばす）と、`_read_argument_parens` の `paren_budget` への課金は変えない。`_skip_parens`（`$(` とプロセス置換）の戻り値と挙動は変えない。`;` `&` 改行の契機、仮に開いた群の救済の規則、群の接続の確定は既存のまま適用する。

#### FR6: 閉じないバッククォートは判定不能

**説明**: 群の読みに戻った後にバッククォートが閉じない形（`` foo(`echo x) ``、`` foo("`echo x") ``）は、既存の引用符の不平衡の規則どおり判定不能（出力なし）とする。

#### FR7: docstring の更新

**説明**: 両コピーのモジュール docstring 手順 4（``The matching `)` is found by ...`` の段落）、`_Parser` の docstring、`_scan_parens` の docstring（返り値の意味）、`_read_argument_parens` の docstring に、範囲内の引用されていないバッククォートと二重引用符内のバッククォートで群の読みに戻ることを書く。

**ビジネスルール**:
- 既存の docstring テストのマーカー（``holds an unquoted `;`, `&` or newline, the `(` opens a group``、`a backquote and a comment get no special reading`）は残すか、文言を変える場合はテストのマーカーを同じ変更で揃える。
- バッククォートの規則のマーカーを docstring テストに足す。

#### FR8: 2 つのコピーを同時に直す

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。

#### FR9: 再発を検出するテスト

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` に再現手順のコマンドを deny として追加し、FR2〜FR6 を固定するケースを足す。既存の deny ケースは消さない。表は両コピーに流す。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1（線形時間）: 解析全体を文字列長に対して線形時間に保つ。契機の判定は走査 1 文字あたり定数の追加作業とし、再帰は使わない（既存の性能テスト・再帰検査テストを通す）。

### 5.2 セキュリティ要件

- 入力検証: 本体の明示的な `python3 -i` は、引数中の `(`〜`)` 範囲にバッククォートがあっても deny する（FR1、FR2、FR4）。

### 5.3 可用性要件

- 該当なし

### 5.4 保守性要件

- NFR2（既存の制約の維持）: 標準ライブラリのみ、ファイル・ネットワーク・子プロセスに触れない、判定はコマンド文字列だけで決まる、という既存の制約とその検査テストを保つ。
- ドキュメント: FR7 のとおり両コピーの docstring を更新する。

### 5.5 互換性要件

- NFR3（version を変えない）: plugin.json と marketplace.json の version は変えない。

## 6. UI/UX要件

該当なし（UI の無いフック判定ロジックの修正。design step は省略）。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 標準ライブラリのみを使う（NFR2）
- 解析は線形時間で、再帰を使わない（NFR1）
- 2 つのコピーをバイト単位で同一に保つ（FR8）

### 9.2 ビジネス上の制約

- plugin.json と marketplace.json の version は変えない（NFR3）

### 9.3 スケジュール制約

- なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-anon-arg-backquote/**`
- `test-docs/codex-guard-anon-arg-backquote/**`

`feature-docs/codex-guard-anon-arg-backquote/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-anon-arg-backquote/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-anon-arg-backquote/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-anon-arg-backquote/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-anon-arg-backquote/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 平衡したバッククォートの範囲の後に入力リダイレクトがある形（`` function { python3; } foo(`echo x`) < /dev/null ``）が deny になる（既知の誤拒否、fail-closed 側） | 低 | 決定済みの既知の誤拒否として受け入れ、SPEC に明記する（FR4） |

### 10.2 ビジネスリスク

- なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1, FR9）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'`` を両コピーに渡すと deny を出力する
- [ ] AC-2（FR2, FR9）: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo "x)"`")'`` を両コピーに渡すと deny を出力する
- [ ] AC-3（FR3, FR9）: 単一引用符内・バックスラッシュの後のバッククォートだけを含む範囲の後に `< /dev/null` がある形（本体 `python3`）は何も出力しない
- [ ] AC-4（FR4, FR9）: ``function { python3; } foo(`echo x`) < /dev/null`` と ``function { python3; } foo("`echo x`") < /dev/null`` は deny を出力し、SPEC に既知の誤拒否として記載されている
- [ ] AC-5（FR6, FR9）: ``function { python3 -i; } foo(`echo x)`` と ``function { python3 -i; } foo("`echo x")`` は何も出力しない
- [ ] AC-6（FR5）: 既存の `CASES`（`foo(x) < /dev/null` の silent、`;` `&` 改行の deny、救済のケース、`$(` を含むケースを含む）が変更なしで通る
- [ ] AC-7（FR7）: 両コピーの docstring がバッククォートの規則を述べ、docstring テストが通る
- [ ] AC-8（FR8）: 2 つのコピーがバイト単位で同一であることを確かめる既存テストが通る
- [ ] AC-9（NFR1）: 性能テスト・再帰検査テストが両コピーで通る
- [ ] AC-10（FR9, NFR2）: `python3 -m unittest tests.test_codex_hook_interactive_guard` と `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: TS1（再現手順）、TS2（二重引用符内のバッククォート）、TS3・TS4（平衡したバッククォート）が deny
- [ ] 異常系: TS8・TS9（閉じないバッククォート）が silent
- [ ] 境界値: TS5〜TS7（エスケープまたは単一引用符内のバッククォート）が silent のまま。終端の `)` より後のバッククォートは契機にならない
- [ ] セキュリティ: 本体の明示的な `python3 -i` の deny が外れない（TS1、TS2）。既存の deny ケースを消さない（TS10）
- [ ] パフォーマンス: TS12（``"function { :; } x(`:` " * depth + ")" * depth`` の形を性能テストに足す）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 範囲 | `_scan_parens` が読む、匿名関数の引数中の `(` から終端の `)` まで |
| 群の読み | 範囲を語として読まず、`(` で群を開く読み方（仮に開いた群） |
| 契機 | 範囲を語として読まず群の読みに戻す条件。既存の `;` `&` 改行に、本フィーチャーでバッククォートを足す |
| 既知の誤拒否 | 実際には対話にならない形を deny する判定。fail-closed 側 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 二重引用符内のバッククォートを契機にするか: 範囲の走査が二重引用符の中でバッククォートに出会ったときも、引用されていないバッククォートと同じく `(` で群を開く。単一引用符内とバックスラッシュの後のバッククォートは契機にしない。`CASES` に二重引用符内の形の deny を足す。
- [x] 平衡したバッククォートを契機にするか: 平衡したバッククォート（`` foo(`echo x`) ``）も含め、範囲内に契機となるバッククォートがあれば群の読みに戻す。その結果 ``function { python3; } foo(`echo x`) < /dev/null`` は deny になる。zsh では本体の標準入力が /dev/null になるため、これは既知の誤拒否（fail-closed 側）として SPEC に明記する。`_skip_parens` の終端判定と `paren_budget` の課金は変えない。
- [x] design step: 省略する（UI の無いフック判定ロジックの修正、デザインシステム候補ゼロ）。

前提（requirements-analyst の仮定）:

- [x] A1: 契機の判定対象は、`_scan_parens` が `(` から終端の `)` までに読んだ文字に限る。`)` より後のバッククォートは対象外とする。
- [x] A2: 群の読みに戻った後は、既存の仮の群・救済・接続の規則をそのまま適用する（新しい読みは足さない）。
- [x] A3: 範囲内の `$(` の中にある引用されていないバッククォートも契機とする（fail-closed 側）。
- [x] A4: 閉じないバッククォートの形（TS8, TS9）の本体は、既存ケース「引数の閉じていない ( は判定不能」にならって `python3 -i` とする。zsh でも構文エラーで何も実行されないため、判定不能（silent）を期待値とする。
- [x] A5: 契機を `separated` に含めるか別の返り値にするかは計画に委ねる。`_skip_parens` の戻り値は変えない。
- [x] A6: ``function { python3; } foo(`echo x`) < /dev/null`` の deny は、決定済みの既知の誤拒否として受け入れる。
- [x] A7: LICENSE ファイルは無く、ライセンスは未検出として扱う。
- [x] A8: version は変えない（core-plugin-version-bump ルール）。

### 14.2 未確認・保留事項

- なし

## 15. 参考資料

- `em-workflow/scripts/codex-hook-interactive-guard.py`: `_scan_parens`、`_read_argument_parens`
- `em-review/scripts/codex-hook-interactive-guard.py`: 同一内容のコピー
- `tests/test_codex_hook_interactive_guard.py`: `CASES`、docstring テスト、性能テスト、バイト同一テスト
- `feature-docs/codex-guard-anon-stdin-args/reviews/round1.yaml`（ブランチ `em-workflow/codex-guard-anon-stdin-args/integration`）: 指摘の記録
