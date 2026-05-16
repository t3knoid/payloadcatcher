import { describe, expect, it } from 'vitest';

import { inferLocalApiBaseUrl, normalizeBaseUrl } from '@/config/runtime';

describe('normalizeBaseUrl', () => {
  it('removes a trailing slash', () => {
    expect(normalizeBaseUrl('http://127.0.0.1:8000/')).toBe('http://127.0.0.1:8000');
  });

  it('returns an empty string for undefined input', () => {
    expect(normalizeBaseUrl(undefined)).toBe('');
  });
});

describe('inferLocalApiBaseUrl', () => {
  it('falls back to the local backend port for Vite localhost development', () => {
    expect(
      inferLocalApiBaseUrl({
        protocol: 'http:',
        hostname: '127.0.0.1',
        port: '5173',
      } as Location),
    ).toBe('http://127.0.0.1:8000');
  });

  it('falls back to the local backend port for Vite localhost hostname development', () => {
    expect(
      inferLocalApiBaseUrl({
        protocol: 'http:',
        hostname: 'localhost',
        port: '4173',
      } as Location),
    ).toBe('http://localhost:8000');
  });

  it('does not infer a loopback backend for machine-ip frontend origins', () => {
    expect(
      inferLocalApiBaseUrl({
        protocol: 'http:',
        hostname: '192.168.10.69',
        port: '5173',
      } as Location),
    ).toBe('');
  });

  it('returns an empty string outside the local Vite dev and preview ports', () => {
    expect(
      inferLocalApiBaseUrl({
        protocol: 'https:',
        hostname: 'payloadcat.ch',
        port: '',
      } as Location),
    ).toBe('');
  });
});