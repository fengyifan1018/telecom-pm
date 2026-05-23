from app.models.workflow_template import WorkflowTemplate

DIA_PHASES = [
    {
        "phase": "project_init",
        "name": "项目立项",
        "order": 1,
        "role": "pm",
        "depends_on": [],
        "estimated_days": 2,
        "tasks": [
            {"title": "项目信息录入", "required": True, "estimated_days": 1},
            {"title": "带宽/IP需求确认", "required": True, "estimated_days": 1},
            {"title": "接入方式确认", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "resource_confirm",
        "name": "资源确认",
        "order": 2,
        "role": "operations",
        "depends_on": ["project_init"],
        "estimated_days": 3,
        "tasks": [
            {"title": "末端接入资源确认", "required": True, "estimated_days": 1},
            {"title": "上游运营商通道确认", "required": True, "estimated_days": 2},
            {"title": "IP地址分配", "required": True, "estimated_days": 1},
            {"title": "端口预留", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "procurement",
        "name": "采购/协调",
        "order": 3,
        "role": "procurement",
        "depends_on": ["resource_confirm"],
        "estimated_days": 5,
        "tasks": [
            {"title": "CPE设备确认", "required": True, "estimated_days": 1},
            {"title": "光模块采购", "required": False, "estimated_days": 3},
            {"title": "发货安排", "required": True, "estimated_days": 2},
        ],
    },
    {
        "phase": "field_deploy",
        "name": "施工开通",
        "order": 4,
        "role": "field_engineer",
        "depends_on": ["resource_confirm", "procurement"],
        "estimated_days": 3,
        "tasks": [
            {"title": "末端线路接入", "required": True, "estimated_days": 1},
            {"title": "CPE安装配置", "required": True, "estimated_days": 1},
            {"title": "端口开通", "required": True, "estimated_days": 1},
            {"title": "基础连通测试", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "network_config",
        "name": "网络配置",
        "order": 5,
        "role": "network_engineer",
        "depends_on": ["field_deploy"],
        "estimated_days": 2,
        "tasks": [
            {"title": "路由配置", "required": True, "estimated_days": 1},
            {"title": "带宽策略配置", "required": True, "estimated_days": 1},
            {"title": "ACL/安全策略", "required": True, "estimated_days": 1},
            {"title": "网管纳管", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "acceptance",
        "name": "验收",
        "order": 6,
        "role": "network_engineer",
        "depends_on": ["network_config"],
        "estimated_days": 2,
        "tasks": [
            {"title": "带宽测试", "required": True, "estimated_days": 1},
            {"title": "延迟/丢包测试", "required": True, "estimated_days": 1},
            {"title": "冗余切换测试", "required": False, "estimated_days": 1},
            {"title": "客户验收确认", "required": True, "estimated_days": 1},
            {"title": "验收报告", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "project_close",
        "name": "项目结项",
        "order": 7,
        "role": "operations",
        "depends_on": ["acceptance"],
        "estimated_days": 2,
        "tasks": [
            {"title": "资源系统录入", "required": True, "estimated_days": 1},
            {"title": "监控告警配置", "required": True, "estimated_days": 1},
            {"title": "项目关闭", "required": True, "estimated_days": 1},
        ],
    },
]


TRANSMISSION_PHASES = [
    {
        "phase": "project_init",
        "name": "项目立项",
        "order": 1,
        "role": "pm",
        "depends_on": [],
        "estimated_days": 2,
        "tasks": [
            {"title": "项目信息录入确认", "required": True, "estimated_days": 1},
            {"title": "客户需求澄清", "required": True, "estimated_days": 1},
            {"title": "交付团队组建", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "site_survey",
        "name": "现场勘察",
        "order": 2,
        "role": "field_engineer",
        "depends_on": ["project_init"],
        "estimated_days": 3,
        "tasks": [
            {"title": "客户侧机房环境确认", "required": True, "estimated_days": 1},
            {"title": "传输路由方案确认", "required": True, "estimated_days": 1},
            {"title": "勘察报告提交", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "solution_design",
        "name": "方案设计",
        "order": 3,
        "role": "network_engineer",
        "depends_on": ["site_survey"],
        "estimated_days": 4,
        "tasks": [
            {"title": "传输通道设计", "required": True, "estimated_days": 1},
            {"title": "端口/时隙规划", "required": True, "estimated_days": 1},
            {"title": "网管配置方案", "required": True, "estimated_days": 1},
            {"title": "方案评审", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "resource_confirm",
        "name": "资源确认",
        "order": 4,
        "role": "operations",
        "depends_on": ["solution_design"],
        "estimated_days": 3,
        "tasks": [
            {"title": "传输通道资源核实", "required": True, "estimated_days": 1},
            {"title": "跨运营商资源协调", "required": False, "estimated_days": 2},
            {"title": "资源锁定确认", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "procurement",
        "name": "采购",
        "order": 5,
        "role": "procurement",
        "depends_on": ["solution_design"],
        "estimated_days": 5,
        "tasks": [
            {"title": "设备需求确认", "required": True, "estimated_days": 1},
            {"title": "供应商询价/下单", "required": True, "estimated_days": 2},
            {"title": "到货验收", "required": True, "estimated_days": 1},
            {"title": "发货至站点", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "field_deploy",
        "name": "施工实施",
        "order": 6,
        "role": "field_engineer",
        "depends_on": ["resource_confirm", "procurement"],
        "estimated_days": 4,
        "tasks": [
            {"title": "设备上架安装", "required": True, "estimated_days": 1},
            {"title": "光路/电路接入", "required": True, "estimated_days": 1},
            {"title": "传输配置开通", "required": True, "estimated_days": 1},
            {"title": "环路测试", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "joint_test",
        "name": "联调验收",
        "order": 7,
        "role": "network_engineer",
        "depends_on": ["field_deploy"],
        "estimated_days": 3,
        "tasks": [
            {"title": "端到端业务验证", "required": True, "estimated_days": 1},
            {"title": "性能指标测试", "required": True, "estimated_days": 1},
            {"title": "客户验收签字", "required": True, "estimated_days": 1},
            {"title": "验收报告提交", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "project_close",
        "name": "项目结项",
        "order": 8,
        "role": "operations",
        "depends_on": ["joint_test"],
        "estimated_days": 2,
        "tasks": [
            {"title": "文档归档", "required": True, "estimated_days": 1},
            {"title": "运维交接", "required": True, "estimated_days": 1},
        ],
    },
]

DARK_FIBER_PHASES = [
    {
        "phase": "project_init",
        "name": "项目立项",
        "order": 1,
        "role": "pm",
        "depends_on": [],
        "estimated_days": 2,
        "tasks": [
            {"title": "项目信息录入", "required": True, "estimated_days": 1},
            {"title": "A/Z端地址确认", "required": True, "estimated_days": 1},
            {"title": "初步路由评估", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "route_survey",
        "name": "路由勘察",
        "order": 2,
        "role": "field_engineer",
        "depends_on": ["project_init"],
        "estimated_days": 5,
        "tasks": [
            {"title": "A端机房勘察", "required": True, "estimated_days": 1},
            {"title": "Z端机房勘察", "required": True, "estimated_days": 1},
            {"title": "中间路由勘察", "required": True, "estimated_days": 2},
            {"title": "管道/杆路资源确认", "required": True, "estimated_days": 1},
            {"title": "勘察报告+路由图", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "resource_coord",
        "name": "资源协调",
        "order": 3,
        "role": "operations",
        "depends_on": ["route_survey"],
        "estimated_days": 5,
        "tasks": [
            {"title": "光缆资源确认", "required": True, "estimated_days": 1},
            {"title": "管道使用许可申请", "required": True, "estimated_days": 2},
            {"title": "占道/施工许可", "required": False, "estimated_days": 3},
            {"title": "资源费用确认", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "construction_plan",
        "name": "施工方案",
        "order": 4,
        "role": "network_engineer",
        "depends_on": ["route_survey"],
        "estimated_days": 3,
        "tasks": [
            {"title": "光缆敷设方案", "required": True, "estimated_days": 1},
            {"title": "熔接方案", "required": True, "estimated_days": 1},
            {"title": "施工排期", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "construction",
        "name": "施工实施",
        "order": 5,
        "role": "field_engineer",
        "depends_on": ["resource_coord", "construction_plan"],
        "estimated_days": 10,
        "tasks": [
            {"title": "光缆敷设", "required": True, "estimated_days": 5},
            {"title": "光纤熔接", "required": True, "estimated_days": 2},
            {"title": "ODF跳纤", "required": True, "estimated_days": 1},
            {"title": "施工记录", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "test_accept",
        "name": "测试验收",
        "order": 6,
        "role": "network_engineer",
        "depends_on": ["construction"],
        "estimated_days": 3,
        "tasks": [
            {"title": "OTDR测试", "required": True, "estimated_days": 1},
            {"title": "光功率测试", "required": True, "estimated_days": 1},
            {"title": "测试报告", "required": True, "estimated_days": 1},
            {"title": "客户验收签字", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "project_close",
        "name": "项目结项",
        "order": 7,
        "role": "operations",
        "depends_on": ["test_accept"],
        "estimated_days": 2,
        "tasks": [
            {"title": "纤芯标识录入资源系统", "required": True, "estimated_days": 1},
            {"title": "文档归档", "required": True, "estimated_days": 1},
            {"title": "项目关闭", "required": True, "estimated_days": 1},
        ],
    },
]

SDWAN_PHASES = [
    {
        "phase": "project_init",
        "name": "项目立项",
        "order": 1,
        "role": "pm",
        "depends_on": [],
        "estimated_days": 2,
        "tasks": [
            {"title": "项目信息录入", "required": True, "estimated_days": 1},
            {"title": "站点清单确认", "required": True, "estimated_days": 1},
            {"title": "带宽/线路需求确认", "required": True, "estimated_days": 1},
            {"title": "组网拓扑确认", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "solution_design",
        "name": "方案设计",
        "order": 2,
        "role": "network_engineer",
        "depends_on": ["project_init"],
        "estimated_days": 5,
        "tasks": [
            {"title": "组网方案设计", "required": True, "estimated_days": 2},
            {"title": "CPE选型", "required": True, "estimated_days": 1},
            {"title": "策略规划(QoS/安全/路由)", "required": True, "estimated_days": 1},
            {"title": "控制器部署方案", "required": True, "estimated_days": 1},
            {"title": "方案评审", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "procurement",
        "name": "采购",
        "order": 3,
        "role": "procurement",
        "depends_on": ["solution_design"],
        "estimated_days": 5,
        "tasks": [
            {"title": "CPE设备采购", "required": True, "estimated_days": 2},
            {"title": "License采购", "required": True, "estimated_days": 1},
            {"title": "设备预配置(ZTP模板)", "required": True, "estimated_days": 1},
            {"title": "分站点发货", "required": True, "estimated_days": 2},
        ],
    },
    {
        "phase": "underlay_circuit",
        "name": "底层线路",
        "order": 4,
        "role": "operations",
        "depends_on": ["project_init"],
        "estimated_days": 5,
        "tasks": [
            {"title": "各站点Underlay线路开通", "required": True, "estimated_days": 3},
            {"title": "线路测试", "required": True, "estimated_days": 1},
            {"title": "线路信息登记", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "site_deploy",
        "name": "站点部署",
        "order": 5,
        "role": "field_engineer",
        "depends_on": ["procurement", "underlay_circuit"],
        "estimated_days": 5,
        "tasks": [
            {"title": "CPE安装上电", "required": True, "estimated_days": 1},
            {"title": "线路对接", "required": True, "estimated_days": 1},
            {"title": "设备注册上线", "required": True, "estimated_days": 1},
            {"title": "各站点逐一开通", "required": True, "estimated_days": 2},
        ],
    },
    {
        "phase": "policy_config",
        "name": "策略配置",
        "order": 6,
        "role": "network_engineer",
        "depends_on": ["site_deploy"],
        "estimated_days": 3,
        "tasks": [
            {"title": "Overlay隧道建立", "required": True, "estimated_days": 1},
            {"title": "路由策略下发", "required": True, "estimated_days": 1},
            {"title": "QoS策略下发", "required": True, "estimated_days": 1},
            {"title": "安全策略下发", "required": True, "estimated_days": 1},
            {"title": "应用识别策略", "required": False, "estimated_days": 1},
        ],
    },
    {
        "phase": "joint_test",
        "name": "联调验收",
        "order": 7,
        "role": "network_engineer",
        "depends_on": ["site_deploy", "policy_config"],
        "estimated_days": 3,
        "tasks": [
            {"title": "端到端连通验证", "required": True, "estimated_days": 1},
            {"title": "策略生效验证", "required": True, "estimated_days": 1},
            {"title": "故障切换测试", "required": True, "estimated_days": 1},
            {"title": "性能基线测试", "required": True, "estimated_days": 1},
            {"title": "客户UAT", "required": True, "estimated_days": 1},
            {"title": "验收报告", "required": True, "estimated_days": 1},
        ],
    },
    {
        "phase": "project_close",
        "name": "项目结项",
        "order": 8,
        "role": "operations",
        "depends_on": ["joint_test"],
        "estimated_days": 2,
        "tasks": [
            {"title": "平台监控配置", "required": True, "estimated_days": 1},
            {"title": "运维文档移交", "required": True, "estimated_days": 1},
            {"title": "客户培训", "required": False, "estimated_days": 1},
            {"title": "项目关闭", "required": True, "estimated_days": 1},
        ],
    },
]


def get_dia_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        product_type="dia",
        name="DIA专线接入标准流程",
        version=1,
        is_active=True,
        phases=DIA_PHASES,
    )


def get_transmission_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        product_type="transmission",
        name="传输产品标准交付流程",
        version=1,
        is_active=True,
        phases=TRANSMISSION_PHASES,
    )


def get_dark_fiber_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        product_type="dark_fiber",
        name="裸纤产品标准交付流程",
        version=1,
        is_active=True,
        phases=DARK_FIBER_PHASES,
    )


def get_sdwan_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        product_type="sdwan",
        name="SD-WAN标准交付流程",
        version=1,
        is_active=True,
        phases=SDWAN_PHASES,
    )
