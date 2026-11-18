# Feature: resolve-findings-parent-symlink

## Overview

`resolve-verified-findings.py` が、`--feature-dir` に渡した feature 以外の review ラウンド記録をシンボリックリンク経由で書き換えないようにする。feature ディレクトリ・`reviews`・ラウンド記録を `O_NOFOLLOW` で開き、確認と書き込みを同じ dir_fd 基準で行う。要件の詳細は `REQUIREMENTS.md` を参照する。

## Objectives

- `resolve-verified-findings.py` に渡した `--feature-dir` の feature 以外の review ラウンド記録を、シンボリックリンク経由で書き換えられないようにする
- 別 feature の deferred 指摘（critical/high, spec）が fixed に書き換わり、`merge-preflight.py` の事前チェックを不正に通る経路を塞ぐ

## User Stories

ユーザーストーリーは定義しない。受け入れ条件を以下に示す。

**Acceptance Criteria:**
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

## Technical Requirements

### Functional Requirements
- **FR1:** reviews ディレクトリがシンボリックリンクなら拒否する — `--feature-dir` 直下の `reviews` がシンボリックリンクのとき（リンク先が別 feature の `reviews`、リポジトリ外のディレクトリ、存在しない場所のいずれでも）、スクリプトは `invalid-round-record` で失敗し（exit 1、stdout は空、stderr は 1 行）、どのファイルも書かない。リンク先のファイルも変わらない。
- **FR2:** feature ディレクトリ自体がシンボリックリンクなら拒否する — `--feature-dir` に渡したパスの最後の要素（FR7 で末尾の区切り文字を取り除いた後の最後の要素）がシンボリックリンクのとき、スクリプトは `workflow.yaml` を読む前に `invalid-workflow` で失敗し、どのファイルも書かない。終了コードは、`--feature-dir` が存在しない場合の既存の挙動と同じ。
- **FR3:** 確認と書き込みを同じディレクトリハンドル基準で行う — feature ディレクトリを `O_DIRECTORY|O_NOFOLLOW` で開き、`reviews` はその dir_fd 基準で `O_DIRECTORY|O_NOFOLLOW` で開く。ラウンド記録の一覧取得、記録の確認と読み込み（FR8）、ファイルモードの取得、一時ファイルの作成（`O_CREAT|O_EXCL|O_NOFOLLOW`、同じディレクトリ内）、置き換え（rename の src/dst を同じ `reviews` の dir_fd 基準にする）、失敗時の一時ファイル削除は、すべて `reviews` の dir_fd 基準で行う。`reviews` を開いた後にパス上の `reviews` がリンクに差し替えられても、書き込みがリンク先に届くことはない。
- **FR4:** 既存の挙動を保つ — コマンドライン（3 つのオプション、`=` 形式）、エラーコードの集合と終了コード、stdout の 1 行 JSON の形、書き換えの判定と内容は変えない。`reviews` が無いときは `missing-round-record`、`reviews` がディレクトリでない通常ファイルのときは `missing-round-record`（現状どおり）、ラウンド記録自体がシンボリックリンクやディレクトリなど通常ファイル以外のときは `invalid-round-record`。記録のファイルモードは保たれ、一時ファイルは同じディレクトリに作られ、成功時も失敗時も残らない。書き込みできないディレクトリでは記録はそのまま残る。新しいエラーコードは追加しない。
- **FR5:** feature ディレクトリより上の階層は検査しない — 検査対象は `--feature-dir` の最後の要素、`reviews`、ラウンド記録の 3 つに限る。`--feature-dir` の祖先（feature-docs、worktree、ホームディレクトリなど）にシンボリックリンクが含まれていても拒否しない。祖先にリンクを含むパスで渡した正当な feature ディレクトリは、これまでどおり書き換えられる。
- **FR6:** docstring の Boundaries を更新する — スクリプト冒頭の docstring の Boundaries 節に、feature ディレクトリ（末尾に区切り文字を付けた場合を含む）・`reviews`・ラウンド記録のシンボリックリンクを拒否すること、およびそれぞれのエラーコードを記載する。
- **FR7:** 末尾に区切り文字を付けた --feature-dir でもリンクを拒否する — `--feature-dir` の末尾の区切り文字（`/` が 1 個以上）を取り除いてから、FR2 / FR3 の `O_DIRECTORY|O_NOFOLLOW` で開く。区切り文字だけからなるパス（`/` など）は取り除かずに開く。末尾に区切り文字を付けた引数（`current/`、`current//` など）でも、最後の要素がシンボリックリンクなら FR2 と同じく `invalid-workflow` で失敗し、どのファイルも書かない。リンクでないディレクトリに末尾の区切り文字を付けた場合は、付けないときと同じ結果になる。末尾の区切り文字以外の要素（`.` や `..`）は書き換えない。
- **FR8:** ラウンド記録を O_NOFOLLOW で開き fstat で通常ファイルか確かめる — ラウンド記録は `reviews` の dir_fd 基準で扱う。開く前にリンクを辿らない lstat で通常ファイルであることを確かめ（現状どおり、通常ファイル以外は開かずに拒否する）、`O_RDONLY|O_NOFOLLOW` で開き、開いた fd の fstat で通常ファイルであることを確かめてから、その fd から上限付きで読む。どれかを満たさないとき、または開く・読むのに失敗したときは `invalid-round-record` で失敗し、どのファイルも書かない。

### Non-Functional Requirements
- **NFR1 - 依存とテストの制約:** スクリプトの依存は標準ライブラリと PyYAML のまま。テストは標準ライブラリの unittest のみを使い、サードパーティを import しない（PyYAML を使う確認は既存どおり子プロセスで行う）。
- **NFR2 - 対象プラットフォーム:** 対象プラットフォームは POSIX（Linux / macOS）。`O_NOFOLLOW`、`O_DIRECTORY`、dir_fd を使う。
- **NFR3 - 競合テストの決定性:** 差し替えの競合を確かめるテストは、CPU に負荷をかけて競合を起こさず、決定的に再現する。たとえば、`yaml.safe_dump` や `os.open` を包むラッパーから runpy でスクリプトを実行し、該当の呼び出しの直前に差し替える。
- **NFR4 - 出力に出す値:** stdout / stderr に出すのは、これまでどおり検証済みの値とエラーコードだけ。パスやリンク先は出さない。
- **NFR5 - 変更しないファイル:** `em-workflow/skills/develop/SKILL.md`、`em-workflow/scripts/merge-preflight.py`、`tests/test_merge_preflight.py` は変更しない。

## Assumptions

- 修正方式は realpath による包含確認ではなく、`O_DIRECTORY|O_NOFOLLOW` で開いた dir_fd を基準にした読み書きとする。
- `reviews` がシンボリックリンクのときのエラーコードは `invalid-round-record`（ラウンド記録自体がリンクのときと同じ）。feature ディレクトリがリンクのときは、末尾の区切り文字の有無にかかわらず `invalid-workflow`（feature ディレクトリが存在しないときと同じ）。新しいエラーコードは足さない。
- `workflow.yaml` とマッピングファイルは読むだけで書き込み先にならないため、それら自体がシンボリックリンクであるときの挙動は変えない（現状どおり辿る）。
- `--feature-dir` の祖先にあるシンボリックリンクは検査しない。
- 末尾の区切り文字以外のパス要素（`.` や `..`）は正規化しない。`--feature-dir` が `current/.` のように `.` で終わるとき、最後の要素は `.` であり、current は FR5 の祖先として扱われ検査されない。
- これはこのリポジトリ自身のコードの修正であり、外部の修正版は存在しない。この修正そのものを恒久対応とし、暫定緩和策は設けない。
- 既存テストが固定している性質（記録自体のリンクの拒否、`reviews` 不在での `missing-round-record`、一時ファイルが残らないこと、ファイルモードの保持、読み取り専用ディレクトリでの不変）と、通常ファイル以外の記録を開く前に拒否する現状の挙動は、保つべき不変条件として扱う。
- plugin の version は手で上げない（main への push 時に Actions が patch を上げる）。

## Implementation Approach

### Architecture

UI・API・データベースは持たない。対象は CLI スクリプト `em-workflow/scripts/resolve-verified-findings.py` 1 本。

**Component Diagram:**
```
--feature-dir（末尾の / を除去、FR7）
  └─ feature ディレクトリ fd   O_DIRECTORY|O_NOFOLLOW（FR2）
       ├─ workflow.yaml / マッピングファイル   現状どおり読む
       └─ reviews dir_fd       O_DIRECTORY|O_NOFOLLOW（FR1, FR3）
            ├─ ラウンド記録の一覧取得
            ├─ ラウンド記録     lstat → O_RDONLY|O_NOFOLLOW → fstat → 上限付き読み込み（FR8）
            ├─ ファイルモードの取得
            ├─ 一時ファイル     O_CREAT|O_EXCL|O_NOFOLLOW
            └─ rename（src/dst とも reviews dir_fd 基準）／失敗時の一時ファイル削除
```

### Data Flow

```
--feature-dir → 末尾の / を除去 → feature ディレクトリを開く（リンクなら invalid-workflow）
  → workflow.yaml を読む → reviews を dir_fd 基準で開く（リンクなら invalid-round-record）
  → ラウンド記録を確認して読む（FR8）→ 一時ファイルに書く → rename で置き換える
```

### API Design

該当なし（コマンドライン・stdout の形は FR4 のとおり変えない）

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/merge-preflight.py`: AC1 / TS-1 の確認に使う。変更しない（NFR5）

**External Dependencies:**
- Python 標準ライブラリ、PyYAML（NFR1）

### File Structure

```
em-workflow/scripts/
└── resolve-verified-findings.py     # 修正対象
tests/
└── test_resolve_verified_findings.py  # テストを追加
```

## Declared Change Set

フィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上のフィーチャー固有のパスに加え、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/resolve-findings-parent-symlink/**`
- `test-docs/resolve-findings-parent-symlink/**`

`feature-docs/resolve-findings-parent-symlink/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` であり、本節はそれらを引用するだけでルールは再掲しない。

`test-docs/resolve-findings-parent-symlink/**` に含まれるもの: タスクごとのテスト記録 `test-docs/resolve-findings-parent-symlink/{T}.tests.yaml`。生成主体は `implement-phase.md` であり、本節は引用するだけでルールは再掲しない。

この 2 つの既定の項目は、SPEC 作成者が明示的に除外しない限り宣言に含まれる。記載が無いことを除外とはみなさない。除外は意図的な絞り込みである。

この宣言はスーパーセット（superset）の主張であり、検証時に観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致する必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/resolve-findings-parent-symlink/` ディレクトリを生成しないが、宣言された `test-docs/resolve-findings-parent-symlink/**` は依然として正しい。宣言されたパスが生成されなくても違反にはならない。

## Test Scenarios

テストは `tests/test_resolve_verified_findings.py` に置き、`python3 -m unittest tests.test_resolve_verified_findings` と `python3 -m unittest discover -s tests` で実行する。

### Unit Tests
該当なし

### Integration Tests
- [ ] TS-1: 一時リポジトリに `feature-docs/other`（`workflow.yaml`、`reviews/round1.yaml`）と `feature-docs/current`（`workflow.yaml`、`reviews -> ../other/reviews`）を作り、current で実行する。終了コード・stderr・other の tree スナップショット（既存の tree ヘルパー）を確かめ、other をコミットして `merge-preflight.py` を other に対して実行する。 - AC1 を満たす（`invalid-round-record`、other の `reviews` 配下が不変でファイルも増えない、`merge-preflight.py` は `unresolved_findings` で止まる）
- [ ] TS-2: 既存の `BROKEN_INPUTS` 表に「reviews がリポジトリ外ディレクトリへのリンク」「reviews がダングリングリンク」を `invalid-round-record` のケースとして加え、既存の snapshot 比較とリンク先の比較を行う。 - AC2 を満たす（`invalid-round-record`、feature ディレクトリ・リンク先とも不変）
- [ ] TS-3: `feature-docs/current` を `feature-docs/other` へのリンクにして実行し、`invalid-workflow` と other の不変を確かめる。 - AC3 を満たす
- [ ] TS-4: 子プロセスで、`yaml.safe_dump` を包んで呼ばれた時点で `current/reviews` を退避し同じ名前で `other/reviews` へのリンクに置き換えるラッパーを用意し、`runpy.run_path` でスクリプトを `__main__` として実行する（`-B`）。other の `reviews` 配下が不変で、一時ファイルが残らないことを確かめる。負荷をかけた競合は使わない。 - AC4 を満たす
- [ ] TS-5: 一時ディレクトリにリポジトリへのリンクを作り、そのリンクを経由したパスを `--feature-dir` に渡して、build_eligible の状態で書き換えが成功することを確かめる。 - AC5 を満たす（fixed に書き換わり exit 0）
- [ ] TS-6: 既存の AC-1〜AC-8 のテスト（記録自体のリンク、ディレクトリの記録、reviews 不在、読み取り専用ディレクトリ、ファイルモード保持、ファイルが増えないこと等）を含むスイート全体を実行する。 - AC6 を満たす（既存テストを削除・弱体化せずにすべて成功）

### Review
- [ ] TS-7: docstring の記載をレビューで確かめる。 - AC7 を満たす

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS-8: TS-3 と同じ構成（`feature-docs/current -> other`）で、`--feature-dir` に `current/` と `current//` をそれぞれ渡して実行し、`invalid-workflow`、stdout が空、stderr が 1 行であること、other の tree スナップショットが不変であることを確かめる。 - AC8 を満たす
- [ ] TS-9: リンクでない feature ディレクトリを使い、build_eligible の状態で `--feature-dir` に `DIR/` と `DIR//` を渡して実行し、exit 0、指摘が fixed に書き換わること、stdout の JSON が末尾の区切り文字なしで実行したときと同じであることを確かめる。 - AC9 を満たす
- [ ] TS-10: 子プロセスで `os.open` を包み、ラウンド記録の名前で呼ばれた時点で記録を退避し同じ名前で other の記録へのリンクに置き換えてから元の `os.open` を呼ぶラッパーを用意し、`runpy.run_path` でスクリプトを `__main__` として実行する（`-B`）。`invalid-round-record` と、other の記録が 1 バイトも変わらないことを確かめる。負荷をかけた競合は使わない。 - AC10 を満たす
- [ ] TS-11: `BROKEN_INPUTS` 表に「ラウンド記録が FIFO（`os.mkfifo`）」を `invalid-round-record` のケースとして加え、子プロセスの実行にタイムアウトを付けて、待ち続けずに失敗することを確かめる。 - AC10 を満たす

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** `--feature-dir` の最後の要素（末尾の区切り文字を除去した後）、`reviews`、ラウンド記録のシンボリックリンクを拒否する（FR1, FR2, FR7, FR8）。祖先は検査しない（FR5）。確認と書き込みは同じ dir_fd 基準で行う（FR3）
- **Data Protection:** stdout / stderr には検証済みの値とエラーコードだけを出し、パスやリンク先は出さない（NFR4）
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

新しいエラーコードは追加しない（FR4）。

| Code | Description | Exit | Output |
|------|-------------|------|--------|
| `invalid-workflow` | `--feature-dir` の最後の要素（末尾の区切り文字を除去した後）がシンボリックリンク（FR2, FR7）。`workflow.yaml` を読む前に失敗する | 1（`--feature-dir` が存在しない場合と同じ） | stdout は空、stderr は 1 行 |
| `invalid-round-record` | `reviews` がシンボリックリンク（FR1）、ラウンド記録が通常ファイル以外、または開く・読むのに失敗した（FR4, FR8） | 1 | stdout は空、stderr は 1 行 |
| `missing-round-record` | `reviews` が無い、または `reviews` がディレクトリでない通常ファイル（FR4） | 現状どおり | 現状どおり |

### Error Flow

```
エラー検出 → どのファイルも書かずに終了 → stderr にエラーコードを 1 行出す（パスやリンク先は出さない）
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete（FR6 の docstring）
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Implementation Phases (if applicable)

該当なし

## References

- 要件定義書: `feature-docs/resolve-findings-parent-symlink/REQUIREMENTS.md`
