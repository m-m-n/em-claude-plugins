---
title: "sca-go-govulncheck-real-output"
created_date: 2026-10-04
status: draft
---

# sca-go-govulncheck-real-output - 要件定義書

## 1. 概要

### 1.1 背景
実際の脆弱性を持つ Go プロジェクトに SCA 軸を実行したとき、findings 0・skipped false・skip_reason null で、何の信号もないまま「脆弱性なし」と報告される結果を防ぐ。

### 1.2 目的
- 実際の脆弱性を持つ Go プロジェクトに SCA 軸を実行したとき、何の信号もなく「脆弱性なし」（findings 0、skipped false、skip_reason null）と報告しない。
- 実際の `govulncheck -json` のキャプチャを Go の正規化処理に再生するテストで、退行を検出する。

### 1.3 スコープ
- SCA 軸の Go 正規化処理（重大度判定、直接依存判定、finding の集約、ストリームの有効性判定、修正バージョンの取得）
- `run_scan` の要約ノートと skip 理由
- 実際の govulncheck キャプチャのフィクスチャとその出自ノート
- リポジトリルートの `tests/` 配下のテスト

## 2. ビジネス要件

### 2.1 ビジネス目標
- 実際の脆弱性を持つ Go プロジェクトに SCA 軸を実行したとき、何の信号もなく「脆弱性なし」と報告しない。
- 実際の govulncheck 出力を再生するテストで退行を検出する。

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
| FR1 | 出力された CVSS v3 ベクトルからの重大度判定 | confirmed |
| FR2 | 重大度未確定を閾値未満と扱わず件数に数える | confirmed |
| FR3 | go.mod の require エントリによる直接依存判定 | confirmed |
| FR4 | stdlib / toolchain を直接依存として扱う | confirmed |
| FR5 | スキャン単位ごとに (OSV id, モジュール) あたり 1 件の finding | confirmed |
| FR6 | 出自つきの実 govulncheck キャプチャのフィクスチャ | confirmed |
| FR7 | 合成された単一オブジェクト形式の廃止 | confirmed |
| FR8 | go.mod を読めない単位は未完了とする | confirmed |
| FR9 | Go ストリームの有効性 | confirmed |
| FR10 | fixed_version を finding のモジュールに限定する | confirmed |

### 4.2 機能詳細

#### FR1: 出力された CVSS v3 ベクトルからの重大度判定

**説明**: Go アドバイザリの重大度は、OSV オブジェクトのトップレベルの `severity[]` 配列からのみ求める。

**ビジネスルール**:
- `type` が `CVSS_V3` で、score のベクトルが `CVSS:3.0/` または `CVSS:3.1/` で始まり、`_cvss_severity_band` で解析できるエントリをすべて対象にする。
- 得られたバンドのうち最も高いものを採用し、レジストリの `severity_map` で対応付ける。
- `type` が `CVSS_V4` のエントリ、およびその他の type のエントリは無視する。
- `osv.database_specific.severity` は読まない。

#### FR2: 重大度未確定を閾値未満と扱わず件数に数える

**説明**: FR1 に該当する有効な CVSS v3 ベクトルを持たないアドバイザリは、重大度未確定とする。

**ビジネスルール**:
- 重大度未確定のアドバイザリは findings に含めない。
- 直接依存（FR3 / FR4）であれば件数に数える。
- スキャン単位ごとの未確定件数を、実行全体で合計する。
- 合計が 0 でないとき、`run_scan` は件数のみの要約ノートを pip と同じ形式で追記する: ` N go advisory|advisories with undetermined severity (go_severity_undetermined).`
- 要約ノートにアドバイザリ由来の文字列は含めない。
- 重大度未確定によって skip 理由は追加しない。skipped / skip_reason は「すべての単位が完了したか」だけを表す。
- バンドが確定し、high 未満のアドバイザリは従来どおり除外する。

#### FR3: go.mod の require エントリによる直接依存判定

**説明**: finding のモジュール（`trace[0].module`）が、バインドされたプロジェクトの go.mod にある `// indirect` 付きでない require エントリのモジュールパスと完全一致するとき、直接依存とする。

**ビジネスルール**:
- 単一行の `require m v` 形式と `require ( ... )` ブロックの両方を対象にする。
- 引用符付きのモジュールパスは引用符を外して比較する。
- その他のディレクティブ（`module`、`go`、`toolchain`、`replace`、`exclude`、`retract`、`tool`）とコメントは判定に寄与しない。
- go.mod はバインドされたプロジェクトディレクトリから読む。
- 単位の対象が go.sum のときは、同じディレクトリにある go.mod を使う。パスは既存のプロジェクト相対の封じ込めで解決する。
- `normalize_go` は、cargo のノーマライザと同様に `project_root` を受け取る。
- trace の長さは直接依存の判定に影響しない。

#### FR4: stdlib / toolchain を直接依存として扱う

**説明**: モジュールが `stdlib` または `toolchain` の finding は直接依存として扱い、同じ重大度ルール（FR1、FR2）を適用する。

#### FR5: スキャン単位ごとに (OSV id, モジュール) あたり 1 件の finding

**説明**: 1 つのスキャン単位（バインドされた 1 つのプロジェクトディレクトリ）の中で、OSV id とモジュールが同じ govulncheck の finding オブジェクトは、レベルや trace の数によらず 1 件のスキャン finding にまとめる。

**ビジネスルール**:
- 直接依存の判定と未確定件数の計上は、まとめたアドバイザリに 1 回だけ適用する。
- まとめと計上はプロジェクト単位ごとに行う。
- 異なるプロジェクト単位の finding はすべて残す。

#### FR6: 出自つきの実 govulncheck キャプチャのフィクスチャ

**説明**: `GO_FIXTURE` を実際のキャプチャに置き換える。

**ビジネスルール**:
- キャプチャは `govulncheck -json` の標準出力とする。既知の脆弱な依存バージョンを require する最小の Go モジュールに対して `go run golang.org/x/vuln/cmd/govulncheck@<固定バージョン> -json ./...` を実行して得る。
- リポジトリルートの `tests/` 配下に、テキストファイルとしてそのまま保存する。マシン固有の絶対パスはプレースホルダに置き換える。
- キャプチャの隣に出自ノートを置く。出自ノートには govulncheck のバージョン、go のバージョン、正確なコマンド、最小モジュールの go.mod、キャプチャ日を記載する。
- テストのスタブは、生のストリームテキストをそのまま出力する（解析済みオブジェクトの `json.dumps` ではない）。
- テストはオフラインで再生する。
- キャプチャを生成できない場合、実装タスクはストリームを手作りせず blocked を報告する。

#### FR7: 合成された単一オブジェクト形式の廃止

**説明**: go の経路は、合成された単一オブジェクトの `{"vulns": [...]}` ペイロードを受け付けない。

**ビジネスルール**:
- このペイロードには config オブジェクトがないため、FR9 により `go_unparseable_output` となる。
- `tests/test_sca_per_project_scan_binding.py` の `GO_PAYLOAD` と go のスタブは、config オブジェクトを含む実際の脆弱性なしストリームに切り替える。
- `_merge_govulncheck_stream` の docstring から、単一オブジェクト互換の記述を除く。

#### FR8: go.mod を読めない単位は未完了とする

**説明**: 正規化の時点で、バインドされたプロジェクトの go.mod を開けない、読めない、または UTF-8 としてデコードできない場合、その Go 単位は finding を出さず、パスを含まない理由 `go_direct_manifest_unreadable` を報告する。

**ビジネスルール**:
- 実行は `skipped: true` となり、理由は通常どおり結合する（ソート、重複除去、`+` 連結）。
- 他の単位の finding は残す。
- 空の直接依存集合へのフォールバックはしない。

#### FR9: Go ストリームの有効性

**説明**: go では、標準出力が 1 個以上の JSON オブジェクトのストリームとして解析でき、かつ値がオブジェクトである `config` キーを持つトップレベルのオブジェクトを 1 個以上含むときにだけ、完了したスキャン結果とする。

**ビジネスルール**:
- ストリームが 1 オブジェクトでも複数オブジェクトでも同じ条件を適用する。
- 条件を満たさないものは `go_unparseable_output` とする。
- `finding` オブジェクトを含まない有効なストリームは、問題なしの完了結果とする。
- 既存の空出力チェック（`go_empty_output`）の優先順位は変えない。
- 文書化された終了ステータス（`{0, 3}`）は変えない。

#### FR10: fixed_version を finding のモジュールに限定する

**説明**: Go の finding の修正バージョンは、`package.name` がその finding のモジュールと一致する `osv.affected` エントリからのみ求める。

**ビジネスルール**:
- 他モジュールの affected エントリにある fixed イベントは使わない。

## 5. 非機能要件

| ID | 区分 | 要件 |
|----|------|------|
| NFR1 | テスト | テストは標準ライブラリの unittest だけを使い、オフラインで動く（テスト時に go、govulncheck、ネットワークを使わない）。テストはリポジトリルートの `tests/` 配下に置く（`em-workflow/` の外で、配布されない）。 |
| NFR2 | フィクスチャ | キャプチャと出自ノートはテキストファイルとする。マシン固有の絶対パス（キャプチャしたユーザーのホームや一時ディレクトリなど）を含めない。 |
| NFR3 | セキュリティ | 要約ノートと skip 理由には件数と固定トークンだけを含め、アドバイザリ由来の文字列やパスを含めない。finding 内のアドバイザリ由来の文字列は引き続き `truncate_untrusted` を通す。 |
| NFR4 | セキュリティ | スキャンはレビュー対象のプロジェクトルート内に何も書き込まない。go.mod は読むだけで、検証済みのバインドされたプロジェクトディレクトリからのみ読む。govulncheck のストリームの内容と go.mod の内容は信頼できない入力として扱う。 |
| NFR5 | 互換性 | npm、cargo、pip の動作は変えない。 |

## 6. UI/UX要件
該当なし（UI なし）

## 7. データ要件
該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| govulncheck | `govulncheck -json` の標準出力 | JSON オブジェクトのストリーム |

## 9. 制約条件

### 9.1 技術的制約
- テスト時に go、govulncheck、ネットワークを使わない（NFR1）。
- npm、cargo、pip の動作は変えない（NFR5）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/sca-go-govulncheck-real-output/**`
- `test-docs/sca-go-govulncheck-real-output/**`

`feature-docs/sca-go-govulncheck-real-output/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-go-govulncheck-real-output/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/sca-go-govulncheck-real-output/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/sca-go-govulncheck-real-output/` ディレクトリを生成しないが、宣言された `test-docs/sca-go-govulncheck-real-output/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 実際のキャプチャを生成できない | — | 実装タスクはストリームを手作りせず blocked を報告する（FR6） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR2, FR3, FR6）: 脆弱なモジュールを直接 require する（`// indirect` なし）go.mod で実際のキャプチャを再生すると、high / critical の finding（アドバイザリが有効な CVSS v3 ベクトルを持つ場合）、または `go_severity_undetermined` として数える要約ノートのどちらかが出る。未確定ノートのない findings 0 + skipped false + skip_reason null は決して返さない。
- [ ] AC2（FR3）: 同じキャプチャで、脆弱なモジュールが `// indirect` としてだけ記載されている（または require にない）場合、そのアドバイザリについて finding も未確定件数も出ない。
- [ ] AC3（FR1）: CVSS_V3 エントリが複数ある場合、有効なバンドのうち最も高いものが採用される。CVSS_V4 だけ、または不正なベクトルの場合は未確定となる。
- [ ] AC4（FR4）: stdlib（または toolchain）の finding は、go.mod の内容によらず直接依存として扱われる。
- [ ] AC5（FR5）: 1 つの単位で OSV id とモジュールが同じ finding オブジェクトが複数あると、1 件の finding（または 1 件の未確定件数）になる。同じアドバイザリが 2 つのプロジェクト単位にあると、単位ごとに 1 件ずつの finding になる。
- [ ] AC6（FR7, FR9）: 単一オブジェクトの `{"vulns": [...]}` ペイロードと config オブジェクトのないストリームは、skipped true と `go_unparseable_output` になる。finding オブジェクトのない config 付きストリームは、findings [] と skipped false で完了する。空の標準出力は引き続き `go_empty_output` になる。
- [ ] AC7（FR8）: バインドされた単位の go.mod が読めない、または UTF-8 でない場合、skipped true で skip_reason に `go_direct_manifest_unreadable` を含み、他の単位の finding は残る。
- [ ] AC8（FR10）: description 内の finding の修正バージョンは、`package.name` がそのモジュールと一致する affected エントリから取られる。他の affected エントリが fixed イベントを持っていても同じ。
- [ ] AC9（FR6）: キャプチャファイルと出自ノートが `tests/` 配下にある。出自ノートに govulncheck のバージョン、go のバージョン、コマンド、最小の go.mod、キャプチャ日が記録されている。キャプチャにマシン固有の絶対パスが含まれない。
- [ ] AC10: `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` の両方が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: スタブが生のキャプチャを出力する。go.mod は脆弱なモジュールを直接 require する。high / critical の finding、または期待件数の `go_severity_undetermined` ノートを確認する。skipped false。
- [ ] TS2（AC2）: 同じキャプチャで、モジュールを `// indirect` とする。そのモジュールの finding も未確定ノートもないことを確認する。
- [ ] TS3（AC3）: キャプチャから派生させたストリームで、OSV の `severity[]` に CVSS:3.1 の high ベクトルと critical ベクトル、CVSS_V4 エントリ、または不正なベクトルを持たせる。バンドの選択、または未確定を確認する。
- [ ] TS4（AC4）: require を持たない go.mod での stdlib の finding。直接依存として扱われることを確認する。
- [ ] TS5（AC5）: 1 つの単位で、1 つの OSV id に対するモジュール・パッケージ・シンボルの各レベルのオブジェクトが 1 件の結果になる。2 つのバインドされたプロジェクト単位がそれぞれそのアドバイザリを持つと 2 件の finding になる。
- [ ] TS6（AC6）: 単一オブジェクトの `{vulns}` ペイロード、config のないストリーム、config だけの問題なしストリーム、空の標準出力。
- [ ] TS7（AC7）: バインドされた単位の go.mod が不正な UTF-8 バイトを含み、隣に完了する npm の単位がある。
- [ ] TS8（AC8）: 異なるモジュールに対する 2 つの affected エントリを持ち、それぞれ異なる fixed イベントを持つ OSV。
- [ ] TS9（AC9）: 構造の確認。キャプチャファイルが config オブジェクトと 1 個以上の finding を含むオブジェクトストリームとして解析でき、どちらのファイルにも `/home/` や `/tmp/` のような絶対パスが含まれない。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 重大度未確定 | FR1 に該当する有効な CVSS v3 ベクトルを持たないアドバイザリの状態（FR2） |
| スキャン単位 | バインドされた 1 つのプロジェクトディレクトリ（FR5） |

## 14. 確認事項

### 14.1 確認済み事項
- [x] 機能要件 FR1〜FR10: すべて status: confirmed

### 14.2 未確認・保留事項
なし

### 14.3 前提
- A1: go.mod の require エントリで `// indirect` が付いたものは直接依存ではない。
- A2: go.sum を対象とする単位では、同じバインドされたディレクトリにある go.mod から直接依存を判定する。
- A3: 解析するのは CVSS 3.0 / 3.1 のベクトルだけとする。その他の重大度の type は未確定として数える（FR1 の最大バンドのルールで具体化される）。
- A4: 不具合修正のため、em-workflow の version を手で上げない。Actions による patch の引き上げが適用される。
- A5: キャプチャのフィクスチャと出自ノートは、リポジトリルートの `tests/` 配下にテキストとして置く。

## 15. 参考資料

- SPEC.md: `feature-docs/sca-go-govulncheck-real-output/SPEC.md`
