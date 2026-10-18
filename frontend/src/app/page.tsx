"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  FileDiff,
  FolderGit2,
  GitBranch,
  ListChecks,
  Play,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  ThumbsUp,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";

import { KindBadge, StatusBadge } from "@/components/badges";
import { EmptyState } from "@/components/empty-state";
import { StartRunDialog } from "@/components/start-run";
import { Term } from "@/components/term";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, shortDate, type PatchSummary, type Repo, type RunSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

const HIDE_GUIDE = "locali.hide-getting-started";

export default function Home() {
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<{ model_configured: boolean }>("/status") });
  const repos = useQuery({ queryKey: ["repos"], queryFn: () => api<Repo[]>("/repos") });
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<RunSummary[]>("/runs"),
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "running" || r.status === "queued") ? 3000 : false),
  });
  const patches = useQuery({ queryKey: ["patches", "all"], queryFn: () => api<PatchSummary[]>("/patches") });

  const params = useSearchParams();
  const router = useRouter();
  const [starting, setStarting] = useState<{ open: boolean; repo?: string }>({ open: false });
  const fromMenu = params.get("start") === "1"; // "Start a run" in the search menu links here

  const pending = patches.data?.filter((p) => p.status === "proposed") ?? [];
  const active = runs.data?.filter((r) => r.status === "running" || r.status === "queued") ?? [];

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-2xl border bg-card px-6 py-7 md:px-8">
        <div className="pointer-events-none absolute -top-24 -right-16 size-72 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-xl space-y-2">
            <p className="text-sm font-medium text-primary">{greeting()}</p>
            <h1 className="text-3xl font-semibold tracking-tight">Review, test and fix your code, on your machine.</h1>
            <p className="text-muted-foreground">
              Locali checks a repository with static tools and a small model running locally, then proposes changes as{" "}
              <Term name="patch">patches</Term>. You decide what gets applied.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="lg" onClick={() => setStarting({ open: true })}>
              <Play /> Start a run
            </Button>
            <Button size="lg" variant="outline" render={<Link href="/repos" />}>
              <FolderGit2 /> Repositories
            </Button>
          </div>
        </div>
        {active.length > 0 && (
          <Link
            href={`/runs/${active[0].id}`}
            className="relative mt-5 flex items-center gap-3 rounded-lg border border-primary/30 bg-accent/50 px-4 py-2.5 text-sm"
          >
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
              <span className="relative inline-flex size-2 rounded-full bg-primary" />
            </span>
            <span>
              <span className="font-medium">{active[0].repo}</span> is being analysed
              {active[0].step ? ` (${active[0].step})` : ""}.
            </span>
            <span className="ml-auto flex items-center gap-1 font-medium text-primary">
              Follow it <ArrowRight className="size-3.5" />
            </span>
          </Link>
        )}
      </section>

      <GettingStarted
        modelReady={status.data?.model_configured}
        hasRepos={repos.data ? repos.data.length > 0 : undefined}
        hasRun={runs.data ? runs.data.some((r) => r.status === "done") : undefined}
        hasDecision={patches.data ? patches.data.some((p) => p.status !== "proposed") : undefined}
        onStart={() => setStarting({ open: true })}
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={FolderGit2} label="Repositories" value={repos.data?.length} href="/repos" />
        <Stat icon={ListChecks} label="Runs" value={runs.data?.length} href="/runs" />
        <Stat
          icon={FileDiff}
          label="Patches waiting for you"
          value={patches.data ? pending.length : undefined}
          href="/patches"
          highlight={pending.length > 0}
        />
        <Stat
          icon={Sparkles}
          label="Model"
          value={status.data ? (status.data.model_configured ? "Connected" : "Not connected") : undefined}
          href="/settings"
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <section className="space-y-3 lg:col-span-3">
          <SectionTitle title="Your repositories" href="/repos" />
          {repos.isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-28 rounded-xl" />
              ))}
            </div>
          ) : repos.data?.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {repos.data.slice(0, 4).map((r) => (
                <RepoCard key={r.name} repo={r} onRun={() => setStarting({ open: true, repo: r.name })} />
              ))}
            </div>
          ) : (
            <EmptyState icon={FolderGit2} title="No repositories found">
              Locali lists the folders with Python code under its repositories root. Point LOCALI_REPOS_ROOT at the folder
              that holds your projects.
            </EmptyState>
          )}
        </section>

        <section className="space-y-3 lg:col-span-2">
          <SectionTitle title="Waiting for your decision" href="/patches" />
          {patches.isLoading ? (
            <Skeleton className="h-40 rounded-xl" />
          ) : pending.length ? (
            <ul className="divide-y rounded-xl border bg-card">
              {pending.slice(0, 5).map((p) => (
                <li key={p.id}>
                  <Link href={`/patches/${p.id}`} className="flex items-start gap-3 px-4 py-3 hover:bg-muted/50">
                    <KindBadge kind={p.kind} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{p.title || p.id}</span>
                      <span className="block text-xs text-muted-foreground">
                        {p.repo.split("/").pop()} · {p.files.length} file{p.files.length === 1 ? "" : "s"} ·{" "}
                        <span className={p.validation_ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}>
                          {p.validation_ok ? "checks passed" : "checks failed"}
                        </span>
                      </span>
                    </span>
                    <ArrowRight className="mt-1 size-3.5 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon={ThumbsUp} title="Nothing to review">
              When the assistant proposes a change, it appears here with its diff and the checks it passed.
            </EmptyState>
          )}
        </section>
      </div>

      <section className="space-y-3">
        <SectionTitle title="Recent runs" href="/runs" />
        {runs.data?.length ? (
          <ul className="divide-y rounded-xl border bg-card">
            {runs.data.slice(0, 6).map((r) => (
              <li key={r.id}>
                <Link href={`/runs/${r.id}`} className="flex items-center gap-4 px-4 py-3 text-sm hover:bg-muted/50">
                  {r.mode === "agents" ? (
                    <Sparkles className="size-4 shrink-0 text-primary" />
                  ) : (
                    <ScanSearch className="size-4 shrink-0 text-muted-foreground" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{r.repo}</span>
                    <span className="text-muted-foreground"> · {r.mode === "agents" ? "full assistant" : "quick scan"}</span>
                  </span>
                  <span className="hidden text-xs text-muted-foreground sm:block">{shortDate(r.created)}</span>
                  <StatusBadge status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        ) : runs.isLoading ? (
          <Skeleton className="h-32 rounded-xl" />
        ) : (
          <EmptyState
            icon={Play}
            title="No runs yet"
            action={<Button onClick={() => setStarting({ open: true })}>Start your first run</Button>}
          >
            A quick scan takes about a minute and needs no model.
          </EmptyState>
        )}
      </section>

      <HowItWorks />

      <StartRunDialog
        key={starting.repo ?? "any"}
        open={starting.open || fromMenu}
        repo={starting.repo}
        onOpenChange={(open) => {
          setStarting((s) => ({ ...s, open }));
          if (!open && fromMenu) router.replace("/");
        }}
      />
    </div>
  );
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function SectionTitle({ title, href }: { title: string; href: string }) {
  return (
    <div className="flex items-center justify-between">
      <h2 className="font-semibold">{title}</h2>
      <Link href={href} className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground">
        See all <ArrowRight className="size-3" />
      </Link>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  href,
  highlight,
}: {
  icon: typeof FolderGit2;
  label: string;
  value: React.ReactNode;
  href: string;
  highlight?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center gap-4 rounded-xl border bg-card p-4 transition-colors hover:border-primary/40",
        highlight && "border-amber-300 dark:border-amber-500/50",
      )}
    >
      <span className="flex size-10 items-center justify-center rounded-lg bg-brand-soft text-primary">
        <Icon className="size-5" />
      </span>
      <span>
        <span className="block text-xs text-muted-foreground">{label}</span>
        <span className="block text-xl font-semibold tabular-nums">
          {value ?? <Skeleton className="mt-1 h-6 w-12" />}
        </span>
      </span>
    </Link>
  );
}

function RepoCard({ repo, onRun }: { repo: Repo; onRun: () => void }) {
  return (
    <div className="flex flex-col justify-between gap-4 rounded-xl border bg-card p-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-medium">{repo.name}</span>
          {repo.ready_to_merge !== null && (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                repo.ready_to_merge
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
                  : "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
              )}
            >
              {repo.ready_to_merge ? "ready to merge" : "blocked"}
            </span>
          )}
        </div>
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          {repo.git?.branch && (
            <>
              <GitBranch className="size-3" /> {repo.git.branch} ·{" "}
            </>
          )}
          {repo.python_files} Python file{repo.python_files === 1 ? "" : "s"}
        </p>
        <p className="text-xs text-muted-foreground">
          {repo.last_run ? `Last run ${shortDate(repo.last_run.created)}` : "Never analysed"}
          {repo.open_patches > 0 && ` · ${repo.open_patches} patch${repo.open_patches === 1 ? "" : "es"} open`}
        </p>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={onRun}>
          <Play /> Run
        </Button>
        {repo.runs > 0 && (
          <Button size="sm" variant="ghost" render={<Link href={`/trends?repo=${encodeURIComponent(repo.name)}`} />}>
            Trends
          </Button>
        )}
      </div>
    </div>
  );
}

function GettingStarted({
  modelReady,
  hasRepos,
  hasRun,
  hasDecision,
  onStart,
}: {
  modelReady?: boolean;
  hasRepos?: boolean;
  hasRun?: boolean;
  hasDecision?: boolean;
  onStart: () => void;
}) {
  const hidden = useSyncExternalStore(subscribeGuide, guideHidden, () => true);
  const steps = [
    { done: hasRepos, title: "Find your code", text: "Repositories under the configured root appear automatically.", href: "/repos", cta: "Open" },
    { done: modelReady, title: "Connect a model", text: "Optional for a quick scan, needed by the full assistant.", href: "/settings", cta: "Check" },
    { done: hasRun, title: "Run Locali", text: "Start with a quick scan, or the full assistant.", onClick: onStart, cta: "Start" },
    { done: hasDecision, title: "Decide on a patch", text: "Read the diff and the checks, then approve or reject.", href: "/patches", cta: "Review" },
  ];
  const loaded = steps.every((s) => s.done !== undefined);
  const done = steps.filter((s) => s.done).length;
  if (hidden || !loaded || done === steps.length) return null;
  return (
    <section className="rounded-2xl border bg-card p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold">Getting started</h2>
          <p className="text-sm text-muted-foreground">
            {done} of {steps.length} done. Four steps from your code to a reviewed change.
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Hide getting started"
          onClick={hideGuide}
        >
          <X />
        </Button>
      </div>
      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(done / steps.length) * 100}%` }} />
      </div>
      <ol className="grid gap-3 md:grid-cols-4">
        {steps.map((s) => (
          <li
            key={s.title}
            className={cn("flex flex-col gap-2 rounded-xl border p-3", s.done ? "bg-muted/40" : "border-primary/30")}
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              {s.done ? (
                <CheckCircle2 className="size-4 text-emerald-600" />
              ) : (
                <Circle className="size-4 text-muted-foreground" />
              )}
              <span className={cn(s.done && "text-muted-foreground line-through decoration-muted-foreground/40")}>{s.title}</span>
            </span>
            <span className="flex-1 text-xs text-muted-foreground">{s.text}</span>
            {!s.done &&
              (s.href ? (
                <Button size="xs" variant="outline" className="self-start" render={<Link href={s.href} />}>
                  {s.cta}
                </Button>
              ) : (
                <Button size="xs" className="self-start" onClick={s.onClick}>
                  {s.cta}
                </Button>
              ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

// Whether the getting-started card was dismissed, kept in this browser only.
function guideHidden() {
  try {
    return window.localStorage.getItem(HIDE_GUIDE) === "1";
  } catch {
    return false;
  }
}

function subscribeGuide(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(HIDE_GUIDE, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(HIDE_GUIDE, onChange);
  };
}

function hideGuide() {
  try {
    window.localStorage.setItem(HIDE_GUIDE, "1");
  } catch {}
  window.dispatchEvent(new Event(HIDE_GUIDE));
}

function HowItWorks() {
  const steps = [
    { icon: ScanSearch, title: "Analyse", text: "Static tools and the model read a copy of your repository." },
    { icon: Sparkles, title: "Propose", text: "Tests, fixes and docs become separate patches." },
    { icon: ShieldCheck, title: "Check", text: "Each patch is validated in a sandbox before you see it." },
    { icon: ThumbsUp, title: "You decide", text: "Approve, apply and revert. Nothing changes without you." },
  ];
  return (
    <section className="rounded-2xl border bg-muted/30 p-5">
      <h2 className="mb-4 font-semibold">How Locali works</h2>
      <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((s, i) => (
          <li key={s.title} className="flex gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-card text-primary shadow-sm ring-1 ring-border">
              <s.icon className="size-4" />
            </span>
            <span>
              <span className="block text-sm font-medium">
                {i + 1}. {s.title}
              </span>
              <span className="block text-xs text-muted-foreground">{s.text}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
