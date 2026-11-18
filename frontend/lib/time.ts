/** Shared time formatting: relative text for people, exact UTC for tooltips. */
export const absFmt = new Intl.DateTimeFormat("en", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});

const relFmt = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** "3 hours ago" relative to `now` (both epoch ms). */
export function relative(ms: number, now: number): string {
  const s = Math.round((ms - now) / 1000);
  const abs = Math.abs(s);
  if (abs < 60) return relFmt.format(s, "second");
  if (abs < 3600) return relFmt.format(Math.round(s / 60), "minute");
  if (abs < 86400) return relFmt.format(Math.round(s / 3600), "hour");
  return relFmt.format(Math.round(s / 86400), "day");
}
