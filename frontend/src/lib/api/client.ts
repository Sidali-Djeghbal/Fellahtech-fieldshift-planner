import { ErrorEnvelopeSchema, TokenPairResponseSchema } from "@/lib/schemas";
import { useAppStore } from "@/store/useAppStore";
import { ApiClientError } from "./errors";
import { fixtureState, handleFixtureRequest } from "./fixtures";

export interface TokenAdapter {
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  getGuestToken: () => string | null;
  onTokensRotated: (tokens: { accessToken: string; refreshToken: string }) => void;
  onAuthInvalidated: () => void;
}

export interface ApiClientConfig {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  tokenAdapter?: TokenAdapter;
  fixtureMode?: boolean;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  idempotencyKey?: string;
  sendBothAuthAndGuest?: boolean;
  skipAuthRefresh?: boolean;
  signal?: AbortSignal;
}

export function isFixtureMode(): boolean {
  return process.env.NEXT_PUBLIC_API_MODE !== "live";
}

function createUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

const defaultTokenAdapter: TokenAdapter = {
  getAccessToken: () => useAppStore.getState().accessToken,
  getRefreshToken: () => useAppStore.getState().refreshToken,
  getGuestToken: () => useAppStore.getState().guestToken,
  onTokensRotated: ({ accessToken, refreshToken }) => {
    useAppStore.getState().setAuthenticatedSession({
      accessToken,
      refreshToken,
      keepGuestToken: true,
    });
  },
  onAuthInvalidated: () => {
    useAppStore.getState().clearSession();
  },
};

export function resolveApiBaseRoot(envBaseUrl?: string | null): string {
  const trimmed = (envBaseUrl ?? "").trim().replace(/\/+$/, "");
  if (!trimmed) return "/api/v1";
  const withoutPrefix = trimmed.endsWith("/api/v1")
    ? trimmed.slice(0, -"/api/v1".length).replace(/\/+$/, "")
    : trimmed;
  return `${withoutPrefix}/api/v1`;
}

export function createApiClient(config: ApiClientConfig = {}) {
  const fetchFn = config.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const tokens = config.tokenAdapter ?? defaultTokenAdapter;
  const baseRoot = config.baseUrl
    ? config.baseUrl.replace(/\/+$/, "")
    : resolveApiBaseRoot(process.env.NEXT_PUBLIC_API_BASE_URL);

  let inflightRefresh: Promise<string | null> | null = null;

  async function refreshAccessToken(): Promise<string | null> {
    if (inflightRefresh) {
      return inflightRefresh;
    }

    const currentRefresh = tokens.getRefreshToken();
    if (!currentRefresh) {
      return null;
    }

    inflightRefresh = (async () => {
      try {
        const useFixture = config.fixtureMode ?? isFixtureMode();
        if (useFixture) {
          const res = await handleFixtureRequest("/auth/refresh", {
            method: "POST",
            body: { refresh_token: currentRefresh },
            headers: { "X-Request-Id": createUuid() },
          });
          const parsed = TokenPairResponseSchema.parse(res.data);
          tokens.onTokensRotated({
            accessToken: parsed.access_token,
            refreshToken: parsed.refresh_token,
          });
          return parsed.access_token;
        }

        const resp = await fetchFn(`${baseRoot}/auth/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Request-Id": createUuid(),
          },
          body: JSON.stringify({ refresh_token: currentRefresh }),
        });

        if (!resp.ok) {
          tokens.onAuthInvalidated();
          return null;
        }

        const json = await resp.json();
        const parsed = TokenPairResponseSchema.parse(json);
        tokens.onTokensRotated({
          accessToken: parsed.access_token,
          refreshToken: parsed.refresh_token,
        });
        return parsed.access_token;
      } catch {
        tokens.onAuthInvalidated();
        return null;
      } finally {
        inflightRefresh = null;
      }
    })();

    return inflightRefresh;
  }

  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? "GET";
    const useFixture = config.fixtureMode ?? isFixtureMode();

    const buildHeaders = (overrideBearer?: string): Record<string, string> => {
      const hdrs: Record<string, string> = {
        "X-Request-Id": createUuid(),
        ...(options.headers ?? {}),
      };
      if (options.body !== undefined) {
        hdrs["Content-Type"] = "application/json";
      }
      if (options.idempotencyKey) {
        hdrs["Idempotency-Key"] = options.idempotencyKey;
      }

      const access = overrideBearer ?? tokens.getAccessToken();
      const guest = tokens.getGuestToken();

      if (options.sendBothAuthAndGuest) {
        if (access) hdrs["Authorization"] = `Bearer ${access}`;
        if (guest) hdrs["X-Guest-Token"] = guest;
      } else if (access) {
        hdrs["Authorization"] = `Bearer ${access}`;
      } else if (guest) {
        hdrs["X-Guest-Token"] = guest;
      }

      return hdrs;
    };

    if (useFixture) {
      fixtureState.simulateDegraded = useAppStore.getState().simulateDegradedReplay;
      const hdrs = buildHeaders();
      const res = await handleFixtureRequest(path, {
        method,
        body: options.body,
        headers: hdrs,
      });
      return res.data as T;
    }

    const executeFetch = async (overrideBearer?: string): Promise<Response> => {
      try {
        return await fetchFn(`${baseRoot}${path}`, {
          method,
          headers: buildHeaders(overrideBearer),
          body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
          signal: options.signal,
        });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          throw err;
        }
        throw new ApiClientError({
          status: 503,
          code: "SERVICE_UNAVAILABLE",
          message: err instanceof Error ? err.message : "Network request failed",
          details: [],
          requestId: null,
        });
      }
    };

    let response = await executeFetch();

    if (
      response.status === 401 &&
      !options.skipAuthRefresh &&
      tokens.getRefreshToken()
    ) {
      const nextAccess = await refreshAccessToken();
      if (nextAccess) {
        response = await executeFetch(nextAccess);
      }
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const reqIdHeader = response.headers.get("X-Request-Id");
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : null;

    let parsedBody: unknown = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      parsedBody = await response.json().catch(() => null);
    }

    if (!response.ok) {
      const envParsed = ErrorEnvelopeSchema.safeParse(parsedBody);
      if (envParsed.success) {
        throw new ApiClientError({
          status: response.status,
          code: envParsed.data.error.code,
          message: envParsed.data.error.message,
          details: envParsed.data.error.details,
          requestId: envParsed.data.error.request_id ?? reqIdHeader,
          retryAfterSeconds: Number.isFinite(retryAfterSeconds) ? retryAfterSeconds : null,
        });
      }

      throw new ApiClientError({
        status: response.status,
        code: response.status === 401 ? "UNAUTHORIZED" : "INTERNAL_ERROR",
        message: `HTTP ${response.status} error calling ${path}`,
        details: [],
        requestId: reqIdHeader,
        retryAfterSeconds: Number.isFinite(retryAfterSeconds) ? retryAfterSeconds : null,
      });
    }

    return parsedBody as T;
  }

  return { request };
}

export const apiClient = createApiClient();
