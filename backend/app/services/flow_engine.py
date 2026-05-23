from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskTransition
from app.models.workflow_template import WorkflowTemplate

VALID_TRANSITIONS: dict[tuple[str, str], str] = {
    ("pending", "activate"): "active",
    ("active", "submit"): "review",
    ("review", "approve"): "done",
    ("review", "reject"): "active",
    ("active", "pause"): "paused",
    ("paused", "resume"): "active",
    ("active", "block"): "blocked",
    ("blocked", "unblock"): "active",
    ("active", "cancel"): "cancelled",
    ("pending", "cancel"): "cancelled",
}


class FlowEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def transition_task(self, task: Task, action: str, operator_id: int, remark: str | None = None) -> Task:
        key = (task.status, action)
        new_status = VALID_TRANSITIONS.get(key)
        if new_status is None:
            raise ValueError(f"Invalid transition: {task.status} + {action}")

        old_status = task.status
        task.status = new_status
        task.version += 1
        task.updated_at = datetime.utcnow()

        if new_status == "active" and task.actual_start is None:
            task.actual_start = date.today()
        if new_status == "done":
            task.actual_end = date.today()
        if action == "reject":
            task.rework_count += 1
            await self._on_task_rejected(task)

        transition = TaskTransition(
            task_id=task.id,
            from_status=old_status,
            to_status=new_status,
            operator_id=operator_id,
            remark=remark,
        )
        self.db.add(transition)

        if new_status == "done":
            await self._on_task_done(task)

        return task

    async def _on_task_done(self, task: Task):
        if not await self._is_phase_complete(task.project_id, task.phase):
            return
        await self._activate_next_phases(task.project_id, task.phase)

    async def _is_phase_complete(self, project_id: int, phase: str) -> bool:
        result = await self.db.execute(
            select(Task).where(
                Task.project_id == project_id,
                Task.phase == phase,
                Task.is_required == True,
                Task.status != "done",
            )
        )
        return result.first() is None

    async def _activate_next_phases(self, project_id: int, completed_phase: str):
        from app.models.project import Project

        project = await self.db.get(Project, project_id)
        if not project:
            return

        template = await self._get_active_template(project.product_type)
        if not template:
            return

        for phase_def in template.phases:
            depends_on = phase_def.get("depends_on", [])
            if completed_phase not in depends_on:
                continue
            all_met = True
            for dep in depends_on:
                if not await self._is_phase_complete(project_id, dep):
                    all_met = False
                    break
            if all_met:
                await self._activate_phase(project_id, phase_def["phase"])

        await self._check_project_completion(project)

    async def _activate_phase(self, project_id: int, phase: str):
        result = await self.db.execute(
            select(Task).where(
                Task.project_id == project_id,
                Task.phase == phase,
                Task.status == "pending",
            )
        )
        tasks = result.scalars().all()
        for t in tasks:
            t.status = "active"
            t.actual_start = date.today()
            t.version += 1

    async def _check_project_completion(self, project):
        result = await self.db.execute(
            select(Task).where(
                Task.project_id == project.id,
                Task.is_required == True,
                Task.status.notin_(["done", "cancelled"]),
            )
        )
        if result.first() is None:
            project.status = "completed"
            project.actual_end = date.today()
            from app.services.notification_service import notify
            if project.sales_id:
                await notify(
                    self.db, project.sales_id, "project_completed",
                    f"项目已完成交付: {project.name}",
                    related_project_id=project.id,
                )

    async def _on_task_rejected(self, task: Task):
        """Block downstream active/review tasks when a task is rejected back to rework."""
        from app.models.project import Project

        project = await self.db.get(Project, task.project_id)
        if not project:
            return
        template = await self._get_active_template(project.product_type)
        if not template:
            return

        downstream = self._downstream_phases(template.phases, task.phase)
        if not downstream:
            return

        result = await self.db.execute(
            select(Task).where(
                Task.project_id == task.project_id,
                Task.phase.in_(downstream),
                Task.status.in_(["active", "review"]),
            )
        )
        for t in result.scalars().all():
            t.status = "blocked"
            t.version += 1
            t.updated_at = datetime.utcnow()

    @staticmethod
    def _downstream_phases(phases: list, source: str) -> set[str]:
        """Return all phase keys that transitively depend on source."""
        result: set[str] = set()
        frontier = {source}
        while frontier:
            next_frontier: set[str] = set()
            for phase_def in phases:
                key = phase_def["phase"]
                if key in result:
                    continue
                if set(phase_def.get("depends_on", [])) & frontier:
                    next_frontier.add(key)
            result |= next_frontier
            frontier = next_frontier
        return result

    async def _get_active_template(self, product_type: str) -> WorkflowTemplate | None:
        result = await self.db.execute(
            select(WorkflowTemplate).where(
                WorkflowTemplate.product_type == product_type,
                WorkflowTemplate.is_active == True,
            )
        )
        return result.scalar_one_or_none()
