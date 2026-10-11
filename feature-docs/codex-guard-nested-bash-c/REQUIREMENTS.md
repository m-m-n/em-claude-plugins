---
title: "codex-guard-nested-bash-c"
created_date: 2026-10-11
status: draft
---

# codex-guard-nested-bash-c - 要件定義書

## 1. 概要

### 1.1 背景
codex-hook-interactive-guard は、シェル `-c` の文字列を一段目だけ判定している。二段目以降の `-c` 文字列の中にある対話的なインタプリタやシェルの起動は判定されない。

### 1.2 目的
- codex-hook-interactive-guard が、シェル `-c` の文字列の中にある対話的なインタプリタやシェルの起動を、入れ子の段数によらず拒否する。無人の Codex レビューが入れ子の REPL で止まらないようにする。
- 判定範囲の決定（すべての段）とその理由を、このフィーチャーの SPEC に記録する。

### 1.3 スコープ

**対象**:
- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` の `_scan` と module docstring
- `tests/test_codex_hook_interactive_guard.py` の `CASES` とテスト

**対象外**:
- シェル以外のインタプリタのコード文字列（`python -c`、`node -e` など）、`eval`、`xargs`、`find -exec`
- `feature-docs/codex-interactive-guard-hook/SPEC.md` と `feature-docs/codex-guard-extglob-funcname/THREAT-MODEL.md` の編集
- シェル `-n` の扱いの変更（一段目と同じ規則のまま）
- version の変更

## 2. ビジネス要件

### 2.1 ビジネス目標
- 入れ子の `-c` 文字列の中の対話起動を、何段目でも拒否する。
- 判定範囲の決定と理由を SPEC に残す。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | すべての段の -c 文字列を判定する | 二段目以降の `-c` 文字列も一段目と同じ規則で判定する |
| FR2 | 再帰ではなく明示的なスタックで走査する | 入れ子の走査を作業リストで行い、判定順は現行と同じにする |
| FR3 | 読み直す文字数の上限 | 二段目以降で読み直す文字数の合計に上限を設け、超えた分は通す |
| FR4 | 既存の silent ケースを deny に変える | 既存 CASES 3 件の期待を deny に変え、ラベルとコメントを直す |
| FR5 | テストケースの追加 | 入れ子の deny ケースと silent ケースを CASES に足す |
| FR6 | docstring の書き換え | module docstring の手順 7 を書き換える |
| FR7 | 2 つのコピーをバイト単位で同一に保つ | 2 つのコピーを一緒に変更する |

### 4.2 機能詳細

#### FR1: すべての段の -c 文字列を判定する

**説明**: `-c` で起動したシェル（bash sh zsh dash ksh。`-lc`、`-cx` のようなまとめ書きを含む）のリテラルな第一オペランドを、どの段でも解析して判定する。

**ビジネスルール**:
- 各段に一段目の規則を使う。
    - 文字列を持つコマンドの標準入力の接続は、その文字列の中のすべてのコマンドに引き継ぐ。
    - 判定できない文字列（クォートの不一致、終端のないヒアドキュメント、閉じていないグループ）は読み飛ばし、通す。
    - 動的なオペランドは判定しない。
    - 関数本体は判定しない。
    - ラッパーとオプションは一段目と同じように読む。
- シェル `-n` は一段目とまったく同じに扱う。

#### FR2: 再帰ではなく明示的なスタックで走査する

**説明**: 入れ子の `-c` 文字列の走査は、再帰ではなく明示的なスタック（作業リスト）で行う。

**ビジネスルール**:
- コマンドの判定順は現行と同じにする。
    - 1 つの文字列の中のコマンドを順に判定する。
    - 入れ子の文字列の中のコマンドは、その文字列を持つコマンドより後ろのコマンドより先に判定する。
- その順で最初に拒否対象となった起動が、拒否理由を決める。

#### FR3: 読み直す文字数の上限

**説明**: module 定数で、二段目以降の `-c` 文字列から読み直す文字数の合計に上限を設ける。合計はコマンド全体で数える。上限は 1,000,000 文字とする。

**ビジネスルール**:
- 一段目の文字列は現行どおり判定し、上限の計数に含めない。
- 次の文字列を読むと上限を超える時点で、その文字列と、それ以降の二段目以降の文字列はすべて解析せず、通す。
- 上限を超えたことは拒否理由にしない。
- 0 段目と一段目のコマンドは引き続き判定する。

#### FR4: 既存の silent ケースを deny に変える

**説明**: `tests/test_codex_hook_interactive_guard.py` の `CASES` のうち次の 3 件を silent から deny に変え、ラベルを新しい挙動を表すものにする。

| 行 | コマンド |
|----|----------|
| 82 | `bash -c "bash -c 'python3 -i'"` |
| 83 | `sh -c 'bash -lc "python3 -i"'` |
| 305 | `bash -cx "bash -c 'python3 -i'"` |

**ビジネスルール**:
- 265 行目のコメント（`# bash -c: one level of literals` で始まるもの）を書き換える。
- SPEC に、それぞれの期待を変えた理由を書く。

#### FR5: テストケースの追加

**説明**: `CASES` に、二段以上の `-c` 文字列の中の対話起動の deny ケースと、内側の段に一段目の規則を適用した silent ケースを足す（12. テストシナリオの TS-1、TS-2）。

#### FR6: docstring の書き換え

**説明**: 2 つのコピーの module docstring の手順 7（`the first operand is judged once, the same way`）を書き換える。

**ビジネスルール**:
- 文字列をどの段でも同じ規則で判定することを書く。
- 走査に明示的なスタックを使うことを書く。
- 文字数の上限を超えた文字列は通すことを書く。

#### FR7: 2 つのコピーをバイト単位で同一に保つ

**説明**: `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を一緒に変更し、バイト単位で同一に保つ。

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR3: 深い入れ子や多数の入れ子でも時間内に応答する。終了ステータス 0、標準エラー出力は空、標準出力は空か deny オブジェクトちょうど 1 つ（`TestMalformedAndDeepInput` の形、タイムアウト 60 秒）。

### 5.2 セキュリティ要件
- NFR1: 標準ライブラリのみを使う。ネットワーク、ファイル書き込み、サブプロセスを使わない（`TestStaticConstraints` が通る状態を保つ）。
- NFR2: 誤った拒否より通過を優先する。判定できないものと上限を超えたものは通す。一段目の規則以外の読み方を追加しない。

### 5.4 保守性要件
- NFR4: `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。
- NFR5: version を変えない。main への push 時に Actions が version を上げる（`.claude/rules/core-plugin-version-bump.md`）。

## 6. UI/UX要件

UI はない。デザインステップは行わない。

## 9. 制約条件

### 9.1 技術的制約
- 標準ライブラリのみ。ネットワーク、ファイル書き込み、サブプロセスを使わない。
- 2 つのコピーはバイト単位で同一に保つ。
- version を変えない。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-nested-bash-c/**`
- `test-docs/codex-guard-nested-bash-c/**`

`feature-docs/codex-guard-nested-bash-c/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-nested-bash-c/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-nested-bash-c/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-nested-bash-c/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-nested-bash-c/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 対応策 |
|------|--------|
| 再帰で走査すると、深い入れ子で発生した例外を `main()` が黙って通す | 明示的なスタックで走査する（FR2） |
| 入れ子の文字列を読み直す処理時間 | 二段目以降で読み直す文字数の合計に上限を設け、超えた分は通す（FR3） |

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: SPEC に、二段目以降の `-c` 文字列を判定すること（すべての段）と、その理由が記録されている。
- [ ] AC2: `CASES` に、二段以上の `bash -c` 文字列の中の対話起動とプログラム指定なしの起動の deny ケースがある。タスクの extglob の例を含む。
- [ ] AC3: 82、83、305 行目の `CASES` が deny を期待し、SPEC にそれぞれの変更理由が書かれている。
- [ ] AC4: 内側の段でも一段目の規則が保たれる。接続された入力、動的な文字列、判定できない文字列、関数本体、無害な文字列は silent のまま。
- [ ] AC5: `_scan` が入れ子の文字列を再帰なしの明示的なスタックで走査する。二段目以降で読み直す文字数に上限があり、上限を超えた文字列は通す。
- [ ] AC6: 深い入れ子と多数の入れ子の入力に、テストのタイムアウト内で、終了ステータス 0、空の標準エラー出力で応答する。
- [ ] AC7: 2 つのコピーの docstring 手順 7 が、すべての段の判定、明示的なスタック、上限を説明している。
- [ ] AC8: 2 つのコピーがバイト単位で同一で、`python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。

## 12. テストシナリオ

### 12.1 テスト観点

#### TS-1: 入れ子の deny ケース（CASES）
対応: FR1、FR5、AC2
- [ ] deny: `bash -c "bash -c 'python3 -i'"`（82 行目、変更）
- [ ] deny: `sh -c 'bash -lc "python3 -i"'`（83 行目、変更）
- [ ] deny: `bash -cx "bash -c 'python3 -i'"`（305 行目、変更）
- [ ] deny: `bash -c "bash -c 'python3'"`（二段目のプログラム指定なしの起動）
- [ ] deny: `bash -c 'bash -O extglob -c "time /bin/true?()\n(python3 -i)"'`（タスクの extglob の例）
- [ ] deny: 最も内側に `python3 -i` を持つ三段の文字列
- [ ] deny: 内側のシェルが `zsh -c` / `bash -lc` / `env FOO=1 bash -c`
- [ ] deny: `bash -c "bash -c 'cd x && python3 -i'"`

#### TS-2: 入れ子の silent ケース（CASES）
対応: FR1、NFR2、AC4
- [ ] silent: `echo | bash -c "bash -c python3"`（パイプの接続が二段目に届く）
- [ ] silent: `bash -c "bash -c python3" < f`（標準入力のリダイレクトが二段目に届く）
- [ ] silent: `bash -c "bash -c 'echo x | python3'"`
- [ ] silent: `bash -c 'bash -c "$CMD"'`（内側の文字列が動的）
- [ ] silent: `bash -c "bash -c 'echo hi'"`（無害な文字列）
- [ ] silent: クォートが不一致の内側の文字列
- [ ] silent: `python3 -i` を持つ内側の関数本体（`bash -c "bash -c 'f() { python3 -i; }'"`）

#### TS-3: 深い入力と多数の入れ子に時間内に応答する
対応: FR2、FR3、NFR3、AC5、AC6
- [ ] `python3 -i` を何段もクォートして作ったコマンド（例: `shlex.quote` を繰り返し適用）。再帰を使った場合に Python の既定の再帰上限を超える深さ、または上限が許す深さにする。フックがタイムアウト内に、終了ステータス 0、空の標準エラー出力で応答する。
- [ ] 合計が上限を超える多数の兄弟の二段目文字列。フックがタイムアウト内に、終了ステータス 0、空の標準エラー出力で応答する。

#### TS-4: 上限の挙動
対応: FR3、AC5
- [ ] 合計が上限を超える二段目の文字列の後ろに、上限を超えた位置の二段目 `python3 -i` → silent（上限超過は拒否理由にしない）
- [ ] 上限に達する前の二段目 `python3 -i` → deny
- [ ] 一段目の判定は影響を受けない。合計が上限を超える一段目の文字列の後ろに、一段目の `python3 -i` → deny

#### TS-5: docstring のマーカー
対応: FR6、AC7
- [ ] `TestGuardDocumentation` が、2 つのコピーで、すべての段の判定、明示的なスタック、上限のマーカー文を確認する。

#### TS-6: 既存スイートとコピー
対応: FR7、NFR1、NFR4、AC8
- [ ] `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。`TestCopies`（バイト単位の同一性）と `TestStaticConstraints` を含む。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 0 段目 | フックが受け取ったコマンドそのもの |
| 一段目の文字列 | 0 段目のコマンドにある、シェル `-c` のリテラルな第一オペランド |
| 二段目以降の文字列 | 一段目以降の文字列の中にある、シェル `-c` のリテラルな第一オペランド |
| 上限 | 二段目以降で読み直す文字数の、コマンド全体での合計の上限（1,000,000 文字） |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 入れ子の `-c` 文字列を何段目まで判定するか: すべての段（all_levels）。一段目と同じ規則で判定する。条件は、明示的なスタックで走査すること、読み直す文字数の合計に上限を設けて超えた分は通すこと、深い入れ子と多数の入れ子で時間内に応答することをテストで確かめること、既存の silent 3 件を deny に変えて理由を SPEC に書くこと。`-n` の扱いは一段目と同じ規則のまま変えない。
- [x] デザインステップ: 行わない（UI なし）。

**前提**:

| ID | 内容 | 影響度 |
|----|------|--------|
| A1 | 既存の silent 3 件（82、83、305 行目）を deny に変えてラベルを付け直す。265 行目のコメントを更新する。SPEC にそれぞれの理由を書く。 | 中 |
| A2 | 内側の段は一段目の規則をそのまま使う（接続の引き継ぎ、判定できないものは読み飛ばし、動的なものは判定しない、関数本体は読み飛ばし、`-n` は一段目と同じ）。走査は明示的なスタックで行い、読み直しは FR3 のとおり上限を設ける。 | 中 |
| A3 | 2 つのコピーの module docstring の手順 7 を、すべての段の判定、明示的なスタック、上限を説明するように書き換える。 | 低 |
| A4 | `feature-docs/codex-interactive-guard-hook/SPEC.md` と `feature-docs/codex-guard-extglob-funcname/THREAT-MODEL.md` は編集しない。決定はこのフィーチャーの SPEC に記録する。 | 低 |
| A5 | シェル以外のインタプリタのコード文字列（`python -c`、`node -e` など）、`eval`、`xargs`、`find -exec` は範囲外のまま。 | 低 |
| A6 | version の変更は計画しない。main への push 時に Actions が version を上げる。 | 低 |
| A7 | 上限は 1,000,000 文字の module 定数 1 つで、1 つのコマンドで二段目以降に読み直すすべての `-c` 文字列の合計に適用する。 | 中 |
| A8 | 一段目の文字列は上限の計数に含めず、現行どおり常に判定する。 | 中 |

### 14.2 未確認・保留事項
なし。

## 15. 参考資料

- `.claude/rules/core-plugin-version-bump.md`
