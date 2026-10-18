"use client";

import { Check, Copy } from "lucide-react";
import { Fragment, useState } from "react";

import { SeverityBadge } from "@/components/badges";
import type { Severity } from "@/lib/api";

type Finding = { line?: string; category?: string; severity?: string; message?: string };
type Diagnosis = { bug_location?: string; bug_type?: string; explanation?: string };

// Answers in the trained formats start with a JSON object: {"findings": [...]} for a review,
// {"bug_location", "bug_type", "explanation"} before the fixed code for a repair. Show those as
// cards; everything else as formatted text with highlighted code blocks.
export function Answer({ text, streaming }: { text: string; streaming?: boolean }) {
  const { json, rest } = leadingJson(text);
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      {json && "findings" in json && Array.isArray(json.findings) && <Findings findings={json.findings as Finding[]} />}
      {json && ("bug_location" in json || "explanation" in json) && <DiagnosisCard d={json as Diagnosis} />}
      <Markdown text={json ? rest : text} />
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
    return (
      <p className="rounded-lg border bg-emerald-50 px-3 py-2 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">
        No problems found.
      </p>
    );
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

// A small Markdown renderer for model answers: code fences, headings, lists, bold, inline code.
function Markdown({ text }: { text: string }) {
  const parts = text.split(/^```/m);
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Blocks key={i} text={part} />;
        const newline = part.indexOf("\n");
        const lang = newline > 0 ? part.slice(0, newline).trim() : "";
        const code = newline >= 0 ? part.slice(newline + 1) : part;
        return <CodeBlock key={i} lang={lang} code={code.replace(/\n$/, "")} />;
      })}
    </>
  );
}

function Blocks({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)/);
    if (heading) {
      out.push(
        <p key={i} className="pt-1 font-semibold">
          <Inline text={heading[2]} />
        </p>,
      );
      i++;
      continue;
    }
    const list = line.match(/^\s*([-*•]|\d+[.)])\s+/);
    if (list) {
      const ordered = /\d/.test(list[1]);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*•]|\d+[.)])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*•]|\d+[.)])\s+/, ""));
        i++;
      }
      const Tag = ordered ? "ol" : "ul";
      out.push(
        <Tag key={i} className={ordered ? "list-decimal space-y-1 pl-5" : "list-disc space-y-1 pl-5"}>
          {items.map((it, k) => (
            <li key={k}>
              <Inline text={it} />
            </li>
          ))}
        </Tag>,
      );
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\s*([-*•]|\d+[.)])\s+)/.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    out.push(
      <p key={i}>
        <Inline text={para.join(" ")} />
      </p>,
    );
  }
  return <>{out}</>;
}

function Inline({ text }: { text: string }) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return (
    <>
      {tokens.map((t, i) =>
        t.startsWith("`") && t.endsWith("`") && t.length > 1 ? (
          <code key={i} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
            {t.slice(1, -1)}
          </code>
        ) : t.startsWith("**") && t.endsWith("**") && t.length > 3 ? (
          <strong key={i} className="font-semibold">
            {t.slice(2, -2)}
          </strong>
        ) : (
          <Fragment key={i}>{t}</Fragment>
        ),
      )}
    </>
  );
}

const KEYWORDS = new Set(
  (
    "def class return if elif else for while in not and or is None True False import from as with try except finally raise " +
    "lambda yield pass break continue async await global nonlocal assert del " +
    "function const let var new this typeof instanceof switch case default throw catch export extends implements interface " +
    "public private protected static final void int long double float boolean char String package func go defer struct type map " +
    "range chan fn mut impl match use pub mod enum trait where self Self null undefined true false " +
    "SELECT FROM WHERE JOIN LEFT RIGHT INNER OUTER ON GROUP BY ORDER HAVING AS AND OR NOT NULL INSERT INTO VALUES UPDATE SET " +
    "DELETE CREATE TABLE DESC ASC LIMIT DISTINCT COUNT SUM AVG MIN MAX NULLIF CASE WHEN THEN END"
  ).split(" "),
);
const TOKEN = /(#[^\n]*|\/\/[^\n]*|--[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b)/g;

function highlight(code: string, lang: string) {
  const hashComments = !["javascript", "js", "typescript", "ts", "java", "go", "rust", "cpp", "c", "csharp", "sql"].includes(lang);
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of code.matchAll(TOKEN)) {
    const t = m[0];
    const at = m.index ?? 0;
    if (at > last) out.push(code.slice(last, at));
    let cls = "";
    if ((t.startsWith("#") && hashComments) || t.startsWith("//") || (t.startsWith("--") && lang === "sql")) cls = "text-muted-foreground italic";
    else if (/^["'`]/.test(t)) cls = "text-emerald-700 dark:text-emerald-400";
    else if (/^\d/.test(t)) cls = "text-amber-700 dark:text-amber-400";
    else if (KEYWORDS.has(t)) cls = "text-primary font-medium";
    out.push(cls ? <span key={at} className={cls}>{t}</span> : t);
    last = at + t.length;
  }
  out.push(code.slice(last));
  return out;
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="overflow-hidden rounded-lg border bg-muted/40">
      <div className="flex items-center justify-between border-b px-3 py-1">
        <span className="font-mono text-[11px] text-muted-foreground">{lang || "code"}</span>
        <CopyButton text={code} copied={copied} onCopied={setCopied} />
      </div>
      <pre className="overflow-x-auto p-3 font-mono text-xs leading-relaxed">{highlight(code, lang.toLowerCase())}</pre>
    </div>
  );
}

export function CopyButton({
  text,
  copied,
  onCopied,
  label = true,
}: {
  text: string;
  copied: boolean;
  onCopied: (v: boolean) => void;
  label?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label="Copy"
      onClick={() => {
        navigator.clipboard?.writeText(text);
        onCopied(true);
        setTimeout(() => onCopied(false), 1500);
      }}
      className="flex items-center gap-1 rounded px-1 text-[11px] text-muted-foreground hover:text-foreground"
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {label && (copied ? "Copied" : "Copy")}
    </button>
  );
}
