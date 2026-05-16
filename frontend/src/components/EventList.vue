<script setup lang="ts">
import type { InboxEventSummary } from '@/types/api';

const props = defineProps<{
  events: InboxEventSummary[];
  loading: boolean;
  loadingMore: boolean;
  selectedRequestId: string | null;
  searchValue: string;
  hasNextPage: boolean;
}>();

const emit = defineEmits<{
  search: [value: string];
  select: [requestId: string];
  next: [];
}>();

const onInput = (event: Event) => {
  const target = event.target as HTMLInputElement;
  emit('search', target.value);
};

const formatTimestamp = (value: string) => {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
};
</script>

<template>
  <section class="card panel" aria-label="Inbox request list" data-testid="event-list-panel">
    <div class="panel__header">
      <p class="section-label">Search requests</p>
      <input
        class="panel__search"
        type="search"
        aria-label="Search requests"
        :value="searchValue"
        placeholder="Search by id, method, IP, or preview..."
        @input="onInput"
      />
    </div>

    <div v-if="loading && events.length === 0" class="panel__state">Loading inbox events…</div>
    <div v-else-if="events.length === 0" class="panel__state">No captured requests match this view yet.</div>
    <ul v-else class="event-list">
      <li v-for="event in props.events" :key="event.request_id">
        <button
          class="event-list__item"
          :class="{ 'event-list__item--active': event.request_id === selectedRequestId }"
          type="button"
          :aria-label="`Open request ${event.request_id}`"
          :aria-pressed="event.request_id === selectedRequestId"
          :data-testid="`request-${event.request_id}`"
          @click="emit('select', event.request_id)"
        >
          <div class="event-list__row">
            <strong>{{ formatTimestamp(event.received_at) }}</strong>
            <span>{{ event.method }}</span>
          </div>
          <div class="event-list__row event-list__row--muted">
            <span>{{ event.source_ip_masked }}</span>
            <span>{{ event.content_type || 'unknown content type' }}</span>
          </div>
        </button>
      </li>
    </ul>

    <button
      v-if="hasNextPage"
      class="panel__more"
      type="button"
      aria-label="Load more requests"
      :disabled="loadingMore"
      @click="emit('next')"
    >
      {{ loadingMore ? 'Loading…' : 'Load more' }}
    </button>
  </section>
</template>