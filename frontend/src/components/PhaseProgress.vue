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
  border: 2px solid #dcdfe6;
  color: #909399;
  background: #fff;
  z-index: 1;
}
.phase-done {
  background: #67c23a;
  border-color: #67c23a;
  color: #fff;
}
.phase-active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}
.phase-name {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
  text-align: center;
}
.phase-name.is-active {
  color: #409eff;
  font-weight: bold;
}
.phase-line {
  position: absolute;
  top: 16px;
  left: calc(50% + 16px);
  width: calc(100% - 32px);
  height: 2px;
  background: #dcdfe6;
}
.line-done {
  background: #67c23a;
}
</style>
