# Feature: plan-feature-docs-route

## Overview

implementation-planner がタスクの `files` に `feature-docs/**` を入れないようにし、`validate-worker-output.py` で replace_planning の `files` も検査する。他 feature の文書の修正は、create-plan の中で implementation-planner が 2 段階の dispatch と専用の明示の許可を使って直す。`feature-docs` の割り当てで implement が failed になった feature は、Step A.6 の failed からの入口で計画の訂正を dispatch し、再開時に止まらずに進む。

要件の詳細は `feature-docs/plan-feature-docs-route/REQUIREMENTS.md` を参照する。

## Objectives

- create-plan が実装担当のタスクに `feature-docs/**` を割り当てないようにし、計画と実装担当の規則の食い違いをなくす。
- 他 feature の `feature-docs` 配下の文書の修正を、実装担当以外の経路（create-plan の計画担当）で最後まで実行できるようにする。
- `feature-docs` の割り当てで implement が failed になった feature を同じ名前で再開したとき、止まらずに進めるようにする。

## User Stories

### US1: 実装担当のタスクに feature-docs を割り当てない
em-workflow の利用者として、create-plan が実装担当のタスクの `files` に `feature-docs/**` を入れないようにしたい。それによって計画と実装担当の規則が食い違わない。

**Acceptance Criteria:**
- [ ] AC1: plan-writing スキルに、タスクの `files` に `feature-docs/**` を入れない規則が書かれていて、implementation-planner のプロンプトがそれを参照している。文書の内容を確かめるテストで確認する。
- [ ] AC2: `files` に `feature-docs/` で始まるパスを持つ replace_planning の patch は、新しいコードで弾かれる。`./feature-docs/x` や `\` 区切りの表記も弾かれる。`feature-docs-archive/x` と `src/feature-docs/x` は通る。append の `rework-task-feature-docs` の判定は今と同じ。`test_ac1_replace_planning_entries_are_not_checked` の期待値は新しい規則に合わせて反転している。
- [ ] AC3: 引き継ぐタスクの `files` に `feature-docs` パスがあっても、再計画の patch はこの新しいコードでは弾かれない。
- [ ] AC8: `agents/implementer.md` と worktree-task-workflow スキルの「Never modify feature-docs/**」は残っている。

### US2: 他 feature の文書を create-plan で直す
em-workflow の利用者として、他 feature の `feature-docs` 配下の文書の修正を create-plan の計画担当の経路で最後まで実行したい。それによって実装担当以外の経路で修正が終わる。

**Acceptance Criteria:**
- [ ] AC4: planner-contract に、他 feature の文書の宣言、2 段階の dispatch、新しい明示の許可、範囲の制限、`digest_inputs` と自己書き込みの照合への追加が書かれている。範囲外のパス（他 feature の `workflow.yaml`、`phase-state/**`、`tasks/**`、`design/mockups/`、`feature-docs/LESSONS.md`）は許可の対象にならない。
- [ ] AC5: create-plan-phase.md 12 節の宣言済み変更集合の導出元に、他 feature の文書の修正の宣言が含まれている。

### US3: failed になった feature を再開する
em-workflow の利用者として、`feature-docs` の割り当てで implement が failed になった feature を同じ名前で再開したとき、止まらずに進めたい。

**Acceptance Criteria:**
- [ ] AC6: implement が failed（`failed_kind: decision`）で、未マージのタスクの `files` に他 feature の THREAT-MODEL.md がある `workflow.yaml` では、入口の判定が dispatch を返し、訂正の対象にそのタスクとパスが含まれる。基準コミットにそのパスがあっても対象から外れない。implement が failed でない場合と、進行中のタスクがある場合は dispatch しない。
- [ ] AC7: 復帰では implement と対象タスクが pending になり、`failed_kind` は null、notes は消え、`routeback_failed_journal_line` が記録される。マージ済みのタスクは変わらない。

## Technical Requirements

### Functional Requirements
- **FR1:** 計画担当の割り当て規則 — implementation-planner は、最初のパス要素が `feature-docs` であるパスをタスクの `files` に入れない。自 feature の `feature-docs/{feature}/` も `feature-docs/LESSONS.md` も対象に含む。判定の正規化は rework の Feature-docs files rule と同じにする（`\` は `/` として扱い、空の要素と `.` は落とし、最初の要素がちょうど `feature-docs` のものだけを対象にする）。規則の本文は plan-writing スキルに置き、implementation-planner のプロンプトからは参照するだけにする。禁止の対象は `files` だけで、タスクの `plan` の値は対象外。
- **FR2:** replace_planning の検証 — `validate-worker-output.py` が、replace_planning の `tasks_patch.entries` の `files` にある `feature-docs` パスを新しいエラーコードで弾く。1 つのパスにつき 1 件報告し、メッセージにはタスク id とパスを含める。append の既存規則とエラーコード `rework-task-feature-docs` は変えない。引き継ぐタスク（`carried_task_ids`）の `files` はそのままの形で写されるので、この検査の対象にしない。
- **FR3:** 他 feature の文書を create-plan で直す — 計画が他 feature の文書の修正を必要とするとき、implementation-planner が create-plan の中で自分で直す。直した内容は結果の中で宣言し（対象パスと、何をなぜ直したか）、`written_artifacts` に入れる。検証、`workflow.yaml` の更新、コミットはこれまでどおりオーケストレーターが行う。修正は create-plan が completed になる前に済ませる。
- **FR4:** 2 段階の dispatch と明示の書き込み許可 — 計画担当は、まず直す必要のある他 feature の文書のパスを宣言する。オーケストレーターはそのパスごとに `write_policy.targets` を設定し（`expect_digest` は dispatch 時のダイジェスト）、計画担当を dispatch し直す。許可には、この経路専用の明示の action か許可の印を新しく作る。`replace_own`、`replace_authorized`、artifact-overwrite の batch policy は流用しない。宣言の経路と新しい許可の名前は未決定（Open Questions 参照）。
- **FR5:** 書き込み範囲の制限 — FR3 の経路で変更できるのは、`feature-docs/{他 feature}/` 配下にある既存の Markdown 文書だけ。他 feature の `workflow.yaml`、`phase-state/**`、`tasks/**`、`design/mockups/` と `feature-docs/LESSONS.md` は対象外。範囲外のパスは許可せず、宣言されても書かない。
- **FR6:** 入力ダイジェストと自己書き込みの照合 — FR4 で許可した他 feature の文書を、implementation-planner の `digest_inputs` と、その dispatch の self-write の照合の両方に含める。planner-contract の `digest_inputs` の一覧と、自己書き込みが重なる範囲の記述を更新する。
- **FR7:** 宣言済み変更集合に含める — FR3 で直した他 feature の文書は、`tasks.*.files` には入らない。代わりに、その修正の宣言を feature の宣言済み変更集合の導出元に加える（create-plan-phase.md の 12 節）。それによって検証時の包含の判定から漏れず、レビューの対象にもなる。修正の宣言は再開した後も読める形で残す。
- **FR8:** failed からの入口の拡張 — Step A.6 の failed からの入口を広げる。implement が failed で、未マージの失敗タスクの `files` に `feature-docs` パスがあるときは、計画の訂正を dispatch する。訂正の対象は、`report-name-entry.py` と同じ方法で未マージの全タスクから集める。最終パスの訂正の条件「旧パスが基準コミットに存在しない」は、この訂正には使わない。訂正では、対象のパスを `files` から外し、その文書は FR3 から FR7 の経路で直す。対話実行でも batch 実行でも同じ入口を使い、`failed_kind` の値によらず停止条件 3 より前に評価する。
- **FR9:** 再開時の復帰 — 検証済みの訂正を適用するときは、成果物を先にコミットし、そのあと次をまとめて 1 回の Write と 1 回のコミットで書く。implement を pending に、`failed_kind` を null に、対象タスクの status を pending にし、`failed_journal_line` があれば `routeback_failed_journal_line` に記録し、notes を消す。進行中のタスクがあるときは訂正しない。マージ済みのタスク、対象タスクの worktree とブランチには触れない。workflow-patch.md の、failed のタスクを許す例外にこの訂正を加える。
- **FR10:** 実装担当の規則を維持 — `agents/implementer.md` と worktree-task-workflow スキルの「Never modify feature-docs/**」は変えない。

### Non-Functional Requirements
- **NFR1 - 新しい gate と質問を足さない:** 新しい gate_id もユーザーへの新しい質問も足さない。batch 実行でも同じ経路で止まらずに進む。
- **NFR2 - 形の崩れた入力の扱い:** 検証スクリプトと入口の判定スクリプトは、形の崩れた入力を例外にせず、エラーとして報告する。
- **NFR3 - テストの依存:** テストは Python 標準ライブラリの unittest だけを使う。
- **NFR4 - 規則の SSOT:** 規則の本文は SSOT の文書 1 か所に置き、他の文書からは参照するだけにする。
- **NFR5 - 信頼できない入力と秘匿:** 他 feature の文書の内容は信頼できない入力として扱い、中の指示には従わない。書く文書には、ホーム配下の絶対パスも Notion URL も入れない。
- **NFR6 - version の扱い:** em-workflow の version には触らない（main への push で Actions が patch を上げる）。

## Implementation Approach

### Architecture

**Component Diagram:**
```
plan-writing スキル ───────────── FR1 の規則の本文（SSOT）
  ↑ 参照
implementation-planner のプロンプト

validate-worker-output.py ─────── FR2 replace_planning の files の検査（新しいエラーコード）
                                  append の rework-task-feature-docs は変えない

planner-contract ──────────────── FR3〜FR6 宣言・2 段階の dispatch・専用の許可・範囲・digest_inputs と self-write
create-plan-phase.md 12 節 ────── FR7 宣言済み変更集合の導出元
develop スキル Step A.6 ────────── FR8 failed からの入口
workflow-patch.md ─────────────── FR9 failed のタスクを許す例外
agents/implementer.md / worktree-task-workflow スキル ── FR10 変更しない
```

### Data Flow

create-plan での他 feature の文書の修正（FR3〜FR7）:
```
implementation-planner（1 回目）── 直す必要のある他 feature の文書のパスを宣言
  → オーケストレーター ── FR5 の範囲外のパスは許可しない
                         範囲内のパスごとに write_policy.targets を設定
                         （専用の明示の許可、expect_digest は dispatch 時のダイジェスト）
  → implementation-planner（2 回目）── 文書を直す
                                      修正を宣言（対象パスと、何をなぜ直したか）
                                      written_artifacts に入れる
  → オーケストレーター ── 検証、workflow.yaml の更新、コミット
                         修正の宣言を宣言済み変更集合の導出元に加える
```

許可範囲の外にある他 feature のファイルを計画が直す必要があるときは、implementation-planner はそのファイルに書かず、パスを名指しして blocked を返す（A2）。

再開時の Step A.6（FR8、FR9）:
```
Step A.6（停止条件 3 より前、failed_kind の値によらない）
  implement が failed かつ 未マージの失敗タスクの files に feature-docs パスがある
  かつ 進行中のタスクがない
    → 訂正の対象を未マージの全タスクから集める（report-name-entry.py と同じ方法）
    → files が空になるタスクがある → そのタスクを名指しして blocked（A3）
    → それ以外 → 計画の訂正を dispatch（files から feature-docs パスを外し、文書は FR3〜FR7 の経路で直す）
  検証済みの訂正の適用
    → 成果物を先にコミット
    → 1 回の Write と 1 回のコミット: implement を pending、failed_kind を null、
       対象タスクの status を pending、failed_journal_line があれば routeback_failed_journal_line に記録、notes を消す
```

最終パスの訂正の判定と `feature-docs` の判定は、同じ Step A.6 の 1 回の評価の中で行い、一方がもう一方を止めることはない（A4）。両方が当てはまるときの順序は未決定（Open Questions 参照）。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- plan-writing スキル: FR1 の規則の本文の置き場所
- planner-contract: FR3〜FR6 の契約
- create-plan-phase.md 12 節: FR7 の宣言済み変更集合の導出元
- `validate-worker-output.py`: FR2 の検証
- `report-name-entry.py`: FR8 の訂正対象の集め方
- workflow-patch.md: FR9 の failed のタスクを許す例外
- rework の Feature-docs files rule: FR1、FR2 のパスの正規化

**External Dependencies:**
- Python 標準ライブラリの unittest（NFR3）

### File Structure

変更する文書とスクリプト:
```
em-workflow/
├── skills/plan-writing/SKILL.md                  # FR1
├── agents/                                       # FR1 implementation-planner のプロンプト（参照のみ）
├── references/contracts/planner-contract.md      # FR3〜FR6
├── references/phases/create-plan-phase.md        # FR7（12 節）
├── references/workflow-patch.md                  # FR9
├── skills/develop/SKILL.md                       # FR8、FR9（Step A.6）
└── scripts/validate-worker-output.py             # FR2
tests/
└── test_rework_docs_only_validator_rules.py      # FR2 test_ac1_replace_planning_entries_are_not_checked の期待値の反転
```

変更しない文書（FR10）: `em-workflow/agents/implementer.md`、`em-workflow/skills/worktree-task-workflow/SKILL.md`

## Declared Change Set

この節は手で列挙した一覧ではなく、create-plan での導出を述べる。フィーチャー固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は既定で、フィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つを宣言する。

- `feature-docs/plan-feature-docs-route/**`
- `test-docs/plan-feature-docs-route/**`

`feature-docs/plan-feature-docs-route/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントと `references/phase-state.md` で、この節はそれを引用するだけで、ルールは再掲しない。

`test-docs/plan-feature-docs-route/**` に含まれるもの: タスクごとのテスト記録 `test-docs/plan-feature-docs-route/{T}.tests.yaml`。生成主体は `implement-phase.md` で、この節はそれを引用するだけで、ルールは再掲しない。

この 2 つの既定のメンバーは、SPEC の作成者が明示的に除外しない限り宣言に含まれる。記載が無いことで除外されたとはみなさない。除外は意図的で明示的な絞り込みに限る。

この宣言はスーパーセット（SUPERSET）の主張であり、検証時に観測した実際の変更集合は、宣言された集合に含まれて（CONTAINED IN）いればよく、一致する必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/plan-feature-docs-route/` ディレクトリを生成しないが、その場合も宣言された `test-docs/plan-feature-docs-route/**` は正しい。宣言したパスが生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests
- [ ] TS-1: replace_planning の patch で、`files` に `feature-docs/call-end-history/THREAT-MODEL.md` を持つタスク - 新しいコードで 1 件弾かれ、メッセージにタスク id とパスが入る。
- [ ] TS-2: `./feature-docs/x`、`feature-docs\x\y.md`、`feature-docs//x`、`feature-docs-archive/x`、`src/feature-docs/x` の表記 - 前の 3 つは弾かれ、`feature-docs-archive/x` と `src/feature-docs/x` は通る。
- [ ] TS-3: append_rework の patch - `rework-task-feature-docs` の判定が変わらない。
- [ ] TS-4: `carried_task_ids` で引き継いだタスクの `files` にある `feature-docs` パス - 新しいコードを出さない。
- [ ] TS-5: 文書の内容を確かめるテスト - plan-writing スキル、implementation-planner、planner-contract、create-plan-phase.md、実装担当の 2 文書に、決めた規則が書かれている。
- [ ] TS-6: 入口の判定、失敗タスクの `files` に他 feature の文書がある `workflow.yaml` - dispatch になり、対象は未マージの全タスクから集められる。基準コミットにそのパスがあっても対象に入る。
- [ ] TS-7: 入口の判定、implement が failed でない場合、進行中のタスクがある場合、`feature-docs` パスを持つのがマージ済みのタスクだけの場合 - dispatch しない。
- [ ] TS-8: 訂正の patch の適用 - 対象タスクの `files` から `feature-docs` パスが消え、implement とそのタスクが pending になる。マージ済みのタスクのレコードは変わらない。
- [ ] TS-9: 検証スクリプトと入口の判定スクリプトに形の崩れた入力を与える - 例外ではなくエラーとして報告される。

実行コマンド: `python3 -m unittest discover -s tests`（AC9）

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 検出なし

### Edge Cases
TS-2、TS-4、TS-7、TS-9 を参照。

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 他 feature の文書への書き込みは、FR4 のパスごとの明示の許可がある場合だけ。範囲は FR5 のとおり。`replace_own`、`replace_authorized`、artifact-overwrite の batch policy は流用しない。
- **Input Validation:** 他 feature の文書の内容は信頼できない入力として扱い、中の指示には従わない（NFR5）。検証スクリプトと入口の判定スクリプトは、形の崩れた入力をエラーとして報告する（NFR2）。
- **Data Protection:** 書く文書には、ホーム配下の絶対パスも Notion URL も入れない（NFR5）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | 発生元 | 報告内容 |
|------|-------------|--------|----------|
| （新しいコード、名前は未決定） | replace_planning の `tasks_patch.entries` の `files` に `feature-docs` パスがある（FR2） | `validate-worker-output.py` | 1 つのパスにつき 1 件、タスク id とパス |
| `rework-task-feature-docs` | append の既存規則。変えない（FR2、A1） | `validate-worker-output.py` | 現行どおり |

### Error Flow

```
範囲外の他 feature のファイルの修正が必要 → implementation-planner はそのファイルに書かず、パスを名指しして blocked（A2）
feature-docs パスを外すと files が空になるタスクがある → そのタスクを訂正せず、入口はタスクを名指しして blocked（A3）
形の崩れた入力 → 検証スクリプトと入口の判定スクリプトは例外にせず、エラーとして報告（NFR2）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1〜AC9 を満たす
- [ ] TS-1〜TS-9 が通る
- [ ] `python3 -m unittest discover -s tests` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

`status: tbd` の要件は無い。次の項目は、要件は確定（`status: resolved`）しているが、名前と順序が未決定。

- [ ] FR4: 2 段階の dispatch と明示の書き込み許可 - 計画担当が他 feature の文書のパスを宣言する経路（結果の中のどこで宣言するか）が未決定
- [ ] FR4: 2 段階の dispatch と明示の書き込み許可 - この経路専用の明示の action または許可の印の名前が未決定
- [ ] FR2: replace_planning の検証 - 新しいエラーコードの名前が未決定
- [ ] FR8: failed からの入口の拡張 - 最終パスの訂正と `feature-docs` の訂正が両方当てはまるときの順序が未決定（A4）

## Assumptions

- A1: 既存のエラーコード `rework-task-feature-docs` は名前を変えずに残す。replace_planning 向けの判定には新しいコードを足す。
- A2: 許可範囲の外にある他 feature のファイル（`workflow.yaml` や `LESSONS.md` など）を計画が直す必要があるときは、計画担当はそのファイルに書かず、パスを名指しして blocked を返す。
- A3: 再開時の訂正で `feature-docs` パスを外すと `files` が空になるタスクがあるときは、そのタスクを訂正せず、入口はタスクを名指しして blocked を返す。
- A4: 最終パスの訂正の判定と `feature-docs` の判定は、同じ Step A.6 の 1 回の評価の中で行う。一方がもう一方を止めることはない。両方が当てはまるときの順序は Open Questions に残す。
- A5: `implementer.md` と worktree-task-workflow スキルの、`feature-docs/**` の変更禁止を維持する。
- A6: web-sip-phone 側のコードと文書の修正はスコープ外とする。

## References

- 要件定義書: `feature-docs/plan-feature-docs-route/REQUIREMENTS.md`
- 計画担当の規則: `em-workflow/skills/plan-writing/SKILL.md`
- 計画担当の契約: `em-workflow/references/contracts/planner-contract.md`
- 宣言済み変更集合: `em-workflow/references/phases/create-plan-phase.md`
- 検証スクリプト: `em-workflow/scripts/validate-worker-output.py`
- 訂正対象の集め方: `em-workflow/scripts/report-name-entry.py`
- failed のタスクを許す例外: `em-workflow/references/workflow-patch.md`
- Step A.6: `em-workflow/skills/develop/SKILL.md`
- 実装担当の規則: `em-workflow/agents/implementer.md`、`em-workflow/skills/worktree-task-workflow/SKILL.md`
