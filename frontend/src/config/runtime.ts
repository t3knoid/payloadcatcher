const normalizeBaseUrl = (value: string | undefined): string => {
  if (!value) {
    return '';
  }

  return value.endsWith('/') ? value.slice(0, -1) : value;
};

const inferLocalApiBaseUrl = (locationValue: Location): string => {
  const isLocalHost = locationValue.hostname === '127.0.0.1' || locationValue.hostname === 'localhost';
  const isVitePort = locationValue.port === '5173' || locationValue.port === '4173';

  if (!isLocalHost || !isVitePort) {
    return '';
  }

  return `${locationValue.protocol}//${locationValue.hostname}:8000`;
};

export const getApiBaseUrl = (): string => {
  const windowConfig = normalizeBaseUrl(window.__PAYLOADCATCHER_CONFIG__?.apiBaseUrl);
  if (windowConfig) {
    return windowConfig;
  }

  const envConfig = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);
  if (envConfig) {
    return envConfig;
  }

  return inferLocalApiBaseUrl(window.location);
};

export { inferLocalApiBaseUrl, normalizeBaseUrl };