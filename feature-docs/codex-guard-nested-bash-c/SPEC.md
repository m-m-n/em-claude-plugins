# Feature: codex-guard-nested-bash-c

## 概要

codex-hook-interactive-guard が、シェル `-c` の文字列の中にある対話的なインタプリタやシェルの起動を、入れ子の段数によらず拒否するようにする。二段目以降の文字列にも一段目と同じ規則を使い、走査は明示的なスタックで行い、二段目以降で読み直す文字数の合計に上限を設ける。

要件定義書: `feature-docs/codex-guard-nested-bash-c/REQUIREMENTS.md`

## 目的

- codex-hook-interactive-guard が、シェル `-c` の文字列の中の対話的なインタプリタやシェルの起動を何段目でも拒否し、無人の Codex レビューが入れ子の REPL で止まらないようにする。
- 判定範囲の決定（すべての段）とその理由を、この SPEC に記録する。

## 判断記録: 入れ子の -c 文字列の判定範囲

**決定**: 二段目以降の `-c` 文字列も、すべての段で、一段目と同じ規則で判定する。

**理由**:
- 判定を固定の段数で止めると、同じ対話起動がそれより深い段にあるときに検出されず、無人実行が止まる経路が残る。
- 既存の一段限定（テストの 265 行目のコメントが示す、一段のリテラルだけを判定する規則）は、一段を上限とする理由を示していない。
- すべての段を判定するリスクは、再帰で発生した例外を `main()` が黙って通すことと処理時間である。前者は明示的なスタック（FR2）、後者は文字数の上限（FR3）で対処する。

### 既存 CASES の期待の変更

次の 3 件は、いずれも REPL を開く起動である。`-c` 文字列をすべての段で判定するようになったため、silent から deny に変える。

| 行 | コマンド | 変更 | 理由 |
|----|----------|------|------|
| 82 | `bash -c "bash -c 'python3 -i'"` | silent → deny | 二段目の `python3 -i` が REPL を開く。二段目を判定するようになった |
| 83 | `sh -c 'bash -lc "python3 -i"'` | silent → deny | 二段目の `python3 -i` が REPL を開く。二段目を判定するようになった |
| 305 | `bash -cx "bash -c 'python3 -i'"` | silent → deny | 二段目の `python3 -i` が REPL を開く。二段目を判定するようになった |

## 技術要件

### 機能要件
- **FR1: すべての段の -c 文字列を判定する** — `-c` で起動したシェル（bash sh zsh dash ksh。`-lc`、`-cx` のようなまとめ書きを含む）のリテラルな第一オペランドを、どの段でも解析して判定する。各段に一段目の規則を使う。文字列を持つコマンドの標準入力の接続は、その文字列の中のすべてのコマンドに引き継ぐ。判定できない文字列（クォートの不一致、終端のないヒアドキュメント、閉じていないグループ）は読み飛ばし、通す。動的なオペランドは判定しない。関数本体は判定しない。ラッパーとオプションは一段目と同じように読む。シェル `-n` は一段目とまったく同じに扱う。
- **FR2: 再帰ではなく明示的なスタックで走査する** — 入れ子の `-c` 文字列の走査は、再帰ではなく明示的なスタック（作業リスト）で行う。コマンドの判定順は現行と同じにする。1 つの文字列の中のコマンドを順に判定し、入れ子の文字列の中のコマンドは、その文字列を持つコマンドより後ろのコマンドより先に判定する。その順で最初に拒否対象となった起動が、拒否理由を決める。
- **FR3: 読み直す文字数の上限** — module 定数で、二段目以降の `-c` 文字列から読み直す文字数の合計に上限を設ける。合計はコマンド全体で数え、上限は 1,000,000 文字とする。一段目の文字列は現行どおり判定し、上限の計数に含めない。次の文字列を読むと上限を超える時点で、その文字列と、それ以降の二段目以降の文字列はすべて解析せず、通す。上限を超えたことは拒否理由にしない。0 段目と一段目のコマンドは引き続き判定する。
- **FR4: 既存の silent ケースを deny に変える** — `tests/test_codex_hook_interactive_guard.py` の `CASES` のうち 82 行目 `bash -c "bash -c 'python3 -i'"`、83 行目 `sh -c 'bash -lc "python3 -i"'`、305 行目 `bash -cx "bash -c 'python3 -i'"` を silent から deny に変え、ラベルを新しい挙動を表すものにする。265 行目のコメント（`# bash -c: one level of literals` で始まるもの）を書き換える。それぞれの変更理由は「既存 CASES の期待の変更」に記す。
- **FR5: テストケースの追加** — `CASES` に、二段以上の `-c` 文字列の中の対話起動の deny ケースと、内側の段に一段目の規則を適用した silent ケースを足す（テストシナリオの TS-1、TS-2）。
- **FR6: docstring の書き換え** — 2 つのコピーの module docstring の手順 7（`the first operand is judged once, the same way`）を書き換える。文字列をどの段でも同じ規則で判定すること、走査に明示的なスタックを使うこと、文字数の上限を超えた文字列は通すことを書く。
- **FR7: 2 つのコピーをバイト単位で同一に保つ** — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を一緒に変更し、バイト単位で同一に保つ。

### 非機能要件
- **NFR1: 標準ライブラリのみ・副作用なし** — 標準ライブラリのみを使う。ネットワーク、ファイル書き込み、サブプロセスを使わない（`TestStaticConstraints` が通る状態を保つ）。
- **NFR2: 誤拒否より通過を優先する** — 誤った拒否より通過を優先する。判定できないものと上限を超えたものは通す。一段目の規則以外の読み方を追加しない。
- **NFR3: 深い入れ子でも時間内に応答する** — 深い入れ子や多数の入れ子でも時間内に応答する。終了ステータス 0、標準エラー出力は空、標準出力は空か deny オブジェクトちょうど 1 つ（`TestMalformedAndDeepInput` の形、タイムアウト 60 秒）。
- **NFR4: テストスイートが通る** — `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。
- **NFR5: version を変えない** — version を変えない。main への push 時に Actions が version を上げる（`.claude/rules/core-plugin-version-bump.md`）。

## 受け入れ基準

- [ ] AC1: この SPEC に、二段目以降の `-c` 文字列を判定すること（すべての段）と、その理由が記録されている。
- [ ] AC2: `CASES` に、二段以上の `bash -c` 文字列の中の対話起動とプログラム指定なしの起動の deny ケースがある。タスクの extglob の例を含む。
- [ ] AC3: 82、83、305 行目の `CASES` が deny を期待し、この SPEC にそれぞれの変更理由が書かれている。
- [ ] AC4: 内側の段でも一段目の規則が保たれる。接続された入力、動的な文字列、判定できない文字列、関数本体、無害な文字列は silent のまま。
- [ ] AC5: `_scan` が入れ子の文字列を再帰なしの明示的なスタックで走査する。二段目以降で読み直す文字数に上限があり、上限を超えた文字列は通す。
- [ ] AC6: 深い入れ子と多数の入れ子の入力に、テストのタイムアウト内で、終了ステータス 0、空の標準エラー出力で応答する。
- [ ] AC7: 2 つのコピーの docstring 手順 7 が、すべての段の判定、明示的なスタック、上限を説明している。
- [ ] AC8: 2 つのコピーがバイト単位で同一で、`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。

## 実装方針

### 段の定義

| 用語 | 定義 |
|------|------|
| 0 段目 | フックが受け取ったコマンドそのもの |
| 一段目の文字列 | 0 段目のコマンドにある、シェル `-c` のリテラルな第一オペランド |
| 二段目以降の文字列 | 一段目以降の文字列の中にある、シェル `-c` のリテラルな第一オペランド |

### 走査（`_scan`）

- 入れ子の `-c` 文字列は明示的なスタック（作業リスト）で走査し、再帰を使わない（FR2）。
- 判定順は現行と同じ。1 つの文字列の中のコマンドを順に判定し、入れ子の文字列の中のコマンドを、その文字列を持つコマンドより後ろのコマンドより先に判定する。最初に拒否対象となった起動が拒否理由を決める（FR2）。
- 各段の文字列には一段目の規則をそのまま使う（FR1）。

### 文字数の上限

- module 定数 1 つ。値は 1,000,000 文字（FR3）。
- 計数の対象は、1 つのコマンドで二段目以降に読み直すすべての `-c` 文字列の文字数の合計。一段目の文字列は数えない。
- 次の文字列を読むと上限を超える時点で、その文字列とそれ以降の二段目以降の文字列は解析せず通す。

### 変更するファイル

```
em-workflow/scripts/codex-hook-interactive-guard.py   # _scan と module docstring 手順 7
em-review/scripts/codex-hook-interactive-guard.py     # 上と同じ変更（バイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # CASES の変更と追加、深い入力・上限・docstring のテスト
```

### 依存関係

**外部依存**: なし（標準ライブラリのみ。NFR1）

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-guard-nested-bash-c/**`
- `test-docs/codex-guard-nested-bash-c/**`

`feature-docs/codex-guard-nested-bash-c/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-guard-nested-bash-c/**` covers `test-docs/codex-guard-nested-bash-c/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/codex-guard-nested-bash-c/` directory at all; the declared
`test-docs/codex-guard-nested-bash-c/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## テストシナリオ

### TS-1: 入れ子の deny ケース（CASES）
対応: FR1、FR5
- [ ] deny: `bash -c "bash -c 'python3 -i'"`（82 行目、変更）
- [ ] deny: `sh -c 'bash -lc "python3 -i"'`（83 行目、変更）
- [ ] deny: `bash -cx "bash -c 'python3 -i'"`（305 行目、変更）
- [ ] deny: `bash -c "bash -c 'python3'"`（二段目のプログラム指定なしの起動）
- [ ] deny: `bash -c 'bash -O extglob -c "time /bin/true?()\n(python3 -i)"'`（タスクの extglob の例）
- [ ] deny: 最も内側に `python3 -i` を持つ三段の文字列
- [ ] deny: 内側のシェルが `zsh -c` / `bash -lc` / `env FOO=1 bash -c`
- [ ] deny: `bash -c "bash -c 'cd x && python3 -i'"`

### TS-2: 入れ子の silent ケース（CASES）
対応: FR1、NFR2
- [ ] silent: `echo | bash -c "bash -c python3"`（パイプの接続が二段目に届く）
- [ ] silent: `bash -c "bash -c python3" < f`（標準入力のリダイレクトが二段目に届く）
- [ ] silent: `bash -c "bash -c 'echo x | python3'"`
- [ ] silent: `bash -c 'bash -c "$CMD"'`（内側の文字列が動的）
- [ ] silent: `bash -c "bash -c 'echo hi'"`（無害な文字列）
- [ ] silent: クォートが不一致の内側の文字列
- [ ] silent: `python3 -i` を持つ内側の関数本体（`bash -c "bash -c 'f() { python3 -i; }'"`）

### TS-3: 深い入力と多数の入れ子に時間内に応答する
対応: FR2、FR3、NFR3
- [ ] `python3 -i` を何段もクォートして作ったコマンド（例: `shlex.quote` を繰り返し適用）。再帰を使った場合に Python の既定の再帰上限を超える深さ、または上限が許す深さにする。フックがタイムアウト内に、終了ステータス 0、空の標準エラー出力で応答する。
- [ ] 合計が上限を超える多数の兄弟の二段目文字列。フックがタイムアウト内に、終了ステータス 0、空の標準エラー出力で応答する。

### TS-4: 上限の挙動
対応: FR3
- [ ] 合計が上限を超える二段目の文字列の後ろに、上限を超えた位置の二段目 `python3 -i` → silent（上限超過は拒否理由にしない）
- [ ] 上限に達する前の二段目 `python3 -i` → deny
- [ ] 一段目の判定は影響を受けない。合計が上限を超える一段目の文字列の後ろに、一段目の `python3 -i` → deny

### TS-5: docstring のマーカー
対応: FR6
- [ ] `TestGuardDocumentation` が、2 つのコピーで、すべての段の判定、明示的なスタック、上限のマーカー文を確認する。

### TS-6: 既存スイートとコピー
対応: FR7、NFR1、NFR4
- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。`TestCopies`（バイト単位の同一性）と `TestStaticConstraints` を含む。

### E2E テスト
**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

## エラー処理

- 判定できない文字列（クォートの不一致、終端のないヒアドキュメント、閉じていないグループ）は読み飛ばし、通す（FR1、NFR2）。
- 上限を超えた文字列は解析せず、通す。上限超過は拒否理由にしない（FR3、NFR2）。

## 範囲外

- シェル以外のインタプリタのコード文字列（`python -c`、`node -e` など）、`eval`、`xargs`、`find -exec`。
- `feature-docs/codex-interactive-guard-hook/SPEC.md` と `feature-docs/codex-guard-extglob-funcname/THREAT-MODEL.md` の編集。判定範囲の決定はこの SPEC に記録する。
- シェル `-n` の扱いの変更。
- version の変更。

## 前提

| ID | 内容 |
|----|------|
| A1 | 既存の silent 3 件（82、83、305 行目）を deny に変えてラベルを付け直す。265 行目のコメントを更新する。この SPEC にそれぞれの理由を書く。 |
| A2 | 内側の段は一段目の規則をそのまま使う（接続の引き継ぎ、判定できないものは読み飛ばし、動的なものは判定しない、関数本体は読み飛ばし、`-n` は一段目と同じ）。走査は明示的なスタックで行い、読み直しは FR3 のとおり上限を設ける。 |
| A3 | 2 つのコピーの module docstring の手順 7 を、すべての段の判定、明示的なスタック、上限を説明するように書き換える。 |
| A4 | `feature-docs/codex-interactive-guard-hook/SPEC.md` と `feature-docs/codex-guard-extglob-funcname/THREAT-MODEL.md` は編集しない。決定はこのフィーチャーの SPEC に記録する。 |
| A5 | シェル以外のインタプリタのコード文字列（`python -c`、`node -e` など）、`eval`、`xargs`、`find -exec` は範囲外のまま。 |
| A6 | version の変更は計画しない。main への push 時に Actions が version を上げる。 |
| A7 | 上限は 1,000,000 文字の module 定数 1 つで、1 つのコマンドで二段目以降に読み直すすべての `-c` 文字列の合計に適用する。 |
| A8 | 一段目の文字列は上限の計数に含めず、現行どおり常に判定する。 |

## 未解決事項

なし。

## 参考

- 要件定義書: `feature-docs/codex-guard-nested-bash-c/REQUIREMENTS.md`
- `.claude/rules/core-plugin-version-bump.md`
