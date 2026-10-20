---
title: "artifact-digest-intermediate-symlink"
created_date: 2026-10-21
status: draft
---

# artifact-digest-intermediate-symlink - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/scripts/artifact-digest.py` は、パスの途中の要素がシンボリックリンクでもダイジェストを返す。
`python3 -B em-workflow/scripts/artifact-digest.py /proc/self/root/etc/hosts /etc/hosts` は同じダイジェストを 2 つ返す。

### 1.2 目的

- artifact-digest.py が、どこかの要素にシンボリックリンクを含むパスにダイジェストを返さないようにし、TM-6 の「シンボリックリンクを辿らない」保護を完全にする。
- 上記の再現コマンドが同じダイジェストを 2 つ返さず、1 つ目の要素が `not_a_regular_file`、終了コードが 1 になる。

### 1.3 スコープ

対象:

- `em-workflow/scripts/artifact-digest.py` のパスの開き方（FR1〜FR6）
- artifact-digest.py の docstring と `OPEN_FLAGS` のコメント、`em-workflow/references/artifact-digest.md` の「Calculation」節（FR7）
- 上記を確かめるテスト（AC1〜AC8）

対象外:

- `feature-docs/worker-digest-ownership/THREAT-MODEL.md` の編集（A6）
- `..` で開始ディレクトリより上に出ることの制限（A4）
- プラグインのバージョンの編集（NFR4、A7）

## 2. ビジネス要件

### 2.1 ビジネス目標

- artifact-digest.py は、どこかの要素にシンボリックリンクを含むパスに対して、決してダイジェストを返さない。これで TM-6 の「シンボリックリンクを辿らない」保護が完全になる。
- 再現コマンド `python3 -B em-workflow/scripts/artifact-digest.py /proc/self/root/etc/hosts /etc/hosts` は、同じダイジェストを 2 つ返さなくなる。1 つ目の要素は `not_a_regular_file`、終了コードは 1 になる。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| artifact-digest.py の呼び出し元 | em-workflow のオーケストレーター。統合ワークツリーから相対パスで呼び出す |

### 2.3 期待される効果

- 途中の要素がシンボリックリンクのパスについて、リンク先の内容のダイジェストが標準出力に現れない。
- 既存の結果（`missing` / `not_a_regular_file` / `unreadable` の判定、出力の形、終了コードの意味）は変わらない。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター |
|----|----------------|----------|
| UC01 | パス引数のダイジェストを計算する | オーケストレーター |

### 3.2 ユースケース詳細

#### UC01: パス引数のダイジェストを計算する

**アクター**: オーケストレーター

**事前条件**:
- 実行環境の `os.open` が `dir_fd` に対応し、`os.O_DIRECTORY` と `os.O_NOFOLLOW` がある。

**基本フロー**:
1. 1 つ以上のパスを引数に渡して artifact-digest.py を実行する。
2. スクリプトは各引数を要素ごとに、シンボリックリンクを辿らずに開く（FR1）。
3. 最後の要素が通常ファイルなら、その内容の sha256 を要素として返す。

**代替フロー**:
- 途中の要素がシンボリックリンク: その引数の要素は `not_a_regular_file`。他の引数は引き続きハッシュし、終了コードは 1（FR2）。
- 存在しない要素、権限エラーなど: 既存のエラートークンを返す（FR3）。
- 必要な機能が無い環境: 標準エラー出力にメッセージを書き、配列を出さず終了コード 2（FR6）。

**事後条件**:
- シンボリックリンク経由で到達した内容のダイジェストは標準出力に現れない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | シンボリックリンクを辿らずにパスを走査する | 要素ごとに直前のディレクトリ記述子を基準に開く |
| FR2 | 途中の要素のシンボリックリンクは `not_a_regular_file` | リンク先の種類によらず同じ結果 |
| FR3 | 既存の結果は変えない | `missing` / `not_a_regular_file` / `unreadable` の判定を保つ |
| FR4 | パスの書き方の扱い | 空要素・`.`・`..`・末尾 `/` の扱い |
| FR5 | 確認と読み込みの間の差し替えに対して安全 | 差し替えはエラーになるだけ |
| FR6 | 必要な機能が無い環境では止まる | 終了コード 2 |
| FR7 | 文書 | docstring と artifact-digest.md の更新 |

### 4.2 機能詳細

#### FR1: シンボリックリンクを辿らずにパスを走査する

**説明**: 各引数を要素ごとに開く。相対パスはカレントディレクトリから、絶対パスは `/` から始める。途中の各要素は、直前のディレクトリの記述子を基準に `O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC` で開く。最後の要素は、最後のディレクトリの記述子を基準に `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC` で開く。成否の判定に、パス全体の解決は使わない。

**入力**:
- 引数: パス文字列（相対・絶対）- 1 つ以上

**出力**:
- 標準出力: 引数ごとの要素の配列（形は変えない。NFR3）
- 終了コード: 意味は変えない。終了コード 2 に環境の機能不足を加える（FR6）

#### FR2: 途中の要素のシンボリックリンクは `not_a_regular_file`

**説明**: 途中のいずれかの要素がシンボリックリンクなら、その引数の要素は `{path, sha256: null, error: not_a_regular_file}` になる。リンク先がディレクトリでもファイルでも、リンク切れでも、ループでも同じ。リンク先のダイジェストは標準出力に一切現れない。他の引数は引き続きハッシュし、終了コードは 1。

#### FR3: 既存の結果は変えない

**説明**: 次の結果は変えない。

**エラーケース**:

| エラー | 条件 |
|--------|------|
| `missing` | 要素の実体が無い |
| `missing` | 途中の要素が存在するが、ディレクトリでもシンボリックリンクでもない |
| `missing` | 引数が空 |
| `not_a_regular_file` | 最後の要素がディレクトリ・シンボリックリンク・FIFO・デバイス・ソケット |
| `unreadable` | 権限エラー・I/O エラー（途中のディレクトリに検索権限が無い場合を含む） |

**ビジネスルール**:
- 途中の要素を開いて `ENOTDIR` か `ELOOP` で失敗したときは、その要素の種類をシンボリックリンクを辿らずに調べてから、エラーを決める。

#### FR4: パスの書き方の扱い

**ビジネスルール**:
- 空の要素（`a//b`）と `.` は飛ばす。
- `..` は引き続き許可する。`..` も `O_DIRECTORY|O_NOFOLLOW` で開くため、実ディレクトリ構造を辿る。拒否するのはシンボリックリンクだけ。
- 末尾の `/` は、最後の要素がディレクトリであることを求める。`a.md/` は `missing`、`dir/` は `not_a_regular_file`。
- パスは今と同じく、渡されたとおりに出力に返す。

#### FR5: 確認と読み込みの間の差し替えに対して安全

**説明**: 通常ファイルの判定は引き続き、実際に読む記述子への `fstat` で行う。走査中に途中または最後の要素が差し替えられても、結果はエラーになるだけ。シンボリックリンク経由で到達した内容のダイジェストにはならず、処理がブロックすることもない。

#### FR6: 必要な機能が無い環境では止まる

**説明**: スクリプトは、引数を処理する前に確認する。`os.open` が `dir_fd` に対応していない（`os.open not in os.supports_dir_fd`）か、`os.O_DIRECTORY` または `os.O_NOFOLLOW` が無い場合、パス全体の解決には戻らない。欠けている機能を名指しするメッセージを標準エラー出力に書き、配列を出さず、終了コード 2 で終える。

#### FR7: 文書

**説明**:
- artifact-digest.py の docstring で、エラートークン一覧の `not_a_regular_file` の行と「Entry kinds」の段落に、パスのどの要素もシンボリックリンクを辿らないことを書く。
- 同じ docstring の終了コード 2 の行に、環境が必要な機能を持たない場合を加える。
- `OPEN_FLAGS` のコメントも同様に更新する。
- `em-workflow/references/artifact-digest.md` の「Calculation」節で、`not_a_regular_file` の項目に「or a path any of whose components is a symlink」を加え、終了コード `2` の項目に環境の機能不足を加える。
- ディスパッチ箇所の節では、この文言を繰り返さない。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1: 標準ライブラリだけを使い、子プロセスや外部コマンドを起動しない。メモリ使用量は分割読み込みにより上限を保つ。既存の AC-7 のテストは通り続ける。

### 5.2 セキュリティ要件

- 入力検証: FR2、FR5 のとおり。
- 認証・認可・データ保護: 該当なし

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR2: 走査中に開いたディレクトリの記述子は、成功・エラーのどの経路でもすべて閉じる。
- ドキュメント: FR7 のとおり。

### 5.5 互換性要件

- NFR3: CLI、出力の形、エラートークンの集合、終了コードの意味は変えない。ただし終了コード 2 は、必要な機能を持たない環境の場合も表す。`tests/test_artifact_digest_script.py`、`tests/test_artifact_digest_docs.py`、`tests/test_digest_contract_alignment.py` の既存テストは、修正なしですべて通る。

## 6. UI/UX要件

該当なし（デザインステップはスキップ）

## 7. データ要件

該当なし（出力の形は変えない。NFR3）

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 標準ライブラリだけを使い、子プロセスや外部コマンドを起動しない（NFR1）。
- 必要な機能が無い環境で、パス全体の解決に戻らない（FR6）。
- NFR4: プラグインのバージョンは編集しない。patch の引き上げは GitHub Actions のワークフローが行う。

### 9.2 ビジネス上の制約

該当なし

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/artifact-digest-intermediate-symlink/**`
- `test-docs/artifact-digest-intermediate-symlink/**`

`feature-docs/artifact-digest-intermediate-symlink/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/artifact-digest-intermediate-symlink/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/artifact-digest-intermediate-symlink/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/artifact-digest-intermediate-symlink/` ディレクトリを生成しないが、宣言された `test-docs/artifact-digest-intermediate-symlink/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| どこかにシンボリックリンクを含む絶対パスは `not_a_regular_file` になる（例: `/proc/self/...`、macOS でシンボリックリンクの `/var` の下にある一時ディレクトリ） | 中 | 前提 A1 を参照 |
| `..` で開始ディレクトリより上に出ることは制限しない | 中 | 前提 A4 を参照 |

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1（FR1、FR2）: 一時ディレクトリに、木の外にある a.md を持つディレクトリへのシンボリックリンク `link` を作る。`link/a.md` は `not_a_regular_file`、`sha256` は null、終了コードは 1。a.md のダイジェストは標準出力に現れない。テストは `tests/test_artifact_digest_script.py` に置く。
- [ ] AC2（FR2）: AC1 の結果は次でも成り立つ。リンクしたディレクトリを通る絶対パスの引数、より深い要素のリンク（`sub/link/x/a.md`）、途中の要素のリンク切れ、途中の要素として使うファイルへのリンク（`file-link/x`）、途中の要素のリンクのループ。
- [ ] AC3（FR2）: Linux で `/proc/self/root/etc/hosts` は `not_a_regular_file`、終了コードは 1（`/proc/self/root` が無い環境ではテストを飛ばす）。同じ呼び出しで渡した `/etc/hosts` には引き続きダイジェストが返る。
- [ ] AC4（FR3、FR4）: 次は変わらない。`plain.md/child.md` は `missing`、`no-such-dir/a.md` は `missing`、`''` は `missing`。`sub/../sub/a.md`、`sub//a.md`、`./sub/a.md`、一時ディレクトリの絶対パスにはダイジェストが返る。`a.md/` は `missing`、`dir/` は `not_a_regular_file`。途中のディレクトリに検索権限が無いと `unreadable`（root で実行するときはテストを飛ばす）。
- [ ] AC5（FR5）: テスト用のドライバーで、途中の要素を確認するときはディレクトリに見せ、開くときはシンボリックリンクにする。結果はエラーで、ダイジェストは無い。最後の要素に対する既存の差し替えテストも引き続き通る。
- [ ] AC6（FR6）: テスト用のドライバーで `os.O_NOFOLLOW` か `os.O_DIRECTORY` を消す、または `os.supports_dir_fd` から `os.open` を除いてから、スクリプトを実行する。スクリプトは終了コード 2 で終わり、標準出力は空で、標準エラー出力にメッセージがある。
- [ ] AC7（FR7、NFR3）: docstring と artifact-digest.md の「Calculation」節に、どの要素のシンボリックリンクも `not_a_regular_file` になること、環境の機能不足は終了コード 2 になることが書かれている。`tests/test_artifact_digest_docs.py`、`tests/test_digest_contract_alignment.py`、`check-plugin-invariants.py` が通る。
- [ ] AC8（NFR1、NFR2、NFR3）: `python3 -m unittest discover -s tests` が通る。AC-7 の標準ライブラリ・子プロセスなしのテストを含む。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 受け入れ基準 | シナリオ |
|----|--------------|----------|
| TS1 | AC1 | `tmp/outside/a.md` があり、`tmp/work/link` が `../outside` を指す。カレントディレクトリ `tmp/work` で `link/a.md` を実行する。期待: `[{path:'link/a.md', sha256:null, error:'not_a_regular_file'}]`、終了コード 1、標準出力に `ABC_DIGEST` が無い。 |
| TS2 | AC2 | 各ケースを subTest で確かめる: リンクを通る絶対パス、`sub/link/x/a.md`、`dangling/a.md`、通常ファイルを指す `file-link` での `file-link/x`、`loop-a/x`。どれも `not_a_regular_file`、終了コード 1。同じ呼び出しに並べた通常ファイルは引き続きハッシュされる。 |
| TS3 | AC3 | `/proc/self/root/etc/hosts` と `/etc/hosts` を一緒に実行する。期待: 要素 0 が `not_a_regular_file`、要素 1 が sha256、終了コード 1。`os.path.islink('/proc/self')` と `/etc/hosts` の存在で skipUnless する。 |
| TS4 | AC4 | 末尾スラッシュと権限のケース: `a.md/` は `missing`、`dir/` は `not_a_regular_file`、`link-to-dir/` は `not_a_regular_file`、mode 0o000 の途中ディレクトリは `unreadable`（root で実行するとき、またはアクセスが通ってしまうときは飛ばす）。既存の AC-2 と AC-5 のケースは修正なしで通る。 |
| TS5 | AC5 | 差し替えドライバーが `os.open` を置き換える。呼び出しが `O_DIRECTORY` と `dir_fd` を伴うとき、ドライバーはまず名前のディレクトリを外のディレクトリへのシンボリックリンクに差し替え、それから本物の `os.open` を呼ぶ。期待: `not_a_regular_file`、外のファイルのダイジェストは無い。 |
| TS6 | AC6 | `os.O_NOFOLLOW` の削除、`os.O_DIRECTORY` の削除、`os.supports_dir_fd` から `os.open` を除く、の 3 通りの変更のあと、runpy でスクリプトを実行する。各 subTest で、終了コード 2、標準出力が空、標準エラー出力が空でないことを期待する。 |
| TS7 | AC7 | 見出しでテキストを切り出して文書のアサーションを足す: artifact-digest.md の「Calculation」で、`not_a_regular_file` がどの要素のシンボリックリンクも含むと書かれている。docstring が「辿らない」を最後の要素に限定していない。 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 要素 | パスを `/` で区切った各部分 |
| 途中の要素 | 最後の要素より前の要素 |
| 最後の要素 | パスの末尾の要素 |
| TM-6 | `feature-docs/worker-digest-ownership/THREAT-MODEL.md` の脅威項目。「シンボリックリンクを辿らない」と書かれている |

## 14. 確認事項

### 14.1 確認済み事項

- [x] フィーチャー名: `artifact-digest-intermediate-symlink`
- [x] `..` の要素の扱い（`requirement.dotdot-components`）: `keep_dotdot`。`..` はこれまでどおり許可し、実ディレクトリ上で辿る。拒否対象はシンボリックリンクだけ。
- [x] 機能が無い環境での扱い（`requirement.platform-fallback`）: `fail_closed_exit2`。`dir_fd` / `O_DIRECTORY` / `O_NOFOLLOW` のいずれかが使えない環境では、パス単位の検査に戻らず、標準エラー出力にメッセージを書き、配列を出さずに終了コード 2 で終える。
- [x] デザインステップ（`design-step.decision`）: `skip`

### 14.2 未確認・保留事項

なし

### 14.3 前提

- A1: 絶対パスの引数も、同じ「シンボリックリンクを辿らない」規則で `/` から走査する。どこかにシンボリックリンクを含む絶対パスは `not_a_regular_file` になる。例: `/proc/self/...`、macOS でシンボリックリンクの `/var` の下にある一時ディレクトリ。
- A2: 存在するがディレクトリでもシンボリックリンクでもない途中の要素は、引き続き `missing`。
- A3: 途中の要素のシンボリックリンクは、リンク切れ・ループ・ファイルへのリンク・ディレクトリへのリンクのどれでも `not_a_regular_file`。
- A4: `..` の要素は引き続き許可し、実ディレクトリ構造上で辿る。`..` で開始ディレクトリより上に出ることは対象外。
- A5: 必要な機能が無い環境では、終了コード 2 で閉じた側に失敗する。パス全体に対する従来の確認には決して戻らない。
- A6: `feature-docs/worker-digest-ownership/THREAT-MODEL.md` は編集しない。
- A7: プラグインのバージョンは編集しない。

## 15. 参考資料

- `em-workflow/scripts/artifact-digest.py`
- `em-workflow/references/artifact-digest.md`
- `feature-docs/worker-digest-ownership/THREAT-MODEL.md`
