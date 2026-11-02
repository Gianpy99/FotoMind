// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { FotoMindClient } from "@fotomind/api-client";
import { AppShell } from "./AppShell";

const client: FotoMindClient = {
  health: async () => ({ status: "ok", version: "0.1.0" }),
  me: async () => ({ username: "gianpaolo", groups: ["family"] }),
  systemStatus: async () => ({
    status: "ok",
    version: "0.1.0",
    environment: "test",
    database: { status: "ok", latency_ms: 1, server_version: "15.8", detail: null },
  }),
};

afterEach(cleanup);

describe("AppShell", () => {
  it("shows the portal user and database status", async () => {
    render(<AppShell client={client} surface="web" />);
    expect(await screen.findByText("gianpaolo")).toBeTruthy();
    expect(screen.getByText(/PostgreSQL 15\.8/)).toBeTruthy();
  });

  it("reports an unavailable API", async () => {
    const failing: FotoMindClient = { ...client, me: () => Promise.reject(new Error("HTTP 401")) };
    render(<AppShell client={failing} surface="web" />);
    expect((await screen.findByRole("alert")).textContent).toContain("HTTP 401");
  });
});
