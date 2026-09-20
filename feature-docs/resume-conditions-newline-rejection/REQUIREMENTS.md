---
title: "resume-conditions-newline-rejection"
created_date: 2026-09-20
status: draft
---

# resume-conditions-newline-rejection - 要件定義書

## 1. 概要

### 1.1 背景

batch 構造化結果の SSOT である `em-workflow/references/batch-terminal-line.md` が自己矛盾している。`## Field values` は `resume_conditions` の CR / LF / TAB を `## Escaping` のエスケープとして残すと定めているのに、`## Consumer constraints` の「em-workflow's OWN emitter obligations and rejection rules」の最初の箇条書きは `detail` と `resume_conditions` の両方について、デコード後の行終端文字を拒否すると定めている。その結果、複数行の復旧手順を持つ `state: stopped` の結果——停止結果の通常形——に合法な表現が存在しない。

### 1.2 目的

- 停止結果の通常形（複数行の復旧手順を持つ `state: stopped` の結果）に合法な表現を与えるため、SSOT の自己矛盾を取り除く。
- SSOT 自身のハードニング規則を実行可能な形に保つ。すなわち、実装がこのドキュメントだけを読んで、フィールドごとにどのデコード済みコードポイントが拒否されるかを判断できる状態にする。

### 1.3 スコープ

対象は次の 4 ファイル。

| ファイル | 変更内容 |
|----------|----------|
| `em-workflow/references/batch-terminal-line.md` | `## Consumer constraints` の OWN-rules 箇条書きの分割と、「cannot fire」文の書き換え |
| `tests/test_batch_stop_contract.py` | 適合性マッチャの更新、偽造サンプルの更新、新規の肯定テストの追加 |
| `em-workflow/.claude-plugin/plugin.json` | em-workflow の version 引き上げ |
| `.claude-plugin/marketplace.json` | em-workflow エントリの version 引き上げ |

スコープ外:

- `## Result format` と `## Escaping` の編集（A5）。
- 5 個の引き継ぎ済み番号付き consumer constraints の変更（A6）。
- `em-workflow/references/batch-mode.md` と `em-workflow/skills/develop/SKILL.md` の編集（A7）。
- ランタイムのスクリプト・フック・スキルの挙動変更（NFR4）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- batch 構造化結果 SSOT の自己矛盾を取り除き、停止結果の通常形（複数行の復旧手順を持つ `state: stopped` の結果）に合法な表現を与える。
- SSOT 自身のハードニング規則を実行可能に保つ。実装がこのドキュメントだけからフィールドごとの拒否対象コードポイントを判断できるようにする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| SSOT を読む実装者 | `batch-terminal-line.md` だけを読んで、フィールドごとにどのデコード済みコードポイントが拒否されるかを判断する |
| 停止結果の出力側 | 複数行の復旧手順を `resume_conditions` に載せた `state: stopped` の結果を出力する |

### 2.3 期待される効果

- 複数行の Markdown 改行を含む `resume_conditions` の値が、合法かつ通常形の値として扱われる。
- `## Field values` と `## Consumer constraints` を順に読んでも矛盾が生じない。
- `detail` の拒否規則は実質的に変わらないまま、その理由が本文に明示される。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | フィールドごとの拒否対象コードポイントを判断する | SSOT を読む実装者 | 高 |
| UC02 | 複数行の復旧手順を持つ停止結果を表現する | 停止結果の出力側 | 高 |

### 3.2 ユースケース詳細

#### UC01: フィールドごとの拒否対象コードポイントを判断する

**アクター**: SSOT を読む実装者

**事前条件**:
- `em-workflow/references/batch-terminal-line.md` が参照できる。

**基本フロー**:
1. `## Field values` の `resume_conditions` の箇条書きを読む。
2. `## Consumer constraints` の OWN-rules ラベル配下の最初の箇条書きを読む。
3. `detail` と `resume_conditions` それぞれについて、デコード後に拒否されるコードポイントを判断する。

**代替フロー**:
- CR / LF / TAB 以外の端末制御コードポイントが `resume_conditions` に含まれる場合は、拒否と判断する。

**事後条件**:
- 2 つの節の記述の間に矛盾がない（AC1）。

**ユースケース図**: 該当なし。

#### UC02: 複数行の復旧手順を持つ停止結果を表現する

**アクター**: 停止結果の出力側

**事前条件**:
- 復旧手順が複数行である。

**基本フロー**:
1. 復旧手順を `resume_conditions` に全文で載せる。
2. CR / LF / TAB を `## Escaping` のエスケープとして保つ。
3. `state: stopped` の結果として出力する。

**代替フロー**:
- 該当なし。

**事後条件**:
- 出力した値が合法な通常形の値として成立する。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 共有の OWN-rules 箇条書きをフィールド別規則に分割する | `detail` と `resume_conditions` を別々の規則にする | 高 |
| FR2 | 改行の例外を明示する | `resume_conditions` の CR / LF / TAB が違反でないことを書く | 高 |
| FR3 | `detail` の根拠を残す | 正規化済みのはずという理由を書く | 高 |
| FR4 | 「cannot fire」の文を書き換える | 規則集合と矛盾しない前置きにする | 高 |
| FR5 | 固定済みセクションを触らない | `## Result format` / `## Escaping` / 5 個の番号付き制約を保つ | 高 |
| FR6 | `## Field values` の固定リテラルを保つ | 既存テストが固定する文言を維持する | 高 |
| FR7 | 適合性マッチャを更新する | `_assert_own_hardening_rules_stated` を新文言に合わせる | 高 |
| FR8 | 否定証明のサンプルを更新する | `FORGED_OWN_RULES_PARTIAL` を新文言下でも成立させる | 高 |
| FR9 | 改行例外の肯定ケースを追加する | 否定証明付きの新規マッチャを足す | 高 |
| FR10 | プラグイン version を引き上げる | plugin.json と marketplace.json を同じ値にする | 高 |

### 4.2 機能詳細

#### FR1: 共有の OWN-rules 箇条書きをフィールド別規則に分割する

**説明**: `em-workflow/references/batch-terminal-line.md` の `## Consumer constraints` において、「em-workflow's OWN emitter obligations and rejection rules」というラベルの配下にある最初の箇条書きを、フィールドごとの規則に置き換える。`detail` はデコード後の行終端文字または端末制御コードポイントを拒否する（実質的に変更なし）。`resume_conditions` はデコード後の、CR (U+000D) / LF (U+000A) / TAB (U+0009) 以外の端末制御コードポイントのみを拒否する。

**入力**: 変更前の `batch-terminal-line.md`

**出力**: フィールド別規則に分割された OWN-rules 箇条書き

**ビジネスルール**:
- `resume_conditions` の拒否対象は、CR / LF / TAB 以外の端末制御コードポイント。
- `detail` の拒否対象は、行終端文字または端末制御コードポイント。

**バリデーション**: 該当なし（文書の文言変更のため、実行時のバリデーションは発生しない）。

**エラーケース**: 該当なし。

#### FR2: 改行の例外を明示する

**説明**: `resume_conditions` の規則は、デコード後の CR / LF / TAB が `resume_conditions` の中にあっても違反ではないことを明示的に述べる。理由は、`## Field values` がそれらを潰さず `## Escaping` のエスケープとして残ると定めているため。

**ビジネスルール**:
- 例外の集合は CR (U+000D)、LF (U+000A)、TAB (U+0009) の 3 つ（A1）。
- 旧規則が対象としていたそれ以外のコードポイント（U+2028 / U+2029 および C0 / C1 の端末制御域を含む）は拒否のまま（A1）。

#### FR3: `detail` の根拠を残す

**説明**: `detail` の規則は、その理由を述べる。`## Field values` が `detail` 中のすべての CR / LF / TAB をエスケープ前に空白へ置換しているため、生き残っているものがあれば正規化が飛ばされたことを意味し、拒否が正しい。

#### FR4: 「cannot fire」の文を書き換える

**説明**: 次の文を、FR1 適用後の規則集合と整合するように書き換える。

> Each of the four cannot fire while `## Escaping` is honoured: they are defense in depth for the case an unescaped newline inside a value is followed by a line that looks like another key.

**ビジネスルール**:
- 一律の「cannot fire」という主張を落とす（A8）。
- ブロックは em-workflow 自身のハードニング規則として端的に導入する。
- 陳腐化する数詞を置かない。
- 直下の規則と矛盾する主張を置かない。

#### FR5: 固定済みセクションを触らない

**説明**: `## Result format` と `## Escaping` はバイト単位で同一のまま保つ。引き継ぎ済みの番号付き consumer constraints はちょうど 5 個のまま、内容も変更しない。新しい文言は OWN-rules ラベル配下の箇条書きとして表現する。

#### FR6: `## Field values` の固定リテラルを保つ

**説明**: `## Field values` の `resume_conditions` 箇条書きに手を入れる場合も、既存テストが固定する次のリテラルを保持する。

- "NOT put through `detail`'s normalization"
- "survive as"
- "non-whitespace whenever `state` is `stopped`"
- "never empty and never whitespace-only"
- "empty for every other `state`"
- "carried in full inside `resume_conditions`"

#### FR7: 適合性マッチャを更新する

**説明**: `tests/test_batch_stop_contract.py` の `_assert_own_hardening_rules_stated` の期待文字列を新しい文言に更新する。既存の保証は維持する。

**ビジネスルール**:
- OWN_RULES_LABEL に固定されたままにする。
- 3 つの shape defenses を引き続き検査する。
- "carried-over consumer behaviour" のラベリングを引き続き検査する。

#### FR8: 否定証明のサンプルを更新する

**説明**: `FORGED_OWN_RULES_PARTIAL` を、新しい文言のもとでも「整形式だが不完全」なサンプルであり続けるように更新する。

**ビジネスルール**:
- `TestOwnHardeningRulesMatcherNegativeProof.test_forged_partial_rules_is_otherwise_well_formed` は引き続き成功する。
- `test_forged_partial_rules_missing_shape_checks_is_rejected` は引き続き失敗（＝拒否）する。その理由は shape checks の欠落であり、変更された制御コードポイントの文言ではない。

#### FR9: 改行例外の肯定ケースを追加する

**説明**: 改行を含む `resume_conditions` が拒否されないことをドキュメントが述べている、と主張する肯定テストを新規に追加する。否定証明を伴う。

**ビジネスルール**:
- 否定証明の偽造サンプルは変更前の文言そのもの（"`detail` and `resume_conditions` each reject a line terminator ... after decoding, in the same form as constraints 3 and 4 above"）を使い、新しいマッチャが矛盾した形を確かに拒否することを示す。

#### FR10: プラグイン version を引き上げる

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリを、同じ変更の中で同一の新しい patch version に引き上げる。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

該当なし。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

- NFR2: 新しいアサーションは生のドキュメントテキスト（`Path.read_text`）を読み、モジュール既存の `_normalize` / `_sections` ヘルパーを通す。これによりフェンス付きブロック内のリテラルも見え、プロース折り返しの位置に影響されない。
- NFR3: 新しいマッチャはそれぞれ否定証明と非空虚性ガードを備える。モジュールが定める作成規約に合わせる。
- NFR5: 変更後のドキュメントは内部整合を保つ。8 つの値のいずれについても、`## Field values` / `## Escaping` / `## Result format` / `## Consumer constraints` の記述が互いに矛盾しない。

### 5.5 互換性要件

- NFR1: テストは Python 標準ライブラリの `unittest` のみを使う（サードパーティ import を持たない）。test/README.md に従う。
- NFR4: 変更はドキュメントとテストのみ。ランタイムのスクリプト・フック・スキルの挙動は変えず、ドキュメントは周囲のプロースと同じ英語のままにする。

## 6. UI/UX要件

### 6.1 画面設計要件

該当なし。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

### 7.1 データモデル概要

該当なし。

### 7.2 データ項目

該当なし。

### 7.3 データ保持期間

該当なし。

## 8. 外部連携

### 8.1 連携システム

該当なし。

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- テストは Python 標準ライブラリの `unittest` のみを使う（NFR1）。
- 新しいアサーションはモジュール既存の `_normalize` / `_sections` ヘルパーを通す（NFR2）。
- 新しいマッチャは否定証明と非空虚性ガードを伴う（NFR3）。
- `## Result format` と `## Escaping` は編集しない（FR5、A5）。
- 引き継ぎ済みの番号付き consumer constraints はちょうど 5 個のまま（FR5、A6）。
- `em-workflow/references/batch-mode.md` と `em-workflow/skills/develop/SKILL.md` は編集不要（A7）。

### 9.2 ビジネス上の制約

- 変更はドキュメントとテストのみで、ランタイムの挙動を変えない（NFR4）。
- プラグイン配下を変更するため、同じ変更に version 引き上げを含める（FR10）。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/resume-conditions-newline-rejection/**`
- `test-docs/resume-conditions-newline-rejection/**`

`feature-docs/resume-conditions-newline-rejection/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/resume-conditions-newline-rejection/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/resume-conditions-newline-rejection/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/resume-conditions-newline-rejection/` ディレクトリを生成しないが、宣言された `test-docs/resume-conditions-newline-rejection/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `resume_conditions` の例外集合の境界（A1） | 中 | 例外は CR (U+000D) / LF (U+000A) / TAB (U+0009) の 3 つに限定し、それ以外（U+2028 / U+2029、C0 / C1 の端末制御域を含む）は拒否のまま保つ。可逆。 |
| 肯定ケースの実現形態（A4） | 中 | このリポジトリには当該規則の構造化結果エミッタもバリデータも無いため、肯定ケースはドキュメント文言の適合性テストとして実装する。可逆。 |
| `detail` 規則の提示形式の変更（A2） | 低 | 共有箇条書きの分割に伴う提示の変更のみとし、実質は変えない。可逆。 |
| 「cannot fire」前置きの扱い（A8） | 低 | 一律の主張を削除して解決する。発火条件は各規則の本文に置く。可逆。 |

### 10.2 ビジネスリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `## Field values` の `resume_conditions` 箇条書きと `## Consumer constraints` の最初の OWN-rules 箇条書きを順に読んで矛盾が生じない。Markdown の改行を含む `resume_conditions` の値が、合法かつ通常形の値である。
- [ ] AC2: OWN-rules セクションが、`resume_conditions` は CR / LF / TAB 以外の端末制御コードポイントのみをデコード後に拒否する、と述べている。
- [ ] AC3: OWN-rules セクションが、`detail` についてはデコード後の行終端文字または端末制御コードポイントの拒否を引き続き述べている。
- [ ] AC4: 「Each of the four cannot fire while `## Escaping` is honoured」の文が、直下の規則集合と矛盾する主張を述べていない。
- [ ] AC5: `python3 -m unittest discover -s tests` が、base revision に対する新規の失敗なしで成功する。
- [ ] AC6: `_assert_own_hardening_rules_stated` と `FORGED_OWN_RULES_PARTIAL` が新しい文言を反映し、`TestOwnHardeningRulesMatcherNegativeProof` の 3 テストがすべて引き続き成功する。
- [ ] AC7: 新規の肯定テストが、変更前のドキュメントテキストに対して失敗し、変更後のテキストに対して成功する。
- [ ] AC8: `TestEscapingAndResultFormatByteIdentical` と `test_five_carried_over_constraints_still_present_and_still_five` が、無変更のまま成功する。
- [ ] AC9: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` が同じ引き上げ後の em-workflow version を持つ。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 正常系: `## Consumer constraints` の OWN-rules テキストが `resume_conditions` の CR / LF / TAB 例外を述べている（新規マッチャ、実ドキュメントに対して検査）。対応要件: FR1 / FR2 / FR9。
- [ ] TS2 異常系: TS1 の否定証明。変更前の箇条書きテキストをそのまま偽造サンプルとして使い、TS1 のマッチャが拒否する。対応要件: FR9 / NFR3。
- [ ] TS3 境界値: TS1 の非空虚性。引き継ぎ済みの番号付き制約だけでは TS1 のマッチャを満たさない（OWN_RULES_LABEL に固定されたまま）。対応要件: FR9 / NFR3。
- [ ] TS4 回帰: `_assert_own_hardening_rules_stated` が更新後ドキュメントに対して成功し、3 つの shape defenses と "carried-over consumer behaviour" のラベリングを引き続き要求する。対応要件: FR3 / FR7。
- [ ] TS5 回帰: `FORGED_OWN_RULES_PARTIAL` が引き続き「それ以外は整形式」であり、shape checks の欠落によって引き続き拒否される。対応要件: FR8。
- [ ] TS6 回帰: `## Result format` と `## Escaping` のバイト同一性、番号付き制約が 5 個であること、`## Field values` の `resume_conditions` の固定（正規化非適用・存在規則・全文搬送）がすべて維持される。対応要件: FR5 / FR6 / NFR5。
- [ ] TS7 回帰: `plugin.json` の em-workflow version が marketplace エントリの version と等しく、base revision の値より大きい。対応要件: FR10。
- [ ] TS8 回帰: スイート全体が `python3 -m unittest discover -s tests` で標準ライブラリのみを使って動く。対応要件: NFR1 / NFR2 / NFR4。
- [ ] セキュリティ: 該当なし。
- [ ] パフォーマンス: 該当なし。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| SSOT | 単一の正とする情報源。ここでは `em-workflow/references/batch-terminal-line.md` |
| OWN-rules ラベル | `## Consumer constraints` 内の "em-workflow's OWN emitter obligations and rejection rules" というラベル |
| `detail` | `## Field values` において、CR / LF / TAB をエスケープ前に空白へ置換して正規化されるフィールド |
| `resume_conditions` | `state` が `stopped` のとき復旧手順を全文で載せるフィールド。CR / LF / TAB は `## Escaping` のエスケープとして残る |
| 引き継ぎ済み consumer constraints | `## Consumer constraints` にある 5 個の番号付き制約 |
| 否定証明 | 偽造サンプルをマッチャが確かに拒否することを示すテスト |
| 非空虚性ガード | マッチャが無条件に成功していないことを示すテスト |

## 14. 確認事項

### 14.1 確認済み事項

requirements-analyst が確定した前提。

- [x] A1 `resume_conditions` の例外集合: ちょうど CR (U+000D) / LF (U+000A) / TAB (U+0009) の 3 つ。旧規則が対象としていたそれ以外のコードポイント（U+2028 / U+2029、C0 / C1 の端末制御域を含む）は拒否のまま。根拠: タスク記述が CR / LF / TAB 以外の端末制御コードポイントのみを拒否と述べていること、この 3 つが `## Escaping` の専用短縮エスケープを持つ 3 文字かつ `detail` の正規化が除去する 3 文字と一致すること、および Codex 相談（2026-09-20）が `## Field values` のインデント保持の約束を理由に TAB の許可を独立に推奨したこと。影響度: 中。可逆。
- [x] A2 `detail` の拒否規則は実質的に変更なし。共有箇条書きの分割により提示だけが変わる。根拠: タスク記述が、`detail` の正規化は既に CR / LF / TAB を除去しているため拒否を維持してよいと述べていること。影響度: 低。可逆。
- [x] A3 em-workflow の version 引き上げは patch 増分。根拠: `.claude/rules/core-plugin-version-bump.md`（挙動の修正は patch、patch が既定の粒度）。影響度: 低。可逆。
- [x] A4 完了定義が求める「肯定ケース」は、実行可能なエミッタテストではなくドキュメント文言の適合性テスト。根拠: このリポジトリには当該規則の構造化結果エミッタもバリデータも無く、`batch-terminal-line.md` はプロースの SSOT、`tests/test_batch_stop_contract.py` はそのテキストに対して検査している。影響度: 中。可逆。
- [x] A5 `## Result format` と `## Escaping` は編集しない。根拠: `TestEscapingAndResultFormatByteIdentical` がバイト単位で固定しており、修正に必要ない。影響度: 低。可逆。
- [x] A6 引き継ぎ済みの番号付き consumer constraints はちょうど 5 個のまま。新しい文言はすべて OWN-rules ラベル配下の箇条書きとして表現する。根拠: `test_five_carried_over_constraints_still_present_and_still_five` が固定している。影響度: 低。可逆。
- [x] A7 `em-workflow/references/batch-mode.md` と `em-workflow/skills/develop/SKILL.md` は編集不要。根拠: batch-mode.md は `resume_conditions` の出現を持たず拒否規則を再掲していない。develop/SKILL.md は復旧手順が `resume_conditions` に全文で載ると述べるだけで、修正はそれを裏づけこそすれ矛盾しない。影響度: 低。可逆。
- [x] A8 「cannot fire」の前置きは、規則ごとに言い換えるのではなく一律の主張を削除して解決する。根拠: Codex 相談（2026-09-20）が削除を推奨した。発火条件は各規則自身の本文に属し、`## Escaping` との関係を前置きで重複させたことが矛盾を生んだ原因である。影響度: 低。可逆。

### 14.2 未確認・保留事項

なし。すべての機能要件・非機能要件のステータスは `ok` であり、`tbd` のものはない。

## 15. 参考資料

- `em-workflow/references/batch-terminal-line.md`: 修正対象の SSOT
- `tests/test_batch_stop_contract.py`: 文言の適合性テスト
- `.claude/rules/core-plugin-version-bump.md`: version 引き上げ規則
- `em-workflow/.claude-plugin/plugin.json`: em-workflow のプラグイン定義
- `.claude-plugin/marketplace.json`: マーケットプレイス定義
- test/README.md: テストが標準ライブラリ `unittest` のみを使う根拠
