"use client";

import { BookOpen, Bug, FlaskConical, MessageSquare, ScanSearch, Sparkles, Square, Wand2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Choice } from "@/components/choice";
import { Answer, CopyButton } from "@/components/answer";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { useApiQuery } from "@/lib/use-hydrated";
import { api, streamPlayground, type PlaygroundDone } from "@/lib/api";
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
    code: `def chunks(items, size):
    it = iter(items)
    while batch := list(itertools.islice(it, size)):
        yield batch`,
  },
  free: { code: "", prompt: "When should I use a dataclass instead of a dict in Python? Give a short example." },
};

type Pane = { text: string; done?: PlaygroundDone; error?: string; running: boolean };

export default function PlaygroundPage() {
  const models = useApiQuery({
    queryKey: ["playground-models"],
    queryFn: () => api<{ key: string; id: string }[]>("/playground/models"),
  });
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

  return (
    <div>
      <PageHeader
        title="Playground"
        description="Ask the model directly: paste code, pick a task, get an answer. Nothing here touches a repository."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(320px,380px)_minmax(0,1fr)]">
        <section className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <p className="text-sm font-semibold">What should the model do?</p>
          <div className="flex flex-wrap gap-1.5">
            {TASKS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTask(t.value)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors",
                  task === t.value
                    ? "border-primary bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:border-primary/40 hover:text-foreground",
                )}
              >
                <t.icon className="size-3.5" />
                {t.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {current.hint}.{" "}
            {current.trained && language === "python"
              ? "Python uses the exact format the model was fine-tuned on."
              : current.trained
                ? "The fine-tune was trained on Python; other languages get the base model's skills."
                : ""}
          </p>

          <div className="flex flex-wrap items-center gap-2">
            <Choice
              label="Language"
              value={language}
              onChange={setLanguage}
              options={LANGUAGES.map(([value, label]) => ({ value, label }))}
            />
            <Button variant="outline" size="sm" onClick={example}>
              <Wand2 /> Try an example
            </Button>
          </div>

          {task !== "free" || code ? (
            <Field label={task === "free" ? "Code (optional)" : "Code"}>
              <CodeArea value={code} onChange={setCode} rows={10} placeholder="Paste a function or a file…" onSubmit={generate} />
            </Field>
          ) : null}
          {task === "fix" && (
            <div className="grid gap-3">
              <Field label="Failing test (optional)">
                <CodeArea value={test} onChange={setTest} rows={4} placeholder="def test_…" onSubmit={generate} />
              </Field>
              <Field label="Error (optional)">
                <CodeArea value={error} onChange={setError} rows={3} placeholder="AssertionError: …" onSubmit={generate} />
              </Field>
            </div>
          )}
          <Field label={task === "free" ? "Prompt" : "Anything to add? (optional)"}>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === "Enter" && generate()}
              rows={task === "free" ? 5 : 2}
              placeholder={task === "free" ? "Ask anything…" : "e.g. focus on error handling"}
              className="w-full resize-y rounded-lg border bg-card px-3 py-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
            />
          </Field>

          <div className="flex items-center gap-3">
            {running ? (
              <Button variant="outline" onClick={() => abort.current?.abort()}>
                <Square /> Stop
              </Button>
            ) : (
              <Button onClick={generate} disabled={!models.data}>
                <Sparkles /> Generate
              </Button>
            )}
            <span className="text-xs text-muted-foreground">Ctrl + Enter. Secrets are removed before the model sees the text.</span>
          </div>
        </section>

        <section className="min-w-0 space-y-3">
          <p className="text-sm font-semibold">Answers</p>
          <div className={cn("grid gap-3", available.length > 1 && "md:grid-cols-2")}>
            {available.map((m) => (
              <AnswerPane key={m.key} model={m} pane={panes[m.key]} />
            ))}
          </div>
          {available.length === 1 && (
            <p className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
              To compare with a second model (for example the base model, or the Q4 version) side by side, start another
              model server and set LOCALI_COMPARE_URL and LOCALI_COMPARE_ID for the backend.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function CodeArea(props: {
  value: string;
  onChange: (v: string) => void;
  rows: number;
  placeholder: string;
  onSubmit: () => void;
}) {
  return (
    <textarea
      value={props.value}
      onChange={(e) => props.onChange(e.target.value)}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") props.onSubmit();
        if (e.key === "Tab") {
          e.preventDefault();
          const t = e.currentTarget;
          const { selectionStart: s, selectionEnd: end } = t;
          props.onChange(t.value.slice(0, s) + "    " + t.value.slice(end));
          requestAnimationFrame(() => t.setSelectionRange(s + 4, s + 4));
        }
      }}
      rows={props.rows}
      spellCheck={false}
      placeholder={props.placeholder}
      className="w-full resize-y rounded-lg border bg-card px-3 py-2 font-mono text-xs leading-relaxed outline-none focus-visible:ring-3 focus-visible:ring-ring/40"
    />
  );
}

function AnswerPane({ model, pane }: { model: { key: string; id: string }; pane?: Pane }) {
  const d = pane?.done;
  const [copied, setCopied] = useState(false);
  const body = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  // keep the newest text in view while it streams, unless the reader has scrolled up
  useEffect(() => {
    const el = body.current;
    if (el && pane?.running && follow.current) el.scrollTop = el.scrollHeight;
  }, [pane?.text, pane?.running]);
  return (
    <div className="flex h-[calc(100vh-13rem)] min-h-[440px] flex-col overflow-hidden rounded-xl border bg-card">
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <span className={cn("size-2 rounded-full", model.key === "main" ? "bg-primary" : "bg-amber-500")} />
        <span className="text-sm font-medium">{model.id}</span>
        <span className="text-xs text-muted-foreground">{model.key === "main" ? "assistant model" : "comparison"}</span>
        <span className="ml-auto">
          {pane?.text && !pane.running && <CopyButton text={pane.text} copied={copied} onCopied={setCopied} />}
        </span>
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
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
            <Sparkles className="size-5 opacity-60" />
            The answer will appear here.
          </div>
        ) : pane.error && !pane.text ? (
          <p className="text-sm text-red-700 dark:text-red-400">{pane.error}</p>
        ) : !pane.text && pane.running ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="size-2 animate-pulse rounded-full bg-primary" /> Reading the prompt…
          </p>
        ) : (
          <Answer text={pane.text} streaming={pane.running} />
        )}
      </div>
      <div className="flex min-h-9 flex-wrap items-center gap-x-4 gap-y-1 border-t px-4 py-2 text-[11px] text-muted-foreground tabular-nums">
        {d ? (
          <>
            <span>{d.input_tokens ?? "?"} tokens in</span>
            <span>{d.output_tokens ?? "?"} tokens out</span>
            <span>first token {d.ttft_s.toFixed(2)} s</span>
            <span>total {d.total_s.toFixed(1)} s</span>
            {d.output_tokens && d.total_s > d.ttft_s && (
              <span>{(d.output_tokens / (d.total_s - d.ttft_s)).toFixed(1)} tokens/s</span>
            )}
          </>
        ) : pane?.running ? (
          <span>Generating…</span>
        ) : (
          <span>Tokens and speed appear here.</span>
        )}
      </div>
    </div>
  );
}
