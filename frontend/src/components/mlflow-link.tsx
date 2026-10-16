"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";

import { api } from "@/lib/api";

// Shown when the backend knows where the MLflow dashboard runs (LOCALI_MLFLOW_UI).
export function MlflowLink() {
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<{ mlflow_ui?: string | null }>("/status") });
  const url = status.data?.mlflow_ui;
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm underline">
      Open MLflow (runs, traces, metrics) <ExternalLink className="size-3" />
    </a>
  );
}
