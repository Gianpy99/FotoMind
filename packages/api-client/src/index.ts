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
export type Album = Schemas["AlbumOut"];
export type AlbumRef = Schemas["AlbumRef"];
export type LibraryFacets = Schemas["LibraryFacets"];
export type FacetValue = Schemas["FacetValue"];
/** Request bodies: fields with a server-side default may be omitted. */
type WithOptional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type AssetUpdate = Schemas["AssetUpdate"];
export type BulkAssetUpdate = WithOptional<Schemas["BulkAssetUpdate"], "add_tags" | "remove_tags">;
export type BulkResult = Schemas["BulkResult"];
export type AlbumCreate = WithOptional<Schemas["AlbumCreate"], "asset_ids">;
export type AlbumUpdate = Schemas["AlbumUpdate"];
export type StorageRootUpdate = Schemas["StorageRootUpdate"];
export type AssetType = AssetSummary["asset_type"];
export type Availability = AssetSummary["availability"];

export interface ListAssetsParams {
  limit?: number;
  cursor?: string | null;
  asset_type?: AssetType;
  availability?: Availability;
  storage_root_id?: string;
  /** Free text: every term must match the name, camera, lens, file path or a tag. */
  q?: string;
  min_rating?: number;
  /** Repeatable: assets must carry every tag. */
  tag?: string[];
  album_id?: string;
  camera?: string;
  /** Inclusive UTC days, YYYY-MM-DD. */
  date_from?: string;
  date_to?: string;
  sort?: "newest" | "oldest";
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
  updateRoot(id: string, body: StorageRootUpdate): Promise<StorageRoot>;
  facets(): Promise<LibraryFacets>;
  updateAsset(id: string, body: AssetUpdate): Promise<AssetDetail>;
  bulkUpdateAssets(body: BulkAssetUpdate): Promise<BulkResult>;
  listAlbums(): Promise<Album[]>;
  getAlbum(id: string): Promise<Album>;
  createAlbum(body: AlbumCreate): Promise<Album>;
  updateAlbum(id: string, body: AlbumUpdate): Promise<Album>;
  deleteAlbum(id: string): Promise<void>;
  addToAlbum(id: string, assetIds: string[]): Promise<Album>;
  removeFromAlbum(id: string, assetIds: string[]): Promise<Album>;
  /** Absolute (or origin-relative) URL for an API-relative path such as a thumbnail_url. */
  url(path: string): string;
}

/**
 * @param baseUrl "" for the web UI (same origin as the API), or an absolute URL for the
 *   desktop shell / local development against another host.
 */
export function createClient(baseUrl = "", fetchImpl: typeof fetch = fetch): FotoMindClient {
  const root = baseUrl.replace(/\/+$/, "");

  async function request<T>(
    method: "GET" | "POST" | "PATCH" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    // Portal auth is cookie/basic-auth based at the proxy, so send credentials.
    const resp = await fetchImpl(`${root}${path}`, {
      method,
      credentials: "include",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
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
    if (resp.status === 204) return undefined as T;
    return (await resp.json()) as T;
  }

  const get = <T>(path: string) => request<T>("GET", path);
  const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body);
  const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
  const id = encodeURIComponent;

  function query(params: object): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      for (const item of Array.isArray(value) ? value : [value]) {
        if (item !== undefined && item !== null && item !== "") search.append(key, String(item));
      }
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
    cancelJob: (jobId) => post<Job>(`/api/v1/jobs/${id(jobId)}/cancel`),
    updateRoot: (rootId, body) => patch<StorageRoot>(`/api/v1/storage-roots/${id(rootId)}`, body),
    facets: () => get<LibraryFacets>("/api/v1/library/facets"),
    updateAsset: (assetId, body) => patch<AssetDetail>(`/api/v1/assets/${id(assetId)}`, body),
    bulkUpdateAssets: (body) => post<BulkResult>("/api/v1/assets/bulk", body),
    listAlbums: () => get<Album[]>("/api/v1/albums"),
    getAlbum: (albumId) => get<Album>(`/api/v1/albums/${id(albumId)}`),
    createAlbum: (body) => post<Album>("/api/v1/albums", body),
    updateAlbum: (albumId, body) => patch<Album>(`/api/v1/albums/${id(albumId)}`, body),
    deleteAlbum: (albumId) => request<void>("DELETE", `/api/v1/albums/${id(albumId)}`),
    addToAlbum: (albumId, assetIds) =>
      post<Album>(`/api/v1/albums/${id(albumId)}/assets`, { asset_ids: assetIds }),
    removeFromAlbum: (albumId, assetIds) =>
      post<Album>(`/api/v1/albums/${id(albumId)}/assets/remove`, { asset_ids: assetIds }),
    url: (path) => `${root}${path}`,
  };
}
