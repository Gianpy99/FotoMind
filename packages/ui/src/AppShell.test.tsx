// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Album, AssetSummary, FotoMindClient, Job, StorageRoot } from "@fotomind/api-client";
import { AppShell } from "./AppShell";

function asset(n: number, extra: Partial<AssetSummary> = {}): AssetSummary {
  return {
    id: `a${n}`,
    asset_type: "photo",
    display_name: `IMG_${n}.jpg`,
    sort_at: "2024-07-14T16:30:00Z",
    captured_at: "2024-07-14T16:30:00Z",
    width: 4000,
    height: 3000,
    duration_s: null,
    rating: 0,
    availability: "online",
    tags: [],
    thumbnail_url: `/api/v1/assets/a${n}/thumbnail?v=abc`,
    ...extra,
  };
}

const root: StorageRoot = {
  id: "r1",
  label: "DesktopImages",
  host: "pc",
  path: "C:\\Photos",
  volume_id: null,
  availability: "online",
  exclude_patterns: [],
  last_scan_at: null,
  created_at: "2024-07-14T16:30:00Z",
  file_count: 2,
  missing_count: 0,
};

const album: Album = {
  id: "al1",
  name: "Rome",
  description: null,
  cover_asset_id: "a1",
  cover_thumbnail_url: "/api/v1/assets/a1/thumbnail?v=abc",
  asset_count: 1,
  created_by: "gianpaolo",
  created_at: "2024-07-14T16:30:00Z",
  updated_at: "2024-07-14T16:30:00Z",
};

const queuedJob: Job = {
  id: "j1",
  job_type: "scan_root",
  status: "queued",
  host: "pc",
  storage_root_id: "r1",
  progress_done: 0,
  progress_total: null,
  message: null,
  error: null,
  result: {},
  attempts: 0,
  requested_by: "gianpaolo",
  created_at: "2024-07-14T16:30:00Z",
  started_at: null,
  heartbeat_at: null,
  finished_at: null,
};

function makeClient(overrides: Partial<FotoMindClient> = {}): FotoMindClient {
  return {
    health: async () => ({ status: "ok", version: "0.1.0" }),
    me: async () => ({ username: "gianpaolo", groups: ["family"] }),
    systemStatus: async () => ({
      status: "ok",
      version: "0.1.0",
      environment: "test",
      database: { status: "ok", latency_ms: 1, server_version: "15.8", detail: null },
    }),
    listAssets: async () => ({
      items: [asset(1), asset(2, { asset_type: "video", duration_s: 75 })],
      total: 2,
      next_cursor: null,
    }),
    getAsset: async (id) => ({
      ...asset(Number(id.slice(1))),
      camera_make: "Canon",
      camera_model: "EOS R6",
      lens_model: null,
      metadata: { f_number: 2.8, exposure_time: "1/250", iso: 400 },
      tags: ["family"],
      albums: [],
      files: [
        {
          id: "f1",
          storage_root_id: "r1",
          storage_root_label: "DesktopImages",
          relative_path: `2024/IMG_${id.slice(1)}.jpg`,
          role: "original",
          mime_type: "image/jpeg",
          size_bytes: 2_500_000,
          mtime: "2024-07-14T16:30:00Z",
          sha256: "0".repeat(64),
          availability: "online",
          backup_state: "unknown",
          last_seen_at: "2024-07-14T16:30:00Z",
        },
      ],
    }),
    listRoots: async () => [root],
    scanRoot: async () => queuedJob,
    listJobs: async () => [],
    cancelJob: async () => ({ ...queuedJob, status: "cancelled" }),
    updateRoot: async (_id, body) => ({ ...root, ...body }) as StorageRoot,
    facets: async () => ({
      cameras: [{ value: "EOS R6", count: 2 }],
      tags: [{ value: "family", count: 1 }],
      years: [{ value: "2024", count: 2 }],
      total: 2,
    }),
    updateAsset: async (id, body) => ({
      ...(await makeClient().getAsset(id)),
      ...(body.rating != null ? { rating: body.rating } : {}),
      ...(body.tags ? { tags: body.tags } : {}),
    }),
    bulkUpdateAssets: async (body) => ({ updated: body.asset_ids.length }),
    listAlbums: async () => [album],
    getAlbum: async () => album,
    createAlbum: async (body) => ({ ...album, id: "al2", name: body.name }),
    updateAlbum: async (_id, body) => ({ ...album, name: body.name ?? album.name }),
    deleteAlbum: async () => undefined,
    addToAlbum: async () => album,
    removeFromAlbum: async () => ({ ...album, asset_count: 0 }),
    url: (path) => path,
    ...overrides,
  };
}

afterEach(cleanup);

describe("AppShell", () => {
  it("shows the portal user and the library grid", async () => {
    render(<AppShell client={makeClient()} surface="web" />);
    expect(await screen.findByText("gianpaolo")).toBeTruthy();
    expect(await screen.findByAltText("IMG_1.jpg")).toBeTruthy();
    expect(screen.getByText("2 items")).toBeTruthy();
    expect(screen.getByText(/1:15/)).toBeTruthy();
  });

  it("reports an unavailable API", async () => {
    const failing = makeClient({ me: () => Promise.reject(new Error("HTTP 401")) });
    render(<AppShell client={failing} surface="web" />);
    expect((await screen.findByRole("alert")).textContent).toContain("HTTP 401");
  });

  it("opens the viewer with file details and navigates with the keyboard", async () => {
    render(<AppShell client={makeClient()} surface="web" />);
    fireEvent.click(await screen.findByTitle("IMG_1.jpg"));
    expect(await screen.findByText("Canon EOS R6")).toBeTruthy();
    expect(screen.getByText("DesktopImages/2024/IMG_1.jpg")).toBeTruthy();

    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(await screen.findByText("DesktopImages/2024/IMG_2.jpg")).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows an empty-library hint", async () => {
    const empty = makeClient({
      listAssets: async () => ({ items: [], total: 0, next_cursor: null }),
    });
    render(<AppShell client={empty} surface="web" />);
    expect(await screen.findByText(/Nothing catalogued yet/)).toBeTruthy();
  });

  it("lists sources, queues a scan and shows system status", async () => {
    const scanRoot = vi.fn(async () => queuedJob);
    const listJobs = vi
      .fn<FotoMindClient["listJobs"]>()
      .mockResolvedValueOnce([])
      .mockResolvedValue([queuedJob]);
    render(<AppShell client={makeClient({ scanRoot, listJobs })} surface="web" />);
    fireEvent.click(await screen.findByRole("button", { name: "Sources & jobs" }));

    fireEvent.click(await screen.findByRole("button", { name: "Scan now" }));
    expect(scanRoot).toHaveBeenCalledWith("r1");
    expect(await screen.findByRole("button", { name: "Scanning…" })).toBeTruthy();
    expect(screen.getByText("queued")).toBeTruthy();
    expect(await screen.findByText(/PostgreSQL 15\.8/)).toBeTruthy();
  });

  it("searches with debounce and filters by facets", async () => {
    const listAssets = vi.fn(makeClient().listAssets);
    render(<AppShell client={makeClient({ listAssets })} surface="web" />);
    await screen.findByAltText("IMG_1.jpg");

    fireEvent.change(screen.getByRole("searchbox", { name: "Search" }), {
      target: { value: "rome" },
    });
    await waitFor(() =>
      expect(listAssets).toHaveBeenLastCalledWith(expect.objectContaining({ q: "rome" })),
    );

    fireEvent.change(await screen.findByRole("combobox", { name: "Year" }), {
      target: { value: "2024" },
    });
    await waitFor(() =>
      expect(listAssets).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "rome", date_from: "2024-01-01", date_to: "2024-12-31" }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() =>
      expect(listAssets).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ q: expect.anything() }),
      ),
    );
  });

  it("rates and tags in the viewer", async () => {
    const updateAsset = vi.fn(makeClient().updateAsset);
    render(<AppShell client={makeClient({ updateAsset })} surface="web" />);
    fireEvent.click(await screen.findByTitle("IMG_1.jpg"));
    expect(await screen.findByText("f/2.8 · 1/250 s · ISO 400")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "4 stars" }));
    expect(updateAsset).toHaveBeenCalledWith("a1", { rating: 4 });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "4 stars" }).getAttribute("aria-pressed")).toBe(
        "true",
      ),
    );

    fireEvent.keyDown(window, { key: "2" });
    expect(updateAsset).toHaveBeenLastCalledWith("a1", { rating: 2 });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "2 stars" }).getAttribute("aria-pressed")).toBe(
        "true",
      ),
    );

    fireEvent.change(screen.getByRole("combobox", { name: "New tag" }), {
      target: { value: "beach" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(updateAsset).toHaveBeenLastCalledWith("a1", { tags: ["family", "beach"] });
    expect(await screen.findByRole("button", { name: "Remove tag beach" })).toBeTruthy();
  });

  it("selects several items and applies bulk actions", async () => {
    const bulkUpdateAssets = vi.fn(makeClient().bulkUpdateAssets);
    const createAlbum = vi.fn(makeClient().createAlbum);
    render(<AppShell client={makeClient({ bulkUpdateAssets, createAlbum })} surface="web" />);
    fireEvent.click(await screen.findByRole("checkbox", { name: "Select IMG_1.jpg" }));
    // While selecting, clicking a tile toggles it instead of opening the viewer.
    fireEvent.click(screen.getByTitle("IMG_2.jpg"));
    const bar = screen.getByRole("toolbar", { name: "Selection" });
    expect(within(bar).getByText("2 selected")).toBeTruthy();

    fireEvent.change(within(bar).getByRole("combobox", { name: "Rate selection" }), {
      target: { value: "5" },
    });
    expect(bulkUpdateAssets).toHaveBeenCalledWith({ asset_ids: ["a1", "a2"], rating: 5 });
    expect(await screen.findByText(/Rated 2 item\(s\) 5★/)).toBeTruthy();

    fireEvent.change(within(bar).getByRole("combobox", { name: "Album for selection" }), {
      target: { value: "Summer" },
    });
    fireEvent.click(within(bar).getByRole("button", { name: "Add to album" }));
    expect(createAlbum).toHaveBeenCalledWith({ name: "Summer", asset_ids: ["a1", "a2"] });
    expect(await screen.findByText(/Created album “Summer”/)).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("lists albums and opens one", async () => {
    const listAssets = vi.fn(makeClient().listAssets);
    render(<AppShell client={makeClient({ listAssets })} surface="web" />);
    fireEvent.click(await screen.findByRole("button", { name: "Albums" }));
    fireEvent.click(await screen.findByRole("button", { name: /Rome/ }));
    expect(await screen.findByRole("heading", { name: "Rome" })).toBeTruthy();
    await waitFor(() =>
      expect(listAssets).toHaveBeenLastCalledWith(expect.objectContaining({ album_id: "al1" })),
    );
    fireEvent.click(screen.getByRole("button", { name: "← Albums" }));
    expect(await screen.findByRole("button", { name: /Rome/ })).toBeTruthy();
  });

  it("edits a root's exclusion rules", async () => {
    const updateRoot = vi.fn(makeClient().updateRoot);
    render(<AppShell client={makeClient({ updateRoot })} surface="web" />);
    fireEvent.click(await screen.findByRole("button", { name: "Sources & jobs" }));
    fireEvent.click(await screen.findByRole("button", { name: /None/ }));
    fireEvent.change(screen.getByRole("textbox", { name: /Skip these folders/ }), {
      target: { value: "@eaDir\n\n Private/2019* " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save exclusions" }));
    await waitFor(() =>
      expect(updateRoot).toHaveBeenCalledWith("r1", {
        exclude_patterns: ["@eaDir", "Private/2019*"],
      }),
    );
  });
});
