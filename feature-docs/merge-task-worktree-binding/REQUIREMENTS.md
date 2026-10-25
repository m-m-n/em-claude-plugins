---
title: "merge-task-worktree-binding"
created_date: 2026-10-25
status: draft
---

# merge-task-worktree-binding - 要件定義書

## 1. 概要

### 1.1 背景
merge-task.sh は、指名されたタスク自身のワークツリーで、そのタスク自身のブランチがチェックアウトされている HEAD 以外も、フィーチャーの統合ブランチにマージできる。終了コード 0 で終わった実行に `merged` のジャーナルイベントが付かないこともある。

### 1.2 目的
- merge-task.sh がフィーチャーの統合ブランチにマージする HEAD を、指名されたタスク自身のワークツリーでチェックアウトされた、そのタスク自身のブランチに限る
- 終了コード 0 で終わる merge-task.sh の実行すべてに `merged` のジャーナルイベントが付くようにする

### 1.3 スコープ
- 対象: merge-task.sh（判定の追加と、自身のコメントの更新）、`em-workflow/references/implement-phase.md`（I.2.b の引用）、`tests/test_merge_unverified_exit_doc_contract.py`、`tests/test_merge_task_journal.py`
- 対象外: レイアウトの中で FR1〜FR3 を通った実行の挙動（FR5 で今のまま保つ）、終了コードの意味（NFR2）、プラグインの version（NFR4）

## 2. ビジネス要件

### 2.1 ビジネス目標
- merge-task.sh は、指名されたタスク自身のワークツリーでチェックアウトされた、そのタスク自身のブランチ以外の HEAD を、フィーチャーの統合ブランチにマージしない
- 終了コード 0 で終わる merge-task.sh の実行すべてに `merged` のジャーナルイベントが付く。失敗の検出がマージ済みのタスクを失敗として記録することはなく、統合ブランチが他の HEAD を黙って取り込むこともない

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 統合ブランチに他の HEAD が黙って取り込まれない
- マージ済みのタスクが失敗として記録されない

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | タスクのワークツリーのレイアウトの外からの実行を拒否する | cwd のワークツリーの最上位が `.../em-workflow/{feature}/{TASK_ID}` でなければ終了コード 2 |
| FR2 | 親ブランチはフィーチャーの統合ブランチでなければならない | 親ブランチの引数が `em-workflow/{feature}/integration` でなければ終了コード 2（既存の判定を保つ） |
| FR3 | チェックアウトされたブランチはタスクブランチでなければならない | HEAD の `git symbolic-ref` が `refs/heads/em-workflow/{feature}/{TASK_ID}` でなければ終了コード 2 |
| FR4 | 拒否はロック・マージ・ref の更新より前に行う | FR1〜FR3 の拒否はマージのロック、作業ツリーの清浄さの事前条件、merge-tree / commit-tree / update-ref より前 |
| FR5 | レイアウトの中の正しい実行は今の挙動を保つ | FR1〜FR3 を通った実行の各経路は今と同じ |
| FR6 | merge-task.sh 自身のコメントを更新する | レイアウトの外からの実行を許すと書いたコメントを新しい拒否に合わせる |
| FR7 | 既に含まれる場合を行番号でなく名前で引用する | implement-phase.md と doc contract のテストの行番号による引用を、場合の名前による引用にする |
| FR8 | AC-5 のマージだけのテストを拒否のテストにする | `test_no_journal_home_merge_succeeds_without_append_or_error` を拒否のテストにする |

### 4.2 機能詳細

#### FR1: タスクのワークツリーのレイアウトの外からの実行を拒否する

**説明**: cwd のワークツリーの最上位（`git rev-parse --show-toplevel`）が `.../em-workflow/{feature}/{TASK_ID}` に一致しない限り、merge-task.sh は stderr に `ERROR:` のメッセージを出して終了コード 2 で終わる。一致の条件は次のすべて。

- 最後のディレクトリが TASK_ID の引数と等しく、`^task[0-9]+$` に一致する
- その親ディレクトリの名前が `^[a-z0-9][a-z0-9-]*$` に一致する
- 祖父ディレクトリの名前が `em-workflow`

メインのワークツリー、フィーチャーの統合ワークツリー（`.../em-workflow/{feature}/integration`）、その他のレイアウトの外のパスはすべて拒否する。レイアウトの外でのマージだけの今の挙動は廃止する。

#### FR2: 親ブランチはフィーチャーの統合ブランチでなければならない

**説明**: レイアウトの中では、親ブランチの引数はワークツリーのパスから取った feature について `em-workflow/{feature}/integration` と等しくなければならない。等しくなければ merge-task.sh は終了コード 2 で終わる。これは既存の判定で、今のまま保つ。

#### FR3: チェックアウトされたブランチはタスクブランチでなければならない

**説明**: レイアウトの中では、HEAD の `git symbolic-ref` は `refs/heads/em-workflow/{feature}/{TASK_ID}` でなければならない。HEAD が detached か、別のブランチがチェックアウトされていれば、merge-task.sh は終了コード 2 で終わる。

#### FR4: 拒否はロック・マージ・ref の更新より前に行う

**説明**: FR1〜FR3 の拒否はどれも、マージのロックを取る前、作業ツリーの清浄さの事前条件を確かめる前、merge-tree・commit-tree・update-ref のどれかを実行する前に行う。拒否したときは、どのブランチの ref も変えず、ジャーナルに何も追記しない。

#### FR5: レイアウトの中の正しい実行は今の挙動を保つ

**説明**: FR1〜FR3 を通ったとき、次の経路は今とまったく同じに振る舞う。

- fast-forward
- マージコミット
- 既に含まれる場合（"Parent already contains us" の場合。`merged` を再び追記する）
- コンフリクト（終了コード 1）
- その他の終了コード 2 の事前条件
- ベストエフォートのジャーナルの追記と、その失敗時の警告
- 並行するマージの直列化

#### FR6: merge-task.sh 自身のコメントを更新する

**説明**: レイアウトの外からの実行を許すと書いている merge-task.sh のヘッダと Identity-binding のコメント（'Outside the layout (manual invocation, merge-only tests) no binding applies'、手動の実行やマージだけのテストが追記を飛ばすと書いた append_merged_event のコメント）を、新しい拒否に合わせて更新する。

#### FR7: 既に含まれる場合を行番号でなく名前で引用する

**説明**:
- `em-workflow/references/implement-phase.md`（I.2.b）の引用 `(its "Parent already contains us" case, lines 116-118)` を、場合の名前（"Parent already contains us"）だけの引用に置き換える。
- `tests/test_merge_unverified_exit_doc_contract.py` の R2_MERGE_TASK_RECORDS_AGAIN_PHRASE をそれに合わせて更新する。
- `lines[115:118]` の範囲を切り出すテスト（`test_merge_task_sh_lines_116_118_still_the_cited_case`）を、merge-task.sh の中でその場合を名前で見つけ、`merge-base --is-ancestor` の判定と一緒にあることを確かめるテストに置き換える。
- EXPECTED_MERGE_TASK_SH_SHA256 を新しい merge-task.sh の内容に合わせて更新する。

#### FR8: AC-5 のマージだけのテストを拒否のテストにする

**説明**: `tests/test_merge_task_journal.py` の `test_no_journal_home_merge_succeeds_without_append_or_error`（レイアウトの外で終了コード 0 を期待する）を拒否のテストにする。レイアウトの外のワークツリーは終了コード 2 になり、親の ref は変わらず、journal.jsonl は存在しない。既存の再試行・再追記のテスト（`test_idempotent_already_merged_path_appends_merged_line_and_tolerates_duplicates`）はそのまま保つ。

## 5. 非機能要件

### 5.1 安全性の要件
- NFR1: 失敗側に倒す。最上位や symbolic-ref を解決できないときは拒否（終了コード 2）として扱い、マージの許可としては扱わない。

### 5.2 互換性の要件
- NFR2: 終了コードの意味は今のまま（0 マージした / 1 コンフリクト / 2 その他のエラー）。新しい終了コードは足さない。

### 5.3 テストの要件
- NFR3: テストは Python 標準ライブラリの `unittest` と、一時ディレクトリの使い捨ての git リポジトリだけを使う（test/README.md）。

### 5.4 リリースの要件
- NFR4: プラグインの version は変えない（.claude/rules/core-plugin-version-bump.md）。Actions のワークフローが patch を上げる。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 解決できない最上位や symbolic-ref は拒否として扱う（NFR1）
- 終了コードの意味は変えず、新しい終了コードを足さない（NFR2）
- テストは標準ライブラリの `unittest` と一時ディレクトリの使い捨ての git リポジトリだけを使う（NFR3）

### 9.2 ビジネス上の制約
- プラグインの version は変えない（NFR4）

### 9.3 スケジュール制約
なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/merge-task-worktree-binding/**`
- `test-docs/merge-task-worktree-binding/**`

`feature-docs/merge-task-worktree-binding/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/merge-task-worktree-binding/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/merge-task-worktree-binding/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/merge-task-worktree-binding/` ディレクトリを生成しないが、宣言された `test-docs/merge-task-worktree-binding/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 再現: メインのワークツリーを cwd にして `merge-task.sh <integration-branch> <task-id>` を実行すると終了コード 2 で終わり、統合ブランチの ref は変わらず、`merge: <task-id>` のコミットは作られない（FR1, FR4）
- [ ] AC2: 最上位が `.../em-workflow/{feature}/integration` のワークツリーを cwd にして実行すると、親が既に HEAD を含む場合も含めて、どの ref の更新よりも前に終了コード 2 で終わる。ジャーナルの行は追記されない（FR1, FR4）
- [ ] AC3: レイアウトの外のタスクのワークツリー（旧 AC-5 のフィクスチャ）から実行すると終了コード 2 で終わり、親の ref は変わらず、journal.jsonl は作られない（FR1, FR4, FR8）
- [ ] AC4: レイアウトの中で HEAD が detached のとき、終了コード 2 で終わり、親の ref は変わらず、ジャーナルの行は追記されない（FR3, FR4）
- [ ] AC5: レイアウトの中で em-workflow/{feature}/{TASK_ID} 以外のブランチがチェックアウトされているとき、終了コード 2 で終わり、親の ref は変わらず、ジャーナルの行は追記されない（FR3, FR4）
- [ ] AC6: `tests/test_merge_task_journal.py` の既存のレイアウトの中のテスト（fast-forward、マージコミット、再追記を伴う冪等な既マージ、コンフリクト、事前条件のエラー、ジャーナルの書き込み失敗、並行するマージ、task id の不一致、親ブランチの不一致）が変更なしで通る（FR2, FR5）
- [ ] AC7: implement-phase.md は既に含まれる場合を行番号なしで名前で引用する。`tests/test_merge_unverified_exit_doc_contract.py` は新しい merge-task.sh の sha256 を固定し、その場合を名前で見つける。どちらも通る（FR7）
- [ ] AC8: `python3 -m unittest discover -s tests` が通る（FR1〜FR8）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
| ID | シナリオ | 対象 |
|----|----------|------|
| TS1 | 使い捨てのリポジトリで、メインのワークツリーに em-workflow/feat/integration に無いコミットを置く。メインのワークツリーを cwd にして `merge-task.sh em-workflow/feat/integration task0001` を実行する。終了コード 2、stderr の ERROR、統合ブランチの ref が変わらないこと、journal.jsonl が無いことを確かめる | AC1 |
| TS2 | `.claude/worktrees/em-workflow/feat/integration` のワークツリーで統合ブランチをチェックアウトし、そこから merge-task.sh を実行する。終了コード 2（旧来の「既に含まれる」の終了コード 0 ではない）、ref が変わらないこと、ジャーナルの行が無いことを確かめる | AC2 |
| TS3 | AC-5 のテストを書き換える: レイアウトの外のワークツリーにタスクのコミットを置く。終了コード 2、親の ref が変わらないこと、一時ディレクトリの下のどこにも journal.jsonl が無いことを確かめる | AC3 |
| TS4 | レイアウトの中のタスクのワークツリーにコミットを置き、`git checkout --detach` する。終了コード 2、親の ref が変わらないこと、ジャーナルの行が無いことを確かめる | AC4 |
| TS5 | レイアウトの中のタスクのワークツリーで別のブランチをチェックアウトする（例: `git checkout -b other`）。終了コード 2、親の ref が変わらないこと、ジャーナルの行が無いことを確かめる | AC5 |
| TS6 | 既存のレイアウトの中のテストを変更せずに再実行する | AC6 |
| TS7 | doc contract の文言のテストと、名前で場合を見つけるテストが、更新後の implement-phase.md と merge-task.sh に対して通る。sha256 の固定値が新しい merge-task.sh と一致する | AC7 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| レイアウト | ワークツリーの最上位が `.../em-workflow/{feature}/{TASK_ID}` の形であること（FR1 の 3 条件） |
| 統合ブランチ | `em-workflow/{feature}/integration` |
| タスクブランチ | `em-workflow/{feature}/{TASK_ID}` |
| 既に含まれる場合 | merge-task.sh の "Parent already contains us" の場合 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] マージ元の束縛（answer requirement.merge-source-binding、reject_outside_task_worktree）: A1 として記録
- [x] レイアウトの中のブランチの判定（answer requirement.in-layout-branch-check、require_branch_match）: A2 として記録
- [x] 固定された merge-task.sh への参照（answer requirement.pinned-merge-task-references、cite_by_case_name）: A3 として記録
- [x] デザインステップ: シェルスクリプトの判定とテストと文書の文言の変更で、UI が無いため省略

### 14.2 未確認・保留事項

以下は前提として置いた事項（いずれも reversible）。

- [ ] A1: マージ元の束縛: cwd の最上位が `.../em-workflow/{feature}/{TASK_ID}` で、親ブランチが `em-workflow/{feature}/integration` でない限り、拒否する（終了コード 2、マージのロックとどの ref の更新よりも前）。メインのワークツリーと統合ワークツリーからの実行は拒否する。レイアウトの外でのマージだけの実行は廃止し、AC-5 のテストは拒否のテストになる。（answer requirement.merge-source-binding、reject_outside_task_worktree）
- [ ] A2: レイアウトの中では、チェックアウトされたブランチ（git symbolic-ref）が `refs/heads/em-workflow/{feature}/{TASK_ID}` でなければならない。detached HEAD や別のブランチはロックより前に終了コード 2 で終わる。（answer requirement.in-layout-branch-check、require_branch_match）
- [ ] A3: merge-task.sh の sha256 の固定値を更新する。行番号による引用（implement-phase.md の 'lines 116-118'、テストの文言、`lines[115:118]` の切り出し）を、場合の名前（'Parent already contains us'）による引用に置き換える。既存の再試行・再追記の挙動のテストは保つ。（answer requirement.pinned-merge-task-references、cite_by_case_name）
- [ ] A4: レイアウトの判定には、merge-task.sh が既に使っている最上位の形の判定（basename、feature の正規表現、祖父の名前が em-workflow）を使う。タスクのワークツリーのサブディレクトリからの実行は同じ最上位に解決され、受け付ける。（既存の merge-task.sh の identity binding）
- [ ] A5: implement-phase.md I.2.b の "Parent already contains us" の再試行の経路は「タスクの残したワークツリーで」実行するので、レイアウトの中にとどまり、`merged` を再追記し続ける。（implement-phase.md I.2.b）

## 15. 参考資料

- `em-workflow/references/implement-phase.md`（I.2.b）
- test/README.md
- .claude/rules/core-plugin-version-bump.md
