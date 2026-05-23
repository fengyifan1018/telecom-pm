import pytest
from sqlalchemy import select

from app.models.task import Task
from app.models.project import Project
from app.services.flow_engine import FlowEngine
from app.services.template_service import generate_tasks_from_template


@pytest.mark.asyncio
async def test_full_dia_flow(seeded_db):
    """Test complete DIA workflow: init project, approve all tasks phase by phase."""
    db = seeded_db

    # Create project
    project = Project(
        project_no="PRJ-2026-0001",
        name="测试DIA项目",
        customer_id=1,
        product_type="dia",
        status="draft",
        priority=3,
        sales_id=1,
        pm_id=2,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Init: generate tasks from template
    tasks = await generate_tasks_from_template(db, project)
    await db.commit()
    assert len(tasks) == 26
    assert project.status == "active"

    # Phase 1 tasks should be active
    phase1 = [t for t in tasks if t.phase == "project_init"]
    assert all(t.status == "active" for t in phase1)

    # Phase 2+ should be pending
    phase2 = [t for t in tasks if t.phase == "resource_confirm"]
    assert all(t.status == "pending" for t in phase2)

    # Complete phase 1: submit + approve each task
    engine = FlowEngine(db)
    for t in phase1:
        await engine.transition_task(t, "submit", 2)
        await engine.transition_task(t, "approve", 2)
    await db.commit()

    # Phase 2 should now be active
    result = await db.execute(
        select(Task).where(Task.project_id == project.id, Task.phase == "resource_confirm")
    )
    phase2_refreshed = result.scalars().all()
    assert all(t.status == "active" for t in phase2_refreshed)


@pytest.mark.asyncio
async def test_reject_increments_rework(seeded_db):
    """Rejecting a task should increment rework_count and return to active."""
    db = seeded_db

    project = Project(
        project_no="PRJ-2026-0002",
        name="退回测试",
        customer_id=1,
        product_type="dia",
        status="draft",
        priority=3,
        sales_id=1,
        pm_id=2,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    tasks = await generate_tasks_from_template(db, project)
    await db.commit()

    task = tasks[0]
    engine = FlowEngine(db)
    await engine.transition_task(task, "submit", 2)
    await engine.transition_task(task, "reject", 2, "需要补充方案细节")
    await db.commit()

    assert task.status == "active"
    assert task.rework_count == 1


@pytest.mark.asyncio
async def test_invalid_transition_raises(seeded_db):
    """Invalid state transitions should raise ValueError."""
    db = seeded_db

    project = Project(
        project_no="PRJ-2026-0003",
        name="无效操作测试",
        customer_id=1,
        product_type="dia",
        status="draft",
        priority=3,
        sales_id=1,
        pm_id=2,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    tasks = await generate_tasks_from_template(db, project)
    await db.commit()

    task = tasks[0]  # active
    engine = FlowEngine(db)
    with pytest.raises(ValueError, match="Invalid transition"):
        await engine.transition_task(task, "approve", 2)  # can't approve active task


@pytest.mark.asyncio
async def test_reject_blocks_downstream_phases(seeded_db):
    """Rejecting a task should block active/review tasks in all downstream phases."""
    db = seeded_db

    project = Project(
        project_no="PRJ-2026-0004",
        name="下游阻断测试",
        customer_id=1,
        product_type="dia",
        status="draft",
        priority=3,
        sales_id=1,
        pm_id=2,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    tasks = await generate_tasks_from_template(db, project)
    await db.commit()

    engine = FlowEngine(db)

    # Complete phase 1 (project_init) to activate phase 2 (resource_confirm)
    phase1 = [t for t in tasks if t.phase == "project_init"]
    for t in phase1:
        await engine.transition_task(t, "submit", 2)
        await engine.transition_task(t, "approve", 2)
    await db.commit()

    # Complete phase 2 (resource_confirm) to activate phase 3 (procurement) and phase 4 (field_deploy depends on both)
    result = await db.execute(
        select(Task).where(Task.project_id == project.id, Task.phase == "resource_confirm")
    )
    phase2_tasks = result.scalars().all()
    for t in phase2_tasks:
        await engine.transition_task(t, "submit", 2)
        await engine.transition_task(t, "approve", 2)
    await db.commit()

    # procurement tasks should now be active (depends only on project_init via solution_design)
    result = await db.execute(
        select(Task).where(Task.project_id == project.id, Task.phase == "procurement")
    )
    procurement_tasks = result.scalars().all()
    assert all(t.status == "active" for t in procurement_tasks), "procurement should be active"

    # Submit one procurement task to put it in review
    target = procurement_tasks[0]
    await engine.transition_task(target, "submit", 2)
    await db.commit()
    assert target.status == "review"

    # Now reject the target task — downstream phases of procurement should get blocked
    await engine.transition_task(target, "reject", 2, "采购方案需修改")
    await db.commit()

    assert target.status == "active"
    assert target.rework_count == 1

    # Tasks in field_deploy (depends on procurement) should now be blocked
    result = await db.execute(
        select(Task).where(Task.project_id == project.id, Task.phase == "field_deploy")
    )
    field_tasks = result.scalars().all()
    # field_deploy also depends on resource_confirm; tasks that were active should be blocked
    active_or_review = [t for t in field_tasks if t.status in ("active", "review")]
    assert len(active_or_review) == 0, "downstream field_deploy tasks must be blocked after rejection"
