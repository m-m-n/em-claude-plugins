# Codex 相談記録 — codex-wrapper-fallback-removal

無人実行（`--batch`）の create-spec フェーズで requirements-analyst が返した
5 件の未決事項を、`em-workflow/scripts/run_codex_exec.sh readonly` 経由の
Codex 相談で解決した記録。相談は 2 ターン。判断は各回ともオーケストレーター側で
option_id への写像として行い、Codex の文言をそのまま答えにはしていない。

- 相談先: Codex CLI（`codex exec`、read-only sandbox、reasoning effort xhigh）
- 応答モデル: gpt-6-astra / provider openai（フォールバックは発生していない）
- ターン 1: 5 問を 1 回の相談にまとめて提示
- ターン 2: Q5 のみ、新証拠を添えて再提示

## 決定一覧

| # | 論点 | 採用した選択肢 | ターン |
|---|---|---|---|
| Q1 | em-review の対象範囲 | `timeout_alignment_only` | 1 |
| Q2 | wrapper と Bash ツールの timeout の入れ子 | `shrink_wrapper_timeout` | 1 |
| Q3 | フォールバック語彙を pin している文書・テスト | `remove_all_fallback_vocabulary` | 1 |
| Q4 | 失効するテストモジュールと SPEC FR13 | `replace_module_keep_spec_history` | 1 |
| Q5 | stdout/stderr の分離捕捉 | `keep_split_capture` | 2（1 の結論から変更） |

## Q1. em-review の対象範囲 → `timeout_alignment_only`

**Codex の理由**: em-review のラッパーは既に単発実行で、削除対象のチェーンを
持たない。一方 `timeout: 600` と Bash ツール timeout 未指定は両プラグインに共通の
欠陥なので、この 2 点だけを揃えるのが妥当。各プラグインの `plugin.json` と
ルートの `marketplace.json` の値を一致させた patch bump が要る。

**採らなかった選択肢**:
- `em_workflow_only` — 共通の欠陥を片側に残す
- `full_parity` — ヘッダコメントまで寄せるのは今回の不具合と無関係に差分を広げる

**Codex が挙げたリスク**: em-review 利用者の実行時間も変わるため、検証と
リリースの範囲が広がる。

## Q2. timeout の入れ子 → `shrink_wrapper_timeout`

`em-workflow/references/codex-cli.yaml` の `timeout` を 540 に下げ、Bash ツール側の
`timeout` を 600000 ms にする。

**Codex の理由**: 540/600000 なら、ラッパーが必ず先に時間切れになり、終了処理と
`CODEX_TIMEOUT` の出力に 60 秒の余裕ができる。`equal_timeouts` と
`bash_timeout_only` は実質同じ設定で、同時失効の競合が残る。

**Codex の追加指摘**: この timeout 指定はレビュアーの Step 5 だけでなく、
`em-workflow/references/question-resolution.md` が定めるラッパー直接呼び出し
（batch の Codex 相談そのもの）にも適用が要る。

**Codex が挙げたリスク**: 従来 540〜600 秒で成功していた実行が打ち切られる。
`timeout` に kill-after の猶予が無いため、終了シグナルへの応答が遅い場合まで
「必ず先に診断を出せる」とは保証できない。

## Q3. フォールバック語彙 → `remove_all_fallback_vocabulary`

**Codex の理由**: `question-resolution.md` の該当箇所はラッパーを直接呼ぶ経路で
あり、オーケストレーター側の R2b chain walk へ言い換えると、実際には通らない
経路の説明になってしまう。チェーン削除後の usage limit は Opus escalation へ
落ちるので、「フォールバック提供元が答えることがある」という文と、
`resolution_note` への該当記載義務を削除するのが整合的。

**採らなかった選択肢**:
- `restate_as_orchestrator_chain` — 直接呼び出し経路に chain walk は無い
- `leave_docs_untouched` — 主張が偽ではなく空虚になるだけだが、文書が実装と食い違う

**Codex が挙げたリスク**: `fallback` 語を機械的に全削除すると、残すべき R2b や
Opus escalation の説明まで壊す。

## Q4. 失効するテストと SPEC → `replace_module_keep_spec_history`

**Codex の理由**: 既存の `tests/test_codex_wrapper_provider_fallback.py` は
チェーンの実現そのものを契約にしているため、単発実行を保証する別名モジュールへ
置き換えるのが明確。usage limit / provider error でも呼び出しが 1 回で終わり、
診断と終了コードが届き、切り替えマーカーが出ないことを検証すべき。
`feature-docs/batch-codex-autonomous-decisions/SPEC.md` の FR13 は、当時の決定を
示す履歴として残す。

**採らなかった選択肢**: `rewrite_module_and_amend_spec`、`keep_negative_tests_only`

**Codex が挙げたリスク**: FR13 に失効の注記が付かないため、現行要件と誤読される
可能性がある。

## Q5. stdout/stderr の分離捕捉 → `keep_split_capture`（ターン 1 の結論から変更）

**ターン 1 の Codex の結論**: `revert_to_combined`（em-review と同じ `2>&1` に戻す）。
ただし Codex 自身が「stderr の診断が JSON 出力の途中に混ざると、Step 6 の JSON 抽出が
難しくなる可能性がある」をリスクとして挙げた。

**ターン 2 で提示した新証拠**:
1. `codex exec` は毎回 stderr に大きなバナー（version / workdir / model / provider /
   sandbox / session id、プロンプト全文のエコー）を出す。約 8 KB のプロンプトで
   stderr は約 240 KB だった
2. レビュアーは `--output-schema` 付きで呼ぶため、stdout は単一の JSON オブジェクト
3. 現行の em-workflow ラッパーは `cat "$OUTFILE" "$ERRFILE"` で終わるので、JSON が
   先頭に来てバナーが混入しない
4. em-review は `2>&1` で本番稼働している

**ターン 2 の Codex の結論（変更）**: `keep_split_capture`。
理由は、`2>&1` では大量のバナーが JSON に先行し途中にも混ざり得ること、
em-review の本番稼働実績だけでは問題が起きないとは判断できないこと。
簡素化はチェーン専用の分岐・状態管理の削除で足り、分離捕捉と JSON 優先の
出力順は残すべき。

**Codex が挙げたリスク**: 分離しても JSON の後ろに stderr が付くため、出力全体を
単一 JSON として解析する実装なら失敗する。分離は JSON 内への混入を防ぐだけで、
解析の成功そのものは保証しない。

## design ステップ

`create-spec.design-step` ゲートは `references/batch-policies.yaml` の決定表で
`decide_autonomously` に解決した（Codex 相談の対象外）。requirements-analyst の
推奨どおり design ステップは `skipped`。

## ターン 3 — verify フェーズの統合チェック 2 件の判定（2026-09-13）

verify フェーズで、VERIFICATION.md「Integrated checks that belong only to this
phase」のうち 2 件が literal には不成立だった。いずれも「検証条件の文言と実態の
ズレ」であり、実装の欠陥かどうかが判断を要したため Codex に相談した。

- 相談先: Codex CLI（`em-workflow/scripts/run_codex_exec.sh readonly`）
- 相談は 1 回。2 問を同時に提示し、各問で A（verify failure として記録し rework）と
  B（PASS として記録し報告で言及）の二択を、賛否の材料込みで提示した。

### Q6: whole-repository phrase sweep の literal 不成立

除去対象の 2 語句は 4 つのプロトコル文書（`run_codex_exec.sh` ヘッダ /
`question-resolution.md` / `batch-mode.md` / `phase-state.md`）からは完全に
消えている。一方、除外節が `feature-docs/` しか挙げていないため、次の 2 群が hit する。

- `tests/` の 3 モジュール — 語句の不在を主張する negative assertion のリテラル
  そのもの。不在を検査するテストは、その語句を含まざるを得ない。
- `test-docs/codex-wrapper-fallback-removal/*.tests.yaml` — 本 feature の TDD
  red/green 記録。`feature-docs/` と同じ「feature ごとの保存履歴」の類。

- 提示した選択肢: A = verify failure として記録し rework へ回す / B = PASS と
  記録し、報告で文言の不備として言及するにとどめる
- 採用: **A**
- Codex の論拠: 明記された「`feature-docs/` 以外ではゼロ」という条件は満たして
  いない。検出された引用自体は妥当なので、実装の不具合ではなく検証条件の不整合
  として記録する。rework は該当テスト内の引用と保存履歴の除外を明文化して再検証
  するだけでよい。動作上の危険は減らないが、PASS の意味が検証者の解釈で変わる
  問題を防げる。

### Q7: change-set containment の不成立

implement の base commit から見た 32 ファイルの変更のうち、
`tests/test_reviewer_roles_protocol.py` だけが、どのタスクの `files` 宣言にも
`feature-docs/**` にも `test-docs/**` にも含まれない。変更内容は、task0002 が
`em-workflow/agents/codex-reviewer.md`（task0002 の `files` に宣言済み）の Step 5 に
散文 1 文を追加したことで、同モジュールが持つ「Step 0 以降 EOF まで」の sha256 pin を
再計算しただけ。アサーションの削除も弱体化も無い。NFR6（Step 5 の起動行を byte 単位で
不変に保つ）を裏づける細粒度 pin は `tests/test_codex_reviewer_temp_file_isolation.py`
にあり、こちらは change set に含まれていない（AC14 の要求どおり）。

- 提示した選択肢: A = verify failure として記録し rework へ回す / B = PASS と
  記録し、task0002 の `files` 宣言の記載漏れとして報告で言及するにとどめる
- 採用: **A**
- Codex の論拠: ハッシュ更新の必要性は説明できていても、宣言した変更範囲を超えた
  事実は残る。未変更の固定検査は NFR6 を裏づけるが、変更範囲の条件まで満たすことには
  ならない。rework は task0002 の `files` 宣言に当該テストを追加して変更範囲を再確認
  すればよい。コードを変更する必要はなく、今回の妥当な更新を根拠に未宣言の変更を
  暗黙に許す前例を防げる。

### 帰結

verify step を `failed`（`result: fail`、`failed_items` に IC1 / IC2、いずれも
`category: spec`）として記録し、batch の自動 rework（系譜 cap 未到達・hard cap
未到達）へ進む。
