import type { components } from "./schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type SystemStatus = components["schemas"]["SystemStatusResponse"];
export type CurrentUser = components["schemas"]["CurrentUser"];

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface FotoMindClient {
  health(): Promise<HealthResponse>;
  systemStatus(): Promise<SystemStatus>;
  me(): Promise<CurrentUser>;
}

/**
 * @param baseUrl "" for the web UI (same origin as the API), or an absolute URL for the
 *   desktop shell / local development against another host.
 */
export function createClient(baseUrl = "", fetchImpl: typeof fetch = fetch): FotoMindClient {
  const root = baseUrl.replace(/\/+$/, "");

  async function get<T>(path: string): Promise<T> {
    // Portal auth is cookie/basic-auth based at the proxy, so send credentials.
    const resp = await fetchImpl(`${root}${path}`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) {
      throw new ApiError(resp.status, `${path} failed with HTTP ${resp.status}`);
    }
    return (await resp.json()) as T;
  }

  return {
    health: () => get<HealthResponse>("/api/v1/health"),
    systemStatus: () => get<SystemStatus>("/api/v1/system/status"),
    me: () => get<CurrentUser>("/api/v1/me"),
  };
}
