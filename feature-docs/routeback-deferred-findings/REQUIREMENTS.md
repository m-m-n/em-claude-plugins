---
title: "routeback-deferred-findings"
created_date: 2026-09-26
status: draft
---

# routeback-deferred-findings - 要件定義書

## 1. 概要

### 1.1 背景

feature `routeback-admissibility-exits` の review round 3 で、6 件の findings が `deferred` のまま残っている。いずれも `em-workflow/references/implement-phase.md` の I.2.b / I.2.c 周辺にある。

| stable_id | severity | 観点 | 指摘 |
| --- | --- | --- | --- |
| `12839a507a7df994` | critical | spec | FR3/AC-2 が名指しする stale `launched` 状態に abort 以外の復旧路が無い |
| `2da3c75adac32650` | high | spec | ancestor 検証失敗 `merged` タスクが自認の行き止まりになり Objectives 第 1 項に反する |
| `bc57aa350bb027c7` | high | spec | 候補集合を前セッション由来の `launched` に限定したため、同一セッション内 stale `launched` に復旧が届かない |
| `59e58726b1b22211` | high | architecture | Failed-task resolution invariant violated for ancestor-check-failure state |
| `94de80a315821a55` | medium | architecture | `agents.jsonl` の読み手集合と欠損時の影響が SSOT（`workflow-schema.md`）とドリフトしている |
| `9cc0ce6b64087d2f` | medium | architecture | status semantics 不変条件を破る状態を SSOT 未更新のまま consumer 側で宣言している |

記録は `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` にある。この記録は変更せず、本フィーチャーの文書が上記 stable_id を引用する。

### 1.2 目的

- round 3 で deferred となった 6 件（`12839a507a7df994`、`2da3c75adac32650`、`bc57aa350bb027c7`、`59e58726b1b22211`、`94de80a315821a55`、`9cc0ce6b64087d2f`）を解消する。
- 再開した無人実行が abort、またはそれと同等の gate-rejected terminal でしか終われない protocol 上の経路を取り除く。対象は、成果物が欠けた stale `launched` タスクと、ancestor 検証に落ちた journal `merged` タスクの 2 つ。
- `implement-phase.md` と `workflow-schema.md` の間にある、failed タスクの status semantics と、`agents.jsonl` の読み手集合・index 欠損時の影響についてのドリフトを取り除く。

### 1.3 スコープ

- `em-workflow/references/implement-phase.md`（I.2.a / I.2.b / I.2.c / Supporting cast）
- `em-workflow/references/workflow-schema.md`（journal writer-set 段落、`agents.jsonl` 段落）
- `em-workflow/scripts/recover-orphaned-task.py`
- `em-workflow/scripts/journal-append-failed.py`
- `tests/` 配下のテスト
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version

対象外:
- `queue_launch_guard.py` と `merge-task.sh`（変更しない）
- `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` と、同フィーチャーの SPEC / REQUIREMENTS（変更しない）

## 2. ビジネス要件

### 2.1 ビジネス目標

1.2 の 3 項目と同じ。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の orchestrator | implement フェーズの reconcile（I.2.b）と失敗タスクの解決（I.2.c）を実行する主体 |
| em-workflow の利用者 | 無人実行（batch）を中断後に再開する Claude Code 利用者 |

### 2.3 期待される効果

- 成果物が欠けた stale `launched` タスクが、証明が得られた場合に retry と route back to planning の両方へ到達できる。
- ancestor 検証に落ちた journal `merged` タスクが、journal `failed` を経て retry と route back to planning の両方へ到達できる。
- `workflow-schema.md` の Status semantics「A `failed` task resolves ONLY by retry or by routing back to planning」が例外なくすべての状態で成り立つ。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 成果物が欠けた stale `launched` タスクの復旧 | orchestrator | 高 |
| UC02 | ancestor 検証に落ちた journal `merged` タスクの出口 | orchestrator | 高 |

### 3.2 ユースケース詳細

#### UC01: 成果物が欠けた stale `launched` タスクの復旧

**アクター**: orchestrator

**事前条件**:
- タスクの journal 最終イベントが `launched`
- task worktree と task branch の少なくとも一方が存在しない
- そのタスクの `Task()` 呼び出しが、この reconcile step 自身の currently-outstanding な呼び出しに含まれない

**基本フロー**:
1. I.2.b step 1 がこのタスクを、両方存在する候補集合と同じ not-live 判定に合流させる。
2. Agent index lookup、Recovery、Orphan recovery、Same-session extension の順で終了の証明を試みる。
3. 証明が得られたら、journal に終端 `failed` イベントが既存の reason で記録される。
4. step 1 が同じ reconcile step 内で journal を再 replay する。
5. step 3・5 と I.2.c が `failed` を見て、retry と route back to planning に到達できる。

**代替フロー**:
- 証明が得られない場合は Residual（journal 不変、タスクは in-flight、gate-rejected terminal、報告にタスク名を記載）となる。

**事後条件**:
- 証明が得られた場合、タスクの journal 最終イベントは `failed`。

#### UC02: ancestor 検証に落ちた journal `merged` タスクの出口

**アクター**: orchestrator

**事前条件**:
- タスクの journal 最終イベントが `merged`
- `git merge-base --is-ancestor <task branch> em-workflow/{feature}/integration` が失敗する
- そのタスクの `Task()` 呼び出しが、この reconcile step 自身の currently-outstanding な呼び出しに含まれない

**基本フロー**:
1. 既存の drain / outstanding-call 規則のもとで、元の実行の終了を確認する。
2. `em-workflow/scripts/journal-append-failed.py` を `--reason merge-unverified` で 1 回呼ぶ。
3. step 1 が同じ reconcile step 内で journal を再 replay し、タスクの journal 最終イベントが `failed` になる。
4. 第 3 route-back conjunct が当たらなくなり、retry と route back to planning（gate に従う）の両方に到達できる。

**代替フロー**:
- helper が非 0 で終了するか、append 以外の outcome を報告した場合、journal は変わらない。journal `merged` かつ reconciled `failed` についての既存の記述がそのタスクを支配する。第 3 conjunct が route-back を阻み、gate-rejected の原因列挙がそのタスクを挙げ、報告にタスク名が載る。

**事後条件**:
- helper が append した場合、タスクの journal 最終イベントは `failed`（reason `merge-unverified`）。
- retry は既存の I.2.c drain と I.2.a resume guard（worktree を保持）に従う。親ブランチがすでに task branch を含む場合、`merge-task.sh` が `merged` を再記録する（`merge-task.sh:116-118`）ため、後続の reconcile がマージを検証する。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 成果物が欠けた stale `launched` を既存の証明チェーンに通す（`12839a507a7df994`） | I.2.b step 1 の not-live 判定対象を、成果物欠損・部分欠損の `launched` に広げる | 高 |
| FR2 | 証明チェーンのスクリプトが成果物欠損を証拠として受け入れる | `recover-orphaned-task.py` の step 1 が `no` でチェーンを終えない | 高 |
| FR3 | `bc57aa350bb027c7` を解消済みとして記録し、pin する | 解消根拠を記録し、候補集合の述語を doc-contract テストで pin する | 高 |
| FR4 | ancestor 検証に落ちた journal `merged` タスクの自動出口（`2da3c75adac32650`） | `merge-unverified` で helper を呼び、journal を `failed` にする | 高 |
| FR5 | helper は locked な `merged` の上でだけ `merge-unverified` を受け入れる | `journal-append-failed.py` の reason を 3 値に広げる | 高 |
| FR6 | failed タスクの status-semantics 例外を撤去する（`59e58726b1b22211`、`9cc0ce6b64087d2f`） | I.2.c の行き止まり記述を置き換え、SSOT は無条件のまま保つ | 高 |
| FR7 | `workflow-schema.md` の journal writer-set 段落に新しい reason 値を記録する | `merge-unverified` を追加的な reason 値として記載する | 中 |
| FR8 | SSOT に `agents.jsonl` の読み手集合と index 欠損時の影響を記載する（`94de80a315821a55`） | `workflow-schema.md` の `agents.jsonl` 段落を更新する | 中 |
| FR9 | version bump | em-workflow を 0.2.10 から 0.2.11 に上げる | 中 |
| FR10 | テスト | 変更した protocol 記述ごとの doc-contract assertion と、スクリプトのテスト | 高 |

### 4.2 機能詳細

#### FR1: 成果物が欠けた stale `launched` を既存の証明チェーンに通す（`12839a507a7df994`）

**説明**:
implement-phase.md I.2.b step 1 で、次の 3 条件をすべて満たすタスクを対象にする。

- journal の最終イベントが `launched`
- task worktree と task branch の少なくとも一方が存在しない（両方欠損、またはいずれか一方のみの部分欠損）
- その `Task()` 呼び出しが、この reconcile step 自身の currently-outstanding な呼び出しに含まれない

このタスクは、両方存在する候補集合と同じ not-live 判定に、次の順で合流する。

1. Agent index lookup。task id をキーとし、worktree を必要としない。Agent index writer の orchestrator-read rule に従う（引用のみで再掲しない）。
2. Recovery。harness の stop tool を使い、その後 stop-tool recorder が終端 `failed` イベントを記録する。
3. Orphan recovery（legacy chain）。
4. Same-session extension。

**ビジネスルール**:
- 成果物の欠損は観測された証拠にとどまり、それ単独で終了の証明とはみなさない。
- 次は変更しない: outstanding-call 除外、termination conjunct、stop-result conjunct、agent-identity binding、append 時の launch-identity 再確認。
- 証明が得られた場合、journal に既存の reason（`orphaned` / `stale-launched`、または recorder 自身の reason）で終端 `failed` イベントが入る。step 1 は同じ reconcile step 内で再 replay する。step 3・5 と I.2.c は `failed` を見て、retry と route back to planning の両方に到達できる。
- Residual（journal 不変、タスクは in-flight、gate-rejected terminal、報告にタスク名を記載）は、証明が得られない場合にだけ残る。
- 現行 566-584 行の文言を置き換える。現行の文言は、この状態で recovery を 'without an Agent index lookup' で起動し、'no stop-tool call occurs' とし、'falls to the same Residual treatment' としている。

#### FR2: 証明チェーンのスクリプトが成果物欠損を証拠として受け入れる

**説明**:
`em-workflow/scripts/recover-orphaned-task.py` の `evaluate_stale_launched_chain` step 1（650 行）で、`--worktree-present no` または `--branch-present no` があってもチェーンを終えない。観測値は証拠として持ち回り、チェーンは残りの step を変更なしで続ける。

**入力**:
- `--worktree-present`: `yes` / `no` - task worktree の観測結果
- `--branch-present`: `yes` / `no` - task branch の観測結果
- `--task-worktree`: パス - タスクの期待 worktree パス（`$WT_ROOT/{T}`）。そのパスが存在するかどうかに関わらず渡す

**ビジネスルール**:
- `task-artifacts-missing` は、closed な 16 値の SC6 reason-code 集合での固定位置を保つ。出すのは、成果物の証拠入力が無いか、正確に `yes` / `no` のどちらでもないとき、つまり成果物の状態が観測されていないときだけにする。
- 成果物入力の判定は、agent-index の読み取り・パスの組み立て・ファイルの open より前に行う（現行どおり）。
- identity-binding step は `--task-worktree` を、Agent index エントリに記録された worktree と文字列として比較する。
- モジュール docstring の呼び出し側前提条件（'the task worktree and task branch exist'）と step 1 の説明を、この変更に合わせて更新する。
- implement-phase.md の Orphan recovery 候補の説明（'task worktree and task branch both present'、588-592 行）と、Same-session extension の step（'both observed present (else `task-artifacts-missing`)'、645-647 行）を、広げた候補集合と狭めたコードの意味に合わせて更新する。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `task-artifacts-missing` | 成果物の証拠入力が無い、または `yes` / `no` 以外 | agent-index の読み取り・ファイル open より前に residual を返す |
| `agent-termination-unproven` | 終了の証拠が無い | residual を返し、journal はバイト単位で不変 |
| `stop-result-unproven` | stop 結果の証拠が無い | residual を返し、journal はバイト単位で不変 |

#### FR3: `bc57aa350bb027c7` を解消済みとして記録し、pin する

**説明**:
本フィーチャーの REQUIREMENTS / SPEC に、`bc57aa350bb027c7` が HEAD 時点で解消済みであることを、次の 2 つの根拠とともに記録する。prose は修正し直さない。

- implement-phase.md 520-523 行: 候補集合の述語 'whose `Task()` call is not among this reconcile step's own currently-outstanding calls'。セッションをキーにしていない。
- implement-phase.md 633-660 行: Same-session extension。reason `stale-launched` の journal `failed` に到達する。

**ビジネスルール**:
- 新しい doc-contract テストで、候補集合の述語を pin する。現状この述語を pin しているテストは無い。
- そのテストには、loop-2 の文言（候補を現セッション開始前に記録された `launched` に限定していた文言）に対する negative proof を付ける。

#### FR4: ancestor 検証に落ちた journal `merged` タスクの自動出口（`2da3c75adac32650`）

**説明**:
I.2.b step 1 の ancestor-check の項で、次の場合に orchestrator が動く。

- `git merge-base --is-ancestor <task branch> em-workflow/{feature}/integration` が失敗する
- タスクの journal 最終イベントが `merged`
- その `Task()` 呼び出しが、この reconcile step 自身の currently-outstanding な呼び出しに含まれない

**処理**:
1. `merged` イベントはエージェント終了の証明ではないので、既存の drain / outstanding-call 規則のもとで、元の実行の終了を先に確認する。
2. `em-workflow/scripts/journal-append-failed.py` を `--reason merge-unverified` で 1 回呼ぶ。
3. step 1 は同じ reconcile step 内で journal を再 replay する。これにより reconciled state だけでなく、タスクの journal 最終イベントも `failed` になる。
4. 第 3 route-back conjunct はこのタスクに当たらなくなる。retry（launch guard は `failed` の後の launch を許可する）と route back to planning（gate に従う）の両方に到達できる。

**ビジネスルール**:
- 第 3 conjunct と `queue_launch_guard.py` は変更しない。
- helper が非 0 で終了するか、append 以外の outcome を報告した場合、journal はそのまま残る。journal `merged` かつ reconciled `failed` についての既存の記述がそのタスクを支配する。第 3 conjunct が route-back を阻み、gate-rejected の原因列挙がそのタスクを挙げ、報告にタスク名が載る。
- タスクの retry は、既存の I.2.c drain と I.2.a resume guard（worktree を保持）に従う。親ブランチがすでに task branch を含む場合、`merge-task.sh` が `merged` を再記録する（`merge-task.sh:116-118`）ので、後続の reconcile がマージを検証する。

#### FR5: helper は locked な `merged` の上でだけ `merge-unverified` を受け入れる

**説明**:
`em-workflow/scripts/journal-append-failed.py` の `VALID_REASONS` を `{orphaned, stale-launched, merge-unverified}` に広げる。この定数への意図した変更として行う。

**入力**:
- `--reason`: `orphaned` / `stale-launched` / `merge-unverified`
- `--launch-at`: reason `merge-unverified` では使わない

**出力**:
- outcome: `appended` / `noop_terminal` / `launch_changed`（語彙は変更しない）

**ビジネスルール**:
- reason `merge-unverified` の場合、同じ排他ロック下の replay の中で、タスク自身の最終イベントが `merged` のときだけ `failed` を append する。フィールドは `event`、`task`、`at`、`reason` の順。
- 最終イベントが `launched`、`failed`、イベント無し、その他の値の場合は append しない。
- `merge-unverified` で append しない場合は `noop_terminal` を報告し、journal はバイト単位で不変に保つ。
- `orphaned` と `stale-launched` の判定は変えない。これらは `launched` の上でだけ append し、最終イベントが `merged` なら no-op のまま（`test_final_event_merged_is_noop` は残す）。
- outcome の語彙と exit-code の契約は変えない。
- docstring と argparse の help に、新しい reason とその別個の前提条件を記載する。

#### FR6: failed タスクの status-semantics 例外を撤去する（`59e58726b1b22211`、`9cc0ce6b64087d2f`）

**説明**:
I.2.c（908-930 行）の ancestor 失敗に関する prose を置き換える。新しい記述は、このタスクが I.2.b step 1 の生成した journal `failed` イベントを持って、通常の retry / route back to planning / abort メニューに到達する、と述べる（I.2.b step 1 は引用のみで再掲しない）。

置き換える prose:
- 'choosing retry there reaches the launch guard's permission denial ...'
- 'an outcome reached without selecting abort'
- 'in effect the same dead end ...'
- 'the only way out is a human ...'
- 'This is the one state where workflow-schema.md's status semantics ... are not met by an automated path; the gap is confined to this single case ...'

**ビジネスルール**:
- 新しい文言に 'append' と 'rework' のトークンを使わない。
- `workflow-schema.md` の Status semantics の項「A `failed` task resolves ONLY by retry or by routing back to planning」は無条件のまま保つ。この変更の後、すべての状態でこれが成り立つ。SSOT に例外は加えない。
- 依存する記述を同じ変更の中で調整する。
    - I.2.a 327-332 行（'the launch guard denies the retry instead — I.2.c owns that narrower outcome'）を、新しい経路と、helper 失敗時に残るケースを述べる記述にする。
    - I.2.b の orphan ブロックの 'This is the ONLY case in which the orchestrator's own action results in an append to `journal.jsonl`'、Supporting cast の Journal の項の単一例外、Stale-`launched` caveat の 'the sole exception to the Journal bullet's rule' は、いずれも `merge-unverified` の呼び出しを同じ helper 例外の一部として挙げる。orphan attempt が orchestrator による唯一の append だと主張する記述を残さない。
- abort の項は変えない。`merge-unverified` による失敗は、既存の 'otherwise' 節により `failed_kind: decision` になる。
- batch の段落は変えない。

#### FR7: `workflow-schema.md` の journal writer-set 段落に新しい reason 値を記録する

**説明**:
`workflow-schema.md` の writer-set 段落（397-422 行）に、`merge-unverified` を既存の `failed` reason フィールドの 3 つ目の追加的な値として記載する。同じ helper が書き、I.2.b step 1 の ancestor-check 分岐からだけ呼ばれる（リポジトリ相対パスで引用し、再掲しない）。writer は増えない。

**ビジネスルール**:
- 'Its writer set is unambiguous' と 'outside this one exception' の間のスクリプト名の列挙は、ちょうど 5 つの名前のまま保つ。
- 'outside this one exception' の文字列を残す。
- `failed_kind` の節は変えない（fail-closed の `decision`）。

#### FR8: SSOT に `agents.jsonl` の読み手集合と index 欠損時の影響を記載する（`94de80a315821a55`）

**説明**:
`workflow-schema.md` の `agents.jsonl` 段落（424-444 行）を同じ変更の中で更新する。

**ビジネスルール**:
- 読み手をすべて挙げる。
    - `queue_taskstop_net.py`（stop 時）
    - `queue_failure_net.py` の agent-index フォールバック
    - orchestrator の I.2.b step 1 の Agent index lookup と Recovery（Orchestrator-side read）
    - `recover-orphaned-task.py`
- index が無い・古い場合、stale `launched` タスクについて I.2.b step 1 の not-live 判定も未解決のままになることを記載する。その結果は implement-phase.md I.2.b から引用し、再掲しない。
- 次の文言を置き換える。
    - 'read by `queue_taskstop_net.py` at stop'
    - 'its absence only degrades the stop-tool recorder to a no-op'
    - '`agents.jsonl` exists solely to make a stop resolvable back to a task'
- 次の文言は残す。
    - 'it carries no status semantics of its own, may be absent or stale'
    - 'The sole exception to "no status semantics of its own" is the session identity'
- orchestrator-read rule は implement-phase.md の Supporting cast に置いたままにする。

#### FR9: version bump

**説明**:
em-workflow を 0.2.10 から 0.2.11 に上げる。`em-workflow/.claude-plugin/plugin.json` と、`.claude-plugin/marketplace.json` の em-workflow エントリの両方を、同じ変更の中で更新する。

#### FR10: テスト

**説明**:
変更した protocol 記述ごとに doc-contract assertion を置く。スクリプトの変更には subprocess レベルと関数レベルのテストを置く。

**ビジネスルール**:
- doc-contract assertion は、標準ライブラリのみ、空白正規化、モジュールレベルの定数とし、変更前の verbatim なサンプルに対する negative proof を対にする。
- 変更と矛盾する pin は同じ変更の中で更新する。置き換えの assertion 無しに削除しない。テストメソッド数を減らさない。
- `python3 -m unittest discover -s tests` が通る。
- round 3 の記録 `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` は変更しない。本フィーチャーの REQUIREMENTS / SPEC が 6 つの stable_id を引用する。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 該当なし

### 5.2 セキュリティ要件
- 該当なし（fail-safe の方向については 5.4 の NFR5 / NFR6）

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件

| ID | 要件 |
|----|------|
| NFR1 | journal を書く新しいスクリプトを作らない。`workflow-schema.md` の writer-set 列挙は、ちょうど {`merge-task.sh`, `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`, `journal-append-failed.py`} のまま。新しい失敗原因は、追加的な `failed` reason 値としてだけ表す。 |
| NFR2 | I.2.c 節（'### I.2.c' から '### Supporting cast' まで）は 'rework' も 'append' も含まない。'appended' のような部分文字列も含まない。 |
| NFR3 | I.2.c の batch-mode 段落は、pin されたテキストとバイト単位で同一のまま。 |
| NFR4 | SC6 の residual reason code は I.2.b の中でだけ記載する。他の箇所は I.2.b を引用し、`workflow-schema.md` と README はそれを再掲しない。 |
| NFR5 | fail-safe の方向: 疑わしい場合は journal を書かない。経過時間やアイドル間隔のしきい値を使わない。成果物の欠損と journal `merged` イベントは、エージェント終了の証明として扱わない。記録された session_id を stop 対象やマッチ候補にしない。 |
| NFR6 | `journal.jsonl` は append-only のまま。helper は replay と append の間、排他 flock を保持する。orchestrator は `journal-append-failed.py` を呼ぶ場合を除き journal を書かない。 |
| NFR7 | `queue_launch_guard.py` と `merge-task.sh` を変更しない。`launched` の後と `merged` の後の launch guard の拒否を保つ。 |
| NFR8 | テストコードは標準ライブラリだけを import する。 |

### 5.5 互換性要件
- `journal-append-failed.py` の outcome 語彙（`appended` | `noop_terminal` | `launch_changed`）と exit-code の契約を変えない（FR5）。
- SC6 reason-code 集合は closed な 16 値のまま、`task-artifacts-missing` の固定位置を保つ（FR2）。

## 6. UI/UX要件

### 6.1 画面設計要件
該当なし（見た目を持つ対象が無いため、デザインステップは skip）。

### 6.2 画面遷移
該当なし。

### 6.3 レスポンシブ対応
該当なし。

## 7. データ要件

### 7.1 データモデル概要
`journal.jsonl` の `failed` イベント（FR5）。

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| journal `failed` イベント（reason `merge-unverified`） | `event` | string | ○ | `failed` |
| journal `failed` イベント（reason `merge-unverified`） | `task` | string | ○ | タスク id |
| journal `failed` イベント（reason `merge-unverified`） | `at` | string | ○ | 記録時刻 |
| journal `failed` イベント（reason `merge-unverified`） | `reason` | string | ○ | `merge-unverified` |

フィールドはこの順で書く。`reason` の値は `orphaned` / `stale-launched` / `merge-unverified` の 3 つ（FR5、FR7）。

### 7.3 データ保持期間
該当なし。

## 8. 外部連携

### 8.1 連携システム
該当なし。

### 8.2 API仕様要件
該当なし。

## 9. 制約条件

### 9.1 技術的制約
- `queue_launch_guard.py` と `merge-task.sh` を変更しない（NFR7）。
- journal を書く新しいスクリプトを作らない（NFR1）。
- テストコードは標準ライブラリのみ（NFR8）。
- Agent index の orchestrator-read rule は implement-phase.md の Supporting cast に置いたままにする（FR8）。

### 9.2 ビジネス上の制約
- `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` と、同フィーチャーの SPEC / REQUIREMENTS を変更しない（FR10）。

### 9.3 スケジュール制約
- なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/routeback-deferred-findings/**`
- `test-docs/routeback-deferred-findings/**`

`feature-docs/routeback-deferred-findings/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/routeback-deferred-findings/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/routeback-deferred-findings/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/routeback-deferred-findings/` ディレクトリを生成しないが、宣言された `test-docs/routeback-deferred-findings/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
なし

### 10.2 ビジネスリスク
なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1（FR1）: I.2.b step 1 が、成果物が欠けた・部分的に欠けた `launched` タスクで `Task()` 呼び出しが outstanding でないものを、Agent index lookup、Recovery、Orphan recovery、Same-session extension に通す。成果物の欠損は証拠であって終了の証明ではない、と述べる。'without an Agent index lookup ... no stop-tool call occurs ... falls to the same Residual' の文言が無く、変更前サンプルに対する negative proof がある。`RESIDUAL_UNRESOLVABLE_PHRASE`、`EXISTENCE_CHECK_FAILURE_CONDITION_PHRASE`、`ALLOWED_BUT_NEVER_STARTED_PHRASE` が引き続き一致する。
- [ ] AC-2（FR2）: `evaluate_stale_launched_chain` に `--worktree-present no` と `--branch-present no` の一方または両方と、他のすべての証明入力を与えると `recovered` に到達し、stub helper を `stale-launched` と launch identity でちょうど 1 回呼ぶ。成果物入力が無い・認識できない場合は、agent-index の読み取りやファイル open より前に residual `task-artifacts-missing` を返す。終了または stop 結果の証拠が無い場合は、引き続き `agent-termination-unproven` / `stop-result-unproven` となり、journal はバイト単位で同一。
- [ ] AC-3（FR3）: テストが候補集合の述語 'not among this reconcile step's own currently-outstanding calls' を pin し、loop-2 の文言に対する negative proof を持つ。本フィーチャーの文書が、`bc57aa350bb027c7` を解消済みとして根拠の行範囲とともに記録している。
- [ ] AC-4（FR4、FR6）: I.2.b step 1 が、ancestor 失敗時の `merge-unverified` 呼び出しを、outstanding-call と終了の前提条件、同じ step 内の再 replay を含めて述べる。I.2.c に行き止まりの文言（`RETRY_REACHES_PERMISSION_DENIAL_PHRASE`、`EXIT_REACHED_WITHOUT_ABORT_PHRASE`、'This is the one state where workflow-schema.md's status semantics'）が無く、それぞれに negative proof がある。`THIRD_CONJUNCT_NEVER_NARROWED_PHRASE` と `NO_RECYCLED_ID_INHERITS_MERGED_VIA_WRITE_SET_PHRASE` が引き続き一致する。I.2.c は 'append' も 'rework' も含まない。
- [ ] AC-5（FR5）: `--reason merge-unverified` の helper は、最終イベントが `merged` のとき、フィールド event, task, at, reason（この順）の `failed` 行をちょうど 1 行 append し、outcome `appended` を返す。`launched`、`failed`、イベント無しの上では `noop_terminal` を返し、journal はバイト単位で同一。`merged` の上の `orphaned` は `noop_terminal` のまま。並行した `merge-unverified` 呼び出しは高々 1 行しか append しない。`valid_reason` はちょうど 3 値を受け入れる。launch guard は `merge-unverified` の `failed` 行の後の relaunch を許可する。
- [ ] AC-6（FR6、FR7）: `workflow-schema.md` の Status semantics が、例外なしに、`failed` タスクは retry か route back でのみ解決すると述べている。writer-set 段落が `merge-unverified` を writer を増やさない追加的な reason として挙げ、5 名列挙のテストが引き続き通る。implement-phase.md に、orphan attempt を orchestrator による唯一の journal append と呼ぶ記述が無い。
- [ ] AC-7（FR8）: `workflow-schema.md` の `agents.jsonl` 段落が 4 つの読み手すべてと、I.2.b step 1 への index 欠損の影響を挙げる。3 つの旧文言が無く、それぞれに negative proof がある。pin されている no-status と session-identity の文言が引き続き一致する。
- [ ] AC-8（FR9）: `plugin.json` と `marketplace.json` の em-workflow エントリがどちらも 0.2.11。
- [ ] AC-9（FR10）: `python3 -m unittest discover -s tests` が通り、`round3.yaml` は変更されていない。

### 11.2 KPI
なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1: I.2.b step 1 の広げた候補集合と、証拠は証明ではないという記述の doc contract。変更前の second-independent-condition サンプルに対する negative proof を付ける。
- [ ] TS-2: `recover-orphaned-task.py` のチェーンテスト。worktree 欠損、branch 欠損、両方欠損のそれぞれが、完全な証明のもとで `recovered` に至る。終了または stop 結果の証拠が証明されない場合は residual に至る。認識できない・無い成果物トークンは `task-artifacts-missing` に至る。step 順序を直接確かめる既存テストは、認識できないトークンを使う形に更新する。
- [ ] TS-3: `bc57aa350bb027c7` の候補集合述語の doc-contract pin と negative proof。
- [ ] TS-4: `merge-unverified` の helper subprocess テスト。最終イベントが merged、launched、failed、イベント無しのそれぞれで確かめる。並行実行で高々 1 行。既存の `orphaned` / `stale-launched` over `merged` の no-op テストは残す。`merge-unverified` の `failed` 行の後に `queue_launch_guard.py` を動かす収束テスト。
- [ ] TS-5: I.2.c の doc contract。行き止まりの文言が無い（negative proof 付き）、新しい出口の文言がある、禁止トークンが無い、batch 段落がバイト単位で同一。
- [ ] TS-6: `workflow-schema.md` の writer-set の追加的 reason（列挙は 5 名のまま）、例外の無い Status semantics、`agents.jsonl` の読み手集合と index 欠損時の影響。negative proof 付き。
- [ ] TS-7: version が 0.2.11 で揃っている。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 部分欠損 | task worktree と task branch のいずれか一方だけが存在しない状態（FR1） |
| Residual | journal 不変、タスクは in-flight、gate-rejected terminal、報告にタスク名を記載、となる扱い（FR1） |
| `merge-unverified` | journal `merged` のタスクが ancestor 検証に落ちたときに使う、`failed` reason の 3 つ目の値（FR5、FR7） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1（`requirement.stale-launched-missing-artifacts.recovery`）: 成果物が欠けた stale `launched` は、既存の Agent index lookup、Recovery、Orphan recovery、Same-session extension を通す。`task-artifacts-missing` はチェーンを終える理由ではなく証拠になる。Residual は証明が得られないときだけ。batch 回答 `widen-proof-chain`。
- [x] A2（`requirement.ancestor-unverified-merged.exit`）: journal `merged` の上の ancestor 検証失敗は、`merge-unverified` での `journal-append-failed.py` 呼び出しに至る。append はロック下の `merged` の上でだけ行い、`launched` の上では行わない。relaunch の前に元の実行の終了を確認する。既存の reason は `merged` に触れない。batch 回答 `helper-merge-unverified`。
- [x] A3（`requirement.round3-record.annotation`）: `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` と、同フィーチャーの SPEC / REQUIREMENTS は変更しない。本フィーチャーが stable_id を引用する。batch 回答 `leave-record`。
- [x] A4（`requirement.stale-launched-missing-artifacts.recovery`）: `task-artifacts-missing` は廃止せず、closed な 16 値のコード集合での固定位置を保ち、意味を「成果物の証拠入力が無い、または認識できない」に狭める。closed set と固定順序の pin（`tests/test_stale_launched_doc_contract.py` の `RESIDUAL_CODES_IN_ORDER`）、step 順序の性質を保つ。
- [x] A5（`requirement.ancestor-unverified-merged.exit`）: `merge-unverified` で append しない場合は既存の `noop_terminal` を報告する。helper の outcome 語彙は広げない。`recover-orphaned-task.py` の outcome 対応付けが、closed な outcome 集合と exit-code の契約に依存している。
- [x] A6: Agent index の orchestrator-read rule は implement-phase.md の Supporting cast に置いたままにし、IMPLEMENTATION.md へは移さない。その文言は `tests/test_implement_routeback_gate.py` で pin されている。ドリフトは `workflow-schema.md` 側にある。
- [x] A7（`requirement.ancestor-unverified-merged.exit`）: `queue_launch_guard.py` と `merge-task.sh` は変更しない。launch guard の拒否は `tests/test_stale_launched_retry_reachability.py` で pin されている。`merge-task.sh` は親ブランチが task branch を含むとき、すでに `merged` を再記録する（`merge-task.sh:116-118`）。
- [x] `bc57aa350bb027c7` は HEAD 時点で解消済み。根拠は implement-phase.md 520-523 行（候補集合の述語）と 633-660 行（Same-session extension）（FR3）。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- round 3 の記録: `feature-docs/routeback-admissibility-exits/reviews/round3.yaml`
- `em-workflow/references/implement-phase.md`
- `em-workflow/references/workflow-schema.md`
