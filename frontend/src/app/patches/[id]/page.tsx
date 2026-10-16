"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Diff, Hunk, parseDiff } from "react-diff-view";
import { toast } from "sonner";

import { KindBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, post, type Patch } from "@/lib/api";

const REVIEWER_KEY = "locali.reviewer";

export default function PatchPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const patch = useQuery({ queryKey: ["patch", id], queryFn: () => api<Patch>(`/patches/${id}`) });
  // The reviewer field only renders after the patch has loaded in the browser, so reading
  // localStorage here cannot cause a hydration mismatch.
  const [reviewer, setReviewer] = useState(() =>
    typeof window === "undefined" ? "" : (localStorage.getItem(REVIEWER_KEY) ?? ""),
  );
  const [confirmApply, setConfirmApply] = useState(false);

  const refresh = (p: Patch) => {
    queryClient.setQueryData(["patch", id], p);
    queryClient.invalidateQueries({ queryKey: ["patches"] });
  };
  const onError = (e: Error) => {
    toast.error(e.message);
    queryClient.invalidateQueries({ queryKey: ["patch", id] });
  };
  const approve = useMutation({
    mutationFn: (p: Patch) => {
      localStorage.setItem(REVIEWER_KEY, reviewer);
      // Send back exactly the hashes shown on this page: the approval covers what was reviewed.
      return post<Patch>(`/patches/${p.id}/approve`, {
        sha256: p.sha256,
        baseline: p.baseline,
        validation_sha256: p.validation_sha256,
        reviewer,
      });
    },
    onSuccess: (p) => {
      refresh(p);
      toast.success("Approved. Apply it when you are ready.");
    },
    onError,
  });
  const reject = useMutation({
    mutationFn: (p: Patch) => {
      localStorage.setItem(REVIEWER_KEY, reviewer);
      return post<Patch>(`/patches/${p.id}/reject`, { reviewer });
    },
    onSuccess: refresh,
    onError,
  });
  const apply = useMutation({
    mutationFn: (p: Patch) => post<Patch>(`/patches/${p.id}/apply`),
    onSuccess: (p) => {
      refresh(p);
      setConfirmApply(false);
      toast.success("Applied. The original files are backed up; you can revert.");
    },
    onError: (e: Error) => {
      setConfirmApply(false);
      onError(e);
    },
  });
  const revert = useMutation({
    mutationFn: (p: Patch) => post<Patch>(`/patches/${p.id}/revert`),
    onSuccess: refresh,
    onError,
  });
  const revalidate = useMutation({
    mutationFn: (p: Patch) => post<Patch>(`/patches/${p.id}/revalidate`),
    onSuccess: (p) => router.push(`/patches/${p.id}`),
    onError,
  });

  const files = useMemo(() => (patch.data ? parseDiff(patch.data.diff) : []), [patch.data]);

  if (patch.isError) return <p className="text-sm text-red-700">Patch not found.</p>;
  if (!patch.data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const p = patch.data;
  const v = p.validation;
  const busy = approve.isPending || reject.isPending || apply.isPending || revert.isPending || revalidate.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{p.title || p.id}</h1>
        <KindBadge kind={p.kind} />
        <StatusBadge status={p.status} />
        <span className="font-mono text-sm text-muted-foreground">{p.id}</span>
        <span className="text-sm text-muted-foreground">
          from run{" "}
          <Link href={`/runs/${p.run_id}`} className="font-mono underline">
            {p.run_id}
          </Link>
          {p.reviewer && ` · reviewed by ${p.reviewer}`}
        </span>
      </div>

      {p.kind === "tests" && (
        <Alert>
          <AlertTitle>These tests record what the code does now</AlertTitle>
          <AlertDescription>
            They were generated and kept because they pass on the current code. If the current behaviour is wrong,
            a test like this would lock it in: read the expected values before approving.
          </AlertDescription>
        </Alert>
      )}

      {p.status === "stale" && (
        <Alert>
          <AlertTitle>The repository changed after this patch was proposed</AlertTitle>
          <AlertDescription>
            It can no longer be applied as reviewed. Revalidate it to get a new proposal against the current files.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Validation</CardTitle>
            <CardDescription>
              Run in the sandbox on the patched copy before you were asked to review it.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className={v.ok ? "font-medium text-emerald-700" : "font-medium text-red-700"}>
              {v.ok ? "All checks passed." : "Validation failed: this patch cannot be approved."}
            </p>
            {v.tests && (
              <p>
                Tests: {v.tests.passed} passed, {v.tests.failed.length} failed
                {v.tests.coverage_percent != null && ` · coverage ${v.tests.coverage_percent}%`}
                {v.tests.timed_out && " · timed out"}
              </p>
            )}
            <TestList
              title="Now passing (failed before this patch)"
              tests={v.now_passing ?? []}
              className="text-emerald-700"
            />
            <TestList
              title="Newly failing (passed before): this blocks the patch"
              tests={v.newly_failing ?? []}
              className="text-red-700"
            />
            {v.tests?.failed.length && !v.newly_failing?.length ? (
              <p className="text-xs text-muted-foreground">
                Still failing, as before this patch: {v.tests.failed.join(", ")}
              </p>
            ) : null}
            <p>New security findings in the changed files: {v.new_security_findings.length}</p>
            {v.new_security_findings.map((f, i) => (
              <p key={i} className="flex items-center gap-2 text-xs">
                <SeverityBadge severity={f.severity} />
                <span className="font-mono">
                  {f.path}:{f.line}
                </span>
                {f.message}
              </p>
            ))}
            <p>Secrets in added lines: {v.secrets_added.length ? v.secrets_added.join(", ") : "none"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Decision</CardTitle>
            <CardDescription>Approval is bound to the hashes below.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <dl className="space-y-1 text-xs">
              <Hash label="Patch" value={p.sha256} />
              <Hash label="Validation" value={p.validation_sha256} />
              {p.head && <Hash label="Git HEAD" value={p.head} />}
            </dl>
            {p.status === "proposed" && (
              <>
                <label className="grid gap-1 text-sm">
                  Reviewer
                  <Input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="your name" />
                </label>
                <div className="flex gap-2">
                  <Button disabled={busy || !v.ok || !reviewer.trim()} onClick={() => approve.mutate(p)}>
                    Approve
                  </Button>
                  <Button variant="outline" disabled={busy || !reviewer.trim()} onClick={() => reject.mutate(p)}>
                    Reject
                  </Button>
                </div>
              </>
            )}
            {p.status === "approved" && (
              <div className="flex gap-2">
                <Button disabled={busy} onClick={() => setConfirmApply(true)}>
                  Apply to repository
                </Button>
                <Button variant="outline" disabled={busy || !reviewer.trim()} onClick={() => reject.mutate(p)}>
                  Reject
                </Button>
              </div>
            )}
            {p.status === "applied" && (
              <Button variant="outline" disabled={busy} onClick={() => revert.mutate(p)}>
                Revert
              </Button>
            )}
            {p.status === "stale" && (
              <Button disabled={busy} onClick={() => revalidate.mutate(p)}>
                Revalidate
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Changes</CardTitle>
          <CardDescription>
            {files.length} file{files.length === 1 ? "" : "s"}: {p.files.join(", ")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 overflow-x-auto">
          {files.map((file) => (
            <div key={`${file.oldPath}-${file.newPath}`} className="rounded-md border">
              <div className="border-b bg-muted/40 px-3 py-1.5 font-mono text-xs">
                {file.type === "add" ? `new file ${file.newPath}` : file.newPath}
              </div>
              <Diff viewType="split" diffType={file.type} hunks={file.hunks}>
                {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
              </Diff>
            </div>
          ))}
        </CardContent>
      </Card>

      <Dialog open={confirmApply} onOpenChange={setConfirmApply}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply this patch?</DialogTitle>
            <DialogDescription>
              This writes {p.files.length} file{p.files.length === 1 ? "" : "s"} in {p.repo}. The files are checked
              against the reviewed baseline first and backed up, so you can revert.
            </DialogDescription>
          </DialogHeader>
          <ul className="list-inside list-disc font-mono text-xs">
            {p.files.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <DialogFooter>
            <DialogClose render={<Button variant="outline">Cancel</Button>} />
            <Button disabled={apply.isPending} onClick={() => apply.mutate(p)}>
              {apply.isPending ? "Applying…" : "Apply"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TestList({ title, tests, className }: { title: string; tests: string[]; className: string }) {
  if (!tests.length) return null;
  return (
    <div>
      <p className={className}>{title}</p>
      <ul className={`list-inside list-disc font-mono text-xs ${className}`}>
        {tests.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function Hash({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono break-all">{value}</dd>
    </div>
  );
}
