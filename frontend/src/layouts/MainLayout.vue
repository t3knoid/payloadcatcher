<script setup lang="ts">
defineProps<{
  statusLabel: string;
}>();
</script>

<template>
  <div class="shell">
    <header class="shell__header">
      <div class="shell__brand-block">
        <h1 class="shell__brand">
          <span class="shell__wordmark">payloadcat.ch</span>
          <img class="shell__logo" src="/logo.png" alt="PayloadCatcher" />
        </h1>
      </div>
      <span class="shell__status">{{ statusLabel }}</span>
    </header>
    <main class="shell__content">
      <slot />
    </main>
  </div>
</template>