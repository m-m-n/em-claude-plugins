# Feature: tier-decision-staged-jev

## Overview

em-workflow の tier 判定を、Jev（タスク説明のみ）→ Codex によるコードの事実調査 → Jev（タスク説明＋両方の JSON）の 3 段階で行う。tier は最終 Jev のバケット 0〜3 の確率だけで決め、2 つの読み取りの不一致による full への強制を削除する。要件の詳細は `feature-docs/tier-decision-staged-jev/REQUIREMENTS.md` を参照。

## Objectives

- em-workflow の tier 判定を 3 段階で行う。タスク説明だけで Jev を呼び、次に Codex でコードの事実を調査し、最後にタスク説明と両方の JSON を入力として Jev を呼ぶ。
- tier は最終 Jev のバケット 0〜3 の確率だけで決める。ルール追加＋テスト追加の小さいタスク（例: loop-develop の triage-completion-judgment。最終読み取り P(0)=0.09, P(1)=0.90）が full に強制されず reduced に到達する。

## User Stories

### US1: 段階的な tier 判定
em-workflow の develop 利用者として、タスク説明とコードの事実調査の両方を踏まえて tier を判定してほしい。そうすれば、タスクの実際の変更規模に合った tier で進められる。

**Acceptance Criteria:**
- [ ] AC1（FR1, FR2）: SKILL.md の tier 判定手順が、Jev（タスク説明のみ）→ Codex 調査 → Jev（タスク説明＋両方の JSON）の順序を記述し、最終呼び出しが第 1 Jev の結果（confidence を含む）を受け取ることを記述している。
- [ ] AC5（FR7）: `tier-rules.yaml` の `codex_output_schema` が、既存フィールドに加えて 7 つの新しい事実フィールドを、それぞれ値の語彙付きで持つ。
- [ ] AC7（FR8）: `codex_available=false` のとき、decide-tier.py は本来 minimal になるスコアでも full を返す。SKILL.md の step 6 と `tier-rules.yaml` の `fallback_matrix` が同じ扱いを記述している。
- [ ] AC8（FR6）: `tier-rules.yaml` の `question_set` がバケット 0〜3 の説明を定義し、ルール追加＋テスト追加がバケット 1 にある。

### US2: 最終確率だけによる tier 決定
em-workflow の develop 利用者として、ルール追加＋テスト追加の小さいタスクが full に強制されないようにしてほしい。そうすれば、そのタスクは reduced で進められる。

**Acceptance Criteria:**
- [ ] AC2（FR3, FR4）: decide-tier.py は、4 バケットが正しい最終スコアを受け取ると、その確率だけで tier を決める。P(0)=0.09, P(1)=0.90, P(2)=0.01, P(3)=0.00 は reduced。P(0)=0.85 は `expectation_clear` の値にかかわらず minimal。P(0)=0.50, P(1)=0.30 は full。
- [ ] AC3（FR3）: バケットの欠落、非有限または範囲外のバケット、許容誤差外の合計は full になり、理由に該当バケットまたは合計を示す。
- [ ] AC4（FR5）: 文字列 `readings_disagree` が `em-workflow/` のどこにも現れず、2 つの読み取りの不一致で full に倒す規則がない。
- [ ] AC6（FR10）: `phase-state.md` の tier 判定永続化の節が tier.yaml schema_version 2 を定義し、`bases` が第 1 と最終の Jev スコアオブジェクトを、`pre_survey_estimate` が Codex の JSON を保持する。
- [ ] AC9（NFR1, NFR2, NFR3, NFR5）: `python3 -m unittest discover -s tests` が通り、plugin.json と marketplace.json が同じ引き上げ後の em-workflow の version を持つ。

## Technical Requirements

### Functional Requirements
- **FR1:** 段階的な呼び出し順序。`em-workflow/skills/develop/SKILL.md` の Step A の tier 判定手順は、(1) 判定スキル `~/.claude/skills/jev`（`--json-input` / `--json-output`）をタスク説明だけで呼び、(2) `run_codex_exec.sh readonly` で Codex の readonly 事前調査を行い、(3) 最終判定として判定スキルを再度呼ぶ。この順に呼び出す。
- **FR2:** 最終 Jev の入力。最終 Jev 呼び出しの入力は、タスク説明、第 1 Jev 呼び出しの JSON 結果全体（confidence を含む）、Codex 事前調査の JSON を含む。
- **FR3:** 最終 Jev の 4 バケットと検証。最終 Jev の結果はバケット `"0"`、`"1"`、`"2"`、`"3"` の確率を持つ。どの閾値行を評価するよりも前に、`scripts/decide-tier.py` は、4 つのキーがすべて存在し、各値が [0, 1] の有限の実数で、合計と 1 の差が許容誤差以内であることを要求する。許容誤差は `references/tier-rules.yaml` に宣言されたメンバーとする。いずれかの検査に失敗した場合、tier は full で、理由に該当バケットまたは合計を示す。
- **FR4:** 最終確率のみによる tier 判定。tier は最終読み取りのバケット確率だけで決める。`tier-rules.yaml` の閾値行をバケット 0〜3 で次のとおり定義し直す。P(0) >= 0.80 なら minimal、P(0)+P(1) >= 0.85 なら reduced（P(0) の下限なし）、それ以外は full。行はこの順に評価し、最初に一致した行を採用する。`expectation_clear` と `confidence` はどの行の閾値メンバーにもせず、記録のみ行う。第 1 読み取り（タスク説明のみ）は閾値行で評価しない。
- **FR5:** 不一致規則の削除。2 つの読み取りが異なる tier を示した場合に full へ倒す規則（`decided_by fallback_matrix:readings_disagree`）を、`scripts/decide-tier.py`、`references/tier-rules.yaml`、`skills/develop/SKILL.md`、`references/phases/create-spec-phase.md` から削除する。評価器は 2 読み取りの `readings` 入力を受け付けなくなり、最終スコアオブジェクト 1 つを受け取る。
- **FR6:** tier-rules.yaml のバケット説明。`references/tier-rules.yaml` の `question_set` に、両方の Jev 呼び出しに渡すバケット 0〜3 それぞれの説明を定義する。バケット 0 は文言またはルール本文の変更のみで、新しいロジックもテストの変更もない。バケット 1 はルール追加とテスト追加の組み合わせ、または少数ファイルの小さな変更と小さなテスト変更。バケット 2 と 3 は段階的に大きな変更を表す（A9）。質問文言を外部スキルに割り当てている `question_set` のコメントを、これに合わせて更新する。jev と typesafe-ai のスキル文書から文を複写しない。
- **FR7:** Codex の事実フィールド。`tier-rules.yaml` の `codex_output_schema` は既存フィールドを維持し、値の語彙を定義したフィールドを追加する。報告する事実は、テスト変更の種類（既存チェックに 1:1 でケースを足すだけか、新しい振る舞いのテストを書くか）、追加テストケースの見込み数、本体変更の種類（文言・ルール追加か、新しいロジックか）、変更の閉じ具合（1 関数内 / 1 モジュール内 / 複数モジュール）、変更箇所の呼び出し元と依存の数、外部契約（引数、戻り値、ファイル形式、設定キーなど）の変更有無、振る舞いの変更有無。Codex は事実だけを報告し、規模の判断はしない。
- **FR8:** Codex 使用不可 → full。Codex 事前調査が使用不可（非ゼロ終了、出力が JSON として解析できない、または必須フィールドの欠落）の場合、最終 Jev 呼び出しを行わず、tier は full。`tier-rules.yaml` の `fallback_matrix`（`jev_only_usable` 行。action は full になる）、`scripts/decide-tier.py`（`codex_available=false` ならスコアにかかわらず full）、SKILL.md の step 6 がすべて同じ扱いを記述する。
- **FR9:** Jev 使用不可 → full。いずれかの Jev 呼び出し（タスク説明のみ、または最終）の非ゼロ終了を「判定スキル使用不可」とみなし、tier は full。既存の `jev_unusable` 行と `jev_exit_codes` 表による。
- **FR10:** 判定記録。`feature-docs/{feature}/phase-state/tier.yaml` を schema_version 2 にする。`schema_version`、`feature`、`tier`、`bases`、`pre_survey_estimate`、`decided_at` を維持する。`bases` は第 1 読み取り（basis `description_only`）と最終読み取り（basis `description_plus_code`）を記録する。各エントリは当該 Jev 呼び出しのスコアオブジェクト全体（0〜3 の確率、`expectation_clear`、`confidence`）と `observed_at` を持つ。`pre_survey_estimate` は Codex の JSON をそのまま保持する。呼び出しを行わなかった、または使用不可だった場合は、そのエントリまたは値を持たず、フォールバック理由を記録する。
- **FR11:** 射影の更新。`references/phases/create-spec-phase.md` の Tier-decision record 対応表、`references/workflow-schema.md` の `tier_decision.confidence` の説明、`skills/develop/SKILL.md` の retrospect `signals.tier_decision` ブロックを、新しい記録に合わせて更新する。`rationale` メンバーは 2 つの読み取りが一致したかどうかを記述せず、tier を決めた最終読み取りまたはフォールバックを要約する。`tier_decision` のサブフィールドはちょうど 4 つのまま。
- **FR12:** no-work 停止の維持。Codex 事前調査が残作業なしと報告した場合、既存の no-work-required 停止により、最終 Jev 呼び出しの前、かつワークフローのどのステップよりも前に実行を終える。

### Non-Functional Requirements
- **NFR1 - 決定的でフェイルセーフな評価器:** `scripts/decide-tier.py` はモデル推論も独自の呼び出しも行わず、常に終了コード 0 で終わる。欠落・不正形式・範囲外の入力には、理由を示して full を返す。非有限の JSON トークンを出力しない。すべての下限と合計の許容誤差はルール表から読み、評価器に数値の既定値を持たない。
- **NFR2 - 閾値は tier-rules.yaml が持つ:** `skills/develop/SKILL.md` の tier 判定の節と `references/workflow-schema.md` の tier の節は、閾値のリテラル、`P(0)`、`expectation_clear` を再掲しない。どこにも confidence 単独に対する閾値を置かない。
- **NFR3 - テストの規約:** テストは `tests/` 配下で標準ライブラリの `unittest` だけを使う（`python3 -m unittest discover -s tests` で実行）。生テキストのマッチャーには、必ず否定の証明と空振り防止のガードを組にする。
- **NFR4 - ゲートと質問を追加しない:** tier 判定の経路は、対話モードでもバッチモードでも gate_id もユーザーへの質問も導入しない。
- **NFR5 - プラグインの version を上げる:** `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`（いずれも現在 0.2.9）の em-workflow の version を、同じ変更の中で同じ値に上げる。
- **NFR6 - レビュー文書は変更しない:** `review-phase.md` とレビュールールに tier の語彙を追加しない（`tests/test_tier_spec_perspective.py` AC-6）。

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────┐
│ skills/develop/SKILL.md  Step A tier 判定手順 │
├──────────────────────────────────────────────┤
│ 判定スキル ~/.claude/skills/jev（2 回）        │
│ Codex readonly 事前調査 run_codex_exec.sh      │
├──────────────────────────────────────────────┤
│ scripts/decide-tier.py（決定的な評価器）       │
├──────────────────────────────────────────────┤
│ references/tier-rules.yaml（閾値・許容誤差・   │
│   question_set・codex_output_schema・          │
│   fallback_matrix・jev_exit_codes）            │
├──────────────────────────────────────────────┤
│ feature-docs/{feature}/phase-state/tier.yaml   │
│   （schema_version 2）                         │
└──────────────────────────────────────────────┘
```

**Component Diagram:**
```
SKILL.md Step A
  ├─ Jev（タスク説明のみ, basis description_only）
  ├─ Codex readonly 事前調査（codex_output_schema に沿った事実 JSON）
  ├─ Jev（最終, basis description_plus_code）
  ├─ decide-tier.py ── reads ──> tier-rules.yaml
  └─ tier.yaml（schema_version 2）
        └─ 射影: create-spec-phase.md の対応表 / workflow-schema.md の tier_decision / SKILL.md の retrospect signals.tier_decision
```

### Data Flow

```
タスク説明 ─> Jev（第 1） ─> 第 1 スコア JSON（confidence を含む）
タスク説明 ─> Codex readonly 事前調査 ─> Codex JSON
  Codex 使用不可 ─> 最終 Jev を呼ばない ─> tier = full
  残作業なし ─> no-work-required 停止（最終 Jev の前）
タスク説明 + 第 1 スコア JSON + Codex JSON ─> Jev（最終） ─> 最終スコア
最終スコア + codex_available + jev_available ─> decide-tier.py（tier-rules.yaml を読む）
  ─> tier / decided_by / 理由 ─> tier.yaml（schema_version 2）
```

第 1 Jev 呼び出しが使用不可でも Codex 事前調査は実行する（A13）。この場合も tier は full。

### API Design

#### Endpoint 1: scripts/decide-tier.py

**Request（入力）:**
```
- 最終スコアオブジェクト 1 つ（バケット "0"〜"3" の確率、expectation_clear、confidence）
- codex_available: 真偽値
- jev_available: 真偽値
- ルール表: references/tier-rules.yaml
旧形式の 2 読み取り readings ペイロードは受け付けない（不正入力として full）。
```

**Response（出力）:**
```
- tier: minimal | reduced | full
- decided_by: 例 threshold_rows:reduced、fallback_matrix:jev_unusable
- 理由: full に倒した場合は、該当バケット、合計、またはフォールバックを示す
出力は厳密に解析可能な JSON で、非有限の JSON トークンを含まない。終了コードは常に 0。
```

**評価順序:**
1. `jev_available=false` → full（`fallback_matrix:jev_unusable`）
2. `codex_available=false` → full（`fallback_matrix` の行。スコアにかかわらず）
3. 4 バケットの検証（キーの存在、[0, 1] の有限値、合計と 1 の差が許容誤差以内）。失敗 → full
4. 閾値行を上から評価し、最初に一致した行を採用

| 順 | tier | 条件 |
|----|------|------|
| 1 | minimal | P(0) >= 0.80 |
| 2 | reduced | P(0)+P(1) >= 0.85（P(0) の下限なし） |
| 3 | full | 上記以外 |

下限と許容誤差（初期値 0.02、A8）は `tier-rules.yaml` から読み、評価器に数値の既定値を持たない。

### Database Schema

#### Table 1: feature-docs/{feature}/phase-state/tier.yaml（schema_version 2）

| Field | Type | Null | Default | Description |
|--------|------|------|---------|-------------|
| schema_version | integer | NO | - | 2 |
| feature | string | NO | - | フィーチャー名 |
| tier | string | NO | - | minimal / reduced / full |
| bases | array | NO | - | 第 1 読み取り（basis `description_only`）と最終読み取り（basis `description_plus_code`）。各エントリは当該 Jev 呼び出しのスコアオブジェクト全体（0〜3 の確率、`expectation_clear`、`confidence`）と `observed_at` を持つ。呼び出しなし・使用不可のエントリは持たない |
| pre_survey_estimate | object | YES | - | Codex の JSON をそのまま保持。呼び出しなし・使用不可なら持たない |
| decided_at | string | NO | - | 判定時刻 |

呼び出しを行わなかった、または使用不可だった場合は、フォールバック理由を記録する。

再開時、既存の schema_version 1 の tier.yaml はそのまま再利用し、再判定しない（A12）。

#### tier-rules.yaml の codex_output_schema に追加するフィールド（名前と語彙は仮置き、A10）

| Field | Values |
|-------|--------|
| test_change_kind | `none` \| `extend_existing_one_to_one` \| `new_behavior_tests` |
| added_test_cases_approx | integer |
| body_change_kind | `wording_or_rule_addition` \| `new_logic` |
| change_containment | `single_function` \| `single_module` \| `multiple_modules` |
| caller_and_dependency_count | integer |
| changes_external_contract | boolean |
| changes_behavior | boolean |

既存フィールドは維持する。

#### tier-rules.yaml の question_set のバケット説明

| バケット | 説明 |
|----------|------|
| 0 | 文言またはルール本文の変更のみ。新しいロジックもテストの変更もない |
| 1 | ルール追加とテスト追加の組み合わせ、または少数ファイルの小さな変更と小さなテスト変更 |
| 2 | 新しいロジック、複数モジュールにまたがる変更、または外部契約の変更（A9） |
| 3 | 広範な横断的変更、新しいファイル・モジュール・依存の追加、またはアーキテクチャの変更（A9） |

### Dependencies

**Internal Dependencies:**
- `references/tier-rules.yaml`: 閾値、合計の許容誤差、`question_set`、`codex_output_schema`、`fallback_matrix`、`jev_exit_codes` を持つ。
- `references/phase-state.md`: tier 判定永続化の節で tier.yaml schema_version 2 を定義する。
- decision_basis の値 `description_only` / `description_plus_code` は維持する（A11）。

**External Dependencies:**
- 判定スキル `~/.claude/skills/jev`: `--json-input` / `--json-output` で呼び出す。
- `run_codex_exec.sh readonly`: Codex の readonly 事前調査。

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json          # version を上げる（NFR5）
├── skills/develop/SKILL.md             # Step A の手順、step 6、retrospect signals.tier_decision
├── scripts/decide-tier.py              # 最終スコア 1 つを受け取る評価器
└── references/
    ├── tier-rules.yaml                 # 閾値行、許容誤差、question_set、codex_output_schema、fallback_matrix
    ├── phase-state.md                  # tier.yaml schema_version 2
    ├── workflow-schema.md              # tier_decision.confidence の説明
    └── phases/create-spec-phase.md     # Tier-decision record 対応表
.claude-plugin/marketplace.json         # em-workflow の version を上げる（NFR5）
tests/                                  # unittest（NFR3）
```

`review-phase.md` とレビュールールは変更しない（NFR6）。

## Declared Change Set

このセクションは手書きの一覧ではなく create-plan での導出を記述する。上記のフィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` エントリから導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上記のフィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つのエントリを既定で宣言する。

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物を含む。これらはフェーズドキュメントと `references/phase-state.md` が生成・所有する。このセクションはそれらを引用するだけで、ルールを再掲しない。

`test-docs/{feature}/**` はタスクごとのテスト記録 `test-docs/{feature}/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。このセクションはそれを引用するだけで、ルールを再掲しない。

この 2 つの既定エントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載がないことを除外とはみなさない。除外は意図的で明示的な絞り込みである。

この宣言はスーパーセット（SUPERSET）の主張である。検証時に観測される実際の変更集合は宣言された集合に含まれ（CONTAINED IN）なければならないが、等しい必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、その場合も宣言された `test-docs/{feature}/**` は正しい。実現しなかった宣言済みのパスは違反ではない。

## Test Scenarios

### Unit Tests
- [ ] TS1（FR4）: triage の事例。最終 P(0)=0.09, P(1)=0.90, P(2)=0.01, P(3)=0.00、両ツール使用可能 - tier reduced、`decided_by threshold_rows:reduced`
- [ ] TS2（FR4）: 最終 P(0)=0.37, P(1)=0.59, P(2)=0.03, P(3)=0.01（以前は full に固定されていた） - tier reduced
- [ ] TS3（FR4）: 最終 P(0)=0.85 で `expectation_clear` 0.1 の場合と、`expectation_clear` なしの場合 - いずれも tier minimal
- [ ] TS4（FR4）: 最終 P(0)=0.50, P(1)=0.30, P(2)=0.15, P(3)=0.05、および境界値 P(0)=0.80 ちょうど、P(0)+P(1)=0.85 ちょうど - 最初は full、境界値ではそれぞれ minimal と reduced
- [ ] TS5（FR3）: 最終スコアにバケット `"3"` がない / P(2)=NaN / P(1)=1.2 / 合計 1.10 - full。理由に該当バケットまたは合計を示す。出力は厳密に解析可能な JSON、終了コード 0
- [ ] TS6（FR5）: `em-workflow/` を `readings_disagree` で走査し、旧形式の 2 読み取り `readings` ペイロードを渡す - 出現なし。旧ペイロードは不正として full
- [ ] TS7（FR8）: `codex_available=false` で、本来 minimal になるスコア - full。閾値行ではなく `fallback_matrix` の行で決まる
- [ ] TS8（FR9）: `jev_available=false`（非ゼロ終了 1、2、75）で、Codex 使用可能・不可のそれぞれ - full、`decided_by fallback_matrix:jev_unusable`

### Integration Tests
- [ ] TS9（FR1, FR2, FR8, FR12, NFR2, NFR4）: SKILL.md の tier の節の生テキスト適合。段階の順序、最終入力の内容、Codex 使用不可の扱い、no-work 停止、閾値リテラルなし、gate_id / AskUserQuestion なし。各マッチャーは偽造サンプルによる否定の証明と組にする - すべてのマッチャーが実テキストで合格し、偽造サンプルで不合格
- [ ] TS10（FR6, FR7）: `tier-rules.yaml` の生テキスト / YAML 適合。4 つのバケット説明、ルール＋テストがバケット 1、7 つの Codex 事実フィールドと語彙、合計の許容誤差の宣言、jev と typesafe-ai の SKILL.md から複写した長い行がない - すべて存在し、複写なし
- [ ] TS11（FR10, FR11）: `phase-state.md`、`create-spec-phase.md` の対応表、`workflow-schema.md` の tier の節、SKILL.md の retrospect ブロックの適合 - schema_version 2 のフィールドが定義されている。対応表がすべてのフィールドを網羅する。`tier_decision` のサブフィールドがちょうど 4 つのまま。`rationale` が読み取りの一致に言及しない
- [ ] TS12（NFR5）: plugin.json と marketplace.json の em-workflow の version を比較する - 等しく、0.2.9 より大きい

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- 該当なし

### Edge Cases
- [ ] P(0)=0.80 ちょうど - minimal（TS4）
- [ ] P(0)+P(1)=0.85 ちょうど - reduced（TS4）
- [ ] `expectation_clear` がない最終スコア - 確率だけで判定し、minimal（TS3）
- [ ] 第 1 Jev 呼び出しが使用不可 - Codex 事前調査は実行し、tier は full（A13）
- [ ] Codex 事前調査が残作業なしを報告 - 最終 Jev 呼び出しの前に no-work-required 停止（FR12）

### Performance Tests
- 該当なし

## Security Considerations

- 該当なし

## Error Handling

### Error Codes

| Code | Description | decided_by / 扱い | 結果 |
|------|-------------|-------------------|------|
| jev_unusable | いずれかの Jev 呼び出しの非ゼロ終了（`jev_exit_codes` 表） | `fallback_matrix:jev_unusable` | full |
| jev_only_usable | Codex 事前調査が使用不可（非ゼロ終了、JSON として解析不能、必須フィールド欠落）。最終 Jev を呼ばない | `fallback_matrix` の `jev_only_usable` 行 | full |
| 確率の検証失敗 | バケット欠落、非有限値、範囲外、合計が許容誤差外 | 理由に該当バケットまたは合計を示す | full |
| 不正入力 | 欠落・不正形式・範囲外の入力、旧形式の `readings` ペイロード | 理由を示す | full |

### Error Flow

```
入力の欠落・不正・範囲外 → 理由を付けて tier = full → 厳密な JSON を出力 → 終了コード 0
```

## Performance Optimization

- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` が通る（AC9）
- [ ] plugin.json と marketplace.json が同じ引き上げ後の em-workflow の version を持つ（AC9）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（status: tbd の要件はない）

## Assumptions

- A1: reduced 条件は P(0)+P(1) >= 0.85 だけ。P(0) >= 0.40 の下限は削除する。
- A2: ルール追加＋テスト追加はバケット 1。バケット 0 はテスト変更なしの文言・ルール本文の変更。
- A3: Codex が使用不可なら最終 Jev 呼び出しを省略し、tier は full。`tier-rules.yaml`、`decide-tier.py`、テストを SKILL.md に揃える。
- A4: 閾値行は最終の 0〜3 の確率だけを見る。`expectation_clear` と `confidence` は記録のみ。
- A5: バケット 0〜3 の説明は `tier-rules.yaml` の `question_set` に置く。
- A6: 最終確率は 4 バケットすべてを必須とし、それぞれ [0,1] の有限値、合計は `tier-rules.yaml` に宣言した許容誤差以内。満たさなければ full。
- A7: デザインステップはスキップする。
- A8: 合計の許容誤差の `tier-rules.yaml` での初期値は 0.02。
- A9: バケット 2 は新しいロジック、複数モジュールにまたがる変更、または外部契約の変更。バケット 3 は広範な横断的変更、新しいファイル・モジュール・依存の追加、またはアーキテクチャの変更。
- A10: Codex のフィールド名と語彙は仮置き（上記の表）。既存フィールドは維持する。
- A11: decision_basis の値は維持する。`description_only` は第 1 読み取り、`description_plus_code` は最終読み取りを表す。
- A12: 再開時、既存の schema_version 1 の tier.yaml はそのまま再利用し、再判定しない。
- A13: 第 1 Jev 呼び出しが使用不可でも Codex 事前調査は実行する（no-work-required 停止に到達できるようにするため）。この場合も tier は full。

## References

- 要件定義書: `feature-docs/tier-decision-staged-jev/REQUIREMENTS.md`
- `em-workflow/skills/develop/SKILL.md`
- `scripts/decide-tier.py`
- `references/tier-rules.yaml`
- `references/phases/create-spec-phase.md`
- `references/workflow-schema.md`
- `references/phase-state.md`
- `tests/test_tier_decision_record.py`
- `tests/test_tier_spec_perspective.py`
