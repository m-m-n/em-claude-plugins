---
title: "sca-file-tasks-robustness"
created_date: 2026-10-05
status: draft
---

# sca-file-tasks-robustness - 要件定義書

## 1. 概要

### 1.1 背景
本機能は次の 4 点を扱う。

- advisory の短いタイトルに含まれる空白（改行を含む）と、finding タイトルからの (package, advisory_id) の復元
- file-tasks の起票処理中に発生する OSError
- コミットされるラウンド記録（triage_filing レシート）での、一部失敗と完全成功の区別、および起票されなかったパッケージの記録
- テストと本番での run_scan / build_scan_jobs のコード経路の一致

### 1.2 目的
- スキャンが出したすべての脆弱性 finding を、file-tasks がタスクまたはレポート項目にできる。
- 起票が途中で失敗しても file-tasks はクラッシュせず、起票済みのパッケージの記録を保持する。
- コミットされるラウンド記録で、一部の起票失敗と完全成功の違いが分かる。起票されなかったパッケージ名も記録に残る。
- テストと本番が同じコード経路を通る。run_scan は build_scan_jobs を使う。

### 1.3 スコープ
**対象**:
- `_build_finding` のタイトル組み立て（pip / npm / cargo / go の各 normalizer のタイトル元）
- `recover_package_advisory` / `group_findings_by_package` / `file_tasks` による往復
- `create_security_task` / `append_security_task_references` の OSError と `main` の出力
- review-phase.md の triage_filing レシート（R4、R5 の YAML 例、R5 の本文）と、R6・batch 最終結果での報告
- `build_scan_jobs` / `run_scan`
- 上記のテスト

**対象外**:
- レポート分岐での `write_report` または `mkdir` の OSError
- デザインステップ

## 2. ビジネス要件

### 2.1 ビジネス目標
- スキャンが出したすべての脆弱性 finding を、file-tasks がタスクまたはレポート項目にできる。
- 起票が途中で失敗しても file-tasks はクラッシュせず、起票済みのパッケージの記録を保持する。
- コミットされるラウンド記録で、一部の起票失敗と完全成功の違いが分かる。起票されなかったパッケージ名も記録に残る。
- テストと本番が同じコード経路を通る。run_scan は build_scan_jobs を使う。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
該当なし

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | タイトルの空白をまとめる | `_build_finding` がタイトルを組み立てる前に、advisory の短いタイトルの空白の連続を 1 個の空白にまとめる | — |
| FR2 | スキャンから file_tasks までの往復 | 複数行の advisory から作ったタイトルが復元・分類・起票まで通る | — |
| FR3 | 起票ヘルパーの OSError を EntryPointError にする | 起票中の OSError を既存の break-and-return 経路に流す | — |
| FR4 | triage_filing レシートの拡張 | review-phase.md の 3 箇所でレシートに 5 項目を加える | — |
| FR5 | 試行されなかったパッケージの記録と報告 | summary に `unattempted_packages` を加え、R6 と batch 最終結果で報告する | — |
| FR6 | run_scan が build_scan_jobs を使う（plan-units） | build_scan_jobs を唯一の計画段階にし、run_scan はその plan を使う | — |

### 4.2 機能詳細

#### FR1: タイトルの空白をまとめる

**説明**: `_build_finding` はタイトルを組み立てる前に、advisory の短いタイトルに含まれる空白の連続（改行を含む）をすべて 1 個の空白にまとめ、両端を取り除く。

**ビジネスルール**:
- 空白をまとめる処理は、`truncate_untrusted` がタイトルを切り詰めるより前に行う。
- 対象は pip の `_pip_advisory_headline`、および npm / cargo / go のタイトル元。

#### FR2: スキャンから file_tasks までの往復

**説明**: 各 normalizer は、本文が複数行にわたる advisory からタイトルを組み立てる。そのタイトルについて次が成り立つ。

- `recover_package_advisory` が元の (package, advisory_id) を復元する。
- `group_findings_by_package` が malformed に分類しない。
- `file_tasks` がタスクまたはレポート項目にする。

**ビジネスルール**:
- 往復の保証は、空白を含まないパッケージ名と advisory id を対象とする。空白を含む名前や id は malformed のままとする。

#### FR3: 起票ヘルパーの OSError を EntryPointError にする

**説明**: `create_security_task` と `append_security_task_references` は、サブプロセスの起動時または一時ファイルの書き込み時に OSError を送出しうる。この OSError を EntryPointError にし、既存の break-and-return 経路に流す。途中失敗の経路はこの 1 つだけのままとする。

**出力**:
- summary: 起票済みのパッケージ、`failed_package`、`failure_reason`（`task_create_failed` / `task_update_failed`）を記録する。
- `main`: stdout に JSON オブジェクトをちょうど 1 つ出力し、終了コード 0 で終わる。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| サブプロセス起動または一時ファイル書き込みの OSError | `create_security_task` 内 | EntryPointError にして break-and-return。`failure_reason` は `task_create_failed` |
| サブプロセス起動または一時ファイル書き込みの OSError | `append_security_task_references` 内 | EntryPointError にして break-and-return。`failure_reason` は `task_update_failed` |

#### FR4: triage_filing レシートの拡張

**説明**: review-phase.md はレシートを 3 箇所で定義している。R4「The receipt」、R5 の YAML 例、R5 の本文。3 箇所すべてで、レシートに `failed_package`、`failure_reason`、`malformed_findings`、`listing_dropped_count`、`unattempted_packages`（FR5）を加える。

**出力**（disposition が another-round のときの値）:
| 項目 | 値 |
|------|----|
| `failed_package` | null |
| `failure_reason` | null |
| `malformed_findings` | [] |
| `listing_dropped_count` | 0 |
| `unattempted_packages` | [] |

#### FR5: 試行されなかったパッケージの記録と報告

**説明**: `file_tasks` は summary に 5 つ目のキー `unattempted_packages` を加える。

**出力**:
- `unattempted_packages`: 失敗したパッケージと、それ以降の試行されなかったすべてのパッケージ。

**ビジネスルール**:
- 並び順はグループを処理した順（復元・重複除去・切り詰めの後の順）とする。malformed な finding は含めない。
- すべての return 分岐が `unattempted_packages` を含む。完全成功では []、レポート分岐と degraded レポート分岐でも [] とする。
- `file_tasks` の docstring は、追加キーの数を 4 から 5 に改める。
- review-phase.md に次を記載する。
    - 自動再試行は行わない。
    - `unattempted_packages` が空でないとき、そのパッケージを添えて「triage filing incomplete」を R6 と batch 最終結果で報告する（batch モードでは R6 単体は表示されない）。
    - review の完了条件は変わらない。
    - file-tasks を再実行すると、重複検出により残りだけが起票される。これは最新の listing に起票済みのパッケージが反映されている場合に限り成り立つ。

#### FR6: run_scan が build_scan_jobs を使う（plan-units）

**説明**: `build_scan_jobs` を唯一の計画段階にする。`build_scan_jobs` は検証、解決、`_verified_groups` による実パスでのグループ化、ターゲット選択を行い、(plans, skip_reasons) を返す。各 plan は起動前の 1 グループ分の単位で、ecosystem、directory/real root、files、target、executable を持つ。`run_scan` はその plan をそのまま使い、ターゲットを選び直さない。

**ビジネスルール**:
- 実行側は、バインディング検査、グループごとの隔離ディレクトリ、pip ロックファイルの準備、`build_scan_job` を現在の順序のまま持つ。
    - 検証または解決に失敗したときはパス検査を行わない。
    - 隔離ディレクトリはバインディング検査が通った後にだけ準備する。
- グループの順序、検証されていない pip パスの扱い、出力オブジェクト、理由文字列は変えない。
- `build_scan_jobs` の docstring から「run_scan does not use this function」の文を削除する。
- `build_scan_jobs` から組み立て済みの job dict を期待していたテストは、plan を検査する形に書き換える。argv/env/cwd の検査は `build_scan_job` と `run_scan` のテストへ移す。

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | `run_scan` の外から見える振る舞いを変えない。対象は出力オブジェクト、skip_reason のトークン、実パスでのグループ化、バインディング検査、グループごとの隔離ディレクトリとその削除、pip ロックファイルの準備、summary の注記、グループの順序。 |
| NFR2 | advisory 由来の文字列や OSError のメッセージを、`failure_reason`、malformed の理由、`unattempted_packages`、レシートに入れない。これらは stderr にだけ出す。理由は固定トークンのままとする。 |
| NFR3 | スクリプトとテストは標準ライブラリだけを使う（test/README.md）。 |
| NFR4 | プラグインの version を変えない（.claude/rules/core-plugin-version-bump.md）。 |
| NFR5 | 既存の `file_tasks` summary キーは名前と意味を保つ。summary に加わるのは `unattempted_packages` だけとする。 |
| NFR6 | triage_filing レシートと「triage filing incomplete」の報告は、ゲート識別子を追加せず、完了ゲートに影響しない。 |

## 6. UI/UX要件

該当なし（UI を持たない。変更は Python スクリプト、Markdown リファレンス、テストに限られる）

## 7. データ要件

### 7.1 データモデル概要
該当なし

### 7.2 データ項目
| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| file_tasks summary | `unattempted_packages` | list | ○ | 失敗したパッケージと、それ以降の試行されなかったパッケージ（処理順、malformed を除く）。すべての return 分岐にある |
| file_tasks summary | `failed_package` | — | — | 起票に失敗したパッケージ |
| file_tasks summary | `failure_reason` | 固定トークン | — | `task_create_failed` / `task_update_failed` |
| triage_filing レシート | `failed_package` | — | ○ | another-round では null |
| triage_filing レシート | `failure_reason` | 固定トークン | ○ | another-round では null |
| triage_filing レシート | `malformed_findings` | list | ○ | another-round では [] |
| triage_filing レシート | `listing_dropped_count` | 整数 | ○ | another-round では 0 |
| triage_filing レシート | `unattempted_packages` | list | ○ | another-round では [] |
| build_scan_jobs の plan | ecosystem / directory・real root / files / target / executable | — | ○ | 起動前の 1 グループ分の単位 |

### 7.3 データ保持期間
該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- スクリプトとテストは標準ライブラリだけを使う（NFR3）。
- プラグインの version を変えない（NFR4）。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/sca-file-tasks-robustness/**`
- `test-docs/sca-file-tasks-robustness/**`

`feature-docs/sca-file-tasks-robustness/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/sca-file-tasks-robustness/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/sca-file-tasks-robustness/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/sca-file-tasks-robustness/` ディレクトリを生成しないが、宣言された `test-docs/sca-file-tasks-robustness/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 説明文に改行を含む（CVSS ベクトル付きの）pip advisory から作った finding のタイトルに改行が無い。`recover_package_advisory` がそれを復元し、`file_tasks` がタスクまたはレポート項目にする。
- [ ] AC2: 往復テストが 4 つの normalizer すべてを対象とし、複数行の本文と、4096 バイトを超えて切り詰められたタイトルを含む。修正が無いとこのテストは失敗する。
- [ ] AC3: 3 パッケージのバッチで、2 つ目のパッケージの create または update の起動が OSError で失敗する。終了コードは 0 で、stdout には JSON オブジェクトがちょうど 1 つある。`filed_packages`（または `appended_packages`）は 1 つ目を含み、`failed_package` は 2 つ目、`unattempted_packages` は [2 つ目, 3 つ目]。3 つ目は試行されず、トレースバックは出ない。
- [ ] AC4: 一時ファイルの書き込み失敗も AC3 と同じに扱われる。
- [ ] AC5: 既存の `listing_launch_failed` の degraded 動作（最初から不正な shebang）は変わらない。
- [ ] AC6: review-phase.md のレシート 3 箇所すべてが `failed_package` / `failure_reason` / `malformed_findings` / `listing_dropped_count` / `unattempted_packages` を持つ。`test_sca_axis_triage_timing` が固定している既存の文字列は残る（「empty when this round's disposition was `another-round`」「introduces no new gate identifier」「never affects the completion gate」、および triage_filing が rework_required の後に置かれていることを含む）。
- [ ] AC7: review-phase.md に次が記載されている。自動再試行は無い。パッケージを添えた「triage filing incomplete」が R6 と batch 最終結果に出る。完了条件は変わらない。listing に起票済みのパッケージが反映されていれば、再実行で残りだけが起票される。
- [ ] AC8: `unattempted_packages` は完全成功、レポート分岐、degraded レポート分岐で [] になる。最初のパッケージで失敗すると、malformed でないすべてのパッケージが入る。malformed な finding は入らない。
- [ ] AC9: `run_scan` は `build_scan_jobs` を呼び、その戻り値の plan を使う。`run_scan` の端から端までのテストと `build_scan_jobs` の plan テストの両方がこの経路を通る。argv/env/cwd の検査は `build_scan_job` と `run_scan` のテストにある。
- [ ] AC10: `python3 -m unittest discover -s tests` がすべて通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1/AC2）: pip / npm / cargo / go の各 normalizer に、本文に LF、CRLF、タブ、Unicode の空白を含む advisory、空白だけのタイトル、4096 バイトを超えるタイトルを与える。finding のタイトルに改行が無く、`recover_package_advisory` が元の (package, advisory_id) を返すことを確かめる。結果を `file_tasks` に通し、タスクまたはレポート項目ができることを確かめる。
- [ ] TS2（AC3）: 2 つ目のパッケージで create の起動が OSError で失敗する代役のエントリポイントを使う（listing の後に不正な shebang を置く）。終了コード 0、JSON オブジェクト 1 つ、filed=[1 つ目]、`failed_package`=2 つ目、`failure_reason`=`task_create_failed`、`unattempted_packages`=[2 つ目, 3 つ目] を確かめる。
- [ ] TS3（AC3）: TS2 と同じことを append 経路（既存の未完了タスク）で行う。`failure_reason`=`task_update_failed`。
- [ ] TS4（AC4）: 一時ファイルの書き込みが OSError を送出する。TS2 と同じに扱われる。
- [ ] TS5（AC8）: 最初のパッケージで失敗する。filed は空、`unattempted_packages` は処理順ですべてのパッケージを含み、malformed な finding は含まない。
- [ ] TS6（AC8）: 完全成功、レポート分岐、degraded レポート分岐で `unattempted_packages` == []。
- [ ] TS7（AC5）: 既存の `listing_launch_failed` の degraded ケースが変わらない。
- [ ] TS8（AC6/AC7）: review-phase.md の文書テキストのテスト。R4、R5 の YAML、R5 の本文にある 5 項目、試行されなかったパッケージの規則、R6 / batch 最終結果での報告、既存の固定文字列。
- [ ] TS9（AC9）: `build_scan_jobs` のグループ化・順序・理由のテストを plan の検査に書き換える。エイリアスと「..」を含むパスの実パスでのグループ化も含む。argv/env/cwd の検査は `build_scan_job` と `run_scan` へ移す。`run_scan` が `build_scan_jobs` を通ることを、たとえばテストダブルへの差し替えで示す。
- [ ] TS10（NFR1）: 既存の `run_scan` の端から端までのスイート（実行、正規化、バインディング、隔離、pip ロックファイル）が、観測している振る舞いを変えずに通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| `unattempted_packages` | 失敗したパッケージと、それ以降の試行されなかったすべてのパッケージ。処理順で並び、malformed な finding を含まない |
| plan | `build_scan_jobs` が返す、起動前の 1 グループ分の単位。ecosystem、directory/real root、files、target、executable を持つ |
| triage_filing レシート | review-phase.md の R4「The receipt」、R5 の YAML 例、R5 の本文で定義されるラウンド記録 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] build_scan_jobs の統一方法（q-build-scan-jobs-unification）: plan-units で統一する。`build_scan_jobs` は起動前のグループ単位の (plans, skip_reasons) を返す。`run_scan` はバインディング検査、隔離、pip ロックファイルの準備、`build_scan_job` を現在の順序のまま持つ。組み立て済みの job dict を期待していたテストは plan を検査する形に書き換える。
- [x] 試行されなかったパッケージの扱い（q-unattempted-policy）: 記録して報告する。summary の 5 つ目のキー `unattempted_packages`（失敗したパッケージとそれ以降の試行されなかったすべてのパッケージ、処理順、malformed を除く）は、すべての return 分岐にあり、レシートの 3 箇所すべてに記録する。自動再試行は無い。「triage filing incomplete」は R6 と batch 最終結果に出て、完了条件は変わらない。
- [x] デザインステップ（q-design-step）: 省略する。
- [x] 往復の保証範囲: 空白を含まないパッケージ名と advisory id を対象とする。空白を含む名前や id は malformed のままとする。
- [x] レポート分岐の OSError: レポート分岐での `write_report` または `mkdir` の OSError は本機能の対象外とする。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- review-phase.md: triage_filing レシート（R4 / R5）と R6 の定義
- test/README.md: テストの依存に関する決まり
- .claude/rules/core-plugin-version-bump.md: プラグインの version の扱い
