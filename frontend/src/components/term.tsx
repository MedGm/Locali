"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

// Words Locali uses that a newcomer may not know, explained where they appear.
export const GLOSSARY = {
  run: "One pass of Locali over a repository: a quick static scan, or the full assistant with the model.",
  patch: "A change Locali proposes, kept apart from your code. Nothing is written until you approve and apply it.",
  validation:
    "Before you see a patch, Locali applies it to a copy of the repository and checks that no passing test breaks and that it adds no security issue or secret.",
  suspect:
    "A generated test that failed on your code. Either the code has a bug or the test expects the wrong thing; Locali cannot tell which, so you decide.",
  finding: "Something a tool or the model flagged in your code: a bug, a security issue or a quality problem.",
  stale: "The files changed after the patch was made. Revalidate it to get a fresh patch against the current code.",
  sandbox: "An isolated container with no network and a read-only copy of your code, where tests run.",
} as const;

export function Term({ name, children }: { name: keyof typeof GLOSSARY; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span />}
        className="cursor-help underline decoration-muted-foreground/50 decoration-dotted underline-offset-4"
      >
        {children}
      </TooltipTrigger>
      <TooltipContent className="max-w-xs text-left leading-relaxed">{GLOSSARY[name]}</TooltipContent>
    </Tooltip>
  );
}
