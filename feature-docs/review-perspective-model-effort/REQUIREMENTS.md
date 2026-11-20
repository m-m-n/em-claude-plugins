---
title: "review-perspective-model-effort"
created_date: 2026-11-20
status: draft
---

# review-perspective-model-effort - 要件定義書

## 1. 概要

### 1.1 背景
該当なし

### 1.2 目的
観点ごとの codex レビュアーの model と effort を reviewers.yaml で指定し、その値で codex exec を呼ぶ。

### 1.3 スコープ
- `em-workflow/references/reviewers.yaml`、`em-review/references/reviewers.yaml`
- `em-workflow/scripts/run_codex_exec.sh`、`em-review/scripts/run_codex_exec.sh`
- `em-workflow/agents/codex-reviewer.md`、`em-review/agents/codex-reviewer.md`
- 両プラグインの `review-phase.md`（R2 と round record）と `review-protocol.md`（Inputs）
- `em-workflow/README.md`、`em-review/README.md`
- `.claude/skills/security-review-model/SKILL.md`
- 各プラグインの `.claude-plugin/plugin.json` と、リポジトリルートの `.claude-plugin/marketplace.json` の version
- 上記に対応する `tests/` 配下のテスト

## 2. ビジネス要件

### 2.1 ビジネス目標
- 観点ごとの codex レビュアーの model と effort を reviewers.yaml で指定し、その値で codex exec を呼ぶ。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 各観点の codex レビュアーが、reviewers.yaml に書いた model と effort で codex exec を呼ぶ。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | codex レビュアーを観点の model と effort で起動する | オーケストレーター | 高 |

### 3.2 ユースケース詳細

#### UC01: codex レビュアーを観点の model と effort で起動する

**アクター**: オーケストレーター

**事前条件**:
- reviewers.yaml の観点の codex エントリが model と effort を持つ。

**基本フロー**:
1. オーケストレーターが review-phase.md の R2 で、エントリの model と effort を input block に加えて codex-reviewer を dispatch する。
2. codex-reviewer が Step 5 で、受け取った effort を `--effort "<effort>"` としてラッパーに渡す。
3. ラッパーが `-c 'model_reasoning_effort="<effort>"'` を付けて codex exec を呼ぶ。
4. オーケストレーターが round record の該当 run に effort を記録する。

**代替フロー**:
- エントリが effort を持たない場合、effort を渡さず、ラッパーは readonly の既定値 xhigh で動く。
- Codex が effort を拒否した場合、Step 6 の非 JSON 規則により harness_unavailable でスキップする。

**事後条件**:
- codex exec が、エントリの model と effort で呼ばれている。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | reviewers.yaml の codex エントリに effort を追加 | 両 reviewers.yaml の codex エントリに任意の effort キーを持たせる | 高 |
| FR2 | 観点ごとの model と effort | 各観点の codex エントリを表の値にする | 高 |
| FR3 | ラッパーの --effort 引数 | 両 run_codex_exec.sh に `--effort LEVEL` を足す | 高 |
| FR4 | モードごとの既定値 | --effort の有無とモードごとの -c の付け方 | 高 |
| FR5 | --litellm との併用（em-workflow のみ） | --effort と --litellm を併用できる | 高 |
| FR6 | codex-reviewer が effort を渡す | Step 5 で受け取った effort をラッパーに渡す | 高 |
| FR7 | オーケストレーターが effort を渡す | R2 でエントリの effort を input block に加える | 高 |
| FR8 | round record に effort を記録 | effort を渡した codex の run に effort を付ける | 高 |
| FR9 | README | チェーン表の順序を直し、effort の受け渡しの 1 文を足す | 中 |
| FR10 | security-review-model スキル | SKILL.md を新しい指定方法に合わせる | 中 |

### 4.2 機能詳細

#### FR1: reviewers.yaml の codex エントリに effort を追加

**説明**: `em-workflow/references/reviewers.yaml` と `em-review/references/reviewers.yaml` で、codex エントリに任意の effort キーを持たせる。

**ビジネスルール**:
- エントリは 1 行のフロー形式 `{harness: codex, model: M, effort: E}` で書く。
- litellm エントリには effort を付けない。
- ヘッダーのコメントに次の 2 点を書く。
    - codex エントリの effort はレビュアーにそのまま渡り、ラッパーの `--effort` になること。
    - effort が無いエントリは xhigh で動くこと。

#### FR2: 観点ごとの model と effort

**説明**: codex エントリを次の値にする。

| 観点 | model | effort |
|------|-------|--------|
| security | gpt-6.2-astra | xhigh |
| comprehensive | gpt-6.2-astra | high |
| architecture | gpt-6.2-astra | high |
| spec | gpt-6.2-sol | xhigh |
| performance | gpt-6.2-sol | xhigh |
| license | gpt-6.2-sol | low |

**ビジネスルール**:
- em-review も同じ値にする。ただし em-review には license 観点が無く、comprehensive の chain は空なので、この 2 つは対象外。
- 2 番目のエントリ `{harness: litellm, model: muse-spark}` は変えない。

#### FR3: ラッパーの --effort 引数

**説明**: `em-workflow/scripts/run_codex_exec.sh` と `em-review/scripts/run_codex_exec.sh` に `--effort LEVEL` を足す。

**入力**:
- `--effort LEVEL`: 文字列 - codex に渡す reasoning effort

**出力**:
- codex exec の argv に `-c 'model_reasoning_effort="LEVEL"'` を 1 つだけ置く。

**ビジネスルール**:
- この effort の -c は、launch の argv の中で今の EFFORT_FLAG と同じ位置に 1 つだけ置く。
- `--effort` を 2 回指定したら後の値を使う。
- usage の行とヘッダーのコメントに `--effort` を書く。

**バリデーション**:
| 項目 | ルール | エラーメッセージ |
|------|--------|------------------|
| LEVEL の有無 | 値が必要 | `ERROR: --effort requires an effort argument` |
| LEVEL の形式 | `^[a-z]+$` に一致する | 不正な値用の専用の 1 行（2 つのコピーで同じ文言） |

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 値なし | `--effort` に値が無い | exit 1。codex を起動しない |
| 不正な値 | LEVEL が `^[a-z]+$` に一致しない | exit 1。codex を起動しない |

#### FR4: モードごとの既定値

**ビジネスルール**:
- `--effort` が無ければ、readonly は今と同じく `-c 'model_reasoning_effort="xhigh"'` を付け、readwrite は何も付けない。
- `--effort` があれば、readonly では xhigh の代わりに指定した値を付け、readwrite でも指定した値を付ける。

#### FR5: --litellm との併用（em-workflow のみ）

**ビジネスルール**:
- em-workflow のラッパーでは `--effort` と `--litellm` を併用できる。
- `--litellm` ルートでも、指定した effort が xhigh の代わりに付く。
- `-m` と `--litellm` の併用を拒否する規則は今のまま。

#### FR6: codex-reviewer が effort を渡す

**説明**: `em-workflow/agents/codex-reviewer.md` と `em-review/agents/codex-reviewer.md` の Step 5 で、オーケストレーターから effort を受け取ったら、`--effort "<effort>"` を `"$PROMPT"` の前に加える。

**ビジネスルール**:
- 値はそのまま渡す。
- 受け取らなければ `--effort` を付けない。
- レビュアーが自分で effort を選ぶことはない。
- Codex が effort を拒否した場合は、今の Step 6 の非 JSON 規則により harness_unavailable でスキップする。専用の判定は足さない。

#### FR7: オーケストレーターが effort を渡す

**ビジネスルール**:
- 両 review-phase.md の R2 で、codex の dispatch の箇条書きを変える。エントリが `effort: E` を持てば、model と同じく input block に `effort: E` を加え、値をそのまま渡す。許可リストの検査はしない。
- 両 review-protocol.md の Inputs に effort の項目を足す。
    - 受け取るのは codex reviewer だけで、エントリが effort を持つときに限る。
    - ラッパーへは `--effort <effort>` としてそのまま渡り、無ければ readonly の xhigh になる。
    - Claude reviewer と litellm reviewer は effort を受け取らない。
- `em-workflow/references/review-protocol.md` の harness 説明の箇条書き（PROTOCOL_BULLETS_SHA256 の範囲）は変更しない。

#### FR8: round record に effort を記録

**ビジネスルール**:
- 両 review-phase.md の record で、effort を渡した codex の run に effort を付ける。
- 対象は em-workflow の R3a の perspectives_dispatched と R5 の perspective_runs（例と注記のコメントを含む）、em-review の該当 record（例と注記のコメントを含む）。
- litellm の run と、effort を渡していない codex の run には付けない。

#### FR9: README

**ビジネスルール**:
- `em-workflow/README.md` と `em-review/README.md` のチェーン表で、performance / spec / architecture の順序を codex → litellm muse-spark に直す。表記は各 README の既存の書き方に合わせる。
- 両 README の「reviewers.yaml が渡した model をレビュアーはそのまま -m に流す」の文の後に、codex エントリの effort も同じ経路でラッパーの `--effort` に渡ることを 1 文足す。
- `tests/test_llm_led_review_user_docs.py` の PINNED_CHAINS も同じ順序に直す。

#### FR10: security-review-model スキル

**ビジネスルール**:
- `.claude/skills/security-review-model/SKILL.md` を新しい指定方法に合わせる。
- 方針の 11 行目（ほかの観点は model を書かない）と 12 行目（xhigh 固定）、手順 2（xhigh への対応を確かめる）、手順 3（xhigh 固定の確認コマンド）を、reviewers.yaml の codex エントリの effort を使う形に直す。
- スキルの対象は security 観点のままにする。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- 入力検証（NFR2）: effort の値は `^[a-z]+$` に一致した場合だけ TOML 文字列に埋め込む。引用符・バックスラッシュ・空白などを含む値で codex を起動しない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR3: em-workflow と em-review のラッパーで、`--effort` の扱い（引数の形、検証、エラー文言、既定値、readwrite での振る舞い）を揃える。
- NFR4: テストは標準ライブラリだけを使い、本物の codex を呼ばない（PATH に置いた stub を使う）。
- NFR5: em-workflow と em-review の version の minor を手で上げる。対象は各プラグインの `.claude-plugin/plugin.json` と、リポジトリルートの `.claude-plugin/marketplace.json` の該当エントリで、同じ値に揃える。SPEC には上げる位置だけを書き、具体的な値は書かない。
- NFR6: ハッシュと literal で固定されている既存テストは、各テストの慣例どおり固定値をその場で更新し、Refreshed by のコメントを添える。固定そのものは外さない。

### 5.5 互換性要件
- NFR1: `--effort` を指定しないラッパーの起動では、launch の argv を今とバイト単位で同じにする（readonly は xhigh の -c が 1 つ、readwrite は無し）。対象は既定ルートと `--litellm` ルートの両方。

## 6. UI/UX要件

該当なし

## 7. データ要件

### 7.1 データモデル概要
該当なし

### 7.2 データ項目
| エンティティ | 項目名 | 型 | 必須 | 説明 |
|--------------|--------|-----|------|------|
| reviewers.yaml の codex エントリ | effort | 文字列 | × | ラッパーの `--effort` に渡る値。無ければ xhigh で動く |
| codex-reviewer の input block | effort | 文字列 | × | エントリが effort を持つときだけ渡す |
| round record の codex run | effort | 文字列 | × | effort を渡した codex の run にだけ付ける |

### 7.3 データ保持期間
該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| codex exec | ラッパーからの起動 | `-c 'model_reasoning_effort="LEVEL"'` |

### 8.2 API仕様要件
該当なし

## 9. 制約条件

### 9.1 技術的制約
- `em-workflow/references/review-protocol.md` の harness 説明の箇条書き（PROTOCOL_BULLETS_SHA256 の範囲）は変更しない。
- テストは標準ライブラリだけを使い、本物の codex を呼ばない。

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/review-perspective-model-effort/**`
- `test-docs/review-perspective-model-effort/**`

`feature-docs/review-perspective-model-effort/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/review-perspective-model-effort/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/review-perspective-model-effort/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/review-perspective-model-effort/` ディレクトリを生成しないが、宣言された `test-docs/review-perspective-model-effort/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| gpt-6.2-sol の slug の実在と、各モデルの表の effort への対応は、このタスクでは確かめない | 中 | 対応していなければ、実行時に harness_unavailable でチェーンの次に進む |

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 各観点の codex レビュアーが、FR2 の表の model と effort で codex exec を呼ぶ。経路（reviewers.yaml → review-phase.md R2 → codex-reviewer Step 5 → ラッパー `--effort`）が文書に書かれ、reviewers.yaml の値と wrapper の argv がテストで確かめられている。（FR1, FR2, FR3, FR6, FR7）
- [ ] AC2: `--effort` を指定しない readonly の起動で、`-c model_reasoning_effort="xhigh"` が 1 つだけ付く。readwrite では付かない。（FR4, NFR1）
- [ ] AC3: `--effort LEVEL` を指定すると、両ラッパーで `-c model_reasoning_effort="LEVEL"` が 1 つだけ付き、xhigh は付かない（readonly、readwrite、em-workflow の `--litellm` ルート）。（FR3, FR4, FR5, NFR3）
- [ ] AC4: `--effort` に値が無い場合と、`^[a-z]+$` に一致しない値の場合は、両ラッパーとも exit 1 で、codex を起動しない。（FR3, NFR2, NFR3）
- [ ] AC5: 両 review-phase.md の record で、effort を渡した codex の run に effort が記録される。（FR8）
- [ ] AC6: 両 README のチェーン表が codex → litellm muse-spark の順になり、effort の受け渡しの 1 文がある。PINNED_CHAINS も同じ順序になっている。（FR9）
- [ ] AC7: security-review-model の SKILL.md に、xhigh 固定と「ほかの観点は model を書かない」の記述が残っていない。（FR10）
- [ ] AC8: em-workflow と em-review の version の minor が、plugin.json と marketplace.json で同じ値に上がっている。（NFR5）
- [ ] AC9: `python3 -m unittest tests.test_codex_wrapper_model_flag tests.test_reviewers_primary_chains tests.test_contributor_tier_criteria` が通る。（FR1, FR2, FR3）
- [ ] AC10: `python3 -m unittest discover -s tests` が通る。（NFR6）

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: 両プラグインで readonly `--effort high` を指定すると、argv に `-c model_reasoning_effort="high"` が隣接して 1 つだけあり、xhigh の -c は無い（TS-1）
- [ ] 正常系: 両プラグインで readonly を `--effort` なしで起動すると xhigh の -c が 1 つだけある。readwrite を `--effort` なしで起動すると model_reasoning_effort の -c が無い（TS-2）
- [ ] 正常系: 両プラグインで readwrite `--effort low` を指定すると、low の -c が 1 つだけある（TS-3）
- [ ] 正常系: em-workflow で readonly `--litellm M --effort low` を指定すると、low の -c が 1 つだけあり、xhigh は無い（TS-4）
- [ ] 異常系: 両プラグインで `--effort` に値が無い場合と、不正な値（引用符入り、大文字、空白入り、空文字）の場合は、exit 1 で起動記録が無い（TS-5）
- [ ] 境界値: `--effort` と `-m`、`-C`、`--output-schema` を組み合わせても各フラグが隣接した組のまま残り、prompt が末尾にある。`--effort` を 2 回指定すると後の値になる（TS-6）
- [ ] 正常系: 両 reviewers.yaml の codex エントリの model と effort を literal で固定し、2 つのファイルで同じ観点の値が一致する（TS-7）
- [ ] 正常系: EXPECTED_CHAINS と EM_REVIEW_EXPECTED_CHAINS の codex エントリが model と effort を持つ（TS-8、TS-9）
- [ ] 正常系: usage の固定文字列が `--effort` を含む新しい usage になる。既定の xhigh の検査はそのまま通る（TS-10）
- [ ] 正常系: ハッシュと literal の固定値が文書の変更に合わせて更新されている（TS-11）
- [ ] 正常系: PINNED_CHAINS で performance / spec / architecture が codex → litellm `muse-spark` になる（TS-12）
- [ ] セキュリティ: 不正な effort 値で codex を起動しない（TS-5）
- [ ] パフォーマンス: 該当なし

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| effort | codex exec に `-c 'model_reasoning_effort="<effort>"'` として渡す値 |
| ラッパー | `em-workflow/scripts/run_codex_exec.sh` と `em-review/scripts/run_codex_exec.sh` |

## 14. 確認事項

### 14.1 確認済み事項
packet create-spec-q0001 への batch の回答。

- [x] wrapper.effort-flag: effort_flag_pattern。`--effort LEVEL` を受け取り、`^[a-z]+$` に一致すればそのまま渡す。値が無い・形式に合わない場合は exit 1 で codex を起動しない
- [x] wrapper.effort-readwrite: apply_in_readwrite。readwrite でも指定があれば -c で effort を付ける。指定が無ければ何も付けない
- [x] wrapper.effort-litellm: allow_with_litellm。`--litellm` ルートでも指定した effort が xhigh の代わりに付く
- [x] docs.readme-chain-table: fix_order_and_note_effort。両 README のチェーン表と PINNED_CHAINS を codex → litellm muse-spark に直し、effort も model と同じ経路でラッパーに渡すことを 1 文足す
- [x] skill.security-review-model-scope: fix_all_contradictions。11・12 行目と手順 2・3 を reviewers.yaml の effort を使う形に直す。対象は security 観点のまま
- [x] record.effort-in-round-record: record_effort。effort を渡した codex の run に effort を記録する（両プラグインの review-phase.md）
- [x] version.bump-level: minor_bump。em-workflow と em-review の version の minor を手で上げる（plugin.json と marketplace.json）
- [x] design-step: skip_design。設計ステップは skip

### 14.2 未確認・保留事項
- [ ] gpt-6.2-sol の slug が実在するか、各モデルが表の effort に対応しているかは、このタスクでは確かめない（A7）

### 14.3 前提
- A1: reviewers.yaml のキー名は effort とし、フロー形式の codex エントリに置く。litellm エントリには付けない。
- A2: オーケストレーターから codex-reviewer への入力名は effort とし、オーケストレーター側で許可リストの検査はしない。R2b と R4 は同じ input block を使うので、effort も一緒に渡る。
- A3: Codex が effort を拒否した場合は、既存の非 JSON 規則により harness_unavailable でスキップする。専用の判定は足さない。
- A4: usage は `[-m MODEL]` の直後に `[--effort LEVEL]` を入れる。エラー文言は `-m` の書き方に揃える（値が無い場合は「ERROR: --effort requires an effort argument」、不正な値には専用の 1 行）。2 つのコピーで同じ文言にする。
- A5: reviewers.yaml の version キー（em-workflow: 3、em-review: 2）は上げない。
- A6: 回答 wrapper.effort-flag=effort_flag_pattern、wrapper.effort-readwrite=apply_in_readwrite、wrapper.effort-litellm=allow_with_litellm、docs.readme-chain-table=fix_order_and_note_effort、skill.security-review-model-scope=fix_all_contradictions、record.effort-in-round-record=record_effort、version.bump-level=minor_bump、design-step=skip_design を採用した（batch での決定）。
- A7: gpt-6.2-sol の slug が実在するか、各モデルが表の effort に対応しているかは、このタスクでは確かめない。対応していなければ、実行時に harness_unavailable でチェーンの次に進む。

## 15. 参考資料

該当なし
