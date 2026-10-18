"use client";

import { useQuery } from "@tanstack/react-query";
import { Menu, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useState } from "react";

import { BackendBanner } from "@/components/backend-banner";
import { Wordmark } from "@/components/brand";
import { CommandMenu, useCommandMenu } from "@/components/command-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { api, type PatchSummary, type RunSummary, type Settings } from "@/lib/api";
import { NAV_GROUPS, navFor } from "@/lib/nav";
import { cn } from "@/lib/utils";

// With cacheComponents, reading the URL (usePathname, useParams) suspends on routes with dynamic
// segments such as /runs/[id]. The parts that read it sit in Suspense boundaries so the rest of the
// shell can still be prerendered.
export function AppShell({ children }: { children: React.ReactNode }) {
  const menu = useCommandMenu();
  const [mobileNav, setMobileNav] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-sidebar px-3 py-4 transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0",
          mobileNav ? "translate-x-0 shadow-xl" : "-translate-x-full",
        )}
      >
        <Link href="/" className="mb-6 rounded-lg px-2 py-1" onClick={() => setMobileNav(false)}>
          <Wordmark />
        </Link>
        <Suspense fallback={<SideNav active={null} />}>
          <ActiveSideNav onNavigate={() => setMobileNav(false)} />
        </Suspense>
        <ModelCard />
      </aside>
      {mobileNav && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={() => setMobileNav(false)}
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur md:px-8">
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" onClick={() => setMobileNav(true)}>
            <Menu className="size-4" />
          </Button>
          <Suspense fallback={<span />}>
            <PageTitle />
          </Suspense>
          <button
            type="button"
            onClick={() => menu.setOpen(true)}
            className="ml-auto flex h-8 w-full max-w-64 items-center gap-2 rounded-lg border bg-muted/50 px-2.5 text-sm text-muted-foreground transition-colors hover:bg-muted"
          >
            <Search className="size-3.5" />
            <span className="flex-1 text-left">Search or jump to…</span>
            <kbd className="hidden rounded border bg-background px-1.5 font-mono text-[10px] sm:inline">Ctrl K</kbd>
          </button>
          <ThemeToggle />
        </header>
        <main className="mx-auto w-full max-w-7xl min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
          <BackendBanner />
          <Suspense fallback={null}>{children}</Suspense>
        </main>
      </div>
      <CommandMenu open={menu.open} onOpenChange={menu.setOpen} />
    </div>
  );
}

function PageTitle() {
  const item = navFor(usePathname());
  return <span className="hidden truncate text-sm font-medium text-muted-foreground sm:inline">{item?.label}</span>;
}

function ActiveSideNav({ onNavigate }: { onNavigate: () => void }) {
  return <SideNav active={usePathname()} onNavigate={onNavigate} />;
}

function SideNav({ active, onNavigate }: { active: string | null; onNavigate?: () => void }) {
  const pending = useQuery({
    queryKey: ["patches", "proposed"],
    queryFn: () => api<PatchSummary[]>("/patches?status=proposed"),
  });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<RunSummary[]>("/runs") });
  const running = runs.data?.some((r) => r.status === "running" || r.status === "queued");
  const current = navFor(active);
  return (
    <nav className="flex flex-col gap-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.label ?? "top"} className="flex flex-col gap-0.5">
          {group.label && (
            <p className="mb-1 px-2.5 text-[11px] font-semibold tracking-wider text-muted-foreground/80 uppercase">
              {group.label}
            </p>
          )}
          {group.items.map(({ href, label, icon: Icon }) => {
            const isCurrent = current?.href === href;
            const badge = href === "/patches" && pending.data?.length ? pending.data.length : null;
            return (
              <Link
                key={href}
                href={href}
                onClick={onNavigate}
                aria-current={isCurrent ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent/60",
                  isCurrent && "bg-sidebar-accent font-medium text-sidebar-accent-foreground",
                )}
              >
                <Icon className={cn("size-4 opacity-70", isCurrent && "text-primary opacity-100")} />
                <span className="flex-1">{label}</span>
                {href === "/runs" && running && (
                  <span className="relative flex size-2" aria-label="a run is in progress">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
                    <span className="relative inline-flex size-2 rounded-full bg-primary" />
                  </span>
                )}
                {badge && (
                  <span className="rounded-full bg-primary px-1.5 py-px text-[10px] font-semibold text-primary-foreground">
                    {badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function ModelCard() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("/settings") });
  const s = settings.data;
  const ready = s?.model.configured;
  return (
    <Link
      href="/settings"
      className="mt-auto flex items-center gap-2.5 rounded-lg border bg-background/60 px-3 py-2.5 text-xs transition-colors hover:bg-background"
    >
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          !s ? "bg-muted-foreground/40" : ready ? "bg-emerald-500" : "bg-amber-500",
        )}
      />
      <span className="min-w-0 flex-1">
        <span className="block font-medium text-foreground">
          {!s ? "Checking…" : ready ? "Model connected" : "No model connected"}
        </span>
        <span className="block truncate text-muted-foreground">
          {!s ? " " : ready ? (s.model.id ?? s.model.name ?? "local model") : "static analysis only"}
        </span>
      </span>
    </Link>
  );
}
