export const STATUS_MAP = {
  pending: { label: '待处理', type: 'info' },
  active: { label: '进行中', type: 'primary' },
  review: { label: '待审核', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  paused: { label: '已暂停', type: 'info' },
  blocked: { label: '阻塞', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
  draft: { label: '草稿', type: 'info' },
  completed: { label: '已完成', type: 'success' },
  suspended: { label: '已暂停', type: 'warning' },
}

export const PRODUCT_TYPE_MAP = {
  dia: 'DIA专线',
  transmission: '传输',
  dark_fiber: '裸纤',
  sdwan: 'SD-WAN',
}

export const PHASE_MAP = {
  project_init: '项目立项',
  resource_confirm: '资源确认',
  procurement: '采购/协调',
  field_deploy: '施工开通',
  network_config: '网络配置',
  acceptance: '验收',
  project_close: '项目结项',
  // 传输
  site_survey: '现场勘察',
  solution_design: '方案设计',
  joint_test: '联调验收',
  // 裸纤
  route_survey: '路由勘察',
  resource_coord: '资源协调',
  construction_plan: '施工方案',
  construction: '施工实施',
  test_accept: '测试验收',
  // SD-WAN
  underlay_circuit: '底层线路',
  site_deploy: '站点部署',
  policy_config: '策略配置',
}

export const PHASE_ORDER_BY_PRODUCT = {
  dia: ['project_init', 'resource_confirm', 'procurement', 'field_deploy', 'network_config', 'acceptance', 'project_close'],
  transmission: ['project_init', 'site_survey', 'solution_design', 'resource_confirm', 'procurement', 'field_deploy', 'joint_test', 'project_close'],
  dark_fiber: ['project_init', 'route_survey', 'resource_coord', 'construction_plan', 'construction', 'test_accept', 'project_close'],
  sdwan: ['project_init', 'solution_design', 'procurement', 'underlay_circuit', 'site_deploy', 'policy_config', 'joint_test', 'project_close'],
}

export const PHASE_ORDER = PHASE_ORDER_BY_PRODUCT.dia

export const ROLE_MAP = {
  sales: '销售',
  pm: '项目经理',
  operations: '运营',
  procurement: '采购',
  network_engineer: '网络工程师',
  field_engineer: '现场实施',
  admin: '管理员',
}

export const PRIORITY_MAP = {
  1: { label: '最高', type: 'danger' },
  2: { label: '高', type: 'warning' },
  3: { label: '中', type: 'primary' },
  4: { label: '低', type: 'info' },
  5: { label: '最低', type: 'info' },
}
