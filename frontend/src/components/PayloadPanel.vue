<script setup lang="ts">
import DOMPurify from 'dompurify';
import { computed, ref, watch } from 'vue';
import Prism from 'prismjs';
import 'prismjs/components/prism-yaml';

import type { InboxEventDetail } from '@/types/api';

const props = defineProps<{
  detail: InboxEventDetail | null;
  loading: boolean;
  error: string | null;
  copying: boolean;
  copied: boolean;
}>();

defineEmits<{
  copy: [];
}>();

const LARGE_PAYLOAD_HIGHLIGHT_LIMIT_BYTES = 256 * 1024;
const LARGE_PAYLOAD_INITIAL_CHARS = 4096;

const escapeHtml = (value: string) => {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
};

const headerEntries = computed(() => {
  return props.detail ? Object.entries(props.detail.headers) : [];
});

const shouldHighlightPayload = computed(() => {
  return Boolean(props.detail) && props.detail.payload_size_bytes <= LARGE_PAYLOAD_HIGHLIGHT_LIMIT_BYTES;
});

const visiblePayloadChars = ref(LARGE_PAYLOAD_INITIAL_CHARS);

watch(
  () => props.detail?.request_id,
  () => {
    visiblePayloadChars.value = LARGE_PAYLOAD_INITIAL_CHARS;
  },
  { immediate: true },
);

const displayedPlainPayload = computed(() => {
  if (!props.detail) {
    return '';
  }

  return props.detail.payload_yaml.slice(0, visiblePayloadChars.value);
});

const hasHiddenPayload = computed(() => {
  if (!props.detail || shouldHighlightPayload.value) {
    return false;
  }

  return visiblePayloadChars.value < props.detail.payload_yaml.length;
});

const showMorePayload = () => {
  if (!props.detail) {
    return;
  }

  visiblePayloadChars.value = Math.min(
    visiblePayloadChars.value + LARGE_PAYLOAD_INITIAL_CHARS,
    props.detail.payload_yaml.length,
  );
};

const highlightedPayload = computed(() => {
  if (!props.detail || !shouldHighlightPayload.value) {
    return '';
  }

  try {
    return DOMPurify.sanitize(Prism.highlight(props.detail.payload_yaml, Prism.languages.yaml, 'yaml'));
  } catch {
    return escapeHtml(props.detail.payload_yaml);
  }
});
</script>

<template>
  <section class="card panel panel--payload" aria-label="Payload details" data-testid="payload-panel" :aria-busy="loading">
    <div class="panel__header panel__header--payload panel__header--split">
      <div>
        <p class="section-label">Payload (YAML)</p>
        <p class="panel__caption">
          {{ detail ? 'Inspect the full stored payload and captured request metadata.' : 'Select a request to inspect its full captured payload.' }}
        </p>
      </div>
      <button
        v-if="detail"
        type="button"
        class="payload-panel__copy"
        :disabled="copying"
        data-testid="payload-copy-button"
        @click="$emit('copy')"
      >
        {{ copied ? 'Copied' : copying ? 'Copying...' : 'Copy payload' }}
      </button>
    </div>

    <div v-if="loading" class="panel__state">Loading selected payload...</div>
    <div v-else-if="error" class="panel__state">{{ error }}</div>
    <div v-else-if="!detail" class="panel__state">Select a captured request to inspect its full payload.</div>
    <div v-else class="payload-panel">
      <dl class="payload-panel__meta">
        <div>
          <dt>Request ID</dt>
          <dd>{{ detail.request_id }}</dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>{{ detail.received_at }}</dd>
        </div>
        <div>
          <dt>Method</dt>
          <dd>{{ detail.method }}</dd>
        </div>
        <div>
          <dt>Content Type</dt>
          <dd>{{ detail.content_type ?? 'Unknown' }}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{{ detail.source_ip_masked }}</dd>
        </div>
        <div>
          <dt>Payload Size</dt>
          <dd>{{ detail.payload_size_bytes }} B</dd>
        </div>
      </dl>

      <section class="payload-panel__section">
        <p class="section-label">Headers</p>
        <div v-if="headerEntries.length === 0" class="panel__state">No captured headers are available for this event.</div>
        <dl v-else class="payload-panel__headers" data-testid="payload-headers">
          <div v-for="[name, value] in headerEntries" :key="name">
            <dt>{{ name }}</dt>
            <dd>{{ value }}</dd>
          </div>
        </dl>
      </section>

      <section class="payload-panel__section">
        <p v-if="!shouldHighlightPayload" class="panel__caption">
          Syntax highlighting is disabled for large payloads to keep rendering responsive.
        </p>
        <pre class="payload-panel__code" :class="{ 'payload-panel__code--plain': !shouldHighlightPayload }">
          <!-- eslint-disable-next-line vue/no-v-html -->
          <code v-if="shouldHighlightPayload" class="language-yaml" v-html="highlightedPayload"></code>
          <code v-else>{{ displayedPlainPayload }}</code>
        </pre>
        <button
          v-if="hasHiddenPayload"
          type="button"
          class="panel__more panel__more--secondary"
          data-testid="payload-show-more-button"
          @click="showMorePayload"
        >
          Show more
        </button>
      </section>
    </div>
  </section>
</template>