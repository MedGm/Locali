"""W1 risk spikes on a Kaggle T4 (see docs/research-design.md and ROADMAP.md, W1).

The driver runs every spike in its own subprocess, so an OOM or kernel crash in one
spike does not stop the others. Each spike writes results/<spike>.json; the driver
writes results/summary.json.

    python w1_spikes.py                      # install deps, run all spikes
    python w1_spikes.py --spikes env,qwen25_qlora --skip-install
    python w1_spikes.py --spike env          # worker mode: one spike, in-process
"""

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

WORK = Path(os.environ.get("SPIKE_WORKDIR", "/kaggle/working"))
RESULTS = WORK / "results"
LOGS = WORK / "logs"

PINS = {
    "qwen2.5-coder-1.5b": ("Qwen/Qwen2.5-Coder-1.5B-Instruct", "2e1fd397ee46e1388853d2af2c993145b0f1098a"),
    "qwen3.5-2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    "phi-4-mini": ("microsoft/Phi-4-mini-instruct", "cfbefacb99257ffa30c83adab238a50856ac3083"),
    "qwen3.5-9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
}
SEQ_LEN = 2048
SEED = 3407
QWEN_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
QWEN_PARTS = ("<|im_start|>user\n", "<|im_start|>assistant\n")
PHI_PARTS = ("<|user|>", "<|assistant|>")
DATASET = "bigcode/self-oss-instruct-sc2-exec-filter-50k"

LLAMA_GGUF = ("unsloth/Qwen3.5-9B-GGUF", "3885219b6810b007914f3a7950a8d1b469d598a5", "Qwen3.5-9B-Q4_K_M.gguf")

# name -> timeout in seconds. Order is priority order.
SPIKES = {
    "env": 600,
    "qwen25_qlora": 1500,
    "qwen35_2b_lora16": 2700,
    "phi4mini_qlora": 2400,
    "peft_rslora": 1200,
    "peft_dora": 1500,
    "teacher_vllm": 3300,
    "teacher_llamacpp": 3000,  # fallback, runs only if teacher_vllm fails
    "teacher_hf4bit": 2100,  # run 1: 4.4 tok/s, too slow for dataset generation
}
# Run 2 repeats only what failed or changed in run 1 (see experiments/results/w1_spikes/).
DEFAULT_RUN = ["env", "qwen25_qlora", "qwen35_2b_lora16", "phi4mini_qlora", "teacher_vllm", "teacher_llamacpp"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- shared helpers


def reset_peak() -> None:
    import torch

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()


def peak_gb() -> dict:
    import torch

    return {
        "peak_allocated_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "peak_reserved_gb": round(torch.cuda.max_memory_reserved() / 2**30, 2),
    }


def load_model(key: str, *, four_bit: bool, sixteen_bit: bool = False):
    import torch
    from unsloth import FastLanguageModel

    repo, rev = PINS[key]
    # use_exact_model_name: without it Unsloth swaps in its own pre-quantized mirror
    # (e.g. "unsloth-bnb-4bit" dynamic quants) and silently drops `revision` (W1 run 1).
    kwargs = {
        "model_name": repo,
        "revision": rev,
        "use_exact_model_name": True,
        "max_seq_length": SEQ_LEN,
        "load_in_4bit": four_bit,
        "dtype": torch.float16,
    }
    if sixteen_bit:
        kwargs["load_in_16bit"] = True
    reset_peak()
    t0 = time.perf_counter()
    model, tok = FastLanguageModel.from_pretrained(**kwargs)
    resolved = getattr(model.config, "_name_or_path", None)
    return model, tok, {
        "repo": repo,
        "revision": rev,
        "resolved_name": resolved,
        "exact_model_loaded": resolved == repo,
        "load_s": round(time.perf_counter() - t0, 1),
        "load_peak_allocated_gb": peak_gb()["peak_allocated_gb"],
    }


def text_tokenizer(tok):
    """Multimodal models return a processor; training and counting need the text tokenizer."""
    return getattr(tok, "tokenizer", tok)


def linear_targets(model) -> list[str]:
    from torch import nn

    names = set()
    for name, module in model.named_modules():
        if any(s in name for s in ("lm_head", "vision", "visual")):
            continue
        if isinstance(module, nn.Linear):
            names.add(name.split(".")[-1])
    return sorted(names)


def add_lora(model, targets: list[str], **extra):
    from unsloth import FastLanguageModel

    return FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        lora_dropout=0,
        target_modules=targets,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=SEED,
        **extra,
    )


def build_texts(tok, n: int = 400, chat_kwargs: dict | None = None):
    from datasets import load_dataset

    ttok = text_tokenizer(tok)
    rows = load_dataset(DATASET, split=f"train[:{n}]")
    texts = []
    for r in rows:
        msgs = [
            {"role": "user", "content": r["instruction"]},
            {"role": "assistant", "content": r["response"]},
        ]
        texts.append(ttok.apply_chat_template(msgs, tokenize=False, **(chat_kwargs or {})))
    lens = [min(len(ttok(t)["input_ids"]), SEQ_LEN) for t in texts]
    return texts, lens


def train_run(model, tok, texts, lens, *, steps: int, batch: int, parts=None) -> dict:
    import inspect

    import torch
    from datasets import Dataset
    from transformers import TrainerCallback
    from trl import SFTConfig, SFTTrainer

    ttok = text_tokenizer(tok)
    cfg_params = inspect.signature(SFTConfig.__init__).parameters
    cfg = {
        "output_dir": "/tmp/spike_out",
        "per_device_train_batch_size": batch,
        "gradient_accumulation_steps": 1,
        "max_steps": steps,
        "learning_rate": 2e-4,
        "warmup_steps": 3,
        "lr_scheduler_type": "cosine",
        "optim": "adamw_8bit",
        "weight_decay": 0.01,
        "fp16": True,
        "bf16": False,
        "logging_steps": 1,
        "save_strategy": "no",
        "report_to": "none",
        "seed": SEED,
        "dataset_text_field": "text",
        "packing": False,
    }
    cfg["max_length" if "max_length" in cfg_params else "max_seq_length"] = SEQ_LEN
    cfg = {k: v for k, v in cfg.items() if k in cfg_params}
    trainer_params = inspect.signature(SFTTrainer.__init__).parameters
    tok_kw = {"processing_class": ttok} if "processing_class" in trainer_params else {"tokenizer": ttok}
    trainer = SFTTrainer(
        model=model, train_dataset=Dataset.from_dict({"text": texts}), args=SFTConfig(**cfg), **tok_kw
    )

    completion_only = None
    if parts:
        try:
            from unsloth.chat_templates import train_on_responses_only

            trainer = train_on_responses_only(trainer, instruction_part=parts[0], response_part=parts[1])
            completion_only = True
        except Exception as e:
            completion_only = f"failed: {type(e).__name__}: {e}"

    class StepTimer(TrainerCallback):
        def __init__(self):
            self.times, self.start = [], 0.0

        def on_step_begin(self, args, state, control, **kw):
            self.start = time.perf_counter()

        def on_step_end(self, args, state, control, **kw):
            torch.cuda.synchronize()
            self.times.append(time.perf_counter() - self.start)

    timer = StepTimer()
    trainer.add_callback(timer)
    reset_peak()
    trainer.train()

    losses = [h["loss"] for h in trainer.state.log_history if "loss" in h]
    steady = timer.times[3:] or timer.times
    mean_step = sum(steady) / len(steady)
    avg_tokens = sum(lens) / len(lens)
    return {
        "steps": steps,
        "batch": batch,
        "seq_len_cap": SEQ_LEN,
        "avg_sample_tokens": round(avg_tokens),
        "first_step_s": round(timer.times[0], 2),
        "mean_step_s": round(mean_step, 3),
        "approx_train_tokens_per_s": round(avg_tokens * batch / mean_step),
        "loss_first": round(losses[0], 4) if losses else None,
        "loss_last": round(losses[-1], 4) if losses else None,
        "completion_only_loss": completion_only,
        "trainable_params": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "train_peak": peak_gb(),
    }


def long_seq_probe(model, tok, texts, parts, chat_kwargs=None, candidates=(4, 2, 1)) -> dict:
    """Largest batch of ~2048-token samples that trains through the real trainer path.

    Run 1 called model(labels=...) directly, which materializes full-vocabulary logits and
    overstated memory; the trainer path uses Unsloth's chunked loss like real training does.
    """
    import torch

    ttok = text_tokenizer(tok)
    responses = "\n\n".join(texts)
    ids = ttok(responses)["input_ids"]
    chunk = SEQ_LEN - 64
    long_texts = []
    for i in range(8):
        body = ttok.decode(ids[i * chunk:(i + 1) * chunk])
        msgs = [{"role": "user", "content": "Continue."}, {"role": "assistant", "content": body}]
        long_texts.append(ttok.apply_chat_template(msgs, tokenize=False, **(chat_kwargs or {})))
    lens = [min(len(ttok(t)["input_ids"]), SEQ_LEN) for t in long_texts]
    for b in candidates:
        try:
            r = train_run(model, tok, long_texts, lens, steps=3, batch=b, parts=parts)
            return {"max_batch_at_2048": b, "long_seq_step_s": r["mean_step_s"], "long_seq_peak": r["train_peak"]}
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
    return {"max_batch_at_2048": 0}


def cast_bf16_to_fp16(model) -> int:
    """T4 has no native bf16; convert any bf16 tensors left after loading. Returns count."""
    import torch

    n = 0
    for t in list(model.parameters()) + list(model.buffers()):
        if t.dtype == torch.bfloat16:
            t.data = t.data.to(torch.float16)
            n += 1
    return n


# ---------------------------------------------------------------- spikes


def spike_env() -> dict:
    import importlib
    import importlib.metadata as md
    import shutil

    import torch

    packages = {}
    for p in [
        "torch", "transformers", "trl", "peft", "bitsandbytes", "unsloth", "unsloth_zoo", "triton",
        "datasets", "accelerate", "xformers", "flash-linear-attention", "causal-conv1d", "vllm",
    ]:
        try:
            packages[p] = md.version(p)
        except md.PackageNotFoundError:
            packages[p] = None
    smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader"],
        capture_output=True, text=True, check=False,
    ).stdout.strip().splitlines()
    fast_paths = {}
    for mod in ("fla", "causal_conv1d"):
        try:
            importlib.import_module(mod)
            fast_paths[mod] = True
        except Exception as e:
            fast_paths[mod] = f"{type(e).__name__}: {e}"[:200]
    return {
        "python": sys.version.split()[0],
        "torch_cuda": torch.version.cuda,
        "gpu_count": torch.cuda.device_count(),
        "nvidia_smi": smi,
        "packages": packages,
        "linear_attention_fast_paths": fast_paths,
        "disk_free_gb": round(shutil.disk_usage("/").free / 2**30, 1),
    }


def spike_qwen25_qlora() -> dict:
    model, tok, meta = load_model("qwen2.5-coder-1.5b", four_bit=True)
    model = add_lora(model, QWEN_TARGETS)
    texts, lens = build_texts(tok)
    result = train_run(model, tok, texts, lens, steps=30, batch=4, parts=QWEN_PARTS)
    probe = long_seq_probe(model, tok, texts, QWEN_PARTS)
    return {**meta, "method": "qlora_nf4_r16", "targets": QWEN_TARGETS, **result, **probe}


def spike_qwen35_2b_lora16() -> dict:
    fast = {}
    for mod in ("fla", "causal_conv1d"):
        try:
            __import__(mod)
            fast[mod] = True
        except Exception as e:
            fast[mod] = f"{type(e).__name__}"
    model, tok, meta = load_model("qwen3.5-2b", four_bit=False, sixteen_bit=True)
    # Run 1 crashed in the linear-attention in_proj: bf16 activations vs fp16 weights.
    bf16_cast = cast_bf16_to_fp16(model)
    model = add_lora(model, QWEN_TARGETS)
    chat_kwargs = {"enable_thinking": False}
    texts, lens = build_texts(tok, chat_kwargs=chat_kwargs)
    result = train_run(model, tok, texts, lens, steps=30, batch=4, parts=QWEN_PARTS)
    probe = long_seq_probe(model, tok, texts, QWEN_PARTS, chat_kwargs=chat_kwargs)
    return {
        **meta,
        "method": "lora16_fp16_r16 (QLoRA not recommended for Qwen3.5 by Unsloth)",
        "targets": QWEN_TARGETS,
        "bf16_tensors_cast_to_fp16": bf16_cast,
        "linear_attention_fast_paths": fast,
        **result,
        **probe,
    }


def spike_phi4mini_qlora() -> dict:
    model, tok, meta = load_model("phi-4-mini", four_bit=True)
    targets = linear_targets(model)
    model = add_lora(model, targets)
    texts, lens = build_texts(tok)
    result = train_run(model, tok, texts, lens, steps=30, batch=4, parts=PHI_PARTS)
    probe = long_seq_probe(model, tok, texts, PHI_PARTS)
    return {**meta, "method": "qlora_nf4_r16", "targets": targets, **result, **probe}


def _peft_variant(name: str, extra: dict) -> dict:
    model, tok, meta = load_model("qwen2.5-coder-1.5b", four_bit=True)
    stack = "unsloth"
    try:
        model = add_lora(model, QWEN_TARGETS, **extra)
    except Exception as e:
        # Unsloth rejected the option: fall back to plain PEFT on a fresh 4-bit model.
        log(f"unsloth get_peft_model({extra}) failed: {type(e).__name__}: {e}")
        stack = f"plain-peft (unsloth error: {type(e).__name__}: {str(e)[:200]})"
        del model
        reset_peak()
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig

        repo, rev = PINS["qwen2.5-coder-1.5b"]
        base = AutoModelForCausalLM.from_pretrained(
            repo,
            revision=rev,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            ),
            torch_dtype=torch.float16,
            device_map={"": 0},
        )
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True)
        model = get_peft_model(
            base, LoraConfig(r=16, lora_alpha=16, lora_dropout=0.0, target_modules=QWEN_TARGETS, **extra)
        )
    texts, lens = build_texts(tok, n=200)
    result = train_run(model, tok, texts, lens, steps=15, batch=4, parts=QWEN_PARTS)
    return {**meta, "method": name, "stack": stack, **result}


def spike_peft_rslora() -> dict:
    return _peft_variant("qlora_rslora_r16", {"use_rslora": True})


def spike_peft_dora() -> dict:
    return _peft_variant("qlora_dora_r16", {"use_dora": True})


TEACHER_PROMPT = (
    "You write short bug explanations for a training dataset. A mutation tool changed one line "
    "of this Python function and a unit test now fails.\n\n"
    "```python\ndef clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x {op} hi:\n"
    "        return hi\n    return x\n```\n\n"
    "Mutation: `{mutation}`. Failing test: `assert clamp({arg}, 0, 10) == {expected}`.\n"
    "Explain the bug in at most 3 sentences, then give the one-line fix."
)
TEACHER_CASES = [
    (">=", "x > hi -> x >= hi", "10", "10"),
    ("<", "x > hi -> x < hi", "5", "5"),
    ("==", "x > hi -> x == hi", "11", "10"),
    ("<=", "x > hi -> x <= hi", "3", "3"),
]

# Run 1 failed: no __main__ guard, and torch.cuda init forced vLLM to use spawn, which
# re-imports this file. Count GPUs via nvidia-smi so CUDA stays uninitialized here.
VLLM_INNER = r'''
import json, subprocess, sys, time


def main():
    from vllm import LLM, SamplingParams

    repo, rev, out_path, prompts = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
    n = len(subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout.strip().splitlines())
    kwargs = dict(model=repo, revision=rev, dtype="half", tensor_parallel_size=n, max_model_len=4096,
                  gpu_memory_utilization=0.90, enforce_eager=True, seed=3407,
                  limit_mm_per_prompt={"image": 0, "video": 0})
    if n < 2:
        kwargs["quantization"] = "bitsandbytes"
    t0 = time.perf_counter()
    llm = LLM(**kwargs)
    load_s = time.perf_counter() - t0
    convs = [[{"role": "user", "content": p}] for p in prompts]
    sp = SamplingParams(temperature=0.7, top_p=0.8, top_k=20, max_tokens=200)
    t1 = time.perf_counter()
    outs = llm.chat(convs, sp, chat_template_kwargs={"enable_thinking": False})
    gen_s = time.perf_counter() - t1
    out_tokens = sum(len(o.outputs[0].token_ids) for o in outs)
    json.dump({
        "gpu_count": n, "config": {k: v for k, v in kwargs.items() if k != "model"},
        "load_s": round(load_s, 1), "requests": len(prompts), "gen_s": round(gen_s, 2),
        "output_tokens": out_tokens, "throughput_tok_per_s": round(out_tokens / gen_s, 1),
        "samples": [o.outputs[0].text[:700] for o in outs[:2]],
    }, open(out_path, "w"), indent=2)


if __name__ == "__main__":
    main()
'''


def teacher_prompts(n: int = 32) -> list[str]:
    return [
        TEACHER_PROMPT.format(op=c[0], mutation=c[1], arg=c[2], expected=c[3])
        for c in (TEACHER_CASES * (n // len(TEACHER_CASES) + 1))[:n]
    ]


def spike_teacher_vllm() -> dict:
    venv = Path("/tmp/venv-vllm")
    py = venv / "bin" / "python"
    install_log = LOGS / "teacher_vllm_install.log"
    t0 = time.perf_counter()
    with open(install_log, "w") as fh:
        steps = [
            [sys.executable, "-m", "pip", "install", "-q", "uv"],
            [sys.executable, "-m", "uv", "venv", str(venv), "--python", "3.12"],
            [sys.executable, "-m", "uv", "pip", "install", "--python", str(py), "vllm"],
        ]
        for cmd in steps:
            rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False).returncode
            if rc != 0:
                raise RuntimeError(f"install step failed rc={rc}: {' '.join(cmd)} (see {install_log.name})")
    install_s = round(time.perf_counter() - t0, 1)
    version = subprocess.run(
        [str(py), "-c", "import vllm;print(vllm.__version__)"], capture_output=True, text=True, check=False
    )
    inner = Path("/tmp/vllm_inner.py")
    inner.write_text(VLLM_INNER)
    out = Path("/tmp/vllm_teacher.json")
    repo, rev = PINS["qwen3.5-9b"]
    proc = subprocess.run(
        [str(py), str(inner), repo, rev, str(out), json.dumps(teacher_prompts())],
        capture_output=True, text=True, check=False,
    )
    (LOGS / "teacher_vllm_inner.log").write_text(proc.stdout + "\n" + proc.stderr)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"vLLM run failed rc={proc.returncode}: {proc.stderr[-1500:]}")
    return {"vllm_version": version.stdout.strip(), "install_s": install_s, "repo": repo, "revision": rev,
            **json.loads(out.read_text())}


def spike_teacher_llamacpp() -> dict:
    import shutil
    import threading
    import urllib.request

    from huggingface_hub import hf_hub_download

    nvcc = shutil.which("nvcc") or next(
        (c for c in ("/usr/local/cuda/bin/nvcc",) if Path(c).exists()), None
    )
    if not nvcc:
        raise RuntimeError("nvcc not found: cannot build llama.cpp with CUDA")
    src = Path("/tmp/llama.cpp")
    t0 = time.perf_counter()
    with open(LOGS / "teacher_llamacpp_build.log", "w") as fh:
        for cmd in [
            ["git", "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp", str(src)],
            ["cmake", "-S", str(src), "-B", str(src / "build"), "-DGGML_CUDA=ON", "-DCMAKE_CUDA_ARCHITECTURES=75",
             "-DLLAMA_CURL=OFF", "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_CUDA_COMPILER={nvcc}"],
            ["cmake", "--build", str(src / "build"), "-j", "4", "--target", "llama-server"],
        ]:
            rc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False).returncode
            if rc != 0:
                raise RuntimeError(f"build step failed rc={rc}: {' '.join(cmd[:3])}")
    build_s = round(time.perf_counter() - t0, 1)

    repo, rev, fname = LLAMA_GGUF
    gguf = hf_hub_download(repo, fname, revision=rev)
    n_parallel = 16
    with open(LOGS / "teacher_llamacpp_server.log", "w") as server_log:
        server = subprocess.Popen(
            [str(src / "build" / "bin" / "llama-server"), "-m", gguf, "-ngl", "99", "-c", str(1024 * n_parallel),
             "--parallel", str(n_parallel), "--host", "127.0.0.1", "--port", "8081"],
            stdout=server_log, stderr=subprocess.STDOUT,
        )
        try:
            t1 = time.perf_counter()
            while time.perf_counter() - t1 < 600:
                try:
                    urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=5)
                    break
                except Exception:
                    if server.poll() is not None:
                        raise RuntimeError("llama-server exited during startup") from None
                    time.sleep(3)
            load_s = round(time.perf_counter() - t1, 1)

            prompts = teacher_prompts(32)
            tokens = [0] * len(prompts)
            samples = [""] * len(prompts)

            def call(i: int) -> None:
                body = {
                    "messages": [{"role": "user", "content": prompts[i]}],
                    "max_tokens": 200, "temperature": 0.7, "top_p": 0.8, "top_k": 20,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
                req = urllib.request.Request(
                    "http://127.0.0.1:8081/v1/chat/completions", data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                )
                d = json.load(urllib.request.urlopen(req, timeout=900))
                tokens[i] = d["usage"]["completion_tokens"]
                samples[i] = d["choices"][0]["message"]["content"]

            threads = [threading.Thread(target=call, args=(i,)) for i in range(len(prompts))]
            t2 = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            gen_s = time.perf_counter() - t2
        finally:
            server.terminate()
    return {
        "method": f"llama.cpp CUDA, Q4_K_M, {n_parallel} parallel slots, all GPUs",
        "gguf": {"repo": repo, "revision": rev, "file": fname},
        "build_s": build_s, "load_s": load_s, "requests": len(prompts), "gen_s": round(gen_s, 2),
        "output_tokens": sum(tokens), "throughput_tok_per_s": round(sum(tokens) / gen_s, 1),
        "samples": [x[:700] for x in samples[:2]],
    }


def spike_teacher_hf4bit() -> dict:
    import torch
    from unsloth import FastLanguageModel

    model, tok, meta = load_model("qwen3.5-9b", four_bit=True)
    FastLanguageModel.for_inference(model)
    ttok = text_tokenizer(tok)
    ttok.padding_side = "left"
    if ttok.pad_token is None:
        ttok.pad_token = ttok.eos_token
    texts = [
        ttok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True,
                                 enable_thinking=False)
        for p in teacher_prompts(8)
    ]
    batch = ttok(texts, return_tensors="pt", padding=True).to("cuda")
    reset_peak()
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**batch, max_new_tokens=200, do_sample=True, temperature=0.7, top_p=0.8, top_k=20)
    gen_s = time.perf_counter() - t0
    new = out[:, batch["input_ids"].shape[1]:]
    out_tokens = int((new != ttok.pad_token_id).sum())
    return {
        **meta, "method": "unsloth 4-bit, batch 8, HF generate", "gen_s": round(gen_s, 2),
        "output_tokens": out_tokens, "throughput_tok_per_s": round(out_tokens / gen_s, 1),
        "gen_peak": peak_gb(), "samples": ttok.batch_decode(new[:2], skip_special_tokens=True),
    }


# ---------------------------------------------------------------- driver


def run_worker(name: str) -> None:
    fn = globals()[f"spike_{name}"]
    t0 = time.perf_counter()
    try:
        data = {"spike": name, "status": "ok", **fn()}
    except Exception as e:
        data = {"spike": name, "status": "failed", "error": f"{type(e).__name__}: {e}"[:3000],
                "traceback": traceback.format_exc()[-4000:]}
    data["duration_s"] = round(time.perf_counter() - t0, 1)
    (RESULTS / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))
    log(f"{name}: {data['status']} in {data['duration_s']}s")


def install() -> dict:
    log("installing unsloth (log: logs/install.log)")
    t0 = time.perf_counter()
    with open(LOGS / "install.log", "w") as fh:
        rc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "unsloth", "unsloth_zoo"],
            stdout=fh, stderr=subprocess.STDOUT, check=False,
        ).returncode
    return {"returncode": rc, "seconds": round(time.perf_counter() - t0, 1)}


def run_driver(selected: list[str], skip_install: bool) -> None:
    summary = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "install": None, "spikes": {}}
    if not skip_install:
        summary["install"] = install()
        log(f"install: {summary['install']}")
    for name in selected:
        if name in ("teacher_llamacpp", "teacher_hf4bit") and summary["spikes"].get("teacher_vllm") == "ok":
            summary["spikes"][name] = "skipped (vLLM teacher works)"
            continue
        log(f"--- {name} (timeout {SPIKES[name]}s)")
        result_file = RESULTS / f"{name}.json"
        result_file.unlink(missing_ok=True)
        with open(LOGS / f"{name}.log", "w") as fh:
            try:
                rc = subprocess.run(
                    [sys.executable, os.path.abspath(__file__), "--spike", name],
                    stdout=fh, stderr=subprocess.STDOUT, timeout=SPIKES[name], check=False,
                ).returncode
                status = None
            except subprocess.TimeoutExpired:
                rc, status = None, "timeout"
        if not result_file.exists():
            tail = (LOGS / f"{name}.log").read_text()[-3000:]
            result_file.write_text(json.dumps(
                {"spike": name, "status": status or "crashed", "exit_code": rc, "log_tail": tail}, indent=2))
        summary["spikes"][name] = json.loads(result_file.read_text())["status"]
        log(f"{name}: {summary['spikes'][name]}")
    summary["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spike", help="worker mode: run one spike in this process")
    parser.add_argument("--spikes", default=",".join(DEFAULT_RUN), help="driver mode: comma-separated subset")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    if args.spike:
        run_worker(args.spike)
    else:
        selected = [s.strip() for s in args.spikes.split(",") if s.strip()]
        unknown = [s for s in selected if s not in SPIKES]
        if unknown:
            sys.exit(f"unknown spikes: {unknown}")
        run_driver(selected, args.skip_install)


if __name__ == "__main__":
    main()
