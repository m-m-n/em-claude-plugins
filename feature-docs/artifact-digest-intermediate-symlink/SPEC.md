# Feature: artifact-digest-intermediate-symlink

## Overview

`em-workflow/scripts/artifact-digest.py` が、パスのどの要素もシンボリックリンクを辿らずに開くようにする。途中の要素がシンボリックリンクのパスは `not_a_regular_file` になり、ダイジェストを返さない。要件の詳細は `feature-docs/artifact-digest-intermediate-symlink/REQUIREMENTS.md` を参照する。

## Objectives

- artifact-digest.py は、どこかの要素にシンボリックリンクを含むパスに対して、決してダイジェストを返さない。これで TM-6 の「シンボリックリンクを辿らない」保護が完全になる。
- 再現コマンド `python3 -B em-workflow/scripts/artifact-digest.py /proc/self/root/etc/hosts /etc/hosts` は、同じダイジェストを 2 つ返さなくなる。1 つ目の要素は `not_a_regular_file`、終了コードは 1 になる。

## User Stories

### US1: 途中の要素のシンボリックリンクを拒否する
オーケストレーターとして、途中の要素にシンボリックリンクを含むパスを渡したとき `not_a_regular_file` を受け取りたい。

**Acceptance Criteria:**
- [ ] AC1
- [ ] AC2
- [ ] AC3
- [ ] AC5

### US2: 既存の結果を保つ
オーケストレーターとして、シンボリックリンクを含まないパスでは今までと同じ結果を受け取りたい。

**Acceptance Criteria:**
- [ ] AC4
- [ ] AC8

### US3: 機能が無い環境で止まる
オーケストレーターとして、必要な機能が無い環境では配列を受け取らず、終了コード 2 を受け取りたい。

**Acceptance Criteria:**
- [ ] AC6
- [ ] AC7

## Technical Requirements

### Functional Requirements
- **FR1:** シンボリックリンクを辿らずにパスを走査する。各引数を要素ごとに開く。相対パスはカレントディレクトリから、絶対パスは `/` から始める。途中の各要素は、直前のディレクトリの記述子を基準に `O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC` で開く。最後の要素は、最後のディレクトリの記述子を基準に `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC` で開く。成否の判定に、パス全体の解決は使わない。
- **FR2:** 途中の要素のシンボリックリンクは `not_a_regular_file`。途中のいずれかの要素がシンボリックリンクなら、その引数の要素は `{path, sha256: null, error: not_a_regular_file}` になる。リンク先がディレクトリでもファイルでも、リンク切れでも、ループでも同じ。リンク先のダイジェストは標準出力に一切現れない。他の引数は引き続きハッシュし、終了コードは 1。
- **FR3:** 既存の結果は変えない。要素の実体が無ければ `missing`。途中の要素が存在するがディレクトリでもシンボリックリンクでもなければ `missing`。空の引数は `missing`。最後の要素がディレクトリ・シンボリックリンク・FIFO・デバイス・ソケットなら `not_a_regular_file`。権限エラー・I/O エラーは `unreadable`（途中のディレクトリに検索権限が無い場合を含む）。途中の要素を開いて `ENOTDIR` か `ELOOP` で失敗したときは、その要素の種類をシンボリックリンクを辿らずに調べてから、エラーを決める。
- **FR4:** パスの書き方の扱い。空の要素（`a//b`）と `.` は飛ばす。`..` は引き続き許可する。`..` も `O_DIRECTORY|O_NOFOLLOW` で開くため、実ディレクトリ構造を辿る。拒否するのはシンボリックリンクだけ。末尾の `/` は、最後の要素がディレクトリであることを求める。`a.md/` は `missing`、`dir/` は `not_a_regular_file`。パスは今と同じく、渡されたとおりに出力に返す。
- **FR5:** 確認と読み込みの間の差し替えに対して安全。通常ファイルの判定は引き続き、実際に読む記述子への `fstat` で行う。走査中に途中または最後の要素が差し替えられても、結果はエラーになるだけ。シンボリックリンク経由で到達した内容のダイジェストにはならず、処理がブロックすることもない。
- **FR6:** 必要な機能が無い環境では止まる。スクリプトは、引数を処理する前に確認する。`os.open` が `dir_fd` に対応していない（`os.open not in os.supports_dir_fd`）か、`os.O_DIRECTORY` または `os.O_NOFOLLOW` が無い場合、パス全体の解決には戻らない。欠けている機能を名指しするメッセージを標準エラー出力に書き、配列を出さず、終了コード 2 で終える。
- **FR7:** 文書。artifact-digest.py の docstring で、エラートークン一覧の `not_a_regular_file` の行と「Entry kinds」の段落に、パスのどの要素もシンボリックリンクを辿らないことを書く。終了コード 2 の行に、環境が必要な機能を持たない場合を加える。`OPEN_FLAGS` のコメントも同様に更新する。`em-workflow/references/artifact-digest.md` の「Calculation」節で、`not_a_regular_file` の項目に「or a path any of whose components is a symlink」を加え、終了コード `2` の項目に環境の機能不足を加える。ディスパッチ箇所の節では、この文言を繰り返さない。

### Non-Functional Requirements
- **NFR1 - 標準ライブラリのみ・子プロセスなし:** 標準ライブラリだけを使い、子プロセスや外部コマンドを起動しない。メモリ使用量は分割読み込みにより上限を保つ。既存の AC-7 のテストは通り続ける。
- **NFR2 - ディレクトリ記述子の解放:** 走査中に開いたディレクトリの記述子は、成功・エラーのどの経路でもすべて閉じる。
- **NFR3 - CLI と出力の互換性:** CLI、出力の形、エラートークンの集合、終了コードの意味は変えない。ただし終了コード 2 は、必要な機能を持たない環境の場合も表す。`tests/test_artifact_digest_script.py`、`tests/test_artifact_digest_docs.py`、`tests/test_digest_contract_alignment.py` の既存テストは、修正なしですべて通る。
- **NFR4 - プラグインのバージョンを編集しない:** プラグインのバージョンは編集しない。patch の引き上げは GitHub Actions のワークフローが行う。

## Assumptions

- A1: 絶対パスの引数も、同じ「シンボリックリンクを辿らない」規則で `/` から走査する。どこかにシンボリックリンクを含む絶対パスは `not_a_regular_file` になる。例: `/proc/self/...`、macOS でシンボリックリンクの `/var` の下にある一時ディレクトリ。
- A2: 存在するがディレクトリでもシンボリックリンクでもない途中の要素は、引き続き `missing`。
- A3: 途中の要素のシンボリックリンクは、リンク切れ・ループ・ファイルへのリンク・ディレクトリへのリンクのどれでも `not_a_regular_file`。
- A4: `..` の要素は引き続き許可し、実ディレクトリ構造上で辿る。`..` で開始ディレクトリより上に出ることは対象外。
- A5: 必要な機能が無い環境では、終了コード 2 で閉じた側に失敗する。パス全体に対する従来の確認には決して戻らない。
- A6: `feature-docs/worker-digest-ownership/THREAT-MODEL.md` は編集しない。
- A7: プラグインのバージョンは編集しない。

## Implementation Approach

### Architecture

**処理の順序:**
```
起動
 └─ 機能の確認（FR6）
      os.open in os.supports_dir_fd / os.O_DIRECTORY / os.O_NOFOLLOW
      欠けていれば: 標準エラー出力にメッセージ、配列を出さず、終了コード 2
 └─ 引数ごと
      空の引数 → missing（FR3）
      開始: 絶対パスは '/'、相対パスはカレントディレクトリ（FR1）
      要素に分ける。空の要素と '.' は飛ばす（FR4）
      途中の要素: 直前のディレクトリ記述子を基準に
                  O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC で開く
                  ENOTDIR / ELOOP → 種類をリンクを辿らずに調べてエラーを決める（FR2, FR3）
      最後の要素: 最後のディレクトリ記述子を基準に
                  O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC で開く
                  末尾 '/' はディレクトリを要求（FR4）
                  開いた記述子への fstat で通常ファイルを判定し、分割読み込みでハッシュ（FR5, NFR1）
      開いたディレクトリ記述子はどの経路でも閉じる（NFR2）
 └─ 配列を標準出力へ。エラーがあれば終了コード 1（FR2）
```

**Component Diagram:**
```
em-workflow/scripts/artifact-digest.py   パスの走査とハッシュ（FR1〜FR6）、docstring・OPEN_FLAGS のコメント（FR7）
em-workflow/references/artifact-digest.md 「Calculation」節（FR7）
```

### Data Flow

```
引数 → 機能の確認 → 要素ごとの走査（dir_fd 基準） → 最後の要素の fstat → 分割読み込み → sha256
                                ↓ シンボリックリンク / 実体なし / 権限エラー
                              エラートークン（not_a_regular_file / missing / unreadable）
```

### API Design

CLI・出力の形・エラートークンの集合は変えない（NFR3）。終了コード 2 の意味に、必要な機能を持たない環境を加える（FR6）。

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/artifact-digest.md`: 「Calculation」節がこのスクリプトの計算と終了コードを記す（FR7）

**External Dependencies:**
- Python 標準ライブラリのみ（NFR1）

### File Structure

```
em-workflow/
├── scripts/
│   └── artifact-digest.py       # 走査の変更、docstring、OPEN_FLAGS のコメント
└── references/
    └── artifact-digest.md       # 「Calculation」節
tests/
└── test_artifact_digest_script.py  # AC1 などのテスト
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/artifact-digest-intermediate-symlink/**`
- `test-docs/artifact-digest-intermediate-symlink/**`

`feature-docs/artifact-digest-intermediate-symlink/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/artifact-digest-intermediate-symlink/**` covers `test-docs/artifact-digest-intermediate-symlink/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/artifact-digest-intermediate-symlink/` directory at all; the declared
`test-docs/artifact-digest-intermediate-symlink/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1（AC1 / FR1, FR2）: `tmp/outside/a.md` があり、`tmp/work/link` が `../outside` を指す。カレントディレクトリ `tmp/work` で `link/a.md` を実行する - `[{path:'link/a.md', sha256:null, error:'not_a_regular_file'}]`、終了コード 1、標準出力に `ABC_DIGEST` が無い。
- [ ] TS2（AC2 / FR2）: 各ケースを subTest で確かめる。リンクを通る絶対パス、`sub/link/x/a.md`、`dangling/a.md`、通常ファイルを指す `file-link` での `file-link/x`、`loop-a/x` - どれも `not_a_regular_file`、終了コード 1。同じ呼び出しに並べた通常ファイルは引き続きハッシュされる。
- [ ] TS3（AC3 / FR2）: `/proc/self/root/etc/hosts` と `/etc/hosts` を一緒に実行する - 要素 0 が `not_a_regular_file`、要素 1 が sha256、終了コード 1。`os.path.islink('/proc/self')` と `/etc/hosts` の存在で skipUnless する。
- [ ] TS4（AC4 / FR3, FR4）: 末尾スラッシュと権限のケース - `a.md/` は `missing`、`dir/` は `not_a_regular_file`、`link-to-dir/` は `not_a_regular_file`、mode 0o000 の途中ディレクトリは `unreadable`（root で実行するとき、またはアクセスが通ってしまうときは飛ばす）。既存の AC-2 と AC-5 のケースは修正なしで通る。
- [ ] TS5（AC5 / FR5）: 差し替えドライバーが `os.open` を置き換える。呼び出しが `O_DIRECTORY` と `dir_fd` を伴うとき、ドライバーはまず名前のディレクトリを外のディレクトリへのシンボリックリンクに差し替え、それから本物の `os.open` を呼ぶ - `not_a_regular_file`、外のファイルのダイジェストは無い。
- [ ] TS6（AC6 / FR6）: `os.O_NOFOLLOW` の削除、`os.O_DIRECTORY` の削除、`os.supports_dir_fd` から `os.open` を除く、の 3 通りの変更のあと、runpy でスクリプトを実行する - 各 subTest で終了コード 2、標準出力が空、標準エラー出力が空でない。
- [ ] TS7（AC7 / FR7, NFR3）: 見出しでテキストを切り出して文書のアサーションを足す - artifact-digest.md の「Calculation」で、`not_a_regular_file` がどの要素のシンボリックリンクも含むと書かれている。docstring が「辿らない」を最後の要素に限定していない。

### Integration Tests
- [ ] AC7: `tests/test_artifact_digest_docs.py`、`tests/test_digest_contract_alignment.py`、`check-plugin-invariants.py` が通る。
- [ ] AC8（NFR1, NFR2, NFR3）: `python3 -m unittest discover -s tests` が通る。AC-7 の標準ライブラリ・子プロセスなしのテストを含む。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] 途中の要素のリンク切れ・ループ・ファイルへのリンク（TS2）
- [ ] 末尾 `/`: `a.md/` は `missing`、`dir/` と `link-to-dir/` は `not_a_regular_file`（TS4）
- [ ] `sub/../sub/a.md`、`sub//a.md`、`./sub/a.md`、一時ディレクトリの絶対パスにはダイジェストが返る（AC4）
- [ ] 空の引数は `missing`、`plain.md/child.md` と `no-such-dir/a.md` は `missing`（AC4）

### Performance Tests
該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** 該当なし
- **Input Validation:** パスのどの要素もシンボリックリンクを辿らない（FR1, FR2）。確認と読み込みの間の差し替えはエラーになるだけ（FR5）。必要な機能が無い環境ではパス全体の解決に戻らない（FR6）。
- **Data Protection:** シンボリックリンク経由で到達した内容のダイジェストは標準出力に現れない（FR2, FR5）。
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Token | 条件 | 終了コード |
|-------|------|------------|
| `not_a_regular_file` | 途中のいずれかの要素がシンボリックリンク（FR2）。最後の要素がディレクトリ・シンボリックリンク・FIFO・デバイス・ソケット（FR3）。末尾 `/` でディレクトリを指す（FR4） | 1 |
| `missing` | 要素の実体が無い。途中の要素がディレクトリでもシンボリックリンクでもない。空の引数。末尾 `/` で通常ファイルを指す（FR3, FR4） | 1 |
| `unreadable` | 権限エラー・I/O エラー（途中のディレクトリに検索権限が無い場合を含む）（FR3） | 1 |
| （配列なし） | `os.open` が `dir_fd` に未対応、または `os.O_DIRECTORY` / `os.O_NOFOLLOW` が無い（FR6） | 2 |

### Error Flow

```
途中の要素を開いて失敗 → ENOTDIR / ELOOP ならリンクを辿らずに種類を調べる → エラートークンを決める → 他の引数の処理を続ける
```

## Performance Optimization

### Performance Goals
- メモリ使用量は分割読み込みにより上限を保つ（NFR1）

## Success Criteria

- [ ] AC1〜AC8 をすべて満たす
- [ ] FR7 の文書更新が済んでいる
- [ ] NFR3 に挙げた既存テストが修正なしで通る

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: `feature-docs/artifact-digest-intermediate-symlink/REQUIREMENTS.md`
- `em-workflow/scripts/artifact-digest.py`
- `em-workflow/references/artifact-digest.md`
- `feature-docs/worker-digest-ownership/THREAT-MODEL.md`
