import { Badge } from "@/components/ui/badge";
import type { PatchKind, PatchStatus, RunStatus, Severity } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-zinc-100 text-zinc-700",
  running: "bg-sky-100 text-sky-800",
  done: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  proposed: "bg-amber-100 text-amber-800",
  approved: "bg-sky-100 text-sky-800",
  applied: "bg-emerald-100 text-emerald-800",
  reverted: "bg-zinc-100 text-zinc-700",
  rejected: "bg-zinc-100 text-zinc-500",
  stale: "bg-orange-100 text-orange-800",
};

export function StatusBadge({ status }: { status: RunStatus | PatchStatus }) {
  return <Badge className={cn("border-0 font-medium", STATUS_COLORS[status])}>{status}</Badge>;
}

const SEVERITY_COLORS: Record<Severity, string> = {
  high: "bg-red-100 text-red-800",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-zinc-100 text-zinc-700",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge className={cn("border-0", SEVERITY_COLORS[severity])}>{severity}</Badge>;
}

const KIND_COLORS: Record<PatchKind, string> = {
  fix: "bg-violet-100 text-violet-800",
  tests: "bg-teal-100 text-teal-800",
  docs: "bg-indigo-100 text-indigo-800",
  change: "bg-zinc-100 text-zinc-700",
};

export function KindBadge({ kind }: { kind: PatchKind }) {
  return <Badge className={cn("border-0", KIND_COLORS[kind])}>{kind}</Badge>;
}
