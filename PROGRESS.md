# 通信项目任务管理系统 - 开发进度记录

## 项目概述

通信行业项目任务管理系统，支持传输、裸纤、DIA、SD-WAN四条产品线，跨角色协作（销售、运营、项目经理、采购、网络工程师、现场实施）。

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 (async) + aiosqlite (SQLite)
- **前端**: Vue 3 (Composition API) + Element Plus + Pinia + Vue Router + Axios + Vite
- **认证**: JWT (Bearer token)，开发模式支持 X-User-Id header 直接指定用户

## 项目结构

```
D:\AI项目\
├── CLAUDE.md              # Claude 行为指南
├── docs/                  # 设计文档
│   ├── 01-需求分析.md
│   ├── 02-系统设计.md
│   ├── 03-产品线流程定义.md
│   ├── 04-协作流转详细设计.md
│   ├── 05-前端原型设计.md
│   └── 06-异常场景设计.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI app + lifespan
│   │   ├── config.py          # Pydantic Settings
│   │   ├── database.py        # async engine + session
│   │   ├── dependencies.py    # get_db, get_current_user
│   │   ├── api/
│   │   │   ├── router.py      # 汇总所有路由 (31个端点)
│   │   │   ├── auth.py        # login, /me
│   │   │   ├── projects.py    # CRUD + init + customers
│   │   │   ├── tasks.py       # list, get, update, assign, start/submit/approve/reject, comments, transitions
│   │   │   ├── templates.py   # list, get
│   │   │   ├── dashboard.py   # my-workbench, overview, phase-stats, user-workload
│   │   │   ├── users.py       # list users
│   │   │   └── notifications.py  # list, unread-count, mark-read, mark-all-read
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── project.py     # Project + Customer
│   │   │   ├── task.py        # Task + TaskDependency + TaskTransition
│   │   │   ├── workflow_template.py
│   │   │   ├── comment.py
│   │   │   └── notification.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── project.py
│   │   │   ├── task.py        # TaskResponse, TaskUpdate, TaskAssign, TaskAction, etc.
│   │   │   ├── template.py
│   │   │   └── common.py
│   │   ├── services/
│   │   │   ├── flow_engine.py          # 核心状态机 + 阶段自动激活
│   │   │   ├── template_service.py     # 从模板生成任务
│   │   │   ├── project_service.py      # 项目 CRUD
│   │   │   ├── task_service.py         # 任务查询(含user join)
│   │   │   └── notification_service.py # 创建通知helper
│   │   └── seed/
│   │       ├── run_seed.py        # 种子数据入口
│   │       ├── seed_users.py      # 6个demo用户 (密码: 123456)
│   │       └── seed_templates.py  # 4条产品线模板定义
│   └── tests/
│       ├── conftest.py        # 内存SQLite + seeded_db fixture
│       ├── test_api.py        # API集成测试 (7个)
│       └── test_flow_engine.py # 流程引擎单元测试 (3个)
└── frontend/
    ├── package.json
    ├── vite.config.js         # proxy /api -> localhost:8000
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue
        ├── router/index.js    # 路由 + auth guard
        ├── stores/auth.js     # Pinia token/user
        ├── api/
        │   ├── index.js       # axios instance + interceptors
        │   ├── auth.js
        │   ├── projects.js    # listProjects, getProject, createProject, updateProject, initProject, listCustomers, createCustomer
        │   └── tasks.js       # 所有任务API + notifications + users + templates
        ├── utils/constants.js # STATUS_MAP, PRODUCT_TYPE_MAP, PHASE_MAP, PHASE_ORDER_BY_PRODUCT, ROLE_MAP
        ├── components/
        │   ├── Layout.vue         # 侧边栏 + header(通知铃铛+用户下拉) + 通知抽屉
        │   ├── PhaseProgress.vue  # 水平阶段进度条(支持多产品线)
        │   ├── TaskDrawer.vue     # 任务详情抽屉(指派/排期/评论/流转)
        │   └── GanttChart.vue     # 甘特图组件
        └── views/
            ├── Login.vue
            ├── Workbench.vue      # 统计卡片 + 进行中/待审核tabs
            ├── ProjectList.vue    # 搜索/筛选 + 表格 + 新建对话框(客户选择/PM分配)
            ├── ProjectDetail.vue  # 项目头 + 阶段进度 + 任务列表/甘特图tabs + 编辑/取消
            ├── TaskKanban.vue     # 4列看板 + 项目/阶段筛选 + 负责人显示
            ├── Reports.vue        # 概览卡片 + 阶段统计表 + 人员负荷
            └── TemplateList.vue   # 模板卡片 + 展开查看阶段/任务
```

## 已完成功能清单

### 后端核心

1. **流程引擎** (`flow_engine.py`)
   - 状态机: pending → active → review → done (+ paused/blocked/rework/cancelled)
   - 有效转换: (active, submit)→review, (review, approve)→done, (review, reject)→active(rework+1)
   - 阶段完成检测: 所有 required 任务 done → 自动激活下游阶段
   - 扇入依赖: 阶段可依赖多个前置阶段，全部完成才激活
   - 项目自动完成: 所有 required 任务 done → project.status = completed

2. **4条产品线模板**
   - DIA: 7阶段 26任务 (资源确认→采购→施工开通→网络配置→验收)
   - 传输: 8阶段 27任务 (勘察→方案→资源/采购并行→施工→联调)
   - 裸纤: 7阶段 26任务 (路由勘察→资源协调/施工方案并行→施工→测试)
   - SD-WAN: 8阶段 35任务 (方案+底层线路并行→站点部署→策略→联调)

3. **通知系统**
   - 触发: 任务指派、提交审核、审核通过、退回
   - API: 列表(最近50条)、未读计数、标记已读、全部已读

4. **API端点** (45+个)
   - auth: login, me
   - projects: CRUD + init + customers(list/create) + suspend + resume + suspensions
   - tasks: list, get, update, assign, start, submit, approve, reject, transitions, comments
   - tasks/attachments: upload, list, download, delete
   - tasks/escalations: create, list, resolve
   - templates: list, get
   - dashboard: my-workbench, overview, phase-stats, user-workload
   - users: list, create, update, change-password
   - notifications: list, unread-count, mark-read, mark-all-read

5. **权限控制 (RBAC)**
   - `require_roles()` 依赖注入，按角色限制端点访问
   - 项目创建: sales/pm/admin; 立项/编辑: pm/admin
   - 任务指派: pm/admin; 提交: assignee; 审批/退回: reviewer或pm/admin
   - 用户管理: admin only; 附件删除: 上传者或admin

6. **文件附件系统**
   - 上传/下载/列表/删除，20MB限制
   - UUID文件名存储避免冲突，local uploads/ 目录

7. **项目暂停/恢复**
   - 暂停: 项目→suspended，active任务→paused，记录暂停原因
   - 恢复: 项目→active，paused任务→active，记录恢复信息
   - 暂停记录表: reason_category, reason, expected_resume

8. **任务问题升级**
   - 严重等级: low/medium/high/critical
   - 状态流转: open → resolved
   - 通知: 创建时通知reviewer，解决时通知发起人

9. **数据丰富化**
   - 任务列表返回 assignee_name
   - 评论返回 user_name
   - 流转记录返回 operator_name
   - 项目列表支持 search 模糊搜索

### 前端页面

1. **登录页** — 用户名/密码 → JWT → localStorage
2. **工作台** — 4个统计卡片(进行中/待审核/已完成/超期) + 我的任务tabs(进行中+待审核) + 超期红色高亮
3. **项目管理** — 搜索框(防抖) + 产品线/状态筛选 + 分页表格 + 新建(客户下拉选择/PM分配/产品线/优先级)
4. **项目详情** — 项目信息头 + 编辑对话框 + 取消按钮 + 阶段进度条 + 任务列表(分阶段)/甘特图 切换 + 显示负责人
5. **任务看板** — 4列(待分配/进行中/待审核/已完成) + 项目筛选 + 阶段筛选 + 负责人/截止显示
6. **报表中心** — 概览卡片 + 各阶段任务分布表(含进度条) + 人员负荷条形图
7. **模板管理** — 模板卡片(展开显示阶段→任务流程)

### 前端组件

1. **Layout** — 侧边栏(5个导航) + 顶栏(通知铃铛+未读角标+通知抽屉+用户信息) + 30s轮询
2. **PhaseProgress** — 接收 productType，从 PHASE_ORDER_BY_PRODUCT 获取对应阶段，显示 done/active/pending 图标
3. **TaskDrawer** — 任务详情(编号/阶段/状态/排期日期选择/负责人下拉+指派) + 操作按钮(提交/通过/退回) + 评论(显示用户名) + 流转记录(显示操作人)
4. **GanttChart** — 横向时间轴，按任务 planned_start/end 绘制彩色条，月份刻度线

### 测试

- 10个测试全部通过
- test_api.py: health, login, debug_header, project_crud_and_init(26 tasks), task_flow_actions, comments, dashboard
- test_flow_engine.py: full_dia_flow(阶段自动激活), reject_increments_rework, invalid_transition_raises

## 种子数据

运行 `python -m app.seed.run_seed`:
- 6个用户: pm01(项目经理), sales01(销售), ops01(运营), eng01(网络工程师), field01(现场实施), proc01(采购), 密码均为 123456
- 4个产品线模板
- 2个示例客户: XX科技有限公司, YY银行

## 启动方式

```bash
# 后端
cd backend
pip install -e .
python -m app.seed.run_seed   # 首次运行种子数据
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev   # 默认 http://localhost:5173, proxy /api -> 8000
```

## 待完成功能（按优先级）

### P0 - 核心缺失 (已全部完成 ✓)

1. ~~**权限控制 (RBAC)**~~ ✓ — 按角色限制操作（assignee可提交，reviewer可审批，PM可立项，sales可创建项目）
2. ~~**文件附件**~~ ✓ — 任务附件上传/下载/删除（20MB限制，UUID存储）
3. ~~**密码修改 & 用户管理**~~ ✓ — 修改密码，管理员新增/编辑/禁用用户
4. ~~**项目暂停/恢复**~~ ✓ — 暂停项目(冻结活跃任务) + 恢复(解冻) + 暂停记录
5. ~~**任务问题升级**~~ ✓ — 问题升级(严重等级/描述) + 通知审核人 + 解决方案

### P1 - 体验提升 (部分完成)

6. ~~**模板管理 CRUD**~~ ✓ — 后端 POST/PUT/DELETE（admin only，修改phases自动版本号+1）+ 前端对话框（名称/产品线/JSON阶段编辑器，含校验+示例填充）+ 启用/停用切换，非admin只读
7. ~~**图表可视化**~~ ✓ — 报表中心集成 ECharts：任务状态饼图、产品线分布饼图、阶段堆叠柱状图、人员负荷条形图
8. ~~**看板拖拽**~~ ✓ — HTML5原生拖拽，仅允许正向状态转移（pending→active→review→done），拖拽提示
9. ~~**报表导出**~~ ✓ — 项目详情页"导出 Excel"按钮，使用 xlsx 库导出任务列表（编号/阶段/状态/负责人/排期）
10. **SD-WAN 多站点** — project_site 模型，站点级任务跟踪（待完成）

### P2 - 生产就绪

11. **操作审计日志** — 通用审计表记录所有变更
12. **WebSocket 实时推送** — 替代30s轮询
13. **邮件/企微通知** — 关键节点推送外部渠道
14. **数据库迁移 (Alembic)** — 安全的表结构升级

## 已知技术细节

- Python 路径: `/c/Users/yifan/AppData/Local/Programs/Python/Python312/python.exe`
- 使用 bcrypt 直接调用（非 passlib，因兼容性问题）
- SQLite 文件: `backend/data.db`（生产数据）, `backend/test.db`（可删除）
- 前端 Vite proxy: `/api` → `http://localhost:8000`
- Git 仓库已 init 但未 commit（需先配置 user.name/email）

## 本次开发session完成的具体工作

### Session 1（初始开发）
1. 需求分析 + 6份设计文档
2. 后端 MVP：FastAPI 项目结构、ORM 模型、流程引擎、DIA 模板、API、测试
3. 前端基础：Vue 3 项目搭建、登录、工作台、项目列表、项目详情、任务抽屉

### Session 2（前端完善）
1. 任务看板页面 (TaskKanban)
2. 报表中心页面 (Reports) + 后端 phase-stats / user-workload 接口
3. 模板管理页面 (TemplateList)

### Session 3（功能完善）
1. **用户列表 API** — `GET /api/users` 端点 + 注册到 router
2. **任务指派功能** — TaskDrawer 添加人员下拉+指派按钮
3. **通知系统** — Notification 模型 + 4个 API + 触发逻辑(assign/submit/approve/reject) + 前端铃铛+抽屉
4. **甘特图** — GanttChart.vue + ProjectDetail 集成为 tab
5. **任务排期** — TaskDrawer 日期范围选择 + `PUT /api/tasks/:id` 更新接口
6. **新增3条产品线模板** — transmission(8阶段27任务), dark_fiber(7阶段26任务), sdwan(8阶段35任务)
7. **前端多产品线适配** — PHASE_ORDER_BY_PRODUCT + PhaseProgress/ProjectDetail 动态阶段
8. **用户名显示** — 评论/流转/任务列表 join user 表返回 display_name
9. **工作台增强** — 进行中/待审核 tabs + 阶段列 + 超期高亮
10. **看板增强** — 阶段筛选器 + 负责人显示
11. **项目搜索** — 模糊搜索 + 客户列表API + 新建对话框改进(客户下拉/PM选择)
12. **项目编辑/取消** — 编辑对话框 + 取消确认 + ProjectUpdate 支持 status
13. **通知铃铛修复** — emoji 替换为 SVG 图标

### Session 4（P0功能全部完成）
1. **RBAC权限控制** — `permissions.py` + 按角色限制: assign(pm/admin), submit(assignee), approve/reject(reviewer/pm/admin), 项目create(sales/pm/admin), init/update(pm/admin)
2. **文件附件系统** — Attachment模型 + upload/download/list/delete API + TaskDrawer集成(上传按钮/文件列表/下载链接/删除) + 20MB限制 + python-multipart依赖
3. **用户管理** — admin CRUD(create/update/disable) + 密码修改(PUT /users/me/password) + 前端UserManage页面(表格+新增/编辑对话框+启用禁用) + Layout密码修改对话框
4. **项目暂停/恢复** — ProjectSuspension模型 + suspend/resume/suspensions API + active任务冻结/解冻 + 前端暂停/恢复按钮 + 暂停原因弹窗
5. **任务问题升级** — TaskEscalation模型 + create/list/resolve API + 通知reviewer + 前端升级表单(严重等级选择+描述) + 升级列表(状态tag+解决方案)

### Session 5（P1功能完成）
1. **ECharts图表** — Reports.vue 集成 vue-echarts：任务状态饼图、产品线分布饼图、阶段堆叠柱状图、人员负荷水平柱状图 + 后端两个新端点(task-status-dist, product-type-dist)
2. **看板拖拽** — HTML5 native drag API，只允许正向状态转移，drag-over高亮目标列，拖拽悬停提示下一状态
3. **Excel导出** — 项目详情任务列表一键导出xlsx，包含编号/阶段/状态/负责人/排期字段

### Session 6（权限体系 + 功能扩充）

1. **用户组管理** — `UserGroup` + `UserGroupMember` 模型 + 7个CRUD端点 + `GroupManage.vue`（表格+展开成员列表+新增/编辑/删除/成员管理）
2. **角色权限管理（DB驱动）** — `RolePermission` 模型 + `_perm_cache` 缓存 + `require_permission(key)` 依赖注入替换 `require_roles()` + 14个权限项定义 + 启动时增量 seed + `PermissionManage.vue`（角色×权限矩阵勾选，自动保存，一键重置）
3. **甘特图重写** — 像素级渲染（28px/天），双行表头（月份分组+天），周末底纹，今日红线，横向滚动，修复 Vue 3 `v-if`+`v-for` 同元素崩溃问题
4. **项目详情页崩溃修复** — GanttChart import 错误导致整页崩溃，修复两处 bug（`v-if`优先级、CSS `v-bind`在`calc()`中无效）
5. **附件下载401修复** — 改用 axios blob 下载替代 `<a href>` 直链（后者不发 Authorization header）
6. **图片附件悬停预览** — 懒加载 blob URL，`el-tooltip` 展示预览图，`onUnmounted` 释放内存
7. **文件上传时间显示** — 附件列表展示 `created_at` 格式化时间
8. **任务开始自动排期** — `start_task` 端点：若无排期则以今天为开始、`estimated_days`（模板定义）计算结束日期；`Task` 模型新增 `estimated_days` 字段；`migrate.py` 一次性迁移脚本补加缺失列
9. **项目列表删除** — admin 专属删除按钮，级联清除任务/附件/依赖/通知等
10. **客户管理页** — `CustomerManage.vue`：表格（关联项目数/创建时间）+ 搜索 + 新增/编辑对话框 + 删除（有关联项目时禁用）；后端补全 `update_customer` / `delete_customer` + `CustomerResponse` 带 `project_count`；修复路由顺序导致的 422 错误（`/customers` 须在 `/{project_id}` 之前注册）
11. **新建项目改为选择客户** — 移除"自动创建客户"输入框，改为纯下拉选择
12. **PM 项目隔离** — `list_projects` 支持 `pm_scope_id`（PM只看自己负责+未指派的项目）；`get_project` / `update_project` / `init_project` / `suspend/resume` 均加 `_assert_pm_access` 检查
13. **菜单权限动态化** — 新增 6 个 `menu.*` 权限项（reports/templates/customers/users/groups/permissions）；`GET /api/permissions/me` 返回当前用户权限列表；auth store 登录时拉取并缓存权限；`Layout.vue` 侧边栏菜单改为 `auth.hasPermission('menu.xxx')` 动态显示，可在权限管理页实时调整

## 当前已注册路由汇总（65+个端点）

- `auth`: login, me
- `projects`: create, list, get, update, delete, init, suspend, resume, suspensions
- `projects/customers`: list, create, update, delete
- `tasks`: list, get, update, assign, start, submit, approve, reject, transitions, comments(get/post)
- `tasks/attachments`: upload, list, download, delete
- `tasks/escalations`: create, list, resolve
- `templates`: list, get, create, update, delete, toggle-active
- `dashboard`: my-workbench, overview, phase-stats, user-workload, task-status-dist, product-type-dist
- `users`: list, create, update, me/password, workload
- `notifications`: list, unread-count, mark-read, mark-all-read
- `groups`: list, create, update, delete, members(list/add/remove)
- `permissions`: list, update, reset, me
- `change-requests`: create, list, approve, reject
- `deliverables`: upload, list, download, delete
