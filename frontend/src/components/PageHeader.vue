<script setup>
defineProps({
  title: { type: String, required: true },
})
</script>

<template>
  <div class="page-header">
    <h2 class="page-header__title">{{ title }}</h2>
    <div class="page-header__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.page-header__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2329;
}
.page-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
