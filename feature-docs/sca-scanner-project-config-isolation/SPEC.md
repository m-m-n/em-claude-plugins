# Feature: sca-scanner-project-config-isolation

## Overview

軸 2 の npm / cargo スキャンを、被レビューツリーの外に作った隔離ディレクトリで実行する。スキャナは被レビュープロジェクト由来の設定ファイル（`.npmrc`、`.cargo/audit.toml`）を読まなくなる。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- 軸 2 の npm / cargo スキャンが、被レビュープロジェクト由来の設定ファイル（`.npmrc`、`.cargo/audit.toml`）を読まないようにする。PR 作者は設定ファイルを置くだけではクリーンなスキャン結果を偽装できなくなる

## User Stories

### US1: 被レビュープロジェクトの設定ファイルに左右されないスキャン
レビュー実行者として、軸 2 の npm / cargo スキャンが被レビュープロジェクト由来の設定ファイルを読まないようにしたい。PR 作者が設定ファイルを置くだけではクリーンなスキャン結果を偽装できないようにするため。

**Acceptance Criteria:**
- [ ] AC1（FR1、FR12）: 敵対的な `.npmrc` を置いたプロジェクトで npm を走査したとき、スタブの cwd は実プロジェクトルートの外にある。cwd とその祖先に `.npmrc` が無い。argv は `[<npm>, audit, --json, --workspaces=false]` である
- [ ] AC2（FR1、FR5）: npm で隔離ディレクトリに置かれた `package.json` とアンカーの内容は原本と一致する。`npm-shrinkwrap.json` と `package-lock.json` が両方あるときは `npm-shrinkwrap.json` がコピーされる
- [ ] AC3（FR2、FR3、FR5、FR12）: 敵対的な `.cargo/audit.toml` を置いたプロジェクトで cargo を走査したとき、スタブの cwd は実プロジェクトルートの外にある。cwd とその祖先に `.cargo/audit.toml` が無い。argv は `[<cargo-audit>, audit, --file, <隔離ディレクトリ内のコピー>, --json]` で、`--url` と `--db` を含まない。コピーの内容は原本の `Cargo.lock` と一致する
- [ ] AC4（FR5、FR9）: グループごとに内容の違う入力を持つ複数グループのとき、各起動が記録した入力の内容は、それぞれのグループの原本と対応する。処理順と findings の file ラベルは変更前と同じ
- [ ] AC5（FR9）: cargo の直接依存の判定には、被レビュープロジェクトの元の `Cargo.toml` が使われる
- [ ] AC6（FR6、FR7、NFR2）: `TMPDIR` / `TEMP` / `TMP` / `tempfile.tempdir` のどれか、またはツリー内を指すシンボリックリンクで、一時ディレクトリの親を被レビューツリーの内側へ向けたとき、`<ecosystem>_isolation_failed` になる。スキャナは起動されず、実プロジェクトルートの内側には何も作られない
- [ ] AC7（FR7、NFR3）: コピーが失敗したグループは起動されず、`<ecosystem>_isolation_failed` になる。同じ実行の他のグループは走査され、その findings は結果に残る。`skip_reason` にパス文字列は入らない
- [ ] AC8（FR8）: 成功、ツールの失敗、タイムアウト、コピーの途中での失敗のどの後にも、隔離ディレクトリは残っていない。隔離ディレクトリの権限は所有者だけ
- [ ] AC9（FR4、NFR1）: prepared path を渡して `build_scan_job` を呼んでも、ファイルを開かず、プロセスも起動しない
- [ ] AC10（FR10、FR11）: pip と go の argv / cwd / env、および `ECOSYSTEM_ENV_PINS` の全エコシステムの値は、変更前と同じ。子プロセスの環境はレビュー実行者の HOME をそのまま渡し、レビュー実行者の設定を無効化・上書きする固定値は追加されていない
- [ ] AC11（NFR4）: `python3 -m unittest discover -s tests` が通る

## Technical Requirements

### Functional Requirements
- **FR1:** npm スキャンを隔離ディレクトリで実行する。紐付け検査を通った npm のスキャングループごとに、`package.json` と選ばれたアンカーの lockfile（`npm-shrinkwrap.json` を `package-lock.json` より優先）を、被レビューツリーの外に新しく作った隔離ディレクトリへコピーし、そこを cwd にして `npm audit` を起動する。argv は `[<npm>, audit, --json, --workspaces=false]` のまま。`ECOSYSTEM_ENV_PINS['npm']` の値も変えない。
- **FR2:** cargo スキャンを隔離ディレクトリで `--file` 付きで実行する。検証済みの `Cargo.lock` を、被レビューツリーの外に新しく作った隔離ディレクトリへコピーし、そこを cwd にして argv `[<cargo-audit>, audit, --file, <コピーのパス>, --json]` で cargo-audit を起動する。`--url` と `--db` は指定しない（advisory DB の設定はレビュー実行者の既定のまま）。
- **FR3:** cargo の対象指定を明示する。cargo の対象指定（`--file`）をレジストリ（`vuln-scanners.yaml`）とジョブ組み立ての両方で明示する。`--file <コピー>` は `audit` サブコマンドの直後に置く。レジストリに `target_flag` を足すだけでは満たさない。
- **FR4:** 隔離準備は実行側で行う。隔離の準備（作成・コピー・検証）は、紐付け検査の後に実行側で行う。`build_scan_job` は純粋関数のまま、準備済みのパスを受け取るだけにする。
- **FR5:** コピー元の検証とコピーの形。コピー元は紐付け検査と同じ規則で検証する。npm は `package.json` と優先順位で選んだアンカー、cargo は `Cargo.lock` をコピーする。内容は変えず、通常ファイルとしてコピーする。許可されている同一ディレクトリ内のシンボリックリンクは、リンク先の内容をコピーする。
- **FR6:** 隔離ディレクトリの置き場所の検証。作成前に一時ディレクトリの親を realpath で確かめ、作成後に隔離ディレクトリ自身も realpath で確かめる。どちらかが被レビューの実プロジェクトルートそのもの、またはその配下にあれば、隔離の失敗として扱い、スキャナは起動しない。
- **FR7:** 隔離失敗時の扱い。隔離ディレクトリの作成・コピー・検証のどれかが失敗したら、スキャナは起動しない。そのスキャン単位は `not_completed` にし、パスを含まない理由 `npm_isolation_failed` / `cargo_isolation_failed` を返す。プロジェクトディレクトリ内での実行にはフォールバックしない。失敗したグループ以外のグループは続けて走査し、完了したグループの findings と失敗理由はどちらも結果に残す（`skip_reason` は既存の規則で組み立てる）。
- **FR8:** 隔離ディレクトリの寿命。隔離ディレクトリはスキャングループごとに 1 つ、名前が他と重ならないものを所有者だけがアクセスできる権限で作る。次のどの場合も削除する: 成功、ツールの失敗、タイムアウト、コピーの途中での失敗。
- **FR9:** ラベルと既存の振る舞いを保つ。ジョブの manifest と findings の file は、元のプロジェクト相対パスのままにする。cargo の直接依存の判定は、これまでどおり被レビュープロジェクトの元の `Cargo.toml` を使う。スキャン単位のまとめ方（グループ化）、紐付け検査、処理順、`skip_reason` の組み立ては変えない。
- **FR10:** pip と go は変えない。pip と go のジョブ（argv / cwd / env）と `ECOSYSTEM_ENV_PINS` の値は変えない。
- **FR11:** 信頼する設定の範囲。HOME、npm の globalconfig、Cargo ホームの `audit.toml`、advisory DB はレビュー実行者が管理するもので、PR 作者は変更できない。このことを明記する。既存の env の固定値は保ち、レビュー実行者自身の設定を追加で無効化したり上書きしたりはしない。
- **FR12:** 再発検出テスト。PATH に置いたオフラインの記録スタブを使う。プロジェクトに敵対的な `.npmrc`（`https-proxy`、`strict-ssl=false`、`registry`、`cafile`）と `.cargo/audit.toml`（`[advisories] ignore`、`[database] url/path`）を置いて `run_scan` し、次を確かめる: スタブの cwd が実プロジェクトルートの外にあること、cwd とその祖先に `.npmrc` / `.cargo/audit.toml` が無いこと、コピーした入力の内容が原本と一致すること（隔離ディレクトリが消える前にスタブが記録する）、cargo の `--file` がコピーを指していること。
- **FR13:** 記述の更新。`ECOSYSTEM_ENV_PINS` / `build_scan_job` / `run_ecosystem_command` / `_scan_bound_group` / `run_scan` の docstring とコメント、`vuln-scanners.yaml` のコメント、`review-phase.md` の軸 2 の記述を、新しい実行場所に合わせて直す。

### Non-Functional Requirements
- **NFR1 - build_scan_job の純粋性:** `build_scan_job` はファイルを開かず、プロセスも起動しない。
- **NFR2 - 被レビューツリーへの書き込み禁止:** スキャンは実プロジェクトルートの内側に何も作らず、何も書かない。
- **NFR3 - パスを含まない理由:** `skip_reason` と summary には固定のトークンだけを入れ、パス文字列を含めない。
- **NFR4 - テストの前提:** テストは標準ライブラリの unittest だけで書き、オフラインで結果が毎回同じになる。実物の npm / cargo-audit を前提にしない。

## Implementation Approach

### Architecture

**System Architecture:**
```
run_scan
  └─ スキャングループごと（グループ化・処理順は変えない）
       ├─ 紐付け検査（変えない）
       ├─ 隔離の準備（実行側、npm / cargo のみ）
       │    ├─ 一時ディレクトリの親を realpath で検証
       │    ├─ 隔離ディレクトリを作成（グループごとに 1 つ、所有者だけの権限）
       │    ├─ 隔離ディレクトリ自身を realpath で検証
       │    └─ コピー元を検証し、通常ファイルとしてコピー
       ├─ build_scan_job（純粋関数、準備済みのパスを受け取る）
       ├─ run_ecosystem_command（cwd = 隔離ディレクトリ）
       └─ 隔離ディレクトリを削除（成功・ツールの失敗・タイムアウト・コピー途中の失敗）
```

**Component Diagram:**
```
scan-dependencies.py
  ECOSYSTEM_ENV_PINS   値は変えない（全エコシステム）
  _scan_bound_group    隔離の準備・削除、失敗時の not_completed
  build_scan_job       準備済みのパスから argv / cwd を組み立てる（ファイルも開かず、プロセスも起動しない）
  run_ecosystem_command  隔離ディレクトリを cwd にしてスキャナを起動
vuln-scanners.yaml
  cargo エントリ       --file による対象指定を明示
```

### Data Flow

```
npm:   package.json + アンカー（npm-shrinkwrap.json > package-lock.json）
         → 隔離ディレクトリへコピー
         → cwd=隔離ディレクトリ, argv=[<npm>, audit, --json, --workspaces=false]
cargo: Cargo.lock
         → 隔離ディレクトリへコピー
         → cwd=隔離ディレクトリ, argv=[<cargo-audit>, audit, --file, <コピーのパス>, --json]
         → 直接依存の判定は被レビュープロジェクトの元の Cargo.toml
findings の file / ジョブの manifest ← 元のプロジェクト相対パス
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/scan-dependencies.py`: スキャンの実行
- `em-workflow/references/vuln-scanners.yaml`: スキャナのレジストリ
- `em-workflow/references/review-phase.md`: 軸 2 の記述

**External Dependencies:**
- npm（`npm audit`）: npm スキャンで起動する
- cargo-audit: cargo スキャンで起動する

### File Structure

```
em-workflow/
├── scripts/
│   └── scan-dependencies.py        # ECOSYSTEM_ENV_PINS のコメント、build_scan_job、run_ecosystem_command、_scan_bound_group、run_scan
└── references/
    ├── vuln-scanners.yaml          # cargo エントリの args / 対象指定とコメント
    └── review-phase.md             # 軸 2 の記述
tests/
├── test_sca_per_project_scan_binding.py
├── test_sca_scan_invocation.py
├── test_sca_scan_job_grouping.py
├── test_sca_scan_normalization.py
└── test_sca_review_phase_multi_project_coverage.py   # review-phase.md の記述が変わる場合
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-scanner-project-config-isolation/**`
- `test-docs/sca-scanner-project-config-isolation/**`

`feature-docs/sca-scanner-project-config-isolation/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-scanner-project-config-isolation/**` covers `test-docs/sca-scanner-project-config-isolation/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-scanner-project-config-isolation/` directory at all; the declared
`test-docs/sca-scanner-project-config-isolation/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

テストは標準ライブラリの unittest で書き、PATH に置いたオフラインの記録スタブを使う（NFR4、FR12）。実行コマンドは `python3 -m unittest discover -s tests`。

### Unit Tests
- [ ] TS1（AC1、AC2）: npm、ルートに敵対的な `.npmrc` を置いた場合 - cwd が外にあること、祖先も含めて `.npmrc` が無いこと、コピーが原本と一致すること、結果が completed になること、ラベルが `package.json` であること
- [ ] TS2（AC2）: npm で `npm-shrinkwrap.json` と `package-lock.json` が両方ある場合 - shrinkwrap がコピーされること
- [ ] TS3（AC3、AC5）: cargo、敵対的な `.cargo/audit.toml` を置いた場合 - cwd、argv（`--file` の位置と、`--url` / `--db` が無いこと）、コピーの内容、元の `Cargo.toml` による直接依存の判定
- [ ] TS4（AC4）: npm と cargo で、内容の違う複数グループを走査する場合 - グループごとに入力が対応すること、処理順・ラベル
- [ ] TS5（AC6）: `TMPDIR` / `TEMP` / `TMP` / `tempfile.tempdir` とシンボリックリンクで、一時ディレクトリをツリー内へ向けた場合 - isolation_failed になり、起動されず、ツリー内に何も作られないこと
- [ ] TS6（AC7）: コピーの失敗 - 起動されず isolation_failed になり、他グループの走査が続くこと
- [ ] TS7（AC8）: 成功、ツールの失敗、タイムアウト、コピーの途中での失敗の後 - 隔離ディレクトリが残っていないこと。スタブが記録した cwd の権限が所有者だけであること
- [ ] TS8（AC9）: prepared path を渡した `build_scan_job` - `open` / `os.open` / `subprocess` を mock で禁止して呼んでも成功すること
- [ ] TS9（AC10）: pip と go - argv / cwd / env の不変、`ECOSYSTEM_ENV_PINS` の不変、HOME がそのまま渡ること

### Integration Tests
該当なし

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] 一時ディレクトリの親が被レビューツリーの内側を指す場合 - `<ecosystem>_isolation_failed`（TS5）
- [ ] コピーの途中で失敗した場合 - スキャナを起動せず、隔離ディレクトリを削除する（TS6、TS7）
- [ ] `npm-shrinkwrap.json` と `package-lock.json` が両方ある場合 - `npm-shrinkwrap.json` をコピーする（TS2）

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** コピー元は紐付け検査と同じ規則で検証する（FR5）。一時ディレクトリの親と隔離ディレクトリ自身を realpath で検証する（FR6）
- **Data Protection:** スキャンは実プロジェクトルートの内側に何も作らず、何も書かない（NFR2）。隔離ディレクトリは所有者だけがアクセスできる権限で作る（FR8）。`skip_reason` と summary にパス文字列を含めない（NFR3）
- **Trusted configuration:** HOME、npm の globalconfig、Cargo ホームの `audit.toml`、advisory DB はレビュー実行者が管理するもので、PR 作者は変更できない（FR11）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | Result |
|------|-------------|--------|
| `npm_isolation_failed` | npm の隔離ディレクトリの作成・コピー・検証のどれかが失敗した | スキャナを起動しない。そのスキャン単位は `not_completed` |
| `cargo_isolation_failed` | cargo の隔離ディレクトリの作成・コピー・検証のどれかが失敗した | スキャナを起動しない。そのスキャン単位は `not_completed` |

### Error Flow

```
隔離の失敗 → スキャナを起動しない → 隔離ディレクトリを削除 → not_completed + <ecosystem>_isolation_failed
           → 他のグループの走査を続ける → 完了したグループの findings と失敗理由をどちらも結果に残す
```

プロジェクトディレクトリ内での実行にはフォールバックしない。`skip_reason` は既存の規則で組み立てる。

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete（FR13）
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` が通る（AC11）

## Open Questions

なし

## Assumptions

- A1: 対象は npm と cargo だけ。pip と go は変えない
- A2: 完了の定義のうち「再現手順で現象が起きない」は、設定ファイルがスキャナの探索経路に載らないことを記録スタブのテストで示して満たす
- A3: `plugin.json` / `marketplace.json` の version は変えない

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/sca-scanner-project-config-isolation/REQUIREMENTS.md`
