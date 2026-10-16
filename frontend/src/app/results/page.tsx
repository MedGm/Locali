"use client";

import { useQuery } from "@tanstack/react-query";

import { HorizontalBars } from "@/components/charts/bars";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
};

const BASE = "var(--viz-series-1)";
const TUNED = "var(--viz-series-2)";

const fmtP = (t: Test) => (t ? (t.p < 0.001 ? t.p.toExponential(0) : t.p.toFixed(3)) : "—");
const mark = (t: Test) => (t && t.p < 0.05 ? " *" : "");

export default function ResultsPage() {
  const summary = useQuery({ queryKey: ["results"], queryFn: () => api<Summary>("/results") });
  if (summary.isError) return <p className="text-sm text-red-700">No results summary yet.</p>;
  if (!summary.data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const s = summary.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Evaluation results</h1>
        <p className="text-sm text-muted-foreground">
          Computed from the per-item result files (exported {new Date(s.generated_at).toLocaleString()}). Every
          comparison is paired on the same items; * marks p &lt; 0.05 (exact McNemar test).
        </p>
      </div>
      <Tabs defaultValue="finetuning">
        <TabsList>
          <TabsTrigger value="finetuning">Fine-tuning</TabsTrigger>
          <TabsTrigger value="baselines">Model baselines</TabsTrigger>
          <TabsTrigger value="ladder">Quantization</TabsTrigger>
          <TabsTrigger value="context">Context</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
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
        <TabsContent value="context">
          <Context data={s.context_ablation} />
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
