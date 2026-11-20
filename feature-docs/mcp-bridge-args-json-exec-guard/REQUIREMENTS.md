---
title: "mcp-bridge-args-json-exec-guard"
created_date: 2026-11-19
status: draft
---

# mcp-bridge-args-json-exec-guard - 要件定義書

## 1. 概要

### 1.1 背景

notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープ（`\u0024(` / `\u0060`）やシェルのエスケープ（二重引用符の `\$(`、ANSI-C の `\x24(`）で書いたコマンド置換を、destructive-guard が検出しない。トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査していない。

### 1.2 目的

- notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープやシェルのエスケープで書いたコマンド置換を、destructive-guard が検出する。シェルを実行する MCP ツール経由の攻撃シナリオを成立させない。
- トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。
- 上限に当たったとき、または静的な語の引用を復元できないときは、検査していない `command`・本体・ペイロードを残したまま allow にしない（ask。batch では deny）。
- notion の組（`notion-create-comment`）の既存の allow は保つ。範囲外の形（O1、O2）は SPEC と docstring に記録する。

### 1.3 スコープ

対象:

- `statements()` が返す文のうち、コマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文（F01）
- notion の組の除外の条件（F02）
- `run` より後ろの語を mcp-bridge のオプションの読み方で読むことと、`--args-json` の値の再構成（F03）
- JSON の復号、全文字列の置換の再走査、トップレベルの `command` のシェル入力としての再走査（F04、F05）
- 静的に決まらない形の扱い（F06）
- 走査量の上限と、未検査を allow にしないこと（F07）
- 復元できない静的な語の ask（F11）と、ペイロードの展開数の使い切りの ask（F12）
- テストケースの追加、コード内の説明の更新、単体テストの更新（F09、F10、F13）

範囲外（F08 で記録する）:

- O1: `command` 以外のキーや、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド
- O2: F06 の形

## 2. ビジネス要件

### 2.1 ビジネス目標

- notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープやシェルのエスケープで書いたコマンド置換を、destructive-guard が検出する。シェルを実行する MCP ツール経由の攻撃シナリオを成立させない。
- トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。
- 上限に当たったとき、または静的な語の引用を復元できないときは、検査していない `command`・本体・ペイロードを残したまま allow にしない（ask。batch では deny）。
- notion の組（`notion-create-comment`）の既存の allow は保つ。範囲外の形（O1、O2）は SPEC と docstring に記録する。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | destructive-guard フックが Bash の実行を判定する環境で作業する利用者 |

### 2.3 期待される効果

- `--args-json` にエスケープで書いた置換と、トップレベルの `command` に平文で書いた破壊的コマンドが deny になる。
- 上限に当たったときと、静的な語の引用を復元できないときは、未検査のまま allow にならず ask になる。
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
3. `run` より後ろの語を mcp-bridge のオプションの読み方で読み、`--args-json` の値を Bash の引用とエスケープの規則で組み立てる（F03）。
4. 値を JSON として復号し、すべての文字列値から置換の候補を探して再走査する（F04）。
5. トップレベルの `command` の文字列値をシェル入力として再走査する（F05）。

**代替フロー**:
- 静的に決まらない形は、4〜5 を行わず、今の生の文字列による判定を保つ（F06）。
- 走査量の上限の超過、入れ子の上限の超過、構文エラー以外の復号器の失敗、ペイロードの展開数の使い切りは、キューを処理し終えた後に `scan-budget-exceeded` の ask にする（batch では deny）（F07、F12）。
- 静的な語の引用を復元できないときは、キューを処理し終えた後に `args-json-unrestorable` の ask にする（batch では deny）（F11）。

**事後条件**:
- 再走査で見つかった破壊的コマンドが、既存の判定で deny / ask になる。それまでに見つかった deny は、後回しにした ask に勝つ。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| F01 (FR1) | 対象の文 | コマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文を対象にする | 高 |
| F02 (FR2) | notion の組は除外する | 厳密な正規の並びの notion の組だけを、復号と検査の対象にしない | 高 |
| F03 (FR3) | フラグの読み方と `--args-json` の値の再構成 | `run` より後ろの語を mcp-bridge のオプションの読み方で読み、値の語を Bash の引用とエスケープの規則で組み立てる | 高 |
| F04 (FR4) | JSON の復号と全文字列の置換の再走査 | すべての文字列値から置換の候補を探して再走査する | 高 |
| F05 (FR5) | トップレベルの `command` のシェル入力としての再走査 | トップレベルの `command` の文字列値をシェル入力として再走査する | 高 |
| F06 (FR6) | 静的に決まらない形は今の判定を保つ | F04・F05 を行わず、生の文字列による判定を保つ | 高 |
| F07 (FR7) | 走査量の上限と、未検査を allow にしないこと | 処理を `scan_budget` に入れ、上限に当たったら ask にする | 高 |
| F08 (FR8) | 範囲外の記録 | SPEC と docstring に範囲外の形（O1、O2）を記録する | 中 |
| F09 (FR9) | ケースの追加 | `destructive-guard-cases.json` に新しいケースを追加する | 高 |
| F10 (FR10) | コード内の説明の更新 | 関連する docstring とコメントを新しい判定に合わせて直す | 中 |
| F11 (FR11) | 復元できない静的な語は ask にする | 引用の復元だけができない静的な語を `args-json-unrestorable` の ask にする | 高 |
| F12 (FR12) | ペイロードの展開数の使い切りは ask にする | 展開数を使い切って積めなかったペイロードを `scan-budget-exceeded` の ask にする | 高 |
| F13 (FR13) | 単体テストの更新 | `tests/test_destructive_guard_args_json.py` を新しい判定に合わせて直す | 高 |

### 4.2 機能詳細

#### F01 (FR1): 対象の文

**説明**: `statements()` が返すすべての文を対象にする。トップレベルの文、`&&` / `;` / `|` で連なった文、ラッパーの後ろ、置換の本体、`-c` / `eval` / ヒアストリングのペイロード、F05 で積んだ `command` を含む。そのうち、既存の文の分割とラッパーの扱い（`head()` など）で、コマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文に、F02〜F05 と F11 を適用する。ほかのコマンドの引数に `mcp-bridge run` が文字として現れるだけの文は対象にしない。

#### F02 (FR2): notion の組は除外する

**説明**: 次の条件をすべて満たす文だけを notion の組として、F03〜F05 と F11 の対象にしない（mcp-bridge-exec-tool-rescan FR1）。

- `run` より後ろの語が正規のフラグ並びとして読める。`--mcp` / `--tool` / `--args-json` / `--format` / `--session` は次の語を値に取り、`--dry-run` は値を取らない。`=` の形、単ダッシュ、`--` や位置引数は含まない。
- `--mcp` / `--tool` / `--args-json` がそれぞれちょうど 1 回現れる。
- それらのフラグの語と `--mcp` / `--tool` の値の語が、どれも引用符・バックスラッシュ・`$`・バッククォートを含まない 1 続きの語で書かれている。
- `--mcp` の値が `notion` で、`--tool` の値が `notion-create-comment` である。

**ビジネスルール**:
- 引用符で書いたフラグ名、静的でない宛先、F03 の正規でない形を含む文は、組として除外せず検査する。
- `_single_quote_skip_spans()` による生の文字列の引用内の候補の除外は、今の「トップレベルの静的な単一コマンドに限る」制限（W1〜W4、C1、S1、S2）をそのまま保つ。

#### F03 (FR3): フラグの読み方と `--args-json` の値の再構成

**説明**: `run` より後ろの語を、左から mcp-bridge のオプションの読み方で読む（mcp-bridge-exec-tool-rescan D1）。

**ビジネスルール**:
- (a) フラグ位置の語は、Bash の引用除去の後の値で照合する。`'--args-json'`、`"--args-json"`、`\--args-json` は `--args-json` と同じに扱う。
- (b) フラグは `--名前` と `-名前` の両方の形で書ける。名前は `mcp` / `tool` / `args-json` / `format` / `session` / `dry-run`。
- (c) 値を取るフラグ（`mcp` / `tool` / `args-json` / `format` / `session`）は、同じ語の `=` の後ろ（`--args-json=値`）か、次の語を値に取る。`dry-run` は値を取らない（`--dry-run=値` の形も 1 語で完結する）。
- (d) 語 `--` はフラグの並びを終える。フラグ位置に、`-` で始まらない語（位置引数）が来たときも、並びを終える。それより後ろの語はフラグとして読まない。
- (e) `--args-json` が 2 回以上現れるときは、すべての値を、それぞれ独立に F04・F05・F11 の対象にする。
- (f) 値の語（`=` の形では `=` より後ろの部分）は、Bash の引用とエスケープの規則で組み立てる。対象は、単一引用符、二重引用符（`\$`、`` \` ``、`\"`、`\\` と行継続）、ANSI-C 引用（`_decode_ansi_c()`）、引用の外のバックスラッシュ、それらを連結した語。生の文字列の走査が引用内で候補として印を付けた `$(` やバッククォートは、Bash にとって文字どおりのテキストなので、印を外して文字として値に含める。`=` の形は、引用除去した後の語の最初の `=` で、フラグ名と値に分ける。
- (g) `--mcp` / `--tool` の値の語が静的でなくても、`--args-json` の値は読む（A8）。

**出力**:
- `--args-json` の値: 文字列 - Bash の引用とエスケープの規則で組み立てた引数の値（`--args-json` ごとに 1 つ）

#### F04 (FR4): JSON の復号と全文字列の置換の再走査

**説明**: F03 の値を標準の JSON として復号する。入れ子のオブジェクトと配列をたどり、すべての文字列値から `$(` とバッククォートの置換の候補を、生の文字列のときと同じ規則で探す。候補の本体は、既存の置換の本体と同じように `pending` に積んで再走査する。

**ビジネスルール**:
- 重複したキーは、最後の値だけでなく、すべての組を対象にする。

#### F05 (FR5): トップレベルの `command` のシェル入力としての再走査

**説明**: 復号した値のトップレベルがオブジェクトで、トップレベルの `command` キーの値が空白だけでない文字列のときは、その文字列を `-c` のペイロードと同じようにシェル入力として `pending` に積み、再走査する。

**ビジネスルール**:
- 重複したキーは、すべての組を積む。
- これらの `command` は `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）の数に入れない。上限は `scan_budget` だけで持ち、積んだ `command` は取り出すときに `scan_budget` に加える（F07）。
- トップレベル以外の `command`、`command` 以外のキー、文字列でない値は、F04 の置換の再走査だけを受ける。

#### F06 (FR6): 静的に決まらない形は今の判定を保つ

**説明**: 次の形では F04・F05 を行わず、今の生の文字列による判定を保つ。

1. `--args-json` の値の語が、置換、パラメータ展開、算術展開、引用の外の `$` やバッククォート、引用の外のグロブ・ブレース・チルダを含む形（引用の復元だけができない形は F11）。
2. フラグ位置の語が (1) と同じ意味で静的でない形。
3. フラグ位置に、F03 の名前に当たらない `-` で始まる語（知らないフラグ）がある形。
4. 値を取るフラグに値の語が無い形。
5. `--args-json` が無い形。
6. JSON の構文エラーになる値。
7. 復号した値のトップレベルがオブジェクトでない形。

**ビジネスルール**:
- Bash が実際に実行する置換の本体は、これまでどおり再走査する。
- `--args-json` が 2 回以上あるときは、値ごとに判断する（静的な値は検査する）。
- 宛先（`--mcp` / `--tool` の値）が静的でない形、引用符で書いたフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複は、F06 の形ではない。

#### F07 (FR7): 走査量の上限と、未検査を allow にしないこと

**説明**: 値の組み立て、JSON の復号、入れ子をたどる処理、復号した文字列の再走査を、`statements()` の全体の走査量の上限（`scan_budget`）に入れる。積んだ本体と `command` は、取り出すときにも加える。

**ビジネスルール**:
- 次のどれかのために、検査しないまま残した `command`・本体・ペイロードが 1 つでもあれば、判定を allow にしない。
    - `scan_budget` の超過
    - `MAX_ARGS_JSON_DEPTH` を超える入れ子（復号の前に判定する）
    - 構文エラー以外の復号器の失敗
    - F12 の展開数の使い切り
- そのときの ask は `scan-budget-exceeded`（batch では deny）。
- `--args-json` の処理での超過や失敗は、すでにキューにある既存の検査を、今の上限の中で処理し終えた後に ask を出す。それまでに見つかった deny が勝つ。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| scan-budget-exceeded | 走査量が `scan_budget` を超えた。入れ子が `MAX_ARGS_JSON_DEPTH` を超えた。構文エラー以外の復号器の失敗 | `scan-budget-exceeded` の ask（batch では deny）。`--args-json` の処理による場合は、キューを処理し終えた後に出し、deny が勝つ |

#### F08 (FR8): 範囲外の記録

**説明**: このフィーチャーの SPEC の Security Considerations と、`_mcp_bridge_args_json_chunks()`（または NFR5 で移した先の関数）と `extract_shell_payload_anchored()` の docstring に、同じ範囲で記録する。

- O1: `command` 以外のキー（例: desktop-commander の `interact_with_process` の `input`）や、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド。置換の候補の検索だけを受ける。
- O2: F06 の形。
    1. 置換や変数展開などで決まる、静的でない `--args-json` の値の語（Bash が実行する置換の本体は再走査する）。
    2. 静的でないフラグ位置の語。
    3. 知らないフラグ。
    4. 値の無い、値を取るフラグ。
    5. `--args-json` が無い形。
    6. JSON として復号できない値。
    7. トップレベルがオブジェクトでない値。

**ビジネスルール**:
- 静的に決まらない宛先、復元できない ANSI-C、引用符付きのフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複は、範囲外に含めない。

#### F09 (FR9): ケースの追加

**説明**: `em-workflow/hooks/tests/destructive-guard-cases.json` に、テストシナリオの新しいケース（TS-1〜TS-15 の既存分に加え、TS-17〜TS-29）を追加する。既存のケースは消さず、変えない。

**ビジネスルール**:
- F12 で、既存のケースの期待する判定と合わなくなるもの（26 個以上のペイロードで allow を期待するケース）が見つかったときは、そのケースを変えずに作業を止めて報告する。

#### F10 (FR10): コード内の説明の更新

**説明**: mcp-bridge の `--args-json` の扱いとペイロードの展開数を述べる docstring とコメントを、新しい判定に合わせて直す。対象は次のとおり。

- `_single_quote_skip_spans()`
- `scan_structure()` のシングルクォート候補の段落
- `statements()` の docstring とキュー投入ループのコメント
- `extract_shell_payload_anchored()` の範囲外の宣言（F08 の O1、O2）
- `_mcp_bridge_args_json_chunks()` の docstring（フラグの読み方、O2 の縮小、A4）
- `MAX_SHELL_PAYLOAD_EXPANSIONS` の定義のコメント（使い切ったときは F12 の ask。トップレベルの `command` は数えない）

#### F11 (FR11): 復元できない静的な語は ask にする

**説明**: `--args-json` の値の語、またはフラグ位置の語が、F06 (1) の要素（置換、パラメータ展開、算術展開、引用の外の `$` やバッククォート、引用の外のグロブ・ブレース・チルダ）を含まず、引用の復元だけができないときは、F06 にせず ask にする。例: ANSI-C 引用の NUL（`\0`）、ASCII の外の文字（`\u00e9` など）、`_decode_ansi_c()` が扱わないエスケープ、ロケール引用 `$"..."`。

**ビジネスルール**:
- 理由 ID は新しい `args-json-unrestorable`。
- 理由の文言は「mcp-bridge run の --args-json の値、またはフラグの語の引用を静的に復元できないため、安全側で確認を挟む」の趣旨にする。
- 検査は続け、キューを処理し終えた後に ask を出す。それまでに見つかった deny が勝つ。
- batch では deny に降格する。
- notion の組（F02）の文には適用しない。

#### F12 (FR12): ペイロードの展開数の使い切りは ask にする

**説明**: `-c` / `eval` / ヒアストリングのペイロードを、`MAX_SHELL_PAYLOAD_EXPANSIONS`（25）を使い切ったために積まなかったときは、黙って読み飛ばさず、キューを処理し終えた後に `scan-budget-exceeded` の ask にする（batch では deny）。それまでに見つかった deny が勝つ。

**ビジネスルール**:
- トップレベルのコマンド、置換の本体、F05 で積んだ `command` から取り出したペイロードを含め、どの文のペイロードにも適用する。
- F05 の `command` は、この数に入れない。

#### F13 (FR13): 単体テストの更新

**説明**: `tests/test_destructive_guard_args_json.py` のうち、変更前の判定を固定しているテストを、新しい判定に合わせて直す。

- `TestPayloadCounter`: `command` は数えず、使い切りは F12 の ask。
- `TestFlagReading`: 引用符付きのフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複、静的でない宛先は検査する。知らないフラグ、値の無いフラグ、`--args-json` の無い形、`run` でない形は検査しない。
- `TestDocstring`: O2 の文言。

**ビジネスルール**:
- 同じ変更の中で `python3 -m unittest tests.test_destructive_guard_args_json` を走らせる。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR1: 1 回の判定を、`hooks.json` の destructive-guard のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS` に収める。巨大な JSON、深い入れ子、多数のトップレベルの `command` でも、再帰や走査量が際限なく増えない（F05、F07）。

### 5.2 セキュリティ要件

- NFR2: 既存の deny / ask の判定を allow に変えない。allow から ask への変更は、F11 と F12 の形（AC-13、AC-14）に限る。
- 入力検証: `mcp-bridge run` の `run` より後ろの語を mcp-bridge の読み方で読み、`--args-json` の静的な値を Bash の引用とエスケープの規則で組み立てて、標準の JSON として復号する。すべての文字列値の置換の候補と、トップレベルの `command` のすべての文字列値を再走査する（F03〜F05）。notion の組は、厳密な正規の並びのときだけ除外する（F02）。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR3: 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる（`.claude/rules/hook-tests.md`）。新しい deny / ask のケースは修正の前に追加し、変更前のフックがそれらを allow にすること（見逃しの再現）を確かめる。TS-19 は変更前も deny なので、この再現の対象に含めない。
- NFR4: `plugin.json` と `marketplace.json` の version は変えない。patch は GitHub Actions が上げる（`.claude/rules/core-plugin-version-bump.md`）。
- NFR5: `statements()` のループに入っている `--args-json` の処理（判定の呼び出し、走査量の加算、本体と `command` の投入、停止と後回しにした ask の記録）は、`statements()` の外の関数にまとめる。`statements()` からは文ごとに 1 回呼び出す。F11・F12 で後回しにする ask の記録も、同じ仕組みでまとめる。

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
| mcp-bridge | `mcp-bridge run` のコマンド行を destructive-guard が静的に解析する | `run` より後ろの語と `--args-json` の値 |

### 8.2 API仕様要件

該当なし

## 9. 制約条件

### 9.1 技術的制約

- `_single_quote_skip_spans()` の除外は、今の「トップレベルの静的な単一コマンドに限る」制限（W1〜W4、C1、S1、S2）をそのまま保つ。
- notion の組の条件は、フラグの読み方を広げても（F03）広げない（A9）。
- 既存のケースは消さず、変えない。既存のケースの期待する判定と合わなくなるものが見つかったときは、そのケースを変えずに作業を止めて報告する（F09）。

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
| 巨大な JSON、深い入れ子、多数のトップレベルの `command` で走査量が増える | 中 | 値の組み立て・復号・入れ子の走査・再走査を `scan_budget` に入れ、上限に当たったら `scan-budget-exceeded` の ask にする（F05、F07） |
| batch では新しい ask が deny に降格する | 低 | 新しい ask は、ペイロード 26 個以上、復元できない静的な語、走査量の超過のときだけに限る（A10） |
| 範囲外の形（O1、O2）は検出しない | 中 | SPEC の Security Considerations と docstring に記録する（F08） |

### 10.2 ビジネスリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1 (FR3, FR4): TS-1〜TS-4（JSON のエスケープとシェルのエスケープで書いた置換）が、変更後に deny になる。変更前は allow になる。
- [ ] AC-2 (FR5): TS-5（トップレベルの `command` に平文の破壊的コマンド）が、変更後に deny になる。変更前は allow になる。
- [ ] AC-3 (FR4): TS-6（`command` 以外の入れ子の文字列にエスケープした置換）が deny になる。
- [ ] AC-4 (FR1): TS-7、TS-8（ほかのコマンドと連ねた文、ラッパーの後ろ）が deny になる。TS-11（ほかのコマンドの引数に文字として現れるだけ）が allow になる。
- [ ] AC-5 (FR2): TS-9（notion の組とエスケープした置換）と、notion の組の既存の allow ケースが allow のまま。TS-29（フラグ名を引用符で書いた notion の組）は deny になる。
- [ ] AC-6 (FR6, FR8): 範囲外の形の TS-10、TS-13、TS-14、TS-27、TS-28 は allow になる。ケースのラベルと SPEC・docstring の範囲外の記述（O1、O2）が一致している。静的でない宛先、復元できない ANSI-C、引用符付きのフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複は、範囲外の記述に無い。
- [ ] AC-7 (FR7): TS-15 が `scan-budget-exceeded` の ask になり、10 秒以内に終わる。
- [ ] AC-8 (NFR2): ほかの既存のケースが、期待する判定（理由 ID を固定しているケースはその理由 ID も）を保つ。ランナーが通り、既存のケースは 1 件も消されていない。
- [ ] AC-9 (FR10): FR10 に挙げた docstring とコメントが新しい判定を述べ、FR8 の範囲外の形を記録している。
- [ ] AC-10 (FR3): TS-17（引用符で書いたフラグ名 `'--args-json'`）が deny になる。変更前は allow。
- [ ] AC-11 (FR5, FR7): TS-18（無害な `command` 25 件の後ろの破壊的な `command`）と TS-19（復号した `command` 25 件の後ろの `bash -c` の破壊的ペイロード）が deny になる。変更前は TS-18 が allow、TS-19 は deny。
- [ ] AC-12 (FR3, FR6): TS-20（静的でない `--mcp` と静的な破壊的 `command`）が deny になる。変更前は allow。
- [ ] AC-13 (FR11): TS-21（有効な JSON の後ろに ANSI-C の `\0` がある値）が `args-json-unrestorable` の ask になる。変更前は allow。
- [ ] AC-14 (FR12): TS-22（`bash -c` の無害なペイロード 25 個の後ろの `bash -c` の破壊的ペイロード）が `scan-budget-exceeded` の ask になる。変更前は allow。
- [ ] AC-15 (FR3): TS-23〜TS-26（`=` の形、単ダッシュ、`--` の前の値、`--args-json` の重複の先の値）が deny になる。変更前はどれも allow。
- [ ] AC-16 (NFR5): `statements()` の `--args-json` の処理は、文ごとに 1 回の関数呼び出しになっている。
- [ ] AC-17 (FR13): `python3 -m unittest tests.test_destructive_guard_args_json` が通る。直したテストは新しい判定を固定している。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: JSON のエスケープ・シェルのエスケープで書いた置換と、トップレベルの `command` の平文の破壊的コマンドが deny になる（TS-1〜TS-6）
- [ ] 正常系: ほかのコマンドと連ねた文、ラッパーの後ろでも deny になる（TS-7、TS-8）
- [ ] 正常系: 引用符で書いたフラグ名、`=` の形、単ダッシュ、`--` の前の値、`--args-json` の重複、静的でない宛先でも、静的な値を検査して deny になる（TS-17、TS-20、TS-23〜TS-26）
- [ ] 正常系: フラグ名を引用符で書いた notion の組は、組として除外せず deny になる（TS-29）
- [ ] 正常系: 正規の並びの notion の組、無害な `command`、ほかのコマンドの引数に文字として現れるだけの形は allow になる（TS-9、TS-11、TS-12）
- [ ] 異常系: 範囲外の形は今の判定を保つ（TS-10、TS-13、TS-14、TS-27、TS-28）
- [ ] 異常系: 引用を復元できない静的な値は `args-json-unrestorable` の ask になる（TS-21）
- [ ] 境界値: トップレベルの `command` が 26 件でも全件を検査し、`command` 25 件の後ろの文のペイロードも取り出す（TS-18、TS-19）
- [ ] 境界値: 26 個目のペイロードは使い切りで積めないので `scan-budget-exceeded` の ask になる（TS-22）
- [ ] パフォーマンス: 走査量の上限を超える JSON が `scan-budget-exceeded` の ask になり、10 秒以内に終わる（TS-15）
- [ ] 回帰: 既存のケースがすべて期待する判定を保つ（TS-16）

各シナリオのコマンドは SPEC.md の Test Scenarios に記載する。

### 12.2 エッジケース

- トップレベルの `command` が多数あるとき: 展開数に入れず全件を積む。上限は `scan_budget` で、超えたら `scan-budget-exceeded` の ask（F05、F07）。
- ペイロードが 26 個以上あるとき: 26 個目以降は積まず、`scan-budget-exceeded` の ask。それまでの deny が勝つ（F12）。
- 宛先が静的でない: 静的な `--args-json` の値は検査する。notion の組にはならない（F02、F03 (g)）。
- ANSI-C の NUL、ASCII 外の文字、扱わないエスケープ、ロケール引用: 値の語でもフラグ位置の語でも、`args-json-unrestorable` の ask（F11）。
- 引用符付きのフラグ名: 引用除去した後の値で照合する。notion の組の条件は満たさない（F02、F03 (a)）。
- `=` の形、単ダッシュ、`--` や位置引数の前の値、`--args-json` の重複: すべて読んで検査する（F03）。
- ask が複数あるとき: 優先は deny > `scan-budget-exceeded`（走査量の超過・入れ子・復号器の失敗・展開数の使い切り）> `args-json-unrestorable`。batch では ask が deny に降格する。
- `--args-json` の値の 1 つが静的でなく、別の値が静的: 静的な値は検査し、静的でない値は F06 のまま（F03 (e)、F06）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| notion の組 | F02 の条件をすべて満たす、`--mcp notion` / `--tool notion-create-comment` の文 |
| 正規のフラグ並び | `--mcp` / `--tool` / `--args-json` / `--format` / `--session` が次の語を値に取り、`--dry-run` が値を取らない語の並び。`=` の形、単ダッシュ、`--` や位置引数は含まない |
| `pending` | `statements()` が再走査する入力を積むキュー |
| `scan_budget` | `statements()` の全体の走査量の上限 |
| `MAX_SHELL_PAYLOAD_EXPANSIONS` | `-c` / `eval` / ヒアストリングのペイロードの展開数の上限（25）。トップレベルの `command` は数えない |
| `MAX_ARGS_JSON_DEPTH` | `--args-json` の値の入れ子の上限。復号の前に判定する |
| `scan-budget-exceeded` | 走査量の超過、入れ子の上限の超過、構文エラー以外の復号器の失敗、ペイロードの展開数の使い切りのときの ask の理由 ID |
| `args-json-unrestorable` | 静的な語の引用を復元できないときの ask の理由 ID |
| O1、O2 | このフィーチャーの範囲外の形（F08） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 前提 A1: `notion-create-comment` は `--args-json` をデータとしてだけ使い、シェルのコマンドとして実行しない（mcp-bridge-exec-tool-rescan A1 と同じ）。
- [x] 前提 A2: mcp-bridge は `--args-json` を標準の JSON として読む。重複したキーをどう扱うかは分からないので、すべての組を検査する。
- [x] 前提 A3: シェルを実行する MCP ツールは、引数をトップレベルの `command` に取るのが一般的（desktop-commander の `start_process`）。ほかのキーで実行する形の平文は範囲外とする（O1）。
- [x] 前提 A4: トップレベルの `command` は `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）の数に入れず、`scan_budget` で上限を持つ。`-c` / `eval` / ヒアストリングのペイロードが 25 を超えて積めないときは、黙って読み飛ばさず `scan-budget-exceeded` の ask にする（F12）。
- [x] 前提 A5: `--dry-run` 付きの `mcp-bridge run` も、ほかの形と同じように検査する。
- [x] 前提 A6: 新しいケースには、ask を固定する TS-15（`scan-budget-exceeded`）、TS-21（`args-json-unrestorable`）、TS-22（`scan-budget-exceeded`）を除いて、`rule` の要素を付けない。
- [x] 前提 A7: version は変えない。
- [x] 前提 A8: 宛先（`--mcp` / `--tool` の値）が静的でなくても、静的な `--args-json` の値は検査する。静的でない宛先の文は notion の組にならない。deny になるのは値に破壊的コマンドがあるときだけ。
- [x] 前提 A9: notion の組の除外は、フラグの語と値の語がどれも引用符なしの 1 続きの語で、各フラグが 1 回だけの正規の並びに限る（mcp-bridge-exec-tool-rescan FR1、TM-5）。フラグの読み方を広げても（F03）、組の条件は広げない。
- [x] 前提 A10: batch では ask が deny に降格する。新しい ask は、ペイロード 26 個以上、復元できない静的な語、走査量の超過のときだけで、普段の作業ではまず起きない。そのため誤 deny の費用は小さいと見込む。
- [x] 前提 A11: F03 (b)〜(d) のフラグの読み方（単ダッシュ、`=` の形、`--` と位置引数で並びを終える）は、mcp-bridge-exec-tool-rescan IMPLEMENTATION.md D1 に記録された mcp-bridge のオプションの読み方に従う。create-plan で D1 と突き合わせる。
- [x] ペイロードの展開数の使い切り（`requirement.args-json.payload-counter-exhaustion`）: `separate_count_fail_closed`（F05、F12、A4）
- [x] ask の理由 ID（`requirement.args-json.ask-reason-id`）: `budget_for_bounds_new_for_unrestorable`。上限には `scan-budget-exceeded`、復元できない語には新しい `args-json-unrestorable`（F07、F11、F12、A6）
- [x] 正規でないフラグの形（`requirement.args-json.noncanonical-flag-forms`）: `read_mcp_bridge_forms`（F03、F06、F08、A11）
- [x] 静的に決まらない形（`requirement.args-json.undeterminable-forms`）: F06 のとおり縮小する。対象の文の範囲、検査の範囲、デザインステップの判断（skip）はそのまま

### 14.2 未確認・保留事項

なし

## 15. 参考資料

- 脅威モデル: `feature-docs/mcp-bridge-args-json-exec-guard/THREAT-MODEL.md`
- `.claude/rules/hook-tests.md`: フックのテストの手順
- `.claude/rules/core-plugin-version-bump.md`: version の扱い
- mcp-bridge-exec-tool-rescan: FR1（正規のフラグ並び）、A1、IMPLEMENTATION.md D1（mcp-bridge のオプションの読み方）
- review round 1 の指摘: 65c5a71c6af6cb06、32aa9e6e947c325d、e0e4df99e5cded9d、934ab7486f2cfbfb、ed852daefce04839
