"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { SeverityBadge } from "@/components/badges";
import type { Severity } from "@/lib/api";

type Finding = { line?: string; category?: string; severity?: string; message?: string };
type Diagnosis = { bug_location?: string; bug_type?: string; explanation?: string };

// Answers in the trained formats start with a JSON object: {"findings": [...]} for a review,
// {"bug_location", "bug_type", "explanation"} before the fixed code for a repair. Show those as
// cards; everything else as text with code blocks.
export function Answer({ text, streaming }: { text: string; streaming?: boolean }) {
  const { json, rest } = leadingJson(text);
  return (
    <div className="space-y-3 text-sm">
      {json && "findings" in json && Array.isArray(json.findings) && <Findings findings={json.findings as Finding[]} />}
      {json && ("bug_location" in json || "explanation" in json) && <DiagnosisCard d={json as Diagnosis} />}
      <Markdownish text={json ? rest : text} />
      {streaming && <span className="inline-block h-4 w-1.5 animate-pulse rounded-sm bg-primary align-middle" />}
    </div>
  );
}

function leadingJson(text: string): { json: Record<string, unknown> | null; rest: string } {
  // some models wrap the object in a ```json block
  const fenced = text.trimStart().match(/^```(?:json)?\s*\n(\{[\s\S]*?\})\s*\n```/);
  if (fenced) {
    try {
      return { json: JSON.parse(fenced[1]), rest: text.trimStart().slice(fenced[0].length) };
    } catch {
      // not JSON after all: show it as it is
    }
  }
  const t = text.trimStart();
  if (!t.startsWith("{")) return { json: null, rest: text };
  let depth = 0;
  let inString = false;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (inString) {
      if (c === "\\") i++;
      else if (c === '"') inString = false;
    } else if (c === '"') inString = true;
    else if (c === "{") depth++;
    else if (c === "}" && --depth === 0) {
      try {
        return { json: JSON.parse(t.slice(0, i + 1)), rest: t.slice(i + 1) };
      } catch {
        return { json: null, rest: text };
      }
    }
  }
  return { json: null, rest: text };
}

function Findings({ findings }: { findings: Finding[] }) {
  if (!findings.length)
    return <p className="rounded-lg border bg-emerald-50 px-3 py-2 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">No problems found.</p>;
  return (
    <ul className="space-y-2">
      {findings.map((f, i) => (
        <li key={i} className="rounded-lg border bg-card p-3">
          <div className="mb-1.5 flex items-center gap-2">
            {f.severity && ["high", "medium", "low"].includes(f.severity) && <SeverityBadge severity={f.severity as Severity} />}
            <span className="text-xs font-medium text-muted-foreground">{f.category}</span>
          </div>
          {f.line && <code className="mb-1.5 block truncate rounded bg-muted px-2 py-1 font-mono text-xs">{f.line.trim()}</code>}
          <p>{f.message}</p>
        </li>
      ))}
    </ul>
  );
}

function DiagnosisCard({ d }: { d: Diagnosis }) {
  return (
    <div className="space-y-1.5 rounded-lg border bg-brand-soft/50 p-3">
      {d.bug_type && <p className="text-xs font-semibold tracking-wide text-primary uppercase">{d.bug_type}</p>}
      {d.bug_location && <code className="block truncate rounded bg-card px-2 py-1 font-mono text-xs">{d.bug_location.trim()}</code>}
      {d.explanation && <p>{d.explanation}</p>}
    </div>
  );
}

function Markdownish({ text }: { text: string }) {
  const parts = text.split(/```/);
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 0) {
          return part.trim() ? (
            <p key={i} className="whitespace-pre-wrap leading-relaxed">
              {part.trim()}
            </p>
          ) : null;
        }
        const newline = part.indexOf("\n");
        const lang = newline > 0 ? part.slice(0, newline).trim() : "";
        const code = newline >= 0 ? part.slice(newline + 1) : part;
        return <CodeBlock key={i} lang={lang} code={code.replace(/\n$/, "")} />;
      })}
    </>
  );
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="overflow-hidden rounded-lg border">
      <div className="flex items-center justify-between border-b bg-muted/60 px-3 py-1">
        <span className="font-mono text-[11px] text-muted-foreground">{lang || "code"}</span>
        <button
          type="button"
          onClick={() => {
            navigator.clipboard?.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
          className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto bg-card p-3 font-mono text-xs leading-relaxed">{code}</pre>
    </div>
  );
}
