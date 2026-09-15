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
| C1 | SLM benchmarking: code generation, completion, bug detection, explanation, refactoring, test generation | 3 models × 6 tasks on benchmark subsets | `evaluation/`, `experiments/` | W1–2 | todo |
| C2 | Efficient fine-tuning with Unsloth, LoRA/QLoRA, other PEFT | 1 model, QLoRA + LoRA runs on Kaggle T4 | `training/` | W3–5 | todo |
| C3 | Quantization 4/8-bit | FP16 / INT8 / INT4 on T4 and laptop CPU | `experiments/` | W6–7 | todo |
| C4 | KV cache, efficient attention, batching | Prefix caching on/off, batch 1/4/16, SDPA vs eager | `experiments/` | W6–7 | todo |
| C5 | Context compression, prompt optimization, token reduction | AST slicing + compact prompts, tokens before/after | `evaluation/`, `backend/` | W6–7 | todo |
| C6 | Measure latency, throughput, memory, cost | Shared metrics logger in harness | `evaluation/` | W1–2 | wip (tokens, TTFT, decode tok/s, energy done; memory, cost todo) |
| C7 | Code quality, maintainability, complexity, vulnerabilities, standards, technical debt | Ruff, Radon, Bandit, Semgrep + LLM summary | `backend/` | W3–5 | todo |
| C8 | Static-analysis tool integration | Same tools exposed via MCP | `mcp_servers/` | W6–7 | todo |
| C9 | Generate unit, integration, API tests | Test-generation agent on `demo_repo/` | `backend/` | W8–10 | todo |
| C10 | Test coverage analysis | pytest-cov before/after | `backend/` | W8–10 | todo |
| C11 | Regression tests | Tests generated for fixed bugs, kept in suite | `backend/` | W8–10 | todo |
| C12 | Detect failing tests, propose fixes | Debug loop, max 3 attempts, human approval | `backend/` | W8–10 | todo |
| C13 | LangGraph agents: Code Analysis, Test Generation, Debugging, Documentation, Code Review, DevOps | 6 nodes, deterministic routing | `backend/` | W8–10 | todo |
| C14 | MCP access to tools, repos, docs, databases, issue trackers, test frameworks, DevOps | 3 servers: repo (read-only), test runner, static analysis | `mcp_servers/` | W6–10 | wip (repo server done) |
| C15 | Git/GitHub + CI/CD: review, tests, quality, docs, deployment assistance | 1 GitHub Action on pull requests | `.github/workflows/` | W11–12 | todo |
| C16 | LLMOps: model versions, prompts, datasets, performance, tokens, agent trajectories, eval results | MLflow runs + JSONL traces | `experiments/`, `backend/` | W1–12 | todo |
| C17 | React/TypeScript web app + FastAPI backend, visualize quality and DevOps results | 3 pages: run, results/approval, metrics | `frontend/`, `backend/` | W11–12 | todo |

## 3. LLM security

| # | Threat | Control | Attack test | Week | Status |
|---|---|---|---|---|---|
| S1 | Prompt injection, indirect injection (code, repos, issues, docs) | Untrusted content never grants permissions; delimiting; detector as extra layer | Malicious README, comments, issue text | W8–13 | todo |
| S2 | Jailbreaking | System-prompt hardening + output policy check | Jailbreak prompt set | W8–13 | todo |
| S3 | Data leakage (code, credentials, API keys) | Secret scanning + redaction before model and in outputs | Fake keys in `demo_repo/` | W3–13 | todo |
| S4 | Malicious code, unsafe commands | Command allow-list, output validation | Generated `rm -rf`, `curl \| bash` | W8–13 | todo |
| S5 | MCP/tool security, excessive permissions | Least-privilege servers, per-tool allow-list | Call to non-allowed tool | W6–13 | wip (repo server: 2 tools, path confinement tested) |
| S6 | Supply-chain, repository poisoning | Dependency pinning, no install from untrusted repo, sandbox | Poisoned `requirements.txt` | W8–13 | wip (sandbox: no network, read-only, limits tested) |
| S7 | Insecure output handling, generated-code vulnerabilities | Semgrep/Bandit on generated code before acceptance | Vulnerable patch | W8–13 | todo |
| S8 | Excessive agent autonomy | Human approval for writes, iteration limits | Agent attempts unapproved write | W8–13 | todo |

Required controls, all covered above: least privilege · sandboxed execution · tool allow-lists · input/output validation · secret filtering · human approval · complete audit logging.

## 4. Experimental evaluation

Pipeline: SLM → Fine-tuning → Quantization → Token optimization → Agentic workflow → SE tasks.

| Metric | Source | Status |
|---|---|---|
| Code correctness, pass@k | EvalPlus (HumanEval+/MBPP+) | todo |
| Unit-test pass rate | pytest runs in sandbox | todo |
| Test coverage | pytest-cov | todo |
| Bug-detection precision/recall/F1 | HumanEvalPack / labelled set | todo |
| Code-quality metrics | Ruff, Radon | todo |
| Vulnerability detection | Labelled vulnerable snippets + Bandit/Semgrep | todo |
| Compilation/execution success | Harness | todo |
| Hallucination/error rate | Invalid APIs, unparseable output | todo |
| Inference latency, TTFT, tokens/s | Metrics logger | todo |
| GPU/CPU memory | nvidia-smi / psutil | todo |
| Input/output tokens | Tokenizer counts | todo |
| Cost per task | GPU-hour and CPU-hour pricing model | todo |
| Energy | Intel RAPL on laptop; nvidia-smi power on T4 | todo |

| Ablation | Status |
|---|---|
| Base vs fine-tuned SLM | todo |
| FP16 vs INT8/INT4 | todo |
| Standard vs optimized prompting | todo |
| Full vs reduced context | todo |
| Single-agent vs multi-agent | todo |

## 5. Deliverables

| Deliverable | Status |
|---|---|
| Platform flow: Repository → Code Analysis → AI Review → Test Generation → Automated Testing → Bug/Fix Suggestions → Quality Assessment → CI/CD → Deployment Assistance → Monitoring/Audit | todo |
| GitHub repository | wip |
| Full report in markdown (README) | todo |
| Demo video, 5 min max | todo |
| Deadline 01/01/2027 — target submission 30/12/2026 | todo |
