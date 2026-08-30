---
title: "declared-change-set-implementation"
created_date: 2026-08-18
status: draft
---

# declared-change-set-implementation - 要件定義書

## 1. 概要

### 1.1 背景

宣言された変更集合節が列挙する `feature-docs/{feature}/**` のメンバーに、create-plan フェーズの必須成果物である `IMPLEMENTATION.md` が含まれていない。列挙だけを見て宣言を明示列挙に絞り込んだ SPEC 作成者は `IMPLEMENTATION.md` を取りこぼす。

### 1.2 目的

両テンプレートの列挙を実態と一致させ、所有 SSOT（`em-workflow/references/phases/create-plan-phase.md` / `em-workflow/references/phase-state.md`）とテンプレート側の列挙のドリフトを解消する。あわせて、対応するテストのリテラル集合を同一内容に揃える。

### 1.3 スコープ

対象は 2 つのテンプレート、2 つのテストファイル、2 つの version 宣言に限定する。フィーチャー固有文書（例: `design-input.md`）の列挙追加はスコープ外。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| BO-1 | 宣言された変更集合節が列挙する `feature-docs/{feature}/**` のメンバーを、create-plan の必須成果物である `IMPLEMENTATION.md` を含む実態と一致させ、列挙だけを見て宣言を明示列挙に絞り込んだ SPEC 作成者が `IMPLEMENTATION.md` を取りこぼさないようにする。 |
| BO-2 | 列挙の所有 SSOT（`create-plan-phase.md` / `phase-state.md`）とテンプレート側の列挙のドリフトを解消し、両テンプレートと対応するテストのリテラル集合を単一の内容に揃える。 |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| SPEC 作成者 | 宣言された変更集合を明示列挙に絞り込む際に、テンプレートの列挙を参照する。 |

### 2.3 期待される効果

- 宣言を明示列挙に絞り込んだ場合でも `IMPLEMENTATION.md` が宣言に含まれる。
- テンプレートとテストのリテラル集合が単一の内容に揃う。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 宣言された変更集合を明示列挙に絞り込む | SPEC 作成者 | 高 |

### 3.2 ユースケース詳細

#### UC01: 宣言された変更集合を明示列挙に絞り込む

**アクター**: SPEC 作成者

**事前条件**:
- テンプレートの宣言された変更集合節が `feature-docs/{feature}/**` のメンバーを列挙している。

**基本フロー**:
1. SPEC 作成者がテンプレートの列挙を参照する。
2. デフォルトメンバー `feature-docs/{feature}/**` を明示列挙に置き換える。
3. 列挙されたメンバーに `IMPLEMENTATION.md` が含まれている。

**事後条件**:
- 明示列挙された宣言に `IMPLEMENTATION.md` が含まれる。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | SPEC テンプレートの列挙に IMPLEMENTATION.md を追加 | `spec-document.md` の `## Declared Change Set` 節の列挙にメンバーを追加する | resolved |
| FR2 | REQUIREMENTS テンプレートの列挙に IMPLEMENTATION.md を追加 | `requirements-document.md` の `### 9.4 宣言された変更集合` の列挙にメンバーを追加する | resolved |
| FR3 | テストの FEATURE_DOCS_MEMBERS に同一リテラルを追加 | 2 つのテストの `FEATURE_DOCS_MEMBERS` に同じリテラルを追加する | resolved |
| FR4 | プラグイン version の bump | `plugin.json` と `marketplace.json` の version を同じ値に bump する | resolved |

### 4.2 機能詳細

#### FR1: SPEC テンプレートの列挙に IMPLEMENTATION.md を追加

**説明**: `em-workflow/references/templates/spec-document.md` の `## Declared Change Set` 節が列挙する `feature-docs/{feature}/**` のメンバーに `IMPLEMENTATION.md` を含める。

#### FR2: REQUIREMENTS テンプレートの列挙に IMPLEMENTATION.md を追加

**説明**: `em-workflow/references/templates/requirements-document.md` の `### 9.4 宣言された変更集合` が列挙する `feature-docs/{feature}/**` のメンバーに `IMPLEMENTATION.md` を含める。

#### FR3: テストの FEATURE_DOCS_MEMBERS に同一リテラルを追加

**説明**: `tests/test_spec_template_declared_change_set.py` と `tests/test_requirements_template_declared_change_set.py` の `FEATURE_DOCS_MEMBERS` に、FR1 / FR2 で追加したものと同じ `IMPLEMENTATION.md` リテラルを含める。

#### FR4: プラグイン version の bump

**説明**: プラグイン配下（`em-workflow/references/templates/`）を変更するため、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` 該当エントリの version を同じ変更の中で同じ値に bump する。刻みは挙動修正相当の patch。

## 5. 非機能要件

| ID | 名称 | 内容 | 状態 |
|----|------|------|------|
| NFR1 | 列挙スタイルの一貫性 | 追加するメンバーの表記・配置は、各節の既存メンバー（`REQUIREMENTS.md` / `SPEC.md` / `workflow.yaml` / `phase-state/` / `tasks/` / `reviews/roundN.yaml` / `VERIFICATION.md` / `retrospect.yaml` / デザイン成果物）の記法に揃える。呼称は所有 SSOT である `em-workflow/references/phases/create-plan-phase.md` および `em-workflow/references/phase-state.md` の呼称と一致させる。 | resolved |
| NFR2 | テストの外部依存禁止 | テスト変更は Python 標準ライブラリ unittest のみに依存する（`test/README.md` の「テストコードはサードパーティを import しない」規約）。 | resolved |
| NFR3 | 負の証明サンプルの不変 | テスト内の `PRE_CHANGE` サンプルは当該リテラルを含まないため変更しない。負の証明（変更前状態では検出が失敗する）が維持されること。 | resolved |
| NFR4 | 変更範囲の限定 | 変更は 2 つのテンプレート、2 つのテストファイル、2 つの version 宣言に限定する。フィーチャー固有文書（例: `design-input.md`）の列挙追加はスコープ外。 | resolved |

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

該当なし。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

- NFR1 のとおり、列挙の呼称を所有 SSOT と一致させる。

### 5.5 互換性要件

- NFR2 のとおり、テストは Python 標準ライブラリ unittest のみに依存する。

## 6. UI/UX要件

該当なし。デザインステップは skip（変更対象は Markdown テンプレートの列挙、Python テストのリテラル、および version メタデータのみで、UI・画面・ユーザー可視の表示要素を一切含まない）。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- テスト変更は Python 標準ライブラリ unittest のみに依存する（NFR2）。
- `PRE_CHANGE` サンプルは変更しない（NFR3）。

### 9.2 ビジネス上の制約

- 変更範囲は 2 つのテンプレート、2 つのテストファイル、2 つの version 宣言に限定する（NFR4）。

### 9.3 スケジュール制約

- 該当なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/templates/spec-document.md`
- `em-workflow/references/templates/requirements-document.md`
- `tests/test_spec_template_declared_change_set.py`
- `tests/test_requirements_template_declared_change_set.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| PR #9 (feature: spec-file-set-completeness) が未マージの場合、対象節と 2 つのテストファイルが存在しない | 高 | 未マージなら本フィーチャーは着手不能（AS-1） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| テンプレートとテストのリテラルが再びドリフトする | 中 | 中 | FR3 により同一リテラルをテストで検証する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `em-workflow/references/templates/spec-document.md` の `## Declared Change Set` 節の列挙に `IMPLEMENTATION.md` が含まれる。（検証対象: FR1）
- [ ] AC2: `em-workflow/references/templates/requirements-document.md` の `### 9.4 宣言された変更集合` の列挙に `IMPLEMENTATION.md` が含まれる。（検証対象: FR2）
- [ ] AC3: `tests/test_spec_template_declared_change_set.py` と `tests/test_requirements_template_declared_change_set.py` の `FEATURE_DOCS_MEMBERS` に同じリテラルが入っている。（検証対象: FR3）
- [ ] AC4: リポジトリルートで `python3 -m unittest discover -s tests` が通る。（検証対象: FR1, FR2, FR3, NFR2, NFR3）
- [ ] AC5: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version が同じ変更の中で同じ値に bump されている。（検証対象: FR4）

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 正常系: `test_spec_template_declared_change_set.py` が、`spec-document.md` の Declared Change Set 節に `FEATURE_DOCS_MEMBERS` の全メンバー（`IMPLEMENTATION.md` を含む）が出現することを検証する。実行コマンド: `python3 -m unittest discover -s tests`
- [ ] TS2 正常系: `test_requirements_template_declared_change_set.py` が、`requirements-document.md` の 9.4 節に対して同じ検証を行う。実行コマンド: `python3 -m unittest discover -s tests`
- [ ] TS3 異常系（負の証明）: `PRE_CHANGE` サンプルに対する負の証明が、変更後も `IMPLEMENTATION.md` を含まない入力で失敗を検出し続ける。実行コマンド: `python3 -m unittest discover -s tests`
- [ ] TS4 回帰: スイート全体が回帰なく通る。実行コマンド: `python3 -m unittest discover -s tests`

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 宣言された変更集合 | SPEC が宣言する、フィーチャーが作成・変更するファイルおよびディレクトリの集合。スーパーセットの主張であり、実際の変更集合は宣言に含まれる必要がある。 |
| `FEATURE_DOCS_MEMBERS` | テストが検証する、`feature-docs/{feature}/**` のメンバーのリテラル集合。 |
| `PRE_CHANGE` サンプル | 変更前状態を表すテスト内サンプル。負の証明に用いる。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 追加するメンバーの呼称: 所有 SSOT である `create-plan-phase.md` / `phase-state.md` の呼称と一致させる（NFR1）
- [x] version bump の刻み: patch（挙動の修正）（FR4 / AS-4）
- [x] 変更範囲: 2 つのテンプレート、2 つのテストファイル、2 つの version 宣言に限定（NFR4）
- [x] デザインステップ: skip（UI・画面・ユーザー可視の表示要素を一切含まない）

### 14.2 前提事項

- AS-1: PR #9 (feature: spec-file-set-completeness) がマージ済みであり、両テンプレートに対象節と 2 つのテストファイルが存在する。未マージなら本フィーチャーは着手不能。
- AS-2: ルート宣言が `**` グロブであるため containment 自体は破れておらず、本件は宣言の妥当性ではなく列挙の網羅性の是正である。
- AS-3: 対象テンプレート・テストの現在の内容は分析時点では未読であり、要件はタスク記述が明示した受け入れ条件から導出した。
- AS-4: version bump の刻みは patch（挙動の修正）。現行 version 値は実装時に決定する。

## 15. 参考資料

- `em-workflow/references/phases/create-plan-phase.md`: `feature-docs/{feature}/**` メンバーの所有 SSOT
- `em-workflow/references/phase-state.md`: `feature-docs/{feature}/**` メンバーの所有 SSOT
- `test/README.md`: テストコードはサードパーティを import しない規約
