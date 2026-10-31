# Feature: unattended-merge-medium-fixes

## Overview

unattended-merge のレビュー 2 回目で残った medium 指摘 5 件を直す。変更は SKILL.md の手順、`merge-preflight.py`、`merge-pr.py`、`merge-ci-wait.py` とそのテストに限られる。あわせて、unattended-merge で走らなかった architecture / spec 観点のレビューを、対象を分割して実施する。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- unattended-merge のレビュー 2 回目で残った medium 指摘 5 件（1eef55acf9af50c3 / 7eab3d538629cc4f / 2d0a436389ac8c32 / 9696fea33b723122 / c442ee13154b13c7）を直す
- unattended-merge で走らなかった architecture / spec 観点のレビューを、対象を分割して実施する

## User Stories

該当なし（受け入れ条件は Success Criteria を参照）

## Technical Requirements

### Functional Requirements
- **FR1:** ローカルマージを head_sha に束縛する。SKILL.md 手順 13.3 で、`git merge --no-ff --no-edit em-workflow/<feature>/integration` の直前に、`refs/heads/em-workflow/<feature>/integration` が head_sha と一致することを確かめる。一致しなければ、マージせず `verification_failed` で終端する。ブランチ名でマージする形（unattended-merge の FR18）は保つ。マージに成功したら、HEAD の第 2 親が head_sha であることを確かめる。一致しない、または読めないときも、結果は `merged` のままにする。detail は 1 行で、固定文の後に、第 2 親が検証した head_sha と異なること（読めないときはその旨）を書き足す。後片付け（手順 15）は通常の merged と同じく行う。SKILL.md の『`detail` の固定文』の規則を、この場合を除外する形に改める。
- **FR2:** HEAD 確認の前に必ず worktree へ cd する。SKILL.md 手順 10 で、`git status --porcelain --untracked-files=no` と `git rev-parse HEAD` による確認の直前に、単独の `cd "<worktree_path>"` を置く。commands の有無は問わない。commands が空でも、この確認を行うと明記する。
- **FR3:** ロック取得後にマージ済みかを判定し直す。SKILL.md 手順 6 で held を得た後、手順 7 の前に、同じ integration の先端でマージ済みかを判定し直す。ローカルルートは `merge-git.py merged`、PR ルートは `merge-pr.py resolve --integration-tip <integration_tip>` を呼ぶ。merged なら、手順 14 で保持タスクを止めてから『マージ済みの経路』へ進み、already_merged で終える。ローカルの not_merged は手順 7 へ進む。PR の open は、再判定の pr_number / pr_url を保持して手順 7 へ進む。stop は、ロックを止めてからその reason で終端する。PR ルートで none が返ったら、ロックを止めて internal_error にする。『マージ済みの経路』の 1 にも、手順 6 の再判定から来た場合を加える。
- **FR4:** 承認の照合で前後の空白を除く。`merge-preflight.py` の `check_approval` は、コマンドを `str.strip()` した値（`bash_guard.py` の `approved_for()` と同じ除去）が承認済みの集合に含まれるかで照合する。出力の `commands[].command` は元の文字列のまま保つ。改行・CR の判定は、これまでどおり生の値で行う。末尾に改行があるコマンドは未承認のまま。内側の空白は、これまでどおり完全一致で比べる。
- **FR5:** リポジトリの比較にホストを含める。`merge-pr.py repo` は、remote 側と gh の既定側の両方から、ホストと owner/name を取り出して比べる。ホストは gh の応答（gh が返すリポジトリの URL）から取る。ホストと owner/name は大文字小文字を区別せずに比べる。どちらかが一致しなければ、`remote_unresolved` で止める（detail に両方の識別子を載せる）。ホストの文字は `[A-Za-z0-9.-]` に限る。ポート付きなど、この形に合わないホストも `remote_unresolved` にする。github の出力 repo は `HOST/OWNER/NAME`。`merge-pr.py`（`resolve` / `state`）と `merge-ci-wait.py` の `--repo` は `HOST/OWNER/NAME` を受け付け、従来の `OWNER/NAME` も引き続き受け付ける。SKILL は、後続のスクリプト呼び出しの `--repo` にホスト付きの値を渡す。`gh pr create` と `gh pr merge` の形は変えない。宛先は gh の既定リポジトリで、この修正によりホストまで一致すると確かめたものになる。SKILL.md 手順 5.1 の『repo（owner/name）』を改める。
- **FR6:** 再発を検出するテスト。FR1〜FR5 のそれぞれに、修正前なら失敗し修正後は通るテストを足す。FR1〜FR3 は、SKILL の手順の順序と形を `tests/test_merge_skill_doc.py` で確かめる。FR4 は `tests/test_merge_preflight.py`、FR5 は `tests/test_merge_pr.py` と `tests/test_merge_ci_wait.py` で確かめる。
- **FR7:** architecture / spec 観点の分割レビュー。この run の review phase では、architecture と spec の観点を、2 つのまとまりについて実行する。1 つは unattended-merge の変更（`feature-docs/unattended-merge/reviews/round2.yaml` の `scope.changed_files`）、もう 1 つはこの feature の差分。対象は reviewer が完了まで走れる大きさに分割する。`review_data_too_large` で skipped になった観点は、完了とみなさない。

### Non-Functional Requirements
- **NFR1:** `plugin.json` と `marketplace.json` の version を変えない。
- **NFR2:** fail-closed を保つ。判定できない場合は stop か internal_error にし、マージ側に倒さない。
- **NFR3:** 新しい状態ファイルを持たず、workflow.yaml にも書き込まない。
- **NFR4:** ガード hook が判定する操作には、検証済みのリテラルだけを載せる。`HOST/OWNER/NAME` も検証してから載せる。
- **NFR5:** `feature-docs/unattended-merge/` 配下の文書（SPEC.md、THREAT-MODEL.md）は変えない。変更は、この feature の文書にだけ記録する。
- **NFR6:** コミットメッセージと feature-docs / test-docs に、Notion の URL とホームディレクトリの絶対パスを書かない。

## Implementation Approach

### Architecture

**変更箇所:**

| 要件 | 対象 | 変更 |
|------|------|------|
| FR1 | SKILL.md 手順 13.3、『`detail` の固定文』の規則 | マージ直前の先端照合、マージ後の第 2 親確認 |
| FR2 | SKILL.md 手順 10 | HEAD 確認の直前に単独の `cd "<worktree_path>"` |
| FR3 | SKILL.md 手順 6、『マージ済みの経路』の 1 | held 取得後のマージ済み再判定 |
| FR4 | `merge-preflight.py` の `check_approval` | `str.strip()` した値で照合 |
| FR5 | `merge-pr.py`（`repo` / `resolve` / `state`）、`merge-ci-wait.py`、SKILL.md 手順 5.1 | ホストを含むリポジトリ比較、`--repo HOST/OWNER/NAME` |
| FR6 | `tests/test_merge_skill_doc.py`、`tests/test_merge_preflight.py`、`tests/test_merge_pr.py`、`tests/test_merge_ci_wait.py` | 再発検出テスト |
| FR7 | この run の review phase | architecture / spec 観点の分割レビュー |

### Data Flow

**FR1（SKILL.md 手順 13.3、ローカルルート）:**
1. `refs/heads/em-workflow/<feature>/integration` が head_sha と一致するか確かめる。一致しなければ、マージせず `verification_failed` で終端する。
2. `git merge --no-ff --no-edit em-workflow/<feature>/integration` を実行する。
3. マージに成功したら、HEAD の第 2 親が head_sha か確かめる。一致しない、または読めないときは、結果を `merged` のまま、detail を 1 行で「固定文 + 第 2 親が検証した head_sha と異なること（読めないときはその旨）」にする。
4. 手順 15 の後片付けを、通常の merged と同じく行う。

**FR3（SKILL.md 手順 6 → 手順 7）:**
1. 手順 6 で held を得る。
2. ローカルルートは `merge-git.py merged`、PR ルートは `merge-pr.py resolve --integration-tip <integration_tip>` で再判定する。
3. 結果ごとの扱い:

| 結果 | ルート | 対応 |
|------|--------|------|
| merged | ローカル / PR | 手順 14 で保持タスクを止めてから『マージ済みの経路』へ進み、already_merged で終える |
| not_merged | ローカル | 手順 7 へ進む |
| open | PR | 再判定の pr_number / pr_url を保持して手順 7 へ進む |
| stop | ローカル / PR | ロックを止めてから、その reason で終端する |
| none | PR | ロックを止めて internal_error にする |

### API Design

#### `merge-pr.py repo`

- remote 側と gh の既定側の両方から、ホストと owner/name を取り出す。gh 側のホストは gh が返すリポジトリの URL から取る。
- ホストと owner/name を大文字小文字を区別せずに比べる。
- 出力:
    - 一致: github と `HOST/OWNER/NAME`
    - 不一致: `remote_unresolved`（detail に両方の識別子を載せる）
    - ホストが `[A-Za-z0-9.-]` の形に合わない（ポート付きなど）: `remote_unresolved`

#### `merge-pr.py resolve` / `merge-pr.py state` / `merge-ci-wait.py` の `--repo`

- `HOST/OWNER/NAME` と `OWNER/NAME` を受け付ける。
- 受け付けた値を gh にそのまま渡す。
- 不正な形は使い方エラーにする。

#### `merge-preflight.py` の `check_approval`

- 照合: コマンドを `str.strip()` した値が承認済みの集合に含まれるか。
- 出力の `commands[].command`: 元の文字列のまま。
- 改行・CR の判定: 生の値で行う。
- 内側の空白: 完全一致で比べる。

### Database Schema

該当なし（新しい状態ファイルを持たない。NFR3）

### Dependencies

**Internal Dependencies:**
- `bash_guard.py` の `approved_for()`: FR4 の空白除去はこれと同じ除去にする。`bash_guard.py` は変えない（as-6）。
- `merge-result.py`: merged の任意の detail をすでに受け付ける（`merge-result.py:267`）。変えない（as-7）。
- unattended-merge の FR18: ブランチ名でマージする形を保つ（FR1）。

**External Dependencies:**
- gh: 既定リポジトリの URL（ホスト）と owner/name の取得、`--repo` を渡す先。`gh pr create` と `gh pr merge` の形は変えない。

### File Structure

変更するファイルのパスは create-plan で `workflow.yaml` の各タスクの `files` から導出する。変えないファイル:

- `plugin.json`、`marketplace.json` の version（NFR1）
- `bash_guard.py`、`merge-lock.py`、`merge_pr_allow.py`、`destructive-guard-cases.json`（as-6）
- `merge-result.py`（as-7）
- `feature-docs/unattended-merge/` 配下の文書（NFR5）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/unattended-merge-medium-fixes/**`
- `test-docs/unattended-merge-medium-fixes/**`

`feature-docs/unattended-merge-medium-fixes/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/unattended-merge-medium-fixes/**` covers `test-docs/unattended-merge-medium-fixes/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/unattended-merge-medium-fixes/` directory at all; the declared
`test-docs/unattended-merge-medium-fixes/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1（FR1）: SKILL.md 13.3 で、git merge のブロックの前に、integration ブランチの先端を head_sha と照合する手順と、一致しないときの verification_failed がある。git merge の後に、第 2 親の確認と、不一致のとき merged に detail を足す記述がある（文書テスト）
- [ ] TS2（FR2）: SKILL.md 10 で、git status / git rev-parse HEAD のブロックの直前のブロックが `cd "<worktree_path>"` であり、commands が空でも確認することが書かれている（文書テスト）
- [ ] TS3（FR3）: SKILL.md 6 で、`held` の後、手順 7 の worktree-state より前に、`merge-git.py merged` と `merge-pr.py resolve` の再判定がある。merged のときロックを止めて『マージ済みの経路』へ進む（文書テスト）
- [ ] TS4（FR4）: 末尾に空白を持つ test_command と、strip した承認エントリで proceed になる。出力の command は元の文字列。`'make a\n'` と内側の空白の違いは commands_unapproved
- [ ] TS5（FR4）: 前後に空白を持つコマンドで、`bash_guard.py --list` の承認判定と preflight の判定が一致する
- [ ] TS6（FR5）: gh スタブで、remote の解決が ghe.example/acme/service、既定先が github.com/acme/service のとき remote_unresolved（再現手順のケース）
- [ ] TS7（FR5）: ホストと owner/name が一致するとき（大文字小文字の違いを含む）github と `HOST/OWNER/NAME`。ホストの形が不正なときは remote_unresolved
- [ ] TS8（FR5）: `merge-pr.py resolve` / `state` と `merge-ci-wait.py` が `--repo HOST/OWNER/NAME` を受け付け、gh にそのまま渡す。不正な形は使い方エラー

### Integration Tests
- [ ] `python3 -m unittest discover -s tests` が通る（AC6）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] マージ後の第 2 親が読めない: `merged` のまま、detail に読めないことを載せる（FR1）
- [ ] commands が空: 手順 10 の HEAD 確認を行う（FR2）
- [ ] 再判定で PR ルートが none を返す: ロックを止めて internal_error（FR3）
- [ ] 末尾に改行があるコマンド: 未承認のまま（FR4）
- [ ] 内側の空白が違うコマンド: 未承認のまま（FR4）
- [ ] ポート付きなど形の合わないホスト: `remote_unresolved`（FR5）
- [ ] `--repo` に従来の `OWNER/NAME`: 引き続き受け付ける（FR5）

### Performance Tests

該当なし

## Security Considerations

- **Input Validation:** ホストの文字は `[A-Za-z0-9.-]` に限る（FR5）。`--repo` の不正な形は使い方エラーにする（TS8）。改行・CR の判定は生の値で行う（FR4）。
- **Guard hook:** ガード hook が判定する操作には、検証済みのリテラルだけを載せる。`HOST/OWNER/NAME` も検証してから載せる（NFR4）。
- **Fail-closed:** 判定できない場合は stop か internal_error にし、マージ側に倒さない（NFR2）。
- **Data Protection:** コミットメッセージと feature-docs / test-docs に、Notion の URL とホームディレクトリの絶対パスを書かない（NFR6）。

## Error Handling

### Error Codes

| 結果 | 条件 | 要件 |
|------|------|------|
| `verification_failed` | マージ直前の integration ブランチの先端が head_sha と異なる | FR1 |
| `remote_unresolved` | remote 側と gh の既定側で、ホストまたは owner/name が一致しない。ホストの形が不正 | FR5 |
| `commands_unapproved` | strip した値が承認済みの集合に無い。末尾に改行がある。内側の空白が違う | FR4 |
| `internal_error` | ロック取得後の再判定で、PR ルートが none を返す | FR3 |
| stop の reason | ロック取得後の再判定が stop を返す（ロックを止めてから終端する） | FR3 |
| 使い方エラー | `--repo` が不正な形 | FR5 |

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1: ローカルルートで、検証後に integration ブランチの先端が head_sha と異なる場合、マージせず verification_failed で終わる。マージ後に第 2 親が head_sha と異なる場合は merged のままで、detail にその旨が載る。どちらも SKILL の手順とテストで確かめられる
- [ ] AC2: 手順 10 の HEAD 確認の直前に、単独の `cd "<worktree_path>"` がある。commands が空でもこの確認を行うと明記されている
- [ ] AC3: 手順 6 で held を得た後、手順 7 の前に、ローカルでは merged、PR では resolve の再判定がある。マージ済みなら、ロックを止めて『マージ済みの経路』へ進む
- [ ] AC4: test_command が `'make test '`、承認ストアが `'make test'` のとき、preflight は proceed になり、出力の command は `'make test '` のまま。`'make a\n'` は commands_unapproved のまま
- [ ] AC5: remote が `https://ghe.example/acme/service.git`、gh の既定先が github.com の acme/service のとき、`merge-pr.py repo` は remote_unresolved を返す。ホストと owner/name が一致すれば、github と `HOST/OWNER/NAME` を返す
- [ ] AC6: `python3 -m unittest discover -s tests` が通る
- [ ] AC7: architecture / spec 観点のレビューが、unattended-merge の変更とこの feature の差分について、分割した対象ごとに完了している。review_data_too_large による skipped が残らない

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし（`status: tbd` の要件は無い）

## Assumptions

| ID | 前提 |
|----|------|
| as-1 | SPEC FR18 のブランチ名でマージする形は保つ。マージ直前の先端が一致しないときは verification_failed にする |
| as-2 | ホストは gh の応答（リポジトリの URL）から取る。大文字小文字は区別しない。ポート付きなど形の合わないホストは remote_unresolved |
| as-3 | `--repo` は OWNER/NAME も引き続き受け付ける |
| as-4 | ロック取得後の再判定で、merged / merged 以外の各結果をどう扱うかは FR3 のとおり |
| as-5 | SKILL の手順の修正（FR1〜FR3）の再発検出は、文書構造テストで行う |
| as-6 | version、`bash_guard.py`、`merge-lock.py`、`merge_pr_allow.py`、`destructive-guard-cases.json` は変えない |
| as-7 | `merge-result.py` は、merged の任意の detail をすでに受け付ける（`merge-result.py:267`）ので変えない |

## Implementation Phases (if applicable)

該当なし

## References

- `feature-docs/unattended-merge-medium-fixes/REQUIREMENTS.md`: 要件定義書
- `feature-docs/unattended-merge/reviews/round2.yaml`: unattended-merge のレビュー 2 回目
- `feature-docs/unattended-merge/SPEC.md`: unattended-merge の SPEC（FR18）
