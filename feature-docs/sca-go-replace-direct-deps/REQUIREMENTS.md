---
title: "sca-go-replace-direct-deps"
created_date: 2026-10-12
status: draft
---

# sca-go-replace-direct-deps - 要件定義書

## 1. 概要

### 1.1 背景
go.mod が直接 require しているモジュールを別のモジュールに replace しているとき、Go SCA は置換先モジュールの脆弱性を落としていた。

### 1.2 目的
- go.mod が直接 require を別のモジュールに replace しているとき、Go SCA が置換先モジュールの脆弱性を落とさない。そのアドバイザリは finding になる。重大度を判定できないときは `go_severity_undetermined` に数える。
- replace の単一行形式とブロック形式の両方を、退行テストで確認する。

### 1.3 スコープ
- go.mod の `replace` ディレクティブの解析（単一行形式とブロック形式）
- replace を反映した直接依存集合の判定
- `em-workflow/scripts/scan-dependencies.py` の Go 正規化セクションのコメント、`_go_mod_direct_modules` と `normalize_go` の docstring の更新
- リポジトリルートの `tests/` 配下のテスト

## 2. ビジネス要件

### 2.1 ビジネス目標
- go.mod が直接 require を別のモジュールに replace しているとき、Go SCA が置換先モジュールの脆弱性を落とさない。そのアドバイザリは finding になる。重大度を判定できないときは `go_severity_undetermined` に数える。
- replace の単一行形式とブロック形式の両方を退行テストで確認する。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 1.2 目的と同じ

## 3. ユースケース
該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | replace ディレクティブの解析 | ok |
| FR2 | indirect でない require の置換先を直接依存とする | ok |
| FR3 | モジュール置換だけが寄与する | ok |
| FR4 | 元の require パスは直接依存のまま残る | ok |
| FR5 | 一致しない replace は寄与しない | ok |
| FR6 | 先行フィーチャーの FR3 の補足 | ok |

### 4.2 機能詳細

#### FR1: replace ディレクティブの解析

**説明**: go.mod の `replace` ディレクティブを、単一行形式（`replace old [v] => new [v]`）と `replace ( ... )` ブロック形式の両方で読む。

**ビジネスルール**:
- コメントの分離、ダブルクォートとバッククォートの除去、CRLF の扱いは require エントリと同じとする。
- replace エントリは、置換元パス、省略可能な置換元バージョン、`=>`、置換先パス、省略可能な置換先バージョンからなり、それぞれが別のトークンである。
- この形をしていない行は何も寄与しない。
- 不正な内容によって go.mod が読めない扱いになることはない。

#### FR2: indirect でない require の置換先を直接依存とする

**説明**: indirect の印が付いていない require エントリごとに、適用する replace を次のように選ぶ。

**ビジネスルール**:
- 置換元にバージョンがある replace は、そのバージョン文字列が require エントリのバージョンと完全一致するときだけ適用する。
- 置換元にバージョンがない replace は、どのバージョンにも適用する。
- 一致するバージョン付きの replace があるときは、バージョンなしの replace より優先する。
- 適用する replace がモジュール置換（FR3）のとき、その置換先パスを直接依存集合に加える。
- 結果は、replace と require のディレクティブがファイル内のどこにあるかに依存しない。

#### FR3: モジュール置換だけが寄与する

**説明**: 置換先がちょうど「パスとバージョン」で、かつそのパスが Go のディレクトリパス形式でないときだけ、モジュール置換とする。

**ビジネスルール**:
- ディレクトリパス形式とは次のいずれかとする。
    - `.` または `..` に等しい
    - `./`、`../`、`.\`、`..\`、`/`、`\` のいずれかで始まる
    - ASCII 英字の後に `:` が続く形で始まる
- バージョンのない置換先（ローカルディレクトリ）と、バージョン付きのディレクトリパス形式の置換先は何も寄与しない。
- 優先されたバージョン付き replace（FR2）がモジュール置換でないときは何も加えない。同じモジュールのバージョンなし replace へのフォールバックはしない。

#### FR4: 元の require パスは直接依存のまま残る

**説明**: 直接依存集合は、indirect でない require パスと、FR2 で加えた置換先パスの和集合とする。

**ビジネスルール**:
- replace を適用しても、元の require パスは直接依存集合から除かれない。

#### FR5: 一致しない replace は寄与しない

**説明**: 次のものは何も寄与しない。

**ビジネスルール**:
- 置換元がどの require エントリとも一致しない replace
- 置換元が indirect の require エントリとだけ一致する replace
- バージョンが require のバージョンと異なるバージョン付き replace
- 置換先の置換（置換は連鎖しない）

#### FR6: 先行フィーチャーの FR3 の補足

**説明**: このフィーチャーは sca-go-govulncheck-real-output の FR3 を補足する。先行 FR3 は replace が何も寄与しないと定めていたが、replace は FR1〜FR5 のとおり寄与するようになる。

**ビジネスルール**:
- 先行 FR3 のそれ以外の部分は変えない: 完全一致、indirect の印のルール、引用符付きのパス、go.sum を対象とする単位では同じディレクトリの go.mod を使うこと、stdlib / toolchain を直接依存とすること（先行 FR4）。
- 先行フィーチャーのドキュメントは編集しない。
- `em-workflow/scripts/scan-dependencies.py` の Go 正規化セクションのコメント、`_go_mod_direct_modules` の docstring、`normalize_go` の docstring を、新しい動作を説明する内容に更新する。

## 5. 非機能要件

| ID | 区分 | 要件 |
|----|------|------|
| NFR1 | テスト | テストは標準ライブラリの unittest だけを使い、既存の govulncheck スタブの仕組みでオフラインに再生する。`python3 -m unittest discover -s tests` で実行する。replace の単一行形式とブロック形式の両方を対象にする。 |
| NFR2 | 互換性 | 既存のテストはすべて変更なしで通り続ける。`tests/test_sca_go_govulncheck_real_output.py` の :709-712（DIRECT_GO_MODS）、:737-741（NOT_DIRECT_GO_MODS）の replace のケースと、:792-809 のパーサーの完全一致集合のテストを含む。 |
| NFR3 | 出力の安全性とセキュリティ | 新しい skip 理由も要約ノートも追加しない。ノートは件数だけを含み、アドバイザリやパスの文字列を含めない。go.mod と govulncheck のストリームは引き続き信頼できない入力とする。go.mod は既存のプロジェクト相対の封じ込めを通して読むだけで、レビュー対象のプロジェクト内には何も書き込まない。 |

## 6. UI/UX要件
該当なし（UI なし）

## 7. データ要件
該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| govulncheck | `govulncheck -json` の標準出力（テストでは既存のスタブで再生） | JSON オブジェクトのストリーム |

## 9. 制約条件

### 9.1 技術的制約
- テストは標準ライブラリの unittest だけを使い、オフラインで再生する（NFR1）。
- 既存のテストは変更しない（NFR2）。
- 新しい skip 理由と要約ノートは追加しない（NFR3）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/sca-go-replace-direct-deps/**`
- `test-docs/sca-go-replace-direct-deps/**`

`feature-docs/sca-go-replace-direct-deps/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-go-replace-direct-deps/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/sca-go-replace-direct-deps/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/sca-go-replace-direct-deps/` ディレクトリを生成しないが、宣言された `test-docs/sca-go-replace-direct-deps/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| require のバージョンは最小バージョンのため、ビルドが別のバージョンを選ぶと、バージョンの完全一致による replace の判定を誤ることがある（A2 の既知の制約） | — | — |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR2, FR4）: go.mod に `require example.org/text v0.3.6` と単一行の `replace example.org/text => golang.org/x/text v0.3.6` がある。govulncheck のストリームで golang.org/x/text に対するアドバイザリが CVSS v3 の critical / high のベクトルを持つと、package が golang.org/x/text の finding が 1 件出る。同じアドバイザリが CVSS v3 のベクトルを持たないと、`go_severity_undetermined` のノートに数えられる。skipped は false。
- [ ] AC2（FR1, FR2）: AC1 と同じで、replace が `replace ( ... )` ブロックの中に書かれている。
- [ ] AC3（FR3）: 直接 require がローカルディレクトリ（`=> ./text`、`=> ../text`、`=> /abs/text`、`=> .\text`、`=> C:\text`、`=> .`）またはバージョン付きのディレクトリパスに置換されている場合、何も加えない。置換先パスに対するアドバイザリは finding にならず、数えられもしない。
- [ ] AC4（FR5）: 置換元の require に `// indirect` が付いている、または置換元の require エントリがない replace は、何も加えない。
- [ ] AC5（FR2, FR3, FR5）: バージョン付きの replace は、そのバージョンが require のバージョンと等しいときだけ適用される。一致するときは、同じモジュールのバージョンなし replace より優先される。優先された replace がローカルのときは何も加えず、バージョンなし replace へのフォールバックもしない。
- [ ] AC6（FR4）: モジュール置換の後も、元の require パスは直接依存のまま残る。
- [ ] AC7（NFR2）: 既存のテストスイートが変更なしで通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: スタブが golang.org/x/text に対するアドバイザリを含むストリームを出力する。go.mod は `require example.org/text v0.3.6` と、golang.org/x/text v0.3.6 への単一行のバージョンなし replace を持つ。アドバイザリが CVSS v3 のベクトルを持つときは package が golang.org/x/text の high / critical の finding を、持たないときは `go_severity_undetermined` の件数を確認する。
- [ ] TS2（AC2）: TS1 と同じで、replace をブロックに書く。他のエントリやコメントを含むブロックも対象にする。
- [ ] TS3（AC3）: ローカルおよびディレクトリ形式の置換先（`./x`、`../x`、`/x`、`.\x`、`..\x`、`\x`、`C:\x`、`.`、`..`、`./x v1.0.0`）は何も加えない。問題なしの完了結果を確認する。
- [ ] TS4（AC4）: 置換元の require が `// indirect`、または置換元の require がない。何も加えられないことを確認する。
- [ ] TS5（AC5）: require のバージョンと一致するバージョン付きの置換元は置換先を加える。一致しないバージョンは何も加えない。同じモジュールのバージョン付きとバージョンなしの replace が両方あると、バージョン付きの置換先だけが加わる。一致するバージョン付き replace がローカルで、バージョンなしのモジュール replace もあると、何も加わらない。
- [ ] TS6（AC6）: パーサーの単位で、直接依存集合が元のパスと置換先パスの両方を含むことを確認する。
- [ ] TS7（FR1, FR2）: 境界の形: require より前にある replace、両側の引用符付きパス、行末のコメント、CRLF の改行、パスに密着した `=>`（何も寄与しない）、不正な replace（右辺の欠落、余分なトークン。何も寄与しない）、連鎖する A=>B と B=>C（B だけが加わる）。
- [ ] TS8（AC7）: 既存の replace のケースを含め、`python3 -m unittest discover -s tests` の全体実行が通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 直接依存集合 | indirect でない require パスと、FR2 で加えた置換先パスの和集合（FR4） |
| モジュール置換 | 置換先がちょうど「パスとバージョン」で、パスがディレクトリパス形式でない replace（FR3） |
| ディレクトリパス形式 | `.` または `..` に等しい、`./`、`../`、`.\`、`..\`、`/`、`\` のいずれかで始まる、または ASCII 英字の後に `:` が続く形で始まるパス（FR3） |

## 14. 確認事項

### 14.1 確認済み事項
- [x] 機能要件 FR1〜FR6: すべて status: ok

### 14.2 未確認・保留事項
なし

### 14.3 前提
- A1: ローカルパスのルール。置換先が寄与するのは、パスとバージョンがあり、そのパスが Go の IsDirectoryPath の形（`.` または `..`、`./`、`../`、`.\`、`..\`、`/`、`\` で始まるもの、ドライブレター）でないときだけとする。バージョンのない置換先と、バージョン付きのディレクトリパスは何も加えない。
- A2: バージョン付きの置換元の照合。バージョン付きの置換元は require のバージョン文字列と完全一致するときだけ適用し、バージョンなしの置換元はどのバージョンにも適用する。一致するバージョン付き replace はバージョンなしの replace より優先する。優先された置換先がローカルのときは何も加えず、バージョンなし replace へのフォールバックはしない。既知の制約: require のバージョンは最小バージョンのため、ビルドが別のバージョンを選ぶと、バージョンの完全一致でも判定を誤ることがある。
- A3: 直接依存集合は、元の require パスと適用した置換先パスの和集合とする。元のパスは直接依存のまま残る。
- A4: 先行フィーチャーのドキュメント（sca-go-govulncheck-real-output の SPEC.md、REQUIREMENTS.md、tasks/task0001.md）は履歴として編集しない。新しい SPEC に、先行 FR3 を補足することを記載する。scan-dependencies.py の docstring とコメントは更新する。
- A5: 置換は 1 回だけ適用し、連鎖しない（A の直接 require に対して A=>B と B=>C があると、B だけを加える）。
- A6: replace の解析は、既存の go.mod のトークン分割、コメントの分離、引用符の除去を再利用する。不正な replace の内容は何も寄与せず、skip 理由もノートも追加しない。
- A7: `tests/test_sca_go_govulncheck_real_output.py` の既存のテストは、:709-712、:737-741、:792-809 の replace のケースを含め、すべて変更なしで通り続ける。
- A8: このフィーチャーでプラグインの version は変えない。patch の引き上げは GitHub Actions に任せる。

## 15. 参考資料

- SPEC.md: `feature-docs/sca-go-replace-direct-deps/SPEC.md`
- 補足対象の先行フィーチャー: `feature-docs/sca-go-govulncheck-real-output/REQUIREMENTS.md`
