# Feature: sca-absolute-executable-path

## Overview

`em-workflow/scripts/scan-dependencies.py` の SCA 軸のスキャンで、実行ファイルの解決（`resolve_executable`）を PATH の絶対パスの項目だけに限り、すべてのスキャンジョブの argv[0] を絶対パスにする。子プロセスに渡す PATH（`build_child_env`）からも空の項目と相対の項目を除く。要件の詳細は `feature-docs/sca-absolute-executable-path/REQUIREMENTS.md` を参照する。

## Objectives

- SCA 軸のスキャンで、PATH の相対の項目を経由して、レビュー対象のリポジトリ内にある実行ファイルが起動されないようにする（入れ子のプロジェクトとルートのプロジェクトの両方）。
- どのスキャンジョブでも argv[0] を実行ファイルの絶対パスにする。

## User Stories

該当なし

## Technical Requirements

### Functional Requirements
- **FR1:** 実行ファイルの解決は PATH の絶対パスの項目だけを探索する — `em-workflow/scripts/scan-dependencies.py` の `resolve_executable(name)` は、探索リストの項目のうち空の項目と相対の項目（`os.path.isabs` が偽のもの）を探索しない。絶対パスの項目だけを元の順序で探索し、見つかった実行ファイルの絶対パスを返す。見つからなければ `None` を返す。探索リストは PATH の値とし、PATH が未設定のときは `shutil.which` と同じく `os.defpath` とする。既存の呼び出し `resolve_executable(name)`（引数 1 つ）はそのまま使える。
- **FR2:** 絶対パスの項目で見つからないときは既存のスキップ理由を使う — `resolve_executable` が `None` を返したエコシステムは、`build_scan_jobs` で既存の `<ecosystem>_tool_not_found` をエコシステムごとに 1 回だけ記録し、プランを作らない。相対の項目にしか実行ファイルが無い場合もこれに当たる。新しいスキップ理由は追加しない。
- **FR3:** スキャンジョブの argv[0] は cwd によらず絶対パス — npm / cargo / pip / go のすべてのスキャンジョブで、argv[0] は FR1 で解決した絶対パスとする。ジョブの cwd（ルートのプロジェクト、入れ子のプロジェクトディレクトリ、隔離ディレクトリ）によって起動される実行ファイルが変わらない。
- **FR4:** 子プロセスの PATH から相対・空の項目を除く — `build_child_env(ecosystem, environ)` が子に渡す PATH は、呼び出し元の PATH から空の項目と相対の項目を除き、絶対パスの項目だけを元の順序のまま `os.pathsep` で連結した値とする。絶対パスの項目は書き換えない（正規化・重複除去をしない）。絶対パスの項目が 1 つも残らないとき、および呼び出し元に PATH が無いときは、PATH キーを渡さない。PATH 以外の `CHILD_ENV_BASE_KEYS` の扱いと `ECOSYSTEM_ENV_PINS` の上書きは変えない。
- **FR5:** コード内の説明を新しい挙動に合わせる — `scan-dependencies.py` のうち、`resolve_executable` による解決と子の PATH の扱いを説明するコメント・docstring（`CHILD_ENV_BASE_KEYS` 直前のコメントの「carried through unchanged」、Scan job construction 節のコメント、`build_scan_jobs` / `build_child_env` の docstring）を FR1・FR4 の挙動に合わせる。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリだけを使う:** `scan-dependencies.py` は標準ライブラリだけを import する状態を保つ。`build_scan_job` / `build_child_env` はファイルを開かず、プロセスを起動しない状態を保つ。
- **NFR2 - 変えないもの:** `ALLOWED_EXECUTABLES`、`ECOSYSTEM_ENV_PINS`、`ECOSYSTEM_LOCKFILES`、`em-workflow/references/vuln-scanners.yaml` のレジストリ値、スキップ理由の語彙、`em-workflow/references/review-phase.md` の手順は変えない。
- **NFR3 - 既存テストの維持:** 既存の `tests/test_sca_*.py` と `tests/test_scan_dependencies_*.py` は通り続ける。例外は `tests/test_sca_scan_unchanged_surfaces.py` の `test_ac2_the_child_environment_is_the_pass_through_keys_plus_the_pins` で、フィクスチャの PATH 値（相対の項目 `"runner-PATH"`）を絶対パスの値に替える。テストが確かめる内容（子の環境 = 引き継ぐキー + ピン）は変えない。
- **NFR4 - version を触らない:** `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version は変更しない。

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────┐
│  run_scan                                    │
├──────────────────────────────────────────────┤
│  build_scan_jobs / build_scan_job            │
│    argv[0] = resolve_executable の絶対パス   │
│    None なら <ecosystem>_tool_not_found      │
├──────────────────────────────────────────────┤
│  resolve_executable(name)                    │
│    探索リスト: PATH（未設定なら os.defpath） │
│    絶対パスの項目だけを元の順序で探索        │
├──────────────────────────────────────────────┤
│  build_child_env(ecosystem, environ)         │
│    PATH: 絶対パスの項目だけ（無ければキー無し）│
│    CHILD_ENV_BASE_KEYS / ECOSYSTEM_ENV_PINS  │
│    の扱いは従来どおり                        │
└──────────────────────────────────────────────┘
```

**Component Diagram:**
```
resolve_executable ──(絶対パス / None)──> build_scan_jobs ──> スキャンジョブ（argv[0], cwd）
build_child_env ──(子の環境)──> スキャンジョブ
run_scan ──> スキャンジョブを起動
```

### Data Flow

```
PATH（未設定なら os.defpath）
  → 空の項目・相対の項目を除く
  → 絶対パスの項目を元の順序で探索
  → 実行ファイルの絶対パス → argv[0]
  → 見つからない → <ecosystem>_tool_not_found（エコシステムごとに 1 回、プランなし）

呼び出し元の environ の PATH
  → 空の項目・相対の項目を除く
  → 絶対パスの項目を元の順序のまま os.pathsep で連結 → 子の PATH
  → 絶対パスの項目が残らない / PATH が無い → 子の環境に PATH キーを入れない
```

### API Design

HTTP エンドポイントは該当なし。関数の振る舞いは次のとおり。

#### resolve_executable(name)

- 引数: `name`（実行ファイル名）。既存の 1 引数の呼び出しはそのまま使える。
- 戻り値: 絶対パスの項目で見つかった実行ファイルの絶対パス。見つからなければ `None`。

#### build_child_env(ecosystem, environ)

- 戻り値: 子の環境。PATH は絶対パスの項目だけを元の順序で `os.pathsep` 連結した値。絶対パスの項目が残らないとき、および `environ` に PATH が無いときは PATH キーを含まない。PATH 以外の `CHILD_ENV_BASE_KEYS` と `ECOSYSTEM_ENV_PINS` の扱いは変えない。

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/scan-dependencies.py`: `resolve_executable`、`build_scan_jobs`、`build_scan_job`、`build_child_env`、`run_scan`
- 既存テスト: `tests/test_sca_*.py`、`tests/test_scan_dependencies_*.py`

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）

### File Structure

```
em-workflow/
└── scripts/
    └── scan-dependencies.py                     # FR1〜FR5 の変更
tests/
└── test_sca_scan_unchanged_surfaces.py          # NFR3 のフィクスチャ修正
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上のフィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリをデフォルトで宣言する。

- `feature-docs/sca-absolute-executable-path/**`
- `test-docs/sca-absolute-executable-path/**`

`feature-docs/sca-absolute-executable-path/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-absolute-executable-path/**` に含まれるもの: `test-docs/sca-absolute-executable-path/{T}.tests.yaml`（タスクごとのテスト記録）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

この 2 つのデフォルトエントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込みである。

この宣言はスーパーセット（superset）の主張であり、verify 時点で観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致は求めない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/sca-absolute-executable-path/` ディレクトリを生成しないが、宣言された `test-docs/sca-absolute-executable-path/**` は依然として正しい。宣言したパスが生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests
- [ ] TS1（AC1）: 一時ディレクトリに相対の項目用ディレクトリと絶対パスの stub ディレクトリを作り、cwd を相対の項目が解決される場所にした状態で PATH を `"tools:<絶対パスの stub ディレクトリ>"` にする - `resolve_executable("npm")` が stub の絶対パスを返す
- [ ] TS2（AC2）: PATH を相対・空の項目だけ（`"tools"`、`"./node_modules/.bin"`、`"."`、`""`、`"~/bin"`）にし、その下に実行ファイルを置く - `resolve_executable` が `None` を返し、`build_scan_jobs` が `["npm_tool_not_found"]` とプラン 0 件を返す
- [ ] TS5（AC5）: `build_child_env` に混在した PATH を渡す - 絶対パスの項目だけが元の順序で残る
- [ ] TS6（AC5）: `build_child_env` に相対・空の項目だけの PATH を渡す、および PATH を含まない environ を渡す - 戻り値に PATH キーが無い
- [ ] TS8（AC6）: 全引き継ぎキーとピン対象の値を持つ environ（PATH は絶対パス）で `build_child_env` を呼ぶ - 結果が「引き継ぎキー + ピン」と一致する（既存 `test_ac2` のフィクスチャ修正で担保）
- [ ] TS9（AC1）: PATH を未設定にし、`os.defpath` を相対・空の項目と絶対パスの stub ディレクトリの混在に差し替える - `resolve_executable` が stub の絶対パスを返す

### Integration Tests
- [ ] TS3（AC3, AC4）: テストハーネス（stub が起動記録を書く既存の形）で、`services/api/package.json`・`package-lock.json` と、起動されたら印を残す `services/api/tools/npm` と `<cwd>/tools/npm` を置き、PATH を `"tools<pathsep><stub ディレクトリ>"` にして `run_scan` を実行する - 起動記録の argv[0] が stub の絶対パスで、どちらの `tools/npm` の印も残らない
- [ ] TS4（AC4）: go の入れ子のプロジェクト（cwd が `<root>/services/api`）と、pip・ルートの go（cwd がルート）について `run_scan` を実行する - 起動記録の argv[0] が絶対パスで、`resolve_executable` の値と一致する
- [ ] TS7（AC5）: `run_scan` を実行する - 起動記録に残る子の環境の PATH に、相対・空の項目が含まれない

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 空の項目と `"."` を含む PATH: 探索しない（FR1）・子の PATH から除く（FR4）
- [ ] `"~/bin"`: `~` を展開せず相対の項目として扱う（A2）
- [ ] PATH が未設定: 探索リストは `os.defpath` とし、そこからも相対・空の項目を除く（FR1、A1）
- [ ] 絶対パスの項目が 1 つも残らない PATH、および PATH が無い environ: 子の環境に PATH キーを入れない（FR4）
- [ ] 実行ファイルが相対の項目の下にしか無い: `<ecosystem>_tool_not_found` を 1 回だけ記録し、プランを作らない（FR2）

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** PATH（PATH が未設定のときは `os.defpath`）の空の項目と相対の項目（`os.path.isabs` が偽のもの）を、実行ファイルの探索（FR1）と子の PATH（FR4）の両方から除く。スキャンジョブの argv[0] は絶対パスにする（FR3）。
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | HTTP Status | User Message |
|------|-------------|-------------|--------------|
| `<ecosystem>_tool_not_found` | `resolve_executable` が `None` を返した（相対の項目にしか実行ファイルが無い場合を含む）。エコシステムごとに 1 回だけ記録し、プランを作らない（既存のスキップ理由） | - | - |

### Error Flow

```
resolve_executable が None → <ecosystem>_tool_not_found を 1 回記録 → そのエコシステムのプランを作らない
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] AC1（FR1）: PATH に相対の項目（例: `tools`、`./node_modules/.bin`、`.`、空の項目）と絶対パスの項目が混在し、両方に同名の実行ファイルがあるとき、`resolve_executable` は絶対パスの項目側の実行ファイルの絶対パスを返す。
- [ ] AC2（FR1, FR2）: 実行ファイルが PATH の相対・空の項目の下にしか無いとき、`resolve_executable` は `None` を返し、`build_scan_jobs` はそのエコシステムについて `<ecosystem>_tool_not_found` を 1 回だけ返し、プランを作らない。
- [ ] AC3（FR3）: 攻撃シナリオ（PATH に相対の項目 `tools` があり、`services/api/package.json`・`package-lock.json` と実行可能な `services/api/tools/npm` がある状態）で `run_scan` を実行しても、`services/api/tools/npm` と `<起動時の cwd>/tools/npm` はどちらも起動されない。
- [ ] AC4（FR3）: cwd が入れ子のディレクトリになるジョブ（go の入れ子のプロジェクト、npm / cargo の隔離ディレクトリ）と、cwd がルートのジョブ（pip、ルートの go）のどちらでも、argv[0] は絶対パスで、`resolve_executable` が返した値と一致する。
- [ ] AC5（FR4）: `build_child_env` に PATH `"tools::/usr/bin:./node_modules/.bin:/opt/bin"`（区切りは `os.pathsep`）を渡すと、子の PATH は `"/usr/bin:/opt/bin"` になる。PATH が相対・空の項目だけのとき、および PATH が無いとき、子の環境に PATH キーは無い。
- [ ] AC6（FR4, NFR2）: PATH 以外の引き継ぎキー（`HOME`、`TMPDIR`、`TEMP`、`TMP`、`SYSTEMROOT`、`USERPROFILE`）とエコシステムごとのピンは、変更前と同じ値で子の環境に入る。
- [ ] AC7（NFR1, NFR3）: `python3 -m unittest discover -s tests` が通る。

## Assumptions

- A1: PATH が未設定のときの探索リストは `shutil.which` と同じ `os.defpath` とし、そこからも相対・空の項目を除く（回答 skip_relative_entries を既存の探索リストに当てはめたもの）。
- A2: 相対かどうかは `os.path.isabs` で判定する。`~` や環境変数は展開しない（`~/bin` は相対として扱う）。
- A3: 対象はスキャンジョブの実行ファイル解決と子の環境だけとする。git の呼び出し（`resolve_main_worktree_root`）とタスクシステムの entry point の呼び出し（`list_security_tasks` ほか）は変えない。
- A4: 見つからない場合のスキップ理由は既存の `<ecosystem>_tool_not_found` を使い続ける（既存テストで固定されている値）。
- A5: task_description の「追加の指示」（push、PR 作成、Codex への相談、Notion への記録）は実行手順への指示として扱い、SPEC の要件には含めない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/sca-absolute-executable-path/REQUIREMENTS.md`
- 変更対象: `em-workflow/scripts/scan-dependencies.py`
- 変更しないレジストリ: `em-workflow/references/vuln-scanners.yaml`
- 変更しない手順: `em-workflow/references/review-phase.md`
