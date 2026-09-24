---
title: "routeback-residual-connections"
created_date: 2026-09-24
status: draft
---

# routeback-residual-connections - 要件定義書

## 1. 概要

### 1.1 背景
PR #7（feature: routeback-reset-scope-consistency）で route-back 経路を単一の導出元に統一した後、`em-workflow/references/implement-phase.md` の I.2.a / I.2.c に未証明の接続が 3 件残った。対応する verify の手動読み合わせ項目は MANUAL-1 / MANUAL-2 / MANUAL-3、レビューの stable_id は 69fc571959dc36a1、e3a4f2b026841bf6、477a18556a3587e3、0acedde04c24cb8d、5a9c94c87a6f7c4f、cbe1e5e8ca5cf4df。

### 1.2 目的
- I.2.a / I.2.c に残った 3 件の未証明な接続を閉じる。
- route-back 経路上の各主張が、文書が検証している内容から導けるようにし、各接続をドキュメント契約テストで固定する。

### 1.3 スコープ
- `em-workflow/references/implement-phase.md` の I.2.a と I.2.c の本文
- `tests/test_routeback_reset_scope_consistency.py` へのドキュメント契約テストの追加
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version bump

スコープ外:
- ウォッチドッグの kill で journal が `launched` のまま固着する failure net の穴（別途起票済み）
- merge-task.sh の処理順序、journal の書き込み処理、hooks の変更
- I.2.b step 3 自体が持つ "verified merged" 節と "report is failed/malformed" 節の優先順位の曖昧さ（routeback-reset-scope-consistency SPEC.md A-2）

## 2. ビジネス要件

### 2.1 ビジネス目標
- PR #7 で単一導出元に統一した後に I.2.a / I.2.c に残った 3 件の未証明な接続（MANUAL-1 / MANUAL-2 / MANUAL-3）を閉じる。
- route-back 経路上のすべての主張が文書の検証内容から導け、各接続がドキュメント契約テストで固定されている状態にする。

### 2.2 対象ユーザー
該当なし（プロトコル参照文書とテストのみの変更）

### 2.3 期待される効果
- 2.1 のビジネス目標に同じ

## 3. ユースケース

該当なし（UI・操作フローの変更を含まない）

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | I.2.a から I.2.c ゲートへの前方参照が `below` を指し、journal `merged` で阻止する conjunct を参照先とする | 本文は既に充足。方向と参照先を固定する回帰テストのみ | 高 |
| FR2 | carve-out / gate / reconciled state の所有関係の連鎖に打ち切り点を明記する | I.2.a に打ち切りの 1 文を追加 | 高 |
| FR3 | route-back の reset 対象集合が 2 つの `failed` 情報源を覆い、事後条件と `replace_all` に接続する | I.2.c の write set を 2 集合の和にし、接続の 1 文を追加 | 高 |
| FR4 | reconciled-`merged` タスクを cleanup から除外することを、ゲートの帰結として記述する | cleanup の文でゲートを理由として挙げる | 高 |
| FR5 | cleanup の not-merged 主張を実際の検証内容に合わせ、残余状態を記録する | 主張を 2 つの情報源に限定し、残余状態の文を追加 | 高 |
| FR6 | TS-10 / TS-11 / TS-12 相当のドキュメント契約テスト | FR1〜FR5 を固定するテストを追加 | 高 |
| FR7 | プラグインの version bump | em-workflow を 0.2.0 から 0.2.1 に上げる | 高 |

### 4.2 機能詳細

#### FR1: I.2.a から I.2.c ゲートへの前方参照が `below` を指し、journal `merged` で阻止する conjunct を参照先とする

**説明**: Step I.2.a の recycled-task-id 段落は、I.2.c の route-back ゲートを `below` として参照し、journal の last event が `merged` のときに route-back を実際に阻止する I.2.c 内の箇所を指す。現在の main は既にこれを満たしている。本文は "Because Step I.2.c's route-back gate below blocks route-back whenever any task's journal last event is `merged` — read from the journal directly, independent of the ancestor check" となっており、I.2.c の第 3 conjunct がまさにその阻止を定義している。旧文言 "(the widened I.2.c gate above)" は既に無い。したがって本要件は文書の編集を必要とせず、方向と参照先を固定する回帰テストだけを求める。

#### FR2: carve-out / gate / reconciled state の所有関係の連鎖に打ち切り点を明記する

**説明**: I.2.a に、I.2.a recycled-task-id carve-out ← I.2.c gate ← I.2.b step 1 reconciled state ← I.2.a carve-out という連鎖を打ち切る 1 文を加える。その文は次のことを述べる。

- carve-out が再分類するのは、workflow.yaml `pending` と対になった journal last event `failed` だけである。
- carve-out は `merged` や `launched` の last event には触れない。
- よって、ゲートの入力である Step I.2.b step 1 の `merged` と in-flight の分類は carve-out を参照せず、連鎖は循環しない。

現在の main にはこの文が無いため、本要件は未充足。

#### FR3: route-back の reset 対象集合が 2 つの `failed` 情報源を覆い、事後条件と `replace_all` に接続する

**説明**: I.2.c の route-back write set において、reset 対象集合を次の 2 集合の和とする。

1. Step I.2.b step 1 の reconciled state が `failed` であるすべてのタスク（このリテラルは原文のまま残し、先頭の要素とする）
2. workflow.yaml が `status: failed` を報告するすべてのタスク

1 文で次のことを述べる。

- 2 つの集合は乖離しうる。workflow.yaml の `failed` 書き込みの所有ルールとして Step I.2.b step 3 を引用し、その内容は再掲しない。
- 事後条件 "no task is left `merged` or `in_progress` or `failed`" と、`references/workflow-patch.md` の `replace_all` permission conditions / protocol-error ルールは、workflow.yaml 自身の status から読まれる。
- 両方の集合を覆うことで、事後条件が真になる。

#### FR4: reconciled-`merged` タスクを cleanup から除外することを、ゲートの帰結として記述する

**説明**: cleanup の文は、reconciled-`merged` のタスクが cleanup 対象にならない理由として、上にあるゲートを挙げる。ゲートはそのようなタスクがあれば route-back を既に拒否しているため、write set が直前に reset した集合にはそのようなタスクが含まれない。判断の所有者はゲートだけのままとする。次の 2 つのリテラルを残す。

- "clean up worktrees and branches for exactly the tasks the write set just reset"
- "a task whose reconciled state is `merged` is never a cleanup target, whatever workflow.yaml says"

#### FR5: cleanup の not-merged 主張を実際の検証内容に合わせ、残余状態を記録する

**説明**: 限定のない "confirmed not merged" を、この経路が読む 2 つの情報源、すなわち workflow.yaml の `status` と Step I.2.b step 1 の reconciled state に限定した主張に置き換える。

既存の "this order's one residual leftover state" の文の後に、残余状態の文を置く。その文は、どちらの情報源からも見えないものを記録する。

- マージが既に integration branch を進めた（merge-task.sh の `git update-ref`）にもかかわらず、その `merged` イベントが journal に届かなかったタスク。
- これは、スクリプトの journal 書き込みが失敗した場合（スクリプトは警告を出すだけで exit 0 する）、または ref 更新と journal 書き込みの間で implementer が report なしに停止した場合に起きる。
- このタスクはここでは失敗タスクと区別できず、route-back がそれを reset してブランチを削除しうる。

その文は、これをゲートが塞がない既知の残余として示す。新たな検証手順も挙動の変更も加えない。

#### FR6: TS-10 / TS-11 / TS-12 相当のドキュメント契約テスト

**説明**: `tests/test_routeback_reset_scope_consistency.py` に、Python 標準ライブラリのみを使う unittest のアサーションを追加し、FR1〜FR5 を既存の D8 スタイルでカバーする。

- 新しい文言のリテラルは、それぞれ 1 つのモジュールレベル定数とし、正のアサーションと否定証明の両方がその定数を読む。
- 各否定証明は、base revision 9f9502487a8da29220aece87f253058becda432e で取得した implement-phase.md の変更前の抜粋（原文のまま）に対して実行する。
- 各抜粋には、保持されているアンカーをアサートする非空性ガードを置く。
- docstring にマッチャーの一覧と取得リビジョンを記録する。

#### FR7: プラグインの version bump

**説明**: em-workflow の version を 0.2.0 から 0.2.1（patch）に上げる。対象は `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリで、同じ値にし、同じ変更に含める。これは task0003 の "no further version bump" 項目（IMPLEMENTATION.md D9 item 4）を置き換える。0.1.39 / 0.2.0 が既に出荷済みのため、その項目はもう当てはまらない。

## 5. 非機能要件

パフォーマンス・セキュリティ・可用性・互換性（ブラウザ・API）の要件は該当なし。

| ID | 要件 |
|----|------|
| NFR1 | ドキュメントのみの変更とする。`em-workflow/scripts/merge-task.sh`、hooks、agents、skills、その他の実行時挙動は変更しない。マニフェスト以外で変更するプラグイン配下のファイルは `em-workflow/references/implement-phase.md` だけとする。 |
| NFR2 | `tests/test_recycled_task_id_consistency.py` と `tests/test_implement_routeback_gate.py` は変更せず、その中のすべてのアサーションが通り続ける。 |
| NFR3 | `tests/test_routeback_reset_scope_consistency.py` と `tests/test_routeback_reset_scope_version_bump.py` の既存のアサーションは、すべて変更なしで通り続ける。 |
| NFR4 | 正規化した I.2.c セクションは、部分文字列 "append" も "rework" も含まない。これにより、新しい文で "journal append"、"appended"、"reworked" は使えない。 |
| NFR5 | I.2.c で保持すべきアンカー: 最初の `tasks.{T}.status` の出現から正規化後 60 文字以内に `pending` がある（そのトークンのより前の言及を追加しない）。4 つの write トークンが `git worktree remove --force` より前にある。順序が gate < ROUTEBACK_TIP < reset --hard < "make one ordered workflow.yaml write set" < "Commit that write set next, BEFORE any cleanup" < "Only once that commit" である。`git branch -D` はちょうど 1 回、cleanup-scope の句と leftover-state の文の間に出現する。commit-docs.sh < git worktree remove --force < "End the phase with a" である。"When the gate does not hold" 以降に write-set / cleanup / ROUTEBACK_TIP のトークンを含まない。見出しと batch-mode の段落がバイト同一の末尾のまま残る。保持されているゲートのリテラルが残る。 |
| NFR6 | I.2.a で保持すべきアンカー: `Select` の行折り返しを含む生のリテラルを再整形しない。"Because Step I.2.c's route-back gate below blocks route-back whenever any task's journal last event is `merged`" から最初の "correctly scoped to `failed` only." までの範囲は、"Because " をちょうど 1 つ、" so " をちょうど 1 つ含むままとする。したがって FR2 の文はその範囲の後に置く。到達不能の文、RECURSION_INVARIANT_PHRASE、"This carve-out is deliberately scoped to `failed` only"、in-flight の文、TWO_PARTIES_PHRASE、hook-group のスライスが残る。I.2.a は "task0001"、"renumber"、"governs only"、"the third route-back gate conjunct above"、"Because route-back proceeds only when no task is `merged` under either source" のいずれも含まない。 |
| NFR7 | implement-phase.md のどの行も、インデントとバッククォートを除いた後に `git ` で始まり、かつ `commit` または `add -A` を含む形にならない。`git update-ref` に触れる文は文の途中に置く。 |
| NFR8 | 新しい文は所有ルール（Step I.2.b step 3、workflow-patch.md の `replace_all` permission conditions、merge-task.sh の journal 書き込みの挙動）を引用し、その内容は再掲しない。 |
| NFR9 | テストは Python 標準ライブラリのみを使い、リポジトリルートの `tests/` に置き、`python3 -m unittest discover -s tests` で検出される。 |

## 6. UI/UX要件

該当なし（デザインステップは skipped: プロトコル参照ファイルに対するドキュメントとテストのみの変更で、UI・見た目・操作の設計対象が無い）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- NFR1〜NFR9 に同じ

### 9.2 ビジネス上の制約
- なし

### 9.3 スケジュール制約
- なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/routeback-residual-connections/**`
- `test-docs/routeback-residual-connections/**`

`feature-docs/routeback-residual-connections/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/routeback-residual-connections/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/routeback-residual-connections/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題（エッジケース）
| 課題 | 内容 |
|------|------|
| EC-1（MANUAL-1） | 対応する journal イベントが無いタスクで workflow.yaml が `status: failed` の場合（I.2.b step 3 が不正または欠落した report を `failed` として書いたもの）。その reconciled state は unlaunched なので、FR3 の和集合によってのみ reset 集合に入る。和集合が無ければ `failed` のまま残り、再計画が workflow-patch.md の `replace_all` の protocol error（"A `replace_all` received while any task is `in_progress` or `failed` is a protocol error"）に当たる。 |
| EC-2（MANUAL-2） | merge-task.sh は `git update-ref` で integration ref を進めた後に append_merged_event を呼ぶ。journal 書き込みの失敗は WARNING を出すだけで exit 0 する。"already contained" の早期終了も同じ journal 書き込みに依存する。implementer が journal 書き込みの前に report なしで停止すると、failure net が `failed` を記録し、reconciled state は `failed` になり、ゲートを通過し、route-back が reset してブランチを削除する。ブランチのコミットは integration branch から到達可能なままなので、`git branch -D` でコミットは失われない。具体的な害は、マージ済みのタスクが `pending` に戻されて再計画されること。 |
| EC-3 | journal イベントが無く workflow.yaml の `failed` だけで FR3 の和集合に入るタスクは、worktree やブランチを持たないことがある。現在の cleanup の本文は、対象が存在しないときに `git worktree remove --force` / `git branch -D` がどう振る舞うかを述べていない。実行時の変更はスコープ外（NFR1）。 |
| EC-4 | ancestor check が失敗したケース（journal は `merged`、reconciled は `failed`）は、I.2.c の第 3 conjunct で阻止されたままとする。FR3 の和集合がこれを通過可能にしてはならず、ゲートは write set より前に評価されるので、通過可能にはならない。 |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: I.2.a の I.2.c ゲートへの参照が `below` となっており、journal の `merged` last event で阻止する I.2.c の conjunct を指す。I.2.a に I.2.c ゲートを `above` として参照する箇所が残っていない。（base で既に真。テストで固定する）
- [ ] AC-2: I.2.a に、recycled-task-id carve-out は journal の last event が `failed` のときだけ適用されるため、Step I.2.b step 1 の `merged`（および in-flight）の分類はそれを参照せず、carve-out / gate / reconciled state の連鎖が打ち切られることを述べる文がある。
- [ ] AC-3: I.2.c の reset 対象集合が 2 つの `failed` 情報源を挙げ、reconciled state のリテラルが原文のまま先頭にある。1 文が乖離について Step I.2.b step 3 を引用し、和集合を事後条件と、workflow.yaml の status に対する workflow-patch.md の `replace_all` permission conditions に結び付けている。
- [ ] AC-4: cleanup の文が reconciled-`merged` タスクを除外する理由としてゲートを挙げ、保持すべき cleanup のリテラル 2 つが残っている。
- [ ] AC-5: 限定のない "confirmed not merged" が無くなっている。not-merged の主張が 2 つの情報源で限定されている。leftover-state の文の後に置かれた残余状態の文が、journal イベントの無いマージ済みブランチの時間窓を検出されないものとして記録している。
- [ ] AC-6: TS-10 / TS-11 / TS-12 相当のドキュメント契約テストが `tests/` にあり、新しいマッチャーごとに否定証明と非空性ガードがある。
- [ ] AC-7: plugin.json と marketplace.json の両方で em-workflow の version が 0.2.1 である。
- [ ] AC-8: リポジトリルートから `python3 -m unittest discover -s tests` が通り、編集禁止の 2 モジュールは変更されていない。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
| ID | 対応 | 相当 | 種別 | 内容 |
|----|------|------|------|------|
| TS-1 | FR1, AC-1 | TS-12（方向の半分） | unit（ドキュメント契約） | 正規化した I.2.a に、Step I.2.c のゲートを `below` と呼ぶ journal-`merged` の前提があり、I.2.c ゲートへの参照が `above` になっていない。参照先の conjunct の句が正規化した I.2.c に存在する。リポジトリに既にある変更前の文言（"(the widened I.2.c gate above)"）に対する否定証明。 |
| TS-2 | FR2, AC-2 | TS-12（打ち切りの半分） | unit（ドキュメント契約） | 連鎖の打ち切りの文が、単一の因果構成の範囲の後で I.2.a に存在する。recursion-invariant の文が引き続き "can never arise." の後にある。carve-out と in-flight の文が残る。base revision の I.2.a の原文抜粋に対する否定証明。 |
| TS-3 | FR3, AC-3 | TS-10 | unit（ドキュメント契約） | reset 対象集合が reconciled state のリテラル（先頭）と workflow.yaml `status: failed` の要素を挙げる。乖離／事後条件の文が Step I.2.b step 3 と `replace_all` を引用する。60 文字の範囲と 4 つの write トークンの順序が引き続き成り立つ。base の write set の抜粋に対する否定証明。 |
| TS-4 | FR4, FR5, AC-4, AC-5 | TS-11 | unit（ドキュメント契約） | cleanup の文が除外をゲートに帰している。not-merged の主張が情報源で限定され、限定の無い "confirmed not merged" が無い。残余状態の文が leftover-state の文の後にある。`git branch -D` がスコープ付きの文の中にちょうど 1 回出現する。I.2.c に "append" / "rework" が無い。base の cleanup の抜粋に対する否定証明。 |
| TS-5 | FR7, AC-7 | - | unit（JSON） | 両マニフェストがパースでき、em-workflow の version が要素ごとの数値比較で 0.2.0 より厳密に大きく、2 つの登録が等しい。偽造した 0.2.0 と、偽造した不一致のペアに対する否定証明。 |
| TS-6 | AC-8, NFR2, NFR3 | - | suite | `python3 -m unittest discover -s tests` が exit 0 になる。base との git diff で、編集禁止の 2 モジュールが変更されていない。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| MANUAL-1 / MANUAL-2 / MANUAL-3 | PR #7 の verify で落ちた手動読み合わせ項目 |
| TS-10 / TS-11 / TS-12 | routeback-reset-scope-consistency の task0003 で計画されたテストシナリオ。本フィーチャーの TS-3 / TS-4 / TS-1・TS-2 がそれぞれ相当する |

## 14. 確認事項

### 14.1 確認済み事項
- [x] ユーザーへの質問と回答: なし（batch モード）
- [x] テストの配置（create-spec.test-module-placement）: 新しいアサーションは既存モジュール `tests/test_routeback_reset_scope_consistency.py` に追加する（orchestrator が Codex への相談を経て batch で解決し、`phase-state/batch-audit.yaml` に記録）

### 14.2 未確認・保留事項
- なし

### 14.3 前提（すべて可逆）
- A-1: MANUAL-2 は選択肢 (b)、すなわち残余状態を文書化して主張を弱める方法で解決する。選択肢 (a)、cleanup の前に候補ごとに `git merge-base --is-ancestor` で検査する方法は採らない（routeback-reset-scope-consistency の IMPLEMENTATION.md D9 item 3 の記録どおり）。タスク記述の受け入れ条件は「不足分の残余状態が明記されている」を明示的に認めている。
- A-2: MANUAL-3 の方向の誤りは、後続の作業で main 上で既に修正されている（test_recycled_task_id_consistency.py が "Because Step I.2.c's route-back gate below ..." を固定し、"the third route-back gate conjunct above" が無いことをアサートしている）。本フィーチャーは打ち切りの文と固定テストを加えるだけで、前提の文は再編集しない。
- A-3: 放置された task0003 の worktree（`.claude/worktrees/em-workflow/routeback-reset-scope-consistency/task0003`）はもう存在しない。その未コミットの編集は破棄し、再利用しない。
- A-4: version は 0.2.0 → 0.2.1（patch: 挙動を明確にするドキュメント修正）とする（`.claude/rules/core-plugin-version-bump.md` に従う）。これは task0003 の D9 item 4 を上書きする。
- A-5: 新しいドキュメント契約アサーション（TS-10/11/12 相当）は、新しいモジュールではなく既存の `tests/test_routeback_reset_scope_consistency.py` を拡張する。その中の既存のアサーションはすべて通り続ける。その docstring の 19 行目（"confirmed not merged"）は説明文であり、アサーションではない。
- A-6: タスク記述の行番号（219 / 372 / 67）は現在の main に対して古い。I.2.a の前提は 249 行目付近、I.2.c は 787 行目から、exit-4 の bullet は 43〜82 行目付近にある。箇所は行番号ではなく本文で特定する。
- A-7: `tests/test_recycled_task_id_consistency.py` と `tests/test_implement_routeback_gate.py` の既存のリテラルアサーションは不変条件であり、変更してはならない（既存テストで固定された事実）。
- A-8: スキャン対象外の他の version-bump モジュール（例: `tests/test_recycled_task_id_version_bump.py`）は、`tests/test_routeback_reset_scope_version_bump.py` と同じ形で、下限の baseline と等価性をアサートしていると仮定する。したがって 0.2.1 でも通る。ファイルが reference_scan_targets の外にあるため直接は確認していない。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: I.2.a / I.2.b / I.2.c
- `em-workflow/references/workflow-patch.md`: `replace_all` permission conditions
- `em-workflow/scripts/merge-task.sh`: journal 書き込みの挙動
- `feature-docs/routeback-reset-scope-consistency/IMPLEMENTATION.md`: D9
- `feature-docs/routeback-reset-scope-consistency/tasks/task0003.md`
- `.claude/rules/core-plugin-version-bump.md`
