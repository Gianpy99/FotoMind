import { describe, expect, it, vi } from "vitest";
import { ApiError, createClient } from "./index";

describe("createClient", () => {
  it("calls the versioned API relative to the base URL with credentials", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ username: "dev", groups: [] }), { status: 200 }),
    );
    const client = createClient("https://photos.example/", fetchMock as typeof fetch);

    await expect(client.me()).resolves.toEqual({ username: "dev", groups: [] });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://photos.example/api/v1/me",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("raises ApiError with the HTTP status", async () => {
    const fetchMock = vi.fn(async () => new Response("", { status: 401 }));
    const client = createClient("", fetchMock as typeof fetch);

    await expect(client.me()).rejects.toMatchObject(
      new ApiError(401, "/api/v1/me failed with HTTP 401"),
    );
  });
});
