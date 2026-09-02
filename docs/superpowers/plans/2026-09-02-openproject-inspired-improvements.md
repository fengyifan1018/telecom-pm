# OpenProject 借鉴改进 Implementation Plan（交互速赢包 + 业务深化包）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴 OpenProject 的业务与交互设计，为系统补齐四类能力：①筛选/视图状态可分享（URL 化）；②任务处理上下文不丢（抽屉导航、内联编辑、空态引导）；③任务间业务关系与排期联动（precedes/blocks + auto-schedule）；④进度量化与关注订阅（progress + watcher）。

**Architecture:** 后端新增 `TaskRelation` / `TaskWatcher` 两张表与 `Task.progress` / `Task.auto_schedule` 两列（走 `Base.metadata.create_all` + `migrate.py` 双通道），新增关系/关注 API 与排期联动服务 `schedule_service.py`；前端改造任务页容器（URL 筛选）、`TaskDrawer`（导航/关系/关注区块）、`TaskListView`（内联编辑/进度列）。不改动现有状态机语义，blocks 卡点以"转换前置校验"形式插入 `FlowEngine`。

**Tech Stack:** 后端 FastAPI + SQLAlchemy 2.0 async + pytest；前端 Vue 3 + Element Plus + Pinia + Vite。

---

## 重要前置说明

- **后端测试**：沿用 `tests/test_api.py` 的 `X-User-Id` DEBUG 鉴权模式与内存 SQLite fixture。新表由 `conftest.py` 的 `create_all` 自动建；开发库 `data.db` 由 `main.py` lifespan 的 create_all 自动建新表，**新增列**仍需在 `migrate.py` 的 `MIGRATIONS` 补 ALTER（项目惯例）。
- **前端无测试运行器**：以 `npm run build` 通过 + 浏览器手动验证为准。
- **执行顺序**：Task 1→4 为交互速赢包（彼此独立，可并行）；Task 5→6→7→8 有依赖链（6 依赖 5 的 precedes；8 可随时插入）。
- **不做的**（架构演进包，另行计划）：工作流矩阵表化、project_member 项目级成员、统一活动时间线、基线快照。

## File Structure

- `backend/app/models/task.py` — 新增 `TaskRelation`、`TaskWatcher` 模型；`Task` 加 `progress`、`auto_schedule` 列。
- `backend/app/models/__init__.py` — 导出新模型。
- `backend/migrate.py` — MIGRATIONS 补 `progress`、`auto_schedule` 两列。
- `backend/app/schemas/task.py` — `TaskUpdate` 加 `progress`；`TaskResponse` 加 `progress/auto_schedule/watcher_ids`；新增 `RelationCreate`。
- `backend/app/services/schedule_service.py` — **新建**：precedes 链联动重排（含环检测、auto_schedule 过滤、链长上限）。
- `backend/app/services/task_service.py` — 关系/关注查询 helper；`list_tasks` 支持 `watched_by` 筛选（可选）。
- `backend/app/api/tasks.py` — 新增 relations / watch 端点；流转动作接入 blocks 校验；日期更新触发联动重排。
- `backend/tests/test_api.py` — 每任务对应用例（URL 化无后端改动不测）。
- `frontend/src/views/TaskKanban.vue` — 筛选状态 ↔ URL query 双向同步。
- `frontend/src/views/ProjectList.vue` — 同上（search/product_type/status）。
- `frontend/src/components/TaskDrawer.vue` — 上一条/下一条导航、关系区块、关注按钮、自动排期开关、进度显示。
- `frontend/src/components/TaskListView.vue` — 截止/优先级内联编辑、进度列。
- `frontend/src/components/EmptyState.vue` — 支持行动按钮。
- `frontend/src/views/Workbench.vue` / `ProjectList.vue` — 空态接行动按钮。

---

# 包一：交互速赢包

## Task 1: 筛选状态进 URL

**Files:**
- Modify: `frontend/src/views/TaskKanban.vue`（任务页容器，持共享筛选）
- Modify: `frontend/src/views/ProjectList.vue`

- [ ] **Step 1: 任务页双向同步**

`TaskKanban.vue`：初始化时从 `route.query` 读 `view_mode/project_id/phase/assignee_id/keyword/priority/overdue/status`（status 为逗号分隔多值）填充对应 ref；现有 `watch(listFilters)` 与 `watch(viewMode)` 中追加 `router.replace({ query: serialize(filters, viewMode) })`（空值删除 key，避免 URL 堆积）。注意 replace 不产生历史记录。

- [ ] **Step 2: 项目列表页同步**

`ProjectList.vue`：`search/product_type/status` 三个筛选同样处理（防抖搜索只在 confirm 时写 URL）。

- [ ] **Step 3: 验收**

- 设置筛选后刷新页面，筛选保持、数据一致
- 复制地址到新标签打开，呈现相同筛选结果
- 清空筛选后 URL 回到干净路径
- `npm run build` 通过

## Task 2: 任务抽屉「上一条 / 下一条」导航

**Files:**
- Modify: `frontend/src/components/TaskDrawer.vue`
- Modify: `frontend/src/components/TaskListView.vue`、`frontend/src/views/Workbench.vue`、`frontend/src/views/TaskKanban.vue`（列表模式）、`frontend/src/views/ProjectDetail.vue`

- [ ] **Step 1: TaskDrawer 支持导航协议**

新增 props：`peerIds?: number[]`（当前列表的任务 id 有序集合）。抽屉头部加 `‹ ›` 按钮与 `n/N` 计数（按当前 task.id 在 peerIds 中的位置计算，禁用边界）。点击 emit `('navigate', newTaskId)`，自身不改数据——由父组件切换 `selectedTask`。

- [ ] **Step 2: 调用方接入**

四个调用点在 `openTask` 时传入当前视图的完整 id 列表（注意列表视图传当前页 ids；看板模式传全部已加载 ids 按列序拼接）；监听 `@navigate` 更新 `selectedTask` 并刷新抽屉数据。

- [ ] **Step 3: 验收**

工作台"待审核"tab 打开抽屉后可连续切换处理，关闭后回到原列表且滚动位置不重置；流转成功刷新后导航计数仍正确。

## Task 3: 表格内联编辑（截止日期 / 优先级）

**Files:**
- Modify: `frontend/src/components/TaskListView.vue`
- Modify: `backend/app/schemas/task.py`（若 `TaskUpdate` 未含 `priority` 则补充）
- Modify: `backend/app/api/tasks.py`（确认 PUT 更新权限覆盖两个字段）

- [ ] **Step 1: 后端确认/补齐**

检查 `TaskUpdate` 已含 `planned_start/planned_end/priority`；缺 `priority` 则补（`ge=1 le=5`）。权限沿用现有 update 端点规则（PM/admin 或 assignee 可改排期；优先级同权限）。审计已由 `log_action` 覆盖。

- [ ] **Step 2: 前端内联控件**

`TaskListView.vue` 截止列：有权限时渲染 `el-date-picker`（shortcuts，clearable），`@change` 调 `updateTask(row.id, {...})`，成功后局部更新行数据 + `ElMessage.success`；失败回显原值。优先级列同理用 `el-select`（PRIORITY_OPTIONS）。无权限时保持纯文本。行点击开抽屉与控件事件需 `.stop` 隔离。

- [ ] **Step 3: 测试与验收**

后端补用例：assignee 改自己任务排期 200；改他人任务 403；priority=0/6 → 422。前端：改截止后刷新仍在；审计页可见 update 记录。

## Task 4: 空态行动按钮

**Files:**
- Modify: `frontend/src/views/ProjectList.vue`、`frontend/src/views/Workbench.vue`
（`EmptyState.vue` 已内置 `action` 插槽与 `.empty-state__action` 样式，无需改组件）

- [ ] **Step 1: 接入插槽**

ProjectList 空结果：区分"无数据"（`<EmptyState><el-button type="primary" size="small">新建项目</el-button></EmptyState>`，有 `project.create` 权限才显示）与"筛选无结果"（按钮"清除筛选"）。Workbench"我的"视图空态：按钮"去任务页领任务"（跳 `/kanban`）。按钮点击事件用 `@click` 直接绑在按钮上（插槽内容正常响应事件）。

- [ ] **Step 2: 验收**

空项目库（新环境）下首页即有明确行动入口；按钮权限正确隐藏；按钮样式与全局主色一致（走 el-button 默认令牌，不新增颜色）。

---

# 包二：业务深化包

## Task 5: 任务关系 precedes / blocks

**Files:**
- Modify: `backend/app/models/task.py`、`backend/app/models/__init__.py`
- Modify: `backend/app/schemas/task.py`、`backend/app/services/task_service.py`、`backend/app/api/tasks.py`
- Modify: `frontend/src/components/TaskDrawer.vue`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: 模型**

```python
class TaskRelation(Base):
    __tablename__ = "task_relations"
    __table_args__ = (UniqueConstraint("from_task_id", "to_task_id", "relation_type"),)
    id, from_task_id(前置/阻塞方), to_task_id, relation_type: "precedes"|"blocks",
    created_by, created_at(now_cn)
```

新表依赖 lifespan create_all 自动建，无存量数据迁移。

- [ ] **Step 2: API**

- `GET /api/tasks/{id}/relations` → `{precedes:[], preceded_by:[], blocks:[], blocked_by:[]}`（带任务号/标题/状态/项目名摘要）
- `POST /api/tasks/{id}/relations` body `{relation_type, related_task_id}`（权限 PM/admin 或 assignee）
  - 环检测：precedes 新边上从 to_task 出发沿 precedes DFS，回到 from_task 则 400「存在循环依赖」（上限 500 节点防爆）
  - 自引用 400；重复关系 409
- `DELETE /api/tasks/relations/{relation_id}`（创建者/PM/admin）

- [ ] **Step 3: blocks 卡点接入流转**

`FlowEngine` 执行转换前检查：目标任务的 `blocked_by` 中存在未 done/cancelled 任务 → 400，文案「被任务 T-xxx（标题）阻塞，需先完成」。放在 `start`（pending→active）与 `submit/approve/reject` 全部动作前。

- [ ] **Step 4: 前端关系区块**

`TaskDrawer` 新增「前置 / 阻塞」折叠区：四组列表（任务号+标题+状态 tag，点击可跳对应项目）；添加控件为远程搜索 `el-select`（`listTasks({keyword, page_size:20})` 跨项目搜索，排除自身）；每行可删。行内文案 `#编号` 风格。

- [ ] **Step 5: 测试**

建关系（precedes/blocks 各一）；blocks 下对被阻塞任务 start → 400 且文案含阻塞任务号；环 → 400；重复 → 409；完成阻塞方后 start 成功；删除关系后解除。

## Task 6: 排期联动重排（auto-schedule）

**Files:**
- Modify: `backend/app/models/task.py`（`Task.auto_schedule Boolean default True`）、`backend/migrate.py`（加列）
- 新建: `backend/app/services/schedule_service.py`
- Modify: `backend/app/api/tasks.py`（PUT 日期后触发）
- Modify: `frontend/src/components/TaskDrawer.vue`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: 联动引擎**

`schedule_service.propagate(db, changed_task) -> int`：沿 precedes 后继边 BFS，逐个把后继任务的 `planned_start/end` 平移同一 delta（保持工期），仅处理 `auto_schedule=True` 且未被人工锁定的任务；链长上限 200 防御性截断；返回影响条数。 weekends 不做特殊处理（与现有 start_task 口径一致）。

- [ ] **Step 2: 接入更新链路**

`PUT /api/tasks/{id}` 中当日期字段实际变化时调用 propagate，响应回传 `{rescheduled: N}`；前端据此 toast「已联动顺延 N 个后续任务」。阶段级 depends_on 本轮不做联动（阶段激活仍走 flow_engine 原逻辑）。

- [ ] **Step 3: 手动锁**

`TaskDrawer` 排期区加「自动排期」开关（PM/admin 可见），关闭后该任务不参与联动（作为链条终点）。

- [ ] **Step 4: 测试**

A precedes B precedes C（均 auto）：改 A 结束 +2 → B/C 起/止各 +2，响应 `rescheduled: 2`；B 设 auto_schedule=False → 仅 C +2（若 B 为终点则 0）；环场景已在 Task 5 拦截。

## Task 7: 任务进度 progress

**Files:**
- Modify: `backend/app/models/task.py`（`Task.progress Integer default 0`）、`backend/migrate.py`
- Modify: `backend/app/schemas/task.py`（Update/Response）
- Modify: `backend/app/api/tasks.py`（approve 置 100）
- Modify: `frontend/src/components/TaskListView.vue`、`TaskDrawer.vue`、`frontend/src/views/Reports.vue`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: 字段与校验**

`progress: int ge=0 le=100`；`approve` 流转成功时置 100；`reject` 保持不变（人工回调）。存量数据迁移默认 0。

- [ ] **Step 2: 前端**

TaskDrawer 基本信息区加进度条 + 滑杆（active/review 状态可编辑，pending/done 只读）；TaskListView 加「进度」列（`el-progress` mini 条，done 恒 100）。

- [ ] **Step 3: 报表加权**

`/api/dashboard/phase-stats` 每阶段加 `avg_progress`（done 视为 100 参与）；Reports 阶段分布表加「平均进度」列，与任务数并列。

- [ ] **Step 4: 测试**

更新 progress=60 → 200；progress=120 → 422；approve 后 progress=100；phase-stats 含 avg_progress 且数值正确。

## Task 8: 任务关注（watcher）

**Files:**
- Modify: `backend/app/models/task.py`（`TaskWatcher`，UniqueConstraint(task_id, user_id)）
- Modify: `backend/app/schemas/task.py`（Response 加 `watcher_ids`）、`backend/app/api/tasks.py`
- Modify: `frontend/src/components/TaskDrawer.vue`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: API**

- `PUT /api/tasks/{id}/watch` toggle → `{watching: bool}`（登录即可关注）
- `TaskResponse.watcher_ids: list[int]`

- [ ] **Step 2: 通知分发**

现有通知触发点（assign/submit/approve/reject/超期升级/@提及）增加收件人：除原目标外，向所有 watcher 发同类型通知（**发起动作的 watcher 本人除外**；assignee/reviewer 与 watcher 重复时去重）。`notification_service.notify_many()` helper 统一收口。

- [ ] **Step 3: 前端**

TaskDrawer 标题行加「关注」按钮（眼睛图标 + 人数），toggle 即时反馈。

- [ ] **Step 4: 测试**

user3 watch 任务后，user2 提交该任务 → user3 收到 submit 通知；重复 watch 幂等返回 false；自己动作不通知自己。

---

## 里程碑与顺序

| 里程碑 | 内容 | 量级 |
|---|---|---|
| M1 交互速赢 | Task 1-4（可并行） | ~3-4 天 |
| M2 关系与卡点 | Task 5 | ~2 天 |
| M3 排期联动 | Task 6（依赖 M2 precedes） | ~2 天 |
| M4 进度与关注 | Task 7、8（互相独立） | ~2 天 |

## 测试策略

- 后端：每 Task 先写失败用例再实现（TDD），全部走现有 conftest 内存库；`datetime` 断言用字符串日期比较避免时区干扰。
- 前端：每 Task 完成 `npm run build` + 浏览器手动验证清单（登录 pm01/admin 双角色过一遍权限显隐）。
- 回归：每包合并前跑全量 pytest（当前基线 21 用例）。

## 风险与对策

1. **联动重排误伤**：仅 precedes 边传播、仅 auto_schedule 任务、链长 200 上限、响应回传影响数让用户可感知；回滚 = 关闭开关。
2. **blocks 与阶段自动激活冲突**：阶段激活只把任务置为 active-ready（pending 可 start），blocks 在 start 动作时才拦截，不影响阶段激活本身；文案明确提示阻塞来源。
3. **TaskResponse 字段膨胀**：relations 明细走独立端点，列表响应只加轻量字段（progress/auto_schedule/watcher_ids），避免 N+1（watcher_ids 用一次性 group concat 查询）。
4. **URL 筛选与 localStorage 视图模式冲突**：view_mode 仍以 localStorage 为默认，URL 显式携带时优先。
