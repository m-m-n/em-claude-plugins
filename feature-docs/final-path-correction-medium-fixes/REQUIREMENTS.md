---
title: "final-path-correction-medium-fixes"
created_date: 2026-11-07
status: draft
---

# final-path-correction-medium-fixes - 要件定義書

## 1. 概要

### 1.1 背景

em-workflow の feature `subagent-report-write-block` のレビュー 1 回目で、最終パスの訂正まわりに medium の指摘が 7 件残った。medium は自動修正の対象外のため、どれも未修正のまま統合ブランチ `em-workflow/subagent-report-write-block/integration` にある。

| 分類 | stable_id | 内容 | 対応要件 |
|------|-----------|------|----------|
| セキュリティ | `73c084892e91326c` | 訂正入口のパッチが `entries` と `requirements_patch` を制限なく通す | FR1 |
| セキュリティ | `7dad93fa93454f47` | `new_path` に任意の文章を入れると条件 5 の比較を通る | FR2 |
| セキュリティ | `041b04abfc9d5b87` | 条件 5 が対象外タスクの計画を比較しない | FR3 |
| 動作 | `4409a460572aac40` | 未起動タスクにも違反があると、失敗タスクだけ訂正しても検証で却下され再開できない | FR4 |
| 動作 | `dc9fcac543811a2d` | 再計画パスでは条件 5 が本文の更新まで拒否し、違反を持つタスクを運べない | FR5 |
| 動作 | `a848a53b57fb0188` | 同じ旧ファイル名を別々の新名へ訂正すると正しい文書が拒否される | FR6 |
| 動作 | `25461d162dc42425` | 旧ファイル名だけの参照が残っても訂正済みとして通る | FR7 |

### 1.2 目的

- 最終パスの訂正はパス以外を何も変更せず、その検証はパス以外の変更を通さない。
- REPORT 系の名前を持つ計画の訂正が、複数タスクと再計画を含めて完走する。

### 1.3 スコープ

上記 7 件の指摘の修正（FR1〜FR7）、関連文書の更新（FR8）、訂正入口で新規作成された計画文書の却下（FR9）を対象とする。

## 2. ビジネス要件

### 2.1 ビジネス目標

- 最終パスの訂正はパス以外を何も変更せず、その検証はパス以外の変更を通さない。
- REPORT 系の名前を持つ計画の訂正が、複数タスクと再計画を含めて完走する。

### 2.2 対象ユーザー

該当なし。

### 2.3 期待される効果

該当なし。

## 3. ユースケース

該当なし。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 状態 |
|----|--------|------|
| FR1 | 訂正入口で `entries` と `requirements_patch` を制限する | ok |
| FR2 | `new_path` の形式を制限する | ok |
| FR3 | 訂正入口で対象外タスクの計画を比較する | ok |
| FR4 | 入口スクリプトの対象を検証側と揃える | ok |
| FR5 | 条件 5 の比較を再計画パスの外に限定する | ok |
| FR6 | 位置ベースで比較し、1 つの旧ファイル名を別々の新名へ対応させられるようにする | ok |
| FR7 | 残った旧ファイル名だけの参照を却下する | ok |
| FR8 | ルールを所有文書に記載する | ok |
| FR9 | 訂正入口で作成された計画文書を却下する | ok |

### 4.2 機能詳細

#### FR1: 訂正入口で `entries` と `requirements_patch` を制限する

**説明**: `--dry-run-apply` で、create-plan が completed かつ implement が failed のときに `tasks_patch.path_corrections` が空でないパッチを検証する場合に、次を適用する。指摘 `73c084892e91326c`。

**ビジネスルール**:

- (a) `requirements_patch` は、次のいずれかを満たす場合を除き `path-correction-requirements` で却下する。
    - null である、または要素を持たない。
    - すべての要素が workflow.yaml に既にある要件を指し、その `set` が `tasks_append` だけを持ち、値がすべて `tasks_patch.entries` 配下の ID である。
- (b) `tasks_patch.entries` の要素は、`files` が空でなく、かつすべてのファイルがベースコミットの通常ファイルで、そのテキストがパッチの訂正の旧パスまたは旧ファイル名だけの参照（出現の定義は FR7）を含む場合を除き、`path-correction-entries` で却下する。既存の読み取り上限内でテキストとして読めないファイルは却下する。
- (c) エントリの各ファイルと、その計画に描画する各 old_path・new_path は FR2 の形式検査を通らなければならない。通らなければ `path-correction-entries` とする。
- (d) エントリの計画は、検証側が描画する正規形のテキストとバイト単位で一致しなければならない。
    - 正規形は、そのタスクの ID と files、および旧パスまたは旧ファイル名だけの参照がベースコミットのそれらのファイルに現れる訂正から描画する。
    - 正規形の内容は、タイトル、Files セクション、該当する訂正 1 件につき旧参照を新参照へ置き換えることを述べた受け入れ条件 1 件であり、それ以外を含まない。
    - TASK.md の計画にも適用する。違反は `path-correction-entries` とする。
    - 正規形は検証スクリプト内の 1 つの関数とする。
- 再計画パスは制限しない。

#### FR2: `new_path` の形式を制限する

**説明**: 条件 4 は、次のいずれかを満たさない new_path も `path-correction-new-path` で却下する。指摘 `7dad93fa93454f47`。

**バリデーション**:

| 項目 | ルール |
|------|--------|
| 使用文字 | `[\w./-]+` に完全一致する（Unicode の単語構成文字、`.`、`/`、`-`） |
| 正規化 | 正規化した形（`/`.join(path_segments(new_path))）と等しい。`.`、`./`、`a//b.md`、`a/./b.md`、末尾の `/` は却下する |
| 先頭 | 最初のセグメントが `-` で始まらない |

`tasks_patch.entries` 配下の `files` の扱いは変えない。

#### FR3: 訂正入口で対象外タスクの計画を比較する

**説明**: 訂正入口で、条件 5 はパッチの対象でない workflow.yaml の全タスクの計画も、ステータスを問わず比較する。指摘 `041b04abfc9d5b87`。

**ビジネスルール**:

- ステータスまたは最後のジャーナルイベントが `merged` のタスクの計画は、ベースコミットとバイト単位で一致しなければならない。違反は文書名を示して `path-correction-content` とする。これは共有の計画にも適用し、対象タスクが必要とする置換より優先する。
- それ以外の対象外タスクの計画は位置ベース（FR6）で比較する。各出現箇所は旧テキストまたは許可された置換のどちらかとする。旧参照は残ってよく、それ以外は変更できない。
- 対象タスクと共有する計画は対象タスクの計画として比較し、旧参照を残せない。
- 比較できない計画は却下する。

#### FR4: 入口スクリプトの対象を検証側と揃える

**説明**: `scripts/report-name-entry.py` の判定を次のとおりとする。指摘 `4409a460572aac40`。

**ビジネスルール**:

- `none` の判定は引き続き失敗タスクで行う。失敗タスクのファイルに違反がなければ、他のタスクが何を持っていても `none` とする。
- 失敗タスクに違反があるときは、`violations` にステータスが `merged` でないすべてのタスクの違反をタスク順、ファイル順で列挙し、条件 1〜3 はその一覧全体で判定する。
- 出力キーは変えない。失敗ジャーナルイベントのないタスクの要素は `failed_journal_line: null` を持つ。

#### FR5: 条件 5 の比較を再計画パスの外に限定する

**説明**: 再計画パス（create-plan が needs_update、または SPEC 変更の再入場で pending）では、条件 5 のベースと現在の比較を実行しない。指摘 `dc9fcac543811a2d`。

**ビジネスルール**:

- 再計画パスの条件 5 は、現在の IMPLEMENTATION.md、VERIFICATION.md、対象タスクの計画に旧パスも旧ファイル名だけの参照もないことだけを求める。違反は `path-correction-content` とする。現在存在しない文書はエラーにしない。
- 条件 1〜4 と計画の Files セクションの一致確認は残す。
- VERIFICATION.md のシナリオ ID 走査の省略は訂正入口にだけ適用する。再計画パスの訂正パッチ、または workflow.yaml なしで検証する訂正パッチでは VERIFICATION.md を走査する。

#### FR6: 位置ベースで比較し、1 つの旧ファイル名を別々の新名へ対応させられるようにする

**説明**: 条件 5 は両側を 1 つのテキストへ正規化しない。指摘 `a848a53b57fb0188`。

**ビジネスルール**:

- ベース版で旧パスと旧ファイル名だけの参照の重複しない出現箇所を、長い一致を優先して確定する。現在版が異なってよいのはその出現箇所だけとする。
- それ以外のテキストは同一でなければならない。置換値はリテラルとして扱い、再走査しない。したがって出現箇所の外で候補名同士を等しく扱うことはない。a/REPORT.md を a/enabled へ、b/REPORT.md を b/disabled へ訂正するとき、`Authentication is enabled` を `Authentication is disabled` に変える変更は却下する。
- 旧パスの出現箇所に許す置換は、その訂正自身の新パスだけとする。
- 旧ファイル名だけの参照に許す置換は次のとおりとする。
    - 対象タスクの計画では、その計画を使うタスクの訂正のうちその旧ファイル名を持つものの新ファイル名。該当がなければパッチの全訂正の新ファイル名。
    - 複数の対象タスクが使う計画では、候補はそれらのタスクの訂正の和集合とし、計画の Files セクションはそれらのタスクの files の和集合と照合する。
- 例: a/REPORT.md → a/one.md と b/REPORT.md → b/two.md を同時に訂正するとき、ベース `Write a/REPORT.md. REPORT.md must exist.` と現在 `Write a/one.md. one.md must exist.` は通る。a/one.md へ訂正するタスクの計画で、その旧ファイル名だけの参照を `two.md` にすると却下する。

#### FR7: 残った旧ファイル名だけの参照を却下する

**説明**: 条件 5 は、現在の IMPLEMENTATION.md、VERIFICATION.md、対象タスクの計画に旧ファイル名だけの出現（曖昧な名前を含む）があれば `path-correction-content` で却下する。指摘 `25461d162dc42425`。

**ビジネスルール**:

- 旧ファイル名だけの出現とは、大文字小文字を区別したリテラルの旧ファイル名で、次の条件をすべて満たすものとする。
    - 直前が ASCII の英字、数字、`_`、`-`、`.`、`/`、`\` のいずれでもない。
    - 直後が ASCII の英字、数字、`_`、`-`、`/`、`\` のいずれでもない。
    - 直後が `.` と、英字、数字、`_`、`-` のいずれかの並びでもない。
- 比較でも、旧ファイル名はこの出現の位置でだけ出現箇所として扱う。`existing/REPORT.md`、`PREREPORT.md`、`REPORT.md.bak` は置換も指摘もせず、これらを書き換えると比較に失敗する。
- 1 セグメントの旧パスは旧ファイル名だけの参照として照合する。
- 複数セグメントの旧パスも同じ境界ルールで出現箇所とする。ただし直前の `./` は出現として数える。`existing/a/REPORT.md` と `a/release-REPORT.md` は出現箇所ではなく、変更できない。
- 残存の確認には部分文字列検索ではなく、これらの出現を使う。

#### FR8: ルールを所有文書に記載する

**説明**: 次の文書を更新する。

**ビジネスルール**:

- `references/workflow-patch.md` の `## Final-path correction` に FR1〜FR3、FR5〜FR7、FR9 を記載する。FR1 の制限と 2 つのエラーコードは 5 つの番号付き条件の外に記載する。
- `agents/implementation-planner.md` の `## Final-path correction` に次を記載する。
    - new_path の形式
    - 対象外の未マージ計画では参照の置換だけができ、マージ済みタスクの計画は編集しないこと
    - 新規タスクの計画の正規形
    - 共有の旧ファイル名だけの参照をどの新名で置き換えるか
    - 訂正のディスパッチで `entries` と `requirements_patch` が持ってよい内容
    - 再計画パスでは本文を変更でき、旧パスも旧ファイル名だけの参照も残してはならないこと
- `references/phases/create-plan-phase.md` の訂正コードを列挙している箇所に 2 つの新コードを加える。
- `scripts/report-name-entry.py` と影響を受ける検証関数の docstring を FR4〜FR7 に合わせる。

#### FR9: 訂正入口で作成された計画文書を却下する

**説明**: 訂正入口で、ベースコミットにエントリがなく現在存在する IMPLEMENTATION.md、VERIFICATION.md、または workflow.yaml のタスクの計画を `path-correction-content` で却下する。

**ビジネスルール**:

- 唯一の例外は `entries` 配下の新規タスクの計画で、そのパスがそれらの文書のいずれでもなく、パスの正規化（`./` と連続する区切りの除去）後にもいずれとも衝突しない場合とする。
- あるパスが両方に該当するときは、既存文書の制約を優先する。

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。

### 5.2 セキュリティ要件

- NFR2 フェイルクローズ: 読めない、または比較できない文書やファイルは却下とし、通過させない。入力の欠落は引き続き実行エラー（exit 2）とする。入口スクリプトの終了コードは変えない。
- NFR3 リテラルなパス: パスはリテラルのテキストのまま扱う。ベースコミットの読み取りには `base_tree_entry` と `_read_base_document` を使い、シェルと git の pathspec を使わない。

### 5.3 可用性要件

該当なし。

### 5.4 保守性要件

該当なし。

### 5.5 互換性要件

- NFR1 訂正以外の挙動を変えない: `tasks_patch.path_corrections` を持たないパッチは、通常の再計画の `entries` と `requirements_patch` を含め、すべての状態でこれまでどおり検証する。
- NFR4 新しいゲートを追加しない: 新しい gate_id、ユーザーへの質問、workflow.yaml のフィールドを追加しない。`report-name-entry.py` の出力キーは変えない。

## 6. UI/UX要件

該当なし。

## 7. データ要件

該当なし。

## 8. 外部連携

該当なし。

## 9. 制約条件

### 9.1 技術的制約

NFR3 のとおり。

### 9.2 ビジネス上の制約

該当なし。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/final-path-correction-medium-fixes/**`
- `test-docs/final-path-correction-medium-fixes/**`

`feature-docs/final-path-correction-medium-fixes/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/final-path-correction-medium-fixes/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/final-path-correction-medium-fixes/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/final-path-correction-medium-fixes/` ディレクトリを生成しないが、宣言された `test-docs/final-path-correction-medium-fixes/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし。

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC-1: 指摘 `73c084892e91326c` の round1 の再現（`.github/workflows/deploy.yml` を持つ task0003 のエントリと FR1 の set.status: excluded）が `path-correction-entries` と `path-correction-requirements` で却下される（FR1）。
- [ ] AC-2: files がベースの通常ファイルで旧パスまたは旧ファイル名だけの参照を持つ新規エントリは、その正規形の計画と、その ID の tasks_append の requirements_patch とともに訂正入口を通る。同じエントリの計画に行を 1 行でも足すと、TASK.md を含め却下される（FR1）。
- [ ] AC-3: round1 の new_path の文章と、TASK.md の計画に対する改行の形式が `path-correction-new-path` で却下される（FR2）。
- [ ] AC-4: 訂正入口で対象外の計画の受け入れ条件を編集すると、pending、failed、merged のタスクについて `path-correction-content` で却下される。旧参照の置換は未マージの計画では通り、ステータスまたは最後のジャーナルイベントが merged のタスクの計画では却下される。変更のない計画は通る（FR3）。
- [ ] AC-5: 失敗タスクと未起動タスクがそれぞれ新しい REPORT 系の名前を持つとき、入口スクリプトは両方を列挙した dispatch を返し、両方を訂正すると検証を通る（FR4）。
- [ ] AC-6: 違反のない失敗タスクと違反のある pending タスクが並ぶ場合、引き続き none を返す（FR4）。
- [ ] AC-7: path_corrections と 3 文書の本文更新を持つ再計画パッチが通る。同じパッチで旧パスまたは旧ファイル名だけの参照を残すと却下される。VERIFICATION.md のハイフンなしの ID は scenario-id-form として報告される（FR5、FR7）。
- [ ] AC-8: 訂正入口では比較が引き続き本文の変更を却下し、VERIFICATION.md は引き続き走査しない（FR5）。
- [ ] AC-9: 指摘 `a848a53b57fb0188` の a/REPORT.md と b/REPORT.md の例が文書と計画で通り、タスク自身の計画の誤った新名は却下され、`enabled` と `disabled` がどちらも候補名のとき出現箇所の外で `enabled` を `disabled` に変える変更は却下される（FR6）。
- [ ] AC-10: 文書に残った旧ファイル名だけの参照は却下され、existing/REPORT.md、PREREPORT.md、REPORT.md.bak を変更せず残した場合は通る（FR7）。
- [ ] AC-12: 訂正入口で新規作成された VERIFICATION.md は、エントリがそれを計画に指定している場合も含めて却下される。新規タスク自身の計画が空いているパスにあれば通る（FR9）。
- [ ] AC-13: 2 つの対象タスクが共有する計画が、両タスクの置換で通り、その Files セクションは両タスクの files の和集合と照合される（FR6）。
- [ ] AC-11: `python3 -m unittest discover -s tests` が通り、7 件の指摘それぞれの再発テストがあり、reference_impact のピン留めテストが更新されている（FR1〜FR8）。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

| ID | シナリオ | 期待結果 | 対象要件 |
|----|----------|----------|----------|
| TS-1 | 訂正入口で、無関係なファイルを持つ entries と requirements_patch の set.status: excluded を validate_worker_result の dry_run にかける | 2 つの新コードの両方で却下される | FR1 |
| TS-2 | requirements_patch の変種: tests_append、status、tests_replace、未登録の要件 ID、持ち越した ID の tasks_append | それぞれ `path-correction-requirements` で却下される | FR1 |
| TS-3 | エントリの files: 新規ファイル、ディレクトリ、参照のない通常ファイル、非 UTF-8 ファイル、空リスト、旧パスを参照する通常ファイル、旧ファイル名だけを参照する通常ファイル。正規形と異なる計画。名前に改行またはバッククォートを含むファイル | 正規形の計画を持つ 2 つの参照ケースだけが通る | FR1 |
| TS-4 | 再計画パスで同じ entries と requirements_patch を検証する | 新コードで却下されない | FR1、FR5 |
| TS-5 | スペース、改行、バッククォートを含む new_path、`:(top)README.md`、`-x.md`、`.`、`./`、`a//b.md`、`a/`、非 ASCII のディレクトリ | 非 ASCII のディレクトリ以外はすべて却下される | FR2 |
| TS-6 | pending、failed、ステータスが merged、ジャーナルが merged のそれぞれで、対象外の計画を編集および参照置換する。パスの置換だけの共有 TASK.md 計画。マージ済みタスクを含む共有計画 | 編集は却下される。置換は未マージでだけ通る。共有計画はマージ済みタスクが共有していなければ通る | FR3 |
| TS-7 | 入口スクリプトで、失敗タスクと未起動タスクが違反を持つ。マージ済みタスクが名前を持つ。最後のジャーナルイベントが merged の未起動タスク。名前がベースでディレクトリである未起動タスク | 両方が列挙され、未起動タスクの行は null。マージ済みタスクは列挙されない。最後の 2 つは blocked | FR4 |
| TS-8 | 2 つの対象を持つ入口スクリプトの出力を、訂正したパッチを通して検証する | `report-name-new-file` エラーが出ない | FR4 |
| TS-9 | path_corrections、本文更新、needs_update とルートバックの状態を持つ再計画 | 残存確認だけで通る。旧パスまたは旧ファイル名だけの参照が残ると却下される | FR5、FR7 |
| TS-10 | 訂正パッチのシナリオ ID 走査: 訂正入口、再計画パス、workflow なし | 訂正入口でだけ省略される | FR5 |
| TS-11 | 旧ファイル名を共有する 2 つの訂正: 共有文書、各対象の計画、どちらも持たないタスクの計画。出現箇所の外での候補名の入れ替え。`a/release-REPORT.md` の中の旧ファイル名。2 つの対象が共有する計画 | FR6 のとおり | FR6 |
| TS-12 | 旧ファイル名だけの参照の境界ケース: バッククォート、括弧、文末の句点、日本語テキストの直接隣接、`#anchor`、ディレクトリの接頭辞、名前の接頭辞、`.bak` の接尾辞、大文字小文字の違い、1 セグメントの旧パス。より長いパスの配下と `./` の後の複数セグメントの旧パス | FR7 のとおり | FR7 |
| TS-13 | 文書テストが workflow-patch.md、implementation-planner.md、create-plan-phase.md を読む | ルールと 2 つの新コードが記載されている | FR8 |
| TS-14 | 計画文書がベースにない訂正入口: VERIFICATION.md、IMPLEMENTATION.md、既存タスクの計画、VERIFICATION.md または `./VERIFICATION.md` を指定するエントリの計画、新規タスク自身の計画 | 最後のものだけが通る | FR9 |

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 訂正入口 | create-plan が completed かつ implement が failed のときに `tasks_patch.path_corrections` が空でないパッチを検証する経路 |
| 再計画パス | create-plan が needs_update、または SPEC 変更の再入場で pending の経路 |
| 旧ファイル名だけの参照 | FR7 の定義を満たす旧ファイル名の出現 |
| 正規形 | FR1 (d) で検証側が描画する新規タスクの計画のテキスト |

## 14. 確認事項

### 14.1 確認済み事項

該当なし。

### 14.2 未確認・保留事項

- [ ] A1: 再計画パスの条件 5 は残存確認だけを持つ。訂正と本文更新の 2 パスへの分割は採用しない。
- [ ] A2: 未マージの対象外の計画は旧参照を残してよい。置換は許可であり、必須ではない。
- [ ] A3: new_path では非 ASCII の単語構成文字を引き続き許可する。スペースと句読点を含まない文章はこの形式であれば通る。
- [ ] A4: エントリのファイルに、名前がテストファイルであることやマージ済みタスクに属することは求めない。ベースで参照を持つことを確認する。
- [ ] A5: `entries` 配下の新規タスクの計画の本文は、訂正入口では生成された正規形のテキストとし、再計画パスでは自由とする。
- [ ] A6: `violations` に加わる未起動タスクは既に `pending` なので、Step A.6 の復元に文面の変更は要らない。`failed_journal_line` が null であれば、その routeback の記録はそのままとする。
- [ ] A7: `./REPORT.md` は、1 セグメントの旧パスについては旧ファイル名だけの出現ではなくパス修飾された参照として数える。複数セグメントの旧パスでは直前の `./` を出現として数える。

## 15. 参考資料

- round 1 のレビュー: `feature-docs/subagent-report-write-block/reviews/round1.yaml`（統合ブランチ `em-workflow/subagent-report-write-block/integration`）
- `em-workflow/references/workflow-patch.md`
- `em-workflow/scripts/validate-worker-output.py`
- `em-workflow/scripts/report-name-entry.py`
- `tests/test_final_path_correction.py`
