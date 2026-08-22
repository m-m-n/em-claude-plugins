---
title: "routeback-admissibility-exits"
created_date: 2026-08-23
status: draft
---

# routeback-admissibility-exits - 要件定義書

## 1. 概要

### 1.1 背景

implement フェーズの I.2.c ルートバック（route-back）プロトコルには、抜け出せない状態に到達しうる経路が残っている。

- I.2.c のルートバック書き込み集合はタスク id を `pending` に戻し、planner の `replace_all` による採番のやり直しでその id が再発行される。この再発行された id が journal の最終イベント `merged` を引き継ぐと、`queue_launch_guard.py` の `deny_already_merged` が起動を恒久的に拒否する。journal は追記専用でオーケストレーターは書き込まないため、この状態を解除できる書き手が存在しない。
- I.2.a には「ルートバックはどちらのソースから見ても `merged` のタスクが無いときにしか進まないので、退役した id が `merged` の最終イベントを残すことはなく、再採番タスクへの引き継ぎは起きない」という趣旨の不到達性の主張が置かれている。しかし trust-but-verify 経路（merge-task.sh が journal に `merged` を書いたが `git merge-base --is-ancestor` が失敗する場合）では、どちらのゲートソースも `merged` を報告しないためルートバックが通り、この主張は成立しない。
- journal の最終イベントが `launched` のまま実体が飛んでいない（タスクワークツリーもタスクブランチも生きたエージェントも無い）plan は、`launched` を終端化できる書き手が居ないため、abort 以外の出口を持たない。
- I.2.b step 1 の trust-but-verify にある「journal が in-flight と主張しているタスクのワークツリー／ブランチ存在確認」は、その失敗が調停後の状態に何をもたらすかが規定されていない。Stale-`launched` の但し書きは wake フェーズの調停が拾うと述べる一方、I.2.b step 1 と I.2.a はいずれも「最終イベントが `launched` なら他のソースに関わらず常に in-flight」と述べており、両者が噛み合っていない。

### 1.2 目的

implement フェーズ I.2.c ルートバックプロトコルのすべての失敗経路が、ワークフローとして離脱可能な状態で終わるようにする。あわせて、プロトコル文書が自ら主張する不到達性が、書かれているプロトコルに対して真であるようにする。

### 1.3 スコープ

**対象**

- `em-workflow/references/implement-phase.md`（プロトコル本文）
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_implement_routeback_gate.py`
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`（バージョン lockstep）
- `feature-docs/routeback-admissibility-exits/**`、`test-docs/routeback-admissibility-exits/**`

**対象外**

- `em-workflow/hooks/` 配下のフック実装。採用する機構がそれを証明可能な形で要求する場合に限り対象となり、その場合は 4 本すべてを同一変更で扱う（NFR1）。
- PR #5 の main との衝突解消。タスク記述により対象外。本要件はベース 9f5d7ae に対して記述されている。
- デザインステップ。スキップされている（1.4 参照）。

### 1.4 デザインステップ

状態: スキップ。理由: ユーザーに見える UI も描画される出力もデザインシステム入力も持たない、プロトコル文書とテストのみの変更であるため。

## 2. ビジネス要件

### 2.1 ビジネス目標

- implement フェーズ I.2.c ルートバックプロトコルのすべての失敗経路が、ワークフローとして離脱可能な状態で終わること。恒久的に起動不能なタスクを生まず、abort だけが選択肢の plan を残さないこと。
- プロトコル文書自身の不到達性の主張が、書かれているプロトコルに対して真であること。将来の変更が、trust-but-verify 経路によって反証される主張ではなく、正しい前提から推論できるようにすること。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow のオーケストレーター（実行主体） | implement フェーズを進行させ、I.2.c のゲート判定とルートバック書き込み集合を実行する |
| ワークフロー利用者（人間） | I.2.c の AskUserQuestion メニュー（retry / plan へのルートバック / フェーズ abort）とフェーズの終了報告のみを目にする |
| implement-phase.md を変更する将来の作業者 | プロトコル文書の不到達性の主張を前提として推論する |

### 2.3 期待される効果

- 再採番されたタスク id が `merged` を引き継いだ場合でも、自動回復可能な出口が存在する、または本文がその組み合わせの不到達性を述べる。
- stale `launched` を抱えた plan が abort 以外の回復経路を持つ。
- I.2.b step 1 の存在確認が、調停後の状態に対して定義された効果を持つ。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | `merged` を引き継いだ再採番タスク id からの離脱 | オーケストレーター | 高 |
| UC02 | stale `launched` を抱えた plan からの離脱 | オーケストレーター | 高 |
| UC03 | ルートバック不可時のユーザー選択 | ワークフロー利用者 | 中 |

### 3.2 ユースケース詳細

#### UC01: `merged` を引き継いだ再採番タスク id からの離脱

**アクター**: オーケストレーター

**事前条件**:
- merge-task.sh が journal に `merged` を書き込んでいる。
- `git merge-base --is-ancestor` が失敗する（trust-but-verify の不一致）。
- どちらのゲートソースも `merged` を報告せず、in-flight も報告しないため、現行プロトコルではルートバックが admissible と判定される。

**基本フロー**:
1. I.2.c のゲートを評価する。
2. ルートバック書き込み集合がタスク id を `pending` に戻す。
3. planner の `replace_all` が採番をやり直し、同じ id を再発行する。
4. 再発行された id の journal 最終イベントは `merged` のままである。
5. プロトコルが定めた自動回復可能な出口によって、この id は起動可能になる。

**代替フロー**:
- 本文がこの組み合わせを不到達にしている場合、ステップ 1 のゲート判定がルートバックを admit しないことでフローは終了する。

**事後条件**:
- 当該タスク id が恒久的に起動不能な状態で残らない。

#### UC02: stale `launched` を抱えた plan からの離脱

**アクター**: オーケストレーター

**事前条件**:
- あるタスクの journal 最終イベントが `launched` である。
- 実体としては implementer が飛んでいない（タスクワークツリー無し、タスクブランチ無し、生きたエージェント無し）。

**基本フロー**:
1. I.2.b step 1 の trust-but-verify が、journal が in-flight と主張するタスクのワークツリー／ブランチ存在を確認する。
2. 存在確認の結果が調停後の状態に反映される。
3. ルートバックの事前条件が調停後の状態に対して評価され、当該タスクは終端として扱われる。
4. ルートバックが admissible となり、plan は abort 以外の経路で離脱できる。

**代替フロー**:
- プロトコルがゲート却下ブランチ上に明示的な回復手順を置く方式を採る場合、そちらの手順で離脱する。

**事後条件**:
- stale `launched` を抱えた plan に abort 以外の回復経路が存在する。

#### UC03: ルートバック不可時のユーザー選択

**アクター**: ワークフロー利用者

**事前条件**:
- implement フェーズでタスクが失敗し、I.2.c の判定に至っている。

**基本フロー**:
1. I.2.c が AskUserQuestion メニュー（retry / plan へのルートバック / フェーズ abort）を提示する。
2. 利用者が選択する。

**代替フロー**:
- batch モードではルートバックは自動的には提示されない（`implement.failed-task` が retry を 1 回自動選択し、その後 abort する）。

**事後条件**:
- 新しい出口は、このメニュー内で表現できるか、メニュー提示より前に自動的に完了している。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | `merged` を引き継いだ再採番タスク id の出口 | 恒久的に起動不能にならないことを保証する | 高 |
| FR2 | I.2.a の不到達性の論証の是正 | trust-but-verify 経路でも成立する形に述べ直す | 高 |
| FR3 | stale `launched` を抱えた plan の出口 | abort 以外の回復経路を規定する | 高 |
| FR4 | I.2.b step 1 の in-flight 検証に結果を与える | 存在確認の失敗が何を生むかを規定する | 高 |
| FR5 | フック契約との整合維持 | 分類ルール変更をフックの実挙動と整合させる | 高 |
| FR6 | SPEC 側のカバレッジ | 要件・受け入れ基準・テストシナリオとマッチャ更新 | 高 |
| FR7 | プラグインバージョンの lockstep | 2 つのマニフェストを同一の新バージョンにする | 中 |

### 4.2 機能詳細

#### FR1: `merged` を引き継いだ再採番タスク id の出口

**説明**: `em-workflow/references/implement-phase.md` は、I.2.c のルートバック書き込み集合によって `pending` に戻され、planner の `replace_all` の採番やり直しによって再発行されたタスク id が、journal の最終イベント `merged` によって恒久的に起動不能なまま残ることが決して無いことを保証しなければならない。保証の手段は、その状態に対する自動回復可能な出口を定義するか、本文が述べる形でその組み合わせを不到達にするかのいずれでもよい。いずれの手段でも、merge-task.sh が journal に `merged` を書いたが `git merge-base --is-ancestor` が失敗し、どちらのゲートソースも `merged` を報告せずルートバックが進む trust-but-verify のケースを明示的に扱わなければならない。

**ビジネスルール**:
- `replace_all` はいずれかのタスクが `in_progress` / `merged` / `failed` である間はプロトコルエラーである（workflow-patch.md）。したがって変更後もルートバック書き込み集合はすべてのタスクを `pending` にしたまま残さなければならない。
- journal のイベントを一切持たないタスクは、`replace_all` がすべての id を再採番するため引き継ぐものが無く、ルートバックを阻害しない。この性質は変更後も維持されなければならない。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 起動の恒久拒否 | 再採番 id の journal 最終イベントが `merged` | FR1 が定める出口、または本文が述べる不到達性によって発生しない |

#### FR2: I.2.a の不到達性の論証の是正

**説明**: I.2.a の段落が置いている次の主張は、trust-but-verify 経路の下でも成立するよう、FR1 が採る機構（前提条件を狭めるか、carve-out を広げるか）と整合する形で述べ直されなければならない。

現行の文（書き換え・削除の対象）:

> Because route-back proceeds only when no task is `merged` under either source (the widened I.2.c gate above), no retired task id can leave a `merged` last event behind for a renumbered task to inherit, so the recycled-task-id carve-out above stays correctly scoped to `failed` only

**ビジネスルール**:
- I.2.a では「governs only」という語句が既存テストにより禁止されている。述べ直しの文言はこの禁止に抵触してはならない。

#### FR3: stale `launched` を抱えた plan の出口

**説明**: あるタスクの journal 最終イベントが `launched` である一方、実体として implementer が飛んでいない（タスクワークツリー無し、タスクブランチ無し、生きたエージェント無し）plan は、abort 以外のプロトコル定義の回復経路を持たなければならない。例として、ルートバックの事前条件を I.2.b step 1 の調停後の状態に対して評価し stale `launched` を終端として数える方式、またはゲート却下ブランチ上に明示的な回復手順を述べる方式がある。

**ビジネスルール**:
- ゲート却下ブランチのスライス（「When the gate does not hold」からフェーズ abort の箇条書きまで）には、ROUTEBACK_TIP、順序付き書き込み集合を指す語句、強制ワークツリー削除コマンドを含めてはならない。
- 同スライスには現在「回復経路を提供しない」旨の文がテストで固定されている。同ブランチに回復経路を足す方式を採る場合、この固定と衝突するため、当該マッチャを同一変更で更新しなければならない（FR6 / AC-7）。上流で stale `launched` を再分類する方式ではこの衝突は起きない。

#### FR4: I.2.b step 1 の in-flight 検証に結果を与える

**説明**: I.2.b step 1 の trust-but-verify にある「journal が in-flight と主張しているタスクのワークツリー／ブランチ存在確認」は、調停後の状態に対する効果が明記されなければならない。現状は、Stale-`launched` の但し書きが wake フェーズの調停が stale `launched` を「拾う」と主張する一方、I.2.b step 1 と I.2.a はいずれも「最終イベントが `launched` なら他のソースに関わらず常に in-flight」と述べており、この確認の失敗が何を生むかを述べたルールが存在しない。

#### FR5: フック契約との整合維持

**説明**: 変更後の分類ルールは、フック分類表および 4 本のキューフックの実挙動と整合していなければならない。`queue_launch_guard.py`、`queue_failure_net.py`、`queue_taskstop_net.py` は journal の最終イベントのみから判定し、`queue_stop_guard.py` はこれに加えて `tasks.{T}.status` を読む。採用する機構がフックの挙動変更を要求する場合、4 本すべてを同一変更で検討しなければならない。

#### FR6: SPEC 側のカバレッジ

**説明**: プロトコル変更には、本フィーチャーの REQUIREMENTS.md / SPEC.md における対応する要件・受け入れ基準・テストシナリオと、固定リテラルを書き換えた箇所すべてについての `tests/test_recycled_task_id_consistency.py` および `tests/test_implement_routeback_gate.py` のマッチャ更新が伴わなければならない。

#### FR7: プラグインバージョンの lockstep

**説明**: `em-workflow/` 配下のファイルが変わるため、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` を同一変更で同じ新バージョンに引き上げなければならない（現在の共通値: 0.1.47）。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。実行時性能に影響する変更ではない。

### 5.2 セキュリティ要件

- 新たな攻撃面を作らない。本変更はドキュメントとテストで構成されることが見込まれている。
- フックに手を入れる場合、既存の防御（journal の O_NOFOLLOW オープン、flock で直列化した compare-and-append、タスク id と絶対ワークツリーパスの検証、agents.jsonl / journal.jsonl の同一ディレクトリ封じ込め）と fail-open の慣行を維持しなければならない。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

- **NFR1 フックコードは既定で不変**: 採用機構が証明可能な形で要求しない限り、`em-workflow/hooks/` 配下のフックは変更しない。変更する場合は `queue_launch_guard.py` / `queue_stop_guard.py` / `queue_failure_net.py` / `queue_taskstop_net.py` を一括で扱う。
- **NFR2 テストモジュールの規律**: 対象 2 モジュールは固定の規約に従う。新しい不在アサーションには必ず変更前の逐語サンプルに対する negative proof を対にする。変更前サンプルには必ず非空虚性を担保する retained anchor ガードを添える。テストの削除・skip をしない。モジュールのテストメソッド数を減らさない。
- **NFR3 implement-phase.md の単一情報源規律**: ルールは 1 箇所だけが所有し、他所からは引用する。再掲しない。現行の I.2.c ゲート本文（所有ルールとして引用し再掲しない旨の断り書き）とフック分類表が既に従っている慣行。
- **NFR4 スイート green**: リポジトリルートから `python3 -m unittest discover -s tests` が通る。
- **NFR5 裸の git commit / add 行を導入しない**: implement-phase.md は commit-docs.sh の外で、裸の `git commit` または `git add -A` 呼び出しに一致するシェル行を導入しない（`TestContainmentAndInvariants.test_no_bare_git_commit_or_add_lines` が固定）。

### 5.5 互換性要件

該当なし。

## 6. UI/UX要件

### 6.1 画面設計要件

ユーザーに見える面は I.2.c の AskUserQuestion メニュー（retry / plan へのルートバック / フェーズ abort）とフェーズの終了報告のみである。新しい出口はこのメニュー内で表現できるか、メニュー提示より前に自動的に起きなければならない。batch モードではルートバックは自動的には提示されない（`implement.failed-task` が retry を 1 回自動選択し、その後 abort する）。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

### 7.1 データモデル概要

新規のデータモデルは無い。既存の journal（追記専用、最終イベントで判定）と `tasks.{T}.status` を扱う。

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| journal | 最終イベント | enum | ○ | `launched` / `merged` / `failed` など。`queue_launch_guard.py` / `queue_failure_net.py` / `queue_taskstop_net.py` はこれのみで判定する |
| workflow.yaml | `tasks.{T}.status` | enum | ○ | `pending` / `in_progress` / `merged` / `failed`。`queue_stop_guard.py` が journal に加えて読む |

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

該当なし。

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- journal は追記専用であり、オーケストレーターは書き込まない。したがって journal の状態を「退役」させられる書き手は限られる。
- `queue_launch_guard.py` は journal の最終イベントが `merged` の起動をすべて拒否する（`deny_already_merged`）。読むのは journal のみである。
- `queue_failure_net.py` は実際の SubagentStop でのみ発火し、`queue_taskstop_net.py` は TaskStop ツール呼び出しの完了後にのみ発火する。したがって「許可されたが実際には開始されなかった起動」は、終端化できる書き手が居ないまま `launched` を残す。
- I.2.c の当該セクション内では 2 つのトークンが既存テストにより禁止されている。そのうち一方は journal への書き込みを表す動詞であるため、journal の機構に関する記述を I.2.c に置くことはできず、その種の文言は I.2.b または Supporting cast 側へ寄せられる。（本文書は禁止トークンそのものを再掲しない。）
- I.2.a では「governs only」という語句が禁止されている。
- ゲート却下ブランチのスライスに対する制約は FR3 のビジネスルールに記載のとおり。
- `replace_all` はいずれかのタスクが `in_progress` / `merged` / `failed` である間はプロトコルエラーである（workflow-patch.md）。

### 9.2 ビジネス上の制約

- タスク記述が挙げた修復案（defect 1: 前提条件を狭める vs carve-out を広げる、defect 2: 調停後状態を前提条件にする vs 明示的な回復手順を置く）は候補であって決定ではない。本要件はいずれも選べるよう成果（outcome）として記述されている。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/implement-phase.md`
- `tests/test_recycled_task_id_consistency.py`
- `tests/test_implement_routeback_gate.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `em-workflow/hooks/queue_launch_guard.py`（NFR1 の条件を満たす場合のみ）
- `em-workflow/hooks/queue_stop_guard.py`（同上）
- `em-workflow/hooks/queue_failure_net.py`（同上）
- `em-workflow/hooks/queue_taskstop_net.py`（同上）

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/routeback-admissibility-exits/**`
- `test-docs/routeback-admissibility-exits/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| ゲート却下ブランチに固定されている「回復経路を提供しない」旨の文と、同ブランチへの回復経路追加が衝突する | 高 | 上流での stale `launched` 再分類を採るか、当該マッチャを同一変更で更新し変更前バイト列に対する negative proof を対にする（AC-7） |
| I.2.c 内の 2 つの禁止トークンにより、journal 機構の記述を I.2.c に置けない | 中 | 該当文言を I.2.b または Supporting cast 側に置く（NFR3 の単一情報源規律に従い、I.2.c からは引用のみ） |
| 分類ルールを変えると 4 本のフックの前提と食い違いうる | 高 | FR5 / NFR1 に従い 4 本すべてを同一変更で検討する |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 恒久的に起動不能なタスクが本番のワークフローで発生する | 中 | 高 | FR1 の出口または不到達性の明文化 |
| abort しか選べない plan が発生する | 中 | 高 | FR3 の回復経路 |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: implement-phase.md が、引き継がれた journal 最終イベントが `merged` である再採番タスクに対する自動回復可能な出口を定義する。または本文がその組み合わせを、journal の `merged` が `git merge-base --is-ancestor` に失敗するケースを含めて不到達にする。（FR1, FR2）
- [ ] AC-2: implement-phase.md が、stale `launched` を抱えた plan に abort 以外の回復経路を定義し、そのようなタスクに対して I.2.b step 1 のワークツリー／ブランチ存在確認が何を生むかを述べる。（FR3, FR4）
- [ ] AC-3: I.2.a の不到達性の段落が、trust-but-verify 経路によって反証される論拠をもはや主張していない。`failed` のみという carve-out の適用範囲が、AC-1 の機構と整合する形で再論証されるか拡張されている。（FR2）
- [ ] AC-4: REQUIREMENTS.md / SPEC.md が AC-1〜AC-3 に対応する要件・受け入れ基準・テストシナリオを持ち、対象 2 テストモジュールが NFR2 の求める対の回帰証明つきでそれらを表明する。（FR6, NFR2）
- [ ] AC-5: `python3 -m unittest discover -s tests` が通る。（NFR4）
- [ ] AC-6: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` が同一バージョンで一致し、その値が 0.1.47 より厳密に大きい。（FR7）
- [ ] AC-7: 生き残ったテストが依然として固定している implement-phase.md のリテラルはバイト単位で不変であり、意図的に書き換えられたリテラルはすべて同一変更内でマッチャが更新され、変更前バイト列に対する negative proof を伴う。（NFR2, NFR3, NFR5）

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1（文書契約）: I.2.c の admissibility 本文が AC-1 の要求する出口（または不到達性）を述べていることを、I.2.c セクションの空白正規化スライスに対して表明する。
- [ ] TS-2（文書契約）: AC-2 の stale `launched` 回復経路が存在し、I.2.b step 1 の存在確認に明記された結果があることを表明する。
- [ ] TS-3（不在＋対の negative proof）: 反証された I.2.a の論拠文が消えていることを、ベース 9f5d7ae から採取した逐語の変更前サンプルに対して証明する。
- [ ] TS-4（マッチャ更新の回帰証明）: 書き換えた固定リテラルごとに回帰証明を置く（特に `tests/test_recycled_task_id_consistency.py` の終端 journal 最終イベントのリテラルを書き換えた場合）。それぞれに非空虚性を担保する retained anchor ガードを添える。
- [ ] TS-5（保持アサーション）: I.2.c 見出しのバイト同一性、I.2.c の末尾としての batch モード段落のバイト同一性、I.2.b step 3 の commit-docs.sh 行折り返しリテラル、I.2.a の Select リテラル、Step I.0 の pending ステータスリテラルがいずれも生き残る。
- [ ] TS-6（不変条件）: I.2.c セクション全体で 2 つの禁止トークンが不在のままであること、I.2.a に「governs only」が無いこと、「never reads workflow.yaml」の主張がどこにも無いこと、裸の git commit / add 行が無いこと。
- [ ] TS-7（バージョン lockstep）: プラグインマニフェストとマーケットプレイスのエントリが一致し、パッチ番号が 47 より厳密に大きい。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| ルートバック（route-back） | implement フェーズ I.2.c から plan フェーズへ戻す経路。書き込み集合がタスク id を `pending` に戻す |
| trust-but-verify | journal が主張する状態を別ソース（`git merge-base --is-ancestor`、ワークツリー／ブランチ存在）で検証する I.2.b の仕組み |
| stale `launched` | journal 最終イベントが `launched` だが、実体として implementer が飛んでいない状態 |
| 再採番タスク id | planner の `replace_all` により採番がやり直され、退役した id が再発行されたもの |
| ゲートソース | I.2.c の admissibility ゲートが参照する 2 つの判定元 |
| retained anchor ガード | 変更前サンプルに対する不在アサーションが空虚に成立していないことを担保する、残存部分への肯定アサーション |

## 14. 確認事項

### 14.1 確認済み事項

- [x] スコープ: `em-workflow/references/implement-phase.md`、対象 2 テストモジュール、2 つのバージョンマニフェスト。フック実装は、採用機構が 4 本すべての変更を証明可能な形で要求しない限り不変（タスク記述自身の制約）。
- [x] 修復案の扱い: タスク記述の修復案（defect 1: 前提条件を狭める vs carve-out を広げる、defect 2: 調停後状態を前提条件にする vs 明示的な回復手順）は候補であって決定ではない。要件は成果として記述し、plan フェーズがいずれかを選べるようにする。
- [x] ベース: PR #5 の main との衝突解消は対象外（タスク記述による）。本要件はベース 9f5d7ae に基づく。
- [x] デザインステップ: スキップ。

### 14.2 未確認・保留事項

- [ ] 統合ワークツリー直下に LICENSE ファイルが存在しないため、プロジェクトの SPDX 識別子は未解決である。推測せず none として記録する。
- [ ] `feature-docs/recycled-task-id-consistency/reviews/round2.yaml`（finding id: 29b99dea6a37377d / c431ec8ba89742db）は envelope で供給されておらず、読んでいない。これらの id は出所（provenance）としてのみ保持する。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: 変更対象のプロトコル本文（I.2.a / I.2.b / I.2.c）
- `em-workflow/references/workflow-patch.md`: `replace_all` の前提条件
- `tests/test_recycled_task_id_consistency.py`: 再採番タスク id の整合性テスト
- `tests/test_implement_routeback_gate.py`: I.2.c ルートバックゲートのテスト
- `em-workflow/hooks/queue_launch_guard.py` / `queue_stop_guard.py` / `queue_failure_net.py` / `queue_taskstop_net.py`: キューフック 4 本
- `feature-docs/recycled-task-id-consistency/reviews/round2.yaml`: finding id 29b99dea6a37377d / c431ec8ba89742db（出所のみ。未読）
