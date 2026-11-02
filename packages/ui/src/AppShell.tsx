import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import {
  Aperture,
  Clapperboard,
  Film,
  Folder,
  FolderSync,
  HardDrive,
  Image as ImageIcon,
  Images,
  Library,
  Moon,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Users,
  BookImage,
  type LucideProps,
} from "lucide-react";
import type { Album, CurrentUser, FotoMindClient, LibraryFacets } from "@fotomind/api-client";
import { AlbumsView } from "./AlbumsView";
import { LibraryView } from "./LibraryView";
import { SourcesView } from "./SourcesView";
import { errorMessage, plural } from "./format";
import { useTheme } from "./theme";

export interface AppShellProps {
  client: FotoMindClient;
  /** Shown in the status bar, e.g. "web" or "desktop". */
  surface: string;
}

type MediaFilter = "all" | "photo" | "video";

type View =
  | { kind: "library"; type: MediaFilter }
  | { kind: "albums"; albumId: string | null }
  | { kind: "sources" };

type Icon = ComponentType<LucideProps>;

const WORKSPACES: { label: string; icon: Icon; ready: boolean }[] = [
  { label: "Library", icon: Library, ready: true },
  { label: "Develop", icon: SlidersHorizontal, ready: false },
  { label: "AI Studio", icon: Sparkles, ready: false },
  { label: "Media", icon: Clapperboard, ready: false },
];

const MEDIA_TITLES: Record<MediaFilter, string> = {
  all: "All media",
  photo: "Photos",
  video: "Videos",
};

const SEARCH_DEBOUNCE_MS = 300;

type UserState =
  { kind: "loading" } | { kind: "ready"; user: CurrentUser } | { kind: "error"; message: string };

interface NavItemProps {
  icon: Icon;
  label: string;
  count?: number | null;
  active?: boolean;
  disabled?: boolean;
  hint?: string;
  onClick?(): void;
}

function NavItem({ icon: ItemIcon, label, count, active, disabled, hint, onClick }: NavItemProps) {
  return (
    <li>
      <button
        type="button"
        className="fm-nav-item"
        aria-current={active ? "page" : undefined}
        disabled={disabled}
        title={hint ?? label}
        onClick={onClick}
      >
        <ItemIcon aria-hidden="true" />
        <span className="fm-nav-label">{label}</span>
        {count != null && (
          <span className="fm-nav-count fm-num" aria-hidden="true">
            {count.toLocaleString()}
          </span>
        )}
      </button>
    </li>
  );
}

function NavSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="fm-nav-section">
      <div className="fm-nav-heading">
        <span>{title}</span>
        {action}
      </div>
      <ul>{children}</ul>
    </div>
  );
}

export function AppShell({ client, surface }: AppShellProps) {
  const [userState, setUserState] = useState<UserState>({ kind: "loading" });
  const [theme, toggleTheme] = useTheme();
  const [view, setView] = useState<View>({ kind: "library", type: "all" });
  const [searchText, setSearchText] = useState("");
  const [query, setQuery] = useState("");
  const [facets, setFacets] = useState<LibraryFacets | null>(null);
  const [albums, setAlbums] = useState<Album[] | null>(null);
  const [catalogVersion, setCatalogVersion] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const searchTimer = useRef<number | undefined>(undefined);

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

  useEffect(() => {
    let cancelled = false;
    client
      .facets()
      .then((f) => !cancelled && setFacets(f))
      .catch(() => undefined);
    client
      .listAlbums()
      .then((a) => !cancelled && setAlbums(a))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [client, catalogVersion]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(searchTimer.current);
    };
  }, []);

  const catalogChanged = useCallback(() => setCatalogVersion((n) => n + 1), []);

  const clearSearch = useCallback(() => {
    window.clearTimeout(searchTimer.current);
    setSearchText("");
    setQuery("");
  }, []);

  function changeSearch(text: string) {
    setSearchText(text);
    // Search applies to a library grid; jump to "All media" from pages without one.
    if (view.kind === "sources" || (view.kind === "albums" && view.albumId === null)) {
      setView({ kind: "library", type: "all" });
    }
    window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(() => setQuery(text.trim()), SEARCH_DEBOUNCE_MS);
  }

  const typeCount = (type: string) => facets?.types?.find((t) => t.value === type)?.count ?? 0;
  const isMedia = (type: MediaFilter) => view.kind === "library" && view.type === type;
  const user = userState.kind === "ready" ? userState.user : null;

  let content: ReactNode;
  if (userState.kind === "error") {
    content = (
      <div className="fm-page">
        <p role="alert" className="fm-error">
          API unavailable: {userState.message}
        </p>
      </div>
    );
  } else if (view.kind === "library") {
    content = (
      <LibraryView
        key={`library-${view.type}`}
        client={client}
        heading={<h2>{MEDIA_TITLES[view.type]}</h2>}
        assetType={view.type}
        query={query}
        facets={facets}
        albums={albums ?? []}
        onClearSearch={clearSearch}
        onCatalogChanged={catalogChanged}
      />
    );
  } else if (view.kind === "albums") {
    content = (
      <AlbumsView
        client={client}
        albums={albums}
        albumId={view.albumId}
        onOpen={(albumId) => setView({ kind: "albums", albumId })}
        onChanged={catalogChanged}
        library={{ query, facets, onClearSearch: clearSearch }}
      />
    );
  } else {
    content = <SourcesView client={client} />;
  }

  return (
    <div className="fm-app">
      <header className="fm-topbar">
        <div className="fm-brand">
          <span className="fm-logo" aria-hidden="true">
            <Aperture />
          </span>
          <h1>FotoMind</h1>
        </div>

        <nav className="fm-workspaces" aria-label="Workspaces">
          {WORKSPACES.map(({ label, icon: WorkspaceIcon, ready }) => (
            <button
              key={label}
              type="button"
              className="fm-workspace"
              aria-current={ready ? "page" : undefined}
              disabled={!ready}
              title={ready ? label : `${label}: coming in a later milestone`}
              onClick={() => setView({ kind: "library", type: "all" })}
            >
              <WorkspaceIcon aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="fm-search" role="search">
          <Search aria-hidden="true" />
          <input
            ref={searchRef}
            type="search"
            aria-label="Search"
            placeholder="Search names, folders, cameras, tags…"
            value={searchText}
            onChange={(e) => changeSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && clearSearch()}
          />
          <kbd aria-hidden="true">Ctrl K</kbd>
        </div>

        <div className="fm-topbar-actions">
          <button
            type="button"
            className="fm-icon-btn"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Light theme" : "Dark theme"}
          >
            {theme === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
          </button>
          {user && (
            <span className="fm-user" title="Signed in through the Family Portal">
              <span className="fm-avatar" aria-hidden="true">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <span>{user.username}</span>
            </span>
          )}
        </div>
      </header>

      <nav className="fm-sidebar" aria-label="Sections">
        <ul className="fm-nav-top">
          <NavItem
            icon={Images}
            label="All media"
            count={facets?.total}
            active={isMedia("all")}
            onClick={() => setView({ kind: "library", type: "all" })}
          />
          <NavItem
            icon={ImageIcon}
            label="Photos"
            count={facets ? typeCount("photo") : null}
            active={isMedia("photo")}
            onClick={() => setView({ kind: "library", type: "photo" })}
          />
          <NavItem
            icon={Film}
            label="Videos"
            count={facets ? typeCount("video") : null}
            active={isMedia("video")}
            onClick={() => setView({ kind: "library", type: "video" })}
          />
        </ul>

        <NavSection title="Library">
          <NavItem
            icon={BookImage}
            label="Albums"
            count={albums?.length}
            active={view.kind === "albums" && view.albumId === null}
            onClick={() => setView({ kind: "albums", albumId: null })}
          />
          <NavItem
            icon={FolderSync}
            label="Sources & jobs"
            active={view.kind === "sources"}
            onClick={() => setView({ kind: "sources" })}
          />
        </NavSection>

        <NavSection
          title="Collections"
          action={
            <button
              type="button"
              className="fm-icon-btn fm-icon-btn-sm"
              aria-label="New album"
              title="New album"
              onClick={() => setView({ kind: "albums", albumId: null })}
            >
              <Plus aria-hidden="true" />
            </button>
          }
        >
          {albums?.map((album) => (
            <NavItem
              key={album.id}
              icon={Folder}
              label={album.name}
              count={album.asset_count}
              active={view.kind === "albums" && view.albumId === album.id}
              onClick={() => setView({ kind: "albums", albumId: album.id })}
            />
          ))}
          {albums?.length === 0 && <li className="fm-nav-empty">No albums yet</li>}
        </NavSection>

        <NavSection title="People">
          <NavItem
            icon={Users}
            label="People"
            disabled
            hint="Face recognition is planned for a later milestone"
          />
        </NavSection>
      </nav>

      <main className="fm-main">{content}</main>

      <footer className="fm-statusbar">
        <span className="fm-status-item fm-num">
          <HardDrive aria-hidden="true" />
          {facets
            ? `${plural(facets.total, "item")} (${plural(typeCount("photo"), "photo")}, ${plural(
                typeCount("video"),
                "video",
              )})`
            : "Loading catalogue…"}
        </span>
        <span className="fm-status-end">FotoMind {surface} · originals are never modified</span>
      </footer>
    </div>
  );
}
