"""排期联动：前置任务（precedes 出边）改期后自动顺推后续任务的排期。

语义：
- 顺延量 = 前置任务 planned_end 的变化天数（整体平移，保持工期）；
- 链条上 auto_schedule=False 的任务视为手动锁定：不移动、也不再向后传播；
- precedes 建边时已做环检测，此处 seen 集合仅作防御；链长上限 MAX_CHAIN。
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskRelation

MAX_CHAIN = 200


async def propagate(db: AsyncSession, task: Task, old_end, new_end) -> int:
    """任务 planned_end 从 old_end 变为 new_end 后，沿 precedes 链顺推后续任务。返回顺延数量。"""
    if old_end is None or new_end is None or old_end == new_end:
        return 0
    delta = (new_end - old_end).days

    count = 0
    frontier = [task.id]
    seen: set[int] = set()
    while frontier and count < MAX_CHAIN:
        cur = frontier.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        res = await db.execute(
            select(TaskRelation.to_task_id).where(
                TaskRelation.relation_type == "precedes",
                TaskRelation.from_task_id == cur,
            )
        )
        for (succ_id,) in res.all():
            if succ_id in seen or count >= MAX_CHAIN:
                continue
            succ = await db.get(Task, succ_id)
            if succ is None or not succ.auto_schedule:
                continue  # 手动锁定：不移动、不再向后传播
            if succ.planned_start is None or succ.planned_end is None:
                continue  # 无排期不联动
            succ.planned_start = succ.planned_start + timedelta(days=delta)
            succ.planned_end = succ.planned_end + timedelta(days=delta)
            count += 1
            frontier.append(succ.id)
    return count
