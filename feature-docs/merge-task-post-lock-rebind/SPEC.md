# Feature: merge-task-post-lock-rebind

## Overview

merge-task.sh は、マージのロックを取った後に HEAD の symbolic-ref をもう一度読み、ロックを待つ前に確かめたタスクブランチ（`IB_EXPECTED_REF`）と一致しなければ終了コード 2 で拒否する。マージ元の HEAD_SHA は `HEAD` でなく `IB_EXPECTED_REF` から読む。ロックを待つ間にワークツリーのチェックアウトが変わっても、マージするのは確かめたタスクブランチだけになる。

## Objectives

- merge-task.sh は、ロックを待つ間にワークツリーのチェックアウトが変わっても、確かめたタスクブランチだけをマージする
- 終了コード 0 で終わるマージにはすべて `merged` のジャーナルイベントが付き、拒否した実行はどれも統合ブランチの ref とジャーナルを変えない

## User Stories

該当なし

## Technical Requirements

### Functional Requirements

- **FR1:** ロックより前の identity binding を保つ。マージのロックより前の既存の判定（ワークツリーのレイアウト、TASK_ID の一致、親ブランチの一致、HEAD の symbolic-ref が IB_EXPECTED_REF と等しいこと）は変えずに残し、今のまま終了コード 2 で終わり、今のままロックを取る前に行う。
- **FR2:** ロックの後に symbolic-ref を確かめ直す。マージのロックの flock が成功したら、merge-task.sh は `git symbolic-ref --quiet HEAD` をもう一度読む。結果が IB_EXPECTED_REF でなければ（別のブランチ、detached HEAD、解決できない HEAD）、stderr に `ERROR:` の行を出して終了コード 2 で終わる。`ERROR:` の行には、期待した ref と見つけた ref の両方を書く（または HEAD が detached か解決できないことを書く）。この判定は merge-tree・commit-tree・update-ref のどれよりも前、ジャーナルへのどの追記よりも前に行う。
- **FR3:** 確かめ直す順序。ロックの後の確かめ直しは flock の直後、作業ツリーの清浄さ（`git status --porcelain`）の判定より前に行う。ブランチが変わり、作業ツリーも汚れているときは、作業ツリーのエラーでなく identity の拒否を報告する。
- **FR4:** マージ元を確かめたタスクの ref から読む。HEAD_SHA は `HEAD` でなく、確かめたタスクブランチの ref（`IB_EXPECTED_REF`）から読む。解決できなければ終了コード 2 で終わる。既に含まれる場合、fast-forward、マージコミットの経路はすべてこの値を使う。
- **FR5:** コメントを更新する。merge-task.sh のコメントを、ロックの後の確かめ直しと HEAD_SHA の読み元に合わせて更新する。対象は、拒否がマージのロックより前に終わると書いたヘッダの段落、identity binding のブロックのコメント、並行性の注記。次の固定された性質を保つ: 'Parent already contains us' を含む行はちょうど 1 行で、その次の行に `merge-base --is-ancestor` の判定がある。どのコメントにも 'manual invocation'、'merge-only'、'exercising only merge' を含めない。
- **FR6:** 内容の固定値をスクリプトに合わせる。`tests/test_merge_unverified_exit_doc_contract.py` の EXPECTED_MERGE_TASK_SH_SHA256 を、変更後の merge-task.sh の sha256 にする。スクリプトを変えるのと同じコミットで行う。
- **FR7:** ロックの後のブランチの切り替えの回帰テスト。`tests/test_merge_task_journal.py` に次の手順のテストを足す。(1) テストのプロセスがマージのロックを持つ。(2) マージするコミットがあるタスクブランチのタスクのワークツリーから、merge-task.sh をテスト自身の子プロセスとして起動する。(3) 単調時計で約 10 秒の期限まで /proc を見て、merge-task.sh のプロセスの直接の子で comm が 'flock' のものが現れるのを待つ。現れなければテストを失敗にする。(4) ワークツリーを別のブランチに切り替える。(5) ロックを放す。(6) 時間の上限つきで実行の終了を待つ。確かめること: 終了コード 2、期待した ref と切り替え先の ref の両方を書いた ERROR、統合ブランチの ref は変わらない、'merge: <task_id>' のコミットは無い、journal.jsonl は無い。どの失敗の経路でも、ロックを放し、起動した子プロセス（テスト自身の子だけ）を止めて回収する。

### Non-Functional Requirements

- **NFR1 - 失敗側に倒す:** ロックの後の HEAD やタスクの ref を解決できないときは、終了コード 2 で拒否する。マージには進まない。
- **NFR2 - インターフェースを変えない:** 使い方、引数、終了コードの意味（0/1/2）、`MERGED:` / `CONFLICT:` / `ERROR:` の出力形式、ジャーナルの行の形式は変えない。merge-task.sh に新しい環境変数、テスト用のフック、引数を足さない。
- **NFR3 - 決定的で上限のあるテスト:** 回帰テストは標準ライブラリの unittest と、一時ディレクトリの使い捨ての git リポジトリだけを使う。同期を短い sleep に頼らず、単調時計で約 10 秒の期限まで /proc を見て flock の子を待つ。実行の終了を待つ時間には上限がある。子プロセスはテスト自身の subprocess のハンドルで終わらせ（パターンによる kill / pkill は使わない）、ロックは必ず放す。
- **NFR4 - version を変えない:** このフィーチャーではプラグインの version を変えない。push のときに Actions が patch を上げる。

### Assumptions

- **A1:** ロックを待つ間に同じタスクブランチに新しいコミットが入ったときは、それもマージする（確かめたブランチの先端なので）。このフィーチャーが扱うのはブランチの取り違えだけ。
- **A2:** ロックの後に確かめ直すのは symbolic-ref だけ。最上位、レイアウト、TASK_ID、親ブランチの判定はロックの後に繰り返さない。
- **A3:** 作業ツリーの清浄さの判定は今のチェックアウトを見る。確かめ直しの後に切り替えがあっても、HEAD_SHA は IB_EXPECTED_REF から読むので、マージする内容は変わらない。
- **A4:** テストスイートは /proc のある Linux のホストで走る。merge-task.sh が既に util-linux の flock を前提にしているのと同じ。回帰テストは /proc の無いホスト向けの skip を足さない。
- **A5:** `tests/test_merge_unverified_exit_doc_contract.py` の既存の固定（'Parent already contains us' の 1 行とその次の行の `merge-base --is-ancestor` の判定、レイアウトの外を許す文言が無いこと）はそのまま保つ。

## Implementation Approach

### Architecture

対象は merge-task.sh の判定の順序とマージ元の読み方。ロックより前の判定（FR1）は今のまま残す。flock の直後、作業ツリーの清浄さの判定より前に HEAD の symbolic-ref を確かめ直す（FR2、FR3）。HEAD_SHA は IB_EXPECTED_REF から読み、既に含まれる場合・fast-forward・マージコミットの経路はすべてこの値を使う（FR4）。

### Data Flow

```
merge-task.sh <parent-branch> <TASK_ID>
  → ロックより前の identity binding（FR1、今のまま）                     不一致 → exit 2
  → マージのロック（flock）
  → HEAD の symbolic-ref を確かめ直す（FR2、FR3、A2）                     別のブランチ・detached・解決不能 → exit 2（NFR1）
  → 作業ツリーの清浄さ（git status --porcelain）
  → HEAD_SHA を IB_EXPECTED_REF から読む（FR4、A3）                       解決不能 → exit 2（NFR1）
  → 既に含まれる / fast-forward / マージコミット → `merged` の追記
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- なし

**External Dependencies:**
- util-linux の flock と /proc のある Linux のホスト（A4）

### File Structure

```
merge-task.sh                                       # FR2〜FR5
tests/test_merge_unverified_exit_doc_contract.py    # sha256 の固定値（FR6）
tests/test_merge_task_journal.py                    # ロックの後のブランチの切り替えの回帰テスト（FR7、TS1、TS2）
```

## Declared Change Set

フィーチャー固有のパスは手で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリを既定で宣言する。

- `feature-docs/merge-task-post-lock-rebind/**`
- `test-docs/merge-task-post-lock-rebind/**`

`feature-docs/merge-task-post-lock-rebind/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、デザインステップが生成するデザイン成果物を含む。生成と所有は各フェーズドキュメントと `references/phase-state.md` にあり、この節は引用だけで、それらのルールを再掲しない。

`test-docs/merge-task-post-lock-rebind/**` はタスクごとのテスト記録 `test-docs/merge-task-post-lock-rebind/{T}.tests.yaml` を含む。生成と所有は `implement-phase.md` にあり、この節は引用だけで、そのルールを再掲しない。

この 2 つの既定のエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込み。

この宣言はスーパーセットの主張で、検証時に観測した実際の変更集合は宣言に含まれる（CONTAINED IN）必要があり、等しい必要は無い。implement タスクを生成しないフィーチャーは `test-docs/merge-task-post-lock-rebind/` を作らないが、宣言した `test-docs/merge-task-post-lock-rebind/**` はその場合も正しい。宣言したパスが生成されなくても違反ではない。

## Test Scenarios

### Unit Tests

`tests/test_merge_task_journal.py` と `tests/test_merge_unverified_exit_doc_contract.py` に置く。一時ディレクトリの使い捨ての git リポジトリを使う（NFR3）。

- [ ] TS1: ロックの後のブランチの切り替えを拒否する。テストのプロセスがマージのロックを持つ。コミット済みの変更があるタスクのワークツリーから merge-task.sh を Popen で起動し、/proc を見て（期限は約 10 秒）そのプロセスの直接の子で comm が 'flock' のものを待つ。ワークツリーで `git checkout -q -b <other>` を実行し、ロックを放し、時間の上限つきで終了を待つ。どの失敗の経路でも、ロックを放し、子プロセスを自身のハンドルで止めて wait する - 終了コード 2、stderr の ERROR に `refs/heads/em-workflow/feat/<task>` と `refs/heads/<other>` を含む、`_assert_rejected_without_side_effects` が成り立つ。修正前は、ロックより前の判定を通った後で新しい HEAD をマージし、`merged` を追記する（FR2, FR7, NFR1, AC-1）
- [ ] TS2: ロックの後は作業ツリーの汚れより identity の拒否を優先する。TS1 と同じ手順で、切り替えの後、ロックを放す前に追跡されていないファイルを作る - 終了コード 2 で identity の ERROR。作業ツリーのエラーの文言は無い。マージもジャーナルも無い。修正前は作業ツリーのエラーを報告する（FR3, AC-2）
- [ ] TS4: 内容の固定値とコメントの契約。固定値を更新した `tests/test_merge_unverified_exit_doc_contract.py` を実行する - すべて通る（FR5, FR6, AC-5）

### Integration Tests

- [ ] TS3: 既存のマージと拒否の挙動を変えない。既存の `tests/test_merge_task_journal.py` のスイートを実行する - すべて通る（FR1, FR4, NFR2, AC-3, AC-4）
- [ ] `python3 -m unittest discover -s tests` がリポジトリのルートから通る（NFR3, AC-6）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS2: ロックの後にブランチが変わり、作業ツリーも汚れている - identity の拒否を報告する（FR3）
- [ ] NFR1: ロックの後の HEAD、またはタスクの ref を解決できない - 終了コード 2、マージには進まない
- [ ] A1: ロックを待つ間に同じタスクブランチに新しいコミットが入る - それもマージする

### Performance Tests

該当なし

## Security Considerations

- **Input Validation:** マージのロックの後、作業ツリーの清浄さの判定とどの ref の更新よりも前に HEAD の symbolic-ref を IB_EXPECTED_REF と照らし、一致しなければ終了コード 2 で拒否する（FR2、FR3）。解決できないときも拒否する（NFR1）。マージ元は IB_EXPECTED_REF から読む（FR4）。

## Error Handling

### Error Codes

| Code | Description |
|------|-------------|
| 0 | マージした（`merged` を追記する） |
| 1 | コンフリクト |
| 2 | その他のエラー。ロックより前の拒否（FR1）、ロックの後の symbolic-ref の不一致（FR2）、解決できない HEAD やタスクの ref（FR4、NFR1）、既存の事前条件 |

終了コードの意味と出力形式は変えない（NFR2）。

### Error Flow

```
ロックの後の symbolic-ref の判定に落ちる → stderr に ERROR:（期待した ref と見つけた ref） → exit 2（merge-tree・commit-tree・update-ref・ジャーナルの追記なし）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC-1: merge-task.sh がマージのロックを待つ間にタスクブランチを別のブランチに切り替えると、実行は終了コード 2 で終わり、期待した ref と切り替え先の ref の両方を書いた ERROR を出す。統合ブランチの ref は変わらず、'merge: <task_id>' のコミットは無く、journal.jsonl は無い
- [ ] AC-2: ブランチを切り替え、切り替えの後に追跡されていないファイルがあるとき、ロックの後の拒否は作業ツリーのエラーでなく identity の不一致を報告する
- [ ] AC-3: HEAD_SHA は IB_EXPECTED_REF から解決する。`tests/test_merge_task_journal.py` の既存の fast-forward、マージコミット、既に含まれる場合、コンフリクト、並行するマージのテストが変更なしで通る
- [ ] AC-4: 既存のロックより前の拒否のテスト（マージのロックを持ち、LOCKED_RUN_BOUND_SECONDS 以内の拒否を求めるテストを含む）が変更なしで通る
- [ ] AC-5: `tests/test_merge_unverified_exit_doc_contract.py` が通る。内容の固定値が新しい merge-task.sh と一致し、'Parent already contains us' はちょうど 1 行にあってその次の行に `merge-base --is-ancestor` があり、レイアウトの外を許す文言はどれも無い
- [ ] AC-6: `python3 -m unittest discover -s tests` がリポジトリのルートから通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- `tests/test_merge_task_journal.py`
- `tests/test_merge_unverified_exit_doc_contract.py`
