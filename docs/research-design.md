# Research design: models, training method, data

Status: **accepted** 2026-09-15 — decisions in section 6.
Facts verified against Hugging Face model configs, model cards and dataset cards on 2026-09-15. Pinned revisions live in [`experiments/configs/models.yaml`](../experiments/configs/models.yaml).

## 1. Research questions

| ID | Question | Answered by |
|---|---|---|
| RQ1 | How well do 1–5B SLMs perform on software-engineering tasks without adaptation? | Baseline benchmark (W1–2) |
| RQ2 | How much does parameter-efficient fine-tuning improve the targeted SE tasks, and what does it cost on untargeted ones (forgetting)? | Base vs fine-tuned (W3–5) |
| RQ3 | What quality is lost, and what memory/latency/energy is gained, going FP16 → INT8 → INT4, on GPU and on CPU? | Quantization ladder (W6–7) |
| RQ4 | How much can prompt design and context reduction cut tokens without losing quality? | Prompt/context ablation (W6–7) |
| RQ5 | Does architecture (dense vs hybrid linear attention) change the efficiency trade-off? | KV-cache and long-context measurements |
| RQ6 | Can an agentic workflow with tools compensate for a small model's limits? | Single- vs multi-agent (W8–10) |
| RQ7 | Can the system resist injection and misuse under strict tool permissions? | Red-team evaluation (W13) |

## 2. Models

### 2.1 Selection criteria

1. The brief names Qwen and Phi; include at least one of each.
2. Open weights under a permissive license (Apache-2.0 or MIT), not gated.
3. 0.8–5B parameters for the studied models, so QLoRA fits a 16 GB T4 and INT4 inference fits a laptop CPU.
4. A larger same-family model as the "general-purpose LLM" reference.
5. Architectural diversity, to make RQ5 answerable.

### 2.2 Candidates and specifications

| | Qwen2.5-Coder-1.5B-Instruct | Qwen3.5-2B | Phi-4-mini-instruct | Qwen3.5-4B | Qwen3.5-9B |
|---|---|---|---|---|---|
| Role | **Fine-tune #1 (main)** | Benchmark; promotion candidate | **Fine-tune #2** | Benchmark | Reference "larger LLM" |
| Release | Sep 2024 | Feb 2026 | Feb 2025 | Feb 2026 | Feb 2026 |
| License | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 | Apache-2.0 |
| Parameters | 1.54 B | 2.27 B (incl. vision encoder) | 3.84 B | 4.66 B (incl. vision) | 9.65 B (incl. vision) |
| Architecture | Dense decoder | Hybrid: 18 Gated-DeltaNet linear-attention + 6 full-attention layers (1 full every 4) | Dense decoder | Hybrid: 24 linear + 8 full | Hybrid: 24 linear + 8 full |
| Layers / hidden | 28 / 1536 | 24 / 2048 | 32 / 3072 | 32 / 2560 | 32 / 4096 |
| Attention heads / KV heads / head dim | 12 / 2 / 128 | 8 / 2 / 256 | 24 / 8 / 128 | 16 / 4 / 256 | 16 / 4 / 256 |
| Context (native) | 32K | 262K | 128K | 262K | 262K |
| Vocabulary | 151,936 | 248,320 | 200,064 | 248,320 | 248,320 |
| Pretraining | 5.5T tokens, code-heavy | Multimodal early fusion, 201 languages | 5T tokens, synthetic + filtered web, Python-heavy code | same as 2B | same as 2B |
| Extras | FIM tokens (completion) | MTP head (speculative decoding); thinking mode, off by default per card | Function-calling format | Thinking mode **on** by default | Thinking on by default |

Excluded: Qwen2.5-Coder-3B (license "other", research-only); Qwen3.8 (no model below 27B); 7B+ dense coders (do not fit the low-resource thesis). An additional non-Qwen/Phi family (Gemma 4 E2B or Granite 4.2 3B, both released 2026) is optional for the baseline only and not yet verified.

### 2.3 Derived resource figures (computed, to be confirmed by measurement)

**Weights in memory**

| Model | FP16 | ~INT8 | ~INT4 (Q4_K_M / NF4) |
|---|---|---|---|
| Qwen2.5-Coder-1.5B | 3.1 GB | 1.6 GB | 1.1 GB (measured GGUF file) |
| Qwen3.5-2B | 4.5 GB | 2.4 GB | 1.2 GB (measured GGUF file) |
| Phi-4-mini | 7.7 GB | 4.1 GB | ~2.4 GB |
| Qwen3.5-4B | 9.3 GB | 5.0 GB | ~2.9 GB |
| Qwen3.5-9B | 19.3 GB — **does not fit a T4** | 10.3 GB | ~5.9 GB |

**KV cache per token (FP16)** = 2 × full-attention layers × KV heads × head dim × 2 bytes

| Model | Per token | At 8K tokens | Plus fixed state |
|---|---|---|---|
| Qwen2.5-Coder-1.5B | 28 KiB | 224 MiB | — |
| Qwen3.5-2B | 12 KiB | 94 MiB | ≈9 MiB recurrent state (18 linear layers) |
| Phi-4-mini | 128 KiB | 1.0 GiB | — |
| Qwen3.5-4B | 32 KiB | 250 MiB | ≈24 MiB recurrent state |

Phi-4-mini needs about 10× the KV memory of Qwen3.5-2B per token. That difference is the basis for RQ5.

**LoRA trainable parameters** (rank 16, all linear projections)

| Model | Trainable | Share |
|---|---|---|
| Qwen2.5-Coder-1.5B | ≈18.5 M | 1.2 % |
| Phi-4-mini | ≈23.1 M | 0.6 % |

### 2.4 Observations so far

- Laptop CPU, llama.cpp Q4_K_M: Qwen2.5-Coder-1.5B generates 16.5 tok/s; Qwen3.5-2B 11.1 tok/s ([results](../experiments/results/w0_smoke_laptop_cpu.json)).
- The Unsloth GGUF of Qwen3.5-2B started in thinking mode, even though the model card says non-thinking is the default for 2B. With thinking on, it used 1024 tokens without producing an answer. Thinking mode must therefore be set explicitly in every run and recorded in results.

### 2.5 Risks to test in W1

- Qwen3.5 linear-attention kernels (Triton-based) and vLLM support on a T4 (Turing, compute capability 7.5, no bf16, no FlashAttention-2).
- Unsloth support for Qwen3.5 training on a T4.
- Promotion rule: Qwen3.5-2B replaces Qwen2.5-Coder-1.5B as fine-tune #1 only if it passes both T4 spikes and scores higher on the W2 baseline.

## 3. Training method

### 3.1 Choice: supervised fine-tuning with QLoRA

| Option | Verdict | Reason |
|---|---|---|
| Full fine-tuning | Rejected | 1.5B with AdamW needs ≈16 bytes/param ≈ 25 GB; a T4 has 16 GB |
| **QLoRA** (4-bit NF4 base + LoRA adapters) | **Main method** | Fits every studied model on one T4; the method the brief names |
| LoRA on 16-bit base | Comparison run (main model only) | Measures the quality/memory/speed cost of 4-bit base quantization |
| DoRA or rsLoRA | One "other PEFT" run, if the W1 spike confirms Unsloth support | Cheap variant covering the brief's "other PEFT techniques" |
| Preference or RL training (DPO, GRPO with execution reward) | Out of scope; stretch goal | Multiplies GPU cost; solo time budget |
| Rejection-sampling fine-tuning (keep self-generated outputs that pass tests) | Stretch goal | Execution-verified, cheaper than RL |

Tooling: Unsloth + TRL `SFTTrainer` + PEFT, on Kaggle T4, with checkpoints and adapters pushed to Hugging Face Hub.

### 3.2 Training setup (starting point, tuned only on the validation split)

| Setting | Value | Note |
|---|---|---|
| Base quantization | NF4, double quantization | QLoRA standard |
| Compute dtype | FP16 | T4 has no bf16 |
| LoRA rank / alpha / dropout | 16 / 16 / 0 | Rank ablation 8 vs 64 only if time |
| Target modules | All linear projections (attention + MLP) | |
| Loss | Assistant response tokens only | The prompt is not learned |
| Chat template | The model's own | Identical at training and inference; thinking explicitly off |
| Max sequence length | 2048 | Covers >95 % of samples (verify in data statistics) |
| Effective batch | 16 (4 × 4 gradient accumulation) | |
| Optimizer | AdamW 8-bit, lr 2e-4, cosine, 3 % warmup, weight decay 0.01 | |
| Epochs | 2, keep best checkpoint by validation loss | |
| Seed | 3407; final config repeated with a second seed if time | |

### 3.3 Fine-tuned tasks vs prompted tasks

The model is specialized on three tasks. Each maps to an agent and has a verifiable output format.

| Fine-tuned task | Input | Output format | Serves agent |
|---|---|---|---|
| T1 · Bug diagnosis and repair | Function + failing test output | JSON diagnosis + corrected code | Debugging |
| T2 · Unit test generation | Function or module | Runnable pytest file | Test generation |
| T3 · Structured code review | Code or diff | JSON findings: category, severity, line, message, suggestion | Code review, quality, security |

Code generation, completion, explanation, refactoring and documentation are **not** trained. They are benchmarked on base and fine-tuned models, which also measures forgetting (RQ2).

## 4. Training data

### 4.1 Principles

1. **Verifiable labels.** Prefer data whose correctness is checked by executing tests or by static-analysis tools.
2. **License-clean.** Record every source's license. Avoid data generated by proprietary APIs whose terms restrict training competing models.
3. **Decontaminated.** Remove exact and 13-gram overlaps with every evaluation set.
4. **Grouped splits.** All samples derived from one seed function stay in the same split.
5. **Python only.**
6. **Budget.** ≈16k examples, ≈7M tokens: about 1.5–2 T4-hours per epoch for 1.5B, 4–5 for Phi-4-mini.

### 4.2 Sources (verified 2026-09-15)

| Source | License | Size | Content | Use |
|---|---|---|---|---|
| [KAKA22/CodeRM-UnitTest](https://huggingface.co/datasets/KAKA22/CodeRM-UnitTest) | Apache-2.0 (tests generated by Llama-3.1-70B, execution-filtered) | 77,192 tasks; 44–92 unittest cases each | Problem, ground-truth Python solution, unit tests | T1 mutation seeds; T2 targets |
| [bigcode/commitpackft](https://huggingface.co/datasets/bigcode/commitpackft) (python) | MIT | 136 MB JSONL | Real GitHub commits: message, old code, new code | T1 real fixes (filter "fix/bug", small diffs); T3 seeds |
| [bigcode/self-oss-instruct-sc2-exec-filter-50k](https://huggingface.co/datasets/bigcode/self-oss-instruct-sc2-exec-filter-50k) | ODC-BY; generated by open StarCoder2-15B | 50,661 | Instruction + execution-validated response (tests not included) | Replay set against forgetting; T3 seeds |
| [CyberNative/Code_Vulnerability_Security_DPO](https://huggingface.co/datasets/CyberNative/Code_Vulnerability_Security_DPO) | Apache-2.0 | 4,656 (multi-language) | Vulnerable vs secure code pairs | T3 security findings (Python subset) |
| [fasterinnerlooper/codereviewer](https://huggingface.co/datasets/fasterinnerlooper/codereviewer) | **Not stated** — mirror of Microsoft CodeReviewer | 317,216 (multi-language) | Human review comments on diffs | Optional T3 style data, **only after license verification** |

Rejected: Magicoder-OSS-Instruct-75K and CodeFeedback (outputs of proprietary OpenAI models); SWE-Gym (repository-level, too hard for 1–4B models and too long for 2048 tokens).

### 4.3 Construction pipelines

**T1 · Mutation-based bugs, execution-verified**
1. Take the ground-truth solution and its tests from CodeRM-UnitTest.
2. Apply one AST mutation operator: comparison flip, off-by-one, wrong variable, removed condition, swapped arguments, wrong return.
3. Run the tests in a sandbox. Keep only mutants that fail at least one test. The failure output is real, not generated.
4. Target: JSON diagnosis (bug type, location, explanation) + original code.
5. Add real bug-fix commits from CommitPackFT for realism. These carry no execution label.

**T2 · Test generation**
1. From CodeRM-UnitTest, convert the unittest cases to pytest.
2. Keep the smallest subset that passes on the ground truth and kills the most T1 mutants.
3. Target: that pytest file.

**T3 · Tool-grounded structured review**
1. Take seeds from T1 mutants, CommitPackFT and self-oss-instruct, plus vulnerable snippets.
2. Run Ruff, Radon, Bandit and Semgrep. Findings with line numbers become ground truth.
3. The teacher model (Qwen3.5-9B, section 6) writes natural-language messages for those findings. The finding set itself stays tool-verified.
4. Target: JSON findings list.

### 4.4 Proposed mixture

| Component | Examples | Share |
|---|---|---|
| T1 mutation bugs (execution-verified) | 5,000 | 31 % |
| T1 real bug-fix commits | 2,000 | 12 % |
| T2 unit test generation | 4,000 | 25 % |
| T3 structured review | 3,000 | 19 % |
| Replay: general code instructions | 2,000 | 13 % |
| **Total** | **16,000** | train 90 % / validation 5 % / internal test 5 % |

### 4.5 Known limitations

- CodeRM-UnitTest problems are competitive-programming style, not application code. CommitPackFT and self-oss-instruct balance this.
- Mutation bugs are simpler than real bugs. HumanEvalPack (human-written bugs) and the demo repository measure transfer.

## 5. Evaluation data (never used for training)

| Capability | Benchmark | License | Size | Metric |
|---|---|---|---|---|
| Code generation | EvalPlus HumanEval+ / MBPP+ | Apache-2.0 | 164 / 378 | pass@1, pass@10 |
| Bug detection, repair, explanation | HumanEvalPack Python (human-written bugs, bug type labels) | MIT | 164 | Detection P/R/F1 (buggy vs canonical), repair pass@1 |
| Code completion | SAFIM (fill-in-the-middle) | CC-BY-4.0 | Python subset | Exact/execution match |
| Code reasoning | CRUXEval | MIT | 800 | Output-prediction accuracy |
| Test generation | HumanEval+ functions, own harness | — | 164 | Pass rate on canonical, line/branch coverage, mutation score |
| Refactoring | HumanEval+ solutions, own harness | — | 164 | Tests still pass; Radon complexity and Ruff violation deltas |
| Vulnerability detection | SecurityEval (license not stated — cite, research use) | — | 121 | Detection rate vs Bandit/Semgrep ground truth |
| Contamination-free check | **Locali-Fresh**: 60–100 tasks written after Sep 2026 | own | 60–100 | Same metrics as above |
| End-to-end workflow | `demo_repo/` seeded bugs, vulnerabilities, missing tests | own | — | Bugs fixed, coverage gain, findings P/R |

Contamination note: Qwen3.5 (Feb 2026) postdates all public benchmarks listed. The latest LiveCodeBench release on the Hub was updated June 2025, so it cannot serve as a clean test for Qwen3.5. Locali-Fresh exists to cover this gap.

## 6. Decisions (2026-09-15)

| # | Decision | Alternative rejected | Rationale |
|---|---|---|---|
| D1 | **Fine-tune #2 is Phi-4-mini** | Qwen3.5-2B | The brief names Phi; a dense model with ~10× the KV cost of Qwen3.5-2B gives a strong architectural contrast. Qwen3.5-2B stays in the baseline and can still replace fine-tune #1 under the promotion rule. Phi fine-tuning remains first on the cut list. |
| D2 | **Teacher: Qwen3.5-9B** (INT4 on Kaggle T4, thinking off) writes natural-language diagnosis and review messages | Templates only | More natural targets at an open license. Budget ≈5–10 GPU-hours. Labels (bug location, failing tests, tool findings) stay execution- or tool-verified; the teacher only phrases them, and messages that contradict the label are discarded. |
| D3 | **Human review comments only if the license is verified** | Synthetic only | Trace the original Microsoft CodeReviewer license before any use. If permissive, add ≤1,000 Python samples to T3; otherwise T3 stays fully synthetic. |
