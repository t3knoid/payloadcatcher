import { describe, expect, it } from 'vitest';

import { normalizeBaseUrl } from '@/config/runtime';

describe('normalizeBaseUrl', () => {
  it('removes a trailing slash', () => {
    expect(normalizeBaseUrl('http://127.0.0.1:8000/')).toBe('http://127.0.0.1:8000');
  });

  it('returns an empty string for undefined input', () => {
    expect(normalizeBaseUrl(undefined)).toBe('');
  });
});