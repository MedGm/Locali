# Fine-tuning v1 — Qwen2.5-Coder-1.5B, QLoRA

Job: `training/kaggle/finetune/finetune_job.py` (commit in `train_report.json`), Kaggle T4 (training on GPU 0, generation on GPU 1). Data: mixture v1 (`../data_mix_v1/`), 10,384 training examples (1 dropped > 2048 tokens).
Training: Unsloth QLoRA (NF4), r = 16, alpha = 16, all attention and MLP projections, completion-only loss, effective batch 16, lr 2e-4 cosine, 2 epochs = 1,298 steps, **1 h 58 min, 3.0 GB peak memory**. Training loss 0.60 → ≈0.25 (epoch mean 0.30).
Generation: vLLM 0.29.0 serving base model + LoRA adapter (unmerged), FP16, eager, 16 concurrent requests, same prompts and decoding as the baselines. Scored locally in the Docker sandbox.
Adapter: kept outside git (`~/models/adapters/qwen2.5-coder-1.5b-qlora-v1`), to be published on the Hugging Face Hub.

## Base vs fine-tuned, paired per item (exact McNemar; * = p < 0.05)

| Task | n | qwen2.5-coder-1.5b | qwen2.5-coder-1.5b-ft-qlora | Δ (points) | only A | only B | McNemar p |
|---|---|---|---|---|---|---|---|
| humaneval_plus | 163 | 65.0 | 65.0 | +0.0 | 20 | 20 | 1 |
| mbpp_plus | 377 | 56.2 | 58.9 | +2.7 | 23 | 33 | 0.229 |
| completion | 163 | 35.6 | 34.4 | -1.2 | 11 | 9 | 0.824 |
| humanevalfix | 164 | 25.0 | 29.9 | +4.9 | 16 | 24 | 0.268 |
| cruxeval_o | 800 | 30.1 | 25.5 | -4.6 * | 73 | 36 | 0.000505 |
| refactor | 163 | 69.9 | 92.6 | +22.7 * | 2 | 39 | 7.84e-10 |
| testgen | 164 | 46.3 | 83.5 | +37.2 * | 10 | 71 | 1.8e-12 |
| bugdetect | 328 | 53.0 | 54.9 | +1.8 | 13 | 19 | 0.377 |
| vulndetect | 712 | 51.0 | 50.4 | -0.6 | 7 | 3 | 0.344 |
| securecodegen | 121 | 76.9 | 81.8 | +5.0 | 1 | 7 | 0.0703 |

## Findings

1. **Test generation is the big win** (T2 in the training data): bugs caught 46.3 → 83.5 %, generated tests correct 57.7 → 87.5 %, coverage 52.5 → 92.7 %, now close to Qwen3.5-4B (97.0 / 88.9 / 98.4 %).
2. **Behaviour-preserving refactoring rises 69.9 → 92.6 %** although refactoring was not a training task; the share of refactors that also improve quality metrics falls (12.3 → 9.8 %). Likely the model now returns cleaner single-block code and changes less — to be checked on the answers.
3. **Bug repair on human-written bugs (HumanEvalFix) +4.9 points, not significant.** T1 trains on injected single faults in a JSON-plus-code format; transfer to HumanEvalFix's human bugs and plain-code prompt is weak. In-distribution T1/T3 accuracy has not been measured yet.
4. **Code reasoning regresses (CRUXEval −4.6, p = 0.0005)** — measurable forgetting despite the 2,000-example replay set.
5. **Bug detection is unchanged and the yes-bias remains** (recall 88 → 93 %). T3 trained a different answer format (`findings` list) than the `has_bug` benchmark prompt; transfer did not happen.
6. **Answers are 28 % shorter** (99 → 71 output tokens). Speed and energy of this run are *not* comparable with the base model: the adapter was served unmerged through vLLM's LoRA path in eager mode (decode 12.1 vs 28.7 tok/s). Efficiency is compared after merging (quantization ladder, W6–7).

## Evaluation-loss diagnostic

Unsloth's evaluation path reports a wrong loss: validation loss on 64 *training* examples was 5.49 while their training loss was ≈0.3, with completion-only masking verified on both splits (42 % / 28 % supervised tokens). Checkpoints are therefore not selected by validation loss; the run uses a fixed schedule and keeps an adapter per epoch.

## Data integrity note

The first download from Kaggle stored a "502 Server Error" HTML page as two result files (refactor summary, securecodegen samples). Both were re-downloaded, every result file was JSON-validated, and the two runs were re-scored before building these tables.
