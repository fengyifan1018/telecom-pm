<script setup>
import { computed } from 'vue'
import { PHASE_MAP, PHASE_ORDER_BY_PRODUCT, PHASE_ORDER } from '../utils/constants'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  productType: { type: String, default: 'dia' },
})

const phaseStatus = computed(() => {
  const order = PHASE_ORDER_BY_PRODUCT[props.productType] || PHASE_ORDER
  return order.map((phase) => {
    const phaseTasks = props.tasks.filter((t) => t.phase === phase)
    if (phaseTasks.length === 0) return { phase, name: PHASE_MAP[phase] || phase, status: 'pending' }
    const allDone = phaseTasks.every((t) => t.status === 'done')
    const anyActive = phaseTasks.some((t) => ['active', 'review'].includes(t.status))
    let status = 'pending'
    if (allDone) status = 'done'
    else if (anyActive) status = 'active'
    return { phase, name: PHASE_MAP[phase] || phase, status }
  })
})
</script>

<template>
  <div class="phase-progress">
    <div v-for="(p, idx) in phaseStatus" :key="p.phase" class="phase-item">
      <div class="phase-icon" :class="'phase-' + p.status">
        <span v-if="p.status === 'done'">✓</span>
        <span v-else-if="p.status === 'active'">{{ idx + 1 }}</span>
        <span v-else>{{ idx + 1 }}</span>
      </div>
      <div class="phase-name" :class="{ 'is-active': p.status === 'active' }">{{ p.name }}</div>
      <div v-if="idx < phaseStatus.length - 1" class="phase-line" :class="{ 'line-done': p.status === 'done' }" />
    </div>
  </div>
</template>

<style scoped>
.phase-progress {
  display: flex;
  align-items: flex-start;
  padding: 16px 0;
}
.phase-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
}
.phase-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  border: 2px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
  background: #fff;
  z-index: 1;
}
.phase-done {
  background: var(--el-color-success);
  border-color: var(--el-color-success);
  color: #fff;
}
.phase-active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
}
.phase-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
  text-align: center;
}
.phase-name.is-active {
  color: var(--el-color-primary);
  font-weight: bold;
}
.phase-line {
  position: absolute;
  top: 16px;
  left: calc(50% + 16px);
  width: calc(100% - 32px);
  height: 2px;
  background: var(--el-border-color);
}
.line-done {
  background: var(--el-color-success);
}
</style>
