# Codex 相談記録 — verify フェーズの合否判定

- 実施: 2026-09-14 (JST)
- 経路: `codex exec`（read-only sandbox）→ 利用上限（解除予定 2026-09-19）で取得不可。
  LiteLLM プロファイル `litellm` 経由の `vertex-glm-5` にフォールバックして完走。
- 論点: 1 問（リポジトリスイートの既存失敗 6 件を、この feature の verify 失敗として
  扱うか）

## 論点

VERIFICATION.md の Test Verification は `python3 -m unittest discover -s tests` の
Expected を「終了コード 0」と書き、成功基準 AC9 は「リポジトリスイートが変更前と
同じく成功」と書いている。実測は `Ran 4596 tests / FAILED (failures=6)` で非ゼロ。

一方、この feature の base commit `dbeb7fb`（1 行も触る前の状態）を一時 worktree に
checkout して同じスイートを流すと、**完全に同一の 6 件が同じく失敗**した。失敗テスト名も
件数も総テスト数も一致し、この feature は新規の失敗を 1 件も導入していない。

## 提示した選択肢

- **選択肢 A（pass）**: verify は当該 feature の統合検証であり、base 比較で回帰ゼロが
  実証されている。AC9 の「変更前と同じく」を「変更前と同一の結果」と読む。既存 6 件は
  別タスクとして起票する。
- **選択肢 B（fail）**: Expected が「終了コード 0」と明記されている以上、実測が非ゼロなら
  fail とし、rework で既存 6 件を直しに行く。

## 第二意見の回答と採用した判断

選択肢 A を採用した。理由は 3 点:

1. AC9 の「変更前と同じく成功」は「変更前との差分ゼロ」と読める。base commit で同一
   6 件が失敗していた実測がその条件を満たす。
2. SPEC がスコープを「コード修正はせず回帰テストのみ追加」と明示的に限定している以上、
   verify は当該 feature 単体の影響範囲を判定する場であり、リポジトリ全体の健全性判定の
   場ではない。
3. fail にして rework で既存 6 件を直すと、SPEC で承認されていない作業に踏み込む。
   無関係な別コミットが壊したものを、無関係な feature で修正することになる。

第二意見が選択肢 A の論拠として挙げた点と、こちらの判断は一致した。食い違いは無い。

## 判定根拠の明示（第二意見の補足を受けて記録）

VERIFICATION.md の文言（「終了コード 0」）と、実際に適用した判定基準（base 比較で
回帰ゼロ）にはズレがある。pass 判定の根拠は「終了コード 0 を観測した」ではなく、
次の 2 点である:

- hook suite `python3 em-workflow/hooks/tests/run-destructive-guard.py` が 236/236 passed
  （終了コード 0、FAIL 行なし）
- repository suite は base commit `dbeb7fb` と HEAD で失敗集合が完全一致（6 件、同一
  テスト名）。この feature による新規回帰はゼロ

## 残件

リポジトリスイートの既存失敗 6 件は本 feature のスコープ外のため、別タスクとして起票する。

- `test_develop_once_option.test_argument_hint_line_includes_once_and_retains_existing_tokens`
- `test_step_c_verify_failed_default.test_batch_auto_select_wording_present`
- `test_step_c_verify_failed_default.test_batch_non_packet_gates_reference_present`
- `test_muse_consent_version_bump.test_em_workflow_manifest_nonversion_content_unchanged`
- `test_codex_wrapper_fallback_removal_version_bump.test_em_workflow_reads_0_1_78`
- `test_muse_consent_no_new_questions.test_no_develop_or_review_document_exceeds_its_pinned_budget`
