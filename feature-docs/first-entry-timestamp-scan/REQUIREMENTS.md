---
title: "first-entry-timestamp-scan"
created_date: 2026-09-29
status: draft
---

# first-entry-timestamp-scan - 要件定義書

## 1. 概要

### 1.1 背景
D2 form 2（marker による現セッション解決）と、それを使う I.2.b の orphan recovery について、次の経路を継続的に守るテストが無い。

- 先頭に timestamp の無い記録を持つ transcript を、form 2 で解決する経路
- recover-orphaned-task.py をコマンドライン入口から `--marker` で呼ぶ経路

### 1.2 目的
- D2 form 2 が、先頭に timestamp の無い記録を持つ transcript でも current-session-unknown に落ちないことを、テストで継続的に守る
- I.2.b の orphan recovery（FR2 の証明経路）が、コマンドライン入口から form 2 で呼ばれたときに成立することを、テストで固定する

### 1.3 スコープ
範囲は keep-earliest-add-tests とする。D2 の最小値規則のまま挙動は変えず、回帰テストを 2 件（FR1、FR2）追加する。

範囲外:
- 開始時刻の導出を「位置で最初」に変えること
- D2 や TS-14 の意味の変更
- 関係の無い整理

## 2. ビジネス要件

### 2.1 ビジネス目標
- D2 form 2（marker による現セッション解決）が、先頭に timestamp の無い記録を持つ transcript でも current-session-unknown に落ちないことを、テストで継続的に守る
- I.2.b の orphan recovery（FR2 の証明経路）が、コマンドライン入口から form 2 で呼ばれたときに成立することを、テストで固定する

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- D2 form 2 の解決が、先頭に timestamp の無い記録を持つ transcript で退行したとき、テストで検出できる
- コマンドライン入口から form 2 で呼ぶ orphan recovery が退行したとき、テストで検出できる

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | コマンドライン入口から form 2 を通す回帰テスト | recover-orphaned-task.py をコマンドライン入口から subprocess で呼び、`--marker` で D2 form 2 を通すテストを追加する | confirmed |
| FR2 | 実際の transcript の冒頭を模した fixture の回帰テスト | timestamp の無い記録を先頭に並べた transcript に対し、marker による解決が最も早い timestamp を返すことを確かめるテストを追加する | confirmed |
| FR3 | 開始時刻の導出規則は変えない | recover-orphaned-task.py の挙動、IMPLEMENTATION.md D2、TS-14 の意味を変えない | confirmed |

### 4.2 機能詳細

#### FR1: コマンドライン入口から form 2 を通す回帰テスト

**説明**: recover-orphaned-task.py をコマンドライン入口から subprocess で呼び、`--marker` で D2 form 2 を通すテストを追加する。現セッションの transcript は、先頭記録が timestamp を持たず、marker を含む。それ以外は孤児であることが証明できる fixture にする。結果は recovered で、journal には reason orphaned の failed がちょうど 1 件追記される。

**入力**:
- `--journal`
- `--agents-index`
- `--task`
- `--transcripts-dir`: 一時ディレクトリ
- `--marker`
- `--current-session-id` と `--current-session-start` は渡さない

**fixture**:
- 現セッションの transcript は、timestamp の無い先頭記録と、marker を含み timestamp を持つ後続行から成る
- 記録済みセッションの transcript は、現セッションの開始より厳密に前に活動が止まっている
- journal の最終イベントは launched
- agent index のエントリは launch に結び付いている
- journal ヘルパーは実物（journal-append-failed.py）を使う

**出力**:
- 終了コード: 0
- stdout: `{"outcome":"recovered","task":<task>,"reason":""}`
- journal: launched の後に、reason orphaned の failed が 1 行だけ増える

#### FR2: 実際の transcript の冒頭を模した fixture の回帰テスト

**説明**: type の異なる timestamp の無い記録を 3 件以上並べ、その後に有効な timestamp を 15:00、10:00 の順で置いた transcript を fixture にする。marker による解決が（ファイル名の stem, 10:00）を返すことを確かめるテストを追加する。

**入力**:
- marker を含む transcript。冒頭に type の異なる timestamp の無い記録が 3 件以上並び、その後に有効な timestamp を持つ行が 15:00、10:00 の順で続く
- 呼び出し: `resolve_current_session(None, None, marker, dir)`

**出力**:
- （ファイル名の stem, 10:00）

**検出できる退行**:
| 退行した実装 | 返る値 |
|--------------|--------|
| 先頭行だけを見る実装 | None |
| 位置で最初を採る実装 | 15:00 |

#### FR3: 開始時刻の導出規則は変えない

**説明**: recover-orphaned-task.py の挙動は変えない。D2 form 2 の開始時刻は、今までどおり、確定した transcript の中で最も早い解析可能な timestamp とする。IMPLEMENTATION.md D2 と TS-14 の意味も変えない。

**ビジネスルール**:
- D2 form 2 の marker 走査（更新時刻が新しい順、marker を含む最初の transcript に確定、古い transcript に戻らない）は変えない
- form 1 が優先される規則は変えない
- SC6 の current-session-unknown の意味は変えない
- 解析できる timestamp が 1 つも無い transcript を未解決として扱う規則は変えない

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | 追加するテストはリポジトリ直下の `tests/` の `test_*.py` に置き、標準ライブラリだけを使う。transcripts ディレクトリは必ず `--transcripts-dir`（または引数）で一時ディレクトリを指定し、実際の `~/.claude` を読み書きしない |
| NFR2 | `python3 -m unittest discover -s tests` をリポジトリのルートで実行し、失敗 0・エラー 0 で終わる |
| NFR3 | これまで証明できなかった復旧が、新たに証明できるようになる変更をしない（安全側に倒す方向を保つ） |
| NFR4 | em-workflow の version は手で変えない |

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 追加するテストは標準ライブラリだけを使う（NFR1）
- 実際の `~/.claude` を読み書きしない（NFR1）
- 変更しないファイル: `em-workflow/scripts/recover-orphaned-task.py`、IMPLEMENTATION.md の D2、VERIFICATION.md の TS-14（FR3）

### 9.2 ビジネス上の制約
- em-workflow の version は手で変えない。patch は main への push 時に Actions が上げる（NFR4）

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/first-entry-timestamp-scan/**`
- `test-docs/first-entry-timestamp-scan/**`

`feature-docs/first-entry-timestamp-scan/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/first-entry-timestamp-scan/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/first-entry-timestamp-scan/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1 (FR1): コマンドライン入口を subprocess で呼ぶテストがある。引数は `--journal`、`--agents-index`、`--task`、一時ディレクトリの `--transcripts-dir`、`--marker` で、`--current-session-id` と `--current-session-start` は渡さない。現セッションの transcript は先頭記録が timestamp を持たず marker を含み、ほかの条件は孤児と証明できる fixture になっている。このテストで、終了コード 0、stdout が `{"outcome":"recovered","task":<task>,"reason":""}`、journal に reason orphaned の failed がちょうど 1 件追記されることを確かめる
- [ ] AC-2 (FR2): 先頭に type の異なる timestamp の無い記録が 3 件以上並び、その後に有効な timestamp が 15:00、10:00 の順で続く marker 入りの transcript がある。これに対し、marker による解決が（ファイル名の stem, 10:00）を返すことをテストで確かめる
- [ ] AC-3 (FR3): `em-workflow/scripts/recover-orphaned-task.py`、IMPLEMENTATION.md の D2、VERIFICATION.md の TS-14 は、この feature では変更しない
- [ ] AC-4 (NFR1, NFR2): `python3 -m unittest discover -s tests` が失敗 0・エラー 0 で終わる。追加したテストは標準ライブラリだけを使い、実際の `~/.claude` に触れない
- [ ] AC-5: 再現手順で現象が起きない。実際のセッションから D2 form 2 を 1 度読み取り専用で実行し、現セッションの transcript の stem と開始時刻が返り、current-session-unknown にならない

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 対象 | 種別 | シナリオ | 期待結果 |
|----|------|------|----------|----------|
| TS-1 | FR1, AC-1 | Integration | コマンドライン入口から `--marker`（form 2）で実行する。現セッションの transcript は timestamp の無い先頭記録と、marker を含み timestamp を持つ後続行から成る。記録済みセッションの transcript は、現セッションの開始より厳密に前に活動が止まっている。journal の最終イベントは launched で、agent index のエントリは launch に結び付いている。journal ヘルパーは実物（journal-append-failed.py）を使う | 終了コード 0、stdout は recovered の JSON、journal には launched の後に reason orphaned の failed が 1 行だけ増える |
| TS-2 | FR2, AC-2 | Unit | marker を含む transcript を用意する。冒頭に type の異なる timestamp の無い記録が 3 件以上並び、その後に有効な timestamp を持つ行が 15:00、10:00 の順で続く。この transcript に対して `resolve_current_session(None, None, marker, dir)` を呼ぶ | (stem, 10:00) が返る。先頭行だけを見る実装なら None、位置で最初を採る実装なら 15:00 になるため、どちらへの退行も検出できる |
| TS-3 | NFR1, NFR2, AC-4 | Integration | リポジトリのルートで `python3 -m unittest discover -s tests` を実行する | 失敗 0・エラー 0 |
| TS-4 | AC-5 | Manual | 実際のセッションで marker を出力した後、transcripts ディレクトリに対して D2 form 2 の解決を 1 度読み取り専用で実行する | 現セッションの transcript の stem と開始時刻が返る。current-session-unknown になれば失敗 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| D2 form 2 | marker による現セッション解決 |
| D2 form 2 の開始時刻 | 確定した transcript の中で最も早い解析可能な timestamp |
| marker 走査 | 更新時刻が新しい順に transcript を見て、marker を含む最初の transcript に確定する。古い transcript には戻らない |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1 範囲: keep-earliest-add-tests とする。D2 の最小値規則のまま挙動は変えず、回帰テストを 2 件（FR1、FR2）追加する。位置で最初への変更、D2 や TS-14 の意味の変更、関係の無い整理は範囲外
- [x] A2 marker 走査: D2 form 2 の marker 走査（更新時刻が新しい順、marker を含む最初の transcript に確定、古い transcript に戻らない）と、form 1 が優先される規則は変えない
- [x] A3 未解決の扱い: SC6 の current-session-unknown の意味と、解析できる timestamp が 1 つも無い transcript を未解決として扱う規則は変えない
- [x] A4 version: em-workflow の version は手で変えない。patch は main への push 時に Actions が上げる

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- IMPLEMENTATION.md D2
- VERIFICATION.md TS-14
- `em-workflow/scripts/recover-orphaned-task.py`
