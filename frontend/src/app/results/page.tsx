"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { HorizontalBars } from "@/components/charts/bars";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MlflowLink } from "@/components/mlflow-link";
import { api } from "@/lib/api";

type Test = { n: number; only_a: number; only_b: number; p: number } | null;
type FtRow = {
  task: string;
  label: string;
  family: "bench" | "format" | "internal";
  base: number | null;
  v1: number | null;
  qlora_v2: number | null;
  lora16_v2: number | null;
  rslora_v2: number | null;
  phi_base: number | null;
  phi_qlora_v2: number | null;
  tests: { base_vs_qlora_v2: Test; v1_vs_qlora_v2: Test; phi_base_vs_phi_v2: Test };
};
type LadderTask = { score: number; tokens_per_s: number; j_per_item: number; j_per_solved: number | null; output_tokens: number };
type LadderRow = { model: string; quant: string; peak_ram_gb: number | null; tasks: Record<string, LadderTask> };
type Summary = {
  generated_at: string;
  baselines: {
    note: string;
    systems: string[];
    rows: { task: string; label: string; systems: Record<string, { score: number | null; gpu_j_per_item: number | null }> }[];
  };
  finetuning: { note: string; rows: FtRow[] };
  ladder: { note: string; rows: LadderRow[] };
  context_ablation: {
    note: string;
    rows: { variant: string; score: number; input_tokens: number; output_tokens: number; gpu_j: number | null;
      vs_standard: { only_standard: number; only_variant: number; p: number } | null }[];
  };
  agents: {
    note: string;
    rows: { variant: string; bugs: Record<string, string>; security: Record<string, boolean>;
      secrets: Record<string, boolean>; false_positives: number; model_calls: number; output_tokens: number }[];
  };
  agent_context: {
    note: string;
    rows: { context: string; review_input: number; testgen_input: number; input_tokens: number; output_tokens: number;
      minutes: number; review_hits: number; model_false_positives: number; fixed: number; found: number;
      suspected: number; tests_kept: number; tests_crashed: number }[];
  };
  redteam: {
    controls: { threat: string; on: number; off: number; cases: number }[];
    cases: { id: string; threat: string; attack: string; control: string; detail: string }[];
    model: { threat: string; attacks: number; complied: number; harm_with: number; harm_without: number }[];
  };
  serving: {
    note: string;
    vllm: { config: string; warm: boolean; workers: number; throughput: number; ttft_s: number; request_s: number;
      j_per_item: number; pass1: number }[];
    transformers: { run: string; batch: number; use_cache: boolean; tokens_per_s: number; peak_memory_gb: number;
      usable: string }[];
  };
  multilang: {
    note: string;
    rows: { language: string; n: number; base: number; ft: number; change: number; only_base: number; only_ft: number;
      p: number; excluded: string[] }[];
  };
};

const BASE = "var(--viz-series-1)";
const TUNED = "var(--viz-series-2)";

const fmtP = (t: Test) => (t ? (t.p < 0.001 ? "< 0.001" : t.p.toFixed(3)) : "—");
const mark = (t: Test) => (t && t.p < 0.05 ? " *" : "");

export default function ResultsPage() {
  const summary = useQuery({ queryKey: ["results"], queryFn: () => api<Summary>("/results") });
  if (summary.isError)
    return (
      <EmptyState icon={BarChart3} title="No results summary yet">
        Run experiments/scripts/export_results.py to build it from the experiment folders.
      </EmptyState>
    );
  if (!summary.data) return <Skeleton className="h-96 rounded-xl" />;
  const s = summary.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research results"
        description={
          <>
            The measurements behind the model Locali runs: how fine-tuning changed it, how it compares with other
            models, what compression costs. Exported {new Date(s.generated_at).toLocaleString()}; every comparison is
            paired on the same items, * marks p &lt; 0.05 (exact McNemar test).
          </>
        }
        actions={<MlflowLink />}
      />
      <Tabs defaultValue="finetuning">
        <TabsList>
          <TabsTrigger value="finetuning">Fine-tuning</TabsTrigger>
          <TabsTrigger value="baselines">Model baselines</TabsTrigger>
          <TabsTrigger value="ladder">Quantization</TabsTrigger>
          <TabsTrigger value="context">Context</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="languages">Other languages</TabsTrigger>
          <TabsTrigger value="serving">Serving</TabsTrigger>
          <TabsTrigger value="redteam">Red-team</TabsTrigger>
        </TabsList>
        <TabsContent value="finetuning">
          <FineTuning rows={s.finetuning.rows} note={s.finetuning.note} />
        </TabsContent>
        <TabsContent value="baselines">
          <Baselines data={s.baselines} />
        </TabsContent>
        <TabsContent value="ladder">
          <Ladder data={s.ladder} />
        </TabsContent>
        <TabsContent value="context" className="space-y-4">
          <Context data={s.context_ablation} />
          <AgentContext data={s.agent_context} />
        </TabsContent>
        <TabsContent value="languages">
          <Languages data={s.multilang} />
        </TabsContent>
        <TabsContent value="serving">
          <Serving data={s.serving} />
        </TabsContent>
        <TabsContent value="redteam">
          <RedTeam data={s.redteam} />
        </TabsContent>
        <TabsContent value="agents">
          <Agents data={s.agents} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FineTuning({ rows, note }: { rows: FtRow[]; note: string }) {
  const chart = (family: FtRow["family"]) =>
    rows
      .filter((r) => r.family === family)
      .map((r) => ({ label: r.label + mark(r.tests.base_vs_qlora_v2), base: r.base, tuned: r.qlora_v2 }));
  const series = [
    { key: "base", label: "Base model", color: BASE },
    { key: "tuned", label: "Fine-tuned (QLoRA v2)", color: TUNED },
  ];
  return (
    <div className="space-y-6 pt-2">
      <p className="text-sm text-muted-foreground">{note}</p>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Benchmarks</CardTitle>
            <CardDescription>Qwen2.5-Coder-1.5B, % of items solved, before and after fine-tuning.</CardDescription>
          </CardHeader>
          <CardContent>
            <HorizontalBars data={chart("bench")} series={series} unit="%" max={100} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Trained formats and held-out training problems</CardTitle>
            <CardDescription>The same model on tasks asked the way it was trained.</CardDescription>
          </CardHeader>
          <CardContent>
            <HorizontalBars data={[...chart("format"), ...chart("internal")]} series={series} unit="%" max={100} />
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>All variants</CardTitle>
          <CardDescription>
            v1 / v2 are the two training mixtures; 16-bit LoRA and rsLoRA use the v2 data. p compares with the
            row&apos;s baseline.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Task</TableHead>
                <TableHead className="text-right">Base</TableHead>
                <TableHead className="text-right">v1</TableHead>
                <TableHead className="text-right">QLoRA v2</TableHead>
                <TableHead className="text-right">p vs base</TableHead>
                <TableHead className="text-right">16-bit LoRA</TableHead>
                <TableHead className="text-right">rsLoRA</TableHead>
                <TableHead className="text-right">Phi-4-mini</TableHead>
                <TableHead className="text-right">Phi QLoRA v2</TableHead>
                <TableHead className="text-right">p (Phi)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.task}>
                  <TableCell>{r.label}</TableCell>
                  <Num v={r.base} />
                  <Num v={r.v1} />
                  <Num v={r.qlora_v2} strong />
                  <TableCell className="text-right font-mono text-xs">{fmtP(r.tests.base_vs_qlora_v2)}</TableCell>
                  <Num v={r.lora16_v2} />
                  <Num v={r.rslora_v2} />
                  <Num v={r.phi_base} />
                  <Num v={r.phi_qlora_v2} />
                  <TableCell className="text-right font-mono text-xs">{fmtP(r.tests.phi_base_vs_phi_v2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Num({ v, strong }: { v: number | null; strong?: boolean }) {
  return <TableCell className={`text-right tabular-nums ${strong ? "font-medium" : ""}`}>{v ?? "—"}</TableCell>;
}

function Baselines({ data }: { data: Summary["baselines"] }) {
  return (
    <Card className="mt-2">
      <CardHeader>
        <CardTitle>Before fine-tuning: five models on ten tasks</CardTitle>
        <CardDescription>{data.note} % of items solved; GPU energy per item below each score.</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Task</TableHead>
              {data.systems.map((sys) => (
                <TableHead key={sys} className="text-right">
                  {sys}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r) => (
              <TableRow key={r.task}>
                <TableCell>{r.label}</TableCell>
                {data.systems.map((sys) => (
                  <TableCell key={sys} className="text-right tabular-nums">
                    {r.systems[sys]?.score ?? "—"}
                    <span className="block text-xs text-muted-foreground">
                      {r.systems[sys]?.gpu_j_per_item != null ? `${r.systems[sys].gpu_j_per_item} J` : ""}
                    </span>
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function Ladder({ data }: { data: Summary["ladder"] }) {
  const name = (r: LadderRow) => `${r.model === "base" ? "Base" : "Fine-tuned"} ${r.quant}`;
  const score = data.rows.map((r) => ({ label: name(r), value: r.tasks.humaneval_plus?.score ?? null }));
  const speed = data.rows.map((r) => ({ label: name(r), value: r.tasks.humaneval_plus?.tokens_per_s ?? null }));
  return (
    <div className="space-y-6 pt-2">
      <p className="text-sm text-muted-foreground">{data.note}</p>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>HumanEval+, % solved</CardTitle>
          </CardHeader>
          <CardContent>
            <HorizontalBars data={score} series={[{ key: "value", label: "% solved", color: BASE }]} unit="%" max={100} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Decoding speed, tokens per second</CardTitle>
          </CardHeader>
          <CardContent>
            <HorizontalBars data={speed} series={[{ key: "value", label: "tokens/s", color: BASE }]} />
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Every format</CardTitle>
          <CardDescription>Energy is CPU package energy; &ldquo;per solved&rdquo; divides by the items the model got right.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Peak RAM</TableHead>
                <TableHead className="text-right">HumanEval+</TableHead>
                <TableHead className="text-right">MBPP+</TableHead>
                <TableHead className="text-right">HumanEvalFix</TableHead>
                <TableHead className="text-right">tokens/s</TableHead>
                <TableHead className="text-right">J per solved (HE+)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((r) => (
                <TableRow key={name(r)}>
                  <TableCell>{name(r)}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.peak_ram_gb != null ? `${r.peak_ram_gb} GB` : "—"}</TableCell>
                  <Num v={r.tasks.humaneval_plus?.score ?? null} />
                  <Num v={r.tasks.mbpp_plus?.score ?? null} />
                  <Num v={r.tasks.humanevalfix?.score ?? null} />
                  <Num v={r.tasks.humaneval_plus?.tokens_per_s ?? null} />
                  <Num v={r.tasks.humaneval_plus?.j_per_solved ?? null} />
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Context({ data }: { data: Summary["context_ablation"] }) {
  return (
    <Card className="mt-2">
      <CardHeader>
        <CardTitle>How much context does repair need?</CardTitle>
        <CardDescription>{data.note}</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Prompt</TableHead>
              <TableHead className="text-right">% fixed</TableHead>
              <TableHead className="text-right">Input tokens</TableHead>
              <TableHead className="text-right">Output tokens</TableHead>
              <TableHead className="text-right">GPU energy</TableHead>
              <TableHead className="text-right">p vs trained prompt</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r) => (
              <TableRow key={r.variant}>
                <TableCell>{r.variant}</TableCell>
                <Num v={r.score} />
                <Num v={Math.round(r.input_tokens)} />
                <Num v={Math.round(r.output_tokens)} />
                <TableCell className="text-right tabular-nums">{r.gpu_j != null ? `${(r.gpu_j / 1000).toFixed(1)} kJ` : "—"}</TableCell>
                <TableCell className="text-right font-mono text-xs">{r.vs_standard ? r.vs_standard.p.toFixed(2) : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

const BUG_LABELS: Record<string, string> = {
  "bug-discount-sign": "Discount sign",
  "bug-mutable-default": "Mutable default",
  "bug-bulk-boundary": "Bulk boundary",
  "bug-skip-first": "Skips first item",
  "bug-restock-boundary": "Restock boundary",
};

function Agents({ data }: { data: Summary["agents"] }) {
  const bugs = Object.keys(data.rows[0]?.bugs ?? {});
  return (
    <Card className="mt-2">
      <CardHeader>
        <CardTitle>Single agent vs multi-agent on demo_repo</CardTitle>
        <CardDescription>{data.note}</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Setup</TableHead>
              {bugs.map((b) => (
                <TableHead key={b}>{BUG_LABELS[b] ?? b}</TableHead>
              ))}
              <TableHead className="text-right">Vulnerabilities</TableHead>
              <TableHead>Secret</TableHead>
              <TableHead className="text-right">False positives</TableHead>
              <TableHead className="text-right">Model calls</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.rows.map((r) => (
              <TableRow key={r.variant}>
                <TableCell>{r.variant}</TableCell>
                {bugs.map((b) => (
                  <TableCell key={b} className={r.bugs[b] === "missed" ? "text-muted-foreground" : ""}>
                    {r.bugs[b]}
                  </TableCell>
                ))}
                <TableCell className="text-right tabular-nums">
                  {Object.values(r.security).filter(Boolean).length} / {Object.keys(r.security).length}
                </TableCell>
                <TableCell>{Object.values(r.secrets).every(Boolean) ? "found" : "missed"}</TableCell>
                <Num v={r.false_positives} />
                <Num v={r.model_calls} />
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function SimpleTable({ head, rows, right = [] }: { head: string[]; rows: React.ReactNode[][]; right?: number[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head.map((h, i) => (
            <TableHead key={h} className={right.includes(i) ? "text-right" : undefined}>
              {h}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={i}>
            {r.map((c, j) => (
              <TableCell key={j} className={right.includes(j) ? "text-right tabular-nums" : undefined}>
                {c}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const pval = (p: number) => (p < 0.001 ? "< 0.001" : p < 0.01 ? p.toFixed(3) : p.toFixed(2));

function AgentContext({ data }: { data: Summary["agent_context"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>How much code should the agents show the model?</CardTitle>
        <CardDescription>
          {data.note} file: the whole file; function: the function alone (default); slice: plus what it uses; compact:
          without comments and docstrings.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <SimpleTable
          head={["Context", "Input tokens", "Output tokens", "Review hits", "Model false positives", "Bugs fixed / found / suspected"]}
          right={[1, 2, 3, 4]}
          rows={data.rows.map((r) => [
            r.context,
            r.input_tokens.toLocaleString(),
            r.output_tokens.toLocaleString(),
            r.review_hits,
            r.model_false_positives,
            `${r.fixed} / ${r.found} / ${r.suspected}`,
          ])}
        />
      </CardContent>
    </Card>
  );
}

function Languages({ data }: { data: Summary["multilang"] }) {
  return (
    <Card className="mt-2">
      <CardHeader>
        <CardTitle>Does the Python fine-tune help other languages?</CardTitle>
        <CardDescription>{data.note} % of bugs fixed; * marks p &lt; 0.05.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 overflow-x-auto">
        <HorizontalBars
          data={data.rows.map((r) => ({ label: r.language, base: r.base, ft: r.ft }))}
          series={[
            { key: "base", label: "Base model", color: BASE },
            { key: "ft", label: "Fine-tuned (QLoRA v2)", color: TUNED },
          ]}
          unit="%"
          max={50}
        />
        <SimpleTable
          head={["Language", "Problems", "Base", "Fine-tuned", "Change", "p"]}
          right={[1, 2, 3, 4, 5]}
          rows={data.rows.map((r) => [
            r.language,
            r.n,
            r.base.toFixed(1),
            r.ft.toFixed(1),
            `${r.change > 0 ? "+" : ""}${r.change.toFixed(1)}${r.p < 0.05 ? " *" : ""}`,
            pval(r.p),
          ])}
        />
      </CardContent>
    </Card>
  );
}

const CONFIG_LABELS: Record<string, string> = {
  "prefix-on-eager": "prefix cache on, eager",
  "prefix-off-eager": "prefix cache off, eager",
  "prefix-on-graphs": "prefix cache on, CUDA graphs",
};

function Serving({ data }: { data: Summary["serving"] }) {
  return (
    <div className="mt-2 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Batching, prefix caching and CUDA graphs (vLLM)</CardTitle>
          <CardDescription>{data.note}</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <SimpleTable
            head={["Server", "Concurrent requests", "Throughput (tok/s)", "Time to first token", "GPU energy per answer", "% fixed"]}
            right={[1, 2, 3, 4, 5]}
            rows={data.vllm.map((r) => [
              CONFIG_LABELS[r.config] + (r.warm ? ", warm second pass" : ""),
              r.workers,
              r.throughput,
              `${r.ttft_s.toFixed(2)} s`,
              `${r.j_per_item} J`,
              r.pass1.toFixed(1),
            ])}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>KV cache, batch size and attention (transformers)</CardTitle>
          <CardDescription>
            Eager attention in FP16 produces no usable answer for this model on a T4 (NaN logits); SDPA is the one that
            works.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <SimpleTable
            head={["Run", "Batch", "KV cache", "Tokens/s", "Peak memory", "Usable answers"]}
            right={[1, 3, 4]}
            rows={data.transformers.map((r) => [
              r.run,
              r.batch,
              r.use_cache ? "on" : "off",
              r.tokens_per_s,
              `${r.peak_memory_gb} GB`,
              r.usable,
            ])}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function RedTeam({ data }: { data: Summary["redteam"] }) {
  return (
    <div className="mt-2 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Attacks on the controls, with each control on and off</CardTitle>
          <CardDescription>
            Each attack runs once through Locali&apos;s control and once without it, against temporary copies.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <SimpleTable
            head={["Threat", "Attacks", "Worked with the control", "Worked without it"]}
            right={[1, 2, 3]}
            rows={data.controls.map((t) => [t.threat, t.cases, t.on, t.off])}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Injection and jailbreak payloads with the real model</CardTitle>
          <CardDescription>
            Payloads hidden in code comments, docstrings and strings. &quot;Complied&quot;: the answer did what the
            payload asked; &quot;harm&quot;: something harmful got through. The 3 S1 &quot;complied&quot; are a
            review missing an SQL injection, which it also misses with no payload at all; the static tools catch it
            every time.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <SimpleTable
            head={["Threat", "Attacks", "Model complied", "Harm with controls", "Harm without controls"]}
            right={[1, 2, 3, 4]}
            rows={data.model.map((t) => [t.threat === "S1" ? "S1 injection" : "S2 jailbreak", t.attacks, t.complied, t.harm_with, t.harm_without])}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>The cases</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <SimpleTable
            head={["Case", "Attack", "Control", "With the control"]}
            rows={data.cases.map((c) => [<span key="id" className="font-mono text-xs">{c.id}</span>, c.attack, c.control, c.detail])}
          />
        </CardContent>
      </Card>
    </div>
  );
}
