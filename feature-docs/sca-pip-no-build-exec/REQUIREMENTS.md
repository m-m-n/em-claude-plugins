---
title: "sca-pip-no-build-exec"
created_date: 2026-11-28
status: draft
---

# sca-pip-no-build-exec - 要件定義書

## 1. 概要

### 1.1 背景
review-sca-axis FR1 は、SCA 軸 2 の pip のコマンド形を `pip-audit --format json` と定めている。本機能は、この pip のコマンド形を本書 FR1 / FR5 の形に置き換える。

### 1.2 目的
- SCA 軸 2 の pip 経路は、レビュー対象プロジェクトのビルドバックエンド、`setup.py`、PEP 517 フックを一度も実行しない。
- pip の入力はすべて、静的に抽出した完全に固定されたパッケージ一覧として監査するか、機械で読める `skip_reason` を返す。
- レジストリとそのテストの固定値を同じ変更で更新し、`python3 -m unittest discover -s tests` が通る。

### 1.3 スコープ
- 対象: pip の走査単位（`requirements.txt`、`pyproject.toml`、`poetry.lock`、`Pipfile.lock`）の監査経路、`em-workflow/references/vuln-scanners.yaml` の pip エントリ、関連するテスト。
- npm（`npm audit`）、cargo（`cargo-audit`）、go（`govulncheck`）は確認のみを行い、挙動は変えない（F09）。
- `feature-docs/review-sca-axis/` 配下の文書は編集しない。

## 2. ビジネス要件

### 2.1 ビジネス目標
- SCA 軸 2 の pip 経路は、レビュー対象プロジェクトのビルドバックエンド、`setup.py`、PEP 517 フックを一度も実行しない。
- pip の入力はすべて、静的に抽出した完全に固定されたパッケージ一覧として監査するか、機械で読める `skip_reason` を返す。
- レジストリとそのテストの固定値を同じ変更で更新し、`python3 -m unittest discover -s tests` が通る。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 対応する SPEC の ID |
|----|--------|------|--------|
| F01 | すべての pip 経路での準備済みファイル監査 | pip-audit を準備済みの requirements ファイルだけに対して起動する | FR1 |
| F02 | 固定値の抽出規則 | `name==version` の行だけを固定値として静的に抽出する | FR2 |
| F03 | 一部だけ固定できる入力・固定できない入力 | 固定値は監査し、除外があれば固定の `skip_reason` を付ける | FR3 |
| F04 | ロックファイル経路 | ロックファイル経路の挙動は変えず、フラグの取得元だけをレジストリに移す | FR4 |
| F05 | レジストリの対象形ごとの引数 | pip エントリの引数を対象形ごとの表で宣言する | FR5 |
| F06 | 固定のスキップトークン | F03 の `skip_reason` はスクリプトが書く固定トークンにする | FR6 |
| F07 | テストの固定値の同時更新 | 新しい形と矛盾するテストの固定値を同じ変更で更新する | FR7 |
| F08 | review-sca-axis FR1 / NFR2 との整合 | review-sca-axis FR1 の pip のコマンド形の置き換えと NFR2 の適用を SPEC に書く | FR8 |
| F09 | 他エコシステムの確認 | npm、cargo、go でレビュー対象のコードが実行されるかを確認し、SPEC に記録する | FR9 |

### 4.2 機能詳細

#### F01: すべての pip 経路での準備済みファイル監査

**説明**:
- pip の走査単位（`requirements.txt`、`pyproject.toml`、`poetry.lock`、`Pipfile.lock`）はすべて、pip-audit を準備済みの requirements ファイルだけに対して起動する。
- 準備済みファイルは正確な `name==version` の行だけを持ち、プロジェクトルートの外に作り、監査後に削除する。
- 起動には `--no-deps` と `--disable-pip` を付ける。
- pip-audit にレビュー対象プロジェクトのファイルやディレクトリを対象として渡さない。ディレクトリをそのまま渡す形（`pip-audit <dir>`）と、レビュー対象ファイルを直接渡す `-r <レビュー対象ファイル>` の形は組み立てない。

#### F02: 固定値の抽出規則

**説明**: 固定値はロックファイル経路と同じ厳密な規則で静的に抽出する。

**ビジネスルール**:
- `name==version` の行だけを固定値として数える。
- extras は落とす。
- 次の行は除外し、件数を数える。
    - 環境マーカー付きの行
    - ワイルドカードのバージョン（例: `==1.*`）。`_pip_pin_is_valid` 単体では受け付けるため、明示的に除外する。
    - `===`
    - その他の指定子・範囲指定
    - `-e` / `--editable`
    - URL、VCS 参照、ローカルパス
- `--hash` の値は無視する。
- requirements ファイルの `-r` による取り込みは、既存の閉じ込め済み取り込み走査を通して、プロジェクトルートの内側だけを辿る。
- `-c` の制約ファイルは開かない。
- 抽出した固定値はすべて `_pip_pin_is_valid` も通す。

#### F03: 一部だけ固定できる入力・固定できない入力

**ビジネスルール**:
- 固定できた項目は準備済みファイルを通して監査する。
- 1 件以上の項目が除外されたとき、その走査単位の結果に固定の `skip_reason` を付け、走査結果を `skipped: true` にする。監査した固定値の検出結果は残す。
- 監査できる項目が 1 件も無いとき、pip-audit を起動せず、固定の `skip_reason` だけを返す。
- 同じ名前の複数バージョンは、ロックファイル経路（`_group_pip_pins`）と同じく、別々の準備済みファイルに分け、それぞれ 1 回ずつ起動する。

#### F04: ロックファイル経路

**説明**:
- `poetry.lock` / `Pipfile.lock` の経路は、変換、宣言の確認、スキップ理由、除外項目の注記を変えない。
- `--no-deps` / `--disable-pip` のフラグは、`build_scan_job` に直接書かず、レジストリ（F05）から読む。

#### F05: レジストリの対象形ごとの引数

**説明**:
- `em-workflow/references/vuln-scanners.yaml` の pip エントリは、引数を対象形ごとの表で宣言する。
- pip の経路はすべて準備済みの requirements ファイルに集約するため、表に定義する形は 1 つにする。対象フラグは `-r`、引数は `[--no-deps, --disable-pip, --format, json]`。
- `build_scan_job` はフラグと引数をその形から取り、`--no-deps` も `--disable-pip` も直接書かない。
- `validate_ecosystem_entry` は、`args` と同じトークン規則で表を検証する。
- レジストリの先頭コメントに新しいフィールドを記述する。
- npm、cargo、go のエントリは変えない。

#### F06: 固定のスキップトークン

**ビジネスルール**:
- F03 のスキップ理由は、スクリプトが書く固定トークンにする。「一部の項目を除外した」と「監査できる項目が無い」で別のトークンにする。
- レビュー対象ファイルやツールの出力から取った文字列は、`skip_reason` にも要約にも入れない。

#### F07: テストの固定値の同時更新

**説明**: 新しい形と矛盾するテストの固定値を、同じ変更ですべて更新する。
- レジストリの文字列の固定値
- requirements / pyproject の argv の固定値
- ロックファイル経路だけのフラグの固定値（`test_no_deps_and_disable_pip_appear_only_on_lockfile_jobs` と `test_non_lockfile_jobs_ignore_a_prepared_file_and_carry_neither_flag` を含む）
- `build_command` の期待値
- 固定されていないマニフェストが完了することを期待しているフィクスチャ

**ビジネスルール**:
- `forbidden_tokens` は（`install`、`--fix`、`-o`、`--output`、`--require-hashes`）のまま変えない。

#### F08: review-sca-axis FR1 / NFR2 との整合

**説明**:
- 本機能の SPEC に、review-sca-axis FR1 が定める pip のコマンド形（`pip-audit --format json`）を本機能の FR1 / FR5 の形に置き換えることを書く。
- 本機能の SPEC に、review-sca-axis NFR2 が本機能にどう適用されるかを書く。
- `feature-docs/review-sca-axis/` 配下の文書は編集しない。

#### F09: 他エコシステムの確認

**説明**:
- npm（`npm audit`）、cargo（`cargo-audit`）、go（`govulncheck`）について、走査がレビュー対象プロジェクトのコードを実行するかを確認し、結果をエコシステムごとの事実として SPEC に記録する。
- go はパッケージの読み込み（`go list` / cgo の処理）とツールチェーンの切り替えも確認の対象に含める。
- 見つかったリスクは、それぞれ後続タスクとして起票する。
- 実装の範囲は pip だけとし、npm、cargo、go の挙動は変えない。

## 5. 非機能要件

### 5.2 セキュリティ要件
- レビュー対象コードの非実行（NFR1）: pip の経路は、レビュー対象プロジェクトのビルドバックエンド、`setup.py`、PEP 517 フックを一度も実行しない。pip-audit には、検証済みの `name==version` の行以外、レビュー対象ファイルの内容を渡さない。
- 読み取り専用の規律（NFR2）: 走査はインストール、ロックファイルの書き換え、プロジェクトルート内への書き込みを行わない。準備済みファイルはシステムの一時ディレクトリに `mkstemp`（所有者だけが読み書きでき、名前を予測できない）で作り、正常終了時も例外終了時も削除する。
- 既存の隔離の維持（NFR3）: `build_child_env`、pip の環境変数の固定（`PIP_CONFIG_FILE`、`PIP_INDEX_URL`）、許可リストに載った実行ファイルの絶対パス解決、argv 配列での起動は変えない。
- 信頼できない文字列（NFR4）: `skip_reason` と要約は固定トークンと件数だけを持つ。レビュー対象ファイルやツールの出力にあるパッケージ名、パス、アドバイザリの文章は入れない。

### 5.4 保守性要件
- 決定性（NFR5）: 同じ入力からは、同じ準備済みファイルの内容、同じ起動、同じ結果が得られる。
- テスト（NFR6）: 追加・更新するテストは標準ライブラリだけを使い（test/README.md）、実際の走査ツールを起動せず、`python3 -m unittest discover -s tests` が終了コード 0 で終わる。

## 9. 制約条件

### 9.1 技術的制約
- 実装の範囲は pip だけとする。npm、cargo、go の挙動は変えない。
- `build_child_env`、pip の環境変数の固定、実行ファイルの絶対パス解決、argv 配列での起動は変えない。
- テストは標準ライブラリだけを使い、実際の走査ツールを起動しない。

### 9.2 ビジネス上の制約
- `feature-docs/review-sca-axis/` 配下の文書は編集しない。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/sca-pip-no-build-exec/**`
- `test-docs/sca-pip-no-build-exec/**`

`feature-docs/sca-pip-no-build-exec/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-pip-no-build-exec/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/sca-pip-no-build-exec/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1（FR1, NFR1）: 変更された `requirements.txt` と `pyproject.toml`（ルートと入れ子）について、pip のジョブの argv が `[<pip-audit>, -r, <プロジェクトルート外の準備済みファイル>, --no-deps, --disable-pip, --format, json]` になる。レビュー対象プロジェクトのパスを含まず、ディレクトリをそのまま渡す形は組み立てられない。
- [ ] AC-2（FR2, NFR1）: 準備済みファイルは、規則が認める `name==version` の行だけをちょうど持つ。`-e .`、ローカルパス、URL、VCS 参照、マーカー、`==1.*`、`===`、範囲指定、extras を含むフィクスチャから、認められた行だけが extras を落として得られる。ルートの外を指す `-r` の取り込みは開かれず、`-c` のファイルは一度も開かれない。
- [ ] AC-3（FR3, FR6）: 固定値と除外項目が混在するとき、pip-audit は固定値に対して起動され、検出結果が残り、「項目を除外した」固定トークンが `skip_reason` に入り、`skipped` が true になる。監査できる項目が無いとき、走査ツールは起動されず、「監査できる項目が無い」固定トークンだけが返る。
- [ ] AC-4（FR3）: requirements ファイルとその取り込み先にまたがる同じ名前の 2 つのバージョンから、準備済みファイルが 2 つでき、2 回起動される。
- [ ] AC-5（FR4）: ロックファイル経路の結果（argv、スキップ理由、`pip_lockfile_entries_unpinnable` の注記）は本機能で変わらない。
- [ ] AC-6（FR5）: pip のレジストリエントリが対象形ごとの表を宣言する。`build_scan_job` は `--no-deps` / `--disable-pip` の文字列を含まない。表の中の不正なトークンは、`validate_ecosystem_entry` が固定の理由で拒否する。npm、cargo、go のエントリはバイト単位で同一のまま。
- [ ] AC-7（NFR2）: 正常終了でも例外終了でも、走査後に準備済みファイルが残らず、プロジェクトルート配下のファイルが作られたり変更されたりしていない。
- [ ] AC-8（NFR4）: `skip_reason` と要約に、フィクスチャのパッケージ名、パス、プロジェクトルートの文字列が含まれない。
- [ ] AC-9（FR7, NFR6）: `python3 -m unittest discover -s tests` が終了コード 0 で終わる。
- [ ] AC-10（FR8, FR9）: SPEC に、review-sca-axis FR1 の pip のコマンド形の置き換えと NFR2 の適用が書かれている。npm、cargo、go のエコシステムごとの確認結果と、見つかったリスクそれぞれの後続タスクへの参照も記録されている。`feature-docs/review-sca-axis/` 配下のファイルは変更されていない。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（AC-1）: 単体テスト。準備済みファイルを与えた `requirements.txt` / `pyproject.toml`（ルート、入れ子）の `build_scan_job` について、argv 全体と cwd を確かめる。
- [ ] TS-2（AC-2, AC-4）: 単体テスト。requirements / pyproject のフィクスチャに対する抽出関数について、認められた行、除外件数、グループ分けを確かめる。
- [ ] TS-3（AC-1, AC-2, AC-3）: argv と `-r` のファイルの内容を記録する代役の pip-audit を使った `run_scan` で、準備済みファイルの内容、フラグ、スキップトークン、`skipped`、残った検出結果を確かめる。
- [ ] TS-4（AC-3）: 監査できる項目が無い `run_scan` で、代役が一度も起動されないことを確かめる。
- [ ] TS-5（AC-5）: 既存のロックファイルのテスト群（`tests/test_sca_pip_lockfile_audit.py` と他所のロックファイルのケース）が、フラグの取得元が移った箇所以外は期待値を変えずに通る。
- [ ] TS-6（AC-6）: `tests/test_sca_scan_invocation.py` の制限付き部分集合パーサーを使った、対象形ごとの表のレジストリ文字列の固定値と検証のケース。
- [ ] TS-7（AC-7）: 正常完了後と、起動失敗を注入した後の両方で、準備済みファイルの後始末を確かめ、プロジェクトツリーのスナップショットを比べる。
- [ ] TS-8（AC-8）: フィクスチャに特徴的なパッケージ名とパスを入れた、信頼できない文字列のケース。
- [ ] TS-9（AC-9）: テスト一式の実行。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 走査単位 | pip の監査対象となる 1 つの入力ファイル（`requirements.txt`、`pyproject.toml`、`poetry.lock`、`Pipfile.lock`） |
| 準備済みファイル | 正確な `name==version` の行だけを持ち、プロジェクトルートの外に作り、監査後に削除する requirements ファイル |
| 固定値 | `name==version` の形で、F02 の規則を通った 1 項目 |

## 14. 確認事項

### 14.1 確認済み事項
- [x] デザインステップ: 実施しない（UI を持たない、プラグイン内部のスクリプト・レジストリ・テストの変更のため）。

### 14.2 未確認・保留事項
requirements-analyst が置いた前提。

- [ ] as-direct-names-unchanged（影響: 低）: 直接依存かどうかは、引き続きレビュー対象マニフェストが宣言する名前から既存の正規化処理を通して決める。ジョブのマニフェストのラベルはレビュー対象ファイルのままで、準備済みファイルにはしない。
- [ ] as-isolation-unchanged（影響: 低）: `build_child_env`、pip の環境変数の固定、実行ファイルの絶対パス解決、argv 配列での起動はそのまま（NFR3）。
- [ ] as-lockfile-note-unchanged（影響: 中）: ロックファイル経路は、除外項目を F03 の `skip_reason` ではなく、引き続き `pip_lockfile_entries_unpinnable` の注記で報告する。
- [ ] as-pyproject-pin-sources（影響: 中）: `pyproject.toml` は、直接依存の名前を解決する処理が読むのと同じ表から固定値を出す。`[project].dependencies` の各 PEP 508 文字列は F02 の規則を通す。`[tool.poetry.dependencies]` / `[tool.poetry.dev-dependencies]` の項目（`python` は無視）は、値が文字列 `'==<version>'` で、残りが規則を通るときだけ固定値として数える。それ以外の値（バージョンだけ、`^`、`~`、表）は除外する。動的な依存宣言や依存宣言が無い場合は、監査できる項目が 0 件になる。
- [ ] as-registry-key-names（影響: 低）: 対象形ごとの表の名前は `target_forms` とし、`target_flag` と `args` を持つ形 `prepared_requirements` を 1 つ置く。pip エントリの最上位の `args` / `target_flag` はこれに置き換える。
- [ ] as-skip-token-names（影響: 低）: F06 のトークンは `pip_manifest_entries_unpinnable`（一部の項目を除外した）と `pip_manifest_unpinnable`（監査できる項目が無い）とする。
