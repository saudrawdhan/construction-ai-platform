import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { api, type Page } from "../lib/api";
import { dateTime } from "../lib/format";

interface Notification {
  id: number;
  title: string;
  body: string;
  category: string | null;
  is_read: boolean;
  created_at: string;
}

/**
 * Topbar bell that surfaces the in-app notifications the backend writes (approval decisions and the
 * scheduled worker's digests/alerts). Polls periodically, shows an unread count, and marks items read.
 */
export default function NotificationsBell() {
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  async function load() {
    try {
      const page = await api.get<Page<Notification>>("/notifications?size=20");
      setItems(page.items);
    } catch {
      /* silently ignore — the bell is non-critical chrome */
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const unread = items.filter((n) => !n.is_read).length;

  async function markRead(n: Notification) {
    if (n.is_read) return;
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    try {
      await api.post(`/notifications/${n.id}/read`);
    } catch {
      load(); // reconcile on failure
    }
  }

  async function markAllRead() {
    const toMark = items.filter((n) => !n.is_read);
    setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
    await Promise.allSettled(toMark.map((n) => api.post(`/notifications/${n.id}/read`)));
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => {
          if (!open) load();
          setOpen((o) => !o);
        }}
        aria-label="Notifications"
        className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100"
      >
        <Bell size={17} />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <span className="text-sm font-semibold text-slate-800">Notifications</span>
            {unread > 0 && (
              <button onClick={markAllRead} className="text-xs font-medium text-blue-600 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-slate-400">No notifications yet.</div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => markRead(n)}
                  className={`flex w-full flex-col items-start gap-0.5 border-b border-slate-50 px-4 py-2.5 text-left last:border-0 hover:bg-slate-50 ${
                    n.is_read ? "" : "bg-blue-50/40"
                  }`}
                >
                  <div className="flex w-full items-center justify-between gap-2">
                    <span className="text-sm font-medium text-slate-800">{n.title}</span>
                    {!n.is_read && <span className="h-2 w-2 flex-shrink-0 rounded-full bg-blue-500" />}
                  </div>
                  <span className="text-xs text-slate-600">{n.body}</span>
                  <span className="text-[11px] text-slate-400">{dateTime(n.created_at)}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
