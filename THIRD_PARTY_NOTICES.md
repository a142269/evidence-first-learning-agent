# Third-Party Notices & Asset Provenance Inventory

> **Machine-generated inventory — not legal advice.** This file lists third-party components and
> bundled media that are declared, pinned, installed or checked into this repository, with the
> license **as declared in package metadata** and the provenance evidence that exists in-repo.
> It does not ship license texts, give a legal opinion, or verify that any declared license is
> the correct one. License decisions for redistribution require human/legal review.

| Field | Value |
|-------|-------|
| Generated | 2026-10-18 (Asia/Shanghai) |
| Generator | `output/license-audit-20261018/collect_python.py`, `collect_frontend.py`, `scan_assets.py`, `build_notices.py` |
| Raw data | `output/license-audit-20261018/{python_deps,frontend_deps,assets}.json` (gitignored) |
| Method / caveats | [`output/license-audit-20261018/report.md`](output/license-audit-20261018/report.md) (gitignored) |
| Python env audited | `<project python>` (Python 3.12.15) |
| Network use | **None.** No npm/PyPI queries, no model calls. |

## 0. Scope and headline counts

* **Project license:** MIT (`LICENSE`, Copyright (c) 2026 智学领航 contributors).
* This inventory covers: Python dependencies (pinned + installed), npm dependencies (web frontend
  and Electron desktop shell), and media/bundle files checked into or present in the working tree.
* It does **not** cover: course/knowledge-base text originality, generated LLM content, online
  service terms (iFlytek Spark/Embedding/imagev3/TTS, Microsoft Edge TTS, OpenAI-compatible
  endpoints), or trademark/logo permissions.

| Inventory | Count | Notes |
|-----------|-------|-------|
| Python components in scope | 151 | 145 pinned in `requirements.lock.txt` + 6 declared/expected but not pinned |
| Python runtime components | 121 | 40 direct + 81 transitive; lockfile versions matched installed metadata exactly |
| Python dev/test-only components | 24 | pytest/ruff/mypy/pre-commit tooling chain — not shipped at runtime |
| Python **UNKNOWN** license | **5** | `chromadb`, `mcp`, `passlib`, `python-jose`, `sentence-transformers` — all five are *not installed*; version-only declarations, no metadata available offline |
| Frontend (web) npm components | 95 | 65 runtime + 30 dev-only (from `frontend/package-lock.json`, 178 entries incl. optional/platform packages, lockfileVersion 3) |
| Desktop (Electron) npm components | 285 | 19 runtime + 266 dev-only (root `package-lock.json`, 453 non-root entries) |
| npm **UNKNOWN** license | **0** | every lock entry has a `license` field (0 version mismatches vs installed tree) |
| Tracked media files (repo) | 126 files / 106 distinct contents | 125 of 126 sit in asset families with **no provenance file**; the other is a 0-byte `.docx` placeholder under `backend/app/templates/reports/` |
| Tracked JS/CSS bundles w/o provenance | 32 files | 30 stale React build files under `frontend/public/assets/` + 2 files of a source-less React build under `frontend/public/integrated-map/assets/` |
| Third-party LICENSE/NOTICE files in `frontend/dist` | **0** | `frontend/dist` is gitignored build output (~99.93 MB) shipped inside the desktop backend bundle by `backend.spec` |

## 1. Python dependencies

Source of truth: `requirements.txt` (47 direct), `requirements.lock.txt` (145 pinned),
`requirements-mcp.txt` (`mcp==2.3.0` optional), `pyproject.toml` (`python-jose`, `passlib`),
installed metadata queried with `importlib.metadata` (no network). Version = installed version;
every lock version matched the installed version (0 mismatches). `torch` is installed but is
**not** in `requirements.txt`/the lock: users provide it separately, and `backend.spec` excludes it.

### 1.1 Runtime dependencies — direct (declared in requirements.txt)

| Package | Version | License (as declared) | Source | Notes |
|---------|---------|----------------------|--------|-------|
| aiohttp | 3.14.5 | Apache-2.0 AND MIT | License-Expression | direct |
| alembic | 1.20.0 | MIT | License-Expression | direct |
| celery | 5.6.3 | BSD-3-Clause | license-field | direct |
| certifi | 2026.7.22 | MPL-2.0 | classifier | direct |
| edge-tts | 7.3.1 | LGPL-3.0 | classifier | direct; **copyleft (LGPL)** |
| fastapi | 0.143.3 | MIT | License-Expression | direct |
| httpx | 0.28.1 | BSD (classifier does not specify 2/3-clause) | classifier | direct; listed under the test section but also a runtime transitive of langchain-core |
| imageio-ffmpeg | 0.6.0 | BSD (classifier does not specify 2/3-clause) | classifier | direct |
| jieba | 0.42.1 | MIT | classifier | direct |
| Jinja2 | 3.1.6 | BSD (classifier does not specify 2/3-clause) | classifier | direct |
| langchain | 1.4.6 | MIT | classifier | direct |
| langchain-openai | 1.7.2 | MIT | classifier | direct |
| langgraph | 1.2.16 | MIT | License-Expression | direct |
| langgraph-checkpoint-postgres | 3.2.0 | MIT | License-Expression | direct |
| loguru | 0.7.3 | MIT | classifier | direct |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | License-Expression | direct |
| opentelemetry-api | 1.45.1 | Apache-2.0 | License-Expression | direct |
| opentelemetry-exporter-otlp-proto-http | 1.45.1 | Apache-2.0 | License-Expression | direct |
| opentelemetry-sdk | 1.45.1 | Apache-2.0 | License-Expression | direct |
| pandas | 3.0.6 | BSD (classifier does not specify 2/3-clause) | classifier | direct |
| pgvector | 0.5.1 | MIT | License-Expression | direct |
| pillow | 13.0.0 | MIT-CMU | License-Expression | direct |
| psycopg | 3.3.6 | LGPL-3.0-only | License-Expression | direct; **copyleft (LGPL)** |
| pydantic | 2.14.1 | MIT | License-Expression | direct |
| pydantic-settings | 2.16.0 | MIT | License-Expression | direct |
| pypdf | 6.21.0 | BSD-3-Clause | License-Expression | direct |
| python-docx | 1.2.0 | MIT | classifier | direct |
| python-dotenv | 1.2.4 | BSD-3-Clause | license-field | direct |
| python-multipart | 0.0.32 | Apache-2.0 | License-Expression | direct |
| python-pptx | 1.0.2 | MIT | classifier | direct |
| PyYAML | 6.0.3 | MIT | classifier | direct |
| qrcode | 8.2 | BSD (classifier does not specify 2/3-clause) | classifier | direct |
| redis | 8.1.0 | MIT | License-Expression | direct |
| requests | 2.34.2 | Apache-2.0 | classifier | direct |
| scikit-learn | 1.9.1 | BSD-3-Clause | License-Expression | direct |
| SQLAlchemy | 2.1.5 | MIT | License-Expression | direct |
| sse-starlette | 3.5.0 | BSD-3-Clause | License-Expression | direct |
| uvicorn | 0.54.0 | BSD-3-Clause | License-Expression | direct |
| websocket-client | 1.9.2 | Apache-2.0 | license-field | direct |
| websockets | 16.1.1 | BSD-3-Clause | License-Expression | direct |

### 1.2 Runtime dependencies — transitive

| Package | Version | License (as declared) | Source | Notes |
|---------|---------|----------------------|--------|-------|
| aiohappyeyeballs | 2.7.1 | PSF-2.0 | classifier | — |
| aiosignal | 1.4.0 | Apache-2.0 | classifier | — |
| amqp | 5.4.1 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| annotated-doc | 0.0.5 | MIT | License-Expression | — |
| annotated-types | 0.8.0 | MIT | License-Expression | — |
| anyio | 4.15.1 | MIT | License-Expression | — |
| attrs | 26.1.0 | MIT | License-Expression | — |
| billiard | 4.3.1 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| charset-normalizer | 3.5.2 | MIT | license-field | — |
| click | 8.5.0 | BSD-3-Clause | License-Expression | — |
| click-didyoumean | 0.3.1 | MIT | classifier | — |
| click-plugins | 1.1.1.2 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| click-repl | 0.4.1 | MIT | license-field | — |
| cloudpickle | 3.1.2 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| colorama | 0.4.6 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| distro | 1.9.0 | Apache-2.0 | classifier | — |
| frozenlist | 1.8.0 | Apache-2.0 | license-field | — |
| googleapis-common-protos | 1.75.5 | Apache-2.0 | License-Expression | — |
| h11 | 0.16.0 | MIT | classifier | — |
| httpcore | 1.0.9 | BSD-3-Clause | License-Expression | — |
| httpcore2 | 2.13.1 | BSD-3-Clause | License-Expression | — |
| httptools | 0.9.0 | MIT | License-Expression | — |
| httpx2 | 2.13.1 | BSD-3-Clause | License-Expression | — |
| idna | 3.20 | BSD-3-Clause | License-Expression | — |
| jiter | 0.17.0 | MIT | License-Expression | — |
| joblib | 1.6.0 | BSD-3-Clause | License-Expression | — |
| jsonpatch | 1.35 | BSD-3-Clause | License-Expression | — |
| jsonpointer | 3.2.1 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| kombu | 5.6.2 | BSD-3-Clause | license-field | — |
| langchain-core | 1.6.12 | MIT | classifier | — |
| langchain-protocol | 0.0.19 | MIT | classifier | — |
| langgraph-checkpoint | 4.3.0 | MIT | License-Expression | — |
| langgraph-prebuilt | 1.1.1 | MIT | License-Expression | — |
| langgraph-sdk | 0.4.8 | MIT | License-Expression | — |
| langsmith | 0.14.11 | MIT | classifier | — |
| lxml | 6.1.3 | BSD-3-Clause | license-field | — |
| Mako | 1.4.3 | MIT | License-Expression | — |
| MarkupSafe | 3.0.4 | BSD-3-Clause | License-Expression | — |
| multidict | 7.1.0 | Apache-2.0 | License-Expression | — |
| narwhals | 2.27.1 | MIT | License-Expression | — |
| openai | 3.33.0 | Apache-2.0 | License-Expression | — |
| opentelemetry-exporter-http-transport | 0.66b1 | Apache-2.0 | License-Expression | — |
| opentelemetry-exporter-otlp-common | 0.66b1 | Apache-2.0 | License-Expression | — |
| opentelemetry-exporter-otlp-proto-common | 1.45.1 | Apache-2.0 | License-Expression | — |
| opentelemetry-proto | 1.45.1 | Apache-2.0 | License-Expression | — |
| opentelemetry-semantic-conventions | 0.66b1 | Apache-2.0 | License-Expression | — |
| orjson | 3.13.0 | MPL-2.0 AND (Apache-2.0 OR MIT) | License-Expression | — |
| ormsgpack | 1.13.0 | Apache-2.0 OR MIT | License-Expression | — |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | License-Expression | — |
| prompt_toolkit | 3.0.53 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| propcache | 0.5.4 | Apache-2.0 | license-field | — |
| protobuf | 7.36.2 | 3-Clause BSD License | license-field-raw | — |
| psycopg-binary | 3.3.6 | LGPL-3.0-only | License-Expression | **copyleft (LGPL)** |
| psycopg-pool | 3.3.3 | LGPL-3.0-only | License-Expression | **copyleft (LGPL)** |
| pydantic_core | 2.50.1 | MIT | License-Expression | — |
| python-dateutil | 2.9.0.post0 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python | License-Expression | — |
| requests-toolbelt | 1.0.0 | Apache-2.0 | classifier | — |
| scipy | 1.18.1 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| six | 1.17.0 | MIT | classifier | — |
| sniffio | 1.3.1 | MIT | classifier | — |
| starlette | 1.8.0 | BSD-3-Clause | License-Expression | — |
| tabulate | 0.10.0 | MIT | License-Expression | — |
| tenacity | 9.2.1 | Apache-2.0 | License-Expression | — |
| threadpoolctl | 3.7.0 | BSD-3-Clause | License-Expression | — |
| tiktoken | 0.14.0 | MIT | license-field | — |
| truststore | 0.10.5 | MIT | License-Expression | — |
| typing-inspection | 0.4.4 | MIT | License-Expression | — |
| typing_extensions | 4.16.0 | PSF-2.0 | License-Expression | — |
| tzdata | 2026.5 | Apache-2.0 | license-field | — |
| tzlocal | 5.4.4 | MIT | License-Expression | — |
| urllib3 | 2.8.0 | MIT | License-Expression | — |
| uuid_utils | 0.17.1 | BSD-3-Clause | License-Expression | — |
| vine | 5.1.0 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| watchfiles | 1.3.0 | MIT | classifier | — |
| wcwidth | 0.9.2 | MIT | classifier | — |
| win32_setctime | 1.2.0 | MIT | classifier | — |
| xlsxwriter | 3.2.9 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| xxhash | 4.0.1 | BSD-2-Clause | license-field | — |
| yarl | 1.25.1 | Apache-2.0 | license-field | — |
| zstandard | 0.25.0 | BSD-3-Clause | License-Expression | — |

### 1.3 Dev/test/code-quality only (not runtime; pin the build, do not redistribute as app code)

| Package | Version | License (as declared) | Source | Notes |
|---------|---------|----------------------|--------|-------|
| ast_serialize | 0.13.1 | MIT | License-Expression | — |
| cfgv | 3.5.0 | MIT | license-field | — |
| coverage | 7.16.2 | Apache-2.0 | license-field | — |
| distlib | 0.4.4 | PSF-2.0 | classifier | — |
| filelock | 4.2.0 | MIT | License-Expression | — |
| identify | 2.6.20 | MIT | license-field | — |
| iniconfig | 2.3.1 | MIT | License-Expression | — |
| librt | 0.16.0 | MIT | License-Expression | — |
| mypy | 2.4.0 | MIT | License-Expression | direct; listed under the test section but also a runtime transitive of langchain-core |
| mypy_extensions | 1.1.0 | MIT | License-Expression | — |
| nodeenv | 1.11.0 | BSD (classifier does not specify 2/3-clause) | classifier | — |
| pathspec | 1.1.1 | MPL-2.0 | classifier | — |
| platformdirs | 4.13.3 | MIT | License-Expression | — |
| pluggy | 1.7.0 | MIT | classifier | — |
| pre_commit | 4.7.0 | MIT | license-field | direct; listed under the test section but also a runtime transitive of langchain-core |
| py-cpuinfo2 | 10.1.1 | MIT | License-Expression | — |
| Pygments | 2.21.0 | BSD-2-Clause | License-Expression | — |
| pytest | 9.1.1 | MIT | License-Expression | direct; listed under the test section but also a runtime transitive of langchain-core |
| pytest-asyncio | 1.4.0 | Apache-2.0 | License-Expression | direct; listed under the test section but also a runtime transitive of langchain-core |
| pytest-benchmark | 5.3.0 | BSD-2-Clause | License-Expression | direct; listed under the test section but also a runtime transitive of langchain-core |
| pytest-cov | 7.1.0 | MIT | License-Expression | direct; listed under the test section but also a runtime transitive of langchain-core |
| python-discovery | 1.6.3 | MIT | classifier | — |
| ruff | 0.17.1 | MIT | License-Expression | direct; listed under the test section but also a runtime transitive of langchain-core |
| virtualenv | 21.14.8 | MIT | License-Expression | — |

### 1.4 Declared/expected components not verified (UNKNOWN licenses)

These five are declared or expected but **not installed** in the audit environment, so no metadata
could be read offline. Their license fields are left as `UNKNOWN` rather than guessed.

| Package | Version basis | Declaration | Status | License |
|---------|---------------|-------------|--------|---------|
| chromadb | unpinned | requirements.txt comment (legacy; not required at runtime) | not installed in audit env | **UNKNOWN** |
| mcp | 2.3.0 | `requirements-mcp.txt` (optional local stdio adapter) | not installed in audit env | **UNKNOWN** |
| passlib | unpinned | `pyproject.toml` poetry dependency (not in requirements/lock) | not installed in audit env | **UNKNOWN** |
| python-jose | unpinned | `pyproject.toml` poetry dependency (not in requirements/lock) | not installed in audit env | **UNKNOWN** |
| sentence-transformers | unpinned | `docs/03` stack list only (not in requirements/lock) | not installed in audit env | **UNKNOWN** |

`torch` (installed 2.14.1, not pinned): declared license expression `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT`. It is installed by users and
excluded from the PyInstaller build (`backend.spec` `excludes`), so it is not redistributed in
the shipped desktop backend, but it is part of the development/runtime environment.

**License notes for Python (facts, not advice):**

* `psycopg`, `psycopg-binary`, `psycopg-pool` are `LGPL-3.0-only`; `edge-tts` is `LGPL-3.0` (classifier).
  If the desktop build bundles them through PyInstaller (`backend.spec` collects `edge_tts`), LGPL
  obligations may apply — verify with counsel and ship the license text/source offer as applicable.
* LGPL-3.0-only / MPL-2.0 / PSF-2.0 / MIT-CMU (`Pillow`) components have license texts in their
  `dist-info` directories locally: 144 of 146 installed in-scope packages expose a license file.
* 17 packages only declare the classifier `BSD License`, which does not distinguish 2- vs 3-clause
  in the metadata; `protobuf` exposes the raw string `3-Clause BSD License`. SPDX identifiers are
  shown when the metadata provides a `License-Expression`; otherwise the declared value is kept verbatim.
* `imageio-ffmpeg` declares `BSD-2-Clause`, but its wheel drops a **third-party FFmpeg executable**
  into `binaries/` on first/installed use. In this env: `ffmpeg-win-x86_64-v7.1.exe` (87.6 MB),
  reporting `ffmpeg version 7.1-essentials_build-www.gyan.dev`, configuration with
  `--enable-gpl --enable-version3` — i.e. a **GPLv3 FFmpeg build**. That binary's license is not
  represented by the Python package's BSD metadata; if the desktop build ships it, separate
  GPL compliance (source/offer, notices) is required. Not verified whether the desktop build
  actually contains it (no `dist/` build present in this working tree).
* **Undeclared media toolchain:** `manim`, used by the video renderer code path, is **not in
  `requirements.txt`/the lock and is not installed as a distribution** in this environment, yet
  its typical dependency stack (`pycuda`, `moderngl`, `glcontext`, `pygame`, `pytools`, `sympy`,
  `networkx`, `fsspec`, `mpmath`) is installed but undeclared (16 env extras total, also
  `pip`/`pip-tools`/`build`/`setuptools`/`wheel`). Generated-video provenance therefore depends on
  tooling that is not pinned by the repo. `playwright`/`cairosvg` are optional and not installed.

## 2. Frontend dependencies (web, Vue 3 + Vite)

Source: `frontend/package-lock.json` (lockfileVersion 3, 178 entries) corroborated against the
offline-installed `frontend/node_modules` (2026-10-18): **0 version mismatches, 0 missing licenses**,
all 65 runtime entries resolve to `registry.npmjs.org`. The 81 lock entries outside the reachable
dependency closures are almost all optional platform-locked binaries (`@esbuild/*`, `@rollup/*`,
`@parcel/watcher-*`) plus optional peer/dev helper packages; all also carry a declared `license`
field. All license values below are the npm `license` field as declared by the package (not
verified against each package's LICENSE file).

### 2.1 Runtime packages (`frontend/package.json` dependencies + closure) — bundled into `dist`

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| @ant-design/colors | 6.0.0 | MIT | — |
| @ant-design/icons-svg | 4.4.2 | MIT | — |
| @ant-design/icons-vue | 7.0.1 | MIT | — |
| @babel/helper-string-parser | 7.27.1 | MIT | — |
| @babel/helper-validator-identifier | 7.28.5 | MIT | — |
| @babel/parser | 7.29.2 | MIT | — |
| @babel/runtime | 7.29.7 | MIT | — |
| @babel/types | 7.29.0 | MIT | — |
| @ctrl/tinycolor | 3.6.1 | MIT | — |
| @emotion/hash | 0.9.2 | MIT | — |
| @emotion/unitless | 0.8.1 | MIT | — |
| @jridgewell/sourcemap-codec | 1.5.5 | MIT | — |
| @kurkle/color | 0.3.4 | MIT | — |
| @simonwep/pickr | 1.8.2 | MIT | — |
| @vue/compiler-core | 3.5.32 | MIT | — |
| @vue/compiler-dom | 3.5.32 | MIT | — |
| @vue/compiler-sfc | 3.5.32 | MIT | — |
| @vue/compiler-ssr | 3.5.32 | MIT | — |
| @vue/devtools-api | 6.6.4 | MIT | — |
| @vue/reactivity | 3.5.32 | MIT | — |
| @vue/runtime-core | 3.5.32 | MIT | — |
| @vue/runtime-dom | 3.5.32 | MIT | — |
| @vue/server-renderer | 3.5.32 | MIT | — |
| @vue/shared | 3.5.32 | MIT | — |
| ant-design-vue | 4.2.6 | MIT | direct dependency |
| array-tree-filter | 2.1.0 | MIT | — |
| async-validator | 4.2.5 | MIT | — |
| chart.js | 4.5.1 | MIT | direct dependency |
| commander | 8.3.0 | MIT | — |
| compute-scroll-into-view | 1.0.20 | MIT | — |
| core-js | 3.49.0 | MIT | — |
| csstype | 3.2.3 | MIT | — |
| dayjs | 1.11.21 | MIT | — |
| dom-align | 1.12.4 | MIT | — |
| dom-scroll-into-view | 2.0.1 | MIT | — |
| echarts | 6.0.0 | Apache-2.0 | direct dependency |
| entities | 7.0.1 | BSD-2-Clause | — |
| estree-walker | 2.0.2 | MIT | — |
| is-plain-object | 3.0.1 | MIT | — |
| js-tokens | 4.0.0 | MIT | — |
| katex | 0.17.0 | MIT | direct dependency |
| lodash | 4.18.1 | MIT | — |
| lodash-es | 4.18.1 | MIT | — |
| loose-envify | 1.4.0 | MIT | — |
| lucide-vue-next | 1.0.0 | ISC | direct dependency |
| magic-string | 0.30.21 | MIT | — |
| marked | 18.0.5 | MIT | direct dependency |
| nanoid | 3.3.11 | MIT | — |
| nanopop | 2.4.2 | MIT | — |
| picocolors | 1.1.1 | ISC | — |
| pinia | 3.0.4 | MIT | direct dependency |
| postcss | 8.5.9 | MIT | — |
| resize-observer-polyfill | 1.5.1 | MIT | — |
| scroll-into-view-if-needed | 2.2.31 | MIT | — |
| shallow-equal | 1.2.1 | MIT | — |
| source-map-js | 1.2.1 | BSD-3-Clause | — |
| stylis | 4.4.0 | MIT | — |
| throttle-debounce | 5.0.2 | MIT | — |
| tslib | 2.3.0 | 0BSD | — |
| vue | 3.5.32 | MIT | direct dependency |
| vue-chartjs | 5.3.3 | MIT | direct dependency |
| vue-router | 4.6.4 | MIT | direct dependency |
| vue-types | 3.0.2 | MIT | — |
| warning | 4.0.3 | MIT | — |
| zrender | 6.0.0 | BSD-3-Clause | — |

### 2.2 Build/test-only packages (`devDependencies` + closure) — not shipped

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| @types/estree | 1.0.8 | MIT | — |
| @types/node | 22.19.17 | MIT | direct dependency |
| @vitejs/plugin-vue | 5.2.4 | MIT | direct dependency |
| @volar/language-core | 2.4.15 | MIT | — |
| @volar/source-map | 2.4.15 | MIT | — |
| @volar/typescript | 2.4.15 | MIT | — |
| @vue/compiler-vue2 | 2.7.16 | MIT | — |
| @vue/language-core | 2.2.12 | MIT | — |
| alien-signals | 1.0.13 | MIT | — |
| balanced-match | 1.0.2 | MIT | — |
| brace-expansion | 2.0.3 | MIT | — |
| chokidar | 4.0.3 | MIT | — |
| de-indent | 1.0.2 | MIT | — |
| esbuild | 0.25.12 | MIT | — |
| fdir | 6.5.0 | MIT | — |
| he | 1.2.0 | MIT | — |
| immutable | 5.1.5 | MIT | — |
| minimatch | 9.0.9 | ISC | — |
| muggle-string | 0.4.1 | MIT | — |
| path-browserify | 1.0.1 | MIT | — |
| picomatch | 4.0.4 | MIT | — |
| readdirp | 4.1.2 | MIT | — |
| rollup | 4.60.1 | MIT | — |
| sass | 1.99.0 | MIT | direct dependency |
| tinyglobby | 0.2.16 | MIT | — |
| typescript | 5.9.3 | Apache-2.0 | direct dependency |
| undici-types | 6.21.0 | MIT | — |
| vite | 6.4.2 | MIT | direct dependency |
| vscode-uri | 3.1.0 | MIT | — |
| vue-tsc | 2.2.12 | MIT | direct dependency |

### 2.3 Fonts bundled by the frontend build

* `frontend/dist/assets/` contains 59 font files (19 woff2 + 20 woff + 20 ttf), all named `KaTeX_*`.
* They come from the `katex` npm package (`katex/dist/fonts`, 60 files in `node_modules`).
  `katex` (v0.17.0, MIT — package `LICENSE`: copyright Khan Academy and other contributors) is a
  production dependency. The npm package ships **no separate font license file**; whether the
  font files (derived from Computer Modern) carry additional terms was not verified offline.
  No web fonts are fetched from a CDN or bundled from any other source: a source scan found no
  `fonts.googleapis`/CDN/font hotlinks in `frontend/src`, `frontend/public` or `frontend/index.html`.

## 3. Desktop shell dependencies (Electron, root package-lock.json)

The root `package.json` builds a Windows NSIS installer (`electron-builder.yml`). `package-lock.json`
has 454 entries; the reachable runtime closure is 19 packages (all MIT/ISC/BlueOak or dual-licensed),
the reachable dev closure is 266 (`electron`/`electron-builder` build tooling), and 168 further lock
entries are optional/platform-locked sub-dependencies outside those closures. Licenses are
lock-declared only: root `node_modules` is absent, so no installed metadata was cross-checked.

| Package | Version | License | Notes |
|---------|---------|---------|-------|
| @types/node | 20.19.43 | MIT | — |
| docx | 9.7.1 | MIT | — |
| hash.js | 1.1.7 | MIT | — |
| immediate | 3.0.6 | MIT | — |
| inherits | 2.0.4 | ISC | — |
| jszip | 3.10.1 | (MIT OR GPL-3.0-or-later) | — |
| lie | 3.3.0 | MIT | — |
| minimalistic-assert | 1.0.1 | ISC | — |
| nanoid | 5.1.16 | MIT | — |
| pako | 1.0.11 | (MIT AND Zlib) | — |
| readable-stream | 3.6.2 | MIT | — |
| safe-buffer | 5.2.1 | MIT | — |
| sax | 1.6.0 | BlueOak-1.0.0 | — |
| setimmediate | 1.0.5 | MIT | — |
| string_decoder | 1.3.0 | MIT | — |
| undici-types | 6.21.0 | MIT | — |
| util-deprecate | 1.0.2 | MIT | — |
| xml | 1.0.1 | MIT | — |
| xml-js | 1.6.11 | MIT | — |

Build tooling includes `electron` (MIT) and `electron-builder` (MIT); these are dev dependencies,
but the Electron runtime itself (MIT; bundles Chromium and other components with their own notices)
is packaged into the installer by electron-builder. That installer also embeds the PyInstaller
backend and — via `backend.spec` — `frontend/dist`, `data/artifacts/{mp3,pptx,mermaid_png}` and
seed data. **No third-party NOTICE/LICENSE file is added by this repo to the installer.**

## 4. Bundled asset families and provenance

Scan: **386 media/document files + 218 JS/CSS bundle files** in the working tree (excluding `.git`,
`node_modules`, test caches), **252 distinct media contents** (89 duplicate-content groups, 134 redundant
copies — mostly `dist/` mirrors of `public/`). `frontend/dist` and `data/artifacts` are gitignored
build/runtime output but are packaged into the desktop build, so both tracked and on-disk files are
listed below.

| Family | Path glob(s) | Tracked / present | Size | Provenance status | Evidence / open question |
|--------|--------------|-------------------|------|-------------------|--------------------------|
| Pixel-campus sprites (public) | `frontend/public/pixel-campus/**` | 51 / 51 | 76.41 MB | **UNKNOWN — no provenance file** | Origin/author/tool not recorded; 51 PNGs at 1254×1254 mostly, no embedded metadata (PNG tags absent); no LICENSE/README in tree. |
| Avatars / role portraits (public) | `frontend/public/avatars/**` | 16 / 16 | 8.71 MB | **UNKNOWN — no provenance file** | 16 files named by role (planner/tutor/quiz/…) and character (owl mascot, etc.); no author/design/tool record; PNG metadata stripped. |
| Companion sprite + login avatars (src) | `frontend/src/assets/**` | 8 / 8 | 3.89 MB | **UNKNOWN — no provenance file** | Pixel sprite/chroma pairs and 6 login-avatar copies byte-identical to `frontend/public/avatars`. |
| Avatars duplicated in React sub-app | `frontend/public/integrated-map/avatars/**` | 6 / 6 | 1.54 MB | **UNKNOWN — copy of public avatars** | 6 copies byte-identical to `frontend/public/avatars`. |
| Project logo | `frontend/public/logo.png` | 1 / 1 | 0.81 MB | **UNKNOWN — no provenance file** | Also copied to `data/logo.png` and `frontend/dist/logo.png`; source/author/design file not recorded. |
| React sub-app bundle (`/integrated-map`) | `frontend/public/integrated-map/assets/*.{js,css}` | 2 / 2 | 0.52 MB | **THIRD-PARTY BUILD — NO SOURCE IN REPO** | 397 KB minified JS + 143 KB CSS (plus a 463 B `index.html` loader); contains React, react-dom, marked, lucide markers; no license/copyright banner, no source map, no lockfile/source. Docs reference `frontend/integrated-map-src/src`, which is absent from the repo and from git history. |
| Stale React bundles served from `public/` | `frontend/public/assets/*.{js,css}` | 30 / 30 | 4.97 MB | **UNPROVENANCED BUILD OUTPUT** | 30 tracked files (16 JS + 14 CSS, 4.97 MB) from earlier React builds; contain React/lucide strings; no license text; unreferenced by current `frontend/index.html`/`dist/index.html`. |
| Vue build output (`frontend/dist`, gitignored) | `frontend/dist/assets/**` | 0 / 212 | 11.95 MB | **BUILD OUTPUT — NO LICENSE/NOTICE FILE** | 212 files: 146 JS/CSS accumulated across builds (only 3 referenced by `dist/index.html`; 143 stale, 8.47 MB) + 59 KaTeX fonts + 7 PNGs. No third-party LICENSE/NOTICE shipped. |
| Dist copy of pixel-campus | `frontend/dist/pixel-campus/**` | 0 / 51 | 76.41 MB | **COPY — same unknown origin** | Mirror of `frontend/public/pixel-campus` (76.41 MB) shipped in the desktop build. |
| Dist copy of avatars | `frontend/dist/avatars/**` | 0 / 16 | 8.71 MB | **COPY — same unknown origin** | Mirror of `frontend/public/avatars`. |
| Generated learning artifacts (gitignored) | `data/artifacts/**` | 0 / 119 | 20.17 MB | **PIPELINE-GENERATED — manifest incomplete** | 119 files (54 pptx, 36 mp3, 22 png, 4 wav, 2 mp4, 1 svg): TTS audio generated via edge-tts/Microsoft service (`tts_*_edge.mp3`, 24 kHz mono), 2 mp4 assembled with ffmpeg (`Lavf61.7.100`), 22 png (20 mermaid renders + 1 png + 1 QR), 54 pptx (python-pptx), 1 manim placeholder SVG. `data/artifacts_index.json` indexes only 4 key artifacts (its own `discovered_total` was 51 at index time); per-file renderer (mmdc vs Playwright vs PIL placeholder) is not recorded. |
| AI-generated architecture diagrams | `docs/TripleU-*.png` | 3 / 3 | 2.39 MB | **AI-GENERATED — service/model not recorded** | Prompt docs exist (`docs/TripleU-*-AI生成提示词.md`); prompt asks for real technology logos; generation-service terms and logo/trademark permission are unrecorded. |
| Product screenshots + hero SVG | `docs/assets/**` | 4 / 4 | 1.29 MB | **PROJECT-GENERATED — no provenance file** | `product-*.png` are screenshots of this app's UI; `repository-hero.svg` is a hand-authored SVG. Authorship/date/license not recorded. |
| Mobile avatars + favicon | `mobile/public/**` | 7 / 7 | 1.54 MB | **UNKNOWN — copies/derivatives** | 6 avatars identical to the web avatar family; favicon derived from project logo. |
| Android launcher icons / splash | `mobile/android/app/src/main/res/**` | 26 / 26 | 0.20 MB | **UNKNOWN — generated icons** | 26 PNGs (splash/launcher densities); no design source or provenance file. |
| Desktop app icon | `electron/assets/icon.ico` | 1 / 1 | 0.04 MB | **UNKNOWN — derived from logo** | Used as NSIS/PyInstaller icon; derivation from `logo.png` not documented. |
| PPTX deck template | `data/pptx_templates/**` | 1 / 1 | 0.03 MB | **UNKNOWN — template origin not recorded** | 1 PPTX template (~27.9 KB) used by the deck generator; layouts/theme/fonts may carry third-party terms; no provenance file. Also `backend/app/templates/reports/student_report.docx` is a tracked 0-byte placeholder. |
| Third-party dataset (local only) | `data/benchmarks/assist2009.zip` | 0 / 1 | 8.66 MB | **THIRD-PARTY DATA — not in git** | Source/terms stated in `docs/datasets/dataset_spec.md` (USTC EduData mirror; "academic research use (CMU open)"); no license text in repo; present locally only, not shipped in git. |

Additional evidence notes:

* **No provenance file exists for any asset family.** The only LICENSE/NOTICE-like files in the
  tree are the project `LICENSE`, README files, and dependency license texts inside
  `frontend/node_modules`; there is no `ATTRIBUTION`, `CREDITS`, `SOURCES` or asset README.
* `data/benchmarks/assist2009.zip` (ASSISTments 2009 skill-builder corrected) is **not tracked
  and not in git**; `docs/datasets/dataset_spec.md` records source (USTC EduData mirror) and
  "academic research use (CMU open)". No license text is included. It is present in the local
  working tree only (8.66 MB), but must not be redistributed without checking its terms.
* **Runtime-fetched components (not bundled assets):** `backend/app/services/multimodal/mermaid/renderer.py`
  invokes `npx -y @mermaid-js/mermaid-cli` (network fetch of an npm package at runtime);
  Manim/Playwright are optional renderers (commented out of `requirements.txt`, absent from the
  lock); `edge-tts` calls Microsoft's online TTS service; LLM/embedding/image calls go to
  iFlytek/OpenAI-compatible APIs. No image/font/script CDN URLs were found in the shipped frontend.
* **Working-tree state (re-checked 2026-10-19, QWEN-103):** the dedup described above is now
  **committed**. Measured: `git ls-files frontend/public/integrated-map/pixel-campus` → **0** tracked
  files, on-disk files → **0**, leaving 14 directories of which 12 are empty leaf directories
  (Git does not track empty directories, so `git status` is clean for this path). The canonical
  copies remain tracked at `frontend/public/pixel-campus/**` (51 PNG + 8 `.gitkeep` = 59 tracked
  files). Provenance accounting for the surviving PNG family still has to be re-run and is owned by
  QWEN-401; this bullet only records that the "deleted but unstaged" state no longer exists.

## 5. Attribution / notice gaps (F8–F10 evidence)

| # | Gap | Evidence |
|---|-----|----------|
| G1 | No third-party LICENSE/NOTICE material is shipped with the frontend build or desktop installer | `frontend/dist` contains 0 license/notice files; `electron-builder.yml` adds no notice file; `backend.spec` packages `frontend/dist` + artifacts |
| G2 | README already links to `THIRD_PARTY_NOTICES.md`, but the file did not exist before this audit | `README.md:206` link; repo root had no such file (`git ls-files` empty) |
| G3 | `frontend/public/integrated-map` is a React build with **no source, manifest or license texts** in-repo | docs (`docs/10-学术与工程创新对照表.md`, `docs/TripleU平台全功能思维导图.md`) reference `frontend/integrated-map-src/src`, which is absent from working tree and git history; bundle strings include React/react-dom/marked/lucide; no `@license` banner |
| G4 | 30 stale, tracked React JS/CSS bundles under `frontend/public/assets/` have no provenance and are unreferenced | 4.97 MB, license-banner-free, not referenced by `frontend/index.html` or `dist/index.html` |
| G5 | All visual/asset families are unprovenanced (pixel-campus, avatars, logo/icon, docs diagrams, mobile icons) | 0 ATTRIBUTION/CREDITS/provenance files; PNG metadata stripped; source-asset provenance not recorded in any doc |
| G6 | `docs/03-开源参考与协议.md` is a curated, incomplete and partly inaccurate dependency disclosure | Only **4 of 47** direct Python deps and **5 of 10** direct frontend deps are named; omits LangChain/LangGraph, OpenTelemetry, Celery/Redis, psycopg/pgvector, edge-tts, ant-design-vue, chart.js, vue-chartjs, katex, lucide-vue-next, Electron/docx; lists ChromaDB/sentence-transformers/bge/highlight.js/Mermaid which are not installed/bundled deps; last updated 2026-06-19 |
| G7 | Copyleft / GPL exposure is undisclosed | `psycopg*` LGPL-3.0-only, `edge-tts` LGPL-3.0 (both collected into PyInstaller build); bundled FFmpeg 7.1 binary reports `--enable-gpl --enable-version3` (GPL build) inside `imageio-ffmpeg` |
| G8 | No automated license/notice gate | `.github/workflows/ci.yml` has no license/NOTICE/SBOM check |
| G9 | Asset dedup mid-flight was the 2026-10-18 state; **re-checked 2026-10-19: the deletions are committed** and the working tree is clean, so the remaining gap is provenance, not staging | `git ls-files frontend/public/integrated-map/pixel-campus` = 0 tracked / 0 files on disk / 14 dirs (12 empty leaves); canonical 51 PNG still tracked under `frontend/public/pixel-campus/` |

## 6. Recommended actions before a public release

1. **Ship license texts.** Generate a `THIRD_PARTY_LICENSES.txt`/`NOTICE` from the installed
   metadata (this env has license files for 144/146 Python packages and 105/115 frontend `node_modules`
   packages) and include it in the Vite build output, the NSIS installer and the PyInstaller
   `datas`. Add a `NOTICE` section for the project's own MIT license.
2. **Resolve the React sub-app provenance.** Locate/restore `frontend/integrated-map-src` (source +
   lockfile) and rebuild the bundle, or document its origin and include React/marked/lucide
   notices. Do not redistribute an unattributable build artifact.
3. **Delete or document `frontend/public/assets/`** (30 stale tracked bundles, 4.97 MB) and clean
   `frontend/dist` before packaging (currently 99.93 MB; 143 of 146 JS/CSS chunks are stale).
4. **Create `docs/ASSETS_PROVENANCE.md`** mapping every tracked media family (path glob, count,
   author/designer, tool/model + service, date, license, evidence) — starting with pixel-campus,
   avatars, logo/icon and the two AI-generated diagrams. Record AI-generation services and confirm
   the right to use third-party product logos in diagrams.
5. **Update `docs/03-开源参考与协议.md`** to point at this inventory (single source of truth),
   remove components that are not shipped (ChromaDB / sentence-transformers / bge / highlight.js /
   Mermaid-as-npm-dep), and add missing runtime stacks + Electron/docx.
6. **Obtain legal review for copyleft/GPL exposure:** LGPL `psycopg*`/`edge-tts` inside the
   PyInstaller bundle and the GPL FFmpeg binary bundled via `imageio-ffmpeg`; decide whether to
   ship those binaries, use differently-licensed builds, and include source/offer as required.
7. **Add CI gates:** validate that `THIRD_PARTY_NOTICES.md` is current (regenerate + diff), that
   `dist` contains a NOTICE file, and that every tracked asset family has a provenance entry.
8. **Record dataset terms:** document `assist2009.zip` terms in `docs/datasets/dataset_spec.md` and
   keep it out of release artifacts unless redistribution is permitted.
9. **Commit or revert the pending asset deletions** and re-run this inventory against the clean tree.

## 7. Explicit unknowns (do not guess)

* Python license UNKNOWN (not installed, no network): `chromadb`, `mcp`, `passlib`, `python-jose`, `sentence-transformers`.
* Provenance of pixel-campus sprites, avatars, companion sprites, logo/icon, mobile icons and both
  AI-generated architecture diagrams: **no evidence in repo**.
* Which model/service generated the diagrams, and under what terms.
* Per-file renderer for `data/artifacts/mermaid_png` (mmdc vs Playwright vs PIL placeholder).
* Whether the desktop installer actually contains the FFmpeg binary and whether `dist/` packaging
  preserves dependency license texts (no `dist/` build present in this tree).
* Correctness of npm/PyPI declared license metadata against actual LICENSE files (only npm
  `license` fields and Python metadata were read; license texts were not diffed).
* Copyright/authorship of course content, prompts, docs and generated media; not part of this audit.

## 8. Reproduction

```powershell
$py = '<project python>'
& $py output/license-audit-20261018/collect_python.py    # importlib.metadata, lockfile parse
& $py output/license-audit-20261018/collect_frontend.py  # package-lock + node_modules parse
& $py output/license-audit-20261018/scan_assets.py       # media/bundle scan + git ls-files
& $py output/license-audit-20261018/summarize.py         # derived counts
& $py output/license-audit-20261018/build_notices.py     # writes this file + report.md
```

---

*Generated by the license-auditor teammate (DSH agent) on 2026-10-18. Machine inventory, **not legal advice**; 
unknowns are marked UNKNOWN rather than guessed. Re-run after dependency or asset changes.*
