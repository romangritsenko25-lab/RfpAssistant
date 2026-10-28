import time

import pytest
from openpyxl import load_workbook

from rfp.retrieval import retrieve
from tests.conftest import KB_TEXT

pytestmark = pytest.mark.db

XLSX_PARAMS = {
    "sheet": "Questionnaire",
    "question_col": "B",
    "answer_col": "C",
    "header_row": "2",
    "number_col": "A",
}


def upload_kb(client):
    response = client.post("/api/documents", files={"file": ("backup.md", KB_TEXT.encode(), "text/markdown")})
    assert response.status_code == 201, response.text
    return response.json()


def submit(client, path):
    with path.open("rb") as handle:
        response = client.post("/api/jobs", files={"file": (path.name, handle)}, data=XLSX_PARAMS)
    assert response.status_code == 202, response.text
    return response.json()["id"]


def wait_done(client, job_id):
    deadline = time.time() + 20
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}/status").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def processed_job(client, path):
    upload_kb(client)
    job_id = submit(client, path)
    wait_done(client, job_id)
    return job_id


def test_full_path_upload_review_export(logged_in, questionnaire_xlsx, tmp_path):
    client = logged_in
    upload_kb(client)
    job_id = submit(client, questionnaire_xlsx)

    status = wait_done(client, job_id)
    assert (status["status"], status["done"], status["total"]) == ("done", 3, 3)

    job = client.get(f"/api/jobs/{job_id}").json()
    by_qid = {item["qid"]: item for item in job["items"]}
    assert by_qid["q1"]["status"] == "answered"
    assert by_qid["q1"]["citations"][0]["doc_id"] == "backup"
    assert by_qid["q2"]["status"] == "no_data"
    # A failure on one question does not fail the job: it goes to review with a note.
    assert by_qid["q3"]["status"] == "needs_review"
    assert "model unavailable" in by_qid["q3"]["note"]

    edited = client.patch(f"/api/jobs/{job_id}/answers/q1", json={"text": "We back up nightly at 02:00."})
    assert edited.status_code == 200
    body = edited.json()
    assert (body["status"], body["reviewed_by"]) == ("edited", "admin")
    assert body["text"] == "We back up nightly at 02:00."
    assert body["model_text"] == "Backups run daily."
    approved = client.patch(f"/api/jobs/{job_id}/answers/q2", json={"status": "approved"})
    assert approved.json()["status"] == "approved"

    export = client.get(f"/api/jobs/{job_id}/export")
    assert export.status_code == 200
    out = tmp_path / "out.xlsx"
    out.write_bytes(export.content)
    sheet = load_workbook(out)["Questionnaire"]
    assert sheet["C3"].value.startswith("We back up nightly at 02:00.")
    assert "Backups run daily" not in sheet["C3"].value
    assert sheet["B3"].value == "Do you enforce multi-factor authentication?"


def test_review_validation(logged_in, questionnaire_xlsx):
    client = logged_in
    job_id = processed_job(client, questionnaire_xlsx)
    assert client.patch(f"/api/jobs/{job_id}/answers/q1", json={}).status_code == 422
    assert client.patch(f"/api/jobs/{job_id}/answers/q1", json={"status": "bogus"}).status_code == 422
    assert client.patch(f"/api/jobs/{job_id}/answers/zz", json={"text": "x"}).status_code == 404
    assert client.get("/api/jobs/9999").status_code == 404


def test_bad_uploads_are_rejected(logged_in):
    client = logged_in
    assert client.post("/api/jobs", files={"file": ("a.txt", b"x")}).status_code == 422
    assert client.post("/api/jobs", files={"file": ("a.xlsx", b"not a workbook")}).status_code == 422
    assert client.post("/api/documents", files={"file": ("a.exe", b"x")}).status_code == 422


def test_reference_answer_is_found_by_retrieval(logged_in, questionnaire_xlsx, db_conn, fake_embedder):
    client = logged_in
    job_id = processed_job(client, questionnaire_xlsx)

    # An unreviewed answer cannot become a reference.
    assert client.post(f"/api/jobs/{job_id}/answers/q1/reference").status_code == 409

    text = "Access rights are reviewed every quarter."
    client.patch(f"/api/jobs/{job_id}/answers/q2", json={"text": text})
    saved = client.post(f"/api/jobs/{job_id}/answers/q2/reference")
    assert saved.status_code == 201
    doc_id = saved.json()["doc_id"]
    assert doc_id.startswith("REF-")

    found = retrieve(db_conn, fake_embedder, "Как часто пересматриваются права доступа?", k=1)
    assert found[0].doc_id == doc_id
    assert "reviewed every quarter" in found[0].text

    documents = {d["doc_id"]: d for d in client.get("/api/documents").json()}
    assert documents[doc_id]["kind"] == "reference"
    assert documents[doc_id]["chunks"] == 1
    # Saving again replaces the chunk instead of duplicating it.
    client.post(f"/api/jobs/{job_id}/answers/q2/reference")
    assert {d["doc_id"]: d["chunks"] for d in client.get("/api/documents").json()}[doc_id] == 1

    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert doc_id not in {d["doc_id"] for d in client.get("/api/documents").json()}


def test_logs_record_actions_and_model_requests(logged_in, questionnaire_xlsx):
    client = logged_in
    job_id = processed_job(client, questionnaire_xlsx)
    client.patch(f"/api/jobs/{job_id}/answers/q1", json={"status": "approved"})
    client.get(f"/api/jobs/{job_id}/export")

    actions = client.get("/api/logs/actions", params={"limit": 100}).json()
    names = [entry["action"] for entry in actions["items"]]
    for expected in ("login", "document.upload", "job.create", "answer.edit", "job.export"):
        assert expected in names
    assert actions["total"] == len(names)
    assert all(entry["username"] == "admin" for entry in actions["items"])

    requests = client.get("/api/logs/model-requests", params={"job_id": job_id}).json()
    assert requests["total"] == 3
    answered = next(r for r in requests["items"] if r["qid"] == "q1")
    assert answered["fragments"][0]["doc_id"] == "backup"
    assert answered["fragments"][0]["score"] > 0
    assert (answered["model"], answered["prompt_tokens"], answered["cost_usd"]) == ("gpt-4o-mini", 100, 0.001)
    assert answered["status"] == "answered"
    failed = next(r for r in requests["items"] if r["qid"] == "q3")
    assert "model unavailable" in failed["error"]

    page = client.get("/api/logs/actions", params={"limit": 2, "offset": 1}).json()
    assert len(page["items"]) == 2 and page["offset"] == 1


def test_knowledge_base_upload_delete_reindex(logged_in, api_settings):
    client = logged_in
    result = upload_kb(client)
    assert (result["doc_id"], result["status"]) == ("backup", "indexed")
    assert (api_settings.kb_dir / "backup.md").exists()

    listing = client.get("/api/documents").json()
    assert [(d["doc_id"], d["filename"], d["kind"]) for d in listing] == [("backup", "backup.md", "file")]
    assert listing[0]["chunks"] >= 1 and listing[0]["indexed_at"]
    again = client.post("/api/documents", files={"file": ("backup.md", KB_TEXT.encode())})
    assert again.json()["status"] == "unchanged"

    (api_settings.kb_dir / "extra.md").write_text("# Extra\n\n## S\n\nsome text here\n", "utf-8")
    reindexed = client.post("/api/documents/reindex").json()
    assert {(o["filename"], o["status"]) for o in reindexed} == {
        ("backup.md", "unchanged"),
        ("extra.md", "indexed"),
    }

    assert client.delete("/api/documents/backup").status_code == 204
    assert not (api_settings.kb_dir / "backup.md").exists()
    assert client.delete("/api/documents/backup").status_code == 404
    assert [d["doc_id"] for d in client.get("/api/documents").json()] == ["extra"]


def test_openapi_documents_the_api(client):
    schema = client.get("/openapi.json").json()
    assert {t["name"] for t in schema["tags"]} >= {"auth", "jobs", "knowledge base", "logs"}
    assert "/api/jobs/{job_id}/export" in schema["paths"]
    assert all(op.get("summary") for path in schema["paths"].values() for op in path.values())
