# Feature: codex-guard-anon-fn-brace-close

## 概要

`codex-hook-interactive-guard.py` で、閉じ波括弧 `}` の前にセミコロンが無い匿名関数の本体があると、同じ `-c` 文字列の対話起動を見逃す。この退行を直し、匿名関数の本体の中にある単独の `}` は、語が残っていても単純コマンドを確定してから群を閉じるようにする。

## 目的

- 閉じ波括弧 `}` の前にセミコロンが無い匿名関数の本体があっても、同じ -c 文字列の対話起動を codex-hook-interactive-guard が deny するように戻す。feature codex-guard-anon-brace-forms の変更で入った、見逃し側の退行を直す。

## 受け入れ条件

- [ ] AC1: 2 つのコピーの両方で `zsh -c 'python3 -i; function { : }'` が deny になる。（FR1, FR7, FR8）
- [ ] AC2: 2 つのコピーの両方で `zsh -c 'function { : }; python3 -i'` が deny になる。（FR1, FR7, FR8）
- [ ] AC3: 2 つのコピーの両方で `zsh -c 'function { python3 -i }'` が deny になる。（FR1, FR3, FR7, FR8）
- [ ] AC4: `zsh -c 'function { { : } }; python3 -i'` が deny になる。（FR2）
- [ ] AC5: `}` の前にセミコロンが無い匿名関数の本体と、その中の入れ子の群のコマンドは、本体の接続を受け継ぐ。`zsh -c 'echo x | function { python3 }'`、`zsh -c '< /dev/null function { python3 }'`、`zsh -c 'echo x | function { { python3 } }'` は silent になる。（FR2, FR3）
- [ ] AC6: 引用符で囲んだ `}` は群を閉じない。`zsh -c "echo x | function { echo '}'; python3 }"` は silent になる。（FR4）
- [ ] AC7: 既存の CASES がすべて通る。最上位のただの `{ python3 }` を silent とするケースもそのまま通る。（FR5, NFR3）
- [ ] AC8: `python3 -m unittest tests.test_codex_hook_interactive_guard` が通る。通るテストには TestCopies（2 つのコピーが同一）、TestGuardDocumentation、TestMalformedAndDeepInput、TestNoRecursion、TestStaticConstraints が含まれる。（FR6, FR7, NFR1, NFR2）
- [ ] AC9: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` が通る。（NFR3, NFR4）

## 技術要件

### 機能要件

- **FR1: 匿名関数の本体を閉じる `}`** — 最内の開いている群が匿名関数の本体のとき、単独で裸の `}` は群を閉じる。単純コマンドに語が残っていても閉じ、その単純コマンドを先に本体の中のコマンドとして確定させる。対象の形は `function {`、`function () {`、`() {` のどれでもよい。
- **FR2: 匿名関数の本体の中に入れ子になった `{` 群** — 最内の開いている群が `{` 群で、それを囲む群の中に匿名関数の本体があるとき、単独で裸の `}` は語が残っていても FR1 と同じ閉じ方をする。間に何段の群があってもよく、`(` 群をはさむ場合も含む。この `{` 群には、匿名関数の本体の中にある関数定義の本体も含む。
- **FR3: 確定したコマンドの所属と接続** — FR1 / FR2 で確定したコマンドは、閉じる群に属する。そのコマンドは、群の接続を、入れ子の群を通して届く分も含めて受け継ぐ。接続とは、パイプ、匿名関数の頭部にある入力リダイレクト、閉じた後の入力リダイレクトのこと。匿名関数の本体を閉じた後に続く語は、従来どおり匿名関数の引数として読む。
- **FR4: 対象外の `}`** — 次の `}` は閉じ括弧として読まない。引用符・エスケープ・展開を含む `}`、語の一部になっている `}`（`a}` など）、リダイレクト先の語になった `}`。
- **FR5: 匿名関数の本体の外の群** — 匿名関数の本体の中に入っていない `{` 群は、語が残っている `}` では従来どおり閉じない。たとえば最上位のただの `{ : }` や、匿名関数の外にある関数定義の本体 `f() { : }`。その文字列は判定不能のまま。
- **FR6: docstring** — モジュールの docstring の手順 4 に、FR1・FR2・FR5 の閉じ方を書く。
- **FR7: 2 つのコピー** — `em-workflow/scripts/codex-hook-interactive-guard.py` と `em-review/scripts/codex-hook-interactive-guard.py` は、同じ変更の中で一緒に直す。2 つはバイト単位で同一に保つ。
- **FR8: 退行を検出するテスト** — `tests/test_codex_hook_interactive_guard.py` の `CASES` に次の 3 つを deny として追加する。`zsh -c 'python3 -i; function { : }'`、`zsh -c 'function { : }; python3 -i'`、`zsh -c 'function { python3 -i }'`。

### 非機能要件

- **NFR1: 線形時間** — `{` 群が匿名関数の本体の中にあるかどうかの判定は、`}` 1 つあたり定数時間で行う。囲む群を祖先へたどって調べることはしない。構文解析全体を、文字列の長さに対して線形に保つ。
- **NFR2: 依存と副作用** — 標準ライブラリだけを使う。ファイル・ネットワーク・子プロセスには触れない。
- **NFR3: fail-open の維持** — 判定できないものは通す、という方針は変えない。silent であるべきものが新しく deny になる誤爆を生まない。
- **NFR4: version** — `plugin.json` と `marketplace.json` の version には触らない。

## 前提

- **as-1**: 閉じる前に残っていた語は、閉じる群の中の単純コマンドとして確定させる。そのコマンドは、`;` で区切られた場合と同じように判定と接続を受ける。
- **as-2**: 最上位のただの `{ : }` と、匿名関数の外の関数定義の本体は、従来どおり判定不能のままにする。既存ケース `{ python3 }` の silent は維持する。
- **as-3**: 引用符・エスケープ・展開を含む `}`、語の一部の `}`、リダイレクト先の `}` は、従来どおり閉じ括弧として扱わない。
- **as-4**: TS4 から TS14 は `CASES`、または既存のテストクラスに追加する推奨のケースとする。完了の定義で必須なのは TS1 から TS3 の 3 つ。

## 実装方針

### 対象ファイル

```
em-workflow/scripts/codex-hook-interactive-guard.py   # FR1-FR6
em-review/scripts/codex-hook-interactive-guard.py     # FR7（em-workflow 側とバイト単位で同一）
tests/test_codex_hook_interactive_guard.py            # FR8
```

### 依存

- 外部依存: なし（標準ライブラリだけ。NFR2）

## Declared Change Set

ここには手書きの一覧を置かない。機能固有のパスは create-plan で、`workflow.yaml` の各タスクの `files` から導く（`references/phases/create-plan-phase.md`）。

機能固有のパスに加えて、ワークフローが生成する次の 2 つを宣言に含める。

- `feature-docs/codex-guard-anon-fn-brace-close/**`
- `test-docs/codex-guard-anon-fn-brace-close/**`

`feature-docs/codex-guard-anon-fn-brace-close/**` は `SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml` を含む。これらは各フェーズの文書と `references/phase-state.md` が生成・所有する。

`test-docs/codex-guard-anon-fn-brace-close/**` はタスクごとのテスト記録 `test-docs/codex-guard-anon-fn-brace-close/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。

この宣言は上位集合の宣言で、検証時に実際に変わったパスが宣言の中に収まっていればよい。宣言したパスが作られなくても違反ではない。

## テストシナリオ

### 単体テスト

完了の定義で必須（FR8）:

- [ ] TS1: `zsh -c 'python3 -i; function { : }'` - deny（AC1）
- [ ] TS2: `zsh -c 'function { : }; python3 -i'` - deny（AC2）
- [ ] TS3: `zsh -c 'function { python3 -i }'` - deny（AC3）

推奨（as-4）:

- [ ] TS4: `zsh -c 'function () { python3 -i }'` - deny（AC3）
- [ ] TS5: `zsh -c '() { python3 -i }'` - deny（AC3）
- [ ] TS6: `zsh -c 'function { python3 -i } arg'` - deny（AC3）
- [ ] TS7: `zsh -c 'function { { : } }; python3 -i'` - deny（AC4）
- [ ] TS8: `zsh -c 'function { ( { python3 -i } ) }'` - deny（AC4）
- [ ] TS9: `zsh -c 'echo x | function { python3 }'` - silent（AC5）
- [ ] TS10: `zsh -c '< /dev/null function { python3 }'` - silent（AC5）
- [ ] TS11: `zsh -c 'echo x | function { { python3 } }'` - silent（AC5）
- [ ] TS12: `zsh -c "echo x | function { echo '}'; python3 }"` - silent（AC6）
- [ ] TS13: `{ python3 }`（既存ケース `tests/test_codex_hook_interactive_guard.py:443`）- silent のまま通る（AC7）

### 性能テスト

- [ ] TS14: 深く入れ子にした `function {` + ` { :` を N 回 + ` }` を N 回 の文字列が、既存の深い入力のテストと同じ時間の上限で読み終わる（AC8）

### 回帰

- [ ] AC8: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- [ ] AC9: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`

## 完了条件

- [ ] FR1 から FR8 がすべて実装され、テストされている
- [ ] TS1 から TS3 が `CASES` に deny として入っている
- [ ] AC1 から AC9 がすべて満たされている
- [ ] 2 つのコピーがバイト単位で同一

## 未解決事項

なし
