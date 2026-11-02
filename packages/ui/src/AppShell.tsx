import { useEffect, useState } from "react";
import type { CurrentUser, FotoMindClient, SystemStatus } from "@fotomind/api-client";

export interface AppShellProps {
  client: FotoMindClient;
  /** Shown in the footer, e.g. "web" or "desktop". */
  surface: string;
}

const SECTIONS = ["Library", "Search", "Albums", "People", "Jobs", "Backup"] as const;

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; user: CurrentUser; status: SystemStatus }
  | { kind: "error"; message: string };

export function AppShell({ client, surface }: AppShellProps) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([client.me(), client.systemStatus()])
      .then(([user, status]) => {
        if (!cancelled) setState({ kind: "ready", user, status });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <div className="fm-shell">
      <header className="fm-header">
        <h1>FotoMind</h1>
        {state.kind === "ready" && <span className="fm-user">{state.user.username}</span>}
      </header>
      <nav className="fm-nav" aria-label="Sections">
        {SECTIONS.map((s) => (
          <button key={s} type="button" disabled title="Coming in a later milestone">
            {s}
          </button>
        ))}
      </nav>
      <main className="fm-main">
        <section aria-labelledby="fm-status-title" className="fm-card">
          <h2 id="fm-status-title">System status</h2>
          {state.kind === "loading" && <p>Connecting to the FotoMind API…</p>}
          {state.kind === "error" && (
            <p role="alert" className="fm-error">
              API unavailable: {state.message}
            </p>
          )}
          {state.kind === "ready" && (
            <dl>
              <dt>API</dt>
              <dd>
                {state.status.status} (v{state.status.version}, {state.status.environment})
              </dd>
              <dt>Database</dt>
              <dd>
                {state.status.database.status}
                {state.status.database.server_version &&
                  ` — PostgreSQL ${state.status.database.server_version}`}
              </dd>
            </dl>
          )}
        </section>
      </main>
      <footer className="fm-footer">FotoMind {surface} · originals are never modified</footer>
    </div>
  );
}
