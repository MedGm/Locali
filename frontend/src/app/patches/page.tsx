"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileDiff } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { KindBadge, StatusBadge } from "@/components/badges";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type PatchStatus, type PatchSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "proposed" | "approved" | "applied" | "closed" | "all";

const TABS: { value: Tab; label: string; statuses: PatchStatus[] | null; empty: string }[] = [
  { value: "proposed", label: "Waiting for you", statuses: ["proposed", "stale"], empty: "Nothing waits for your decision." },
  { value: "approved", label: "Approved", statuses: ["approved"], empty: "No approved patch waits to be applied." },
  { value: "applied", label: "Applied", statuses: ["applied"], empty: "No patch has been applied yet." },
  { value: "closed", label: "Rejected or reverted", statuses: ["rejected", "reverted"], empty: "Nothing rejected or reverted." },
  { value: "all", label: "All", statuses: null, empty: "The assistant has not proposed any change yet." },
];

const HOW = [
  { title: "Proposed", text: "The assistant turns each change (a fix, tests, docstrings) into its own patch." },
  { title: "Checked", text: "It is applied to a fresh copy: no passing test may break, no new security issue or secret." },
  { title: "Approved", text: "You approve that exact patch. If the files changed since, it becomes stale instead." },
  { title: "Applied", text: "Only now is your repository changed, with a backup. Revert puts the files back." },
];

export default function PatchesPage() {
  const [tab, setTab] = useState<Tab>("proposed");
  const patches = useQuery({ queryKey: ["patches", "all"], queryFn: () => api<PatchSummary[]>("/patches") });
  const all = patches.data ?? [];
  const count = (t: (typeof TABS)[number]) => (t.statuses ? all.filter((p) => t.statuses!.includes(p.status)).length : all.length);
  const current = TABS.find((t) => t.value === tab)!;
  const shown = current.statuses ? all.filter((p) => current.statuses!.includes(p.status)) : all;

  return (
    <div>
      <PageHeader
        title="Patches"
        description="Every change Locali proposes waits here. Your code changes only when you apply one."
        howItWorks={HOW}
      />
      <div className="mb-4">
        <Segmented value={tab} onChange={setTab} options={TABS.map((t) => ({ value: t.value, label: t.label, count: count(t) }))} />
      </div>

      {patches.isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : shown.length ? (
        <ul className="divide-y rounded-xl border bg-card">
          {shown.map((p) => (
            <li key={p.id}>
              <Link href={`/patches/${p.id}`} className="flex items-center gap-4 px-4 py-3.5 hover:bg-muted/40">
                <KindBadge kind={p.kind} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{p.title || p.id}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {p.repo.split("/").pop()} · {p.files.join(", ")}
                    {p.reviewer && ` · decided by ${p.reviewer}`}
                  </span>
                </span>
                <span
                  className={cn(
                    "hidden text-xs sm:block",
                    p.validation_ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400",
                  )}
                >
                  {p.validation_ok ? "checks passed" : "checks failed"}
                </span>
                <StatusBadge status={p.status} />
                <ArrowRight className="size-3.5 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon={FileDiff} title={current.empty}>
          {tab === "proposed" || tab === "all"
            ? "Run the full assistant on a repository; the fixes, tests and docstrings it produces appear here."
            : undefined}
        </EmptyState>
      )}
    </div>
  );
}
