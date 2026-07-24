import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  ShoppingCart,
  FileQuestion,
  Scale,
  FileDiff,
  CalendarCheck,
  ClipboardList,
  FolderSearch,
  FileBarChart2,
  MessageSquareText,
  Bot,
  ShieldCheck,
  BrainCircuit,
  ScrollText,
  UsersRound,
  HardHat,
  LogOut,
  Languages,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { roleLabel } from "../lib/format";
import { useI18n } from "../lib/i18n";
import NotificationsBell from "./NotificationsBell";

const nav = [
  { to: "/", key: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", key: "nav.projects", icon: Building2 },
  { to: "/procurement", key: "nav.procurement", icon: ShoppingCart },
  { to: "/rfis", key: "nav.rfis", icon: FileQuestion },
  { to: "/claims", key: "nav.claims", icon: Scale },
  { to: "/change-orders", key: "nav.changeOrders", icon: FileDiff },
  { to: "/meetings", key: "nav.meetings", icon: CalendarCheck },
  { to: "/site-reports", key: "nav.siteReports", icon: ClipboardList },
  { to: "/documents", key: "nav.documents", icon: FolderSearch },
  { to: "/reports", key: "nav.reports", icon: FileBarChart2 },
  { to: "/copilot", key: "nav.copilot", icon: MessageSquareText },
  { to: "/agent", key: "nav.agent", icon: Bot },
  { to: "/approvals", key: "nav.approvals", icon: ShieldCheck },
  { to: "/memory", key: "nav.memory", icon: BrainCircuit },
  { to: "/audit", key: "nav.audit", icon: ScrollText },
  { to: "/users", key: "nav.users", icon: UsersRound, adminOnly: true },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { t, toggle } = useI18n();
  const items = nav.filter((item) => !item.adminOnly || user?.role === "admin");
  return (
    <div className="flex h-full">
      <aside className="flex w-64 flex-col border-e border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white">
            <HardHat size={20} />
          </span>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-slate-900">{t("brand.name")}</div>
            <div className="text-xs text-slate-500">{t("brand.tagline")}</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-2">
          {items.map(({ to, key, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              <Icon size={18} />
              {t(key)}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="text-sm text-slate-500">{t("shell.headerTagline")}</div>
          <div className="flex items-center gap-4">
            <button
              onClick={toggle}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              <Languages size={15} /> {t("shell.language")}
            </button>
            <NotificationsBell />
            <div className="text-end">
              <div className="text-sm font-medium text-slate-900">{user?.full_name}</div>
              <div className="text-xs text-slate-500">{user ? roleLabel(user.role, t) : ""}</div>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              <LogOut size={15} /> {t("shell.signOut")}
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
