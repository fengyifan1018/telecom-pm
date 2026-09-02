<script setup>
import { ref, computed, watch, onMounted, onUnmounted, onBeforeUnmount } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { startTask, submitTask, approveTask, rejectTask, assignTask, updateTask, getComments, addComment, getTransitions, listUsers, listAttachments, uploadAttachment, deleteAttachment, getAttachmentDownloadUrl, listEscalations, createEscalation, resolveEscalation, listTasks, getTaskRelations, addTaskRelation, deleteTaskRelation } from '../api/tasks'
import http from '../api/index'
import EmptyState from './EmptyState.vue'
import { STATUS_MAP, PHASE_MAP, ROLE_MAP } from '../utils/constants'
import { formatDateTime } from '../utils/format'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  task: { type: Object, default: null },
  visible: { type: Boolean, default: false },
  showProjectLink: { type: Boolean, default: false },
  peerIds: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:visible', 'refresh', 'view-project', 'navigate'])

// 抽屉内上一条/下一条导航（调用方传入当前列表的任务 id 序列）
const navIndex = computed(() => (props.task && props.peerIds.length ? props.peerIds.indexOf(props.task.id) : -1))
const hasPrev = computed(() => navIndex.value > 0)
const hasNext = computed(() => navIndex.value >= 0 && navIndex.value < props.peerIds.length - 1)
function goPrev() { if (hasPrev.value) emit('navigate', props.peerIds[navIndex.value - 1]) }
function goNext() { if (hasNext.value) emit('navigate', props.peerIds[navIndex.value + 1]) }

const auth = useAuthStore()

const windowWidth = ref(window.innerWidth)
const onResize = () => { windowWidth.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
const isMobile = computed(() => windowWidth.value < 768)

const canStart = computed(() => {
  if (!props.task) return false
  const role = auth.user?.role
  if (role === 'pm' || role === 'admin') return true
  return props.task.assignee_id === auth.user?.id
})

const comments = ref([])
const transitions = ref([])
const newComment = ref('')
const loading = ref(false)
const users = ref([])
const assigneeId = ref(null)
const assignLoading = ref(false)
const workloadWarning = ref(false)
const dateRange = ref(null)
const dateLoading = ref(false)
const attachments = ref([])
const uploadLoading = ref(false)
const escalations = ref([])
const showEscalationForm = ref(false)
const escalationForm = ref({ severity: 'medium', description: '' })

// 任务关系（precedes 前置 / blocks 阻塞）
const relations = ref({ predecessors: [], successors: [], blocking: [], blocked: [] })
const relationGroups = [
  { key: 'predecessors', label: '前置任务' },
  { key: 'blocking', label: '阻塞中' },
  { key: 'successors', label: '后续任务' },
  { key: 'blocked', label: '正在阻塞' },
]
const relationTotal = computed(() => Object.values(relations.value).reduce((s, arr) => s + arr.length, 0))
const canManageRelation = computed(() => {
  if (!props.task) return false
  return ['pm', 'admin'].includes(auth.user?.role) || props.task.assignee_id === auth.user?.id
})
const relationTypes = [
  { value: 'precedes', label: '前置任务' },
  { value: 'blocks', label: '阻塞我的任务' },
]
const newRelation = ref({ relation_type: 'precedes', related_task_id: null })
const relationOptions = ref([])
const relationSearching = ref(false)

async function loadRelations(taskId) {
  const res = await getTaskRelations(taskId)
  relations.value = res.data
}

async function searchRelationTasks(query) {
  if (!query) { relationOptions.value = []; return }
  relationSearching.value = true
  try {
    const res = await listTasks({ keyword: query, page_size: 20 })
    relationOptions.value = res.data.items
      .filter(t => t.id !== props.task?.id)
      .map(t => ({ id: t.id, label: `${t.task_no} ${t.title}（${t.project_name}）` }))
  } finally {
    relationSearching.value = false
  }
}

async function handleAddRelation() {
  if (!newRelation.value.related_task_id) {
    ElMessage.warning('请先搜索并选择任务')
    return
  }
  try {
    await addTaskRelation(props.task.id, {
      relation_type: newRelation.value.relation_type,
      related_task_id: newRelation.value.related_task_id,
    })
    ElMessage.success('关系已添加')
    newRelation.value.related_task_id = null
    relationOptions.value = []
    await loadRelations(props.task.id)
  } catch {
    // 错误提示由全局拦截器统一处理
  }
}

async function handleDeleteRelation(relationId) {
  try {
    await deleteTaskRelation(relationId)
    ElMessage.success('关系已删除')
    await loadRelations(props.task.id)
  } catch {
    // 错误提示由全局拦截器统一处理
  }
}

onMounted(async () => {
  const res = await listUsers()
  users.value = res.data
})

watch(() => props.task, async (val) => {
  if (val) {
    assigneeId.value = val.assignee_id
    dateRange.value = (val.planned_start && val.planned_end) ? [val.planned_start, val.planned_end] : null
    autoSchedule.value = val.auto_schedule !== false
    progressValue.value = val.progress || 0
    const [cRes, tRes, aRes, eRes] = await Promise.all([getComments(val.id), getTransitions(val.id), listAttachments(val.id), listEscalations(val.id)])
    comments.value = cRes.data
    transitions.value = tRes.data
    attachments.value = aRes.data
    escalations.value = eRes.data
    loadRelations(val.id)
  }
})

async function handleStart() {
  loading.value = true
  try {
    await startTask(props.task.id)
    ElMessage.success('任务已开始')
    emit('refresh')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  loading.value = true
  try {
    await submitTask(props.task.id)
    ElMessage.success('已提交审核')
    emit('refresh')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function handleApprove() {
  loading.value = true
  try {
    await approveTask(props.task.id)
    ElMessage.success('审核通过')
    emit('refresh')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function handleReject() {
  try {
    const { value } = await ElMessageBox.prompt('请输入退回原因', '退回任务', {
      confirmButtonText: '确认退回',
      cancelButtonText: '取消',
      inputValidator: (v) => !!v || '请输入退回原因',
    })
    loading.value = true
    await rejectTask(props.task.id, value)
    ElMessage.success('已退回')
    emit('refresh')
  } catch (e) {
    // 取消无需提示，请求错误由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function handleDateChange(val) {
  if (!val) return
  dateLoading.value = true
  try {
    const res = await updateTask(props.task.id, { planned_start: val[0], planned_end: val[1] })
    const n = res.data?.rescheduled || 0
    ElMessage.success(n > 0 ? `排期已更新，已联动顺延 ${n} 个后续任务` : '排期已更新')
    emit('refresh')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    dateLoading.value = false
  }
}

// 自动排期联动开关（前置任务改期时自动顺延本任务）
const autoSchedule = ref(true)
async function handleAutoScheduleChange(val) {
  try {
    await updateTask(props.task.id, { auto_schedule: val })
    ElMessage.success(val ? '已开启自动排期联动' : '已锁定为手动排期')
    emit('refresh')
  } catch (e) {
    autoSchedule.value = !val
  }
}

// 任务进度（active/review 可拖动报量，approve 自动 100）
const progressValue = ref(0)
const canEditProgress = computed(() => {
  if (!props.task) return false
  return canManageRelation.value && ['active', 'review'].includes(props.task.status)
})
async function handleProgressChange(val) {
  try {
    await updateTask(props.task.id, { progress: val })
    ElMessage.success('进度已更新')
  } catch (e) {
    progressValue.value = props.task.progress || 0
  }
}

watch(assigneeId, async (id) => {
  workloadWarning.value = false
  if (!id) return
  try {
    const res = await http.get(`/users/${id}/workload`)
    workloadWarning.value = res.data.warning
  } catch {}
})

async function handleAssign() {
  if (!assigneeId.value) return
  assignLoading.value = true
  try {
    await assignTask(props.task.id, { assignee_id: assigneeId.value })
    ElMessage.success('已指派')
    emit('refresh')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    assignLoading.value = false
  }
}

async function handleComment() {
  if (!newComment.value.trim()) return
  await addComment(props.task.id, newComment.value)
  newComment.value = ''
  const res = await getComments(props.task.id)
  comments.value = res.data
}

async function handleUpload(file) {
  if (!file) return
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过20MB')
    return
  }
  uploadLoading.value = true
  try {
    await uploadAttachment(props.task.id, file)
    ElMessage.success('上传成功')
    const res = await listAttachments(props.task.id)
    attachments.value = res.data
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    uploadLoading.value = false
  }
}

async function handleDeleteAttachment(att) {
  try {
    await ElMessageBox.confirm(`确定删除文件 "${att.original_name}"?`, '确认删除', { type: 'warning' })
    await deleteAttachment(props.task.id, att.id)
    attachments.value = attachments.value.filter(a => a.id !== att.id)
    ElMessage.success('已删除')
  } catch (e) {
    // 取消无需提示，请求错误由全局拦截器统一处理
  }
}

async function handleDownload(att) {
  try {
    const res = await http.get(`/tasks/${props.task.id}/attachments/${att.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = att.original_name
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    // 错误提示由全局拦截器统一处理
  }
}

const previewUrls = ref({})

function isImage(att) {
  return !!att.content_type?.startsWith('image/')
}

async function loadPreview(att) {
  if (previewUrls.value[att.id]) return
  try {
    const res = await http.get(`/tasks/${props.task.id}/attachments/${att.id}/download`, { responseType: 'blob' })
    previewUrls.value = { ...previewUrls.value, [att.id]: URL.createObjectURL(res.data) }
  } catch {}
}

onUnmounted(() => {
  Object.values(previewUrls.value).forEach(url => URL.revokeObjectURL(url))
})

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function handleCreateEscalation() {
  if (!escalationForm.value.description.trim()) {
    ElMessage.error('请输入问题描述')
    return
  }
  try {
    await createEscalation(props.task.id, escalationForm.value)
    ElMessage.success('问题已升级')
    showEscalationForm.value = false
    escalationForm.value = { severity: 'medium', description: '' }
    const res = await listEscalations(props.task.id)
    escalations.value = res.data
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  }
}

async function handleResolveEscalation(esc) {
  try {
    const { value } = await ElMessageBox.prompt('请输入解决方案', '解决问题', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputValidator: (v) => !!v || '请输入解决方案',
    })
    await resolveEscalation(props.task.id, esc.id, { resolution: value })
    ElMessage.success('已标记为解决')
    const res = await listEscalations(props.task.id)
    escalations.value = res.data
  } catch (e) {
    // 取消无需提示，请求错误由全局拦截器统一处理
  }
}

const cameraInput = ref(null)
function triggerCamera() {
  cameraInput.value?.click()
}
async function handleCameraChange(e) {
  const file = e.target.files?.[0]
  if (file) await handleUpload(file)
  e.target.value = ''
}

function close() {
  emit('update:visible', false)
}
</script>

<template>
  <el-drawer :model-value="visible" @update:model-value="close" :size="isMobile ? '100%' : '550px'" :title="task?.title">
    <template v-if="task">
      <div v-if="showProjectLink || peerIds.length > 1" style="margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between">
        <el-button v-if="showProjectLink" link type="primary" size="small" @click="emit('view-project', task.project_id)">
          查看所属项目 →
        </el-button>
        <span v-else></span>
        <div v-if="peerIds.length > 1" class="drawer-nav">
          <el-button link size="small" :disabled="!hasPrev" @click="goPrev">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <span class="drawer-nav__count">{{ navIndex + 1 }} / {{ peerIds.length }}</span>
          <el-button link size="small" :disabled="!hasNext" @click="goNext">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
      <div style="margin-bottom: 16px">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="编号">{{ task.task_no }}</el-descriptions-item>
          <el-descriptions-item label="阶段">{{ PHASE_MAP[task.phase] }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="STATUS_MAP[task.status]?.type" size="small">{{ STATUS_MAP[task.status]?.label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="排期">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              size="small"
              range-separator="~"
              start-placeholder="开始"
              end-placeholder="结束"
              value-format="YYYY-MM-DD"
              style="width: 220px"
              @change="handleDateChange"
            />
          </el-descriptions-item>
          <el-descriptions-item label="进度">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-slider v-if="canEditProgress" v-model="progressValue" size="small" style="width: 140px"
                         :format-tooltip="(v) => v + '%'" @change="handleProgressChange" />
              <el-progress v-else :percentage="task.progress || 0" :stroke-width="8" style="width: 150px" />
              <span style="font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums">{{ progressValue }}%</span>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="自动排期">
            <el-switch v-if="canManageRelation" v-model="autoSchedule" size="small" @change="handleAutoScheduleChange" />
            <span v-else style="font-size: 13px">{{ task.auto_schedule === false ? '手动' : '自动' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="负责人" :span="2">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-select
                v-model="assigneeId"
                placeholder="选择负责人"
                size="small"
                style="width: 180px"
                filterable
              >
                <el-option
                  v-for="u in users"
                  :key="u.id"
                  :label="`${u.display_name} (${ROLE_MAP[u.role] || u.role})`"
                  :value="u.id"
                />
              </el-select>
              <el-button
                size="small"
                type="primary"
                :loading="assignLoading"
                :disabled="!assigneeId || assigneeId === task.assignee_id"
                @click="handleAssign"
              >指派</el-button>
            </div>
            <div v-if="workloadWarning" style="color: var(--el-color-warning); font-size: 12px; margin-top: 4px">
              ⚠ 该成员当前进行中任务 ≥ 3，工作量较高
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- Actions -->
      <div style="margin-bottom: 20px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-button v-if="task.status === 'pending' && canStart" type="primary" @click="handleStart" :loading="loading">
          开始任务
        </el-button>
        <el-button v-if="task.status === 'active'" type="primary" @click="handleSubmit" :loading="loading">
          提交审核
        </el-button>
        <el-button v-if="task.status === 'review'" type="success" @click="handleApprove" :loading="loading">
          审核通过
        </el-button>
        <el-button v-if="task.status === 'review'" type="warning" @click="handleReject" :loading="loading">
          退回
        </el-button>
      </div>

      <!-- Attachments -->
      <el-divider content-position="left">前置与阻塞 ({{ relationTotal }})</el-divider>
    <div style="margin-bottom: 12px">
      <template v-for="g in relationGroups" :key="g.key">
        <div v-if="relations[g.key].length">
          <div class="relation-group__label">{{ g.label }}</div>
          <div v-for="item in relations[g.key]" :key="item.relation_id" class="relation-item">
            <el-tag :type="STATUS_MAP[item.status]?.type" size="small">{{ STATUS_MAP[item.status]?.label }}</el-tag>
            <span class="relation-item__no">{{ item.task_no }}</span>
            <span class="relation-item__title">{{ item.title }}</span>
            <span class="relation-item__project">{{ item.project_name }}</span>
            <el-button v-if="canManageRelation" link type="danger" size="small" @click="handleDeleteRelation(item.relation_id)">删除</el-button>
          </div>
        </div>
      </template>
      <div v-if="relationTotal === 0" style="color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 8px">暂无关联任务</div>
      <div v-if="canManageRelation" style="display: flex; gap: 8px; margin-top: 8px">
        <el-select v-model="newRelation.relation_type" size="small" style="width: 130px">
          <el-option v-for="t in relationTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="newRelation.related_task_id" size="small" style="width: 250px" filterable remote clearable
                   :remote-method="searchRelationTasks" :loading="relationSearching"
                   placeholder="搜索任务编号/标题后添加">
          <el-option v-for="o in relationOptions" :key="o.id" :label="o.label" :value="o.id" />
        </el-select>
        <el-button size="small" type="primary" @click="handleAddRelation">添加</el-button>
      </div>
    </div>

    <el-divider content-position="left">附件 ({{ attachments.length }})</el-divider>
      <div style="margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap">
        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          :on-change="(file) => handleUpload(file.raw)"
          style="display: inline-block"
        >
          <el-button size="small" type="primary" :loading="uploadLoading">上传文件</el-button>
        </el-upload>
        <!-- 拍照上传（移动端） -->
        <el-button v-if="isMobile" size="small" type="success" :loading="uploadLoading" @click="triggerCamera">
          📷 拍照上传
        </el-button>
        <input
          ref="cameraInput"
          type="file"
          accept="image/*"
          capture="environment"
          style="display: none"
          @change="handleCameraChange"
        />
      </div>
      <div v-if="attachments.length === 0" style="color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 12px">暂无附件</div>
      <div v-for="att in attachments" :key="att.id" class="attachment-item">
        <el-tooltip v-if="isImage(att)" placement="right" effect="light" :hide-after="0">
          <template #content>
            <img
              v-if="previewUrls[att.id]"
              :src="previewUrls[att.id]"
              style="max-width: 260px; max-height: 260px; display: block; border-radius: 4px"
            />
            <span v-else style="color: var(--el-text-color-secondary); font-size: 12px">加载中...</span>
          </template>
          <a href="#" class="attachment-name" @click.prevent="handleDownload(att)" @mouseenter="loadPreview(att)">
            {{ att.original_name }}
          </a>
        </el-tooltip>
        <a v-else href="#" class="attachment-name" @click.prevent="handleDownload(att)">{{ att.original_name }}</a>
        <span class="attachment-size">{{ formatSize(att.size) }}</span>
        <span class="attachment-time">{{ formatDateTime(att.created_at) }}</span>
        <el-button size="small" text type="danger" @click="handleDeleteAttachment(att)">删除</el-button>
      </div>

      <!-- Escalations -->
      <el-divider content-position="left">问题升级 ({{ escalations.length }})</el-divider>
      <div style="margin-bottom: 12px">
        <el-button size="small" type="danger" plain @click="showEscalationForm = !showEscalationForm">
          {{ showEscalationForm ? '取消' : '发起升级' }}
        </el-button>
      </div>
      <div v-if="showEscalationForm" style="margin-bottom: 12px; padding: 12px; background: #fef0f0; border-radius: 4px">
        <el-select v-model="escalationForm.severity" size="small" style="width: 120px; margin-bottom: 8px">
          <el-option label="低" value="low" />
          <el-option label="中" value="medium" />
          <el-option label="高" value="high" />
          <el-option label="紧急" value="critical" />
        </el-select>
        <el-input v-model="escalationForm.description" type="textarea" :rows="2" placeholder="描述遇到的问题..." style="margin-bottom: 8px" />
        <el-button size="small" type="danger" @click="handleCreateEscalation">提交</el-button>
      </div>
      <div v-for="esc in escalations" :key="esc.id" class="escalation-item">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px">
          <el-tag :type="esc.severity === 'critical' ? 'danger' : esc.severity === 'high' ? 'warning' : 'info'" size="small">
            {{ { low: '低', medium: '中', high: '高', critical: '紧急' }[esc.severity] }}
          </el-tag>
          <el-tag :type="esc.status === 'resolved' ? 'success' : 'danger'" size="small">
            {{ esc.status === 'resolved' ? '已解决' : '待处理' }}
          </el-tag>
          <span style="font-size: 12px; color: var(--el-text-color-secondary)">{{ formatDateTime(esc.created_at) }}</span>
        </div>
        <div style="font-size: 13px; margin-bottom: 4px">{{ esc.description }}</div>
        <div v-if="esc.resolution" style="font-size: 13px; color: var(--el-color-success)">解决: {{ esc.resolution }}</div>
        <el-button v-if="esc.status !== 'resolved'" size="small" text type="success" @click="handleResolveEscalation(esc)">
          标记解决
        </el-button>
      </div>

      <!-- Comments -->
      <el-divider content-position="left">评论 ({{ comments.length }})</el-divider>
      <div style="max-height: 200px; overflow-y: auto; margin-bottom: 12px">
        <div v-for="c in comments" :key="c.id" style="margin-bottom: 12px; padding: 8px; background: #f9f9f9; border-radius: 4px">
          <div style="font-size: 12px; color: #999; margin-bottom: 4px">
            {{ c.user_name || `用户${c.user_id}` }} · {{ formatDateTime(c.created_at) }}
          </div>
          <div style="font-size: 14px">{{ c.content }}</div>
        </div>
        <EmptyState v-if="comments.length === 0" text="暂无评论" :size="36" />
      </div>
      <div style="display: flex; gap: 8px">
        <el-input v-model="newComment" placeholder="输入评论，支持 @用户名 提及..." @keyup.enter="handleComment" />
        <el-button type="primary" @click="handleComment">发送</el-button>
      </div>

      <!-- Transitions -->
      <el-divider content-position="left">流转记录</el-divider>
      <el-timeline>
        <el-timeline-item v-for="t in transitions" :key="t.id" :timestamp="formatDateTime(t.created_at)">
          <span style="color: var(--el-color-primary)">{{ t.operator_name }}</span>:
          {{ t.from_status || '(创建)' }} → {{ t.to_status }}
          <span v-if="t.remark" style="color: var(--el-color-warning); margin-left: 8px">{{ t.remark }}</span>
        </el-timeline-item>
      </el-timeline>
    </template>
  </el-drawer>
</template>

<style scoped>
.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}
.attachment-name {
  flex: 1;
  color: var(--el-color-primary);
  text-decoration: none;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-name:hover {
  text-decoration: underline;
}
.attachment-size {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.attachment-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}
.escalation-item {
  padding: 10px;
  border: 1px solid #fde2e2;
  border-radius: 4px;
  margin-bottom: 8px;
  background: #fef0f0;
}
.drawer-nav {
  display: flex;
  align-items: center;
  gap: 2px;
}
.drawer-nav__count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
  min-width: 44px;
  text-align: center;
}
.relation-group__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin: 6px 0 4px;
}
.relation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}
.relation-item__no {
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.relation-item__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
}
.relation-item__project {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  flex-shrink: 0;
}
</style>
