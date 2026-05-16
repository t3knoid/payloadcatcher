<script setup lang="ts">
import { watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import CallbackCard from '@/components/CallbackCard.vue';
import EventList from '@/components/EventList.vue';
import PayloadPanel from '@/components/PayloadPanel.vue';
import MainLayout from '@/layouts/MainLayout.vue';
import { useInboxStore } from '@/stores/inbox';

const route = useRoute();
const router = useRouter();
const store = useInboxStore();

let skipNextRouteSync = false;

const queryValue = (value: string | string[] | null | undefined) => {
  if (Array.isArray(value)) {
    return value[0] ?? '';
  }

  return value ?? '';
};

const parseCursorHistory = () => {
  const rawHistory = queryValue(route.query.history as string | string[] | null | undefined);
  const history = rawHistory
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
  const cursor = queryValue(route.query.cursor as string | string[] | null | undefined) || null;

  if (cursor && history.at(-1) !== cursor) {
    history.push(cursor);
  }

  return {
    cursor,
    history,
  };
};

const buildRouteQuery = () => {
  const query: Record<string, string> = {};

  if (store.search) {
    query.q = store.search;
  }

  if (store.currentCursor) {
    query.cursor = store.currentCursor;
  }

  if (store.cursorHistory.length > 0) {
    query.history = store.cursorHistory.join(',');
  }

  return query;
};

const syncRouteWithStore = async (mode: 'push' | 'replace' = 'replace') => {
  skipNextRouteSync = true;
  await router[mode]({
    name: 'inbox',
    params: {
      clsid: String(route.params.clsid ?? ''),
    },
    query: buildRouteQuery(),
  });
};

const loadFromRoute = async () => {
  const clsid = String(route.params.clsid ?? '');
  if (!clsid) {
    return;
  }

  const q = queryValue(route.query.q as string | string[] | null | undefined);
  const { cursor, history } = parseCursorHistory();

  store.clearBootstrap();
  await store.loadInbox(clsid, {
    q: q || undefined,
    cursor,
    cursorHistory: history,
    loadingState: history.length > 0 ? 'pagination' : 'primary',
  });
};

const handleSearch = async (value: string) => {
  await store.refreshSearch(value);
  await syncRouteWithStore();
};

const handleNext = async () => {
  await store.loadNextPage();
  await syncRouteWithStore('push');
};

const handlePrevious = async () => {
  await store.loadPreviousPage();
  await syncRouteWithStore('push');
};

watch(
  () => [route.params.clsid, route.query.q, route.query.cursor, route.query.history],
  () => {
    if (skipNextRouteSync) {
      skipNextRouteSync = false;
      return;
    }

    void loadFromRoute();
  },
  { immediate: true },
);
</script>

<template>
  <MainLayout :status-label="store.statusLabel">
    <CallbackCard
      :callback-url="store.callbackUrl"
      :viewer-url="store.viewerUrl"
      :copied="store.copied"
      :copying="store.loading"
      @copy="store.copyCallbackUrl"
    />

    <p v-if="store.error" class="error-banner">{{ store.error }}</p>

    <section class="workspace-grid">
      <EventList
        :events="store.events"
        :loading="store.loading"
        :loading-more="store.loadingMore"
        :selected-request-id="store.selectedRequestId"
        :search-value="store.search"
        :current-page="store.currentPage"
        :has-next-page="store.hasNextPage"
        :has-previous-page="store.hasPreviousPage"
        @search="handleSearch"
        @select="store.selectRequest"
        @next="handleNext"
        @previous="handlePrevious"
      />
      <PayloadPanel
        :detail="store.selectedEventDetail"
        :loading="store.detailLoading"
        :error="store.detailError"
        :copying="store.payloadCopying"
        :copied="store.payloadCopied"
        @copy="store.copyPayload"
      />
    </section>
  </MainLayout>
</template>