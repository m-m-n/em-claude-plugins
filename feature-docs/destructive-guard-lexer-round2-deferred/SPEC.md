# Feature: destructive-guard-lexer-round2-deferred

## Overview

`em-workflow/hooks/destructive-guard.py` の字句解析で、feature destructive-guard-lexer-round2-residuals の review round 2 で deferred になった 8 件を扱う。bash 5.3 が実行する破壊的な行を、フックが本文・コメント・展開として隠して allow を返す経路をなくす。要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- 次の 8 件を扱う。
    - high 5 件: 5753be9288beab27、52bfa0f59d1ea852、e959ba60bde865a4、e25427e2a8b1dddf、2b52be5874de85f4
    - medium 3 件: aa735aa95be36542、1fcae1f76f2a20f0、c8c16caba82d6238（一部、A3）
- bash 5.3 が実行する破壊的な行を、フックが本文・コメント・展開として隠して allow を返す経路をなくす。

## Technical Requirements

再現入力は cases.json の JSON 文字列表記で書く。「deny になる」は、通常実行と CLAUDE_BATCH=1 の両方で deny になることを指す。

### Functional Requirements

- **FR1:** 行をまたいで閉じる配列添字の後のヒアドキュメントで後続行を隠さない（5753be9288beab27）。
    - 行をまたいで `]` が閉じる代入語の添字（`a[1\n]=x` など）の後ろにある `<<` は、bash 5.3 と同じく本物のヒアドキュメント演算子として読む。本文の `'` / `"` / `${` が閉じ行と後続行を領域に取り込まない。
    - deny になる形:
        - `a[1\n]=x\ncat <<E\n'\nE\nrm -rf /home/sakura/valuable\n'`
        - 上の `\"` 版と `${` 版（閉じは `}`）
        - `a[1\n]=x; cat <<E\n'\nE\nrm -rf /home/sakura/valuable\n'`
        - `a[$(echo 1\n)]=x\ncat <<E\n'\nE\nrm -rf /home/sakura/valuable\n'`
        - `a[b[1\n]]=x\ncat <<E\n'\nE\nrm -rf /home/sakura/valuable\n'`
    - 該当箇所: subscript フレーム（2341-2393）、`word_transition()` の添字判定（1542-1572）。
- **FR2:** 読めない区切り語の後ろ（tail）で `${` / `$((` / `$[` / `((` と case のパターン状態を開かない（52bfa0f59d1ea852）。
    - 区切り語を読めない `<<`（tail source）より後ろでは、`${`、`$((`、`$[`、コマンド位置の `((`、`case ... in` のパターン状態を開かない。引用・コメント・`<<` 演算子を開かないという現行の扱いと同じにする。
    - case のパターン状態は後段の `_shape_leading()`（6056 付近）でも保持されるため、tail より後ろではそこでも case のパターン状態に入らない。
    - deny になる形:
        - `cat <<E${x}\n${\nE${x}\nrm -rf /home/sakura/valuable\n}`
        - 上の `${` を `$((` / `$[` / `((` / `case x in` に替えた形（閉じはそれぞれ `))` / `]` / `))` / `esac`）
    - 該当箇所: `dollar()`（1610-1631。`$((` / `${` / `$[` に tail_source の判定が無い）、コマンド位置の `((`（1969-1989）、`word_transition()` の `case`（1516-1518）。
- **FR3:** 区切り語の終わりと行の境界を `\n` だけにする（e959ba60bde865a4）。
    - ヒアドキュメントの区切り語はメタ文字（空白・タブ・`\n`・`;|&()<>`）だけで終わる。`\r`・`\x0b`・`\x0c`・`\x1c`-`\x1e`・`\x85`・` `・` ` は区切り語の文字に含める。
    - 本文の開始行と閉じ行の索引（`_LexLines`）は `\n` だけで行を分ける。
    - deny になる形:
        - `cat <<EOF\r; rm -rf /home/sakura/valuable\nEOF` と、その `\r` を `\x0b` / ` ` に替えた形
        - `cat <<END \r; rm -rf /home/sakura/valuable\nEND`
        - `cat <<END\nx\rEND\n# $(rm -rf /home/sakura/valuable)\nEND`
        - `cat <<E\rX\nE\n# $(rm -rf /home/sakura/valuable)\nE\rX`
        - `cat <<EOF\r\nx\r\nEOF\r\nrm -rf /home/sakura/valuable\nEOF`
    - 該当箇所: `_LexLines`（830-873、847 の splitlines）、`_LEX_LINE_BREAKS` / `_LEX_LINE_BREAK`（887-890）、`_LEX_DELIM_RUN`（895-897）、`_LEX_DELIM_DQ_SPECIAL`（899-901）、`_read_heredoc_delimiter()`（996-1084）。
- **FR4:** 識別子の途中の行継続を取り除いてから添字の始まりを判定する（e25427e2a8b1dddf）。
    - 代入を受け付ける位置の語では、`\<改行>` の組を取り除いた文字列で `識別子[` を判定する。`a\<改行>[1<<2]=x` の `<<` は演算子にしない。
    - 閉じが無い場合の扱いは現行の `LexUnmatchedSubscript` のままにする。
    - deny になる形:
        - `a\\\n[1<<2]=x\nrm -rf /home/sakura/valuable\n2]=x`
        - `ab\\\nc[1<<2]=x\nrm -rf /home/sakura/valuable\n2]=x`
    - `]` の直前・`=` の直前の継続の形もケースで固定する。添字判定から漏れた形が語全体の区切り語と組み合わさると allow になることを、ケースのラベルに書く。
    - 該当箇所: `_LEX_SUBSCRIPTED_NAME`（916）、`word_transition()` の sub_name（1542-1572）、行継続の処理（1829-1839）。
- **FR5:** 引用なしの区切り語の本文で `\<改行>` の連結を閉じ行の判定に反映する（2b52be5874de85f4）。
    - 引用を含まない区切り語の演算子（QUOTED が偽）では、奇数個のバックスラッシュで終わる行の次の行を閉じ行の候補から外す。`\<改行>` を連結した論理行の先頭だけを閉じ行として比べる。
    - `<<-` では連結後に先頭のタブを除いて比べる。
    - 引用した区切り語の読みは変えない。
    - deny になる形:
        - `cat <<END\nfoo\\\nEND\n# $(rm -rf /home/sakura/valuable)\nEND`
        - `cat <<-END\nfoo\\\n\tEND\n# $(rm -rf /home/sakura/valuable)\nEND`
    - 該当箇所: `_LexLines.close_lines()`（854-873）、その参照箇所（1787）。
- **FR6:** `\r` を空白として扱わない（aa735aa95be36542）。
    - 字句解析の空白は空白とタブだけにする。`\r` は語の文字として読む。
    - `_LEX_WS`、`_LEX_WORD_RUN`、`_LEX_WORD_END`、`_LEX_SUBSCRIPT_BOUND_SPECIAL`、1816 行の空白判定、マスク後の文字列を読む shlex の whitespace（`_tokenize_marked()`、2906 行）を揃える。
    - `_tokenize_marked()` は通常実行と batch の両方で `\r` を語の区切りとして残さない。
    - deny になる形: `echo x\r# ; rm -rf /home/sakura/valuable`
- **FR7:** bash 5.3 の `${ cmd; }` / `${| cmd; }` の中身をコマンドとして検査する（1fcae1f76f2a20f0）。
    - `${` の直後が空白・タブ・改行・`|` のときは、中身をコマンドとして読む命令置換として開く。
    - 閉じは、予約語が認められる位置（`;`・`&`・改行の後）にある `}` とする。
    - トップレベル、二重引用符の中、引用なしの区切り語の本文（btop）で同じに扱う。
    - 本文の抽出（3938-3995 付近）は閉じていない `${ ` / `${|` の本文も対象にし、`${|` では `|` の後ろから本文として読む。
    - deny になる形:
        - `echo ${ rm -rf /home/sakura/valuable; }`
        - `echo ${|rm -rf /home/sakura/valuable; }`
        - `echo ${\nrm -rf /home/sakura/valuable\n}`
        - `cat <<E\n${ rm -rf /home/sakura/valuable; }\nE`
    - 該当箇所: `dollar()` の `${`（1620-1625）、param フレーム（2209-2238）、dq フレーム（2168-2185）、btop（2441-2455）。
- **FR8:** tail で開いてよい領域の判定を一か所にまとめる（c8c16caba82d6238 の一部）。
    - tail_start / tail_source から後ろで、ある開き記号（引用、`$'`、`$"`、`${`、`$((`、`$[`、`((`、コメント、`<<` 演算子、添字、case のパターン状態）を開いてよいかの判定を、1 つの関数で行う。
    - 現行で個別の `if state.tail_source is None` / `state.tail_start` 判定が散っている各箇所（1636、1641、1843、1858、1874、1933、1959、2033、2053、2078、2089、2098、2106、2159、2222、2228、2287、2293、2323、2329、2377、2383、2423、2429 など）は、その関数を使う。
    - `_lex_pass` を小さな関数に分ける作業はこの機能に含めない（A3）。
- **FR9:** 直す前に cases.json へ deny ケースを足す。
    - FR1〜FR7 の各再現入力を `["deny", ラベル, コマンド]` の形で `em-workflow/hooks/tests/destructive-guard-cases.json` の末尾（既存の最後の項目の後ろ）に足す。
    - そのコミットを、対応する修正のコミットより前に置く。
    - 各ラベルは該当する stable_id で始める。
- **FR10:** 既存ケースを消さない。
    - cases.json の既存の deny / ask ケースを 1 件も消さず、並び順も変えない。
    - cases[574:604]、cases[604:627]、ROUND2_BASE_CASE_COUNT = 627、SUBSCRIPT_CASE_FLOOR = 627 など、位置で固定している既存テストはそのまま通る。
- **FR11:** 字句解析の一致テストに固定期待を足す。
    - `tests/test_destructive_guard_lexer_agreement.py` に、FR1〜FR7 の各形の字句地図（heredocs、regions、tail_start）と通常実行・batch の判定を固定するテストを足す。
    - 追加したケースの塊が既存の項目より後ろにあることを固定するテストも足す。

### Non-Functional Requirements

- **NFR1 - Performance:** `lex_shell()` の仕事量が入力長に比例する。FR1〜FR7 の形を k 個 / 2k 個並べた入力と既存の線形性テストの形で、work が `LEX_WORK_FACTOR` × 入力長 + 1024 以下に収まる。2 倍の長さで work が 2.5 倍 + 100 以下になる。
- **NFR2 - Performance:** 約 60KB の入力でもフック 1 回の評価が、hooks.json の timeout と同じ 10 秒以内に終わる。入れ子の `${ ` を 60KB 並べた形（`TestUnclosedOpeners.bulk("${")`）を含む。
- **NFR3 - Security:** 作業上限を超えた場合は従来どおり scan-budget の ask（batch では deny）にし、allow にしない。
- **NFR4 - Determinism:** 同じ入力は同じ字句地図と同じ判定を返す。
- **NFR5 - Dependencies:** フックとテストは標準ライブラリだけを使う。字句解析はファイルを読まず、何も評価しない（TestModuleContract）。
- **NFR6 - Compatibility:** 読みは bash 5.3 の構文に合わせる。bash と一致させられない形は、後続行を検査から外さない側に倒す。
- **NFR7 - Compatibility:** cases.json の既存 allow ケースは allow のままにする。

## Implementation Approach

### Architecture

変更は `em-workflow/hooks/destructive-guard.py` の字句解析に閉じる。各 FR の該当箇所は Functional Requirements に記した（行番号は現行の main のもの、A1）。

- 区切り語と行の境界: FR3（`_LexLines`、`_LEX_DELIM_*`、`_read_heredoc_delimiter()`）、FR5（`_LexLines.close_lines()`）
- 添字: FR1（subscript フレーム、`word_transition()`）、FR4（`_LEX_SUBSCRIPTED_NAME`、行継続の処理）
- tail の扱い: FR2（`dollar()`、コマンド位置の `((`、`case`、`_shape_leading()`）、FR8（判定を 1 つの関数にまとめる）
- 空白: FR6（`_LEX_WS` ほか、`_tokenize_marked()`）
- `${ ` / `${|`: FR7（`dollar()`、param / dq フレーム、btop、本文の抽出）

### Implementation Order

- FR9 の deny ケースを足すコミットを、対応する修正のコミットより前に置く。
- F1（FR1）は再現形を deny ケースとして必ず足し、deny にならない形があるときだけコードを直す（A5）。

### Dependencies

**Internal Dependencies:**
- 対象のコードは main（PR #105 の destructive-guard-lexer-round2-residuals と destructive-guard-heredoc-syntax-error のマージ後）（A1）。

**External Dependencies:**
- Python 標準ライブラリだけを使う（NFR5）。
- bash の構文の基準は bash 5.3（5.3.9）（A2）。

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # 字句解析の修正（FR1〜FR8）
└── tests/
    └── destructive-guard-cases.json     # deny ケースの追加（FR9、FR10）
tests/
└── test_destructive_guard_lexer_agreement.py  # 固定期待の追加（FR11）
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、既定で上記のフィーチャー固有のパスに加えて、ワークフローが生成する次の 2 つを宣言に含める。

- `feature-docs/destructive-guard-lexer-round2-deferred/**`
- `test-docs/destructive-guard-lexer-round2-deferred/**`

`feature-docs/destructive-guard-lexer-round2-deferred/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-lexer-round2-deferred/**` に含まれるもの: `test-docs/destructive-guard-lexer-round2-deferred/{T}.tests.yaml`（タスクごとのテスト記録）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

この 2 つの既定のメンバーは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とは見なさない。除外は意図的な絞り込みである。

この宣言はスーパーセット（superset）の主張であり、検証時に観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致は求めない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/destructive-guard-lexer-round2-deferred/` ディレクトリを生成しないが、宣言された `test-docs/destructive-guard-lexer-round2-deferred/**` は依然として正しい。生成されないパスが宣言されていても違反にはならない。

## Test Scenarios

### Unit Tests

cases.json（`python3 em-workflow/hooks/tests/run-destructive-guard.py`）:
- [ ] TS1: FR1 の 6 形（`'` 版・`"` 版・`${` 版、`; cat` 版、`a[$(echo 1\n)]` 版、`a[b[1\n]]` 版）が deny。（FR1、FR9）
- [ ] TS2: FR2 の 5 形（`${`、`$((`、`$[`、`((`、`case x in`）が deny。（FR2、FR9）
- [ ] TS3: FR3 の形（`\r` / `\x0b` / ` ` の区切り語、`END \r`、本文中の `x\rEND`、`E\rX`、CRLF 行末）が deny。（FR3、FR9）
- [ ] TS4: FR4 の 2 形と、`]` の直前・`=` の直前に継続を置いた形が deny。（FR4、FR9）
- [ ] TS5: FR5 の `<<` 版と `<<-` 版が deny。（FR5、FR9）
- [ ] TS6: `echo x\r# ; rm -rf /home/sakura/valuable` が deny。（FR6、FR9）
- [ ] TS7: FR7 の 4 形（`${ `、`${|`、`${\n`、本文中の `${ `）が deny。（FR7、FR9）

unittest:
- [ ] TS8: 一致テストが各形の字句地図と両モードの判定を固定し、追加ブロックの位置を固定している。（FR11）

### Integration Tests
- [ ] TS10: 既存スイート全件（`python3 em-workflow/hooks/tests/run-destructive-guard.py`、`python3 -m unittest discover -s tests`）が通る。（regression／FR10、NFR2、NFR3、NFR4、NFR5、NFR7）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] F1: round2.yaml の再現形は、現行（P14）では添字を行をまたいで読むため、すでに deny になっている可能性がある。deny ならケースの追加だけで、コードは変えない（A5）。
- [ ] F2: tail の中で `$(` / バッククォートは今どおり開く（中身はコマンドとして検査されるので隠さない）。
- [ ] F3/F6: CRLF 行末の無害なコマンド（`cat <<EOF\r\nhi\r\nEOF\r\n`）は、区切り語 `EOF\r` が行 `EOF\r` で閉じるので allow のまま。
- [ ] F3/F6: 語に `\r` が付いても（`rm -rf /home/sakura/valuable\r`、`git reset --hard\r`）、既存の deny を allow に変えない。
- [ ] F3: `\x0c`・`\x85`・`\x1c`-`\x1e`・` ` も `\r` と同じく語の文字。
- [ ] F4: `a[1\\\n<<2]=x`（添字の中の継続）、`a[1<<2\\\n]=x`、`a[1<<2]\\\n=x`。
- [ ] F5: 偶数個のバックスラッシュで終わる行は連結しない（`foo\\\\\nEND` は END で閉じる）。引用した区切り語（`<<'END'`）の本文は連結しない。
- [ ] F7: 閉じない `${ cmd`（bash は構文エラー）は中身をコマンドとして末尾まで読み、検査から外さない。`${ echo }` のように `}` が引数位置にある形も閉じとしない。
- [ ] F7: 既存ケース 682 / 718 / 720（捨てられた行の `${\n` / `${ ;`）は読みが変わるが、deny のまま。
- [ ] F7: 捨てられた行（P13）で開いた `${ ` は、その行の改行で他の文脈と一緒に閉じる。
- [ ] F7: `${x}`、`${x:-y}`、`${#x}` など、`${` の直後が空白・タブ・改行・`|` 以外のものはパラメータ展開のまま。
- [ ] F7: `${ ` を入れ子に並べた 60KB の入力（TestUnclosedOpeners）でも、判定が allow にも timeout にもならない。
- [ ] F7: 引用した区切り語の本文の `${ ` は文字のまま。

### Performance Tests
- [ ] TS9: 各形を k 個 / 2k 個並べた入力で work の比と上限を確かめる。（unittest linearity／NFR1）

## Security Considerations

- **Input Validation:** 修正が既存の deny / ask の検知を弱めない（FR10、AC3）。bash と食い違う形は後続行を検査から外さない側に倒す（NFR6）。

## Error Handling

- 作業上限を超えた場合は scan-budget の ask（batch では deny）にし、allow にしない（NFR3）。
- 添字の閉じが無い場合の扱いは現行の `LexUnmatchedSubscript` のままにする（FR4）。

## Performance Optimization

### Performance Goals
- work が `LEX_WORK_FACTOR` × 入力長 + 1024 以下（NFR1）。
- 2 倍の長さで work が 2.5 倍 + 100 以下（NFR1）。
- 約 60KB の入力でもフック 1 回の評価が 10 秒以内（NFR2）。

## Success Criteria

- [ ] AC1: FR1〜FR7 に挙げた再現入力がすべて、通常実行と CLAUDE_BATCH=1 の両方で deny になる。（FR1〜FR7）
- [ ] AC2: 各再現入力が deny ケースとして cases.json の末尾に、修正より前のコミットで足されている。各ラベルは該当する stable_id で始まる。（FR9）
- [ ] AC3: 既存の deny / ask ケースが 1 件も消えておらず、並び順も変わっていない。（FR10）
- [ ] AC4: tail 内で開いてよいかの判定が 1 つの関数にまとまり、各開き記号の箇所がそれを使っている。（FR8）
- [ ] AC5: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` がすべて通る。（FR10、FR11、NFR1〜NFR7）

## Assumptions

- A1: 対象のコードは main（PR #105 の destructive-guard-lexer-round2-residuals と destructive-guard-heredoc-syntax-error のマージ後）とする。task_description の「PR #105 は未マージのまま」は古い記述として扱う。完了の定義の「修正版に追随している」は、外部の修正版が無いため、この修正そのものが対応にあたる。
- A2: bash の構文の基準は bash 5.3（round2.yaml の確認に使われた 5.3.9）とする。
- A3: c8c16caba82d6238 は一部だけ扱う。tail で開いてよい領域の判定を一か所にまとめる部分（F1・F2 と共通）は FR8 として含める。`_lex_pass`（1224-2483 行、約 1260 行）を添字・ヒアドキュメント演算子・非隣接の閉じの読み直しごとの小さな関数に分ける作業は含めない。
- A4: F2 は、tail で `${` / `$((` / `$[` / `((` と case のパターン状態を開かない方式で直す。読めない区切り語の `<<` を scan-budget と同じ ask にする方式は取らない。
- A5: F1 は、P14 で行をまたぐ添字を bash と同じく読むようになった現行コードで deny になっている可能性がある。再現形は deny ケースとして必ず足し、deny にならない形があるときだけコードを直す。
- A6: F6（aa735aa95be36542）と F7（1fcae1f76f2a20f0）は、round2.yaml で「別の機能として起票」とされたもので、この feature の範囲に含める。
- A7: F7 の `${ ` / `${|` の閉じは予約語が認められる位置の `}` とする。閉じない場合は中身をコマンドとして末尾まで読み、文字として settle しない。
- A8: `${ ` を parameter-expansion として前提にしている既存の unittest（TestHeredocBodies の BODIES、TestUnclosedOpeners の OPENERS / mixed unit / `"${ " * 20000`）は、目的（allow にならない、線形、決定的）を保ったまま bash 5.3 の読みに合わせて期待を直す。cases.json の項目は消さず、並びも変えない。
- A9: version は手で上げない（main への push で Actions が patch を上げる）。
- A10: 既存の cases.json の項目とそれを位置で固定する既存テストは変えない。新しいケースは現在の最後の項目（grep で数えて 769 件）の後ろに足す。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/destructive-guard-lexer-round2-deferred/REQUIREMENTS.md`
- 対象コード: `em-workflow/hooks/destructive-guard.py`
- ケース: `em-workflow/hooks/tests/destructive-guard-cases.json`
- 一致テスト: `tests/test_destructive_guard_lexer_agreement.py`
