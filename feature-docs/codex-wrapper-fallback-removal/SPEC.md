# Feature: codex-wrapper-fallback-removal

## Overview

`em-workflow/scripts/run_codex_exec.sh` が内部に持つプロバイダフォールバックチェーンを削除し、
ラッパーがあらゆる結果において `codex exec` をちょうど 1 回だけ実行するようにする。あわせて
ラッパーのタイムアウト（540 秒）を呼び出し側の Bash ツールのタイムアウト（600000 ミリ秒）の
内側に厳密に入れ子にし、`CODEX_TIMEOUT` の診断が常に呼び出し側へ届くようにする。プロバイダの
フォールバックはオーケストレーターの Phase R2b による `reviewers.yaml` のチェーン走査にのみ
存在する状態になる。要件の詳細は `feature-docs/codex-wrapper-fallback-removal/REQUIREMENTS.md`
を参照。

## Objectives

- ラッパー内部のプロバイダフォールバックチェーンを削除し、使用量上限に達した Codex アカウントが
  3 回の無言の試行で最大 1800 秒を消費するのではなく、自分自身の診断とともに即座に失敗するように
  する。
- プロバイダのフォールバックを 1 箇所だけ（オーケストレーターの Phase R2b による
  `reviewers.yaml` のチェーン走査）に存在させ、プロンプトの形を知っている層がハーネスを選ぶように
  する。
- ラッパーのタイムアウトを呼び出し側の Bash ツールのタイムアウトの内側に厳密に入れ子にし、
  `CODEX_TIMEOUT` の診断が常に呼び出し側へ届き、`rate_limited` の分類が素の `exit 124` に失われない
  ようにする。
- システムを説明するすべてのドキュメントとテストを、出荷されるラッパーと一致した状態に保つ。

## User Stories

### US1: 使用量上限に達したアカウントでの即時失敗

`codex-reviewer` の利用者として、使用量上限に達した Codex アカウントでは 1 回の呼び出しで即座に
失敗し、その診断をそのまま受け取りたい。無言の再試行に最大 1800 秒を費やしたくないため。

**Acceptance Criteria:**
- [ ] AC1: 使用量上限の診断を stderr に出して非ゼロ終了するスタブ `codex` に対し、ラッパーは呼び出しを
      ちょうど 1 回記録し、その呼び出し自身の終了コードで終了する。
- [ ] AC2: プロバイダエラーの診断でも同じ。`LITELLM_API_KEY` が設定され
      `~/.codex/litellm.config.toml` が存在する状態での使用量上限の診断でも同じ。
- [ ] AC3: いかなる結果のもとでも `CODEX_FALLBACK:` / `CODEX_FALLBACK_UNCONFIGURED:` で始まる行は出力
      されず、どちらの文字列も `em-workflow/scripts/run_codex_exec.sh` に現れない。

### US2: タイムアウト時に診断が呼び出し側へ届くこと

呼び出し側として、タイムアウトの際にラッパーの `CODEX_TIMEOUT` 行を受け取りたい。実行を
`rate_limited` に分類でき、情報量のない `exit 124` を受け取らずに済むため。

**Acceptance Criteria:**
- [ ] AC5: タイムアウトを超えてスリープするスタブは `exit 124` と stderr 行
      `CODEX_TIMEOUT: Codex did not respond within 540 seconds` を生む。無関係な非ゼロ終了はその終了
      コードとともにそのまま表面化する。
- [ ] AC6: 両方の `codex-cli.yaml` が `timeout: 540` を示し、3 つの呼び出し箇所がいずれも Bash ツールの
      `timeout` として `600000` ミリ秒を述べている。

### US3: ドキュメントとテストの整合

ドキュメントの読み手として、ラッパーの説明が出荷されるラッパーと一致していてほしい。一方で、
オーケストレーター側のフォールバック（Phase R2b）と Opus エスカレーションの記述は失われてほしく
ない。

**Acceptance Criteria:**
- [ ] AC9: `whether a fallback provider answered` と
      `The wrapper's reply may come from a fallback provider` のいずれの語句も 4 つのドキュメントに現れず、
      それらを固定する 4 つのテストが編集後のテキストに対して通る。
- [ ] AC10: `em-workflow/references/review-phase.md` の Phase R2b チェーン走査のテキスト、その
      `rate_limited` / `budget_exhausted` / `harness_unavailable` の表、`question-resolution.md` の Opus
      エスカレーションに関するすべての記述が、変更前とバイト単位で同一である。

## Technical Requirements

### Functional Requirements

- **FR1 — Delete the in-wrapper provider fallback chain:** `em-workflow/scripts/run_codex_exec.sh` は
  あらゆる結果において `codex exec` をちょうど 1 回だけ実行する（現在のエントリ 1、
  `--ignore-user-config` 付き）。削除対象は `ENTRY_ARGS_2`、`ENTRY_ARGS_3`、`PROVIDER_NAME_2`、
  `PROVIDER_NAME_3`、`FALLBACK_PROFILE_FILE`、`fallback_prerequisites_present()`、
  `is_usage_limit_response()`、`is_provider_error_response()`、`answering_entry` 変数とその分岐、
  `CODEX_FALLBACK:` と `CODEX_FALLBACK_UNCONFIGURED:` の両方の出力、およびチェーンを説明する
  ヘッダーコメントブロック（"Provider fallback chain"、"Switch-shape stream"、"Fallback environment
  prerequisites"、エントリ 1 のマーカー段落）。使用量上限やプロバイダエラーの応答はもはや切り替え
  条件ではない。切り替え自体が存在しないため。
- **FR2 — Keep the split stdout/stderr capture and the JSON-first output order:** `$OUTFILE` / `$ERRFILE`
  の `mktemp` ペア、その `trap ... EXIT` によるクリーンアップ、唯一の呼び出しに対する
  `> "$OUTFILE" 2> "$ERRFILE"` のリダイレクト、末尾の `cat "$OUTFILE" "$ERRFILE"` の順序を挙動として
  一字一句そのまま保持する。これにより `--output-schema` の JSON 応答が codex の大きな stderr バナー
  より前に出力され、その中に混入することがない。ラッパーを em-review の `2>&1` 結合形へ戻すことは
  しない。
- **FR3 — Preserve every non-chain wrapper behaviour:** 次は変更しない。
  `CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds` の stderr 診断とその `exit 124`、
  呼び出し自身の終了コードのパススルー、`</dev/null` による stdin リダイレクト、
  `set -euo pipefail` 下で必要な `|| <var>=$?` ガード、フラグ `--color never` /
  `--skip-git-repo-check` / `--ignore-rules` / `--ignore-user-config`、`readonly` / `readwrite`
  サンドボックス・effort・`-C`・`--output-schema` の引数処理（usage メッセージとエラーメッセージを
  含む）。
- **FR4 — Bound the wrapper call so the wrapper always times out first:**
  `em-workflow/references/codex-cli.yaml` と `em-review/references/codex-cli.yaml` の**両方**で
  `timeout: 600` を `timeout: 540` にし、次の各呼び出し箇所で Bash ツールの `timeout` パラメータを
  `600000` ミリ秒に設定する。(a) `em-workflow/agents/codex-reviewer.md` Step 5、
  (b) `em-review/agents/codex-reviewer.md` Step 5、(c) `em-workflow/references/question-resolution.md`
  の "Codex consultation procedure" step 2 にある直接のラッパー呼び出し。60 秒のマージンが、両方の
  タイマーが同時に切れるのではなくラッパーの `CODEX_TIMEOUT` 行が呼び出し側へ届くことを可能にする。
  Bash ツールのタイムアウトは散文で述べるツールパラメータであり、各 Step 5 のコードフェンス内の
  コマンドテキストはバイト単位で変更しない（NFR6）。
- **FR5 — Scope em-review to timeout alignment only:** em-review に触れるのはちょうど 2 点のみ。
  `codex-cli.yaml` のタイムアウト値（FR4）と、`em-review/agents/codex-reviewer.md` Step 5 の Bash
  ツールタイムアウト（FR4）。`em-review/scripts/run_codex_exec.sh` は変更しない（そもそもチェーンを
  持たない）。ヘッダーコメントの対応合わせ作業も行わない。
- **FR6 — Replace the superseded wrapper test module:**
  `tests/test_codex_wrapper_provider_fallback.py` を削除し、別のファイル名の**新規**モジュールで
  フォールバックなしの契約を検証する。使用量上限の応答とプロバイダエラーの応答がそれぞれ記録される
  `codex` 呼び出しをちょうど 1 回だけ生むこと、失敗した呼び出し自身の終了コードとその stdout + stderr
  が呼び出し側へ届くこと、どの結果でも `CODEX_FALLBACK:` / `CODEX_FALLBACK_UNCONFIGURED:` の行が一切
  出力されないこと、タイムアウト経路が `CODEX_TIMEOUT` と `exit 124` を保つこと、FR2 の分離キャプチャ
  順序（stdout の内容が stderr の内容より前）が成り立つこと。
- **FR7 — Document realignment: remove the in-wrapper-fallback claims, preserve R2b and Opus prose:**
  「ラッパー自身の応答がフォールバックプロバイダから来ることがある」という主張と「フォールバック
  プロバイダが応答したかどうかを記録する」義務を、ちょうど 4 つのドキュメントから削除する。
  `em-workflow/references/question-resolution.md`（Codex consultation procedure step 2 の "The
  wrapper's reply may come from a fallback provider instead of the primary one, with no provider name or
  detection mechanism named here."）、`em-workflow/references/batch-mode.md`（最終報告項目 "whether a
  fallback provider answered"）、`em-workflow/references/phase-state.md`（`resolution_note` の義務にある
  同じ語句）、`em-workflow/scripts/run_codex_exec.sh` のヘッダーコメント（FR1）。あわせてそれらを固定
  する 4 つのテストを更新する: `tests/test_question_resolution_doc.py`
  （`test_wrapper_fallback_provider_fact_stated_once_no_name`）、
  `tests/test_batch_quiet_output_discipline.py`、`tests/test_batch_quiet_output_audit_record_contract.py`
  （"the wrapper's hidden fallback-provider chain" への docstring 参照と必須語句のタプルの両方）、
  `tests/test_codex_wrapper_provider_fallback.py`（FR6 により削除）。**明示的に無編集で保持する**もの:
  オーケストレーターの Phase R2b による `reviewers.yaml` のチェーン走査に関するすべての記述、
  `rate_limited` / `budget_exhausted` / `harness_unavailable` のルーティング表、Opus エスカレーションに
  関するすべての記述。削除するのはラッパー内部の主張のみ。
- **FR8 — Leave the superseded SPEC entry as historical record:**
  `feature-docs/batch-codex-autonomous-decisions/SPEC.md` は編集しない。その FR13、TS-11、およびそれらを
  参照する依存関係・ファイル構成の行は、当時決定された内容の記録として残す。supersession の注記も追加
  しない。
- **FR9 — Patch-bump both plugins in both places:** `.claude/rules/core-plugin-version-bump.md` に従い、
  em-workflow を `0.1.76` → `0.1.77`、em-review を `0.5.9` → `0.5.10` に引き上げる。各値は
  `<plugin>/.claude-plugin/plugin.json` と、リポジトリルート `.claude-plugin/marketplace.json` の該当
  する `plugins[]` エントリに同一の値で書く。

### Non-Functional Requirements

- **NFR1 - Bounded worst-case wrapper duration:** 1 回のラッパー起動は、設定された 540 秒を超えない。
  最悪ケースは 3 x 600 秒 = 1800 秒から 540 秒へ下がり、Bash ツールの 600 秒の上限に収まる。この収まり
  は変更前には不可能だった。
- **NFR2 - Diagnostic preservation:** 唯一の呼び出しの stderr（`usage limit` メッセージとそのリセット
  時刻を含む）がそのまま呼び出し側へ届き、`codex-reviewer.md` Step 6 のレート上限テキスト照合が実行を
  `rate_limited` に分類できる。情報量のない `exit 124` を受け取ることがなくなる。
- **NFR3 - Untrusted-stream discipline:** レビュー対象リポジトリを引用し攻撃者の影響を受けうるモデル
  生成の stdout 応答から、制御フローの判断を一切行わない。チェーンの削除により、そのような判断点が
  再スコープではなく完全に消滅する。
- **NFR4 - No provider named in protocol documents:** バッチ解決のドキュメント群は引き続きプロバイダ名を
  一切挙げず、使用量上限の検出についても記述しない。本変更はその表面を縮小するだけであり、
  `em-workflow/references/` のどこにもプロバイダ名を導入してはならない。
- **NFR5 - Hermetic standard-library tests:** `python3 -m unittest discover -s tests` が 0 で終了し、
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` も引き続き通る。新規および編集するテスト
  コードは Python 標準ライブラリのみを import し、密閉状態を保つ（`PATH` 上のスタブ `codex`、隔離された
  `HOME`、ネットワークなし、実プロバイダなし）。
- **NFR6 - Step 5 invocation line stays byte-for-byte identical:**
  `tests/test_codex_reviewer_temp_file_isolation.py` は両プラグインの `codex-reviewer.md` にある正確な
  ラッパー呼び出し文字列を検証する。FR4 の Bash ツールタイムアウトはその行を変更してはならない。

## Implementation Approach

### Architecture

変更後の呼び出し階層は次のとおり。

```
呼び出し側（codex-reviewer.md Step 5 / question-resolution.md step 2）
  Bash ツール timeout = 600000 ms
    └─ run_codex_exec.sh   timeout = 540 s（codex-cli.yaml）
         └─ codex exec  ← 1 回のみ（FR1）
              stdout → $OUTFILE
              stderr → $ERRFILE
```

プロバイダのフォールバックはこの階層の外側、オーケストレーターの Phase R2b による
`reviewers.yaml` のチェーン走査にのみ存在する（A7）。`reviewers.yaml` は本フィーチャーでは編集
しない。

### Data Flow

```
codex exec → stdout ($OUTFILE) ─┐
           → stderr ($ERRFILE) ─┤→ cat "$OUTFILE" "$ERRFILE" → 呼び出し側
           → exit code ─────────┴→ そのままパススルー（タイムアウト時のみ 124 + CODEX_TIMEOUT）
```

結合された出力は JSON のあとに stderr が続く形で終わる。出力全体を単一の JSON ドキュメントとして
解析する消費者は失敗する。これを安全にしているのは `codex-reviewer.md` Step 6 の「抽出してから
解析する」挙動である（A5）。

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/review-phase.md`: Phase R2b のチェーン走査と
  `rate_limited` / `budget_exhausted` / `harness_unavailable` のルーティング表。無編集で保持する
  （FR7、AC10）。
- `em-workflow/agents/codex-reviewer.md` Step 6: レート上限テキストの照合による `rate_limited` 分類と、
  抽出してから解析する挙動（NFR2、A5）。
- `.claude/rules/core-plugin-version-bump.md`: バージョン引き上げの 2 箇所ルール（FR9）。

**External Dependencies:**
- `codex` CLI: ラッパーが実行する唯一の外部コマンド（FR1）。テストでは `PATH` 上のスタブで置き換える
  （NFR5）。
- Bash ツールの `timeout` パラメータ: 上限は 600000 ミリ秒であり、FR4 が指定する値はまさにその値。上に
  余裕はないため、将来の伸びを吸収できるのはラッパー側の値だけである（A8）。

### File Structure

```
em-workflow/
├── scripts/run_codex_exec.sh                 # FR1, FR2, FR3, FR7
├── references/
│   ├── codex-cli.yaml                        # FR4 (timeout: 540)
│   ├── question-resolution.md                # FR4 (step 2), FR7
│   ├── batch-mode.md                         # FR7
│   ├── phase-state.md                        # FR7
│   └── review-phase.md                       # 無編集（AC10）
├── agents/codex-reviewer.md                  # FR4 (Step 5), NFR6
└── .claude-plugin/plugin.json                # FR9 (0.1.77)
em-review/
├── references/codex-cli.yaml                 # FR4 (timeout: 540)
├── agents/codex-reviewer.md                  # FR4 (Step 5), NFR6
├── scripts/run_codex_exec.sh                 # 無編集（FR5, AC7）
└── .claude-plugin/plugin.json                # FR9 (0.5.10)
tests/
├── test_codex_wrapper_provider_fallback.py   # 削除（FR6）
├── <新規モジュール>.py                        # FR6（別名で新設）
├── test_question_resolution_doc.py           # FR7
├── test_batch_quiet_output_discipline.py     # FR7
├── test_batch_quiet_output_audit_record_contract.py  # FR7
└── test_codex_reviewer_temp_file_isolation.py        # NFR6（無変更で通ること）
.claude-plugin/marketplace.json               # FR9（両プラグイン）
feature-docs/batch-codex-autonomous-decisions/SPEC.md  # 無編集（FR8, AC11）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-wrapper-fallback-removal/**`
- `test-docs/codex-wrapper-fallback-removal/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1 (FR1): 唯一の呼び出しで使用量上限の stderr → 記録される呼び出しは 1 回、呼び出し側はその終了
      コードとその stderr を受け取り、マーカー行は出ない（AC1、AC3）。
- [ ] TS2 (FR1): プロバイダエラーの stderr → 単一呼び出しで同一の結果（AC2）。
- [ ] TS3 (FR1): かつてのフォールバック前提条件が構成された状態での使用量上限の stderr → 依然として 1 回の
      呼び出し。前提条件ゲートは消えている（AC2）。
- [ ] TS5 (FR2): stdout の JSON と大きな stderr バナー → ラッパーの結合出力で JSON がバナーより前に来る
      （AC4）。
- [ ] TS6 (FR3): 設定されたタイムアウトを超えてスリープするスタブ（フィクスチャ側で設定値を下げて時間を
      圧縮）→ `exit 124` と、設定値を示す `CODEX_TIMEOUT` 行（AC5）。
- [ ] TS7 (FR3): 無関係な非ゼロ終了 → そのまま表面化し、元の終了コードが保たれる（AC5）。

### Integration Tests

- [ ] TS8 (FR7, NFR4): ドキュメント固定の一括検査 — 4 つのドキュメントがラッパーフォールバックの主張を
      持たず、R2b / Opus の記述は変わっていない（AC9、AC10）。
- [ ] TS9 (FR9): 両プラグインについて `plugin.json` と `marketplace.json` のバージョン一致検査（AC12）。
- [ ] TS10 (NFR5): 両スイートのフル実行（AC13）。
- [ ] TS11 (FR4, FR5, NFR1, NFR6): タイムアウト設定の一括検査 — 両方の `codex-cli.yaml` が 540 を示し、
      3 つの呼び出し箇所すべてが 600000 ミリ秒の Bash ツールタイムアウトを述べ、固定された Step 5 の
      呼び出し行が保たれている（AC6、AC14）。
- [ ] TS12 (FR5, FR8): 無変更の一括検査 — `em-review/scripts/run_codex_exec.sh` と
      `feature-docs/batch-codex-autonomous-decisions/SPEC.md` が手つかずである（AC7、AC11）。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases

- [ ] TS4 (FR1, NFR3): 切り替えを示す形のテキストが stdout にのみ存在 → 挙動の差は一切なく、stdout 駆動の
      制御フローが残っていないことを示す（NFR3）。

### Performance Tests

- [ ] NFR1: 1 回のラッパー起動が設定された 540 秒を超えず、Bash ツールの 600 秒の上限に収まる。

## Security Considerations

- **Untrusted input:** モデル生成の stdout 応答はレビュー対象リポジトリを引用し、攻撃者の影響を受けうる。
  そこから制御フローの判断を一切行わない。チェーンの削除により、そのような判断点が完全に消滅する
  （NFR3、TS4）。
- **Information disclosure:** バッチ解決のドキュメント群は引き続きプロバイダ名を挙げず、使用量上限の検出も
  記述しない。`em-workflow/references/` にプロバイダ名を導入してはならない（NFR4）。
- **Test isolation:** 新規・編集するテストは標準ライブラリのみを使い、`PATH` 上のスタブ `codex`、隔離された
  `HOME`、ネットワークなし、実プロバイダなしで動く（NFR5）。

## Error Handling

| 条件 | ラッパーの挙動 | 根拠 |
|------|----------------|------|
| `codex` が使用量上限の診断を stderr に出して非ゼロ終了 | その stderr をそのまま通し、その終了コードで終了。再試行しない。 | FR1, FR3, NFR2 |
| `codex` がプロバイダエラーの診断を出して非ゼロ終了 | 同上 | FR1, AC2 |
| `codex` が 540 秒以内に応答しない | stderr に `CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds` を出し、`exit 124` | FR3, AC5 |
| 無関係な非ゼロ終了 | そのまま表面化し、元の終了コードを保つ | FR3, TS7 |
| いずれの場合も | `CODEX_FALLBACK:` / `CODEX_FALLBACK_UNCONFIGURED:` を出力しない | FR1, AC3 |

`timeout` は kill-after の猶予なしで使われるため、終了シグナルへの応答が遅い `codex` プロセスに対して
「ラッパーが呼び出し側のタイマーより先に必ず診断を出す」ことは保証されない。60 秒のマージンはそれを
圧倒的に起こりやすくするが、確実にはしない（A2）。

## Performance Optimization

### Performance Goals

- 1 回のラッパー起動の実行時間: 540 秒以内（NFR1）
- 最悪ケース: 3 x 600 秒 = 1800 秒 → 540 秒（NFR1）

ラッパーのタイムアウトを 600 秒から 540 秒へ下げることで、これまで 540〜600 秒の区間で成功していた Codex の
実行は打ち切られる。診断を素の `exit 124` に失う実行より、診断が残ったまま 60 秒早く打ち切られる実行の
ほうがましであるとして受容する（A1）。

## Success Criteria

- [ ] FR1〜FR9、NFR1〜NFR6 のすべてが実装され、テストされている
- [ ] TS1〜TS12 のすべてが通る
- [ ] AC1〜AC14 のすべてを満たす
- [ ] `python3 -m unittest discover -s tests` が 0 で終了し、
      `python3 em-workflow/hooks/tests/run-destructive-guard.py` が通る（AC13）
- [ ] `em-workflow/references/` にプロバイダ名が導入されていない（NFR4）
- [ ] `em-review/scripts/run_codex_exec.sh` と `feature-docs/batch-codex-autonomous-decisions/SPEC.md` が
      バイト単位で変更前と同一（AC7、AC11）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし（FR1〜FR9 はすべて `status: resolved`）。

## References

- 要件定義書: `feature-docs/codex-wrapper-fallback-removal/REQUIREMENTS.md`
- Phase R2b のチェーン走査とルーティング表: `em-workflow/references/review-phase.md`（無編集で保持）
- バージョン引き上げのルール: `.claude/rules/core-plugin-version-bump.md`
- 歴史的記録（無編集）: `feature-docs/batch-codex-autonomous-decisions/SPEC.md`
