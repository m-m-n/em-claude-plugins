---
title: "destructive-guard-rm-reason-positions"
created_date: 2026-10-03
status: draft
---

# destructive-guard-rm-reason-positions - 要件定義書

## 1. 概要

### 1.1 背景
destructive-guard の rm 拒否理由・確認理由には、対象の位置表記（`N番目のrmのM番目の対象`）が出る。この位置表記を、元のコマンド文字列を左から読んだときの rm と対象の位置に一致させる。

### 1.2 目的
- destructive-guard の rm 拒否理由・確認理由に出る位置表記（N番目のrmのM番目の対象）が、元のコマンド文字列を左から読んだときの rm と対象の位置に一致する
- 複数対象をまとめた rm-recursive の理由文にも、対象ごとに位置と代替コマンドの雛形が入る
- 判定（deny / ask / allow）と rule id は変えない

### 1.3 スコープ
- rm の呼び出し番号と対象番号の振り方（FR1〜FR3）
- 複数対象をまとめた rm-recursive の理由文への代替コマンドの雛形の追加（FR4）
- 判定・rule id・既存の文言の維持（FR5）
- 回帰テストの追加（FR6）
- 番号の振り方を書いたコメント・docstring の更新（FR7）

範囲外:
- 判定の変更（FR5）。`rm -rf -- -targets` が allow になる判定の穴は範囲外（前提 A2）
- `--` の無い単独の `-` の数え方（前提 A3）
- 位置表記の書式（前提 A4）
- 判定が 1 件だけのときの理由文（前提 A5）
- destructive-guard-cases.json へのケース追加（前提 A6）

## 2. ビジネス要件

### 2.1 ビジネス目標
1.2 目的のとおり。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 理由文の位置表記が、元のコマンド文字列上の rm と対象の位置に一致する
- 複数対象をまとめた rm-recursive の理由文で、対象ごとに位置と代替コマンドの雛形が分かる

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | 呼び出し番号は元のコマンド上の出現順 | rm の呼び出し番号を、元のコマンド文字列に rm のコマンド語が現れる順で振る |
| FR2 | 複数の経路で判定しても呼び出し番号は 1 つ | 同じ rm を複数の経路で判定しても、呼び出し番号は 1 つだけ消費する |
| FR3 | 対象番号は `--` を考慮した元のオペランド位置 | 対象番号を `--` を考慮した元のオペランド位置で数える |
| FR4 | まとめた rm-recursive の理由文に代替コマンドの雛形を入れる | まとめた理由文で、位置表記と代替コマンドの雛形を対にして並べる |
| FR5 | 判定・rule id・既存の文言を保つ | 判定・rule id・rm-root の理由文・CLAUDE_BATCH 下の文言・置換の目印を変えない |
| FR6 | 回帰テスト | 位置表記と代替コマンドの雛形を確かめる unittest を tests/ の下に追加する |
| FR7 | 番号の振り方を書いたコメント・docstring を実装に合わせる | 関係する docstring とコメントを FR1〜FR3 に合わせて書き直す |

### 4.2 機能詳細

#### FR1: 呼び出し番号は元のコマンド上の出現順

**説明**: rm の呼び出し番号（N番目のrm）は、元のコマンド文字列に rm のコマンド語が現れる順（左から 1 始まり）で振る。`$(…)`・バッククォートの本文、`bash -c` / eval / here-string のペイロード、シェルに渡るヒアドキュメント本文の中にある rm も、元の文字列上の位置で順序を決める。置換で始まる文（`$(which rm) -rf x` など）では、その置換トークンの位置を rm の位置とする。番号は全文を走査し終えてから振り、その後で理由文を組み立てる。

**状態**: resolved

#### FR2: 複数の経路で判定しても呼び出し番号は 1 つ

**説明**: 同じ rm を複数の経路で判定しても（置換で始まる文を route_substitution_headed_statement() と通常経路の両方で check_rm() に渡すなど）、呼び出し番号は 1 つだけ消費する。同じトークンには、どの経路でも同じ対象番号が付く。対象番号は元の引数位置に対応する。

**状態**: resolved

#### FR3: 対象番号は `--` を考慮した元のオペランド位置

**説明**: 対象番号（M番目の対象）は `--` を考慮した元のオペランド位置で数える。最初の `--` より前では `-` で始まる語はオプションで数えない。最初の `--` 自体は数えない。`--` より後ろの語は、`-` で始まる語や 2 つ目以降の `--` も含めて全部オペランドとして数える。`.is_operator` の語は今までどおり数えない。何を判定するかは変えず、変わるのは番号だけ（`--` の後ろの `-` 始まりのオペランドは、今までどおり判定しない）。

**状態**: resolved

#### FR4: まとめた rm-recursive の理由文に代替コマンドの雛形を入れる

**説明**: 最も強い判定に複数の対象が並んで strongest_rm_decision() が理由文を 1 つにまとめる場合、単独なら deletion_alternative() の雛形が付く rm-recursive の対象については、位置表記とその雛形（gio trash / mv / 制御文字の定型文）を対にして並べる。雛形の選び方（gio の有無、HOME 配下か、制御文字の有無）は変えない。対象の生文字列は入れない。単独でも雛形が付かない対象（rm-root、rm-unresolvable、一部が置換の rm-recursive）には雛形を付けない。

**状態**: resolved

#### FR5: 判定・rule id・既存の文言を保つ

**説明**: どのコマンドでも判定と rule id は変えない。rm-root の理由文は今までどおり RM_ROOT_SHAPE のトークンをそのまま出す。CLAUDE_BATCH 下で ask を deny に落とす文言も変えない。置換だけでできた対象に付ける固定の目印 [`$(...)`] も残す。

**状態**: resolved

#### FR6: 回帰テスト

**説明**: 再現手順の 4 つのコマンドと `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` について、理由文の位置表記と代替コマンドの雛形を確かめる unittest を tests/ の下に追加する。テストはフックを subprocess で起動し、PreToolUse の JSON を標準入力から渡す。

**状態**: resolved

#### FR7: 番号の振り方を書いたコメント・docstring を実装に合わせる

**説明**: rm_target_designation()、check_rm()、route_substitution_headed_statement() の docstring と、main() の呼び出し番号カウンタのコメントを、FR1-FR3 の番号の振り方に合わせて書き直す。

**状態**: resolved

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | 同じコマンド文字列からは、いつも同じ位置表記と同じ理由文が出る |
| NFR2 | 理由文に rm 対象の生文字列を入れない。フックの stdout に制御文字を出さない（destructive-guard-rm-holes の FR4 / NFR3 を保つ） |
| NFR3 | テストは Python 標準ライブラリの unittest だけを使う。HOME と PATH はテスト側で明示して渡す |
| NFR4 | プラグインの version は触らない（.claude/rules/core-plugin-version-bump.md） |

## 6. UI/UX要件

該当なし（フックの理由文の文字列と番号付けの変更だけで、UI も画面も無い）

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- テストは Python 標準ライブラリの unittest だけを使う（NFR3）
- プラグインの version は触らない（NFR4）

### 9.2 ビジネス上の制約
- 判定（deny / ask / allow）と rule id は変えない（FR5）

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/destructive-guard-rm-reason-positions/**`
- `test-docs/destructive-guard-rm-reason-positions/**`

`feature-docs/destructive-guard-rm-reason-positions/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/destructive-guard-rm-reason-positions/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/destructive-guard-rm-reason-positions/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/destructive-guard-rm-reason-positions/` ディレクトリを生成しないが、宣言された `test-docs/destructive-guard-rm-reason-positions/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR5）: `echo "$(rm -rf /var/x)"; rm -rf /tmp/y` の理由文が `/var/x` を「1番目のrmの1番目の対象」と示し、「2番目のrm」を含まない。判定は deny、rule id は rm-recursive のまま
- [ ] AC2（FR1, FR5）: `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` の理由文が拒否対象を「1番目のrmの1番目の対象」と示す。判定と rule id は変わらない
- [ ] AC3（FR2, FR5）: `$(printf rm) rm -rf /tmp/cache; rm -rf /var/valuable` の理由文に「3番目のrm」が出ない。位置表記は「1番目のrm」と「2番目のrm」だけで、`/var/valuable` は「2番目のrmの1番目の対象」と示される。判定と rule id は変わらない
- [ ] AC4（FR3, FR5）: `rm -rf -- -cache /tmp/scratch /var/valuable` の理由文が `/var/valuable` を「1番目のrmの3番目の対象」と示す。判定と rule id は変わらない
- [ ] AC5（FR4, FR5, NFR2）: `rm -rf /var/a /var/b` の理由文に、「1番目のrmの1番目の対象」と「1番目のrmの2番目の対象」のそれぞれについて代替コマンドの雛形（gio trash か mv）が入り、`/var/a` も `/var/b` も含まない。HOME 配下で gio がある場合は gio trash、gio が無い場合や HOME の外では mv の雛形になる
- [ ] AC6（FR5）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` の既存ケースで、判定が 1 件も変わらない
- [ ] AC7（FR6, NFR3）: AC1-AC5 を確かめる回帰テストが tests/ の下にあり、`python3 -m unittest discover -s tests` が成功する（既存の tests/test_destructive_guard_rm_reason.py も含む）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（AC1）: `echo "$(rm -rf /var/x)"; rm -rf /tmp/y` を渡し、deny / rm-recursive で、位置表記が「1番目のrmの1番目の対象」だけであることを確かめる
- [ ] TS2（AC2）: `bash -c 'rm -rf /var/valuable'; rm -rf /tmp/safe` を渡し、拒否対象が「1番目のrmの1番目の対象」と示されることを確かめる
- [ ] TS3（AC1）: 入れ子の形 `rm -rf $(rm -rf /var/x)` を渡し、内側の rm の対象が「2番目のrmの1番目の対象」と示されることを確かめる（外側の rm が先に現れる）
- [ ] TS4（AC3）: `$(printf rm) rm -rf /tmp/cache; rm -rf /var/valuable` を渡し、位置表記の呼び出し番号が {1, 2} だけで、`/var/valuable` が「2番目のrmの1番目の対象」であることを確かめる
- [ ] TS5（AC4）: `rm -rf -- -cache /tmp/scratch /var/valuable` を渡し、拒否対象が「1番目のrmの3番目の対象」と示されることを確かめる
- [ ] TS6（AC5）: HOME を固定し、`rm -rf /var/a /var/b` を gio ありと gio なしで、HOME 配下の 2 対象を gio ありで渡す。まとめた理由文で、どちらの位置にも雛形が付き、対象の文字列が無いことを確かめる
- [ ] TS7（AC6）: `python3 em-workflow/hooks/tests/run-destructive-guard.py` を実行し、全件成功することを確かめる
- [ ] TS8（AC7）: `python3 -m unittest discover -s tests` を実行し、全件成功することを確かめる

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 位置表記 | 理由文に出る `N番目のrmのM番目の対象` の表記。置換だけの対象に付ける [`$(...)`] を含む |
| 呼び出し番号 | 位置表記の N。元のコマンド文字列に rm のコマンド語が現れる順（左から 1 始まり） |
| 対象番号 | 位置表記の M。`--` を考慮した元のオペランド位置 |

## 14. 確認事項

### 14.1 確認済み事項

前提（いずれも後から変更可能）:

- [x] A1: 置換で始まり、置換の中身から rm と読める文（`$(printf rm) rm -rf /tmp/cache`）では、置換トークンを rm のコマンド語として扱い、その後ろの語からオペランドを数える。この場合、書いてある `rm` の語は 1 番目の対象、`/tmp/cache` は 2 番目の対象になる。どちらの経路でも同じ番号を使う。この文で deny になるのは置換経由の経路が `rm` の語を対象として判定するためで、FR5 で判定を変えないので、この対象にも位置表記が要る。判定される対象すべてに重ならない番号を付けられる数え方はこれだけ。置換から rm と読めない文（`$(foo) rm -rf /x`）では、今までどおり書いてある `rm` がコマンド語になる
- [x] A2: `--` の後ろにある `-` 始まりのオペランドは、番号には入れるが判定はしない。`rm -rf -- -targets` が allow になるのは前からある判定の穴で、FR5 によりこの機能の範囲外（round1.yaml a7026abc0ff69de7 の suggestion）
- [x] A3: `--` の無い単独の `-` は、今までどおりオペランドとして数えない。FR3 の範囲は `--` の扱いだけ
- [x] A4: 位置表記の書式 `N番目のrmのM番目の対象`（置換だけの対象に付ける [`$(...)`] を含む）は変えない。変わるのは N と M の値だけ
- [x] A5: 判定が 1 件だけのときの理由文は、今までどおりその対象の理由文をそのまま使う。FR4 が変えるのは、最も強い判定に対象が 2 つ以上並ぶときのまとめた理由文だけ
- [x] A6: destructive-guard-cases.json に追加は不要（判定は変わらず、誤爆も見逃しも新しく見つかっていない）。理由文の検証は unittest 側に置く

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- `.claude/rules/core-plugin-version-bump.md`
- destructive-guard-rm-holes の FR4 / NFR3
