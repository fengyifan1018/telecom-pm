import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_login_and_me(client: AsyncClient, seeded_db):
    # Login
    resp = await client.post("/api/auth/login", json={"username": "pm01", "password": "123456"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Get me
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "pm01"
    assert resp.json()["role"] == "pm"


@pytest.mark.asyncio
async def test_debug_user_id_header(client: AsyncClient, seeded_db):
    resp = await client.get("/api/auth/me", headers={"X-User-Id": "1"})
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


@pytest.mark.asyncio
async def test_project_crud_and_init(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "1"}

    # Create project
    resp = await client.post("/api/projects", json={
        "name": "API测试DIA项目",
        "customer_id": 1,
        "product_type": "dia",
        "priority": 2,
        "pm_id": 2,
    }, headers=headers)
    assert resp.status_code == 201
    project = resp.json()
    assert project["status"] == "draft"
    project_id = project["id"]

    # Init project (requires pm/admin, user 2 is pm01)
    pm_headers = {"X-User-Id": "2"}
    resp = await client.post(f"/api/projects/{project_id}/init", headers=pm_headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 26

    # Check phase 1 is active
    phase1_tasks = [t for t in tasks if t["phase"] == "project_init"]
    assert all(t["status"] == "active" for t in phase1_tasks)

    # List tasks
    resp = await client.get(f"/api/tasks?project_id={project_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 26


@pytest.mark.asyncio
async def test_task_flow_actions(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}  # PM

    # Create and init project
    resp = await client.post("/api/projects", json={
        "name": "流转测试",
        "customer_id": 1,
        "product_type": "dia",
    }, headers=headers)
    project_id = resp.json()["id"]
    resp = await client.post(f"/api/projects/{project_id}/init", headers=headers)
    tasks = resp.json()
    task_id = tasks[0]["id"]

    # Submit
    resp = await client.put(f"/api/tasks/{task_id}/submit", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "review"

    # Approve
    resp = await client.put(f"/api/tasks/{task_id}/approve", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    # Check transitions
    resp = await client.get(f"/api/tasks/{task_id}/transitions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # submit + approve


@pytest.mark.asyncio
async def test_comments(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}

    # Create project + init
    resp = await client.post("/api/projects", json={
        "name": "评论测试",
        "customer_id": 1,
        "product_type": "dia",
    }, headers=headers)
    project_id = resp.json()["id"]
    resp = await client.post(f"/api/projects/{project_id}/init", headers=headers)
    task_id = resp.json()[0]["id"]

    # Add comment
    resp = await client.post(f"/api/tasks/{task_id}/comments", json={"content": "测试评论"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["content"] == "测试评论"

    # List comments
    resp = await client.get(f"/api/tasks/{task_id}/comments", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}

    resp = await client.get("/api/dashboard/overview", headers=headers)
    assert resp.status_code == 200
    assert "projects" in resp.json()

    resp = await client.get("/api/dashboard/my-workbench", headers=headers)
    assert resp.status_code == 200
    assert "total" in resp.json()
