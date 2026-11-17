---
title: "declared-command-edge-fold"
created_date: 2026-11-18
status: draft
---

# declared-command-edge-fold - 要件定義書

## 1. 概要

### 1.1 背景
workflow.yaml の `*_command` の引用符付きの値の端に U+0085 / U+2028 / U+2029 が混在または連続していると、その YAML 解析結果（PyYAML）が宣言集合の形と一致せず、bash_guard のフックが判定なしにする。上流に修正版はない。

### 1.2 目的
- workflow.yaml の `*_command` の引用符付きの値の端に、U+0085 / U+2028 / U+2029 が混在または連続していても、その YAML 解析結果（PyYAML）をコマンドとして渡されたら、bash_guard のフックは未承認として deny する。判定なしにはしない。
- 許可の範囲は広げない（TM-2 は維持）。
- 暫定の緩和策、広がった拒否の範囲、残る対象外の範囲を文書に書き残す。

### 1.3 スコープ
- `em-workflow/hooks/bash_guard.py` の `hook_main` の照合（FR1〜FR3）
- 回帰テストの追加と、既存テスト 1 件の期待値の変更（FR4）
- 他の feature の文書 4 か所への追記と、`bash_guard.py` の docstring・コメントの更新（FR5）

対象外は 14.2 と A3 に記載する。

## 2. ビジネス要件

### 2.1 ビジネス目標
- workflow.yaml の `*_command` の引用符付きの値の端に、U+0085 / U+2028 / U+2029 が混在または連続していても、その YAML 解析結果（PyYAML）をコマンドとして渡されたら、bash_guard のフックは未承認として deny する。判定なしにはしない。
- 許可の範囲は広げない（TM-2 は維持）。
- 上流に修正版がないので、暫定の緩和策、広がった拒否の範囲、残る対象外の範囲を文書に書き残す。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 端に U+0085 / U+2028 / U+2029 が混在または連続した宣言の YAML 解析結果が、判定なしではなく未承認として deny される。
- 許可（allow）が出る範囲は変わらない。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | hook_main で、両端から 6 文字を除いた形も宣言集合と照合する | 宣言集合と照合する 3 か所で、両端から 6 文字を除いた形も照合する | 高 |
| FR2 | declared_commands と許可の範囲を変えない | 宣言集合の形と、許可・記録まわりの挙動を変えない | 高 |
| FR3 | 広がった拒否の範囲 | 宣言済みの値の端を 6 文字で埋めたコマンドは、承認済みの値でも未承認として deny される | 中 |
| FR4 | 回帰テスト | 新しいテストファイルの追加と、既存テスト 1 件の期待値の変更 | 高 |
| FR5 | 文書への追記 | 他の feature の文書 4 か所への追記と、bash_guard.py の docstring・コメントの更新 | 中 |

### 4.2 機能詳細

#### FR1: hook_main で、両端から 6 文字を除いた形も宣言集合と照合する

**説明**: `em-workflow/hooks/bash_guard.py` の `hook_main` では、宣言集合と照合する 3 か所のすべてで、今の照合（`trim_blanks` した command が `declared` にあるか）に加えて、もう 1 つの形も照合する。

照合する 3 か所:
1. 受け取ったコマンドが宣言されておらず、承認ストアのファイルもないときの早期 return
2. ワークフローに関係するかどうかの判定
3. 未承認の deny

**ビジネスルール**:
- 追加で照合する形は、受け取ったコマンドの両端から U+0020・U+0009・LF（U+000A）・U+0085・U+2028・U+2029 を除いたもの。これが `declared` にあれば「宣言済み」とする。
- 両端を除いた形が空なら、宣言済みとはしない。
- この 6 文字以外（U+00A0、CR、U+000B、U+000C、U+2000〜U+200A、U+3000 など）は除かない。
- 受け取ったコマンド自体は書き換えない。`refusal_reason`、exact、cd 前置形の判定は、これまでどおり `trim_blanks` した command に当てる。
- 判定順序（禁止パターン -> exact -> cd 前置形 -> 宣言済みかつ未承認の deny -> 判定なし）は変えない。

#### FR2: declared_commands と許可の範囲を変えない

**説明**: `declared_commands` が入れる 2 つの形（`trim_blanks(value)` と `value.strip(DECLARED_END_STRIP)`）と、`DECLARED_END_STRIP` は変えない。

**ビジネスルール**:
- 次の挙動を変えない: `trim_blanks`、`is_matchable`、`approved_for`、exact と cd 前置形による許可、`cd_prefix_allowed` / `is_cd_prefixed_approved`、`read_stdin_commands`、`--record` / `--remove` / `--list`、`refusal_reason`。
- FR1 の照合から許可が出ることはない。

#### FR3: 広がった拒否の範囲

**説明**: FR1 によって、宣言済みの値の端に FR1 の 6 文字（スペース・タブ以外の LF / U+0085 / U+2028 / U+2029 を含む）を付けたコマンドは、その値が承認済みであっても、判定なしではなく未承認として deny される。

**ビジネスルール**:
- 例: `/usr/bin/true` が宣言済みかつ承認済みのとき、`'/usr/bin/true'` + LF は deny。
- 宣言のないリポジトリでは、同じ形はこれまでどおり判定なしになる。
- deny の理由の文言と additionalContext は変えない。

#### FR4: 回帰テスト

**説明**: フックをサブプロセスとして動かすテストを新しいファイルに足す。

**ビジネスルール**:
- 宣言は、二重引用符とシングルクォートの両方で、生の文字で書く。
- YAML 解析結果の形はテストのソースにリテラルで書き、PyYAML は import しない。
- 確かめるのは次のとおり。
    1. 先頭 U+0085 + 末尾 U+2028 / U+2029 と、その逆（先頭 U+2028 / U+2029 + 末尾 U+0085）。
    2. 同じ端での U+0085 U+0085（-> LF）、U+0085 U+2028（-> U+2028）、U+2028 U+0085（-> U+2028 LF）を、先頭と末尾のそれぞれに置いた宣言。
    - (1)(2) の YAML 解析結果の形が、理由に「未承認」を含めて deny されること。宣言のないリポジトリでは判定なしのままであること。
    - allow が出ないこと。承認済みの `/usr/bin/true` が完全一致で allow されること。
- 既存の `tests/test_bash_guard_declared_yaml_breaks.py` の `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` は、FR1 の 6 文字のどれかで両端を埋めた形だけを deny の期待に変える。U+00A0 で埋めた形は判定なしの期待を保つ。
- 既存の deny のケースは消さない。

#### FR5: 文書への追記

**説明**: 次の 4 か所に追記する。追記だけにして、既存の文は書き換えない。
- approval-unicode-whitespace の SPEC.md FR8 と THREAT-MODEL.md TM-5
- declared-command-yaml-breaks の SPEC.md FR1 と THREAT-MODEL.md TM-1

**ビジネスルール**:
- 追記する内容は 3 点。
    1. `hook_main` が、両端から 6 文字を除いた形も宣言集合と照合すること。
    2. FR3 の、広がった拒否の範囲（承認済みの値でも、端を改行文字で埋めると未承認として deny されること）。
    3. 対象外の範囲。改行文字だけの宣言（両端を除くと空になる値）の解析結果、YAML のエスケープ表記、ブロックスカラー、値の内側の文字による食い違いは対象外で、通常の権限確認に回ること。
- `bash_guard.py` のモジュール docstring（Matching の段落と判定表の declared 行）と `hook_main` まわりのコメントも、FR1 に合わせて更新する。
- `feature-docs/*/reviews/round1.yaml` と `em-workflow/references/command-execution-protocol.md` は変えない。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- 許可の範囲は広げない（TM-2 は維持）。FR1 の照合から許可が出ることはない（FR2）。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1 - 依存: `bash_guard.py` は標準ライブラリのモジュールだけを import する（`test_ac7_the_hook_imports_only_standard_library_modules`、`test_ac6_guard_imports_only_standard_library_modules`）。
- NFR2 - classification pin: `bash_guard.py` の実行されるテキストには、新しい定数名・コメント・docstring を含めて、部分文字列 `'status'` を入れない（`tests/test_hook_classification_pin.py` ほか）。
- NFR3 - 関数の並び: `strip_yaml_quotes`、`trim_blanks`、`is_matchable`、`declared_commands` の 4 つは、この順で連続して並び、それぞれ 1 回だけ定義されるままにする。FR1 は `hook_main` の中に書くか、モジュールレベルの定数を足して実現し、この並びの間に関数を足さない。
- NFR4 - ソースの文字: `bash_guard.py` のソースには、U+0085 / U+2028 / U+2029 をエスケープで書き、生の文字を入れない（`test_ac7_the_hook_source_has_no_raw_next_line_or_separator_character`）。
- NFR5 - docstring: モジュール docstring の固定された文言（`'after removing surrounding spaces and tabs only'`、`'any other whitespace at either end is never allowed'`、cd 前置形の approval 項目）を残す。
- NFR6 - テスト: Python 3.14 標準ライブラリの unittest だけを使い、PyYAML は import しない。ストアは `EM_WORKFLOW_APPROVALS` で切り離し、フックの環境から `CLAUDE_PROJECT_DIR` を外し、一時ディレクトリの git リポジトリを使う。テストのソースは ASCII だけにして、非 ASCII 文字はエスケープで書く。
- NFR7 - Version: version は変えない。

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- NFR1〜NFR6 に従う。
- `declared_commands` の 2 つの形と `DECLARED_END_STRIP` は変えない（FR2）。

### 9.2 ビジネス上の制約
- version は変えない（NFR7）。
- 他の feature の文書には追記だけをする。`round1.yaml` と `command-execution-protocol.md` は変えない（FR5、A5）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/declared-command-edge-fold/**`
- `test-docs/declared-command-edge-fold/**`

`feature-docs/declared-command-edge-fold/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/declared-command-edge-fold/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/declared-command-edge-fold/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/declared-command-edge-fold/` ディレクトリを生成しないが、宣言された `test-docs/declared-command-edge-fold/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 拒否の範囲が広がり、宣言済みの値の端を改行文字で埋めたコマンドは、承認済みの値でも未承認として deny される（A2） | 中 | 受け入れ、文書に明記する（FR3、FR5） |
| 改行文字だけの宣言の解析結果、YAML のエスケープ表記、ブロックスカラー、複数行の値、値の内側の文字による食い違い、CR は対象外（A3） | 低 | 通常の権限確認に回り、FR5 で文書に残す |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1 (FR1, FR4): `build_command` が `"<U+0085>./unapproved<U+2028>"` で、承認ストアには `/usr/bin/true` だけがあるとき、`' ./unapproved<U+2028>'`（YAML 解析結果）が、理由に「未承認」を含めて deny される。末尾が U+2029 の宣言なら `' ./unapproved<U+2029>'` も同じ。生の形と、両端を除いた形 `'./unapproved'` も deny される。
- [ ] AC2 (FR1, FR4): その逆。`"<U+2028>./unapproved<U+0085>"` と `"<U+2029>./unapproved<U+0085>"` の YAML 解析結果（`'<U+2028>./unapproved '`、`'<U+2029>./unapproved '`）が、未承認として deny される。
- [ ] AC3 (FR1, FR4): 同じ端の連続。`"<U+0085><U+0085>./unapproved"` -> LF + `'./unapproved'`、`"./unapproved<U+0085><U+0085>"` -> `'./unapproved'` + LF、`"<U+0085><U+2028>./unapproved"` -> `'<U+2028>./unapproved'`、`"./unapproved<U+0085><U+2028>"` -> `'./unapproved<U+2028>'`、`"<U+2028><U+0085>./unapproved"` -> `'<U+2028>'` + LF + `'./unapproved'`。どれも未承認として deny される。
- [ ] AC4 (FR1, FR4): AC1〜AC3 の宣言をシングルクォートで書いた場合も、同じ YAML 解析結果の形が deny される。
- [ ] AC5 (FR1, FR2, FR4): AC1〜AC4 の形は、宣言のないリポジトリでは判定なしになる。宣言があってもなくても allow は出ない。`/usr/bin/true` そのものは、これまでどおり完全一致で allow される。U+00A0 で端を埋めた `'./unapproved'` は、宣言のあるリポジトリでも判定なしのまま。
- [ ] AC6 (FR3): `/usr/bin/true` が宣言済みかつ承認済みのリポジトリでは、`'/usr/bin/true'` + LF、`'<U+0085>/usr/bin/true'`、`'/usr/bin/true<U+2028>'` が未承認として deny される。宣言のないリポジトリでは、どれも判定なしになる。
- [ ] AC7 (FR2): `declared_commands` が返す集合は変わらない。`tests/test_bash_guard_declared_yaml_breaks.py` の AC-4 / AC-5 の集合比較のテストは、変更しないままで通る。
- [ ] AC8 (FR4): `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` は、U+0020 / U+0009 / U+0085 / U+2028 / U+2029 で埋めた形を deny と期待し、U+00A0 で埋めた形を silent と期待する。allow が出ないことの確認は残る。
- [ ] AC9 (FR5): FR5 の 4 文書に 3 点が追記されている。既存の文、`round1.yaml`、`command-execution-protocol.md` は変わっていない。
- [ ] AC10 (NFR1〜NFR7): `python3 -m unittest discover -s tests` が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: `declared_commands` を直接呼び、宣言集合が変わらないことを確かめる（既存の AC-4 / AC-5 の集合比較のテストをそのまま通す）。モジュールは、既存の `_load_guard_module` と同じ方法で、バイトコードを書かずに読み込む（TS1）。
- [ ] 正常系: 新しいファイル（例: `tests/test_bash_guard_declared_edge_fold.py`）を作り、独自の fixture を持たせる。fixture は、ケースごとに宣言を 1 つだけ持つ一時 git リポジトリと、宣言のないリポジトリで、ストアには `/usr/bin/true` だけを入れる。宣言（二重引用符 / シングルクォート）× YAML 解析結果の形について、フックのサブプロセスで deny を確かめ、宣言なしでは silent になることも確かめる。allow が出ないことも確かめる（TS2）。
- [ ] 正常系: `/usr/bin/true` を宣言したリポジトリと、宣言のないリポジトリで、LF / U+0085 / U+2028 / U+2029 で端を埋めた `/usr/bin/true` が、それぞれ deny / silent になる（TS3）。
- [ ] 正常系: 既存の `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` の期待値を、FR1 の 6 文字による埋め方なら deny、U+00A0 なら silent に変える（TS4）。
- [ ] 正常系: `python3 -m unittest discover -s tests` でテスト一式を回す（TS5）。
- [ ] 境界値: 改行文字だけの宣言（例: `"<U+0085><U+2028><U+2029>"`）の解析結果は、両端を除くと空になる。宣言済みとはしないこと（判定なし）を確かめ、対象外として記録する（TS6）。
- [ ] 境界値: cd 前置形 `cd "<path>" && <値><U+2028>` は、両端を除いた後の文字列全体が宣言値と一致しないので、今の判定のまま変わらない（TS7）。
- [ ] 境界値: 承認ストアのファイルがなく、宣言だけがあるとき（早期 return の経路）でも、AC1 の YAML 解析結果の形が deny される（TS8）。
- [ ] セキュリティ: 宣言があってもなくても、FR1 の照合から allow は出ない（TS2、AC5）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| FR1 の 6 文字 | U+0020・U+0009・LF（U+000A）・U+0085・U+2028・U+2029 |
| 判定なし | フックが allow / deny のどちらも出さず、通常の権限確認に回ること（テストでの期待値は silent） |
| YAML 解析結果 | workflow.yaml の値を PyYAML で解析した結果の文字列 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 緩和策の方式: 案 1（`hook_main` 側で、両端から 6 文字を除いた形も照合する）を採る。`declared_commands` の 2 つの形は変えない（A1、mitigation.edge-fold.approach への回答 hook_side_end_strip）。
- [x] 広がる拒否の範囲: 宣言済みの値の端を改行文字で埋めたコマンドは、承認済みの値でも未承認として deny される。これは受け入れ、文書に明記する（A2、mitigation.edge-fold.approach への回答）。
- [x] 対象外: 改行文字だけの宣言の解析結果、YAML のエスケープ表記（`\N`、` `、二重引用符の中のエスケープした改行）、ブロックスカラー、複数行の値、値の内側の文字による食い違い、CR、`merge-preflight.py`、承認ゲートの手順。どれも通常の権限確認に回り、FR5 で文書に残す（A3）。
- [x] 許可が出るのは exact と `cd_prefix_allowed` の 2 つだけで、どちらも `declared` を参照しない。FR1 で変わるのは deny と判定なしの境目だけになる（TM-2 は維持）（A4）。
- [x] 他の feature の文書（approval-unicode-whitespace と declared-command-yaml-breaks の SPEC / THREAT-MODEL）には追記だけをする。`round1.yaml` と `command-execution-protocol.md` は変えない（A5）。
- [x] version は変えない（A6）。
- [x] デザインステップ: skip（design.step.recommendation への回答 decide_autonomously）。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- approval-unicode-whitespace の SPEC.md（FR8）と THREAT-MODEL.md（TM-5）
- declared-command-yaml-breaks の SPEC.md（FR1、A5）と THREAT-MODEL.md（TM-1、TM-2）
