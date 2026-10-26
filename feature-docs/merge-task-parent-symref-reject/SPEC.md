# Feature: merge-task-parent-symref-reject

## Overview

merge-task.sh は、マージロック取得後に統合ブランチの参照 `refs/heads/<parent-branch>` がシンボリック参照かを判定し、シンボリック参照なら（または判定できなければ）exit 2 で終える。fast-forward / merge-commit 経路の `git update-ref` には `--no-deref` を付ける。要件の詳細は `feature-docs/merge-task-parent-symref-reject/REQUIREMENTS.md` にある。

## Objectives

- merge-task.sh が `refs/heads/<parent-branch>` に置かれたシンボリック参照を辿らず、統合ブランチ以外のブランチを動かさず、マージしていないタスクを merged として記録しない

## User Stories

### US1: シンボリック参照になった統合ブランチへのマージを拒否する
merge-task.sh の呼び出し元として、`refs/heads/<parent-branch>` がシンボリック参照のときにマージが拒否されてほしい。参照先のブランチが動かず、merged が記録されないようにするため。

**Acceptance Criteria:**
- [ ] AC-1（FR1, FR3, FR4）: ロック待機中に `refs/heads/<parent-branch>` をタスク参照へのシンボリック参照に付け替えると、merge-task.sh は exit 2 で終わり、merged イベントは記録されず、ERROR 行が統合ブランチ名を含む
- [ ] AC-2（FR1, FR4）: ロック待機中に `refs/heads/<parent-branch>` を別ブランチ（main など、fast-forward が成立する位置）へのシンボリック参照に付け替えると、exit 2 で終わり、その別ブランチの値は変わらず、journal.jsonl は作られない
- [ ] AC-3（FR1, FR4）: merge-commit 経路が成立する位置（統合ブランチと分岐した）の別ブランチへのシンボリック参照でも同様に exit 2 で、別ブランチの値と履歴は変わらない
- [ ] AC-4（FR1）: 実行前から `refs/heads/<parent-branch>` がシンボリック参照の場合（ロック待機なし）も exit 2 で終わる
- [ ] AC-5（FR1, FR3）: 参照先が存在しないシンボリック参照（dangling）の場合も exit 2 で終わり、ERROR 行が統合ブランチ名を含む
- [ ] AC-6（FR4）: 拒否後もシンボリック参照の参照先は付け替えた先のまま（merge-task.sh は参照を書き換えない）

### US2: update-ref がシンボリック参照を辿らない
merge-task.sh の呼び出し元として、FR1 の確認の後に参照が付け替えられても、参照先のブランチが更新されないでほしい。

**Acceptance Criteria:**
- [ ] AC-8（FR7）: FR1 の確認を通過した後、fast-forward / merge-commit の update-ref の直前に `refs/heads/<parent-branch>` を別ブランチ（main）へのシンボリック参照に付け替えても、main の値は変わらない（両経路）。付け替え先の値が旧値と一致するケースを含む

### US3: 通常の統合ブランチに対する挙動を保つ
merge-task.sh の呼び出し元として、シンボリック参照でない統合ブランチへのマージは従来どおり動いてほしい。

**Acceptance Criteria:**
- [ ] AC-7（NFR1, FR5, FR6）: 通常の統合ブランチに対する既存テストがすべて通り、`test_merge_unverified_exit_doc_contract` の内容ピンが変更後の merge-task.sh と一致する

## Technical Requirements

### Functional Requirements
- **FR1:** 統合ブランチのシンボリック参照を拒否する。merge-task.sh は、マージロック取得後・統合ブランチの値（PARENT）を show-ref で読む前に `git symbolic-ref --quiet "refs/heads/$PARENT_BRANCH"` を実行する。終了コードが 0（シンボリック参照である）なら exit 2 で終える。拒否は already-contained / fast-forward / merge-commit のいずれの経路、update-ref、merge-tree、commit-tree、journal 追記よりも前に起きる。
- **FR2:** 判定できない場合は拒否する（fail-closed）。FR1 の symbolic-ref の終了コードが 0（シンボリック参照）でも 1（シンボリック参照ではない）でもない場合も exit 2 で終える。終了コード 1 の場合だけ、既存の show-ref による値の解決とコミット型の確認に進む。
- **FR3:** 拒否時のエラー出力。FR1 / FR2 の拒否では、stderr の ERROR 行 1 行に統合ブランチ名（PARENT_BRANCH）を含める。dirty worktree を示す文言（uncommitted / untracked / commit everything）は出さない。
- **FR4:** 参照先を変えない。拒否された実行の後、シンボリック参照そのもの（`refs/heads/<parent-branch>` の参照先）、参照先ブランチの値、タスク参照の値はいずれも実行前のまま残り、journal.jsonl は作られない。
- **FR5:** スクリプト内コメントの更新。merge-task.sh 冒頭の説明コメント（統合ブランチの値を完全一致の参照名で読む旨の段落）、exit 2 の例示、および「Merge source and parent」節のコメントに、統合ブランチの参照がシンボリック参照なら exit 2 で終えること、および update-ref を `--no-deref` で呼ぶことを書き足す。"Parent already contains us" を含む行は 1 行のまま残し、その次の行は `merge-base --is-ancestor` の確認のままにする。
- **FR6:** 内容ピンの更新。`tests/test_merge_unverified_exit_doc_contract.py` の `EXPECTED_MERGE_TASK_SH_SHA256` を、変更後の merge-task.sh の sha256 に同じコミットで更新し、直前のコメントの来歴列挙に本 feature を追記する。
- **FR7:** update-ref はシンボリック参照を辿らない。fast-forward 経路と merge-commit 経路の `git update-ref "refs/heads/$PARENT_BRANCH" NEW OLD` の 2 箇所に `--no-deref` を付ける。既存の旧値（PARENT）による比較は残す。FR1 の確認の後、update-ref までの間に `refs/heads/<parent-branch>` がシンボリック参照へ付け替えられても、参照先のブランチ（main など）は更新されない。通常の直接参照に対しては更新先も旧値比較も変わらない。

### Non-Functional Requirements
- **NFR1 - 既存挙動の維持:** シンボリック参照でない通常の統合ブランチに対する既存の挙動（exit 0 / 1 / 2 の意味、fast-forward・merge-commit・already-contained の各経路、journal 追記）は変えない。`tests/test_merge_task_journal.py` の既存テストはすべて通る。
- **NFR2 - テストの実行形態:** テストは標準ライブラリだけを使い、一時ディレクトリに作った使い捨ての git リポジトリで merge-task.sh をサブプロセスとして実行する（test/README.md）。
- **NFR3 - version を変更しない:** プラグインの version は変更しない（core-plugin-version-bump）。
- **NFR4 - kill / pkill を使わない:** kill / pkill を使わない。ロック待機中の変更は既存ヘルパ `_run_merge_with_mutation_during_lock_wait` を使う。

## Implementation Approach

### Architecture

merge-task.sh のロック取得後の処理順:

```
マージロック取得
  → git symbolic-ref --quiet "refs/heads/$PARENT_BRANCH"
       終了コード 0      → ERROR 行（PARENT_BRANCH を含む）、exit 2   (FR1, FR3)
       終了コード 0/1 以外 → ERROR 行（PARENT_BRANCH を含む）、exit 2   (FR2, FR3)
       終了コード 1      → 既存の show-ref による PARENT の解決とコミット型の確認
  → already-contained / fast-forward / merge-commit
       fast-forward:  git update-ref --no-deref "refs/heads/$PARENT_BRANCH" NEW OLD   (FR7)
       merge-commit:  git update-ref --no-deref "refs/heads/$PARENT_BRANCH" NEW OLD   (FR7)
  → journal 追記
```

### Data Flow

該当なし

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- merge-task.sh: 変更対象
- `tests/test_merge_task_journal.py`: 既存テストと既存ヘルパ `_run_merge_with_mutation_during_lock_wait` / `_run_merge`
- `tests/test_merge_unverified_exit_doc_contract.py`: merge-task.sh の内容ピン `EXPECTED_MERGE_TASK_SH_SHA256`

**External Dependencies:**
- git（`symbolic-ref --quiet`、`update-ref --no-deref`）

### File Structure

対象ファイルは create-plan で `workflow.yaml` の各タスクの `files` として確定する。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/merge-task-parent-symref-reject/**`
- `test-docs/merge-task-parent-symref-reject/**`

`feature-docs/merge-task-parent-symref-reject/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/merge-task-parent-symref-reject/**` covers `test-docs/merge-task-parent-symref-reject/{T}.tests.yaml`, the
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
該当なし

### Integration Tests
- [ ] TS-1（AC-1, AC-6）: `_run_merge_with_mutation_during_lock_wait` の mutate で `git symbolic-ref refs/heads/<parent> refs/heads/em-workflow/feat/task0001` を実行。exit 2、journal なし、ERROR 行に PARENT_BRANCH、タスク参照の値は不変
- [ ] TS-2（AC-2, AC-6）: mutate で `git symbolic-ref refs/heads/<parent> refs/heads/main` を実行（main は初期コミットでタスク先端の祖先）。exit 2、`refs/heads/main` の値は不変、journal なし、`git symbolic-ref refs/heads/<parent>` は `refs/heads/main` を返す
- [ ] TS-3（AC-3）: 統合ブランチから分岐したコミットを持つ別ブランチを作り、mutate でそのブランチへのシンボリック参照に付け替える。exit 2、そのブランチの値は不変で "merge: task0001" コミットは作られない
- [ ] TS-4（AC-4）: ロック待機なしで、実行前に `refs/heads/<parent>` を `refs/heads/main` へのシンボリック参照にしてから `_run_merge`。exit 2、main 不変
- [ ] TS-5（AC-5）: `refs/heads/<parent>` を存在しない `refs/heads/...` へのシンボリック参照にしてから実行。exit 2、ERROR 行に PARENT_BRANCH
- [ ] TS-6（AC-7）: 既存テスト一式と `test_merge_unverified_exit_doc_contract` を実行して通る
- [ ] TS-7（既存挙動の固定）: ロック待機中にタスク参照を別ブランチへのシンボリック参照に付け替えると、ロック後の HEAD の再確認で exit 2 になる
- [ ] TS-8（AC-8）: PATH に置いた git の仲介スクリプトで update-ref の呼び出しを捕まえ、その直前に `refs/heads/<parent>` を main へのシンボリック参照に付け替えてから本物の git に渡す（main の先端を旧値と一致させる）。fast-forward / merge-commit の両経路で main の値が変わらない。具体的な仲介の方式は計画段階で決める

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 参照先が存在しないシンボリック参照（dangling）: exit 2（TS-5）
- [ ] FR1 の確認後、update-ref の直前の付け替えで付け替え先の値が旧値と一致する: 参照先ブランチ（main）は変わらない（TS-8）

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `refs/heads/<parent-branch>` がシンボリック参照なら、または判定できなければ exit 2（FR1, FR2）
- **Data Protection:** 拒否時、参照・参照先ブランチ・タスク参照を変えず、journal.jsonl を作らない（FR4）。update-ref はシンボリック参照を辿らない（FR7）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| exit 2 | `refs/heads/<parent-branch>` がシンボリック参照（symbolic-ref の終了コード 0） | - | stderr の ERROR 行 1 行。PARENT_BRANCH を含み、uncommitted / untracked / commit everything を含まない |
| exit 2 | symbolic-ref の終了コードが 0 でも 1 でもない | - | 同上 |

### Error Flow

```
symbolic-ref 判定 → 拒否（終了コード 0 / その他） → ERROR 行を stderr へ → exit 2（update-ref・merge-tree・commit-tree・journal 追記の前）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Documentation is complete
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- シンボリック参照の検出はロック取得後に 1 回だけ行う。ロック前の識別の確認には追加しない（ロック後の確認がロック前に置かれた参照も捕捉するため）
- update-ref `--no-deref` は、旧値と一致する付け替えの場合にシンボリック参照そのものを直接参照へ置き換えて成功し得る。参照先ブランチは動かないので許容する。また already-contained 経路には update-ref が無いため、FR1 の確認後〜merge-base の間の付け替えによる誤った merged 記録は本 feature の範囲外とする（主体は参照を直接書き換えられる権限を既に持つ）
- タスク参照側のコードは変更しない。ロック後の `git symbolic-ref --quiet HEAD` が再帰的に解決するので、別ブランチへの付け替えは既存の再確認で拒否される（TS-7 で固定する）
- `git symbolic-ref --quiet <ref>` の終了コードは、シンボリック参照なら 0、通常の参照・存在しない参照なら 1 として扱う。それ以外はすべて FR2 で拒否する

## References

- 要件定義書: `feature-docs/merge-task-parent-symref-reject/REQUIREMENTS.md`
- テストの書き方: `test/README.md`
