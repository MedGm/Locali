"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, post, type PatchSummary, type RunSummary } from "@/lib/api";

export default function Dashboard() {
  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => api<{ model_configured: boolean; static_analysis: boolean }>("/status"),
  });
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<RunSummary[]>("/runs"),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running" || r.status === "queued") ? 2000 : false),
  });
  const pending = useQuery({ queryKey: ["patches", "proposed"], queryFn: () => api<PatchSummary[]>("/patches?status=proposed") });

  const counts = {
    runs: runs.data?.length ?? 0,
    running: runs.data?.filter((r) => r.status === "running" || r.status === "queued").length ?? 0,
    pending: pending.data?.length ?? 0,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Start a run on a repository and review what it proposes.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Model" value={status.data ? (status.data.model_configured ? "connected" : "not configured") : "…"} />
        <Stat label="Runs" value={counts.runs} />
        <Stat label="In progress" value={counts.running} />
        <Stat label="Patches awaiting review" value={counts.pending} highlight={counts.pending > 0} />
      </div>

      <NewRun modelReady={status.data?.model_configured ?? false} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent runs</CardTitle>
          </CardHeader>
          <CardContent>
            {runs.data?.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Run</TableHead>
                    <TableHead>Repository</TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.data.slice(0, 8).map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        <Link className="font-mono text-sm underline-offset-2 hover:underline" href={`/runs/${r.id}`}>
                          {r.id}
                        </Link>
                      </TableCell>
                      <TableCell>{r.repo}</TableCell>
                      <TableCell>{r.mode}</TableCell>
                      <TableCell>
                        <StatusBadge status={r.status} />
                        {r.status === "running" && r.step && (
                          <span className="ml-2 text-xs text-muted-foreground">{r.step}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No runs yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Awaiting your review</CardTitle>
            <CardDescription>Nothing is written to a repository until you approve and apply a patch.</CardDescription>
          </CardHeader>
          <CardContent>
            {pending.data?.length ? (
              <ul className="space-y-2">
                {pending.data.map((p) => (
                  <li key={p.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <div>
                      <Link className="font-mono text-sm hover:underline" href={`/patches/${p.id}`}>
                        {p.id}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {p.files.length} file{p.files.length === 1 ? "" : "s"} · run {p.run_id}
                      </p>
                    </div>
                    <span className={p.validation_ok ? "text-xs text-emerald-700" : "text-xs text-red-700"}>
                      {p.validation_ok ? "validation passed" : "validation failed"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Nothing to review.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: React.ReactNode; highlight?: boolean }) {
  return (
    <Card className={highlight ? "border-amber-300" : undefined}>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  );
}

function NewRun({ modelReady }: { modelReady: boolean }) {
  const [repo, setRepo] = useState("demo_repo");
  const [mode, setMode] = useState<"agents" | "analyze">("agents");
  const router = useRouter();
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: () => post<RunSummary>("/runs", { repo, mode }),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      router.push(`/runs/${run.id}`);
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>New run</CardTitle>
        <CardDescription>
          The repository path is relative to the configured repos root. Agent runs work in an isolated copy.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            start.mutate();
          }}
        >
          <label className="grid gap-1 text-sm">
            Repository
            <Input value={repo} onChange={(e) => setRepo(e.target.value)} className="w-64" />
          </label>
          <label className="grid gap-1 text-sm">
            Mode
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "agents" | "analyze")}
              className="h-8 rounded-lg border bg-transparent px-2 text-sm"
            >
              <option value="agents">Agents (review, tests, fixes)</option>
              <option value="analyze">Static analysis only</option>
            </select>
          </label>
          <Button type="submit" disabled={start.isPending || (mode === "agents" && !modelReady)}>
            {start.isPending ? "Starting…" : "Start run"}
          </Button>
          {mode === "agents" && !modelReady && (
            <span className="text-xs text-muted-foreground">Agent runs need a model (LOCALI_MODEL_URL).</span>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
