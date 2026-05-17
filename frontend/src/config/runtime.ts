const normalizeBaseUrl = (value: string | undefined): string => {
  if (!value) {
    return '';
  }

  return value.endsWith('/') ? value.slice(0, -1) : value;
};

const isLoopbackHost = (hostname: string): boolean => {
  return hostname === '127.0.0.1' || hostname === 'localhost';
};

const isVitePort = (port: string): boolean => {
  return port === '5173' || port === '4173';
};

const rebaseLoopbackApiBaseUrl = (envConfig: string, locationValue: Location): string => {
  if (!envConfig || isLoopbackHost(locationValue.hostname) || !isVitePort(locationValue.port)) {
    return envConfig;
  }

  try {
    const envUrl = new URL(envConfig);
    if (!isLoopbackHost(envUrl.hostname)) {
      return envConfig;
    }

    envUrl.hostname = locationValue.hostname;
    return envUrl.toString().replace(/\/$/, '');
  } catch {
    return envConfig;
  }
};

const inferLocalApiBaseUrl = (locationValue: Location): string => {
  const isLocalHost = isLoopbackHost(locationValue.hostname);
  const isLocalVitePort = isVitePort(locationValue.port);

  if (!isLocalHost || !isLocalVitePort) {
    return '';
  }

  return `${locationValue.protocol}//${locationValue.hostname}:8000`;
};

const resolveApiBaseUrl = ({ envConfig, locationValue }: { envConfig: string; locationValue: Location }): string => {
  const rebasedEnvConfig = rebaseLoopbackApiBaseUrl(envConfig, locationValue);
  if (rebasedEnvConfig) {
    return rebasedEnvConfig;
  }

  return inferLocalApiBaseUrl(locationValue);
};

export const getApiBaseUrl = (): string => {
  const windowConfig = normalizeBaseUrl(window.__PAYLOADCATCHER_CONFIG__?.apiBaseUrl);
  if (windowConfig) {
    return windowConfig;
  }

  const envConfig = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);
  return resolveApiBaseUrl({
    envConfig,
    locationValue: window.location,
  });
};

export { inferLocalApiBaseUrl, normalizeBaseUrl, resolveApiBaseUrl };