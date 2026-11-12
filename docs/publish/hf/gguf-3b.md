---
base_model: Qwen/Qwen2.5-Coder-3B-Instruct
license: other
license_name: qwen-research
license_link: LICENSE
language: [en]
tags: [code, gguf, llama.cpp, built-with-qwen, built-with-llama]
---

# Llama-Locali-Qwen2.5-Coder-3B-GGUF

The default model of [Locali](https://github.com/MedGm/Locali), a software-engineering assistant
that runs on a laptop without a GPU: Qwen2.5-Coder-3B-Instruct fine-tuned with QLoRA, merged and
quantized to Q4_K_M for llama.cpp. It was trained to repair code from a failing test, write tests
that catch bugs, review code next to static-analysis findings and refactor without changing
behaviour.

| File | Run | Size | SHA-256 |
|---|---|---|---|
| `llama-locali-qwen2.5-coder-3b-run-g-q4_k_m.gguf` | **G, the default since 12 November 2026** | 1.93 GB | `247c7c7f6754c0e561ffc684833de9365cb414d8db6a848e3ebcdd35d3ba3838` |
| `llama-locali-qwen2.5-coder-3b-run-g-q5_k_m.gguf` | G in 5 bits: more accurate, 1.75 times slower | 2.22 GB | `8fff1701f77f0bebc7c24848936cb9a64729bbe4a92408f9ed7a47c77f97fa70` |
| `llama-locali-qwen2.5-coder-3b-run-e-q4_k_m.gguf` | E, the default from 5 to 12 November 2026 | 1.93 GB | `45af6f7195bb3b5e80e11ddd7bfa8969f193ae9d1fb8285610ddd86d7be22a82` |
| `llama-locali-qwen2.5-coder-3b-q4_k_m.gguf` | D, the earlier default | 1.93 GB | `fd68e2cf3a925c1860b35e49585cac37dd51d2bf252d9eafcf0054bc16bc7b04` |

All were made with llama.cpp `987498f` from the merged model (`training/kaggle/deploy/gguf` in the project
repository), then `llama-quantize`. Run G is run E's data plus 1,441 real bugs from AtCoder contests before
February 2024 (ConDefects). Run E differs from run D only in part of the general
replay data: 2,648 of those answers are the base model's own answers to the same prompts.

## Scores

Scored on a T4 (vLLM, FP16), greedy decoding, every answer run in a sandbox, % of each task. The p
value is run E against the base, from a paired exact McNemar test on the same problems; the
general skills (below the line) are Holm-corrected together. **Bold** marks the side that is
significantly better. Without bold, the difference may be chance.

| Task | Qwen2.5-Coder-3B-Instruct | Run D | Run E | p (E vs base) |
|---|---|---|---|---|
| Repair from a failing test (HumanEvalFix) | 50.0 | 61.6 | **63.4** | 0.0009 |
| Tests: bugs caught by the tests it writes | 62.2 | 82.9 | **82.3** | 0.00002 |
| Real bugs from AtCoder 2024 (ConDefects, 382) | 14.1 | 14.9 | 14.7 | 0.90 |
| *General skills* | | | | |
| HumanEval+ | 81.0 | 72.4 | 74.8 | 0.45 |
| MBPP+ | 64.7 | 64.2 | 64.2 | 1 |
| CRUXEval-O | 42.2 | 43.4 | 43.6 | 1 |
| Completion (infilling) | 56.4 | 62.0 | **65.6** | 0.006 |
| Refactoring: behaviour kept | 89.0 | 87.7 | 87.7 | 1 |
| Explaining code (HumanEvalExplain) | 68.3 | 57.9 | 68.3 | 1 |

Repair and test generation gain significantly on the benchmarks. On real bugs outside the training
distribution the repair gain is not confirmed (the pre-registered check, run on run D: 57 vs 54 of
382, p = 0.79). Run E was chosen as the default after these results were known.

**Run G** changes that last point. Same tests, run G against run E and the base (FP16, counts):

| Task | Base | Run E | Run G |
|---|---|---|---|
| Real bugs from AtCoder 2024 (ConDefects, 382) | 54 | 56 | **106** (p = 2e-8 vs base, registered before the run) |
| QuixBugs (40) | 21 | 28 | 29 |
| HumanEvalFix (164) | 82 | 104 | 103 |
| HumanEval+ (163) | 132 | 122 | 123 |
| MBPP+ (377) | 244 | 242 | 244 |
| Explaining code (164) | 112 | 112 | 116 |

Run G's training bugs come from the same site as the 382 test bugs (older contests, no shared
task, 13-gram decontaminated): the gain is on bugs of that kind. On QuixBugs, from another source,
it equals run E.

On the laptop (i5-10210U, 4 threads, n-gram lookup), run G fixes 93 of the 164 HumanEvalFix bugs
in 4 bits (17.6 s per problem, 2.2 GB of RAM, 410 J per fixed bug) and 102 in 5 bits (30.8 s,
2.5 GB, 647 J; p = 0.02 against 4 bits). With Q4_K_M, run E fixes 95 of the 164
HumanEvalFix bugs (57.9 %; run D 100, p = 0.36), in 15.2 s per problem, with 2.2 GB of RAM and
478 J of CPU energy per fixed bug.

```
llama-server -m llama-locali-qwen2.5-coder-3b-run-g-q4_k_m.gguf -c 4096 --jinja --spec-type ngram-simple
```

## Training

QLoRA with Unsloth on one T4: rank 16 on all projections, 2 epochs, seed 3407. Data: bug repair
(mutation bugs and 3,271 realistic bugs written by Qwen3.5-9B, each kept only when a real test
catches it), test writing, code review with tool findings, execution traces and general replay
data, all 13-gram decontaminated against the evaluation sets. Run D's data is mixture v3b
([Kaggle](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3b)); run E's (v3s) is not
published, since part of it is Qwen2.5-Coder-3B output; run G's (v3r) adds the ConDefects rows to it. The 1.5B version of the same project is
[Llama-Locali-Qwen2.5-Coder-1.5B](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B).

## Licence

Built with Qwen. This model is a derivative of Qwen2.5-Coder-3B-Instruct and is distributed under
the Qwen RESEARCH LICENSE AGREEMENT (`LICENSE`, `NOTICE`): **non-commercial use only** (research or
evaluation).

Built with Llama: part of the training tests came from a Llama-generated dataset, so the
[Llama 3.1 Community License](https://www.llama.com/llama3_1/license/) naming and attribution
terms also apply.
