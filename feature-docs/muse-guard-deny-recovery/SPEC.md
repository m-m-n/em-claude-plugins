# Feature: muse-guard-deny-recovery

## Overview

muse_guard が contributor tier（`muse-spark-contributor`）の呼び出しを deny したときの復帰経路を、レビュープロトコルに定義する。新しい retryable な skip_reason `contributor_consent_missing` を em-workflow / em-review の Skip Semantics と Phase R2b に加え、2 つの `muse_guard.py` の DENY_CONTEXT をその経路に合わせて書き換える。要件の詳細は `feature-docs/muse-guard-deny-recovery/REQUIREMENTS.md` を参照する。

## Objectives

- muse_guard が contributor tier（`muse-spark-contributor`）の呼び出しを deny したとき、レビューは次の手順が無いまま止まらず、レビュープロトコルが定める復帰経路に沿って進む。
- フックがエージェントに返す deny 文言（DENY_CONTEXT）の内容が、その経路と一致する。

## User Stories

### US1: contributor tier の deny 後もレビューが続く
muse_guard が contributor tier の呼び出しを deny したとき、レビュアーはスキップオブジェクトを返し、オーケストレーターはチェーンの次エントリへ進む。

**Acceptance Criteria:**
- [ ] AC-1（FR1）: em-workflow の review-protocol.md が retryable の組の中に `contributor_consent_missing` を挙げ、`` These five `skip_reason` values are the **retryable** set `` と `` `scratchpad_unavailable`, like every value outside the five above, is NOT retryable `` を述べている。
- [ ] AC-2（FR2）: em-review の review-protocol.md が retryable の組の中に `contributor_consent_missing` を挙げ、`` These four `skip_reason` values are the **retryable** set `` と `These last two are NOT retryable, like every value outside the four above` を述べている。
- [ ] AC-3（FR3）: em-workflow の R2b の表がちょうど 5 行で、旧い 4 行はバイト単位で同一、5 行目は `contributor_consent_missing` で `the next entry in the chain` へ進む。節は、同じエントリを plain の muse-spark として読み直さないこと、同意を判定し直さないこと、チェーンを編集しないことを述べている。
- [ ] AC-4（FR4）: em-workflow の review-phase.md が、`contributor_consent_missing` の有効なスキップオブジェクトは R2b の表の経路を取ること、ハーネスレベルの経路は有効なスキップオブジェクトが返らないときだけ適用されることを述べている。固定されたハーネスレベルの文は変わっていない。
- [ ] AC-5（FR5）: em-review の R2b の表がちょうど 4 行で、旧い 3 行は変わらず、新しい行は `the next entry in the chain` へ進む。
- [ ] AC-8（FR8）: em-workflow の README のホップ段落が固定句を保ち、retryable な値を列挙しているなら、次エントリへ進む組に `contributor_consent_missing` を含む。

### US2: DENY_CONTEXT の指示がプロトコルと一致する
deny されたエージェントが受け取る DENY_CONTEXT は、レビュアーならスキップオブジェクトを返して終了し、それ以外なら contributor tier を使わずに続けるよう指示する。

**Acceptance Criteria:**
- [ ] AC-6（FR6）: contributor tier の呼び出しが deny されたとき、両コピーが出す additionalContext は 1 行で、`contributor_consent_missing`、レビュアーの分岐とレビュアー以外の分岐、`muse-spark`、`/<plugin>:contributor-consent`、`--record` による自己同意の禁止を含む。チェーンの別エントリや contributor でない muse-spark エントリへ切り替える指示を含まない。
- [ ] AC-7（FR7）: 2 つの muse_guard.py は行数が同じで、異なるのはちょうど 1 行、PLUGIN_SLUG の行だけ。

## Technical Requirements

### Functional Requirements
- **FR1:** em-workflow の Skip Semantics に retryable な skip_reason を追加する。`em-workflow/references/review-protocol.md` の Skip Semantics に skip_reason `contributor_consent_missing` を加え、contributor tier（`muse-spark-contributor`）の呼び出しを muse_guard に deny されたレビュアー向けの箇条を足す。そのレビュアーは次のオブジェクトを返して終了する。
  ```json
  {"findings": [], "summary": "skipped: contributor consent missing", "skipped": true, "skip_reason": "contributor_consent_missing", "source": "<source>"}
  ```
  レビュアーは同じエントリを plain の `muse-spark` として再試行せず、同意を記録・再判定せず、別のモデルやチェーンエントリを自分で選ばない。次のエントリを選ぶのはオーケストレーターの役割。retryable の組の文を `` These five `skip_reason` values are the **retryable** set `` にし、文 `walks the perspective's fallback chain on exactly these strings` は残す。retryable でない側の文を `` `scratchpad_unavailable`, like every value outside the five above, is NOT retryable `` にする。新しい箇条は `harness_unavailable` の箇条と、retryable の組の文を含む箇条の間に置く。retryable の組の文より後ろに `review_data_too_large` は引き続き現れない。
- **FR2:** em-review の Skip Semantics に retryable な skip_reason を追加する。`em-review/references/review-protocol.md` の Skip Semantics に、FR1 と同じ `contributor_consent_missing` の箇条とスキップオブジェクトを加える。レビュアーの振る舞いは FR1 と同じ。retryable の組の文を `` These four `skip_reason` values are the **retryable** set `` にし、retryable でない側の文を `These last two are NOT retryable, like every value outside the four above` にする。`scratchpad_unavailable` と `review_data_too_large` はその文の後ろに引き続き並べる。新しい箇条は retryable の組の中、その文を含む箇条の前に置く。
- **FR3:** em-workflow の Phase R2b の振り分け行。`em-workflow/references/review-phase.md` の Phase R2b の表に 5 行目 `contributor_consent_missing` | muse_guard denied the contributor tier because the repository has no recorded consent | the next entry in the chain を足す。既存の 4 行はバイト単位で変えない。節の中で次の 3 点を述べる。(1) 同意はハーネスではなく contributor tier の性質なので、同じハーネスの中でチェーンを進めてよい。(2) 記録済みのチェーン位置の次のエントリから再開し、同じエントリを plain の `muse-spark` として再ディスパッチしない（ホップ後の読み替え禁止は維持する）。(3) Phase R0 の `contributor_consented` を判定し直さず、チェーンも編集しない。このホップは既存の 2 ホップの予算に数え、チェーンが尽きたら既存の Claude フォールバックを取る。
- **FR4:** ハーネスレベルの失敗経路に対する優先順位。`em-workflow/references/review-phase.md` に、ハーネスレベルの段落（`A reviewer that fails at the **harness** level never reaches this table: ... a permission denial lands in its output ...`）に対する優先順位を書く。レビュアーが `contributor_consent_missing` の有効なスキップオブジェクトを返したら、原因がフックの deny であっても、オーケストレーターは R2b の表で振り分ける。有効なスキップオブジェクトが返らない場合（`is_error`、スキップオブジェクトを伴わない権限拒否、ラッパーが起動しなかった場合）は、引き続きハーネスレベルの経路（Claude フォールバックと workflow-doctor による診断）を取る。固定文 `A reviewer that fails at the **harness** level never reaches this table` は一字一句そのまま残す。
- **FR5:** em-review の Phase R2b の振り分け行。`em-review/references/review-phase.md` の Phase R2b の表に、`contributor_consent_missing` で `the next entry in the chain` へ進む 4 行目を足す。既存の 3 行は変えない。FR3 と同じ「同意はハーネスではなく tier の性質」の注記と、読み替えしない・判定し直さない・チェーンを編集しない旨を書く。em-review にはハーネスレベルの段落が無いため、優先順位の記述は足さない。
- **FR6:** DENY_CONTEXT をプロトコルに合わせて書き換える（レビュアーかどうかで分岐）。2 つの `muse_guard.py` の DENY_CONTEXT は 1 行の文字列定数のまま、次の 3 節をこの順に持つ。(1) 代わりにすること。2 通りに分ける。レビュアーとして動いているなら、skip_reason `contributor_consent_missing` のスキップオブジェクトを返して終了する。それ以外なら、回避策を探さず、contributor tier を使わずに作業を続ける。(2) 同意は、ユーザーが対話セッションで `/{PLUGIN_SLUG}:contributor-consent` スキルを実行したときだけ記録される。(3) エージェントは `muse_guard.py --record` を実行して自分で同意してはならない。文言に文字列 `muse-spark` と同意スキル名を残す。contributor でない `muse-spark` エントリやチェーンの別エントリで続けるという現在の指示は削除する。埋め込む値は PLUGIN_SLUG だけで、フックの入力からは何も埋め込まない。
- **FR7:** 2 つのコピーを PLUGIN_SLUG 以外バイト単位で同一に保つ。`em-workflow/hooks/muse_guard.py` と `em-review/hooks/muse_guard.py` を同じように編集し、差分は `PLUGIN_SLUG = "..."` の行だけにする。
- **FR8:** em-workflow の README の R2b ホップ段落。em-workflow の README で `R2b はスキップ理由が retryable なときだけチェーンを進める` から始まる段落が retryable な値を列挙している場合、`contributor_consent_missing` を次のチェーンエントリへ進む組（`rate_limited` と同じ組）に加える。固定句 `` `budget_exhausted` / `harness_unavailable` / `review_data_too_large` は**別ハーネス**の次エントリへ飛ぶ `` と `ホップ数はシャードごとに数える` は一字一句そのまま残す。
- **FR9:** テストの更新。旧い件数と文言を固定しているテストを更新する。
  - `tests/test_codex_reviewer_skip_handling.py`: `EM_WORKFLOW_RETRYABLE` に値を加え、件数の語を `five` にする。`EM_REVIEW_RETRYABLE` に値を加え、件数の語を `four` にする。retryable でない側の文と、件数を偽造する改変（em-workflow では `These five` -> `These four`）もこれに合わせる。
  - `tests/test_reviewer_roles_protocol.py`: `SKIP_REASON_STRINGS` と `RETRYABLE_SKIP_REASONS` に値を加え、件数と文の文字列を five にする。
  - `tests/test_review_phase_llm_led.py`: 表のリテラルに 5 行目を加え、`| the next entry` の件数を 5 にする。
  - `tests/test_review_phase_shard_dispatch.py`: `routing_table_ok` が新しい行を含む 2+5 行を期待するようにし、行数のテストを 5 にする。README のホップの固定は残す。
  - `tests/test_muse_guard.py`: additionalContext が `contributor_consent_missing` を含むことの検査を足し、`muse-spark` と `{plugin}:contributor-consent` の検査は残す。
  - モジュールが既に偽造文の拒否の型に従っている箇所では、新しい固定ごとに偽造文を拒否する検査を付ける。

### Non-Functional Requirements
- **NFR1 - フックの判定の振る舞い:** フックの判定の振る舞いは変えない。分類、ストアの読み取り、fail-open、`deny` のみ（`ask` や `allow` は返さない）、4 フィールドのペイロードの形。変えるのは DENY_CONTEXT の文言だけで、DENY_REASON は変えない。
- **NFR2 - version:** どの plugin.json の `version` も、`.claude-plugin/marketplace.json` の `version` も変えない。SPEC・計画・受け入れ条件に version の変更を書かない。patch はマージ時に Actions が上げる。
- **NFR3 - 禁止語:** em-review/ 配下のどのファイルにも `shard` と `dispatch cap` の語を含めない（`tests/test_codex_reviewer_skip_handling.py` が固定している）。`em-workflow/references/review-protocol.md` に `cross-model reviewer` などの禁止された言い回しを含めない（`tests/test_reviewer_roles_protocol.py` が固定している）。
- **NFR4 - 既存の R2b の固定句:** 既存の R2b の固定句は一字一句そのまま残す。`Applies to every perspective whose R2 primary-reviewer dispatch returned`、`**At most 2 fallback dispatches per perspective**`、`A reviewer that fails at the **harness** level never reaches this table`、``not a candidate for this section's retryable-`skip_reason` table``、Contributor tier のディスパッチ前の判定基準の文（`never after a hop has already been spent`）を含む。
- **NFR5 - テスト:** `python3 -m unittest discover -s tests` が通る。

## Implementation Approach

### Architecture

**System Architecture:**
```
レビュアー ──(codex exec -m muse-spark-contributor)──> muse_guard.py (PreToolUse)
   ^                                                      │ deny + DENY_CONTEXT
   └──────────────────────────────────────────────────────┘
レビュアー ──(skip_reason: contributor_consent_missing のスキップオブジェクト)──> オーケストレーター
オーケストレーター ──(Phase R2b の表)──> チェーンの次エントリ / チェーンが尽きたら Claude フォールバック
```

**Component Diagram:**
```
em-workflow/hooks/muse_guard.py ─┐
em-review/hooks/muse_guard.py  ─┴─ DENY_CONTEXT（PLUGIN_SLUG の行以外同一）

em-workflow/references/review-protocol.md (Skip Semantics) ── em-workflow/references/review-phase.md (Phase R2b)
em-review/references/review-protocol.md   (Skip Semantics) ── em-review/references/review-phase.md   (Phase R2b)
```

### Data Flow

```
deny → レビュアーがスキップオブジェクトを返して終了 → オーケストレーターが R2b の表で振り分け
     → 記録済みのチェーン位置の次のエントリへ（2 ホップの予算に数える）
     → チェーンが尽きたら既存の Claude フォールバック
有効なスキップオブジェクトが返らない → ハーネスレベルの経路（Claude フォールバックと workflow-doctor による診断）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/review-protocol.md` / `em-review/references/review-protocol.md`: Skip Semantics の retryable の組
- `em-workflow/references/review-phase.md` / `em-review/references/review-phase.md`: Phase R2b の振り分け表

**External Dependencies:**
- 該当なし

### File Structure

```
em-workflow/
├── hooks/muse_guard.py                  # DENY_CONTEXT（FR6, FR7）
├── references/review-protocol.md        # Skip Semantics（FR1）
├── references/review-phase.md           # Phase R2b（FR3, FR4）
└── README（R2b のホップ段落）            # FR8
em-review/
├── hooks/muse_guard.py                  # DENY_CONTEXT（FR6, FR7）
├── references/review-protocol.md        # Skip Semantics（FR2）
└── references/review-phase.md           # Phase R2b（FR5）
tests/
├── test_codex_reviewer_skip_handling.py # FR9
├── test_reviewer_roles_protocol.py      # FR9
├── test_review_phase_llm_led.py         # FR9
├── test_review_phase_shard_dispatch.py  # FR9
└── test_muse_guard.py                   # FR9
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/muse-guard-deny-recovery/**`
- `test-docs/muse-guard-deny-recovery/**`

`feature-docs/muse-guard-deny-recovery/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/muse-guard-deny-recovery/**` covers `test-docs/muse-guard-deny-recovery/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/muse-guard-deny-recovery/` directory at all; the declared
`test-docs/muse-guard-deny-recovery/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 各 muse_guard.py のコピーを、同意の無いリポジトリで `codex exec -m muse-spark-contributor` のペイロードを与えてサブプロセスで実行する - deny、4 フィールドのペイロード、additionalContext の内容を検査する（AC-6、FR6）
- [ ] TS-2: 既存の TestBothCopiesShape の 1 行差分の検査 - 引き続き通る（AC-7、FR7）
- [ ] TS-3: `tests/test_codex_reviewer_skip_handling.py` の Skip Semantics の retryable の組の照合を、更新した値の集合と件数の語で行う - 旧い件数の語や値の欠けた偽造文は拒否される（AC-1、AC-2、FR1、FR2）
- [ ] TS-4: `tests/test_reviewer_roles_protocol.py` の skip_reason、retryable の件数、retryable でない側の文の固定を更新したもの - 通る（AC-1、FR1）
- [ ] TS-5: `routing_table_ok` - ちょうど 5 行の表を受け入れ、4 行の表と旧い行を変えた表を拒否する。`| the next entry` の件数は `tests/test_review_phase_llm_led.py` と `tests/test_review_phase_shard_dispatch.py` の両方で 5（AC-3、FR3）
- [ ] TS-6: 優先順位の文と変わらないハーネスレベルの文の固定 - 優先順位の文を落とした偽造文は拒否される（AC-4、FR4）
- [ ] TS-7: `tests/test_review_phase_shard_dispatch.py` の README のホップ段落の固定 - 引き続き通る（AC-8、FR8）
- [ ] TS-8: em-review の R2b の表の固定 - 新しい行を含む 4 行である（AC-5、FR5）

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
該当なし

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 同意は、ユーザーが対話セッションで `/{PLUGIN_SLUG}:contributor-consent` スキルを実行したときだけ記録される。エージェントは `muse_guard.py --record` を実行して自分で同意しない（FR6）。フックは `deny` のみを返し、`ask` や `allow` は返さない（NFR1）。
- **Input Validation:** DENY_CONTEXT に埋め込む値は PLUGIN_SLUG だけで、フックの入力からは何も埋め込まない（FR6）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| `contributor_consent_missing` | muse_guard が contributor tier を deny した（同意の記録が無い） | - | `skipped: contributor consent missing` |

### Error Flow

```
有効なスキップオブジェクト（contributor_consent_missing）→ R2b の表 → チェーンの次エントリ
有効なスキップオブジェクトが無い（is_error / スキップオブジェクトを伴わない権限拒否 / ラッパーが起動しなかった）→ ハーネスレベルの経路
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-9（NFR2）: どちらの plugin.json でも marketplace.json でも `version` フィールドが変わっていない。
- [ ] AC-10（FR9、NFR5）: `python3 -m unittest discover -s tests` が通る。

## Assumptions

- A-1: 振り分け。`contributor_consent_missing` は retryable で、チェーンの次エントリへ進む。同じハーネスでもよい。レビュアーはスキップオブジェクトを返すだけで、次のエントリはオーケストレーターが選ぶ（q-deny-routing = retryable_next_entry）。
- A-2: version は Actions のワークフローに任せる。手で上げず、SPEC・計画・受け入れ条件に version の記述を入れない（q-version-bump = leave_to_actions）。
- A-3: DENY_CONTEXT はレビュアーかどうかで分岐し、2 通りを 1 行に収め、3 節構成を保つ（q-deny-context-non-reviewer = reviewer_conditional）。
- A-4: スキップオブジェクトの summary は `skipped: contributor consent missing`、source は `<source>`（レビュアー自身のハーネス）。既存のスキップオブジェクトの型に従う。
- A-5: 同じチェーンの後続エントリも `muse-spark` なら、Phase R0 の `contributor_consented` を判定し直さないため、それも contributor tier として読まれる。再び deny されたら、既存の 2 ホップの予算の範囲で再び進む。
- A-6: em-workflow と em-review の muse_guard.py は PLUGIN_SLUG の行だけが異なる。`tests/test_muse_guard.py` の TestBothCopiesShape がこれを固定している。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/muse-guard-deny-recovery/REQUIREMENTS.md`
- Skip Semantics: `em-workflow/references/review-protocol.md`、`em-review/references/review-protocol.md`
- Phase R2b: `em-workflow/references/review-phase.md`、`em-review/references/review-phase.md`
