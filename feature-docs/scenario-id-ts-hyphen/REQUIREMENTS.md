---
title: "scenario-id-ts-hyphen"
created_date: 2026-11-03
status: draft
---

# scenario-id-ts-hyphen - 要件定義書

## 1. 概要

### 1.1 背景
em-workflow の文書では、シナリオ ID に `TS-n` 形式（ハイフンあり）と `TSn` 形式（ハイフンなし）の 2 種類が使われている。

### 1.2 目的
- em-workflow が新規に作る SPEC.md・VERIFICATION.md・tasks/*.md のシナリオ ID を `TS-n` 形式（`TS`、ハイフン、1 桁以上の数字）の 1 種類に揃える。
- 既存文書に残る `TSn` 形式（ハイフンなし）は、読み取りでは今まで通り受け付ける。

### 1.3 スコープ
- 対象: spec-writer の SPEC.md 描画ルール・テンプレート・contract、plan-writing スキルのシナリオ ID ルール、implementation-planner の出力検査（`validate-worker-output.py`）、検査の追加を記す文書、関連テストの sha256 ピン。
- 対象外: rework-planner の出力と、rework で既存の VERIFICATION.md に足すシナリオ ID の形（前提 A4）。既存文書（`TSn` 形式の SPEC.md など）の書き換え（前提 A6）。spec-writer の出力への機械的な検査（前提 A5）。プラグインの version（前提 A7）。

## 2. ビジネス要件

### 2.1 ビジネス目標
- 新規に作られる SPEC.md・VERIFICATION.md・tasks/*.md のシナリオ ID を `TS-n` 形式の 1 種類にする。
- 既存文書の `TSn` 形式は、読み取りで受け付け続ける。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
該当なし

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | spec-writer が SPEC.md に書くシナリオ ID を TS-n にする | confirmed |
| FR2 | plan-writing の TSn 許容を既存文書の読み取りに限る | confirmed |
| FR3 | implementation-planner の出力検査で TSn を弾く | confirmed |
| FR4 | 既存文書の読み取りは両方の形を受け付け続ける | confirmed |
| FR5 | 検査の追加を文書に反映する | confirmed |

### 4.2 機能詳細

#### FR1: spec-writer が SPEC.md に書くシナリオ ID を TS-n にする

- spec-writer は、SPEC.md の Test Scenarios に書く各シナリオに `TS-1`, `TS-2`, … の形の ID を付ける。
- `payload.spec_index.test_scenarios[].id` も同じ形にする。
- そのために `em-workflow/agents/spec-writer.md` の SPEC.md 描画ルールに番号付けのルールを足す（FR/NFR の番号付けルールと同じ書き方）。
- `em-workflow/references/templates/spec-document.md` の `## Test Scenarios` の項目を `TS-n` の ID 付きの書式にする。
- `em-workflow/references/contracts/spec-writer-contract.md` の `spec_index.test_scenarios[].id` にも、この形を明記する。

#### FR2: plan-writing の TSn 許容を既存文書の読み取りに限る

- `em-workflow/skills/plan-writing/SKILL.md` のシナリオ ID ルール（現 305-314 行）を書き換える。
- 新規に書く VERIFICATION.md と tasks/*.md のシナリオ ID は `TS-n` 形式だけにする。
- `TSn` 形式は、既存文書を読むときだけ有効な ID として扱う、と明記する。
- ID を文字列のまま比べ、`TS13` と `TS-13` を別の ID とするルールは残す。

#### FR3: implementation-planner の出力検査で TSn を弾く

- `em-workflow/scripts/validate-worker-output.py` の `--kind worker-result --worker implementation-planner` で `--feature-dir` を渡したときに、検査を 1 つ足す。
- 対象は次の 2 つ。
    - (a) feature-dir 内の VERIFICATION.md
    - (b) `workflow_patch.tasks_patch.entries[].plan` が指す各タスク計画（最後のパス要素が TASK.md のものは除く）
- どちらかに `TSn` 形式のシナリオ ID があれば、検証エラーにする。
- エラーには、該当ファイルと見つかった ID を示す。
- rework-planner の出力にはこの検査を当てない。

#### FR4: 既存文書の読み取りは両方の形を受け付け続ける

- シナリオ ID の抽出（`_TS_ID_RE` = `TS-?\d+` と `extract_verification_scenario_ids`）は `TS-n` と `TSn` の両方を、文字列のまま抽出し続ける。
- 次の処理の挙動も変えない。
    - rework_index の novelty / rename-aware coverage 検査
    - workflow-patch の tests_replace（`TS3` → `TS-3` など）
    - verification_index の読み取り

#### FR5: 検査の追加を文書に反映する

- validator が機械的に実装している不変条件の一覧に、FR3 の検査を足す（`em-workflow/references/phases/create-plan-phase.md` の 9 節）。
- planner 側の文書（`em-workflow/agents/implementation-planner.md` と `em-workflow/references/contracts/planner-contract.md`）にも、新規の VERIFICATION.md・tasks/*.md は `TS-n` のみで、`TSn` は検査で弾かれることを書く。

## 5. 非機能要件

### 5.1 非機能要件一覧
| ID | 要件名 | 状態 |
|----|--------|------|
| NFR1 | 既存テストの互換 | confirmed |
| NFR2 | sha256 ピンの更新 | confirmed |
| NFR3 | テストスイート全体の合格 | confirmed |

### 5.2 非機能要件詳細

#### NFR1: 既存テストの互換
- `tests/test_validate_worker_output.py` の `TestScenarioIdExtractionAcceptsBothForms` と `TestReworkIndexNoveltyWithBothScenarioIdForms`、および `tests/test_requirements_tests_replace.py` を、期待値を変えずに通す。

#### NFR2: sha256 ピンの更新
- `tests/test_gate_option_vocabulary.py` は `validate-worker-output.py` と `tests/test_validate_worker_output.py` の sha256 を固定している（`VALIDATE_WORKER_OUTPUT_SHA256` / `TEST_VALIDATE_WORKER_OUTPUT_SHA256`）。
- この 2 つの値を新しい内容に合わせて更新し、同ファイルの慣例どおり「Refreshed again by scenario-id-ts-hyphen/taskNNNN」のコメントを足す。
- `PINNED_VALIDATOR_TEST_LINE` は変えない。
- `workflow-patch.md` は変更しない（`WORKFLOW_PATCH_SHA256` も固定されているため）。

#### NFR3: テストスイート全体の合格
- `python3 -m unittest discover -s tests` が全件通る。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 既存の `TSn` 形式の読み取り（FR4）と既存テストの期待値（NFR1）を変えない。
- `workflow-patch.md` は変更しない（NFR2）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/scenario-id-ts-hyphen/**`
- `test-docs/scenario-id-ts-hyphen/**`

`feature-docs/scenario-id-ts-hyphen/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/scenario-id-ts-hyphen/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/scenario-id-ts-hyphen/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/scenario-id-ts-hyphen/` ディレクトリを生成しないが、宣言された `test-docs/scenario-id-ts-hyphen/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: 新規に作られる SPEC.md・VERIFICATION.md・tasks/*.md のシナリオ ID が `TS-n` になる（spec-writer.md、spec-document.md、spec-writer-contract.md、plan-writing SKILL.md の記述が `TS-n` のみを定めている）。（FR1, FR2, FR5）
- [ ] AC-2: 新規の VERIFICATION.md・tasks/*.md に `TSn` を含む implementation-planner の出力が、`validate-worker-output.py` の検査でエラーになる。（FR3）
- [ ] AC-3: 既存の `TSn` 形式の文書を含むフィーチャーの読み取りと rework 検証が、今まで通り動く。（FR4, NFR1）
- [ ] AC-4: `python3 -m unittest discover -s tests` が全件通る。sha256 ピンが更新されている。（NFR2, NFR3）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テストシナリオ一覧
| ID | シナリオ | 要件 |
|----|----------|------|
| TS-1 | implementation-planner の結果で、feature-dir の VERIFICATION.md の Test Scenarios に `TS1` がある → `validate_worker_result` がシナリオ ID 形式のエラーを返す。エラーにファイルと ID が含まれる。 | FR3 |
| TS-2 | implementation-planner の結果で、tasks_patch エントリの plan（`tasks/task0001.md`）の本文に `TS2` がある → エラーになる。 | FR3 |
| TS-3 | VERIFICATION.md とタスク計画がすべて `TS-n` 形式 → `TSn` 形式のエラーは出ない。 | FR3 |
| TS-4 | `TS-13` と `TS13` が混在する VERIFICATION.md → エラーになる。 | FR3 |
| TS-5 | `TSn` が fenced code block か HTML コメントの中にだけある → エラーにならない。 | FR3 |
| TS-6 | `XTS1` / `UTS46` のように英数字に続く並び → エラーにならない。 | FR3 |
| TS-7 | plan が TASK.md を指すエントリ（本文に `TS1` がある）→ この検査ではエラーにならない。 | FR3 |
| TS-8 | rework-planner の結果で、feature-dir の VERIFICATION.md が `TSn` 形式 → `TSn` 形式のエラーは出ない。既存の rework_index 検査は `TSn` を新旧どちらでも判定できる。 | FR3, FR4 |
| TS-9 | 既存の `TestScenarioIdExtractionAcceptsBothForms` / `TestReworkIndexNoveltyWithBothScenarioIdForms` / `test_requirements_tests_replace` が変更なしで通る。 | FR4, NFR1 |
| TS-10 | spec-writer.md・spec-document.md・spec-writer-contract.md・plan-writing SKILL.md の記述が、新規文書に `TS-n` を求めている。plan-writing は `TSn` を既存文書の読み取りに限っている（文書の内容を確かめるテスト）。 | FR1, FR2 |
| TS-11 | create-plan-phase.md 9 節の validator 実装済み一覧と、planner 側の文書に `TSn` 検査が書かれている。 | FR5 |
| TS-12 | `tests/test_gate_option_vocabulary.py` の sha256 ピンが新しい内容と一致し、`python3 -m unittest discover -s tests` が全件通る。 | NFR2, NFR3 |

### 12.2 エッジケース
- 同じ VERIFICATION.md に `TS-13` と `TS13` が混在する → `TSn` を含むのでエラー。
- fenced code block や HTML コメントの中にある `TSn` → 検査の対象外（既存の `_strip_noise` と同じ扱い）。
- 英数字の直後に続く TS+数字（例: `XTS1`、`UTS46`）→ シナリオ ID とみなさず、エラーにしない。
- 最小 tier で plan が TASK.md を指すエントリ → 検査しない。最小 tier では VERIFICATION.md が作られない。
- `--feature-dir` を渡さない呼び出し → 既存の files/AC 検査と同じく、`TSn` 検査も実行しない。
- 再計画（replace_own で VERIFICATION.md を書き直す）で旧文書が `TSn` だった → 書き直した VERIFICATION.md は `TS-n` でなければエラー。
- 既存の SPEC.md が `TSn` 形式（この変更より前に作られたフィーチャー）のまま create-plan に進む → planner は同じ番号の `TS-n`（`TS3` → `TS-3`）で VERIFICATION.md を書く。SPEC.md は書き換えない。
- rework-planner の結果で、feature-dir の VERIFICATION.md が `TSn` のまま → 受け入れる（新しい検査は rework-planner に当てない）。
- tests_replace の `TS1` → `TS-1` の付け替え → 今まで通り受け入れる。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `TS-n` 形式 | `TS`、ハイフン、1 桁以上の数字からなるシナリオ ID |
| `TSn` 形式 | `TS` と 1 桁以上の数字からなり、ハイフンを含まないシナリオ ID |

## 14. 確認事項

### 14.1 確認済み事項

前提（すべて可逆）:

- [x] A1: `TSn` の判定は既存の文法（`TS-?\d+`）で見つかる ID のうちハイフンを含まないものとし、さらに直前が英数字でないことを条件にする。読み取り用の抽出（境界条件なし）は変えない。
- [x] A2: 検査範囲は文書全体から fenced code block と HTML コメントを除いた部分にする（既存の `_strip_noise` と同じ）。インラインのコードスパンは除かない（バッククォートで囲むだけで検査をすり抜けられないようにするため）。
- [x] A3: 「新規に書く」文書は、implementation-planner の結果を検査するときの次の 2 つとする。feature-dir の VERIFICATION.md、`tasks_patch.entries[].plan` が指すタスク計画。再計画での書き直しもここに含む。`carried_task_ids` で持ち越したタスクの計画は検査しない。
- [x] A4: rework-planner の出力と、rework で既存の VERIFICATION.md に足すシナリオ ID の形は、この feature の範囲外とし、今の挙動のままにする。
- [x] A5: spec-writer の出力（`spec_index.test_scenarios[].id` や SPEC.md）への機械的な検査は足さない。SPEC.md 側は prompt・テンプレート・contract の記述で `TS-n` にする（依頼が求める検査は planner 側だけのため）。
- [x] A6: 既存の SPEC.md が `TSn` のフィーチャーでは、planner は同じ番号の `TS-n` で VERIFICATION.md を書き、SPEC.md は書き換えない（既存文書の書き換えは範囲外）。
- [x] A7: プラグインの version は触らない（core-plugin-version-bump ルールに従い、Actions が patch を上げる）。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

該当なし
