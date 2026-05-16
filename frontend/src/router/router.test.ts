import { describe, expect, it } from 'vitest';

import { buildRouter } from '@/router';

describe('router', () => {
  it('resolves the home route', () => {
    const router = buildRouter();

    expect(router.resolve('/').name).toBe('home');
  });

  it('resolves inbox routes with clsid params', () => {
    const router = buildRouter();
    const result = router.resolve('/inbox/550e8400-e29b-41d4-a716-446655440000');

    expect(result.name).toBe('inbox');
    expect(result.params.clsid).toBe('550e8400-e29b-41d4-a716-446655440000');
  });
});