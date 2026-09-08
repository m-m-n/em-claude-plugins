---
title: "destructive-guard-var-resolution"
created_date: 2026-09-01
status: draft
---

# destructive-guard-var-resolution - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow の destructive-guard PreToolUse フックには誤検知のクラスがある。リテラルなパスをシェル変数に代入し、その変数経由で削除するコマンドは、リテラル値が SAFE_DELETE の内側にあることが明らかな場合でも、解決不能（ルール rm-unresolvable、判定 ask）と判定される。

claude-batch では ask が deny に降格されるため、この誤検知 1 件ごとに、誰も解除できないまま無人実行が停止する。

### 1.2 目的

- 上記の誤検知クラスを取り除く。
- 無人実行を止めない。
- 検知力を落とさない。変数を解決することで、フックが見る実際の対象は増えることはあっても減ってはならない。

### 1.3 スコープ

対象は次の 4 ファイル。

| パス | 変更内容 |
|------|----------|
| `em-workflow/hooks/destructive-guard.py` | 変数解決の実装 |
| `em-workflow/hooks/tests/destructive-guard-cases.json` | 新挙動のケース追加 |
| `em-workflow/.claude-plugin/plugin.json` | version 更新 |
| `.claude-plugin/marketplace.json` | version 更新 |

対象外（FR5 / FR6 / FR7 / NFR6 として明示）:

- 連鎖参照（解決済み変数から値を組み立てる形）
- `export VAR=value`
- コマンド接頭辞の代入（`VAR=/tmp/x rm -rf "$VAR"`）
- 同一コマンド文字列内で 2 回以上代入された変数
- ネストレベルをまたぐ代入と参照
- SAFE_DELETE / SELF_CONFIG / TRANSCRIPT / DYNAMIC の各パターン定義そのものの再定義

## 2. ビジネス要件

### 2.1 ビジネス目標

- em-workflow の destructive-guard PreToolUse フックにおける誤検知クラスの除去。リテラルパスをシェル変数に代入し、その変数経由で削除するコマンドは、現状ルール rm-unresolvable により解決不能（ask）と判定される。リテラル値が明らかに SAFE_DELETE の内側にある場合でも同様である。
- 無人実行を止めないこと。claude-batch では ask が deny に降格されるため、この誤検知 1 件ごとにバッチ実行が停止し、誰も解除できない。
- その過程で検知力を弱めないこと。変数の解決は、フックが見る実際の対象を増やす方向にのみ働き、減らしてはならない。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| destructive-guard フック配下で動くエージェント | 変数経由の削除コマンドを実行し、現状は誤検知で止められている |
| claude-batch による無人実行 | ask が deny に降格されるため、誤検知がそのまま走行停止になる |

### 2.3 期待される効果

- リテラル代入 + 変数経由削除という形の誤検知が解消する。
- 無人実行が誤検知で停止しなくなる。
- 解決された値が実際の対象として全ての対象パス判定に流れるため、検知対象はむしろ増える。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 変数経由の対象パスを解決して判定する | destructive-guard フック | 高 |
| UC02 | 解決できない形をこれまでどおりの判定に留める | destructive-guard フック | 高 |

### 3.2 ユースケース詳細

#### UC01: 変数経由の対象パスを解決して判定する

**アクター**: destructive-guard フック

**事前条件**:
- 判定対象のコマンド文字列を受け取っている。

**基本フロー**:
1. コマンド文字列から `VAR=value` の平明な代入文（右辺が単一のリテラルトークン）を集め、名前から値への解決マップを作る（FR1）。
2. 対象パス判定の前に、各対象トークンの `$VAR` / `${VAR}` 参照をマップの値で置換する（FR2）。
3. 完全に解決されたトークンは、そのリテラルパスがコマンドに直接書かれていた場合と同じに判定する（FR2）。
4. 解決された値は、`check_rm` の rm-root 経路・SAFE_DELETE / rm-recursive 経路、および `check_self_modification` が SELF_CONFIG（self-modification）と TRANSCRIPT（transcript-write）に対して検査する `write_targets` 由来の候補を含む、全ての対象パス判定に流れる（FR3）。

**代替フロー**:
- 置換後もなお動的構成（グロブ `*` `?` `[`、コマンド置換 `$(` およびバッククォート、マップにない変数参照）を含むトークンは解決しない（FR2）。
- 解決されたリテラルパスが再帰削除下で SAFE_DELETE の外にある場合は、リテラル表記と同じ deny（ルール `rm-recursive`）となり、理由には解決後のパスから組み立てた `deletion_alternative(target)` の代替コマンドを含める（FR4）。

**事後条件**:
- 解決可能な形は、リテラル表記と同じ判定になる。

#### UC02: 解決できない形をこれまでどおりの判定に留める

**アクター**: destructive-guard フック

**事前条件**:
- 判定対象のコマンド文字列を受け取っている。

**基本フロー**:
1. 平明・単段・リテラルの `VAR=value` 形以外は解決しない（FR5）。
2. 同一コマンド文字列内で 2 回以上代入された変数は解決マップから完全に除外する（FR6）。
3. 代入と参照が同じネストレベルにない場合は解決しない（FR7）。
4. 上記に該当する参照は、これまでどおり ask（ルール rm-unresolvable）を維持する。

**代替フロー**:
- 再代入により解決不能となった場合、判定理由に「2 つの値を別々の変数に代入すればコマンドは解決可能になる」旨を記載し、呼び出し元エージェントが書き換えて再試行できるようにする（FR6）。

**事後条件**:
- 変更前の判定が維持される。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | コマンド文字列からの平明な代入の収集 | `VAR=value` 形の代入から解決マップを作る | 高 |
| FR2 | 解決値の対象トークンへの適用 | `$VAR` / `${VAR}` を置換し、完全解決したものだけをリテラル扱いにする | 高 |
| FR3 | 全ての対象パス判定への適用 | `check_rm` と `check_self_modification` の双方に解決値を流す | 高 |
| FR4 | SAFE_DELETE 外に解決されたパスの判定 | リテラル表記と同じ deny（rm-recursive）と代替コマンド提示 | 高 |
| FR5 | 対象とする代入形式 | 平明・単段・リテラルのみ。連鎖参照 / `export` / コマンド接頭辞は対象外 | 高 |
| FR6 | 再代入された変数の除外と書き換えヒント | 除外して ask を維持し、変数分割のヒントを理由に載せる | 高 |
| FR7 | 同一ネストレベルのみのスコープ | ネストをまたぐ代入と参照は解決しない | 高 |
| FR8 | プロジェクトルールに沿ったテストケース追加 | `[expected_verdict, label, command]` の 3 要素形式で追加 | 高 |
| FR9 | プラグイン version の更新 | 0.1.56 -> 0.1.57 を 2 ファイルで一致させる | 高 |

**ID 対応表**（要件分析時の表記と本書・SPEC.md の表記の対応。順序と 1 対 1 対応を保持）:

| 本書・SPEC.md | 要件分析 | | 本書・SPEC.md | 要件分析 |
|---|---|---|---|---|
| FR1 | FR-1 | | NFR1 | NFR-1 |
| FR2 | FR-2 | | NFR2 | NFR-2 |
| FR3 | FR-3 | | NFR3 | NFR-3 |
| FR4 | FR-4 | | NFR4 | NFR-4 |
| FR5 | FR-5 | | NFR5 | NFR-5 |
| FR6 | FR-6 | | NFR6 | NFR-6 |
| FR7 | FR-7 | | | |
| FR8 | FR-8 | | | |
| FR9 | FR-9 | | | |

### 4.2 機能詳細

#### FR1: コマンド文字列からの平明な代入の収集

**説明**: フックは、判定対象のコマンド文字列から、右辺が単一のリテラルトークンである平明な `VAR=value` 形の独立した代入文をすべて収集し、名前から値への解決マップを構築する。

**入力**:
- コマンド文字列: string - フックが判定対象として受け取ったコマンド

**出力**:
- 解決マップ: 変数名 -> リテラル値 の対応

**ビジネスルール**:
- 収集対象は独立した代入文に限る。

#### FR2: 解決値の対象トークンへの適用

**説明**: 対象パス判定が走る前に、各対象トークンの `$VAR` および `${VAR}` 参照をマップされたリテラル値で置換する。この置換によって完全に解決されたトークンは、そのリテラルパスがコマンドに書かれていた場合と同じに判定する。置換後もなお動的構成を含むトークンは解決せず、現行の挙動を維持する。

**入力**:
- 対象トークン: string
- 解決マップ: 変数名 -> リテラル値

**出力**:
- 解決済みリテラルパス、または未解決のままのトークン

**処理フロー**:
```mermaid
flowchart TD
    A[対象トークン] --> B[$VAR / ${VAR} をマップ値で置換]
    B --> C{置換後に動的構成が残るか}
    C -->|グロブ * ? [ / コマンド置換 $( ` / 未マップ変数| E[解決しない: 現行の挙動を維持]
    C -->|残らない| D[リテラルパスとして判定]
```

**ビジネスルール**:
- 動的構成とは、グロブ（`*`、`?`、`[`）、コマンド置換（`$(`、バッククォート）、マップにない変数参照を指す。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 解決不能 | 置換後も動的構成が残る | 変更前の判定を維持する |

#### FR3: 全ての対象パス判定への適用

**説明**: 解決された値は `check_rm` だけでなく、対象パスを検査するすべての判定に流れる。対象は、`check_rm` の rm-root 経路および SAFE_DELETE / rm-recursive 経路と、`check_self_modification` が SELF_CONFIG（self-modification）および TRANSCRIPT（transcript-write）に対して検査する `write_targets` 由来の候補である。

**ビジネスルール**:
- ゲート `create-spec` の質問 `requirement.resolution-scope` に対する選択 `all_target_checks` による決定。

#### FR4: SAFE_DELETE 外に解決されたパスの判定

**説明**: 解決されたリテラルパスが再帰削除下で SAFE_DELETE の外にある場合、判定はリテラル表記が今日生成するのと同じ deny（ルール `rm-recursive`）であり、その理由には解決後のパスから組み立てた `deletion_alternative(target)` の置き換えコマンドを含める。

**ビジネスルール**:
- 質問 `requirement.resolved-unsafe-verdict` に対する選択 `deny_as_literal` による決定。

#### FR5: 対象とする代入形式

**説明**: 解決するのは平明・単段・リテラルの `VAR=value` 形のみ。次は対象外とし、解決不能のままとする。

- 既に解決済みの変数から値を組み立てる連鎖参照
- `export VAR=value`
- コマンド接頭辞の代入（`VAR=/tmp/x rm -rf "$VAR"`）

**ビジネスルール**:
- コマンド接頭辞の代入は、シェルのセマンティクス上、同じコマンド自身の語の展開に影響しないため、決して解決してはならない。
- 質問 `requirement.assignment-forms` に対する選択 `plain_only` による決定。

#### FR6: 再代入された変数の除外と書き換えヒント

**説明**: 同一コマンド文字列内のどこかで 2 回以上代入された変数は、解決マップから完全に除外する。その変数への参照は解決不能のままとなり、今日どおりの ask（ルール rm-unresolvable）を維持する。

**ビジネスルール**:
- その判定の理由文には、2 つの値を別々の変数に代入すればコマンドが解決可能になる旨を記載し、呼び出し元エージェントが書き換えて再試行できるようにする。
- 質問 `requirement.reassignment` に対する選択 `unresolvable_on_conflict`（自由記述: 「変数を分ける旨のコンテキスト注入」）による決定。

#### FR7: 同一ネストレベルのみのスコープ

**説明**: 代入が参照を解決するのは、両者が同じネストレベルにあるときに限る。代入と使用が次のいずれかで隔てられている場合、参照は解決不能のままとする。

- サブシェル
- `bash -c`（その他 SHELL_WORDS の `-c`）のペイロード
- コマンド置換の本体
- パイプの要素
- ヒアドキュメントの本体

**ビジネスルール**:
- 質問 `requirement.assignment-scope` に対する選択 `same_stream_only` による決定。

#### FR8: プロジェクトルールに沿ったテストケース追加

**説明**: 新挙動を網羅するケースを `em-workflow/hooks/tests/destructive-guard-cases.json` に `[expected_verdict, label, command]` の 3 要素形式で追加する（`.claude/rules/hook-tests.md` に従う）。

**ビジネスルール**:
- 既存の deny / ask ケースはすべてそのまま残す。これにより、この誤検知の抑制が検知力を削っていないことを実行結果で示す。

#### FR9: プラグイン version の更新

**説明**: em-workflow プラグインの version を 0.1.56 -> 0.1.57 に上げる。対象は `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の該当エントリの 2 箇所（`.claude/rules/core-plugin-version-bump.md` に従う）。

**バリデーション**:
| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| version | 2 ファイルの値が一致すること | - |

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR4: コストは有界であること。解決処理は既に字句解析済みの文に対する線形の 1 パスであり、無制限に展開するループを持たない。これはファイル内に既にある MAX_SHELL_PAYLOAD_EXPANSIONS の規律と一致する。

### 5.2 セキュリティ要件

- NFR2: フェイルクローズド。解決器が静的に確定できないケースは、変更前の判定をそのまま維持する。本変更は、完全に解決されたリテラル値を経由する場合を除き、既存の deny または ask を allow に変えることはない。
- NFR6: 変数解決以外の既存挙動には手を入れない。SAFE_DELETE、SELF_CONFIG、TRANSCRIPT、DYNAMIC の各パターン定義そのものは、本フィーチャーでは再定義しない。

### 5.3 可用性要件

- NFR3: 決定性を維持する。同じコマンド文字列は常に同じ判定を返す。これはフックのモジュール docstring に記載されているとおり。

### 5.4 保守性要件

- NFR1: 解決は純粋に静的であること。ファイルシステムへのアクセス、stat、realpath、サブプロセス、シェル起動をいずれも行わない。`normalize_candidate()` が持つ「字句のみの変換」という既存の規律に一致させる。

### 5.5 互換性要件

- NFR5: フックは標準ライブラリのみを使う単一ファイルの Python 3 スクリプトのままとする。新たな依存関係は導入しない。

## 6. UI/UX要件

### 6.1 画面設計要件

該当なし。本変更は既存の Python フックとそのテストケース JSON に閉じており、利用者向けの画面や視覚的な出力を持たない。

### 6.2 画面遷移

該当なし。

### 6.3 レスポンシブ対応

該当なし。

## 7. データ要件

### 7.1 データモデル概要

該当なし（永続化するデータモデルを持たない）。

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| 解決マップ | 変数名 | string | ○ | 平明な代入の左辺 |
| 解決マップ | リテラル値 | string | ○ | 単一のリテラルトークンである右辺 |
| テストケース | expected_verdict | string | ○ | 期待する判定 |
| テストケース | label | string | ○ | ケースのラベル |
| テストケース | command | string | ○ | 判定対象のコマンド文字列 |

### 7.3 データ保持期間

| データ種別 | 保持期間 |
|------------|----------|
| 解決マップ | 1 コマンド文字列の判定中のみ |

## 8. 外部連携

### 8.1 連携システム

該当なし。

### 8.2 API仕様要件

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- 解決は静的解析のみで行う（NFR1）。
- 標準ライブラリのみの単一ファイル Python 3 スクリプトを維持する（NFR5）。
- 既存のパターン定義（SAFE_DELETE、SELF_CONFIG、TRANSCRIPT、DYNAMIC）は再定義しない（NFR6）。
- コマンド接頭辞の代入は、シェルのセマンティクス上、同じコマンド自身の語の展開に影響しないため解決してはならない（FR5）。

### 9.2 ビジネス上の制約

- 検知力を弱めないこと。変数解決は、フックが見る実際の対象を増やす方向にのみ働く。

### 9.3 スケジュール制約

なし。

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

### 9.5 前提事項

- ベースリビジョンにおける em-workflow プラグインの version は 0.1.56 である（ディスパッチ時の注記による）。実装者は version を上げる前にこれを確認する。
- 既存のルール識別子（rm-recursive、rm-unresolvable、rm-root、self-modification、transcript-write）を再利用する。本フィーチャーは新しいルール ID を導入しない。
- SAFE_DELETE、SELF_CONFIG、TRANSCRIPT、DYNAMIC の各正規表現は現状のまま使用し、本フィーチャーでは再定義しない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 変数解決の導入が検知力を削る | 高 | フェイルクローズドを守り（NFR2）、既存の deny / ask ケースをすべて残したままテストを実行して示す（FR8、AC-6） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 誤検知により claude-batch の無人実行が停止する | 高 | 高 | 該当する誤検知クラスを解決可能にする（FR1、FR2、FR3） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: 報告された誤検知コマンド（平明なリテラル代入に続いて、同じネストレベルで、その変数経由で SAFE_DELETE 配下のパスを再帰削除する形）が allow になる。
- [ ] AC-2: 同じ形で SAFE_DELETE の外を指すものが、ルール rm-recursive の deny となり、理由に解決後のパスに対する deletion_alternative コマンドが含まれる。
- [ ] AC-3: root / home の対象に到達する解決値が、ルール rm-root の deny になる。
- [ ] AC-4: SELF_CONFIG に一致する書き込み対象に流れる解決値が ask（self-modification）になり、TRANSCRIPT に一致するものが deny（transcript-write）になる。
- [ ] AC-5: FR5・FR6・FR7 の解決不能な形が、すべて変更前の判定を維持する。再代入ケースの理由文には、変数を分ける旨のヒントが含まれる。
- [ ] AC-6: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が通り、既存の deny / ask ケースがすべて残ったまま、すべて通っている。
- [ ] AC-7: plugin.json と marketplace.json のいずれも 0.1.57 になっている。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系（TS-1）: 報告された誤検知が解消する。`D=/tmp/build-xyz; rm -rf "$D"` -> allow
- [ ] 異常系（TS-2）: SAFE_DELETE 外に解決されたパスがリテラル表記と同じく拒否される。`D=/home/sakura/src/proj; rm -rf "$D"` -> deny（ルール rm-recursive、理由に deletion_alternative コマンドを含む）
- [ ] 異常系（TS-3）: 再代入された変数は解決不能のままで、書き換えヒントが出る。`D=/tmp/a; D=/home/sakura/proj; rm -rf "$D"` -> ask（ルール rm-unresolvable、理由に変数を分ければ解決可能になる旨）
- [ ] 境界値（TS-4）: ネストをまたぐ代入は解決不能のまま。`bash -c 'D=/tmp/x'; rm -rf "$D"` および `(D=/tmp/x); rm -rf "$D"` -> ask（ルール rm-unresolvable）
- [ ] 境界値（TS-5）: コマンド接頭辞の代入は解決不能のまま（シェルは代入が効く前に語を展開する）。`D=/tmp/x rm -rf "$D"` -> ask（ルール rm-unresolvable）
- [ ] 境界値（TS-6）: 解決値にグロブが残る場合は解決不能のまま。`D=/home/sakura/proj/*; rm -rf "$D"` -> ask（ルール rm-unresolvable）
- [ ] 境界値（TS-7）: 解決値にコマンド置換が残る場合は解決不能のまま。`D=$(pwd)/out; rm -rf "$D"` -> ask（ルール rm-unresolvable）
- [ ] セキュリティ（TS-8）: root / home に到達する解決値は拒否される。`D=~; rm -rf "$D"` および `D=/; rm -rf "$D"` -> deny（ルール rm-root）
- [ ] セキュリティ（TS-9）: 全対象判定への適用が self-modification 経路に届く。`V=~/.claude/settings.json; rm "$V"` -> ask（ルール self-modification）
- [ ] セキュリティ（TS-10）: 全対象判定への適用が transcript-write 経路に届く。`V=~/.claude/projects/foo/bar.jsonl; tee "$V"` -> deny（ルール transcript-write）
- [ ] 回帰（TS-11）: `destructive-guard-cases.json` の既存ケース全体が、記録どおりの判定を維持する。
- [ ] パフォーマンス: 該当なし（NFR4 のとおり、既に字句解析済みの文に対する線形の 1 パスに留める）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 解決マップ | コマンド文字列から集めた、変数名からリテラル値への対応 |
| 動的構成 | グロブ（`*`、`?`、`[`）、コマンド置換（`$(`、バッククォート）、マップにない変数参照 |
| SAFE_DELETE | 削除が安全とみなされるパスを表す、フック内の既存パターン |
| SELF_CONFIG | 自己変更判定（self-modification）に用いる、フック内の既存パターン |
| TRANSCRIPT | トランスクリプト書き込み判定（transcript-write）に用いる、フック内の既存パターン |
| DYNAMIC | 動的構成の検出に用いる、フック内の既存パターン |
| `deletion_alternative(target)` | 削除の代わりに提示する置き換えコマンドを組み立てる、フック内の既存処理 |
| `normalize_candidate()` | 字句のみの変換を行う、フック内の既存処理 |
| MAX_SHELL_PAYLOAD_EXPANSIONS | 展開回数の上限を定める、フック内の既存の規律 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 解決値を適用する範囲（`requirement.resolution-scope`）: 対象パスを検査するすべての判定に適用する（`all_target_checks`）。
- [x] SAFE_DELETE 外に解決されたパスの判定（`requirement.resolved-unsafe-verdict`）: リテラル表記と同じ deny とする（`deny_as_literal`）。
- [x] 対象とする代入形式（`requirement.assignment-forms`）: 平明・単段・リテラルの `VAR=value` のみ（`plain_only`）。
- [x] 再代入された変数の扱い（`requirement.reassignment`）: 解決不能として除外する（`unresolvable_on_conflict`）。自由記述「変数を分ける旨のコンテキスト注入」により、判定理由に変数分割のヒントを載せる。
- [x] 代入のスコープ（`requirement.assignment-scope`）: 同一ネストレベルのみ（`same_stream_only`）。
- [x] デザインステップ（`create-spec.design-step` / `design-step.decision`）: スキップ（`skip`）。本変更は既存の Python フック 1 つとそのテストケース JSON に閉じており、利用者向けの表層も視覚的な出力も持たない。上記の要件集合で計画を立てるのに十分である。

### 14.2 未確認・保留事項

- [ ] ベースリビジョンのプラグイン version が 0.1.56 であることを、実装者が version を上げる前に確認する。

なお、`status: tbd` の要件はない。

## 15. 参考資料

- SPEC.md: `feature-docs/destructive-guard-var-resolution/SPEC.md`
- フックのテスト規約: `.claude/rules/hook-tests.md`
- プラグイン version 更新規約: `.claude/rules/core-plugin-version-bump.md`
- 変更対象のフック: `em-workflow/hooks/destructive-guard.py`
- テストケース: `em-workflow/hooks/tests/destructive-guard-cases.json`
- テスト実行: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
