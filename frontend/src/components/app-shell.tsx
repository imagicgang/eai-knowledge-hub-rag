"use client";

import {
  Boxes,
  CircleHelp,
  Database,
  Network,
  PanelLeft,
  Plus,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  { label: "Ask knowledge", icon: Sparkles, href: "/chat" },
  { label: "Upload data", icon: Database, href: "/upload" },
  { label: "Vector & Graph RAG", icon: Network, href: "/knowledge" },
];

const pageTitles: Record<string, string> = {
  "/chat": "Enterprise Knowledge",
  "/upload": "Upload Data",
  "/knowledge": "Vector & Graph RAG",
};

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const title = pageTitles[pathname] ?? "Enterprise Knowledge";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark"><Boxes size={18} /></div>
          <div><strong>Atlas</strong><span>Knowledge Hub</span></div>
          <button className="icon-button" aria-label="Collapse sidebar"><PanelLeft size={17} /></button>
        </div>

        <Link className="new-chat" href="/chat"><Plus size={16} /> New conversation</Link>

        <nav>
          <p className="nav-label">Workspace</p>
          {navigation.map(({ label, icon: Icon, href }) => (
            <Link className={`nav-item ${pathname === href ? "active" : ""}`} href={href} key={href}>
              <Icon size={17} /> {label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="nav-item"><CircleHelp size={17} /> Help & docs</button>
          <button className="nav-item"><Settings size={17} /> Settings</button>
          <div className="profile"><div className="avatar">TN</div><div><b>Demo workspace</b><span>Local environment</span></div></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><b>{title}</b><span><i /> Knowledge index connected</span></div>
          <button className="search-button"><Search size={16} /> Search everything <kbd>⌘ K</kbd></button>
        </header>
        {children}
      </section>
    </div>
  );
}
