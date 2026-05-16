const normalizeBaseUrl = (value: string | undefined): string => {
  if (!value) {
    return '';
  }

  return value.endsWith('/') ? value.slice(0, -1) : value;
};

export const getApiBaseUrl = (): string => {
  const windowConfig = normalizeBaseUrl(window.__PAYLOADCATCHER_CONFIG__?.apiBaseUrl);
  if (windowConfig) {
    return windowConfig;
  }

  return normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);
};

export { normalizeBaseUrl };