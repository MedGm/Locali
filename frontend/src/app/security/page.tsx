"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

type AuditEvent = { time: string; action: string } & Record<string, unknown>;

const SECURITY_LABELS: Record<string, { label: string; meaning: string }> = {
  "auth.refused": { label: "Refused requests", meaning: "API calls without the right token" },
  "run.refused": { label: "Refused repositories", meaning: "paths outside the repos root, or missing" },
  "command.refused": { label: "Blocked commands", meaning: "programs not on the allow-list" },
  "model.redacted": { label: "Redactions", meaning: "model calls whose text contained secrets" },
  "patch.stale": { label: "Stale patches", meaning: "files changed after a patch was proposed" },
  "patch.conflict": { label: "Conflicts", meaning: "patches that no longer applied cleanly" },
  "patch.revert_refused": { label: "Refused reverts", meaning: "reverts that would overwrite later work" },
  "patch.rejected": { label: "Rejected patches", meaning: "proposals a reviewer turned down" },
};

const DETAIL_SKIP = new Set(["time", "action"]);

export default function SecurityPage() {
  const events = useQuery({
    queryKey: ["security"],
    queryFn: () => api<{ counts: Record<string, number>; events: AuditEvent[] }>("/security/events"),
  });
  const [action, setAction] = useState("all");
  const audit = useQuery({
    queryKey: ["audit", action],
    queryFn: () => api<AuditEvent[]>(action === "all" ? "/audit?limit=500" : `/audit?limit=500&action=${action}`),
  });
  const counts = events.data?.counts ?? {};

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Security</h1>
        <p className="text-sm text-muted-foreground">
          Every action of the backend is written to an append-only audit log. This page shows what the controls
          stopped or changed.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Object.entries(SECURITY_LABELS).map(([key, { label, meaning }]) => (
          <Card key={key}>
            <CardHeader>
              <CardDescription>{label}</CardDescription>
              <CardTitle className="text-2xl tabular-nums">{counts[key] ?? 0}</CardTitle>
              <p className="text-xs text-muted-foreground">{meaning}</p>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="events">
        <TabsList>
          <TabsTrigger value="events">Security events</TabsTrigger>
          <TabsTrigger value="audit">Full audit log</TabsTrigger>
        </TabsList>
        <TabsContent value="events">
          <EventTable events={events.data?.events ?? []} />
        </TabsContent>
        <TabsContent value="audit">
          <div className="flex items-center gap-2 pt-2">
            <select
              aria-label="Action"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="h-8 rounded-lg border bg-transparent px-2 text-sm"
            >
              <option value="all">All actions</option>
              {[...new Set((audit.data ?? []).map((e) => e.action).concat(action === "all" ? [] : [action]))]
                .sort()
                .map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
            </select>
            <span className="text-xs text-muted-foreground">Newest first, last 500 entries.</span>
          </div>
          <EventTable events={audit.data ?? []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function EventTable({ events }: { events: AuditEvent[] }) {
  if (!events.length) return <p className="py-4 text-sm text-muted-foreground">Nothing recorded.</p>;
  return (
    <Card className="mt-2">
      <CardContent className="overflow-x-auto pt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((e, i) => (
              <TableRow key={`${e.time}-${i}`}>
                <TableCell className="whitespace-nowrap font-mono text-xs">{new Date(e.time).toLocaleString()}</TableCell>
                <TableCell className="font-mono text-xs">{e.action}</TableCell>
                <TableCell className="max-w-2xl whitespace-normal font-mono text-xs text-muted-foreground">
                  {Object.entries(e)
                    .filter(([k]) => !DETAIL_SKIP.has(k))
                    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
                    .join("  ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
