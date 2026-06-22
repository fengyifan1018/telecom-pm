<script setup>
import { DocumentRemove } from '@element-plus/icons-vue'

defineProps({
  text: { type: String, default: '暂无数据' },
  icon: { type: [Object, Function], default: () => DocumentRemove },
  size: { type: Number, default: 48 },
})
</script>

<template>
  <div class="empty-state">
    <el-icon class="empty-state__icon" :style="{ fontSize: size + 'px' }">
      <component :is="icon" />
    </el-icon>
    <div class="empty-state__text">{{ text }}</div>
    <div v-if="$slots.default" class="empty-state__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--sp-8) var(--sp-4);
  color: var(--text-secondary);
}
.empty-state__icon {
  color: var(--el-text-color-placeholder);
  margin-bottom: var(--sp-3);
}
.empty-state__text {
  font-size: 14px;
  color: var(--text-secondary);
}
.empty-state__action {
  margin-top: var(--sp-4);
}
</style>
