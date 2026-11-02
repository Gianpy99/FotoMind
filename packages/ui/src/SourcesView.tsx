import { Fragment, useCallback, useEffect, useState } from "react";
import type { FotoMindClient, Job, StorageRoot, SystemStatus } from "@fotomind/api-client";
import { errorMessage, formatDate } from "./format";

const ACTIVE_POLL_MS = 3000;
const IDLE_POLL_MS = 30000;

function isActive(job: Job): boolean {
  return job.status === "queued" || job.status === "running";
}

function jobProgress(job: Job): string {
  if (job.progress_total) {
    const pct = Math.min(100, Math.round((job.progress_done / job.progress_total) * 100));
    return `${job.progress_done} / ${job.progress_total} (${pct}%)`;
  }
  return job.progress_done ? `${job.progress_done}` : "";
}

interface ExclusionEditorProps {
  root: StorageRoot;
  onSave(patterns: string[]): Promise<void>;
  onCancel(): void;
}

function ExclusionEditor({ root, onSave, onCancel }: ExclusionEditorProps) {
  const [text, setText] = useState((root.exclude_patterns ?? []).join("\n"));
  const [saving, setSaving] = useState(false);
  const id = `fm-exclude-${root.id}`;
  return (
    <form
      className="fm-exclusions"
      onSubmit={(e) => {
        e.preventDefault();
        setSaving(true);
        const patterns = text
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean);
        void onSave(patterns).finally(() => setSaving(false));
      }}
    >
      <label htmlFor={id}>Skip these folders/files when scanning {root.label}, one per line:</label>
      <textarea
        id={id}
        rows={5}
        value={text}
        placeholder={"@eaDir\n*.tmp\nPrivate/2019*"}
        onChange={(e) => setText(e.target.value)}
      />
      <p className="fm-muted fm-small">
        A name without “/” (e.g. <code>Thumbs</code>, <code>*.edit.jpg</code>) matches anywhere; a
        path with “/” (e.g. <code>Private/2019*</code>) matches from the top of this folder.
        Case-insensitive. Already catalogued files that match leave the library on the next scan
        (originals are untouched).
      </p>
      <div className="fm-inline-form">
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save exclusions"}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function SourcesView({ client }: { client: FotoMindClient }) {
  const [roots, setRoots] = useState<StorageRoot[] | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const refresh = useCallback(
    () =>
      Promise.all([client.listRoots(), client.listJobs(20)]).then(
        ([r, j]) => {
          setRoots(r);
          setJobs(j);
          setError(null);
        },
        (err: unknown) => setError(errorMessage(err)),
      ),
    [client],
  );

  useEffect(() => {
    let cancelled = false;
    client
      .systemStatus()
      .then((s) => !cancelled && setStatus(s))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [client]);

  const anyActive = jobs.some(isActive);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(
      () => void refresh(),
      anyActive ? ACTIVE_POLL_MS : IDLE_POLL_MS,
    );
    return () => window.clearInterval(timer);
  }, [refresh, anyActive]);

  async function act(action: () => Promise<unknown>) {
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    }
    await refresh();
  }

  const rootLabel = (id: string | null | undefined) =>
    roots?.find((r) => r.id === id)?.label ?? "—";

  return (
    <section className="fm-sources" aria-labelledby="fm-sources-title">
      <div className="fm-toolbar">
        <h2 id="fm-sources-title">Sources</h2>
      </div>
      {error && (
        <p role="alert" className="fm-error">
          {error}
        </p>
      )}

      {roots && roots.length === 0 && (
        <p className="fm-empty">
          No folders registered yet. On the PC run{" "}
          <code>fotomind-worker roots add &quot;D:\Photos&quot; --label Photos</code>.
        </p>
      )}

      {roots && roots.length > 0 && (
        <table className="fm-table">
          <thead>
            <tr>
              <th>Folder</th>
              <th>Host</th>
              <th>Files</th>
              <th>Status</th>
              <th>Last scan</th>
              <th>Exclusions</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {roots.map((root) => {
              const busy = jobs.some((j) => isActive(j) && j.storage_root_id === root.id);
              const patterns = root.exclude_patterns ?? [];
              return (
                <Fragment key={root.id}>
                  <tr>
                    <td>
                      <strong>{root.label}</strong>
                      <div className="fm-muted fm-small">{root.path}</div>
                    </td>
                    <td>{root.host}</td>
                    <td>
                      {root.file_count}
                      {root.missing_count > 0 && (
                        <span className="fm-muted"> ({root.missing_count} missing)</span>
                      )}
                    </td>
                    <td>{root.availability}</td>
                    <td>{formatDate(root.last_scan_at)}</td>
                    <td>
                      <button
                        type="button"
                        aria-expanded={editing === root.id}
                        onClick={() => setEditing(editing === root.id ? null : root.id)}
                        title={patterns.join(", ")}
                      >
                        {patterns.length ? `${patterns.length} rule(s)` : "None"} ✎
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void act(() => client.scanRoot(root.id))}
                      >
                        {busy ? "Scanning…" : "Scan now"}
                      </button>
                    </td>
                  </tr>
                  {editing === root.id && (
                    <tr>
                      <td colSpan={7}>
                        <ExclusionEditor
                          root={root}
                          onCancel={() => setEditing(null)}
                          onSave={(exclude_patterns) =>
                            act(async () => {
                              await client.updateRoot(root.id, { exclude_patterns });
                              setEditing(null);
                            })
                          }
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}

      <h2 className="fm-subtitle">Jobs</h2>
      {jobs.length === 0 ? (
        <p className="fm-muted">No jobs yet.</p>
      ) : (
        <table className="fm-table">
          <thead>
            <tr>
              <th>Folder</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Message</th>
              <th>Requested</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{rootLabel(job.storage_root_id)}</td>
                <td>
                  <span className={`fm-status fm-status-${job.status}`}>{job.status}</span>
                </td>
                <td>{jobProgress(job)}</td>
                <td className="fm-small">{job.error ?? job.message ?? ""}</td>
                <td className="fm-small">
                  {formatDate(job.created_at)}
                  {job.requested_by && ` · ${job.requested_by}`}
                </td>
                <td>
                  {isActive(job) && (
                    <button type="button" onClick={() => void act(() => client.cancelJob(job.id))}>
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {jobs.some((j) => j.status === "queued") && (
        <p className="fm-muted fm-small">
          Queued scans run when the worker on the PC is online (<code>fotomind-worker run</code>).
        </p>
      )}

      <h2 className="fm-subtitle">System</h2>
      {status ? (
        <dl className="fm-kv">
          <dt>API</dt>
          <dd>
            {status.status} (v{status.version}, {status.environment})
          </dd>
          <dt>Database</dt>
          <dd>
            {status.database.status}
            {status.database.server_version && ` — PostgreSQL ${status.database.server_version}`}
          </dd>
        </dl>
      ) : (
        <p className="fm-muted">Checking…</p>
      )}
    </section>
  );
}
