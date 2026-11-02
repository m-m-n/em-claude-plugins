# Feature: merge-tip-binding

## Overview

merge スキルの再判定・取り込み・検証・マージの対象を、事前判定（preflight）か、判定し直した先端に結び付ける。手順 6.4 の PR ルートはロック後に読んだ先端で再判定し、手順 8 の `merge-git.py integrate` は取り込みの前に期待する先端と照合する。要件は `feature-docs/merge-tip-binding/REQUIREMENTS.md` にある。

## Objectives

- merge スキルの再判定・取り込み・検証・マージの対象を、preflight か、判定し直した先端に結び付ける。判定を経ていない先端は base に入れない（fail-closed）。
- 並行する走行が base を取り込んで先端を進め、その先端でマージを済ませていた場合、ロック後の再判定を internal_error ではなく already_merged で終える。

## User Stories

### US1: 判定を経ていない先端を base に入れない

merge スキルの取り込みは、preflight か判定し直した先端と一致するときだけ進み、一致しないときは verification_failed で止まる。

**Acceptance Criteria:**
- [ ] AC-3: `merge-git.py integrate` に、worktree HEAD と異なる期待値を渡すと、stop・verification_failed・detail `integration branch moved after preflight` を返す。このとき fetch と merge は走らず、integration ブランチの先端も変わらない。一致する値なら従来どおりの outcome を返す。オプションが無い、または 40 桁の小文字 16 進でないときは exit 2 で、stdout は空
- [ ] AC-4: 再現手順 2 の場面。preflight の後・integrate の前に integration ブランチへコミットを足すと、`integration_tip` を渡した integrate が verification_failed で止まり、そのコミットは取り込まれない（`tests/test_merge_local_route.py` の連鎖でも確かめる）
- [ ] AC-5: 手順 8 に次のことが書かれている。最初の取り込みでは `integration_tip` を、手順 12 の redo から戻ったときは `head_sha` を、期待値として渡す。verification_failed の stop では、手順 14 の後に終端する
- [ ] AC-6: SKILL.md の結果の値の表の verification_failed 行が、手順 8, 10, 13、出どころ merge-git integrate、手順 8 の固定文を含む。merge-result.md の verification_failed 行の Condition に手順 8 の不一致があり、Emitted by に merge-git integrate がある。reason code の数は 28 のまま

### US2: ロック後の再判定をその時点の先端で行う

並行する走行が先端を進めてマージを済ませていた場合、ロック後の再判定は already_merged で終わる。

**Acceptance Criteria:**
- [ ] AC-1: 手順 6.4 の PR ルートで、held の後・resolve の前に、単独の `cd "<project_root>"` と `git rev-parse --verify refs/heads/em-workflow/<feature>/integration` がこの順に並び、それぞれに timeout 行がある。resolve の `--integration-tip` には、その読み取り値の保持値が入り、`<integration_tip>` ではない。値が 40 桁の小文字 16 進でないとき、または git が失敗したときは、手順 14 の後 internal_error と書かれている
- [ ] AC-2: MERGED・headRefOid=T2 の PR は、`--integration-tip T2` で merged、T1 で none のまま（既存の `test_task0010_ac4_*` が通る）。手順 6.4 がロック後の先端を渡すことは、AC-1 の文書テストで検出する
- [ ] AC-7: 手順 6.4 に「先端は手順 4 / 5.2 と同じ `integration_tip`」が無い。ローカルルートの再判定は、呼ばれた時点の先端で判定すると書かれている

## Technical Requirements

### Functional Requirements

- **FR1:** PR ルートのロック後の再判定は、その時点の先端で行う — 手順 6.4 の PR ルートでは、held を得てから resolve を呼ぶまでの間に、integration ブランチの現在の先端を読む。読み方は、単独の `cd "<project_root>"` と `git rev-parse --verify refs/heads/em-workflow/<feature>/integration` を、別々の Bash 呼び出しで行う（それぞれに timeout 行を付ける）。出力（末尾の改行を除く）が 40 桁の小文字 16 進のときだけ、その値を新しい保持値にする（名前は計画で決める。例: `locked_tip`）。その値を `merge-pr.py resolve` の `--integration-tip` に渡す。git が失敗したとき、または値が 40 桁の小文字 16 進でないときは、手順 14 で保持タスクを止めてから internal_error で終端する。保持値 `integration_tip` は上書きしない。
- **FR2:** merge-git.py integrate が期待する先端と照合する — `merge-git.py integrate` に、期待する worktree HEAD を渡す必須オプションを足す（名前は計画で決める。例: `--expected-head`）。値は 40 桁の小文字 16 進だけを受け付け、それ以外やオプションが無い場合は exit 2 で終え、stdout には何も出さない。照合は、worktree の状態確認と HEAD == `refs/heads/<branch>` の確認の後、fetch と merge の前に行う。不一致なら fetch も merge もせず、ref も変えずに、outcome stop・reason verification_failed・detail は固定文 `integration branch moved after preflight` を返す。一致すれば従来どおり merged_clean / up_to_date / conflict / stop を返す。
- **FR3:** 手順 8 が期待する先端を渡し、不一致なら verification_failed で止まる — SKILL.md 手順 8 の integrate 呼び出しでは、期待する先端として、最初の取り込みで `integration_tip` を渡す。手順 12 の redo から戻ったときは、直前に検証した `head_sha` を渡す（手順 9 の解消を経た場合も含む）。手順 8 の stop の列挙に verification_failed を足す。ロック保持中なので、描画の前に手順 14 を行ってから、その reason と detail で終端する。
- **FR4:** 結果の値の契約に、手順 8 の不一致を足す — 28 個の閉じた集合は変えない。SKILL.md の結果の値の表の verification_failed 行で、次の 3 つを変える。出どころに merge-git integrate を足す。手順を 8, 10, 13 にする。detail に、手順 8 の固定文 `integration branch moved after preflight` を足す。`em-workflow/references/merge-result.md` の Reason codes 表の verification_failed 行も変える。Condition に「取り込み前の integration worktree HEAD が期待する先端と異なる」を足し、Emitted by に merge-git integrate を足す。`merge-result.py` の `REASON_CODES` は変えない。
- **FR5:** 手順 6.4 と保持する値の記述を、実際の挙動に合わせる — 手順 6.4 の「先端は手順 4 / 5.2 と同じ `integration_tip`」を書き換える。ローカルルートの再判定は、`merge-git.py merged` が、呼ばれた時点の integration ブランチの先端で判定する（挙動は変えない）。PR ルートは、FR1 で読んだ先端で判定する。保持する値では、`integration_tip` に「手順 8 の照合でも使う」ことを書き足し、ロック後に読んだ先端を新しい保持値として足す。
- **FR6:** 再発を検出するテスト — FR1・FR3・FR4・FR5 の文書テストを `tests/test_merge_skill_doc.py` に足す。FR2 のスクリプトテストを `tests/test_merge_git.py` と `tests/test_merge_local_route.py` に足す。新しい形と合わなくなる既存の固定テスト（reference_impact に列挙）は、新しい形に合わせて直す。既存の検知（偽の文書で照合が発火することを示すテスト）は削らない。

### Non-Functional Requirements

- **NFR1 - fail-closed:** 照合できないとき、または値が不正なときは、マージ側に倒れずに止まる。
- **NFR2 - コマンド形:** ガード hook が判定する操作とコマンド形は、SKILL の呼び出しの規則を守る。リテラルだけを使い、変数展開・コマンド置換・グロブ・リビジョン接尾辞は使わない。`cd` は単独の呼び出しにする。前景の Bash 呼び出しにはすべて、600000 以下の timeout 行を付ける。
- **NFR3 - 状態の持ち方:** 状態ファイルを新しく作らない。`workflow.yaml` には書き込まない。
- **NFR4 - テストの書き方:** テストは標準ライブラリの unittest だけで書き、一時ディレクトリの git リポジトリを使う。CPU に意図的な負荷をかけない（並行する書き手は、コミットを足して決定的に再現する）。
- **NFR5 - 記載の秘匿:** 出力・detail・文書に、ホームディレクトリの絶対パスと Notion の URL を書かない。
- **NFR6 - version:** em-workflow の version は手で上げない（patch は Actions が上げる）。

## Implementation Approach

### Architecture

**System Architecture:**

変更はスキル手順書・Python スクリプト・契約文書・テストだけ。UI は無い。

**Component Diagram:**
```
merge スキル SKILL.md
├── 手順 6.4（ロック後の再判定）
│   ├── PR ルート: cd → git rev-parse（ロック後の先端）→ merge-pr.py resolve --integration-tip <ロック後の先端>
│   └── ローカルルート: merge-git.py merged（呼ばれた時点の先端で判定。挙動は変えない）
├── 手順 8（取り込み）
│   └── merge-git.py integrate <期待する先端のオプション>
├── 保持する値（integration_tip / ロック後の先端 / head_sha）
└── 結果の値の表（verification_failed 行）
em-workflow/references/merge-result.md（Reason codes 表の verification_failed 行）
merge-result.py の REASON_CODES（変えない。28 個のまま）
```

### Data Flow

```
preflight（手順 4 / 5.2）→ integration_tip
  ├─ 手順 6.4 PR ルート: held → cd "<project_root>" → git rev-parse --verify refs/heads/em-workflow/<feature>/integration
  │     → 40 桁の小文字 16 進ならロック後の先端（例: locked_tip）→ merge-pr.py resolve --integration-tip
  │     → git 失敗 / 不正な値なら 手順 14 → internal_error
  └─ 手順 8（最初の取り込み）: merge-git.py integrate <期待値 = integration_tip>
手順 12 の redo → 手順 8: merge-git.py integrate <期待値 = 直前に検証した head_sha>

merge-git.py integrate:
  期待値の検査（無い / 不正 → exit 2、stdout 空）
  → worktree の状態確認 → HEAD == refs/heads/<branch> の確認
  → HEAD と期待値の照合
       不一致 → stop / verification_failed / "integration branch moved after preflight"（fetch・merge なし、ref 不変）
       一致   → fetch → merge → merged_clean / up_to_date / conflict / stop
```

### API Design

#### Endpoint 1: merge-git.py integrate

**Request:**
```
merge-git.py integrate <既存の引数> <期待する worktree HEAD の必須オプション（名前は計画で決める。例: --expected-head）> <40 桁の小文字 16 進>
```

**Response:**
- 一致: 従来どおり merged_clean / up_to_date / conflict / stop
- 不一致:
```
outcome: stop
reason: verification_failed
detail: integration branch moved after preflight
```

**Error Response:**
- オプションが無い、または値が 40 桁の小文字 16 進でない: exit 2、stdout には何も出さない

#### Endpoint 2: merge-pr.py resolve（挙動は変えない）

**Request:**
- 手順 5.2 / 5.3: `--integration-tip` に `integration_tip`
- 手順 6.4 の PR ルート: `--integration-tip` にロック後の先端の保持値
- 手順 13.2: `head_sha`

### Database Schema

該当なし。状態ファイルを新しく作らない（NFR3）。保持する値は次のとおり。

| Value | Format | Description |
|-------|--------|-------------|
| `integration_tip` | 40 桁の小文字 16 進 | 手順 4 / 5.2 の先端。手順 8 の照合でも使う。上書きしない |
| ロック後の先端（例: `locked_tip`） | 40 桁の小文字 16 進 | 手順 6.4 の PR ルートで held の後に読んだ先端。手順 6.4 の resolve にだけ使う |
| `head_sha` | 40 桁の小文字 16 進 | 直前に検証した先端。手順 12 の redo から戻ったときの手順 8 の期待値 |

### Dependencies

**Internal Dependencies:**
- merge スキルの SKILL.md: 手順 6.4、手順 8、保持する値、結果の値の表を変える
- `merge-git.py integrate`: 期待する先端の必須オプションと照合を足す
- `merge-git.py merged`: 挙動は変えない
- `merge-pr.py resolve`: 挙動は変えない
- `em-workflow/references/merge-result.md`: Reason codes 表の verification_failed 行を変える
- `merge-result.py`: `REASON_CODES` は変えない

**External Dependencies:**
- git: `git rev-parse --verify` で integration ブランチの先端を読む

### File Structure

```
tests/
├── test_merge_skill_doc.py     # FR1・FR3・FR4・FR5 の文書テストを足す
├── test_merge_git.py           # FR2 のスクリプトテストを足す
├── test_merge_local_route.py   # FR2 の連鎖テストを足す
└── test_merge_pr.py            # 既存の test_task0010_ac4_*（TS2）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/merge-tip-binding/**`
- `test-docs/merge-tip-binding/**`

`feature-docs/merge-tip-binding/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/merge-tip-binding/**` covers `test-docs/merge-tip-binding/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/merge-tip-binding/` directory at all; the declared
`test-docs/merge-tip-binding/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1（AC-1）: 文書テスト。手順 6 の Bash ブロックを文書の順に並べ、次を確かめる。verify --wait、`cd "<project_root>"`、TIP_REF の読み取り、resolve の順になっている。resolve の `--integration-tip` の値は、ロック後の保持値の placeholder である。各ブロックに timeout 行がある。読み取りの失敗の扱いに internal_error と手順 14 がある。偽の文書（読み取りが無い、または `<integration_tip>` のまま）では、照合が発火する
- [ ] TS3（AC-3）: `tests/test_merge_git.py`。一時リポジトリで integrate を呼び、次を確かめる。期待値が不一致なら stop・verification_failed・固定 detail になり、ブランチの先端と worktree が変わらない。git のシムのログで fetch と merge が走っていない。一致なら既存の各 outcome を返す。オプションが無い、大文字、短い値のときは exit 2 で stdout が空
- [ ] TS5（AC-5）: 文書テスト。手順 8 の integrate 形に期待値のオプションがあり、初回の値 `integration_tip` と redo の値 `head_sha` の両方が書かれている。手順 8 の stop の列挙に verification_failed と手順 14 がある
- [ ] TS6（AC-6）: 文書テスト。結果の値の表の verification_failed 行の手順が {8, 10, 13} で、出どころに merge-git がある。merge-result.md の verification_failed 行に、手順 8 の不一致の条件と merge-git integrate がある。`REASON_CODES` は 28 個のまま
- [ ] TS7（AC-7）: 文書テスト。手順 6.4 の項目 4 に「手順 4 / 5.2 と同じ `integration_tip`」が無く、ローカルルートは呼ばれた時点の先端で判定すると書かれている

### Integration Tests
- [ ] TS2（AC-2）: `tests/test_merge_pr.py` の既存の `test_task0010_ac4_*` で、resolve の先端での絞り込みが変わっていないことを確かめる
- [ ] TS4（AC-4）: `tests/test_merge_local_route.py` の連鎖。preflight で `integration_tip` を得た後、integration ブランチにコミットを足す。integrate に `integration_tip` を渡すと verification_failed で止まり、base は変わらない。コミットを足さない連鎖は、従来どおりマージまで進む
- [ ] TS8（AC-8）: `python3 -m unittest discover -s tests`

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 期待値のオプションが無い、大文字、短い値: exit 2 で stdout が空（TS3）
- [ ] 手順 6.4 のロック後の先端の読み取りで git が失敗する、または値が 40 桁の小文字 16 進でない: 手順 14 の後 internal_error（TS1）
- [ ] 手順 12 の redo から手順 8 に戻る（手順 9 の解消を経た場合も含む）: 期待値は直前に検証した `head_sha`（TS5）

### Performance Tests
- 該当なし。CPU に意図的な負荷をかけない（NFR4）

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** ロック後の先端の読み取り値（FR1）と integrate の期待値（FR2）は、40 桁の小文字 16 進だけを受け付ける
- **Data Protection:** 出力・detail・文書に、ホームディレクトリの絶対パスと Notion の URL を書かない（NFR5）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし
- **Command Form:** NFR2 に従う

## Error Handling

### Error Codes

| Code | Description | Emitted by | Handling |
|------|-------------|------------|----------|
| verification_failed | 取り込み前の integration worktree HEAD が期待する先端と異なる。detail は `integration branch moved after preflight` | merge-git integrate（手順 8） | fetch・merge をせず ref も変えずに stop。手順 14 の後、その reason と detail で終端する |
| internal_error | 手順 6.4 のロック後の先端の読み取りで git が失敗した、または値が 40 桁の小文字 16 進でない | SKILL.md 手順 6.4 | 手順 14 で保持タスクを止めてから終端する |
| exit 2 | integrate の期待値のオプションが無い、または 40 桁の小文字 16 進でない | merge-git.py integrate | stdout には何も出さない |

### Error Flow

```
不一致・不正な値 → マージ側に倒れずに止まる（NFR1）→ ロック保持中なら手順 14 → reason と detail で終端
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] AC-1 から AC-8 を満たす
- [ ] `python3 -m unittest discover -s tests` が通る（AC-8）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- a1: 取り込み前の照合は `merge-git.py integrate` の中で行う。期待する先端は、新しい必須オプションで渡す。値は 40 桁の小文字 16 進だけを受け付け、それ以外は exit 2。不一致なら fetch も merge もせず、ref を変えずに stop を返す
- a2: 手順 8 の期待値は、最初の取り込みで `integration_tip`、手順 12 の redo から戻ったときは直前に検証した `head_sha`（手順 9 の解消を経た場合も含む）
- a3: ロック後の先端の読み取りで git が失敗したとき、または出力が不正な値のときは、手順 14 の後 internal_error で終端する
- a4: ロック後に読んだ先端は、新しい保持値として手順 6.4 の resolve にだけ使う。`integration_tip` は上書きせず、手順 8 の照合は preflight の値で行う
- a5: ローカルルートの再判定（`merge-git.py merged`）の挙動は変えず、手順 6.4 の記述を実際の挙動に合わせる
- a6: `merge-pr.py resolve` の挙動は変えない。手順 5.2 / 5.3 は `integration_tip`、手順 13.2 は `head_sha` のまま
- a7: em-workflow の version は触らない

## References

- 要件定義書: `feature-docs/merge-tip-binding/REQUIREMENTS.md`
- Reason codes: `em-workflow/references/merge-result.md`
