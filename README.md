# 通信项目任务管理系统

面向通信行业的项目全生命周期管理平台，支持 DIA、传输、裸纤、SD-WAN 四条产品线，覆盖从立项到交付的多角色协作流程。

## 功能概览

- **项目管理** — 创建、立项、暂停/恢复、归档，支持按产品线/状态筛选
- **任务流转** — 模板驱动自动生成任务，多阶段状态机（待分配→进行中→审核→完成）
- **客户管理** — 客户档案 CRUD，与项目关联
- **任务看板** — 拖拽式看板，支持跨列状态转移
- **甘特图** — 天级精度时间轴，周末底纹，今日标线
- **通知系统** — 指派/审核/退回/超期自动推送站内通知
- **文件附件** — 任务附件上传/下载/图片悬停预览
- **变更申请（CR）** — 提交→审批工作流
- **问题升级** — 任务阻塞时升级，通知审核人
- **报表中心** — ECharts 图表（任务状态、产品线分布、阶段统计、人员负荷）
- **权限管理** — DB 驱动的角色×权限矩阵，实时勾选生效，菜单动态显示
- **用户/用户组管理** — 账号 CRUD，分组管理
- **操作审计** — 记录登录、增删改、权限变更等关键操作日志

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLAlchemy 2.0 (async) · aiosqlite · JWT |
| 前端 | Vue 3 · Element Plus · Pinia · Vue Router · Axios · Vite · ECharts |
| 数据库 | SQLite（开发/小团队）|

## 角色说明

| 角色 | 标识 | 主要权限 |
|---|---|---|
| 管理员 | admin | 全部权限 |
| 项目经理 | pm | 立项、指派、审核、暂停/恢复，只能管理自己的项目 |
| 销售 | sales | 创建项目，查看自己的项目 |
| 运营 | operations | 查看报表 |
| 采购 | procurement | 处理采购相关任务 |
| 网络工程师 | network_engineer | 处理网络配置任务 |
| 现场实施 | field_engineer | 处理施工/开通任务 |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+

### 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e .
python -m app.seed.run_seed   # 初始化演示数据
python migrate.py             # 补充数据库字段（已有 DB 时执行）
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### 演示账号

密码均为 `123456`

| 用户名 | 角色 |
|---|---|
| admin | 管理员 |
| pm01 | 项目经理 |
| sales01 | 销售 |
| ops01 | 运营 |
| eng01 | 网络工程师 |
| field01 | 现场实施 |
| proc01 | 采购 |

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/          # 路由端点
│   │   ├── models/       # ORM 模型
│   │   ├── schemas/      # Pydantic 序列化
│   │   ├── services/     # 业务逻辑（流程引擎、通知、审计等）
│   │   └── seed/         # 演示数据
│   ├── migrate.py        # 一次性字段迁移脚本
│   └── tests/            # 集成测试 + 流程引擎单元测试
└── frontend/
    └── src/
        ├── api/          # Axios 接口封装
        ├── components/   # Layout · TaskDrawer · GanttChart · PhaseProgress
        ├── stores/       # Pinia（auth + 权限缓存）
        └── views/        # 各页面
```

## 生产部署

参考 [部署指南](#部署)：nginx 反代 + systemd 守护进程 + 前端静态文件。

### 关键配置（backend/.env）

```env
SECRET_KEY=替换为随机长字符串
DATABASE_URL=sqlite+aiosqlite:///./data.db
ACCESS_TOKEN_EXPIRE_MINUTES=480
DEBUG=false
UPLOAD_DIR=./uploads
```

### nginx 核心配置

```nginx
location / {
    root /path/to/frontend/dist;
    try_files $uri $uri/ /index.html;
}
location /api/ {
    proxy_pass http://127.0.0.1:8000;
}
```

### systemd 服务

```bash
gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
```

## 开发说明

- 权限系统：`require_permission("key")` 依赖注入，启动时自动 seed 缺失权限行
- 新增数据库列：在模型中添加字段后，同步在 `migrate.py` 的 `MIGRATIONS` 列表里补充 ALTER TABLE
- 流程引擎：`app/services/flow_engine.py`，状态转换规则集中定义
