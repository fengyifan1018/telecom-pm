<script setup>
defineProps({
  height: { type: Number, default: 30 },
  text: { type: String, default: '' },
  textColor: { type: String, default: 'var(--text-title)' },
})
</script>

<template>
  <div class="brand-logo">
    <img class="brand-logo__img" src="/logo.svg" alt="睿鸿" :style="{ height: height + 'px' }" />
    <span
      v-if="text"
      class="brand-logo__text"
      :style="{ color: textColor, fontSize: Math.round(height * 0.5) + 'px' }"
    >{{ text }}</span>
  </div>
</template>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.brand-logo__img {
  display: block;
  width: auto;
}
.brand-logo__text {
  font-weight: 600;
  letter-spacing: 0.5px;
  white-space: nowrap;
}
</style>
