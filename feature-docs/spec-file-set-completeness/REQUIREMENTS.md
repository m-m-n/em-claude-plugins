---
title: "spec-file-set-completeness"
created_date: 2026-08-16
status: draft
---

# spec-file-set-completeness - 要件定義書

## 1. 概要

### 1.1 背景

閉じた変更集合を宣言する SPEC が、ワークフロー自身の実行によって満たされない状態がある。em-workflow が生成を義務付けている成果物（タスクごとのテスト記録、および SPEC 作成後に生成される feature-docs 配下の成果物）が宣言の外に置かれると、implement / review / verify が行き止まりに達し、その唯一の出口が `em-workflow/references/rework-task-synthesis.md` の禁じる SPEC 編集（同文書は当該編集を `gate_id: rework.spec-change` に回す）になる。

### 1.2 目的

SPEC が書かれた時点で、ワークフロー生成物が宣言の内側に入っている状態にする。修正は spec-writer がレンダリングする 2 つのドキュメントテンプレートに置き、以後のすべての feature が feature ごとの是正なしに、また verify 側の除外ルールなしに、正しい既定メンバーシップを継承する。

### 1.3 スコープ

対象は次に限る。

- `em-workflow/references/templates/spec-document.md`
- `em-workflow/references/templates/requirements-document.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `feature-docs/spec-file-set-completeness/**`
- `test-docs/spec-file-set-completeness/**`
- `tests/` 配下の新規または拡張されるテストモジュール

対象外（本 feature で変更しないもの）は 9.1 に記す。

## 2. ビジネス要件

### 2.1 ビジネス目標

- 閉じた変更集合を宣言する SPEC が、ワークフロー自身の実行によって満たせること。em-workflow が生成を義務付けている成果物（タスクごとのテスト記録、および SPEC 作成後に生成されるすべての feature-docs 成果物）が、SPEC が書かれた時点から宣言の内側にあり、implement / review / verify が、`em-workflow/references/rework-task-synthesis.md` が禁じる（`gate_id: rework.spec-change` へ回す）SPEC 編集しか出口のない行き止まりに達しないこと。
- 修正が繰り返しではなく継承であること。修正は spec-writer がレンダリングする 2 つのドキュメントテンプレートに存在し、以後のすべての feature が、feature ごとの是正なしに、また verify 側の除外ルールなしに、正しい既定メンバーシップを得る。
- 封じ込めが強いままであること。検証時に観測された変更集合から何も差し引かない。宣言の側を実態に合わせて広げる。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| SPEC 作成者（spec-writer worker） | テンプレートから SPEC / 要件定義書をレンダリングし、feature 固有のパスを列挙する |
| ワークフロー実行者 | implement / review / verify を通して feature を完了させる |

### 2.3 期待される効果

- SPEC が宣言した閉じた変更集合を、ワークフロー自身の実行で満たせる
- 以後の feature が feature ごとの是正なしに正しい既定メンバーシップを継承する
- 検証時の封じ込め判定を弱めずに済む

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | SPEC / 要件定義書に変更集合を宣言する | SPEC 作成者（spec-writer worker） | 高 |
| UC02 | 宣言された変更集合に対して実際の変更集合の封じ込めを検証する | ワークフロー実行者 | 高 |

### 3.2 ユースケース詳細

#### UC01: SPEC / 要件定義書に変更集合を宣言する

**アクター**: SPEC 作成者（spec-writer worker）

**事前条件**:
- 2 つのテンプレートに変更集合セクション（FR1 / FR2）が存在する

**基本フロー**:
1. SPEC 作成者がテンプレートから SPEC / 要件定義書をレンダリングする
2. 既定メンバーシップのブロック（`feature-docs/{feature}/**` と `test-docs/{feature}/**`）がレンダリング済みの文書に含まれる
3. SPEC 作成者が feature 固有のパスを `{placeholder}` のリストに列挙する

**代替フロー**:
- SPEC 作成者が既定エントリを明示的に削除する（意図的な狭め。沈黙による欠落ではない）

**事後条件**:
- 宣言された変更集合が、SPEC 作成後に生成されるワークフロー成果物を含んでいる

#### UC02: 宣言された変更集合に対して実際の変更集合の封じ込めを検証する

**アクター**: ワークフロー実行者

**事前条件**:
- SPEC が閉じた変更集合を宣言している

**基本フロー**:
1. 変更が commit される
2. 検証時に、commit されたすべての成果物が実際の変更集合の一部として扱われる
3. 実際の変更集合が宣言に CONTAINED IN であることを確認する

**代替フロー**:
- 宣言されたパスが一度も実体化しない場合、それは違反ではない（implement タスクが 0 件の feature は `test-docs/{feature}/` を一切生成しないが、宣言された `test-docs/{feature}/**` エントリは依然として正しい）

**事後条件**:
- 検証時に、ワークフロー生成物を観測された変更集合から除外するルールは適用されていない

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | SPEC テンプレートに Declared Change Set セクションを追加 | `spec-document.md` に `## Declared Change Set` を追加する | 高 |
| FR2 | 要件定義書テンプレートに同等のセクションを追加 | `requirements-document.md` に `### 9.4 宣言された変更集合` を追加する | 高 |
| FR3 | 既定メンバーシップは 2 つのワークフロー出力ルート | `feature-docs/{feature}/**` と `test-docs/{feature}/**` の両方 | 高 |
| FR4 | 既定メンバーシップが 2 ルートの内容を引用付きで列挙 | 生成元の phase ドキュメントを CITE する | 高 |
| FR5 | 既定包含・上位集合セマンティクスの明示 | 削除しない限り既定は残る／実態は宣言に含まれる | 高 |
| FR6 | 封じ込め検証セマンティクスは不変 | verify 側の除外ルールを追加しない | 高 |
| FR7 | 完了済み feature は書き換えず、整合済み状態をテストで固定 | `recycled-task-id-consistency` は変更しない | 中 |
| FR8 | 本 feature の変更封じ込め | 変更対象ファイルの列挙 | 高 |
| FR9 | 両レジストリのプラグインバージョンを 0.1.41 に bump | plugin.json と marketplace.json | 中 |

### 4.2 機能詳細

#### FR1: SPEC テンプレートに Declared Change Set セクションを追加

**説明**: `em-workflow/references/templates/spec-document.md` の外側の fenced ```markdown テンプレート本文の内側に、新しいトップレベルセクション `## Declared Change Set` を追加する。位置は `## Implementation Approach` の `### File Structure` サブセクションの後、`## Test Scenarios` の前。このセクションは (a) SPEC 作成者が列挙する feature 固有パスのための `{placeholder}` リストと、(b) レンダリングされたすべての SPEC に存在する固定の既定メンバーシップブロック（FR3、FR4）を持つ。

**入力**:
- `spec-document.md`: markdown - 変更前のテンプレート本文

**出力**:
- `spec-document.md`: markdown - `## Declared Change Set` セクションを含むテンプレート本文

**ビジネスルール**:
- セクションは外側の fenced ```markdown ブロックの内側に置く
- 既定メンバーシップブロックはレンダリングされたすべての SPEC に存在する

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| セクション位置の誤り | `### File Structure` より前、または `## Test Scenarios` より後に置かれた | AC-1 / TS-1 で検出する |

#### FR2: 要件定義書テンプレートに同等のセクションを追加

**説明**: `em-workflow/references/templates/requirements-document.md` の fenced テンプレート本文の内側に、既存の `## 9. 制約条件` の下位として新しいサブセクション `### 9.4 宣言された変更集合` を追加する。FR1 のセクションと同じ既定メンバーシップを持つ。既存のトップレベルセクション番号（1..15）とタイトルをすべて変えないために、サブセクションとして追加する。

**入力**:
- `requirements-document.md`: markdown - 変更前のテンプレート本文

**出力**:
- `requirements-document.md`: markdown - `### 9.4 宣言された変更集合` を含むテンプレート本文

**ビジネスルール**:
- 既存のトップレベルセクション番号（1..15）とタイトルは変更しない

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 番号の振り直し | 既存トップレベル見出しの番号またはタイトルが変わった | AC-2 / TS-4 で検出する |

#### FR3: 既定メンバーシップは 2 つのワークフロー出力ルート

**説明**: 新しい 2 つのセクションはいずれも、feature の宣言された変更集合が既定で `feature-docs/{feature}/**` と `test-docs/{feature}/**` の両方を含むと述べる。既定を `test-docs/` のみに限定することは明示的に却下する。feature-docs ルートは SPEC が書かれた後に生成される成果物を担うため、これを省略すると 1 フェーズ遅れて同じ行き止まりを再現する。

**ビジネスルール**:
- 既定は 2 ルート両方。`test-docs/` のみへの限定は却下

#### FR4: 既定メンバーシップが 2 ルートの内容を引用付きで列挙

**説明**: 新しい 2 つのセクションはいずれも、2 つのルートが覆うワークフロー生成成果物を列挙し、SPEC 作成者がそれらを再発見しなくて済むようにする。`feature-docs/{feature}/` 配下では `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する design 成果物。`test-docs/{feature}/` 配下では `em-workflow/references/implement-phase.md` が義務付けるタスクごとの `{T}.tests.yaml` 記録（`tests_yaml_path` = `test-docs/{feature}/{T}.tests.yaml`。タスク worktree で書かれ、実装とともに親ブランチへマージされる）。各エントリは、その成果物の生成を所有する phase ドキュメントを CITE するのであって、そのドキュメントのルールを再掲しない。

**ビジネスルール**:
- 各エントリは所有ドキュメントを引用する。ルールの再掲はしない

#### FR5: 既定包含・上位集合セマンティクスの明示

**説明**: 新しい 2 つのセクションはいずれも、宣言の 2 つの性質を述べる。(a) 既定エントリは SPEC 作成者が明示的に削除しない限り宣言の一部である。削除は意図的な狭めであって、沈黙による欠落ではない。(b) 宣言は SUPERSET の主張である。実際の変更集合は宣言に CONTAINED IN でなければならず、宣言されたパスが一度も実体化しなくても違反ではない。具体例として implement タスクが 0 件のケースを挙げる。implement タスクを生成しない feature は `test-docs/{feature}/` ディレクトリを一切生成しないが、宣言された `test-docs/{feature}/**` エントリは依然として正しい。

**ビジネスルール**:
- 既定エントリは明示的削除がない限り残る
- 宣言は上位集合。実態は宣言に含まれていればよい

#### FR6: 封じ込め検証セマンティクスは不変

**説明**: どのドキュメントにも、検証時にワークフロー生成成果物を観測された変更集合から除外するルールを追加しない。commit されたすべての成果物は、今日と同じく実際の変更集合の一部であり続ける。本 feature で変更しないもの: `em-workflow/references/implement-phase.md`、`review-phase.md`、`review-protocol.md`、`phases/create-spec-phase.md`、`phases/create-plan-phase.md`、`rework-task-synthesis.md`、`em-workflow/references/contracts/` 配下のすべて、`em-workflow/scripts/validate-worker-output.py`、`em-workflow/hooks/`、`em-workflow/agents/`、`em-workflow/skills/` 配下のすべて。

#### FR7: 完了済み feature は書き換えず、整合済み状態をテストで固定

**説明**: `feature-docs/recycled-task-id-consistency/SPEC.md` と `feature-docs/recycled-task-id-consistency/REQUIREMENTS.md` は変更しない。ベースリビジョンの時点で、両者は変更封じ込め要件（SPEC.md の FR8 / AC-8、REQUIREMENTS.md の対応する制約）に `test-docs/recycled-task-id-consistency/**` をすでに列挙しており、是正すべきものがない。代わりに、その整合済み状態が黙って退行しないよう、ドキュメント契約テストで固定する。

#### FR8: 本 feature の変更封じ込め

**説明**: 本変更が触れるのは次のみ。`em-workflow/references/templates/spec-document.md`、`em-workflow/references/templates/requirements-document.md`、`em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`feature-docs/spec-file-set-completeness/**` 配下の成果物、`test-docs/spec-file-set-completeness/**` 配下の成果物、`tests/` 配下の新規または拡張されるテストモジュール。この列挙自体が、FR1〜FR5 がテンプレートに追加するものの一事例である。

#### FR9: 両レジストリのプラグインバージョンを 0.1.41 に bump

**説明**: 同一変更の一部として、`em-workflow/.claude-plugin/plugin.json` の `version` を `0.1.40` から `0.1.41` へ（patch）、ルートの `.claude-plugin/marketplace.json` の `plugins[]` のうち `name` が `em-workflow` のエントリを `0.1.40` から `0.1.41` へ変更する。`em-review` エントリには触れず、どちらのファイルの他のフィールドも変更しない。

## 5. 非機能要件

### 5.1 パフォーマンス要件

N/A — 本変更に実行時の振る舞いはなく、パフォーマンス目標は定義されていない。

### 5.2 セキュリティ要件

N/A — 本変更は 2 つの markdown テンプレートと Python の unittest モジュールに限られ、認証・認可・データ保護・入力検証の要件は定義されていない。

### 5.3 可用性要件

N/A — 稼働率・障害復旧時間の要件は定義されていない。

### 5.4 保守性要件

- NFR2（SSOT 非重複）: 既定メンバーシップの列挙は 2 つのテンプレートにのみ存在する。テンプレートごとに 1 つの記述で、それを再掲する第 3 のドキュメントを置かない。列挙された各エントリは、その成果物の生成を所有するドキュメント（`{T}.tests.yaml` については `implement-phase.md`、feature-docs 成果物については create-spec / create-plan / review / verify の各 phase ドキュメントと `references/phase-state.md`）を、ルールを複写する代わりに引用する。
- NFR3（両テンプレートのローカルなスタイル一貫性）: `spec-document.md` への追加は英語のままで、既存の `{placeholder}` 規約と `## ` / `### ` の見出し構造を用い、外側の fenced ```markdown ブロックの内側（外側ではない）に置く。`requirements-document.md` への追加は日本語のままで、`### N.M` の採番方式に従い、同様に fenced テンプレート本文の内側に置く。どちらの追加も、要件が述べる以上の根拠は載せない。
- NFR5（新規検証は否定証明付きの Python unittest ドキュメント契約テスト）: 新規検証は `tests/` 配下の Python `unittest` ドキュメント契約テストとして追加する（標準ライブラリのみ、サードパーティ import なし、`tests/test_*.py`）。リポジトリルートから `python3 -m unittest discover -s tests` で実行できる。本プロジェクトは build コマンド、format コマンド、E2E 基盤のいずれも定義していない。テストは `tests/test_recycled_task_id_consistency.py` が確立したリポジトリのパターンに従う。モジュールレベルのパス定数、見出しベースのセクション切り出し、散文アサーション用の `_normalize_ws` ヘルパー（生テキストはバイト同一性アサーションにのみ使用）、および新規 matcher ごとに最低 1 つの否定証明テスト（対応するテンプレートの変更前テキストを matcher が検出することを示す。決して失敗し得ないテストはテストではない）。retention matcher には否定証明は不要。

### 5.5 互換性要件

- NFR1（ドキュメントとテストのみの変更）: 実行される振る舞いは変わらない。`em-workflow/hooks/` および `em-workflow/scripts/` 配下のファイルは編集せず、`em-workflow/agents/` および `em-workflow/skills/` 配下のエージェントプロンプトやスキルも編集しない。成果物は 2 つのテンプレートドキュメント、本 feature の feature-docs 成果物、バージョン bump、新規テスト。
- NFR4（既存スイートは全既存モジュール無変更のままグリーン）: リポジトリルートから `python3 -m unittest discover -s tests` が、`tests/` 配下の既存モジュールをすべて無変更のまま通る。対象には `tests/test_reference_sweep.py`、`tests/test_check_plugin_invariants.py`、`tests/test_worker_contracts_create_spec.py`、`tests/test_worker_contract_docs.py`、`tests/test_recycled_task_id_consistency.py` を含む。現時点でどちらのテンプレートについても何かを表明している既存モジュールはないため、追加によってリポジトリ全体の参照スイープと invariant スイープも壊してはならない。
- NFR6（閉じた宣言を持たない SPEC への遡及的義務なし）: 閉じたファイル集合をまったく宣言していない SPEC は有効なままで、影響を受けない。本 feature が追加するものは、そのような SPEC を拒否せず、書き直しを要求せず、既に書かれたドキュメントに対して新セクションを必須にしない。テンプレート変更は、以後テンプレートから生成されるドキュメントに影響する。既存の feature-docs には触れない。

## 6. UI/UX要件

### 6.1 画面設計要件

N/A — 本変更にユーザーインターフェースはない。

### 6.2 画面遷移

N/A — 画面がないため画面遷移もない。

### 6.3 レスポンシブ対応

N/A — 画面がないため対象外。

## 7. データ要件

### 7.1 データモデル概要

N/A — 本変更に新しいデータモデルはない。

### 7.2 データ項目

N/A — 新しいデータ項目はない。

### 7.3 データ保持期間

N/A — 新しく保持するデータはない。

## 8. 外部連携

### 8.1 連携システム

N/A — 新しい外部連携はない。

### 8.2 API仕様要件

N/A — 新しい API はない。

## 9. 制約条件

### 9.1 技術的制約

- `em-workflow/references/implement-phase.md`、`review-phase.md`、`review-protocol.md`、`phases/create-spec-phase.md`、`phases/create-plan-phase.md`、`rework-task-synthesis.md`、`em-workflow/references/contracts/` 配下のすべて、`em-workflow/scripts/validate-worker-output.py`、`em-workflow/hooks/`、`em-workflow/agents/`、`em-workflow/skills/` 配下のすべては変更しない（FR6）。
- `feature-docs/recycled-task-id-consistency/SPEC.md` と `REQUIREMENTS.md` は変更しない（FR7）。
- 新規検証は標準ライブラリのみの Python `unittest` で、`python3 -m unittest discover -s tests` から実行できること（NFR5）。本プロジェクトは build コマンド、format コマンド、E2E 基盤を定義していない。
- 既存の `tests/` 配下モジュールはすべて無変更のままとする（NFR4）。

### 9.2 ビジネス上の制約

- 修正は spec-writer がレンダリングする 2 つのドキュメントテンプレートに置く。feature ごとの是正や verify 側の除外ルールで代替しない。
- 検証時に観測された変更集合から何も差し引かない。

### 9.3 スケジュール制約

N/A — スケジュール上の制約は定義されていない。

### 9.4 宣言された変更集合

本 feature の変更が触れるのは次のみ（FR8）。

- `em-workflow/references/templates/spec-document.md`
- `em-workflow/references/templates/requirements-document.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `feature-docs/spec-file-set-completeness/**`
- `test-docs/spec-file-set-completeness/**`
- `tests/` 配下の新規または拡張されるテストモジュール

この宣言は上位集合の主張であり、実際の変更集合はこれに CONTAINED IN であればよい。宣言されたパスが一度も実体化しなくても違反ではない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 既定を `test-docs/` のみに限定すると、SPEC 作成後に生成される feature-docs 成果物が宣言の外に残り、1 フェーズ遅れて同じ行き止まりを再現する | 高 | 既定を 2 ルート両方とする（FR3） |
| `### 9.4` をトップレベルセクションとして追加すると既存の番号が振り直される | 中 | `## 9. 制約条件` のサブセクションとして追加する（FR2） |
| 決して失敗し得ないテストを新規 matcher に付けてしまう | 中 | 新規 matcher ごとに否定証明テストを置く（NFR5、TS-13） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 閉じた宣言を持たない既存 SPEC に遡及的な義務が生じる | 低 | 中 | 新セクションを既存ドキュメントに必須化しない（NFR6、TS-12） |
| 既定メンバーシップの記述が第 3 のドキュメントに重複する | 低 | 中 | 記述は 2 つのテンプレートのみ（NFR2、TS-11） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1 (FR1): `em-workflow/references/templates/spec-document.md` が、fenced テンプレート本文の内側にトップレベル見出し `## Declared Change Set` を含み、その位置が `### File Structure` サブセクションの後かつ `## Test Scenarios` の前である。
- [ ] AC-2 (FR2): `em-workflow/references/templates/requirements-document.md` が `## 9. 制約条件` の下に `### 9.4 宣言された変更集合` を含み、既存のトップレベル見出し（`## 1. 概要` .. `## 15. 参考資料`）がすべて番号とタイトルを変えずに存在する。
- [ ] AC-3 (FR3): 新しい 2 つのセクションがいずれもリテラル `feature-docs/{feature}/**` と `test-docs/{feature}/**` を含む。
- [ ] AC-4 (FR4): 新しい 2 つのセクションがいずれも `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml` を feature-docs のメンバーとして、`{T}.tests.yaml` を test-docs のメンバーとして名指し、テスト記録については `implement-phase.md` を、feature-docs 成果物については phase ドキュメント／`references/phase-state.md` を、ルールの再掲ではなく引用として示す。
- [ ] AC-5 (FR5): 新しい 2 つのセクションがいずれも、既定エントリは明示的に削除されない限り残ること、実際の変更集合は宣言に CONTAINED IN でなければならないこと、一度も実体化しない宣言済みパスは違反ではないことを述べ、具体例として implement タスク 0 件の feature（`test-docs/{feature}/` が一切生成されない）を挙げる。
- [ ] AC-6 (FR6, NFR1): 本変更の `git diff --name-only` が、`em-workflow/references/` 配下では 2 つのテンプレートファイル以外のパスを挙げず、`em-workflow/hooks/`、`em-workflow/scripts/`、`em-workflow/agents/`、`em-workflow/skills/`、`em-workflow/references/contracts/` 配下のパスを挙げない。どのドキュメントも、検証時にワークフロー生成成果物を観測された変更集合から除外するルールを導入していない。
- [ ] AC-7 (FR7): 本変更の `git diff --name-only` が `feature-docs/recycled-task-id-consistency/` 配下のパスを挙げず、`feature-docs/recycled-task-id-consistency/SPEC.md` と `REQUIREMENTS.md` が変更封じ込めの記述に `test-docs/recycled-task-id-consistency/**` を依然として列挙していることをテストが表明する。
- [ ] AC-8 (FR8): 本変更の `git diff --name-only` が {`em-workflow/references/templates/spec-document.md`, `em-workflow/references/templates/requirements-document.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `feature-docs/spec-file-set-completeness/**`, `test-docs/spec-file-set-completeness/**`, `tests/` 配下の新規／拡張モジュール} の部分集合である。
- [ ] AC-9 (FR9): `em-workflow/.claude-plugin/plugin.json` が `"version": "0.1.41"` であり、`.claude-plugin/marketplace.json` の `em-workflow` エントリが `"version": "0.1.41"` である。`em-review` エントリは変更されていない。
- [ ] AC-10 (NFR2): リポジトリ全体の検索で、既定メンバーシップの列挙が 2 つのテンプレートにのみ見つかる。`em-workflow/references/`、`em-workflow/agents/`、`em-workflow/skills/` 配下の第 3 のドキュメントがそれを再掲していない。
- [ ] AC-11 (NFR3): どちらの追加もそのドキュメントの fenced テンプレート本文の内側にある。spec-document への追加は英語で `{placeholder}` 形式を用い、requirements-document への追加は日本語で `### N.M` の採番形式を用いる。
- [ ] AC-12 (NFR4): リポジトリルートから `python3 -m unittest discover -s tests` が、既存テストモジュールをすべてバイト単位で無変更のまま通る。
- [ ] AC-13 (NFR5): 新規テストモジュールが存在し、`unittest discover` に発見され、TS-1..TS-13 を実装し、Python 標準ライブラリ外を import せず、新規 matcher すべてに、変更前テンプレートテキストを検出する否定証明テストを持つ。
- [ ] AC-14 (NFR6): 本 feature が追加するテスト・ドキュメント・スクリプトのいずれも、既存 SPEC に新セクションを必須化せず、閉じたファイル集合を宣言しない SPEC を失敗させない。完了済み feature の既存 feature-docs はバイト単位で無変更のままである。

### 11.2 KPI

N/A — KPI は定義されていない。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系 TS-1 (FR1): `spec-document.md` に `## Declared Change Set` が存在し、その正規化後のインデックスが `### File Structure` より大きく `## Test Scenarios` より小さいことを表明する。
- [ ] 正常系 TS-2 (FR1, NFR3): 新しい SPEC テンプレートセクションが外側の fenced ```markdown ブロックの内側にある（そのオフセットが開始フェンスと終了フェンスの間に入る）ことを表明する。
- [ ] 正常系 TS-3 (FR2): `requirements-document.md` に `### 9.4 宣言された変更集合` が存在し、`### 9.3 スケジュール制約` の後かつ `## 10. 想定される課題とリスク` の前に位置することを表明する。
- [ ] 境界値 TS-4 (FR2): 既存のトップレベル見出し `## 1. 概要` .. `## 15. 参考資料` がすべて番号とタイトルを変えずに存在することを表明する（採番ガード）。
- [ ] 正常系 TS-5 (FR3): 新しい 2 つのセクションがいずれも `feature-docs/{feature}/**` と `test-docs/{feature}/**` を含むことを表明する。
- [ ] 正常系 TS-6 (FR4): 新しい 2 つのセクションがいずれも 8 つの feature-docs メンバーと `{T}.tests.yaml` の test-docs メンバーを列挙し、`implement-phase.md` を引用していることを表明する。
- [ ] 境界値 TS-7 (FR5): 新しい 2 つのセクションがいずれも「削除しない限り既定」のルールと封じ込め（等号ではなく部分集合）のルールを、implement タスク 0 件の非違反ケースを含めて述べていることを表明する。
- [ ] 異常系 TS-8 (FR6): `implement-phase.md`、`review-phase.md`、`review-protocol.md`、`phases/create-spec-phase.md`、`phases/create-plan-phase.md`、`rework-task-synthesis.md`、`references/contracts/*` のいずれも、ワークフロー生成成果物に対する verify 側の除外ルールを含まないことを表明する（そのようなルールの matcher に対する否定的アサーション）。
- [ ] 正常系 TS-9 (FR7): `feature-docs/recycled-task-id-consistency/SPEC.md` が FR8 と AC-8 に `test-docs/recycled-task-id-consistency/**` を依然として挙げ、`REQUIREMENTS.md` が対応する制約に依然として挙げていることを表明する（pin テスト。retention matcher であり否定証明は不要）。
- [ ] 正常系 TS-10 (FR9): 両レジストリが `0.1.41` であり、`em-review` の marketplace エントリが無変更であることを表明する。
- [ ] 異常系 TS-11 (NFR2): 既定メンバーシップの列挙が `em-workflow/**` 全体でちょうど 2 つのテンプレートファイルに現れることを表明する（重複ガード）。
- [ ] 異常系 TS-12 (NFR6): 本 feature が追加するどの matcher も `feature-docs/*/SPEC.md` 配下のファイルに必須セクション要件として適用されないことを表明する。Declared Change Set セクションを持たない SPEC は、本 feature が追加する何によっても検出されない。
- [ ] 異常系 TS-13 (NFR5): 否定証明。TS-1、TS-3、TS-5、TS-6、TS-7、TS-8 の各新規 matcher について、対応するテンプレートテキストのモジュールレベルに捕捉した変更前サンプルに対して実行し、不在を報告することを表明する。各サンプルは非空虚性をガードする。
- [ ] セキュリティ: N/A — 本変更にセキュリティ観点のテストシナリオは定義されていない。
- [ ] パフォーマンス: N/A — 本変更にパフォーマンス観点のテストシナリオは定義されていない。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 宣言された変更集合 (Declared Change Set) | SPEC / 要件定義書が宣言する、変更が触れてよいパスの集合。上位集合の主張であり、実際の変更集合はこれに CONTAINED IN でなければならない |
| 既定メンバーシップ | SPEC 作成者が明示的に削除しない限り、宣言された変更集合の一部であるエントリ。既定は `feature-docs/{feature}/**` と `test-docs/{feature}/**` |
| retention matcher | 既存の整合済み状態が保たれていることを表明する matcher。否定証明を必要としない |
| 否定証明 (negative proof) | 新規 matcher が、捕捉した変更前テキストに対して不在を報告することを示すテスト |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1 修正の置き場所（`fix-locus`、packet create-spec-q0001、`gate_id: create-spec.requirement-clarification` の batch codex 相談で解決。当該ポリシーは `record_as_assumption: true`。影響度: 高、可逆: はい）: 構造的な修正は SPEC / REQUIREMENTS テンプレートに、既定メンバーシップがワークフロー生成成果物を含む新しい「宣言された変更集合」セクションとして置く。封じ込め検証セマンティクスは今日のままとし、commit されたすべての成果物を実際の変更集合の一部として扱う（verify 側の除外なし）。
- [x] A2 既定集合の範囲（`workflow-artifact-set`、packet create-spec-q0001、同じ gate の batch codex 相談で解決。影響度: 高、可逆: はい）: 既定の宣言集合は `test-docs/{feature}/**` と `feature-docs/{feature}/**` の両方。後者は SPEC 作成後に生成される成果物（reviews/roundN.yaml、retrospect.yaml、VERIFICATION.md、tasks/、workflow.yaml、phase-state/）を覆う。
- [x] A3 完了済み feature の是正（`recycled-feature-remediation`、packet create-spec-q0001、同じ gate の batch codex 相談で解決。影響度: 低、可逆: はい）: `feature-docs/recycled-task-id-consistency/SPEC.md` と `REQUIREMENTS.md` は編集しない。整合済み状態はドキュメント契約テストでのみ固定する。
- [x] A4 バージョン bump（リポジトリ規約（ルート CLAUDE.md）。ベースリビジョンで両ファイルの現在値が 0.1.40 であることを確認済み。影響度: 低、可逆: はい）: プラグインバージョンを `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の `em-workflow` エントリの両方で 0.1.40 → 0.1.41 に上げる。
- [x] A5 変更の性質（修正の置き場所（A1）が 2 つの markdown テンプレートであることによる。影響度: 中、可逆: はい）: 本変更はドキュメントとテストのみ。hook、script、エージェントプロンプト、スキルの振る舞いは変わらない。
- [x] A6 新規検証の形式（本プロジェクトの唯一のテスト基盤が `python3 -m unittest discover -s tests` であることによる。影響度: 中、可逆: はい）: 新規検証は `tests/` 配下の Python `unittest` ドキュメント契約テストとし、標準ライブラリのみ、新規 matcher ごとに否定証明を備える。
- [x] A7 design ステップ（`references/batch-policies.yaml` が batch モードで `create-spec.design-step` を `decide_autonomously` で解決。本変更にはユーザーに見える面、UI、新しいアーキテクチャ、データモデルがない。影響度: 低、可逆: はい）: 本 feature では design ステップをスキップする。

### 14.2 未確認・保留事項

- 未確認・保留の事項はない（`status: tbd` の要件は 0 件）。

## 15. 参考資料

- `em-workflow/references/templates/spec-document.md`: 本 feature が `## Declared Change Set` を追加する SPEC テンプレート
- `em-workflow/references/templates/requirements-document.md`: 本 feature が `### 9.4 宣言された変更集合` を追加する要件定義書テンプレート
- `em-workflow/references/implement-phase.md`: `{T}.tests.yaml`（`tests_yaml_path` = `test-docs/{feature}/{T}.tests.yaml`）の生成を所有する
- `em-workflow/references/rework-task-synthesis.md`: SPEC 編集を `gate_id: rework.spec-change` に回す
- `em-workflow/references/phase-state.md`: feature-docs 配下の phase-state 成果物を所有する
- `feature-docs/recycled-task-id-consistency/SPEC.md`: FR8 / AC-8 に `test-docs/recycled-task-id-consistency/**` を列挙する既存の整合済み事例
- `tests/test_recycled_task_id_consistency.py`: 新規ドキュメント契約テストが従うリポジトリのパターン
