<script setup lang="ts">
defineProps<{
  callbackUrl: string;
  viewerUrl: string;
  copied: boolean;
  copying: boolean;
}>();

defineEmits<{
  copy: [];
}>();
</script>

<template>
  <section class="card callback-card" aria-label="Callback URL panel" data-testid="callback-panel">
    <div class="callback-card__text">
      <p class="section-label">Callback URL</p>
      <button class="callback-card__url" type="button" aria-label="Copy callback URL" @click="$emit('copy')">
        {{ callbackUrl || 'Waiting for an active inbox...' }}
      </button>
      <p class="callback-card__meta">Viewer link: {{ viewerUrl || 'Pending' }}</p>
    </div>
    <button
      class="callback-card__copy"
      type="button"
      aria-label="Copy URL"
      :disabled="!callbackUrl || copying"
      @click="$emit('copy')"
    >
      {{ copied ? 'Copied' : 'Copy URL' }}
    </button>
  </section>
</template>