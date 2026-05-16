import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { ApiClientError, apiClient } from '@/api/api-client';
import type { BootstrapResponse, InboxEventSummary, InboxResponse } from '@/types/api';

const DEFAULT_LIMIT = 50;

const buildSafeMessage = (error: unknown) => {
  if (error instanceof ApiClientError) {
    return error.message;
  }
  return 'Unable to load inbox data.';
};

export const useInboxStore = defineStore('inbox', () => {
  const bootstrap = ref<BootstrapResponse | null>(null);
  const inbox = ref<InboxResponse | null>(null);
  const events = ref<InboxEventSummary[]>([]);
  const selectedRequestId = ref<string | null>(null);
  const search = ref('');
  const loading = ref(false);
  const loadingMore = ref(false);
  const copying = ref(false);
  const copied = ref(false);
  const error = ref<string | null>(null);
  const activeClsid = ref<string | null>(null);

  const selectedEvent = computed(() => {
    return events.value.find((event) => event.request_id === selectedRequestId.value) ?? events.value[0] ?? null;
  });

  const callbackUrl = computed(() => {
    return bootstrap.value?.callback_url ?? inbox.value?.hook_url ?? '';
  });

  const viewerUrl = computed(() => {
    if (bootstrap.value?.viewer_url) {
      return bootstrap.value.viewer_url;
    }

    if (inbox.value?.hook_url && activeClsid.value) {
      try {
        const viewerUrl = new URL(inbox.value.hook_url);
        viewerUrl.pathname = `/inbox/${activeClsid.value}`;
        viewerUrl.search = '';
        viewerUrl.hash = '';
        return viewerUrl.toString();
      } catch {
        return '';
      }
    }

    return '';
  });

  const statusLabel = computed(() => {
    if (loading.value) {
      return 'Syncing';
    }
    return events.value.length > 0 ? 'Listening' : 'Waiting';
  });

  const applyInbox = (payload: InboxResponse, mode: 'replace' | 'append') => {
    inbox.value = payload;
    events.value = mode === 'append' ? [...events.value, ...payload.events] : payload.events;

    if (!selectedRequestId.value || !events.value.some((event) => event.request_id === selectedRequestId.value)) {
      selectedRequestId.value = events.value[0]?.request_id ?? null;
    }
  };

  const loadInbox = async (clsid: string, options?: { q?: string; cursor?: string | null; mode?: 'replace' | 'append' }) => {
    activeClsid.value = clsid;
    error.value = null;
    if ((options?.mode ?? 'replace') === 'replace') {
      loading.value = true;
    } else {
      loadingMore.value = true;
    }

    try {
      const payload = await apiClient.getInbox(clsid, {
        q: options?.q,
        cursor: options?.cursor,
        limit: DEFAULT_LIMIT,
      });
      applyInbox(payload, options?.mode ?? 'replace');
    } catch (caughtError) {
      error.value = buildSafeMessage(caughtError);
    } finally {
      loading.value = false;
      loadingMore.value = false;
    }
  };

  const bootstrapHome = async () => {
    loading.value = true;
    error.value = null;

    try {
      const payload = await apiClient.bootstrapInbox();
      bootstrap.value = payload;
      activeClsid.value = payload.clsid;
      await loadInbox(payload.clsid, { mode: 'replace' });
    } catch (caughtError) {
      error.value = buildSafeMessage(caughtError);
      loading.value = false;
    }
  };

  const loadNextPage = async () => {
    if (!activeClsid.value || !inbox.value?.next_token || loadingMore.value) {
      return;
    }

    await loadInbox(activeClsid.value, {
      q: search.value || undefined,
      cursor: inbox.value.next_token,
      mode: 'append',
    });
  };

  const refreshSearch = async (value: string) => {
    search.value = value;
    if (!activeClsid.value) {
      return;
    }

    await loadInbox(activeClsid.value, {
      q: value || undefined,
      mode: 'replace',
    });
  };

  const selectRequest = (requestId: string) => {
    selectedRequestId.value = requestId;
  };

  const copyCallbackUrl = async () => {
    if (!callbackUrl.value) {
      return;
    }

    copying.value = true;
    try {
      await navigator.clipboard.writeText(callbackUrl.value);
      copied.value = true;
      window.setTimeout(() => {
        copied.value = false;
      }, 1800);
    } finally {
      copying.value = false;
    }
  };

  const clearBootstrap = () => {
    bootstrap.value = null;
  };

  return {
    activeClsid,
    bootstrap,
    callbackUrl,
    clearBootstrap,
    copied,
    copyCallbackUrl,
    error,
    events,
    inbox,
    loadInbox,
    loadNextPage,
    loading,
    loadingMore,
    refreshSearch,
    search,
    selectRequest,
    selectedEvent,
    selectedRequestId,
    statusLabel,
    viewerUrl,
    bootstrapHome,
  };
});