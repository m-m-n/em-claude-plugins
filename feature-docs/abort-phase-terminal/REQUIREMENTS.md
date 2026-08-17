---
title: "abort-phase-terminal"
created_date: 2026-08-17
status: draft
---

# abort-phase-terminal - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/references/implement-phase.md` Step I.2.c の rejected path は、自身の終端を「`- **abort phase**` オプションと同じ終端」であると主張している（`the same terminal as the "abort phase" option below`）。しかし実際には、Step I.1 が `implement: in_progress` を設定し、その後 `failed` へ書き戻すのは rejected path だけである。abort phase を選んだ場合、実ステータスは `in_progress` のまま残る。

この不一致は develop ループの危険を生む。`implement` が `in_progress` のまま残るため、develop の停止条件 3（`failed` / `needs_update` で発火）が abort 後に発火せず、Step B が implement を再実行して I.2.c が三択を再提示し続け、最終的に停止条件 2（同一ステップが進捗なしで二度実行された）で止まる。

同じ終端記述は batch mode 側にも存在し、`em-workflow/references/batch-mode.md` の Non-packet gates 表 `implement.failed-task` 行が「`implement` stays `failed`」という、どの書き込みも生み出さないステータスを独立に再掲している。

### 1.2 目的

abort phase オプションに、rejected path が既に持つのと同じ明示的な終端 — 統合 worktree のリフレッシュ → `implement: failed` の書き込み → `commit-docs.sh` → 報告 — を与え、equivalence の主張を（削除ではなく書き込み側の修正によって）真にする。あわせて batch mode の終端記述を implement-phase.md と batch-mode.md の間で一致させる。

### 1.3 スコープ

散文の変更集合は 4 箇所に限定される。

1. `em-workflow/references/implement-phase.md` Step I.2.c の `- **abort phase**` バレット（FR1）
2. 同セクションの batch-mode 段落（FR2）
3. 同ファイルの Branch & Worktree Model の exit-4 recovery バレット（FR6）
4. `em-workflow/references/batch-mode.md` の `implement.failed-task` 行（FR7）

これに加えて、byte pin を持つ 3 つのテストモジュール（FR8）と 2 つのバージョンマニフェスト（FR9）を同一変更内で更新する。

明示的な非目標: `em-workflow/skills/develop/SKILL.md` は編集しない。特に停止条件 5 の括弧書き「batch: 三択の代わりにタスクごと 1 回だけ自動 retry、2 回目の failed で中断 — `batch-mode.md` の Non-packet gates 表、`implement.failed-task`」（SKILL.md L38-40）は変更しない。停止条件 2 / 3 および Step B の「停止条件 3 との優先関係」も同様に不変。`em-workflow/references/workflow-patch.md` と `em-workflow/scripts/validate-worker-output.py` も凍結。exit-4 recovery の適用範囲（findings 2394334a18ac6901 / 397c2a098d705a55）および `feature-docs/routeback-gate-postcondition/SPEC.md` の改訂（298809a29d50c663 と兄弟）は完全にスコープ外で、別タスクとして起票済み。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| BO1 | implement-phase.md Step I.2.c の rejected path が主張する equivalence（`the same terminal as the "abort phase" option below`）を実際に真にする。abort オプションに、rejected path が既に持つのと同じ明示的な「リフレッシュ → `implement: failed` の書き込み → `commit-docs.sh` → 報告」の終端を与える。現状は Step I.1 が `implement: in_progress` を設定し、`failed` へ書き戻すのは rejected path のみであるため、abort を選ぶと実ステータスは `in_progress` のまま残る。 |
| BO2 | 不一致が生む develop ループの危険を除去する。`implement` が `in_progress` のまま残ることで、develop の停止条件 3（`failed` / `needs_update` で発火）が abort 後に発火せず、Step B が implement を再実行し I.2.c が三択を再提示し続け、停止条件 2（同一ステップが進捗なしで二度）で初めて止まる。修正後は abort 後の停止点が散文だけから読み取れ、それが停止条件 3 であること。 |
| BO3 | 「同一タスクでの二度目の失敗 → abort phase」に対する batch mode 側の根拠を復元し、implement-phase.md I.2.c と batch-mode.md の `implement.failed-task` 行が一つの同じ終端を記述する状態を保つ。 |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| implement フェーズを実行するエージェント | Step I.2.c の散文を読んで abort 時の手順を実行する。現状は終端の書き込みが記述されていない。 |
| develop スキルを実行するエージェント | abort 後にどの停止条件で制御が返るかを散文から判断する。 |
| em-workflow プラグインの保守者 | implement-phase.md と batch-mode.md の終端記述の整合性を維持する。 |

### 2.3 期待される効果

- abort phase 選択後、`implement` の実ステータスが `failed` になり、develop の停止条件 3 が次の Step B イテレーションで発火する。
- 三択の再提示ループが解消され、停止条件 2 に頼らずに停止する。
- implement-phase.md I.2.c と batch-mode.md の `implement.failed-task` 行が矛盾しない一つの終端を記述する。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | interactive モードで abort phase を選択する | implement フェーズ実行エージェント | 高 |
| UC02 | batch モードで同一タスク二度目の失敗により abort する | implement フェーズ実行エージェント | 高 |

### 3.2 ユースケース詳細

#### UC01: interactive モードで abort phase を選択する

**アクター**: implement フェーズ実行エージェント

**事前条件**:
- Step I.1 により `implement` ステップの `status` が `in_progress` である。
- Step I.2.c の三択が提示されている。

**基本フロー**:
1. ユーザーが `- **abort phase**` を選択する。
2. 統合 worktree をリフレッシュする（`git -C "$WT_ROOT/integration" reset --hard em-workflow/{feature}/integration`）。
3. tip を変数に取得する（rejected path の `TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)` に倣う）。
4. workflow.yaml の `implement` ステップの `status` を `failed` に設定する。
5. その書き込みだけを `commit-docs.sh "$WT_ROOT/integration" "docs({feature}): ..." "$TERMINAL_TIP"` でコミットする。
6. 報告して停止する。

**代替フロー**:
- `commit-docs.sh` が exit 4 を返した場合は、Branch & Worktree Model の bounded recovery（リフレッシュ、tip 再取得、ソースから再導出した同一遷移の再適用、1 回だけ再試行。二度目の exit 4 でフェーズを報告して停止）に従う（FR6）。

**事後条件**:
- `implement` ステップの `status` が `failed` であり、その書き込みがコミットされている。
- 他の副作用はない（route-back write set なし、`create-plan: needs_update` なし、`tasks.{T}.status` リセットなし、`tasks.{T}.notes` の失敗理由書き込みなし、worktree / branch のクリーンアップなし）。
- 次の Step B イテレーションが `implement: failed` を読むことで develop の停止条件 3 が発火する。

#### UC02: batch モードで同一タスク二度目の失敗により abort する

**アクター**: implement フェーズ実行エージェント

**事前条件**:
- `references/batch-mode.md` の Non-packet gates 表、gate id `implement.failed-task` に従い、同一タスクで既に 1 回 retry が自動選択されている。

**基本フロー**:
1. 同一タスクで二度目の失敗が発生する。
2. UC01 と同一の「リフレッシュ → `implement: failed` の書き込み → `commit-docs.sh` → 報告」シーケンスを実行して停止する。

**事後条件**:
- UC01 と同一。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | interactive の abort オプションに明示的な write-and-commit 終端を与える | I.2.c の `- **abort phase**` バレットを書き換える | 高 |
| FR2 | batch mode の abort に同一の終端を与える | I.2.c の batch-mode 段落を書き換える | 高 |
| FR3 | abort の副作用集合を終端書き込みとそのコミットに限定する | 両 abort パスに no-other-side-effect を明記する | 高 |
| FR4 | abort 後の停止点を一意に記述する | 停止条件 3 と「次の Step B イテレーション」の定式を明記する | 高 |
| FR5 | equivalence の主張を削除せず保持する | rejected path の該当文を verbatim で残す | 高 |
| FR6 | 新しいコミット呼び出し点を exit-4 recovery の bounded 側に置く | Branch & Worktree Model の列挙に追加する | 高 |
| FR7 | batch-mode.md の `implement.failed-task` 行を同期する | 行の終端記述を FR2 に合わせる | 高 |
| FR8 | I.2.c batch-mode 段落の byte pin を全て更新する | 3 テストモジュールのリテラルを更新する | 高 |
| FR9 | プラグインバージョンを lockstep で bump する | 2 つのマニフェストを 0.1.44 にする | 高 |
| FR10 | 同期範囲を 4 ドキュメントに限定し、非目標を明示する | 変更集合と凍結対象を確定する | 高 |

### 4.2 機能詳細

#### FR1: Interactive abort option gets an explicit write-and-commit terminal

**説明**: `em-workflow/references/implement-phase.md` Step I.2.c において、`- **abort phase**` オプションは rejected path が述べるのと同じ順序の終端を述べなければならない。すなわち、統合 worktree のリフレッシュ（`git -C "$WT_ROOT/integration" reset --hard em-workflow/{feature}/integration`）、tip の変数への取得（rejected path の `TERMINAL_TIP=$(git -C "$WT_ROOT/integration" rev-parse HEAD)` に倣う）、workflow.yaml の `implement` ステップの `status` を `failed` に設定、そしてその書き込みだけを `commit-docs.sh "$WT_ROOT/integration" "docs({feature}): ..." "$TERMINAL_TIP"` でコミットすること。

**ビジネスルール**:
- 現行の文言 `` leave `implement` as `failed` for manual handling ``（どの書き込みも生み出さないステータスを主張している）は残してはならない。
- バレットは引き続き literal な `- **abort phase**` で始まらなければならない（2 つのテストモジュールがこれをスライスの終端アンカーとして使用している）。

#### FR2: Batch-mode abort gets the identical terminal

**説明**: Step I.2.c の batch-mode 段落は、二度目の失敗による abort を、現行の「implement stays `failed`, report and stop」ではなく、同じ「リフレッシュ → `implement: failed` の書き込み → `commit-docs.sh` → 報告して停止」のシーケンスで記述しなければならない。

**ビジネスルール**:
- 段落は I.2.c セクションの最終コンテンツであり続けなければならない（3 つの byte pin アサーションはいずれも `` Batch mode (`references/batch-mode.md` `` からセクション末尾までをスライスする）。
- `` references/batch-mode.md `` の Non-packet gates 表と gate id `implement.failed-task` の言及を維持しなければならない。

#### FR3: Abort's side-effect set is bounded to the terminal write and its commit

**説明**: 両 abort パスは、終端ステータス書き込みとそれ自身のコミットが唯一の副作用であると述べなければならない。すなわち route-back write set なし、`create-plan: needs_update` なし、`tasks.{T}.status` のリセットなし、`tasks.{T}.notes` への失敗理由書き込みなし、worktree / branch のクリーンアップ（`git worktree remove` / `git branch -D`）なし。

**ビジネスルール**:
- これは rejected path の既存文 `There is no route-back write set, no worktree/branch cleanup and no route-back commit on this path` を鏡写しにするものであり、その文は現在の位置に intact のまま残らなければならない。

#### FR4: The post-abort stopping point is stated uniquely

**説明**: 両 abort パスは develop の停止条件 3 を停止点として名指し、それが `implement: failed` を読む**次の** Step B イテレーションで発火すると述べなければならない。これは rejected path が既に用いている定式（`reports and returns control to the user via develop's stop condition 3, which fires on the next Step B iteration reading `implement: failed``）と同一である。

**ビジネスルール**:
- この形が必要な理由は、`skills/develop/SKILL.md` Step B の「停止条件 3 との優先関係」が停止条件 3 を「Step B が実行しようとしているステップを特定した時点」で一度だけ評価し、そのステップ自身のフェーズ実行中に意図的に保持されたステータスに対しては再発火しないためである。

#### FR5: The equivalence claim is kept, not deleted

**説明**: 採用する方向は書き込み側の修正であり、finding dbb12002e43e113d が提示した主張削除の代替案ではない。rejected path の文 `the same terminal as the "abort phase" option below` は verbatim で残らなければならず、FR1 / FR2 の後にはそれが真の言明となる。

**ビジネスルール**:
- 当該文字列は `tests/test_recycled_task_id_consistency.py` L143 の `ABORT_PHASE_TERMINAL_PHRASE` として pin されており、L350 で rejected-path スライス内の存在がアサートされている。

#### FR6: The new commit call site falls on the bounded side of exit-4 recovery

**説明**: Branch & Worktree Model の exit-4 recovery バレット（implement-phase.md L43-80）は、新しい abort 終端ステータスコミットを、bounded recovery（リフレッシュ、tip 再取得、ソースから再導出した同一遷移の再適用、1 回だけ再試行。二度目の exit 4 はフェーズを報告して停止）に拘束される呼び出し点として列挙しなければならない。

**ビジネスルール**:
- 唯一の carve-out は Step I.2.c の route-back commit のままでなければならない。abort の呼び出し点を carve-out に加えてはならない。
- 既存の列挙項目（`Step I.1's baseline commit`、`Step I.2.b's wake-phase commit`、`Step I.2.c's rejected-path terminal status commit`）は全て残らなければならない。
- 列挙は `for example` で導入されており閉じていないため、項目の追加は許容される。撤回済みの閉集合主張 `` the three `commit-docs.sh` call sites in this phase where exit 4 can occur `` は再登場してはならない。

#### FR7: batch-mode.md's implement.failed-task row is synchronized

**説明**: `em-workflow/references/batch-mode.md` の Non-packet gates 行 `implement.failed-task`（L60）は現在 `` A second failure on the SAME task → **abort phase** (`implement` stays `failed`) `` と読める。これを FR2 の終端（`implement: failed` の書き込みとそのコミット）に言い換えなければならない。

**ビジネスルール**:
- 行の gate id `implement.failed-task`、`Auto-select **retry** once per task` 節、`Route-back-to-planning is never taken automatically` 節、`` Full detail: `references/implement-phase.md` Step I.2.c `` ポインタを保持し、`tests/test_batch_policies.py` の Non-packet-gate id リストと (description, substring) の対応が引き続き一致するようにする。

#### FR8: Every byte pin of the I.2.c batch-mode paragraph is updated

**説明**: batch-mode 段落は 3 つのテストモジュールで byte-identical に pin されており、その全てを同一変更内で変更後テキストに更新しなければならない。

| # | モジュール | pin の位置 | アサーション |
|---|-----------|-----------|-------------|
| a | `tests/test_implement_routeback_gate.py` | モジュール定数 `PRE_CHANGE_BATCH_MODE_PARAGRAPH`（L111-120） | `test_batch_mode_paragraph_is_byte_identical`（L706-710） |
| b | `tests/test_recycled_task_id_consistency.py` | モジュール定数 `PRE_CHANGE_BATCH_MODE_PARAGRAPH`（L116-125） | `test_batch_mode_paragraph_is_byte_identical_tail`（L480-484） |
| c | `tests/test_routeback_reset_scope_consistency.py` | `test_batch_mode_paragraph_is_byte_identical_tail` 内の関数ローカルリテラル（L594-613） | 同関数 |

**ビジネスルール**:
- 各 pin は `` Batch mode (`references/batch-mode.md` `` から始まり I.2.c セクション末尾までのセクションスライスとの等価性をアサートする。

#### FR9: Plugin version bump in lockstep

**説明**: `em-workflow/` 配下のファイルが変更されるため、`em-workflow/.claude-plugin/plugin.json` の `version` とルート `.claude-plugin/marketplace.json` の `em-workflow` エントリの `version` を、同一変更内で現行の `0.1.43` から `0.1.44` へ揃って移動させなければならない。

**ビジネスルール**:
- `tests/test_implement_routeback_gate.py::TestPluginVersionBumpedInLockstep` が両値の等価性と `(major, minor) == (0, 1)` かつ patch > 42 をアサートするため、2 ファイルが乖離してはならない。

#### FR10: Synchronization scope — exactly four documents, one explicit non-goal

**説明**: 散文の変更集合は正確に次の 4 つである。(1) `em-workflow/references/implement-phase.md` Step I.2.c の `- **abort phase**` バレット（FR1）、(2) 同セクションの batch-mode 段落（FR2）、(3) 同ファイルの Branch & Worktree Model exit-4 recovery バレット（FR6）、(4) `em-workflow/references/batch-mode.md` の `implement.failed-task` 行（FR7）。

**ビジネスルール**:
- 明示的な非目標: `em-workflow/skills/develop/SKILL.md` は編集しない。特に停止条件 5 の括弧書き「batch: 三択の代わりにタスクごと 1 回だけ自動 retry、2 回目の failed で中断 — `batch-mode.md` の Non-packet gates 表、`implement.failed-task`」（SKILL.md L38-40）は変更しない。これは batch gate の選択メカニクスを記述しており、終端の詳細は既に batch-mode.md へ委譲しているためである。
- 停止条件 2 と 3、および Step B の「停止条件 3 との優先関係」も同様に不変。
- 凍結かつ不変: `em-workflow/references/workflow-patch.md`、`em-workflow/scripts/validate-worker-output.py`。
- 完全にスコープ外: exit-4 recovery の適用範囲（findings 2394334a18ac6901 / 397c2a098d705a55）、`feature-docs/routeback-gate-postcondition/SPEC.md` の改訂（298809a29d50c663 と兄弟）。いずれも別途起票済み。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| exit 4 | 新しい abort 終端コミットで `commit-docs.sh` が exit 4 を返す | FR6 の bounded recovery（1 回だけ再試行、二度目でフェーズを報告して停止） |

## 5. 非機能要件

本フィーチャーはドキュメント整合性の修正であり、パフォーマンス・セキュリティ・可用性の要件は requirements-analyst の解決済み要件に含まれない。確定している非機能要件は以下の 6 件である。

### 5.1 NFR1: Forbidden tokens in I.2.c

正規化された I.2.c セクションは、部分文字列 `rework` も `append` もどこにも含んではならない。`tests/test_recycled_task_id_consistency.py::test_no_rework_or_append_anywhere_in_i2c` により、また rejected-path スライスに対しては `tests/test_implement_routeback_gate.py::test_no_rework_or_append_handoff` により強制される。新しい abort 文言は、活用形を含めてこれらの部分文字列を避けなければならない。

### 5.2 NFR2: Structural anchors preserved

- `### I.2.c: Failed handling` は byte-identical のまま。
- abort バレットは正確な開始 `- **abort phase**` を保つ。
- rejected-path マーカー `When the gate does not hold` と、そのアサート対象フレーズ（`` create-plan` is NOT set to `needs_update` ``、`` sets the `implement` step's `status` to `failed` ``、`the single write this path makes`、`commits exactly that write`、`No retry loop, no alternative recovery route, and no degraded route back is offered`）は存在し続ける。
- batch-mode 段落はセクションの最終コンテンツのまま。
- オプションリストの後の段落（`There is NO skip option: …`）は残る。

### 5.3 NFR3: No bare git commit/add lines

`tests/test_implement_routeback_gate.py::test_no_bare_git_commit_or_add_lines` が implement-phase.md 全体をスキャンする。新しい散文が規定する全てのコミットは `commit-docs.sh` を経由しなければならず、raw な `git commit` / `git add -A` 行であってはならない。

### 5.4 NFR4: Documentation-only change

ランタイム挙動のコード変更はない。`em-workflow/scripts/commit-docs.sh`（その RECOVERY CONTRACT は既に implement-phase.md I.2.c の route-back commit を唯一の unreachability carve-out として名指している）は変更せず、hooks その他のスクリプトも変更しない。変更集合は散文 + 3 テストモジュール + 2 バージョンマニフェストである。

### 5.5 NFR5: Suite green

`python3 -m unittest discover -s tests` がリポジトリルートから外部依存なしで成功する（test/README.md: Python 標準ライブラリの unittest のみ）。

### 5.6 NFR6: Internal consistency of the terminal description

abort 終端、rejected-path 終端、batch-mode.md の行は、一つの同じシーケンスを記述しなければならない。いずれのドキュメントも他が矛盾する終端を述べてはならず、いずれのドキュメントも、それを生み出す書き込みを名指すことなく `implement` が `failed` に到達すると主張してはならない。

## 6. UI/UX要件

該当なし。本フィーチャーはユーザーインターフェース、視覚的サーフェス、CSS / token / theme 成果物、新しいユーザー向けインタラクションを一切出荷しない。既存のエージェント向けプロトコル言明を真にするだけである（design ステップは `skipped`）。

## 7. データ要件

該当なし。データモデル、データ項目、保持期間に関する要件は解決済み要件に含まれない。本フィーチャーが触れる唯一の状態は workflow.yaml の `implement` ステップの `status` 値であり、それは既存のスキーマ上の値である。

## 8. 外部連携

該当なし。外部システム連携および API 仕様要件は解決済み要件に含まれない。

## 9. 制約条件

### 9.1 技術的制約

- 変更後の I.2.c セクションに部分文字列 `rework` / `append` を含められない（NFR1）。
- 全てのコミットは `commit-docs.sh` 経由でなければならず、bare な `git commit` / `git add` 行を書けない（NFR3）。
- I.2.c の batch-mode 段落は 3 つのテストモジュールで byte-identical に pin されているため、散文とテストリテラルを同一変更内で更新しなければならない（FR8）。
- 構造アンカー（見出し、バレット開始、rejected-path のフレーズ群、段落順序）を壊せない（NFR2）。
- テストは Python 標準ライブラリの unittest のみで、外部依存を追加できない（NFR5）。

### 9.2 ビジネス上の制約

- 主張削除の代替案（finding dbb12002e43e113d）は採らない。書き込み側の修正のみ（FR5）。
- `em-workflow/skills/develop/SKILL.md`、`em-workflow/references/workflow-patch.md`、`em-workflow/scripts/validate-worker-output.py`、`feature-docs/routeback-gate-postcondition/SPEC.md` は変更しない（FR10 / NFR4）。

### 9.3 スケジュール制約

解決済み要件にスケジュール制約の記載はない。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/implement-phase.md`
- `em-workflow/references/batch-mode.md`
- `tests/test_implement_routeback_gate.py`
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_routeback_reset_scope_consistency.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/abort-phase-terminal/**`
- `test-docs/abort-phase-terminal/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| batch-mode 段落の byte pin が 3 モジュールに分散している | 高 | FR8 で 3 箇所を同一変更内に更新し、TS-7 の負の証明（いずれか 1 つを変更前値に戻すとそのモジュールだけが失敗する）で網羅を確認する |
| 新しい abort 文言に `rework` / `append` が混入する | 中 | NFR1 / TS-8 の否定アサーションで検出する |
| 新しいコミット呼び出し点が exit-4 の carve-out 側に誤って置かれる | 中 | FR6 / TS-5 で bounded 側の列挙に入り、carve-out が route-back commit 単独のままであることをアサートする |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| implement-phase.md と batch-mode.md の終端記述が再び乖離する | 中 | 高 | NFR6 と FR7 により両者を同一シーケンスとして記述し、TS-6 で行の内容をアサートする |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1 (FR1, NFR2): implement-phase.md の I.2.c セクションで `- **abort phase**` バレットが、順に worktree リフレッシュ、tip 取得、`implement` ステップの `status: failed` 書き込み、取得した tip を第 3 引数に持つ `commit-docs.sh` 呼び出しを述べており、フレーズ `` leave `implement` as `failed` for manual handling `` はセクション内のどこにも現れない。
- [ ] AC-2 (FR2): I.2.c の batch-mode 段落が二度目の失敗による abort を同じ refresh / write / `commit-docs.sh` / report のシーケンスで記述し、引き続き Non-packet gates 表と `implement.failed-task` を名指し、セクションの最後のコンテンツであり続ける。フレーズ「implement stays `failed`, report and stop」はそこに現れない。
- [ ] AC-3 (FR3): 両 abort パスが、終端ステータス書き込みとそのコミットが唯一の副作用であること（`create-plan` の `needs_update` なし、task status / notes のリセットなし、worktree / branch のクリーンアップなし）を明示する。rejected path の既存文 `There is no route-back write set, no worktree/branch cleanup and no route-back commit on this path` と `the terminal status write and its own commit are the ONLY side effect` 節は不変。
- [ ] AC-4 (FR4): 両 abort パスが develop の停止条件 3 を名指し、それが `implement: failed` を読む次の Step B イテレーションで発火すると述べる。
- [ ] AC-5 (FR5): literal `the same terminal as the "abort phase" option below` が rejected-path ブランチに引き続き存在する。
- [ ] AC-6 (FR6): Branch & Worktree Model の exit-4 バレットが abort 終端ステータスコミットを bounded recovery に拘束されるものとして列挙し、引き続き `Step I.1's baseline commit`、`Step I.2.b's wake-phase commit`、`Step I.2.c's rejected-path terminal status commit` を名指し、route-back commit を唯一の carve-out として名指す。exit-4 が起きうる呼び出し点数についての閉集合主張は導入されない。
- [ ] AC-7 (FR7): batch-mode.md の `implement.failed-task` 行が FR2 の終端を記述し、gate id、retry-once 節、never-auto-route-back 節、Full-detail ポインタを保持する。
- [ ] AC-8 (FR8): 3 つの byte pin リテラル（`tests/test_implement_routeback_gate.py`、`tests/test_recycled_task_id_consistency.py`、`tests/test_routeback_reset_scope_consistency.py`）が変更後の batch-mode 段落と等しく、各モジュールの pin アサーションが通る。
- [ ] AC-9 (FR9): `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の `em-workflow` エントリがいずれも `0.1.44` を読む。
- [ ] AC-10 (FR10): `em-workflow/skills/develop/SKILL.md`、`em-workflow/references/workflow-patch.md`、`em-workflow/scripts/validate-worker-output.py`、`feature-docs/routeback-gate-postcondition/SPEC.md` が本変更で変更されていない。
- [ ] AC-11 (NFR1, NFR3): 正規化された I.2.c セクションが `rework` も `append` も含まず、implement-phase.md に bare な `git commit` / `git add` 行がない。
- [ ] AC-12 (NFR5): `python3 -m unittest discover -s tests` が exit 0 で終了する。

### 11.2 KPI

解決済み要件に KPI の記載はない。合否は上記受け入れ基準と 12 節のテストシナリオで判定する。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系 (TS-1, FR1/NFR2): implement-phase.md を `### I.2.c: Failed handling` から `### Supporting cast` までスライスし、空白を正規化し、`- **abort phase**` から batch-mode 段落の開始までのスライスを取り、リフレッシュコマンドの literal `reset --hard em-workflow/{feature}/integration`、`rev-parse HEAD` の tip 取得、`implement` ステップの `status` を `failed` に書くフレーズ、第 3 引数を持つ `commit-docs.sh` 呼び出しを含むことをアサートする。`` assertNotIn("leave `implement` as `failed` for manual handling", section) ``。
- [ ] 正常系 (TS-2, FR2): 同じ正規化済みセクションで、`` Batch mode (`references/batch-mode.md` `` から始まるスライスが同じ refresh / write / `commit-docs.sh` / report の要素を含み、「implement stays `failed`, report and stop」を含まないこと。生（未正規化）のスライスが引き続きセクションを終端する（`### Supporting cast` の前に何も続かない）こと。
- [ ] 正常系 (TS-3, FR3/FR4): 両 abort スライスが no-other-side-effect の言明（`create-plan` の `needs_update` なし、worktree / branch のクリーンアップなし）と、`stop condition 3` および `next Step B iteration` の定式を含むこと。rejected-path スライス自身の副作用文が引き続き存在すること。
- [ ] 回帰 (TS-4, FR5): `` assertIn('the same terminal as the "abort phase" option below', rejected_path_slice) `` — すなわち `tests/test_recycled_task_id_consistency.py::test_rejected_path_cites_stop_condition_3_and_abort_phase` と `tests/test_implement_routeback_gate.py::test_control_returns_via_stop_condition_3` が変更なしで通る。
- [ ] 正常系 (TS-5, FR6): 正規化された Branch & Worktree Model セクションに対し、新しい abort 終端コミットが bounded-recovery の列挙に名指されていること、`Step I.1's baseline commit` / `Step I.2.b's wake-phase commit` / `Step I.2.c's rejected-path terminal status commit` が引き続き名指されていること、route-back commit が引き続き唯一の carve-out として記述されていること、`` assertNotIn('the three `commit-docs.sh` call sites in this phase where exit 4 can occur', section) `` をアサートする。
- [ ] 正常系 (TS-6, FR7): batch-mode.md を読み、`` `implement.failed-task` `` を含む行を特定し、write-and-commit 終端の文言を含み、引き続き `Auto-select **retry** once per task`、`Route-back-to-planning is never taken automatically`、`` Full detail: `references/implement-phase.md` Step I.2.c `` を含み、`` `implement` stays `failed` `` を含まないことをアサートする。`tests/test_batch_policies.py` は変更なしで green のまま。
- [ ] 回帰 (TS-7, FR8/NFR5): pin を持つ 3 モジュールを全て実行し、各 pin アサーションが変更後の段落に対して通ることを確認する。負の証明: 3 リテラルのいずれか 1 つを変更前の値に戻すと、正確にそのモジュールだけが失敗する。
- [ ] 異常系 (TS-8, NFR1/NFR3): 編集後に `assertNotIn('rework', normalized_i2c)` と `assertNotIn('append', normalized_i2c)`。implement-phase.md 全体を走査した bare な `git commit` / `git add` 行のリストが空である。
- [ ] 正常系 (TS-9, FR9): `tests/test_implement_routeback_gate.py::TestPluginVersionBumpedInLockstep` が通る — plugin.json と marketplace の `em-workflow` エントリが一致し、`(major, minor) == (0, 1)`、patch > 42、いずれも 0.1.44 を読む。
- [ ] 統合 (TS-10, FR10/NFR4/NFR5): 変更後の `git status --porcelain` が implement-phase.md、batch-mode.md、3 テストモジュール、2 バージョンマニフェストのみに触れており、develop/SKILL.md、workflow-patch.md、validate-worker-output.py、routeback-gate-postcondition/SPEC.md が diff に現れない。`python3 -m unittest discover -s tests` が失敗もエラーもなく exit 0。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 終端 (terminal) | フェーズが制御を返す前に行う、順序付けられた最終手続き。ここでは統合 worktree のリフレッシュ、tip 取得、`implement: failed` の書き込み、`commit-docs.sh` によるコミット、報告。 |
| rejected path | I.2.c の `When the gate does not hold` 以降のブランチ。既に明示的な終端を持つ。 |
| byte pin | テストモジュール内に文書の一節を byte-identical なリテラルとして保持し、等価性をアサートする仕組み。 |
| bounded recovery | exit 4 に対する有界の回復手順。リフレッシュ、tip 再取得、ソースから再導出した同一遷移の再適用、1 回だけ再試行。二度目の exit 4 でフェーズを報告して停止。 |
| carve-out | bounded recovery の適用から除外された唯一の呼び出し点（Step I.2.c の route-back commit）。 |
| 停止条件 3 | develop の停止条件のうち、`failed` / `needs_update` で発火するもの。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 同期範囲: `em-workflow/references/implement-phase.md`（Step I.2.c の abort バレット + batch-mode 段落）**および** `em-workflow/references/batch-mode.md` の Non-packet gates 行 `implement.failed-task` を同期する。`em-workflow/skills/develop/SKILL.md` の停止条件 5 の括弧書きは変更しない。（gate `create-spec.requirement-clarification`、option `include_batch_mode_row`。根拠: batch-mode.md の行は委譲ではなく誤った副作用「`implement` stays `failed`」を独立に再掲しているのに対し、develop/SKILL.md は二度目の失敗で中断するとだけ述べステータスを主張していない。）
- [x] design ステップ: requirements-analyst の推奨をそのまま受理し `skipped`。（gate `create-spec.design-step`、option `decide_autonomously`。理由: 本フィーチャーは 2 つの markdown プロトコル文書 + 3 テストモジュール + 2 バージョンマニフェストのドキュメント整合性修正であり、UI・視覚的サーフェス・CSS / token / theme 成果物・新しいユーザー向けインタラクションを出荷しないため、designer worker が生成するものがない。）
- [x] 前提 A1: PR #6 はマージ済み。implement-phase.md L459-470 の rejected-path 終端（`TERMINAL_TIP` の取得、`implement: failed` の書き込み、`docs({feature}): implement route-back gate rejected` コミット）が abort パスの複製元テンプレートである。統合 worktree 上で存在を確認済み。
- [x] 前提 A2: ベースラインバージョンは `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の双方で 0.1.43 と確認済み。したがって lockstep の目標は 0.1.44。
- [x] 前提 A3: abort コミットのコミットメッセージは実装に委ねる。履歴上で判別可能な程度に `docs({feature}): implement route-back gate rejected` と区別できること。pin するテストはないため、正確な文字列はここでは規定しない。
- [x] 前提 A4: 2 つの abort 呼び出し点（interactive オプション、batch の二度目の失敗）は、コマンド列を重複させる代わりに I.2.c 内の明示的な相互参照で 1 つの記述された手続きを共有してよい。ただし各パスの終端がセクションを離れずに読み取れることを条件とする。
- [x] 前提 A5: リポジトリルートに LICENSE ファイルは存在せず、パッケージマニフェストも存在しない（envelope より）。したがってライセンス検出は SPDX id を返さない。
- [x] 前提 A6: E2E インフラは存在しない（`resolved_input_paths.e2e` が空）。記録すべき e2e_test_command はない。
- [x] 前提 A7: テストコマンドは `python3 -m unittest discover -s tests` のみで、リポジトリルートから実行する（test/README.md）。CLAUDE.md にも test/README.md にも build / lint / format コマンドの定義はない。

### 14.2 未確認・保留事項

なし。全ての機能要件・非機能要件は `status: resolved` である。

## 15. 参考資料

- implement フェーズ仕様: `em-workflow/references/implement-phase.md`（Step I.2.c、Branch & Worktree Model の exit-4 recovery バレット L43-80、rejected-path 終端 L459-470）
- batch モード仕様: `em-workflow/references/batch-mode.md`（Non-packet gates 表、`implement.failed-task` 行 L60）
- develop スキル: `em-workflow/skills/develop/SKILL.md`（停止条件 2 / 3 / 5、Step B の「停止条件 3 との優先関係」L38-40）— 非目標（変更しない）
- コミットヘルパ: `em-workflow/scripts/commit-docs.sh`（RECOVERY CONTRACT）— 非目標（変更しない）
- テストモジュール: `tests/test_implement_routeback_gate.py`、`tests/test_recycled_task_id_consistency.py`、`tests/test_routeback_reset_scope_consistency.py`、`tests/test_batch_policies.py`
- テスト実行方法: `test/README.md`
- バージョンマニフェスト: `em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`
