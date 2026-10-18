"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Bug,
  Check,
  Circle,
  FlaskConical,
  Loader2,
  RotateCw,
  ShieldAlert,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { KindBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { EmptyState } from "@/components/empty-state";
import { StartRunDialog } from "@/components/start-run";
import { Term } from "@/components/term";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useApiQuery } from "@/lib/use-hydrated";
import { api, PIPELINE, shortDate, type Devops, type Finding, type ModelCall, type Run } from "@/lib/api";
import { cn } from "@/lib/utils";

const STEPS: Record<string, { label: string; text: string }> = {
  prepare: { label: "Copy", text: "Making a private copy of the repository to work on." },
  analyze: { label: "Static analysis", text: "Ruff, Bandit, Radon, Semgrep and the secret scanner read the code." },
  review: { label: "Model review", text: "The model reviews each function for bugs and security issues." },
  testgen: { label: "Write tests", text: "The model writes regression tests; they run in the sandbox." },
  debug: { label: "Fix failing tests", text: "Failing tests go to the model with their error, up to three attempts." },
  docs: { label: "Docstrings", text: "Undocumented public functions get a one-line docstring." },
  propose: { label: "Propose patches", text: "Each change is checked alone on a fresh copy." },
  devops: { label: "Merge check", text: "Blockers, dependencies and CI for this repository." },
  report: { label: "Report", text: "Writing the summary." },
};

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [again, setAgain] = useState(false);
  // Live progress: the backend streams the run's state and any change refreshes the run. The browser
  // reconnects the stream by itself after an error; slow polling is a safety net on top of that.
  const run = useApiQuery({
    queryKey: ["run", id],
    queryFn: () => api<Run>(`/runs/${id}`),
    refetchInterval: (q) => (q.state.data?.status === "queued" || q.state.data?.status === "running" ? 5000 : false),
  });
  const live = run.data && (run.data.status === "queued" || run.data.status === "running");
  useEffect(() => {
    if (!live) return;
    const events = new EventSource(`/api/runs/${id}/events`);
    events.onmessage = () => queryClient.invalidateQueries({ queryKey: ["run", id] });
    return () => events.close();
  }, [id, live, queryClient]);

  if (run.isError)
    return (
      <EmptyState icon={X} title="Run not found" action={<Button render={<Link href="/runs" />}>All runs</Button>}>
        It may have been made with another data folder.
      </EmptyState>
    );
  if (!run.data)
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-12 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
    );
  const r = run.data;
  const agents = r.mode === "agents";

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Link href="/runs" className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" /> All runs
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl font-semibold tracking-tight">{r.repo}</h1>
              <StatusBadge status={r.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {agents ? "Full assistant run" : "Quick scan"} · {shortDate(r.created)} ·{" "}
              <span className="font-mono text-xs">{r.id}</span>
            </p>
          </div>
          {!live && (
            <Button variant="outline" onClick={() => setAgain(true)}>
              <RotateCw /> Run again
            </Button>
          )}
        </div>
      </div>

      {agents && <Pipeline run={r} />}

      {live && r.step && STEPS[r.step] && (
        <div className="flex items-center gap-3 rounded-xl border border-primary/30 bg-accent/40 px-4 py-3 text-sm">
          <Loader2 className="size-4 animate-spin text-primary" />
          <span>
            <span className="font-medium">{STEPS[r.step].label}.</span>{" "}
            <span className="text-muted-foreground">{STEPS[r.step].text}</span>
          </span>
          <span className="ml-auto hidden text-xs text-muted-foreground sm:block">
            A full run takes 10–15 minutes on a laptop CPU. You can leave this page.
          </span>
        </div>
      )}

      {r.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>The run stopped with an error</AlertTitle>
          <AlertDescription>{r.error}</AlertDescription>
        </Alert>
      )}

      <Summary run={r} />

      {r.patches && r.patches.length > 0 && (
        <section className="rounded-xl border border-amber-300/70 bg-amber-50/60 p-4 dark:border-amber-500/30 dark:bg-amber-500/5">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-semibold">
              {r.patches.length} change{r.patches.length === 1 ? "" : "s"} waiting for your decision
            </h2>
            <p className="text-xs text-muted-foreground">
              Each <Term name="patch">patch</Term> is separate: accept the fix and reject a test, or the other way round.
              Nothing has been written to the repository.
            </p>
          </div>
          <ul className="space-y-2">
            {r.patches.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/patches/${p.id}`}
                  className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5 transition-colors hover:border-primary/40"
                >
                  <KindBadge kind={p.kind} />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{p.title}</span>
                  <span
                    className={cn(
                      "hidden text-xs sm:block",
                      p.ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400",
                    )}
                  >
                    {p.ok ? "checks passed" : "checks failed"}
                  </span>
                  <span className="flex items-center gap-1 text-xs font-medium text-primary">
                    Review <ArrowRight className="size-3.5" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Tabs defaultValue="findings">
        <TabsList className="max-w-full justify-start overflow-x-auto">
          <TabsTrigger value="findings">Findings ({r.findings?.length ?? 0})</TabsTrigger>
          {agents && (
            <>
              <TabsTrigger value="tests">Tests & suspects</TabsTrigger>
              <TabsTrigger value="fixes">Fixes ({r.fixes?.length ?? 0})</TabsTrigger>
              <TabsTrigger value="devops">Merge check</TabsTrigger>
              <TabsTrigger value="trajectory">Model calls</TabsTrigger>
              <TabsTrigger value="report">Report</TabsTrigger>
            </>
          )}
        </TabsList>
        <TabsContent value="findings">
          <Findings findings={r.findings ?? []} />
        </TabsContent>
        <TabsContent value="tests">
          <TestsAndSuspects run={r} />
        </TabsContent>
        <TabsContent value="fixes">
          <Fixes run={r} />
        </TabsContent>
        <TabsContent value="trajectory">
          <Trajectory id={r.id} live={!!live} />
        </TabsContent>
        <TabsContent value="devops">
          {r.devops ? (
            <DevopsPanel devops={r.devops} />
          ) : (
            <p className="py-4 text-sm text-muted-foreground">
              {live ? "Not ready yet." : "This run was made before the merge check existed."}
            </p>
          )}
        </TabsContent>
        <TabsContent value="report">
          <pre className="whitespace-pre-wrap rounded-xl border bg-muted/30 p-4 font-mono text-xs leading-relaxed">
            {r.report ?? "Not ready yet."}
          </pre>
        </TabsContent>
      </Tabs>

      <StartRunDialog open={again} repo={r.repo} onOpenChange={setAgain} />
    </div>
  );
}

function Summary({ run }: { run: Run }) {
  const findings = run.findings ?? [];
  const high = findings.filter((f) => f.severity === "high").length;
  const toolSecurity = findings.filter((f) => f.category === "security" && f.tool !== "model").length;
  const tiles: { icon: typeof Bug; label: string; value: React.ReactNode; note: string }[] = [
    { icon: Bug, label: "Findings", value: findings.length, note: high ? `${high} high severity` : "none high severity" },
    { icon: ShieldAlert, label: "Security issues", value: toolSecurity, note: "found by the static tools" },
  ];
  if (run.mode === "agents") {
    const fixed = run.fixes?.filter((f) => f.fixed).length ?? 0;
    tiles.push(
      { icon: FlaskConical, label: "Tests added", value: run.tests_added?.length ?? 0, note: `${run.suspects?.length ?? 0} possible bugs to check` },
      { icon: Wrench, label: "Bugs fixed", value: `${fixed} / ${run.fixes?.length ?? 0}`, note: "failing tests repaired" },
    );
  }
  return (
    <section className={cn("grid gap-3 sm:grid-cols-2", run.mode === "agents" ? "lg:grid-cols-4" : "lg:grid-cols-2")}>
      {tiles.map((t) => (
        <div key={t.label} className="flex items-center gap-3 rounded-xl border bg-card p-4">
          <span className="flex size-9 items-center justify-center rounded-lg bg-brand-soft text-primary">
            <t.icon className="size-4.5" />
          </span>
          <span>
            <span className="block text-xs text-muted-foreground">{t.label}</span>
            <span className="block text-xl font-semibold tabular-nums">{t.value}</span>
            <span className="block text-xs text-muted-foreground">{t.note}</span>
          </span>
        </div>
      ))}
    </section>
  );
}

function Pipeline({ run }: { run: Run }) {
  const done = new Set(run.steps_done ?? []);
  const finished = run.status === "done" || run.status === "failed";
  const steps = PIPELINE.filter((s) => s !== "analyze" || done.has("analyze") || run.step === "analyze" || !finished);
  return (
    <ol className="flex flex-wrap items-center gap-1.5">
      {steps.map((step, i) => {
        const state = done.has(step)
          ? "done"
          : run.step === step
            ? run.status === "failed"
              ? "failed"
              : "running"
            : finished
              ? "skipped"
              : "pending";
        const info = STEPS[step];
        return (
          <li key={step} className="flex items-center gap-1.5">
            <Tooltip>
              <TooltipTrigger
                render={<span />}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                  state === "done" && "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300",
                  state === "running" && "border-primary/40 bg-accent text-accent-foreground",
                  state === "failed" && "border-red-300 bg-red-50 text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300",
                  state === "pending" && "text-muted-foreground",
                  state === "skipped" && "border-dashed text-muted-foreground/70",
                )}
              >
                {state === "done" && <Check className="size-3.5" />}
                {state === "running" && <Loader2 className="size-3.5 animate-spin" />}
                {state === "failed" && <X className="size-3.5" />}
                {(state === "pending" || state === "skipped") && <Circle className="size-3.5" />}
                {info?.label ?? step}
              </TooltipTrigger>
              <TooltipContent>
                {state === "skipped" ? "Not part of this run (made before this step existed)." : info?.text}
              </TooltipContent>
            </Tooltip>
            {i < steps.length - 1 && <span className="h-px w-3 bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}

function Findings({ findings }: { findings: Finding[] }) {
  const [source, setSource] = useState("all");
  const [category, setCategory] = useState("all");
  const [text, setText] = useState("");
  const tools = useMemo(() => [...new Set(findings.map((f) => f.tool))].sort(), [findings]);
  const shown = findings.filter(
    (f) =>
      (source === "all" || f.tool === source) &&
      (category === "all" || f.category === category) &&
      (!text || `${f.path} ${f.message}`.toLowerCase().includes(text.toLowerCase())),
  );
  if (!findings.length) return <p className="py-4 text-sm text-muted-foreground">No findings.</p>;

  return (
    <div className="space-y-3 pt-2">
      <div className="flex flex-wrap gap-2">
        <Filter value={source} onChange={setSource} label="Source" all="All sources" options={tools} />
        <Filter value={category} onChange={setCategory} label="Category" all="All categories" options={["bug", "security", "quality"]} />
        <Input placeholder="Search file or message" value={text} onChange={(e) => setText(e.target.value)} className="w-64" />
        <span className="self-center text-xs text-muted-foreground">
          {shown.length} of {findings.length}. Findings from the model are a second opinion; the static tools are
          the reliable source for security issues.
        </span>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Severity</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Message</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shown.map((f, i) => (
            <TableRow key={`${f.tool}-${f.path}-${f.line}-${i}`}>
              <TableCell>
                <SeverityBadge severity={f.severity} />
              </TableCell>
              <TableCell>{f.category}</TableCell>
              <TableCell>
                <Badge variant={f.tool === "model" ? "outline" : "secondary"}>
                  {f.tool === "model" ? "model review" : `${f.tool} ${f.rule}`}
                </Badge>
              </TableCell>
              <TableCell className="font-mono text-xs">
                {f.path}:{f.line}
              </TableCell>
              <TableCell className="max-w-xl whitespace-normal text-sm">{f.message}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Filter(props: { label: string; all: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <select
      aria-label={props.label}
      value={props.value}
      onChange={(e) => props.onChange(e.target.value)}
      className="h-8 rounded-lg border bg-transparent px-2 text-sm"
    >
      <option value="all">{props.all}</option>
      {props.options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function TestsAndSuspects({ run }: { run: Run }) {
  return (
    <div className="grid gap-6 pt-2 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Tests added</CardTitle>
          <CardDescription>Generated tests that pass on the current code; they become regression tests.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {run.tests_added?.length ? (
            <ul className="list-inside list-disc font-mono text-xs">
              {run.tests_added.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground">None.</p>
          )}
          <p className="text-xs text-muted-foreground">
            Each test file is its own patch. Tests are not generated for functions with a security finding, and a
            function with a suspected bug keeps none: a passing test records what the code does now, bug included.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Suspected bugs ({run.suspects?.length ?? 0})</CardTitle>
          <CardDescription>
            Generated tests whose assertion failed. Either the code is wrong or the test is: check the test first.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {run.suspects?.length ? (
            run.suspects.map((s, i) => (
              <details key={i} className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm">
                  <span className="font-mono">
                    {s.file}::{s.function}
                  </span>{" "}
                  <span className="text-muted-foreground">— {s.error.split("\n")[0]}</span>
                </summary>
                <pre className="mt-2 overflow-x-auto rounded bg-muted/40 p-2 text-xs">{s.test}</pre>
                <pre className="mt-2 overflow-x-auto rounded bg-red-50 p-2 text-xs text-red-900">{s.error}</pre>
              </details>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">None.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Fixes({ run }: { run: Run }) {
  if (!run.fixes?.length) return <p className="py-4 text-sm text-muted-foreground">No failing tests to fix.</p>;
  return (
    <div className="space-y-3 pt-2">
      {run.fixes.map((f) => (
        <Card key={f.test}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-mono text-sm">
              {f.test}
              <Badge className={f.fixed ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}>
                {f.fixed ? `fixed in ${f.attempts} attempt${f.attempts === 1 ? "" : "s"}` : `not fixed after ${f.attempts}`}
              </Badge>
            </CardTitle>
            <CardDescription className="font-mono">
              {f.file}::{f.function}
            </CardDescription>
          </CardHeader>
          {f.diagnosis && (
            <CardContent className="space-y-1 text-sm">
              <p>
                <span className="text-muted-foreground">Bug:</span>{" "}
                <code className="rounded bg-muted px-1">{f.diagnosis.bug_location?.trim()}</code> ({f.diagnosis.bug_type})
              </p>
              <p>{f.diagnosis.explanation}</p>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}

function Trajectory({ id, live }: { id: string; live: boolean }) {
  const calls = useApiQuery({
    queryKey: ["trajectory", id],
    queryFn: () => api<ModelCall[]>(`/runs/${id}/trajectory`),
    refetchInterval: live ? 3000 : false,
  });
  const data = calls.data ?? [];
  const totals = data.reduce(
    (t, c) => ({ out: t.out + (c.output_tokens ?? 0), in: t.in + (c.input_tokens ?? 0), s: t.s + c.latency_s }),
    { out: 0, in: 0, s: 0 },
  );
  if (!data.length) return <p className="py-4 text-sm text-muted-foreground">No model calls yet.</p>;
  return (
    <div className="space-y-3 pt-2">
      <p className="text-sm text-muted-foreground">
        {data.length} calls · {totals.in.toLocaleString()} tokens in · {totals.out.toLocaleString()} tokens out ·{" "}
        {totals.s.toFixed(0)} s of generation. Prompts and answers are shown as the model saw them, with secrets
        redacted.
      </p>
      {data.map((c, i) => (
        <details key={i} className="rounded-md border p-3">
          <summary className="flex cursor-pointer flex-wrap items-center gap-3 text-sm">
            <span className="w-8 text-muted-foreground">#{i + 1}</span>
            <Badge variant="secondary">{c.step}</Badge>
            <span className="text-muted-foreground">
              {c.output_tokens ?? "?"} tokens out · {c.latency_s.toFixed(1)} s
            </span>
            <span className="truncate text-muted-foreground">{c.prompt.split("\n")[0]}</span>
          </summary>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <pre className="max-h-96 overflow-auto rounded bg-muted/40 p-2 text-xs whitespace-pre-wrap">{c.prompt}</pre>
            <pre className="max-h-96 overflow-auto rounded bg-sky-50 p-2 text-xs whitespace-pre-wrap">{c.answer}</pre>
          </div>
        </details>
      ))}
    </div>
  );
}

function DevopsPanel({ devops }: { devops: Devops }) {
  return (
    <div className="space-y-4">
      <Alert variant={devops.ready_to_merge ? "default" : "destructive"}>
        <AlertTitle>{devops.ready_to_merge ? "Ready to merge" : "Not ready to merge"}</AlertTitle>
        <AlertDescription>
          {devops.blockers.length ? (
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {devops.blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : (
            "No blockers found."
          )}
        </AlertDescription>
      </Alert>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Warnings</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {devops.warnings.length ? (
              <ul className="list-disc space-y-1 pl-4">
                {devops.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">None.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Dependencies</CardTitle>
            <CardDescription>Names one edit away from a popular package (possible typosquats)</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {devops.dependencies.length ? (
              <ul className="space-y-1">
                {devops.dependencies.map((d) => (
                  <li key={`${d.file}:${d.name}`}>
                    <span className="font-mono">{d.name}</span> looks like <span className="font-mono">{d.looks_like}</span>{" "}
                    <span className="text-muted-foreground">({d.file})</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">Nothing suspicious.</p>
            )}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">CI</CardTitle>
          <CardDescription>
            {devops.ci.workflows.length ? `Workflows: ${devops.ci.workflows.join(", ")}` : "No GitHub workflows."}
            {devops.ci.has_ci && !devops.ci.has_locali_review && " None of them reviews pull requests for security issues."}
          </CardDescription>
        </CardHeader>
        {devops.suggested_workflow && (
          <CardContent>
            <p className="mb-2 text-sm">A workflow to start from (.github/workflows/ci.yml):</p>
            <pre className="overflow-x-auto rounded-md border bg-muted/30 p-3 text-xs">{devops.suggested_workflow}</pre>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
