import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import {
  History,
  LayoutDashboard,
  type LucideIcon,
  Moon,
  RefreshCw,
  SlidersHorizontal,
  Sun,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn, formatTimestamp } from "@/lib/format";

const THEME_KEY = "scat-console-theme";

function initialTheme(): "light" | "dark" {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Storage blocked: fall through to the system preference.
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function NavItem({ to, icon: Icon, children }: { to: string; icon: LucideIcon; children: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cn(
          "relative flex min-h-[44px] items-center gap-xs rounded-sm px-sm text-sm font-medium hover:bg-surface-hover",
          // Active item: the reserved brand-red indicator bar.
          isActive &&
            "bg-surface-hover font-semibold before:absolute before:inset-y-xs before:left-0 before:w-[3px] before:rounded-full before:bg-brand-primary",
        )
      }
    >
      <Icon className="size-4" strokeWidth={1.75} aria-hidden />
      {children}
    </NavLink>
  );
}

/** When data on screen was last fetched, with a button to fetch it again. Re-renders when a
 *  fetch starts or ends, which is when the newest timestamp can change. */
function LastRefreshed() {
  const queryClient = useQueryClient();
  const fetching = useIsFetching() > 0;
  const updatedAt = Math.max(0, ...queryClient.getQueryCache().getAll().map((q) => q.state.dataUpdatedAt));
  return (
    <div className="flex items-center justify-end gap-xs text-xs text-content-muted">
      <span>
        Last refreshed{" "}
        <time className="num text-content-secondary" dateTime={updatedAt ? new Date(updatedAt).toISOString() : undefined}>
          {updatedAt ? formatTimestamp(updatedAt) : "not yet"}
        </time>
      </span>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Refresh data"
        disabled={fetching}
        onClick={() => queryClient.invalidateQueries()}
      >
        <RefreshCw strokeWidth={1.75} />
      </Button>
    </div>
  );
}

export function Layout() {
  const [theme, setTheme] = useState(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Storage blocked: the choice lasts for this page only.
    }
  }, [theme]);

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[220px_1fr]">
      <aside className="flex flex-col gap-xs border-b bg-surface-secondary p-sm lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between gap-xs px-xs py-xs">
          <div className="flex flex-col">
            <span className="text-md font-bold text-brand-primary">SATS</span>
            <span className="text-xs text-content-muted">Meal Request Console</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun strokeWidth={1.75} /> : <Moon strokeWidth={1.75} />}
          </Button>
        </div>
        <nav aria-label="Main" className="flex flex-row flex-wrap gap-xxs lg:flex-col">
          <NavItem to="/" icon={LayoutDashboard}>
            Flights
          </NavItem>
          <NavItem to="/audit" icon={History}>
            Audit trail
          </NavItem>
          <NavItem to="/admin" icon={SlidersHorizontal}>
            Admin settings
          </NavItem>
        </nav>
      </aside>
      <main className="min-w-0 bg-surface-secondary p-md lg:p-lg">
        <div className="mx-auto flex max-w-desktop flex-col gap-md">
          <LastRefreshed />
          <Outlet />
        </div>
      </main>
    </div>
  );
}
