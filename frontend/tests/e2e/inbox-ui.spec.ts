import { expect, test } from '@playwright/test';

const CLSID = '550e8400-e29b-41d4-a716-446655440000';
const HOOK_URL = `https://payloadcat.ch/hook/${CLSID}`;
const VIEWER_URL = `https://payloadcat.ch/inbox/${CLSID}`;
const ROTATED_CLSID = '660e8400-e29b-41d4-a716-446655440000';
const ROTATED_HOOK_URL = `https://payloadcat.ch/hook/${ROTATED_CLSID}`;
const ROTATED_VIEWER_URL = `https://payloadcat.ch/inbox/${ROTATED_CLSID}`;

const bootstrapPayload = {
  clsid: CLSID,
  callback_url: HOOK_URL,
  viewer_url: VIEWER_URL,
  expires_at: '2026-05-16T12:00:00Z',
  new_session: true,
};

const rotatedBootstrapPayload = {
  clsid: ROTATED_CLSID,
  callback_url: ROTATED_HOOK_URL,
  viewer_url: ROTATED_VIEWER_URL,
  expires_at: '2026-05-17T12:00:00Z',
  new_session: true,
};

const inboxFirstPage = {
  hook_url: HOOK_URL,
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

const inboxSecondPage = {
  hook_url: HOOK_URL,
  next_token: null,
  metadata: inboxFirstPage.metadata,
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

const detailByRequestId = {
  'req-003': {
    request_id: 'req-003',
    received_at: '2026-05-15T12:00:02Z',
    method: 'PATCH',
    content_type: 'application/json',
    headers: {
      'content-type': 'application/json',
      'x-trace-id': 'trace-003',
    },
    payload_yaml: 'type: patch\nid: 3\nstatus: queued\nembedded: <script>alert(1)</script>',
    source_ip_masked: '203.0.113.xxx',
    payload_size_bytes: 74,
  },
  'req-002': {
    request_id: 'req-002',
    received_at: '2026-05-15T12:00:01Z',
    method: 'POST',
    content_type: 'application/json',
    headers: {
      'content-type': 'application/json',
    },
    payload_yaml: 'type: signup\nemail: ada@example.test',
    source_ip_masked: '203.0.113.xxx',
    payload_size_bytes: 38,
  },
  'req-001': {
    request_id: 'req-001',
    received_at: '2026-05-15T12:00:00Z',
    method: 'PUT',
    content_type: 'text/plain',
    headers: {
      'content-type': 'text/plain',
    },
    payload_yaml: `archived payload\n${'a'.repeat(5000)}\ntail-marker`,
    source_ip_masked: '203.0.113.xxx',
    payload_size_bytes: 400000,
  },
  'req-101': {
    request_id: 'req-101',
    received_at: '2026-05-16T12:00:01Z',
    method: 'POST',
    content_type: 'application/json',
    headers: {
      'content-type': 'application/json',
    },
    payload_yaml: 'type: rotated\nstatus: active',
    source_ip_masked: '203.0.113.xxx',
    payload_size_bytes: 29,
  },
} as const;

const rotatedInboxFirstPage = {
  hook_url: ROTATED_HOOK_URL,
  next_token: null,
  metadata: {
    inbox_issued_at: '2026-05-16T12:00:00Z',
    expires_at: '2026-05-17T12:00:00Z',
    capture_count: 1,
  },
  events: [
    {
      request_id: 'req-101',
      received_at: '2026-05-16T12:00:01Z',
      method: 'POST',
      content_type: 'application/json',
      payload_yaml: 'type: rotated\nstatus: active',
      source_ip_masked: '203.0.113.xxx',
    },
  ],
};

const emptyInbox = {
  hook_url: HOOK_URL,
  next_token: null,
  metadata: inboxFirstPage.metadata,
  events: [],
};

const errorEnvelope = {
  error: {
    code: 'viewer_unavailable',
    message: 'Viewer temporarily unavailable.',
  },
  request_id: 'req-error-001',
};

const filterInboxPayload = (payload: typeof inboxFirstPage | typeof rotatedInboxFirstPage, query: string) => {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return payload;
  }

  return {
    ...payload,
    next_token: null,
    events: payload.events.filter((event) => {
      const searchableValue = [
        event.request_id,
        event.method,
        event.source_ip_masked,
        event.payload_yaml,
      ]
        .join(' ')
        .toLowerCase();

      return searchableValue.includes(normalizedQuery);
    }),
  };
};

const routeInboxApi = async (
  page: Parameters<typeof test.beforeEach>[0]['page'],
  options?: {
    initialDelayMs?: number;
    errorQuery?: string;
    detailDelayMs?: number;
    detailErrorRequestId?: string;
    visitMetadataFailure?: boolean;
    bootstrapSequence?: Array<typeof bootstrapPayload>;
  },
) => {
  let inboxCalls = 0;
  let bootstrapCalls = 0;

  const bootstrapSequence = options?.bootstrapSequence ?? [bootstrapPayload];
  const inboxByClsid: Record<string, typeof inboxFirstPage | typeof rotatedInboxFirstPage> = {
    [CLSID]: inboxFirstPage,
    [ROTATED_CLSID]: rotatedInboxFirstPage,
  };

  await page.route('http://api.payloadcatcher.test/', async (route) => {
    const payload = bootstrapSequence[Math.min(bootstrapCalls, bootstrapSequence.length - 1)];
    bootstrapCalls += 1;

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });

  await page.route('http://api.payloadcatcher.test/visit-metadata', async (route) => {
    if (options?.visitMetadataFailure) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'metadata_unavailable',
            message: 'Visit metadata update unavailable.',
          },
          request_id: 'req-metadata-error-001',
        }),
      });
      return;
    }

    await route.fulfill({
      status: 204,
      body: '',
    });
  });

  await page.route('http://api.payloadcatcher.test/inbox/*/events/*', async (route) => {
    const url = new URL(route.request().url());
    const pathParts = url.pathname.split('/');
    const requestId = decodeURIComponent(pathParts[pathParts.length - 1] ?? '');
    const detailPayload = detailByRequestId[requestId as keyof typeof detailByRequestId];

    if (options?.detailDelayMs) {
      await new Promise((resolve) => setTimeout(resolve, options.detailDelayMs));
    }

    if (options?.detailErrorRequestId === requestId) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'payload_unavailable',
            message: 'Payload temporarily unavailable.',
          },
          request_id: 'req-detail-error-001',
        }),
      });
      return;
    }

    if (!detailPayload) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'event_not_found',
            message: 'Event not found for inbox',
          },
          request_id: 'req-detail-not-found-001',
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(detailPayload),
    });
  });

  await page.route('http://api.payloadcatcher.test/inbox/*', async (route) => {
    const url = new URL(route.request().url());
    const clsid = url.pathname.split('/').pop() ?? '';
    const query = url.searchParams.get('q');
    const cursor = url.searchParams.get('cursor');
    const defaultInboxPayload = inboxByClsid[clsid] ?? inboxFirstPage;

    if (options?.initialDelayMs && !query && !cursor) {
      await new Promise((resolve) => setTimeout(resolve, options.initialDelayMs));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(defaultInboxPayload),
      });
      return;
    }

    if (options?.errorQuery && query === options.errorQuery) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify(errorEnvelope),
      });
      return;
    }

    let payload = defaultInboxPayload;
    if (query === 'nothing') {
      payload = emptyInbox;
    } else if (cursor === 'cursor-next' && clsid === CLSID) {
      payload = inboxSecondPage;
    } else if (query) {
      payload = filterInboxPayload(defaultInboxPayload, query);
    }

    inboxCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });
  });

  return {
    bootstrapCalls: () => bootstrapCalls,
    inboxCalls: () => inboxCalls,
  };
};

test.describe('QA-011 inbox UI flows', () => {
  test.beforeEach(async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await routeInboxApi(page);
  });

  test('renders the branded header and copies the callback URL', async ({ page }) => {
    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('heading', { name: 'PayloadCatcher' })).toBeVisible();
    await expect(page.getByLabel('Callback URL panel')).toBeVisible();
    await expect(page.getByText(`Viewer link: ${VIEWER_URL}`)).toBeVisible();
    await page.getByRole('button', { name: 'Copy callback URL' }).click();
    await expect
      .poll(async () => page.evaluate(() => navigator.clipboard.readText()))
      .toBe(HOOK_URL);
  });

  test('provisions callback URLs on home and keeps reuse or rotation aligned with bootstrap responses', async ({ page, context }) => {
    test.skip(test.info().project.name !== 'chromium', 'Provisioning lifecycle assertions run in the desktop Chromium project only.');

    await page.unroute('http://api.payloadcatcher.test/');
    await page.unroute('http://api.payloadcatcher.test/inbox/*');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const api = await routeInboxApi(page, {
      bootstrapSequence: [bootstrapPayload, bootstrapPayload, rotatedBootstrapPayload],
    });

    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('privacy-notice')).toBeVisible();
    await page.getByTestId('privacy-start-button').click();
    await expect(page.getByRole('button', { name: 'Copy callback URL' })).toContainText(HOOK_URL);
    await expect(page.getByText(`Viewer link: ${VIEWER_URL}`)).toBeVisible();
    await expect(page.getByTestId('request-req-003')).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('button', { name: 'Copy callback URL' })).toContainText(HOOK_URL);
    await expect(page.getByText(`Viewer link: ${VIEWER_URL}`)).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('button', { name: 'Copy callback URL' })).toContainText(ROTATED_HOOK_URL);
    await expect(page.getByText(`Viewer link: ${ROTATED_VIEWER_URL}`)).toBeVisible();
    await expect(page.getByTestId('request-req-101')).toBeVisible();
    expect(api.bootstrapCalls()).toBe(3);
  });

  test('keeps the GPS fallback message visible when geolocation is unavailable', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Allow one-time precise GPS collection for this device.').check();
    await page.getByTestId('privacy-start-button').click();

    await expect(page.getByText('Precise location was unavailable. Continuing with connection and browser metadata only.')).toBeVisible();
  });

  test('keeps the inbox flow available when the GPS metadata update request fails', async ({ page, context }) => {
    test.skip(test.info().project.name !== 'chromium', 'Desktop privacy-state assertions run in the desktop Chromium project only.');

    await page.route(/^http:\/\/api\.payloadcatcher\.test\/(?:\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(bootstrapPayload),
      });
    });
    await page.unroute('http://api.payloadcatcher.test/visit-metadata');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.addInitScript(() => {
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
    });
    await page.route('http://api.payloadcatcher.test/visit-metadata', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'metadata_unavailable',
            message: 'Visit metadata update unavailable.',
          },
          request_id: 'req-metadata-error-001',
        }),
      });
    });

    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Allow one-time precise GPS collection for this device.').check();
    await page.getByTestId('privacy-start-button').click();

    await expect(page.getByText('Precise location could not be saved. Continuing with connection and browser metadata only.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Copy callback URL' })).toContainText(HOOK_URL);
  });

  test('uses the desktop split layout and updates the payload panel when a request is selected', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'Desktop layout assertions run in the desktop Chromium project only.');

    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });

    const listPanel = page.getByTestId('event-list-panel');
    const payloadPanel = page.getByTestId('payload-panel');
    const listBox = await listPanel.boundingBox();
    const payloadBox = await payloadPanel.boundingBox();

    expect(listBox).not.toBeNull();
    expect(payloadBox).not.toBeNull();
    expect(listBox!.x).toBeLessThan(payloadBox!.x);
    expect(payloadBox!.width).toBeGreaterThan(listBox!.width);

    await page.getByTestId('request-req-002').click();
    const payloadPanelContent = page.getByTestId('payload-panel');
    await expect(payloadPanelContent).toContainText('email: ada@example.test');
    await expect(payloadPanelContent).toContainText('Request ID');
    await expect(payloadPanelContent).toContainText('req-002');
    await expect(payloadPanelContent).toContainText('content-type');

    await page.getByTestId('request-req-003').click();
    await expect(payloadPanelContent).toContainText('<script>alert(1)</script>');
    await page.getByTestId('payload-copy-button').click();
    await expect
      .poll(async () => page.evaluate(() => navigator.clipboard.readText()))
      .toContain('embedded: <script>alert(1)</script>');
  });

  test('shows payload detail loading and safe panel errors during selected request fetches', async ({ page, context }) => {
    test.skip(test.info().project.name !== 'chromium', 'Payload detail state assertions run in the desktop Chromium project only.');

    await page.unroute('http://api.payloadcatcher.test/');
    await page.unroute('http://api.payloadcatcher.test/inbox/*/events/*');
    await page.unroute('http://api.payloadcatcher.test/inbox/*');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await routeInboxApi(page, { detailDelayMs: 800, detailErrorRequestId: 'req-002' });

    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('request-req-002').click();

    await expect(page.getByTestId('payload-panel')).toContainText('Loading selected payload...');
    await expect(page.getByTestId('payload-panel')).toContainText('Payload temporarily unavailable.');
    await expect(page.getByTestId('payload-panel')).not.toContainText('TypeError');
  });

  test('reveals large selected payloads incrementally without rendering the full body immediately', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'Large payload assertions run in the desktop Chromium project only.');

    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Next page' }).click();
    await expect(page.getByTestId('request-req-001')).toBeVisible();

    const payloadPanel = page.getByTestId('payload-panel');
    await expect(payloadPanel).toContainText('Syntax highlighting is disabled for large payloads to keep rendering responsive.');
    await expect(payloadPanel).toContainText('Show more');
    await expect(payloadPanel).not.toContainText('tail-marker');

    await page.getByTestId('payload-show-more-button').click();
    await expect(payloadPanel).toContainText('tail-marker');
  });

  test('stacks panels on mobile and supports paging plus empty search states', async ({ page }) => {
    test.skip(test.info().project.name !== 'mobile-chrome', 'Mobile layout assertions run in the mobile Chromium project only.');

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });

    const listPanel = page.getByTestId('event-list-panel');
    const payloadPanel = page.getByTestId('payload-panel');
    const listBox = await listPanel.boundingBox();
    const payloadBox = await payloadPanel.boundingBox();

    expect(listBox).not.toBeNull();
    expect(payloadBox).not.toBeNull();
    expect(listBox!.y).toBeLessThan(payloadBox!.y);

    await expect(page.getByText('Page 1')).toBeVisible();
    await page.getByRole('button', { name: 'Next page' }).click();
    await expect(page.getByText('Page 2')).toBeVisible();
    await expect(page).toHaveURL(new RegExp('cursor=cursor-next'));
    await expect(page).toHaveURL(new RegExp('history=cursor-next'));
    await expect(page.getByTestId('request-req-001')).toBeVisible();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Page 2')).toBeVisible();
    await expect(page.getByTestId('request-req-001')).toBeVisible();

    await page.getByRole('button', { name: 'Previous page' }).click();
    await expect(page.getByText('Page 1')).toBeVisible();
    await expect(page).not.toHaveURL(new RegExp('cursor=cursor-next'));

    await page.getByLabel('Search requests').fill('nothing');
    await expect(page).toHaveURL(new RegExp('q=nothing'));
    await expect(page.getByText('No captured requests match this view yet.')).toBeVisible();
  });

  test('keeps the mobile header branding on one row without horizontal overflow', async ({ page }) => {
    test.skip(test.info().project.name !== 'mobile-chrome', 'Mobile header assertions run in the mobile Chromium project only.');

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });

    const overflowState = await page.evaluate(() => {
      return {
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      };
    });

    expect(overflowState.scrollWidth).toBeLessThanOrEqual(overflowState.clientWidth);

    const logo = page.getByAltText('PayloadCatcher');
    const wordmark = page.locator('.shell__wordmark');
    const logoBox = await logo.boundingBox();
    const wordmarkBox = await wordmark.boundingBox();

    expect(logoBox).not.toBeNull();
    expect(wordmarkBox).not.toBeNull();
    expect(logoBox!.x).toBeGreaterThan(wordmarkBox!.x);
    expect(Math.abs(logoBox!.y - wordmarkBox!.y)).toBeLessThan(40);
  });

  test('preserves inbox pagination state across browser back and forward navigation', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'Browser history assertions run in the desktop Chromium project only.');

    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: 'Next page' }).click();
    await expect(page.getByText('Page 2')).toBeVisible();
    await expect(page).toHaveURL(new RegExp('cursor=cursor-next'));
    await expect(page.getByTestId('request-req-001')).toBeVisible();

    await page.goBack();
    await expect(page).not.toHaveURL(new RegExp('cursor=cursor-next'));
    await expect(page.getByText('Page 1')).toBeVisible();
    await expect(page.getByTestId('request-req-003')).toBeVisible();

    await page.goForward();
    await expect(page).toHaveURL(new RegExp('cursor=cursor-next'));
    await expect(page).toHaveURL(new RegExp('history=cursor-next'));
    await expect(page.getByText('Page 2')).toBeVisible();
    await expect(page.getByTestId('request-req-001')).toBeVisible();
  });

  test('filters the request list as the search query changes', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'Search filter assertions run in the desktop Chromium project only.');

    await page.goto(`/inbox/${CLSID}`, { waitUntil: 'domcontentloaded' });

    await page.getByLabel('Search requests').fill('signup');
    await expect(page).toHaveURL(new RegExp('q=signup'));
    await expect(page.getByTestId('request-req-002')).toBeVisible();
    await expect(page.getByTestId('request-req-003')).toHaveCount(0);

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByLabel('Search requests')).toHaveValue('signup');
    await expect(page.getByTestId('request-req-002')).toBeVisible();
  });

  test('shows readable loading and error banners during inbox refreshes', async ({ page, context }) => {
    test.skip(test.info().project.name !== 'chromium', 'This state-based banner check runs in the desktop Chromium project only.');

    await page.unroute('http://api.payloadcatcher.test/');
    await page.unroute(`http://api.payloadcatcher.test/inbox/${CLSID}*`);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await routeInboxApi(page, { initialDelayMs: 1200, errorQuery: 'error-state' });

    const navigation = page.goto(`/inbox/${CLSID}`, { waitUntil: 'commit' });
  await expect(page.getByTestId('event-list-panel').getByText('Loading inbox events…')).toBeVisible();
    await navigation;

    await expect(page.getByTestId('request-req-003')).toBeVisible();
    await page.getByLabel('Search requests').fill('error-state');
    await expect(page.getByText('Viewer temporarily unavailable.')).toBeVisible();
  });
});