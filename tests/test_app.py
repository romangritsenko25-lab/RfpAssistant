from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from rfp import app as app_module


def test_health_reports_ok_and_manages_connection(monkeypatch):
    conn = MagicMock()
    apply_schema = MagicMock()
    monkeypatch.setattr(app_module.db, "connect", lambda *a, **k: conn)
    monkeypatch.setattr(app_module.db, "apply_schema", apply_schema)

    with TestClient(app_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
    apply_schema.assert_called_once_with(conn)
    conn.cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")
    conn.close.assert_called_once()
