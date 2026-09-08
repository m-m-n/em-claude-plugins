# Implementation Plan: batch-verify-rework-lineage-cap

## Overview

batch モードの verify 自動 rework 上限を系譜カウント化し、cap 到達後も走行を
止めずに retrospect と Step C まで到達させる。実行コードは無く、em-workflow
プラグインの Markdown SSOT・プラグインマニフェスト 2 件・Python の構造テスト
だけを変更する。

## Technology Stack

- **Language / Framework**: Markdown（SSOT ドキュメント）+ Python 3 標準
  ライブラリ `unittest`（構造テスト）
- **Key libraries**: なし。**新規に導入する外部依存は 1 件も無い**（NFR3）。
- **License**: `project.license` は `none`。新規依存が無いため互換性の判断点は
  発生せず、記録すべき新規依存のライセンスも無い。

## Layer Structure

プラグインは実行コードではなく 3 層のドキュメント/ガード構成を持つ。

| Layer | 実体 | 責務 |
|---|---|---|
| Protocol | `em-workflow/skills/develop/SKILL.md` | オーケストレーターの手順。フェーズ内の判断・分岐の本文 |
| Reference | `em-workflow/references/*.md` | 契約・スキーマ・ゲート表。Protocol から参照される定義集 |
| Guard | `tests/*.py` | 上記 2 層に対する構造的・テキスト的アサーション |

許される依存方向:

- Guard → Protocol / Reference（テストはドキュメントを読む。逆は無い）
- Protocol ⇄ Reference（相互参照は可。ただし **1 つの事実の定義本文は
  どちらか一方にのみ置く** — NFR1）

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| cap 定義 SSOT | 系譜 cap / hard cap の値と数え方の唯一の定義本文 | 定義本文は SKILL.md「verify フェーズ」節にのみ置く。`batch-mode.md` と `workflow-schema.md` は同節を参照するだけで、cap の数値も数え方も書かない | task0001（定義側）/ task0002・task0003（参照側 — 数値を書かない） |
| `batch` ブロック構造 | workflow.yaml が持つ rework 履歴の永続構造 | `review_rework_count`（据え置き）+ `verify_rework.rounds` + `verify_rework.failed_id_counts` の 3 キー。構造の定義元は `references/workflow-schema.md`。`verify_rework_count` は構造から消える | task0001（定義）/ 他タスクは参照のみ |
| Step C 見出し文字列 | Step C 節の開始境界であり、同時に実行条件の記述そのもの | 新しい見出し全文は task0002 が確定する。確定した文字列は SKILL.md の見出しと、2 つのテストモジュールの見出し定数の計 3 箇所で**一字一句同一**であること。他タスクは Step C の見出し行を変更しない | task0002（所有）/ task0004（本文のみ編集、見出しには触れない） |
| cap 到達走行の終端状態 | 外部サービスへの唯一の機械可読な結果通知 | `state=stopped` / `step=verify` / `reason=verify_rework_cap_reached`。`detail` に「Step C まで到達し worktree 掃除と終了報告を完了」の旨を含める。`references/batch-terminal-line.md` は変更しない | task0002 |
| `follow_up_drafts` | cap 到達時に未解決で残った項目の機械可読な引き渡し | 生成母集団は「cap 到達時点で未解決の `failed_items` 全件」。フィールドは `origin_kind` / `origin_id` / `title` / `body` の 4 つ。対の意味は `references/rework-task-synthesis.md` Invariant 6 を参照し、再定義しない | task0003 |
| SKILL.md セクション所有権表 | 並列実装時の衝突面を最小化する編集境界 | 下記「D3」の表のとおり、1 節につき編集タスクは 1 つ。表に無い節は誰も編集しない | 全タスク |
| 既存テストモジュールのシンボル所有権表 | 既存の pin を壊す変更の責任所在 | 下記「D8」の表のとおり、ファイル単位ではなくシンボル単位で所有する | task0001 / task0002 |

## Conventions

- **新規テストモジュールの命名**: `tests/test_<topic>.py`。既存の
  `test_*_skill_wiring.py` / `test_*_version_bump.py` の命名感覚に合わせる。
- **テストの書き方**（NFR3 / NFR4）: 標準ライブラリ `unittest` のみを import
  する。サードパーティの存在も前提にしない。既存モジュールに倣い、(a) 自
  モジュールが標準ライブラリだけを import していることを検査するクラスと、
  (b) 同じ matcher が旧文言の合成テキストに対して失敗することを示す負の証明
  クラスを併せて置く。
- **アサーションの粒度**: 見出し・ラベルでセクションを切り出し、その内側で
  文言を検査する。全文検査は「消えたことの確認」にのみ使う。
- **テスト隔離規律（最重要）**: あるタスクが新規に書くテストは、**そのタスク
  自身が変更するファイルに対してのみ**アサートしてよい（D2）。
- **用語**: 「系譜 cap」（同一 ID の再発に対する上限）と「hard cap」
  （ラウンド数の上限）を全ドキュメント共通の呼び分けとして使う。
- **エラー処理方針**: 本フィーチャーは新しいエラーコード体系を持たない。
  verify の失敗は `verify.status: failed` と `failed_items` としてのみ表現し、
  cap 到達を別 status や `deferred` に写像しない。

## Cross-task Design Decisions

### D1: cap の定義本文は SKILL.md「verify フェーズ」節に置く（NFR1）

現行の cap は SKILL.md・`batch-mode.md`・`workflow-schema.md` の 3 箇所に
ベタ書きされている。`batch-mode.md` の Non-packet gates 表は既に
`verify.failed` 行の Full detail を SKILL.md「verify フェーズ」節に委ねて
いるため、定義元をそこに一本化するのが現行の参照方向と一致する。

- 定義本文（系譜 cap の数え方・値、hard cap の値、両者が独立評価であること、
  cap 到達時の帰結）は SKILL.md「verify フェーズ」節にのみ書く。
- `batch-mode.md` の `verify.failed` 行は「系譜 cap と hard cap による自動
  rework、cap 到達時は `failed` のまま retrospect へ進む」旨と Full detail の
  参照だけを書き、**数値を書かない**。
- `workflow-schema.md` の `batch` ブロックは**構造**（キーとその意味）だけを
  書き、cap の値と判定規則を書かない。

影響タスク: task0001（定義と参照の両側を同一タスクで揃える）、task0002 /
task0003（参照側として数値を書かない）。

### D2: テスト隔離規律 — 新規テストは自タスクが変更するファイルにのみアサートする

全タスクは互いに独立した worktree で並列に実装される。あるタスクの worktree
には他タスクの編集が存在しない。したがって「他タスクが書く予定の文言」を
アサートするテストは、そのタスクの worktree で必ず失敗する。

- 新規テストがアサートしてよい対象は、そのタスクの `files` に挙がっている
  ファイルに限る。
- 例外は「変更されていないこと」を確かめる回帰ガード。自タスクが変更しない
  ファイルに対しては、**他のどのタスクも変更しない**ことが本計画上明らかな
  箇所に限り、現状の文言が残っていることをアサートしてよい（例: task0004 が
  `review-phase.md` の Phase R5 節に対して行う FR10 の回帰ガード）。
- 複数ファイルにまたがる検査（NFR1 の SSOT 単一性など）は、対象ファイルを
  すべて同一タスクが所有している場合にのみ書ける。本計画では cap 定義の
  3 ファイルを task0001 に集約することでこれを成立させている。

（根拠: 既存の `tests/test_batch_quiet_output_skill_wiring.py` が同じ理由から
「他タスクの担当ファイルが定義を持つことはアサートしない」と明記している。）

### D3: SKILL.md のセクション所有権

SKILL.md は 4 タスクが編集する。衝突面を減らすため、節ごとに編集者を 1 つに
固定する。

| SKILL.md の節 | 編集タスク | 変更内容の要旨 |
|---|---|---|
| 「### ターンを終わらせていい唯一の条件」の条件 1 / 条件 3 | task0002 | cap 到達による verify の `failed` を停止理由から外す独立条項への参照 |
| 「## Step B: 自走ループ」の停止条件 3 との優先関係ブロック以降 | task0002 | batch 専用の独立条項の新設 |
| 「### verify フェーズ」 | task0001 | cap 判定の系譜化、cap 到達時に停止しない旨、cap 定義本文 |
| 「### retrospect フェーズ」 | task0003 | `signals.verification_failures` の構造確定と `follow_up_drafts` の新設 |
| 「## Step C: 完了処理」の見出し行 | task0002 | 実行条件の変更（見出し文字列そのものの書き換え） |
| 「## Step C: 完了処理」の手順 1（完了方式の決定） | task0004 | interactive の推奨デフォルトの条件付き切り替え |
| 「## バッチ終端行」 | task0002 | cap 到達走行の終端状態の明記 |

表に無い節は本フィーチャーでは変更しない。同一ファイルの別節同士の編集は
衝突しても実装者の parent-side-adoption 手順で解消できる範囲に収まる。

### D4: Step B 停止条件との整合は「独立条項の新設」で行う（FR7 / 仮定 a-fr7）

既存の自動再エントリ carve-out（「フェーズプロトコルが自動再エントリのために
設定した `needs_update`」限定、対象遷移を「厳密に次の 2 つ」と網羅的に宣言）
には一切触れない。代わりに batch 専用の独立条項を新設し、次の 2 つを対象と
する:

- 停止条件 3（ある step の status が `failed` なら停止）に対する例外
- 停止条件 1（全 step が `completed` でないとターンを終えられない）に対する例外

いずれも「batch モードで、verify が系譜 cap / hard cap 到達により `failed` で
ある場合」に限る。`verify.status` は `failed` のままで、別 status も
`deferred` も導入しない。

この決定は既存テスト `TestStopCondition3AutomaticReentryCarveOut` の網羅性
宣言を無傷に保つことを前提条件とする（同テストは carve-out 節を切り出して
検査するため、新条項は同節の外側に置く）。

影響タスク: task0002。

### D5: cap 到達走行の終端状態は既存コードを再利用する（FR11 / 仮定 a-fr11）

`references/batch-terminal-line.md` は stop point `verify-rework-cap` を
reason code `verify_rework_cap_reached` に既に束ねており、その stop point の
所有ドキュメントは SKILL.md である。したがって終端行 SSOT を変更せずに、
SKILL.md 側で「cap 到達走行はどの終端状態として報告されるか」を明記できる
（NFR5 の変更範囲を維持できる）。

- `state=stopped` / `step=verify` / `reason=verify_rework_cap_reached`。
- `detail` に「Step C まで到達し、worktree 掃除と終了報告は完了した」旨を
  含める。
- 終端行は 1 走行につき 1 行。cap 到達走行では Step C の完了報告の直後に
  出力する（通常完了の `state=completed` は使わない）。
- `references/batch-terminal-line.md` は変更しない。

影響タスク: task0002。

### D6: `follow_up_drafts` の生成母集団（FR5 / 仮定 a-fr5）

母集団は「cap 到達時点で未解決の `failed_items` 全件」。系譜 cap に触れた ID
かどうかで絞り込まない。絞り込むと「毎ラウンド新規 ID が現れて hard cap で
止まった」走行で draft が 0 件になり、受け入れ条件が満たせない分岐が生じる。
深刻度や優先度による絞り込みは retrospect 側の判断に委ねる。

影響タスク: task0003。

### D7: 旧 `verify_rework_count` を持つ既存 workflow.yaml の扱い

`batch` ブロックは走行ごとにオーケストレーターが読む揮発的なカウンタであり、
過去の feature の workflow.yaml には旧キー `verify_rework_count` が残る。
移行処理は行わない。新構造のキーが存在しない場合は「未計上」（ラウンド数 0、
ID ごとの出現回数は空）として扱う旨を `workflow-schema.md` の `batch` ブロック
の説明に 1 行で書き、旧キーは無視する。

影響タスク: task0001。

### D8: 既存テストモジュールのシンボル所有権

既存の 3 モジュールが本フィーチャーの変更で壊れる pin を持つ。ファイル単位で
はなくシンボル単位で所有を割り当てる。

| 既存モジュール | 所有タスク | 触ってよい範囲 |
|---|---|---|
| `tests/test_develop_skill_rewiring.py` | task0001 | 旧 cap 文言を pin しているテストのみ。carve-out 検査クラスには触れない |
| `tests/test_batch_quiet_output_skill_wiring.py` | task0001 | 旧 cap 文言の非改変ガードのみ |
| `tests/test_batch_quiet_output_skill_wiring.py` | task0002 | Step C 見出し定数のみ |
| `tests/test_batch_stop_contract_skill_wiring.py` | task0002 | Step C 見出し定数のみ |

`tests/test_batch_quiet_output_skill_wiring.py` は task0001 と task0002 の
双方が触れる。触る箇所（旧 cap 文言のガード / 見出し定数）が離れているため、
衝突しても parent-side-adoption で解消できる。それ以外のクラス・定数には
どちらのタスクも触れない。

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Step C 見出しの変更が、見出しをセクション境界に使う既存テスト 2 モジュールを一斉に壊す | high | high | 見出し文字列を task0002 の単独所有にし、SKILL.md と 2 つのテスト定数の同時更新を同タスクの受け入れ条件にする（D3 / D8） |
| FR7 の新条項を carve-out 節の内側に書いてしまい、既存の網羅性宣言テストを壊す | medium | high | 新条項は carve-out 節の外側に置くことを task0002 の受け入れ条件に含め、既存テストを無改変で通すことを検証項目にする（D4） |
| 他タスクの成果を前提にしたアサーションを書き、実装者の worktree でテストが落ちる | medium | medium | D2 のテスト隔離規律を全タスク計画に明記し、cap 定義の 3 ファイルを 1 タスクに集約する |
| cap の値が複数ドキュメントに再びベタ書きされ、NFR1 が崩れる | medium | medium | 定義元を D1 で固定し、非定義元での数値ベタ書きを検出するテストを task0001 が持つ |
| `follow_up_drafts` の `title` / `body` が未信頼入力の扱いを外れて外部サービスへ命令として渡る | low | high | NFR6 の引き継ぎを task0003 の受け入れ条件に含め、`worker-envelope.md` の Untrusted-Input Handling を参照させる |
| 変更範囲が NFR5 の 6 種類（SKILL.md / batch-mode.md / workflow-schema.md / マニフェスト 2 件 / tests/）を超える | medium | medium | 各タスクの `files` を NFR5 の範囲内に限定し、範囲外ファイルの必要性が判明したら計画逸脱として報告させる |
| プラグイン version の bump 漏れでインストール済みキャッシュが更新されない | low | high | task0005 を独立タスクにし、2 マニフェストの一致を検証する |

## Open Questions

- [ ] cap 到達走行で `--once` を併用した場合、終端行を出すターンが Step C の
      ターンになる。`references/batch-terminal-line.md` の `step` フィールドの
      一般規則は「そのターンで実行した step」を指すため、`step=verify` との
      整合を SKILL.md 側でどう言い切るか（D5 は「1 走行につき 1 行、cap 到達
      走行では `step=verify`」と決めたが、`--once` 併用時の記述粒度は
      task0002 の実装判断に委ねている）。
- [ ] cap 到達で `verify` が `failed` のまま `retrospect` へ進む走行は、
      `--once` のフェーズ境界表の「通常の step（status が `completed`）」行に
      当てはまらない。境界表を変更するかどうかは本フィーチャーの要件に無く、
      変更しない前提で計画している。
- [ ] 旧キー `verify_rework_count` を持つ既存 workflow.yaml の扱い（D7）は
      SPEC の要件に明示が無く、planner の設計判断として置いた。
