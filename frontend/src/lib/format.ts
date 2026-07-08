export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return `SAR ${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function date(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
