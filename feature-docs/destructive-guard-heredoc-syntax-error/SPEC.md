# Feature: destructive-guard-heredoc-syntax-error

## 概要

destructive-guard の字句解析（lex_shell() / _lex_pass()）は、配列の複合代入の括弧の中にある `<<` をヒアドキュメント演算子として登録しない。bash はこの行を構文エラーとして捨てるので、続く行は本文として検査から外さず、コマンドとして判定する。置換・引用の中や閉じた配列の後にある `<<` の扱いと、既存の deny / ask ケースは変えない。

## 目的

- bash が配列の複合代入の構文エラーで捨てる行にある `<<` をヒアドキュメント演算子と読まないようにする。これで、続く行の破壊的コマンドが本文として検査から外れ、allow のまま実行される抜け道を塞ぐ
- 無人実行（em-workflow の batch）でも、この形の rm -rf や git reset --hard が確認なしに実行されないようにする
- 既存の deny / ask ケースを 1 件も失わず、配列の外や置換の中にある本物のヒアドキュメントの allow も保つ

## 受け入れ条件

- [ ] AC1（FR1）: `x=( <<EOF\ngit reset --hard HEAD\nEOF` が deny になる
- [ ] AC2（FR1）: `x=( <<EOF\nrm -rf /home/sakura/valuable\nEOF` が deny になる
- [ ] AC3（FR1）: `x+=( <<EOF`、要素入りの `x=(a b <<EOF`、`declare -a x=( <<EOF`、複数行の配列 `x=(\na <<EOF` の各形の後に `git reset --hard HEAD` の行と `EOF` の行を置いたコマンドが、すべて deny になる
- [ ] AC4（FR2）: `cat <<'A'; x=( <<B\ngit reset --hard HEAD\nA\nB` が deny になる
- [ ] AC5（FR3）: 配列エラーの行の後にある本物のヒアドキュメント（`x=( <<A\ncat <<'EOF'\ngit reset --hard HEAD\nEOF`）は従来どおり本文として扱われ、allow になる
- [ ] AC6（FR4）: 配列内のコマンド置換の中のヒアドキュメント（`x=( $(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n) )`）と、二重引用符で囲んだ同じ形が allow のまま
- [ ] AC7（FR4）: 配列内のプロセス置換の中のヒアドキュメント（`x=( <(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n) )`）が allow のまま
- [ ] AC8（FR4）: 閉じた配列の後のヒアドキュメント（`x=(a b); cat <<'EOF'\ngit reset --hard HEAD\nEOF`）が allow のまま
- [ ] AC9（FR4）: 配列内の引用の中にある `<<EOF`（`x=( '<<EOF' )\nrm -rf /home/sakura/valuable\nEOF`）は従来どおり演算子にならず、deny になる
- [ ] AC10（FR5）: AC1〜AC9 の形が destructive-guard-cases.json に追加されている
- [ ] AC11（FR6, NFR3, NFR4）: 既存の deny / ask ケースの件数が減っていない。run-destructive-guard.py と unittest discover -s tests が全件成功する

## 技術要件

### 機能要件

- **FR1: 配列の複合代入の括弧内にある `<<` を演算子として登録しない** — lex_shell() / _lex_pass() は、配列の複合代入の括弧の中で、置換と引用の外にある `<<` / `<<-` をヒアドキュメント演算子として登録しない。対象の括弧は `NAME=(` と `NAME+=(` の `(`、および `declare -a x=(` など宣言組み込みの引数にある複合代入の `(`。この `<<` の後に続く行は本文として外さず、コマンドとして判定する。
- **FR2: 同じ行で先に登録された演算子にも本文を取らせない** — FR1 の `<<` が現れた行で、配列より前に登録され、まだ本文を取っていない演算子（例: `cat <<'A'; x=( <<B` の `<<'A'`）にも本文を取らせない。bash はこの行全体を捨てるので、続く行はコマンドとして判定する。
- **FR3: 配列エラーの後に配列状態を解除する** — FR1 の `<<` を読んだ後、その行を終える改行で配列の文脈を解除する。次の行はトップレベルのコマンド位置として読む。次の行以降にある本物のヒアドキュメントは従来どおり登録し、本文を取らせる。
- **FR4: 置換・引用の中や閉じた配列の後にある `<<` は従来どおり扱う** — 配列の中にあるコマンド置換・バッククォート置換・プロセス置換の中の `<<` と、閉じた配列の後の `<<` は、従来どおり本物の演算子として扱う。配列の中にある引用の中の `<<` は、従来どおり演算子として扱わない。祖先に配列があるというだけでは演算子の登録を止めない。
- **FR5: 再発防止ケースを cases.json に追加する** — `em-workflow/hooks/tests/destructive-guard-cases.json` に `[期待する判定, ラベル, コマンド]` の形でケースを足す。deny 側のケースには FR1〜FR3 の各形を入れ、続く行には単独でも deny になるコマンド（`git reset --hard HEAD`、`rm -rf /home/sakura/valuable`）を置く。allow 側のケースには FR4 の各形を入れる。
- **FR6: 既存ケースを保つ** — 既存の deny / ask ケースを 1 件も消さず、書き換えもしない。既存の全ケースが修正後も期待どおりの判定を返す。

### 非機能要件

- **NFR1: 判定を下す場所を 1 か所に保つ** — ヒアドキュメント演算子かどうかの判定は、従来どおり lex_shell() だけが行う。strip_heredocs()、scan_structure()、_TrackingLexer、tokens() は lex_shell() の地図から判定を受け取り、独自に分類しない（統一字句解析器の契約）。
- **NFR2: 作業量の上限を保つ** — lex_shell() は 1 回のパスで左から右へ読む方式と、作業量の上限（LEX_WORK_FACTOR × 文字数 + 下限）を保つ。上限を超えたときは従来どおり scan-budget の ask を返す。run-destructive-guard.py の 1 件ごとの制限時間（10 秒）を超えるケースを出さない。
- **NFR3: 判定は厳しくなる方向にだけ動かす** — 変更で判定が動くのは、対象の形を allow から deny / ask に変えることだけにする。既存ケースが deny / ask から allow に変わってはならない。
- **NFR4: テストを走らせる** — 同じ変更の中で `python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest discover -s tests` を走らせ、どちらも全件成功させる。

## 前提

- A1: 修正の範囲は、配列の複合代入（`NAME=(` / `NAME+=(`、宣言組み込みの引数の複合代入を含む）の括弧の中の `<<` に限る（requirement.fix-scope の回答 array_assignment_only）。Bash 5.3.9 の実測では、これらの形はエラーの後の行を実行した
- A2: 構文エラーの行一般は範囲外とする。対応の無い `)` や、置けない位置の予約語（単独の then / fi / done / in / esac など）では bash が停止して後続の行を実行しないため。これらの形の判定は変えない
- A3: FR2 の「同じ行」は、FR1 の `<<` が現れた行で登録され、まだ本文を取っていない演算子を指す
- A4: このフックは自前のコードで、追随すべき外部の修正版は無い。この feature の修正がそのまま対応になる
- A5: design step は skip する（design-step.decision の回答 decide_autonomously）
- A6: `git reset --hard HEAD` と `rm -rf /home/sakura/valuable` は単独で deny になる（既存ケース: cases.json の 141 行目と 425 行目、および事前調査の実測）

## 宣言する変更範囲

この節は手書きの一覧ではなく、create-plan での導出を示す。この feature 固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

この feature 固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/destructive-guard-heredoc-syntax-error/**`
- `test-docs/destructive-guard-heredoc-syntax-error/**`

`feature-docs/destructive-guard-heredoc-syntax-error/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design step が生成する設計成果物を含む。これらは各フェーズ文書と `references/phase-state.md` が生成・管理する。この節はそれらを参照するだけで、規則は再掲しない。

`test-docs/destructive-guard-heredoc-syntax-error/**` はタスクごとのテスト記録 `test-docs/destructive-guard-heredoc-syntax-error/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・管理する。この節はそれを参照するだけで、規則は再掲しない。

この 2 つの既定の宣言は、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことを理由に外れたとはみなさない。外すのは意図的・明示的な絞り込みとして行う。

この宣言は上位集合としての宣言である。検証時に観測した実際の変更範囲は、宣言した範囲に含まれていればよく、一致している必要はない。implement タスクを生まない feature では `test-docs/destructive-guard-heredoc-syntax-error/` ディレクトリ自体が生成されないが、その場合も `test-docs/destructive-guard-heredoc-syntax-error/**` の宣言は正しい。宣言したパスが実在しないことは違反ではない。

## テストシナリオ

### 判定ケース（destructive-guard-cases.json）

- [ ] TS1（deny / AC1, AC2）: 単純な `x=( <<EOF` の後に破壊的コマンドの行を置く形（2 種類のコマンド）
- [ ] TS2（deny / AC3）: `x+=(`、要素入り、`declare -a`、複数行の配列の各形
- [ ] TS3（deny / AC4）: 同じ行で配列より前に登録された演算子が、本文を取らない形
- [ ] TS4（allow / AC5）: 配列エラーの行の後に本物のヒアドキュメントが続く形（配列状態が解除されている）
- [ ] TS5（allow / AC6, AC7）: 配列内のコマンド置換・プロセス置換の中の本物のヒアドキュメント（祖先に配列があるだけでは抑止しない）
- [ ] TS6（allow / AC8）: 閉じた配列の後の本物のヒアドキュメント
- [ ] TS7（deny / AC9）: 配列内の引用の中の `<<` が演算子にならない形

### 回帰

- [ ] TS8（regression / AC11）: 既存スイートの全件実行と unittest discover -s tests（字句解析の一致検査を含む）

### E2E テスト

**既存の E2E テスト**: なし
**実行コマンド**: 検出なし

## 未解決事項

なし
