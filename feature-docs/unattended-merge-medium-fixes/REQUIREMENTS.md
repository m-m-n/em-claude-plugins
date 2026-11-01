---
title: "unattended-merge-medium-fixes"
created_date: 2026-11-01
status: draft
---

# unattended-merge-medium-fixes - 要件定義書

## 1. 概要

### 1.1 背景
unattended-merge のレビュー 2 回目（`feature-docs/unattended-merge/reviews/round2.yaml`）で、medium の指摘 5 件が残った。また、unattended-merge では architecture / spec 観点のレビューが走らなかった。

### 1.2 目的
- unattended-merge のレビュー 2 回目で残った medium 指摘 5 件（1eef55acf9af50c3 / 7eab3d538629cc4f / 2d0a436389ac8c32 / 9696fea33b723122 / c442ee13154b13c7）を直す。
- unattended-merge で走らなかった architecture / spec 観点のレビューを、対象を分割して実施する。

### 1.3 スコープ

対象:
- SKILL.md の手順 5.1・6・10・13.3、『マージ済みの経路』、『`detail` の固定文』の規則（FR1〜FR3、FR5）
- `merge-preflight.py` の `check_approval`（FR4）
- `merge-pr.py`（`repo` / `resolve` / `state`）と `merge-ci-wait.py` の `--repo`（FR5）
- `tests/test_merge_skill_doc.py`、`tests/test_merge_preflight.py`、`tests/test_merge_pr.py`、`tests/test_merge_ci_wait.py`（FR6）
- この run の review phase での architecture / spec 観点の分割レビュー（FR7）

対象外:
- `plugin.json` と `marketplace.json` の version
- `bash_guard.py`、`merge-lock.py`、`merge_pr_allow.py`、`destructive-guard-cases.json`
- `merge-result.py`
- `feature-docs/unattended-merge/` 配下の文書（SPEC.md、THREAT-MODEL.md）
- `gh pr create` と `gh pr merge` の形

## 2. ビジネス要件

### 2.1 ビジネス目標
- unattended-merge のレビュー 2 回目で残った medium 指摘 5 件を直す。
- unattended-merge で走らなかった architecture / spec 観点のレビューを、対象を分割して実施する。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
該当なし

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | ローカルマージを head_sha に束縛する | resolved |
| FR2 | HEAD 確認の前に必ず worktree へ cd する | resolved |
| FR3 | ロック取得後にマージ済みかを判定し直す | resolved |
| FR4 | 承認の照合で前後の空白を除く | resolved |
| FR5 | リポジトリの比較にホストを含める | resolved |
| FR6 | 再発を検出するテスト | resolved |
| FR7 | architecture / spec 観点の分割レビュー | resolved |

### 4.2 機能詳細

#### FR1: ローカルマージを head_sha に束縛する

**説明**:
- SKILL.md 手順 13.3 で、`git merge --no-ff --no-edit em-workflow/<feature>/integration` の直前に、`refs/heads/em-workflow/<feature>/integration` が head_sha と一致することを確かめる。
- 一致しなければ、マージせず `verification_failed` で終端する。
- ブランチ名でマージする形（unattended-merge の FR18）は保つ。
- マージに成功したら、HEAD の第 2 親が head_sha であることを確かめる。
- 第 2 親が一致しない、または読めないときも、結果は `merged` のままにする。detail は 1 行で、固定文の後に、第 2 親が検証した head_sha と異なること（読めないときはその旨）を書き足す。
- 後片付け（手順 15）は通常の merged と同じく行う。
- SKILL.md の『`detail` の固定文』の規則を、この場合を除外する形に改める。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 先端の不一致 | マージ直前の `refs/heads/em-workflow/<feature>/integration` が head_sha と異なる | マージせず `verification_failed` で終端する |
| 第 2 親の不一致 | マージ後の HEAD の第 2 親が head_sha と異なる | `merged` のまま、detail に固定文と、第 2 親が head_sha と異なることを 1 行で載せる。手順 15 を行う |
| 第 2 親が読めない | マージ後の HEAD の第 2 親が読めない | `merged` のまま、detail に固定文と、読めないことを 1 行で載せる。手順 15 を行う |

#### FR2: HEAD 確認の前に必ず worktree へ cd する

**説明**:
- SKILL.md 手順 10 で、`git status --porcelain --untracked-files=no` と `git rev-parse HEAD` による確認の直前に、単独の `cd "<worktree_path>"` を置く。
- commands の有無は問わない。
- commands が空でも、この確認を行うと明記する。

#### FR3: ロック取得後にマージ済みかを判定し直す

**説明**:
- SKILL.md 手順 6 で held を得た後、手順 7 の前に、同じ integration の先端でマージ済みかを判定し直す。
- ローカルルートは `merge-git.py merged`、PR ルートは `merge-pr.py resolve --integration-tip <integration_tip>` を呼ぶ。
- 『マージ済みの経路』の 1 にも、手順 6 の再判定から来た場合を加える。

**再判定の結果ごとの扱い**:
| 結果 | ルート | 対応 |
|------|--------|------|
| merged | ローカル / PR | 手順 14 で保持タスクを止めてから『マージ済みの経路』へ進み、already_merged で終える |
| not_merged | ローカル | 手順 7 へ進む |
| open | PR | 再判定の pr_number / pr_url を保持して手順 7 へ進む |
| stop | ローカル / PR | ロックを止めてから、その reason で終端する |
| none | PR | ロックを止めて internal_error にする |

#### FR4: 承認の照合で前後の空白を除く

**説明**:
- `merge-preflight.py` の `check_approval` は、コマンドを `str.strip()` した値（`bash_guard.py` の `approved_for()` と同じ除去）が承認済みの集合に含まれるかで照合する。
- 出力の `commands[].command` は元の文字列のまま保つ。
- 改行・CR の判定は、これまでどおり生の値で行う。末尾に改行があるコマンドは未承認のまま。
- 内側の空白は、これまでどおり完全一致で比べる。

**バリデーション**:
| 項目 | ルール | 結果 |
|------|--------|------|
| 前後の空白 | `str.strip()` した値で承認済みの集合と照合する | 含まれれば承認済み |
| 改行・CR | 生の値で判定する | 末尾に改行があれば未承認 |
| 内側の空白 | 完全一致で比べる | 違えば未承認 |

#### FR5: リポジトリの比較にホストを含める

**説明**:
- `merge-pr.py repo` は、remote 側と gh の既定側の両方から、ホストと owner/name を取り出して比べる。
- ホストは gh の応答（gh が返すリポジトリの URL）から取る。
- ホストと owner/name は大文字小文字を区別せずに比べる。
- github の出力 repo は `HOST/OWNER/NAME`。
- `merge-pr.py`（`resolve` / `state`）と `merge-ci-wait.py` の `--repo` は `HOST/OWNER/NAME` を受け付け、従来の `OWNER/NAME` も引き続き受け付ける。
- SKILL は、後続のスクリプト呼び出しの `--repo` にホスト付きの値を渡す。
- `gh pr create` と `gh pr merge` の形は変えない。宛先は gh の既定リポジトリで、この修正によりホストまで一致すると確かめたものになる。
- SKILL.md 手順 5.1 の『repo（owner/name）』を改める。

**バリデーション**:
| 項目 | ルール | 結果 |
|------|--------|------|
| ホストの文字 | `[A-Za-z0-9.-]` に限る | ポート付きなど、この形に合わないホストは `remote_unresolved` |
| ホストと owner/name の一致 | 大文字小文字を区別せずに比べる | どちらかが一致しなければ `remote_unresolved` |

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `remote_unresolved` | remote 側と gh の既定側で、ホストまたは owner/name が一致しない | 止める。detail に両方の識別子を載せる |
| `remote_unresolved` | ホストが `[A-Za-z0-9.-]` の形に合わない | 止める |

#### FR6: 再発を検出するテスト

**説明**:
- FR1〜FR5 のそれぞれに、修正前なら失敗し修正後は通るテストを足す。
- FR1〜FR3 は、SKILL の手順の順序と形を `tests/test_merge_skill_doc.py` で確かめる。
- FR4 は `tests/test_merge_preflight.py` で確かめる。
- FR5 は `tests/test_merge_pr.py` と `tests/test_merge_ci_wait.py` で確かめる。

#### FR7: architecture / spec 観点の分割レビュー

**説明**:
- この run の review phase では、architecture と spec の観点を、2 つのまとまりについて実行する。
    - unattended-merge の変更（`feature-docs/unattended-merge/reviews/round2.yaml` の `scope.changed_files`）
    - この feature の差分
- 対象は reviewer が完了まで走れる大きさに分割する。
- `review_data_too_large` で skipped になった観点は、完了とみなさない。

## 5. 非機能要件

### 5.1 非機能要件一覧
| ID | 要件 |
|----|------|
| NFR1 | `plugin.json` と `marketplace.json` の version を変えない |
| NFR2 | fail-closed を保つ。判定できない場合は stop か internal_error にし、マージ側に倒さない |
| NFR3 | 新しい状態ファイルを持たず、workflow.yaml にも書き込まない |
| NFR4 | ガード hook が判定する操作には、検証済みのリテラルだけを載せる。`HOST/OWNER/NAME` も検証してから載せる |
| NFR5 | `feature-docs/unattended-merge/` 配下の文書（SPEC.md、THREAT-MODEL.md）は変えない。変更は、この feature の文書にだけ記録する |
| NFR6 | コミットメッセージと feature-docs / test-docs に、Notion の URL とホームディレクトリの絶対パスを書かない |

## 6. UI/UX要件

該当なし（UI の変更が無い。変更はスクリプト・SKILL の手順・テストに限られる）

## 7. データ要件

新しい状態ファイルを持たず、workflow.yaml にも書き込まない（NFR3）。

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| gh | `merge-pr.py` / `merge-ci-wait.py` からの呼び出し | 既定リポジトリの URL（ホスト）と owner/name、`--repo` の値 |

### 8.2 API仕様要件
- `gh pr create` と `gh pr merge` の形は変えない（FR5）。
- `merge-pr.py`（`resolve` / `state`）と `merge-ci-wait.py` は、`--repo HOST/OWNER/NAME` を gh にそのまま渡す（TS8）。

## 9. 制約条件

### 9.1 技術的制約
- ブランチ名でマージする形（unattended-merge の FR18）は保つ（FR1）。
- NFR1〜NFR6 を守る。
- `bash_guard.py`、`merge-lock.py`、`merge_pr_allow.py`、`destructive-guard-cases.json`、`merge-result.py` は変えない（as-6、as-7）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/unattended-merge-medium-fixes/**`
- `test-docs/unattended-merge-medium-fixes/**`

`feature-docs/unattended-merge-medium-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/unattended-merge-medium-fixes/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/unattended-merge-medium-fixes/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/unattended-merge-medium-fixes/` ディレクトリを生成しないが、宣言された `test-docs/unattended-merge-medium-fixes/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: ローカルルートで、検証後に integration ブランチの先端が head_sha と異なる場合、マージせず verification_failed で終わる。マージ後に第 2 親が head_sha と異なる場合は merged のままで、detail にその旨が載る。どちらも SKILL の手順とテストで確かめられる
- [ ] AC2: 手順 10 の HEAD 確認の直前に、単独の `cd "<worktree_path>"` がある。commands が空でもこの確認を行うと明記されている
- [ ] AC3: 手順 6 で held を得た後、手順 7 の前に、ローカルでは merged、PR では resolve の再判定がある。マージ済みなら、ロックを止めて『マージ済みの経路』へ進む
- [ ] AC4: test_command が `'make test '`、承認ストアが `'make test'` のとき、preflight は proceed になり、出力の command は `'make test '` のまま。`'make a\n'` は commands_unapproved のまま
- [ ] AC5: remote が `https://ghe.example/acme/service.git`、gh の既定先が github.com の acme/service のとき、`merge-pr.py repo` は remote_unresolved を返す。ホストと owner/name が一致すれば、github と `HOST/OWNER/NAME` を返す
- [ ] AC6: `python3 -m unittest discover -s tests` が通る
- [ ] AC7: architecture / spec 観点のレビューが、unattended-merge の変更とこの feature の差分について、分割した対象ごとに完了している。review_data_too_large による skipped が残らない

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（FR1）: SKILL.md 13.3 で、git merge のブロックの前に、integration ブランチの先端を head_sha と照合する手順と、一致しないときの verification_failed がある。git merge の後に、第 2 親の確認と、不一致のとき merged に detail を足す記述がある（文書テスト）
- [ ] TS2（FR2）: SKILL.md 10 で、git status / git rev-parse HEAD のブロックの直前のブロックが `cd "<worktree_path>"` であり、commands が空でも確認することが書かれている（文書テスト）
- [ ] TS3（FR3）: SKILL.md 6 で、`held` の後、手順 7 の worktree-state より前に、`merge-git.py merged` と `merge-pr.py resolve` の再判定がある。merged のときロックを止めて『マージ済みの経路』へ進む（文書テスト）
- [ ] TS4（FR4）: 末尾に空白を持つ test_command と、strip した承認エントリで proceed になる。出力の command は元の文字列。`'make a\n'` と内側の空白の違いは commands_unapproved
- [ ] TS5（FR4）: 前後に空白を持つコマンドで、`bash_guard.py --list` の承認判定と preflight の判定が一致する
- [ ] TS6（FR5）: gh スタブで、remote の解決が ghe.example/acme/service、既定先が github.com/acme/service のとき remote_unresolved（再現手順のケース）
- [ ] TS7（FR5）: ホストと owner/name が一致するとき（大文字小文字の違いを含む）github と `HOST/OWNER/NAME`。ホストの形が不正なときは remote_unresolved
- [ ] TS8（FR5）: `merge-pr.py resolve` / `state` と `merge-ci-wait.py` が `--repo HOST/OWNER/NAME` を受け付け、gh にそのまま渡す。不正な形は使い方エラー

## 13. 用語定義

該当なし

## 14. 確認事項

### 14.1 確認済み事項
- [x] Q1: script_reads_only（as-6）
- [x] Q2: merged_with_detail（as-7）

### 14.2 未確認・保留事項
なし

### 14.3 前提
| ID | 前提 | 根拠 | 影響度 | 可逆 |
|----|------|------|--------|------|
| as-1 | SPEC FR18 のブランチ名でマージする形は保つ。マージ直前の先端が一致しないときは verification_failed にする | 期待する挙動 1 と round2 1eef55acf9af50c3 の suggestion | low | 可 |
| as-2 | ホストは gh の応答（リポジトリの URL）から取る。大文字小文字は区別しない。ポート付きなど形の合わないホストは remote_unresolved | ssh.github.com や ssh config の別名による、誤った停止を避ける | medium | 可 |
| as-3 | `--repo` は OWNER/NAME も引き続き受け付ける | 既存の呼び出しとテストを壊さない | low | 可 |
| as-4 | ロック取得後の再判定で、merged / merged 以外の各結果をどう扱うかは FR3 のとおり | 期待する挙動 3 が決めているのは merged のときだけ | low | 可 |
| as-5 | SKILL の手順の修正（FR1〜FR3）の再発検出は、文書構造テストで行う | SKILL の手順は散文で、モデルが実行する | low | 可 |
| as-6 | version、`bash_guard.py`、`merge-lock.py`、`merge_pr_allow.py`、`destructive-guard-cases.json` は変えない | プロジェクトのルールと、Q1 の回答（script_reads_only） | low | 可 |
| as-7 | `merge-result.py` は、merged の任意の detail をすでに受け付ける（`merge-result.py:267`）ので変えない | Q2 の回答（merged_with_detail） | low | 可 |

## 15. 参考資料

- `feature-docs/unattended-merge/reviews/round2.yaml`: unattended-merge のレビュー 2 回目
- `feature-docs/unattended-merge/SPEC.md`: unattended-merge の SPEC（FR18）
