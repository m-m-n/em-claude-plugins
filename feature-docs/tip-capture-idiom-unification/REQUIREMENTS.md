---
title: "tip-capture-idiom-unification"
created_date: 2026-08-23
status: draft
---

# tip-capture-idiom-unification - 要件定義書

## 1. 概要

### 1.1 背景

implement フェーズの SSOT である `em-workflow/references/implement-phase.md` は、
tip を伴う `commit-docs.sh` 呼び出しについて、7 箇所のうち 2 箇所では 1 つのイディオムを
規定し、残り 5 箇所では、同じ文書に新たに追加された散文が「危険」と断じているイディオムを
規定している。同一の操作を、同じ文書が規定しつつ非難している状態にある。

### 1.2 目的

7 箇所すべての `commit-docs.sh` 呼び出しサイトを、単一の安全なイディオムに統一する。
併せて、各サイト本体の初回手順が Branch & Worktree Model の exit-4 リカバリ項と同じ順序を
述べるようにし、「初回は旧イディオム、リトライは新イディオム」という不整合を取り除く。
さらに、この統一を機械的に検査可能にして、後続の編集でイディオムが黙って元に戻らないように
する。

### 1.3 スコープ

対象は、プロトコル散文（`implement-phase.md`）、シェルスクリプトのコメント
（`em-workflow/scripts/commit-docs.sh`）、既存テスト 1 モジュールの 3 アサーション、
新規テストモジュール 1 本、バージョンマニフェスト 2 ファイルである。
実行可能コードの挙動変更は含まない。

## 2. ビジネス要件

### 2.1 ビジネス目標

| ID | 目標 |
|----|------|
| OBJ1 | implement フェーズの SSOT である `implement-phase.md` において、7 箇所の `commit-docs.sh` 呼び出しサイトを単一の安全なイディオムに統一し、同じ操作を規定しつつ非難する状態を解消する。 |
| OBJ2 | 各呼び出しサイトの初回手順が Branch & Worktree Model の exit-4 リカバリ項と同じ順序を述べるようにし、「初回は旧イディオム、リトライは新イディオム」という不整合を除去する。 |
| OBJ3 | 統一を機械的に検査可能にし、後続の編集でイディオムが黙って元に戻らないようにして、「呼び出しサイト群が単一の一貫した機構として読める」という既存の非機能要件を満たす。 |

### 2.2 対象ユーザー

| ユーザータイプ | 説明 |
|----------------|------|
| implement フェーズの手順を実行する主体 | `implement-phase.md` の記述に従って `commit-docs.sh` を呼び出す。 |
| `em-workflow` プラグインの保守者 | `implement-phase.md` および `commit-docs.sh` を編集し、イディオムの一貫性を維持する。 |

### 2.3 期待される効果

- `implement-phase.md` 内に、tip を伴う `commit-docs.sh` 呼び出しに対して旧イディオム
  （refresh → `rev-parse HEAD`）を規定する箇所がなくなる。
- 初回実行と exit-4 リトライが同一の手順になる。
- イディオムの逸脱がテストスイートで検出される。

## 3. ユースケース

### 3.1 ユースケース一覧

該当なし。本フィーチャーはプロトコル文書・シェルコメント・テスト・バージョンマニフェストの
変更のみであり、対話的なユーザー操作フローを持たない。

### 3.2 ユースケース詳細

該当なし（3.1 と同じ理由）。

## 4. 機能要件

### 4.1 機能一覧

| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 正準 tip 取得イディオム | tip を伴う全呼び出しサイトの単一イディオムを定義する。 | — |
| FR2 | 旧イディオム 5 サイトの変換 | `refresh → rev-parse HEAD` の 5 サイトを FR1 のイディオムへ書き換える。 | — |
| FR3 | PR 17 の 2 サイトは参照形として不変 | 既に FR1 のイディオムを持つ 2 サイトの内容は変更しない。 | — |
| FR4 | 対象サイト集合 | 対象は tip を伴う `commit-docs.sh` 呼び出し 7 箇所すべて。 | — |
| FR5 | Step I.1 の扱い（capture-then-refresh） | Step I.1 は capture に加えて refresh も追加し、完全なイディオムを採用する。 | — |
| FR6 | Step I.2.b の capture 行配置（凍結された順序ピンの維持） | 既存の順序ピンを触らずに通るよう capture 行を配置する。 | — |
| FR7 | 凍結モジュールのアサーション修正 | `tests/test_implement_routeback_gate.py` の 3 アサーションのみを新イディオムへ再ピンする。 | — |
| FR8 | `commit-docs.sh` の散文整合（2 ブロック） | 引数説明と RECOVERY CONTRACT の 2 ブロックを新イディオムに合わせる。 | — |
| FR9 | イディオム一貫性テスト | 7 サイトの一貫性を検出する新規テストモジュールを追加する。 | — |
| FR10 | プラグインのバージョン bump | `plugin.json` と `marketplace.json` の `version` を同一値へ上げる。 | — |

優先度は要件分析で付与されていないため未設定（—）とする。

### 4.2 機能詳細

#### FR1: 正準 tip 取得イディオム

**説明**: tip を伴うすべての `commit-docs.sh` 呼び出しサイトにおける単一のイディオムは次のとおり。

- (a) tip を **ブランチ ref** から取得する ―
  `<VAR>=$(git -C <integration worktree> rev-parse em-workflow/{feature}/integration)`
- (b) integration worktree の refresh は
  `git -C <integration worktree> reset --hard em-workflow/{feature}/integration` で行い、
  その対象は常に **ブランチ名** であって、取得済み SHA ではない。
- (c) capture は refresh に **先行する**。

**ビジネスルール**:
- Branch & Worktree Model の exit-4 リカバリ項（`implement-phase.md` 43-82 行）は
  既にこの順序を述べており、規範的参照である。この項自体は変更しない。

**状態**: resolved

#### FR2: 旧イディオム 5 サイトの変換

**説明**: `refresh → rev-parse HEAD` の 5 サイトを FR1 のイディオムへ書き換える。

| サイト | 変数 | 参照位置 |
|--------|------|----------|
| Step I.1 | `BASE_COMMIT` | `implement-phase.md` 約 158-176 行 |
| Step I.2.b step 2 | `RECONCILE_TIP` | 約 389-406 行 |
| Step I.2.c route-back | `ROUTEBACK_TIP` | 約 459-477 行 |
| Step I.2.c rejected-path | `TERMINAL_TIP` | 約 504-510 行 |
| Step I.2.c abort-phase | `ABORT_TIP` | 約 518-524 行 |

**ビジネスルール**:
- 各サイトは、自身の変数名、自身のコミットメッセージ literal、自身の exit-4 相互参照を維持する。

**状態**: resolved

#### FR3: PR 17 の 2 サイトは参照形として不変

**説明**: Step I.2.a の `LAUNCH_TIP`（約 258-266 行）と Step I.3 の `COMPLETION_TIP`
（約 651-658 行）は既に FR1 のイディオムを持ち、本フィーチャーではその内容を変更しない。
これらは他の 5 サイトを合わせるべき参照形である。

**ビジネスルール**:
- Step I.2.a の、refresh 後の `rev-parse HEAD` が安全でない理由を説明する散文
  （約 275-297 行）は記述のまま残す。

**状態**: resolved

#### FR4: 対象サイト集合

**説明**: 対象集合は、tip を伴う `commit-docs.sh` 呼び出し 7 箇所すべて
（Step I.1、Step I.2.a、Step I.2.b、Step I.2.c route-back、Step I.2.c rejected、
Step I.2.c abort、Step I.3）である。

**ビジネスルール**:
- route-back サイトの exit-4 到達不能性に関する carve-out 散文はそのまま維持する。
  これは exit-4 の到達可能性に関するものであり tip 取得とは別事項で、本変更後も
  carve-out は carve-out のまま残る。

**状態**: resolved

#### FR5: Step I.1 の扱い（capture-then-refresh）

**説明**: Step I.1 は capture 形式のみではなく完全なイディオムを採用する。すなわち、
ブランチ ref から `BASE_COMMIT` を取得し、次に現在この step が持っていない
`git -C "$WT_ROOT/integration" reset --hard em-workflow/{feature}/integration` の refresh を
**追加**し、その後 `workflow.yaml` を書き、コミットする。

**ビジネスルール**:
- `$BASE_COMMIT` は引き続き `workflow[implement].base_commit` に記録される値であり、かつ
  `commit-docs.sh` の第 3 引数である（first-entry-only の意味論は変更しない）。
- `tests/test_review_implement_develop_lock_contracts.py` がピンしている literal
  `"docs({feature}): implement phase start" "$BASE_COMMIT"` は変更しない。

**状態**: resolved

#### FR6: Step I.2.b の capture 行配置（凍結された順序ピンの維持）

**説明**: Step I.2.b step 2 では、`tests/test_review_implement_develop_lock_contracts.py` の
`TestImplementPhaseWakePhaseOrdering` が無修正のまま通るように capture 行を配置する。

**ビジネスルール**:
- 当該クラスがピンするのは、`"Refresh the integration worktree FIRST"` <
  `"Update workflow.yaml, then commit"` < wake-phase のコミット literal という相対順序と、
  `phase reconcile" "$RECONCILE_TIP"` および `"(exit-4 recovery: Branch & Worktree"` の
  存在のみである。
- capture を `**Refresh the integration worktree FIRST**` の文の直前に挿入すれば、
  FR1 の capture-precedes-refresh 順序と上記すべてのピンを同時に満たす。

**状態**: resolved

#### FR7: 凍結モジュールのアサーション修正

**説明**: `tests/test_implement_routeback_gate.py` は、新イディオムを再ピンする 3 つの
限定的なアサーション修正に限りスコープ内である。

| 対象 | 内容 |
|------|------|
| (1) route-back 順序ピン | `TestGateDecisionPrecedesAllSideEffects.test_admitted_path_order_gate_refresh_tip_writeset_commit_cleanup`（約 486-502 行）の `assertLess(refresh_idx, tip_idx)` を、tip が refresh より前になるよう反転する。 |
| (2) abort-path の literal アサーション | `test_states_tip_capture`（約 817-818 行）の `rev-parse HEAD` literal を、ブランチ ref からの capture 形へ変更する。 |
| (3) abort-path 順序ピン | `test_order_refresh_before_tip_before_write_before_commit`（約 829-841 行）の refresh/tip 順序を反転する。 |

**ビジネスルール**:
- 当該モジュールの他のアサーションはすべて無修正のまま残す。
  `test_rejected_path_order_gate_terminal_write_terminal_commit`（約 504-512 行）は
  gate < `TERMINAL_TIP` < コミットメッセージのみをピンしており、無修正で通る。

**状態**: resolved

#### FR8: `commit-docs.sh` の散文整合（2 ブロック）

**説明**: `em-workflow/scripts/commit-docs.sh` の 2 つの散文ブロックを FR1 のイディオムに
合わせる。

- (a) `expected_base_tip` 引数の説明（約 13-21 行）。現在の
  「captured at the caller's last refresh (e.g. right after its `git reset --hard`)」という
  記述は旧イディオムを説明している。
- (b) RECOVERY CONTRACT のリカバリ手順（約 39-50 行）。現在の手順 (1) は
  refresh してから暗黙に再取得する形を説明している。

**ビジネスルール**:
- RECOVERY CONTRACT のうち、`implement-phase.md` Step I.2.c の route-back コミットを名指しする
  carve-out 文は変更しない。
- スクリプトの実行行は一切変更しない（コメントのみの変更）。

**状態**: resolved

#### FR9: イディオム一貫性テスト

**説明**: `tests/` 配下に新規の Python unittest モジュールを追加する（現時点で該当モジュールは
存在しない）。このモジュールは `implement-phase.md` のスコープ内 7 サイトすべてについて、
capture がブランチ ref から行われていること、それらのサイト内の `reset --hard` の対象が
すべてブランチ名であること（取得済み SHA でも HEAD でもないこと）、および各サイトで capture が
refresh に先行することを検出する。

**ビジネスルール**:
- 当該サイトにおける refresh 後の `rev-parse HEAD` 形の不在も検査対象に含め、
  退行が発生した場合にスイートが失敗するようにする。

**状態**: resolved

#### FR10: プラグインのバージョン bump

**説明**: `em-workflow/` 配下のファイルが変更されるため、
`em-workflow/.claude-plugin/plugin.json` の `version`（現在 0.1.45）と、
リポジトリルート `.claude-plugin/marketplace.json` の em-workflow エントリを、
同一の新しい値へ上げる。

**ビジネスルール**:
- リポジトリの plugin-version-bump ルールに従う。

**状態**: resolved

## 5. 非機能要件

### 5.1 パフォーマンス要件

該当なし。実行時の処理を持たない文書・テストの変更であり、測定対象の応答時間・スループット・
同時接続数が存在しない。

### 5.2 セキュリティ要件

該当なし（認証・認可・入力検証の対象となる実行時インタフェースを持たない）。
ただし安全性に関する不変条件は NFR5 として 5.6 に記載する。

### 5.3 可用性要件

該当なし。常時稼働するサービスを含まない。

### 5.4 保守性要件

- ドキュメント: `implement-phase.md` の 7 サイトが単一の一貫した機構として読めること（NFR1）。
- 検査: イディオムの逸脱を自動テストで検出できること（FR9 / TS-7）。

### 5.5 互換性要件

該当なし。ブラウザおよび API バージョンの互換性対象を持たない。

### 5.6 本フィーチャーの非機能要件

| ID | 名称 | 内容 |
|----|------|------|
| NFR1 | SSOT の内部整合性 | 変更後の `implement-phase.md` に、tip を伴う `commit-docs.sh` 呼び出しに対して旧イディオム（refresh → `rev-parse HEAD`）を規定する箇所が存在しないこと。7 サイトすべてが Branch & Worktree Model の exit-4 リカバリ項と合わせて単一の一貫した機構として読めること。 |
| NFR2 | テストスイートのスコープ限定 | 変更される既存テストモジュールは `tests/test_implement_routeback_gate.py` のみで、変更は FR7 の 3 アサーションに限る。他の既存テストモジュールはバイト単位で無変更（`tests/test_review_implement_develop_lock_contracts.py`、`tests/test_recycled_task_id_consistency.py`、`tests/test_routeback_reset_scope_consistency.py` を含む。後二者はコミットメッセージ literal の存続のみを観測する）。`python3 -m unittest discover -s tests` が全件成功すること。 |
| NFR3 | 凍結ピンの取り扱い規律 | プロトコル散文を既存テストに合わせて歪めない。凍結ピンが FR1 と矛盾する場合はピンの側を修正し（FR7）、その修正はイディオム変更によって正当化される（逆ではない）。ピンが FR1 と矛盾しない場合（wake-phase の順序クラス、コミットメッセージ literal の検査）は、ピンが無修正で通るように散文を配置する（FR6）。 |
| NFR4 | `commit-docs.sh` の実行系無変更 | `commit-docs.sh` の変更はコメントのみ。引数処理・終了コード・ロック・staleness 比較は変更後もバイト単位で同一であること。 |
| NFR5 | `reset --hard` 対象の安全性不変条件 | いかなるサイトも `reset --hard` の対象を取得済み SHA にしてはならない。integration worktree は HEAD が attach されているため、SHA への reset はブランチ ref 自体を巻き戻し、並行する `merge-task.sh` のマージコミットを黙って破棄する（PR 17 のレビューで critical として検出済み）。refresh の対象は常にブランチ名 `em-workflow/{feature}/integration` とする。 |
| NFR6 | スコープクリープの排除 | 変更集合はドキュメント、シェルコメント、テストアサーション 3 点、新規テストモジュール 1 本、バージョンマニフェスト 2 ファイルに限る。コミットメッセージ literal、`$BASE_COMMIT` の記録値の意味論、route-back の exit-4 到達不能性 carve-out とその証明、拡張済みの I.2.c ゲート条件、PR 17 の 2 サイトの内容は、いずれも保持する。 |

## 6. UI/UX要件

### 6.1 画面設計要件

該当なし。可視な表示面を持たないため、design ステップは `skipped` である。

### 6.2 画面遷移

該当なし（画面が存在しない）。

### 6.3 レスポンシブ対応

該当なし（画面が存在しない）。

## 7. データ要件

### 7.1 データモデル概要

該当なし。永続データモデルを持たない変更である。

### 7.2 データ項目

該当なし（7.1 と同じ理由）。

### 7.3 データ保持期間

該当なし（保持対象のデータが存在しない）。

## 8. 外部連携

### 8.1 連携システム

該当なし。外部システムとの連携を追加・変更しない。

### 8.2 API仕様要件

該当なし（API を定義・変更しない）。

## 9. 制約条件

### 9.1 技術的制約

- Branch & Worktree Model の exit-4 リカバリ項（`implement-phase.md` 43-82 行）は規範的参照であり
  変更しない（FR1）。
- `commit-docs.sh` の実行行は変更しない（FR8 / NFR4）。
- `tests/test_implement_routeback_gate.py` 以外の既存テストモジュールは変更しない（NFR2）。
- 新規テストは Python unittest モジュールとして `tests/` に置き、
  `python3 -m unittest discover -s tests` で発見される（前提 a7）。

### 9.2 ビジネス上の制約

- `em-workflow/` 配下の変更にはバージョン bump が伴う（FR10、リポジトリの
  plugin-version-bump ルール）。

### 9.3 スケジュール制約

要件分析にスケジュール制約の記載はない。

### 9.4 宣言された変更集合

**このフィーチャー固有のパス**:
- `em-workflow/references/implement-phase.md`
- `em-workflow/scripts/commit-docs.sh`
- `tests/test_implement_routeback_gate.py`
- `tests/`（FR9 で追加する新規イディオム一貫性テストモジュール）
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/tip-capture-idiom-unification/**`
- `test-docs/tip-capture-idiom-unification/**`

`feature-docs/{feature}/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`workflow.yaml`、
`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、
およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび
`references/phase-state.md` を参照。

`test-docs/{feature}/**` に含まれるもの: `{T}.tests.yaml`（パス形式:
`test-docs/tip-capture-idiom-unification/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な
  絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる
  （CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。

## 10. 想定される課題とリスク

### 10.1 技術的課題

| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 凍結された順序ピンが FR1 の順序と矛盾する | 中 | 矛盾するピンのみ FR7 の 3 アサーションとして修正し、矛盾しないピンは FR6 の配置で無修正のまま通す。 |
| 後続の編集でイディオムが旧形へ戻る | 中 | FR9 のイディオム一貫性テストで検出し、TS-7 で検出能力自体を確認する。 |
| `reset --hard` を取得済み SHA に向ける実装 | 高 | NFR5 の不変条件として禁止し、FR9 のテストで refresh 対象がブランチ名であることを検査する。 |

### 10.2 ビジネスリスク

| リスク | 発生確率 | 影響度 | 対応策 |
|--------|----------|--------|--------|
| スコープが文書・テスト・バージョン以外へ広がる | 低 | 中 | NFR6 で変更集合を限定し、TS-6 の diff 検査で確認する。 |
| バージョン bump 漏れによりキャッシュが更新されない | 低 | 中 | FR10 で 2 箇所を同一値に上げ、TS-8 で確認する。 |

## 11. 成功基準

### 11.1 受け入れ基準

- [ ] AC1: `em-workflow/references/implement-phase.md` のスコープ内 7 サイトすべてが、tip を
      ブランチ ref から取得し、refresh の対象をブランチ名とし、capture を refresh より前に置く。
- [ ] AC2: Branch & Worktree Model の exit-4 リカバリ項と各サイト本体の手順が同じ順序
      （capture してから refresh）を述べ、初回実行と exit-4 リトライが同一手順になる。
- [ ] AC3: `em-workflow/scripts/commit-docs.sh` の 2 つの散文ブロック（`expected_base_tip` の
      説明と RECOVERY CONTRACT のリカバリ手順）が新イディオムと整合し、carve-out 文と
      すべての実行行が無変更である。
- [ ] AC4: `python3 -m unittest discover -s tests` が成功し、
      `tests/test_implement_routeback_gate.py` の変更は FR7 が挙げる 3 アサーションのみ、
      他の既存モジュールは無変更である。
- [ ] AC5: 7 サイトのイディオム一貫性を検出し、いずれかのサイトが refresh 後の
      `rev-parse HEAD` 形に戻るか、`reset --hard` の対象がブランチ名以外になった場合に
      失敗するテストが存在する。
- [ ] AC6: `em-workflow/.claude-plugin/plugin.json` とルートの `.claude-plugin/marketplace.json` が
      同一の bump 後バージョン（0.1.45 より大きい）を持つ。

### 11.2 KPI

要件分析に KPI の記載はない。成否は 11.1 の受け入れ基準で判定する。

## 12. テストシナリオ

### 12.1 テスト観点

- [ ] 正常系（TS-1, 自動）: 新規一貫性テストが `implement-phase.md` を解析し、tip を伴う 7 つの
      `commit-docs.sh` 呼び出しサイト（`BASE_COMMIT`、`LAUNCH_TIP`、`RECONCILE_TIP`、
      `ROUTEBACK_TIP`、`TERMINAL_TIP`、`ABORT_TIP`、`COMPLETION_TIP`）を特定し、各サイトについて
      capture 式が `rev-parse em-workflow/{feature}/integration` を含むこと、capture に
      `rev-parse HEAD` を使っていないこと、サイト内のすべての `reset --hard` が
      `em-workflow/{feature}/integration` を対象にすること、capture の位置が refresh より前で
      あることを表明する。
- [ ] 正常系（TS-2, 自動）: Branch & Worktree Model の exit-4 リカバリ項が refresh の前に
      ブランチ ref から再取得することを述べており、その順序が TS-1 でサイトごとに表明した順序
      （capture-before-refresh の関係）と一致することを表明し、初回とリトライが乖離し得ないことを
      確認する。
- [ ] 正常系（TS-3, 自動）: `em-workflow/scripts/commit-docs.sh` を読み、`expected_base_tip` の
      説明と RECOVERY CONTRACT ブロックが、refresh とは独立に/refresh より前にブランチ ref から
      取得する旨を記述していること、旧来の
      「captured at the caller's last refresh (e.g. right after its `git reset --hard`)」という
      表現が消えていること、`implement-phase.md` Step I.2.c の route-back コミットを名指しする
      carve-out 文が逐語的に残っていることを表明する。
- [ ] 正常系（TS-4, 自動）: `commit-docs.sh` の実行本体が無変更であること、すなわちコメント以外の
      全行が変更前とバイト単位で同一であること（例: コメント除去後のソースを固定した期待値と
      比較する）を表明し、変更がコメントのみであることを確認する。
- [ ] 正常系（TS-5, コマンド）: integration worktree のルートで
      `python3 -m unittest discover -s tests` を実行し、修正後の
      `tests/test_implement_routeback_gate.py` と無修正の
      `tests/test_review_implement_develop_lock_contracts.py`、
      `tests/test_recycled_task_id_consistency.py`、
      `tests/test_routeback_reset_scope_consistency.py` を含めてスイート全体が成功する。
- [ ] 境界値（TS-6, 差分目視）: `tests/` に対する `git diff` を検査し、変更された既存モジュールが
      `tests/test_implement_routeback_gate.py` のみであること、その中で変更されたのが route-back の
      順序ピン（約 486-502 行）、abort の tip 取得 literal（約 817-818 行）、abort の順序ピン
      （約 829-841 行）だけであること、他のアサーション・モジュールが差分に現れないことを確認する。
- [ ] 異常系（TS-7, ネガティブ）: 新規一貫性テストを配置した状態で、変換済みサイトの 1 つを
      refresh 後の `rev-parse HEAD` 取得形へ一時的に戻すとそのテストが失敗し、戻しを取り消すと
      再び成功することを確認する（テストが自明に成功しているのではなく、実際に逸脱を検出している
      ことの確認）。
- [ ] 境界値（TS-8, 差分目視）: `em-workflow/.claude-plugin/plugin.json` と
      `.claude-plugin/marketplace.json` を読み、両者が同一の新バージョン文字列を持ち、それが
      0.1.45 よりパッチ 1 段階分大きいことを確認する。
- [ ] セキュリティ: 該当なし（認証・認可・入力検証の対象となる実行時インタフェースを持たない）。
- [ ] パフォーマンス: 該当なし（測定対象の実行時処理を持たない）。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| tip capture | `commit-docs.sh` に渡す `expected_base_tip` を取得する操作。 |
| 旧イディオム | integration worktree を refresh してから `rev-parse HEAD` で tip を取得する形。 |
| 新イディオム（正準イディオム） | FR1 が定める、ブランチ ref から tip を取得し、その後ブランチ名を対象に `reset --hard` で refresh する形。 |
| exit-4 リカバリ | `commit-docs.sh` が exit 4 を返したときの再試行手順。Branch & Worktree Model の該当項が規範。 |
| carve-out | Step I.2.c route-back サイトにおける exit-4 到達不能性の例外記述。 |
| 凍結ピン | 既存テストが逐語的に固定している文字列や相対順序の表明。 |

## 14. 確認事項

### 14.1 確認済み事項

要件分析が確定した前提（assumptions）は以下のとおり。

- [x] a1-base-is-pr17-head: 本フィーチャーの integration ブランチは
      `em-workflow/exit4-tip-argument/integration`（PR 17 の head）に基づいており、`main` ではない。
      したがって PR 17 の 2 サイト（Step I.2.a `LAUNCH_TIP`、Step I.3 `COMPLETION_TIP`）と exit-4
      リカバリ項のブランチ ref 表現は作業ベースに既に存在する。ベースが `main` であれば
      「変換 5 サイト・既に正しい 2 サイト」という分割は誤りとなり、変更集合の形自体が変わる。
- [x] a2-seven-sites-canonical: 列挙した 7 つの呼び出しが `implement-phase.md` における
      tip を伴う `commit-docs.sh` 呼び出しサイトの完全な集合である。同文書のその他の
      `commit-docs.sh` への言及（Branch & Worktree Model の各項、exit-4 リカバリ散文、
      約 541 行の Step I.2.c 失敗時散文）は機構への参照であって追加の呼び出しサイトではなく、
      FR8/FR1 の整合上必要な箇所のみ編集する。
- [x] a3-carveout-untouched: Step I.2.c route-back の exit-4 到達不能性 carve-out は、
      `implement-phase.md` と `commit-docs.sh` の RECOVERY CONTRACT の双方で有効なまま変更しない。
      これは当該サイトで exit 4 が発生し得るかを論じるものであり、tip の取得方法とは直交する。
      当該サイトの取得形を変換しても証明は強くも弱くもならない。
- [x] a4-wake-phase-pin-analysis-valid: `TestImplementPhaseWakePhaseOrdering` がピンするのは
      「Refresh the integration worktree FIRST」/「Update workflow.yaml, then commit」/
      wake-phase のコミット literal の相対順序のみであり、capture 行の位置も capture コマンドの
      形式も制約しない。分析時に当該モジュールの現行ソースに対して確認済み。
- [x] a5-step-i1-gains-a-refresh: Step I.1 には現在 `reset --hard` がない。したがって FR5 の
      capture-then-refresh 解決は当該 step に refresh 操作を追加する。これは意図されたものとして
      受け入れる。integration worktree はターンをまたいで未コミット状態を持たない
      （`implement-phase.md` の NFR2）ため、追加される refresh は安全であり、ベースラインコミットを
      他のすべてのサイトと整合させる。
- [x] a6-version-bump-is-patch: bump はパッチ 1 段階（0.1.45 → 0.1.46）である。実行可能物の挙動は
      変わらないため、minor でも major でもない。
- [x] a7-new-test-is-python-unittest-in-tests: 新規の一貫性テストは `tests/` 配下に置く Python
      unittest モジュールであり、`python3 -m unittest discover -s tests` で拾われる。これは本
      リポジトリの既存プロトコル文書整合テストと同じ形である。新しいテストフレームワークや
      ランナーは導入しない。
- [x] a8-task-description-site-count: タスク説明の「6 サイト」という枠組みは FR4 の 7 サイト集合に
      よって置き換えられる。説明は Step I.2.c rejected-path の `TERMINAL_TIP` サイトを落としていたが、
      当該サイトも他と同じ有界の exit-4 リカバリに従う。

### 14.2 未確認・保留事項

- なし。FR1-FR10 および NFR1-NFR6 はすべて `resolved` であり、`tbd` の要件はない。
- design ステップは `skipped`。理由: 本変更はプロトコル散文（`implement-phase.md`）、シェル
  コメント（`commit-docs.sh`）、Python テストのアサーション、バージョンマニフェスト 2 件のみを
  対象とし、可視面・ユーザー対話面・デザイントークンや画面が存在しないため、DESIGN.md と
  モックアップは内容を持たない。

## 15. 参考資料

- SPEC: `feature-docs/tip-capture-idiom-unification/SPEC.md`
- implement フェーズ SSOT: `em-workflow/references/implement-phase.md`
- コミットスクリプト: `em-workflow/scripts/commit-docs.sh`
- 変更対象の既存テスト: `tests/test_implement_routeback_gate.py`
- 無変更を確認する既存テスト: `tests/test_review_implement_develop_lock_contracts.py`,
  `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py`
- バージョンマニフェスト: `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
