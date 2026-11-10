---
title: "muse-guard-deny-recovery"
created_date: 2026-11-10
status: draft
---

# muse-guard-deny-recovery - 要件定義書

## 1. 概要

### 1.1 背景
muse_guard が contributor tier（`muse-spark-contributor`）の呼び出しを deny したとき、レビュープロトコルに次の手順が定義されていない。フックがエージェントに返す deny 文言（DENY_CONTEXT）は、contributor でない `muse-spark` エントリか、チェーンの別エントリで続けるよう指示している。

### 1.2 目的
- muse_guard が contributor tier の呼び出しを deny したとき、レビューが止まらず、レビュープロトコルが定める復帰経路に沿って進む。
- フックがエージェントに返す deny 文言（DENY_CONTEXT）の指示が、その復帰経路と一致する。

### 1.3 スコープ
- em-workflow / em-review の `references/review-protocol.md`（Skip Semantics）
- em-workflow / em-review の `references/review-phase.md`（Phase R2b）
- em-workflow / em-review の `hooks/muse_guard.py`（DENY_CONTEXT）
- em-workflow の README（R2b のホップの段落）
- `tests/` 配下の関連テスト

## 2. ビジネス要件

### 2.1 ビジネス目標
- muse_guard が contributor tier（`muse-spark-contributor`）の呼び出しを deny したとき、レビューは次の手順が無いまま止まらず、レビュープロトコルが定める復帰経路に沿って進む。
- フックがエージェントに返す deny 文言（DENY_CONTEXT）の内容が、その経路と一致する。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| レビュアー | contributor tier の呼び出しを muse_guard に deny されるサブエージェント |
| オーケストレーター | レビュアーが返したスキップオブジェクトを Phase R2b で振り分ける |
| レビュアー以外のエージェント | contributor tier の呼び出しを deny される、レビュー以外の作業中のエージェント |

### 2.3 期待される効果
- contributor tier の deny 後も、レビューがチェーンの次エントリで続く。
- DENY_CONTEXT の指示とレビュープロトコルの手順が食い違わない。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | レビュアーが contributor tier を deny され、チェーンの次エントリへ進む | レビュアー、オーケストレーター | 高 |
| UC02 | レビュアー以外のエージェントが contributor tier を deny される | レビュアー以外のエージェント | 高 |

### 3.2 ユースケース詳細

#### UC01: レビュアーが contributor tier を deny され、チェーンの次エントリへ進む

**アクター**: レビュアー、オーケストレーター

**事前条件**:
- リポジトリに contributor tier の同意が記録されていない。
- レビュアーが contributor tier（`muse-spark-contributor`）を呼び出す。

**基本フロー**:
1. muse_guard が呼び出しを deny し、DENY_CONTEXT を返す。
2. レビュアーは skip_reason `contributor_consent_missing` のスキップオブジェクトを返して終了する。
3. オーケストレーターは Phase R2b の表に従い、記録済みのチェーン位置の次のエントリへ進む。

**代替フロー**:
- 後続エントリも `muse-spark` の場合、Phase R0 の `contributor_consented` を判定し直さないため、そのエントリも contributor tier として読まれる。再び deny されたら、既存の 2 ホップの予算の範囲で再び次へ進む。
- チェーンが尽きたら、既存の Claude フォールバックに進む。
- 有効なスキップオブジェクトが返らない場合（`is_error`、スキップオブジェクトを伴わない権限拒否、ラッパーが起動しなかった場合）は、ハーネスレベルの経路（Claude フォールバックと workflow-doctor による診断）を取る。

**事後条件**:
- 同じエントリを plain の `muse-spark` として再ディスパッチしていない。
- 同意の記録・再判定、チェーンの編集をしていない。

#### UC02: レビュアー以外のエージェントが contributor tier を deny される

**アクター**: レビュアー以外のエージェント

**事前条件**:
- リポジトリに contributor tier の同意が記録されていない。

**基本フロー**:
1. muse_guard が呼び出しを deny し、DENY_CONTEXT を返す。
2. エージェントは回避策を探さず、contributor tier を使わずに作業を続ける。

**事後条件**:
- エージェントは `muse_guard.py --record` を実行していない。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | em-workflow の Skip Semantics に retryable な skip_reason を追加 | `contributor_consent_missing` を retryable の組に加える | 高 |
| FR2 | em-review の Skip Semantics に retryable な skip_reason を追加 | FR1 と同じ値を em-review にも加える | 高 |
| FR3 | em-workflow の Phase R2b の振り分け行 | R2b の表に 5 行目を足す | 高 |
| FR4 | ハーネスレベルの失敗経路に対する優先順位 | 有効なスキップオブジェクトは R2b の表で振り分ける | 高 |
| FR5 | em-review の Phase R2b の振り分け行 | R2b の表に 4 行目を足す | 高 |
| FR6 | DENY_CONTEXT をプロトコルに合わせて書き換える（レビュアーかどうかで分岐） | 3 節構成のまま指示を書き換える | 高 |
| FR7 | 2 つのコピーを PLUGIN_SLUG 以外バイト単位で同一に保つ | muse_guard.py の 2 コピーを同じに編集する | 高 |
| FR8 | em-workflow の README の R2b ホップ段落 | 列挙があれば新しい値を加える | 中 |
| FR9 | テストの更新 | 旧い件数・文言を固定しているテストを更新する | 高 |

### 4.2 機能詳細

#### FR1: em-workflow の Skip Semantics に retryable な skip_reason を追加

**説明**: `em-workflow/references/review-protocol.md` の Skip Semantics に skip_reason `contributor_consent_missing` を追加する。contributor tier（`muse-spark-contributor`）の呼び出しを muse_guard に deny されたレビュアー向けの箇条を足す。そのレビュアーは次のオブジェクトを返して終了する。

```json
{"findings": [], "summary": "skipped: contributor consent missing", "skipped": true, "skip_reason": "contributor_consent_missing", "source": "<source>"}
```

**ビジネスルール**:
- レビュアーは同じエントリを plain の `muse-spark` として再試行しない。同意を記録・再判定しない。別のモデルやチェーンエントリを自分で選ばない。次のエントリを選ぶのはオーケストレーターの役割。
- retryable の組の文を `` These five `skip_reason` values are the **retryable** set `` にする。文 `walks the perspective's fallback chain on exactly these strings` は残す。
- retryable でない側の文を `` `scratchpad_unavailable`, like every value outside the five above, is NOT retryable `` にする。
- 新しい箇条は `harness_unavailable` の箇条と、retryable の組の文を含む箇条の間に置く。retryable の組の文より後ろに `review_data_too_large` は引き続き現れない。

#### FR2: em-review の Skip Semantics に retryable な skip_reason を追加

**説明**: `em-review/references/review-protocol.md` の Skip Semantics に、FR1 と同じ `contributor_consent_missing` の箇条とスキップオブジェクトを追加する。レビュアーの振る舞いは FR1 と同じ。

**ビジネスルール**:
- retryable の組の文を `` These four `skip_reason` values are the **retryable** set `` にする。
- retryable でない側の文を `These last two are NOT retryable, like every value outside the four above` にする。
- `scratchpad_unavailable` と `review_data_too_large` は、その文の後ろに引き続き並べる。
- 新しい箇条は retryable の組の中、その文を含む箇条の前に置く。

#### FR3: em-workflow の Phase R2b の振り分け行

**説明**: `em-workflow/references/review-phase.md` の Phase R2b の表に 5 行目を足す。

| skip_reason | 状況 | 進み先 |
|---|---|---|
| `contributor_consent_missing` | muse_guard denied the contributor tier because the repository has no recorded consent | the next entry in the chain |

**ビジネスルール**:
- 既存の 4 行はバイト単位で変えない。
- 節の中で次の 3 点を述べる。
    1. 同意はハーネスではなく contributor tier の性質なので、同じハーネスの中でチェーンを進めてよい。
    2. 記録済みのチェーン位置の次のエントリから再開し、同じエントリを plain の `muse-spark` として再ディスパッチしない（ホップ後の読み替え禁止は維持する）。
    3. Phase R0 の `contributor_consented` を判定し直さず、チェーンも編集しない。
- このホップは既存の 2 ホップの予算に数える。チェーンが尽きたら既存の Claude フォールバックを取る。

#### FR4: ハーネスレベルの失敗経路に対する優先順位

**説明**: `em-workflow/references/review-phase.md` に、ハーネスレベルの段落（`A reviewer that fails at the **harness** level never reaches this table: ... a permission denial lands in its output ...`）に対する優先順位を書く。

**ビジネスルール**:
- レビュアーが `contributor_consent_missing` の有効なスキップオブジェクトを返したら、原因がフックの deny であっても、オーケストレーターは R2b の表で振り分ける。
- 有効なスキップオブジェクトが返らない場合（`is_error`、スキップオブジェクトを伴わない権限拒否、ラッパーが起動しなかった場合）は、引き続きハーネスレベルの経路（Claude フォールバックと workflow-doctor による診断）を取る。
- 固定文 `A reviewer that fails at the **harness** level never reaches this table` は一字一句そのまま残す。

#### FR5: em-review の Phase R2b の振り分け行

**説明**: `em-review/references/review-phase.md` の Phase R2b の表に、`contributor_consent_missing` で `the next entry in the chain` へ進む 4 行目を足す。

**ビジネスルール**:
- 既存の 3 行は変えない。
- FR3 と同じ「同意はハーネスではなく tier の性質」の注記と、読み替えしない・判定し直さない・チェーンを編集しない旨を書く。
- em-review にはハーネスレベルの段落が無いため、優先順位の記述は足さない。

#### FR6: DENY_CONTEXT をプロトコルに合わせて書き換える（レビュアーかどうかで分岐）

**説明**: 2 つの `muse_guard.py` の DENY_CONTEXT は、1 行の文字列定数のまま、次の 3 節をこの順に持つ。
1. 代わりにすること。2 通りに分ける。レビュアーとして動いているなら、skip_reason `contributor_consent_missing` のスキップオブジェクトを返して終了する。それ以外なら、回避策を探さず、contributor tier を使わずに作業を続ける。
2. 同意は、ユーザーが対話セッションで `/{PLUGIN_SLUG}:contributor-consent` スキルを実行したときだけ記録される。
3. エージェントは `muse_guard.py --record` を実行して自分で同意してはならない。

**ビジネスルール**:
- 文言に文字列 `muse-spark` と同意スキル名を残す。
- contributor でない `muse-spark` エントリや、チェーンの別エントリで続けるという現在の指示は削除する。
- 埋め込む値は PLUGIN_SLUG だけで、フックの入力からは何も埋め込まない。

#### FR7: 2 つのコピーを PLUGIN_SLUG 以外バイト単位で同一に保つ

**説明**: `em-workflow/hooks/muse_guard.py` と `em-review/hooks/muse_guard.py` を同じように編集する。差分は `PLUGIN_SLUG = "..."` の行だけにする。

#### FR8: em-workflow の README の R2b ホップ段落

**説明**: em-workflow の README で `R2b はスキップ理由が retryable なときだけチェーンを進める` から始まる段落が retryable な値を列挙している場合、`contributor_consent_missing` を次のチェーンエントリへ進む組（`rate_limited` と同じ組）に加える。

**ビジネスルール**:
- 次の固定句は一字一句そのまま残す。
    - `` `budget_exhausted` / `harness_unavailable` / `review_data_too_large` は**別ハーネス**の次エントリへ飛ぶ ``
    - `ホップ数はシャードごとに数える`

#### FR9: テストの更新

**説明**: 旧い件数と文言を固定しているテストを更新する。

**ビジネスルール**:
- `tests/test_codex_reviewer_skip_handling.py`: `EM_WORKFLOW_RETRYABLE` に値を加え、件数の語を `five` にする。`EM_REVIEW_RETRYABLE` に値を加え、件数の語を `four` にする。retryable でない側の文と、件数を偽造する改変（em-workflow では `These five` -> `These four`）もこれに合わせる。
- `tests/test_reviewer_roles_protocol.py`: `SKIP_REASON_STRINGS` と `RETRYABLE_SKIP_REASONS` に値を加え、件数と文の文字列を five にする。
- `tests/test_review_phase_llm_led.py`: 表のリテラルに 5 行目を加え、`| the next entry` の件数を 5 にする。
- `tests/test_review_phase_shard_dispatch.py`: `routing_table_ok` が新しい行を含む 2+5 行を期待するようにし、行数のテストを 5 にする。README のホップの固定は残す。
- `tests/test_muse_guard.py`: additionalContext が `contributor_consent_missing` を含むことの検査を足し、`muse-spark` と `{plugin}:contributor-consent` の検査は残す。
- モジュールが既に偽造文の拒否の型に従っている箇所では、新しい固定ごとに偽造文を拒否する検査を付ける。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- NFR1: フックの判定の振る舞いは変えない。分類、ストアの読み取り、fail-open、`deny` のみ（`ask` や `allow` は返さない）、4 フィールドのペイロードの形。変えるのは DENY_CONTEXT の文言だけで、DENY_REASON は変えない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2: どの plugin.json の `version` も、`.claude-plugin/marketplace.json` の `version` も変えない。SPEC・計画・受け入れ条件に version の変更を書かない。patch はマージ時に Actions が上げる。
- NFR3: em-review/ 配下のどのファイルにも `shard` と `dispatch cap` の語を含めない（`tests/test_codex_reviewer_skip_handling.py` が固定している）。`em-workflow/references/review-protocol.md` に `cross-model reviewer` などの禁止された言い回しを含めない（`tests/test_reviewer_roles_protocol.py` が固定している）。
- NFR4: 既存の R2b の固定句は一字一句そのまま残す。次を含む。
    - `Applies to every perspective whose R2 primary-reviewer dispatch returned`
    - `**At most 2 fallback dispatches per perspective**`
    - `A reviewer that fails at the **harness** level never reaches this table`
    - ``not a candidate for this section's retryable-`skip_reason` table``
    - Contributor tier のディスパッチ前の判定基準の文（`never after a hop has already been spent`）
- NFR5: `python3 -m unittest discover -s tests` が通る。

### 5.5 互換性要件
該当なし

## 6. UI/UX要件

該当なし。UI や見た目に関わる面が無い（変更はフックの文字列定数、プロトコルとリファレンスの markdown、テスト）ため、デザインステップは行わない。

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- `em-workflow/hooks/muse_guard.py` と `em-review/hooks/muse_guard.py` は PLUGIN_SLUG の行だけが異なる（FR7）。
- 既存の固定句を変えない（NFR3、NFR4）。

### 9.2 ビジネス上の制約
- version を手で変えない（NFR2）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/muse-guard-deny-recovery/**`
- `test-docs/muse-guard-deny-recovery/**`

`feature-docs/muse-guard-deny-recovery/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/muse-guard-deny-recovery/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/muse-guard-deny-recovery/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/muse-guard-deny-recovery/` ディレクトリを生成しないが、宣言された `test-docs/muse-guard-deny-recovery/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1）: em-workflow の review-protocol.md が retryable の組の中に `contributor_consent_missing` を挙げ、`` These five `skip_reason` values are the **retryable** set `` と `` `scratchpad_unavailable`, like every value outside the five above, is NOT retryable `` を述べている。
- [ ] AC-2（FR2）: em-review の review-protocol.md が retryable の組の中に `contributor_consent_missing` を挙げ、`` These four `skip_reason` values are the **retryable** set `` と `These last two are NOT retryable, like every value outside the four above` を述べている。
- [ ] AC-3（FR3）: em-workflow の R2b の表がちょうど 5 行で、旧い 4 行はバイト単位で同一、5 行目は `contributor_consent_missing` で `the next entry in the chain` へ進む。節は、同じエントリを plain の muse-spark として読み直さないこと、同意を判定し直さないこと、チェーンを編集しないことを述べている。
- [ ] AC-4（FR4）: em-workflow の review-phase.md が、`contributor_consent_missing` の有効なスキップオブジェクトは R2b の表の経路を取ること、ハーネスレベルの経路は有効なスキップオブジェクトが返らないときだけ適用されることを述べている。固定されたハーネスレベルの文は変わっていない。
- [ ] AC-5（FR5）: em-review の R2b の表がちょうど 4 行で、旧い 3 行は変わらず、新しい行は `the next entry in the chain` へ進む。
- [ ] AC-6（FR6）: contributor tier の呼び出しが deny されたとき、両コピーが出す additionalContext は 1 行で、`contributor_consent_missing`、レビュアーの分岐とレビュアー以外の分岐、`muse-spark`、`/<plugin>:contributor-consent`、`--record` による自己同意の禁止を含む。チェーンの別エントリや contributor でない muse-spark エントリへ切り替える指示を含まない。
- [ ] AC-7（FR7）: 2 つの muse_guard.py は行数が同じで、異なるのはちょうど 1 行、PLUGIN_SLUG の行だけ。
- [ ] AC-8（FR8）: em-workflow の README のホップ段落が固定句を保ち、retryable な値を列挙しているなら、次エントリへ進む組に `contributor_consent_missing` を含む。
- [ ] AC-9（NFR2）: どちらの plugin.json でも marketplace.json でも `version` フィールドが変わっていない。
- [ ] AC-10（FR9、NFR5）: `python3 -m unittest discover -s tests` が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: TS-1 各 muse_guard.py のコピーを、同意の無いリポジトリで `codex exec -m muse-spark-contributor` のペイロードを与えてサブプロセスで実行する。deny、4 フィールドのペイロード、additionalContext の内容を検査する（AC-6）。
- [ ] 正常系: TS-2 既存の TestBothCopiesShape の 1 行差分の検査が引き続き通る（AC-7）。
- [ ] 正常系・異常系: TS-3 `tests/test_codex_reviewer_skip_handling.py` の Skip Semantics の retryable の組の照合を、更新した値の集合と件数の語で行う。旧い件数の語や値の欠けた偽造文は拒否される（AC-1、AC-2）。
- [ ] 正常系: TS-4 `tests/test_reviewer_roles_protocol.py` の skip_reason、retryable の件数、retryable でない側の文の固定を更新したもの（AC-1）。
- [ ] 正常系・異常系: TS-5 `routing_table_ok` はちょうど 5 行の表を受け入れ、4 行の表と旧い行を変えた表を拒否する。`| the next entry` の件数は `tests/test_review_phase_llm_led.py` と `tests/test_review_phase_shard_dispatch.py` の両方で 5（AC-3）。
- [ ] 正常系・異常系: TS-6 優先順位の文と変わらないハーネスレベルの文の固定。優先順位の文を落とした偽造文は拒否される（AC-4）。
- [ ] 正常系: TS-7 `tests/test_review_phase_shard_dispatch.py` の README のホップ段落の固定が引き続き通る（AC-8）。
- [ ] 正常系: TS-8 em-review の R2b の表が新しい行を含む 4 行であることの固定（AC-5）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| contributor tier | `muse-spark-contributor` での呼び出し。リポジトリに同意が記録されていないと muse_guard が deny する |
| スキップオブジェクト | `skipped: true` と `skip_reason` を持つ、レビュアーの返り値 |
| retryable な skip_reason | オーケストレーターがその文字列のときだけ観点のフォールバックチェーンを進める skip_reason の組 |
| DENY_CONTEXT | muse_guard.py が deny 時に additionalContext としてエージェントに返す 1 行の文字列定数 |
| PLUGIN_SLUG | muse_guard.py の 2 コピーで唯一異なる値。DENY_CONTEXT に埋め込む唯一の値 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] deny 後の振り分け（q-deny-routing）: retryable_next_entry。`contributor_consent_missing` は retryable で、チェーンの次エントリへ進む（同じハーネスでもよい）。
- [x] version の扱い（q-version-bump）: leave_to_actions。手で上げない。
- [x] レビュアー以外への DENY_CONTEXT（q-deny-context-non-reviewer）: reviewer_conditional。レビュアーかどうかで 2 通りに分ける。
- [x] デザインステップ（q-design-step）: decide_autonomously。UI が無いため行わない。

### 14.2 未確認・保留事項
なし

### 14.3 前提

- A-1: 振り分け。`contributor_consent_missing` は retryable で、チェーンの次エントリへ進む。同じハーネスでもよい。レビュアーはスキップオブジェクトを返すだけで、次のエントリはオーケストレーターが選ぶ（q-deny-routing = retryable_next_entry）。
- A-2: version は Actions のワークフローに任せる。手で上げず、SPEC・計画・受け入れ条件に version の記述を入れない（q-version-bump = leave_to_actions）。
- A-3: DENY_CONTEXT はレビュアーかどうかで分岐し、2 通りを 1 行に収め、3 節構成を保つ（q-deny-context-non-reviewer = reviewer_conditional）。
- A-4: スキップオブジェクトの summary は `skipped: contributor consent missing`、source は `<source>`（レビュアー自身のハーネス）。既存のスキップオブジェクトの型に従う。
- A-5: 同じチェーンの後続エントリも `muse-spark` なら、Phase R0 の `contributor_consented` を判定し直さないため、それも contributor tier として読まれる。再び deny されたら、既存の 2 ホップの予算の範囲で再び進む。
- A-6: em-workflow と em-review の muse_guard.py は PLUGIN_SLUG の行だけが異なる。`tests/test_muse_guard.py` の TestBothCopiesShape がこれを固定している。

## 15. 参考資料

- `em-workflow/references/review-protocol.md`: Skip Semantics
- `em-review/references/review-protocol.md`: Skip Semantics
- `em-workflow/references/review-phase.md`: Phase R2b
- `em-review/references/review-phase.md`: Phase R2b
- `em-workflow/hooks/muse_guard.py`、`em-review/hooks/muse_guard.py`: DENY_CONTEXT
