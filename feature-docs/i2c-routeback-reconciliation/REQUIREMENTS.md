---
title: "i2c-routeback-reconciliation"
created_date: 2026-08-18
status: draft
---

# i2c-routeback-reconciliation - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/references/implement-phase.md` の `### I.2.c: Failed handling` は、
recycled-task-id-consistency と routeback-gate-postcondition という 2 つのフィーチャーの
意図をマージ済みのテキストとして既に main 上に持っている。
タスク記述が置いていた前提（PR #5 が CONFLICTING であり reconciliation が未了）は stale である。

### 1.2 目的

マージ済みテキストが両フィーチャーの意図を矛盾なく表現していることを、再現可能な証跡とともに確定させ、
逸脱箇所とその権威文書を記録する。あわせて PR #5 の処遇を確定して記録する。

### 1.3 スコープ

- 対象: `feature-docs/i2c-routeback-reconciliation/` 配下に置く検証記録の作成のみ。
- 対象外: プロトコル文書・テストマッチャ・version フィールドの変更。
  `em-workflow/references/implement-phase.md`、`tests/test_implement_routeback_gate.py`、
  `tests/test_recycled_task_id_consistency.py` は本フィーチャーにとって read-only な入力である。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| OBJ1 | マージ済みの `### I.2.c: Failed handling` が、recycled-task-id-consistency と routeback-gate-postcondition の両フィーチャーの意図を、矛盾のない 1 つの本文として表現していることを、再現可能な証跡とともに確定させる。 |
| OBJ2 | マージ済みテキストが source SPEC の字義的な記述から意図的に逸脱している箇所と、その逸脱についてどの文書が権威を持つかを記録し、後続の読み手が既に決着した対立を superseded なテキストから蒸し返さないようにする。 |
| OBJ3 | PR #5 の処遇を確定して記録し、「まだマージ不能である」という前提で起票されたタスクを閉じる。 |
| OBJ4 | 成果物を検証記録に限定する。プロトコル文書・テストマッチャ・version フィールドをいずれも変更しない。 |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| 後続の読み手 | マージ済み I.2.c テキストと source SPEC の差分に遭遇し、既に決着した対立を蒸し返しうる読み手（OBJ2）。 |

### 2.3 期待される効果

- superseded な記述が「満たされている」と誤読されず、権威文書が明示される（OBJ2 / NFR3）。
- PR #5 に対して追加の作業が不要であることが記録される（OBJ3 / FR6）。

## 3. ユースケース

該当なし。本フィーチャーの唯一の成果物は markdown の検証記録であり、UI サーフェス・データモデル・
API サーフェスを持たない（design ステップの skip 理由に同じ）。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | ステータス |
|----|--------|-----------|
| FR1 | 調停後のゲート条件が両フィーチャーの受け入れ基準を満たすことの検証 | resolved |
| FR2 | write → commit → cleanup の順序の検証と、superseded になった source 側順序の記録 | resolved |
| FR3 | ゲート却下時の副作用の検証と、両フィーチャーの相反する記述の調停 | resolved |
| FR4 | 2 つの document-contract テストモジュールがマージ済みテキストに対して green であることの検証 | resolved |
| FR5 | version bump — 本フィーチャーには非該当 | resolved |
| FR6 | PR #5 の確定した処遇の記録 | resolved |
| FR7 | 成果物は本フィーチャーのディレクトリ配下の検証記録のみ | resolved |

### 4.2 機能詳細

#### FR1: 調停後のゲート条件が両フィーチャーの受け入れ基準を満たすことの検証

検証記録は、マージ済みの I.2.c route-back ゲートが、routeback-gate-postcondition AC1
（ゲートが「no task has status `merged`」かつ「no task has status `in_progress`」として記述され、
write set は `failed` タスクを `pending` に戻すこと）と、recycled-task-id-consistency AC-3/FR3
（route-back が admissible なのは、journal にイベントを持つすべてのタスクの journal last event が
terminal であるときに限る）を同時に満たすことを示さなければならない。

証跡: `implement-phase.md` の 405-428 行 — 407-409 行の連言、413-418 行の
`merged` 側（workflow.yaml と Step I.2.b step 1 の reconciled state の和として記述）、
418-423 行の `in_progress` 側（workflow.yaml と Step I.2.b の last-event-per-task ルールの和として記述）、
および 423-428 行（2 つ目の和の要素から terminal-last-event 性を導く文）。

記録は、FR3 の precondition が独立したチェックとしてではなく **和の要素として** 満たされていること、
および「no task has status `merged`」が両 SPEC の要求どおり逐語的に残っていることを明記しなければならない。

#### FR2: write → commit → cleanup の順序の検証と、superseded になった source 側順序の記録

検証記録は、マージ済みの admitted path が次の順序を取ることを示さなければならない。

gate decision → integration-worktree refresh → ROUTEBACK_TIP capture →
1 つの ordered workflow.yaml write set → route-back commit → worktree/branch cleanup →
end-of-phase report。

証跡: `implement-phase.md` 444 行（`Commit that write set next, BEFORE any cleanup`）、
450-451 行（`Only once that commit succeeds, clean up worktrees and branches`）、
および 456-459 行に記載された残存 leftover state。

記録は次を明記しなければならない。

- recycled-task-id-consistency の SPEC.md が記述している順序（write set → cleanup → commit。
  SPEC.md 160 行、NFR1 87 行、TS-10 244 行）は **SUPERSEDED** である。
- その supersession と根拠は同 SPEC.md の Merge Note 3 行目（SPEC.md 23 行）が記録している。
- routeback-gate-postcondition FR3/AC3 の「gate decision があらゆる `commit-docs.sh` 呼び出しと
  すべての cleanup に先行する」という要求は、この順序の下でも依然として成立する。

#### FR3: ゲート却下時の副作用の検証と、両フィーチャーの相反する記述の調停

検証記録は、マージ済みの rejected path が、書き込みをちょうど 1 つ（`implement` step の `status` を
`failed` に設定）、およびその書き込みのコミットをちょうど 1 つ
（`docs({feature}): implement route-back gate rejected`）だけ行い、それに refresh と TERMINAL_TIP capture が
先行し、route-back write set・worktree/branch cleanup・route-back commit をいずれも行わないことを
示さなければならない。

証跡: `implement-phase.md` 467-486 行。特に 4 つの却下要因すべての列挙（467-472 行）、
単一書き込みの文（473-479 行）、スコープ付きの no-side-effect の文（480-482 行）。

記録は 2 つの source の記述を明示的に調停しなければならない。

- routeback-gate-postcondition FR2（86-90 行）は `implement: failed` の書き込みを要求する。
- 同フィーチャーの FR3/AC3（47-49 行、91-94 行）は rejected path が
  「commits nothing and mutates nothing」と述べる。
- recycled-task-id-consistency FR4/AC-4（51 行、78 行）は `implement` が `failed` の **ままである**（書き込みなし）
  ことを要求する。

調停後の読み: routeback-gate-postcondition AC3 の "nothing" は ROUTE-BACK の write set・commit・cleanup に
スコープし、terminal status commit にはスコープしない。記録はこの読みを明記し、
recycled-task-id-consistency SPEC.md の Merge Note 2 行目（22 行）が既にこの読みを
「the same guarantee, stated as an explicit write rather than as an absence」として採用していることを
引用しなければならない。

#### FR4: 2 つの document-contract テストモジュールがマージ済みテキストに対して green であることの検証

検証記録は、`tests/test_implement_routeback_gate.py` と `tests/test_recycled_task_id_consistency.py` の
双方が、いずれの pre-merge variant でもなく **マージ済み** の文言と順序を encode していること、
および双方が pass することを示さなければならない。

引用すべき証跡アンカー:

- `test_implement_routeback_gate.py` 486-502 行
  （`test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`。
  gate < refresh < tip < write set < commit < cleanup を assert）
- 同 504-512 行（`test_rejected_path_order_gate_terminal_write_terminal_commit`）
- 同 569 行（`test_implement_is_written_to_failed_and_committed`）
- 同 407-418 行（`in_progress` 側を和として扱う assert 群）
- `test_recycled_task_id_consistency.py` 892-897 行
  （`test_commit_precedes_cleanup_precedes_end_of_phase_report`。
  `commit_idx < cleanup_idx < report_idx` を assert）。その class docstring（864-871 行）が
  commit-before-cleanup の根拠を記録している。
- 同 521-533 行（terminal-last-event precondition と、それが ordered write set より前に位置すること）

#### FR5: version bump — 本フィーチャーには非該当

**NOT APPLICABLE**。タスク記述の 5 番目の受け入れ基準は
`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の lockstep bump を要求していた。
これは `em-workflow/` 配下のファイルを変更することを条件としており、確定したスコープ（`verify_and_close`）は
そのような変更を禁じるため、条件が成立せず bump も生じない。

検証記録はこれを outstanding item ではなく **resolved-not-applicable** として記載し、
2 つのレジストリが既に lockstep であることを観測事実として記録しなければならない:
`em-workflow/.claude-plugin/plugin.json` は `"version": "0.1.45"`、
`.claude-plugin/marketplace.json` の em-workflow エントリは `"version": "0.1.45"`。

あわせて、recycled-task-id-consistency FR9/AC-9 が掲げた 0.1.38 という目標値はマージ時点で満たされており、
以後の bump によって superseded であること、したがって 0.1.45 は同 AC の違反ではないことを注記しなければならない。

#### FR6: PR #5 の確定した処遇の記録

検証記録は PR #5 を **MERGED** として記録しなければならない。オーケストレータが収集した証跡:

- `gh pr view 5` が state MERGED を報告（base main、head `em-workflow/recycled-task-id-consistency/integration`）
- `git merge-base --is-ancestor origin/em-workflow/recycled-task-id-consistency/integration origin/main` が true を返す

記録は、タスク記述の 4 番目の受け入れ基準が第 1 選言のより強い形で満たされていること
（branch は単に mergeable なのではなく、既に merged である）、および PR #5 に対して追加の作業が
不要であることを明記しなければならない。

#### FR7: 成果物は本フィーチャーのディレクトリ配下の検証記録のみ

本フィーチャーが生む唯一の成果物は `feature-docs/i2c-routeback-reconciliation/` 配下の検証記録である。
変更集合には `em-workflow/` 配下のパス、`tests/` 配下のパス、
`em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` のいずれも含めてはならない。
特に `em-workflow/references/implement-phase.md`、`tests/test_implement_routeback_gate.py`、
`tests/test_recycled_task_id_consistency.py` は本フィーチャーの read-only 入力である。

## 5. 非機能要件

### 5.1 非機能要件一覧

| ID | 名称 | ステータス |
|----|------|-----------|
| NFR1 | 証跡に裏づけられ、再チェック可能な主張 | resolved |
| NFR2 | 本フィーチャーのディレクトリ外はゼロ diff | resolved |
| NFR3 | supersession は記録し、黙って落とさない | resolved |
| NFR4 | 挙動変更なし、機械的チェッカの新設なし | resolved |
| NFR5 | ローカルのドキュメント規約 | resolved |

### 5.2 非機能要件詳細

- **NFR1 — 証跡に裏づけられ、再チェック可能な主張**:
  検証記録のすべての主張は、位置特定可能なアンカー（引用句とそのセクション、またはテストモジュールと
  テストメソッド名）を伴う。読み手は履歴を再導出することなくチェックを再実行できる。
  タスク記述の物語のみに依拠した主張を置かない。
- **NFR2 — 本フィーチャーのディレクトリ外はゼロ diff**:
  本変更の `git diff --name-only` は `feature-docs/i2c-routeback-reconciliation/**`
  （および implement フェーズが要求する場合は `test-docs/i2c-routeback-reconciliation/**`）の部分集合である。
  `em-workflow/` 配下、`tests/` 配下、いずれのマニフェストも現れない。
- **NFR3 — supersession は記録し、黙って落とさない**:
  マージ済みテキストが source SPEC の字義的記述から逸脱する箇所では、記録が source の記述・マージ後の記述・
  権威を持つ文書の 3 つを名指しする。recycled-task-id-consistency SPEC.md の Merge Note テーブルの先例に倣う。
  superseded な記述を「満たされている」と提示しない。
- **NFR4 — 挙動変更なし、機械的チェッカの新設なし**:
  本フィーチャーは hook・script・agent・skill・テストマッチャのいずれの変更も導入せず、
  機械的チェッカを新設しない。受け入れ水準は、無変更のスイートに対する
  `python3 -m unittest discover -s tests` の green である。
- **NFR5 — ローカルのドキュメント規約**:
  検証記録はリポジトリの feature-docs 規約に従う。markdown、識別子とファイルパスのバッククォート記法、
  要件が述べる以上の根拠を書かないこと。

### 5.3 テンプレート上のその他の非機能カテゴリ

パフォーマンス要件・セキュリティ要件・可用性要件・互換性要件は本フィーチャーには該当しない。

## 6. UI/UX要件

該当なし。本フィーチャーは UI サーフェスを持たない。

## 7. データ要件

該当なし。本フィーチャーはデータモデルを持たない。

## 8. 外部連携

該当なし。本フィーチャーは API サーフェスを持たない。

## 9. 制約条件

### 9.1 技術的制約

- `em-workflow/references/implement-phase.md`、`tests/test_implement_routeback_gate.py`、
  `tests/test_recycled_task_id_consistency.py` は read-only（FR7）。
- 機械的チェッカを新設しない（NFR4）。
- リポジトリに LICENSE ファイル・パッケージマニフェスト・E2E 基盤は存在しない。

### 9.2 ビジネス上の制約

- 成果物は検証記録のみ。プロトコル文書・テストマッチャ・version フィールドを変更しない（OBJ4）。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:

- なし（FR7 により、成果物は下記デフォルトメンバーの範囲に収まる）

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/i2c-routeback-reconciliation/**`
- `test-docs/i2c-routeback-reconciliation/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、
`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、
およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび
`references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`
（パス形式: `test-docs/i2c-routeback-reconciliation/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| superseded な source 記述が「満たされている」と誤読される | 中 | 逸脱を source 記述・マージ後記述・権威文書の 3 列テーブルで列挙する（NFR3 / AC12） |
| routeback-gate-postcondition AC3 の "nothing" を無スコープに読むと同フィーチャーが自己矛盾する | 中 | route-back の write set・commit・cleanup にスコープする調停読みを明記する（FR3 / ASM4） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| stale な前提（PR #5 が CONFLICTING）に基づいて作業が再開される | 中 | 中 | PR #5 を MERGED として証跡付きで記録する（FR6 / TS8） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1 (FR1): マージ済みの `### I.2.c: Failed handling` を読むと、route-back ゲートが
      「no task has status `merged`」と「no task has status `in_progress`」の連言として
      記述されており（implement-phase.md 407-409 行）、各項が workflow.yaml 由来と
      Step I.2.b journal 由来の和として記述されている（413-423 行）。記録は
      routeback-gate-postcondition AC1 と recycled-task-id-consistency AC-3 の双方が
      この 1 つの文群で満たされていることを引用する。
- [ ] AC2 (FR1): 記録は、ゲートの 2 つ目の和の要素が
      「journal にイベントを持つすべてのタスクの last event が terminal であるときに限り route-back が admissible」
      という性質を成立させていることを implement-phase.md 423-428 行の引用で示し、
      journal イベントを 1 つも持たないタスクが route-back を阻害しないことを注記する。
- [ ] AC3 (FR2): 記録は admitted path の commit-before-cleanup を
      `Commit that write set next, BEFORE any cleanup`（444 行）と
      `Only once that commit succeeds`（450 行）の引用で示し、自身の記述する cleanup-before-commit 順序の
      supersession を記録している文書として recycled-task-id-consistency SPEC.md 23 行を名指しする。
- [ ] AC4 (FR2): 記録は routeback-gate-postcondition AC3 の
      「gate decision before any `commit-docs.sh` invocation and before route-back cleanup」が
      マージ済みテキストでも成立することを、ゲートの文群（405-428 行）が最初の `commit-docs.sh`（445 行）に
      先行することを引用して確認する。
- [ ] AC5 (FR3): 記録は rejected path の唯一の副作用が `implement: failed` の書き込みとその commit であることを
      implement-phase.md 480-482 行の引用で示し、routeback-gate-postcondition AC3 の
      「nothing is committed」を route-back の write set・commit・cleanup にスコープする調停読みを述べ、
      その読みの先行採用として recycled-task-id-consistency SPEC.md 22 行を引用する。
- [ ] AC6 (FR3): 記録はゲート却下の 4 要因をマージ済みテキストの記述どおり列挙し（467-472 行）、
      retry loop・代替の recovery route・degraded route back のいずれも提供されないことを確認する（485-486 行）。
- [ ] AC7 (FR4): 記録は、調停された 3 つの hunk それぞれについて、マージ済みの形を pin している
      `tests/test_implement_routeback_gate.py` または `tests/test_recycled_task_id_consistency.py` の
      テストメソッドを最低 1 つ名指しする。最低限
      `test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`、
      `test_rejected_path_order_gate_terminal_write_terminal_commit`、
      `test_implement_is_written_to_failed_and_committed`、
      `test_commit_precedes_cleanup_precedes_end_of_phase_report` を含む。
- [ ] AC8 (FR4, NFR4): リポジトリルートから実行した
      `python3 -m unittest discover -s tests` が exit 0 で、skip・追加・削除・変更されたテストがない。
      記録は観測したテスト数を、オーケストレータ自身の観測値である 1522 tests OK と併記する。
- [ ] AC9 (FR5): 記録は version bump 要件を非該当と述べ、観測された lockstep ペア
      `em-workflow/.claude-plugin/plugin.json` = 0.1.45 と
      `.claude-plugin/marketplace.json` の em-workflow エントリ = 0.1.45 を記録する。いずれも変更しない。
- [ ] AC10 (FR6): 記録は PR #5 を MERGED として、オーケストレータの 2 つの証跡とともに述べ、
      タスク記述の 4 番目の受け入れ基準への対応を示す。
- [ ] AC11 (FR7, NFR2): 本変更の `git diff --name-only` に `em-workflow/` 配下のパス、
      `tests/` 配下のパス、いずれのマニフェストも現れない。
- [ ] AC12 (NFR1, NFR3): マージ済みテキストと source SPEC の逸脱がすべて 1 つのテーブルに
      3 列（source の記述 / マージ後の記述 / 権威文書）で列挙されており、最低限
      routeback-gate-postcondition AC3 の rejected-path-commit 逸脱と
      recycled-task-id-consistency NFR1/TS-10 の順序逸脱を含む。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 (document assertion, AC1/AC2): `implement-phase.md` を
      `### I.2.c: Failed handling` から `### Supporting cast` まで切り出し、空白を正規化して、
      ゲートの 2 つの連言項と 2 つの和の要素が 1 つの文群に存在すること、
      「no task has status `merged`」が逐語で残っていることを確認する。
- [ ] TS2 (document assertion, AC3/AC4): 同じスライス内で、
      gate < `Refresh the integration worktree first` < `ROUTEBACK_TIP` <
      `make one ordered workflow.yaml write set` < `Commit that write set next, BEFORE any cleanup` <
      `Only once that commit` < `End the phase with a` のインデックス順序を確認する。
- [ ] TS3 (異常系, AC5/AC6): `When the gate does not hold` から `- **abort phase**` までを切り出し、
      `implement: failed` の書き込み、TERMINAL_TIP capture、
      `implement route-back gate rejected` のコミットメッセージ、スコープ付きの ONLY-side-effect の文が含まれ、
      `git worktree remove --force` が 1 度も現れないことを確認する。
- [ ] TS4 (cross-document, AC1/AC5/AC12): routeback-gate-postcondition SPEC.md の AC1-AC3 と
      recycled-task-id-consistency SPEC.md の AC-3/AC-4 をマージ済みスライスと突き合わせ、各々を
      satisfied-verbatim / satisfied-under-the-reconciled-reading / superseded に分類する。
      後の 2 分類には権威文書を名指しする。
- [ ] TS5 (regression, AC7/AC8): リポジトリルートから `python3 -m unittest discover -s tests` を実行し、
      exit 0 であること、`tests/test_implement_routeback_gate.py` と
      `tests/test_recycled_task_id_consistency.py` が単独モジュールとしても pass することを確認する。
- [ ] TS6 (境界値, AC7): `test_recycled_task_id_consistency.py` の TS-10 クラスが
      `commit_idx < cleanup_idx` を assert していること（892-897 行）を確認する。
      すなわち同モジュールが SPEC の記述する cleanup-first 順序から更新されており、
      スイートがどちらの順序も許容せずマージ済み順序を pin していること。
- [ ] TS7 (diff scope, AC9/AC11): 本変更の `git diff --name-only` を実行し、
      `feature-docs/i2c-routeback-reconciliation/**` と `test-docs/i2c-routeback-reconciliation/**` の
      部分集合であること、`em-workflow/references/implement-phase.md`・両テストモジュール・
      両マニフェストがいずれも含まれないことを確認する。
- [ ] TS8 (staleness, AC10): 検証記録がタスク記述の前提（PR #5 CONFLICTING、reconciliation 未了）を
      stale と述べ、それを superseded にした証跡を名指ししていることを確認する。
- [ ] TS9 (エッジケース): 記録が recycled-task-id-consistency FR9/AC-9 の version 目標 0.1.38 を
      historical と注記し、現行の 0.1.45 lockstep ペアが同 AC に違反しないと述べていることを確認する。
- [ ] TS10 (エッジケース): 記録が recycled-task-id-consistency SPEC.md の Merge Note（9-27 行）が
      既に in-repo に存在し、git/gh の証跡とは独立に reconciliation が landed したことの
      裏づけ証跡になっていると注記していることを確認する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 調停後（merged）テキスト | 現在 main 上にある `em-workflow/references/implement-phase.md` の `### I.2.c: Failed handling` の本文。 |
| superseded | source SPEC の字義的記述が、マージ済みテキストによって置き換えられた状態。権威はマージ済みテキスト側にある。 |
| 調停読み（reconciled reading） | routeback-gate-postcondition AC3 の "nothing" を route-back の write set・commit・cleanup にスコープする読み。 |
| admitted path | ゲートが成立したときの I.2.c の経路。 |
| rejected path | ゲートが成立しなかったときの I.2.c の経路。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] スコープ（gate `create-spec.requirement-clarification` / question `scope.reconciliation-already-merged` /
      option `verify_and_close` / source `batch_policy`）:
      タスク記述の前提は stale。I.2.c の reconciliation は既に main 上にあり、本フィーチャーは
      検証と記録のみにスコープされる。`em-workflow/references/implement-phase.md` の編集なし、
      テストマッチャ変更なし、version bump なし。
- [x] PR #5 の状態: `gh pr view 5` が state MERGED を報告（base main、
      head `em-workflow/recycled-task-id-consistency/integration`）。
- [x] ブランチの祖先関係:
      `git merge-base --is-ancestor origin/em-workflow/recycled-task-id-consistency/integration origin/main`
      が true を返す。
- [x] テストスイート: `python3 -m unittest discover -s tests` が 1522 tests、OK を報告。
- [x] 権威関係: マージ済み implement-phase.md のテキストが recycled-task-id-consistency SPEC.md の
      記述と異なる箇所では、マージ済みテキストが権威を持つ（同 SPEC の Merge Note 9-27 行がそう述べている）。
      対象は同 SPEC の Architecture/Data-Flow の順序（write set → cleanup → commit）、NFR1 の順序節、
      TS-10 の文言。その順序のテストレベルの表現については
      `tests/test_recycled_task_id_consistency.py` が権威を持つ。
- [x] 調停読み: routeback-gate-postcondition FR3/AC3 の
      「the rejected path commits nothing and mutates nothing」は、route-back の write set・commit・cleanup に
      スコープすると読む。同フィーチャーの FR2 が `implement: failed` の書き込みを要求しており、
      無スコープの読みでは同フィーチャーが自己矛盾するため。マージ済みテキストはスコープ付きの形を明記しており、
      recycled-task-id-consistency の Merge Note 2 行目が既にこの読みを採用している。
- [x] routeback-gate-postcondition SPEC.md は自身の merge note を持たない（先に landed したフィーチャーであるため）。
      したがって本検証記録が同フィーチャーの AC3 逸脱を記録する唯一の場所である。
- [x] design ステップ（gate `create-spec.design-step` / question `design.step-decision` /
      option `decide_autonomously` / source `batch_policy`）: skip。
- [x] version bump: 不要（スコープ確定の帰結）。
- [x] リポジトリ状況: LICENSE ファイル、パッケージマニフェスト、E2E 基盤はいずれも存在しない。

### 14.2 未確認・保留事項

なし。すべての機能要件・非機能要件が `resolved` である。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: マージ済みの `### I.2.c: Failed handling`（read-only 入力）
- `tests/test_implement_routeback_gate.py`: routeback-gate-postcondition の document-contract テスト（read-only 入力）
- `tests/test_recycled_task_id_consistency.py`: recycled-task-id-consistency の document-contract テスト（read-only 入力）
- `feature-docs/recycled-task-id-consistency/SPEC.md`: Merge Note（9-27 行）を含む source SPEC
- `feature-docs/routeback-gate-postcondition/SPEC.md`: source SPEC
- `em-workflow/.claude-plugin/plugin.json` / `.claude-plugin/marketplace.json`: version の観測対象（変更しない）
