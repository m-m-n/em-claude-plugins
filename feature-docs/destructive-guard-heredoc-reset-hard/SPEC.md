# Feature: destructive-guard-heredoc-reset-hard

## Overview

destructive-guard.py が、ヒアドキュメント本文に書かれただけの `git reset --hard` 文字列で deny しないようにする。本文を再走査するかどうかを、チャンク全体に対する SHELL_SINK の部分一致ではなく、ヒアドキュメントごとの宛先で判定する。シェルシンクに渡るヒアドキュメント本文と、通常のコマンドとしての `git reset --hard` の検知は保つ。

要件定義書: `feature-docs/destructive-guard-heredoc-reset-hard/REQUIREMENTS.md`

## Objectives

- destructive-guard.py がヒアドキュメント本文に書かれただけの `git reset --hard` 文字列で deny しないようにし、--batch 無人実行が誤爆で止まらないようにする
- 実際にシェルが実行する位置の `git reset --hard`（通常のコマンド、シェルシンクに渡るヒアドキュメント本文を含む）の検知力は落とさない

## Technical Requirements

### Functional Requirements

- **FR1:** ヒアドキュメント本文の再走査を、そのヒアドキュメント自身の宛先で判定する。statements() がヒアドキュメント本文を再走査キューに戻す条件を、チャンク全体に対する SHELL_SINK の部分一致（destructive-guard.py 1222 行 `if bodies and SHELL_SINK.search(chunk)`）から、本文ごとの宛先判定に置き換える。本文を再走査するのは、そのヒアドキュメントが次のいずれかに当たるときに限る。
    - (i) ヒアドキュメントのリダイレクトを持つ文のコマンド語（代入・ラッパー・グルーピングを読み飛ばした後の語の basename）がシェルシンクである。
    - (ii) その文が属するパイプラインの下流にシェルシンクのコマンド語がある（例: `cat <<'EOF' | bash`）。
    - (iii) ヒアドキュメントがコマンド置換の中にあり、その置換を含む外側の文のコマンド語がシェルシンクである（例: `bash -c "$(cat <<'EOF' ... EOF)"`）。

    これ以外のヒアドキュメント本文はデータとして扱い、再走査しない。
- **FR2:** シェルシンクの判定を語単位にする。シェルシンクかどうかはコマンド位置の語（basename）で判定し、チャンク内の任意の部分文字列では判定しない。`run_codex_exec.sh` の `.sh` 接尾辞、引数や本文中の `python3` / `bash` などの語はシンク判定に使わない。シンクとして扱う語彙は現行の SHELL_SINK（sh, bash, zsh, dash, ksh, python, pythonN, perl, ruby, node）から減らさない。現行の `\b` 境界一致がコマンド語として拾っていた版付き表記（例: `python3.12`）も引き続きシンクとして扱う。
- **FR3:** 1 行に複数あるヒアドキュメントの本文をすべて除去する。1 行に複数のヒアドキュメント演算子がある場合（例: `cat > /tmp/a <<'A' ; cat > /tmp/b <<'B'`）、演算子の出現順に、その行の後ろに続く本文を順番に消費して除去する（最初の演算子の本文は区切り語 A まで、次の本文は区切り語 B まで）。現行の HEREDOC 正規表現の `[^\n]*` が 2 個目以降の `<<` を飲み込み、その本文がコマンドとして読まれる問題をなくす。各本文の再走査の要否は FR1 に従い、ヒアドキュメントごとに個別に判定する。
- **FR4:** ヒアドキュメントの後に続く文は引き続き検査する。ヒアドキュメントを閉じる区切り行より後ろの文は、これまでどおりコマンドとして検査する。例: `cat > /tmp/p <<'EOF'` / 本文 / `EOF` / `git reset --hard HEAD` は deny のまま。
- **FR5:** 宛先が決められないときは現行の保守的な挙動に倒す。ヒアドキュメントを持つ文を字句解析できず宛先を決められないとき（lex_segments() がパース失敗の代替経路に落ちたときなど）は、現行の挙動（チャンクに SHELL_SINK が現れたら本文を再走査する）を保つ。検知漏れの方向には倒さない。
- **FR6:** 誤爆の再発を検出するケースを先に足す。`.claude/rules/hook-tests.md` に従い、修正より前に `em-workflow/hooks/tests/destructive-guard-cases.json` に `[期待する判定, ラベル, コマンド]` 形式でケースを追加する。追加するのは allow 側の再発防止ケース（チケットの最小再現、実際に踏んだ経路の形、1 行に 2 個のヒアドキュメント、クォート内の reset --hard）と、検知力を保つ deny 側の対照ケース（シェルシンク宛てのヒアドキュメント、パイプライン経由のシンク、同じ行の 2 個目がシンク宛て、ヒアドキュメントの後に続く本物の reset --hard）。
- **FR7:** 既存ケースを保つ。destructive-guard-cases.json にある既存の deny / ask ケースは 1 件も削除せず、期待する判定も変えない。既存の allow ケースも期待する判定を変えない。
- **FR8:** em-workflow の version の patch を上げる。em-workflow/ 配下を変更するので、同じ変更の中で em-workflow の version の patch を上げる。`em-workflow/.claude-plugin/plugin.json` の `version` と、リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリの `version` を同じ値にする。具体値はコミット時点の HEAD から決める。

### Non-Functional Requirements

- **NFR1 - 静的解析のみ:** 判定は今までどおり決定的に行う。同じコマンドには常に同じ判定を返す。ファイルシステムにアクセスせず、コマンドや置換を評価しない。
- **NFR2 - 依存を増やさない:** Python 標準ライブラリだけで実装する。
- **NFR3 - 性能:** hooks.json の destructive-guard.py の timeout（10 秒）に十分収まること。ヒアドキュメントの処理で、入力長に対して計算量が爆発しないこと。
- **NFR4 - 変更範囲:** 変更は destructive-guard.py、destructive-guard-cases.json、version の 2 ファイルに限る。hooks.json の hook 構成と run-destructive-guard.py は変えない。

## Implementation Approach

### 変更箇所

| 箇所 | 変更 | 要件 |
|------|------|------|
| statements() の本文再走査条件（destructive-guard.py 1222 行 `if bodies and SHELL_SINK.search(chunk)`） | チャンク全体の部分一致から、ヒアドキュメントごとの宛先判定（i〜iii）に置き換える | FR1 |
| シェルシンク判定 | コマンド位置の語の basename で判定する。語彙は現行の SHELL_SINK から減らさない | FR2 |
| HEREDOC 正規表現による本文除去 | 1 行の複数の演算子について、出現順に本文を消費して除去する | FR3 |
| 区切り行より後ろの文 | これまでどおりコマンドとして検査する | FR4 |
| lex_segments() がパース失敗の代替経路に落ちたとき | 現行の挙動（チャンクに SHELL_SINK が現れたら本文を再走査する）を保つ | FR5 |

### Dependencies

**External Dependencies:**
- なし。Python 標準ライブラリだけで実装する（NFR2）。

### File Structure

変更するファイル（NFR4）:

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json                      # version の patch を上げる（FR8）
└── hooks/
    ├── destructive-guard.py             # FR1〜FR5
    └── tests/
        └── destructive-guard-cases.json # ケース追加（FR6、FR7）
.claude-plugin/
└── marketplace.json                     # em-workflow エントリの version（FR8）
```

変えないファイル（NFR4）:
- `em-workflow/hooks/hooks.json` の hook 構成
- `em-workflow/hooks/tests/run-destructive-guard.py`

## Declared Change Set

このフィーチャー固有のパスは手で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

上のフィーチャー固有のパスに加えて、次の 2 つのワークフロー生成エントリを既定で宣言する。

- `feature-docs/destructive-guard-heredoc-reset-hard/**`
- `test-docs/destructive-guard-heredoc-reset-hard/**`

`feature-docs/destructive-guard-heredoc-reset-hard/**` には、`REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物が含まれる。これらはフェーズドキュメントと `references/phase-state.md` が生成・管理する。この節はそれらを引用するだけで、ルールは再掲しない。

`test-docs/destructive-guard-heredoc-reset-hard/**` には、タスクごとのテスト記録 `test-docs/destructive-guard-heredoc-reset-hard/{T}.tests.yaml` が含まれる。これは `implement-phase.md` が生成・管理する。この節はそれを引用するだけで、ルールは再掲しない。

この 2 つの既定エントリは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込みとして明示する。

この宣言はスーパーセットの主張である。検証時に観測される実際の変更集合は、宣言された集合に含まれて（CONTAINED IN）いればよく、一致する必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/destructive-guard-heredoc-reset-hard/` ディレクトリを生成しないが、その場合も宣言された `test-docs/destructive-guard-heredoc-reset-hard/**` は正しい。宣言されたパスが生成されなくても違反にはならない。

## Test Scenarios

### Unit Tests

`em-workflow/hooks/tests/destructive-guard-cases.json` のケースとして追加する（FR6）。各コマンドは改行を含めてそのまま入力とする。

- [ ] TS-1: 期待 allow（AC-1）
```
cat > /tmp/p.txt <<'EOF'
Some prose mentioning `git reset --hard` inside a documentation quote.
EOF
echo done
```

- [ ] TS-2: 期待 allow（AC-2）
```
S=/tmp/x && cat > $S/prompt.md <<'EOF'
Step I.2.a には `git reset --hard` の記述が無い
EOF
em-workflow/scripts/run_codex_exec.sh readonly "$(cat $S/prompt.md)"
```

- [ ] TS-3: 期待 allow（AC-2）
```
python3 x.py; cat > /tmp/p <<'EOF'
git reset --hard HEAD
EOF
```

- [ ] TS-4: 期待 allow（AC-3）
```
cat > /tmp/a <<'A' ; cat > /tmp/b <<'B'
first
A
git reset --hard HEAD
B
```

- [ ] TS-5: 期待 deny（AC-4）
```
bash <<'EOF'
git reset --hard HEAD
EOF
```

- [ ] TS-6: 期待 deny（AC-4）
```
cat <<'EOF' | bash
git reset --hard HEAD
EOF
```

- [ ] TS-7: 期待 deny（AC-4）
```
sudo bash <<'EOF'
git reset --hard HEAD
EOF
```

- [ ] TS-8: 期待 deny（AC-4）
```
/bin/sh <<'EOF'
git reset --hard HEAD
EOF
```

- [ ] TS-9: 期待 deny（AC-4）
```
cat > /tmp/a <<'A' ; bash <<'B'
first
A
git reset --hard HEAD
B
```

- [ ] TS-10: 期待 deny（AC-5）
```
cat > /tmp/p <<'EOF'
x
EOF
git reset --hard HEAD
```

- [ ] TS-11: 期待 allow（AC-6）
```
echo 'git reset --hard HEAD'
```

- [ ] TS-12: 期待 allow（AC-6）
```
git commit -m "docs: explain why git reset --hard is forbidden"
```

- [ ] TS-13: 期待 deny（AC-4）。FR1 (iii)。現行ではチャンク全体一致で deny になる。修正後も deny を保つ。
```
bash -c "$(cat <<'EOF'
git reset --hard HEAD
EOF
)"
```

### Integration Tests

- [ ] TS-14: 期待 全件 pass（AC-7）
```
python3 em-workflow/hooks/tests/run-destructive-guard.py
```

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] ヒアドキュメントを持つ文の宛先を決められないとき（lex_segments() がパース失敗の代替経路に落ちたときなど）は、チャンクに SHELL_SINK が現れたら本文を再走査する（FR5）。

## Error Handling

宛先判定ができないときは、検知漏れの方向に倒さず、現行の挙動（チャンクに SHELL_SINK が現れたら本文を再走査する）を保つ（FR5）。

## Performance Optimization

### Performance Goals
- hooks.json の destructive-guard.py の timeout（10 秒）に十分収まる（NFR3）。
- ヒアドキュメントの処理で、入力長に対して計算量が爆発しない（NFR3）。

## Success Criteria

- [ ] AC-1: チケットの再現手順のコマンド（`cat > /tmp/p.txt <<'EOF'` / ``Some prose mentioning `git reset --hard` inside a documentation quote.`` / `EOF` / `echo done`）が allow になる。allow ケースとして cases.json に入っている。（FR1、FR6）
- [ ] AC-2: 実際に踏んだ経路の形（`S=/tmp/x && cat > $S/prompt.md <<'EOF'` / `git reset --hard` に触れる本文行 / `EOF` / `em-workflow/scripts/run_codex_exec.sh readonly "$(cat $S/prompt.md)"`）が allow になる。本文と同じチャンク内の別の文に `python3` や `bash` の語が引数として現れる形も allow になる。（FR1、FR2、FR6）
- [ ] AC-3: 1 行に 2 個のヒアドキュメントを開き（`cat > /tmp/a <<'A' ; cat > /tmp/b <<'B'`）、2 個目の本文にだけ `git reset --hard` がある形が allow になる。（FR3、FR6）
- [ ] AC-4: シェルシンク宛てのヒアドキュメント本文の検知が保たれる。次がすべて deny になる: `bash <<'EOF'` の本文に `git reset --hard HEAD`、`cat <<'EOF' | bash` の本文に `git reset --hard HEAD`、ラッパーや絶対パス付きのシンク（`sudo bash <<'EOF'`、`/bin/sh <<'EOF'`）、同じ行の 2 個目のヒアドキュメントだけがシンク宛て（`cat > /tmp/a <<'A' ; bash <<'B'`）で B の本文に `git reset --hard HEAD`。既存ケース「bash ヒアドキュメントは実行」も deny のまま。（FR1、FR2、FR3、FR7）
- [ ] AC-5: ヒアドキュメントの後に続く本物の `git reset --hard HEAD` の文は deny になる。（FR4）
- [ ] AC-6: クォート内の文字列としての `git reset --hard`（例: `echo 'git reset --hard HEAD'`、`git commit -m "... git reset --hard ..."`）が allow になり、cases.json に allow ケースとして入っている。（FR6）
- [ ] AC-7: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する。変更前の cases.json にあった deny / ask ケースがすべて残り、期待する判定も変わっていない。（FR6、FR7）
- [ ] AC-8: em-workflow の version の patch が上がり、plugin.json と marketplace.json の値が一致している。（FR8）

## Assumptions

- 引用符なしのヒアドキュメント本文にある `$(...)` / バッククォート内の `git reset --hard` は現在 allow（検知漏れ）だが、この feature の対象外とし、別タスクで扱う。本文内の置換を走査する要件は追加しない。
- 既存の deny / ask ケースはすべて残す。`bash <<EOF` の本文が実行される形の検知は保つ（既存ケースで固定されている不変条件）。
- ヒアドキュメントでファイルに書いた本文を、後続の別の文でシェルが実行する形（例: `cat > s.sh <<'EOF' ... EOF` の後に `bash s.sh`）は、本文の再走査の対象にしない。ファイルを経由するデータの流れは静的に追わない。この形は現在はチャンク内の `bash` 一致で偶然 deny になっているが、既存ケースでは固定されていない。
- `python3 <<EOF` などシェル以外のインタプリタに渡る本文も、現行どおりシェル文として再走査する（シンクの語彙は減らさない）。
- 閉じる区切り行が無いヒアドキュメント、`\w+` 以外の文字を含む区切り語（例: `END-OF-TEXT`）、クォート内の `<<` を演算子と誤認する挙動は、現行の扱いのまま変えない（対象外）。
- チケット末尾の「追加指示」（PR 作成、Codex への相談、Notion への記録）は実行時の進め方への指示で、この feature の機能要件には含めない。
- オーケストレーターの直接検証により、チケットの最小再現は現行コードで既に allow と確認済み。それでも再発防止のため allow ケースとして追加する。

## Open Questions

なし（status: tbd の要件は無い）。

## References

- 要件定義書: `feature-docs/destructive-guard-heredoc-reset-hard/REQUIREMENTS.md`
- フックのテストのルール: `.claude/rules/hook-tests.md`
