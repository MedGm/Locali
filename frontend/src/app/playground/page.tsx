"use client";

import { BookOpen, Bug, FlaskConical, GitCompareArrows, Loader2, MessageSquare, ScanSearch, ShieldCheck, Sparkles, Square, Wand2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Choice } from "@/components/choice";
import { Answer, CopyButton } from "@/components/answer";
import { CodeEditor } from "@/components/code-editor";
import { ModelPicker, NO_MODEL, splitLabel, type ModelChoice } from "@/components/model-picker";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiQuery } from "@/lib/use-hydrated";
import { api, post, streamPlayground, type PlaygroundDone } from "@/lib/api";
import { useModelLabel } from "@/lib/models";
import { cn } from "@/lib/utils";

type Task = "review" | "tests" | "fix" | "explain" | "free";

const TASKS: { value: Task; label: string; icon: typeof Bug; hint: string; trained: boolean }[] = [
  { value: "review", label: "Review", icon: ScanSearch, hint: "Bugs, security and quality problems, line by line", trained: true },
  { value: "tests", label: "Write tests", icon: FlaskConical, hint: "Unit tests with edge cases", trained: true },
  { value: "fix", label: "Fix a bug", icon: Bug, hint: "Best with the failing test and its error", trained: true },
  { value: "explain", label: "Explain", icon: BookOpen, hint: "What the code does, step by step", trained: false },
  { value: "free", label: "Free prompt", icon: MessageSquare, hint: "Ask anything, with or without code", trained: false },
];

const LANGUAGES: [string, string][] = [
  ["python", "Python"],
  ["javascript", "JavaScript"],
  ["typescript", "TypeScript"],
  ["java", "Java"],
  ["go", "Go"],
  ["csharp", "C#"],
  ["cpp", "C++"],
  ["rust", "Rust"],
  ["php", "PHP"],
  ["ruby", "Ruby"],
  ["other", "Other"],
];

const EXAMPLES: Record<Task, { code: string; test?: string; error?: string; prompt?: string }> = {
  review: {
    code: `def find_user(conn, name):
    query = f"SELECT * FROM users WHERE name = '{name}'"
    rows = conn.execute(query).fetchall()
    return rows[0] if rows else None`,
  },
  tests: {
    code: `def slugify(title):
    """Lower-case the title, keep letters and digits, join words with single dashes."""
    words = "".join(c.lower() if c.isalnum() else " " for c in title).split()
    return "-".join(words)`,
  },
  fix: {
    code: `def apply_discount(total, percent):
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return round(total * (1 + percent / 100), 2)`,
    test: `def test_discount():
    assert apply_discount(200, 10) == 180.0`,
    error: "AssertionError: assert 220.0 == 180.0",
  },
  explain: {
    code: `import itertools


def chunks(items, size):
    it = iter(items)
    while batch := list(itertools.islice(it, size)):
        yield batch`,
  },
  free: { code: "", prompt: "When should I use a dataclass instead of a dict in Python? Give a short example." },
};

type Pane = { text: string; done?: PlaygroundDone; error?: string; running: boolean };

type CompareState = { available: boolean; current: string | null; starting: string | null; choices: ModelChoice[] };

export default function PlaygroundPage() {
  const models = useApiQuery({
    queryKey: ["playground-models"],
    queryFn: () => api<{ key: string; id: string }[]>("/playground/models"),
  });
  const compare = useApiQuery({
    queryKey: ["playground-compare"],
    queryFn: () => api<CompareState>("/playground/compare"),
  });
  const queryClient = useQueryClient();
  const label = useModelLabel();
  const [loading, setLoading] = useState<string | null>(null);
  const [task, setTask] = useState<Task>("review");
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState("");
  const [test, setTest] = useState("");
  const [error, setError] = useState("");
  const [prompt, setPrompt] = useState("");
  const [panes, setPanes] = useState<Record<string, Pane>>({});
  const abort = useRef<AbortController | null>(null);
  const running = Object.values(panes).some((p) => p.running);
  const available = models.data ?? [];
  const current = TASKS.find((t) => t.value === task)!;

  // the backend stops the running comparison model and starts the picked one (a few seconds to load)
  async function pickCompare(id: string) {
    const picked = id === NO_MODEL ? null : id;
    if (picked === (compare.data?.current ?? null)) return;
    setLoading(picked ?? NO_MODEL);
    setPanes((all) => Object.fromEntries(Object.entries(all).filter(([k]) => k !== "compare")));
    try {
      await post<CompareState>("/playground/compare", { id: picked });
      if (picked) toast.success(`${label(picked)} is ready`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["playground-compare"] }),
        queryClient.invalidateQueries({ queryKey: ["playground-models"] }),
      ]);
    }
  }

  function example() {
    const e = EXAMPLES[task];
    setLanguage("python");
    setCode(e.code);
    setTest(e.test ?? "");
    setError(e.error ?? "");
    setPrompt(e.prompt ?? "");
  }

  async function generate() {
    if (running || !available.length) return;
    abort.current = new AbortController();
    const body = { task, language, code, prompt, test, error };
    setPanes(Object.fromEntries(available.map((m) => [m.key, { text: "", running: true }])));
    // the models answer one after the other: on a laptop CPU two at once would only slow both down
    for (const m of available) {
      try {
        await streamPlayground(
          { ...body, model: m.key },
          (e) =>
            setPanes((all) => {
              const pane = all[m.key];
              if (e.type === "token") return { ...all, [m.key]: { ...pane, text: pane.text + e.text } };
              if (e.type === "done") return { ...all, [m.key]: { text: e.answer, done: e, running: false } };
              return { ...all, [m.key]: { ...pane, error: e.message, running: false } };
            }),
          abort.current.signal,
        );
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        if (!abort.current.signal.aborted) toast.error(message);
        setPanes((all) => ({ ...all, [m.key]: { ...all[m.key], error: abort.current?.signal.aborted ? "Stopped." : message, running: false } }));
        if (abort.current.signal.aborted) break;
      }
    }
    setPanes((all) => Object.fromEntries(Object.entries(all).map(([k, p]) => [k, { ...p, running: false }])));
  }

  if (models.data && !available.length)
    return (
      <div>
        <PageHeader title="Playground" description="Ask the model directly: paste code, pick a task, get an answer." />
        <EmptyState icon={Sparkles} title="No model connected">
          Start a model server and set LOCALI_MODEL_URL for the backend (see Settings). The playground uses the same model
          as the assistant.
        </EmptyState>
      </div>
    );

  const compareOn = available.length > 1;
  const canGenerate = !!models.data && (task === "free" ? !!prompt.trim() : !!code.trim());

  return (
    <div>
      <PageHeader
        title="Playground"
        description="Ask the model directly: paste code, pick a task, get an answer. Nothing here touches a repository."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(340px,420px)_minmax(0,1fr)]">
        <section className="space-y-5 rounded-xl border bg-card p-5 lg:sticky lg:top-20 lg:self-start">
          <div className="space-y-2.5">
            <p className="text-sm font-semibold">Task</p>
            <div className="grid grid-cols-5 gap-1.5">
              {TASKS.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setTask(t.value)}
                  className={cn(
                    "flex flex-col items-center gap-1 rounded-lg border px-1 py-2.5 text-[11px] leading-tight transition-colors",
                    task === t.value
                      ? "border-primary bg-primary/10 font-medium text-foreground"
                      : "text-muted-foreground hover:border-primary/40 hover:bg-muted/40 hover:text-foreground",
                  )}
                >
                  <t.icon className={cn("size-4", task === t.value && "text-primary")} />
                  {t.label}
                </button>
              ))}
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {current.hint}.{" "}
              {current.trained && language === "python"
                ? "Python uses the exact format the model was fine-tuned on."
                : current.trained
                  ? "The fine-tune was trained on Python; other languages get the base model's skills."
                  : ""}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Choice
              label="Language"
              value={language}
              onChange={setLanguage}
              className="h-9 min-w-36 flex-1 bg-background"
              options={LANGUAGES.map(([value, label]) => ({ value, label }))}
            />
            <Button variant="outline" className="h-9" onClick={example}>
              <Wand2 /> Example
            </Button>
          </div>

          {task !== "free" || code ? (
            <Field label={task === "free" ? "Code (optional)" : "Code"}>
              <CodeEditor
                value={code}
                onChange={setCode}
                language={language}
                minHeight="200px"
                placeholder="Paste a function or a file…"
                onSubmit={generate}
              />
            </Field>
          ) : null}
          {task === "fix" && (
            <>
              <Field label="Failing test" optional>
                <CodeEditor value={test} onChange={setTest} language={language} minHeight="72px" placeholder="def test_…" onSubmit={generate} />
              </Field>
              <Field label="Error" optional>
                <CodeEditor value={error} onChange={setError} language="text" minHeight="48px" placeholder="AssertionError: …" onSubmit={generate} />
              </Field>
            </>
          )}
          <Field label={task === "free" ? "Prompt" : "Instructions"} optional={task !== "free"}>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === "Enter" && generate()}
              rows={task === "free" ? 5 : 2}
              placeholder={task === "free" ? "Ask anything…" : "e.g. focus on error handling"}
              className="w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
            />
          </Field>

          <div className="space-y-2">
            {running ? (
              <Button variant="outline" className="h-10 w-full" onClick={() => abort.current?.abort()}>
                <Square /> Stop
              </Button>
            ) : (
              <Button className="h-10 w-full" onClick={generate} disabled={!canGenerate}>
                <Sparkles /> Generate
                <kbd className="ml-auto rounded border border-primary-foreground/30 px-1.5 font-mono text-[10px] opacity-80">
                  Ctrl ↵
                </kbd>
              </Button>
            )}
            <p className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
              <ShieldCheck className="size-3.5" /> Secrets are removed before the model sees the text.
            </p>
          </div>
        </section>

        <section className="min-w-0 space-y-3">
          <div className="flex min-h-9 flex-wrap items-center gap-3">
            <p className="text-sm font-semibold">Answers</p>
            {compare.data?.available && (
              <div className="ml-auto flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Compare with</span>
                <ModelPicker
                  value={loading ?? compare.data.current ?? NO_MODEL}
                  choices={compare.data.choices}
                  label={label}
                  loading={!!loading && loading !== NO_MODEL}
                  disabled={!!loading || running}
                  onChange={pickCompare}
                />
              </div>
            )}
          </div>
          <div className={cn("grid gap-3", (compareOn || (loading && loading !== NO_MODEL)) && "md:grid-cols-2")}>
            {available.map((m) => (
              <AnswerPane key={m.key} model={m} name={label(m.id)} pane={panes[m.key]} expanded={Object.keys(panes).length > 0} />
            ))}
            {loading && loading !== NO_MODEL && !available.some((m) => m.key === "compare") && (
              <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card/50 text-center">
                <Loader2 className="size-5 animate-spin text-amber-500" />
                <div>
                  <p className="text-sm font-medium">Starting {label(loading)}</p>
                  <p className="text-xs text-muted-foreground">Loading the model into memory, a few seconds</p>
                </div>
              </div>
            )}
          </div>
          {compare.data?.available && !compareOn && !loading && (
            <p className="flex items-center gap-2 rounded-lg border border-dashed px-3 py-2.5 text-xs text-muted-foreground">
              <GitCompareArrows className="size-4 shrink-0" />
              Pick a model in “Compare with” to see its answer beside the assistant’s, for example the base model it was
              fine-tuned from.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function Field({ label, optional, children }: { label: string; optional?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium">
        {label}
        {optional && <span className="ml-1 font-normal text-muted-foreground">optional</span>}
      </p>
      {children}
    </div>
  );
}

function AnswerPane({
  model,
  name,
  pane,
  expanded,
}: {
  model: { key: string; id: string };
  name: string;
  pane?: Pane;
  expanded: boolean;
}) {
  const d = pane?.done;
  const [copied, setCopied] = useState(false);
  const body = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const [title, quant] = splitLabel(name);
  // "Qwen2.5-Coder-3B fine-tuned (run E)" -> "Qwen2.5-Coder-3B" over "fine-tuned (run E)"
  const cut = title.indexOf(" ");
  const family = cut > 0 ? title.slice(0, cut) : title;
  const variant = cut > 0 ? title.slice(cut + 1) : "";
  const main = model.key === "main";
  // keep the newest text in view while it streams, unless the reader has scrolled up
  useEffect(() => {
    const el = body.current;
    if (el && pane?.running && follow.current) el.scrollTop = el.scrollHeight;
  }, [pane?.text, pane?.running]);
  const waiting = pane?.running && !pane.text && !main;
  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-xl border bg-card transition-[height]",
        expanded ? "h-[calc(100vh-12rem)] min-h-[440px]" : "min-h-[320px]",
      )}
    >
      <div className="flex items-center gap-2.5 border-b px-4 py-2.5">
        <span className={cn("size-2 shrink-0 rounded-full", main ? "bg-primary" : "bg-amber-500")} />
        <div className="min-w-0 flex-1 leading-tight" title={`${name} (${model.id})`}>
          <p className="truncate text-sm font-medium">{family}</p>
          {variant && <p className="truncate text-xs text-muted-foreground">{variant}</p>}
        </div>
        {quant && <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{quant}</span>}
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
            main ? "bg-primary/10 text-primary" : "bg-amber-500/10 text-amber-600 dark:text-amber-400",
          )}
        >
          {main ? "Assistant" : "Comparison"}
        </span>
        {pane?.text && !pane.running && <CopyButton text={pane.text} copied={copied} onCopied={setCopied} />}
      </div>
      <div
        ref={body}
        onScroll={(e) => {
          const el = e.currentTarget;
          follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
        className="min-h-0 flex-1 overflow-y-auto p-4"
      >
        {!pane ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <div className="rounded-full bg-muted p-2.5">
              <Sparkles className="size-4 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">Answers stream here as the model writes them.</p>
          </div>
        ) : pane.error && !pane.text ? (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
            {pane.error}
          </p>
        ) : waiting ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" /> Waiting for the assistant model to finish: on a laptop CPU, one
            model at a time is faster.
          </p>
        ) : !pane.text && pane.running ? (
          <div className="space-y-2.5">
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="size-2 animate-pulse rounded-full bg-primary" /> Reading the prompt…
            </p>
            <Skeleton className="h-3 w-4/5" />
            <Skeleton className="h-3 w-3/5" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        ) : (
          <Answer text={pane.text} streaming={pane.running} />
        )}
      </div>
      {(d || pane?.running) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t bg-muted/20 px-4 py-2 text-[11px] text-muted-foreground tabular-nums">
          {d ? (
            <>
              <Stat label="tokens" value={`${d.input_tokens ?? "?"} → ${d.output_tokens ?? "?"}`} />
              <Stat label="first token" value={`${d.ttft_s.toFixed(2)} s`} />
              <Stat label="total" value={`${d.total_s.toFixed(1)} s`} />
              {d.output_tokens && d.total_s > d.ttft_s ? (
                <Stat label="speed" value={`${(d.output_tokens / (d.total_s - d.ttft_s)).toFixed(1)} tok/s`} />
              ) : null}
            </>
          ) : (
            <span className="flex items-center gap-1.5">
              <Loader2 className="size-3 animate-spin" /> Generating…
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span>
      {label} <span className="font-medium text-foreground">{value}</span>
    </span>
  );
}
