# Feature: prelaunch-inprogress-routeback

## 概要

`em-workflow/references/implement-phase.md` の Step I.2.a で、launch-state の capture / refresh / write / commit を承認ゲートと `Task()` 起動ループの後ろへ移し、journal で起動を確認できたタスクだけを `in_progress` としてコミットする。起動前に中断したタスクの `in_progress` がブランチに残らないようにし、Step I.2.c の route-back を恒久的にブロックしないようにする。要件は `REQUIREMENTS.md` を参照する。

## 目的

- 起動前に中断したタスクの in_progress 残骸が、Step I.2.c の route-back を恒久的にブロックしないこと
- 再発を検出するテストがあること

## ユーザーストーリー

該当なし

## 技術要件

### 機能要件

- **FR1:** I.2.a の launch-state 書き込みを承認ゲートと起動ループの後ろへ移す。em-workflow/references/implement-phase.md の Step I.2.a で、capture / refresh / write / commit の 4 段シーケンスを、project_commands 承認ゲートと Task() 起動ループの後ろへ移す。I.2.a の流れは、タスク選択、worktree 作成（resume guard を含む）、承認ゲート、Task() 起動ループ、journal の読み直し、capture、refresh、write、commit、ターン終了の順になる。4 段の相対順序（capture→refresh→write→commit）、refresh の対象がブランチ名 `em-workflow/{feature}/integration` であること、commit-docs.sh の第 3 引数が `"$LAUNCH_TIP"` であること、entry ごとに 1 回（refill の再入を含む）であること、`$RECONCILE_TIP` を再利用しないことは変えない。
- **FR2:** 起動を確認できたタスクだけを in_progress としてコミットする。write set の対象は、この entry で選択したタスクのうち、起動ループ後に読み直した journal で起動（launched）を確認できたタスクに限る。対象タスクには `tasks.{T}.status = in_progress` と `tasks.{T}.branch` を書く。起動を確認できなかったタスク（承認ゲートで止まった、起動ガードに拒否された、Task() を発行していない）は書かず、workflow.yaml 上は pending のまま残す。一部だけ起動できた場合も、確認できた集合で 1 つの write set・1 回のコミットにし、コミットメッセージにはその集合のタスクを並べる。
- **FR3:** 起動ゼロのときはコミットを省略し、ターンはコミット処理の後に終える。起動を確認できたタスクが 0 件なら、write とコミットを省略する。ターンの終了は「起動直後」ではなく、このコミット処理（または省略）の後に移す。--batch 実行でターンの最後のメッセージを batch-mode.md のマーカー行だけにする規則は変えない。
- **FR4:** コミット時と exit 4 再試行時に journal を読み直し、終端タスクを in_progress に戻さない。通常のコミットでも exit 4 の再試行でも、write set を作る直前に最新の journal を読み直す。既に終端（merged / failed）に達したタスクには in_progress を書かない。exit 4 の回数制限（1 回再試行、2 回目で停止）は既存の Branch & Worktree Model の規則に従う。2 回目の exit 4 で停止する場合も、journal の起動記録と、タスクの worktree・ブランチは保持し、削除も巻き戻しもしない。停止レポートにはコール箇所と対象タスクを記す。
- **FR5:** 『pending と launched の組み合わせは決して生じない』文を事実に合わせて書き直す。Step I.2.a にある、workflow.yaml の `status: pending` と journal 最終イベント `launched` の組み合わせは決して生じない（"can never arise."）という文を書き直す。この組み合わせは、起動からコミットまでの間と、コミットに至らなかった場合（中断、または 2 回目の exit 4）に生じうる。生じた場合は、journal 最終イベントが launched のタスクを workflow.yaml の status によらず in-flight とする既存規則で扱われる、と書く。recycled-task-id carve-out が failed にだけ適用されること、launched の in-flight 文、recursion invariant 文（pending のタスクが merged の journal 最終イベントを引き継ぐことはない）は残す。
- **FR6:** 再発検出テストの追加と、古い文を固定しているテストの修正。tests/ 配下に、FR1〜FR5 を implement-phase.md の文面で検査するテストを追加する。古い文を固定している既存テストは新しい文に合わせて直す。対象は tests/test_routeback_reset_scope_consistency.py の "can never arise." アンカーを使うテスト（test_i2a_unreachability_sentence_present_and_terminates_correctly、test_recursion_invariant_placed_after_unreachability_terminal）と、同じ文を参照していれば tests/test_recycled_task_id_consistency.py。

### 非機能要件

- **NFR1 - I.2.c と exit-4 証明の文言を変えない:** Step I.2.c の route-back ゲート（merged 半分、in_progress 半分、第 3 条件）、リセット集合、掃除対象、Branch & Worktree Model の exit-4 recovery bullet（呼び出し箇所の列挙と到達不能性の証明を含む）の文言を変えない。
- **NFR2 - 変更範囲:** 変更するのは em-workflow/references/implement-phase.md と tests/ 配下だけとする。フック（queue_launch_guard.py、queue_stop_guard.py など）とスクリプトの挙動は変えない。
- **NFR3 - テストスイート:** `python3 -m unittest discover -s tests` が全件 green になる。既存テストの修正は、変更した文面への追従に限る。
- **NFR4 - テストの形式:** 新しいテストは test/README.md の規約に従う。標準ライブラリの unittest だけを使い、repository root の tests/ 配下に test_*.py として置く。

## 実装方針

### アーキテクチャ

**Step I.2.a の流れ（FR1）:**
```
タスク選択
  → worktree 作成（resume guard を含む）
  → project_commands 承認ゲート
  → Task() 起動ループ
  → journal の読み直し
  → capture   LAUNCH_TIP=$(git -C {integration_worktree} rev-parse em-workflow/{feature}/integration)
  → refresh   ブランチ名 em-workflow/{feature}/integration
  → write     起動を確認できたタスクだけ tasks.{T}.status = in_progress / tasks.{T}.branch
  → commit    commit-docs.sh（第 3 引数 "$LAUNCH_TIP"）
  → ターン終了
```

**コンポーネント:**
```
Task() 起動ループ ──(PreToolUse)──> queue_launch_guard.py ──> journal（launched を記録）
journal の読み直し ──> 起動を確認できたタスクの集合 ──> write set ──> commit-docs.sh
```

### データフロー

```
journal 最終イベント
  launched        → write set に含める（終端でないもの）
  merged / failed → write set に含めない（終端、FR4）
  イベント無し    → write set に含めない（workflow.yaml 上は pending のまま、FR2）

起動を確認できたタスク 0 件 → write とコミットを省略 → ターン終了（FR3）
起動を確認できたタスク 1 件以上 → 1 つの write set・1 回のコミット → ターン終了（FR2、FR3）
```

### API 設計

該当なし

### データベーススキーマ

該当なし

### 依存関係

**内部依存:**
- queue_launch_guard.py: 起動ループの後に読み直す journal の launched イベントを記録する。挙動は変えない（NFR2）
- queue_stop_guard.py: journal 最終イベントが launched のタスクを in-flight とする既存規則を持つ。挙動は変えない（NFR2）
- commit-docs.sh: 第 3 引数 `"$LAUNCH_TIP"` で呼び出す。exit 4 の扱いは Branch & Worktree Model の規則に従う（FR1、FR4）
- Step I.2.c: route-back ゲート、リセット集合、掃除対象の文言は変えない（NFR1）

**外部依存:**
- なし

### ファイル構成

```
em-workflow/references/
└── implement-phase.md                          # Step I.2.a を変更（FR1〜FR5）
tests/
├── test_*.py                                   # 新規: FR1〜FR5 の文面検査（FR6）
├── test_routeback_reset_scope_consistency.py   # "can never arise." アンカーのテストを修正（FR6）
├── test_recycled_task_id_consistency.py        # 同じ文を参照していれば修正（FR6）
├── test_exit4_tip_argument_consistency.py      # 修正なし（AC2）
└── test_implement_routeback_gate.py            # 修正なし（AC7）
```

## 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/prelaunch-inprogress-routeback/**`
- `test-docs/prelaunch-inprogress-routeback/**`

`feature-docs/prelaunch-inprogress-routeback/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/prelaunch-inprogress-routeback/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/prelaunch-inprogress-routeback/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## テストシナリオ

### ユニットテスト

- [ ] TS1（AC1、AC2 / FR1）: I.2.a の節で、承認ゲート、Task() 起動ループ、LAUNCH_TIP の capture、refresh、write、commit の位置が、この順に厳密に増えていくことを検査する。
- [ ] TS2（AC3 / FR2）: write の対象が起動を確認できたタスクに限られ、選択した全タスクではないことを、文面で検査する。部分起動のときの扱いと、起動していないタスクを pending のまま残すことも検査する。
- [ ] TS3（AC4 / FR3）: 起動ゼロのときのコミット省略と、ターン終了がコミットの後であることを検査する。「起動直後にターンを終える」記述が無いことも検査する。
- [ ] TS4（AC5 / FR4）: exit 4 の再試行で journal を読み直すこと、終端タスクを除くこと、2 回目の exit 4 で停止するときに起動記録と worktree を保持することを検査する。
- [ ] TS5（AC6 / FR5）: "can never arise." の主張が I.2.a から消え、置き換えの文があり、recursion invariant 文が残っていることを検査する（tests/test_routeback_reset_scope_consistency.py の修正を含む）。
- [ ] TS6（AC8 / FR6、NFR3、NFR4）: 変更前の I.2.a の文面サンプルに対して、TS1〜TS3 の matcher が失敗することを確かめる（negative proof）。

### 結合テスト

- [ ] TS7（AC7 / NFR1）: 既存の tests/test_implement_routeback_gate.py と tests/test_exit4_tip_argument_consistency.py を回帰ガードとして実行し、修正なしで通ることを確かめる。

### E2E テスト

**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

### エッジケース

- [ ] 一部だけ起動できた: 起動を確認できた集合で 1 つの write set・1 回のコミットにする。起動を確認できなかったタスクは pending のまま残す（FR2）
- [ ] 起動ゼロ: write とコミットを省略し、その後にターンを終える（FR3）
- [ ] exit 4 の再試行時点で終端（merged / failed）に達したタスクがある: 読み直した journal に基づき、そのタスクを write set から除く（FR4）
- [ ] 2 回目の exit 4: 停止する。journal の起動記録と、タスクの worktree・ブランチは保持し、削除も巻き戻しもしない（FR4）

### パフォーマンステスト

該当なし

## セキュリティ考慮事項

該当なし

## エラー処理

### エラーコード

| コード | 説明 | 対応 |
|--------|------|------|
| commit-docs.sh exit 4（1 回目） | launch-state のコミットが exit 4 で失敗した | 最新の journal を読み直し、終端タスクを除いた write set で 1 回再試行する（FR4） |
| commit-docs.sh exit 4（2 回目） | 再試行も exit 4 で失敗した | 停止する。journal の起動記録と、タスクの worktree・ブランチは保持する。停止レポートにコール箇所と対象タスクを記す（FR4） |

### エラーフロー

```
commit-docs.sh exit 4 → journal の読み直し → 終端タスクを除いた write set → 再試行
再試行で exit 4 → 停止（起動記録・worktree・ブランチを保持） → 停止レポート（コール箇所、対象タスク）
```

## パフォーマンス最適化

該当なし

## 前提

- queue_launch_guard.py（PreToolUse）は、許可した起動を Task() 呼び出しが進む時点で journal に launched として記録する唯一の書き手である。そのため、起動ループの後に journal を読み直せば、起動の成否を確認できる（implement-phase.md I.2.a 末尾の記述による）。
- journal 最終イベントが launched のタスクは、workflow.yaml の status によらず in-flight とする既存規則（I.2.a、I.2.b step 1、queue_stop_guard.py）は変えない。起動からコミットまでの間の pending + launched の状態は、この規則で扱われる。
- この変更より前の実行で既にブランチにコミットされた in_progress の残骸は修復しない。I.2.c のゲートを変えないことが回答で決まっているため。
- Step I.2.c の route-back ゲート、リセット集合、掃除対象、exit-4 到達不能性の証明は変えない（回答で指定）。

## 対象外

- queue_launch_guard を fail-closed にすること（launched の記録に失敗したら起動を拒否する）。フックの挙動変更でスコープが広がるため、残るリスクとして別タスクに起票する。ガードが fail-open で launched を記録しないまま実装者が動いた場合、そのタスクは pending かつ journal にイベントが無い状態になる。このとき再選択による二重起動の余地が残る。
- Step I.2.c のゲートへの除外規定（選択肢 a: routeback_gate_carve_out）。採用しなかった。
- I.1 / I.2.b / I.2.c の他の呼び出し箇所の capture 方式の移行（既存の Idiom split 記述が別件として扱っているもの）。

## 成功基準

- [ ] AC1（FR1）: Step I.2.a の節の中で、承認ゲートの記述と Task() 起動ループの記述が、LAUNCH_TIP の capture より前にある。
- [ ] AC2（FR1）: capture（`LAUNCH_TIP=$(git -C {integration_worktree} rev-parse em-workflow/{feature}/integration)`）、ブランチ名への refresh、`tasks.{T}.status = in_progress` / `tasks.{T}.branch` の write、第 3 引数が "$LAUNCH_TIP" の commit-docs.sh 呼び出しが、この順で残っている。refill の記述（ONCE per entry、$RECONCILE_TIP を再利用しない）も残っている。tests/test_exit4_tip_argument_consistency.py が修正なしで通る。
- [ ] AC3（FR2）: write set の対象が「選択したタスク全部」ではなく「読み直した journal で起動を確認できたタスク」と書かれている。起動を確認できなかったタスクは pending のまま書かないこと、部分起動のときは確認できた集合で 1 回コミットすることが書かれている。
- [ ] AC4（FR3）: 起動ゼロのときにコミットを省略すること、ターンの終了がコミット処理の後であることが書かれている。「起動直後にターンを終える」という記述は残っていない。
- [ ] AC5（FR4）: 通常のコミットでも exit 4 の再試行でも journal を読み直し、終端（merged / failed）のタスクを in_progress にしないことが書かれている。2 回目の exit 4 で停止するときに起動記録と worktree・ブランチを保持することが書かれている。
- [ ] AC6（FR5）: I.2.a に「`status: pending` と journal 最終イベント `launched` の組み合わせは決して生じない」という主張がもう無い。代わりに、その組み合わせが生じうる場面と、launched の in-flight 規則で扱われることが書かれている。recursion invariant 文と launched の in-flight 文は残っている。
- [ ] AC7（NFR1）: Step I.2.c の節と Branch & Worktree Model の exit-4 recovery bullet が、変更前と文言で一致する。tests/test_implement_routeback_gate.py が修正なしで通る。
- [ ] AC8（FR6、NFR3、NFR4）: AC1〜AC6 を検査する新しいテストがある。変更前の I.2.a の文面（コミットが承認ゲート・起動ループより前にある）に対しては、そのテストが失敗する。`python3 -m unittest discover -s tests` が全件 green になる。

## 未解決事項

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## 参照

- 要件定義書: `feature-docs/prelaunch-inprogress-routeback/REQUIREMENTS.md`
- 変更対象: `em-workflow/references/implement-phase.md`
