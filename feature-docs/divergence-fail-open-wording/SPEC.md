# Feature: divergence-fail-open-wording

## Overview

`em-workflow/references/implement-phase.md` の I.2.a にある unlaunched 判定の divergence 段落を、Supporting cast の fail-open 定義と食い違わない表現に書き直し、I.2.b step 1 の reconcile ルールとの関係を両側に書く。`tests/test_recycled_task_id_consistency.py` の固定文言と negative proof を新しい表現に合わせ、em-workflow の version を 0.2.8 に上げる。要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照。

## Objectives

- em-workflow/references/implement-phase.md の I.2.a にある unlaunched 判定の divergence 段落を、同じ文書の Supporting cast にある fail-open 定義（想定外の状態では exit 0 で黙って通す）と食い違わない表現に直す
- divergence 段落と I.2.b step 1 の reconcile ルールの関係を、どちらを単独で読んでも誤読しない形にする
- tests/test_recycled_task_id_consistency.py で固定している文言を新しい表現に合わせ、対になる negative proof も更新する

## User Stories

### US1: divergence 段落の根拠を fail-open 定義と食い違わない表現にする
implement-phase.md の読者として、divergence 段落の説明が Supporting cast の fail-open 定義と食い違わないようにしたい。

**Acceptance Criteria:**
- [ ] AC-1: I.2.a の divergence 段落に 'fail-open' という文字列が含まれていない。
- [ ] AC-2: divergence 段落に、初回 launch の取りこぼしを検出するという根拠と、誤 BLOCK が consecutive-block cap（3）で有界化されている事実の両方が書かれている。

### US2: divergence 段落と I.2.b step 1 のどちらを単独で読んでも誤読しない
implement-phase.md の読者として、divergence 段落と I.2.b step 1 のどちらか一方だけを読んでも `status != merged` がどこで効くかを誤読しないようにしたい。

**Acceptance Criteria:**
- [ ] AC-3: divergence 段落が、I.2.b step 1 の reconcile も status を参照せずに分類することと、`status != merged` が I.2.a の選択時フィルタとして効くことを述べている。
- [ ] AC-4: I.2.b step 1 に、no-event の分類が status を参照しないことと、merged の除外が I.2.a の選択で適用されることを示す注記がある。'the recycled-task-id rule in I.2.a above' も残っている。

### US3: 固定文言とテストを新しい表現に合わせる
tests/test_recycled_task_id_consistency.py で固定している文言を新しい表現に合わせ、対になる negative proof も更新したい。

**Acceptance Criteria:**
- [ ] AC-5: DIVERGENCE_REASON_PHRASE が新しい文言になっている。正の assertion が現行文書で通り、新しく足した negative proof が base 4999893 時点の divergence 段落サンプルに対して『新しい phrase が無く、旧い phrase が有る』ことを assert している。
- [ ] AC-6: plugin.json と marketplace.json の em-workflow の version が、どちらも 0.2.8 で一致している。
- [ ] AC-7: リポジトリのルートで `python3 -m unittest discover -s tests` が通る。

## Technical Requirements

### Functional Requirements
- **FR1:** divergence の正当化を fail-open 以外の語で書き直す。I.2.a の divergence 段落（統合 worktree の em-workflow/references/implement-phase.md の 298-308 行、'The other three queue hooks detect a task as **unlaunched** solely from ...' で始まる段落）から、'the hooks are fail-open nets, not authorities' という句と、この挙動を 'fail-open' と呼ぶ記述をすべて取り除く。書き直した段落では次の 2 点を明示する。(a) 意図された根拠：journal にイベントが 1 件も無いタスクを unlaunched として扱うことで、初回 launch の取りこぼしを検出する。(b) 結果として queue_stop_guard.py は workflow.yaml の status が merged のタスク名を挙げて turn の終了を BLOCK（exit 2）することがあるが、この誤 BLOCK は consecutive-block cap（3）で有界化されており、上限を超えると警告を出して turn を終わらせる。この挙動に 'fail-open' という語を当てない。
- **FR2:** divergence 段落で I.2.b step 1 との関係を述べる。divergence 段落には次の 2 点も書く。(1) I.2.b step 1 の reconcile も、status を参照せずに『no event → unlaunched』と分類する。(2) `status != merged` による除外は I.2.a の選択時フィルタとして効く（I.2.b は I.2.a に再突入する）。このため、『orchestrator は分類の時点で常に `status != merged` を併用する』とは読めない形にする。
- **FR3:** I.2.b step 1 に注記を足す。I.2.b step 1（465-471 行）の『no event → unlaunched』に短い注記を足す。内容は、この分類が workflow.yaml の status を参照しないこと、そして `status != merged` による除外は I.2.a の選択条件で適用されること（divergence 段落を参照先として示す）。既存の句 'the recycled-task-id rule in I.2.a above' はそのまま残す。
- **FR4:** 固定文言とテストを更新する。tests/test_recycled_task_id_consistency.py の `DIVERGENCE_REASON_PHRASE`（439 行。ticket に書かれた `DIVERGENCE_DELIBERATE_PHRASE` は HEAD に存在しない）を、FR1 の新しい根拠の文言に合わせて更新する。986 行の正の assertion も同じく更新し、fail-open を名指ししているテストメソッド名 `test_reason_states_fail_open_nets_not_authorities` も内容に合う名前に変える。1349 行の negative proof（`test_unlaunched_divergence_matchers_flag_absence_in_pre_change_wording`）は、今の b28a716 時点のサンプルに対してだと自明にしか通らないので、次の形で対になる negative proof を足す。このモジュールの既存パターンに倣い、base 4999893 時点の divergence 段落を一字一句そのまま写した pre-change サンプル定数を置き、そのサンプルには新しい phrase が無く、旧い 'the hooks are fail-open nets, not authorities' が有ることを assert する。FR2・FR3 で足す新しい文言にも、正の pin とこのサンプルに対する negative proof を付ける。
- **FR5:** em-workflow の version を上げる。em-workflow/.claude-plugin/plugin.json の version と、.claude-plugin/marketplace.json の em-workflow エントリの version を、どちらも 0.2.7 から 0.2.8 に上げる。

### Non-Functional Requirements
- **NFR1 - 変更対象外の箇所:** 次の箇所は変更しない。em-workflow/hooks/queue_stop_guard.py のコード、Supporting cast の fail-open 定義（1167-1171 行）、hook classification table とその anchor、I.2.a の Select 行の改行位置に依存する生リテラル（'`tasks.*.status`. Select\nunlaunched tasks (no journal event yet and `status != merged`, ascending'）。
- **NFR2 - 既存の固定句の維持:** divergence 段落に既に固定されている句は、空白を正規化した状態で本文に残す。対象は UNLAUNCHED_SOLELY_FROM_ABSENCE_PHRASE、NARROWER_THAN_ORCHESTRATOR_PHRASE、NO_EQUIVALENT_EXCLUSION_PHRASE、AUTHORITATIVE_SOURCE_PHRASE。
- **NFR3 - テストの import 制約:** テストが import してよいのは Python 標準ライブラリの unittest と、同じディレクトリにある既存モジュールだけ（test/README.md）。

## Implementation Approach

### Architecture

**System Architecture:**
該当なし（リファレンス文書、Python の unittest、version 番号の JSON の変更のみ）。

**Component Diagram:**
```
em-workflow/references/implement-phase.md
  ├── I.2.a divergence 段落   ← FR1, FR2
  └── I.2.b step 1            ← FR3
tests/test_recycled_task_id_consistency.py  ← FR4（上記 2 か所の文言を固定する）
em-workflow/.claude-plugin/plugin.json      ← FR5
.claude-plugin/marketplace.json             ← FR5
```

### Data Flow

該当なし。

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- tests/test_recycled_task_id_consistency.py: implement-phase.md の I.2.a 節・I.2.b 節の文言を固定している
- test_plugin_version_parity: plugin.json と marketplace.json の version の一致を検査している

**External Dependencies:**
- なし（NFR3）

### File Structure

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json                         # FR5
└── references/
    └── implement-phase.md                  # FR1, FR2, FR3
.claude-plugin/
└── marketplace.json                        # FR5
tests/
└── test_recycled_task_id_consistency.py    # FR4
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/divergence-fail-open-wording/**`
- `test-docs/divergence-fail-open-wording/**`

`feature-docs/divergence-fail-open-wording/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/divergence-fail-open-wording/**` covers `test-docs/divergence-fail-open-wording/{T}.tests.yaml`, the
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
- [ ] TS-1（FR1 / AC-1）: 現行文書の I.2.a 節を取り出し、空白を正規化する。divergence 段落（UNLAUNCHED_SOLELY_FROM_ABSENCE_PHRASE から AUTHORITATIVE_SOURCE_PHRASE の終わりまで）に 'fail-open' が無いことを assert する。
- [ ] TS-2（FR1, FR4 / AC-2, AC-5）: I.2.a 節に、新しい DIVERGENCE_REASON_PHRASE（初回 launch 取りこぼし検出の根拠）と、consecutive-block cap（3）で有界化されていることを述べる句が含まれることを assert する。
- [ ] TS-3（FR2 / AC-3）: I.2.a 節に、I.2.b step 1 の status 無参照の分類と、I.2.a の選択時フィルタとしての `status != merged` を述べる句が含まれることを assert する。
- [ ] TS-4（FR3 / AC-4）: I.2.b 節に FR3 の注記の句と 'the recycled-task-id rule in I.2.a above' が含まれることを assert する。
- [ ] TS-5（FR4 / AC-5）: negative proof：base 4999893 時点の divergence 段落を一字一句写したサンプルでは、新しい phrase（TS-2・TS-3 の句）がすべて無く、'the hooks are fail-open nets, not authorities' が有ることを assert する。I.2.b step 1 の pre-change サンプルでは FR3 の注記の句が無いことを assert する。
- [ ] TS-6（FR5 / AC-6）: 既存の test_plugin_version_parity が 0.2.8 で通る。

### Integration Tests
- [ ] TS-7（FR1〜FR5, NFR1〜NFR3 / AC-7）: `python3 -m unittest discover -s tests` の全体が通る。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] 該当なし

### Edge Cases
- [ ] 改名したテストメソッド名と test-docs/recycled-task-id-contract/task0001.tests.yaml（35 行）の旧名参照: task0001.tests.yaml は書き換えない。全体テストがこの参照の不整合を理由に落ちた場合は、改名をやめて旧い名前を残す（A5）。
- [ ] pre-change サンプル自体の欠落: サンプルに期待する旧句が含まれていることを assert し、サンプルが空や別文面のときに negative proof が自明に通るのを防ぐ（A8）。
- [ ] Supporting cast の 'All of the hooks above are fail-open nets, not authorities': 変更対象外のため残る。本文側で旧句が無いことの検査は divergence 段落の範囲に限定する（A8）。
- [ ] 『status を参照しない』の範囲: journal にイベントが無い場合の分類に限定し、failed かつ pending の例外（recycled-task-id carve-out）と混同させる書き方をしない（A7）。

### Performance Tests
- [ ] 該当なし

## Security Considerations

該当なし。

## Error Handling

該当なし。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Code review is completed
- [ ] AC-1〜AC-7 をすべて満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- A1: ticket にある `DIVERGENCE_DELIBERATE_PHRASE` は、HEAD の `DIVERGENCE_REASON_PHRASE`（tests/test_recycled_task_id_consistency.py:439）を指しているものとして扱う。定数名は変えずに値だけ更新する。
- A2: ticket が引用する 'deliberate, intended fail-open behavior' と 'the hook is a fail-open net' は HEAD の文書に無い。書き換えの対象は、実際にある 'the hooks are fail-open nets, not authorities'（implement-phase.md の 305-306 行）とする。
- A3: 完了の定義にある『どちらか一方を読んだだけで誤読しない』を満たすため、divergence 段落（FR2）と I.2.b step 1 への注記（FR3）の両方を入れる。
- A4: Supporting cast の fail-open 定義（1167-1171 行）と queue_stop_guard.py のコードは変えない。
- A5: テストメソッド `test_reason_states_fail_open_nets_not_authorities` は改名する。過去の feature の記録である test-docs/recycled-task-id-contract/task0001.tests.yaml（35 行でこの名前を参照）は書き換えない。全体テストがこの参照の不整合を理由に落ちた場合は、改名をやめて旧い名前を残す。同じテストモジュール内で旧メソッド名を参照している箇所（対応一覧など）は新しい名前に揃える。
- A6: version の上げ幅は patch（0.2.7 → 0.2.8）とする。
- A7: divergence 段落と I.2.b step 1 の注記で『status を参照しない』と書く範囲は、journal にイベントが無い場合の分類に限定する。failed かつ pending の例外（recycled-task-id carve-out）と混同させる書き方をしない。
- A8: 新しく足す pre-change サンプル定数には、このモジュールの既存方式に倣ってサンプル自体の欠落を検出する検査（サンプルに期待する旧句が含まれていることの assert）も置く。本文側で旧句が無いことの検査は divergence 段落の範囲に限定する（Supporting cast の 'All of the hooks above are fail-open nets, not authorities' は残るため）。

## References

- Requirements: [REQUIREMENTS.md](REQUIREMENTS.md)
- Task: [https://www.notion.so/3c03509ec8ee818fa135ef93bc6f3e89](https://www.notion.so/3c03509ec8ee818fa135ef93bc6f3e89)
