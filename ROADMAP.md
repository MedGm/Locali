# Roadmap

Solo, 15 weeks, ~20 h/week. Deadline 01/01/2027, target submission 30/12/2026.

**Hardware split**
- Laptop (i5-10210U, 16 GB RAM, no GPU): development, app, agents, MCP, security, CPU inference via llama.cpp.
- Kaggle (T4, 30 GPU-h/week): fine-tuning, GPU benchmarks.
- Hugging Face Hub: adapters and quantized models.

**Rules**
1. Test risky pieces first.
2. Evaluation harness before fine-tuning.
3. Write app code while GPU jobs run.
4. Model behind one OpenAI-compatible endpoint.
5. Security built into each layer; W13 only measures it.
6. Cover every spec bullet at minimum depth, then deepen.
7. Timebox phases. Negative results get documented, not chased.
8. Python only.

## Phases

### W0 · Sep 15–20 · Setup
- [x] Free disk space
- [x] Repo skeleton, spec checklist, roadmap
- [x] Install uv, build llama.cpp
- [x] Kaggle account + CLI access token (`~/.kaggle/access_token`)
- [x] Hugging Face account + write token
- [x] Choose and pin model versions (`experiments/configs/models.yaml`)
- [x] Local inference smoke test (llama.cpp server, OpenAI-compatible)

### W1–2 · Sep 21–Oct 4 · Risk tests + evaluation harness
- [x] Spike: Unsloth tiny run on Kaggle T4 — Qwen2.5-Coder-1.5B and Phi-4-mini QLoRA work; Qwen3.5-2B training blocked ([results](experiments/results/w1_spikes/README.md))
- [x] Spike: vLLM serving on T4 — Qwen3.5-9B teacher, TP=2, 101 tok/s
- [x] Spike: pytest inside Docker, no network — `security/sandbox.py`, 9 probe tests (network, read-only, non-root, env, timeout kill, memory, pids)
- [x] Spike: one MCP tool called from LangGraph — `mcp_servers/repo_server.py`, 10 tests; tool-calling check: Qwen2.5-Coder-1.5B 0/10 native calls, Qwen3.5-2B 10/10 → fixed routing
- [x] Harness: client, results JSON schema, metrics logger (tokens, TTFT, tok/s, energy; memory still todo) — `evaluation/`, 53 tests
- [x] Harness validation: all reference solutions pass (163 HumanEval+, 377 MBPP+ after 2 documented exclusions)
- [x] Tasks (10, all validated): HumanEval+, MBPP+, HumanEvalFix, bug detection, CRUXEval-O, test generation, refactoring, completion (infilling, replaces SAFIM), SecurityEval insecure generation, vulnerability detection — [validation](experiments/results/harness_validation/README.md)
- [x] Unattended laptop baseline script with energy: `experiments/scripts/laptop_baselines.sh`
- [ ] Locali-Fresh: first 30 contamination-free tasks
- [x] `demo_repo/`: bugs, vulnerabilities, fake secret, missing tests, malicious README (answer key in `security/demo_repo_flaws.json`)
- [x] Laptop CPU baselines with energy, HumanEval+ and MBPP+: Qwen2.5-Coder-1.5B, Qwen3.5-2B ([results](experiments/results/baselines/README.md))
- [x] Full baselines on Kaggle, 10 tasks × 4 models ([results](experiments/results/kaggle_baselines_20261012/README.md))
- [x] Qwen3.5-9B reference baseline (2 × T4, separate session) ([results](experiments/results/kaggle_reference_20261012/README.md))
- **Gate:** baseline table reproducible from one command

### W3–5 · Oct 5–25 · Fine-tuning
Design: [docs/research-design.md](docs/research-design.md)
- [x] Data pipelines: T1 mutation bugs, T2 tests, T3 tool-grounded reviews, replay set ([mix v1](experiments/results/data_mix_v1/README.md)); v2 adds T4 execution traces, 5 more bug operators, verified clean reviews ([mix v2](experiments/results/data_mix_v2/README.md))
- [x] Teacher explanations with Qwen3.5-9B (v1 + v2, ~1.5 GPU-h); CodeReviewer license not verified → not used, T3 stays synthetic (decision D3)
- [x] Decontaminate (13-gram) against all eval sets; grouped split (0 groups in more than one split)
- [x] Unsloth QLoRA run + LoRA run + rsLoRA run on Qwen2.5-Coder-1.5B ([v1](experiments/results/finetune_qwen25_qlora_v1/README.md), [v2](experiments/results/finetune_v2/README.md)); DoRA not run
- [x] QLoRA run on Phi-4-mini (in the [v2 report](experiments/results/finetune_v2/README.md))
- [x] Evaluate with harness: benchmarks, [format-transfer check](experiments/results/format_transfer_qwen25_v1/README.md), in-distribution tasks, paired McNemar tests. Published on Hugging Face (public, `MedGm/Llama-Locali-*`, dataset `MedGm/locali-mix-v2`; "Llama" prefix required by the Llama 3.1 licence)
- [x] During GPU waits: FastAPI skeleton (`backend/app.py`), static analysis (`backend/analysis.py`), secret scanner (`security/secrets.py`), audit log
- **Gate:** fine-tuned model evaluated and documented — **passed 2026-10-13**. Deployment model: Qwen2.5-Coder-1.5B + QLoRA v2

### W6–7 · Oct 26–Nov 8 · Optimization ladder
- [x] Merge adapter, export FP16 / INT8 / INT4 ([merge](experiments/results/merge_qwen25_qlora_v2/README.md), [laptop ladder](experiments/results/ladder_laptop/README.md))
- [x] Prompt optimization and context slicing ([repair on T4](experiments/results/context_ablation_t4/README.md), [agents on demo_repo](experiments/results/context_agents/README.md))
- [ ] KV cache and batching tests (T4)
- [ ] Experiments A–F
- [x] During waits: 3 MCP servers (repo, tests, analysis)
- **Gate:** optimization table + plots generated by script

### W8–10 · Nov 9–29 · Agents + security controls
- [x] LangGraph: analysis → review → test gen → sandbox tests → debug loop → report (`backend/agents/`); docstring step (docstring-only changes, checked on the syntax tree) and DevOps summary step (merge readiness, typosquat check, CI suggestion)
- [x] Allow-lists (`security/commands.py`), approval of exact validated patches (`backend/patches.py`), audit log, output validation (sandbox tests, Bandit/Semgrep, secret scan)
- [x] Single-agent vs multi-agent ablation ([results](experiments/results/agents_demo_repo/README.md))
- **Gate:** full workflow runs on `demo_repo/` via API — **passed 2026-10-15** (real model, 11 min, validated patch awaiting review)

### W11–12 · Nov 30–Dec 13 · React + CI/CD + LLMOps
- [x] Next.js/TypeScript app, 11 pages: dashboard, repositories, runs (live progress), patches (diff review, approve/apply/revert), security center, models, quality trends, results, settings (`frontend/`)
- [x] GitHub Action on pull requests (`.github/workflows/locali-review.yml`) + CI for this repository (`ci.yml`)
- [x] MLflow dashboard linked from metrics page (agent runs + traces logged live; evaluations, training runs and datasets backfilled by `experiments/scripts/log_to_mlflow.py`)
- **Gate:** end-to-end run from browser — **passed 2026-10-16** (agent run started, followed live and reviewed from the browser)

### W13 · Dec 14–20 · Red-team + final runs
- [x] Attack cases with defenses off vs on: 16 control cases (0/16 with, 16/16 without) and 17 model attacks (0 harm through the controls); two gaps found and fixed ([results](experiments/results/redteam/README.md))
- [ ] Rerun all experiments from clean state
- **Feature freeze Dec 20**

### W14–15 · Dec 21–Jan 1 · Report + demo
- [ ] README report with figures
- [ ] 5-min demo, scripted and timed
- **Submit by Dec 30**

## Status 2026-10-17 (week 5)

- Done: W0–5, W8–10, W11–12 (about seven weeks early). All six agent steps, the safety layer, the API, the web app, CI with pull request review, and MLflow.
- Open: rest of W6–7 (prompt optimization, KV cache and batching on T4), W13 red-team, W14–15 report and demo, UI design pass.

## Cut order if behind
1. Phi fine-tuning
2. LoRA vs QLoRA comparison (keep QLoRA)
3. React down to 1 page + FastAPI docs
4. DevOps agent reduced to CI summary
5. Energy measurement

Never cut: base vs fine-tuned, quantization ladder, security controls + attack tests, working end-to-end demo.
