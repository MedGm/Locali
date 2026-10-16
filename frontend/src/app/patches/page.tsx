"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { KindBadge, StatusBadge } from "@/components/badges";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type PatchSummary } from "@/lib/api";

const STATUSES = ["all", "proposed", "approved", "applied", "reverted", "rejected", "stale"];

export default function PatchesPage() {
  const [status, setStatus] = useState("all");
  const patches = useQuery({
    queryKey: ["patches", status],
    queryFn: () => api<PatchSummary[]>(status === "all" ? "/patches" : `/patches?status=${status}`),
  });
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Patches</h1>
        <select
          aria-label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-8 rounded-lg border bg-transparent px-2 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      {patches.data?.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Patch</TableHead>
              <TableHead>Kind</TableHead>
              <TableHead>Run</TableHead>
              <TableHead>Files</TableHead>
              <TableHead>Validation</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Reviewer</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {patches.data.map((p) => (
              <TableRow key={p.id}>
                <TableCell>
                  <Link className="text-sm hover:underline" href={`/patches/${p.id}`}>
                    {p.title || p.id}
                  </Link>
                  <p className="font-mono text-xs text-muted-foreground">{p.id}</p>
                </TableCell>
                <TableCell>
                  <KindBadge kind={p.kind} />
                </TableCell>
                <TableCell>
                  <Link className="font-mono text-sm hover:underline" href={`/runs/${p.run_id}`}>
                    {p.run_id}
                  </Link>
                </TableCell>
                <TableCell>{p.files.length}</TableCell>
                <TableCell className={p.validation_ok ? "text-emerald-700" : "text-red-700"}>
                  {p.validation_ok ? "passed" : "failed"}
                </TableCell>
                <TableCell>
                  <StatusBadge status={p.status} />
                </TableCell>
                <TableCell>{p.reviewer ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-muted-foreground">{patches.isLoading ? "Loading…" : "No patches."}</p>
      )}
    </div>
  );
}
