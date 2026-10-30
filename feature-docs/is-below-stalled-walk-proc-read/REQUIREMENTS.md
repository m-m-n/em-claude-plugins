---
title: "is-below-stalled-walk-proc-read"
created_date: 2026-10-30
status: draft
---

# is-below-stalled-walk-proc-read - 要件定義書

## 1. 概要

### 1.1 背景
`em-workflow/hooks/bash_guard.py` の `is_below` は、段階走査（stage walk）が存在しない段や通常ファイルの段で止まったあと、`os.path.realpath` を呼ぶ。変更前は、この形で `/proc` 配下の段の検査（probe）やリンクの読み取りが記録される（TS2）。

### 1.2 目的
- `is_below` の段階走査が存在しない段や通常ファイルの段で止まったとき、その後に続く `os.path.realpath` 呼び出しが `/proc` や `/dev/fd` 配下を `lstat` / `readlink` しないようにする。物理パス側と論理パス側の両方で成り立つ。
- 判定が、フックのプロセス自身の cwd や fd（`/proc/self/...`）に依存しないようにする。

### 1.3 スコープ
- `em-workflow/hooks/bash_guard.py` の `_stage_walk_refuses` と、関連する docstring（`_stage_walk_refuses`、`is_below`、モジュール）
- `em-workflow/references/command-execution-protocol.md` の Verbatim execution rule のパス項目
- `tests/test_bash_guard_cd_prefix.py` へのテスト追加

## 2. ビジネス要件

### 2.1 ビジネス目標
- 段階走査が止まった形の判定中に、`/proc` や `/dev/fd` 配下を読まない。
- 判定がフックのプロセス自身の cwd や fd に依存しない。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 段階走査が止まった形を判定する間、`/proc` / `/dev/fd` 配下への `os.lstat` / `os.stat` / `os.readlink` が発生しない（NFR2）。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | 止まった段階走査を緩い realpath の規則で続ける | 存在しない段・ディレクトリでない段で走査を終えず、非 strict の `os.path.realpath` と同じ規則で続ける |
| FR2 | 継続中に `/proc` / `/dev/fd` の段で拒否する | 継続中も既存の段チェックをそのまま適用し、拒否時は `os.path.realpath` を呼ばずに `False` を返す |
| FR3 | 継続が `/proc` / `/dev/fd` に届かなければ拒否しない | 走査後は既存の規則で判定する |
| FR4 | 継続中のリンク上限とエラー | 同じ `FOLLOWED_LINK_LIMIT`（40）を数え、継続中の `lstat` / `readlink` 失敗は拒否しない |
| FR5 | 規則の記述を更新する | docstring と protocol の記述を継続の規則に合わせる |
| FR6 | 変えないもの | シグネチャ、呼び出し元、判定順、cd prefix の判定表などを維持する |
| FR7 | ファイル操作を記録するテスト | `_recorded_probes` を使うテストを追加する |
| FR8 | 記録器のガードテスト | `_recorded_probes` が `os.path.realpath` 内部の呼び出しを捕捉することを示す |

### 4.2 機能詳細

#### FR1: 止まった段階走査を緩い realpath の規則で続ける

**説明**: `_stage_walk_refuses` が存在しない段、またはディレクトリでない段に達したとき、走査を終えない。非 strict の `os.path.realpath` と同じ規則で続ける。

**ビジネスルール**:
- その段は到達位置に通常の名前として連結され、後続の `..` で取り除かれる。
- 走査が既存の位置に戻ったら、再び段を検査し、リンクを辿る。
- 相対のリンク先は、そのリンクを持つディレクトリから解決する。
- 絶対のリンク先は、到達位置をルートに戻す。
- 論理パスの走査（`_stage_walk_refuses(os.path.normpath(path))`）と物理パスの走査（`_stage_walk_refuses(path)`）の両方に適用する。

#### FR2: 継続中に `/proc` / `/dev/fd` の段で拒否する

**説明**: 継続中も既存の段チェックをそのまま適用する。

**ビジネスルール**:
- 到達した段が `_under_proc_or_dev_fd` で `/proc` または `/dev/fd` 配下と判定されたら、走査は拒否する。`..` のあとに残った位置も含む。
- 辿るリンクの絶対リンク先の文字列が `/proc` または `/dev/fd` 配下なら、走査は拒否する。
- 拒否は、その段を検査する前に行う。
- どちらかの走査が拒否したら、`is_below` は `os.path.realpath` を呼ばずに `False` を返す。

#### FR3: 継続が `/proc` / `/dev/fd` に届かなければ拒否しない

**説明**: 継続が `/proc` や `/dev/fd` の段に触れずにパスの終わりまで達したら、走査は拒否しない。

**ビジネスルール**:
- 走査後は既存の規則で結果を決める。論理パスがディレクトリなら論理パスと物理パスの両方が領域の真下にあること、そうでなければ物理パスだけで判定する。
- `tests/test_bash_guard_cd_prefix.py:1572` で固定されている「止まった走査は拒否ではない」という規則を保つ。

#### FR4: 継続中のリンク上限とエラー

**説明**: 継続中に辿ったリンクも、同じ `FOLLOWED_LINK_LIMIT`（40）に数える。

**ビジネスルール**:
- 上限を超えて辿ったら拒否する。
- 継続中の `lstat` / `readlink` の失敗は、非 strict の realpath と同じように扱う。その段は通常の名前として扱い、走査を続け、拒否しない。
- 走査が止まる前は既存のエラー規則を保つ。存在しない段・ディレクトリでない段以外のエラーは拒否する。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| リンク上限超過 | 継続後を含めて辿ったリンクが `FOLLOWED_LINK_LIMIT` を超える | 拒否する |
| `lstat` / `readlink` の失敗 | 継続中 | 通常の名前として扱い、拒否しない |
| 存在しない段・ディレクトリでない段以外のエラー | 走査が止まる前 | 拒否する（既存） |

#### FR5: 規則の記述を更新する

**説明**: 規則の記述を継続の規則に合わせる。

**ビジネスルール**:
- `_stage_walk_refuses` の docstring から 'A stage that does not exist, or a non-directory, ends the walk without refusal ...' の文を除き、代わりに FR1 と FR2 の継続の規則を書く。
- 次の箇所で、段チェックが存在しない段・ディレクトリでない段の先も緩い realpath と同じように続くことを書く。
    - `is_below` の docstring の `/proc` と `/dev/fd` の段落
    - モジュール docstring のパス項目
    - `em-workflow/references/command-execution-protocol.md` の Verbatim execution rule のパス項目
- モジュール docstring のパス項目と protocol のパス項目は同一の文言で書く。
- 既存の文言テストの needle は保つ。

#### FR6: 変えないもの

**説明**: 次のものは変更しない。

**ビジネスルール**:
- `is_below` と `_stage_walk_refuses` のシグネチャと呼び出し元
- `_under_proc_or_dev_fd`
- `FOLLOWED_LINK_LIMIT` の値
- `is_below` がチェックを行う順序
- cd prefix の許可の判定表（allow / silent / deny）
- realpath の前に `resolves_to_directory(path)` を呼ぶ事前チェックは追加しない（A6）。

#### FR7: ファイル操作を記録するテスト

**説明**: `tests/test_bash_guard_cd_prefix.py` に、`os.lstat` / `os.stat` / `os.readlink` の記録器 `_recorded_probes` を使うテストを追加する。フィクスチャに次のリンク先を置き、それぞれについて「`is_below` が `False` を返すこと」と「判定中に `/proc` / `/dev/fd` 配下が検査・読み取りされないこと」を確かめる。

- (a) `proc` で始まる相対リンク先: `proc/missing/` のあとに `..`、続いて `proc/self/cwd`
- (b) `proc` で始まらない相対リンク先: `x/missing/` のあとに `..`、続いて `proc/self/cwd`
- (c) 絶対リンク先: `<area>/task/missing/` のあとに `..`、続いて `proc/self/cwd`
- (d) 存在しない段の代わりに通常ファイルの段で止まるリンク先
- (e) `/proc` の代わりに `/dev/fd/<n>` で終わるリンク先

**ビジネスルール**:
- 各リンク先の `..` の数は、`climb_target` と同じように一時ディレクトリの深さから計算し、ルートまで上がるようにする。
- 論理パスの角のケース（A1）の形も、モジュール単位とフック経由の両方で追加する。

#### FR8: 記録器のガードテスト

**説明**: この Python（3.14）で、`_recorded_probes` が `os.path.realpath` 内部の `lstat` / `readlink` 呼び出しを捕捉することを示すガードテストを追加する。

**ビジネスルール**:
- 例: 記録器の中で FR7 (a) または (b) の止まった形に直接 `os.path.realpath` を実行し、`/proc` 配下の検査またはリンク読み取りが 1 件以上記録されることを確かめる。これで FR7 のテストが空振りで通ることを防ぐ。
- FR7 の各ケースでは、リンク自身が `record['reads']` に現れることも確かめる。

## 5. 非機能要件

### NFR1: 判定変更の向きと範囲
`is_below` の判定が変わるのは次の 2 つの場合だけで、向きは `True` から `False` のみ。
- A1 の論理パスの角のケース: 止まった論理パスの走査の字句的な継続が `/proc` / `/dev/fd` の段に達する場合
- A3 のリンク上限

物理パス側（A5）や、止まるリンクを直接通る形を含め、それ以外の判定はすべて変わらない。

### NFR2: `/proc` / `/dev/fd` 配下を読まない
段階走査が存在しない段または通常ファイルの段で止まるパスを `is_below` が判定する間、物理パス側でも論理パス側でも、`/proc` / `/dev/fd` 配下を `os.lstat` / `os.stat` で検査せず、`os.readlink` で読まない。`os.path.realpath` の呼び出しも含む。

### NFR3: 既存テストを保つ
`tests/test_bash_guard_cd_prefix.py` の既存のテストやアサーションを削除も弱めもしない。特に次はそのまま通る。
- `test_ac6_a_missing_stage_or_a_non_directory_stage_is_not_an_error`
- `test_ac2_the_logical_walk_refuses_a_form_only_the_collapsed_path_reaches`
- `test_ac4_the_decision_does_not_depend_on_strict_mode_realpath`
- `TestRelativeLinkTarget` のすべて

### NFR4: 実装上の制約
- 標準ライブラリのみ使う。
- パスチェックは子プロセスを起動しない。
- プラグインの version は触らない。

## 6. UI/UX要件

該当なし。デザインステップは skipped（変更は Python フックの内部のパスチェックのロジックと、そのテストと文言に限られ、UI や視覚的な出力が無い。デザインステップの回答は decide_autonomously で、スキップの推奨が採用された）。

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 標準ライブラリのみ使う（NFR4）。
- パスチェックは子プロセスを起動しない（NFR4）。
- `is_below` のチェック順序は変えない（FR6）。

### 9.2 ビジネス上の制約
- em-workflow の version は変更しない。main への push 時に GitHub Actions が patch を上げる（A7）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/is-below-stalled-walk-proc-read/**`
- `test-docs/is-below-stalled-walk-proc-read/**`

`feature-docs/is-below-stalled-walk-proc-read/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/is-below-stalled-walk-proc-read/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/is-below-stalled-walk-proc-read/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/is-below-stalled-walk-proc-read/` ディレクトリを生成しないが、宣言された `test-docs/is-below-stalled-walk-proc-read/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: FR7 (a)〜(e) のすべての形で `is_below` が `False` を返す。`_recorded_probes` には `/proc` / `/dev/fd` 配下の検査も読み取りも記録されず、リンク自身は reads に記録される。物理パス側と論理パス側の両方で成り立つ。（FR1, FR2, FR7, NFR2）
- [ ] AC2: 論理パスが `/proc/self/cwd/<name>` へ上がる止まるリンクを通り、物理パスは領域の真下の既存ディレクトリである形を取る。例: `<root>/hop/../<link name>` で、`<root>/<link name>` が止まるリンク、`area/task0001/<link name>` がディレクトリ。フィクスチャはまず、旧規則（緩い realpath）ならこの形が `True` と判定されたことを確かめる。そのうえで、フックのプロセスの cwd を領域内にした状態で、`is_below` が `False` を返し、フックは silent のままで、判定中に `/proc` / `/dev/fd` 配下は検査も読み取りもされない。（FR1, FR2, FR7, NFR1, NFR2）
- [ ] AC3: ガードテストが、直接の `os.path.realpath` 呼び出しの内部で行われた `/proc` 配下の検査またはリンク読み取りを `_recorded_probes` が捕捉することを示す。（FR8）
- [ ] AC4: 止まった継続が `/proc` / `/dev/fd` に届かない形は、既存の判定を保つ。1572 行目のテスト（`resolves_to_directory` をモックして `True`）、cd-prefix-non-directory-dotdot の存在しない段・通常ファイルの `..` の形（`False`）、is-below-physical-fallback の物理パスへのフォールバックの形（allow）、`TestRelativeLinkTarget`（相対リンク先 `proc`、`./proc`、`dev/fd` は `True` のまま、上がるリンクは `False` のまま）を含む。（FR3, NFR1, NFR3）
- [ ] AC5: 止まったあとに辿ったリンクで合計が `FOLLOWED_LINK_LIMIT` を超えたら、結果は `False`。継続中に `lstat` / `readlink` のエラーが起きても、そのエラーを理由に走査は拒否しない。（FR4）
- [ ] AC6: `_stage_walk_refuses` の docstring に 'ends the walk without refusal' が含まれない。FR5 の 4 箇所が継続の規則を記述する。モジュール docstring のパス項目と protocol のパス項目は同一の文言を使う。既存の文言テスト（`TestPathConditionWording`、`TestProcessDependentPathWording`、`TestLinkTargetWording`）が通る。（FR5）
- [ ] AC7: `python3 -m unittest discover -s tests` がすべて通る。既存のアサーションを削除も弱めもしない。テストモジュールは標準ライブラリのみ import する。追加した形の判定中、パスチェックは子プロセスを起動しない。`is_below` に、realpath の前に `resolves_to_directory` を呼ぶ事前チェックを追加しない。（FR6, NFR3, NFR4）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: FR7 の (a) 相対 `proc/missing/...`、(b) 相対 `x/missing/...`、(c) 絶対 `<area>/task/missing/...`、(d) 通常ファイルの段、(e) `/dev/fd/<n>` の変形のそれぞれで、リンクを作り、`_recorded_probes` の中で `is_below` を呼び、`False` であること、`_is_proc_or_dev_fd_location` で `/proc` / `/dev/fd` 配下となる記録パスが無いこと、リンクが reads にあることを確かめる。(e) は `/dev/fd` がディレクトリのときだけ実行する（`needs_dev_fd`）。`/proc` のケースは `needs_proc` のもとで実行する。
- [ ] TS2（AC1、red の確認）: 変更前は、同じ形で `/proc` 配下の検査または読み取りが記録される。テストを書くときに確かめる。
- [ ] TS3（AC2）: A1 の角のケースの形。cwd を `procdep/work` にして、モジュール単位で `is_below` が `False` で、`/proc` 配下に何も記録されないことを確かめる。フック経由では `process_cwd=work` で silent を確かめる。加えて、`resolves_to_directory` を `True` にモックした状態で、論理パスの走査だけで拒否することを確かめる。
- [ ] TS4（AC3）: ガードテスト。`_recorded_probes` の中で止まった形に直接 `os.path.realpath` を呼び、`/proc` 配下の検査または読み取りが記録されることを確かめる。
- [ ] TS5（AC4）: AC4 に挙げた既存テストがそのまま通る。
- [ ] TS6（AC5）: 止まったあとに 40 を超えるリンクを辿る連鎖は `False` になる。継続中の 1 つの段でだけ `os.lstat` または `os.readlink` が例外を投げるようにモックし、そのエラーだけでは走査が拒否しないことを確かめる。
- [ ] TS7（AC6）: docstring と protocol の文言を確かめ、既存の文言テストが通ることを確かめる。

実行コマンド:
- 対象を絞った実行: `python3 -m unittest tests.test_bash_guard_cd_prefix`
- 全体の実行: `python3 -m unittest discover -s tests`

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 継続（continuation） | `_stage_walk_refuses` が存在しない段・ディレクトリでない段に達したあと、非 strict の `os.path.realpath` と同じ規則で走査を続けること（FR1） |
| 論理パスの走査 | `_stage_walk_refuses(os.path.normpath(path))` |
| 物理パスの走査 | `_stage_walk_refuses(path)` |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: 論理パスの角のケース（止まった走査の字句的な継続が `/proc` / `/dev/fd` の段に達する場合）での `True` から `False` への変化は、タスクの受け入れ基準「`is_below` の判定は変わらない」の例外として受け入れる。requirement.logical-side-stalled-walk への回答: refuse_on_proc_stage（batch の Codex 相談で決定）。
- [x] A2: 止まった走査をすべて拒否すると、止まった走査は拒否ではないことを固定している `tests/test_bash_guard_cd_prefix.py:1572` の既存テストが壊れる。そのため、継続が `/proc` / `/dev/fd` の段に達したときだけ拒否する。
- [x] A3: 止まったあとに辿ったリンクも `FOLLOWED_LINK_LIMIT` に数え、超えたら拒否する。上限が無いと、長い連鎖の末端で realpath が `/proc` に達しないことを走査が保証できない。これは A1 の角のケース以外での `True` から `False` への変化で、止まったあとに 40 を超えるリンクを辿ったときだけ起きる。
- [x] A4: 継続中の `lstat` / `readlink` エラーは、非 strict の realpath（Python 3.14）と同じく通常の名前として扱い、拒否しない。realpath はリンクを読めなければそのリンクを辿って `/proc` に入ることもできないので、realpath に合わせることで読まない保証を保ち、判定も変わらない。
- [x] A5: 同じ継続の規則を物理パスの走査にも適用する。物理パスの走査が止まるときはカーネルによる解決（`resolves_to_directory`）も失敗するため、`is_below` はもともと `False` で、判定は変わらない。目的は `os.path.realpath(path)` での `/proc` の読み取りを止めること。
- [x] A6: タスクが提案した物理パス側の事前チェック（realpath の前に `resolves_to_directory(path)` を呼ぶ）は採用しない。理由: (1) 継続した走査は両方の realpath 呼び出しより前に走り、realpath と同じ緩い規則（存在しない段・通常ファイルの段を通常の名前として扱う、字句的な `..`、リンクを辿る）に従う。走査が拒否しなければ realpath は `/proc` / `/dev/fd` の段に達しないので、走査だけで両側を覆える。(2) 事前チェックは物理パス側しか覆わず、論理パス側の `realpath(normpath(path))` には依然として走査が要る。(3) 仕組みを 1 つに保つと、規則の記述とテストが 1 箇所にまとまる。`is_below` の順序は変えない（FR6）。
- [x] A7: em-workflow の version は変更しない。main への push 時に GitHub Actions が patch 番号を上げる。
- [x] デザインステップ: decide_autonomously の回答により、スキップの推奨を採用した。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- `em-workflow/hooks/bash_guard.py`: 変更対象のフック
- `em-workflow/references/command-execution-protocol.md`: Verbatim execution rule のパス項目
- `tests/test_bash_guard_cd_prefix.py`: 既存テストと追加テストの置き場所
