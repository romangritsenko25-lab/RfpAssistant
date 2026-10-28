import pytest

from rfp.ingest import index_file
from rfp.services import jobs
from rfp.services.errors import ConflictError, InvalidInputError
from tests.conftest import KB_TEXT

pytestmark = pytest.mark.db

PARAMS = jobs.JobParams(sheet="Questionnaire", header_row=2, number_col="A")


@pytest.fixture
def kb(db_conn, fake_embedder, tmp_path):
    path = tmp_path / "backup.md"
    path.write_text(KB_TEXT, "utf-8")
    index_file(db_conn, fake_embedder, path)


def create(db_conn, path, params=PARAMS):
    return jobs.create_job(db_conn, "tester", path.name, path.read_bytes(), params)


def test_create_job_extracts_questions_as_queued(db_conn, questionnaire_xlsx):
    job = create(db_conn, questionnaire_xlsx)
    assert (job.status, job.total, job.done) == ("queued", 3, 0)
    detail = jobs.get_job(db_conn, job.id)
    assert [i.status for i in detail.items] == ["pending"] * 3
    assert detail.items[0].number == "IAM-01"


def test_unknown_sheet_and_bad_column_are_invalid_input(db_conn, questionnaire_xlsx):
    with pytest.raises(InvalidInputError, match="Sheet 'Nope' not found"):
        create(db_conn, questionnaire_xlsx, jobs.JobParams(sheet="Nope"))
    with pytest.raises(InvalidInputError, match="column letter"):
        create(db_conn, questionnaire_xlsx, jobs.JobParams(question_col="1; DROP"))


def test_process_job_isolates_failures_and_resumes(
    db_conn, kb, fake_embedder, scripted_llm, api_settings, questionnaire_xlsx
):
    job = create(db_conn, questionnaire_xlsx)
    jobs.process_job(db_conn, fake_embedder, scripted_llm, api_settings, job.id)
    assert scripted_llm.calls == 3
    summary = jobs.get_job_summary(db_conn, job.id)
    assert (summary.status, summary.done) == ("done", 3)

    # A second run touches nothing: only pending questions are processed (restart resume).
    jobs.process_job(db_conn, fake_embedder, scripted_llm, api_settings, job.id)
    assert scripted_llm.calls == 3


def test_export_refused_while_queued(db_conn, questionnaire_xlsx):
    job = create(db_conn, questionnaire_xlsx)
    with pytest.raises(ConflictError):
        jobs.export_job(db_conn, job.id, "tester")


def test_review_of_pending_question_conflicts(db_conn, questionnaire_xlsx):
    job = create(db_conn, questionnaire_xlsx)
    with pytest.raises(ConflictError):
        jobs.review_item(db_conn, job.id, "q1", "tester", text="x")
