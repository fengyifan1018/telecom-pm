# 任务列表视图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有「任务看板」页内新增一个全局可筛选/排序/分页的任务列表视图，与看板通过顶部切换共存，支持点行打开抽屉与行内快捷操作。

**Architecture:** 后端 `GET /api/tasks` 扩展可选筛选/排序参数并回传 `project_name`（向后兼容）。前端把 `TaskKanban.vue` 升级为「任务」页容器：持有共享筛选状态与 `看板|列表` 切换，看板沿用原逻辑，列表抽到新组件 `TaskListView.vue`（服务端分页+排序+行内操作+复用 `TaskDrawer`）。

**Tech Stack:** 后端 FastAPI + SQLAlchemy 2.0 async + pytest；前端 Vue 3 + Element Plus + Pinia + Vite。

---

## 重要前置说明

- **后端测试环境**：`backend/tests/test_api.py` 中的流转类用例用 `X-User-Id` 头走 DEBUG 鉴权，可正常跑。运行 pytest 前确认用项目自带虚拟环境：`backend/.venv/bin/python -m pytest`（无系统 python）。本计划新增的 list 过滤用例同样走 `X-User-Id`，不依赖 RBAC 种子权限。
- **前端无测试运行器**（package.json 无 vitest/jest）。前端任务以 `npm run build` 通过 + 手动验证为准，不写自动化测试。

## File Structure

- `backend/app/services/task_service.py` — 修改 `list_tasks`：增 `keyword/priority/overdue/sort/order` 参数，多值 `status`，回传 `project_name`。
- `backend/app/api/tasks.py` — 修改 `GET /api/tasks`：新增同名 query 参数并透传。
- `backend/tests/test_api.py` — 新增 list 过滤/排序用例。
- `frontend/src/utils/constants.js` — 新增 `PRIORITY_MAP`。
- `frontend/src/components/TaskListView.vue` — **新建**：列表视图组件（接收 `filters` prop，自管分页/排序/抽屉/行内操作）。
- `frontend/src/views/TaskKanban.vue` — 改造为「任务」页容器：共享筛选栏 + `看板|列表` 切换。
- `frontend/src/components/Layout.vue` — 菜单文案「任务看板」→「任务」。

---

## Task 1: 后端 — 扩展 list_tasks 筛选/排序/project_name

**Files:**
- Modify: `backend/app/services/task_service.py:12-75`
- Modify: `backend/app/api/tasks.py:22-50`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_api.py` 末尾追加。该用例建项目并立项（DIA 模板 26 个任务），然后验证新参数。

```python
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

    # keyword 命中标题（立项阶段任务标题含“立项”用其一）
    sample_title = tasks[0]["title"]
    kw = sample_title[:2]
    resp = await client.get(f"/api/tasks?project_id={project_id}&keyword={kw}", headers=headers)
    assert resp.json()["total"] >= 1
    assert all(kw in t["title"] or kw in t["task_no"] for t in resp.json()["items"])

    # keyword 命中编号
    no = tasks[0]["task_no"]
    resp = await client.get(f"/api/tasks?project_id={project_id}&keyword={no}", headers=headers)
    assert resp.json()["total"] == 1

    # 多状态：active + pending（立项后阶段1为active，其余pending）
    resp = await client.get(
        f"/api/tasks?project_id={project_id}&status=active,pending", headers=headers)
    assert resp.json()["total"] == 26
    resp = await client.get(
        f"/api/tasks?project_id={project_id}&status=active", headers=headers)
    active_total = resp.json()["total"]
    assert 0 < active_total < 26

    # 排序：按 created_at desc 不报错且数量一致
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

    # 人为把一个任务的 planned_end 设为昨天
    res = await db.execute(select(Task).where(Task.project_id == project_id))
    t = res.scalars().first()
    t.planned_end = date.today() - timedelta(days=1)
    await db.commit()

    resp = await client.get(f"/api/tasks?project_id={project_id}&overdue=true", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(it["status"] not in ("done", "cancelled") for it in items)
    assert any(it["id"] == t.id for it in items)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api.py::test_list_tasks_filters_and_sort tests/test_api.py::test_list_tasks_overdue -v`
Expected: FAIL（`KeyError: 'project_name'` 或 422/未识别参数）

- [ ] **Step 3: 修改 `task_service.list_tasks`**

将 `backend/app/services/task_service.py` 顶部 import 改为：

```python
import re
from datetime import date

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskTransition
from app.models.project import Project
from app.models.comment import Comment
from app.models.user import User
from app.services.notification_service import notify
```

在 `list_tasks` 之前新增排序白名单常量：

```python
SORT_FIELDS = {
    "planned_end": Task.planned_end,
    "priority": Task.priority,
    "created_at": Task.created_at,
}
```

将整个 `list_tasks` 函数替换为：

```python
async def list_tasks(
    db: AsyncSession,
    project_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    phase: str | None = None,
    page: int = 1,
    page_size: int = 50,
    scope_assignee_id: int | None = None,  # scope: field/procurement only see own tasks
    sales_project_ids: list[int] | None = None,  # scope: sales only see own projects' tasks
    keyword: str | None = None,
    priority: int | None = None,
    overdue: bool = False,
    sort: str | None = None,
    order: str = "asc",
) -> tuple[list[dict], int]:
    assignee = User.__table__.alias("assignee")
    project = Project.__table__.alias("project")
    query = (
        select(
            Task,
            assignee.c.display_name.label("assignee_name"),
            project.c.name.label("project_name"),
        )
        .outerjoin(assignee, Task.assignee_id == assignee.c.id)
        .outerjoin(project, Task.project_id == project.c.id)
    )
    count_query = select(func.count()).select_from(Task)

    conditions = []
    if sales_project_ids is not None:
        if sales_project_ids:
            conditions.append(Task.project_id.in_(sales_project_ids))
        else:
            conditions.append(Task.project_id == -1)  # no projects → no tasks
    if scope_assignee_id:
        conditions.append(Task.assignee_id == scope_assignee_id)
    elif assignee_id:
        conditions.append(Task.assignee_id == assignee_id)
    if project_id:
        conditions.append(Task.project_id == project_id)
    if status:
        statuses = [s for s in status.split(",") if s]
        if len(statuses) > 1:
            conditions.append(Task.status.in_(statuses))
        elif statuses:
            conditions.append(Task.status == statuses[0])
    if phase:
        conditions.append(Task.phase == phase)
    if keyword:
        kw = f"%{keyword}%"
        conditions.append(or_(Task.title.like(kw), Task.task_no.like(kw)))
    if priority:
        conditions.append(Task.priority == priority)
    if overdue:
        conditions.append(Task.planned_end < date.today())
        conditions.append(Task.status.notin_(["done", "cancelled"]))

    for cond in conditions:
        query = query.where(cond)
        count_query = count_query.where(cond)

    total = (await db.execute(count_query)).scalar() or 0

    sort_col = SORT_FIELDS.get(sort)
    if sort_col is not None:
        query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    else:
        query = query.order_by(Task.id)
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = []
    for task, assignee_name, project_name in result.all():
        d = {
            "id": task.id,
            "project_id": task.project_id,
            "project_name": project_name,
            "task_no": task.task_no,
            "title": task.title,
            "phase": task.phase,
            "status": task.status,
            "is_required": task.is_required,
            "assignee_id": task.assignee_id,
            "assignee_name": assignee_name,
            "reviewer_id": task.reviewer_id,
            "priority": task.priority,
            "planned_start": task.planned_start,
            "planned_end": task.planned_end,
            "actual_start": task.actual_start,
            "actual_end": task.actual_end,
            "rework_count": task.rework_count,
            "created_at": task.created_at,
        }
        items.append(d)
    return items, total
```

- [ ] **Step 4: 修改 `GET /api/tasks` 端点透传新参数**

在 `backend/app/api/tasks.py` 的 `list_tasks` 端点（22-50 行）签名中，在 `phase` 之后、`page` 之前插入新参数，并在调用 service 时传入：

```python
@router.get("")
async def list_tasks(
    project_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
    phase: str | None = None,
    keyword: str | None = None,
    priority: int | None = None,
    overdue: bool = False,
    sort: str | None = None,
    order: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scope = current_user.id if current_user.role in ("procurement", "field_engineer") else None
    sales_scope_ids: list[int] | None = None
    if current_user.role == "sales":
        from sqlalchemy import select as _select
        from app.models.project import Project as _Project
        res = await db.execute(_select(_Project.id).where(_Project.sales_id == current_user.id))
        sales_scope_ids = [r[0] for r in res.all()]
    items, total = await task_service.list_tasks(
        db, project_id, assignee_id, status, phase, page, page_size,
        scope_assignee_id=scope,
        sales_project_ids=sales_scope_ids,
        keyword=keyword,
        priority=priority,
        overdue=overdue,
        sort=sort,
        order=order,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api.py::test_list_tasks_filters_and_sort tests/test_api.py::test_list_tasks_overdue -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 回归 — 确认未破坏既有任务用例**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api.py -k "task or project" -v`
Expected: 既有 `test_project_crud_and_init`、`test_task_flow_actions` 等仍 PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/task_service.py backend/app/api/tasks.py backend/tests/test_api.py
git commit -m "feat(task): list_tasks 支持关键词/优先级/多状态/超期/排序 + 回传 project_name"
```

---

## Task 2: 前端 — 新增 PRIORITY_MAP 常量

**Files:**
- Modify: `frontend/src/utils/constants.js`

- [ ] **Step 1: 追加 PRIORITY_MAP**

在 `frontend/src/utils/constants.js` 末尾追加（约定：数值越小优先级越高，与项目 `priority` 默认 3=中 一致）：

```javascript
export const PRIORITY_MAP = {
  1: { label: '最高', type: 'danger' },
  2: { label: '高', type: 'warning' },
  3: { label: '中', type: 'primary' },
  4: { label: '低', type: 'info' },
  5: { label: '最低', type: 'info' },
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/utils/constants.js
git commit -m "feat(task): 新增 PRIORITY_MAP 优先级常量"
```

---

## Task 3: 前端 — 新建 TaskListView 列表组件

**Files:**
- Create: `frontend/src/components/TaskListView.vue`

该组件接收 `filters` prop（普通对象，含 project_id/phase/assignee_id/keyword/priority/overdue/status 数组），自管分页、排序、行内操作与抽屉。`users` 用于负责人显示（也可不传，列表只显示 assignee_name，已由后端返回）。

- [ ] **Step 1: 创建组件文件**

```vue
<script setup>
import { ref, watch, computed } from 'vue'
import { listTasks, startTask, submitTask, approveTask, rejectTask } from '../api/tasks'
import TaskDrawer from './TaskDrawer.vue'
import { STATUS_MAP, PHASE_MAP, PRIORITY_MAP } from '../utils/constants'
import { todayStr } from '../utils/format'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  filters: { type: Object, default: () => ({}) },
})

const auth = useAuthStore()
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const sort = ref('')
const order = ref('asc')
const loading = ref(false)

const drawerVisible = ref(false)
const selectedTask = ref(null)
const rowLoading = ref({})

function buildParams() {
  const f = props.filters || {}
  const params = {
    page: page.value,
    page_size: pageSize.value,
  }
  if (f.project_id) params.project_id = f.project_id
  if (f.phase) params.phase = f.phase
  if (f.assignee_id) params.assignee_id = f.assignee_id
  if (f.keyword) params.keyword = f.keyword
  if (f.priority) params.priority = f.priority
  if (f.overdue) params.overdue = true
  if (Array.isArray(f.status) && f.status.length) params.status = f.status.join(',')
  if (sort.value) { params.sort = sort.value; params.order = order.value }
  return params
}

async function fetchData() {
  loading.value = true
  try {
    const res = await listTasks(buildParams())
    tasks.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

// 筛选变化回到第一页重新查询
watch(() => props.filters, () => { page.value = 1; fetchData() }, { deep: true, immediate: true })

function onSortChange({ prop, order: ord }) {
  if (!ord) { sort.value = ''; order.value = 'asc' }
  else { sort.value = prop; order.value = ord === 'descending' ? 'desc' : 'asc' }
  page.value = 1
  fetchData()
}

function onPageChange(p) { page.value = p; fetchData() }

function openTask(row) { selectedTask.value = row; drawerVisible.value = true }

function isOverdue(row) {
  return row.planned_end && row.planned_end < todayStr() && !['done', 'cancelled'].includes(row.status)
}

const canStart = (row) => {
  const role = auth.user?.role
  return role === 'pm' || role === 'admin' || row.assignee_id === auth.user?.id
}

async function runAction(row, fn, okMsg) {
  rowLoading.value = { ...rowLoading.value, [row.id]: true }
  try {
    await fn(row.id)
    ElMessage.success(okMsg)
    await fetchData()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    rowLoading.value = { ...rowLoading.value, [row.id]: false }
  }
}

function handleStart(row) { runAction(row, startTask, '任务已开始') }
function handleSubmit(row) { runAction(row, (id) => submitTask(id), '已提交审核') }
function handleApprove(row) { runAction(row, approveTask, '审核通过') }

async function handleReject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入退回原因', '退回任务', {
      confirmButtonText: '确认退回', cancelButtonText: '取消',
      inputValidator: (v) => !!v || '请输入退回原因',
    })
    await runAction(row, (id) => rejectTask(id, value), '已退回')
  } catch (e) { /* 取消无需提示 */ }
}

function onRefresh() { fetchData() }
</script>

<template>
  <div v-loading="loading">
    <el-table :data="tasks" size="small" @row-click="openTask" @sort-change="onSortChange"
              highlight-current-row style="cursor: pointer">
      <el-table-column prop="task_no" label="编号" width="160" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="project_name" label="项目" width="140" show-overflow-tooltip />
      <el-table-column label="阶段" width="100">
        <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="90">
        <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="优先级" width="90" prop="priority" sortable="custom">
        <template #default="{ row }">
          <el-tag v-if="PRIORITY_MAP[row.priority]" :type="PRIORITY_MAP[row.priority].type" size="small">
            {{ PRIORITY_MAP[row.priority].label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="截止" width="120" prop="planned_end" sortable="custom">
        <template #default="{ row }">
          <span :style="{ color: isOverdue(row) ? '#f56c6c' : '', fontWeight: isOverdue(row) ? 'bold' : '' }">
            {{ row.planned_end || '—' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending' && canStart(row)" size="small" type="primary"
                     :loading="rowLoading[row.id]" @click.stop="handleStart(row)">开始</el-button>
          <el-button v-else-if="row.status === 'active'" size="small" type="primary"
                     :loading="rowLoading[row.id]" @click.stop="handleSubmit(row)">提交</el-button>
          <template v-else-if="row.status === 'review'">
            <el-button size="small" type="success" :loading="rowLoading[row.id]" @click.stop="handleApprove(row)">通过</el-button>
            <el-button size="small" type="warning" :loading="rowLoading[row.id]" @click.stop="handleReject(row)">退回</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 12px">
      <el-pagination
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>

    <TaskDrawer v-model:visible="drawerVisible" :task="selectedTask" show-project-link
                @refresh="onRefresh" @view-project="(id) => $router.push(`/projects/${id}`)" />
  </div>
</template>
```

- [ ] **Step 2: 构建校验（组件语法）**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TaskListView.vue 相关报错（此时组件尚未被引用，仅验证可编译）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/TaskListView.vue
git commit -m "feat(task): 新增任务列表视图组件 TaskListView"
```

---

## Task 4: 前端 — 任务页加 看板/列表 切换与共享筛选栏 + 菜单改名

**Files:**
- Modify: `frontend/src/views/TaskKanban.vue`
- Modify: `frontend/src/components/Layout.vue:25`

- [ ] **Step 1: 改造 TaskKanban.vue `<script setup>`**

替换 `frontend/src/views/TaskKanban.vue` 的 `<script setup>` 段为以下内容（在原基础上：引入列表组件与新筛选项；把看板取数改为服务端筛选驱动）：

```javascript
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import TaskListView from '../components/TaskListView.vue'
import { todayStr } from '../utils/format'
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listTasks, startTask, submitTask, approveTask, listUsers } from '../api/tasks'
import { listProjects } from '../api/projects'
import { STATUS_MAP, PHASE_MAP } from '../utils/constants'
import { ElMessage } from 'element-plus'

const router = useRouter()
const tasks = ref([])
const projects = ref([])
const users = ref([])
const loading = ref(true)

// 视图模式（持久化）
const viewMode = ref(localStorage.getItem('task-view-mode') || 'kanban')
watch(viewMode, (v) => localStorage.setItem('task-view-mode', v))

// 共享筛选
const filterProject = ref('')
const filterPhase = ref('')
const filterAssignee = ref('')
const filterKeyword = ref('')
const filterPriority = ref('')
const filterOverdue = ref(false)
const filterStatus = ref([]) // 仅列表视图用

// 传给列表组件的筛选对象
const listFilters = computed(() => ({
  project_id: filterProject.value || undefined,
  phase: filterPhase.value || undefined,
  assignee_id: filterAssignee.value || undefined,
  keyword: filterKeyword.value || undefined,
  priority: filterPriority.value || undefined,
  overdue: filterOverdue.value || undefined,
  status: filterStatus.value,
}))

const draggingTask = ref(null)
const dragOverColumn = ref(null)

const columns = [
  { key: 'pending', label: '待分配', type: 'info' },
  { key: 'active', label: '进行中', type: 'primary' },
  { key: 'review', label: '待审核', type: 'warning' },
  { key: 'done', label: '已完成', type: 'success' },
  { key: '_exception', label: '异常', type: 'danger' },
]

const VALID_TRANSITIONS = {
  pending: { target: 'active', api: startTask },
  active: { target: 'review', api: (id) => submitTask(id) },
  review: { target: 'done', api: approveTask },
}

const PRIORITY_OPTIONS = [
  { value: 1, label: '最高' }, { value: 2, label: '高' }, { value: 3, label: '中' },
  { value: 4, label: '低' }, { value: 5, label: '最低' },
]
const STATUS_OPTIONS = ['pending', 'active', 'review', 'done', 'paused', 'blocked', 'cancelled']

const availablePhases = computed(() => {
  const phases = [...new Set(tasks.value.map(t => t.phase))]
  return phases.map(p => ({ key: p, label: PHASE_MAP[p] || p }))
})

// 看板取数：服务端筛选（不传 status，列本身即状态）
async function fetchKanban() {
  loading.value = true
  try {
    const params = { page_size: 200 }
    if (filterProject.value) params.project_id = filterProject.value
    if (filterPhase.value) params.phase = filterPhase.value
    if (filterAssignee.value) params.assignee_id = filterAssignee.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterOverdue.value) params.overdue = true
    const tRes = await listTasks(params)
    tasks.value = tRes.data.items
  } finally {
    loading.value = false
  }
}

// 仅看板模式下，筛选变化时重新取数
watch([filterProject, filterPhase, filterAssignee, filterKeyword, filterPriority, filterOverdue], () => {
  if (viewMode.value === 'kanban') fetchKanban()
})
watch(viewMode, (v) => { if (v === 'kanban') fetchKanban() })

const kanbanData = computed(() => columns.map((col) => ({
  ...col,
  tasks: col.key === '_exception'
    ? tasks.value.filter((t) => ['blocked', 'paused'].includes(t.status))
    : tasks.value.filter((t) => t.status === col.key),
})))

onMounted(async () => {
  const [pRes, uRes] = await Promise.all([listProjects({ page_size: 100 }), listUsers()])
  projects.value = pRes.data.items
  users.value = uRes.data
  if (viewMode.value === 'kanban') await fetchKanban()
  else loading.value = false
})

function goProject(task) { router.push(`/projects/${task.project_id}`) }

function getProjectName(projectId) {
  const p = projects.value.find((p) => p.id === projectId)
  return p?.name?.slice(0, 10) || ''
}

function onDragStart(event, task) {
  if (['blocked', 'paused'].includes(task.status)) return
  draggingTask.value = task
  event.dataTransfer.effectAllowed = 'move'
}
function onDragEnd() { draggingTask.value = null; dragOverColumn.value = null }
function onDragOver(event, colKey) {
  if (colKey === '_exception') return
  const task = draggingTask.value
  if (!task) return
  const transition = VALID_TRANSITIONS[task.status]
  if (transition && transition.target === colKey) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    dragOverColumn.value = colKey
  }
}
function onDragLeave(colKey) { if (dragOverColumn.value === colKey) dragOverColumn.value = null }
async function onDrop(event, colKey) {
  event.preventDefault()
  dragOverColumn.value = null
  const task = draggingTask.value
  draggingTask.value = null
  if (!task) return
  const transition = VALID_TRANSITIONS[task.status]
  if (!transition || transition.target !== colKey) return
  try {
    await transition.api(task.id)
    task.status = colKey
    ElMessage.success('状态已更新')
  } catch (e) {
    await fetchKanban()
  }
}
```

- [ ] **Step 2: 改造 TaskKanban.vue `<template>` 头部（筛选栏 + 切换）**

把 `<template>` 中 `<PageHeader title="任务看板"> ... </PageHeader>` 整段替换为：

```vue
    <PageHeader title="任务">
      <el-segmented v-model="viewMode" :options="[{ label: '看板', value: 'kanban' }, { label: '列表', value: 'list' }]" />
      <el-input v-model="filterKeyword" placeholder="搜索标题/编号" clearable style="width: 160px" />
      <el-select v-model="filterProject" placeholder="项目" clearable style="width: 150px" filterable>
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="filterPhase" placeholder="阶段" clearable style="width: 120px">
        <el-option v-for="p in availablePhases" :key="p.key" :label="p.label" :value="p.key" />
      </el-select>
      <el-select v-model="filterAssignee" placeholder="负责人" clearable filterable style="width: 130px">
        <el-option v-for="u in users" :key="u.id" :label="u.display_name" :value="u.id" />
      </el-select>
      <el-select v-model="filterPriority" placeholder="优先级" clearable style="width: 100px">
        <el-option v-for="o in PRIORITY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-if="viewMode === 'list'" v-model="filterStatus" placeholder="状态" multiple collapse-tags clearable style="width: 160px">
        <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="STATUS_MAP[s]?.label || s" :value="s" />
      </el-select>
      <el-checkbox v-model="filterOverdue">仅超期</el-checkbox>
    </PageHeader>
```

> 说明：`availablePhases` 在列表模式下基于当前看板数据可能为空；阶段下拉为空时不影响列表筛选（用户可不选阶段）。如需列表模式也有完整阶段项，可改用 `PHASE_MAP` 全量，但本次保持简单。

- [ ] **Step 3: 改造 TaskKanban.vue `<template>` 主体（按视图渲染）**

把 `<div class="kanban-board"> ... </div>` 整段用 `v-if="viewMode === 'kanban'"` 包裹，并在其后加列表渲染。即将原看板根节点 `<div class="kanban-board">` 改为：

```vue
    <div v-if="viewMode === 'kanban'" class="kanban-board">
```

（其内部内容保持不变）紧随其后、`</div>`（kanban-board 结束）之后插入：

```vue
    <TaskListView v-else :filters="listFilters" />
```

`goProject` / `getProjectName` 等看板原有函数保持不变。

- [ ] **Step 4: 菜单改名**

`frontend/src/components/Layout.vue:25` 由：

```javascript
  { path: '/kanban', label: '任务看板', icon: Grid },
```

改为：

```javascript
  { path: '/kanban', label: '任务', icon: Grid },
```

- [ ] **Step 5: 构建校验**

Run: `cd frontend && npm run build`
Expected: 构建成功，无报错。

- [ ] **Step 6: 手动验证**

启动后端与前端（`backend/.venv/bin/python -m uvicorn app.main:app` + `cd frontend && npm run dev`），用 pm01/123456 登录，进入「任务」页，逐项确认：
- 默认看板视图正常；切到列表视图，刷新后仍记住列表（localStorage）。
- 关键词/项目/阶段/负责人/优先级/仅超期 在两个视图都生效。
- 列表「状态」多选仅列表可见且生效。
- 列表点表头「优先级」「截止」可排序；分页可翻页。
- 列表点行打开抽屉；抽屉内操作后列表刷新。
- 列表行内「开始/提交/通过/退回」按状态显示且操作后该行状态更新。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/TaskKanban.vue frontend/src/components/Layout.vue
git commit -m "feat(task): 任务页新增看板/列表切换与共享筛选栏"
```

---

## 完成后

- 运行后端全量任务相关测试回归：`cd backend && .venv/bin/python -m pytest tests/test_api.py -k "task or project" -v`
- `cd frontend && npm run build` 通过
- 使用 superpowers:finishing-a-development-branch 决定合并/PR。
