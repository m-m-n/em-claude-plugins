# Feature: sca-per-project-scan-binding

## Overview

SCA 軸（`scan-dependencies.py scan`）で、変更されたマニフェスト / lockfile をプロジェクトディレクトリごとにグループ化し、1 プロジェクトにつき 1 スキャン単位を作る。npm / cargo / go のスキャナはそのプロジェクトディレクトリを cwd として起動し、束縛できないプロジェクトはルートレベルのスキャンに畳み込まず、パスを含まない `<ecosystem>_project_unbindable` で報告する。

要件の詳細は [REQUIREMENTS.md](REQUIREMENTS.md) を参照する。

## Objectives

- SCA 軸（scan-dependencies.py scan）の npm / cargo / go のスキャンが、変更されたマニフェスト / lockfile を含むプロジェクトディレクトリに束縛される
- 1 エコシステム内で別ディレクトリにある複数プロジェクトの変更が、プロジェクトごとに走査されるか、機械可読で安定した skip_reason で報告される
- findings の file ラベルが、実際に監査した依存集合のプロジェクトを指す

## User Stories

### US1: ネストしたプロジェクトの監査

モノレポを持つ em-workflow / em-review の利用者として、ネストしたプロジェクトの変更がそのプロジェクトの依存集合で監査されてほしい。finding の file ラベルが、実際に監査したプロジェクトを指すようにしたい。

**Acceptance Criteria:**
- [ ] AC-1: services/api/package.json と services/api/package-lock.json があり、changed_files が ["services/api/package.json"] のとき、npm スタブの cwd は project_root/services/api になる。finding の file は services/api/package.json になる。
- [ ] AC-2: services/api と services/web の両方に package.json と package-lock.json があり、両方の package.json が変更されたとき、npm は 2 回起動される。cwd はそれぞれのディレクトリで、各プロジェクトの findings がそのパスのラベルで返る。
- [ ] AC-8: 同じディレクトリを別表記で指す変更ファイルは 1 グループにまとまり、起動は 1 回になる。
- [ ] AC-15: 再現手順（モノレポで services/api/package.json を変更して scan を実行する、さらに services/web/package.json も同時に変更する）で、現象が起きないことをテストで検出できる。

### US2: 束縛できないプロジェクトの報告

em-workflow / em-review の利用者として、走査できなかったプロジェクトが機械可読で安定した skip_reason で報告されてほしい。

**Acceptance Criteria:**
- [ ] AC-3: package.json があって package-lock.json と npm-shrinkwrap.json のどちらもないプロジェクトでは npm を起動しない。結果は skipped: true、skip_reason: "npm_project_unbindable" になる。ルートのプロジェクトでも同じになる。
- [ ] AC-4: 束縛できる npm プロジェクトと束縛できない npm プロジェクトが混在すると、結果は skipped: true、skip_reason: "npm_project_unbindable" になる。束縛できたプロジェクトの findings は保持され、summary に npm は 1 回だけ現れる。
- [ ] AC-5: Cargo.toml だけがあって Cargo.lock がないプロジェクトでは cargo-audit を起動しない。skip_reason は cargo_project_unbindable になり、プロジェクトツリーは変化しない。
- [ ] AC-6: go.sum だけが変更され、同じディレクトリに go.mod があれば束縛して起動する。go.mod がなければ go_project_unbindable になる。
- [ ] AC-7: アンカーまたはマニフェストが別ディレクトリへ解決されるシンボリックリンクの場合、変更ファイルが絶対パスや '..' で外に出るパスの場合、解決できないパスの場合、選択したターゲットが削除されている場合は、いずれも <ecosystem>_project_unbindable になり、スキャナは起動されない。ルートのプロジェクトや祖先ディレクトリへフォールバックしない。
- [ ] AC-9: 束縛できない npm プロジェクトが 2 つあるとき、skip_reason は "npm_project_unbindable"（1 回）になる。エコシステムレベルの理由も重複しない。
- [ ] AC-12: 実行ファイルが PATH にない場合、skip_reason は <ecosystem>_tool_not_found の 1 回だけになり、束縛検査は行われない。

### US3: 祖先ワークスペースへの脱出防止とその他の維持事項

em-workflow / em-review の利用者として、スキャナがプロジェクトディレクトリの外のワークスペースを監査しないこと、pip の既存の挙動が保たれることを求める。

**Acceptance Criteria:**
- [ ] AC-10: npm ジョブの argv に --workspaces=false が含まれる。go ジョブの env で GOWORK=off、GOFLAGS=-mod=readonly になっている。
- [ ] AC-11: 2 つのディレクトリの pip マニフェスト / lockfile が変更されると、pip はグループごとに既存ルールで監査される。cwd は project_root のまま変わらない。既存の pip lockfile テストは通る。
- [ ] AC-13: build_scan_job と build_scan_jobs は、ファイルを開かず、プロセスも起動しない。
- [ ] AC-14: review-phase.md の axis-2 段落が複数プロジェクトの partial coverage を述べている。既存の固定文言を検査するテストは通る。
- [ ] AC-16: python3 -m unittest discover -s tests が成功する。

## Technical Requirements

### Functional Requirements

- **FR1:** プロジェクト単位のグループ化 — run_scan は、選択された各エコシステム（npm / cargo / go / pip）の変更ファイル（マニフェストと lockfile）を (エコシステム, 検証済みプロジェクト相対ディレクトリ) でグループ化する。ルートのディレクトリは `""` とする。同じディレクトリの別表記（重複や、同じディレクトリへ解決されるエイリアス）は 1 グループにまとめる。グループはプロジェクト相対パス順に処理する。
- **FR2:** グループ内のターゲット選択 — 各グループの走査ターゲットと finding の file ラベルは、そのグループの変更ファイルに既存の manifest_file_for の入力順ルールを適用して 1 つ選ぶ（pip は lockfile 優先、npm / cargo / go はマニフェスト優先）。
- **FR3:** 1 プロジェクトにつき 1 スキャン単位 — 1 つのプロジェクトグループにつき、1 つのスキャン単位を作る。npm / cargo / go のジョブの cwd はそのプロジェクトディレクトリとし、argv は `[実行ファイルの絶対パス] + registry の args` とする。pip の lockfile で同名の複数バージョンを分割実行する場合、1 スキャン単位の中で複数のサブプロセスを起動する形は維持する。
- **FR4:** 束縛可能条件（アンカーファイル） — npm / cargo / go のプロジェクトを束縛できるのは、そのディレクトリが project_root の下に収まり（realpath で判定）、エコシステムのアンカーと、必須の同階層マニフェストの両方を持つときだけとする。npm はアンカーが `npm-shrinkwrap.json` か `package-lock.json`（両方あれば `npm-shrinkwrap.json`）、マニフェストが `package.json`。cargo はアンカーが `Cargo.lock`、マニフェストが `Cargo.toml`。go はアンカーもマニフェストも `go.mod`。この条件はルートのプロジェクトにも同じく適用する。
- **FR5:** npm / cargo / go の厳格なパス検証 — npm / cargo / go について run_scan は、グループのすべての変更ファイル、プロジェクトディレクトリ、アンカー、必須マニフェストを検証する。検証内容は、project_root 配下に収まること（realpath）、絶対パスでないこと、`..` で外に出ないこと、解決時に例外が出ないこと。アンカーとマニフェストは、同じプロジェクトディレクトリの中に解決される通常ファイルでなければならない。別のディレクトリへ解決されるシンボリックリンクは束縛不可とする。選択したターゲットが削除されている場合や、ディレクトリが存在しない場合も束縛不可とする。祖先ディレクトリへのフォールバックはしない。
- **FR6:** 束縛できないプロジェクトの扱い — 束縛できないプロジェクトではスキャナを起動せず、ルートレベルのスキャンにも畳み込まない。理由として、パスを含まない `<ecosystem>_project_unbindable`（`npm_project_unbindable` / `cargo_project_unbindable` / `go_project_unbindable`）を加える。
- **FR7:** skip_reason の集約形式 — 集約した skip_reason は、パスを含まない理由を重複除去してソートし、`"+"` で連結した文字列とする。エコシステムレベルの理由（例: `<ecosystem>_tool_not_found`）は 1 回だけ現れる。
- **FR8:** プロジェクトをまたいだ部分カバレッジ — 1 エコシステムの中で 1 つでも未完了のプロジェクトがあれば、結果は `skipped: true` とし、集約した skip_reason を付ける。完了したプロジェクトの findings は保持する。summary に出すエコシステム名は重複させない。
- **FR9:** エコシステムレベルの検査順 — validate_ecosystem_entry と実行ファイルの解決はエコシステムごとに 1 回、プロジェクト単位の束縛より前に行う。エコシステムの検証に失敗した場合や実行ファイルが見つからない場合は、そのエコシステムのグループについて束縛検査もスキャナの起動もしない。
- **FR10:** pip のグループ化 — pip の変更ファイルもプロジェクトディレクトリごとにグループ化する。各グループのターゲットは既存ルール（lockfile 優先）で選ぶ。pip の argv / target の形式と cwd（project_root）は変えない。既存の lockfile 変換、固定の skip reason（`pip_lockfile_unconvertible` / `pip_direct_manifest_not_found` など）、プロジェクト内シンボリックリンクの許容、同名複数バージョンの分割実行はそのまま残す。pip の検証は既存のまま変えない。
- **FR11:** 祖先ワークスペースへの脱出防止 — `vuln-scanners.yaml` の npm の args に `--workspaces=false` を加える。go の子プロセス環境の固定値に `GOWORK=off` と `GOFLAGS=-mod=readonly` を入れる（GOFLAGS を空にする既存の固定値はこれに置き換える）。cargo には何も追加しない。
- **FR12:** build_scan_job / build_scan_jobs の純粋性 — build_scan_job と build_scan_jobs は、ファイルの読み書きもプロセスの起動もしない。束縛検査（アンカー、パス検証）は run_scan で行う。build_scan_jobs は、選択されたエコシステムのプロジェクトグループ 1 つにつき 1 ジョブを返す。
- **FR13:** review-phase.md の axis-2 段落の拡張 — `em-workflow/references/review-phase.md` の partial coverage 段落を追記だけで拡張し、1 エコシステム内の複数プロジェクトを扱うようにする。"partial coverage" という語は残し、既存の文言は書き換えない。
- **FR14:** 既存テストフィクスチャの更新 — lockfile を置かずに npm / cargo / go を起動している既存の run_scan フィクスチャは、マニフェストとアンカーを作る形に更新する。npm の argv を固定している既存テストも、`--workspaces=false` を含む形に更新する。

### Non-Functional Requirements

- **NFR1 - 読み取り専用:** scan はレビュー対象のプロジェクトツリーにファイルを作らず、変更もしない。lockfile の生成もしない。
- **NFR2 - 決定性:** 同じ入力に対しては、バイト単位で同一の結果 JSON を出す。入力全体の並べ替えに対する不変性は、集約した skip_reason 以外には求めない。
- **NFR3 - パスを含まない理由文字列:** skip_reason にはパスを含めない。
- **NFR4 - テストの依存:** テストモジュールが import するのは標準ライブラリだけとする。実在のスキャナは実行せず、一時 PATH に置いたスタブを使う。
- **NFR5 - 出力スキーマ:** scan の出力は review-output-schema.json に適合する。

## Implementation Approach

### Architecture

**System Architecture:**
```
scan-dependencies.py scan
└── run_scan
    ├── エコシステムの選択
    ├── 変更ファイルのグループ化 (エコシステム, 検証済みプロジェクト相対ディレクトリ)   [FR1, FR10]
    ├── エコシステムごとに 1 回: validate_ecosystem_entry + 実行ファイルの解決            [FR9]
    ├── プロジェクトグループごと（プロジェクト相対パス順）
    │   ├── 束縛検査: アンカー + 必須マニフェスト + パス検証（npm / cargo / go）          [FR4, FR5]
    │   ├── 束縛不可 → <ecosystem>_project_unbindable、スキャナは起動しない              [FR6]
    │   └── 束縛可 → build_scan_job（純粋）→ サブプロセス起動                           [FR2, FR3, FR12]
    └── 集約: skipped / skip_reason / findings / summary                                [FR7, FR8]
```

**Component Diagram:**
```
run_scan ──(検証済みプロジェクト相対ターゲット)──> build_scan_jobs / build_scan_job
   │                                                  │（ファイル I/O もプロセス起動もしない）
   │                                                  └─> job: argv / cwd / env
   ├── manifest_file_for（グループ内のターゲット選択）
   ├── validate_ecosystem_entry
   └── vuln-scanners.yaml（registry の args / env の固定値）
```

- build_scan_jobs は、ファイルシステムに触れずに字句上正規化したプロジェクト相対ディレクトリでグループ化する。realpath による検証済みのグループ化は run_scan が行う（A-11）。
- build_scan_job の npm / cargo / go の cwd は、project_root とターゲットのディレクトリを字句的に結合して得る。ルートのプロジェクトでは `str(project_root)` と一致させる（既存テストの `'/proj'` の固定値を保つ）。run_scan は検証済みのプロジェクト相対ターゲットを渡す（A-12）。

### Data Flow

```
changed_files → グループ化 → エコシステム検査 → 束縛検査 → ジョブ生成 → スキャナ起動 → findings / skip_reason の集約 → 結果 JSON
                                   │                 │
                                   └ tool_not_found  └ project_unbindable（スキャナは起動しない）
```

### API Design

#### CLI: `scan-dependencies.py scan`

**入力:**
- `changed_files`: 変更ファイルのリスト

**出力（エコシステム単位）:**
- `skipped`: 1 つでも未完了のプロジェクトがあれば `true`（FR8）
- `skip_reason`: パスを含まない理由を重複除去・ソートして `"+"` で連結した文字列（FR7、NFR3）
- `findings`: 完了したプロジェクトの findings。`file` はグループで選んだターゲット（FR2）
- `summary`: エコシステム名を重複させない（FR8）
- 出力全体は review-output-schema.json に適合する（NFR5）

**ジョブの形:**

| エコシステム | argv | cwd | env の固定値 |
|--------------|------|-----|--------------|
| npm | `[実行ファイルの絶対パス, audit, --json, --workspaces=false]` | プロジェクトディレクトリ | - |
| cargo | `[実行ファイルの絶対パス] + registry の args` | プロジェクトディレクトリ | - |
| go | `[実行ファイルの絶対パス] + registry の args` | プロジェクトディレクトリ | `GOWORK=off`、`GOFLAGS=-mod=readonly` |
| pip | 既存の形式のまま | project_root | 既存のまま |

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `manifest_file_for`: グループ内のターゲット / ラベル選択の既存ルール
- `validate_ecosystem_entry`: エコシステムレベルの検証
- `vuln-scanners.yaml`: npm の args（`[audit, --json, --workspaces=false]`）
- `em-workflow/references/review-phase.md`: axis-2 の partial coverage 段落
- review-output-schema.json: 出力スキーマ

**External Dependencies:**
- npm / cargo-audit / go / pip の各スキャナ: テストでは実行せず、一時 PATH に置いたスタブを使う（NFR4）

### File Structure

変更対象:

```
em-workflow/
├── scripts/
│   └── scan-dependencies.py      # run_scan / build_scan_job / build_scan_jobs / manifest_file_for
└── references/
    ├── review-phase.md           # axis-2 の partial coverage 段落（追記のみ）
    └── vuln-scanners.yaml        # npm の args
tests/                            # 既存フィクスチャの更新と再発検出テスト
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-per-project-scan-binding/**`
- `test-docs/sca-per-project-scan-binding/**`

`feature-docs/sca-per-project-scan-binding/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-per-project-scan-binding/**` covers `test-docs/sca-per-project-scan-binding/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-per-project-scan-binding/` directory at all; the declared
`test-docs/sca-per-project-scan-binding/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-7（AC-10, AC-13 / FR11, FR12）: build_scan_job の argv と env を検査する（npm の --workspaces=false、go の GOWORK / GOFLAGS）。open や subprocess をモックして純粋性を確認する。

### Integration Tests
- [ ] TS-1（AC-1, AC-15 / FR1, FR2, FR3, FR4）: ネストした npm プロジェクト 1 つを変更する。cwd を記録するスタブで、cwd とラベルを確認する。
- [ ] TS-2（AC-2, AC-15 / FR1, FR3）: services/api と services/web を同時に変更し、起動回数と各 cwd、findings のラベルを確認する。
- [ ] TS-3（AC-3, AC-5, AC-6 / FR4, FR6, NFR3）: npm / cargo / go それぞれでアンカーを欠いたプロジェクトを作り、未起動であることと <ecosystem>_project_unbindable を確認する。ルートのプロジェクトのケースも含める。
- [ ] TS-4（AC-4, AC-9 / FR7, FR8, NFR2, NFR3）: 束縛できるプロジェクトとできないプロジェクトを混在させ、skipped / skip_reason の重複除去 / findings の保持 / summary のエコシステム名の重複がないことを確認する。
- [ ] TS-5（AC-7 / FR5, FR6）: 外部を指すシンボリックリンクのアンカーやマニフェスト、絶対パス、'..' で外に出るパス、NUL を含むパス、削除済みのターゲット、存在しないディレクトリで、未起動であることと unbindable を確認する。
- [ ] TS-6（AC-8 / FR1）: 'a/package.json' と 'a/./package-lock.json' のような別表記で、1 グループ・1 回の起動になることを確認する。
- [ ] TS-8（AC-11 / FR10）: 2 ディレクトリの pip 変更で、グループごとの監査と cwd が project_root のままであることを確認する。既存の pip lockfile テストを全件通す。
- [ ] TS-9（AC-12 / FR7, FR9）: 実行ファイルがない状態で、tool_not_found が 1 回だけになり、束縛検査が行われないことを確認する。
- [ ] TS-10（AC-5 / NFR1）: スキャン前後で git status --porcelain が一致する（lockfile が生成されない）ことを確認する。
- [ ] TS-11（AC-14 / FR13）: review-phase.md の R2 セクションに、複数プロジェクトの partial coverage の記述と既存の固定文言の両方があることを確認する。
- [ ] TS-12（AC-16 / FR14, NFR4）: 既存フィクスチャ（マニフェストとアンカーを追加したもの）を含めてテスト全体を実行する。

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] yarn.lock / pnpm-lock.yaml しか持たないプロジェクト: npm を選択するがアンカーにならず、npm_project_unbindable になる（A-9）
- [ ] パス検証に失敗した変更ファイル（絶対パス、'..' で外に出るパス、解決できないパス）: どのグループにも属さず <ecosystem>_project_unbindable を加える。ルートや他の有効なグループには合流せず、他の有効なグループの走査も妨げない（A-10）
- [ ] npm-shrinkwrap.json と package-lock.json の両方がある: npm-shrinkwrap.json をアンカーにする（FR4）
- [ ] go.sum だけの変更: 同じディレクトリの go.mod で束縛する（AC-6）

### Performance Tests
該当なし

## Security Considerations

- **Input Validation:** npm / cargo / go の変更ファイル、プロジェクトディレクトリ、アンカー、必須マニフェストを FR5 のとおり検証する（realpath で project_root 配下、絶対パスでない、`..` で外に出ない、解決時に例外が出ない、アンカーとマニフェストは同じプロジェクトディレクトリ内の通常ファイル）。pip は既存の検証のまま（FR10）。
- **Data Protection:** scan はプロジェクトツリーにファイルを作らず、変更もしない（NFR1）。
- Authentication / Authorization / XSS / SQL Injection / CSRF: 該当なし

## Error Handling

### Error Codes

| skip_reason | 条件 | 結果 |
|-------------|------|------|
| `npm_project_unbindable` | npm プロジェクトが FR4 / FR5 の条件を満たさない | npm を起動しない。skipped: true |
| `cargo_project_unbindable` | cargo プロジェクトが FR4 / FR5 の条件を満たさない | cargo-audit を起動しない。skipped: true |
| `go_project_unbindable` | go プロジェクトが FR4 / FR5 の条件を満たさない | go のスキャナを起動しない。skipped: true |
| `<ecosystem>_tool_not_found` | 実行ファイルが PATH にない | 束縛検査をしない。理由は 1 回だけ現れる |
| `pip_lockfile_unconvertible` / `pip_direct_manifest_not_found` など | 既存の pip の条件 | 既存のまま（FR10） |

### Error Flow

```
エコシステム検査に失敗 → エコシステムレベルの理由を 1 回加える → そのエコシステムのグループは束縛検査もスキャナ起動もしない
束縛検査に失敗       → <ecosystem>_project_unbindable を加える → 他のグループは走査を続ける
集約                 → 理由を重複除去・ソートして "+" で連結 → 未完了があれば skipped: true、完了分の findings は保持
```

## Performance Optimization

該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete（FR13）
- [ ] Code review is completed
- [ ] 再現手順で現象が起きない（AC-15）
- [ ] 再発を検出するテストがある（AC-15）
- [ ] em-workflow の version は手で変更しない（A-13）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 要件定義書: [REQUIREMENTS.md](REQUIREMENTS.md)
- `em-workflow/scripts/scan-dependencies.py`: `build_scan_job`（1648 行付近）、`manifest_file_for`、`run_scan`、`build_scan_jobs`
- `em-workflow/references/review-phase.md`: axis-2 の partial coverage 段落
