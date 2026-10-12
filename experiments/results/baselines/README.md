# Baselines — laptop CPU

Run: 2026-10-12, 01:12–06:46, unattended (`experiments/scripts/laptop_baselines.sh`, log `laptop_run_20261012.log`).
Hardware: Intel Core i5-10210U (4 cores, 15 W), 15 GB RAM, no GPU. Runtime: llama.cpp `987498f`, CPU, 4 threads, one request at a time.
Models: GGUF Q4_K_M at the revisions pinned in `experiments/configs/models.yaml`. Decoding: greedy (temperature 0), max 768 new tokens, thinking off, same EvalPlus instruction prompt for both models.
Energy: Intel RAPL CPU package counter, measured around each generation call (whole package, not the process).
Scoring: harness commit recorded in each `summary.json`; samples re-scored after the sanitizer fix (see below), original scores kept in `samples.original.jsonl` and `summary.json → rescored.previous_metrics`.

## Results

| | Qwen2.5-Coder-1.5B | | Qwen3.5-2B | |
|---|---|---|---|---|
| | **HumanEval+** (163) | **MBPP+** (377) | **HumanEval+** (163) | **MBPP+** (377) |
| pass@1 | **67.5 %** | **60.5 %** | 48.5 % | 42.2 % (37.4 % before sanitizer) |
| Mean output tokens | 209 | 99 | 263 | 299 |
| Truncated at 768 tokens | 1 | 1 | 4 | 34 |
| Mean time to first token | 2.03 s | 0.74 s | 3.64 s | 1.87 s |
| Decode speed | 16.8 tok/s | 17.3 tok/s | 12.2 tok/s | 12.2 tok/s |
| Energy per task | 224 J | 102 J | 381 J | 399 J |
| **Energy per correct solution** | **332 J** | **169 J** | 787 J | 947 J |
| Wall time | 0.74 h | 0.79 h | 1.18 h | 2.86 h |

## Findings

1. **The code-specialised 1.5B model beats the newer, larger general model** by 19 points on both benchmarks, while generating faster and using 2.4–5.6× less energy per correct solution. On this hardware Qwen2.5-Coder-1.5B is the better base for fine-tuning, consistent with the W1 decision to keep it as fine-tune #1.
2. **Energy follows tokens.** For Qwen2.5-Coder, MBPP+ answers are half as long as HumanEval+ answers and cost 46 % of the energy per task. Average CPU package power during generation is ≈15.3 W, matching the processor's 15 W TDP. Fewer output tokens is the most direct energy lever (RQ4).
3. **Qwen3.5-2B loses points to format, not only to correctness.** On MBPP+ it renames functions to PEP 8 style despite the given assert (`remove_Occ` → `remove_first_last_occurrence`; 42 failures), writes long self-tests that hit the token limit (34 truncated), and averages 3× the output tokens of Qwen2.5-Coder. Instruction-following on interface details is a measurable weakness, and a target for the fine-tuning data (strict output schemas).
4. **Runs are exactly reproducible.** The Qwen2.5-Coder HumanEval+ answers of this run are identical, character for character, to a run on 2026-09-15 (163/163 completions, same statuses), as expected with greedy decoding and pinned weights. Only timing differs (TTFT 2.03 s vs 2.17 s), from background load.

## Harness change during this run: answer sanitization

Qwen3.5-2B appends its own `assert` lines after the solution. The harness executed them, so a wrong self-written assert failed an otherwise correct function, and answers truncated mid-assert lost their code (unclosed fence). EvalPlus sanitizes answers before execution; this harness now does too (`evaluation/extract.py::sanitize`: keep imports, functions, classes and assignments; drop other top-level statements; trim a truncated tail until it parses; formatting of kept code unchanged). After the change all reference solutions still pass (HumanEval+ 163/163, MBPP+ 377/377, HumanEvalFix 164/164, completion 163/163; refactoring deltas 0). Re-scoring changed one number: Qwen3.5-2B MBPP+ 37.4 % → 42.2 %; Qwen2.5-Coder was unaffected.

## Caveats

- Both models use greedy decoding for comparability. Qwen's model card recommends sampling (temperature 0.7, top-p 0.8) for Qwen3.5 in non-thinking mode, which may score differently.
- Thinking mode was off. Qwen3.5-2B with thinking on may score higher at a much higher token and energy cost (W0: 1,024 tokens without an answer on a trivial task).
- Scores are on 163 / 377 problems after two harness exclusions (`experiments/results/harness_validation/README.md`); leaderboard numbers use 164 / 378.
- The September run (`humaneval_plus/qwen2.5-coder-1.5b__q4km__laptop-cpu`) has no energy data; it is kept as the reproducibility reference.
