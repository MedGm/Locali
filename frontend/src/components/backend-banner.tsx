"use client";

import { useQuery } from "@tanstack/react-query";
import { PlugZap } from "lucide-react";

import { api, ApiError } from "@/lib/api";

// When the web app cannot use the backend, every page would just look empty. Say why instead.
export function BackendBanner() {
  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => api<{ model_configured: boolean }>("/status"),
    retry: false,
    refetchInterval: (q) => (q.state.error ? 5000 : false),
  });
  const e = status.error;
  if (!e) return null;
  const code = e instanceof ApiError ? e.status : 0;
  const [title, text] =
    code === 401
      ? ["The backend refused the web app's token.", "LOCALI_API_TOKEN must be the same for both; keep it in .env and restart them."]
      : code === 502
        ? ["The backend is not running.", "Start it with scripts/run.sh backend. This page reconnects by itself."]
        : ["The backend answered with an error.", e.message];
  return (
    <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
      <PlugZap className="mt-0.5 size-4 shrink-0" />
      <span>
        <span className="font-medium">{title}</span> {text}
      </span>
    </div>
  );
}
