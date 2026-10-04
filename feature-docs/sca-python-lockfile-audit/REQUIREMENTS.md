---
title: "sca-python-lockfile-audit"
created_date: 2026-10-04
status: draft
---

# sca-python-lockfile-audit - 要件定義書

## 1. 概要

### 1.1 背景
記載なし。

### 1.2 目的
- SCA 軸が、変更された poetry.lock / Pipfile.lock にピン留めされた脆弱なバージョンを finding として報告する。
- 変換できない lockfile と、直接依存の宣言ファイルを解決できない lockfile について、機械可読で安定した skip_reason を返す。

### 1.3 スコープ
**対象**:
- pip の lockfile（poetry.lock / Pipfile.lock）の監査（FR1〜FR12）

**対象外**:
- npm / cargo / go の監査対象の選び方（FR1）
- 変更された pip プロジェクトが複数ある場合（A8。後続タスクとして起票する）
- uv.lock / pdm.lock / pylock.toml（A10。今と同じく選ばれない）

## 2. ビジネス要件

### 2.1 ビジネス目標
- SCA 軸が、変更された poetry.lock / Pipfile.lock にピン留めされた脆弱なバージョンを finding として報告する。
- 変換できない lockfile と、直接依存の宣言ファイルを解決できない lockfile について、機械可読で安定した skip_reason を返す。

### 2.2 対象ユーザー
記載なし。

### 2.3 期待される効果
記載なし。

## 3. ユースケース

該当なし（UI の無い CLI スクリプトとテストの変更）。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | pip の監査対象に lockfile を優先する | resolved |
| FR2 | lockfile のピンを変換する | resolved |
| FR3 | lockfile ジョブの呼び出し形 | resolved |
| FR4 | 同じ名前でバージョンが違うピンの分割 | resolved |
| FR5 | 変換できない lockfile | resolved |
| FR6 | ピンに変換できないエントリ | resolved |
| FR7 | 直接依存の判定先 | resolved |
| FR8 | 直接依存の宣言ファイルが無いとき | resolved |
| FR9 | 名前の正規化 | resolved |
| FR10 | lockfile 由来の finding の中身 | resolved |
| FR11 | 一時ファイルに書く内容の検証 | resolved |
| FR12 | skip_reason の合成 | resolved |

### 4.2 機能詳細

#### FR1: pip の監査対象に lockfile を優先する

変更ファイルに pip の lockfile(poetry.lock / Pipfile.lock)が 1 つ以上あるときは、pip のマニフェスト(pyproject.toml / requirements.txt)より lockfile を優先して監査対象にする。lockfile が複数あるときは、changed_files の順で最初のものを選ぶ。pip のジョブは 1 回のスキャンにつき 1 対象のまま。npm / cargo / go の選び方は変えない。

#### FR2: lockfile のピンを変換する

選ばれた lockfile のエントリを name==version の行に変換する。poetry.lock はトップレベルの `[[package]]` の name / version、Pipfile.lock は default と develop の各エントリの名前と version(`"==X"` の形)を使う。同じ name==version は 1 行にまとめる。ハッシュは出力しない。

#### FR3: lockfile ジョブの呼び出し形

lockfile 由来の pip ジョブの argv は `[<pip-audit の絶対パス>, '-r', <一時 requirements ファイル>, '--no-deps', '--disable-pip', '--format', 'json']` にする。`'--no-deps'` と `'--disable-pip'` は、スクリプトが lockfile 由来のジョブにだけ付ける。vuln-scanners.yaml の pip エントリ(manifests / executable / args / target_flag / severity_map / threshold)は変えない。requirements.txt と pyproject.toml のジョブの argv も変えない。

#### FR4: 同じ名前でバージョンが違うピンの分割

1 つの lockfile に、同じ名前(PEP 503 で正規化した名前)で違うバージョンのピンがある場合は、どの一時 requirements ファイルにも同じ名前が 1 回しか出ないように複数のファイルに分ける。ファイルごとに pip-audit を 1 回実行し、その findings を 1 つの結果にまとめる。

#### FR5: 変換できない lockfile

選ばれた lockfile が、解析できない、想定した構造が無い(poetry.lock にトップレベルの package 配列が無い、Pipfile.lock に default も develop も無い)、変換できるエントリが 0 件、のいずれかに当てはまる場合、pip は skip_reason `'pip_lockfile_unconvertible'` で not_completed になる。pip-audit は実行しない。マニフェスト監査やディレクトリ監査に切り替えない。

#### FR6: ピンに変換できないエントリ

次のエントリは変換から外す。レジストリ以外が出どころのもの(poetry.lock の source.type が git / directory / file / url。Pipfile.lock で git / path / file / editable を持つもの)、version が無いもの、または `"==X"` の形でないもの、名前かバージョンが検証を通らないもの(FR11)。それ以外のピンは監査する。外したエントリの件数は、summary に件数だけの固定注記として載せる(注記名 `'pip_lockfile_entries_unpinnable'`。形式: `' N pip lockfile entr(y|ies) not auditable (pip_lockfile_entries_unpinnable).'`)。これらのエントリを理由に skipped を true にはしない。

#### FR7: 直接依存の判定先

poetry.lock の直接依存は、同じ階層の pyproject.toml から既存の解析で判定する。Pipfile.lock の直接依存は、同じ階層の Pipfile の `[packages]` と `[dev-packages]` のキーから判定する。`_pip_manifest_candidate` は Pipfile.lock に対して Pipfile を返す。

#### FR8: 直接依存の宣言ファイルが無いとき

FR7 の宣言ファイルが、存在しない、読めない、解析できない、project root の外に解決される、のいずれかの場合、pip は skip_reason `'pip_direct_manifest_not_found'` で not_completed になる。pip-audit は実行しない。

#### FR9: 名前の正規化

直接依存の判定では、宣言側と pip-audit 出力側の両方のパッケージ名を PEP 503 で正規化してから比較する(小文字にし、`'-'` / `'_'` / `'.'` の連続を `'-'` 1 つにする)。

#### FR10: lockfile 由来の finding の中身

lockfile 由来の finding の file は、その lockfile のプロジェクト相対パスにする。affected_range は pip-audit が報告したピンのバージョンにする。

#### FR11: 一時ファイルに書く内容の検証

一時 requirements ファイルに書くのは、名前が `^[A-Za-z0-9][A-Za-z0-9._-]*$` に、バージョンが空白・改行・`';'`・`'#'` を含まず `'-'` で始まらない値に一致する行だけ。一致しないエントリは FR6 の扱いにする。

#### FR12: skip_reason の合成

pip_lockfile_unconvertible と pip_direct_manifest_not_found は、既存の pip_tool_not_found などと同じ経路で skip_reasons に入る。他のエコシステムの理由とは、ソートしたうえで `'+'` でつなぐ。完了した他のエコシステムの findings は残す。

**エラーケース**:
| skip_reason / 注記 | 条件 | 対応 |
|--------------------|------|------|
| `pip_lockfile_unconvertible` | FR5 の条件 | pip は not_completed。pip-audit は実行しない |
| `pip_direct_manifest_not_found` | FR8 の条件 | pip は not_completed。pip-audit は実行しない |
| `pip_lockfile_entries_unpinnable`（注記） | FR6 で外したエントリがある | summary に件数注記を載せる。skipped は true にしない |

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | スキャンは project root 配下のファイルを作らない、変えない、消さない。一時 requirements ファイルは project root の外に作り、スキャンが終わるまでに削除する(例外で終わった場合も削除する)。 |
| NFR2 | build_scan_job は純粋関数のまま残す(ファイルの読み書きもプロセスの起動もしない)。lockfile の読み取りと一時ファイルの作成は別の段階で行う。 |
| NFR3 | 同じ入力からは、バイト単位で同じ結果 JSON を返す。一時ファイルのパスは結果に含めない。FR4 で分割したときは、まとめる順序を固定する。 |
| NFR4 | lockfile と Pipfile の解析には標準ライブラリだけを使う(tomllib / json)。スクリプトに新しい実行時依存を足さない。 |
| NFR5 | テストは標準ライブラリだけを import する。実際の pip-audit もネットワークも使わず、PATH 上のスタブスキャナで検証する。 |
| NFR6 | 子プロセスの環境変数のピン(PIP_CONFIG_FILE / PIP_INDEX_URL)、ALLOWED_EXECUTABLES、ECOSYSTEM_LOCKFILES は変えない。 |
| NFR7 | プラグインの version は変更しない。 |

## 6. UI/UX要件

該当なし（UI の無い CLI スクリプトとテストの変更）。

## 7. データ要件

該当なし。

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| pip-audit | FR3 の argv で起動する | 一時 requirements ファイル / JSON 出力 |

### 8.2 API仕様要件
該当なし。

## 9. 制約条件

### 9.1 技術的制約
- NFR2、NFR4、NFR6、NFR7 を参照。

### 9.2 ビジネス上の制約
記載なし。

### 9.3 スケジュール制約
記載なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/sca-python-lockfile-audit/**`
- `test-docs/sca-python-lockfile-audit/**`

`feature-docs/sca-python-lockfile-audit/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-python-lockfile-audit/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/sca-python-lockfile-audit/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/sca-python-lockfile-audit/` ディレクトリを生成しないが、宣言された `test-docs/sca-python-lockfile-audit/**` は依然として正しい。

## 10. 想定される課題とリスク

記載なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR2, FR3, FR10）: 脆弱なバージョンをピンした poetry.lock だけを changed_files に入れ、同じ階層の pyproject.toml はそのパッケージを修正済みバージョンも許容する範囲で宣言する。この状態で scan を実行すると、そのパッケージの finding が 1 件以上出る。skipped は false、finding の file は poetry.lock。
- [ ] AC2（FR2, FR7）: AC1 と同じことを Pipfile.lock と Pipfile で行い、finding が出る。
- [ ] AC3（FR1）: pyproject.toml と poetry.lock を同時に changed_files に入れると、lockfile 由来のジョブ(-r <一時ファイル> --no-deps --disable-pip)が 1 つだけ作られる。
- [ ] AC4（FR3）: requirements.txt と pyproject.toml のジョブの argv、および vuln-scanners.yaml の pip エントリは、変更前と同じ。
- [ ] AC5（FR5）: 解析できない lockfile、構造の無い lockfile、変換できるエントリが 0 件の lockfile では、skipped: true、skip_reason `'pip_lockfile_unconvertible'` になり、pip-audit は起動されない。
- [ ] AC6（FR8）: 同じ階層に pyproject.toml / Pipfile が無い lockfile では、skipped: true、skip_reason `'pip_direct_manifest_not_found'` になり、pip-audit は起動されない。
- [ ] AC7（FR6, FR11）: git / path が出どころのエントリと、検証を通らない名前のエントリを含む lockfile では、残りのピンが監査される。summary に `'pip_lockfile_entries_unpinnable'` の件数注記が出て、skipped は false。一時ファイルには検証を通った行しか書かれない。
- [ ] AC8（FR4）: 同じ名前で違うバージョンのピンが 2 つある lockfile では、pip-audit が 2 回起動され、それぞれの一時ファイルにその名前が 1 回ずつだけ出る。両方のバージョンの finding が 1 つの結果に入る。同じ name==version が重なった場合は、1 行だけ書かれる。
- [ ] AC9（FR9）: 宣言側が 'Django'、lockfile と pip-audit の出力が 'django' の場合、直接依存として判定され、finding が出る。
- [ ] AC10（NFR1）: スキャンの前後で project root の git status --porcelain が同じで、一時ファイルが残らない。
- [ ] AC11（NFR5）: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` がどちらも成功する。

### 11.2 KPI
該当なし。

## 12. テストシナリオ

- [ ] TS1（AC1）: 一時ディレクトリに project(poetry.lock に脆弱なピン、pyproject.toml に範囲宣言)を置く。PATH 上のスタブ pip-audit は、受け取った -r ファイルの中身を検査して脆弱性入りの JSON を返す。run_scan の結果に finding が出ることと、skipped が false であることを確かめる。
- [ ] TS2（AC2）: TS1 と同じことを Pipfile.lock(default / develop)と Pipfile(`[packages]`)で行う。
- [ ] TS3（AC3, AC4）: lockfile 由来のジョブの argv を検証する。`'--no-deps'` と `'--disable-pip'` は lockfile ジョブにだけあることを確かめ、requirements.txt / pyproject.toml のジョブには無いことも確かめる。test_sca_scan_invocation.py:243-248 を置き換え、258-264 の禁止トークン検査を lockfile ジョブ以外に限る。
- [ ] TS4（AC5）: 壊れた TOML の poetry.lock、壊れた JSON の Pipfile.lock、package 配列の無い poetry.lock、全エントリが git の lockfile で、それぞれ pip_lockfile_unconvertible になることを確かめる。スタブの起動記録が残らないことも確かめる。
- [ ] TS5（AC6）: 同じ階層に宣言ファイルが無い lockfile、宣言ファイルが壊れた lockfile で、pip_direct_manifest_not_found になり、スタブが起動されないことを確かめる。
- [ ] TS6（AC7）: git / path のエントリと、`'-r evil'` のような名前を含む lockfile で、件数注記と skipped: false を確かめる。一時ファイルの中身をスタブ側で記録し、検証を通った行だけが書かれたことも確かめる。
- [ ] TS7（AC8）: 同じ名前で 2 バージョンのピンがある lockfile で、スタブが 2 回起動され、各ファイルにその名前が 1 回ずつ出ることを確かめる。findings が両方そろうこと、同じ入力を 2 回スキャンして結果が同じになることも確かめる。
- [ ] TS8（AC9）: 'Django' と 'django' の表記ゆれで、直接依存と判定されることを確かめる。
- [ ] TS9（AC10）: git init した project で lockfile をスキャンし、前後の git status --porcelain が同じであること、一時ファイルが消えていることを確かめる。
- [ ] TS10（AC4）: test_sca_scan_normalization.py:187-192 と 295-312 の既存の固定(pip の manifests と args)が変更なしで通ることを確かめる。

## 13. 用語定義

記載なし。

## 14. 確認事項

### 14.1 確認済み事項
- [x] 未解決（status: tbd）の要件: なし（FR1〜FR12 はすべて resolved）
- [x] デザインステップ: skipped（UI の無い CLI スクリプトとテストの変更）

### 14.2 未確認・保留事項

以下は前提（いずれも可逆）として置いたもの。

- [ ] A1: 一時 requirements ファイルは tempfile でシステムの一時ディレクトリに作る。
- [ ] A2: lockfile の変換は build_scan_job の外(run_scan / build_scan_jobs 側)で行う。build_scan_job は変換済みの対象を受け取る。
- [ ] A3: lockfile の全グループのピンを変換対象にする。Pipfile.lock は default と develop の両方、poetry.lock はグループや category で絞らない。
- [ ] A4: FR8 の宣言ファイルの確認は pip-audit を起動する前に行い、失敗したら起動しない。
- [ ] A5: FR4 の分割では、名前ごとのバージョンをソートし、k 番目のバージョンを k 番目のファイルに入れる。findings はファイルの順にまとめる。
- [ ] A6: FR4 で分割した実行の 1 つが not_completed になった場合、その理由(重複は除く)を pip の skip_reason にする。完了した実行の findings は残す。
- [ ] A7: pyproject.toml の既存の直接依存の解析(_pip_pyproject_direct_names)は変えない。
- [ ] A8: 変更された pip プロジェクトが複数ある場合は範囲外とし、後続タスクとして起票する。
- [ ] A9: test-docs/review-sca-axis/task0010.tests.yaml は過去タスクの記録として書き換えない。
- [ ] A10: uv.lock / pdm.lock / pylock.toml は今と同じく選ばれない。

## 15. 参考資料

記載なし。
