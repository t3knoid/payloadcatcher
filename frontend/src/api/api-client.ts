import { getApiBaseUrl } from '@/config/runtime';
import type { ApiErrorEnvelope, BootstrapResponse, InboxEventDetail, InboxResponse } from '@/types/api';

class ApiClientError extends Error {
  status: number;
  code: string;
  requestId?: string;

  constructor(status: number, payload: ApiErrorEnvelope | null) {
    super(payload?.error.message ?? 'Request failed');
    this.name = 'ApiClientError';
    this.status = status;
    this.code = payload?.error.code ?? 'request_failed';
    this.requestId = payload?.request_id;
  }
}

const buildUrl = (path: string, query?: Record<string, string | number | undefined | null>) => {
  const baseUrl = getApiBaseUrl();
  const url = new URL(path, baseUrl || window.location.origin);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return url.toString();
};

const request = async <T>(path: string, init?: RequestInit, query?: Record<string, string | number | undefined | null>): Promise<T> => {
  const response = await fetch(buildUrl(path, query), {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let payload: ApiErrorEnvelope | null = null;
    try {
      payload = (await response.json()) as ApiErrorEnvelope;
    } catch {
      payload = null;
    }
    throw new ApiClientError(response.status, payload);
  }

  return (await response.json()) as T;
};

export const apiClient = {
  bootstrapInbox(): Promise<BootstrapResponse> {
    return request<BootstrapResponse>('/');
  },
  getInbox(clsid: string, params?: { q?: string; cursor?: string | null; limit?: number }): Promise<InboxResponse> {
    return request<InboxResponse>(`/inbox/${clsid}`, undefined, params);
  },
  getInboxEventDetail(clsid: string, requestId: string): Promise<InboxEventDetail> {
    return request<InboxEventDetail>(`/inbox/${clsid}/events/${encodeURIComponent(requestId)}`);
  },
};

export { ApiClientError };