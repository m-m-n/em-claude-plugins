---
title: "repo-suite-pinned-test-drift"
created_date: 2026-09-24
status: draft
---

# repo-suite-pinned-test-drift - 要件定義書

## 1. 概要

### 1.1 背景
リポジトリルートで `python3 -m unittest discover -s tests` を実行すると、現 HEAD で 16 件のテストが失敗する。いずれも em-workflow のドキュメント本文・マニフェストの値・`review-rules.yaml` の定義、またはプラグインの version をピン留めしたテストで、対象側の変更に期待値が追随していない。

### 1.2 目的
- リポジトリスイートを終了コード 0 で通す。
- version の特定値ピン留めを、version が上がっても失敗しない検証に置き換える。

### 1.3 スコープ
- 対象: Orchestrator が現 HEAD で観測した 16 件の失敗テスト（4.1 の F01〜F10）。
- em-workflow 配下の変更: `em-workflow/skills/develop/SKILL.md` の 1 箇所の言い換え（F04）と、version の bump（F11）。
- 対象外: SKILL.md の argument-hint 行・Step C の文面、`review-rules.yaml` の選定規則、`plugin.json` の description の変更。

## 2. ビジネス要件

### 2.1 ビジネス目標
- `python3 -m unittest discover -s tests` がリポジトリルートで終了コード 0 になる。
- verify フェーズで既存失敗と新規回帰を base commit 比較で切り分ける作業を不要にする。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の verify フェーズ | `workflow.yaml` の `project.components.main.test_command` としてリポジトリスイートを実行する |

### 2.3 期待される効果
- リポジトリスイートが終了コード 0 で終わる。
- verify フェーズで base commit との比較による切り分けが要らなくなる。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | リポジトリスイートの全件実行 | em-workflow の verify フェーズ | 高 |

### 3.2 ユースケース詳細

#### UC01: リポジトリスイートの全件実行

**アクター**: em-workflow の verify フェーズ

**事前条件**:
- F11 の version bump が適用された integration worktree である。

**基本フロー**:
1. リポジトリルートで `python3 -m unittest discover -s tests` を実行する。
2. 全テストが pass する。

**代替フロー**:
- 該当なし

**事後条件**:
- 終了コードが 0 である。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| F01 (FR1) | argument-hint 期待値の追随 | `test_develop_once_option.py` の期待値を現行の argument-hint 行に合わせる | 高 |
| F02 (FR2) | Step C batch 自動選択文面の追随 | `test_step_c_verify_failed_default.py` の期待文面を現行の Step C 1. に合わせる | 高 |
| F03 (FR3) | Non-packet gates 参照検査の空白正規化 | 改行をまたぐ参照を空白除去後に比較する | 高 |
| F04 (FR4) | develop SKILL.md の AskUserQuestion 出現数を上限内に戻す | `--pr` 項目の 1 箇所を言い換える | 高 |
| F05 (FR5) | em-workflow マニフェスト非 version ダイジェストの追随 | `test_muse_consent_version_bump.py` のダイジェストを更新する | 高 |
| F06 (FR6) | abort-terminal-commit-precedence の version リテラル固定の撤去 | 下限＋一致＋形式の検証に置き換える | 高 |
| F07 (FR7) | stop-reason-coverage の version リテラル固定の撤去 | 下限の検証に置き換える | 高 |
| F08 (FR8) | codex-wrapper-fallback-removal の version リテラル固定の撤去 | 一致＋下限の検証に置き換える | 高 |
| F09 (FR9) | batch-structured-result-output の em-review version 固定の撤去 | version を形式検査に変える | 高 |
| F10 (FR10) | review-rules.yaml 期待値の追随 | `test_reviewers_primary_chains.py` の 4 検査を現行定義に合わせる | 高 |
| F11 (FR11) | em-workflow の version bump | 0.2.3 → 0.2.4 | 高 |

### 4.2 機能詳細

#### F01 (FR1): argument-hint 期待値の追随

**説明**: `tests/test_develop_once_option.py` の `ARGUMENT_HINT_LINE` を、`em-workflow/skills/develop/SKILL.md` 4 行目の現行 argument-hint 行に更新する。`test_argument_hint_line_includes_once_and_retains_existing_tokens` のトークン検査に `--pr` を加える。

現行 argument-hint 行:
```
argument-hint: "[feature-path] [--report-only] [--batch] [--once] [--pr] [task-description]"
```

**ビジネスルール**:
- SKILL.md の argument-hint 行は変更しない。

#### F02 (FR2): Step C batch 自動選択文面の追随

**説明**: `tests/test_step_c_verify_failed_default.py` の `BATCH_AUTO_SELECT_PHRASE` を、SKILL.md Step C 1. の現行文面に更新する。

現行文面:
```
batch: `--pr` 未指定なら質問せず自動で「ブランチを残す」を選ぶ。マージ・push・PR 作成のいずれも行わない
```

**ビジネスルール**:
- 比較は既存の `_strip_ws` による空白除去比較のまま。

#### F03 (FR3): Non-packet gates 参照検査の空白正規化

**説明**: `tests/test_step_c_verify_failed_default.py` の `test_batch_non_packet_gates_reference_present` で、「`batch-mode.md` の Non-packet gates 表」の検査を `_strip_ws` 適用後の部分文字列比較にする。本文 918-919 行で改行をまたいでいるため。

**ビジネスルール**:
- `develop.completion` の検査は維持する。
- SKILL.md は変更しない。

#### F04 (FR4): develop SKILL.md の AskUserQuestion 出現数を上限内に戻す

**説明**: `em-workflow/skills/develop/SKILL.md`「引数処理」の `--pr` 項目（106 行目）にある「AskUserQuestion を出さない」を、ツール名 `AskUserQuestion` を含まない表現（例:「質問を出さない」）に言い換え、ファイル内の出現数を 7 以下にする。

**ビジネスルール**:
- `tests/test_muse_consent_no_new_questions.py` の `BASELINE_COUNTS` は変更しない。
- `--pr` の挙動の記述内容は変えない。
- Step C 側（910 行目）の `AskUserQuestion` には触れない。

#### F05 (FR5): em-workflow マニフェスト非 version ダイジェストの追随

**説明**: `tests/test_muse_consent_version_bump.py` の `EM_WORKFLOW_MANIFEST_NONVERSION_SHA256` を、現行 `em-workflow/.claude-plugin/plugin.json` の非 version 内容のダイジェスト `bf70d7104511c338b6f076c3d9ab08b6a19b757b59d45397324242f11008ebf0` に更新し、基準時点を説明するコメントを更新する。この値は `tests/test_batch_structured_result_output_version_bump.py` の `PLUGIN_MANIFEST_NONVERSION_SHA256` と同値。

**ビジネスルール**:
- `plugin.json` の description は変更しない。

#### F06 (FR6): abort-terminal-commit-precedence の version リテラル固定の撤去

**説明**: `tests/test_abort_terminal_commit_precedence.py` の `TestVersionBump` の 2 テストを、`0.2.2` との文字列一致から、次の検証に置き換える。
- `plugin.json` とマーケットプレイスの em-workflow エントリの version が X.Y.Z 形式である。
- 数値比較で 0.2.2 以上である。
- 両者が一致する。

**ビジネスルール**:
- テストメソッド名・docstring・`EXPECTED_VERSION` 定数をこの内容に合わせて改める。

#### F07 (FR7): stop-reason-coverage の version リテラル固定の撤去

**説明**: `tests/test_stop_reason_coverage_version_bump.py` の `test_version_is_the_literal_bump_target` と `test_entry_version_is_the_literal_bump_target` を、`0.2.2` との文字列一致から、数値比較で 0.2.1 以上の検証に置き換える。

**ビジネスルール**:
- メソッド名・docstring・モジュール docstring の該当記述を合わせて改める。

#### F08 (FR8): codex-wrapper-fallback-removal の version リテラル固定の撤去

**説明**: `tests/test_codex_wrapper_fallback_removal_version_bump.py` の `TestSpecificVersionValues` の 2 テストを、`PLUGIN_SPECS[*]["expected"]` との一致から、次の検証に置き換える。
- マニフェストとマーケットプレイスエントリの version が一致する。
- 数値比較で各プラグインの記録済み下限以上である。

**ビジネスルール**:
- `PLUGIN_SPECS` の `"expected"` キーと「later features update this literal」系のコメントを撤去する。

#### F09 (FR9): batch-structured-result-output の em-review version 固定の撤去

**説明**: `tests/test_batch_structured_result_output_version_bump.py` の `_assert_em_review_entry_unchanged` を、name / author / category / source の完全一致と、version の形式検査（X.Y.Z）に変える。

**ビジネスルール**:
- `EM_REVIEW_VERSION` 定数の用途を合わせて改める。
- `test_em_review_matcher_rejects_altered_identity_field` の `("version", "99.0.0")` ケースは、形式不正 version を拒否するケースに置き換える。

#### F10 (FR10): review-rules.yaml 期待値の追随

**説明**: `tests/test_reviewers_primary_chains.py` の `review-rules.yaml` 検査 4 件を現行定義に更新する。

| テスト | 更新後の期待値 |
|--------|----------------|
| `test_baseline_unchanged` | `baseline: [comprehensive, security]` |
| `test_rules_block_unchanged` | 現行の 4 規則: data-persistence→performance / concurrency, external-io→performance / api-contract→architecture / if_complexity: high→architecture, comprehensive |
| `test_cross_validation_data_block_unchanged` | when_any は `- complexity: high` のみ |
| `test_computation_semantics_preserved_in_prose` | 「re-evaluates it after Layer 2」を「Layer 1 settles the value and Layer 2 cannot change it」に置き換える |

**ビジネスルール**:
- モジュール・クラス docstring の該当記述を合わせて改める。
- `review-rules.yaml` は変更しない。

#### F11 (FR11): em-workflow の version bump

**説明**: F04 で em-workflow 配下を変更するため、em-workflow の version を 0.2.3 から 0.2.4 に上げる。

**ビジネスルール**:
- 変更箇所は `em-workflow/.claude-plugin/plugin.json` の version と `.claude-plugin/marketplace.json` の em-workflow エントリの version の 2 箇所で、同じ値にする。
- em-review の version は変更しない。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 該当なし

### 5.2 セキュリティ要件
- 該当なし

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- NFR1: 変更するテストモジュールは Python 標準ライブラリのみを import する。
- NFR2: FR6〜FR9 で変更した version 検査は、どのプラグインの現行 version のリテラルとも一致比較しない。
- NFR3: 変更・新設した各 matcher は、偽造データに対する否定証明テストを持つ（既存の否定証明が検査対象の変化で無効になる場合は置き換える）。

### 5.5 互換性要件
- NFR4: `plugin.json` と `marketplace.json` の version 以外のフィールドは変更しない。

## 6. UI/UX要件

該当なし（UI・画面・視覚要素を持たない）。

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- テストモジュールは Python 標準ライブラリのみを import する（NFR1）。
- em-workflow 配下を変更したら、`plugin.json` とマーケットプレイスエントリの version を同じ値に上げる（`.claude/rules/core-plugin-version-bump.md`）。

### 9.2 ビジネス上の制約
- `tests/test_muse_consent_no_new_questions.py` の `BASELINE_COUNTS` は上げない。

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/repo-suite-pinned-test-drift/**`
- `test-docs/repo-suite-pinned-test-drift/**`

`feature-docs/repo-suite-pinned-test-drift/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/repo-suite-pinned-test-drift/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/repo-suite-pinned-test-drift/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 調査対象外のテストが em-workflow の version リテラル `0.2.3`、または F04 で言い換える「AskUserQuestion を出さない」の文面をピン留めしている場合、F04 / F11 の適用で新たに失敗する | 中 | 同じ扱い（リテラル version は下限検証へ、文面は現行へ追随）の対象に含める。AC1 の全件実行で検出する |
| F04 の言い換えが Step C 側（910 行目）の `AskUserQuestion` に及ぶと、`test_askuserquestion_and_three_way_wording_present` が失敗する（Step C 節内の出現を要求している） | 中 | F04 は `--pr` 項目（106 行目）の 1 箇所のみを言い換える |
| 作業中に main が進み、他 feature が version を上げる | 低 | FR6〜FR9 の検証は下限比較のため失敗しない。統合時は F11 の値をその時点の現行値より大きい patch に合わせる |
| `plugin.json` の description が将来変わると、非 version ダイジェストを固定している 2 モジュール（`test_muse_consent_version_bump` / `test_batch_structured_result_output_version_bump`）が同時に失敗する | 低 | 本 feature では description を変えない（NFR4） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: F11 の version bump 適用後の integration worktree で `python3 -m unittest discover -s tests` が終了コード 0 で終わる。
- [ ] AC2: Orchestrator が観測した 16 件がすべて pass する（test_abort_terminal_commit_precedence 2 件、test_batch_structured_result_output_version_bump 1 件、test_codex_wrapper_fallback_removal_version_bump 2 件、test_develop_once_option 1 件、test_muse_consent_no_new_questions 1 件、test_muse_consent_version_bump 1 件、test_reviewers_primary_chains 4 件、test_step_c_verify_failed_default 2 件、test_stop_reason_coverage_version_bump 2 件。FR6 / FR7 で改名したものは改名後の名前）。
- [ ] AC3: FR6〜FR9 の version matcher は、偽造した上位 version（例: 99.0.0、両レジストリ一致）を受理し、下限未満の version・形式不正の version・レジストリ不一致を拒否する。
- [ ] AC4: `em-workflow/skills/develop/SKILL.md` の `AskUserQuestion` 出現数が 7 以下で、`BASELINE_COUNTS` の値は変更されていない。
- [ ] AC5: em-workflow の `plugin.json` とマーケットプレイスエントリの version がともに 0.2.4、em-review はともに 0.5.13 のまま。
- [ ] AC6: SKILL.md の argument-hint 行、Step C の文面、`review-rules.yaml` の選定規則、`plugin.json` の description は変更されていない（FR4 の 1 箇所の言い換えを除く）。

### 11.2 KPI
| 指標 | 目標値 | 測定方法 |
|------|--------|----------|
| リポジトリスイートの失敗件数 | 0 | `python3 -m unittest discover -s tests` |

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1, AC2）: integration worktree で `python3 -m unittest discover -s tests` を実行し、失敗 0・終了コード 0 を確認する。
- [ ] TS2（AC3）: FR6〜FR9 で変更した各 matcher に対し、偽造上位 version（受理）、下限未満（拒否）、形式不正（拒否）、レジストリ不一致（拒否）の各ケースを hermetic なテストで確認する。
- [ ] TS3（AC4）: `test_no_develop_or_review_document_exceeds_its_pinned_budget` が `BASELINE_COUNTS` 無変更のまま pass することを確認する。
- [ ] TS4（AC5）: `tests/test_plugin_version_parity.py` を含む既存の version 一致テストが 0.2.4 で pass することを確認する。
- [ ] TS5（AC6）: 差分を確認し、em-workflow 配下の変更が SKILL.md 106 行付近の 1 箇所と `plugin.json` の version のみであることを確認する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| リポジトリスイート | リポジトリルートで `python3 -m unittest discover -s tests` により実行されるテスト群 |
| ピン留めテスト | ドキュメント本文・マニフェスト・定義ファイルの値を固定値として検査するテスト |
| 下限検証 | version を X.Y.Z として数値比較し、記録済みの下限以上であることを確かめる検証 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: fba3d7e（`--pr` 追加）と 6c4971e（security 常時選択）の変更は意図どおりであり、ドキュメント・選定規則は戻さずテスト側を追随させる。
- [x] A2: version の特定値ピン留め（FR6〜FR9）は新しい値へ更新せず、下限＋レジストリ一致＋形式の検証に置き換える。version は変更のたびに上がる運用（`.claude/rules/core-plugin-version-bump.md`）で、本 feature 自身も FR11 で bump するため。
- [x] A3: develop SKILL.md の AskUserQuestion 上限超過は、上限（7）を上げずに本文の言い換えで解消する。`test_muse_consent_no_new_questions.py` のモジュール docstring が「the baseline is never raised to make that pass」と定めているため。
- [x] A4: em-workflow の bump は patch（0.2.3 → 0.2.4）とする。変更はドキュメント 1 箇所の言い換えで挙動を変えない。
- [x] A5: タスク記述の `test_codex_wrapper_fallback_removal_version_bump.TestSpecificVersionValues.test_em_workflow_reads_0_1_78` は、現行の `test_em_workflow_manifest_and_entry_agree_on_the_current_version` に改名済みのものを指す。
- [x] A6: 対象範囲はタスク記述の 6 件ではなく、Orchestrator が現 HEAD で観測した 16 件（同種のピン留め追随漏れ）とする。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- `.claude/rules/core-plugin-version-bump.md`: version bump の運用
