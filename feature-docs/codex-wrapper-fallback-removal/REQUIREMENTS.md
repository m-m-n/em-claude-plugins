---
title: "codex-wrapper-fallback-removal"
created_date: 2026-09-13
status: draft
---

# codex-wrapper-fallback-removal - 要件定義書

## 1. 概要

### 1.1 背景

`em-workflow/scripts/run_codex_exec.sh` は、ラッパー内部にプロバイダのフォールバック
チェーンを持っている。使用量上限に達した Codex アカウントでは、このチェーンが 3 回の
無言の試行を重ね、最大 1800 秒（3 x 600 秒）を消費したうえで、呼び出し側には情報量の
ない `exit 124` しか返らない。プロバイダのフォールバックは、オーケストレーターの
Phase R2b が `reviewers.yaml` を走査する形でも実装されており、ラッパー内部のチェーンは
その重複になっている。

### 1.2 目的

- 使用量上限に達した Codex アカウントが、3 回の無言の試行で最大 1800 秒を消費するのでは
  なく、自分自身の診断メッセージとともに即座に失敗するよう、ラッパー内部のプロバイダ
  フォールバックチェーンを削除する。
- プロバイダのフォールバックを 1 箇所だけ（オーケストレーターの Phase R2b による
  `reviewers.yaml` のチェーン走査）に置き、プロンプトの形を知っている層がハーネスを
  選ぶ構造にする。
- ラッパーのタイムアウトを呼び出し側の Bash ツールのタイムアウトの内側に厳密に入れ子に
  し、`CODEX_TIMEOUT` の診断が常に呼び出し側へ届くようにする。これにより
  `rate_limited` の分類が素の `exit 124` に失われなくなる。
- システムを説明するすべてのドキュメントとテストを、出荷されるラッパーと一致した状態に
  保つ。

### 1.3 スコープ

対象は次のファイル群。

- ラッパー本体: `em-workflow/scripts/run_codex_exec.sh`
- タイムアウト設定: `em-workflow/references/codex-cli.yaml`、`em-review/references/codex-cli.yaml`
- 呼び出し側: `em-workflow/agents/codex-reviewer.md`、`em-review/agents/codex-reviewer.md`、
  `em-workflow/references/question-resolution.md`
- ドキュメント: `em-workflow/references/question-resolution.md`、
  `em-workflow/references/batch-mode.md`、`em-workflow/references/phase-state.md`
- テスト: `tests/test_codex_wrapper_provider_fallback.py`（削除と別名での新設）、
  `tests/test_question_resolution_doc.py`、`tests/test_batch_quiet_output_discipline.py`、
  `tests/test_batch_quiet_output_audit_record_contract.py`
- バージョン: `em-workflow/.claude-plugin/plugin.json`、`em-review/.claude-plugin/plugin.json`、
  リポジトリルートの `.claude-plugin/marketplace.json`

スコープ外は次のとおり。

- `em-review/scripts/run_codex_exec.sh`（そもそもチェーンを持たないため変更しない。FR5）
- `feature-docs/batch-codex-autonomous-decisions/SPEC.md`（歴史的記録としてそのまま残す。FR8）
- `reviewers.yaml`（本フィーチャーでは編集しない。A7）

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| BO1 | ラッパー内部のプロバイダフォールバックチェーンを削除し、使用量上限に達した Codex アカウントが 3 回の無言の試行で最大 1800 秒を消費するのではなく、自分自身の診断とともに即座に失敗するようにする。 |
| BO2 | プロバイダのフォールバックを 1 箇所だけ（オーケストレーターの Phase R2b による `reviewers.yaml` のチェーン走査）に存在させ、プロンプトの形を知っている層がハーネスを選ぶようにする。 |
| BO3 | ラッパーのタイムアウトを呼び出し側の Bash ツールのタイムアウトの内側に厳密に入れ子にし、`CODEX_TIMEOUT` の診断が常に呼び出し側へ届き、`rate_limited` の分類が素の `exit 124` に失われないようにする。 |
| BO4 | システムを説明するすべてのドキュメントとテストを、出荷されるラッパーと一致した状態に保つ。 |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow 利用者 | `codex-reviewer` および `question-resolution.md` の Codex 相談手順を通じてラッパーを呼び出す。 |
| em-review 利用者 | `em-review/agents/codex-reviewer.md` を通じてラッパーを呼び出す。本フィーチャーではタイムアウト値の変更のみが及ぶ（A6）。 |

### 2.3 期待される効果

- 1 回のラッパー起動の最悪実行時間が 3 x 600 秒 = 1800 秒から 540 秒に下がり、Bash ツールの
  600 秒の上限に収まる（NFR1）。
- 唯一の呼び出しの stderr（`usage limit` メッセージとそのリセット時刻を含む）がそのまま
  呼び出し側へ届き、`codex-reviewer.md` Step 6 のレート上限テキスト照合が実行を
  `rate_limited` に分類できる（NFR2）。
- モデル生成の stdout に基づく制御フロー判断が、再スコープではなく完全に消滅する（NFR3）。

## 3. ユースケース

### 3.1 ユースケース一覧

本フィーチャーはユーザー可視の操作面を持たず、新規 UI もスタイリングもデザインシステムも
伴わない。変更対象は 1 本の bash ラッパー、2 つの YAML タイムアウト値、4 つのプロトコル
ドキュメント、2 つのエージェントプロンプト、5 つのテストモジュール、3 つのバージョン文字列
である。したがってユースケースは定義しない。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | ラッパー内部のプロバイダフォールバックチェーンの削除 | resolved |
| FR2 | stdout/stderr 分離キャプチャと JSON 先行の出力順の維持 | resolved |
| FR3 | チェーン以外のラッパー挙動の完全保持 | resolved |
| FR4 | ラッパーが常に先にタイムアウトするような呼び出しの境界設定 | resolved |
| FR5 | em-review の変更範囲をタイムアウト整合のみに限定 | resolved |
| FR6 | 役目を終えたラッパーテストモジュールの置き換え | resolved |
| FR7 | ドキュメント整合: ラッパー内フォールバックの記述の削除と、R2b / Opus 記述の保持 | resolved |
| FR8 | 役目を終えた SPEC の記載を歴史的記録として残す | resolved |
| FR9 | 両プラグインのパッチバージョンを 2 箇所ずつ引き上げ | resolved |

### 4.2 機能詳細

#### FR1: ラッパー内部のプロバイダフォールバックチェーンの削除

**説明**: `em-workflow/scripts/run_codex_exec.sh` は、あらゆる結果において `codex exec` を
ちょうど 1 回だけ実行する（現在のエントリ 1、`--ignore-user-config` 付き）。

**削除対象**: `ENTRY_ARGS_2`、`ENTRY_ARGS_3`、`PROVIDER_NAME_2`、`PROVIDER_NAME_3`、
`FALLBACK_PROFILE_FILE`、`fallback_prerequisites_present()`、`is_usage_limit_response()`、
`is_provider_error_response()`、`answering_entry` 変数とその分岐、`CODEX_FALLBACK:` と
`CODEX_FALLBACK_UNCONFIGURED:` の両方の出力、およびチェーンを説明するヘッダーコメント
ブロック（"Provider fallback chain"、"Switch-shape stream"、"Fallback environment
prerequisites"、エントリ 1 のマーカー段落）。

**ビジネスルール**:
- 使用量上限の応答もプロバイダエラーの応答も、もはや切り替え条件ではない。切り替え自体が
  存在しないため。

#### FR2: stdout/stderr 分離キャプチャと JSON 先行の出力順の維持

**説明**: `$OUTFILE` / `$ERRFILE` の `mktemp` ペア、その `trap ... EXIT` によるクリーンアップ、
唯一の呼び出しに対する `> "$OUTFILE" 2> "$ERRFILE"` のリダイレクト、末尾の
`cat "$OUTFILE" "$ERRFILE"` の順序は、挙動として一字一句そのまま保持する。これにより
`--output-schema` の JSON 応答が codex の大きな stderr バナーより前に出力され、バナーの中に
混入することがない。

**ビジネスルール**:
- ラッパーを em-review の `2>&1` 結合形へ戻すことはしない。

#### FR3: チェーン以外のラッパー挙動の完全保持

**説明**: 次はすべて変更しない。

- `CODEX_TIMEOUT: Codex did not respond within ${TIMEOUT} seconds` の stderr 診断と、その
  `exit 124`
- 呼び出し自身の終了コードのパススルー
- `</dev/null` による stdin リダイレクト
- `set -euo pipefail` 下で必要な `|| <var>=$?` ガード
- フラグ `--color never`、`--skip-git-repo-check`、`--ignore-rules`、`--ignore-user-config`
- `readonly` / `readwrite` サンドボックス、effort、`-C`、`--output-schema` の引数処理（その
  usage メッセージとエラーメッセージを含む）

#### FR4: ラッパーが常に先にタイムアウトするような呼び出しの境界設定

**説明**: `em-workflow/references/codex-cli.yaml` と `em-review/references/codex-cli.yaml` の
**両方**で `timeout: 600` を `timeout: 540` にする。あわせて、次のすべての呼び出し箇所で
Bash ツールの `timeout` パラメータを `600000` ミリ秒に設定する。

1. `em-workflow/agents/codex-reviewer.md` Step 5
2. `em-review/agents/codex-reviewer.md` Step 5
3. `em-workflow/references/question-resolution.md` の "Codex consultation procedure" step 2 に
   ある直接のラッパー呼び出し

**ビジネスルール**:
- 60 秒のマージンが、両方のタイマーが同時に切れるのではなく、ラッパーの `CODEX_TIMEOUT` 行が
  呼び出し側に届くことを可能にする。
- Bash ツールのタイムアウトは散文で述べるツールパラメータであり、各 Step 5 のコードフェンス内の
  コマンドテキストはバイト単位で変更しない（NFR6）。

#### FR5: em-review の変更範囲をタイムアウト整合のみに限定

**説明**: em-review に触れるのはちょうど 2 点のみ。`codex-cli.yaml` のタイムアウト値（FR4）と、
`em-review/agents/codex-reviewer.md` Step 5 の Bash ツールタイムアウト（FR4）。

**ビジネスルール**:
- `em-review/scripts/run_codex_exec.sh` は変更しない（そもそもチェーンを持たない）。
- ヘッダーコメントの対応合わせ作業は行わない。

#### FR6: 役目を終えたラッパーテストモジュールの置き換え

**説明**: `tests/test_codex_wrapper_provider_fallback.py` を削除し、別のファイル名で新しい
モジュールを追加して、フォールバックなしの契約を検証する。

**検証内容**:
- 使用量上限の応答とプロバイダエラーの応答のそれぞれで、記録される `codex` 呼び出しがちょうど
  1 回であること
- 失敗した呼び出し自身の終了コードと、その stdout + stderr が呼び出し側に届くこと
- どの結果においても `CODEX_FALLBACK:` / `CODEX_FALLBACK_UNCONFIGURED:` の行が一切出力されない
  こと
- タイムアウト経路が `CODEX_TIMEOUT` と `exit 124` を保つこと
- FR2 の分離キャプチャの順序が保たれること（stdout の内容が stderr の内容より前）

#### FR7: ドキュメント整合: ラッパー内フォールバックの記述の削除と、R2b / Opus 記述の保持

**説明**: 「**ラッパー自身の**応答がフォールバックプロバイダから来ることがある」という主張と、
「フォールバックプロバイダが応答したかどうかを記録する」義務を、次の 4 つのドキュメントから
削除する。

| ドキュメント | 削除対象 |
|--------------|----------|
| `em-workflow/references/question-resolution.md` | Codex consultation procedure step 2 の "The wrapper's reply may come from a fallback provider instead of the primary one, with no provider name or detection mechanism named here." |
| `em-workflow/references/batch-mode.md` | 最終報告項目の "whether a fallback provider answered" |
| `em-workflow/references/phase-state.md` | `resolution_note` の義務にある同じ語句 |
| `em-workflow/scripts/run_codex_exec.sh` | ヘッダーコメント（FR1） |

あわせて、これらを固定している 4 つのテストを更新する。

- `tests/test_question_resolution_doc.py`（`test_wrapper_fallback_provider_fact_stated_once_no_name`）
- `tests/test_batch_quiet_output_discipline.py`
- `tests/test_batch_quiet_output_audit_record_contract.py`（"the wrapper's hidden fallback-provider
  chain" への docstring 参照と、必須語句のタプルの両方）
- `tests/test_codex_wrapper_provider_fallback.py`（FR6 により削除）

**明示的に保持するもの（無編集）**:
- オーケストレーターの Phase R2b による `reviewers.yaml` のチェーン走査に関するすべての記述
- `rate_limited` / `budget_exhausted` / `harness_unavailable` のルーティング表
- Opus エスカレーションに関するすべての記述

削除するのはラッパー内部の主張のみ。

#### FR8: 役目を終えた SPEC の記載を歴史的記録として残す

**説明**: `feature-docs/batch-codex-autonomous-decisions/SPEC.md` は編集しない。その FR13、TS-11、
およびそれらを参照する依存関係とファイル構成の行は、当時決定された内容の記録としてそのまま
残す。supersession の注記も追加しない。

#### FR9: 両プラグインのパッチバージョンを 2 箇所ずつ引き上げ

**説明**: `.claude/rules/core-plugin-version-bump.md` に従い、em-workflow を `0.1.76` → `0.1.77`、
em-review を `0.5.9` → `0.5.10` に引き上げる。各値は `<plugin>/.claude-plugin/plugin.json` と、
リポジトリルート `.claude-plugin/marketplace.json` の該当する `plugins[]` エントリに、同一の値で
書く。

## 5. 非機能要件

### 5.1 パフォーマンス要件

**NFR1 — ラッパーの最悪実行時間の上限**: 1 回のラッパー起動は、設定された 540 秒を超えない。
最悪ケースは 3 x 600 秒 = 1800 秒から 540 秒へ下がり、Bash ツールの 600 秒の上限に収まる。この
収まりは変更前には不可能だった。

### 5.2 セキュリティ要件

**NFR3 — 信頼できないストリームの規律**: レビュー対象リポジトリを引用し攻撃者の影響を受けうる
モデル生成の stdout 応答から、制御フローの判断を一切行わない。チェーンの削除により、そのような
判断点が再スコープではなく完全に消滅する。

### 5.4 保守性要件

**NFR2 — 診断の保持**: 唯一の呼び出しの stderr（`usage limit` メッセージとそのリセット時刻を
含む）がそのまま呼び出し側へ届き、`codex-reviewer.md` Step 6 のレート上限テキスト照合が実行を
`rate_limited` に分類できる。情報量のない `exit 124` を受け取ることがなくなる。

**NFR4 — プロトコルドキュメントでプロバイダ名を挙げない**: バッチ解決のドキュメント群は、引き
続きプロバイダ名を一切挙げず、使用量上限の検出についても記述しない。本変更はその表面を縮小する
だけであり、`em-workflow/references/` のどこにもプロバイダ名を導入してはならない。

**NFR5 — 標準ライブラリのみによる密閉テスト**: `python3 -m unittest discover -s tests` が 0 で終了
し、`python3 em-workflow/hooks/tests/run-destructive-guard.py` も引き続き通る。新規および編集する
テストコードは Python 標準ライブラリのみを import し、密閉状態を保つ（`PATH` 上のスタブ `codex`、
隔離された `HOME`、ネットワークなし、実プロバイダなし）。

### 5.5 互換性要件

**NFR6 — Step 5 の呼び出し行のバイト単位の同一性**: `tests/test_codex_reviewer_temp_file_isolation.py`
は両プラグインの `codex-reviewer.md` にある正確なラッパー呼び出し文字列を検証する。FR4 の Bash
ツールタイムアウトはその行を変更してはならない。

## 6. UI/UX要件

本変更にはユーザー可視の操作面がなく、新規 UI もスタイリングもデザインシステムも存在しない。
UI/UX 要件は定義しない。

## 7. データ要件

永続データモデルを導入・変更しない。データ要件は定義しない。

## 8. 外部連携

新たな外部連携は追加しない。ラッパーが行う外部呼び出しは、`codex exec` の 1 回のみである（FR1）。

## 9. 制約条件

### 9.1 技術的制約

- Bash ツールの `timeout` パラメータの上限は 600000 ミリ秒であり、FR4 が指定する値はまさにその値。
  上に余裕はないため、将来の伸びを吸収できるのはラッパー側の値だけである（A8）。
- Step 5 のラッパー呼び出し文字列は、両プラグインについて
  `tests/test_codex_reviewer_temp_file_isolation.py` が固定するバイト単位の契約である（A9）。
- 「フォールバック」という語彙の削除は、各箇所を読んで判断する必要があり、機械的な文字列置換で
  行ってはならない。同じ語は R2b のチェーン走査の記述、Claude フォールバックのルール、両方の
  `codex-reviewer.md` にあるスキーマパスのフォールバック、`question-resolution.md` の
  "Unlisted-gate fallback" というセクション名でも正当に使われている（A3）。
- プロバイダのフォールバックは、オーケストレーターの Phase R2b による `reviewers.yaml` のチェーン
  走査として存在し続ける。本変更が削除するのはラッパー側の重複であり、能力そのものではない。
  `reviewers.yaml` は本フィーチャーでは編集しない（A7）。

### 9.2 ビジネス上の制約

- `em-review/scripts/run_codex_exec.sh` と
  `feature-docs/batch-codex-autonomous-decisions/SPEC.md` は変更しない（FR5、FR8）。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files`
から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-wrapper-fallback-removal/**`
- `test-docs/codex-wrapper-fallback-removal/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、
`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、
`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズ
ドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/{feature}/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、
ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な
  絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。
  implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成
  しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| ID | 課題 | 内容 | 可逆性 |
|----|------|------|--------|
| A1 | タイムアウト短縮による取りこぼし | ラッパーのタイムアウトを 600 秒から 540 秒へ下げることで、これまで 540〜600 秒の区間で成功していた Codex の実行が打ち切られる。Codex が `shrink_wrapper_timeout` の残存リスクとして提起した。診断を素の `exit 124` に失う実行より、診断が残ったまま 60 秒早く打ち切られる実行のほうがましであるとして受容する。 | reversible |
| A2 | 終了保証の限界 | `timeout` は kill-after の猶予なしで使われるため、終了シグナルへの応答が遅い `codex` プロセスに対して「ラッパーが呼び出し側のタイマーより先に必ず診断を出す」ことは保証されない。60 秒のマージンはそれを圧倒的に起こりやすくするが、確実にはしない。 | reversible |
| A5 | 出力全体を 1 つの JSON として解釈する消費者 | 分離キャプチャは stderr が JSON の**中に**混入することを防ぐが、結合された出力は依然として JSON のあとに stderr が続く形で終わる。ラッパーの出力全体を単一の JSON ドキュメントとして解析する消費者は失敗する。これを安全にしているのは `codex-reviewer.md` Step 6 の「抽出してから解析する」挙動である。 | reversible |

### 10.2 ビジネスリスク

| ID | リスク | 内容 | 可逆性 |
|----|--------|------|--------|
| A4 | 歴史的 SPEC の誤読 | `feature-docs/batch-codex-autonomous-decisions/SPEC.md` の FR13 に supersession の注記を付けないため、後の読み手が現行要件と取り違えうる。その SPEC を手つかずの歴史的記録として保つコストとして受容する。 | reversible |
| A6 | em-review 側の検証・リリース範囲の拡大 | em-review のタイムアウト変更は、em-workflow の不具合に遭遇していない em-review 利用者の実行時間も変える。検証とリリースの対象範囲が広がる。 | reversible |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1 (FR1): 使用量上限の診断を stderr に出して非ゼロ終了するスタブ `codex` に対し、ラッパーは
      呼び出しをちょうど 1 回記録し、その呼び出し自身の終了コードで終了する。
- [ ] AC2 (FR1): プロバイダエラーの診断でも同じことが成り立ち、`LITELLM_API_KEY` が設定され
      `~/.codex/litellm.config.toml` が存在する状態での使用量上限の診断でも同じ。かつての前提条件
      ゲートはもはや存在せず、何も変えない。
- [ ] AC3 (FR1): いかなる結果のもとでも、`CODEX_FALLBACK:` または `CODEX_FALLBACK_UNCONFIGURED:` で
      始まる行を出力する実行は存在しない。どちらの文字列も
      `em-workflow/scripts/run_codex_exec.sh` のどこにも現れない。
- [ ] AC4 (FR2): `{"ok":1}` を stdout に、複数行のバナーを stderr に書くスタブに対し、ラッパーの
      結合出力では stdout の内容全体がいかなる stderr の内容よりも厳密に前にある。スクリプトは
      codex 呼び出しに `2>&1` を含まない。
- [ ] AC5 (FR3): タイムアウトを超えてスリープするスタブは `exit 124` と stderr 行
      `CODEX_TIMEOUT: Codex did not respond within 540 seconds` を生む。無関係な非ゼロ終了はその
      終了コードとともにそのまま表面化する。
- [ ] AC6 (FR4): `grep '^timeout:' em-workflow/references/codex-cli.yaml` と em-review 側の対応物が
      どちらも `540` を返し、3 つの呼び出し箇所（em-workflow Step 5、em-review Step 5、
      question-resolution.md の Codex consultation procedure step 2）がいずれも Bash ツールの
      `timeout` として `600000` ミリ秒を述べている。
- [ ] AC7 (FR5): `git diff --stat` が `em-review/scripts/run_codex_exec.sh` に変更がないことを示す。
- [ ] AC8 (FR6): `tests/test_codex_wrapper_provider_fallback.py` が存在せず、置き換えモジュールが
      別名で存在し、その検証が AC1〜AC5 を覆う。
- [ ] AC9 (FR7): `whether a fallback provider answered` と
      `The wrapper's reply may come from a fallback provider` のいずれの語句も 4 つのドキュメントに
      現れず、それらを固定する 4 つのテストが編集後のテキストに対して通る。
- [ ] AC10 (FR7, 保持): `em-workflow/references/review-phase.md` の Phase R2b チェーン走査のテキスト、
      その `rate_limited` / `budget_exhausted` / `harness_unavailable` の表、`question-resolution.md`
      の Opus エスカレーションに関するすべての記述が、変更前とバイト単位で同一である。
- [ ] AC11 (FR8): `feature-docs/batch-codex-autonomous-decisions/SPEC.md` が変更前とバイト単位で同一
      である。
- [ ] AC12 (FR9): em-workflow が `0.1.77`、em-review が `0.5.10` を `plugin.json` と
      `marketplace.json` の両方で示し、プラグインごとに 2 箇所の値が一致している。
- [ ] AC13 (NFR5): `python3 -m unittest discover -s tests` が 0 で終了し、
      `python3 em-workflow/hooks/tests/run-destructive-guard.py` が通る。
- [ ] AC14 (NFR6): `tests/test_codex_reviewer_temp_file_isolation.py` が無変更のまま通る。あるいは
      どうしても触れる必要がある場合でも、その `WRAPPER_INVOCATION_LINE` 定数は変わっていない。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1 (FR1): 唯一の呼び出しで使用量上限の stderr → 記録される呼び出しは 1 回、呼び出し側は
      その終了コードとその stderr を受け取り、マーカー行は出ない（AC1、AC3）。
- [ ] TS2 (FR1): プロバイダエラーの stderr → 単一呼び出しで同一の結果（AC2）。
- [ ] TS3 (FR1): かつてのフォールバック前提条件が構成された状態での使用量上限の stderr → 依然として
      1 回の呼び出し。前提条件ゲートは消えている（AC2）。
- [ ] TS4 (FR1, NFR3): 切り替えを示す形のテキストが stdout にのみ存在 → 挙動の差は一切なく、stdout
      駆動の制御フローが残っていないことを示す（NFR3）。
- [ ] TS5 (FR2): stdout の JSON と大きな stderr バナー → ラッパーの結合出力で JSON がバナーより前に
      来る（AC4）。
- [ ] TS6 (FR3): 設定されたタイムアウトを超えてスリープするスタブ（フィクスチャ側で設定値を下げて
      時間を圧縮）→ `exit 124` と、設定値を示す `CODEX_TIMEOUT` 行（AC5）。
- [ ] TS7 (FR3): 無関係な非ゼロ終了 → そのまま表面化し、元の終了コードが保たれる（AC5）。
- [ ] TS8 (FR7, NFR4): ドキュメント固定の一括検査 — 4 つのドキュメントがラッパーフォールバックの
      主張を持たず、R2b / Opus の記述は変わっていない（AC9、AC10）。
- [ ] TS9 (FR9): 両プラグインについて `plugin.json` と `marketplace.json` のバージョン一致検査
      （AC12）。
- [ ] TS10 (NFR5): 両スイートのフル実行（AC13）。
- [ ] TS11 (FR4, FR5, NFR1, NFR6): タイムアウト設定の一括検査 — 両方の codex-cli.yaml が 540 を示し、
      3 つの呼び出し箇所すべてが 600000 ミリ秒の Bash ツールタイムアウトを述べ、固定された Step 5 の
      呼び出し行が保たれている（AC6、AC14）。
- [ ] TS12 (FR5, FR8): 無変更の一括検査 — `em-review/scripts/run_codex_exec.sh` と
      `feature-docs/batch-codex-autonomous-decisions/SPEC.md` が手つかずである（AC7、AC11）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| ラッパー内フォールバックチェーン | `em-workflow/scripts/run_codex_exec.sh` の中で、エントリ 1 の応答に応じてエントリ 2・エントリ 3 へ切り替える仕組み。本フィーチャーで削除する（FR1）。 |
| Phase R2b チェーン走査 | オーケストレーターが `reviewers.yaml` を走査して行うプロバイダフォールバック。本フィーチャー後も唯一のフォールバック実装として残る（BO2、A7）。 |
| 分離キャプチャ | `> "$OUTFILE" 2> "$ERRFILE"` で stdout と stderr を別ファイルに取り、最後に `cat "$OUTFILE" "$ERRFILE"` で結合する方式（FR2）。 |
| `rate_limited` | `codex-reviewer.md` Step 6 がレート上限テキストの照合により与える実行の分類（NFR2）。 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] requirement.timeout-nesting: タイムアウトはラッパー 540 秒 / Bash ツール 600000 ミリ秒の入れ子に
      する。540〜600 秒の区間で成功していた実行が打ち切られること（A1）と、`timeout` に kill-after の
      猶予がないため診断到達が確実ではないこと（A2）を受容する。
- [x] requirement.doc-vocabulary-scope: 「フォールバック」語彙の削除は各箇所を読んで行い、機械的な
      文字列置換はしない（A3）。
- [x] requirement.superseded-test-and-spec: 役目を終えたテストモジュールは削除して別名で置き換え、
      `feature-docs/batch-codex-autonomous-decisions/SPEC.md` は注記なしで手つかずのまま残す（FR6、
      FR8、A4）。
- [x] requirement.wrapper-output-stream: 分離キャプチャを維持する。結合出力は JSON のあとに stderr が
      続く形のままであり、それを安全にしているのは Step 6 の抽出してから解析する挙動である（FR2、A5）。
- [x] requirement.em-review-scope: em-review はタイムアウト整合の 2 点のみに触れる。検証とリリースの
      対象範囲が広がることを受容する（FR5、A6）。

### 14.2 未確認・保留事項

- なし（すべての機能要件・非機能要件が resolved）。

## 15. 参考資料

- `em-workflow/references/review-phase.md`: Phase R2b のチェーン走査と、`rate_limited` /
  `budget_exhausted` / `harness_unavailable` のルーティング表（変更しない）
- `.claude/rules/core-plugin-version-bump.md`: バージョン引き上げの 2 箇所ルール（FR9）
- `feature-docs/batch-codex-autonomous-decisions/SPEC.md`: FR13 / TS-11 を含む歴史的記録（変更しない）
- `feature-docs/codex-wrapper-fallback-removal/codex-consultation.md`: 本要件の確認事項の由来
