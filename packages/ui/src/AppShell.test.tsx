// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  Album,
  AssetSummary,
  FotoMindClient,
  Job,
  Place,
  StorageRoot,
} from "@fotomind/api-client";
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
    title: null,
    location: null,
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

const rome: Place = {
  name: "Rome",
  label: "Rome, Italy",
  kind: "city",
  country_code: "IT",
  latitude: 41.89,
  longitude: 12.48,
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
      description: null,
      edited_fields: [],
      file_values: {},
      location_near: null,
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
      types: [
        { value: "photo", count: 1 },
        { value: "video", count: 1 },
      ],
      total: 2,
      located: 1,
    }),
    searchPlaces: async () => [rome],
    tagPlaces: async () => ({
      suggestions: [{ tag: "rome", count: 3, candidates: [rome] }],
      decided: [],
      attribution: "Place names © GeoNames (CC BY 4.0)",
    }),
    decideTagPlace: async (body) => ({
      suggestions: [],
      decided: [
        {
          tag: body.tag,
          count: 3,
          status: "confirmed",
          label: rome.label,
          kind: "city",
          latitude: rome.latitude,
          longitude: rome.longitude,
        },
      ],
      attribution: "Place names © GeoNames (CC BY 4.0)",
    }),
    mapAssets: async () => ({
      items: [
        {
          id: "a1",
          asset_type: "photo",
          display_name: "IMG_1.jpg",
          thumbnail_url: "/api/v1/assets/a1/thumbnail?v=abc",
          sort_at: "2024-07-14T16:30:00Z",
          latitude: 41.89,
          longitude: 12.48,
          source: "file",
        },
      ],
      truncated: false,
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

afterEach(() => {
  cleanup();
  localStorage.removeItem("fotomind.groupBy");
});

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

  it("inspects on click, opens the viewer on a second click and navigates", async () => {
    render(<AppShell client={makeClient()} surface="web" />);
    fireEvent.click(await screen.findByTitle("IMG_1.jpg"));
    expect(await screen.findByText("Canon EOS R6")).toBeTruthy();
    expect(screen.getByText("DesktopImages/2024/IMG_1.jpg")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();

    // Arrow keys move the inspected item in the grid.
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(await screen.findByText("DesktopImages/2024/IMG_2.jpg")).toBeTruthy();
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(await screen.findByText("DesktopImages/2024/IMG_1.jpg")).toBeTruthy();

    fireEvent.click(screen.getByAltText("IMG_1.jpg"));
    const dialog = await screen.findByRole("dialog", { name: "IMG_1.jpg" });
    expect(await within(dialog).findByText("Canon EOS R6")).toBeTruthy();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(await screen.findByRole("dialog", { name: "IMG_2.jpg" })).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    // The last viewed item stays inspected.
    expect(await screen.findByText("DesktopImages/2024/IMG_2.jpg")).toBeTruthy();
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

    fireEvent.click(screen.getByRole("button", { name: "Filter" }));
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

  it("groups by day or week and selects a whole section, loading the rest of it", async () => {
    const listAssets = vi.fn<FotoMindClient["listAssets"]>(async (params) =>
      params?.cursor
        ? {
            items: [asset(3), asset(4, { sort_at: "2024-06-01T10:00:00Z" })],
            total: 4,
            next_cursor: null,
          }
        : { items: [asset(1), asset(2)], total: 4, next_cursor: "c2" },
    );
    render(<AppShell client={makeClient({ listAssets })} surface="web" />);
    await screen.findByTitle("IMG_1.jpg");

    fireEvent.change(screen.getByRole("combobox", { name: "Group by" }), {
      target: { value: "week" },
    });
    expect(screen.getByRole("heading", { level: 3, name: /2024/ })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 4, name: /2024/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^CW 28 · / })).toBeTruthy();
    expect(localStorage.getItem("fotomind.groupBy")).toBe("week");
    fireEvent.change(screen.getByRole("combobox", { name: "Group by" }), {
      target: { value: "day" },
    });
    const sectionSelects = () => screen.getAllByRole("checkbox", { name: /^Select all in / });
    // Year › month › day.
    expect(sectionSelects()).toHaveLength(3);

    // The only loaded day may continue on the next page: selecting it pages in the rest.
    fireEvent.click(sectionSelects()[2]!);
    const bar = await screen.findByRole("toolbar", { name: "Selection" });
    expect(await within(bar).findByText("3 selected")).toBeTruthy();
    expect(listAssets).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: "c2" }));
    // Now also a June month and day.
    expect(sectionSelects()).toHaveLength(5);

    // The whole year, then ticked again to clear it.
    fireEvent.click(sectionSelects()[0]!);
    expect(await within(bar).findByText("4 selected")).toBeTruthy();
    fireEvent.click(sectionSelects()[0]!);
    expect(screen.queryByRole("toolbar", { name: "Selection" })).toBeNull();

    // Collapsing the year hides everything under it.
    fireEvent.click(screen.getByRole("button", { name: "2024", expanded: true }));
    expect(sectionSelects()).toHaveLength(1);
    expect(screen.queryByTitle("IMG_1.jpg")).toBeNull();
  });

  it("edits info on a selection: shifts the date and sets a place", async () => {
    const bulkUpdateAssets = vi.fn(makeClient().bulkUpdateAssets);
    render(<AppShell client={makeClient({ bulkUpdateAssets })} surface="web" />);
    fireEvent.click(await screen.findByRole("checkbox", { name: "Select IMG_1.jpg" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select IMG_2.jpg" }));
    fireEvent.click(screen.getByRole("button", { name: /Edit info/ }));
    const dialog = screen.getByRole("dialog", { name: "Edit info" });

    // Nothing ticked yet: the editor refuses to submit.
    fireEvent.click(within(dialog).getByRole("button", { name: "Apply to 2 items" }));
    expect(await within(dialog).findByText("Tick at least one thing to change.")).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Date taken" }));
    fireEvent.change(within(dialog).getByRole("spinbutton", { name: "Shift hours" }), {
      target: { value: "2" },
    });
    fireEvent.change(within(dialog).getByRole("combobox", { name: "Shift direction" }), {
      target: { value: "-1" },
    });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Location" }));
    fireEvent.change(within(dialog).getByRole("searchbox", { name: "Search places" }), {
      target: { value: "Rome" },
    });
    fireEvent.click(await within(dialog).findByRole("button", { name: /Rome, Italy/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Apply to 2 items" }));

    await waitFor(() =>
      expect(bulkUpdateAssets).toHaveBeenCalledWith({
        asset_ids: ["a1", "a2"],
        metadata: {
          shift_seconds: -7200,
          location: { latitude: 41.89, longitude: 12.48, label: "Rome, Italy" },
        },
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("shows the location in the inspector and opens the map from it", async () => {
    const located = makeClient();
    const getAsset: FotoMindClient["getAsset"] = async (id) => ({
      ...(await located.getAsset(id)),
      location: { latitude: 41.89, longitude: 12.48, source: "file", label: null, tag: null },
      location_near: "Rome, Italy",
      edited_fields: ["captured_at"],
    });
    render(<AppShell client={makeClient({ getAsset })} surface="web" />);
    fireEvent.click(await screen.findByTitle("IMG_1.jpg"));
    const inspector = await screen.findByRole("complementary", { name: "Details" });
    expect(await within(inspector).findByText(/Near Rome, Italy/)).toBeTruthy();
    expect(within(inspector).getByText("GPS")).toBeTruthy();
    expect(within(inspector).getAllByText("edited").length).toBe(1);
    fireEvent.click(within(inspector).getByRole("button", { name: "Show on map" }));
    expect(await screen.findByRole("heading", { name: "Map" })).toBeTruthy();
  });

  it("shows the map and confirms a place suggested from a tag", async () => {
    const decideTagPlace = vi.fn(makeClient().decideTagPlace);
    const mapAssets = vi.fn(makeClient().mapAssets);
    render(<AppShell client={makeClient({ decideTagPlace, mapAssets })} surface="web" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Map/ }));
    expect(await screen.findByRole("heading", { name: "Map" })).toBeTruthy();
    expect(screen.getByRole("application", { name: "Photo map" })).toBeTruthy();
    await waitFor(() => expect(mapAssets).toHaveBeenCalled());

    const suggestions = await screen.findByRole("list", { name: "Suggested places" });
    expect(within(suggestions).getByText("Rome, Italy")).toBeTruthy();
    fireEvent.click(within(suggestions).getByRole("button", { name: "Confirm rome as a place" }));
    await waitFor(() =>
      expect(decideTagPlace).toHaveBeenCalledWith({
        tag: "rome",
        status: "confirmed",
        place: {
          label: "Rome, Italy",
          kind: "city",
          latitude: 41.89,
          longitude: 12.48,
        },
      }),
    );
    const confirmed = await screen.findByRole("list", { name: "Confirmed places" });
    expect(within(confirmed).getByText("rome")).toBeTruthy();
  });

  it("lists albums and opens one", async () => {
    const listAssets = vi.fn(makeClient().listAssets);
    render(<AppShell client={makeClient({ listAssets })} surface="web" />);
    fireEvent.click(await screen.findByRole("button", { name: "Albums" }));
    const main = screen.getByRole("main");
    fireEvent.click(await within(main).findByRole("button", { name: /Rome/ }));
    expect(await screen.findByRole("heading", { name: "Rome" })).toBeTruthy();
    await waitFor(() =>
      expect(listAssets).toHaveBeenLastCalledWith(expect.objectContaining({ album_id: "al1" })),
    );
    fireEvent.click(screen.getByRole("button", { name: "All albums" }));
    expect(await within(main).findByRole("button", { name: /Rome/ })).toBeTruthy();

    // Collections in the sidebar open an album directly.
    const nav = screen.getByRole("navigation", { name: "Sections" });
    fireEvent.click(within(nav).getByRole("button", { name: "Rome" }));
    expect(await screen.findByRole("heading", { name: "Rome" })).toBeTruthy();
  });

  it("filters by media type from the sidebar and shows counts in the status bar", async () => {
    const listAssets = vi.fn(makeClient().listAssets);
    render(<AppShell client={makeClient({ listAssets })} surface="web" />);
    expect(await screen.findByText("2 items (1 photo, 1 video)")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Videos" }));
    expect(await screen.findByRole("heading", { name: "Videos" })).toBeTruthy();
    await waitFor(() =>
      expect(listAssets).toHaveBeenLastCalledWith(expect.objectContaining({ asset_type: "video" })),
    );
  });

  it("toggles the theme and focuses search with Ctrl+K", async () => {
    render(<AppShell client={makeClient()} surface="web" />);
    await screen.findByAltText("IMG_1.jpg");
    expect(document.documentElement.dataset.theme).toBe("dark");
    fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: "Switch to dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(document.activeElement).toBe(screen.getByRole("searchbox", { name: "Search" }));
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
