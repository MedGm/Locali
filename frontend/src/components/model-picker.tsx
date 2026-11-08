"use client";

import { Loader2 } from "lucide-react";

import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectSeparator, SelectTrigger, SelectValue } from "@/components/ui/select";

export type ModelChoice = { id: string; name: string; size_gib: number | null; fine_tuned: boolean };

export const NO_MODEL = "none";

// "Qwen2.5-Coder-3B fine-tuned (run E) · Q4_K_M" -> ["Qwen2.5-Coder-3B fine-tuned (run E)", "Q4_K_M"]
export function splitLabel(label: string): [string, string] {
  const cut = label.lastIndexOf(" · ");
  return cut > 0 ? [label.slice(0, cut), label.slice(cut + 3)] : [label, ""];
}

// "Qwen2.5-Coder-3B fine-tuned (run E)" -> "Fine-tuned (run E)": the group already names the model
function short(name: string) {
  const rest = name.replace(/^Qwen2\.5-Coder-[\d.]+B\s*/, "");
  return rest ? rest[0].toUpperCase() + rest.slice(1) : name;
}

function family(label: string) {
  return label.match(/Coder-([\d.]+B)/)?.[1] ?? "Other";
}

// The comparison model picker: models grouped by size, each with its quantization, file size and
// whether it is fine-tuned; picking one makes the backend start it.
export function ModelPicker({
  value,
  choices,
  label,
  loading,
  disabled,
  onChange,
}: {
  value: string;
  choices: ModelChoice[];
  label: (id: string) => string;
  loading: boolean;
  disabled: boolean;
  onChange: (id: string) => void;
}) {
  const groups = new Map<string, ModelChoice[]>();
  for (const c of choices) {
    const key = family(label(c.id));
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  const items = { [NO_MODEL]: "No comparison", ...Object.fromEntries(choices.map((c) => [c.id, label(c.id)])) };
  return (
    <Select value={value} onValueChange={(v) => v !== null && onChange(v as string)} items={items} disabled={disabled}>
      <SelectTrigger aria-label="Compare with" className="h-9 w-[22rem] max-w-full bg-card">
        {loading && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
        <SelectValue />
      </SelectTrigger>
      <SelectContent alignItemWithTrigger={false} align="end" className="w-[24rem] p-1">
        <SelectItem value={NO_MODEL} className="py-1.5">
          <span className="text-muted-foreground">No comparison</span>
        </SelectItem>
        {[...groups].map(([size, models]) => (
          <SelectGroup key={size}>
            <SelectSeparator />
            <SelectLabel className="px-2 pt-1.5 pb-1 text-[11px] font-medium tracking-wide uppercase">
              Qwen2.5-Coder {size}
            </SelectLabel>
            {models.map((c) => {
              const [name, quant] = splitLabel(label(c.id));
              return (
                <SelectItem key={c.id} value={c.id} className="py-1.5">
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{short(name)}</span>
                    <span className="text-xs text-muted-foreground">
                      {quant}
                      {c.size_gib ? ` · ${c.size_gib} GB` : ""}
                    </span>
                  </span>
                </SelectItem>
              );
            })}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
}
