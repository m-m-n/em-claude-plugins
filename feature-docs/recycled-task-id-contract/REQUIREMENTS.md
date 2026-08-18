---
title: "recycled-task-id-contract"
created_date: 2026-08-18
status: draft
---

# recycled-task-id-contract - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow の SSOT である `em-workflow/references/implement-phase.md` の I.2.a に置かれた recycled-task-id の文言が自己矛盾しており、読み手が単一の解釈に到達できない。同ドキュメントの Supporting cast にある Stop-hook 箇条書き（:496-506）も、この I.2.a（:222-232）と整合していない。あわせて `tests/test_recycled_task_id_consistency.py` の `TestRecycledTaskIdRuleScopedToOrchestrator` が空振りしており、実装が壊れてもテストが落ちない状態にある。

由来: stopguard-retired-failed フィーチャーのレビュー findings `eda12b14c5d3235f`（comprehensive / medium / confidence 80）および `0e36903a813a34fa`（architecture / medium / confidence 75）の deferred 分。

Notion task: [https://app.notion.com/p/3be3509ec8ee81abbfd6e3776242c804](https://app.notion.com/p/3be3509ec8ee81abbfd6e3776242c804)

### 1.2 目的

- implement-phase.md I.2.a の recycled-task-id 文言から自己矛盾を取り除き、読み手が単一の解釈に到達できる状態にする。
- `tests/test_recycled_task_id_consistency.py` を実装と一致する契約に更新し、空振り状態を解消する。
- ドキュメントの分類ルールと hook 実装の対応を機械的に pin し、片側だけの変更が検出されるようにする。

### 1.3 スコープ

**対象**:
- `em-workflow/references/implement-phase.md` の I.2.a および Supporting cast の Stop-hook 箇条書きの記述更新
- `em-workflow/references/implement-phase.md` への機械可読な hook 分類表の追加
- `tests/` 配下の Python テスト（既存 `test_recycled_task_id_consistency.py` の更新と pin テスト 1 本）
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version bump

**対象外**:
- `em-workflow/hooks/queue_stop_guard.py` の分類ロジック
- hook 群の実行時挙動（本変更で一切変更しない）

## 2. ビジネス要件

### 2.1 ビジネス目標

- em-workflow の SSOT である implement-phase.md I.2.a の recycled-task-id 文言から自己矛盾を取り除き、読み手が単一の解釈に到達できる状態にする。
- `tests/test_recycled_task_id_consistency.py` を実装と一致する契約に更新し、空振り（実装が壊れても落ちない）状態を解消する。
- ドキュメントの分類ルールと hook 実装の対応を機械的に pin し、片側だけの変更が検出されるようにする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の読み手（orchestrator / worker） | implement-phase.md I.2.a を SSOT として読み、recycled-task-id の扱いを判断する |
| 開発者 / CI | `tests/` の整合性テストを実行し、ドキュメントと hook 実装の乖離を検出する |

### 2.3 期待される効果

- I.2.a の recycled-task-id 記述が一読で曖昧さなく決まる。
- ドキュメント側・実装側のどちらか一方だけが変更された場合に、テストが落ちて検出される。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | I.2.a を読んで recycled-task-id の扱いを判断する | em-workflow の読み手（orchestrator / worker） | 高 |
| UC02 | 整合性テストを実行してドキュメントと実装の乖離を検出する | 開発者 / CI | 高 |

### 3.2 ユースケース詳細

#### UC01: I.2.a を読んで recycled-task-id の扱いを判断する

**アクター**: em-workflow の読み手（orchestrator / worker）

**事前条件**:
- `em-workflow/references/implement-phase.md` が参照可能である

**基本フロー**:
1. 読み手が I.2.a の recycled-task-id に関する記述を読む。
2. recycled-task-id ルールが orchestrator にスコープされることを読み取る。
3. hook 側がどこまでを担うか（hook 群は journal の不在のみをもって unlaunched と扱う）を、その理由とともに読み取る。

**代替フロー**:
- Supporting cast の Stop-hook 箇条書きを参照した場合も、I.2.a と同じ分類（`tasks.{T}.status` を読む hook / 読まない hook）に到達する。

**事後条件**:
- 読み手が単一の解釈に到達している。

#### UC02: 整合性テストを実行してドキュメントと実装の乖離を検出する

**アクター**: 開発者 / CI

**事前条件**:
- リポジトリルートで `python3` が実行可能である

**基本フロー**:
1. リポジトリルートで `python3 -m unittest discover -s tests` を実行する。
2. pin テストが implement-phase.md の hook 分類表を parse する。
3. 表に載る各 hook のソースが `tasks.{T}.status` を読むかどうかを検証する。

**代替フロー**:
- ドキュメント側・実装側のどちらか一方だけが変更されていた場合、テストが落ちる。

**事後条件**:
- ドキュメントの分類と hook 実装の対応が検証されている。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 | 状態 |
|----|--------|------|--------|------|
| FR1 | I.2.a の recycled-task-id 文言を無矛盾化する | 自己矛盾のない単一の文面に書き換える | 高 | resolved |
| FR2 | Supporting cast の Stop-hook 箇条書きを I.2.a と整合させる | FR1 で確定した文面と矛盾しない記述に更新する | 高 | resolved |
| FR3 | `TestRecycledTaskIdRuleScopedToOrchestrator` の assert を分割する | 3 hook 群と明示的例外を分けて assert する | 高 | resolved |
| FR4 | unlaunched 判定の乖離を I.2.a に SSOT として明記する | journal の不在のみで unlaunched と扱う旨を理由とともに記す | 高 | resolved |
| FR5 | hook 分類表を機械可読にし、それを parse する pin テストを 1 本置く | ドキュメントを期待分類の出所とする | 高 | resolved |
| FR6 | プラグイン version を bump する | plugin.json と marketplace.json を同一値・patch 刻みで引き上げる | 高 | resolved |

### 4.2 機能詳細

#### FR1: I.2.a の recycled-task-id 文言を無矛盾化する

**説明**: `em-workflow/references/implement-phase.md` I.2.a の recycled-task-id に関する記述を、自己矛盾のない単一の文面に書き換える。recycled-task-id ルールが orchestrator にスコープされること、および hook 側がどこまでを担うかが、一読して曖昧さなく決まること。

**入力**:
- `em-workflow/references/implement-phase.md` I.2.a（:222-232）の現行記述

**出力**:
- 自己矛盾のない単一の I.2.a 文面

**ビジネスルール**:
- recycled-task-id ルールは orchestrator にスコープされる。
- hook 側の担当範囲が一読して曖昧さなく決まる。

#### FR2: Supporting cast の Stop-hook 箇条書きを I.2.a と整合させる

**説明**: 同ドキュメントの Supporting cast にある Stop-hook 箇条書き（:496-506）を、FR1 で確定した I.2.a の文面と矛盾しない記述に更新する。両者が同じ分類（`tasks.{T}.status` を読む hook / 読まない hook）を指すこと。

**入力**:
- FR1 で確定した I.2.a の文面
- Supporting cast の Stop-hook 箇条書きの現行記述

**出力**:
- I.2.a と同じ分類を指す Stop-hook 箇条書き

**ビジネスルール**:
- I.2.a と Supporting cast が同一の分類を指す。

#### FR3: `TestRecycledTaskIdRuleScopedToOrchestrator` の assert を分割する

**説明**: `tests/test_recycled_task_id_consistency.py` の `TestRecycledTaskIdRuleScopedToOrchestrator` を、「`tasks.{T}.status` を読まない 3 hook」に対する assert と、「明示的例外である `queue_stop_guard.py`」に対する assert に分けて記述する。

**入力**:
- 既存の `tests/test_recycled_task_id_consistency.py`

**出力**:
- 2 グループに分割された assert

**ビジネスルール**:
- 両グループを 1 つの assert にまとめない。
- いずれか一方が崩れた場合に、該当グループのテストが落ちる。

#### FR4: unlaunched 判定の乖離を I.2.a に SSOT として明記する

**説明**: hook の挙動は変更せず、`implement-phase.md` I.2.a に「hook 群は journal の不在のみをもって unlaunched と扱う」ことを、その理由とともに SSOT として明記する。

**入力**:
- hook 群の現行挙動（変更しない）

**出力**:
- journal 不在ルールとその理由を含む I.2.a の記述

**ビジネスルール**:
- I.2.a が hook の提供しない保護を約束する文面にならないこと。
- hook の挙動は変更しない。

#### FR5: hook 分類表を機械可読にし、それを parse する pin テストを 1 本置く

**説明**: `implement-phase.md` に hook 名と分類（`tasks.{T}.status` を読む / 読まない）の対応を示す機械可読な表を追加し、pin テストがその表を parse して、表に載る各 hook のソースが `tasks.{T}.status` を読むかどうかを検証する。

**入力**:
- `em-workflow/references/implement-phase.md` の hook 分類表
- 表に載る各 hook のソース

**出力**:
- 分類の一致 / 不一致の検証結果

**ビジネスルール**:
- ドキュメント側・実装側のどちらか一方だけが変更された場合にテストが落ちる。
- テストは 1 本に収める。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 分類不一致 | 表の分類と hook 実装が食い違う | テストが落ちる |
| 未知の hook 名 | 表に載る hook 名が実装側に存在しない | テストが落ちる |

#### FR6: プラグイン version を bump する

**説明**: `em-workflow/` 配下を変更するため、`em-workflow/.claude-plugin/plugin.json` とリポジトリルート `.claude-plugin/marketplace.json` の該当エントリの version を、同一値・patch 刻みで同じ変更に含めて引き上げる。

**入力**:
- 現行の `em-workflow/.claude-plugin/plugin.json` の version
- 現行の `.claude-plugin/marketplace.json` の該当エントリの version

**出力**:
- 同一値に bump された 2 箇所の version

**ビジネスルール**:
- 2 箇所の version は同一値にする。
- patch 刻みで引き上げる。
- 同じ変更に含める。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし（本フィーチャーはドキュメントとテストのみを変更し、実行時性能に影響する要素を持たない）。

### 5.2 セキュリティ要件

該当なし（本フィーチャーは認証・認可・データ保護を伴う要素を持たない）。

### 5.3 可用性要件

該当なし（本フィーチャーは稼働するサービスを持たない）。

### 5.4 保守性要件

#### NFR1: テストは標準ライブラリのみ

テストコードは Python 標準ライブラリ `unittest` のみを用い、サードパーティパッケージを import しない（`test/README.md`）。

#### NFR2: テスト配置・命名規約

テストはリポジトリルート `tests/` 配下に `test_*.py` として置き、クラスは `Test<Behavior>`、メソッドは `test_<condition>_<expected_result>` とする。対象はパス参照（例 `em-workflow/hooks/queue_stop_guard.py`）で扱う。

#### NFR4: SSOT の単一性

hook 分類の期待値はドキュメント側の表を唯一の出所とし、テスト内に分類のハードコード重複を作らない。

### 5.5 互換性要件

#### NFR3: スコープ外の非改変

`queue_stop_guard.py` の分類ロジック自体は変更しない。hook の実行時挙動は本変更で一切変えない。

## 6. UI/UX要件

該当なし。本フィーチャーは UI・視覚的成果物・ユーザー向け表示面を持たないため、デザインステップはスキップされる。

### 6.1 画面設計要件

該当なし。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

### 7.1 データモデル概要

該当なし（永続データモデルを持たない）。

### 7.2 データ項目

本フィーチャーが扱う構造化データは、implement-phase.md に追加する hook 分類表のみ。

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| hook 分類表の行 | hook 名 | string | ○ | 対象 hook のパス参照 |
| hook 分類表の行 | 分類 | enum | ○ | `tasks.{T}.status` を読む / 読まない |

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

該当なし。

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- テストは Python 標準ライブラリ `unittest` のみを使用する（NFR1）。
- テストはリポジトリルート `tests/` 配下に `test_*.py` として置く（NFR2）。
- `queue_stop_guard.py` の分類ロジックおよび hook の実行時挙動は変更しない（NFR3）。
- hook 分類の期待値はドキュメント側の表を唯一の出所とする（NFR4）。
- FR5 のテストは 1 本に収める。

### 9.2 ビジネス上の制約

- `em-workflow/` 配下を変更するため、version bump を同じ変更に含める（FR6）。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/implement-phase.md`
- `tests/**`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/recycled-task-id-contract/**`
- `test-docs/recycled-task-id-contract/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| I.2.a が hook の提供しない保護を約束する文面になる | 中 | journal 不在ルールを理由とともに明記する（FR4） |
| テストが分類をハードコードして再び空振りする | 中 | ドキュメントの表を parse し、期待値の出所を単一にする（FR5 / NFR4） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| version 据え置きによりプラグインキャッシュが更新されない | 中 | 中 | plugin.json と marketplace.json を同一値に bump する（FR6） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: implement-phase.md I.2.a の recycled-task-id 文言が矛盾のない単一の文面になっている（FR1）。
- [ ] AC2: Supporting cast の Stop-hook 箇条書きが I.2.a と整合している（FR2）。
- [ ] AC3: `TestRecycledTaskIdRuleScopedToOrchestrator` が「status を読まない 3 hook」と「明示的例外である `queue_stop_guard.py`」を分けて assert している（FR3）。
- [ ] AC4: I.2.a に、hook 群が journal の不在のみで unlaunched と判定する旨とその理由が明記されている（FR4）。
- [ ] AC5: ドキュメントの機械可読な hook 分類表を parse し、各 hook のソースが `tasks.{T}.status` を読むかを検証する pin テストが 1 本存在する（FR5）。
- [ ] AC6: `python3 -m unittest discover -s tests` がリポジトリルートで通る。
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version が同一値に bump されている（FR6）。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1（正常系）: 分類表に載る「status を読まない 3 hook」それぞれについて、ソースが `tasks.{T}.status` を読まないことを個別に assert する。
- [ ] TS2（正常系）: `queue_stop_guard.py` について、明示的例外として `tasks.{T}.status` を読むことを別の assert で検証する。
- [ ] TS3（正常系 / pin）: implement-phase.md の分類表を parse し、表に載る全 hook の実装と分類が一致することを検証する。表に無い hook 名や、実装と食い違う分類があれば落ちる。
- [ ] TS4（異常系 / ネガティブ確認）: 分類表の分類だけを反転させると pin テストが落ちる（テストが空振りしていないこと）。
- [ ] TS5（回帰）: `python3 -m unittest discover -s tests` の全体実行が成功する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| recycled-task-id | 一度使われたタスク ID が再度使われる状況を指す、implement-phase.md I.2.a が扱う対象 |
| I.2.a | `em-workflow/references/implement-phase.md` の該当セクション（:222-232） |
| Supporting cast | 同ドキュメント内の Stop-hook 箇条書きを含むセクション（:496-506） |
| journal | hook 群が unlaunched 判定に用いる存在／不在の対象 |
| pin テスト | ドキュメントの記述と実装の対応を機械的に固定し、片側だけの変更を検出するテスト |
| SSOT | Single Source of Truth |

## 14. 確認事項

### 14.1 確認済み事項

- [x] unlaunched 判定の乖離の扱い: hook の挙動は変更せず、hook 群が journal の不在のみをもって unlaunched と扱う事実をその理由とともに implement-phase.md I.2.a に SSOT として記録する（batch-codex-consultation、gate `create-spec.requirement-clarification`、option `doc_records_divergence`）。根拠: `queue_stop_guard.py` の分類ロジック変更はタスク記述でスコープ外とされており、journal 不在ルールを明文化することで SSOT が hook の提供しない保護を約束することを避ける。
- [x] hook 分類の期待値の持ち方: implement-phase.md に機械可読な hook-to-classification 表を追加し、pin テストはその表を parse して各 hook のソースが `tasks.{T}.status` を読むかを検証する（batch-codex-consultation、gate `create-spec.requirement-clarification`、option `parse_doc_table`）。根拠: 表を parse することでドキュメントが期待分類の出所となり、片側だけの変更でテストが落ちる。
- [x] 「status を読まない 3 hook」の具体的な hook 名の出所: implement-phase.md の記述（および新設する分類表）を出所とする。hook ファイル一覧の実地確認は実装フェーズで行う。
- [x] ライセンス識別子: リポジトリルートに LICENSE ファイルが存在しないため、SPDX 識別子は特定できない（未検出として扱う）。

### 14.2 未確認・保留事項

なし（すべての要件が `resolved`）。

## 15. 参考資料

- Notion task: [https://app.notion.com/p/3be3509ec8ee81abbfd6e3776242c804](https://app.notion.com/p/3be3509ec8ee81abbfd6e3776242c804)
- `em-workflow/references/implement-phase.md`: I.2.a（:222-232）、Supporting cast Stop-hook 箇条書き（:496-506）
- `tests/test_recycled_task_id_consistency.py`: `TestRecycledTaskIdRuleScopedToOrchestrator`
- `test/README.md`: テストの依存方針（標準ライブラリのみ）
- 由来レビュー findings: `eda12b14c5d3235f`（comprehensive / medium / confidence 80）、`0e36903a813a34fa`（architecture / medium / confidence 75）
