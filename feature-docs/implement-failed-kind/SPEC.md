# Feature: implement-failed-kind

## Overview

implement step の `failed` に理由の分類 `failed_kind`（`infra` | `decision`）を持たせ、
インフラ起因の失敗と設計判断が必要な失敗を workflow.yaml 上で区別する。`infra` では
develop Step B の停止条件 3 を発火させず implement を `pending` に戻して走行を継続し、
`decision` では従来どおり停止して人に制御を返す。要件の全体像は
`feature-docs/implement-failed-kind/REQUIREMENTS.md` を参照する。

## Objectives

- implement step の `failed` に理由の分類を持たせ、インフラ起因の失敗と設計判断が必要な失敗を
  workflow.yaml 上で区別できるようにする
- インフラ起因の `failed` では develop Step B の停止条件 3 を発火させず、implement を `pending` に
  戻して走行を継続させる
- 設計判断が必要な `failed` は従来どおり停止条件 3 で人に制御を返す挙動を保つ
- 無人走行（`--batch`）が、人の判断を要しない失敗で 1〜2 分ごとの同一報告を繰り返す状態に陥らない
  ようにする

## User Stories

### US1: インフラ起因の失敗で走行を止めない

As em-workflow の利用者, I want implementer の孤児化や harness 障害で implement が `failed` に
なったときに走行を自動で継続してほしい, so that 人の判断を要しない失敗で無人走行が止まらない。

**Acceptance Criteria:**
- [ ] AC4: `failed_kind: infra` のとき implement を `pending` に戻し、その write をコミットしてから
      フェーズを実行する手順が規定されている（FR6・NFR2）
- [ ] AC5: `infra` 起因の自動続行に回数上限があり、上限到達時は `decision` 扱いで停止することが
      規定されている。上限値と回数の記録先が workflow.yaml の `batch` セクションであることが
      `references/workflow-schema.md` の `batch` ブロック節に定義されている（FR7）

### US2: 設計判断が必要な失敗では制御を受け取る

As em-workflow の利用者, I want 実装内容の失敗や計画見直しが必要な `failed` では走行を止めてほしい,
so that 判断が必要な時点で制御が戻る。

**Acceptance Criteria:**
- [ ] AC3: `skills/develop/SKILL.md` の停止条件 3 が、implement の `failed` については
      `failed_kind: decision` のときだけ発火すると規定されている（FR6）
- [ ] AC7: `failed_kind` を持たない既存の workflow.yaml が `decision` として扱われ、後方互換が
      保たれることが規定されている（FR9）

## Technical Requirements

### Functional Requirements

- **FR1 — implement step への `failed_kind` フィールド追加 (ok):**
  `references/workflow-schema.md` の `workflow[]` の implement step に `failed_kind` を追加する。
  値は `infra` | `decision` の閉じた 2 値。`infra` は外部要因（implementer の孤児化、harness 障害）、
  `decision` は実装内容の失敗や計画の見直しが必要なもの。`failed_items[].category` 節と同じ形式で
  workflow-schema.md を唯一の定義元とし、他ドキュメントはリポジトリ相対パスで引用するだけにする。
- **FR2 — `failed_kind` のライフサイクル（設定・保持・クリア） (tbd):**
  `failed_kind` を書く時点・保持する期間・クリアする時点を規定する。implement が `failed` 以外の
  status に遷移するときにフィールドをどう扱うかを含む。
  *TBD 理由*: 未決定事項『failed_kind のライフサイクル』（question_id: failed-kind.lifecycle、
  packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は
  `clear_on_leaving_failed`（implement が `failed` を離れる書き込みと同じ write set で `failed_kind` を
  null に戻す）。create-plan の tbd-resolution で確定する。
- **FR3 — I.2.c abort 経路での `failed_kind` 書き込み (ok):**
  `references/implement-phase.md` I.2.c の abort phase 分岐が implement を `failed` に書く単一 write
  （実装フェーズ中断のターミナル status write）に `failed_kind` を必ず含める。失敗の journal reason が
  `orphaned`（I.2.b の orphan-recovery が記録するもの）由来なら `infra`、それ以外は `decision`。
  write と `commit-docs.sh` によるコミットの単位は現行のまま変えない。
- **FR4 — batch の 2 回目 failed 経路での `failed_kind` 書き込み (tbd):**
  `references/batch-mode.md` Non-packet gates の `implement.failed-task`（同一タスクが 2 回目に失敗した
  場合の abort phase）が implement を `failed` に書くときの `failed_kind` の値を規定する。
  *TBD 理由*: 未決定事項『batch 2 回目 failed の分類』（question_id: batch.second-failure.kind、
  packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `second_always_decision`
  （2 回目失敗は原因を問わず常に `decision`）。この推奨は既存の precedence 規則と整合する —
  `references/batch-terminal-line.md` の Stop point coverage で `implement-second-failure` は
  `implement_task_failed` として `stop-condition-3` より優先されるため、`infra` に分類しても走行は
  停止する。create-plan の tbd-resolution で確定する。
- **FR5 — route-back gate-rejected terminal での `failed_kind` 書き込み (tbd):**
  `references/implement-phase.md` I.2.c の route-back gate が成立しなかった経路
  （`docs({feature}): implement route-back gate rejected` をコミットするターミナル status write）が書く
  `failed_kind` の値を規定する。
  *TBD 理由*: 未決定事項『gate-rejected terminal の分類』（question_id: gate-rejected.kind、
  packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `always_decision`
  （gate 不成立は `merged` / `in_progress` タスクの存在という計画側の状態が原因であり、自動続行しても
  同じ gate で再び弾かれるため常に `decision`）。create-plan の tbd-resolution で確定する。
- **FR6 — 停止条件 3 の発火条件を `failed_kind: decision` に限定する (ok):**
  `skills/develop/SKILL.md` Step B の停止条件 3 は、implement step の `failed` については
  `failed_kind: decision` のときだけ発火する。`failed_kind: infra` のときは停止せず、implement step を
  `pending` に戻す write を行い、その write を `commit-docs.sh` でコミットしてから当該フェーズを実行する。
  既存の「停止条件 3 との優先関係」ブロック（フェーズプロトコルが自動再エントリのために設定した
  `needs_update` の carve-out）と、「batch: verify の cap 到達に対する停止条件の例外」は変更しない。
- **FR7 — `infra` 自動続行の回数上限とその記録 (tbd):**
  `failed_kind: infra` を理由とする自動続行に回数上限を設け、上限到達時は `decision` 扱いで停止する。
  上限値と現在の回数は workflow.yaml の `batch` セクションに記録する（`references/workflow-schema.md` の
  `batch` ブロック節に新キーとして定義し、未設定キーは 0 として読む既存の読み取り規則に倣う）。
  上限値以外の構造（`batch` セクションへ記録すること、上限到達時は `decision` 扱いで停止すること）は
  受け入れ条件で確定済み。
  *TBD 理由*: 未決定事項『infra 起因の自動続行の回数上限』（question_id: infra.retry-cap-value、
  packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `cap_2`（上限 2 回）。
  上限値そのものが未確定のため、キー名・カウント更新規則・上限到達時の報告文面もあわせて create-plan の
  tbd-resolution で確定する。
- **FR8 — `infra` 自動続行を適用するモードの範囲 (tbd):**
  `failed_kind: infra` による自動続行を batch モードだけに適用するか、interactive にも適用するかを
  規定する。
  *TBD 理由*: 未決定事項『infra 自動続行の適用モード』（question_id: infra.mode-scope、
  packet: create-spec-q0001）が batch で TBD として記録された。worker 推奨は `batch_only`（回数の記録先が
  workflow.yaml の `batch` セクションであること、および `batch` ブロックが --batch 走行でのみ作成される
  既存規則と整合するため）。create-plan の tbd-resolution で確定する。
- **FR9 — `failed_kind` 欠落時の後方互換 (ok):**
  `failed_kind` を持たない既存の workflow.yaml の implement `failed` は `decision` として扱う。移行処理は
  行わない。この扱いは `failed_kind` を必須で書く新規 write 経路（FR3〜FR5）の要求を緩めない —
  `failed_items[].category` の pre-change compatibility 節と同じ形をとる。
- **FR10 — 関連ドキュメントの更新 (ok):**
  `references/batch-terminal-line.md` の `step_needs_intervention` の Meaning 行（現在
  「A workflow step reported `failed` or `needs_update`」）と Stop point coverage の `stop-condition-3` 行の
  記述、`skills/develop/SKILL.md` の停止条件 3 の記述、`references/batch-mode.md`
  （`implement.failed-task` 行および「Failure stops are UNCHANGED」の記述）を、`failed_kind` による分岐に
  合わせて更新する。

### Non-Functional Requirements

- **NFR1 — SSOT 規律 (ok):**
  `failed_kind` の定義・必須性・閉じた語彙は `references/workflow-schema.md` の 1 箇所だけが所有し、
  他ドキュメント（implement-phase.md / develop SKILL.md / batch-mode.md / batch-terminal-line.md）は
  リポジトリ相対パスで引用するだけにする。値の再定義を複数箇所に置かない。
- **NFR2 — write とコミットの単位を変えない (ok):**
  implement を `failed` に書く 3 経路は「ターミナル status write とそのコミットが唯一の副作用」という
  現行不変条件を保つ。`failed_kind` はその同じ write に含める（追加の write / 追加のコミットにしない）。
  停止条件 3 の `infra` 分岐で implement を `pending` に戻す write も、フェーズ実行前に 1 回のコミットとして
  確定させる。
- **NFR3 — プラグイン version bump (ok):**
  `em-workflow/` 配下を変更するため、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` と
  リポジトリルート `.claude-plugin/marketplace.json` の当該 version を同値で上げる
  （`.claude/rules/core-plugin-version-bump.md`）。
- **NFR4 — スクリプト／フックを変更する場合のテスト追随 (ok):**
  `em-workflow/scripts/` や `em-workflow/hooks/` に変更が及ぶ場合は、リポジトリルート `tests/` に
  `test_*.py` を追加・更新し、`python3 -m unittest discover -s tests` が通ることを同じ変更の中で確認する
  （`test/README.md`）。`destructive-guard.py` に触れる場合は
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` も走らせる（`.claude/rules/hook-tests.md`）。

## Implementation Approach

### Architecture

変更対象は em-workflow プラグインのプロトコル文書（Markdown）と、必要なら Python フック／スクリプトと
その unittest。`failed_kind` の定義は `references/workflow-schema.md` が単独で所有し、他文書はリポジトリ
相対パスで引用する（NFR1）。

```
references/workflow-schema.md            # failed_kind の定義元（infra | decision）+ batch ブロックの回数キー
        ▲ 引用のみ
        ├── references/implement-phase.md        # I.2.c abort / route-back gate-rejected の write 経路
        ├── references/batch-mode.md             # implement.failed-task の write 経路
        ├── references/batch-terminal-line.md    # step_needs_intervention / stop-condition-3 の記述
        └── skills/develop/SKILL.md              # Step B 停止条件 3 の分岐
```

### Data Flow

```
implement が失敗
  → write 経路（I.2.c abort / batch 2 回目 failed / route-back gate-rejected）が
    ターミナル status write に failed_kind を含めて 1 回だけ書き、commit-docs.sh でコミット
  → develop Step B が workflow.yaml を読む
      failed_kind: decision（またはキー欠落）→ 停止条件 3 が発火して停止
      failed_kind: infra                     → 回数上限内なら implement を pending に戻す write
                                               → commit-docs.sh でコミット → 当該フェーズを実行
                                               → 上限到達なら decision 扱いで停止
```

### Data Model

`workflow[]` の implement step:

| Key | Value | Required | Description |
|-----|-------|----------|-------------|
| `failed_kind` | `infra` \| `decision` | FR3〜FR5 の write 経路では必須。欠落は `decision` として読む（FR9） | `infra` = 実装者の孤児化・harness 障害などの外部要因、`decision` = 実装内容の失敗や計画見直しが必要なもの |

workflow.yaml の `batch` セクション（FR7）:

| Key | Value | Description |
|-----|-------|-------------|
| `infra` 自動続行の上限値と現在の回数 | 数値 | `references/workflow-schema.md` の `batch` ブロック節に新キーとして定義する。未設定キーは 0 として読む既存の読み取り規則に倣う。キー名と上限値は FR7 の TBD 解消後に確定 |

### Dependencies

**Internal Dependencies:**
- 前提タスク「孤児 implementer の自動復旧」: `references/implement-phase.md` I.2.c の
  orphaned-`launched` convergence と、`em-workflow/scripts/journal-append-failed.py` が書く reason
  `orphaned` の `failed`。FR3 の `infra` 判定材料（A1）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Integration Tests

- [ ] **TS-1** (FR6, NFR2): `failed_kind: infra` の implement `failed` を持つ workflow.yaml を用意し、
      `--batch --once` で起動する。走行が停止条件 3 で停止せず、implement が `pending` に戻され、
      その write がコミットされたうえで implement フェーズが実行されることを確認する
- [ ] **TS-2** (FR6): `failed_kind: decision` の implement `failed` を持つ workflow.yaml を用意し、
      `--batch --once` で起動する。従来どおり停止条件 3 で停止し、
      `EM_WORKFLOW_TERMINAL: state=stopped step=implement reason=step_needs_intervention ...` の終端行が
      出ることを確認する
- [ ] **TS-4** (FR7): `infra` 自動続行の回数が上限に達した状態の workflow.yaml で起動し、`decision` 扱いで
      停止することを確認する（上限値は FR7 の TBD 解消後に確定）

### Edge Cases

- [ ] **TS-3** (FR9): `failed_kind` を持たない（キー欠落の）implement `failed` の workflow.yaml で起動し、
      TS-2 と同じ停止挙動になる（= `decision` として扱われる）ことを確認する

### Unit Tests

- [ ] **TS-5** (NFR4): スクリプト／フックに変更が及んだ場合、`python3 -m unittest discover -s tests` が
      通ることを確認する

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Assumptions

- **A1**: 前提タスク「孤児 implementer の自動復旧」による経路は base revision 上で既に反映済みと判断した。
  `references/implement-phase.md` I.2.c 冒頭に orphaned-`launched` convergence（FR4）の記述があり、
  `references/workflow-schema.md` の journal 節に `em-workflow/scripts/journal-append-failed.py` が
  reason `orphaned` の `failed` を書く記述がある。したがって「孤児化由来かどうか」を I.2.c が判定する材料は
  既に存在する
- **A2**: `references/batch-terminal-line.md` の precedence rule は `docs-commit-conflict` を
  「step の status を `failed` にする」stop point の 1 つとして列挙しているが、その所有文書
  `references/phase-state.md` が `failed` にすると明記しているのは phase-state ファイル自身の `status` であり、
  workflow.yaml の step status ではない。本仕様は「タスク記述が列挙する 3 経路が implement step の `failed` を
  書く全経路である」という前提で組み立て、`docs-commit-conflict` は implement step の `failed_kind` の書き手では
  ないものとして扱う。この前提が誤りなら第 4 経路の分類（推奨: `infra`）が追加で必要になる
- **A3**: 停止条件 3 のもう一方のトリガである `needs_update`、および review / verify step の `failed` には
  `failed_kind` を適用しない（タスク記述のスコープ外指定に従う）
- **A4**: 本変更は Markdown のプロトコル文書更新が主であり、`em-workflow/scripts/` / `em-workflow/hooks/` の
  Python 変更が必要かどうかは create-plan の調査に委ねる。必要になった場合のみ NFR4 が発動する

## Design Step

**Status**: skipped

成果物は em-workflow プラグインのプロトコル文書（Markdown）と、必要なら Python フック／スクリプトと
その unittest のみ。ユーザーに見える視覚的表面・UI・画面遷移・デザイントークンのいずれも持たないため、
design ステップの入力も出力も存在しない。

## Success Criteria

- [ ] AC1: `references/workflow-schema.md` の implement step に `failed_kind: infra | decision` が定義され、
      値の意味（infra = 孤児化・harness 障害などの外部要因、decision = 実装内容の失敗や計画見直しが必要な
      もの）が同ファイル 1 箇所で規定されている（FR1）
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
- [ ] AC8: `em-workflow/.claude-plugin/plugin.json` とルート `.claude-plugin/marketplace.json` の version が
      同値で上がっている（NFR3）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- [ ] FR2: `failed_kind` のライフサイクル（設定・保持・クリア） - 未決定事項『failed_kind のライフサイクル』
      （question_id: failed-kind.lifecycle、packet: create-spec-q0001）が batch で TBD として記録された。
      worker 推奨は `clear_on_leaving_failed`。create-plan の tbd-resolution で確定する。
- [ ] FR4: batch の 2 回目 failed 経路での `failed_kind` 書き込み - 未決定事項『batch 2 回目 failed の分類』
      （question_id: batch.second-failure.kind、packet: create-spec-q0001）が batch で TBD として記録された。
      worker 推奨は `second_always_decision`。create-plan の tbd-resolution で確定する。
- [ ] FR5: route-back gate-rejected terminal での `failed_kind` 書き込み - 未決定事項
      『gate-rejected terminal の分類』（question_id: gate-rejected.kind、packet: create-spec-q0001）が
      batch で TBD として記録された。worker 推奨は `always_decision`。create-plan の tbd-resolution で確定する。
- [ ] FR7: `infra` 自動続行の回数上限とその記録 - 未決定事項『infra 起因の自動続行の回数上限』
      （question_id: infra.retry-cap-value、packet: create-spec-q0001）が batch で TBD として記録された。
      worker 推奨は `cap_2`。キー名・カウント更新規則・上限到達時の報告文面もあわせて create-plan の
      tbd-resolution で確定する。
- [ ] FR8: `infra` 自動続行を適用するモードの範囲 - 未決定事項『infra 自動続行の適用モード』
      （question_id: infra.mode-scope、packet: create-spec-q0001）が batch で TBD として記録された。
      worker 推奨は `batch_only`。create-plan の tbd-resolution で確定する。

## References

- Requirements document: `feature-docs/implement-failed-kind/REQUIREMENTS.md`
- Workflow schema (SSOT for `failed_kind`): `em-workflow/references/workflow-schema.md`
- Implement phase protocol: `em-workflow/references/implement-phase.md`
- Batch mode: `em-workflow/references/batch-mode.md`
- Batch terminal line: `em-workflow/references/batch-terminal-line.md`
- Develop skill (Step B stop conditions): `em-workflow/skills/develop/SKILL.md`
- Plugin version bump rule: `.claude/rules/core-plugin-version-bump.md`
- Hook test rule: `.claude/rules/hook-tests.md`
