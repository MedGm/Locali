# Evaluation harness

Benchmarks a model served behind an OpenAI-compatible endpoint (llama.cpp server on the laptop, vLLM on Kaggle). Generated code runs only inside the Docker sandbox (`security/sandbox.py`).

| Module | Role |
|---|---|
| `client.py` | Streaming chat client: text, reasoning, token usage, time-to-first-token, truncation |
| `extract.py` | Pulls code from a response (entry-point block first, `<think>` ignored) |
| `tasks/codegen.py` | HumanEval+ and MBPP+ at pinned dataset revisions, EvalPlus prompt, sandboxed checking, exclusions |
| `passk.py` | Unbiased pass@k |
| `energy.py` | CPU package energy from Intel RAPL |
| `run.py` | Resumable runner: `samples.jsonl` per problem, `summary.json` with config, environment, metrics, exclusions |

## Run

```bash
# 1. Serve the model (laptop example)
~/tools/llama.cpp/build/bin/llama-server -m ~/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
    --jinja --host 127.0.0.1 --port 8080 -t 4 -c 4096

# 2. Benchmark (re-running the same command resumes)
uv run python -m evaluation.run --benchmark humaneval_plus \
    --model-id qwen2.5-coder-1.5b --quantization Q4_K_M --runtime "llama.cpp CPU t=4" \
    --base-url http://127.0.0.1:8080/v1 \
    --out experiments/results/baselines/humaneval_plus/<model>__<quant>__<hardware>
```

Thinking models: thinking is **off** unless `--thinking` is passed. The flag is recorded in the summary.

Harness check with official solutions instead of a model: add `--reference`. Expected pass@1 is 1.000 ([validation](../experiments/results/harness_validation/README.md)).

## Energy on the laptop

The RAPL counter is root-only by default, a mitigation for the PLATYPUS power side channel. For measurement sessions only, make it readable until the next reboot:

```bash
sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj
```

Without it, `energy_j` is `null` and `environment.rapl_energy_available` is `false` in the summary. Per-task energy is recorded only with `--workers 1`, since overlapping requests cannot be attributed. The reading covers the whole CPU package, so keep other load (browser, IDE indexing) low during energy runs.

## Tests

```bash
uv run pytest evaluation security   # needs Docker; loader tests need Hugging Face Hub access
```
