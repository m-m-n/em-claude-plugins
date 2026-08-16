---
title: "batch-stop-contract"
created_date: 2026-08-16
status: draft
---

# batch-stop-contract - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow の batch 実行がワークフロー内部で停止したとき、その事実を機械可読な形で受け取る手段が無い。正常完了と停止の区別が呼び出し元プロセスの exit code に依存しており、ターンの打ち切りやクラッシュと正常完了を構造的に判別できない。

### 1.2 目的

batch mode の終端状態（正常完了 / 停止）を機械可読に表明する出力契約を定義し、停止時には停止した step と停止理由を含める。その契約を SSOT 文書に明記し、ドキュメント契約テストで固定する。

### 1.3 スコープ

対象は em-workflow の出力契約の定義と、その契約を固定するテスト、および version bump。

対象外は外部タスク管理サービスのステータス遷移。停止の表明までを em-workflow の責務とする。

## 2. ビジネス要件

### 2.1 ビジネス目標

- em-workflow の batch 実行がワークフロー内部で停止した事実を、機械可読な形で出力する
- 正常完了と停止を、呼び出し元プロセスの exit code に依存せず構造的に区別可能にする
- 停止時の出力に、停止した step と停止理由を含める
- その出力契約を `em-workflow/references/batch-mode.md`（またはそこが指す SSOT）に明記し、ドキュメント契約テストで固定する
- 停止の表明までを em-workflow の責務とし、外部タスク管理サービスのステータス遷移には踏み込まない

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| 無人実行の呼び出し元プロセス | batch mode の出力ログから終端行を解析し、正常完了と停止を判別する（NFR5 由来） |
| 人間の評価者 | 停止理由の detail を外部サービス経由で受け取る（NFR6 由来） |

### 2.3 期待される効果

- 終端行の不在自体を異常（クラッシュ・打ち切り）として検出できる
- 停止点ごとの理由コードにより、停止の所在が出力だけで特定できる
- 出力契約が契約テストで固定され、以後の変更で暗黙に壊れない

## 3. ユースケース

### 3.1 ユースケース一覧

本 feature はワークフローの出力契約の定義であり、ユースケース単位への分解は requirements_analysis に含まれない。対象範囲は第 4 章の機能要件（FR1〜FR9）が規定する。

### 3.2 ユースケース詳細

（記載なし。第 4 章を参照）

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | 終端状態の機械可読出力 | 終了時に固定接頭辞付き 1 行で終端状態を出力する | resolved |
| FR2 | 停止 step と停止理由の同梱 | 停止時の終端行に停止 step と理由コード + detail を含める | resolved |
| FR3 | 出力契約の SSOT 明記 | 出力契約を batch-mode.md またはその指し先 SSOT に明記する | resolved |
| FR4 | 既存成功時出力の非破壊 | Step C 3. の終了報告の形式を壊さない | resolved |
| FR5 | 対象停止点の列挙 | 全ての終端停止点を列挙し理由コードに結びつける | resolved |
| FR6 | 待機ターンと step を持たない停止の表現 | 停止条件 5 では終端行を出さず、step 不成立時はセンチネル値を使う | resolved |
| FR7 | 外部サービス責務の非侵犯 | 外部タスク管理サービスのページ本文・ステータスを編集しない | resolved |
| FR8 | ドキュメント契約テストの追加 | 契約を固定するテストを tests/ に追加する | resolved |
| FR9 | version bump | plugin.json と marketplace.json の version を同値で patch bump する | resolved |

### 4.2 機能詳細

#### FR1: 終端状態の機械可読出力

**説明**: batch mode の終了時に、最終アシスタントメッセージ内の固定接頭辞付き 1 行として終端状態を出力する。正常完了時と停止時の双方で同一形式の行を出し、行の不在自体を異常（クラッシュ・打ち切り）として検出できるようにする。

#### FR2: 停止 step と停止理由の同梱

**説明**: 停止時の終端行に、停止した step の識別子と停止理由を含める。停止理由は安定した理由コードの閉じた集合（enum）で表し、人間向けの自由文 detail を添える。

#### FR3: 出力契約の SSOT 明記

**説明**: 出力契約を `em-workflow/references/batch-mode.md`、またはそこから指される SSOT に明記する。既存の SSOT 分割規律（他文書の内容を再掲せず、指し先を作る）に従う。

#### FR4: 既存成功時出力の非破壊

**説明**: Step C 3. の終了報告（`em-workflow 完了: {feature}` / 残したブランチ名と取り込み案内 / PR URL / license none の 1 行 / batch 監査項目）の形式を壊さない。終端行はそれらと共存する追加の行として定義する。

#### FR5: 対象停止点の列挙

**説明**: 契約の対象を全ての終端停止点とする。すなわち停止条件 2（スタック）/ 3（failed・needs_update）/ 4（YAML parse エラー）/ 6（git-setup 中断）に加え、`question-resolution.md` の fail-closed classification による phase abort、`batch-policies.yaml` の `on_unavailable: abort`、`implement.failed-task` の同一タスク 2 回目 failed による abort phase、`verify.failed` の rework cap 到達、Step C の中断（main 作業ツリー dirty / `git worktree remove` 失敗）を列挙し、それぞれを終端行の理由コードに結びつける。

**対象停止点一覧**:

| 停止点 |
|--------|
| 停止条件 2（スタック） |
| 停止条件 3（failed・needs_update） |
| 停止条件 4（YAML parse エラー） |
| 停止条件 6（git-setup 中断） |
| `question-resolution.md` の fail-closed classification による phase abort |
| `batch-policies.yaml` の `on_unavailable: abort` |
| `implement.failed-task` の同一タスク 2 回目 failed による abort phase |
| `verify.failed` の rework cap 到達 |
| Step C の中断（main 作業ツリー dirty / `git worktree remove` 失敗） |

#### FR6: 待機ターンと step を持たない停止の表現

**説明**: 停止条件 5（implementer 通知待ち）で終わるターンには終端行を出力しない。`workflow.yaml` の step が成立していない停止（Step 0 git-setup 中断 / Step A の feature 解決失敗）には、固定のセンチネル step 値を割り当てて終端行に載せる。

#### FR7: 外部サービス責務の非侵犯

**説明**: em-workflow から外部タスク管理サービスのタスクページ本文・ステータスプロパティを編集しない。停止の表明までが責務であることを契約に明記する。

#### FR8: ドキュメント契約テストの追加

**説明**: 出力契約を固定するドキュメント契約テストを `tests/` に追加し、`python3 -m unittest discover -s tests` が通る状態にする。

#### FR9: version bump

**説明**: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version を同じ値へ patch bump する（現行はいずれも 0.1.39）。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし（requirements_analysis に性能目標値の指定は無い）。

### 5.2 セキュリティ要件

- **NFR6**: 停止理由の detail に秘匿情報を含めない。終端行は外部サービス経由で人間の評価者へ中継される。

### 5.3 可用性要件

該当なし（requirements_analysis に稼働率・復旧時間の指定は無い）。

### 5.4 保守性要件

- **NFR4**: 契約テストの assertion は固定リテラルではなく耐久的な不変条件で表現し、matcher ごとに negative proof と non-vacuity guard を置く（既存 `tests/test_routeback_reset_scope_version_bump.py` の慣行）。
- **NFR5**: 終端行の接頭辞は無人実行のログ中で一意に識別でき、通常の散文や契約文書内の例示行と衝突しない。
- **NFR7**: 停止理由コードは閉じた集合として契約文書に列挙され、契約テストがその集合と停止点の対応を検査できる形で記述される。

### 5.5 互換性要件

- **NFR1**: テストコードは Python 標準ライブラリのみを使う。PyYAML 等の実行時依存をテスト依存に持ち込まない。
- **NFR2**: 既存テストモジュールを変更せずに、スイート全体が通る。
- **NFR3**: 終端行の生成に外部ツール・追加依存を必要としない（テキスト 1 行の出力のみ）。

## 6. UI/UX要件

該当なし。変更対象が Markdown / YAML の SSOT 文書、Python 契約テスト、2 つの JSON マニフェストに限られ、UI・画面・視覚要素を伴わないため、design ステップは skip 判定となっている。

## 7. データ要件

該当なし（永続データモデルを伴わない）。終端行のフィールド構成（接頭辞 / step / 停止理由コード / detail）は FR1・FR2 が規定する。

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| 外部タスク管理サービス | 終端行の中継（読み取りのみ） | 停止 step・停止理由コード・detail |

### 8.2 API仕様要件

FR7 により、em-workflow から外部タスク管理サービスのタスクページ本文・ステータスプロパティを編集しない。

## 9. 制約条件

### 9.1 技術的制約

- テストは Python 標準ライブラリのみで書く（NFR1）
- 既存テストモジュールを変更しない（NFR2）
- 終端行の生成に外部ツール・追加依存を用いない（NFR3）
- SSOT 分割規律に従い、他文書の内容を再掲せず指し先を作る（FR3）
- テストコマンドは `python3 -m unittest discover -s tests`。build / format / e2e のコマンドはプロジェクトに存在しない

### 9.2 ビジネス上の制約

- 停止の表明までが em-workflow の責務であり、外部タスク管理サービスのステータス遷移には踏み込まない
- リポジトリに LICENSE ファイルは無い（`project.license: none`）

### 9.3 スケジュール制約

該当なし。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 終端行の接頭辞が散文や契約文書内の例示行と衝突する | 中 | NFR5 として一意性を要件化し、TS-8 で偶発的出現を検査する |
| 停止点の取りこぼしが他経路に残る | 高 | FR5 で全終端停止点を列挙し、TS-3 で双方向カバレッジを検査する |
| 停止条件 5 の待機ターンを停止と誤判定する | 中 | FR6 で終端行を出さないことを契約に明記し、TS-4 で検査する |

### 10.2 ビジネスリスク

| リスク | 影響度 | 対応策 |
|--------|--------|--------|
| 停止理由の detail に秘匿情報が混入し外部サービス経由で流出する | 中 | NFR6 として detail の内容を制約する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] batch mode の終了時に、正常完了と停止を機械可読に判別できる終端行が定義されている（固定接頭辞付きの 1 行、完了・停止の双方で同一形式）
- [ ] 停止時の終端行に停止 step と停止理由が含まれる（理由は閉じた enum + 自由文 detail）
- [ ] 停止理由コードの集合が契約文書に列挙され、FR5 が挙げる全停止点がそのいずれかに対応づけられている
- [ ] その出力契約が `em-workflow/references/batch-mode.md`（またはそれが指す SSOT）に明記されている
- [ ] 既存の成功時出力（`em-workflow 完了: {feature}` / integration ブランチ名の行 / PR URL の行 / batch 監査項目）の形式が保たれている
- [ ] 停止条件 5 の待機ターンでは終端行を出さないことが契約上明記されている
- [ ] step を持たない停止（Step 0 / Step A）に固定センチネル step 値が定義されている
- [ ] 対応するドキュメント契約テストが `tests/` に追加されている
- [ ] `python3 -m unittest discover -s tests` が通る
- [ ] `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version が同じ値で bump されている

### 11.2 KPI

該当なし（requirements_analysis に KPI の指定は無い）。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | 対象要件 | シナリオ |
|----|----------|----------|
| TS-1 | FR1, FR3 | 契約 SSOT が終端行の接頭辞・フィールド構成・完了/停止の両方に出す旨を定義していることを、文書本文の assert で確認する |
| TS-2 | FR2, NFR7 | 契約 SSOT が停止理由コードの閉じた集合を列挙し、各コードが step フィールドと detail フィールドを伴うことを assert する。集合を集合として抽出し、重複・空要素が無いことも検査する |
| TS-3 | FR5 | FR5 が挙げる全停止点（停止条件 2/3/4/6、fail-closed abort、`on_unavailable: abort`、implement 2 回目 failed、verify cap 到達、Step C 中断）が契約文書上でいずれかの理由コードに対応づけられていることを、停止点リストと対応表の双方向カバレッジとして assert する |
| TS-4 | FR6 | 契約文書が「停止条件 5 の待機ターンには終端行を出さない」と明記していること、および step を持たない停止用のセンチネル step 値が定義されていることを assert する |
| TS-5 | FR4 | `skills/develop/SKILL.md` の Step C 終了報告が、`em-workflow 完了: {feature}`・ブランチ名案内・PR URL・license none の 1 行・batch 監査項目を保持していることを回帰ガードとして assert する |
| TS-6 | FR7 | 契約文書が「外部タスク管理サービスのステータス操作を行わない」旨を明記していることを assert する |
| TS-7 | FR9, NFR4 | `plugin.json` と `marketplace.json` が JSON としてパースでき、version が 0.1 系で patch > 39、かつ両者が文字列として一致することを assert する。matcher ごとに negative proof（偽造した 0.1.39 / 不一致ペアを拒否する）と non-vacuity guard（偽造値が well-formed であること）を置く |
| TS-8 | NFR1, NFR2, NFR5 | 追加モジュールが標準ライブラリのみを import すること、既存モジュール無改変で `python3 -m unittest discover -s tests` 全体が通ること、および終端行の接頭辞が契約文書内の例示行とテスト側の期待値だけに現れ、散文中に偶発的に出現しないことを確認する |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 終端行 | batch mode の終了時に最終アシスタントメッセージ内へ出力する、固定接頭辞付きの 1 行（FR1） |
| 停止理由コード | 停止理由を表す安定した閉じた集合の要素（FR2, NFR7） |
| detail | 停止理由に添える人間向けの自由文（FR2） |
| センチネル step 値 | `workflow.yaml` の step が成立していない停止に割り当てる固定値（FR6） |
| 停止条件 5 | implementer 通知待ちで終わる待機ターン。終端行を出さない（FR6） |

## 14. 確認事項

### 14.1 確認済み事項

本 feature は batch mode で実行されており、ユーザーとの対話による確認は行われていない。以下は analyst が導出した仮定として記録する。

- [x] a1: 本 feature の変更対象は Markdown / YAML の SSOT 文書と `tests/` 配下の Python テスト、および 2 つのマニフェストに限られ、実行コード（hooks / scripts）の挙動変更は伴わない。（根拠: 受け入れ条件がすべて文書・契約・テスト・version bump で構成されており、実装物の指定が無いため / 影響度 medium / 可逆）
- [x] a2: 停止表明は em-workflow 側の出力までが責務であり、外部タスク管理サービスのステータス遷移は実装しない。（根拠: task_description のスコープ外節と、notion-batch-develop の規約として明示されているため / 影響度 low / 可逆）
- [x] a3: 停止理由の detail に、パス以外の秘匿情報を含めない。停止出力は外部サービス経由で人間に中継されるため。（根拠: `batch-mode.md` の Reporting が「外部サービスが人間の評価者へ中継する唯一の確認面」と定義しているため / 影響度 low / 可逆）

### 14.2 未確認・保留事項

以下は batch mode で Codex consultation により解決された事項であり、**ユーザー確認は経ていない**（`record_as_assumption: true`）。仮定として記録する。

- [ ] b1（batch 解決 / 未確認）: 終端状態は最終アシスタントメッセージ内の固定接頭辞付き 1 行として出力する（fenced JSON・`--output-schema`・ファイル出力は採らない）。選定理由: 既存の integration ブランチ行 / PR URL 行と同じ行パース方式で受け取れるため。影響度 high / 可逆。
- [ ] b2（batch 解決 / 未確認）: 正常完了時にも停止時と同形式の終端行を出し、行の不在自体を異常として検出できるようにする。選定理由: 「不在＝正常」ではターン打ち切りと正常完了を区別できないため。影響度 high / 可逆。
- [ ] b3（batch 解決 / 未確認）: 停止理由は安定した理由コードの閉じた集合で表し、人間向けの自由文 detail を添える。選定理由: 契約テストで固定できる対象を持たせるため。影響度 medium / 可逆。
- [ ] b4（batch 解決 / 未確認）: 契約対象は SKILL.md の停止条件 2/3/4/6 に限らず、fail-closed abort・`on_unavailable: abort`・implement 2 回目 failed・verify cap 到達・Step C 中断を含む全終端停止点とする。選定理由: 同種の取りこぼしを他経路に残さないため。影響度 high / 可逆。
- [ ] b5（batch 解決 / 未確認）: 停止条件 5 の待機ターンには終端行を出さず、step を持たない停止には固定センチネル step 値を割り当てる。選定理由: 実行中の待機を停止と誤判定しないため。影響度 medium / 可逆。

なお、design ステップは skip 判定である。理由: 変更対象が Markdown / YAML の SSOT 文書、Python 契約テスト、2 つの JSON マニフェストに限られ、UI・画面・視覚要素を伴わない。design-system 候補も 0 件。batch policy `create-spec.design-step`（`decide_autonomously`）により analyst の skip 推奨がそのまま採用された。

## 15. 参考資料

- `em-workflow/references/batch-mode.md`: 出力契約の明記先 SSOT（FR3）
- `em-workflow/references/question-resolution.md`: fail-closed classification による phase abort（FR5）
- `em-workflow/references/batch-policies.yaml`: `on_unavailable: abort`（FR5）
- `em-workflow/skills/develop/SKILL.md`: 停止条件 2/3/4/5/6 と Step C 終了報告（FR4, FR5, FR6）
- `tests/test_routeback_reset_scope_version_bump.py`: 契約テストの既存慣行（NFR4）
- `em-workflow/.claude-plugin/plugin.json` / `.claude-plugin/marketplace.json`: version bump 対象（FR9）
