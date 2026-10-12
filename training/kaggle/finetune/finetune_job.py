"""Fine-tune with Unsloth on one Kaggle T4, then generate all benchmark answers with the adapter.

Phases (one session):
  1. train: Unsloth + TRL SFT on the mixture (Kaggle dataset `locali-mix-v1`), loss on assistant
     tokens only, best checkpoint by validation loss -> /kaggle/working/adapter
  2. generate: vLLM serves base model + LoRA adapter; `evaluation.run --generate-only` for every
     task (same runtime and prompts as the baselines); scoring happens locally in the sandbox.

Environment variables (set through build_notebook.py):
    MODEL=qwen2.5-coder-1.5b | phi-4-mini
    METHOD=qlora (4-bit NF4 base) | lora16 (16-bit base) | rslora (QLoRA + rank-stabilised LoRA)
    EPOCHS=2   MAX_STEPS=   (MAX_STEPS set => short smoke run, e.g. 30)
    SKIP_GENERATE=1         (train only)
    LIMIT=3                 (items per task during generation; smoke runs)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")  # training uses one GPU (W1: Unsloth split models over both)

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
CODE = Path("/tmp/locali")
WORK = Path("/kaggle/working")
INPUT_ROOT = Path("/kaggle/input")

MODELS = {
    "qwen2.5-coder-1.5b": {"repo": "Qwen/Qwen2.5-Coder-1.5B-Instruct", "revision": "2e1fd397ee46e1388853d2af2c993145b0f1098a"},
    "phi-4-mini": {"repo": "unsloth/Phi-4-mini-instruct", "revision": "75becc471c56fc34761ec998615ca6f8535c5a61"},
}
TASKS = ["humaneval_plus", "mbpp_plus", "humanevalfix", "bugdetect", "cruxeval_o",
         "testgen", "refactor", "completion", "securecodegen", "vulndetect"]
SEQ_LEN = 2048
SEED = 3407


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def setup() -> None:
    (WORK / "logs").mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        subprocess.run(["git", "clone", REPO, str(CODE)], check=True)
    subprocess.run(["git", "-C", str(CODE), "checkout", COMMIT], check=True)
    sys.path.insert(0, str(CODE))
    with open(WORK / "logs" / "setup.log", "a") as fh:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "unsloth", "unsloth_zoo",
                        "radon", "bandit", "datasets"], stdout=fh, stderr=subprocess.STDOUT, check=True)


def find_input(name: str) -> Path:
    found = sorted(INPUT_ROOT.rglob(name))
    if not found:
        raise FileNotFoundError(f"{name} not found under {INPUT_ROOT}")
    return found[0]


def load_split(name: str) -> list[dict]:
    return [json.loads(line) for line in find_input(f"{name}.jsonl").read_text().splitlines() if line.strip()]


def train(model_id: str, method: str, epochs: float, max_steps: int | None) -> dict:
    # unsloth must be imported before transformers/trl so its patches apply
    # isort: off
    import torch
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    # isort: on

    spec = MODELS[model_id]
    model, tok = FastLanguageModel.from_pretrained(
        model_name=spec["repo"], revision=spec["revision"], use_exact_model_name=True,
        max_seq_length=SEQ_LEN, load_in_4bit=method != "lora16", dtype=torch.float16,
    )
    assert model.config._name_or_path == spec["repo"], model.config._name_or_path
    model = FastLanguageModel.get_peft_model(
        model, r=16, lora_alpha=16, lora_dropout=0, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        if model_id.startswith("qwen") else ["qkv_proj", "o_proj", "gate_up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=SEED, use_rslora=method == "rslora",
    )

    def render(rows: list[dict]) -> tuple[Dataset, int]:
        """Conversational prompt/completion pairs: TRL computes the loss on the completion only,
        for training and validation alike (W4 smoke run: masking applied to training data only
        left validation loss at 4.4 against 0.5 for training)."""
        prompts, completions, too_long = [], [], 0
        for row in rows:
            text = tok.apply_chat_template(row["messages"], tokenize=False)
            if len(tok(text)["input_ids"]) > SEQ_LEN:
                too_long += 1
                continue
            prompts.append(row["messages"][:-1])
            completions.append(row["messages"][-1:])
        return Dataset.from_dict({"prompt": prompts, "completion": completions}), too_long

    train_ds, train_dropped = render(load_split("train"))
    val_ds, val_dropped = render(load_split("val"))
    log(f"train {len(train_ds)} (dropped {train_dropped} > {SEQ_LEN} tokens), val {len(val_ds)}")

    config = SFTConfig(
        output_dir=str(WORK / "checkpoints"), per_device_train_batch_size=4, gradient_accumulation_steps=4,
        per_device_eval_batch_size=4, num_train_epochs=epochs, max_steps=max_steps or -1,
        learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.03, weight_decay=0.01,
        optim="adamw_8bit", fp16=True, bf16=False, logging_steps=10, eval_strategy="steps",
        eval_steps=100 if not max_steps else max(10, max_steps // 3), save_strategy="steps",
        save_steps=100 if not max_steps else max(10, max_steps // 3), save_total_limit=2,
        load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
        report_to="none", seed=SEED, max_length=SEQ_LEN, packing=False, completion_only_loss=True,
    )
    trainer = SFTTrainer(model=model, processing_class=tok, train_dataset=train_ds, eval_dataset=val_ds, args=config)

    def supervised_fraction(loader) -> float:
        labels = next(iter(loader))["labels"]
        return round(float((labels != -100).float().mean()), 3)

    masking = {"train": supervised_fraction(trainer.get_train_dataloader()),
               "val": supervised_fraction(trainer.get_eval_dataloader())}
    log(f"fraction of supervised tokens in one batch: {masking}")
    if not 0.02 < masking["val"] < 0.9 or abs(masking["train"] - masking["val"]) > 0.3:
        raise RuntimeError(f"loss masking looks wrong: {masking}")
    start = time.time()
    result = trainer.train()
    adapter_dir = WORK / "adapter"
    model.save_pretrained(str(adapter_dir))
    tok.save_pretrained(str(adapter_dir))
    report = {
        "model": model_id, "method": method, "train_examples": len(train_ds), "val_examples": len(val_ds),
        "dropped_too_long": train_dropped + val_dropped, "train_seconds": round(time.time() - start),
        "train_loss": result.training_loss, "best_eval_loss": trainer.state.best_metric,
        "best_checkpoint": trainer.state.best_model_checkpoint, "log_history": trainer.state.log_history,
        "peak_memory_gb": round(torch.cuda.max_memory_reserved() / 2**30, 2), "commit": COMMIT,
        "supervised_token_fraction": masking,
    }
    (WORK / "train_report.json").write_text(json.dumps(report, indent=2))
    return report


def generate(model_id: str, method: str) -> None:
    from training.kaggle.common import (
        install_vllm,
        start_power_log,
        start_server,
        stop_server,
        wait_healthy,
    )

    spec = MODELS[model_id]
    logs = WORK / "logs"
    install_vllm(logs / "setup.log")
    power = start_power_log(WORK / "gpu_power.csv")
    adapter = str(WORK / "adapter")
    # GPU 1: the training process still holds memory on GPU 0 (W4 smoke run: vLLM refused to start).
    server = start_server(spec["repo"], spec["revision"], gpus=[1], port=8000, logfile=logs / "vllm.log",
                          extra=["--enable-lora", "--max-lora-rank", "16", "--lora-modules", f"adapter={adapter}"])
    try:
        if not wait_healthy(8000, server):
            raise RuntimeError("vLLM with adapter failed to start, see logs/vllm.log")
        from evaluation.gpu_energy import attach_gpu_energy

        for task in TASKS:
            out = WORK / "results" / task / f"{model_id}-ft-{method}__fp16__kaggle-t4"
            start = time.time()
            with open(logs / "generate.log", "a") as gen_log:
                rc = subprocess.run(
                    [sys.executable, "-m", "evaluation.run", "--benchmark", task, "--generate-only", "--workers", "16",
                     "--model-id", f"{model_id}-ft-{method}", "--model-revision", spec["revision"],
                     "--quantization", "fp16", "--runtime", "vLLM T4x1 eager + LoRA adapter",
                     "--base-url", "http://127.0.0.1:8000/v1", "--served-model", "adapter", "--out", str(out),
                     "--notes", f"fine-tuned ({method}) adapter at commit {COMMIT}",
                     *(["--limit", os.environ["LIMIT"]] if os.environ.get("LIMIT") else [])],
                    cwd=CODE, stdout=gen_log, stderr=subprocess.STDOUT, check=False,
                ).returncode
            if rc == 0 and (out / "summary.json").exists():
                energy = attach_gpu_energy(out, (WORK / "gpu_power.csv").read_text(), [1], start, time.time())
                log(f"{task}: done, GPU energy {energy['total_j']} J")
            else:
                log(f"{task}: FAILED rc={rc}")
    finally:
        stop_server(server)
        power.terminate()


def main() -> None:
    model_id = os.environ.get("MODEL", "qwen2.5-coder-1.5b")
    method = os.environ.get("METHOD", "qlora")
    max_steps = int(os.environ["MAX_STEPS"]) if os.environ.get("MAX_STEPS") else None
    setup()
    report = train(model_id, method, float(os.environ.get("EPOCHS", "2")), max_steps)
    log(f"trained: loss {report['train_loss']:.4f}, best eval {report['best_eval_loss']}, {report['train_seconds']} s")
    if not os.environ.get("SKIP_GENERATE"):
        generate(model_id, method)
    log("done")


if __name__ == "__main__":
    main()
