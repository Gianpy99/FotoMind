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

/** Inclusive UTC day range for a year facet value. */
export function yearRange(year: string): { date_from: string; date_to: string } {
  return { date_from: `${year}-01-01`, date_to: `${year}-12-31` };
}
