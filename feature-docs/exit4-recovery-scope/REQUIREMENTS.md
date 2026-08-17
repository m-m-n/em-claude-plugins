---
title: "exit4-recovery-scope"
created_date: 2026-08-17
status: draft
---

# exit4-recovery-scope - 要件定義書

## 1. 概要

### 1.1 背景

implement フェーズにおける `commit-docs.sh` exit 4（stale worktree）の
bounded recovery の適用範囲について、3 つの SSOT の記述が食い違っている。

- `em-workflow/references/implement-phase.md` は、bounded recovery の適用範囲を
  閉じた 3 サイト列挙（Step I.1 のベースラインコミット、Step I.2.b の wake-phase
  コミット、Step I.2.c の rejected-path terminal status コミット）に限定し、
  それを「このフェーズで exit 4 が起こり得る 3 つの `commit-docs.sh` 呼び出し箇所」
  と主張している。
- `em-workflow/scripts/commit-docs.sh` の RECOVERY CONTRACT ヘッダと
  `em-workflow/skills/develop/SKILL.md` の exit-4 段落は、全呼び出し箇所を対象と
  する全称記述に、ちょうど 1 つの除外（Step I.2.c の route-back コミット）を
  加えた形で記述している。

この不一致により、Step I.2.a の launch/refill ステータスコミットと Step I.3 の
完了コミットが、bounded recovery に拘束されるとも除外されるとも書かれていない
状態になっている。並行する `merge-task.sh` のブランチ ref 前進（exit 4）が最も
起こりやすい refill ウィンドウが、まさに未定義のまま残されている。

### 1.2 目的

implement フェーズの exit-4 recovery contract を、単一かつ曖昧さのないものに
戻す。フェーズ内の **すべて** の `commit-docs.sh` 呼び出し箇所について、
orchestrator が exit 4 でどう振る舞うかが定義された状態にする。

### 1.3 スコープ

- 対象: `em-workflow/references/implement-phase.md` の
  `## Branch & Worktree Model (READ FIRST)` セクション内の
  `**exit-4 recovery**` 箇条書きの文面。
- 対象: `tests/test_implement_routeback_gate.py` への assertion 追加。
- 対象: バージョン bump（`em-workflow/.claude-plugin/plugin.json` および
  `.claude-plugin/marketplace.json`）。
- 対象外: `commit-docs.sh` と `develop/SKILL.md` の編集（両者は既に
  「全称 + 1 除外」の形になっているため、変更不要 / 前提 A6）。
- 対象外: Step I.2.a / Step I.3 に明示的な `commit-docs.sh` 呼び出し行を
  追記すること（前提 A3）。

## 2. ビジネス要件

### 2.1 ビジネス目標

implement フェーズの exit-4 recovery contract を、単一かつ曖昧さのないものとして
復元し、orchestrator の `commit-docs.sh` exit 4 時の振る舞いが、そのフェーズの
**すべて** のコミット箇所について定義されている状態にする。

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow orchestrator（実行主体） | implement フェーズを実行し、`commit-docs.sh` の exit 4 に対して recovery を行う主体。プロトコル文書の記述がそのまま振る舞いを決める |
| プロトコル文書の読者（開発者） | 3 つの SSOT を読んで、どの呼び出し箇所が bounded recovery に拘束されるかを判断する |

### 2.3 期待される効果

- Step I.2.a の launch/refill ステータスコミットと Step I.3 の完了コミットが、
  bounded recovery に拘束される側として明示される。
- 並行する `merge-task.sh` の ref 前進が最も起こりやすい refill ウィンドウで、
  exit 4 時の振る舞いが未定義でなくなる。
- 3 つの SSOT が、拘束される箇所と除外される 1 箇所について同一のことを述べる。
- 新しい呼び出し箇所が追加されたときに、再び列挙が陳腐化しなくなる。

## 3. ユースケース

### 3.1 ユースケース一覧

| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | Step I.2.a の refill コミットで exit 4 に遭遇した際の recovery 判断 | em-workflow orchestrator | 高 |
| UC02 | 3 つの SSOT を読んで carve-out を確認する | プロトコル文書の読者（開発者） | 中 |

### 3.2 ユースケース詳細

#### UC01: Step I.2.a の refill コミットで exit 4 に遭遇した際の recovery 判断

**アクター**: em-workflow orchestrator

**事前条件**:
- implement フェーズが進行中で、Step I.2.a の launch/refill 時点にある。
- `tasks.{T}.status = in_progress` / `tasks.{T}.branch` の書き込みに続く
  `commit-docs.sh` コミットが行われようとしている。

**基本フロー**:
1. orchestrator が Step I.2.a のステータス書き込みを行う。
2. NFR2 の write-then-commit ルールにより `commit-docs.sh` を呼ぶ。
3. 並行する `merge-task.sh` が ref を前進させていたため exit 4 が返る。
4. orchestrator は `## Branch & Worktree Model (READ FIRST)` の
   exit-4 recovery 箇条書きを参照し、この呼び出し箇所が bounded recovery に
   拘束されると判断する。
5. bounded recovery を実行する（worktree の再 refresh、tip の再取得、同一の
   state transition の再適用、`commit-docs.sh` の 1 回リトライ）。

**代替フロー**:
- 2 回目の exit 4 が返った場合: 呼び出し箇所と対象タスクを報告してフェーズを
  停止する（無制限にループしない）。

**事後条件**:
- Step I.2.a のコミット箇所における exit 4 の扱いが、プロトコル文書上で
  定義された振る舞いに従っている。

#### UC02: 3 つの SSOT を読んで carve-out を確認する

**アクター**: プロトコル文書の読者（開発者）

**事前条件**:
- `implement-phase.md`、`commit-docs.sh` の RECOVERY CONTRACT ヘッダ、
  `develop/SKILL.md` の exit-4 段落が参照可能である。

**基本フロー**:
1. 読者が 3 つの文書の exit-4 に関する記述を読む。
2. どの呼び出し箇所が bounded recovery に拘束されるかを判断する。
3. 除外される箇所が Step I.2.c の route-back コミットのみであることを確認する。

**事後条件**:
- 3 文書のいずれを読んでも、拘束される箇所と除外される 1 箇所について
  同じ結論に到達する。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 | ステータス |
|----|--------|------|--------|-----------|
| FR1 | exit-4 recovery スコープを全称量化に戻す | bounded recovery の適用範囲を、implement フェーズの全 `commit-docs.sh` 呼び出し箇所に対する全称記述にする | 高 | resolved |
| FR2 | I.2.a と I.3 のコミットを拘束側に明示 | 例示列挙に Step I.2.a の launch 時書き込みと Step I.3 の完了書き込みを加える | 高 | resolved |
| FR3 | carve-out は 1 つのまま不変 | 唯一の carve-out は Step I.2.c の route-back コミットのままとする | 高 | resolved |
| FR4 | 3 SSOT の carve-out 記述の一致 | 3 文書が拘束範囲と唯一の除外について同一のことを述べる | 高 | resolved |
| FR5 | 既存の pin 済み文字列の保持 | `tests/test_implement_routeback_gate.py` が現在固定している文字列すべてを満たし続ける | 高 | resolved |
| FR6 | バージョン bump の同期 | `plugin.json` と `marketplace.json` の両方を `0.1.42` から `0.1.43` へ上げる | 中 | resolved |

### 4.2 機能詳細

#### FR1: exit-4 recovery スコープを全称量化に戻す

**説明**:
implement-phase.md の `## Branch & Worktree Model (READ FIRST)` セクション内の
`**exit-4 recovery**` 箇条書きが、bounded recovery の適用範囲を implement
フェーズの **すべて** の `commit-docs.sh` 呼び出し箇所に対して全称的に定め、
除外はちょうど 1 つ、同じ箇条書き内で名指しされる形にする。現在 43-46 行目に
ある閉じた列挙の言い回し（"applies to Step I.1's baseline commit, Step I.2.b's
wake-phase commit and Step I.2.c's rejected-path terminal status commit — the
three `commit-docs.sh` call sites in this phase where exit 4 can occur"）は、
網羅性を主張しなくなる。

**入力**:
- `em-workflow/references/implement-phase.md`: Markdown 文書 - 変更前の
  exit-4 recovery 箇条書きを含む。

**出力**:
- `em-workflow/references/implement-phase.md`: Markdown 文書 - 全称スコープに
  書き換えられた exit-4 recovery 箇条書きを含む。

**ビジネスルール**:
- 適用範囲は全称量化子で表現する。
- 除外は同一箇条書き内で名指しされた 1 箇所のみとする。

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 列挙の再閉鎖 | 全称句の後にダッシュリストを残した結果、将来の読者がそのリストを網羅的と読む | リストが全称スコープ下の例示であることが文面から分かるようにする（EC1） |

#### FR2: I.2.a と I.3 のコミットを拘束側に明示

**説明**:
箇条書きの例示列挙に、Step I.2.a の launch 時の
`tasks.{T}.status = in_progress` / `tasks.{T}.branch` 書き込みと、Step I.3 の
`implement = completed` / `completed_at_commit` 書き込みを、現在名指しされている
3 箇所と並べて明示的に含める。列挙は全称スコープ下の例示として読まれ、新しい
呼び出し箇所が追加されたときに再び陳腐化し得る閉じた集合としては読まれない。

**ビジネスルール**:
- 列挙は例示（illustrative）であり、閉じた集合ではない。
- Step I.2.a と Step I.3 のコミットは、NFR2 の write-then-commit ルールが
  生み出すコミットとして名指しされる（前提 A3）。

#### FR3: carve-out は 1 つのまま不変

**説明**:
唯一の carve-out は Step I.2.c の **route-back** コミットのままである。既存の
文 "The single carve-out is Step I.2.c's **route-back** commit — distinct from
the rejected-path terminal status commit enumerated above, which IS bound by
this bounded recovery" と、それに続く unreachability proof の各文は残存する。

**ビジネスルール**:
- carve-out の数は 1 のまま増減しない。
- unreachability proof は "the orchestrator's own `commit-docs.sh` calls
  elsewhere in this phase" を対象に推論しており、拘束集合を広げた後も正しい。
  この proof を新たに列挙した箇所だけに狭めてはならない（EC2）。

#### FR4: 3 SSOT の carve-out 記述の一致

**説明**:
変更後、implement-phase.md、`commit-docs.sh` の RECOVERY CONTRACT ヘッダ、
`develop/SKILL.md` の exit-4 段落が、どの呼び出し箇所が拘束され、どの 1 箇所が
carve-out されるかについて同一のことを述べる。後者 2 つは既に「全称 + 1 除外」の
形で記述されているため、この要件を満たすためにいずれのファイルも編集する必要が
ない（前提 A6）。

**ビジネスルール**:
- AC3 は implement-phase.md の編集のみで到達する。

#### FR5: 既存の pin 済み文字列の保持

**説明**:
`tests/test_implement_routeback_gate.py` が現在固定している文字列すべてが
満たされ続ける。

**存在が必要な文字列**:
- "Step I.1's baseline commit"
- "Step I.2.b's wake-phase commit"
- "Step I.2.c's rejected-path terminal status commit"
- "The single carve-out is Step I.2.c's **route-back** commit"
- unreachability-chain の語句
- ref-advancing-paths の語句
- recovery 手順の各文（"retry `commit-docs.sh` once" / "second exit 4" /
  "stops the phase"）

**不在が必要な文字列**:
- OLD_EXIT4_ENUMERATION_TAIL（"Step I.2.b's wake-phase commit, and Step
  I.2.c's route-back commit"）
- OLD_EXIT4_MERGETASK_ONLY_PHRASE

**エラーケース**:

| エラー | 条件 | 対応 |
|--------|------|------|
| 旧列挙形の再導入 | 列挙を広げる際に、カンマ + and の厳密な語順を再び作ってしまう | OLD_EXIT4_ENUMERATION_TAIL の厳密な語順を作らない（EC4） |

#### FR6: バージョン bump の同期

**説明**:
`em-workflow/.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json`
の `em-workflow` エントリの双方を、同じ変更の中で `0.1.42` から `0.1.43` へ
上げる。

**ビジネスルール**:
- 2 箇所の値は一致させる（前提 A2）。

## 5. 非機能要件

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | ドキュメント / コメントのみの変更 | スクリプトの実行可能行は一切変更しない。変更対象は implement-phase.md の prose と 2 つのバージョンフィールドのみで、`commit-docs.sh` およびいずれの hook のランタイム挙動も変えない |
| NFR2 | 凍結ファイルに触れない | `em-workflow/references/workflow-patch.md` と `em-workflow/scripts/validate-worker-output.py` は凍結されており、この成果に到達するために変更しない |
| NFR3 | スイートグリーン、テスト喪失なし | `python3 -m unittest discover -s tests` が通る。テストの削除・改名による消失・skip を行わない。`test_implement_routeback_gate.py` のテストメソッド数を減らさない |
| NFR4 | 最小かつ限定されたファイル集合 | 想定ファイル集合: `em-workflow/references/implement-phase.md`、`tests/test_implement_routeback_gate.py`、`em-workflow/.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json` |
| NFR5 | SSOT 規律の維持 | Branch & Worktree Model の箇条書きが bounded recovery 手順の唯一の所有者であり続ける。他 2 文書は carve-out を引用するにとどまり、列挙の第二定義にならない。他所が所有するルール（NFR2 の write-then-commit ルール、広げられた I.2.c ゲート）は再掲せず、現状どおり引用のみとする |
| NFR6 | テストモジュールの慣習 | 新しい assertion はモジュール既存の規律に従う。内容 assertion は空白正規化済みのコピーに対して行い、新しい不在 assertion にはそれぞれ、その matcher が変更前の文面を検出することを示す regression proof を対にする（TestValidationDetectsRegressions に倣う） |

### 5.1 パフォーマンス要件

該当なし。NFR1 のとおり、実行可能行を変更しないドキュメントのみの変更であり、
ランタイム挙動は変わらない。

### 5.2 セキュリティ要件

該当なし。NFR1 のとおり、ランタイム挙動を変えない。

### 5.3 可用性要件

該当なし。NFR1 のとおり、ランタイム挙動を変えない。

### 5.4 保守性要件

- SSOT: NFR5 のとおり、Branch & Worktree Model の箇条書きが bounded recovery
  手順の唯一の所有者であり続ける。
- ドキュメント: 3 つの SSOT が carve-out について同一のことを述べる（FR4）。
- 陳腐化耐性: 列挙は全称スコープ下の例示であり、呼び出し箇所の追加で
  再び陳腐化しない（FR2）。

### 5.5 互換性要件

- テスト互換性: `tests/test_implement_routeback_gate.py` が現在固定している
  文字列すべてを満たし続ける（FR5 / NFR3）。

## 6. UI/UX要件

該当なし。UI 面は一切存在しない。変更はプロトコル文書の prose と 2 つの
バージョンフィールドであり、ユーザーに見えるインターフェース、スタイリング、
デザインシステムの関与はいずれも無い（design ステップは skip）。

## 7. データ要件

該当なし。データモデル、データ項目、データ保持期間のいずれも本変更の対象外。

## 8. 外部連携

該当なし。連携システムおよび API 仕様は本変更の対象外。

## 9. 制約条件

### 9.1 技術的制約

- スクリプトの実行可能行を変更しない（NFR1）。
- `em-workflow/references/workflow-patch.md` と
  `em-workflow/scripts/validate-worker-output.py` は凍結（NFR2）。
- Step I.2.a / Step I.3 に明示的な `commit-docs.sh` 呼び出し行を追記しない
  （前提 A3）。
- 編集は Branch & Worktree Model の箇条書き内に限定する。
  `test_batch_mode_paragraph_is_byte_identical` と
  `test_no_bare_git_commit_or_add_lines` はファイル全体 / I.2.c セクションを
  対象に動作するため、いずれも乱してはならない（EC3）。

### 9.2 ビジネス上の制約

- テストを削除・改名消失・skip させない（NFR3）。
- バージョンは 2 箇所同時に bump する（FR6 / 前提 A2）。

### 9.3 スケジュール制約

該当なし。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/implement-phase.md`
- `tests/test_implement_routeback_gate.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/exit4-recovery-scope/**`
- `test-docs/exit4-recovery-scope/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/exit4-recovery-scope/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 列挙の再閉鎖（EC1）: 全称句の後にダッシュリストを残すと、将来の読者がそのリストを網羅的と読み得る | 高 | リストが全称スコープ下の例示であることが文面から分かるようにする |
| unreachability proof の意図しない狭化（EC2） | 中 | proof は "the orchestrator's own `commit-docs.sh` calls elsewhere in this phase" を対象に推論しており、拘束集合を広げた後も正しい。新たに列挙した箇所だけに狭めない |
| 全体 / I.2.c セクションを対象とするテストの破壊（EC3） | 中 | 編集を Branch & Worktree Model の箇条書き内に限定し、`test_batch_mode_paragraph_is_byte_identical` と `test_no_bare_git_commit_or_add_lines` を乱さない |
| 旧列挙形の再導入（EC4） | 中 | OLD_EXIT4_ENUMERATION_TAIL（"Step I.2.b's wake-phase commit, and Step I.2.c's route-back commit"）の厳密な語順を作らない |
| 他のテストモジュールが箇条書きの文面を固定している可能性（前提 A4） | 中 | 目視ではなく全スイート実行で解消する |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| 未定義のままの refill ウィンドウ（Step I.2.a / Step I.3）で exit 4 が発生し、orchestrator の振る舞いが定まらない | 高 | 高 | FR1 / FR2 により当該箇所を拘束側に明示する |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: implement-phase.md の exit-4 recovery 箇条書きが、bounded recovery を
      implement フェーズの全 `commit-docs.sh` 呼び出し箇所に対して全称的に
      スコープし、carve-out がちょうど 1 箇所（Step I.2.c の route-back
      コミット）である。
- [ ] AC2: Step I.2.a の launch/refill ステータスコミットと Step I.3 の完了
      コミットが、その箇条書きの拘束側に明示的に名指しされている。
- [ ] AC3: implement-phase.md、`commit-docs.sh` の RECOVERY CONTRACT ヘッダ、
      `develop/SKILL.md` の exit-4 段落が、carve-out される箇所と、それ以外の
      全箇所が拘束されることについて同一のことを述べている。
- [ ] AC4: `tests/test_implement_routeback_gate.py` が現在固定している文字列
      すべてが満たされ続けている（存在が必要なものは FR5 に列挙、
      OLD_EXIT4_ENUMERATION_TAIL の不在が維持されている）。
- [ ] AC5: 削除された閉じた列挙の言い回しに対する不在 assertion と、変更前の
      文面に対する対の regression proof が存在する。
- [ ] AC6: `python3 -m unittest discover -s tests` が通る。
- [ ] AC7: `em-workflow/.claude-plugin/plugin.json` と
      `.claude-plugin/marketplace.json` の双方が `0.1.43` と読める。

### 11.2 KPI

該当なし。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] TS1: 箇条書きが全称スコープを述べていることを assert する（例:
      "every `commit-docs.sh` call site in this phase" の matcher）—
      `tests/test_implement_routeback_gate.py` の
      TestExit4EnumerationExcludesRouteBackCommit を拡張する。
- [ ] TS2: Step I.2.a の launch 時書き込みと Step I.3 の完了書き込みの双方が、
      箇条書きの拘束側列挙の内側に名指しされていることを assert する。
- [ ] TS3: 閉じた列挙の語句（"the three `commit-docs.sh` call sites in this
      phase where exit 4 can occur"）に対する不在 assertion と、
      TestValidationDetectsRegressions における matcher-flags-pre-change-wording
      の proof。
- [ ] TS4: TestExit4EnumerationExcludesRouteBackCommit と
      TestExit4CarveOutStatedInAllThreeSSOTs の既存 assertion が無変更で
      実行され、パスする。
- [ ] TS5: 全スイート実行: `python3 -m unittest discover -s tests` がグリーンで、
      箇条書きの文面を固定している他のモジュールを検出する。
- [ ] TS6: プラグイン不変条件 / バージョン整合性: 2 つのバージョンフィールドが
      `0.1.43` で一致する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| exit 4 | `commit-docs.sh` が返す stale worktree の終了コード。並行する `merge-task.sh` が、当該呼び出し箇所の最後の refresh とコミット試行の間にブランチ ref を前進させたことを意味する |
| bounded recovery | exit 4 に対する上限付き復旧手順（worktree の再 refresh、tip の再取得、同一の state transition の再適用、`commit-docs.sh` の 1 回リトライ。2 回目の exit 4 でフェーズ停止） |
| carve-out | bounded recovery の適用対象から除外される呼び出し箇所。本フィーチャーでは Step I.2.c の route-back コミットのみ |
| SSOT | Single Source of Truth。本フィーチャーでは implement-phase.md、`commit-docs.sh` の RECOVERY CONTRACT ヘッダ、`develop/SKILL.md` の exit-4 段落の 3 つ |
| refill ウィンドウ | Step I.2.a の launch/refill 時点。並行する `merge-task.sh` の ref 前進が最も起こりやすい |
| OLD_EXIT4_ENUMERATION_TAIL | テストが不在を要求する語句 "Step I.2.b's wake-phase commit, and Step I.2.c's route-back commit" |

## 14. 確認事項

### 14.1 確認済み事項

- [x] A1: PR #6 は `main` にマージ済みで、この統合ブランチはそのマージ済み
      `main` から分岐している（orchestrator 検証済み）。したがってタスク記述の
      「PR #6 が未マージならそのブランチ上で修正する」という代替案は適用されない。
- [x] A2: タスク記述はバージョン bump 対象として `plugin.json` のみを挙げているが、
      リポジトリは `em-workflow` の `version` の複製を
      `.claude-plugin/marketplace.json` にも保持している（現在 `0.1.42`）。
      両方を `0.1.43` へ同期して上げる。
- [x] A3: Step I.2.a と Step I.3 には implement-phase.md 上に文字列として明示的な
      `commit-docs.sh` 呼び出しが存在せず、これらのコミットは Branch & Worktree
      Model の NFR2 write-then-commit ルール経由でのみ存在する。これらのステップに
      明示的な呼び出し行を追記することはスコープ **外** であり、exit-4 箇条書きは
      それらを「そのルールが生み出すコミット」として名指しする。
- [x] A4: `tests/test_implement_routeback_gate.py` 以外のテストモジュールも
      exit-4 箇条書きの文面を固定している可能性がある。これは目視ではなく
      全スイート実行で解消する。
- [x] A5: アーキテクチャレビュアーが提示した置換テキストは出発点として扱い、
      バイト単位で一致させる要件とはしない。要件として求められるのは、全称量化子と
      ちょうど 1 つの名指しされた除外である。
- [x] A6: 両ファイルを読んで検証済み。`commit-docs.sh` は既に "binding on every
      caller EXCEPT ... today exactly one such site: ... Step I.2.c's route-back
      commit" と読め、`develop/SKILL.md` は既に "commit-docs.sh の全呼び出し箇所で
      共通 ... ただし ... Step I.2.c の route-back コミットは対象外" と読める。
      逸脱しているのは implement-phase.md のみであり、AC3 は implement-phase.md
      単独の編集で到達する。
- [x] design ステップ: skip。UI 面が一切存在しない。変更はプロトコル文書の prose と
      2 つのバージョンフィールドであり、ユーザーに見えるインターフェース、
      スタイリング、デザインシステムの関与はいずれも無い。

### 14.2 未確認・保留事項

なし。すべての要件は `status: resolved` である。

## 15. 参考資料

- `em-workflow/references/implement-phase.md`: 変更対象。exit-4 recovery
  箇条書きを含む Branch & Worktree Model セクションの所有者。
- `em-workflow/scripts/commit-docs.sh`: RECOVERY CONTRACT ヘッダ（既に
  「全称 + 1 除外」形）。
- `em-workflow/skills/develop/SKILL.md`: exit-4 段落（既に「全称 + 1 除外」形）。
- `tests/test_implement_routeback_gate.py`: 箇条書きの文面を固定するテスト
  モジュール。
- `em-workflow/.claude-plugin/plugin.json`: バージョンフィールド（`0.1.42` →
  `0.1.43`）。
- `.claude-plugin/marketplace.json`: `em-workflow` エントリのバージョン
  フィールド（`0.1.42` → `0.1.43`）。
