# Feature: review-perspective-model-effort

## Overview

観点ごとの codex レビュアーの model と effort を reviewers.yaml で指定し、その値で codex exec を呼ぶ。要件の詳細は `feature-docs/review-perspective-model-effort/REQUIREMENTS.md` を参照する。

## Objectives

- 観点ごとの codex レビュアーの model と effort を reviewers.yaml で指定し、その値で codex exec を呼ぶ。

## User Stories

該当なし（受け入れ条件は Success Criteria に記載）

## Technical Requirements

### Functional Requirements
- **FR1:** reviewers.yaml の codex エントリに effort を追加 — `em-workflow/references/reviewers.yaml` と `em-review/references/reviewers.yaml` で、codex エントリに任意の effort キーを持たせる。エントリは 1 行のフロー形式 `{harness: codex, model: M, effort: E}` で書く。litellm エントリには effort を付けない。ヘッダーのコメントに次の 2 点を書く: codex エントリの effort はレビュアーにそのまま渡り、ラッパーの `--effort` になること。effort が無いエントリは xhigh で動くこと。
- **FR2:** 観点ごとの model と effort — codex エントリを次の表の値にする。em-review も同じ値にする。ただし em-review には license 観点が無く、comprehensive の chain は空なので、この 2 つは対象外。2 番目のエントリ `{harness: litellm, model: muse-spark}` は変えない。

  | 観点 | model | effort |
  |------|-------|--------|
  | security | gpt-6.2-astra | xhigh |
  | comprehensive | gpt-6.2-astra | high |
  | architecture | gpt-6.2-astra | high |
  | spec | gpt-6.2-sol | xhigh |
  | performance | gpt-6.2-sol | xhigh |
  | license | gpt-6.2-sol | low |

- **FR3:** ラッパーの --effort 引数 — `em-workflow/scripts/run_codex_exec.sh` と `em-review/scripts/run_codex_exec.sh` に `--effort LEVEL` を足す。LEVEL が `^[a-z]+$` に一致すれば、`-c 'model_reasoning_effort="LEVEL"'` として codex exec に渡す。この effort の -c は、launch の argv の中で今の EFFORT_FLAG と同じ位置に 1 つだけ置く。LEVEL が無い場合と、一致しない場合は exit 1 にして、codex を起動しない。`--effort` を 2 回指定したら後の値を使う。usage の行とヘッダーのコメントに `--effort` を書く。
- **FR4:** モードごとの既定値 — `--effort` が無ければ、readonly は今と同じく `-c 'model_reasoning_effort="xhigh"'` を付け、readwrite は何も付けない。`--effort` があれば、readonly では xhigh の代わりに指定した値を付け、readwrite でも指定した値を付ける。
- **FR5:** --litellm との併用（em-workflow のみ） — em-workflow のラッパーでは `--effort` と `--litellm` を併用できる。`--litellm` ルートでも、指定した effort が xhigh の代わりに付く。`-m` と `--litellm` の併用を拒否する規則は今のまま。
- **FR6:** codex-reviewer が effort を渡す — `em-workflow/agents/codex-reviewer.md` と `em-review/agents/codex-reviewer.md` の Step 5 で、オーケストレーターから effort を受け取ったら、`--effort "<effort>"` を `"$PROMPT"` の前に加える。値はそのまま渡す。受け取らなければ `--effort` を付けない。レビュアーが自分で effort を選ぶことはない。Codex が effort を拒否した場合は、今の Step 6 の非 JSON 規則により harness_unavailable でスキップする。専用の判定は足さない。
- **FR7:** オーケストレーターが effort を渡す — 両 review-phase.md の R2 で、codex の dispatch の箇条書きを変える: エントリが `effort: E` を持てば、model と同じく input block に `effort: E` を加え、値をそのまま渡す。許可リストの検査はしない。両 review-protocol.md の Inputs に effort の項目を足す。受け取るのは codex reviewer だけで、エントリが effort を持つときに限る。ラッパーへは `--effort <effort>` としてそのまま渡り、無ければ readonly の xhigh になる。Claude reviewer と litellm reviewer は effort を受け取らない。`em-workflow/references/review-protocol.md` の harness 説明の箇条書き（PROTOCOL_BULLETS_SHA256 の範囲）は変更しない。
- **FR8:** round record に effort を記録 — 両 review-phase.md の record で、effort を渡した codex の run に effort を付ける。対象は em-workflow の R3a の perspectives_dispatched と R5 の perspective_runs（例と注記のコメントを含む）、em-review の該当 record（例と注記のコメントを含む）。litellm の run と、effort を渡していない codex の run には付けない。
- **FR9:** README — `em-workflow/README.md` と `em-review/README.md` のチェーン表で、performance / spec / architecture の順序を codex → litellm muse-spark に直す。表記は各 README の既存の書き方に合わせる。両 README の「reviewers.yaml が渡した model をレビュアーはそのまま -m に流す」の文の後に、codex エントリの effort も同じ経路でラッパーの `--effort` に渡ることを 1 文足す。`tests/test_llm_led_review_user_docs.py` の PINNED_CHAINS も同じ順序に直す。
- **FR10:** security-review-model スキル — `.claude/skills/security-review-model/SKILL.md` を新しい指定方法に合わせる。方針の 11 行目（ほかの観点は model を書かない）と 12 行目（xhigh 固定）、手順 2（xhigh への対応を確かめる）、手順 3（xhigh 固定の確認コマンド）を、reviewers.yaml の codex エントリの effort を使う形に直す。スキルの対象は security 観点のままにする。

### Non-Functional Requirements
- **NFR1 - 互換性:** `--effort` を指定しないラッパーの起動では、launch の argv を今とバイト単位で同じにする（readonly は xhigh の -c が 1 つ、readwrite は無し）。対象は既定ルートと `--litellm` ルートの両方。
- **NFR2 - 入力検証:** effort の値は `^[a-z]+$` に一致した場合だけ TOML 文字列に埋め込む。引用符・バックスラッシュ・空白などを含む値で codex を起動しない。
- **NFR3 - 2 つのラッパーの一致:** em-workflow と em-review のラッパーで、`--effort` の扱い（引数の形、検証、エラー文言、既定値、readwrite での振る舞い）を揃える。
- **NFR4 - テスト:** テストは標準ライブラリだけを使い、本物の codex を呼ばない（PATH に置いた stub を使う）。
- **NFR5 - version:** em-workflow と em-review の version の minor を手で上げる。対象は各プラグインの `.claude-plugin/plugin.json` と、リポジトリルートの `.claude-plugin/marketplace.json` の該当エントリで、同じ値に揃える。
- **NFR6 - 固定値テストの更新:** ハッシュと literal で固定されている既存テストは、各テストの慣例どおり固定値をその場で更新し、Refreshed by のコメントを添える。固定そのものは外さない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
reviewers.yaml の codex エントリ {harness: codex, model: M, effort: E}
  → review-phase.md R2（input block に model と effort を加える）
  → codex-reviewer Step 5（-m M、--effort "E" をラッパーに渡す）
  → run_codex_exec.sh（-c 'model_reasoning_effort="E"' を付けて codex exec を起動）
  → round record（effort を渡した codex の run に effort を記録）
```

### Data Flow

```
reviewers.yaml → オーケストレーター（R2） → codex-reviewer（Step 5） → ラッパー（--effort） → codex exec
```

- エントリが effort を持たない場合、オーケストレーターは effort を渡さず、codex-reviewer は `--effort` を付けず、ラッパーは FR4 の既定値で動く。
- Codex が effort を拒否した場合、codex-reviewer は Step 6 の非 JSON 規則により harness_unavailable でスキップする。

### Wrapper argv

| モード | `--effort` | 付ける -c |
|--------|-----------|-----------|
| readonly（既定ルート / `--litellm` ルート） | なし | `-c 'model_reasoning_effort="xhigh"'` を 1 つ |
| readonly（既定ルート / `--litellm` ルート） | `LEVEL` | `-c 'model_reasoning_effort="LEVEL"'` を 1 つ。xhigh は付けない |
| readwrite | なし | 付けない |
| readwrite | `LEVEL` | `-c 'model_reasoning_effort="LEVEL"'` を 1 つ |

- -c の位置は、launch の argv の中で今の EFFORT_FLAG と同じ位置。
- usage は `[-m MODEL]` の直後に `[--effort LEVEL]` を入れる。

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `review-phase.md` R2 / R3a / R5 と em-review の該当 record: effort の受け渡しと記録
- `review-protocol.md` Inputs: effort の入力項目
- `codex-reviewer.md` Step 5 / Step 6: ラッパーへの受け渡しと、拒否時の harness_unavailable

**External Dependencies:**
- codex exec: `-c 'model_reasoning_effort="..."'` を受け取る

### File Structure

```
em-workflow/
├── references/reviewers.yaml       # FR1, FR2
├── references/review-phase.md      # FR7, FR8
├── references/review-protocol.md   # FR7
├── scripts/run_codex_exec.sh       # FR3, FR4, FR5
├── agents/codex-reviewer.md        # FR6
├── README.md                       # FR9
└── .claude-plugin/plugin.json      # NFR5
em-review/
├── references/reviewers.yaml       # FR1, FR2
├── references/review-phase.md      # FR7, FR8
├── references/review-protocol.md   # FR7
├── scripts/run_codex_exec.sh       # FR3, FR4
├── agents/codex-reviewer.md        # FR6
├── README.md                       # FR9
└── .claude-plugin/plugin.json      # NFR5
.claude-plugin/marketplace.json     # NFR5
.claude/skills/security-review-model/SKILL.md   # FR10
tests/                              # TS-1 から TS-12
```

### Version

- em-workflow の version の minor を上げる（`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の該当エントリを同じ値にする）。
- em-review の version の minor を上げる（`em-review/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の該当エントリを同じ値にする）。
- reviewers.yaml の version キー（em-workflow: 3、em-review: 2）は上げない。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/review-perspective-model-effort/**`
- `test-docs/review-perspective-model-effort/**`

`feature-docs/review-perspective-model-effort/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/review-perspective-model-effort/**` covers `test-docs/review-perspective-model-effort/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/review-perspective-model-effort/` directory at all; the declared
`test-docs/review-perspective-model-effort/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: 両プラグインで readonly `--effort high` を指定する - argv に `-c model_reasoning_effort="high"` が隣接して 1 つだけあり、xhigh の -c は無い。対象: `tests/test_codex_wrapper_model_flag.py`（FR3, FR4, NFR3, NFR4）
- [ ] TS-2: 両プラグインで readonly / readwrite を `--effort` なしで起動する - readonly は xhigh の -c が 1 つだけある。readwrite は model_reasoning_effort の -c が無い。対象: `tests/test_codex_wrapper_model_flag.py`（FR4, NFR1, NFR4）
- [ ] TS-3: 両プラグインで readwrite `--effort low` を指定する - low の -c が 1 つだけある。対象: `tests/test_codex_wrapper_model_flag.py`（FR3, FR4, NFR3, NFR4）
- [ ] TS-4: em-workflow で readonly `--litellm M --effort low` を指定する - low の -c が 1 つだけあり、xhigh は無い。対象: `tests/test_codex_wrapper_model_flag.py`（FR5, NFR4）
- [ ] TS-5: 両プラグインで `--effort` に値が無い場合と、不正な値（引用符入り、大文字、空白入り、空文字）の場合 - exit 1 で起動記録が無い。対象: `tests/test_codex_wrapper_model_flag.py`（FR3, NFR2, NFR3, NFR4）
- [ ] TS-6: `--effort` と `-m`、`-C`、`--output-schema` を組み合わせる / `--effort` を 2 回指定する - 各フラグが隣接した組のまま残り、prompt が末尾にある。2 回指定すると後の値になる。対象: `tests/test_codex_wrapper_model_flag.py`（FR3, NFR4）

### Integration Tests
- [ ] TS-7: 「security だけが model を持つ」検査を置き換える - 両 reviewers.yaml の codex エントリの model と effort を FR2 の表の literal で固定する。2 つのファイルで同じ観点の値が一致することも検査する。CHAIN_ENTRY 正規表現は effort キーを読めるようにする。対象: `tests/test_codex_wrapper_model_flag.py`（FR1, FR2）
- [ ] TS-8: EXPECTED_CHAINS の codex エントリに model と effort を入れる - test_chain_entries_well_formed は、codex エントリが model と effort を持つ形を検査する。対象: `tests/test_reviewers_primary_chains.py`（FR1, FR2）
- [ ] TS-9: EM_REVIEW_EXPECTED_CHAINS の codex エントリに model と effort を入れる - em-review の codex エントリが FR2 の値を持つ。対象: `tests/test_contributor_tier_criteria.py`（FR2）
- [ ] TS-10: usage の固定文字列を、`--effort` を含む新しい usage に直す - 既定の xhigh の検査はそのまま通る。対象: `tests/test_codex_hook_wrapper_args.py`、`tests/test_codex_wrapper_single_invocation.py`（FR3, NFR6）
- [ ] TS-11: codex-reviewer.md、review-protocol.md Inputs、review-phase.md の変更に合わせて、ハッシュと literal の固定値を更新する - 更新後の固定値でテストが通る。対象: `tests/test_reviewer_roles_protocol.py`、`tests/test_reproduction_reviewer_instructions.py`、`tests/test_tier_record_schema_v2.py`、`tests/test_codex_reviewer_temp_file_isolation.py` ほか（FR6, FR7, FR8, NFR6）
- [ ] TS-12: PINNED_CHAINS で、performance / spec / architecture を codex → litellm `muse-spark` にする - README のチェーン表と同じ順序で固定される。対象: `tests/test_llm_led_review_user_docs.py`（FR9）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- TS-5 と TS-6 で扱う。

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** effort の値は `^[a-z]+$` に一致した場合だけ TOML 文字列に埋め込む。引用符・バックスラッシュ・空白などを含む値で codex を起動しない（NFR2）。オーケストレーター側では許可リストの検査はしない（FR7）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| 条件 | 終了コード | 出力 |
|------|-----------|------|
| `--effort` に値が無い | exit 1（codex を起動しない） | `ERROR: --effort requires an effort argument` |
| `--effort` の値が `^[a-z]+$` に一致しない | exit 1（codex を起動しない） | 不正な値用の専用の 1 行（2 つのコピーで同じ文言） |
| Codex が effort を拒否した | — | codex-reviewer が Step 6 の非 JSON 規則により harness_unavailable でスキップする |

### Error Flow

```
ラッパーが --effort を解析 → 値なし / 形式不一致 → エラーを出して exit 1（codex を起動しない）
codex exec が effort を拒否 → 非 JSON 出力 → harness_unavailable でスキップ → チェーンの次へ
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1: 各観点の codex レビュアーが、FR2 の表の model と effort で codex exec を呼ぶ。経路（reviewers.yaml → review-phase.md R2 → codex-reviewer Step 5 → ラッパー `--effort`）が文書に書かれ、reviewers.yaml の値と wrapper の argv がテストで確かめられている。（FR1, FR2, FR3, FR6, FR7）
- [ ] AC2: `--effort` を指定しない readonly の起動で、`-c model_reasoning_effort="xhigh"` が 1 つだけ付く。readwrite では付かない。（FR4, NFR1）
- [ ] AC3: `--effort LEVEL` を指定すると、両ラッパーで `-c model_reasoning_effort="LEVEL"` が 1 つだけ付き、xhigh は付かない（readonly、readwrite、em-workflow の `--litellm` ルート）。（FR3, FR4, FR5, NFR3）
- [ ] AC4: `--effort` に値が無い場合と、`^[a-z]+$` に一致しない値の場合は、両ラッパーとも exit 1 で、codex を起動しない。（FR3, NFR2, NFR3）
- [ ] AC5: 両 review-phase.md の record で、effort を渡した codex の run に effort が記録される。（FR8）
- [ ] AC6: 両 README のチェーン表が codex → litellm muse-spark の順になり、effort の受け渡しの 1 文がある。PINNED_CHAINS も同じ順序になっている。（FR9）
- [ ] AC7: security-review-model の SKILL.md に、xhigh 固定と「ほかの観点は model を書かない」の記述が残っていない。（FR10）
- [ ] AC8: em-workflow と em-review の version の minor が、plugin.json と marketplace.json で同じ値に上がっている。（NFR5）
- [ ] AC9: `python3 -m unittest tests.test_codex_wrapper_model_flag tests.test_reviewers_primary_chains tests.test_contributor_tier_criteria` が通る。（FR1, FR2, FR3）
- [ ] AC10: `python3 -m unittest discover -s tests` が通る。（NFR6）

## Assumptions

- A1: reviewers.yaml のキー名は effort とし、フロー形式の codex エントリに置く。litellm エントリには付けない。
- A2: オーケストレーターから codex-reviewer への入力名は effort とし、オーケストレーター側で許可リストの検査はしない。R2b と R4 は同じ input block を使うので、effort も一緒に渡る。
- A3: Codex が effort を拒否した場合は、既存の非 JSON 規則により harness_unavailable でスキップする。専用の判定は足さない。
- A4: usage は `[-m MODEL]` の直後に `[--effort LEVEL]` を入れる。エラー文言は `-m` の書き方に揃える（値が無い場合は「ERROR: --effort requires an effort argument」、不正な値には専用の 1 行）。2 つのコピーで同じ文言にする。
- A5: reviewers.yaml の version キー（em-workflow: 3、em-review: 2）は上げない。
- A6: 回答 wrapper.effort-flag=effort_flag_pattern、wrapper.effort-readwrite=apply_in_readwrite、wrapper.effort-litellm=allow_with_litellm、docs.readme-chain-table=fix_order_and_note_effort、skill.security-review-model-scope=fix_all_contradictions、record.effort-in-round-record=record_effort、version.bump-level=minor_bump、design-step=skip_design を採用した（batch での決定）。
- A7: gpt-6.2-sol の slug が実在するか、各モデルが表の effort に対応しているかは、このタスクでは確かめない。対応していなければ、実行時に harness_unavailable でチェーンの次に進む。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（status: tbd の要件は無い）

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/review-perspective-model-effort/REQUIREMENTS.md`
