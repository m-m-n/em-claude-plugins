---
title: "mcp-bridge-args-json-exec-guard"
created_date: 2026-11-19
status: draft
---

# mcp-bridge-args-json-exec-guard - 要件定義書

## 1. 概要

### 1.1 背景

notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープ（`$(` / ```）やシェルのエスケープ（二重引用符の `\$(`、ANSI-C の `\x24(`）で書いたコマンド置換を、destructive-guard が検出しない。トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査していない。

### 1.2 目的

- notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープやシェルのエスケープで書いたコマンド置換を、destructive-guard が検出する。シェルを実行する MCP ツール経由の攻撃シナリオを成立させない。
- トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。
- notion の組（`notion-create-comment`）の既存の allow は保つ。

### 1.3 スコープ

対象:

- `statements()` が返す文のうち、コマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文（F01）
- `--args-json` の値の再構成、JSON の復号、全文字列の置換の再走査、トップレベルの `command` のシェル入力としての再走査（F03〜F05）
- 走査量の上限（F07）
- テストケースの追加と、コード内の説明の更新（F09、F10）

範囲外（F08 で記録する）:

- `command` 以外のキーや、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド
- 静的に決まらない形（動的な値、静的に決まらない宛先、JSON として読めない値、`--args-json` の欠落・重複・`=` の形）

## 2. ビジネス要件

### 2.1 ビジネス目標

- シェルを実行する MCP ツール経由の攻撃シナリオを、destructive-guard で成立させない。
- notion の組の既存の allow を保つ。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | destructive-guard フックが Bash の実行を判定する環境で作業する利用者 |

### 2.3 期待される効果

- `--args-json` にエスケープで書いた置換と、トップレベルの `command` に平文で書いた破壊的コマンドが deny になる。
- notion の組と、範囲外の形の判定は今のまま保たれる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | `mcp-bridge run` を含む Bash コマンドの判定 | destructive-guard フック | 高 |

### 3.2 ユースケース詳細

#### UC01: `mcp-bridge run` を含む Bash コマンドの判定

**アクター**: destructive-guard フック

**事前条件**:
- Bash のコマンドに、コマンドの位置が `mcp-bridge` で 2 語目が `run` の文が含まれる。

**基本フロー**:
1. `statements()` が文を返し、対象の文を決める（F01）。
2. notion の組の文は、復号と検査の対象にしない（F02）。
3. `--args-json` の値を Bash の引用とエスケープの規則で組み立てる（F03）。
4. 値を JSON として復号し、すべての文字列値から置換の候補を探して再走査する（F04）。
5. トップレベルの `command` の文字列値をシェル入力として再走査する（F05）。

**代替フロー**:
- 静的に決まらない形は、3〜5 を行わず、今の生の文字列による判定を保つ（F06）。
- 走査量の上限を超えたときは、`scan-budget-exceeded` の ask にする（batch では deny）（F07）。

**事後条件**:
- 再走査で見つかった破壊的コマンドが、既存の判定で deny / ask になる。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| F01 (FR1) | 対象の文 | コマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文を対象にする | 高 |
| F02 (FR2) | notion の組は除外する | notion の組を持つ文は復号と検査の対象にしない | 高 |
| F03 (FR3) | `--args-json` の値の再構成 | 値の語を Bash の引用とエスケープの規則で組み立てる | 高 |
| F04 (FR4) | JSON の復号と全文字列の置換の再走査 | すべての文字列値から置換の候補を探して再走査する | 高 |
| F05 (FR5) | トップレベルの `command` のシェル入力としての再走査 | トップレベルの `command` の文字列値をシェル入力として再走査する | 高 |
| F06 (FR6) | 静的に決まらない形は今の判定を保つ | F03〜F05 を行わず、生の文字列による判定を保つ | 高 |
| F07 (FR7) | 走査量の上限 | 復号と再走査を `scan_budget` に入れる | 高 |
| F08 (FR8) | 範囲外の記録 | SPEC と docstring に範囲外の形を記録する | 中 |
| F09 (FR9) | ケースの追加 | `destructive-guard-cases.json` に新しいケースを追加する | 高 |
| F10 (FR10) | コード内の説明の更新 | 関連する docstring とコメントを新しい判定に合わせて直す | 中 |

### 4.2 機能詳細

#### F01 (FR1): 対象の文

**説明**: `statements()` が返すすべての文を対象にする。トップレベルの文、`&&` / `;` / `|` で連なった文、ラッパーの後ろ、置換の本体、`-c` / `eval` / ヒアストリングのペイロードを含む。そのうち、既存の文の分割とラッパーの扱い（`head()` など）でコマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文に、F02〜F05 を適用する。ほかのコマンドの引数に `mcp-bridge run` が文字として現れるだけの文は対象にしない。

#### F02 (FR2): notion の組は除外する

**説明**: mcp-bridge-exec-tool-rescan FR1 の正規のフラグ並びで notion の組（`--mcp notion` / `--tool notion-create-comment`）を持つ文は、F03〜F05 の復号と検査の対象にしない。`_single_quote_skip_spans()` による生の文字列の引用内の候補の除外は、今の「トップレベルの静的な単一コマンドに限る」制限（W1〜W4、C1、S1、S2）をそのまま保つ。

#### F03 (FR3): `--args-json` の値の再構成

**説明**: `run` より後ろの語を正規のフラグ並びとして読み、`--args-json` がちょうど 1 回現れるときに、その値の語を対象にする。値の語が静的なときだけ、Bash の引用とエスケープの規則で引数の値を組み立てる。生の文字列の走査が引用内で候補として印を付けた `$(` やバッククォートは、Bash にとって文字どおりのテキストなので、印を外して文字として値に含める。

**入力**:
- `run` より後ろの語: 正規のフラグ並び
    - `--mcp` / `--tool` / `--args-json` / `--format` / `--session` は次の語を値として取る
    - `--dry-run` は値を取らない

**出力**:
- `--args-json` の値: 文字列 - Bash の引用とエスケープの規則で組み立てた引数の値

**ビジネスルール**:
- 組み立ての対象は、単一引用符、二重引用符（`\$`、`` \` ``、`\"`、`\\` と行継続）、ANSI-C 引用（既存の `_decode_ansi_c()`）、引用の外のバックスラッシュ、それらを連結した語。

#### F04 (FR4): JSON の復号と全文字列の置換の再走査

**説明**: F03 の値を標準の JSON として復号する。入れ子のオブジェクトと配列をたどり、すべての文字列値から `$(` とバッククォートの置換の候補を、生の文字列のときと同じ規則で探す。候補の本体は、既存の置換の本体と同じように `pending` に積んで再走査する。

**ビジネスルール**:
- 重複したキーは、最後の値だけでなく、すべての組を対象にする。

#### F05 (FR5): トップレベルの `command` のシェル入力としての再走査

**説明**: 復号した値のトップレベルがオブジェクトで、トップレベルの `command` キーの値が文字列のときは、その文字列を `-c` のペイロードと同じようにシェル入力として `pending` に積み、再走査する。

**ビジネスルール**:
- 重複したキーは、すべての組を対象にする。
- このペイロードは、入力全体で共有している既存の `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）の数に入れる。
- トップレベル以外の `command`、`command` 以外のキー、文字列でない値は、F04 の置換の再走査だけを受ける。

#### F06 (FR6): 静的に決まらない形は今の判定を保つ

**説明**: 次の形は F03〜F05 を行わず、今の生の文字列による判定を保つ。Bash が実際に実行する置換の本体は、これまでどおり再走査する。

- 値が置換や変数展開で決まる形
- 宛先が静的に決まらない形
- JSON として読めない値
- `--args-json` が無い・重複する・`=` で書かれている形
- 正規のフラグ並びとして読めない形
- トップレベルがオブジェクトでない値

#### F07 (FR7): 走査量の上限

**説明**: JSON の復号、入れ子をたどる処理、復号した文字列の再走査を、`statements()` の全体の走査量の上限（`scan_budget`）に入れる。この上限は `MAX_SHELL_PAYLOAD_EXPANSIONS` の数とは別に数える。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| scan-budget-exceeded | 走査量が `scan_budget` を超えた | 既存の `scan-budget-exceeded` の ask にする（batch では deny） |

#### F08 (FR8): 範囲外の記録

**説明**: このフィーチャーの SPEC の Security Considerations と、該当するコードの docstring に、範囲外の形を記録する。

- 1 つめ: `command` 以外のキー（例: desktop-commander の `interact_with_process` の `input`）や、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド
- 2 つめ: F06 の形（動的な値、静的に決まらない宛先、JSON として読めない値、`--args-json` の欠落・重複・`=` の形）

#### F09 (FR9): ケースの追加

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に、テストシナリオの新しいケースを追加する。既存のケースは消さず、変えない。

#### F10 (FR10): コード内の説明の更新

**説明**: mcp-bridge の `--args-json` の扱いを述べる docstring とコメントを、新しい判定に合わせて直す。対象は次のとおり。

- `_single_quote_skip_spans()`
- `scan_structure()` のシングルクォート候補の段落
- `statements()` の docstring とキュー投入ループのコメント
- `extract_shell_payload_anchored()` の範囲外の宣言（F07）

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1: 1 回の判定を、`hooks.json` の destructive-guard のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS` に収める。巨大な JSON や深い入れ子でも、再帰や走査量が際限なく増えない（F07）。

### 5.2 セキュリティ要件

- NFR2: 既存の deny / ask の判定を allow に変えない。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR3: 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる（`.claude/rules/hook-tests.md`）。新しい deny ケースは修正の前に追加し、変更前のフックがそれらを allow にすること（見逃しの再現）を確かめる。
- NFR4: `plugin.json` と `marketplace.json` の version は変えない。patch は GitHub Actions が上げる（`.claude/rules/core-plugin-version-bump.md`）。

### 5.5 互換性要件

- notion の組（`notion-create-comment`）の既存の allow を保つ。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

### 8.1 連携システム

| システム名 | 連携方法 | データ |
|------------|----------|--------|
| mcp-bridge | `mcp-bridge run` のコマンド行を destructive-guard が静的に解析する | `--args-json` の値 |

### 8.2 API仕様要件

該当なし

## 9. 制約条件

### 9.1 技術的制約

- `_single_quote_skip_spans()` の除外は、今の「トップレベルの静的な単一コマンドに限る」制限（W1〜W4、C1、S1、S2）をそのまま保つ。
- `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）を使い切った後に積まれるはずだったペイロードの扱いは、既存の `-c` / `eval` と同じにし、このフィーチャーでは変えない。
- 既存のケースは消さず、変えない。

### 9.2 ビジネス上の制約

- version は変えない。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/mcp-bridge-args-json-exec-guard/**`
- `test-docs/mcp-bridge-args-json-exec-guard/**`

`feature-docs/mcp-bridge-args-json-exec-guard/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/mcp-bridge-args-json-exec-guard/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/mcp-bridge-args-json-exec-guard/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/mcp-bridge-args-json-exec-guard/` ディレクトリを生成しないが、宣言された `test-docs/mcp-bridge-args-json-exec-guard/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 巨大な JSON や深い入れ子で走査量が増える | 中 | 復号・入れ子の走査・再走査を `scan_budget` に入れ、超えたら `scan-budget-exceeded` の ask にする（F07） |
| 範囲外の形（平文の `command` 以外のキー、静的に決まらない形）は検出しない | 中 | SPEC の Security Considerations と docstring に記録する（F08） |

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1 (FR3, FR4): TS-1〜TS-4（JSON のエスケープとシェルのエスケープで書いた置換）が、変更後に deny になる。変更前は allow になる。
- [ ] AC-2 (FR5): TS-5（トップレベルの `command` に平文の破壊的コマンド）が、変更後に deny になる。変更前は allow になる。
- [ ] AC-3 (FR4): TS-6（`command` 以外の入れ子の文字列にエスケープした置換）が deny になる。
- [ ] AC-4 (FR1): TS-7、TS-8（ほかのコマンドと連ねた文、ラッパーの後ろ）が deny になる。TS-11（ほかのコマンドの引数に文字として現れるだけ）が allow になる。
- [ ] AC-5 (FR2): TS-9（notion の組とエスケープした置換）と、notion の組の既存の allow ケースが allow のまま。
- [ ] AC-6 (FR6, FR8): 範囲外の形の TS-10、TS-13、TS-14 は allow になる。ケースのラベルと SPEC の範囲外の記述が一致している。
- [ ] AC-7 (FR7): TS-15 が `scan-budget-exceeded` の ask になり、10 秒以内に終わる。
- [ ] AC-8 (NFR2): ほかの既存のケースが、期待する判定（理由 ID を固定しているケースはその理由 ID も）を保つ。ランナーが通り、既存のケースは 1 件も消されていない。
- [ ] AC-9 (FR10): FR10 に挙げた docstring とコメントが新しい判定を述べ、FR8 の範囲外の形を記録している。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: JSON のエスケープ・シェルのエスケープで書いた置換と、トップレベルの `command` の平文の破壊的コマンドが deny になる（TS-1〜TS-6）
- [ ] 正常系: ほかのコマンドと連ねた文、ラッパーの後ろでも deny になる（TS-7、TS-8）
- [ ] 正常系: notion の組、無害な `command`、ほかのコマンドの引数に文字として現れるだけの形は allow になる（TS-9、TS-11、TS-12）
- [ ] 異常系: 範囲外の形は今の判定を保つ（TS-10、TS-13、TS-14）
- [ ] パフォーマンス: 走査量の上限を超える JSON が `scan-budget-exceeded` の ask になり、10 秒以内に終わる（TS-15）
- [ ] 回帰: 既存のケースがすべて期待する判定を保つ（TS-16）

各シナリオのコマンドは SPEC.md の Test Scenarios に記載する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| notion の組 | `--mcp notion` / `--tool notion-create-comment` の組 |
| 正規のフラグ並び | `--mcp` / `--tool` / `--args-json` / `--format` / `--session` が次の語を値として取り、`--dry-run` が値を取らない語の並び |
| `pending` | `statements()` が再走査する入力を積むキュー |
| `scan_budget` | `statements()` の全体の走査量の上限 |
| `MAX_SHELL_PAYLOAD_EXPANSIONS` | 入力全体で共有するシェル入力のペイロードの展開数の上限（25） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 前提 A1: `notion-create-comment` は `--args-json` をデータとしてだけ使い、シェルのコマンドとして実行しない（mcp-bridge-exec-tool-rescan A1 と同じ）。
- [x] 前提 A2: mcp-bridge は `--args-json` を標準の JSON として読む。重複したキーをどう扱うかは分からないので、すべての組を検査する。
- [x] 前提 A3: シェルを実行する MCP ツールは、引数をトップレベルの `command` に取るのが一般的（desktop-commander の `start_process`）。ほかのキーで実行する形の平文は範囲外とする。
- [x] 前提 A4: `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）を使い切った後に積まれるはずだったペイロードの扱いは、既存の `-c` / `eval` と同じにし、このフィーチャーでは変えない。
- [x] 前提 A5: `--dry-run` 付きの `mcp-bridge run` も、ほかの形と同じように検査する。
- [x] 前提 A6: 新しいケースには、TS-15 を除いて `rule` の要素を付けない。
- [x] 前提 A7: version は変えない。

### 14.2 未確認・保留事項

なし

## 15. 参考資料

- `.claude/rules/hook-tests.md`: フックのテストの手順
- `.claude/rules/core-plugin-version-bump.md`: version の扱い
- mcp-bridge-exec-tool-rescan: FR1（正規のフラグ並び）、A1
