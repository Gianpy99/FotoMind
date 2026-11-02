import { useState } from "react";
import { ArrowLeft, FolderPlus, Images, Pencil, Trash2 } from "lucide-react";
import type { Album, FotoMindClient } from "@fotomind/api-client";
import { LibraryView, type LibraryViewProps } from "./LibraryView";
import { errorMessage, plural } from "./format";

export interface AlbumsViewProps {
  client: FotoMindClient;
  /** null while loading. */
  albums: Album[] | null;
  /** The open album, or null for the album grid. */
  albumId: string | null;
  onOpen(albumId: string | null): void;
  /** Albums were created, renamed, deleted or their contents changed. */
  onChanged(): void;
  /** Passed through to the album's library grid. */
  library?: Pick<LibraryViewProps, "query" | "facets" | "onClearSearch">;
}

export function AlbumsView({
  client,
  albums,
  albumId,
  onOpen,
  onChanged,
  library,
}: AlbumsViewProps) {
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");

  const open = albumId ? albums?.find((a) => a.id === albumId) : undefined;
  if (open) {
    return (
      <AlbumDetail
        key={open.id}
        client={client}
        album={open}
        albums={albums ?? []}
        library={library}
        onBack={() => onOpen(null)}
        onChanged={onChanged}
        onDeleted={() => {
          onOpen(null);
          onChanged();
        }}
      />
    );
  }

  function create(name: string) {
    client.createAlbum({ name }).then(
      () => {
        setError(null);
        onChanged();
      },
      (err: unknown) => setError(errorMessage(err)),
    );
  }

  return (
    <section className="fm-page fm-albums" aria-labelledby="fm-albums-title">
      <div className="fm-page-head">
        <h2 id="fm-albums-title">Albums</h2>
        <form
          className="fm-inline-form fm-page-head-end"
          onSubmit={(e) => {
            e.preventDefault();
            const name = newName.trim();
            if (!name) return;
            setNewName("");
            create(name);
          }}
        >
          <input
            aria-label="New album name"
            placeholder="New album name"
            maxLength={200}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button type="submit" className="fm-btn fm-btn-primary" disabled={!newName.trim()}>
            <FolderPlus aria-hidden="true" />
            Create album
          </button>
        </form>
      </div>
      {error && (
        <p role="alert" className="fm-error">
          {error}
        </p>
      )}
      {albums && albums.length === 0 && (
        <div className="fm-empty">
          No albums yet. Create one here, or select photos in the Library and use “Add to album”.
        </div>
      )}
      <ul className="fm-album-grid">
        {albums?.map((album) => (
          <li key={album.id}>
            <button type="button" className="fm-album-card" onClick={() => onOpen(album.id)}>
              {album.cover_thumbnail_url ? (
                <img src={client.url(album.cover_thumbnail_url)} alt="" loading="lazy" />
              ) : (
                <span className="fm-tile-placeholder">
                  <Images aria-hidden="true" />
                </span>
              )}
              <span className="fm-album-name">{album.name}</span>
              <span className="fm-muted fm-small fm-num">{plural(album.asset_count, "item")}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface AlbumDetailProps {
  client: FotoMindClient;
  album: Album;
  albums: Album[];
  library?: AlbumsViewProps["library"];
  onBack(): void;
  onChanged(): void;
  onDeleted(): void;
}

function AlbumDetail({
  client,
  album,
  albums,
  library,
  onBack,
  onChanged,
  onDeleted,
}: AlbumDetailProps) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(album.name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function rename() {
    const next = name.trim();
    if (!next || next === album.name) {
      setRenaming(false);
      return;
    }
    client.updateAlbum(album.id, { name: next }).then(
      () => {
        setRenaming(false);
        onChanged();
      },
      (err: unknown) => setError(errorMessage(err)),
    );
  }

  function remove() {
    client.deleteAlbum(album.id).then(onDeleted, (err: unknown) => setError(errorMessage(err)));
  }

  const heading = (
    <div className="fm-album-head">
      <button
        type="button"
        className="fm-icon-btn"
        onClick={onBack}
        aria-label="All albums"
        title="All albums"
      >
        <ArrowLeft aria-hidden="true" />
      </button>
      {renaming ? (
        <form
          className="fm-inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            rename();
          }}
        >
          <input
            aria-label="Album name"
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          <button type="submit" className="fm-btn fm-btn-primary">
            Save
          </button>
          <button type="button" className="fm-btn fm-btn-ghost" onClick={() => setRenaming(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <>
          <h2>{album.name}</h2>
          <button
            type="button"
            className="fm-icon-btn"
            aria-label="Rename"
            title="Rename"
            onClick={() => {
              setName(album.name);
              setRenaming(true);
            }}
          >
            <Pencil aria-hidden="true" />
          </button>
        </>
      )}
      {confirmDelete ? (
        <span className="fm-inline-form">
          <span className="fm-small">Delete the album? Photos are kept.</span>
          <button type="button" className="fm-btn fm-btn-danger" onClick={remove}>
            Delete album
          </button>
          <button
            type="button"
            className="fm-btn fm-btn-ghost"
            onClick={() => setConfirmDelete(false)}
          >
            Keep
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="fm-icon-btn"
          aria-label="Delete…"
          title="Delete album"
          onClick={() => setConfirmDelete(true)}
        >
          <Trash2 aria-hidden="true" />
        </button>
      )}
      {error && (
        <span role="alert" className="fm-error">
          {error}
        </span>
      )}
    </div>
  );

  return (
    <LibraryView
      client={client}
      albumId={album.id}
      heading={heading}
      albums={albums}
      onCatalogChanged={onChanged}
      {...library}
    />
  );
}
