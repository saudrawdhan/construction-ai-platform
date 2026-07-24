import type { Translate } from "./i18n";

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

// Maps a role code to its localized label, falling back to a title-cased version
// of the raw code when a translation is not defined.
export function roleLabel(role: string, t: Translate): string {
  const key = `role.${role}`;
  const label = t(key);
  return label === key ? titleCase(role) : label;
}

// Maps a stored English enum value (status, type, risk level…) to its localized
// display label. The original value is unchanged and is what still gets sent to
// the API — only the on-screen text is translated. Unknown values are title-cased.
export function enumLabel(value: string | null | undefined, t: Translate): string {
  if (!value) return "—";
  const key = `enum.${value.toLowerCase().trim().replace(/[\s/]+/g, "_")}`;
  const label = t(key);
  return label === key ? titleCase(value) : label;
}

// Maps an AI workflow code (e.g. "pr_review") to its localized label, falling
// back to a title-cased version of the code when no translation is defined.
export function workflowLabel(value: string, t: Translate): string {
  const key = `workflow.${value.toLowerCase()}`;
  const label = t(key);
  return label === key ? titleCase(value) : label;
}
