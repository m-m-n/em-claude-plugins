---
title: "verify-rerun-legacy-deferred-resolution"
created_date: 2026-11-21
status: draft
---

# verify-rerun-legacy-deferred-resolution - 要件定義書

## 1. 概要

### 1.1 背景
verify step に round / passed_ids が無い旧形式の workflow.yaml を持つ完了済み feature では、review で deferred になった critical/high・category spec の指摘が残り、merge-preflight.py が unresolved_findings で止まる。

### 1.2 目的
- 完了済み feature で verify をやり直したとき、review で deferred になった critical/high・category spec の指摘を、verify の合格に基づいて fixed にできるようにする。
- verify step に round / passed_ids が無い旧形式の workflow.yaml でも、verify のやり直しで resolve-verified-findings.py が実行され、merge-preflight.py が unresolved_findings で止まらないようにする。

### 1.3 スコープ
- 対象
    - develop SKILL.md の「#### verify pass による deferred 指摘の解決」の記述（旧形式の workflow.yaml での verify のやり直し、対応づけの規則）
    - tests/test_verify_pass_resolution_procedure.py の固定文言
    - verify のやり直しから merge-preflight.py までのシナリオテスト
- 対象外
    - em-workflow/scripts/resolve-verified-findings.py の変更
    - merge-preflight.py の判定条件の変更
    - 先行 feature verify-pass-resolves-deferred-findings の REQUIREMENTS.md / SPEC.md の変更
    - verify をやり直す起点（verify を pending に戻す操作）

## 2. ビジネス要件

### 2.1 ビジネス目標
- 完了済み feature で verify をやり直したとき、review で deferred になった critical/high・category spec の指摘を、verify の合格に基づいて fixed にできる。
- 旧形式の workflow.yaml でも、verify のやり直しで resolve-verified-findings.py が実行され、merge-preflight.py が unresolved_findings で止まらない。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | 旧形式の workflow.yaml を持つ完了済み feature で verify をやり直す |

### 2.3 期待される効果
- verify のやり直しの結果、該当する指摘が fixed になる。
- merge-preflight.py が proceed を返す。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 旧形式の workflow.yaml で verify をやり直し、deferred 指摘を解決する | develop のオーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: 旧形式の workflow.yaml で verify をやり直し、deferred 指摘を解決する

**アクター**: develop のオーケストレーター

**事前条件**:
- verify step に round / passed_ids が無い workflow.yaml がある。
- 最新の review round 記録に deferred・high・category spec の指摘（ある受け入れ条件の未達）がある。

**基本フロー**:
1. verify をやり直す。round は 1 になる。
2. result を書くのと同じ workflow.yaml の書き込みで passed_ids を書く。
3. result が pass なら、指摘と基準 ID を対応づける。
4. resolve-verified-findings.py を実行する。
5. integration ブランチにコミットする。

**代替フロー**:
- result が pass でない場合、対応づけとスクリプトの実行を行わない。

**事後条件**:
- 指摘が resolution fixed と verify_resolution を持つ。
- merge-preflight.py が proceed を返す。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 旧形式の workflow.yaml での verify のやり直し | round / passed_ids が無い workflow.yaml で verify をやり直したときも同じ手順を行う | 高 |
| FR2 | スクリプトは変えない | resolve-verified-findings.py と、その条件を固定する既存テストを変えない | 高 |
| FR3 | 対応づけの規則 | 指摘と基準 ID を対応づける規則を定める | 高 |
| FR4 | 手順の記述をテストで固定する | FR1 と FR3 の記述をテストで固定する | 高 |
| FR5 | やり直しから merge-preflight までのシナリオテスト | 旧形式の fixture で、やり直しから merge-preflight.py の proceed までをテストで固定する | 高 |
| FR6 | 変えない文書とスクリプト | merge-preflight.py の判定条件と、先行 feature の文書を変えない | 高 |

### 4.2 機能詳細

#### FR1: 旧形式の workflow.yaml での verify のやり直し

**説明**: develop SKILL.md の「#### verify pass による deferred 指摘の解決」に、verify step に round / passed_ids が無い workflow.yaml で verify をやり直したときも同じ手順を行うことを明記する。その場合 round は 1 になり、result を書くのと同じ workflow.yaml の書き込みで passed_ids を書く。result が pass なら対応づけとスクリプトの実行を行う。

**ビジネスルール**:
- round が無い workflow.yaml は round 0、passed_ids が無いものは空集合として読む（workflow-schema.md「`round` and `passed_ids`」の既存規則）。この規則は変えない。

#### FR2: スクリプトは変えない

**説明**: em-workflow/scripts/resolve-verified-findings.py は変えない。round >= 1 の条件と、その条件を固定する既存テスト（tests/test_resolve_verified_findings.py）は変えない。

#### FR3: 対応づけの規則

**説明**: develop SKILL.md の同じ小節の対応づけの規則を次のとおりにする。

**ビジネスルール**:
- 指摘の主張がその基準 ID の未達であれば、原因の分析・修正案・範囲の判断が書き添えてあっても対応づける。
- 次の指摘は対応づけない。
    - 対応が曖昧な指摘
    - pass 済みでない別の基準の未達や別の欠陥も主張している指摘
    - 本文に ID が現れるだけの指摘

#### FR4: 手順の記述をテストで固定する

**説明**: tests/test_verify_pass_resolution_procedure.py で FR1 と FR3 の記述を固定する。FR3 で置き換える現行の除外文言「未達そのもの以外の内容を含む指摘は対応づけない」を固定している箇所（TestAC2MappingRule.test_ac2_ambiguous_and_mixed_content_findings_are_left_out）は、新しい文言に合わせて更新する。

#### FR5: やり直しから merge-preflight までのシナリオテスト

**説明**: verify step に round / passed_ids が無く、最新の review round 記録に deferred・high・category spec の指摘（ある受け入れ条件の未達）を持つ fixture で、verify のやり直し（round 1、その受け入れ条件を含む passed_ids、result pass の記録）、対応づけファイル、resolve-verified-findings.py の実行、integration ブランチへのコミットを行うと、指摘が fixed になり merge-preflight.py が proceed を返すことをテストで固定する。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| unresolved_findings | やり直しの前の状態で merge-preflight.py を実行する | merge-preflight.py が unresolved_findings を返すことをテストで確かめる |

#### FR6: 変えない文書とスクリプト

**説明**: merge-preflight.py の判定条件は変えない。先行 feature verify-pass-resolves-deferred-findings の REQUIREMENTS.md / SPEC.md は変えない。verify のやり直しの扱いはこの feature の文書に書く。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- 該当なし

### 5.2 セキュリティ要件
- 該当なし

### 5.3 可用性要件
- 該当なし

### 5.4 保守性要件
- NFR1: テストは標準ライブラリだけを import し、スクリプトは子プロセスとして実行する（tests/test_resolve_verified_findings.py と同じ形）。テストは一時ディレクトリの git リポジトリを fixture にする。
- NFR2: develop SKILL.md の小節は、既存の固定文言（interactive でも batch でも同じ、ゲートも質問も batch の non-packet ゲートも追加しない、未達そのものであるときだけ、本文に ID が現れているだけでは足りない、対応が曖昧な指摘、Untrusted-Input Handling の参照など）を保つ。gate_id / AskUserQuestion / batch-policies.yaml を書かない。verify の残りに deferred を与える文言を書かない。verify フェーズ内で category の語彙を backtick で囲まない。
- NFR3: ゲート・質問・batch の non-packet ゲートを追加しない。手順は interactive と batch で同じ。
- NFR4: プラグインの version は手で変えない。

### 5.5 互換性要件
- verify step に round / passed_ids が無い旧形式の workflow.yaml を扱う（FR1）。

## 6. UI/UX要件

該当なし（UI を持たない）。

## 7. データ要件

### 7.1 データモデル概要
既存の workflow.yaml と review round 記録を使う。

### 7.2 データ項目
| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| workflow.yaml の verify step | round | - | - | 無い場合は 0 として読む。やり直しで 1 になる |
| workflow.yaml の verify step | passed_ids | - | - | 無い場合は空集合として読む。result を書くのと同じ書き込みで書く |
| review round 記録の指摘 | resolution | - | - | 解決後は fixed |
| review round 記録の指摘 | verify_resolution | - | - | 解決後に付く |

### 7.3 データ保持期間
該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- resolve-verified-findings.py、merge-preflight.py の判定条件、tests/test_resolve_verified_findings.py の既存テストを変えない。
- テストは標準ライブラリだけを import する。

### 9.2 ビジネス上の制約
- 先行 feature verify-pass-resolves-deferred-findings の REQUIREMENTS.md / SPEC.md を変えない。
- プラグインの version を手で変えない。

### 9.3 スケジュール制約
- 該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/verify-rerun-legacy-deferred-resolution/**`
- `test-docs/verify-rerun-legacy-deferred-resolution/**`

`feature-docs/verify-rerun-legacy-deferred-resolution/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/verify-rerun-legacy-deferred-resolution/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/verify-rerun-legacy-deferred-resolution/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/verify-rerun-legacy-deferred-resolution/` ディレクトリを生成しないが、宣言された `test-docs/verify-rerun-legacy-deferred-resolution/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| FR3 で現行の除外文言を置き換えると、その文言を固定している既存テストが合わなくなる | 中 | TestAC2MappingRule.test_ac2_ambiguous_and_mixed_content_findings_are_left_out を新しい文言に合わせて更新する（FR4） |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: develop SKILL.md の「#### verify pass による deferred 指摘の解決」に、verify step に round / passed_ids が無い workflow.yaml で verify をやり直したときも同じ手順を行い、round が 1 になり passed_ids を書き、pass なら対応づけとスクリプトの実行を行うことが書かれている。これがテストで固定されている。（FR1, FR4）
- [ ] AC2: 同じ小節に、指摘の主張がその基準 ID の未達であれば原因の分析・修正案・範囲の判断が書き添えてあっても対応づけること、対応が曖昧な指摘・pass 済みでない別の基準の未達や別の欠陥も主張している指摘・本文に ID が現れるだけの指摘は対応づけないことが書かれている。これがテストで固定され、旧文言を固定していたテストが更新されている。（FR3, FR4）
- [ ] AC3: verify step に round / passed_ids が無い workflow.yaml と、deferred・high・category spec の指摘を持つ最新 review round 記録の fixture で、verify のやり直しを記録してスクリプトを実行しコミットすると、指摘が fixed になり merge-preflight.py が proceed を返す。やり直しの前の状態では merge-preflight.py が unresolved_findings を返す。これがテストで固定されている。（FR5）
- [ ] AC4: resolve-verified-findings.py、merge-preflight.py、tests/test_resolve_verified_findings.py の既存テスト、先行 feature の REQUIREMENTS.md / SPEC.md が変わっておらず、python3 -m unittest discover -s tests が通る。（FR2, FR6）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系 TS-1（AC1）: SKILL.md の小節に、round / passed_ids が無い workflow.yaml での verify のやり直しに同じ手順を行うこと、round が 1 になること、passed_ids を書くこと、pass なら対応づけとスクリプトの実行を行うことが書かれていることを確かめる。
- [ ] 正常系 TS-2（AC2）: SKILL.md の小節に、書き添え（原因の分析・修正案・範囲の判断）があっても対応づけること、曖昧な指摘・別の基準の未達や別の欠陥も主張する指摘・ID が現れるだけの指摘を対応づけないことが書かれていること、旧文言「未達そのもの以外の内容を含む指摘は対応づけない」が無いことを確かめる。
- [ ] 異常系 TS-3（AC3）: 旧形式の workflow.yaml（verify step に round / passed_ids が無い、全 step completed / skipped）と round2 の記録（deferred・high・category spec の指摘 1 件）をコミットし、merge-preflight.py が unresolved_findings を返すことを確かめる。
- [ ] 正常系 TS-4（AC3）: 同じ fixture で verify step に round 1・その受け入れ条件を含む passed_ids・result pass を記録し、stable_id とその基準 ID の対応づけファイルで resolve-verified-findings.py を実行し、コミットしたあと、指摘が resolution fixed と verify_resolution を持ち、merge-preflight.py が proceed を返すことを確かめる。
- [ ] 回帰 TS-5（AC4）: python3 -m unittest discover -s tests を実行し、既存テストを含めて通ることを確かめる。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 旧形式の workflow.yaml | verify step に round / passed_ids が無い workflow.yaml |
| verify のやり直し | 完了済み feature で verify を再度実行すること |
| 対応づけ | review の指摘（stable_id）と、verify で pass した基準 ID を結びつけること |
| 書き添え | 指摘に添えられた原因の分析・修正案・範囲の判断 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1 AC1 の満たし方: スクリプトを変えず、SKILL.md の記述とテストで満たす。resolve-verified-findings.py の round >= 1 の条件と既存テストは変えない。
- [x] A2 対応づけの境界: 指摘の主張がその基準 ID の未達であれば書き添えがあっても対応づける。曖昧な指摘、pass 済みでない別の基準の未達や別の欠陥も主張する指摘、ID が現れるだけの指摘は除外する。現行の除外文言を置き換えるため tests/test_verify_pass_resolution_procedure.py の固定文言を合わせて更新する。
- [x] A3 先行 feature の文書: 先行 feature verify-pass-resolves-deferred-findings の REQUIREMENTS.md / SPEC.md は変えない。verify のやり直しの扱いはこの feature の文書に書く。
- [x] A4 既存の読み方: round が無い workflow.yaml は round 0、passed_ids が無いものは空集合として読む（workflow-schema.md「`round` and `passed_ids`」の既存規則）。この規則は変えない。
- [x] A5 範囲外: verify をやり直す起点（verify を pending に戻す操作）はこの feature の範囲外とする。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- develop SKILL.md「#### verify pass による deferred 指摘の解決」
- workflow-schema.md「`round` and `passed_ids`」
- tests/test_verify_pass_resolution_procedure.py
- tests/test_resolve_verified_findings.py
