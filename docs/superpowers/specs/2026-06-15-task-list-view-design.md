# 任务列表视图 — 设计文档

日期：2026-06-15
状态：已确认，待实现

## 背景

任务模块目前全局只有一个入口 `/kanban`（菜单「任务看板」），仅提供按状态分列的拖拽看板。
工作台和项目详情各有局部列表，但**缺少一个全局、可筛选、可排序、可分页的任务列表视图**。

本设计在不破坏现有看板/甘特图/状态机的前提下，新增任务列表视图，并与看板共用筛选栏。

## 目标

- 在现有「任务看板」页内新增**列表视图**，与看板通过顶部切换共存。
- 列表支持多维筛选、排序、分页，点行打开现有 `TaskDrawer`，并提供行内快捷操作。

## 非目标（YAGNI，本次不做）

- 批量操作（批量指派/批量改状态）
- 看板泳道、日历视图
- 自定义/保存筛选视图
- 状态机、甘特图、依赖、子任务相关改动

## 落点与结构

- `/kanban` 页菜单由「任务看板」改名为「**任务**」（`frontend/src/components/Layout.vue`，图标 `Grid` 不变，路由 `path` 不变）。
- 页面顶部新增 **看板 | 列表** 切换控件（`el-radio-group` button 风格或 `el-segmented`），默认「看板」。
- 当前视图选择持久化到 `localStorage`（键名 `task-view-mode`）。
- 看板与列表**共用一条筛选栏**，置于 `PageHeader` 内。

## 共享筛选栏

| 控件 | 后端参数 | 看板 | 列表 |
|---|---|---|---|
| 项目（可搜索下拉） | `project_id` | ✓ | ✓ |
| 阶段 | `phase` | ✓ | ✓ |
| 负责人 | `assignee_id` | ✓ | ✓ |
| 关键词（标题/编号） | `keyword` | ✓ | ✓ |
| 优先级 | `priority` | ✓ | ✓ |
| 仅看超期 | `overdue` | ✓ | ✓ |
| 状态（多选） | `status` | ✗（看板列即状态） | ✓ |
| 排序 | `sort` | ✗ | ✓ |

行为：
- 切换视图或修改任一筛选 → 重新拉取数据。
- **看板视图**：拉全量（`page_size=200`），不传 `status`（列本身即状态分组），其余筛选透传。
- **列表视图**：服务端分页 + 排序 + 全部筛选（含多状态）。

## 列表视图

`el-table`，列顺序：

`编号 · 标题 · 项目 · 阶段 · 状态(tag) · 负责人 · 优先级 · 计划起止 · 截止 · 操作`

- **截止列**：`planned_end < today` 且未完成时标红加粗（复用现有 `is-overdue` 样式与 `todayStr()`）。
- **点行** → 复用现有 `TaskDrawer`（指派/排期/附件/升级/评论/流转一应俱全）；抽屉 `refresh` 后刷新列表。
- **操作列（行内快捷操作，复用现有 transition 接口，不新增接口）**，按当前状态显示：
  - `pending` → 「开始」（权限：负责人本人或 `pm`/`admin`，与 `TaskDrawer.canStart` 一致）
  - `active` → 「提交」
  - `review` → 「审核通过」/「退回」（退回弹框输入原因，复用 `rejectTask`）
  - 操作成功后局部刷新（重新拉取当前页）。
- **排序**：`截止`、`优先级` 列可点表头排序，服务端排序（`el-table` `sortable="custom"` + `@sort-change`）。
- 底部 `el-pagination`，复用项目现有分页样式。

## 后端改动

文件：`backend/app/services/task_service.py`（`list_tasks`）与 `backend/app/api/tasks.py`（`GET /api/tasks`）。
全部为新增可选参数，向后兼容，现有调用（看板/工作台/项目详情）不受影响。

新增/调整参数：
- `keyword: str | None` → `Task.title LIKE %kw%` OR `Task.task_no LIKE %kw%`
- `priority: int | None` → 精确匹配
- `status: str | None` → **支持逗号分隔多值**，多值走 `Task.status.in_([...])`，单值仍等值匹配（兼容现状）
- `overdue: bool` → `Task.planned_end < today AND Task.status NOT IN ('done', 'cancelled')`
- `sort: str | None` → 白名单字段 `planned_end | priority | created_at`；`order: str = "asc"` → `asc | desc`。`sort` 为空或非白名单值时回退默认 `Task.id asc`；`order` 非 `asc/desc` 时回退 `asc`。前端 `@sort-change` 映射：`prop` → `sort`，`order`(`ascending/descending`) → `asc/desc`。

返回项变更：
- 列表项新增 `project_name`（`outerjoin` projects 表取 `Project.name`），供列表「项目」列显示。看板继续沿用其已有的 projects 拉取做名称解析，不依赖该字段，互不破坏。

角色数据范围（sales / 采购 / 现场的 scope 逻辑）沿用现有实现，不改动。

## 测试与验证

后端（pytest，沿用现有夹具，注意 [[backend-test-harness]] 与 [[backend-python-env]]）：
- `keyword` 命中标题与编号
- `status` 多值
- `overdue` 过滤
- `sort` 白名单与非法值回退

前端（手动）：
- 看板/列表切换 + `localStorage` 记忆
- 筛选联动两视图
- 行内操作后行状态更新、分页正确
- 点行打开抽屉、抽屉操作后列表刷新

## 涉及文件

- `backend/app/services/task_service.py` — `list_tasks` 增参
- `backend/app/api/tasks.py` — `GET /api/tasks` 透传新参数
- `backend/tests/test_api.py`（或新增）— 新参数用例
- `frontend/src/views/TaskKanban.vue` — 加视图切换 + 共享筛选栏 + 列表视图（或拆出 `TaskListView.vue` 子组件）
- `frontend/src/components/Layout.vue` — 菜单文案「任务看板」→「任务」
- `frontend/src/api/tasks.js` — `listTasks` 已支持透传 params，无需改动
