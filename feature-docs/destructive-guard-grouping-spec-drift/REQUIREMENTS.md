---
title: "destructive-guard-grouping-spec-drift"
created_date: 2026-09-27
status: draft
---

# destructive-guard-grouping-spec-drift - 要件定義書

## 1. 概要

### 1.1 背景

feature `destructive-guard-write-target-scoping` のレビュー round2 で high と判定された 4 件が、`deferred` のまま未修正で残っている。内訳は、既存のガード迂回 1 件と、SPEC と実装のドリフト 3 件。

- `d60553d13cb54e0c`: `( )` / `{ }` などのグルーピング・複合構文でコマンドを囲むと、`em-workflow/hooks/destructive-guard.py` が中のコマンドを一度も判定しない。`ALLOW_NON_DESTRUCTIVE=True` の構成では、これらは最終的に無条件 allow になる。
- `bb74a3458679e1b4`: mv の write target 範囲について、前 feature の SPEC FR2(c) / Edge Cases と実装が食い違っている。
- `bafd6e8260de4337`: rsync / git clone / tar / unzip / curl / wget の宛先判定が前 feature の SPEC FR2 の抽出元に無く、ケースも無い。
- `7f7144aea35f534f`: 前 feature の SPEC FR6「rm 判定は不変」に対し、`head()` / `statements()` の入力整形によって rm の判定が変わっている。

### 1.2 目的

- グルーピング・複合構文（`( )`、`{ }`、if/elif/else、for/select、while/until、`!`、case、関数定義）で囲むと `destructive-guard.py` の全判定が素通りになる穴を塞ぐ。
- 前 feature から持ち越した SPEC と実装のドリフト 3 件（`bb74a3458679e1b4` / `bafd6e8260de4337` / `7f7144aea35f534f`）を決着させ、前 feature の SPEC.md と REQUIREMENTS.md がマージ済み実装の実際の挙動を記述する状態にする。
- 検知力を変えた箇所には、`.claude/rules/hook-tests.md` の要求どおり `em-workflow/hooks/tests/destructive-guard-cases.json` に ask / allow ケースを添え、後の退行をスイートで検出できるようにする。

### 1.3 スコープ

**対象**:

- `em-workflow/hooks/destructive-guard.py`（グルーピング・複合構文の内側にあるコマンドの判定、閉じ括弧トークンの扱い、tar `-C` の抽出モード限定）
- `em-workflow/hooks/tests/destructive-guard-cases.json`（ケース追加と、mv ケース 1 件のラベル修正）
- `feature-docs/destructive-guard-write-target-scoping/SPEC.md` と `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md`（実装に合わせた改訂）
- `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の version フィールド

**対象外**:

- `em-workflow/hooks/failed-run-cleanup-guard.py` の変更と、failed-run-cleanup-guard への委譲判定（`matches_target_shape` / `strip_grouping_prefix` / `_deferral_head` の判定結果）の変更。
- 前 feature のレビュー round2 で deferred になった medium 指摘。ただし FR6 で決着させる tar `-C` の誤爆（`ed5c0ae5ec37e137`）は除く。対象外となるのは次のとおり: `<>` の SPEC ドリフト（`a9ef8f56bd1a375a`）、deletion_alternative のクォート（`02d9c33015f12347`）、末尾スラッシュ無し保護ディレクトリの deny→ask 後退、`~/.claude/plugins/` が `SELF_CONFIG` に無い件、`bash -lc` / `bash -cx` の迂回、`wget -P` / `curl --output-dir`、`SELF_CONFIG` を `TRANSCRIPT` より先に評価する件、`MAX_SHELL_PAYLOAD_EXPANSIONS` が総数上限である件、未使用の `TARGET_DIR_FLAGS`、`_TrackingLexer` が shlex の非公開状態に依存する件。
- `coproc`、コマンドとしての算術 `(( ))` / `[[ ]]`、入れ子の括弧を含む置換本体（`$( ( ... ) )`。`SUBSTITUTION` 正規表現が一致しない）。

## 2. ビジネス要件

### 2.1 ビジネス目標

- グルーピング・複合構文でコマンドを囲むと `destructive-guard.py` が全判定をスキップする迂回を塞ぐ。対象は `( )`、`{ }`、if/elif/else、for/select、while/until、`!`、case、関数定義。`ALLOW_NON_DESTRUCTIVE=True` の下では、これらのコマンドは現状、無条件 allow で終わる。
- 前 feature `destructive-guard-write-target-scoping` から deferred で持ち越したレビュー round2 の high 指摘 `bb74a3458679e1b4` / `bafd6e8260de4337` / `7f7144aea35f534f` を決着させ、前 feature の SPEC.md と REQUIREMENTS.md がマージ済み実装の実際の挙動を記述するようにする。
- 検知力の変更には必ず `em-workflow/hooks/tests/destructive-guard-cases.json` の ask / allow ケースを添える（`.claude/rules/hook-tests.md`）。後の退行はスイートで検出される。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| 無人実行（claude-batch）の走行者 | ask が deny に降格されるため、誤爆 1 件で走行がその場で止まる。迂回が残るとガードが働かない |

### 2.3 期待される効果

- グルーピング・複合構文の内側にあるコマンドが、単体で書いたときと同じ判定を受ける。
- 前 feature の SPEC.md / REQUIREMENTS.md と実装が一致する。
- 検知力を変えた箇所がケース表で固定され、退行が検出できる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | グルーピング・複合構文の内側のコマンドが単体時と同じ判定を受ける | 無人実行の走行者 | 高 |
| UC02 | データとしての予約語・括弧が誤爆しない | 無人実行の走行者 | 高 |
| UC03 | 前 feature の SPEC / REQUIREMENTS が実装と一致する | 無人実行の走行者 | 中 |

### 3.2 ユースケース詳細

#### UC01: グルーピング・複合構文の内側のコマンドが単体時と同じ判定を受ける

**アクター**: 無人実行の走行者

**事前条件**:

- `destructive-guard.py` が PreToolUse(Bash) で呼ばれる。

**基本フロー**:

1. `( rm -rf /home/sakura/x )` のようなコマンドが実行される。
2. グルーピング構文がコマンド位置に置いたコマンド（`rm -rf /home/sakura/x`）が判定対象になる。
3. 単体の `rm -rf /home/sakura/x` と同じく deny となる。

**代替フロー**:

- `(rm -rf /tmp/x)` のように閉じ括弧が引数に連結していても、`)` は rm の対象に数えない（FR3）。
- `(cp /tmp/x ~/.claude/settings.json)>/dev/null` の `)>` は閉じ括弧と実リダイレクトに分かれ、`/dev/null` はリダイレクト先としてのみ判定される（FR3）。

**事後条件**:

- グルーピング・複合構文で囲んでも判定が緩まない。

#### UC02: データとしての予約語・括弧が誤爆しない

**アクター**: 無人実行の走行者

**事前条件**:

- 予約語や括弧文字を、コマンド位置以外（引数・クォート・ヒアドキュメント本文・コミットメッセージ・for ヘッダの語・case パターン文字列）に含むコマンドが実行される。

**基本フロー**:

1. `echo if then fi do done` が実行される。
2. 予約語は引数位置にあるため、グルーピング構文として扱わない。
3. 判定は allow のまま。

**事後条件**:

- 迂回の修正によって新たな誤爆が生じない。

#### UC03: 前 feature の SPEC / REQUIREMENTS が実装と一致する

**アクター**: 無人実行の走行者

**事前条件**:

- 前 feature の実装が main にマージ済みである（A-5）。

**基本フロー**:

1. 前 feature の SPEC.md の FR2 / FR6 / Edge Cases と関連箇所を、実装の挙動に合わせて改訂する（FR10）。
2. 前 feature の REQUIREMENTS.md の該当箇所を同じ内容で改訂する（FR11）。

**事後条件**:

- 同じドリフト指摘がレビューで再燃しない状態になる。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | グルーピング・複合構文のケースを修正前に追加する | 再現・同等判定・誤爆防止のケースを追加し、修正前に red を確認する | 高 |
| FR2 | グルーピング・複合構文の内側のコマンドを判定する | コマンド位置に置かれたコマンドに、単体時と同じ判定を出す | 高 |
| FR3 | 連結した閉じトークンを引数・対象に数えない | 素の `)` 演算子トークンはどのチェックでも引数に含めない | 高 |
| FR4 | データとしての予約語・括弧で新たな誤爆を出さない | 予約語・括弧はコマンド位置でのみ構文として扱う | 高 |
| FR5 | グルーピング修正の適用範囲 | main() の全セグメント単位チェックに適用し、委譲判定は変えない | 高 |
| FR6 | 宛先 6 族を残し、tar -C は展開モードに限る | tar の `-C` / `--directory` は展開モードでのみ write target | 高 |
| FR7 | 宛先 6 族のケースを追加する（tar のモード含む） | 各族に ask / allow ケースを添える | 高 |
| FR8 | head() / statements() の入力整形による rm 判定変化を固定する | sudo -u / bash -c / eval 経由の rm ケースを追加する | 中 |
| FR9 | 誤解を招く mv ケースのラベルを直す | コマンドと期待判定は変えない | 中 |
| FR10 | 前 feature の SPEC.md を実装に合わせて改訂する | FR2 / Edge Cases / FR6 と矛盾する周辺記述を直す | 高 |
| FR11 | 前 feature の REQUIREMENTS.md を同じ内容で改訂する | SPEC.md の改訂と一致させる | 高 |
| FR12 | em-workflow の version を 2 箇所で patch 上げする | 0.2.12 → 0.2.13 | 中 |

### 4.2 機能詳細

#### FR1: グルーピング・複合構文のケースを修正前に追加する

**説明**: `destructive-guard.py` を変更する前に、`em-workflow/hooks/tests/destructive-guard-cases.json` へ `[期待する判定, ラベル, コマンド]` の形で次のケースを追加し、スイートを走らせて red を確認する。期待判定はランナーが出す判定（`CLAUDE_BATCH` を外した状態）とする。

(1) チケットの再現 5 件。いずれも単体の `rm -rf $HOME/x` に合わせて ask:

- `( rm -rf $HOME/important )`
- `{ rm -rf $HOME/important; }`
- `if true; then rm -rf $HOME/x; fi`
- `for f in a; do rm -rf $HOME/x; done`
- `! rm -rf $HOME/x`

(2) リテラル対象の同等判定。いずれも単体の `rm -rf /home/sakura/x` に合わせて deny:

- `( rm -rf /home/sakura/x )`
- `(rm -rf /home/sakura/x)`
- `{ rm -rf /home/sakura/x; }`
- `if true; then rm -rf /home/sakura/x; fi`
- `if false; then :; elif true; then :; else rm -rf /home/sakura/x; fi`
- `if rm -rf /home/sakura/x; then :; fi`
- `while true; do rm -rf /home/sakura/x; done`
- `until rm -rf /home/sakura/x; do :; done`
- `for f in a; do rm -rf /home/sakura/x; done`
- `! rm -rf /home/sakura/x`
- `case x in a) rm -rf /home/sakura/x;; esac`
- `case x in (a) rm -rf /home/sakura/x;; esac`
- `case x in a|b) rm -rf /home/sakura/x;; esac`
- 複数行の形:

  ```
  case $x in
    a) rm -rf /home/sakura/x ;;
  esac
  ```

- `f() { rm -rf /home/sakura/x; }; f`
- `function f { rm -rf /home/sakura/x; }; f`
- `( { rm -rf /home/sakura/x; } )`
- `if true; then ( sudo rm -rf /home/sakura/x ); fi`
- `bash -c '( rm -rf /home/sakura/x )'`
- `echo $(if true; then rm -rf /home/sakura/x; fi)`

(3) git の同等判定（deny）:

- `( git reset --hard HEAD~1 )`
- `{ git push --force origin main; }`
- `if true; then git clean -fdx; fi`

(4) self-modification の同等判定（ask）:

- `(cp /tmp/x ~/.claude/settings.json)`
- `(cp /tmp/x ~/.claude/settings.json)>/dev/null`
- `{ tee ~/.claude/settings.json < /tmp/x; }`
- `for f in a; do mv /tmp/x ~/.claude/hooks/x.py; done`
- `for f in a; do echo $f; done > ~/.claude/settings.json`

(5) transcript-write の同等判定（deny）:

- `(mv ~/.claude/projects/x/y.jsonl /tmp/y.jsonl)`
- `if true; then cp /tmp/x ~/.claude/projects/a/b.jsonl; fi`

(6) その他のセグメント単位チェック:

- `( find /home/sakura -name '*.log' -delete )`（deny）
- `{ chmod -R 777 /home/sakura/x; }`（ask）

(7) 誤爆防止（allow）:

- `( rm -rf /tmp/x )`
- `(rm -rf node_modules)`
- `(rm -rf /tmp/x)>/dev/null`
- `if [ -d /tmp/x ]; then rm -rf /tmp/x; fi`
- `( cd /tmp && ls )`
- `{ echo hi; } 2>/dev/null`
- `f() { echo hi; }; f`
- `echo if then fi do done`
- `echo "( rm -rf /home/sakura/x )"`
- `echo '{ rm -rf /home/sakura/x; }'`
- `for f in rm -rf /home/sakura/x; do echo $f; done`
- `case x in rm) echo hi;; esac`
- ヒアドキュメントのデータ形:

  ```
  cat <<'EOF'
  if true; then rm -rf /home/sakura/x; fi
  EOF
  ```

- `git commit -m 'fix: ( rm -rf ) in docs'`

red の確認は、修正で判定が変わるケースに対して行う。既に通るケース（固定する allow 形など）は退行防止として残す。

**状態**: confirmed

**ビジネスルール**:

- 見逃し・誤爆のケースは直す前に足す（`.claude/rules/hook-tests.md`、NFR3）。
- 追加するコマンド文字列は既存のどれとも重複させない（NFR4）。

**関連受け入れ基準**: AC-3、AC-4、AC-5、AC-6

#### FR2: グルーピング・複合構文の内側のコマンドを判定する

**説明**: グルーピング・複合構文がコマンド位置に置いたコマンドは、同じコマンドを単体で書いたときと同じ判定を受ける。対象は次のとおり。

- サブシェルの開き `(`（クォートされていない演算子トークンのみ）
- ブレースグループの開き `{`
- 予約語 `if`、`then`、`elif`、`else`、`while`、`until`、`do`、`!`
- case パターン（`case WORD in` の後、省略可能な `(`、パターンの選択肢と `)`。`|` や改行で文をまたいで分かれたパターンも含む）
- 関数定義（`NAME() {`、`function NAME {`、`function NAME() {`）

**ビジネスルール**:

- 関数本体は実行されるものとして判定する（A-2）。
- `for` / `select` のヘッダ（`for NAME in WORDS`）はコマンドではなく、`in` の後の語をコマンドとして判定することはない。
- 閉じトークン・終端（`)`、`}`、`fi`、`done`、`esac`、`;;`）はそれ自体のコマンドを持たない。ただし、それに付いたリダイレクトは write target として判定する（`... done > ~/.claude/settings.json` は ask のまま）。
- 入れ子・組み合わせの形は完全にほどく。既存の VAR=value、`WRAPPERS`、置換を先頭に置いた形の読み飛ばしとの組み合わせも含む。
- 設定値は回答 grouping-scope = all_including_case。

**状態**: confirmed

**関連受け入れ基準**: AC-4、AC-5

#### FR3: 連結した閉じトークンを引数・対象に数えない

**説明**: サブシェルや case パターンを閉じる素の `)` 演算子トークンは、どのチェックでもコマンドの引数に数えない。対象となるチェックは、rm の対象、write target（cp / ln / rsync の最後の位置引数、mv / rm / chmod / chown のフラグでない引数、`INPLACE_WRITERS`）、git、ファイル破壊、外部・権限のチェック。

**ビジネスルール**:

- 閉じ括弧が引数列に連結した形（`(rm -rf /tmp/x)`、`(cp /tmp/x ~/.claude/settings.json)`。最後の引数の直後に `)` が続く）も含む。
- 閉じ括弧と後続のリダイレクト演算子が連結した形（`)>`、`)>>`、`)2>` など。例: `(cp /tmp/x ~/.claude/settings.json)>/dev/null`）は、閉じ括弧と実リダイレクトに分ける。リダイレクト先はリダイレクト先としてのみ判定し、コマンドの宛先や rm の対象としては扱わない。
- よって `(rm -rf /tmp/x)>/dev/null` は `rm -rf /tmp/x > /dev/null` と同じく allow、`(cp /tmp/x ~/.claude/settings.json)>/dev/null` は ask。
- クォートされた `")"` / `"("` は普通の語であり、固定済みの `git push "(" --force origin main` は deny のまま。

**状態**: confirmed

**関連受け入れ基準**: AC-6

#### FR4: データとしての予約語・括弧で新たな誤爆を出さない

**説明**: 予約語とグルーピング文字は、コマンド位置にあるときだけグルーピング構文として扱う。`(` はクォートされていない演算子トークンのときだけ扱う。次はいずれも allow のまま。

- 引数位置の予約語（`echo if then fi do done`）
- クォート内のグルーピング文字列
- シェルへ流し込まれないヒアドキュメント本文
- コミットメッセージ
- for / select ヘッダの語
- 文字列がたまたまコマンド名である case パターン

**ビジネスルール**:

- 既存ケースは全て現在の判定を保つ。次の固定済みケースを含む:
  - `(cd /home/sakura && rm -rf ./x)`（deny）
  - `(true; X=/tmp/safe; false)>/dev/null; rm -rf $X` / `(X=/tmp/safe; true); rm -rf $X` / 改行区切りのサブシェル形（ask）
  - if/then の HOME 形（deny）
  - for / while-read の形（ask）
  - `find /home/sakura \( -name '*.log' \) -delete`（deny）
- サブシェル末尾の `)` を case パターンの終端と取り違えない。

**状態**: confirmed

**関連受け入れ基準**: AC-1、AC-7

#### FR5: グルーピング修正の適用範囲

**説明**: 修正は `destructive-guard.py` の `main()` にある全セグメント単位チェックに適用する: `check_rm`（rm-root / rm-recursive / rm-unresolvable）、`check_git`、`check_file_destruction`、`check_external`、`check_permissions`、`check_self_modification`（self-modification と transcript-write）、および置換を先頭に置いた形の経路。`statements()` の置換本体、シェルへ流し込むヒアドキュメント、`-c` / eval / ヒアストリングのペイロード再走査で到達する文にも同じく適用する。

**ビジネスルール**:

- 変えないもの: failed-run-cleanup-guard.py への委譲（`strip_grouping_prefix()` / `_deferral_head()` を通した `matches_target_shape()`）。既存の `(silent)` ケースと委譲関連の allow ケースは判定を保つ（A-1）。
- `em-workflow/hooks/failed-run-cleanup-guard.py` は変更しない。
- `head()` は 2 要素タプルの戻り値の形を保つ。
- グルーピングを意識した読み飛ばしは、`substitution_only` の読み飛ばしの前例に倣い、`destructive-guard.py` 内に閉じたものとして記述する。`head()` の docstring にある対応関係の注記にもそう書く。
- `strip_grouping_prefix()` の docstring にある「サブシェルやブレースで囲んだ破壊的コマンドは他のチェックで検査されないまま残る」旨の文と、対応する `main()` のコメントを新しい挙動に合わせて書き直す。

**状態**: confirmed

**関連受け入れ基準**: AC-1、AC-2

#### FR6: 宛先 6 族を残し、tar -C は展開モードに限る

**説明**: 次の宛先判定を残す。

- rsync: 値付きフラグを除いた後の最後の位置引数
- git clone: 位置引数が 2 つ以上あるときの最後の位置引数
- unzip `-d`
- curl `-o` / `--output`
- wget `-O` / `--output-document`

tar は、`-C` / `--directory` の値（分離・連結・`=`・短オプション束の末尾の各書き方）を、展開モードのときだけ write target とする。

**ビジネスルール**:

- 展開モードとは、`-x`、`--extract`、`--get`、`x` を含む短オプション束（`-xzf`）、または `x` を含むダッシュ無しの伝統的な第 1 引数（`tar xzf a.tgz -C DIR`）のいずれか（A-3）。
- 作成（`-c` / `--create`）、一覧（`-t` / `--list`）、その他のモードでは、`-C` は読み取るディレクトリを指し、write target にしない。
- 設定値は回答 dest-families-scope = keep_fix_tar_mode。

**状態**: confirmed

**関連受け入れ基準**: AC-8

#### FR7: 宛先 6 族のケースを追加する（tar のモード含む）

**説明**: tar の変更より前に、`destructive-guard-cases.json` へ次を追加する。tar の作成・一覧の allow ケースは先に red を確認する。

- rsync:
  - `rsync -a /tmp/x/ ~/.claude/skills/`（ask）
  - `rsync -a ~/.claude/skills/ /tmp/backup/`（allow）
- git clone:
  - `git clone https://x.example/r.git ~/.claude/skills/r`（ask）
  - `git clone https://x.example/r.git /tmp/r`（allow）
  - `git clone https://x.example/r.git`（allow）
- tar 展開:
  - `tar -xzf /tmp/a.tgz -C ~/.claude/skills`（ask）
  - `tar -xf /tmp/a.tar --directory=~/.claude/hooks`（ask）
  - `tar xzf /tmp/a.tgz -C ~/.claude/hooks`（ask）
  - `tar -xf /tmp/a.tar -C /tmp/out`（allow）
- tar 作成・一覧:
  - `tar -cf /tmp/backup.tar -C ~/.claude/skills .`（allow）
  - `tar -tzf /tmp/a.tgz -C ~/.claude/skills`（allow）
  - `tar --directory=~/.claude/hooks -cf /tmp/b.tar .`（allow）
  - `tar --create -f /tmp/b.tar -C ~/.claude/skills .`（allow）
  - `tar -cf - -C ~/.claude/skills . | tar -xf - -C /tmp/copy`（allow）
- unzip:
  - `unzip /tmp/a.zip -d ~/.claude/skills/`（ask）
  - `unzip /tmp/a.zip -d /tmp/out`（allow）
- curl:
  - `curl -o ~/.claude/settings.json https://x.example/s.json`（ask）
  - `curl -o ~/.claude/projects/a/b.jsonl https://x.example/l`（deny、transcript-write）
  - `curl -o /tmp/s.json https://x.example/s.json`（allow）
- wget:
  - `wget -O ~/.claude/hooks/x.py https://x.example/x.py`（ask）
  - `wget -O /tmp/x.py https://x.example/x.py`（allow）
  - `wget -qO- https://x.example/a.txt`（allow）

**状態**: confirmed

**関連受け入れ基準**: AC-3、AC-8

#### FR8: head() / statements() の入力整形による rm 判定変化を固定する

**説明**: マージ済みのラッパー値付きフラグの消費（`WRAPPER_VALUE_FLAGS`）と、`-c` / eval / ヒアストリングのペイロード再走査がもたらした rm 判定について、ケースを追加する。ランナーでの判定は次のとおり。

- `sudo -u root rm -rf $HOME/x`（ask）
- `bash -c 'rm -rf $HOME/x'`（ask）
- `eval 'rm -rf $HOME/x'`（ask）
- `sudo -u root rm -rf /home/sakura/x`（deny）
- `eval 'rm -rf /home/sakura/x'`（deny）
- `env -u NAME rm -rf /home/sakura/x`（deny）
- 非破壊の対照 `sudo -u root ls /root`（allow）

**ビジネスルール**:

- これらは現行の基準で既に成り立つため、固定のためのケースであり、先に red になることは求めない。
- この挙動の実装は変えない。

**状態**: confirmed

**関連受け入れ基準**: AC-9

#### FR9: 誤解を招く mv ケースのラベルを直す

**説明**: `destructive-guard-cases.json` の既存ケース `mv ~/.claude/hooks/x.py extra.txt /tmp/y` のラベルを、`mv 複数ソース + 宛先のみ判定` から、mv のフラグでない引数（ソースを含む）が全て write target であり、そのため保護対象のソースで ask になる旨を表すラベルに変える。コマンドと期待判定（ask）は変えない。

**状態**: confirmed

**関連受け入れ基準**: AC-7

#### FR10: 前 feature の SPEC.md を実装に合わせて改訂する

**説明**: `feature-docs/destructive-guard-write-target-scoping/SPEC.md` を直接編集する。設定値は回答 spec-revision-location = edit_prior_spec_and_req。

- (a) FR2: 閉じた「3 つの抽出元」の列挙を、実装が使う抽出元に置き換える。
  - (a) 出力リダイレクト
  - (b) `INPLACE_WRITERS` と `sed -i`
  - (c) rm / chmod / chown のフラグでない引数。mv はフラグでない引数の全て（mv は各ソースを unlink するため）と `-t` / `--target-directory` の値。cp / ln は値付きフラグを除いた後の最後の位置引数。ただし `-t` / `--target-directory` があるときはその値のみ
  - (d) コマンド固有の宛先: rsync の最後の位置引数、git clone の最後の位置引数、展開モードに限った tar `-C` / `--directory`、unzip `-d`、curl `-o` / `--output`、wget `-O` / `--output-document`
- (b) Edge Cases: `mv a b c dir/` の行を、a、b、c、dir/ の全てが write target であるという規則に置き換える。
- (c) FR6: `check_rm` と `SAFE_DELETE` の本体は変えていないが、`head()` のラッパー値付きフラグ消費と `statements()` の `-c` / eval / ヒアストリングのペイロード再走査によって、`check_rm` が受け取る入力が変わったことを書く。その結果、`sudo -u root rm -rf $HOME/x`、`bash -c 'rm -rf $HOME/x'`、`eval 'rm -rf $HOME/x'` は allow から ask になった（`CLAUDE_BATCH` 下では deny に降格）。
- (d) 改訂後の FR2 / FR6 と矛盾するその他の文も直す: アーキテクチャ図の `(c) rm / mv / cp / ln / chmod / chown args` のラベル、コンポーネント図と Dependencies にある「変更した関数は `check_self_modification` のみ」という記述、Data Flow の説明。

**状態**: confirmed

**関連受け入れ基準**: AC-10

#### FR11: 前 feature の REQUIREMENTS.md を同じ内容で改訂する

**説明**: `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md` を、改訂後の SPEC.md と一致するように編集する。変更する箇所は次のとおり。

- 1.3 スコープ（`check_rm` / `SAFE_DELETE` についての対象外の行）
- 4.1 の表の FR2 と FR6 の行
- FR2 の説明とそのビジネスルール（cp / mv / ln の最後の引数）
- FR6 の説明
- 抽出元を 3 つに固定している 10.1 のリスク行
- 12.1 の境界値項目 `mv a b c dir/ の宛先は最後の 1 つ`
- 13 章の用語 書き込み先パス集合
- 14.1 の確認済み事項のうち 対象引数 の項目

文言は前文書の既存の日本語の書き方に揃える。

**状態**: confirmed

**関連受け入れ基準**: AC-10

#### FR12: em-workflow の version を 2 箇所で patch 上げする

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、同じ変更の中で `em-workflow/.claude-plugin/plugin.json` の `version` と `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を 0.2.12 から 0.2.13 に上げる。em-review の version は変えない。

**状態**: confirmed

**関連受け入れ基準**: AC-11

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし

### 5.2 セキュリティ要件

- 判定はコマンド文字列の静的解析だけで行う。コマンドを実行せず、置換を評価せず、ファイルシステム呼び出しやサブプロセスを追加しない（NFR1）。
- claude-batch 下では ask が deny に降格されるため、誤爆 1 件で無人走行が止まる。迂回を塞ぐ修正で、現在 allow のデータ形コマンドを ask / deny にしてはならない（NFR5）。

### 5.3 可用性要件

該当なし

### 5.4 保守性要件

- `destructive-guard.py` とそのテストは Python 標準ライブラリのみを import する（NFR2）。
- 見逃し・誤爆のケースは修正前に足す。既存ケースは削除せず、コマンドも期待判定も変えない（NFR3）。
- 追加するコマンド文字列は既存と重複させない（NFR4）。
- ケースの期待判定は、`CLAUDE_BATCH` を外した状態のランナーの判定とする（NFR6）。

### 5.5 互換性要件

該当なし

### 5.6 非機能要件一覧

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | 静的解析のみ・決定的判定 | 判定はコマンド文字列の静的解析だけで行う。コマンドを実行せず、置換を評価せず、ファイルシステム呼び出しやサブプロセスを追加しない（`tests/test_destructive_guard_command_substitution.py` が禁止呼び出しの一覧を検査する）。同じコマンドには常に同じ判定を返す。 |
| NFR2 | 標準ライブラリのみ | `destructive-guard.py` とそのテストは Python 標準ライブラリのみを import する（`test/README.md`。`test_module_uses_only_standard_library` が検査する）。 |
| NFR3 | テスト先行と既存ケース保持 | `.claude/rules/hook-tests.md` に従い、見逃し・誤爆のケースは修正前に足す。既存ケースは削除せず、既存ケースのコマンドも期待判定も変えない。既存行への変更は FR9 のラベルのみ。 |
| NFR4 | ケース表のコマンド文字列を重複させない | 追加するコマンド文字列は既存のどれとも異なること。重複があると `test_every_pre_task_command_preserved_with_only_named_changes` が失敗し、`ORIGINAL_VERDICT_BY_COMMAND` の全コマンドは固定された判定を保つ必要がある。 |
| NFR5 | 誤爆のコストは見逃しと同じ | claude-batch 下では ask が deny に降格されるため、誤爆 1 件で無人走行が止まる。迂回を塞ぐ修正で、現在 allow のデータ形コマンドを ask / deny にしてはならない。FR4 と FR7 の allow ケースがこれを守る。 |
| NFR6 | 期待判定はランナー環境の判定 | ケースの期待判定は、`CLAUDE_BATCH` を外した状態で `run-destructive-guard.py` が観測する判定とする。レビュー記録は batch 下で deny と測っているが、`$HOME/...` を対象とする rm はランナーでは ask になる。 |

## 6. UI/UX要件

### 6.1 画面設計要件

該当なし

### 6.2 画面遷移

該当なし

### 6.3 レスポンシブ対応

該当なし

## 7. データ要件

### 7.1 データモデル概要

該当なし

### 7.2 データ項目

該当なし

### 7.3 データ保持期間

該当なし

## 8. 外部連携

### 8.1 連携システム

該当なし

### 8.2 API仕様要件

該当なし

## 9. 制約条件

### 9.1 技術的制約

- 判定はコマンド文字列の静的解析のみで行う（NFR1）。
- 標準ライブラリのみを使う（NFR2）。
- `head()` は 2 要素タプルの戻り値の形を保つ（FR5）。
- `em-workflow/hooks/failed-run-cleanup-guard.py` と委譲判定は変更しない（FR5、A-1）。

### 9.2 ビジネス上の制約

- 見逃し・誤爆のケースは修正前に足し、既存ケースは消さない（NFR3）。
- 誤爆 1 件のコストは見逃し 1 件と同じ（NFR5）。
- プラグインの内容を変更したら、同じ変更の中で version を 2 箇所同値で上げる（FR12）。

### 9.3 スケジュール制約

該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-grouping-spec-drift/**`
- `test-docs/destructive-guard-grouping-spec-drift/**`

`feature-docs/destructive-guard-grouping-spec-drift/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-grouping-spec-drift/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-grouping-spec-drift/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/destructive-guard-grouping-spec-drift/` ディレクトリを生成しないが、宣言された `test-docs/destructive-guard-grouping-spec-drift/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| `\|` や改行で文をまたいで分かれた case パターンは、文をまたぐ文脈が要る | 高 | サブシェル末尾の `)` を case パターンの終端と取り違えない（FR2、FR4） |
| shlex の句読点連結で生じる閉じ括弧とリダイレクトの連結トークン（`)>`、`)>>`、`)2>`） | 高 | 閉じ括弧と実リダイレクトに分け、リダイレクト先はリダイレクト先としてのみ判定する（FR3） |
| データとしての予約語・括弧（引数位置、クォート、ヒアドキュメント本文、for / select ヘッダの語、case パターン文字列） | 高 | コマンド位置のときだけ構文として扱う。FR1 (7) の allow ケースで固定する（FR4、NFR5） |
| コマンド位置のクォートされた `"{"` は、語がクォートの由来を持たないため素の `{` と区別できない | 低 | グルーピングとして扱う（厳しい側） |
| グルーピングと VAR=value、`WRAPPERS`、mise / asdf exec、置換を先頭に置いたコマンド語との組み合わせ、および入れ子（`( { ...; } )`、if/then 内のサブシェル） | 中 | 完全にほどく（FR2） |
| `-c` / eval / ヒアストリングのペイロード内や置換本体内のグルーピング（`echo $(if true; then rm ...; fi)`） | 中 | ペイロード再走査・置換本体で到達する文にも同じく適用する（FR5） |
| ダッシュ無しの伝統的な tar モード引数（`tar xzf ...`）と、長オプションだけで与えたモード（`--create`、`--extract`、`--get`） | 中 | FR6 の展開モードの定義に従う（A-3） |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 迂回を塞ぐ修正が、現在 allow のデータ形コマンドを ask / deny にする | 中 | 高 | FR4 と FR7 の allow ケースで守る（NFR5） |
| 既存ケースの判定が変わる | 中 | 高 | 既存ケースのコマンド・期待判定を変えないことを受け入れ基準にする（NFR3、AC-7） |
| version 据え置きでキャッシュが更新されない | 中 | 中 | plugin.json と marketplace.json を同値で 0.2.13 に上げる（FR12） |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が、末尾の無人実行降格ケースを含む全ケースを通過し、終了コード 0 を返す。
- [ ] AC-2: `python3 -m unittest discover -s tests` が通る。
- [ ] AC-3: FR1 のケースと FR7 の tar 作成・一覧の allow ケースだけを追加した状態（`destructive-guard.py` は未変更）で、ランナーが red になる。
- [ ] AC-4: チケットの再現 5 コマンドがランナーで ask（`CLAUDE_BATCH=1` では deny）になり、単体の `rm -rf $HOME/x` と一致する。
- [ ] AC-5: `( )`、`{ }`、if/elif/else、for、while/until、`!`、case、関数定義を通しても、rm 再帰削除・git・self-modification・transcript-write の判定が、同じコマンドを単体で書いたときと一致する（FR1 のケース）。
- [ ] AC-6: 閉じ括弧連結形 `(cp /tmp/x ~/.claude/settings.json)` と `(cp /tmp/x ~/.claude/settings.json)>/dev/null` が ask、`(rm -rf /tmp/x)>/dev/null` が allow になる。
- [ ] AC-7: 既存ケースは全てコマンドと期待判定を保つ。変わるのは FR9 の mv のラベルだけ。
- [ ] AC-8: tar `-C` は展開モードでのみ write target になり（`tar -cf /tmp/backup.tar -C ~/.claude/skills .` は allow、`tar -xzf /tmp/a.tgz -C ~/.claude/skills` は ask）、6 族それぞれに ask ケースと allow ケースが 1 件以上ある。
- [ ] AC-9: `sudo -u` / `bash -c` / `eval` 経由の rm のケースが存在し、通る。
- [ ] AC-10: `feature-docs/destructive-guard-write-target-scoping/SPEC.md` と REQUIREMENTS.md において、FR2(c)/(d)、Edge Cases の mv の行、FR6 が、mv・宛先 6 族・`head()` / `statements()` についての実装の挙動と一致する。
- [ ] AC-11: `em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の em-workflow の version がどちらも 0.2.13 である。

### 11.2 KPI

該当なし

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系: `python3 em-workflow/hooks/tests/run-destructive-guard.py`（TS-1）— ケース表の実行。FR1 / FR7 のケース追加後は red、修正後は green。FR1〜FR4、FR6〜FR9 を扱う。
- [ ] 正常系: `python3 -m unittest discover -s tests`（TS-2）— リポジトリ全体のユニットテスト。ケース表の不変条件（重複なし、`ORIGINAL_VERDICT_BY_COMMAND` の固定、標準ライブラリのみ、ファイルシステム呼び出しなし）と failed-run-cleanup-guard のテストを含む。FR5、NFR1〜NFR4 を扱う。
- [ ] 正常系: `python3 em-workflow/hooks/tests/run-destructive-guard.py ~/.claude/plugins/cache/em-claude-plugins/em-workflow/0.2.13/hooks/destructive-guard.py`（TS-3）— 任意。version を上げた後、インストール済みキャッシュのコピーに修正が入っていることを確かめる。FR12 を扱う。
- [ ] E2E（TS-E2E）: 該当なし。E2E の基盤が無い。
- [ ] 異常系: グルーピング・複合構文を通した rm 再帰削除・git・self-modification・transcript-write が単体時と同じ判定になる（FR1 (1)〜(6)）。
- [ ] 境界値: case パターンの `|` / 改行による分割、case パターンの省略可能な先頭 `(`、`)>` / `)>>` / `)2>` の連結トークン、閉じキーワードに付いたリダイレクト（`done > file`、`} 2>/dev/null`）、入れ子構文、ダッシュ無しの tar モード引数と長オプションのみのモード指定。
- [ ] セキュリティ: データとしての予約語・括弧が誤爆しない（FR1 (7)、FR4）。
- [ ] パフォーマンス: 該当なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| グルーピング・複合構文 | `( )`、`{ }`、if/elif/else、for/select、while/until、`!`、case、関数定義 |
| コマンド位置 | 文の中でコマンド名として読まれる位置 |
| 閉じトークン | `)`、`}`、`fi`、`done`、`esac`、`;;`。それ自体のコマンドを持たない |
| 閉じ括弧の連結 | 閉じ括弧 `)` が直前の引数や直後のリダイレクト演算子と 1 つのトークンに連結した形（`(rm -rf /tmp/x)`、`)>`） |
| 宛先 6 族 | rsync / git clone / tar / unzip / curl / wget |
| 展開モード（tar） | `-x`、`--extract`、`--get`、`x` を含む短オプション束、または `x` を含むダッシュ無しの第 1 引数 |
| 同等判定 | グルーピング・複合構文を通したコマンドの判定段階が、同じコマンドを単体で書いたときと一致すること（A-4） |
| 降格 | 無人実行（`CLAUDE_BATCH`）下で ask が deny として扱われること |
| ランナー | `em-workflow/hooks/tests/run-destructive-guard.py`。`CLAUDE_BATCH` を外した状態で判定を観測する |

## 14. 確認事項

### 14.1 確認済み事項

- [x] grouping-scope: all_including_case。`( )`、`{ }`、if/elif/else、for/select、while/until、`!`、case、関数定義の全てを対象とする。閉じ括弧が引数列に連結した形（`(rm -rf /tmp/x)`、`(cp /tmp/x ~/.claude/settings.json)`）も対象に含める。
- [x] dest-families-scope: keep_fix_tar_mode。宛先 6 族の判定を残し、tar `-C` は展開モードに限る。tar の作成・一覧・展開のケースを追加する。
- [x] spec-revision-location: edit_prior_spec_and_req。前 feature の SPEC.md と REQUIREMENTS.md の両方を直接改訂し、本 feature の変更対象に含める。
- [x] em-workflow の version: 現在 0.2.12、上げ先 0.2.13（patch）。em-review は変えない。
- [x] 既存 E2E 基盤: なし。
- [x] デザインステップ: skipped。UI も視覚デザインも無い。変更は 1 つのフックスクリプトの静的コマンド解析、そのケース表、前 feature の文書 2 つ、version フィールド 2 つに閉じる。

### 14.2 未確認・保留事項

なし（全要件が confirmed）。

### 14.3 前提

| ID | 前提 | 理由 | 影響度 | 可逆 |
|----|------|------|--------|------|
| A-1 | failed-run-cleanup-guard への委譲と failed-run-cleanup-guard.py 自体は変えない。`head()` の対応する 2 要素タプルの契約は保ち、グルーピングの読み飛ばしは `destructive-guard.py` 内に閉じたものとして記述する。 | 回答が決めているのはこのフックの範囲だけ。`head()` の docstring は、戻り値の形を変えない局所的な読み飛ばしを既に許している（`substitution_only` の前例）。failed-run-cleanup-guard 自身の `head()` が判定できない if/then/do 形まで委譲を広げると、それらのコマンドが allow から silent に移り、分類器に委ねられる（NFR5）。 | 中 | はい |
| A-2 | 関数本体は、コマンドがその関数を呼ぶかどうかに関わらず、実行されるものとして判定する。 | `strip_grouping_prefix()` は既に、定義された関数の本体を呼ばれたものとして扱っている。本体を判定するのは安全網として厳しい側。 | 低 | はい |
| A-3 | ダッシュ無しの伝統的な tar 形（`tar xzf ...`）は展開モードに数える。 | 現行実装は全モードで `-C` を宛先として扱っており、ダッシュ無しの展開形を外すと検知力が下がる。回答が求めているのは `-C` を展開に限ることで、検知済みの展開を外すことではない。 | 低 | はい |
| A-4 | 同等判定は判定段階（ランナーが比較するもの）で確かめる。ルール ID は別に確かめない。 | チケットの完了の定義は判定が単体形と一致することを求めており、ランナーは判定段階を比較する。 | 低 | はい |
| A-5 | 前 feature のブランチは main にマージ済みで、main を基準とする。mv・宛先 6 族・`head()` / `statements()` についてのその挙動が、改訂後の SPEC が記述する実装である。 | オーケストレーターが与えた事実。integration worktree の `destructive-guard.py` は `FLAG_DEST_FLAGS`、`WRAPPER_VALUE_FLAGS`、ペイロード再走査を含む。 | 低 | はい |

## 15. 参考資料

- `em-workflow/hooks/destructive-guard.py`: 変更対象のフック本体
- `em-workflow/hooks/tests/destructive-guard-cases.json`: 期待判定のケース表
- `em-workflow/hooks/tests/run-destructive-guard.py`: 専用テストランナー
- `em-workflow/hooks/failed-run-cleanup-guard.py`: 委譲先のフック（変更しない）
- `feature-docs/destructive-guard-write-target-scoping/SPEC.md`: 改訂対象の前 feature の SPEC
- `feature-docs/destructive-guard-write-target-scoping/REQUIREMENTS.md`: 改訂対象の前 feature の要件定義書
- `feature-docs/destructive-guard-write-target-scoping/reviews/round2.yaml`: 前 feature のレビュー記録
- `.claude/rules/hook-tests.md`: フックのテスト規則
- `.claude/rules/core-plugin-version-bump.md`: version bump 規則
- `test/README.md`: テストコードの外部依存禁止
