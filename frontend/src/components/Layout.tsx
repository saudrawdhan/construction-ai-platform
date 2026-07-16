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
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { roleLabel } from "../lib/format";
import NotificationsBell from "./NotificationsBell";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", label: "Projects", icon: Building2 },
  { to: "/procurement", label: "Procurement", icon: ShoppingCart },
  { to: "/rfis", label: "RFIs", icon: FileQuestion },
  { to: "/claims", label: "Claims", icon: Scale },
  { to: "/change-orders", label: "Change Orders", icon: FileDiff },
  { to: "/meetings", label: "Meetings", icon: CalendarCheck },
  { to: "/site-reports", label: "Site Reports", icon: ClipboardList },
  { to: "/documents", label: "Documents", icon: FolderSearch },
  { to: "/reports", label: "Reports", icon: FileBarChart2 },
  { to: "/copilot", label: "Copilot", icon: MessageSquareText },
  { to: "/agent", label: "Agent", icon: Bot },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck },
  { to: "/memory", label: "Memory", icon: BrainCircuit },
  { to: "/audit", label: "Audit", icon: ScrollText },
  { to: "/users", label: "Users", icon: UsersRound, adminOnly: true },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const items = nav.filter((item) => !item.adminOnly || user?.role === "admin");
  return (
    <div className="flex h-full">
      <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white">
            <HardHat size={20} />
          </span>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-slate-900">Construction AI</div>
            <div className="text-xs text-slate-500">Operations Intelligence</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-2">
          {items.map(({ to, label, icon: Icon, end }) => (
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
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="text-sm text-slate-500">AI-Powered Construction Operations Platform</div>
          <div className="flex items-center gap-4">
            <NotificationsBell />
            <div className="text-right">
              <div className="text-sm font-medium text-slate-900">{user?.full_name}</div>
              <div className="text-xs text-slate-500">{user ? roleLabel(user.role) : ""}</div>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              <LogOut size={15} /> Sign out
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
