---
title: "rework-contract-drift"
created_date: 2026-08-24
status: draft
---

# rework-contract-drift - 要件定義書

## 1. 概要

### 1.1 背景

先行フィーチャー goal-vs-spec-divergence の verify-origin rework（task0027〜task0029）が、
producer と consumer の契約の食い違いを 4 件、新たに持ち込むか未解決のまま残した。その結果、
先行フィーチャーが開いたはずの SPEC 変更による再入経路が、apply 時に拒否されて実際には機能しない。

現在のテストスイート（2234 テスト、全緑）はこの 4 件のいずれも検出しない。`workflow-patch.md` は
テストから凍結 SHA でしか読まれておらず、それ自体が FR2 のずれが見逃された理由になっている。

証拠基盤は、ブランチ `em-workflow/goal-vs-spec-divergence/integration` のコミット範囲
`711a9519..53395562` と、`tmp/em-review-goal-vs-spec-rework/round1.yaml` のレビュー記録である
（前提 A8）。本フィーチャーの integration ブランチは、FR1〜FR4 が根拠とする行が `main` に存在しない
ため、その未マージブランチから作成されている。

### 1.2 目的

- BO1: goal-vs-spec-divergence の verify-origin rework が持ち込んだ／残した 4 件の
  producer/consumer 契約の破れを閉じ、先行フィーチャーが開いた SPEC 変更による再入経路が、
  apply 時に拒否されるのではなく端から端まで実際に機能する状態にする。
- BO2: ずれの発生源そのものを無くす。所有 SSOT から離れた場所に再掲されているルールを、
  所有者への引用に置き換え、所有者側の後の編集が古い写しを黙って残す事態を起こさないようにする。
- BO3: 閉じたずれをテストスイートが検出できる状態にする。現在のスイートは 4 件のいずれも検出しない。
  本フィーチャー後は、いずれかがリグレッションしたらテストが落ちなければならない。
- BO4: fail-closed の強度を維持する。無人 batch 実行が、セキュリティ関連またはライセンス関連の
  rework を SPEC.md の変更として自動分類できる状態を、どの変更も開いてはならない。

### 1.3 スコープ

対象は、機能要件 FR1〜FR11 が名指しする SSOT ドキュメント（`workflow-patch.md`、
`workflow-schema.md`、`question-resolution.md`、`question-packet-schema.md`、`phase-state.md`、
2 つの contract ドキュメント、1 つの SKILL.md）、1 つのエージェントプロンプト
（`implementation-planner.md`）、1 つの Python スクリプト（`validate-worker-output.py`）、
および標準ライブラリ `unittest` によるテストである。

画面・コンポーネント・スタイル・デザイントークンは一切作成も変更もしないため、
**デザインステップはスキップされている**。

FR3 について明示的にスコープ外かつ変更しないもの: SPEC.md、VERIFICATION.md のフォーマット、
`verification_index`、retrospect フェーズ、rework-planner。

除外事項として、却下された 2 件（フィクスチャ移行漏れとされた指摘、性能指摘 5 件）は、
すべての要件・受け入れ基準・テストシナリオから除外される（NFR7）。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| BO1 | goal-vs-spec-divergence の verify-origin rework（task0027〜task0029）が持ち込んだ／残した 4 件の producer/consumer 契約の破れを閉じ、SPEC 変更による再入経路を端から端まで機能させる |
| BO2 | ずれの発生源そのものを無くす。所有 SSOT から離れて再掲されたルールを所有者への引用に置き換え、所有者の編集が古い写しを黙って残せないようにする |
| BO3 | 閉じたずれをテストスイートで検出可能にする。現在は 4 件とも検出されない。以後はリグレッションがテストを落とす |
| BO4 | fail-closed の強度を保つ。無人 batch 実行がセキュリティ／ライセンス関連の rework を SPEC.md 変更へ自動分類できるようにはしない |

### 2.2 対象ユーザー

確定要件に対象ユーザーの定義は含まれていないため、本書では定義しない。

### 2.3 期待される効果

期待される効果はビジネス目標 BO1〜BO4 と同一であり、重複しては記載しない。

## 3. ユースケース

確定要件にユースケースの定義は含まれていない。本フィーチャーは画面を持たず、対象は SSOT
ドキュメント・エージェントプロンプト・検証スクリプト・テストであるため、ユースケース図および
画面を伴う基本フローは該当しない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 | 優先度（由来） |
|----|--------|------|----------------|
| FR1 | 再計画分岐のキーを、再掲ではなく workflow-patch.md の引用にする | ok | critical |
| FR2 | 再計画認可条件が origin_kind / origin_id の組を使う | ok | high |
| FR3 | verify-origin の failed_items が必須の category を持ち、fail-closed はゲート側に置く | ok | high |
| FR4 | finding_stable_id を origin_id にスキーマと全 consumer で改名する | ok | high |
| FR5 | ルール18の認可消費が復旧可能かつ冪等である | ok | medium |
| FR6 | origin_kind の閉じた語彙をバリデーターが強制する | ok | medium |
| FR7 | 破壊的な形状変更に対して phase-state の schema_version を明示的に解決する | ok | medium |
| FR8 | classification の再適用ルールを冪等性セクションに定義する | ok | medium |
| FR9 | direction 2 の独立性の主張を reversible 側の分岐と整合させる | ok | medium |
| FR10 | high-water mark の再掲を SSOT の引用に置き換える | ok | medium |
| FR11 | ルール18の phase-state への越境を Ownership boundary セクションが扱う | ok | medium |

未確定（`status: tbd`）の機能要件は存在しない。

### 4.2 機能詳細

#### FR1: 再計画分岐のキーを、再掲ではなく workflow-patch.md の引用にする

**状態**: ok（未確定理由: なし）

**要件**:
implementation-planner のプロンプト（`em-workflow/agents/implementation-planner.md:126-133`）は、
再計画条件の再掲をやめなければならない。2 つの task-id 採番分岐は、誤った
「`create-plan` が `needs_update`」というリテラルではなく、`references/workflow-patch.md` の
Re-planning path を引用してキーとする。この path は既に両方のケース（SPEC 変更遷移が実際に生成する
`pending` 状態を含む）をカバーしている。判断ルールの所有は `workflow-patch.md` のままとし、
引用するだけで複製しない。同じ変更の中で
`em-workflow/references/contracts/planner-contract.md:102` を同じ引用形式に揃え、
`tests/test_replanning_producer_alignment.py::TestImplementationPlannerTwoBranchAllocation::test_two_branches_present_keyed_on_create_plan_status`
を、現在バグを固定している `needs_update` リテラルの固定ではなく、所有者が定義する両方の path を
検証するよう更新する。オーケストレーターが path を渡す代替案は採用しない。planner に新しい
ディスパッチ入力フィールドは定義しない。

**由来**: task_description 項目 1（critical）

#### FR2: 再計画認可条件が origin_kind / origin_id の組を使う

**状態**: ok（未確定理由: なし）

**要件**:
未消費の再計画認可条件を所有する `em-workflow/references/workflow-patch.md:97-98` は、task0029 が
改名した後のフィールド名を示さなければならない。すなわち記録は `reason`、`origin_kind`、
`origin_id`、`recorded_at_commit` を持ち、いずれも非空である。古い `finding_stable_id` は削除する。
これはリポジトリに残る、フィクスチャ以外で最後の規範的な旧名の使用箇所である。同じ変更で、
`em-workflow/skills/develop/SKILL.md` に残る「中断理由と finding の `stable_id` を同じファイルに
記録する」という指示を、同じ `origin_kind` / `origin_id` の組に揃える。

**由来**: task_description 項目 2（high）

#### FR3: verify-origin の failed_items が必須の category を持ち、fail-closed はゲート側に置く

**状態**: ok（未確定理由: なし）

**要件**:
`workflow.yaml` の verify ステップの `failed_items` は、各エントリが必須の `category` を持つよう
構造化されなければならない。`category` の値は閉じた語彙
`comprehensive | spec | security | performance | architecture | license | unknown`
（レビュー観点の集合に fail-closed の番兵として `unknown` を加えたもの）から取る。

verify フェーズのオーケストレーターは、`failed_items` を記録するその時点で `category` を付与する。
付与の根拠は、失敗した VERIFICATION.md のシナリオと、そのシナリオが `verification_index` を通じて
対応づく要件 ID である。根拠が不十分・未対応・矛盾している場合、またはセキュリティ／ライセンスを
排除できない場合は、`unknown` を付与する。

fail-closed の中断は verify フェーズには置かない。verify は `unknown` を記録して当該ケースを分類
ゲートまで到達させる。verify 中に中断すると、goal-vs-spec-divergence SPEC の FR7
（「`gate_id: rework.spec-change` に到達するすべてのケースがゲートを通過する」）に違反する状態を
再現してしまうためである。

中断を行うのは**分類ゲート**である。ゲートは `security`、`license`、`unknown`、`category` の欠落、
読み取り不能、語彙外のいずれの場合も中断する。その文言の方向性は、direction 1 が既に用いている
上書き不可の文言と同じにする。`question-resolution.md` の direction 2 は、存在し得ないフィールドを
読むのではなく、`failed_items` の `category` の定義を**引用**する。

対象ドキュメント: `references/workflow-schema.md`、`skills/develop/SKILL.md` の verify ステップ 4、
`references/question-resolution.md`、`scripts/validate-worker-output.py`。

明示的にスコープ外かつ変更しないもの: SPEC.md、VERIFICATION.md のフォーマット、
`verification_index`、retrospect フェーズ、rework-planner。

**由来**: task_description 項目 3（high）

#### FR4: finding_stable_id を origin_id にスキーマと全 consumer で改名する

**状態**: ok（未確定理由: なし）

**要件**:
`em-workflow/references/question-packet-schema.md` の
`questions[].evidence[].finding_stable_id` を `origin_id` に改名しなければならない。そして
**同じ変更の中で**すべての consumer を揃える: `references/question-resolution.md`、
`references/contracts/rework-planner-contract.md`、`scripts/validate-worker-output.py`、
`references/fixtures/` 配下のフィクスチャ、および既存テストの全参照箇所。

組の定義（`origin_kind` -> `origin_id`）の所有は `references/rework-task-synthesis.md` の
Invariant 6 のままとし、パケットスキーマはこれを**引用**する。再掲はしない。

この要件は 1 つの変更の中で all-or-nothing である。パケットの producer と origin 検証の consumer が
フィールド名について食い違う中間状態は存在してはならない。既存フィールドの説明をその場で
広げる案は採用しない。本フィーチャーの中で最も影響範囲が広い項目である。

**由来**: task_description 項目 4（high）

#### FR5: ルール18の認可消費が復旧可能かつ冪等である

**状態**: ok（未確定理由: なし）

**要件**:
`references/workflow-patch.md:278` は、適用ルール 18 の認可消費をルール 15/16 の後に置いている。
そのため両者の間で中断が起きると「ちょうど一度だけ消費される」不変条件が壊れ、しかも復旧ルールが
定義されていない。ドキュメントは、そうした中断からの再開に対する復旧ルールと冪等性ルールを
定義しなければならない。

**由来**: task_description medium 項目 5

#### FR6: origin_kind の閉じた語彙をバリデーターが強制する

**状態**: ok（未確定理由: なし）

**要件**:
`scripts/validate-worker-output.py:738` は `origin_kind` を閉じた語彙に対して検証していない。
一方 `classification` は同じ変更でまさにその強制を獲得している。バリデーターは `origin_kind` の
閉じた語彙を強制し、この非対称を解消しなければならない。

**由来**: task_description medium 項目 6

#### FR7: 破壊的な形状変更に対して phase-state の schema_version を明示的に解決する

**状態**: ok（未確定理由: なし）

**要件**:
`references/phase-state.md:121` は、破壊的な形状変更（必須となった `origin_kind`/`origin_id` の組、
リストになった `classification`）をまたいで `schema_version` を 1 のままにしている。これは進行中
フィーチャーのディスク上の `rework.yaml` を黙って再入不能にする。

SPEC は次のちょうど 1 つによって、これを**明示的に**解決しなければならない: 既存のディスク上
記録に対する移行ルールの明記、バージョン 1 の記録が読み取り可能であり続ける互換性ルールの明記、
または根拠を伴うバージョン遷移。進行中の `rework.yaml` を黙って再入不能のまま残すことは、
受け入れ可能な結末ではない。

本項目は FR5〜FR11 の中で受け入れリスクが最も高く、medium スコープを受け入れる際にその旨が
明示的に条件づけられている。

**注**: 本フィーチャーの FR7 は、FR3 の中で引用している goal-vs-spec-divergence SPEC の FR7 とは
無関係である（前提 A4）。

**由来**: task_description medium 項目 7

#### FR8: classification の再適用ルールを冪等性セクションに定義する

**状態**: ok（未確定理由: なし）

**要件**:
`references/phase-state.md:138` は `classification` を冪等性セクションから外した結果、
`classification` を「再適用ルールが定義されていない唯一の append 型記録」にしてしまっている。
その再適用ルールを定義しなければならない。

**由来**: task_description medium 項目 8

#### FR9: direction 2 の独立性の主張を reversible 側の分岐と整合させる

**状態**: ok（未確定理由: なし）

**要件**:
`references/question-resolution.md:191` は worker 由来のフィールドに一切依存しないと宣言しているが、
これは同じ段落にある `assumptions[].reversible` の分岐と矛盾する。宣言と分岐が一致するよう、
矛盾を解消しなければならない。

**由来**: task_description medium 項目 9

#### FR10: high-water mark の再掲を SSOT の引用に置き換える

**状態**: ok（未確定理由: なし）

**要件**:
`agents/implementation-planner.md:132` は high-water mark を
`max(carried_task_ids union entries)` と再掲しており、SSOT の定義（retire 済み id を**含む**最大値）
と食い違っている。これは FR1 と同じ再掲ずれの類型であり、同じファイルに存在する。写しをその場で
訂正するのではなく、所有する定義を引用することで修正しなければならない。

**由来**: task_description medium 項目 10

#### FR11: ルール18の phase-state への越境を Ownership boundary セクションが扱う

**状態**: ok（未確定理由: なし）

**要件**:
`references/workflow-patch.md:275` のルール 18 は phase-state に越境しているが、同ドキュメントの
Ownership boundary セクションはこの越境に触れていない。同セクションはこの越境を扱わなければならない。

**由来**: task_description medium 項目 11

## 5. 非機能要件

### 5.1 非機能要件一覧

| ID | 名称 | 要件 |
|----|------|------|
| NFR1 | fail-closed のリグレッション禁止 | どの変更も、どこであれ fail-closed の強度を弱めてはならない。特に FR3 の経路は、無人 batch 実行がセキュリティ関連またはライセンス関連の rework を SPEC.md の変更として自動分類できる状態を残してはならない。新たに導入されるすべての分岐は、根拠が欠落・読み取り不能・語彙外である場合に中断へ解決する |
| NFR2 | 単一所有、再掲ではなく引用 | 本フィーチャーが触れるすべてのルールは、所有ドキュメントをちょうど 1 つ持つ。修正はずれた再掲を所有者への引用に置き換える（FR1、FR4、FR10）。どの修正も、他所が所有するルールの新たな再掲を持ち込まない |
| NFR3 | 協調改名の原子性 | FR4 の改名は 1 つの変更の中で all-or-nothing である。スキーマ・consumer・フィクスチャ・テストが一緒に動き、producer と consumer がフィールド名で食い違うコミット状態は存在しない |
| NFR4 | 訂正だけでなく検出 | FR1〜FR4 のそれぞれが、変更前のツリーに対して失敗するテストカバレッジを得る。現在のスイートは 4 件のいずれも検出しない。`workflow-patch.md` はテストから凍結 SHA でしか読まれておらず、それ自体が FR2 のずれが見逃された理由であるため、追加するカバレッジはライブのドキュメントを読まなければならない |
| NFR5 | プロジェクト自身のランナーでスイートが緑のまま | 変更後に `python3 -m unittest discover -s tests` が全件通る。テストコードはサードパーティ依存を追加しない（Python 3.14 標準ライブラリの `unittest` のみ） |
| NFR6 | プラグインのバージョン更新 | `em-workflow/` 配下のファイルが変わるため、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` とリポジトリルートの `.claude-plugin/marketplace.json` の該当エントリの**両方**を、**同じ値**に引き上げなければならない。既存ドキュメントとスクリプトの挙動修正であるため、patch レベルの更新が想定される刻み幅である。他のプラグインのバージョンは動かさない |
| NFR7 | 却下された指摘は入れない | 却下された 2 件（フィクスチャ移行漏れとされた指摘、性能指摘 5 件）は、すべての要件・受け入れ基準・テストシナリオから除外され、以降のどのフェーズでも再導入してはならない |

### 5.2 テンプレート既定項目の適用可否

| テンプレート項目 | 適用 |
|------------------|------|
| パフォーマンス要件 | 該当なし。性能に関する確定要件はなく、性能指摘 5 件は NFR7 により除外されている |
| セキュリティ要件 | NFR1（fail-closed の非後退）に集約される。認証・認可・データ保護の要件はない。入力検証は FR3（`failed_items[].category`）と FR6（`origin_kind` の閉じた語彙）としてバリデーターに置かれる |
| 可用性要件 | 該当なし。稼働率・障害復旧時間の目標は確定要件に含まれない |
| 保守性要件 | NFR2（単一所有・引用）、NFR4（検出）、NFR5（スイート維持）に集約される |
| 互換性要件 | ブラウザ・API バージョンの要件はない。ディスク上記録の互換性は FR7（`schema_version`）として機能要件で扱う |

## 6. UI/UX要件

該当なし。**デザインステップはスキップされている**。理由は、UI 面がまったく存在しないためである。
変更対象は Markdown の SSOT ドキュメント（`workflow-patch.md`、`workflow-schema.md`、
`question-resolution.md`、`question-packet-schema.md`、`phase-state.md`、2 つの contract
ドキュメント、1 つの SKILL.md）、1 つのエージェントプロンプト（`implementation-planner.md`）、
1 つの Python スクリプト（`validate-worker-output.py`）、標準ライブラリ `unittest` のテストに限られ、
画面・コンポーネント・スタイル・デザイントークンは作成も変更もされない。画面遷移およびレスポンシブ
対応も同じ理由で該当しない。

## 7. データ要件

データベースは存在しない。エンティティ定義・データ項目・保持期間は該当しない。ディスク上の記録の
形状変更（`rework.yaml` の `schema_version` と `classification`）は、データ要件ではなく機能要件
FR7・FR8 として扱う。

## 8. 外部連携

該当なし。外部システム連携はない。テストコードはサードパーティ依存を追加しない。
`validate-worker-output.py` は PyYAML を使い続けてよいが、これはプラグインのランタイム依存であり、
テスト依存ではない（前提 A7）。

## 9. 制約条件

### 9.1 技術的制約

- テストは Python 3.14 標準ライブラリの `unittest` のみを用い、サードパーティ依存を追加しない（NFR5、A7）。
- 変更後に `python3 -m unittest discover -s tests` が全件通ること（NFR5）。
- 追加するカバレッジは凍結 SHA ではなくライブのドキュメントを読むこと（NFR4）。
- FR4 の改名は 1 つの変更の中で完結し、producer と consumer が食い違う中間状態を作らない（NFR3）。
- `em-workflow/` 配下が変わるため、`em-workflow/.claude-plugin/plugin.json` とルートの
  `.claude-plugin/marketplace.json` を同じ値に引き上げる（NFR6、A2）。ユーザーへの報告には、
  反映に Claude Code の再起動が必要である旨を添える。
- プラグインは `em-workflow/` 配下の全ファイルをユーザーのキャッシュへ配布するため、プラグイン
  ディレクトリ内に置いたテストや開発用ファイルも配布される。リポジトリルートの `tests/` は
  プラグイン外であり配布されない（A6）。
- 新しいスラッシュコマンドは作らない。コマンド形状のものが必要になった場合は
  `em-workflow/skills/<name>/SKILL.md` として追加し、`commands/` 配下には置かない（A5）。
- `em-workflow/hooks/destructive-guard.py` は本フィーチャーでは触らない想定である。触る場合は同じ
  変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行し、新たに見つかった
  誤爆や見逃しは修正の**前に** `em-workflow/hooks/tests/destructive-guard-cases.json` にケースを
  追加する（A3）。

### 9.2 ビジネス上の制約

- fail-closed の強度をどこでも弱めない。特に、無人 batch 実行がセキュリティ関連または
  ライセンス関連の rework を SPEC.md の変更として自動分類できるようにはしない（BO4、NFR1）。
- 却下された 2 件（フィクスチャ移行漏れとされた指摘、性能指摘 5 件）を、要件・受け入れ基準・
  テストシナリオのいずれにも入れない（NFR7）。
- FR3 のスコープ外（SPEC.md、VERIFICATION.md フォーマット、`verification_index`、retrospect
  フェーズ、rework-planner）を変更しない。

### 9.3 スケジュール制約

確定要件にスケジュール制約の記載はない。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files`
から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/rework-contract-drift/**`
- `test-docs/rework-contract-drift/**`

`feature-docs/rework-contract-drift/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、
`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、
`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は
各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/rework-contract-drift/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/rework-contract-drift/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照
（引用のみ、ルールは再掲しない）。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みで
  あり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）
  必要がある。実際には生成されないパスが宣言されていても違反にはならない。implement タスクを 1 つも
  生成しないフィーチャーは `test-docs/rework-contract-drift/` ディレクトリを生成しないが、宣言された
  `test-docs/rework-contract-drift/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 出典 | 対応策 |
|------|------|--------|
| FR4 の改名は本フィーチャーで最も影響範囲が広く、producer と consumer が食い違う中間状態を作りうる | FR4、NFR3 | 1 つの変更の中で all-or-nothing にする。スキーマ・consumer・フィクスチャ・テストを同時に動かす |
| FR7 は FR5〜FR11 の中で受け入れリスクが最も高い（medium スコープ受け入れ時に明示的に条件づけられた） | FR7 | 移行ルール・互換性ルール・根拠を伴うバージョン遷移のちょうど 1 つを SPEC で明示的に選ぶ。黙って再入不能のまま残さない |
| 現在のスイート（2234 テスト、全緑）は 4 件のいずれも検出しない。`workflow-patch.md` は凍結 SHA でしか読まれておらず、それが FR2 のずれを見逃した原因 | BO3、NFR4 | 追加するカバレッジはライブのドキュメントを読む。FR1〜FR4 それぞれが変更前ツリーに対して失敗するテストを得る |
| FR3 の変更が、verify 中の中断によって goal-vs-spec-divergence SPEC の FR7（ゲート通過の不変条件）を再び破りうる | FR3 | verify は `unknown` を記録して分類ゲートまで到達させ、中断は分類ゲート側だけで行う |

### 10.2 ビジネスリスク

| リスク | 出典 | 対応策 |
|--------|------|--------|
| fail-closed の強度が後退し、無人 batch 実行がセキュリティ／ライセンス関連の rework を SPEC.md 変更として自動分類してしまう | BO4、NFR1 | 新たに導入するすべての分岐を、根拠が欠落・読み取り不能・語彙外のときに中断へ解決させる |
| 「FR7」という番号がドキュメント間で曖昧になり、別々の要件が同一のものとして読まれる | A4 | 下流ドキュメントは、各 FR 番号がどの SPEC に属するかを明示的に限定して書く |
| 却下された指摘（フィクスチャ移行漏れ、性能指摘 5 件）が後のフェーズで再導入される | NFR7 | 要件・受け入れ基準・テストシナリオから除外した状態を維持する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `agents/implementation-planner.md` と `contracts/planner-contract.md` に
      `needs_update` をキーとする再計画条件が残っていない。両者とも
      `references/workflow-patch.md` の Re-planning path を引用している。
- [ ] AC2: `test_replanning_producer_alignment.py` の二分岐テストが、所有者が定義する両方の path を
      検証し、`needs_update` リテラルの固定をやめている。変更前のプロンプトに対しては失敗する。
- [ ] AC3: `finding_stable_id` が履歴以外のリポジトリ内のどこにも現れない。`workflow-patch.md`、
      `skills/develop/SKILL.md`、`question-packet-schema.md`、`question-resolution.md`、
      `rework-planner-contract.md`、`validate-worker-output.py`、`references/fixtures/`、
      `tests/` のいずれにも無い。
- [ ] AC4: `references/workflow-schema.md` が `failed_items[].category` を必須として、閉じた語彙
      `comprehensive | spec | security | performance | architecture | license | unknown`
      とともに定義している。
- [ ] AC5: `question-resolution.md` の direction 2 がその定義を引用し、`security`、`license`、
      `unknown`、欠落、読み取り不能、語彙外に対するゲート側の中断を、direction 1 が用いるのと同じ
      上書き不可の文言で述べている。
- [ ] AC6: category が `unknown` の verify-origin ケースが分類ゲートに**到達する**（verify フェーズは
      中断しない）。そしてゲートがそれを中断する。
- [ ] AC7: SPEC.md、VERIFICATION.md のフォーマット、`verification_index`、retrospect フェーズ、
      rework-planner は FR3 によって変更されていない。
- [ ] AC8: `validate-worker-output.py` が語彙外の `origin_kind` を拒否し、語彙外または欠落した
      `failed_items[].category` を拒否する。
- [ ] AC9: SPEC が FR7 に対する明示的で名前のついた解決（移行ルール、互換性ルール、または根拠を
      伴うバージョン遷移）を含み、`schema_version: 1` で書かれた既存のディスク上 `rework.yaml` が
      どうなるかを述べている。
- [ ] AC10: `python3 -m unittest discover -s tests` が全件緑であり、
      `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` が同じ引き上げ後の
      バージョンを持つ。

### 11.2 KPI

確定要件に KPI の定義は含まれていない。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | シナリオ | 対応要件 |
|----|----------|----------|
| TS1 | 変更前は赤・変更後は緑: planner プロンプトの 2 分岐が workflow-patch.md の Re-planning path をキーにしていることを検証する。現在のプロンプトに対しては失敗する | FR1 |
| TS2 | SPEC 変更遷移の create-plan patch（`create-plan` が `pending`、マージ済みタスクが 1 件以上）を `validate-worker-output.py --dry-run-apply` に通すと受理され、`replace-all-entry-for-registered-id` も `replace-all-drops-task` も発火しない | FR1 |
| TS3 | 規範ドキュメント・フィクスチャ・テストをまたぐ `finding_stable_id` のリポジトリ全体の不在スキャン。凍結 SHA ではなくライブのファイルを読む | FR2, FR4, NFR4 |
| TS4 | `workflow-patch.md` の認可条件を**ライブの**ドキュメントから読み、`origin_kind` と `origin_id` を名指ししていることを検証する。凍結 SHA 読みこそが FR2 を 2234 テストのスイートからすり抜けさせた原因である | FR2, NFR4 |
| TS5 | バリデーターが `category` の欠落・空・語彙外の `failed_items` エントリを拒否し、語彙の 7 値それぞれを受理する | FR3 |
| TS6 | ゲート挙動の表: `security` -> 中断、`license` -> 中断、`unknown` -> 中断、欠落 -> 中断、読み取り不能 -> 中断、語彙外 -> 中断。`comprehensive` / `spec` / `performance` / `architecture` -> 分類へ進む | FR3, NFR1 |
| TS7 | 改名後のスキーマに沿って作られた verify-origin の question packet が origin 検証のステップ 3 を通過する（`evidence[].origin_id` を持つ）。変更前の producer はこのフィールドを欠き、中断していた | FR4 |
| TS8 | バリデーターが語彙外の `origin_kind` を拒否する。既存の `classification` 語彙テストと同じ形にする | FR6 |
| TS9 | 変更前の形状で書かれた `rework.yaml` が、FR7 で選ばれた解決の通りに扱われる（移行される、互換性のために受理される、または述べられたバージョン遷移の診断とともに拒否される）。黙って再入不能になることは決してない | FR7 |

性能テストは該当しない（性能に関する確定要件はなく、性能指摘 5 件は NFR7 により除外）。
E2E テストも該当しない（E2E の基盤を持たない）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 本 SPEC の FR7 | 本フィーチャー rework-contract-drift の FR7。phase-state の `schema_version` に関する要件 |
| goal-vs-spec-divergence SPEC の FR7 | 先行フィーチャーの FR7。「`gate_id: rework.spec-change` に到達するすべてのケースがゲートを通過する」というゲート通過の不変条件。本 SPEC の FR3 の根拠として引用される。本 SPEC の FR7 とは別の要件である（前提 A4） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1（可逆）: batch ポリシーの `record_as_assumption` に従って記録。FR1 の方針 (a)、FR4 の
      `rename_to_origin_id`、medium スコープの `all_seven` は、Codex への相談結果を既存の option id へ
      対応づける形で解決し、その対応づけはオーケストレーターが判断した。FR3 はユーザーが直接決定した。
- [x] A2（可逆）: `em-workflow/` 配下のファイルが変わるため、バージョン更新の義務（NFR6）が適用される。
      `em-workflow/.claude-plugin/plugin.json` とルートの `.claude-plugin/marketplace.json` エントリを、
      同じ値で、同じ変更の中で更新する。ユーザーへの報告には、反映に Claude Code の再起動が必要である
      旨を含める。
- [x] A3（可逆）: `em-workflow/hooks/destructive-guard.py` は本フィーチャーでは触らない想定。触る場合は
      同じ変更で専用ランナー（`python3 em-workflow/hooks/tests/run-destructive-guard.py`）を実行し、
      新たに見つかった誤爆・見逃しは修正の**前に**
      `em-workflow/hooks/tests/destructive-guard-cases.json` にケースを追加する。
- [x] A4（可逆）: 本フィーチャーにおいて「FR7」はドキュメント間で曖昧である。FR3 の根拠が引用する
      goal-vs-spec-divergence SPEC の FR7（ゲート通過の不変条件）は、本フィーチャーの FR7
      （phase-state の `schema_version`）とは**別の**要件である。下流ドキュメントは、各 FR 番号が
      どの SPEC に属するかを限定して書かなければならない。
- [x] A5（可逆）: 新しいスラッシュコマンドは作らない。コマンド形状のものは
      `em-workflow/skills/<name>/SKILL.md` として追加し、`commands/` 配下には決して置かない。
- [x] A6（可逆）: プラグインは `em-workflow/` 配下の全ファイルをユーザーのキャッシュへ配布するため、
      プラグインディレクトリ内に追加したテストや開発用ファイルも配布される。リポジトリルートの
      `tests/` はプラグイン外であり配布されない。
- [x] A7（可逆）: テストコードはサードパーティ依存を追加しない。`validate-worker-output.py` は PyYAML を
      使い続けてよい。これはプラグインのランタイム依存であり、テスト依存ではない。
- [x] A8（可逆）: ブランチ `em-workflow/goal-vs-spec-divergence/integration` のコミット範囲
      `711a9519..53395562` と、`tmp/em-review-goal-vs-spec-rework/round1.yaml` のレビュー記録が
      FR1〜FR11 の証拠基盤である。本フィーチャーの integration ブランチは、FR1〜FR4 が根拠とする行が
      `main` に存在しないため、その未マージブランチから作成された。

### 14.2 未確認・保留事項

未確定（`status: tbd`）の要件はない。FR1〜FR11、NFR1〜NFR7 はすべて確定済みである。

## 15. 参考資料

- `em-workflow/references/workflow-patch.md`: 再計画 path、認可条件、適用ルール 15/16/18、
  Ownership boundary セクションの所有ドキュメント（FR1、FR2、FR5、FR11）
- `em-workflow/references/workflow-schema.md`: `failed_items[].category` の定義先（FR3）
- `em-workflow/references/question-resolution.md`: direction 1 / direction 2（FR3、FR4、FR9）
- `em-workflow/references/question-packet-schema.md`: `questions[].evidence[]` のスキーマ（FR4）
- `em-workflow/references/phase-state.md`: `schema_version` と冪等性セクション（FR7、FR8）
- `em-workflow/references/rework-task-synthesis.md` Invariant 6: `origin_kind` -> `origin_id` の
  組の定義の所有者（FR4）
- `em-workflow/references/contracts/planner-contract.md`（FR1）
- `em-workflow/references/contracts/rework-planner-contract.md`（FR4）
- `em-workflow/agents/implementation-planner.md`（FR1、FR10）
- `em-workflow/skills/develop/SKILL.md`: verify ステップ 4 と再計画認可の記録指示（FR2、FR3）
- `em-workflow/scripts/validate-worker-output.py`（FR3、FR4、FR6）
- `em-workflow/references/fixtures/`（FR4）
- `tests/test_replanning_producer_alignment.py`（FR1）
- `em-workflow/references/phases/create-plan-phase.md`: 宣言された変更集合の導出元（9.4）
- ブランチ `em-workflow/goal-vs-spec-divergence/integration` のコミット範囲
  `711a9519..53395562`: 証拠基盤（A8）
- `tmp/em-review-goal-vs-spec-rework/round1.yaml`: レビュー記録、証拠基盤（A8）
