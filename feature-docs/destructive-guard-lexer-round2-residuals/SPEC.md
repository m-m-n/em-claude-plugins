# Feature: destructive-guard-lexer-round2-residuals

## Overview

`em-workflow/hooks/destructive-guard.py` の一本化した字句解析で、review round 2 に残った 4 件（453963d025537b11、681fab61e1d9ff2c、9381769d7116fab2、29bbf9032dd762a0）を解消する。
後続行をヒアドキュメント本文と読み違えて破壊的コマンドに allow を返す経路と、閉じない `((` / `$((` を含む無害なコマンドが scan-budget の ask（batch では deny）になる退行をなくす。

## Objectives

- `em-workflow/hooks/destructive-guard.py` の一本化した字句解析で、review round 2 に残った 4 件（453963d025537b11、681fab61e1d9ff2c、9381769d7116fab2、29bbf9032dd762a0）を解消する
- 後続行をヒアドキュメント本文と読み違えて破壊的コマンドに allow を返す経路をなくす
- 閉じない `((` / `$((` を含む無害なコマンドが scan-budget の ask（batch では deny）になる退行をなくす

## Acceptance Criteria

- [ ] AC1: round2.yaml 記載の攻撃形 10 件（for 系 3、time 系 3、`a[1<<2]=x`、`<<END-X`、`<<E.X`、`<<E\X`）が、通常実行と `CLAUDE_BATCH=1` の両方で deny になる。（FR1、FR2、FR3、FR4）
- [ ] AC2: `x=$((echo N) | wc -c)` を 28 行・100 行並べた入力、`((cd /tmp/aN && ls) || echo no)` を 40 文並べた入力が allow になる。（FR5）
- [ ] AC3: k 個の `$((cmd) ...)` を並べた入力で work が入力長に比例することをテストが固定している。（FR5、FR7、NFR1）
- [ ] AC4: 新しいケースは修正より前のコミットで cases.json に足されている。（FR6）
- [ ] AC5: 既存の deny / ask ケースが 1 件も消えておらず、`python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest tests.test_destructive_guard_lexer_agreement` がすべて通る。（FR8、NFR2、NFR3、NFR4、NFR5）
- [ ] AC6: `cat a[1] <<EOF\nhi\nEOF` は従来どおり本物の演算子（区切り語 EOF、本文 hi）として読まれ allow のまま。（FR3）

## Technical Requirements

### Functional Requirements

- **FR1:** 算術 for の直後の `{` を予約語として読む（453963d025537b11）。`for ((...))` の閉じ `))` の直後（rw が立つ位置）にある `{` を予約語として認め、その後ろをコマンド位置として読む。`for ((i=0;i<1;i++)) { ((1<<2)); }`、`for ((;0;)){ ((1<<2)); }`、`if :; then for ((;0;)) { ((1<<2)); }; fi` の本体の `((1<<2))` は arithmetic-command で、`<<` はヒアドキュメント演算子ではない。該当箇所: destructive-guard.py:726 の `_LEX_AFTER_CLOSER_WORDS`、:869 の判定。
- **FR2:** `time --` / `time -p --` の後ろをコマンド位置として読む（681fab61e1d9ff2c）。`time` の直後、または `time -p` の直後の `--` を受け付け、その後ろをコマンド位置のまま残す。`--` の後ろでは `time` の選択肢をもう受け付けない。`time -- ((1<<2))`、`time -p -- ((1<<2))`、`time -- ! ((1<<2))` の `((1<<2))` は arithmetic-command として読む。該当箇所: destructive-guard.py:900 の `word_transition()` の time_p 分岐。
- **FR3:** 代入語の配列添字の中の `<<` を演算子と読まない（9381769d7116fab2 前半）。bash が代入を受け付ける位置にある `識別子[` は、対応する `]` までを添字として読み、中の `<<` をヒアドキュメント演算子として登録しない。`a[1<<2]=x` の後続行は本文にならない。引数位置の `cat a[1] <<EOF`（既存の固定期待、TS-8）は従来どおり本物の演算子として読む。
- **FR4:** ヒアドキュメントの区切り語を語全体から決める（9381769d7116fab2 後半）。`<<` / `<<-` の区切り語は、次のメタ文字までの 1 語として読み、引用除去した値を区切り語にする（`<<END-X` → `END-X`、`<<E.X` → `E.X`、`<<E\X` → `EX`）。語のどこかに引用（`'`、`"`、`\`）があれば quoted とする。閉じ行の判定（`_delimiter_line_word()`、:2234 / :2244、および `_LexLines.word_to_lines()`）も英数字以外を含む区切り語を受け付ける。区切り語を読み切れない形では本文を取らず、後ろの行を検査から外さない。該当箇所: destructive-guard.py:154 の `HEREDOC_OP`、:1180 の登録。
- **FR5:** 非隣接の閉じでの読み直しを全文からにしない（29bbf9032dd762a0）。`))` で閉じない `((` / `$((` を見つけたとき、全文を先頭から読み直さずに済む形にし、k 個並べた入力の仕事量を入力長に比例させる。読み直し後の字句地図（regions、heredocs、candidates、unopened、tail_start）は、2 つの括弧として読む現行の意味と同じにする。該当箇所: destructive-guard.py:1332 の restart、:1451-1461 の `lex_shell()` のループ。
- **FR6:** 直す前に cases.json へケースを足す。`em-workflow/hooks/tests/destructive-guard-cases.json` の末尾（既存 627 件の後ろ）に、`[期待する判定, ラベル, コマンド]` の形で次を足す。deny: FR1〜FR4 の各攻撃形（round2.yaml 記載の 10 形）。allow: `x=$((echo N) | wc -c)` を 28 行並べた入力と 100 行並べた入力、`((cd /tmp/aN && ls) || echo no)` を 40 文並べた入力（現状 ask になる誤爆）。各ラベルに該当する stable_id を含める。
- **FR7:** 字句解析の一致テストに固定期待と線形性テストを足す。`tests/test_destructive_guard_lexer_agreement.py` の `COMMAND_POSITION_FORMS` に FR1・FR2 の形を足す。k 個の `$((cmd) ...)` を並べた入力について、2 倍の長さで work が 2.5 倍 + 100 以下、かつ `LEX_WORK_FACTOR` × 入力長 + 1024 以下であることを `TestUnclosedOpeners` または `TestReworkLinearity` に足す。追加ブロックが既存ケースの後ろにあることを固定するテストを足す。
- **FR8:** 既存ケースを消さない。cases.json の既存の deny / ask ケースを 1 件も消さず、並び順も変えない（cases[574:627] は既存テストが位置で固定している）。

### Non-Functional Requirements

- **NFR1:** `lex_shell()` の仕事量は入力長に比例する。FR5 の形、既存の `TestUnclosedOpeners` / `TestReworkLinearity` の形の両方で `LEX_WORK_FACTOR` × 入力長 + 1024 以下に収まる。
- **NFR2:** 約 60KB の入力でもフック 1 回の評価が 10 秒（hooks.json の timeout）以内に終わる。
- **NFR3:** 作業上限を超えた場合は従来どおり scan-budget の ask（batch では deny）にし、allow にしない。
- **NFR4:** 同じ入力は同じ字句地図と同じ判定を返す（決定性）。
- **NFR5:** フックとテストは標準ライブラリだけを使い、字句解析はファイルを読まず何も評価しない（`TestModuleContract`）。
- **NFR6:** 読みは bash 5.3 の構文に合わせる。bash と一致させられない形は、後続行を検査から外さない側に倒す。

## Implementation Approach

### 影響する箇所

| シンボル | 変更 | 該当箇所 | 影響するテスト |
|---|---|---|---|
| `HEREDOC_OP` | 区切り語の読み方を変えるため、置き換えまたは削除の候補 | destructive-guard.py :147-154 定義とコメント、:1180 の唯一の使用箇所 | なし |
| `_delimiter_line_word` | 閉じ行が受け付ける語の形を広げる（名前の変更候補） | destructive-guard.py :674 docstring、:696 `_LexLines.word_to_lines()`、:2234-2245 定義 | なし |
| `_lex_pass` の `("restart", settled, reparen, iterations)` 返り値と reparen 集合 | FR5 で全文 restart をやめる場合に形が変わる候補 | destructive-guard.py :775-783、:952、:1135、:1332、:1394、:1451-1461 `lex_shell()` | tests/test_destructive_guard_lexer_agreement.py :1495、:1496、:1501、:1550、:1562（`LexMap.work` と `H.LEX_WORK_FACTOR` に依存） |
| `_LEX_AFTER_CLOSER_WORDS` | 名前は変えず `{` を足す | destructive-guard.py :724-728、:852、:869 | なし |
| destructive-guard-cases.json の並び | 削除・改名なし。末尾に追記 | em-workflow/hooks/tests/destructive-guard-cases.json | tests/test_destructive_guard_lexer_agreement.py :1610-1639（cases[574:604] と cases[604:627] を位置で固定） |

### Dependencies

**Internal Dependencies:**
- なし

**External Dependencies:**
- なし（標準ライブラリのみ。NFR5）

### File Structure

```
em-workflow/
├── hooks/
│   ├── destructive-guard.py                       # 字句解析の修正（FR1〜FR5）
│   └── tests/
│       └── destructive-guard-cases.json           # 末尾へのケース追加（FR6、FR8）
tests/
└── test_destructive_guard_lexer_agreement.py      # 固定期待と線形性テストの追加（FR7）
```

## Declared Change Set

この節は手書きの一覧ではなく create-plan での導出を述べる。上記の機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` 項目から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上記の機能固有のパスに加えて、ワークフローが生成する次の 2 項目を既定で宣言する。

- `feature-docs/destructive-guard-lexer-round2-residuals/**`
- `test-docs/destructive-guard-lexer-round2-residuals/**`

`feature-docs/destructive-guard-lexer-round2-residuals/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。この節はそれらを引用するだけで、その規則を再記述しない。

`test-docs/destructive-guard-lexer-round2-residuals/**` はタスクごとのテスト記録 `test-docs/destructive-guard-lexer-round2-residuals/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。この節はそれを引用するだけで、その規則を再記述しない。

この 2 つの既定項目は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことを外したとはみなさない。外すことは意図的で明示的な絞り込みである。

この宣言は SUPERSET の表明である。verify 時に観測される実際の変更集合は、宣言した集合に「含まれる」必要があり、「等しい」必要はない。implement タスクを生まない機能は `test-docs/destructive-guard-lexer-round2-residuals/` ディレクトリを一切生成しないが、その場合も宣言した `test-docs/destructive-guard-lexer-round2-residuals/**` は正しい。宣言したパスが実体化しないことは違反ではない。

## Test Scenarios

入力の表記は cases.json の JSON 文字列表記に合わせる（`\n` は改行）。

### Unit Tests

- [ ] TS1: `for ((i=0;i<1;i++)) { ((1<<2)); }` / `for ((;0;)){ ((1<<2)); }` / `if :; then for ((;0;)) { ((1<<2)); }; fi` の後ろに `\nrm -rf /home/sakura/valuable\n2` を付けた入力が deny。（cases.json deny + COMMAND_POSITION_FORMS／FR1、FR6、FR7）
- [ ] TS2: `time -- ((1<<2))` / `time -p -- ((1<<2))` / `time -- ! ((1<<2))` に同じ後続を付けた入力が deny。（cases.json deny + COMMAND_POSITION_FORMS／FR2、FR6、FR7）
- [ ] TS3: `a[1<<2]=x\nrm -rf /home/sakura/valuable\n2` が deny。（cases.json deny／FR3、FR6）
- [ ] TS4: `cat <<END-X\nbody\nEND-X\nrm -rf /home/sakura/valuable\nEND`、`cat <<E.X\nbody\nE.X\nrm -rf /home/sakura/valuable\nE`、`cat <<E\\X\nbody\nEX\nrm -rf /home/sakura/valuable\nE` が deny。（cases.json deny／FR4、FR6）
- [ ] TS5: `x=$((echo N) | wc -c)` を 28 行 / 100 行、`((cd /tmp/aN && ls) || echo no)` を 40 文並べた入力が allow。（cases.json allow／FR5、FR6）
- [ ] TS6: k 個と 2k 個の `$((cmd) ...)` で work の比と上限を確かめる。（unittest linearity／FR5、FR7、NFR1）

### Regression Tests

- [ ] TS7: 既存スイート全件（基準時点で run-destructive-guard.py 628/628、lexer agreement 78 件）が通る。（regression／FR8、NFR2、NFR3、NFR4、NFR5）

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] `for x { ((1<<2)); }` / `select x { ((1<<2)); }`: for / select の NAME の後ろも rw が立つ位置で、`{` を集合に足すと同じ修正で拾える。bash 5.3 で成立を確かめてから deny ケースに含める
- [ ] 閉じ記号の後ろの `{` を予約語として読むと `fi {` などでも読まれるが、bash では構文エラーで何も実行しない
- [ ] `time -p -p ...`、`time -- -p ...`、`time -- -- ...`: bash は 2 つめの `-p` / `--` を語として読む。`--` の後ろでは time_p を落とす
- [ ] `)){` のように `{` が `))` に隣接する形
- [ ] 添字の位置: 先行する代入語の後ろ（`x=1 a[1<<2]=y`）、`$( )` の中のコマンド位置、`a[1<<2]+=x`、入れ子 `a[b[1]<<2]=x`、添字内の引用や `$( )`、`declare` / `local` / `export` / `readonly` / `typeset` の引数（bash が添字として読むかを 5.3 で確かめる）
- [ ] 引数位置の `echo a[1<<2]` は bash では `<<` が本物の演算子。添字として広く読みすぎると本文行をコマンドとして読み、本文の引用で後続を覆う形になり得る
- [ ] 閉じない `a[`（bash は構文エラー）
- [ ] 区切り語の変形: `<<E"X"`、`<<'E-X'`、`<<\EOF`（現状は演算子として登録されない）、`<<E$X`（展開されず字面が区切り語）、`<<-` の場合のタブ除去
- [ ] 閉じ行の判定は現状 `<<` / `<<-` とも前後の空白・タブを許す（bash より広い）。広い側は本文を早く終える側なので維持してよい
- [ ] 非隣接の閉じが入れ子になる形（`$(( $((echo a) ) ...`）、二重引用符の中、ヒアドキュメント本文待ちの間にまたがる形
- [ ] 敵対的な入れ子で作業上限を超える場合は ask（batch では deny）であり allow にならない

### Performance Tests

- [ ] TS6 で仕事量の比と上限（NFR1）を確かめる

## Security Considerations

- 修正が既存の deny / ask の検知を弱めない（FR8、AC5）
- bash と食い違う形は後続行を検査から外さない側に倒す（NFR6、A3）

## Error Handling

- 作業上限を超えた場合は scan-budget の ask（batch では deny）にし、allow にしない（NFR3）
- 区切り語・添字を読み切れない形では本文を取らず、後続行を検査する（FR4、A3）

## Performance Optimization

### Performance Goals

- `lex_shell()` の仕事量: `LEX_WORK_FACTOR` × 入力長 + 1024 以下（NFR1）
- 約 60KB の入力でフック 1 回の評価が 10 秒以内（NFR2）

## Success Criteria

- [ ] FR1〜FR8 がすべて実装・テストされている
- [ ] TS1〜TS7 がすべて通る
- [ ] AC1〜AC6 を満たす

## Assumptions

- A1: 完了の定義の「修正版に追随している」は、対象がこのリポジトリ自身のコードで外部の修正版が無いため、この修正そのものが対応にあたる。暫定緩和策は「なし」のまま。
- A2: bash の構文の基準は bash 5.3（round2.yaml で確認に使われた 5.3.9）。
- A3: 読み切れない区切り語・添字は、本文を取らず後続行を検査する側に倒す（unified-lexer の SPEC A3 と同じ方針）。
- A4: version は手で上げない（main への push で Actions が patch を上げる）。
- A5: cases.json の既存 627 件と、それを位置で固定する既存テスト（cases[574:604]、cases[604:627]）は変えない。新規ケースは index 627 以降に足す。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases

### Phase 1: ケースの追加

**Goals:** 修正より前のコミットで cases.json に新しいケースを足す（AC4）
**Deliverables:**
- FR6

### Phase 2: 字句解析の修正とテストの追加

**Goals:** 字句解析を直し、一致テストに固定期待と線形性テストを足す
**Deliverables:**
- FR1、FR2、FR3、FR4、FR5
- FR7

## References

- フックのテスト: `.claude/rules/hook-tests.md`
- version の扱い: `.claude/rules/core-plugin-version-bump.md`
