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
