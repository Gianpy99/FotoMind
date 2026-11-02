import { useEffect, useState } from "react";
import type { CurrentUser, FotoMindClient } from "@fotomind/api-client";
import { LibraryView } from "./LibraryView";
import { SourcesView } from "./SourcesView";
import { errorMessage } from "./format";

export interface AppShellProps {
  client: FotoMindClient;
  /** Shown in the footer, e.g. "web" or "desktop". */
  surface: string;
}

type Section = "library" | "sources";

const SECTIONS: { id: Section | null; label: string }[] = [
  { id: "library", label: "Library" },
  { id: null, label: "Search" },
  { id: null, label: "Albums" },
  { id: null, label: "People" },
  { id: "sources", label: "Sources & jobs" },
  { id: null, label: "Backup" },
];

type UserState =
  { kind: "loading" } | { kind: "ready"; user: CurrentUser } | { kind: "error"; message: string };

export function AppShell({ client, surface }: AppShellProps) {
  const [userState, setUserState] = useState<UserState>({ kind: "loading" });
  const [section, setSection] = useState<Section>("library");

  useEffect(() => {
    let cancelled = false;
    client
      .me()
      .then((user) => !cancelled && setUserState({ kind: "ready", user }))
      .catch(
        (err: unknown) => !cancelled && setUserState({ kind: "error", message: errorMessage(err) }),
      );
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <div className="fm-shell">
      <header className="fm-header">
        <h1>FotoMind</h1>
        {userState.kind === "ready" && <span className="fm-user">{userState.user.username}</span>}
      </header>
      <nav className="fm-nav" aria-label="Sections">
        {SECTIONS.map(({ id, label }) =>
          id ? (
            <button
              key={label}
              type="button"
              aria-current={section === id ? "page" : undefined}
              onClick={() => setSection(id)}
            >
              {label}
            </button>
          ) : (
            <button key={label} type="button" disabled title="Coming in a later milestone">
              {label}
            </button>
          ),
        )}
      </nav>
      <main className="fm-main">
        {userState.kind === "error" ? (
          <p role="alert" className="fm-error">
            API unavailable: {userState.message}
          </p>
        ) : section === "library" ? (
          <LibraryView client={client} />
        ) : (
          <SourcesView client={client} />
        )}
      </main>
      <footer className="fm-footer">FotoMind {surface} · originals are never modified</footer>
    </div>
  );
}
