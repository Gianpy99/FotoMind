// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AssetSummary, FotoMindClient, Job, StorageRoot } from "@fotomind/api-client";
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
  last_scan_at: null,
  created_at: "2024-07-14T16:30:00Z",
  file_count: 2,
  missing_count: 0,
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
      metadata: {},
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
});
