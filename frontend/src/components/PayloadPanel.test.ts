import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import PayloadPanel from '@/components/PayloadPanel.vue';

const detail = {
  request_id: 'req-003',
  received_at: '2026-05-15T12:00:02Z',
  method: 'PATCH',
  content_type: 'application/json',
  headers: {
    'content-type': 'application/json',
    'x-trace-id': 'trace-003',
  },
  payload_yaml: 'type: patch\nembedded: <script>alert(1)</script>',
  source_ip_masked: '203.0.113.xxx',
  payload_size_bytes: 96,
};

describe('PayloadPanel', () => {
  it('renders metadata, headers, and safely highlighted payload content', () => {
    const wrapper = mount(PayloadPanel, {
      props: {
        detail,
        loading: false,
        error: null,
        copying: false,
        copied: false,
      },
    });

    expect(wrapper.text()).toContain('Request ID');
    expect(wrapper.text()).toContain('req-003');
    expect(wrapper.text()).toContain('x-trace-id');
    expect(wrapper.text()).toContain('<script>alert(1)</script>');
    expect(wrapper.html()).not.toContain('<script>alert(1)</script>');
    expect(wrapper.find('.token').exists()).toBe(true);
  });

  it('shows loading and error states without rendering stale payload content', () => {
    const loadingWrapper = mount(PayloadPanel, {
      props: {
        detail: null,
        loading: true,
        error: null,
        copying: false,
        copied: false,
      },
    });
    expect(loadingWrapper.text()).toContain('Loading selected payload...');

    const errorWrapper = mount(PayloadPanel, {
      props: {
        detail: null,
        loading: false,
        error: 'Payload temporarily unavailable.',
        copying: false,
        copied: false,
      },
    });
    expect(errorWrapper.text()).toContain('Payload temporarily unavailable.');
  });

  it('emits copy when the copy button is clicked', async () => {
    const wrapper = mount(PayloadPanel, {
      props: {
        detail,
        loading: false,
        error: null,
        copying: false,
        copied: false,
      },
    });

    await wrapper.get('[data-testid="payload-copy-button"]').trigger('click');

    expect(wrapper.emitted('copy')).toEqual([[]]);
  });

  it('renders large payloads incrementally instead of mounting the full payload at once', async () => {
    const tailMarker = 'tail-marker';
    const largeDetail = {
      ...detail,
      payload_yaml: `header: start\n${'a'.repeat(5000)}\n${tailMarker}`,
      payload_size_bytes: 400000,
    };

    const wrapper = mount(PayloadPanel, {
      props: {
        detail: largeDetail,
        loading: false,
        error: null,
        copying: false,
        copied: false,
      },
    });

    expect(wrapper.text()).toContain('Syntax highlighting is disabled for large payloads to keep rendering responsive.');
    expect(wrapper.text()).toContain('Show more');
    expect(wrapper.text()).not.toContain(tailMarker);

    await wrapper.get('[data-testid="payload-show-more-button"]').trigger('click');

    expect(wrapper.text()).toContain(tailMarker);
  });
});