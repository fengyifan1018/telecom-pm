from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.task import Task
from app.models.workflow_template import WorkflowTemplate


async def generate_tasks_from_template(db: AsyncSession, project: Project) -> list[Task]:
    result = await db.execute(
        select(WorkflowTemplate).where(
            WorkflowTemplate.product_type == project.product_type,
            WorkflowTemplate.is_active == True,
        )
    )
    template = result.scalars().first()
    if not template:
        raise ValueError(f"No active template for product type: {project.product_type}")

    # 预排期：按依赖关系推算每个阶段的起止（阶段内任务并行，阶段时长取任务最大预估天数）
    phase_end: dict[str, date] = {}
    phase_start: dict[str, date] = {}

    def schedule_phase(defn: dict) -> None:
        key = defn["phase"]
        if key in phase_start:
            return
        for dep in defn.get("depends_on", []):
            for d in template.phases:
                if d["phase"] == dep:
                    schedule_phase(d)
        deps = defn.get("depends_on", [])
        start = max((phase_end[d] for d in deps if d in phase_end), default=None)
        start = start + timedelta(days=1) if start else (project.planned_start or date.today())
        duration = max((t.get("estimated_days", 1) for t in defn.get("tasks", [])), default=1)
        phase_start[key] = start
        phase_end[key] = start + timedelta(days=duration)

    for phase_def in template.phases:
        schedule_phase(phase_def)

    tasks: list[Task] = []
    task_seq = 0
    for phase_def in template.phases:
        phase_key = phase_def["phase"]
        is_first_phase = len(phase_def.get("depends_on", [])) == 0
        start = phase_start[phase_key]

        for task_def in phase_def.get("tasks", []):
            task_seq += 1
            estimated_days = task_def.get("estimated_days", 1)
            task = Task(
                project_id=project.id,
                task_no=f"T-{project.project_no}-{task_seq:03d}",
                title=task_def["title"],
                phase=phase_key,
                status="active" if is_first_phase else "pending",
                is_required=task_def.get("required", True),
                priority=project.priority,
                estimated_days=estimated_days,
                planned_start=start,
                planned_end=start + timedelta(days=estimated_days),
            )
            if is_first_phase:
                task.actual_start = date.today()
            db.add(task)
            tasks.append(task)

    project.status = "active"
    project.actual_start = date.today()
    project.template_id = template.id  # 使用统计

    return tasks
