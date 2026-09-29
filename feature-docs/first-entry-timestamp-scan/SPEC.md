# Feature: first-entry-timestamp-scan

## Overview

D2 form 2（marker による現セッション解決）と、それを使う I.2.b の orphan recovery に回帰テストを 2 件追加する。recover-orphaned-task.py の挙動は変えない。要件の詳細は `feature-docs/first-entry-timestamp-scan/REQUIREMENTS.md` を参照する。

## Objectives

- D2 form 2（marker による現セッション解決）が、先頭に timestamp の無い記録を持つ transcript でも current-session-unknown に落ちないことを、テストで継続的に守る
- I.2.b の orphan recovery（FR2 の証明経路）が、コマンドライン入口から form 2 で呼ばれたときに成立することを、テストで固定する

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** コマンドライン入口から form 2 を通す回帰テスト。recover-orphaned-task.py をコマンドライン入口から subprocess で呼び、`--marker` で D2 form 2 を通すテストを追加する。現セッションの transcript は、先頭記録が timestamp を持たず、marker を含む。それ以外は孤児であることが証明できる fixture にする。結果は recovered で、journal には reason orphaned の failed がちょうど 1 件追記される
- **FR2:** 実際の transcript の冒頭を模した fixture の回帰テスト。type の異なる timestamp の無い記録を 3 件以上並べ、その後に有効な timestamp を 15:00、10:00 の順で置いた transcript を fixture にする。marker による解決が（ファイル名の stem, 10:00）を返すことを確かめるテストを追加する
- **FR3:** 開始時刻の導出規則は変えない。recover-orphaned-task.py の挙動は変えない。D2 form 2 の開始時刻は、今までどおり、確定した transcript の中で最も早い解析可能な timestamp とする。IMPLEMENTATION.md D2 と TS-14 の意味も変えない

### Non-Functional Requirements
- **NFR1:** 追加するテストはリポジトリ直下の `tests/` の `test_*.py` に置き、標準ライブラリだけを使う。transcripts ディレクトリは必ず `--transcripts-dir`（または引数）で一時ディレクトリを指定し、実際の `~/.claude` を読み書きしない
- **NFR2:** `python3 -m unittest discover -s tests` をリポジトリのルートで実行し、失敗 0・エラー 0 で終わる
- **NFR3:** これまで証明できなかった復旧が、新たに証明できるようになる変更をしない（安全側に倒す方向を保つ）
- **NFR4:** em-workflow の version は手で変えない

## Implementation Approach

### Architecture

変更対象は `tests/` 配下の unittest だけ。`em-workflow/scripts/recover-orphaned-task.py` は変更しない（FR3）。

### Data Flow

FR1（コマンドライン入口）:

```
テスト → subprocess: recover-orphaned-task.py
           --journal / --agents-index / --task / --transcripts-dir <一時ディレクトリ> / --marker
         → D2 form 2 で現セッションを解決
         → journal-append-failed.py（実物）で journal に failed を追記
         ← 終了コード 0、stdout {"outcome":"recovered","task":<task>,"reason":""}
```

`--current-session-id` と `--current-session-start` は渡さない。

FR2（関数呼び出し）:

```
テスト → resolve_current_session(None, None, marker, dir)
       ← (stem, 10:00)
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/recover-orphaned-task.py`: FR1 はコマンドライン入口を subprocess で呼び、FR2 は `resolve_current_session` を呼ぶ
- journal-append-failed.py: FR1 で実物を使う

**External Dependencies:**
- なし（標準ライブラリだけを使う。NFR1）

### File Structure

```
tests/
└── test_*.py    # 追加するテスト（NFR1）
```

### Fixture

FR1 / TS-1:
- 現セッションの transcript は、timestamp の無い先頭記録と、marker を含み timestamp を持つ後続行から成る
- 記録済みセッションの transcript は、現セッションの開始より厳密に前に活動が止まっている
- journal の最終イベントは launched
- agent index のエントリは launch に結び付いている

FR2 / TS-2:
- marker を含む transcript
- 冒頭に type の異なる timestamp の無い記録が 3 件以上並ぶ
- その後に有効な timestamp を持つ行が 15:00、10:00 の順で続く

### 変えない規則

- D2 form 2 の開始時刻は、確定した transcript の中で最も早い解析可能な timestamp とする（FR3）
- D2 form 2 の marker 走査（更新時刻が新しい順、marker を含む最初の transcript に確定、古い transcript に戻らない）と、form 1 が優先される規則（A2）
- SC6 の current-session-unknown の意味と、解析できる timestamp が 1 つも無い transcript を未解決として扱う規則（A3）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/first-entry-timestamp-scan/**`
- `test-docs/first-entry-timestamp-scan/**`

`feature-docs/first-entry-timestamp-scan/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/first-entry-timestamp-scan/**` covers `test-docs/first-entry-timestamp-scan/{T}.tests.yaml`, the
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

### Unit Tests
- [ ] TS-2 (FR2, AC-2): marker を含む transcript を用意する。冒頭に type の異なる timestamp の無い記録が 3 件以上並び、その後に有効な timestamp を持つ行が 15:00、10:00 の順で続く。この transcript に対して `resolve_current_session(None, None, marker, dir)` を呼ぶ - (stem, 10:00) が返る。先頭行だけを見る実装なら None、位置で最初を採る実装なら 15:00 になるため、どちらへの退行も検出できる

### Integration Tests
- [ ] TS-1 (FR1, AC-1): コマンドライン入口から `--marker`（form 2）で実行する。現セッションの transcript は timestamp の無い先頭記録と、marker を含み timestamp を持つ後続行から成る。記録済みセッションの transcript は、現セッションの開始より厳密に前に活動が止まっている。journal の最終イベントは launched で、agent index のエントリは launch に結び付いている。journal ヘルパーは実物（journal-append-failed.py）を使う - 終了コード 0、stdout は recovered の JSON、journal には launched の後に reason orphaned の failed が 1 行だけ増える
- [ ] TS-3 (NFR1, NFR2, AC-4): リポジトリのルートで `python3 -m unittest discover -s tests` を実行する - 失敗 0・エラー 0

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Manual Tests
- [ ] TS-4 (AC-5): 実際のセッションで marker を出力した後、transcripts ディレクトリに対して D2 form 2 の解決を 1 度読み取り専用で実行する - 現セッションの transcript の stem と開始時刻が返る。current-session-unknown になれば失敗

### Edge Cases
- [ ] 先頭記録が timestamp を持たない transcript（TS-1、TS-2）
- [ ] 有効な timestamp が位置の順と時刻の順で逆になっている transcript（15:00、10:00 の順。TS-2）

### Performance Tests

該当なし

## Security Considerations

該当なし

## Error Handling

該当なし

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC-1 (FR1): コマンドライン入口を subprocess で呼ぶテストがある。引数は `--journal`、`--agents-index`、`--task`、一時ディレクトリの `--transcripts-dir`、`--marker` で、`--current-session-id` と `--current-session-start` は渡さない。現セッションの transcript は先頭記録が timestamp を持たず marker を含み、ほかの条件は孤児と証明できる fixture になっている。このテストで、終了コード 0、stdout が `{"outcome":"recovered","task":<task>,"reason":""}`、journal に reason orphaned の failed がちょうど 1 件追記されることを確かめる
- [ ] AC-2 (FR2): 先頭に type の異なる timestamp の無い記録が 3 件以上並び、その後に有効な timestamp が 15:00、10:00 の順で続く marker 入りの transcript がある。これに対し、marker による解決が（ファイル名の stem, 10:00）を返すことをテストで確かめる
- [ ] AC-3 (FR3): `em-workflow/scripts/recover-orphaned-task.py`、IMPLEMENTATION.md の D2、VERIFICATION.md の TS-14 は、この feature では変更しない
- [ ] AC-4 (NFR1, NFR2): `python3 -m unittest discover -s tests` が失敗 0・エラー 0 で終わる。追加したテストは標準ライブラリだけを使い、実際の `~/.claude` に触れない
- [ ] AC-5: 再現手順で現象が起きない。実際のセッションから D2 form 2 を 1 度読み取り専用で実行し、現セッションの transcript の stem と開始時刻が返り、current-session-unknown にならない

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Assumptions

- A1: 範囲は keep-earliest-add-tests とする。D2 の最小値規則のまま挙動は変えず、回帰テストを 2 件（FR1、FR2）追加する。位置で最初への変更、D2 や TS-14 の意味の変更、関係の無い整理は範囲外
- A2: D2 form 2 の marker 走査（更新時刻が新しい順、marker を含む最初の transcript に確定、古い transcript に戻らない）と、form 1 が優先される規則は変えない
- A3: SC6 の current-session-unknown の意味と、解析できる timestamp が 1 つも無い transcript を未解決として扱う規則は変えない
- A4: em-workflow の version は手で変えない。patch は main への push 時に Actions が上げる

## References

- 要件定義書: `feature-docs/first-entry-timestamp-scan/REQUIREMENTS.md`
- IMPLEMENTATION.md D2
- VERIFICATION.md TS-14
- `em-workflow/scripts/recover-orphaned-task.py`
