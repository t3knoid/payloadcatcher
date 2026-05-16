import { fileURLToPath } from 'node:url';

import { defineConfig, devices } from '@playwright/test';

const frontendRoot = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:42173',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 42173 --strictPort',
    cwd: frontendRoot,
    port: 42173,
    reuseExistingServer: false,
    env: {
      VITE_API_BASE_URL: 'http://api.payloadcatcher.test',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
  ],
});