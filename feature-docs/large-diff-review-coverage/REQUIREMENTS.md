---
title: "large-diff-review-coverage"
created_date: 2026-11-07
status: draft
---

# large-diff-review-coverage - 要件定義書

## 1. 概要

### 1.1 背景

記載なし。

### 1.2 目的

- 実施できなかった観点を「指摘なし」と区別する
- 差分が大きくても選択された観点を実施する

### 1.3 スコープ

**対象**:

- em-workflow と em-review の codex-reviewer のタイムアウトと non-JSON の扱い(FR1、FR2、FR17)
- em-workflow の Phase R2b における litellm の空結果の扱い(FR3)
- 未実施と部分実施の開示(FR4、FR13、FR15、FR16)
- em-workflow のレビュー入力のサイズ計測、シャード分割、dispatch 上限、run_id、シャード単位の chain walk(FR5 から FR9)
- review_data_too_large の経路(FR10)
- spec 観点の全差分優先と救済 run の扱い(FR11、FR12)
- Phase R4 再レビューの網羅(FR14)
- 再発検出テスト(FR18)

**対象外**:

- vertex-review プラグインの変更(NFR2)
- レビュアーの入力フィールドと review-output-schema.json の変更(NFR5)
- em-review への分割、dispatch 上限、review_data_too_large の経路の適用(FR17)
- 完了ゲートの条件の変更と新しい gate の追加(FR15)

## 2. ビジネス要件

### 2.1 ビジネス目標

- 実施できなかった観点を「指摘なし」と区別する
- 差分が大きくても選択された観点を実施する

### 2.2 対象ユーザー

記載なし。

### 2.3 期待される効果

記載なし。

## 3. ユースケース

記載なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | Codex タイムアウトの区別 | confirmed |
| FR2 | Codex の non-JSON の区別 | confirmed |
| FR3 | litellm の空結果の区別 | confirmed |
| FR4 | 未実施の開示 | confirmed |
| FR5 | レビュー入力のサイズ計測 | confirmed |
| FR6 | ファイル単位のシャード分割 | confirmed |
| FR7 | dispatch 上限 | confirmed |
| FR8 | run_id | confirmed |
| FR9 | シャード単位の chain walk | confirmed |
| FR10 | review_data_too_large の経路 | confirmed |
| FR11 | spec 観点の全差分優先 | confirmed |
| FR12 | 救済 run の未実装指摘 | confirmed |
| FR13 | 部分実施の記録 | confirmed |
| FR14 | R4 再レビューの網羅 | confirmed |
| FR15 | 完了と報告 | confirmed |
| FR16 | evaluator への受け渡し | confirmed |
| FR17 | em-review の揃え | confirmed |
| FR18 | 再発検出テスト | confirmed |

### 4.2 機能詳細

#### FR1: Codex タイムアウトの区別

**説明**: codex-reviewer は Step 6 の最初に、JSON パースより前かつ優先してラッパーの終了コード 124 を判定する。124 のときは次を返す。途中の findings は保持しない。判定は終了コードだけで行い、出力の文字列では行わない。

```json
{"findings": [], "summary": "skipped: codex timed out", "skipped": true, "skip_reason": "harness_unavailable", "source": "codex"}
```

**受け入れ基準**: AC1

**テストシナリオ**: TS-1

#### FR2: Codex の non-JSON の区別

**説明**: codex-reviewer は JSON をパースできず、rate-limit と unsupported-model のどちらにも該当しないとき、次を返す。

```json
{"findings": [], "summary": "skipped: codex returned non-JSON output", "skipped": true, "skip_reason": "harness_unavailable", "source": "codex"}
```

**受け入れ基準**: AC2

**テストシナリオ**: TS-1

#### FR3: litellm の空結果の区別

**説明**: Phase R2b は、orchestrator が記録した実行元が litellm で、findings が空で、summary が `litellm model output truncated` または `litellm returned non-JSON output` に完全一致する結果を完了として扱わない。この run は status: failed とし、既存の malformed-result 経路で Claude fallback を 1 回実行する。これ以外の結果にはスキーマ適合だけの判定を維持する。

**受け入れ基準**: AC2

**テストシナリオ**: TS-2

#### FR4: 未実施の開示

**説明**: dispatch した観点で完了した run が 1 つも無いものは、最後の skip_reason が再試行可能かどうかに関係なく unreviewed_perspectives に載せる。requires_spec により dispatch しなかった観点は載せない。axis 2 の source: tool の run は載せない。

**受け入れ基準**: AC3

**テストシナリオ**: TS-5

#### FR5: レビュー入力のサイズ計測

**説明**: Phase R2 の fan-out 前に、ファイルごとのレビュー入力の文字数を測る。diff mode の tracked ファイルはそのファイルの diff テキスト、whole-codebase mode のファイルと standalone の untracked ファイルはファイル内容を測る。diff に現れない入力も計測から漏らさない。

**受け入れ基準**: AC4

**テストシナリオ**: TS-3

#### FR6: ファイル単位のシャード分割

**説明**: レビュー入力の合計が 200,000 文字を超えるとき、changed_files をファイル単位でシャードに分ける。各シャードは 200,000 文字以下とする。1 ファイルで 200,000 文字を超えるものは単独のシャードにする。1 ファイルは 1 シャードにだけ属する。シャードごとに Phase R0 step 3 の検証済みパスから diff_cmd_quoted を作る。spec 以外の全観点・全ハーネスに適用し、Phase R2、Phase R4 の再レビュー、develop 駆動、standalone、diff mode、whole-codebase mode で同じ手順を使う。

**受け入れ基準**: AC4、AC7

**テストシナリオ**: TS-3

#### FR7: dispatch 上限

**説明**: 1 ラウンドの primary reviewer dispatch を 24 件までにする。観点あたりのシャード数は floor(24 / 選択観点数) を上限とし、超過したシャードは決定的に未実施として開示する。再試行と Claude fallback は数えない。Phase R4 の再レビューはループごとに同じ上限を別に適用する。

**受け入れ基準**: AC5

**テストシナリオ**: TS-4

#### FR8: run_id

**説明**: run_id はシャード、chain エントリ、ループを識別する。形式は `{perspective}[@s{k}]#[loop{N}.]{chain_index|fallback}` とし、`@s{k}` は分割時だけ付ける。Phase R4 の run は chain walk が同じループで複数回起きても一意になるよう `loop{N}.{chain_index|fallback}` を使う。

**受け入れ基準**: AC6

**テストシナリオ**: TS-6

#### FR9: シャード単位の chain walk

**説明**: Phase R2 の 1 reviewer、Phase R2b の最大 2 回のフォールバック、Claude fallback 1 回、最後の結果による置き換えは、観点単位ではなくシャード単位で適用する。あるシャードの結果が別のシャードの結果を置き換えることはない。

**受け入れ基準**: AC6、AC7

**テストシナリオ**: TS-6

#### FR10: review_data_too_large の経路

**説明**: em-workflow の Phase R2b は review_data_too_large を再試行理由に加え、別ハーネスの次のエントリへ進める。chain が尽きたら既存の Claude fallback を実行する。

**受け入れ基準**: AC7

**テストシナリオ**: TS-7

#### FR11: spec 観点の全差分優先

**説明**: spec 観点は分割せず、全差分で通常の chain を実行する(muse-spark、Codex の自己取得、Claude fallback の順)。その全経路が完了しなかったときだけ、シャード単位の救済 run を実行する。救済 run を実行した spec は、全シャードが完了しても一部実施として開示する。

**受け入れ基準**: AC8

**テストシナリオ**: TS-7

#### FR12: 救済 run の未実装指摘

**説明**: spec の救済 run が報告した未実装系の指摘は `resolution: unresolved`、`resolution_reason` は `unverified` で始める形で記録し、auto-fix 候補と residual critical/high から除外する。Phase R4 の再レビューと evaluator 失敗時の経路でも同じ扱いを維持する。

**受け入れ基準**: AC8

**テストシナリオ**: TS-7

#### FR13: 部分実施の記録

**説明**: unreviewed_perspectives は全体が未実施の観点の一覧のまま維持する。round 記録のルートに `partially_reviewed_perspectives` を追加し、完了した run と未実施の範囲が併存する観点を、観点名、未実施ファイル、理由の組で記録する。無いときは空で存在させる。

**受け入れ基準**: AC8

**テストシナリオ**: TS-5

#### FR14: R4 再レビューの網羅

**説明**: Phase R4 のループごとに現在の差分からシャードを作り直す。観点とファイルの組は、そのファイルの最終内容を見た完了 run があるときだけ実施済みとする。修正で変わったファイルは修正前の完了 run で実施済みにしない。修正で変わっていないファイルは既存の完了 run を維持する。

**受け入れ基準**: AC9

**テストシナリオ**: TS-5

#### FR15: 完了と報告

**説明**: 完了ゲートは residual_critical_high == 0 のまま変えない。Phase R6 に unreviewed_perspectives と partially_reviewed_perspectives の両方を出す。--batch の最終結果にも両方を出し、batch-mode.md の `## Reporting` と Audit-item source map に追加する。新しい gate は足さない。

**受け入れ基準**: AC10

**テストシナリオ**: TS-7

#### FR16: evaluator への受け渡し

**説明**: Phase R3a の入力に unreviewed_perspectives と partially_reviewed_perspectives を含める。Independent Inspection Duty の対象外は unreviewed_perspectives の観点だけとする。部分実施の観点は対象のままとする。

**受け入れ基準**: AC10

**テストシナリオ**: TS-7

#### FR17: em-review の揃え

**説明**: em-review の codex-reviewer に FR1 と FR2 を適用し、em-review の review-protocol.md の skip の説明を揃える。分割、dispatch 上限、review_data_too_large の経路は em-review に適用しない。

**受け入れ基準**: AC11

**テストシナリオ**: TS-1

#### FR18: 再発検出テスト

**説明**: サイズ計測、シャード分割、dispatch 上限、未実施と部分実施の判定を scripts/ 配下の Python スクリプトに置き、tests/ の単体テストで検証する。agent と references の規定は tests/ のテキスト検査で固定する。

**受け入れ基準**: AC13

## 5. 非機能要件

| ID | 要件 | 受け入れ基準 | テストシナリオ |
|----|------|--------------|----------------|
| NFR1 | レビュー入力が 200,000 文字以下の round では、dispatch 数と round 記録の既存フィールドの意味が現行と同じ。Phase R4 の run_id の形式だけ FR8 に従う | AC12 | TS-8 |
| NFR2 | vertex-review プラグインを変更せずに動作する | - | - |
| NFR3 | orchestrator の context に差分本文を入れない。スクリプトはパス、文字数、シャード構成だけを返す | - | - |
| NFR4 | 同じ入力からは同じシャード、同じ超過シャードを作る | AC4 | - |
| NFR5 | レビュアーの入力フィールドと review-output-schema.json は変更しない。シャードは changed_files と diff_cmd_quoted の範囲で表す | AC12 | TS-8 |
| NFR6 | テストは標準ライブラリの unittest だけを使い、シェル系は一時ディレクトリの使い捨て git リポジトリで検証する | - | - |

## 6. UI/UX要件

UI の変更は無い。デザインステップは実施しない。

## 7. データ要件

### 7.1 データモデル概要

round 記録に、未実施と部分実施を表す次の 2 フィールドを持つ。

### 7.2 データ項目

| エンティティ | 項目名 | 必須 | 説明 |
|--------------|--------|------|------|
| round 記録 | `unreviewed_perspectives` | ○ | 全体が未実施の観点の一覧 |
| round 記録 | `partially_reviewed_perspectives` | ○ | 完了した run と未実施の範囲が併存する観点を、観点名、未実施ファイル、理由の組で記録する。無いときは空で存在させる |

### 7.3 データ保持期間

記載なし。

## 8. 外部連携

記載なし。

## 9. 制約条件

### 9.1 技術的制約

- 分割、dispatch 上限、review_data_too_large の経路は em-review に適用しない(FR17)
- vertex-review プラグインを変更しない(NFR2)
- レビュアーの入力フィールドと review-output-schema.json を変更しない(NFR5)
- orchestrator の context に差分本文を入れない(NFR3)

### 9.2 ビジネス上の制約

記載なし。

### 9.3 スケジュール制約

記載なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/large-diff-review-coverage/**`
- `test-docs/large-diff-review-coverage/**`

`feature-docs/large-diff-review-coverage/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/large-diff-review-coverage/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/large-diff-review-coverage/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/large-diff-review-coverage/` ディレクトリを生成しないが、宣言された `test-docs/large-diff-review-coverage/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 200,000 文字は 540 秒以内の完了を保証しない初期値である(A12) | 中 | 時間切れは FR1 と chain walk で扱う |
| シャードをまたぐ設計上の問題を見逃しうる(A13) | 中 | 既知の制約とする。シャードの調査予算は既存の 3 ファイルのままとする |

### 10.2 ビジネスリスク

記載なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1(FR1): exit 124 の Codex 実行は、出力に有効な JSON が含まれていても skipped:true、skip_reason harness_unavailable、findings 空になる
- [ ] AC2(FR2、FR3): Codex の non-JSON と litellm の定型 summary 2 種の結果が completed にならない。実行元が litellm 以外、findings が非空、summary が不一致のいずれかなら FR3 の扱いにならない
- [ ] AC3(FR4): dispatch した観点が非再試行の skip だけで終わると unreviewed_perspectives に載る
- [ ] AC4(FR5、FR6、NFR4): 200,000 文字を超える入力が、同じ入力で常に同じ、1 ファイル 1 シャードの構成に分かれる。whole-codebase のファイルと untracked ファイルも計測される
- [ ] AC5(FR7): 選択観点数 N のとき観点あたりのシャードが floor(24 / N) 以下に収まり、超過分が未実施として記録される
- [ ] AC6(FR8、FR9): 同一 round の run_id が重複せず、1 シャードの skip や置き換えが他シャードの結果に影響しない
- [ ] AC7(FR6、FR9、FR10): 300,000 文字を超える差分で performance / architecture に完了した run が残り、完了しなかった範囲は記録に載る
- [ ] AC8(FR11、FR12、FR13): spec は全差分の経路が全滅したときだけ救済 run を実行し、救済を経た spec は部分実施として記録され、救済 run の未実装系の指摘は auto-fix と residual に入らない
- [ ] AC9(FR14): 修正前に完了していたファイルが修正で変わり、再レビューが完了しなければ、そのファイルは未実施として記録される
- [ ] AC10(FR15、FR16): 完了ゲートの条件が変わらず、R6、batch の Reporting、source map、R3a の入力に 2 フィールドが揃う
- [ ] AC11(FR17): em-review の codex-reviewer が exit 124 と non-JSON で skipped:true を返し、分割の規定は持たない
- [ ] AC12(NFR1、NFR5): 200,000 文字以下の round は単一の入力のまま dispatch され、レビュアーの入力フィールドと review-output-schema.json が変わらない
- [ ] AC13(FR18): `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` が成功する

### 11.2 KPI

記載なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS-1(FR1、FR2、FR17): 両 plugin の codex-reviewer の Step 6 で、終了コード 124 の判定が JSON パースより前にあり、規定の skip オブジェクトを返す規定があることをテキスト検査する
- [ ] TS-2(FR3): 実行元・findings・summary の組み合わせごとに failed の判定を検証する
- [ ] TS-3(FR5、FR6): 使い捨て git リポジトリで、tracked、untracked、whole-codebase、rename、バイナリ、単独超過ファイルの計測と分割を検証する
- [ ] TS-4(FR7): 選択観点数 1 から 6 までのシャード上限と超過シャードの決定性を検証する
- [ ] TS-5(FR4、FR13、FR14): perspective_runs の組み合わせから、未実施、部分実施、修正後の失効を判定する
- [ ] TS-6(FR8、FR9): シャード、chain、ループが重なる run_id の一意性とシャード単位の結果置き換えを検証する
- [ ] TS-7(FR10、FR11、FR12、FR15、FR16): R2b の表、spec の順序、救済 run の扱い、完了ゲート、Reporting、source map、R3a の入力をテキスト検査する
- [ ] TS-8(NFR1、NFR5): 上限以下の入力が 1 シャードになること、スキーマと Inputs セクションの固定が保たれることを検証する

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 救済 run | spec 観点の全差分の全経路が完了しなかったときだけ実行する、シャード単位の run |
| 未実装系 | 変更箇所の誤りではなく、要求に対応する実装が見えた差分に無いことを主張する指摘。判定は orchestrator が行い、判断できないときは未実装系として扱う |
| 選択観点数 | spec を含む Task dispatch の観点の数。axis 2 の vulnerability は数えない |

## 14. 確認事項

### 14.1 確認済み事項

記載なし。

### 14.2 未確認・保留事項

次の事項は前提として扱う。

- [ ] A1(影響度: medium): Codex のタイムアウトには skip_reason の harness_unavailable を使い、新しい skip_reason は足さない
- [ ] A2(影響度: high): exit 124 の判定は JSON パースより前に置いて優先し、結果は skipped:true、harness_unavailable、findings 空とする。途中の findings は保持しない
- [ ] A3(影響度: high): vertex-review プラグインは変更しない
- [ ] A4(影響度: medium): 分割は Phase R2、Phase R4、develop 駆動、standalone、diff mode、whole-codebase mode の全経路に適用する
- [ ] A5(影響度: medium): 計測、分割、上限、未実施の判定は標準ライブラリの Python スクリプトに置く
- [ ] A6(影響度: low): review-output-schema.json は変更しない
- [ ] A7(影響度: low): version は手で上げない
- [ ] A8(影響度: medium): 未実装系とは、変更箇所の誤りではなく、要求に対応する実装が見えた差分に無いことを主張する指摘を指す。判定は orchestrator が行い、判断できないときは未実装系として扱う
- [ ] A9(影響度: low): FR3 の結果は skip_reason を作らず、既存の malformed-result 経路に乗せる
- [ ] A10(影響度: low): 選択観点数は spec を含む Task dispatch の観点を数え、axis 2 の vulnerability は数えない。spec の救済 run は floor(24 / 選択観点数) を上限とする
- [ ] A11(影響度: low): 超過シャードはパス順に並べたシャードの後ろから選ぶ
- [ ] A12(影響度: medium): 200,000 文字は 540 秒以内の完了を保証しない初期値とする
- [ ] A13(影響度: medium): シャードをまたぐ設計上の問題を見逃しうることは既知の制約とする。シャードの調査予算は既存の 3 ファイルのままとする

## 15. 参考資料

記載なし。
