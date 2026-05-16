<script setup lang="ts">
import type { InboxEventSummary } from '@/types/api';

defineProps<{
  event: InboxEventSummary | null;
}>();
</script>

<template>
  <section class="card panel panel--payload" aria-label="Payload details" data-testid="payload-panel">
    <div class="panel__header panel__header--payload">
      <div>
        <p class="section-label">Payload (YAML)</p>
        <p class="panel__caption">Select a request to inspect its captured preview.</p>
      </div>
    </div>

    <div v-if="!event" class="panel__state">Select a captured request to inspect its payload preview.</div>
    <div v-else class="payload-panel">
      <dl class="payload-panel__meta">
        <div>
          <dt>Request ID</dt>
          <dd>{{ event.request_id }}</dd>
        </div>
        <div>
          <dt>Received</dt>
          <dd>{{ event.received_at }}</dd>
        </div>
        <div>
          <dt>Method</dt>
          <dd>{{ event.method }}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{{ event.source_ip_masked }}</dd>
        </div>
      </dl>

      <pre class="payload-panel__code"><code>{{ event.payload_yaml }}</code></pre>
    </div>
  </section>
</template>