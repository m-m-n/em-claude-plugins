---
title: "batch-verify-rework-lineage-cap"
created_date: 2026-09-06
status: draft
---

# batch-verify-rework-lineage-cap - 要件定義書

## 1. 概要

### 1.1 背景

batch モードの verify 自動 rework の上限は、現在 `batch.verify_rework_count` による固定回数（cap 1）で数えられている。この数え方では、検証カバレッジ強化によって新規に発見された欠陥も、既に 1 回消費された同一の予算に載るため、回数上限によって握り潰される。また cap 到達時は `failed` のまま報告して停止するため、retrospect と完了処理（Step C）に到達せず、integration ブランチが宙に浮いたまま残る。

### 1.2 目的

- batch モードの verify 自動 rework 上限を、固定回数（cap 1）から「失敗項目 ID の系譜ごとの再発回数」ベースへ変える。
- 検証カバレッジ強化によって新規に発見された欠陥が、回数上限によって握り潰されない状態にする。
- cap 到達後も走行を停止させず、retrospect と完了処理（Step C）まで到達させ、integration ブランチを宙に浮かせない。
- 未解決の failed_items を機械可読な follow-up draft として retrospect.yaml に引き渡し、外部サービスへの引き継ぎを自動化可能にする。

### 1.3 スコープ

変更範囲は次に閉じる（NFR5）。

- `em-workflow/skills/develop/SKILL.md`
- `em-workflow/references/batch-mode.md`
- `em-workflow/references/workflow-schema.md`
- `em-workflow/.claude-plugin/plugin.json`
- リポジトリルート `.claude-plugin/marketplace.json`
- `tests/` 配下

review 側の cap 到達時挙動と `batch.review_rework_count` はスコープ外（FR10）。`em-workflow/references/rework-task-synthesis.md` は変更しない（NFR2）。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| BO1 | batch モードの verify 自動 rework 上限を、固定回数（cap 1）から「失敗項目 ID の系譜ごとの再発回数」ベースへ変える |
| BO2 | 検証カバレッジ強化によって新規に発見された欠陥が、回数上限によって握り潰されない状態にする |
| BO3 | cap 到達後も走行を停止させず、retrospect と完了処理（Step C）まで到達させ、integration ブランチを宙に浮かせない |
| BO4 | 未解決の failed_items を機械可読な follow-up draft として retrospect.yaml に引き渡し、外部サービスへの引き継ぎを自動化可能にする |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| batch 走行の実行者 | 人が張り付かない無人走行で em-workflow を回す利用者。cap 到達後も完了処理まで到達することを期待する（BO3） |
| batch 走行の結果を受け取る外部サービス | batch 終端行と retrospect.yaml の follow_up_drafts を機械可読な入力として受け取る側（BO4、FR11） |
| interactive 走行の実行者 | Step C の三択を自分で選ぶ利用者（FR9） |

### 2.3 期待される効果

- 新規に発見された欠陥に新規の rework 予算が与えられ、回数上限による握り潰しが起きなくなる。
- cap 到達走行でも worktree 掃除と終了報告が行われ、integration ブランチが宙に浮かない。
- 未解決の failed_items が定型の follow-up draft として引き渡され、外部サービスへの引き継ぎが自動化可能になる。

## 3. ユースケース

### 3.1 ユースケース一覧

本フィーチャーは既存の batch 走行フローの改訂であり、要件は第 4 章の機能要件および第 5 章の非機能要件として確定している。ユースケース単位の定義は行っていない。

### 3.2 ユースケース詳細

該当なし（3.1 参照）。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | ステータス |
|----|--------|------|-----------|
| FR1 | 系譜カウントによる cap 判定 | failed item ID ごとの累積出現回数で cap を判定する | resolved |
| FR2 | グローバル hard cap | `rounds` が 3 に達したら cap 到達とする | resolved |
| FR3 | cap 到達時は停止せず retrospect へ | `failed` のまま retrospect フェーズへ進む | resolved |
| FR4 | retrospect への失敗項目と証拠の引き渡し | `signals.verification_failures` の構造を確定させる | resolved |
| FR5 | follow_up_drafts の新設 | retrospect.yaml に定型の follow-up draft を出力する | **tbd** |
| FR6 | Step C 実行条件の変更 | `failed` のままでも Step C に到達できるようにする | resolved |
| FR7 | Step B 停止条件との整合 | 停止条件 1 / 3 に捕まらないようにする | **tbd** |
| FR8 | workflow-schema.md の batch ブロック構造 | 系譜判定に必要な履歴を持てる構造に更新する | resolved |
| FR9 | interactive の Step C デフォルト条件付き変更 | 三択は維持し、推奨デフォルトのみ切り替える | resolved |
| FR10 | review 側の非変更 | review の cap 挙動とカウンタを変更しない | resolved |
| FR11 | batch 終端行の扱い | cap 到達走行の終端状態を確定する | **tbd** |
| FR12 | プラグイン version の同時 bump | plugin.json と marketplace.json を同じ値へ上げる | resolved |

### 4.2 機能詳細

#### FR1: 系譜カウントによる cap 判定

**説明**: `batch.verify_rework.failed_id_counts` に failed item ID ごとの累積出現回数を保持し、過去ラウンドの `failed_items` に現れなかった新規 ID には新規予算を与える。系譜 cap は 1 とし、同一 ID が 2 回目の `failed_items` に現れた時点で cap 到達とする。

**ステータス**: resolved

#### FR2: グローバル hard cap

**説明**: `batch.verify_rework.rounds` が 3 に達したら cap 到達とする。系譜 cap とは独立に評価し、「新しい問題が湧き続ける」ケースの暴走を止める。

**ステータス**: resolved

#### FR3: cap 到達時は停止せず retrospect へ

**説明**: cap 到達時、`verify.status` は `failed` のまま retrospect フェーズへ進む。走行を停止しない。残項目を `deferred` にもしない（review の defer が「リスク受容の記録」であるのに対し、verify の defer は「検証の偽装」になるため）。

**ステータス**: resolved

#### FR4: retrospect への失敗項目と証拠の引き渡し

**説明**: `failed_items` と検証の証拠（ビルド・フォーマット・非 race 実行等の結果）を retrospect.yaml に引き渡す。現在キーのみで下位構造が未定義の `signals.verification_failures` を、verify の `failed_items` をそのまま載せる形で構造確定させる。

**ステータス**: resolved

#### FR5: follow_up_drafts の新設

**説明**: retrospect.yaml に `follow_up_drafts` を新設し、`origin_kind` / `origin_id` / `title` / `body` を出力する。`origin_kind` / `origin_id` の対は `references/rework-task-synthesis.md` Invariant 6 が定義済みのものをそのまま使い、再定義しない。

**ステータス**: **tbd**

**TBD 理由**: draft の生成母集団が未決定 — 「cap 到達時点で未解決の `failed_items` 全件」か「系譜 cap に触れた ID のみ」か。後者を採ると hard cap 3 で停止したケース（毎ラウンド新規 ID で、系譜 cap に触れた ID が 1 つも無い）で draft が空になり、受け入れ条件「follow-up task の draft が定型出力される」が満たせない分岐が生じる。batch policy create-spec.requirement-clarification の action: codex_consultation が Codex CLI の usage limit により実行不能で、unresolved: record_tbd が適用された。キー・フィールド構成（origin_kind / origin_id / title / body）と Invariant 6 の引用方針は確定済みで、未確定なのは母集団のみ。

#### FR6: Step C 実行条件の変更

**説明**: `verify.status` が `failed` のままでも Step C（完了処理）に到達でき、`git worktree remove` による worktree 掃除と終了報告が行われるよう、Step C の実行条件「全 step completed — design のみ skipped 可 — 時のみ」を変更する。この実行条件は見出し文字列そのものに埋め込まれているため、見出しの書き換えを伴う。

**ステータス**: resolved

#### FR7: Step B 停止条件との整合

**説明**: `failed` のまま retrospect / Step C へ進む走行が、Step B の停止条件 1（全 step が `completed` でないとターンを終われない）と停止条件 3（ある step の status が `failed` なら停止）に捕まらないようにする。

**ステータス**: **tbd**

**TBD 理由**: 整合の実現方法が未決定 — (a) 停止条件 3 の既存 carve-out を `failed` まで拡張して網羅的列挙を 2 遷移から 3 遷移へ更新する、(b) 既存 carve-out に触れず batch 専用の独立条項を新設する、(c) `failed` とは別の status を導入する（ただし受け入れ条件「`verify.status` は `failed` のまま」に反する）、のいずれか。既存 carve-out は「フェーズプロトコルが自動再エントリのために設定した `needs_update`」限定で、対象遷移を「厳密に次の 2 つ」と網羅的に宣言しており、tests/test_develop_skill_rewiring.py の TestStopCondition3AutomaticReentryCarveOut がその網羅性宣言と 2 遷移の所有ドキュメントを固定している。選ぶ選択肢によって変更対象テストが変わる。batch policy create-spec.requirement-clarification の codex_consultation が Codex CLI の usage limit により実行不能で、unresolved: record_tbd が適用された。なお本 FR が未解決のままだと FR3 と FR6 は実効しない（Step C の実行条件だけを直しても Step B が retrospect の手前で停止する）。

#### FR8: workflow-schema.md の batch ブロック構造

**説明**: `references/workflow-schema.md` の `batch` ブロックを、系譜判定に必要な履歴を持てる構造に更新する: `review_rework_count`（据え置き）に加え `verify_rework: {rounds, failed_id_counts}`。ブロックの説明コメント（現行「Rework counters ONLY」）も、履歴を保持する構造に合わせて更新する。

**ステータス**: resolved

#### FR9: interactive の Step C デフォルト条件付き変更

**説明**: interactive の Step C 三択（マージ / ブランチを残す / PR を作成）は維持する。`verify.status` が `failed` のときのみ推奨デフォルトを「ブランチを残す」へ切り替え、質問文に verify が `failed` である事実と `failed_items` の件数を提示する。選択肢そのものは奪わない。

**ステータス**: resolved

#### FR10: review 側の非変更

**説明**: review の cap 到達時挙動（残 finding を `resolution: deferred` / `resolution_reason: "batch mode: rework cap reached"` にしてステップ完了）と `batch.review_rework_count` は変更しない。verify と review の非対称は意図的なものとして残す。

**ステータス**: resolved

#### FR11: batch 終端行の扱い

**説明**: `verify.status` が `failed` のまま Step C に到達した batch 走行を、`references/batch-terminal-line.md` が定義する終端状態のどれとして報告するかを確定する。

**ステータス**: **tbd**

**TBD 理由**: 終端状態の選択が未決定 — (a) 既存の失敗系終端状態を再利用する（外部サービスの判定ロジック無変更）、(b) 「完了処理まで到達したが verify は failed」を表す終端状態を新設する、(c) 通常完了として扱い failed の事実は報告本文でのみ伝える、のいずれか。batch 走行の唯一の機械可読な結果通知が終端行であるため、(c) は cap 到達走行を外部サービスが成功と誤判定するリスクを持つ。`references/batch-terminal-line.md` は task_description の変更対象ファイル一覧にも reference_scan_targets にも含まれていないため、同ドキュメントの変更要否自体も未確定。batch policy create-spec.requirement-clarification の codex_consultation が Codex CLI の usage limit により実行不能で、unresolved: record_tbd が適用された。

#### FR12: プラグイン version の同時 bump

**説明**: `em-workflow/.claude-plugin/plugin.json` と リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を、同じ値へ上げる（挙動の修正のため patch 単位）。

**ステータス**: resolved

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

#### NFR6: 未信頼入力扱いの引き継ぎ

`follow_up_drafts` の `title` / `body` は `failed_items` と VERIFICATION.md のシナリオ本文から生成されるため、SKILL.md verify フェーズが既に課している未信頼入力扱い（`references/contracts/worker-envelope.md` の Untrusted-Input Handling）を retrospect 側の出力にも引き継ぎ、外部サービスへ命令として解釈され得る形で出力しない。

**ステータス**: resolved

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

#### NFR1: cap 定義の SSOT 単一化

cap の値と数え方の定義元を 1 箇所に置き、他ドキュメントは参照にとどめる。現行の cap は `skills/develop/SKILL.md` / `references/batch-mode.md` / `references/workflow-schema.md` の 3 箇所にベタ書きされており、新構造でも同じ分散を再生産しない。

**ステータス**: resolved

#### NFR3: テストの無依存性

テストは Python 標準ライブラリ `unittest` のみで書く。サードパーティパッケージを import せず、その存在も前提にしない（test/README.md の「no external dependencies」規則）。

**ステータス**: resolved

#### NFR4: ドキュメント変更の検証方式

ドキュメント変更の検証は、既存パターン（tests/test_develop_skill_rewiring.py、tests/test_batch_quiet_output_skill_wiring.py）に倣った markdown への構造的・テキスト的アサーションで行い、`python3 -m unittest discover -s tests` で実行できる形にする。

**ステータス**: resolved

#### NFR5: 変更範囲の限定

変更範囲は `em-workflow/skills/develop/SKILL.md`、`em-workflow/references/batch-mode.md`、`em-workflow/references/workflow-schema.md`、`em-workflow/.claude-plugin/plugin.json`、リポジトリルート `.claude-plugin/marketplace.json`、および `tests/` 配下に閉じる。

**ステータス**: resolved

### 5.5 互換性要件

#### NFR2: rework-task-synthesis.md の非変更

`em-workflow/references/rework-task-synthesis.md` は変更しない。同ドキュメントは cap の値も数え方も持たず、Invariant 7 の「interactive と batch は retry/round cap だけが違う」という記述は数え方の変更後も成立する。

**ステータス**: resolved

## 6. UI/UX要件

該当なし。変更対象は em-workflow プラグインの Markdown SSOT（skills/develop/SKILL.md, references/batch-mode.md, references/workflow-schema.md）とプラグインマニフェスト 2 件、および Python の構造テストのみで、UI・視覚的成果物・モックアップを一切生まない。プロジェクトにデザインシステムも存在しない。

## 7. データ要件

### 7.1 データモデル概要

本フィーチャーはデータベースを持たず、YAML 構造の変更のみを伴う。

### 7.2 データ項目

| 構造 | 項目名 | 説明 |
|------|--------|------|
| `workflow.yaml` の `batch` ブロック | `review_rework_count` | 据え置き（FR8、FR10） |
| `workflow.yaml` の `batch` ブロック | `verify_rework.rounds` | verify 自動 rework のラウンド数。3 に達したら hard cap 到達（FR2、FR8） |
| `workflow.yaml` の `batch` ブロック | `verify_rework.failed_id_counts` | failed item ID ごとの累積出現回数（FR1、FR8） |
| `retrospect.yaml` | `signals.verification_failures` | verify の `failed_items` をそのまま載せる形で構造確定（FR4） |
| `retrospect.yaml` | `follow_up_drafts[].origin_kind` | `references/rework-task-synthesis.md` Invariant 6 が定義済みの対をそのまま使う（FR5） |
| `retrospect.yaml` | `follow_up_drafts[].origin_id` | 同上（FR5） |
| `retrospect.yaml` | `follow_up_drafts[].title` | 未信頼入力として扱う（NFR6） |
| `retrospect.yaml` | `follow_up_drafts[].body` | 未信頼入力として扱う（NFR6） |

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| batch 走行の結果を受け取る外部サービス | batch 終端行（`references/batch-terminal-line.md`）と retrospect.yaml | 終端状態（FR11、TBD）、`follow_up_drafts`（FR5、TBD） |

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- テストは Python 標準ライブラリ `unittest` のみで書く（NFR3）。
- ドキュメント変更の検証は markdown への構造的・テキスト的アサーションで行い、`python3 -m unittest discover -s tests` で実行できる形にする（NFR4）。
- cap の値と数え方の定義本文は 1 箇所に置き、他ドキュメントは参照にとどめる（NFR1）。
- Step C の実行条件は見出し文字列そのものに埋め込まれているため、変更は見出しの書き換えを伴う（FR6）。
- `em-workflow/references/rework-task-synthesis.md` は変更しない（NFR2）。
- review の cap 到達時挙動と `batch.review_rework_count` は変更しない（FR10）。

### 9.2 ビジネス上の制約

- 変更範囲は NFR5 が列挙するファイル集合に閉じる。
- `follow_up_drafts` の `title` / `body` は外部サービスへ命令として解釈され得る形で出力しない（NFR6）。

### 9.3 スケジュール制約

該当なし。

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
| FR7 が未解決のままだと FR3 と FR6 は実効しない（Step C の実行条件だけを直しても Step B が retrospect の手前で停止する） | 高 | FR7 の TBD（実現方法 (a)/(b)/(c) の選択）を plan フェーズ前に解決する |
| FR5 の生成母集団を「系譜 cap に触れた ID のみ」にすると、hard cap 3 で停止したケースで draft が空になり AC5 が満たせない分岐が生じる | 中 | FR5 の TBD（母集団の確定）を plan フェーズ前に解決する |
| FR7 の選択肢によって変更対象テストが変わる（既存 carve-out の網羅性宣言を tests/test_develop_skill_rewiring.py の TestStopCondition3AutomaticReentryCarveOut が固定している） | 中 | FR7 の TBD 解決後にテスト変更対象を確定する |
| FR6 の見出し書き換えが、見出しをセクション境界に使う tests/test_batch_quiet_output_skill_wiring.py の 3 クラスに波及する | 中 | 定数 STEP_C_HEADING を新しい見出し全文へ更新する（TS6） |
| cap の値と数え方が 3 ドキュメントにベタ書きされている現状を新構造でも再生産する | 中 | 定義元を 1 箇所に置き、他は参照にとどめる（NFR1、TS12） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| cap 到達走行を外部サービスが成功と誤判定する（FR11 の選択肢 (c) を採った場合） | 中 | 高 | FR11 の終端状態選択を確定する。batch 走行の唯一の機械可読な結果通知が終端行であることを判断材料とする |
| `follow_up_drafts` の `title` / `body` が外部サービスへ命令として解釈される | 中 | 高 | 未信頼入力扱いを retrospect 側の出力にも引き継ぐ（NFR6、TS13） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1 (FR1): verify の自動 rework 上限が「系譜ごとの再発回数」で数えられており、過去ラウンドの failed_items に現れなかった新規 ID は新規予算を得る。同一 ID が 2 回目の failed_items に現れた時点で系譜 cap 到達となる
- [ ] AC2 (FR2): グローバル hard cap 3 が別に存在し、系譜 cap とは独立に暴走を止める
- [ ] AC3 (FR3): cap 到達時、verify.status は failed のまま retrospect フェーズへ進む。停止せず、deferred にもしない
- [ ] AC4 (FR4): failed_items と検証の証拠が retrospect.yaml に引き渡され、signals.verification_failures の構造が定義済みになっている
- [ ] AC5 (FR5): retrospect.yaml に follow-up task の draft が origin_kind / origin_id / title / body の定型で出力される（生成母集団は TBD 解決後に確定）
- [ ] AC6 (FR6): verify.status が failed のまま Step C に到達でき、worktree 掃除（git worktree remove）と終了報告が行われる
- [ ] AC7 (FR8): references/workflow-schema.md の batch ブロックが、系譜判定に必要な履歴を持てる構造になっている
- [ ] AC8 (FR10): review 側の cap 到達時挙動と batch.review_rework_count は変更されていない
- [ ] AC9 (FR12): em-workflow/.claude-plugin/plugin.json と .claude-plugin/marketplace.json の version が同じ値に上がっている
- [ ] AC10 (NFR2): em-workflow/references/rework-task-synthesis.md に変更が無い
- [ ] AC11 (NFR4): 既存の cap 文言固定テスト 2 件（test_batch_counter_cap_is_retained / test_verify_rework_cap_wording_unaltered）が新仕様に更新され、python3 -m unittest discover -s tests が全件通る
- [ ] AC12 (FR9): interactive の Step C 三択が維持され、verify が failed のときのみ推奨デフォルトが「ブランチを残す」に切り替わり、質問文に failed の事実と failed_items 件数が出る
- [ ] AC13 (FR7) [TBD]: failed のまま進む走行が Step B の停止条件 1 / 停止条件 3 に捕まらないことが仕様に明記されている — 実現方法の決定待ち
- [ ] AC14 (FR11) [TBD]: cap 到達走行の batch 終端状態が確定している — 終端状態の選択待ち

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 対象要件 | 実行方法 | シナリオ |
|----|----------|----------|----------|
| TS1 | FR1 | `python3 -m unittest discover -s tests` | 新規テストが SKILL.md の verify フェーズ節と batch-mode.md の verify.failed 行に対し、系譜カウント（failed_id_counts による ID ごとの累積出現回数）と系譜 cap = 1、および「過去ラウンドの failed_items に現れなかった新規 ID は新規予算を得る」旨が述べられていることを構造的アサーションで確認する。旧文言（batch.verify_rework_count == 0）を含む合成テキストに対して同じ matcher が失敗することを示す負の証明を併せて置く。 |
| TS2 | FR2 | `python3 -m unittest discover -s tests` | hard cap 3 が rounds に対する上限として、系譜 cap とは独立した判定であることが SKILL.md と batch-mode.md の双方に述べられていることをアサートする。 |
| TS3 | FR3 | `python3 -m unittest discover -s tests` | cap 到達時の記述が「verify.status は failed のまま retrospect へ進む」であり、旧文言「`failed` のまま報告して停止」が SKILL.md 全文から消えていること、および verify 側の残項目に deferred を与える記述が存在しないことをアサートする。 |
| TS4 | FR4 | `python3 -m unittest discover -s tests` | SKILL.md の retrospect.yaml スキーマ例で signals.verification_failures が下位構造付き（verify の failed_items をそのまま載せる形）で定義されており、キーのみの状態でなくなっていることをアサートする。 |
| TS5 | FR5 | `python3 -m unittest discover -s tests` | retrospect.yaml スキーマ例に follow_up_drafts が存在し、origin_kind / origin_id / title / body の 4 フィールドを持ち、references/rework-task-synthesis.md Invariant 6 を参照していることをアサートする。生成母集団に関するアサーションは FR5 の TBD 解決後に追加する。 |
| TS6 | FR6 | `python3 -m unittest discover -s tests` | Step C の実行条件が verify の failed を許容する形になっていることをアサートし、かつ tests/test_batch_quiet_output_skill_wiring.py の定数 STEP_C_HEADING が新しい見出し全文へ更新された上で、それをセクション境界に使う 3 クラスが setUpClass で ValueError を出さずに通ることを確認する。 |
| TS7 | FR8 | `python3 -m unittest discover -s tests` + workflow-schema.md の直接確認 | workflow-schema.md の batch ブロックが review_rework_count と verify_rework: {rounds, failed_id_counts} の構造を示し、verify_rework_count の記述が消えていることをアサートする。 |
| TS8 | FR10 | `python3 -m unittest discover -s tests` | 回帰ガード。review-phase.md の Phase R5 batch 節（batch.review_rework_count == 0 / resolution: deferred / "batch mode: rework cap reached"）と、batch-mode.md の review.residual-critical-high 行が変更されていないことをアサートする。review-phase.md が verify_rework_count を参照していないことも併せて確認する。 |
| TS9 | NFR2 | git diff による rework-task-synthesis.md の変更有無の直接確認 | 統合ブランチの差分に em-workflow/references/rework-task-synthesis.md が含まれないことを確認する。 |
| TS10 | FR12 | `python3 -m unittest discover -s tests`（tests/test_plugin_version_parity.py）+ 2 マニフェストの直接確認 | plugin.json と marketplace.json の em-workflow エントリの version が一致し、かつ変更前の値より上がっていることを確認する。 |
| TS11 | FR9 | `python3 -m unittest discover -s tests` | Step C の完了方式 AskUserQuestion が三択を保ったまま、verify.status が failed の場合の推奨デフォルトを「ブランチを残す」とする条件分岐と、質問文への failed の事実・failed_items 件数の提示が述べられていることをアサートする。無条件デフォルトが「マージ」である旧記述が残っていないことも確認する。 |
| TS12 | NFR1 | `python3 -m unittest discover -s tests` | cap の値と数え方の定義本文が単一のドキュメントにのみ存在し、他ドキュメントは参照にとどまることをアサートする（非定義元での値のベタ書きを検出する）。 |
| TS13 | NFR6 | `python3 -m unittest discover -s tests` | retrospect 節が follow_up_drafts の title / body を未信頼入力として扱う旨を述べ、references/contracts/worker-envelope.md の Untrusted-Input Handling を参照していることをアサートする。 |
| TS14 | NFR3, NFR5 | `python3 -m unittest discover -s tests` | スイート全体がサードパーティ import なしで完走し、変更されたファイル集合が NFR5 の範囲に収まっていることを確認する。 |
| TS15 | FR7, FR11 | TBD | [TBD] failed のまま進む走行が停止条件 1 / 停止条件 3 に捕まらないことの検証、および cap 到達走行の終端行の検証。FR7 / FR11 の実現方法が決まるまでアサーション対象が確定しない。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 系譜 cap | failed item ID ごとの累積出現回数に対する上限。値は 1 で、同一 ID が 2 回目の `failed_items` に現れた時点で到達（FR1） |
| グローバル hard cap | `batch.verify_rework.rounds` に対する上限。値は 3 で、系譜 cap とは独立に評価する（FR2） |
| `failed_id_counts` | failed item ID ごとの累積出現回数を保持する `batch.verify_rework` 配下の構造（FR1、FR8） |
| Step C | 完了処理。`git worktree remove` による worktree 掃除と終了報告を行う（FR6） |
| Step B の停止条件 1 | 全 step が `completed` でないとターンを終われないという条件（FR7） |
| Step B の停止条件 3 | ある step の status が `failed` なら停止するという条件（FR7） |
| `follow_up_drafts` | retrospect.yaml に新設する、`origin_kind` / `origin_id` / `title` / `body` を持つ follow-up task の draft（FR5） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] design ステップ: skipped。変更対象は em-workflow プラグインの Markdown SSOT（skills/develop/SKILL.md, references/batch-mode.md, references/workflow-schema.md）とプラグインマニフェスト 2 件、および Python の構造テストのみで、UI・視覚的成果物・モックアップを一切生まない。プロジェクトにデザインシステムも存在しない。
- [x] review 側の非対称: verify と review の cap 到達時挙動の非対称は意図的なものとして残す（FR10）。
- [x] `origin_kind` / `origin_id` の対: `references/rework-task-synthesis.md` Invariant 6 が定義済みのものをそのまま使い、再定義しない（FR5）。

#### 前提事項

要件分析が確定した前提。いずれも要件の一部として扱う。

| ID | 前提 | 根拠 | 影響度 | 可逆 |
|----|------|------|--------|------|
| a1 | 系譜カウントは batch モードのみに適用し、interactive の verify 失敗時三択（implement へ rework / review へ / 中断）は現状のまま。 | 確定構造が batch: ブロック配下に置かれ、制約・前提が interactive については Step C デフォルトの変更のみを挙げているため。 | 中 | 可 |
| a2 | failed_id_counts は verify ラウンドごとに、そのラウンドの failed_items に現れた全 ID について +1 する（1 回目のラウンドも含む）。 | task_description の適用例が「1 回目 {TS-4} で TS-4=1、2 回目 {TS-10} で TS-10=1」と述べており、1 回目からカウントされることを示すため。 | 高 | 可 |
| a3 | em-workflow/references/rework-task-synthesis.md は変更しない。 | task_description の調査結果として明示的に確定済み（Invariant 7 の文言は数え方の変更後も成立する）。 | 低 | 可 |

### 14.2 未確認・保留事項

- [ ] FR5: follow_up_drafts の新設 — draft の生成母集団が未決定（「cap 到達時点で未解決の `failed_items` 全件」か「系譜 cap に触れた ID のみ」か）。後者を採ると hard cap 3 で停止したケースで draft が空になり、AC5 が満たせない分岐が生じる。キー・フィールド構成と Invariant 6 の引用方針は確定済み。
- [ ] FR7: Step B 停止条件との整合 — 実現方法が (a) 既存 carve-out の拡張 / (b) batch 専用の独立条項の新設 / (c) 別 status の導入 のいずれか未決定。選択によって変更対象テストが変わる。未解決のままだと FR3 と FR6 は実効しない。
- [ ] FR11: batch 終端行の扱い — 終端状態の選択が (a) 既存の失敗系終端状態の再利用 / (b) 新設 / (c) 通常完了扱い のいずれか未決定。`references/batch-terminal-line.md` の変更要否自体も未確定。
- [ ] 上記 3 件はいずれも、batch policy create-spec.requirement-clarification の action: codex_consultation が Codex CLI の usage limit により実行不能となり、unresolved: record_tbd が適用された結果として保留されている。

## 15. 参考資料

- `em-workflow/skills/develop/SKILL.md`: verify フェーズ節、retrospect.yaml スキーマ例、Step B の停止条件、Step C
- `em-workflow/references/batch-mode.md`: verify.failed 行、review.residual-critical-high 行
- `em-workflow/references/workflow-schema.md`: `batch` ブロック
- `em-workflow/references/rework-task-synthesis.md`: Invariant 6（`origin_kind` / `origin_id` の対）、Invariant 7（変更しない、NFR2）
- `em-workflow/references/review-phase.md`: Phase R5 batch 節（回帰ガード対象、TS8）
- `em-workflow/references/batch-terminal-line.md`: batch 終端状態の定義（FR11、変更要否は未確定）
- `em-workflow/references/contracts/worker-envelope.md`: Untrusted-Input Handling（NFR6）
- `tests/test_develop_skill_rewiring.py`: TestStopCondition3AutomaticReentryCarveOut（FR7 の変更対象候補）
- `tests/test_batch_quiet_output_skill_wiring.py`: 定数 STEP_C_HEADING（FR6 の波及先）
- `tests/test_plugin_version_parity.py`: version 一致の確認（TS10）
