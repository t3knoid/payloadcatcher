<script setup lang="ts">
defineProps<{
  statusLabel: string;
}>();
</script>

<template>
  <div class="shell">
    <header class="shell__header">
      <div class="shell__brand-block">
        <button class="shell__menu" type="button" aria-label="Open navigation">
          <span></span>
          <span></span>
          <span></span>
        </button>
        <div>
          <h1 class="shell__brand">
            <img class="shell__logo" src="/logo.png" alt="PayloadCatcher" />
            <span class="shell__wordmark">payloadcat.ch</span>
          </h1>
        </div>
      </div>
      <span class="shell__status">{{ statusLabel }}</span>
    </header>
    <main class="shell__content">
      <slot />
    </main>
  </div>
</template>