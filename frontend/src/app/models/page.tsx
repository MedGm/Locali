"use client";

import { ExternalLink } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MlflowLink } from "@/components/mlflow-link";
import { useApiQuery } from "@/lib/use-hydrated";
import { api } from "@/lib/api";

type Measured = { score: number; tokens_per_s: number; j_per_solved: number | null };
type Model = {
  id: string;
  name: string;
  base: string;
  fine_tuned: boolean;
  quant: string;
  file: string;
  size_gib: number;
  hf_repo: string;
  recommended: "default" | "fast" | null;
  laptop: Record<string, Measured>;
  peak_ram_gb: number | null;
  active: boolean;
};

const TASKS: [string, string][] = [
  ["humaneval_plus", "HumanEval+"],
  ["mbpp_plus", "MBPP+"],
  ["humanevalfix", "HumanEvalFix"],
];

export default function ModelsPage() {
  const models = useApiQuery({ queryKey: ["models"], queryFn: () => api<{ note: string; models: Model[] }>("/models") });
  return (
    <div className="space-y-6">
      <PageHeader
        title="Models"
        description="The fine-tuned model in its three sizes, and the base model it came from. The highlighted card is the one this installation runs."
        actions={<MlflowLink />}
        howItWorks={[
          { title: "One model, three sizes", text: "F16 is the full model; Q8 and Q4 are compressed copies that run faster in less memory." },
          { title: "Q8 is the default", text: "It gives the same answers as F16 in our tests, in half the memory." },
          { title: "Q4 is the fast option", text: "About 60 % faster than Q8 for 2–4 points of accuracy." },
          { title: "Measured here", text: "Scores and speed come from benchmark runs on a 4-core laptop CPU." },
        ]}
      />
      {models.data?.note && <p className="-mt-3 text-xs text-muted-foreground">{models.data.note}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {models.data?.models.map((m) => (
          <Card key={m.id} className={m.active ? "border-emerald-400" : undefined}>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                {m.name}
                {m.active && <Badge className="bg-emerald-100 text-emerald-800">active</Badge>}
                {m.recommended === "default" && <Badge variant="secondary">recommended</Badge>}
                {m.recommended === "fast" && <Badge variant="secondary">fastest</Badge>}
              </CardTitle>
              <CardDescription className="space-y-1">
                <span className="block">
                  {m.fine_tuned ? "Fine-tuned for repair, tests, review and tracing" : "Base model, no fine-tuning"} ·{" "}
                  {m.quant} · {m.size_gib} GiB
                  {m.peak_ram_gb != null && ` · ${m.peak_ram_gb} GB RAM`}
                </span>
                <a
                  href={`https://huggingface.co/${m.hf_repo}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 underline"
                >
                  {m.hf_repo} <ExternalLink className="size-3" />
                </a>
              </CardDescription>
            </CardHeader>
            <CardContent>
              {Object.keys(m.laptop).length ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground">
                      <th className="font-normal">Laptop CPU</th>
                      <th className="text-right font-normal">% solved</th>
                      <th className="text-right font-normal">tokens/s</th>
                      <th className="text-right font-normal">J per solved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {TASKS.filter(([t]) => m.laptop[t]).map(([t, label]) => (
                      <tr key={t}>
                        <td>{label}</td>
                        <td className="text-right tabular-nums">{m.laptop[t].score}</td>
                        <td className="text-right tabular-nums">{m.laptop[t].tokens_per_s}</td>
                        <td className="text-right tabular-nums">{m.laptop[t].j_per_solved ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-muted-foreground">Not measured on the laptop.</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
