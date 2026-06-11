<script setup>
import PageHeader from '../components/PageHeader.vue'
import { ref, onMounted } from 'vue'
import { getPermissions, updatePermission, resetPermissions } from '../api/permissions'
import { ElMessage, ElMessageBox } from 'element-plus'

const permissions = ref([])  // [{key, label, roles: string[]}]
const roles = ref([])        // ordered list of role keys
const roleLabels = ref({})   // role → Chinese label
const loading = ref(false)
const saving = ref('')       // perm_key being saved

async function fetchData() {
  loading.value = true
  try {
    const res = await getPermissions()
    permissions.value = res.data.permissions
    roles.value = res.data.roles
    roleLabels.value = res.data.role_labels
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

function hasRole(perm, role) {
  return perm.roles.includes(role)
}

async function toggleRole(perm, role) {
  const newRoles = perm.roles.includes(role)
    ? perm.roles.filter(r => r !== role)
    : [...perm.roles, role]
  saving.value = perm.key
  try {
    await updatePermission(perm.key, newRoles)
    perm.roles = newRoles
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = ''
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('确定重置所有权限为系统默认值？', '重置权限', { type: 'warning' })
    await resetPermissions()
    ElMessage.success('已重置为默认权限')
    await fetchData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}
</script>

<template>
  <div>
    <PageHeader title="权限管理">
      <el-button type="warning" plain @click="handleReset">重置为默认</el-button>
    </PageHeader>

    <el-card v-loading="loading">
      <div style="font-size: 13px; color: #909399; margin-bottom: 16px">
        勾选表示该角色拥有此操作权限。修改后立即生效。
      </div>

      <el-table :data="permissions" border size="small">
        <el-table-column prop="label" label="权限项" width="160" fixed />
        <el-table-column
          v-for="role in roles"
          :key="role"
          :label="roleLabels[role] || role"
          align="center"
          width="90"
        >
          <template #default="{ row }">
            <el-checkbox
              :model-value="hasRole(row, role)"
              :loading="saving === row.key"
              @change="toggleRole(row, role)"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
