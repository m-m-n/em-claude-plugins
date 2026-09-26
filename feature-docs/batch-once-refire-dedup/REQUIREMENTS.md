---
title: "batch-once-refire-dedup"
created_date: 2026-09-27
status: draft
---

# batch-once-refire-dedup - 要件定義書

## 1. 概要

### 1.1 背景
`--batch --once` は外部サービスから繰り返し発火される。同一タスクに対して重複 feature（重複 integration ブランチ）が作られない運用契約を、em-workflow 側の文書で明示する。

### 1.2 目的
- `--batch --once` を外部サービスから繰り返し発火させても、同一タスクに重複 feature（重複 integration ブランチ）が作られない運用契約を em-workflow 側の文書で明示し、テストで固定する。
- Step A の既存規定（パス引数なしは常に新規 feature、既存ブランチの列挙・推測はしない、再開は feature 名を明示する経路のみ）を維持する。

### 1.3 スコープ

**対象**:
- `em-workflow/references/batch-mode.md` の Non-packet gates 表「Step A feature resolution」行への再起動契約の明記
- `em-workflow/references/batch-terminal-line.md` の `## Field values` の `state` 項目（`phase_done` の説明）への再起動契約の明記
- `tests/` 配下への回帰テストの追加
- em-workflow プラグインの version 更新

**対象外**:
- `~/.claude/skills/notion-batch-develop/SKILL.md` の変更
- develop の feature 解決規則の変更（外部 ID による突き合わせ、既存ブランチの列挙）
- 重複 feature の検出・報告

## 2. ビジネス要件

### 2.1 ビジネス目標
- `--batch --once` を外部サービスから繰り返し発火させても、同一タスクに重複 feature（重複 integration ブランチ）が作られない運用契約を em-workflow 側の文書で明示し、テストで固定する。
- Step A の既存規定（パス引数なしは常に新規 feature、既存ブランチの列挙・推測はしない、再開は feature 名を明示する経路のみ）を維持する。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| 外部ディスパッチャ | `--batch --once` を外部から繰り返し発火させるサービス。feature 名を持ち回る |

### 2.3 期待される効果
- `--once` のフェーズ境界で終わった起動の続きを、結果の `feature` 値をパス引数に渡して再起動することで、同一タスクに重複 feature が作られない。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | `--once` フェーズ境界後の再起動 | 外部ディスパッチャ | 高 |

### 3.2 ユースケース詳細

#### UC01: `--once` フェーズ境界後の再起動

**アクター**: 外部ディスパッチャ

**事前条件**:
- `--batch --once` の起動がフェーズ境界で終わり、構造化結果の `state` が `phase_done` である。
- 結果の `feature` は Step A で確定した slug を持つ。

**基本フロー**:
1. 外部ディスパッチャが構造化結果の `feature` 値を受け取る。
2. 外部ディスパッチャが `feature` 値をパス引数として渡して再起動する。タスク記述は渡し直さない。
3. develop は Step A で明示された feature 名により既存 feature を再開する。

**代替フロー**:
- ディスパッチャが契約に従わずタスク記述で再発火した場合は、従来どおり新規 feature が作られる。
- 再起動でパス引数とタスク記述の両方が渡された場合は、既存規定どおりパス引数が優先される。

**事後条件**:
- 同一タスクに対して新たな feature（integration ブランチ）は作られない。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | batch-mode.md の Step A 行に再起動契約を明記 | Step A feature resolution 行に、`feature` 値をパス引数に渡しタスク記述を渡し直さない再起動契約を書く | 高 |
| FR2 | SKILL.md の Step A 規定を変更しない | develop の SKILL.md の「パス引数なし」項目と Step A「feature の決定」の記述を維持する | 高 |
| FR3 | batch-terminal-line.md の phase_done 再起動記述を明確化 | `state` 項目の `phase_done` 説明に再起動契約を書く | 高 |
| FR4 | 回帰テストの追加 | 再起動契約と既存規定の文言を検査するテストを追加する | 高 |
| FR5 | em-workflow プラグインの version を上げる | plugin.json と marketplace.json の version を patch 単位で上げる | 高 |

### 4.2 機能詳細

#### FR1: batch-mode.md の Step A 行に再起動契約を明記

**状態**: confirmed

**説明**: `em-workflow/references/batch-mode.md` の Non-packet gates 表「Step A feature resolution」行に、`--once` のフェーズ境界で終わった起動の続きは、構造化結果の `feature` 値をパス引数として渡して再起動し、タスク記述を渡し直さないことを明記する。同じ行の既存記述（Explicit feature-name/path argument wins / No path argument → always a new feature / Existing branches are never enumerated, and a feature is never guessed from them — resuming requires the explicit feature name）は維持する。

**ビジネスルール**:
- batch-mode.md 側は構造化結果の形式を再定義せず、`feature` 値の用い方のみを述べる（NFR4）。

#### FR2: SKILL.md の Step A 規定を変更しない

**状態**: confirmed

**説明**: `em-workflow/skills/develop/SKILL.md` の「引数処理」の「パス引数なし」項目、および Step A「feature の決定」の記述（既存 feature の再開はこの経路のみ / パス引数が無ければ新規 feature / 既存ブランチの列挙・推測は一切しない）を変更しない。develop の feature 解決規則は変えない。

#### FR3: batch-terminal-line.md の phase_done 再起動記述を明確化

**状態**: confirmed

**説明**: `em-workflow/references/batch-terminal-line.md` の `## Field values` の `state` 項目（`phase_done` の説明）に、再起動時は結果の `feature` 値をパス引数として渡し、タスク記述を渡し直さないことを明記する。既存の語句「re-launches the same feature」は保持する。

#### FR4: 回帰テストの追加

**状態**: confirmed

**説明**: `tests/` 配下に、次を検査するテストを追加する。各検査は文言が欠けた偽造テキストで失敗することを示す。
1. batch-mode.md の Step A 行が再起動契約（`feature` 値をパス引数に渡す・タスク記述を渡し直さない）を含むこと
2. batch-terminal-line.md の `phase_done` 記述が同契約を含むこと
3. batch-mode.md Step A 行の既存の列挙禁止・新規 feature 規定が残っていること

#### FR5: em-workflow プラグインの version を上げる

**状態**: confirmed

**説明**: `em-workflow/.claude-plugin/plugin.json` の `version` と、リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を同じ値に patch 単位で上げ、同じ変更に含める。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 該当なし

### 5.2 セキュリティ要件
- 入力検証: feature 名は既存の fail-closed 識別子ゲートを通したうえでシェルコマンドに補間する（変更なし）。

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- **NFR1**: `python3 -m unittest discover -s tests` が全件通る。
- **NFR2**: 追加テストは Python 標準ライブラリ（unittest）のみを使う。
- **NFR3**: SKILL.md に terminal-line の `state` 値リテラルや SC5 禁止リテラルを持ち込まない（`tests/test_develop_once_option.py` の既存ガードを維持する）。
- **NFR4**: batch-terminal-line.md が構造化結果の形式の唯一の所有者である関係を崩さない。batch-mode.md 側は形式を再定義せず、`feature` 値の用い方のみを述べる。

### 5.5 互換性要件
- 該当なし

## 6. UI/UX要件

該当なし（UI を持たない変更。references 文書・テスト・version のみ）。

## 7. データ要件

該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| 外部ディスパッチャ | `--batch --once` の起動と、構造化結果の受け取り | 構造化結果の `feature` 値 |

### 8.2 API仕様要件
- 構造化結果の形式は `em-workflow/references/batch-terminal-line.md` が所有する。本 feature では形式を変更しない。

## 9. 制約条件

### 9.1 技術的制約
- develop の feature 解決規則は変えない。
- 追加テストは Python 標準ライブラリ（unittest）のみを使う。
- SKILL.md に terminal-line の `state` 値リテラルや SC5 禁止リテラルを持ち込まない。

### 9.2 ビジネス上の制約
- 該当なし

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/batch-once-refire-dedup/**`
- `test-docs/batch-once-refire-dedup/**`

`feature-docs/batch-once-refire-dedup/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/batch-once-refire-dedup/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/batch-once-refire-dedup/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/batch-once-refire-dedup/` ディレクトリを生成しないが、宣言された `test-docs/batch-once-refire-dedup/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| ディスパッチャが契約に従わずタスク記述で再発火した場合、従来どおり新規 feature が作られる | 中 | develop 側の挙動は変えない。リポジトリ外のディスパッチャ側の対応（feature 名の持ち回り実装）は本 feature の範囲外で、別対応とする |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1）: batch-mode.md の Step A feature resolution 行に、`--once` フェーズ境界後の再起動は結果の `feature` 値をパス引数に渡し、タスク記述を渡し直さないことが書かれている。
- [ ] AC2（FR1, FR2）: batch-mode.md の Step A 行の既存規定（パス引数なしは常に新規 feature、既存ブランチの列挙・推測をしない、再開は明示 feature 名が必要）と、SKILL.md の「パス引数なし」項目・Step A「feature の決定」の既存文言が残っている。
- [ ] AC3（FR3）: batch-terminal-line.md の `phase_done` 記述に「re-launches the same feature」が残り、かつ結果の `feature` 値をパス引数として渡しタスク記述を渡し直さないことが書かれている。
- [ ] AC4（FR4, NFR1, NFR2）: FR4 のテストが存在し、`python3 -m unittest discover -s tests` が全件通る。FR4 の各検査に対し、文言を欠いた偽造テキストで検査が失敗することを示すテストがある。
- [ ] AC5（FR5）: em-workflow の plugin.json と marketplace.json の `version` が同じ値で、変更前より patch 単位で上がっている。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: batch-mode.md を読み、Non-packet gates 表の Step A feature resolution 行を切り出し、再起動契約（`feature` 値をパス引数に渡す・タスク記述を渡し直さない）の文言を含むことを確認する。
- [ ] TS2（AC2）: batch-mode.md の同じ行が既存の新規 feature 規定と列挙・推測禁止の文言を含むこと、SKILL.md の既存 Step A 文言が残っていることを確認する（SKILL.md 側は `tests/test_review_implement_develop_lock_contracts.py` の既存検査を維持）。
- [ ] TS3（AC3）: batch-terminal-line.md の `## Field values` の `state` 項目を切り出し、「re-launches the same feature」と再起動契約の文言を含むことを確認する。
- [ ] TS4（AC4）: TS1-TS3 の各マッチャに、契約文言を欠いた偽造テキストを与えて失敗することを確認する（非空虚性の検査）。
- [ ] TS5（AC4, NFR3）: `python3 -m unittest discover -s tests` を実行し、既存テスト（`test_develop_once_option.py` の SC5 / state リテラル検査、`test_batch_stop_contract.py` を含む）と新規テストが全件通ることを確認する。

### 12.2 エッジケース
- 再起動でパス引数とタスク記述の両方が渡された場合は、既存規定どおりパス引数が優先される。
- `state` `stopped` の結果（Step A 中断など）で `feature` が空の場合は、再起動契約の対象外（`phase_done` のみが対象）。
- retrospect 境界で終わった後の再起動は Step C を実行する。PR が必要なら再起動時に `--pr` を渡す（既存規定）。
- パス引数の feature 名が `^[a-z0-9][a-z0-9-]*$` に合わない場合は Step A で中断する（既存規定）。
- integration worktree が削除済みでも、パス引数で再起動すれば `git worktree add` で再生成される（既存規定）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 再起動契約 | `--once` のフェーズ境界で終わった起動の続きは、構造化結果の `feature` 値をパス引数として渡して再起動し、タスク記述を渡し直さないこと |
| 構造化結果 | `--batch` 起動の終了時に出力される結果。形式は `em-workflow/references/batch-terminal-line.md` が所有する |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1 再発火対策の方式: 方式 (a)（外部ディスパッチャが feature 名を持ち回る）を採る。develop の feature 解決規則は変えず、em-workflow 側は再起動契約の明記とテストでの固定のみを行う。方式 (b) 外部 ID 突き合わせ、(c) 重複の報告は採らない。
- [x] A2 範囲: リポジトリ外の `~/.claude/skills/notion-batch-develop/SKILL.md` の変更（feature 名の持ち回り実装）は本 feature の範囲外で、別対応とする。
- [x] A3 `feature` の値: `--once` のフェーズ境界で終わる結果（`state` `phase_done`）の `feature` は、Step A で確定した slug を常に持つ（batch-terminal-line.md の `feature` 項目の既存規定）。
- [x] A4 契約に従わない再発火: ディスパッチャが契約に従わずタスク記述で再発火した場合は、従来どおり新規 feature が作られる（develop 側の挙動は変えない）。
- [x] A5 既存テスト: `tests/test_batch_stop_contract.py:1042` が batch-terminal-line.md の語句「re-launches the same feature」を固定している。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- `em-workflow/references/batch-mode.md`
- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/skills/develop/SKILL.md`
