export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

type Metadata = Record<string, unknown>;

/** "f/2.8 · 1/250 s · ISO 400 · 35 mm", or null when the file had no exposure data. */
export function formatExposure(meta: Metadata): string | null {
  const parts: string[] = [];
  if (typeof meta.f_number === "number") parts.push(`f/${meta.f_number}`);
  if (typeof meta.exposure_time === "string") parts.push(`${meta.exposure_time} s`);
  if (typeof meta.iso === "number") parts.push(`ISO ${meta.iso}`);
  if (typeof meta.focal_length_mm === "number") parts.push(`${meta.focal_length_mm} mm`);
  return parts.length ? parts.join(" · ") : null;
}

/** "h264 · 29.97 fps · 12000 kbps · audio aac", or null for non-video metadata. */
export function formatVideoInfo(meta: Metadata): string | null {
  const parts: string[] = [];
  if (typeof meta.video_codec === "string") parts.push(meta.video_codec);
  if (typeof meta.fps === "number") parts.push(`${meta.fps} fps`);
  if (typeof meta.bitrate_kbps === "number") parts.push(`${meta.bitrate_kbps} kbps`);
  if (meta.has_audio === false) parts.push("no audio");
  else if (typeof meta.audio_codec === "string") parts.push(`audio ${meta.audio_codec}`);
  return parts.length ? parts.join(" · ") : null;
}

const RAW_FORMATS = new Set(["ARW", "CR2", "CR3", "DNG", "NEF", "ORF", "RAF", "RW2"]);

/** Upper-case file extension ("JPG", "ARW"), or null. */
export function fileFormat(name: string): string | null {
  const match = /\.([a-z0-9]{2,5})$/i.exec(name);
  const ext = match?.[1];
  return ext ? ext.toUpperCase() : null;
}

export function isRawFormat(format: string | null): boolean {
  return format !== null && RAW_FORMATS.has(format);
}

/** Local calendar month of a timestamp, for grouping ("2024-07"). */
export function monthKey(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function monthLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

export type GroupBy = "month" | "week" | "day";

const DAY_MS = 86_400_000;

/** ISO 8601 week (Monday first; week 1 holds the year's first Thursday), in local time. */
export function isoWeek(date: Date): { year: number; week: number; monday: Date } {
  const monday = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  const thursday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 3);
  const year = thursday.getFullYear();
  // Round: daylight-saving changes make some days 23 or 25 hours long.
  const dayOfYear = Math.round((thursday.getTime() - new Date(year, 0, 1).getTime()) / DAY_MS);
  return { year, week: Math.floor(dayOfYear / 7) + 1, monday };
}

/** Grid section key for a timestamp; sorted items with the same key form one section. */
export function groupKey(value: string, by: GroupBy): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  if (by === "month") return monthKey(value);
  if (by === "week") {
    const { year, week } = isoWeek(date);
    return `${year}-W${String(week).padStart(2, "0")}`;
  }
  return `${monthKey(value)}-${String(date.getDate()).padStart(2, "0")}`;
}

export function groupLabel(value: string, by: GroupBy): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  if (by === "month") return monthLabel(value);
  if (by === "day") {
    return date.toLocaleDateString(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }
  const { week, monday } = isoWeek(date);
  const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
  const short: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  const end = sunday.toLocaleDateString(undefined, { ...short, year: "numeric" });
  return `CW ${week} · ${monday.toLocaleDateString(undefined, short)} – ${end}`;
}

export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** Inclusive UTC day range for a year facet value. */
export function yearRange(year: string): { date_from: string; date_to: string } {
  return { date_from: `${year}-01-01`, date_to: `${year}-12-31` };
}
