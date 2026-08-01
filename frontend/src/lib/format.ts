import { currentLang, type Translate } from "./i18n";

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return `SAR ${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function date(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

// `undefined` as the locale means "whatever the browser is set to", which left every timestamp in
// English while the rest of an Arabic page was translated. The interface language is the correct
// signal; the Gregorian calendar is pinned so an Arabic reader still sees the same date the record
// actually carries rather than a Hijri conversion of it.
export function dateTime(value: string | null | undefined, language = currentLang()): string {
  if (!value) return "—";
  const locale = language === "ar" ? "ar-SA-u-ca-gregory-nu-latn" : "en-GB";
  return new Date(value).toLocaleString(locale, {
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
