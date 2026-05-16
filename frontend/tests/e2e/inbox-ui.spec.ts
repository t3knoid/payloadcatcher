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

const routeInboxApi = async (
  page: Parameters<typeof test.beforeEach>[0]['page'],
  options?: {
    initialDelayMs?: number;
    errorQuery?: string;
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

  await page.route('http://api.payloadcatcher.test/inbox/*', async (route) => {
    const url = new URL(route.request().url());
    const clsid = url.pathname.split('/').pop() ?? '';
    const query = url.searchParams.get('q');
    const cursor = url.searchParams.get('cursor');
    const defaultInboxPayload = inboxByClsid[clsid] ?? inboxFirstPage;

    if (options?.initialDelayMs && !query && !cursor) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(defaultInboxPayload),
        delay: options.initialDelayMs,
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
    await expect(page.getByText('email: ada@example.test')).toBeVisible();
    await expect(page.getByText('Request ID')).toBeVisible();
    await expect(page.getByText('req-002')).toBeVisible();
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

    await page.getByRole('button', { name: 'Load more requests' }).click();
    await expect(page.getByTestId('request-req-001')).toBeVisible();

    await page.getByLabel('Search requests').fill('nothing');
    await expect(page.getByText('No captured requests match this view yet.')).toBeVisible();
  });

  test('shows readable loading and error banners during inbox refreshes', async ({ page, context }) => {
    test.skip(test.info().project.name !== 'chromium', 'This state-based banner check runs in the desktop Chromium project only.');

    await page.unroute('http://api.payloadcatcher.test/');
    await page.unroute(`http://api.payloadcatcher.test/inbox/${CLSID}*`);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await routeInboxApi(page, { initialDelayMs: 1200, errorQuery: 'error-state' });

    const navigation = page.goto(`/inbox/${CLSID}`, { waitUntil: 'commit' });
    await expect(page.getByText('Loading inbox events…')).toBeVisible();
    await navigation;

    await expect(page.getByTestId('request-req-003')).toBeVisible();
    await page.getByLabel('Search requests').fill('error-state');
    await expect(page.getByText('Viewer temporarily unavailable.')).toBeVisible();
  });
});