import { useState, type ReactNode } from "react";
import { X } from "lucide-react";
import type {
  AssetDetail,
  EditableField,
  FotoMindClient,
  MetadataEdit,
} from "@fotomind/api-client";
import { LocationPicker, type PickedLocation } from "./LocationPicker";
import { errorMessage, plural } from "./format";

export interface MetadataEditorProps {
  client: FotoMindClient;
  /** How many items the edit applies to. */
  count: number;
  /** Editing one item: its current values pre-fill the form and its edits can be reverted. */
  detail?: AssetDetail | null;
  onSubmit(edit: MetadataEdit): Promise<void>;
  onClose(): void;
}

type DateMode = "keep" | "set" | "shift";
type LocationMode = "keep" | "set" | "clear";
type CameraField = "camera_make" | "camera_model" | "lens_model";

const CAMERA_FIELDS: { field: CameraField; label: string }[] = [
  { field: "camera_make", label: "Camera make" },
  { field: "camera_model", label: "Camera model" },
  { field: "lens_model", label: "Lens" },
];

export const FIELD_LABELS: Record<EditableField, string> = {
  captured_at: "Date taken",
  location: "Location",
  camera_make: "Camera make",
  camera_model: "Camera model",
  lens_model: "Lens",
};
const ALL_FIELDS = Object.keys(FIELD_LABELS) as EditableField[];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** ISO instant -> value for <input type="datetime-local"> in the browser's time zone. */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function Section({
  title,
  checked,
  onToggle,
  children,
}: {
  title: string;
  checked: boolean;
  onToggle(on: boolean): void;
  children: ReactNode;
}) {
  return (
    <fieldset className={checked ? "fm-edit-section fm-edit-on" : "fm-edit-section"}>
      <legend>
        <label>
          <input type="checkbox" checked={checked} onChange={(e) => onToggle(e.target.checked)} />
          {title}
        </label>
      </legend>
      {children}
    </fieldset>
  );
}

export function MetadataEditor({ client, count, detail, onSubmit, onClose }: MetadataEditorProps) {
  const single = detail != null;
  const [titleOn, setTitleOn] = useState(false);
  const [title, setTitle] = useState(detail?.title ?? "");
  const [descriptionOn, setDescriptionOn] = useState(false);
  const [description, setDescription] = useState(detail?.description ?? "");
  const [dateMode, setDateMode] = useState<DateMode>("keep");
  const [dateValue, setDateValue] = useState(
    toLocalInput(detail ? (detail.captured_at ?? detail.sort_at) : null),
  );
  const [shift, setShift] = useState({ direction: 1, days: 0, hours: 0, minutes: 0 });
  const [locationMode, setLocationMode] = useState<LocationMode>("keep");
  const own = detail?.location && detail.location.source !== "tag" ? detail.location : null;
  const [location, setLocation] = useState<PickedLocation | null>(
    own ? { latitude: own.latitude, longitude: own.longitude, label: own.label ?? "" } : null,
  );
  const [camera, setCamera] = useState<Record<CameraField, { on: boolean; value: string }>>({
    camera_make: { on: false, value: detail?.camera_make ?? "" },
    camera_model: { on: false, value: detail?.camera_model ?? "" },
    lens_model: { on: false, value: detail?.lens_model ?? "" },
  });
  const [revert, setRevert] = useState<ReadonlySet<EditableField>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const changing: Record<EditableField, boolean> = {
    captured_at: dateMode !== "keep",
    location: locationMode !== "keep",
    camera_make: camera.camera_make.on,
    camera_model: camera.camera_model.on,
    lens_model: camera.lens_model.on,
  };
  const revertable = single
    ? ALL_FIELDS.filter((f) => detail.edited_fields?.includes(f))
    : ALL_FIELDS;
  const shiftSeconds =
    shift.direction * (shift.days * 86400 + shift.hours * 3600 + shift.minutes * 60);

  function setCameraField(field: CameraField, next: Partial<{ on: boolean; value: string }>) {
    setCamera((c) => ({ ...c, [field]: { ...c[field], ...next } }));
  }

  function toggleRevert(field: EditableField, on: boolean) {
    setRevert((prev) => {
      const next = new Set(prev);
      if (on) next.add(field);
      else next.delete(field);
      return next;
    });
  }

  function build(): MetadataEdit | string {
    const edit: MetadataEdit = {};
    if (titleOn) edit.title = title;
    if (descriptionOn) edit.description = description;
    if (dateMode === "set") {
      const when = new Date(dateValue);
      if (!dateValue || Number.isNaN(when.getTime())) return "Enter the date and time taken.";
      edit.captured_at = when.toISOString();
    } else if (dateMode === "shift") {
      if (!shiftSeconds) return "Enter how much to shift the date by.";
      edit.shift_seconds = shiftSeconds;
    }
    if (locationMode === "set") {
      if (!location) return "Choose a place on the map or search for one.";
      edit.location = {
        latitude: location.latitude,
        longitude: location.longitude,
        label: location.label || null,
      };
    } else if (locationMode === "clear") {
      edit.clear_location = true;
    }
    for (const { field } of CAMERA_FIELDS) {
      if (camera[field].on) edit[field] = camera[field].value;
    }
    const reverting = [...revert].filter((f) => !changing[f]);
    if (reverting.length) edit.revert = reverting;
    return Object.keys(edit).length ? edit : "Tick at least one thing to change.";
  }

  async function submit() {
    const edit = build();
    if (typeof edit === "string") {
      setError(edit);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit(edit);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  const heading = single
    ? `Edit info · ${detail.display_name}`
    : `Edit info · ${plural(count, "item")}`;

  return (
    <div className="fm-modal-backdrop">
      <div
        className="fm-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Edit info"
        onKeyDown={(e) => {
          // Keep the viewer's and library's shortcuts (arrows, 0–5, Esc) out of the form.
          e.stopPropagation();
          if (e.key === "Escape" && !saving) onClose();
        }}
      >
        <header className="fm-modal-head">
          <h2>{heading}</h2>
          <button
            type="button"
            className="fm-icon-btn"
            aria-label="Cancel"
            title="Cancel"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </header>

        <form
          className="fm-modal-body"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          {!single && (
            <p className="fm-muted fm-small">
              Only ticked fields change; everything else stays as it is on each item.
            </p>
          )}

          <Section title="Title" checked={titleOn} onToggle={setTitleOn}>
            <input
              aria-label="Title"
              maxLength={300}
              value={title}
              placeholder="No title (leave empty to remove)"
              onChange={(e) => {
                setTitle(e.target.value);
                setTitleOn(true);
              }}
            />
          </Section>

          <Section title="Description" checked={descriptionOn} onToggle={setDescriptionOn}>
            <textarea
              aria-label="Description"
              rows={3}
              maxLength={5000}
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
                setDescriptionOn(true);
              }}
            />
          </Section>

          <Section
            title="Date taken"
            checked={dateMode !== "keep"}
            onToggle={(on) => setDateMode(on ? (single ? "set" : "shift") : "keep")}
          >
            <div className="fm-segmented" role="radiogroup" aria-label="Date change">
              <label>
                <input
                  type="radio"
                  name="fm-date-mode"
                  checked={dateMode === "set"}
                  onChange={() => setDateMode("set")}
                />
                Set to
              </label>
              <label>
                <input
                  type="radio"
                  name="fm-date-mode"
                  checked={dateMode === "shift"}
                  onChange={() => setDateMode("shift")}
                />
                Shift by
              </label>
            </div>
            {dateMode !== "shift" ? (
              <input
                type="datetime-local"
                aria-label="Date and time taken"
                step={1}
                value={dateValue}
                onChange={(e) => {
                  setDateValue(e.target.value);
                  setDateMode("set");
                }}
              />
            ) : (
              <div className="fm-shift">
                <select
                  aria-label="Shift direction"
                  value={shift.direction}
                  onChange={(e) => setShift((s) => ({ ...s, direction: Number(e.target.value) }))}
                >
                  <option value={1}>Later</option>
                  <option value={-1}>Earlier</option>
                </select>
                {(["days", "hours", "minutes"] as const).map((unit) => (
                  <label key={unit}>
                    <input
                      type="number"
                      aria-label={`Shift ${unit}`}
                      min={0}
                      max={unit === "days" ? 36500 : 1000}
                      value={shift[unit]}
                      onChange={(e) =>
                        setShift((s) => ({
                          ...s,
                          [unit]: Math.max(0, Number(e.target.value) || 0),
                        }))
                      }
                    />
                    {unit}
                  </label>
                ))}
              </div>
            )}
            {dateMode === "shift" && (
              <p className="fm-muted fm-small">
                Fixes a camera clock that was wrong: every item moves by the same amount.
              </p>
            )}
          </Section>

          <Section
            title="Location"
            checked={locationMode !== "keep"}
            onToggle={(on) => setLocationMode(on ? "set" : "keep")}
          >
            <div className="fm-segmented" role="radiogroup" aria-label="Location change">
              <label>
                <input
                  type="radio"
                  name="fm-location-mode"
                  checked={locationMode === "set"}
                  onChange={() => setLocationMode("set")}
                />
                Set place
              </label>
              <label>
                <input
                  type="radio"
                  name="fm-location-mode"
                  checked={locationMode === "clear"}
                  onChange={() => setLocationMode("clear")}
                />
                Remove location
              </label>
            </div>
            {locationMode === "set" && (
              <LocationPicker client={client} value={location} onChange={setLocation} />
            )}
            {locationMode === "clear" && (
              <p className="fm-muted fm-small">
                Hides these items from the map, even if a tag names a place.
              </p>
            )}
          </Section>

          <Section
            title="Camera & lens"
            checked={CAMERA_FIELDS.some(({ field }) => camera[field].on)}
            onToggle={(on) => CAMERA_FIELDS.forEach(({ field }) => setCameraField(field, { on }))}
          >
            <div className="fm-edit-grid">
              {CAMERA_FIELDS.map(({ field, label }) => (
                <label key={field}>
                  <span>
                    <input
                      type="checkbox"
                      aria-label={`Change ${label.toLowerCase()}`}
                      checked={camera[field].on}
                      onChange={(e) => setCameraField(field, { on: e.target.checked })}
                    />
                    {label}
                  </span>
                  <input
                    aria-label={label}
                    maxLength={200}
                    value={camera[field].value}
                    onChange={(e) => setCameraField(field, { value: e.target.value, on: true })}
                  />
                </label>
              ))}
            </div>
          </Section>

          {revertable.length > 0 && (
            <fieldset className="fm-edit-section">
              <legend>Restore from the original file</legend>
              <div className="fm-edit-checks">
                {revertable.map((field) => (
                  <label key={field}>
                    <input
                      type="checkbox"
                      aria-label={`Restore ${FIELD_LABELS[field].toLowerCase()} from the file`}
                      checked={revert.has(field) && !changing[field]}
                      disabled={changing[field]}
                      onChange={(e) => toggleRevert(field, e.target.checked)}
                    />
                    {FIELD_LABELS[field]}
                  </label>
                ))}
              </div>
              {!single && (
                <p className="fm-muted fm-small">Only affects items where the field was edited.</p>
              )}
            </fieldset>
          )}

          {error && (
            <p role="alert" className="fm-error">
              {error}
            </p>
          )}

          <footer className="fm-modal-foot">
            <span className="fm-muted fm-small">
              Saved in the catalogue; files are not modified.
            </span>
            <button type="button" className="fm-btn fm-btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="fm-btn fm-btn-primary" disabled={saving}>
              {saving ? "Saving…" : single ? "Save" : `Apply to ${plural(count, "item")}`}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
