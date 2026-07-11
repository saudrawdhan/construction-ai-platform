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

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  executive: "Executive",
  project_manager: "Project Manager",
  site_engineer: "Site Engineer",
  procurement_officer: "Procurement Officer",
  qa_qc: "QA / QC",
  viewer: "Viewer",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? titleCase(role);
}
