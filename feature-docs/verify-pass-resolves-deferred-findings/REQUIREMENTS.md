---
title: "verify-pass-resolves-deferred-findings"
created_date: 2026-11-12
status: draft
---

# verify-pass-resolves-deferred-findings - 要件定義書

## 1. 概要

### 1.1 背景
verify で受け入れ条件の pass を確認しても、deferred の critical/high 指摘は review 記録で未解決のまま残る。完了処理後の自動マージの事前チェック（merge-preflight.py）は、この指摘を unresolved_findings として扱って止まる。

### 1.2 目的
- verify で、対応する受け入れ条件の pass を確認した deferred の critical/high 指摘を review 記録で解決済み（fixed）にし、完了処理後の自動マージの事前チェックが unresolved_findings で止まらないようにする。
- 受け入れ条件に対応しない deferred 指摘は、これまでどおり未解決として扱う。

### 1.3 スコープ

対象:
- workflow.yaml の verify step への round カウンタと pass 済み ID 集合の記録（FR1・FR2）
- verify result が pass の round での、orchestrator による対応表の作成（FR3）
- em-workflow/scripts/ 配下の新しいスクリプトによる、最新 review round 記録の検証と書き換え（FR4〜FR8）
- interactive と batch の両方への適用（FR9）
- batch の最終報告の監査項目（FR10）
- develop SKILL.md・workflow-schema.md・review-phase.md・batch-mode.md の記述

対象外:
- merge-preflight.py の判定の変更（FR11）
- すでに完了した feature の救済（scope.backfill: no-backfill）。merge スキルと merge-preflight は書き込まないまま
- 最新でない review round の書き換え

## 2. ビジネス要件

### 2.1 ビジネス目標
- verify で、対応する受け入れ条件の pass を確認した deferred の critical/high 指摘を review 記録で解決済み（fixed）にし、完了処理後の自動マージの事前チェックが unresolved_findings で止まらないようにする。
- 受け入れ条件に対応しない deferred 指摘は、これまでどおり未解決として扱う。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | develop を interactive または batch で実行する |

### 2.3 期待される効果
- 受け入れ条件の pass で裏付けられた deferred の spec 指摘が、マージの事前チェックを止めなくなる。
- 受け入れ条件に対応しない deferred 指摘は、これまでどおりマージの事前チェックで止まる。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | verify pass による deferred 指摘の解決 | orchestrator（develop の verify フェーズ） | 高 |

### 3.2 ユースケース詳細

#### UC01: verify pass による deferred 指摘の解決

**アクター**: orchestrator（develop の verify フェーズ）

**事前条件**:
- 最新 review round 記録に、resolution: deferred・severity が critical/high・category: spec の指摘がある。

**基本フロー**:
1. verify フェーズが verify を実行し、結果を記録する。round カウンタを 1 増やし、評価して pass した受け入れ条件 / シナリオの ID 集合を verify step に記録する（FR1・FR2）。
2. result が pass なら、orchestrator が判定対象の指摘ごとに、pass 済み ID 集合に含まれる受け入れ条件の未達そのものであるかを判定し、stable_id → 受け入れ条件 ID の対応表を作る（FR3）。
3. orchestrator が対応表・workflow.yaml・最新 review round 記録を入力にスクリプトを実行する。スクリプトは条件をすべて満たすエントリの指摘だけを fixed に書き換え、根拠を記録する（FR4・FR5）。
4. round 記録の書き換えを、その verify round の結果を記録する workflow.yaml の更新と同じ commit-docs.sh のコミットに含める（FR6）。

**代替フロー**:
- result が fail の round では、どの指摘も変更しない（FR8）。
- 入力が構造的に壊れているとき、スクリプトは何も書かず 0 以外で終了する（FR4）。
- スクリプトが失敗しても、verify の結果記録と走行は止めない。deferred 指摘はそのまま残る（A4）。

**事後条件**:
- 書き換えた指摘は resolution: fixed で、根拠が記録されている。
- merge-preflight.py は、書き換えた指摘を解決済みとして扱う（RESOLVED = fixed / declined）。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | verify step の round カウンタ | verify を実行して結果を記録するたびに 1 増やす | 高 |
| FR2 | 評価済み・pass した ID 集合の記録 | 各 round で pass した受け入れ条件 / シナリオの ID 集合を記録する | 高 |
| FR3 | 対応付けの判定（orchestrator） | pass の round で stable_id → 受け入れ条件 ID の対応表を作る | 高 |
| FR4 | 検証と書き換え（スクリプト） | 条件をすべて満たすエントリだけを書き換える | 高 |
| FR5 | 根拠の記録 | resolution_reason と構造化フィールドを記録する | 高 |
| FR6 | 同一コミット | verify round の結果と同じ commit-docs.sh のコミットに含める | 高 |
| FR7 | 冪等性 | 再実行・中断後の再開で記録が変わらない | 高 |
| FR8 | 非対象の維持 | 対象外の指摘は変更しない | 高 |
| FR9 | 適用モード | interactive と batch で同じに適用する | 高 |
| FR10 | batch 報告 | 監査項目で fixed にした指摘を区別して示す | 中 |
| FR11 | merge-preflight 不変 | merge-preflight.py の判定を変えない | 高 |

### 4.2 機能詳細

#### FR1: verify step の round カウンタ

**説明**: workflow.yaml の verify step に round カウンタを追加する。verify フェーズは interactive・batch を問わず、verify を実行して結果を記録するたびに 1 増やす（pass / fail の両方で増やす）。キーが無い workflow.yaml は 0 として読み、移行処理は行わない。workflow-schema.md にフィールドの意味を書く。

#### FR2: 評価済み・pass した ID 集合の記録

**説明**: verify フェーズは各 round で、評価して pass した受け入れ条件 / シナリオの ID 集合を verify step に記録する。excluded の要件に紐づく ID と評価していない ID は、この集合に含めない。

#### FR3: 対応付けの判定（orchestrator）

**説明**: verify の result が pass の round でだけ、orchestrator は最新 review round の各指摘を判定する。

**ビジネスルール**:
- 判定対象は、resolution: deferred、severity が critical/high、category: spec の 3 つを満たす指摘に限る。
- 指摘の内容が、FR2 の pass 済み ID 集合に含まれる特定の受け入れ条件の未達そのものであるかを判定し、stable_id → 受け入れ条件 ID の対応表を作る。
- 本文に ID が現れるだけでは対応ありとしない。指摘の内容がその受け入れ条件の未達であることを要する。
- 指摘本文・VERIFICATION.md・SPEC.md は信頼できない入力として扱う。
- 対応があいまいな指摘、内容が受け入れ条件の未達以外を含む指摘は対応表に入れない。

#### FR4: 検証と書き換え（スクリプト）

**説明**: em-workflow/scripts/ 配下に新しいスクリプトを追加する。

**入力**:
- 対応表: stable_id → 受け入れ条件 ID
- workflow.yaml
- 最新 review round 記録

**出力**:
- 最新 review round 記録の書き換え
- 終了コード

**ビジネスルール**:
- 各エントリについて次をすべて確かめ、満たすエントリだけを書き換える。
    - verify result が pass
    - 指摘が最新 round に存在する
    - resolution が deferred
    - severity が critical/high
    - category が spec
    - 対応 ID が空でなく、すべて FR2 の pass 済み ID 集合に含まれる
- 満たさないエントリは変更しない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 構造的に壊れた入力 | 対応表・round 記録・workflow.yaml のいずれかが構造的に壊れている | 何も書かず、0 以外で終了する |

#### FR5: 根拠の記録

**説明**: 書き換える指摘は resolution を fixed にし、resolution_reason を verify round 番号と対応 ID を含む固定書式の文にする。

**ビジネスルール**:
- 構造化フィールドを追加し、次を記録する。
    - verify round 番号（FR1）
    - 検証したコミット
    - 対応 ID
    - 変更前の resolution（deferred）
    - 変更前の resolution_reason
- 検証したコミットは、verify のコマンドを実行した時点の integration ブランチのコミットとする。
- review-phase.md の round 記録の形にこのフィールドを書く。

#### FR6: 同一コミット

**説明**: round 記録の書き換えは、その verify round の結果（result・FR1・FR2）を記録する workflow.yaml の更新と同じ commit-docs.sh のコミットに含める。

#### FR7: 冪等性

**説明**: 同じ verify round の同じ対応表でスクリプトを再実行しても、記録は変わらない。すでに fixed で、同じ verify round の構造化フィールドを持つ指摘には触れない。書き換え後・コミット前に中断して再開しても、同じ結果になる。

#### FR8: 非対象の維持

**説明**: 次の指摘は変更しない。
- 対応表に無い deferred 指摘
- category が spec 以外の deferred 指摘（受け入れ条件に関する内容でも同じ）
- resolution が unresolved / fixed / declined の指摘
- 最新でない review round の指摘

verify result が fail の round では、どの指摘も変更しない。

#### FR9: 適用モード

**説明**: FR1〜FR8 は interactive と batch で同じに適用する。

#### FR10: batch 報告

**説明**: batch の最終報告の deferred findings の監査項目で、verify pass によって fixed にした指摘を stable_id・verify round・対応 ID とともに、deferred のまま残る指摘と区別して示す。batch-mode.md の Reporting と監査項目のソースマップをこれに合わせる。

#### FR11: merge-preflight 不変

**説明**: merge-preflight.py の判定（最新 round だけを読む、RESOLVED = fixed / declined）は変えない。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 該当なし

### 5.2 セキュリティ要件
- 入力検証（NFR1）: 指摘本文・VERIFICATION.md・SPEC.md・round 記録の自由文は信頼できない入力として扱う（worker-envelope.md の Untrusted-Input Handling）。スクリプトの出力には ID・件数などの検証済みの構造化値だけを書き、自由文を転記しない。
- 読み込みと書き込み先（NFR6）: スクリプトは PyYAML の safe load だけを使う。書き込み先は integration worktree の最新 review round 記録だけとする。

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- 既存テストの文言（NFR2）: 既存テストが固定している文言を壊さない。
    - review-phase.md R5 の Completion gate 段落（一字一句）
    - R5 に 'gate_id:' と 'batch-policies.yaml' が無いこと
    - develop SKILL.md の verify 節の「`deferred` を与えない」と、禁止表現（'deferred にする' / 'deferred を設定' / 'deferred を与える' / 'status: deferred'、空白除去後の一致）が無いこと
    - '（batch: 確認せず自動 rework。' の存在
    - workflow-schema.md と batch-mode.md の verify_rework / 系譜 / hard cap の前後 60 文字に 1 と 3 の数字を置かないこと
- テスト（NFR3）: テストは標準ライブラリの unittest で tests/ に置き、`python3 -m unittest discover -s tests` で通る。tests/test_merge_preflight.py の既存ケース（deferred を未解決とするものを含む）は変えない。
- ゲート（NFR4）: 新しい gate_id・質問・batch 非 packet ゲートを追加しない。
- version（NFR5）: プラグインの version（plugin.json / marketplace.json）を変えない。

### 5.5 互換性要件
- verify step に round カウンタのキーが無い workflow.yaml は 0 として読み、移行処理は行わない（FR1）。

## 6. UI/UX要件

### 6.1 画面設計要件
該当なし（UI を持たない変更）

### 6.2 画面遷移
該当なし

### 6.3 レスポンシブ対応
該当なし

## 7. データ要件

### 7.1 データモデル概要
- workflow.yaml の verify step: result、round カウンタ（FR1）、pass 済み ID 集合（FR2）
- 対応表: stable_id → 受け入れ条件 ID（FR3）
- 最新 review round 記録の指摘: resolution、resolution_reason、構造化フィールド（FR5）

### 7.2 データ項目
| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| verify step | round カウンタ | 整数 | × | verify を実行して結果を記録するたびに 1 増やす。キーが無いときは 0 として読む |
| verify step | pass 済み ID 集合 | ID の集合 | × | 評価して pass した受け入れ条件 / シナリオの ID。excluded の要件に紐づく ID と評価していない ID は含めない |
| 対応表 | stable_id | 文字列 | ○ | 最新 review round の指摘の stable_id |
| 対応表 | 受け入れ条件 ID | ID のリスト | ○ | 指摘が未達そのものである受け入れ条件の ID |
| 指摘 | resolution | 文字列 | ○ | 書き換え後は fixed |
| 指摘 | resolution_reason | 文字列 | ○ | verify round 番号と対応 ID を含む固定書式の文 |
| 指摘（構造化フィールド） | verify round 番号 | 整数 | ○ | FR1 の値 |
| 指摘（構造化フィールド） | 検証したコミット | コミット | ○ | verify のコマンドを実行した時点の integration ブランチのコミット |
| 指摘（構造化フィールド） | 対応 ID | ID のリスト | ○ | 対応表の受け入れ条件 ID |
| 指摘（構造化フィールド） | 変更前の resolution | 文字列 | ○ | deferred |
| 指摘（構造化フィールド） | 変更前の resolution_reason | 文字列 | ○ | 書き換え前の resolution_reason |

フィールドの定義は workflow-schema.md（FR1・FR2）と review-phase.md（FR5）に書く。

### 7.3 データ保持期間
該当なし

## 8. 外部連携

### 8.1 連携システム
該当なし

### 8.2 API仕様要件
該当なし

## 9. 制約条件

### 9.1 技術的制約
- スクリプトは PyYAML の safe load だけを使う（NFR6）。
- テストは標準ライブラリの unittest を使う（NFR3）。
- merge-preflight.py の判定は変えない（FR11）。

### 9.2 ビジネス上の制約
- 新しい gate_id・質問・batch 非 packet ゲートを追加しない（NFR4）。
- プラグインの version を変えない（NFR5）。

### 9.3 スケジュール制約
- なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/verify-pass-resolves-deferred-findings/**`
- `test-docs/verify-pass-resolves-deferred-findings/**`

`feature-docs/verify-pass-resolves-deferred-findings/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/verify-pass-resolves-deferred-findings/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/verify-pass-resolves-deferred-findings/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/verify-pass-resolves-deferred-findings/` ディレクトリを生成しないが、宣言された `test-docs/verify-pass-resolves-deferred-findings/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| スクリプトの失敗 | 中 | verify の結果記録と走行は止めない。deferred 指摘はそのまま残る（A4） |
| minimal tier（VERIFICATION.md が無い） | 低 | pass 済み ID 集合は TASK.md の Expected Result から verify が評価した ID だけで構成する。ID が無ければ集合は空で、どの指摘も更新しない（A5） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 最新 review round に category: spec・severity: high・resolution: deferred の指摘があり、対応表がその指摘を pass 済み ID 集合内の受け入れ条件 ID に対応付けている。この状態で verify result が pass なら、スクリプト実行後の round 記録でその指摘は resolution: fixed になり、resolution_reason と構造化フィールドに verify round 番号・検証したコミット・対応 ID・変更前の resolution と理由が記録されている
- [ ] AC2: AC1 の状態の round 記録と workflow.yaml をコミットした integration ブランチに対して、merge-preflight.py が outcome: proceed を返す
- [ ] AC3: 対応表に無い deferred 指摘、category が spec 以外の deferred 指摘、対応 ID が pass 済み ID 集合に無い（excluded・未評価・未知の）指摘は deferred のまま残る。その状態で merge-preflight.py は unresolved_findings を返す
- [ ] AC4: verify result が fail のとき、スクリプトはどの指摘も変更しない
- [ ] AC5: resolution が unresolved / fixed / declined の指摘と、最新でない round の指摘は変更されない
- [ ] AC6: 同じ入力でスクリプトを 2 回実行した結果は 1 回実行した結果と同じになる
- [ ] AC7: 構造的に壊れた入力では、スクリプトは何も書かず 0 以外で終了する
- [ ] AC8: develop SKILL.md の verify フェーズに、round カウンタの加算、pass 済み ID 集合の記録、result: pass のときの対応表作成・スクリプト実行、結果と同じ commit-docs.sh コミットに含めることが書かれている。workflow-schema.md と review-phase.md に新しいフィールドが定義されている
- [ ] AC9: 修正前の挙動では AC1・AC2 のテストが失敗する
- [ ] AC10: `python3 -m unittest discover -s tests` が通る（既存テストを含む）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系（TS-1）: 一時 git リポジトリに、deferred の spec/high 指摘を持つ round 記録と verify pass の workflow.yaml を置き、対応表を与えてスクリプトを実行し、コミットする。round 記録の値を確認し、merge-preflight.py が proceed を返すことを確かめる（AC1・AC2・AC9）
- [ ] 異常系（TS-2）: 対応表に無い指摘、category: security の deferred 指摘、excluded・未評価・未知の ID に対応付けた指摘が deferred のまま残り、merge-preflight.py が unresolved_findings を返す（AC3）
- [ ] 異常系（TS-3）: verify result: fail の workflow.yaml では、round 記録が変わらない（AC4）
- [ ] 境界値（TS-4）: unresolved / fixed / declined の指摘と、round1 の指摘（最新は round2）が変わらない（AC5）
- [ ] 冪等性（TS-5）: 同じ入力で 2 回実行し、記録がバイト単位で同じであることを確かめる（AC6）
- [ ] 異常系（TS-6）: 壊れた対応表、壊れた round 記録、壊れた workflow.yaml のそれぞれで、0 以外の終了コードになり、ファイルが変わらない（AC7）
- [ ] 文書（TS-7）: develop SKILL.md の verify 節、workflow-schema.md、review-phase.md に、必要な記述と新しいフィールドがあることを文言で確かめる（AC8）
- [ ] 回帰（TS-8）: `python3 -m unittest discover -s tests` を実行する（AC10）
- [ ] パフォーマンス: 該当なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| round カウンタ | workflow.yaml の verify step に記録する、verify の実行・結果記録の回数（FR1） |
| pass 済み ID 集合 | verify の各 round で評価して pass した受け入れ条件 / シナリオの ID 集合（FR2） |
| 対応表 | stable_id → 受け入れ条件 ID の対応（FR3） |
| 判定対象の指摘 | 最新 review round の、resolution: deferred・severity が critical/high・category: spec の指摘 |

## 14. 確認事項

### 14.1 確認済み事項
- [x] merge-preflight.py の判定と tests/test_merge_preflight.py の既存ケース: 変えない（A1）
- [x] scope.backfill: no-backfill。すでに完了した feature の救済は範囲外とし、merge スキルと merge-preflight は書き込まないまま（A3）

### 14.2 未確認・保留事項
- なし

### 14.3 前提
- A1: merge-preflight.py の判定と tests/test_merge_preflight.py の既存ケースは変えない（影響度: 高）
- A2: 書き換えの対象は最新 review round だけとする（影響度: 中）
- A3: すでに完了した feature の救済は範囲外とする（scope.backfill: no-backfill）。merge スキルと merge-preflight は書き込まないまま（影響度: 中）
- A4: スクリプトが失敗しても、verify の結果記録と走行は止めない。deferred 指摘はそのまま残る（fail-closed）（影響度: 中）
- A5: minimal tier（VERIFICATION.md が無い）では、pass 済み ID 集合は TASK.md の Expected Result から verify が評価した ID だけで構成する。ID が無ければ集合は空で、どの指摘も更新しない（影響度: 低）
- A6: 既存テストが固定している文言（NFR2）は変えない（影響度: 中）
- A7: プラグインの version は変えない（影響度: 低）

## 15. 参考資料

- worker-envelope.md: Untrusted-Input Handling
- merge-preflight.py
- tests/test_merge_preflight.py
- tests/test_review_phase_coverage_record.py
- tests/test_verify_rework_lineage_cap.py
- tests/test_develop_skill_rewiring.py
