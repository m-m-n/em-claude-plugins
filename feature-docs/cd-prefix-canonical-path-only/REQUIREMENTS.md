---
title: "cd-prefix-canonical-path-only"
created_date: 2026-10-31
status: draft
---

# cd-prefix-canonical-path-only - 要件定義書

## 1. 概要

### 1.1 背景
bash_guard.py の cd 前置形のパス判定は、Bash のパス解決を再現している。段階検査（`_stage_walk_refuses`）、物理パスへのフォールバック、`/proc`・`/dev/fd` の特別扱いを持ち、段階検査の続行は要素数の二乗で遅くなる。

### 1.2 目的
- bash_guard.py の cd 前置形のパス判定を、正規の絶対パスだけを許可する単純な判定に置き換え、Bash のパス解決の再現をやめる。
- 段階検査（`_stage_walk_refuses`）、物理パスへのフォールバック、`/proc`・`/dev/fd` の特別扱いを取り除く。
- 段階検査の続行が要素数の二乗で遅くなる問題を、長さ上限と単純な判定で吸収する。

### 1.3 スコープ
- bash_guard.py の cd 前置形のパス判定（FR1〜FR6）
- command-execution-protocol.md、bash_guard.py の docstring、implementer の手順書（agents/implementer.md、skills/worktree-task-workflow/SKILL.md）の記述（FR7）
- implement-phase.md の worktree_path の生成（FR8）
- テストと過去 feature のテスト記録（FR9、FR10）

対象外:
- feature-docs/ の過去 5 feature の SPEC.md（as-9）
- design ステップ（as-8）

## 2. ビジネス要件

### 2.1 ビジネス目標
- cd 前置形のパス判定を、正規の絶対パスだけを許可する単純な判定に置き換える。
- 段階検査、物理パスへのフォールバック、`/proc`・`/dev/fd` の特別扱いを取り除く。
- 要素数の二乗で遅くなる問題を、長さ上限と単純な判定で吸収する。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 1.2 の目的と同じ

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | 正規の絶対パスだけを許可 | 4 条件をすべて満たすパスだけがパスの条件を満たす | confirmed |
| FR2 | 長さ上限 | `os.pathconf('/', 'PC_PATH_MAX')` 以上のバイト長は走査前に不許可 | confirmed |
| FR3 | 構文・除外規則・判定表・例外の扱いは不変 | 既存の構文、除外規則、判定表、例外の扱いを変えない | confirmed |
| FR4 | 旧判定の削除 | 段階検査ほかの旧判定を削除する | confirmed |
| FR5 | 許可領域がリンクを含む場合 | 解決した許可領域が main worktree の realpath の厳密に下にあるときだけ使う | confirmed |
| FR6 | 許可範囲 | 許可領域の厳密に下の既存ディレクトリ全体、深さは問わない | confirmed |
| FR7 | 文書を新しい判定に合わせる | protocol、docstring、implementer の手順書を書き換える | confirmed |
| FR8 | 生成側で worktree_path を正規化 | implement-phase.md で realpath（strict）により正規化して渡す | confirmed |
| FR9 | テスト | 新しい判定のテストを追加し、旧判定のテストを整理する | confirmed |
| FR10 | 過去 feature のテスト記録 | 削除したテスト ID を過去 feature の tests.yaml から外す | confirmed |

### 4.2 機能詳細

#### FR1: 正規の絶対パスだけを許可

**説明**: cd 前置形のパスは、次をすべて満たすときだけパスの条件を満たす。

- (a) 絶対パスで、ルート以外に空要素・`.`・`..` を含まない。正規化してから受け入れることはしない。
- (b) 字句的に `strictly_below(path, area)` を満たす。
- (c) `os.path.realpath(path, strict=True) == path`。
- (d) `os.path.isdir(path)`。

#### FR2: 長さ上限

**説明**:
- 上限は実行時に `os.pathconf('/', 'PC_PATH_MAX')` で得る。
- `len(os.fsencode(path))` が上限以上なら不許可にする。
- この判定は、ファイルシステムを走査する前、`worktree_area()` を呼ぶ前に行う。
- 上限を取得できないとき、または値が正でないときも不許可にする。
- `PC_PATH_MAX` はディレクトリからの相対パスに対する上限だが、ここでは絶対パス全体に対する控えめな受け入れ上限として使う。

#### FR3: 構文・除外規則・判定表・例外の扱いは不変

**説明**:
- 次は変えない。
    - `CD_PREFIX_RE` による構文の制限
    - `cd_remainder_excluded` の除外規則（E1〜E10）
    - 拒否パターンをコマンド全体に先に適用する順序
    - hook の判定表
    - 例外（`OSError`、`ValueError`）を不許可にする動作
- パスの条件を満たさない cd 前置形は、cd 前置がないものとして判定し、新たな deny は出さない。

#### FR4: 旧判定の削除

**説明**: 次を削除する。
- `_stage_walk_refuses`
- `_under_proc_or_dev_fd`
- `FOLLOWED_LINK_LIMIT`
- `resolves_to_directory`
- 論理パスと物理パスの二重判定（normpath 後と書かれたままの realpath の比較）

#### FR5: 許可領域がリンクを含む場合

**説明**: `worktree_area()` が解決した許可領域は、main worktree（git common dir の親）の realpath の厳密に下にあるときだけ使う。そうでなければ cd 前置形を許可しない。この扱いを SPEC に書く。

#### FR6: 許可範囲

**説明**: 許可する範囲は、許可領域の厳密に下にある既存ディレクトリ全体とする。深さは問わない（従来と同じ）。この範囲を SPEC に書く。

#### FR7: 文書を新しい判定に合わせる

**説明**:
- 次を FR1、FR2、FR5、FR6 の条件に書き換える。
    - command-execution-protocol.md の Verbatim execution rule の path の項目
    - bash_guard.py のモジュール docstring の path の項目
    - `is_below` の docstring
- 論理パス、物理パス、`/proc`、`/dev/fd`、段階検査の記述は取り除く。
- implementer の手順書（agents/implementer.md、skills/worktree-task-workflow/SKILL.md）には、cd 先は渡された worktree_path をそのまま使い、それが正規の絶対パスであることを前提とする旨を書く。

#### FR8: 生成側で worktree_path を正規化

**説明**:
- WT_ROOT は文字列をつないで作っているだけなので、正規の形になる保証がない。
- implement-phase.md では、`git worktree add` で作った `$WT_ROOT/{T}` を生成側で realpath（strict）により正規化し、その値を worktree_path として渡す。
- tests_yaml_path は、worktree_path の下にあるという前提を保つため、正規化した worktree_path から導出する。

#### FR9: テスト

**説明**:
- 末尾の `/`、重複した `/`、`.`、`..`、リンクを含むパスを不許可とするテストを追加する。
- 長いパス（例: `'/dev/null' + '/x' * 32000`、および許可領域の下の長いパス）で判定がすぐに返ることを確かめるテストを追加する。
- 許可領域が main worktree の外へ解決される場合に不許可となるテストを追加する。
- 取り除いた判定のテストを整理し、残ったテストがすべて通るようにする。

#### FR10: 過去 feature のテスト記録

**説明**:
- 削除したテスト ID を、過去 feature の `test-docs/**/*.tests.yaml` から外す。
- 残るテストへ付け替えられるものは付け替える。
- `tests/test_tests_yaml_id_resolution.py` が通る状態にする。

## 5. 非機能要件

| ID | 要件名 | 内容 |
|----|--------|------|
| NFR1 | 標準ライブラリだけ | hook とテストは標準ライブラリだけを import する（既存の `TestAc7StandardLibraryOnly` を維持する）。 |
| NFR2 | 子プロセスを起動しない | パスの判定で子プロセスを起動しない。パスを子プロセスの作業ディレクトリや引数に使わない。 |
| NFR3 | hook の出力の規律 | どの入力でも hook は終了コード 0 で終わり、stderr に何も書かない。 |
| NFR4 | 判定時間 | 上限を超えるパスは走査せずに返す。上限以下のパスでも、判定時間がパスの要素数の二乗で伸びない。 |
| NFR5 | フェイルクローズ | 判断できないときは不許可にする。不許可は新たな deny ではなく、判定表のほかの行に回る。 |

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- `is_below(path, area)` の名前と引数、および呼び出し元 `is_cd_prefixed_approved` / `cd_prefix_allowed` / `hook_main` の判定表は変えない。ただし FR2 のため、長さの検査を `worktree_area()` の呼び出しより前に置く（as-1）。
- 例外を不許可にする範囲は、現状と同じ `OSError` と `ValueError` とする（as-3）。
- implementer に実行時の worktree_path の検査は追加しない（as-2）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/cd-prefix-canonical-path-only/**`
- `test-docs/cd-prefix-canonical-path-only/**`

`feature-docs/cd-prefix-canonical-path-only/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/cd-prefix-canonical-path-only/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/cd-prefix-canonical-path-only/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1）: FR1 の 4 条件をすべて満たすパスだけを許可する
- [ ] AC2（FR2）: `os.fsencode` でのバイト長が `os.pathconf('/', 'PC_PATH_MAX')` 以上のパスは、走査の前、`worktree_area()` の前に不許可になる。上限の取得に失敗したとき、または値が正でないときも不許可になる
- [ ] AC3（FR3）: 構文の制限、除外規則、拒否パターンの適用順、判定表、例外を不許可にする動作が変わっていない（既存の operators テスト、構文テスト、SILENT のパスのケースが通る）
- [ ] AC4（FR4）: `_stage_walk_refuses`、`_under_proc_or_dev_fd`、`FOLLOWED_LINK_LIMIT`、`resolves_to_directory`、論理パスと物理パスの判定がコードから消えている
- [ ] AC5（FR5）: 解決した許可領域が main worktree の realpath の厳密に下にないときは許可しない。この扱いが SPEC に書かれている
- [ ] AC6（FR6）: 許可領域の下の任意の深さの正規の既存ディレクトリを許可する。この範囲が SPEC に書かれている
- [ ] AC7（FR7）: protocol、hook のモジュール docstring、`is_below` の docstring、implementer の手順書が新しい判定と一致し、旧判定の記述が残っていない
- [ ] AC8（FR8）: implement-phase.md が、realpath（strict）で正規化した `$WT_ROOT/{T}` を worktree_path として渡し、tests_yaml_path をそこから導出している
- [ ] AC9（FR9）: 末尾 `/`、`//`、`.`、`..`、リンクを含むパスを不許可とするテストと、長いパスで判定がすぐに返ることを確かめるテストがある
- [ ] AC10（FR9、FR10）: `python3 -m unittest discover -s tests` がすべて通る（`tests/test_tests_yaml_id_resolution.py` を含む）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1、AC6）: `<area>/task0001`、`<area>/task0001/sub/deeper`、空白や `&&` を含む名前の正規ディレクトリ、許可領域の下の git worktree が allow になる（main worktree から実行した場合と git worktree から実行した場合）
- [ ] TS2（AC1、AC9）: `<in>/`、`<area>//task0001`、`//<in の残り>`、`<in>/.`、`<area>/./task0001`、`<in>/..`、`<in>/sub/../sub` が silent になる
- [ ] TS3（AC1、AC9）: 許可領域内のディレクトリを指す許可領域内のリンク、許可領域の外へのリンク、リンク切れ、ファイルへのリンク、以前の `FALLBACK_ALLOW_CASES` と相対リンクのケースが silent になる
- [ ] TS4（AC1）: `/`、許可領域そのもの、名前の先頭が同じ兄弟ディレクトリ、別リポジトリの許可領域、存在しないパス、通常ファイル、`/proc` と `/dev/fd` の各形が silent のまま
- [ ] TS5（AC2、AC9）: `'/dev/null' + '/x' * 32000` と `'<area>' + '/x' * 32000` で、パスの判定がすぐに False を返す。上限以上の長さでは `worktree_area()` もファイルシステムの検査も呼ばれない（mock で確かめる）
- [ ] TS6（AC2）: `os.pathconf` が `OSError` を出す場合や 0 以下を返す場合に False になる。上限ちょうどの長さは不許可、上限より 1 バイト短い長さは長さの検査を通る
- [ ] TS7（AC5）: main worktree の `.claude/worktrees/em-workflow`（またはその祖先）が main worktree の外へのリンクであるとき、その先の正規のディレクトリは silent になる。main worktree の中へのリンクの場合は、解決後の正規のパスで allow になる
- [ ] TS8（AC3）: NUL を含むパスと解決エラーで False になり、hook は終了コード 0、stderr は空。拒否パターンを含む cd 前置形は deny のまま。除外規則（演算子と安全側の構文）の既存テストが通る
- [ ] TS9（AC4、AC7）: 削除したシンボルがモジュールに存在しないこと、docstring と protocol の path の項目に新しい条件があり、旧条件（logical / physical / /proc / /dev/fd / stage）がないことを文書テストで確かめる。`cd prefix:` 段落の既存の文言検査と、`realpath` を含むことの検査が通る
- [ ] TS10（AC8）: implement-phase.md の起動手順に、realpath（strict）で `$WT_ROOT/{T}` を正規化して worktree_path にすること、tests_yaml_path をそこから導出することが書かれていることを文書テストで確かめる
- [ ] TS11（AC10）: 過去 feature の `*.tests.yaml` から削除した ID を外した後、`python3 -m unittest discover -s tests` が全件通る

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 許可領域（area） | `worktree_area()` が解決するディレクトリ |
| main worktree | git common dir の親 |
| 正規の絶対パス | FR1 の (a)〜(d) をすべて満たすパス |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 許可領域にリンクがある場合（requirement.area-symlink）: `worktree_area()` の解決先が main worktree の realpath の厳密に下にあるときだけ使う。そうでなければ cd 前置形を許可しない（as-4）
- [x] 許可範囲（requirement.allowed-scope）: 許可領域の厳密に下の既存ディレクトリ全体とし、深さは問わない（as-5）
- [x] 長さ上限（requirement.path-length-bound）: `os.pathconf('/', 'PC_PATH_MAX')` を実行時に取得する。`len(os.fsencode(path))` が上限以上なら不許可にする。取得に失敗したとき、または値が正でないときも不許可にする（as-6）。長さの検査は `worktree_area()` の呼び出しより前に置く（as-1）
- [x] 過去 feature のテスト記録（requirement.legacy-test-records）: 削除したテスト ID を過去 feature の `*.tests.yaml` から外し、付け替えられるものは残るテストへ付け替える（as-7）
- [x] design ステップ（design-step.recommendation）: 省く（as-8）
- [x] worktree_path の正規性: 制約・前提の「worktree_path が正規であることを確かめる」は、この feature で生成側を確かめて直すことを指す。生成側で realpath（strict）により正規化する（FR8）。implementer に実行時の検査は追加しない（as-2）
- [x] 例外を不許可にする範囲: 現状と同じ `OSError` と `ValueError`（as-3）
- [x] 過去の SPEC.md: feature-docs/ の過去 5 feature の SPEC.md は履歴の文書として変更しない（as-9）

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- SPEC.md: `feature-docs/cd-prefix-canonical-path-only/SPEC.md`
