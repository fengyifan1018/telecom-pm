<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { listProjects } from '../api/projects'
import { listTasks } from '../api/tasks'

const router = useRouter()
const keyword = ref('')
const options = ref([])
const loading = ref(false)

async function remoteSearch(query) {
  if (!query || query.length < 2) {
    options.value = []
    return
  }
  loading.value = true
  try {
    const [pRes, tRes] = await Promise.all([
      listProjects({ search: query, page_size: 5 }),
      listTasks({ keyword: query, page_size: 5 }),
    ])
    const opts = []
    pRes.data.items.forEach(p => opts.push({
      key: `p${p.id}`, type: '项目', goto: `/projects/${p.id}`,
      label: `${p.project_no} ${p.name}`,
    }))
    tRes.data.items.forEach(t => opts.push({
      key: `t${t.id}`, type: '任务', goto: `/projects/${t.project_id}`,
      label: `${t.task_no} ${t.title}`,
    }))
    options.value = opts
  } finally {
    loading.value = false
  }
}

function onSelect(opt) {
  if (opt?.goto) router.push(opt.goto)
  keyword.value = ''
  options.value = []
}
</script>

<template>
  <el-select
    v-model="keyword"
    remote
    filterable
    clearable
    :remote-method="remoteSearch"
    :loading="loading"
    placeholder="搜索项目、任务..."
    style="width: 100%"
    @change="onSelect"
  >
    <template #prefix><el-icon><Search /></el-icon></template>
    <el-option v-for="o in options" :key="o.key" :label="o.label" :value="o">
      <span style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
        <span style="overflow: hidden; text-overflow: ellipsis">{{ o.label }}</span>
        <el-tag size="small" :type="o.type === '项目' ? 'primary' : 'info'">{{ o.type }}</el-tag>
      </span>
    </el-option>
  </el-select>
</template>
