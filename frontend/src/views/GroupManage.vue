<script setup>
import PageHeader from '../components/PageHeader.vue'
import { ref, onMounted } from 'vue'
import { listGroups, createGroup, updateGroup, deleteGroup, listGroupMembers, addGroupMember, removeGroupMember } from '../api/groups'
import { listUsers } from '../api/tasks'
import { ROLE_MAP } from '../utils/constants'
import { ElMessage, ElMessageBox } from 'element-plus'

const groups = ref([])
const loading = ref(false)
const showDialog = ref(false)
const dialogTitle = ref('新建用户组')
const form = ref({ name: '', description: '' })
const editingId = ref(null)
const submitLoading = ref(false)

const expandedGroupId = ref(null)
const membersByGroup = ref({})
const allUsers = ref([])
const addMemberUserId = ref(null)
const addMemberLoading = ref(false)

async function fetchGroups() {
  loading.value = true
  try {
    const res = await listGroups()
    groups.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const [, uRes] = await Promise.all([fetchGroups(), listUsers()])
  allUsers.value = uRes.data
})

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新建用户组'
  form.value = { name: '', description: '' }
  showDialog.value = true
}

function openEdit(group) {
  editingId.value = group.id
  dialogTitle.value = '编辑用户组'
  form.value = { name: group.name, description: group.description }
  showDialog.value = true
}

async function handleSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.error('请填写用户组名称')
    return
  }
  submitLoading.value = true
  try {
    if (editingId.value) {
      await updateGroup(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createGroup(form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    await fetchGroups()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(group) {
  try {
    await ElMessageBox.confirm(`确定删除用户组「${group.name}」？`, '确认删除', { type: 'warning' })
    await deleteGroup(group.id)
    ElMessage.success('已删除')
    if (expandedGroupId.value === group.id) expandedGroupId.value = null
    await fetchGroups()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function toggleExpand(group) {
  if (expandedGroupId.value === group.id) {
    expandedGroupId.value = null
    return
  }
  expandedGroupId.value = group.id
  addMemberUserId.value = null
  const res = await listGroupMembers(group.id)
  membersByGroup.value = { ...membersByGroup.value, [group.id]: res.data }
}

async function handleAddMember(groupId) {
  if (!addMemberUserId.value) return
  addMemberLoading.value = true
  try {
    await addGroupMember(groupId, addMemberUserId.value)
    ElMessage.success('已添加')
    addMemberUserId.value = null
    const res = await listGroupMembers(groupId)
    membersByGroup.value = { ...membersByGroup.value, [groupId]: res.data }
    const g = groups.value.find(g => g.id === groupId)
    if (g) g.member_count++
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加失败')
  } finally {
    addMemberLoading.value = false
  }
}

async function handleRemoveMember(groupId, userId, displayName) {
  try {
    await ElMessageBox.confirm(`确定将「${displayName}」从组中移除？`, '确认', { type: 'warning' })
    await removeGroupMember(groupId, userId)
    ElMessage.success('已移除')
    membersByGroup.value[groupId] = membersByGroup.value[groupId].filter(m => m.id !== userId)
    const g = groups.value.find(g => g.id === groupId)
    if (g) g.member_count--
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '移除失败')
  }
}

function availableUsers(groupId) {
  const members = membersByGroup.value[groupId] || []
  const memberIds = new Set(members.map(m => m.id))
  return allUsers.value.filter(u => !memberIds.has(u.id))
}
</script>

<template>
  <div>
    <PageHeader title="用户组管理">
      <el-button type="primary" @click="openCreate">新建用户组</el-button>
    </PageHeader>

    <el-table :data="groups" v-loading="loading" border stripe row-key="id">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="用户组名称" min-width="150" />
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">
          <span style="color: #909399">{{ row.description || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="member_count" label="成员数" width="80" align="center" />
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="toggleExpand(row)">
            {{ expandedGroupId === row.id ? '收起' : '管理成员' }}
          </el-button>
          <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Member panel -->
    <div v-if="expandedGroupId" class="member-panel">
      <div style="font-weight: bold; margin-bottom: 12px; font-size: 14px">
        「{{ groups.find(g => g.id === expandedGroupId)?.name }}」成员管理
      </div>

      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <el-select
          v-model="addMemberUserId"
          placeholder="选择用户添加到组"
          filterable
          style="width: 240px"
        >
          <el-option
            v-for="u in availableUsers(expandedGroupId)"
            :key="u.id"
            :label="`${u.display_name} (${ROLE_MAP[u.role] || u.role})`"
            :value="u.id"
          />
        </el-select>
        <el-button type="primary" size="small" :loading="addMemberLoading" :disabled="!addMemberUserId" @click="handleAddMember(expandedGroupId)">
          添加
        </el-button>
      </div>

      <el-empty
        v-if="!membersByGroup[expandedGroupId]?.length"
        description="暂无成员"
        :image-size="50"
      />
      <el-table v-else :data="membersByGroup[expandedGroupId]" size="small" border>
        <el-table-column prop="display_name" label="显示名" width="140" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">{{ ROLE_MAP[row.role] || row.role }}</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="handleRemoveMember(expandedGroupId, row.id, row.display_name)">
              移除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showDialog" :title="dialogTitle" width="440px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="用户组名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选：描述该用户组的用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.member-panel {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fafafa;
}
</style>
