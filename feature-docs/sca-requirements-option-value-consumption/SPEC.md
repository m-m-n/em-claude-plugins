# Feature: sca-requirements-option-value-consumption

## Overview

`scan-dependencies.py` が requirements ファイルのオプション行を読むとき、値を取る pip オプションの値になるトークンを `-r` / `-c` / `-e` と取り違えないようにする。
値を取るオプションの分離形では次のトークンを値として消費して読み捨て、値を取る長形式の省略形は判定不能（`complete=False`）として扱う。

## Objectives

- requirements ファイルのオプション行で、値を取る pip オプションの値になるトークンを `-r` / `-c` / `-e` と取り違えない。
- include の取りこぼしで直接依存の high / critical の advisory が黙って落ちる過小方向と、値のトークンを editable / include と読んで直接依存を余分に足す過大方向の両方を無くす。

## Technical Requirements

### Functional Requirements

- **FR1:** 値を取るオプションの集合 — 分離形で次のトークンを値として消費するオプションは、既存の `-r` / `--requirement`、`-c` / `--constraint`、`-e` / `--editable` に加えて次のすべてとする: `-i` / `--index-url` / `--pypi-url`、`--extra-index-url`、`-f` / `--find-links`、`--trusted-host`、`--no-binary`、`--only-binary`、`--use-feature`、`--hash`、`--global-option`、`-C` / `--config-settings`。`--install-option` は含めない。
- **FR2:** 分離形の値の消費 — FR1 で追加したオプションを分離形（トークンがオプション名と完全一致）で書いたときは、次のトークンを先頭が `-` でも、単独の `--` でも値として消費し、読み捨てる。行末で次のトークンが無いときは何も消費しない。
- **FR3:** `=` 形式と短形式の連結形 — 長形式の `=` 形式（`--index-url=URL`、`--trusted-host=` など空の値を含む）と、短形式に値を連結した形（`-iURL`、`-f./wheels`、`-Ckey=val`）は、そのトークンだけで完結させ、次のトークンを消費しない。
- **FR4:** 消費した値は解釈しない — FR1 で追加したオプションの値として消費したトークンは、include / constraint / editable として解釈しない。値の中の `-r...`、`-e...`、`-c...` からファイルを開かず、名前の集合にも加えない。
- **FR5:** 値を取る長形式の省略形 — トークンが `--` で始まり、`=` より前の名前が `--` より長く、値を取る長形式（`--requirement`、`--editable`、`--constraint` と FR1 で追加した長形式）のいずれかの真の接頭辞（完全一致しない）であるときは、一意・曖昧を問わず undetermined として名前の集合を `complete=False` にする。次のトークンは消費せず、`=` 以降の値は名前にもファイルにもしない。`--requirement` / `--editable` の省略形の扱いは変えない。
- **FR6:** 変えない挙動 — 次の挙動は変えない: `-r` / `-c` / `-e` の各形式の解釈、include を開く範囲の制限（プロジェクトルートの外・URL を開かない）、制約ファイルを開かず complete を変えないこと、未知のオプションと余分な語の読み捨て、値として消費されない単独の `--` の読み捨て、値を取るオプションが行末にあり値が無いときに `complete=True` のままであること、判定不能の注記（summary）の形。
- **FR7:** 既存テストの期待の書き換え — `tests/test_scan_dependencies_pip_directness.py` の `test_ac6_a_constraint_abbreviation_is_not_flagged` の期待を、`--con y` を含む行で `complete=False` になる形に書き換える。
- **FR8:** コード内の説明の更新 — `_requirements_option_items` と `_pip_requirements_direct_names` の docstring、および `_ABBREVIATED_REQUIREMENTS_OPTIONS` のコメントを、FR1 から FR5 の挙動に合わせて書き直す。

### Non-Functional Requirements

- **NFR1:** 標準ライブラリのみ・例外を外へ出さない — `scan-dependencies.py` は標準ライブラリだけで動き、`_pip_requirements_direct_names` は例外を外へ出さない。
- **NFR2:** ファイルとネットワークへの到達 — 値として消費したトークンや省略形の値から、ファイルを開いたり URL へ接続したりしない。
- **NFR3:** summary に中身を出さない — summary にトークンの中身・パス・制約ファイル名を出さない。
- **NFR4:** テストの書き方 — テストは標準ライブラリの unittest だけで書き、`tests/test_scan_dependencies_pip_directness.py` に置く。
- **NFR5:** version を変えない — em-workflow の `plugin.json` と `marketplace.json` の version は変えない。

## Acceptance Criteria

- [ ] **AC-1** (FR1, FR2, FR4): requirements.txt が `--trusted-host -c -r deps.txt` の 1 行だけで、deps.txt が advisory のあるパッケージを宣言するとき、deps.txt を開き、名前の集合は deps.txt の名前で `complete=True` になる。スキャンはその advisory を finding として出し、判定不能の注記を出さない。
- [ ] **AC-2** (FR1, FR2, FR4): `-f -c -r deps.txt`、`-i -c -r deps.txt`、`--extra-index-url -c -r deps.txt` と、FR1 で追加した残りの分離形（`--index-url`、`--pypi-url`、`--find-links`、`--no-binary`、`--only-binary`、`--use-feature`、`--hash`、`--global-option`、`-C`、`--config-settings`）で `-c -r deps.txt` を続けた行でも、AC-1 と同じ名前の集合と `complete=True` になる。
- [ ] **AC-3** (FR2, FR4): `-f "-enamed-pkg" -r actual.txt` では named-pkg を名前に加えず、actual.txt を開いてその名前を加える。`complete=True`。
- [ ] **AC-4** (FR2, FR4): `--find-links "-rdeps.txt" -r actual.txt` では deps.txt を開かず、actual.txt を開いてその名前を加える。`complete=True`。
- [ ] **AC-5** (FR2): `-f -- -r deps.txt` では `--` を `-f` の値として消費し、deps.txt を開く。`complete=True`。
- [ ] **AC-6** (FR3): `--trusted-host=x -r deps.txt`、`--index-url= -r deps.txt`、`-ihttps://example.invalid/simple -r deps.txt`、`-f./wheels -r deps.txt` では deps.txt を開く。`complete=True`。
- [ ] **AC-7** (FR5): `--trusted -c -r deps.txt`、`--index -c -r deps.txt`、`--find -c -r deps.txt` では `complete=False` になり、deps.txt を開かない。この行の requirements.txt で宣言されていないパッケージの advisory は、判定不能の注記で 1 件として数える。
- [ ] **AC-8** (FR5): 省略形は次のトークンを消費しない: `--trusted -r deps.txt` では deps.txt を開き、`complete=False`。`--trusted=-rdeps.txt` では deps.txt を開かず、`complete=False`。
- [ ] **AC-9** (FR5, FR7): `--constraint-extra x --con y` と `--con y` は `complete=False` になる。`--constraint-extra x` だけの行は `complete=True` のまま。曖昧な接頭辞 `--no x` も `complete=False` になる。
- [ ] **AC-10** (FR6): 値を取るオプションが行末にあり値が無い行（`-i`、`-f`、`--trusted-host`）は `complete=True` のまま。値として消費されない単独の `--` を含む既存の行（`--`、`-f ./wheels --`、`--index-url URL -- --no-index`）も `complete=True` のまま。
- [ ] **AC-11** (FR1, FR2, FR4): include した先のファイルの中の `--trusted-host -c -r deeper.txt`、および継続行で 1 行につないだ `--trusted-host \` + `-c -r deeper.txt` でも、deeper.txt を開き、`complete=True` になる。
- [ ] **AC-12** (FR6, FR7, NFR1, NFR4): `python3 -m unittest discover -s tests` が通る。既存テストの期待を変えるのは `test_ac6_a_constraint_abbreviation_is_not_flagged` だけ。
- [ ] **AC-13** (NFR5): `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る。

## Implementation Approach

対象は `scan-dependencies.py` の requirements ファイルのオプション行の解析（`_requirements_option_items`、`_pip_requirements_direct_names`、`_ABBREVIATED_REQUIREMENTS_OPTIONS`）と、`tests/test_scan_dependencies_pip_directness.py`。

### Dependencies

**Internal Dependencies:**
- `scan-dependencies.py`: 標準ライブラリのみで動く（NFR1）。

**External Dependencies:**
- なし

## Assumptions

- **A1:** 値を取るオプションが行末にあり値が無い行は `complete=True` のままにする。
- **A2:** `=` 形式と短形式の連結形は次のトークンを消費しない。
- **A3:** 値として消費される `--` は値として扱う。値として消費されない単独の `--` の扱いは変えない（requirement.lone-double-dash: out_of_scope）。
- **A4:** 判定不能の注記（summary）の形は変えない。
- **A5:** 値を取るオプションの集合は pip 25.1.1 の requirements ファイル用パーサが受け付けるものとする（requirement.value-option-set: pip_requirements_file_set）。
- **A6:** 値を取る長形式の省略形は、一意・曖昧を問わず `complete=False` にし、次のトークンを消費しない（requirement.abbreviation-handling: incomplete_without_consuming）。
- **A7:** `--constraint` の省略形も `complete=False` にし、既存テスト `test_ac6_a_constraint_abbreviation_is_not_flagged` の期待を書き換える（requirement.constraint-abbreviation: include_constraint_abbreviation）。
- **A8:** requirements ファイル用パーサの値を取らないオプション名（`--no-index`、`--prefer-binary`、`--require-hashes`、`--pre`）は、FR5 の対象となる長形式のどれの真の接頭辞にもならない。

## Declared Change Set

この節は手書きの一覧を持たず、create-plan での導出を示す。機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

機能固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言に含める。

- `feature-docs/sca-requirements-option-value-consumption/**`
- `test-docs/sca-requirements-option-value-consumption/**`

`feature-docs/sca-requirements-option-value-consumption/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml` と、design ステップが生成する成果物を含む。これらは各フェーズ文書と `references/phase-state.md` が生成・所有する。

`test-docs/sca-requirements-option-value-consumption/**` はタスクごとのテスト記録 `test-docs/sca-requirements-option-value-consumption/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。

この宣言は上位集合の宣言で、検証時に観測した実際の変更集合が宣言した集合に含まれていればよい。implement タスクが無い場合は `test-docs/sca-requirements-option-value-consumption/` が生成されないが、宣言した `test-docs/sca-requirements-option-value-consumption/**` はその場合も正しく、実体化しなかった宣言パスは違反にならない。

## Test Scenarios

テストは `tests/test_scan_dependencies_pip_directness.py` に標準ライブラリの unittest で書く（NFR4）。

### Unit Tests

- [ ] **TS-1** (AC-1): 入力 requirements.txt: `--trusted-host -c -r deps.txt`、deps.txt: `vuln-pkg==1.0`、advisory: vuln-pkg — 名前 {vuln-pkg}、`complete=True`、deps.txt を開く、finding 1 件、判定不能の注記なし、ネットワーク接続なし
- [ ] **TS-2** (AC-2): 入力 requirements.txt: `-f -c -r deps.txt`（同じ形で `-i`、`--extra-index-url`、`--index-url`、`--pypi-url`、`--find-links`、`--no-binary`、`--only-binary`、`--use-feature`、`--hash`、`--global-option`、`-C`、`--config-settings` を subTest で回す） — 名前 {vuln-pkg}、`complete=True`、deps.txt を開く
- [ ] **TS-3** (AC-3): 入力 requirements.txt: `-f "-enamed-pkg" -r actual.txt`、actual.txt: `actual-pkg` — 名前に named-pkg を含まず actual-pkg を含む、`complete=True`、actual.txt を開く
- [ ] **TS-4** (AC-4): 入力 requirements.txt: `--find-links "-rdeps.txt" -r actual.txt`、deps.txt と actual.txt がルート内に存在 — deps.txt を開かない、actual.txt を開く、名前に deps 側の名前を含まない、`complete=True`
- [ ] **TS-5** (AC-5): 入力 requirements.txt: `-f -- -r deps.txt` — deps.txt を開く、`complete=True`
- [ ] **TS-6** (AC-6): 入力 `--trusted-host=x -r deps.txt`、`--index-url= -r deps.txt`、`-ihttps://example.invalid/simple -r deps.txt`、`-f./wheels -r deps.txt` — deps.txt を開く、`complete=True`
- [ ] **TS-7** (AC-7): 入力 `--trusted -c -r deps.txt`、`--index -c -r deps.txt`、`--find -c -r deps.txt`。スキャンでは requirements.txt に own-pkg、advisory は undeclared-pkg — `complete=False`、deps.txt を開かない、判定不能の注記で 1 件
- [ ] **TS-8** (AC-8): 入力 `--trusted -r deps.txt` と `--trusted=-rdeps.txt` — 前者は deps.txt を開き `complete=False`、後者は deps.txt を開かず `complete=False`
- [ ] **TS-9** (AC-9): 入力 `--constraint-extra x --con y`、`--con y`、`--no x`、`--constraint-extra x` — 前の 3 つは `complete=False`、`--constraint-extra x` は `complete=True`。名前は {own-pkg}
- [ ] **TS-10** (AC-10): 入力 `-i`、`-f`、`--trusted-host`、`--`、`-f ./wheels --`、`--index-url URL -- --no-index` — `complete=True`、名前 {own-pkg}
- [ ] **TS-11** (AC-11): 入力 requirements.txt: `-r inc.txt`、inc.txt: `--trusted-host -c -r deeper.txt`。別ケースで requirements.txt: `--trusted-host \`（改行で継続）`-c -r deeper.txt` — deeper.txt を開き、その名前が入る、`complete=True`

### Integration Tests

- [ ] `python3 -m unittest discover -s tests` が通る（AC-12）
- [ ] `python3 em-workflow/scripts/check-plugin-invariants.py .` が通る（AC-13）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] FR1〜FR8、NFR1〜NFR5 を満たす
- [ ] AC-1〜AC-13 を満たす
- [ ] TS-1〜TS-11 が通る

## Open Questions

なし
