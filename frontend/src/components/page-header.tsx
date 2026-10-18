"use client";

import { ChevronDown, Lightbulb } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

// Title, one sentence on what the page is for, and an optional "How this works" panel for people
// who have never used Locali.
export function PageHeader({
  title,
  description,
  actions,
  howItWorks,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  howItWorks?: { title: string; text: string }[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-6 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {howItWorks && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-expanded={open}
            >
              <Lightbulb className="size-3.5" />
              How this works
              <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
            </button>
          )}
          {actions}
        </div>
      </div>
      {howItWorks && open && (
        <ol className="grid gap-3 rounded-xl border bg-brand-soft/50 p-4 sm:grid-cols-2 lg:grid-cols-4">
          {howItWorks.map((step, i) => (
            <li key={step.title} className="flex gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                {i + 1}
              </span>
              <span className="space-y-0.5">
                <span className="block text-sm font-medium">{step.title}</span>
                <span className="block text-xs text-muted-foreground">{step.text}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
