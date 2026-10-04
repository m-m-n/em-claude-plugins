# Feature: sca-python-lockfile-audit

## Overview

SCA 軸の pip 監査で、変更された poetry.lock / Pipfile.lock を監査対象にする。lockfile のピンを name==version の行に変換して pip-audit に渡し、変換できない lockfile と直接依存の宣言ファイルを解決できない lockfile には固定の skip_reason を返す。

要件の原文は [REQUIREMENTS.md](REQUIREMENTS.md) にある。

## Objectives

- SCA 軸が、変更された poetry.lock / Pipfile.lock にピン留めされた脆弱なバージョンを finding として報告する。
- 変換できない lockfile と、直接依存の宣言ファイルを解決できない lockfile について、機械可読で安定した skip_reason を返す。

## Acceptance Criteria

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

## Technical Requirements

### Functional Requirements

- **FR1:** pip の監査対象に lockfile を優先する — 変更ファイルに pip の lockfile(poetry.lock / Pipfile.lock)が 1 つ以上あるときは、pip のマニフェスト(pyproject.toml / requirements.txt)より lockfile を優先して監査対象にする。lockfile が複数あるときは、changed_files の順で最初のものを選ぶ。pip のジョブは 1 回のスキャンにつき 1 対象のまま。npm / cargo / go の選び方は変えない。
- **FR2:** lockfile のピンを変換する — 選ばれた lockfile のエントリを name==version の行に変換する。poetry.lock はトップレベルの `[[package]]` の name / version、Pipfile.lock は default と develop の各エントリの名前と version(`"==X"` の形)を使う。同じ name==version は 1 行にまとめる。ハッシュは出力しない。
- **FR3:** lockfile ジョブの呼び出し形 — lockfile 由来の pip ジョブの argv は `[<pip-audit の絶対パス>, '-r', <一時 requirements ファイル>, '--no-deps', '--disable-pip', '--format', 'json']` にする。`'--no-deps'` と `'--disable-pip'` は、スクリプトが lockfile 由来のジョブにだけ付ける。vuln-scanners.yaml の pip エントリ(manifests / executable / args / target_flag / severity_map / threshold)は変えない。requirements.txt と pyproject.toml のジョブの argv も変えない。
- **FR4:** 同じ名前でバージョンが違うピンの分割 — 1 つの lockfile に、同じ名前(PEP 503 で正規化した名前)で違うバージョンのピンがある場合は、どの一時 requirements ファイルにも同じ名前が 1 回しか出ないように複数のファイルに分ける。ファイルごとに pip-audit を 1 回実行し、その findings を 1 つの結果にまとめる。
- **FR5:** 変換できない lockfile — 選ばれた lockfile が、解析できない、想定した構造が無い(poetry.lock にトップレベルの package 配列が無い、Pipfile.lock に default も develop も無い)、変換できるエントリが 0 件、のいずれかに当てはまる場合、pip は skip_reason `'pip_lockfile_unconvertible'` で not_completed になる。pip-audit は実行しない。マニフェスト監査やディレクトリ監査に切り替えない。
- **FR6:** ピンに変換できないエントリ — 次のエントリは変換から外す。レジストリ以外が出どころのもの(poetry.lock の source.type が git / directory / file / url。Pipfile.lock で git / path / file / editable を持つもの)、version が無いもの、または `"==X"` の形でないもの、名前かバージョンが検証を通らないもの(FR11)。それ以外のピンは監査する。外したエントリの件数は、summary に件数だけの固定注記として載せる(注記名 `'pip_lockfile_entries_unpinnable'`。形式: `' N pip lockfile entr(y|ies) not auditable (pip_lockfile_entries_unpinnable).'`)。これらのエントリを理由に skipped を true にはしない。
- **FR7:** 直接依存の判定先 — poetry.lock の直接依存は、同じ階層の pyproject.toml から既存の解析で判定する。Pipfile.lock の直接依存は、同じ階層の Pipfile の `[packages]` と `[dev-packages]` のキーから判定する。`_pip_manifest_candidate` は Pipfile.lock に対して Pipfile を返す。
- **FR8:** 直接依存の宣言ファイルが無いとき — FR7 の宣言ファイルが、存在しない、読めない、解析できない、project root の外に解決される、のいずれかの場合、pip は skip_reason `'pip_direct_manifest_not_found'` で not_completed になる。pip-audit は実行しない。
- **FR9:** 名前の正規化 — 直接依存の判定では、宣言側と pip-audit 出力側の両方のパッケージ名を PEP 503 で正規化してから比較する(小文字にし、`'-'` / `'_'` / `'.'` の連続を `'-'` 1 つにする)。
- **FR10:** lockfile 由来の finding の中身 — lockfile 由来の finding の file は、その lockfile のプロジェクト相対パスにする。affected_range は pip-audit が報告したピンのバージョンにする。
- **FR11:** 一時ファイルに書く内容の検証 — 一時 requirements ファイルに書くのは、名前が `^[A-Za-z0-9][A-Za-z0-9._-]*$` に、バージョンが空白・改行・`';'`・`'#'` を含まず `'-'` で始まらない値に一致する行だけ。一致しないエントリは FR6 の扱いにする。
- **FR12:** skip_reason の合成 — pip_lockfile_unconvertible と pip_direct_manifest_not_found は、既存の pip_tool_not_found などと同じ経路で skip_reasons に入る。他のエコシステムの理由とは、ソートしたうえで `'+'` でつなぐ。完了した他のエコシステムの findings は残す。

### Non-Functional Requirements

- **NFR1 - project root を変更しない:** スキャンは project root 配下のファイルを作らない、変えない、消さない。一時 requirements ファイルは project root の外に作り、スキャンが終わるまでに削除する(例外で終わった場合も削除する)。
- **NFR2 - build_scan_job の純粋性:** build_scan_job は純粋関数のまま残す(ファイルの読み書きもプロセスの起動もしない)。lockfile の読み取りと一時ファイルの作成は別の段階で行う。
- **NFR3 - 結果の決定性:** 同じ入力からは、バイト単位で同じ結果 JSON を返す。一時ファイルのパスは結果に含めない。FR4 で分割したときは、まとめる順序を固定する。
- **NFR4 - 標準ライブラリだけで解析する:** lockfile と Pipfile の解析には標準ライブラリだけを使う(tomllib / json)。スクリプトに新しい実行時依存を足さない。
- **NFR5 - テストの依存:** テストは標準ライブラリだけを import する。実際の pip-audit もネットワークも使わず、PATH 上のスタブスキャナで検証する。
- **NFR6 - 既存のピンと許可リストを変えない:** 子プロセスの環境変数のピン(PIP_CONFIG_FILE / PIP_INDEX_URL)、ALLOWED_EXECUTABLES、ECOSYSTEM_LOCKFILES は変えない。
- **NFR7 - version を変更しない:** プラグインの version は変更しない。

## Assumptions

いずれも可逆な前提。

- **A1:** 一時 requirements ファイルは tempfile でシステムの一時ディレクトリに作る。
- **A2:** lockfile の変換は build_scan_job の外(run_scan / build_scan_jobs 側)で行う。build_scan_job は変換済みの対象を受け取る。
- **A3:** lockfile の全グループのピンを変換対象にする。Pipfile.lock は default と develop の両方、poetry.lock はグループや category で絞らない。
- **A4:** FR8 の宣言ファイルの確認は pip-audit を起動する前に行い、失敗したら起動しない。
- **A5:** FR4 の分割では、名前ごとのバージョンをソートし、k 番目のバージョンを k 番目のファイルに入れる。findings はファイルの順にまとめる。
- **A6:** FR4 で分割した実行の 1 つが not_completed になった場合、その理由(重複は除く)を pip の skip_reason にする。完了した実行の findings は残す。
- **A7:** pyproject.toml の既存の直接依存の解析(_pip_pyproject_direct_names)は変えない。
- **A8:** 変更された pip プロジェクトが複数ある場合は範囲外とし、後続タスクとして起票する。
- **A9:** test-docs/review-sca-axis/task0010.tests.yaml は過去タスクの記録として書き換えない。
- **A10:** uv.lock / pdm.lock / pylock.toml は今と同じく選ばれない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
run_scan / build_scan_jobs（A2）
  ├─ pip の対象選択: lockfile を優先（FR1, A10）
  ├─ lockfile の読み取りと変換（FR2, FR5, FR6, FR11, A3 / tomllib・json: NFR4）
  ├─ 直接依存の宣言ファイルの確認（FR7, FR8, A4, A7 / _pip_manifest_candidate）
  ├─ 一時 requirements ファイルの作成と削除（NFR1, A1 / 分割: FR4, A5）
  └─ build_scan_job（純粋関数のまま: NFR2）
       └─ pip-audit の argv（FR3）
集約
  ├─ 直接依存の判定（FR9）
  ├─ finding の file / affected_range（FR10）
  ├─ 分割実行の findings と理由（FR4, A5, A6 / 順序固定: NFR3）
  └─ skip_reasons の合成（FR12）
```

### Data Flow

```
changed_files → pip の lockfile を選ぶ → name==version の行に変換 → 一時 requirements ファイル
  → pip-audit -r <一時ファイル> --no-deps --disable-pip --format json
  → findings（file = lockfile のプロジェクト相対パス、affected_range = ピンのバージョン）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- build_scan_job: 純粋関数のまま残す（NFR2）。変換済みの対象を受け取る（A2）。
- run_scan / build_scan_jobs: lockfile の変換を行う側（A2）。
- _pip_manifest_candidate: Pipfile.lock に対して Pipfile を返す（FR7）。
- _pip_pyproject_direct_names: 変えない（A7）。
- vuln-scanners.yaml の pip エントリ: 変えない（FR3）。
- ALLOWED_EXECUTABLES / ECOSYSTEM_LOCKFILES / 子プロセスの環境変数のピン: 変えない（NFR6）。

**External Dependencies:**
- pip-audit: lockfile 由来のジョブで起動する（FR3）。
- tomllib / json（標準ライブラリ）: lockfile と Pipfile の解析（NFR4）。

### File Structure

記載なし（変更対象のパスは create-plan で導出する）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-python-lockfile-audit/**`
- `test-docs/sca-python-lockfile-audit/**`

`feature-docs/sca-python-lockfile-audit/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-python-lockfile-audit/**` covers `test-docs/sca-python-lockfile-audit/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-python-lockfile-audit/` directory at all; the declared
`test-docs/sca-python-lockfile-audit/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Scenarios

- [ ] TS1（AC1 / FR1, FR2, FR3, FR10）: 一時ディレクトリに project(poetry.lock に脆弱なピン、pyproject.toml に範囲宣言)を置く。PATH 上のスタブ pip-audit は、受け取った -r ファイルの中身を検査して脆弱性入りの JSON を返す。run_scan の結果に finding が出ることと、skipped が false であることを確かめる。
- [ ] TS2（AC2 / FR2, FR7）: TS1 と同じことを Pipfile.lock(default / develop)と Pipfile(`[packages]`)で行う。
- [ ] TS3（AC3, AC4 / FR1, FR3）: lockfile 由来のジョブの argv を検証する。`'--no-deps'` と `'--disable-pip'` は lockfile ジョブにだけあることを確かめ、requirements.txt / pyproject.toml のジョブには無いことも確かめる。test_sca_scan_invocation.py:243-248 を置き換え、258-264 の禁止トークン検査を lockfile ジョブ以外に限る。
- [ ] TS4（AC5 / FR5）: 壊れた TOML の poetry.lock、壊れた JSON の Pipfile.lock、package 配列の無い poetry.lock、全エントリが git の lockfile で、それぞれ pip_lockfile_unconvertible になることを確かめる。スタブの起動記録が残らないことも確かめる。
- [ ] TS5（AC6 / FR8）: 同じ階層に宣言ファイルが無い lockfile、宣言ファイルが壊れた lockfile で、pip_direct_manifest_not_found になり、スタブが起動されないことを確かめる。
- [ ] TS6（AC7 / FR6, FR11）: git / path のエントリと、`'-r evil'` のような名前を含む lockfile で、件数注記と skipped: false を確かめる。一時ファイルの中身をスタブ側で記録し、検証を通った行だけが書かれたことも確かめる。
- [ ] TS7（AC8 / FR4）: 同じ名前で 2 バージョンのピンがある lockfile で、スタブが 2 回起動され、各ファイルにその名前が 1 回ずつ出ることを確かめる。findings が両方そろうこと、同じ入力を 2 回スキャンして結果が同じになることも確かめる。
- [ ] TS8（AC9 / FR9）: 'Django' と 'django' の表記ゆれで、直接依存と判定されることを確かめる。
- [ ] TS9（AC10 / NFR1）: git init した project で lockfile をスキャンし、前後の git status --porcelain が同じであること、一時ファイルが消えていることを確かめる。
- [ ] TS10（AC4 / FR3）: test_sca_scan_normalization.py:187-192 と 295-312 の既存の固定(pip の manifests と args)が変更なしで通ることを確かめる。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

- **Authentication:** 該当なし。
- **Authorization:** 該当なし。
- **Input Validation:** 一時 requirements ファイルに書く行の検証（FR11）。検証を通らないエントリは変換から外す（FR6）。
- **Data Protection:** project root 配下を変更しない（NFR1）。子プロセスの環境変数のピン、ALLOWED_EXECUTABLES、ECOSYSTEM_LOCKFILES を変えない（NFR6）。
- **XSS Prevention:** 該当なし。
- **SQL Injection Prevention:** 該当なし。
- **CSRF Protection:** 該当なし。

## Error Handling

### Error Codes

| Code | Condition | Result |
|------|-----------|--------|
| `pip_lockfile_unconvertible` | FR5 の条件 | pip は not_completed。pip-audit は実行しない。 |
| `pip_direct_manifest_not_found` | FR8 の条件 | pip は not_completed。pip-audit は実行しない。 |
| `pip_lockfile_entries_unpinnable`（summary の注記） | FR6 で外したエントリがある | 件数注記を載せる。skipped は true にしない。 |

### Error Flow

skip_reason は既存の pip_tool_not_found などと同じ経路で skip_reasons に入り、他のエコシステムの理由とはソートしたうえで `'+'` でつなぐ。完了した他のエコシステムの findings は残す（FR12）。分割実行の 1 つが not_completed になった場合は A6 に従う。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] FR1〜FR12 と NFR1〜NFR7 を満たす
- [ ] AC1〜AC11 を満たす
- [ ] TS1〜TS10 が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## Implementation Phases (if applicable)

該当なし。

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
