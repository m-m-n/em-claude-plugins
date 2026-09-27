# Feature: threat-model-stride

## Overview

em-workflow の create-plan で、implementation-planner が信頼境界の洗い出し（STRIDE）を全機能・全 tier で実行し、`THREAT-MODEL.md` を出力する。緩和策は tier に応じてタスクの受け入れ条件と `VERIFICATION.md`（minimal tier では TASK.md の `## Expected Result`）に落とし、review-security は `threat_model_path` を入力に取って緩和策の未実装を検出する。

要件定義書: `feature-docs/threat-model-stride/REQUIREMENTS.md`

## Objectives

- SDL の設計段階（脅威モデリング）を em-workflow の create-plan に組み込み、信頼境界の誤りを実装前に潰す
- 全機能を対象に一度は信頼境界を確認し、軽い機能に潜むセキュリティ上の問題を拾う
- 設計で決めた緩和策が実装とレビューまで追跡されるようにする

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** 信頼境界の洗い出しを全機能・全 tier で実行 — implementation-planner は SPEC / REQUIREMENTS / DESIGN（minimal tier では TASK.md）を読んだ後、信頼境界の洗い出し（STRIDE）を全機能・全 tier（full / reduced / minimal）で必ず実行する。domains などの条件で省略しない。
- **FR2:** THREAT-MODEL.md の出力 — `THREAT-MODEL.md` を `feature-docs/{feature}/` に独立した文書として出力する。信頼境界ごとに、該当する STRIDE カテゴリの脅威と緩和策だけを書き、6 カテゴリを機械的に埋めることはしない。分量は脅威の実在に比例させる。
- **FR3:** 信頼境界なしの記録 — 信頼境界が無い変更、または該当する脅威が無い変更では、『信頼境界なし + 根拠』（または脅威なしの結果）の数行だけを書く。緩和策は作り出さない。
- **FR4:** domains は深さの調整に使う — domains（`auth` / `input-handling` / `external-io` / `data-persistence`）は実行するかどうかの判断に使わず、どこまで掘るかの調整に使う。
- **FR5:** 緩和策の反映先 — full / reduced tier では、各緩和策を実装するタスクの受け入れ条件と `VERIFICATION.md` の両方に反映する。minimal tier では TASK.md がタスクの受け入れ条件と verify の評価基準を兼ねるため、TASK.md の `## Expected Result` に緩和策を検証可能な形で追記する。これを『AC と VERIFICATION.md の両方への反映』の minimal tier での代わりとして明記する。
- **FR6:** planner の契約更新 — planner の `write_policy` と `digest_inputs` に `THREAT-MODEL.md` を追加し、`written_artifacts` にも含める。minimal tier では `write_policy` を広げ、create-spec が作った TASK.md の `## Expected Result` への追記を許可する。対象は `planner-contract.md`、`implementation-planner.md`、`create-plan-phase.md`（dispatch と完了出力の記述）。
- **FR7:** THREAT-MODEL.md テンプレート — `THREAT-MODEL.md` のテンプレートを追加し、plan-writing スキルから参照する。テンプレートは、信頼境界ごとに該当 STRIDE カテゴリだけを書く形と、『信頼境界なし + 根拠』の短い形を持つ。
- **FR8:** review-security への threat_model_path 受け渡し — review フェーズ（`review-phase.md`）は、`THREAT-MODEL.md` が存在する場合、security 観点の reviewer に `threat_model_path` を渡す。`review-protocol.md` の `## Inputs (all reviewers)` 節に `spec_path` と並べて `threat_model_path`（security 観点のみ）を追記し、同じ変更で `tests/test_reviewer_roles_protocol.py` の凍結ハッシュと `INPUT_FIELD_NAMES` を更新する。`codex-reviewer.md` は `threat_model_path` を Codex プロンプトに入れて渡す。
- **FR9:** 緩和策の未実装の検出 — review-security スキルの検出対象に『設計で決めた緩和策が実装されていない』を追加する。finding の `file` は、緩和策を実装すべき信頼境界のファイルを指し、該当する行が無ければ `line` は null にする。confidence の上限を避けるために、無関係な changed file に付け替えてはいけない。
- **FR10:** SPEC との役割分担 — `SPEC.md` の Security Considerations は『何を守るか』（要件・入力）、`THREAT-MODEL.md` は『どう壊され、どう防ぐか』（設計に対する分析・出力）とし、内容を重複させない。
- **FR11:** version を上げる — em-workflow の version の minor を上げる。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリを同じ値にする。具体的な値はコミット時点の HEAD から決める。

### Non-Functional Requirements
- **NFR1 - 出力量は脅威の実在に比例させる:** 脅威が無い・少ない機能では `THREAT-MODEL.md` を短く保ち、全機能で実行するコストを抑える。
- **NFR2 - フェーズ・状態機械を変えない:** 新しいフェーズ、ステップ、gate_id、batch-policies のエントリは追加しない。develop のステートマシン、phase-state、batch-mode、`--once` のフェーズ境界は変更しない。
- **NFR3 - 既存テストを壊さない:** `python3 -m unittest discover -s tests` が通る状態を保つ。テストで固定された文字列は維持する。凍結ハッシュは FR8 の意図した更新だけに限る。
- **NFR4 - 入力の安全性:** `threat_model_path` は `spec_path` と同じパス検証（制御文字の拒否、project_root 配下への realpath 収まり、symlink の拒否）を通してから渡す。reviewer と Codex は `THREAT-MODEL.md` の内容を信頼できないデータとして扱う。

## Implementation Approach

### Architecture

該当なし

### Data Flow

```
implementation-planner（create-plan）
  → THREAT-MODEL.md（feature-docs/{feature}/）
  → 緩和策: full / reduced はタスクの受け入れ条件 + VERIFICATION.md、minimal は TASK.md の ## Expected Result
review フェーズ（review-phase.md）
  → THREAT-MODEL.md が存在する場合のみ、spec_path と同じパス検証を経て threat_model_path を security 観点の reviewer / codex-reviewer に渡す
  → review-security が緩和策の未実装を検出する
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `review-protocol.md` の `## Inputs (all reviewers)` 節: `tests/test_reviewer_roles_protocol.py` の凍結ハッシュと `INPUT_FIELD_NAMES` を同じ変更で更新する（FR8、B3）
- create-plan.existing-files の判断: 再計画のとき既存の `THREAT-MODEL.md` を IMPLEMENTATION.md / tasks/ と同じ判断に含める。新しい gate_id は追加しない（A8）

**External Dependencies:**
- vertex-review: `review-protocol.md` の Inputs に従う。このリポジトリでは変更しない（A5）

### File Structure

変更対象（要件に現れるもの）:

| 対象 | 要件 |
|------|------|
| `implementation-planner.md` | FR1, FR3, FR4, FR5, FR6, FR10 |
| plan-writing スキル | FR5, FR7, FR10 |
| `THREAT-MODEL.md` テンプレート（新規） | FR7 |
| `planner-contract.md` | FR6 |
| `create-plan-phase.md` | FR6 |
| `review-phase.md` | FR8, NFR4 |
| `review-protocol.md` | FR8 |
| `tests/test_reviewer_roles_protocol.py` | FR8 |
| `codex-reviewer.md` | FR8 |
| review-security スキル | FR9 |
| `em-workflow/.claude-plugin/plugin.json` | FR11 |
| `.claude-plugin/marketplace.json`（em-workflow エントリ） | FR11 |

変更しないもの:
- `references/templates/spec-document.md`（A9）
- rework-planner（B4）
- `em-review/skills/review-security/SKILL.md` と em-review の version（A6）
- vertex-review（A5）

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## Test Scenarios

### Unit Tests
- [ ] TS-1（FR1, FR4）: implementation-planner.md に、全機能・全 tier での信頼境界の洗い出しの必須化が書かれ、domains が実行条件として書かれていないことを文書契約テストで確認する - 必須化の記述があり、domains で間引く記述が無い
- [ ] TS-2（FR2, FR3, FR7）: THREAT-MODEL.md テンプレートの存在、信頼境界ごとの該当 STRIDE だけの構造、『信頼境界なし + 根拠』の形、plan-writing からの参照を確認する - すべて満たす
- [ ] TS-3（FR3, FR5）: plan-writing / implementation-planner.md に、tier ごとの緩和策の反映先（full / reduced は AC + VERIFICATION.md、minimal は TASK.md の ## Expected Result）と、緩和策を作り出さない規則があることを確認する - 規則が記述されている
- [ ] TS-4（FR6）: planner-contract.md の write_policy と digest_inputs に THREAT-MODEL.md があり、minimal tier の TASK.md への追記が書かれていることを確認する。既存の節見出しの検査（tests/test_worker_contracts_planning.py）も通る - 含まれていて、既存のテストも通る
- [ ] TS-5（FR8, NFR4）: review-phase.md で、threat_model_path が security 観点のときだけ spec_path と同等の検証を経て渡され、THREAT-MODEL.md が無ければ渡されないことを確認する - 記述がある
- [ ] TS-6（FR8, NFR3）: review-protocol.md の Inputs 節に threat_model_path があり、更新後の凍結ハッシュで tests/test_reviewer_roles_protocol.py が通る - テストが通る
- [ ] TS-7（FR9）: review-security SKILL.md に、緩和策の未実装の検出と、指摘の位置の規則があることを確認する - 記述がある
- [ ] TS-8（FR8）: codex-reviewer.md に、threat_model_path を Codex プロンプトへ渡す記述があることを確認する - 記述がある
- [ ] TS-9（FR10）: SPEC の Security Considerations と THREAT-MODEL.md の役割分担が planner 側の文書にあることを確認する - 記述がある
- [ ] TS-10（FR11）: plugin.json と marketplace.json の em-workflow の version が一致し、base revision の値から minor が上がっていることを確認する - 一致していて、minor bump になっている
- [ ] TS-12（NFR2, NFR3）: 既存の固定文字列（planner の '### 6. Populate requirements mapping (MANDATORY)'、review-phase.md の Phase 見出し、develop SKILL.md の Tier 削減表の語）が残っていることを既存のテストで確認する - 既存のテストが通る

### Integration Tests
- [ ] TS-11（NFR3）: python3 -m unittest discover -s tests を実行する - 全テストが通る

### Manual Tests
- [ ] TS-13（NFR1）: 手動確認：NFR1（出力量は脅威の実在に比例）が THREAT-MODEL.md テンプレートと planner の手順に反映されていることを目視で確認する - 脅威が無いときに短く終わる形がテンプレートと手順にある

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 信頼境界・脅威が無い変更: 『信頼境界なし + 根拠』（または脅威なしの結果）の数行だけを書き、緩和策は作らない（FR3）
- [ ] THREAT-MODEL.md が無い場合（この機能より前に計画した feature、standalone の /em-workflow:review）: threat_model_path を渡さない。review-security は従来どおり動き、THREAT-MODEL.md が無いこと自体は指摘しない（A2）
- [ ] 緩和策の未実装の finding で該当する行が無い: line は null。無関係な changed file へ付け替えない（FR9）

### Performance Tests

該当なし

## Security Considerations

- **Input Validation:** `threat_model_path` は `spec_path` と同じパス検証（制御文字の拒否、project_root 配下への realpath 収まり、symlink の拒否）を通してから渡す（NFR4）
- **Data Protection:** reviewer と Codex は `THREAT-MODEL.md` の内容を信頼できないデータとして扱う（NFR4）
- **Authentication / Authorization / XSS / SQL Injection / CSRF:** 該当なし

## Error Handling

該当なし

## Performance Optimization

NFR1 を参照。

## Success Criteria

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

## Assumptions

| ID | 前提 | 影響度 |
|----|------|--------|
| A1 | THREAT-MODEL.md は feature-docs/{feature}/THREAT-MODEL.md（IMPLEMENTATION.md と同じディレクトリ）に置く。 | low |
| A2 | THREAT-MODEL.md が無い場合（この機能より前に計画した feature、standalone の /em-workflow:review）は threat_model_path を渡さない。review-security は従来どおり動き、THREAT-MODEL.md が無いこと自体は指摘しない。 | medium |
| A3 | threat_model_path は perspective == security のときだけ渡す。orchestrator は spec_path と同じ検証をかけてから渡す。 | medium |
| A4 | threat_model_path の Read は調査予算（changed_files 以外は 3 ファイルまで）に数えない。 | low |
| A5 | 外部プラグイン vertex-review は review-protocol.md の Inputs に従い、このリポジトリでは変更しない。 | low |
| A6 | em-review プラグイン（em-review/skills/review-security/SKILL.md）は変更せず、その version も上げない。 | low |
| A7 | em-workflow の version の minor を上げる（plugin.json と marketplace.json を同じ値に）。具体的な値は SPEC・計画・AC に書かず、コミット時点の HEAD から決める。 | low |
| A8 | 再計画のとき既存の THREAT-MODEL.md は、既存の create-plan.existing-files の判断（IMPLEMENTATION.md / tasks/ と同じ）に含めて扱う。新しい gate_id は追加しない。 | medium |
| A9 | SPEC テンプレート（references/templates/spec-document.md）は変更しない。重複させない規則は planner / plan-writing / THREAT-MODEL.md テンプレート側に書く。 | low |
| A10 | task_description の『追加指示（起動引数）』（push と PR 作成、Codex への相談、Notion への記録）は走行時の指示として扱い、この機能の要件には含めない。 | low |
| B1 | （batch 解決：requirement.tier-coverage）全 tier で脅威モデリングを実行する。minimal tier では planner の write_policy を広げ、TASK.md の ## Expected Result に緩和策を検証可能な形で追記し、これを AC + VERIFICATION.md の代わりとして明記する。脅威が無ければ結果だけを記録する。 | high |
| B2 | （batch 解決：requirement.missing-mitigation-finding-site）緩和策の未実装の finding は、信頼境界を実装するファイルを file に指し、行が無ければ line は null。confidence の上限を避けるために無関係な changed file へ付け替えない。 | medium |
| B3 | （batch 解決：requirement.review-protocol-frozen-inputs）threat_model_path は review-protocol.md の Inputs 節に追記し、凍結ハッシュと INPUT_FIELD_NAMES を同じ変更で更新する。 | medium |
| B4 | （batch 解決：requirement.rework-threat-model）rework での THREAT-MODEL.md の更新はスコープ外とし、rework-planner は変更しない。rework で生じた新しい信頼境界が THREAT-MODEL.md に反映される保証は無い。spec-change で create-plan に戻る経路では作り直される。 | medium |
| B5 | （batch 解決：design-step.recommendation）design step は推奨どおりスキップする。 | low |

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件はない）

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/threat-model-stride/REQUIREMENTS.md`
