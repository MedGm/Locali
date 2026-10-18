"use client";

import { useQuery } from "@tanstack/react-query";
import { FolderGit2, Search } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RepoCard } from "@/components/repo-card";
import { StartRunDialog } from "@/components/start-run";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Repo } from "@/lib/api";

const HOW = [
  { title: "Found automatically", text: "Every folder with Python code under the repositories root is listed here." },
  { title: "Run on a copy", text: "A run works in a temporary copy; your files stay as they are." },
  { title: "Results per repository", text: "The last run, open patches and merge readiness show on each card." },
  { title: "Follow the trend", text: "Quality trends compare every finished run of a repository." },
];

export default function ReposPage() {
  const repos = useQuery({ queryKey: ["repos"], queryFn: () => api<Repo[]>("/repos") });
  const [filter, setFilter] = useState("");
  const [starting, setStarting] = useState<{ open: boolean; repo?: string }>({ open: false });
  const list = (repos.data ?? []).filter((r) => r.name.toLowerCase().includes(filter.trim().toLowerCase()));
  const analysed = repos.data?.filter((r) => r.runs > 0).length ?? 0;

  return (
    <div>
      <PageHeader
        title="Repositories"
        description={
          repos.data
            ? `${repos.data.length} found, ${analysed} analysed. Pick one to scan it or run the full assistant.`
            : "The projects Locali can work on."
        }
        howItWorks={HOW}
      />

      {(repos.data?.length ?? 0) > 6 && (
        <label className="mb-4 flex max-w-sm items-center gap-2 rounded-lg border bg-card px-2.5">
          <Search className="size-4 text-muted-foreground" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by name"
            className="h-9 flex-1 bg-transparent text-sm outline-none"
          />
        </label>
      )}

      {repos.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))}
        </div>
      ) : list.length ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((r) => (
            <RepoCard key={r.name} repo={r} onRun={() => setStarting({ open: true, repo: r.name })} />
          ))}
        </div>
      ) : (
        <EmptyState icon={FolderGit2} title={filter ? "No repository matches" : "No repositories found"}>
          {filter
            ? "Try another name."
            : "Locali lists the folders with Python code under LOCALI_REPOS_ROOT. Point it at the folder that holds your projects and restart the backend."}
        </EmptyState>
      )}

      <StartRunDialog
        key={starting.repo ?? "any"}
        open={starting.open}
        repo={starting.repo}
        onOpenChange={(open) => setStarting((s) => ({ ...s, open }))}
      />
    </div>
  );
}
