---
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
library_name: peft
license: apache-2.0
language: [en]
tags: [code, lora, qlora, unsloth, bug-repair, test-generation, code-review, built-with-llama]
datasets: [MedGm/locali-mix-v2]
---

# Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA

LoRA adapter for [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)
(revision `2e1fd39`). I trained it for Locali, a course project on small language models as
software-engineering assistants that run on modest hardware: a laptop CPU or one T4.

The "Llama" prefix in the name is a licence requirement, not a claim about the architecture.
Part of the training data contains unit tests written by Llama-3.1-70B (see Data), and the Llama 3.1
licence asks models trained on its outputs to carry the name.

Merged weights: [MedGm/Llama-Locali-Qwen2.5-Coder-1.5B](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B).
GGUF for llama.cpp: [MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-GGUF](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-GGUF).

## What it was trained to do

Four tasks, each with a fixed prompt format:

1. **Bug repair (T1).** Given a function, a failing test and its error, answer with one JSON line
   (`bug_location`, `bug_type`, `explanation`) followed by the fixed function in a python block.
2. **Test generation (T2).** Given a function, write a compact pytest file.
3. **Code review (T3).** Given code, answer `{"findings": [...]}` with line, category
   (bug / security / quality), severity and a one-sentence message. An empty list is a valid answer.
4. **Execution trace (T4).** Predict the exact value a call returns.

General instruction data (replay) is mixed in so the model keeps its normal coding behaviour.

## Training

QLoRA with Unsloth on one Kaggle T4: NF4 base, r = 16, alpha = 16, all attention and MLP
projections, 2 epochs, lr 2e-4 cosine, effective batch 16, max length 2048, loss on the answer
tokens only, seed 3407. 14,151 training examples, 2 h 04 min, 3.1 GB peak GPU memory.

## Results

Greedy decoding, vLLM FP16 base + this adapter, scored in a Docker sandbox. Paired against the base
model on the same items with an exact McNemar test.

| Task | Base | This adapter | p |
|---|---|---|---|
| Test generation, bug caught (HumanEval-based) | 46.3 | 82.3 | 2e-12 |
| Refactoring, behaviour preserved | 69.9 | 93.9 | 9e-10 |
| HumanEvalFix | 25.0 | 36.0 | 0.006 |
| Bug detection (HumanEvalPack) | 53.0 | 65.5 | 0.0004 |
| MBPP+ | 56.2 | 62.1 | 0.005 |
| HumanEval+ | 65.0 | 62.0 | 0.51 |
| CRUXEval-O | 30.1 | 28.7 | 0.31 |
| Vulnerability detection | 51.0 | 51.5 | 0.54 |

On held-out problems from its own training distribution, repair goes from 2.4 % to 63.7 % and
review from 26.2 % to 50.7 %.

Things to know before using it:

- The bug-detection gain did not reproduce in two sibling runs trained on the same data (16-bit
  LoRA, rsLoRA). It comes from the model saying "has a bug" less often, so treat it as unconfirmed.
- Repair works best on small, single-line faults like the ones it was trained on. On bug types such
  as missing logic or wrong variables it is much weaker (about 33–40 % on held-out examples).
- Vulnerability detection stays at chance level.
- It was evaluated on Python only.

The full write-up, with all comparisons and the code to reproduce them, is in the
[project repository](https://github.com/MedGm/Locali) under `experiments/results/finetune_v2/`.

## Usage

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
tok = AutoTokenizer.from_pretrained(base)
model = AutoModelForCausalLM.from_pretrained(base, torch_dtype="auto")
model = PeftModel.from_pretrained(model, "MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA")
```

With vLLM: `vllm serve Qwen/Qwen2.5-Coder-1.5B-Instruct --enable-lora --max-lora-rank 16 --lora-modules locali=MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA`.

The prompt formats are defined in `training/data/format.py`, `t2_tests.py`, `t3_review.py` and
`t4_trace.py` in the repository. The model does best when asked in those exact formats.

## Data

[MedGm/locali-mix-v2](https://huggingface.co/datasets/MedGm/locali-mix-v2). Labels come from
executing tests in a sandbox and from static analysers (Ruff, Bandit), never from a model.
Explanations of the bugs were written by Qwen3.5-9B. Seed problems and unit tests come from
[KAKA22/CodeRM-UnitTest](https://huggingface.co/datasets/KAKA22/CodeRM-UnitTest), whose tests
were generated with Llama-3.1-70B-Instruct. General instructions come from
[bigcode/self-oss-instruct-sc2-exec-filter-50k](https://huggingface.co/datasets/bigcode/self-oss-instruct-sc2-exec-filter-50k).
All training data was checked for 13-gram overlap with every evaluation set used above.

Built with Llama.

## Licence

The adapter is released under Apache-2.0, like the base model. Because the training data includes
Llama 3.1 outputs, the [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/)
terms on naming and attribution apply to it as well.
