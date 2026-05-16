<script setup lang="ts">
import type { InboxEventSummary } from '@/types/api';

const props = defineProps<{
  events: InboxEventSummary[];
  loading: boolean;
  loadingMore: boolean;
  selectedRequestId: string | null;
  searchValue: string;
  currentPage: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
}>();

const emit = defineEmits<{
  search: [value: string];
  select: [requestId: string];
  next: [];
  previous: [];
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

const truncateRequestId = (value: string) => {
  if (value.length <= 22) {
    return value;
  }

  return `${value.slice(0, 12)}...${value.slice(-6)}`;
};

const buildPreview = (value: string) => {
  const collapsed = value.replace(/\s+/g, ' ').trim();

  if (collapsed.length <= 100) {
    return collapsed;
  }

  return `${collapsed.slice(0, 97)}...`;
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
            <span>{{ truncateRequestId(event.request_id) }}</span>
            <span>{{ event.source_ip_masked }}</span>
          </div>
          <p class="event-list__preview">{{ buildPreview(event.payload_yaml) }}</p>
        </button>
      </li>
    </ul>

    <div class="panel__pagination" aria-label="Pagination controls">
      <button
        class="panel__more panel__more--secondary"
        type="button"
        aria-label="Previous page"
        :disabled="!hasPreviousPage || loadingMore"
        @click="emit('previous')"
      >
        Previous
      </button>
      <span class="panel__page-indicator">Page {{ currentPage }}</span>
      <button
        class="panel__more"
        type="button"
        aria-label="Next page"
        :disabled="!hasNextPage || loadingMore"
        @click="emit('next')"
      >
        {{ loadingMore ? 'Loading…' : 'Next' }}
      </button>
    </div>
  </section>
</template>