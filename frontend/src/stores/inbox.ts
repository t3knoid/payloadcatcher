import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

import { ApiClientError, apiClient } from '@/api/api-client';
import type {
  BootstrapRequest,
  BootstrapResponse,
  InboxEventDetail,
  InboxEventSummary,
  InboxResponse,
  VisitMetadataUpdateRequest,
} from '@/types/api';

const DEFAULT_LIMIT = 50;

type LoadInboxOptions = {
  q?: string;
  cursor?: string | null;
  cursorHistory?: string[];
  loadingState?: 'primary' | 'pagination';
};

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
  const selectedEventDetail = ref<InboxEventDetail | null>(null);
  const search = ref('');
  const loading = ref(false);
  const loadingMore = ref(false);
  const detailLoading = ref(false);
  const copying = ref(false);
  const copied = ref(false);
  const payloadCopying = ref(false);
  const payloadCopied = ref(false);
  const error = ref<string | null>(null);
  const detailError = ref<string | null>(null);
  const activeClsid = ref<string | null>(null);
  const currentCursor = ref<string | null>(null);
  const cursorHistory = ref<string[]>([]);
  let detailRequestSequence = 0;

  const selectedEvent = computed(() => {
    return events.value.find((event) => event.request_id === selectedRequestId.value) ?? events.value[0] ?? null;
  });

  const currentPage = computed(() => cursorHistory.value.length + 1);
  const hasNextPage = computed(() => Boolean(inbox.value?.next_token));
  const hasPreviousPage = computed(() => cursorHistory.value.length > 0);

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

  const applyInbox = (payload: InboxResponse) => {
    inbox.value = payload;
    events.value = payload.events;

    if (!selectedRequestId.value || !events.value.some((event) => event.request_id === selectedRequestId.value)) {
      selectedRequestId.value = events.value[0]?.request_id ?? null;
    }
  };

  const clearSelectedEventDetail = () => {
    selectedEventDetail.value = null;
    detailError.value = null;
    detailLoading.value = false;
    payloadCopying.value = false;
    payloadCopied.value = false;
  };

  const loadEventDetail = async (requestId: string) => {
    if (!activeClsid.value) {
      clearSelectedEventDetail();
      return;
    }

    const requestSequence = ++detailRequestSequence;
    detailLoading.value = true;
    detailError.value = null;
    selectedEventDetail.value = null;
    payloadCopied.value = false;

    try {
      const payload = await apiClient.getInboxEventDetail(activeClsid.value, requestId);
      if (requestSequence !== detailRequestSequence || selectedRequestId.value !== requestId) {
        return;
      }

      selectedEventDetail.value = payload;
    } catch (caughtError) {
      if (requestSequence !== detailRequestSequence || selectedRequestId.value !== requestId) {
        return;
      }

      detailError.value = buildSafeMessage(caughtError);
    } finally {
      if (requestSequence === detailRequestSequence && selectedRequestId.value === requestId) {
        detailLoading.value = false;
      }
    }
  };

  const ensureSelectedEventDetail = async () => {
    const requestId = selectedRequestId.value;
    if (!requestId) {
      clearSelectedEventDetail();
      return;
    }

    if (selectedEventDetail.value?.request_id === requestId && !detailError.value) {
      return;
    }

    await loadEventDetail(requestId);
  };

  const loadInbox = async (clsid: string, options?: LoadInboxOptions) => {
    activeClsid.value = clsid;
    error.value = null;
    search.value = options?.q ?? '';

    if ((options?.loadingState ?? 'primary') === 'primary') {
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
      applyInbox(payload);
      currentCursor.value = options?.cursor ?? null;
      cursorHistory.value = [...(options?.cursorHistory ?? [])];
      await ensureSelectedEventDetail();
    } catch (caughtError) {
      error.value = buildSafeMessage(caughtError);
    } finally {
      loading.value = false;
      loadingMore.value = false;
    }
  };

  const bootstrapHome = async (metadata?: BootstrapRequest) => {
    loading.value = true;
    error.value = null;

    try {
      const payload = await apiClient.bootstrapInbox(metadata);
      bootstrap.value = payload;
      activeClsid.value = payload.clsid;
      await loadInbox(payload.clsid);
      return payload;
    } catch (caughtError) {
      error.value = buildSafeMessage(caughtError);
      loading.value = false;
      return null;
    }
  };

  const updateVisitMetadata = async (payload: VisitMetadataUpdateRequest) => {
    await apiClient.updateVisitMetadata(payload);
  };

  const loadNextPage = async () => {
    if (!activeClsid.value || !inbox.value?.next_token || loadingMore.value) {
      return;
    }

    const nextCursor = inbox.value.next_token;
    const nextHistory = [...cursorHistory.value, nextCursor];

    await loadInbox(activeClsid.value, {
      q: search.value || undefined,
      cursor: nextCursor,
      cursorHistory: nextHistory,
      loadingState: 'pagination',
    });
  };

  const loadPreviousPage = async () => {
    if (!activeClsid.value || cursorHistory.value.length === 0 || loadingMore.value) {
      return;
    }

    const previousHistory = cursorHistory.value.slice(0, -1);
    const previousCursor = previousHistory.at(-1) ?? null;

    await loadInbox(activeClsid.value, {
      q: search.value || undefined,
      cursor: previousCursor,
      cursorHistory: previousHistory,
      loadingState: 'pagination',
    });
  };

  const refreshSearch = async (value: string) => {
    search.value = value;
    if (!activeClsid.value) {
      return;
    }

    await loadInbox(activeClsid.value, {
      q: value || undefined,
      cursor: null,
      cursorHistory: [],
    });
  };

  const selectRequest = (requestId: string) => {
    if (
      selectedRequestId.value === requestId &&
      selectedEventDetail.value?.request_id === requestId &&
      !detailError.value
    ) {
      return Promise.resolve();
    }

    selectedRequestId.value = requestId;
    return loadEventDetail(requestId);
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

  const copyPayload = async () => {
    if (!selectedEventDetail.value) {
      return;
    }

    payloadCopying.value = true;
    try {
      await navigator.clipboard.writeText(selectedEventDetail.value.payload_yaml);
      payloadCopied.value = true;
      window.setTimeout(() => {
        payloadCopied.value = false;
      }, 1800);
    } finally {
      payloadCopying.value = false;
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
    copyPayload,
    currentCursor,
    currentPage,
    cursorHistory,
    detailError,
    detailLoading,
    error,
    events,
    hasNextPage,
    hasPreviousPage,
    inbox,
    loadInbox,
    loadNextPage,
    loadPreviousPage,
    loading,
    loadingMore,
    payloadCopied,
    payloadCopying,
    refreshSearch,
    search,
    selectRequest,
    selectedEventDetail,
    selectedEvent,
    selectedRequestId,
    statusLabel,
    updateVisitMetadata,
    viewerUrl,
    bootstrapHome,
  };
});