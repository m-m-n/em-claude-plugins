# Feature: batch-verify-rework-lineage-cap

要件の確定版は `feature-docs/batch-verify-rework-lineage-cap/REQUIREMENTS.md`。本書はその実装向けレンダリングであり、要件の追加・変更は行わない。

## Overview

batch モードの verify 自動 rework 上限を、固定回数（cap 1）から「失敗項目 ID の系譜ごとの再発回数」ベースへ変える。系譜 cap 1 とグローバル hard cap 3 を独立に評価し、cap 到達時も走行を停止させずに `verify.status: failed` のまま retrospect と Step C（完了処理）へ到達させる。未解決の failed_items は retrospect.yaml の `follow_up_drafts` として機械可読な形で引き渡す。

## Objectives

- batch モードの verify 自動 rework 上限を、固定回数（cap 1）から「失敗項目 ID の系譜ごとの再発回数」ベースへ変える。
- 検証カバレッジ強化によって新規に発見された欠陥が、回数上限によって握り潰されない状態にする。
- cap 到達後も走行を停止させず、retrospect と完了処理（Step C）まで到達させ、integration ブランチを宙に浮かせない。
- 未解決の failed_items を機械可読な follow-up draft として retrospect.yaml に引き渡し、外部サービスへの引き継ぎを自動化可能にする。

## User Stories

### US1: 新規欠陥に新規の rework 予算が与えられる

batch 走行の実行者として、検証カバレッジ強化によって新規に発見された欠陥に新規の rework 予算が与えられてほしい。回数上限によって欠陥が握り潰されないようにするため。

**Acceptance Criteria:**
- [ ] AC1 (FR1): verify の自動 rework 上限が「系譜ごとの再発回数」で数えられており、過去ラウンドの failed_items に現れなかった新規 ID は新規予算を得る。同一 ID が 2 回目の failed_items に現れた時点で系譜 cap 到達となる
- [ ] AC2 (FR2): グローバル hard cap 3 が別に存在し、系譜 cap とは独立に暴走を止める
- [ ] AC7 (FR8): references/workflow-schema.md の batch ブロックが、系譜判定に必要な履歴を持てる構造になっている

### US2: cap 到達後も完了処理まで到達する

batch 走行の実行者として、cap 到達後も走行が停止せず完了処理まで到達してほしい。integration ブランチが宙に浮いたまま残らないようにするため。

**Acceptance Criteria:**
- [ ] AC3 (FR3): cap 到達時、verify.status は failed のまま retrospect フェーズへ進む。停止せず、deferred にもしない
- [ ] AC6 (FR6): verify.status が failed のまま Step C に到達でき、worktree 掃除（git worktree remove）と終了報告が行われる
- [ ] AC13 (FR7) [TBD]: failed のまま進む走行が Step B の停止条件 1 / 停止条件 3 に捕まらないことが仕様に明記されている — 実現方法の決定待ち
- [ ] AC14 (FR11) [TBD]: cap 到達走行の batch 終端状態が確定している — 終端状態の選択待ち

### US3: 未解決の失敗項目が機械可読な形で引き継がれる

batch 走行の結果を受け取る外部サービスとして、未解決の failed_items を定型の draft として受け取りたい。follow-up への引き継ぎを自動化するため。

**Acceptance Criteria:**
- [ ] AC4 (FR4): failed_items と検証の証拠が retrospect.yaml に引き渡され、signals.verification_failures の構造が定義済みになっている
- [ ] AC5 (FR5): retrospect.yaml に follow-up task の draft が origin_kind / origin_id / title / body の定型で出力される（生成母集団は TBD 解決後に確定）

### US4: interactive の選択肢は奪われない

interactive 走行の実行者として、Step C の三択を維持したまま、verify が failed のときは推奨デフォルトだけを切り替えてほしい。判断材料を得つつ選択権を保つため。

**Acceptance Criteria:**
- [ ] AC12 (FR9): interactive の Step C 三択が維持され、verify が failed のときのみ推奨デフォルトが「ブランチを残す」に切り替わり、質問文に failed の事実と failed_items 件数が出る
- [ ] AC8 (FR10): review 側の cap 到達時挙動と batch.review_rework_count は変更されていない

## Technical Requirements

### Functional Requirements

- **FR1 — 系譜カウントによる cap 判定 (resolved):** `batch.verify_rework.failed_id_counts` に failed item ID ごとの累積出現回数を保持し、過去ラウンドの `failed_items` に現れなかった新規 ID には新規予算を与える。系譜 cap は 1 とし、同一 ID が 2 回目の `failed_items` に現れた時点で cap 到達とする。
- **FR2 — グローバル hard cap (resolved):** `batch.verify_rework.rounds` が 3 に達したら cap 到達とする。系譜 cap とは独立に評価し、「新しい問題が湧き続ける」ケースの暴走を止める。
- **FR3 — cap 到達時は停止せず retrospect へ (resolved):** cap 到達時、`verify.status` は `failed` のまま retrospect フェーズへ進む。走行を停止しない。残項目を `deferred` にもしない（review の defer が「リスク受容の記録」であるのに対し、verify の defer は「検証の偽装」になるため）。
- **FR4 — retrospect への失敗項目と証拠の引き渡し (resolved):** `failed_items` と検証の証拠（ビルド・フォーマット・非 race 実行等の結果）を retrospect.yaml に引き渡す。現在キーのみで下位構造が未定義の `signals.verification_failures` を、verify の `failed_items` をそのまま載せる形で構造確定させる。
- **FR5 — follow_up_drafts の新設 (tbd):** retrospect.yaml に `follow_up_drafts` を新設し、`origin_kind` / `origin_id` / `title` / `body` を出力する。`origin_kind` / `origin_id` の対は `references/rework-task-synthesis.md` Invariant 6 が定義済みのものをそのまま使い、再定義しない。**TBD 理由**: Open Questions を参照。
- **FR6 — Step C 実行条件の変更 (resolved):** `verify.status` が `failed` のままでも Step C（完了処理）に到達でき、`git worktree remove` による worktree 掃除と終了報告が行われるよう、Step C の実行条件「全 step completed — design のみ skipped 可 — 時のみ」を変更する。この実行条件は見出し文字列そのものに埋め込まれているため、見出しの書き換えを伴う。
- **FR7 — Step B 停止条件との整合 (tbd):** `failed` のまま retrospect / Step C へ進む走行が、Step B の停止条件 1（全 step が `completed` でないとターンを終われない）と停止条件 3（ある step の status が `failed` なら停止）に捕まらないようにする。**TBD 理由**: Open Questions を参照。
- **FR8 — workflow-schema.md の batch ブロック構造 (resolved):** `references/workflow-schema.md` の `batch` ブロックを、系譜判定に必要な履歴を持てる構造に更新する: `review_rework_count`（据え置き）に加え `verify_rework: {rounds, failed_id_counts}`。ブロックの説明コメント（現行「Rework counters ONLY」）も、履歴を保持する構造に合わせて更新する。
- **FR9 — interactive の Step C デフォルト条件付き変更 (resolved):** interactive の Step C 三択（マージ / ブランチを残す / PR を作成）は維持する。`verify.status` が `failed` のときのみ推奨デフォルトを「ブランチを残す」へ切り替え、質問文に verify が `failed` である事実と `failed_items` の件数を提示する。選択肢そのものは奪わない。
- **FR10 — review 側の非変更 (resolved):** review の cap 到達時挙動（残 finding を `resolution: deferred` / `resolution_reason: "batch mode: rework cap reached"` にしてステップ完了）と `batch.review_rework_count` は変更しない。verify と review の非対称は意図的なものとして残す。
- **FR11 — batch 終端行の扱い (tbd):** `verify.status` が `failed` のまま Step C に到達した batch 走行を、`references/batch-terminal-line.md` が定義する終端状態のどれとして報告するかを確定する。**TBD 理由**: Open Questions を参照。
- **FR12 — プラグイン version の同時 bump (resolved):** `em-workflow/.claude-plugin/plugin.json` と リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を、同じ値へ上げる（挙動の修正のため patch 単位）。

### Non-Functional Requirements

- **NFR1 — Maintainability / cap 定義の SSOT 単一化 (resolved):** cap の値と数え方の定義元を 1 箇所に置き、他ドキュメントは参照にとどめる。現行の cap は `skills/develop/SKILL.md` / `references/batch-mode.md` / `references/workflow-schema.md` の 3 箇所にベタ書きされており、新構造でも同じ分散を再生産しない。
- **NFR2 — Compatibility / rework-task-synthesis.md の非変更 (resolved):** `em-workflow/references/rework-task-synthesis.md` は変更しない。同ドキュメントは cap の値も数え方も持たず、Invariant 7 の「interactive と batch は retry/round cap だけが違う」という記述は数え方の変更後も成立する。
- **NFR3 — Testability / テストの無依存性 (resolved):** テストは Python 標準ライブラリ `unittest` のみで書く。サードパーティパッケージを import せず、その存在も前提にしない（test/README.md の「no external dependencies」規則）。
- **NFR4 — Testability / ドキュメント変更の検証方式 (resolved):** ドキュメント変更の検証は、既存パターン（tests/test_develop_skill_rewiring.py、tests/test_batch_quiet_output_skill_wiring.py）に倣った markdown への構造的・テキスト的アサーションで行い、`python3 -m unittest discover -s tests` で実行できる形にする。
- **NFR5 — Scope / 変更範囲の限定 (resolved):** 変更範囲は `em-workflow/skills/develop/SKILL.md`、`em-workflow/references/batch-mode.md`、`em-workflow/references/workflow-schema.md`、`em-workflow/.claude-plugin/plugin.json`、リポジトリルート `.claude-plugin/marketplace.json`、および `tests/` 配下に閉じる。
- **NFR6 — Security / 未信頼入力扱いの引き継ぎ (resolved):** `follow_up_drafts` の `title` / `body` は `failed_items` と VERIFICATION.md のシナリオ本文から生成されるため、SKILL.md verify フェーズが既に課している未信頼入力扱い（`references/contracts/worker-envelope.md` の Untrusted-Input Handling）を retrospect 側の出力にも引き継ぎ、外部サービスへ命令として解釈され得る形で出力しない。

## Implementation Approach

### Architecture

本フィーチャーは実行コードを持たず、em-workflow プラグインの Markdown SSOT、プラグインマニフェスト 2 件、および Python の構造テストのみを変更する。

**変更対象と役割:**

```
em-workflow/skills/develop/SKILL.md        # verify フェーズ節 / retrospect.yaml スキーマ例 /
                                           # Step B の停止条件 / Step C（FR1-FR7, FR9, NFR1, NFR6）
em-workflow/references/batch-mode.md       # verify.failed 行（FR1-FR3, NFR1）
em-workflow/references/workflow-schema.md  # batch ブロック（FR8, NFR1）
em-workflow/.claude-plugin/plugin.json     # version（FR12）
.claude-plugin/marketplace.json            # em-workflow エントリの version（FR12）
tests/                                     # 構造アサーション（NFR3, NFR4）
```

**Component Diagram:**

```
cap 判定（FR1 系譜 cap=1 / FR2 hard cap=3、独立評価）
        ↓ cap 到達
verify.status = failed のまま（FR3）
        ↓ Step B 停止条件 1 / 3 を通過（FR7, TBD）
retrospect（FR4 signals.verification_failures / FR5 follow_up_drafts, TBD）
        ↓
Step C 完了処理（FR6: worktree remove + 終了報告）
        ↓
batch 終端行（FR11, TBD）
```

### Data Flow

```
verify ラウンド → failed_items
      → batch.verify_rework.rounds を更新（FR2）
      → batch.verify_rework.failed_id_counts の各 ID を +1（FR1 / 前提 a2）
      → cap 判定（系譜 cap 1 / hard cap 3 を独立評価）
      → 未到達なら rework へ / 到達なら failed のまま retrospect へ（FR3）
retrospect → signals.verification_failures（FR4） + follow_up_drafts（FR5）
      → Step C（FR6） → batch 終端行（FR11）
```

### API Design

該当なし。本フィーチャーは HTTP API を持たない。

### Database Schema

該当なし。データベースを持たない。変更するのは以下の YAML 構造のみ。

**`workflow.yaml` の `batch` ブロック（FR8）:**

| キー | 内容 |
|------|------|
| `review_rework_count` | 据え置き（FR10） |
| `verify_rework.rounds` | verify 自動 rework のラウンド数。3 で hard cap 到達（FR2） |
| `verify_rework.failed_id_counts` | failed item ID ごとの累積出現回数（FR1） |

ブロックの説明コメント（現行「Rework counters ONLY」）も、履歴を保持する構造に合わせて更新する。`verify_rework_count` の記述は消える。

**`retrospect.yaml`（FR4, FR5）:**

| キー | 内容 |
|------|------|
| `signals.verification_failures` | verify の `failed_items` をそのまま載せる形で構造確定（現行はキーのみ） |
| `follow_up_drafts[].origin_kind` | `references/rework-task-synthesis.md` Invariant 6 が定義済みの対をそのまま使う |
| `follow_up_drafts[].origin_id` | 同上 |
| `follow_up_drafts[].title` | 未信頼入力として扱う（NFR6） |
| `follow_up_drafts[].body` | 未信頼入力として扱う（NFR6） |

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/rework-task-synthesis.md`: Invariant 6（`origin_kind` / `origin_id` の対）を FR5 が参照する。本ドキュメント自体は変更しない（NFR2）。
- `em-workflow/references/review-phase.md`: Phase R5 batch 節。FR10 の回帰ガード対象（変更しない）。
- `em-workflow/references/batch-terminal-line.md`: FR11 の対象。変更要否自体が未確定。
- `em-workflow/references/contracts/worker-envelope.md`: Untrusted-Input Handling（NFR6 の参照先）。
- `tests/test_develop_skill_rewiring.py`: `TestStopCondition3AutomaticReentryCarveOut` が停止条件 3 の carve-out の網羅性宣言を固定している（FR7 の変更対象候補）。
- `tests/test_batch_quiet_output_skill_wiring.py`: 定数 `STEP_C_HEADING` をセクション境界に使う 3 クラスがある（FR6 の波及先）。
- `tests/test_plugin_version_parity.py`: version 一致の確認（FR12）。

**External Dependencies:**
- Python 標準ライブラリ `unittest` のみ。サードパーティパッケージは import せず、その存在も前提にしない（NFR3）。

### File Structure

```
em-workflow/
├── skills/develop/SKILL.md
├── references/
│   ├── batch-mode.md
│   └── workflow-schema.md
└── .claude-plugin/plugin.json
.claude-plugin/marketplace.json
tests/
├── test_develop_skill_rewiring.py
├── test_batch_quiet_output_skill_wiring.py
└── test_plugin_version_parity.py
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

実行方法はいずれも `python3 -m unittest discover -s tests`（NFR4）。

- [ ] TS1 (FR1): 新規テストが SKILL.md の verify フェーズ節と batch-mode.md の verify.failed 行に対し、系譜カウント（failed_id_counts による ID ごとの累積出現回数）と系譜 cap = 1、および「過去ラウンドの failed_items に現れなかった新規 ID は新規予算を得る」旨が述べられていることを構造的アサーションで確認する。旧文言（batch.verify_rework_count == 0）を含む合成テキストに対して同じ matcher が失敗することを示す負の証明を併せて置く。
- [ ] TS2 (FR2): hard cap 3 が rounds に対する上限として、系譜 cap とは独立した判定であることが SKILL.md と batch-mode.md の双方に述べられていることをアサートする。
- [ ] TS3 (FR3): cap 到達時の記述が「verify.status は failed のまま retrospect へ進む」であり、旧文言「`failed` のまま報告して停止」が SKILL.md 全文から消えていること、および verify 側の残項目に deferred を与える記述が存在しないことをアサートする。
- [ ] TS4 (FR4): SKILL.md の retrospect.yaml スキーマ例で signals.verification_failures が下位構造付き（verify の failed_items をそのまま載せる形）で定義されており、キーのみの状態でなくなっていることをアサートする。
- [ ] TS5 (FR5): retrospect.yaml スキーマ例に follow_up_drafts が存在し、origin_kind / origin_id / title / body の 4 フィールドを持ち、references/rework-task-synthesis.md Invariant 6 を参照していることをアサートする。生成母集団に関するアサーションは FR5 の TBD 解決後に追加する。
- [ ] TS6 (FR6): Step C の実行条件が verify の failed を許容する形になっていることをアサートし、かつ tests/test_batch_quiet_output_skill_wiring.py の定数 STEP_C_HEADING が新しい見出し全文へ更新された上で、それをセクション境界に使う 3 クラスが setUpClass で ValueError を出さずに通ることを確認する。
- [ ] TS11 (FR9): Step C の完了方式 AskUserQuestion が三択を保ったまま、verify.status が failed の場合の推奨デフォルトを「ブランチを残す」とする条件分岐と、質問文への failed の事実・failed_items 件数の提示が述べられていることをアサートする。無条件デフォルトが「マージ」である旧記述が残っていないことも確認する。
- [ ] TS12 (NFR1): cap の値と数え方の定義本文が単一のドキュメントにのみ存在し、他ドキュメントは参照にとどまることをアサートする（非定義元での値のベタ書きを検出する）。
- [ ] TS13 (NFR6): retrospect 節が follow_up_drafts の title / body を未信頼入力として扱う旨を述べ、references/contracts/worker-envelope.md の Untrusted-Input Handling を参照していることをアサートする。

### Integration Tests

- [ ] TS7 (FR8): workflow-schema.md の batch ブロックが review_rework_count と verify_rework: {rounds, failed_id_counts} の構造を示し、verify_rework_count の記述が消えていることをアサートする。実行方法: `python3 -m unittest discover -s tests` + workflow-schema.md の直接確認。
- [ ] TS8 (FR10): 回帰ガード。review-phase.md の Phase R5 batch 節（batch.review_rework_count == 0 / resolution: deferred / "batch mode: rework cap reached"）と、batch-mode.md の review.residual-critical-high 行が変更されていないことをアサートする。review-phase.md が verify_rework_count を参照していないことも併せて確認する。実行方法: `python3 -m unittest discover -s tests`。
- [ ] TS9 (NFR2): 統合ブランチの差分に em-workflow/references/rework-task-synthesis.md が含まれないことを確認する。実行方法: git diff による rework-task-synthesis.md の変更有無の直接確認。
- [ ] TS10 (FR12): plugin.json と marketplace.json の em-workflow エントリの version が一致し、かつ変更前の値より上がっていることを確認する。実行方法: `python3 -m unittest discover -s tests`（tests/test_plugin_version_parity.py）+ 2 マニフェストの直接確認。
- [ ] TS14 (NFR3, NFR5): スイート全体がサードパーティ import なしで完走し、変更されたファイル集合が NFR5 の範囲に収まっていることを確認する。実行方法: `python3 -m unittest discover -s tests`。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS15 (FR7, FR11) [TBD]: failed のまま進む走行が停止条件 1 / 停止条件 3 に捕まらないことの検証、および cap 到達走行の終端行の検証。FR7 / FR11 の実現方法が決まるまでアサーション対象が確定しない。実行方法: TBD。
- [ ] 毎ラウンド新規 ID が現れ、系譜 cap に触れた ID が 1 つも無いまま hard cap 3 で停止するケース（FR5 の生成母集団の選択に依存 — Open Questions 参照）。

### Performance Tests

該当なし。

## Security Considerations

- **Input Validation / Untrusted Input:** `follow_up_drafts` の `title` / `body` は `failed_items` と VERIFICATION.md のシナリオ本文から生成されるため、SKILL.md verify フェーズが既に課している未信頼入力扱い（`references/contracts/worker-envelope.md` の Untrusted-Input Handling）を retrospect 側の出力にも引き継ぐ。外部サービスへ命令として解釈され得る形で出力しない（NFR6）。
- **Authentication / Authorization / Data Protection / XSS / SQL Injection / CSRF:** 該当なし。

## Error Handling

該当なし。本フィーチャーはエラーコード体系を持たない。verify の失敗は `verify.status: failed` と `failed_items` として表現され、cap 到達時の扱いは FR3 / FR6 / FR11 が定める。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested（TBD の FR5 / FR7 / FR11 は解決後）
- [ ] All test scenarios pass（TS1–TS14、TS15 は TBD 解決後）
- [ ] Security requirements are satisfied（NFR6）
- [ ] AC1–AC12 が満たされている
- [ ] AC13 / AC14 が TBD 解決後に満たされている
- [ ] `python3 -m unittest discover -s tests` が全件通る（AC11）
- [ ] 変更されたファイル集合が NFR5 の範囲に収まっている

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- [ ] FR5: follow_up_drafts の新設 - draft の生成母集団が未決定 — 「cap 到達時点で未解決の `failed_items` 全件」か「系譜 cap に触れた ID のみ」か。後者を採ると hard cap 3 で停止したケース（毎ラウンド新規 ID で、系譜 cap に触れた ID が 1 つも無い）で draft が空になり、受け入れ条件「follow-up task の draft が定型出力される」が満たせない分岐が生じる。batch policy create-spec.requirement-clarification の action: codex_consultation が Codex CLI の usage limit により実行不能で、unresolved: record_tbd が適用された。キー・フィールド構成（origin_kind / origin_id / title / body）と Invariant 6 の引用方針は確定済みで、未確定なのは母集団のみ。
- [ ] FR7: Step B 停止条件との整合 - 整合の実現方法が未決定 — (a) 停止条件 3 の既存 carve-out を `failed` まで拡張して網羅的列挙を 2 遷移から 3 遷移へ更新する、(b) 既存 carve-out に触れず batch 専用の独立条項を新設する、(c) `failed` とは別の status を導入する（ただし受け入れ条件「`verify.status` は `failed` のまま」に反する）、のいずれか。既存 carve-out は「フェーズプロトコルが自動再エントリのために設定した `needs_update`」限定で、対象遷移を「厳密に次の 2 つ」と網羅的に宣言しており、tests/test_develop_skill_rewiring.py の TestStopCondition3AutomaticReentryCarveOut がその網羅性宣言と 2 遷移の所有ドキュメントを固定している。選ぶ選択肢によって変更対象テストが変わる。batch policy create-spec.requirement-clarification の codex_consultation が Codex CLI の usage limit により実行不能で、unresolved: record_tbd が適用された。なお本 FR が未解決のままだと FR3 と FR6 は実効しない（Step C の実行条件だけを直しても Step B が retrospect の手前で停止する）。
- [ ] FR11: batch 終端行の扱い - 終端状態の選択が未決定 — (a) 既存の失敗系終端状態を再利用する（外部サービスの判定ロジック無変更）、(b) 「完了処理まで到達したが verify は failed」を表す終端状態を新設する、(c) 通常完了として扱い failed の事実は報告本文でのみ伝える、のいずれか。batch 走行の唯一の機械可読な結果通知が終端行であるため、(c) は cap 到達走行を外部サービスが成功と誤判定するリスクを持つ。`references/batch-terminal-line.md` は task_description の変更対象ファイル一覧にも reference_scan_targets にも含まれていないため、同ドキュメントの変更要否自体も未確定。batch policy create-spec.requirement-clarification の codex_consultation が Codex CLI の usage limit により実行不能で、unresolved: record_tbd が適用された。

### Assumptions

要件分析が確定した前提。

| ID | 前提 | 根拠 | 影響度 | 可逆 |
|----|------|------|--------|------|
| a1 | 系譜カウントは batch モードのみに適用し、interactive の verify 失敗時三択（implement へ rework / review へ / 中断）は現状のまま。 | 確定構造が batch: ブロック配下に置かれ、制約・前提が interactive については Step C デフォルトの変更のみを挙げているため。 | medium | true |
| a2 | failed_id_counts は verify ラウンドごとに、そのラウンドの failed_items に現れた全 ID について +1 する（1 回目のラウンドも含む）。 | task_description の適用例が「1 回目 {TS-4} で TS-4=1、2 回目 {TS-10} で TS-10=1」と述べており、1 回目からカウントされることを示すため。 | high | true |
| a3 | em-workflow/references/rework-task-synthesis.md は変更しない。 | task_description の調査結果として明示的に確定済み（Invariant 7 の文言は数え方の変更後も成立する）。 | low | true |

## Implementation Phases (if applicable)

該当なし。フェーズ分割は create-plan で `workflow.yaml` のタスクとして決まる。

## References

- 要件定義書: `feature-docs/batch-verify-rework-lineage-cap/REQUIREMENTS.md`
- `em-workflow/skills/develop/SKILL.md`
- `em-workflow/references/batch-mode.md`
- `em-workflow/references/workflow-schema.md`
- `em-workflow/references/rework-task-synthesis.md`（Invariant 6 / Invariant 7、変更しない）
- `em-workflow/references/review-phase.md`（Phase R5 batch 節、変更しない）
- `em-workflow/references/batch-terminal-line.md`（FR11、変更要否は未確定）
- `em-workflow/references/contracts/worker-envelope.md`（Untrusted-Input Handling）
- `em-workflow/.claude-plugin/plugin.json` / `.claude-plugin/marketplace.json`
- `tests/test_develop_skill_rewiring.py` / `tests/test_batch_quiet_output_skill_wiring.py` / `tests/test_plugin_version_parity.py`
