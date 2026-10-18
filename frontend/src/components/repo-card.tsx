"use client";

import { FileDiff, FolderGit2, GitBranch, Play, TrendingUp } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { shortDate, type Repo } from "@/lib/api";
import { cn } from "@/lib/utils";

export function RepoCard({ repo, onRun }: { repo: Repo; onRun: () => void }) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-card p-4 transition-shadow hover:shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-primary">
          <FolderGit2 className="size-4.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-medium">{repo.name}</span>
            {repo.ready_to_merge !== null && (
              <span
                className={cn(
                  "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
                  repo.ready_to_merge
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
                    : "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
                )}
              >
                {repo.ready_to_merge ? "ready to merge" : "not ready to merge"}
              </span>
            )}
          </div>
          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-muted-foreground">
            {repo.git?.branch && (
              <>
                <GitBranch className="size-3 shrink-0" />
                <span className="truncate">
                  {repo.git.branch}
                  {repo.git.last_commit && ` · ${repo.git.last_commit}`}
                </span>
                <span>·</span>
              </>
            )}
            <span className="shrink-0">
              {repo.python_files} Python file{repo.python_files === 1 ? "" : "s"}
            </span>
          </p>
        </div>
      </div>

      <div className="space-y-1.5 text-xs">
        {repo.last_run ? (
          <Link
            href={`/runs/${repo.last_run.id}`}
            className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-2.5 py-1.5 hover:bg-muted"
          >
            <span className="text-muted-foreground">
              Last {repo.last_run.mode === "agents" ? "assistant run" : "scan"} {shortDate(repo.last_run.created)}
            </span>
            <StatusBadge status={repo.last_run.status} />
          </Link>
        ) : (
          <p className="rounded-md bg-muted/50 px-2.5 py-1.5 text-muted-foreground">Not analysed yet</p>
        )}
        {repo.open_patches > 0 && (
          <Link href="/patches" className="flex items-center gap-1.5 px-2.5 font-medium text-amber-700 hover:underline dark:text-amber-400">
            <FileDiff className="size-3.5" />
            {repo.open_patches} patch{repo.open_patches === 1 ? "" : "es"} waiting for you
          </Link>
        )}
      </div>

      <div className="mt-auto flex gap-2">
        <Button size="sm" onClick={onRun}>
          <Play /> Run
        </Button>
        {repo.runs > 1 && (
          <Button size="sm" variant="ghost" render={<Link href={`/trends?repo=${encodeURIComponent(repo.name)}`} />}>
            <TrendingUp /> Trends
          </Button>
        )}
      </div>
    </div>
  );
}
