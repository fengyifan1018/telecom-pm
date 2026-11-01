<script setup>
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import { ref, computed, watch, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { PRODUCT_TYPE_MAP, PHASE_MAP } from '../utils/constants'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '../utils/format'
import http from '../api/index'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')

const templates = ref([])
const loading = ref(false)
const expandedId = ref(null)

const showDialog = ref(false)
const dialogTitle = ref('')
const editingId = ref(null)
const submitLoading = ref(false)
const editorTab = ref('visual')
watch(editorTab, (tab) => {
  if (tab === 'json') { jsonDraft.value = JSON.stringify(editPhases.value, null, 2); jsonError.value = '' }
})

const formName = ref('')
const formProductType = ref('dia')
const editPhases = ref([])

const PRODUCT_TYPES = [
  { value: 'dia', label: 'DIA专线' },
  { value: 'transmission', label: '传输' },
  { value: 'dark_fiber', label: '裸纤' },
  { value: 'sdwan', label: 'SD-WAN' },
]

const ROLE_OPTIONS = [
  { value: 'pm', label: '项目经理' },
  { value: 'operations', label: '运营' },
  { value: 'procurement', label: '采购' },
  { value: 'network_engineer', label: '网络工程师' },
  { value: 'field_engineer', label: '现场实施' },
  { value: 'admin', label: '管理员' },
]

const ROLE_COLOR = {
  pm: 'var(--el-color-primary)',
  operations: 'var(--el-color-success)',
  procurement: 'var(--el-color-warning)',
  network_engineer: 'var(--el-text-color-secondary)',
  field_engineer: 'var(--el-color-danger)',
  admin: '#6f42c1',
}

const jsonPreview = computed(() => JSON.stringify(editPhases.value, null, 2))
// JSON 双向：文本编辑 → 解析回填编辑器（watch 在 editorTab 声明后注册）
const jsonDraft = ref('')
const jsonError = ref('')
function applyJson() {
  try {
    const parsed = JSON.parse(jsonDraft.value)
    if (!Array.isArray(parsed)) throw new Error('顶层必须是数组')
    editPhases.value = parsed
    editorTab.value = 'visual'
    ElMessage.success('JSON 已应用，请检查后保存')
  } catch (e) {
    jsonError.value = '解析失败：' + e.message
  }
}

// 版本历史
const versionList = ref([])
const versionDetail = ref(null)
const versionLoading = ref(false)
async function openVersions(t) {
  editingId.value = t.id
  dialogTitle.value = `历史版本：${t.name}`
  editPhases.value = JSON.parse(JSON.stringify(t.phases))
  formName.value = t.name
  editorTab.value = 'versions'
  versionDetail.value = null
  versionLoading.value = true
  showDialog.value = true
  try {
    const res = await http.get(`/templates/${t.id}/versions`)
    versionList.value = res.data
  } finally {
    versionLoading.value = false
  }
}
async function viewVersion(v) {
  const res = await http.get(`/templates/${editingId.value}/versions/${v.version}`)
  versionDetail.value = res.data
}
function loadVersionToEditor() {
  if (!versionDetail.value) return
  editPhases.value = JSON.parse(JSON.stringify(versionDetail.value.phases))
  editorTab.value = 'visual'
  ElMessage.success(`已载入 v${versionDetail.value.version} 内容，保存将生成新版本`)
}

// 新建时同产品线已有启用模板 → 保存将自动切换
const productTypeConflict = computed(() =>
  !editingId.value && templates.value.some(t => t.product_type === formProductType.value && t.is_active))

async function fetchTemplates() {
  loading.value = true
  try {
    const res = await http.get('/templates', { params: { include_inactive: isAdmin.value } })
    templates.value = res.data
  } finally {
    loading.value = false
  }
}
onMounted(fetchTemplates)

function getTotalTasks(t) { return t.phases.reduce((s, p) => s + (p.tasks?.length || 0), 0) }
function getTotalDays(t) { return t.phases.reduce((s, p) => s + (p.estimated_days || 0), 0) }
function toggleExpand(t) { expandedId.value = expandedId.value === t.id ? null : t.id }

function openCreate(fromTpl) {
  editingId.value = null
  if (fromTpl) {
    dialogTitle.value = '复制模板'
    formName.value = fromTpl.name + ' 副本'
    formProductType.value = fromTpl.product_type
    editPhases.value = JSON.parse(JSON.stringify(fromTpl.phases))
    ElMessage.info('已载入模板内容，可修改名称与细节后保存')
  } else {
    dialogTitle.value = '新建模板'
    formName.value = ''
    formProductType.value = 'dia'
    editPhases.value = []
  }
  editorTab.value = 'visual'
  showDialog.value = true
}

function openCopy(t) { openCreate(t) }

function openEdit(t) {
  editingId.value = t.id
  dialogTitle.value = `编辑：${t.name}`
  formName.value = t.name
  editPhases.value = JSON.parse(JSON.stringify(t.phases))
  editorTab.value = 'visual'
  showDialog.value = true
}

function addPhase() {
  const idx = editPhases.value.length
  editPhases.value.push({
    phase: `phase_${idx + 1}`,
    name: '新阶段',
    order: idx + 1,
    role: 'pm',
    depends_on: [],
    estimated_days: 3,
    tasks: [],
  })
}

function removePhase(idx) {
  const key = editPhases.value[idx].phase
  editPhases.value.splice(idx, 1)
  for (const p of editPhases.value) {
    p.depends_on = (p.depends_on || []).filter(d => d !== key)
  }
}

function movePhase(idx, dir) {
  const arr = editPhases.value
  const t = idx + dir
  if (t < 0 || t >= arr.length) return
  ;[arr[idx], arr[t]] = [arr[t], arr[idx]]
}

function addTask(phase) {
  if (!phase.tasks) phase.tasks = []
  phase.tasks.push({ title: '', required: true, estimated_days: 1 })
}

function removeTask(phase, idx) {
  phase.tasks.splice(idx, 1)
}

function validate() {
  if (!formName.value.trim()) { ElMessage.error('请输入模板名称'); return false }
  if (!editPhases.value.length) { ElMessage.error('至少需要一个阶段'); return false }
  const keys = new Set()
  for (const [i, p] of editPhases.value.entries()) {
    if (!p.phase?.trim()) { ElMessage.error(`第${i + 1}个阶段的标识不能为空`); return false }
    if (!p.name?.trim()) { ElMessage.error(`第${i + 1}个阶段的名称不能为空`); return false }
    if (keys.has(p.phase)) { ElMessage.error(`阶段标识 "${p.phase}" 重复`); return false }
    keys.add(p.phase)
    for (const dep of p.depends_on || []) {
      if (!editPhases.value.some(x => x.phase === dep)) {
        ElMessage.error(`阶段"${p.name}"的前置 "${dep}" 不存在`); return false
      }
    }
    for (const [j, task] of (p.tasks || []).entries()) {
      if (!task.title?.trim()) { ElMessage.error(`阶段"${p.name}"第${j + 1}个任务标题不能为空`); return false }
    }
  }
  // 环检测（DFS 染色）
  const color = {}
  const byKey = Object.fromEntries(editPhases.value.map(p => [p.phase, p]))
  let cycleAt = null
  const dfs = (k) => {
    color[k] = 1
    for (const dep of byKey[k]?.depends_on || []) {
      if (color[dep] === 1) { cycleAt = `${k} → ${dep}`; return false }
      if (!color[dep] && !dfs(dep)) return false
    }
    color[k] = 2
    return true
  }
  for (const k of keys) {
    if (!color[k] && !dfs(k)) {
      ElMessage.error(`前置阶段存在循环依赖：${cycleAt}`); return false
    }
  }
  return true
}

async function handleSubmit() {
  if (!validate()) return
  submitLoading.value = true
  try {
    const phases = editPhases.value.map((p, i) => ({ ...p, order: i + 1 }))
    if (editingId.value) {
      await http.put(`/templates/${editingId.value}`, { name: formName.value, phases })
      ElMessage.success('模板已更新（版本+1）')
    } else {
      await http.post('/templates', { name: formName.value, product_type: formProductType.value, phases })
      ElMessage.success('模板已创建')
    }
    showDialog.value = false
    await fetchTemplates()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    submitLoading.value = false
  }
}

async function toggleActive(t) {
  const action = t.is_active ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}模板 "${t.name}"?`, `${action}模板`, { type: 'warning' })
    await http.put(`/templates/${t.id}`, { is_active: !t.is_active })
    ElMessage.success(`已${action}`)
    await fetchTemplates()
  } catch (e) {
    // 取消无需提示，请求错误由全局拦截器统一处理
  }
}
</script>

<template>
  <div>
    <PageHeader title="流程模板管理">
      <el-button v-if="isAdmin" type="primary" @click="openCreate">新建模板</el-button>
    </PageHeader>

    <el-skeleton v-if="loading" :rows="6" animated />
    <el-row v-else :gutter="16">
      <el-col :span="24" v-for="t in templates" :key="t.id" style="margin-bottom: 16px">
        <el-card :class="{ 'template-inactive': !t.is_active }">
          <div class="template-header" @click="toggleExpand(t)">
            <div>
              <h4 style="margin: 0 0 4px">{{ t.name }}</h4>
              <el-space>
                <el-tag size="small">{{ PRODUCT_TYPE_MAP[t.product_type] || t.product_type }}</el-tag>
                <el-tag type="info" size="small">v{{ t.version }}</el-tag>
                <el-tag :type="t.is_active ? 'success' : 'danger'" size="small">{{ t.is_active ? '启用中' : '已停用' }}</el-tag>
                <span style="font-size: 12px; color: var(--el-text-color-secondary)">
                  {{ t.phases.length }} 阶段 · {{ getTotalTasks(t) }} 任务 · 预估 {{ getTotalDays(t) }} 工作日 · 被 {{ t.usage_count ?? 0 }} 个项目使用
                </span>
              </el-space>
            </div>
            <div style="display: flex; align-items: center; gap: 8px">
              <template v-if="isAdmin">
                <el-button size="small" text type="primary" @click.stop="openEdit(t)">编辑</el-button>
                <el-button size="small" text @click.stop="openVersions(t)">历史</el-button>
                <el-button size="small" text @click.stop="openCopy(t)">复制</el-button>
                <el-button size="small" text :type="t.is_active ? 'danger' : 'success'" @click.stop="toggleActive(t)">
                  {{ t.is_active ? '停用' : '启用' }}
                </el-button>
              </template>
              <span style="font-size: 18px; color: var(--el-text-color-placeholder); transition: transform 0.2s; display: inline-block"
                :style="{ transform: expandedId === t.id ? 'rotate(180deg)' : '' }">▾</span>
            </div>
          </div>

          <!-- Expanded: Phase Flow -->
          <div v-if="expandedId === t.id" style="margin-top: 16px">
            <div class="phase-flow">
              <template v-for="(phase, idx) in t.phases" :key="phase.phase">
                <div class="phase-block" :style="{ borderTopColor: ROLE_COLOR[phase.role] || 'var(--el-color-primary)' }">
                  <div class="phase-block-header">
                    <span class="phase-number" :style="{ background: ROLE_COLOR[phase.role] || 'var(--el-color-primary)' }">{{ idx + 1 }}</span>
                    <span class="phase-block-name">{{ phase.name }}</span>
                    <el-tag size="small" type="info">{{ phase.estimated_days }}天</el-tag>
                  </div>
                  <div v-if="phase.depends_on?.length" class="phase-deps">
                    前置: {{ phase.depends_on.map(d => PHASE_MAP[d] || d).join(', ') }}
                  </div>
                  <div class="phase-tasks">
                    <div v-for="task in phase.tasks" :key="task.title" class="phase-task-item">
                      <span :class="{ 'is-required': task.required }">{{ task.required ? '●' : '○' }}</span>
                      {{ task.title }}
                      <span style="color: var(--el-text-color-placeholder); margin-left: auto; font-size: 12px">{{ task.estimated_days }}天</span>
                    </div>
                  </div>
                </div>
                <div v-if="idx < t.phases.length - 1" class="phase-connector">→</div>
              </template>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <EmptyState v-if="!loading && templates.length === 0" text="暂无模板" />

    <!-- Editor Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="dialogTitle"
      width="960px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <!-- Basic Info -->
      <div class="editor-meta">
        <el-alert v-if="!editingId && productTypeConflict" type="warning" :closable="false" show-icon
                  style="margin-bottom: 12px"
                  :title="`产品线「${PRODUCT_TYPE_MAP[formProductType]}」已有启用模板，保存后原模板将自动停用切换为本次新建`" />
        <el-form inline label-width="80px">
          <el-form-item label="模板名称" required>
            <el-input v-model="formName" placeholder="如: DIA专线标准流程v2" style="width: 260px" />
          </el-form-item>
          <el-form-item v-if="!editingId" label="产品线">
            <el-select v-model="formProductType" style="width: 140px">
              <el-option v-for="pt in PRODUCT_TYPES" :key="pt.value" :label="pt.label" :value="pt.value" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <el-tabs v-model="editorTab" style="margin-top: 4px">
        <!-- ===== Visual Editor Tab ===== -->
        <el-tab-pane label="可视化编辑" name="visual">
          <!-- Flow Strip Preview -->
          <div class="flow-strip" v-if="editPhases.length">
            <template v-for="(phase, idx) in editPhases" :key="idx">
              <div class="strip-node" :style="{ borderColor: ROLE_COLOR[phase.role] || 'var(--el-color-primary)' }">
                <span class="strip-num" :style="{ background: ROLE_COLOR[phase.role] || 'var(--el-color-primary)' }">{{ idx + 1 }}</span>
                <span class="strip-name">{{ phase.name || '?' }}</span>
                <span class="strip-days">{{ phase.estimated_days }}天</span>
              </div>
              <div v-if="idx < editPhases.length - 1" class="strip-arrow">→</div>
            </template>
          </div>
          <div v-else class="flow-strip flow-strip-empty">点击下方"添加阶段"开始构建流程</div>

          <!-- Phase Cards -->
          <div class="phase-editor-list">
            <div v-for="(phase, idx) in editPhases" :key="idx" class="phase-edit-card"
              :style="{ borderLeftColor: ROLE_COLOR[phase.role] || 'var(--el-color-primary)' }">

              <!-- Phase Header Row -->
              <div class="phase-edit-header">
                <span class="phase-edit-num" :style="{ background: ROLE_COLOR[phase.role] || 'var(--el-color-primary)' }">{{ idx + 1 }}</span>
                <el-input v-model="phase.name" placeholder="阶段名称" style="width: 140px" />
                <el-input
                  v-model="phase.phase"
                  placeholder="标识(英文)"
                  style="width: 150px; font-family: monospace; font-size: 12px"
                  size="default"
                />
                <el-select v-model="phase.role" style="width: 120px">
                  <el-option v-for="r in ROLE_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
                </el-select>
                <el-input-number
                  v-model="phase.estimated_days"
                  :min="1" :max="365"
                  controls-position="right"
                  style="width: 90px"
                />
                <span style="font-size: 12px; color: var(--el-text-color-secondary)">天</span>
                <div style="margin-left: auto; display: flex; gap: 2px">
                  <el-button text size="small" :disabled="idx === 0" @click="movePhase(idx, -1)">↑</el-button>
                  <el-button text size="small" :disabled="idx === editPhases.length - 1" @click="movePhase(idx, 1)">↓</el-button>
                  <el-button text type="danger" size="small" @click="removePhase(idx)">删除</el-button>
                </div>
              </div>

              <!-- Depends On -->
              <div class="phase-edit-deps">
                <span class="deps-label">前置阶段：</span>
                <el-select
                  v-model="phase.depends_on"
                  multiple
                  placeholder="无前置依赖（并行/起始阶段）"
                  style="flex: 1"
                  size="small"
                >
                  <el-option
                    v-for="(p, i) in editPhases.filter((_, i) => i !== idx)"
                    :key="p.phase"
                    :label="`${p.name || p.phase}`"
                    :value="p.phase"
                  />
                </el-select>
              </div>

              <!-- Tasks -->
              <el-table
                :data="phase.tasks"
                size="small"
                style="margin-top: 8px"
                empty-text="暂无任务，点击下方添加"
              >
                <el-table-column label="任务名称" min-width="200">
                  <template #default="{ row }">
                    <el-input v-model="row.title" size="small" placeholder="任务名称" />
                  </template>
                </el-table-column>
                <el-table-column label="必须" width="60" align="center" header-align="center">
                  <template #default="{ row }">
                    <el-checkbox v-model="row.required" />
                  </template>
                </el-table-column>
                <el-table-column label="预估天" width="100">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.estimated_days"
                      :min="1" :max="90"
                      size="small"
                      controls-position="right"
                      style="width: 80px"
                    />
                  </template>
                </el-table-column>
                <el-table-column width="44" align="center">
                  <template #default="{ $index }">
                    <el-button text type="danger" size="small" @click="removeTask(phase, $index)">×</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-button text type="primary" size="small" @click="addTask(phase)" style="margin-top: 6px; padding-left: 0">
                + 添加任务
              </el-button>
            </div>
          </div>

          <el-button @click="addPhase" style="width: 100%; margin-top: 12px; border-style: dashed">
            + 添加阶段
          </el-button>
        </el-tab-pane>

        <!-- ===== JSON Preview Tab ===== -->
        <el-tab-pane label="JSON 编辑" name="json">
          <el-alert v-if="jsonError" type="error" :closable="false" show-icon :title="jsonError" style="margin-bottom: 8px" />
          <el-input
            v-model="jsonDraft"
            type="textarea"
            :rows="20"
            spellcheck="false"
            style="font-family: monospace; font-size: 12px"
          />
          <div style="margin-top: 8px; display: flex; gap: 8px">
            <el-button type="primary" @click="applyJson">应用到编辑器</el-button>
            <el-button @click="jsonDraft = JSON.stringify(editPhases.value, null, 2); jsonError = ''">重置为当前内容</el-button>
          </div>
        </el-tab-pane>
        <el-tab-pane label="历史版本" name="versions">
          <div v-if="versionLoading" style="padding: 20px; text-align: center">加载中...</div>
          <template v-else>
            <div v-if="versionList.length === 0" style="color: var(--el-text-color-secondary); font-size: 13px; padding: 12px 0">
              暂无历史版本（每次修改任务结构会自动保存旧版本）
            </div>
            <el-table v-else :data="versionList" size="small" highlight-current-row @row-click="viewVersion" style="cursor: pointer">
              <el-table-column prop="version" label="版本" width="80">
                <template #default="{ row }">v{{ row.version }}</template>
              </el-table-column>
              <el-table-column prop="created_at" label="保存时间" width="170">
                <template #default="{ row }">{{ formatDateTime(row.created_at, true) }}</template>
              </el-table-column>
              <el-table-column label="" width="110">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click.stop="viewVersion(row)">查看</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="versionDetail" style="margin-top: 12px">
              <div class="section-label">v{{ versionDetail.version }} 内容（{{ versionDetail.phases.length }} 阶段）</div>
              <el-input
                :value="JSON.stringify(versionDetail.phases, null, 2)"
                type="textarea" :rows="10" readonly
                style="font-family: monospace; font-size: 12px"
              />
              <el-button type="primary" size="small" style="margin-top: 8px" @click="loadVersionToEditor">
                载入编辑器（保存后生成新版本）
              </el-button>
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          {{ editingId ? '保存修改' : '创建模板' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
}
.template-inactive { opacity: 0.6; }

/* Read-only phase flow */
.phase-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0;
}
.phase-block {
  background: var(--el-fill-color-lighter);
  border: 1px solid #ebeef5;
  border-top: 3px solid var(--el-color-primary);
  border-radius: 6px;
  padding: 12px;
  min-width: 180px;
  max-width: 220px;
  flex: 1;
}
.phase-block-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.phase-number {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.phase-block-name { font-weight: bold; font-size: 13px; }
.phase-deps { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 6px; }
.phase-tasks { display: flex; flex-direction: column; gap: 3px; }
.phase-task-item {
  font-size: 12px;
  display: flex; align-items: center; gap: 5px; padding: 2px 0;
}
.is-required { color: var(--el-color-danger); }
.phase-connector {
  align-self: center;
  padding: 0 6px;
  color: var(--el-text-color-placeholder);
  font-size: 18px;
  flex-shrink: 0;
}

/* Editor */
.editor-meta {
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  padding: 12px 16px 4px;
  margin-bottom: 8px;
}

/* Flow strip */
.flow-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 6px;
  margin-bottom: 12px;
  min-height: 48px;
}
.flow-strip-empty {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}
.strip-node {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--el-bg-color);
  border: 1.5px solid var(--el-color-primary);
  border-radius: 20px;
  padding: 3px 10px 3px 4px;
  font-size: 12px;
}
.strip-num {
  width: 18px; height: 18px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.strip-name { font-weight: 500; }
.strip-days { color: var(--el-text-color-secondary); font-size: 12px; }
.strip-arrow { color: var(--el-text-color-placeholder); font-size: 14px; }

/* Phase editor cards */
.phase-editor-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 440px;
  overflow-y: auto;
  padding-right: 4px;
}
.phase-edit-card {
  border: 1px solid #ebeef5;
  border-left: 4px solid var(--el-color-primary);
  border-radius: 6px;
  padding: 12px 14px;
  background: var(--el-bg-color);
}
.phase-edit-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.phase-edit-num {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.phase-edit-deps {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.deps-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
</style>
