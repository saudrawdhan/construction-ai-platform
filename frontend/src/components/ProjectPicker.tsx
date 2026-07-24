import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useT } from "../lib/i18n";

export interface ProjectOption {
  id: number;
  project_name: string;
}

/**
 * A searchable project selector: type to filter, or just open it and scroll the full list — both
 * stay available, neither replaces the other. Drop-in replacement for the `<Select>` + `<option>`
 * pattern used everywhere a project is picked from a list fetched via `/projects?size=100`.
 */
export default function ProjectPicker({
  projects,
  value,
  onChange,
  placeholder: placeholderProp,
  required = false,
}: {
  projects: ProjectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const t = useT();
  const placeholder = placeholderProp ?? t("projectPicker.all");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(
    () => projects.find((p) => String(p.id) === value),
    [projects, value]
  );

  // Keep the visible text in sync with the committed selection whenever it changes externally
  // (e.g. a parent resets the value, or the project list finishes loading).
  useEffect(() => {
    if (!open) setQuery(selected ? selected.project_name : "");
  }, [selected, open]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery(selected ? selected.project_name : "");
      }
    }
    function onKey(e: KeyboardEvent) {
      // stopImmediatePropagation: this picker is often opened inside a Modal, which has its own
      // document-level Escape listener. Without this, one Escape press would close the dropdown
      // AND the whole modal at once — the dropdown should close first, on its own.
      if (e.key === "Escape") {
        e.stopImmediatePropagation();
        setOpen(false);
        setQuery(selected ? selected.project_name : "");
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey, true);
    };
  }, [open, selected]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || (selected && q === selected.project_name.toLowerCase())) return projects;
    return projects.filter((p) => p.project_name.toLowerCase().includes(q));
  }, [projects, query, selected]);

  // Row 0 is always the placeholder/"clear" option; rows 1..n are the filtered projects. Keeping
  // both in one list makes arrow-key navigation and Enter-to-select a single, simple index.
  const rows: { id: string; label: string }[] = useMemo(
    () => [{ id: "", label: placeholder }, ...filtered.map((p) => ({ id: String(p.id), label: p.project_name }))],
    [filtered, placeholder]
  );

  // Default to the first real project match while actively filtering, so Enter confirms the
  // obvious match — not row 0 ("clear"), which is only the sensible default when browsing the
  // full, unfiltered list.
  useEffect(() => {
    setHighlight(query.trim() && filtered.length > 0 ? 1 : 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, open]);

  function choose(id: string) {
    onChange(id);
    setOpen(false);
  }

  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      // Always prevent the default submit — this input commonly sits inside a form (CreateModal),
      // and Enter should confirm a selection here, never fall through to submitting the whole form.
      e.preventDefault();
      if (open) choose(rows[highlight]?.id ?? "");
      else setOpen(true);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      else setHighlight((h) => Math.min(h + 1, rows.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (open) setHighlight((h) => Math.max(h - 1, 0));
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <div className="relative">
        <input
          role="combobox"
          aria-expanded={open}
          aria-controls="project-picker-list"
          aria-activedescendant={open ? `project-picker-row-${highlight}` : undefined}
          required={required && !value}
          className="w-full rounded-lg border border-slate-200 bg-white py-2 ps-3 pe-8 text-sm text-slate-800 shadow-sm outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          placeholder={placeholder}
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={onInputKeyDown}
          onBlur={(e) => {
            // Tabbing (or otherwise moving focus) away should close the dropdown and discard any
            // unconfirmed typed text, same as clicking outside does. But a mouse click on one of
            // our own option buttons ALSO fires blur first (before its click event) — closing here
            // unconditionally would unmount the button before the click could register, silently
            // breaking mouse selection. relatedTarget tells us where focus is actually going: if
            // it's still inside this component (one of our own buttons), let that click proceed.
            if (rootRef.current && e.relatedTarget && rootRef.current.contains(e.relatedTarget as Node)) {
              return;
            }
            setOpen(false);
            setQuery(selected ? selected.project_name : "");
          }}
        />
        <ChevronDown
          size={15}
          className="pointer-events-none absolute end-2.5 top-1/2 -translate-y-1/2 text-slate-400"
        />
      </div>
      {open && (
        <div
          id="project-picker-list"
          role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {rows.map((row, i) => (
            <button
              key={row.id || "__placeholder__"}
              id={`project-picker-row-${i}`}
              type="button"
              role="option"
              aria-selected={row.id === value}
              onClick={() => choose(row.id)}
              onMouseEnter={() => setHighlight(i)}
              className={`block w-full truncate px-3 py-1.5 text-start text-sm ${
                i === highlight ? "bg-blue-50" : ""
              } ${
                row.id === value
                  ? "font-medium text-blue-700"
                  : row.id === ""
                    ? "text-slate-500"
                    : "text-slate-700"
              }`}
            >
              {row.label}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-3 py-1.5 text-sm text-slate-400">{t("projectPicker.noMatch")}</div>
          )}
        </div>
      )}
    </div>
  );
}
