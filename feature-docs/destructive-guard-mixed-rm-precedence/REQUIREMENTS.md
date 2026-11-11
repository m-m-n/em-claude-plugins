---
title: "destructive-guard-mixed-rm-precedence"
created_date: 2026-11-11
status: draft
---

# destructive-guard-mixed-rm-precedence - 要件定義書

## 1. 概要

### 1.1 背景

D6 で、destructive-guard に退行が入った。複合コマンドで、後ろのセグメントの rm 以外の ask が、先に集めた rm の deny を飲み込む。

### 1.2 目的

- 複合コマンドのどこかに deny になる再帰削除があるとき、destructive-guard はセグメントの順序や他の check の有無に関係なく deny と再帰削除側の理由 ID（rm-recursive / rm-root）を出す。
- 無人実行（CLAUDE_BATCH）では、エージェントが自分で直すために読む判定文に、再帰削除の対象の位置と書き換え案が残るようにする（今は git-amend などの理由に置き換わって消えている）。
- rm と rm 以外が混ざった形で同じ退行が再び起きたら、ケース表で検出できるようにする。判定段と理由 ID の両方を固定する。

### 1.3 スコープ

- `em-workflow/hooks/destructive-guard.py` の判定の優先順位（FR1〜FR4、FR8）
- `em-workflow/hooks/tests/run-destructive-guard.py` のケース形式（FR5）
- `em-workflow/hooks/tests/destructive-guard-cases.json` へのケース追加（FR6）
- コメントと `.claude/rules/hook-tests.md` の記述（FR7）

## 2. ビジネス要件

### 2.1 ビジネス目標

- 複合コマンドのどこかに deny になる再帰削除があるとき、セグメントの順序や他の check の有無に関係なく deny と再帰削除側の理由 ID（rm-recursive / rm-root）を出す。D6 で入った退行を直す。
- 無人実行（CLAUDE_BATCH）の判定文に、再帰削除の対象の位置と書き換え案が残る。
- rm と rm 以外が混ざった形の退行を、判定段と理由 ID の両方でケース表から検出できる。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | destructive-guard を通してコマンドを実行する Claude Code 利用者 |
| 無人実行のエージェント | CLAUDE_BATCH の下で動き、判定文を読んで自分でコマンドを直すエージェント |
| フックの開発者 | ケース表とランナーで destructive-guard の判定を確かめる人 |

### 2.3 期待される効果

- deny になる再帰削除を含む複合コマンドが、後ろや前に rm 以外の ask 源があっても deny になる。
- 無人実行の判定文に、再帰削除の対象の位置と書き換え案が入る。
- 同じ退行が起きたら、ケース表の判定段と理由 ID の比較で FAIL になる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 再帰削除と rm 以外の ask 源が混ざった複合コマンドを判定する | destructive-guard（フック） | 高 |
| UC02 | 無人実行で判定文を読んでコマンドを直す | 無人実行のエージェント | 高 |
| UC03 | ケース表で判定段と理由 ID を確かめる | フックの開発者 | 高 |

### 3.2 ユースケース詳細

#### UC01: 再帰削除と rm 以外の ask 源が混ざった複合コマンドを判定する

**アクター**: destructive-guard（フック）

**事前条件**:
- コマンド文字列に、deny になる再帰削除のセグメントと rm 以外の ask 源のセグメントがある。

**基本フロー**:
1. statements() で文を順に走査し、rm 判定を集め、rm 以外の ask は走査の最後まで後回しにする。
2. 走査が終わったら、集めた rm の deny と後回しにした ask を、降格前の段で比べる。
3. rm の deny があれば、deny と再帰削除側の理由 ID を出す。
4. 優先を決めた後に、CLAUDE_BATCH による ask から deny への降格を行う。

**代替フロー**:
- 走査中に scan-budget-exceeded / ask_lex_unsettled になったら、その場で走査をやめる。集めた rm 判定に deny があれば（FR8 で候補から外した分は除く）deny と再帰削除側の理由を出す。無ければ今と同じ ask を出す。
- rm の削除対象そのものが SELF_CONFIG のために self-modification の ask が出た文では、その文の rm 判定を候補から外す（FR8）。
- rm 以外の deny は、今までどおりループの中ですぐ exit する（A2）。

**事後条件**:
- deny になる再帰削除があれば、判定は deny、理由 ID は rm-recursive または rm-root。

#### UC02: 無人実行で判定文を読んでコマンドを直す

**アクター**: 無人実行のエージェント

**事前条件**:
- CLAUDE_BATCH が立っている。

**基本フロー**:
1. エージェントが、deny になる再帰削除と rm 以外の ask 源を含む複合コマンドを実行しようとする。
2. destructive-guard が deny / rm-recursive（または rm-root）を返す。
3. 判定文には、再帰削除の対象の位置（rm_target_designation）と書き換え案が入る。

**事後条件**:
- 判定文に git-amend など rm 以外の理由の文言は入らない。

#### UC03: ケース表で判定段と理由 ID を確かめる

**アクター**: フックの開発者

**事前条件**:
- ケースの 4 要素目に `rule` がある。

**基本フロー**:
1. `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行する。
2. ランナーが判定段と、permissionDecisionReason の先頭 `[destructive-guard/<rule>]` から取り出した理由 ID を期待値と比べる。
3. どちらかが違えば FAIL にし、得られた理由 ID も出す。

**代替フロー**:
- `rule` が無いケースは判定段だけを比べる。
- `rule` が文字列でない、または知らないキーがあるときは malformed case として実行を止める。

**事後条件**:
- 全件通るか、FAIL の行に得られた理由 ID が出る。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 後ろの rm 以外の ask より、先に集めた rm の deny を優先する | rm の deny の後に rm 以外の ask 源が続く複合コマンドを deny / 再帰削除側の理由 ID にする | 高 |
| FR2 | 順序を逆にしても同じ判定にする | rm 以外の ask 源が先でも deny / 再帰削除側の理由 ID にする | 高 |
| FR3 | 優先を決めてから降格する | 降格前の段で優先を決め、その後に CLAUDE_BATCH の降格を行う | 高 |
| FR4 | 走査の途中で出る ask も、集めた rm の deny には勝たない | scan-budget-exceeded / ask_lex_unsettled でも集めた rm の deny を出す | 高 |
| FR5 | ケースの 4 要素目に理由 ID を固定するキーを足す | ランナーが `rule` を受け付けて理由 ID も比べる | 高 |
| FR6 | 退行を検出するケースを足す | `rule` 付きのケースを destructive-guard-cases.json に足す | 高 |
| FR7 | コメントとドキュメントを今の制御の流れに合わせる | コメント・docstring・エラーメッセージ・hook-tests.md を修正後の動作に合わせる | 中 |
| FR8 | 同じ文の self-modification は、その文の rm 判定より優先する | rm の削除対象が SELF_CONFIG の文では、その文の rm 判定を候補から外す | 高 |

### 4.2 機能詳細

#### FR1: 後ろの rm 以外の ask より、先に集めた rm の deny を優先する

**説明**: deny になる再帰削除のセグメントの後に rm 以外の ask 源が続く複合コマンドの判定は deny とする。理由 ID は再帰削除側（rm-recursive。root やホームの形なら rm-root）にする。区切りは `;` `&&` `||` 改行のどれでも同じ。同じ文の中の self-modification は FR8 に従う。

対象の rm 以外の ask 源:
- check_git の git-amend
- check_permissions の chmod-broad / chown-recursive
- check_external の terraform / kubectl-destructive / cloud-iam / cloud-delete / systemctl-system / remote-exec / gh-pr-merge
- check_file_destruction の archive-overwrite
- 別の文の check_self_modification の self-modification

#### FR2: 順序を逆にしても同じ判定にする

**説明**: rm 以外の ask 源が先で、deny になる再帰削除が後ろのセグメントにある複合コマンドも deny とし、理由 ID は再帰削除側にする。rm 以外の ask は走査が終わるまで後回しにし、コマンド全体を見てから確定させる。今は最初の ask で exit するため後ろのセグメントを見ていない。

#### FR3: 優先を決めてから降格する

**説明**: rm の deny と rm 以外の ask を比べるときは降格前の段（ask）を使う。CLAUDE_BATCH による ask から deny への降格は、どれを優先するか決めた後に行う。発火する理由 ID は再帰削除側で、理由の本文に再帰削除の対象の位置（rm_target_designation）と書き換え案がそのまま入る。

#### FR4: 走査の途中で出る ask も、集めた rm の deny には勝たない

**説明**: statements() の走査中に scan budget を超えたとき（scan-budget-exceeded）と、LexBudgetExceeded / LexUnmatchedSubscript になったとき（ask_lex_unsettled）は、その場で走査をやめる。その時点で集めた rm 判定に deny があれば（FR8 で候補から外した分は除く）、deny と再帰削除側の理由を出す。deny が無ければ今と同じ ask を出す。statements() の「先に出た deny はすでに出ている」という前提のコメントは、D6 以後は成り立っていない。

#### FR5: ケースの 4 要素目に理由 ID を固定するキーを足す

**説明**: run-destructive-guard.py はケースの 4 要素目に任意の `rule`（空でない文字列）を受け付ける。`rule` があるケースでは、permissionDecisionReason の先頭 `[destructive-guard/<rule>]` から取り出した理由 ID も期待値と比べる。

**入力**:
- `rule`: 空でない文字列 - 期待する理由 ID（任意キー）

**出力**:
- 判定段か理由 ID のどちらかが違えば FAIL。FAIL の行には得られた理由 ID も出す。

**ビジネスルール**:
- `rule` が無いケースは今までどおり判定段だけを比べる。
- 3 要素のケースと、cwd / batch だけの 4 要素のケースは今と同じ結果になる。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| malformed case | `rule` が文字列でない、または知らないキーがある | 今までどおり実行を止める |

#### FR6: 退行を検出するケースを足す

**説明**: destructive-guard-cases.json に、少なくとも次のケースを `rule` 付きで足す。

- (a) task に挙がっている 5 つの形（rm の deny 対象 ; git commit --amend / ; chmod -R 777 /etc / && terraform destroy / ; kubectl delete pod x / ; gcloud projects add-iam-policy-binding ...）を、rm を先に置いた順と後ろに置いた順の両方で、それぞれ deny / rm-recursive に固定する。
- (b) 少なくとも 1 つの形の batch:true 版を deny / rm-recursive に固定する。
- (c) rm-root の形（rm -rf ~ ; git commit --amend）を deny / rm-root に固定する。
- (d) 別の文の self-modification との組み合わせと、FR8 の 3 つの例（TS-9・TS-12・TS-13）を固定する。

対象パスは既存ケースと同じ汎用の例（/home/user/valuable など）にし、マシン固有のパスは書かない。

#### FR7: コメントとドキュメントを今の制御の流れに合わせる

**説明**: 次を、修正後の動作（FR8 の例外も含む）と `rule` キーに合わせて書き換える。

- main() で strongest_rm_decision() を呼ぶ直前のコメント
- statements() の「a deny among them has been given」
- route_substitution_headed_statement() の docstring の、check_git() が exit するという記述
- run-destructive-guard.py のモジュール docstring と case_options() のエラーメッセージ
- `.claude/rules/hook-tests.md` のケース形式の説明

#### FR8: 同じ文の self-modification は、その文の rm 判定より優先する

**説明**: rm の呼び出しの削除対象そのものが保護された自己設定パス（SELF_CONFIG）なために self-modification の ask が出たとき、その ask は同じ文の rm 判定より優先する。

**ビジネスルール**:
- 「文」は、main() のループで statements() が 1 回 yield した単位を指す。ループの 1 回ごとに区別し、文字列や行が同じかどうかでは決めない。
- 別に yield されるコマンド置換の本文や bash -c の payload には広げない。
- その文の rm 判定（rm-recursive / rm-root / rm-unresolvable）は、プールで勝ちを決める候補から外す。
- self-modification の ask は他の ask と同じく走査の最後まで後回しにする。
- 他の文の rm の deny は、順序に関係なくこの ask に勝つ。
- CLAUDE_BATCH による降格は、優先を決めた後に行う。

**例**:
- `rm -rf ~/.claude/skills/foo` は ask / self-modification のまま（既存ケース 42 行目）。
- `rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json` は deny / rm-recursive。
- `rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable` は deny / rm-recursive。

**わかっている影響**: 1 つの rm に保護パスと /home/user/valuable を並べた形（`rm -rf ~/.claude/skills/foo /home/user/valuable`）は ask / self-modification のままになる。

## 5. 非機能要件

### 5.1 パフォーマンス要件

- NFR4: 後ろのセグメントまで見るようにしても、走査は既存の scan budget と線形の作業上限の中に収まる。どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない。

### 5.2 セキュリティ要件

- NFR1: 検出力を下げない。今 deny のコマンドは、修正後もすべて deny のまま。既存の deny / ask ケースは消さず、書き換えもしない（hook-tests.md のルール）。42 行目の `rm -rf ~/.claude/skills/foo`（ask）も含む。
- NFR3: ask を後回しにして後ろのセグメントを見るようにしたことで、そこで rm 以外の deny が見つかった場合は deny に変わってよい（強くなる方向の変化）。弱くなる方向の変化は許さない。FR8 の例外は、今 ask の形を ask のまま残すためのもので、今 deny の形を弱めない。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

- NFR2: どこにも deny が無いコマンドの判定段と理由 ID は今と変えない。ask が複数あるときは、今の実装が出している理由 ID がそのまま発火する（今と同じく、ループの中で最初に出た rm 以外の ask が、ループ後の unsettled / gh-pr-merge fallback / rm の ask より先に立つ）。
- NFR5: 判定は今までどおりコマンド文字列だけで決まる。同じコマンド文字列からは、同じ判定段・理由 ID・理由の本文が出る。
- NFR6: plugin.json / marketplace.json の version は触らない（バグ修正なので patch。上げるのは Actions）。

### 5.5 互換性要件

- 3 要素のケースと、cwd / batch だけの 4 要素のケースは今と同じ結果になる（FR5）。

## 6. UI/UX要件

該当なし（UI も画面も無い）。

## 7. データ要件

### 7.2 データ項目

| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| ケース（4 要素目） | cwd | 文字列 | × | ペイロードの作業ディレクトリ（既存） |
| ケース（4 要素目） | batch | 真偽値 | × | そのケースだけ CLAUDE_BATCH を立てる（既存） |
| ケース（4 要素目） | rule | 空でない文字列 | × | 期待する理由 ID（FR5 で追加） |

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

- ケースの判定は、今までどおりフックを subprocess で動かした出力で行う。テストからフックの関数を直接 import しない（A6）。
- ケースにマシン固有のパスやホームディレクトリのパスを書かない（FR6）。

### 9.2 ビジネス上の制約

- 既存のケースを 1 件も消さず、書き換えもしない（NFR1）。
- plugin.json / marketplace.json の version は触らない（NFR6）。

### 9.3 スケジュール制約

なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-mixed-rm-precedence/**`
- `test-docs/destructive-guard-mixed-rm-precedence/**`

`feature-docs/destructive-guard-mixed-rm-precedence/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-mixed-rm-precedence/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-mixed-rm-precedence/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 1 つの rm に保護パスと /home/user/valuable を並べた形（`rm -rf ~/.claude/skills/foo /home/user/valuable`）は ask / self-modification のままになる | 中 | わかっている影響として TS-15 で固定する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: CLAUDE_BATCH を立てずに、task の 5 つの形（rm を先に置いた順）を destructive-guard.py に渡すと、permissionDecision が deny、理由の先頭が [destructive-guard/rm-recursive] になる。
- [ ] AC2: 同じ 5 つの形で順序を逆にしても deny / rm-recursive になる。
- [ ] AC3: CLAUDE_BATCH を立てて rm の deny 対象 ; git commit --amend を渡すと deny / rm-recursive になる。理由の本文に「1番目のrmの1番目の対象」の位置表記と書き換え案が入り、git-amend の文言は入らない。
- [ ] AC4: rm -rf ~ ; git commit --amend は deny / rm-root になる。
- [ ] AC5: rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json は deny / rm-recursive になる。
- [ ] AC6: run-destructive-guard.py は `rule` 付きのケースで理由 ID が違えば FAIL にする（例: rule を git-amend にしたケースは修正後のフックで FAIL）。`rule` が無いケースは判定段だけで判定する。
- [ ] AC7: 追加したケースを含めて `python3 em-workflow/hooks/tests/run-destructive-guard.py` が全件通る（無人実行の降格チェックも含む）。
- [ ] AC8: 既存のケースを 1 件も消さず、書き換えもしない。
- [ ] AC9: `rm -rf ~/.claude/skills/foo` は ask / self-modification のまま。`rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable` は deny / rm-recursive。`rm -rf ~/.claude/skills/foo /home/user/valuable` は ask / self-modification。CLAUDE_BATCH を立てた `rm -rf ~/.claude/skills/foo` は deny / self-modification（降格は優先を決めた後）。
- [ ] AC10: rm -rf /home/user/valuable の後に、scan budget を超えるか lex を確定できない部分が続く形を作れるなら、それは deny / rm-recursive になる。

## 12. テストシナリオ

### 12.1 テスト観点

各シナリオは destructive-guard-cases.json のケースとして `rule` 付きで足す。表記は [期待する判定段, 理由 ID]。

- [ ] 正常系 TS-1 [deny, rm-recursive]: `rm -rf /home/user/valuable ; git commit --amend`
- [ ] 正常系 TS-2 [deny, rm-recursive]: `git commit --amend ; rm -rf /home/user/valuable`
- [ ] 正常系 TS-3 [deny, rm-recursive]: `rm -rf /home/user/valuable ; chmod -R 777 /etc` とその逆順
- [ ] 正常系 TS-4 [deny, rm-recursive]: `rm -rf /home/user/valuable && terraform destroy` とその逆順
- [ ] 正常系 TS-5 [deny, rm-recursive]: `rm -rf /home/user/valuable ; kubectl delete pod x` とその逆順
- [ ] 正常系 TS-6 [deny, rm-recursive]: `rm -rf /home/user/valuable ; gcloud projects add-iam-policy-binding p --member=user:a@example.com --role=roles/owner` とその逆順
- [ ] 正常系 TS-7 [deny, rm-recursive, batch:true]: `rm -rf /home/user/valuable ; git commit --amend`
- [ ] 正常系 TS-8 [deny, rm-root]: `rm -rf ~ ; git commit --amend`
- [ ] 正常系 TS-9 [deny, rm-recursive]: `rm -rf /home/user/valuable ; echo x > ~/.claude/settings.json`（別の文の self-modification）
- [ ] 境界値 TS-10 [ask、理由 ID は今の実装と同じ]: `rm -rf tmp/$X ; git commit --amend`（どちらも ask。今の出力は git-amend）
- [ ] 境界値 TS-11（作れる場合）[deny, rm-recursive]: `rm -rf /home/user/valuable` の後に、scan budget を超える入れ子が続く形
- [ ] 正常系 TS-12 [ask, self-modification]: `rm -rf ~/.claude/skills/foo`（既存の 42 行目と同じ形を `rule` 付きでもう 1 件足す。既存ケースは書き換えない）
- [ ] 正常系 TS-13 [deny, rm-recursive]: `rm -rf ~/.claude/skills/foo ; rm -rf /home/user/valuable`
- [ ] 正常系 TS-14 [deny, rm-recursive]: `rm -rf /home/user/valuable ; rm -rf ~/.claude/skills/foo`（TS-13 の逆順）
- [ ] 境界値 TS-15 [ask, self-modification]: `rm -rf ~/.claude/skills/foo /home/user/valuable`（わかっている影響を固定する）
- [ ] 正常系 TS-16 [deny, self-modification, batch:true]: `rm -rf ~/.claude/skills/foo`（優先を決めた後に降格する）
- [ ] 異常系 TS-17: `rule` 付きのケースで理由 ID が違えば run-destructive-guard.py が FAIL にする（例: rule を git-amend にしたケースは修正後のフックで FAIL）。`rule` が無いケースは判定段だけで判定する（AC6）。
- [ ] パフォーマンス: どのケースも GUARD_TIMEOUT_SECONDS（10 秒）を超えない（NFR4）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 文 | main() のループで statements() が 1 回 yield した単位 |
| rm 以外の ask 源 | git-amend / chmod-broad / chown-recursive / terraform / kubectl-destructive / cloud-iam / cloud-delete / systemctl-system / remote-exec / gh-pr-merge / archive-overwrite / 別の文の self-modification |
| 降格 | CLAUDE_BATCH による ask から deny への変換 |
| 理由 ID | permissionDecisionReason の先頭 `[destructive-guard/<rule>]` の `<rule>` |
| SELF_CONFIG | 保護された自己設定パス |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: rm 以外を先に置いた逆順の形も deny / rm-recursive に固定する（batch の回答 create-spec.reverse-order: A で確定）。
- [x] A2: rm 以外の deny と rm の deny が同じコマンドにあるときは、今の動作（rm 以外の deny はループの中ですぐ exit する）を残す（batch の回答 create-spec.deny-vs-deny: A で確定）。
- [x] A3: task の「同じ露出を持つ他の非 rm ask 源」は一部がコードと合わない。git-worktree-force-remove はコード上 deny（check_git）なので ask 源ではない。archive-overwrite は tar / unzip の -o / --overwrite から出るもので、sed -i からは出ない。要件はコード上の実際の ask 源を対象にする。
- [x] A4: 理由 ID を固定するには、ケースの 4 要素目に任意キー `rule` を足す（batch の回答 create-spec.rule-key: A で確定）。既存ケースには付け足さない。
- [x] A5: LICENSE ファイル、パッケージマニフェスト、E2E の仕組み、UI はどれも無い。
- [x] A6: ケースの判定は、今までどおりフックを subprocess で動かした出力で行う。テストからフックの関数を直接 import することはしない。
- [x] A7: FR8 の例外は、self-modification の ask が rm の削除対象から出たときだけ効く。rm の文で ask が redirect 先（例: `rm -rf /home/user/valuable > ~/.claude/settings.json`）だけから出た場合は、その文の rm 判定を候補から外さないので、rm の deny が勝つ。FR8 は rm の呼び出しを、普通の経路でもコマンド置換を先頭に置いた経路でも、同じ yield の中なら同じに扱う。
- [x] A8: 同じ文で transcript-write（deny）が出た場合は、rm 以外の deny なので今までどおりループの中ですぐ exit する（A2）。FR8 は self-modification の ask だけを対象にする。

### 14.2 未確認・保留事項

なし。

## 15. 参考資料

- `.claude/rules/hook-tests.md`: フックのテストのルール
