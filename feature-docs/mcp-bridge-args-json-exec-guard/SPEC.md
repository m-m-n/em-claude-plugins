# Feature: mcp-bridge-args-json-exec-guard

要件定義書: `feature-docs/mcp-bridge-args-json-exec-guard/REQUIREMENTS.md`

## Overview

notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープ（`\u0024(` / `\u0060`）やシェルのエスケープ（二重引用符の `\$(`、ANSI-C の `\x24(`）で書いたコマンド置換を、destructive-guard が検出する。トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。上限（走査量、入れ子、ペイロードの展開数）に当たったときと、静的な語の引用を復元できないときは、未検査のまま allow にせず ask にする。notion の組（`notion-create-comment`）の既存の allow は保つ。値やフラグの語が動的な形と、`command` 以外のキーに平文で書く形は、範囲外として記録する。

## Objectives

- notion の組以外の `mcp-bridge run` で、`--args-json` に JSON のエスケープやシェルのエスケープで書いたコマンド置換を、destructive-guard が検出する。シェルを実行する MCP ツール経由の攻撃シナリオを成立させない。
- トップレベルの `command` キーに平文で書いた破壊的コマンドも、シェル入力として検査する。
- 上限に当たったとき、または静的な語の引用を復元できないときは、検査していない `command`・本体・ペイロードを残したまま allow にしない（ask。batch では deny）。
- notion の組（`notion-create-comment`）の既存の allow は保つ。範囲外の形（O1、O2）は SPEC と docstring に記録する。

## Acceptance Criteria

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
- [ ] AC-11 (FR5, FR7): TS-18（無害な `command` 25 件の後ろの破壊的な `command`）と TS-19（復号した `command` 25 件の後ろの `bash -c` の破壊的ペイロード）が deny になる。変更前はどちらも allow。
- [ ] AC-12 (FR3, FR6): TS-20（静的でない `--mcp` と静的な破壊的 `command`）が deny になる。変更前は allow。
- [ ] AC-13 (FR11): TS-21（有効な JSON の後ろに ANSI-C の `\0` がある値）が `args-json-unrestorable` の ask になる。変更前は allow。
- [ ] AC-14 (FR12): TS-22（`bash -c` の無害なペイロード 25 個の後ろの `bash -c` の破壊的ペイロード）が `scan-budget-exceeded` の ask になる。変更前は allow。
- [ ] AC-15 (FR3): TS-23〜TS-26（`=` の形、単ダッシュ、`--` の前の値、`--args-json` の重複の先の値）が deny になる。変更前はどれも allow。
- [ ] AC-16 (NFR5): `statements()` の `--args-json` の処理は、文ごとに 1 回の関数呼び出しになっている。
- [ ] AC-17 (FR13): `python3 -m unittest tests.test_destructive_guard_args_json` が通る。直したテストは新しい判定を固定している。

## Technical Requirements

### Functional Requirements

- **FR1:** 対象の文 — `statements()` が返すすべての文を対象にする。トップレベルの文、`&&` / `;` / `|` で連なった文、ラッパーの後ろ、置換の本体、`-c` / `eval` / ヒアストリングのペイロード、FR5 で積んだ `command` を含む。そのうち、既存の文の分割とラッパーの扱い（`head()` など）で、コマンドの位置に `mcp-bridge` が静的に決まり、2 語目がちょうど `run` の文に、FR2〜FR5 と FR11 を適用する。ほかのコマンドの引数に `mcp-bridge run` が文字として現れるだけの文は対象にしない。
- **FR2:** notion の組は除外する — 次の条件をすべて満たす文だけを notion の組として、FR3〜FR5 と FR11 の対象にしない（mcp-bridge-exec-tool-rescan FR1）。
    - `run` より後ろの語が正規のフラグ並び（`--mcp` / `--tool` / `--args-json` / `--format` / `--session` は次の語を値に取り、`--dry-run` は値を取らない。`=` の形、単ダッシュ、`--` や位置引数は含まない）として読める。
    - `--mcp` / `--tool` / `--args-json` がそれぞれちょうど 1 回現れる。
    - それらのフラグの語と `--mcp` / `--tool` の値の語が、どれも引用符・バックスラッシュ・`$`・バッククォートを含まない 1 続きの語で書かれている。
    - `--mcp` の値が `notion` で、`--tool` の値が `notion-create-comment` である。

  引用符で書いたフラグ名、静的でない宛先、FR3 の正規でない形を含む文は、組として除外せず検査する。`_single_quote_skip_spans()` による生の文字列の引用内の候補の除外は、今の「トップレベルの静的な単一コマンドに限る」制限（W1〜W4、C1、S1、S2）をそのまま保つ。
- **FR3:** フラグの読み方と `--args-json` の値の再構成 — `run` より後ろの語を、左から mcp-bridge のオプションの読み方で読む（mcp-bridge-exec-tool-rescan D1）。
    - (a) フラグ位置の語は、Bash の引用除去の後の値で照合する。`'--args-json'`、`"--args-json"`、`\--args-json` は `--args-json` と同じに扱う。
    - (b) フラグは `--名前` と `-名前` の両方の形で書ける。名前は `mcp` / `tool` / `args-json` / `format` / `session` / `dry-run`。
    - (c) 値を取るフラグ（`mcp` / `tool` / `args-json` / `format` / `session`）は、同じ語の `=` の後ろ（`--args-json=値`）か、次の語を値に取る。`dry-run` は値を取らない（`--dry-run=値` の形も 1 語で完結する）。
    - (d) 語 `--` はフラグの並びを終える。フラグ位置に、`-` で始まらない語（位置引数）が来たときも、並びを終える。それより後ろの語はフラグとして読まない。
    - (e) `--args-json` が 2 回以上現れるときは、すべての値を、それぞれ独立に FR4・FR5・FR11 の対象にする。
    - (f) 値の語（`=` の形では `=` より後ろの部分）は、Bash の引用とエスケープの規則で組み立てる。対象は、単一引用符、二重引用符（`\$`、`` \` ``、`\"`、`\\` と行継続）、ANSI-C 引用（`_decode_ansi_c()`）、引用の外のバックスラッシュ、それらを連結した語。生の文字列の走査が引用内で候補として印を付けた `$(` やバッククォートは、Bash にとって文字どおりのテキストなので、印を外して文字として値に含める。`=` の形は、引用除去した後の語の最初の `=` で、フラグ名と値に分ける。
    - (g) `--mcp` / `--tool` の値の語が静的でなくても、`--args-json` の値は読む（A8）。
- **FR4:** JSON の復号と全文字列の置換の再走査 — FR3 の値を標準の JSON として復号する。入れ子のオブジェクトと配列をたどり、すべての文字列値から `$(` とバッククォートの置換の候補を、生の文字列のときと同じ規則で探す。候補の本体は、既存の置換の本体と同じように `pending` に積んで再走査する。重複したキーは、最後の値だけでなく、すべての組を対象にする。
- **FR5:** トップレベルの `command` のシェル入力としての再走査 — 復号した値のトップレベルがオブジェクトで、トップレベルの `command` キーの値が空白だけでない文字列のときは、その文字列を `-c` のペイロードと同じようにシェル入力として `pending` に積み、再走査する。重複したキーは、すべての組を積む。これらの `command` は `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）の数に入れない。上限は `scan_budget` だけで持ち、積んだ `command` は取り出すときに `scan_budget` に加える（FR7）。トップレベル以外の `command`、`command` 以外のキー、文字列でない値は、FR4 の置換の再走査だけを受ける。
- **FR6:** 静的に決まらない形は今の判定を保つ — 次の形では FR4・FR5 を行わず、今の生の文字列による判定を保つ。
    1. `--args-json` の値の語が、置換、パラメータ展開、算術展開、引用の外の `$` やバッククォート、引用の外のグロブ・ブレース・チルダを含む形（引用の復元だけができない形は FR11）。
    2. フラグ位置の語が (1) と同じ意味で静的でない形。
    3. フラグ位置に、FR3 の名前に当たらない `-` で始まる語（知らないフラグ）がある形。
    4. 値を取るフラグに値の語が無い形。
    5. `--args-json` が無い形。
    6. JSON の構文エラーになる値。
    7. 復号した値のトップレベルがオブジェクトでない形。

  Bash が実際に実行する置換の本体は、これまでどおり再走査する。`--args-json` が 2 回以上あるときは、値ごとに判断する（静的な値は検査する）。宛先（`--mcp` / `--tool` の値）が静的でない形、引用符で書いたフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複は、FR6 の形ではない。
- **FR7:** 走査量の上限と、未検査を allow にしないこと — 値の組み立て、JSON の復号、入れ子をたどる処理、復号した文字列の再走査を、`statements()` の全体の走査量の上限（`scan_budget`）に入れる。積んだ本体と `command` は、取り出すときにも加える。次のどれかのために、検査しないまま残した `command`・本体・ペイロードが 1 つでもあれば、判定を allow にしない。`scan_budget` の超過、`MAX_ARGS_JSON_DEPTH` を超える入れ子（復号の前に判定する）、構文エラー以外の復号器の失敗、FR12 の展開数の使い切り。そのときの ask は `scan-budget-exceeded`（batch では deny）。`--args-json` の処理での超過や失敗は、すでにキューにある既存の検査を、今の上限の中で処理し終えた後に ask を出す。それまでに見つかった deny が勝つ。
- **FR8:** 範囲外の記録 — このフィーチャーの SPEC の Security Considerations と、`_mcp_bridge_args_json_chunks()`（または NFR5 で移した先の関数）と `extract_shell_payload_anchored()` の docstring に、同じ範囲で記録する。O1: `command` 以外のキー（例: desktop-commander の `interact_with_process` の `input`）や、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド。置換の候補の検索だけを受ける。O2: FR6 の形。(1) 置換や変数展開などで決まる、静的でない `--args-json` の値の語（Bash が実行する置換の本体は再走査する）。(2) 静的でないフラグ位置の語。(3) 知らないフラグ。(4) 値の無い、値を取るフラグ。(5) `--args-json` が無い形。(6) JSON として復号できない値。(7) トップレベルがオブジェクトでない値。静的に決まらない宛先、復元できない ANSI-C、引用符付きのフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複は、範囲外に含めない。
- **FR9:** ケースの追加 — `em-workflow/hooks/tests/destructive-guard-cases.json` に、Test Scenarios の新しいケース（TS-1〜TS-15 の既存分に加え、TS-17〜TS-29）を追加する。既存のケースは消さず、変えない。FR12 で、既存のケースの期待する判定と合わなくなるもの（26 個以上のペイロードで allow を期待するケース）が見つかったときは、そのケースを変えずに作業を止めて報告する。
- **FR10:** コード内の説明の更新 — mcp-bridge の `--args-json` の扱いとペイロードの展開数を述べる docstring とコメントを、新しい判定に合わせて直す。対象は次のとおり。
    - `_single_quote_skip_spans()`
    - `scan_structure()` のシングルクォート候補の段落
    - `statements()` の docstring とキュー投入ループのコメント
    - `extract_shell_payload_anchored()` の範囲外の宣言（FR8 の O1、O2）
    - `_mcp_bridge_args_json_chunks()` の docstring（フラグの読み方、O2 の縮小、A4）
    - `MAX_SHELL_PAYLOAD_EXPANSIONS` の定義のコメント（使い切ったときは FR12 の ask。トップレベルの `command` は数えない）
- **FR11:** 復元できない静的な語は ask にする — `--args-json` の値の語、またはフラグ位置の語が、FR6 (1) の要素（置換、パラメータ展開、算術展開、引用の外の `$` やバッククォート、引用の外のグロブ・ブレース・チルダ）を含まず、引用の復元だけができないときは、FR6 にせず ask にする。例: ANSI-C 引用の NUL（`\0`）、ASCII の外の文字（`\u00e9` など）、`_decode_ansi_c()` が扱わないエスケープ、ロケール引用 `$"..."`。理由 ID は新しい `args-json-unrestorable`。理由の文言は「mcp-bridge run の --args-json の値、またはフラグの語の引用を静的に復元できないため、安全側で確認を挟む」の趣旨にする。検査は続け、キューを処理し終えた後に ask を出す。それまでに見つかった deny が勝つ。batch では deny に降格する。notion の組（FR2）の文には適用しない。
- **FR12:** ペイロードの展開数の使い切りは ask にする — `-c` / `eval` / ヒアストリングのペイロードを、`MAX_SHELL_PAYLOAD_EXPANSIONS`（25）を使い切ったために積まなかったときは、黙って読み飛ばさず、キューを処理し終えた後に `scan-budget-exceeded` の ask にする（batch では deny）。それまでに見つかった deny が勝つ。トップレベルのコマンド、置換の本体、FR5 で積んだ `command` から取り出したペイロードを含め、どの文のペイロードにも適用する。FR5 の `command` は、この数に入れない。
- **FR13:** 単体テストの更新 — `tests/test_destructive_guard_args_json.py` のうち、変更前の判定を固定しているテストを、新しい判定に合わせて直す。`TestPayloadCounter`（`command` は数えず、使い切りは FR12 の ask）、`TestFlagReading`（引用符付きのフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複、静的でない宛先は検査する。知らないフラグ、値の無いフラグ、`--args-json` の無い形、`run` でない形は検査しない）、`TestDocstring`（O2 の文言）。同じ変更の中で `python3 -m unittest tests.test_destructive_guard_args_json` を走らせる。

### Non-Functional Requirements

- **NFR1 - Performance:** 1 回の判定を、`hooks.json` の destructive-guard のタイムアウト（10 秒）と、ランナーの `GUARD_TIMEOUT_SECONDS` に収める。巨大な JSON、深い入れ子、多数のトップレベルの `command` でも、再帰や走査量が際限なく増えない（FR5、FR7）。
- **NFR2 - Fail-closed:** 既存の deny / ask の判定を allow に変えない。allow から ask への変更は、FR11 と FR12 の形（AC-13、AC-14）に限る。
- **NFR3 - Test procedure:** 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる（`.claude/rules/hook-tests.md`）。新しい deny / ask のケースは修正の前に追加し、変更前のフックがそれらを allow にすること（見逃しの再現）を確かめる。
- **NFR4 - Version:** `plugin.json` と `marketplace.json` の version は変えない。patch は GitHub Actions が上げる（`.claude/rules/core-plugin-version-bump.md`）。
- **NFR5 - Maintainability:** `statements()` のループに入っている `--args-json` の処理（判定の呼び出し、走査量の加算、本体と `command` の投入、停止と後回しにした ask の記録）は、`statements()` の外の関数にまとめる。`statements()` からは文ごとに 1 回呼び出す。FR11・FR12 で後回しにする ask の記録も、同じ仕組みでまとめる。

## Implementation Approach

### Architecture

`em-workflow/hooks/destructive-guard.py` の `statements()` の走査で、`mcp-bridge run` の文に対する処理を `statements()` の外の関数にまとめ、文ごとに 1 回呼ぶ（NFR5）。

```
statements() が返す文（FR1）
  └─ コマンドの位置が mcp-bridge、2 語目が run か
       ├─ いいえ → 今の判定
       └─ はい → --args-json の処理の関数を呼ぶ（NFR5）
            ├─ notion の組（FR2）→ 復号と検査をしない（今の判定）
            └─ それ以外
                 ├─ run より後ろの語を mcp-bridge のオプションの読み方で読む（FR3 (a)〜(e)）
                 │    ├─ 静的でないフラグ位置の語、知らないフラグ、値の無いフラグ、--args-json の欠落
                 │    │    → 今の生の文字列による判定（FR6）
                 │    └─ 引用の復元だけができないフラグ位置の語 → args-json-unrestorable を後回しの ask に記録（FR11）
                 └─ --args-json の値ごとに（FR3 (e)）
                      ├─ 静的でない値の語 → 今の判定（FR6）
                      ├─ 引用の復元だけができない値の語 → args-json-unrestorable を後回しの ask に記録（FR11）
                      ├─ Bash の引用とエスケープの規則で値を組み立てる（FR3 (f)）
                      ├─ 入れ子が MAX_ARGS_JSON_DEPTH を超える（復号の前に判定）→ scan-budget-exceeded（FR7）
                      ├─ 標準の JSON として復号する（FR4）
                      │    ├─ 構文エラー／トップレベルがオブジェクトでない → 今の判定（FR6）
                      │    └─ 構文エラー以外の復号器の失敗 → scan-budget-exceeded（FR7）
                      ├─ すべての文字列値から置換の候補を探し、本体を pending に積む（FR4）
                      └─ トップレベルの command の文字列値を、シェル入力として pending に積む（FR5）

キューを処理し終えた後: deny > scan-budget-exceeded > args-json-unrestorable（batch では ask を deny に降格）
```

- FR12 の使い切りの記録と FR11 の ask の記録は、既存の `early_stop`（`SCAN_BUDGET_ASK`、`UNMATCHED_SUBSCRIPT_ASK` と同じ `(理由 ID, 文言)` の組）の仕組みで、キューを処理し終えた後に渡す。

### Data Flow

```
run より後ろの語 → フラグの読み方（FR3）→ --args-json の値の組み立て（FR3）
  → JSON の復号（FR4）→ 入れ子をたどる（FR4）
  → 置換の本体 / トップレベルの command → pending → 再走査
  （組み立て・復号・入れ子の走査・積んだ本体と command の取り出しは scan_budget に入れる。FR7）
  （-c / eval / ヒアストリングのペイロードは MAX_SHELL_PAYLOAD_EXPANSIONS で数える。トップレベルの command は数えない。FR5、FR12）
```

### Dependencies

**Internal Dependencies:**
- `statements()`: 文の分割、`pending` による再走査、`scan_budget`
- `head()` などのラッパーの扱い: コマンドの位置の決定（FR1）
- `_decode_ansi_c()`: ANSI-C 引用の復号（FR3）
- `_single_quote_skip_spans()`: notion の組の引用内の候補の除外（FR2）
- `_mcp_bridge_args_json_chunks()`: `--args-json` の値の扱い（FR8、FR10）
- `extract_shell_payload_anchored()`: 範囲外の宣言（FR8、FR10）
- `MAX_SHELL_PAYLOAD_EXPANSIONS`: `-c` / `eval` / ヒアストリングのペイロードの展開数の上限（FR5、FR12）
- `MAX_ARGS_JSON_DEPTH`: `--args-json` の値の入れ子の上限（FR7）
- `early_stop`（`SCAN_BUDGET_ASK`、`UNMATCHED_SUBSCRIPT_ASK`）: 後回しにする ask の記録（FR11、FR12）
- mcp-bridge-exec-tool-rescan FR1: 正規のフラグ並びと notion の組（FR2）
- mcp-bridge-exec-tool-rescan IMPLEMENTATION.md D1: mcp-bridge のオプションの読み方（FR3、A11）

**External Dependencies:**
- なし

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # FR1〜FR8、FR10〜FR12、NFR5
└── tests/
    └── destructive-guard-cases.json     # FR9
tests/
└── test_destructive_guard_args_json.py  # FR13
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/mcp-bridge-args-json-exec-guard/**`
- `test-docs/mcp-bridge-args-json-exec-guard/**`

`feature-docs/mcp-bridge-args-json-exec-guard/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/mcp-bridge-args-json-exec-guard/**` covers `test-docs/mcp-bridge-args-json-exec-guard/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/mcp-bridge-args-json-exec-guard/` directory at all; the declared
`test-docs/mcp-bridge-args-json-exec-guard/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

各シナリオは `em-workflow/hooks/tests/destructive-guard-cases.json` のケースとして追加する（FR9）。TS-1〜TS-15 は追加済み。`rule` の要素を付けるのは TS-15（`scan-budget-exceeded`）、TS-21（`args-json-unrestorable`）、TS-22（`scan-budget-exceeded`）だけ（A6）。下のコマンドはシェルに渡す文字列そのもの。ケースファイルでは JSON の文字列としてエスケープする。

### Unit Tests

- [ ] TS-1: JSON の `\u0024(` で書いた置換。変更前は allow - deny（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0024(git branch -D example)","shell":"bash"}'
  ```
- [ ] TS-2: JSON の `\u0060` で書いたバッククォートの置換 - deny（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0060git branch -D example\u0060","shell":"bash"}'
  ```
- [ ] TS-3: 二重引用符の中の `\$(` で書いた置換 - deny（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"echo \$(git branch -D example)\",\"shell\":\"bash\"}"
  ```
- [ ] TS-4: ANSI-C 引用の `\x24(` で書いた置換 - deny（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{"command":"echo \x24(git branch -D example)","shell":"bash"}'
  ```
- [ ] TS-5: トップレベルの `command` に平文の破壊的コマンド。変更前は allow - deny（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-6: `command` 以外の入れ子の文字列に、エスケープした置換 - deny（追加済み）
  ```
  mcp-bridge run --mcp example-server --tool example-tool --args-json '{"msg":{"text":"\u0024(git branch -D example)"}}'
  ```
- [ ] TS-9: notion の組は復号の対象にしない - allow（追加済み）
  ```
  mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"\u0024(git branch -D example) と記載する"}'
  ```
- [ ] TS-12: 無害な `command` - allow（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"ls -la","shell":"bash"}'
  ```
- [ ] TS-17: 引用符で書いたフラグ名 `'--args-json'` は `--args-json` と同じに読む（FR3）。変更前は allow - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process '--args-json' '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-20: 宛先 `--mcp` が静的でなくても、静的な `--args-json` の値は検査する（FR3 (g)、A8）。変更前は allow - deny
  ```
  mcp-bridge run --mcp "$S" --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-21: 有効な JSON の後ろに ANSI-C の `\0` があり、引用を復元できない値は ask（FR11）。変更前は allow - ask、`rule` は `args-json-unrestorable`
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{"command":"git branch -D example"}\0'
  ```
- [ ] TS-23: `=` の形の `--args-json=値` も読む（FR3 (c)）。変更前は allow - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json='{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-24: 単ダッシュの `-args-json` も読む（FR3 (b)）。変更前は allow - deny
  ```
  mcp-bridge run -mcp desktop-commander -tool start_process -args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-25: `--` と位置引数の前の `--args-json` の値も読む（FR3 (d)）。変更前は allow - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}' -- extra
  ```
- [ ] TS-26: `--args-json` を 2 回書いても、すべての値を検査する（FR3 (e)）。変更前は allow - deny
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}' --args-json '{"command":"ls"}'
  ```

### Integration Tests

- [ ] TS-7: `&&` で連ねた文 - deny（追加済み）
  ```
  cd /tmp && mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0024(git branch -D example)","shell":"bash"}'
  ```
- [ ] TS-8: ラッパー `env` の後ろ - deny（追加済み）
  ```
  env mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-11: コマンドの位置ではない。ほかのコマンドの引数に文字として現れるだけ - allow（追加済み）
  ```
  echo "mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{\"command\":\"git branch -D example\"}'"
  ```
- [ ] TS-18: トップレベルの `command` を 26 件（無害な `true` を 25 件、最後に破壊的コマンド）。`command` は展開数に入れないので全件を検査する（FR5）。変更前は allow - deny。`"command":"true"` を `,` で区切って計 25 回並べる形で、create-plan で 25 回を書き下す。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"true",…,"command":"git branch -D example"}'
  ```
- [ ] TS-19: 復号した `command` 25 件の後ろの文の `bash -c` のペイロードも取り出す（FR5。指摘 934ab7486f2cfbfb）。変更前は allow - deny。`"command":"true"` を計 25 回並べる形で、create-plan で 25 回を書き下す。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"true",…}'; bash -c 'git branch -D example'
  ```
- [ ] TS-22: `bash -c` のペイロード 25 個の後ろの 26 個目は、使い切りで積めないので ask（FR12）。変更前は allow - ask、`rule` は `scan-budget-exceeded`。`bash -c 'true'` を `;` で区切って計 25 回並べる形で、create-plan で 25 回を書き下す。
  ```
  bash -c 'true'; …; bash -c 'git branch -D example'
  ```
- [ ] TS-29: フラグ名を引用符で書いた notion の組は組として除外せず、復号して検査する（FR2、A9） - deny
  ```
  mcp-bridge run '--mcp' notion --tool notion-create-comment --args-json '{"body":"\u0024(git branch -D example) と記載する"}'
  ```
- [ ] TS-16: 既存のケースがすべて期待する判定を保つ（notion の組の allow、mcp-bridge-exec-tool-rescan の deny を含む） - 回帰なし

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases

エッジケースの扱い:

- トップレベルの `command` が多数あるとき: 展開数に入れず全件を積む。上限は `scan_budget` で、超えたら `scan-budget-exceeded` の ask（FR5、FR7）。
- ペイロードが 26 個以上あるとき: 26 個目以降は積まず、`scan-budget-exceeded` の ask。それまでの deny が勝つ（FR12）。
- 宛先が静的でない: 静的な `--args-json` の値は検査する。notion の組にはならない（FR2、FR3 (g)）。
- ANSI-C の NUL、ASCII 外の文字、扱わないエスケープ、ロケール引用: 値の語でもフラグ位置の語でも、`args-json-unrestorable` の ask（FR11）。
- 引用符付きのフラグ名: 引用除去した後の値で照合する。notion の組の条件は満たさない（FR2、FR3 (a)）。
- `=` の形、単ダッシュ、`--` や位置引数の前の値、`--args-json` の重複: すべて読んで検査する（FR3）。
- ask が複数あるとき: 優先は deny > `scan-budget-exceeded`（走査量の超過・入れ子・復号器の失敗・展開数の使い切り）> `args-json-unrestorable`。batch では ask が deny に降格する。
- `--args-json` の値の 1 つが静的でなく、別の値が静的: 静的な値は検査し、静的でない値は FR6 のまま（FR3 (e)、FR6）。

範囲外の形（FR6、FR8）:

- [ ] TS-10: 範囲外 O1: `command` 以外のキーに平文で書いたコマンド - allow（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool interact_with_process --args-json '{"pid":1,"input":"git branch -D example"}'
  ```
- [ ] TS-13: 範囲外 O2 (1): 置換の出力が値になる形。`cat` の本体は再走査される - allow（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "$(cat args.json)"
  ```
- [ ] TS-14: 範囲外 O2 (6): JSON として復号できない値は、今の生の文字列による判定を保つ - allow（追加済み）
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0024(git branch -D example)"'
  ```
- [ ] TS-27: 範囲外 O2 (2): フラグ位置の語が変数展開で静的でない形は、今の判定を保つ - allow
  ```
  mcp-bridge run $OPTS --args-json '{"command":"git branch -D example"}'
  ```
- [ ] TS-28: 範囲外 O2 (3): 知らないフラグがある形は、今の判定を保つ - allow
  ```
  mcp-bridge run --unknown x --args-json '{"command":"git branch -D example"}'
  ```

### Performance Tests

- [ ] TS-15: 深い入れ子や大量の文字列で走査量の上限を超える JSON（FR7）。10 秒以内に終わる。追加済みの nesting と chain の 2 件（`destructive-guard-cases.json` の TS-15 nesting / TS-15 chain） - ask、`rule` は `scan-budget-exceeded`

## Security Considerations

- **Input Validation:** `mcp-bridge run` の `run` より後ろの語を mcp-bridge の読み方で読み、`--args-json` の静的な値を Bash の引用とエスケープの規則で組み立てて、標準の JSON として復号する。すべての文字列値の置換の候補と、トップレベルの `command` のすべての文字列値を再走査する（FR3〜FR5）。notion の組は、厳密な正規の並びのときだけ除外する（FR2）。
- **Fail-closed:** 既存の deny / ask の判定を allow に変えない（NFR2）。走査量の超過、入れ子の上限、構文エラー以外の復号器の失敗、ペイロードの展開数の使い切りは `scan-budget-exceeded` の ask。静的な語の引用を復元できないときは `args-json-unrestorable` の ask。どれもキューを処理し終えた後に出し、見つかった deny が勝つ。batch では deny に降格する（FR7、FR11、FR12）。
- **Threat model impact:** `THREAT-MODEL.md` の受け入れ済みの残りから、静的に決まらない宛先、復元できない ANSI-C、単ダッシュ、`=` の形、`--` や位置引数、`--args-json` の重複が外れる。Unchanged dependencies の A4 の段落（展開数を使い切ったら `command` を積まない）も成り立たなくなる。TM-2（重複の全件の検査）は、上限に当たっても ask にすることで満たす。

### 範囲外（FR8）

次の形は、このフィーチャーでは検出しない。

- O1: `command` 以外のキー（例: desktop-commander の `interact_with_process` の `input`）や、トップレベル以外の `command` に、置換を使わず平文で書いたコマンド。置換の候補の検索だけを受ける（TS-10）。
- O2: FR6 の形。今の生の文字列による判定を保つ。
    1. 置換や変数展開などで決まる、静的でない `--args-json` の値の語。Bash が実行する置換の本体は再走査する（TS-13）
    2. 静的でないフラグ位置の語（TS-27）
    3. 知らないフラグ（TS-28）
    4. 値の無い、値を取るフラグ
    5. `--args-json` が無い形
    6. JSON として復号できない値（TS-14）
    7. トップレベルがオブジェクトでない値

静的に決まらない宛先、復元できない ANSI-C、引用符付きのフラグ名、`=` の形、単ダッシュ、`--` や位置引数の後ろ、`--args-json` の重複は、範囲外に含めない。

### 前提

- A1: `notion-create-comment` は `--args-json` をデータとしてだけ使い、シェルのコマンドとして実行しない（mcp-bridge-exec-tool-rescan A1 と同じ）。
- A2: mcp-bridge は `--args-json` を標準の JSON として読む。重複したキーをどう扱うかは分からないので、すべての組を検査する。
- A3: シェルを実行する MCP ツールは、引数をトップレベルの `command` に取るのが一般的（desktop-commander の `start_process`）。ほかのキーで実行する形の平文は範囲外とする（O1）。
- A4: トップレベルの `command` は `MAX_SHELL_PAYLOAD_EXPANSIONS`（25）の数に入れず、`scan_budget` で上限を持つ。`-c` / `eval` / ヒアストリングのペイロードが 25 を超えて積めないときは、黙って読み飛ばさず `scan-budget-exceeded` の ask にする（FR12）。
- A5: `--dry-run` 付きの `mcp-bridge run` も、ほかの形と同じように検査する。
- A6: 新しいケースには、ask を固定する TS-15（`scan-budget-exceeded`）、TS-21（`args-json-unrestorable`）、TS-22（`scan-budget-exceeded`）を除いて、`rule` の要素を付けない。
- A7: version は変えない。
- A8: 宛先（`--mcp` / `--tool` の値）が静的でなくても、静的な `--args-json` の値は検査する。静的でない宛先の文は notion の組にならない。deny になるのは値に破壊的コマンドがあるときだけ。
- A9: notion の組の除外は、フラグの語と値の語がどれも引用符なしの 1 続きの語で、各フラグが 1 回だけの正規の並びに限る（mcp-bridge-exec-tool-rescan FR1、TM-5）。フラグの読み方を広げても（FR3）、組の条件は広げない。
- A10: batch では ask が deny に降格する。新しい ask は、ペイロード 26 個以上、復元できない静的な語、走査量の超過のときだけで、普段の作業ではまず起きない。そのため誤 deny の費用は小さいと見込む。
- A11: FR3 (b)〜(d) のフラグの読み方（単ダッシュ、`=` の形、`--` と位置引数で並びを終える）は、mcp-bridge-exec-tool-rescan IMPLEMENTATION.md D1 に記録された mcp-bridge のオプションの読み方に従う。create-plan で D1 と突き合わせる。

## Error Handling

| 状況 | 判定 |
|------|------|
| 走査量が `scan_budget` を超えた。`--args-json` の入れ子が `MAX_ARGS_JSON_DEPTH` を超えた。構文エラー以外の復号器の失敗（FR7） | `scan-budget-exceeded` の ask（batch では deny）。`--args-json` の処理による場合は、キューを処理し終えた後に出し、deny が勝つ |
| `-c` / `eval` / ヒアストリングのペイロードを、展開数（25）を使い切ったために積めなかった（FR12） | キューを処理し終えた後に `scan-budget-exceeded` の ask（batch では deny）。deny が勝つ |
| `--args-json` の値の語、またはフラグ位置の語の引用を、静的に復元できない（FR11） | キューを処理し終えた後に `args-json-unrestorable` の ask（batch では deny）。deny が勝つ |
| FR6 の形（静的でない値の語やフラグ位置の語、知らないフラグ、値の無いフラグ、`--args-json` の欠落、JSON の構文エラー、トップレベルがオブジェクトでない値） | FR4・FR5 を行わず、生の文字列による今の判定 |

## Performance Optimization

### Performance Goals

- 1 回の判定を、`hooks.json` の 10 秒と `GUARD_TIMEOUT_SECONDS` に収める（NFR1）。

### Optimization Strategies

- 走査量の上限: 値の組み立て、復号、入れ子の走査、積んだ本体と `command` の再走査を `scan_budget` に入れる。トップレベルの `command` は展開数に入れず、`scan_budget` で上限を持つ（FR5、FR7）。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` が通り、既存のケースは 1 件も消されていない
- [ ] `python3 -m unittest tests.test_destructive_guard_args_json` が通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/mcp-bridge-args-json-exec-guard/REQUIREMENTS.md`
- 脅威モデル: `feature-docs/mcp-bridge-args-json-exec-guard/THREAT-MODEL.md`
- フックのテスト: `.claude/rules/hook-tests.md`
- version の扱い: `.claude/rules/core-plugin-version-bump.md`
- mcp-bridge-exec-tool-rescan: FR1（正規のフラグ並び）、A1、IMPLEMENTATION.md D1（mcp-bridge のオプションの読み方）
- review round 1 の指摘: 65c5a71c6af6cb06、32aa9e6e947c325d、e0e4df99e5cded9d、934ab7486f2cfbfb、ed852daefce04839
