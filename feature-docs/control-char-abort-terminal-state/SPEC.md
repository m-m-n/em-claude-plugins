# Feature: control-char-abort-terminal-state

## Overview

implement フェーズの Step I.2.a にある制御文字チェック（Control-character check）が
フェーズを止めたとき、workflow.yaml を終端状態にする。終端の扱いは Step I.2.c の
abort phase を引用する形で `em-workflow/references/implement-phase.md` に追記し、
回帰テストを `tests/test_canonical_worktree_path_docs.py` に加える。

## Objectives

- Step I.2.a の制御文字チェックが implement フェーズを止めたとき、フェーズは
  workflow.yaml の終端状態で終わる。develop は停止条件 2（stuck）まで ABORT を
  繰り返さず、停止条件 3 で止まる。
- `queue_stop_guard.py` が、ターンの終了を止めることも、チェックが拒否したタスクの
  起動をオーケストレーターに求めることもなくなる。

## User Stories

N/A（ユーザーインターフェースを持たない、プロトコル文書と文書テストの変更）

## Technical Requirements

### Functional Requirements

- **FR1: 制御文字による停止での終端書き込み**
  `em-workflow/references/implement-phase.md` の Step I.2.a、Control-character check の
  段落に、正規化済みの `worktree_path` を拒否した後、フェーズが Step I.2.c の
  abort phase と同じ終端の扱いを取ることを書く。その扱いは次のとおり。
  integration ブランチの先端を取得し、integration worktree を更新し、1 回の書き込みで
  implement ステップの `status` を `failed`、`failed_kind` を `decision` にし、
  その書き込みだけを `commit-docs.sh` でコミットする。create-plan の `needs_update`、
  タスクの status や notes の書き込み、worktree やブランチの片付けはしない。
  制御はユーザーに、develop の停止条件 3 を通って戻る。

- **FR2: abort phase を書き直さずに引用する**
  追記する文は、終端の扱いの出典として Step I.2.c の abort phase を名指しする。
  回帰テストが確かめるため、`failed` / `failed_kind` の `decision` の値と
  `commit-docs.sh` のコミットも書く。この経路では journal の failed イベントが無く、
  abort phase の infra 規則は当てはまらないため、`failed_kind` は無条件に `decision` とする。

- **FR3: 既存の停止文を 1 つに保つ**
  追記する文には 'ABORT the implement phase' という句を含めない。段落内でこの句を
  含む文はちょうど 1 つのままとし、その文は違反タスク ID の報告と
  'build no implementer launch prompt for any selected task' の句を保つ。
  追記する文は 'Unicode general category Cc' を含む同じ 1 つの段落ブロックの中に置く。
  段落の位置は、正規化の手順の後、承認ゲートと起動ループの段落の前のままとする。
  既存の `check_control_char_scope`、rejected_set、stop、placement の各チェックは
  引き続き通る。

- **FR4: failed_kind の書き込み経路数を正しく保つ**
  `em-workflow/references/workflow-schema.md` の failed_kind セクションは
  'Three write paths make such a write' と書き、`implement-phase.md` を引用している。
  この数を、implement を `failed` にする 4 つ目の経路として制御文字による停止を含めた
  数に更新する。`implement-phase.md` の引用は保ち、各経路の値は列挙しない。

- **FR5: tests/test_canonical_worktree_path_docs.py の回帰テスト**
  既存の `check_control_char_*` 関数にならったチェック関数を追加する。この関数は
  制御文字チェックの 1 つの段落の中で、引用された終端の扱いを探す。Step I.2.c の
  abort phase への参照、implement の status `failed`、`failed_kind` の `decision`、
  `commit-docs.sh` の 4 つを見つけなければならない。
  生きた文書に対して問題が出ないことを期待するテストを追加する。
  生きたセクションから `_replace_phrase` または `_remove_paragraph_with` で作る
  偽造コピーのテストを追加する。
  (a) 終端の扱いの文を取り除いたコピーは問題を返す。
  (b) `failed_kind` の `decision` を別の値に置き換えたコピーは問題を返す。
  あわせて、既存の `check_control_char_stop` が生きたセクションで引き続き通ることを
  確かめる。

### Non-Functional Requirements

- **NFR1:** テストモジュールは標準ライブラリだけを import する（既存のテストがこれを
  固定している）。テストは見出しと安定した句でテキストを探し、行番号には頼らない。
- **NFR2:** `em-workflow/hooks/queue_stop_guard.py` は変更しない。このフックは
  implement ステップが `in_progress` でないフィーチャーを既に対象外にしている。
- **NFR3:** プラグインの version（`em-workflow/.claude-plugin/plugin.json`、
  `.claude-plugin/marketplace.json`）は変更しない。patch の引き上げは Actions が行う。
- **NFR4:** 既存の制御文字の段落の文言は保つ。対象範囲の文、拒否集合の範囲、
  サニタイズしない旨の句、フォールバックしない旨の句、Step I.0 との比較がこれに当たる。
  追加するのは終端の扱いの記述だけとする。

## Implementation Approach

### Architecture

N/A（UI・アプリケーション層・データベースを持たない）

変更対象は次の 3 ファイル。

- `em-workflow/references/implement-phase.md` — Step I.2.a の Control-character check
  段落に終端の扱いの記述を追記する（FR1, FR2, FR3, NFR4）。
- `em-workflow/references/workflow-schema.md` — failed_kind セクションの書き込み経路数を
  更新する（FR4）。
- `tests/test_canonical_worktree_path_docs.py` — 新しいチェック関数と、生きた文書・
  偽造コピーのテストを追加する（FR5, NFR1）。

### Data Flow

制御文字チェックで停止したときの流れ（FR1）。

```
正規化済み worktree_path を拒否
  → 違反タスク ID を報告し、どの選択タスクの起動プロンプトも作らない（既存の停止文）
  → integration ブランチの先端を取得
  → integration worktree を更新
  → 1 回の書き込みで implement.status = failed、failed_kind = decision
  → その書き込みだけを commit-docs.sh でコミット
  → develop の停止条件 3 でユーザーに制御が戻る
```

### API Design

N/A

### Database Schema

N/A

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md` の Step I.2.c abort phase: 終端の扱いの出典として引用する（FR2）。
- `commit-docs.sh`: 終端の書き込みのコミットに使う（FR1）。
- `em-workflow/hooks/queue_stop_guard.py`: 変更しない。implement が `in_progress` でないフィーチャーは対象外になる（NFR2）。

**External Dependencies:**
- なし（テストは標準ライブラリのみ、NFR1）

### File Structure

```
em-workflow/
└── references/
    ├── implement-phase.md      # Step I.2.a Control-character check 段落に追記
    └── workflow-schema.md      # failed_kind セクションの書き込み経路数を更新
tests/
└── test_canonical_worktree_path_docs.py   # 終端の扱いのチェックとテストを追加
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

- [ ] TS1: 生きた `implement-phase.md` — 新しい終端の扱いのチェックが I.2.a セクションに対して `[]` を返す（FR1, FR2, FR5）
- [ ] TS2: 制御文字チェック段落から終端の扱いの文を取り除いた偽造コピー — 新しいチェックが問題を返す。コピーと元のセクションが異なることも確かめる（FR1, FR5）
- [ ] TS3: `failed_kind` の `decision` を置き換えた偽造コピー（例: `infra`）— 新しいチェックが問題を返す（FR2, FR5）
- [ ] TS4: 生きた文書 — `check_control_char_stop`、`check_control_char_scope`、`check_control_char_rejected_set`、`check_control_char_placement` が引き続き `[]` を返す。追記した文が 2 つ目の 'ABORT the implement phase' の文を足しておらず、段落を分割していないことを示す（FR3, NFR4）

### Integration Tests

- [ ] TS5: 全体のスイート — `python3 -m unittest discover -s tests` が通る（FR4, FR5, NFR1）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] 先端の取得からコミットまでの間に integration ブランチが動いた場合は、既存の `commit-docs.sh` の exit 4 からの回復（Branch & Worktree Model）を適用する（前提 A1）
- [ ] 以前の補充で起動済みの兄弟タスクは、取り消しも巻き戻しもしない（前提 A1）

### Performance Tests

N/A

## Security Considerations

N/A（認証・認可・外部入力の新規処理なし）

## Error Handling

N/A（エラーコードなし）。制御文字による停止の扱いは FR1 のとおり。

## Performance Optimization

N/A

## Acceptance Criteria

- [ ] AC-1: `em-workflow/references/implement-phase.md` の Step I.2.a、Control-character check 段落が、停止は Step I.2.c の abort phase の終端の扱いを取ると書いている。つまり implement の status は 1 回の書き込みで `failed`、`failed_kind` は `decision` になり、その書き込みは `commit-docs.sh` でコミットされ、worktree もブランチも片付けない。制御は develop の停止条件 3 を通って戻る。
- [ ] AC-2: 段落内で 'ABORT the implement phase' を含む文はちょうど 1 つのままで、`tests/test_canonical_worktree_path_docs.py` の既存の制御文字テストはすべて変更なしで通る。
- [ ] AC-3: `tests/test_canonical_worktree_path_docs.py` に、終端の扱いの引用を確かめる生きた文書のテストと、引用の無いコピーや別の `failed_kind` のコピーが失敗する偽造コピーのテストがある。
- [ ] AC-4: `em-workflow/references/workflow-schema.md` の failed_kind セクションの書き込み経路数が、`implement-phase.md` が定める implement を failed にする書き込み経路の数と一致する。
- [ ] AC-5: `python3 -m unittest discover -s tests` が通る。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed

## Assumptions

- **A1:** 終端の書き込みはチェックの時点で行い、それ以前に起動済みのタスクの完了は待たない。待つと、拒否したタスクには journal イベントが無く何も抑止しないため、この変更で取り除くフックのブロックが戻ってくる。以前の補充で起動済みの兄弟タスクは、取り消しも巻き戻しもしない。先端の取得からコミットまでの間に integration ブランチが動いた場合は、既存の `commit-docs.sh` の exit 4 からの回復（Branch & Worktree Model）を適用する。（可逆）
- **A2:** `failed_kind` は `decision` とする。原因（解決後の worktree パスにある制御文字）はユーザーによるファイルシステム配置の修正を要し、reason が orphaned または stale-launched の journal failed イベントも存在しない。そのため batch の failed_kind 自動再開は当てはまらず、停止条件 3 は interactive と batch の両方で発火する。（可逆）
- **A3:** implement が `failed` になると `queue_stop_guard.py` は何も出さない。`active_candidates` は `implement_in_progress` で絞り込み、`tests/test_queue_stop_guard.py` は `in_progress` でない場合の通過を既に固定している（`pending` を使う `test_no_feature_with_implement_in_progress_passes`）。完了の定義上、新しいフックのテストは要らない。（可逆）
- **A4:** チェックの前に `git worktree add -b` で作られたタスクの worktree とブランチは、abort phase の片付けない規則のとおり残す。後の再入では I.2.a の Resume guard のもとでそれらを再利用する。（可逆）
- **A5:** コミットの件名は、abort phase の 'docs({feature}): implement phase aborted' に従う。どちらの選択も変更できる。（可逆）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- `em-workflow/references/implement-phase.md`（Step I.2.a Control-character check、Step I.2.c abort phase）
- `em-workflow/references/workflow-schema.md`（failed_kind セクション）
- `tests/test_canonical_worktree_path_docs.py`
- `tests/test_queue_stop_guard.py`
