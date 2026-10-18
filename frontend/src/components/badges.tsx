import { Badge } from "@/components/ui/badge";
import type { PatchKind, PatchStatus, RunStatus, Severity } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/15 dark:text-zinc-300",
  running: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  proposed: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  approved: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  applied: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  reverted: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/15 dark:text-zinc-300",
  rejected: "bg-zinc-100 text-zinc-500 dark:bg-zinc-500/15 dark:text-zinc-400",
  stale: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
};

export function StatusBadge({ status }: { status: RunStatus | PatchStatus }) {
  return <Badge className={cn("border-0 font-medium", STATUS_COLORS[status])}>{status}</Badge>;
}

const SEVERITY_COLORS: Record<Severity, string> = {
  high: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  low: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/15 dark:text-zinc-300",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge className={cn("border-0", SEVERITY_COLORS[severity])}>{severity}</Badge>;
}

const KIND_COLORS: Record<PatchKind, string> = {
  fix: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
  tests: "bg-teal-100 text-teal-800 dark:bg-teal-500/15 dark:text-teal-300",
  docs: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  change: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/15 dark:text-zinc-300",
};

export function KindBadge({ kind }: { kind: PatchKind }) {
  return <Badge className={cn("w-12 justify-center border-0", KIND_COLORS[kind])}>{kind}</Badge>;
}
