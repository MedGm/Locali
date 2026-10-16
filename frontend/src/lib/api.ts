// Typed access to the backend through the Next.js proxy (/api/* -> FastAPI).

export type Category = "bug" | "security" | "quality";
export type Severity = "high" | "medium" | "low";

export type Finding = {
  tool: string;
  rule: string;
  path: string;
  line: number;
  category: Category;
  severity: Severity;
  message: string;
};

export type Suspect = { file: string; function: string; test: string; error: string };

export type Fix = {
  test: string;
  file: string;
  function: string;
  fixed: boolean;
  attempts: number;
  diagnosis: { bug_location?: string; bug_type?: string; explanation?: string } | null;
};

export type TestResult = {
  passed: number;
  failed: string[];
  errors: number;
  timed_out: boolean;
  coverage_percent: number | null;
  output_tail: string;
};

export type Validation = {
  ok: boolean;
  tests: TestResult | null;
  newly_failing?: string[];
  now_passing?: string[];
  new_security_findings: Finding[];
  secrets_added: string[];
};

export type RunStatus = "queued" | "running" | "done" | "failed";

export type RunSummary = {
  id: string;
  repo: string;
  mode: "analyze" | "agents";
  status: RunStatus;
  step?: string | null;
  patch_ids?: string[];
  error?: string;
  created?: string;
};

export type Repo = {
  name: string;
  python_files: number;
  git: { branch: string | null; last_commit: string | null; last_commit_date: string | null } | null;
  runs: number;
  last_run: { id: string; mode: RunSummary["mode"]; status: RunStatus; created: string } | null;
  open_patches: number;
  ready_to_merge: boolean | null;
};

export type TrendPoint = {
  id: string;
  created: string;
  mode: RunSummary["mode"];
  findings: { bug: number; security: number; quality: number };
  high_security: number;
  tests_passed: number | null;
  tests_failed: number | null;
  coverage_percent: number | null;
  patches: number;
  patches_validated: number;
  ready_to_merge: boolean | null;
};

export type Settings = {
  repos_root: string;
  model: { configured: boolean; url: string | null; name: string | null; id: string | null; key_set: boolean; max_tokens: number };
  api_token_set: boolean;
  workflow: { steps: string[]; static_analysis: boolean; routing: string; concurrent_runs: number };
  sandbox: { image: string; network: boolean };
  mlflow: { tracking: boolean; ui: string | null };
  variables: { env: string; description: string; value: string | null }[];
};

export function shortDate(iso?: string | null) {
  return iso ? iso.slice(0, 16).replace("T", " ") : "—";
}

export type RunPatch = { id: string; kind: PatchKind; title: string; files: string[]; ok: boolean };

export type Run = RunSummary & {
  steps_done?: string[];
  report?: string;
  findings?: Finding[];
  suspects?: Suspect[];
  fixes?: Fix[];
  tests_added?: string[];
  patches?: RunPatch[];
  summary?: { by_category: Record<string, number>; by_tool: Record<string, number> };
  devops?: Devops;
};

export type Devops = {
  ready_to_merge: boolean;
  blockers: string[];
  warnings: string[];
  dependencies: { file: string; name: string; looks_like: string }[];
  ci: { has_ci: boolean; has_locali_review: boolean; workflows: string[] };
  suggested_workflow: string | null;
};

export type ModelCall = {
  step: string;
  prompt: string;
  answer: string;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_s: number;
};

export type PatchStatus = "proposed" | "approved" | "applied" | "reverted" | "rejected" | "stale";
export type PatchKind = "fix" | "tests" | "docs" | "change";

export type PatchSummary = {
  id: string;
  run_id: string;
  repo: string;
  files: string[];
  status: PatchStatus;
  reviewer: string | null;
  sha256: string;
  title: string;
  kind: PatchKind;
  validation_ok: boolean;
};

export type Patch = Omit<PatchSummary, "validation_ok"> & {
  diff: string;
  baseline: Record<string, string | null>;
  head: string | null;
  validation: Validation;
  validation_sha256: string;
  applied_hashes: Record<string, string | null>;
  history: string[];
};

export const PIPELINE = ["prepare", "analyze", "review", "testgen", "debug", "propose", "devops", "report"] as const;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof body.detail === "string" ? body.detail : res.statusText);
  }
  return res.json() as Promise<T>;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
