# Feature: args-json-quoting-bypass

## Overview

destructive-guard フックの `mcp-bridge run --args-json` 検査にある 2 件の high のすり抜けを塞ぐ。
1 件は語分割で偽装した notion ペアの除外（3f7145c6c8c0b26a）、もう 1 件は `=` 付きフラグ語の中の、
クォートされていないバックスラッシュでエスケープされた `=`（f16e5bb8d5da2621）。
あわせて、対象に含めた medium の指摘を解消する。

## Objectives

- destructive-guard の `mcp-bridge run --args-json` 検査の 2 件の high のすり抜けを塞ぐ。
    - 語分割で偽装した notion ペアの除外（3f7145c6c8c0b26a）
    - `=` 付きフラグ語の中の、クォートされていないバックスラッシュでエスケープされた `=`（f16e5bb8d5da2621）
- 対象の medium を解消する: dc2fdf65ce30d198、f35ed060564bcf20、0379cf2eb7ad4e92 / 9981fd673b28e7e4、
  3340375b4b50c4b0（確認のみ）。
- 既存の notion ペアの allow ケースはすべて allow のまま保つ。既存の deny / ask の判定を allow にしない。

## Acceptance Criteria

- [ ] AC-1（FR1, FR8）: TS-1 から TS-4 が deny になる。修正前は allow。
- [ ] AC-2（FR1）: TS-5 が allow になる。既存の notion ペアの allow ケース（`destructive-guard-cases.json`
  の 1161、1162、1163、1200、1201、1374、1405 行目）は allow のまま。
- [ ] AC-3（FR2, FR8）: TS-6 と TS-7 が deny になる。修正前は allow。
- [ ] AC-4（FR3, FR7, FR8）: TS-8 と TS-9 が理由 ID `args-json-unrestorable` の ask になる。
  修正前は TS-8 が allow、TS-9 が deny。
- [ ] AC-5（FR4, FR8）: TS-10 と TS-11 が deny になる。修正前は allow。
- [ ] AC-6（FR6, FR8）: TS-12 が allow になる。TS-12 のラベルと、3 箇所の対象外の記述（この SPEC、
  `_mcp_bridge_args_json_chunks()` の docstring、`extract_shell_payload_anchored()` の docstring）が、
  同じ範囲で O2 (8) を述べる。新しい固定を含めて TestDocstring が通る。
- [ ] AC-7（FR3, FR4, FR9）: TS-13 から TS-15 が通る。
- [ ] AC-8（FR5, FR9, NFR4）: TS-16 が通る。既存のアンカーのテスト
  （`tests/test_destructive_guard_args_json.py` の 718-735 行目）が変更なしで通る。
- [ ] AC-9（FR1, FR9）: TS-17 が通る。
- [ ] AC-10（FR11）: サブテスト 'equals form with a destination' が通る。
- [ ] AC-11（NFR2, NFR3）: ランナーが通る。既存ケースの削除・変更がない。
  `tests.test_destructive_guard_args_json` と `unittest discover -s tests` が通る。

## Technical Requirements

### Functional Requirements

- **FR1: 値の語が 1 語に確定するときだけ notion ペアを除外する**
  `_args_json_notion_pair()` が文を除外するのは、現在の条件を満たし、さらに `--format`、`--session`、
  `--args-json` の値の語がすべて「1 語確定」であるときに限る。
    - 「1 語確定」の語とは、Bash が常にちょうど 1 つの引数にする語。静的な語であるか、語の中の
      静的でない要素がすべてダブルクォートの中にあるか ANSI-C クォート・ロケールクォートであり、かつ
      ダブルクォートの中の要素に `@` 形式の配列展開（`$@`、`${name[@]...}`、`${!prefix@}`）が無いもの。
    - 次の要素を含む語は 1 語確定ではない（安全側）: クォートされていないパラメータ展開・コマンド置換・
      算術展開、クォートされていないバッククォート、クォートされていないブレース展開・グロブ・拡張グロブ・
      チルダの形、プロセス置換、`@` 形式。
    - 除外されない文は通常のフラグ読み取りに進む。
    - シングルクォートの値、ANSI-C の値（`_decode_ansi_c()` が復号できないものを含む）、
      `"$(cat comment.json)"` や `"$SID"` のようなクォートされた展開は、除外の対象のまま。
    - シェル構文の誤りはここで判定しない。この判定を行う場所はこの述語 1 箇所だけ。
    - `_single_quote_skip_spans()` の生文字列のスキップは条件を変えない（W4 がすでに全語の静的を求めている）。
- **FR2: クォートされていない `\=` を `=` の区切りとして扱う**
  `_flag_equals_prefix_name()` は、Bash のクォート除去と同じく、クォートされていないバックスラッシュで
  エスケープされた `=` を、復元したフラグ語の最初の `=` として扱う。その前の名前部分が値を取る既知の
  名前で、値部分が静的でないときは、その値だけを読み飛ばしてフラグ読み取りを続ける。
    - 例: `--mcp\="$S"` と `--session\="$SID"` は `--mcp="$S"` と同じように読む。
    - ダブルクォートの中の `\=` は現在どおりバックスラッシュを残す。`"--mcp\=$S"` の名前は `mcp\` で、
      nothing-to-do のまま。
- **FR3: 行継続が続く `$`**
  `--args-json` の語の読み取り（`_read_static_word()`、および `_read_double_quoted()` によるダブルクォートの
  読み取りを含む）では、`$` を、任意個の行継続（バックスラッシュと改行）の後の最初の文字で判定する。
    - その文字が展開を開始できる文字なら、その語は Unrestorable になり、`args-json-unrestorable` の ask
      （batch では deny）を保持する。
    - ダブルクォートの中で展開を開始できる文字は、名前の文字、数字、特殊パラメータの文字、`{`、`(`、`[`。
      クォートの外では `'` と `"` も含む（行継続で分割された `$'` / `$"` の開始）。
    - 語が FR6 (1) の別の要素も含むときは、現在どおり Not static のまま。
    - 行継続の後の文字が展開を開始できないときは、`$` はリテラルの `$` で、行継続は現在どおり消える。
    - マスク停止の読み取り（`_read_word_as_written()`）は `_read_double_quoted()` を共有する。
      マスク停止の読み取りにとって、この形の語は判定不能（唯一の安全側の結果）。
    - `$` の後に行継続が無い語は、現在とまったく同じに読む。
- **FR4: `$` の後の非 ASCII 文字はリテラル**
  `_read_double_quoted()` と `_read_static_word()` のクォート外の分岐では、非 ASCII 文字が続く `$` を
  リテラルの `$` とする。`$€` を含む静的な値は、読み飛ばされずに復元・検査される。共有ヘルパーが同じ規則を
  マスク停止の読み取りにも適用する。
- **FR5: アンカーの線形な検索**
  `_queue_args_json_chunks()` は、候補の本文かトップレベルの `command` 文字列を持つ値に対してだけ、
  アンカーのトークン位置を求める。1 回の呼び出しにつき最大 1 回作る TOKENS のスパンから位置への対応表を使い、
  スパンを持たない語は `_token_index()` で求める。キューに積むチャンクとその起点の位置（アンカー、文の位置、
  トークンの位置、序数）は現在と同一。
- **FR6: 値の語の語数のずれを対象外として記録する（O2 (8)）**
  一般のフラグ読み取りは、語を書かれたとおりに読み続ける。`--mcp`、`--tool`、`--format`、`--session` の値、
  または `=` に続く値は、展開されて 1 語以外の語数になることがある。そのうち、mcp-bridge がフラグと値を読む
  位置をずらし、後続の `--args-json` を隠すものを、新しい O2 の項目 (8) として記録する。
    - 記録する場所は O2 (2) の隣で、次の 3 箇所に同じ範囲で書く: この SPEC の Security Considerations、
      `_mcp_bridge_args_json_chunks()` の docstring の対象外の一覧、`extract_shell_payload_anchored()` の
      対象外の宣言。
    - この形は、復号した値の検査を行わないまま、現在の判定を保つ。ask には送らない。
    - 新しい文言には、TestDocstring が Out of scope の節で禁じる語句を使わない: destination、ANSI-C、
      quoted flag、`=` form、single-dash、single dash、positional、`--`、repeated、canonical flag sequence。
- **FR7: FR11 を改め、行継続の形を明記する**
  この SPEC で、前身 feature の FR11 の定義を改め、FR3 の形を明示する。その形は「`$`、1 つ以上の行継続、
  展開を開始する文字」の並び。
    - 同じ改訂を、`_read_static_word()` の docstring の WORD_UNRESTORABLE の段落、
      `_mcp_bridge_args_json_chunks()` の docstring の手順 4、`ARGS_JSON_UNRESTORABLE_ASK` のコメントにも入れる。
    - 理由 ID `args-json-unrestorable` と理由の文言は変えない。
- **FR8: ランナーのケース**
  ランナー水準の TS-1 から TS-12 を `em-workflow/hooks/tests/destructive-guard-cases.json` に追加する。
    - 各ケースのラベルに、指摘 ID か O2 (8) を書く。
    - ask のケースには `{"rule": "args-json-unrestorable"}` を付ける。
    - ケースは修正の前に追加し、修正前のフックが各シナリオの「修正前」の判定を返すことを確かめる。
    - 既存のケースは削除も変更もしない。
- **FR9: ユニットテスト**
  ユニット水準の TS-13 から TS-18 を `tests/test_destructive_guard_args_json.py` に追加する。O2 (8) の文言を
  固定する TestDocstring のピンを追加する。既存のテストは変更なしで通り続ける（469-491 行目の notion の
  テスト、718-735 行目のアンカーのテスト、TestStructure を含む）。
- **FR10: docstring とコメント**
  次を新しい振る舞いに合わせて更新する。TestDocstring が固定している O1 / O2 の語句はすべて残す。
    - `_args_json_notion_pair()` の docstring（"whatever it holds" の文言）
    - `_flag_equals_prefix_name()` の docstring（"followed directly by an unquoted `=`" の文言）
    - `_read_double_quoted()` と `_read_static_word()` の docstring
    - `_mcp_bridge_args_json_chunks()` の docstring の手順 2
    - `_MCP_RUN_VALUE_FLAGS` のコメント
- **FR11: 3340375b4b50c4b0 の確認**
  `tests/test_destructive_guard_args_json.py:610` のサブテスト 'equals form with a destination' は、
  `test_a_destination_that_is_not_static_is_inspected` の中で、すでに KIND_INSPECTED を期待している。
  これが通ることを確かめる。失敗したときだけ変更する。

### Non-Functional Requirements

- **NFR1 - Performance:** 1 回のフック評価は、`hooks.json` の destructive-guard のタイムアウト（10 秒）と、
  ランナーの `GUARD_TIMEOUT_SECONDS` に収まる。FR5 により、`--args-json` の手順のアンカー検索は、
  値の数とトークン数の和に対して線形になる。
- **NFR2 - Fail-closed:** 既存の deny / ask の判定は allow にならない。allow が ask になるのは FR3 の形
  （FR7 で改めた FR11）だけ。deny が ask になるのも FR3 の形だけで、TS-9 に示すとおり。既存のランナーの
  ケースは、判定も理由 ID も変わらない。
- **NFR3 - Test procedure:** 同じ変更の中で、次の 3 つを実行する（`.claude/rules/hook-tests.md`）。
  新しいランナーのケースは修正前に追加し、修正前の判定を確かめる。
    - `python3 em-workflow/hooks/tests/run-destructive-guard.py`
    - `python3 -m unittest tests.test_destructive_guard_args_json`
    - `python3 -m unittest discover -s tests`
- **NFR4 - No load-based testing:** FR5 は構造で確かめる。例: 検索の回数を数える、モックやスパイで対応表の
  作成が 1 回であることを示す。数千個の値に対する実時間の計測や、CPU に負荷をかける再現では確かめない。
- **NFR5 - Version:** `plugin.json` と `marketplace.json` の em-workflow の version は変えない。
  GitHub Actions が patch を上げる。
- **NFR6 - Maintainability:** FR1 の 1 語確定の判定は 1 つのヘルパーにする。`statements()` は
  `_queue_args_json_chunks()` の 1 回の呼び出しを保ち、ほかの `--args-json` の処理を持たない。
  TestStructure は変更なしで通る。

## Implementation Approach

### Architecture

destructive-guard フック（`em-workflow/hooks/destructive-guard.py`）の `mcp-bridge run --args-json` 検査の
読み取り部分を変更する。新しいモジュールは追加しない。

**変更する関数と要件の対応:**
```
_args_json_notion_pair()          FR1 （1 語確定の判定ヘルパーを呼ぶ）
1 語確定の判定ヘルパー（新規）    FR1, NFR6
_flag_equals_prefix_name()        FR2
_read_static_word()               FR3, FR4, FR7
_read_double_quoted()             FR3, FR4
_read_word_as_written()           FR3, FR4 （_read_double_quoted() の共有による）
_queue_args_json_chunks()         FR5
_mcp_bridge_args_json_chunks()    FR6, FR7, FR10 （docstring）
extract_shell_payload_anchored()  FR6 （対象外の宣言）
ARGS_JSON_UNRESTORABLE_ASK        FR7 （コメント）
_MCP_RUN_VALUE_FLAGS              FR10 （コメント）
_single_quote_skip_spans()        変更しない
statements()                      変更しない（NFR6）
```

### Data Flow

該当なし（判定の流れは変えず、上記の読み取りの規則だけを変える）。

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- 前身 feature `mcp-bridge-args-json-exec-guard`: FR11（Unrestorable の定義）と O1 / O2 の対象外の一覧。
  この feature は FR11 を FR7 のとおり改め、O2 に (8) を加える。

**External Dependencies:**
- なし。

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # FR1-FR7, FR10
└── tests/
    └── destructive-guard-cases.json     # FR8（TS-1 から TS-12）
tests/
└── test_destructive_guard_args_json.py  # FR9（TS-13 から TS-18、O2 (8) のピン）、FR11
```

## Declared Change Set

上記の feature 固有のパスは、手で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する
（`references/phases/create-plan-phase.md`）。

すべての SPEC は、既定で、feature 固有のパスに加えて次の 2 つのワークフロー生成物を宣言する。

- `feature-docs/args-json-quoting-bypass/**`
- `test-docs/args-json-quoting-bypass/**`

`feature-docs/args-json-quoting-bypass/**` は、`REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、
`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、
design step の成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節は
それらを参照するだけで、規則を再掲しない。

`test-docs/args-json-quoting-bypass/**` は、タスクごとのテスト記録
`test-docs/args-json-quoting-bypass/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。
この節はそれを参照するだけで、規則を再掲しない。

この 2 つの既定の項目は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことを外したとは
みなさない。外すのは明示的な絞り込みに限る。

この宣言は上位集合の表明である。検証時に観測した実際の変更集合は、宣言した集合に含まれていればよく、
一致する必要はない。implement タスクを生まない feature は `test-docs/args-json-quoting-bypass/` を
生成しないが、その場合も宣言した `test-docs/args-json-quoting-bypass/**` は正しい。宣言したパスが実在しない
ことは違反ではない。

## Test Scenarios

### Integration Tests（ランナーのケース、`em-workflow/hooks/tests/destructive-guard-cases.json`）

各ケースの「修正前」は、FR8 のとおり修正前のフックで確かめる判定。

- [ ] TS-1: 期待 deny（修正前 allow）。指摘 3f7145c6c8c0b26a。
  ```
  mcp-bridge run --mcp notion --tool notion-create-comment --format ${REVIEW_UNSET:-json --mcp desktop-commander --tool start_process} --args-json '{"command":"git branch -D example"}'
  ```
- [ ] TS-2: 期待 deny（修正前 allow）。指摘 3f7145c6c8c0b26a（`--session` の値）。
  ```
  mcp-bridge run --mcp notion --tool notion-create-comment --session ${REVIEW_UNSET:-s --mcp desktop-commander --tool start_process} --args-json '{"command":"git branch -D example"}'
  ```
- [ ] TS-3: 期待 deny（修正前 allow）。指摘 3f7145c6c8c0b26a（クォートされた `@` の配列展開）。
  ```
  A=(json --mcp desktop-commander --tool start_process); mcp-bridge run --mcp notion --tool notion-create-comment --format "${A[@]}" --args-json '{"command":"git branch -D example"}'
  ```
- [ ] TS-4: 期待 deny（修正前 allow）。指摘 3f7145c6c8c0b26a（ブレース展開）。
  ```
  mcp-bridge run --mcp notion --tool notion-create-comment --format {json,--mcp=desktop-commander} --args-json '{"command":"git branch -D example"}'
  ```
- [ ] TS-5: 期待 allow（修正前 allow）。FR1 はクォートされた展開を除外の対象に残す。
  ```
  mcp-bridge run --mcp notion --tool notion-create-comment --session "$SID" --args-json '{"body":"$(git branch -D example) と記載する"}'
  ```
- [ ] TS-6: 期待 deny（修正前 allow）。指摘 f16e5bb8d5da2621。
  ```
  mcp-bridge run --mcp\="$S" --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'
  ```
- [ ] TS-7: 期待 deny（修正前 allow）。指摘 f16e5bb8d5da2621 / 63d94a7bddc5d673（`--session`）。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --session\="$SID" --args-json '{"command":"git branch -D example"}'
  ```
- [ ] TS-8: 期待 ask、`{"rule": "args-json-unrestorable"}`（修正前 allow）。指摘 dc2fdf65ce30d198。
  `<backslash-newline>` は、ダブルクォートの値の中で `$` と `DEST` の間に置くバックスラッシュと改行を表す。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"printf $<backslash-newline>DEST\"}"
  ```
- [ ] TS-9: 期待 ask、`{"rule": "args-json-unrestorable"}`（修正前 deny）。指摘 dc2fdf65ce30d198（deny が ask に
  なる）。`<backslash-newline>` は、`$` と `X` の間に置くバックスラッシュと改行を表す。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"git branch -D $<backslash-newline>X\"}"
  ```
- [ ] TS-10: 期待 deny（修正前 allow）。指摘 f35ed060564bcf20（ダブルクォート）。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"git branch -D example\",\"note\":\"5 $€\"}"
  ```
- [ ] TS-11: 期待 deny（修正前 allow）。指摘 f35ed060564bcf20（クォート外）。
  ```
  mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","note":"'$€'"}'
  ```
- [ ] TS-12: 期待 allow（修正前 allow）。O2 (8) の対象外: 値の語の展開がフラグと値の対応をずらす形。
  ```
  mcp-bridge run --mcp desktop-commander --format ${REVIEW_UNSET:-json --tool} start_process --args-json '{"command":"git branch -D example"}'
  ```

### Unit Tests（`tests/test_destructive_guard_args_json.py`）

- [ ] TS-13: `_read_static_word()` - ダブルクォートの値で `$`、行継続、`DEST` の並びは WORD_UNRESTORABLE。
  行継続が 2 つのもの、行継続の後が `{` のものも WORD_UNRESTORABLE。クォート外の「`$`、行継続、`X`」と
  「`$`、行継続、`'...'`」も WORD_UNRESTORABLE。さらに `$Y` を含む語は WORD_NOT_STATIC。「`$`、行継続、
  空白または閉じクォート」は、行継続を除いたリテラルの `$` として復元する。
- [ ] TS-14: `_read_word_as_written()` - ダブルクォートの語で `$`、行継続、名前の並びは None（判定不能）を返す。
  この形を含まない語は現在どおり読む。
- [ ] TS-15: ダブルクォートの `"5 $€"` は `5 $€`（WORD_STATIC）に復元する。同じ値を `\$€` で書いたものも同じ
  文字列に復元する。
- [ ] TS-16: 多数の `--args-json '{}'` の値と、command 文字列を持つ値 1 つを含む文で、command 文字列を持つ値の
  アンカーが現在と等しく、トークンの検索が値ごとに繰り返されない。時間の計測ではなく、スパイかモックで示す。
- [ ] TS-17: TestFlagReading - notion ペアで `--format` / `--session` / `--args-json` の値がクォートされていない
  展開、ブレースの形、`"$@"`、`"${A[@]}"` のものは KIND_INSPECTED。notion ペアで `--session "$SID"`、
  `--args-json "$(cat comment.json)"`、ANSI-C の値のものは KIND_NOTHING で、Unrestorable のフラグを持たない。
- [ ] TS-18: TestFlagReading - `--mcp\="$S"` と `--session\="$SID"` に静的な `--args-json` が続くものは、
  復号した command を伴う KIND_INSPECTED。`"--mcp\=$S"` は KIND_NOTHING のまま。

### E2E Tests

**Existing E2E tests**: なし
**Run command**: 検出なし
- [ ] Existing E2E tests pass without regression

### Edge Cases

上記の TS-5（除外の対象に残る形）、TS-9（deny が ask になる形）、TS-12（対象外の形）が境界を扱う。

### Performance Tests

TS-16 で FR5 を構造的に確かめる（NFR4）。負荷試験・ストレス試験は行わない。

## Security Considerations

- **Input Validation:** FR1 から FR4 のとおり、`--args-json` の値と notion ペアの値の語を、Bash の語分割・
  クォート除去・展開と同じ規則で読む。
- **Fail-closed:** NFR2 のとおり。判定が変わるのは、TS-1 から TS-12 に示した形に限る。

### 前身 feature の FR11 の改訂（FR7）

前身 feature の FR11 が定める Unrestorable の形に、次の形を明示して加える: `$`、1 つ以上の行継続
（バックスラッシュと改行）、展開を開始する文字、の並び。理由 ID `args-json-unrestorable` と理由の文言は
変えない。前身 feature の SPEC（`feature-docs/mcp-bridge-args-json-exec-guard/SPEC.md`）は編集しない。

### 対象外（O2 への追加）

O2 (2) の隣に次の項目を置く。

- O2 (8): 値の語の展開による語数のずれ。mcp、tool、format、session の各フラグの値の語、またはフラグ語に
  `=` で続けた値の部分が、Bash の展開で 1 語以外の語数になり、mcp-bridge がフラグと値を読む位置がずれて、
  後続の args-json の値が隠れる形。一般のフラグ読み取りは語を書かれたとおりに読む。この形は、復号した値の
  検査を行わないまま、現在の判定を保つ。ask には送らない。

### この feature で扱わない指摘

- round 4 の medium のうち、次は対象外: 03086290fa444588、ababcd7ad8a0073c、e2933b56bc73a10c、
  53104f98739b5681、328945641695048d、abc1993a82f81567（二次の検索の重複で、FR5 が扱う）。
- フラグ位置の語が FR3 の形を含む場合は、既存の FR11 のフラグ語の振る舞い（値を検査せずに読み取りを終え、
  ask を保持する）を保つ。その結果 deny が ask になりうる点は、対象外の 328945641695048d に属する。

## Error Handling

### Error Codes

| Code | Description | Verdict | Reason text |
|------|-------------|---------|-------------|
| `args-json-unrestorable` | FR11（FR7 で改訂）の形を含む `--args-json` の値 | ask（batch では deny） | 変更しない |

### Error Flow

```
FR3 の形を検出 → 語を Unrestorable とする → args-json-unrestorable の ask を保持 → batch では deny に降格
```

## Performance Optimization

### Performance Goals
- 1 回のフック評価: 10 秒以内（`hooks.json` のタイムアウト、ランナーの `GUARD_TIMEOUT_SECONDS`）

### Optimization Strategies
- アンカー検索（FR5）: 対象の値に限って求め、TOKENS のスパンから位置への対応表を 1 回の呼び出しにつき最大 1 回作る。

### Caching Strategy
- 該当なし。

## Assumptions

- **A1（影響: 高）:** 1 語確定は FR1 の定義による。1 語以外になりうるものとして扱うのは、クォートされていない
  展開、クォートされていないブレース・グロブ・拡張グロブ・チルダの形、プロセス置換、`@` 形式の配列だけ。
  チルダとプロセス置換は安全側として含める。
- **A2（影響: 中）:** 使われている正規の notion の呼び出しは、`--format` / `--session` / `--args-json` の値に
  クォートされていない展開を置かない。置いた場合は復号・検査され、破壊的な内容のときだけ deny になる。
- **A3（影響: 低）:** Bash は C または UTF-8 のロケールで動き、`$` の後の非 ASCII のバイトは名前を開始しない（FR4）。
- **A4（影響: 低）:** mcp-bridge は、`--mcp` / `--tool` が複数回現れたとき最後のものを使う
  （3f7145c6c8c0b26a の再現手順のとおり）。
- **A5（影響: 中）:** requirement.scope.medium-findings の回答は listed_mediums（batch-codex-consultation）。
  2 件の high（medium の対 63d94a7bddc5d673 を含む）に加えて、dc2fdf65ce30d198、f35ed060564bcf20、
  0379cf2eb7ad4e92 / 9981fd673b28e7e4 を扱い、3340375b4b50c4b0 を確認する。round 4 の他の medium は対象外
  （「この feature で扱わない指摘」のとおり）。
- **A6（影響: 中）:** security.value-word-arity の回答は record_out_of_scope（batch-codex-consultation）。
  一般のフラグ読み取りは語を書かれたとおりに読み、値の語の展開による語数のずれは O2 (2) の隣に O2 (8) として
  記録する（FR6）。シナリオ 1 は FR1 により引き続き deny になる。
- **A7（影響: 中）:** security.dollar-line-continuation の回答は ask_unrestorable（batch-codex-consultation）。
  FR3 の形は語を Unrestorable にし、FR11 を改めてそれを明記する（FR7）。既存の deny / ask は allow にならない。
- **A8（影響: 低）:** design-step.decision の回答は skip（batch-decision-table）。
- **A9（影響: 低）:** FR11 の改訂は、この feature の SPEC とコードの docstring・コメントに書く。前身 feature の
  SPEC（`feature-docs/mcp-bridge-args-json-exec-guard/SPEC.md`）は編集しない。理由 ID
  `args-json-unrestorable` と理由の文言は変えない。
- **A10（影響: 低）:** FR3 の形を含むフラグ位置の語は、既存の FR11 のフラグ語の振る舞いを保つ（値を検査せずに
  読み取りを終え、ask を保持する）。その結果の deny から ask への変化の可能性は、対象外の medium
  328945641695048d に属する。

## Success Criteria

- [ ] AC-1 から AC-11 をすべて満たす
- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Performance meets specified goals
- [ ] Security requirements are satisfied
- [ ] Documentation is complete（FR6、FR7、FR10 の docstring・コメント）
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし。

## References

- 前身 feature の SPEC: `feature-docs/mcp-bridge-args-json-exec-guard/SPEC.md`
- フックのテストの規則: `.claude/rules/hook-tests.md`
