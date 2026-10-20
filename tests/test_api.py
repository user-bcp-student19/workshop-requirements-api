import base64
import time
from pathlib import Path
from typing import Iterator

import app.main as main
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def token(username: str = "student", role: str = "STUDENT") -> str:
    raw = f"{username}|{role}|{int(time.time()) + 3600}|WORKSHOP_SECRET_2026"
    return base64.b64encode(raw.encode()).decode()


def headers(username: str = "student", role: str = "STUDENT") -> dict[str, str]:
    return {"Authorization": f"Bearer {token(username, role)}"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as test_client:
        yield test_client


def test_lists_seeded_tasks(client: TestClient) -> None:
    response = client.get("/api/tasks", headers=headers())

    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    assert [task["id"] for task in tasks] == sorted(task["id"] for task in tasks)
    assert all(task["owner"] == "student" for task in tasks)
    assert set(tasks[0]) == {"id", "title", "description", "status", "owner", "priority", "createdAt"}
    assert isinstance(tasks[0]["id"], int)
    assert isinstance(tasks[0]["createdAt"], str)


def test_empty_owner_filter_uses_authenticated_user(client: TestClient) -> None:
    response = client.get("/api/tasks", params={"owner": ""}, headers=headers())

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {task["owner"] for task in response.json()} == {"student"}


def test_creates_task_and_summary(client: TestClient) -> None:
    created = client.post(
        "/api/tasks",
        headers=headers(),
        json={"title": "Add tests", "description": "Improve coverage", "status": "TODO", "priority": "HIGH"},
    )
    summary = client.get("/api/summary", headers=headers())

    assert created.status_code == 201
    assert set(created.json()) == {"id", "title", "description", "status", "owner", "priority", "createdAt"}
    assert created.json()["owner"] == "student"
    assert summary.status_code == 200
    assert summary.json() == {
        "owner": "student",
        "total": 3,
        "byStatus": {"TODO": 2, "IN_PROGRESS": 1},
        "highPriorityOpen": 2,
    }


def test_creates_task_with_default_values(client: TestClient) -> None:
    response = client.post("/api/tasks", headers=headers(), json={"title": "Defaults"})

    assert response.status_code == 201
    assert response.json()["title"] == "Defaults"
    assert response.json()["description"] == ""
    assert response.json()["status"] == "TODO"
    assert response.json()["priority"] == "MEDIUM"
    assert response.json()["owner"] == "student"


def test_summary_for_identity_without_tasks_is_empty(client: TestClient) -> None:
    response = client.get("/api/summary", headers=headers("new-user"))

    assert response.status_code == 200
    assert response.json() == {
        "owner": "new-user",
        "total": 0,
        "byStatus": {},
        "highPriorityOpen": 0,
    }


def test_uploads_requirement_and_returns_metadata(client: TestClient, tmp_path: Path) -> None:
    content = b"Login must be accessible"
    response = client.post(
        "/api/requirements",
        headers=headers(),
        files={"file": ("requirements.txt", content, "text/plain")},
    )

    expected_path = tmp_path / "uploads" / "requirements.txt"
    assert response.status_code == 201
    assert response.json() == {
        "owner": "student",
        "fileName": "requirements.txt",
        "storedAt": str(expected_path),
        "size": len(content),
    }
    assert expected_path.read_bytes() == content


def test_uploads_empty_file_as_zero_bytes(client: TestClient) -> None:
    response = client.post(
        "/api/requirements",
        headers=headers(),
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["size"] == 0


def test_backend_health_returns_upstream_response(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_HEALTH_URL", "http://backend.test/health")

    class FakeResponse:
        status = 200
        data = b'{"status":"UP"}'

    class FakePoolManager:
        def request(self, method: str, url: str, timeout: float) -> FakeResponse:
            assert method == "GET"
            assert url == "http://backend.test/health"
            assert timeout == 3.0
            return FakeResponse()

    monkeypatch.setattr(main.urllib3, "PoolManager", FakePoolManager)
    response = client.get("/api/backend-health", headers=headers())

    assert response.status_code == 200
    assert response.json() == {"requestedBy": "student", "status": 200, "body": '{"status":"UP"}'}


def test_backend_health_preserves_upstream_error_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status = 503
        data = b"temporarily unavailable"

    class FakePoolManager:
        def request(self, method: str, url: str, timeout: float) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(main.urllib3, "PoolManager", FakePoolManager)
    response = client.get("/api/backend-health", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "requestedBy": "student",
        "status": 503,
        "body": "temporarily unavailable",
    }


def test_backend_health_returns_zero_when_upstream_raises(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePoolManager:
        def request(self, method: str, url: str, timeout: float) -> None:
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(main.urllib3, "PoolManager", FakePoolManager)
    response = client.get("/api/backend-health", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "requestedBy": "student",
        "status": 0,
        "body": "upstream unavailable",
    }


@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/api/tasks", {}),
        ("POST", "/api/tasks", {"json": {"title": "Unauthorized"}}),
        ("GET", "/api/summary", {}),
        ("POST", "/api/requirements", {"files": {"file": ("requirements.txt", b"x")}}),
        ("GET", "/api/backend-health", {}),
    ],
)
def test_all_endpoints_reject_invalid_token(
    client: TestClient,
    method: str,
    path: str,
    request_kwargs: dict[str, object],
) -> None:
    response = client.request(method, path, headers={"Authorization": "Bearer invalid"}, **request_kwargs)

    assert response.status_code == 401
    assert response.json()["detail"].startswith("Invalid token:")


def test_create_task_requires_json_body(client: TestClient) -> None:
    response = client.post("/api/tasks", headers=headers())

    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_task_requires_object_body(client: TestClient) -> None:
    response = client.post("/api/tasks", headers=headers(), json=[])

    assert response.status_code == 422
    assert "detail" in response.json()


def test_upload_requires_file_field(client: TestClient) -> None:
    response = client.post("/api/requirements", headers=headers())

    assert response.status_code == 422
    assert "detail" in response.json()