"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { StatusBadge } from "@/components/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, post, shortDate, type Repo, type RunSummary } from "@/lib/api";

export default function ReposPage() {
  const repos = useQuery({ queryKey: ["repos"], queryFn: () => api<Repo[]>("/repos") });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<{ model_configured: boolean }>("/status") });
  const router = useRouter();
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: (v: { repo: string; mode: RunSummary["mode"] }) => post<RunSummary>("/runs", v),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      router.push(`/runs/${run.id}`);
    },
    onError: (e) => toast.error(e.message),
  });
  const modelReady = status.data?.model_configured ?? false;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Repositories</h1>
        <p className="text-sm text-muted-foreground">
          Folders with Python code under the repos root. Runs never write to them; only applied patches do.
        </p>
      </div>
      {repos.data?.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Repository</TableHead>
              <TableHead>Last commit</TableHead>
              <TableHead className="text-right">Python files</TableHead>
              <TableHead>Last run</TableHead>
              <TableHead className="text-right">Open patches</TableHead>
              <TableHead>Merge</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {repos.data.map((r) => (
              <TableRow key={r.name}>
                <TableCell>
                  <div className="font-medium">{r.name}</div>
                  {r.git?.branch && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <GitBranch className="size-3" /> {r.git.branch}
                    </div>
                  )}
                </TableCell>
                <TableCell className="max-w-64 text-sm">
                  {r.git ? (
                    <>
                      <div className="truncate">{r.git.last_commit ?? "no commits"}</div>
                      <div className="text-xs text-muted-foreground">{shortDate(r.git.last_commit_date)}</div>
                    </>
                  ) : (
                    <span className="text-muted-foreground">not a git repository</span>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">{r.python_files}</TableCell>
                <TableCell>
                  {r.last_run ? (
                    <div className="flex items-center gap-2">
                      <Link href={`/runs/${r.last_run.id}`} className="font-mono text-sm hover:underline">
                        {r.last_run.id}
                      </Link>
                      <StatusBadge status={r.last_run.status} />
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">never run</span>
                  )}
                  {r.runs > 0 && (
                    <div className="text-xs text-muted-foreground">
                      {shortDate(r.last_run?.created)} · {r.runs} run{r.runs === 1 ? "" : "s"}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {r.open_patches > 0 ? (
                    <Link href="/patches" className="underline">
                      {r.open_patches}
                    </Link>
                  ) : (
                    0
                  )}
                </TableCell>
                <TableCell>
                  {r.ready_to_merge === null ? (
                    <span className="text-sm text-muted-foreground">—</span>
                  ) : r.ready_to_merge ? (
                    <Badge className="bg-emerald-100 text-emerald-800">ready</Badge>
                  ) : (
                    <Badge className="bg-red-100 text-red-800">blocked</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={start.isPending}
                      onClick={() => start.mutate({ repo: r.name, mode: "analyze" })}
                    >
                      Analyze
                    </Button>
                    <Button
                      size="sm"
                      disabled={start.isPending || !modelReady}
                      title={modelReady ? undefined : "No model configured"}
                      onClick={() => start.mutate({ repo: r.name, mode: "agents" })}
                    >
                      Run agents
                    </Button>
                    <Link
                      href={`/trends?repo=${encodeURIComponent(r.name)}`}
                      className="self-center text-sm underline"
                    >
                      Trends
                    </Link>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-muted-foreground">
          {repos.isLoading ? "Loading…" : "No folders with Python code under the repos root."}
        </p>
      )}
    </div>
  );
}
