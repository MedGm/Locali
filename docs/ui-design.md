# Web app design

## Architecture

```
browser ──> Next.js (frontend/, App Router, TypeScript) ──> FastAPI (backend/, localhost only)
                 server-side route handlers add the API token
```

- The browser only talks to Next.js. Next.js forwards `/api/*` to FastAPI from its server side and
  adds `Authorization: Bearer $LOCALI_API_TOKEN`, so the token never reaches the browser and
  FastAPI can stay bound to 127.0.0.1.
- Single user. The reviewer name recorded with approvals comes from settings.
- Live run progress uses Server-Sent Events from FastAPI, passed through by Next.js.
- UI: Tailwind + shadcn/ui components, TanStack Query for data, Recharts for the results pages,
  a side-by-side diff viewer for patches.

## Pages

| # | Page | What it shows | Wave |
|---|---|---|---|
| 1 | Dashboard | recent runs, patches awaiting approval, model server status, headline numbers | 1 |
| 2 | Run (live) | pipeline steps as they happen; agent trajectory: every model call with prompt, answer, tokens, latency | 1 |
| 3 | Findings | filter by tool / category / severity / file; code with inline annotations; tool vs model findings; mark false positive | 1 |
| 4 | Tests & suspects | generated tests, coverage before/after; triage suspects ("test wrong" / "code wrong"); a confirmed bug goes to the debug agent | 1 |
| 5 | Patch review | side-by-side diff, validation record, hashes; approve / reject / apply / revert / revalidate | 1 |
| 6 | Repositories | registered repos, file tree and code viewer, run history | 3 |
| 7 | Quality | complexity, maintainability index, debt hotspots, trend across runs | 3 |
| 8 | CI/CD | GitHub Action results per pull request, DevOps summary | 3 |
| 9 | Security center | audit log explorer, security events (refused paths, blocked commands, redactions, injection attempts), red-team results | 2 |
| 10 | Models | registry (base, QLoRA v2 F16/Q8/Q4, Hugging Face links, active model), prompt versions, tokens / latency / energy per run | 2 |
| 11 | Evaluation results | benchmarks, base vs fine-tuned, quantization ladder, context ablation, single vs multi-agent | 2 |
| 12 | Settings | model endpoint, repos root, approval policy, thresholds | 3 |

## Backend work behind wave 1

- API token on every endpoint except `/health`.
- Every model call of a run recorded (step, prompt, answer, tokens, latency) and served as the
  run's trajectory.
- Run progress: the current step stored on the run record, streamed over SSE.
- `GET /runs` (list), findings feedback (false positive), suspect triage that can start a
  targeted debug run, coverage before/after on the run record.
