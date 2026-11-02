import type { components } from "./schema";

type Schemas = components["schemas"];

export type HealthResponse = Schemas["HealthResponse"];
export type SystemStatus = Schemas["SystemStatusResponse"];
export type CurrentUser = Schemas["CurrentUser"];
export type AssetSummary = Schemas["AssetSummary"];
export type AssetDetail = Schemas["AssetDetail"];
export type AssetPage = Schemas["AssetPage"];
export type MediaFile = Schemas["MediaFileOut"];
export type StorageRoot = Schemas["StorageRootOut"];
export type Job = Schemas["JobOut"];
export type AssetType = AssetSummary["asset_type"];
export type Availability = AssetSummary["availability"];

export interface ListAssetsParams {
  limit?: number;
  cursor?: string | null;
  asset_type?: AssetType;
  availability?: Availability;
  storage_root_id?: string;
}

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
  listAssets(params?: ListAssetsParams): Promise<AssetPage>;
  getAsset(id: string): Promise<AssetDetail>;
  listRoots(): Promise<StorageRoot[]>;
  scanRoot(id: string): Promise<Job>;
  listJobs(limit?: number): Promise<Job[]>;
  cancelJob(id: string): Promise<Job>;
  /** Absolute (or origin-relative) URL for an API-relative path such as a thumbnail_url. */
  url(path: string): string;
}

/**
 * @param baseUrl "" for the web UI (same origin as the API), or an absolute URL for the
 *   desktop shell / local development against another host.
 */
export function createClient(baseUrl = "", fetchImpl: typeof fetch = fetch): FotoMindClient {
  const root = baseUrl.replace(/\/+$/, "");

  async function request<T>(method: "GET" | "POST", path: string): Promise<T> {
    // Portal auth is cookie/basic-auth based at the proxy, so send credentials.
    const resp = await fetchImpl(`${root}${path}`, {
      method,
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) {
      let detail = `${path} failed with HTTP ${resp.status}`;
      try {
        const body = (await resp.json()) as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        // Non-JSON error body: keep the generic message.
      }
      throw new ApiError(resp.status, detail);
    }
    return (await resp.json()) as T;
  }

  const get = <T>(path: string) => request<T>("GET", path);
  const post = <T>(path: string) => request<T>("POST", path);

  function query(params: object): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
    }
    const text = search.toString();
    return text ? `?${text}` : "";
  }

  return {
    health: () => get<HealthResponse>("/api/v1/health"),
    systemStatus: () => get<SystemStatus>("/api/v1/system/status"),
    me: () => get<CurrentUser>("/api/v1/me"),
    listAssets: (params = {}) => get<AssetPage>(`/api/v1/assets${query(params)}`),
    getAsset: (id) => get<AssetDetail>(`/api/v1/assets/${encodeURIComponent(id)}`),
    listRoots: () => get<StorageRoot[]>("/api/v1/storage-roots"),
    scanRoot: (id) => post<Job>(`/api/v1/storage-roots/${encodeURIComponent(id)}/scan`),
    listJobs: (limit = 20) => get<Job[]>(`/api/v1/jobs${query({ limit })}`),
    cancelJob: (id) => post<Job>(`/api/v1/jobs/${encodeURIComponent(id)}/cancel`),
    url: (path) => `${root}${path}`,
  };
}
