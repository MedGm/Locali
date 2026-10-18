"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileDiff, ListChecks, Play, ScanSearch, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { StatusBadge } from "@/components/badges";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { StartRunDialog } from "@/components/start-run";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, shortDate, type RunSummary } from "@/lib/api";

type Tab = "all" | "active" | "done" | "failed";

const STEP_LABEL: Record<string, string> = {
  prepare: "copying",
  analyze: "static analysis",
  review: "model review",
  testgen: "writing tests",
  debug: "fixing tests",
  docs: "docstrings",
  propose: "proposing patches",
  devops: "merge check",
  report: "report",
};

export default function RunsPage() {
  const [tab, setTab] = useState<Tab>("all");
  const [starting, setStarting] = useState(false);
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<RunSummary[]>("/runs"),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running" || r.status === "queued") ? 2000 : false),
  });
  const all = runs.data ?? [];
  const match = (r: RunSummary, t: Tab) =>
    t === "all" || (t === "active" ? r.status === "running" || r.status === "queued" : r.status === t);
  const shown = all.filter((r) => match(r, tab));

  return (
    <div>
      <PageHeader
        title="Runs"
        description="Every scan and assistant run, newest first. Open one to see what it found and what it proposes."
        actions={
          <Button onClick={() => setStarting(true)}>
            <Play /> Start a run
          </Button>
        }
      />
      <div className="mb-4">
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { value: "all", label: "All", count: all.length },
            { value: "active", label: "In progress", count: all.filter((r) => match(r, "active")).length },
            { value: "done", label: "Finished", count: all.filter((r) => match(r, "done")).length },
            { value: "failed", label: "Failed", count: all.filter((r) => match(r, "failed")).length },
          ]}
        />
      </div>

      {runs.isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : shown.length ? (
        <ul className="divide-y rounded-xl border bg-card">
          {shown.map((r) => (
            <li key={r.id}>
              <Link href={`/runs/${r.id}`} className="flex items-center gap-4 px-4 py-3.5 hover:bg-muted/40">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-primary">
                  {r.mode === "agents" ? <Sparkles className="size-4" /> : <ScanSearch className="size-4" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{r.repo}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {r.mode === "agents" ? "Full assistant" : "Quick scan"} · {shortDate(r.created)}
                    {r.status === "running" && r.step && ` · ${STEP_LABEL[r.step] ?? r.step}`}
                    {r.status === "failed" && r.error && ` · ${r.error}`}
                  </span>
                </span>
                {r.patch_ids && r.patch_ids.length > 0 && (
                  <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
                    <FileDiff className="size-3.5" /> {r.patch_ids.length} patch{r.patch_ids.length === 1 ? "" : "es"}
                  </span>
                )}
                <StatusBadge status={r.status} />
                <ArrowRight className="size-3.5 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={ListChecks}
          title={tab === "all" ? "No runs yet" : "Nothing here"}
          action={tab === "all" ? <Button onClick={() => setStarting(true)}>Start your first run</Button> : undefined}
        >
          {tab === "all" ? "A quick scan takes about a minute and needs no model." : "No run matches this filter."}
        </EmptyState>
      )}

      <StartRunDialog open={starting} onOpenChange={setStarting} />
    </div>
  );
}
