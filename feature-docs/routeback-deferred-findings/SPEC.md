# Feature: routeback-deferred-findings

## Overview

feature `routeback-admissibility-exits` の review round 3 で deferred となった 6 件の findings（`12839a507a7df994`、`2da3c75adac32650`、`bc57aa350bb027c7`、`59e58726b1b22211`、`94de80a315821a55`、`9cc0ce6b64087d2f`）を解消する。対象は `em-workflow/references/implement-phase.md` の I.2.a / I.2.b / I.2.c / Supporting cast、`em-workflow/references/workflow-schema.md`、`em-workflow/scripts/recover-orphaned-task.py`、`em-workflow/scripts/journal-append-failed.py`、テスト、version。要件の詳細は `feature-docs/routeback-deferred-findings/REQUIREMENTS.md` を参照する。

## Objectives

- round 3 で deferred となった 6 件を解消する。
- 再開した無人実行が abort、またはそれと同等の gate-rejected terminal でしか終われない protocol 上の経路を取り除く。対象は、成果物が欠けた stale `launched` タスクと、ancestor 検証に落ちた journal `merged` タスク。
- `implement-phase.md` と `workflow-schema.md` の間にある、failed タスクの status semantics と、`agents.jsonl` の読み手集合・index 欠損時の影響についてのドリフトを取り除く。

## User Stories

### US1: 成果物が欠けた stale `launched` タスクの復旧
As a em-workflow の orchestrator, I want to 成果物が欠けた・部分的に欠けた stale `launched` タスクを既存の証明チェーンに通す, so that 証明が得られたとき retry と route back to planning の両方に到達できる。

**Acceptance Criteria:**
- [ ] AC-1（FR1）
- [ ] AC-2（FR2）
- [ ] AC-3（FR3）

### US2: ancestor 検証に落ちた journal `merged` タスクの出口
As a em-workflow の orchestrator, I want to ancestor 検証に落ちた journal `merged` タスクを `merge-unverified` で journal `failed` にする, so that そのタスクが通常の retry / route back to planning / abort メニューに到達する。

**Acceptance Criteria:**
- [ ] AC-4（FR4、FR6）
- [ ] AC-5（FR5）
- [ ] AC-6（FR6、FR7）

### US3: SSOT とのドリフト解消
As a em-workflow の orchestrator, I want to `workflow-schema.md` が `agents.jsonl` の読み手集合と index 欠損時の影響を正しく述べる, so that consumer 側の記述と SSOT が一致する。

**Acceptance Criteria:**
- [ ] AC-7（FR8）
- [ ] AC-8（FR9）
- [ ] AC-9（FR10）

## Technical Requirements

### Functional Requirements

- **FR1:** 成果物が欠けた stale `launched` を既存の証明チェーンに通す（`12839a507a7df994`）。implement-phase.md I.2.b step 1 で、journal 最終イベントが `launched`、task worktree と task branch の少なくとも一方が存在しない（両方欠損、または部分欠損）、`Task()` 呼び出しがこの reconcile step 自身の currently-outstanding な呼び出しに含まれない、の 3 条件をすべて満たすタスクを、両方存在する候補集合と同じ not-live 判定に次の順で合流させる。(1) Agent index lookup（task id キー、worktree 不要、Agent index writer の orchestrator-read rule に従い引用のみ）。(2) Recovery（harness の stop tool、その後 stop-tool recorder が終端 `failed` を記録）。(3) Orphan recovery（legacy chain）。(4) Same-session extension。成果物の欠損は観測された証拠にとどまり、単独で終了の証明にならない。outstanding-call 除外、termination conjunct、stop-result conjunct、agent-identity binding、append 時の launch-identity 再確認は変えない。証明が得られたら既存の reason（`orphaned` / `stale-launched`、または recorder 自身のもの）で終端 `failed` が journal に入り、step 1 が同じ reconcile step 内で再 replay する。step 3・5 と I.2.c は `failed` を見て、retry と route back to planning の両方に到達できる。Residual（journal 不変、in-flight、gate-rejected terminal、報告にタスク名）は証明が得られない場合にだけ残る。現行 566-584 行の 'without an Agent index lookup'、'no stop-tool call occurs'、'falls to the same Residual treatment' の記述を置き換える。
- **FR2:** 証明チェーンのスクリプトが成果物欠損を証拠として受け入れる。`em-workflow/scripts/recover-orphaned-task.py` の `evaluate_stale_launched_chain` step 1（650 行）で、`--worktree-present no` / `--branch-present no` がチェーンを終えないようにする。観測値は証拠として持ち回り、残りの step は変えない。`task-artifacts-missing` は closed な 16 値の SC6 reason-code 集合で固定位置を保ち、成果物の証拠入力が無いか正確に `yes` / `no` でないとき（成果物の状態が未観測のとき）だけ出す。成果物入力の判定は agent-index の読み取り・パスの組み立て・ファイルの open より前に行う。`--task-worktree` はパスの存在に関わらずタスクの期待 worktree パス（`$WT_ROOT/{T}`）を運び、identity-binding step が Agent index エントリの記録 worktree と文字列比較する。モジュール docstring の呼び出し側前提条件（'the task worktree and task branch exist'）と step 1 の説明を更新する。implement-phase.md の Orphan recovery 候補の説明（'task worktree and task branch both present'、588-592 行）と Same-session extension の step（'both observed present (else `task-artifacts-missing`)'、645-647 行）を、広げた候補集合と狭めたコードの意味に合わせて更新する。
- **FR3:** `bc57aa350bb027c7` を解消済みとして記録し、pin する。HEAD 時点で解消済みである根拠は、implement-phase.md 520-523 行の候補集合の述語 'whose `Task()` call is not among this reconcile step's own currently-outstanding calls'（セッションをキーにしない）と、633-660 行の Same-session extension（reason `stale-launched` の journal `failed` に到達する）。prose は修正し直さない。現状どのテストも pin していない候補集合の述語を、新しい doc-contract テストで pin し、候補を現セッション開始前に記録された `launched` に限定していた loop-2 の文言に対する negative proof を付ける。
- **FR4:** ancestor 検証に落ちた journal `merged` タスクの自動出口（`2da3c75adac32650`）。I.2.b step 1 の ancestor-check の項で、`git merge-base --is-ancestor <task branch> em-workflow/{feature}/integration` が失敗し、journal 最終イベントが `merged` で、`Task()` 呼び出しがこの reconcile step 自身の currently-outstanding な呼び出しに含まれないタスクについて、orchestrator が動く。`merged` イベントはエージェント終了の証明ではないので、既存の drain / outstanding-call 規則のもとで元の実行の終了を先に確認する。その後 `em-workflow/scripts/journal-append-failed.py` を `--reason merge-unverified` で 1 回呼ぶ。step 1 は同じ reconcile step 内で再 replay し、reconciled state だけでなく journal 最終イベントも `failed` になる。第 3 route-back conjunct は当たらなくなり、retry（launch guard は `failed` の後の launch を許可する）と route back to planning（gate に従う）の両方に到達できる。第 3 conjunct と `queue_launch_guard.py` は変えない。helper が非 0 で終了するか append 以外の outcome を報告した場合、journal はそのままで、journal `merged` かつ reconciled `failed` についての既存の記述がそのタスクを支配する（第 3 conjunct が route-back を阻み、gate-rejected の原因列挙がタスクを挙げ、報告にタスク名が載る）。retry は既存の I.2.c drain と I.2.a resume guard（worktree を保持）に従う。親ブランチがすでに task branch を含む場合、`merge-task.sh` が `merged` を再記録する（`merge-task.sh:116-118`）ので、後続の reconcile がマージを検証する。
- **FR5:** helper は locked な `merged` の上でだけ `merge-unverified` を受け入れる。`em-workflow/scripts/journal-append-failed.py` の `VALID_REASONS` を、この定数への意図した変更として `{orphaned, stale-launched, merge-unverified}` に広げる。reason `merge-unverified` では、同じ排他ロック下の replay の中で、タスク自身の最終イベントが `merged` のときだけ `failed`（フィールド `event`、`task`、`at`、`reason` の順）を append する。最終イベントが `launched`、`failed`、無し、その他の値なら append しない。この reason では `--launch-at` を使わない。`orphaned` と `stale-launched` の判定は変えず、`launched` の上でだけ append し、最終イベント `merged` では no-op のまま（`test_final_event_merged_is_noop` は残す）。outcome 語彙（`appended` | `noop_terminal` | `launch_changed`）と exit-code の契約は変えない。`merge-unverified` で append しない場合は `noop_terminal` を報告し、journal はバイト単位で不変。docstring と argparse の help に新しい reason とその別個の前提条件を記載する。
- **FR6:** failed タスクの status-semantics 例外を撤去し、SSOT は無条件のまま保つ（`59e58726b1b22211`、`9cc0ce6b64087d2f`）。I.2.c（908-930 行）の ancestor 失敗に関する prose を、このタスクが I.2.b step 1 の生成した journal `failed` イベント（引用のみ、再掲しない）を持って通常の retry / route back to planning / abort メニューに到達する、という記述に置き換える。置き換える prose は 'choosing retry there reaches the launch guard's permission denial ...'、'an outcome reached without selecting abort'、'in effect the same dead end ...'、'the only way out is a human ...'、'This is the one state where workflow-schema.md's status semantics ... are not met by an automated path; the gap is confined to this single case ...'。新しい文言は 'append' と 'rework' のトークンを使わない。`workflow-schema.md` の Status semantics の項 'A `failed` task resolves ONLY by retry or by routing back to planning' は無条件のまま保ち、この変更後はすべての状態で成り立つ。SSOT に例外は加えない。依存する記述を同じ変更の中で調整する。I.2.a 327-332 行（'the launch guard denies the retry instead — I.2.c owns that narrower outcome'）は、新しい経路と helper 失敗時に残るケースを述べる。I.2.b の orphan ブロックの 'This is the ONLY case in which the orchestrator's own action results in an append to `journal.jsonl`'、Supporting cast の Journal の項の単一例外、Stale-`launched` caveat の 'the sole exception to the Journal bullet's rule' は、`merge-unverified` の呼び出しを同じ helper 例外の一部として挙げ、orphan attempt が orchestrator による唯一の append だと主張する記述を残さない。abort の項は変えない（`merge-unverified` による失敗は既存の 'otherwise' 節で `failed_kind: decision` になる）。batch の段落は変えない。
- **FR7:** `workflow-schema.md` の journal writer-set 段落に新しい reason 値を記録する。writer-set 段落（397-422 行）に、`merge-unverified` を既存の `failed` reason フィールドの 3 つ目の追加的な値として記載する。同じ helper が書き、I.2.b step 1 の ancestor-check 分岐からだけ呼ばれ（リポジトリ相対パスで引用し、再掲しない）、writer を増やさない。'Its writer set is unambiguous' と 'outside this one exception' の間のスクリプト名列挙は、ちょうど 5 つの名前のまま保ち、'outside this one exception' の文字列を残す。`failed_kind` の節は変えない（fail-closed の `decision`）。
- **FR8:** SSOT に `agents.jsonl` の読み手集合と index 欠損時の影響を記載する（`94de80a315821a55`）。`workflow-schema.md` の `agents.jsonl` 段落（424-444 行）を同じ変更の中で更新する。読み手として `queue_taskstop_net.py`（stop 時）、`queue_failure_net.py` の agent-index フォールバック、orchestrator の I.2.b step 1 の Agent index lookup と Recovery（Orchestrator-side read）、`recover-orphaned-task.py` をすべて挙げる。index が無い・古い場合、stale `launched` タスクについて I.2.b step 1 の not-live 判定も未解決のままになることを記載し、その結果は implement-phase.md I.2.b から引用して再掲しない。'read by `queue_taskstop_net.py` at stop'、'its absence only degrades the stop-tool recorder to a no-op'、'`agents.jsonl` exists solely to make a stop resolvable back to a task' を置き換える。'it carries no status semantics of its own, may be absent or stale' と 'The sole exception to "no status semantics of its own" is the session identity' は残す。orchestrator-read rule は implement-phase.md の Supporting cast に置いたままにする。
- **FR9:** version bump。em-workflow を 0.2.10 から 0.2.11 に上げる。`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリを同じ変更の中で更新する。
- **FR10:** テスト。変更した protocol 記述ごとに doc-contract assertion を置く（標準ライブラリのみ、空白正規化、モジュールレベルの定数、変更前の verbatim なサンプルに対する negative proof を対にする）。変更と矛盾する pin は同じ変更の中で更新し、置き換えの assertion 無しに削除せず、テストメソッド数を減らさない。スクリプトの変更には subprocess レベルと関数レベルのテストを置く。`python3 -m unittest discover -s tests` が通る。round 3 の記録 `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` は変更せず、本フィーチャーの REQUIREMENTS / SPEC が 6 つの stable_id を引用する。

### Non-Functional Requirements

- **NFR1:** journal を書く新しいスクリプトを作らない。`workflow-schema.md` の writer-set 列挙は、ちょうど {`merge-task.sh`, `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`, `journal-append-failed.py`} のまま。新しい失敗原因は追加的な `failed` reason 値としてだけ表す。
- **NFR2:** I.2.c 節（'### I.2.c' から '### Supporting cast' まで）は 'rework' も 'append' も含まない。'appended' のような部分文字列も含まない。
- **NFR3:** I.2.c の batch-mode 段落は、pin されたテキストとバイト単位で同一のまま。
- **NFR4:** SC6 の residual reason code は I.2.b の中でだけ記載する。他の箇所は I.2.b を引用し、`workflow-schema.md` と README はそれを再掲しない。
- **NFR5:** fail-safe の方向: 疑わしい場合は journal を書かない。経過時間やアイドル間隔のしきい値を使わない。成果物の欠損と journal `merged` イベントをエージェント終了の証明として扱わない。記録された session_id を stop 対象やマッチ候補にしない。
- **NFR6:** `journal.jsonl` は append-only のまま。helper は replay と append の間、排他 flock を保持する。orchestrator は `journal-append-failed.py` を呼ぶ場合を除き journal を書かない。
- **NFR7:** `queue_launch_guard.py` と `merge-task.sh` を変更しない。`launched` の後と `merged` の後の launch guard の拒否を保つ。
- **NFR8:** テストコードは標準ライブラリだけを import する。

## Implementation Approach

### Architecture

**変更する構成要素:**
```
em-workflow/references/implement-phase.md
  I.2.a  327-332 行            ... FR6（依存記述の調整）
  I.2.b  step 1                ... FR1（候補集合の拡張）、FR4（ancestor-check の出口）
         520-523 行            ... FR3（変更しない。pin のみ）
         566-584 行            ... FR1（置き換え）
         588-592 行 / 645-647 行 ... FR2（候補説明とコードの意味）
         orphan ブロック        ... FR6（helper 例外に merge-unverified を含める）
  I.2.c  908-930 行            ... FR6（行き止まり記述の置き換え）
  Supporting cast Journal の項 / Stale-`launched` caveat ... FR6
em-workflow/references/workflow-schema.md
  writer-set 段落 397-422 行   ... FR7
  agents.jsonl 段落 424-444 行 ... FR8
  Status semantics             ... FR6（無条件のまま。変更しない）
em-workflow/scripts/recover-orphaned-task.py  ... FR2
em-workflow/scripts/journal-append-failed.py  ... FR5
tests/                                        ... FR3、FR10
em-workflow/.claude-plugin/plugin.json        ... FR9
.claude-plugin/marketplace.json               ... FR9
```

**変更しない構成要素:**
```
em-workflow の queue_launch_guard.py  ... NFR7
merge-task.sh                         ... NFR7
feature-docs/routeback-admissibility-exits/reviews/round3.yaml ... FR10
```

### Data Flow

成果物が欠けた stale `launched`（FR1、FR2）:
```
I.2.b step 1: journal 最終 = launched かつ worktree/branch の少なくとも一方が欠損
              かつ Task() が outstanding でない
  → Agent index lookup → Recovery → Orphan recovery → Same-session extension
      証明あり → 終端 failed（orphaned / stale-launched / recorder の reason）
               → 同じ reconcile step 内で再 replay
               → step 3・5 / I.2.c が failed を見る → retry / route back to planning
      証明なし → Residual（journal 不変、in-flight、gate-rejected terminal、報告にタスク名）
```

ancestor 検証に落ちた journal `merged`（FR4、FR5）:
```
I.2.b step 1: journal 最終 = merged かつ is-ancestor 失敗 かつ Task() が outstanding でない
  → 既存の drain / outstanding-call 規則で元の実行の終了を確認
  → journal-append-failed.py --reason merge-unverified（1 回）
      appended     → 同じ reconcile step 内で再 replay → journal 最終 = failed
                   → I.2.c: retry / route back to planning / abort
      非 0 / 非 append → journal 不変 → 既存の journal merged + reconciled failed の記述が支配
                         （第 3 conjunct が route-back を阻む、gate-rejected の原因列挙、報告にタスク名）
```

### API Design

#### `journal-append-failed.py`（FR5）

**Request:**
```
--reason orphaned | stale-launched | merge-unverified
--launch-at  ... merge-unverified では使わない
```

**判定（同じ排他ロック下の replay の中）:**

| reason | タスクの最終イベント | 結果 |
|--------|----------------------|------|
| `merge-unverified` | `merged` | `failed` を 1 行 append、outcome `appended` |
| `merge-unverified` | `launched` / `failed` / 無し / その他 | append しない、outcome `noop_terminal`、journal はバイト単位で不変 |
| `orphaned` / `stale-launched` | `launched` | 現行どおり |
| `orphaned` / `stale-launched` | `merged` | no-op（現行どおり） |

outcome 語彙（`appended` | `noop_terminal` | `launch_changed`）と exit-code の契約は変えない。

#### `recover-orphaned-task.py` の `evaluate_stale_launched_chain`（FR2）

| 入力 | 値 | step 1 の扱い |
|------|----|---------------|
| `--worktree-present` / `--branch-present` | `yes` / `no` | 証拠として持ち回り、チェーンを続ける |
| `--worktree-present` / `--branch-present` | 無し、または `yes` / `no` 以外 | residual `task-artifacts-missing`（agent-index 読み取り・パス組み立て・ファイル open より前） |
| `--task-worktree` | `$WT_ROOT/{T}`（存在の有無に関わらず） | identity-binding step で Agent index エントリの記録 worktree と文字列比較 |

### Database Schema

#### `journal.jsonl` の `failed` イベント（reason `merge-unverified`）

| Field | Type | 説明 |
|-------|------|------|
| `event` | string | `failed` |
| `task` | string | タスク id |
| `at` | string | 記録時刻 |
| `reason` | string | `merge-unverified` |

フィールドはこの順で書く。`reason` の値は `orphaned` / `stale-launched` / `merge-unverified` の 3 つ。`journal.jsonl` は append-only（NFR6）。

### Dependencies

**Internal Dependencies:**
- `queue_launch_guard.py`: `failed` の後の launch を許可し、`launched` の後と `merged` の後の launch を拒否する（変更しない）。
- `merge-task.sh`: 親ブランチが task branch を含むとき `merged` を再記録する（`merge-task.sh:116-118`、変更しない）。
- `tests/test_stale_launched_doc_contract.py` の `RESIDUAL_CODES_IN_ORDER`: `task-artifacts-missing` の固定位置の pin。
- `tests/test_implement_routeback_gate.py`: Supporting cast の orchestrator-read rule の pin。
- `tests/test_stale_launched_retry_reachability.py`: launch guard の拒否の pin。

**External Dependencies:**
- なし（テストは標準ライブラリのみ、NFR8）

### File Structure

```
em-workflow/
├── .claude-plugin/plugin.json           # FR9
├── references/
│   ├── implement-phase.md               # FR1, FR2, FR4, FR6
│   └── workflow-schema.md               # FR7, FR8
└── scripts/
    ├── recover-orphaned-task.py         # FR2
    └── journal-append-failed.py         # FR5
.claude-plugin/marketplace.json          # FR9
tests/                                   # FR3, FR10
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

各 SPEC は、上記のフィーチャー固有パスに加えて、次の 2 つのワークフロー生成エントリをデフォルトで宣言する。

- `feature-docs/routeback-deferred-findings/**`
- `test-docs/routeback-deferred-findings/**`

`feature-docs/routeback-deferred-findings/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` で、この節は引用のみでルールは再掲しない。

`test-docs/routeback-deferred-findings/**` に含まれるもの: タスクごとのテスト記録 `test-docs/routeback-deferred-findings/{T}.tests.yaml`。生成主体は `implement-phase.md` で、この節は引用のみでルールは再掲しない。

この 2 つのデフォルトエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことで除外とはみなさない。除外は意図的・明示的な絞り込みである。

この宣言はスーパーセット（SUPERSET）の主張であり、検証時に観測される実際の変更集合は宣言された集合に含まれる（CONTAINED IN）必要があり、一致する必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/routeback-deferred-findings/` ディレクトリを生成しないが、宣言された `test-docs/routeback-deferred-findings/**` はその場合も正しい。実際には生成されないパスが宣言されていても違反にはならない。

## Test Scenarios

### Unit Tests
- [ ] TS-2: `recover-orphaned-task.py` のチェーンテスト - worktree 欠損、branch 欠損、両方欠損のそれぞれが完全な証明のもとで `recovered` に至る。終了または stop 結果の証拠が証明されない場合は residual。認識できない・無い成果物トークンは `task-artifacts-missing`。step 順序を直接確かめる既存テストは、認識できないトークンを使う形に更新する。
- [ ] TS-4: `journal-append-failed.py` の `merge-unverified` subprocess テスト - 最終イベントが merged、launched、failed、無しのそれぞれで確かめる。並行実行で高々 1 行。既存の `orphaned` / `stale-launched` over `merged` の no-op テストは残す。`merge-unverified` の `failed` 行の後に `queue_launch_guard.py` を動かす収束テスト。

### Integration Tests
- [ ] TS-1: I.2.b step 1 の広げた候補集合と、証拠は証明ではないという記述の doc contract - 変更前の second-independent-condition サンプルに対する negative proof。
- [ ] TS-3: `bc57aa350bb027c7` の候補集合述語の doc-contract pin - negative proof 付き。
- [ ] TS-5: I.2.c の doc contract - 行き止まりの文言が無い（negative proof 付き）、新しい出口の文言がある、禁止トークンが無い、batch 段落がバイト単位で同一。
- [ ] TS-6: `workflow-schema.md` の doc contract - writer-set の追加的 reason（列挙は 5 名のまま）、例外の無い Status semantics、`agents.jsonl` の読み手集合と index 欠損時の影響。negative proof 付き。
- [ ] TS-7: version の一致 - `plugin.json` と `marketplace.json` の em-workflow エントリが 0.2.11。

### E2E Tests
**Existing E2E tests**: なし
**Run command**: 未検出
- [ ] 該当なし

### Edge Cases
- [ ] 部分欠損（worktree だけ、または branch だけが無い）の stale `launched` - 両方欠損と同じチェーンを通る（FR1、TS-2）。
- [ ] 成果物入力が無い・`yes` / `no` 以外 - agent-index 読み取り・ファイル open より前に `task-artifacts-missing`（FR2、TS-2）。
- [ ] `merge-unverified` の helper が非 0 終了または非 append - journal 不変、既存の journal `merged` + reconciled `failed` の記述が支配（FR4）。
- [ ] 並行した `merge-unverified` 呼び出し - 高々 1 行の append（FR5、TS-4）。
- [ ] `orphaned` / `stale-launched` over `merged` - no-op のまま（FR5、TS-4）。

### Performance Tests
- [ ] 該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `recover-orphaned-task.py` の成果物入力は正確に `yes` / `no` のみを観測値として受け入れ、それ以外は `task-artifacts-missing`（FR2）。`journal-append-failed.py` の reason は 3 値のみ（FR5）。
- **Data Protection:** `journal.jsonl` は append-only、helper は replay と append の間に排他 flock を保持（NFR6）。疑わしい場合は journal を書かない（NFR5）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | 発生元 |
|------|-------------|--------|
| `task-artifacts-missing` | 成果物の証拠入力が無い、または `yes` / `no` 以外（SC6 の固定位置を保つ） | `recover-orphaned-task.py`（FR2） |
| `agent-termination-unproven` | 終了の証拠が無い。journal はバイト単位で不変 | `recover-orphaned-task.py`（FR2） |
| `stop-result-unproven` | stop 結果の証拠が無い。journal はバイト単位で不変 | `recover-orphaned-task.py`（FR2） |
| `noop_terminal` | `merge-unverified` で最終イベントが `merged` でない。journal はバイト単位で不変 | `journal-append-failed.py`（FR5） |

SC6 の residual reason code は I.2.b の中でだけ記載する（NFR4）。

### Error Flow

```
証明が得られない → journal を書かない → Residual（FR1）
helper が非 0 / 非 append → journal 不変 → 既存の journal merged + reconciled failed の扱い（FR4）
```

## Performance Optimization

### Performance Goals
- 該当なし

### Optimization Strategies
- 該当なし

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 から AC-9 を満たす（`feature-docs/routeback-deferred-findings/REQUIREMENTS.md` 11.1）
- [ ] `python3 -m unittest discover -s tests` が通る
- [ ] `feature-docs/routeback-admissibility-exits/reviews/round3.yaml` が変更されていない
- [ ] `plugin.json` と `marketplace.json` の em-workflow エントリが 0.2.11

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし（タスク分割は create-plan で行う）。

## References

- 要件定義書: `feature-docs/routeback-deferred-findings/REQUIREMENTS.md`
- round 3 の記録: `feature-docs/routeback-admissibility-exits/reviews/round3.yaml`
- `em-workflow/references/implement-phase.md`
- `em-workflow/references/workflow-schema.md`
