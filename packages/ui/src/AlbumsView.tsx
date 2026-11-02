import { useCallback, useEffect, useState } from "react";
import type { Album, FotoMindClient } from "@fotomind/api-client";
import { LibraryView } from "./LibraryView";
import { errorMessage } from "./format";

export function AlbumsView({ client }: { client: FotoMindClient }) {
  const [albums, setAlbums] = useState<Album[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");

  const refresh = useCallback(
    () =>
      client.listAlbums().then(
        (a) => {
          setAlbums(a);
          setError(null);
        },
        (err: unknown) => setError(errorMessage(err)),
      ),
    [client],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function act(action: () => Promise<unknown>) {
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    }
    await refresh();
  }

  const open = albums?.find((a) => a.id === openId);
  if (openId && open) {
    return (
      <AlbumDetail
        client={client}
        album={open}
        onBack={() => setOpenId(null)}
        onChanged={() => void refresh()}
        onDeleted={() => {
          setOpenId(null);
          void refresh();
        }}
      />
    );
  }

  return (
    <section className="fm-albums" aria-labelledby="fm-albums-title">
      <div className="fm-toolbar">
        <h2 id="fm-albums-title">Albums</h2>
        <form
          className="fm-inline-form fm-toolbar-end"
          onSubmit={(e) => {
            e.preventDefault();
            const name = newName.trim();
            if (!name) return;
            setNewName("");
            void act(() => client.createAlbum({ name }));
          }}
        >
          <input
            aria-label="New album name"
            placeholder="New album name"
            maxLength={200}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button type="submit" disabled={!newName.trim()}>
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
        <p className="fm-empty">
          No albums yet. Create one here, or select photos in the Library and use “Add to album”.
        </p>
      )}
      <ul className="fm-album-grid">
        {albums?.map((album) => (
          <li key={album.id}>
            <button type="button" className="fm-album-card" onClick={() => setOpenId(album.id)}>
              {album.cover_thumbnail_url ? (
                <img src={client.url(album.cover_thumbnail_url)} alt="" loading="lazy" />
              ) : (
                <span className="fm-tile-placeholder">Empty</span>
              )}
              <span className="fm-album-name">{album.name}</span>
              <span className="fm-muted fm-small">{album.asset_count} items</span>
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
  onBack(): void;
  onChanged(): void;
  onDeleted(): void;
}

function AlbumDetail({ client, album, onBack, onChanged, onDeleted }: AlbumDetailProps) {
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
      <button type="button" onClick={onBack}>
        ← Albums
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
          <button type="submit">Save</button>
          <button type="button" onClick={() => setRenaming(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <>
          <h2>{album.name}</h2>
          <button
            type="button"
            onClick={() => {
              setName(album.name);
              setRenaming(true);
            }}
          >
            Rename
          </button>
        </>
      )}
      {confirmDelete ? (
        <span className="fm-inline-form">
          <span className="fm-small">Delete the album? Photos are kept.</span>
          <button type="button" className="fm-danger" onClick={remove}>
            Delete album
          </button>
          <button type="button" onClick={() => setConfirmDelete(false)}>
            Keep
          </button>
        </span>
      ) : (
        <button type="button" onClick={() => setConfirmDelete(true)}>
          Delete…
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
    <LibraryView client={client} albumId={album.id} heading={heading} onAlbumsChanged={onChanged} />
  );
}
