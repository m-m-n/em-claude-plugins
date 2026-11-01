---
title: "launch-guard-common-dir-fallback"
created_date: 2026-11-01
status: draft
---

# launch-guard-common-dir-fallback - 要件定義書

## 1. 概要

### 1.1 背景
launch guard は、worktree_path に区切り（`/.claude/worktrees/em-workflow/`）が無いとき、`git rev-parse --path-format=absolute --git-common-dir` の出力（共通管理ディレクトリ）の親をプロジェクトのルートとして求める（git-common-dir フォールバック）。

### 1.2 目的
- 共通管理ディレクトリが主作業場所直下の `.git` でない構成（サブモジュール、`--separate-git-dir`）で、正しい場所からの起動を拒否しない。
- プロジェクトのルート自体が linked worktree の構成で、正しい場所からの起動を拒否しない。
- 判断できない状態は fail-open を保つ（NFR2）。

### 1.3 スコープ
- launch guard の、区切りが無い経路でのプロジェクトのルートの判定と cwd の確認（FR1〜FR4）
- 区切りがある経路は変えない（FR5）
- フック冒頭の docstring（FR6）
- `tests/test_queue_launch_guard_linked_layout.py` のテスト追加と既存 fixture の修正（FR7）
- `tests/test_merge_unverified_exit_doc_contract.py` の sha256 の固定値と関連する記述の更新（FR8）

## 2. ビジネス要件

### 2.1 ビジネス目標
- launch guard の git-common-dir フォールバックが、共通管理ディレクトリが主作業場所直下の `.git` でない構成（サブモジュール、`--separate-git-dir`）や、プロジェクトのルート自体が linked worktree の構成で、正しい場所からの起動を拒否しないようにする。
- 判断できない状態は fail-open を保つ（NFR2）。

### 2.2 対象ユーザー
| ユーザータイプ | 説明 |
|----------------|------|
| em-workflow の利用者 | launch guard が判定する起動を行う |

### 2.3 期待される効果
- サブモジュール、`--separate-git-dir`、linked worktree をルートにした構成で、正しい場所からの起動が拒否されない。

## 3. ユースケース

### 3.1 ユースケース一覧
| ID | ユースケース名 | アクター | 優先度 |
|----|----------------|----------|--------|
| UC01 | 共通管理ディレクトリの末尾が `.git` でない構成での起動 | em-workflow の利用者 | 高 |
| UC02 | linked worktree をプロジェクトのルートにした構成での起動 | em-workflow の利用者 | 高 |

### 3.2 ユースケース詳細

#### UC01: 共通管理ディレクトリの末尾が `.git` でない構成での起動

**アクター**: em-workflow の利用者

**事前条件**:
- worktree_path に区切りが無い。
- git-common-dir の出力を正規化した末尾要素が `.git` でない（例: `/super/.git/modules/sub`、`/store/proj.git`）。

**基本フロー**:
1. launch guard が git-common-dir を 1 回呼び出す。
2. 出力を正規化し、末尾要素が `.git` でないことを確認する。
3. プロジェクトのルートを未確定とし、cwd の確認を省く。

**事後条件**:
- フックは出力なしで exit 0 になり、journal に launched を 1 件記録する。

#### UC02: linked worktree をプロジェクトのルートにした構成での起動

**アクター**: em-workflow の利用者

**事前条件**:
- worktree_path に区切りが無い。
- プロジェクトのルートが linked worktree で、主作業場所の外または内側に置かれている。

**基本フロー**:
1. launch guard が共通管理ディレクトリの親としてルートを求める。
2. 求めたルートが cwd の git toplevel を内包し、その toplevel が worktree_path を真に内包することを確認する。
3. 起動を拒否しない。

**代替フロー**:
- toplevel と worktree_path が同一のときは拒否する。
- 求めたルートが toplevel を内包しないときは拒否する。

**事後条件**:
- 起動が許可され、journal に launched が記録される。

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 共通管理ディレクトリ末尾の確認 | 末尾要素が `.git` でないときルートを未確定とし、cwd の確認を省く | 高 |
| FR2 | ルートが worktree_path を内包しないときの fail-open | 求めたルートが worktree_path を内包しないとき cwd の確認を省く | 高 |
| FR3 | linked worktree のルートからの起動を拒否しない | ルートが toplevel を内包し、toplevel が worktree_path を真に内包するとき拒否しない | 高 |
| FR4 | git 呼び出しの回数 | 既存の呼び出しの結果だけを使い、git の呼び出しを増やさない | 高 |
| FR5 | 区切りがある経路は変えない | 区切りがある経路の挙動を保つ | 高 |
| FR6 | モジュール docstring | Project root 段落に FR1〜FR3 の規則を加える | 中 |
| FR7 | テスト | linked layout のテストを追加し、既存 fixture を直す | 高 |
| FR8 | sha256 の固定値の更新 | EXPECTED_LAUNCH_GUARD_SHA256 と関連する記述を更新する | 高 |

### 4.2 機能詳細

#### FR1: 共通管理ディレクトリ末尾の確認

**説明**: 区切り（`/.claude/worktrees/em-workflow/`）が無い経路で、`git rev-parse --path-format=absolute --git-common-dir` の出力を正規化し、末尾要素が `.git` でないとき、プロジェクトのルートは未確定とし、cwd の確認を省く（fail-open）。

**ビジネスルール**:
- 末尾の確認は、既存の git-common-dir 呼び出しの出力を normpath した結果の basename が `.git` と完全一致するかで行う（A1）。

#### FR2: ルートが worktree_path を内包しないときの fail-open

**説明**: 区切りが無い経路で、共通管理ディレクトリの親として求めたルートが worktree_path を内包しないとき、cwd の確認を省く（fail-open）。

**ビジネスルール**:
- 内包は realpath を取った両者を `os.path.commonpath` で比べて判定する。

#### FR3: linked worktree のルートからの起動を拒否しない

**説明**: 区切りが無い経路で、次の 2 つがどちらも成り立つときは拒否しない。
- 求めたルートが cwd の git toplevel を内包する。
- その toplevel が worktree_path を真に内包する（toplevel と worktree_path が同一の場合は除く）。

**ビジネスルール**:
- 内包は realpath と `os.path.commonpath` で判定する。

#### FR4: git 呼び出しの回数

**説明**: FR1〜FR3 の判定は、既存の git-common-dir 呼び出し 1 回と、既存の show-toplevel 呼び出しの結果だけを使う。git の呼び出しは増やさない。

#### FR5: 区切りがある経路は変えない

**説明**: worktree_path に区切りがあるとき、ルートは最後の出現より前の部分とする（先頭にあれば未確定）。この挙動とプロセスを起動しないことは変えない。FR1〜FR3 は区切りが無い経路だけに適用する。

#### FR6: モジュール docstring

**説明**: フック冒頭の docstring の Project root 段落に、FR1〜FR3 の規則を加える。TestHookDocstring が固定している 3 文（区切りの文、フォールバックの文、fail-open の文）はそのまま残す。

**ビジネスルール**:
- 固定されている 3 文は、空白を正規化した部分文字列として docstring に残す（A2）。

#### FR7: テスト

**説明**: `tests/test_queue_launch_guard_linked_layout.py` に次を足す。
1. 共通管理ディレクトリが `/super/.git/modules/sub` と `/store/proj.git` を返す構成で、ルートが未確定になる。他の toplevel を cwd にしても拒否されない。hook_main が出力なしで exit 0 になり、launched を 1 件記録する。
2. ルートが worktree_path を内包しない構成で fail-open になる。
3. linked worktree をルートにした構成で、そのルートを cwd とした起動が拒否されない。主作業場所の外に置く配置と、主作業場所の内側に置く配置の両方で確かめる。
4. FR3 の境界: toplevel == worktree_path は拒否する。ルートが toplevel を内包しないときは拒否する。

既存の `TestFallbackCallShape.CANONICAL_PATH` と `TestFallbackFailures.WORKTREE_PATH`（`/proj-store/em-workflow/f/task0001` で `/proj/.git` と組）は、区切りの無い `/proj` 配下のパスに直す。既存の拒否の検証（`test_a_resolved_common_dir_with_another_toplevel_is_a_denial` など）は残す。

**ビジネスルール**:
- 受け入れ条件 3 は、RecordingRunner で git-common-dir の出力を差し替える単体テストと、hook_main のテストで確かめる。実際のサブモジュールや `--separate-git-dir` の fixture は作らない（A4）。

#### FR8: sha256 の固定値の更新

**説明**: `tests/test_merge_unverified_exit_doc_contract.py` の `EXPECTED_LAUNCH_GUARD_SHA256` を、変更後の launch guard の sha256 に同じ変更の中で更新する。直前のコメントと `TestNeverModifiedFilesAreByteIdentical` の docstring の、変更されていないという記述も実態に合わせて直す。

**ビジネスルール**:
- `EXPECTED_LAUNCH_GUARD_SHA256` は、同じ変更の中で新しいフックの内容の sha256 に更新する（A5）。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| ルート未確定 | 正規化した共通管理ディレクトリの末尾要素が `.git` でない | cwd の確認を省く（FR1） |
| ルートが worktree_path を内包しない | 区切りが無い経路で、求めたルートが worktree_path を内包しない | cwd の確認を省く（FR2） |

## 5. 非機能要件

### 5.1 パフォーマンス要件
- NFR3: git-common-dir の呼び出しは区切りが無い経路で 1 回のまま。コマンド形・cwd（worktree_path）・タイムアウト（GIT_TIMEOUT_SECONDS）は変えない。

### 5.2 セキュリティ要件
- NFR4: 標準 linked layout（主作業場所がルートで、保管先がプロジェクト内）で、integration worktree や task worktree 自身を cwd にした起動は、主作業場所を名指しして拒否されたまま。拒否時は journal に launched を残さない。

### 5.3 可用性要件
- NFR2: 判断できない状態は fail-open。どの経路でもフックは exit 0 で、クラッシュしない。

### 5.4 保守性要件
- NFR1: フックとテストは標準ライブラリだけを import する（TestStdlibAndDeterminism）。
- NFR5: テストは時間待ちや CPU 負荷に頼らない（sleep や時間計測のモジュールを使わない）。

### 5.5 互換性要件
- 標準 linked layout の既存の拒否ケースは、FR2・FR3 の後も拒否されたまま（A3）。

## 6. UI/UX要件

該当なし。

## 7. データ要件

該当なし。

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| git | `git rev-parse --path-format=absolute --git-common-dir`、show-toplevel（既存の呼び出し） | 共通管理ディレクトリ、cwd の git toplevel |

## 9. 制約条件

### 9.1 技術的制約
- git の呼び出しは増やさない（FR4、NFR3）。
- 標準ライブラリだけを import する（NFR1）。
- plugin の version は変えない（A6）。

### 9.2 ビジネス上の制約
- なし

### 9.3 スケジュール制約
- なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/launch-guard-common-dir-fallback/**`
- `test-docs/launch-guard-common-dir-fallback/**`

`feature-docs/launch-guard-common-dir-fallback/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/launch-guard-common-dir-fallback/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/launch-guard-common-dir-fallback/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
| 課題 | 影響度 | 対応策 |
|------|--------|--------|
| 標準 linked layout の既存の拒否ケースが拒否されなくなる | 中 | 既存の TestLinkedLayoutOtherWorktreeLaunch が通ることを確かめる（A3、NFR4） |

### 10.2 ビジネスリスク
該当なし。

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: 正規化した共通管理ディレクトリの末尾要素が `.git` でないときは確認を省く（fail-open）
- [ ] AC2: プロジェクトのルートが linked worktree の場合に、正しい場所からの起動が拒否されない。主作業場所の外に置く配置と内側に置く配置の両方で確かめる
- [ ] AC3: `/super/.git/modules/sub` と `/store/proj.git` を返す構成で拒否されないことをテストで確かめる
- [ ] AC4: 区切りが無い経路で、求めたルートが worktree_path を内包しないときは確認を省く（fail-open）
- [ ] AC5: 標準 linked layout で、integration worktree や task worktree 自身からの起動は拒否されたまま（既存テストが通る）
- [ ] AC6: git-common-dir の呼び出しは 1 回のまま（TestFallbackCallShape が通る）
- [ ] AC7: docstring の既存の固定文が残り、新しい規則が書かれている
- [ ] AC8: EXPECTED_LAUNCH_GUARD_SHA256 が変更後のフックと一致し、`python3 -m unittest discover -s tests` が通る

### 11.2 KPI
該当なし。

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1 (AC1/AC3, 単体): RecordingRunner で common dir に `/super/.git/modules/sub` を返す。project root は未確定になり、cwd_outside_project_root は他の toplevel でも None。git-common-dir の呼び出しは 1 回
- [ ] TS2 (AC1/AC3, 単体): `/store/proj.git` で TS1 と同じことを確かめる
- [ ] TS3 (AC1/AC3, hook_main): TS1・TS2 の出力で hook_main が exit 0、stdout が空、launched が 1 件
- [ ] TS4 (AC1, 単体): `/proj/.git/` や `/proj/./x/../.git` のように末尾スラッシュや `.`・`..` を含む出力でも、正規化してから末尾が `.git` と判定される
- [ ] TS5 (AC4, 単体): common dir `/proj/.git`、worktree_path `/elsewhere/em-workflow/f/task0001`、cwd の toplevel が別の場所 → None（拒否しない）
- [ ] TS6 (AC2, 実際の git): 主作業場所 M の外に linked worktree L を作り、L を project root にして linked layout（保管先は L の中）の task worktree を作る。cwd を L にして起動 → 許可され、launched が記録される
- [ ] TS7 (AC2, 実際の git): linked worktree L を主作業場所 M の内側に置いて TS6 と同じことを確かめる → cwd が L なら許可される
- [ ] TS8 (FR3 の境界, 単体): toplevel == worktree_path → 拒否。ルートが toplevel を内包しない（toplevel がルートの外側の祖先）→ 拒否
- [ ] TS9 (AC5): 既存の TestLinkedLayoutOtherWorktreeLaunch がそのまま通る
- [ ] TS10 (AC6/AC7): 既存の TestFallbackCallShape・TestFallbackFailures（fixture のパスは `/proj` 配下に直す）・TestHookDocstring が通る
- [ ] TS11 (AC8): `tests.test_merge_unverified_exit_doc_contract.TestNeverModifiedFilesAreByteIdentical.test_launch_guard_untouched` が通る

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 区切り | worktree_path に含まれる `/.claude/worktrees/em-workflow/` |
| 共通管理ディレクトリ | `git rev-parse --path-format=absolute --git-common-dir` の出力 |
| 内包 | realpath を取った両者を `os.path.commonpath` で比べ、一方が他方の配下（または同一）であること |
| 真に内包 | 内包し、かつ同一でないこと |
| 標準 linked layout | 主作業場所がルートで、保管先がプロジェクト内の配置 |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 前提 A1: 末尾の確認は、既存の git-common-dir 呼び出しの出力を normpath した結果の basename が `.git` と完全一致するかで行う
- [x] 前提 A2: TestHookDocstring が固定している 3 文は、空白を正規化した部分文字列として docstring に残す
- [x] 前提 A3: 標準 linked layout の既存の拒否ケースは、FR2・FR3 の後も拒否されたまま
- [x] 前提 A4: 受け入れ条件 3 は、RecordingRunner で git-common-dir の出力を差し替える単体テストと、hook_main のテストで確かめる。実際のサブモジュールや `--separate-git-dir` の fixture は作らない
- [x] 前提 A5: EXPECTED_LAUNCH_GUARD_SHA256 は、同じ変更の中で新しいフックの内容の sha256 に更新する
- [x] 前提 A6: plugin の version は変えない（main への push 時に Actions が patch を上げる）
- [x] デザインステップ: 省略（UI の無いフック内部の判定ロジックとテストだけの変更）

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

- `tests/test_queue_launch_guard_linked_layout.py`
- `tests/test_merge_unverified_exit_doc_contract.py`
