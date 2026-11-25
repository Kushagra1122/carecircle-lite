const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function shiftDate(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + days));
  const y = next.getUTCFullYear();
  const m = String(next.getUTCMonth() + 1).padStart(2, "0");
  const d = String(next.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function instantDate(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}

export function clockTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(new Date(iso));
}

export function duePhrase(iso: string, timeZone: string, todayDate: string): string {
  const date = instantDate(iso, timeZone);
  const time = clockTime(iso, timeZone);
  if (date === todayDate) return time;
  if (date === shiftDate(todayDate, -1)) return `Yesterday, ${time}`;
  const [, month, day] = date.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]}, ${time}`;
}

export function longDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "UTC",
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

export function defaultTime(
  timeZone: string,
  nowIso: string,
): { day: "today" | "tomorrow"; time: string } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(nowIso));
  const rawHour = Number(parts.find((part) => part.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((part) => part.type === "minute")?.value ?? "0");
  const hour = rawHour === 24 ? 0 : rawHour;
  const rounded = Math.ceil((hour * 60 + minute + 60) / 15) * 15;
  const dayOffset = Math.floor(rounded / 1440);
  const mins = rounded % 1440;
  return {
    day: dayOffset >= 1 ? "tomorrow" : "today",
    time: `${String(Math.floor(mins / 60)).padStart(2, "0")}:${String(mins % 60).padStart(2, "0")}`,
  };
}
