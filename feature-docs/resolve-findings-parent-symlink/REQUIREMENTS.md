---
title: "resolve-findings-parent-symlink"
created_date: 2026-11-18
status: draft
---

# resolve-findings-parent-symlink - 要件定義書

## 1. 概要

### 1.1 背景
`resolve-verified-findings.py` に渡した `--feature-dir` の feature 以外の review ラウンド記録が、シンボリックリンク経由で書き換えられ得る。別 feature の deferred 指摘（critical/high, spec）が fixed に書き換わると、`merge-preflight.py` の事前チェックを通る。

### 1.2 目的
- `resolve-verified-findings.py` に渡した `--feature-dir` の feature 以外の review ラウンド記録を、シンボリックリンク経由で書き換えられないようにする
- 別 feature の deferred 指摘（critical/high, spec）が fixed に書き換わり、`merge-preflight.py` の事前チェックを不正に通る経路を塞ぐ

### 1.3 スコープ
- 検査対象は `--feature-dir` の最後の要素、`reviews`、ラウンド記録の 3 つ（FR5）
- `--feature-dir` の祖先にあるシンボリックリンクは検査しない（FR5）
- `em-workflow/skills/develop/SKILL.md`、`em-workflow/scripts/merge-preflight.py`、`tests/test_merge_preflight.py` は変更しない（NFR5）

## 2. ビジネス要件

### 2.1 ビジネス目標
- `resolve-verified-findings.py` に渡した `--feature-dir` の feature 以外の review ラウンド記録を、シンボリックリンク経由で書き換えられないようにする
- 別 feature の deferred 指摘（critical/high, spec）が fixed に書き換わり、`merge-preflight.py` の事前チェックを不正に通る経路を塞ぐ

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 別 feature の review ラウンド記録が `resolve-verified-findings.py` によって書き換わらない
- 別 feature の deferred 指摘が残っている状態では、`merge-preflight.py` が `unresolved_findings` で止まる（AC1）

## 3. ユースケース

該当なし（機能要件は 4 章に記載する）

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 |
|----|--------|------|
| FR1 | reviews ディレクトリがシンボリックリンクなら拒否する | `reviews` がリンクのとき `invalid-round-record` で失敗し、何も書かない |
| FR2 | feature ディレクトリ自体がシンボリックリンクなら拒否する | `--feature-dir` の最後の要素がリンクのとき `invalid-workflow` で失敗し、何も書かない |
| FR3 | 確認と書き込みを同じディレクトリハンドル基準で行う | feature ディレクトリと `reviews` を `O_DIRECTORY\|O_NOFOLLOW` で開き、以降の操作を `reviews` の dir_fd 基準で行う |
| FR4 | 既存の挙動を保つ | コマンドライン、エラーコード、終了コード、出力の形、書き換えの判定と内容を変えない |
| FR5 | feature ディレクトリより上の階層は検査しない | `--feature-dir` の祖先のシンボリックリンクは拒否しない |
| FR6 | docstring の Boundaries を更新する | リンクを拒否すること、およびそのエラーコードを記載する |
| FR7 | 末尾に区切り文字を付けた --feature-dir でもリンクを拒否する | 末尾の `/` を取り除いてから開く |
| FR8 | ラウンド記録を O_NOFOLLOW で開き fstat で通常ファイルか確かめる | lstat、`O_RDONLY\|O_NOFOLLOW` での open、fstat の順に確かめてから読む |

### 4.2 機能詳細

#### FR1: reviews ディレクトリがシンボリックリンクなら拒否する

**説明**: `--feature-dir` 直下の `reviews` がシンボリックリンクのとき（リンク先が別 feature の `reviews`、リポジトリ外のディレクトリ、存在しない場所のいずれでも）、スクリプトは `invalid-round-record` で失敗し（exit 1、stdout は空、stderr は 1 行）、どのファイルも書かない。リンク先のファイルも変わらない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `invalid-round-record` | `reviews` がシンボリックリンク | exit 1、stdout は空、stderr は 1 行。どのファイルも書かない |

#### FR2: feature ディレクトリ自体がシンボリックリンクなら拒否する

**説明**: `--feature-dir` に渡したパスの最後の要素（FR7 で末尾の区切り文字を取り除いた後の最後の要素）がシンボリックリンクのとき、スクリプトは `workflow.yaml` を読む前に `invalid-workflow` で失敗し、どのファイルも書かない。終了コードは、`--feature-dir` が存在しない場合の既存の挙動と同じ。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `invalid-workflow` | `--feature-dir` の最後の要素がシンボリックリンク | `workflow.yaml` を読む前に失敗する。終了コードは `--feature-dir` が存在しない場合と同じ。どのファイルも書かない |

#### FR3: 確認と書き込みを同じディレクトリハンドル基準で行う

**説明**: feature ディレクトリを `O_DIRECTORY|O_NOFOLLOW` で開き、`reviews` はその dir_fd 基準で `O_DIRECTORY|O_NOFOLLOW` で開く。次の操作は、すべて `reviews` の dir_fd 基準で行う。

- ラウンド記録の一覧取得
- 記録の確認と読み込み（FR8）
- ファイルモードの取得
- 一時ファイルの作成（`O_CREAT|O_EXCL|O_NOFOLLOW`、同じディレクトリ内）
- 置き換え（rename の src/dst を同じ `reviews` の dir_fd 基準にする）
- 失敗時の一時ファイル削除

`reviews` を開いた後にパス上の `reviews` がリンクに差し替えられても、書き込みがリンク先に届くことはない。

#### FR4: 既存の挙動を保つ

**説明**: コマンドライン（3 つのオプション、`=` 形式）、エラーコードの集合と終了コード、stdout の 1 行 JSON の形、書き換えの判定と内容は変えない。記録のファイルモードは保たれ、一時ファイルは同じディレクトリに作られ、成功時も失敗時も残らない。書き込みできないディレクトリでは記録はそのまま残る。新しいエラーコードは追加しない。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `missing-round-record` | `reviews` が無い | 現状どおり |
| `missing-round-record` | `reviews` がディレクトリでない通常ファイル | 現状どおり |
| `invalid-round-record` | ラウンド記録自体がシンボリックリンクやディレクトリなど通常ファイル以外 | 現状どおり |

#### FR5: feature ディレクトリより上の階層は検査しない

**説明**: 検査対象は `--feature-dir` の最後の要素、`reviews`、ラウンド記録の 3 つに限る。`--feature-dir` の祖先（feature-docs、worktree、ホームディレクトリなど）にシンボリックリンクが含まれていても拒否しない。祖先にリンクを含むパスで渡した正当な feature ディレクトリは、これまでどおり書き換えられる。

#### FR6: docstring の Boundaries を更新する

**説明**: スクリプト冒頭の docstring の Boundaries 節に、feature ディレクトリ（末尾に区切り文字を付けた場合を含む）・`reviews`・ラウンド記録のシンボリックリンクを拒否すること、およびそれぞれのエラーコードを記載する。

#### FR7: 末尾に区切り文字を付けた --feature-dir でもリンクを拒否する

**説明**: `--feature-dir` の末尾の区切り文字（`/` が 1 個以上）を取り除いてから、FR2 / FR3 の `O_DIRECTORY|O_NOFOLLOW` で開く。

**ビジネスルール**:
- 区切り文字だけからなるパス（`/` など）は取り除かずに開く。
- 末尾に区切り文字を付けた引数（`current/`、`current//` など）でも、最後の要素がシンボリックリンクなら FR2 と同じく `invalid-workflow` で失敗し、どのファイルも書かない。
- リンクでないディレクトリに末尾の区切り文字を付けた場合は、付けないときと同じ結果になる。
- 末尾の区切り文字以外の要素（`.` や `..`）は書き換えない。

#### FR8: ラウンド記録を O_NOFOLLOW で開き fstat で通常ファイルか確かめる

**説明**: ラウンド記録は `reviews` の dir_fd 基準で扱う。

**処理フロー**:
1. 開く前にリンクを辿らない lstat で通常ファイルであることを確かめる（現状どおり、通常ファイル以外は開かずに拒否する）。
2. `O_RDONLY|O_NOFOLLOW` で開く。
3. 開いた fd の fstat で通常ファイルであることを確かめる。
4. その fd から上限付きで読む。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| `invalid-round-record` | 上の確認のどれかを満たさない、または開く・読むのに失敗した | どのファイルも書かない |

## 5. 非機能要件

| ID | 要件 |
|----|------|
| NFR1 | スクリプトの依存は標準ライブラリと PyYAML のまま。テストは標準ライブラリの unittest のみを使い、サードパーティを import しない（PyYAML を使う確認は既存どおり子プロセスで行う）。 |
| NFR2 | 対象プラットフォームは POSIX（Linux / macOS）。`O_NOFOLLOW`、`O_DIRECTORY`、dir_fd を使う。 |
| NFR3 | 差し替えの競合を確かめるテストは、CPU に負荷をかけて競合を起こさず、決定的に再現する。たとえば、`yaml.safe_dump` や `os.open` を包むラッパーから runpy でスクリプトを実行し、該当の呼び出しの直前に差し替える。 |
| NFR4 | stdout / stderr に出すのは、これまでどおり検証済みの値とエラーコードだけ。パスやリンク先は出さない。 |
| NFR5 | `em-workflow/skills/develop/SKILL.md`、`em-workflow/scripts/merge-preflight.py`、`tests/test_merge_preflight.py` は変更しない。 |

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 依存は標準ライブラリと PyYAML のまま（NFR1）
- 対象プラットフォームは POSIX（Linux / macOS）（NFR2）
- 新しいエラーコードは追加しない（FR4）

### 9.2 ビジネス上の制約
- `em-workflow/skills/develop/SKILL.md`、`em-workflow/scripts/merge-preflight.py`、`tests/test_merge_preflight.py` は変更しない（NFR5）

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/resolve-findings-parent-symlink/**`
- `test-docs/resolve-findings-parent-symlink/**`

`feature-docs/resolve-findings-parent-symlink/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/resolve-findings-parent-symlink/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/resolve-findings-parent-symlink/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/resolve-findings-parent-symlink/` ディレクトリを生成しないが、宣言された `test-docs/resolve-findings-parent-symlink/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1）: `feature-docs/current/reviews` を別 feature（other）の `reviews` へのシンボリックリンクにし、other の `round1.yaml` に deferred の high/spec 指摘を置いた状態で、`--feature-dir` に current を渡して実行すると、`invalid-round-record` で失敗する。other の `reviews` 配下は 1 バイトも変わらず、ファイルも増えない。other の記録をコミットした状態では `merge-preflight.py` は `unresolved_findings` で止まる。
- [ ] AC2（FR1）: `reviews` がリポジトリ外のディレクトリを指すリンク、または存在しない場所を指すリンクのとき、`invalid-round-record` で失敗し、feature ディレクトリ・リンク先とも変わらない。
- [ ] AC3（FR2）: `--feature-dir` が別 feature のディレクトリを指すシンボリックリンクのとき、`invalid-workflow` で失敗し、リンク先の feature のファイルは変わらない。
- [ ] AC4（FR3）: スクリプトが `reviews` を開いた後、書き込む前に、パス上の `reviews` を別 feature の `reviews` へのリンクに差し替えても、別 feature の `reviews` 配下は 1 バイトも変わらず、一時ファイルも残らない。
- [ ] AC5（FR5）: 祖先にシンボリックリンクを含むパスで正当な feature ディレクトリを渡すと、条件を満たす指摘はこれまでどおり fixed に書き換わる（exit 0）。
- [ ] AC6（FR4）: `tests.test_resolve_verified_findings` の既存テストをすべて削除・弱体化せずに残し、`python3 -m unittest tests.test_resolve_verified_findings` と `python3 -m unittest discover -s tests` がともに成功する。
- [ ] AC7（FR6）: docstring の Boundaries 節に、feature ディレクトリ（末尾に区切り文字を付けた場合を含む）・`reviews`・ラウンド記録のシンボリックリンクを拒否することと、そのエラーコードが書かれている。
- [ ] AC8（FR7, FR2）: `feature-docs/current` が `feature-docs/other` へのシンボリックリンクのとき、`--feature-dir` に `current/` と `current//` を渡すと、どちらも `invalid-workflow` で失敗し（exit 1、stdout は空、stderr は 1 行）、other の feature ディレクトリ配下は 1 バイトも変わらず、ファイルも増えない。
- [ ] AC9（FR7）: リンクでない正当な feature ディレクトリに末尾の区切り文字を付けて（`DIR/` と `DIR//`）渡すと、付けないときと同じく条件を満たす指摘が fixed に書き換わり（exit 0）、stdout の JSON も同じになる。
- [ ] AC10（FR8）: ラウンド記録を開く前の確認の後、開く直前に記録を別 feature の記録へのシンボリックリンクに差し替えると、`invalid-round-record` で失敗し、リンク先の記録は 1 バイトも変わらない。ラウンド記録が FIFO のときは、待ち続けずに `invalid-round-record` で失敗する。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 正常系: 祖先にリンクを含むパスでの書き換え（AC5）、末尾に区切り文字を付けたリンクでない feature ディレクトリでの書き換え（AC9）、既存テストの維持（AC6）
- [ ] 異常系: `reviews` がリンク（AC1、AC2）、feature ディレクトリがリンク（AC3）、末尾に区切り文字を付けた feature ディレクトリがリンク（AC8）、ラウンド記録が FIFO（AC10）
- [ ] 境界値: `--feature-dir` の末尾の区切り文字が 1 個と 2 個（AC8、AC9）
- [ ] セキュリティ: `reviews` を開いた後の差し替え（AC4）、ラウンド記録を開く直前の差し替え（AC10）
- [ ] パフォーマンス: 該当なし

### 12.2 エッジケース
- `reviews` がリポジトリ外のディレクトリを指すリンク、存在しない場所を指すリンク（AC2）
- `--feature-dir` が `current/`、`current//` のように末尾に区切り文字を持つ（FR7、AC8、AC9）
- 区切り文字だけからなるパス（`/` など）は末尾の区切り文字を取り除かずに開く（FR7）
- `--feature-dir` が `current/.` のように `.` で終わるとき、最後の要素は `.` であり、current は FR5 の祖先として扱われ検査されない（14.1 の前提）
- ラウンド記録が FIFO（AC10）
- `reviews` がディレクトリでない通常ファイル（FR4、`missing-round-record`）

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| ラウンド記録 | feature ディレクトリの `reviews` 配下にある review ラウンドの記録ファイル |
| dir_fd | ディレクトリを開いたファイル記述子。FR3 のディレクトリハンドル |

## 14. 確認事項

### 14.1 確認済み事項
- [x] 修正方式: realpath による包含確認ではなく、`O_DIRECTORY|O_NOFOLLOW` で開いた dir_fd を基準にした読み書きとする。
- [x] エラーコード: `reviews` がシンボリックリンクのときは `invalid-round-record`（ラウンド記録自体がリンクのときと同じ）。feature ディレクトリがリンクのときは、末尾の区切り文字の有無にかかわらず `invalid-workflow`（feature ディレクトリが存在しないときと同じ）。新しいエラーコードは足さない。
- [x] `workflow.yaml` とマッピングファイル: 読むだけで書き込み先にならないため、それら自体がシンボリックリンクであるときの挙動は変えない（現状どおり辿る）。
- [x] `--feature-dir` の祖先にあるシンボリックリンクは検査しない。
- [x] 末尾の区切り文字以外のパス要素（`.` や `..`）は正規化しない。`--feature-dir` が `current/.` のように `.` で終わるとき、最後の要素は `.` であり、current は FR5 の祖先として扱われ検査されない。
- [x] これはこのリポジトリ自身のコードの修正であり、外部の修正版は存在しない。この修正そのものを恒久対応とし、暫定緩和策は設けない。
- [x] 既存テストが固定している性質（記録自体のリンクの拒否、`reviews` 不在での `missing-round-record`、一時ファイルが残らないこと、ファイルモードの保持、読み取り専用ディレクトリでの不変）と、通常ファイル以外の記録を開く前に拒否する現状の挙動は、保つべき不変条件として扱う。
- [x] plugin の version は手で上げない（main への push 時に Actions が patch を上げる）。
- [x] デザインステップ: UI を持たない CLI スクリプトのセキュリティ修正のため、スキップする。

### 14.2 未確認・保留事項
- なし

## 15. 参考資料

該当なし
