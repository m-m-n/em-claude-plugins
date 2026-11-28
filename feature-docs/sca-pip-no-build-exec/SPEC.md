# Feature: sca-pip-no-build-exec

## 概要

SCA 軸 2 の pip 経路を、レビュー対象プロジェクトのコードを実行しない形に改める。pip の走査単位はすべて、静的に抽出した `name==version` の行だけを持つ準備済みファイルに対して pip-audit を起動し、監査できない項目は固定の `skip_reason` で報告する。要件の詳細は `REQUIREMENTS.md` を参照する。

## 目的

- SCA 軸 2 の pip 経路は、レビュー対象プロジェクトのビルドバックエンド、`setup.py`、PEP 517 フックを一度も実行しない。
- pip の入力はすべて、静的に抽出した完全に固定されたパッケージ一覧として監査するか、機械で読める `skip_reason` を返す。
- レジストリとそのテストの固定値を同じ変更で更新し、`python3 -m unittest discover -s tests` が通る。

## 受け入れ基準

- [ ] AC-1（FR1, NFR1）: 変更された `requirements.txt` と `pyproject.toml`（ルートと入れ子）について、pip のジョブの argv が `[<pip-audit>, -r, <プロジェクトルート外の準備済みファイル>, --no-deps, --disable-pip, --format, json]` になる。レビュー対象プロジェクトのパスを含まず、ディレクトリをそのまま渡す形は組み立てられない。
- [ ] AC-2（FR2, NFR1）: 準備済みファイルは、規則が認める `name==version` の行だけをちょうど持つ。`-e .`、ローカルパス、URL、VCS 参照、マーカー、`==1.*`、`===`、範囲指定、extras を含むフィクスチャから、認められた行だけが extras を落として得られる。ルートの外を指す `-r` の取り込みは開かれず、`-c` のファイルは一度も開かれない。
- [ ] AC-3（FR3, FR6）: 固定値と除外項目が混在するとき、pip-audit は固定値に対して起動され、検出結果が残り、「項目を除外した」固定トークンが `skip_reason` に入り、`skipped` が true になる。監査できる項目が無いとき、走査ツールは起動されず、「監査できる項目が無い」固定トークンだけが返る。
- [ ] AC-4（FR3）: requirements ファイルとその取り込み先にまたがる同じ名前の 2 つのバージョンから、準備済みファイルが 2 つでき、2 回起動される。
- [ ] AC-5（FR4）: ロックファイル経路の結果（argv、スキップ理由、`pip_lockfile_entries_unpinnable` の注記）は本機能で変わらない。
- [ ] AC-6（FR5）: pip のレジストリエントリが対象形ごとの表を宣言する。`build_scan_job` は `--no-deps` / `--disable-pip` の文字列を含まない。表の中の不正なトークンは、`validate_ecosystem_entry` が固定の理由で拒否する。npm、cargo、go のエントリはバイト単位で同一のまま。
- [ ] AC-7（NFR2）: 正常終了でも例外終了でも、走査後に準備済みファイルが残らず、プロジェクトルート配下のファイルが作られたり変更されたりしていない。
- [ ] AC-8（NFR4）: `skip_reason` と要約に、フィクスチャのパッケージ名、パス、プロジェクトルートの文字列が含まれない。
- [ ] AC-9（FR7, NFR6）: `python3 -m unittest discover -s tests` が終了コード 0 で終わる。
- [ ] AC-10（FR8, FR9）: この SPEC に、review-sca-axis FR1 の pip のコマンド形の置き換えと NFR2 の適用が書かれている。npm、cargo、go のエコシステムごとの確認結果と、見つかったリスクそれぞれの後続タスクへの参照も記録されている。`feature-docs/review-sca-axis/` 配下のファイルは変更されていない。

## 技術要件

### 機能要件

- **FR1: すべての pip 経路での準備済みファイル監査** — pip の走査単位（`requirements.txt`、`pyproject.toml`、`poetry.lock`、`Pipfile.lock`）はすべて、pip-audit を準備済みの requirements ファイルだけに対して起動する。各ファイルは正確な `name==version` の行だけを持ち、プロジェクトルートの外に作り、監査後に削除する。起動には `--no-deps` と `--disable-pip` を付ける。pip-audit にレビュー対象プロジェクトのファイルやディレクトリを対象として渡さない。ディレクトリをそのまま渡す形（`pip-audit <dir>`）と、レビュー対象ファイルを直接渡す `-r <レビュー対象ファイル>` の形は組み立てない。
- **FR2: 固定値の抽出規則** — 固定値はロックファイル経路と同じ厳密な規則で静的に抽出する。
    - `name==version` の行だけを固定値として数える。extras は落とす。
    - 次の行は除外し、件数を数える: 環境マーカー付きの行、ワイルドカードのバージョン（例: `==1.*`。`_pip_pin_is_valid` 単体では受け付けるため、明示的に除外する）、`===`、その他の指定子・範囲指定、`-e` / `--editable`、URL、VCS 参照、ローカルパス。
    - `--hash` の値は無視する。
    - requirements ファイルの `-r` による取り込みは、既存の閉じ込め済み取り込み走査を通して、プロジェクトルートの内側だけを辿る。`-c` の制約ファイルは開かない。
    - 抽出した固定値はすべて `_pip_pin_is_valid` も通す。
- **FR3: 一部だけ固定できる入力・固定できない入力** — 固定できた項目は準備済みファイルを通して監査する。1 件以上の項目が除外されたとき、その走査単位の結果に固定の `skip_reason` を付け、走査結果を `skipped: true` にする。監査した固定値の検出結果は残す。監査できる項目が 1 件も無いとき、pip-audit を起動せず、固定の `skip_reason` だけを返す。同じ名前の複数バージョンは、ロックファイル経路（`_group_pip_pins`）と同じく、別々の準備済みファイルに分け、それぞれ 1 回ずつ起動する。
- **FR4: ロックファイル経路** — `poetry.lock` / `Pipfile.lock` の経路は、変換、宣言の確認、スキップ理由、除外項目の注記を変えない。`--no-deps` / `--disable-pip` のフラグは、`build_scan_job` に直接書かず、レジストリ（FR5）から読む。
- **FR5: レジストリの対象形ごとの引数** — `em-workflow/references/vuln-scanners.yaml` の pip エントリは、引数を対象形ごとの表で宣言する。pip の経路はすべて準備済みの requirements ファイルに集約するため、表に定義する形は 1 つにする。対象フラグは `-r`、引数は `[--no-deps, --disable-pip, --format, json]`。`build_scan_job` はフラグと引数をその形から取り、`--no-deps` も `--disable-pip` も直接書かない。`validate_ecosystem_entry` は、`args` と同じトークン規則で表を検証する。レジストリの先頭コメントに新しいフィールドを記述する。npm、cargo、go のエントリは変えない。
- **FR6: 固定のスキップトークン** — FR3 のスキップ理由は、スクリプトが書く固定トークンにする。「一部の項目を除外した」と「監査できる項目が無い」で別のトークンにする。レビュー対象ファイルやツールの出力から取った文字列は、`skip_reason` にも要約にも入れない。
- **FR7: テストの固定値の同時更新** — 新しい形と矛盾するテストの固定値を、同じ変更ですべて更新する。対象は、レジストリの文字列の固定値、requirements / pyproject の argv の固定値、ロックファイル経路だけのフラグの固定値（`test_no_deps_and_disable_pip_appear_only_on_lockfile_jobs` と `test_non_lockfile_jobs_ignore_a_prepared_file_and_carry_neither_flag` を含む）、`build_command` の期待値、固定されていないマニフェストが完了することを期待しているフィクスチャ。`forbidden_tokens` は（`install`、`--fix`、`-o`、`--output`、`--require-hashes`）のまま変えない。
- **FR8: review-sca-axis FR1 / NFR2 との整合** — この SPEC に、review-sca-axis FR1 が定める pip のコマンド形（`pip-audit --format json`）を本機能の FR1 / FR5 の形に置き換えることと、review-sca-axis NFR2 が本機能にどう適用されるかを書く（「review-sca-axis との整合」の節）。`feature-docs/review-sca-axis/` 配下の文書は編集しない。
- **FR9: 他エコシステムの確認** — npm（`npm audit`）、cargo（`cargo-audit`）、go（`govulncheck`）について、走査がレビュー対象プロジェクトのコードを実行するかを確認し、結果をエコシステムごとの事実としてこの SPEC に記録する（「他エコシステムの確認結果」の節）。go はパッケージの読み込み（`go list` / cgo の処理）とツールチェーンの切り替えも確認の対象に含める。見つかったリスクは、それぞれ後続タスクとして起票する。実装の範囲は pip だけとし、npm、cargo、go の挙動は変えない。

### 非機能要件

- **NFR1: レビュー対象コードの非実行** — pip の経路は、レビュー対象プロジェクトのビルドバックエンド、`setup.py`、PEP 517 フックを一度も実行しない。pip-audit には、検証済みの `name==version` の行以外、レビュー対象ファイルの内容を渡さない。
- **NFR2: 読み取り専用の規律** — 走査はインストール、ロックファイルの書き換え、プロジェクトルート内への書き込みを行わない。準備済みファイルはシステムの一時ディレクトリに `mkstemp`（所有者だけが読み書きでき、名前を予測できない）で作り、正常終了時も例外終了時も削除する。
- **NFR3: 既存の隔離の維持** — `build_child_env`、pip の環境変数の固定（`PIP_CONFIG_FILE`、`PIP_INDEX_URL`）、許可リストに載った実行ファイルの絶対パス解決、argv 配列での起動は変えない。
- **NFR4: 信頼できない文字列** — `skip_reason` と要約は固定トークンと件数だけを持つ。レビュー対象ファイルやツールの出力にあるパッケージ名、パス、アドバイザリの文章は入れない。
- **NFR5: 決定性** — 同じ入力からは、同じ準備済みファイルの内容、同じ起動、同じ結果が得られる。
- **NFR6: テスト** — 追加・更新するテストは標準ライブラリだけを使い（test/README.md）、実際の走査ツールを起動せず、`python3 -m unittest discover -s tests` が終了コード 0 で終わる。

## 実装方針

### データの流れ

```
レビュー対象の走査単位（requirements.txt / pyproject.toml / poetry.lock / Pipfile.lock）
  → 静的な固定値の抽出（FR2。ロックファイルは既存の変換、FR4）
  → 同じ名前の複数バージョンのグループ分け（_group_pip_pins、FR3）
  → 準備済みファイルの作成（システムの一時ディレクトリ、mkstemp、NFR2）
  → pip-audit -r <準備済みファイル> --no-deps --disable-pip --format json（FR1 / FR5）
  → 結果の集約（検出結果、固定の skip_reason、skipped、FR3 / FR6）
  → 準備済みファイルの削除（正常終了時・例外終了時、NFR2）
```

監査できる項目が 1 件も無い走査単位は、pip-audit を起動せず、固定の `skip_reason` だけを返す（FR3）。

### レジストリの形

`em-workflow/references/vuln-scanners.yaml` の pip エントリは、最上位の `args` / `target_flag` を対象形ごとの表 `target_forms` に置き換え、形 `prepared_requirements` を 1 つだけ持つ（前提 as-registry-key-names、FR5）。

```yaml
target_forms:
  prepared_requirements:
    target_flag: -r
    args: [--no-deps, --disable-pip, --format, json]
```

### pyproject.toml の固定値の取得元

前提 as-pyproject-pin-sources に従う。

- `pyproject.toml` は、直接依存の名前を解決する処理が読むのと同じ表から固定値を出す。
- `[project].dependencies` の各 PEP 508 文字列は FR2 の規則を通す。
- `[tool.poetry.dependencies]` / `[tool.poetry.dev-dependencies]` の項目（`python` は無視）は、値が文字列 `'==<version>'` で、残りが規則を通るときだけ固定値として数える。それ以外の値（バージョンだけ、`^`、`~`、表）は除外する。
- 動的な依存宣言や依存宣言が無い場合は、監査できる項目が 0 件になる。

### スキップトークン

前提 as-skip-token-names に従う（FR6）。

| トークン | 意味 |
|----------|------|
| `pip_manifest_entries_unpinnable` | 一部の項目を除外した |
| `pip_manifest_unpinnable` | 監査できる項目が無い |

ロックファイル経路は、除外項目を引き続き `pip_lockfile_entries_unpinnable` の注記で報告し、上の `skip_reason` は使わない（前提 as-lockfile-note-unchanged、FR4）。

### 直接依存の判定

直接依存かどうかは、引き続きレビュー対象マニフェストが宣言する名前から既存の正規化処理を通して決める。ジョブのマニフェストのラベルはレビュー対象ファイルのままで、準備済みファイルにはしない（前提 as-direct-names-unchanged）。

### 依存関係

**内部の依存:**
- `build_scan_job`: 対象形の表からフラグと引数を取る（FR5）。
- `validate_ecosystem_entry`: 対象形の表を `args` と同じトークン規則で検証する（FR5）。
- `_pip_pin_is_valid`: 抽出した固定値の検証（FR2）。
- `_group_pip_pins`: 同じ名前の複数バージョンの分割（FR3）。
- 既存の閉じ込め済み取り込み走査: `-r` の取り込みをプロジェクトルートの内側だけ辿る（FR2）。
- `build_child_env`、pip の環境変数の固定、実行ファイルの絶対パス解決、argv 配列での起動: 変えない（NFR3、前提 as-isolation-unchanged）。

**外部の依存:**
- pip-audit: pip の走査ツール。

## review-sca-axis との整合

- **review-sca-axis FR1 の置き換え:** review-sca-axis FR1 が定める pip のコマンド形 `pip-audit --format json` を、本機能では `pip-audit -r <準備済みファイル> --no-deps --disable-pip --format json`（FR1 / FR5）に置き換える。npm、cargo、go のコマンド形は変えない。
- **review-sca-axis NFR2 の適用:** 本機能の pip 経路では、review-sca-axis NFR2 を本 SPEC の NFR2 の形で適用する。走査はインストール、ロックファイルの書き換え、プロジェクトルート内への書き込みを行わない。走査中に書くのは準備済みファイルだけで、システムの一時ディレクトリに `mkstemp` で作り、正常終了時も例外終了時も削除する。
- `feature-docs/review-sca-axis/` 配下の文書は編集しない。

## 他エコシステムの確認結果

FR9 の確認結果を、エコシステムごとの事実としてこの節に記録する。見つかったリスクは、それぞれ後続タスクとして起票し、その参照をこの節に書く。npm、cargo、go の挙動は本機能では変えない。

| エコシステム | 走査ツール | 確認の対象 | 確認結果 | 後続タスク |
|--------------|------------|------------|----------|------------|
| npm | `npm audit` | 走査がレビュー対象プロジェクトのコードを実行するか | 未記録 | - |
| cargo | `cargo-audit` | 走査がレビュー対象プロジェクトのコードを実行するか | 未記録 | - |
| go | `govulncheck` | 走査がレビュー対象プロジェクトのコードを実行するか。パッケージの読み込み（`go list` / cgo の処理）とツールチェーンの切り替えを含む | 未記録 | - |

## 宣言された変更集合

フィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、フィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリをデフォルトで宣言する。

- `feature-docs/sca-pip-no-build-exec/**`
- `test-docs/sca-pip-no-build-exec/**`

`feature-docs/sca-pip-no-build-exec/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照する（引用のみ、ルールは再掲しない）。

`test-docs/sca-pip-no-build-exec/**` に含まれるもの: タスクごとのテスト記録 `test-docs/sca-pip-no-build-exec/{T}.tests.yaml`。生成主体は `implement-phase.md` を参照する（引用のみ、ルールは再掲しない）。

この 2 つのデフォルトエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的で明示的な絞り込みである。

この宣言はスーパーセット（SUPERSET）の主張であり、検証時に観測された実際の変更集合は、宣言された集合に含まれる（CONTAINED IN）必要がある。等しい必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。宣言されたパスが実際に生成されなくても違反にはならない。

## テストシナリオ

### シナリオ一覧

- [ ] TS-1: 単体テスト。準備済みファイルを与えた `requirements.txt` / `pyproject.toml`（ルート、入れ子）の `build_scan_job` について、argv 全体と cwd を確かめる。（AC-1）
- [ ] TS-2: 単体テスト。requirements / pyproject のフィクスチャに対する抽出関数について、認められた行、除外件数、グループ分けを確かめる。（AC-2, AC-4）
- [ ] TS-3: argv と `-r` のファイルの内容を記録する代役の pip-audit を使った `run_scan` で、準備済みファイルの内容、フラグ、スキップトークン、`skipped`、残った検出結果を確かめる。（AC-1, AC-2, AC-3）
- [ ] TS-4: 監査できる項目が無い `run_scan` で、代役が一度も起動されないことを確かめる。（AC-3）
- [ ] TS-5: 既存のロックファイルのテスト群（`tests/test_sca_pip_lockfile_audit.py` と他所のロックファイルのケース）が、フラグの取得元が移った箇所以外は期待値を変えずに通る。（AC-5）
- [ ] TS-6: `tests/test_sca_scan_invocation.py` の制限付き部分集合パーサーを使った、対象形ごとの表のレジストリ文字列の固定値と検証のケース。（AC-6）
- [ ] TS-7: 正常完了後と、起動失敗を注入した後の両方で、準備済みファイルの後始末を確かめ、プロジェクトツリーのスナップショットを比べる。（AC-7）
- [ ] TS-8: フィクスチャに特徴的なパッケージ名とパスを入れた、信頼できない文字列のケース。（AC-8）
- [ ] TS-9: テスト一式の実行。（AC-9）

### E2E テスト

**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

## セキュリティ上の考慮

- **レビュー対象コードの非実行:** pip-audit は準備済みファイルだけを対象に `--no-deps` と `--disable-pip` を付けて起動し、レビュー対象のファイルやディレクトリを対象として渡さない（FR1、NFR1）。
- **入力検証:** 準備済みファイルに入るのは FR2 の規則と `_pip_pin_is_valid` を通った `name==version` の行だけ（FR2、NFR1）。
- **データ保護:** 準備済みファイルはシステムの一時ディレクトリに `mkstemp` で作り、正常終了時も例外終了時も削除する。プロジェクトルート内には書き込まない（NFR2）。
- **信頼できない文字列:** `skip_reason` と要約は固定トークンと件数だけを持つ（FR6、NFR4）。
- **既存の隔離:** `build_child_env`、pip の環境変数の固定、実行ファイルの絶対パス解決、argv 配列での起動は変えない（NFR3）。

## 成功基準

- [ ] すべての機能要件が実装され、テストされている
- [ ] すべてのテストシナリオが通る
- [ ] セキュリティ要件を満たす
- [ ] AC-1 から AC-10 を満たす
- [ ] `python3 -m unittest discover -s tests` が終了コード 0 で終わる

## 未解決事項

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## 前提

requirements-analyst が置いた前提。

- **as-direct-names-unchanged**（影響: 低）: 直接依存かどうかは、引き続きレビュー対象マニフェストが宣言する名前から既存の正規化処理を通して決める。ジョブのマニフェストのラベルはレビュー対象ファイルのままで、準備済みファイルにはしない。
- **as-isolation-unchanged**（影響: 低）: `build_child_env`、pip の環境変数の固定、実行ファイルの絶対パス解決、argv 配列での起動はそのまま（NFR3）。
- **as-lockfile-note-unchanged**（影響: 中）: ロックファイル経路は、除外項目を FR3 の `skip_reason` ではなく、引き続き `pip_lockfile_entries_unpinnable` の注記で報告する。
- **as-pyproject-pin-sources**（影響: 中）: 「pyproject.toml の固定値の取得元」の節のとおり。
- **as-registry-key-names**（影響: 低）: 対象形ごとの表の名前は `target_forms` とし、`target_flag` と `args` を持つ形 `prepared_requirements` を 1 つ置く。pip エントリの最上位の `args` / `target_flag` はこれに置き換える。
- **as-skip-token-names**（影響: 低）: FR6 のトークンは `pip_manifest_entries_unpinnable`（一部の項目を除外した）と `pip_manifest_unpinnable`（監査できる項目が無い）とする。

## 参照

- 要件定義書: `feature-docs/sca-pip-no-build-exec/REQUIREMENTS.md`
- 走査ツールのレジストリ: `em-workflow/references/vuln-scanners.yaml`
- 置き換え・適用の対象: review-sca-axis FR1 / NFR2（`feature-docs/review-sca-axis/`）
