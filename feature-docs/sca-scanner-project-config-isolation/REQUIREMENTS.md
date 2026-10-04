---
title: "sca-scanner-project-config-isolation"
created_date: 2026-10-04
status: draft
---

# sca-scanner-project-config-isolation - 要件定義書

## 1. 概要

### 1.1 背景
軸 2 の npm / cargo スキャンが、被レビュープロジェクト由来の設定ファイル（`.npmrc`、`.cargo/audit.toml`）を読む。

### 1.2 目的
軸 2 の npm / cargo スキャンが、被レビュープロジェクト由来の設定ファイル（`.npmrc`、`.cargo/audit.toml`）を読まないようにする。

### 1.3 スコープ
- 対象: 軸 2 の npm スキャンと cargo スキャン
- 対象外: pip と go のスキャン（argv / cwd / env、`ECOSYSTEM_ENV_PINS` の値を変えない）

## 2. ビジネス要件

### 2.1 ビジネス目標
軸 2 の npm / cargo スキャンが、被レビュープロジェクト由来の設定ファイル（`.npmrc`、`.cargo/audit.toml`）を読まないようにする。PR 作者は設定ファイルを置くだけではクリーンなスキャン結果を偽装できなくなる。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| レビュー実行者 | 軸 2 のスキャンを実行する。HOME、npm の globalconfig、Cargo ホームの `audit.toml`、advisory DB を管理する |
| PR 作者 | 被レビュープロジェクトのファイルを変更できる。レビュー実行者が管理する設定は変更できない |

### 2.3 期待される効果
- PR 作者は設定ファイルを置くだけではクリーンなスキャン結果を偽装できなくなる

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター |
|----|----------------|----------|
| UC01 | 軸 2 の npm / cargo スキャンを実行する | レビュー実行者 |

### 3.2 ユースケース詳細

#### UC01: 軸 2 の npm / cargo スキャンを実行する

**アクター**: レビュー実行者

**事前条件**:
- スキャングループが紐付け検査を通っている

**基本フロー**:
1. スキャングループごとに、被レビューツリーの外に隔離ディレクトリを作る（FR6、FR8）
2. コピー元を紐付け検査と同じ規則で検証し、隔離ディレクトリへコピーする（FR1、FR2、FR5）
3. 隔離ディレクトリを cwd にしてスキャナを起動する（FR1、FR2、FR3）
4. 隔離ディレクトリを削除する（FR8）

**代替フロー**:
- 隔離ディレクトリの作成・コピー・検証のどれかが失敗したら、スキャナを起動せず、そのスキャン単位を `not_completed` にする。他のグループは続けて走査する（FR7）

**事後条件**:
- 隔離ディレクトリは残っていない
- 実プロジェクトルートの内側には何も作られておらず、何も書かれていない

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | npm スキャンを隔離ディレクトリで実行 | `package.json` とアンカーの lockfile を隔離ディレクトリへコピーし、そこを cwd にして `npm audit` を起動する |
| FR2 | cargo スキャンを隔離ディレクトリで `--file` 付きで実行 | `Cargo.lock` を隔離ディレクトリへコピーし、そこを cwd にして `--file <コピー>` 付きで cargo-audit を起動する |
| FR3 | cargo の対象指定を明示 | `--file` をレジストリとジョブ組み立ての両方で明示する |
| FR4 | 隔離準備は実行側で行う | 隔離の準備は紐付け検査の後に実行側で行い、`build_scan_job` は準備済みのパスを受け取るだけにする |
| FR5 | コピー元の検証とコピーの形 | コピー元を紐付け検査と同じ規則で検証し、内容を変えず通常ファイルとしてコピーする |
| FR6 | 隔離ディレクトリの置き場所の検証 | 一時ディレクトリの親と隔離ディレクトリ自身を realpath で確かめる |
| FR7 | 隔離失敗時の扱い | 隔離に失敗したらスキャナを起動せず、`<ecosystem>_isolation_failed` を返す |
| FR8 | 隔離ディレクトリの寿命 | グループごとに 1 つ、所有者だけがアクセスできる権限で作り、どの場合も削除する |
| FR9 | ラベルと既存の振る舞いを保つ | ラベル、直接依存の判定、グループ化、紐付け検査、処理順、`skip_reason` の組み立てを変えない |
| FR10 | pip と go は変えない | pip と go のジョブと `ECOSYSTEM_ENV_PINS` の値を変えない |
| FR11 | 信頼する設定の範囲 | レビュー実行者が管理する設定の範囲を明記し、既存の env の固定値を保つ |
| FR12 | 再発検出テスト | 記録スタブと敵対的な設定ファイルで `run_scan` を検査する |
| FR13 | 記述の更新 | docstring・コメント・`review-phase.md` の軸 2 の記述を新しい実行場所に合わせる |

### 4.2 機能詳細

#### FR1: npm スキャンを隔離ディレクトリで実行

**説明**: 紐付け検査を通った npm のスキャングループごとに、`package.json` と選ばれたアンカーの lockfile（`npm-shrinkwrap.json` を `package-lock.json` より優先）を、被レビューツリーの外に新しく作った隔離ディレクトリへコピーし、そこを cwd にして `npm audit` を起動する。argv は `[<npm>, audit, --json, --workspaces=false]` のまま。`ECOSYSTEM_ENV_PINS['npm']` の値も変えない。

#### FR2: cargo スキャンを隔離ディレクトリで `--file` 付きで実行

**説明**: 検証済みの `Cargo.lock` を、被レビューツリーの外に新しく作った隔離ディレクトリへコピーし、そこを cwd にして argv `[<cargo-audit>, audit, --file, <コピーのパス>, --json]` で cargo-audit を起動する。`--url` と `--db` は指定しない（advisory DB の設定はレビュー実行者の既定のまま）。

#### FR3: cargo の対象指定を明示

**説明**: cargo の対象指定（`--file`）をレジストリ（`vuln-scanners.yaml`）とジョブ組み立ての両方で明示する。`--file <コピー>` は `audit` サブコマンドの直後に置く。

**ビジネスルール**:
- レジストリに `target_flag` を足すだけでは満たさない

#### FR4: 隔離準備は実行側で行う

**説明**: 隔離の準備（作成・コピー・検証）は、紐付け検査の後に実行側で行う。`build_scan_job` は純粋関数のまま、準備済みのパスを受け取るだけにする。

#### FR5: コピー元の検証とコピーの形

**説明**: コピー元は紐付け検査と同じ規則で検証する。npm は `package.json` と優先順位で選んだアンカー、cargo は `Cargo.lock` をコピーする。

**ビジネスルール**:
- 内容は変えず、通常ファイルとしてコピーする
- 許可されている同一ディレクトリ内のシンボリックリンクは、リンク先の内容をコピーする

#### FR6: 隔離ディレクトリの置き場所の検証

**説明**: 作成前に一時ディレクトリの親を realpath で確かめ、作成後に隔離ディレクトリ自身も realpath で確かめる。

**バリデーション**:
| 項目 | ルール | 結果 |
|------|--------|------|
| 一時ディレクトリの親（作成前） | realpath が被レビューの実プロジェクトルートそのもの、またはその配下でない | 違反時は隔離の失敗として扱い、スキャナは起動しない |
| 隔離ディレクトリ自身（作成後） | realpath が被レビューの実プロジェクトルートそのもの、またはその配下でない | 違反時は隔離の失敗として扱い、スキャナは起動しない |

#### FR7: 隔離失敗時の扱い

**説明**: 隔離ディレクトリの作成・コピー・検証のどれかが失敗したら、スキャナは起動しない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `npm_isolation_failed` | npm の隔離ディレクトリの作成・コピー・検証のどれかが失敗した | スキャナを起動せず、そのスキャン単位を `not_completed` にする |
| `cargo_isolation_failed` | cargo の隔離ディレクトリの作成・コピー・検証のどれかが失敗した | スキャナを起動せず、そのスキャン単位を `not_completed` にする |

**ビジネスルール**:
- 理由はパスを含まない
- プロジェクトディレクトリ内での実行にはフォールバックしない
- 失敗したグループ以外のグループは続けて走査する
- 完了したグループの findings と失敗理由はどちらも結果に残す（`skip_reason` は既存の規則で組み立てる）

#### FR8: 隔離ディレクトリの寿命

**説明**: 隔離ディレクトリはスキャングループごとに 1 つ、名前が他と重ならないものを所有者だけがアクセスできる権限で作る。

**ビジネスルール**:
- 次のどの場合も削除する: 成功、ツールの失敗、タイムアウト、コピーの途中での失敗

#### FR9: ラベルと既存の振る舞いを保つ

**説明**: ジョブの manifest と findings の file は、元のプロジェクト相対パスのままにする。cargo の直接依存の判定は、これまでどおり被レビュープロジェクトの元の `Cargo.toml` を使う。スキャン単位のまとめ方（グループ化）、紐付け検査、処理順、`skip_reason` の組み立ては変えない。

#### FR10: pip と go は変えない

**説明**: pip と go のジョブ（argv / cwd / env）と `ECOSYSTEM_ENV_PINS` の値は変えない。

#### FR11: 信頼する設定の範囲

**説明**: HOME、npm の globalconfig、Cargo ホームの `audit.toml`、advisory DB はレビュー実行者が管理するもので、PR 作者は変更できない。このことを明記する。

**ビジネスルール**:
- 既存の env の固定値は保つ
- レビュー実行者自身の設定を追加で無効化したり上書きしたりはしない

#### FR12: 再発検出テスト

**説明**: PATH に置いたオフラインの記録スタブを使う。プロジェクトに敵対的な `.npmrc`（`https-proxy`、`strict-ssl=false`、`registry`、`cafile`）と `.cargo/audit.toml`（`[advisories] ignore`、`[database] url/path`）を置いて `run_scan` し、次を確かめる。
- スタブの cwd が実プロジェクトルートの外にあること
- cwd とその祖先に `.npmrc` / `.cargo/audit.toml` が無いこと
- コピーした入力の内容が原本と一致すること（隔離ディレクトリが消える前にスタブが記録する）
- cargo の `--file` がコピーを指していること

#### FR13: 記述の更新

**説明**: `ECOSYSTEM_ENV_PINS` / `build_scan_job` / `run_ecosystem_command` / `_scan_bound_group` / `run_scan` の docstring とコメント、`vuln-scanners.yaml` のコメント、`review-phase.md` の軸 2 の記述を、新しい実行場所に合わせて直す。

## 5. 非機能要件

| ID | 名前 | 内容 |
|----|------|------|
| NFR1 | `build_scan_job` の純粋性 | `build_scan_job` はファイルを開かず、プロセスも起動しない |
| NFR2 | 被レビューツリーへの書き込み禁止 | スキャンは実プロジェクトルートの内側に何も作らず、何も書かない |
| NFR3 | パスを含まない理由 | `skip_reason` と summary には固定のトークンだけを入れ、パス文字列を含めない |
| NFR4 | テストの前提 | テストは標準ライブラリの unittest だけで書き、オフラインで結果が毎回同じになる。実物の npm / cargo-audit を前提にしない |

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- データ保護: NFR2、NFR3
- 入力検証: FR5、FR6

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- ドキュメント: FR13
- テスト: NFR4

### 5.5 互換性要件
- FR9、FR10

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| npm（`npm audit`） | 子プロセスとして起動 | 隔離ディレクトリ内の `package.json` とアンカーの lockfile のコピー |
| cargo-audit | 子プロセスとして起動 | 隔離ディレクトリ内の `Cargo.lock` のコピー |

### 8.2 API仕様要件
該当なし

## 9. 制約条件

### 9.1 技術的制約
- `build_scan_job` はファイルを開かず、プロセスも起動しない（NFR1）
- テストは標準ライブラリの unittest だけで書く（NFR4）

### 9.2 ビジネス上の制約
- `plugin.json` / `marketplace.json` の version は変えない（A3）

### 9.3 スケジュール制約
なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/sca-scanner-project-config-isolation/**`
- `test-docs/sca-scanner-project-config-isolation/**`

`feature-docs/sca-scanner-project-config-isolation/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-scanner-project-config-isolation/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/sca-scanner-project-config-isolation/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/sca-scanner-project-config-isolation/` ディレクトリを生成しないが、宣言された `test-docs/sca-scanner-project-config-isolation/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
なし

### 10.2 ビジネスリスク
なし

## 11. 成功基準

### 11.1 受け入れ基準
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

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1、AC2）: npm、ルートに敵対的な `.npmrc` を置いた場合。cwd が外にあること、祖先も含めて `.npmrc` が無いこと、コピーが原本と一致すること、結果が completed になること、ラベルが `package.json` であることを確かめる
- [ ] TS2（AC2）: npm で `npm-shrinkwrap.json` と `package-lock.json` が両方ある場合。shrinkwrap がコピーされることを確かめる
- [ ] TS3（AC3、AC5）: cargo、敵対的な `.cargo/audit.toml` を置いた場合。cwd、argv（`--file` の位置と、`--url` / `--db` が無いこと）、コピーの内容、元の `Cargo.toml` による直接依存の判定を確かめる
- [ ] TS4（AC4）: npm と cargo で、内容の違う複数グループを走査する場合。グループごとに入力が対応することと、処理順・ラベルを確かめる
- [ ] TS5（AC6）: `TMPDIR` / `TEMP` / `TMP` / `tempfile.tempdir` とシンボリックリンクで、一時ディレクトリをツリー内へ向けた場合。isolation_failed になり、起動されず、ツリー内に何も作られないことを確かめる
- [ ] TS6（AC7）: コピーの失敗と、他グループの継続を確かめる
- [ ] TS7（AC8）: 成功、ツールの失敗、タイムアウト、コピーの途中での失敗の後に、隔離ディレクトリが残っていないこと。スタブが cwd の権限を記録して所有者だけであることを確かめる
- [ ] TS8（AC9）: prepared path を渡した `build_scan_job` の純粋性（`open` / `os.open` / `subprocess` を mock で禁止して呼ぶ）
- [ ] TS9（AC10）: pip と go の不変、`ECOSYSTEM_ENV_PINS` の不変、HOME がそのまま渡ることを確かめる

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 隔離ディレクトリ | 被レビューツリーの外に、スキャングループごとに新しく作るディレクトリ。スキャナの cwd になり、スキャン入力のコピーを置く |
| アンカー | npm のスキャングループで選ばれる lockfile。`npm-shrinkwrap.json` を `package-lock.json` より優先する |
| 記録スタブ | PATH に置く、オフラインの npm / cargo-audit の代わり。起動時の cwd・argv・入力の内容などを記録する |

## 14. 確認事項

### 14.1 確認済み事項
- [x] 再発検出テストの方針（`requirement.regression-test-strategy`）: `stub_only`。記録スタブのテストで示す

### 14.2 未確認・保留事項
なし

### 14.3 前提
- A1: 対象は npm と cargo だけ。pip と go は変えない
- A2: 完了の定義のうち「再現手順で現象が起きない」は、設定ファイルがスキャナの探索経路に載らないことを記録スタブのテストで示して満たす
- A3: `plugin.json` / `marketplace.json` の version は変えない

## 15. 参考資料

なし
