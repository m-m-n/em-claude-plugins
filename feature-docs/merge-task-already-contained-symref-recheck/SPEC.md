# Feature: merge-task-already-contained-symref-recheck

## Overview

merge-task.sh の already-contained 経路（"Parent already contains us" の分岐）で、merged を記録する直前に統合ブランチ参照 `refs/heads/$PARENT_BRANCH` を再確認する。シンボリック参照の再判定と、新値・旧値とも PARENT の同値 CAS をこの順で行い、どちらかで拒否したら exit 2 で終える。要件は `REQUIREMENTS.md` を参照する。

## Objectives

- merge-task.sh の already-contained 経路で、シンボリック参照の検査と統合ブランチの値の取得の間に統合ブランチ参照をシンボリック参照へ差し替えられても、統合していないタスクに merged が記録されず、exit 0 にならない
- シンボリック参照でない通常の統合ブランチに対する merge-task.sh の挙動（exit 0 / 1 / 2 の意味、already-contained・fast-forward・merge-commit の各経路、journal 追記）を変えない

## User Stories

該当なし。受け入れ基準は「Acceptance Criteria」節に記載する。

## Acceptance Criteria

- [ ] AC-1（FR1, FR2, FR3, FR6）: ロック取得後のシンボリック参照の検査を通過した直後、統合ブランチの値の取得より前に `refs/heads/<parent-branch>` をタスク参照へのシンボリック参照に差し替えると、merge-task.sh は exit 2 で終わる。ERROR 行は 1 行で、統合ブランチ名と "symbolic ref" を含み、dirty worktree の文言を含まない。journal.jsonl は作られず、stdout に `MERGED:` 行は無い。タスク参照の値は変わらず、統合ブランチ参照はタスク参照を指すシンボリック参照のまま残る
- [ ] AC-2（FR1, FR2, FR3）: AC-1 と同じ差し替えの後、再確認の `git symbolic-ref --quiet` の直前に統合ブランチ参照を元の値（タスクを含まない値）の直接参照へ戻すと、同値 CAS が値の不一致で失敗し exit 2 で終わる。ERROR 行は統合ブランチ名と "update-ref" を含み、journal.jsonl は作られず、統合ブランチ参照は元の値の直接参照のまま残る
- [ ] AC-3（FR1, FR2, FR3）: 統合ブランチが既にタスクブランチを含む状態（マージ済みのタスクの再実行）で、再確認の `git symbolic-ref --quiet` の終了コードが 0 でも 1 でもない場合、exit 2 で終わる。ERROR 行は統合ブランチ名と終了コードを含み、journal.jsonl の行は増えない
- [ ] AC-4（NFR1）: 通常の統合ブランチでマージ済みのタスクを再実行すると、従来どおり exit 0 で `already contained in` を出力し、merged を 1 行追記し、統合ブランチ参照の値は変わらない（既存テスト test_idempotent_already_merged_path_appends_merged_line_and_tolerates_duplicates が通る）
- [ ] AC-5（NFR1, FR4, FR5）: `tests/test_merge_task_journal.py` と `tests/test_merge_unverified_exit_doc_contract.py` の既存テストがすべて通る。内容ピンが変更後の merge-task.sh と一致し、"Parent already contains us" を含む行は 1 行でその次の行が `merge-base --is-ancestor` の確認である

## Technical Requirements

### Functional Requirements
- **FR1:** already-contained 経路での統合ブランチ参照の再確認。merge-task.sh は already-contained 経路（"Parent already contains us" の分岐）で `git merge-base --is-ancestor "$HEAD_SHA" "$PARENT"` が成功した後、journal 追記（append_merged_event）と `MERGED:` 行の出力より前に、次の順で統合ブランチ参照 `refs/heads/$PARENT_BRANCH` を確認する。(1) `git symbolic-ref --quiet "refs/heads/$PARENT_BRANCH"` を実行し、終了コード 0（シンボリック参照。dangling を含む）なら exit 2、1 なら続行、それ以外なら exit 2 で終える。(2) `git update-ref --no-deref "refs/heads/$PARENT_BRANCH" "$PARENT" "$PARENT"`（新値・旧値とも PARENT の同値 CAS）を実行し、失敗した場合は exit 2 で終える。(2) は journal 追記の前に行う最後の git 呼び出しとする。
- **FR2:** 再確認で拒否したときの副作用なし。FR1 で拒否した実行では、journal.jsonl に merged を追記せず（journal.jsonl が無ければ作らず、あれば行を増やさず）、stdout に `MERGED:` 行を出さない。FR1 (1) で拒否した実行では、merge-task.sh は統合ブランチ参照（シンボリック参照ならその参照先の指定も）、参照先ブランチの値、タスク参照の値のいずれも書き換えない。FR1 (2) で拒否した実行では、統合ブランチ参照の値とタスク参照の値を書き換えない。
- **FR3:** 拒否時のエラー出力。FR1 で拒否するときは stderr に ERROR 行を 1 行だけ出し、その行に統合ブランチ名（PARENT_BRANCH）を含める。シンボリック参照を理由とする拒否では、その行に "symbolic ref" を含める。symbolic-ref の終了コードが 0 でも 1 でもない拒否では、その行に終了コードを含める。同値 CAS の失敗による拒否では、その行に "update-ref" を含める。dirty worktree を示す文言（uncommitted / untracked / commit everything）は出さない。
- **FR4:** スクリプト内コメントの更新。merge-task.sh 冒頭の説明コメント（統合ブランチ参照は直接参照でなければならない旨の段落）、exit 2 の例示、「Merge source and parent」節のコメント、および already-contained の分岐に、already-contained 経路では merged を記録する直前に統合ブランチ参照が直接参照のままであることを確認し、続けて値が PARENT のままであることを同値 CAS で確認し、そうでなければ exit 2 で終えることを書き足す。"Parent already contains us" を含む行は 1 行のまま残し、その次の行は `merge-base --is-ancestor` の確認のままにする。
- **FR5:** 内容ピンの更新。`tests/test_merge_unverified_exit_doc_contract.py` の `EXPECTED_MERGE_TASK_SH_SHA256` を、変更後の merge-task.sh の sha256 に同じコミットで更新し、直前のコメントの来歴列挙に本 feature を追記する。
- **FR6:** 隙間を突くテストの追加。`tests/test_merge_task_journal.py` に、ロック取得後のシンボリック参照の検査を通過した後、統合ブランチの値の取得より前に統合ブランチ参照をタスク参照へのシンボリック参照に差し替えるテストを追加する。差し替えは PATH に置いた git の仲介スクリプト（既存ヘルパ `_build_git_shim` に新しいモードを足す形）で、統合ブランチ参照を引数に含む最初の `show-ref` 呼び出しを捕まえ、本物の git に渡す前に行う。変更前の merge-task.sh ではこのテストが失敗する（exit 0 で merged が記録される）ことを確認する。

### Non-Functional Requirements
- **NFR1:** 既存挙動の維持。シンボリック参照でない通常の統合ブランチに対する既存の挙動（exit 0 / 1 / 2 の意味、already-contained・fast-forward・merge-commit の各経路、journal 追記、`already contained in` を含む stdout）は変えない。fast-forward 経路と merge-commit 経路のコードは変更しない。`tests/test_merge_task_journal.py` と `tests/test_merge_unverified_exit_doc_contract.py` の既存テストはすべて通る。
- **NFR2:** テストの実行形態。テストは標準ライブラリだけを使い、一時ディレクトリに作った使い捨ての git リポジトリで merge-task.sh をサブプロセスとして実行する（test/README.md）。
- **NFR3:** version を変更しない。プラグインの version は変更しない（core-plugin-version-bump）。
- **NFR4:** kill / pkill を使わない。テストでも実装でも kill / pkill / killall を使わない。ロック待機中の変更が必要な場合は既存ヘルパ `_run_merge_with_mutation_during_lock_wait` を使う。
- **NFR5:** 依存を増やさない。merge-task.sh の動作要件（git 2.40 以上、util-linux の flock）を増やさない。

## Implementation Approach

### Architecture

**System Architecture:**

該当なし（シェルスクリプトとテストのみの変更）。

**Component Diagram:**
```
merge-task.sh
  └─ already-contained 経路（"Parent already contains us"）
       merge-base --is-ancestor 成功
         → 再確認 (1) git symbolic-ref --quiet
         → 再確認 (2) git update-ref --no-deref（同値 CAS）
         → append_merged_event / MERGED: 出力

tests/test_merge_task_journal.py
  └─ _build_git_shim（新モードを追加）
tests/test_merge_unverified_exit_doc_contract.py
  └─ EXPECTED_MERGE_TASK_SH_SHA256（内容ピン）
```

### Data Flow

```
merge-base --is-ancestor 成功
  → git symbolic-ref --quiet "refs/heads/$PARENT_BRANCH"
       0         → ERROR 行（"symbolic ref"）→ exit 2
       0/1 以外  → ERROR 行（終了コード）→ exit 2
       1         → git update-ref --no-deref "refs/heads/$PARENT_BRANCH" "$PARENT" "$PARENT"
                      失敗 → ERROR 行（"update-ref"）→ exit 2
                      成功 → journal 追記（merged）→ MERGED: 出力
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- ロック取得後・値の取得前の既存のシンボリック参照の検査: 残す（参照先が無いシンボリック参照を "symbolic ref" として拒否するもの）
- `_build_git_shim`: 新しいモードを足す
- `_run_merge_with_mutation_during_lock_wait`: ロック待機中の変更が必要な場合に使う

**External Dependencies:**
- git: 2.40 以上（増やさない）
- util-linux の flock（増やさない）

### File Structure

```
merge-task.sh                                     # FR1〜FR4
tests/
├── test_merge_task_journal.py                    # FR6
└── test_merge_unverified_exit_doc_contract.py    # FR5
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/merge-task-already-contained-symref-recheck/**`
- `test-docs/merge-task-already-contained-symref-recheck/**`

`feature-docs/merge-task-already-contained-symref-recheck/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/merge-task-already-contained-symref-recheck/**` covers `test-docs/merge-task-already-contained-symref-recheck/{T}.tests.yaml`, the
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
- なし

### Integration Tests
- [ ] TS-1（AC-1）: `_build_git_shim` に新モードを足し、統合ブランチ参照を引数に含む最初の `show-ref` 呼び出しで、本物の git により `symbolic-ref refs/heads/<parent> refs/heads/em-workflow/feat/task0001` を実行してから元の呼び出しを渡す。タスクのコミットを持つ worktree で `_run_merge` を shim 付きの env で実行。exit 2、ERROR 行 1 行（PARENT_BRANCH と "symbolic ref" を含む）、journal なし、`MERGED:` なし、タスク参照の値は不変、`git symbolic-ref refs/heads/<parent>` はタスク参照を返す、捕捉回数は 1。変更前のスクリプトでは exit 0 と merged 記録になることを確認する
- [ ] TS-2（AC-2）: TS-1 の差し替えに加え、統合ブランチ参照を引数に含む 2 回目の `symbolic-ref` 呼び出し（already-contained 経路での再確認）の直前に、本物の git により `update-ref --no-deref refs/heads/<parent> <元の値>` で元の値の直接参照に戻してから元の呼び出しを渡す。exit 2、ERROR 行に PARENT_BRANCH と "update-ref"、journal なし、統合ブランチ参照は元の値の直接参照
- [ ] TS-3（AC-3）: 通常どおり 1 回マージしてから、統合ブランチ参照を引数に含む 2 回目の `symbolic-ref` 呼び出しだけを終了コード 128 で返す shim を付けて同じタスクを再実行する。exit 2、ERROR 行に PARENT_BRANCH と 128、journal の行は 1 行のまま
- [ ] TS-4（AC-4, AC-5）: 既存テスト一式（`python3 -m unittest tests.test_merge_task_journal tests.test_merge_unverified_exit_doc_contract`）と `python3 -m unittest discover -s tests` を実行して通る

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 再確認の同値 CAS が失敗する（統合ブランチ参照が消された、または値が変わった）: exit 2、journal 追記なし
- [ ] シンボリック参照を値の取得の前に置き、再確認の前に元の値の直接参照へ戻す: 同値 CAS の値の不一致で exit 2（TS-2）
- [ ] 再確認の symbolic-ref が判定できない終了コードを返す: exit 2（TS-3）
- [ ] 既存の "status" モードの shim（統合ブランチ参照へのすべての symbolic-ref を 128 で返す）は、ロック後の最初の検査で従来どおり拒否される

### Performance Tests
- なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** FR1 の再確認（シンボリック参照の再判定と同値 CAS）
- **Data Protection:** FR2（拒否時に journal と参照を書き換えない）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | Exit Status | User Message |
|------|-------------|-------------|--------------|
| シンボリック参照 | FR1 (1) の `git symbolic-ref --quiet` が終了コード 0（dangling を含む） | 2 | ERROR 行 1 行。PARENT_BRANCH と "symbolic ref" を含む |
| 判定できない終了コード | FR1 (1) の終了コードが 0 でも 1 でもない | 2 | ERROR 行 1 行。PARENT_BRANCH と終了コードを含む |
| 同値 CAS の失敗 | FR1 (2) の `git update-ref --no-deref` が失敗 | 2 | ERROR 行 1 行。PARENT_BRANCH と "update-ref" を含む |

いずれの ERROR 行も dirty worktree を示す文言（uncommitted / untracked / commit everything）を含まない。

### Error Flow

```
再確認で拒否 → stderr に ERROR 行 1 行 → journal 追記なし・MERGED: 出力なし → exit 2
```

## Performance Optimization

該当なし

## Assumptions

- 修正方式は、merged を記録する直前に、シンボリック参照の再判定（シンボリック参照なら exit 2）と、新値・旧値とも PARENT の同値 CAS（`update-ref --no-deref`）をこの順で行う方式を採る。値の読み直しと種別の判定を別々に行う方式は、読み直しまでシンボリック参照を維持し最後の判定の直前に未統合の直接参照へ戻す競合が残るため採らない。同値 CAS だけの方式は、シンボリック参照を黙って直接参照に置き換えて exit 0 にするため、検出時に fail-closed で止まる再判定を先に置く（バッチ実行で Codex と相談して決めた）
- 「1 回の読み取りで判定と値の取得を行う」案（for-each-ref の %(symref) と %(objectname) を 1 回で読む等）は採らない。Git 呼び出しが 1 回でも、更新を伴う原子的な検証と同じ保証にはならないため
- 同値 CAS は通常の直接参照では参照の値を変えない。ロックファイルの作成・削除と reference-transaction フックの実行は起こり得るものとして受容する。reflog の有無はテストで固定しない
- 再判定の後、同値 CAS より前に統合ブランチ参照を同じ値のシンボリック参照へ差し替えられた場合、同値 CAS がそれを直接参照に置き換えて成功し得る。このとき統合ブランチ参照はタスクを含む直接参照になるため、統合せずに merged が記録される状態にはならない。同値 CAS の後に統合ブランチ参照を書き換えられる場合は、マージ後に参照を書き換えられる場合と同じ扱いとし、範囲外とする（主体は参照を直接書き換えられる権限を既に持つ）
- fast-forward 経路と merge-commit 経路は変更しない。両経路は前 feature で update-ref に `--no-deref` が付いており、旧値と一致する差し替えでシンボリック参照が直接参照に置き換わり得る点は前 feature の受容済みの残存リスクのまま
- ロック取得後・値の取得前の既存のシンボリック参照の検査（参照先が無いシンボリック参照を "symbolic ref" として拒否するもの）は残す
- 前 feature `merge-task-parent-symref-reject` の SPEC.md（Assumptions）と THREAT-MODEL.md（Accepted residuals）は過去の記録として変更しない
- `em-workflow/references/implement-phase.md` の「統合ブランチが既にタスクブランチを含むとき merge-task.sh は merged を再記録する」旨の記述、`em-workflow/skills/worktree-task-workflow/SKILL.md` の exit code 分岐、`em-workflow/agents/implementer.md` は、通常の直接参照ではそのまま正しいため変更しない
- task_description の「追加指示」（remote への push と PR 作成、外部への相談とその記録）はワークフロー運用の指示として扱い、プロダクトの要件には含めない
- プラグインの version は変更しない

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1〜AC-5 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/merge-task-already-contained-symref-recheck/REQUIREMENTS.md`
- テストの実行形態: test/README.md
