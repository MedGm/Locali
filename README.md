# Locali

Efficient small language models for software engineering, testing and DevOps.

> **Research question:** can small, efficiently fine-tuned and optimized language models provide useful software-engineering capabilities under low-resource constraints, while keeping strong security, quality and operational supervision?

**Status:** Week 0 — setup. See [ROADMAP.md](ROADMAP.md) and [docs/spec-checklist.md](docs/spec-checklist.md).

## Repository layout

| Path | Contents |
|---|---|
| `evaluation/` | Benchmark harness: tasks, metrics, results schema |
| `experiments/` | Configs, scripts and JSON results for every run |
| `training/` | Fine-tuning code and Kaggle notebooks |
| `backend/` | FastAPI + LangGraph agents |
| `frontend/` | React/TypeScript web app |
| `mcp_servers/` | MCP servers exposing repo, tests and static analysis |
| `security/` | Guards, sandbox policy, attack corpus |
| `demo_repo/` | Deliberately flawed target project for tests, security and demo |
| `docs/` | Spec checklist and design notes |

## Setup

```bash
uv sync
cp .env.example .env
```

The full report will replace this README by the end of the project.
