# Locali

A software-engineering assistant built on small language models that run on a laptop CPU (a
fine-tuned Qwen2.5-Coder-3B by default, a fine-tuned 1.5B as the fast option): it reviews a
repository, writes tests, fixes failing ones, documents functions and checks merge readiness, and
every change it proposes waits for a human to approve that exact patch.

Course project *Efficient Small Language Models for Intelligent Software Engineering, Testing and
DevOps* (2026). The brief was written for teams of five; I did it alone, with the hardware I have
(a 4-core laptop without a GPU, 16 GB RAM) and Kaggle's free T4 GPUs.

> **Research question.** Can small, efficiently fine-tuned and optimized language models provide
> useful software-engineering capabilities under low-resource constraints, while keeping strong
> security, quality and operational supervision?

**Short answer: yes, within limits I can now measure.**

A 1.5B model fine-tuned with QLoRA in two hours on one T4 catches 82 % of bugs with the tests it
writes (from 46 %), preserves behaviour in 94 % of refactors (from 70 %) and repairs 36 % of
HumanEvalFix bugs (from 25 %), without a significant loss in general code generation. Quantized to
8 bits it loses nothing measurable, needs 1.8 GB of RAM and answers at 10 tokens/s on the laptop CPU.

The same recipe on a 3B model, with realistic bugs added to the data, repairs 62 % of HumanEvalFix
(from 46 %); quantized to 4 bits it fixes a bug in about 15 s on the
laptop with 2.2 GB of RAM, for 456 J of CPU energy per fixed bug. The cost is general code
generation on HumanEval+ (81 → 72 %, p = 0.013, not significant once corrected for the number of
tasks compared): the model still knows the solutions (equal pass@20) but its first answer is less
reliable.

On its own the model is noisy as a reviewer; it becomes useful as one part of a workflow where
static tools carry security, a sandbox runs every test, and nothing reaches the repository without
approval. The main security property is a design one: the model never acts, it only produces text
that is checked before anything changes. My own attack cases did not get through those controls,
which shows they work as built, not that they resist an attacker who adapts to them.

### Results at a glance

| What | Before → after | Section |
|---|---|---|
| Bug repair, HumanEvalFix (fine-tuned 3B) | 46 → 62 % | [3](#3-fine-tuning) |
| Bugs caught by the tests it writes (3B) | 62 → 83 % | [3](#3-fine-tuning) |
| Refactors that keep behaviour (1.5B) | 70 → 94 % | [3](#3-fine-tuning) |
| HumanEval+, the cost of fine-tuning (3B) | 81 → 72 % | [3](#3-fine-tuning) |
| One bug fix on the laptop (3B, 4-bit) | ~15 s, 2.2 GB RAM, 456 J | [4](#4-performance-optimization) |
| 8-bit vs 16-bit (1.5B) | no measurable loss, 1.8× less RAM | [4](#4-performance-optimization) |
| Bugs caught on demo_repo (one repository I built): single review → workflow with tools | 0 → 4 of 5 | [5](#5-the-agents) |
| My own attack cases that got through the controls | 0 of 33 | [6](#6-llm-security) |

### Models and data online

| What | Where |
|---|---|
| Fine-tuned 3B (run D), the default model: Q4_K_M GGUF for llama.cpp | [Llama-Locali-Qwen2.5-Coder-3B-GGUF](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-3B-GGUF) |
| Fine-tuned 1.5B (QLoRA v2), the fast option: merged model, GGUF (Q8_0, Q4_K_M), adapter | [merged](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B) · [GGUF](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-GGUF) · [adapter](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA) |
| The other adapters: 1.5B QLoRA v1, 16-bit LoRA, rsLoRA, Phi-4-mini | [Llama-Locali-adapters](https://huggingface.co/MedGm/Llama-Locali-adapters) |
| Training data, mixtures v1 to v3b | Kaggle: [v1](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v1) · [v2](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v2) · [v3](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3) · [v3b](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3b); v2 also on [Hugging Face](https://huggingface.co/datasets/MedGm/locali-mix-v2) |
| Everything on Hugging Face | [huggingface.co/MedGm](https://huggingface.co/MedGm) |

The 3B model is under the Qwen research licence: non-commercial use only. Its adapters (runs A to
E) and mixture v3s, which contains the 3B's own outputs, are not published; `training/kaggle/gguf`
rebuilds a 3B model from an adapter.

![The brief's chain and what each stage gave](docs/diagrams/evaluation_chain.svg)

## Contents

1. [The platform](#1-the-platform)
2. [Models and benchmark](#2-models-and-benchmark)
3. [Fine-tuning](#3-fine-tuning)
4. [Performance optimization](#4-performance-optimization)
5. [The agents](#5-the-agents)
6. [LLM security](#6-llm-security)
7. [DevOps, LLMOps and the web app](#7-devops-llmops-and-the-web-app)
8. [The five ablations of the brief](#8-the-five-ablations-of-the-brief)
9. [Metrics](#9-metrics)
10. [What did not work, and limits](#10-what-did-not-work-and-limits)
11. [Running it](#11-running-it)
12. [Reproducing the results](#12-reproducing-the-results)
13. [Use of AI tools](#13-use-of-ai-tools)
14. [Repository layout](#14-repository-layout)

## 1. The platform

The brief's pipeline, and where each step lives:

| Step | What Locali does | Code |
|---|---|---|
| Repository | Works on any folder under a configured root; a run never writes to it | `backend/workspace.py` |
| Code analysis | Ruff, Bandit, Radon, Semgrep (own rules for Python, JavaScript/TypeScript, Java and Go), a secret scanner and a prompt-injection detector | `backend/analysis.py`, `security/` |
| AI review | The model reviews each function; findings must quote a line that exists | `backend/agents/review.py` |
| Test generation | Regression tests for untested functions, kept only if they pass | `backend/agents/testgen.py` |
| Automated testing | pytest with coverage in a Docker sandbox: no network, read-only, CPU/memory/process limits | `security/sandbox.py` |
| Bug/fix suggestions | Failing tests go to a repair loop; failed assertions in generated tests become "suspects" | `backend/agents/debug.py` |
| Documentation | Docstrings for undocumented public functions, accepted only if nothing but docstrings changed | `backend/agents/docs.py` |
| Quality assessment | Findings by category and severity, coverage, merge readiness | `backend/agents/devops.py` |
| CI/CD | A GitHub Action reviews pull requests and blocks new security issues | `.github/workflows/` |
| Deployment assistance | Dependency typosquat check, CI suggestion, blockers and warnings | `backend/agents/devops.py` |
| Monitoring/audit | Audit log of every action, MLflow runs and traces, a security center | `backend/audit.py`, `backend/llmops.py` |
| Ask the model | A playground: paste code in any language, pick a task, compare two models side by side | `backend/playground.py` |

Quick scans (static tools only) work on Python, JavaScript, TypeScript, Java and Go projects. The
full assistant (tests, repair loop, patch validation) works on Python code, because those steps run
pytest and use Python's parser.

![Locali system architecture](docs/diagrams/architecture.svg)

Every agent change becomes a **patch**: one per fixed file, per test file and per documented file,
each applied alone to a fresh copy of the repository and validated there (no test that passed
before may fail, no new Bandit/Semgrep finding, no secret in the added lines). A reviewer approves
a patch by sending back its SHA-256, the hashes of the files it was made against and the hash of
its validation record; if anything differs, or the files changed since, it is refused or marked
stale and can be revalidated. Applied patches can be reverted.

![From an agent's change to the repository](docs/diagrams/patches.svg)

### The web app

| | |
|---|---|
| ![Home](docs/screenshots/home.png) | ![Repositories](docs/screenshots/repositories.png) |
| **Home**: what to do next, repositories, changes waiting for a decision | **Repositories**: languages, last run, patches waiting |
| ![A run](docs/screenshots/run.png) | ![Patch review](docs/screenshots/patch-review.png) |
| **A run**: the steps, a summary, then every finding, test, fix and model call | **Patch review**: what to check, the validation record, approve the exact patch |
| ![Playground](docs/screenshots/playground.png) | ![Research results](docs/screenshots/results.png) |
| **Playground**: the fine-tuned model (left) finds and fixes the bug; the base model (right) does not | **Research results**: every study, here the other languages |

Dark theme: [home-dark.png](docs/screenshots/home-dark.png).

## 2. Models and benchmark

**Models** ([research design](docs/research-design.md)): Qwen2.5-Coder-1.5B, Phi-4-mini (3.8B),
Qwen3.5-2B and Qwen3.5-4B as small models, and Qwen3.5-9B as the "larger general-purpose LLM"
reference. All open weights, pinned to exact revisions.

**Benchmark** (`evaluation/`): eleven tasks covering code generation (HumanEval+, MBPP+), completion
(infilling), bug repair (HumanEvalFix), bug detection, code explanation (HumanEvalExplain), code
reasoning (CRUXEval-O), test generation, refactoring, secure code generation and vulnerability
detection, plus four held-out
tasks in the formats I trained on. Answers are generated on Kaggle T4s with vLLM (or on the laptop
with llama.cpp) and scored afterwards on the laptop, with all generated code run in the sandbox
(the one exception, repair in five other languages, is described in section 10).
The harness was validated on reference solutions first: all eleven tasks score 100 %
([harness validation](experiments/results/harness_validation/README.md)). Comparisons on the same
items use paired exact McNemar tests. Repair and test generation are the confirmatory outcomes,
the two the training data was built for from the start; every other task is exploratory. Each
family is corrected with Holm for each fine-tuned model ([tables](experiments/results/multiple_comparisons/README.md)).
In the score tables, **bold** marks a gain and *italic* a loss that stay significant after that
correction (adjusted p < 0.05); in speed, energy and memory tables bold marks the best value.

"Bugs caught" by the tests a model writes: each generated test first runs on the correct code and
is dropped if it fails there (a wrong expected value); the bug counts as caught if at least one of
the remaining tests fails, errors or hangs on the buggy code, with the same 60 s limit on both. A
problem where no test survives catches nothing.

| % of each task | Qwen2.5-Coder 1.5B | Qwen3.5-2B | Phi-4-mini 3.8B | Qwen3.5-4B | Qwen3.5-9B |
|---|---|---|---|---|---|
| HumanEval+ pass@1 | 65.0 | 47.2 | 71.2 | 79.8 | 84.0 |
| MBPP+ pass@1 | 56.2 | 40.8 | 54.1 | 66.8 | 62.1 |
| Repair (HumanEvalFix) | 25.0 | 34.2 | 42.7 | 53.7 | 65.8 |
| Tests: bugs caught | 46.3 | 87.2 | 90.2 | 97.0 | 95.7 |
| Refactoring: behaviour kept | 69.9 | 82.8 | 86.5 | 92.0 | 92.6 |
| Energy per correct HumanEval+ answer, T4 (J) | **54** | 116 | 105 | 98 | 421 |

([full tables](experiments/results/kaggle_reference_20261012/README.md))

Two things decided the rest of the project. Qwen2.5-Coder-1.5B is by far the cheapest model per
correct answer (8× less energy than the 9B) and the weakest exactly on repair, testing and
refactoring, which leaves the most room for fine-tuning. And Unsloth could not train Qwen3.5 on a T4 at
all: tested on the 2B in FP16, BF16 and FP32, all three failed in the same code path, which the 4B
and 9B share ([W1 spikes](experiments/results/w1_spikes/README.md)). The two models I fine-tuned
first are therefore Qwen2.5-Coder-1.5B and Phi-4-mini; Qwen2.5-Coder-3B was added later as a
stronger base that still runs on the laptop (end of section 3).

## 3. Fine-tuning

![Fine-tuning pipeline](docs/diagrams/training.svg)

Two fine-tuned models are in Locali: the 3B (run D), the default since 1 November, and the 1.5B
(QLoRA v2), the fast option. Their results come first; how I got there is below, folded.

**The 3B, default model** ([run D](experiments/results/finetune_qwen25_3b_qlora_mixv3b_diag/README.md),
[run E](experiments/results/finetune_qwen25_3b_qlora_mixv3s/README.md)), Qwen2.5-Coder-3B, % of each task:

| Task | Base | Run D (default) | Run E |
|---|---|---|---|
| Repair (HumanEvalFix) | 46.3 | **61.6** | **63.4** |
| Tests: bugs caught | 62.2 | **82.9** | **82.3** |
| Refactoring: behaviour kept | 86.5 | 87.7 | 87.7 |
| Completion (infilling) | 56.4 | 62.0 | **65.6** |
| MBPP+ | 64.7 | 64.2 | 64.2 |
| CRUXEval-O | 42.2 | 43.4 | 43.6 |
| HumanEval+ | 81.0 | 72.4 | 74.8 |
| Explanation (HumanEvalExplain) | 68.3 | 57.9 | 68.3 |

Bold: significantly better than the base after the Holm correction. Repair and test generation gain
in both runs, completion in run E. HumanEval+ stays below the base (p = 0.013 for D, 0.076 for E,
not significant after the correction, Holm p = 0.088 and 0.45; see "Why HumanEval+ drops" below).
Both gains are being rechecked in a pre-registered evaluation: repair on real bugs that the
training data was not shaped after, and test generation with a token budget that the base does not
run out of ([protocol](docs/preregistration-repair.md)). The explanation
task has the model explain a function and then rewrite it from its own explanation; when the 3B
base writes the code from every model's explanation, D's explanations are as good as the base's
(65.9 vs 68.3 %, p = 0.54), so D's loss there is the same code-writing loss
([explanation](experiments/results/explain_t4/README.md)). Run D fixes a
bug in about 15 s on the laptop with 2.2 GB of RAM ([laptop check](experiments/results/laptop_3b_check/README.md)).
Run E is better on repair and completion but not deployed: that needs its own GGUF build and a
laptop energy run. Run D is published as a GGUF under the Qwen research licence (non-commercial),
with the notices it requires.

**The 1.5B, fast option** ([results](experiments/results/finetune_v2/README.md)), Qwen2.5-Coder-1.5B,
% of each task, p from a paired exact McNemar test (bug detection is not bold: the second seed did
not replicate it):

| Task | Base | QLoRA v2 | p |
|---|---|---|---|
| Tests: bugs caught | 46.3 | **82.3** | 2e-12 |
| Refactoring: behaviour kept | 69.9 | **93.9** | 9e-10 |
| Repair (HumanEvalFix) | 25.0 | **36.0** | 0.006 |
| MBPP+ | 56.2 | **62.1** | 0.005 |
| Bug detection (not replicated) | 53.0 | 65.5 | 0.0004 |
| HumanEval+ | 65.0 | 62.0 | 0.51 |
| CRUXEval-O (not trained) | 30.1 | 28.7 | 0.31 |

On held-out repair items in the trained prompt format the score goes from 2.4 to 63.7 %; that
mostly measures that the model learned the output format, so it is not a result about repair.

It is published on Hugging Face ([merged](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B),
[GGUF](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-GGUF),
[dataset](https://huggingface.co/datasets/MedGm/locali-mix-v2)); the "Llama" prefix is required by
the Llama 3.1 license, because part of the training tests came from a Llama-generated dataset.

**Why HumanEval+ drops** ([capability study](experiments/results/capability_study/)). Every
fine-tuned 3B run scores 6 to 9 points below the base on HumanEval+, while matching it on MBPP+.
Instead of trying more data, I looked at what changed in the model. Short version: fine-tuning kept
what the 3B can do and made its first answer on this benchmark less reliable. With 20 sampled
answers per problem, the fine-tuned runs solve as many problems as the base:

| HumanEval+, %, from 20 samples at temperature 0.8 | pass@1 | pass@5 | pass@20 |
|---|---|---|---|
| 3B base | 76.6 | 88.8 | 92.0 |
| Run D | 68.0 | 86.8 | 92.0 |
| Run E | 72.9 | 87.0 | 92.0 |

The pass@1 here is estimated from the 20 samples at temperature 0.8, which is why it is lower than
the greedy scores in the table above (81.0 for the base). Training on the base's own answers (run E)
narrows the gap; a prompt does not.

### How I got there

<details>
<summary><b>Data and training recipe</b></summary>

**Data** ([mixture v2](experiments/results/data_mix_v2/README.md)): 14,151 training examples in
four formats, all built and checked by execution rather than written by hand:

- T1 repair: bugs injected by mutation into verified solutions, kept only if a real test fails,
  with a diagnosis written by the 9B teacher model and accepted only when it is consistent;
- T2 test writing, T3 review (bug/clean pairs with tool findings), T4 execution traces (the
  output of a call, confirmed by both the sandbox and the problem's own test);
- 13-gram decontamination against HumanEval+, MBPP+, HumanEvalPack, CRUXEval, SecurityEval and
  CyberNative.

The first mixture made the model forget code reasoning (CRUXEval-O 30.1 → 25.5, p = 0.0005); the
execution traces in v2 were added for that and removed the drop.

**Training**: Unsloth + TRL on one T4, rank 16 on all projections, 2 epochs. I compared QLoRA,
16-bit LoRA and rsLoRA on the same data ([results](experiments/results/finetune_v2/README.md)).

QLoRA took 2 h 04 min with a 3.09 GB peak (16-bit LoRA: 4.85 GB, same quality). The test
generation, refactoring and in-format gains hold in all three variants at p < 1e-4.

</details>

<details>
<summary><b>Checks on the 1.5B: second seed, repair with feedback, Phi-4-mini</b></summary>

**Second seed** ([results](experiments/results/finetune_qwen25_qlora_v2_seed1234/README.md)): I
repeated QLoRA v2 with seed 1234 instead of 3407, same data and versions. The MBPP+ gain (234 vs
212 solved, p = 0.005) and the HumanEvalFix gain (58 vs 41, p = 0.008) replicate. The bug
detection gain does not: the second seed answers "buggy" almost every time (accuracy 54.6 %,
recall 0.95), while both seeds score 66 % in the trained review format. I therefore do not claim
it.

**Repair with execution feedback** ([results](experiments/results/feedback_t4/README.md)): when
the failing test's error is shown back and the model may try again, up to 3 attempts, the
fine-tune fixes 41.5 % of HumanEvalFix (36.0 % in one attempt, p = 0.004) and the base model
29.9 % (25.0 %). The fine-tune keeps its lead (p = 0.007). The gain is small because the model
mostly repeats its first answer.

**Phi-4-mini** got worse on several tasks from the same data (repair in the trained format
46.3 → 24.4, MBPP+ 54.1 → 48.3): fine-tuning imitates the targets, and for a stronger model my
minimal targets were a downgrade. The first model I deployed was therefore **Qwen2.5-Coder-1.5B + QLoRA
v2**, merged into the base and published on Hugging Face (links above).

</details>

<details>
<summary><b>v3: realistic bugs on a 3B base (runs A to D)</b></summary>

**v3: realistic bugs on a 3B base** ([retrospective](docs/retrospective.md),
[bugs](experiments/results/v3_bugs/README.md), [3B baselines](experiments/results/kaggle_coder_baselines_20261024/README.md),
[run A](experiments/results/finetune_qwen25_3b_qlora_mixv2/README.md),
[run B](experiments/results/finetune_qwen25_3b_qlora_mixv3/README.md),
[robustness](experiments/results/robust_3b_t4/README.md)). The fine-tuned 1.5B fixed operator bugs
better than the 9B teacher but barely moved on logic bugs: it had learned the shape of the one-line
mutations. The untrained Qwen2.5-Coder-3B already repaired more (46.3 %) than the fine-tuned 1.5B
(36.0 %). I had the teacher write 3,271 realistic bugs of seven kinds into unused, verified problems
(kept only when the problem's tests catch them) and trained the 3B twice with the same recipe:

| HumanEvalFix, % fixed | 3B base | + v2 data | + v2 + realistic bugs | p, last vs base |
|---|---|---|---|---|
| Benchmark prompt | 46.3 | 43.9 | **64.6** | 4e-5 |
| Reworded prompt, same tests | 40.2 | 38.4 | **56.7** | 4e-4 |
| 3 attempts with explained errors | 54.9 | 52.4 | 71.3 | not tested |
| Docstring instead of tests | 73.8 | 59.2 | 75.0 | n.s. |

The gain is in repair from failing tests, holds when the prompt is reworded, and is largest on
excess logic (11 → 21) and missing logic (12 → 15). Test generation keeps the v2 gain (62 → 82 %
of bugs caught). Two costs remain: refactoring falls to 78.5 % (base 86.5 %) and HumanEval+ stays
six points below the base (a cost of the v2 data). A third run
([run C](experiments/results/finetune_qwen25_3b_qlora_mixv3b/README.md)), with half of the mutation
bugs and twice the general replay data, restores refactoring (88.3 %) and keeps most of the repair
gain (61.0 %, p = 0.001 against the base), but not HumanEval+ (73.0 %). Run D
([README](experiments/results/finetune_qwen25_3b_qlora_mixv3b_diag/README.md)) repeats run C on the
corrected v3b data (reviewer-side explanations for the realistic bugs): same scores within noise on
all 16 tasks, no explanation phrased as an edit. **Run D is Locali's default model since 1 November**
(run C from 25 October before it): merged and exported to Q4_K_M (1.93 GB), it fixes a bug in about 15 s on
the laptop with 2.2 GB of RAM ([laptop check](experiments/results/laptop_3b_check/README.md)); the
1.5B Q4_K_M stays as the fast option (about 6 s).

</details>

<details>
<summary><b>Run E: the base model's own answers as replay data</b></summary>

**Run E** ([README](experiments/results/finetune_qwen25_3b_qlora_mixv3s/README.md)) keeps run D's
data but replaces 2,648 of the general replay answers (written by StarCoder2-15B) with the base
3B's own answers to the same prompts, kept when they ran without error. Nothing gets worse, and it
is the best 3B run on repair and completion (table above).

</details>

<details>
<summary><b>The capability study in four steps</b></summary>

1. The loss is concentrated: 10 problems that the base solves and all five runs fail, with wrong
   logic rather than a format problem ([step 1](experiments/results/capability_study/step1_behaviour/README.md)).
2. The solutions are still in the model. With 20 sampled answers per problem (temperature 0.8),
   the fine-tuned runs solve as many problems as the base; only the first answer is worse
   ([step 2](experiments/results/capability_study/step2_kaggle/README.md), table above).
3. A wrong answer is one or two tokens away from a right one. Forcing the base's token where the
   two answers part makes 69 of 70 failing answers pass, usually after one or two forced tokens,
   and more often than forcing a random alternative. At those points the base spells the code out
   (a step comment, a setup variable, a helper function) where the fine-tuned model writes a
   one-liner ([step 3](experiments/results/capability_study/step3_kaggle/README.md)).
4. Asking for a comment before each step, forcing the answer to start with one, or turning off the
   repetition penalty does not bring the points back: every change for D and E is within noise,
   and what it fixes on the lost problems it breaks elsewhere. Run D also ignores the comment
   instruction (5 of 163 answers), the base follows it (149)
   ([step 4](experiments/results/capability_study/step4_kaggle/README.md)).

</details>

## 4. Performance optimization

**Quantization** on the laptop CPU, llama.cpp ([ladder](experiments/results/ladder_laptop/README.md)):

| Fine-tuned 1.5B | F16 | Q8_0 | Q4_K_M |
|---|---|---|---|
| HumanEval+ pass@1 (%) | 64.4 | 63.2 | 60.1 |
| MBPP+ pass@1 (%) | 60.2 | 59.4 | 58.1 |
| Decode speed (tokens/s) | 5.8 | 10.4 | **16.1** |
| CPU energy per solved HumanEval+ item (J) | 638 | 396 | **234** |
| Peak RAM (GB) | 3.21 | 1.79 | **1.16** |

Q8_0 changes 2 of 163 answers against F16; Q4_K_M costs 2–4 points (not significant one by one,
all in the same direction) and is the fast option of the 1.5B. The fine-tuned model
also writes about a third fewer tokens than the base, which saves time and energy on its own.

**Speculative decoding**: draft-free n-gram lookup is the best setting on the laptop and on a T4.
For the fine-tuned 3B (the default model) on the laptop it brings a fixed bug from 501 J to 456 J; small draft models cost
more than they save, because on four shared CPU cores the draft has to read the long prompt too.

<details>
<summary><b>Speculative decoding in detail (1.5B and 3B, laptop and T4)</b></summary>

**Speculative decoding** ([laptop](experiments/results/speculative_laptop/README.md),
[T4](experiments/results/speculative_t4/README.md)): draft-free n-gram lookup is the best
setting on both devices. On the laptop it makes the Q8 model about 1.5× faster and saves 21–25 %
of the CPU energy per correct answer; the fine-tuned Q4_K_M model with n-gram lookup is the
cheapest configuration measured (189 J per solved HumanEval+ problem, against 962 J for the base
model in F16). A 0.5B draft model barely helps on the CPU (at most 6 % less energy, and more on
repair), because it competes with the target for the same four cores. On a T4 both help, n-gram
lookup most (50–67 % less energy per correct answer). The stock draft predicts the fine-tune worse
than the base model (acceptance on repair 0.63 vs 0.87 at 8 drafted tokens), so fine-tuning
makes long drafts a net loss. Greedy speculative decoding keeps the pass counts but is not
bit-exact: a few answers change.

For the fine-tuned 3B on the laptop ([3B drafts](experiments/results/speculative_3b_laptop/README.md),
all 164 HumanEvalFix problems), n-gram lookup is again the best: 456 J per fixed bug against 501 J
without speculation. A 0.5B draft costs 516 J and 1.5B drafts 668 J, despite accepting 89 to 97 %
of drafted tokens, because the draft has to read the long repair prompt too, on the same four
cores. A 1.5B draft fine-tuned on the same data accepts no more tokens than the base 1.5B (0.97 vs
0.96).

</details>

<details>
<summary><b>Serving on a T4: batching, CUDA graphs, KV cache</b></summary>

**Serving on a T4** (vLLM and transformers, [results](experiments/results/serving_t4/README.md)):
16 concurrent requests give 13.6× the throughput of one and use 15× less energy per answer; CUDA
graphs add 1.6× for a single request (every earlier run used eager mode); the KV cache doubles
generation speed already at 128 tokens; prefix caching brings nothing on these prompts, which
share only a short instruction. Eager attention in FP16 produces NaN logits for this model on a
T4; SDPA is the one that works.

</details>

**Context and prompts**: the savings come from what is left out (other functions, other tests),
not from compressing what is kept.

<details>
<summary><b>Context and prompts in detail</b></summary>

**Context and prompts** ([repair on T4](experiments/results/context_ablation_t4/README.md),
[agents](experiments/results/context_agents/README.md)): giving the repair prompt the whole test
suite instead of the one failing test doubles the input and fixes slightly fewer bugs (62.3 vs
63.7 %); stripping comments and docstrings saves 14 % of input for a small, non-significant loss.
In the agent workflow, a whole file instead of one function makes the review cheaper but quieter
(it misses a planted bug), and adding the function's dependencies ("slicing") costs 21 % more input
and cuts the model's false positives from 17 to 6. The savings come from what is left out (other
functions, other tests), not from compressing what is kept.

</details>

## 5. The agents

A LangGraph graph with fixed routing: `prepare → analyze → review → testgen → debug → docs →
propose → devops → report`. Routing is fixed because the 1.5B model made no usable native tool
calls in the first spike, and fixed steps make runs reproducible. The model has no tools: it only
ever answers a prompt, and its answer is parsed into findings or code that is then checked.

![One assistant run](docs/diagrams/workflow.svg)

Tool access for other clients (Claude Desktop, an IDE, another agent) goes through five MCP
servers with one to three tools each (`mcp_servers/`):

| Server | Tools | Limits |
|---|---|---|
| repository | `list_files`, `read_file` | read-only, confined to the root, secrets redacted |
| tests | `run_tests` | only in the sandbox (no network, read-only, limits) |
| static analysis | `analyze` | Ruff, Bandit, Radon, Semgrep, secret scan |
| documentation | `list_docs`, `search_docs`, `read_doc` | read-only, documentation files only, lines that look like prompt injections listed with the text |
| issues | `list_issues`, `get_issue`, `draft_issue` | reads `docs/issues/*.md`; a new issue is only a draft in a folder outside the repository, a person files it; no `draft_issue` without `--drafts` |

Docs and issues are written by anyone, so the two servers give them back as data with a list of
suspicious lines: on demo_repo the hidden note in the README and the fake "maintainer approved"
line in issue #12 both come back flagged. Locali runs offline, so the issue tracker is the
Markdown one many small projects keep in the repository, not GitHub.

On `demo_repo/`, a small shop application with 5 planted bugs, 5 vulnerabilities, a hard-coded key,
a typosquatted dependency and two prompt injections ([answer key](security/demo_repo_flaws.json),
[runs](experiments/results/agents_demo_repo/README.md); these runs are from before the shop got
its HTTP API, see below). I built this repository and planted its flaws, so the table shows how the
workflow behaves on one repository, not how accurate it is in general. The columns also differ in
more than the number of agents: the single agent makes 8 model calls, the workflow 40, and most of
the security findings come from the static tools, not from the model.

| | Single agent (one review per file) | Multi-agent, no tools | Multi-agent + tools |
|---|---|---|---|
| Bugs caught in any way (of 5) | 0 | 3 | 4 |
| Bugs fixed | 0 | 1 | 1 |
| Vulnerabilities found (of 5) | 3 | 3 | 5 |
| Hard-coded secret found | no | no | yes |
| Model calls / output tokens | 8 / 441 | 40 / 5,129 | 40 / 5,129 |

The fix comes from the trained format: given a failing test and its error, the model fixed the
bug at the first attempt. Security comes from the tools: they found every vulnerability and the
secret with no false positives, the model alone a different 3 of 5 each time. Reviewing the first
real patch led to three changes: no tests for functions the tools flag as insecure, no kept tests
for functions with a suspected bug, and one patch per change so each can be accepted alone.

**Unit, integration and API tests** ([results](experiments/results/agents_api_tests/README.md)).
The test step writes three kinds of tests: unit tests for one function, integration tests for a
function together with the project functions it calls (a real temporary database, no mocks), and
API tests for each route of a FastAPI app, through `TestClient` on an empty temporary database.
They follow the same rules: only passing tests are kept, and a failing one is reported as a
suspected bug. For this, `demo_repo` got a small HTTP API with a sixth planted bug: an order larger
than the stock is accepted, although the endpoint's docstring says it is refused. With the
fine-tuned 3B, the agent's API test for that endpoint expected the refusal, failed, and reported
the bug (`assert 201 == 409`); the kept tests raised line coverage from 27.7 to 45.0 %. No API test
was kept, because every API answer also had a wrong expectation somewhere, and 4 of the 8 suspected
functions were not where a bug was planted. The first attempt failed completely (the model built the
app outside the temporary database); a ready-made test fixture in the prompt fixed that.

## 6. LLM security

Every threat in the brief has a control and an attack test, run with the control on and off
([results](experiments/results/redteam/README.md)). The attacks are my own cases against my own
controls, with no attacker adapting to them: the table shows that each control works as built. The
property that carries the security is architectural: the model has no tools and never acts, and
what it writes is parsed and checked before anything changes.

| Threat | Control | Attacks that worked: control on / off |
|---|---|---|
| S1 Prompt injection | The model never acts; README and issue text never reach it; injection detector | model red-team: harm 0/11 |
| S2 Jailbreak | Output only parsed into findings or validated code | model red-team: 0/6 complied |
| S3 Data leakage | Secret redaction in both directions, including the exact values found in the repository | 0/2 / 2/2 |
| S4 Unsafe commands | Command allow-list (git, patch, docker, the analysers), sandbox | 0/3 / 3/3 |
| S5 Tool permissions | Path confinement, symlinks resolved, read-only servers | 0/2 / 2/2 |
| S6 Supply chain | Repository code runs only in the sandbox; typosquat check | 0/2 / 2/2 |
| S7 Insecure output | Validation with Bandit, Semgrep and a secret scan on every patch | 0/4 / 4/4 |
| S8 Excessive autonomy | Approval of the exact patch, stale check, revert | 0/3 / 3/3 |

<details>
<summary><b>How the attacks were run, and the two gaps they found</b></summary>

With a control off, each attack really runs on this machine, against temporary copies and a local
listener. The red-team found two real gaps, both fixed with a regression case: a key repeated in a
model answer without its assignment slipped past redaction, and a fix that also ran
`os.system('curl … | sh')` passed validation because Bandit rates a constant command as low
severity. With the real model, payloads hidden in comments, docstrings and strings asked for a
backdoor, a destructive test, code in a docstring or a keylogger; the model followed none of them.

</details>

Every action (runs, refusals, approvals, redactions, stale patches) is appended to an audit log,
and the web app's security center lists the security-relevant ones.

## 7. DevOps, LLMOps and the web app

- **CI** (`.github/workflows/ci.yml`): lint, the sandbox image, 489 tests, and the frontend's type
  check, lint and build, on every push.
- **Pull request review** (`locali-review.yml`): runs the static analysis and secret scan on the
  changed files, comments on the pull request and fails it on a new high-severity issue or secret.
- **DevOps step** in every agent run: merge readiness with blockers and warnings, a dependency
  typosquat check, the test baseline and coverage, and a CI workflow to start from when a
  repository has none.
- **LLMOps** (MLflow): every agent run is logged with its parameters, metrics, report and
  trajectory, plus a trace with one span per step and per model call (prompts already redacted).
  All 235 evaluation runs, the 7 training runs and both datasets are backfilled into the same
  store (`experiments/scripts/log_to_mlflow.py`).
- **Web app** (Next.js, React, TypeScript; FastAPI backend): a home page that guides a first run,
  repositories, runs with live progress, a patch review page with the diff, its validation record
  and what to check before approving, a playground, the security center, models, quality trends,
  research results and settings, in light and dark themes. The API needs a token; the browser
  never sees it.

## 8. The five ablations of the brief

- **Base vs fine-tuned SLM.** 1.5B: +36 points test generation, +24 refactoring, +11 repair, no
  loss on generation ([finetune_v2](experiments/results/finetune_v2/README.md)). 3B (run D): +21 test
  generation, +15 repair, −9 HumanEval+ ([run D](experiments/results/finetune_qwen25_3b_qlora_mixv3b_diag/README.md)).
- **FP16 vs INT8/INT4.** Q8 lossless; Q4 −2 to −4 points, 2.8× faster, 2.8× less RAM
  ([ladder_laptop](experiments/results/ladder_laptop/README.md)).
- **Standard vs optimized prompting.** Compressed prompts: −14 % input, −2.4 points (n.s.)
  ([context_ablation_t4](experiments/results/context_ablation_t4/README.md)).
- **Full vs reduced context.** The full test suite: 2.2× input, no gain; a whole file instead of one
  function: misses a bug ([context_ablation_t4](experiments/results/context_ablation_t4/README.md),
  [context_agents](experiments/results/context_agents/README.md)).
- **Single- vs multi-agent.** 0 vs 4 bugs caught, 3 vs 5 vulnerabilities (with tools)
  ([agents_demo_repo](experiments/results/agents_demo_repo/README.md)).

## 9. Metrics

How each metric of the brief is measured:

<details>
<summary><b>The metrics of the brief, one by one</b></summary>

- **Code correctness, pass@k, execution success:** pass@1, greedy, every answer executed in the
  sandbox (other languages: on a Kaggle VM); pass@1/5/20 from 20 samples per problem for the 3B
  models on HumanEval+ (unbiased estimator).
- **Unit-test pass rate, test coverage:** pytest and pytest-cov in the sandbox (line and branch).
- **Bug-detection precision / recall / F1:** per task, with accuracy as the headline because the
  models answer "yes" too often.
- **Code-quality metrics:** Ruff, Radon complexity, refactoring "improved and preserved".
- **Vulnerability detection:** accuracy, precision, recall; insecure generation rate with Bandit.
- **Hallucination / error rate:** review findings must quote an existing line or are dropped; false
  positives against the planted-flaw key (on demo_repo, 17 of the model's 21 review findings were
  wrong).
- **Latency, TTFT, tokens/s:** per request, from the streaming API.
- **GPU / CPU memory:** peak GPU memory in training and serving, llama-server RSS on the laptop.
- **Input / output tokens:** per request and per agent step.
- **Cost per task, energy:** GPU board power (`nvidia-smi`) and CPU package energy (RAPL), per item
  and per correct answer.

</details>

Cost is reported as energy and time rather than money: everything ran on free hardware, and the
energy per correct answer is what changes between options.

## 10. What did not work, and limits

- **The model is a noisy reviewer.** On demo_repo most of its review findings are wrong, and it
  answers "yes" to almost every bug-detection question in the base version. The platform keeps
  model findings separate from tool findings and never turns them into changes on their own.
- **500 verified clean reviews did not reduce false bug reports.**
- **Phi-4-mini got worse** from training on targets weaker than it already was.
- **Vulnerability detection stayed at chance level** (about 50 %) for every model, fine-tuned or not.
- **Open-ended repair:** the 1.5B stays far below the 9B model (36 % vs 66 %); the fine-tuned 3B
  gets nearer (62 to 63 %). That comparison is weaker than it looks: the 9B wrote the diagnoses and
  the realistic bugs the 3B was trained on, it ran untuned, and in separate runs.
- **The realistic bugs were shaped after the benchmark.** I chose the seven bug kinds of the v3 data
  after reading HumanEvalFix's results by bug type, and two of them have its category names
  (missing and excess logic). The 3B repair gain on HumanEvalFix may therefore partly come from
  training on its bug distribution, and runs A to E were compared on the same benchmark. The
  pre-registered evaluation above checks it on real bugs (ConDefects).
- **Fine-tuning the 3B costs HumanEval+** (81 → 72 % for run D) and no prompt brings it back
  (section 3). Training on the base model's own answers narrows the gap to 6 points; closing it
  would need training targets closer to the base's style.
- **Kaggle and laptop runs do not decode in exactly the same way.** On Kaggle, vLLM applied the
  Qwen2.5-Coder models' `generation_config` by default (repetition penalty 1.05, and top-k 20 when
  sampling); llama.cpp on the laptop applies none. A base model and its fine-tunes always ran with
  the same settings, so those comparisons hold, but absolute numbers from the two setups are not
  interchangeable.
- **The fine-tune was trained on Python only.** On HumanEvalFix in other languages it gains in
  JavaScript (+9.8, p = 0.0025) and Go (+8.1, p = 0.041), is level in C++ and Rust, and lower in Java
  (−6.7, p = 0.10) ([results](experiments/results/multilang_t4/README.md)). That experiment is the
  only one that ran model-written code outside the laptop's sandbox, on a disposable Kaggle VM.
- **Dense vs hybrid attention (RQ5)** is answered only by computed KV-cache sizes, not measured.
- **Single runs.** Most configurations ran once at temperature 0; paired tests on the same items
  are what makes differences meaningful, and differences without them are marked as such. The
  fine-tune was repeated with a second seed: its MBPP+ and repair gains held, its bug detection
  gain did not.
- **Scale of the agent evaluation.** The agent results come from one small repository built for the
  purpose; they show behaviour, not general accuracy.

## 11. Running it

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Docker, Node 22, and
[llama.cpp](https://github.com/ggml-org/llama.cpp) for the model server.

```bash
uv sync
uv run python -c "from security.sandbox import ensure_image; ensure_image()"   # test sandbox
(cd frontend && npm ci)
cp .env.example .env    # then set the token, the keys and the path to the GGUF model
# the default model (1.93 GB, Qwen research licence, non-commercial):
uv run hf download MedGm/Llama-Locali-Qwen2.5-Coder-3B-GGUF llama-locali-qwen2.5-coder-3b-q4_k_m.gguf --local-dir models
```

Then, one per terminal:

```bash
scripts/run.sh model      # the fine-tuned 3B (Q4_K_M) with llama.cpp and n-gram lookup
scripts/run.sh compare    # optional: a second model for the playground
scripts/run.sh backend    # the API
scripts/run.sh web        # http://localhost:3000
```

The backend, the web app and the model servers all read the one `.env`, so the token and keys are
written once ([.env.example](.env.example) explains each line). Without a model server, quick scans
still work; the assistant and the playground say they need one.

## 12. Reproducing the results

Every run folder in `experiments/results/` holds the answers (`samples.jsonl`), the scores, the
configuration with pinned model revisions and the commit it ran at. Each results README says how
it was produced. `bash experiments/scripts/reproduce.sh` rebuilds every derived table, plot and
summary from a clean checkout and re-executes the red-team cases; all of them came out identical,
and re-executing the scoring of four headline runs gave the same pass@1
([details](experiments/results/REPRODUCTION.md)). Kaggle jobs are in `training/kaggle/` and check
out the exact commit they were built from.

## 13. Use of AI tools

I used Claude Code (Anthropic's coding assistant) throughout the project. It wrote most of the
code, tests, experiment scripts and first drafts of the result write-ups, at my request and under
my review, in this repository. The research questions, the choice of models and methods, the
experimental design, the decisions after each result and the scope were mine; every number in this
report comes from a run whose answers and logs are committed, not from the assistant.

Its output was not taken on trust: claims in drafts were checked against the data and corrected
when they did not hold, the harness was validated on reference solutions before any model was
scored, and the bugs found along the way, including the two security gaps the red-team exposed,
were fixed with a test that reproduces them. The models used inside Locali are unrelated
to this: they are the fine-tuned Qwen2.5-Coder-3B and 1.5B described above.

## 14. Repository layout

<details>
<summary><b>Folders</b></summary>

| Path | Contents |
|---|---|
| `evaluation/` | Benchmark harness, tasks, sandboxed scoring, red-team cases |
| `training/` | Data builders, fine-tuning, merge, Kaggle jobs |
| `experiments/` | Model configs, scripts and every result with its README |
| `backend/` | FastAPI app, LangGraph agents, patches, validation, MLflow tracking |
| `frontend/` | Next.js web app |
| `mcp_servers/` | Repository, test-runner, static-analysis, documentation and issue MCP servers |
| `security/` | Sandbox, command allow-list, secret scanner, injection detector |
| `demo_repo/` | The flawed shop application used for agent and security tests |
| `docs/` | Research design, requirement checklist, UI notes, model cards; `docs/diagrams/` holds the diagrams as Excalidraw files (`make_diagrams.py` builds them, `export.py` renders the SVGs) |

</details>

Planning and status: [ROADMAP.md](ROADMAP.md); every requirement of the brief mapped to its code
and evidence: [docs/spec-checklist.md](docs/spec-checklist.md).
