---
title: "threat-model-stride"
created_date: 2026-09-27
status: draft
---

# threat-model-stride - 要件定義書

## 1. 概要

### 1.1 背景
SDL の設計段階（脅威モデリング）を em-workflow の create-plan に組み込み、信頼境界の誤りを実装前に潰す。

### 1.2 目的
- 全機能を対象に一度は信頼境界を確認し、軽い機能に潜むセキュリティ上の問題を拾う
- 設計で決めた緩和策が実装とレビューまで追跡されるようにする

### 1.3 スコープ
対象:
- create-plan の implementation-planner による信頼境界の洗い出し（STRIDE）と `THREAT-MODEL.md` の出力（FR1〜FR5、FR10）
- planner の契約（`write_policy` / `digest_inputs` / `written_artifacts`）の更新（FR6）
- `THREAT-MODEL.md` テンプレートの追加と plan-writing スキルからの参照（FR7）
- review フェーズから security 観点の reviewer への `threat_model_path` の受け渡しと、緩和策の未実装の検出（FR8、FR9）
- em-workflow の version の minor を上げる（FR11）

対象外:
- rework での `THREAT-MODEL.md` の更新。rework-planner は変更しない（B4）
- 外部プラグイン vertex-review の変更（A5）
- em-review プラグイン（`em-review/skills/review-security/SKILL.md`）の変更と、その version の変更（A6）
- SPEC テンプレート（`references/templates/spec-document.md`）の変更（A9）
- task_description の『追加指示（起動引数）』（push と PR 作成、Codex への相談、Notion への記録）。走行時の指示として扱い、この機能の要件には含めない（A10）

## 2. ビジネス要件

### 2.1 ビジネス目標
- SDL の設計段階（脅威モデリング）を em-workflow の create-plan に組み込み、信頼境界の誤りを実装前に潰す
- 全機能を対象に一度は信頼境界を確認し、軽い機能に潜むセキュリティ上の問題を拾う
- 設計で決めた緩和策が実装とレビューまで追跡されるようにする

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 信頼境界の誤りが実装前に見つかる
- 設計で決めた緩和策が、タスクの受け入れ条件・`VERIFICATION.md`・review-security の検出対象まで追跡される

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | 信頼境界の洗い出しを全機能・全 tier で実行 | 信頼境界の洗い出し（STRIDE）を全機能・全 tier で必ず実行する | confirmed |
| FR2 | THREAT-MODEL.md の出力 | 信頼境界ごとに該当 STRIDE カテゴリの脅威と緩和策だけを書く独立文書を出力する | confirmed |
| FR3 | 信頼境界なしの記録 | 信頼境界・脅威が無い変更では結果の数行だけを書き、緩和策は作り出さない | confirmed |
| FR4 | domains は深さの調整に使う | domains を実行可否の判断に使わず、掘る深さの調整に使う | confirmed |
| FR5 | 緩和策の反映先 | 緩和策を tier に応じた反映先へ落とす | confirmed |
| FR6 | planner の契約更新 | planner の write_policy / digest_inputs / written_artifacts に THREAT-MODEL.md を加える | confirmed |
| FR7 | THREAT-MODEL.md テンプレート | テンプレートを追加し plan-writing から参照する | confirmed |
| FR8 | review-security への threat_model_path 受け渡し | security 観点の reviewer に threat_model_path を渡す | confirmed |
| FR9 | 緩和策の未実装の検出 | review-security の検出対象に緩和策の未実装を加える | confirmed |
| FR10 | SPEC との役割分担 | SPEC の Security Considerations と THREAT-MODEL.md の内容を重複させない | confirmed |
| FR11 | version を上げる | em-workflow の version の minor を上げる | confirmed |

### 4.2 機能詳細

#### FR1: 信頼境界の洗い出しを全機能・全 tier で実行

**説明**: implementation-planner は SPEC / REQUIREMENTS / DESIGN（minimal tier では TASK.md）を読んだ後、信頼境界の洗い出し（STRIDE）を全機能・全 tier（full / reduced / minimal）で必ず実行する。domains などの条件で省略しない。

#### FR2: THREAT-MODEL.md の出力

**説明**: `THREAT-MODEL.md` を `feature-docs/{feature}/` に独立した文書として出力する。信頼境界ごとに、該当する STRIDE カテゴリの脅威と緩和策だけを書き、6 カテゴリを機械的に埋めることはしない。分量は脅威の実在に比例させる。

#### FR3: 信頼境界なしの記録

**説明**: 信頼境界が無い変更、または該当する脅威が無い変更では、『信頼境界なし + 根拠』（または脅威なしの結果）の数行だけを書く。緩和策は作り出さない。

#### FR4: domains は深さの調整に使う

**説明**: domains（`auth` / `input-handling` / `external-io` / `data-persistence`）は実行するかどうかの判断に使わず、どこまで掘るかの調整に使う。

#### FR5: 緩和策の反映先

**説明**: 緩和策の反映先は tier で分ける。

| tier | 反映先 |
|------|--------|
| full / reduced | 各緩和策を実装するタスクの受け入れ条件と `VERIFICATION.md` の両方 |
| minimal | TASK.md の `## Expected Result` に、緩和策を検証可能な形で追記する |

minimal tier では TASK.md がタスクの受け入れ条件と verify の評価基準を兼ねる。TASK.md への追記を『AC と VERIFICATION.md の両方への反映』の minimal tier での代わりとして明記する。

#### FR6: planner の契約更新

**説明**: planner の `write_policy` と `digest_inputs` に `THREAT-MODEL.md` を追加し、`written_artifacts` にも含める。minimal tier では `write_policy` を広げ、create-spec が作った TASK.md の `## Expected Result` への追記を許可する。

**対象**:
- `planner-contract.md`
- `implementation-planner.md`
- `create-plan-phase.md`（dispatch と完了出力の記述）

#### FR7: THREAT-MODEL.md テンプレート

**説明**: `THREAT-MODEL.md` のテンプレートを追加し、plan-writing スキルから参照する。テンプレートは次の 2 つの形を持つ。
- 信頼境界ごとに該当 STRIDE カテゴリだけを書く形
- 『信頼境界なし + 根拠』の短い形

#### FR8: review-security への threat_model_path 受け渡し

**説明**:
- review フェーズ（`review-phase.md`）は、`THREAT-MODEL.md` が存在する場合、security 観点の reviewer に `threat_model_path` を渡す。
- `review-protocol.md` の `## Inputs (all reviewers)` 節に、`spec_path` と並べて `threat_model_path`（security 観点のみ）を追記する。同じ変更で `tests/test_reviewer_roles_protocol.py` の凍結ハッシュと `INPUT_FIELD_NAMES` を更新する。
- `codex-reviewer.md` は `threat_model_path` を Codex プロンプトに入れて渡す。

#### FR9: 緩和策の未実装の検出

**説明**: review-security スキルの検出対象に『設計で決めた緩和策が実装されていない』を追加する。

**ビジネスルール**:
- finding の `file` は、緩和策を実装すべき信頼境界のファイルを指す。
- 該当する行が無ければ `line` は null にする。
- confidence の上限を避けるために、無関係な changed file に付け替えてはいけない。

#### FR10: SPEC との役割分担

**説明**: 内容を重複させない。

| 文書 | 役割 |
|------|------|
| `SPEC.md` の Security Considerations | 何を守るか（要件・入力） |
| `THREAT-MODEL.md` | どう壊され、どう防ぐか（設計に対する分析・出力） |

#### FR11: version を上げる

**説明**: em-workflow の version の minor を上げる。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリを同じ値にする。具体的な値はコミット時点の HEAD から決める。

## 5. 非機能要件

| ID | 要件名 | 内容 | 状態 |
|----|--------|------|------|
| NFR1 | 出力量は脅威の実在に比例させる | 脅威が無い・少ない機能では `THREAT-MODEL.md` を短く保ち、全機能で実行するコストを抑える。 | confirmed |
| NFR2 | フェーズ・状態機械を変えない | 新しいフェーズ、ステップ、gate_id、batch-policies のエントリは追加しない。develop のステートマシン、phase-state、batch-mode、`--once` のフェーズ境界は変更しない。 | confirmed |
| NFR3 | 既存テストを壊さない | `python3 -m unittest discover -s tests` が通る状態を保つ。テストで固定された文字列は維持する。凍結ハッシュは FR8 の意図した更新だけに限る。 | confirmed |
| NFR4 | 入力の安全性 | `threat_model_path` は `spec_path` と同じパス検証（制御文字の拒否、project_root 配下への realpath 収まり、symlink の拒否）を通してから渡す。reviewer と Codex は `THREAT-MODEL.md` の内容を信頼できないデータとして扱う。 | confirmed |

### 5.1 パフォーマンス要件
NFR1 を参照。

### 5.2 セキュリティ要件
- 入力検証: NFR4 を参照。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
NFR3 を参照。

### 5.5 互換性要件
NFR2 を参照。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| Codex | `codex-reviewer.md` が Codex プロンプトに入れて渡す（FR8） | `threat_model_path` |
| vertex-review | `review-protocol.md` の Inputs に従う。このリポジトリでは変更しない（A5） | `threat_model_path` |

### 8.2 API仕様要件
該当なし

## 9. 制約条件

### 9.1 技術的制約
- 新しいフェーズ、ステップ、gate_id、batch-policies のエントリは追加しない（NFR2）
- develop のステートマシン、phase-state、batch-mode、`--once` のフェーズ境界は変更しない（NFR2）
- 凍結ハッシュの更新は FR8 の意図した更新だけに限る（NFR3）

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

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
| rework で生じた新しい信頼境界が `THREAT-MODEL.md` に反映される保証は無い（B4） | 中 | rework での更新はスコープ外とする。spec-change で create-plan に戻る経路では作り直される（B4） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: implementation-planner.md が、信頼境界の洗い出しを全機能・全 tier での必須手順として定め、domains を実行条件にしていない（FR1, FR4）
- [ ] AC2: THREAT-MODEL.md テンプレートが、信頼境界ごとに該当 STRIDE カテゴリだけを書く形と、『信頼境界なし + 根拠』の短い形を持ち、plan-writing から参照されている（FR2, FR3, FR7）
- [ ] AC3: planner / plan-writing に、緩和策を full / reduced では AC と VERIFICATION.md の両方へ、minimal では TASK.md の ## Expected Result へ反映する規則と、脅威が無ければ緩和策を作らない規則がある（FR3, FR5）
- [ ] AC4: planner-contract.md の write_policy と digest_inputs に THREAT-MODEL.md が含まれ、minimal tier の TASK.md への追記が write_policy として記述されている。create-plan-phase.md の dispatch と完了出力の記述にも THREAT-MODEL.md が含まれる（FR6）
- [ ] AC5: review-phase.md が、THREAT-MODEL.md が存在する場合に security 観点へ threat_model_path を spec_path と同等の検証を経て渡し、存在しない場合は渡さない（FR8, NFR4）
- [ ] AC6: review-protocol.md の Inputs 節に threat_model_path が記載され、tests/test_reviewer_roles_protocol.py の凍結ハッシュと INPUT_FIELD_NAMES が同じ変更で更新されている（FR8）
- [ ] AC7: review-security SKILL.md が、緩和策の未実装を検出対象に含め、指摘の位置の規則（信頼境界のファイル、line は null 可、無関係なファイルへ付け替えない）を持つ（FR9）
- [ ] AC8: codex-reviewer.md が threat_model_path を Codex プロンプトに渡す（FR8）
- [ ] AC9: SPEC の Security Considerations と THREAT-MODEL.md の役割分担が planner 側に明記されている（FR10）
- [ ] AC10: plugin.json と marketplace.json の em-workflow の version が同じ値で、base からの minor bump になっている（FR11）
- [ ] AC11: python3 -m unittest discover -s tests が通る（NFR3）

### 11.2 KPI
該当なし

## 12. テストシナリオ

| ID | シナリオ | 期待結果 | 種別 | 要件 |
|----|----------|----------|------|------|
| TS-1 | implementation-planner.md に、全機能・全 tier での信頼境界の洗い出しの必須化が書かれ、domains が実行条件として書かれていないことを文書契約テストで確認する | 必須化の記述があり、domains で間引く記述が無い | unit | FR1, FR4 |
| TS-2 | THREAT-MODEL.md テンプレートの存在、信頼境界ごとの該当 STRIDE だけの構造、『信頼境界なし + 根拠』の形、plan-writing からの参照を確認する | すべて満たす | unit | FR2, FR3, FR7 |
| TS-3 | plan-writing / implementation-planner.md に、tier ごとの緩和策の反映先（full / reduced は AC + VERIFICATION.md、minimal は TASK.md の ## Expected Result）と、緩和策を作り出さない規則があることを確認する | 規則が記述されている | unit | FR3, FR5 |
| TS-4 | planner-contract.md の write_policy と digest_inputs に THREAT-MODEL.md があり、minimal tier の TASK.md への追記が書かれていることを確認する。既存の節見出しの検査（tests/test_worker_contracts_planning.py）も通る | 含まれていて、既存のテストも通る | unit | FR6 |
| TS-5 | review-phase.md で、threat_model_path が security 観点のときだけ spec_path と同等の検証を経て渡され、THREAT-MODEL.md が無ければ渡されないことを確認する | 記述がある | unit | FR8, NFR4 |
| TS-6 | review-protocol.md の Inputs 節に threat_model_path があり、更新後の凍結ハッシュで tests/test_reviewer_roles_protocol.py が通る | テストが通る | unit | FR8, NFR3 |
| TS-7 | review-security SKILL.md に、緩和策の未実装の検出と、指摘の位置の規則があることを確認する | 記述がある | unit | FR9 |
| TS-8 | codex-reviewer.md に、threat_model_path を Codex プロンプトへ渡す記述があることを確認する | 記述がある | unit | FR8 |
| TS-9 | SPEC の Security Considerations と THREAT-MODEL.md の役割分担が planner 側の文書にあることを確認する | 記述がある | unit | FR10 |
| TS-10 | plugin.json と marketplace.json の em-workflow の version が一致し、base revision の値から minor が上がっていることを確認する | 一致していて、minor bump になっている | unit | FR11 |
| TS-11 | python3 -m unittest discover -s tests を実行する | 全テストが通る | integration | NFR3 |
| TS-12 | 既存の固定文字列（planner の '### 6. Populate requirements mapping (MANDATORY)'、review-phase.md の Phase 見出し、develop SKILL.md の Tier 削減表の語）が残っていることを既存のテストで確認する | 既存のテストが通る | unit | NFR2, NFR3 |
| TS-13 | 手動確認：NFR1（出力量は脅威の実在に比例）が THREAT-MODEL.md テンプレートと planner の手順に反映されていることを目視で確認する | 脅威が無いときに短く終わる形がテンプレートと手順にある | manual | NFR1 |

### 12.1 テスト観点
- [ ] 正常系: TS-1〜TS-10
- [ ] 異常系: TS-5（THREAT-MODEL.md が無いとき threat_model_path を渡さない）
- [ ] 境界値: 該当なし
- [ ] セキュリティ: TS-5（threat_model_path のパス検証）
- [ ] パフォーマンス: TS-13（NFR1）
- [ ] 回帰: TS-11、TS-12

## 13. 用語定義

該当なし

## 14. 確認事項

### 14.1 確認済み事項
batch 実行のため、ユーザーとの対話で確認した事項はない。次の事項は batch で解決した。

- [x] requirement.tier-coverage（B1）: 全 tier で脅威モデリングを実行する。minimal tier では planner の write_policy を広げ、TASK.md の ## Expected Result に緩和策を検証可能な形で追記し、これを AC + VERIFICATION.md の代わりとして明記する。脅威が無ければ結果だけを記録する。
- [x] requirement.missing-mitigation-finding-site（B2）: 緩和策の未実装の finding は、信頼境界を実装するファイルを file に指し、行が無ければ line は null。confidence の上限を避けるために無関係な changed file へ付け替えない。
- [x] requirement.review-protocol-frozen-inputs（B3）: threat_model_path は review-protocol.md の Inputs 節に追記し、凍結ハッシュと INPUT_FIELD_NAMES を同じ変更で更新する。
- [x] requirement.rework-threat-model（B4）: rework での THREAT-MODEL.md の更新はスコープ外とし、rework-planner は変更しない。rework で生じた新しい信頼境界が THREAT-MODEL.md に反映される保証は無い。spec-change で create-plan に戻る経路では作り直される。
- [x] design-step.recommendation（B5）: design step は推奨どおりスキップする。

### 14.2 前提（未確認）
| ID | 前提 | 影響度 |
|----|------|--------|
| A1 | THREAT-MODEL.md は feature-docs/{feature}/THREAT-MODEL.md（IMPLEMENTATION.md と同じディレクトリ）に置く。 | 低 |
| A2 | THREAT-MODEL.md が無い場合（この機能より前に計画した feature、standalone の /em-workflow:review）は threat_model_path を渡さない。review-security は従来どおり動き、THREAT-MODEL.md が無いこと自体は指摘しない。 | 中 |
| A3 | threat_model_path は perspective == security のときだけ渡す。orchestrator は spec_path と同じ検証をかけてから渡す。 | 中 |
| A4 | threat_model_path の Read は調査予算（changed_files 以外は 3 ファイルまで）に数えない。 | 低 |
| A5 | 外部プラグイン vertex-review は review-protocol.md の Inputs に従い、このリポジトリでは変更しない。 | 低 |
| A6 | em-review プラグイン（em-review/skills/review-security/SKILL.md）は変更せず、その version も上げない。 | 低 |
| A7 | em-workflow の version の minor を上げる（plugin.json と marketplace.json を同じ値に）。具体的な値は SPEC・計画・AC に書かず、コミット時点の HEAD から決める。 | 低 |
| A8 | 再計画のとき既存の THREAT-MODEL.md は、既存の create-plan.existing-files の判断（IMPLEMENTATION.md / tasks/ と同じ）に含めて扱う。新しい gate_id は追加しない。 | 中 |
| A9 | SPEC テンプレート（references/templates/spec-document.md）は変更しない。重複させない規則は planner / plan-writing / THREAT-MODEL.md テンプレート側に書く。 | 低 |
| A10 | task_description の『追加指示（起動引数）』（push と PR 作成、Codex への相談、Notion への記録）は走行時の指示として扱い、この機能の要件には含めない。 | 低 |

## 15. 参考資料

該当なし
