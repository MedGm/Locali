# Spec checklist

Every requirement from the project brief, mapped to where it gets satisfied and when.
Status: `todo` · `wip` · `done` · `cut` (with reason).

Week numbers refer to [ROADMAP.md](../ROADMAP.md).

## 1. Objective

| # | Requirement | Satisfied by | Week | Status |
|---|---|---|---|---|
| O1 | SE assistant built on SLMs (Qwen, Phi) | `backend/` + `frontend/` running on Qwen main model | W8–12 | todo |
| O2 | Show reduced GPU memory, latency, cost, tokens vs larger LLMs | Optimization table + comparison with a 7B/API reference | W6–7 | todo |

## 2. Components

| # | Requirement | Solo minimum | Location | Week | Status |
|---|---|---|---|---|---|
| C1 | SLM benchmarking: code generation, completion, bug detection, explanation, refactoring, test generation | 3 models × 6 tasks on benchmark subsets | `evaluation/`, `experiments/` | W1–2 | done: 10 tasks × 4 SLMs + Qwen3.5-9B reference on Kaggle, laptop CPU baselines |
| C2 | Efficient fine-tuning with Unsloth, LoRA/QLoRA, other PEFT | 1 model, QLoRA + LoRA runs on Kaggle T4 | `training/` | W3–5 | done: QLoRA, 16-bit LoRA, rsLoRA (Qwen2.5-Coder) + Phi-4-mini QLoRA, Unsloth |
| C3 | Quantization 4/8-bit | FP16 / INT8 / INT4 on T4 and laptop CPU | `experiments/` | W6–7 | todo |
| C4 | KV cache, efficient attention, batching | Prefix caching on/off, batch 1/4/16, SDPA vs eager | `experiments/` | W6–7 | done on a T4: concurrency 1/4/16 (13.6× throughput, 15× less energy per answer), prefix caching on/off (no gain on repair prompts; warm cache halves TTFT), CUDA graphs vs eager (1.6× at 1 request), KV cache on/off (2.1×), SDPA vs eager attention (eager breaks in FP16) ([results](../experiments/results/serving_t4/README.md)) |
| C5 | Context compression, prompt optimization, token reduction | AST slicing + compact prompts, tokens before/after | `evaluation/`, `backend/` | W6–7 | done: repair context ablation on T4 (full suite / compressed vs standard) and agent context settings on demo_repo (file / function / slice / compact; slice cuts model false positives 17→6 for +21 % input) ([results](../experiments/results/context_agents/README.md)) |
| C6 | Measure latency, throughput, memory, cost | Shared metrics logger in harness | `evaluation/` | W1–2 | wip (tokens, TTFT, decode tok/s, CPU + GPU energy, training peak memory done; inference memory, cost todo) |
| C7 | Code quality, maintainability, complexity, vulnerabilities, standards, technical debt | Ruff, Radon, Bandit, Semgrep + LLM summary | `backend/` | W3–5 | wip (tools in `backend/analysis.py`; LLM summary todo) |
| C8 | Static-analysis tool integration | Same tools exposed via MCP | `mcp_servers/` | W6–7 | done (`analysis_server`: Ruff, Bandit, Radon, Semgrep, secrets) |
| C9 | Generate unit, integration, API tests | Test-generation agent on `demo_repo/` | `backend/` | W8–10 | todo |
| C10 | Test coverage analysis | pytest-cov before/after | `backend/` | W8–10 | todo |
| C11 | Regression tests | Tests generated for fixed bugs, kept in suite | `backend/` | W8–10 | todo |
| C12 | Detect failing tests, propose fixes | Debug loop, max 3 attempts, human approval | `backend/` | W8–10 | todo |
| C13 | LangGraph agents: Code Analysis, Test Generation, Debugging, Documentation, Code Review, DevOps | 6 nodes, deterministic routing | `backend/` | W8–10 | done: analysis, review, test generation, debugging, documentation and DevOps steps in one LangGraph graph (`backend/agents/workflow.py`) |
| C14 | MCP access to tools, repos, docs, databases, issue trackers, test frameworks, DevOps | 3 servers: repo (read-only), test runner, static analysis | `mcp_servers/` | W6–10 | done: repo (read-only, redacted), tests (sandboxed pytest + coverage), static analysis |
| C15 | Git/GitHub + CI/CD: review, tests, quality, docs, deployment assistance | 1 GitHub Action on pull requests | `.github/workflows/` | W11–12 | wip (CI: lint, 331 tests incl. sandbox, frontend build; PR review: new findings + secrets, comment, blocking; docs/deployment assistance todo) |
| C16 | LLMOps: model versions, prompts, datasets, performance, tokens, agent trajectories, eval results | MLflow runs + JSONL traces | `experiments/`, `backend/` | W1–12 | done: agent runs as MLflow runs with traces (steps, model calls, tokens), evaluations (235 runs), training runs with loss curves, datasets; JSONL trajectories per run |
| C17 | React/TypeScript web app + FastAPI backend, visualize quality and DevOps results | 3 pages: run, results/approval, metrics | `frontend/`, `backend/` | W11–12 | done: 12 pages incl. a guided home, repositories, runs, patch review, a playground comparing two models, security, quality trends, research results and settings; light and dark themes ([screenshots](../README.md#the-web-app)) |

## 3. LLM security

| # | Threat | Control | Attack test | Week | Status |
|---|---|---|---|---|---|
| S1 | Prompt injection, indirect injection (code, repos, issues, docs) | Untrusted content never grants permissions; delimiting; detector as extra layer | Malicious README, comments, issue text | W8–13 | done: payloads in code comments, docstrings and strings, real model: complied with 3/11 (all the review missing an SQL injection it misses without a payload too), harm through the controls 0/11; README/issue text never reaches the model and is flagged by `security/injection.py` ([results](../experiments/results/redteam/README.md)) |
| S2 | Jailbreaking | System-prompt hardening + output policy check | Jailbreak prompt set | W8–13 | done: jailbreak payloads in code, real model: complied 0/6, harm 0/6 ([results](../experiments/results/redteam/model.md)); the model has no chat surface, output is only parsed into findings or code that is validated |
| S3 | Data leakage (code, credentials, API keys) | Secret scanning + redaction before model and in outputs | Fake keys in `demo_repo/` | W3–13 | done: 0/2 attacks with redaction, 2/2 without; red-team found that a key repeated without its assignment slipped through, fixed by redacting the exact values found in the repository |
| S4 | Malicious code, unsafe commands | Command allow-list, output validation | Generated `rm -rf`, `curl \| bash` | W8–13 | done: `rm -rf`, `curl \| sh` and a destructive generated test: 0/3 with the allow-list and sandbox, 3/3 without |
| S5 | MCP/tool security, excessive permissions | Least-privilege servers, per-tool allow-list | Call to non-allowed tool | W6–13 | done: `../` and symlink escapes: 0/2 with path confinement, 2/2 without |
| S6 | Supply-chain, repository poisoning | Dependency pinning, no install from untrusted repo, sandbox | Poisoned `requirements.txt` | W8–13 | done: poisoned conftest.py 0/1 in the sandbox (1/1 on the host); typosquat `reqeusts` flagged by the DevOps step |
| S7 | Insecure output handling, generated-code vulnerabilities | Semgrep/Bandit on generated code before acceptance | Vulnerable patch | W8–13 | done: fixes adding eval, shell=True, os.system(constant) and a hard-coded key: 0/4 through validation, 4/4 without; red-team found os.system(constant) passed (Bandit rates it low), fixed with a Semgrep rule |
| S8 | Excessive agent autonomy | Human approval for writes, iteration limits | Agent attempts unapproved write | W8–13 | done: unapproved apply, forged approval hash, stale patch: 0/3 with the approval gate, 3/3 without |

Required controls, all covered above: least privilege · sandboxed execution · tool allow-lists · input/output validation · secret filtering · human approval · complete audit logging.

## 4. Experimental evaluation

Pipeline: SLM → Fine-tuning → Quantization → Token optimization → Agentic workflow → SE tasks.

| Metric | Source | Status |
|---|---|---|
| Code correctness, pass@k | EvalPlus (HumanEval+/MBPP+) | done |
| Unit-test pass rate | pytest runs in sandbox | done (harness) |
| Test coverage | pytest-cov | done (harness: line + branch, `testgen`) |
| Bug-detection precision/recall/F1 | HumanEvalPack / labelled set | done (harness: `bugdetect`) |
| Code-quality metrics | Ruff, Radon | done (harness: `refactor`) |
| Vulnerability detection | Labelled vulnerable snippets + Bandit/Semgrep | wip (`vulndetect`, `securecodegen` with Bandit; Semgrep todo) |
| Compilation/execution success | Harness | done (status: passed/failed/timeout/crashed) |
| Hallucination/error rate | Invalid APIs, unparseable output | todo |
| Inference latency, TTFT, tokens/s | Metrics logger | done (harness) |
| GPU/CPU memory | nvidia-smi / psutil | wip (training peak GPU memory; inference todo) |
| Input/output tokens | Tokenizer counts | done (server usage counts) |
| Cost per task | GPU-hour and CPU-hour pricing model | todo |
| Energy | Intel RAPL on laptop; nvidia-smi power on T4 | done (both) |

| Ablation | Status |
|---|---|
| Base vs fine-tuned SLM | done ([v1](../experiments/results/finetune_qwen25_qlora_v1/README.md), [v2](../experiments/results/finetune_v2/README.md); also QLoRA vs LoRA vs rsLoRA, Qwen vs Phi) |
| FP16 vs INT8/INT4 | todo |
| Standard vs optimized prompting | todo |
| Full vs reduced context | done ([context ablation](../experiments/results/context_ablation_t4/README.md)) |
| Single-agent vs multi-agent | done ([agents on demo_repo](../experiments/results/agents_demo_repo/README.md)) |

## 5. Deliverables

| Deliverable | Status |
|---|---|
| Platform flow: Repository → Code Analysis → AI Review → Test Generation → Automated Testing → Bug/Fix Suggestions → Quality Assessment → CI/CD → Deployment Assistance → Monitoring/Audit | todo |
| GitHub repository | wip (research half done) |
| Full report in markdown (README) | todo |
| Demo video, 5 min max | todo |
| Deadline 01/01/2027 — target submission 30/12/2026 | todo |
