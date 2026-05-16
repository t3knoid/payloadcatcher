import { flushPromises, mount } from '@vue/test-utils';
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

import HomeView from '@/views/HomeView.vue';

const CLSID = '550e8400-e29b-41d4-a716-446655440000';

const bootstrapPayload = {
  clsid: CLSID,
  callback_url: `https://payloadcat.ch/hook/${CLSID}`,
  viewer_url: `https://payloadcat.ch/inbox/${CLSID}`,
  expires_at: '2026-05-16T12:00:00Z',
  new_session: true,
};

const inboxPayload = {
  hook_url: `https://payloadcat.ch/hook/${CLSID}`,
  next_token: null,
  metadata: {
    inbox_issued_at: '2026-05-15T12:00:00Z',
    expires_at: '2026-05-16T12:00:00Z',
    capture_count: 1,
  },
  events: [
    {
      request_id: 'req-001',
      received_at: '2026-05-15T12:00:00Z',
      method: 'POST',
      content_type: 'application/json',
      payload_yaml: 'type: signup',
      source_ip_masked: '203.0.113.xxx',
    },
  ],
};

const detailPayload = {
  request_id: 'req-001',
  received_at: '2026-05-15T12:00:00Z',
  method: 'POST',
  content_type: 'application/json',
  headers: {
    'content-type': 'application/json',
  },
  payload_yaml: 'type: signup',
  source_ip_masked: '203.0.113.xxx',
  payload_size_bytes: 24,
};

describe('HomeView privacy notice', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    window.localStorage.clear();
    bootstrapInbox.mockReset();
    getInbox.mockReset();
    getInboxEventDetail.mockReset();
    delete (navigator as Navigator & { geolocation?: Geolocation }).geolocation;
  });

  it('shows the privacy notice before bootstrapping the inbox on first visit', async () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [createPinia()],
      },
    });

    await flushPromises();

    expect(wrapper.get('[data-testid="privacy-notice"]').text()).toContain('Review metadata collection');
    expect(bootstrapInbox).not.toHaveBeenCalled();
  });

  it('collects GPS only after explicit opt-in and then bootstraps the inbox', async () => {
    bootstrapInbox.mockResolvedValueOnce(bootstrapPayload);
    getInbox.mockResolvedValueOnce(inboxPayload);
    getInboxEventDetail.mockResolvedValueOnce(detailPayload);

    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: (success: PositionCallback) => {
          success({
            coords: {
              latitude: 35.77959,
              longitude: -78.63818,
              accuracy: 25,
              altitude: null,
              altitudeAccuracy: null,
              heading: null,
              speed: null,
              toJSON: () => ({}),
            },
            timestamp: Date.now(),
            toJSON: () => ({}),
          } as GeolocationPosition);
        },
      },
    });

    const wrapper = mount(HomeView, {
      global: {
        plugins: [createPinia()],
      },
    });

    await wrapper.get('#gps-consent-toggle').setValue(true);
    await wrapper.get('[data-testid="privacy-start-button"]').trigger('click');
    await flushPromises();

    expect(bootstrapInbox).toHaveBeenCalledWith(
      expect.objectContaining({
        gpsConsent: true,
        gpsLat: 35.77959,
        gpsLng: -78.63818,
      }),
    );
    expect(window.localStorage.getItem('payloadcatcher_privacy_notice_ack')).toBe('accepted');
  });
});