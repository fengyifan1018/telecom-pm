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
    template = result.scalar_one_or_none()
    if not template:
        raise ValueError(f"No active template for product type: {project.product_type}")

    tasks: list[Task] = []
    task_seq = 0
    current_date = project.planned_start or date.today()

    for phase_def in template.phases:
        phase_key = phase_def["phase"]
        is_first_phase = len(phase_def.get("depends_on", [])) == 0

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
                planned_start=current_date if is_first_phase else None,
                planned_end=(current_date + timedelta(days=estimated_days)) if is_first_phase else None,
            )
            if is_first_phase:
                task.actual_start = date.today()
            db.add(task)
            tasks.append(task)

    project.status = "active"
    project.actual_start = date.today()

    return tasks
