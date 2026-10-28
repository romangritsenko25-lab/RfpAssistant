"""Command line entry: ``python -m rfp.eval --set dev|test [--limit N]``."""

import argparse
import sys
from datetime import date
from pathlib import Path

from rfp.config import Settings, get_settings
from rfp.eval import dataset
from rfp.eval.metrics import EvalRecord, GoldItem, compute_metrics, extraction_rate
from rfp.eval.report import RunInfo, render_report, report_paths, write_raw
from rfp.eval.runner import run_items
from rfp.llm import OpenAIChatClient

REPORTS_DIR = Path("reports")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rfp.eval", description="Measure answer quality on a question set."
    )
    parser.add_argument("--set", dest="set_name", choices=("dev", "test"), required=True)
    parser.add_argument("--limit", type=int, default=None, help="use only the first N questions")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    folder = dataset.set_dir(args.set_name)
    if not (folder / "gold.jsonl").is_file():
        print(f"No gold.jsonl in {folder}", file=sys.stderr)
        return 1
    settings = get_settings()
    items, version = dataset.load_gold(folder)
    extraction = _measure_extraction(folder, items)
    selected = items[: args.limit] if args.limit else items

    records = _run(settings, selected)
    info = RunInfo(
        set_name=args.set_name,
        set_version=version,
        run_date=date.today(),
        llm_model=settings.llm_model,
        judge_model=settings.judge_model,
        embedding_model=settings.embedding_model,
        top_k=settings.retrieval_top_k,
        confidence_threshold=settings.confidence_threshold,
        limit=args.limit,
    )
    report_path, raw_path = report_paths(REPORTS_DIR, info)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(info, compute_metrics(records), records, extraction), encoding="utf-8"
    )
    write_raw(raw_path, records)
    print(f"Report: {report_path}\nRaw answers: {raw_path}")
    return 0


def _measure_extraction(folder: Path, items: list[GoldItem]) -> dict[str, tuple[int, int]]:
    """Per source file: how many gold questions the production extraction finds."""
    extracted = dataset.extract_set_questions(folder, {item.file for item in items})
    return {
        name: extraction_rate([i.question for i in items if i.file == name], [q.text for q in questions])
        for name, questions in extracted.items()
    }


def _run(settings: Settings, items: list[GoldItem]) -> list[EvalRecord]:
    # Imported here so that unit tests of the evaluation code do not need the database layer.
    from rfp.db import apply_schema, connect
    from rfp.embeddings import get_embedder
    from rfp.ingest import index_folder
    from rfp.retrieval import retrieve

    embedder = get_embedder(settings)
    judge_prompt = settings.judge_prompt_path.read_text(encoding="utf-8")
    llm = OpenAIChatClient(settings)
    judge = OpenAIChatClient(settings, model=settings.judge_model)
    with connect() as conn:
        apply_schema(conn)
        index_folder(conn, embedder, settings.kb_dir)
        return run_items(
            items,
            lambda question: retrieve(conn, embedder, question, settings.retrieval_top_k),
            llm,
            judge,
            settings,
            judge_prompt,
        )


if __name__ == "__main__":
    sys.exit(main())
