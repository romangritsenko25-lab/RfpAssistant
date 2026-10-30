# RfpAssistant

*Русская версия: [README.md](README.md)*

A demonstration RAG service that fills RFPs and customer questionnaires with answers from a knowledge base. Every
answer carries a source and a quote, and when the knowledge base has nothing, the service says so plainly
("no data in the knowledge base").

**This is a demo project, not a delivered order.** It is built as a sample result for the Andersen Kazakhstan task
on Astana Hub at reduced scale: a 40-document knowledge base instead of 200, with the same acceptance criteria.
The knowledge base, customers, certificates and figures in `data/` are fictional: the company is Steppelight
Technologies, see `data/README.md`.

## How it works

```
file upload (DOCX / XLSX)
  -> layout: the model finds the question and answer columns/blocks, code checks the layout against rules
     (on failure it falls back to header rules)
  -> per question: the model translates the query (ru / kk / en)
  -> hybrid search: full-text (FTS) + vector (pgvector), merged with RRF
  -> the model answers with a quote from the retrieved fragment; code checks that the quote is in the fragment text
     (otherwise the citation is dropped)
  -> no data or low confidence -> "no data in the knowledge base", no invented answer
  -> export into the original file with a self-check: answers sit where they belong
```

Each answer stores its source (document, section), the quote and a status (`answered`, `needs_review`, `no_data`).
User actions are written to an audit log.

## Run in 3 commands

```
cp .env.example .env
docker compose up -d
# open http://localhost:8000
```

Before starting, set `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` in `.env` (the first administrator is created
at startup) and `LLM_API_KEY` for an OpenAI-compatible service. No values are stored in the repository. Without a
key the service starts, but model calls are unavailable.

Without Docker: Python 3.12 and `uv`; run `uv sync`, then `uv run uvicorn rfp.app:app` (needs PostgreSQL with
pgvector, `DATABASE_URL` in `.env`).

## Local mode (no external API)

The `local` profile starts an Ollama model server next to the app:

```
docker compose --profile local up -d
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull bge-m3
```

Then replace the OpenAI block in `.env` with the "Local mode" block from `.env.example`:
`LLM_BASE_URL=http://ollama:11434/v1`, `LLM_MODEL=qwen2.5:7b` (answers, query translation, layout),
`EMBEDDING_MODEL=bge-m3`, `EMBEDDING_DIM=1024`. Vector size changes from 1536 to 1024, so use a separate empty
database (new volume or `DATABASE_URL`) and re-index the knowledge base.

Hardware estimate: for a 7B model, a GPU with 8 GB VRAM (the GPU block in `docker-compose.yml` is commented out;
enable it and install the NVIDIA Container Toolkit) and 16 GB RAM; on CPU it is much slower.

**Quality and speed on a local model were not measured in this repository; that is part of a pilot.**
The figures below apply to the OpenAI models only.

## Quality

All figures come from reproducible runs; details are in `reports/`.

**Answers, held-out test set, 2026-10-30** (`reports/quality-2026-10-30-test.md`; set `test` version
`58926e1cc8cd`: 53 questions in Russian, Kazakh and English, 11 of them without an answer in the knowledge base;
answers `gpt-4o-mini`, judge `gpt-4o`, embeddings `text-embedding-3-small`). The set was built separately and was
not used to tune retrieval or prompts.

| Metric | Result | Threshold in the terms of reference |
|---|---|---|
| Correct answers | 81.0% | at least 75% |
| Partially correct | 11.9% | - |
| Incorrect | 7.1% | at most 10% |
| Answers with a source | 95.2% | at least 95% |
| Cited answers with a gold document as source | 95.0% | at least 90% |
| "No data" on unanswerable questions | 100% (11/11) | 18 of 20 |
| Questions found when parsing the source files | 100% (53/53) | at least 95% |
| Time per question | 4.7 s | 100 questions in 15 min |
| Cost | $0.0003 per question, $0.033 per 100 questions (judge excluded) | - |

Accuracy is judged by a model against the reference answers; the report includes a sample of 10 pairs for manual
checking. The thresholds are set for a 100-question set; this one has 53, so the figures are indicative.

The dev set (55 questions) was used for tuning; its latest run is `reports/quality-2026-10-30-dev.md`
(77.3% correct, 4.5% incorrect).

**Layout on public questionnaires, 2026-10-29** (`reports/layout-2026-10-29-final.md`; model `gpt-4o-mini`):
mode `llm` found 966 of 1096 reference questions (88.1%); 5 of 7 files at 95% or above. Below the threshold:
`hecvat-4-16-github-mirror` (222/334, 66.5%) and `ut-system-3rd-party-intake` (13/16, 81.2%).
Mode `rules` (header rules only): 386 of 724 (53.3%), 3 of 5 files at 95% or above.
Cost of 9 model calls: 0.0163 USD.

## API

Interactive OpenAPI documentation is at `http://localhost:8000/docs` (routes in `src/rfp/api/`: authentication,
knowledge base, fill jobs, logs). The web interface uses the same routes.

## Screenshots

Current interface screenshots (to be updated):

- `docs/screens/review-1440.png` - answer review, desktop
- `docs/screens/review-390.png` - answer review, phone
- `docs/screens/jobs-1440.png` - job list

## Repository layout

```
src/rfp/           service: app.py, config.py, llm.py, query.py, retrieval.py, answering.py, ingest.py
  api/ web/        API routes and web interface (templates, static files, IBM Plex fonts)
  questions/       question detection and DOCX/XLSX layout
  export/          writing answers into the source file and the self-check
  services/        knowledge base, jobs, reference answers
  eval/            quality evaluation (python -m rfp.eval)
  db/ documents/   pgvector schema, document readers
prompts/           answer, judge and layout prompts
data/              fictional knowledge base (kb_src, kb) and the dev set (sets/dev)
scripts/           knowledge base build, layout evaluation
reports/           run reports
docs/              licenses, tuning log, public questionnaire sources, screenshots
tests/             tests
```

## Tests and CI

```
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

CI (GitHub Actions, `.github/workflows/ci.yml`): the same three checks, then `docker compose up -d --wait` and a
request to `/health`. Quality evaluation: `uv run python -m rfp.eval --set dev`.

## Demo limitations

- No brute-force protection for passwords and no CSRF token: only the `SameSite=Lax` cookie.
- The model layout call runs synchronously on upload, so a large file waits for the model.
- The public questionnaires used to measure the layout are not in the repository because of their licenses
  (`data/public/` is in `.gitignore`; sources are listed in `docs/public-questionnaires.md`).
- Quality and speed on a local model have not been measured.
- Background jobs do not resume after a container restart: upload an unfinished job again.
- Some English questions get a Russian answer when the retrieved fragments are in Russian (the terms of reference
  require the question's language). A fix is in progress.

## Licenses

Dependencies, images, the font, htmx and models with their licenses: [docs/licenses.md](docs/licenses.md).
