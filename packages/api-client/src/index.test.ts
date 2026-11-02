import { describe, expect, it, vi } from "vitest";
import { ApiError, createClient } from "./index";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("createClient", () => {
  it("calls the versioned API relative to the base URL with credentials", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ username: "dev", groups: [] }));
    const client = createClient("https://photos.example/", fetchMock as typeof fetch);

    await expect(client.me()).resolves.toEqual({ username: "dev", groups: [] });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://photos.example/api/v1/me",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
  });

  it("raises ApiError with the HTTP status", async () => {
    const fetchMock = vi.fn(async () => new Response("", { status: 401 }));
    const client = createClient("", fetchMock as typeof fetch);

    await expect(client.me()).rejects.toMatchObject(
      new ApiError(401, "/api/v1/me failed with HTTP 401"),
    );
  });

  it("uses the API error detail when present", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ detail: "Root is offline" }, 409));
    const client = createClient("", fetchMock as typeof fetch);

    await expect(client.scanRoot("r1")).rejects.toMatchObject({
      status: 409,
      message: "Root is offline",
    });
  });

  it("encodes list filters and skips empty values", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ items: [], total: 0, next_cursor: null }));
    const client = createClient("", fetchMock as typeof fetch);

    await client.listAssets({
      limit: 50,
      cursor: "a+b/c=",
      asset_type: "video",
      availability: undefined,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/assets?limit=50&cursor=a%2Bb%2Fc%3D&asset_type=video",
      expect.anything(),
    );
  });

  it("POSTs scan and cancel requests", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({}));
    const client = createClient("http://api", fetchMock as typeof fetch);

    await client.scanRoot("r1");
    await client.cancelJob("j1");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://api/api/v1/storage-roots/r1/scan",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://api/api/v1/jobs/j1/cancel",
      expect.objectContaining({ method: "POST" }),
    );
    expect(client.url("/api/v1/assets/x/thumbnail")).toBe("http://api/api/v1/assets/x/thumbnail");
  });

  it("repeats array filters", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ items: [], total: 0, next_cursor: null }));
    const client = createClient("", fetchMock as typeof fetch);

    await client.listAssets({ q: "rome 2023", tag: ["family", "trip"], sort: "oldest" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/assets?q=rome+2023&tag=family&tag=trip&sort=oldest",
      expect.anything(),
    );
  });

  it("sends JSON bodies and handles 204 responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "a1", rating: 4 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createClient("", fetchMock as unknown as typeof fetch);

    await expect(client.updateAsset("a1", { rating: 4 })).resolves.toMatchObject({ rating: 4 });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/assets/a1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ rating: 4 }),
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
    await expect(client.deleteAlbum("al1")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/albums/al1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
