"use client";

import { CornerDownLeft, Moon, Play, Search } from "lucide-react";
import { useTheme } from "next-themes";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

type Command = { id: string; label: string; hint: string; icon: React.ComponentType<{ className?: string }>; run: () => void };

export function useCommandMenu() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}

export function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const commands: Command[] = useMemo(
    () => [
      { id: "start", label: "Start a run", hint: "Analyse a repository", icon: Play, run: () => router.push("/?start=1") },
      ...NAV.map((n) => ({ id: n.href, label: n.label, hint: n.hint, icon: n.icon, run: () => router.push(n.href) })),
      {
        id: "theme",
        label: resolvedTheme === "dark" ? "Use light theme" : "Use dark theme",
        hint: "Appearance",
        icon: Moon,
        run: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
      },
    ],
    [router, resolvedTheme, setTheme],
  );
  const shown = commands.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(query.trim().toLowerCase()));

  function choose(c: Command | undefined) {
    if (!c) return;
    onOpenChange(false);
    setQuery("");
    c.run();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-lg" showCloseButton={false}>
        <DialogTitle className="sr-only">Search Locali</DialogTitle>
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="size-4 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, shown.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") {
                choose(shown[active]);
              }
            }}
            placeholder="Go to a page or start a run…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {shown.map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(c)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left text-sm",
                  i === active && "bg-accent text-accent-foreground",
                )}
              >
                <c.icon className="size-4 shrink-0 opacity-70" />
                <span className="font-medium">{c.label}</span>
                <span className="truncate text-xs text-muted-foreground">{c.hint}</span>
                {i === active && <CornerDownLeft className="ml-auto size-3.5 opacity-60" />}
              </button>
            </li>
          ))}
          {!shown.length && <li className="px-3 py-6 text-center text-sm text-muted-foreground">Nothing matches.</li>}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
