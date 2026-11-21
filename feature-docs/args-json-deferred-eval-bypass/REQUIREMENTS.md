---
title: "args-json-deferred-eval-bypass"
created_date: 2026-11-21
status: draft
---

# args-json-deferred-eval-bypass - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/hooks/destructive-guard.py` の notion ペアの除外（`_args_json_notion_pair()`）は、先行するコマンドが名前参照を作り得るかを `_args_json_nameref_scan()` で判定する。値を後から現在のシェルで評価し直す構文（算術式、`${var@P}` など）を経由すると、この判定をすり抜けて `--args-json` の検査を省かせられる。

シェルを実行する MCP ツールが mcp-bridge に登録された環境で、次のどれかの形で名前参照 `r` を配列に向け、`mcp-bridge run --mcp notion --tool notion-create-comment --format "$r" --args-json '{"command":"<破壊的なコマンド>"}'` を実行する。フックは notion 宛てと判定して JSON を検査せず allow にするが、Bash では `"$r"` が `json --mcp desktop-commander --tool start_process` に展開され、別のツールに送られる。

- ANSI-C で開始記号を隠した値を `${p@P}` で評価する（`p=$'$\x7b declare -gn r=A[@]; }'`）
- `$''{` で分割した値や ANSI-C の値を、算術式 `(( a ))` の配列添字で評価する
- 区切り語を引用したヒアドキュメントやファイルから `read` した値を同じように評価する

round 3 の修正では、字面の `${ ` / `${|` をチャンク全体から探す判定（引用の内外を問わない）で塞いだが、値を実行時に組み立てる形は防げない。

### 1.2 目的

- 後から現在のシェルで評価される値（算術式、`${var@P}`、`read` で読んだ値など）を使って名前参照を作り、notion ペアの除外を回避する攻撃を成立させない。
- 各攻撃形を `destructive-guard-cases.json` の deny ケースとして固定する。
- 文字列を評価する組み込み（`fc`, `history`, `enable`, `compgen`, `complete`, `bind`）の取りこぼしを、組み込みの許可リストで同時に塞ぐ。

### 1.3 スコープ

- `em-workflow/hooks/destructive-guard.py` の notion ペアの除外判定（`_args_json_nameref_scan()`、`_args_json_declares_nameref()`、`_args_json_declaration_word()`、`_args_json_has_brace_substitution()`）
- `em-workflow/hooks/tests/destructive-guard-cases.json` の deny ケースの追加
- `tests/test_destructive_guard_args_json.py` の算術コマンドのサブテストの変更

## 2. ビジネス要件

### 2.1 ビジネス目標

- 後から評価される値を使った notion ペアの除外の回避を成立させない。
- 各攻撃形を deny ケースとして固定する。
- 文字列を評価する組み込みの取りこぼしを、組み込みの許可リストで塞ぐ。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | destructive-guard フックが有効な環境で Claude Code を無人実行する |

### 2.3 期待される効果

- 後から評価される構文や許可リストに無いコマンドと、`--format` / `--session` / `--args-json` の値の `"$var"` を同じコマンドに含む notion 呼び出しは、`--args-json` が検査されるようになる。中に破壊的なコマンドがあれば deny になる。
- 利用者に見える変化は判定だけ。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | notion 呼び出しを含む Bash コマンドの判定 | destructive-guard フック | - |

### 3.2 ユースケース詳細

#### UC01: notion 呼び出しを含む Bash コマンドの判定

**アクター**: destructive-guard フック

**事前条件**:
- Bash コマンドに `mcp-bridge run --mcp notion ...` の呼び出しがある。

**基本フロー**:
1. notion 呼び出しのチャンクと、その外側のチャンクを `_args_json_nameref_scan()` で走査する。
2. 名前参照の宣言、後から評価される構文（FR1）、許可リストに無いコマンド名（FR3）のどれも無ければ、notion ペアの除外を保つ。
3. どれかがあれば、シェル状態を不明として除外を外し、`--args-json` を検査する。

**代替フロー**:
- lexer が文として読めないチャンクは、今までどおり不明として扱う。

**事後条件**:
- 不明扱いで外れるのは除外だけ。`--args-json` に破壊的なコマンドが無ければ deny にならない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 後から評価される構文を持つチャンクはシェル状態を不明とする | 値をコードとして評価し直す構文があるチャンクを不明とする | - |
| FR2 | 算術コマンドを「何も宣言しない」とする扱いをやめる | arithmetic-command 領域を FR1 に従って不明とする | - |
| FR3 | コマンド名を許可リストで判定する | 拒否リストを許可リストに変える | - |
| FR4 | 字面検索を補助として残す | round 3 の字面の `${` / `${\|` 検索を残す | - |
| FR5 | 攻撃形の deny ケースを固定する | 攻撃形と各構文・各名前の deny ケースを追加する | - |
| FR6 | 既存の除外が保たれる形を維持する | 既存の allow / deny / ask ケースの判定を変えない | - |
| FR7 | 算術コマンドを固定していた単体テストを改める | `((x=1));` のサブテストを KIND_INSPECTED に移す | - |
| FR8 | 新しい規則や理由 ID を足さない | 不明の扱いは既存の除外判定に反映するだけとする | - |

### 4.2 機能詳細

#### FR1: 後から評価される構文を持つチャンクはシェル状態を不明とする

**説明**: `_args_json_nameref_scan()` は、チャンクに次の構文が 1 つでもあれば True（シェル状態不明）を返す。

**対象の位置**: 関数本体・グループ・条件文・ループの中、二重引用符の中、引用なしの区切り語のヒアドキュメント本文、ヒアストリングを含む、lexer が構文として読む位置すべて。

**構文**:
- 算術コマンド `((...))`（`for ((...))` を含む）
- 算術展開 `$((...))`、`$[...]`
- `let`
- `[[ ]]` の算術比較（`-eq` `-ne` `-lt` `-le` `-gt` `-ge`）と `-v`
- 変数（`$` 展開または名前）を添字に使う配列添字（代入語、複合代入の `[..]=`、パラメータ展開の中）
- `declare` / `local` / `typeset` の `i` を含むオプション
- `@P` 変換を持つパラメータ展開
- 間接展開 `${!x}`
- 整数属性を持つ定義済み変数（例: `OPTIND`）への代入
- `PS4` への代入と xtrace の有効化（`set -x` / `set -o xtrace`）

**ビジネスルール**:
- 単一引用符の中や、引用した区切り語のヒアドキュメント本文の `((` や `@P` は、データとして数えない（A3）。
- 添字が数字だけの配列添字と、添字の無い複合代入は除外を保つ（A4）。

#### FR2: 算術コマンドを「何も宣言しない」とする扱いをやめる

**説明**: `_args_json_declaration_word()` とその呼び出し元で、arithmetic-command 領域を「コマンド名にならず何も宣言しない」と扱うのをやめる。算術コマンドは FR1 に従って不明として扱う。

#### FR3: コマンド名を許可リストで判定する

**説明**: `_args_json_declares_nameref()` のコマンド名の判定を、拒否リスト（`eval`, `source`, `.`, `trap`, `alias`, `mapfile`, `readarray`）から許可リストに変える。

**ビジネスルール**:
- 許可リストに載せるのは、シェル状態を変えず、文字列を評価せず、変数名を引数に取らないと確かめた組み込み・キーワードと外部コマンドだけとする。
- 許可リストに無いコマンド名を持つ単純コマンドはシェル状態を不明とする。次が該当する。
    - `fc`, `history`, `enable`, `compgen`, `complete`, `bind`
    - 分類していない名前
    - チャンクの中で定義した関数の呼び出し
    - 変数名を引数に取る組み込み（`read`, `printf -v`, `getopts`, `wait -p`, `unset`, `test -v` / `[ -v` など）
- `builtin` / `command`（と既存の前置語 `exec`, `time`, `!`）を前に置いて呼んだ場合も、前置語を読み飛ばした後の名前を同じく分類する。
- `printf` は `-v` を持つ場合に加え、`%n` を含む書式を持つ場合も不明とする。
- `declare` / `local` / `typeset` は既存どおり個別に扱い、`n` を含むオプション、FR1 の `i` を含むオプション、復元できない語のどれかがあれば不明とする。

#### FR4: 字面検索を補助として残す

**説明**: round 3 で入れた、引用の内外を問わない字面の `${` / `${|` 検索と行継続の扱い（`_args_json_has_brace_substitution()`）は削らずに残す。

#### FR5: 攻撃形の deny ケースを固定する

**説明**: 次を `destructive-guard-cases.json` に deny として追加する。ラベルの先頭は `args-json-deferred-eval-bypass` にする。

- 1.1 の攻撃シナリオの各形（`${p@P}` で ANSI-C の値を評価、`$''{` で分けた値や ANSI-C の値を `(( a ))` の配列添字で評価、引用した区切り語のヒアドキュメントやファイルから `read` した値を評価）
- FR1 の各構文
- FR3 で不明になる名前（`fc`, `history`, `enable`, `compgen`, `complete`, `bind`、`builtin` / `command` 前置の形、`printf -v`、`%n` を含む `printf` の書式、変数名を引数に取る組み込み）

#### FR6: 既存の除外が保たれる形を維持する

**説明**: 次の判定を変えない。

- notion ペアの除外を保つ既存の allow ケース（`destructive-guard-cases.json` の 1161-1163, 1200-1201, 1374, 1421, 1426, 1473, 1474。単一引用符の本文、`"$SID"`、1 段と 2 段のコマンド置換を含む）
- 既存の deny / ask ケース（round 3 の deny を含む）

**ビジネスルール**:
- 許可リストには、これらのケースと既存の単体テストで notion 呼び出しのチャンクとその外側のチャンクに現れるコマンド名（`mcp-bridge`, `echo`）を含める。
- 既存の単体テストが KIND_NOTHING を固定している形（`declare -a`、`command -- echo`、コメント）が通る分類を含める。

#### FR7: 算術コマンドを固定していた単体テストを改める

**説明**: `tests/test_destructive_guard_args_json.py` の `TestNamerefDeclarations.test_a_declaration_with_no_nameref_option_does_not_make_the_call_uncertain` から、サブテスト `'arithmetic command without blanks'`（`((x=1));` の後の notion 呼び出しを KIND_NOTHING とするもの）を外し、KIND_INSPECTED を期待する形に移す。docstring の「an arithmetic command」の記述も同じく改める。

#### FR8: 新しい規則や理由 ID を足さない

**説明**: 不明の扱いは既存の notion ペアの除外判定（`_args_json_nameref_declared()` の結果）に反映するだけとする。新しい ask / deny の規則と理由 ID は足さない。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR2: 判定はチャンクごとに 1 回計算してキャッシュする（`_nameref_declared_cache`）。外側のチャンクへの遡りは再帰を使わない（既存の `test_the_chain_is_walked_without_recursion` を保つ）。

### 5.2 セキュリティ要件

- NFR1: 判定は静的解析だけで行い、コマンドを実行・評価しない。lexer が文として読めないチャンクは今までどおり不明として扱う。
- severity high。無人実行で、破壊的なコマンドが MCP 経由のシェルで deny を通らずに実行され得る。fail-safe 側に倒し、判定できない形と分類していない名前は不明として扱う。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- NFR3: テストは標準ライブラリだけで書く（`test/README.md`）。
- NFR4: em-workflow の version は変更しない（`.claude/rules/core-plugin-version-bump.md`）。
- NFR5: `destructive-guard.py` を変更した同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` を走らせる（`.claude/rules/hook-tests.md`）。
- 既存の deny / ask ケースは消さない（`.claude/rules/hook-tests.md`）。

### 5.5 互換性要件

- FR6 のとおり、既存の allow / deny / ask ケースの判定を変えない。

## 6. UI/UX要件

該当なし（画面や見た目の成果物が無い。デザインステップはスキップする）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- Python 3（`test/README.md` は Python 3.14 を想定）
- 判定対象の構文は Bash
- フレームワークなし（標準ライブラリの unittest）

### 9.2 ビジネス上の制約

- 新しい ask / deny の規則と理由 ID は足さない（FR8）。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/args-json-deferred-eval-bypass/**`
- `test-docs/args-json-deferred-eval-bypass/**`

`feature-docs/args-json-deferred-eval-bypass/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/args-json-deferred-eval-bypass/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/args-json-deferred-eval-bypass/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/args-json-deferred-eval-bypass/` ディレクトリを生成しないが、宣言された `test-docs/args-json-deferred-eval-bypass/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `read` で読んだ値そのものは静的に見えない（ファイルから読む形を含む） | - | `read` は許可リストに無いので、同じチャンクか外側のチャンクにあれば不明になる。読んだ後に評価する構文（FR1）も不明になる |
| 変数名を引数に取る組み込みに添字付きの名前を渡す形（`read 'x[a]'`、`printf -v 'x[a]'`、`getopts o 'x[a]'`、`wait -p 'x[a]'`、`unset 'x[a]'`、`test -v 'x[a]'`）は、添字の名前が算術評価される | - | これらの組み込みは引数によらず不明になる（FR3） |
| 整数属性を持つ定義済み変数（`OPTIND` など）への値の代入は、値が算術として評価される | - | FR1 で不明とする |
| `PS4` は xtrace のたびに現在のシェルで展開される | - | FR1 で不明とする |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 正当な notion 呼び出しの除外が外れる | - | - | FR6 の既存 allow ケースを全件維持する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: 1.1 の攻撃シナリオの各形が `destructive-guard-cases.json` で deny として通る。
- [ ] AC2: FR1 の各構文について、notion 呼び出しの前にそれを置いたコマンドが deny として通る。
- [ ] AC3: `fc`, `history`, `enable`, `compgen`, `complete`, `bind`、`builtin` / `command` を前に置いたそれらの形、`printf -v`、`%n` を含む書式の `printf`、変数名を引数に取る組み込み（`read`, `getopts`, `wait -p`, `unset`, `test -v`）、許可リストに無い名前のそれぞれについて、notion 呼び出しの前にそれを置いたコマンドが deny として通る。
- [ ] AC4: FR6 に挙げた既存の allow ケースと、既存のすべての deny / ask ケースが、同じ判定のまま通る。
- [ ] AC5: 名前参照の宣言も FR1 の構文も無く、コマンド名がすべて許可リストにあるチャンク（例: `A=(...); echo hello;` と `--session "$SID"` の notion 呼び出し）は、引き続き KIND_NOTHING になる。
- [ ] AC6: 追加した deny ケースの理由 ID は既存のものだけで、`destructive-guard.py` に新しい理由 ID が無い。
- [ ] AC7: `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` がどちらも成功する。
- [ ] AC8: SPEC の暫定緩和策の欄に、上流の修正版が無いことと、このフィーチャーの修正を対応とすることが書かれている。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] セキュリティ: TS-1 (AC1): `p=$'$\x7b declare -gn r=A[@]; }'` と `${p@P}` を置いた後の、`--format "$r"` と破壊的な command を持つ notion 呼び出しが deny。
- [ ] セキュリティ: TS-2 (AC1): `$''{` で分けた値と ANSI-C の値を `(( a ))` の配列添字で評価した後の同じ notion 呼び出しが deny。
- [ ] セキュリティ: TS-3 (AC1): 区切り語を引用したヒアドキュメントから `read` した値と、ファイルから `read` した値を評価した後の同じ notion 呼び出しが deny。
- [ ] セキュリティ: TS-4 (AC2): FR1 の構文ごとに 1 件、notion 呼び出しの前に置いた形が deny（関数本体・グループ・条件文・ループ・二重引用符・引用なしの区切り語のヒアドキュメント本文・ヒアストリングの中に置いた形を含む）。
- [ ] セキュリティ: TS-5 (AC3): `fc`, `history`, `enable`, `compgen`, `complete`, `bind` をそれぞれ単独と `builtin` / `command` 前置で置いた形が deny。
- [ ] セキュリティ: TS-6 (AC3): `printf -v`、`%n` を含む書式の `printf`、`read`, `getopts`, `wait -p`, `unset`, `test -v`、チャンクの中で定義した関数の呼び出し、許可リストに無い名前を置いた形が deny。
- [ ] 正常系: TS-7 (AC4): 既存の allow / deny / ask ケースがすべて同じ判定（`run-destructive-guard.py`）。
- [ ] 正常系: TS-8 (AC5): `A=(...); echo hello;` の後の `--session "$SID"` の notion 呼び出し、`declare -a`、`command -- echo`、コメントの形が単体テストで KIND_NOTHING。`((x=1));` の形は KIND_INSPECTED（FR7）。
- [ ] 境界値: TS-9 (AC5): 評価する構文がコマンド置換の中だけにあり、notion 呼び出しが外側にある形は除外を保つ。
- [ ] 正常系: TS-10 (AC6): 追加した deny ケースに rule を付け、既存の理由 ID と一致する。

### 12.2 エッジケース

- `read` で読んだ値そのものは静的に見えない（ファイルから読む形を含む）。`read` は許可リストに無いので、同じチャンクか外側のチャンクにあれば不明になる。読んだ後に評価する構文（FR1）も不明になる。
- 変数名を引数に取る組み込みに添字付きの名前を渡す形（`read 'x[a]'`、`printf -v 'x[a]'`、`getopts o 'x[a]'`、`wait -p 'x[a]'`、`unset 'x[a]'`、`test -v 'x[a]'`）は、添字の名前が算術評価される。許可リスト方式なので、これらの組み込みは引数によらず不明になる。
- `test` / `[` は `-v` を持つときだけ不明とする。`[[ ]]` は FR1 の算術比較と `-v` を持つときに不明とする。
- 整数属性を持つ定義済み変数（`OPTIND` など）への値の代入は、値が算術として評価される。
- `PS4` は xtrace のたびに現在のシェルで展開される。
- チャンクの中で定義した関数は、許可リストにある名前と同じ名前でない限り、呼び出しが不明になる。許可リストにある名前で関数を定義した場合、その本体は同じチャンクの一部として走査される。
- 評価する構文がコマンド置換の中（サブシェル）にあり、notion 呼び出しが外側にある場合は、呼び出し元の状態は変わらない。今の判定は外側へ遡るだけなので、この場合は除外を保つ。
- 単一引用符の中や、引用した区切り語のヒアドキュメント本文の `((` や `@P` は、データとして数えない（A3）。
- 添字が数字だけの配列添字と、添字の無い複合代入は除外を保つ（A4）。
- 不明扱いで外れるのは除外だけ。`--args-json` に破壊的なコマンドが無ければ deny にならない。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| notion ペアの除外 | `_args_json_notion_pair()` が notion 宛ての呼び出しと判定したとき、`--args-json` の検査を省く扱い |
| シェル状態不明 | `_args_json_nameref_scan()` が True を返す状態。notion ペアの除外を外す |
| チャンク | `_args_json_nameref_scan()` が走査する単位 |
| 許可リスト | シェル状態を変えず、文字列を評価せず、変数名を引数に取らないと確かめた組み込み・キーワードと外部コマンドの一覧 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 組み込みの判定方式（requirement.builtin-judgment-approach）: 組み込みは許可リストで判定する。シェル状態を変えず文字列を評価せず変数名を引数に取らないと確かめた組み込み・キーワードと外部コマンドだけを既知とし、それ以外（`fc` / `history` / `enable` / `compgen` / `complete` / `bind`、分類していないもの、`read` / `printf -v` / `getopts` / `wait -p` / `unset` / `test -v` など変数名を取るもの）は不明とする。`builtin` / `command` 前置で呼んだ場合も分類対象から外さない。`printf` は `-v` に加えて `%n` を含む書式も不明。不明扱いは既存の notion ペア除外判定に反映するだけで新しい ask / deny 規則や理由 ID は足さない。既存の notion allow ケース（単一引用符の本文、`"$SID"`、1 段と 2 段のコマンド置換を含む）と round 3 の deny を全件維持する。
- [x] デザインステップ（design.step.recommendation）: スキップする。

前提:

- A1: コマンド名は許可リストで判定する。シェル状態を変えず、文字列を評価せず、変数名を引数に取らないと確かめた組み込み・キーワードと外部コマンドだけを既知とし、それ以外は不明とする。（出典: requirement.builtin-judgment-approach）
- A2: `builtin` / `command` を前に置いた呼び出しも分類の対象とする。`printf` は `-v` に加えて `%n` を含む書式も不明とする。（出典: requirement.builtin-judgment-approach）
- A3: 単一引用符の中や、引用した区切り語のヒアドキュメント本文の `((` や `@P` は、データとして数えない。（出典: 既存の allow ケース 1161, 1162, 1200, 1201）
- A4: 添字が数字だけの配列添字と、添字の無い複合代入は除外を保つ。（出典: 既存の単体テストと AC5 の例）
- A5: 不明の扱いは既存の notion ペアの除外判定に反映するだけで、新しい ask / deny の規則と理由 ID は足さない。既存の notion allow ケースと round 3 の deny を全件維持する。（出典: requirement.builtin-judgment-approach）
- A6: デザインステップはスキップする。（出典: design.step.recommendation）

### 14.2 未確認・保留事項

なし

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 判定の実装
- `em-workflow/hooks/tests/destructive-guard-cases.json`: `[判定, ラベル, コマンド]` の表
- `em-workflow/hooks/tests/run-destructive-guard.py`: 表のランナー
- `tests/test_destructive_guard_args_json.py`: `--args-json` の段の単体テスト
- `.claude/rules/hook-tests.md`
- `.claude/rules/core-plugin-version-bump.md`
- `test/README.md`
