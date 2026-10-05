---
title: "codex-guard-parser-fixes"
created_date: 2026-10-05
status: draft
---

# codex-guard-parser-fixes - 要件定義書

## 1. 概要

### 1.1 背景

`codex-hook-interactive-guard.py` の解析器に、対話起動を通してしまう見落としと、正当なコマンドを拒否する誤爆がある。PR #86 の review round 1 に medium の指摘が 6 件残っている。

### 1.2 目的

- 見落としを拒否に直す。対象は、シェルの `-c` の束・`--`・単独の `-`、シェルの `-h` / `-V`。
- 誤爆を通すように直す。対象は、二重引用符の中のコマンド置換、括弧・波括弧のグループへの標準入力の接続、パイプ直後の改行。読み切れないものは判定不能として通す。
- PR #86 の review round 1 に残った medium 6 件（`8145e7b41df8bd41` / `101256e4667a9ec6` / `71168f778ca98eb1` / `b151c1b9643b68b4` / `ad51d256afb757aa` / `a1b1320c32b41256`）を解消する。

### 1.3 スコープ

対象:

- `em-workflow/scripts/codex-hook-interactive-guard.py`
- `em-review/scripts/codex-hook-interactive-guard.py`
- `tests/test_codex_hook_interactive_guard.py`
- `feature-docs/codex-interactive-guard-hook/SPEC.md` の FR7（39 行）と処理系表の注記（126 行）

対象外:

- シェル以外の処理系の `-c` / `-m` / `-e` の読み方
- while / for / until / if / case の複合コマンド（今の挙動を保つ）
- `feature-docs/codex-interactive-guard-hook/REQUIREMENTS.md` と `reviews/round1.yaml`
- プラグインの version

## 2. ビジネス要件

### 2.1 ビジネス目標

- `codex-hook-interactive-guard.py` の解析器で、見落とし（対話起動を通してしまう）を拒否に直す。シェルの `-c` の束・`--`・単独の `-`、シェルの `-h` / `-V` が対象。
- 誤爆（正当なコマンドの拒否）を通すように直す。二重引用符の中のコマンド置換、括弧・波括弧のグループへの標準入力の接続、パイプ直後の改行が対象。読み切れないものは判定不能として通す。
- PR #86 の review round 1 に残った medium 6 件を解消する。

### 2.2 対象ユーザー

該当なし

### 2.3 期待される効果

2.1 に同じ

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 |
|----|--------|
| FR1 | シェルの -c を値を取らないフラグとして読む |
| FR2 | 情報表示用の短いオプションを処理系ごとに定義する |
| FR3 | 二重引用符の中のコマンド置換を 1 つの塊として読む |
| FR4 | 括弧・波括弧のグループに標準入力の接続を引き継ぐ |
| FR5 | パイプ直後の改行で接続情報を保つ |
| FR6 | 2 つのコピーの同一性 |
| FR7 | 再発を検出するテスト |
| FR8 | SPEC FR7 の修正 |

### 4.2 機能詳細

#### FR1: シェルの -c を値を取らないフラグとして読む

- シェル系（bash / sh / zsh / dash / ksh）では、`-c` を値を取らないフラグとして扱う。
- 同じ束の残りの文字と、後続のオプション語（`-o` / `-O` / `--rcfile` / `--init-file` の値を含む）を読む。
- `--` または単独の `-` でオプションの読み取りを止める。
- そのうえで、最初のオペランドを `-c` の文字列として 1 段判定する。
- 束の中や後続の語にある `i` は `-i` として拒否する。
- 最初のオペランドより後ろの語はオプションとして読まない。
- 拒否する: `bash -cx 'python3 -i'`、`bash -ce 'python3 -i'`、`bash -c -- 'python3 -i'`、`bash -c - 'python3 -i'`、`bash -ci 'python3'`
- シェル以外の処理系の `-c` / `-m` / `-e` の読み方は変えない。

#### FR2: 情報表示用の短いオプションを処理系ごとに定義する

- 全処理系に共通の `INFO_LETTERS` をやめ、情報表示用の短いオプションを処理系ごとに定義する。
- シェル系（bash / sh / zsh / dash / ksh）には情報表示用の短いオプションを置かない。`h` も `V` も情報表示としない。
- `bash -h` / `sh -h` / `zsh -V` / `dash -V` / `bash -V` は、他に条件が無ければ引数なし起動として拒否する。
- シェル以外の処理系は今の判定を保つ（`python3 -h` / `-V` / `-VV`、`node -v`、`perl -v` などは通す）。
- 長いオプション（`--version` / `--help` と各処理系の `info_long`）の扱いは変えない。

#### FR3: 二重引用符の中のコマンド置換を 1 つの塊として読む

- 二重引用符の中の `$( ... )`（`$(( ... ))` を含む）と `` ` ... ` `` を、閉じるまで 1 つの塊として読み飛ばす。
- 中に現れる `"` で外側の引用を閉じない。
- その語は dynamic とし、置換の中身は判定しない。
- 閉じていない、入れ子を読み切れないといった場合は判定不能として何も出力しない。
- 通す: `echo "$(echo "; python3 -i")"`

#### FR4: 括弧・波括弧のグループに標準入力の接続を引き継ぐ

- サブシェルの括弧 `( ... )` と波括弧のグループ `{ ...; }` が対象。
- 次のときは、グループ内の全コマンドを接続ありとして扱う。
    - グループがパイプの右側にある
    - グループを閉じた後ろに標準入力のリダイレクト（`<`、`<<`、`<<<`、`<&`、`0<`）がある
- 入れ子のグループにも伝える。
- `{` と `}` は、コマンドの位置にある単独の語のときだけグループとして読む。
- 標準入力以外のリダイレクト（`2>/dev/null`、`>out`）では接続ありにしない。
- `-i` 付きの起動は、接続があっても今までどおり拒否する。
- 読み切れないグループは判定不能として通す。
- 通す: `(python3) < /dev/null`、`printf 'print(1)\n' | (echo ignored; python3)`、`{ python3; } < /dev/null`、`printf 'print(1)\n' | { echo ignored; python3; }`
- while / for / until / if / case の複合コマンドは対象外で、今の挙動を保つ。

#### FR5: パイプ直後の改行で接続情報を保つ

- `|` または `|&` の右側のコマンドを待っている間は、空のコマンドしか生まない改行・空行・コメント行で `pipe_pending` を消さない。
- heredoc 本文を挟む場合も同じ。
- 通す: 複数行のパイプの右側の python3（`"echo x |\npython3"`）
- `&&` / `||` の後ろの改行では接続ありにしない。

#### FR6: 2 つのコピーの同一性

- `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` を同じ変更の中で直し、バイト単位で同一に保つ。
- モジュールの docstring（判定手順）と、`INFO_LETTERS` まわりのコメントを新しい挙動に合わせて直す。

#### FR7: 再発を検出するテスト

- `tests/test_codex_hook_interactive_guard.py` の `CASES` に、FR1〜FR5 の再現コマンドと境界のケースを `(期待する判定, ラベル, コマンド)` で足し、両コピーに流す。
- 281 行目の `bash -cx 'python3 -i'` の期待値を `deny` に直し、ラベルを実際の挙動に合わせる。
- 281 行目以外の既存ケースの期待値は変えない。
- コマンド文字列は表の中で重複させない。

#### FR8: SPEC FR7 の修正

- `feature-docs/codex-interactive-guard-hook/SPEC.md` の FR7（39 行）と処理系表の注記（126 行）を直す。
- 「`--version` / `-V` / `-h` / `--help` は拒否しない」の共通扱いをやめる。
- 情報表示用の短いオプションは処理系ごとに定まり、シェル系には無い（シェルの `-h` / `-V` は拒否しない対象に含めない）と書く。
- `REQUIREMENTS.md` と `reviews/round1.yaml` は変更しない。

## 5. 非機能要件

- NFR1: 誤爆を避けることを優先する。読み切れない入力は判定不能として何も出力せず、exit 0 で抜ける。修正によって、新しく deny を出す読み違いを持ち込まない。
- NFR2: 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（`TestStaticConstraints` を満たす）。判定はコマンド文字列だけで決まり、作業ディレクトリや環境変数に左右されない。
- NFR3: プラグインの version は変えない。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 標準ライブラリだけを使い、ファイル・ネットワーク・子プロセスに触れない（NFR2）。
- 2 つのコピーをバイト単位で同一に保つ（FR6）。

### 9.2 ビジネス上の制約

- プラグインの version は変えない（NFR3）。
- `feature-docs/codex-interactive-guard-hook/REQUIREMENTS.md` と `reviews/round1.yaml` は変更しない（FR8）。

### 9.3 スケジュール制約

なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-guard-parser-fixes/**`
- `test-docs/codex-guard-parser-fixes/**`

`feature-docs/codex-guard-parser-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-guard-parser-fixes/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-guard-parser-fixes/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-guard-parser-fixes/` ディレクトリを生成しないが、宣言された `test-docs/codex-guard-parser-fixes/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `bash -cx 'python3 -i'`、`bash -ce 'python3 -i'`、`bash -c -- 'python3 -i'`、`bash -c - 'python3 -i'`、`bash -ci 'python3'` は、両コピーで拒否の JSON を出す。
- [ ] AC2: `bash -h`、`sh -h`、`zsh -V`、`dash -V` は、両コピーで拒否の JSON を出す。`python3 -h`、`python3 -V`、`python3 -VV`、`node -v`、`perl -v` は何も出力しない。
- [ ] AC3: `echo "$(echo "; python3 -i")"` は、両コピーで何も出力しない。
- [ ] AC4: `(python3) < /dev/null`、`printf 'print(1)\n' | (echo ignored; python3)`、`{ python3; } < /dev/null`、`printf 'print(1)\n' | { echo ignored; python3; }` は、両コピーで何も出力しない。
- [ ] AC5: `"echo x |\npython3"` は、両コピーで何も出力しない。
- [ ] AC6: `tests/test_codex_hook_interactive_guard.py` の `CASES` に AC1〜AC5 の各コマンドがあり、旧 281 行目の `bash -cx 'python3 -i'` の期待値が `deny` になっている。`python3 -m unittest tests.test_codex_hook_interactive_guard` がすべて通る。
- [ ] AC7: 2 つのコピーがバイト単位で同一である。
- [ ] AC8: SPEC.md の FR7 と 126 行の注記が、情報表示用の短いオプションを処理系ごとに定めていて、シェル系の `-h` / `-V` を拒否しない対象に含めていない。REQUIREMENTS.md は変更されていない。
- [ ] AC9: `python3 -m unittest discover -s tests` がすべて通る。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1（シェルの -c / deny）: `bash -cx 'python3 -i'`、`bash -ce 'python3 -i'`、`bash -c -- 'python3 -i'`、`bash -c - 'python3 -i'`、`bash -ci 'python3'`、`bash -c -i 'python3'`、`bash -co pipefail 'python3 -i'`、`bash -c -o pipefail 'python3 -i'`、`sh -cx 'python3'`
- [ ] TS2（シェルの -c / silent）: `bash -c 'echo hi' -i`、`bash -cx 'echo hi'`、`bash -c -- 'echo hi'`、`bash -cx`（文字列なし）、`echo | bash -cx python3`、`bash -cx 'python3' < f`。`python3 -ci` は既存ケースのまま silent
- [ ] TS3（情報表示 / deny）: `bash -h`、`sh -h`、`zsh -h`、`zsh -V`、`dash -V`、`bash -V`
- [ ] TS4（情報表示 / silent）: 既存の `python3 -h`、`python3 -V`、`python3 -VV`、`node -v`、`perl -v`、`bash --version` は silent のまま
- [ ] TS5（二重引用符 / silent）: `echo "$(echo "; python3 -i")"`、`` echo "`echo x`; python3 -i" `` のうち引用内に閉じるもの、`echo "$((1+2)); python3 -i"`、`echo "$(python3 -i)"`（置換の中身は判定しない）、閉じていない `echo "$(echo "`
- [ ] TS6（二重引用符 / deny）: `echo "$(echo x)"; python3 -i`（引用の外の起動は拒否のまま）
- [ ] TS7（グループ / silent）: `(python3) < /dev/null`、`printf 'print(1)\n' | (echo ignored; python3)`、`(python3) 0< f`、`(python3) <<EOF\nprint(1)\nEOF`、`( (python3) ) < f`、`{ python3; } < /dev/null`、`printf 'print(1)\n' | { echo ignored; python3; }`
- [ ] TS8（グループ / deny）: `(python3) 2>/dev/null`、`(python3) > out`、`(python3) | cat`、`(python3 -i) < /dev/null`、`echo x | (python3 -i)`、`{ python3; } 2>/dev/null`、`{ python3; }`
- [ ] TS9（複数行のパイプ / silent）: `"echo x |\npython3"`、`"echo x |\n\npython3"`、`"echo x | # c\npython3"`、`"cat <<EOF |\nbody\nEOF\npython3"`
- [ ] TS10（複数行のパイプ / deny）: `"echo x &&\npython3"`、`"echo x ||\npython3"`
- [ ] TS11（回帰）: 281 行目以外の既存 `CASES` がすべて同じ判定のまま。両コピーのバイト一致・静的制約・rules 文書のテストが通る

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 見落とし | 対話起動を通してしまうこと |
| 誤爆 | 正当なコマンドを拒否すること |
| 判定不能 | 読み切れない入力。何も出力せず、exit 0 で抜ける |
| 両コピー | `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` |

## 14. 確認事項

### 14.1 確認済み事項

- [x] シェルの `-c` の後ろの単独の `-`: `--` と同じくオプションの読み取りを止め、次の語を `-c` の文字列として判定する。
- [x] 情報表示用の短いオプションの範囲: シェル系（bash / sh / zsh / dash / ksh）には置かない（`-h` / `-V` とも外す）。他の処理系は今のまま保つ。
- [x] 標準入力の接続を引き継ぐグループの範囲: `( )` と `{ }` の両方。
- [x] 旧フィーチャーの文書: `SPEC.md` の FR7（39 行）と処理系表の注記（126 行）だけを直し、`REQUIREMENTS.md` は変更しない。
- [x] デザインステップ: 省略する。

### 14.2 未確認・保留事項

なし

### 14.3 前提

| ID | 内容 | 影響度 | 可逆 |
|----|------|--------|------|
| A1 | 二重引用符の中のコマンド置換の中身は判定しない。引用符の外のコマンド置換を判定しない今の挙動と揃える。 | 低 | ○ |
| A2 | `-c` を値を取らないフラグとして読み直すのはシェル系だけにする。他の処理系の `-c` / `-m` / `-e` の読み方は変えない。 | 低 | ○ |
| A3 | シェルの `-c` の文字列より後ろの語は `$0` 以降の引数で、オプションとして読まない。 | 低 | ○ |
| A4 | 内側の文字列を判定するのは 1 段だけ。標準入力の接続は外側から引き継ぐ。 | 低 | ○ |
| A5 | コマンド文字列が無いシェルの `-c`（`bash -c`、`bash -cx`）は、何も出力しない。 | 低 | ○ |
| A6 | 281 行目以外の既存 `CASES` の期待値は変えない。 | 中 | ○ |
| A7 | `SPEC.md` の 126 行（処理系表の注記）は FR7 と同じ内容なので、FR7 と一緒に直す。 | 低 | ○ |
| A8 | `reviews/round1.yaml` と `REQUIREMENTS.md` は書き換えない。プラグインの version も触らない。 | 低 | ○ |
| A9 | `{` と `}` は、コマンドの位置にある単独の語のときだけグループとして扱う。`{a,b}` のような語の一部は対象外。 | 低 | ○ |

## 15. 参考資料

- `feature-docs/codex-interactive-guard-hook/SPEC.md`
- `feature-docs/codex-interactive-guard-hook/reviews/round1.yaml`
