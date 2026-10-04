---
title: "destructive-guard-heredoc-sink-gaps"
created_date: 2026-10-03
status: draft
---

# destructive-guard-heredoc-sink-gaps - 要件定義書

## 1. 概要

### 1.1 背景
round2 で deferred にした critical 1 件・high 4 件の検知漏れと、単一引用符内に `$(` を大量に含む大きな入力の判定時間の問題がある。対象はチケットに挙がった 6 件とする。

### 1.2 目的
- `destructive-guard.py` が、シェルシンクに渡るヒアドキュメント本文の破壊的コマンドを ask / deny にする。ヒアドキュメントと誤認されて隠れていた実コマンド行も同じく ask / deny にする。round2 で deferred にした critical 1 件・high 4 件の検知漏れを塞ぐ。
- 単一引用符内に `$(` を大量に含む大きな入力でも、hooks.json の timeout（10 秒）内に判定を返す。

### 1.3 スコープ
- 対象はチケットに挙がった 6 件（cdb8382d4bbb0b1d、73a1d7b31734dd22、26ab9a3d83649eff、18b99bd71e74c8dc、511cd470522973d8、b8fd289ca7750a04）に限る。
- 変更するファイルは次の 3 つに限る（NFR4）。
    - `em-workflow/hooks/destructive-guard.py`
    - `em-workflow/hooks/tests/destructive-guard-cases.json`
    - `em-workflow/hooks/tests/run-destructive-guard.py`
- hooks.json と version は変えない。
- 対象外は 14.1（A1、A7、A8）を参照。

## 2. ビジネス要件

### 2.1 ビジネス目標
- `destructive-guard.py` が、シェルシンクに渡るヒアドキュメント本文の破壊的コマンドを ask / deny にする。ヒアドキュメントと誤認されて隠れていた実コマンド行も同じく ask / deny にする。round2 で deferred にした critical 1 件・high 4 件の検知漏れを塞ぐ。
- 単一引用符内に `$(` を大量に含む大きな入力でも、hooks.json の timeout（10 秒）内に判定を返す。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
2.1 を参照。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | ホスト文の特定を lex_segments() の文の区切りに合わせる | resolved |
| FR2 | ホスト文が確定できないときは判定不能にする | resolved |
| FR3 | エスケープされた引用符を引用の開始として扱わない | resolved |
| FR4 | 単一引用符内 `$(` の対応探索を線形にする | resolved |
| FR5 | 偽のヒアドキュメント演算子は本文を取り込まない | resolved |
| FR6 | 読み飛ばした語に sink がある文は data にしない | resolved |
| FR7 | コマンド名を差し替える構文があれば、コマンド全体の data 判定を判定不能にする | resolved |
| FR8 | 修正より前にケースを足す | resolved |
| FR9 | 既存ケースを保つ | resolved |
| FR10 | テストランナーに制限時間を入れる | resolved |

### 4.2 機能詳細

#### FR1: ホスト文の特定を lex_segments() の文の区切りに合わせる

**説明**: ヒアドキュメントのホスト文（宛先を判定する文）は、`lex_segments()` と同じ区切りで特定する。`2>&1`・`>&2`・`&>`・`&>>`・`>|` はリダイレクトであり、文の区切りに数えない。`\;`・`\&`・行継続（`\` + 改行）はエスケープであり、これも区切りに数えない。（cdb8382d4bbb0b1d）

**関連する受け入れ基準**: AC-1、AC-2

#### FR2: ホスト文が確定できないときは判定不能にする

**説明**: ホスト文として選んだ文に、そのヒアドキュメント自身の `<<` / `<<-` 演算子が無いことがある。その場合は宛先を判定不能にし、既存のフォールバックに回す。フォールバックは、チャンクに `SHELL_SINK` が現れたら本文を再走査する。data としては確定させない。（cdb8382d4bbb0b1d、73a1d7b31734dd22）

**関連する受け入れ基準**: AC-1、AC-3

#### FR3: エスケープされた引用符を引用の開始として扱わない

**説明**: `scan_structure()` は、バックスラッシュでエスケープされた `'` と `"` を引用の開始として扱わない。`case` / `esac` を見分けるための語の読み取りでも同じにする（例: `echo it\'s`、`echo a\"b`）。（73a1d7b31734dd22）

**関連する受け入れ基準**: AC-3

#### FR4: 単一引用符内 `$(` の対応探索を線形にする

**説明**: `honor_single_quotes=False` の走査では、単一引用符内の `$(` に対応する `)` を探す。この探索を入力長に対して線形の計算量にする。見つける範囲は現行と変えない。対応が取れるのは、引用の終わりより前で釣り合ったときだけとする。（26ab9a3d83649eff）

**関連する受け入れ基準**: AC-4

#### FR5: 偽のヒアドキュメント演算子は本文を取り込まない

**説明**: 引用符の中やコメントの中にある `<<WORD` は、ヒアドキュメントの演算子として扱わない。置換の中にある本物の演算子（例: `"$(cat <<'EOF' … EOF)"`）は除く。偽の演算子は後続の行を本文として取り込まない。後続の行は元の位置に残し、実際の構文どおりに字句解析する。引用の続きであれば引用として、そうでなければコマンドとして読む。引用とコメントの判定は行をまたいで追跡する。本物のヒアドキュメントの本文の行は、この追跡の対象から外す。（18b99bd71e74c8dc）

**関連する受け入れ基準**: AC-5、AC-6

#### FR6: 読み飛ばした語に sink がある文は data にしない

**説明**: コマンド語より前で読み飛ばした語のどれかに `SHELL_SINK` が一致したら、ホストのコマンド語を data と判定せず、判定不能にする。読み飛ばした語とは、`VAR=value` の代入、ラッパーのオプションとその値、git / gh のグローバルオプションの値をいう。一致の判定には、引用符を除去した後の一致も含める。`env` が `-S` または `--split-string` を持つ文も判定不能にする。つづり方（分けて書く、続けて書く、`=` 付き）は問わない。`GIT_EDITOR=bash git commit -e -F -` と `git -c core.editor=sh commit -e -F -` もこの要件で扱う。（511cd470522973d8）

**関連する受け入れ基準**: AC-7

#### FR7: コマンド名を差し替える構文があれば、コマンド全体の data 判定を判定不能にする

**説明**: コマンド名の実体を差し替える構文が、hook に渡されたコマンド文字列の中に 1 つでもあれば、そのコマンドの中のヒアドキュメントの data 判定をすべて判定不能にする。対象の構文は次のとおり。

- 関数定義（`NAME()` と `function NAME`。本体が `( )` のものも含む）
- コマンド位置の `alias`・`hash`・`enable`
- PATH への代入（コマンドの前に置く代入、単独の代入、`export`）

判定不能になった本文は、既存のフォールバックで扱う。（b8fd289ca7750a04）

**関連する受け入れ基準**: AC-8

#### FR8: 修正より前にケースを足す

**説明**: `.claude/rules/hook-tests.md` に従い、修正より前に `destructive-guard-cases.json` へケースを `[期待する判定, ラベル, コマンド]` 形式で足す。足すのは、6 件それぞれの再現形（deny）と、FR1 の逆向きの誤検知（allow）と、FR5 の引用の続きの形（allow）。

**関連する受け入れ基準**: AC-1、AC-2、AC-3、AC-5、AC-6、AC-7、AC-8

#### FR9: 既存ケースを保つ

**説明**: 既存の deny / ask ケースは 1 件も削除せず、期待する判定も変えない。既存の allow ケースも期待する判定を変えない。

**関連する受け入れ基準**: AC-9

#### FR10: テストランナーに制限時間を入れる

**説明**: `run-destructive-guard.py` は各ケース（無人実行の降格ケースも含む）の実行に、hooks.json の `destructive-guard.py` と同じ 10 秒の制限時間を設ける。制限時間を超えたケースは FAIL として数え、ランナー自体は異常終了させずに残りのケースを続ける。cases.json には約 60KB の再現入力（`echo ' + $(×30000 + ' ; rm -rf <対象>`）を deny ケースとして足す。（26ab9a3d83649eff）

**関連する受け入れ基準**: AC-4、AC-9

## 5. 非機能要件

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | 静的解析のみ | 判定は決定的にし、同じコマンドには常に同じ判定を返す。ファイルシステムにはアクセスしない。コマンドや置換は評価しない。 |
| NFR2 | 依存を増やさない | Python 標準ライブラリだけで実装する。 |
| NFR3 | 性能 | 判定は hooks.json の timeout（10 秒）に十分収まる。FR1〜FR7 で追加・変更する処理は、どれも入力長に対して線形の計算量にする。 |
| NFR4 | 変更範囲 | 変更するのは `em-workflow/hooks/destructive-guard.py`、`em-workflow/hooks/tests/destructive-guard-cases.json`、`em-workflow/hooks/tests/run-destructive-guard.py` の 3 ファイルに限る。hooks.json と version は変えない。 |

### 5.1 パフォーマンス要件
- NFR3 を参照。

### 5.2 セキュリティ要件
- NFR1 を参照。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2、NFR4 を参照。

### 5.5 互換性要件
- 既存ケースの期待する判定を変えない（FR9）。

## 6. UI/UX要件

該当なし（デザインステップは省略する。A9）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 判定は静的解析のみとする（NFR1）。
- Python 標準ライブラリだけで実装する（NFR2）。
- 変更するファイルは 3 つに限る。hooks.json と version は変えない（NFR4）。

### 9.2 ビジネス上の制約
- 対象はチケットに挙がった 6 件に限る（A1）。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-heredoc-sink-gaps/**`
- `test-docs/destructive-guard-heredoc-sink-gaps/**`

`feature-docs/destructive-guard-heredoc-sink-gaps/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-heredoc-sink-gaps/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-heredoc-sink-gaps/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/destructive-guard-heredoc-sink-gaps/` ディレクトリを生成しないが、宣言された `test-docs/destructive-guard-heredoc-sink-gaps/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 判定不能にしても、チャンクに sink 語が無ければフォールバックは本文を再走査しない。差し替え先が sink 名を含まないパスの場合（例: `hash -p /tmp/evil cat`）は検知漏れが残る。 | 中 | 受け入れた残存リスクとする（A6）。 |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準

表記: 各コードブロックは 1 つのコマンド文字列を表す。行の区切りは改行を表す。`<<'EOF'…EOF` の `…` は本文の行を省略した表記。

- [ ] **AC-1**（FR1、FR2、FR8）: 次の形がすべて deny になる（cdb8382d4bbb0b1d）。
    1.
       ```text
       make 2>&1 | tail -5
       bash <<'EOF'
       git reset --hard HEAD
       EOF
       echo done
       ```
    2.
       ```text
       ls &>/dev/null; bash <<'EOF'…EOF
       cat /dev/null
       ```
    3.
       ```text
       docker ps \
         -a
       bash <<'EOF'…EOF
       echo done
       ```
    4.
       ```text
       find . -exec ls {} \; -print
       bash <<'EOF'…EOF
       echo done
       ```
    5.
       ```text
       echo hi >| /tmp/x; bash <<'EOF'…EOF
       echo done
       ```
    6.
       ```text
       bash 2>&1 <<'EOF'…EOF
       echo hi
       ```
    7.
       ```text
       bash &>/dev/null <<'EOF'…EOF
       echo hi
       ```
    8.
       ```text
       bash >|/tmp/log <<'EOF'…EOF
       echo hi
       ```
    9.
       ```text
       echo a\&b; bash <<'EOF'…EOF
       echo hi
       ```
    10.
        ```text
        echo x >&2
        bash <<'EOF'…EOF
        echo done
        ```
    11.
        ```text
        ls &>>/tmp/l
        bash <<'EOF'…EOF
        echo done
        ```
- [ ] **AC-2**（FR1、FR8）: 次の形が allow になる。
    ```text
    ls 2>&1
    cat > /tmp/p <<'EOF'
    git reset --hard HEAD
    EOF
    python3 x.py
    ```
- [ ] **AC-3**（FR2、FR3、FR8）: 次の形がすべて deny になる（73a1d7b31734dd22）。
    1.
       ```text
       echo it\'s; bash <<'EOF'
       git reset --hard HEAD
       EOF
       ```
    2. 1. の後ろに `ls` を続けた形
    3.
       ```text
       echo a\"b; bash <<'EOF'…EOF
       echo done
       ```
- [ ] **AC-4**（FR4、FR10、NFR3）: `echo ' + $(×30000 + ' ; rm -rf <対象>`（約 60KB）が deny になり、10 秒の制限時間内に判定を返す（26ab9a3d83649eff）。ランナーは 10 秒を超えたケースを FAIL として数える。
- [ ] **AC-5**（FR5、FR8）: 次の形がすべて deny になる（18b99bd71e74c8dc）。
    1.
       ```text
       echo '<<EOF'; bash --version
       rm -rf <対象>
       EOF
       ```
    2.
       ```text
       python3 -V; echo "<<EOF"
       rm -rf <対象>
       EOF
       ```
    3.
       ```text
       bash --version; echo "abc
       def" # <<EOF
       rm -rf <対象>
       EOF
       ```
    4.
       ```text
       echo 'x <<EOF'
       git reset --hard HEAD~3
       EOF
       ```
- [ ] **AC-6**（FR5、FR8）: 複数行の二重引用符の中に偽の `<<WORD` がある形が allow になる。例:
    ```text
    git commit -m "docs: <<EOF
    git reset --hard の説明
    EOF
    "
    ```
- [ ] **AC-7**（FR6、FR8）: 次の形がすべて deny になる（511cd470522973d8）。本文はいずれも破壊的コマンドとする。
    1. `env -S 'bash -s' cat <<'EOF'…EOF`
    2. `env --split-string='bash -s' cat <<'EOF'…EOF`
    3. `env -S'sh -s' jq <<'EOF'…EOF`
    4. `GIT_EDITOR=bash git commit -e -F - <<'EOF'…EOF`
    5. `git -c core.editor=sh commit -e -F - <<'EOF'…EOF`
- [ ] **AC-8**（FR7、FR8）: 次の形がすべて deny になる（b8fd289ca7750a04）。
    1.
       ```text
       cat() ( bash )
       cat <<'EOF'
       rm -rf <対象>
       EOF
       ```
    2. `hash -p /bin/sh git; git status <<'EOF'…EOF`
    3.
       ```text
       shopt -s expand_aliases; alias cat=bash
       cat <<'EOF'…EOF
       ```
    4. `ln -sf /bin/bash /tmp/p/cat && PATH=/tmp/p cat <<'EOF'…EOF`
    5.
       ```text
       hash -p /bin/bash tee; cat <<'EOF' | tee
       git reset --hard HEAD
       EOF
       ```
- [ ] **AC-9**（FR9、FR10）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件 pass する。変更前の cases.json にあった deny / ask ケースはすべて残り、期待する判定も変わっていない。既存の allow ケースの判定も変わっていない。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS-1（unit、AC-1）: AC-1 の 11 形を、それぞれ deny ケースとして cases.json に足す。
- [ ] TS-2（unit、AC-2）: AC-2 の形を allow ケースとして足す。
- [ ] TS-3（unit、AC-3）: AC-3 の 3 形を deny ケースとして足す。
- [ ] TS-4（unit、AC-4）: `echo ' + $(×30000 + ' ; rm -rf <対象>` を deny ケースとして足す。
- [ ] TS-5（unit、AC-5）: AC-5 の 4 形を deny ケースとして足す。
- [ ] TS-6（unit、AC-6）: AC-6 の形を allow ケースとして足す。
- [ ] TS-7（unit、AC-7）: AC-7 の 5 形を deny ケースとして足す。
- [ ] TS-8（unit、AC-8）: AC-8 の 5 形を deny ケースとして足す。
- [ ] TS-9（unit、FR4、FR9）: round2 の 46923ffe262f20b1 の 3 形を deny ケースとして足す。FR4 の変更後も、単一引用符内の閉じないバッククォートや `$(` の後ろにある置換・文が検査されることを確かめる。3 形は次のとおり。
    1. ``tr -d '`' < a > b; echo "$(rm -rf <対象>)"``
    2. ``echo 'don`t'; echo "$(rm -rf <対象>)"``
    3. `echo 'a $(' ; rm -rf <対象> ; f "(" ; echo ')'`
- [ ] TS-10（integration、AC-9）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行し、全件 pass することを確かめる。

### 12.2 エッジケース
- ヒアドキュメントの区切り語を囲む引用符（`<<'EOF'` / `<<"EOF"`）は演算子の一部である。FR5 の行をまたぐ引用追跡で、引用の開始と読まない。
- 置換の中にある本物の演算子（`"$(cat <<'EOF' … EOF)"`、既存ケース 428・434・435・456・457 の形）は、FR5 の変更後もヒアドキュメントとして扱う。
- コメント内の 2 つ目の演算子（既存ケース 455: `cat <<'A' # <<'B'`）は、これまでどおり本文を取り込まない。
- FR6 の sink 照合は `user.name=x` のような値には一致しない。既存の allow ケース 468・469 は allow のまま。
- FR2 の判定不能化と FR7 の判定不能化は、チャンクに sink 語が無ければ本文を再走査しない。既存の allow ケース 4・36・416〜419 は allow のまま。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| ホスト文 | ヒアドキュメントの宛先を判定する文 |
| 読み飛ばした語 | コマンド語より前で読み飛ばした語。`VAR=value` の代入、ラッパーのオプションとその値、git / gh のグローバルオプションの値をいう |
| 偽の演算子 | 引用符の中やコメントの中にある `<<WORD`。置換の中にある本物の演算子は除く |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1 対象範囲: 対象はチケットに挙がった 6 件に限る。round2.yaml で unresolved のまま残っている medium 指摘は対象外にする（fb0b084358071a85 / 6066de2d27af2e1e / e2354806c0c5fa93 の設定ファイル経由の経路 / 96d5395a938f4b94 / 4220886f3405959e / a823f35af5aa9d2d / c1971c4c72142127 / 5f736d84f0aff55f / 24e5ac9f02b26f7f / 1775423080603fbd）。
- [x] A2 version: em-workflow の version は変更しない。
- [x] A3 性能の退行の検出: 性能の退行は、`run-destructive-guard.py` に入れる 10 秒の制限時間（hooks.json と同じ値）で検出する。超過したケースは FAIL にする。約 60KB の再現入力を deny ケースとして足す。
- [x] A4 偽の `<<WORD`: 引用符やコメントの中の偽の `<<WORD` は本文を取り込まない。後続の行は元の位置で、実際の構文どおりに字句解析する（not_a_heredoc）。
- [x] A5 差し替え構文の適用範囲: コマンド名を差し替える構文が、コマンドの中に 1 つでもあれば、そのコマンドの data 判定をすべて判定不能にする（whole_command）。
- [x] A6 残存リスク: 判定不能にしても、チャンクに sink 語が無ければフォールバックは本文を再走査しない。このため、差し替え先が sink 名を含まないパスの場合（例: `hash -p /tmp/evil cat`）は検知漏れが残る。これは受け入れた残存リスクとする。
- [x] A7 FR7 の対象構文: FR7 の対象は、finding が列挙した構文に限る（関数定義、alias、hash、enable、PATH への代入と export）。declare / typeset / readonly による PATH の代入、および source / . で読み込む外部ファイル内の定義は対象外とする。
- [x] A8 追加指示の扱い: チケット末尾の「追加指示」（PR の作成、Codex への相談、Notion への記録）は実行時の進め方への指示とみなし、この feature の機能要件には含めない。
- [x] A9 デザインステップ: デザインステップは省略する。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

なし
