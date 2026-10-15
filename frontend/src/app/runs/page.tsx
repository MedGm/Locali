"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { StatusBadge } from "@/components/badges";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type RunSummary } from "@/lib/api";

export default function RunsPage() {
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<RunSummary[]>("/runs"),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running" || r.status === "queued") ? 2000 : false),
  });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Runs</h1>
      {runs.data?.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Run</TableHead>
              <TableHead>Repository</TableHead>
              <TableHead>Mode</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Patch</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.data.map((r) => (
              <TableRow key={r.id}>
                <TableCell>
                  <Link className="font-mono text-sm hover:underline" href={`/runs/${r.id}`}>
                    {r.id}
                  </Link>
                </TableCell>
                <TableCell>{r.repo}</TableCell>
                <TableCell>{r.mode}</TableCell>
                <TableCell>
                  <StatusBadge status={r.status} />
                  {r.status === "running" && r.step && <span className="ml-2 text-xs text-muted-foreground">{r.step}</span>}
                </TableCell>
                <TableCell>
                  {r.patch_id ? (
                    <Link className="font-mono text-sm hover:underline" href={`/patches/${r.patch_id}`}>
                      {r.patch_id}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-muted-foreground">{runs.isLoading ? "Loading…" : "No runs yet."}</p>
      )}
    </div>
  );
}
