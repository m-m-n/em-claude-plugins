---
title: "batch-structured-result-output"
created_date: 2026-09-20
status: draft
---

# batch-structured-result-output - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow のバッチ端末出力と、その外部コンシューマが黙って乖離している。コンシューマはバッチ実行で捕捉した stdout を YAML として解析し、8 キーのトップレベルマッピングを要求するようになった一方、em-workflow は今も `EM_WORKFLOW_TERMINAL:` 接頭辞付きの 4 フィールド `key=value` 行を出力している。コンシューマ側はマーカー行パーサを既に削除済みである。

### 1.2 目的

終端行を構造化 8 キー YAML の結果に置き換え、その結果を em-workflow の唯一の終端出力形状とし、旧形状に依存していた SSOT の記述とテストの表明をすべて記述し直す。これにより、バッチ実行の終端状態がコンシューマから再び機械可読になり、次にコンシューマの文書化されたドメインとの乖離が起きたときに、それが黙って進行するのではなく本リポジトリ側で可視になる。

### 1.3 スコープ

対象:

- `em-workflow/references/batch-terminal-line.md`（構造化結果の SSOT）
- `em-workflow/references/batch-mode.md`（「## Terminal line」「## Batch quiet output」「## Reporting」）
- `em-workflow/skills/develop/SKILL.md`（「## バッチ終端行」節および他 4 箇所の終端行引用）
- `em-workflow/references/implement-phase.md`（終端行引用 1 箇所）
- 旧形状を固定している Python テストモジュール群
- `em-workflow/.claude-plugin/plugin.json` とリポジトリルート `.claude-plugin/marketplace.json` の em-workflow バージョン

対象外:

- 非終端の `EM_WORKFLOW_PROGRESS:` マーカー行の形状（FR18 が要求する記述し直しを除く）
- `state` ドメイン・`step` ドメイン・`step` の優先規則
- 11 個の stop reason コードとその 11 個の stop point 束縛
- 他フィーチャーの `feature-docs/**` 配下に残る `EM_WORKFLOW_TERMINAL:` および 4 フィールド形状の記述（履歴記録であり、生きた契約ではない）
- em-review のバージョン

## 2. ビジネス要件

### 2.1 ビジネス目標

バッチ実行の終端状態を、外部コンシューマが解析できる構造化 8 キー YAML として出力する。旧終端行は完全に撤去し、構造化結果を唯一の終端出力形状にする。旧形状に依存していた SSOT の段落とテストの表明をすべて記述し直し、コンシューマの文書化されたドメインからの次の乖離が本リポジトリ側で可視になる状態にする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| 外部コンシューマ | バッチ実行で捕捉した stdout を YAML として解析し、8 キーのトップレベルマッピングを要求する |
| em-workflow の保守者 | コンシューマの文書化されたドメインとの乖離を、本リポジトリ側で検知する |

### 2.3 期待される効果

- バッチ実行の終端状態が、コンシューマから再び機械可読になる
- コンシューマの文書化されたドメインからの次の乖離が、黙って進行せず本リポジトリ側で可視になる

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 終端バッチターンが構造化結果を出力する | em-workflow | 高 |
| UC02 | コンシューマが捕捉した stdout を解析する | 外部コンシューマ | 高 |
| UC03 | 結果が存在しないことを異常終了として読む | 外部コンシューマ | 高 |

### 3.2 ユースケース詳細

#### UC01: 終端バッチターンが構造化結果を出力する

**アクター**: em-workflow

**事前条件**:

- バッチ実行が終端に到達している（`completed` / `stopped` / `phase_done` のいずれか）

**基本フロー**:

1. `state`・`step`・`reason` を既存のドメインと優先規則に従って決定する
2. `detail` に既存の正規化を適用する
3. `feature`・`branch`・`pr_url`・`resume_conditions` を各導出規則に従って決定する
4. 各値に文字単位のエスケープ規則を適用する
5. 8 キーを固定順で、各値を二重引用符付きスカラーとして、最終アシスタントメッセージに裸で出力する

**代替フロー**:

- クラッシュまたはターンの途中終了では構造化結果が出力されない

**事後条件**:

- 最終アシスタントメッセージ全体が、ちょうど 8 物理行の 1 つの YAML マッピングである

#### UC02: コンシューマが捕捉した stdout を解析する

**アクター**: 外部コンシューマ

**事前条件**:

- バッチ実行の stdout を捕捉している

**基本フロー**:

1. stdout を YAML として解析する
2. 8 キーのトップレベルマッピングを取得する
3. コンシューマ側の制約（`stopped`+`none` の拒否、`phase_done` の要件、`branch`/`pr_url` の文字制約、64 KiB 上限）を検査する

**事後条件**:

- 終端状態が機械可読な値として得られる

#### UC03: 結果が存在しないことを異常終了として読む

**アクター**: 外部コンシューマ

**事前条件**:

- 実行が終了しているが構造化結果が出力されていない

**基本フロー**:

1. 実行の末尾に結果が無いことを検出する
2. それを成功ではなく異常終了として読む

**事後条件**:

- 「結果なし = 異常終了」のシグナルが保たれている

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | 構造化結果の SSOT 所有 | `batch-terminal-line.md` が構造化結果の唯一の定義箇所になる | resolved |
| FR2 | 裸の 8 キーマッピングが最終メッセージ全体 | コードフェンス・散文・区切り・コメント・追加キーを伴わない | resolved |
| FR3 | 固定キー集合とキー順 | 8 キーを固定順で各 1 回、行頭に書く | resolved |
| FR4 | 全値が二重引用符付きスカラー | 空文字列も `""` と書く | resolved |
| FR5 | エスケープ規則 | 文字単位で適用し、生成したエスケープを再処理しない | resolved |
| FR6 | 8 物理行の不変条件 | 値の中に物理改行が現れないため常に 8 物理行 | resolved |
| FR7 | `detail` の正規化を維持しエスケープ | 正規化とエスケープは順序の決まった 2 段階 | resolved |
| FR8 | `resume_conditions` は detail 正規化しない | Markdown として改行・字下げ・行末空白を保つ | resolved |
| FR9 | `feature` の導出 | 確定した feature slug、未確定なら `""` | resolved |
| FR10 | `branch` の導出 | 本実行が存在確認または作成した統合ブランチ名、それ以外は `""` | resolved |
| FR11 | `pr_url` の導出 | 本実行の Step C が作成に成功した PR の URL、それ以外は `""` | resolved |
| FR12 | `resume_conditions` の出現規則 | `state` が `stopped` のときのみ非空白の Markdown | resolved |
| FR13 | `state`・`step` のドメイン不変 | ドメインと `step` の優先規則をすべて維持 | resolved |
| FR14 | コンシューマ由来の制約 | 組み合わせ禁止・文字制約・サイズ上限 | resolved |
| FR15 | `context_budget_reached` を never emitted として文書化 | ドメインに載せ、出力しないコードとして明示 | resolved |
| FR16 | 旧マーカー行の完全撤去 | 二重出力も互換期間も設けない | resolved |
| FR17 | 「## Reporting」の監査項目を値の中に完全収容 | 参照・件数による代替を認めない | resolved |
| FR18 | 接頭辞非衝突の段落の書き直し | 比較対象の終端接頭辞が消えたため | resolved |
| FR19 | 進捗マーカー行は不変 | FR18 が要求する書き直しを除き対象外 | resolved |
| FR20 | ポインタ文書の更新（リテラル非再掲） | SSOT を指し続け、リテラルを再掲しない | resolved |
| FR21 | プラグインバージョンの引き上げ | 2 つのマニフェストを同じ値にする | resolved |
| FR22 | テスト側の契約を同一変更で更新 | 旧形状を固定しているテストを陳腐化させない | resolved |

### 4.2 機能詳細

#### FR1: 構造化結果の SSOT 所有

**説明**: `em-workflow/references/batch-terminal-line.md` が、構造化結果の形式の唯一の所有者になる。所有する内容は、キー集合、キー順、引用とエスケープの規則、`state` / `step` / `reason` の値ドメイン、閉じた stop reason コード集合、および終端となる各 stop point から reason コードへの対応付けである。これは、同文書が現在所有している「接頭辞付き 4 フィールド行」の所有を置き換える。

#### FR2: 裸の 8 キーマッピングが最終メッセージ全体

**説明**: 終端バッチターンの最終アシスタントメッセージは、1 つの YAML マッピングを裸で出力したものである。コードフェンスなし、前後の散文なし、ドキュメント区切りなし、コメントなし、追加キーなし、前後に何も置かない。

#### FR3: 固定キー集合とキー順

**説明**: 次の 8 キーちょうどを、各 1 回、行頭に、この順で書く。

1. `state`
2. `step`
3. `reason`
4. `detail`
5. `feature`
6. `branch`
7. `pr_url`
8. `resume_conditions`

#### FR4: 全値が二重引用符付きスカラー

**説明**: すべての値を二重引用符付きの YAML スカラーとして出力する。空文字列も含め、空文字列は `""` と書く。

#### FR5: エスケープ規則

**説明**: ソース値に対して文字単位で適用し、生成したエスケープを再処理しない。

| 元の文字 | 出力 |
|----------|------|
| `\` | `\\` |
| `"` | `\"` |
| CR | `\r` |
| LF | `\n` |
| TAB | `\t` |

残る文字のうち U+0000-U+001F、U+007F-U+009F、U+2028、U+2029、U+FFFE、U+FFFF に含まれるものは 4 桁の `\uXXXX` にする。それ以外の有効な Unicode 文字はそのまま保つ。

#### FR6: 8 物理行の不変条件

**説明**: すべての値が二重引用符付きであるため、値の中の `:`、行頭の `-`、`#` は特別扱いを必要としない。値の中に物理改行が現れることはないため、ドキュメントは常にちょうど 8 物理行である。

#### FR7: `detail` の正規化を維持し、その後エスケープ

**説明**: `detail` は現在の SSOT が述べるとおりの正規化を維持する。CR / LF / TAB を単一のスペースに、スペースの連続を畳み、結果をトリムし、正規化後が空になる場合は固定の非空プレースホルダを代入する。正規化と YAML エスケープは別々の 2 段階であり、この順で適用する。

#### FR8: `resume_conditions` は detail 正規化しない

**説明**: `detail` の正規化は `resume_conditions` には適用しない。`resume_conditions` は Markdown であり、自身の改行・字下げ・行末空白を保つ。それらは引用符付きスカラーの中で `\n` などのエスケープとして生き残る。

#### FR9: `feature` の導出

**説明**: `feature` は確定した feature slug であり、slug が一度も確定していない場合は `""` である。タスク記述から推測してはならず、既存ブランチから推測してもならない。明示的に与えられた名前は Step 0 の中断時でも使用可能だが、`^[a-z0-9][a-z0-9-]*$` に一致する場合に限る。

#### FR10: `branch` の導出

**説明**: `branch` は、本実行がそのブランチの存在を確認したか、または作成した場合に限り `em-workflow/{feature}/integration` であり、それ以外は `""` である。Step 0 の git セットアップ中断と Step A の feature 解決中断も `""` に含まれる。名前を構成できることは、ブランチが存在することと同じではない。Step C がワークツリーを削除してブランチを残す場合、値は保持される。

#### FR11: `pr_url` の導出

**説明**: `pr_url` は、本実行の Step C が `gh pr create` で作成に成功した PR の裸の URL であり、それ以外は `""` である。PR 作成後に実行が停止した場合（作成後のクリーンアップ失敗、verify の上限到達実行など）も値は保持される。

#### FR12: `resume_conditions` の出現規則

**説明**: `resume_conditions` が非空白の Markdown になるのは `state` が `stopped` のときのみであり、`state` が `completed` または `phase_done` のときは `""` である。

#### FR13: `state` と `step` のドメイン不変

**説明**: `state` ドメイン（`completed` / `stopped` / `phase_done`）、`step` ドメイン（`workflow.yaml` の 7 つの step id と `no-step` センチネル）、および `step` の既存の優先規則（実行済み step の一般規則、`no-step` センチネル規則、`state=completed` のとき `retrospect` とする規則、Step C の結果の非対称性）はいずれも変更しない。

#### FR14: コンシューマ由来の制約

**ビジネスルール**:

- `state: "stopped"` と `reason: "none"` の組み合わせは拒否される
- `state: "phase_done"` は `reason: "none"` かつ `resume_conditions: ""` を要求する
- `branch` と `pr_url` は行終端文字および端末制御コードポイントを含んではならない（エスケープは救済にならない。コンシューマは解析後の値を拒否する）
- ドキュメント全体は UTF-8 エンコードで 64 KiB 以下

#### FR15: `context_budget_reached` を never emitted として文書化

**説明**: `context_budget_reached` を SSOT の文書化された `reason` 値ドメインに載せ、em-workflow が決して出力しないコード（コンシューマ側の予約）として明示する。Stop point のカバレッジ表は 11 行と 11 個の束縛コードを維持する。「すべてのコードがちょうど 1 つの stop point を持つ」という対称性からの逸脱は、このコード 1 つだけを対象とする意図的かつ名前付きの例外として明記する。

#### FR16: 旧マーカー行の完全撤去

**説明**: `EM_WORKFLOW_TERMINAL:` 接頭辞付きの 4 フィールド行を完全に撤去する。構造化 YAML 結果が em-workflow の唯一の終端出力形状であり、二重出力も互換期間も設けない。

#### FR17: 「## Reporting」の監査項目を値の中に完全収容

**説明**: `references/batch-mode.md` の「## Reporting」が要求する監査項目はすべて、文字列値の中に完全な形で収容する。監査項目と引き継ぎガイダンスは `detail` に、停止からの復帰ガイダンスは `resume_conditions` に置く。参照による存在（件数のみ、ポインタのみ）は「## Reporting」を満たさない。新しい集約レポート成果物は書かない。batch-mode.md の Audit-item source map が、要求される各項目を既に永続化されている場所へ既に束縛しているためである。

#### FR18: 接頭辞非衝突の段落の書き直し

**説明**: `references/batch-mode.md` の「## Batch quiet output」にある、接頭辞の非衝突を正当化する段落を書き直す。終端接頭辞が無くなったことで、`EM_WORKFLOW_PROGRESS:` 接頭辞を比較すべき終端接頭辞が存在しなくなるためである。書き直した段落は、コンシューマが非終端のマーカー行を終端の構造化結果と取り違えないことを依然として成立させ、終端契約の「結果なし = 異常終了」のシグナルを依然として保たなければならない。

#### FR19: 進捗マーカー行は不変

**説明**: 非終端の `EM_WORKFLOW_PROGRESS:` マーカー行は現在の 2 フィールド（`phase`、`point`）形状を維持し、FR18 が要求する書き直しを除いて本変更の対象外である。

#### FR20: ポインタ文書の更新（リテラル非再掲）

**説明**: `references/batch-mode.md` の「## Terminal line」節、`skills/develop/SKILL.md` の「## バッチ終端行」節とその他 4 箇所の終端行引用、`references/implement-phase.md` の 1 箇所の引用を、構造化結果に合わせて更新する。これらは SSOT を名指しし続け、SSOT のリテラルを引き続き一切再掲しない（`state=` の値リテラル、reason コード、`no-step` センチネル、フィールド名トークン集合のいずれも）。既存の D2 ガードがまさにそれらの不在を表明しているためである。

#### FR21: プラグインバージョンの引き上げ

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、同一変更の中で `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリのバージョンを、同じ値に引き上げる。いずれも現在 `0.1.82` である。em-review エントリ（`0.5.10`）は変更しない。

#### FR22: テスト側の契約を同一変更で更新

**説明**: 旧形状を固定しているテストモジュールはすべて、陳腐化させずに同一変更の中で更新する。これはリポジトリの既存の慣行に従う。

## 5. 非機能要件

### 5.1 非機能要件一覧

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | SSOT 規律の維持 | `batch-terminal-line.md` が唯一の定義箇所であり続ける。`batch-mode.md`、`skills/develop/SKILL.md`、`implement-phase.md` はそれを引用し、リテラルを再掲しない。既存のファイル全体の不在ガード（`tests/test_batch_quiet_output_discipline.py`、`tests/test_batch_quiet_output_phase_wiring.py`、`tests/test_batch_stop_contract_skill_wiring.py`）は、新しいリテラルへ向け直した後も green を保つ |
| NFR2 | 外部ツール不要・LLM が書ける | 結果の出力に外部ツールを要しない。モデルが最終アシスタントメッセージに書き込むテキストである。したがってエスケープ規則は YAML シリアライザライブラリなしに文字単位で適用でき、LLM が決定的に追える形で SSOT に記述されていなければならない |
| NFR3 | 実パーサによる適合検証 | 引用規則を PyYAML に対して 14 の敵対的ケース（空文字列、`null`、`true`、`0`、`: value`、`- item`、`# title`、`x: y # z`、埋め込み LF / CRLF / TAB、埋め込みの引用符とバックスラッシュ、非 BMP 絵文字、C0/C1/行区切り/非文字コードポイントの文字列）で検証する。各ケースが 8 つの文字列値を持つ単一マッピングへ往復すること |
| NFR4 | テスト記述の慣行 | リポジトリの既存慣行に従う。リテラルが陳腐化する箇所では固定リテラルより永続的な不変条件を用いる。新しいマッチャごとに否定証明と非空虚ガードを 1 つずつ置く。保持文言に対する純粋な回帰ガードは免除。テストモジュールは Python 標準ライブラリ（`os`、`re`、`unittest`、`pathlib`）のみを import し、`python3 -m unittest discover -s tests` で発見される |
| NFR5 | 機密境界を新フィールドへ拡張 | 「## Responsibility boundary」の規則（結果はパス以上の機密情報を運ばない。内容が em-workflow のプロセス境界の外へ中継されるため）は、`detail` 単独ではなく `detail`、`resume_conditions`、`branch`、`pr_url` を統べる |
| NFR6 | 不在が異常終了のシグナルであり続ける | クラッシュまたは途中終了したターンは構造化結果を生成しない。実行の末尾に結果が無いのを見たコンシューマは、その不在を成功ではなく異常終了として読む。この性質は FR16 と FR18 を経ても保たれなければならない |
| NFR7 | 同梱ファイルへの配慮 | `.claude/rules/core-plugin-structure.md` に従い、`em-workflow/` 配下のすべてがユーザーのプラグインキャッシュへコピーされる。本変更はそのルート配下に実行時依存も生成成果物も追加しない |

### 5.2 パフォーマンス要件

該当なし。ただし FR14 によりドキュメント全体は UTF-8 エンコードで 64 KiB 以下である。

### 5.3 セキュリティ要件

- データ保護: NFR5（機密境界を `detail`、`resume_conditions`、`branch`、`pr_url` へ拡張）
- 入力検証: FR14（`branch` と `pr_url` は行終端文字と端末制御コードポイントを含まない）

### 5.4 可用性要件

該当なし。NFR6 により、結果の不在が異常終了のシグナルとして機能する。

### 5.5 保守性要件

- ドキュメント: NFR1（SSOT 規律）、FR20（ポインタ文書はリテラルを再掲しない）
- テスト: NFR3（実パーサによる適合検証）、NFR4（テスト記述の慣行）、FR22（テスト側契約の同時更新）

### 5.6 互換性要件

FR16 により互換期間を設けない。構造化 YAML 結果が唯一の終端出力形状である。NFR7 により、`em-workflow/` 配下に実行時依存も生成成果物も追加しない。

## 6. UI/UX要件

対象外。本変更は 3 つの reference SSOT Markdown 文書、1 つの skill Markdown 文書、10 個の Python テストモジュール、2 つの JSON バージョンマニフェストに閉じており、ユーザー向け UI もレンダリング面も存在しない。

## 7. データ要件

### 7.1 データモデル概要

構造化結果は、8 つの文字列値を持つ 1 つの YAML トップレベルマッピングである。永続化されるデータストアは持たない。

### 7.2 データ項目

| 項目名 | 型 | 必須 | 説明 |
|--------|-----|------|------|
| `state` | 二重引用符付き文字列 | ○ | `completed` / `stopped` / `phase_done`（FR13） |
| `step` | 二重引用符付き文字列 | ○ | `workflow.yaml` の 7 つの step id、または `no-step` センチネル（FR13） |
| `reason` | 二重引用符付き文字列 | ○ | 文書化された 12 値のドメイン。うち `context_budget_reached` は出力されない（FR15） |
| `detail` | 二重引用符付き文字列 | ○ | 既存の正規化を適用した後にエスケープ（FR7）。「## Reporting」の監査項目と引き継ぎガイダンスを完全収容（FR17） |
| `feature` | 二重引用符付き文字列 | ○ | 確定した feature slug、または `""`（FR9） |
| `branch` | 二重引用符付き文字列 | ○ | 本実行が確認または作成した統合ブランチ名、または `""`（FR10） |
| `pr_url` | 二重引用符付き文字列 | ○ | 本実行の Step C が作成に成功した PR の裸の URL、または `""`（FR11） |
| `resume_conditions` | 二重引用符付き文字列 | ○ | `state` が `stopped` のときのみ非空白の Markdown、他は `""`（FR12）。detail 正規化は適用しない（FR8）。停止からの復帰ガイダンスを完全収容（FR17） |

### 7.3 データ保持期間

該当なし。構造化結果は最終アシスタントメッセージとして出力されるのみで、本変更は新しい集約レポート成果物を書かない（FR17）。

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| 外部コンシューマ | バッチ実行で捕捉した stdout を YAML として解析 | 8 キーのトップレベルマッピング |

### 8.2 API仕様要件

連携の仕様は構造化結果の形状そのものである。FR2-FR6 が形状を、FR14 がコンシューマ側の受け入れ制約を定める。

## 9. 制約条件

### 9.1 技術的制約

- 出力に外部ツールを使えない。モデルが最終アシスタントメッセージに書くテキストである（NFR2）
- エスケープ規則は YAML シリアライザライブラリなしに文字単位で適用できなければならない（NFR2、FR5）
- テストモジュールは Python 標準ライブラリのみを import し、`python3 -m unittest discover -s tests` で発見される（NFR4）
- `em-workflow/` 配下に実行時依存も生成成果物も追加しない（NFR7）

### 9.2 ビジネス上の制約

- 二重出力も互換期間も設けない（FR16）
- ポインタ文書は SSOT のリテラルを再掲しない（FR20、NFR1）
- 同一変更で 2 つのマニフェストのバージョンを同じ値に引き上げる（FR21）
- 旧形状を固定しているテストは同一変更で更新する（FR22）

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:

- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

要件分析で特定された技術的課題はない。

### 10.2 ビジネスリスク

要件分析で特定されたビジネスリスクはない。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: 終端バッチターンの最終アシスタントメッセージが、strict な YAML ロードでちょうど 1 つのマッピングとして解析され、FR3 の 8 キーちょうどがその順で各 1 回現れ、すべての値が文字列である
- [ ] AC-2: 出力ドキュメントが、CR / LF / CRLF / TAB を含むソース値を含めてあらゆる入力に対してちょうど 8 物理行である
- [ ] AC-3: NFR3 の 14 の敵対的ケースがすべて PyYAML を通じて 8 つの文字列値を持つ単一マッピングへ往復する
- [ ] AC-4: `detail` の正規化（FR7）がエスケープの前に適用され、`resume_conditions` には適用されない（FR8）。改行を含む `detail` ソースが `\n` エスケープを生まないこと、改行を含む `resume_conditions` ソースが `\n` エスケープを生むことで示す
- [ ] AC-5: `feature`、`branch`、`pr_url`、`resume_conditions` が、Step 0 の git セットアップ中断、Step A の feature 解決中断、ワークツリー削除後のブランチ保持ケース、PR 作成後に停止したケース、verify の上限到達実行を含む各所で FR9-FR12 に従う
- [ ] AC-6: コンシューマの制約（FR14）が成立する。`stopped`+`none` が無いこと、`phase_done` が `reason: "none"` と `resume_conditions: ""` を含意すること、`branch` と `pr_url` が行終端文字と端末制御コードポイントを持たないこと、ドキュメントが UTF-8 で 64 KiB 以下であること
- [ ] AC-7: リテラル `EM_WORKFLOW_TERMINAL:` が `em-workflow/` 配下のどこにも出現しない。`tests/test_batch_stop_contract.py` の既存の AC-7 sweep を「`batch-terminal-line.md` のフェンス済みブロック内のみ」から「どこにも存在しない」へ反転する
- [ ] AC-8: SSOT が 12 個の `reason` 値を文書化し、`context_budget_reached` を em-workflow が決して出力しないものとして明示し、Stop point カバレッジ表を 11 行・同じ 11 コードの束縛に保ち、名前付き例外を明示的に述べている（FR15）
- [ ] AC-9: `batch-mode.md` の書き直した「## Batch quiet output」段落（FR18）が `EM_WORKFLOW_PROGRESS:` を名指しし、終端接頭辞を一切名指しせずに構造化結果の形状に対する非混同性を成立させ、NFR6 の不在シグナルを保っている
- [ ] AC-10: 「## Reporting」が要求する各監査項目が `detail` または `resume_conditions` の中に完全な形で現れる（FR17）。いずれの項目もポインタのみ・件数のみの提示になっていない。本変更は新しい集約レポート成果物を書かない
- [ ] AC-11: `batch-mode.md`、`skills/develop/SKILL.md`、`implement-phase.md` が SSOT を名指しし、そのリテラルを再掲しない（FR20、NFR1）。向け直した不在ガードが通る
- [ ] AC-12: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow エントリが同じ、引き上げ後のバージョンを持つ（FR21）
- [ ] AC-13: `python3 -m unittest discover -s tests` が新規失敗なしで通り、新しいマッチャがそれぞれ否定証明と非空虚ガードを備えている（NFR4）

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1（AC-1, AC-2 / 正常系）: 各 `state` 値について代表的な終端結果を strict な YAML ロードで解析し、単一マッピング・固定順の 8 キー・全値が文字列・ちょうど 8 物理行を表明する
- [ ] TS2（AC-3 / 境界値）: 14 の敵対的ソース値を文書化されたエスケープ規則と PyYAML に通し、往復後の値がソース値とバイト単位で等しいことを表明する
- [ ] TS3（AC-4 / 正常系）: CR/LF/TAB とスペースの連続を含む `detail` ソース、改行・字下げ・行末空白を含む `resume_conditions` ソース。前者に正規化→エスケープ、後者にエスケープのみが適用されることを表明する
- [ ] TS4（AC-5 / 正常系・異常系）: 導出箇所を表駆動で網羅する。名前が与えられない Step 0 中断、slug に適合する名前が与えられた Step 0 中断、適合しない名前が与えられた Step 0 中断、Step A 中断、ブランチ作成、ブランチ存在確認、ワークツリー削除後の Step C ブランチ保持、`--pr` 成功、`--pr` 成功後のクリーンアップ停止、verify 上限到達実行
- [ ] TS5（AC-6 / 異常系・境界値）: `stopped`+`none` と、非空の `resume_conditions` を伴う `phase_done` の拒否経路の表明。解析後の `branch` / `pr_url` に対する制御文字・行終端文字の拒否。64 KiB の境界ケース
- [ ] TS6（AC-7 / セキュリティ規律）: `em-workflow/` を `os.walk` し、接頭辞リテラルが全ファイルから不在であることを表明する（手動保守の許可リストは持たない）。既存の非空虚ガードは維持する
- [ ] TS7（AC-8 / 正常系・否定証明）: `reason` 値ドメインとカバレッジ表を構造的に抽出し、12 の文書化値、11 のカバレッジ行、11 の束縛コード、`context_budget_reached` がカバレッジ表に不在でドメインには never-emitted として存在すること、名前付き例外の文が存在することを表明する。否定証明として、12 個目のコードをカバレッジ行として加えた偽造ドメインが拒否されること
- [ ] TS8（AC-9, AC-11 / 正常系・否定証明）: `batch-mode.md`、`skills/develop/SKILL.md`、`implement-phase.md` に対する向け直した不在ガードと、書き直した非衝突段落に対する肯定マッチャ（それ自身の否定証明と非空虚ガードを伴う）
- [ ] TS9（AC-10 / 正常系・否定証明）: 「## Reporting」の各監査項目が、割り当てられた値の中に完全な形で存在することを表明する。項目の代わりにポインタまたは件数を運ぶ偽造サンプルが拒否されること。新しい集約レポートのパスが write set に入らないことを表明する
- [ ] TS10（AC-12 / 正常系）: 両マニフェストを読み、em-workflow のバージョンが等しく `0.1.82` より厳密に大きいこと、em-review のバージョンが変わっていないことを表明する
- [ ] TS11（AC-13 / 回帰）: スイート全体の `python3 -m unittest discover -s tests`、および `.claude/rules/hook-tests.md` に従う無回帰チェックとしての `python3 em-workflow/hooks/tests/run-destructive-guard.py`（本変更の影響外）
- [ ] TS12（AC-1, AC-6 / 手動）: 実際の `--batch` 実行と `--batch --once` 実行を起動して stdout を捕捉し、コンシューマのパーサが結果を受け入れることを確認する。本プロジェクトに自動 E2E ハーネスは存在しない

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 構造化結果 | 終端バッチターンの最終アシスタントメッセージとして裸で出力される、8 キーの YAML トップレベルマッピング |
| SSOT | 単一の定義箇所。本フィーチャーでは `em-workflow/references/batch-terminal-line.md` |
| コンシューマ | バッチ実行で捕捉した stdout を YAML として解析する外部の利用者 |
| 終端行 | 撤去対象の `EM_WORKFLOW_TERMINAL:` 接頭辞付き 4 フィールド `key=value` 行 |
| 進捗マーカー行 | 非終端の `EM_WORKFLOW_PROGRESS:` マーカー行（`phase`、`point` の 2 フィールド） |
| `no-step` センチネル | `step` ドメインが `workflow.yaml` の 7 つの step id に加えて持つ値 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 終端出力形状: 構造化 8 キー YAML が唯一の形状であり、旧マーカー行は完全撤去。二重出力も互換期間もなし
- [x] SSOT の所有範囲: キー集合・キー順・引用とエスケープ規則・値ドメイン・stop reason コード集合・stop point との対応付け
- [x] `detail` の正規化は維持し、`resume_conditions` には適用しない
- [x] `state` / `step` のドメインと `step` の優先規則は変更しない
- [x] 11 個の stop reason コードと 11 個の stop point 束縛は変更せず、`context_budget_reached` はカバレッジ表の外に never-emitted として文書化する
- [x] `EM_WORKFLOW_PROGRESS:` マーカー行の形状は対象外（FR18 の記述し直しを除く）
- [x] 「## Reporting」の監査項目は値の中に完全収容し、新しい集約レポート成果物は作らない
- [x] バージョンは 2 つのマニフェストで同じ値に引き上げ、em-review は触らない
- [x] 旧形状を固定しているテストは同一変更で更新する

### 14.2 未確認・保留事項

なし。すべての機能要件が resolved である。

### 14.3 要件分析時の前提

| ID | 前提 | 可逆 |
|----|------|------|
| A1 | SSOT 文書は既存パス `em-workflow/references/batch-terminal-line.md` を維持し、形状変更に伴うファイル名変更は行わない | はい |
| A2 | 同文書の 7 つの固定レベル 2 見出しは、新しい形状が要求するとおりに改名・追加してよい（特に「Line format」）。`tests/test_batch_stop_contract.py` の `CONTRACT_HEADINGS` は陳腐化させず同一変更で更新する | はい |
| A3 | 他フィーチャーの `feature-docs/**` 成果物に含まれる `EM_WORKFLOW_TERMINAL:` と 4 フィールド形状の出現は、生きた契約ではなくフィーチャーごとの履歴記録であり、書き換えない | はい |
| A4 | 既存の 11 個の stop reason コードと 11 個の stop point 束縛は変更しない。`context_budget_reached` はカバレッジ表の外に文書化する | はい |
| A5 | `state` と `step` のドメイン、および `step` のすべての優先規則は変更しない。既存の回帰ガードは無修正のまま green を保つ | はい |
| A6 | バージョンは両マニフェストとも `0.1.82` からの patch 引き上げとする。旧行の撤去を互換性の破壊と判断する場合は minor または major の引き上げも同様に許容される。ルールが要求するのは 2 つのマニフェストの一致のみである | はい |
| A7 | 本プロジェクトに E2E 基盤は存在しない。検証は Python `unittest` スイートと `--batch` 実行の手動観察である | はい |
| A8 | プロジェクトルートに LICENSE ファイルが無いため、`project.license` は推測せず unknown として記録する | はい |

## 15. 参考資料

- `em-workflow/references/batch-terminal-line.md`: 構造化結果の SSOT
- `em-workflow/references/batch-mode.md`: 「## Terminal line」「## Batch quiet output」「## Reporting」「## Responsibility boundary」「Audit-item source map」
- `em-workflow/skills/develop/SKILL.md`: 「## バッチ終端行」節と他 4 箇所の終端行引用
- `em-workflow/references/implement-phase.md`: 終端行引用 1 箇所
- `tests/test_batch_stop_contract.py`: `CONTRACT_HEADINGS`、AC-7 sweep
- `tests/test_batch_quiet_output_discipline.py`: 不在ガード
- `tests/test_batch_quiet_output_phase_wiring.py`: 不在ガード
- `tests/test_batch_stop_contract_skill_wiring.py`: 不在ガード
- `em-workflow/.claude-plugin/plugin.json`: em-workflow バージョン（現在 `0.1.82`）
- `.claude-plugin/marketplace.json`: em-workflow エントリのバージョン（現在 `0.1.82`）、em-review エントリ（`0.5.10`）
- `.claude/rules/core-plugin-version-bump.md`: バージョン引き上げ規則
- `.claude/rules/core-plugin-structure.md`: 同梱ファイルの範囲
- `.claude/rules/hook-tests.md`: フックテストの実行規則
