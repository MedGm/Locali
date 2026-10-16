"use client";

import {
  BarChart3,
  Boxes,
  FileDiff,
  FolderGit2,
  LayoutDashboard,
  ListChecks,
  Settings,
  Shield,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/repos", label: "Repositories", icon: FolderGit2 },
  { href: "/runs", label: "Runs", icon: ListChecks },
  { href: "/patches", label: "Patches", icon: FileDiff },
  { href: "/security", label: "Security", icon: Shield },
  { href: "/models", label: "Models", icon: Boxes },
  { href: "/trends", label: "Quality trends", icon: TrendingUp },
  { href: "/results", label: "Results", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

// With cacheComponents, reading the URL (usePathname, useParams) suspends on routes with dynamic
// segments such as /runs/[id]. The parts that read it sit in Suspense boundaries so the rest of the
// shell can still be prerendered.
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r bg-muted/30 px-3 py-4">
        <Link href="/" className="mb-6 flex items-center gap-2 px-2 font-semibold">
          <ShieldCheck className="size-5 text-emerald-600" />
          Locali
        </Link>
        <Suspense fallback={<NavLinks active={null} />}>
          <ActiveNav />
        </Suspense>
        <p className="mt-auto px-2 text-xs text-muted-foreground">
          Small models, local runs, nothing changes without your approval.
        </p>
      </aside>
      <main className="min-w-0 flex-1 px-8 py-6">
        <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>{children}</Suspense>
      </main>
    </div>
  );
}

function ActiveNav() {
  return <NavLinks active={usePathname()} />;
}

function NavLinks({ active }: { active: string | null }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const current = active !== null && (href === "/" ? active === "/" : active.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground",
              current && "bg-muted font-medium text-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
