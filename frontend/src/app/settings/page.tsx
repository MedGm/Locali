"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, type Settings } from "@/lib/api";

export default function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("/settings") });
  const s = settings.data;
  if (!s) return <p className="text-sm text-muted-foreground">{settings.isError ? "Could not load settings." : "Loading…"}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          What the backend is running with. Values come from environment variables and change on restart; keys and
          tokens are never shown.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Model" description={s.model.configured ? "Agent runs are enabled" : "No model: only static analysis runs"}>
          <Row label="Server" value={s.model.url} />
          <Row label="Model name" value={s.model.name} />
          <Row label="Registry id" value={s.model.id} />
          <Row label="API key" value={s.model.key_set ? "set" : "not set"} />
          <Row label="Max answer tokens" value={String(s.model.max_tokens)} />
        </Section>
        <Section title="Workflow" description={`${s.workflow.routing} routing, ${s.workflow.concurrent_runs} run at a time`}>
          <Row label="Steps" value={s.workflow.steps.join(" → ")} />
          <Row label="Static analysis" value={s.workflow.static_analysis ? "on" : "off (ablation)"} />
          <Row label="Repos root" value={s.repos_root} mono />
        </Section>
        <Section title="Sandbox" description="Where repository tests run">
          <Row label="Image" value={s.sandbox.image} mono />
          <Row label="Network" value={s.sandbox.network ? "on" : "off"} />
        </Section>
        <Section title="Access and tracking" description="Who can call the API, where runs are logged">
          <Row label="API token" value={s.api_token_set ? "required" : "not required"} />
          <Row label="MLflow tracking" value={s.mlflow.tracking ? "on" : "off"} />
          <Row label="MLflow interface" value={s.mlflow.ui} />
        </Section>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Environment variables</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Variable</TableHead>
                <TableHead>What it sets</TableHead>
                <TableHead>Current value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {s.variables.map((v) => (
                <TableRow key={v.env}>
                  <TableCell className="font-mono text-sm">{v.env}</TableCell>
                  <TableCell className="text-sm">{v.description}</TableCell>
                  <TableCell className="max-w-80 truncate font-mono text-sm">
                    {v.value ?? <span className="font-sans text-muted-foreground">not set</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-2 text-sm">{children}</dl>
      </CardContent>
    </Card>
  );
}

function Row({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={mono ? "break-all font-mono text-xs leading-5" : undefined}>
        {value ?? <span className="text-muted-foreground">not set</span>}
      </dd>
    </>
  );
}
