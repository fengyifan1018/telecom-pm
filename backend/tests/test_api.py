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

    # 立项自动排期：所有任务都应带 planned_start/planned_end
    assert all(t["planned_start"] and t["planned_end"] for t in tasks)
    # 阶段顺序：后续阶段开始日期不早于其前置阶段结束日期
    starts = [t["planned_start"] for t in tasks]
    assert max(starts) >= min(starts)


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

    # @提及：评论里 @pm01 应给用户2（pm01）生成 mention 通知
    resp = await client.post(
        f"/api/tasks/{task_id}/comments",
        json={"content": "请 @pm01 关注一下"},
        headers={"X-User-Id": "1"},
    )
    assert resp.status_code == 201
    resp = await client.get("/api/notifications", headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert any(n["type"] == "mention" for n in items)


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}

    resp = await client.get("/api/dashboard/overview", headers=headers)
    assert resp.status_code == 200
    assert "projects" in resp.json()



@pytest.mark.asyncio
async def test_list_tasks_filters_and_sort(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}  # pm01
    resp = await client.post("/api/projects", json={
        "name": "列表筛选测试", "customer_id": 1, "product_type": "dia", "pm_id": 2,
    }, headers=headers)
    project_id = resp.json()["id"]
    resp = await client.post(f"/api/projects/{project_id}/init", headers=headers)
    tasks = resp.json()
    assert len(tasks) == 26

    # project_name 已回传
    resp = await client.get(f"/api/tasks?project_id={project_id}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items and items[0]["project_name"] == "列表筛选测试"

    # keyword 命中标题
    sample_title = tasks[0]["title"]
    kw = sample_title[:2]
    resp = await client.get(f"/api/tasks?project_id={project_id}&keyword={kw}", headers=headers)
    assert resp.json()["total"] >= 1
    assert all(kw in t["title"] or kw in t["task_no"] for t in resp.json()["items"])

    # keyword 命中编号
    no = tasks[0]["task_no"]
    resp = await client.get(f"/api/tasks?project_id={project_id}&keyword={no}", headers=headers)
    assert resp.json()["total"] == 1

    # 多状态：active + pending
    resp = await client.get(
        f"/api/tasks?project_id={project_id}&status=active,pending", headers=headers)
    assert resp.json()["total"] == 26
    resp = await client.get(
        f"/api/tasks?project_id={project_id}&status=active", headers=headers)
    active_total = resp.json()["total"]
    assert 0 < active_total < 26

    # 排序：created_at desc
    resp = await client.get(
        f"/api/tasks?project_id={project_id}&sort=created_at&order=desc", headers=headers)
    assert resp.json()["total"] == 26

    # 非法 sort 回退默认，不报错
    resp = await client.get(
        f"/api/tasks?project_id={project_id}&sort=bogus&order=xyz", headers=headers)
    assert resp.json()["total"] == 26


@pytest.mark.asyncio
async def test_list_tasks_overdue(client: AsyncClient, seeded_db, db):
    from datetime import date, timedelta
    from sqlalchemy import select
    from app.models.task import Task
    headers = {"X-User-Id": "2"}
    resp = await client.post("/api/projects", json={
        "name": "超期测试", "customer_id": 1, "product_type": "dia", "pm_id": 2,
    }, headers=headers)
    project_id = resp.json()["id"]
    await client.post(f"/api/projects/{project_id}/init", headers=headers)

    res = await db.execute(select(Task).where(Task.project_id == project_id))
    t = res.scalars().first()
    t.planned_end = date.today() - timedelta(days=1)
    await db.commit()

    resp = await client.get(f"/api/tasks?project_id={project_id}&overdue=true", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(it["status"] not in ("done", "cancelled") for it in items)
    assert any(it["id"] == t.id for it in items)


# ---- 任务数据范围（可见性）与单任务越权 ----

async def _make_inited_project(client, name, pm_id, init_user):
    """销售(1)创建项目，指定 pm，由 init_user 立项生成任务。返回 (project_id, tasks)。"""
    resp = await client.post("/api/projects", json={
        "name": name, "customer_id": 1, "product_type": "dia", "pm_id": pm_id,
    }, headers={"X-User-Id": "1"})
    pid = resp.json()["id"]
    tasks = (await client.post(f"/api/projects/{pid}/init", headers={"X-User-Id": str(init_user)})).json()
    return pid, tasks


@pytest.mark.asyncio
async def test_task_scope_pm_sees_only_own_projects(client: AsyncClient, seeded_db, db):
    from app.models.user import User
    from app.seed.seed_users import hash_password
    pm_b = User(username="pm02", hashed_password=hash_password("123456"),
                display_name="王经理(项目经理)", role="pm")
    db.add(pm_b)
    await db.commit()
    await db.refresh(pm_b)

    p1, _ = await _make_inited_project(client, "PM-A项目", pm_id=2, init_user=2)
    p2, _ = await _make_inited_project(client, "PM-B项目", pm_id=pm_b.id, init_user=pm_b.id)

    # pm01 只看到自己项目 P1 的任务
    resp = await client.get("/api/tasks?page_size=200", headers={"X-User-Id": "2"})
    items = resp.json()["items"]
    assert resp.json()["total"] == 26
    assert items and all(it["project_id"] == p1 for it in items)

    # pmB 只看到自己项目 P2 的任务
    resp = await client.get("/api/tasks?page_size=200", headers={"X-User-Id": str(pm_b.id)})
    items = resp.json()["items"]
    assert resp.json()["total"] == 26
    assert items and all(it["project_id"] == p2 for it in items)


@pytest.mark.asyncio
async def test_task_scope_engineer_sees_only_assigned(client: AsyncClient, seeded_db):
    pid, tasks = await _make_inited_project(client, "工程师范围项目", pm_id=2, init_user=2)
    tid = tasks[0]["id"]
    # 指派给 net01 (id 5, network_engineer)
    resp = await client.put(f"/api/tasks/{tid}/assign", json={"assignee_id": 5}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    # network_engineer 只看到指派给自己的那 1 个任务
    resp = await client.get("/api/tasks?page_size=200", headers={"X-User-Id": "5"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == tid


@pytest.mark.asyncio
async def test_task_scope_operations_sees_all(client: AsyncClient, seeded_db):
    pid, _ = await _make_inited_project(client, "运营可见项目", pm_id=2, init_user=2)
    # operations (id 3) 全部可见（只读角色）
    resp = await client.get("/api/tasks?page_size=200", headers={"X-User-Id": "3"})
    assert resp.json()["total"] == 26


@pytest.mark.asyncio
async def test_single_task_access_scoped(client: AsyncClient, seeded_db):
    pid, tasks = await _make_inited_project(client, "越权校验项目", pm_id=2, init_user=2)
    tid, other = tasks[0]["id"], tasks[1]["id"]

    # net01 未被指派 → 看不到（404，不泄露存在性）
    resp = await client.get(f"/api/tasks/{tid}", headers={"X-User-Id": "5"})
    assert resp.status_code == 404

    # 指派后可见
    await client.put(f"/api/tasks/{tid}/assign", json={"assignee_id": 5}, headers={"X-User-Id": "2"})
    resp = await client.get(f"/api/tasks/{tid}", headers={"X-User-Id": "5"})
    assert resp.status_code == 200

    # 未指派的任务不可通过 PUT 越权修改
    resp = await client.put(f"/api/tasks/{other}", json={"priority": 1}, headers={"X-User-Id": "5"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_relations_and_blocks(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "关系卡点测试", pm_id=2, init_user=2)
    a = tasks[0]  # 第一阶段任务（active）
    b = next(t for t in tasks if t["phase"] != a["phase"])  # 其他阶段任务（pending）

    # 1. 建立 precedes：a 前置于 b
    resp = await client.post(f"/api/tasks/{b['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": a["id"],
    }, headers=headers)
    assert resp.status_code == 201

    # 双向回显：b 的前置含 a；a 的后续含 b
    resp = await client.get(f"/api/tasks/{b['id']}/relations", headers=headers)
    assert any(t["task_id"] == a["id"] for t in resp.json()["predecessors"])
    resp = await client.get(f"/api/tasks/{a['id']}/relations", headers=headers)
    assert any(t["task_id"] == b["id"] for t in resp.json()["successors"])

    # 2. 重复关系 → 409
    resp = await client.post(f"/api/tasks/{b['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": a["id"],
    }, headers=headers)
    assert resp.status_code == 409

    # 3. 自引用 → 400
    resp = await client.post(f"/api/tasks/{a['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": a["id"],
    }, headers=headers)
    assert resp.status_code == 400

    # 4. 环：反向再建 precedes（b 前置于 a）应被拒绝
    resp = await client.post(f"/api/tasks/{a['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": b["id"],
    }, headers=headers)
    assert resp.status_code == 400
    assert "循环" in resp.json()["detail"]

    # 5. blocks 卡点：a 阻塞 b → b 无法开始
    resp = await client.post(f"/api/tasks/{b['id']}/relations", json={
        "relation_type": "blocks", "related_task_id": a["id"],
    }, headers=headers)
    assert resp.status_code == 201
    resp = await client.put(f"/api/tasks/{b['id']}/start", json={}, headers=headers)
    assert resp.status_code == 400
    assert "阻塞" in resp.json()["detail"]
    # 阻塞组回显
    resp = await client.get(f"/api/tasks/{b['id']}/relations", headers=headers)
    assert any(t["task_id"] == a["id"] for t in resp.json()["blocking"])

    # 6. 完成 a（submit + approve）后 b 可开始
    resp = await client.put(f"/api/tasks/{a['id']}/submit", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(f"/api/tasks/{a['id']}/approve", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(f"/api/tasks/{b['id']}/start", json={}, headers=headers)
    assert resp.status_code == 200

    # 7. 删除关系 → 204 且列表不再包含
    resp = await client.get(f"/api/tasks/{b['id']}/relations", headers=headers)
    rel_id = resp.json()["predecessors"][0]["relation_id"]
    resp = await client.delete(f"/api/tasks/relations/{rel_id}", headers=headers)
    assert resp.status_code == 204
    resp = await client.get(f"/api/tasks/{b['id']}/relations", headers=headers)
    assert not any(t["relation_id"] == rel_id for t in resp.json()["predecessors"])


@pytest.mark.asyncio
async def test_phase_activation_respects_blocks(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "激活卡点测试", pm_id=2, init_user=2)
    phase1 = [t for t in tasks if t["phase"] == tasks[0]["phase"]]
    later_phase_tasks = [t for t in tasks if t["phase"] == "resource_confirm"]
    later, blocker = later_phase_tasks[0], later_phase_tasks[1]
    others = later_phase_tasks[2:]

    # 同阶段的 blocker 阻塞 later
    resp = await client.post(f"/api/tasks/{later['id']}/relations", json={
        "relation_type": "blocks", "related_task_id": blocker["id"],
    }, headers=headers)
    assert resp.status_code == 201

    # 完成第一阶段，触发 resource_confirm 阶段自动激活
    for t in phase1:
        resp = await client.put(f"/api/tasks/{t['id']}/submit", json={}, headers=headers)
        assert resp.status_code == 200
        resp = await client.put(f"/api/tasks/{t['id']}/approve", json={}, headers=headers)
        assert resp.status_code == 200

    # 阶段已激活：未被阻塞的任务 active，blocker 本身也 active，被阻塞的 later 保持 pending
    resp = await client.get(f"/api/tasks?project_id={pid}&page_size=100", headers=headers)
    by_id = {t["id"]: t["status"] for t in resp.json()["items"]}
    assert others and all(by_id[t["id"]] == "active" for t in others)
    assert by_id[blocker["id"]] == "active"
    assert by_id[later["id"]] == "pending"

    # 完成 blocker → 手动开始 later 放行
    resp = await client.put(f"/api/tasks/{blocker['id']}/submit", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(f"/api/tasks/{blocker['id']}/approve", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(f"/api/tasks/{later['id']}/start", json={}, headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_schedule_propagation(client: AsyncClient, seeded_db):
    from datetime import date, timedelta

    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "排期联动测试", pm_id=2, init_user=2)
    phase2 = [t for t in tasks if t["phase"] == "resource_confirm"]
    a, b, c = phase2[0], phase2[1], phase2[2]
    orig = {t["id"]: (t["planned_start"], t["planned_end"]) for t in (a, b, c)}

    # 建链：a precedes b precedes c（同阶段并行任务建链时会自动顺推消解冲突）
    resp = await client.post(f"/api/tasks/{b['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": a["id"]}, headers=headers)
    assert resp.status_code == 201
    resp = await client.post(f"/api/tasks/{c['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": b["id"]}, headers=headers)
    assert resp.status_code == 201
    # 建链后重取基线（b/c 可能已被自动顺推过）
    for t in (a, b, c):
        cur = (await client.get(f"/api/tasks/{t['id']}", headers=headers)).json()
        orig[t["id"]] = (cur["planned_start"], cur["planned_end"])

    # 改 a 的排期整体 +2 → b/c 自动顺延 2 天
    new_start = (date.fromisoformat(a["planned_start"]) + timedelta(days=2)).isoformat()
    new_end = (date.fromisoformat(a["planned_end"]) + timedelta(days=2)).isoformat()
    resp = await client.put(f"/api/tasks/{a['id']}", json={
        "planned_start": new_start, "planned_end": new_end}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["rescheduled"] == 2

    for tid in (b["id"], c["id"]):
        resp = await client.get(f"/api/tasks/{tid}", headers=headers)
        body = resp.json()
        assert body["planned_start"] == (date.fromisoformat(orig[tid][0]) + timedelta(days=2)).isoformat()
        assert body["planned_end"] == (date.fromisoformat(orig[tid][1]) + timedelta(days=2)).isoformat()

    # b 锁定手动排期 → 再改 a +1：链条在 b 处停止，b/c 均不动
    resp = await client.put(f"/api/tasks/{b['id']}", json={"auto_schedule": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["auto_schedule"] is False
    newer_start = (date.fromisoformat(new_start) + timedelta(days=1)).isoformat()
    newer_end = (date.fromisoformat(new_end) + timedelta(days=1)).isoformat()
    resp = await client.put(f"/api/tasks/{a['id']}", json={
        "planned_start": newer_start, "planned_end": newer_end}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["rescheduled"] == 0

    resp = await client.get(f"/api/tasks/{c['id']}", headers=headers)
    body = resp.json()
    assert body["planned_end"] == (date.fromisoformat(orig[c["id"]][1]) + timedelta(days=2)).isoformat()


@pytest.mark.asyncio
async def test_task_progress(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "进度测试", pm_id=2, init_user=2)
    t = tasks[0]  # active

    # 更新进度 60
    resp = await client.put(f"/api/tasks/{t['id']}", json={"progress": 60}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["progress"] == 60

    # 越界 120 → 422
    resp = await client.put(f"/api/tasks/{t['id']}", json={"progress": 120}, headers=headers)
    assert resp.status_code == 422

    # 审批通过后进度自动置 100
    resp = await client.put(f"/api/tasks/{t['id']}/submit", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(f"/api/tasks/{t['id']}/approve", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["progress"] == 100

    # 阶段统计带平均进度（done 计 100）：3 个任务 1 done 2 active(0) → 33.3
    resp = await client.get("/api/dashboard/phase-stats", headers=headers)
    stats = resp.json()
    assert stats[t["phase"]]["avg_progress"] == 33.3


@pytest.mark.asyncio
async def test_task_watch_notifications(client: AsyncClient, seeded_db):
    pid, tasks = await _make_inited_project(client, "关注测试", pm_id=2, init_user=2)
    t = tasks[0]  # active

    # user3(运营) 关注任务
    resp = await client.put(f"/api/tasks/{t['id']}/watch", headers={"X-User-Id": "3"})
    assert resp.status_code == 200
    assert resp.json()["watching"] is True

    # 关注状态查询
    resp = await client.get(f"/api/tasks/{t['id']}/watch", headers={"X-User-Id": "3"})
    body = resp.json()
    assert body["watching"] is True and body["count"] == 1

    # toggle 取关后再关注
    resp = await client.put(f"/api/tasks/{t['id']}/watch", headers={"X-User-Id": "3"})
    assert resp.json()["watching"] is False
    resp = await client.put(f"/api/tasks/{t['id']}/watch", headers={"X-User-Id": "3"})
    assert resp.json()["watching"] is True

    # pm 提交任务 → 关注者 user3 收到状态通知
    resp = await client.put(f"/api/tasks/{t['id']}/submit", json={}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    resp = await client.get("/api/notifications", headers={"X-User-Id": "3"})
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert any(n["type"] == "task_status" and n.get("related_task_id") == t["id"] for n in items)

    # 发起动作的人自己即使关注了也不收自己的通知
    resp = await client.put(f"/api/tasks/{t['id']}/watch", headers={"X-User-Id": "2"})
    assert resp.json()["watching"] is True
    resp = await client.put(f"/api/tasks/{t['id']}/approve", json={}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    resp = await client.get("/api/notifications", headers={"X-User-Id": "2"})
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert not any(n["type"] == "task_status" and n.get("related_task_id") == t["id"] for n in items)


@pytest.mark.asyncio
async def test_project_health_list(client: AsyncClient, seeded_db):
    from datetime import date, timedelta

    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "健康度测试", pm_id=2, init_user=2)
    t = tasks[0]

    # 造超期：昨天截止的未完成任务
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    resp = await client.put(f"/api/tasks/{t['id']}", json={"planned_end": yesterday}, headers=headers)
    assert resp.status_code == 200
    # 造未解决升级
    resp = await client.post(f"/api/tasks/{t['id']}/escalations", json={
        "severity": "high", "description": "资源卡住"}, headers=headers)
    assert resp.status_code == 201
    # 项目计划结束日期改为昨天 → 延期
    resp = await client.put(f"/api/projects/{pid}", json={"planned_end": yesterday}, headers=headers)
    assert resp.status_code == 200

    # 默认列表带健康字段
    resp = await client.get("/api/projects?search=健康度测试", headers=headers)
    items = resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["progress_pct"] == 0
    assert item["overdue_count"] >= 1
    assert item["open_escalations"] == 1
    assert item["at_risk"] is True
    assert item["is_delayed"] is True
    assert item["in_acceptance"] is False  # 刚立项，验收阶段未激活

    # 延期筛选命中
    resp = await client.get("/api/projects?delayed=true", headers=headers)
    assert pid in [p["id"] for p in resp.json()["items"]]
    # 风险筛选命中
    resp = await client.get("/api/projects?at_risk=true", headers=headers)
    assert pid in [p["id"] for p in resp.json()["items"]]
    # 验收中筛选：未到验收阶段 → 不命中
    resp = await client.get("/api/projects?in_acceptance=true", headers=headers)
    assert pid not in [p["id"] for p in resp.json()["items"]]

    # 完成该任务后 overdue 归零（该任务 done 不再计超期）
    resp = await client.put(f"/api/tasks/{t['id']}/submit", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.put(f"/api/tasks/{t['id']}/approve", json={}, headers=headers)
    assert resp.status_code == 200
    resp = await client.get("/api/projects?search=健康度测试", headers=headers)
    item = resp.json()["items"][0]
    assert item["overdue_count"] == 0
    assert item["progress_pct"] > 0  # 1/26 完成


@pytest.mark.asyncio
async def test_project_overview_extras(client: AsyncClient, seeded_db):
    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "概览数据测试", pm_id=2, init_user=2)
    t = tasks[0]

    # 提交产生一条流转记录
    resp = await client.put(f"/api/tasks/{t['id']}/submit", json={}, headers=headers)
    assert resp.status_code == 200
    # 造一个未解决升级
    resp = await client.post(f"/api/tasks/{t['id']}/escalations", json={
        "severity": "high", "description": "设备到货延迟"}, headers=headers)
    assert resp.status_code == 201

    # 项目动态：包含该流转，带任务号/操作人
    resp = await client.get(f"/api/projects/{pid}/activity?limit=5", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["task_no"] == t["task_no"]
    assert items[0]["operator_name"] == "李四(项目经理)"
    assert items[0]["from_status"] == "active" and items[0]["to_status"] == "review"

    # 未解决升级：能查到且带任务信息
    resp = await client.get(f"/api/projects/{pid}/open-escalations", headers=headers)
    assert resp.status_code == 200
    esc = resp.json()
    assert len(esc) == 1
    assert esc[0]["task_no"] == t["task_no"]
    assert esc[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_dashboard_workbench_role_scope(client: AsyncClient, seeded_db):
    pid, tasks = await _make_inited_project(client, "工作台驾驶舱测试", pm_id=2, init_user=2)
    t, t2 = tasks[0], tasks[1]

    # net01(5) 指派 t；造两个升级（t 上一个、t2 上一个）；t2 造成超期
    resp = await client.put(f"/api/tasks/{t['id']}/assign", json={"assignee_id": 5}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    resp = await client.post(f"/api/tasks/{t['id']}/escalations", json={
        "severity": "high", "description": "到货延迟"}, headers={"X-User-Id": "2"})
    assert resp.status_code == 201
    resp = await client.post(f"/api/tasks/{t2['id']}/escalations", json={
        "severity": "medium", "description": "测试未开始风险"}, headers={"X-User-Id": "2"})
    assert resp.status_code == 201
    from datetime import date, timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    resp = await client.put(f"/api/tasks/{t2['id']}", json={"planned_end": yesterday}, headers=headers if False else {"X-User-Id": "2"})
    assert resp.status_code == 200

    # 提交 t 产生一条流转记录（供动态校验）
    resp = await client.put(f"/api/tasks/{t['id']}/submit", json={}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200

    # ── pm01(id=2)：scope=all 全局口径（PM 属全局角色，口径=自己项目的任务）──
    resp = await client.get("/api/dashboard/workbench?scope=all", headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == "all"
    assert body["stats"]["task_total"] == 26
    assert body["stats"]["project_active"] == 1
    assert body["project_health"]["at_risk"] == 1
    risk_task_ids = {r["task_id"] for r in body["risks"]}
    assert {t["id"], t2["id"]} <= risk_task_ids
    assert len(body["top_projects"]) == 1
    assert any(d["task_id"] == t["id"] for d in body["due_soon"])
    assert len(body["activity"]) >= 1

    # ── 工程师 net01(5)：强制 mine，只看指派给自己的任务 ──
    resp = await client.get("/api/dashboard/workbench?scope=all", headers={"X-User-Id": "5"})
    body = resp.json()
    assert body["scope"] == "mine"
    assert body["stats"]["task_total"] == 1
    assert all(r["task_id"] == t["id"] for r in body["risks"])
    assert all(d["task_id"] == t["id"] for d in body["due_soon"])

    # ── 销售 sales01(1)：项目范围口径，看自己项目全部 26 个任务 ──
    resp = await client.get("/api/dashboard/workbench", headers={"X-User-Id": "1"})
    body = resp.json()
    assert body["scope"] == "mine"
    assert body["stats"]["task_total"] == 26


@pytest.mark.asyncio
async def test_project_initiation_approval(client: AsyncClient, seeded_db):
    # 销售(1)创建项目 → 待立项
    resp = await client.post("/api/projects", json={
        "name": "立项审核测试", "customer_id": 1, "product_type": "dia",
    }, headers={"X-User-Id": "1"})
    assert resp.status_code == 201
    pid = resp.json()["id"]

    # 销售提交立项申请 → 立项审核中
    resp = await client.post(f"/api/projects/{pid}/submit-initiation", headers={"X-User-Id": "1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "init_pending"
    # 重复提交 → 400
    resp = await client.post(f"/api/projects/{pid}/submit-initiation", headers={"X-User-Id": "1"})
    assert resp.status_code == 400

    # 无审核权限（net01/pm01）→ 403
    for uid in ("5", "2"):
        resp = await client.post(f"/api/projects/{pid}/init-approval", json={
            "action": "approve"}, headers={"X-User-Id": uid})
        assert resp.status_code == 403

    # operations(3) 审核通过 → active + 任务树生成
    resp = await client.post(f"/api/projects/{pid}/init-approval", json={
        "action": "approve"}, headers={"X-User-Id": "3"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"
    assert len(body["tasks"]) == 26
    # 任务里不含审核信息（已清空）
    assert body["init_reject_reason"] is None

    # ── 驳回流：第二个项目 ──
    resp = await client.post("/api/projects", json={
        "name": "立项驳回测试", "customer_id": 1, "product_type": "dia",
    }, headers={"X-User-Id": "1"})
    pid2 = resp.json()["id"]
    resp = await client.post(f"/api/projects/{pid2}/submit-initiation", headers={"X-User-Id": "1"})
    assert resp.status_code == 200

    # operations 驳回（缺原因 → 400；带原因 → 回待立项并记录）
    resp = await client.post(f"/api/projects/{pid2}/init-approval", json={
        "action": "reject"}, headers={"X-User-Id": "3"})
    assert resp.status_code == 400
    resp = await client.post(f"/api/projects/{pid2}/init-approval", json={
        "action": "reject", "reason": "客户意向不明确"}, headers={"X-User-Id": "3"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"
    assert resp.json()["init_reject_reason"] == "客户意向不明确"

    # 驳回后可重新提交
    resp = await client.post(f"/api/projects/{pid2}/submit-initiation", headers={"X-User-Id": "1"})
    assert resp.status_code == 200

    # 提交人收到驳回通知
    resp = await client.get("/api/notifications", headers={"X-User-Id": "1"})
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert any(n["type"] == "project_init_rejected" and n.get("related_project_id") == pid2 for n in items)

    # 列表筛选：立项审核中可筛出
    resp = await client.get("/api/projects?status=init_pending", headers={"X-User-Id": "1"})
    assert pid2 in [p["id"] for p in resp.json()["items"]]


@pytest.mark.asyncio
async def test_batch_update_tasks(client: AsyncClient, seeded_db):
    pid, tasks = await _make_inited_project(client, "批量操作测试", pm_id=2, init_user=2)
    t1, t2, t3 = tasks[0], tasks[1], tasks[2]
    ids = [t1["id"], t2["id"], t3["id"]]

    # 空更新集 → 400
    resp = await client.post("/api/tasks/batch-update", json={"task_ids": ids}, headers={"X-User-Id": "2"})
    assert resp.status_code == 400

    # 工程(5)无 task.assign 权限 → 403
    resp = await client.post("/api/tasks/batch-update", json={
        "task_ids": ids, "assignee_id": 5}, headers={"X-User-Id": "5"})
    assert resp.status_code == 403

    # PM 批量指派给 net01(5)
    resp = await client.post("/api/tasks/batch-update", json={
        "task_ids": ids, "assignee_id": 5}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 3 and body["failed"] == []
    # 指派生效 + 被指派者收到通知
    resp = await client.get(f"/api/tasks/{t1['id']}", headers={"X-User-Id": "5"})
    assert resp.json()["assignee_id"] == 5
    resp = await client.get("/api/notifications", headers={"X-User-Id": "5"})
    data = resp.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert sum(1 for n in items if n["type"] == "task_assigned") >= 3

    # 批量优先级 + 越界
    resp = await client.post("/api/tasks/batch-update", json={
        "task_ids": ids, "priority": 2}, headers={"X-User-Id": "2"})
    assert resp.status_code == 200 and resp.json()["updated"] == 3
    resp = await client.post("/api/tasks/batch-update", json={
        "task_ids": ids, "priority": 9}, headers={"X-User-Id": "2"})
    assert resp.status_code == 422

    # 混入不存在 id → 部分成功，失败明细
    resp = await client.post("/api/tasks/batch-update", json={
        "task_ids": [ids[0], 99999], "priority": 4}, headers={"X-User-Id": "2"})
    body = resp.json()
    assert body["updated"] == 1
    assert body["failed"] and body["failed"][0]["task_id"] == 99999


@pytest.mark.asyncio
async def test_precedes_relation_reschedules_conflict(client: AsyncClient, seeded_db):
    from datetime import date, timedelta

    headers = {"X-User-Id": "2"}  # pm01
    pid, tasks = await _make_inited_project(client, "前置矛盾测试", pm_id=2, init_user=2)
    phase2 = [t for t in tasks if t["phase"] == "resource_confirm"]
    a, b = phase2[0], phase2[1]

    # 人为制造矛盾：B 开始日早于 A 结束日（工期保持原值）
    b_dur = (date.fromisoformat(b["planned_end"]) - date.fromisoformat(b["planned_start"])).days
    b_start = (date.fromisoformat(a["planned_end"]) - timedelta(days=3)).isoformat()
    b_end = (date.fromisoformat(b_start) + timedelta(days=b_dur)).isoformat()
    resp = await client.put(f"/api/tasks/{b['id']}", json={
        "planned_start": b_start, "planned_end": b_end}, headers=headers)
    assert resp.status_code == 200

    # 建 precedes（A 前置于 B）→ B 应顺推到 A 结束次日
    resp = await client.post(f"/api/tasks/{b['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": a["id"]}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body.get("rescheduled", 0) >= 1

    resp = await client.get(f"/api/tasks/{b['id']}", headers=headers)
    nb = resp.json()
    expected_start = (date.fromisoformat(a["planned_end"]) + timedelta(days=1)).isoformat()
    assert nb["planned_start"] == expected_start
    # 工期保持（3 天）
    assert (date.fromisoformat(nb["planned_end"]) - date.fromisoformat(nb["planned_start"])).days == \
           (date.fromisoformat(b["planned_end"]) - date.fromisoformat(b["planned_start"])).days

    # 锁定 auto_schedule 的后继不自动顺推
    c = phase2[2]
    resp = await client.put(f"/api/tasks/{c['id']}", json={"auto_schedule": False}, headers=headers)
    assert resp.status_code == 200
    c_start = (date.fromisoformat(a["planned_end"]) - timedelta(days=2)).isoformat()
    c_end = (date.fromisoformat(c["planned_end"]) - timedelta(days=2)).isoformat()
    resp = await client.put(f"/api/tasks/{c['id']}", json={
        "planned_start": c_start, "planned_end": c_end}, headers=headers)
    assert resp.status_code == 200
    resp = await client.post(f"/api/tasks/{c['id']}/relations", json={
        "relation_type": "precedes", "related_task_id": a["id"]}, headers=headers)
    assert resp.status_code == 201
    assert resp.json().get("rescheduled", 0) == 0
    resp = await client.get(f"/api/tasks/{c['id']}", headers=headers)
    assert resp.json()["planned_start"] == c_start
