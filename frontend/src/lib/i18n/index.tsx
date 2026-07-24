import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { en } from "./en";
import { ar } from "./ar";

export type Lang = "en" | "ar";

type Dict = Record<string, string>;

const dicts: Record<Lang, Dict> = { en, ar };
const STORAGE_KEY = "lang";

function readStoredLang(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
}

function applyDocumentLang(lang: Lang) {
  const html = document.documentElement;
  html.lang = lang;
  html.dir = lang === "ar" ? "rtl" : "ltr";
}

// Called once from main.tsx before React renders, so the document direction and
// language are correct on the very first paint (no left-to-right flash before hydration).
export function applyInitialLang() {
  applyDocumentLang(readStoredLang());
}

// Hook-free translator for modules that run outside React (e.g. the API layer's
// transport-error messages). Reads the same stored language the provider uses.
export function translate(key: string, vars?: Record<string, string | number>): string {
  const lang = readStoredLang();
  const template = dicts[lang][key] ?? dicts.en[key] ?? key;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) =>
    vars[name] === undefined ? `{${name}}` : String(vars[name]),
  );
}

export type Translate = (key: string, vars?: Record<string, string | number>) => string;

interface I18nState {
  lang: Lang;
  t: Translate;
  setLang: (lang: Lang) => void;
  toggle: () => void;
}

const I18nContext = createContext<I18nState | undefined>(undefined);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang);

  const setLang = useCallback((next: Lang) => {
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage unavailable; language still applies for this session */
    }
    applyDocumentLang(next);
    setLangState(next);
  }, []);

  const toggle = useCallback(() => setLang(lang === "en" ? "ar" : "en"), [lang, setLang]);

  // Missing keys fall back to the English dictionary, then to the raw key, so the
  // interface can never render blank while a translation is still being added.
  const t = useCallback<Translate>(
    (key, vars) => {
      const template = dicts[lang][key] ?? dicts.en[key] ?? key;
      if (!vars) return template;
      return template.replace(/\{(\w+)\}/g, (_, name: string) =>
        vars[name] === undefined ? `{${name}}` : String(vars[name]),
      );
    },
    [lang],
  );

  return <I18nContext.Provider value={{ lang, t, setLang, toggle }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

export function useT(): Translate {
  return useI18n().t;
}
