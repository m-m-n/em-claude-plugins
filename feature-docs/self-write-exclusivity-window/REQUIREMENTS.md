---
title: "self-write-exclusivity-window"
created_date: 2026-10-24
status: draft
---

# self-write-exclusivity-window - 要件定義書

## 1. 概要

### 1.1 背景
scope verification の後、Layer 5 の記録より前に外部の書き換えが入ると、self-write の置換によって、その書き換えが worker の成果物として隠れて記録される。また、排他の前提の適用区間は scope verification の終わりまでとされており、それに依拠する R1 の返却時の手順（再計算・置換・比較・Layer 5 の記録）と食い違っている。

### 1.2 目的
- scope verification の後、Layer 5 の記録より前に入った外部の書き換えが、self-write の置換で worker の成果物として隠れて記録されないようにする。
- 排他の前提の適用区間を、それに依拠する R1 の返却時の手順（再計算・置換・比較・再確認・Layer 5 の記録）と食い違わない形で述べる。

### 1.3 スコープ
- `references/contracts/worker-envelope.md` の Rule R1（『Order』『Known limit』）と『Exclusivity assumption during dispatch』
- `references/phases/create-spec-phase.md` の『Exclusivity assumption (normative)』の『Scope of applicability』
- `references/artifact-digest.md` の『Layer 5 recording』の『When』
- 3 つの dispatch 箇所（develop SKILL.md の design step 5、create-plan-phase.md の §8、rework-task-synthesis.md の §10）
- `tests/` のドキュメントテスト

対象外:
- `scripts/self-write-digest.py`（変更しない）
- `references/phase-state.md` のスキーマ（変更しない）
- requirements-analyst の『Exclusivity assumption』節（analyst-contract.md:215-220）
- spec-writer-contract.md:88-91 と artifact-digest.md:116-119 の記述
- plugin の version

## 2. ビジネス要件

### 2.1 ビジネス目標
- scope verification の後、Layer 5 の記録より前に入った外部の書き換えが、self-write の置換で worker の成果物として隠れて記録されないようにする。
- 排他の前提の適用区間を、それに依拠する R1 の返却時の手順（再計算・置換・比較・再確認・Layer 5 の記録）と食い違わない形で述べる。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| オーケストレーター | R1 の返却時の手順（再計算・置換・比較・再確認・記録）を実行する主体 |

### 2.3 期待される効果
- scope verification の後の外部の書き換えが、再確認の不一致で stale になり、Layer 5 に記録されない。
- 2 文書の排他の前提の区間が、同じ終点で述べられる。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 返却時の再確認で、scope verification の後の書き換えを stale にする | オーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: 返却時の再確認で、scope verification の後の書き換えを stale にする

**アクター**: オーケストレーター

**事前条件**:
- worker が返却し、scope verification が observed change set を出している。
- 比較で stale になっていない。

**基本フロー**:
1. Layer 5 の Calculation を終える。
2. artifacts と self_write_set を記録する phase-state 書き込みの前に、self-write set の各パスの現在の git blob id（`git hash-object --`）と mode・種別（file / symlink / absent）を読み直す。
3. scope verification がそのパスについて観測した変更後の値と比べる。
4. すべて一致すれば、記録の書き込みに進む。

**代替フロー**:
- 1 つでも不一致があるか、再確認を実行できなければ（読み取りの失敗を含む）、result を stale として扱う。扱いは scope verification の stale handling（create-spec-phase.md）に従う。
- self-write set が空なら、再確認は何もせずに通る。

**事後条件**:
- 再現手順（designer に extend_only で tokens.yaml を書かせ、scope verification の直後に外部が既存キーを書き換える）は、文書の規則上、再確認の不一致で stale になる。書き換え後の内容は Layer 5 に記録されない。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | R1 Order に返却時の再確認を足す | 比較の後、記録の phase-state 書き込みの前に、オーケストレーターが self-write set の各パスを読み直して scope verification の観測値と比べる | 高 |
| FR2 | 再確認の比較対象 | git blob id・mode・種別どうしを比べ、raw-byte の sha256 とは混ぜない | 高 |
| FR3 | worker-envelope.md の排他の前提の区間を延ばす | 区間の終点を記録の phase-state 書き込みの完了までにする | 高 |
| FR4 | create-spec-phase.md の区間を揃える | 『Scope of applicability』を FR3 と同じ終点で述べる | 高 |
| FR5 | Known limit の範囲を言い直す | 既存の文言を保ち、scope verification の後の変更と残りの窓の扱いを足す | 高 |
| FR6 | artifact-digest.md の Layer 5『When』を揃える | 比較と再確認の後に記録の書き込みを行うことを、R1 を参照して述べる | 高 |
| FR7 | 3 つの dispatch 箇所が参照で揃う | 再確認を R1 の参照として示し、規則を繰り返さない | 高 |
| FR8 | 再発を検出するドキュメントテスト | 4 つの内容を forged-text の対照付きで固定する | 高 |

### 4.2 機能詳細

#### FR1: R1 Order に返却時の再確認を足す

**説明**: worker-envelope.md の Rule R1『Order』に、比較の後の手順を足す。オーケストレーターは、比較で stale にならず、Layer 5 の Calculation を終えた後で、artifacts と self_write_set を記録する phase-state 書き込みの前に、self-write set の各パスの現在の git blob id（`git hash-object --`）と mode・種別（file / symlink / absent）を読み直す。そして scope verification がそのパスについて観測した変更後の値と比べる。1 つでも不一致があるか、再確認を実行できなければ（読み取りの失敗を含む）、result を stale として扱う。stale の扱いは scope verification の stale handling（create-spec-phase.md）に従う。self-write set が空なら、再確認は何もせずに通る。

**ビジネスルール**:
- 既存の 4 段の手順とその文言は残し、再確認を後ろに足す。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 再確認の不一致 | self-write set のいずれかのパスの blob id・mode・種別が観測値と異なる | result を stale として扱う |
| 再確認の失敗 | 再確認を実行できない（読み取りの失敗を含む） | result を stale として扱う |

#### FR2: 再確認の比較対象

**説明**: 再確認では、scope verification と同じ種類の値（git blob id、mode、種別）どうしを比べる。raw-byte の sha256（artifact-digest.md の Calculation、digest_inputs）とは混ぜない。比較の基準にする観測値は、同じ run の scope verification が出した observed change set の値とする。

#### FR3: worker-envelope.md の排他の前提の区間を延ばす

**説明**: 『Exclusivity assumption during dispatch』の適用区間を、dispatch の scope snapshot の取得から、run の artifacts と self_write_set を記録する phase-state 書き込みの完了までとする。written_artifacts が空の run では、返却された status と self_write_set を記録する書き込みの完了まで。result が stale と判定された場合は、その判定までとする。

**ビジネスルール**:
- 五つの worker に限ること、恒常的な制約ではないこと、review の wave-parallel auto-fix loop が例外であることは変えない。

#### FR4: create-spec-phase.md の区間を揃える

**説明**: 『Exclusivity assumption (normative)』の『Scope of applicability』を、FR3 と同じ終点で述べる。worker-envelope.md と食い違わないようにする。

#### FR5: Known limit の範囲を言い直す

**説明**: R1 の『Known limit』は、scope verification より前に worker と別の主体が同じ permitted path を変えた場合を排他の前提に委ねる記述として残す（現在の文言を保つ）。そのうえで、scope verification の後の変更は FR1 の再確認が検出すること、再確認から記録までの残りの窓は延ばした区間が覆うことを足す。

#### FR6: artifact-digest.md の Layer 5『When』を揃える

**説明**: artifact-digest.md の『Layer 5 recording』の『When』を、layer 4 を通っただけでなく、R1 の返却時の比較と再確認で stale にならなかった後に記録の書き込みを行うことが読み取れる形に直す。

**ビジネスルール**:
- R1（worker-envelope.md の『Recomputation and comparison timing』）を参照し、手順は繰り返して書かない。
- Calculation が再確認の前に走ることと、記録の書き込みが再確認の後に来ることを食い違わせない。

#### FR7: 3 つの dispatch 箇所が参照で揃う

**説明**: develop SKILL.md の design step 5、create-plan-phase.md の §8、rework-task-synthesis.md の §10 は、再確認を R1 の参照として示す。順序は、比較（または validate-worker-output.py での検証）の後、Layer 5 の記録と self_write_set の記録の書き込みの前。再確認で不一致か失敗なら stale になる。

**ビジネスルール**:
- membership の表、置換、再確認の比較規則は繰り返して書かない。
- 既存の『scope verification → self-write-digest.py → Layer 5 recording』の順と、各箇所の既存の文言は保つ。

#### FR8: 再発を検出するドキュメントテスト

**説明**: tests/ に unittest のドキュメントテストを足すか、既存のものを強める。固定する内容は次の 4 つ。

- (a) 2 文書の区間の終点が phase-state の記録書き込みまで延びていること。
- (b) R1 Order の再確認の手順。オーケストレーターが行い、blob id・mode・種別を scope verification の観測値と比べ、不一致や失敗で stale になり、比較の後かつ記録の前に置かれること。
- (c) artifact-digest.md の『When』。
- (d) 3 つの dispatch 箇所の参照と順序。

**ビジネスルール**:
- どの probe にも forged-text の対照を付け、旧い文言で probe が反応することを示す。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
該当なし

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1: テストは Python 標準ライブラリの unittest だけを使い、python3 -m unittest discover -s tests で通る。ファイル名は test_<target>.py、クラス名は Test<Behavior>、メソッド名は test_<condition>_<expected_result> にする（test/README.md）。
- NFR2: ドキュメントテストは見出しで切り出して空白を正規化した文字列で検証する。改行位置にも文書全体の一致にも依存しない。
- NFR3: 既存のテストは通ったままにする。R1 の領域に足す文で digest に触れるものは、オーケストレーターを主語にするか否定文にする（test_ac5_every_digest_sentence_of_the_self_write_rule_names_the_orchestrator_or_is_negated、find_worker_directed_digest_instructions、check_worker_digest_stance）。
- NFR4: R1 にラベル付きのブロックを足す場合は、tests/test_self_write_digest_docs.py の R1_LABELS にも加え、各ラベルが 1 回だけ現れるようにする。再確認を既存の『Order』ブロックの中に書くなら、ラベルは足さない。

### 5.5 互換性要件
- NFR5: worker-envelope.md に expect_digest のトークンを入れない。R1 の正規化の段落と digest_source の 7 つのキーは変えない。
- NFR6: scripts/self-write-digest.py は変えない（スクリプトは digest を計算しない）。再確認はオーケストレーターが行う。
- NFR7: plugin の version は変更しない。

## 6. UI/UX要件

該当なし（UI 成果物は無い）

## 7. データ要件

該当なし（phase-state.md のスキーマは変えない）

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- `scripts/self-write-digest.py` は変えない。
- phase-state.md のスキーマは変えない。
- 排他の前提は、延ばした後も lock や hook では強制しない。

### 9.2 ビジネス上の制約
- plugin の version は変更しない。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/self-write-exclusivity-window/**`
- `test-docs/self-write-exclusivity-window/**`

`feature-docs/self-write-exclusivity-window/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/self-write-exclusivity-window/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/self-write-exclusivity-window/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 再確認から記録の書き込みまでの窓 | 低 | 延ばした排他の前提の区間で覆う。lock や hook では強制しない |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC-1: worker-envelope.md R1『Order』が、比較の後、artifacts と self_write_set を記録する phase-state 書き込みの前に行う再確認を、オーケストレーターの手順として述べている。そこには、self-write set の各パスの現在の blob id・mode・種別を scope verification の観測値と比べることと、不一致または再確認の失敗で stale になることが含まれる。（FR1, FR2）
- [ ] AC-2: worker-envelope.md『Exclusivity assumption during dispatch』と create-spec-phase.md『Scope of applicability』が、同じ終点（記録の phase-state 書き込みの完了。stale のときはその判定まで）を述べている。（FR3, FR4）
- [ ] AC-3: Known limit が、scope verification より前の競合を前提に委ねる既存の文言を保ったまま、その後の変更は再確認が検出することを述べている。（FR5）
- [ ] AC-4: artifact-digest.md『Layer 5 recording』の『When』が、R1 の比較と再確認の後に記録の書き込みを行うことを、R1 を参照して述べている。（FR6）
- [ ] AC-5: 3 つの dispatch 箇所が、比較と記録書き込みの間にある再確認を R1 の参照として示しており、規則を繰り返して書いていない。既存の順序の anchor は保たれている。（FR7）
- [ ] AC-6: 再現手順（designer に extend_only で tokens.yaml を書かせ、scope verification の直後に外部が既存キーを書き換える）は、文書の規則上、再確認の不一致で stale になる。書き換え後の内容は Layer 5 に記録されない。（FR1, FR2）
- [ ] AC-7: 新しいテストは、修正前の文書に対応する forged-text では失敗し、修正後の文書では通る。python3 -m unittest discover -s tests が全部通る。（FR8）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1: worker-envelope.md の Exclusivity 節で、区間の終点が記録の phase-state 書き込みを名指していることを確かめる。旧文言（'through the end of that dispatch's scope verification' で終わるもの）の forged-text では probe が反応する。（AC-2）
- [ ] TS-2: create-spec-phase.md の Scope of applicability について、TS-1 と同じことを確かめる。旧文言（'through the end of verification'）の forged-text を対照にする。（AC-2）
- [ ] TS-3: R1 Order の切り出しに、再確認の要素が既存 4 段の anchor の後、記録の前の順で現れることを確かめる。要素は、オーケストレーターが主語であること、blob id・mode・種別、scope verification の観測値、不一致または失敗で stale、の 4 つ。再確認を欠いた forged の Order では probe が反応する。（AC-1）
- [ ] TS-4: 既存の Order・Known limit・digest-sentence のテスト（tests/test_self_write_digest_docs.py）がそのまま通ることを確かめる。（AC-1, AC-3）
- [ ] TS-5: Known limit が既存の 3 句を保ち、scope verification の後の変更は再確認が検出することを述べていることを確かめる。（AC-3）
- [ ] TS-6: artifact-digest.md の Layer 5 recording の『When』が R1 を参照し、比較と再確認の後の記録を述べていることを確かめる。旧文言（'after layer 4 (scope verification) passes' だけのもの）の forged-text を対照にする。（AC-4）
- [ ] TS-7: 3 つの dispatch 箇所それぞれで、SCRIPT_TOKEN → 再確認の参照 → Layer 5 recording（rework §10 では SCRIPT_TOKEN → step 3 validates → 再確認 → 記録）の順を確かめる。R1 を引用していることと、規則を繰り返していないことも確かめる。forged-text を対照にする。（AC-5）
- [ ] TS-8: python3 -m unittest discover -s tests の全体が通る。（AC-7）

### 12.2 エッジケース
- self-write set が空の run では、再確認は何もせずに通る。
- written_artifacts が空の run では Layer 5 の Calculation が走らない。再確認は比較の後、status と self_write_set を記録する書き込みの前に行う。
- created のパスは、absent から file への変化として観測される。再確認では、現在もその blob id・mode・種別のままかを見る。
- regenerate のターゲットは、source が member のときだけ self-write set に入る。入った場合は再確認の対象になる。
- 再確認の時点でパスが消えている、symlink に変わっている、または読めない場合は、不一致または失敗として stale にする。
- 書き換えて元に戻した（ABA）場合は、内容が同じなので検出されず、実害も無い。
- HEAD が動いた stale の経路では、再計算も再確認も記録も走らない。区間は stale の判定で終わる。
- 再開時（substitute_only）は、永続化された self_write_set を使う。記録の後の書き換えは、Resume decision table の read input 5（成果物の本文と記録した digest の比較）が検出する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 再確認 | 比較の後、記録の phase-state 書き込みの前に、オーケストレーターが self-write set の各パスの現在の git blob id・mode・種別を読み直し、scope verification の観測値と比べる手順（FR1） |
| 観測値 | 同じ run の scope verification が出した observed change set の値（FR2） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] design step: skipped（変更はプロトコルの Markdown とドキュメントテストだけで、UI 成果物が無い。create-spec.design-step を batch-policies で decide_autonomously と解決した）
- [x] A1: requirements-analyst の『Exclusivity assumption』節（analyst-contract.md:215-220）は変更しない。
- [x] A2: spec-writer-contract.md:88-91 と artifact-digest.md:116-119 にある、pre-dispatch verification から worker の書き込みまでを排他の前提が守るという記述は変更しない。
- [x] A3: 再確認の基準にする scope verification の観測値は、同じ run の中で保持するだけにして、phase-state には永続化しない。phase-state.md のスキーマは変えない。
- [x] A4: plugin の version は変更しない（patch は Actions が上げる）。
- [x] A5: 排他の前提は、延ばした後も lock や hook では強制しない。再確認から記録の書き込みまでの窓は、前提で覆う。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- `references/contracts/worker-envelope.md`
- `references/phases/create-spec-phase.md`
- `references/artifact-digest.md`
- `tests/test_self_write_digest_docs.py`
