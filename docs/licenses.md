# Licenses of dependencies, images, fonts and models

Collected 2026-10-29. Versions come from `uv.lock`; licenses from the metadata of the installed packages
(`importlib.metadata`: fields `License-Expression`, `License`, trove classifiers). Where the metadata says nothing,
the cell is marked "not found in metadata". This is an inventory for a technical review, not legal advice.

## Python packages (direct dependencies, `[project].dependencies`)

| Package | Version | License | Source of the license |
|---|---|---|---|
| fastapi | 0.162.0 | MIT | License-Expression |
| uvicorn (extra `standard`) | 0.54.0 | BSD-3-Clause | License-Expression |
| pydantic | 2.14.1 | MIT | License-Expression |
| pydantic-settings | 2.16.1 | MIT | classifier |
| psycopg (extra `binary`) | 3.3.6 | LGPL-3.0-only | License-Expression |
| pgvector | 0.5.1 | MIT | License-Expression |
| jinja2 | 3.1.6 | BSD (BSD-3-Clause) | classifier |
| python-multipart | 0.0.32 | Apache-2.0 | License-Expression |
| argon2-cffi | 25.1.0 | MIT | License-Expression |
| itsdangerous | 2.2.0 | BSD (BSD-3-Clause) | classifier |
| openai | 3.40.0 | Apache-2.0 | License-Expression |
| httpx | 0.28.1 | BSD-3-Clause | License field |
| python-docx | 1.2.0 | MIT | License field |
| openpyxl | 3.1.5 | MIT | License field |
| pypdf | 6.21.3 | BSD-3-Clause | License-Expression |

Development group (`[dependency-groups].dev`, not in the Docker image):

| Package | Version | License | Source of the license |
|---|---|---|---|
| pytest | 9.2.0 | MIT | License-Expression |
| ruff | 0.17.3 | MIT | License-Expression |
| reportlab | 5.1.0 | BSD (license text in `license.txt`) | License field, classifier |

Notes:

- `uvicorn[standard]` and `psycopg[binary]` pull in further transitive packages (for example `psycopg-binary`,
  LGPL-3.0-only, 3.3.6). The full transitive list is in `uv.lock`; its licenses were not collected here.
- `psycopg` is LGPL: it is used as an unmodified library, installed as a separate package.
- The version in the table was checked against the environment used for this inventory; `uv.lock` is the source of truth.

## Container images

| Image | Tag | License |
|---|---|---|
| pgvector/pgvector | pg16 | PostgreSQL License (PostgreSQL); pgvector extension: PostgreSQL License. Not found in metadata here: check the image page |
| python | 3.12-slim | Python Software Foundation License for Python; Debian packages carry their own licenses |
| ghcr.io/astral-sh/uv | 0.5 | MIT or Apache-2.0 (upstream); build stage only. Not found in metadata here |
| ollama/ollama | 0.12.6 | MIT (upstream); profile `local` only. Not found in metadata here; tag not pulled during this work |

## Front-end assets (in `src/rfp/web/static`)

| Asset | License | Note |
|---|---|---|
| IBM Plex Sans (woff2, weights 300/400/600, latin and cyrillic) | SIL Open Font License 1.1 | Free for any use, including embedding |
| htmx 2.0.4 (`htmx-2.0.4.min.js`) | 0BSD (upstream, htmx 2.x) | Not found in the file: the minified file has no license header. Verify on the htmx repository |

## Models

| Model | Role | Terms |
|---|---|---|
| gpt-4o-mini | answers, question translation, layout map (default) | OpenAI API, OpenAI terms of use; called over the network |
| gpt-4o | judge in the evaluation run | OpenAI API, OpenAI terms of use |
| text-embedding-3-small | embeddings (default, 1536 dimensions) | OpenAI API, OpenAI terms of use |
| qwen2.5:7b | local mode: answers, translation, layout map | Apache-2.0 (upstream Qwen2.5 7B Instruct) |
| gemma2:9b | candidate for the local mode | Gemma Terms of Use (not an OSI license; has a use policy) |
| bge-m3 | local mode: embeddings (1024 dimensions) | MIT |

Model terms were taken from the model publishers' pages by name, not from files in this repository: check the current
text before commercial use. Quality figures in this repository exist only for the OpenAI models (see `reports/`).

## Data

- The synthetic knowledge base and the dev set (fictional company Steppelight) are created for this project.
- Public questionnaires used to measure the layout map are not in the repository (`data/public/` is in `.gitignore`):
  their licenses forbid or do not clearly allow redistribution. See `docs/public-questionnaires.md`.
