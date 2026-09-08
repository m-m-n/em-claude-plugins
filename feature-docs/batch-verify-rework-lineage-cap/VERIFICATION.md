# Verification Document: batch-verify-rework-lineage-cap

## Overview

**Feature**: batch-verify-rework-lineage-cap /
**SPEC.md**: `feature-docs/batch-verify-rework-lineage-cap/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/batch-verify-rework-lineage-cap/IMPLEMENTATION.md`

本書は統合後の検証を定義する。タスク単位の受け入れ条件は各タスク計画
（`tasks/taskNNNN.md`）が持つ。

## Build Verification

- Command: 該当なし（`project.components.main.build_command` は空。本
  フィーチャーはビルド生成物を持たない）
- Expected: 該当なし

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0、失敗 0 / エラー 0
- Coverage target: 数値カバレッジの目標は置かない（対象が Markdown SSOT で
  あり、カバレッジ計測の対象コードが無いため）。代わりに「全 FR/NFR が
  1 つ以上のシナリオに写像していること」を下記の要件カバレッジ表で担保する。

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | SKILL.md の verify フェーズ節と batch-mode.md の verify.failed 行に対し、系譜カウント（ID ごとの累積出現回数）と系譜 cap = 1、および「過去ラウンドの failed_items に現れなかった新規 ID は新規予算を得る」旨が述べられていることを構造的に検査する。旧文言を含む合成テキストに対して同じ matcher が失敗する負の証明を併置する | 両文書に系譜カウントの記述があり、負の証明クラスが期待どおり失敗を検出する | Unit |
| TS2 | hard cap 3 が rounds に対する上限として、系譜 cap とは独立した判定であることが SKILL.md と batch-mode.md の双方で述べられていることを検査する | 双方に独立評価の記述がある | Unit |
| TS3 | cap 到達時の記述が「verify.status は failed のまま retrospect へ進む」であり、旧文言「`failed` のまま報告して停止」が SKILL.md 全文から消えていること、verify 側の残項目に `deferred` を与える記述が無いことを検査する | 新文言が存在し、旧文言と deferred 付与の記述が存在しない | Unit |
| TS4 | SKILL.md の retrospect.yaml スキーマ例で `signals.verification_failures` が下位構造付き（verify の failed_items をそのまま載せる形）で定義されており、キーのみの状態でないことを検査する | 下位構造が定義されている | Unit |
| TS5 | retrospect.yaml スキーマ例に `follow_up_drafts` が存在し、`origin_kind` / `origin_id` / `title` / `body` の 4 フィールドを持ち、rework-task-synthesis.md Invariant 6 を参照していること、および生成母集団が「cap 到達時点で未解決の failed_items 全件」と明記されていることを検査する | 4 フィールドと Invariant 6 の参照、母集団の明記がすべて存在する | Unit |
| TS6 | Step C の実行条件が verify の failed を許容する形になっていることを検査し、かつ Step C 見出しを境界に使う既存 2 モジュールの見出し定数が新見出し全文へ更新され、それを使う全クラスが setUpClass で例外を出さずに通ることを確認する | 新しい実行条件が見出しに現れ、既存 2 モジュールが緑 | Unit |
| TS7 | workflow-schema.md の batch ブロックが `review_rework_count` と `verify_rework: {rounds, failed_id_counts}` の構造を示し、`verify_rework_count` の記述が消えていることを検査する | 新構造が示され、旧キーが消えている | Integration |
| TS8 | 回帰ガード。review-phase.md の Phase R5 batch 節（`batch.review_rework_count == 0` / `resolution: deferred` / `"batch mode: rework cap reached"`）と、batch-mode.md の review.residual-critical-high 行が変更されていないこと、review-phase.md が `verify_rework_count` を参照していないことを検査する | review 側の記述がすべて現状のまま | Integration |
| TS9 | 統合ブランチの差分に `em-workflow/references/rework-task-synthesis.md` が含まれないことを確認する（`git diff` による直接確認） | 同ファイルが差分に現れない | Integration |
| TS10 | `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリの version が一致し、変更前の値より上がっていることを確認する | 2 マニフェストの version が一致し、かつ増加している | Integration |
| TS11 | Step C の完了方式 AskUserQuestion が三択を保ったまま、`verify.status` が failed の場合の推奨デフォルトを「ブランチを残す」とする条件分岐と、質問文への failed の事実・failed_items 件数の提示が述べられていること、無条件デフォルトが「マージ」である旧記述が残っていないことを検査する | 条件分岐と提示要件が存在し、旧記述が消えている | Unit |
| TS12 | cap の値と数え方の定義本文が単一のドキュメントにのみ存在し、他ドキュメントは参照にとどまることを検査する（非定義元での値のベタ書きを検出する。review 側の cap 1 の記述は検出対象から除外する） | 定義本文は SKILL.md verify 節のみ。batch-mode.md / workflow-schema.md に verify cap の数値が現れない | Unit |
| TS13 | retrospect 節が `follow_up_drafts` の title / body を未信頼入力として扱う旨を述べ、`references/contracts/worker-envelope.md` の Untrusted-Input Handling を参照していることを検査する | 未信頼入力扱いの記述と参照が存在する | Unit |
| TS14 | スイート全体がサードパーティ import なしで完走し、変更されたファイル集合が NFR5 の範囲（SKILL.md / batch-mode.md / workflow-schema.md / マニフェスト 2 件 / tests/ 配下）に収まっていることを確認する | `python3 -m unittest discover -s tests` が全件緑。`git diff --name-only` の結果が NFR5 の範囲に収まる（feature-docs/ と test-docs/ のワークフロー生成物は除く） | Integration |
| TS15 | cap 到達で `failed` のまま進む走行が停止条件 1 / 停止条件 3 に捕まらないことが batch 専用の独立条項として述べられていること、既存の自動再エントリ carve-out の網羅性宣言が無改変であること、および cap 到達走行の終端行が `state=stopped` / `step=verify` / `reason=verify_rework_cap_reached` として明記されていることを検査する | 独立条項と終端状態の記述が存在し、既存 carve-out 検査クラスが無改変で緑 | Unit |

## Code Quality Verification

- Format: 該当なし（`project.components.main.format_command` は空）
- 静的解析: 該当なし。代わりに `python3 -m unittest discover -s tests` に含まれる
  既存のプラグイン不変条件テスト（`tests/test_check_plugin_invariants.py`、
  `tests/test_reference_sweep.py` 等）が、参照の切れとプラグイン構造の破れを
  機械的に検出する。

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | 全 functional requirement が実装され検証されている | 下記の要件カバレッジ表がすべて埋まっていること |
| SC2 | TS1–TS15 がすべて通る | `python3 -m unittest discover -s tests` + TS9 / TS10 / TS14 の直接確認 |
| SC3 | セキュリティ要件（NFR6）が満たされている | TS13 |
| SC4 | AC1–AC14 が満たされている | 各 AC に対応する FR の行を要件カバレッジ表で追跡 |
| SC5 | 変更されたファイル集合が NFR5 の範囲に収まっている | TS14 の `git diff --name-only` による確認 |
| SC6 | `em-workflow/references/rework-task-synthesis.md` が変更されていない | TS9 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS3 |
| FR4 | task0003 | TS4 |
| FR5 | task0003 | TS5 |
| FR6 | task0002 | TS6 |
| FR7 | task0002 | TS15 |
| FR8 | task0001 | TS7 |
| FR9 | task0004 | TS11 |
| FR10 | task0004 | TS8 |
| FR11 | task0002 | TS15 |
| FR12 | task0005 | TS10 |
| NFR1 | task0001 | TS12 |
| NFR2 | task0004 | TS9 |
| NFR3 | task0001, task0002, task0003, task0004, task0005 | TS14 |
| NFR4 | task0001, task0002, task0003, task0004, task0005 | TS14 |
| NFR5 | task0001, task0002, task0003, task0004, task0005 | TS14 |
| NFR6 | task0003 | TS13 |

## E2E Testing

プロジェクトに E2E フレームワークは無く、`project.components.main.e2e_test_command`
も空。E2E テストは実施しない。

## Manual Testing (E2E Not Possible)

- [ ] TS9: `git diff --name-only {base} HEAD` の結果に
      `em-workflow/references/rework-task-synthesis.md` が含まれないことを目視
      確認する（NFR2）。
- [ ] TS10: `em-workflow/.claude-plugin/plugin.json` と
      `.claude-plugin/marketplace.json` の em-workflow エントリの version が
      同じ値であり、統合前の値より上がっていることを目視確認する（FR12）。
- [ ] TS14（範囲確認部分）: `git diff --name-only {base} HEAD` の結果が
      NFR5 の範囲（`em-workflow/skills/develop/SKILL.md`、
      `em-workflow/references/batch-mode.md`、
      `em-workflow/references/workflow-schema.md`、
      `em-workflow/.claude-plugin/plugin.json`、
      `.claude-plugin/marketplace.json`、`tests/` 配下）と、ワークフローが
      生成する `feature-docs/{feature}/**` / `test-docs/{feature}/**` に
      収まっていることを目視確認する。
- [ ] TS7（直接確認部分）: `em-workflow/references/workflow-schema.md` の
      `batch` ブロックを目視で読み、`verify_rework` の 2 キーが構造として
      読み取れ、cap の数値がここに書かれていないことを確認する（FR8 / NFR1）。

（design ステップは `skipped` のため、モックとの目視照合は対象外。）

## Performance / Security Verification

- Performance: 該当なし。
- Security（NFR6）: `follow_up_drafts` の `title` / `body` が未信頼入力として
  扱われ、外部サービスへ命令として解釈され得る形で出力されない旨が retrospect
  節に明記されていること — TS13 で確認する。

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit | TS1, TS2, TS3, TS4, TS5, TS6, TS11, TS12, TS13, TS15 | 10 | 0 | 0 |
| Integration | TS7, TS8, TS9, TS10, TS14 | 3 | 0 | 4 項目（TS7 の直接確認 / TS9 / TS10 / TS14 の範囲確認） |
| 合計 | 15 シナリオ | 13 | 0 | 4 |
