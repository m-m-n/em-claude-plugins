---
title: "implement-failed-kind"
created_date: 2026-09-06
status: draft
---

# implement-failed-kind - 要件定義書

## 1. 概要

### 1.1 背景

現在、implement step の `failed` は理由を区別せず、develop Step B の停止条件 3 を一律に
発火させる。そのため無人走行（`--batch`）が、人の判断を要しない失敗でも 1〜2 分ごとに
同一の報告を繰り返す状態に陥る。

### 1.2 目的

implement step の `failed` に理由の分類（`failed_kind`）を持たせ、インフラ起因の失敗と
設計判断が必要な失敗を workflow.yaml 上で区別できるようにする。インフラ起因では走行を
継続させ、設計判断が必要なものは従来どおり人に制御を返す。

### 1.3 スコープ

- 対象: implement step の `failed`。
- 対象外: 停止条件 3 のもう一方のトリガである `needs_update`、および review / verify step の
  `failed`（A3）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- implement step の `failed` に理由の分類を持たせ、インフラ起因の失敗と設計判断が必要な
  失敗を workflow.yaml 上で区別できるようにする
- インフラ起因の `failed` では develop Step B の停止条件 3 を発火させず、implement を
  `pending` に戻して走行を継続させる
- 設計判断が必要な `failed` は従来どおり停止条件 3 で人に制御を返す挙動を保つ
- 無人走行（`--batch`）が、人の判断を要しない失敗で 1〜2 分ごとの同一報告を繰り返す状態に
  陥らないようにする

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | `--batch` で無人走行させ、人の判断を要する時点だけ制御を受け取りたい利用者 |

### 2.3 期待される効果

- インフラ起因の失敗で走行が停止しなくなる
- 設計判断が必要な失敗でのみ人に制御が戻る

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | インフラ起因の implement 失敗から自動で走行を継続する | em-workflow の利用者 | 高 |
| UC02 | 設計判断が必要な implement 失敗で人に制御を返す | em-workflow の利用者 | 高 |

### 3.2 ユースケース詳細

#### UC01: インフラ起因の implement 失敗から自動で走行を継続する

**アクター**: em-workflow の利用者

**事前条件**:
- implement step が `failed` かつ `failed_kind: infra` である

**基本フロー**:
1. develop Step B が implement step の `failed` を検出する
2. `failed_kind` が `infra` であるため停止条件 3 を発火させない
3. implement step を `pending` に戻す write を行う
4. その write を `commit-docs.sh` でコミットする
5. 当該フェーズを実行する

**代替フロー**:
- `infra` 起因の自動続行が回数上限に達している場合は、`decision` 扱いで停止する（FR7）

**事後条件**:
- implement フェーズが再実行され、走行が継続している

#### UC02: 設計判断が必要な implement 失敗で人に制御を返す

**アクター**: em-workflow の利用者

**事前条件**:
- implement step が `failed` かつ `failed_kind: decision` である（`failed_kind` を持たない
  既存の workflow.yaml も `decision` として扱う）

**基本フロー**:
1. develop Step B が implement step の `failed` を検出する
2. `failed_kind` が `decision` であるため停止条件 3 を発火させる
3. 走行を停止し、人に制御を返す

**事後条件**:
- 走行が停止し、終端行に `step_needs_intervention` が出ている

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | implement step への `failed_kind` フィールド追加 | `workflow[]` の implement step に `infra` \| `decision` の閉じた 2 値を定義する | ok |
| FR2 | `failed_kind` のライフサイクル（設定・保持・クリア） | 書く時点・保持期間・クリアする時点を規定する | tbd |
| FR3 | I.2.c abort 経路での `failed_kind` 書き込み | abort phase 分岐のターミナル status write に `failed_kind` を含める | ok |
| FR4 | batch の 2 回目 failed 経路での `failed_kind` 書き込み | `implement.failed-task` が書く `failed_kind` の値を規定する | tbd |
| FR5 | route-back gate-rejected terminal での `failed_kind` 書き込み | gate 不成立経路が書く `failed_kind` の値を規定する | tbd |
| FR6 | 停止条件 3 の発火条件を `failed_kind: decision` に限定する | `infra` では停止せず implement を `pending` に戻す | ok |
| FR7 | `infra` 自動続行の回数上限とその記録 | 上限到達時は `decision` 扱いで停止し、回数は `batch` セクションに記録する | tbd |
| FR8 | `infra` 自動続行を適用するモードの範囲 | batch のみか interactive も含むかを規定する | tbd |
| FR9 | `failed_kind` 欠落時の後方互換 | 欠落は `decision` として扱い、移行処理は行わない | ok |
| FR10 | 関連ドキュメントの更新 | batch-terminal-line.md / develop SKILL.md / batch-mode.md を更新する | ok |

### 4.2 機能詳細

#### FR1: implement step への `failed_kind` フィールド追加

**状態**: ok

**説明**: `references/workflow-schema.md` の `workflow[]` の implement step に `failed_kind` を
追加する。値は `infra` | `decision` の閉じた 2 値。`infra` は外部要因（implementer の孤児化、
harness 障害）、`decision` は実装内容の失敗や計画の見直しが必要なもの。
`failed_items[].category` 節と同じ形式で workflow-schema.md を唯一の定義元とし、他ドキュメントは
リポジトリ相対パスで引用するだけにする。

#### FR2: `failed_kind` のライフサイクル（設定・保持・クリア）

**状態**: tbd

**説明**: `failed_kind` を書く時点・保持する期間・クリアする時点を規定する。implement が
`failed` 以外の status に遷移するときにフィールドをどう扱うかを含む。

**TBD 理由**: 未決定事項『failed_kind のライフサイクル』（question_id: failed-kind.lifecycle、
packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は
`clear_on_leaving_failed`（implement が `failed` を離れる書き込みと同じ write set で
`failed_kind` を null に戻す）。create-plan の tbd-resolution で確定する。

#### FR3: I.2.c abort 経路での `failed_kind` 書き込み

**状態**: ok

**説明**: `references/implement-phase.md` I.2.c の abort phase 分岐が implement を `failed` に
書く単一 write（実装フェーズ中断のターミナル status write）に `failed_kind` を必ず含める。
失敗の journal reason が `orphaned`（I.2.b の orphan-recovery が記録するもの）由来なら `infra`、
それ以外は `decision`。write と `commit-docs.sh` によるコミットの単位は現行のまま変えない。

#### FR4: batch の 2 回目 failed 経路での `failed_kind` 書き込み

**状態**: tbd

**説明**: `references/batch-mode.md` Non-packet gates の `implement.failed-task`（同一タスクが
2 回目に失敗した場合の abort phase）が implement を `failed` に書くときの `failed_kind` の値を
規定する。

**TBD 理由**: 未決定事項『batch 2 回目 failed の分類』（question_id: batch.second-failure.kind、
packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は
`second_always_decision`（2 回目失敗は原因を問わず常に `decision`）。この推奨は既存の precedence
規則と整合する — `references/batch-terminal-line.md` の Stop point coverage で
`implement-second-failure` は `implement_task_failed` として `stop-condition-3` より優先されるため、
`infra` に分類しても走行は停止する。create-plan の tbd-resolution で確定する。

#### FR5: route-back gate-rejected terminal での `failed_kind` 書き込み

**状態**: tbd

**説明**: `references/implement-phase.md` I.2.c の route-back gate が成立しなかった経路
（`docs({feature}): implement route-back gate rejected` をコミットするターミナル status write）が
書く `failed_kind` の値を規定する。

**TBD 理由**: 未決定事項『gate-rejected terminal の分類』（question_id: gate-rejected.kind、
packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `always_decision`
（gate 不成立は `merged` / `in_progress` タスクの存在という計画側の状態が原因であり、自動続行しても
同じ gate で再び弾かれるため常に `decision`）。create-plan の tbd-resolution で確定する。

#### FR6: 停止条件 3 の発火条件を `failed_kind: decision` に限定する

**状態**: ok

**説明**: `skills/develop/SKILL.md` Step B の停止条件 3 は、implement step の `failed` については
`failed_kind: decision` のときだけ発火する。`failed_kind: infra` のときは停止せず、implement step を
`pending` に戻す write を行い、その write を `commit-docs.sh` でコミットしてから当該フェーズを
実行する。既存の「停止条件 3 との優先関係」ブロック（フェーズプロトコルが自動再エントリのために
設定した `needs_update` の carve-out）と、「batch: verify の cap 到達に対する停止条件の例外」は
変更しない。

#### FR7: `infra` 自動続行の回数上限とその記録

**状態**: tbd

**説明**: `failed_kind: infra` を理由とする自動続行に回数上限を設け、上限到達時は `decision` 扱いで
停止する。上限値と現在の回数は workflow.yaml の `batch` セクションに記録する
（`references/workflow-schema.md` の `batch` ブロック節に新キーとして定義し、未設定キーは 0 として
読む既存の読み取り規則に倣う）。上限値以外の構造（`batch` セクションへ記録すること、上限到達時は
`decision` 扱いで停止すること）は受け入れ条件で確定済み。

**TBD 理由**: 未決定事項『infra 起因の自動続行の回数上限』（question_id: infra.retry-cap-value、
packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `cap_2`（上限 2 回）。
上限値そのものが未確定のため、キー名・カウント更新規則・上限到達時の報告文面もあわせて create-plan の
tbd-resolution で確定する。

#### FR8: `infra` 自動続行を適用するモードの範囲

**状態**: tbd

**説明**: `failed_kind: infra` による自動続行を batch モードだけに適用するか、interactive にも
適用するかを規定する。

**TBD 理由**: 未決定事項『infra 自動続行の適用モード』（question_id: infra.mode-scope、
packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `batch_only`（回数の
記録先が workflow.yaml の `batch` セクションであること、および `batch` ブロックが --batch 走行でのみ
作成される既存規則と整合するため）。create-plan の tbd-resolution で確定する。

#### FR9: `failed_kind` 欠落時の後方互換

**状態**: ok

**説明**: `failed_kind` を持たない既存の workflow.yaml の implement `failed` は `decision` として
扱う。移行処理は行わない。この扱いは `failed_kind` を必須で書く新規 write 経路（FR3〜FR5）の要求を
緩めない — `failed_items[].category` の pre-change compatibility 節と同じ形をとる。

#### FR10: 関連ドキュメントの更新

**状態**: ok

**説明**: `references/batch-terminal-line.md` の `step_needs_intervention` の Meaning 行
（現在「A workflow step reported `failed` or `needs_update`」）と Stop point coverage の
`stop-condition-3` 行の記述、`skills/develop/SKILL.md` の停止条件 3 の記述、
`references/batch-mode.md`（`implement.failed-task` 行および「Failure stops are UNCHANGED」の記述）を、
`failed_kind` による分岐に合わせて更新する。

## 5. 非機能要件

### 5.1 NFR1: SSOT 規律

**状態**: ok

`failed_kind` の定義・必須性・閉じた語彙は `references/workflow-schema.md` の 1 箇所だけが所有し、
他ドキュメント（implement-phase.md / develop SKILL.md / batch-mode.md / batch-terminal-line.md）は
リポジトリ相対パスで引用するだけにする。値の再定義を複数箇所に置かない。

### 5.2 NFR2: write とコミットの単位を変えない

**状態**: ok

implement を `failed` に書く 3 経路は「ターミナル status write とそのコミットが唯一の副作用」という
現行不変条件を保つ。`failed_kind` はその同じ write に含める（追加の write / 追加のコミットにしない）。
停止条件 3 の `infra` 分岐で implement を `pending` に戻す write も、フェーズ実行前に 1 回のコミットとして
確定させる。

### 5.3 NFR3: プラグイン version bump

**状態**: ok

`em-workflow/` 配下を変更するため、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` と
リポジトリルート `.claude-plugin/marketplace.json` の当該 version を同値で上げる
（`.claude/rules/core-plugin-version-bump.md`）。

### 5.4 NFR4: スクリプト／フックを変更する場合のテスト追随

**状態**: ok

`em-workflow/scripts/` や `em-workflow/hooks/` に変更が及ぶ場合は、リポジトリルート `tests/` に
`test_*.py` を追加・更新し、`python3 -m unittest discover -s tests` が通ることを同じ変更の中で確認する
（`test/README.md`）。`destructive-guard.py` に触れる場合は
`python3 em-workflow/hooks/tests/run-destructive-guard.py` も走らせる（`.claude/rules/hook-tests.md`）。

## 6. UI/UX要件

該当なし。成果物は em-workflow プラグインのプロトコル文書（Markdown）と、必要なら Python フック／
スクリプトとその unittest のみで、ユーザーに見える視覚的表面・UI・画面遷移・デザイントークンの
いずれも持たない（design ステップは skipped）。

## 7. データ要件

### 7.1 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| workflow[] の implement step | `failed_kind` | `infra` \| `decision`（閉じた 2 値） | FR3〜FR5 の write 経路では必須 | `infra` = 孤児化・harness 障害などの外部要因、`decision` = 実装内容の失敗や計画見直しが必要なもの |
| workflow.yaml の `batch` セクション | `infra` 自動続行の上限値と現在の回数 | 数値 | — | 未設定キーは 0 として読む既存の読み取り規則に倣う。キー名は FR7 の TBD 解消後に確定 |

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- `failed_kind` の定義は `references/workflow-schema.md` の 1 箇所だけが所有する（NFR1）
- implement を `failed` に書く 3 経路の write とコミットの単位を変えない（NFR2）
- `failed_kind` を持たない既存の workflow.yaml に対する移行処理は行わない（FR9）

### 9.2 ビジネス上の制約

- 設計判断が必要な `failed` の停止挙動は従来どおり保つ

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から
導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、
`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、
およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび
`references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは
再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、
  記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要が
  ある。実際には生成されないパスが宣言されていても違反にはならない。implement タスクを 1 つも生成しない
  フィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は
  依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `docs-commit-conflict` が implement step の `failed` を書く第 4 経路である可能性（A2） | 中 | 前提が誤りと判明した場合、第 4 経路の分類（推奨: `infra`）を追加で規定する |
| `em-workflow/scripts/` / `em-workflow/hooks/` の Python 変更が必要かどうかが未確定（A4） | 低 | create-plan の調査に委ね、必要になった場合のみ NFR4 が発動する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `references/workflow-schema.md` の implement step に `failed_kind: infra | decision` が
      定義され、値の意味（infra = 孤児化・harness 障害などの外部要因、decision = 実装内容の失敗や
      計画見直しが必要なもの）が同ファイル 1 箇所で規定されている（FR1）
- [ ] AC2: implement を `failed` に書く 3 経路（I.2.c abort、batch の 2 回目 failed、route-back
      gate-rejected terminal）のいずれも `failed_kind` を必ず書くことがドキュメント上で規定されている。
      孤児化由来は `infra`、それ以外は `decision`（FR3・FR4・FR5）
- [ ] AC3: `skills/develop/SKILL.md` の停止条件 3 が、implement の `failed` については
      `failed_kind: decision` のときだけ発火すると規定されている（FR6）
- [ ] AC4: `failed_kind: infra` のとき implement を `pending` に戻し、その write をコミットしてから
      フェーズを実行する手順が規定されている（FR6・NFR2）
- [ ] AC5: `infra` 起因の自動続行に回数上限があり、上限到達時は `decision` 扱いで停止することが
      規定されている。上限値と回数の記録先が workflow.yaml の `batch` セクションであることが
      `references/workflow-schema.md` の `batch` ブロック節に定義されている（FR7）
- [ ] AC6: `references/batch-terminal-line.md` の `step_needs_intervention` の説明、
      `skills/develop/SKILL.md` の停止条件 3、`references/batch-mode.md` が更新されている（FR10）
- [ ] AC7: `failed_kind` を持たない既存の workflow.yaml が `decision` として扱われ、後方互換が
      保たれることが規定されている（FR9）
- [ ] AC8: `em-workflow/.claude-plugin/plugin.json` とルート `.claude-plugin/marketplace.json` の
      version が同値で上がっている（NFR3）

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1: `failed_kind: infra` の implement `failed` を持つ workflow.yaml を用意し、
      `--batch --once` で起動する。走行が停止条件 3 で停止せず、implement が `pending` に戻され、
      その write がコミットされたうえで implement フェーズが実行されることを確認する
- [ ] TS-2: `failed_kind: decision` の implement `failed` を持つ workflow.yaml を用意し、
      `--batch --once` で起動する。従来どおり停止条件 3 で停止し、
      `EM_WORKFLOW_TERMINAL: state=stopped step=implement reason=step_needs_intervention ...` の
      終端行が出ることを確認する
- [ ] TS-3: `failed_kind` を持たない（キー欠落の）implement `failed` の workflow.yaml で起動し、
      TS-2 と同じ停止挙動になる（= `decision` として扱われる）ことを確認する
- [ ] TS-4: `infra` 自動続行の回数が上限に達した状態の workflow.yaml で起動し、`decision` 扱いで
      停止することを確認する（上限値は FR7 の TBD 解消後に確定）
- [ ] TS-5: スクリプト／フックに変更が及んだ場合、`python3 -m unittest discover -s tests` が
      通ることを確認する

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `failed_kind` | implement step の `failed` に持たせる理由の分類。`infra` \| `decision` の閉じた 2 値 |
| `infra` | 外部要因（implementer の孤児化、harness 障害） |
| `decision` | 実装内容の失敗や計画の見直しが必要なもの |
| 停止条件 3 | `skills/develop/SKILL.md` Step B の停止条件のひとつ |

## 14. 確認事項

### 14.1 確認済み事項

- [x] design ステップ: skipped。成果物は em-workflow プラグインのプロトコル文書（Markdown）と、
      必要なら Python フック／スクリプトとその unittest のみ。ユーザーに見える視覚的表面・UI・
      画面遷移・デザイントークンのいずれも持たないため、design ステップの入力も出力も存在しない。

### 14.2 未確認・保留事項

- [ ] FR2: `failed_kind` のライフサイクル（設定・保持・クリア）— question_id: failed-kind.lifecycle
- [ ] FR4: batch の 2 回目 failed 経路での `failed_kind` の値 — question_id: batch.second-failure.kind
- [ ] FR5: route-back gate-rejected terminal での `failed_kind` の値 — question_id: gate-rejected.kind
- [ ] FR7: `infra` 自動続行の回数上限の値 — question_id: infra.retry-cap-value
- [ ] FR8: `infra` 自動続行を適用するモードの範囲 — question_id: infra.mode-scope

### 14.3 前提

- A1: 前提タスク「孤児 implementer の自動復旧」による経路は base revision 上で既に反映済みと判断した。
  `references/implement-phase.md` I.2.c 冒頭に orphaned-`launched` convergence（FR4）の記述があり、
  `references/workflow-schema.md` の journal 節に `em-workflow/scripts/journal-append-failed.py` が
  reason `orphaned` の `failed` を書く記述がある。したがって「孤児化由来かどうか」を I.2.c が判定する
  材料は既に存在する
- A2: `references/batch-terminal-line.md` の precedence rule は `docs-commit-conflict` を
  「step の status を `failed` にする」stop point の 1 つとして列挙しているが、その所有文書
  `references/phase-state.md` が `failed` にすると明記しているのは phase-state ファイル自身の `status`
  であり、workflow.yaml の step status ではない。本仕様は「タスク記述が列挙する 3 経路が implement step の
  `failed` を書く全経路である」という前提で組み立て、`docs-commit-conflict` は implement step の
  `failed_kind` の書き手ではないものとして扱う。この前提が誤りなら第 4 経路の分類（推奨: `infra`）が
  追加で必要になる
- A3: 停止条件 3 のもう一方のトリガである `needs_update`、および review / verify step の `failed` には
  `failed_kind` を適用しない（タスク記述のスコープ外指定に従う）
- A4: 本変更は Markdown のプロトコル文書更新が主であり、`em-workflow/scripts/` / `em-workflow/hooks/` の
  Python 変更が必要かどうかは create-plan の調査に委ねる。必要になった場合のみ NFR4 が発動する

## 15. 参考資料

- `em-workflow/references/workflow-schema.md`
- `em-workflow/references/implement-phase.md`
- `em-workflow/references/batch-mode.md`
- `em-workflow/references/batch-terminal-line.md`
- `em-workflow/skills/develop/SKILL.md`
- `.claude/rules/core-plugin-version-bump.md`
- `.claude/rules/hook-tests.md`
