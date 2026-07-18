# License Generation Procedure (SSOT)

Consumed by `skills/gen-license/SKILL.md` (`/em-workflow:gen-license`).
Compatibility knowledge lives in `references/license-compat.md` — read it
first and evaluate against it; do not restate or reinvent its rules.

All user-facing output is Japanese. License texts stay in English.

## Arguments

- `--analyze-only`: analyze and report only; never write files.
- A license id (e.g. `MIT`, `GPL-3.0-only`): user-specified target license.
  Still run the compatibility check and warn on conflict before writing.

## Phase 1 — Detect

1. Project type(s) from dependency manifests: `go.mod`, `package.json`,
   `Cargo.toml`, `pyproject.toml` / `requirements.txt`, `composer.json`,
   `Gemfile`, `build.gradle` / `pom.xml`. Polyglot → analyze all.
2. Existing project license per license-compat.md detection. When a LICENSE
   file exists and generation would replace it → AskUserQuestion:
   上書きする / バックアップ（LICENSE.bak）して作成 / 中止。

## Phase 2 — Dependency licenses

- Prefer tooling over guessing: `npm view {pkg} license` or
  `node_modules/{pkg}/package.json`; `cargo metadata` の
  `.packages[].license`; `go-licenses` or the module's LICENSE in
  `$(go env GOMODCACHE)`; `pip show {pkg}` / `importlib.metadata`;
  `vendor/{vendor}/{pkg}/composer.json`. Fall back to the registry page or
  WebSearch. Record failures as `unknown` — never assume.
- Direct dependencies are mandatory; include transitive ones when tooling
  reports them cheaply.
- Scan for vendored/copied code: `vendor/`, `third_party/`, LICENSE files in
  subdirectories, `SPDX-License-Identifier` / `Copyright (c)` headers.

## Phase 3 — Determine the license

- Evaluate the full dependency set against license-compat.md.
- Default preference: MIT when every dependency permits it.
- Copyleft dependencies force the project license (GPL family) →
  AskUserQuestion: そのライセンスを採用する / 依存を見直す / 中止。
- Multiple valid options, or unknowns remaining → AskUserQuestion with the
  candidates and a one-line trade-off each.

## Phase 4 — Copyright information

- Year: `date +%Y`. Holder: `git config user.name`（fallback: first-commit
  author）. Ambiguous or missing → AskUserQuestion.

## Phase 5 — Write（--analyze-only ではスキップ）

- Final confirmation via AskUserQuestion: 生成する / プレビュー / 中止。
- Write `LICENSE` with the official text: MIT from the template below;
  Apache-2.0 from https://www.apache.org/licenses/LICENSE-2.0.txt; GPL-3.0
  from https://www.gnu.org/licenses/gpl-3.0.txt; others from
  https://choosealicense.com/licenses/ or spdx.org.
- Recommend in the report (do NOT edit them yourself): the manifest license
  field（package.json `"license"`, Cargo.toml `[package] license`,
  pyproject `[project] license`, composer.json `"license"`）and a README
  License section.

## Phase 6 — Workflow sync

If any `feature-docs/*/workflow.yaml` has a `project.license` field that now
differs from the written LICENSE, update that field to the new SPDX id and
mention the update in the report.

## Report (Japanese)

依存ライセンスの集計 / 採用ライセンスと理由 / 生成・変更したファイル /
`unknown` のまま残った依存（あれば手動確認を促す）/ 推奨フォローアップ。
`--analyze-only` では「LICENSE を生成するにはフラグを外して再実行」を添える。

## MIT template

```
MIT License

Copyright (c) {year} {copyright holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
