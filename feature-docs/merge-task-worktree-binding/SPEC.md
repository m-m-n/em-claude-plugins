# Feature: merge-task-worktree-binding

要件定義書: `feature-docs/merge-task-worktree-binding/REQUIREMENTS.md`

## Overview

merge-task.sh がフィーチャーの統合ブランチにマージする HEAD を、指名されたタスク自身のワークツリーでチェックアウトされた、そのタスク自身のブランチに限る。レイアウトの外、統合ワークツリー、ブランチの不一致からの実行は、ロックと ref の更新より前に終了コード 2 で拒否する。終了コード 0 で終わる実行すべてに `merged` のジャーナルイベントが付く。

## Objectives

- merge-task.sh は、指名されたタスク自身のワークツリーでチェックアウトされた、そのタスク自身のブランチ以外の HEAD を、フィーチャーの統合ブランチにマージしない
- 終了コード 0 で終わる merge-task.sh の実行すべてに `merged` のジャーナルイベントが付く。失敗の検出がマージ済みのタスクを失敗として記録することはなく、統合ブランチが他の HEAD を黙って取り込むこともない

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** タスクのワークツリーのレイアウトの外からの実行を拒否する。cwd のワークツリーの最上位（`git rev-parse --show-toplevel`）が `.../em-workflow/{feature}/{TASK_ID}` に一致しない限り、merge-task.sh は stderr に `ERROR:` のメッセージを出して終了コード 2 で終わる。一致の条件は、最後のディレクトリが TASK_ID の引数と等しく `^task[0-9]+$` に一致すること、その親ディレクトリの名前が `^[a-z0-9][a-z0-9-]*$` に一致すること、祖父ディレクトリの名前が `em-workflow` であること。メインのワークツリー、フィーチャーの統合ワークツリー（`.../em-workflow/{feature}/integration`）、その他のレイアウトの外のパスはすべて拒否する。レイアウトの外でのマージだけの今の挙動は廃止する。
- **FR2:** 親ブランチはフィーチャーの統合ブランチでなければならない。レイアウトの中では、親ブランチの引数はワークツリーのパスから取った feature について `em-workflow/{feature}/integration` と等しくなければならない。等しくなければ終了コード 2。既存の判定で、今のまま保つ。
- **FR3:** チェックアウトされたブランチはタスクブランチでなければならない。レイアウトの中では、HEAD の `git symbolic-ref` は `refs/heads/em-workflow/{feature}/{TASK_ID}` でなければならない。HEAD が detached か、別のブランチがチェックアウトされていれば終了コード 2。
- **FR4:** 拒否はロック・マージ・ref の更新より前に行う。FR1〜FR3 の拒否はどれも、マージのロックを取る前、作業ツリーの清浄さの事前条件を確かめる前、merge-tree・commit-tree・update-ref のどれかを実行する前に行う。拒否したときは、どのブランチの ref も変えず、ジャーナルに何も追記しない。
- **FR5:** レイアウトの中の正しい実行は今の挙動を保つ。FR1〜FR3 を通ったとき、fast-forward、マージコミット、既に含まれる場合（"Parent already contains us" の場合。`merged` を再び追記する）、コンフリクト（終了コード 1）、その他の終了コード 2 の事前条件、ベストエフォートのジャーナルの追記とその失敗時の警告、並行するマージの直列化は、今とまったく同じに振る舞う。
- **FR6:** merge-task.sh 自身のコメントを更新する。レイアウトの外からの実行を許すと書いている merge-task.sh のヘッダと Identity-binding のコメント（'Outside the layout (manual invocation, merge-only tests) no binding applies'、手動の実行やマージだけのテストが追記を飛ばすと書いた append_merged_event のコメント）を、新しい拒否に合わせて更新する。
- **FR7:** 既に含まれる場合を行番号でなく名前で引用する。`em-workflow/references/implement-phase.md`（I.2.b）の引用 `(its "Parent already contains us" case, lines 116-118)` を、場合の名前（"Parent already contains us"）だけの引用に置き換える。`tests/test_merge_unverified_exit_doc_contract.py` の R2_MERGE_TASK_RECORDS_AGAIN_PHRASE をそれに合わせて更新する。`lines[115:118]` の範囲を切り出すテスト（`test_merge_task_sh_lines_116_118_still_the_cited_case`）を、merge-task.sh の中でその場合を名前で見つけ、`merge-base --is-ancestor` の判定と一緒にあることを確かめるテストに置き換える。EXPECTED_MERGE_TASK_SH_SHA256 を新しい merge-task.sh の内容に合わせて更新する。
- **FR8:** AC-5 のマージだけのテストを拒否のテストにする。`tests/test_merge_task_journal.py` の `test_no_journal_home_merge_succeeds_without_append_or_error`（レイアウトの外で終了コード 0 を期待する）を拒否のテストにする。レイアウトの外のワークツリーは終了コード 2 になり、親の ref は変わらず、journal.jsonl は存在しない。既存の再試行・再追記のテスト（`test_idempotent_already_merged_path_appends_merged_line_and_tolerates_duplicates`）はそのまま保つ。

### Non-Functional Requirements

- **NFR1 - 失敗側に倒す:** 最上位や symbolic-ref を解決できないときは拒否（終了コード 2）として扱い、マージの許可としては扱わない。
- **NFR2 - 終了コードの意味を保つ:** 終了コードの意味は今のまま（0 マージした / 1 コンフリクト / 2 その他のエラー）。新しい終了コードは足さない。
- **NFR3 - 標準ライブラリと使い捨てのリポジトリだけを使う:** テストは Python 標準ライブラリの `unittest` と、一時ディレクトリの使い捨ての git リポジトリだけを使う（test/README.md）。
- **NFR4 - version を変えない:** プラグインの version は変えない（.claude/rules/core-plugin-version-bump.md）。Actions のワークフローが patch を上げる。

### Assumptions

- **A1:** マージ元の束縛: cwd の最上位が `.../em-workflow/{feature}/{TASK_ID}` で、親ブランチが `em-workflow/{feature}/integration` でない限り、拒否する（終了コード 2、マージのロックとどの ref の更新よりも前）。メインのワークツリーと統合ワークツリーからの実行は拒否する。レイアウトの外でのマージだけの実行は廃止し、AC-5 のテストは拒否のテストになる。（answer requirement.merge-source-binding、reject_outside_task_worktree）
- **A2:** レイアウトの中では、チェックアウトされたブランチ（git symbolic-ref）が `refs/heads/em-workflow/{feature}/{TASK_ID}` でなければならない。detached HEAD や別のブランチはロックより前に終了コード 2 で終わる。（answer requirement.in-layout-branch-check、require_branch_match）
- **A3:** merge-task.sh の sha256 の固定値を更新する。行番号による引用（implement-phase.md の 'lines 116-118'、テストの文言、`lines[115:118]` の切り出し）を、場合の名前（'Parent already contains us'）による引用に置き換える。既存の再試行・再追記の挙動のテストは保つ。（answer requirement.pinned-merge-task-references、cite_by_case_name）
- **A4:** レイアウトの判定には、merge-task.sh が既に使っている最上位の形の判定（basename、feature の正規表現、祖父の名前が em-workflow）を使う。タスクのワークツリーのサブディレクトリからの実行は同じ最上位に解決され、受け付ける。（既存の merge-task.sh の identity binding）
- **A5:** implement-phase.md I.2.b の "Parent already contains us" の再試行の経路は「タスクの残したワークツリーで」実行するので、レイアウトの中にとどまり、`merged` を再追記し続ける。（implement-phase.md I.2.b）

## Implementation Approach

### Architecture

対象は merge-task.sh の判定の順序。FR1（レイアウト）、FR2（親ブランチ）、FR3（チェックアウトされたブランチ）の判定を、マージのロック・作業ツリーの清浄さの事前条件・merge-tree / commit-tree / update-ref より前に置く（FR4）。どれかに落ちたら stderr に `ERROR:` を出して終了コード 2 で終わる。判定を通った後の経路は今のまま（FR5）。

### Data Flow

```
merge-task.sh <parent-branch> <TASK_ID>
  → 最上位の解決（git rev-parse --show-toplevel）とレイアウトの判定（FR1、A4）   不一致・解決不能 → exit 2（NFR1）
  → 親ブランチの判定（FR2）                                                      不一致 → exit 2
  → HEAD の symbolic-ref の判定（FR3）                                           detached・不一致・解決不能 → exit 2（NFR1）
  → マージのロック → 事前条件 → マージ → `merged` の追記（FR5、今のまま）
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md` I.2.b: "Parent already contains us" の再試行の経路（A5）

**External Dependencies:**
- なし（NFR3）

### File Structure

```
merge-task.sh                                       # FR1〜FR6
em-workflow/references/implement-phase.md           # I.2.b の引用（FR7）
tests/test_merge_unverified_exit_doc_contract.py    # 文言・名前による場合の検出・sha256 の固定値（FR7）
tests/test_merge_task_journal.py                    # AC-5 のテストを拒否のテストに、拒否のテストの追加（FR8、TS1〜TS5）
```

## Declared Change Set

フィーチャー固有のパスは手で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリを既定で宣言する。

- `feature-docs/merge-task-worktree-binding/**`
- `test-docs/merge-task-worktree-binding/**`

`feature-docs/merge-task-worktree-binding/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、デザインステップが生成するデザイン成果物を含む。生成と所有は各フェーズドキュメントと `references/phase-state.md` にあり、この節は引用だけで、それらのルールを再掲しない。

`test-docs/merge-task-worktree-binding/**` はタスクごとのテスト記録 `test-docs/merge-task-worktree-binding/{T}.tests.yaml` を含む。生成と所有は `implement-phase.md` にあり、この節は引用だけで、そのルールを再掲しない。

この 2 つの既定のエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込み。

この宣言はスーパーセットの主張で、検証時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要があり、等しい必要は無い。implement タスクを生成しないフィーチャーは `test-docs/merge-task-worktree-binding/` を作らないが、宣言した `test-docs/merge-task-worktree-binding/**` はその場合も正しい。宣言したパスが生成されなくても違反ではない。

## Test Scenarios

### Unit Tests

`tests/test_merge_task_journal.py` と `tests/test_merge_unverified_exit_doc_contract.py` に置く。一時ディレクトリの使い捨ての git リポジトリを使う（NFR3）。

- [ ] TS1: 使い捨てのリポジトリで、メインのワークツリーに em-workflow/feat/integration に無いコミットを置く。メインのワークツリーを cwd にして `merge-task.sh em-workflow/feat/integration task0001` を実行する - 終了コード 2、stderr に ERROR、統合ブランチの ref は変わらず、journal.jsonl は無い（FR1, FR4, AC1）
- [ ] TS2: `.claude/worktrees/em-workflow/feat/integration` のワークツリーで統合ブランチをチェックアウトし、そこから merge-task.sh を実行する - 終了コード 2（旧来の「既に含まれる」の終了コード 0 ではない）、ref は変わらず、ジャーナルの行は無い（FR1, FR4, AC2）
- [ ] TS3: AC-5 のテストを書き換える: レイアウトの外のワークツリーにタスクのコミットを置いて実行する - 終了コード 2、親の ref は変わらず、一時ディレクトリの下のどこにも journal.jsonl は無い（FR1, FR4, FR8, AC3）
- [ ] TS4: レイアウトの中のタスクのワークツリーにコミットを置き、`git checkout --detach` して実行する - 終了コード 2、親の ref は変わらず、ジャーナルの行は無い（FR3, FR4, AC4）
- [ ] TS5: レイアウトの中のタスクのワークツリーで別のブランチをチェックアウトして（例: `git checkout -b other`）実行する - 終了コード 2、親の ref は変わらず、ジャーナルの行は無い（FR3, FR4, AC5）
- [ ] TS7: doc contract の文言のテストと、名前で場合を見つけるテスト - 更新後の implement-phase.md と merge-task.sh に対して通り、sha256 の固定値が新しい merge-task.sh と一致する（FR7, AC7）

### Integration Tests

- [ ] TS6: `tests/test_merge_task_journal.py` の既存のレイアウトの中のテスト（fast-forward、マージコミット、再追記を伴う冪等な既マージ、コンフリクト、事前条件のエラー、ジャーナルの書き込み失敗、並行するマージ、task id の不一致、親ブランチの不一致）を変更せずに再実行する - 通る（FR2, FR5, AC6）
- [ ] `python3 -m unittest discover -s tests` が通る（AC8）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS2: 親が既に HEAD を含む統合ワークツリーからの実行 - どの ref の更新よりも前に終了コード 2、ジャーナルの行は追記されない（AC2）
- [ ] NFR1: 最上位や symbolic-ref を解決できないとき - 終了コード 2
- [ ] A4: タスクのワークツリーのサブディレクトリからの実行 - 同じ最上位に解決され、受け付ける

### Performance Tests

該当なし

## Security Considerations

- **Input Validation:** cwd のワークツリーの最上位、親ブランチの引数、HEAD の symbolic-ref を、マージのロックとどの ref の更新よりも前に判定し、どれかが一致しなければ終了コード 2 で拒否する（FR1〜FR4）。解決できないときも拒否する（NFR1）。

## Error Handling

### Error Codes

| Code | Description |
|------|-------------|
| 0 | マージした（`merged` を追記する） |
| 1 | コンフリクト |
| 2 | その他のエラー。FR1〜FR3 の拒否、解決できない最上位や symbolic-ref（NFR1）、既存の事前条件 |

新しい終了コードは足さない（NFR2）。

### Error Flow

```
FR1〜FR3 の判定に落ちる → stderr に ERROR: → exit 2（ロック・ref の更新・ジャーナルの追記なし）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1: 再現: メインのワークツリーを cwd にして `merge-task.sh <integration-branch> <task-id>` を実行すると終了コード 2 で終わり、統合ブランチの ref は変わらず、`merge: <task-id>` のコミットは作られない
- [ ] AC2: 最上位が `.../em-workflow/{feature}/integration` のワークツリーを cwd にして実行すると、親が既に HEAD を含む場合も含めて、どの ref の更新よりも前に終了コード 2 で終わる。ジャーナルの行は追記されない
- [ ] AC3: レイアウトの外のタスクのワークツリー（旧 AC-5 のフィクスチャ）から実行すると終了コード 2 で終わり、親の ref は変わらず、journal.jsonl は作られない
- [ ] AC4: レイアウトの中で HEAD が detached のとき、終了コード 2 で終わり、親の ref は変わらず、ジャーナルの行は追記されない
- [ ] AC5: レイアウトの中で em-workflow/{feature}/{TASK_ID} 以外のブランチがチェックアウトされているとき、終了コード 2 で終わり、親の ref は変わらず、ジャーナルの行は追記されない
- [ ] AC6: `tests/test_merge_task_journal.py` の既存のレイアウトの中のテストが変更なしで通る
- [ ] AC7: implement-phase.md は既に含まれる場合を行番号なしで名前で引用する。`tests/test_merge_unverified_exit_doc_contract.py` は新しい merge-task.sh の sha256 を固定し、その場合を名前で見つける。どちらも通る
- [ ] AC8: `python3 -m unittest discover -s tests` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/merge-task-worktree-binding/REQUIREMENTS.md`
- `em-workflow/references/implement-phase.md`（I.2.b）
- test/README.md
- .claude/rules/core-plugin-version-bump.md
