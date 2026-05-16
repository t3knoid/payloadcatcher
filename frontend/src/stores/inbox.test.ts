import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { bootstrapInbox, getInbox, getInboxEventDetail } = vi.hoisted(() => {
  return {
    bootstrapInbox: vi.fn(),
    getInbox: vi.fn(),
    getInboxEventDetail: vi.fn(),
  };
});

vi.mock('@/api/api-client', () => {
  class ApiClientError extends Error {
    status: number;
    code: string;
    requestId?: string;

    constructor(status: number, payload: { error?: { code?: string; message?: string }; request_id?: string } | null) {
      super(payload?.error?.message ?? 'Request failed');
      this.name = 'ApiClientError';
      this.status = status;
      this.code = payload?.error?.code ?? 'request_failed';
      this.requestId = payload?.request_id;
    }
  }

  return {
    ApiClientError,
    apiClient: {
      bootstrapInbox,
      getInbox,
      getInboxEventDetail,
    },
  };
});

import { useInboxStore } from '@/stores/inbox';

const CLSID = '550e8400-e29b-41d4-a716-446655440000';

const firstPage = {
  hook_url: `https://payloadcat.ch/hook/${CLSID}`,
  next_token: 'cursor-next',
  metadata: {
    inbox_issued_at: '2026-05-15T12:00:00Z',
    expires_at: '2026-05-16T12:00:00Z',
    capture_count: 3,
  },
  events: [
    {
      request_id: 'req-003',
      received_at: '2026-05-15T12:00:02Z',
      method: 'PATCH',
      content_type: 'application/json',
      payload_yaml: 'type: patch\nid: 3\nstatus: queued',
      source_ip_masked: '203.0.113.xxx',
    },
    {
      request_id: 'req-002',
      received_at: '2026-05-15T12:00:01Z',
      method: 'POST',
      content_type: 'application/json',
      payload_yaml: 'type: signup\nemail: ada@example.test',
      source_ip_masked: '203.0.113.xxx',
    },
  ],
};

const secondPage = {
  ...firstPage,
  next_token: null,
  events: [
    {
      request_id: 'req-001',
      received_at: '2026-05-15T12:00:00Z',
      method: 'PUT',
      content_type: 'text/plain',
      payload_yaml: 'archived payload',
      source_ip_masked: '203.0.113.xxx',
    },
  ],
};

const filteredPage = {
  ...firstPage,
  next_token: null,
  events: [firstPage.events[1]],
};

const firstDetail = {
  request_id: 'req-003',
  received_at: '2026-05-15T12:00:02Z',
  method: 'PATCH',
  content_type: 'application/json',
  headers: {
    'content-type': 'application/json',
    'x-trace-id': 'trace-003',
  },
  payload_yaml: 'type: patch\nid: 3\nstatus: queued\n<script>alert(1)</script>',
  source_ip_masked: '203.0.113.xxx',
  payload_size_bytes: 64,
};

const secondDetail = {
  request_id: 'req-002',
  received_at: '2026-05-15T12:00:01Z',
  method: 'POST',
  content_type: 'application/json',
  headers: {
    'content-type': 'application/json',
  },
  payload_yaml: 'type: signup\nemail: ada@example.test',
  source_ip_masked: '203.0.113.xxx',
  payload_size_bytes: 39,
};

describe('inbox store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getInbox.mockReset();
    bootstrapInbox.mockReset();
    getInboxEventDetail.mockReset();
  });

  it('loads selected event detail after the inbox list is loaded', async () => {
    const store = useInboxStore();

    getInbox.mockResolvedValueOnce(firstPage);
    getInboxEventDetail.mockResolvedValueOnce(firstDetail);

    await store.loadInbox(CLSID);

    expect(getInboxEventDetail).toHaveBeenCalledWith(CLSID, 'req-003');
    expect(store.selectedEventDetail).toEqual(firstDetail);
    expect(store.detailError).toBeNull();
    expect(store.detailLoading).toBe(false);
  });

  it('resets pagination state when search changes', async () => {
    const store = useInboxStore();

    getInbox.mockResolvedValueOnce(firstPage);
    getInboxEventDetail.mockResolvedValueOnce(firstDetail);
    await store.loadInbox(CLSID);

    getInbox.mockResolvedValueOnce(secondPage);
    getInboxEventDetail.mockResolvedValueOnce({
      ...firstDetail,
      request_id: 'req-001',
      payload_yaml: 'archived payload',
      payload_size_bytes: 16,
    });
    await store.loadNextPage();

    getInbox.mockResolvedValueOnce(filteredPage);
    getInboxEventDetail.mockResolvedValueOnce(secondDetail);
    await store.refreshSearch('signup');

    expect(getInbox).toHaveBeenLastCalledWith(CLSID, {
      q: 'signup',
      cursor: null,
      limit: 50,
    });
    expect(store.search).toBe('signup');
    expect(store.currentPage).toBe(1);
    expect(store.cursorHistory).toEqual([]);
    expect(store.currentCursor).toBeNull();
    expect(store.events.map((event) => event.request_id)).toEqual(['req-002']);
  });

  it('tracks next and previous page state with cursor history', async () => {
    const store = useInboxStore();

    getInbox.mockResolvedValueOnce(firstPage);
    getInboxEventDetail.mockResolvedValueOnce(firstDetail);
    await store.loadInbox(CLSID);

    getInbox.mockResolvedValueOnce(secondPage);
    getInboxEventDetail.mockResolvedValueOnce({
      ...firstDetail,
      request_id: 'req-001',
      payload_yaml: 'archived payload',
      payload_size_bytes: 16,
    });
    await store.loadNextPage();

    expect(getInbox).toHaveBeenLastCalledWith(CLSID, {
      q: undefined,
      cursor: 'cursor-next',
      limit: 50,
    });
    expect(store.currentPage).toBe(2);
    expect(store.currentCursor).toBe('cursor-next');
    expect(store.cursorHistory).toEqual(['cursor-next']);
    expect(store.events.map((event) => event.request_id)).toEqual(['req-001']);

    getInbox.mockResolvedValueOnce(firstPage);
  getInboxEventDetail.mockResolvedValueOnce(firstDetail);
    await store.loadPreviousPage();

    expect(getInbox).toHaveBeenLastCalledWith(CLSID, {
      q: undefined,
      cursor: null,
      limit: 50,
    });
    expect(store.currentPage).toBe(1);
    expect(store.currentCursor).toBeNull();
    expect(store.cursorHistory).toEqual([]);
    expect(store.events.map((event) => event.request_id)).toEqual(['req-003', 'req-002']);
  });

  it('reloads detail when selecting another request and surfaces safe detail errors', async () => {
    const store = useInboxStore();

    getInbox.mockResolvedValueOnce(firstPage);
    getInboxEventDetail.mockResolvedValueOnce(firstDetail);
    await store.loadInbox(CLSID);

    getInboxEventDetail.mockRejectedValueOnce(
      new Error('Payload temporarily unavailable.'),
    );
    await store.selectRequest('req-002');

    expect(getInboxEventDetail).toHaveBeenLastCalledWith(CLSID, 'req-002');
    expect(store.selectedRequestId).toBe('req-002');
    expect(store.selectedEventDetail).toBeNull();
    expect(store.detailError).toBe('Unable to load inbox data.');
  });
});