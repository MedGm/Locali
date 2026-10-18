"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, FolderGit2, Search, Sparkles, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, post, shortDate, type Repo, type RunSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

type Mode = RunSummary["mode"];

const MODES: { mode: Mode; title: string; icon: typeof Zap; time: string; text: string; does: string[] }[] = [
  {
    mode: "analyze",
    title: "Quick scan",
    icon: Zap,
    time: "about a minute",
    text: "Static tools only. No model needed.",
    does: ["Bugs and code smells (Ruff, Radon)", "Security issues (Bandit, Semgrep)", "Hard-coded secrets and injected instructions"],
  },
  {
    mode: "agents",
    title: "Full assistant",
    icon: Sparkles,
    time: "10–15 minutes on a laptop CPU",
    text: "Everything in the quick scan, plus the model.",
    does: [
      "Reviews every function",
      "Writes regression tests and runs them in a sandbox",
      "Fixes failing tests and documents functions",
      "Checks merge readiness and dependencies",
    ],
  },
];

export function StartRunDialog({
  open,
  onOpenChange,
  repo: initialRepo,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  repo?: string;
}) {
  const [repo, setRepo] = useState<string | undefined>(initialRepo);
  const [mode, setMode] = useState<Mode>("agents");
  const [filter, setFilter] = useState("");
  const repos = useQuery({ queryKey: ["repos"], queryFn: () => api<Repo[]>("/repos"), enabled: open });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<{ model_configured: boolean }>("/status") });
  const modelReady = status.data?.model_configured ?? false;
  const effective: Mode = modelReady ? mode : "analyze";
  const router = useRouter();
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: () => post<RunSummary>("/runs", { repo, mode: effective }),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      onOpenChange(false);
      router.push(`/runs/${run.id}`);
    },
    onError: (e) => toast.error(e.message),
  });
  const chosen = repo !== undefined && (initialRepo !== undefined || repos.data?.some((r) => r.name === repo));
  const step = chosen ? 2 : 1;
  const list = (repos.data ?? []).filter((r) => r.name.toLowerCase().includes(filter.toLowerCase()));

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) setRepo(initialRepo);
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <p className="text-xs font-medium text-primary">Step {step} of 2</p>
          <DialogTitle>{step === 1 ? "Which repository?" : `What should Locali do with ${repo}?`}</DialogTitle>
          <DialogDescription>
            {step === 1
              ? "Locali works on a copy. Your files are never changed by a run."
              : "Either way, you get a report. Changes come as patches that wait for your approval."}
          </DialogDescription>
        </DialogHeader>

        {step === 1 ? (
          <div className="space-y-3">
            <label className="flex items-center gap-2 rounded-lg border px-2.5">
              <Search className="size-4 text-muted-foreground" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter repositories"
                className="h-9 flex-1 bg-transparent text-sm outline-none"
              />
            </label>
            <ul className="grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2">
              {list.map((r) => (
                <li key={r.name}>
                  <button
                    type="button"
                    onClick={() => setRepo(r.name)}
                    className="flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors hover:border-primary/50 hover:bg-accent/40"
                  >
                    <FolderGit2 className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{r.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {r.python_files} Python file{r.python_files === 1 ? "" : "s"} ·{" "}
                        {r.last_run ? `last run ${shortDate(r.last_run.created)}` : "never analysed"}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
              {repos.isLoading && <li className="text-sm text-muted-foreground">Looking for repositories…</li>}
              {repos.data && !list.length && (
                <li className="text-sm text-muted-foreground">
                  No folder with Python code {filter ? "matches" : "under the repositories root"}. The root is set with
                  LOCALI_REPOS_ROOT (see Settings).
                </li>
              )}
            </ul>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {MODES.map((m) => {
              const disabled = m.mode === "agents" && !modelReady;
              const selected = effective === m.mode;
              return (
                <button
                  key={m.mode}
                  type="button"
                  disabled={disabled}
                  onClick={() => setMode(m.mode)}
                  className={cn(
                    "relative flex flex-col gap-2 rounded-xl border p-4 text-left transition-colors",
                    selected ? "border-primary bg-accent/50 ring-2 ring-primary/20" : "hover:border-primary/40",
                    disabled && "cursor-not-allowed opacity-55",
                  )}
                >
                  {selected && (
                    <span className="absolute top-3 right-3 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Check className="size-3" />
                    </span>
                  )}
                  <m.icon className="size-5 text-primary" />
                  <span className="font-medium">{m.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {m.text} Takes {m.time}.
                  </span>
                  <ul className="mt-1 space-y-1 text-xs">
                    {m.does.map((d) => (
                      <li key={d} className="flex gap-1.5">
                        <Check className="mt-0.5 size-3 shrink-0 text-emerald-600" />
                        {d}
                      </li>
                    ))}
                  </ul>
                  {disabled && (
                    <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                      Needs a model server. See Settings.
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        <DialogFooter>
          {step === 2 && initialRepo === undefined && (
            <Button variant="ghost" onClick={() => setRepo(undefined)} className="mr-auto">
              <ArrowLeft /> Back
            </Button>
          )}
          {step === 2 && (
            <Button
              onClick={() => start.mutate()}
              disabled={start.isPending}
            >
              {start.isPending ? "Starting…" : effective === "agents" ? "Start the assistant" : "Start the scan"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
