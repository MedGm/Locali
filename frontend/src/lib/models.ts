import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/use-hydrated";

export type RegistryModel = { id: string; label?: string; name: string };

// The app shows models by their full short name ("Qwen2.5-Coder-3B fine-tuned (run E) · Q4_K_M"),
// not by their registry id; an id missing from backend/models.json is shown as it is.
export function useModelLabel() {
  const models = useApiQuery({
    queryKey: ["models"],
    queryFn: () => api<{ note: string; models: RegistryModel[] }>("/models"),
  });
  const labels = new Map((models.data?.models ?? []).map((m) => [m.id, m.label ?? m.name]));
  return (id: string | null | undefined) => (id ? (labels.get(id) ?? id) : "");
}
