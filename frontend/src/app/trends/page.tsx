"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PageHeader } from "@/components/page-header";
import { RunLines } from "@/components/charts/lines";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApiQuery } from "@/lib/use-hydrated";
import { api, shortDate, type Repo, type TrendPoint } from "@/lib/api";

const FINDINGS = [
  { key: "bug", label: "Bugs", color: "var(--viz-series-1)" },
  { key: "security", label: "Security", color: "var(--viz-series-2)" },
  { key: "quality", label: "Quality", color: "var(--viz-series-3)" },
];

export default function TrendsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <Trends />
    </Suspense>
  );
}

function Trends() {
  const params = useSearchParams();
  const router = useRouter();
  const repos = useApiQuery({ queryKey: ["repos"], queryFn: () => api<Repo[]>("/repos") });
  const repo = params.get("repo") ?? repos.data?.find((r) => r.runs > 0)?.name ?? repos.data?.[0]?.name;
  const points = useApiQuery({
    queryKey: ["trends", repo],
    queryFn: () => api<TrendPoint[]>(`/trends?repo=${encodeURIComponent(repo!)}`),
    enabled: !!repo,
  });
  const data = (points.data ?? []).map((p) => ({ label: shortDate(p.created).slice(5), ...p.findings }));
  const coverage = (points.data ?? [])
    .filter((p) => p.coverage_percent != null)
    .map((p) => ({ label: shortDate(p.created).slice(5), coverage: p.coverage_percent }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Quality trends"
        description="How each finished run of a repository compares with the ones before: findings, tests, coverage and merge readiness."
        actions={
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Repository</span>
          <select
            value={repo ?? ""}
            onChange={(e) => router.replace(`/trends?repo=${encodeURIComponent(e.target.value)}`)}
            className="h-8 rounded-lg border bg-transparent px-2 text-sm"
          >
            {repos.data?.map((r) => (
              <option key={r.name} value={r.name}>
                {r.name} ({r.runs} run{r.runs === 1 ? "" : "s"})
              </option>
            ))}
          </select>
        </label>
        }
      />

      {!points.data?.length ? (
        <p className="text-sm text-muted-foreground">
          {points.isLoading ? "Loading…" : "No finished runs for this repository yet."}
        </p>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Findings per run</CardTitle>
                <CardDescription>Static tools and, in agent runs, the model review</CardDescription>
              </CardHeader>
              <CardContent>
                <RunLines data={data} series={FINDINGS} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Test coverage</CardTitle>
                <CardDescription>Measured before any change, in agent runs only</CardDescription>
              </CardHeader>
              <CardContent>
                {coverage.length ? (
                  <RunLines
                    data={coverage}
                    series={[{ key: "coverage", label: "Coverage", color: "var(--viz-series-1)" }]}
                    unit="%"
                    max={100}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">No agent runs with coverage yet.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead className="text-right">Bugs</TableHead>
                <TableHead className="text-right">Security (high)</TableHead>
                <TableHead className="text-right">Quality</TableHead>
                <TableHead className="text-right">Tests passed / failed</TableHead>
                <TableHead className="text-right">Coverage</TableHead>
                <TableHead className="text-right">Patches validated</TableHead>
                <TableHead>Merge</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[...points.data].reverse().map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/runs/${p.id}`} className="font-mono text-sm hover:underline">
                      {p.id}
                    </Link>
                  </TableCell>
                  <TableCell>{shortDate(p.created)}</TableCell>
                  <TableCell>{p.mode}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.findings.bug}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {p.findings.security} ({p.high_security})
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{p.findings.quality}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {p.tests_passed == null ? "—" : `${p.tests_passed} / ${p.tests_failed}`}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {p.coverage_percent == null ? "—" : `${p.coverage_percent.toFixed(1)}%`}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {p.mode === "agents" ? `${p.patches_validated} / ${p.patches}` : "—"}
                  </TableCell>
                  <TableCell>{p.ready_to_merge == null ? "—" : p.ready_to_merge ? "ready" : "blocked"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}
